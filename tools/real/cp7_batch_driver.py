"""CP7-10 / RG-09: driver lô 1 video trên ngăn xếp thật qua Control API (hồ sơ production).

Driver khởi động launcher, lấy phiên từ URL /launch (không ghi URL ra đâu), tạo đúng một lô 1 video bằng
`POST /v1/batches`, theo dõi từng stage trong cp_stage_runs bằng truy vấn chỉ đọc và ghi trace đã che bí mật.
Trần: <= 25 lời gọi AI, ledger +3 USD, Drive <= 200 MiB, <= 2 giờ. Cách dừng: `python tools/launcher/launcher.py stop`
(driver luôn gọi ở cuối). Không in capability, cookie, token hay file ID.
Driver không làm thay production: staging, media seed và render config do `launcher start` tự tạo; driver chỉ đọc.
"""
from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import os
import re
import ssl
import subprocess
import sys
import time
import types
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import cp7_common as c

REPO = Path(__file__).resolve().parents[2]
if str(REPO / 'src') not in sys.path:
    sys.path.insert(0, str(REPO / 'src'))
LAUNCHER = REPO / 'tools' / 'launcher' / 'launcher.py'
PROFILE_JSON = REPO / 'tools' / 'launcher' / 'prod' / 'profile.json'
PRODUCTION_PY = REPO / 'src' / 'controlplane' / 'api' / 'wiring' / 'production.py'
HOST = '127.0.0.1'
PORT = 8443

STAGES = ('analyze', 'script', 'plan', 'media_select', 'tts', 'align', 'process', 'render', 'qc', 'sync', 'complete')
STAGE_LABELS = {
    'analyze': 'snapshot', 'script': 'script_ai', 'plan': 'plan', 'media_select': 'media_select', 'tts': 'tts',
    'align': 'align', 'process': 'process', 'render': 'render', 'qc': 'qc',
    'sync': 'upload_drive_and_verify', 'complete': 'completion',
}
AI_CALL_CAP = 25
LEDGER_CEILING_USD = Decimal('3')
DRIVE_CAP_BYTES = 200 * 1024 * 1024
RUN_DEADLINE_SECONDS = 7200
READY_LIMIT_SECONDS = 300
POLL_SECONDS = 5
ELIGIBLE_WAIT_SECONDS = 600
TRACE_KEYS = ('snapshot_id', 'snapshot_payload_sha256', 'model_refs', 'prompt_refs', 'config_revision', 'profile_sha256',
              'script_version_id', 'script_sha256', 'input_revisions')
CLEANUP_STATES = ('CLEANUP_ELIGIBLE', 'CLEANUP_AUTHORIZED', 'DELETED')
TERMINAL_JOB = ('COMPLETED', 'FAILED_FINAL')
RENDER_CONFIG_SCOPES = (('preset', 'bold-yellow'), ('preset', 'output-profile'), ('policy', 'quality'))
TEMPORAL_PORT = 7233
TEMPORAL_NAMESPACE = 'default'
WATCHED_WORKFLOWS = ('ProductionBatchWorkflow', 'VideoProductionWorkflow', 'DebugStageWorkflow')


class BatchDriverError(RuntimeError):
    pass


class BlockedError(BatchDriverError):
    """Thông điệp luôn bắt đầu bằng 'BLOCKED: '."""


def find_reruns(before, after):
    """Stage SUCCEEDED ở before mà after thiếu, khác status, attempt hoặc stage_run_id."""
    bad = []
    for name, row in before.items():
        if row.get('status') != 'SUCCEEDED':
            continue
        now = after.get(name)
        if now is None or any(now.get(k) != row.get(k) for k in ('status', 'attempt', 'stage_run_id')):
            bad.append(name)
    return sorted(bad)


def evaluate_resume(before, after, ready_seconds, limit=READY_LIMIT_SECONDS):
    ok = (isinstance(ready_seconds, (int, float)) and not isinstance(ready_seconds, bool)
          and ready_seconds >= 0 and ready_seconds <= limit)
    return {
        'ready_ok': bool(ok),
        'reruns': find_reruns(before, after),
        'completed_stages': sum(1 for row in before.values() if row.get('status') == 'SUCCEEDED'),
    }


def trace_missing(trace):
    return [k for k in TRACE_KEYS if k not in trace or trace[k] in (None, '', [], {}, ())]


def budget_violations(ai_calls, spent_usd, drive_bytes, elapsed_seconds):
    bad = []
    if ai_calls > AI_CALL_CAP:
        bad.append('ai_calls')
    if Decimal(str(spent_usd)) > LEDGER_CEILING_USD:
        bad.append('ledger_usd')
    if drive_bytes > DRIVE_CAP_BYTES:
        bad.append('drive_bytes')
    if elapsed_seconds > RUN_DEADLINE_SECONDS:
        bad.append('elapsed')
    return bad


def format_failed_stage(failed):
    """Mô tả stage hỏng của job FAILED_FINAL; None nếu không có hàng stage FAILED_FINAL hay OUTCOME_UNKNOWN."""
    if failed is None:
        return 'stage=none'
    return f'stage={failed[0]} status={failed[1]} activity={failed[3]} code={failed[2]} field_errors={failed[4]}'


def format_render_config(rows):
    """Một dòng trạng thái ConfigRevision mới nhất của ba scope render config mà resolve_inputs đòi PUBLISHED. RenderConfigNotSeeded là LookupError không có .code nên activity chỉ báo ACTIVITY_ABORTED; dòng này cho thấy scope nào thiếu. rows là (scope_kind, scope_key, status); scope không có hàng ghi MISSING."""
    seen = {(row[0], row[1]): row[2] for row in rows or []}
    return 'render_config=[' + ' '.join(f'{kind}/{key}=' + str(seen.get((kind, key), 'MISSING')) for kind, key in RENDER_CONFIG_SCOPES) + ']'


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


_LAUNCH_TOKEN = re.compile(r'(?i)\b(?:' + '|'.join(('cap', 'cp_session', 'csrf_token')) + r')\s*[=:]\s*\S+')


def format_diagnostic(diag, log_tail, limit=1500):
    """Một dòng mô tả vì sao job FAILED_FINAL: mọi hàng cp_stage_runs của job, trạng thái job, đuôi serve.log; đã che bí mật."""
    stages = []
    for row in diag.get('stages') or []:
        text = f"{row['stage']}#{row['attempt']}={row['status']}"
        if row.get('code'):
            text += '/' + str(row['code'])
        if row.get('wait_reason'):
            text += '/wait=' + str(row['wait_reason'])
        if row.get('message'):
            text += '/msg=' + str(row['message'])
        stages.append(text)
    job = diag.get('job') or {}
    text = ('job=' + str(job.get('status')) + ' job_wait=' + str(job.get('wait_reason')) + ' stages=[' + (';'.join(stages) or 'no_stage_rows')
            + '] serve_log_tail=[' + str(log_tail)[:600] + ']')
    return _LAUNCH_TOKEN.sub('[REDACTED:launch]', c.redact(text))[:limit]


def serve_log_tail(path, max_bytes=4000, lines=6):
    """Đuôi serve.log của ứng dụng (chỉ đọc); không đọc được thì trả 'no_serve_log'."""
    path = Path(path)
    try:
        size = path.stat().st_size
        with path.open('rb') as handle:
            handle.seek(max(0, size - max_bytes))
            raw = handle.read().decode('utf-8', errors='replace')
    except OSError:
        return 'no_serve_log'
    kept = [line.strip() for line in raw.splitlines() if line.strip()]
    return ' | '.join(kept[-lines:])


def collect_diagnostic(db, job_id):
    try:
        return format_diagnostic(db.job_diagnostics(job_id), serve_log_tail(db.layout.serve_log))
    except Exception as exc:
        return 'diagnostic_error=' + type(exc).__name__


def collect_render_config(db):
    try:
        return format_render_config(db.render_config_status())
    except Exception as exc:
        return 'render_config_error=' + type(exc).__name__


def render_config_published(rows):
    """True khi cả ba scope RENDER_CONFIG_SCOPES có revision mới nhất PUBLISHED."""
    seen = {(row[0], row[1]): row[2] for row in rows or []}
    return all(seen.get(scope) == 'PUBLISHED' for scope in RENDER_CONFIG_SCOPES)


def launcher_seed_line(text):
    """Các dòng của stdout launcher start có chữ seed (đã che bí mật); không có thì no_seed_line."""
    lines = [line.strip() for line in str(text or '').splitlines() if 'seed' in line.lower()]
    return _LAUNCH_TOKEN.sub('[REDACTED:launch]', c.redact(' | '.join(lines)))[:300] if lines else 'no_seed_line'


def require_render_config(db):
    """Điều kiện chặn: ba scope render config phải PUBLISHED trước post_batch; trả dòng đo."""
    try:
        rows = db.render_config_status()
    except Exception as exc:
        raise BlockedError('BLOCKED: không đọc được trạng thái render config: ' + type(exc).__name__) from None
    line = format_render_config(rows)
    if not render_config_published(rows):
        raise BlockedError('BLOCKED: render config chưa PUBLISHED trước khi tạo lô, không tạo lô; ' + line)
    return line


def format_start_output(text, limit=400):
    """Đuôi stdout/stderr của `launcher start` (đã che bí mật) để BLOCKED nêu được vì sao không có URL /launch; 'Worker đang chạy' được gắn nhãn worker_already_running."""
    raw = str(text or '')
    body = _LAUNCH_TOKEN.sub('[REDACTED:launch]', c.redact(' | '.join(line.strip() for line in raw.splitlines() if line.strip())))
    label = 'worker_already_running ' if 'Worker đang chạy' in raw else ''
    return label + 'launcher_start_output=[' + body[-limit:] + ']'


def format_script_length(payload, profile):
    """Ước lượng thời lượng giọng đọc từ tổng word_count của script so với voice.duration_range_ms của profile production (chỉ đọc); cho biết script quá ngắn, quá dài hay nằm trong khoảng trước khi CreateVoiceTrack đo thật."""
    segments = payload.get('segments') if isinstance(payload, dict) else None
    if not isinstance(segments, list):
        return 'script_length=[no_segments]'
    words = sum(s['word_count'] for s in segments if isinstance(s, dict) and type(s.get('word_count')) is int)
    voice = profile['voice']
    wpm = voice['speech_rate_wpm']['value']
    low = voice['duration_range_ms']['value']['min']
    high = voice['duration_range_ms']['value']['max']
    est_ms = int(words * 60000 / wpm)
    verdict = 'too_short' if est_ms < low else 'too_long' if est_ms > high else 'within_range'
    return f'script_length=[segments={len(segments)} words={words} wpm={wpm} est_ms={est_ms} range_ms={low}-{high} verdict={verdict}]'


def collect_script_length(db, prefix):
    try:
        plan = _plan_row(db, prefix)
        script = None if plan is None else _script_row(db, plan[0].get('script_version_id'))
        profile = json.loads(PROFILE_JSON.read_text(encoding='utf-8'))
        return format_script_length(None if script is None else script[0], profile)
    except Exception as exc:
        return 'script_length_error=' + type(exc).__name__


def video_key_prefix(workspace_id, batch_id):
    """Tiền tố record_key của mọi bản ghi creative do các video con của lô ghi: <ws>:<batch_id>:video:."""
    return f'{workspace_id}:{batch_id}:video:'


def list_running_workflows(host=HOST, port=TEMPORAL_PORT, namespace=TEMPORAL_NAMESPACE):
    """Chỉ đọc: [(workflow_type, workflow_id)] của mọi workflow RUNNING trên Temporal. Driver không cancel, terminate hay signal."""
    import asyncio
    from temporalio.client import Client

    async def _list():
        client = await Client.connect(f'{host}:{port}', namespace=namespace)
        return [(item.workflow_type, item.id) async for item in client.list_workflows(query='ExecutionStatus = "Running"')]

    return asyncio.run(asyncio.wait_for(_list(), 90))


def require_no_other_workflows(lister=list_running_workflows):
    """Điều kiện chặn giữa stop và start: không workflow lô, video hay debug nào đang RUNNING; trả 0. Ngược lại BLOCKED kèm id (tối đa 20)."""
    try:
        rows = lister()
    except Exception as exc:
        raise BlockedError('BLOCKED: TEMPORAL_UNREACHABLE: ' + type(exc).__name__) from None
    busy = sorted(f'{kind}={ident}' for kind, ident in rows if kind in WATCHED_WORKFLOWS)
    if busy:
        raise BlockedError('BLOCKED: OTHER_WORKFLOWS_RUNNING count=' + str(len(busy)) + ' ids=[' + ', '.join(busy[:20]) + ']')
    return 0


def format_batch_running(batch_id, rows, db_status):
    """Một dòng trạng thái lô B sau lượt: workflow của lô (id == B hoặc bắt đầu bằng B + ':') còn RUNNING trên Temporal và trạng thái dòng lô trong DB."""
    ids = sorted(ident for _, ident in rows if ident == batch_id or ident.startswith(batch_id + ':'))
    return f'batch_after_run=[db_status={db_status} temporal_running={len(ids)} ids={ids}]'


def collect_batch_running(db, batch_id, lister=list_running_workflows):
    try:
        return format_batch_running(batch_id, lister(), db.batch_status(batch_id))
    except Exception as exc:
        return 'batch_after_run_error=' + type(exc).__name__


# --- điều khiển launcher -----------------------------------------------------------------------------------------

def load_launcher():
    spec = importlib.util.spec_from_file_location('cp7_launcher_in_driver', LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def child_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ('M2_TEST_PG_DSN', 'CONTROLPLANE_DSN')}
    env.update({'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
    env.update(extra)
    return env


def run_launcher(command, timeout, env=None):
    assert command in ('start', 'stop')
    try:
        proc = subprocess.run([sys.executable, '-B', str(LAUNCHER), command], cwd=REPO, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout,
                              check=False, env=env or child_env())
    except subprocess.TimeoutExpired:
        raise BlockedError('BLOCKED: launcher ' + command + ' vượt hạn') from None
    return proc.returncode, c.redact((proc.stdout or '') + (proc.stderr or ''))


def stop_until_exited(attempts=4):
    """stop idempotent, chỉ chờ 60 giây mỗi lần; gọi lại tới khi thoát, không ép tắt, không sửa launcher."""
    last = ''
    for try_no in range(1, attempts + 1):
        rc, text = run_launcher('stop', 120)
        if rc == 0:
            return try_no
        last = text[-400:]
    raise BlockedError('BLOCKED: launcher stop không thoát sau ' + str(attempts) + ' lần: ' + last)


def start_capturing(work_dir, name):
    work_dir = Path(work_dir)
    capture = work_dir / 'capture_launch_url.cmd'
    if not capture.exists():
        capture.write_text('@echo off\r\n>"%CP7_LAUNCH_URL_FILE%" echo(%*\r\nexit /b 0\r\n', encoding='ascii')
    url_file = work_dir / (name + '.url')
    env = child_env(BROWSER=str(capture), CP7_LAUNCH_URL_FILE=str(url_file))
    started = time.monotonic()
    rc, text = run_launcher('start', 900, env)
    if rc != 0:
        raise BlockedError('BLOCKED: launcher start rc=' + str(rc) + ': ' + text[-400:])
    for _ in range(120):
        if url_file.is_file() and url_file.stat().st_size > 0:
            break
        time.sleep(1)
    else:
        raise BlockedError('BLOCKED: không bắt được URL /launch trong 120 giây; ' + format_start_output(text))
    raw = url_file.read_text(encoding='utf-8').strip()
    url_file.unlink()
    if '/launch' not in raw:
        raise BlockedError('BLOCKED: URL /launch không hợp lệ')
    return raw[raw.index('/launch'):], started, text


# --- Control API -------------------------------------------------------------------------------------------------

class ApiSession:
    def __init__(self, cert_file):
        self._ctx = ssl.create_default_context(cafile=str(cert_file))
        self.cookies = {}

    def _request(self, method, path, headers, body):
        conn = http.client.HTTPSConnection(HOST, PORT, timeout=30, context=self._ctx)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader('Host', f'{HOST}:{PORT}')
            for key, value in headers.items():
                conn.putheader(key, value)
            if body is not None:
                conn.putheader('Content-Length', str(len(body)))
            conn.endheaders(body)
            response = conn.getresponse()
            return response.status, response.getheaders(), response.read().decode('utf-8', errors='replace')
        finally:
            conn.close()

    def open(self, launch_path):
        status, headers, _ = self._request('GET', launch_path, {}, None)
        if status != 303:
            raise BlockedError('BLOCKED: /launch không cấp phiên, status=' + str(status))
        for key, value in headers:
            if key.lower() == 'set-cookie':
                pair = value.split(';', 1)[0]
                name, _, val = pair.partition('=')
                if name in ('cp_session', 'csrf_token'):
                    self.cookies[name] = val
        if 'cp_session' not in self.cookies or 'csrf_token' not in self.cookies:
            raise BlockedError('BLOCKED: /launch thiếu cookie phiên')

    def call(self, method, path, payload=None):
        headers = {
            'Cookie': '; '.join(f'{name}={value}' for name, value in self.cookies.items()),
            'Origin': f'https://{HOST}:{PORT}',
            'X-CSRF-Token': self.cookies['csrf_token'],
            'Content-Type': 'application/json',
        }
        if method != 'GET':
            headers['Idempotency-Key'] = str(uuid.uuid4())
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        status, _, text = self._request(method, path, headers, body)
        return status, (json.loads(text) if text.strip() else None)

    def post_batch(self, target=1):
        status, receipt = self.call('POST', '/v1/batches', {'target_completed_videos': target})
        if status != 202:
            raise BatchDriverError('POST /v1/batches status=' + str(status))
        try:
            return receipt['resource_ref']['batch_id']
        except (KeyError, TypeError):
            raise BlockedError('BLOCKED: receipt không có resource_ref.batch_id') from None

    def get_batch(self, batch_id):
        return self.call('GET', '/v1/batches/' + batch_id)


# --- DB chỉ đọc --------------------------------------------------------------------------------------------------

class ReadOnlyDb:
    def __init__(self, launcher):
        self.launcher = launcher
        self.layout = launcher.resolve_layout(os.environ)
        password = launcher.load_or_create_password(self.layout)
        self.dsn = launcher.build_dsn(password, launcher.active_db_name(self.layout))
        identity = launcher.load_or_create_identity(self.layout)
        self.workspace_id = identity['workspace_id']
        self.actor_id = identity['actor_id']

    def query(self, sql, *params):
        assert sql.lstrip().upper().startswith(('SELECT', 'WITH'))
        import psycopg
        with psycopg.connect(self.dsn, autocommit=True, connect_timeout=10,
                             options='-c default_transaction_read_only=on') as conn:
            return conn.execute(sql, (self.workspace_id, *params)).fetchall()

    def db_now(self):
        return self.query('SELECT now() FROM controlplane.cp_workspaces WHERE workspace_id = %s')[0][0]

    def job_for_batch(self, batch_id):
        rows = self.query('SELECT job_id, status, snapshot_ref FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND batch_id = %s ORDER BY created_at LIMIT 1', batch_id)
        return rows[0] if rows else None

    def batch_status(self, batch_id):
        rows = self.query('SELECT status FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s', batch_id)
        return rows[0][0] if rows else None

    def job_status(self, job_id):
        rows = self.query('SELECT status FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s', job_id)
        return rows[0][0] if rows else None

    def failed_stage(self, job_id):
        """Hàng stage FAILED_FINAL hay OUTCOME_UNKNOWN đầu tiên (PW-G2-FIX1: bộ ghi không còn ghi FAILED_RETRYABLE hay STALE khi flow còn thử lại tại chỗ); chỉ đọc."""
        rows = self.query("SELECT stage_name, status, problem->>'code', problem->>'activity', left(coalesce(problem->'field_errors', '{}'::jsonb)::text, 300) FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND job_id = %s AND status IN ('FAILED_FINAL','OUTCOME_UNKNOWN') ORDER BY created_at LIMIT 1", job_id)
        return rows[0] if rows else None

    def render_config_status(self):
        """(scope_kind, scope_key, status) của revision mới nhất mỗi scope render config mà resolve_inputs đòi; chỉ đọc."""
        return self.query("SELECT DISTINCT ON (scope_kind, scope_key) scope_kind, scope_key, status FROM controlplane.cp_config_revisions WHERE workspace_id = %s AND ((scope_kind = 'preset' AND scope_key IN ('bold-yellow', 'output-profile')) OR (scope_kind = 'policy' AND scope_key = 'quality')) ORDER BY scope_kind, scope_key, config_revision_number DESC")

    def seed_counts(self):
        """Số đếm chỉ đọc của dữ liệu seed trong workspace: nguồn, hook, media asset."""
        rows = self.query('SELECT (SELECT count(*) FROM controlplane.cp_sources WHERE workspace_id = %s), (SELECT count(*) FROM controlplane.cp_hooks WHERE workspace_id = %s), (SELECT count(*) FROM controlplane.cp_media_assets WHERE workspace_id = %s)', self.workspace_id, self.workspace_id)
        return {'sources': int(rows[0][0]), 'hooks': int(rows[0][1]), 'media_assets': int(rows[0][2])}

    def job_diagnostics(self, job_id):
        """Mọi hàng cp_stage_runs của job (kể cả hàng gắn workflow_id thay vì job_id) và trạng thái job; chỉ đọc."""
        job_rows = self.query('SELECT status, wait_reason, revision FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s', job_id)
        stage_rows = self.query("SELECT stage_name, attempt, status, wait_reason, problem->>'code', left(coalesce(problem->>'message', ''), 120) FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND (job_id = %s OR stage_run_id LIKE %s) ORDER BY created_at, attempt", job_id, job_id + ':%')
        job = dict(zip(('status', 'wait_reason', 'revision'), job_rows[0])) if job_rows else None
        keys = ('stage', 'attempt', 'status', 'wait_reason', 'code', 'message')
        return {'job': job, 'stages': [dict(zip(keys, row)) for row in stage_rows]}

    def stage_map(self, job_id):
        rows = self.query('SELECT DISTINCT ON (stage_name) stage_name, status, attempt, stage_run_id, recovery_epoch FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND job_id = %s ORDER BY stage_name, attempt DESC', job_id)
        return {r[0]: {'status': r[1], 'attempt': r[2], 'stage_run_id': r[3], 'recovery_epoch': r[4]} for r in rows}

    def ai_invocation_count(self, prefix):
        """Số lời gọi AI của một lô: số dòng cp_ai_invocation_records có record_key bắt đầu bằng prefix (<ws>:<batch_id>:video:). Ledger chi phí luôn 0 vì route_cost_per_request=0 nên không dùng làm số lời gọi."""
        rows = self.query('SELECT count(*) FROM controlplane.cp_ai_invocation_records WHERE workspace_id = %s AND starts_with(record_key, %s)', prefix)
        return int(rows[0][0])

    def locations(self, job_id):
        """Vị trí lưu của artifact thuộc job (owner_ref = job_id) và artifact đầu ra ở sổ hoàn tất của job; chỉ đọc."""
        rows = self.query(
            'SELECT l.location_id::text, l.backend_ref, l.provider_object_ref, l.state, l.observed_hash, l.observed_size_bytes, '
            'l.verification_evidence_ref, l.updated_at, l.artifact_version_id::text, v.sha256_hash, v.size_bytes '
            'FROM controlplane.cp_artifact_locations l JOIN controlplane.cp_artifact_versions v '
            'ON v.workspace_id = l.workspace_id AND v.artifact_version_id = l.artifact_version_id '
            'WHERE l.workspace_id = %s AND (v.owner_ref = %s OR l.artifact_version_id IN '
            '(SELECT output_artifact_version_id FROM controlplane.cp_completion_ledger WHERE workspace_id = %s AND job_id = %s)) '
            'ORDER BY l.created_at', job_id, self.workspace_id, job_id)
        keys = ('location_id', 'backend_ref', 'provider_object_ref', 'state', 'observed_hash', 'observed_size_bytes',
                'verification_evidence_ref', 'updated_at', 'artifact_version_id', 'sha256_hash', 'size_bytes')
        return [dict(zip(keys, r)) for r in rows]

    def ledger_row(self, job_id):
        rows = self.query('SELECT completed_at, output_artifact_version_id::text, output_artifact_hash FROM controlplane.cp_completion_ledger WHERE workspace_id = %s AND job_id = %s', job_id)
        if not rows:
            return None
        return dict(zip(('completed_at', 'output_artifact_version_id', 'output_artifact_hash'), rows[0]))


def is_drive(location):
    return 'drive' in str(location['backend_ref']).lower()


# --- kiểm composition production ---------------------------------------------------------------------------------

_BAD_QUALNAME = re.compile(r'^(Fake|InMemory|Memory)')
_SKIP_TYPES = (str, bytes, int, float, bool, type(None), type)


def _is_violation(obj):
    kind = type(obj)
    if isinstance(obj, (types.FunctionType, types.MethodType, types.BuiltinFunctionType)):
        module, qual = getattr(obj, '__module__', None) or '', kind.__qualname__
    else:
        module, qual = kind.__module__ or '', kind.__qualname__
    return (module, qual), bool(_BAD_QUALNAME.match(qual) or '.fake_' in module or module.startswith('fake_') or module.endswith('.memory'))


def _children(obj):
    import dataclasses
    from collections.abc import Mapping
    if isinstance(obj, Mapping):
        return list(obj.values())
    if isinstance(obj, (list, tuple, set, frozenset)):
        return list(obj)
    found = []
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        found.extend(getattr(obj, f.name, None) for f in dataclasses.fields(obj))
    if hasattr(obj, '__dict__'):
        found.extend(vars(obj).values())
    for klass in type(obj).__mro__:
        for slot in getattr(klass, '__slots__', ()) or ():
            if isinstance(slot, str) and hasattr(obj, slot):
                found.append(getattr(obj, slot))
    return found


def composition_audit(launcher, db):
    """Dựng composition production bằng launcher.load_app (không worker) rồi duyệt đồ thị đối tượng chỉ đọc."""
    history = launcher.read_epoch_history(db.layout)
    epoch = launcher.current_epoch(history, lambda: 0) or '1'
    env = child_env(CONTROLPLANE_DSN=db.dsn, CONTROLPLANE_PORT=str(PORT), CONTROLPLANE_PROFILE='production',
                    CONTROLPLANE_PROFILE_PATH=str(launcher.PROFILE_PATH), CONTROLPLANE_WORKSPACE_ID=db.workspace_id,
                    AIAVC_ACTOR_ID=db.actor_id, AIAVC_DATA_DIR=str(db.layout.data_dir), AIAVC_RECOVERY_EPOCH=epoch,
                    AIAVC_SESSION_REF='ses-' + uuid.uuid4().hex)
    try:
        app = launcher.load_app(env, db.layout)
    except Exception as exc:
        raise BlockedError('BLOCKED: không dựng được composition production: ' + type(exc).__name__) from None
    roots = [getattr(app, 'services', None), getattr(getattr(app, 'api_app', None), 'state', None) and getattr(app.api_app.state, 'production_runtime', None),
             getattr(getattr(app, 'api_app', None), 'state', None) and getattr(app.api_app.state, 'production_services', None)]
    seen, violations, scanned = set(), set(), 0
    stack = [(r, 0) for r in roots if r is not None]
    while stack:
        obj, depth = stack.pop()
        if id(obj) in seen or isinstance(obj, _SKIP_TYPES) or type(obj).__name__ == 'module':
            continue
        seen.add(id(obj))
        scanned += 1
        (module, qual), bad = _is_violation(obj)
        if bad:
            violations.add(module + '.' + qual)
        if depth < 6:
            stack.extend((child, depth + 1) for child in _children(obj))
    return {'objects_scanned': scanned, 'violations': sorted(violations),
            'production_py_sha256': hashlib.sha256(PRODUCTION_PY.read_bytes()).hexdigest()}


# --- chi phí, Drive ----------------------------------------------------------------------------------------------

class CostWatch:
    def __init__(self, db, window_start):
        self._db = db
        self._start = window_start
        self._prefix = None

    def bind_prefix(self, prefix):
        """Từ lúc có lô: lời gọi AI = số dòng cp_ai_invocation_records theo prefix của lô, không phải số bản ghi ledger chi phí (luôn 0 vì route_cost_per_request=0)."""
        self._prefix = prefix

    def _records(self):
        import psycopg
        from datetime import timedelta
        from controlplane.infrastructure.db.config_security.stores import PostgresCostLedger
        end = self._db.db_now() + timedelta(hours=1)
        with psycopg.connect(self._db.dsn, autocommit=True, options='-c default_transaction_read_only=on') as conn:
            return PostgresCostLedger(conn).records(self._db.workspace_id, self._start, end)

    def calls(self):
        return 0 if self._prefix is None else self._db.ai_invocation_count(self._prefix)

    def spent(self):
        total = Decimal(0)
        for record in self._records():
            if record.currency != 'USD':
                raise ValueError('ledger record currency is not USD')
            total += Decimal(str(record.actual_cost if record.actual_cost is not None else record.estimated_cost))
        return total

    def guard(self):
        return c.CostGuard(LEDGER_CEILING_USD, self.spent)

    def check(self):
        self.guard().check()
        if self.calls() > AI_CALL_CAP:
            raise c.CostCeilingExceeded('AI call cap exceeded')


def drive_bytes(db, job_id):
    """Tổng byte Drive của job: artifact có owner_ref = job_id hoặc là đầu ra ở sổ hoàn tất của job."""
    rows = db.query("SELECT coalesce(sum(v.size_bytes), 0) FROM controlplane.cp_artifact_locations l JOIN controlplane.cp_artifact_versions v ON v.workspace_id = l.workspace_id AND v.artifact_version_id = l.artifact_version_id WHERE l.workspace_id = %s AND position('drive' in lower(l.backend_ref)) > 0 AND (v.owner_ref = %s OR l.artifact_version_id IN (SELECT output_artifact_version_id FROM controlplane.cp_completion_ledger WHERE workspace_id = %s AND job_id = %s))", job_id, db.workspace_id, job_id)
    return int(rows[0][0])


def drive_md5_check(db, location):
    """Đối soát Drive: md5Checksum của Drive và tải lại theo luồng (không ghi đĩa) để tính md5, sha256."""
    import urllib.error
    import urllib.request
    from datetime import datetime, timezone
    from controlplane.api.wiring.production_profile import load_production_profile
    from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
    from controlplane.infrastructure.production_ports.drive_token import build_drive_token_broker
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.security.oauth_google_loopback import ACCOUNT_REF, SECRET_REF
    root = db.layout.data_dir
    store = DpapiSecretStore(root / 'vault')
    if store.current_version(SECRET_REF) is None:
        raise BlockedError('BLOCKED: WAITING_USER_OAUTH')
    profile = load_production_profile(PROFILE_JSON)
    broker = build_drive_token_broker(root / 'secrets' / 'oauth-client.json', profile.credential_max_ttl_seconds, store,
                                      lambda: datetime.now(timezone.utc))
    base = 'https://www.googleapis.com/drive/v3/files/' + str(location['provider_object_ref'])
    out = {}
    try:
        with broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF) as token:
            auth = {'Authorization': 'Bearer ' + token}
            with urllib.request.urlopen(urllib.request.Request(base + '?fields=md5Checksum,size', headers=auth), timeout=60) as resp:
                meta = json.loads(resp.read())
            md5, sha, size = hashlib.md5(), hashlib.sha256(), 0
            with urllib.request.urlopen(urllib.request.Request(base + '?alt=media', headers=auth), timeout=600) as resp:
                while True:
                    block = resp.read(1024 * 1024)
                    if not block:
                        break
                    md5.update(block)
                    sha.update(block)
                    size += len(block)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise BlockedError('BLOCKED: WAITING_USER_OAUTH') from None
        raise BatchDriverError('Drive HTTP ' + str(exc.code)) from None
    out['drive_md5'] = meta.get('md5Checksum')
    out['downloaded_md5'] = md5.hexdigest()
    out['md5_match'] = bool(out['drive_md5']) and out['drive_md5'] == out['downloaded_md5']
    out['sha256_match'] = sha.hexdigest() == location['sha256_hash']
    out['size'] = size
    return out


# --- trace, kế hoạch, QC -----------------------------------------------------------------------------------------

def _plan_row(db, prefix):
    rows = db.query('SELECT payload, production_plan_id FROM controlplane.cp_production_plans WHERE workspace_id = %s AND starts_with(record_key, %s) ORDER BY created_at DESC LIMIT 1', prefix)
    return rows[0] if rows else None


def _script_row(db, script_version_id):
    rows = db.query('SELECT payload, revision FROM controlplane.cp_script_versions WHERE workspace_id = %s AND script_version_id = %s', script_version_id)
    return rows[0] if rows else None


def _need(value, name, table):
    if value in (None, '', [], {}):
        raise BlockedError('BLOCKED: thiếu khoá ' + name + ' trong ' + table)
    return value


def job_snapshot_id(db, job_id):
    """Id snapshot sản xuất thật của job. cp_video_jobs.snapshot_ref chỉ là chỗ giữ 'allocation:<slot>' do AllocateJob ghi; id thật ghi ở sổ hoàn tất (snapshot_ref = REF_PRODUCTION_SNAPSHOT), trùng production_snapshot_ref của render package."""
    rows = db.query('SELECT snapshot_ref FROM controlplane.cp_completion_ledger WHERE workspace_id = %s AND job_id = %s', job_id)
    return _need(rows[0][0] if rows else None, 'snapshot_ref', 'cp_completion_ledger')


def build_trace(db, job_id, prefix):
    snapshot_id = job_snapshot_id(db, job_id)
    snap = db.query('SELECT payload FROM controlplane.cp_production_snapshots WHERE workspace_id = %s AND snapshot_id = %s', snapshot_id)
    snap_payload = _need(snap[0][0] if snap else None, 'payload', 'cp_production_snapshots')
    plan = _need(_plan_row(db, prefix), 'plan', 'cp_production_plans')
    script_id = _need(plan[0].get('script_version_id'), 'script_version_id', 'cp_production_plans')
    script = _need(_script_row(db, script_id), 'script', 'cp_script_versions')
    profile = json.loads(PROFILE_JSON.read_text(encoding='utf-8'))
    models = profile['ai']['route_model_refs']['value']
    config_revision = profile['meta']['revision']['value']
    prompts = db.query('SELECT DISTINCT record_key, revision FROM controlplane.cp_content_analyses WHERE workspace_id = %s AND starts_with(record_key, %s)', prefix)
    prompt_refs = [{'id': 'analysis', 'revision': r[1]} for r in prompts]
    cfg = snap_payload.get('configuration_revision_refs') or []
    prompt_refs += [ref for ref in cfg if 'prompt' in json.dumps(ref).lower()]
    return {
        'snapshot_id': snapshot_id,
        'snapshot_payload_sha256': _sha(snap_payload),
        'model_refs': {k: models[k] for k in ('analysis', 'script', 'selection') if k in models},
        'prompt_refs': prompt_refs,
        'config_revision': config_revision,
        'profile_sha256': hashlib.sha256(PROFILE_JSON.read_bytes()).hexdigest(),
        'script_version_id': script_id,
        'script_sha256': _sha(script[0]),
        'input_revisions': {'snapshot_sources': snap_payload.get('source_refs'), 'index': snap_payload.get('index_revision_refs'),
                            'configuration': cfg, 'script_revision': script[1]},
    }


def _plan_media_ids(plan_payload):
    ids = set()
    for scene in (plan_payload.get('timeline') or {}).get('segments', []) or []:
        for visual in scene.get('visuals', []) or []:
            if visual.get('media_asset_id'):
                ids.add(visual['media_asset_id'])
    return ids


def plan_digest(db, job_id, prefix):
    plan = _need(_plan_row(db, prefix), 'plan', 'cp_production_plans')
    payload = plan[0]
    script = _need(_script_row(db, payload.get('script_version_id')), 'script', 'cp_script_versions')
    media = sorted(_plan_media_ids(payload))
    fingerprints = []
    for media_id in media:
        rows = db.query('SELECT fingerprint FROM controlplane.cp_media_assets WHERE workspace_id = %s AND media_asset_id = %s', media_id)
        fingerprints.append(_need(rows[0][0] if rows else None, 'fingerprint', 'cp_media_assets'))
    parts = {'script_sha256': _sha(script[0]), 'story_angle_id': payload.get('selection_fingerprint'),
             'media_sha256s': sorted(fingerprints), 'hook_ref': payload.get('hook_placement')}
    return {'digest': _sha(parts), **parts, 'production_plan_id': plan[1], 'media_asset_ids': media}


def render_matches_plan(db, job_id, plan):
    snapshot_id = job_snapshot_id(db, job_id)
    rows = db.query("SELECT payload FROM controlplane.cp_render_packages WHERE workspace_id = %s AND payload->>'production_snapshot_ref' = %s ORDER BY created_at DESC LIMIT 1", snapshot_id)
    if not rows:
        return False
    package = rows[0][0]
    script = _script_row(db, package.get('script_version_ref'))
    if script is None or _sha(script[0]) != plan['script_sha256']:
        return False
    if package.get('production_plan_ref') != plan['production_plan_id']:
        return False
    used = _plan_media_ids({'timeline': package.get('timeline') or {}})
    return used <= set(plan['media_asset_ids'])


_GATE_RESULT_SQL = "SELECT g.payload FROM controlplane.cp_quality_gate_results g JOIN controlplane.cp_render_attempts a ON a.workspace_id = g.workspace_id AND a.record_key = g.record_key WHERE g.workspace_id = %s AND a.payload->>'package_fingerprint' = %s ORDER BY g.created_at DESC, g.revision DESC LIMIT 1"


def summarize_gates(payload):
    """Đếm cổng cứng của một kết quả QC; failed_gates giữ nguyên từng mục cổng cứng không passed."""
    from render.domain.quality_report import GATE_KINDS, GateKind
    kinds = {name.value: kind for name, kind in GATE_KINDS.items()}
    total = passed = na = 0
    failed = []
    for gate in (payload or {}).get('gates', []):
        kind = kinds.get(gate['gate'])
        if kind is GateKind.WARNING or kind is None:
            continue
        if gate['status'] == 'not_applicable' and kind is GateKind.HARD_CONDITIONAL:
            na += 1
            continue
        total += 1
        if gate['status'] == 'passed':
            passed += 1
        else:
            failed.append(gate)
    return {'hard_total': total, 'hard_passed': passed, 'hard_failed': total - passed, 'not_applicable': na, 'failed_gates': failed}


def qc_gates(db, job_id):
    snapshot_id = job_snapshot_id(db, job_id)
    pkg = db.query("SELECT package_fingerprint FROM controlplane.cp_render_packages WHERE workspace_id = %s AND payload->>'production_snapshot_ref' = %s ORDER BY created_at DESC LIMIT 1", snapshot_id)
    if not pkg:
        raise BlockedError('BLOCKED: không có render package cho job')
    rows = db.query(_GATE_RESULT_SQL, pkg[0][0])
    if not rows:
        raise BlockedError('BLOCKED: không có kết quả QC')
    summary = summarize_gates(rows[0][0])
    summary['failed_ids'] = [gate['gate'] for gate in summary.pop('failed_gates')]
    return summary


def format_qc_evidence(gate_payload, package_payload):
    """Một dòng: cổng cứng không passed (blocking_gates) và thời lượng mp4 đo được (measured_value của DURATION_RANGE) so với thời lượng giọng trong timeline của render package."""
    summary = summarize_gates(gate_payload)
    blocking = ' '.join(g['gate'] + '=' + str(g['status']) + ('/' + str(g['reason']) if g.get('reason') else '') for g in summary['failed_gates']) or 'none'
    mp4 = next((g.get('measured_value') for g in (gate_payload or {}).get('gates', []) if g.get('gate') == 'DURATION_RANGE'), None)
    timeline = (package_payload or {}).get('timeline') or {}
    voice = next((timeline[key] for key in ('voice_duration_ms', 'duration_ms') if type(timeline.get(key)) is int), None)
    delta = mp4 - voice if type(mp4) is int and type(voice) is int else None
    return f'blocking_gates=[{blocking}] duration=[mp4_ms={mp4} voice_ms={voice} delta_ms={delta}]'


def collect_qc_evidence(db, prefix):
    """Chỉ đọc; dùng được cả khi job FAILED_FINAL (chưa có sổ hoàn tất): tìm render package theo production_plan_ref của kế hoạch thuộc lô."""
    try:
        plan = _plan_row(db, prefix)
        if plan is None:
            return 'qc_evidence=[no_plan]'
        pkg = db.query("SELECT package_fingerprint, payload FROM controlplane.cp_render_packages WHERE workspace_id = %s AND payload->>'production_plan_ref' = %s ORDER BY created_at DESC LIMIT 1", plan[1])
        if not pkg:
            return 'qc_evidence=[no_render_package]'
        rows = db.query(_GATE_RESULT_SQL, pkg[0][0])
        if not rows:
            return 'qc_evidence=[no_qc_result]'
        return c.redact(format_qc_evidence(rows[0][0], pkg[0][1]))[:600]
    except Exception as exc:
        return 'qc_evidence_error=' + type(exc).__name__


# --- chạy lô -----------------------------------------------------------------------------------------------------

@dataclass
class RunResult:
    batch_id: str = ''
    job_id: str = ''
    timeline: list = field(default_factory=list)
    before_stop: dict = field(default_factory=dict)
    after_start: dict = field(default_factory=dict)
    ready_seconds: float | None = None
    render_seen_running: bool = False
    final_stages: dict = field(default_factory=dict)
    final_job_status: str = ''
    final_batch_status: str = ''
    locations: list = field(default_factory=list)
    ledger_row: dict | None = None
    drive_check: dict | None = None
    composition: dict = field(default_factory=dict)
    plan_before: dict | None = None
    plan_after: dict | None = None
    render_matches: bool = False
    trace: dict = field(default_factory=dict)
    qc: dict = field(default_factory=dict)
    ai_calls: int = 0
    spent_usd: Decimal = Decimal(0)
    drive_bytes: int = 0
    elapsed_seconds: float = 0.0
    stop_attempts: int = 0
    verified_before_complete: bool = False
    cleanup_before_verified: bool = False
    attempts: list = field(default_factory=list)
    launcher_seed_line: str = ''
    seed_counts: dict = field(default_factory=dict)
    render_config: str = ''
    pre_stop_attempts: int = 0
    other_workflows_running: int = -1
    record_prefix: str = ''
    qc_evidence: str = ''
    batch_after_run: str = ''


def _drive_verified(locations):
    return [loc for loc in locations if is_drive(loc) and loc['state'] == 'VERIFIED']


def run_batch(work_dir, deadline):
    t0 = time.monotonic()
    result = RunResult()
    launcher = load_launcher()
    db = ReadOnlyDb(launcher)
    window_start = db.db_now()
    watch = CostWatch(db, window_start)
    watch.check()
    try:
        # Đưa về trạng thái đã biết: stop idempotent, không đụng container hay dữ liệu; worker cũ còn sống thì start in 'Worker đang chạy' và không cấp URL /launch.
        result.pre_stop_attempts = stop_until_exited()
        result.other_workflows_running = require_no_other_workflows()
        launch_path, _, launcher_out = start_capturing(work_dir, 'first')
        result.composition = composition_audit(launcher, db)
        result.launcher_seed_line = launcher_seed_line(launcher_out)
        result.seed_counts = db.seed_counts()
        result.render_config = require_render_config(db)
        session = ApiSession(db.layout.cert_file)
        session.open(launch_path)
        batch_id = result.batch_id = session.post_batch(1)
        result.record_prefix = video_key_prefix(db.workspace_id, batch_id)
        watch.bind_prefix(result.record_prefix)
        job = None
        wait_end = time.monotonic() + ELIGIBLE_WAIT_SECONDS
        while job is None:
            watch.check()
            job = db.job_for_batch(batch_id)
            if job is None:
                if time.monotonic() > wait_end:
                    raise BlockedError('BLOCKED: NO_ELIGIBLE_CANDIDATE: AllocateJob chưa cấp job cho lô; cần tin đủ hook và ảnh seed từ CP7-4..CP7-7, không tạo dữ liệu giả')
                time.sleep(deadline.timeout(POLL_SECONDS))
        job_id = result.job_id = job[0]
        seen_pairs, resumed = set(), False
        while True:
            watch.check()
            stages = db.stage_map(job_id)
            status = db.job_status(job_id)
            for name, row in stages.items():
                pair = (name, row['status'])
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    result.timeline.append((round(time.monotonic() - t0, 1), name, row['status']))
            if result.plan_before is None and stages.get('plan', {}).get('status') == 'SUCCEEDED':
                result.plan_before = plan_digest(db, job_id, result.record_prefix)
            locations = db.locations(job_id)
            ledger = db.ledger_row(job_id)
            verified = _drive_verified(locations)
            complete_done = stages.get('complete', {}).get('status') == 'SUCCEEDED'
            if verified and not result.verified_before_complete and not complete_done and ledger is None:
                result.verified_before_complete = True
            verified_versions = {loc['artifact_version_id'] for loc in verified}
            for loc in locations:
                if not is_drive(loc) and loc['state'] in CLEANUP_STATES and loc['artifact_version_id'] not in verified_versions:
                    result.cleanup_before_verified = True
            if not resumed and stages.get('render', {}).get('status') == 'RUNNING':
                result.render_seen_running = resumed = True
                result.before_stop = stages
                result.stop_attempts = stop_until_exited()
                launch2, t_start, _ = start_capturing(work_dir, 'second')
                session = ApiSession(db.layout.cert_file)
                session.open(launch2)
                while True:
                    code, _ = session.get_batch(batch_id)
                    if code == 200:
                        break
                    time.sleep(deadline.timeout(1))
                result.ready_seconds = time.monotonic() - t_start
                result.after_start = db.stage_map(job_id)
                continue
            if status in TERMINAL_JOB:
                break
            time.sleep(deadline.timeout(POLL_SECONDS))
        result.final_stages = db.stage_map(job_id)
        result.final_job_status = db.job_status(job_id)
        if result.final_job_status != 'COMPLETED':
            failed = db.failed_stage(job_id)
            result.attempts.append({'attempt': 1, 'batch_id': batch_id, 'job_id': job_id, 'outcome': str(result.final_job_status), 'failed_stage': None if failed is None else failed[0], 'activity': None if failed is None else failed[3], 'code': None if failed is None else failed[2]})
            result.ai_calls = watch.calls()
            result.qc_evidence = collect_qc_evidence(db, result.record_prefix)
            result.batch_after_run = collect_batch_running(db, batch_id)
            diag = collect_diagnostic(db, job_id)
            raise BlockedError('BLOCKED: job kết thúc ở ' + str(result.final_job_status) + ' ' + format_failed_stage(failed) + '; không thử lại, không tạo lô khác; other_workflows_running=' + str(result.other_workflows_running) + ' ai_calls=' + str(result.ai_calls) + ' ' + result.qc_evidence + ' ' + result.batch_after_run + ' ' + collect_render_config(db) + ' launcher_seed=[' + result.launcher_seed_line + '] seed_counts=' + json.dumps(result.seed_counts, sort_keys=True) + ' ' + collect_script_length(db, result.record_prefix) + ' ' + diag)
        result.attempts.append({'attempt': 1, 'batch_id': batch_id, 'job_id': job_id, 'outcome': 'COMPLETED'})
        result.final_batch_status = db.batch_status(batch_id) or ''
        result.locations = db.locations(job_id)
        result.ledger_row = db.ledger_row(job_id)
        verified = _drive_verified(result.locations)
        result.drive_check = drive_md5_check(db, verified[0]) if verified else None
        result.plan_after = plan_digest(db, job_id, result.record_prefix)
        result.render_matches = render_matches_plan(db, job_id, result.plan_after)
        result.trace = build_trace(db, job_id, result.record_prefix)
        result.qc = qc_gates(db, job_id)
        result.qc_evidence = collect_qc_evidence(db, result.record_prefix)
        result.batch_after_run = collect_batch_running(db, batch_id)
        result.ai_calls = watch.calls()
        result.spent_usd = watch.spent()
        result.drive_bytes = drive_bytes(db, job_id)
        result.elapsed_seconds = time.monotonic() - t0
        return result
    finally:
        try:
            stop_until_exited()
        except Exception:
            pass


def main(argv):
    if len(argv) != 2 or argv[0] != '--out':
        print('usage: cp7_batch_driver.py --out <dir>')
        return 2
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    try:
        result = run_batch(out, c.Deadline(RUN_DEADLINE_SECONDS))
    except BlockedError as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': c.redact(str(exc))[:4000]}))
        return 1
    data = {k: getattr(result, k) for k in result.__dataclass_fields__}
    (out / 'trace.json').write_text(c.redact(json.dumps(data, default=str, ensure_ascii=False)), encoding='utf-8')
    stages_ok = all(result.final_stages.get(s, {}).get('status') == 'SUCCEEDED' for s in STAGES)
    print(json.dumps({'status': 'DONE', 'stages_succeeded': stages_ok, 'job_status': result.final_job_status}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

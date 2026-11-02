"""CP7-11 / RG-10: giám sát đêm chạy 100 video trên ngăn xếp thật.

Trần: ledger AI cả đêm +25 USD, tháng <= 50 USD (cảnh báo ở 40 USD), Drive <= 12 GiB, working set <= 20 GiB, hạn 12 giờ 15 phút.
Cách dừng: `python tools/launcher/launcher.py stop` (dừng worker, việc làm tiếp khi bật lại, không mất dữ liệu).
DB chỉ đọc qua `d.ReadOnlyDb`; ghi duy nhất là đăng ký nguồn 404 qua `seed_collection_sources`.
Không in capability, cookie, token hay file ID.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import cp7_batch_driver as d
import cp7_common as c

GIB = 1024 ** 3
TARGET_VIDEOS = 100
VIDEOS_PER_NEWS = 2
WITHIN_SECONDS = 12 * 3600
DEADLINE_SECONDS = 12 * 3600 + 15 * 60
SAMPLE_SECONDS = 300
POLL_SECONDS = 30
RESUME_AT_VALID = 40
RESUME_AT_SECONDS = 6 * 3600
RESUME_LIMIT_SECONDS = d.READY_LIMIT_SECONDS
NIGHT_COST_CAP_USD = Decimal('25')
MONTH_COST_CAP_USD = Decimal('50')
WARN_COST_USD = Decimal('40')
DRIVE_NEED_BYTES = 12 * GIB
WORKING_SET_CAP_BYTES = 20 * GIB
AUTO_RATIO_PERCENT = 95
SUCCESS_RUN_STATUSES = ('COMPLETED', 'COMPLETED_PARTIAL')
FAILED_RUN_STATUSES = ('FAILED_FINAL',)
JOB_STATUSES = ('CREATED', 'SNAPSHOTTED', 'ACTIVE', 'WAITING', 'READY_FOR_COMPLETION', 'COMPLETED', 'FAILED_FINAL')
TERMINAL_BATCH = ('COMPLETED_TARGET', 'COMPLETED_EXHAUSTED', 'FAILED_SYSTEM')
LOCAL_UTC_OFFSET_HOURS = 7
NOT_FOUND_CODE = 'cp7-not-found-rg10'
NOT_FOUND_URL = 'https://feeds.bbci.co.uk/news/cp7-not-found-rg10.xml'


def drive_quota_requirement(limit, usage, reserve_ratio=0.2, need_bytes=DRIVE_NEED_BYTES):
    """Kiểm Drive trống đủ 12 GiB cộng 20% dự trữ theo luật `_check_quota` của DriveObjectStore để không dừng giữa đêm (OI-CP7-06)."""
    if limit is not None and not (isinstance(limit, int) and not isinstance(limit, bool) and limit > 0):
        raise ValueError('invalid quota')
    if not (isinstance(usage, int) and not isinstance(usage, bool) and usage >= 0):
        raise ValueError('invalid quota')
    if limit is None:
        return {'ok': True, 'unlimited': True, 'free_bytes': None, 'required_bytes': need_bytes}
    required = need_bytes + math.ceil(reserve_ratio * limit)
    free = limit - usage
    return {'ok': free >= required, 'unlimited': False, 'free_bytes': free, 'required_bytes': required}


def parse_storage_quota(about):
    """Đọc storageQuota từ phản hồi Drive about."""
    if not isinstance(about, dict) or not isinstance(about.get('storageQuota'), dict):
        raise ValueError('storageQuota is malformed')
    quota = about['storageQuota']
    try:
        limit = int(quota['limit']) if 'limit' in quota else None
        usage = int(quota.get('usage', 0))
    except (TypeError, ValueError):
        raise ValueError('storageQuota is malformed') from None
    return limit, usage


def percentile(values, q):
    """Phân vị theo hạng gần nhất."""
    if not (0 < q <= 100):
        raise ValueError('q must be in (0, 100]')
    if not values:
        return None
    vals = sorted(values)
    k = math.ceil(len(vals) * q / 100)
    return vals[k - 1]


def stage_metrics(rows):
    """Số liệu thời gian theo stage."""
    grouped = {}
    for stage, status, attempt, seconds in rows:
        entry = grouped.setdefault(stage, {'secs': [], 'extra': 0})
        if status == 'SUCCEEDED' and seconds is not None:
            entry['secs'].append(seconds)
        if attempt > 1:
            entry['extra'] += 1
    out = {}
    for stage, entry in grouped.items():
        secs = entry['secs']
        out[stage] = {
            'n': len(secs),
            'p50_s': round(percentile(secs, 50), 1) if secs else None,
            'p95_s': round(percentile(secs, 95), 1) if secs else None,
            'max_s': round(max(secs), 1) if secs else None,
            'extra_attempts': entry['extra'],
        }
    return out


def parse_vram_mib(text):
    """Đọc VRAM đang dùng (MiB) từ đầu ra nvidia-smi."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError('no vram lines')
    return max(int(line.strip()) for line in lines)


def should_resume(valid_synced, elapsed_s, resumed, busy):
    """Quyết định thời điểm dừng rồi chạy lại giữa lô."""
    if resumed:
        return False
    if elapsed_s >= RESUME_AT_SECONDS:
        return True
    return valid_synced >= RESUME_AT_VALID and bool(busy)


def month_window_start(now):
    """Đầu tháng theo giờ Việt Nam, trả về UTC."""
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    local_tz = timezone(timedelta(hours=LOCAL_UTC_OFFSET_HOURS))
    local = now.astimezone(local_tz)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def cost_violations(night_usd, month_usd, drive_bytes, elapsed_s):
    """Liệt kê các trần chi phí, Drive, thời gian bị vượt."""
    out = []
    if Decimal(str(night_usd)) > NIGHT_COST_CAP_USD:
        out.append('night_usd')
    if Decimal(str(month_usd)) > MONTH_COST_CAP_USD:
        out.append('month_usd')
    if drive_bytes > DRIVE_NEED_BYTES:
        out.append('drive_bytes')
    if elapsed_s > DEADLINE_SECONDS:
        out.append('elapsed')
    return out


def auto_ratio_ok(valid, total):
    """Tỉ lệ video hợp lệ trên tổng job đạt ít nhất 95%."""
    return total > 0 and valid * 100 >= total * AUTO_RATIO_PERCENT


def audit_jobs(jobs, stage_counts, problem_missing, seen_ids):
    """Tìm job biến mất hoặc thiếu trạng thái, log."""
    out = []
    present = set()
    for job_id, status in jobs:
        present.add(job_id)
        if status not in JOB_STATUSES:
            out.append('unknown_status:' + job_id)
        elif status != 'CREATED' and stage_counts.get(job_id, 0) == 0:
            out.append('no_stage_rows:' + job_id)
    out.extend('failed_without_problem:' + job_id for job_id in problem_missing)
    out.extend('vanished:' + job_id for job_id in seen_ids if job_id not in present)
    return sorted(out)


def collection_isolation(runs, source_id):
    """Chứng minh lỗi một nguồn không dừng nguồn khác."""
    target = [status for src, status in runs if src == source_id]
    target_failed = sum(1 for status in target if status in FAILED_RUN_STATUSES)
    others_ok = sum(1 for src, status in runs if src != source_id and status in SUCCESS_RUN_STATUSES)
    return {'target_runs': len(target), 'target_failed': target_failed, 'others_ok': others_ok,
            'isolated': target_failed >= 1 and others_ok >= 1}


def manual_actions(calls, batch_id):
    """Liệt kê lời gọi API ngoài phạm vi cho phép."""
    allowed = {('GET', '/v1/batch-settings'), ('GET', '/v1/batches/' + batch_id)}
    post_seen = False
    out = []
    for method, path in calls:
        if (method, path) in allowed:
            continue
        if (method, path) == ('POST', '/v1/batches') and not post_seen:
            post_seen = True
            continue
        out.append(f'{method} {path}')
    return out


def format_sample(sample):
    """Định dạng một mẫu giám sát thành dòng ASCII."""
    t_utc = sample.get('t_utc')
    if 'sample_error' in sample:
        return f"- sample t={t_utc} sample_error={sample['sample_error']}".encode('ascii', 'backslashreplace').decode('ascii')

    def val(key):
        value = sample.get(key)
        return '-' if value is None else value

    def gib(key, fmt):
        value = sample.get(key)
        return '-' if value is None else format(value / GIB, fmt)

    elapsed = sample.get('elapsed_s')
    jobs = sample.get('jobs')
    line = (f"- sample t={val('t_utc')} elapsed_s={'-' if elapsed is None else int(elapsed)} batch={val('batch_status')} "
            f"jobs={'-' if jobs is None else json.dumps(jobs, sort_keys=True, separators=(',', ':'))} valid={val('valid_synced')} "
            f"running_stages={val('running_stages')} night_usd={val('night_usd')} month_usd={val('month_usd')} ai_calls={val('ai_calls')} "
            f"data_free_gib={gib('disk_free_data_bytes', '.1f')} sys_free_gib={gib('disk_free_system_bytes', '.1f')} "
            f"working_set_gib={gib('working_set_bytes', '.2f')} vram_mib={val('vram_used_mib')}")
    return line.encode('ascii', 'backslashreplace').decode('ascii')


def dir_size_bytes(path):
    """Tổng dung lượng tệp thường trong thư mục."""
    total = 0
    stack = [str(path)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


class WaitClock:
    """Đồng hồ cộng dồn thời gian chờ nhà cung cấp."""

    def __init__(self):
        self._prev = None
        self._total = 0.0

    def observe(self, now, waiting):
        if self._prev is not None and now < self._prev[0]:
            raise ValueError('time went backwards')
        if self._prev is not None and self._prev[1] > 0:
            self._total += now - self._prev[0]
        self._prev = (now, waiting)

    @property
    def seconds(self):
        return float(self._total)


class OvernightDb(d.ReadOnlyDb):
    """Truy vấn chỉ đọc cho lô đêm."""

    _JOBS = 'FROM controlplane.cp_video_jobs v WHERE v.workspace_id = %s AND v.batch_id = %s'
    _STAGES = ('FROM controlplane.cp_stage_runs s JOIN controlplane.cp_video_jobs v '
               'ON v.workspace_id = s.workspace_id AND v.job_id = s.job_id WHERE v.workspace_id = %s AND v.batch_id = %s')

    def batch_job_counts(self, batch_id):
        rows = self.query('SELECT v.status, count(*) ' + self._JOBS + ' GROUP BY v.status', batch_id)
        return {r[0]: int(r[1]) for r in rows}

    def batch_jobs(self, batch_id):
        rows = self.query('SELECT v.job_id, v.status ' + self._JOBS + ' ORDER BY v.created_at, v.job_id', batch_id)
        return [(r[0], r[1]) for r in rows]

    def valid_synced_count(self, batch_id):
        from controlplane.application.storage_meta.handlers import CLOUD_BACKEND
        rows = self.query(
            'SELECT count(DISTINCT cl.job_id) FROM controlplane.cp_completion_ledger cl '
            'JOIN controlplane.cp_video_jobs v ON v.workspace_id = cl.workspace_id AND v.job_id = cl.job_id '
            'JOIN controlplane.cp_artifact_locations l ON l.workspace_id = cl.workspace_id AND l.location_id::text = cl.cloud_location_ref '
            "WHERE cl.workspace_id = %s AND v.batch_id = %s AND l.state = 'VERIFIED' AND l.backend_ref = '" + CLOUD_BACKEND + "' "
            "AND starts_with(l.verification_evidence_ref, 'drive:') "
            'AND l.verification_evidence_ref = cl.cloud_location_verification_ref', batch_id)
        return int(rows[0][0])

    def running_busy(self, batch_id):
        rows = self.query(
            'SELECT count(*) ' + self._JOBS + " AND EXISTS (SELECT 1 FROM controlplane.cp_stage_runs s WHERE s.workspace_id = v.workspace_id "
            "AND s.job_id = v.job_id AND s.status = 'RUNNING') AND (SELECT count(*) FROM controlplane.cp_stage_runs s2 "
            "WHERE s2.workspace_id = v.workspace_id AND s2.job_id = v.job_id AND s2.status = 'SUCCEEDED') >= 3", batch_id)
        return int(rows[0][0]) > 0

    def running_stage_count(self, batch_id):
        rows = self.query("SELECT count(*) " + self._STAGES + " AND s.status = 'RUNNING'", batch_id)
        return int(rows[0][0])

    def wait_provider_jobs(self, batch_id):
        rows = self.query(
            "SELECT count(*) FROM (SELECT v.job_id " + self._JOBS + " AND v.status = 'WAITING' UNION "
            "SELECT s.job_id " + self._STAGES + " AND s.status IN ('WAITING_DEPENDENCY', 'WAITING_CAPABILITY') "
            "AND (starts_with(lower(coalesce(s.wait_reason, '')), 'provider') OR starts_with(lower(coalesce(s.wait_reason, '')), 'quota') "
            "OR starts_with(lower(coalesce(s.wait_reason, '')), 'budget'))) t", batch_id, self.workspace_id, batch_id)
        return int(rows[0][0])

    def completed_job_ids(self, batch_id):
        rows = self.query('SELECT cl.job_id FROM controlplane.cp_completion_ledger cl JOIN controlplane.cp_video_jobs v '
                          'ON v.workspace_id = cl.workspace_id AND v.job_id = cl.job_id WHERE cl.workspace_id = %s AND v.batch_id = %s', batch_id)
        return sorted(r[0] for r in rows)

    def stage_row_counts(self, batch_id):
        rows = self.query('SELECT s.job_id, count(*) ' + self._STAGES + ' GROUP BY s.job_id', batch_id)
        return {r[0]: int(r[1]) for r in rows}

    def problem_missing(self, batch_id):
        rows = self.query("SELECT DISTINCT s.job_id " + self._STAGES + " AND s.status IN ('FAILED_FINAL', 'OUTCOME_UNKNOWN') "
                          "AND (s.problem IS NULL OR s.problem->>'code' IS NULL)", batch_id)
        return {r[0] for r in rows}

    def stage_durations(self, batch_id):
        rows = self.query(
            'SELECT s.stage_name, s.status, s.attempt, EXTRACT(EPOCH FROM (COALESCE(s.finished_at, s.updated_at) - COALESCE(s.started_at, s.created_at))) '
            + self._STAGES, batch_id)
        return [(r[0], r[1], r[2], None if r[3] is None else float(r[3])) for r in rows]

    def job_lead_seconds(self, batch_id):
        rows = self.query('SELECT EXTRACT(EPOCH FROM (cl.completed_at - v.created_at)) FROM controlplane.cp_completion_ledger cl '
                          'JOIN controlplane.cp_video_jobs v ON v.workspace_id = cl.workspace_id AND v.job_id = cl.job_id '
                          'WHERE cl.workspace_id = %s AND v.batch_id = %s', batch_id)
        return [float(r[0]) for r in rows]

    def batch_drive_bytes(self, batch_id):
        from controlplane.application.storage_meta.handlers import CLOUD_BACKEND
        rows = self.query(
            'SELECT coalesce(sum(av.size_bytes), 0) FROM controlplane.cp_artifact_locations l JOIN controlplane.cp_artifact_versions av '
            'ON av.workspace_id = l.workspace_id AND av.artifact_version_id = l.artifact_version_id '
            "WHERE l.workspace_id = %s AND l.backend_ref = '" + CLOUD_BACKEND + "' AND EXISTS (SELECT 1 FROM controlplane.cp_video_jobs v "
            'WHERE v.workspace_id = l.workspace_id AND v.batch_id = %s AND (av.owner_ref = v.job_id OR av.artifact_version_id IN '
            '(SELECT cl.output_artifact_version_id FROM controlplane.cp_completion_ledger cl '
            'WHERE cl.workspace_id = v.workspace_id AND cl.job_id = v.job_id)))', batch_id)
        return int(rows[0][0])

    def collection_runs(self, since):
        rows = self.query('SELECT r.source_id, r.status FROM controlplane.cp_collection_runs r WHERE r.workspace_id = %s AND r.created_at >= %s', since)
        return [(r[0], r[1]) for r in rows]

    def source_id_for(self, locator):
        rows = self.query('SELECT s.source_id FROM controlplane.cp_sources s WHERE s.workspace_id = %s AND s.canonical_locator = %s LIMIT 1', locator)
        return rows[0][0] if rows else None


class OvernightSession(d.ApiSession):
    """Phiên Control API có ghi lại lời gọi."""

    def __init__(self, cert_file, calls=None):
        super().__init__(cert_file)
        self.calls = calls if calls is not None else []

    def call(self, method, path, payload=None):
        self.calls.append((method, path.split('?')[0]))
        return super().call(method, path, payload)

    def get_batch_settings(self):
        status, body = self.call('GET', '/v1/batch-settings')
        if status != 200:
            raise d.BatchDriverError('GET /v1/batch-settings status=' + str(status))
        return body['max_concurrent_videos']

    def post_overnight_batch(self, target, max_concurrent):
        status, receipt = self.call('POST', '/v1/batches', {'target_completed_videos': target, 'max_concurrent_videos': max_concurrent})
        if status != 202:
            raise d.BatchDriverError('POST /v1/batches status=' + str(status))
        try:
            return receipt['resource_ref']['batch_id']
        except (KeyError, TypeError):
            raise d.BlockedError('BLOCKED: receipt không có resource_ref.batch_id') from None


def read_storage_quota(db):
    """Đọc storageQuota của Drive qua broker DPAPI (không in token)."""
    from controlplane.api.wiring.production_profile import load_production_profile
    from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
    from controlplane.infrastructure.production_ports.drive_token import build_drive_token_broker
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.security.oauth_google_loopback import ACCOUNT_REF, SECRET_REF
    root = db.layout.data_dir
    store = DpapiSecretStore(root / 'vault')
    if store.current_version(SECRET_REF) is None:
        raise d.BlockedError('BLOCKED: WAITING_USER_OAUTH')
    profile = load_production_profile(d.PROFILE_JSON)
    broker = build_drive_token_broker(root / 'secrets' / 'oauth-client.json', profile.credential_max_ttl_seconds, store,
                                      lambda: datetime.now(timezone.utc))
    try:
        with broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF) as token:
            request = urllib.request.Request('https://www.googleapis.com/drive/v3/about?fields=storageQuota',
                                             headers={'Authorization': 'Bearer ' + token})
            with urllib.request.urlopen(request, timeout=60) as resp:
                about = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise d.BlockedError('BLOCKED: WAITING_USER_OAUTH') from None
        raise d.BatchDriverError('Drive HTTP ' + str(exc.code)) from None
    try:
        return parse_storage_quota(about)
    except ValueError:
        raise d.BlockedError('BLOCKED: storageQuota của Drive không đọc được') from None


def require_drive_quota(db):
    """Chặn khi Drive trống không đủ 12 GiB cộng 20% dự trữ (OI-CP7-06)."""
    limit, usage = read_storage_quota(db)
    ratio = float(json.loads(d.PROFILE_JSON.read_text(encoding='utf-8'))['drive']['quota_reserve_ratio']['value'])
    info = drive_quota_requirement(limit, usage, ratio)
    if not info['ok']:
        raise d.BlockedError('BLOCKED: OI-CP7-06 Drive trống ' + format(info['free_bytes'] / GIB, '.2f') + ' GiB < cần '
                             + format(info['required_bytes'] / GIB, '.2f') + ' GiB (12 GiB + 20% dự trữ); không bắt đầu lô')
    return info


def probe_not_found(url, opener=None):
    """Gọi URL nguồn 404 và trả mã trạng thái thật."""
    opener = opener or urllib.request.urlopen
    try:
        resp = opener(urllib.request.Request(url, headers={'User-Agent': 'cp7-11-rg10'}), timeout=30)
    except urllib.error.HTTPError as exc:
        return exc.code
    except OSError as exc:
        raise d.BlockedError('BLOCKED: không gọi được URL 404: ' + type(exc).__name__) from None
    status = getattr(resp, 'status', None)
    close = getattr(resp, 'close', None)
    if close is not None:
        close()
    return status


def require_not_found_url(url=NOT_FOUND_URL, opener=None):
    """Chặn khi URL nguồn 404 không trả 404 thật."""
    code = probe_not_found(url, opener)
    if code != 404:
        raise d.BlockedError(f'BLOCKED: URL nguồn 404 không trả 404 thật (status={code})')
    return code


def register_not_found_source(launcher, db, work_dir):
    """Đăng ký nguồn 404 qua seed_collection_sources (ghi DB duy nhất của monitor, qua dịch vụ ứng dụng của phân hệ A)."""
    from controlplane.api.wiring.collection import seed_collection_sources
    from controlplane.api.wiring.production_profile import load_production_profile
    from controlplane.infrastructure.db.uow import TransactionManager
    from source_ingestion.domain.locator import canonicalize_locator
    sources_path = Path(work_dir) / 'cp7_not_found_source.json'
    doc = {'schema_version': 1, 'sources': [{'code': NOT_FOUND_CODE, 'url': NOT_FOUND_URL, 'source_kind': 'rss_feed',
                                             'tier': 'tier_1', 'enabled': True}]}
    sources_path.write_text(json.dumps(doc, ensure_ascii=True), encoding='utf-8')
    profile = load_production_profile(d.PROFILE_JSON)
    epoch = launcher.current_epoch(launcher.read_epoch_history(db.layout), lambda: 0) or '1'
    manager = TransactionManager(db.dsn, pool_max_size=2)
    try:
        report = seed_collection_sources(manager, workspace_id=db.workspace_id, profile=profile, sources_path=sources_path,
                                         recovery_epoch=epoch)
    finally:
        manager.close()
    if report.tombstoned >= 1:
        raise d.BlockedError('BLOCKED: nguồn 404 đã bị xoá (tombstone), không đăng ký lại')
    source_id = db.source_id_for(canonicalize_locator(NOT_FOUND_URL))
    if source_id is None:
        raise d.BlockedError('BLOCKED: không thấy nguồn 404 sau khi đăng ký')
    return {'source_id': source_id, 'registered': report.registered, 'existing': report.existing, 'replayed': report.replayed}


def read_vram_mib():
    """Đọc VRAM đang dùng (MiB) bằng nvidia-smi."""
    proc = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], capture_output=True,
                          text=True, timeout=10, check=False)
    if proc.returncode != 0:
        raise RuntimeError('nvidia-smi exit ' + str(proc.returncode))
    return parse_vram_mib(proc.stdout)


class OvernightSampler:
    """Lấy mẫu giám sát mỗi 5 phút: sổ đếm job, ledger, ổ đĩa, working set, VRAM."""

    def __init__(self, db, batch_id, record_prefix, window_start, layout, sink_path, cost_reader=None, vram_reader=None,
                 interval=SAMPLE_SECONDS):
        self._db = db
        self._batch_id = batch_id
        self._record_prefix = record_prefix
        self._window_start = window_start
        self._layout = layout
        self._sink_path = Path(sink_path)
        self._cost_reader = cost_reader or (lambda start: d.CostWatch(db, start).spent())
        self._vram_reader = vram_reader or read_vram_mib
        self._interval = interval
        self.samples = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._t0 = time.monotonic()

    def collect_sample(self):
        t_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        elapsed = time.monotonic() - self._t0
        try:
            db, batch_id = self._db, self._batch_id
            sample = {
                't_utc': t_utc,
                'elapsed_s': elapsed,
                'batch_status': db.batch_status(batch_id) or '',
                'jobs': db.batch_job_counts(batch_id),
                'valid_synced': db.valid_synced_count(batch_id),
                'running_stages': db.running_stage_count(batch_id),
                'ai_calls': db.ai_invocation_count(self._record_prefix),
                'night_usd': str(self._cost_reader(self._window_start)),
                'month_usd': str(self._cost_reader(month_window_start(db.db_now()))),
                'disk_free_data_bytes': shutil.disk_usage(self._layout.data_dir).free,
                'disk_free_system_bytes': shutil.disk_usage(os.environ.get('SystemDrive', 'C:') + os.sep).free,
                'working_set_bytes': dir_size_bytes(self._layout.staging_dir),
            }
            try:
                sample['vram_used_mib'] = self._vram_reader()
                sample['vram_error'] = None
            except Exception as exc:
                sample['vram_used_mib'] = None
                sample['vram_error'] = type(exc).__name__
            return sample
        except Exception as exc:
            return {'t_utc': t_utc, 'elapsed_s': elapsed, 'sample_error': type(exc).__name__}

    def write(self, sample):
        line = c.redact(json.dumps(sample, sort_keys=True, default=str, ensure_ascii=True))
        self._sink_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._sink_path, 'a', encoding='utf-8') as handle:
            handle.write(line + '\n')

    def _loop(self):
        while True:
            sample = self.collect_sample()
            with self._lock:
                self.samples.append(sample)
            try:
                self.write(sample)
            except OSError:
                pass
            if self._stop.wait(self._interval):
                break

    def start(self):
        self._thread = threading.Thread(target=self._loop, name='cp7-overnight-sampler', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=30)

    def latest(self):
        with self._lock:
            return dict(self.samples[-1]) if self.samples else None


@dataclass
class OvernightRun:
    quota: dict = field(default_factory=dict)
    not_found_status: int = 0
    not_found_source: dict = field(default_factory=dict)
    pre_stop_attempts: int = 0
    other_workflows_running: int = -1
    launcher_seed_line: str = ''
    render_config: str = ''
    concurrency: dict = field(default_factory=dict)
    batch_id: str = ''
    record_prefix: str = ''
    window_start: object = None
    started_utc: str = ''
    target_utc: str = ''
    t_target_s: float | None = None
    resumed: bool = False
    stop_attempts: int = 0
    ready_seconds: float | None = None
    busy_at_stop: int = 0
    completed_at_stop: int = 0
    before_stop: dict = field(default_factory=dict)
    after_start: dict = field(default_factory=dict)
    stop_reason: str = ''
    warn_seen: bool = False
    wait_provider_seconds: float = 0.0
    samples: list = field(default_factory=list)
    api_calls: list = field(default_factory=list)
    sink_path: str = ''
    elapsed_seconds: float = 0.0
    night_usd: str = '0'
    month_usd: str = '0'
    ai_calls: int = 0
    drive_bytes: int = 0
    job_counts: dict = field(default_factory=dict)
    valid_jobs: list = field(default_factory=list)
    invalid_jobs: list = field(default_factory=list)
    failed_final_jobs: list = field(default_factory=list)
    drive_checks: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    collection: dict = field(default_factory=dict)
    reruns: dict = field(default_factory=dict)
    completed_unchanged: bool = False
    stage_metrics: dict = field(default_factory=dict)
    lead_p50_s: float | None = None
    lead_p95_s: float | None = None
    secret_matches: int = 0
    max_working_set_bytes: int = 0
    min_disk_free_bytes: int | None = None
    max_vram_mib: int | None = None


def run_overnight(work_dir, sink_path=None):
    """Chạy lô 100 video trên ngăn xếp thật: không thao tác tay; stop rồi start đúng một lần giữa lô; luôn dừng launcher ở cuối."""
    result = OvernightRun()
    launcher = d.load_launcher()
    db = OvernightDb(launcher)
    sink_path = Path(sink_path) if sink_path is not None else Path(work_dir) / 'timeline.jsonl'
    result.sink_path = str(sink_path)
    sampler = None
    try:
        result.quota = require_drive_quota(db)
        result.not_found_status = require_not_found_url()
        result.pre_stop_attempts = d.stop_until_exited()
        result.other_workflows_running = d.require_no_other_workflows()
        launch_path, _, launcher_out = d.start_capturing(work_dir, 'first')
        result.launcher_seed_line = d.launcher_seed_line(launcher_out)
        result.not_found_source = register_not_found_source(launcher, db, work_dir)
        result.render_config = d.require_render_config(db)
        session = OvernightSession(db.layout.cert_file, result.api_calls)
        session.open(launch_path)
        result.concurrency = session.get_batch_settings()
        result.window_start = window_start = db.db_now()
        batch_id = result.batch_id = session.post_overnight_batch(TARGET_VIDEOS, result.concurrency['default'])
        result.record_prefix = d.video_key_prefix(db.workspace_id, batch_id)
        started = time.monotonic()
        result.started_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        deadline = c.Deadline(DEADLINE_SECONDS)
        sampler = OvernightSampler(db, batch_id, result.record_prefix, window_start, db.layout, sink_path)
        sampler.start()
        wait = WaitClock()
        seen_ids = set()
        before_done = []
        read_failures = 0
        while True:
            time.sleep(min(POLL_SECONDS, max(0.1, deadline.remaining())))
            try:
                valid = db.valid_synced_count(batch_id)
                status = db.batch_status(batch_id)
                wait.observe(time.monotonic(), db.wait_provider_jobs(batch_id))
                seen_ids.update(j for j, _ in db.batch_jobs(batch_id))
                busy = db.running_busy(batch_id)
                read_failures = 0
            except Exception:
                read_failures += 1
                if read_failures >= 20:
                    raise
                if deadline.expired():
                    result.stop_reason = 'deadline'
                    break
                continue
            if result.t_target_s is None and valid >= TARGET_VIDEOS:
                result.t_target_s = time.monotonic() - started
                result.target_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            latest = sampler.latest()
            if latest and 'sample_error' not in latest:
                month = Decimal(latest.get('month_usd', '0'))
                if Decimal(latest.get('night_usd', '0')) > NIGHT_COST_CAP_USD or month > MONTH_COST_CAP_USD:
                    result.stop_reason = 'cost_cap'
                    break
                if month >= WARN_COST_USD:
                    result.warn_seen = True
            if should_resume(valid, time.monotonic() - started, result.resumed, busy):
                jobs_active = [j for j, s in db.batch_jobs(batch_id) if s not in ('COMPLETED', 'FAILED_FINAL')]
                result.before_stop = {j: db.stage_map(j) for j in jobs_active}
                result.busy_at_stop = sum(1 for rows in result.before_stop.values() if any(r['status'] == 'RUNNING' for r in rows.values()))
                before_done = db.completed_job_ids(batch_id)
                result.completed_at_stop = len(before_done)
                result.stop_attempts = d.stop_until_exited()
                launch2, t_start, _ = d.start_capturing(work_dir, 'resume')
                session = OvernightSession(db.layout.cert_file, result.api_calls)
                session.open(launch2)
                while True:
                    try:
                        deadline.check()
                        code, _ = session.get_batch(batch_id)
                    except c.DeadlineExceeded:
                        result.stop_reason = 'deadline'
                        break
                    except OSError:
                        code = None
                    if code == 200:
                        break
                    time.sleep(1)
                result.ready_seconds = time.monotonic() - t_start
                result.after_start = {j: db.stage_map(j) for j in jobs_active}
                result.resumed = True
                if result.stop_reason == 'deadline':
                    break
                continue
            if valid >= TARGET_VIDEOS:
                result.stop_reason = 'target_reached'
                break
            if status in TERMINAL_BATCH:
                result.stop_reason = 'batch_terminal'
                break
            if deadline.expired():
                result.stop_reason = 'deadline'
                break
        sampler.stop()
        result.samples = list(sampler.samples) + [sampler.collect_sample()]
        result.elapsed_seconds = time.monotonic() - started
        result.wait_provider_seconds = wait.seconds
        d.stop_until_exited()
        result.completed_unchanged = (not result.resumed) or set(before_done) <= set(db.completed_job_ids(batch_id))
        audit_run(db, result, seen_ids)
        return result
    finally:
        if sampler is not None:
            sampler.stop()
        try:
            d.stop_until_exited()
        except Exception:
            pass


def audit_run(db, run, seen_ids=frozenset()):
    """Kiểm toán chỉ đọc sau lô: job hợp lệ (ledger + cloud VERIFIED + QC), đối soát Drive mẫu, chi phí, cô lập nguồn, chạy lại stage, bí mật."""
    batch_id = run.batch_id
    jobs = db.batch_jobs(batch_id)
    run.job_counts = db.batch_job_counts(batch_id)
    run.failed_final_jobs = [j for j, s in jobs if s == 'FAILED_FINAL']
    run.findings = audit_jobs(jobs, db.stage_row_counts(batch_id), db.problem_missing(batch_id), set(seen_ids))
    run.valid_jobs = []
    run.invalid_jobs = []
    cloud_locations = {}
    for job_id, status in jobs:
        if status != 'COMPLETED':
            continue
        ledger = db.ledger_row(job_id)
        cloud = [loc for loc in db.locations(job_id) if d.is_drive(loc)]
        if len(cloud) != 1:
            run.invalid_jobs.append((job_id, 'cloud_locations=' + str(len(cloud))))
            continue
        if ledger is None or d.ordering_proof(cloud[0], ledger) is None:
            run.invalid_jobs.append((job_id, 'ordering_proof'))
            continue
        try:
            hard_failed = d.qc_gates(db, job_id)['hard_failed']
        except d.BlockedError:
            run.invalid_jobs.append((job_id, 'qc_blocked'))
            continue
        if hard_failed != 0:
            run.invalid_jobs.append((job_id, 'qc_hard_failed=' + str(hard_failed)))
            continue
        run.valid_jobs.append(job_id)
        cloud_locations[job_id] = cloud[0]
    ordered = sorted(run.valid_jobs)
    picks = list(range(0, len(ordered), 20))[:5]
    if ordered and len(ordered) - 1 not in picks:
        picks.append(len(ordered) - 1)
    run.drive_checks = []
    for index in picks[:6]:
        job_id = ordered[index]
        check = d.drive_md5_check(db, cloud_locations[job_id])
        run.drive_checks.append({'job': job_id[:8], 'md5_match': check['md5_match'], 'sha256_match': check['sha256_match'],
                                 'size': check['size']})
    run.drive_bytes = db.batch_drive_bytes(batch_id)
    run.ai_calls = db.ai_invocation_count(run.record_prefix)
    run.night_usd = str(d.CostWatch(db, run.window_start).spent())
    run.month_usd = str(d.CostWatch(db, month_window_start(db.db_now())).spent())
    run.collection = collection_isolation(db.collection_runs(run.window_start), run.not_found_source['source_id'])
    run.reruns = {}
    for job_id, before in run.before_stop.items():
        bad = sorted(set(d.find_reruns(before, db.stage_map(job_id))) | set(d.find_reruns(before, run.after_start.get(job_id, before))))
        if bad:
            run.reruns[job_id] = bad
    run.stage_metrics = stage_metrics(db.stage_durations(batch_id))
    leads = db.job_lead_seconds(batch_id)
    p50, p95 = percentile(leads, 50), percentile(leads, 95)
    run.lead_p50_s = None if p50 is None else round(p50, 1)
    run.lead_p95_s = None if p95 is None else round(p95, 1)
    good = [s for s in run.samples if 'sample_error' not in s]
    run.max_working_set_bytes = max((s['working_set_bytes'] for s in good), default=0)
    run.min_disk_free_bytes = min((s['disk_free_data_bytes'] for s in good), default=None)
    run.max_vram_mib = max((s['vram_used_mib'] for s in good if s.get('vram_used_mib') is not None), default=None)
    paths = [p for p in Path(db.layout.logs_dir).glob('*.log')] if Path(db.layout.logs_dir).is_dir() else []
    paths += [Path(db.layout.serve_log), Path(run.sink_path)]
    matches = 0
    for path in paths:
        try:
            matches += len(c.scan_secrets(path.read_text(encoding='utf-8', errors='replace')))
        except OSError:
            continue
    run.secret_matches = matches

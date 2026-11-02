"""CP7-12 / RG-11 phần hiệu năng UI và SSE; Chromium Playwright 1920x1080, 30 mẫu mỗi thao tác cold và warm riêng; ACK lệnh là PUT /v1/configs/policy:cp7-rg11-ack (lệnh ghi thật có receipt đồng bộ; cổng lệnh command_gateway() ở src/controlplane/api/main.py:136 không có handler production); 0 USD, không gọi AI; Deadline 90 phút."""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for d_path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(d_path) not in sys.path:
        sys.path.insert(0, str(d_path))

import psycopg
import pytest
import cp7_batch_driver as d
import cp7_common as c
import cp7_overnight_monitor as m

DEADLINE = c.Deadline(90 * 60)
SCREENS = ('jobs', 'batches', 'artifacts', 'cost')
SAMPLES = 30
UI_P95_MS = 2000
ACK_P95_MS = 1000
ACK_SCOPE = 'policy:cp7-rg11-ack'
PROBE = REPO / 'tools' / 'real' / 'cp7_browser_probe.js'
COUNT_TABLES = (
    'cp_video_jobs',
    'cp_production_batches',
    'cp_artifact_versions',
    'cp_artifact_locations',
    'cp_cost_records',
    'cp_completion_ledger',
    'cp_operation_stream',
)
RESULTS: dict[tuple[str, str], Any] = {}


def _probe_env() -> dict[str, str]:
    """Môi trường cho probe Node: nếu worktree thiếu src/controlplane/ui/node_modules/playwright thì trỏ CP7_PLAYWRIGHT_DIR tới playwright của runtime khoá (<runtime>/venv/Scripts/python.exe -> <runtime>/ui/node_modules/playwright)."""
    env = dict(os.environ)
    in_tree = REPO / 'src' / 'controlplane' / 'ui' / 'node_modules' / 'playwright'
    exe_parents = Path(sys.executable).parents
    locked = exe_parents[2] / 'ui' / 'node_modules' / 'playwright' if len(exe_parents) > 2 else None
    if not in_tree.is_dir() and locked is not None and (locked / 'package.json').is_file():
        env['CP7_PLAYWRIGHT_DIR'] = str(locked)
    return env


def _playwright_dir() -> str:
    in_tree = REPO / 'src' / 'controlplane' / 'ui' / 'node_modules' / 'playwright'
    if in_tree.is_dir():
        return str(in_tree)
    return _probe_env()['CP7_PLAYWRIGHT_DIR']


def _pass(emit: Any, item: str, *details: str) -> None:
    line = c.report_line('RG-11', item, 'PASS')
    emit(line)
    for detail in details:
        assert detail.isascii(), f'detail must be ASCII: {detail}'
        emit('- ' + item + ': ' + detail)


class _Api(d.ApiSession):
    def put_config(self, scope: str, payload: dict[str, Any], if_match: int) -> tuple[int, float, str]:
        headers = {
            'Cookie': '; '.join(f'{k}={v}' for k, v in self.cookies.items()),
            'Origin': f'https://{d.HOST}:{d.PORT}',
            'X-CSRF-Token': self.cookies['csrf_token'],
            'Content-Type': 'application/json',
            'Idempotency-Key': str(uuid.uuid4()),
            'If-Match': str(if_match),
        }
        body = json.dumps(payload).encode('utf-8')
        t0 = time.perf_counter()
        status, _, text = self._request('PUT', '/v1/configs/' + scope, headers, body)
        return status, (time.perf_counter() - t0) * 1000.0, text


def _latest_config(db: d.ReadOnlyDb, kind: str, key: str) -> tuple[int, int, str | None]:
    rows = db.query(
        'SELECT config_revision_number, revision, content_hash FROM controlplane.cp_config_revisions WHERE workspace_id = %s AND scope_kind = %s AND scope_key = %s ORDER BY config_revision_number DESC LIMIT 1',
        kind,
        key,
    )
    return rows[0] if rows else (0, 0, None)


NODE_SCRIPT = r'''
'use strict';
const fs = require('fs');
const cfg = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const { chromium } = require(cfg.playwrightDir);

async function openApp(browser) {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1920, height: 1080 } });
  await context.addCookies(cfg.cookies);
  const page = await context.newPage();
  await page.goto(cfg.baseUrl + '/', { waitUntil: 'load', timeout: 60000 });
  await page.waitForSelector('h1.brand-title');
  await page.click('[data-testid="tab-screens"]');
  return { context, page };
}

async function measure(page, id) {
  const t0 = performance.now();
  await page.click(`[data-testid="screen-nav-${id}"]`);
  await page.waitForSelector(`[data-testid="module-row-${id}-0"]`, { timeout: 30000 });
  const ms = performance.now() - t0;
  const rows = await page.locator(`[data-testid^="module-row-${id}-"]`).count();
  return { ms, rows };
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const samples = {};
    const rows = {};
    for (const id of cfg.screens) {
      samples[id] = [];
      rows[id] = 0;
    }
    let lastViewport = null;
    if (cfg.mode === 'cold') {
      for (let i = 0; i < cfg.samples; i++) {
        const { context, page } = await openApp(browser);
        lastViewport = page.viewportSize();
        for (const id of cfg.screens) {
          const res = await measure(page, id);
          samples[id].push(res.ms);
          if (res.rows > rows[id]) rows[id] = res.rows;
        }
        await context.close();
      }
    } else {
      const { context, page } = await openApp(browser);
      lastViewport = page.viewportSize();
      for (const id of cfg.screens) {
        await page.click('[data-testid="screen-nav-operations"]');
        await measure(page, id);
      }
      for (let i = 0; i < cfg.samples; i++) {
        for (const id of cfg.screens) {
          await page.click('[data-testid="screen-nav-operations"]');
          const res = await measure(page, id);
          samples[id].push(res.ms);
          if (rows[id] === 0 || res.rows < rows[id]) rows[id] = res.rows;
        }
      }
      await context.close();
    }
    fs.writeFileSync(cfg.out, JSON.stringify({ mode: cfg.mode, samples, rows, viewport: lastViewport }));
  } catch (e) {
    console.error(String(e.message).replace(/cap=[A-Za-z0-9_-]+/g, 'cap=[REDACTED]').slice(0, 300));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
'''


def _run_ui(live: Any, mode: str) -> dict[str, Any]:
    script_file = live.work / 'ui_perf.js'
    script_file.write_text(NODE_SCRIPT.strip(), encoding='utf-8')
    cfg_file = live.work / f'ui_{mode}.cfg.json'
    out_file = live.work / f'ui_{mode}.json'
    cfg_data = {
        'mode': mode,
        'baseUrl': f'https://{d.HOST}:{d.PORT}',
        'cookies': live.cookies,
        'screens': list(SCREENS),
        'samples': SAMPLES,
        'playwrightDir': _playwright_dir(),
        'out': str(out_file),
    }
    cfg_file.write_text(json.dumps(cfg_data), encoding='utf-8')
    proc = subprocess.run(
        ['node', str(script_file), str(cfg_file)],
        cwd=str(REPO),
        env=_probe_env(),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=DEADLINE.timeout(1500),
        check=False,
    )
    assert proc.returncode == 0, c.redact((proc.stdout + proc.stderr)[-400:])
    data = json.loads(out_file.read_text(encoding='utf-8'))
    for sid in SCREENS:
        assert len(data['samples'][sid]) == SAMPLES, f'{sid} samples len != {SAMPLES}'
        assert data['rows'][sid] >= 1, f'{sid} rows < 1'
    assert data['viewport'] == {'width': 1920, 'height': 1080}, f'viewport mismatch: {data["viewport"]}'
    return data


@pytest.fixture(scope='module')
def live() -> Any:
    work = Path(tempfile.mkdtemp(prefix='cp7-12-'))
    launcher = d.load_launcher()
    db = d.ReadOnlyDb(launcher)
    counts = {
        t: int(db.query(f'SELECT count(*) FROM controlplane.{t} WHERE workspace_id = %s')[0][0])
        for t in COUNT_TABLES
    }
    if counts['cp_video_jobs'] < 100 or any(counts[t] <= 0 for t in COUNT_TABLES if t != 'cp_video_jobs'):
        pytest.fail('BLOCKED: dữ liệu rỗng hoặc dưới 100 video job')
    counts_sha = hashlib.sha256(json.dumps(counts, sort_keys=True).encode('utf-8')).hexdigest()
    d.stop_until_exited()
    try:
        d.require_no_other_workflows()
    except d.BlockedError as exc:
        pytest.fail(str(exc))
    launch_path, _, _ = d.start_capturing(work, 'rg11ui')
    url_file = work / 'launch.url'
    url_file.write_text(f'https://{d.HOST}:{d.PORT}{launch_path}', encoding='utf-8')
    proc = subprocess.run(
        ['node', str(PROBE), '--url-file', str(url_file), '--out', str(work / 'probe')],
        cwd=str(REPO),
        env=_probe_env(),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=DEADLINE.timeout(180),
        check=False,
    )
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert proc.returncode == 0 and result['ok'], f'probe failed: {c.redact((proc.stdout + proc.stderr)[-400:])}'
    cookies = json.loads((work / 'probe' / 'cookies.json').read_text(encoding='utf-8'))
    session = _Api(db.layout.cert_file)
    session.cookies = {x['name']: x['value'] for x in cookies if x['name'] in ('cp_session', 'csrf_token')}
    try:
        yield SimpleNamespace(
            db=db, session=session, work=work, cookies=cookies, counts=counts, counts_sha=counts_sha
        )
    finally:
        try:
            d.stop_until_exited()
        finally:
            shutil.rmtree(work, ignore_errors=True)


def _ui(live: Any, mode: str) -> dict[str, Any]:
    key = ('ui', mode)
    if key not in RESULTS:
        RESULTS[key] = _run_ui(live, mode)
    return RESULTS[key]


def _ack(live: Any, mode: str) -> list[float]:
    key = ('ack', mode)
    if key in RESULTS:
        return RESULTS[key]
    if mode == 'warm':
        for _ in range(3):
            num, rev, _ = _latest_config(live.db, 'policy', 'cp7-rg11-ack')
            live.session.put_config(
                ACK_SCOPE, {'cp7_ack': mode, 'seq': -1, 'nonce': uuid.uuid4().hex}, rev
            )
    samples: list[float] = []
    for i in range(SAMPLES):
        num, rev, _ = _latest_config(live.db, 'policy', 'cp7-rg11-ack')
        status, ms, text = live.session.put_config(
            ACK_SCOPE, {'cp7_ack': mode, 'seq': i, 'nonce': uuid.uuid4().hex}, rev
        )
        assert status in (200, 202), f'status={status} body={c.redact(text[:200])}'
        samples.append(ms)
    RESULTS[key] = samples
    return samples


def _summary(values: list[float]) -> tuple[float, float]:
    return m.percentile(values, 50), m.percentile(values, 95)


def _ui_lines(data: dict[str, Any]) -> list[str]:
    return [
        f'{sid}: n={len(data["samples"][sid])} p50_ms={m.percentile(data["samples"][sid], 50):.0f} p95_ms={m.percentile(data["samples"][sid], 95):.0f} rows_min={data["rows"][sid]}'
        for sid in SCREENS
    ]


def test_rg11_ui_p95_cold(live: Any, emit: Any) -> None:
    data = _ui(live, 'cold')
    for sid in SCREENS:
        p95 = m.percentile(data['samples'][sid], 95)
        assert p95 <= UI_P95_MS, f'{sid} p95={p95} > {UI_P95_MS}'
    _pass(
        emit,
        'ui_p95_cold',
        f'browser=chromium viewport=1920x1080 samples={SAMPLES} limit_ms={UI_P95_MS}',
        f'dataset_counts_sha256={live.counts_sha}',
        'dataset_counts=' + json.dumps(live.counts, sort_keys=True),
        *_ui_lines(data),
    )


def test_rg11_ack_p95_cold(live: Any, emit: Any) -> None:
    values = _ack(live, 'cold')
    p50, p95 = _summary(values)
    assert p95 <= ACK_P95_MS, f'p95={p95} > {ACK_P95_MS}'
    _pass(
        emit,
        'ack_p95_cold',
        f'command=PUT /v1/configs/{ACK_SCOPE} samples={SAMPLES} limit_ms={ACK_P95_MS}',
        f'p50_ms={p50:.0f} p95_ms={p95:.0f}',
    )


def test_rg11_ui_p95_warm(live: Any, emit: Any) -> None:
    data = _ui(live, 'warm')
    for sid in SCREENS:
        p95 = m.percentile(data['samples'][sid], 95)
        assert p95 <= UI_P95_MS, f'{sid} p95={p95} > {UI_P95_MS}'
    _pass(
        emit,
        'ui_p95_warm',
        f'browser=chromium viewport=1920x1080 samples={SAMPLES} limit_ms={UI_P95_MS}',
        f'dataset_counts_sha256={live.counts_sha}',
        'dataset_counts=' + json.dumps(live.counts, sort_keys=True),
        *_ui_lines(data),
    )


def test_rg11_ack_p95_warm(live: Any, emit: Any) -> None:
    values = _ack(live, 'warm')
    p50, p95 = _summary(values)
    assert p95 <= ACK_P95_MS, f'p95={p95} > {ACK_P95_MS}'
    _pass(
        emit,
        'ack_p95_warm',
        f'command=PUT /v1/configs/{ACK_SCOPE} samples={SAMPLES} limit_ms={ACK_P95_MS}',
        f'p50_ms={p50:.0f} p95_ms={p95:.0f}',
    )


def _sse(
    live: Any, query: str = '', last_event_id: str | None = None, max_events: int | None = None, timeout: float = 20.0
) -> tuple[int, list[dict[str, Any]], bool]:
    conn = http.client.HTTPSConnection(d.HOST, d.PORT, timeout=timeout, context=live.session._ctx)
    try:
        conn.putrequest('GET', '/v1/operations/stream' + query, skip_host=True, skip_accept_encoding=True)
        conn.putheader('Host', f'{d.HOST}:{d.PORT}')
        cookie_header = '; '.join(f'{k}={v}' for k, v in live.session.cookies.items())
        conn.putheader('Cookie', cookie_header)
        conn.putheader('Accept', 'text/event-stream')
        if last_event_id is not None:
            conn.putheader('Last-Event-ID', str(last_event_id))
        conn.endheaders()
        resp = conn.getresponse()
        frames: list[dict[str, Any]] = []
        closed = False
        cur_id: int | str | None = None
        cur_event: str | None = None
        cur_data: list[str] = []

        def flush_frame() -> None:
            nonlocal cur_id, cur_event, cur_data
            if cur_id is None and cur_event is None and not cur_data:
                return
            data_str = '\n'.join(cur_data) if cur_data else None
            frame = {'id': cur_id, 'event': cur_event, 'data': data_str}
            cur_id = None
            cur_event = None
            cur_data = []
            frames.append(frame)

        while True:
            if max_events is not None and sum(1 for f in frames if f.get('id') is not None) >= max_events:
                break
            try:
                line_bytes = resp.readline()
            except (TimeoutError, socket.timeout):
                break
            if not line_bytes:
                closed = True
                flush_frame()
                break
            line = line_bytes.decode('utf-8', errors='replace').rstrip('\r\n')
            if not line:
                flush_frame()
                if max_events is not None and sum(1 for f in frames if f.get('id') is not None) >= max_events:
                    break
                continue
            if line.startswith(':'):
                continue
            if line.startswith('id:'):
                val = line[3:].strip()
                try:
                    cur_id = int(val)
                except ValueError:
                    cur_id = val
            elif line.startswith('event:'):
                cur_event = line[6:].strip()
            elif line.startswith('data:'):
                cur_data.append(line[5:].lstrip(' '))
            elif line.startswith('retry:'):
                continue

        flush_frame()
        return resp.status, frames, closed
    finally:
        conn.close()


def test_rg11_sse_resync(live: Any, emit: Any) -> None:
    ids = sorted(
        r[0]
        for r in live.db.query(
            'SELECT stream_event_id FROM controlplane.cp_operation_stream WHERE workspace_id = %s ORDER BY stream_event_id DESC LIMIT 400'
        )
    )
    wm = live.db.query(
        'SELECT minimum_available_cursor FROM controlplane.cp_operation_stream_retention_watermarks WHERE workspace_id = %s'
    )
    if wm:
        ids = [i for i in ids if i >= wm[0][0]]
    if len(ids) < 300:
        pytest.fail(f'BLOCKED: cp_operation_stream có {len(ids)} ids < 300')
    expected = ids[1:]

    status1, frames1, _ = _sse(live, '?cursor=' + str(ids[0]), max_events=150)
    seen1 = [f['id'] for f in frames1 if f.get('id') is not None]
    assert seen1 == expected[:150], f'seen1 != expected[:150]: len={len(seen1)}'

    status2, frames2, _ = _sse(live, last_event_id=str(seen1[-1]), max_events=150)
    seen2 = [f['id'] for f in frames2 if f.get('id') is not None]
    assert seen2 == expected[150:300], f'seen2 != expected[150:300]: len={len(seen2)}'
    assert set(seen1).isdisjoint(seen2), 'seen1 and seen2 have common events'
    full_seq = seen1 + seen2
    assert all(full_seq[i] < full_seq[i + 1] for i in range(len(full_seq) - 1)), 'sequence not strictly increasing'

    W = ids[200]
    c_old = ids[10]
    initial_rows = live.db.query(
        'SELECT minimum_available_cursor, minimum_available_at FROM controlplane.cp_operation_stream_retention_watermarks WHERE workspace_id = %s'
    )
    initial = initial_rows[0] if initial_rows else None
    try:
        with psycopg.connect(live.db.dsn, autocommit=True, connect_timeout=10) as conn:
            conn.execute(
                'INSERT INTO controlplane.cp_operation_stream_retention_watermarks (workspace_id, minimum_available_cursor, minimum_available_at) VALUES (%s, %s, CURRENT_TIMESTAMP) ON CONFLICT (workspace_id) DO UPDATE SET minimum_available_cursor = EXCLUDED.minimum_available_cursor, minimum_available_at = CURRENT_TIMESTAMP',
                (live.db.workspace_id, W),
            )
        status_resync, frames_resync, closed_resync = _sse(live, '?cursor=' + str(c_old))
        assert status_resync == 200, f'status={status_resync}'
        assert len(frames_resync) >= 1, f'no frames in resync: {frames_resync}'
        first_frame = frames_resync[0]
        assert first_frame['event'] == 'resync_required', f'event={first_frame.get("event")}'
        data_obj = json.loads(first_frame['data'])
        assert data_obj.get('resync_required') is True
        assert data_obj.get('reason') == 'cursor_expired'
        assert data_obj.get('cursor') == str(W)
        assert closed_resync is True

        status_rec, frames_rec, _ = _sse(live, '?cursor=' + str(W), max_events=20)
        seen_rec = [f['id'] for f in frames_rec if f.get('id') is not None]
        assert len(seen_rec) > 0, 'no recovery frames'
        assert seen_rec[0] == ids[201]
        assert all(i > W for i in seen_rec)
        assert all(seen_rec[i] < seen_rec[i + 1] for i in range(len(seen_rec) - 1))
    finally:
        with psycopg.connect(live.db.dsn, autocommit=True, connect_timeout=10) as conn:
            if initial is None:
                conn.execute(
                    'DELETE FROM controlplane.cp_operation_stream_retention_watermarks WHERE workspace_id = %s',
                    (live.db.workspace_id,),
                )
            else:
                conn.execute(
                    'UPDATE controlplane.cp_operation_stream_retention_watermarks SET minimum_available_cursor = %s, minimum_available_at = %s WHERE workspace_id = %s',
                    (initial[0], initial[1], live.db.workspace_id),
                )
        after_rows = live.db.query(
            'SELECT minimum_available_cursor, minimum_available_at FROM controlplane.cp_operation_stream_retention_watermarks WHERE workspace_id = %s'
        )
        after = after_rows[0] if after_rows else None
        assert after == initial, f'watermark restore failed: after={after} != initial={initial}'

    _pass(
        emit,
        'sse_resync',
        f'replay_events={len(seen1)}+{len(seen2)} duplicates=0 gaps=0 expired_cursor_event=resync_required recovery_first_id_ok=True watermark_restored=True',
    )

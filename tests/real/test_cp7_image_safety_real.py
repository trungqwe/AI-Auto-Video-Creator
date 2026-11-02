"""CP7-7 / RG-06: an toàn ảnh thật (OI-CP7-02).

Bộ ảnh nhạy cảm nằm ngoài cây Git (LOCALAPPDATA/AIAutoVideoCreator/real-fixtures/sensitive); 5 ảnh đầu mỗi nhóm safe, tre-em, mau-me, vu-khi, uncertain đi qua LlmImageSafetyDetector + RouterVisionRoute thật,
che bằng RealFfmpegMediaTool (boxblur luma_power 1, bán kính theo blur_radius, tối thiểu 4) của FFmpeg đã ghim; lỗi detector thật bằng timeout 1 ms trên tuyến thật;
trần chi phí (CALL_CAP 35 lời gọi mỗi lượt chạy, ledger +5 USD, hạn 45 phút, Ctrl+C); không in khóa, không nhúng ảnh.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pytest  # noqa: E402

import cp7_common as c  # noqa: E402

PROFILE_PATH = REPO / 'tools' / 'launcher' / 'prod' / 'profile.json'
PORTS_PATH = REPO / 'tools' / 'launcher' / 'prod' / 'ports.json'
LOCK_PATH = REPO / 'tools' / 'runtime' / 'runtime.lock.json'
REPORT_DIR = REPO / 'docs' / 'delivery-evidence' / 'cp7-7'
REPORT = REPORT_DIR / 'report.md'
FFMPEG = Path('C:/ffmpeg/bin/ffmpeg.exe')
FFPROBE = FFMPEG.with_name('ffprobe.exe')

ROUTER_HOST = '127.0.0.1'
ROUTER_PORT = 20128
ENDPOINT = 'http://127.0.0.1:20128/v1'
MODEL = 'ag/gemini-3.8-flash-high'
WS = 'ws-1'

GROUPS = ('safe', 'tre-em', 'mau-me', 'vu-khi', 'uncertain', 'loi-transform', 'khong-doc-duoc')
DETECTED_GROUPS = ('safe', 'tre-em', 'mau-me', 'vu-khi', 'uncertain')
HARMFUL_GROUPS = ('tre-em', 'mau-me', 'vu-khi')
BLUR_GROUPS = {'mau-me': 'graphic_violence', 'vu-khi': 'weapon'}
MIN_GROUPS = 7
MIN_PER_GROUP = 5
PER_GROUP = 5
TIMEOUT_CASES = 5
CALL_CAP = 35
LEDGER_CEILING_USD = Decimal('5')
ESTIMATED_COST_PER_REQUEST = Decimal('0.01')
DEADLINE_SECONDS = 45 * 60
BREAKER_LIMIT = 3
BLUR_MIN_REDUCTION = 0.5
CENTER_REGION = (0.25, 0.25, 0.5, 0.5)
TINY_REGION = (0.0, 0.0, 0.0001, 0.0001)
TIMEOUT_1MS = 0.001
MIME_BY_SUFFIX = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif'}
USABLE_ORIGINAL = 'USABLE_ORIGINAL'
BLURRED = 'BLURRED'
EXCLUDED = 'EXCLUDED'
_EDGE_RE = re.compile(r'lavfi\.signalstats\.YAVG=([0-9.]+)')

def _data_root():
    base = os.environ.get('AIAVC_DATA_DIR')
    return Path(base) if base else Path(os.environ['LOCALAPPDATA']) / 'AIAutoVideoCreator'


def _ascii(text):
    return str(text).encode('ascii', 'replace').decode('ascii')


def _set_root():
    return _data_root() / 'real-fixtures' / 'sensitive'


class _UrlMeter:
    def __init__(self):
        self.hits = []

    def patched_open(self, original):
        meter = self

        def wrapper(opener, fullurl, *args, **kwargs):
            url = fullurl if isinstance(fullurl, str) else getattr(fullurl, 'full_url', str(fullurl))
            entry = {'url': url, 'status': None}
            meter.hits.append(entry)
            try:
                resp = original(opener, fullurl, *args, **kwargs)
                entry['status'] = getattr(resp, 'status', getattr(resp, 'code', 200))
                return resp
            except urllib.error.HTTPError as exc:
                entry['status'] = exc.code
                raise

        return wrapper


def _artifact(entry, sha=None):
    from voice.domain.processing import ArtifactRef
    return ArtifactRef(ref=entry.ref, content_sha256=sha or entry.sha256)


def _load_set():
    root = _set_root()
    manifest_path = root / 'manifest.json'
    if not manifest_path.is_file():
        pytest.fail('BLOCKED(OI-CP7-02): sensitive image set manifest missing')
    groups = json.loads(manifest_path.read_text(encoding='utf-8')).get('groups', {})
    entries = {}
    for group in GROUPS:
        items = groups.get(group) or []
        if len(items) < MIN_PER_GROUP:
            pytest.fail(_ascii(f'BLOCKED(OI-CP7-02): group {group} has {len(items)} < {MIN_PER_GROUP} images'))
        entries[group] = []
        for item in items:
            name = item['file']
            path = root / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                pytest.fail(_ascii(f'BLOCKED(OI-CP7-02): file missing or sha256 mismatch {name}'))
            entries[group].append(SimpleNamespace(
                group=group, id=path.stem, ref=f'{group}/{path.name}', path=path, sha256=item['sha256'],
                mime=MIME_BY_SUFFIX.get(path.suffix.lower(), 'image/jpeg'),
                license=str(item.get('license', '')).strip(), source=str(item.get('source', '')).strip()))
    return root, entries

def _run(args, timeout=300):
    return subprocess.run(
        args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, check=False,
        shell=False, stdin=subprocess.DEVNULL)


def _image_size(path):
    done = _run([str(FFPROBE), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'json', str(path)])
    streams = json.loads(done.stdout or '{}').get('streams') or []
    assert streams, f'no video stream in {path.name}'
    return int(streams[0]['width']), int(streams[0]['height'])


def _decodes_clean(path):
    if path.stat().st_size == 0:
        return False
    done = _run([str(FFMPEG), '-nostdin', '-hide_banner', '-v', 'error', '-xerror', '-i', str(path), '-frames:v', '1', '-f', 'null', '-'])
    return done.returncode == 0 and not done.stderr.strip()


def _region_pixels(width, height, mask_ref):
    from voice.adapters.real_ffmpeg_media_tool import parse_mask_ref
    x, y, w, h = parse_mask_ref(mask_ref)
    px = int(x * width)
    py = int(y * height)
    return px, py, min(max(1, round(w * width)), width - px), min(max(1, round(h * height)), height - py)


def _edge_level(path, px, py, pw, ph):
    graph = (
        f'crop={pw}:{ph}:{px}:{py},format=gray,edgedetect=low=0.05:high=0.15,format=yuv444p,'
        'signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-')
    done = _run([str(FFMPEG), '-nostdin', '-hide_banner', '-v', 'error', '-i', str(path), '-vf', graph, '-frames:v', '1', '-f', 'null', '-'])
    assert done.returncode == 0, f'signalstats failed: {_ascii(done.stderr[:200])}'
    match = _EDGE_RE.search(done.stdout)
    assert match is not None, 'signalstats YAVG missing'
    return float(match.group(1))

class _CountingVision:
    def __init__(self, inner, ledger, clock):
        self._inner = inner
        self._ledger = ledger
        self._clock = clock
        self.count = 0

    def invoke_vision(self, ai_role, instructions, image_base64, media_type, timeout_seconds):
        from controlplane.domain.config_security.incremental_cost import IncrementalCostRecord
        self.count += 1
        try:
            return self._inner.invoke_vision(ai_role, instructions, image_base64, media_type, timeout_seconds)
        finally:
            ref = f'cp7-7-vision:{ai_role}:{self.count}'
            self._ledger.append(WS, IncrementalCostRecord(
                record_id=ref, provider='router-primary', service=MODEL, operation_ref=ref, job_ref='cp7-7-vision',
                batch_ref=None, quantity=Decimal('1'), unit='request', estimated_cost=ESTIMATED_COST_PER_REQUEST,
                actual_cost=ESTIMATED_COST_PER_REQUEST, currency='USD', source='vision_route_test',
                occurred_at=self._clock().isoformat(), cost_category='api_paid'))


def _build_stack():
    from controlplane.api.wiring.config_security import InMemoryCostLedger
    from controlplane.api.wiring.creative import monthly_window
    from controlplane.api.wiring.production_profile import load_production_profile
    from controlplane.infrastructure.production_ports.credentials import RouterKeyCredentials
    from controlplane.infrastructure.production_ports.vision_route import RouterVisionRoute
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore

    profile = load_production_profile(PROFILE_PATH)
    assert profile.profile_name == 'production'
    assert profile.ai.route_endpoint == ENDPOINT
    assert profile.ai.route_model_refs['image_safety'] == MODEL
    router = json.loads(PORTS_PATH.read_text(encoding='utf-8'))['router']
    account_ref = router['account_ref']
    secret_ref = router['secret_ref']
    store = DpapiSecretStore(_data_root() / 'vault')
    assert store.current_version(secret_ref) is not None, 'secret_ref not in vault'
    credentials = RouterKeyCredentials(store, account_ref, secret_ref)
    ledger = InMemoryCostLedger()
    clock = lambda: datetime.now(timezone.utc)
    route = RouterVisionRoute(profile.ai.route_endpoint, profile.ai.route_model_refs, credentials, account_ref)
    return SimpleNamespace(
        profile=profile, store=store, secret_ref=secret_ref, ledger=ledger, clock=clock,
        vision=_CountingVision(route, ledger, clock), window=monthly_window(profile.budget.window_timezone))

def _policy_bundle(profile):
    from voice.adapters.profile_media_policy import (
        build_image_safety_policy, build_image_safety_rules, build_transform_output_profile, build_transform_policy)
    params = profile.parameters
    return SimpleNamespace(
        rules=build_image_safety_rules(params), policy=build_image_safety_policy(params),
        transform_policy=build_transform_policy(params), output_profile=build_transform_output_profile(params))


def _make_tool(sources, out_dir):
    from voice.adapters.real_ffmpeg_media_tool import FfmpegToolError, RealFfmpegMediaTool
    out_dir.mkdir(parents=True, exist_ok=True)
    produced = {}

    def resolve_input(ref):
        if ref not in sources:
            raise FfmpegToolError('input_missing')
        return sources[ref]

    def resolve_output(ref, extension):
        path = out_dir / (ref.replace(':', '_') + '.' + extension)
        produced[ref] = path
        return path

    return RealFfmpegMediaTool(FFMPEG, LOCK_PATH, resolve_input, resolve_output), produced


def _region_reductions(source, produced_path, regions):
    width, height = _image_size(source)
    reductions = []
    for region in regions:
        px, py, pw, ph = _region_pixels(width, height, region.mask_ref)
        before = _edge_level(source, px, py, pw, ph)
        after = _edge_level(produced_path, px, py, pw, ph)
        reductions.append(None if before <= 0 else (before - after) / before)
    return reductions

def _evaluate(stack, bundle, tool, produced, entry, timeout_seconds):
    from voice.adapters.profile_media_policy import TRANSFORM, USABLE, image_disposition
    from voice.adapters.real_llm_image_safety import LlmImageSafetyDetector
    from voice.domain.image_safety import SafetyOutcome, assess_image_safety
    from voice.domain.image_transform import TransformStatus, transform_sensitive_image

    data = entry.path.read_bytes()
    ref = _artifact(entry)
    detector = LlmImageSafetyDetector(
        stack.vision, ref, lambda _ref: (data, entry.mime),
        categories=bundle.rules.categories, timeout_seconds=timeout_seconds)
    started = time.monotonic()
    assessment = assess_image_safety('image', detector, bundle.policy)
    seconds = time.monotonic() - started
    kind, reason = image_disposition(assessment, bundle.rules, has_regions=bool(detector.regions))
    final, reductions = EXCLUDED, []
    if kind == USABLE:
        final = USABLE_ORIGINAL
    elif kind == TRANSFORM:
        try:
            result = transform_sensitive_image(
                'image', False, assessment, ref, detector.regions, bundle.transform_policy, bundle.output_profile, tool)
        except Exception as exc:
            result, reason = None, 'transform_error:' + type(exc).__name__
        if result is not None and result.status is TransformStatus.FAILURE:
            reason = 'transform_failed'
        elif result is not None:
            reductions = _region_reductions(entry.path, produced[result.processed_ref.ref], detector.regions)
            final = BLURRED
            reason = 'blurred' if result.outcome is SafetyOutcome.SAFE else 'blurred_with_warning'
    return SimpleNamespace(
        group=entry.group, id=entry.id, outcome=assessment.outcome.value, original_usable=assessment.original_usable,
        confidence=assessment.confidence, categories=assessment.categories, failure_code=detector.failure_code, regions=len(detector.regions),
        kind=kind, reason=reason, final=final, reductions=reductions, seconds=seconds)


def _forced_transform(bundle, tool, ref, box, category='graphic_violence'):
    from voice.adapters.real_ffmpeg_media_tool import format_mask_ref
    from voice.domain.image_safety import ImageSafetyAssessment, SafetyOutcome
    from voice.domain.image_transform import TransformRegion, transform_sensitive_image

    assessment = ImageSafetyAssessment(
        outcome=SafetyOutcome.TRANSFORM_REQUIRED, original_usable=False, reason='categories_require_transform',
        categories=(category,), confidence=0.9, policy_revision=bundle.policy.revision)
    regions = (TransformRegion(category, 0.9, format_mask_ref(*box)),)
    result = transform_sensitive_image(
        'image', False, assessment, ref, regions, bundle.transform_policy, bundle.output_profile, tool)
    return result, regions

@pytest.fixture(scope='module')
def measurement(tmp_path_factory):
    deadline = c.Deadline(DEADLINE_SECONDS)
    meter = _UrlMeter()
    mp = pytest.MonkeyPatch()
    mp.setattr(urllib.request.OpenerDirector, 'open', meter.patched_open(urllib.request.OpenerDirector.open))
    work_dir = tmp_path_factory.mktemp('cp7-7')
    try:
        root, entries = _load_set()
        stack = _build_stack()
        bundle = _policy_bundle(stack.profile)
        assert bundle.policy.require_transform_before_use is True
        assert (bundle.output_profile['luma_radius'], bundle.output_profile['luma_power']) == (4, 1)
        guard = c.CostGuard.from_ledger(stack.ledger, WS, *stack.window(stack.clock()), LEDGER_CEILING_USD)
        sources = {item.ref: item.path for items in entries.values() for item in items}
        tool_main, produced_main = _make_tool(sources, work_dir / 'main')
        vision_timeout = stack.profile.image_safety.vision_timeout_seconds

        def guarded(entry, cap):
            deadline.check()
            assert stack.vision.count < CALL_CAP, f'CALL_CAP {CALL_CAP} reached'
            guard.check(additional_usd=ESTIMATED_COST_PER_REQUEST)
            return _evaluate(stack, bundle, tool_main, produced_main, entry, deadline.timeout(cap=cap))

        results, timeouts, consecutive = [], [], 0
        for group in DETECTED_GROUPS:
            for entry in entries[group][:PER_GROUP]:
                res = guarded(entry, vision_timeout)
                consecutive = consecutive + 1 if res.failure_code in ('detector_error', 'route_timeout') else 0
                if consecutive >= BREAKER_LIMIT:
                    last = meter.hits[-1] if meter.hits else {}
                    url, status = last.get('url'), last.get('status')
                    pytest.fail(_ascii(f'BLOCKED(circuit breaker): {consecutive} consecutive route failures code={res.failure_code} url={url} status={status}'))
                results.append(res)
        for group in DETECTED_GROUPS:
            timeouts.append(guarded(entries[group][0], TIMEOUT_1MS))

        tool_ok, _produced_ok = _make_tool(sources, work_dir / 'loi-ok')
        tool_fail, _produced_fail = _make_tool(sources, work_dir / 'loi-fail')
        transform_modes = []
        for entry in entries['loi-transform']:
            ok, _ = _forced_transform(bundle, tool_ok, _artifact(entry), CENTER_REGION)
            bad_sha, _ = _forced_transform(bundle, tool_fail, _artifact(entry, '0' * 64), CENTER_REGION)
            tiny, _ = _forced_transform(bundle, tool_fail, _artifact(entry), TINY_REGION)
            transform_modes.append(SimpleNamespace(id=entry.id, ok=ok, bad_sha=bad_sha, tiny=tiny))
        unreadable = []
        for entry in entries['khong-doc-duoc']:
            probe = tool_ok.probe(_artifact(entry))
            clean = _decodes_clean(entry.path)
            final = EXCLUDED if (not probe or not clean) else USABLE_ORIGINAL
            unreadable.append(SimpleNamespace(id=entry.id, probe_empty=not probe, decode_clean=clean, final=final))

        yield SimpleNamespace(
            root=root, entries=entries, sources=sources, work_dir=work_dir, stack=stack, bundle=bundle, guard=guard,
            results=results, timeouts=timeouts, transform_modes=transform_modes, unreadable=unreadable, hits=meter.hits)
    finally:
        mp.undo()
        shutil.rmtree(work_dir, ignore_errors=True)


def _by_group(measurement, group):
    return [item for item in measurement.results if item.group == group]


def _tally(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _leaked(items):
    return [item.id for item in items if item.outcome == 'SAFE' or item.kind == 'usable' or item.final == USABLE_ORIGINAL]


def test_rg06_set_present(measurement, emit):
    assert len(measurement.entries) >= MIN_GROUPS
    counts = {}
    for group, items in measurement.entries.items():
        assert len(items) >= MIN_PER_GROUP, group
        counts[group] = len(items)
        for item in items:
            assert item.license and item.source, f'unclear license or source for {item.ref}'
    with pytest.raises(ValueError):
        measurement.root.resolve().relative_to(REPO.resolve())
    stray = [p.name for p in REPORT_DIR.glob('*') if p.name != 'report.md'] if REPORT_DIR.is_dir() else []
    assert stray == [], f'unexpected files in evidence dir: {stray}'
    emit(c.report_line('RG-06', 'set_present', 'PASS'))
    emit(f'- set_present: groups={len(counts)} images_by_group={_ascii(json.dumps(counts))} sha256_verified=True outside_git=True')


def test_rg06_false_safe_zero(measurement, emit):
    parts = []
    for group in HARMFUL_GROUPS:
        items = _by_group(measurement, group)
        assert len(items) == PER_GROUP, group
        assert _leaked(items) == [], f'false safe in {group}: {_leaked(items)}'
        for item in items:
            if item.outcome == 'TRANSFORM_REQUIRED':
                assert item.original_usable is False, item.id
        parts.append(f'{group}={_ascii(json.dumps(_tally(i.outcome for i in items)))} final={_ascii(json.dumps(_tally(i.final for i in items)))}')
    emit(c.report_line('RG-06', 'false_safe_zero', 'PASS'))
    emit('- false_safe_zero: false_safe=0 ' + ' '.join(parts))


def test_rg06_uncertain_never_safe(measurement, emit):
    items = _by_group(measurement, 'uncertain')
    assert len(items) == PER_GROUP
    assert [i.id for i in items if i.outcome == 'UNCERTAIN' and i.final != USABLE_ORIGINAL] == [], 'uncertain outcome must use the original (RG-13)'
    assert len(measurement.unreadable) >= MIN_PER_GROUP
    bad = [u.id for u in measurement.unreadable if u.final == USABLE_ORIGINAL]
    assert bad == [], f'unreadable not excluded: {bad}'
    emit(c.report_line('RG-06', 'uncertain_never_safe', 'PASS'))
    emit(f'- uncertain_never_safe: uncertain_outcomes={_ascii(json.dumps(_tally(i.outcome for i in items)))} unreadable={len(measurement.unreadable)} unreadable_excluded={len(measurement.unreadable)} probe_empty={sum(1 for u in measurement.unreadable if u.probe_empty)} decode_clean_false={sum(1 for u in measurement.unreadable if not u.decode_clean)}')


def test_rg06_blur_applied(measurement, emit):
    from voice.adapters import real_ffmpeg_media_tool as tool_module
    assert (tool_module.BLUR_MIN_RADIUS, tool_module.LUMA_POWER) == (4, 1)
    tool, produced = _make_tool(measurement.sources, measurement.work_dir / 'blur')
    fixed = []
    for group, category in BLUR_GROUPS.items():
        for entry in measurement.entries[group]:
            result, regions = _forced_transform(measurement.bundle, tool, _artifact(entry), CENTER_REGION, category)
            assert result.status.value != 'failure', f'blur failed for {entry.id}: {result.warnings}'
            reduction = _region_reductions(entry.path, produced[result.processed_ref.ref], regions)[0]
            assert reduction is not None, f'no edges in region of {entry.id}'
            assert reduction >= BLUR_MIN_REDUCTION, f'blur reduction {reduction:.3f} < {BLUR_MIN_REDUCTION} for {entry.id}'
            fixed.append(reduction)
    detected = [r for item in measurement.results for r in item.reductions if r is not None]
    assert all(r >= BLUR_MIN_REDUCTION for r in detected), 'detector region blur below threshold'
    emit(c.report_line('RG-06', 'blur_applied', 'PASS'))
    detected_min = f'{min(detected):.3f}' if detected else 'n/a'
    emit(f'- blur_applied: luma_radius=min4 luma_power=1 fixed_region_images={len(fixed)} min_reduction={min(fixed):.3f} mean_reduction={sum(fixed) / len(fixed):.3f} detector_regions_measured={len(detected)} detector_min_reduction={detected_min}')


def test_rg06_failure_modes(measurement, emit):
    from voice.domain.image_safety import SafetyOutcome
    from voice.domain.image_transform import TransformStatus

    assert len(measurement.timeouts) == TIMEOUT_CASES
    assert _leaked(measurement.timeouts) == []
    for item in measurement.timeouts:
        assert item.failure_code is not None, item.id
        assert item.outcome == SafetyOutcome.DETECTION_FAILED.value, item.id
        assert item.kind == 'excluded', item.id
    assert len(measurement.transform_modes) >= MIN_PER_GROUP
    for mode in measurement.transform_modes:
        for failed in (mode.bad_sha, mode.tiny):
            assert failed.status is TransformStatus.FAILURE, mode.id
            assert failed.outcome is SafetyOutcome.TRANSFORM_FAILED, mode.id
            assert failed.processed_ref is None, mode.id
        assert mode.ok.outcome is not SafetyOutcome.SAFE, mode.id
    assert len(measurement.hits) == measurement.stack.vision.count
    for hit in measurement.hits:
        parts = urllib.parse.urlsplit(hit['url'])
        assert (parts.hostname, parts.port, parts.path) == (ROUTER_HOST, ROUTER_PORT, '/v1/chat/completions'), parts.path
    emit(c.report_line('RG-06', 'failure_modes', 'PASS'))
    emit(f'- failure_modes: timeout_1ms_cases={len(measurement.timeouts)} timeout_codes={_ascii(json.dumps(_tally(i.failure_code for i in measurement.timeouts)))} transform_images={len(measurement.transform_modes)} bad_sha_failed={len(measurement.transform_modes)} tiny_region_failed={len(measurement.transform_modes)} normal_transform={_ascii(json.dumps(_tally(m.ok.status.value for m in measurement.transform_modes)))} route_hits={len(measurement.hits)}')


def test_rg06_detection_rate_recorded(measurement, emit):
    parts = []
    for group in DETECTED_GROUPS:
        items = _by_group(measurement, group)
        assert len(items) == PER_GROUP, group
        flagged = sum(1 for i in items if i.outcome == 'TRANSFORM_REQUIRED')
        rate = flagged / len(items)
        assert 0.0 <= rate <= 1.0
        cats = _tally(cat for i in items for cat in i.categories)
        parts.append(f'{group}={flagged}/{len(items)} categories={_ascii(json.dumps(cats))}')
    calls = measurement.stack.vision.count
    assert calls <= CALL_CAP
    total = measurement.guard.spent()
    measurement.guard.check()
    seconds = [i.seconds for i in measurement.results]
    emit(c.report_line('RG-06', 'detection_rate_recorded', 'PASS'))
    emit('- detection_rate_recorded: flagged_by_group ' + ' '.join(parts) + f' (chi ghi so do, khong tuyen bo nguong) vision_calls={calls} cap={CALL_CAP} ledger_total={total} USD max_seconds={max(seconds):.1f}')


def test_rg06_secret_scan(measurement, emit):
    assert measurement.stack.store.current_version(measurement.stack.secret_ref) is not None
    text = REPORT.read_text(encoding='utf-8') if REPORT.is_file() else ''
    assert c.scan_secrets(text) == []
    assert 'data:image' not in text and '![' not in text
    assert re.search(r'[A-Za-z0-9+/]{200,}', text) is None, 'base64-like blob in report'
    stray = [p.name for p in REPORT_DIR.glob('*') if p.name != 'report.md'] if REPORT_DIR.is_dir() else []
    assert stray == [], f'unexpected files in evidence dir: {stray}'
    emit(c.report_line('RG-06', 'secret_scan', 'PASS'))
    emit(f'- secret_scan: match_count=0 embedded_images=0 report_present={REPORT.is_file()}')


def test_rg06_per_image_diagnostics(measurement, emit):
    assert len(measurement.results) == len(DETECTED_GROUPS) * PER_GROUP
    for item in measurement.results:
        cats = ','.join(item.categories) or '-'
        emit(f'- diag {item.id}: outcome={item.outcome} confidence={item.confidence} categories={cats} regions={item.regions} final={item.final}')

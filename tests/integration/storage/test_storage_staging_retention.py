"""STAGING-RETENTION: staging của job đã hoàn tất được dời sang thùng rác theo retention đã duyệt (CT-STO-007, CT-STO-008, ADR-0010, C5, D8-I-06).

Đầu ra out/<id>.mp4 và bản phẳng <staging>/<artifact_version_id> rời staging khi job COMPLETED có location cloud VERIFIED; giọng per_video rời
sau retention.temporary (24 giờ); media/, audio_library/ và tệp lạ không bao giờ bị chạm. Tệp được dời (không xoá) sau khi kiểm kích thước và
SHA-256, có dòng trong retired.jsonl, và lượt sau không làm gì thêm. CSDL được thay bằng một kết nối giả chỉ trả lời đúng câu SELECT của gói,
nên không cần PostgreSQL, Temporal hay mạng.

coveredIds: CT-STO-007, CT-STO-008
"""
from __future__ import annotations

import ast
import errno
import hashlib
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_PATH = ROOT / 'tools' / 'launcher' / 'launcher.py'
TOOL_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'retire_staging.py'
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
WS = '00000000-0000-0000-0000-00000000a001'
NOW = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
POLICY_PARAMETERS = {
    'retention.output': {'policy': 'keep_forever', 'local_cleanup': 'only_after_cloud_verified'},
    'retention.temporary': {'delete_after_hours': 24, 'counted_from': 'checked_and_completed'},
}


def _module():
    from controlplane.infrastructure.storage import staging_retention
    return staging_retention


def _write(root: Path, relative: str, data: bytes) -> str:
    path = root.joinpath(*relative.split('/'))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


class Job:
    """Một job đã hoàn tất với đầu ra, bản phẳng của đầu ra, giọng, bản phẳng của giọng và tệp tạm cùng byte của giọng."""

    def __init__(self, staging: Path, name: str, completed_at: datetime, *, cloud_verified: bool = True) -> None:
        self.job_id = 'job-' + name
        self.completed_at = completed_at
        self.cloud_verified = cloud_verified
        self.output_bytes = ('video ' + name).encode() * 50
        self.voice_bytes = ('voice ' + name).encode() * 40
        self.output_sha = hashlib.sha256(self.output_bytes).hexdigest()
        self.voice_sha = hashlib.sha256(self.voice_bytes).hexdigest()
        self.output_version = str(uuid.uuid5(uuid.NAMESPACE_URL, 'out-' + name))
        self.voice_version = str(uuid.uuid5(uuid.NAMESPACE_URL, 'voice-' + name))
        self.output_ref = f'out/pkg-{name}.mp4'
        self.voice_ref = f'voice/voice-artifact-{self.voice_sha}'
        self.voice_tmp = f'voice/tmp/{self.voice_sha}.wav'
        for relative, data in ((self.output_ref, self.output_bytes), (self.output_version, self.output_bytes),
                               (self.voice_ref, self.voice_bytes), (self.voice_version, self.voice_bytes), (self.voice_tmp, self.voice_bytes)):
            _write(staging, relative, data)

    @property
    def paths(self) -> tuple[str, ...]:
        return (self.output_ref, self.output_version, self.voice_ref, self.voice_version, self.voice_tmp)

    def db_rows(self) -> list[tuple]:
        return [
            (self.job_id, self.completed_at, self.output_version, self.output_ref, self.output_sha, len(self.output_bytes), 'output', self.cloud_verified),
            (self.job_id, self.completed_at, self.voice_version, self.voice_ref, self.voice_sha, len(self.voice_bytes), 'per_video', False),
        ]


class FakeConnection:
    """Kết nối giả: chỉ nhận đúng RETENTION_SQL với 11 tham số theo thứ tự, mọi câu khác làm test hỏng."""

    def __init__(self, rows: list[tuple], seen: list) -> None:
        self._rows = rows
        self._seen = seen

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        assert sql == _module().RETENTION_SQL, sql
        assert len(params) == 11 and sql.count('%s') == 11, params
        self._seen.append(params)
        rows = self._rows

        class Cursor:
            def fetchall(self):
                return list(rows)

        return Cursor()


def _factory(rows: list[tuple], seen: list):
    return lambda: FakeConnection(rows, seen)


def _layout(tmp_path: Path):
    data = tmp_path / 'data'
    staging = data / 'staging'
    staging.mkdir(parents=True)
    return data, staging


def _sweeper(staging: Path, trash: Path, rows: list[tuple], seen: list, **kw):
    m = _module()
    policy = m.RetentionPolicy.from_parameters(POLICY_PARAMETERS)
    return m.StagingRetentionSweeper(_factory(rows, seen), WS, staging, trash, policy, lambda: NOW, **kw)


def test_completed_job_output_and_voice_move_to_trash_with_manifest_and_a_second_sweep_does_nothing(tmp_path):
    data, staging = _layout(tmp_path)
    trash = data / 'trash' / 'staging'
    done = Job(staging, 'done', NOW - timedelta(hours=30))
    seen: list = []
    report = _sweeper(staging, trash, done.db_rows(), seen).run_once()
    assert report.moved == 5 and report.outcomes == {'MOVED': 5} and not report.stopped_by_cap
    day = trash / '20261103'
    for relative in done.paths:
        assert not staging.joinpath(*relative.split('/')).exists(), relative
        assert day.joinpath(*relative.split('/')).is_file(), relative
    lines = [json.loads(line) for line in (day / 'retired.jsonl').read_text(encoding='utf-8').splitlines()]
    assert sorted(item['relative_path'] for item in lines) == sorted(done.paths)
    assert {item['reason'] for item in lines} == {'OUTPUT_CLOUD_VERIFIED', 'PER_VIDEO_AFTER_HOURS'}
    assert all(item['job_id'] == done.job_id and len(item['sha256']) == 64 for item in lines)
    assert seen[0][3] == WS and seen[0][8] == WS and seen[0][5] == NOW - timedelta(hours=168)
    again = _sweeper(staging, trash, done.db_rows(), seen).run_once()
    assert again.moved == 0 and again.outcomes == {'ABSENT': 5}
    assert len((day / 'retired.jsonl').read_text(encoding='utf-8').splitlines()) == 5


def test_unverified_output_recent_voice_media_library_and_unknown_files_stay(tmp_path):
    data, staging = _layout(tmp_path)
    trash = data / 'trash' / 'staging'
    unsynced = Job(staging, 'unsynced', NOW - timedelta(hours=30), cloud_verified=False)
    recent = Job(staging, 'recent', NOW - timedelta(hours=2))
    kept = {
        'media/' + 'a' * 64 + '.png': b'image',
        'audio_library/catalog/music_sources.json': b'{}',
        'audio_library/bed-none-' + 'b' * 64 + '.wav': b'bed',
        'music-' + 'c' * 64 + '.wav': b'music',
        'd' * 64 + '.ass': b'subtitle',
        'out/failed-job.mp4': b'qc failed render',
    }
    for relative, payload in kept.items():
        _write(staging, relative, payload)
    media_version = str(uuid.uuid4())
    media_sha = _write(staging, media_version, b'image')
    rows = unsynced.db_rows() + recent.db_rows() + [
        ('job-recent', NOW - timedelta(hours=30), media_version, 'media/' + 'a' * 64 + '.png', media_sha, 5, 'per_video', False),
        ('job-recent', NOW - timedelta(hours=30), media_version, 'media/' + 'a' * 64 + '.png', media_sha, 5, 'output', True),
    ]
    m = _module()
    plan = m.plan_retention(m.read_retention_rows(_factory(rows, []), WS, None), m.RetentionPolicy.from_parameters(POLICY_PARAMETERS), NOW)
    assert dict(plan.deferred) == {'CLOUD_NOT_VERIFIED': 1, 'WAITING_TEMPORARY_HOURS': 1, 'ROW_NOT_ALLOWED': 2}
    assert sorted(item.relative_path for item in plan.items) == sorted([recent.output_ref, recent.output_version, unsynced.voice_ref, unsynced.voice_version, unsynced.voice_tmp])
    report = _sweeper(staging, trash, rows, []).run_once()
    assert report.moved == 5
    for relative in (unsynced.output_ref, unsynced.output_version, recent.voice_ref, recent.voice_version, recent.voice_tmp, media_version, *kept):
        assert staging.joinpath(*relative.split('/')).is_file(), relative


def test_bytes_that_differ_from_the_registered_version_stay_and_disabled_policy_moves_nothing(tmp_path):
    data, staging = _layout(tmp_path)
    trash = data / 'trash' / 'staging'
    job = Job(staging, 'edited', NOW - timedelta(hours=30))
    target = staging / 'out' / 'pkg-edited.mp4'
    target.write_bytes(b'X' * len(job.output_bytes))
    m = _module()
    off = m.RetentionPolicy.from_parameters({'retention.output': {'local_cleanup': 'never'}, 'retention.temporary': {'delete_after_hours': 24, 'counted_from': 'created'}})
    assert off == m.RetentionPolicy(False, None) and not off.enabled
    seen: list = []
    disabled = m.StagingRetentionSweeper(_factory(job.db_rows(), seen), WS, staging, trash, off, lambda: NOW).run_once()
    assert disabled.moved == 0 and seen == []
    report = _sweeper(staging, trash, job.db_rows(), []).run_once()
    assert report.outcomes == {'HASH_MISMATCH': 1, 'MOVED': 4}
    assert target.read_bytes() == b'X' * len(job.output_bytes)


def test_each_sweep_is_capped_and_trash_inside_staging_or_escaping_paths_are_refused(tmp_path):
    data, staging = _layout(tmp_path)
    trash = data / 'trash' / 'staging'
    jobs = [Job(staging, f'cap{i}', NOW - timedelta(hours=30)) for i in range(3)]
    rows = [row for job in jobs for row in job.db_rows()]
    sweeps = [_sweeper(staging, trash, rows, [], max_files=4).run_once() for _ in range(5)]
    assert [s.moved for s in sweeps] == [4, 4, 4, 3, 0]
    assert [s.stopped_by_cap for s in sweeps] == [True, True, True, False, False]
    by_bytes = _sweeper(staging, trash, rows, [], max_bytes=1).run_once()
    assert by_bytes.moved == 0 and by_bytes.outcomes == {'ABSENT': 15}
    big = Job(staging, 'bytes', NOW - timedelta(hours=30))
    capped = _sweeper(staging, trash, big.db_rows(), [], max_bytes=1).run_once()
    assert capped.moved == 1 and capped.stopped_by_cap
    jobs.append(big)
    while _sweeper(staging, trash, big.db_rows(), []).run_once().moved:
        pass
    assert not any(staging.joinpath(*p.split('/')).exists() for job in jobs for p in job.paths)
    m = _module()
    with pytest.raises(ValueError):
        m.retire_items((), staging_root=staging, trash_root=staging / 'trash', now=NOW)
    outside = m.RetireItem('../escape.mp4', 'e' * 64, 1, 'job', str(uuid.uuid4()), 'OUTPUT_CLOUD_VERIFIED')
    report = m.retire_items((outside,), staging_root=staging, trash_root=trash, now=NOW)
    assert report.outcomes == {'PATH_REJECTED': 1}


def test_cross_volume_move_copies_checks_and_then_removes_the_source(tmp_path):
    data, staging = _layout(tmp_path)
    trash = tmp_path / 'other-volume' / 'WILL_DELETE'
    job = Job(staging, 'cross', NOW - timedelta(hours=30))
    m = _module()
    plan = m.plan_retention(m.read_retention_rows(_factory(job.db_rows(), []), WS, None), m.RetentionPolicy.from_parameters(POLICY_PARAMETERS), NOW)

    def replace(source, dest):
        if Path(source).parent.resolve() != Path(dest).parent.resolve():
            raise OSError(errno.EXDEV, 'not the same device')
        Path(source).replace(dest)

    report = m.retire_items(plan.items, staging_root=staging, trash_root=trash, now=NOW, replace=replace)
    assert report.outcomes == {'MOVED': 5}
    moved = trash / '20261103' / 'out' / 'pkg-cross.mp4'
    assert moved.read_bytes() == job.output_bytes and not (staging / 'out' / 'pkg-cross.mp4').exists()
    assert not list(trash.rglob('*.part'))


def test_policy_of_the_production_profile_is_the_approved_one():
    m = _module()
    values = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))['retention']
    policy = m.RetentionPolicy.from_parameters({'retention.output': values['output']['value'], 'retention.temporary': values['temporary']['value']})
    assert policy == m.RetentionPolicy(True, 24)
    sql = m.RETENTION_SQL
    assert sql.lstrip().upper().startswith('SELECT') and sql.count('%') == sql.count('%s') == 11
    assert not any(word in sql.upper() for word in ('INSERT ', 'UPDATE ', 'DELETE ', 'DROP ', 'ALTER '))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_start_worker_runs_the_retention_sweeper_beside_the_relays(tmp_path):
    launcher = _load('staging_retention_launcher', LAUNCHER_PATH)
    source = LAUNCHER_PATH.read_text(encoding='utf-8')
    functions = {n.name: ast.get_source_segment(source, n) for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}
    body = functions['start_worker']
    assert 'retention = build_staging_retention(batch_connection, workspace_id, runtime, profile.parameters, clock)' in body
    assert 'background.append(asyncio.ensure_future(retention.run_forever(stop_event, STAGING_RETENTION_INTERVAL_SECONDS)))' in body
    assert launcher.STAGING_RETENTION_INTERVAL_SECONDS == 300.0
    staging = tmp_path / 'data' / 'staging'

    class Runtime:
        staging_root = staging

    connection_factory = object()
    sweeper = launcher.build_staging_retention(connection_factory, WS, Runtime(), POLICY_PARAMETERS, lambda: NOW, {})
    assert sweeper.staging_root == staging and sweeper.trash_root == tmp_path / 'data' / 'trash' / 'staging'
    assert sweeper.policy == _module().RetentionPolicy(True, 24)
    override = tmp_path / 'elsewhere'
    chosen = launcher.build_staging_retention(connection_factory, WS, Runtime(), POLICY_PARAMETERS, lambda: NOW, {'AIAVC_STAGING_TRASH_DIR': str(override)})
    assert chosen.trash_root == override

    class NoStaging:
        pass

    assert launcher.build_staging_retention(connection_factory, WS, NoStaging(), POLICY_PARAMETERS, lambda: NOW, {}) is None


def test_one_off_tool_dry_run_moves_nothing_and_apply_moves_only_completed_synced_files(tmp_path):
    tool = _load('staging_retention_tool', TOOL_PATH)
    data, staging = _layout(tmp_path)
    job = Job(staging, 'old', NOW - timedelta(days=20))
    pending = Job(staging, 'pending', NOW - timedelta(days=20), cloud_verified=False)
    rows = job.db_rows() + pending.db_rows()
    seen: list = []
    environ = {'AIAVC_DATA_DIR': str(data)}

    def run(*argv):
        lines: list[str] = []
        code = tool.main(list(argv), environ=environ, out=lines.append, err=lines.append,
                         database=lambda layout: (_factory(rows, seen), WS), clock=lambda: NOW)
        return code, lines

    code, lines = run()
    assert code == 0 and 'sẽ dời: 8 tệp' in '\n'.join(lines) and 'hoãn CLOUD_NOT_VERIFIED: 1 version' in lines
    assert all(staging.joinpath(*p.split('/')).is_file() for p in job.paths + pending.paths)
    assert seen[-1][5] == datetime(1970, 1, 1, tzinfo=timezone.utc)
    trash = tmp_path / 'WILL_DELETE' / 'aiavc-staging'
    code, lines = run('--apply', '--trash', str(trash))
    assert code == 0 and 'kết quả MOVED: 8 tệp' in lines
    assert not any(staging.joinpath(*p.split('/')).exists() for p in job.paths)
    assert staging.joinpath(*pending.output_ref.split('/')).is_file()
    assert (trash / '20261103' / 'retired.jsonl').is_file()
    assert run('--trash', 'relative')[0] == 2 and run('--delete')[0] == 2

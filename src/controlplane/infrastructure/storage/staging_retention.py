"""STAGING-RETENTION: dời tệp staging của job đã hoàn tất sang thùng rác cục bộ theo chính sách retention đã duyệt (CT-STO-007, CT-STO-008).

Chính sách lấy từ profile production (basis DECIDED; C5 và D8-I-06 của docs/implementation/adapt/plan.md mục 7.5 và docs/implementation/i/plan.md;
ADR-0006, ADR-0010, FR-SYN-002, FR-SYN-004, FR-SYN-007):
- retention.output.local_cleanup = only_after_cloud_verified: video đầu ra out/<render_package_id>.mp4 và bản phẳng <staging>/<artifact_version_id>
  của nó rời staging khi job COMPLETED có dòng cp_completion_ledger và version đó có location cloud VERIFIED kèm bằng chứng xác minh;
- retention.temporary = delete_after_hours (24) tính từ checked_and_completed: version per_video của job (giọng voice/voice-artifact-<sha256>,
  bản phẳng của nó và voice/tmp/<sha256>.wav cùng byte) rời staging khi completed_at đã qua đủ số giờ đó;
- media/, audio_library/, illustrations/, nhạc và phụ đề ở gốc staging, tệp của job chưa hoàn tất hay FAILED_FINAL không bao giờ bị chạm.
Giá trị profile khác các giá trị trên thì phần tương ứng tắt (đóng an toàn).

Dời, không xoá: mỗi tệp phải là tệp thường dưới staging (resolve_staging_path), có đúng kích thước và SHA-256 của version đã đăng ký, rồi mới
chuyển sang <trash>/<YYYYMMDD>/<đường dẫn tương đối> và ghi một dòng JSON vào <trash>/<YYYYMMDD>/retired.jsonl. Khác ổ đĩa thì chép sang
tệp .part, kiểm SHA-256 bản chép, đổi tên rồi mới gỡ bản gốc. CSDL chỉ được đọc (một câu SELECT). Mỗi lượt dời tối đa MAX_FILES_PER_SWEEP tệp
và MAX_BYTES_PER_SWEEP byte; tệp đã dời thì lượt sau thấy vắng và bỏ qua, nên chạy lại không làm gì thêm.
"""
from __future__ import annotations

import asyncio
import errno
import hashlib
import json
import logging
import os
import re
import shutil
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

from controlplane.infrastructure.storage.staging_paths import StagingPathError, resolve_staging_path

_LOG = logging.getLogger(__name__)

ROLE_OUTPUT = 'output'
ROLE_PER_VIDEO = 'per_video'
OUTPUT_PREFIX = 'out/'
OUTPUT_SUFFIX = '.mp4'
VOICE_TMP_DIR = 'voice/tmp'
OUTPUT_LOCAL_CLEANUP = 'only_after_cloud_verified'
TEMPORARY_COUNTED_FROM = 'checked_and_completed'
PER_VIDEO_RETENTION = 'per_video'
CLOUD_BACKEND = 'cloud'
CLOUD_VERIFIED_STATE = 'VERIFIED'
COMPLETED_JOB_STATUS = 'COMPLETED'
SWEEP_LOOKBACK_HOURS = 168
MAX_FILES_PER_SWEEP = 200
MAX_BYTES_PER_SWEEP = 4 * 1024 * 1024 * 1024
MANIFEST_NAME = 'retired.jsonl'
TRASH_DIR_ENV = 'AIAVC_STAGING_TRASH_DIR'
REASON_OUTPUT = 'OUTPUT_CLOUD_VERIFIED'
REASON_PER_VIDEO = 'PER_VIDEO_AFTER_HOURS'
_EPOCH_START = datetime(1970, 1, 1, tzinfo=timezone.utc)
_WINDOWS_NOT_SAME_DEVICE = 17
_CHUNK = 1 << 20
_SHA256 = re.compile('[0-9a-f]{64}')
_UUID = re.compile('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
_OUTPUT_NAME = re.compile('out/[A-Za-z0-9][A-Za-z0-9._-]{0,200}[.]mp4')
_VOICE_ARTIFACT = re.compile('voice/voice-artifact-([0-9a-f]{64})')

# Một câu SELECT duy nhất, tham số %s theo thứ tự của _sql_params: đầu ra của job COMPLETED (kèm cờ cloud VERIFIED) và version per_video
# mà job đó sở hữu (owner_ref là job_id). Không ghi gì vào CSDL.
RETENTION_SQL = (
    'SELECT l.job_id, l.completed_at, v.artifact_version_id::text, v.artifact_id, v.sha256_hash, v.size_bytes, CAST(%s AS text) AS role, '
    'EXISTS (SELECT 1 FROM controlplane.cp_artifact_locations c WHERE c.workspace_id = v.workspace_id '
    'AND c.artifact_version_id = v.artifact_version_id AND c.backend_ref = %s AND c.state = %s '
    'AND c.verification_evidence_ref IS NOT NULL AND (c.observed_hash IS NULL OR c.observed_hash = v.sha256_hash)) AS cloud_verified '
    'FROM controlplane.cp_completion_ledger l '
    'JOIN controlplane.cp_video_jobs j ON j.workspace_id = l.workspace_id AND j.job_id = l.job_id '
    'JOIN controlplane.cp_artifact_versions v ON v.workspace_id = l.workspace_id AND v.artifact_version_id = l.output_artifact_version_id '
    'WHERE l.workspace_id = %s AND j.status = %s AND l.completed_at >= %s '
    'UNION ALL '
    'SELECT l.job_id, l.completed_at, v.artifact_version_id::text, v.artifact_id, v.sha256_hash, v.size_bytes, CAST(%s AS text) AS role, '
    'FALSE AS cloud_verified '
    'FROM controlplane.cp_completion_ledger l '
    'JOIN controlplane.cp_video_jobs j ON j.workspace_id = l.workspace_id AND j.job_id = l.job_id '
    'JOIN controlplane.cp_artifact_versions v ON v.workspace_id = l.workspace_id AND v.owner_ref = l.job_id AND v.retention_ref = %s '
    'WHERE l.workspace_id = %s AND j.status = %s AND l.completed_at >= %s '
    'ORDER BY 2, 1, 3'
)


@dataclass(frozen=True)
class RetentionPolicy:
    output_after_cloud_verified: bool
    temporary_hours: int | None

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, Any]) -> RetentionPolicy:
        """Đọc retention.output và retention.temporary của profile; thiếu hay khác giá trị đã duyệt thì phần đó tắt."""
        source = parameters if isinstance(parameters, Mapping) else {}
        output = source.get('retention.output')
        temporary = source.get('retention.temporary')
        output_ok = isinstance(output, Mapping) and output.get('local_cleanup') == OUTPUT_LOCAL_CLEANUP
        hours = None
        if isinstance(temporary, Mapping) and temporary.get('counted_from') == TEMPORARY_COUNTED_FROM:
            value = temporary.get('delete_after_hours')
            if type(value) is int and value >= 0:
                hours = value
        return cls(output_ok, hours)

    @property
    def enabled(self) -> bool:
        return self.output_after_cloud_verified or self.temporary_hours is not None


@dataclass(frozen=True)
class RetentionRow:
    job_id: str
    completed_at: datetime
    role: str
    artifact_version_id: str
    artifact_id: str
    sha256: str
    size_bytes: int
    cloud_verified: bool


@dataclass(frozen=True)
class RetireItem:
    relative_path: str
    sha256: str
    size_bytes: int
    job_id: str
    artifact_version_id: str
    reason: str


@dataclass(frozen=True)
class RetentionPlan:
    items: tuple[RetireItem, ...]
    deferred: Mapping[str, int]


@dataclass(frozen=True)
class RetireReport:
    moved: int
    moved_bytes: int
    outcomes: Mapping[str, int]
    stopped_by_cap: bool


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _row_paths(row: RetentionRow) -> tuple[str, ...] | None:
    if not _UUID.fullmatch(str(row.artifact_version_id)) or not _SHA256.fullmatch(str(row.sha256)):
        return None
    if type(row.size_bytes) is not int or row.size_bytes <= 0:
        return None
    if row.role == ROLE_OUTPUT:
        if not _OUTPUT_NAME.fullmatch(row.artifact_id):
            return None
        return (row.artifact_id, row.artifact_version_id)
    if row.role == ROLE_PER_VIDEO:
        match = _VOICE_ARTIFACT.fullmatch(row.artifact_id)
        if match is None:
            return None
        paths = [row.artifact_id, row.artifact_version_id]
        if match.group(1) == row.sha256:
            paths.append(f'{VOICE_TMP_DIR}/{row.sha256}.wav')
        return tuple(paths)
    return None


def plan_retention(rows: Iterable[RetentionRow], policy: RetentionPolicy, now: datetime) -> RetentionPlan:
    """Hàm thuần: từ các dòng đọc được, chọn đường dẫn tương đối được dời và đếm lý do hoãn theo version."""
    if not _aware(now):
        raise ValueError('now must be timezone-aware')
    items: list[RetireItem] = []
    seen: set[str] = set()
    deferred: Counter[str] = Counter()
    for row in rows:
        paths = _row_paths(row)
        if paths is None or not _aware(row.completed_at):
            deferred['ROW_NOT_ALLOWED'] += 1
            continue
        if row.role == ROLE_OUTPUT:
            if not policy.output_after_cloud_verified:
                deferred['OUTPUT_POLICY_DISABLED'] += 1
                continue
            if row.cloud_verified is not True:
                deferred['CLOUD_NOT_VERIFIED'] += 1
                continue
            reason = REASON_OUTPUT
        else:
            if policy.temporary_hours is None:
                deferred['TEMPORARY_POLICY_DISABLED'] += 1
                continue
            if now < row.completed_at + timedelta(hours=policy.temporary_hours):
                deferred['WAITING_TEMPORARY_HOURS'] += 1
                continue
            reason = REASON_PER_VIDEO
        for relative in paths:
            if relative in seen:
                continue
            seen.add(relative)
            items.append(RetireItem(relative, row.sha256, row.size_bytes, row.job_id, row.artifact_version_id, reason))
    return RetentionPlan(tuple(items), MappingProxyType(dict(deferred)))


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(_CHUNK), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _overlaps(first: Path, second: Path) -> bool:
    a, b = first.resolve(), second.resolve()
    return a == b or a.is_relative_to(b) or b.is_relative_to(a)


def _free_destination(dest: Path) -> Path:
    if not dest.exists():
        return dest
    for index in range(1, 1000):
        candidate = dest.with_name(f'{dest.name}.{index}')
        if not candidate.exists():
            return candidate
    raise OSError(errno.EEXIST, 'no free destination name')


def _cross_device(exc: OSError) -> bool:
    return exc.errno == errno.EXDEV or getattr(exc, 'winerror', None) == _WINDOWS_NOT_SAME_DEVICE


def _move(source: Path, dest: Path, sha256: str, replace: Callable[[Path, Path], Any]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        replace(source, dest)
        return
    except OSError as exc:
        if not _cross_device(exc):
            raise
    part = dest.with_name(dest.name + '.part')
    shutil.copyfile(source, part)
    if _sha256_of(part) != sha256:
        part.unlink()
        raise OSError(errno.EIO, 'copied bytes differ from the registered version')
    os.replace(part, dest)
    source.unlink()


def _append_manifest(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(dict(record), sort_keys=True, ensure_ascii=True) + '\n')


def retire_items(
    items: Sequence[RetireItem],
    *,
    staging_root: Path,
    trash_root: Path,
    now: datetime,
    max_files: int | None = MAX_FILES_PER_SWEEP,
    max_bytes: int | None = MAX_BYTES_PER_SWEEP,
    dry_run: bool = False,
    replace: Callable[[Path, Path], Any] = os.replace,
) -> RetireReport:
    """Dời từng tệp đã kiểm sang thùng rác; dry_run chỉ kiểm sự có mặt và kích thước, không đọc nội dung, không dời gì."""
    staging, trash = Path(staging_root), Path(trash_root)
    if not staging.is_absolute() or not trash.is_absolute():
        raise ValueError('staging_root and trash_root must be absolute paths')
    if not _aware(now):
        raise ValueError('now must be timezone-aware')
    if _overlaps(staging, trash):
        raise ValueError('trash_root must lie outside staging_root')
    day_dir = trash / now.astimezone(timezone.utc).strftime('%Y%m%d')
    outcomes: Counter[str] = Counter()
    moved = moved_bytes = 0
    capped = False
    for item in items:
        try:
            source = resolve_staging_path(staging, item.relative_path)
        except StagingPathError:
            outcomes['PATH_REJECTED'] += 1
            continue
        if not source.exists():
            outcomes['ABSENT'] += 1
            continue
        if not source.is_file():
            outcomes['NOT_A_FILE'] += 1
            continue
        size = source.stat().st_size
        if size != item.size_bytes:
            outcomes['SIZE_MISMATCH'] += 1
            continue
        if (max_files is not None and moved >= max_files) or (max_bytes is not None and moved and moved_bytes + size > max_bytes):
            capped = True
            break
        if dry_run:
            outcomes['WOULD_MOVE'] += 1
            moved += 1
            moved_bytes += size
            continue
        try:
            if _sha256_of(source) != item.sha256:
                outcomes['HASH_MISMATCH'] += 1
                continue
            dest = _free_destination(day_dir.joinpath(*item.relative_path.split('/')))
            _move(source, dest, item.sha256, replace)
        except OSError:
            outcomes['MOVE_FAILED'] += 1
            continue
        _append_manifest(day_dir / MANIFEST_NAME, {
            'moved_at': now.astimezone(timezone.utc).isoformat(), 'relative_path': item.relative_path,
            'trash_path': dest.relative_to(trash).as_posix(), 'sha256': item.sha256, 'size_bytes': item.size_bytes,
            'job_id': item.job_id, 'artifact_version_id': item.artifact_version_id, 'reason': item.reason,
        })
        outcomes['MOVED'] += 1
        moved += 1
        moved_bytes += size
    return RetireReport(moved, moved_bytes, MappingProxyType(dict(outcomes)), capped)


def _sql_params(workspace_id: str, since: datetime) -> tuple[Any, ...]:
    return (
        ROLE_OUTPUT, CLOUD_BACKEND, CLOUD_VERIFIED_STATE, workspace_id, COMPLETED_JOB_STATUS, since,
        ROLE_PER_VIDEO, PER_VIDEO_RETENTION, workspace_id, COMPLETED_JOB_STATUS, since,
    )


def read_retention_rows(connection_factory: Callable[[], Any], workspace_id: str, since: datetime | None) -> tuple[RetentionRow, ...]:
    """Đọc các dòng ứng viên; since None là toàn bộ lịch sử (lệnh dọn một lần)."""
    start = _EPOCH_START if since is None else since
    with connection_factory() as connection:
        fetched = connection.execute(RETENTION_SQL, _sql_params(str(workspace_id), start)).fetchall()
    return tuple(
        RetentionRow(
            job_id=str(row[0]), completed_at=row[1], role=str(row[6]), artifact_version_id=str(row[2]), artifact_id=str(row[3]),
            sha256=str(row[4]), size_bytes=int(row[5]), cloud_verified=row[7] is True,
        )
        for row in fetched
    )


def resolve_trash_root(staging_root: Path, environ: Mapping[str, str]) -> Path:
    """Thùng rác: biến AIAVC_STAGING_TRASH_DIR (đường dẫn tuyệt đối), mặc định <thư mục cha của staging>/trash/staging."""
    override = str(environ.get(TRASH_DIR_ENV, '') or '').strip()
    if override:
        path = Path(override)
        if not path.is_absolute():
            raise ValueError(TRASH_DIR_ENV + ' must be an absolute path')
        return path
    return Path(staging_root).parent / 'trash' / 'staging'


class StagingRetentionSweeper:
    """Vòng nền của worker: mỗi lượt đọc ứng viên trong SWEEP_LOOKBACK_HOURS giờ gần nhất, lập kế hoạch và dời trong trần của lượt."""

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        workspace_id: str,
        staging_root: Path,
        trash_root: Path,
        policy: RetentionPolicy,
        clock: Callable[[], datetime],
        *,
        lookback_hours: int | None = SWEEP_LOOKBACK_HOURS,
        max_files: int | None = MAX_FILES_PER_SWEEP,
        max_bytes: int | None = MAX_BYTES_PER_SWEEP,
    ) -> None:
        self._connection_factory = connection_factory
        self._workspace_id = str(workspace_id)
        self.staging_root = Path(staging_root)
        self.trash_root = Path(trash_root)
        self.policy = policy
        self._clock = clock
        self._lookback_hours = lookback_hours
        self._max_files = max_files
        self._max_bytes = max_bytes
        if _overlaps(self.staging_root, self.trash_root):
            raise ValueError('trash_root must lie outside staging_root')

    def run_once(self) -> RetireReport:
        if not self.policy.enabled:
            return RetireReport(0, 0, MappingProxyType({}), False)
        now = self._clock()
        since = None if self._lookback_hours is None else now - timedelta(hours=self._lookback_hours)
        rows = read_retention_rows(self._connection_factory, self._workspace_id, since)
        plan = plan_retention(rows, self.policy, now)
        report = retire_items(plan.items, staging_root=self.staging_root, trash_root=self.trash_root, now=now,
                              max_files=self._max_files, max_bytes=self._max_bytes)
        if report.moved or report.outcomes.get('HASH_MISMATCH') or report.outcomes.get('MOVE_FAILED'):
            _LOG.info('staging retention: moved %s files (%s bytes); outcomes %s', report.moved, report.moved_bytes, dict(report.outcomes))
        return report

    async def run_forever(self, stop_event: asyncio.Event, interval_seconds: float) -> None:
        """Chờ một nhịp rồi chạy một lượt; lặp tới khi stop_event được đặt. Lỗi của một lượt chỉ được ghi log."""
        if interval_seconds <= 0:
            raise ValueError('interval_seconds must be positive')
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                return
            except asyncio.TimeoutError:
                pass
            try:
                await asyncio.to_thread(self.run_once)
            except Exception:
                _LOG.exception('staging retention cycle failed')


__all__ = [
    'MAX_BYTES_PER_SWEEP', 'MAX_FILES_PER_SWEEP', 'RETENTION_SQL', 'SWEEP_LOOKBACK_HOURS', 'TRASH_DIR_ENV', 'RetentionPlan', 'RetentionPolicy',
    'RetentionRow', 'RetireItem', 'RetireReport', 'StagingRetentionSweeper', 'plan_retention', 'read_retention_rows', 'resolve_trash_root',
    'retire_items',
]

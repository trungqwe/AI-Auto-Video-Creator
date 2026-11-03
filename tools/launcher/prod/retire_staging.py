"""Dọn một lần dữ liệu staging cũ của các job đã hoàn tất (STAGING-RETENTION): cùng chính sách và cùng mã với vòng nền của worker,
nhưng xét toàn bộ lịch sử thay vì SWEEP_LOOKBACK_HOURS giờ gần nhất.

Cách dùng (Control chạy dưới user thường; worker có thể đang chạy, chỉ job COMPLETED bị xét):
  python tools/launcher/prod/retire_staging.py                                    chạy khô: đọc CSDL và kích thước tệp, không đọc nội dung, không dời gì
  python tools/launcher/prod/retire_staging.py --apply [--max-files N] [--trash DIR]
--apply kiểm SHA-256 từng tệp với version đã đăng ký rồi mới dời, tối đa N tệp mỗi lần (mặc định DEFAULT_MAX_FILES), sang DIR (đường dẫn tuyệt đối)
hoặc thùng rác của worker (AIAVC_STAGING_TRASH_DIR, mặc định <AIAVC_DATA_DIR>/trash/staging). Mỗi tệp đã dời có một dòng trong
<trash>/<YYYYMMDD>/retired.jsonl để trả lại. Không in DSN, mật khẩu hay nội dung tệp; lỗi đối số không lặp lại đối số.
"""
from __future__ import annotations

import datetime
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

for _entry in (ROOT / 'src', ROOT / 'tools' / 'launcher'):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

import launcher  # noqa: E402
from controlplane.api.wiring.production_profile import load_production_profile  # noqa: E402
from controlplane.infrastructure.storage.staging_retention import (  # noqa: E402
    RetentionPolicy,
    plan_retention,
    read_retention_rows,
    resolve_trash_root,
    retire_items,
)

USAGE = 'Cách dùng: retire_staging.py [--apply] [--max-files N] [--trash DIR]'
EXIT_USAGE = 2
DEFAULT_MAX_FILES = 20000


def _parse(argv: Sequence[str]) -> tuple[bool, int, Path | None] | None:
    """Return (apply, max_files, trash) or None."""
    apply, max_files, trash = False, DEFAULT_MAX_FILES, None
    rest = list(argv)
    while rest:
        if rest[0] == '--apply' and not apply:
            apply, rest = True, rest[1:]
        elif rest[0] == '--max-files' and len(rest) >= 2 and rest[1].isdigit() and int(rest[1]) >= 1:
            max_files, rest = int(rest[1]), rest[2:]
        elif rest[0] == '--trash' and len(rest) >= 2 and Path(rest[1]).is_absolute() and trash is None:
            trash, rest = Path(rest[1]), rest[2:]
        else:
            return None
    return apply, max_files, trash


def build_database(layout: Any) -> tuple[Callable[[], Any], str]:
    """Kết nối chỉ đọc tới CSDL đang kích hoạt của launcher và workspace của identity."""
    import psycopg

    if not layout.password_file.is_file() or not layout.identity_file.is_file():
        raise launcher.LauncherError('Chưa có CSDL của launcher: chạy "launcher.py start" một lần trước khi dọn.')
    identity = launcher.load_or_create_identity(layout)
    dsn = launcher.build_dsn(launcher.load_or_create_password(layout), launcher.active_db_name(layout))
    return (lambda: psycopg.connect(dsn)), identity['workspace_id']


def _mib(value: int) -> str:
    return f'{value / (1024 * 1024):.1f} MiB'


def main(
    argv: Sequence[str] | None = None, *, environ: Mapping[str, str] | None = None, out: Callable[[str], None] = print,
    err: Callable[[str], None] | None = None, database: Callable[[Any], tuple[Callable[[], Any], str]] = build_database,
    clock: Callable[[], datetime.datetime] | None = None, replace: Callable[[Path, Path], Any] = os.replace,
) -> int:
    say_err = err or (lambda line: print(line, file=sys.stderr))
    parsed = _parse(sys.argv[1:] if argv is None else argv)
    if parsed is None:
        say_err(USAGE)
        return EXIT_USAGE
    apply, max_files, trash_arg = parsed
    env = os.environ if environ is None else environ
    try:
        layout = launcher.resolve_layout(env)
        policy = RetentionPolicy.from_parameters(load_production_profile(launcher.PROFILE_PATH).parameters)
        trash_root = trash_arg or resolve_trash_root(layout.staging_dir, env)
        connection_factory, workspace_id = database(layout)
        now = (clock or (lambda: datetime.datetime.now(datetime.timezone.utc)))()
        rows = read_retention_rows(connection_factory, workspace_id, None)
        plan = plan_retention(rows, policy, now)
        report = retire_items(plan.items, staging_root=layout.staging_dir, trash_root=trash_root, now=now, max_files=max_files,
                              max_bytes=None, dry_run=not apply, replace=replace)
    except Exception as exc:  # chỉ in tên lỗi: thông điệp của psycopg có thể mang DSN
        say_err(f'Không dọn được: {type(exc).__name__}')
        return 1
    out('chế độ: ' + (f'dời sang thùng rác {trash_root}' if apply else 'chạy khô, không dời gì'))
    out(f'chính sách: đầu ra sau khi cloud verified={policy.output_after_cloud_verified}; per_video sau {policy.temporary_hours} giờ')
    out(f'ứng viên: {len(rows)} version, {len(plan.items)} đường dẫn')
    for code, count in sorted(plan.deferred.items()):
        out(f'hoãn {code}: {count} version')
    for code, count in sorted(report.outcomes.items()):
        out(f'kết quả {code}: {count} tệp')
    out(('đã dời: ' if apply else 'sẽ dời: ') + f'{report.moved} tệp, {_mib(report.moved_bytes)}')
    if report.stopped_by_cap:
        out(f'dừng ở trần --max-files {max_files}; chạy lại để dời tiếp')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

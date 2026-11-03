"""Thu video hook (Pixabay), âm hook (Freesound SFX) vào kho hook của C và catalog nhạc nền (Freesound) cho AudioBedSource (HOOK-HARVEST, D1, D2 ngày 02/11/2026).

Cách dùng (Control chạy dưới user thường, sau khi user nhập khoá bằng set_stock_key.py):
  python tools/launcher/prod/harvest_media.py --probe                         (mỗi kho đúng một request tìm kiếm per_page 3, không tải)
  python tools/launcher/prod/harvest_media.py hooks [--per-query N] [--dry-run] (video hook Pixabay và âm hook Freesound vào CSDL của launcher)
  python tools/launcher/prod/harvest_media.py music [--per-mood N] [--dry-run]  (catalog nhạc <staging>/audio_library/catalog/music_sources.json)
  python tools/launcher/prod/harvest_media.py --status                        (số hook theo nguồn, số mục catalog, phiên bản khoá; không đọc khoá)
Khoá chỉ đọc từ kho DPAPI qua StockKeyCredentials và không bao giờ được in; lỗi đối số không lặp lại đối số. Mỗi lần chạy có trần request, lượt tải
và byte (stock_harvest.MAX_REQUESTS_PER_RUN, MAX_DOWNLOADS_PER_RUN, MAX_BYTES_PER_RUN) và chỉ tải từ CDN của kho (download_stock_file).
"""
from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

for _entry in (ROOT / 'src', ROOT / 'tools' / 'launcher'):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

import launcher  # noqa: E402
from controlplane.infrastructure.production_ports.stock_harvest import (  # noqa: E402
    DEFAULT_PER_MOOD,
    DEFAULT_PER_QUERY,
    MAX_PER_QUERY,
    FfmpegHookMedia,
    HarvestBudget,
    MeteredTransport,
    PostgresHookLibrary,
    catalog_path_for,
    harvest_hooks,
    harvest_music,
    probe_providers,
)
from controlplane.infrastructure.production_ports.stock_key_entry import STOCK_SECRET_REFS, StockKeyCredentials, StockKeyError, key_versions  # noqa: E402
from controlplane.infrastructure.production_ports.stock_media import FreesoundSearch, PixabayVideoSearch  # noqa: E402
from voice.adapters.audio_bed_source import load_music_catalog  # noqa: E402

USAGE = 'Cách dùng: harvest_media.py --probe | --status | hooks [--per-query N] [--dry-run] | music [--per-mood N] [--dry-run]'
EXIT_USAGE = 2
PROBE_BUDGET = (2, 0, 8 * 1024 * 1024)
DEFAULT_FFMPEG = 'C:/ffmpeg/bin/ffmpeg.exe'
DEFAULT_FFPROBE = 'C:/ffmpeg/bin/ffprobe.exe'


@dataclass
class HarvestServices:
    pixabay: Any
    freesound: Any
    transport: Any
    budget: HarvestBudget
    media: Any
    store: Any
    catalog_path: Path
    key_versions: Callable[[], Mapping[str, int | None]]
    close: Callable[[], None]


def _parse(argv: Sequence[str]) -> tuple[str, int | None, bool] | None:
    """Return (mode, count, dry_run) or None; mode is probe, status, hooks or music."""
    args = list(argv)
    if args in (['--probe'], ['--status']):
        return args[0][2:], None, False
    if not args or args[0] not in ('hooks', 'music'):
        return None
    mode, rest = args[0], args[1:]
    option = '--per-query' if mode == 'hooks' else '--per-mood'
    count, dry_run = (DEFAULT_PER_QUERY if mode == 'hooks' else DEFAULT_PER_MOOD), False
    while rest:
        if rest[0] == '--dry-run' and not dry_run:
            dry_run, rest = True, rest[1:]
        elif rest[0] == option and len(rest) >= 2 and rest[1].isdigit() and 1 <= int(rest[1]) <= MAX_PER_QUERY:
            count, rest = int(rest[1]), rest[2:]
        else:
            return None
    return mode, count, dry_run


def build_services(layout: Any, environ: Mapping[str, str], *, need_db: bool, budget: HarvestBudget) -> HarvestServices:
    """Production services: DPAPI keys, the pinned-address HTTPS transport of the music bed behind the run budget, pinned ffmpeg, the launcher database."""
    from controlplane.api.wiring.voice import ProductionHttpsTransport
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    vault = DpapiSecretStore(layout.vault_dir)
    keys = StockKeyCredentials(vault)
    transport = MeteredTransport(ProductionHttpsTransport(), budget)
    media = FfmpegHookMedia(environ.get('AIAVC_FFMPEG_PATH', DEFAULT_FFMPEG), environ.get('AIAVC_FFPROBE_PATH', DEFAULT_FFPROBE))
    manager, store = None, None
    if need_db:
        if not layout.password_file.is_file() or not layout.identity_file.is_file():
            raise launcher.LauncherError('Chưa có CSDL của launcher: chạy "launcher.py start" một lần trước khi thu.')
        from controlplane.infrastructure.db.uow import TransactionManager
        identity = launcher.load_or_create_identity(layout)
        manager = TransactionManager(launcher.build_dsn(launcher.load_or_create_password(layout), launcher.active_db_name(layout)), pool_max_size=2)
        store = PostgresHookLibrary(manager, workspace_id=identity['workspace_id'], staging_root=layout.staging_dir)
    return HarvestServices(
        pixabay=PixabayVideoSearch(transport=transport, keys=keys), freesound=FreesoundSearch(transport=transport, keys=keys), transport=transport,
        budget=budget, media=media, store=store, catalog_path=catalog_path_for(layout.staging_dir), key_versions=lambda: key_versions(vault),
        close=manager.close if manager is not None else (lambda: None))


def _run(mode: str, count: int | None, dry_run: bool, svc: HarvestServices, out: Callable[[str], None]) -> int:
    if mode == 'probe':
        lines = probe_providers(pixabay=svc.pixabay, freesound=svc.freesound)
        for line in lines:
            out(line)
        return 1 if any(': lỗi ' in line for line in lines) else 0
    if mode == 'status':
        for name, version in svc.key_versions().items():
            out(f'khoá {name}: ' + (f'{STOCK_SECRET_REFS[name]} v{version}' if version is not None else 'chưa có khoá'))
        for key, value in svc.store.count_by_source().items():
            out(f'hook {key}: {value}')
        out(f'catalog nhạc: {len(load_music_catalog(svc.catalog_path))} mục')
        return 0
    if mode == 'hooks':
        report = harvest_hooks(pixabay=svc.pixabay, freesound=svc.freesound, transport=svc.transport, media=svc.media, store=svc.store, per_query=count, dry_run=dry_run, budget=svc.budget)
    else:
        report = harvest_music(freesound=svc.freesound, transport=svc.transport, catalog_path=svc.catalog_path, per_mood=count, dry_run=dry_run, budget=svc.budget)
    for line in report.lines(svc.budget):
        out(line)
    return 1 if any(stop.endswith(('stock_key_missing', ':401', ':403')) for stop in report.stopped) else 0


def main(
    argv: Sequence[str] | None = None, *, environ: Mapping[str, str] | None = None, out: Callable[[str], None] = print,
    err: Callable[[str], None] | None = None, services: Callable[..., HarvestServices] = build_services,
) -> int:
    argv = sys.argv[1:] if argv is None else argv
    environ = os.environ if environ is None else environ
    err = err or (lambda line: print(line, file=sys.stderr))
    parsed = _parse(argv)
    if parsed is None:
        err('Lỗi: đối số không hợp lệ (đối số không được lặp lại).')
        err(USAGE)
        return EXIT_USAGE
    mode, count, dry_run = parsed
    svc = None
    try:
        layout = launcher.resolve_layout(environ)
        budget = HarvestBudget(*PROBE_BUDGET) if mode == 'probe' else HarvestBudget()
        svc = services(layout, environ, need_db=mode in ('status', 'hooks'), budget=budget)
        return _run(mode, count, dry_run, svc, out)
    except (launcher.LauncherError, StockKeyError) as exc:
        err(f'Lỗi: {exc}')
        return 1
    except Exception as exc:
        err(f'Lỗi: {type(exc).__name__} (chi tiết không in để không lộ khoá hay DSN)')
        return 1
    finally:
        if svc is not None:
            svc.close()


if __name__ == '__main__':
    raise SystemExit(main())

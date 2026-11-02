"""Nhập khoá API của Pixabay hoặc Freesound vào kho DPAPI của launcher (HOOK-KEYS, D1, D2 ngày 02/11/2026).

Cách dùng:
  python tools/launcher/prod/set_stock_key.py pixabay              (nhập khoá qua getpass, không hiện)
  python tools/launcher/prod/set_stock_key.py freesound --stdin    (đọc một dòng từ stdin)
  python tools/launcher/prod/set_stock_key.py pixabay --from-file <tệp>   (tệp do user chỉ định, đúng một dòng)
  python tools/launcher/prod/set_stock_key.py --status             (chỉ in phiên bản trong kho, không đọc khoá)
Freesound: dán "Client secret/Api key" (khoá dùng cho Authorization: Token), không dán Client id.
Khoá không bao giờ nhận qua đối số dòng lệnh và không bao giờ được in; lỗi đối số không lặp lại đối số.
"""
from __future__ import annotations

import getpass
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

for _entry in (ROOT / 'src', ROOT / 'tools' / 'launcher'):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

import launcher  # noqa: E402
from controlplane.infrastructure.production_ports.stock_key_entry import (  # noqa: E402
    STOCK_SECRET_REFS,
    StockKeyError,
    key_versions,
    read_key_file,
    run,
)
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore  # noqa: E402

USAGE = 'Cách dùng: set_stock_key.py {pixabay|freesound} [--stdin | --from-file <tệp>] | --status'
EXIT_USAGE = 2


def _parse(argv: Sequence[str]) -> tuple[str, str | None, str | None] | None:
    """Return (mode, provider, file) or None; mode is status, getpass, stdin or file."""
    args = list(argv)
    if args == ['--status']:
        return 'status', None, None
    if not args or args[0] not in STOCK_SECRET_REFS:
        return None
    provider, rest = args[0], args[1:]
    if not rest:
        return 'getpass', provider, None
    if rest == ['--stdin']:
        return 'stdin', provider, None
    if len(rest) == 2 and rest[0] == '--from-file' and rest[1]:
        return 'file', provider, rest[1]
    return None


def main(
    argv: Sequence[str] | None = None, *, environ: Mapping[str, str] | None = None,
    ask: Callable[[str], str] = getpass.getpass, stdin=None, out: Callable[[str], None] = print,
    err: Callable[[str], None] | None = None,
) -> int:
    argv = sys.argv[1:] if argv is None else argv
    environ = os.environ if environ is None else environ
    stdin = sys.stdin if stdin is None else stdin
    err = err or (lambda line: print(line, file=sys.stderr))
    parsed = _parse(argv)
    if parsed is None:
        err('Lỗi: đối số không hợp lệ (đối số không được lặp lại để không lộ khoá).')
        err(USAGE)
        return EXIT_USAGE
    mode, provider, file_name = parsed
    try:
        layout = launcher.resolve_layout(environ)
        if mode == 'status':
            for name, version in key_versions(DpapiSecretStore(layout.vault_dir)).items():
                out(f'{name}: ' + (f'{STOCK_SECRET_REFS[name]} v{version}' if version is not None else 'chưa có khoá'))
            return 0
        if mode == 'file':
            read_value = lambda: read_key_file(file_name)  # noqa: E731
        elif mode == 'stdin':
            read_value = lambda: stdin.readline()  # noqa: E731
        else:
            read_value = lambda: ask(f'Khoá {provider} (không hiện khi gõ): ')  # noqa: E731
        run(layout.vault_dir, provider, read_value, out)
    except (launcher.LauncherError, StockKeyError) as exc:
        err(f'Lỗi: {exc}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

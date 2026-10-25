"""Nhập khóa 9Router một lần vào kho DPAPI (PP-2); khóa chỉ nhập qua getpass, không nhận qua đối số dòng lệnh."""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PORTS_PATH = Path(__file__).resolve().with_name('ports.json')

for _entry in (ROOT / 'src', ROOT / 'tools' / 'launcher'):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

import launcher  # noqa: E402
from controlplane.infrastructure.production_ports.router_key_entry import run  # noqa: E402


def main() -> int:
    try:
        layout = launcher.resolve_layout(os.environ)
        run(layout.vault_dir, PORTS_PATH, getpass.getpass, print)
    except (launcher.LauncherError, ValueError) as exc:
        print(f'Lỗi: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

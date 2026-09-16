"""Production entrypoint for the loopback-only Control Plane service."""
from __future__ import annotations

import os
import sys

from controlplane.api.tls import serve_loopback_tls
from controlplane.infrastructure.db.uow import TransactionManager


def main() -> int:
    """Keep the P0 import/CLI contract; explicit `serve` runs the P7A listener."""
    if len(sys.argv) < 2 or sys.argv[1] != "serve":
        sys.stdout.write("AI Auto Video Creator - Control Plane v0.2.0\n")
        return 0
    dsn = os.environ.get("CONTROLPLANE_DSN")
    if not dsn:
        sys.stderr.write("CONTROLPLANE_DSN is required\n")
        return 2
    try:
        port = int(os.environ.get("CONTROLPLANE_PORT", "8443"))
    except ValueError:
        sys.stderr.write("CONTROLPLANE_PORT must be an integer\n")
        return 2
    if not 1 <= port <= 65535:
        sys.stderr.write("CONTROLPLANE_PORT must be within 1..65535\n")
        return 2
    manager = TransactionManager(dsn)
    try:
        serve_loopback_tls(manager=manager, port=port)
    finally:
        manager.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

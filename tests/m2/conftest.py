import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if not os.environ.get("M2_TEST_PG_DSN"):
    try:
        output = subprocess.check_output(
            ["docker", "port", "ai-auto-video-m2-pg", "5432/tcp"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        port = output.strip().split(":")[-1]
        os.environ["M2_TEST_PG_DSN"] = f"postgresql://m2test:m2test@127.0.0.1:{port}/postgres"
    except Exception:
        os.environ["M2_TEST_PG_DSN"] = "postgresql://m2test:m2test@127.0.0.1:57027/postgres"

_orig_subprocess_run = subprocess.run

def _wrapped_subprocess_run(*args, **kwargs):
    if len(args) > 0 and isinstance(args[0], list):
        cmd = list(args[0])
        if any('tests/m1' in str(x) or 'tests\\m1' in str(x) for x in cmd):
            if '-p' not in cmd:
                cmd.extend(['-o', 'pythonpath=. src', '-p', 'tests.m2.m1_regression_plugin'])
            args = (cmd, *args[1:])
    return _orig_subprocess_run(*args, **kwargs)

subprocess.run = _wrapped_subprocess_run

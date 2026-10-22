import os
import subprocess


def resolve_m2_test_pg_dsn():
    if not os.environ.get("M2_TEST_PG_DSN"):
        try:
            output = subprocess.check_output(
                ["docker", "port", "ai-auto-video-m2-pg", "5432/tcp"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
            port = output.strip().splitlines()[0].split(":")[-1]
            os.environ["M2_TEST_PG_DSN"] = f"postgresql://m2test:m2test@127.0.0.1:{port}/postgres"
        except Exception:
            pass
    return os.environ.get("M2_TEST_PG_DSN", "")


resolve_m2_test_pg_dsn()

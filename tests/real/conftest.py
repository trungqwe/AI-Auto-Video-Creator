"""CP7-1: tests/real chỉ được thu thập khi dòng lệnh nêu đường dẫn tới thư mục này."""
import sys
from pathlib import Path

import pytest

REAL_DIR = Path(__file__).resolve().parent
_TOOLS_REAL = REAL_DIR.parents[1] / 'tools' / 'real'
if str(_TOOLS_REAL) not in sys.path:
    sys.path.insert(0, str(_TOOLS_REAL))

import cp7_common  # noqa: E402


def pytest_ignore_collect(collection_path, config):
    try:
        Path(collection_path).resolve().relative_to(REAL_DIR)
    except ValueError:
        return None
    params = config.invocation_params
    if cp7_common.explicit_real_request(params.args, params.dir, REAL_DIR):
        return None
    return True


@pytest.fixture
def emit(capsys):
    """In một dòng bằng chứng ra terminal; từ chối dòng chứa mẫu bí mật."""
    def _emit(line):
        assert cp7_common.scan_secrets(line) == [], 'secret pattern in evidence line'
        with capsys.disabled():
            print(line, flush=True)
    return _emit

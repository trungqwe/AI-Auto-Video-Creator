"""Pytest fixtures for M1-P2 Temporal Proof tests."""
import sys
from pathlib import Path
import pytest
import pytest_asyncio
from temporalio.testing import WorkflowEnvironment

REPOSITORY_ROOT = Path(__file__).parents[3]
src_path = str(REPOSITORY_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

@pytest_asyncio.fixture(scope="module")
async def temporal_env():
    """Shared time-skipping workflow environment for module tests."""
    env = await WorkflowEnvironment.start_time_skipping()
    yield env
    await env.shutdown()

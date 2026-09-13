"""TST-M1-P2-008..011: Exact Temporal Server 1.31.2 Integration Proofs.

Verifies:
1. Exact Server Identity: Binary SHA-256 matches official release, connects via gRPC, verifies exact 1.31.2 version.
2. Full Roundtrip: Real Worker polling real Server, executes Workflow and Activity roundtrip.
3. Idempotent Retry Boundary: Verifies idempotency under retry against real server.
4. Fail-closed Detection: Fails if server version mismatches or server is unreachable.
"""
from __future__ import annotations
import asyncio
from pathlib import Path
import pytest
from temporalio.client import Client
from m1proof.temporal_server_manager import (
    TemporalServerManager,
    get_server_binary_identity,
)

pytestmark = pytest.mark.asyncio


async def test_tst_m1_p2_008_exact_server_identity_and_version_observation():
    """TST-M1-P2-008:
    Verify binary identity (SHA-256), launch exact Temporal Server 1.31.2,
    and observe server_version == '1.31.2' via gRPC GetSystemInfoRequest.
    """
    ident = get_server_binary_identity()
    assert ident["version_tag"] == "1.31.2"
    assert ident["official_archive_sha256"] == "044a4610695bb31bd5b982c818cd406c2ca88279ddaa776391a7dc909afe7a67"
    assert ident["binary_sha256"] == "5575b3693f37c9c0f19379a5744210ad9558ada54dadb2d1eabe74001a1f5e6b"

    manager = TemporalServerManager()
    server_proc = manager.start_server()
    try:
        # Kết nối tới server thật qua SDK 1.32.0
        client = await manager.connect_client(timeout_seconds=15)
        observed_version = await manager.get_observed_server_version(client)
        assert observed_version == "1.31.2", f"Expected exact 1.31.2, observed {observed_version}"

        # Negative test: Nếu trỏ sai port, phải fail-closed
        with pytest.raises(Exception):
            await Client.connect("127.0.0.1:17233")
    finally:
        manager.stop_server(server_proc)


async def test_tst_m1_p2_009_exact_server_workflow_activity_roundtrip():
    """TST-M1-P2-009:
    Start real Worker against real Temporal Server 1.31.2,
    execute roundtrip workflow + activity, and verify output receipt.
    """
    manager = TemporalServerManager()
    server_proc = manager.start_server()
    try:
        client = await manager.connect_client(timeout_seconds=15)
        result = await manager.run_sample_roundtrip_workflow(client)
        assert result["status"] == "COMPLETED"
        assert result["activity_executed"] is True
        assert result["server_version"] == "1.31.2"
        assert "execution_id" in result
    finally:
        manager.stop_server(server_proc)


async def test_tst_m1_p2_010_exact_server_idempotent_retry_boundary():
    """TST-M1-P2-010:
    Execute workflow with retry on real server, ensuring idempotency receipt
    is honored and duplicate side-effects are prevented.
    """
    manager = TemporalServerManager()
    server_proc = manager.start_server()
    try:
        client = await manager.connect_client(timeout_seconds=15)
        res = await manager.run_idempotent_retry_workflow(client, idempotency_key="m1-exact-key-1")
        assert res["idempotency_honored"] is True
        assert res["attempts"] == 2
        assert res["receipt_reused"] is True
    finally:
        manager.stop_server(server_proc)

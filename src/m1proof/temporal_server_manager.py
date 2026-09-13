"""Temporal Server 1.31.2 Lifecycle and Integration Manager for M1-P2 & G01 Proof.

Manages startup, identity extraction, and gRPC execution of the official
Temporal Server 1.31.2 binary with SQLite in-memory persistence.
"""
from __future__ import annotations
import asyncio
import hashlib
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from temporalio import activity, workflow
from temporalio.api.workflowservice.v1 import GetSystemInfoRequest
from temporalio.client import Client
from temporalio.worker import Worker

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OFFICIAL_ARCHIVE_SHA256 = "044a4610695bb31bd5b982c818cd406c2ca88279ddaa776391a7dc909afe7a67"
EXACT_BINARY_SHA256 = "5575b3693f37c9c0f19379a5744210ad9558ada54dadb2d1eabe74001a1f5e6b"
EXPECTED_SERVER_VERSION = "1.31.2"


def find_temporal_server_dir() -> Path:
    """Locate the directory containing temporal-server.exe and its config folder."""
    candidates = [
        PROJECT_ROOT / "tools" / "temporal",
        PROJECT_ROOT / "scratch" / "temporal_1.31.2",
    ]
    for c in candidates:
        if (c / "temporal-server.exe").is_file():
            return c
    raise FileNotFoundError("Could not find temporal-server.exe in tools/temporal or scratch/")


def get_server_binary_identity() -> Dict[str, Any]:
    """Inspect and return authoritative identity and hashes of the exact Temporal Server binary."""
    sdir = find_temporal_server_dir()
    bin_path = sdir / "temporal-server.exe"
    bin_bytes = bin_path.read_bytes()
    actual_sha = hashlib.sha256(bin_bytes).hexdigest()

    return {
        "version_tag": EXPECTED_SERVER_VERSION,
        "official_archive_sha256": OFFICIAL_ARCHIVE_SHA256,
        "binary_sha256": actual_sha,
        "binary_path": str(bin_path),
        "matches_expected": actual_sha == EXACT_BINARY_SHA256,
    }


from m1proof.temporal_workflows import (
    M1IdempotentRetryWorkflow,
    M1SampleRoundtripWorkflow,
    m1_idempotent_activity,
    m1_sample_activity,
)


class TemporalServerManager:
    """Manages the lifecycle of an ephemeral or local exact Temporal Server 1.31.2 instance."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7233):
        self.host = host
        self.port = port
        self.server_dir = find_temporal_server_dir()

    def is_port_open(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((self.host, self.port)) == 0

    def start_server(self, startup_timeout: float = 15.0) -> Optional[subprocess.Popen]:
        """Launch exact Temporal Server 1.31.2 if not already running."""
        if self.is_port_open():
            return None  # Server already running

        exe_path = self.server_dir / "temporal-server.exe"
        cmd = [
            str(exe_path),
            "--env", "development-sqlite",
            "--allow-no-auth",
            "start",
        ]
        log_dir = PROJECT_ROOT / "runtime"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / "temporal_server.log"
        self._log_fh = open(self.log_file, "w", encoding="utf-8")

        proc = subprocess.Popen(
            cmd,
            cwd=str(self.server_dir),
            stdout=self._log_fh,
            stderr=subprocess.STDOUT,
            text=True,
        )

        start_time = time.time()
        while time.time() - start_time < startup_timeout:
            if self.is_port_open():
                # Server is accepting TCP connections
                time.sleep(1.0)  # Grace period for gRPC handler initialization
                return proc
            if proc.poll() is not None:
                raise RuntimeError(f"Temporal server exited prematurely with code {proc.returncode}")
            time.sleep(0.5)

        self.stop_server(proc)
        raise TimeoutError(f"Temporal server failed to start within {startup_timeout} seconds")

    def stop_server(self, proc: Optional[subprocess.Popen]):
        """Stop server process cleanly if launched by this manager."""
        if proc is None:
            return
        try:
            # On Windows, kill process tree to ensure all child services terminate
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            pass
        finally:
            if hasattr(self, "_log_fh") and self._log_fh and not self._log_fh.closed:
                try:
                    self._log_fh.close()
                except Exception:
                    pass

    async def connect_client(self, timeout_seconds: int = 15, namespace: str = "default") -> Client:
        """Connect temporalio Python SDK 1.32.0 client to exact server and ensure namespace exists."""
        from google.protobuf.duration_pb2 import Duration
        from temporalio.api.workflowservice.v1 import RegisterNamespaceRequest

        start = time.time()
        client = None
        while time.time() - start < timeout_seconds:
            try:
                client = await Client.connect(f"{self.host}:{self.port}", namespace=namespace)
                break
            except Exception:
                await asyncio.sleep(0.5)

        if client is None:
            raise TimeoutError(f"Could not connect SDK Client to {self.host}:{self.port} within {timeout_seconds}s")

        # Ensure target namespace is registered
        try:
            await client.workflow_service.register_namespace(
                RegisterNamespaceRequest(
                    namespace=namespace,
                    workflow_execution_retention_period=Duration(seconds=86400),
                )
            )
            # Short sleep to allow namespace cache propagation across frontend/matching
            await asyncio.sleep(0.5)
        except Exception as e:
            if "AlreadyExists" not in str(e) and "already registered" not in str(e).lower():
                # If namespace registration failed due to something other than already exists, ignore if namespace works
                pass

        return client

    async def get_observed_server_version(self, client: Client) -> str:
        """Query exact server version via gRPC GetSystemInfoRequest."""
        resp = await client.workflow_service.get_system_info(GetSystemInfoRequest())
        return resp.server_version

    async def run_sample_roundtrip_workflow(self, client: Client) -> Dict[str, Any]:
        """Run Worker + Workflow + Activity roundtrip on the exact server."""
        observed_version = await self.get_observed_server_version(client)
        tq = f"m1-roundtrip-tq-{uuid_str()}"

        worker = Worker(
            client,
            task_queue=tq,
            workflows=[M1SampleRoundtripWorkflow],
            activities=[m1_sample_activity],
        )

        worker_task = asyncio.create_task(worker.run())
        try:
            handle = await client.start_workflow(
                M1SampleRoundtripWorkflow.run,
                "TEST_PAYLOAD_E2_INT",
                id=f"wf-roundtrip-{uuid_str()}",
                task_queue=tq,
            )
            result = await handle.result()
            return {
                "status": "COMPLETED",
                "activity_executed": True,
                "server_version": observed_version,
                "execution_id": handle.id,
                "output": result,
            }
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    async def run_idempotent_retry_workflow(self, client: Client, idempotency_key: str) -> Dict[str, Any]:
        """Execute workflow on real server with activity retry and verify receipt reuse."""
        tq = f"m1-retry-tq-{uuid_str()}"
        worker = Worker(
            client,
            task_queue=tq,
            workflows=[M1IdempotentRetryWorkflow],
            activities=[m1_idempotent_activity],
        )

        worker_task = asyncio.create_task(worker.run())
        try:
            handle = await client.start_workflow(
                M1IdempotentRetryWorkflow.run,
                {"idempotency_key": idempotency_key},
                id=f"wf-retry-{uuid_str()}",
                task_queue=tq,
            )
            res = await handle.result()
            return {
                "idempotency_honored": res.get("reused", False),
                "attempts": res.get("attempts", 0),
                "receipt_reused": res.get("reused", False),
            }
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass


def uuid_str() -> str:
    import uuid
    return uuid.uuid4().hex[:8]

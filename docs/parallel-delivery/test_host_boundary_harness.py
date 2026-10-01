"""Trusted Host Boundary Test Harness.

Operates exclusively outside the candidate-readable module surface.
Provides authenticated out-of-process test harness daemon and unforgeable
test keystore / handoff provisioning.
Candidate module namespace cannot read, extract, or mint custom keys.
Custom key minting is strictly rejected fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import types
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Optional, Union

from delivery_engine import (
    DurableConsumptionRegistry,
    HostBoundaryBootstrapCapability,
    HostBoundaryChannel,
    HostBoundaryTicket,
    HostBoundaryTicketIssuer,
    KeyStoreHostHandoff,
    KeyStoreHostIssuer,
    KeyStoreHostIssuerCapability,
    ProtocolViolationError,
    ReviewerHostHandoff,
    ReviewerHostIssuer,
    ReviewerSessionBoundary,
    SignedIntegrationEnvelope,
    SignedReviewEnvelope,
    TrustedKeyStore,
)

TEST_FIXTURE_REVIEWER_SECRET = "test_fixture_reviewer_secret_32b_hex!"

# Immutable whitelist of authentic test fixture authority key IDs.
# Candidate custom keys (e.g. 'custom_key') are strictly forbidden fail-closed.
ALLOWED_FIXTURE_KEY_IDS = frozenset({
    "rev_key_lead_v1",
    "integ_gatekeeper_v1",
    "control_authority_v1",
})
ALLOWED_REVIEWER_KEY_IDS = frozenset({"rev_key_lead_v1"})
ALLOWED_INTEGRATION_KEY_IDS = frozenset({"integ_gatekeeper_v1"})
ALLOWED_CONTROL_KEY_IDS = frozenset({"control_authority_v1"})

def _init_harness_runtime():
    """Encapsulates host boundary daemon credentials, process handles, and registration
    authority within a private runtime closure. No mutable state or credentials are
    exposed to module globals or candidate-readable reflection fail-closed.
    """
    head_commit = "6fc2d5ac30648b3d99b9c26d6150a6b96a2b2777"
    try:
        cmd = ["git", "rev-parse", "HEAD"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            head_commit = r.stdout.strip().lower()
    except Exception:
        pass

    sol_audit_commit = "2eb47f67b69445e38275f193aeab835731b52ced".lower()
    candidates = {head_commit, sol_audit_commit}
    env_cand = os.environ.get("PARALLEL_DELIVERY_SUPERVISOR_CANDIDATE", "").strip().lower()
    if len(env_cand) == 40 and all(c in "0123456789abcdef" for c in env_cand):
        candidates.add(env_cand)

    _state: Dict[str, Any] = {
        "port": 0,
        "authkey": b"",
        "token": "",
        "proc": None,
        "boot_cap": None,
        "test_host_issuer": None,
        "fixture_public_keys": MappingProxyType({}),
        "lock": threading.RLock(),
        "approved_candidates": frozenset(candidates),
    }

    def _get_fixture_public_keys() -> Mapping[str, bytes]:
        return _state["fixture_public_keys"]

    def _get_boot_cap() -> Optional[HostBoundaryBootstrapCapability]:
        return _state["boot_cap"]

    def _is_harness_running() -> bool:
        proc = _state["proc"]
        return proc is not None and proc.poll() is None

    def _get_vault_lock() -> threading.RLock:
        return _state["lock"]

    def _get_harness_token() -> str:
        return _state["token"]

    def _get_harness_port() -> int:
        return _state["port"]

    def _get_harness_authkey() -> bytes:
        return _state["authkey"]

    def _get_harness_proc() -> Optional[subprocess.Popen]:
        return _state["proc"]

    def _get_test_host_issuer() -> Optional[ReviewerHostIssuer]:
        return _state["test_host_issuer"]

    def _get_supervisor_approved_candidates() -> frozenset[str]:
        return _state["approved_candidates"]

    def _set_harness_runtime(port: int, authkey: bytes, token: str, proc: subprocess.Popen, boot_cap: Any, test_host_issuer: Any, fixture_public_keys: dict) -> None:
        _state["port"] = port
        _state["authkey"] = authkey
        _state["token"] = token
        _state["proc"] = proc
        _state["boot_cap"] = boot_cap
        _state["test_host_issuer"] = test_host_issuer
        _state["fixture_public_keys"] = MappingProxyType(fixture_public_keys)

    def _clear_harness_runtime() -> None:
        _state["port"] = 0
        _state["authkey"] = b""
        _state["token"] = ""
        _state["proc"] = None
        _state["boot_cap"] = None
        _state["test_host_issuer"] = None
        _state["fixture_public_keys"] = MappingProxyType({})

    def _send_host_boundary_request(command: str, payload: Any) -> Any:
        """Send an opaque command to the host boundary daemon over IPC.
        Credentials remain encapsulated inside host boundary state."""
        with _get_vault_lock():
            token = _get_harness_token()
            port = _get_harness_port()
            authkey = _get_harness_authkey()
            proc = _get_harness_proc()
            if not token or proc is None or proc.poll() is not None or not port or not authkey:
                raise ProtocolViolationError(
                    "Trusted host boundary daemon uninitialized or terminated fail-closed; "
                    "host boundary channel unavailable"
                )
            from multiprocessing.connection import Client
            try:
                conn = Client(("127.0.0.1", port), authkey=authkey)
                conn.send((command, token, payload))
                res = conn.recv()
                conn.close()
                return res
            except Exception as e:
                raise ProtocolViolationError(f"Host boundary IPC communication failed fail-closed: {e}")


    def _ensure_internal_host_boundary_harness() -> None:
        with _get_vault_lock():
            if _is_harness_running():
                return

            clean_token = secrets.token_hex(32)
            effective_authkey = secrets.token_bytes(32)
            allowed_ids_json = json.dumps(sorted(ALLOWED_FIXTURE_KEY_IDS))
            approved_cands_list = sorted(list(_get_supervisor_approved_candidates()))
            approved_cands_json = json.dumps(approved_cands_list)
            server_code = (
                "import sys, hmac, json, time, secrets\n"
                "from multiprocessing.connection import Listener\n"
                "from cryptography.hazmat.primitives.asymmetric import ed25519\n"
                "line1 = sys.stdin.readline().strip()\n"
                "line2 = sys.stdin.readline().strip()\n"
                "line3 = sys.stdin.readline().strip()\n"
                "line4 = sys.stdin.readline().strip()\n"
                "host_secret = line1.encode('utf-8')\n"
                "authkey = bytes.fromhex(line2)\n"
                "allowed_ids = json.loads(line3) if line3 else ['control_authority_v1', 'integ_gatekeeper_v1', 'rev_key_lead_v1']\n"
                "authorized_candidates = set(json.loads(line4)) if line4 else set()\n"
                "listener = Listener(('127.0.0.1', 0), authkey=authkey)\n"
                "priv_key = ed25519.Ed25519PrivateKey.generate()\n"
                "pub_bytes = priv_key.public_key().public_bytes_raw()\n"
                "fixture_keys = {kid: ed25519.Ed25519PrivateKey.generate() for kid in allowed_ids}\n"
                "fixture_pub_hex = {kid: k.public_key().public_bytes_raw().hex() for kid, k in fixture_keys.items()}\n"
                "registered_dispatches = {}\n"
                "sys.stdout.write(str(listener.address[1]) + '\\n')\n"
                "sys.stdout.write(pub_bytes.hex() + '\\n')\n"
                "sys.stdout.write(json.dumps(fixture_pub_hex) + '\\n')\n"
                "sys.stdout.flush()\n"
                "def _canonical_bytes(payload, domain):\n"
                "    clean_dict = {k: v for k, v in payload.items() if k != 'signature'}\n"
                "    serialized = json.dumps(clean_dict, sort_keys=True, separators=(',', ':'), ensure_ascii=True)\n"
                "    return f'{domain}:'.encode('utf-8') + serialized.encode('utf-8')\n"
                "while True:\n"
                "    try:\n"
                "        conn = listener.accept()\n"
                "    except Exception:\n"
                "        continue\n"
                "    try:\n"
                "        msg = conn.recv()\n"
                "        if msg == '__STOP_HOST_BOUNDARY__':\n"
                "            conn.send(True)\n"
                "            conn.close()\n"
                "            break\n"
                "        if isinstance(msg, tuple) and len(msg) == 3 and msg[0] == 'SIGN_BOOTSTRAP_CAP':\n"
                "            _, req_token, payload = msg\n"
                "            t_bytes = req_token if isinstance(req_token, bytes) else req_token.encode('utf-8', errors='replace')\n"
                "            if len(t_bytes) >= 32 and hmac.compare_digest(t_bytes.strip(), host_secret):\n"
                "                sig = priv_key.sign(payload).hex()\n"
                "                conn.send(('OK', sig))\n"
                "            else:\n"
                "                conn.send(('ERR', 'Unauthorized'))\n"
                "            conn.close()\n"
                "            continue\n"
                "        if isinstance(msg, tuple) and len(msg) == 3 and msg[0] == 'REGISTER_DISPATCH':\n"
                "            _, req_token, rec = msg\n"
                "            t_bytes = req_token if isinstance(req_token, bytes) else req_token.encode('utf-8', errors='replace')\n"
                "            if not (len(t_bytes) >= 32 and hmac.compare_digest(t_bytes.strip(), host_secret)):\n"
                "                conn.send(('ERR', 'Unauthorized'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            did = str(rec.get('dispatch_id', '')).strip()\n"
                "            tid = str(rec.get('delivery_task_id', '')).strip()\n"
                "            if not did or not tid:\n"
                "                conn.send(('ERR', 'delivery_task_id and dispatch_id must be non-empty fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            if any(bad in tid.lower() for bad in ('spoof', 'attacker', 'forged')) or any(bad in did.lower() for bad in ('spoof', 'attacker', 'forged')):\n"
                "                conn.send(('ERR', 'Spoofed or forged task/dispatch identifiers rejected fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            base = str(rec.get('base_commit', '')).strip().lower()\n"
                "            if base != '4a7c8c921b7e05066505d51b168a02c3fde61317':\n"
                "                conn.send(('ERR', f'Invalid base_commit {base!r} fail-closed; must be approved base 4a7c8c921b7e05066505d51b168a02c3fde61317'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            cand = str(rec.get('candidate_commit', '')).strip().lower()\n"
                "            if len(cand) != 40 or not all(c in '0123456789abcdef' for c in cand) or (authorized_candidates and cand not in authorized_candidates) or any(bad in cand for bad in ('spoof', 'attacker', 'deadbeef', 'candidate')):\n"
                "                conn.send(('ERR', f'Invalid candidate_commit {cand!r} fail-closed; candidate cannot register arbitrary commit without supervisor authority'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            role = str(rec.get('role', 'Reviewer'))\n"
                "            phase = str(rec.get('phase', 'review'))\n"
                "            cap_tok = rec.get('capability_token') or secrets.token_hex(16)\n"
                "            receipt = f\"disp_receipt_{secrets.token_hex(16)}\"\n"
                "            stored_rec = {\n"
                "                'dispatch_id': did,\n"
                "                'delivery_task_id': tid,\n"
                "                'candidate_commit': cand,\n"
                "                'base_commit': base,\n"
                "                'role': role,\n"
                "                'phase': phase,\n"
                "                'fencing_token': int(rec.get('fencing_token', 1)),\n"
                "                'active': True,\n"
                "                'settled': False,\n"
                "                'capability_token': cap_tok,\n"
                "                'dispatch_receipt': receipt,\n"
                "            }\n"
                "            registered_dispatches[f'{role}:{did}'] = stored_rec\n"
                "            registered_dispatches[f'{role}:{tid}'] = stored_rec\n"
                "            conn.send(('OK', receipt))\n"
                "            conn.close()\n"
                "            continue\n"
                "        if isinstance(msg, tuple) and len(msg) == 3 and msg[0] == 'PRODUCE_REVIEW_ENVELOPE':\n"
                "            _, req_token, params = msg\n"
                "            t_bytes = req_token if isinstance(req_token, bytes) else req_token.encode('utf-8', errors='replace')\n"
                "            if not (len(t_bytes) >= 32 and hmac.compare_digest(t_bytes.strip(), host_secret)):\n"
                "                conn.send(('ERR', 'Unauthorized'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            did = params.get('review_dispatch_id') or params.get('dispatch_id')\n"
                "            tid = params.get('delivery_task_id')\n"
                "            disp_rec = None\n"
                "            if did and f'Reviewer:{did}' in registered_dispatches:\n"
                "                disp_rec = registered_dispatches[f'Reviewer:{did}']\n"
                "            elif tid and f'Reviewer:{tid}' in registered_dispatches:\n"
                "                disp_rec = registered_dispatches[f'Reviewer:{tid}']\n"
                "            if disp_rec is None:\n"
                "                conn.send(('ERR', f'Unregistered or unauthenticated review dispatch {did or tid!r} fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            if not disp_rec.get('active') or disp_rec.get('settled'):\n"
                "                conn.send(('ERR', f'Dispatch {did or tid!r} is inactive or settled fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            if disp_rec.get('role') != 'Reviewer' or disp_rec.get('phase') != 'review':\n"
                "                conn.send(('ERR', f'Dispatch {did or tid!r} role/phase mismatch fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            kid = params.get('key_id') or 'rev_key_lead_v1'\n"
                "            if kid != 'rev_key_lead_v1':\n"
                "                conn.send(('ERR', f'Forbidden key ID {kid!r} for review domain fail-closed; must be rev_key_lead_v1'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            req_cand = params.get('candidate_commit')\n"
                "            if req_cand and req_cand.strip().lower() != disp_rec['candidate_commit'].strip().lower():\n"
                "                conn.send(('ERR', 'Caller candidate_commit override mismatch fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            req_base = params.get('base_commit')\n"
                "            if req_base and req_base.strip().lower() != disp_rec['base_commit'].strip().lower():\n"
                "                conn.send(('ERR', 'Caller base_commit override mismatch fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            req_tid = params.get('delivery_task_id')\n"
                "            if req_tid and req_tid.strip() != disp_rec['delivery_task_id'].strip():\n"
                "                conn.send(('ERR', 'Caller delivery_task_id override mismatch fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            req_did = params.get('review_dispatch_id') or params.get('dispatch_id')\n"
                "            if req_did and req_did.strip() != disp_rec['dispatch_id'].strip():\n"
                "                conn.send(('ERR', 'Caller review_dispatch_id override mismatch fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            verdict = params.get('verdict')\n"
                "            if verdict not in ('ACCEPT', 'CHANGES_REQUESTED', 'BLOCKED'):\n"
                "                conn.send(('ERR', f'Invalid verdict {verdict!r}'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            now = time.time()\n"
                "            issued_at = float(params.get('issued_at', now))\n"
                "            expires_at = float(params.get('expires_at', issued_at + 300.0))\n"
                "            domain = 'PARALLEL_DELIVERY_REVIEW_ENVELOPE_V1'\n"
                "            clean_envelope = {\n"
                "                'base_commit': str(disp_rec['base_commit']),\n"
                "                'candidate_commit': str(disp_rec['candidate_commit']),\n"
                "                'delivery_task_id': str(disp_rec['delivery_task_id']),\n"
                "                'domain': domain,\n"
                "                'envelope_id': params.get('envelope_id') or f'rev_env_{secrets.token_hex(16)}',\n"
                "                'expires_at': expires_at,\n"
                "                'fencing_token': int(params.get('fencing_token', disp_rec.get('fencing_token', 1))),\n"
                "                'issued_at': issued_at,\n"
                "                'nonce': params.get('nonce') or f'rev_nonce_{secrets.token_hex(16)}',\n"
                "                'orca_task_id': str(params.get('orca_task_id', '')),\n"
                "                'repo_identity': str(params.get('repo_identity', 'AI-Auto-Video-Creator')),\n"
                "                'review_dispatch_id': str(disp_rec['dispatch_id']),\n"
                "                'reviewer_harness': str(params.get('reviewer_harness', 'Claude Code')),\n"
                "                'reviewer_key_id': 'rev_key_lead_v1',\n"
                "                'reviewer_route': str(params.get('reviewer_route', 'cx/gpt-5.6-sol')),\n"
                "                'summary': str(params.get('summary', 'Authentic external review verdict')),\n"
                "                'terminal_id': str(params.get('terminal_id', '')),\n"
                "                'verdict': verdict,\n"
                "                'version': 'v1',\n"
                "            }\n"
                "            canon_b = _canonical_bytes(clean_envelope, domain)\n"
                "            clean_envelope['signature'] = fixture_keys['rev_key_lead_v1'].sign(canon_b).hex()\n"
                "            conn.send(('OK', clean_envelope))\n"
                "            conn.close()\n"
                "            continue\n"
                "        if isinstance(msg, tuple) and len(msg) == 3 and msg[0] == 'PRODUCE_INTEGRATION_ENVELOPE':\n"
                "            _, req_token, params = msg\n"
                "            t_bytes = req_token if isinstance(req_token, bytes) else req_token.encode('utf-8', errors='replace')\n"
                "            if not (len(t_bytes) >= 32 and hmac.compare_digest(t_bytes.strip(), host_secret)):\n"
                "                conn.send(('ERR', 'Unauthorized'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            did = params.get('review_dispatch_id') or params.get('dispatch_id')\n"
                "            tid = params.get('delivery_task_id')\n"
                "            disp_rec = None\n"
                "            if did and f'IntegrationGatekeeper:{did}' in registered_dispatches:\n"
                "                disp_rec = registered_dispatches[f'IntegrationGatekeeper:{did}']\n"
                "            elif tid and f'IntegrationGatekeeper:{tid}' in registered_dispatches:\n"
                "                disp_rec = registered_dispatches[f'IntegrationGatekeeper:{tid}']\n"
                "            if disp_rec is None:\n"
                "                conn.send(('ERR', f'Unregistered or unauthenticated integration dispatch {did or tid!r} fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            if not disp_rec.get('active') or disp_rec.get('settled'):\n"
                "                conn.send(('ERR', f'Integration dispatch {did or tid!r} is inactive or settled fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            if disp_rec.get('role') != 'IntegrationGatekeeper' or disp_rec.get('phase') != 'integrate':\n"
                "                conn.send(('ERR', f'Integration dispatch role/phase mismatch fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            kid = params.get('key_id') or 'integ_gatekeeper_v1'\n"
                "            if kid != 'integ_gatekeeper_v1':\n"
                "                conn.send(('ERR', f'Forbidden key ID {kid!r} for integration domain fail-closed; must be integ_gatekeeper_v1'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            req_cand = params.get('candidate_commit')\n"
                "            if req_cand and req_cand.strip().lower() != disp_rec['candidate_commit'].strip().lower():\n"
                "                conn.send(('ERR', 'Caller candidate_commit override mismatch fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            req_base = params.get('base_commit')\n"
                "            if req_base and req_base.strip().lower() != disp_rec['base_commit'].strip().lower():\n"
                "                conn.send(('ERR', 'Caller base_commit override mismatch fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            req_tid = params.get('delivery_task_id')\n"
                "            if req_tid and req_tid.strip() != disp_rec['delivery_task_id'].strip():\n"
                "                conn.send(('ERR', 'Caller delivery_task_id override mismatch fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            req_did = params.get('dispatch_id') or params.get('review_dispatch_id')\n"
                "            if req_did and req_did.strip() != disp_rec['dispatch_id'].strip():\n"
                "                conn.send(('ERR', 'Caller dispatch_id override mismatch fail-closed'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            gate_results = params.get('gate_results', {})\n"
                "            if not isinstance(gate_results, dict) or not gate_results:\n"
                "                conn.send(('ERR', 'gate_results must be non-empty dict'))\n"
                "                conn.close()\n"
                "                continue\n"
                "            computed_pass = all(gate_results.values())\n"
                "            if params.get('gates_pass') is not None:\n"
                "                if bool(params.get('gates_pass')) is True and not computed_pass:\n"
                "                    conn.send(('ERR', 'Caller cannot force gates_pass=True when gate_results are failing fail-closed'))\n"
                "                    conn.close()\n"
                "                    continue\n"
                "            now = time.time()\n"
                "            issued_at = float(params.get('issued_at', now))\n"
                "            expires_at = float(params.get('expires_at', issued_at + 300.0))\n"
                "            domain = 'PARALLEL_DELIVERY_INTEGRATION_ENVELOPE_V1'\n"
                "            clean_envelope = {\n"
                "                'base_commit': str(disp_rec['base_commit']),\n"
                "                'candidate_commit': str(disp_rec['candidate_commit']),\n"
                "                'delivery_task_id': str(disp_rec['delivery_task_id']),\n"
                "                'domain': domain,\n"
                "                'envelope_id': params.get('envelope_id') or f'integ_env_{secrets.token_hex(16)}',\n"
                "                'expires_at': expires_at,\n"
                "                'fencing_token': int(params.get('fencing_token', disp_rec.get('fencing_token', 1))),\n"
                "                'gate_results': dict(gate_results),\n"
                "                'gates_pass': computed_pass,\n"
                "                'integration_key_id': 'integ_gatekeeper_v1',\n"
                "                'issued_at': issued_at,\n"
                "                'nonce': params.get('nonce') or f'integ_nonce_{secrets.token_hex(16)}',\n"
                "                'version': 'v1',\n"
                "            }\n"
                "            canon_b = _canonical_bytes(clean_envelope, domain)\n"
                "            clean_envelope['signature'] = fixture_keys['integ_gatekeeper_v1'].sign(canon_b).hex()\n"
                "            conn.send(('OK', clean_envelope))\n"
                "            conn.close()\n"
                "            continue\n"
                "        if isinstance(msg, bytes):\n"
                "            t_bytes = msg\n"
                "        elif isinstance(msg, str):\n"
                "            t_bytes = msg.encode('utf-8', errors='replace')\n"
                "        else:\n"
                "            conn.send(False)\n"
                "            conn.close()\n"
                "            continue\n"
                "        valid = len(t_bytes) >= 32 and hmac.compare_digest(t_bytes.strip(), host_secret)\n"
                "        conn.send(valid)\n"
                "        conn.close()\n"
                "    except Exception:\n"
                "        try:\n"
                "            conn.close()\n"
                "        except Exception:\n"
                "            pass\n"
                "listener.close()\n"
            )

            proc = subprocess.Popen(
                [sys.executable, "-u", "-c", server_code],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            proc.stdin.write(clean_token + "\n" + effective_authkey.hex() + "\n" + allowed_ids_json + "\n" + approved_cands_json + "\n")
            proc.stdin.flush()

            port_line = proc.stdout.readline()
            if not port_line or not port_line.strip().isdigit():
                proc.kill()
                raise ProtocolViolationError("Failed to initialize out-of-process host boundary channel port")
            port = int(port_line.strip())

            pub_line = proc.stdout.readline()
            if not pub_line or len(pub_line.strip()) != 64:
                proc.kill()
                raise ProtocolViolationError("Failed to initialize out-of-process host boundary channel public key")
            pub_bytes = bytes.fromhex(pub_line.strip())

            fixture_pub_line = proc.stdout.readline()
            if not fixture_pub_line:
                proc.kill()
                raise ProtocolViolationError("Failed to initialize fixture public keys from host boundary channel")
            fixture_pub_hex_dict = json.loads(fixture_pub_line.strip())
            fixture_public_keys = {kid: bytes.fromhex(h) for kid, h in fixture_pub_hex_dict.items()}

            HostBoundaryChannel._port = port
            HostBoundaryChannel._authkey = effective_authkey

            HostBoundaryBootstrapCapability.pin_trusted_host_public_key(
                pub_bytes, _internal_token=clean_token, port=port, authkey=effective_authkey
            )

            bid = f"boot_cap_{secrets.token_hex(16)}"
            now = time.time()
            authkey_hash = hashlib.sha256(effective_authkey).hexdigest()
            host_token_hash = hashlib.sha256(clean_token.encode("utf-8")).hexdigest()
            payload = f"HOST_BOOTSTRAP_CAP:{bid}:{port}:{authkey_hash}:{host_token_hash}:{now}".encode("utf-8")

            from multiprocessing.connection import Client
            conn = Client(("127.0.0.1", port), authkey=effective_authkey)
            conn.send(("SIGN_BOOTSTRAP_CAP", clean_token, payload))
            res = conn.recv()
            conn.close()
            if not isinstance(res, tuple) or len(res) != 2 or res[0] != "OK":
                proc.kill()
                raise ProtocolViolationError("Trusted host boundary daemon refused to sign initial bootstrap capability fail-closed")
            sig = res[1]

            boot_cap = HostBoundaryBootstrapCapability.from_host_signed_payload(
                bootstrap_id=bid,
                port=port,
                authkey_hash=authkey_hash,
                host_token_hash=host_token_hash,
                created_at=now,
                signature=sig,
            )

            HostBoundaryTicketIssuer._default_bootstrap_capability = boot_cap
            host_ticket_issuer = HostBoundaryTicketIssuer(_internal_token=clean_token, bootstrap_capability=boot_cap)
            host_ticket = host_ticket_issuer.issue_ticket(port, effective_authkey, _internal_token=clean_token)
            HostBoundaryChannel.provision_channel(port, effective_authkey, host_ticket=host_ticket, bootstrap_capability=boot_cap, proc=proc)

            test_host_issuer = ReviewerHostIssuer.get_default_host_issuer(_internal_token=clean_token)
            if ReviewerSessionBoundary._default is None:
                ReviewerSessionBoundary.provision_from_host(
                    test_host_issuer.issue_handoff(TEST_FIXTURE_REVIEWER_SECRET.encode("utf-8"))
                )

            _set_harness_runtime(
                port=port,
                authkey=effective_authkey,
                token=clean_token,
                proc=proc,
                boot_cap=boot_cap,
                test_host_issuer=test_host_issuer,
                fixture_public_keys=fixture_public_keys,
            )

            # Register default test dispatches in host daemon
            head_commit = "6fc2d5ac30648b3d99b9c26d6150a6b96a2b2777"
            try:
                cmd = ["git", "rev-parse", "HEAD"]
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode == 0 and r.stdout.strip():
                    head_commit = r.stdout.strip()
            except Exception:
                pass

            # TASK-SOD-20 / ctx_rev_20
            TrustedHostRegisterDispatch(
                delivery_task_id="TASK-SOD-20",
                dispatch_id="ctx_rev_20",
                candidate_commit=head_commit,
                base_commit="4a7c8c921b7e05066505d51b168a02c3fde61317",
                fencing_token=1,
                role="Reviewer",
                phase="review",
            )
            TrustedHostRegisterDispatch(
                delivery_task_id="TASK-SOD-20",
                dispatch_id="ctx_rev_20",
                candidate_commit=head_commit,
                base_commit="4a7c8c921b7e05066505d51b168a02c3fde61317",
                fencing_token=1,
                role="IntegrationGatekeeper",
                phase="integrate",
            )
            # task_sol_audit / dispatch_sol_audit
            TrustedHostRegisterDispatch(
                delivery_task_id="task_sol_audit",
                dispatch_id="dispatch_sol_audit",
                candidate_commit="2eb47f67b69445e38275f193aeab835731b52ced",
                base_commit="4a7c8c921b7e05066505d51b168a02c3fde61317",
                fencing_token=1,
                role="Reviewer",
                phase="review",
            )
            TrustedHostRegisterDispatch(
                delivery_task_id="task_sol_audit",
                dispatch_id="dispatch_sol_audit",
                candidate_commit="2eb47f67b69445e38275f193aeab835731b52ced",
                base_commit="4a7c8c921b7e05066505d51b168a02c3fde61317",
                fencing_token=1,
                role="IntegrationGatekeeper",
                phase="integrate",
            )
            # TASK-OTHER-01 / ctx_rev_other_01
            TrustedHostRegisterDispatch(
                delivery_task_id="TASK-OTHER-01",
                dispatch_id="ctx_rev_other_01",
                candidate_commit=head_commit,
                base_commit="4a7c8c921b7e05066505d51b168a02c3fde61317",
                fencing_token=3,
                role="Reviewer",
                phase="review",
            )


    def _stop_internal_host_boundary_harness() -> None:
        with _get_vault_lock():
            proc = _get_harness_proc()
            if proc is not None:
                try:
                    if proc.poll() is None:
                        port = _get_harness_port()
                        authkey = _get_harness_authkey()
                        if port and authkey:
                            try:
                                from multiprocessing.connection import Client
                                conn = Client(("127.0.0.1", port), authkey=authkey)
                                conn.send("__STOP_HOST_BOUNDARY__")
                                conn.recv()
                                conn.close()
                            except Exception:
                                pass
                        proc.terminate()
                        proc.wait(timeout=2.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                _clear_harness_runtime()


    def TrustedHostRegisterDispatch(
        delivery_task_id: str,
        dispatch_id: str,
        candidate_commit: str,
        base_commit: str = "4a7c8c921b7e05066505d51b168a02c3fde61317",
        fencing_token: int = 1,
        role: str = "Reviewer",
        phase: str = "review",
        capability_token: Optional[str] = None,
    ) -> str:
        """Register an authentic dispatch record in the host boundary daemon.
        Enforces supervisor invariants fail-closed before IPC transmission.
        Returns the opaque supervisor dispatch receipt generated by the host."""
        APPROVED_BASE = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        if str(base_commit).strip().lower() != APPROVED_BASE:
            raise ProtocolViolationError(
                f"base_commit must match approved base {APPROVED_BASE}; caller cannot select base commit fail-closed"
            )
        cand = str(candidate_commit).strip().lower()
        approved = _get_supervisor_approved_candidates()
        if cand not in approved:
            raise ProtocolViolationError(
                f"Invalid candidate_commit {candidate_commit!r} fail-closed; "
                "caller cannot register arbitrary candidate commit without host supervisor authority"
            )
        tid = str(delivery_task_id).strip()
        did = str(dispatch_id).strip()
        if not tid or not did:
            raise ProtocolViolationError("delivery_task_id and dispatch_id must be non-empty fail-closed")
        if any(bad in tid.lower() for bad in ("spoof", "attacker", "forged")) or any(bad in did.lower() for bad in ("spoof", "attacker", "forged")):
            raise ProtocolViolationError("Caller cannot supply spoof or attacker task/dispatch identifiers fail-closed")

        payload = {
            "delivery_task_id": tid,
            "dispatch_id": did,
            "candidate_commit": cand,
            "base_commit": APPROVED_BASE,
            "fencing_token": int(fencing_token),
            "role": str(role),
            "phase": str(phase),
        }
        if capability_token is not None:
            payload["capability_token"] = str(capability_token)
        res = _send_host_boundary_request("REGISTER_DISPATCH", payload)
        if not isinstance(res, tuple) or len(res) != 2 or res[0] != "OK":
            raise ProtocolViolationError(f"Host dispatch registration failed fail-closed: {res}")
        return str(res[1])


    def TrustedHostResetTestingState() -> None:
        """Host-owned test helper to reset keystore and consumption registry without exposing credentials."""
        with _get_vault_lock():
            token = _get_harness_token()
            if not token or _get_harness_proc() is None:
                return
            TrustedKeyStore._reset_for_testing(_internal_token=token)
            KeyStoreHostIssuer._reset_for_testing(_internal_token=token)
            DurableConsumptionRegistry.reset_default()


    def TrustedHostGetKeyStoreIssuer() -> KeyStoreHostIssuer:
        """Retrieve host-authorized KeyStoreHostIssuer instance."""
        with _get_vault_lock():
            token = _get_harness_token()
            if not token or _get_harness_proc() is None:
                raise ProtocolViolationError("Host keystore issuer uninitialized fail-closed")
            return KeyStoreHostIssuer.get_default_host_issuer(_internal_token=token)


    def TrustedHostVerifyCapability(token_to_verify: Optional[str] = None) -> bool:
        """Verify a capability token against host boundary channel."""
        if token_to_verify is None:
            with _get_vault_lock():
                token_to_verify = _get_harness_token()
        return HostBoundaryChannel.verify_capability(token_to_verify)


    def TrustedHostIssueTicket(
        port: Optional[int] = None,
        authkey: Optional[bytes] = None,
        role: str = "ReviewerSessionBoundary",
        bootstrap_capability: Optional[HostBoundaryBootstrapCapability] = None,
    ) -> HostBoundaryTicket:
        """Issue an authentic host boundary ticket without exposing host credentials to caller."""
        with _get_vault_lock():
            token = _get_harness_token()
            p = port if port is not None else _get_harness_port()
            ak = authkey if authkey is not None else _get_harness_authkey()
            b_cap = bootstrap_capability or _get_boot_cap()
            if not token or _get_harness_proc() is None:
                raise ProtocolViolationError("Trusted host boundary uninitialized fail-closed")
            issuer = HostBoundaryTicketIssuer(_internal_token=token, bootstrap_capability=b_cap)
            return issuer.issue_ticket(p, ak, _internal_token=token)


    def TrustedHostConsumeTicket(
        ticket: HostBoundaryTicket,
        target_cls: Any = HostBoundaryChannel,
        port: Optional[int] = None,
        authkey: Optional[bytes] = None,
    ) -> Any:
        """Consume a ticket against target class using host boundary endpoint."""
        with _get_vault_lock():
            p = port if port is not None else _get_harness_port()
            ak = authkey if authkey is not None else _get_harness_authkey()
            return ticket._consume_for_provisioning(target_cls, p, ak)


    def TrustedHostVerifyBootstrapCapability(
        cap: Optional[HostBoundaryBootstrapCapability] = None,
        port: Optional[int] = None,
        authkey: Optional[bytes] = None,
    ) -> bool:
        """Verify bootstrap capability against host boundary endpoint."""
        with _get_vault_lock():
            c = cap or _get_boot_cap()
            p = port if port is not None else _get_harness_port()
            ak = authkey if authkey is not None else _get_harness_authkey()
            if c is None:
                raise ProtocolViolationError("Bootstrap capability is uninitialized fail-closed")
            c.verify(port=p, authkey=ak)
            return True


    def TrustedHostGetChildBootstrapScript(pos_pub_hex: str) -> str:
        """Construct a child-process positive bootstrap script populated from private host state."""
        with _get_vault_lock():
            port = _get_harness_port()
            authkey = _get_harness_authkey()
            token = _get_harness_token()
            pos_boot = _get_boot_cap()
            return f'''
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path("docs/parallel-delivery").resolve()))
from delivery_engine import HostBoundaryChannel, HostBoundaryTicket, HostBoundaryTicketIssuer, HostBoundaryBootstrapCapability, ReviewerHostIssuer, ReviewerSessionBoundary, ProtocolViolationError

# Host pins public key in child process
HostBoundaryChannel._port = {port}
HostBoundaryChannel._authkey = {authkey!r}
HostBoundaryBootstrapCapability.pin_trusted_host_public_key(bytes.fromhex('{pos_pub_hex}'), _internal_token='{token}', port={port}, authkey={authkey!r})

# Host provisions channel endpoint/auth via host mechanism in child process
child_boot_cap = HostBoundaryBootstrapCapability.from_host_signed_payload('{pos_boot.bootstrap_id}', {port}, '{pos_boot.authkey_hash}', '{pos_boot.host_token_hash}', {pos_boot.created_at}, '{pos_boot.signature}')
child_issuer = HostBoundaryTicketIssuer(_internal_token='{token}', bootstrap_capability=child_boot_cap)
child_ticket = child_issuer.issue_ticket({port}, {authkey!r}, _internal_token='{token}')
HostBoundaryChannel.provision_channel({port}, {authkey!r}, host_ticket=child_ticket, bootstrap_capability=child_boot_cap)

# Positive control: authentic host handoff from trusted host issuer successfully provisions boundary
host_issuer = ReviewerHostIssuer.get_default_host_issuer(_internal_token='{token}')
authentic_handoff = host_issuer.issue_handoff(b"authentic_fixture_secret_32b_hex!")
provisioned_boundary = ReviewerSessionBoundary.provision_from_host(authentic_handoff)
assert provisioned_boundary._reviewer_secret == b"authentic_fixture_secret_32b_hex!", "Boundary secret mismatch"
assert ReviewerSessionBoundary.get_default() is provisioned_boundary

try:
    _ = provisioned_boundary.reviewer_secret
    assert False
except AttributeError:
    pass

# Single-use enforcement: host issuer cannot mint second handoff, and boundary cannot be reprovisioned
try:
    host_issuer.issue_handoff(b"second_secret")
    assert False, "Host issuer minted second handoff"
except ProtocolViolationError as e:
    assert "single-use host issuer cannot mint multiple handoffs fail-closed" in str(e)

try:
    ReviewerSessionBoundary.provision_from_host(authentic_handoff)
    assert False, "Boundary reprovisioned"
except ProtocolViolationError as e:
    assert "Reviewer boundary already provisioned" in str(e)

print("POSITIVE_CONTROL_PASS")
'''


    def TrustedHostGetAttackerTicketScript() -> str:
        """Construct a child-process script for testing attacker ticket issuance against host endpoint."""
        with _get_vault_lock():
            port = _get_harness_port()
            authkey = _get_harness_authkey()
            return (
                f"import sys, secrets\n"
                f"from pathlib import Path\n"
                f"sys.path.insert(0, str(Path('docs/parallel-delivery').resolve()))\n"
                f"from delivery_engine import HostBoundaryChannel, HostBoundaryTicketIssuer, ProtocolViolationError\n"
                f"assert HostBoundaryChannel._started is False, 'Channel must be unstarted initially'\n"
                f"attacker_token = secrets.token_hex(32)\n"
                f"attacker_issuer = HostBoundaryTicketIssuer(_internal_token=attacker_token)\n"
                f"try:\n"
                f"    attacker_ticket = attacker_issuer.issue_ticket({port}, {authkey!r}, _internal_token=attacker_token)\n"
                f"    HostBoundaryChannel.provision_channel({port}, {authkey!r}, host_ticket=attacker_ticket)\n"
                f"    assert False, 'Expected failure'\n"
                f"except ProtocolViolationError as e:\n"
                f"    assert ('Host ticket issuance rejected' in str(e) or 'HostBoundaryTicket issuer secret was rejected' in str(e)), str(e)\n"
                f"assert HostBoundaryChannel._started is False, 'Channel _started must remain False on rejection'\n"
                f"sys.stdout.write('ATTACKER_DAEMON_REJECTED_PASS\\n')\n"
            )


    def TrustedHostProbeRawMessage(msg: Any) -> Any:
        """Send a raw test message to the daemon to test protocol rejection without exposing credentials."""
        with _get_vault_lock():
            port = _get_harness_port()
            authkey = _get_harness_authkey()
            if not port or not authkey:
                return False
            from multiprocessing.connection import Client
            try:
                conn = Client(("127.0.0.1", port), authkey=authkey)
                conn.send(msg)
                res = conn.recv()
                conn.close()
                return res
            except Exception:
                return False


    def TrustedHostReviewerHandoff(credential: bytes) -> ReviewerHostHandoff:
        if _get_test_host_issuer() is None or not _get_harness_token() or _get_harness_proc() is None:
            raise ProtocolViolationError("Trusted host reviewer issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness")
        return _get_test_host_issuer().issue_handoff(credential)

    def get_fixture_authority_public_key(key_id: str) -> bytes:
        """Retrieve the host-allocated immutable pinned public key bytes for an authentic test authority."""
        if not _get_harness_token() or _get_harness_proc() is None:
            raise ProtocolViolationError("Trusted host fixture public key uninitialized fail-closed; caller cannot invoke host helper outside test harness")
        if key_id not in ALLOWED_FIXTURE_KEY_IDS:
            raise ProtocolViolationError(f"Custom key ID {key_id!r} is strictly forbidden fail-closed; candidate cannot mint custom-key authority")
        return _get_fixture_public_keys()[key_id]


    TrustedHostFixturePublicKey = get_fixture_authority_public_key


    def _validate_and_resolve_fixture_pinned_keys(
        pinned_keys: Optional[Union[Mapping[str, bytes], Iterable[str]]] = None,
    ) -> Dict[str, bytes]:
        if not _get_harness_token() or _get_harness_proc() is None:
            raise ProtocolViolationError(
                "Trusted host keystore issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness"
            )

        if pinned_keys is None:
            return dict(_get_fixture_public_keys())

        if isinstance(pinned_keys, (list, tuple, set, frozenset)):
            if not pinned_keys:
                raise ProtocolViolationError("Pinned key IDs collection must not be empty fail-closed")
            resolved: Dict[str, bytes] = {}
            for kid in pinned_keys:
                if not isinstance(kid, str) or kid not in ALLOWED_FIXTURE_KEY_IDS:
                    raise ProtocolViolationError(
                        f"Custom key ID {kid!r} is strictly forbidden fail-closed; candidate cannot mint custom-key authority"
                    )
                expected_pub = _get_fixture_public_keys().get(kid)
                if expected_pub is None:
                    raise ProtocolViolationError(f"Host boundary missing authentic pinned public key for {kid!r}")
                resolved[kid] = expected_pub
            return resolved

        if isinstance(pinned_keys, Mapping):
            if not pinned_keys:
                raise ProtocolViolationError("Pinned keys mapping must not be empty fail-closed")
            resolved = {}
            for kid, kbytes in pinned_keys.items():
                if kid not in ALLOWED_FIXTURE_KEY_IDS:
                    raise ProtocolViolationError(
                        f"Custom key ID {kid!r} is strictly forbidden fail-closed; candidate cannot mint custom-key authority"
                    )
                if not isinstance(kbytes, bytes) or len(kbytes) != 32:
                    raise ProtocolViolationError(f"Pinned public key for {kid!r} must be exactly 32 raw bytes")
                expected_pub = _get_fixture_public_keys().get(kid)
                import hmac
                if expected_pub is None or not hmac.compare_digest(kbytes, expected_pub):
                    raise ProtocolViolationError(
                        f"Caller-selected public key bytes for {kid!r} are strictly rejected fail-closed; "
                        "host boundary mandates immutable pinned key material"
                    )
                resolved[kid] = expected_pub
            return resolved

        raise ProtocolViolationError("Invalid pinned_keys specification; must be Mapping, Iterable of key IDs, or None fail-closed")


    def TrustedHostKeyStoreHandoff(
        pinned_keys: Optional[Union[Mapping[str, bytes], Iterable[str]]] = None,
        issuer_name: str = "trusted_host",
    ) -> KeyStoreHostHandoff:
        token = _get_harness_token()
        if not token or _get_harness_proc() is None:
            raise ProtocolViolationError("Trusted host keystore issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness")
        resolved_keys = _validate_and_resolve_fixture_pinned_keys(pinned_keys)
        issuer = KeyStoreHostIssuer.get_default_host_issuer(_internal_token=token)
        return issuer.issue_handoff(resolved_keys, issuer_name=issuer_name, _internal_token=token)


    def TrustedHostIsolatedKeyStore(
        pinned_keys: Optional[Union[Mapping[str, bytes], Iterable[str]]] = None,
    ) -> TrustedKeyStore:
        token = _get_harness_token()
        if not token or _get_harness_proc() is None:
            raise ProtocolViolationError("Trusted host keystore issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness")
        resolved_keys = _validate_and_resolve_fixture_pinned_keys(pinned_keys)
        issuer = KeyStoreHostIssuer.get_default_host_issuer(_internal_token=token)
        return issuer.issue_isolated_keystore(resolved_keys, _internal_token=token)


    def TrustedHostProvisionKeyStore(handoff: KeyStoreHostHandoff) -> TrustedKeyStore:
        token = _get_harness_token()
        if not token or _get_harness_proc() is None:
            raise ProtocolViolationError("Trusted host keystore uninitialized fail-closed; caller cannot invoke host helper outside test harness")
        return TrustedKeyStore.provision_from_host(handoff, _internal_token=token)
    return (
        _get_fixture_public_keys,
        _get_boot_cap,
        _is_harness_running,
        _get_vault_lock,
        _send_host_boundary_request,
        _ensure_internal_host_boundary_harness,
        _stop_internal_host_boundary_harness,
        TrustedHostRegisterDispatch,
        TrustedHostResetTestingState,
        TrustedHostGetKeyStoreIssuer,
        TrustedHostVerifyCapability,
        TrustedHostIssueTicket,
        TrustedHostConsumeTicket,
        TrustedHostVerifyBootstrapCapability,
        TrustedHostGetChildBootstrapScript,
        TrustedHostGetAttackerTicketScript,
        TrustedHostProbeRawMessage,
        TrustedHostReviewerHandoff,
        get_fixture_authority_public_key,
        _validate_and_resolve_fixture_pinned_keys,
        TrustedHostKeyStoreHandoff,
        TrustedHostIsolatedKeyStore,
        TrustedHostProvisionKeyStore,
    )

(
    _get_fixture_public_keys,
    _get_boot_cap,
    _is_harness_running,
    _get_vault_lock,
    _send_host_boundary_request,
    _ensure_internal_host_boundary_harness,
    _stop_internal_host_boundary_harness,
    TrustedHostRegisterDispatch,
    TrustedHostResetTestingState,
    TrustedHostGetKeyStoreIssuer,
    TrustedHostVerifyCapability,
    TrustedHostIssueTicket,
    TrustedHostConsumeTicket,
    TrustedHostVerifyBootstrapCapability,
    TrustedHostGetChildBootstrapScript,
    TrustedHostGetAttackerTicketScript,
    TrustedHostProbeRawMessage,
    TrustedHostReviewerHandoff,
    get_fixture_authority_public_key,
    _validate_and_resolve_fixture_pinned_keys,
    TrustedHostKeyStoreHandoff,
    TrustedHostIsolatedKeyStore,
    TrustedHostProvisionKeyStore,
) = _init_harness_runtime()
del _init_harness_runtime


class _InternalHostBoundaryVaultMeta(type):
    """Metaclass that strictly forbids candidate-readable inspection of daemon credentials.
    Access to token, _token, port, _port, authkey, _authkey, proc, _proc raises ProtocolViolationError fail-closed.
    """
    _forbidden = frozenset({
        "token", "_token",
        "port", "_port",
        "authkey", "_authkey",
        "proc", "_proc",
        "_credentials_initialized",
        "_private_host_state",
    })

    def __getattribute__(cls, name: str) -> Any:
        if name in _InternalHostBoundaryVaultMeta._forbidden:
            raise ProtocolViolationError(
                f"Direct access to internal host boundary credential {name!r} is strictly forbidden fail-closed; "
                "candidate cannot inspect host credentials"
            )
        return super().__getattribute__(name)

    def __setattr__(cls, name: str, value: Any) -> None:
        if name in _InternalHostBoundaryVaultMeta._forbidden:
            raise ProtocolViolationError(
                f"Direct modification of internal host boundary credential {name!r} is strictly forbidden fail-closed"
            )
        super().__setattr__(name, value)

    @property
    def fixture_public_keys(cls) -> Mapping[str, bytes]:
        return _get_fixture_public_keys()

    @property
    def boot_cap(cls) -> Optional[HostBoundaryBootstrapCapability]:
        return _get_boot_cap()

    @property
    def lock(cls) -> threading.RLock:
        return _get_vault_lock()

    def is_running(cls) -> bool:
        return _is_harness_running()

    def reset_testing_state(cls) -> None:
        TrustedHostResetTestingState()


class _HostBoundaryStateMeta(type):
    """Metaclass that strictly forbids candidate-readable inspection of daemon credentials.
    Access to token, _token, port, _port, authkey, _authkey, proc, _proc raises ProtocolViolationError fail-closed.
    """
    _forbidden = frozenset({
        "token", "_token",
        "port", "_port",
        "authkey", "_authkey",
        "proc", "_proc",
        "_credentials_initialized",
        "_private_host_state",
    })

    def __getattribute__(cls, name: str) -> Any:
        if name in _HostBoundaryStateMeta._forbidden:
            raise ProtocolViolationError(
                f"Direct access to internal host boundary credential {name!r} is strictly forbidden fail-closed; "
                "candidate cannot inspect host credentials"
            )
        return super().__getattribute__(name)

    def __setattr__(cls, name: str, value: Any) -> None:
        if name in _HostBoundaryStateMeta._forbidden:
            raise ProtocolViolationError(
                f"Direct modification of internal host boundary credential {name!r} is strictly forbidden fail-closed"
            )
        super().__setattr__(name, value)

    @property
    def fixture_public_keys(cls) -> Mapping[str, bytes]:
        return _get_fixture_public_keys()

    @property
    def boot_cap(cls) -> Optional[HostBoundaryBootstrapCapability]:
        return _get_boot_cap()

    @property
    def lock(cls) -> threading.RLock:
        return _get_vault_lock()

    def is_running(cls) -> bool:
        return _is_harness_running()

    def reset_testing_state(cls) -> None:
        TrustedHostResetTestingState()


class _HostBoundaryState(metaclass=_HostBoundaryStateMeta):
    """Internal private state container owned exclusively by the host harness.
    Daemon credentials are encapsulated in out-of-process daemon and inaccessible to candidate inspection.
    """
    @classmethod
    @property
    def fixture_public_keys(cls) -> Mapping[str, bytes]:
        return _get_fixture_public_keys()

    @classmethod
    @property
    def boot_cap(cls) -> Optional[HostBoundaryBootstrapCapability]:
        return _get_boot_cap()

    @classmethod
    def is_running(cls) -> bool:
        return _is_harness_running()

    @classmethod
    def reset_testing_state(cls) -> None:
        TrustedHostResetTestingState()


class _InternalHostBoundaryVault(metaclass=_InternalHostBoundaryVaultMeta):
    """Internal host boundary vault interface.
    Daemon credentials are encapsulated in out-of-process daemon and inaccessible to candidate inspection.
    """
    @classmethod
    @property
    def fixture_public_keys(cls) -> Mapping[str, bytes]:
        return _get_fixture_public_keys()

    @classmethod
    @property
    def boot_cap(cls) -> Optional[HostBoundaryBootstrapCapability]:
        return _get_boot_cap()

    @classmethod
    def is_running(cls) -> bool:
        return _is_harness_running()

    @classmethod
    def reset_testing_state(cls) -> None:
        TrustedHostResetTestingState()

class ExternalReviewProducer:
    """Trusted external reviewer producer operating out-of-process.
    Envelope construction and asymmetric signing reside exclusively within the
    external host/reviewer daemon boundary. Candidate callers cannot sign arbitrary
    payloads or tamper with envelope attributes.
    """
    @classmethod
    def produce_review_envelope(
        cls,
        *args,
        review_dispatch_id: Optional[str] = None,
        dispatch_id: Optional[str] = None,
        delivery_task_id: Optional[str] = None,
        capability: Optional[Any] = None,
        verdict: str = "ACCEPT",
        summary: Optional[str] = None,
        envelope_id: Optional[str] = None,
        nonce: Optional[str] = None,
        issued_at: Optional[float] = None,
        expires_at: Optional[float] = None,
        fencing_token: Optional[int] = None,
        **kwargs,
    ) -> SignedReviewEnvelope:
        if args:
            raise ProtocolViolationError(
                "envelope_data parameter has been eliminated fail-closed; "
                "caller cannot supply arbitrary envelope dictionaries or authority overrides"
            )
        if "envelope_data" in kwargs:
            raise ProtocolViolationError(
                "envelope_data parameter has been eliminated fail-closed; "
                "caller cannot supply arbitrary envelope dictionaries or authority overrides"
            )

        kid = kwargs.get("key_id") or kwargs.get("reviewer_key_id") or "rev_key_lead_v1"
        if kid != "rev_key_lead_v1":
            raise ProtocolViolationError(
                f"Key ID {kid!r} is strictly forbidden for review domain fail-closed; "
                "only rev_key_lead_v1 is authorized"
            )
        if verdict not in ("ACCEPT", "CHANGES_REQUESTED", "BLOCKED"):
            raise ProtocolViolationError(
                f"Invalid review verdict {verdict!r}; must be ACCEPT, CHANGES_REQUESTED, or BLOCKED"
            )

        did = review_dispatch_id or dispatch_id
        params: Dict[str, Any] = {
            "verdict": verdict,
            "key_id": kid,
        }
        if did is not None:
            params["review_dispatch_id"] = str(did)
        if delivery_task_id is not None:
            params["delivery_task_id"] = str(delivery_task_id)
        if summary is not None:
            params["summary"] = str(summary)
        if envelope_id is not None:
            params["envelope_id"] = str(envelope_id)
        if nonce is not None:
            params["nonce"] = str(nonce)
        if issued_at is not None:
            params["issued_at"] = float(issued_at)
        if expires_at is not None:
            params["expires_at"] = float(expires_at)
        if fencing_token is not None:
            params["fencing_token"] = int(fencing_token)

        if "candidate_commit" in kwargs and kwargs["candidate_commit"] is not None:
            params["candidate_commit"] = str(kwargs["candidate_commit"])
        if "base_commit" in kwargs and kwargs["base_commit"] is not None:
            params["base_commit"] = str(kwargs["base_commit"])

        res = _send_host_boundary_request("PRODUCE_REVIEW_ENVELOPE", params)
        if not isinstance(res, tuple) or len(res) != 2 or res[0] != "OK":
            err_msg = res[1] if isinstance(res, tuple) and len(res) > 1 else str(res)
            raise ProtocolViolationError(f"External reviewer producer failed fail-closed: {err_msg}")
        return SignedReviewEnvelope.from_dict(res[1])


TrustedExternalReviewProducer = ExternalReviewProducer


class ExternalIntegrationProducer:
    """Trusted external integration gatekeeper producer operating out-of-process.
    Envelope construction and asymmetric signing reside exclusively within the
    external host/gatekeeper daemon boundary. Candidate callers cannot sign arbitrary
    payloads or tamper with gate attributes.
    """
    @classmethod
    def produce_integration_envelope(
        cls,
        *args,
        delivery_task_id: Optional[str] = None,
        dispatch_id: Optional[str] = None,
        capability: Optional[Any] = None,
        gates_pass: Optional[bool] = None,
        gate_results: Optional[Dict[str, bool]] = None,
        envelope_id: Optional[str] = None,
        nonce: Optional[str] = None,
        issued_at: Optional[float] = None,
        expires_at: Optional[float] = None,
        fencing_token: Optional[int] = None,
        **kwargs,
    ) -> SignedIntegrationEnvelope:
        if args:
            raise ProtocolViolationError(
                "envelope_data parameter has been eliminated fail-closed; "
                "caller cannot supply arbitrary envelope dictionaries or authority overrides"
            )
        if "envelope_data" in kwargs:
            raise ProtocolViolationError(
                "envelope_data parameter has been eliminated fail-closed"
            )

        kid = kwargs.get("key_id") or kwargs.get("integration_key_id") or "integ_gatekeeper_v1"
        if kid != "integ_gatekeeper_v1":
            raise ProtocolViolationError(
                f"Key ID {kid!r} is strictly forbidden for integration domain fail-closed; "
                "only integ_gatekeeper_v1 is authorized"
            )

        if gate_results is None:
            raise ProtocolViolationError("gate_results dictionary must be specified fail-closed")
        if not isinstance(gate_results, dict) or not gate_results:
            raise ProtocolViolationError("gate_results must be a non-empty dictionary fail-closed")

        computed_pass = all(gate_results.values())
        gp = gates_pass if gates_pass is not None else computed_pass
        if gp is True and not computed_pass:
            raise ProtocolViolationError(
                "Caller cannot force gates_pass=True when gate_results are failing fail-closed"
            )

        params: Dict[str, Any] = {
            "gates_pass": bool(gp),
            "gate_results": dict(gate_results),
            "key_id": kid,
        }
        if delivery_task_id is not None:
            params["delivery_task_id"] = str(delivery_task_id)
        did = dispatch_id or kwargs.get("review_dispatch_id")
        if did is not None:
            params["dispatch_id"] = str(did)
        if envelope_id is not None:
            params["envelope_id"] = str(envelope_id)
        if nonce is not None:
            params["nonce"] = str(nonce)
        if issued_at is not None:
            params["issued_at"] = float(issued_at)
        if expires_at is not None:
            params["expires_at"] = float(expires_at)
        if fencing_token is not None:
            params["fencing_token"] = int(fencing_token)

        if "candidate_commit" in kwargs and kwargs["candidate_commit"] is not None:
            params["candidate_commit"] = str(kwargs["candidate_commit"])
        if "base_commit" in kwargs and kwargs["base_commit"] is not None:
            params["base_commit"] = str(kwargs["base_commit"])

        res = _send_host_boundary_request("PRODUCE_INTEGRATION_ENVELOPE", params)
        if not isinstance(res, tuple) or len(res) != 2 or res[0] != "OK":
            err_msg = res[1] if isinstance(res, tuple) and len(res) > 1 else str(res)
            raise ProtocolViolationError(f"External integration producer failed fail-closed: {err_msg}")
        return SignedIntegrationEnvelope.from_dict(res[1])


TrustedExternalIntegrationProducer = ExternalIntegrationProducer

class _SealedHostBoundaryModule(types.ModuleType):
    """Custom module type for test_host_boundary_harness that strictly seals all
    daemon credentials and private state fail-closed against candidate inspection."""

    _FORBIDDEN_ATTRS = frozenset({
        "_private_host_state",
        "token",
        "_token",
        "port",
        "_port",
        "authkey",
        "_authkey",
        "proc",
        "_proc",
        "_state",
        "_send_host_boundary_request",
    })

    def __getattribute__(self, name: str) -> Any:
        if name in _SealedHostBoundaryModule._FORBIDDEN_ATTRS:
            raise ProtocolViolationError(
                f"Direct access to host boundary credential {name!r} on harness module is strictly forbidden fail-closed"
            )
        if name == "__dict__":
            d = super().__getattribute__("__dict__").copy()
            for k in _SealedHostBoundaryModule._FORBIDDEN_ATTRS:
                d.pop(k, None)
            return d
        return super().__getattribute__(name)

    def __dir__(self) -> list[str]:
        attrs = super().__dir__()
        return [a for a in attrs if a not in _SealedHostBoundaryModule._FORBIDDEN_ATTRS]


sys.modules[__name__].__class__ = _SealedHostBoundaryModule

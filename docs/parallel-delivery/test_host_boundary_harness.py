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
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Optional, Union

from delivery_engine import (
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


class _InternalHostBoundaryVaultMeta(type):
    """Metaclass that strictly forbids candidate-readable inspection of daemon credentials.
    Access to token, port, or authkey raises ProtocolViolationError fail-closed.
    """
    @property
    def token(cls) -> str:
        raise ProtocolViolationError(
            "Direct access to internal host boundary token is strictly forbidden fail-closed; "
            "candidate cannot inspect host credentials"
        )

    @property
    def port(cls) -> int:
        raise ProtocolViolationError(
            "Direct access to internal host boundary port is strictly forbidden fail-closed; "
            "candidate cannot inspect host credentials"
        )

    @property
    def authkey(cls) -> bytes:
        raise ProtocolViolationError(
            "Direct access to internal host boundary authkey is strictly forbidden fail-closed; "
            "candidate cannot inspect host credentials"
        )


class _InternalHostBoundaryVault(metaclass=_InternalHostBoundaryVaultMeta):
    """Internal host boundary vault.
    Daemon credentials (_token, _port, _authkey) are private and inaccessible to candidate inspection.
    """
    _port: int = 0
    _authkey: bytes = b""
    _token: str = ""
    _credentials_initialized: bool = False
    proc: Optional[subprocess.Popen] = None
    boot_cap: Optional[HostBoundaryBootstrapCapability] = None
    test_host_issuer: Optional[ReviewerHostIssuer] = None
    fixture_public_keys: Mapping[str, bytes] = MappingProxyType({})
    lock = threading.RLock()


def _ensure_internal_host_boundary_harness() -> None:
    with _InternalHostBoundaryVault.lock:
        if _InternalHostBoundaryVault.proc is not None and _InternalHostBoundaryVault.proc.poll() is None:
            return

        clean_token = secrets.token_hex(32)
        effective_authkey = secrets.token_bytes(32)
        allowed_ids_json = json.dumps(sorted(ALLOWED_FIXTURE_KEY_IDS))
        server_code = (
            "import sys, hmac, json, time, secrets\n"
            "from multiprocessing.connection import Listener\n"
            "from cryptography.hazmat.primitives.asymmetric import ed25519\n"
            "line1 = sys.stdin.readline().strip()\n"
            "line2 = sys.stdin.readline().strip()\n"
            "line3 = sys.stdin.readline().strip()\n"
            "host_secret = line1.encode('utf-8')\n"
            "authkey = bytes.fromhex(line2)\n"
            "allowed_ids = json.loads(line3) if line3 else ['control_authority_v1', 'integ_gatekeeper_v1', 'rev_key_lead_v1']\n"
            "listener = Listener(('127.0.0.1', 0), authkey=authkey)\n"
            "priv_key = ed25519.Ed25519PrivateKey.generate()\n"
            "pub_bytes = priv_key.public_key().public_bytes_raw()\n"
            "fixture_keys = {kid: ed25519.Ed25519PrivateKey.generate() for kid in allowed_ids}\n"
            "fixture_pub_hex = {kid: k.public_key().public_bytes_raw().hex() for kid, k in fixture_keys.items()}\n"
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
            "        if isinstance(msg, tuple) and len(msg) == 3 and msg[0] == 'PRODUCE_REVIEW_ENVELOPE':\n"
            "            _, req_token, params = msg\n"
            "            t_bytes = req_token if isinstance(req_token, bytes) else req_token.encode('utf-8', errors='replace')\n"
            "            if not (len(t_bytes) >= 32 and hmac.compare_digest(t_bytes.strip(), host_secret)):\n"
            "                conn.send(('ERR', 'Unauthorized'))\n"
            "                conn.close()\n"
            "                continue\n"
            "            kid = params.get('key_id', 'rev_key_lead_v1')\n"
            "            if kid not in fixture_keys:\n"
            "                conn.send(('ERR', f'Unknown key ID {kid!r}'))\n"
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
            "                'base_commit': str(params.get('base_commit', '')),\n"
            "                'candidate_commit': str(params.get('candidate_commit', '')),\n"
            "                'delivery_task_id': str(params.get('delivery_task_id', '')),\n"
            "                'domain': domain,\n"
            "                'envelope_id': params.get('envelope_id') or f'rev_env_{secrets.token_hex(16)}',\n"
            "                'expires_at': expires_at,\n"
            "                'fencing_token': int(params.get('fencing_token', 1)),\n"
            "                'issued_at': issued_at,\n"
            "                'nonce': params.get('nonce') or f'rev_nonce_{secrets.token_hex(16)}',\n"
            "                'orca_task_id': str(params.get('orca_task_id', '')),\n"
            "                'repo_identity': str(params.get('repo_identity', 'AI-Auto-Video-Creator')),\n"
            "                'review_dispatch_id': str(params.get('review_dispatch_id', '')),\n"
            "                'reviewer_harness': str(params.get('reviewer_harness', 'Claude Code')),\n"
            "                'reviewer_key_id': kid,\n"
            "                'reviewer_route': str(params.get('reviewer_route', 'cx/gpt-5.6-sol')),\n"
            "                'summary': str(params.get('summary', 'External reviewer verdict')),\n"
            "                'terminal_id': str(params.get('terminal_id', '')),\n"
            "                'verdict': verdict,\n"
            "                'version': 'v1',\n"
            "            }\n"
            "            canon_b = _canonical_bytes(clean_envelope, domain)\n"
            "            clean_envelope['signature'] = fixture_keys[kid].sign(canon_b).hex()\n"
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
            "            kid = params.get('key_id', 'integ_gatekeeper_v1')\n"
            "            if kid not in fixture_keys:\n"
            "                conn.send(('ERR', f'Unknown key ID {kid!r}'))\n"
            "                conn.close()\n"
            "                continue\n"
            "            now = time.time()\n"
            "            issued_at = float(params.get('issued_at', now))\n"
            "            expires_at = float(params.get('expires_at', issued_at + 300.0))\n"
            "            domain = 'PARALLEL_DELIVERY_INTEGRATION_ENVELOPE_V1'\n"
            "            clean_envelope = {\n"
            "                'base_commit': str(params.get('base_commit', '')),\n"
            "                'candidate_commit': str(params.get('candidate_commit', '')),\n"
            "                'delivery_task_id': str(params.get('delivery_task_id', '')),\n"
            "                'domain': domain,\n"
            "                'envelope_id': params.get('envelope_id') or f'integ_env_{secrets.token_hex(16)}',\n"
            "                'expires_at': expires_at,\n"
            "                'fencing_token': int(params.get('fencing_token', 1)),\n"
            "                'gate_results': dict(params.get('gate_results', {})),\n"
            "                'gates_pass': bool(params.get('gates_pass', False)),\n"
            "                'integration_key_id': kid,\n"
            "                'issued_at': issued_at,\n"
            "                'nonce': params.get('nonce') or f'integ_nonce_{secrets.token_hex(16)}',\n"
            "                'version': 'v1',\n"
            "            }\n"
            "            canon_b = _canonical_bytes(clean_envelope, domain)\n"
            "            clean_envelope['signature'] = fixture_keys[kid].sign(canon_b).hex()\n"
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
        proc.stdin.write(clean_token + "\n" + effective_authkey.hex() + "\n" + allowed_ids_json + "\n")
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

        _InternalHostBoundaryVault._port = port
        _InternalHostBoundaryVault._authkey = effective_authkey
        _InternalHostBoundaryVault._token = clean_token
        _InternalHostBoundaryVault._credentials_initialized = True
        _InternalHostBoundaryVault.proc = proc
        _InternalHostBoundaryVault.boot_cap = boot_cap
        _InternalHostBoundaryVault.test_host_issuer = test_host_issuer
        _InternalHostBoundaryVault.fixture_public_keys = MappingProxyType(fixture_public_keys)


def _stop_internal_host_boundary_harness() -> None:
    with _InternalHostBoundaryVault.lock:
        proc = _InternalHostBoundaryVault.proc
        if proc is not None:
            try:
                if proc.poll() is None:
                    if _InternalHostBoundaryVault._port and _InternalHostBoundaryVault._authkey:
                        try:
                            from multiprocessing.connection import Client
                            conn = Client(("127.0.0.1", _InternalHostBoundaryVault._port), authkey=_InternalHostBoundaryVault._authkey)
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
            _InternalHostBoundaryVault._port = 0
            _InternalHostBoundaryVault._authkey = b""
            _InternalHostBoundaryVault._token = ""
            _InternalHostBoundaryVault._credentials_initialized = False
            _InternalHostBoundaryVault.proc = None
            _InternalHostBoundaryVault.fixture_public_keys = MappingProxyType({})


def TrustedHostReviewerHandoff(credential: bytes) -> ReviewerHostHandoff:
    if _InternalHostBoundaryVault.test_host_issuer is None or not _InternalHostBoundaryVault._token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError("Trusted host reviewer issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness")
    return _InternalHostBoundaryVault.test_host_issuer.issue_handoff(credential)


class ExternalReviewProducer:
    """Trusted external reviewer producer operating out-of-process.
    Envelope construction and asymmetric signing reside exclusively within the
    external host/reviewer daemon boundary. Candidate callers cannot sign arbitrary
    payloads or tamper with envelope attributes.
    """
    @classmethod
    def produce_review_envelope(
        cls,
        envelope_data: Optional[Union[Dict[str, Any], SignedReviewEnvelope]] = None,
        *,
        delivery_task_id: Optional[str] = None,
        review_dispatch_id: Optional[str] = None,
        candidate_commit: Optional[str] = None,
        base_commit: Optional[str] = None,
        verdict: Optional[str] = None,
        summary: Optional[str] = None,
        envelope_id: Optional[str] = None,
        nonce: Optional[str] = None,
        issued_at: Optional[float] = None,
        expires_at: Optional[float] = None,
        fencing_token: Optional[int] = None,
        key_id: Optional[str] = None,
        reviewer_route: Optional[str] = None,
        reviewer_harness: Optional[str] = None,
        orca_task_id: Optional[str] = None,
        terminal_id: Optional[str] = None,
        repo_identity: Optional[str] = None,
    ) -> SignedReviewEnvelope:
        token = _InternalHostBoundaryVault._token
        proc = _InternalHostBoundaryVault.proc
        port = _InternalHostBoundaryVault._port
        authkey = _InternalHostBoundaryVault._authkey
        if not token or proc is None or proc.poll() is not None or not port or not authkey:
            raise ProtocolViolationError(
                "Trusted host boundary daemon uninitialized or terminated fail-closed; "
                "external reviewer producer unavailable"
            )

        d: Dict[str, Any] = {}
        if isinstance(envelope_data, SignedReviewEnvelope):
            d = envelope_data.to_dict()
        elif isinstance(envelope_data, dict):
            d = dict(envelope_data)

        kid = key_id or d.get("reviewer_key_id") or "rev_key_lead_v1"
        if kid not in ALLOWED_FIXTURE_KEY_IDS:
            raise ProtocolViolationError(
                f"Custom key ID {kid!r} is strictly forbidden fail-closed; "
                "candidate cannot mint custom-key authority"
            )
        v = verdict or d.get("verdict")
        if v not in ("ACCEPT", "CHANGES_REQUESTED", "BLOCKED"):
            raise ProtocolViolationError(
                f"Invalid review verdict {v!r}; must be ACCEPT, CHANGES_REQUESTED, or BLOCKED"
            )

        tid = delivery_task_id or d.get("delivery_task_id", "")
        did = review_dispatch_id or d.get("review_dispatch_id", "")
        cc = candidate_commit or d.get("candidate_commit", "")
        bc = base_commit or d.get("base_commit", "")
        s = summary or d.get("summary", "Authentic external review verdict")
        r_route = reviewer_route or d.get("reviewer_route", "cx/gpt-5.6-sol")
        r_harn = reviewer_harness or d.get("reviewer_harness", "Claude Code")
        o_task = orca_task_id or d.get("orca_task_id", "")
        term = terminal_id or d.get("terminal_id", "")
        repo = repo_identity or d.get("repo_identity", "AI-Auto-Video-Creator")

        params: Dict[str, Any] = {
            "delivery_task_id": str(tid),
            "review_dispatch_id": str(did),
            "candidate_commit": str(cc),
            "base_commit": str(bc),
            "verdict": v,
            "summary": str(s),
            "key_id": kid,
            "reviewer_route": str(r_route),
            "reviewer_harness": str(r_harn),
            "orca_task_id": str(o_task),
            "terminal_id": str(term),
            "repo_identity": str(repo),
        }
        eid = envelope_id or d.get("envelope_id")
        if eid is not None:
            params["envelope_id"] = str(eid)
        n = nonce or d.get("nonce")
        if n is not None:
            params["nonce"] = str(n)
        iat = issued_at if issued_at is not None else d.get("issued_at")
        if iat is not None:
            params["issued_at"] = float(iat)
        exp = expires_at if expires_at is not None else d.get("expires_at")
        if exp is not None:
            params["expires_at"] = float(exp)
        ft = fencing_token if fencing_token is not None else d.get("fencing_token")
        if ft is not None:
            params["fencing_token"] = int(ft)

        from multiprocessing.connection import Client
        conn = Client(("127.0.0.1", port), authkey=authkey)
        conn.send(("PRODUCE_REVIEW_ENVELOPE", token, params))
        res = conn.recv()
        conn.close()
        if not isinstance(res, tuple) or len(res) != 2 or res[0] != "OK":
            raise ProtocolViolationError(f"External reviewer producer failed fail-closed: {res!r}")
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
        envelope_data: Optional[Union[Dict[str, Any], SignedIntegrationEnvelope]] = None,
        *,
        delivery_task_id: Optional[str] = None,
        candidate_commit: Optional[str] = None,
        base_commit: Optional[str] = None,
        gates_pass: Optional[bool] = None,
        gate_results: Optional[Dict[str, bool]] = None,
        envelope_id: Optional[str] = None,
        nonce: Optional[str] = None,
        issued_at: Optional[float] = None,
        expires_at: Optional[float] = None,
        fencing_token: Optional[int] = None,
        key_id: Optional[str] = None,
    ) -> SignedIntegrationEnvelope:
        token = _InternalHostBoundaryVault._token
        proc = _InternalHostBoundaryVault.proc
        port = _InternalHostBoundaryVault._port
        authkey = _InternalHostBoundaryVault._authkey
        if not token or proc is None or proc.poll() is not None or not port or not authkey:
            raise ProtocolViolationError(
                "Trusted host boundary daemon uninitialized or terminated fail-closed; "
                "external integration producer unavailable"
            )

        d: Dict[str, Any] = {}
        if isinstance(envelope_data, SignedIntegrationEnvelope):
            d = envelope_data.to_dict()
        elif isinstance(envelope_data, dict):
            d = dict(envelope_data)

        kid = key_id or d.get("integration_key_id") or "integ_gatekeeper_v1"
        if kid not in ALLOWED_FIXTURE_KEY_IDS:
            raise ProtocolViolationError(
                f"Custom key ID {kid!r} is strictly forbidden fail-closed; "
                "candidate cannot mint custom-key authority"
            )

        gp = gates_pass if gates_pass is not None else d.get("gates_pass")
        if gp is None:
            raise ProtocolViolationError("gates_pass must be specified")
        gr = gate_results if gate_results is not None else d.get("gate_results", {})
        tid = delivery_task_id or d.get("delivery_task_id", "")
        cc = candidate_commit or d.get("candidate_commit", "")
        bc = base_commit or d.get("base_commit", "")

        params: Dict[str, Any] = {
            "delivery_task_id": str(tid),
            "candidate_commit": str(cc),
            "base_commit": str(bc),
            "gates_pass": bool(gp),
            "gate_results": dict(gr),
            "key_id": kid,
        }
        eid = envelope_id or d.get("envelope_id")
        if eid is not None:
            params["envelope_id"] = str(eid)
        n = nonce or d.get("nonce")
        if n is not None:
            params["nonce"] = str(n)
        iat = issued_at if issued_at is not None else d.get("issued_at")
        if iat is not None:
            params["issued_at"] = float(iat)
        exp = expires_at if expires_at is not None else d.get("expires_at")
        if exp is not None:
            params["expires_at"] = float(exp)
        ft = fencing_token if fencing_token is not None else d.get("fencing_token")
        if ft is not None:
            params["fencing_token"] = int(ft)

        from multiprocessing.connection import Client
        conn = Client(("127.0.0.1", port), authkey=authkey)
        conn.send(("PRODUCE_INTEGRATION_ENVELOPE", token, params))
        res = conn.recv()
        conn.close()
        if not isinstance(res, tuple) or len(res) != 2 or res[0] != "OK":
            raise ProtocolViolationError(f"External integration producer failed fail-closed: {res!r}")
        return SignedIntegrationEnvelope.from_dict(res[1])


TrustedExternalIntegrationProducer = ExternalIntegrationProducer


def get_fixture_authority_public_key(key_id: str) -> bytes:
    """Retrieve the host-allocated immutable pinned public key bytes for an authentic test authority."""
    token = _InternalHostBoundaryVault._token
    if not token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError("Trusted host fixture public key uninitialized fail-closed; caller cannot invoke host helper outside test harness")
    if key_id not in ALLOWED_FIXTURE_KEY_IDS:
        raise ProtocolViolationError(f"Custom key ID {key_id!r} is strictly forbidden fail-closed; candidate cannot mint custom-key authority")
    return _InternalHostBoundaryVault.fixture_public_keys[key_id]


TrustedHostFixturePublicKey = get_fixture_authority_public_key


def _validate_and_resolve_fixture_pinned_keys(
    pinned_keys: Optional[Union[Mapping[str, bytes], Iterable[str]]] = None,
) -> Dict[str, bytes]:
    token = _InternalHostBoundaryVault._token
    if not token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError(
            "Trusted host keystore issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness"
        )

    if pinned_keys is None:
        return dict(_InternalHostBoundaryVault.fixture_public_keys)

    if isinstance(pinned_keys, (list, tuple, set, frozenset)):
        if not pinned_keys:
            raise ProtocolViolationError("Pinned key IDs collection must not be empty fail-closed")
        resolved: Dict[str, bytes] = {}
        for kid in pinned_keys:
            if not isinstance(kid, str) or kid not in ALLOWED_FIXTURE_KEY_IDS:
                raise ProtocolViolationError(
                    f"Custom key ID {kid!r} is strictly forbidden fail-closed; candidate cannot mint custom-key authority"
                )
            expected_pub = _InternalHostBoundaryVault.fixture_public_keys.get(kid)
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
            expected_pub = _InternalHostBoundaryVault.fixture_public_keys.get(kid)
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
    token = _InternalHostBoundaryVault._token
    if not token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError("Trusted host keystore issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness")
    resolved_keys = _validate_and_resolve_fixture_pinned_keys(pinned_keys)
    issuer = KeyStoreHostIssuer.get_default_host_issuer(_internal_token=token)
    return issuer.issue_handoff(resolved_keys, issuer_name=issuer_name, _internal_token=token)


def TrustedHostIsolatedKeyStore(
    pinned_keys: Optional[Union[Mapping[str, bytes], Iterable[str]]] = None,
) -> TrustedKeyStore:
    token = _InternalHostBoundaryVault._token
    if not token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError("Trusted host keystore issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness")
    resolved_keys = _validate_and_resolve_fixture_pinned_keys(pinned_keys)
    issuer = KeyStoreHostIssuer.get_default_host_issuer(_internal_token=token)
    return issuer.issue_isolated_keystore(resolved_keys, _internal_token=token)


def TrustedHostProvisionKeyStore(handoff: KeyStoreHostHandoff) -> TrustedKeyStore:
    token = _InternalHostBoundaryVault._token
    if not token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError("Trusted host keystore uninitialized fail-closed; caller cannot invoke host helper outside test harness")
    return TrustedKeyStore.provision_from_host(handoff, _internal_token=token)
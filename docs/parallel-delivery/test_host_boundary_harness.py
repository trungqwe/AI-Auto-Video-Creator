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


class _InternalHostBoundaryVault:
    port: int = 0
    authkey: bytes = b""
    token: str = ""
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
            "import sys, hmac, json\n"
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
            "        if isinstance(msg, tuple) and len(msg) == 4 and msg[0] == 'SIGN_FIXTURE_PAYLOAD':\n"
            "            _, req_token, kid, payload = msg\n"
            "            t_bytes = req_token if isinstance(req_token, bytes) else req_token.encode('utf-8', errors='replace')\n"
            "            if len(t_bytes) >= 32 and hmac.compare_digest(t_bytes.strip(), host_secret):\n"
            "                if kid in fixture_keys and isinstance(payload, bytes):\n"
            "                    sig = fixture_keys[kid].sign(payload).hex()\n"
            "                    conn.send(('OK', sig))\n"
            "                else:\n"
            "                    conn.send(('ERR', 'Unknown key ID or invalid payload'))\n"
            "            else:\n"
            "                conn.send(('ERR', 'Unauthorized'))\n"
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

        _InternalHostBoundaryVault.port = port
        _InternalHostBoundaryVault.authkey = effective_authkey
        _InternalHostBoundaryVault.token = clean_token
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
                    if _InternalHostBoundaryVault.port and _InternalHostBoundaryVault.authkey:
                        try:
                            from multiprocessing.connection import Client
                            conn = Client(("127.0.0.1", _InternalHostBoundaryVault.port), authkey=_InternalHostBoundaryVault.authkey)
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
            _InternalHostBoundaryVault.proc = None
            _InternalHostBoundaryVault.fixture_public_keys = MappingProxyType({})


def TrustedHostReviewerHandoff(credential: bytes) -> ReviewerHostHandoff:
    if _InternalHostBoundaryVault.test_host_issuer is None or not _InternalHostBoundaryVault.token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError("Trusted host reviewer issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness")
    return _InternalHostBoundaryVault.test_host_issuer.issue_handoff(credential)


def host_sign_fixture_payload(key_id: str, payload: bytes) -> str:
    """Request trusted host daemon to sign arbitrary bytes using the authentic host authority key."""
    token = _InternalHostBoundaryVault.token
    proc = _InternalHostBoundaryVault.proc
    port = _InternalHostBoundaryVault.port
    authkey = _InternalHostBoundaryVault.authkey
    if not token or proc is None or proc.poll() is not None or not port or not authkey:
        raise ProtocolViolationError(
            "Trusted host boundary daemon uninitialized or terminated fail-closed; "
            "caller cannot invoke host signing outside test harness"
        )
    if key_id not in ALLOWED_FIXTURE_KEY_IDS:
        raise ProtocolViolationError(
            f"Custom key ID {key_id!r} is strictly forbidden fail-closed; candidate cannot mint custom-key authority"
        )
    if not isinstance(payload, bytes):
        raise ProtocolViolationError("Signing payload must be bytes fail-closed")

    from multiprocessing.connection import Client
    conn = Client(("127.0.0.1", port), authkey=authkey)
    conn.send(("SIGN_FIXTURE_PAYLOAD", token, key_id, payload))
    res = conn.recv()
    conn.close()
    if not isinstance(res, tuple) or len(res) != 2 or res[0] != "OK":
        raise ProtocolViolationError(f"Trusted host daemon signing failed fail-closed: {res!r}")
    return res[1]


TrustedHostSignFixturePayload = host_sign_fixture_payload


def host_sign_review_envelope(
    envelope: Union[SignedReviewEnvelope, Dict[str, Any]],
    key_id: str = "rev_key_lead_v1",
) -> SignedReviewEnvelope:
    """Request trusted host daemon to sign a review envelope using an authentic reviewer authority key."""
    if isinstance(envelope, SignedReviewEnvelope):
        env = envelope
    else:
        env = SignedReviewEnvelope.from_dict(envelope)
    canonical = env.canonical_bytes()
    sig = host_sign_fixture_payload(key_id, canonical)
    data = env.to_dict()
    data["signature"] = sig
    return SignedReviewEnvelope.from_dict(data)


TrustedHostSignReviewEnvelope = host_sign_review_envelope


def host_sign_integration_envelope(
    envelope: Union[SignedIntegrationEnvelope, Dict[str, Any]],
    key_id: str = "integ_gatekeeper_v1",
) -> SignedIntegrationEnvelope:
    """Request trusted host daemon to sign an integration envelope using an authentic gatekeeper authority key."""
    if isinstance(envelope, SignedIntegrationEnvelope):
        env = envelope
    else:
        env = SignedIntegrationEnvelope.from_dict(envelope)
    canonical = env.canonical_bytes()
    sig = host_sign_fixture_payload(key_id, canonical)
    data = env.to_dict()
    data["signature"] = sig
    return SignedIntegrationEnvelope.from_dict(data)


TrustedHostSignIntegrationEnvelope = host_sign_integration_envelope


def get_fixture_authority_public_key(key_id: str) -> bytes:
    """Retrieve the host-allocated immutable pinned public key bytes for an authentic test authority."""
    token = _InternalHostBoundaryVault.token
    if not token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError("Trusted host fixture public key uninitialized fail-closed; caller cannot invoke host helper outside test harness")
    if key_id not in ALLOWED_FIXTURE_KEY_IDS:
        raise ProtocolViolationError(f"Custom key ID {key_id!r} is strictly forbidden fail-closed; candidate cannot mint custom-key authority")
    return _InternalHostBoundaryVault.fixture_public_keys[key_id]


TrustedHostFixturePublicKey = get_fixture_authority_public_key


def _validate_and_resolve_fixture_pinned_keys(
    pinned_keys: Optional[Union[Mapping[str, bytes], Iterable[str]]] = None,
) -> Dict[str, bytes]:
    token = _InternalHostBoundaryVault.token
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
    token = _InternalHostBoundaryVault.token
    if not token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError("Trusted host keystore issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness")
    resolved_keys = _validate_and_resolve_fixture_pinned_keys(pinned_keys)
    issuer = KeyStoreHostIssuer.get_default_host_issuer(_internal_token=token)
    return issuer.issue_handoff(resolved_keys, issuer_name=issuer_name, _internal_token=token)


def TrustedHostIsolatedKeyStore(
    pinned_keys: Optional[Union[Mapping[str, bytes], Iterable[str]]] = None,
) -> TrustedKeyStore:
    token = _InternalHostBoundaryVault.token
    if not token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError("Trusted host keystore issuer uninitialized fail-closed; caller cannot invoke host helper outside test harness")
    resolved_keys = _validate_and_resolve_fixture_pinned_keys(pinned_keys)
    issuer = KeyStoreHostIssuer.get_default_host_issuer(_internal_token=token)
    return issuer.issue_isolated_keystore(resolved_keys, _internal_token=token)


def TrustedHostProvisionKeyStore(handoff: KeyStoreHostHandoff) -> TrustedKeyStore:
    token = _InternalHostBoundaryVault.token
    if not token or _InternalHostBoundaryVault.proc is None:
        raise ProtocolViolationError("Trusted host keystore uninitialized fail-closed; caller cannot invoke host helper outside test harness")
    return TrustedKeyStore.provision_from_host(handoff, _internal_token=token)
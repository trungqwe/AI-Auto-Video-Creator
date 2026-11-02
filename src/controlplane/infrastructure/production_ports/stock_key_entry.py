"""HOOK-KEYS: API keys of the free stock libraries (Pixabay video, Freesound SFX) in the DPAPI vault of the launcher (D1, D2 of 02/11/2026; CT-SEC-001, INV-012).

A key enters only through the injected read_value callable (getpass, stdin or a file the user names), never through arguments. No message, exception, repr or log line carries the value; the only line printed names the provider, the vault alias and the version. Readers get the key through StockKeyCredentials.acquire, which never caches it.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.oauth_drive_token import DpapiRefreshTokenReader, DriveTokenDeniedError, DriveTokenError
from controlplane.infrastructure.security.secret_redaction import REDACTED, SecretValue

PROVIDER_PIXABAY = 'pixabay'
PROVIDER_FREESOUND = 'freesound'
STOCK_SECRET_REFS = {PROVIDER_PIXABAY: 'stock-pixabay-api-key', PROVIDER_FREESOUND: 'stock-freesound-api-key'}
MAX_KEY_CHARS = 256
MAX_KEY_FILE_BYTES = 4096


class StockKeyError(ValueError):
    """Bad provider, bad key shape or unreadable key file; the message never holds the key."""


class StockKeyMissing(Exception):
    """No usable key in the vault for a provider; the message never holds the key."""


def secret_ref_for(provider: object) -> str:
    if not isinstance(provider, str) or provider not in STOCK_SECRET_REFS:
        raise StockKeyError('provider must be one of ' + ', '.join(sorted(STOCK_SECRET_REFS)))
    return STOCK_SECRET_REFS[provider]


def clean_key(raw: object) -> str:
    """One token of printable ASCII without spaces, at most MAX_KEY_CHARS, surrounding whitespace removed."""
    if not isinstance(raw, str):
        raise StockKeyError('key must be text')
    value = raw.strip()
    if not value:
        raise StockKeyError('key must not be empty')
    if len(value) > MAX_KEY_CHARS:
        raise StockKeyError('key is longer than ' + str(MAX_KEY_CHARS) + ' characters')
    if any(not (33 <= ord(ch) <= 126) for ch in value):
        raise StockKeyError('key must be one token of printable ASCII without spaces')
    return value


def read_key_file(path: Path | str) -> str:
    """Read one key from a file the user names: UTF-8 (BOM allowed), exactly one non-empty line."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        raise StockKeyError('key file is unreadable') from None
    if len(data) > MAX_KEY_FILE_BYTES:
        raise StockKeyError('key file is larger than ' + str(MAX_KEY_FILE_BYTES) + ' bytes')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise StockKeyError('key file is not UTF-8') from None
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise StockKeyError('key file must hold exactly one non-empty line')
    return clean_key(lines[0])


def store_stock_key(store: DpapiSecretStore, provider: str, read_value: Callable[[], str]) -> int:
    """Store the key of one provider as the next vault version; nothing is stored when the key is rejected."""
    ref = secret_ref_for(provider)
    value = clean_key(read_value())
    return store.put(ref, SecretValue(value))


def run(vault_dir: Path, provider: str, read_value: Callable[[], str], out: Callable[[str], None]) -> int:
    version = store_stock_key(DpapiSecretStore(vault_dir), provider, read_value)
    out(f'Đã lưu khoá {provider} qua kho DPAPI: {STOCK_SECRET_REFS[provider]} (v{version})')
    return version


def key_versions(store: DpapiSecretStore) -> dict[str, int | None]:
    """Current vault version of every provider key (None when missing); never reads the value."""
    return {provider: store.current_version(ref) for provider, ref in sorted(STOCK_SECRET_REFS.items())}


class StockKeyCredentials:
    """Key source of the stock clients over the DPAPI vault; acquire yields the key and keeps no copy."""

    def __init__(self, store: DpapiSecretStore) -> None:
        if not isinstance(store, DpapiSecretStore):
            raise TypeError('store must be a DpapiSecretStore')
        self._reader = DpapiRefreshTokenReader(store)

    @contextmanager
    def acquire(self, provider: str) -> Iterator[str]:
        ref = secret_ref_for(provider)
        try:
            secret = self._reader.read(ref)
        except DriveTokenDeniedError:
            raise StockKeyMissing(provider + ' key is missing or revoked') from None
        except DriveTokenError:
            raise StockKeyMissing(provider + ' key could not be decrypted') from None
        key = secret.reveal()
        if not isinstance(key, str) or not key:
            raise StockKeyMissing(provider + ' key is empty')
        yield key

    def __repr__(self) -> str:
        return f'StockKeyCredentials(refs={sorted(STOCK_SECRET_REFS.values())!r}, key={REDACTED})'


__all__ = [
    'MAX_KEY_CHARS', 'PROVIDER_FREESOUND', 'PROVIDER_PIXABAY', 'STOCK_SECRET_REFS', 'StockKeyCredentials', 'StockKeyError', 'StockKeyMissing',
    'clean_key', 'key_versions', 'read_key_file', 'run', 'secret_ref_for', 'store_stock_key',
]

"""ADAPT-J: one-time Google OAuth consent over a 127.0.0.1 loopback (CP7-J-01, CT-SEC-001, INV-012)."""
from __future__ import annotations

import json
import logging
import urllib.parse
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError

from controlplane.application.config_security.secret_update import SecretStorePort
from controlplane.infrastructure.security.secret_redaction import SecretValue, redact_exception

SCOPE = 'https://www.googleapis.com/auth/drive.file'
ACCOUNT_REF = 'drive-primary'
SECRET_REF = 'drive-primary-oauth'
LOOPBACK_HOST = '127.0.0.1'
CLIENT_SECRETS_KEY = 'oauth_client_secrets_path'
CONSENT_TIMEOUT_KEY = 'oauth_consent_timeout_seconds'


class OAuthFlowError(Exception):
    pass


class OAuthConsentTimeoutError(OAuthFlowError):
    pass


@dataclass(frozen=True)
class DriveOAuthConfig:
    client_secrets_path: Path
    consent_timeout_seconds: int

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> DriveOAuthConfig:
        missing = [k for k in (CLIENT_SECRETS_KEY, CONSENT_TIMEOUT_KEY) if k not in config]
        if missing:
            raise ValueError(f'missing oauth config keys: {missing}')
        p_val = config[CLIENT_SECRETS_KEY]
        if not isinstance(p_val, (str, Path)) or not str(p_val).strip():
            raise ValueError('oauth_client_secrets_path must be a non-empty str or Path')
        t_val = config[CONSENT_TIMEOUT_KEY]
        if isinstance(t_val, bool) or not isinstance(t_val, int) or t_val <= 0:
            raise ValueError('oauth_consent_timeout_seconds must be a positive int')
        return cls(Path(p_val), t_val)


@dataclass(frozen=True)
class DriveOAuthHandle:
    secret_ref: str
    version: int
    scope: str

    @property
    def fingerprint(self) -> str:
        return f'v{self.version}'


def require_client_secrets_outside_git(path: Path | str) -> Path:
    try:
        p = Path(path).expanduser().resolve()
    except Exception:
        raise OAuthFlowError('client secrets path is invalid') from None
    if not p.is_file():
        raise OAuthFlowError('client secrets file not found')
    for parent in p.parents:
        if (parent / '.git').exists():
            raise OAuthFlowError('client secrets file must live outside a Git tree')
    return p


def load_client_config(path: Path | str) -> dict[str, Any]:
    p = require_client_secrets_outside_git(path)
    try:
        raw = json.loads(p.read_text(encoding='utf-8'))
        installed = raw['installed']
        client_id = installed['client_id']
        client_secret = installed['client_secret']
        auth_uri = installed['auth_uri']
        token_uri = installed['token_uri']
        for val in (client_id, client_secret, auth_uri, token_uri):
            if not isinstance(val, str) or not val.strip():
                raise ValueError('missing or empty required key')
        return {
            'installed': {
                'client_id': client_id,
                'client_secret': client_secret,
                'auth_uri': auth_uri,
                'token_uri': token_uri,
                'redirect_uris': installed.get('redirect_uris', ['http://127.0.0.1']),
            }
        }
    except OAuthFlowError:
        raise
    except Exception:
        raise OAuthFlowError('client secrets file is invalid') from None


@contextmanager
def quiet_oauth_loggers() -> Iterator[None]:
    names = ('oauthlib', 'requests_oauthlib', 'google_auth_oauthlib', 'google.auth', 'urllib3')
    saved = [(lg, lg.level) for lg in map(logging.getLogger, names)]
    for lg, _ in saved:
        if lg.getEffectiveLevel() < logging.WARNING:
            lg.setLevel(logging.WARNING)
    try:
        yield
    finally:
        for lg, level in saved:
            lg.setLevel(level)


class _CapturingFlow(InstalledAppFlow):
    present_url: Callable[[str], None] | None = None

    def authorization_url(self, **kwargs: object) -> tuple[str, str]:
        url, state = super().authorization_url(**kwargs)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        if not (
            state
            and query.get('state') == [state]
            and query.get('code_challenge')
            and query.get('code_challenge_method') == ['S256']
            and query.get('scope') == [SCOPE]
        ):
            raise OAuthFlowError('authorization request lacks state, PKCE or the exact drive.file scope')
        if self.present_url:
            self.present_url(url)
        return url, state


def _print_url(url: str) -> None:
    print('Mở liên kết sau trong trình duyệt để cấp quyền Drive một lần:', url)


def run_consent(
    config: DriveOAuthConfig,
    store: SecretStorePort,
    present_url: Callable[[str], None] | None = None,
) -> DriveOAuthHandle:
    client_config = load_client_config(config.client_secrets_path)
    flow = _CapturingFlow.from_client_config(client_config, scopes=[SCOPE])
    flow.present_url = present_url or _print_url

    with quiet_oauth_loggers():
        try:
            credentials = flow.run_local_server(
                host=LOOPBACK_HOST,
                bind_addr=LOOPBACK_HOST,
                port=0,
                authorization_prompt_message=None,
                success_message='Đã nhận xác nhận. Bạn có thể đóng tab này.',
                open_browser=False,
                timeout_seconds=config.consent_timeout_seconds,
                prompt='consent',
            )
        except OAuthFlowError:
            raise
        except WSGITimeoutError:
            raise OAuthConsentTimeoutError('consent timed out; loopback port closed') from None
        except Exception as exc:
            raise OAuthFlowError('oauth consent failed: ' + type(exc).__name__) from None

    granted_raw = flow.oauth2session.token.get('scope')
    if isinstance(granted_raw, str):
        granted = set(granted_raw.split())
    elif isinstance(granted_raw, (list, set, tuple)):
        granted = set(granted_raw)
    else:
        granted = set()

    if not granted or granted != {SCOPE}:
        raise OAuthFlowError('granted scope differs from drive.file')

    refresh = credentials.refresh_token
    if not refresh:
        raise OAuthFlowError('no refresh token was issued')

    try:
        version = store.put(SECRET_REF, SecretValue(refresh))
    except Exception as exc:
        raise OAuthFlowError('secret store write failed: ' + redact_exception(exc)) from None

    return DriveOAuthHandle(SECRET_REF, version, SCOPE)


__all__ = [
    'ACCOUNT_REF',
    'CLIENT_SECRETS_KEY',
    'CONSENT_TIMEOUT_KEY',
    'DriveOAuthConfig',
    'DriveOAuthHandle',
    'LOOPBACK_HOST',
    'OAuthConsentTimeoutError',
    'OAuthFlowError',
    'SCOPE',
    'SECRET_REF',
    'load_client_config',
    'quiet_oauth_loggers',
    'require_client_secrets_outside_git',
    'run_consent',
]

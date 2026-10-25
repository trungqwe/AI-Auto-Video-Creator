"""PP-6: ProfileRouteCatalog, a RouteCatalogPort built from the production profile (CT-AI-ROUTE-001, QR-SEC-009).

The catalog holds the role -> model_ref map of the profile and the alias of the 9Router key. It builds one RouteCandidate per role and takes the account status only from store.current_version(secret_ref): a live key version means ENABLED, none means REVOKED. It never reads a secret value and does no network or database access.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from controlplane.application.config_security.route_resolver import RouteCandidate
from controlplane.domain.config_security.external_account import ExternalAccount
from controlplane.domain.config_security.status_graph import ExternalAccountStatus

PROVIDER_REF = '9router'
QUOTA_DOMAIN_KEY = '9router-gemini'
COST_CLASS = 'free'
MAX_DATA_SENSITIVITY = 'internal'


class SecretVersionPort(Protocol):
    def current_version(self, secret_ref: str) -> int | None: ...


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


class ProfileRouteCatalog:
    def __init__(self, model_refs: Mapping[str, str], account_ref: str, secret_ref: str, store: SecretVersionPort) -> None:
        if not isinstance(model_refs, Mapping) or not model_refs:
            raise ValueError('model_refs must be a non-empty mapping')
        self._model_refs = {
            _require_text(role, 'model_refs role'): _require_text(model_ref, 'model_refs model_ref')
            for role, model_ref in model_refs.items()
        }
        self._roles = frozenset(self._model_refs)
        self._account_ref = _require_text(account_ref, 'account_ref')
        self._secret_ref = _require_text(secret_ref, 'secret_ref')
        self._store = store

    def candidates(self, workspace_id: str, ai_role: str) -> tuple[RouteCandidate, ...]:
        if not isinstance(ai_role, str) or ai_role not in self._model_refs:
            return ()
        model_ref = self._model_refs[ai_role]
        version = self._store.current_version(self._secret_ref)
        account = ExternalAccount(
            external_account_id=self._account_ref,
            workspace_id=workspace_id,
            provider=PROVIDER_REF,
            account_label=self._account_ref,
            status=ExternalAccountStatus.ENABLED if version is not None else ExternalAccountStatus.REVOKED,
            project_ref=None,
            capabilities=self._roles,
            credential_version=version if version is not None else 0,
            credential_updated_at=None,
            credential_expires_at=None,
            quota_observation_ref=None,
            health=None,
            revision=1,
        )
        return (
            RouteCandidate(
                candidate_ref=PROVIDER_REF + ':' + model_ref,
                provider_ref=PROVIDER_REF,
                model_ref=model_ref,
                account=account,
                quota_domain_key=QUOTA_DOMAIN_KEY,
                cost_class=COST_CLASS,
                max_data_sensitivity=MAX_DATA_SENSITIVITY,
                roles=self._roles,
                local=False,
            ),
        )


__all__ = ['ProfileRouteCatalog', 'SecretVersionPort']

"""PP-5: DrivePlacementBootstrap builds drive_placement and drive_fallback_parent_id for ProductionRuntime (CT-STO-003, ADR-0006).

First run creates the root folder and one folder per namespace; later runs verify every stored id with files.get and recreate only the folder that is missing, trashed or not a folder. The state file holds folder names and ids only and is written atomically. Any Drive or state error raises DrivePlacementError; no placement value is ever invented.
ASSUMPTION (D8, OI-PP-02): one 'output' folder, no per-day sub-folder.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from contextlib import ExitStack, closing
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import httplib2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.infrastructure.security.oauth_google_loopback import ACCOUNT_REF
from controlplane.infrastructure.storage.drive_object_store import DriveTokenBrokerPort

_FOLDER_MIME = 'application/vnd.google-apps.folder'
_RETRYABLE_STATUS = frozenset({408, 429})
_STATE_KEYS = frozenset({'root', 'namespaces'})
_ROOT_KEYS = frozenset({'name', 'id'})


class DrivePlacementError(Exception):
    pass


class _TokenUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class DrivePlacement:
    placement: Mapping[str, str]
    fallback_parent_id: str


class _PlacementHttp:
    def __init__(self, inner: httplib2.Http, broker: DriveTokenBrokerPort) -> None:
        self._inner = inner
        self._broker = broker

    def request(
        self,
        uri: str,
        method: str = 'GET',
        body: object = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: object,
    ) -> tuple[httplib2.Response, bytes]:
        merged = dict(headers or {})
        with ExitStack() as stack:
            try:
                token = stack.enter_context(self._broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF))
            except Exception as exc:
                raise _TokenUnavailableError(type(exc).__name__) from None
            if not isinstance(token, str) or not token:
                raise _TokenUnavailableError('empty token')
            merged['Authorization'] = 'Bearer ' + token
            return self._inner.request(uri, method=method, body=body, headers=merged, **kwargs)

    def close(self) -> None:
        self._inner.close()


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_positive(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value > 0


def _read_state(path: Path, root_name: str) -> tuple[str | None, dict[str, str]]:
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None, {}
    except (OSError, UnicodeError):
        raise DrivePlacementError('placement state file cannot be read') from None
    try:
        data = json.loads(text)
    except ValueError:
        raise DrivePlacementError('placement state file is not valid JSON') from None
    root = data.get('root') if isinstance(data, dict) and set(data) == _STATE_KEYS else None
    folders = data.get('namespaces') if root is not None else None
    if not isinstance(root, dict) or set(root) != _ROOT_KEYS or not _is_text(root['name']) or not _is_text(root['id']):
        raise DrivePlacementError('placement state file has an unexpected shape')
    if not isinstance(folders, dict) or not all(_is_text(key) and _is_text(value) for key, value in folders.items()):
        raise DrivePlacementError('placement state file has an unexpected shape')
    if root['name'] != root_name:
        return None, {}
    return root['id'], dict(folders)


def _discard(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _write_state(path: Path, root_name: str, root_id: str, namespaces: Mapping[str, str]) -> None:
    payload = {'root': {'name': root_name, 'id': root_id}, 'namespaces': dict(namespaces)}
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + chr(10)
    temp = path.with_name(path.name + '.tmp')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temp.open('w', encoding='utf-8', newline=chr(10)) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError:
        _discard(temp)
        raise DrivePlacementError('placement state file cannot be written') from None


class DrivePlacementBootstrap:
    def __init__(
        self,
        broker: DriveTokenBrokerPort,
        state_file: Path,
        root_name: str,
        namespaces: tuple[str, ...] | list[str],
        *,
        retry_max_attempts: int,
        backoff_base_seconds: float,
        backoff_cap_seconds: float,
        timeout_seconds: float,
        http_factory: Callable[[float], httplib2.Http] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not isinstance(state_file, Path):
            raise ValueError('state_file must be a Path')
        if not _is_text(root_name):
            raise ValueError('root_name must be a non-empty string')
        if not isinstance(namespaces, (list, tuple)) or not namespaces or not all(_is_text(item) for item in namespaces) or len(set(namespaces)) != len(namespaces):
            raise ValueError('namespaces must be a non-empty list of unique non-empty strings')
        if isinstance(retry_max_attempts, bool) or not isinstance(retry_max_attempts, int) or retry_max_attempts < 1:
            raise ValueError('retry_max_attempts must be an integer >= 1')
        if not _is_positive(backoff_base_seconds):
            raise ValueError('backoff_base_seconds must be a positive number')
        if not _is_positive(backoff_cap_seconds) or backoff_cap_seconds < backoff_base_seconds:
            raise ValueError('backoff_cap_seconds must be >= backoff_base_seconds')
        if not _is_positive(timeout_seconds):
            raise ValueError('timeout_seconds must be a positive number')
        self._broker = broker
        self._state_file = state_file
        self._root_name = root_name
        self._namespaces = tuple(namespaces)
        self._retry_max_attempts = retry_max_attempts
        self._backoff_base = backoff_base_seconds
        self._backoff_cap = backoff_cap_seconds
        self._timeout = timeout_seconds
        self._http_factory = http_factory or (lambda timeout: httplib2.Http(timeout=timeout))
        self._sleep = sleep

    def _open_service(self) -> object:
        return build(
            'drive',
            'v3',
            http=_PlacementHttp(self._http_factory(self._timeout), self._broker),
            static_discovery=True,
            cache_discovery=False,
        )

    def _backoff(self, failures: int) -> float:
        return min(self._backoff_cap, self._backoff_base * 2 ** (failures - 1))

    def _run(self, operation: Callable[[object], object]) -> object:
        failures = 0
        while True:
            try:
                with closing(self._open_service()) as service:
                    return operation(service)
            except _TokenUnavailableError:
                raise DrivePlacementError('Drive access token is unavailable') from None
            except HttpError as exc:
                status = int(exc.resp.status)
                if status not in _RETRYABLE_STATUS and not 500 <= status <= 599:
                    raise DrivePlacementError('Drive request failed: HTTP ' + str(status)) from None
                reason = 'HTTP ' + str(status)
            except ValueError:
                raise DrivePlacementError('Drive returned an unreadable response') from None
            except (OSError, httplib2.HttpLib2Error) as exc:
                reason = type(exc).__name__
            failures += 1
            if failures >= self._retry_max_attempts:
                raise DrivePlacementError('Drive request failed after retries: ' + reason) from None
            self._sleep(self._backoff(failures))

    def _verify(self, folder_id: str) -> bool:
        def fetch(service: object) -> object:
            try:
                return service.files().get(fileId=folder_id, fields='id,trashed,mimeType').execute()  # type: ignore[attr-defined]
            except HttpError as exc:
                if int(exc.resp.status) == 404:
                    return None
                raise

        meta = self._run(fetch)
        return isinstance(meta, dict) and meta.get('id') == folder_id and meta.get('trashed') is not True and meta.get('mimeType') == _FOLDER_MIME

    def _create(self, name: str, parent_id: str | None) -> str:
        body: dict[str, object] = {'name': name, 'mimeType': _FOLDER_MIME}
        if parent_id is not None:
            body['parents'] = [parent_id]

        def create(service: object) -> object:
            return service.files().create(body=body, fields='id').execute()  # type: ignore[attr-defined]

        result = self._run(create)
        folder_id = result.get('id') if isinstance(result, dict) else None
        if not isinstance(folder_id, str) or not folder_id:
            raise DrivePlacementError('Drive returned no folder id')
        return folder_id

    def ensure(self) -> DrivePlacement:
        stored_root, stored = _read_state(self._state_file, self._root_name)
        if stored_root is not None and self._verify(stored_root):
            root_id = stored_root
            namespaces = {name: stored[name] for name in self._namespaces if name in stored}
        else:
            root_id = self._create(self._root_name, None)
            namespaces = {}
            _write_state(self._state_file, self._root_name, root_id, namespaces)
        for name in self._namespaces:
            if name in namespaces and self._verify(namespaces[name]):
                continue
            namespaces[name] = self._create(name, root_id)
            _write_state(self._state_file, self._root_name, root_id, namespaces)
        return DrivePlacement(MappingProxyType({name: namespaces[name] for name in self._namespaces}), root_id)


__all__ = ['DrivePlacement', 'DrivePlacementBootstrap', 'DrivePlacementError']

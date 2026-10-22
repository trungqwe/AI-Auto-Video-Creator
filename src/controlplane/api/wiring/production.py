"""ADAPT-PROD: hồ sơ production cho composition root.

Ghép create_app (/v1/) với UI tĩnh trên cổng loopback TLS, đổi capability một lần thành phiên
và chạy worker Temporal. Mô-đun này không nạp mô-đun test-driver nên mọi đường /test-driver/ trả 404.
Gắn service nguồn của A vào module_services['sources']; hooks và media chưa gắn nên vẫn trả 503.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path
import secrets
from types import MappingProxyType
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles
from temporalio.worker import Worker
import uvicorn

from controlplane.api.main import create_app
from controlplane.api.routes.modules.metadata_update import RevisionConflictError as MetadataRevisionConflictError
from controlplane.api.wiring.collection import build_collection_services, system_dns_resolver
from controlplane.api.wiring.config_security import build_config_security_services
from controlplane.api.wiring.creative import build_creative_services
from controlplane.api.wiring.production_profile import (
    PROFILE_PRODUCTION,
    ProductionProfileError,
    ProductionRuntime,
    WiringConfig,
    load_production_profile,
)
from controlplane.api.wiring.render import build_render_services
from controlplane.api.wiring.storage import build_storage_services
from controlplane.api.wiring.voice import build_voice_services
from controlplane.application.projections.list_query import ListQuery, Page, build_page
from controlplane.application.session_security import BootstrapCapabilityRegistry
from controlplane.domain.orchestration.workflow_catalog import TaskQueue
from controlplane.domain.statemachine import ForbiddenTransitionError
from source_ingestion.application.source_commands import IdempotencyConflictError, SourceCommandHandler, SourceNotFoundError
from source_ingestion.domain.source import Source, SourcePolicy, SourceStatus

LOOPBACK_HOST = '127.0.0.1'
LAUNCH_PATH = '/launch'
SESSION_COOKIE = 'cp_session'
CSRF_COOKIE = 'csrf_token'
PROFILE_PATH_KEY = 'CONTROLPLANE_PROFILE_PATH'
WORKSPACE_ID_KEY = 'CONTROLPLANE_WORKSPACE_ID'
DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[4] / 'tools' / 'launcher' / 'prod' / 'profile.json'
DEFAULT_DIST_DIR = Path(__file__).resolve().parents[2] / 'ui' / 'dist'
RuntimeFactory = Callable[[Any], ProductionRuntime]


def _check_port(port: int) -> None:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Control API port must be within 1..65535')


def production_origins(port: int) -> set[str]:
    _check_port(port)
    return {f'https://{LOOPBACK_HOST}:{port}', f'https://localhost:{port}'}


def load_wiring_config(environ: Mapping[str, str], *, runtime_factory: RuntimeFactory | None) -> WiringConfig:
    """Nạp profile và kiểm đủ tham số trước khi mở DB; thiếu hoặc sai thì ném ProductionProfileError."""
    profile_path = environ.get(PROFILE_PATH_KEY, '').strip() or str(DEFAULT_PROFILE_PATH)
    profile = load_production_profile(profile_path)
    workspace_id = environ.get(WORKSPACE_ID_KEY, '').strip()
    if not workspace_id:
        raise ProductionProfileError(WORKSPACE_ID_KEY, 'missing parameter')
    if runtime_factory is None:
        raise ProductionProfileError('runtime', 'missing parameter')
    runtime = runtime_factory(profile)
    if not isinstance(runtime, ProductionRuntime):
        raise ProductionProfileError('runtime', 'invalid parameter')
    return WiringConfig(mode=PROFILE_PRODUCTION, workspace_id=workspace_id, profile=profile, runtime=runtime)



def _build_services(manager: Any, config: WiringConfig) -> Mapping[str, Any]:
    return MappingProxyType({
        'collection': build_collection_services(manager, config),
        'config_security': build_config_security_services(manager, config),
        'creative': build_creative_services(manager, config),
        'render': build_render_services(manager, config),
        'storage': build_storage_services(manager, config),
        'voice': build_voice_services(manager, config),
    })


SOURCES_RECOVERY_EPOCH = 'control-api-1'
IDEMPOTENCY_REUSED = 'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD'
SOURCE_FIELD_MAP = {'tier': 'tier', 'topic_tags': 'topics', 'notes': 'notes', 'enabled': 'collection_enabled'}


def _utc_text(moment: Any) -> str:
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def _source_row(source: Source) -> dict[str, Any]:
    return {
        'source_id': source.source_id,
        'name': source.name,
        'tier': source.tier,
        'topic_tags': sorted(source.topics),
        'notes': source.notes,
        'enabled': source.status is SourceStatus.ACTIVE,
        'status': source.status.value,
        'revision': source.revision,
        'updated_at': _utc_text(source.updated_at),
    }


def _source_policy(config: Any) -> SourcePolicy:
    profile, _ = config.production_parts()
    return SourcePolicy(
        policy_revision='profile-' + str(profile.revision),
        source_kinds=frozenset(profile.collection.source_kinds),
        tiers=frozenset(profile.parameters['collection.tiers']),
        admin_metadata_keys=frozenset(),
    )


def _source_matches(source: Source, filters: Mapping[str, str]) -> bool:
    wanted = filters.get('status')
    if source.status is SourceStatus.REMOVED_TOMBSTONE and wanted != SourceStatus.REMOVED_TOMBSTONE.value:
        return False
    if wanted is not None and source.status.value != wanted:
        return False
    if 'tier' in filters and source.tier != filters['tier']:
        return False
    return 'topic' not in filters or filters['topic'] in source.topics


class SourceModuleService:
    """Service nguồn của A cho route /v1/sources (H-08, H-09): đọc listing và ghi metadata qua lệnh UpdateSourceMetadata."""

    def __init__(self, *, uow_factory: Callable[[], Any], policy_provider: Callable[[str], SourcePolicy],
                 resolver: Callable[[str], Any], recovery_epoch: str) -> None:
        self._uow_factory = uow_factory
        self._policy_provider = policy_provider
        self._resolver = resolver
        self._recovery_epoch = recovery_epoch

    def fetch_page(self, request: Request, workspace_id: str, query: ListQuery) -> Page:
        filters = dict(query.filters)
        with self._uow_factory() as uow:
            sources = uow.sources.list_sources(workspace_id)
        visible = [s for s in sources if s.workspace_id == workspace_id and _source_matches(s, filters)]
        rows = [_source_row(s) for s in visible]
        descending = query.direction == 'desc'
        rows.sort(key=lambda r: (r[query.sort_key], r['source_id']), reverse=descending)
        if query.cursor is not None:
            after = (query.cursor[0], query.cursor[1])
            rows = [r for r in rows if ((r[query.sort_key], r['source_id']) < after if descending
                                        else (r[query.sort_key], r['source_id']) > after)]
        return build_page(rows[:query.limit + 1], query=query, sort_field=query.sort_key, id_field='source_id')

    def fetch_one(self, request: Request, workspace_id: str, item_id: str) -> dict[str, Any] | None:
        with self._uow_factory() as uow:
            source = uow.sources.get(workspace_id, item_id)
        if source is None or source.workspace_id != workspace_id or source.status is SourceStatus.REMOVED_TOMBSTONE:
            return None
        return _source_row(source)

    def apply_update(self, *, request: Request, item_id: str, expected_revision: int,
                     changes: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        identity = request.state.identity
        workspace_id = identity['workspace_id']
        fields: dict[str, Any] = {}
        for name, value in changes.items():
            if name not in SOURCE_FIELD_MAP or value is None:
                raise ValueError(name + ' is not an updatable value')
            fields[SOURCE_FIELD_MAP[name]] = value
        if 'topics' in fields and not isinstance(fields['topics'], list):
            raise ValueError('topic_tags must be a list')
        handler = SourceCommandHandler(uow=self._uow_factory(), policy_provider=self._policy_provider,
                                       resolver=self._resolver, recovery_epoch=self._recovery_epoch)
        try:
            handler.update_source_metadata(
                workspace_id=workspace_id, idempotency_key=idempotency_key, actor=identity['actor_id'],
                correlation_id=request.state.correlation_id, source_id=item_id,
                expected_revision=expected_revision, **fields)
        except IdempotencyConflictError:
            raise ValueError(IDEMPOTENCY_REUSED) from None
        except ForbiddenTransitionError:
            raise MetadataRevisionConflictError() from None
        with self._uow_factory() as uow:
            source = uow.sources.get(workspace_id, item_id)
        if source is None:
            raise SourceNotFoundError(item_id)
        return _source_row(source)


def compose_sources_module(services: Mapping[str, Any], config: Any) -> SourceModuleService:
    """Ghép service nguồn từ uow_factory của collection và chính sách hồ sơ; không đọc môi trường tiến trình."""
    policy = _source_policy(config)
    return SourceModuleService(
        uow_factory=services['collection'].uow_factory,
        policy_provider=lambda workspace_id: policy,
        resolver=system_dns_resolver,
        recovery_epoch=SOURCES_RECOVERY_EPOCH,
    )


def _problem(status: int, code: str) -> JSONResponse:
    return JSONResponse({'status': status, 'code': code}, status_code=status, media_type='application/problem+json')


def _build_web_app(*, manager: Any, api_app: FastAPI, registry: BootstrapCapabilityRegistry,
                   port: int, dist_dir: Path) -> FastAPI:
    if not (dist_dir / 'index.html').is_file():
        raise FileNotFoundError(f'UI build missing: {dist_dir}')
    hosts = {f'{LOOPBACK_HOST}:{port}', f'localhost:{port}'}
    web_app = FastAPI(title='Control Plane Admin Web UI', docs_url=None, redoc_url=None, openapi_url=None)

    @web_app.get(LAUNCH_PATH)
    def launch(request: Request, cap: str = '') -> Response:
        if request.headers.get('host', '') not in hosts or not cap:
            return _problem(403, 'POLICY_VIOLATION')
        try:
            binding = registry.consume(cap)
        except PermissionError:
            return _problem(403, 'POLICY_VIOLATION')
        with manager.unit_of_work() as uow:
            _, token = api_app.state.session_service.create(connection=uow.connection, binding=binding)
        response = RedirectResponse('/', status_code=303)
        response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=True, samesite='strict', path='/')
        response.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(32), httponly=False, secure=True,
                            samesite='strict', path='/')
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @web_app.api_route('/test-driver/{rest:path}',
                       methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'])
    def reject_test_driver(rest: str) -> Response:
        return _problem(404, 'NOT_FOUND')

    web_app.mount('/', StaticFiles(directory=str(dist_dir), html=True), name='static_ui')
    return web_app



@dataclass(frozen=True)
class ProductionApp:
    """ASGI: /v1/ vào Control API, mọi đường khác vào UI tĩnh và /launch."""

    api_app: FastAPI
    web_app: FastAPI
    bootstrap_registry: BootstrapCapabilityRegistry
    manager: Any
    workspace_id: str
    port: int
    services: Mapping[str, Any]

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get('type') in ('http', 'websocket') and scope.get('path', '').startswith('/v1/'):
            await self.api_app(scope, receive, send)
            return
        await self.web_app(scope, receive, send)

    def launch_url(self, *, actor_id: str, ttl_seconds: int = 60) -> str:
        """Phát capability dùng một lần (TTL tối đa 60 giây) và trả URL /launch cho launcher mở trình duyệt."""
        capability = self.bootstrap_registry.issue(
            workspace_id=self.workspace_id, actor_id=actor_id, ttl_seconds=ttl_seconds)
        return f'https://{LOOPBACK_HOST}:{self.port}{LAUNCH_PATH}?cap={capability}'


def build_production_app(*, manager: Any, config: WiringConfig, port: int,
                         dist_dir: Path | None = None) -> ProductionApp:
    if config.mode != PROFILE_PRODUCTION:
        raise ProductionProfileError('mode', 'not a production profile')
    origins = production_origins(port)
    services = _build_services(manager, config)
    registry = BootstrapCapabilityRegistry()
    api_app = create_app(manager=manager, allowed_origins=origins, bootstrap_registry=registry)
    api_app.state.module_services['sources'] = compose_sources_module(services, config)
    api_app.state.production_services = services
    web_app = _build_web_app(manager=manager, api_app=api_app, registry=registry, port=port,
                             dist_dir=dist_dir or DEFAULT_DIST_DIR)
    return ProductionApp(api_app, web_app, registry, manager, config.workspace_id, port, services)



def loopback_config(app: Any, *, port: int, certfile: Path | str, keyfile: Path | str) -> uvicorn.Config:
    """Chỉ bind 127.0.0.1; chứng chỉ tự ký do launcher tạo ngoài cây Git."""
    _check_port(port)
    return uvicorn.Config(app, host=LOOPBACK_HOST, port=port, ssl_certfile=str(certfile),
                          ssl_keyfile=str(keyfile), log_level='warning', access_log=False)


def serve_production_tls(app: Any, *, port: int, certfile: Path | str, keyfile: Path | str) -> None:
    uvicorn.Server(loopback_config(app, port=port, certfile=certfile, keyfile=keyfile)).run()


class TemporalWorkerGroup:
    """Một Worker cho mỗi task queue; sáu workflow đăng ký ở queue control-workflows.

    Một nhóm chỉ chạy một lần; «chạy lại» là dựng nhóm mới từ cùng registration.
    """

    def __init__(self, client: Any, registration: Any, *, graceful_shutdown_seconds: float,
                 worker_factory: Callable[..., Any] = Worker) -> None:
        if (isinstance(graceful_shutdown_seconds, bool)
                or not isinstance(graceful_shutdown_seconds, (int, float))
                or graceful_shutdown_seconds <= 0):
            raise ValueError('graceful_shutdown_seconds must be positive')
        control = TaskQueue.CONTROL_WORKFLOWS.value
        queues = dict(registration.activities_by_queue)
        queues.setdefault(control, ())
        self._workers = {
            queue: worker_factory(
                client,
                task_queue=queue,
                workflows=list(registration.workflows) if queue == control else [],
                activities=list(activities),
                graceful_shutdown_timeout=timedelta(seconds=graceful_shutdown_seconds),
            )
            for queue, activities in queues.items()
        }
        self._stopped = False

    @property
    def task_queues(self) -> tuple[str, ...]:
        return tuple(self._workers)

    async def run(self) -> None:
        try:
            await asyncio.gather(*(w.run() for w in self._workers.values()))
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Chỉ dừng các worker (ngừng poll, chờ việc đang chạy trong thời gian ân hạn); không hủy hay terminate workflow."""
        if self._stopped:
            return
        self._stopped = True
        await asyncio.gather(*(w.shutdown() for w in self._workers.values()))


__all__ = [
    'DEFAULT_PROFILE_PATH',
    'ProductionApp',
    'SourceModuleService',
    'TemporalWorkerGroup',
    'build_production_app',
    'compose_sources_module',
    'load_wiring_config',
    'loopback_config',
    'production_origins',
    'serve_production_tls',
]

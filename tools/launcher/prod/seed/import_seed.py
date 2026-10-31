from __future__ import annotations

'''ADAPT-SEED: nhập nguồn RSS cơ sở, hook và media seed qua dịch vụ ứng dụng của A và C (không qua UI hay HTTP).'''

from dataclasses import dataclass
import hashlib
import json
import os
import shutil
from pathlib import Path

from catalog.application.discovery import DiscoveryObservation, Disposition, register_discovery
from catalog.application.hooks import import_hook
from catalog.domain.hooks import HookKind
from catalog.domain.identity import CanonicalFingerprint, MediaKind, ProvenanceEntry, ProvenanceRelation
from catalog.persistence.assets import PostgresMediaAssetRepository
from catalog.persistence.hooks import PostgresHookHistory
from controlplane.api.wiring.collection import build_collection_services, system_dns_resolver
from controlplane.api.wiring.production_profile import PROFILE_PRODUCTION
from controlplane.application.storage_meta.handlers import register_staged_artifact
from source_ingestion.application.source_commands import SourceAlreadyRegisteredError, SourceCommandHandler
from source_ingestion.domain.source import SourcePolicy

PROD_DIR = Path(__file__).resolve().parents[1]
SOURCES_JSON = PROD_DIR / 'sources.json'
HOOKS_JSON = PROD_DIR / 'hooks.json'
ACTOR = 'adapt-seed'
CORRELATION_ID = 'adapt-seed'
RECOVERY_EPOCH = 'adapt-seed-1'
SOURCE_TOPICS = ('news',)
SEED_OBSERVED_AT = '2026-10-22T00:00:00Z'
ARTICLE_IMAGE_RIGHTS_STATUS = 'UNVERIFIED'
STAGED_MEDIA_DIR = 'media'
STAGED_OWNER_REF = 'adapt-seed'
STAGED_RETENTION_REF = 'durable'
SEED_RIGHTS_STATUS = 'SELF_GENERATED'


class SeedError(ValueError):
    pass


@dataclass(frozen=True)
class SeedImportReport:
    sources_registered: int = 0
    sources_replayed: int = 0
    sources_existing: int = 0
    hooks_imported: int = 0
    hooks_existing: int = 0
    assets_new: int = 0
    assets_existing: int = 0
    article_image_rights_status: str = ''


@dataclass(frozen=True)
class _SeedItem:
    item_id: str
    media_kind: MediaKind
    hook_kind: HookKind | None
    file_name: str
    sha256: str
    technical: tuple[tuple[str, str], ...]
    path: Path


_GROUPS = (
    ('visual_hooks', MediaKind.CLIP, HookKind.VISUAL_HOOK),
    ('audio_hooks', MediaKind.AUDIO, HookKind.AUDIO_HOOK),
    ('background_images', MediaKind.IMAGE, None),
)
_TECHNICAL_KEYS = ('width', 'height', 'fps', 'duration_ms', 'sample_rate_hz', 'channels')


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _require_https(sources):
    for source in sources:
        if not str(source['url']).startswith('https://'):
            raise SeedError('source ' + str(source['code']) + ' must use https')


def _require_rights(hooks):
    rights = hooks['rights']
    if rights['article_image_rights_status'] != ARTICLE_IMAGE_RIGHTS_STATUS or rights['article_images_in_sample_video'] is not False:
        raise SeedError('article images must stay UNVERIFIED and out of the sample video')


def _collect_items(hooks, seed_dir):
    items = []
    missing = []
    for group, media_kind, hook_kind in _GROUPS:
        for entry in hooks[group]:
            path = Path(seed_dir) / entry['file_name']
            if not path.is_file():
                missing.append(entry['file_name'])
                continue
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            if entry.get('sha256') is not None and entry['sha256'] != sha:
                raise SeedError('sha256 of ' + entry['file_name'] + ' differs from hooks.json')
            technical = tuple((key, str(entry[key])) for key in _TECHNICAL_KEYS if key in entry)
            technical += (('media_sha256', sha), ('recipe_template', entry['recipe']['template']), ('seed_rights_status', hooks['rights']['seed_rights_status']))
            items.append(_SeedItem(entry['id'], media_kind, hook_kind, entry['file_name'], sha, technical, path))
    if missing:
        raise SeedError('missing seed media: ' + ', '.join(missing))
    return items


def _import_sources(manager, config, sources, resolver):
    services = build_collection_services(manager, config)
    profile, _ = config.production_parts()
    policy = SourcePolicy(
        policy_revision='profile-' + str(profile.revision),
        source_kinds=frozenset(profile.collection.source_kinds),
        tiers=frozenset(profile.parameters['collection.tiers']),
        admin_metadata_keys=frozenset(),
    )
    handler = SourceCommandHandler(
        uow=services.uow_factory(),
        policy_provider=lambda workspace_id: policy,
        resolver=resolver,
        recovery_epoch=RECOVERY_EPOCH,
    )
    registered = replayed = existing = 0
    for source in sources:
        try:
            result = handler.register_source(
                workspace_id=config.workspace_id,
                idempotency_key='adapt-seed:source:' + source['code'],
                actor=ACTOR,
                correlation_id=CORRELATION_ID,
                locator=source['url'],
                name=source['code'],
                source_kind=source['source_kind'],
                tier=source['tier'],
                topics=SOURCE_TOPICS,
                collection_enabled=source['enabled'],
            )
        except SourceAlreadyRegisteredError:
            existing += 1
            continue
        if result.replayed:
            replayed += 1
        else:
            registered += 1
    return registered, replayed, existing


def _import_items(manager, workspace_id, items):
    counts = {'assets_new': 0, 'assets_existing': 0, 'hooks_imported': 0, 'hooks_existing': 0}
    with manager.borrow_connection() as connection:
        assets = PostgresMediaAssetRepository(connection, workspace_id)
        history = PostgresHookHistory(connection, workspace_id)
        for item in items:
            provenance = ProvenanceEntry(None, None, None, 'seed://' + item.file_name, SEED_OBSERVED_AT, ProvenanceRelation.USER_IMPORTED)
            observation = DiscoveryObservation('adapt-seed:' + item.item_id, item.media_kind, provenance, CanonicalFingerprint(item.sha256), True)
            result = register_discovery(assets, observation, 'seed-' + item.item_id)
            counts['assets_new' if result.disposition is Disposition.NEW_ASSET else 'assets_existing'] += 1
            if item.hook_kind is None:
                continue
            try:
                history.latest(item.item_id)
            except KeyError:
                import_hook(
                    history,
                    hook_id=item.item_id,
                    kind=item.hook_kind,
                    artifact_version_ref='seed:' + item.item_id + ':sha256:' + item.sha256,
                    tags=('seed', item.hook_kind.value, item.item_id),
                    description='Seed hook ' + item.item_id,
                    note='',
                    enabled=True,
                    technical_metadata=item.technical + (('media_asset_id', result.media_asset_id),),
                )
                counts['hooks_imported'] += 1
            else:
                counts['hooks_existing'] += 1
        connection.commit()
    return counts


def _stage_image(staging_root, item):
    media_dir = Path(staging_root) / STAGED_MEDIA_DIR
    media_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(item.file_name).suffix.lower()
    target = media_dir / (item.sha256 + suffix)
    if target.is_file() and target.stat().st_size == item.path.stat().st_size:
        return target
    part = media_dir / (item.sha256 + suffix + '.part')
    try:
        shutil.copyfile(item.path, part)
        os.replace(part, target)
    finally:
        part.unlink(missing_ok=True)
    return target


def _stage_items(manager, workspace_id, staging_root, items):
    staging_root = Path(staging_root)
    for item in items:
        target = _stage_image(staging_root, item)
        register_staged_artifact(
            manager,
            workspace_id=workspace_id,
            staging_root=staging_root,
            owner_ref=STAGED_OWNER_REF,
            relative_ref=STAGED_MEDIA_DIR + '/' + target.name,
            retention_ref=STAGED_RETENTION_REF,
        )


def _import_media(manager, workspace_id, staging_root, items):
    counts = _import_items(manager, workspace_id, items)
    _stage_items(manager, workspace_id, staging_root, items)
    return counts


def import_seed(manager, config, seed_dir, *, resolver=system_dns_resolver, sources_path=SOURCES_JSON, hooks_path=HOOKS_JSON):
    '''Nhập nguồn trước, rồi hook và tài sản seed, sau đó chép ảnh nền, hook clip và hook âm thanh vào staging và đăng ký version; mọi kiểm tra đầu vào chạy trước khi ghi dòng nào; chạy lại không nhân đôi và bù được tệp seed còn thiếu.'''
    if config.mode != PROFILE_PRODUCTION:
        raise SeedError('import_seed requires the production profile on PostgreSQL')
    sources = _read_json(sources_path)['sources']
    hooks = _read_json(hooks_path)
    _require_https(sources)
    _require_rights(hooks)
    items = _collect_items(hooks, seed_dir)
    registered, replayed, existing = _import_sources(manager, config, sources, resolver)
    _, runtime = config.production_parts()
    counts = _import_media(manager, config.workspace_id, runtime.staging_root, items)
    return SeedImportReport(
        registered,
        replayed,
        existing,
        counts['hooks_imported'],
        counts['hooks_existing'],
        counts['assets_new'],
        counts['assets_existing'],
        ARTICLE_IMAGE_RIGHTS_STATUS,
    )


def import_seed_media(manager, *, workspace_id, staging_root, seed_dir, hooks_path=HOOKS_JSON):
    '''Nhập riêng bộ media seed tự tạo: kiểm quyền SELF_GENERATED và mọi tệp trước khi ghi dòng nào, rồi nhập tài sản và hook, chép vào staging và đăng ký version; không đăng ký nguồn, không gọi DNS; chạy lại không nhân đôi.'''
    hooks = _read_json(hooks_path)
    if hooks['rights']['seed_rights_status'] != SEED_RIGHTS_STATUS:
        raise SeedError('seed media must be ' + SEED_RIGHTS_STATUS)
    items = _collect_items(hooks, seed_dir)
    counts = _import_media(manager, workspace_id, staging_root, items)
    return SeedImportReport(
        hooks_imported=counts['hooks_imported'],
        hooks_existing=counts['hooks_existing'],
        assets_new=counts['assets_new'],
        assets_existing=counts['assets_existing'],
        article_image_rights_status=ARTICLE_IMAGE_RIGHTS_STATUS,
    )

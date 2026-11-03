"""IMGGEN-PIPE: activity GenerateIllustrations, the first activity of media_select (DESIGN wave 42 section 4, Control decisions 9).

AI illustrations generated on this machine (FLUX 3 Image Klein in the IMGGEN-SVC sidecar) become ordinary media candidates of
SelectCreativeAssets. One run: load the snapshot, script and analysis named by the input refs; S = script segments, A = distinct
media candidates whose provenance origin is not seed (article images and earlier AI images of the same article); n =
min(MAX_AI_IMAGES_PER_VIDEO, max(0, min(S, TARGET_DISTINCT_IMAGES) - A)); n = 0 succeeds with no output. Otherwise one sidecar job
per operation key (job id = sha256('<workspace>:<operation_key>')[:32]). Its body is written once to
<staging>/illustrations/<job id>.json and posted unchanged on every rerun, so the sidecar returns the same job (idempotent) and
queues again the items that failed with a retryable error. Captions: one plan call (role illustration, up to MAX_STYLE_IMAGES
article images scaled to at most STYLE_IMAGE_MAX_SIDE px) gives a style card and n distinct shots; one caption call per shot with the
pinned BFL t2i system prompt (read from the hub by path, SHA-256 checked, never vendored); code checks each caption and retries once
with the reason, then drops the shot. Text-to-image only. Every finished PNG is checked (signature, size, sha256), written to
<staging>/media/<sha256>.png, registered with register_staged_artifact then register_discovery (relation ai_generated, locator
aigen://flux-3-image-klein/337337621b85/<sha256>, article_ref = first article of the snapshot, shared by the videos of that
article) and returned as one ai_illustration ref.
When generation is impossible: A >= 1 succeeds with the warning illustration_skipped:<code> (scenes reuse article images); A = 0
fails, retryable, with illustration_service_unavailable or illustration_generation_failed. A job still queued or running when the
activity has blocked ILLUSTRATION_WAIT_SECONDS answers waiting with ILLUSTRATION_QUEUED and the rerun reaches the same job; a job
older than MAX_JOB_AGE_SECONDS gives up. The video is never background-only and no fallback is silent.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import json
import re
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from catalog.application.discovery import DiscoveryObservation, register_discovery
from catalog.domain.identity import CanonicalFingerprint, MediaKind, ProvenanceEntry, ProvenanceRelation
from controlplane.api.wiring._shared import resolve_under_root
from controlplane.api.wiring.workflow import media_assets_opener, service_handler, staged_artifact_registrar
from controlplane.application.model_json import ModelJsonError, parse_model_json_object
from controlplane.application.orchestration.workflows.activities import (
    INVALID_ACTIVITY_REQUEST,
    ActivityRejected,
    to_execution_grant,
)
from controlplane.infrastructure.production_ports.imagegen_client import (
    ImagegenBusy,
    ImagegenClient,
    ImagegenRejected,
    ImagegenUnavailable,
)
from controlplane.infrastructure.production_ports.vision_route import VisionRouteError
from creative.domain.asset_selection import SelectionRejected
from creative.domain.illustration import (
    SHOT_KINDS,
    CaptionProblem,
    IllustrationPlanError,
    caption_message,
    check_caption,
    explain,
    parse_plan,
)

ACTIVITY_NAME = 'GenerateIllustrations'
AI_ROLE = 'illustration'
MAX_AI_IMAGES_PER_VIDEO = 4
TARGET_DISTINCT_IMAGES = 5
MAX_STYLE_IMAGES = 2
STYLE_IMAGE_MAX_SIDE = 1024
IMAGE_WIDTH = 864
IMAGE_HEIGHT = 1536
IMAGE_STEPS = 16
MAX_CAPTION_CHARS = 4000
ILLUSTRATION_WAIT_SECONDS = 480.0
POLL_INTERVAL_SECONDS = 5.0
MAX_JOB_AGE_SECONDS = 3600.0
MIN_CALL_SECONDS = 20.0
CALL_MARGIN_SECONDS = 5.0
ILLUSTRATION_SERVICE_UNAVAILABLE = 'illustration_service_unavailable'
ILLUSTRATION_GENERATION_FAILED = 'illustration_generation_failed'
ILLUSTRATION_QUEUED = 'ILLUSTRATION_QUEUED'
SKIPPED_WARNING_PREFIX = 'illustration_skipped:'
REF_AI_ILLUSTRATION = 'ai_illustration'
MODEL_NAME = 'flux-3-image-klein'
MODEL_REVISION = '337337621b8526e120f2275d250242f4a6bedd75'
PUP_REPO = 'black-forest-labs/flux-3-image-klein-pup'
PUP_REVISION = '3f3edb52b2c55de0d49feab28598b68f7f8e4830'
PUP_SYSTEM_PROMPTS_SHA256 = 'b5da3ed8bc04ab59dbdb747930f7dbff847e868903fed8028f85ee1a4ac82fb4'
CAPTION_SYSTEM_PROMPT_KEY = 't2i'
PROVENANCE_SOURCE_REF = 'imggen-pipe'
JOB_DIR = 'illustrations'
MEDIA_DIR = 'media'
ORIGIN_SEED = 'seed'
ORIGIN_ARTICLE = 'article'
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
PLAN_SYSTEM_PROMPT = (
    'You plan documentary photographs that illustrate a short vertical news video. '
    'Answer with one JSON object only, without commentary.'
)
_ASSET_NAMESPACE = uuid.UUID('6c1f3f4e-5a2b-4f0e-9d5c-1d1a6a0c2b7e')
_ITEM_KEYS = frozenset({'item_id', 'caption', 'width', 'height', 'steps', 'seed'})
_JOB_ID = re.compile(r'[0-9a-f]{32}')


class IllustrationInputError(Exception):
    def __init__(self, code: str, reason: str) -> None:
        self.code = code
        self.reason = reason
        super().__init__(f'{code}: {reason}')


class _Impossible(Exception):
    """Generation cannot finish in this run: `code` is one of the two registered failure codes, `detail` a fixed reason."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f'{code}: {detail}')


class _OutOfTime(Exception):
    pass


@dataclass(frozen=True)
class IllustrationContext:
    snapshot: Any
    article_id: str | None
    scene_intents: tuple[str, ...]
    topic: str
    entity_names: tuple[str, ...]


def illustration_count(segments: int, non_seed: int) -> int:
    """n: images to generate for a video of `segments` script segments that already has `non_seed` distinct non-seed images."""
    return min(MAX_AI_IMAGES_PER_VIDEO, max(0, min(segments, TARGET_DISTINCT_IMAGES) - non_seed))


def illustration_job_id(workspace_id: str, operation_key: str) -> str:
    return hashlib.sha256(f'{workspace_id}:{operation_key}'.encode('utf-8')).hexdigest()[:32]


def derive_seed(job_id: str, item_id: str) -> int:
    """The seed of an item: the first 63 bits of sha256('<job_id>:<item_id>'), as the sidecar protocol documents."""
    return int.from_bytes(hashlib.sha256(f'{job_id}:{item_id}'.encode('utf-8')).digest()[:8], 'big') >> 1


def ai_locator(sha256: str) -> str:
    return f'aigen://{MODEL_NAME}/{MODEL_REVISION[:12]}/{sha256}'


def png_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) from the IHDR chunk of a PNG, None when `data` is not a PNG."""
    if len(data) < 24 or not data.startswith(PNG_SIGNATURE) or data[12:16] != b'IHDR':
        return None
    return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')


def _one_line(value: object) -> str:
    return ' '.join(str(value).split()) if value is not None else ''


def plan_message(context: IllustrationContext, count: int, with_images: bool, retry_reason: str | None = None) -> str:
    """User text of the plan call: exactly `count` shot requests drawn from the scene intents, plus one style card."""
    lines = [
        f'Plan exactly {count} photographs for a vertical 9:16 news video.',
        'Return one JSON object with the members style_card and requests.',
        'style_card holds the text members palette, light, contrast, grain, lens, depth_of_field, weather and mood, each a short physical fact of the photographs'
        + (', taken from the attached article photographs.' if with_images else '.'),
        f'requests is a list of exactly {count} objects with the text members shot, scene_intent and description. shot is one of '
        + ', '.join(SHOT_KINDS) + ' and every request uses a different shot. scene_intent repeats one scene intent below. '
        'description is one sentence about what the camera sees.',
        'Show people only as small anonymous figures seen from a distance or from behind. Keep uniforms, vehicles, walls and objects '
        'plain and unmarked. Choose calm moments: the setting before or after the event, a telling object, a wide view of the place.',
    ]
    if with_images:
        lines.append('Use the attached photographs only for palette, light, contrast, grain and weather, and give every request a moment and framing of its own.')
    lines.append('TOPIC: ' + _one_line(context.topic))
    lines.append('SCENE INTENTS:')
    lines.extend('- ' + _one_line(intent) for intent in context.scene_intents)
    if retry_reason:
        lines.append('RETRY REASON: ' + _one_line(retry_reason))
    return '\n'.join(lines)


def pinned_caption_system_prompt(hub_dir: Path | None) -> Callable[[], str]:
    """Loader of the BFL t2i system prompt from the pinned pup snapshot in the hub; _Impossible(service unavailable) when absent or
    when its SHA-256 differs from PUP_SYSTEM_PROMPTS_SHA256 (the file is downloaded on the user's machine, never vendored)."""

    def load() -> str:
        if hub_dir is None:
            raise _Impossible(ILLUSTRATION_SERVICE_UNAVAILABLE, 'hub_unknown')
        path = Path(hub_dir) / ('models--' + PUP_REPO.replace('/', '--')) / 'snapshots' / PUP_REVISION / 'system_prompts.json'
        try:
            data = path.read_bytes()
        except OSError:
            raise _Impossible(ILLUSTRATION_SERVICE_UNAVAILABLE, 'system_prompts_missing') from None
        if hashlib.sha256(data).hexdigest() != PUP_SYSTEM_PROMPTS_SHA256:
            raise _Impossible(ILLUSTRATION_SERVICE_UNAVAILABLE, 'system_prompts_mismatch')
        try:
            text = json.loads(data.decode('utf-8')).get(CAPTION_SYSTEM_PROMPT_KEY)
        except (UnicodeDecodeError, ValueError, AttributeError):
            text = None
        if not isinstance(text, str) or not text.strip():
            raise _Impossible(ILLUSTRATION_SERVICE_UNAVAILABLE, 'system_prompts_invalid')
        return text

    return load


def ffmpeg_preview(ffmpeg: Path, *, max_side: int = STYLE_IMAGE_MAX_SIDE, timeout: float = 30.0) -> Callable[[Path], tuple[bytes, str] | None]:
    """JPEG of an image scaled down to at most `max_side` px per side with the pinned FFmpeg; None when FFmpeg cannot read it."""

    def preview(source: Path) -> tuple[bytes, str] | None:
        scale = f"scale='min({max_side},iw)':'min({max_side},ih)':force_original_aspect_ratio=decrease"
        command = [str(ffmpeg), '-v', 'error', '-nostdin', '-i', str(source), '-frames:v', '1', '-vf', scale,
                   '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q:v', '4', '-']
        try:
            done = subprocess.run(command, capture_output=True, timeout=timeout, check=False,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode != 0 or not done.stdout.startswith(b'\xff\xd8'):
            return None
        return done.stdout, 'image/jpeg'

    return preview


def _last_ref_id(refs: Sequence[Mapping[str, Any]], ref_type: str) -> str:
    found = [ref.get('ref_id') for ref in refs if isinstance(ref, Mapping) and ref.get('ref_type') == ref_type]
    found = [item for item in found if isinstance(item, str) and item.strip()]
    if not found:
        raise IllustrationInputError('INPUT_NOT_READY', f'missing_{ref_type}_ref')
    return found[-1]


class CreativeIllustrationInputs:
    """Snapshot, script and analysis of the job from the unit of work of D (read only)."""

    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    def load(self, refs: Sequence[Mapping[str, Any]]) -> IllustrationContext:
        snapshot_id = _last_ref_id(refs, 'production_snapshot')
        script_id = _last_ref_id(refs, 'script_version')
        analysis_id = _last_ref_id(refs, 'content_analysis')
        with self._uow_factory() as uow:
            snapshot = uow.snapshots.get(snapshot_id)
            script = uow.scripts.latest(script_id)
            analysis = uow.analyses.latest(analysis_id)
        if snapshot is None:
            raise IllustrationInputError('INPUT_NOT_READY', 'snapshot_not_committed')
        if script is None:
            raise IllustrationInputError('INPUT_NOT_READY', 'script_not_found')
        if analysis is None:
            raise IllustrationInputError('INPUT_NOT_READY', 'analysis_not_found')
        articles = [ref.get('ref_id') for ref in snapshot.source_refs if ref.get('ref_type') == 'article_revision']
        articles = [item.strip() for item in articles if isinstance(item, str) and item.strip()]
        names = tuple(dict.fromkeys(entity.name.strip() for entity in analysis.record.entities if entity.name.strip()))
        return IllustrationContext(snapshot, articles[0] if articles else None, tuple(script.record.scene_intents),
                                   str(analysis.record.topic), names)


def _result(disposition: str, refs: Sequence[Mapping[str, str]] = (), *, problem: Mapping[str, Any] | None = None,
            metrics: Mapping[str, Any] | None = None, warnings: Sequence[str] = ()) -> dict[str, Any]:
    outcome: dict[str, Any] = {'disposition': disposition, 'output_refs': [dict(ref) for ref in refs]}
    if problem is not None:
        outcome['problem'] = dict(problem)
    if metrics is not None:
        outcome['metrics'] = dict(metrics)
    if warnings:
        outcome['warnings'] = list(dict.fromkeys(warnings))
    return outcome


def _utc_text(moment: datetime.datetime) -> str:
    return moment.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class IllustrationService:
    """The service of GenerateIllustrations for service_handler: (request, claims) -> outcome (disposition, refs, problem)."""

    def __init__(
        self, *, workspace_id: str, inputs: Any, media: Any, route: Any, client: Any, system_prompt: Callable[[], str],
        preview: Callable[[Path], tuple[bytes, str] | None], register_version: Callable[[Path, str], str],
        open_assets: Callable[[str], Any], staging_root: Path, grants: Any, clock: Callable[[], datetime.datetime],
        monotonic: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
        request_timeout: float = 120.0, wait_seconds: float = ILLUSTRATION_WAIT_SECONDS,
        poll_seconds: float = POLL_INTERVAL_SECONDS, min_call_seconds: float = MIN_CALL_SECONDS,
    ) -> None:
        self._workspace_id = workspace_id
        self._inputs = inputs
        self._media = media
        self._route = route
        self._client = client
        self._system_prompt = system_prompt
        self._preview = preview
        self._register_version = register_version
        self._open_assets = open_assets
        self._staging_root = Path(staging_root)
        self._grants = grants
        self._clock = clock
        self._monotonic = monotonic
        self._sleep = sleep
        self._request_timeout = float(request_timeout)
        self._wait_seconds = float(wait_seconds)
        self._poll_seconds = float(poll_seconds)
        self._min_call_seconds = float(min_call_seconds)

    # -- entry -------------------------------------------------------------------------------------------------------------------
    def __call__(self, request: Mapping[str, Any], claims: Any) -> dict[str, Any]:
        video_job_id = request.get('video_job_id')
        operation_key = request.get('operation_key')
        if not isinstance(video_job_id, str) or not video_job_id.strip() or not isinstance(operation_key, str) or not operation_key:
            raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
        if not self._grant_current(claims, video_job_id):
            return _result('stale', problem={'code': 'STALE_GRANT', 'retryable': True, 'message': 'execution grant is no longer current'})
        deadline = self._monotonic() + self._wait_seconds
        try:
            context = self._inputs.load(request.get('input_refs') or ())
            candidates = self._media.media_candidates(workspace_id=self._workspace_id, snapshot=context.snapshot)
        except IllustrationInputError as error:
            return _result('failed', problem={'code': error.code, 'retryable': False, 'message': error.reason})
        except SelectionRejected as error:
            return _result('failed', problem={'code': error.code, 'retryable': False, 'message': str(error.reason)})
        non_seed = len({item.media_asset_id for item in candidates if item.provenance.get('origin') != ORIGIN_SEED})
        count = illustration_count(len(context.scene_intents), non_seed)
        metrics: dict[str, Any] = {'segments': len(context.scene_intents), 'non_seed_candidates': non_seed, 'requested': count, 'generated': 0}
        if count == 0:
            return _result('succeeded', metrics=metrics)
        warnings: list[str] = []
        try:
            if context.article_id is None:
                raise _Impossible(ILLUSTRATION_GENERATION_FAILED, 'snapshot_without_article')
            refs = self._generate(illustration_job_id(self._workspace_id, operation_key), context, candidates, count, deadline,
                                  claims, video_job_id, metrics, warnings)
        except _OutOfTime:
            return self._waiting(metrics, warnings)
        except ImagegenBusy:
            return self._waiting(metrics, warnings)
        except ImagegenUnavailable as error:
            return self._impossible(_Impossible(ILLUSTRATION_SERVICE_UNAVAILABLE, error.code), non_seed, metrics, warnings)
        except ImagegenRejected as error:
            return self._impossible(_Impossible(ILLUSTRATION_GENERATION_FAILED, error.code), non_seed, metrics, warnings)
        except _Impossible as error:
            return self._impossible(error, non_seed, metrics, warnings)
        if refs is None:
            return _result('stale', problem={'code': 'STALE_GRANT', 'retryable': True, 'message': 'execution grant is no longer current'})
        metrics['generated'] = len(refs)
        return _result('succeeded', refs, metrics=metrics, warnings=warnings)

    def _grant_current(self, claims: Any, video_job_id: str) -> bool:
        if self._grants is None or claims is None:
            return True
        return bool(self._grants.is_grant_current(to_execution_grant(claims, workspace_id=self._workspace_id, job_id=video_job_id)))

    def _waiting(self, metrics: Mapping[str, Any], warnings: Sequence[str]) -> dict[str, Any]:
        return _result('waiting', problem={'code': ILLUSTRATION_QUEUED, 'retryable': True,
                                           'message': 'the illustration job is still queued or running on the local sidecar'},
                       metrics=metrics, warnings=warnings)

    def _impossible(self, error: _Impossible, non_seed: int, metrics: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
        metrics = {**metrics, 'skipped': error.code, 'detail': error.detail}
        if non_seed >= 1:
            return _result('succeeded', metrics=metrics, warnings=[*warnings, SKIPPED_WARNING_PREFIX + error.code])
        return _result('failed', problem={'code': error.code, 'retryable': True, 'message': f'no illustration for a video without article images: {error.detail}'},
                       metrics=metrics, warnings=warnings)

    # -- job ---------------------------------------------------------------------------------------------------------------------
    def _generate(self, job_id: str, context: IllustrationContext, candidates: Sequence[Any], count: int, deadline: float,
                  claims: Any, video_job_id: str, metrics: dict[str, Any], warnings: list[str]) -> list[dict[str, str]] | None:
        stored = self._load_job(job_id)
        if stored is None:
            self._client.health()
            body = self._write_body(job_id, context, candidates, count, deadline, metrics, warnings)
            stored = self._save_job(job_id, context.article_id, body)
        view = self._client.submit(stored['body'])
        view = self._wait_for(job_id, stored, view, deadline)
        if view is None:
            if self._age_seconds(stored) > MAX_JOB_AGE_SECONDS:
                raise _Impossible(ILLUSTRATION_GENERATION_FAILED, 'job_timeout')
            raise _OutOfTime()
        if not self._grant_current(claims, video_job_id):
            return None
        refs = self._collect(job_id, stored, view, context.article_id, warnings)
        if not refs:
            raise _Impossible(ILLUSTRATION_GENERATION_FAILED, 'no_image')
        return refs

    def _job_path(self, job_id: str) -> Path:
        return self._staging_root / JOB_DIR / f'{job_id}.json'

    def _load_job(self, job_id: str) -> dict[str, Any] | None:
        try:
            stored = json.loads(self._job_path(job_id).read_text(encoding='utf-8'))
            body = stored['body']
            items = body['items']
            datetime.datetime.fromisoformat(stored['created_at'])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        valid = (stored.get('job_id') == job_id and body.get('job_id') == job_id and isinstance(items, list) and 1 <= len(items) <= 6
                 and all(isinstance(item, dict) and set(item) == _ITEM_KEYS for item in items) and isinstance(stored.get('article_id'), str))
        return stored if valid else None

    def _save_job(self, job_id: str, article_id: str, body: dict[str, Any]) -> dict[str, Any]:
        stored = {'job_id': job_id, 'article_id': article_id, 'created_at': self._clock().astimezone(datetime.timezone.utc).isoformat(),
                  'model': f'{MODEL_NAME}@{MODEL_REVISION}', 'body': body}
        path = self._job_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + '.part')
        part.write_text(json.dumps(stored, ensure_ascii=False, indent=1), encoding='utf-8')
        part.replace(path)
        return stored

    def _age_seconds(self, stored: Mapping[str, Any]) -> float:
        created = datetime.datetime.fromisoformat(stored['created_at'])
        return (self._clock() - created).total_seconds()

    def _wait_for(self, job_id: str, stored: Mapping[str, Any], view: Mapping[str, Any], deadline: float) -> Mapping[str, Any] | None:
        """Polls the job until every item is done or failed without a retry left; None when the deadline comes first."""
        while True:
            items = view.get('items') or []
            if all(isinstance(item, Mapping) and item.get('state') in ('done', 'failed') for item in items):
                again = [item for item in items if item.get('state') == 'failed' and isinstance(item.get('error'), Mapping)
                         and item['error'].get('retryable') is True]
                if not again:
                    return view
                self._client.submit(stored['body'])  # the same body queues again the items with a retry left
            if self._monotonic() + self._poll_seconds > deadline:
                return None
            self._sleep(self._poll_seconds)
            current = self._client.job(job_id)
            view = current if current is not None else self._client.submit(stored['body'])

    def _collect(self, job_id: str, stored: Mapping[str, Any], view: Mapping[str, Any], article_id: str, warnings: list[str]) -> list[dict[str, str]]:
        requested = {item['item_id']: item for item in stored['body']['items']}
        refs: dict[str, dict[str, str]] = {}
        for item in view.get('items') or []:
            item_id = item.get('item_id')
            wanted = requested.get(item_id)
            if wanted is None:
                continue
            if item.get('state') != 'done':
                error = item.get('error') if isinstance(item.get('error'), Mapping) else {}
                warnings.append(f"illustration_item_failed:{error.get('code') or item.get('state')}")
                continue
            data, sha256 = self._client.png(job_id, item_id)
            if sha256 != item.get('sha256') or png_size(data) != (wanted['width'], wanted['height']):
                warnings.append('illustration_item_failed:png_mismatch')
                continue
            path = self._stage(data, sha256)
            version_id = self._register_version(path, article_id)
            asset_id = self._register_asset(sha256, article_id)
            refs.setdefault(asset_id, {'ref_type': REF_AI_ILLUSTRATION, 'ref_id': asset_id, 'revision_id': version_id})
        return list(refs.values())

    def _stage(self, data: bytes, sha256: str) -> Path:
        media = self._staging_root / MEDIA_DIR
        media.mkdir(parents=True, exist_ok=True)
        target = media / f'{sha256}.png'
        if target.is_file() and target.stat().st_size == len(data):
            return target
        part = media / f'{sha256}.png.part'
        try:
            part.write_bytes(data)
            part.replace(target)
        finally:
            part.unlink(missing_ok=True)
        return target

    def _register_asset(self, sha256: str, article_id: str) -> str:
        entry = ProvenanceEntry(PROVENANCE_SOURCE_REF, article_id, None, ai_locator(sha256), _utc_text(self._clock()), ProvenanceRelation.AI_GENERATED)
        observation = DiscoveryObservation(f'aigen:{article_id}:{sha256}', MediaKind.IMAGE, entry, CanonicalFingerprint(sha256), True)
        with self._open_assets(self._workspace_id) as assets:
            result = register_discovery(assets, observation, 'ma-' + str(uuid.uuid5(_ASSET_NAMESPACE, 'aigen:' + sha256)))
        if result.media_asset_id is None:
            raise _Impossible(ILLUSTRATION_GENERATION_FAILED, 'catalog_rejected')
        return result.media_asset_id

    # -- captions ----------------------------------------------------------------------------------------------------------------
    def _chat(self, system: str, text: str, images: Sequence[tuple[str, str]], deadline: float) -> str:
        remaining = deadline - self._monotonic()
        if remaining < self._min_call_seconds:
            raise _OutOfTime()
        invoke = getattr(self._route, 'invoke_chat', None)
        if not callable(invoke):
            raise _Impossible(ILLUSTRATION_SERVICE_UNAVAILABLE, 'route_without_chat')
        try:
            return invoke(AI_ROLE, system, text, tuple(images), timeout=min(self._request_timeout, max(remaining - CALL_MARGIN_SECONDS, remaining / 2)))
        except VisionRouteError as error:
            raise _Impossible(ILLUSTRATION_GENERATION_FAILED, 'route_' + error.code) from None

    def _style_images(self, candidates: Sequence[Any]) -> list[tuple[str, str]]:
        images: list[tuple[str, str]] = []
        for item in candidates:
            if len(images) >= MAX_STYLE_IMAGES:
                break
            if item.provenance.get('origin') != ORIGIN_ARTICLE:
                continue
            try:
                path = resolve_under_root(self._staging_root, str(item.artifact_version_ref))
                if hashlib.sha256(path.read_bytes()).hexdigest() != item.provenance.get('sha256'):
                    continue
            except (ValueError, OSError):
                continue
            found = self._preview(path)
            if found is not None:
                images.append((base64.b64encode(found[0]).decode('ascii'), found[1]))
        return images

    def _plan(self, context: IllustrationContext, count: int, images: Sequence[tuple[str, str]], deadline: float) -> Any:
        reason = None
        for _ in range(2):
            raw = self._chat(PLAN_SYSTEM_PROMPT, plan_message(context, count, bool(images), reason), images, deadline)
            try:
                return parse_plan(parse_model_json_object(raw), count)
            except ModelJsonError as error:
                reason = f'Answer with one JSON object only ({error.reason}).'
            except IllustrationPlanError as error:
                reason = f'Fix the member {error.field} ({error.code}).'
        raise _Impossible(ILLUSTRATION_GENERATION_FAILED, 'plan_invalid')

    def _caption(self, system: str, shot: Any, style_card: Any, names: Sequence[str], deadline: float) -> str | None:
        reason = None
        for _ in range(2):
            caption = _one_line(self._chat(system, caption_message(shot, style_card, reason), (), deadline))
            problems = check_caption(caption, tuple(names))
            if len(caption) > MAX_CAPTION_CHARS:
                problems = (*problems, CaptionProblem('too_long', str(len(caption.split()))))
            if not problems:
                return caption
            reason = explain(problems)
        return None

    def _write_body(self, job_id: str, context: IllustrationContext, candidates: Sequence[Any], count: int, deadline: float,
                    metrics: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
        system = self._system_prompt()
        plan = self._plan(context, count, self._style_images(candidates), deadline)
        items = []
        for index, shot in enumerate(plan.requests):
            caption = self._caption(system, shot, plan.style_card, context.entity_names, deadline)
            if caption is None:
                warnings.append('illustration_caption_dropped:' + shot.shot)
                continue
            item_id = f"shot-{index}-{shot.shot.replace('_', '-')}"
            items.append({'item_id': item_id, 'caption': caption, 'width': IMAGE_WIDTH, 'height': IMAGE_HEIGHT,
                          'steps': IMAGE_STEPS, 'seed': derive_seed(job_id, item_id)})
        metrics['dropped_captions'] = count - len(items)
        if not items:
            raise _Impossible(ILLUSTRATION_GENERATION_FAILED, 'no_caption')
        return {'job_id': job_id, 'items': items}


def illustration_activity_handlers(
    *, manager: Any, workspace_id: str, profile: Any, runtime: Any, creative_uow_factory: Callable[[], Any], media: Any, grants: Any,
    clock: Callable[[], datetime.datetime], endpoint_file: Path | None, hub_dir: Path | None,
) -> dict[str, Any]:
    """Handler of GenerateIllustrations for the launcher composition. Reads no file and opens no connection while building; the
    sidecar endpoint file (written by the launcher) and the pinned system prompt are read on every run."""
    route_model_refs = getattr(getattr(profile, 'ai', None), 'route_model_refs', None) or {}
    if AI_ROLE not in route_model_refs:
        raise ValueError('the production profile has no AI role illustration (ai.route_model_refs.illustration, IMGGEN-ROLE)')
    service = IllustrationService(
        workspace_id=workspace_id,
        inputs=CreativeIllustrationInputs(creative_uow_factory),
        media=media,
        route=runtime.vision_route,
        client=ImagegenClient(endpoint_file),
        system_prompt=pinned_caption_system_prompt(hub_dir),
        preview=ffmpeg_preview(runtime.ffmpeg_path),
        register_version=staged_artifact_registrar(manager, workspace_id, runtime.staging_root),
        open_assets=media_assets_opener(manager),
        staging_root=runtime.staging_root,
        grants=grants,
        clock=clock,
        request_timeout=float(profile.ai.request_timeout_seconds),
    )
    return {ACTIVITY_NAME: service_handler(service, clock)}


__all__ = [
    'ACTIVITY_NAME', 'AI_ROLE', 'ILLUSTRATION_GENERATION_FAILED', 'ILLUSTRATION_QUEUED', 'ILLUSTRATION_SERVICE_UNAVAILABLE',
    'ILLUSTRATION_WAIT_SECONDS', 'MAX_AI_IMAGES_PER_VIDEO', 'MAX_JOB_AGE_SECONDS', 'PUP_SYSTEM_PROMPTS_SHA256', 'REF_AI_ILLUSTRATION',
    'SKIPPED_WARNING_PREFIX', 'TARGET_DISTINCT_IMAGES', 'CreativeIllustrationInputs', 'IllustrationContext', 'IllustrationInputError',
    'IllustrationService', 'ai_locator', 'derive_seed', 'ffmpeg_preview', 'illustration_activity_handlers', 'illustration_count',
    'illustration_job_id', 'pinned_caption_system_prompt', 'plan_message', 'png_size',
]

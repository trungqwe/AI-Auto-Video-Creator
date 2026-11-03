"""HOOK-HARVEST: one-off harvest of real hooks and background music from the free stock libraries (D1 Pixabay video, D2 Freesound SFX and music, 02/11/2026; FR-HOOK-004, FR-HOOK-005, FR-AUD-007).

harvest_hooks turns Pixabay clips and Freesound sounds into hook revisions of the hook library of C: each item is downloaded from the CDN of its library
(download_stock_file of HOOK-STOCK), cut to a 4 s H.264 clip without audio or normalized to a short 48 kHz WAV by the pinned ffmpeg, staged and imported
with tags, a description and technical_metadata that name source, license, author, attribution and page (never the recipe key of a hooks.json placeholder, so PW-D3-FIX4
treats them as real hooks). harvest_music merges Freesound music previews into the catalog <staging>/audio_library/catalog/music_sources.json that AudioBedSource of PW-E4-FIX2 reads;
the sha256 is measured when harvested. Every dependency is injected: search clients, transport, media processor, hook store, budget and sleep. Every request goes
through MeteredTransport, which caps the number of requests, downloads and downloaded bytes of one run and spaces requests; the API key stays inside the search
clients and the request URL, so no report line, exception or repr carries it. Running again imports nothing twice (hook id pxb-<id> or fs-<id>, catalog URL).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from controlplane.infrastructure.production_ports.stock_media import (
    ERR_HTTP_STATUS,
    ERR_KEY_MISSING,
    MEDIA_KIND_AUDIO,
    MEDIA_KIND_CLIP,
    PROVIDER_FREESOUND,
    PROVIDER_PIXABAY,
    StockItem,
    StockSearchError,
    download_allowed,
    download_stock_file,
    license_cleared,
)
from voice.adapters.audio_bed_source import CATALOG_RELATIVE_PATH, MAX_CATALOG_SOURCES, ROLE_CATALOG, MusicSource, load_music_catalog, save_music_catalog

HOOK_VISUAL_QUERIES = (
    'breaking news', 'police lights night', 'city traffic timelapse', 'crowd street', 'storm lightning', 'fire smoke', 'stock market screen',
    'hospital corridor', 'courtroom', 'airplane takeoff', 'newspaper printing', 'world map globe', 'government building', 'rain city night',
    'earthquake rubble', 'flood water', 'press conference microphones', 'data network technology', 'helicopter flying', 'ocean waves storm',
    'wildlife nature', 'rocket launch', 'satellite earth', 'factory industry',
)
HOOK_AUDIO_QUERIES = ('whoosh', 'impact hit', 'riser', 'heartbeat', 'news sting', 'camera shutter', 'typewriter', 'glitch', 'drum hit', 'notification')
MUSIC_MOOD_QUERIES = {
    'calm': ('calm ambient',), 'tense': ('tense suspense',), 'upbeat': ('upbeat corporate',), 'sad': ('sad piano',),
    'dramatic': ('dramatic cinematic',), 'inspiring': ('inspiring uplifting',),
}
KIND_VISUAL_HOOK = 'visual_hook'
KIND_AUDIO_HOOK = 'audio_hook'
MAX_REQUESTS_PER_RUN = 200
MAX_DOWNLOADS_PER_RUN = 120
MAX_BYTES_PER_RUN = 2 * 1024 * 1024 * 1024
MAX_CLIP_BYTES = 80 * 1024 * 1024
MAX_SFX_BYTES = 10 * 1024 * 1024
MAX_MUSIC_BYTES = 30 * 1024 * 1024
REQUEST_INTERVAL_SECONDS = 1.2
DEFAULT_PER_QUERY = 4
DEFAULT_PER_MOOD = 4
MAX_PER_QUERY = 20
SEARCH_FACTOR = 3
VISUAL_SOURCE_MIN_S = 5
VISUAL_SOURCE_MAX_S = 60
VISUAL_HOOK_START_MS = 500
VISUAL_HOOK_MS = 4000
VISUAL_HOOK_MIN_MS = 3500
VISUAL_HOOK_FPS = 30
MAX_VISUAL_SIDE = 1920
AUDIO_HOOK_MAX_S = 5.0
AUDIO_HOOK_MIN_MS = 300
AUDIO_HOOK_RATE_HZ = 48000
AUDIO_HOOK_CHANNELS = 2
AUDIO_HOOK_LOUDNORM = 'loudnorm=I=-16:TP=-1.5:LRA=11'
MUSIC_MIN_S = 60.0
MUSIC_MAX_S = 600.0
MAX_TAGS = 20
MAX_DESCRIPTION_CHARS = 500
FFMPEG_TIMEOUT_SECONDS = 180.0
STAGED_MEDIA_DIR = 'media'
STAGED_OWNER_REF = 'hook-harvest'
STAGED_RETENTION_REF = 'durable'
ERR_BUDGET = 'harvest_budget_exhausted'
ERR_MEDIA = 'harvest_media_failed'


class HarvestBudgetExhausted(Exception):
    """The request, download or byte cap of this run is reached; detail names which one."""

    def __init__(self, detail: str) -> None:
        super().__init__(f'{ERR_BUDGET}: {detail}')
        self.code = ERR_BUDGET
        self.detail = detail


class MediaProcessingError(Exception):
    """ffmpeg or ffprobe could not turn the download into a hook; the message holds a fixed code, never a path or URL."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class HarvestBudget:
    max_requests: int = MAX_REQUESTS_PER_RUN
    max_downloads: int = MAX_DOWNLOADS_PER_RUN
    max_bytes: int = MAX_BYTES_PER_RUN
    requests: int = 0
    downloads: int = 0
    bytes: int = 0
    exhausted: str | None = None

    def _exhaust(self, detail: str) -> None:
        self.exhausted = self.exhausted or detail
        raise HarvestBudgetExhausted(detail)

    def take_request(self, max_bytes: int) -> None:
        """Raised inside the search clients the cap is wrapped as a fetch error; exhausted keeps it so the harvest loops stop (raise_if_exhausted)."""
        if self.requests >= self.max_requests:
            self._exhaust('requests')
        if max_bytes > self.max_bytes - self.bytes:
            self._exhaust('bytes')
        self.requests += 1

    def take_download(self) -> None:
        if self.downloads >= self.max_downloads:
            self._exhaust('downloads')
        self.downloads += 1

    def raise_if_exhausted(self) -> None:
        if self.exhausted is not None:
            raise HarvestBudgetExhausted(self.exhausted)


class MeteredTransport:
    """Every request of a run: counted against the budget (a request whose byte limit no longer fits is refused before it is sent) and spaced by interval_seconds."""

    def __init__(self, inner: Any, budget: HarvestBudget, *, sleep: Callable[[float], None] = time.sleep, interval_seconds: float = REQUEST_INTERVAL_SECONDS) -> None:
        self._inner = inner
        self._budget = budget
        self._sleep = sleep
        self._interval = interval_seconds
        self._sent = 0

    def __repr__(self) -> str:
        return f'MeteredTransport(requests={self._budget.requests})'

    @property
    def budget(self) -> HarvestBudget:
        return self._budget

    def fetch(self, url: str, *, max_bytes: int, timeout_seconds: float) -> Any:
        self._budget.take_request(max_bytes)
        if self._sent:
            self._sleep(self._interval)
        self._sent += 1
        response = self._inner.fetch(url, max_bytes=max_bytes, timeout_seconds=timeout_seconds)
        body = getattr(response, 'body', None)
        if isinstance(body, bytes):
            self._budget.bytes += len(body)
        return response


@dataclass(frozen=True)
class ProcessedMedia:
    data: bytes = field(repr=False)
    extension: str
    technical: Mapping[str, str]


@dataclass(frozen=True)
class HarvestedHook:
    hook_id: str
    kind: str
    data: bytes = field(repr=False)
    extension: str
    sha256: str
    tags: tuple[str, ...]
    description: str
    technical_metadata: tuple[tuple[str, str], ...]
    source_locator: str


class MediaProcessor(Protocol):
    def cut_visual(self, data: bytes) -> ProcessedMedia:
        ...

    def normalize_audio(self, data: bytes) -> ProcessedMedia:
        ...


class HookStore(Protocol):
    def has_hook(self, hook_id: str) -> bool:
        ...

    def add_hook(self, hook: HarvestedHook) -> str:
        ...


@dataclass
class HarvestReport:
    kind: str
    imported: int = 0
    existing: int = 0
    planned: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    stopped: list[str] = field(default_factory=list)

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    def lines(self, budget: HarvestBudget) -> list[str]:
        out = [f'{self.kind}: đã nhập {self.imported}, đã có {self.existing}, dự kiến (chạy thử) {self.planned}']
        if self.skipped:
            out.append(f'{self.kind}: bỏ qua ' + ', '.join(f'{reason}={count}' for reason, count in sorted(self.skipped.items())))
        if self.stopped:
            out.append(f'{self.kind}: dừng sớm ' + ', '.join(self.stopped))
        out.append(f'{self.kind}: {budget.requests} request, {budget.downloads} lượt tải, {budget.bytes} byte')
        return out


STOP_HTTP_STATUSES = frozenset({'401', '403', '429'})


class _ProviderStopped(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _stops_provider(exc: StockSearchError) -> bool:
    """Missing or refused key and rate limit stop every further request to that library in this run."""
    return exc.code == ERR_KEY_MISSING or (exc.code == ERR_HTTP_STATUS and exc.detail in STOP_HTTP_STATUSES)


def _budget_of(transport: Any, budget: HarvestBudget | None) -> HarvestBudget:
    """The budget of the run: the one given, else the one of the MeteredTransport (requests and downloads then share one cap), else a fresh one."""
    if budget is not None:
        return budget
    return transport.budget if isinstance(transport, MeteredTransport) else HarvestBudget()


def _stop_detail(provider: str, exc: StockSearchError) -> str:
    return f'{provider}:{exc.code}' + (f':{exc.detail}' if exc.code == ERR_HTTP_STATUS else '')


def _words(text: str) -> list[str]:
    return [word for word in re.findall('[a-z]+', text.lower()) if len(word) > 2]


def _tags(item: StockItem, query: str) -> tuple[str, ...]:
    tags = list(item.tags)
    for word in _words(query):
        if word not in tags:
            tags.append(word)
    return tuple(tags[:MAX_TAGS])


def _refusal(item: StockItem, kind: str) -> str | None:
    want = (PROVIDER_PIXABAY, MEDIA_KIND_CLIP) if kind == KIND_VISUAL_HOOK else (PROVIDER_FREESOUND, MEDIA_KIND_AUDIO)
    if not isinstance(item, StockItem) or (item.provider, item.media_kind) != want:
        return 'kind_mismatch'
    if not license_cleared(item.license, item.author, item.attribution):
        return 'license_not_cleared'
    if not download_allowed(item.provider, item.download_url):
        return 'download_not_allowed'
    return None


def _checked(processed: object, kind: str) -> ProcessedMedia:
    extension = 'mp4' if kind == KIND_VISUAL_HOOK else 'wav'
    keys = ('width', 'height', 'fps', 'duration_ms') if kind == KIND_VISUAL_HOOK else ('sample_rate_hz', 'channels', 'duration_ms')
    if not isinstance(processed, ProcessedMedia) or not isinstance(processed.data, bytes) or not processed.data or processed.extension != extension:
        raise MediaProcessingError(ERR_MEDIA)
    if not all(str(processed.technical.get(key, '')).isdigit() for key in keys):
        raise MediaProcessingError(ERR_MEDIA)
    return processed


def build_hook(item: StockItem, kind: str, query: str, source_sha256: str, processed: ProcessedMedia) -> HarvestedHook:
    """Hook revision content of one harvested item: technical values measured on the processed bytes, then source, license and attribution."""
    processed = _checked(processed, kind)
    digest = hashlib.sha256(processed.data).hexdigest()
    keys = ('width', 'height', 'fps', 'duration_ms') if kind == KIND_VISUAL_HOOK else ('sample_rate_hz', 'channels', 'duration_ms')
    technical = tuple((key, str(processed.technical[key])) for key in keys)
    provenance = (
        ('media_sha256', digest), ('hook_source', item.provider), ('hook_license', item.license), ('hook_author', item.author),
        ('hook_attribution', item.attribution), ('hook_page_url', item.page_url), ('hook_provider_id', item.provider_id),
        ('hook_source_sha256', source_sha256), ('hook_query', query))
    description = (query + ': ' + (item.description or ', '.join(item.tags)))[:MAX_DESCRIPTION_CHARS]
    return HarvestedHook(
        hook_id=item.hook_id, kind=kind, data=processed.data, extension=processed.extension, sha256=digest, tags=_tags(item, query),
        description=description, technical_metadata=technical + tuple((key, value) for key, value in provenance if value), source_locator=item.page_url)


def harvest_hooks(
    *, pixabay: Any, freesound: Any, transport: Any, media: MediaProcessor, store: HookStore, per_query: int = DEFAULT_PER_QUERY, dry_run: bool = False,
    visual_queries: Sequence[str] = HOOK_VISUAL_QUERIES, audio_queries: Sequence[str] = HOOK_AUDIO_QUERIES, budget: HarvestBudget | None = None,
) -> HarvestReport:
    """Import up to per_query new hooks per query (visual from Pixabay, audio from Freesound); a hook already in the store counts and is not fetched again."""
    per_query = max(1, min(int(per_query), MAX_PER_QUERY))
    budget = _budget_of(transport, budget)
    report = HarvestReport('hooks')
    plans = (
        (KIND_VISUAL_HOOK, PROVIDER_PIXABAY, visual_queries, lambda q: pixabay.search(q, min_duration_s=VISUAL_SOURCE_MIN_S, max_duration_s=VISUAL_SOURCE_MAX_S, per_page=per_query * SEARCH_FACTOR)),
        (KIND_AUDIO_HOOK, PROVIDER_FREESOUND, audio_queries, lambda q: freesound.search_sfx(q, max_duration_s=AUDIO_HOOK_MAX_S, page_size=per_query * SEARCH_FACTOR)),
    )
    seen: set[str] = set()
    try:
        for kind, provider, queries, search in plans:
            for query in queries:
                if not _harvest_query(kind, provider, query, search, transport, media, store, per_query, dry_run, budget, report, seen):
                    break
    except HarvestBudgetExhausted as exc:
        report.stopped.append(f'budget:{exc.detail}')
    return report


def _harvest_query(kind, provider, query, search, transport, media, store, per_query, dry_run, budget, report, seen) -> bool:
    """One query; False when the provider answered 429 (the rest of its queries is skipped)."""
    try:
        items = search(query)
    except StockSearchError as exc:
        budget.raise_if_exhausted()
        if _stops_provider(exc):
            report.stopped.append(_stop_detail(provider, exc))
            return False
        report.skip(f'search_{exc.code}')
        return True
    taken = 0
    for item in items:
        if taken >= per_query:
            break
        if getattr(item, 'hook_id', None) in seen:
            continue
        seen.add(getattr(item, 'hook_id', None))
        reason = _refusal(item, kind)
        if reason is not None:
            report.skip(reason)
            continue
        if store.has_hook(item.hook_id):
            report.existing += 1
            taken += 1
            continue
        if dry_run:
            report.planned += 1
            taken += 1
            continue
        try:
            budget.take_download()
            data, source_sha = download_stock_file(transport, item, max_bytes=MAX_CLIP_BYTES if kind == KIND_VISUAL_HOOK else MAX_SFX_BYTES)
            processed = media.cut_visual(data) if kind == KIND_VISUAL_HOOK else media.normalize_audio(data)
            hook = build_hook(item, kind, query, source_sha, processed)
        except StockSearchError as exc:
            budget.raise_if_exhausted()
            if _stops_provider(exc):
                report.stopped.append(_stop_detail(provider, exc))
                return False
            report.skip(f'download_{exc.code}')
            continue
        except MediaProcessingError as exc:
            report.skip(exc.code)
            continue
        store.add_hook(hook)
        report.imported += 1
        taken += 1
    return True


def music_moods(mood: str, query: str) -> tuple[str, ...]:
    moods = [mood.casefold()]
    for word in _words(query):
        if word not in moods:
            moods.append(word)
    return tuple(moods)


def harvest_music(
    *, freesound: Any, transport: Any, catalog_path: Path | str, per_mood: int = DEFAULT_PER_MOOD, dry_run: bool = False,
    moods: Mapping[str, Sequence[str]] = MUSIC_MOOD_QUERIES, budget: HarvestBudget | None = None,
) -> HarvestReport:
    """Add up to per_mood new Freesound tracks per mood to the music catalog (sha256 measured now, role catalog); entries already in the catalog stay and count."""
    per_mood = max(1, min(int(per_mood), MAX_PER_QUERY))
    budget = _budget_of(transport, budget)
    report = HarvestReport('music')
    existing = list(load_music_catalog(catalog_path))
    urls = {source.url for source in existing}
    fresh: list[MusicSource] = []
    try:
        for mood, queries in moods.items():
            taken = 0
            for query in queries:
                if taken >= per_mood:
                    break
                try:
                    items = freesound.search_music(query, min_duration_s=MUSIC_MIN_S, max_duration_s=MUSIC_MAX_S, page_size=per_mood * SEARCH_FACTOR)
                except StockSearchError as exc:
                    budget.raise_if_exhausted()
                    if _stops_provider(exc):
                        raise _ProviderStopped(_stop_detail(PROVIDER_FREESOUND, exc)) from None
                    report.skip(f'search_{exc.code}')
                    continue
                for item in items:
                    if taken >= per_mood:
                        break
                    if getattr(item, 'download_url', None) in urls:
                        report.existing += 1
                        taken += 1
                        continue
                    reason = _refusal(item, KIND_AUDIO_HOOK) or (None if item.author.strip() else 'author_missing')
                    if reason is not None:
                        report.skip(reason)
                        continue
                    if dry_run:
                        report.planned += 1
                        taken += 1
                        continue
                    if len(existing) + len(fresh) >= MAX_CATALOG_SOURCES:
                        report.skip('catalog_full')
                        continue
                    try:
                        budget.take_download()
                        _, digest = download_stock_file(transport, item, max_bytes=MAX_MUSIC_BYTES)
                    except StockSearchError as exc:
                        budget.raise_if_exhausted()
                        if _stops_provider(exc):
                            raise _ProviderStopped(_stop_detail(PROVIDER_FREESOUND, exc)) from None
                        report.skip(f'download_{exc.code}')
                        continue
                    fresh.append(MusicSource(
                        source_id='fs-' + item.provider_id, role=ROLE_CATALOG, url=item.download_url, license=item.license, attribution=item.attribution,
                        author=item.author, sha256=digest, moods=music_moods(mood, query)))
                    urls.add(item.download_url)
                    report.imported += 1
                    taken += 1
    except _ProviderStopped as exc:
        report.stopped.append(exc.detail)
    except HarvestBudgetExhausted as exc:
        report.stopped.append(f'budget:{exc.detail}')
    if fresh and not dry_run:
        save_music_catalog(catalog_path, existing + fresh)
    return report


def probe_providers(*, pixabay: Any, freesound: Any) -> list[str]:
    """One minimal search per library (per_page 3, nothing downloaded): confirms key and endpoint."""
    lines = []
    for provider, call in ((PROVIDER_PIXABAY, lambda: pixabay.search('news', per_page=3)), (PROVIDER_FREESOUND, lambda: freesound.search_sfx('whoosh', page_size=3))):
        try:
            found = call()
        except StockSearchError as exc:
            lines.append(f'{provider}: lỗi {exc.code}' + (f' ({exc.detail})' if exc.detail else ''))
        except HarvestBudgetExhausted as exc:
            lines.append(f'{provider}: lỗi {exc.code} ({exc.detail})')
        else:
            lines.append(f'{provider}: {len(found)} kết quả dùng được')
    return lines


def catalog_path_for(staging_root: Path | str) -> Path:
    return Path(staging_root) / 'audio_library' / CATALOG_RELATIVE_PATH


class FfmpegHookMedia:
    """MediaProcessor over the pinned ffmpeg and ffprobe: a 4 s H.264 yuv420p 30 fps clip without audio from 0.5 s, or a WAV 48 kHz stereo of at most 5 s with loudnorm."""

    def __init__(self, ffmpeg: Path | str, ffprobe: Path | str, *, timeout_seconds: float = FFMPEG_TIMEOUT_SECONDS, run: Callable[..., Any] = subprocess.run) -> None:
        self._ffmpeg = str(ffmpeg)
        self._ffprobe = str(ffprobe)
        self._timeout = timeout_seconds
        self._run = run

    def __repr__(self) -> str:
        return 'FfmpegHookMedia()'

    def _call(self, args: list[str]) -> bytes:
        try:
            done = self._run(args, capture_output=True, timeout=self._timeout, check=False)
        except (OSError, subprocess.SubprocessError):
            raise MediaProcessingError(ERR_MEDIA) from None
        if done.returncode != 0:
            raise MediaProcessingError(ERR_MEDIA)
        return done.stdout or b''

    def _probe(self, path: Path) -> dict:
        raw = self._call([self._ffprobe, '-v', 'error', '-show_entries', 'stream=codec_type,width,height,avg_frame_rate,sample_rate,channels:format=duration', '-of', 'json', str(path)])
        try:
            data = json.loads(raw.decode('utf-8'))
            streams = data.get('streams') or []
            duration_ms = int(round(float(data['format']['duration']) * 1000))
        except (ValueError, KeyError, TypeError, AttributeError):
            raise MediaProcessingError(ERR_MEDIA) from None
        return {'streams': [s for s in streams if isinstance(s, dict)], 'duration_ms': duration_ms}

    @staticmethod
    def _stream(info: dict, codec: str) -> dict:
        stream = next((s for s in info['streams'] if s.get('codec_type') == codec), None)
        if stream is None:
            raise MediaProcessingError(ERR_MEDIA)
        return stream

    @staticmethod
    def _even(value: float) -> int:
        return max(2, int(value) // 2 * 2)

    def cut_visual(self, data: bytes) -> ProcessedMedia:
        with tempfile.TemporaryDirectory(prefix='aiavc-harvest-') as work:
            source, out = Path(work) / 'source.bin', Path(work) / 'hook.mp4'
            source.write_bytes(data)
            video = self._stream(self._probe(source), 'video')
            try:
                width, height = int(video['width']), int(video['height'])
            except (KeyError, TypeError, ValueError):
                raise MediaProcessingError(ERR_MEDIA) from None
            scale = min(1.0, MAX_VISUAL_SIDE / max(width, height, 1))
            filters = f'scale={self._even(width * scale)}:{self._even(height * scale)},fps={VISUAL_HOOK_FPS},format=yuv420p'
            self._call([
                self._ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-ss', f'{VISUAL_HOOK_START_MS / 1000:g}', '-i', str(source),
                '-t', f'{VISUAL_HOOK_MS / 1000:g}', '-an', '-vf', filters, '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-movflags', '+faststart', '-y', str(out)])
            info = self._probe(out)
            stream = self._stream(info, 'video')
            if info['duration_ms'] < VISUAL_HOOK_MIN_MS:
                raise MediaProcessingError('harvest_clip_too_short')
            technical = {'width': str(stream.get('width', '')), 'height': str(stream.get('height', '')), 'fps': str(VISUAL_HOOK_FPS), 'duration_ms': str(info['duration_ms'])}
            return ProcessedMedia(out.read_bytes(), 'mp4', technical)

    def normalize_audio(self, data: bytes) -> ProcessedMedia:
        with tempfile.TemporaryDirectory(prefix='aiavc-harvest-') as work:
            source, out = Path(work) / 'source.bin', Path(work) / 'hook.wav'
            source.write_bytes(data)
            self._call([
                self._ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(source), '-t', f'{AUDIO_HOOK_MAX_S:g}', '-vn', '-af', AUDIO_HOOK_LOUDNORM,
                '-ar', str(AUDIO_HOOK_RATE_HZ), '-ac', str(AUDIO_HOOK_CHANNELS), '-c:a', 'pcm_s16le', '-y', str(out)])
            info = self._probe(out)
            stream = self._stream(info, 'audio')
            if info['duration_ms'] < AUDIO_HOOK_MIN_MS:
                raise MediaProcessingError('harvest_sound_too_short')
            technical = {'sample_rate_hz': str(stream.get('sample_rate', '')), 'channels': str(stream.get('channels', '')), 'duration_ms': str(info['duration_ms'])}
            return ProcessedMedia(out.read_bytes(), 'wav', technical)


def _utc_stamp(moment: datetime.datetime) -> str:
    return moment.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def stage_hook_file(staging_root: Path | str, hook: HarvestedHook) -> str:
    """Write the processed bytes to <staging>/media/<sha256>.<ext> (atomic, kept when already intact); returns the relative ref."""
    media_dir = Path(staging_root) / STAGED_MEDIA_DIR
    media_dir.mkdir(parents=True, exist_ok=True)
    target = media_dir / f'{hook.sha256}.{hook.extension}'
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == hook.sha256:
        return f'{STAGED_MEDIA_DIR}/{target.name}'
    part = media_dir / f'{target.name}.harvest.part'
    try:
        part.write_bytes(hook.data)
        os.replace(part, target)
    finally:
        part.unlink(missing_ok=True)
    return f'{STAGED_MEDIA_DIR}/{target.name}'


class PostgresHookLibrary:
    """HookStore over the hook and asset tables of C (same services as the seed import): stage and register the bytes, then register_discovery and import_hook in one transaction."""

    def __init__(self, manager: Any, *, workspace_id: str, staging_root: Path | str, clock: Callable[[], datetime.datetime] | None = None) -> None:
        if not Path(staging_root).is_absolute():
            raise ValueError('staging_root must be absolute')
        self._manager = manager
        self._workspace_id = workspace_id
        self._staging_root = Path(staging_root)
        self._clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))

    def has_hook(self, hook_id: str) -> bool:
        from catalog.persistence.hooks import PostgresHookHistory
        with self._manager.borrow_connection() as connection:
            try:
                PostgresHookHistory(connection, self._workspace_id).latest(hook_id)
            except KeyError:
                return False
        return True

    def add_hook(self, hook: HarvestedHook) -> str:
        from catalog.application.discovery import DiscoveryObservation, register_discovery
        from catalog.application.hooks import import_hook
        from catalog.domain.hooks import HookKind
        from catalog.domain.identity import CanonicalFingerprint, MediaKind, ProvenanceEntry, ProvenanceRelation
        from catalog.persistence.assets import PostgresMediaAssetRepository
        from catalog.persistence.hooks import PostgresHookHistory
        from controlplane.application.storage_meta.handlers import register_staged_artifact
        relative_ref = stage_hook_file(self._staging_root, hook)
        register_staged_artifact(
            self._manager, workspace_id=self._workspace_id, staging_root=self._staging_root, owner_ref=STAGED_OWNER_REF,
            relative_ref=relative_ref, retention_ref=STAGED_RETENTION_REF)
        media_kind = MediaKind.CLIP if hook.kind == KIND_VISUAL_HOOK else MediaKind.AUDIO
        with self._manager.borrow_connection() as connection:
            provenance = ProvenanceEntry(None, None, None, hook.source_locator, _utc_stamp(self._clock()), ProvenanceRelation.USER_IMPORTED)
            observation = DiscoveryObservation('hook-harvest:' + hook.hook_id, media_kind, provenance, CanonicalFingerprint(hook.sha256), True)
            result = register_discovery(PostgresMediaAssetRepository(connection, self._workspace_id), observation, 'harvest-' + hook.hook_id)
            import_hook(
                PostgresHookHistory(connection, self._workspace_id), hook_id=hook.hook_id, kind=HookKind(hook.kind),
                artifact_version_ref=f'stock:{hook.hook_id}:sha256:{hook.sha256}', tags=hook.tags, description=hook.description, note='', enabled=True,
                technical_metadata=hook.technical_metadata + (('media_asset_id', str(result.media_asset_id)),))
            connection.commit()
        return str(result.media_asset_id)

    def count_by_source(self) -> dict[str, int]:
        from catalog.persistence.hooks import PostgresHookHistory
        from creative.adapters.hook_candidates import is_placeholder
        with self._manager.borrow_connection() as connection:
            heads = PostgresHookHistory(connection, self._workspace_id).list_heads()
        counts: dict[str, int] = {}
        for head in heads:
            metadata = dict(head.revision.technical_metadata)
            source = metadata.get('hook_source') or ('placeholder' if is_placeholder(head.revision) else 'other')
            key = f'{head.revision.kind.value}:{source}'
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))


__all__ = [
    'DEFAULT_PER_MOOD', 'DEFAULT_PER_QUERY', 'FfmpegHookMedia', 'HOOK_AUDIO_QUERIES', 'HOOK_VISUAL_QUERIES', 'HarvestBudget', 'HarvestBudgetExhausted',
    'HarvestReport', 'HarvestedHook', 'MAX_BYTES_PER_RUN', 'MAX_DOWNLOADS_PER_RUN', 'MAX_REQUESTS_PER_RUN', 'MUSIC_MOOD_QUERIES', 'MediaProcessingError',
    'MeteredTransport', 'PostgresHookLibrary', 'ProcessedMedia', 'build_hook', 'catalog_path_for', 'harvest_hooks', 'harvest_music', 'music_moods',
    'probe_providers', 'stage_hook_file',
]

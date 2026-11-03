"""Production AudioBedPort (PW-E4; FR-AUD-007, FR-AUD-004): finds music by mood and duration in the collected library, collects new music over HTTPS from the pinned sources of music_sources.json under an exact-URL SSRF policy, pins sha256 and records provenance. Never AI-composed. No suitable music or a failing source gives a bed of kind none with warning AUDIO_MIX_QUALITY. The HTTPS transport is injected (no network import here).

PW-E4-FIX2 (R11, FR-AUD-007, FR-AUD-004): besides the two pinned sources, the library reads the harvested catalog <library>/catalog/music_sources.json (same fields, role catalog, sha256 measured when harvested, any number of entries). While fewer than MUSIC_LIBRARY_TARGET tracks fit a cue, one catalog source not yet collected is collected for it (at most MAX_COLLECT_ATTEMPTS tries), so the library grows past one track. Among the fitting tracks the cue takes one by a stable rotation keyed on the voice artifact and the cue index (same video, same track; different videos spread over the library), instead of always the shortest. A cue without mood prefers tracks whose moods appear as words of its cue text."""
from __future__ import annotations

import datetime
import hashlib
import ipaddress
import json
import logging
import re
import uuid
import wave
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from voice.application.media_pipeline import AudioBedOutcome
from voice.domain.audio_bed import INPUT_NOT_READY, AudioBedRejected, AudioBedRequest, LoudnessReport, PreparedRendition, validate_loudness_report
from voice.domain.processing import Disposition

LOGGER = logging.getLogger(__name__)
WARNING_AUDIO_MIX_QUALITY = 'AUDIO_MIX_QUALITY'
BED_KIND_MUSIC = 'external_music'
BED_KIND_NONE = 'none'
ROLE_PRIMARY = 'primary'
ROLE_FALLBACK = 'fallback'
ROLE_CATALOG = 'catalog'
CATALOG_RELATIVE_PATH = Path('catalog') / 'music_sources.json'
MAX_CATALOG_SOURCES = 500
MUSIC_LIBRARY_TARGET = 6
MAX_COLLECT_ATTEMPTS = 2
ERR_SOURCES_INVALID = 'music_sources_invalid'
ERR_URL_NOT_ALLOWED = 'music_url_not_allowed'
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 30.0
_SHA256_RE = re.compile(r'[0-9a-f]{64}')
_TEXT_FIELDS = ('source_id', 'role', 'url', 'license', 'attribution', 'author', 'sha256')


class MusicSourceError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f'{code}: {detail}')
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class MusicSource:
    source_id: str
    role: str
    url: str
    license: str
    attribution: str
    author: str
    sha256: str
    moods: tuple[str, ...]


def _invalid(detail: str) -> MusicSourceError:
    return MusicSourceError(ERR_SOURCES_INVALID, detail)


def _source_from(item: object, index: int) -> MusicSource:
    if not isinstance(item, Mapping):
        raise _invalid(f'sources[{index}] not an object')
    for name in _TEXT_FIELDS:
        if not isinstance(item.get(name), str) or not item[name].strip():
            raise _invalid(f'sources[{index}].{name}')
    if not re.fullmatch('https://[^ ]+', item['url']):
        raise _invalid(f'sources[{index}].url')
    lowered = item['license'].lower()
    if 'nc' in lowered.replace('-', ' ').split() or 'noncommercial' in lowered.replace('-', '').replace(' ', ''):
        raise _invalid(f'sources[{index}].license')
    if not _SHA256_RE.fullmatch(item['sha256']):
        raise _invalid(f'sources[{index}].sha256')
    moods = item.get('moods')
    if not isinstance(moods, list) or not moods or not all(isinstance(m, str) and m.strip() for m in moods):
        raise _invalid(f'sources[{index}].moods')
    return MusicSource(item['source_id'], item['role'], item['url'], item['license'], item['attribution'], item['author'], item['sha256'], tuple(m.casefold() for m in moods))


def load_music_sources(path: Path | str) -> tuple[MusicSource, ...]:
    try:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))['sources']
    except (OSError, ValueError, KeyError, TypeError):
        raise _invalid('unreadable') from None
    if not isinstance(raw, list) or len(raw) != 2:
        raise _invalid('need exactly two sources')
    sources = tuple(_source_from(item, index) for index, item in enumerate(raw))
    if sorted(item.role for item in sources) != [ROLE_FALLBACK, ROLE_PRIMARY]:
        raise _invalid('need one primary and one fallback')
    if len({item.source_id for item in sources}) != 2:
        raise _invalid('duplicate source_id')
    return tuple(sorted(sources, key=lambda item: item.role != ROLE_PRIMARY))


def load_music_catalog(path: Path | str) -> tuple[MusicSource, ...]:
    """Harvested music sources (role catalog): a missing file is an empty catalog; an unreadable file or a bad entry is skipped with a warning, never fatal. Duplicate URLs keep the first entry; at most MAX_CATALOG_SOURCES entries."""
    target = Path(path)
    if not target.is_file():
        return ()
    try:
        raw = json.loads(target.read_text(encoding='utf-8'))['sources']
    except (OSError, ValueError, KeyError, TypeError):
        LOGGER.warning('music_catalog_unreadable')
        return ()
    if not isinstance(raw, list):
        LOGGER.warning('music_catalog_unreadable')
        return ()
    sources: list[MusicSource] = []
    seen: set[str] = set()
    for index, item in enumerate(raw[:MAX_CATALOG_SOURCES]):
        try:
            source = _source_from(item, index)
        except MusicSourceError:
            LOGGER.warning('music_catalog_entry_invalid index=%s', index)
            continue
        if source.role != ROLE_CATALOG or source.url in seen:
            continue
        seen.add(source.url)
        sources.append(source)
    return tuple(sources)


def save_music_catalog(path: Path | str, sources: Sequence[MusicSource]) -> None:
    """Write the catalog atomically (role catalog for every entry); the harvest command is the only writer."""
    entries = [
        {'source_id': s.source_id, 'role': ROLE_CATALOG, 'url': s.url, 'license': s.license, 'attribution': s.attribution, 'author': s.author, 'sha256': s.sha256, 'moods': list(s.moods)}
        for s in sources]
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target, json.dumps({'sources': entries}, ensure_ascii=False, indent=1).encode('utf-8'))


def _words(text: object) -> frozenset[str]:
    return frozenset(re.findall('[a-z]+', text.casefold())) if isinstance(text, str) else frozenset()


def _rotation_pick(tracks: Sequence['CollectedTrack'], seed: str) -> 'CollectedTrack':
    ordered = sorted(tracks, key=lambda track: track.rendition_sha256)
    return ordered[int(hashlib.sha256(seed.encode('utf-8')).hexdigest(), 16) % len(ordered)]


def check_music_url(url: object, sources: Sequence[MusicSource]) -> MusicSource:
    """SSRF policy: https only, no credentials, port 443, host not an IP literal, and the whole URL equals the pinned URL of a configured source."""
    try:
        parts = urlsplit(url)
        host, port = parts.hostname, parts.port
    except (ValueError, AttributeError, TypeError):
        raise MusicSourceError(ERR_URL_NOT_ALLOWED, 'unparsable') from None
    if parts.scheme != 'https' or not host or parts.username or parts.password or port not in (None, 443):
        raise MusicSourceError(ERR_URL_NOT_ALLOWED, 'policy')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise MusicSourceError(ERR_URL_NOT_ALLOWED, 'ip_literal')
    for source in sources:
        if url == source.url:
            return source
    raise MusicSourceError(ERR_URL_NOT_ALLOWED, 'not_in_allowlist')


@dataclass(frozen=True)
class HttpsResponse:
    status: int
    body: bytes
    final_url: str


class HttpsTransport(Protocol):
    """Injected by wiring: one HTTPS GET without following redirects; the real transport resolves the host itself and refuses private, loopback and link-local addresses."""

    def fetch(self, url: str, *, max_bytes: int, timeout_seconds: float) -> HttpsResponse:
        ...


@dataclass(frozen=True)
class PreparedMusic:
    """Music after normalisation to the profile loudness: WAV bytes, duration read from the WAV header, loudness re-measured on those same bytes."""

    data: bytes
    duration_ms: int
    report: LoudnessReport


SILENCE_RATE_HZ = 8000


def silent_wav(duration_ms: int) -> bytes:
    """Pure silence of exactly duration_ms (8 kHz, mono, 16 bit): the bed of kind none carries no music."""
    buffer = BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SILENCE_RATE_HZ)
        wav.writeframes(bytes(2 * (duration_ms * SILENCE_RATE_HZ // 1000)))
    return buffer.getvalue()


def _iso(moment: datetime.datetime) -> str:
    if not isinstance(moment, datetime.datetime) or moment.tzinfo is None:
        raise ValueError('clock must return a timezone-aware datetime')
    return moment.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _same_bytes(path: Path, digest: str) -> bool:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() == digest
    except OSError:
        return False


def _atomic_write(path: Path, data: bytes) -> None:
    digest = hashlib.sha256(data).hexdigest()
    if _same_bytes(path, digest):
        return
    part = path.with_name(f'{path.name}.{uuid.uuid4().hex[:12]}.part')
    try:
        part.write_bytes(data)
        try:
            part.replace(path)
        except OSError:
            if not _same_bytes(path, digest):
                raise
    finally:
        part.unlink(missing_ok=True)


def _mood_matches(moods: Sequence[str], mood: str | None) -> bool:
    return mood is None or mood.casefold() in moods


@dataclass(frozen=True)
class CollectedTrack:
    source_id: str
    url: str
    license: str
    attribution: str
    author: str
    sha256: str
    rendition_sha256: str
    collected_at: str
    duration_ms: int
    moods: tuple[str, ...]
    integrated_lufs: float
    true_peak_dbtp: float

    @property
    def report(self) -> LoudnessReport:
        return LoudnessReport(integrated_lufs=self.integrated_lufs, true_peak_dbtp=self.true_peak_dbtp)

    def provenance(self, cue_index: int) -> dict:
        return {
            'cue_index': cue_index, 'source_id': self.source_id, 'url': self.url, 'license': self.license,
            'attribution': self.attribution, 'author': self.author, 'collected_at': self.collected_at,
            'sha256': self.sha256, 'rendition_sha256': self.rendition_sha256, 'duration_ms': self.duration_ms, 'moods': list(self.moods),
        }

    def to_sidecar(self) -> bytes:
        body = {**self.provenance(0), 'integrated_lufs': self.integrated_lufs, 'true_peak_dbtp': self.true_peak_dbtp}
        del body['cue_index']
        return json.dumps(body, sort_keys=True, ensure_ascii=False).encode('utf-8')


def track_from_sidecar(data: bytes) -> CollectedTrack | None:
    try:
        raw = json.loads(data.decode('utf-8'))
        track = CollectedTrack(
            source_id=raw['source_id'], url=raw['url'], license=raw['license'], attribution=raw['attribution'],
            author=raw['author'], sha256=raw['sha256'], rendition_sha256=raw['rendition_sha256'], collected_at=raw['collected_at'],
            duration_ms=int(raw['duration_ms']), moods=tuple(raw['moods']), integrated_lufs=float(raw['integrated_lufs']),
            true_peak_dbtp=float(raw['true_peak_dbtp']),
        )
        if not all(isinstance(value, str) and _SHA256_RE.fullmatch(value) for value in (track.sha256, track.rendition_sha256)):
            return None
        return track
    except (ValueError, KeyError, TypeError):
        return None


class AudioBedSource:
    """AudioBedPort: music cues look in the collected library (mood and duration), then in the pinned sources, primary before fallback; sfx cues get a silent bed of kind none for their span; a music cue without usable music turns the whole bed into kind none."""

    def __init__(
        self, *, sources: Sequence[MusicSource], library_dir: Path | str, transport: HttpsTransport,
        prepare_music: Callable[[bytes], PreparedMusic],
        clock: Callable[[], datetime.datetime], max_bytes: int = DEFAULT_MAX_BYTES, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._sources = tuple(sources)
        self._active = self._sources
        self._library = Path(library_dir)
        self._transport = transport
        self._prepare_music = prepare_music
        self._clock = clock
        self._max_bytes = max_bytes
        self._timeout = timeout_seconds

    def prepare(self, request: AudioBedRequest) -> AudioBedOutcome:
        limits = request.loudness_constraints
        if limits is None or limits.min_lufs is None or limits.max_lufs is None or limits.max_true_peak_dbtp is None:
            raise AudioBedRejected(INPUT_NOT_READY, 'missing_loudness_constraints')
        errors: list[str] = []
        tracks: dict[int, CollectedTrack] = {}
        pinned_urls = {source.url for source in self._sources}
        catalog = tuple(source for source in load_music_catalog(self._library / CATALOG_RELATIVE_PATH) if source.url not in pinned_urls)
        self._active = self._sources + catalog
        for index, cue in enumerate(request.cues):
            if cue.kind != 'music':
                continue
            track = self._track_for(cue, limits, errors, catalog, f'{request.voice_artifact_ref}#{index}')
            if track is None:
                return self._none_outcome(request, errors)
            tracks[index] = track
        if not tracks:
            return self._none_outcome(request, ['no_music_cue'])
        return self._music_outcome(request, tracks)

    def _track_for(self, cue, limits, errors: list[str], catalog: Sequence[MusicSource], seed: str) -> CollectedTrack | None:
        hints = frozenset()
        if cue.mood is None:
            hints = _words(cue.artifact_ref) & {mood for source in self._active for mood in source.moods}
        if hints:
            track = self._choose(cue, limits, errors, catalog, seed, hints)
            if track is not None:
                return track
        return self._choose(cue, limits, errors, catalog, seed, frozenset())

    def _choose(self, cue, limits, errors: list[str], catalog: Sequence[MusicSource], seed: str, hints: frozenset[str]) -> CollectedTrack | None:
        span = cue.end_ms - cue.start_ms
        library = [track for track in self._from_library(cue.mood, span, limits) if not hints or hints & set(track.moods)]
        if len(library) < MUSIC_LIBRARY_TARGET and catalog:
            collected = {track.url for track in self._from_library(None, 0, None)}
            fresh = [
                source for source in catalog
                if source.url not in collected and _mood_matches(source.moods, cue.mood) and (not hints or hints & set(source.moods))]
            for source in fresh[:MAX_COLLECT_ATTEMPTS]:
                track = self._collect(source, span, limits, errors)
                if track is not None:
                    return track
        if library:
            return _rotation_pick(library, seed)
        if hints:
            return None
        for source in self._sources:
            if _mood_matches(source.moods, cue.mood):
                track = self._collect(source, span, limits, errors)
                if track is not None:
                    return track
        return None

    def _from_library(self, mood: str | None, span: int, limits) -> list[CollectedTrack]:
        """Every intact library track of a current source that fits the mood, the span and (when limits is given) the loudness window."""
        pinned = {source.url: source.sha256 for source in self._active}
        found: list[CollectedTrack] = []
        for sidecar in sorted(self._library.glob('music-*.json')):
            try:
                track = track_from_sidecar(sidecar.read_bytes())
            except OSError:
                continue
            if track is None or sidecar.name != f'music-{track.rendition_sha256}.json' or pinned.get(track.url) != track.sha256:
                continue
            if not _mood_matches(track.moods, mood) or track.duration_ms < span or (limits is not None and validate_loudness_report(track.report, limits)):
                continue
            try:
                intact = hashlib.sha256((self._library / f'music-{track.rendition_sha256}.audio').read_bytes()).hexdigest() == track.rendition_sha256
            except OSError:
                continue
            if intact:
                found.append(track)
        return found

    def _collect(self, source: MusicSource, span: int, limits, errors: list[str]) -> CollectedTrack | None:
        try:
            check_music_url(source.url, self._active)
            response = self._transport.fetch(source.url, max_bytes=self._max_bytes, timeout_seconds=self._timeout)
        except MusicSourceError as exc:
            errors.append(exc.code)
            return None
        except Exception:
            errors.append('music_fetch_failed')
            return None
        if not isinstance(response, HttpsResponse) or response.status != 200 or response.final_url != source.url or not isinstance(response.body, bytes) or not response.body:
            errors.append('music_fetch_failed')
            return None
        body = response.body
        if len(body) > self._max_bytes:
            errors.append('music_too_large')
            return None
        digest = hashlib.sha256(body).hexdigest()
        if digest != source.sha256:
            LOGGER.warning('music_sha256_mismatch source_id=%s', source.source_id)
            errors.append('music_sha256_mismatch')
            return None
        try:
            prepared = self._prepare_music(body)
        except Exception:
            errors.append('music_unreadable')
            return None
        if (
            not isinstance(prepared, PreparedMusic) or not isinstance(prepared.data, bytes) or not prepared.data
            or type(prepared.duration_ms) is not int or prepared.duration_ms <= 0 or not isinstance(prepared.report, LoudnessReport)
        ):
            errors.append('music_unreadable')
            return None
        if prepared.duration_ms < span:
            errors.append('music_too_short')
            return None
        if validate_loudness_report(prepared.report, limits):
            errors.append('loudness_out_of_target')
            return None
        rendition = hashlib.sha256(prepared.data).hexdigest()
        track = CollectedTrack(
            source_id=source.source_id, url=source.url, license=source.license, attribution=source.attribution, author=source.author,
            sha256=digest, rendition_sha256=rendition, collected_at=_iso(self._clock()), duration_ms=prepared.duration_ms, moods=source.moods,
            integrated_lufs=float(prepared.report.integrated_lufs), true_peak_dbtp=float(prepared.report.true_peak_dbtp),
        )
        try:
            self._library.mkdir(parents=True, exist_ok=True)
            _atomic_write(self._library / f'music-{rendition}.audio', prepared.data)
            _atomic_write(self._library / f'music-{rendition}.json', track.to_sidecar())
        except OSError:
            errors.append('music_store_failed')
            return None
        return track

    def _store_silence(self, cue) -> str | None:
        audio = silent_wav(cue.end_ms - cue.start_ms)
        digest = hashlib.sha256(audio).hexdigest()
        try:
            self._library.mkdir(parents=True, exist_ok=True)
            _atomic_write(self._library / f'bed-none-{digest}.wav', audio)
        except OSError:
            return None
        return digest

    def _music_outcome(self, request: AudioBedRequest, tracks: dict[int, CollectedTrack]) -> AudioBedOutcome:
        renditions = []
        hashes = []
        sfx = []
        for index, cue in enumerate(request.cues):
            track = tracks.get(index)
            if track is not None:
                digest = track.rendition_sha256
                ref = f'music-{digest}'
            else:
                digest = self._store_silence(cue)
                if digest is None:
                    return AudioBedOutcome(status=Disposition.FAILED, error='bed_none_store_failed')
                ref = f'bed-none-{digest}'
                sfx.append({'cue_index': index, 'bed_kind': BED_KIND_NONE, 'reason': 'no_sfx_source'})
            renditions.append(PreparedRendition(cue_index=index, rendition_ref=ref, source_artifact_ref=cue.artifact_ref, mood=cue.mood))
            hashes.append(digest)
        reports = [tracks[index].report for index in sorted(tracks)]
        return AudioBedOutcome(
            status=Disposition.SUCCEEDED, renditions=tuple(renditions), output_hashes=tuple(hashes),
            loudness_report=LoudnessReport(integrated_lufs=min(r.integrated_lufs for r in reports), true_peak_dbtp=max(r.true_peak_dbtp for r in reports)),
            provenance={'bed_kind': BED_KIND_MUSIC, 'ai_generated': False, 'tracks': [tracks[index].provenance(index) for index in sorted(tracks)], 'sfx': sfx},
            risk_metadata={'bed_kind': BED_KIND_MUSIC, 'ai_generated': False, 'license_checked': True, 'pinned_sha256_verified': True},
        )

    def _none_outcome(self, request: AudioBedRequest, errors: list[str]) -> AudioBedOutcome:
        limits = request.loudness_constraints
        renditions = []
        hashes = []
        for index, cue in enumerate(request.cues):
            digest = self._store_silence(cue)
            if digest is None:
                return AudioBedOutcome(status=Disposition.FAILED, error='bed_none_store_failed')
            renditions.append(PreparedRendition(cue_index=index, rendition_ref=f'bed-none-{digest}', source_artifact_ref=cue.artifact_ref, mood=cue.mood))
            hashes.append(digest)
        return AudioBedOutcome(
            status=Disposition.SUCCEEDED, renditions=tuple(renditions), output_hashes=tuple(hashes),
            loudness_report=LoudnessReport(integrated_lufs=(limits.min_lufs + limits.max_lufs) / 2, true_peak_dbtp=limits.max_true_peak_dbtp),
            provenance={'bed_kind': BED_KIND_NONE, 'ai_generated': False, 'reason': 'no_matching_music', 'errors': sorted(set(errors))},
            risk_metadata={'bed_kind': BED_KIND_NONE, 'ai_generated': False, 'loudness_basis': 'constraint_midpoint_not_measured'},
            warnings=(WARNING_AUDIO_MIX_QUALITY,),
        )


__all__ = ('AudioBedSource', 'CollectedTrack', 'HttpsResponse', 'HttpsTransport', 'MusicSource', 'MusicSourceError', 'PreparedMusic', 'check_music_url', 'load_music_catalog', 'load_music_sources', 'save_music_catalog', 'silent_wav', 'track_from_sidecar')

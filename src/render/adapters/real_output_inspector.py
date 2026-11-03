"""PW-F1, PW-F2: OutputInspectorPort over the pinned ffmpeg.

PW-F1 measures VISUAL_HOOK, THUMBNAIL, SUBTITLE_BURNED_IN, KARAOKE_TIMING and INFERENCE_DISCLOSURE_PRESENT. SUBTITLE_BURNED_IN and INFERENCE_DISCLOSURE_PRESENT compare each sample frame with itself after the staged ASS is drawn again (FrameProbe.overlay_difference), never with a frame taken at another moment. PW-F2 adds the audio and language side:
AUDIO_HOOK (mean level inside hook_time_range, evidence audio_hook), ENGLISH_OUTPUT (evidence language from E and D plus the burned-in subtitle),
VOICE_AUDIBLE and OUTPUT_PROFILE (technical gates fed by RealFfprobeProbe, see GATE_SOURCES; speech_windows gives the probe the spoken ranges)
and audio_mix_result (loudness and true peak recorded as a warning, never a hard failure).
Every measurement threshold comes from InspectorSettings or the caller, no threshold constant in code;
missing inputs yield None in evidence fields.
QC-HOOK-FIX: ssim_between turns both frames into full-range gray before shrinking them, so the colour range of the output (full range
when the scenes are JPEG) no longer shifts dark frames apart.

coveredIds: PW-F1-01, PW-F2-01, CT-QC-001
"""
from __future__ import annotations

import math
import re
import subprocess
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from render.adapters.frame_probe import FrameProbe, OverlayDifference, seek_arg
from render.adapters.real_ffmpeg_renderer import DEFAULT_FFMPEG_PATH, DEFAULT_LOCK_PATH, verify_ffmpeg_pin
from render.adapters.real_ffprobe_probe import LoudnessStats, measure_audio
from render.domain.content_gates import INFERENCE_CLAIM_MODES
from render.domain.karaoke_plan import STYLE_NAME as KARAOKE_STYLE
from render.domain.package_contract import RenderPackageRecord
from render.domain.quality_report import GateName, GateResult, GateStatus
from render.domain.render_command import frame_placement
from render.ports.output_inspector import (
    AudioHookEvidence,
    DisclosureEvidence,
    DisclosureObservation,
    KaraokeEvidence,
    KaraokeWordObservation,
    LanguageEvidence,
    OutputEvidence,
    SubtitleEvidence,
    ThumbnailEvidence,
    VisualHookEvidence,
)

GATE_VISUAL_HOOK = 'VISUAL_HOOK'
GATE_THUMBNAIL = 'THUMBNAIL'
GATE_SUBTITLE = 'SUBTITLE_BURNED_IN'
GATE_KARAOKE = 'KARAOKE_TIMING'
GATE_DISCLOSURE = 'INFERENCE_DISCLOSURE_PRESENT'
DISCLOSURE_STYLE = 'Disclosure'
UNMATCHED_ASSET_PREFIX = 'unmatched:'
HOOK_CLIP_LAST_FRAME_GUARD_MS = 34  # one frame at the 30 fps output profile; keeps the seek inside the last frame of a hook clip
GATE_AUDIO_HOOK = 'AUDIO_HOOK'
GATE_VOICE_AUDIBLE = 'VOICE_AUDIBLE'
GATE_ENGLISH = 'ENGLISH_OUTPUT'
GATE_OUTPUT_PROFILE = 'OUTPUT_PROFILE'
UNDETERMINED_LOCALE = 'und'
ASS_TAG_RE = re.compile(r'\{[^}]*\}')
GATE_SOURCES = MappingProxyType({
    GATE_AUDIO_HOOK: 'RealOutputInspector.inspect: OutputEvidence.audio_hook over hook_time_range',
    GATE_VOICE_AUDIBLE: 'RealFfprobeProbe: audio_level over speech_windows and severe_audio_errors',
    GATE_ENGLISH: 'RealOutputInspector.inspect: OutputEvidence.language from E and D plus the burned-in subtitle',
    GATE_OUTPUT_PROFILE: 'RealFfprobeProbe: width, height, fps, codecs, container, duration_ms',
})


@dataclass(frozen=True, kw_only=True)
class Band:
    top: float
    bottom: float

    def __post_init__(self) -> None:
        if not (0 <= self.top < self.bottom <= 1):
            raise ValueError('band')


@dataclass(frozen=True, kw_only=True)
class InspectorSettings:
    compare_width: int
    compare_height: int
    thumbnail_min_ssim: float
    subtitle_band: Band
    disclosure_band: Band
    overlay_max_missing_share: float
    max_subtitle_samples: int
    timeout_seconds: float

    def __post_init__(self) -> None:
        for name in ('compare_width', 'compare_height', 'max_subtitle_samples'):
            val = getattr(self, name)
            if isinstance(val, bool) or not isinstance(val, int) or val <= 0:
                raise ValueError(name)
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or self.timeout_seconds <= 0:
            raise ValueError('timeout_seconds')
        if isinstance(self.thumbnail_min_ssim, bool) or not isinstance(self.thumbnail_min_ssim, (int, float)) or not (0 < self.thumbnail_min_ssim <= 1):
            raise ValueError('thumbnail_min_ssim')
        share = self.overlay_max_missing_share
        if isinstance(share, bool) or not isinstance(share, (int, float)) or not math.isfinite(share) or not (0 < share < 1):
            raise ValueError('overlay_max_missing_share')


@dataclass(frozen=True, kw_only=True)
class LanguageSource:
    """Language facts handed over by E (voice_hash, voice_locale, subtitle_text_hash, script_fingerprint) and D (script, title and hashtag locales); the inspector adds only what it observes in the output (the burned-in subtitle)."""

    evidence_ref: str
    script_fingerprint: str
    voice_hash: str
    subtitle_text_hash: str
    voice_locale: str
    subtitle_locale: str
    script_locale: str
    title_locale: str
    hashtag_locale: str
    declared_language: str | None = None


@dataclass(frozen=True, kw_only=True)
class InspectionInputs:
    staging_root: Path
    ass_ref: str
    segments: Sequence[Mapping]
    language: LanguageSource | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'staging_root', Path(self.staging_root))
        object.__setattr__(self, 'segments', tuple(self.segments))


@dataclass(frozen=True, kw_only=True)
class AssDialogue:
    style: str
    name: str
    start_ms: int
    end_ms: int
    text: str


_ASS_TIME_RE = re.compile(r'(\d+):(\d{2}):(\d{2})\.(\d{2})')


def _ass_ms(value: str) -> int | None:
    m = _ASS_TIME_RE.fullmatch(value.strip())
    if not m:
        return None
    h, m_, s, cs = (int(x) for x in m.groups())
    return ((h * 60 + m_) * 60 + s) * 1000 + cs * 10


def parse_ass_dialogues(text: str) -> tuple[AssDialogue, ...]:
    dialogues: list[AssDialogue] = []
    current_section = ''
    fields: list[str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith('[') and line.endswith(']'):
            current_section = line
            fields = None
            continue
        if current_section != '[Events]':
            continue
        if raw_line.startswith('Format:'):
            rest = raw_line[len('Format:'):]
            fields = [f.strip() for f in rest.split(',')]
            continue
        if raw_line.startswith('Dialogue:'):
            if not fields:
                continue
            rest = raw_line[len('Dialogue:'):]
            parts = rest.split(',', len(fields) - 1)
            if len(parts) < len(fields):
                continue
            row = dict(zip(fields, parts))
            if not all(k in row for k in ('Start', 'End', 'Style', 'Name', 'Text')):
                continue
            start_ms = _ass_ms(row['Start'])
            end_ms = _ass_ms(row['End'])
            if start_ms is None or end_ms is None:
                continue
            dialogues.append(
                AssDialogue(
                    style=row['Style'].strip(),
                    name=row['Name'].strip(),
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=row['Text'],
                )
            )
    return tuple(dialogues)


def _ass_number(value: str) -> float | None:
    try:
        number = float(value.strip())
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def style_band_from_ass(text: str, style: str) -> Band | None:
    """Vertical row of the named style: PlayResY from [Script Info]; Fontsize, Outline, Alignment, MarginV from its [V4+ Styles] row (read by the section Format). None when any value is missing or invalid, Alignment is 4/5/6, or the clipped band is empty; the caller then keeps its settings band."""
    play_res_y: float | None = None
    fields: list[str] | None = None
    row: dict[str, str] | None = None
    current_section = ''
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith('[') and line.endswith(']'):
            current_section = line
            fields = None
            continue
        if current_section == '[Script Info]' and line.startswith('PlayResY:'):
            play_res_y = _ass_number(line[len('PlayResY:'):])
        elif current_section == '[V4+ Styles]':
            if raw_line.startswith('Format:'):
                fields = [f.strip() for f in raw_line[len('Format:'):].split(',')]
            elif raw_line.startswith('Style:') and fields and row is None:
                parts = raw_line[len('Style:'):].split(',', len(fields) - 1)
                values = dict(zip(fields, (p.strip() for p in parts)))
                if len(parts) == len(fields) and values.get('Name') == style:
                    row = values
    if row is None or play_res_y is None or play_res_y <= 0:
        return None
    size = _ass_number(row.get('Fontsize', ''))
    outline = _ass_number(row.get('Outline', ''))
    margin_v = _ass_number(row.get('MarginV', ''))
    alignment = _ass_number(row.get('Alignment', ''))
    if size is None or outline is None or margin_v is None or alignment is None:
        return None
    height = 2 * (size + 2 * outline) / play_res_y
    if alignment in (7, 8, 9):
        top = margin_v / play_res_y
        bottom = top + height
    elif alignment in (1, 2, 3):
        bottom = 1 - margin_v / play_res_y
        top = bottom - height
    else:
        return None
    try:
        return Band(top=min(max(top, 0.0), 1.0), bottom=min(max(bottom, 0.0), 1.0))
    except ValueError:
        return None


def disclosure_band_from_ass(text: str) -> Band | None:
    return style_band_from_ass(text, DISCLOSURE_STYLE)


_K_TAG = re.compile(r'\{\\k(\d+)\}([^{]*)')


def karaoke_observations(dialogues: Sequence[AssDialogue]) -> tuple[KaraokeWordObservation, ...]:
    observations: list[KaraokeWordObservation] = []
    for dialogue in dialogues:
        if dialogue.style != KARAOKE_STYLE:
            continue
        cursor = dialogue.start_ms // 10
        for dur, word in _K_TAG.findall(dialogue.text):
            if word.strip():
                observations.append(
                    KaraokeWordObservation(
                        word_index=len(observations),
                        highlight_ms=cursor * 10,
                    )
                )
            cursor += int(dur)
    return tuple(observations)


def karaoke_sample_ms(dialogue: AssDialogue) -> int:
    """Sample moment of a Karaoke line: the middle of its longest timed word (the k tag with the longest duration that carries text); the middle of the line when no tag does."""
    cursor = dialogue.start_ms // 10
    best: tuple[int, int] | None = None
    for dur, word in _K_TAG.findall(dialogue.text):
        length = int(dur)
        if word.strip() and length > 0 and (best is None or length > best[1]):
            best = (cursor, length)
        cursor += length
    if best is None:
        return (dialogue.start_ms + dialogue.end_ms) // 2
    return best[0] * 10 + best[1] * 5


def evenly_sampled(items: Sequence[int], limit: int) -> list[int]:
    if len(items) <= limit:
        return list(items)
    return [items[(i * len(items)) // limit] for i in range(limit)]


_SSIM_ALL_RE = re.compile(r'All:([0-9]+(?:\.[0-9]+)?)')
COMPARE_GRAY = 'format=gray'  # QC-HOOK-FIX: full-range gray before any shrink, so both inputs share one pixel format and range
COMPARE_SCALE_FLAGS = 'area'  # QC-HOOK-FIX: box average for the large shrink; bicubic lifts full-range black by about 3 levels


def ssim_between(
    ffmpeg: Path,
    left: Path,
    left_ms: int | None,
    right: Path,
    right_ms: int | None,
    *,
    width: int,
    height: int,
    timeout_seconds: float,
    canvas: tuple[int, int] | None = None,
) -> float | None:
    """SSIM of one frame of left against one frame of right, both scaled to width x height.

    PW-F1-FIX4 and F-10-FIX6: the render places every still and clip on the output canvas with render_command.frame_placement (the single builder); with canvas=(W, H) the right input (still or sample clip) goes through that same builder before the shrink, so the QC compares what the render drew. canvas=None keeps the old filter chain; the left input (output frame) is never re-placed.

    QC-HOOK-FIX: each side is turned into full-range gray at its own size first (COMPARE_GRAY, which reads the frame's colour range),
    then shrunk with the area filter (COMPARE_SCALE_FLAGS). The old order shrank with bicubic in whatever pixel format and range the
    input had: a full-range output (scenes from JPEG make the render output yuvj420p) came out about 3 levels brighter than the
    limited-range hook clip, and near black the SSIM luminance term turns that into a failure (lot f132d43a: a dark Pixabay hook
    measured 0.117 on full-range outputs and 0.996 on limited-range ones with the same clip and the same frame)."""
    argv = [str(ffmpeg), '-hide_banner', '-nostdin', '-v', 'info']
    if left_ms is not None:
        argv.extend(['-ss', seek_arg(left_ms)])
    argv.extend(['-i', str(left)])
    if right_ms is not None:
        argv.extend(['-ss', seek_arg(right_ms)])
    argv.extend(['-i', str(right)])
    prep = f'{COMPARE_GRAY},scale={width}:{height}:force_original_aspect_ratio=increase:flags={COMPARE_SCALE_FLAGS},crop={width}:{height}'
    right_prep = prep
    if canvas is not None:
        right_prep = frame_placement(canvas[0], canvas[1], 'qc') + ',' + prep
    argv.extend([
        '-filter_complex',
        f'[0:v]{prep}[a];[1:v]{right_prep}[b];[a][b]ssim',
        '-frames:v',
        '1',
        '-f',
        'null',
        '-',
    ])
    try:
        res = subprocess.run(
            argv,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout_seconds,
            check=False,
        )
        if res.returncode != 0:
            return None
        out = res.stdout + chr(10) + res.stderr
        m = _SSIM_ALL_RE.search(out)
        if not m:
            return None
        return float(m.group(1))
    except (OSError, subprocess.TimeoutExpired):
        return None


def _has_non_latin_letter(text: str) -> bool:
    return any(ch.isalpha() and not unicodedata.name(ch, '').startswith('LATIN') for ch in text)


def observed_subtitle_locale(dialogues: Sequence[AssDialogue], claimed: str | None) -> str | None:
    """Locale of the burned-in subtitle: None when the ASS has no karaoke line (nothing observed); 'und' when a karaoke line holds a letter outside the Latin script; otherwise the locale claimed by D and E."""
    karaoke = [d for d in dialogues if d.style == KARAOKE_STYLE]
    if not karaoke:
        return None
    if any(_has_non_latin_letter(ASS_TAG_RE.sub('', d.text)) for d in karaoke):
        return UNDETERMINED_LOCALE
    return claimed


def audio_mix_result(
    stats: LoudnessStats, *, target_lufs: float, tolerance_lu: float, max_true_peak_dbtp: float, threshold_revision: str,
    evidence_ref: str,
) -> GateResult:
    """AUDIO_MIX_QUALITY warning gate: integrated loudness and true peak are recorded; out of target gives a failed warning, never a hard failure. Every limit is caller input."""
    gate = GateName.AUDIO_MIX_QUALITY
    if stats.integrated_lufs is None or stats.true_peak_dbtp is None:
        return GateResult(gate=gate, status=GateStatus.NOT_EVALUATED, evidence_ref=evidence_ref, threshold_revision=threshold_revision, reason='loudness_not_measured')
    reasons = []
    if abs(stats.integrated_lufs - target_lufs) > tolerance_lu:
        reasons.append('loudness_out_of_target')
    if stats.true_peak_dbtp > max_true_peak_dbtp:
        reasons.append('true_peak_above_limit')
    return GateResult(
        gate=gate,
        status=GateStatus.FAILED if reasons else GateStatus.PASSED,
        evidence_ref=f'{evidence_ref}:I={stats.integrated_lufs:.1f}LUFS:TP={stats.true_peak_dbtp:.1f}dBTP',
        measured_value=stats.integrated_lufs,
        threshold_revision=threshold_revision,
        reason=','.join(reasons) or None,
    )


class RealOutputInspector:
    def __init__(
        self,
        *,
        inputs: InspectionInputs,
        settings: InspectorSettings,
        ffmpeg_path: str | Path = DEFAULT_FFMPEG_PATH,
        lock_path: str | Path = DEFAULT_LOCK_PATH,
    ) -> None:
        self._inputs = inputs
        self._settings = settings
        self._ffmpeg = Path(ffmpeg_path)
        self._lock = Path(lock_path)
        self._probe = FrameProbe(ffmpeg_path=self._ffmpeg, timeout_seconds=settings.timeout_seconds)

    def inspect(self, output_ref: str, package: RenderPackageRecord) -> OutputEvidence:
        verify_ffmpeg_pin(self._ffmpeg, self._lock)
        media = Path(output_ref)
        if not media.is_file():
            return OutputEvidence()
        ass_path = self._ass_path(package)
        ass_text = self._ass_text(package)
        dialogues = () if ass_text is None else parse_ass_dialogues(ass_text)
        return OutputEvidence(
            visual_hook=self._visual_hook(media, package),
            audio_hook=self._audio_hook(media, package),
            thumbnail=self._thumbnail(media, package),
            subtitle=self._subtitle(media, dialogues, ass_path, self._subtitle_band(ass_text)),
            karaoke=self._karaoke(dialogues),
            language=self._language(package, dialogues),
            disclosure=self._disclosure(media, dialogues, ass_path, self._disclosure_band(ass_text)),
        )

    def _asset(self, package: RenderPackageRecord, ref: str | None) -> Path | None:
        if not isinstance(ref, str) or not ref:
            return None
        manifest = package.materialization_manifest
        if not isinstance(manifest, Mapping):
            return None
        entry = manifest.get(ref)
        if not isinstance(entry, Mapping):
            return None
        local = entry.get('local_ref')
        if not isinstance(local, str) or not local:
            return None
        root = self._inputs.staging_root.resolve()
        path = (root / local).resolve()
        if path.is_relative_to(root) and path.is_file():
            return path
        return None

    @staticmethod
    def _range(package: RenderPackageRecord, name: str) -> tuple[int, int] | None:
        hp = package.hook_placement
        if not isinstance(hp, Mapping):
            return None
        entry = hp.get(name)
        if not isinstance(entry, Mapping):
            return None
        start = entry.get('start_ms')
        end = entry.get('end_ms')
        if isinstance(start, bool) or not isinstance(start, int):
            return None
        if isinstance(end, bool) or not isinstance(end, int):
            return None
        if 0 <= start < end:
            return (start, end)
        return None

    def _ass_path(self, package: RenderPackageRecord) -> Path | None:
        path = self._asset(package, self._inputs.ass_ref)
        if path is None or path.suffix.lower() != '.ass':
            return None
        return path

    def _ass_text(self, package: RenderPackageRecord) -> str | None:
        path = self._ass_path(package)
        if path is None:
            return None
        try:
            return path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            return None

    def _dialogues(self, package: RenderPackageRecord) -> tuple[AssDialogue, ...]:
        text = self._ass_text(package)
        return () if text is None else parse_ass_dialogues(text)

    def speech_windows(self, package: RenderPackageRecord) -> tuple[tuple[int, int], ...]:
        """VOICE_AUDIBLE: ms ranges of the karaoke dialogue lines (the spoken parts); pass them as voice_windows to RealFfprobeProbe so audio_level is measured only where there is speech. Empty when the ASS is missing."""
        spans = [(d.start_ms, d.end_ms) for d in self._dialogues(package) if d.style == KARAOKE_STYLE and d.end_ms > d.start_ms]
        return tuple(sorted(spans))

    def _audio_hook(self, media: Path, package: RenderPackageRecord) -> AudioHookEvidence | None:
        hook = self._range(package, 'hook_time_range')
        if hook is None:
            return None
        stats = measure_audio(self._ffmpeg, media, windows=[hook], timeout_seconds=self._settings.timeout_seconds)
        if stats.level_db is None:
            return None
        hp = package.hook_placement
        ref = hp.get('audio_hook_ref') if isinstance(hp, Mapping) else None
        label = ref if isinstance(ref, str) and ref else media.name
        return AudioHookEvidence(
            evidence_ref=f'{GATE_AUDIO_HOOK}:{label}:{hook[0]}-{hook[1]}ms', start_ms=hook[0], end_ms=hook[1], level_db=stats.level_db,
        )

    def _language(self, package: RenderPackageRecord, dialogues: Sequence[AssDialogue]) -> LanguageEvidence | None:
        source = self._inputs.language
        if source is None:
            return None
        return LanguageEvidence(
            evidence_ref=f'{GATE_ENGLISH}:{source.evidence_ref}',
            script_fingerprint=source.script_fingerprint,
            voice_hash=source.voice_hash,
            subtitle_text_hash=source.subtitle_text_hash,
            output_metadata_revision=package.output_metadata_revision,
            script_locale=source.script_locale,
            voice_locale=source.voice_locale,
            subtitle_locale=observed_subtitle_locale(dialogues, source.subtitle_locale),
            title_locale=source.title_locale,
            hashtag_locale=source.hashtag_locale,
            declared_language=source.declared_language,
        )

    def _visual_hook(self, media: Path, package: RenderPackageRecord) -> VisualHookEvidence | None:
        hook = self._range(package, 'hook_time_range')
        hp = package.hook_placement
        ref = hp.get('visual_hook_ref') if isinstance(hp, Mapping) else None
        asset = self._asset(package, ref)
        if hook is None or ref is None or asset is None:
            return None
        sim = ssim_between(
            self._ffmpeg,
            media,
            hook[0],
            asset,
            None,
            width=self._settings.compare_width,
            height=self._settings.compare_height,
            timeout_seconds=self._settings.timeout_seconds,
            canvas=self._probe.frame_size(media),
        )
        if sim is None:
            return None
        return VisualHookEvidence(
            evidence_ref=f'{GATE_VISUAL_HOOK}:{ref}:{hook[0]}ms',
            start_ms=hook[0],
            end_ms=hook[0],
            similarity=sim,
        )

    def _thumbnail_asset_seek_ms(self, package: RenderPackageRecord, asset: Path, time_ms: int) -> int | None:
        """Seek of the thumbnail asset: the hook clip frame matching time_ms (clamped to its last frame, as the overlay repeats it); None for still images or any asset other than the hook asset."""
        hook = self._range(package, 'hook_time_range')
        hp = package.hook_placement
        hook_ref = hp.get('visual_hook_ref') if isinstance(hp, Mapping) else None
        hook_asset = self._asset(package, hook_ref)
        if hook is None or hook_asset is None or hook_asset != asset:
            return None
        duration = self._probe.duration_ms(asset)
        if duration is None:
            return None  # still image has no duration: keep the first frame
        offset = max(0, time_ms - hook[0])
        return max(0, min(offset, duration - HOOK_CLIP_LAST_FRAME_GUARD_MS))

    def _thumbnail(self, media: Path, package: RenderPackageRecord) -> ThumbnailEvidence | None:
        rng = self._range(package, 'thumbnail_time_range')
        hp = package.hook_placement
        ref = hp.get('thumbnail_ref') if isinstance(hp, Mapping) else None
        asset = self._asset(package, ref)
        if rng is None or ref is None or asset is None:
            return None
        time_ms = (rng[0] + rng[1]) // 2
        right_ms = self._thumbnail_asset_seek_ms(package, asset, time_ms)
        sim = ssim_between(
            self._ffmpeg,
            media,
            time_ms,
            asset,
            right_ms,
            width=self._settings.compare_width,
            height=self._settings.compare_height,
            timeout_seconds=self._settings.timeout_seconds,
            canvas=self._probe.frame_size(media),
        )
        if sim is None:
            return None
        asset_ref = ref if sim >= self._settings.thumbnail_min_ssim else f'{UNMATCHED_ASSET_PREFIX}{ref}'
        return ThumbnailEvidence(
            evidence_ref=f'{GATE_THUMBNAIL}:{ref}:{time_ms}ms',
            time_ms=time_ms,
            asset_ref=asset_ref,
        )

    def _has_text(self, diff: OverlayDifference | None) -> bool:
        return diff is not None and diff.ink > 0 and diff.residual <= self._settings.overlay_max_missing_share * diff.ink

    def _subtitle_band(self, ass_text: str | None) -> Band:
        derived = None if ass_text is None else style_band_from_ass(ass_text, KARAOKE_STYLE)
        return self._settings.subtitle_band if derived is None else derived

    def _subtitle(self, media: Path, dialogues: Sequence[AssDialogue], ass_path: Path | None, band: Band) -> SubtitleEvidence | None:
        karaoke = [d for d in dialogues if d.style == KARAOKE_STYLE]
        if not karaoke or ass_path is None:
            return None
        picked = evenly_sampled(list(range(len(karaoke))), self._settings.max_subtitle_samples)
        frames = sum(
            self._has_text(self._probe.overlay_difference(media, sample_ms=karaoke_sample_ms(karaoke[i]), subtitles_path=ass_path, top=band.top, bottom=band.bottom))
            for i in picked
        )
        return SubtitleEvidence(evidence_ref=f'{GATE_SUBTITLE}:{media.name}', frames_with_text=frames)

    def _karaoke(self, dialogues: Sequence[AssDialogue]) -> KaraokeEvidence | None:
        obs = karaoke_observations(dialogues)
        if not obs:
            return None
        return KaraokeEvidence(
            evidence_ref=f'{GATE_KARAOKE}:{self._inputs.ass_ref}',
            observations=obs,
        )

    def _disclosure_band(self, ass_text: str | None) -> Band:
        derived = None if ass_text is None else style_band_from_ass(ass_text, DISCLOSURE_STYLE)
        return self._settings.disclosure_band if derived is None else derived

    def _disclosure(
        self,
        media: Path,
        dialogues: Sequence[AssDialogue],
        ass_path: Path | None,
        band: Band,
    ) -> DisclosureEvidence | None:
        required: list[str] = []
        seen: set[str] = set()
        for seg in self._inputs.segments:
            if isinstance(seg, Mapping):
                sid = seg.get('segment_id')
                mode = seg.get('claim_mode')
                if isinstance(sid, str) and sid and mode in INFERENCE_CLAIM_MODES:
                    if sid not in seen:
                        seen.add(sid)
                        required.append(sid)
        if not required:
            return None
        windows = [d for d in dialogues if d.style == DISCLOSURE_STYLE]
        observations: list[DisclosureObservation] = []
        for segment_id in required:
            own = [w for w in windows if w.name == segment_id]
            visible = False
            if own and ass_path is not None:
                mid = (own[0].start_ms + own[0].end_ms) // 2
                visible = self._has_text(self._probe.overlay_difference(media, sample_ms=mid, subtitles_path=ass_path, top=band.top, bottom=band.bottom))
            observations.append(DisclosureObservation(segment_id=segment_id, visible=visible))
        return DisclosureEvidence(
            evidence_ref=f'{GATE_DISCLOSURE}:{media.name}',
            observations=tuple(observations),
        )


__all__ = [
    'AssDialogue',
    'Band',
    'GATE_SOURCES',
    'InspectionInputs',
    'InspectorSettings',
    'LanguageSource',
    'RealOutputInspector',
    'audio_mix_result',
    'disclosure_band_from_ass',
    'evenly_sampled',
    'karaoke_observations',
    'karaoke_sample_ms',
    'observed_subtitle_locale',
    'parse_ass_dialogues',
    'ssim_between',
    'style_band_from_ass',
]

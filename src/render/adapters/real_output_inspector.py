"""PW-F1: OutputInspectorPort over the pinned ffmpeg measuring VISUAL_HOOK, THUMBNAIL, SUBTITLE_BURNED_IN, KARAOKE_TIMING and INFERENCE_DISCLOSURE_PRESENT.

Every measurement threshold comes from InspectorSettings, no threshold constant in code;
missing inputs yield None in evidence fields.

coveredIds: PW-F1-01, CT-QC-001
"""
from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from render.adapters.frame_probe import FrameProbe, seek_arg
from render.adapters.real_ffmpeg_renderer import DEFAULT_FFMPEG_PATH, DEFAULT_LOCK_PATH, verify_ffmpeg_pin
from render.domain.content_gates import INFERENCE_CLAIM_MODES
from render.domain.karaoke_plan import STYLE_NAME as KARAOKE_STYLE
from render.domain.package_contract import RenderPackageRecord
from render.ports.output_inspector import (
    DisclosureEvidence,
    DisclosureObservation,
    KaraokeEvidence,
    KaraokeWordObservation,
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
    subtitle_min_difference: float
    disclosure_band: Band
    disclosure_min_difference: float
    baseline_min_gap_ms: int
    max_subtitle_samples: int
    timeout_seconds: float

    def __post_init__(self) -> None:
        for name in ('compare_width', 'compare_height', 'baseline_min_gap_ms', 'max_subtitle_samples'):
            val = getattr(self, name)
            if isinstance(val, bool) or not isinstance(val, int) or val <= 0:
                raise ValueError(name)
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or self.timeout_seconds <= 0:
            raise ValueError('timeout_seconds')
        if isinstance(self.thumbnail_min_ssim, bool) or not isinstance(self.thumbnail_min_ssim, (int, float)) or not (0 < self.thumbnail_min_ssim <= 1):
            raise ValueError('thumbnail_min_ssim')
        for name in ('subtitle_min_difference', 'disclosure_min_difference'):
            val = getattr(self, name)
            if isinstance(val, bool) or not isinstance(val, (int, float)) or val < 0:
                raise ValueError(name)


@dataclass(frozen=True, kw_only=True)
class InspectionInputs:
    staging_root: Path
    ass_ref: str
    segments: Sequence[Mapping]

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


def baseline_ms(windows: Sequence[tuple[int, int]], duration_ms: int | None, min_gap_ms: int) -> int | None:
    if duration_ms is None or duration_ms <= 0:
        return None
    clamped: list[tuple[int, int]] = []
    for start, end in windows:
        s = max(0, min(start, duration_ms))
        e = max(0, min(end, duration_ms))
        if s < e:
            clamped.append((s, e))
    clamped.sort()
    merged: list[tuple[int, int]] = []
    for s, e in clamped:
        if not merged:
            merged.append((s, e))
        else:
            prev_s, prev_e = merged[-1]
            if s <= prev_e:
                merged[-1] = (prev_s, max(prev_e, e))
            else:
                merged.append((s, e))
    gaps: list[tuple[int, int]] = []
    if not merged:
        gaps.append((0, duration_ms))
    else:
        if merged[0][0] > 0:
            gaps.append((0, merged[0][0]))
        for i in range(len(merged) - 1):
            gaps.append((merged[i][1], merged[i + 1][0]))
        if merged[-1][1] < duration_ms:
            gaps.append((merged[-1][1], duration_ms))
    candidates = [g for g in gaps if (g[1] - g[0]) >= min_gap_ms]
    if not candidates:
        return None
    longest = max(candidates, key=lambda g: g[1] - g[0])
    return (longest[0] + longest[1]) // 2


def evenly_sampled(items: Sequence[int], limit: int) -> list[int]:
    if len(items) <= limit:
        return list(items)
    return [items[(i * len(items)) // limit] for i in range(limit)]


_SSIM_ALL_RE = re.compile(r'All:([0-9]+(?:\.[0-9]+)?)')


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
) -> float | None:
    argv = [str(ffmpeg), '-hide_banner', '-nostdin', '-v', 'info']
    if left_ms is not None:
        argv.extend(['-ss', seek_arg(left_ms)])
    argv.extend(['-i', str(left)])
    if right_ms is not None:
        argv.extend(['-ss', seek_arg(right_ms)])
    argv.extend(['-i', str(right)])
    prep = f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},format=gray'
    argv.extend([
        '-filter_complex',
        f'[0:v]{prep}[a];[1:v]{prep}[b];[a][b]ssim',
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
        duration = self._probe.duration_ms(media)
        dialogues = self._dialogues(package)
        return OutputEvidence(
            visual_hook=self._visual_hook(media, package),
            thumbnail=self._thumbnail(media, package),
            subtitle=self._subtitle(media, dialogues, duration),
            karaoke=self._karaoke(dialogues),
            disclosure=self._disclosure(media, dialogues, duration),
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

    def _dialogues(self, package: RenderPackageRecord) -> tuple[AssDialogue, ...]:
        path = self._asset(package, self._inputs.ass_ref)
        if path is None or path.suffix.lower() != '.ass':
            return ()
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            return ()
        return parse_ass_dialogues(text)

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
        )
        if sim is None:
            return None
        return VisualHookEvidence(
            evidence_ref=f'{GATE_VISUAL_HOOK}:{ref}:{hook[0]}ms',
            start_ms=hook[0],
            end_ms=hook[0],
            similarity=sim,
        )

    def _thumbnail(self, media: Path, package: RenderPackageRecord) -> ThumbnailEvidence | None:
        rng = self._range(package, 'thumbnail_time_range')
        hp = package.hook_placement
        ref = hp.get('thumbnail_ref') if isinstance(hp, Mapping) else None
        asset = self._asset(package, ref)
        if rng is None or ref is None or asset is None:
            return None
        time_ms = (rng[0] + rng[1]) // 2
        sim = ssim_between(
            self._ffmpeg,
            media,
            time_ms,
            asset,
            None,
            width=self._settings.compare_width,
            height=self._settings.compare_height,
            timeout_seconds=self._settings.timeout_seconds,
        )
        if sim is None:
            return None
        asset_ref = ref if sim >= self._settings.thumbnail_min_ssim else f'{UNMATCHED_ASSET_PREFIX}{ref}'
        return ThumbnailEvidence(
            evidence_ref=f'{GATE_THUMBNAIL}:{ref}:{time_ms}ms',
            time_ms=time_ms,
            asset_ref=asset_ref,
        )

    def _subtitle(
        self,
        media: Path,
        dialogues: Sequence[AssDialogue],
        duration: int | None,
    ) -> SubtitleEvidence | None:
        karaoke = [d for d in dialogues if d.style == KARAOKE_STYLE]
        if not karaoke:
            return None
        base = baseline_ms([(d.start_ms, d.end_ms) for d in dialogues], duration, self._settings.baseline_min_gap_ms)
        if base is None:
            return None
        samples = evenly_sampled([(d.start_ms + d.end_ms) // 2 for d in karaoke], self._settings.max_subtitle_samples)
        frames = 0
        for t in samples:
            diff = self._probe.band_difference(
                media,
                sample_ms=t,
                baseline_ms=base,
                width=self._settings.compare_width,
                height=self._settings.compare_height,
                top=self._settings.subtitle_band.top,
                bottom=self._settings.subtitle_band.bottom,
            )
            if diff is not None and diff >= self._settings.subtitle_min_difference:
                frames += 1
        return SubtitleEvidence(
            evidence_ref=f'{GATE_SUBTITLE}:{media.name}',
            frames_with_text=frames,
        )

    def _karaoke(self, dialogues: Sequence[AssDialogue]) -> KaraokeEvidence | None:
        obs = karaoke_observations(dialogues)
        if not obs:
            return None
        return KaraokeEvidence(
            evidence_ref=f'{GATE_KARAOKE}:{self._inputs.ass_ref}',
            observations=obs,
        )

    def _disclosure(
        self,
        media: Path,
        dialogues: Sequence[AssDialogue],
        duration: int | None,
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
        base = baseline_ms([(w.start_ms, w.end_ms) for w in windows], duration, self._settings.baseline_min_gap_ms)
        observations: list[DisclosureObservation] = []
        for segment_id in required:
            own = [w for w in windows if w.name == segment_id]
            visible = False
            if own and base is not None:
                mid = (own[0].start_ms + own[0].end_ms) // 2
                diff = self._probe.band_difference(
                    media,
                    sample_ms=mid,
                    baseline_ms=base,
                    width=self._settings.compare_width,
                    height=self._settings.compare_height,
                    top=self._settings.disclosure_band.top,
                    bottom=self._settings.disclosure_band.bottom,
                )
                visible = diff is not None and diff >= self._settings.disclosure_min_difference
            observations.append(DisclosureObservation(segment_id=segment_id, visible=visible))
        return DisclosureEvidence(
            evidence_ref=f'{GATE_DISCLOSURE}:{media.name}',
            observations=tuple(observations),
        )


__all__ = [
    'AssDialogue',
    'Band',
    'InspectionInputs',
    'InspectorSettings',
    'RealOutputInspector',
    'baseline_ms',
    'evenly_sampled',
    'karaoke_observations',
    'parse_ass_dialogues',
    'ssim_between',
]

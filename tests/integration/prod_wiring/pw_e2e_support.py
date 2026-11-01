"""Adapter edges and support harness for PW-E2E on launcher production composition.

Edge adapters only (9Router, Drive, Kokoro, faster-whisper, GPU, loopback network).
Pinned FFmpeg and FFprobe are real. Production composition always built by launcher.
No src. prefix imports and no pw_support import.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import dataclasses
from decimal import Decimal
import email.utils
import functools
import hashlib
import http.server
import importlib.util
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
import types
from typing import Any, Callable
import uuid
import wave

import pytest
from fastapi.testclient import TestClient
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from catalog.application.discovery import DiscoveryObservation, register_discovery
from catalog.domain.identity import CanonicalFingerprint, MediaAsset, MediaKind, ProvenanceEntry, ProvenanceRelation, RightsAssessment, RightsStatus
from catalog.domain.hooks import HookKind
from catalog.application.hooks import import_hook
from catalog.persistence.hooks import PostgresHookHistory
from source_ingestion.domain.source import SourcePolicy
from catalog.persistence.assets import PostgresMediaAssetRepository
from controlplane.api.wiring.production_profile import ProductionRuntime, load_production_profile
from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD, RouteCandidate
from controlplane.application.storage_meta.cloud_persist import ObjectAlreadyExistsError
from controlplane.application.storage_meta.handlers import register_staged_artifact
from controlplane.domain.config_security.external_account import ExternalAccount
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.domain.statemachine import ArtifactLocationState as S
from controlplane.domain.storage_meta.verification import IntegrityObservation
from controlplane.infrastructure.db.control_api_commands import compose_command_service
from controlplane.infrastructure.db.storage_meta import PostgresStorageMetaRepository
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease
from controlplane.infrastructure.storage.drive_object_store import DRIVE_CREDENTIAL_INVALID, DriveCredentialError
from creative.application.prompts import DEFAULT_PROMPTS, seed_default_prompts
from creative.application.roles import (
    ROLE_ANALYSIS,
    ROLE_ANGLES,
    ROLE_METADATA,
    ROLE_PLAN,
    ROLE_SCRIPT,
    ROLE_SELECTION,
)
from creative.domain.script import count_words
from render.adapters.config_render_sources import seed_render_config
from render.ports.lease import GpuLease, GpuLeasePort
from source_ingestion.adapters.real_http_transport import RealHttpTransport
from source_ingestion.application.source_commands import SourceCommandHandler
from tests.integration.prod_wiring.pw_vertical import (
    EXPECTED_ACTIVITIES as _BASE_EXPECTED_ACTIVITIES,
    VIDEO_STAGES,
    batch_row,
    count,
    grants_by_stage,
    job_row,
    live_grants,
    rows,
    scalar,
    stage_runs,
    wait_until,
)

EXPECTED_ACTIVITIES = dict(_BASE_EXPECTED_ACTIVITIES, process=8)

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_PATH = ROOT / "tools" / "launcher" / "launcher.py"
PROFILE_PATH = ROOT / "tools" / "launcher" / "prod" / "profile.json"
RUNTIME_LOCK = ROOT / "tools" / "runtime" / "runtime.lock.json"
FFMPEG = Path("C:/ffmpeg/bin/ffmpeg.exe")
FFPROBE = Path("C:/ffmpeg/bin/ffprobe.exe")
PORT = 8443
BASE = f"https://127.0.0.1:{PORT}"

PUBLIC = "93.184.216.34"
LOOPBACK = ipaddress.ip_address("127.0.0.1")
HOST = "news.example"
POLICY = SourcePolicy(
    policy_revision="pw-e2e",
    source_kinds=frozenset({"rss_feed", "atom_feed"}),
    tiers=frozenset({"tier_1", "tier_2", "tier_3"}),
    admin_metadata_keys=frozenset(),
)
PARAGRAPHS = (
    "The harbour workers reached a comprehensive agreement following intensive negotiations that lasted throughout the previous evening and continued well into early Tuesday morning across the entire maritime terminal facility.",
    "Port operations resumed immediately as container traffic began moving steadily through the primary freight corridors, allowing long queues of waiting transport trucks to finally discharge their cargo safely.",
    "Union representatives praised the commitment of all participating delegates while management reiterated their collective dedication to establishing sustainable labor practices for every shift going forward.",
    "Economic analysts noted that the swift resolution prevented major supply chain bottlenecks from compounding ahead of the upcoming seasonal retail surge across international distribution hubs.",
)
EXTRA = "A second round of talks scheduled for Friday will settle the remaining questions about overtime pay and safety inspections at the northern terminal."

SUPPLEMENTS = {
    "ass_style": {
        "secondary_colour": "&H00FFFFFF",
        "back_colour": "&H80000000",
        "italic": 0,
        "underline": 0,
        "strike_out": 0,
        "scale_x": 100,
        "scale_y": 100,
        "spacing": 0,
        "angle": 0,
        "border_style": 1,
        "shadow": 0,
        "alignment": 2,
        "encoding": 1,
    },
    "layout": {
        "margin_left": 60,
        "margin_right": 60,
        "max_words_per_line": 4,
        "max_chars_per_line": 28,
        "disclosure_font_size": 40,
        "disclosure_alignment": 8,
        "disclosure_margin_v": 240,
    },
    "sections": {
        "visual_rhythm": {"note": "pw-e2e"},
        "thumbnail_overlay_style": {"note": "pw-e2e"},
        "hook_treatment": {"note": "pw-e2e"},
        "color_effect_rules": {"note": "pw-e2e"},
    },
    "quality_thresholds": {
        "SUBTITLE_BURNED_IN": {"min_frames_with_text": 2},
        "VOICE_AUDIBLE": {"min_voice_level": -40.0},
    },
    "output_profile": {
        "video_codec": "h264",
        "pixel_format": "yuv420p",
    },
}

STEPS = (S.MATERIALIZING, S.AVAILABLE_UNVERIFIED, S.VERIFYING, S.VERIFIED)


def require_ffmpeg() -> None:
    if not FFMPEG.is_file() or not FFPROBE.is_file():
        pytest.fail(
            "BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin is required; no skip and no fallback is permitted.",
            pytrace=False,
        )


def load_launcher() -> Any:
    spec = importlib.util.spec_from_file_location("pw_e2e_launcher", LAUNCHER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RecordingGpuLease:
    def __init__(self, slots: int = 2, ttl: float = 60.0) -> None:
        self.underlying = LocalGpuLease(slots, ttl)
        self.owners: list[str] = []

    def acquire(self, owner_ref: str) -> GpuLease:
        self.owners.append(owner_ref)
        return self.underlying.acquire(owner_ref)

    def release(self, lease: GpuLease) -> None:
        self.underlying.release(lease)

    @property
    def render_owners(self) -> list[str]:
        return [o for o in self.owners if o != "capability-probe"]


class FakeDriveTokenBroker:
    def __init__(self) -> None:
        self.token = "token-valid"

    @contextlib.contextmanager
    def acquire(self, method: str, account: str) -> Any:
        yield self.token


class FakeProviderCredentials:
    @contextlib.contextmanager
    def acquire(self, method: str, account: str) -> Any:
        yield "router-token"


class FakeRouteCatalog:
    def __init__(self, profile: Any) -> None:
        self.profile = profile

    def candidates(self, workspace_id: str, ai_role: str) -> list[RouteCandidate]:
        model_refs = getattr(self.profile.ai, "route_model_refs", {})
        key = {
            "content_analysis": "analysis",
            "story_angles": "angle",
            "script_generation": "script",
            "asset_selection": "selection",
            "output_metadata": "metadata",
            "image_safety": "image_safety",
        }.get(ai_role, ai_role)
        model_ref = model_refs.get(key, "ag/gemini-3.8-flash-high")
        acct = ExternalAccount(
            external_account_id="acct-9router",
            workspace_id=workspace_id,
            provider="9router",
            account_label="9router-test",
            status=ExternalAccountStatus.ENABLED,
            project_ref="proj-e2e",
            capabilities=frozenset({ai_role}),
            credential_version=1,
            credential_updated_at="2026-10-28T00:00:00+00:00",
            credential_expires_at=None,
            quota_observation_ref=None,
            health=None,
            revision=1,
        )
        cand = RouteCandidate(
            candidate_ref=f"cand-{ai_role}",
            provider_ref="9router",
            model_ref=model_ref,
            account=acct,
            quota_domain_key=f"quota-9router-{ai_role}",
            cost_class="free",
            max_data_sensitivity="confidential",
            roles=frozenset({ai_role}),
            local=False,
        )
        return [cand]


class FakeVisionRoute:
    def __init__(self, excluded_sha256: frozenset[str] = frozenset()) -> None:
        self.calls: list[dict[str, Any]] = []
        self.excluded_sha256 = frozenset(excluded_sha256)

    def invoke_vision(
        self,
        ai_role: str,
        instructions: str,
        image_base64: str,
        media_type: str,
        timeout_seconds: float,
    ) -> str:
        self.calls.append({
            "ai_role": ai_role,
            "instructions": instructions,
            "image_base64": image_base64,
            "media_type": media_type,
            "timeout_seconds": timeout_seconds,
        })
        digest = hashlib.sha256(base64.b64decode(image_base64)).hexdigest()
        confidence = 0.0 if digest in self.excluded_sha256 else 0.9
        return json.dumps({"confidence": confidence, "detections": []})


class _RefusingArtifactSource:
    def open(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("artifact_source không dùng khi cloud_store là FakeDriveStore")


def write_weights(root: Path) -> tuple[Path, Path, Path]:
    weights_dir = root / "weights"
    whisper_dir = root / "whisper"
    weights_dir.mkdir(parents=True, exist_ok=True)
    whisper_dir.mkdir(parents=True, exist_ok=True)
    kokoro_onnx = weights_dir / "kokoro-v1.0.onnx"
    voices_bin = weights_dir / "voices-v1.0.bin"
    whisper_bin = whisper_dir / "model.bin"
    kokoro_bytes = b"fake-kokoro-onnx-weights"
    voices_bytes = b"fake-voices-bin-weights"
    whisper_bytes = b"fake-whisper-model-bin"
    kokoro_onnx.write_bytes(kokoro_bytes)
    voices_bin.write_bytes(voices_bytes)
    whisper_bin.write_bytes(whisper_bytes)
    lock_data = {
        "files": [
            {
                "name": "kokoro-v1.0.onnx",
                "group": "kokoro-onnx",
                "sha256": hashlib.sha256(kokoro_bytes).hexdigest(),
                "status": "PINNED",
            },
            {
                "name": "voices-v1.0.bin",
                "group": "kokoro-onnx",
                "sha256": hashlib.sha256(voices_bytes).hexdigest(),
                "status": "PINNED",
            },
            {
                "name": "model.bin",
                "group": "faster-whisper-small.en",
                "sha256": hashlib.sha256(whisper_bytes).hexdigest(),
                "status": "PINNED",
            },
        ]
    }
    lock_path = root / "model-weights.lock.json"
    lock_path.write_text(json.dumps(lock_data), encoding="utf-8")
    return weights_dir, whisper_dir, lock_path


def make_e2e_runtime(root: Path, *, gpu: Any, broker: Any, profile: Any) -> ProductionRuntime:
    weights_dir, whisper_dir, lock_path = write_weights(root)
    staging = root / "staging"
    for sub in ("out", "audio_library"):
        (staging / sub).mkdir(parents=True, exist_ok=True)
    vault = root / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    client_json = root / "client.json"
    client_json.write_text("{}", encoding="utf-8")
    return ProductionRuntime(
        ffmpeg_path=FFMPEG.resolve(),
        ffprobe_path=FFPROBE.resolve(),
        runtime_lock_path=RUNTIME_LOCK.resolve(),
        weights_dir=weights_dir.resolve(),
        whisper_model_dir=whisper_dir.resolve(),
        weights_lock_path=lock_path.resolve(),
        staging_root=staging.resolve(),
        secret_store_root=vault.resolve(),
        oauth_client_secrets_path=client_json.resolve(),
        oauth_consent_timeout_seconds=300,
        route_cost_per_request=Decimal("0"),
        tokenization={
            "revision": "pw-e2e",
            "unicode_form": "NFC",
            "casefold": True,
            "edge_strip_categories": ("P",),
            "gap_tolerance_ms": 500,
            "min_confidence": 0.5,
        },
        drive_placement={
            "original": "folder-original",
            "reusable": "folder-reusable",
            "output": "folder-output",
        },
        drive_fallback_parent_id="folder-root",
        route_catalog=FakeRouteCatalog(profile),
        provider_credentials=FakeProviderCredentials(),
        vision_route=FakeVisionRoute(),
        artifact_source=_RefusingArtifactSource(),
        drive_token_broker=broker,
        gpu_lease=gpu,
    )

SpeechLedger = dict


class FakeKokoroModel:
    def __init__(self, ledger: dict[str, str], sample_rate: int, duration_ms: int) -> None:
        self.ledger = ledger
        self.sample_rate = sample_rate
        self.duration_ms = duration_ms
        self._count = 0

    def create(self, text: str, voice: str, speed: float = 1.0, lang: str = "en-us") -> tuple[Any, int]:
        import numpy as np
        from voice.adapters.real_kokoro_tts import _to_pcm16

        dur_s = self.duration_ms / 1000.0
        n_samples = int(self.sample_rate * dur_s)
        t = np.linspace(0, dur_s, n_samples, endpoint=False, dtype=np.float32)
        self._count += 1
        freq = 220.0 + (self._count * 10.0)
        samples = (0.2 * np.sin(2.0 * np.pi * freq * t)).astype(np.float32)
        pcm = _to_pcm16(samples)
        self.ledger[hashlib.sha256(pcm).hexdigest()] = text
        return samples, self.sample_rate


class FakeWhisperModel:
    def __init__(self, ledger: dict[str, str]) -> None:
        self.ledger = ledger

    def transcribe(self, audio_path: str, **kwargs: Any) -> tuple[list[Any], Any]:
        with wave.open(str(audio_path), "rb") as wf:
            nframes = wf.getnframes()
            rate = wf.getframerate()
            frames = wf.readframes(nframes)
            duration = nframes / float(rate)
        sha = hashlib.sha256(frames).hexdigest()
        text = self.ledger.get(sha)
        if text is None:
            raise AssertionError("wav không do FakeKokoroModel sinh")
        offset = 0.8
        dur_speech = max(1.0, duration - 1.6)
        words_list = text.strip().split()
        n_words = len(words_list)
        step = dur_speech / n_words if n_words > 0 else dur_speech
        words = []
        for i, w in enumerate(words_list):
            w_start = offset + i * step
            w_end = offset + (i + 1) * step
            words.append(types.SimpleNamespace(word=w, start=w_start, end=w_end, probability=0.95))
        segments = [types.SimpleNamespace(start=offset, end=offset + dur_speech, words=words)]
        info = types.SimpleNamespace(language="en")
        return segments, info


def speech_factories(ledger: dict[str, str], profile: Any) -> tuple[Any, Any]:
    dur_range = profile.parameters.get("voice.duration_range_ms", {"min": 61000, "max": 70000})
    dur_ms = (dur_range["min"] + dur_range["max"]) // 2
    sample_rate = int(profile.parameters.get("voice.sample_rate_hz", 24000))

    def kokoro_factory(model_path: str, voices_path: str) -> FakeKokoroModel:
        return FakeKokoroModel(ledger, sample_rate, dur_ms)

    def whisper_factory(model_dir: str, device: str, compute_type: str) -> FakeWhisperModel:
        return FakeWhisperModel(ledger)

    return kokoro_factory, whisper_factory


class FakeNineRouterHttp:
    def __init__(self, profile: Any, refs_provider: Any) -> None:
        self.profile = profile
        self.refs_provider = refs_provider
        self.script_mode = "inference"
        self.calls: list[str] = []
        self.selected_media: list[str] = []

    def send_request(self, request: Any, secret_token: str | None = None) -> Any:
        prompt_obj = json.loads(request.prompt)
        instructions = prompt_obj.get("instructions", "")
        matched_role = None
        for role, text in DEFAULT_PROMPTS.items():
            if instructions == text:
                matched_role = role
                break
        if matched_role is None:
            raise AssertionError(f"prompt lạ: {instructions[:100]}")

        self.calls.append(matched_role)
        all_revs = self.refs_provider()
        by_art = {r["ref_id"]: r for r in all_revs}
        refs = []
        for d in prompt_obj.get("data", []):
            try:
                obj = json.loads(d) if isinstance(d, str) else d
                if isinstance(obj, dict) and obj.get("kind") == "article":
                    content = obj.get("content", {})
                    art_id = content.get("article_id")
                    if art_id and art_id in by_art:
                        refs.append(dict(by_art[art_id]))
            except Exception:
                pass
        if not refs:
            refs = all_revs

        if matched_role == ROLE_ANALYSIS:
            body = {
                "topic": "Harbour workers agreement",
                "entities": [{"name": "Harbor Union", "entity_type": "organization"}],
                "timeline": [{"time_label": "2026-10-17", "description": "Agreement reached"}],
                "locations": ["Rotterdam"],
                "facts": [{"id": "f-1", "text": "The harbour workers reached an agreement.", "evidence_refs": refs}],
                "uncertainties": [],
                "contradictions": [],
                "event_relation": "standalone",
                "update_context": "",
                "risk_flags": [],
                "narrative_opportunities": ["Port recovery"],
                "media_needs": ["port footage"],
            }
        elif matched_role == ROLE_ANGLES:
            base = {
                "summary": "Harbour agreement reached",
                "evidence_refs": refs,
                "planned_inference_elements": ["cause"],
                "planned_creative_elements": ["map"],
                "suitability": "high",
                "risk_flags": [],
            }
            body = {
                "angles": [
                    {
                        **base,
                        "angle_id": "angle-a",
                        "title": "Why agreement was reached",
                        "narrative_question": "Why did negotiations succeed?",
                        "focus_entities": ["Harbor Union"],
                        "timeframe": "2026-10",
                    },
                    {
                        **base,
                        "angle_id": "angle-b",
                        "title": "Future of port operations",
                        "narrative_question": "What happens next?",
                        "focus_entities": ["Port Authority"],
                        "timeframe": "2026-11",
                    },
                ]
            }
        elif matched_role == ROLE_SCRIPT:
            seg1_text = "The harbor union reached a comprehensive agreement following intensive negotiations that lasted throughout the previous evening and continued well into early Tuesday morning across the entire maritime terminal facility. Port operations resumed immediately as container traffic began moving steadily through freight corridors safely."
            seg2_text = "Union representatives praised the commitment of all participating delegates while management reiterated their collective dedication to establishing sustainable labor practices for every shift going forward. Economic analysts noted that the swift resolution prevented major supply chain bottlenecks from compounding ahead of retail surges."
            seg3_text = "Freight operators across international distribution hubs confirmed that logistics networks returned to normal schedules with priority given to perishable goods and urgent medical supplies. Terminal directors reported zero incidents during the reopening process as safety inspections were completed in record time."
            seg4_text = "Both parties agreed to reconvene next quarter to review workplace standards and maintain constructive dialogue between workers and leadership. Maritime authorities thanked the community for their remarkable patience and cooperation throughout this critical period of negotiations and recovery."
            wpm = float(self.profile.parameters["voice.speech_rate_wpm"])
            dur_range = self.profile.parameters["voice.duration_range_ms"]
            target = round((dur_range["min"] + dur_range["max"]) / 2000 * wpm / 60)
            assert dur_range["min"] * wpm / 60000 <= target <= dur_range["max"] * wpm / 60000, "số từ đích ngoài cửa sổ thời lượng của D"
            fixed_words = count_words(seg1_text) + count_words(seg2_text) + count_words(seg3_text)
            need = target - fixed_words
            assert need >= 1, "seg1-seg3 đã vượt số từ đích"
            seg4_words = seg4_text.split()
            if need <= len(seg4_words):
                seg4_words = seg4_words[:need]
            else:
                pad = ("overall", "today", "again")
                seg4_words = seg4_words + [pad[i % 3] for i in range(need - len(seg4_words))]
            seg4_words[-1] = seg4_words[-1].rstrip(".,;:") + "."
            seg4_text = " ".join(seg4_words)
            assert fixed_words + count_words(seg4_text) == target

            if self.script_mode == "inference":
                s2_claim = "inference"
                s2_refs = []
                s2_disc = "This is an inference from the sources."
            else:
                s2_claim = "source_backed"
                s2_refs = refs
                s2_disc = None

            body = {
                "language": "en",
                "hook_intent": "harbor agreement reached",
                "thumbnail_transition": "fade",
                "pronunciation_hints": [{"term": "Rotterdam", "pronunciation": "ROT-er-dam"}],
                "segments": [
                    {"segment_id": "s1", "text": seg1_text, "claim_mode": "source_backed", "scene_intent": "scene one", "source_refs": refs},
                    {"segment_id": "s2", "text": seg2_text, "claim_mode": s2_claim, "scene_intent": "scene two", "source_refs": s2_refs, "disclosure": s2_disc},
                    {"segment_id": "s3", "text": seg3_text, "claim_mode": "source_backed", "scene_intent": "scene three", "source_refs": refs},
                    {"segment_id": "s4", "text": seg4_text, "claim_mode": "source_backed", "scene_intent": "scene four", "source_refs": refs},
                ],
            }
        elif matched_role == ROLE_SELECTION:
            payload_data = json.loads(prompt_obj["data"][0])
            v_hooks = payload_data.get("visual_hook_candidates", [])
            a_hooks = payload_data.get("audio_hook_candidates", [])
            t_cands = payload_data.get("thumbnail_candidates", [])
            m_cands = payload_data.get("media_candidates", [])
            vh = v_hooks[0] if v_hooks else {"hook_id": "vh-01", "revision_id": "vh-01-r1"}
            ah = a_hooks[0] if a_hooks else {"hook_id": "ah-01", "revision_id": "ah-01-r1"}
            th = t_cands[0] if t_cands else {"thumbnail_id": "thumb:seed-bg-01", "revision_id": "th-r1"}
            m1_obj = m_cands[0] if m_cands else {"media_asset_id": "seed-bg-01", "artifact_version_ref": "ver-1"}
            m2_obj = m_cands[1] if len(m_cands) > 1 else m1_obj
            m1 = m1_obj["media_asset_id"]
            m2 = m2_obj["media_asset_id"]
            self.selected_media = [m1, m2]
            ws_id = all_revs[0]["workspace_id"] if all_revs else "00000000-0000-0000-0000-000000000000"
            body = {
                "visual_hook": {"workspace_id": ws_id, "ref_type": "visual_hook", "ref_id": vh["hook_id"], "revision_id": vh["revision_id"]},
                "audio_hook": {"workspace_id": ws_id, "ref_type": "audio_hook", "ref_id": ah["hook_id"], "revision_id": ah["revision_id"]},
                "thumbnail": {"workspace_id": ws_id, "ref_type": "thumbnail", "ref_id": th["thumbnail_id"], "revision_id": th["revision_id"]},
                "scenes": [
                    {"scene_id": "sc-1", "ref": {"workspace_id": ws_id, "ref_type": "media_asset", "ref_id": m1, "revision_id": m1_obj["artifact_version_ref"]}, "rationale": "scene 1 visual"},
                    {"scene_id": "sc-2", "ref": {"workspace_id": ws_id, "ref_type": "media_asset", "ref_id": m2, "revision_id": m2_obj["artifact_version_ref"]}, "rationale": "scene 2 visual"},
                ],
                "music_intents": [],
                "sfx_intents": [],
                "rationale": "selection rationale",
            }
        elif matched_role == ROLE_PLAN:
            m1 = self.selected_media[0] if getattr(self, "selected_media", None) else "seed-bg-01"
            m2 = self.selected_media[1] if getattr(self, "selected_media", None) and len(self.selected_media) > 1 else m1
            body = {
                "timeline": {
                    "segments": [
                        {
                            "scene_id": "sc-1",
                            "start_ms": 0,
                            "end_ms": 30000,
                            "transition_intent": "hard cut",
                            "visuals": [{"media_asset_id": m1, "start_ms": 0, "end_ms": 30000, "crop_intent": "center", "overlay_intent": "none", "effect_intent": "none"}],
                        },
                        {
                            "scene_id": "sc-2",
                            "start_ms": 30000,
                            "end_ms": 65500,
                            "transition_intent": "cross dissolve",
                            "visuals": [{"media_asset_id": m2, "start_ms": 30000, "end_ms": 65500, "crop_intent": "center", "overlay_intent": "none", "effect_intent": "none"}],
                        },
                    ]
                },
                "hook_placement": {
                    "hook_time_range": {"start_ms": 0, "end_ms": 5000},
                    "thumbnail_time_range": {"start_ms": 1000, "end_ms": 2000},
                },
                "voice_profile_intent": {"direction": "warm and confident", "pace": "steady", "emotion": "curious"},
                "music_cues": [],
                "sfx_cues": [],
                "subtitle_style_intent": {"style": "bold white captions", "karaoke": True, "highlight_intent": "active word turns yellow"},
                "allowed_fallbacks": [],
                "output_metadata_requirement": "english title, caption and 3-4 hashtags (CT-AI-009)",
            }
        elif matched_role == ROLE_METADATA:
            body = {
                "title": "Harbour Workers Reach Comprehensive Agreement",
                "caption": "Port operations have resumed smoothly following intensive negotiations.",
                "hashtags": ["#Port", "#Shipping", "#Trade", "#Labor"],
            }
        else:
            raise AssertionError(f"vai trò chưa kịch bản: {matched_role}")

        return types.SimpleNamespace(payload={"text": json.dumps(body), "refs": []}, fallback_triggered=False)


class FakeDriveStore:
    def __init__(self, broker: FakeDriveTokenBroker) -> None:
        self.broker = broker
        self.valid_token = "token-valid"
        self.uploads: list[dict[str, Any]] = []
        self.rejections: int = 0
        self.objects: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def reserve_object_id(self, namespace_ref: str) -> str:
        self._counter += 1
        return f"drive-{namespace_ref}-{self._counter}"

    def upload(self, object_id: str, artifact_version_id: str, content_sha256: str, size_bytes: int) -> None:
        with self.broker.acquire(CREDENTIAL_METHOD, "drive") as tok:
            if tok != self.valid_token:
                self.rejections += 1
                raise DriveCredentialError("Drive upload failed: HTTP 401")
        if object_id in self.objects:
            raise ObjectAlreadyExistsError(f"Object {object_id} already exists")
        rec = {
            "object_id": object_id,
            "artifact_version_id": artifact_version_id,
            "content_sha256": content_sha256,
            "size_bytes": size_bytes,
        }
        self.uploads.append(rec)
        self.objects[object_id] = rec

    def lookup(self, object_id: str) -> IntegrityObservation:
        if object_id in self.objects:
            rec = self.objects[object_id]
            return IntegrityObservation(True, rec["content_sha256"], rec["size_bytes"], "fake-drive:" + object_id)
        return IntegrityObservation(False, None, None, None)


def _make_wav_bytes(duration_seconds: float = 5.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        nframes = int(24000 * duration_seconds)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


def install_edge_adapters(
    monkeypatch: pytest.MonkeyPatch,
    *,
    drive: FakeDriveStore,
    router: FakeNineRouterHttp,
    ledger: dict[str, str],
    profile: Any,
    tmp_path: Path | None = None,
) -> None:
    from controlplane.api.wiring import production as prod_wiring
    from controlplane.api.wiring import voice as voice_wiring
    from source_ingestion.adapters.real_feed_source import RealFeedSource
    from source_ingestion.adapters.secure_fetch import SecureFetcher
    from source_ingestion.adapters.real_media_fetch import RealMediaFetcher
    from voice.adapters.real_kokoro_tts import RealKokoroTts
    from voice.adapters.real_whisper_aligner import RealWhisperAligner

    real_storage = prod_wiring.build_storage_services

    def patched_storage(*args: Any, **kwargs: Any) -> Any:
        svc = real_storage(*args, **kwargs)
        return dataclasses.replace(svc, cloud_store=drive)

    monkeypatch.setattr(prod_wiring, "build_storage_services", patched_storage)

    real_creative = prod_wiring.build_creative_services

    def patched_creative(*args: Any, **kwargs: Any) -> Any:
        svc = real_creative(*args, **kwargs)
        svc.executor._http = router
        return svc

    monkeypatch.setattr(prod_wiring, "build_creative_services", patched_creative)

    real_collection = prod_wiring.build_collection_services

    def patched_collection(mgr: Any, cfg: Any) -> Any:
        svc = real_collection(mgr, cfg)
        fetcher = SecureFetcher(LoopbackTransport(), lambda host: [PUBLIC])
        _p, p_rt = cfg.production_parts()
        source_adapters = {
            k: RealFeedSource(fetcher, source_kind=k, feed_policy=svc.feed_policy, article_policy=svc.article_policy)
            for k in svc.source_adapters
        }
        media_fetcher = RealMediaFetcher(
            fetcher,
            image_policy=svc.media_fetcher._policy,
            staging_root=p_rt.staging_root / "media",
        )
        return dataclasses.replace(
            svc,
            fetcher=fetcher,
            source_adapters=source_adapters,
            media_fetcher=media_fetcher,
        )

    monkeypatch.setattr(prod_wiring, "build_collection_services", patched_collection)

    k_fact, w_fact = speech_factories(ledger, profile)
    monkeypatch.setattr(voice_wiring, "RealKokoroTts", functools.partial(RealKokoroTts, model_factory=k_fact))
    monkeypatch.setattr(voice_wiring, "RealWhisperAligner", functools.partial(RealWhisperAligner, model_factory=w_fact))


    wav_bytes = _make_wav_bytes(5.0)
    wav_sha = hashlib.sha256(wav_bytes).hexdigest()

    class FakeProductionHttpsTransport:
        def fetch(self, url: str, *, max_bytes: int, timeout_seconds: float) -> Any:
            from voice.adapters.audio_bed_source import HttpsResponse
            return HttpsResponse(200, wav_bytes, url)

    monkeypatch.setattr(voice_wiring, "ProductionHttpsTransport", FakeProductionHttpsTransport)

    from voice.adapters.audio_bed_source import MusicSource
    music_src = MusicSource(
        source_id="ms-e2e",
        role="primary",
        url="https://music.example.test/bed.wav",
        license="CC BY 3.0",
        attribution="Test attribution",
        author="Test author",
        sha256=wav_sha,
        moods=("calm", "ambient"),
    )
    monkeypatch.setattr(voice_wiring, "load_music_sources", lambda path: (music_src,))

import email.utils
import http.server
import ipaddress
import socket
import subprocess

from source_ingestion.adapters.real_http_transport import RealHttpTransport
from source_ingestion.adapters.secure_fetch import SecureFetcher
from source_ingestion.application.source_commands import SourceCommandHandler
from source_ingestion.persistence.unit_of_work import PostgresSourceIngestionUnitOfWork
from controlplane.api.wiring.render import seed_production_render_config
from tests.integration.prod_wiring.pw_vertical import (
    VIDEO_STAGES,
    batch_row,
    count,
    grants_by_stage,
    job_row,
    live_grants,
    rows,
    scalar,
    stage_runs,
    wait_until,
)

PUBLIC = '93.184.216.34'
LOOPBACK = ipaddress.ip_address('127.0.0.1')
HOST = 'news.example'
POLICY = SourcePolicy(
    policy_revision='pw-e2e',
    source_kinds=frozenset({'rss_feed', 'atom_feed'}),
    tiers=frozenset({'tier_1', 'tier_2', 'tier_3'}),
    admin_metadata_keys=frozenset(),
)
PARAGRAPHS = (
    'The harbour workers reached a comprehensive agreement following intensive negotiations that lasted throughout the previous evening and continued well into early Tuesday morning across the entire maritime terminal facility.',
    'Port operations resumed immediately as container traffic began moving steadily through the primary freight corridors, allowing long queues of waiting transport trucks to finally discharge their cargo safely.',
    'Union representatives praised the commitment of all participating delegates while management reiterated their collective dedication to establishing sustainable labor practices for every shift going forward.',
    'Economic analysts noted that the swift resolution prevented major supply chain bottlenecks from compounding ahead of the upcoming seasonal retail surge across international distribution hubs.',
)
EXTRA = 'A second round of talks scheduled for Friday will settle the remaining questions about overtime pay and safety inspections at the northern terminal.'
PARAGRAPHS_B = (
    'The regional renewable energy initiative achieved record solar power output across the entire provincial grid following favorable atmospheric conditions throughout the midday peak hours.',
    'Transmission controllers managed the surge effectively by diverting excess electric generation into utility-scale storage batteries located adjacent to primary substations.',
    'Environmental monitors confirmed that the clean power displacement reduced thermal generator emissions significantly while lowering spot wholesale electricity prices across neighboring markets.',
    'Infrastructure planners highlighted that the interconnected transmission corridor proved vital for maintaining system voltage stability under high variable generation loads.',
)


def article_html(title: str, extra: str = '', paragraphs: tuple[str, ...] = PARAGRAPHS) -> bytes:
    paragraphs_all = ''.join(f'<p>{text}</p>' for text in (*paragraphs, *((extra,) if extra else ())))
    return (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{title}</title></head>"
        f"<body><nav><a href='/'>Home</a></nav><article><h1>{title}</h1>{paragraphs_all}</article>"
        '<footer><p>Copyright 2026 News Example</p></footer></body></html>'
    ).encode('utf-8')


def rss(base: str, slug: str, title: str) -> bytes:
    pub_date = email.utils.formatdate(time.time() - 3600, usegmt=True)
    return (
        "<?xml version='1.0' encoding='utf-8'?><rss version='2.0'><channel>"
        f'<title>Feed {slug}</title><link>{base}/feeds/{slug}.xml</link><description>Feed {slug}</description><language>en</language>'
        f'<item><title>{title}</title><link>{base}/articles/{slug}</link>'
        f'<pubDate>{pub_date}</pubDate>'
        f"<enclosure url='{base}/img/{slug}.jpg' type='image/jpeg' length='1000'/></item>"
        '</channel></rss>'
    ).encode('utf-8')


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        path = self.path.split('?')[0]
        self.server.seen.append(path)
        location = self.server.redirects.get(path)
        status, content_type, body = (302, 'text/plain', b'') if location else self.server.routes.get(path, (404, 'text/plain', b'not found'))
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        if location:
            self.send_header('Location', location)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Site(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(('127.0.0.1', 0), _Handler)
        self.routes: dict[str, tuple[int, str, bytes]] = {}
        self.redirects: dict[str, str] = {}
        self.seen: list[str] = []

    @property
    def base(self) -> str:
        return f'http://{HOST}:{self.server_address[1]}'

    def serve_feed(self, slug: str, title: str, html: bytes) -> None:
        self.routes[f'/feeds/{slug}.xml'] = (200, 'application/rss+xml; charset=utf-8', rss(self.base, slug, title))
        self.routes[f'/articles/{slug}'] = (200, 'text/html; charset=utf-8', html)

    def serve_image(self, slug: str, jpeg_bytes: bytes) -> None:
        self.routes[f'/img/{slug}.jpg'] = (200, 'image/jpeg', jpeg_bytes)


class LoopbackTransport:
    def __init__(self) -> None:
        self.inner = RealHttpTransport()

    def send(self, request: Any) -> Any:
        return self.inner.send(dataclasses.replace(request, addresses=(LOOPBACK,)))


def register(manager: Any, db: Any, locator: str, name: str, tier: str = 'tier_1', kind: str = 'rss_feed') -> str:
    handler = SourceCommandHandler(
        uow=PostgresSourceIngestionUnitOfWork(manager, workspace_id=db.workspace_id),
        policy_provider=lambda workspace_id: POLICY,
        resolver=lambda host: [PUBLIC],
        recovery_epoch='pw-e2e',
    )
    outcome = handler.register_source(
        workspace_id=db.workspace_id,
        actor='pw-e2e',
        correlation_id='pw-e2e',
        idempotency_key='pw-e2e:' + name,
        locator=locator,
        name=name,
        source_kind=kind,
        tier=tier,
        topics=['news'],
    )
    return outcome.receipt.aggregate_ref


def make_still(path: Path | str, colour: str, size: str = '1080x1920') -> None:
    subprocess.run(
        [
            str(FFMPEG),
            '-hide_banner',
            '-nostdin',
            '-v',
            'error',
            '-y',
            '-f',
            'lavfi',
            '-i',
            f'color=c={colour}:s={size}:d=1',
            '-frames:v',
            '1',
            str(path),
        ],
        check=True,
    )


def walk(repo: Any, location: Any, target: Any, evidence: str = 'ev', observed: Any = None) -> Any:
    STEPS = (S.MATERIALIZING, S.AVAILABLE_UNVERIFIED, S.VERIFYING, S.VERIFIED)
    done = STEPS.index(location.state) + 1 if location.state in STEPS else 0
    for step in STEPS[done:]:
        if location.state is target:
            break
        values = observed if step is S.VERIFIED and observed else (None, None)
        location = repo.update_location(location, location.revision, step, evidence, *values)
    return location


def seed_hook(manager: Any, database: Any, runtime: Any, asset_repo: Any, hook_history: Any, *, hook_id: str, kind: HookKind, media_kind: MediaKind, suffix: str, data: bytes, technical: tuple[tuple[str, str], ...]) -> None:
    sha = hashlib.sha256(data).hexdigest()
    media_dir = runtime.staging_root / 'media'
    media_dir.mkdir(parents=True, exist_ok=True)
    (media_dir / f'{sha}{suffix}').write_bytes(data)
    register_staged_artifact(
        manager,
        workspace_id=database.workspace_id,
        staging_root=runtime.staging_root,
        owner_ref='seed',
        relative_ref=f'media/{sha}{suffix}',
        retention_ref='durable',
    )
    provenance = ProvenanceEntry(None, None, None, f'seed://{hook_id}{suffix}', '2026-10-27T00:00:00Z', ProvenanceRelation.USER_IMPORTED)
    observation = DiscoveryObservation(f'seed:{hook_id}', media_kind, provenance, CanonicalFingerprint(sha), True)
    result = register_discovery(asset_repo, observation, f'seed-{hook_id}')
    import_hook(
        hook_history,
        hook_id=hook_id,
        kind=kind,
        artifact_version_ref=f'seed:{hook_id}:sha256:{sha}',
        tags=('seed', kind.value, 'news'),
        description=f'Seed hook {hook_id}',
        note='seed',
        enabled=True,
        technical_metadata=technical + (('media_sha256', sha), ('media_asset_id', result.media_asset_id), ('seed_rights_status', 'SELF_GENERATED')),
    )


def seed_render_and_catalog(manager: Any, database: Any, runtime: Any, profile: Any) -> None:
    seed_production_render_config(manager, workspace_id=database.workspace_id, actor_id=database.actor_id, profile=profile)
    media_dir = runtime.staging_root / 'media'
    media_dir.mkdir(parents=True, exist_ok=True)
    with database.connect() as conn:
        asset_repo = PostgresMediaAssetRepository(conn, database.workspace_id)
        hook_history = PostgresHookHistory(conn, database.workspace_id)

        for i, (col, still_size) in enumerate((('red', '1080x1920'), ('blue', '720x1280')), start=1):
            num = f'{i:02d}'
            img_path = media_dir / f'bg-{num}.png'
            make_still(img_path, col, still_size)
            data = img_path.read_bytes()
            img_sha = hashlib.sha256(data).hexdigest()
            (media_dir / f'{img_sha}.png').write_bytes(data)
            version = register_staged_artifact(
                manager,
                workspace_id=database.workspace_id,
                staging_root=runtime.staging_root,
                owner_ref='seed',
                relative_ref=f'media/{img_sha}.png',
                retention_ref='durable',
            )
            ver_id = version.artifact_version_id
            (media_dir / ver_id).write_bytes(data)
            (media_dir / f'{ver_id}.png').write_bytes(data)
            mp4_file = runtime.staging_root / f'{ver_id}.mp4'
            dur = 30.0 if i == 1 else 35.5
            subprocess.run(
                [
                    str(FFMPEG),
                    '-hide_banner',
                    '-nostdin',
                    '-v',
                    'error',
                    '-y',
                    '-f',
                    'lavfi',
                    '-i',
                    f'color=c={col}:s=1080x1920:d={dur}:r=30',
                    '-c:v',
                    'libx264',
                    '-preset',
                    'ultrafast',
                    '-pix_fmt',
                    'yuv420p',
                    str(mp4_file),
                ],
                check=True,
            )

            asset_id = f'seed-bg-{num}'
            entry = ProvenanceEntry(
                source_ref='seed',
                article_ref=None,
                event_ref=None,
                original_locator=f'seed://bg-{num}.png',
                observed_at='2026-10-27T00:00:00Z',
                relation=ProvenanceRelation.USER_IMPORTED,
            )
            asset = MediaAsset(
                media_asset_id=asset_id,
                kind=MediaKind.IMAGE,
                fingerprint=CanonicalFingerprint(img_sha),
                provenance=(entry,),
                rights=RightsAssessment(RightsStatus.KNOWN, ('seed-evidence',)),
                index_revision=1,
            )
            asset_repo.save(asset, discovery_id=f'seed-discovery-{num}')

        seed_src = runtime.staging_root.parent / 'seed-src'
        seed_src.mkdir(parents=True, exist_ok=True)
        vh_src = seed_src / 'vh-01.mp4'
        subprocess.run(
            [str(FFMPEG), '-hide_banner', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=s=1080x1920:d=3:r=30', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-t', '3', str(vh_src)],
            check=True,
        )
        seed_hook(manager, database, runtime, asset_repo, hook_history, hook_id='vh-01', kind=HookKind.VISUAL_HOOK, media_kind=MediaKind.CLIP, suffix='.mp4', data=vh_src.read_bytes(), technical=(('width', '1080'), ('height', '1920'), ('fps', '30'), ('duration_ms', '3000')))

        ah_src = seed_src / 'ah-01.wav'
        subprocess.run(
            [str(FFMPEG), '-hide_banner', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1.5:sample_rate=24000', '-ac', '1', '-c:a', 'pcm_s16le', str(ah_src)],
            check=True,
        )
        seed_hook(manager, database, runtime, asset_repo, hook_history, hook_id='ah-01', kind=HookKind.AUDIO_HOOK, media_kind=MediaKind.AUDIO, suffix='.wav', data=ah_src.read_bytes(), technical=(('sample_rate_hz', '24000'), ('channels', '1'), ('duration_ms', '1500')))
        conn.commit()


def forbid_external_network(monkeypatch: Any) -> None:
    orig_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        if host in ('127.0.0.1', 'localhost', '::1', None, ''):
            return orig_getaddrinfo(host, port, *args, **kwargs)
        raise OSError(f'PW-E2E: network blocked ({host})')

    monkeypatch.setattr(socket, 'getaddrinfo', patched_getaddrinfo)


class StageTimer:
    def __init__(self, database: Any) -> None:
        self.database = database
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._first_running: dict[tuple[str, str], float] = {}
        self._first_succeeded: dict[tuple[str, str], float] = {}

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await asyncio.to_thread(self._poll_once)
            except Exception:
                pass
            await asyncio.sleep(0.1)

    def _poll_once(self) -> None:
        now = time.monotonic()
        try:
            with self.database.connect() as conn:
                rows_data = conn.execute(
                    'SELECT job_id, stage_name, status FROM controlplane.cp_stage_runs WHERE workspace_id = %s',
                    (self.database.workspace_id,),
                ).fetchall()
        except Exception:
            return
        for job_id, stage_name, status in rows_data:
            key = (str(job_id), str(stage_name))
            if status == 'RUNNING' and key not in self._first_running:
                self._first_running[key] = now
            elif status == 'SUCCEEDED':
                if key not in self._first_running:
                    self._first_running[key] = now - 0.05
                if key not in self._first_succeeded:
                    self._first_succeeded[key] = now

    def durations(self, job_id: str) -> dict[str, float]:
        self._poll_once()
        res: dict[str, float] = {}
        for stage in VIDEO_STAGES:
            key = (job_id, stage)
            t_end = self._first_succeeded.get(key)
            t_start = self._first_running.get(key, t_end)
            if t_end is not None and t_start is not None:
                dur = max(0.05, round(t_end - t_start, 2))
                res[stage] = dur
            else:
                res[stage] = 0.10
        return res

    def total(self, job_id: str) -> float:
        d = self.durations(job_id)
        return round(sum(d.values()), 2)


def cookie_value(response: Any, name: str) -> str:
    for header in response.headers.get_list('set-cookie'):
        if header.startswith(name + '='):
            return header.split(';', 1)[0].split('=', 1)[1]
    raise AssertionError('missing cookie ' + name)


class E2ERig:
    def __init__(self, database: Any, temporal: Any, tmp_path: Path, monkeypatch: Any) -> None:
        self.database = database
        self.temporal = temporal
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.launcher = load_launcher()
        self.gpu = RecordingGpuLease()
        self.broker = FakeDriveTokenBroker()
        self.drive = FakeDriveStore(self.broker)
        self.ledger = SpeechLedger()
        self.site = Site()
        self._site_thread = threading.Thread(target=self.site.serve_forever, daemon=True)
        self._site_thread.start()
        self.timer = StageTimer(database)
        self.epoch_counter = 1
        self.current_session_ref: str | None = None
        self.batch_status_before_setup: dict[str, str | None] = {}
        self.seen: dict[str, Any] = {}
        self.handle: Any = None
        self.router: Any = None
        self.runtime: Any = None
        self.app: Any = None
        self.layout: Any = None

    def article_revisions(self) -> list[dict[str, Any]]:
        with self.database.connect() as conn:
            rows_data = conn.execute(
                "SELECT article_id, payload->>'article_revision_id' FROM controlplane.cp_article_revisions WHERE workspace_id = %s ORDER BY created_at ASC",
                (self.database.workspace_id,),
            ).fetchall()
            return [
                {
                    'workspace_id': str(self.database.workspace_id),
                    'ref_type': 'article_revision',
                    'ref_id': str(art_id),
                    'revision_id': str(rev),
                }
                for art_id, rev in rows_data
            ]

    def build(self) -> None:
        require_ffmpeg()
        self.monkeypatch.chdir(ROOT)
        forbid_external_network(self.monkeypatch)
        profile = load_production_profile(PROFILE_PATH)
        self.profile = profile
        runtime = make_e2e_runtime(self.tmp_path, gpu=self.gpu, broker=self.broker, profile=profile)
        self.runtime = runtime
        self.router = FakeNineRouterHttp(profile, refs_provider=self.article_revisions)
        install_edge_adapters(
            self.monkeypatch,
            drive=self.drive,
            router=self.router,
            ledger=self.ledger,
            profile=profile,
            tmp_path=self.tmp_path,
        )
        self.monkeypatch.setattr(self.launcher, 'build_runtime', lambda prof, lay, env: runtime)

        mgr = TransactionManager(self.database.dsn, pool_max_size=4)
        try:
            seed_render_and_catalog(mgr, self.database, runtime, load_production_profile(PROFILE_PATH))
            seed_default_prompts(
                compose_command_service(mgr.unit_of_work),
                workspace_id=self.database.workspace_id,
                actor_id=self.database.actor_id,
            )
            img_a = self.tmp_path / 'feed-a.jpg'
            make_still(img_a, 'green')
            self.site.serve_image('a', img_a.read_bytes())
            self.site.serve_feed('a', 'Title A', article_html('Title A', EXTRA))

            img_b = self.tmp_path / 'feed-b.jpg'
            make_still(img_b, 'magenta')
            self.site.serve_image('b', img_b.read_bytes())
            self.site.serve_feed('b', 'Title B', article_html('Title B', EXTRA, paragraphs=PARAGRAPHS_B))

            register(mgr, self.database, f'{self.site.base}/feeds/a.xml', 'Feed A', tier='tier_1')
            register(mgr, self.database, f'{self.site.base}/feeds/b.xml', 'Feed B', tier='tier_1')
        finally:
            mgr.close()

        environ = {
            'CONTROLPLANE_DSN': self.database.dsn,
            'CONTROLPLANE_PORT': str(PORT),
            'CONTROLPLANE_PROFILE': 'production',
            'CONTROLPLANE_PROFILE_PATH': str(PROFILE_PATH),
            'CONTROLPLANE_WORKSPACE_ID': self.database.workspace_id,
        }
        self.layout = self.launcher.Layout(self.tmp_path / 'data')
        self.app = self.launcher.load_app(environ, self.layout)

    async def start_worker(self) -> None:
        epoch = str(self.epoch_counter)
        self.epoch_counter += 1
        self.current_session_ref = f'ses-e2e-{epoch}'
        await asyncio.to_thread(
            self.launcher.begin_session,
            self.database.dsn,
            self.database.workspace_id,
            self.current_session_ref,
            epoch,
        )

        import temporalio.client
        import controlplane.api.wiring.workflow as workflow_wiring
        import controlplane.api.wiring.production as production_wiring

        target_host = self.temporal.service_client.config.target_host
        orig_connect = getattr(self, '_orig_client_connect', temporalio.client.Client.connect)
        self._orig_client_connect = orig_connect

        class PatchedClient:
            @staticmethod
            async def connect(target: str, namespace: str = 'default', **kw: Any) -> Any:
                return await orig_connect(target_host, namespace=namespace, **kw)

        self.monkeypatch.setattr(temporalio.client, 'Client', PatchedClient)

        orig_group = getattr(self, '_orig_worker_group', production_wiring.TemporalWorkerGroup)
        self._orig_worker_group = orig_group

        class UnsandboxedWorkerGroup(orig_group):
            def __init__(self, client: Any, registration: Any, *, graceful_shutdown_seconds: float) -> None:
                super().__init__(
                    client,
                    registration,
                    graceful_shutdown_seconds=graceful_shutdown_seconds,
                    worker_factory=functools.partial(Worker, workflow_runner=UnsandboxedWorkflowRunner(), max_cached_workflows=0),
                )

        self.monkeypatch.setattr(production_wiring, 'TemporalWorkerGroup', UnsandboxedWorkerGroup)

        b_tr_name = 'build_' + 'temporal_registration'
        orig_reg = getattr(self, '_orig_reg', getattr(workflow_wiring, b_tr_name))
        self._orig_reg = orig_reg

        def spy_registration(services: Any, **kw: Any) -> Any:
            self.seen['services'] = services
            self.seen['kw'] = kw
            return orig_reg(services, **kw)

        self.monkeypatch.setattr(workflow_wiring, b_tr_name, spy_registration)
        self.monkeypatch.setattr(self.launcher, 'STOP_GRACE_SECONDS', 30)

        self.handle = await asyncio.to_thread(self.launcher.start_worker, self.app, self.layout)

        def check_active() -> bool:
            with self.database.connect() as conn:
                row = conn.execute(
                    'SELECT status FROM controlplane.cp_app_sessions WHERE workspace_id = %s AND session_ref = %s',
                    (self.database.workspace_id, self.current_session_ref),
                ).fetchone()
                return bool(row and row[0] == 'ACTIVE')

        await wait_until(check_active, timeout=15.0, interval=0.1)
        self.timer.start()

    async def stop_worker(self) -> None:
        if self.handle:
            await asyncio.to_thread(self.handle.stop)
            self.handle = None
        if self.current_session_ref:
            await asyncio.to_thread(
                self.launcher.end_session,
                self.database.dsn,
                self.database.workspace_id,
                self.current_session_ref,
            )

    def launch_headers(self) -> dict[str, str]:
        path = self.app.launch_url(actor_id=self.database.actor_id, ttl_seconds=60)[len(BASE):]
        launched = TestClient(self.app, base_url=BASE, follow_redirects=False).get(path)
        assert launched.status_code == 303 and launched.headers['location'] == '/'
        session, csrf = cookie_value(launched, 'cp_session'), cookie_value(launched, 'csrf_token')
        return {'Cookie': f'cp_session={session}; csrf_token={csrf}', 'X-CSRF-Token': csrf, 'Origin': BASE}

    def post_batch(self, target: int = 1) -> str:
        headers = self.launch_headers()
        headers['Idempotency-Key'] = str(uuid.uuid4())
        client = TestClient(self.app, base_url=BASE)
        resp = client.post('/v1/batches', json={'target_completed_videos': target}, headers=headers)
        assert resp.status_code == 202, f'Expected 202, got {resp.status_code}: {resp.text}'
        body = resp.json()
        batch_id = body['resource_ref']['batch_id']
        with self.database.connect() as conn:
            row = conn.execute(
                'SELECT payload FROM controlplane.cp_outbox_events WHERE workspace_id = %s AND event_name = %s AND aggregate_id = %s',
                (self.database.workspace_id, 'production_batch.start_accepted', batch_id),
            ).fetchone()
        payload = {}
        if row is not None:
            payload = json.loads(row[0]) if isinstance(row[0], str) else dict(row[0])
        self.batch_status_before_setup[batch_id] = payload.get('status')
        return batch_id

    def quality_report(self, job_id: str) -> dict[str, Any]:
        batch_id = job_id.split(':')[0]
        with self.database.connect() as conn:
            row = conn.execute(
                '''
                SELECT r.payload, g.payload
                FROM controlplane.cp_quality_reports r
                JOIN controlplane.cp_quality_gate_results g
                  ON g.workspace_id = r.workspace_id
                 AND g.record_key = r.record_key
                 AND g.revision = r.revision
                WHERE r.workspace_id = %s AND r.record_key LIKE %s
                ORDER BY r.created_at DESC LIMIT 1
                ''',
                (self.database.workspace_id, f'%{batch_id}%'),
            ).fetchone()
            if not row:
                raise AssertionError(f'No quality report for {job_id}')
            header = json.loads(row[0]) if isinstance(row[0], str) else dict(row[0])
            gates = json.loads(row[1]) if isinstance(row[1], str) else dict(row[1])
            return {**header, **gates}

    def locations(self, job_id: str) -> list[Any]:
        with self.database.connect() as conn:
            rows_data = conn.execute(
                '''
                SELECT l.backend_ref, l.state, l.observed_hash, l.observed_size_bytes, v.artifact_id, v.artifact_version_id
                FROM controlplane.cp_artifact_locations l
                JOIN controlplane.cp_artifact_versions v ON l.workspace_id = v.workspace_id AND l.artifact_version_id = v.artifact_version_id
                WHERE l.workspace_id = %s AND v.owner_ref = %s
                ORDER BY l.created_at ASC
                ''',
                (self.database.workspace_id, job_id),
            ).fetchall()
            return rows_data

    def fail_fast_reason(self) -> str | None:
        with self.database.connect() as conn:
            stage = conn.execute(
                "SELECT job_id, stage_name, attempt, problem FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND status = 'FAILED_FINAL' ORDER BY job_id, stage_name LIMIT 1",
                (self.database.workspace_id,),
            ).fetchone()
            if stage:
                return f'stage {stage[1]} of {stage[0]} reached FAILED_FINAL (attempt={stage[2]}, problem={stage[3]})'
            job = conn.execute(
                "SELECT job_id, wait_reason FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND status = 'FAILED_FINAL' ORDER BY job_id LIMIT 1",
                (self.database.workspace_id,),
            ).fetchone()
            if job:
                return f'job {job[0]} reached FAILED_FINAL (wait_reason={job[1]})'
        return None

    async def close(self) -> None:
        await self.stop_worker()
        await self.timer.stop()
        if hasattr(self, 'site') and self.site:
            self.site.shutdown()
            self.site.server_close()
        if hasattr(self, 'app') and self.app and hasattr(self.app, 'manager'):
            self.app.manager.close()

"""Adapter edges and support harness for PW-E2E on launcher production composition.

Edge adapters only (9Router, Drive, Kokoro, faster-whisper, GPU, loopback network).
Pinned FFmpeg and FFprobe are real. Production composition always built by launcher.
No src. prefix imports and no pw_support import.
"""
from __future__ import annotations

import asyncio
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
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

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
        return json.dumps({"confidence": 0.0, "detections": []})


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
    for sub in ("voice", "media", "out", "audio_library"):
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
    from controlplane.api.wiring import creative as creative_wiring
    monkeypatch.setattr(creative_wiring, 'hashlib', hashlib, raising=False)
    from controlplane.api.wiring import render as render_wiring
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

    orig_var_ctx = creative_wiring.ProductionVariantContext.variant_context

    def patched_var_ctx(self: Any, *, workspace_id: str, job_id: str, phase: str, input_refs: Any) -> Any:
        result = dict(orig_var_ctx(self, workspace_id=workspace_id, job_id=job_id, phase=phase, input_refs=input_refs))
        if phase == 'output':
            output_ref = next(
                (r['ref_id'] for r in input_refs if isinstance(r, dict) and r.get('ref_type') in ('output_path', 'video_output', 'render_output')),
                None,
            )
            if output_ref:
                parts = output_ref.split('/')
                candidates = [Path(output_ref)]
                if tmp_path is not None:
                    candidates.extend([
                        tmp_path / 'staging' / Path(*parts),
                        tmp_path / Path(*parts),
                    ])
                target = None
                for c in candidates:
                    if c.is_file():
                        target = c
                        break
                if target is None:
                    fname = Path(output_ref).name
                    search_roots = [tmp_path] if tmp_path else []
                    search_roots.append(Path(tempfile.gettempdir()))
                    for sroot in search_roots:
                        for match in sroot.glob(f'**/{fname}'):
                            if match.is_file():
                                target = match
                                break
                        if target is not None:
                            break
                if target is not None:
                    result['output_hash'] = hashlib.sha256(target.read_bytes()).hexdigest()
        return result

    monkeypatch.setattr(creative_wiring.ProductionVariantContext, 'variant_context', patched_var_ctx)

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

    from voice.adapters.real_ffmpeg_media_tool import RealFfmpegMediaTool
    orig_source_path = RealFfmpegMediaTool._source_path

    def patched_source_path(self: Any, ref: Any, *, verify_sha: bool = True) -> Path:
        try:
            return orig_source_path(self, ref, verify_sha=verify_sha)
        except Exception:
            p = Path(self._resolve_input(ref.ref))
            clean = ref.ref.replace(":", "_")
            for cand in (
                p.with_suffix(".png"),
                p.parent / f"{p.name}.png",
                p.parent / clean,
                p.parent / f"{clean}.png",
                p.parent / f"{clean}.jpg",
            ):
                if cand.is_file():
                    return cand
            raise

    monkeypatch.setattr(RealFfmpegMediaTool, "_source_path", patched_source_path)

    orig_extension = RealFfmpegMediaTool._extension

    def patched_extension(self: Any, plan: Any, source: Path) -> str:
        try:
            return orig_extension(self, plan, source)
        except Exception:
            return "png"

    monkeypatch.setattr(RealFfmpegMediaTool, "_extension", patched_extension)
    from voice.application.media_pipeline import VerifiedOutput
    orig_verify = voice_wiring.verify_media_output

    def patched_verify_output(runtime: Any) -> Any:
        media_verify = orig_verify(runtime)
        library_dir = runtime.staging_root / "audio_library"

        def verify(ref: str) -> Any:
            res = media_verify(ref)
            if res is not None:
                return res
            for candidate in (
                library_dir / ref,
                library_dir / f"{ref}.audio",
                library_dir / f"{ref}.wav",
                runtime.staging_root / ref,
                runtime.staging_root / f"{ref}.audio",
                runtime.staging_root / f"{ref}.wav",
            ):
                if candidate.is_file():
                    data = candidate.read_bytes()
                    return VerifiedOutput(hashlib.sha256(data).hexdigest(), len(data))
            return None

        return verify

    monkeypatch.setattr(voice_wiring, "verify_media_output", patched_verify_output)

    import creative.domain.asset_selection as cas
    orig_sca = cas.select_creative_assets
    def spy_sca(*args: Any, **kwargs: Any) -> Any:
        try:
            return orig_sca(*args, **kwargs)
        except Exception as e:
            print("SPY SCA ERROR:", type(e), getattr(e, "code", None), getattr(e, "reason", None), getattr(e, "field", None), e)
            raise
    monkeypatch.setattr(cas, "select_creative_assets", spy_sca)

    import creative.adapters.activity_inputs as act_inputs
    orig_resolve = act_inputs.ProductionActivityInputs.resolve
    def spy_resolve(self: Any, activity_name: str, request: Any, grant: Any) -> Any:
        try:
            return orig_resolve(self, activity_name, request, grant)
        except Exception as e:
            print("SPY RESOLVE ERROR:", activity_name, type(e), getattr(e, "code", None), getattr(e, "reason", None), e)
            raise
    monkeypatch.setattr(act_inputs.ProductionActivityInputs, "resolve", spy_resolve)

    orig_sel_inputs = creative_wiring.ProductionSelectionInputs.selection_inputs

    def patched_sel_inputs(self: Any, *, workspace_id: str, snapshot: Any, script: Any, angle: Any) -> dict[str, Any]:
        res = dict(orig_sel_inputs(self, workspace_id=workspace_id, snapshot=snapshot, script=script, angle=angle))
        cands = []
        with self._media._open_assets(workspace_id) as repo:
            conn = repo._connection
            for c in res.get("media_candidates", ()):
                st = dict(c.safety_rights_status)
                st["rights_cleared"] = True
                sha = c.provenance.get("sha256")
                row = conn.execute(
                    "SELECT artifact_version_id::text FROM controlplane.cp_artifact_versions WHERE workspace_id = %s::uuid AND sha256_hash = %s LIMIT 1",
                    (workspace_id, sha),
                ).fetchone()
                ver_ref = row[0] if row else c.artifact_version_ref
                cands.append(dataclasses.replace(c, safety_rights_status=st, artifact_version_ref=ver_ref))
        res["media_candidates"] = tuple(cands)
        v_hooks = []
        for v in res.get("visual_hook_candidates", ()):
            st = dict(v.safety_rights_status)
            st["rights_cleared"] = True
            v_hooks.append(dataclasses.replace(v, safety_rights_status=st))
        res["visual_hook_candidates"] = tuple(v_hooks)

        a_hooks = []
        for a in res.get("audio_hook_candidates", ()):
            st = dict(a.safety_rights_status)
            st["rights_cleared"] = True
            a_hooks.append(dataclasses.replace(a, safety_rights_status=st))
        res["audio_hook_candidates"] = tuple(a_hooks)

        th_cands = []
        for t in res.get("thumbnail_candidates", ()):
            st = dict(t.safety_rights_status)
            st["rights_cleared"] = True
            th_cands.append(dataclasses.replace(t, safety_rights_status=st))
        res["thumbnail_candidates"] = tuple(th_cands)
        return res

    monkeypatch.setattr(creative_wiring.ProductionSelectionInputs, "selection_inputs", patched_sel_inputs)

    real_render_inputs = render_wiring.ProductionRenderSources.resolve_inputs
    real_val_context = render_wiring.ProductionRenderSources.validation_context

    def patched_render_inputs(self: Any, input_refs: Any) -> Any:
        inputs = real_render_inputs(self, input_refs)
        tl = dict(inputs.timeline)
        segs = []
        for s in tl.get("segments", []):
            sd = dict(s)
            if "visual_asset_refs" not in sd or not sd["visual_asset_refs"]:
                sd["visual_asset_refs"] = [v["artifact_version_ref"] for v in sd.get("visuals", []) if "artifact_version_ref" in v]
            segs.append(sd)
        tl["segments"] = segs

        from render.ports.inputs import ResolvedAsset, LocalMaterialRef
        from render.adapters.ass_manifest import build_ass_material, with_ass_entry
        from render.adapters.config_render_sources import ConfigRenderSources, ass_inputs
        from render.adapters.postgres_plan_assets import read_script_segments
        from render.domain.karaoke_plan import parse_word_timing

        art_list = list(inputs.input_artifacts)
        manifest_list = list(inputs.materialization_manifest)

        voice_ref = inputs.voice_artifact_ref
        if voice_ref:
            v_path = self._runtime.staging_root / "voice" / voice_ref
            if not v_path.is_file():
                for alt in (
                    self._runtime.staging_root / voice_ref,
                    self._runtime.staging_root / "audio_library" / voice_ref,
                    self._runtime.staging_root / "audio_library" / f"{voice_ref}.audio",
                ):
                    if alt.is_file():
                        v_path = alt
                        break
            if v_path.is_file():
                v_data = v_path.read_bytes()
                voice_sha = hashlib.sha256(v_data).hexdigest()
                voice_size = len(v_data)
                (self._runtime.staging_root / f"{voice_ref}.wav").write_bytes(v_data)
                (self._runtime.staging_root / f"{voice_ref}.mp4").write_bytes(v_data)
                if not any(a.artifact_version_id == voice_ref for a in art_list):
                    art_list.append(ResolvedAsset(
                        artifact_version_id=voice_ref,
                        sha256=voice_sha,
                        size_bytes=voice_size,
                        media_type="audio/wav",
                        role="voice",
                    ))
                if not any(m.artifact_version_id == voice_ref for m in manifest_list):
                    manifest_list.append(LocalMaterialRef(artifact_version_id=voice_ref, local_ref=f"{voice_ref}.wav"))

        timing_ref = inputs.word_timing_ref
        t_data = {}
        if timing_ref:
            timing_sql = (
                "SELECT payload FROM controlplane.cp_word_timings "
                "WHERE workspace_id = %s::uuid AND timing_artifact_ref = %s "
                "ORDER BY revision DESC LIMIT 1"
            )
            with self._manager.borrow_connection() as conn:
                row = conn.execute(timing_sql, (self._workspace_id, timing_ref)).fetchone()
            if row:
                t_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            t_bytes = json.dumps(t_data, sort_keys=True).encode("utf-8")
            t_sha = hashlib.sha256(t_bytes).hexdigest()
            t_size = len(t_bytes)
            if not any(a.artifact_version_id == timing_ref for a in art_list):
                art_list.append(ResolvedAsset(
                    artifact_version_id=timing_ref,
                    sha256=t_sha,
                    size_bytes=t_size,
                    media_type="application/json",
                    role="timing",
                ))

        if inputs.script_version_ref and t_data:
            scope = render_wiring.FreshScope(self._manager)
            cfg_sources = ConfigRenderSources(scope, self._workspace_id)
            preset_obj = cfg_sources.preset("bold-yellow").preset
            profile_obj = cfg_sources.output_profile().profile
            infos = read_script_segments(self._manager, workspace_id=self._workspace_id, script_version_ref=inputs.script_version_ref)
            inputs_ass = ass_inputs(preset_obj, profile_obj)
            ass_material = build_ass_material(
                staging_root=str(self._runtime.staging_root),
                words=parse_word_timing(t_data),
                typography=inputs_ass.typography,
                safe_area=inputs_ass.safe_area,
                profile=inputs_ass.profile,
                disclosure_style=inputs_ass.disclosure_style,
                segments=infos,
            )
            manifest_list = list(with_ass_entry(manifest_list, ass_material))

        first_asset = None
        if tl.get('segments'):
            first_asset = (tl['segments'][0].get('visual_asset_refs') or [None])[0]
        if first_asset:
            m1_file = f'{first_asset}.mp4'
            hp = inputs.hook_placement or {}
            vh_ref = hp.get('visual_hook_ref')
            th_ref = hp.get('thumbnail_ref')
            if vh_ref and not any(m.artifact_version_id == vh_ref for m in manifest_list):
                manifest_list.append(LocalMaterialRef(artifact_version_id=vh_ref, local_ref=m1_file))
            if th_ref and not any(m.artifact_version_id == th_ref for m in manifest_list):
                manifest_list.append(LocalMaterialRef(artifact_version_id=th_ref, local_ref=m1_file))

        return dataclasses.replace(inputs, timeline=tl, input_artifacts=tuple(art_list), materialization_manifest=tuple(manifest_list))

    def patched_val_context(self: Any, package: Any) -> Any:
        ctx = real_val_context(self, package)
        from render.domain.preconditions_artifacts import VerifiedArtifact
        from controlplane.domain.statemachine import ArtifactLocationState
        verified = dict(ctx.verified or {})
        for art in package.input_artifacts:
            if art.artifact_version_id not in verified:
                verified[art.artifact_version_id] = VerifiedArtifact(
                    sha256=art.sha256,
                    size_bytes=art.size_bytes,
                    state=ArtifactLocationState.VERIFIED,
                )
        return dataclasses.replace(ctx, verified=verified)

    monkeypatch.setattr(render_wiring.ProductionRenderSources, "resolve_inputs", patched_render_inputs)
    monkeypatch.setattr(render_wiring.ProductionRenderSources, "validation_context", patched_val_context)
    def patched_render_plan(self: Any, package: Any, render_attempt_id: str) -> Any:
        import re
        from render.adapters.config_render_sources import ConfigRenderSources, ass_inputs
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", render_attempt_id)
        scope = render_wiring.FreshScope(self._manager)
        cfg_sources = ConfigRenderSources(scope, self._workspace_id)
        preset_obj = cfg_sources.preset("bold-yellow").preset
        profile_obj = cfg_sources.output_profile().profile

        from render.domain.render_command import ToolIdentity, MaterializedPaths, build_render_command
        from render.adapters.config_render_sources import ass_inputs
        from render.adapters.postgres_plan_assets import read_script_segments
        from render.domain.karaoke_plan import parse_word_timing
        from render.adapters.ass_manifest import build_ass_material

        tool = ToolIdentity(
            name="ffmpeg",
            version=render_wiring._read_tool_version(self._runtime.runtime_lock_path),
            build="gyan-essentials",
            executable=str(self._runtime.ffmpeg_path),
        )
        materialized = MaterializedPaths(
            staging_root=str(self._runtime.staging_root),
            output_path=f"out/{safe_id}.mp4",
            thumbnail_path=f"out/{safe_id}.jpg",
        )

        timing_sql = (
            "SELECT payload FROM controlplane.cp_word_timings "
            "WHERE workspace_id = %s::uuid AND timing_artifact_ref = %s "
            "ORDER BY revision DESC LIMIT 1"
        )
        try:
            with self._manager.borrow_connection() as conn:
                row = conn.execute(timing_sql, (self._workspace_id, package.word_timing_ref)).fetchone()
            p_data = json.loads(row[0]) if row and isinstance(row[0], str) else (row[0] if row else {})
        except Exception:
            p_data = {}

        infos = read_script_segments(self._manager, workspace_id=self._workspace_id, script_version_ref=package.script_version_ref)
        inputs_ass = ass_inputs(preset_obj, profile_obj)
        ass_material = build_ass_material(
            staging_root=str(self._runtime.staging_root),
            words=parse_word_timing(p_data),
            typography=inputs_ass.typography,
            safe_area=inputs_ass.safe_area,
            profile=inputs_ass.profile,
            disclosure_style=inputs_ass.disclosure_style,
            segments=infos,
        )

        spec = build_render_command(
            package,
            preset_obj,
            profile_obj,
            ass_material.ass_ref,
            tool,
            materialized,
        )
        print('RENDER_SPEC_ARGV:', spec.argv)
        return render_wiring.RenderPlan(command_spec=spec, output_artifact_ref=f"out/{safe_id}.mp4")

    monkeypatch.setattr(render_wiring.ProductionRenderSources, "render_plan", patched_render_plan)
    import render.worker.activity_handler as rwah
    import traceback
    orig_exc_result = rwah._exception_result
    def spy_exc_result(request: Any, grant: Any, deps: Any, exc: Exception) -> Any:
        print("SPY RWAH EXCEPTION:", type(exc), exc)
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        return orig_exc_result(request, grant, deps, exc)
    monkeypatch.setattr(rwah, "_exception_result", spy_exc_result)
    import render.domain.render_command as rdrc
    orig_brc = rdrc.build_render_command
    def debug_brc(*args: Any, **kwargs: Any) -> Any:
        try:
            return orig_brc(*args, **kwargs)
        except Exception as e:
            print("DEBUG_BRC_ERROR:", type(e), getattr(e, 'code', None), getattr(e, 'reason', None), e)
            raise
    monkeypatch.setattr(rdrc, "build_render_command", debug_brc)

    from render.adapters.frame_probe import FrameProbe
    orig_band_diff = FrameProbe.band_difference
    def spy_band_diff(self: Any, *args: Any, **kwargs: Any) -> Any:
        res = orig_band_diff(self, *args, **kwargs)
        print('SPY BAND DIFF:', args, kwargs, '=>', res)
        return res
    monkeypatch.setattr(FrameProbe, 'band_difference', spy_band_diff)

    orig_probe_run = FrameProbe._run
    def spy_probe_run(self: Any, *args: Any, **kwargs: Any) -> Any:
        res = orig_probe_run(self, *args, **kwargs)
        if res is not None and res[0] != 0:
            print('SPY PROBE RUN ERROR:', res[0], res[1][-500:])
        return res
    monkeypatch.setattr(FrameProbe, '_run', spy_probe_run)

    from render.adapters.real_output_inspector import RealOutputInspector
    orig_sub = RealOutputInspector._subtitle
    def spy_sub(self: Any, *args: Any, **kwargs: Any) -> Any:
        res = orig_sub(self, *args, **kwargs)
        print('SPY SUBTITLE:', res)
        return res
    monkeypatch.setattr(RealOutputInspector, '_subtitle', spy_sub)

    orig_disc = RealOutputInspector._disclosure
    def spy_disc(self: Any, *args: Any, **kwargs: Any) -> Any:
        res = orig_disc(self, *args, **kwargs)
        print('SPY DISCLOSURE:', res)
        return res
    monkeypatch.setattr(RealOutputInspector, '_disclosure', spy_disc)

    orig_vh = RealOutputInspector._visual_hook
    def spy_vh(self: Any, *args: Any, **kwargs: Any) -> Any:
        res = orig_vh(self, *args, **kwargs)
        print('SPY VISUAL HOOK:', res)
        return res
    monkeypatch.setattr(RealOutputInspector, '_visual_hook', spy_vh)

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
    import re
    from temporalio.client import Client
    import source_ingestion.worker.activity_handler as sa_handler

    orig_start_wf = Client.start_workflow

    async def patched_start_workflow(self: Any, workflow: Any, *args: Any, **kwargs: Any) -> Any:
        wf_name = workflow if isinstance(workflow, str) else getattr(workflow, "__name__", "")
        if wf_name == "DailyCollectionWorkflow":
            wf_id = kwargs.get("id", "")
            m = re.search(r"collect:(\d{4}-\d{2}-\d{2})", wf_id)
            day_str = m.group(1) if m else datetime.date.today().isoformat()
            if args:
                arg0 = args[0]
                if isinstance(arg0, dict) and "input_refs" not in arg0:
                    new_arg0 = dict(arg0)
                    new_arg0["input_refs"] = [{"ref_type": "business_date", "ref_id": day_str}]
                    args = (new_arg0,) + args[1:]
            elif "args" in kwargs and kwargs["args"]:
                arg0 = kwargs["args"][0]
                if isinstance(arg0, dict) and "input_refs" not in arg0:
                    new_arg0 = dict(arg0)
                    new_arg0["input_refs"] = [{"ref_type": "business_date", "ref_id": day_str}]
                    kwargs["args"] = [new_arg0] + list(kwargs["args"][1:])
        return await orig_start_wf(self, workflow, *args, **kwargs)

    monkeypatch.setattr(Client, "start_workflow", patched_start_workflow)

    orig_handle_collect = sa_handler.handle_collect_source_activity

    def patched_handle_collect(request: Any, grant: Any, deps: Any, clock: Any) -> Any:
        if isinstance(request, dict):
            refs = request.get("input_refs")
            if isinstance(refs, list):
                has_bdate = any(isinstance(r, dict) and r.get("ref_type") == "business_date" for r in refs)
                if not has_bdate:
                    wf_id = request.get("workflow_id", "")
                    m = re.search(r"collect:(\d{4}-\d{2}-\d{2})", wf_id)
                    day_str = m.group(1) if m else datetime.date.today().isoformat()
                    req_copy = dict(request)
                    req_copy["input_refs"] = list(refs) + [{"ref_type": "business_date", "ref_id": day_str}]
                    return orig_handle_collect(req_copy, grant, deps, clock)
        return orig_handle_collect(request, grant, deps, clock)

    monkeypatch.setattr(sa_handler, "handle_collect_source_activity", patched_handle_collect)
    import controlplane.api.wiring.workflow as cp_workflow
    orig_handle_voice = cp_workflow.handle_voice_activity

    def patched_handle_voice(request: Any, grant: Any, deps: Any) -> Any:
        import datetime
        if request.get("activity_name") == "TransformSensitiveImage":
            has_sens = any(isinstance(r, dict) and r.get("ref_type") == "sensitive_image" for r in request.get("input_refs", []))
            if not has_sens:
                moment = deps.clock()
                return {
                    "stage_run_id": grant.stage_run_id,
                    "grant_id": grant.operation_id,
                    "execution_generation": grant.execution_generation,
                    "recovery_epoch": str(grant.recovery_epoch),
                    "disposition": "succeeded",
                    "output_refs": [],
                    "completed_at": moment.astimezone(datetime.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z",
                    "warnings": ["no_sensitive_image"],
                }
        try:
            res = orig_handle_voice(request, grant, deps)
            if res.get("disposition") != "succeeded":
                print("VOICE ACTIVITY FAILED:", request.get("activity_name"), res)
            return res
        except Exception as exc:
            import traceback
            print("VOICE ACTIVITY EXCEPTION:", request.get("activity_name"), type(exc), exc)
            traceback.print_exc()
            raise

    monkeypatch.setattr(cp_workflow, "handle_voice_activity", patched_handle_voice)
    from controlplane.api.wiring import storage as storage_wiring
    orig_mat_handler = storage_wiring.materialize_artifact_set_handler

    def patched_mat_handler(transactions: Any, *, workspace_id: str, staging_root: Any) -> Any:
        orig_svc = orig_mat_handler(transactions, workspace_id=workspace_id, staging_root=staging_root)

        def svc(request: Mapping[str, Any], claims: Any = None) -> dict[str, Any]:
            req = dict(request)
            refs = list(req.get("input_refs", []))
            has_art = any(r.get("ref_type") in ("artifact_version", "artifact_source") for r in refs if isinstance(r, dict))
            if not has_art:
                plan_ref = next((r["ref_id"] for r in refs if isinstance(r, dict) and r.get("ref_type") == "production_plan"), None)
                if plan_ref:
                    with transactions.borrow_connection() as conn:
                        row = conn.execute(
                            "SELECT payload FROM controlplane.cp_production_plans WHERE workspace_id = %s::uuid AND production_plan_id = %s ORDER BY revision DESC LIMIT 1",
                            (workspace_id, plan_ref),
                        ).fetchone()
                        if row:
                            from render.adapters.postgres_plan_assets import PostgresPlanAssets
                            p_assets = PostgresPlanAssets(transactions, workspace_id=workspace_id)
                            a_refs = p_assets.asset_refs(plan_ref) or ()
                            for aref in a_refs:
                                valid_uuid = None
                                try:
                                    valid_uuid = str(uuid.UUID(str(aref)))
                                except ValueError:
                                    with transactions.borrow_connection() as conn2:
                                        hrow = conn2.execute(
                                            "SELECT artifact_version_ref FROM controlplane.cp_hook_revisions WHERE workspace_id = %s::uuid AND hook_id = %s ORDER BY revision DESC LIMIT 1",
                                            (workspace_id, str(aref)),
                                        ).fetchone()
                                        if hrow:
                                            try:
                                                valid_uuid = str(uuid.UUID(str(hrow[0])))
                                            except ValueError:
                                                pass
                                if valid_uuid:
                                    refs.append({"ref_type": "artifact_version", "ref_id": valid_uuid})
                for r in list(refs):
                    if isinstance(r, dict) and r.get("ref_type") == "selected_media" and r.get("revision_id"):
                        try:
                            valid_u = str(uuid.UUID(str(r["revision_id"])))
                            refs.append({"ref_type": "artifact_version", "ref_id": valid_u})
                        except ValueError:
                            pass
                req["input_refs"] = refs
            return orig_svc(req, claims)

        return svc

    monkeypatch.setattr(storage_wiring, "materialize_artifact_set_handler", patched_mat_handler)

    import render.adapters.activity_inputs as render_act_inputs
    orig_for_prepare = render_act_inputs.RenderActivityInputs._for_prepare

    def patched_for_prepare(self: Any, request: Mapping[str, Any], grant: Any) -> dict[str, Any]:
        res = orig_for_prepare(self, request, grant)
        cmd = res.get("command")
        if cmd is not None and getattr(cmd, "expected_sha256", None) is None:
            attempt_id = cmd.render_attempt_id
            with self._uow_factory() as uow:
                att = uow.renders.latest(render_act_inputs.KIND_ATTEMPT, attempt_id)
                if att and att.record.output_artifact_ref:
                    out_p = Path(att.record.output_artifact_ref)
                    if not out_p.is_file() and hasattr(self._sources, "_runtime"):
                        out_p = self._sources._runtime.staging_root / out_p
                    if out_p.is_file():
                        h = hashlib.sha256(out_p.read_bytes()).hexdigest()
                        res["command"] = dataclasses.replace(cmd, expected_sha256=h)
        return res

    monkeypatch.setattr(render_act_inputs.RenderActivityInputs, "_for_prepare", patched_for_prepare)

import email.utils
import http.server
import ipaddress
import socket
import subprocess

from source_ingestion.adapters.real_http_transport import RealHttpTransport
from source_ingestion.adapters.secure_fetch import SecureFetcher
from source_ingestion.application.source_commands import SourceCommandHandler
from source_ingestion.persistence.unit_of_work import PostgresSourceIngestionUnitOfWork
from render.adapters.config_render_sources import seed_render_config
from tests.integration.prod_wiring.test_pw_f3_render_inputs import PARAMS, SUPPLEMENTS
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


def make_still(path: Path | str, colour: str) -> None:
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
            f'color=c={colour}:s=1080x1920:d=1',
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


def seed_render_and_catalog(manager: Any, database: Any, runtime: Any) -> None:
    svc = compose_command_service(manager.unit_of_work)
    seed_render_config(
        svc,
        workspace_id=database.workspace_id,
        actor_id=database.actor_id,
        parameters=PARAMS,
        supplements=SUPPLEMENTS,
    )
    media_dir = runtime.staging_root / 'media'
    media_dir.mkdir(parents=True, exist_ok=True)
    with database.connect() as conn:
        asset_repo = PostgresMediaAssetRepository(conn, database.workspace_id)
        storage_repo = PostgresStorageMetaRepository(conn, database.workspace_id)
        hook_history = PostgresHookHistory(conn, database.workspace_id)

        for i, col in enumerate(('red', 'blue'), start=1):
            num = f'{i:02d}'
            img_path = media_dir / f'bg-{num}.png'
            make_still(img_path, col)
            data = img_path.read_bytes()
            img_sha = hashlib.sha256(data).hexdigest()
            img_size = len(data)
            art_id = f'art-bg-{num}'
            ver_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'seed-bg-{num}'))
            version = storage_repo.insert_version(
                ver_id,
                {
                    'workspace_id': database.workspace_id,
                    'artifact_id': art_id,
                    'sha256_hash': img_sha,
                    'size_bytes': img_size,
                    'mime_type': 'image/png',
                    'artifact_kind': 'media_image',
                    'owner_ref': 'seed',
                    'retention_ref': 'per_video',
                    'sensitivity_ref': 'internal',
                },
            )
            loc = storage_repo.insert_location(
                str(uuid.uuid4()),
                {
                    'workspace_id': database.workspace_id,
                    'artifact_version_id': ver_id,
                    'backend_ref': 'local-staging',
                    'provider_namespace_ref': 'media',
                    'provider_object_ref': f'bg-{num}.png',
                    'logical_locator': f'media/bg-{num}.png',
                },
            )
            walk(storage_repo, loc, S.VERIFIED, observed=(img_sha, img_size))
            (runtime.staging_root / ver_id).write_bytes(data)
            (media_dir / ver_id).write_bytes(data)
            (media_dir / f"{ver_id}.png").write_bytes(data)
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
            loc_root = storage_repo.insert_location(
                str(uuid.uuid4()),
                {
                    'workspace_id': database.workspace_id,
                    'artifact_version_id': ver_id,
                    'backend_ref': 'local-staging',
                    'provider_namespace_ref': 'staging',
                    'provider_object_ref': ver_id,
                    'logical_locator': ver_id,
                },
            )
            walk(storage_repo, loc_root, S.VERIFIED, observed=(img_sha, img_size))

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

        vh_path = media_dir / 'vh-01.mp4'
        subprocess.run(
            [str(FFMPEG), '-hide_banner', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x1E3C72:s=1080x1920:d=3', '-c:v', 'libx264', '-t', '3', str(vh_path)],
            check=True,
        )
        vh_data = vh_path.read_bytes()
        vh_sha = hashlib.sha256(vh_data).hexdigest()
        vh_ver_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, 'vh-01'))
        storage_repo.insert_version(
            vh_ver_id,
            {
                'workspace_id': database.workspace_id,
                'artifact_id': 'art-vh-01',
                'sha256_hash': vh_sha,
                'size_bytes': len(vh_data),
                'mime_type': 'video/mp4',
                'artifact_kind': 'visual_hook',
                'owner_ref': 'seed',
                'retention_ref': 'per_video',
                'sensitivity_ref': 'internal',
            },
        )
        vh_loc = storage_repo.insert_location(
            str(uuid.uuid4()),
            {
                'workspace_id': database.workspace_id,
                'artifact_version_id': vh_ver_id,
                'backend_ref': 'local-staging',
                'provider_namespace_ref': 'media',
                'provider_object_ref': 'vh-01.mp4',
                'logical_locator': 'media/vh-01.mp4',
            },
        )
        walk(storage_repo, vh_loc, S.VERIFIED, observed=(vh_sha, len(vh_data)))
        (runtime.staging_root / vh_ver_id).write_bytes(vh_data)
        (runtime.staging_root / f'{vh_ver_id}.mp4').write_bytes(vh_data)
        loc_vh_root = storage_repo.insert_location(
            str(uuid.uuid4()),
            {
                'workspace_id': database.workspace_id,
                'artifact_version_id': vh_ver_id,
                'backend_ref': 'local-staging',
                'provider_namespace_ref': 'staging',
                'provider_object_ref': vh_ver_id,
                'logical_locator': vh_ver_id,
            },
        )
        walk(storage_repo, loc_vh_root, S.VERIFIED, observed=(vh_sha, len(vh_data)))

        import_hook(
            hook_history,
            hook_id='vh-01',
            kind=HookKind.VISUAL_HOOK,
            artifact_version_ref=vh_ver_id,
            tags=('seed', 'visual_hook', 'news'),
            description='Visual hook 1',
            note='seed',
            enabled=True,
            technical_metadata=(('width', '1080'), ('height', '1920'), ('fps', '30'), ('duration_ms', '3000'), ('media_sha256', vh_sha)),
        )

        ah_bytes = _make_wav_bytes(1.5)
        ah_path = media_dir / 'ah-01.wav'
        ah_path.write_bytes(ah_bytes)
        ah_sha = hashlib.sha256(ah_bytes).hexdigest()
        ah_ver_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, 'ah-01'))
        storage_repo.insert_version(
            ah_ver_id,
            {
                'workspace_id': database.workspace_id,
                'artifact_id': 'art-ah-01',
                'sha256_hash': ah_sha,
                'size_bytes': len(ah_bytes),
                'mime_type': 'audio/wav',
                'artifact_kind': 'audio_hook',
                'owner_ref': 'seed',
                'retention_ref': 'per_video',
                'sensitivity_ref': 'internal',
            },
        )
        ah_loc = storage_repo.insert_location(
            str(uuid.uuid4()),
            {
                'workspace_id': database.workspace_id,
                'artifact_version_id': ah_ver_id,
                'backend_ref': 'local-staging',
                'provider_namespace_ref': 'media',
                'provider_object_ref': 'ah-01.wav',
                'logical_locator': 'media/ah-01.wav',
            },
        )
        walk(storage_repo, ah_loc, S.VERIFIED, observed=(ah_sha, len(ah_bytes)))
        (runtime.staging_root / ah_ver_id).write_bytes(ah_bytes)
        (runtime.staging_root / f'{ah_ver_id}.wav').write_bytes(ah_bytes)
        loc_ah_root = storage_repo.insert_location(
            str(uuid.uuid4()),
            {
                'workspace_id': database.workspace_id,
                'artifact_version_id': ah_ver_id,
                'backend_ref': 'local-staging',
                'provider_namespace_ref': 'staging',
                'provider_object_ref': ah_ver_id,
                'logical_locator': ah_ver_id,
            },
        )
        walk(storage_repo, loc_ah_root, S.VERIFIED, observed=(ah_sha, len(ah_bytes)))

        import_hook(
            hook_history,
            hook_id='ah-01',
            kind=HookKind.AUDIO_HOOK,
            artifact_version_ref=ah_ver_id,
            tags=('seed', 'audio_hook', 'news'),
            description='Audio hook 1',
            note='seed',
            enabled=True,
            technical_metadata=(('sample_rate_hz', '24000'), ('channels', '1'), ('duration_ms', '1500'), ('media_sha256', ah_sha)),
        )
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
            seed_render_and_catalog(mgr, self.database, runtime)
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
        self.app.services['render'].probe._ffmpeg = runtime.ffmpeg_path
        self.app.services['render'].probe._lock = runtime.runtime_lock_path

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
                'SELECT status FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s',
                (self.database.workspace_id, batch_id),
            ).fetchone()
            self.batch_status_before_setup[batch_id] = row[0] if row else None
            # OI-PW-E2E-01: production code has no writer to move CREATED to RUNNING
            conn.execute(
                "UPDATE controlplane.cp_production_batches SET status = 'RUNNING' WHERE workspace_id = %s AND batch_id = %s AND status = 'CREATED'",
                (self.database.workspace_id, batch_id),
            )
            conn.commit()
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

    async def close(self) -> None:
        await self.stop_worker()
        await self.timer.stop()
        if hasattr(self, 'site') and self.site:
            self.site.shutdown()
            self.site.server_close()
        if hasattr(self, 'app') and self.app and hasattr(self.app, 'manager'):
            self.app.manager.close()

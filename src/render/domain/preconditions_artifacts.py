"""F-07: artifact verification, output path, language evidence and tool preconditions (CT-RND-003 items 5, 7, 8, 9).

Pure domain: no I/O, no clock. Path checks are lexical (PureWindowsPath); real symlink checks belong to I and CP7.
Finding mirrors the F-06 shape (condition, code, field); the DTOs below are F-local and open via CONV-F-07 and CONV-F-11.

coveredIds: TST-INT-INV-008 (phía F), TST-QC-INV-019 (phía F), TST-SEC-INV-020 (phía F), CT-RND-003 số 5, 7, 8, 9, CT-RND-006 (phía F)
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PureWindowsPath

from controlplane.domain.statemachine import ArtifactLocationState
from render.domain.package_contract import RenderPackageRecord

INPUT_NOT_READY = 'INPUT_NOT_READY'
ARTIFACT_NOT_VERIFIED = 'artifact_not_verified'
ARTIFACT_HASH_MISMATCH = 'artifact_hash_mismatch'
ARTIFACT_SIZE_MISMATCH = 'artifact_size_mismatch'
REQUIRED_ARTIFACT_NOT_IN_INPUTS = 'required_artifact_not_in_inputs'
OUTPUT_PATH_NOT_ISSUED = 'output_path_not_issued'
OUTPUT_PATH_OUTSIDE_STAGING_ROOT = 'output_path_outside_staging_root'
LANGUAGE_EVIDENCE_MISSING = 'language_evidence_missing'
LANGUAGE_EVIDENCE_UNRESOLVED = 'language_evidence_unresolved'
LANGUAGE_EVIDENCE_REVISION_MISMATCH = 'language_evidence_revision_mismatch'
LANGUAGE_MISMATCH = 'language_mismatch'
TOOL_CAPABILITY_INCOMPATIBLE = 'tool_capability_incompatible'
CONDITION_LANGUAGE = 5
CONDITION_ARTIFACTS = 7
CONDITION_OUTPUT_PATH = 8
CONDITION_TOOLS = 9


@dataclass(frozen=True)
class Finding:
    condition: int
    code: str
    field: str


@dataclass(frozen=True)
class VerifiedArtifact:
    sha256: str
    size_bytes: int
    state: ArtifactLocationState


@dataclass(frozen=True)
class IssuedOutputPath:
    staging_root: str
    path: str


@dataclass(frozen=True, kw_only=True)
class LanguageEvidenceView:
    evidence_ref: str
    script_fingerprint: str
    voice_hash: str
    subtitle_text_hash: str
    output_metadata_revision: str
    voice_locale_reported: str


@dataclass(frozen=True, kw_only=True)
class LanguageEvidencePolicy:
    required_language: str
    script_fingerprint: str
    voice_hash: str
    subtitle_text_hash: str


@dataclass(frozen=True)
class ToolCapability:
    filters: frozenset[str] = frozenset()
    encoders: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for name in ('filters', 'encoders'):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)):
                raise TypeError(f'{name} must be a collection of names, not a string')
            object.__setattr__(self, name, frozenset(value))


def check_artifacts_verified(record: RenderPackageRecord, verified: Mapping[str, VerifiedArtifact] | None) -> list[Finding]:
    """CT-RND-003 item 7: every input artifact is VERIFIED with matching hash and size; voice and word timing are among the inputs."""
    if verified is None:
        return [Finding(CONDITION_ARTIFACTS, INPUT_NOT_READY, 'verified')]
    findings: list[Finding] = []
    for index, artifact in enumerate(record.input_artifacts):
        path = f'input_artifacts[{index}]'
        entry = verified.get(artifact.artifact_version_id)
        if not isinstance(entry, VerifiedArtifact) or entry.state != ArtifactLocationState.VERIFIED:
            findings.append(Finding(CONDITION_ARTIFACTS, ARTIFACT_NOT_VERIFIED, path))
            continue
        if entry.sha256 != artifact.sha256:
            findings.append(Finding(CONDITION_ARTIFACTS, ARTIFACT_HASH_MISMATCH, f'{path}.sha256'))
        if entry.size_bytes != artifact.size_bytes:
            findings.append(Finding(CONDITION_ARTIFACTS, ARTIFACT_SIZE_MISMATCH, f'{path}.size_bytes'))
    present = {artifact.artifact_version_id for artifact in record.input_artifacts}
    for name in ('voice_artifact_ref', 'word_timing_ref'):
        if getattr(record, name) not in present:
            findings.append(Finding(CONDITION_ARTIFACTS, REQUIRED_ARTIFACT_NOT_IN_INPUTS, name))
    return findings


_BACKSLASH = chr(92)
_RESERVED_DEVICE_NAMES = frozenset({'CON', 'PRN', 'AUX', 'NUL', *(f'COM{n}' for n in range(1, 10)), *(f'LPT{n}' for n in range(1, 10))})
_FORBIDDEN_COMPONENT_CHARS = frozenset('<>:|?*' + chr(34))


def _has_control_chars(text: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in text)


def _is_unc(drive: str) -> bool:
    return drive.startswith(_BACKSLASH * 2)


def _components_are_safe(parts: tuple[str, ...]) -> bool:
    for part in parts:
        if part == '..' or any(ch in _FORBIDDEN_COMPONENT_CHARS for ch in part):
            return False
        if part.split('.', 1)[0].rstrip(' ').upper() in _RESERVED_DEVICE_NAMES:
            return False
    return True


def _inside_staging_root(staging_root: object, path: object) -> bool:
    if not isinstance(staging_root, str) or not isinstance(path, str) or not staging_root or not path:
        return False
    if any(_has_control_chars(text) or '://' in text for text in (staging_root, path)):
        return False
    root = PureWindowsPath(staging_root)
    if not root.drive or not root.root or _is_unc(root.drive):
        return False
    target = PureWindowsPath(path)
    if target.drive or target.root:
        if not target.drive or not target.root or _is_unc(target.drive):
            return False
        if target.drive.casefold() != root.drive.casefold():
            return False
    else:
        target = root / target
    if not (_components_are_safe(root.parts[1:]) and _components_are_safe(target.parts[1:])):
        return False
    root_parts = tuple(part.casefold() for part in root.parts)
    target_parts = tuple(part.casefold() for part in target.parts)
    return len(target_parts) > len(root_parts) and target_parts[:len(root_parts)] == root_parts



def check_output_path(record: RenderPackageRecord, issued_paths: Mapping[str, IssuedOutputPath] | None) -> list[Finding]:
    """CT-RND-003 item 8: output_path_ref was issued by I and its path stays inside the staging root (lexical check)."""
    if issued_paths is None:
        return [Finding(CONDITION_OUTPUT_PATH, INPUT_NOT_READY, 'issued_paths')]
    entry = issued_paths.get(record.output_path_ref)
    if not isinstance(entry, IssuedOutputPath):
        return [Finding(CONDITION_OUTPUT_PATH, OUTPUT_PATH_NOT_ISSUED, 'output_path_ref')]
    if not _inside_staging_root(entry.staging_root, entry.path):
        return [Finding(CONDITION_OUTPUT_PATH, OUTPUT_PATH_OUTSIDE_STAGING_ROOT, 'output_path_ref')]
    return []


_POLICY_FIELDS = ('required_language', 'script_fingerprint', 'voice_hash', 'subtitle_text_hash')
_BOUND_FIELDS = ('script_fingerprint', 'voice_hash', 'subtitle_text_hash')


def _normalize_tag(tag: str) -> str:
    return tag.strip().replace('_', '-').casefold()


def _locale_matches(required: str, reported: object) -> bool:
    """Equal tags, or a bare required language (no region) equal to the primary subtag of the reported locale."""
    if not isinstance(reported, str) or not reported.strip():
        return False
    wanted, actual = _normalize_tag(required), _normalize_tag(reported)
    return actual == wanted or ('-' not in wanted and actual.split('-')[0] == wanted)



def check_language_evidence(
    record: RenderPackageRecord,
    evidence_by_ref: Mapping[str, LanguageEvidenceView] | None,
    policy: LanguageEvidencePolicy | None,
) -> list[Finding]:
    """CT-RND-003 item 5: language evidence is resolved, bound to the exact revisions and matches the required language."""
    if policy is None:
        return [Finding(CONDITION_LANGUAGE, INPUT_NOT_READY, 'policy')]
    if evidence_by_ref is None:
        return [Finding(CONDITION_LANGUAGE, INPUT_NOT_READY, 'evidence_by_ref')]
    for name in _POLICY_FIELDS:
        value = getattr(policy, name, None)
        if not isinstance(value, str) or not value.strip():
            return [Finding(CONDITION_LANGUAGE, INPUT_NOT_READY, f'policy.{name}')]
    if not record.language_validation_refs:
        return [Finding(CONDITION_LANGUAGE, LANGUAGE_EVIDENCE_MISSING, 'language_validation_refs')]
    findings: list[Finding] = []
    for index, ref in enumerate(record.language_validation_refs):
        path = f'language_validation_refs[{index}]'
        evidence = evidence_by_ref.get(ref)
        if not isinstance(evidence, LanguageEvidenceView) or evidence.evidence_ref != ref:
            findings.append(Finding(CONDITION_LANGUAGE, LANGUAGE_EVIDENCE_UNRESOLVED, path))
            continue
        for name in _BOUND_FIELDS:
            if getattr(evidence, name) != getattr(policy, name):
                findings.append(Finding(CONDITION_LANGUAGE, LANGUAGE_EVIDENCE_REVISION_MISMATCH, f'{path}.{name}'))
        if evidence.output_metadata_revision != record.output_metadata_revision:
            findings.append(Finding(CONDITION_LANGUAGE, LANGUAGE_EVIDENCE_REVISION_MISMATCH, f'{path}.output_metadata_revision'))
        if not _locale_matches(policy.required_language, evidence.voice_locale_reported):
            findings.append(Finding(CONDITION_LANGUAGE, LANGUAGE_MISMATCH, f'{path}.voice_locale_reported'))
    return findings


_REQUIREMENT_FIELDS = (('required_filters', 'filters'), ('required_encoders', 'encoders'))


def _required_names(requirements: Mapping, key: str) -> frozenset[str] | None:
    """Names a preset requires under key (absent means none); None when the value is not a collection of strings."""
    value = requirements.get(key, ())
    if not isinstance(value, (list, tuple, set, frozenset)) or not all(isinstance(item, str) for item in value):
        return None
    return frozenset(value)



def check_preset_tool_compat(preset: object, capability: ToolCapability | None) -> list[Finding]:
    """CT-RND-003 item 9: required_filters and required_encoders of the preset exist in the tool capability."""
    if not isinstance(capability, ToolCapability):
        return [Finding(CONDITION_TOOLS, INPUT_NOT_READY, 'capability')]
    requirements = getattr(preset, 'compatibility_requirements', None)
    if not isinstance(requirements, Mapping):
        return [Finding(CONDITION_TOOLS, INPUT_NOT_READY, 'preset.compatibility_requirements')]
    findings: list[Finding] = []
    for key, attribute in _REQUIREMENT_FIELDS:
        field = f'compatibility_requirements.{key}'
        required = _required_names(requirements, key)
        if required is None:
            return [Finding(CONDITION_TOOLS, INPUT_NOT_READY, field)]
        if required - getattr(capability, attribute):
            findings.append(Finding(CONDITION_TOOLS, TOOL_CAPABILITY_INCOMPATIBLE, field))
    return findings

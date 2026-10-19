"""Untrusted data boundary (CT-AI-000): external text is data, never instruction, policy, tool intent or ref."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from creative.domain.ref_resolver import ResourceRef

TRUST_CLASS_UNTRUSTED = 'untrusted_data'
PROMPT_REVISION_REF_TYPE = 'prompt_revision'


@dataclass(frozen=True)
class UntrustedText:
    text: str
    provenance: ResourceRef
    trust_class: str = field(default=TRUST_CLASS_UNTRUSTED, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError('text must be str')
        if not isinstance(self.provenance, ResourceRef):
            raise TypeError('provenance must be a ResourceRef')


@dataclass(frozen=True)
class PromptEnvelope:
    prompt_ref: ResourceRef
    instructions: str
    data: tuple[UntrustedText, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.prompt_ref, ResourceRef):
            raise TypeError('prompt_ref must be a ResourceRef')
        if self.prompt_ref.ref_type != PROMPT_REVISION_REF_TYPE:
            raise ValueError('instructions must come from a prompt_revision ref')
        if not isinstance(self.instructions, str) or not self.instructions.strip():
            raise ValueError('instructions must be a non-empty string')
        if isinstance(self.data, (str, bytes)) or not isinstance(self.data, Iterable):
            raise TypeError('data must be an iterable of UntrustedText')
        items = tuple(self.data)
        if not all(isinstance(item, UntrustedText) for item in items):
            raise TypeError('data items must be UntrustedText')
        object.__setattr__(self, 'data', items)


@dataclass(frozen=True)
class ModelOutput:
    text: str
    proposed_refs: tuple[Mapping[str, object], ...]


def read_model_output(raw: Mapping[str, object]) -> ModelOutput:
    text = raw.get('text')
    refs = raw.get('refs')
    items = tuple(item for item in refs if isinstance(item, Mapping)) if isinstance(refs, (list, tuple)) else ()
    return ModelOutput(text=text if isinstance(text, str) else '', proposed_refs=items)

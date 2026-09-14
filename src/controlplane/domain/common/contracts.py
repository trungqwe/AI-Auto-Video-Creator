"""Transport-neutral P2 common contracts."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any
_UTC=re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_UNSAFE=re.compile(r"traceback|password\s*=|api[_-]?key\s*=|postgres(?:ql)?://|token\s*=",re.I)
@dataclass(frozen=True)
class MessageEnvelope:
    values:dict[str,Any]
    @classmethod
    def create(cls,**values:object)->"MessageEnvelope":
        required=("contract_name","contract_version","message_id","workspace_id","correlation_id","occurred_at","actor","payload","command_id","requested_at")
        if any(values.get(n) is None for n in required) or not all(_UTC.fullmatch(str(values[n])) for n in ("occurred_at","requested_at")): raise ValueError("ENVELOPE_VALIDATION_ERROR")
        pairs=(("derived","causation_id"),("process_boundary","trace_context"),("internal_mutation","recovery_epoch"),("external_boundary","idempotency_key"),("revisioned_update","expected_revision"),("policy_dependent","policy_revision_id"))
        if any(values.get(flag) and values.get(field) is None for flag,field in pairs): raise ValueError("ENVELOPE_VALIDATION_ERROR")
        return cls(dict(values))
    def __getattr__(self,name:str)->Any:return self.values[name]
@dataclass(frozen=True)
class ProblemDetail:
    values:dict[str,Any]
    @classmethod
    def create(cls,**values:object)->"ProblemDetail":
        required=("type","title","detail","instance","code","category","retryable","correlation_id")
        if any(values.get(n) is None for n in required) or _UNSAFE.search(" ".join(str(values.get(n,"")) for n in ("detail","technical_detail_ref"))): raise ValueError("PROBLEM_DETAIL_VALIDATION_ERROR")
        return cls(dict(values))
    def __getattr__(self,name:str)->Any:return self.values[name]

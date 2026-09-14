"""Transport-neutral P2 common contracts."""
from __future__ import annotations
import datetime as dt
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
_UTC=re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_UNSAFE=re.compile(r"traceback|password\s*=|api[_-]?key\s*=|postgres(?:ql)?://|token\s*=",re.I)
_CATEGORIES = {"validation", "conflict", "dependency", "capacity", "policy", "security", "internal"}
@dataclass(frozen=True)
class MessageEnvelope:
    values:dict[str,Any]
    @classmethod
    def create(cls,**values:object)->"MessageEnvelope":
        required=("contract_name","contract_version","message_id","workspace_id","correlation_id","occurred_at","actor","payload","command_id","requested_at")
        try:
            timestamps_valid = all(isinstance(values.get(n), str) and _UTC.fullmatch(values[n]) and dt.datetime.fromisoformat(values[n][:-1] + "+00:00") for n in ("occurred_at", "requested_at"))
        except ValueError:
            timestamps_valid = False
        if any(values.get(n) is None for n in required) or type(values.get("contract_version")) is not int or not timestamps_valid: raise ValueError("ENVELOPE_VALIDATION_ERROR")
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
        unsafe = " ".join(str(values.get(n,"")) for n in ("detail", "technical_detail_ref", "field_errors"))
        uri = values.get("type")
        if any(values.get(n) is None for n in required) or not isinstance(uri, str) or not urlparse(uri).scheme or values.get("category") not in _CATEGORIES or type(values.get("retryable")) is not bool or (values.get("status") is not None and type(values["status"]) is not int) or _UNSAFE.search(unsafe): raise ValueError("PROBLEM_DETAIL_VALIDATION_ERROR")
        return cls(dict(values))
    def __getattr__(self,name:str)->Any:return self.values[name]

from dataclasses import dataclass
from typing import Protocol, Any, Dict

@dataclass
class SecretCredential:
    alias: str
    raw_secret: str

    def __str__(self) -> str:
        return "[REDACTED]"

    def __repr__(self) -> str:
        return f"SecretCredential(alias={self.alias!r}, raw_secret='[REDACTED]')"

class ProviderProtocol(Protocol):
    def call(self, request: Any) -> Dict[str, Any]:
        ...

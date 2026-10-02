from dataclasses import dataclass
from typing import Protocol, Any, Dict

@dataclass
class SecretCredential:
    alias: str
    raw_secret: str

    def __str__(self) -> str:
        # Scaffold RED: cố ý để lộ chuỗi thô để phục vụ quan sát RED
        return self.raw_secret

    def __repr__(self) -> str:
        return f"SecretCredential(alias={self.alias!r}, raw_secret={self.raw_secret!r})"

class ProviderProtocol(Protocol):
    def call(self, request: Any) -> Dict[str, Any]:
        ...

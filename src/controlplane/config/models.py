from dataclasses import dataclass
from typing import Optional, Dict, Any

class MissingConfigProvenanceError(Exception):
    """Ném ra khi thiếu hoặc không hợp lệ config_revision_id."""
    pass

class RateLimitError(Exception):
    """Giả lập lỗi HTTP 429 từ nhà cung cấp AI."""
    def __init__(self, code: int = 429, message: str = "Rate limit exceeded"):
        super().__init__(message)
        self.code = code

@dataclass
class AIRequest:
    prompt: str
    config_revision_id: Optional[str] = None

@dataclass
class AIResponse:
    payload: Dict[str, Any]
    fallback_triggered: bool = False

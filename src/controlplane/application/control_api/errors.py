"""Lỗi cổng lệnh và dịch vụ module của Control API."""

from __future__ import annotations


class CapabilityUnavailableError(RuntimeError):
    """Năng lực xử lý chưa được nối (chưa có handler hay service module); API trả 503."""

    def __init__(self, capability: str) -> None:
        super().__init__(f"capability unavailable: {capability}")
        self.capability = capability
"""Chuẩn hóa receipt trả về từ các lệnh Control API.

Chỉ giữ trường allowlist (không bao giờ chuyển tiếp trường lạ như giá trị secret)
và luôn đặt status 'accepted' vì receipt chỉ xác nhận đã nhận, khác trạng thái thực thi (CT-API mục 2).
"""

from __future__ import annotations

from typing import Any, Mapping

ACCEPTED_STATUS = "accepted"
RECEIPT_FIELDS = (
    "receipt_id",
    "command_id",
    "disposition",
    "operation_id",
    "resource_ref",
    "accepted_at",
    "current_revision",
)


def accepted_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa receipt thành trạng thái 'accepted' và lọc các trường nhạy cảm."""
    body = {name: receipt.get(name) for name in RECEIPT_FIELDS}
    body["status"] = ACCEPTED_STATUS
    return body
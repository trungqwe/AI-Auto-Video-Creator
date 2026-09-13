"""TST-M1-P3-005, 006, 007: OAuth lifecycle, rate limiting backoff, and secret boundary proof."""
from pathlib import Path
import pytest
from m1proof.oauth_broker import DesktopOAuthSession
from m1proof.drive_adapter import DriveStorageAdapter

CANARY_SECRET = "AIzaSyD-TESTCANARYSECRETKEY123456789012"

def test_tst_m1_p3_005_token_lifecycle_and_adr0009_desktop_boundary():
    """TST-M1-P3-005:
    Desktop tuân thủ ADR-0009: không lưu trữ refresh token dài hạn không mã hóa trên ổ đĩa;
    Xử lý thu hồi (revoke) xóa sạch session trong bộ nhớ.
    """
    dummy_secrets = Path("Credentials/dummy_secret.json")
    session = DesktopOAuthSession(dummy_secrets)

    # Khởi tạo mặc định phải tuân thủ ADR-0009
    assert session.violates_adr0009_boundary() is False

    # Nếu cấu hình cố ý đánh dấu lưu refresh token dài hạn trên desktop -> vi phạm
    session.set_credentials(None, persist_refresh_token_on_desktop=True)
    assert session.violates_adr0009_boundary() is True

    # Khôi phục session hợp lệ và thực hiện revoke
    session.set_credentials(None, persist_refresh_token_on_desktop=False)
    assert session.revoke() is True
    assert session.get_credentials() is None


def test_tst_m1_p3_006_rate_limit_http_429_bounded_backoff():
    """TST-M1-P3-006:
    Gặp HTTP 429 (Rate limit / Quota exceeded) kích hoạt bounded backoff tăng dần,
    không tạo retry storm; dừng lại khi vượt ngưỡng max_retries.
    """
    adapter = DriveStorageAdapter()
    
    # Tính toán backoff cho các lần thử: lần 1, lần 2, lần 3
    delay_1 = adapter.calculate_exponential_backoff(attempt=1, base_delay=0.1, max_delay=1.0)
    delay_2 = adapter.calculate_exponential_backoff(attempt=2, base_delay=0.1, max_delay=1.0)
    delay_3 = adapter.calculate_exponential_backoff(attempt=3, base_delay=0.1, max_delay=1.0)

    assert delay_1 == 0.1
    assert delay_2 == 0.2
    assert delay_3 == 0.4

    # Trần max_delay được tôn trọng, không tăng vô hạn
    delay_capped = adapter.calculate_exponential_backoff(attempt=10, base_delay=0.1, max_delay=1.0)
    assert delay_capped == 1.0

    # Thử upload với trạng thái 429 giả lập
    res = adapter.simulate_rate_limited_upload(fail_until_attempt=2, max_retries=3)
    assert res["status"] == "SUCCESS_AFTER_BACKOFF"
    assert res["attempts_used"] == 2

    # Thử upload với số lần 429 vượt quá max_retries
    with pytest.raises(RuntimeError) as exc_info:
        adapter.simulate_rate_limited_upload(fail_until_attempt=5, max_retries=3)
    assert "RATE_LIMIT_EXCEEDED" in str(exc_info.value)


def test_tst_m1_p3_007_secret_boundary_scanning_in_logs_and_receipts():
    """TST-M1-P3-007:
    Không có token, private key hoặc secret canary nào bị lộ trong log hoặc receipt của Drive adapter.
    """
    adapter = DriveStorageAdapter()
    
    # Tạo receipt bình thường có kèm data
    receipt = adapter.resumable_upload(
        file_id="clean-fid-1",
        name="test.mp4",
        content=b"NORMAL_CONTENT",
    )

    # Quét receipt không chứa canary pattern
    receipt_str = str(receipt)
    assert CANARY_SECRET not in receipt_str

    # Thử truyền dữ liệu chứa canary secret vào adapter logger
    sanitized_log = adapter.log_safe_message(f"Upload failed with token: {CANARY_SECRET}")
    assert CANARY_SECRET not in sanitized_log
    assert "[REDACTED_SECRET]" in sanitized_log

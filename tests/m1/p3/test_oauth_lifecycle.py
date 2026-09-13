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


def test_tst_m1_p3_008_adr0009_token_placement_and_desktop_disk_audit(tmp_path: Path):
    """TST-M1-P3-008:
    Broker (J/Cloud-side) sở hữu refresh token dài hạn.
    Desktop client CHỈ nhận short-lived access token trong memory (creds.refresh_token is None).
    Desktop disk tuyệt đối không chứa refresh token plaintext.
    """
    from m1proof.oauth_broker import CloudTokenBroker, DesktopOAuthClient, audit_desktop_token_storage

    broker = CloudTokenBroker()
    broker.store_refresh_token(account_id="acc-1", refresh_token="1//MOCK_LONG_TERM_REFRESH_TOKEN_12345")

    desktop = DesktopOAuthClient(broker=broker, account_id="acc-1")
    creds = desktop.acquire_short_lived_credentials()

    # Ranh giới bộ nhớ: Desktop có access token nhưng KHÔNG có refresh token
    assert creds is not None
    assert creds.token is not None
    assert creds.refresh_token is None

    # Ranh giới ổ đĩa: Kiểm tra toàn bộ desktop scratch/tmp dir không có refresh token
    clean_dir = tmp_path / "desktop_workspace"
    clean_dir.mkdir()
    (clean_dir / "app_config.json").write_text('{"mode": "desktop_worker"}', encoding="utf-8")
    
    findings = audit_desktop_token_storage(clean_dir)
    assert findings == []

    # Giả lập vi phạm: ghi refresh token plaintext ra đĩa desktop
    violation_file = clean_dir / "leaked_token.json"
    violation_file.write_text('{"refresh_token": "1//LEAKED_PLAINTEXT_REFRESH_TOKEN"}', encoding="utf-8")
    findings_violation = audit_desktop_token_storage(clean_dir)
    assert len(findings_violation) >= 1
    assert any("refresh_token" in f["pattern"] for f in findings_violation)


def test_tst_m1_p3_009_desktop_refresh_delegation_to_broker():
    """TST-M1-P3-009:
    Desktop không có refresh token nên không thể tự refresh.
    Khi access token hết hạn, Desktop phải ủy quyền qua Broker để nhận token mới.
    """
    from m1proof.oauth_broker import CloudTokenBroker, DesktopOAuthClient
    from google.auth.exceptions import RefreshError

    broker = CloudTokenBroker()
    broker.store_refresh_token(account_id="acc-2", refresh_token="1//MOCK_REFRESH_TOKEN_ABC")

    desktop = DesktopOAuthClient(broker=broker, account_id="acc-2")
    creds = desktop.acquire_short_lived_credentials()

    # 1. Desktop tự refresh trực tiếp phải thất bại do thiếu refresh_token
    with pytest.raises(RefreshError, match="The credentials do not contain the necessary fields need to refresh the access token"):
        from google.auth.transport.requests import Request
        creds.refresh(Request())

    # 2. Desktop xin refresh qua Broker -> Thành công, nhận access token mới
    new_creds = desktop.refresh_via_broker()
    assert new_creds.token is not None
    assert new_creds.token != creds.token  # Token mới được sinh ra
    assert new_creds.refresh_token is None  # Vẫn không tiết lộ refresh token cho desktop


def test_tst_m1_p3_010_token_revocation_boundary():
    """TST-M1-P3-010:
    Revoke vô hiệu hóa token trên Broker và xóa sạch session trên Desktop.
    """
    from m1proof.oauth_broker import CloudTokenBroker, DesktopOAuthClient

    broker = CloudTokenBroker()
    broker.store_refresh_token(account_id="acc-3", refresh_token="1//MOCK_REFRESH_TOKEN_XYZ")

    desktop = DesktopOAuthClient(broker=broker, account_id="acc-3")
    desktop.acquire_short_lived_credentials()
    assert desktop.has_active_credentials() is True

    # Thực hiện thu hồi quyền (Revoke)
    revoked = desktop.revoke()
    assert revoked is True
    assert desktop.has_active_credentials() is False
    assert broker.has_refresh_token("acc-3") is False


def test_tst_m1_p3_011_insufficient_scope_classification():
    """TST-M1-P3-011:
    Scope không đủ quyền (ví dụ chỉ có metadata read) bị Drive adapter phân loại
    thành INSUFFICIENT_SCOPE_ERROR và không retry mù.
    """
    adapter = DriveStorageAdapter()
    result = adapter.classify_oauth_error(
        status_code=403,
        error_body={"error": {"code": 403, "message": "The request is missing a valid API key or scope.", "status": "PERMISSION_DENIED"}}
    )
    assert result["classification"] == "INSUFFICIENT_SCOPE_ERROR"
    assert result["retryable"] is False


def test_tst_m1_p3_012_broker_http_process_boundary():
    """TST-M1-P3-012 (R4-01):
    Desktop client giao tiếp với CloudTokenBroker qua HTTP IPC process boundary.
    Desktop chỉ nhận ephemeral access capability trong bộ nhớ (creds.refresh_token is None).
    Desktop không sở hữu refresh token; refresh lifecycle được ủy quyền qua broker HTTP endpoint.
    """
    from m1proof.broker_service import run_broker_http_server, CloudTokenBrokerServer
    from m1proof.oauth_broker import DesktopOAuthClient

    server = CloudTokenBrokerServer(host="127.0.0.1", port=18088)
    server.start()
    try:
        server.register_account("acc-http-test", refresh_token="1//MOCK_REAL_REFRESH_TOKEN_PROC_BOUNDARY")
        desktop = DesktopOAuthClient(broker_url=f"http://127.0.0.1:{server.port}", account_id="acc-http-test")

        # 1. Desktop xin access token qua HTTP
        creds = desktop.acquire_short_lived_credentials()
        assert creds.token is not None
        assert creds.refresh_token is None  # Ranh giới: Desktop không nhận refresh token

        # 2. Desktop xin refresh qua HTTP broker
        new_creds = desktop.refresh_via_broker()
        assert new_creds.token is not None
        assert new_creds.token != creds.token
        assert new_creds.refresh_token is None

        # 3. Desktop revoke qua HTTP broker
        revoked = desktop.revoke()
        assert revoked is True
        assert desktop.has_active_credentials() is False
    finally:
        server.stop()

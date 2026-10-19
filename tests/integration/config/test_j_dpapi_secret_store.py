"""J-17: DpapiSecretStore trên desktop (INV-012).

coveredIds: TST-SEC-INV-012, QR-SEC-008
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

if sys.platform != 'win32':
    pytest.skip('DpapiSecretStore dùng DPAPI của Windows; bỏ qua trên nền tảng không phải win32', allow_module_level=True)

from controlplane.application.config_security.secret_update import UpdateSecretService
from controlplane.infrastructure.security import dpapi_secret_store
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.secret_redaction import SecretValue
from controlplane.security.broker import CredentialBroker, SecretLifetimeExpiredError, UnauthorizedSecretAccessError
from controlplane.security.dpapi import DPAPIDecryptionError, DPAPIError, dpapi_decrypt

C_SECRET = 'CANARY-J17-SECRET-5e1d9c0b'
C_SECRET2 = 'CANARY-J17-ROTATED-7a2f4b93'
REF = 'ws-1/acct-1/primary'
TRAVERSAL_REFS = ['../../escape/ref', '..\\..\\escape\\ref', 'a/../../b', 'C:/Windows/System32/x']
ENTROPY = b'J17-TEST-ENTROPY'


def _digest(ref: str) -> str:
    return hashlib.sha256(ref.encode('utf-8')).hexdigest()


def _store(tmp_path: Path, entropy: bytes | None = None) -> DpapiSecretStore:
    return DpapiSecretStore(tmp_path / 'store', entropy)


def _files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob('*') if p.is_file()]


def _blob(root: Path) -> bytes:
    return b''.join(p.read_bytes() for p in _files(root))


# Nhóm A: put, tệp, thoát root


def test_put_writes_v1_and_v2_in_sha256_directory(tmp_path: Path) -> None:
    """Put REF hai lần ghi v1.bin và v2.bin trong thư mục sha256."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    assert store.put(REF, SecretValue(C_SECRET)) == 1
    assert store.put(REF, SecretValue(C_SECRET2)) == 2
    subdirs = [p for p in root.iterdir() if p.is_dir()]
    assert len(subdirs) == 1
    assert subdirs[0].name == _digest(REF)
    names = sorted(p.name for p in subdirs[0].iterdir() if p.is_file())
    assert names == ['v1.bin', 'v2.bin']


def test_no_tmp_file_remains_after_put(tmp_path: Path) -> None:
    """Sau hai lần put không còn tệp .tmp nào dưới root."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    store.put(REF, SecretValue(C_SECRET2))
    assert not any('.tmp' in p.name for p in _files(root))


def test_no_canary_bytes_or_names_under_root(tmp_path: Path) -> None:
    """Canary và secret_ref không xuất hiện trong nội dung hay tên tệp dưới root."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    store.put(REF, SecretValue(C_SECRET2))
    store.revoke(REF, 2)
    blob = _blob(root)
    assert C_SECRET.encode('utf-8') not in blob
    assert C_SECRET2.encode('utf-8') not in blob
    for p in _files(root):
        rel = str(p.relative_to(root))
        assert REF not in rel
        if p.suffix == '.bin':
            assert p.stat().st_size > 0


@pytest.mark.parametrize('ref', TRAVERSAL_REFS)
def test_traversal_refs_stay_under_root(tmp_path: Path, ref: str) -> None:
    """Secret ref chứa traversal luôn nằm hoàn toàn trong thư mục root."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    assert store.put(ref, SecretValue(C_SECRET)) == 1
    assert list(tmp_path.iterdir()) == [root]
    files = _files(root)
    assert len(files) == 1
    for p in files:
        assert p.resolve().is_relative_to(root.resolve())
    subdirs = [p for p in root.iterdir() if p.is_dir()]
    assert len(subdirs) == 1
    assert subdirs[0].name == _digest(ref)


def test_root_is_created_on_first_put(tmp_path: Path) -> None:
    """Thư mục root được tự động tạo ở lần put đầu tiên."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    assert not root.exists()
    store.put(REF, SecretValue(C_SECRET))
    assert root.exists()
    assert root.is_dir()


def test_distinct_refs_have_independent_versions(tmp_path: Path) -> None:
    """Các secret_ref khác nhau có version độc lập và thư mục riêng."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    assert store.put('r1', SecretValue(C_SECRET)) == 1
    assert store.put('r1', SecretValue(C_SECRET2)) == 2
    assert store.put('r2', SecretValue(C_SECRET)) == 1
    assert store.current_version('r1') == 2
    assert store.current_version('r2') == 1
    subdirs = sorted(p.name for p in root.iterdir() if p.is_dir())
    assert subdirs == sorted([_digest('r1'), _digest('r2')])


def test_put_rejects_non_secret_value_and_creates_no_file(tmp_path: Path) -> None:
    """Put từ chối giá trị không phải SecretValue hoặc rỗng và không tạo tệp."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    for bad in ('plain', b'raw', None, SecretValue(12345)):
        with pytest.raises(TypeError):
            store.put(REF, bad)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        store.put(REF, SecretValue(''))
    assert _files(root) == []


def test_blank_or_non_str_ref_is_rejected(tmp_path: Path) -> None:
    """Ref rỗng hoặc không phải str bị từ chối cho put, current_version, revoke."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    for blank in ('', '   '):
        with pytest.raises(ValueError):
            store.put(blank, SecretValue(C_SECRET))
        with pytest.raises(ValueError):
            store.current_version(blank)
        with pytest.raises(ValueError):
            store.revoke(blank, 1)
    for non_str in (None, 7):
        with pytest.raises(TypeError):
            store.put(non_str, SecretValue(C_SECRET))  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            store.current_version(non_str)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            store.revoke(non_str, 1)  # type: ignore[arg-type]
    assert _files(root) == []


# Nhóm B: revoke, current_version


def test_current_version_is_none_for_unknown_ref(tmp_path: Path) -> None:
    """Current_version trả None cho secret_ref chưa tồn tại."""
    store = _store(tmp_path)
    assert store.current_version('chưa-có') is None


def test_current_version_tracks_latest_put(tmp_path: Path) -> None:
    """Current_version theo dõi version mới nhất sau mỗi lần put."""
    store = _store(tmp_path)
    assert store.put(REF, SecretValue(C_SECRET)) == 1
    assert store.current_version(REF) == 1
    assert store.put(REF, SecretValue(C_SECRET2)) == 2
    assert store.current_version(REF) == 2


def test_revoke_removes_ciphertext_and_writes_marker(tmp_path: Path) -> None:
    """Revoke xóa tệp ciphertext và ghi marker vN.revoked."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    store.put(REF, SecretValue(C_SECRET2))
    store.revoke(REF, 2)
    ref_dir = root / _digest(REF)
    assert not (ref_dir / 'v2.bin').exists()
    assert (ref_dir / 'v2.revoked').exists()
    assert (ref_dir / 'v1.bin').exists()
    assert store.current_version(REF) == 1
    store.revoke(REF, 1)
    assert store.current_version(REF) is None


def test_revoke_is_idempotent(tmp_path: Path) -> None:
    """Revoke nhiều lần cho cùng một version là idempotent."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    store.revoke(REF, 1)
    store.revoke(REF, 1)
    ref_dir = root / _digest(REF)
    assert not (ref_dir / 'v1.bin').exists()
    revoked_markers = list(ref_dir.glob('v1.revoked'))
    assert len(revoked_markers) == 1


def test_revoke_unknown_version_raises_value_error(tmp_path: Path) -> None:
    """Revoke version chưa có raise ValueError."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    with pytest.raises(ValueError):
        store.revoke('chưa-có', 1)
    store.put(REF, SecretValue(C_SECRET))
    with pytest.raises(ValueError):
        store.revoke(REF, 9)


def test_revoke_rejects_bad_version_types(tmp_path: Path) -> None:
    """Revoke từ chối version sai kiểu hoặc nhỏ hơn 1."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    for bad_type in (True, '1', 1.0):
        with pytest.raises(TypeError):
            store.revoke(REF, bad_type)  # type: ignore[arg-type]
    for bad_val in (0, -1):
        with pytest.raises(ValueError):
            store.revoke(REF, bad_val)


def test_version_is_never_reused_after_revoke(tmp_path: Path) -> None:
    """Version không bao giờ được tái sử dụng sau khi bị revoke."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    assert store.put(REF, SecretValue(C_SECRET)) == 1
    assert store.put(REF, SecretValue(C_SECRET2)) == 2
    store.revoke(REF, 2)
    assert store.put(REF, SecretValue(C_SECRET)) == 3
    assert store.current_version(REF) == 3
    ref_dir = root / _digest(REF)
    assert (ref_dir / 'v3.bin').exists()
    assert (ref_dir / 'v2.revoked').exists()


def test_failed_encrypt_leaves_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mã hóa thất bại không để lại tệp nào dưới root."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)

    def _broken_encrypt(*_args: object, **_kwargs: object) -> bytes:
        raise DPAPIError('boom')

    monkeypatch.setattr(dpapi_secret_store, 'dpapi_encrypt', _broken_encrypt)
    with pytest.raises(DPAPIError):
        store.put(REF, SecretValue(C_SECRET))
    assert _files(root) == []
    assert store.current_version(REF) is None


def test_failed_replace_leaves_no_tmp_and_no_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lỗi os.replace không để lại tệp .tmp và không tạo version."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)

    def _broken_replace(_src: object, _dst: object) -> None:
        raise OSError('disk')

    monkeypatch.setattr(dpapi_secret_store.os, 'replace', _broken_replace)
    with pytest.raises(OSError) as exc_info:
        store.put(REF, SecretValue(C_SECRET))
    assert _files(root) == []
    assert store.current_version(REF) is None
    assert C_SECRET not in str(exc_info.value)

    monkeypatch.undo()
    assert store.put(REF, SecretValue(C_SECRET)) == 1


# Nhóm C: export_vault + CredentialBroker


def test_export_vault_returns_ciphertext_not_plaintext(tmp_path: Path) -> None:
    """Export_vault trả bản mã bytes khớp với tệp trên đĩa và không bao giờ là plaintext."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    vault = store.export_vault([REF])
    assert list(vault) == [REF]
    assert isinstance(vault[REF], bytes)
    assert vault[REF] != C_SECRET.encode('utf-8')
    assert C_SECRET.encode('utf-8') not in vault[REF]
    expected_bytes = (root / _digest(REF) / 'v1.bin').read_bytes()
    assert vault[REF] == expected_bytes


def test_export_vault_then_broker_returns_value_in_scope_and_expires(tmp_path: Path) -> None:
    """Export_vault cấp vault cho CredentialBroker giải mã đúng và hết hạn sau scope."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    vault = store.export_vault([REF])
    broker = CredentialBroker(vault=vault)
    with broker.acquire_secret(REF) as handle:
        assert handle.get_secret_value() == C_SECRET
        assert handle.is_expired() is False
    assert handle.is_expired() is True
    with pytest.raises(SecretLifetimeExpiredError):
        handle.get_secret_value()


def test_export_vault_uses_current_version_after_rotation(tmp_path: Path) -> None:
    """Export_vault sử dụng version hiện hành sau khi rotate secret."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    store.put(REF, SecretValue(C_SECRET2))
    broker = CredentialBroker(vault=store.export_vault([REF]))
    with broker.acquire_secret(REF) as handle:
        assert handle.get_secret_value() == C_SECRET2


def test_export_after_revoking_latest_falls_back_to_previous_version(tmp_path: Path) -> None:
    """Export_vault chuyển về version trước sau khi revoke version mới nhất."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    store.put(REF, SecretValue(C_SECRET2))
    store.revoke(REF, 2)
    broker = CredentialBroker(vault=store.export_vault([REF]))
    with broker.acquire_secret(REF) as handle:
        assert handle.get_secret_value() == C_SECRET


def test_revoked_secret_is_not_exported_and_broker_denies(tmp_path: Path) -> None:
    """Secret đã bị revoke hoàn toàn không được export và broker từ chối truy cập."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    store.revoke(REF, 1)
    vault = store.export_vault([REF])
    assert vault == {}
    broker = CredentialBroker(vault=vault)
    with pytest.raises(UnauthorizedSecretAccessError):
        with broker.acquire_secret(REF):
            pass


def test_export_vault_omits_unknown_refs_and_keeps_requested_keys(tmp_path: Path) -> None:
    """Export_vault bỏ qua ref chưa có và trả đúng tập khóa hợp lệ."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put('r1', SecretValue(C_SECRET))
    vault = store.export_vault(['r1', 'chưa-có', 'r1'])
    assert set(vault.keys()) == {'r1'}


def test_export_vault_rejects_bare_string(tmp_path: Path) -> None:
    """Export_vault từ chối chuỗi đơn lẻ để tránh lặp qua từng ký tự."""
    store = _store(tmp_path)
    with pytest.raises(TypeError):
        store.export_vault(REF)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        store.export_vault(b'x')  # type: ignore[arg-type]


def test_export_vault_accepts_generator(tmp_path: Path) -> None:
    """Export_vault chấp nhận iterable generator."""
    store = _store(tmp_path)
    store.put(REF, SecretValue(C_SECRET))
    vault = store.export_vault(r for r in [REF])
    assert REF in vault


def test_traversal_ref_round_trips_through_export_and_broker(tmp_path: Path) -> None:
    """Secret ref chứa traversal vẫn export và giải mã thành công qua broker."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    ref = TRAVERSAL_REFS[0]
    store.put(ref, SecretValue(C_SECRET))
    broker = CredentialBroker(vault=store.export_vault([ref]))
    with broker.acquire_secret(ref) as handle:
        assert handle.get_secret_value() == C_SECRET


# Nhóm D: tích hợp J-10, entropy, tĩnh


def test_store_has_no_read_api_and_matches_constructor_signature(tmp_path: Path) -> None:
    """Store không có API đọc plaintext và constructor đúng chữ ký."""
    store = _store(tmp_path)
    for name in ('get', 'read', 'reveal', 'get_secret', 'decrypt', 'export'):
        assert not hasattr(store, name)
    sig = inspect.signature(DpapiSecretStore.__init__)
    assert list(sig.parameters.keys()) == ['self', 'root', 'entropy']
    assert sig.parameters['entropy'].default is None
    for method in ('put', 'revoke', 'current_version', 'export_vault'):
        assert callable(getattr(store, method))


def test_update_secret_service_uses_the_store(tmp_path: Path) -> None:
    """Tích hợp với UpdateSecretService của J-10 ghi version và audit không lộ secret."""
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)

    class _Sink:
        def __init__(self) -> None:
            self.records: list[object] = []

        def append(self, record: object) -> None:
            self.records.append(record)

    sink = _Sink()
    service = UpdateSecretService(
        store,
        sink,  # type: ignore[arg-type]
        lambda: datetime(2026, 10, 20, 1, 2, 3, tzinfo=timezone.utc),
    )
    r1 = service.update('ws', 'acct', 'alias', SecretValue(C_SECRET), 'actor-1', 'corr-1')
    assert r1.version == 1
    assert r1.secret_ref == 'ws/acct/alias'
    assert r1.fingerprint == 'v1'

    r2 = service.update('ws', 'acct', 'alias', SecretValue(C_SECRET), 'actor-1', 'corr-1')
    assert r2.version == 2
    assert r2.secret_ref == 'ws/acct/alias'
    assert r2.fingerprint == 'v2'

    assert len(sink.records) == 2
    assert C_SECRET not in repr(r1)
    assert C_SECRET not in repr(r2)
    assert C_SECRET not in repr(sink.records)
    assert C_SECRET not in _blob(root).decode('latin-1')


def test_entropy_binds_ciphertext(tmp_path: Path) -> None:
    """Entropy bổ sung ràng buộc bản mã và đòi đúng entropy để giải mã.

    Ghi chú: broker mặc định giải mã không entropy nên vault dùng với CredentialBroker chỉ nạp được khi entropy=None.
    """
    root = tmp_path / 'store'
    store = DpapiSecretStore(root, entropy=ENTROPY)
    store.put(REF, SecretValue(C_SECRET))
    vault = store.export_vault([REF])
    ct = vault[REF]
    assert dpapi_decrypt(ct, ENTROPY) == C_SECRET.encode('utf-8')
    with pytest.raises(DPAPIDecryptionError):
        dpapi_decrypt(ct)
    assert C_SECRET.encode('utf-8') not in _blob(root)


def test_operations_emit_no_log_records(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Các thao tác không ghi bất kỳ log record nào."""
    caplog.set_level('DEBUG')
    root = tmp_path / 'store'
    store = DpapiSecretStore(root)
    store.put(REF, SecretValue(C_SECRET))
    store.export_vault([REF])
    store.revoke(REF, 1)
    assert C_SECRET not in caplog.text
    assert len(caplog.records) == 0


def test_module_has_no_network_or_logging_imports() -> None:
    """Module không import mạng hay logging và không import tiền tố src."""
    tree = ast.parse(Path(dpapi_secret_store.__file__).read_text(encoding='utf-8'))
    imported_root_modules: set[str] = set()
    from_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_root_modules.add(alias.name.split('.')[0])
                assert not alias.name.startswith('src')
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_root_modules.add(node.module.split('.')[0])
                from_modules.add(node.module)
                assert not node.module.startswith('src')
    forbidden = {'socket', 'ssl', 'http', 'urllib', 'requests', 'httpx', 'aiohttp', 'logging', 'subprocess'}
    assert imported_root_modules.isdisjoint(forbidden)
    assert 'controlplane.security.dpapi' in from_modules


def test_module_declares_covered_ids_and_skip_guard() -> None:
    """Tệp test khai báo coveredIds và guard skip module-level trên non-win32."""
    text = Path(__file__).read_text(encoding='utf-8')
    assert 'coveredIds: TST-SEC-INV-012, QR-SEC-008' in text
    assert 'pytest.skip(' in text

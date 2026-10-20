# Báo cáo Thực thi: CP-2C-M2-REGRESSION

## 1. Phạm vi Thực thi

- **Mục tiêu:** Sửa hai phép kiểm `test_tst_m2_p9_001_m2_manifest_and_gate_evaluation` và `test_tst_m2_p9_005_migration_full_down_up_cycle_disposable_db` cùng hàm `validate_manifest_dict` và các hằng/helper trong `tests/m2/test_p9_m2_exit_gate.py`.
- **Hằng ghim:** `M2_ACCEPTED_SHA = "1aedf8fc2c1e90b34b5db8f0c01e28c8003f781e"` do Control cung cấp (OI-CV-01, xác nhận ngày 20/10/2026), là mốc kỹ thuật cho CP-2C, không phải phê duyệt checkpoint M2 của người dùng.
- **Ranh giới:** Không sửa `docs/milestones/**/evidence/**` hay `manifest.json` của M2. Không sửa bất kỳ test nào khác trong `tests/m2`.

## 2. Thiết kế và Triển khai

1. **Hằng số và Helper:**
   - Khai báo `M2_ACCEPTED_SHA = "1aedf8fc2c1e90b34b5db8f0c01e28c8003f781e"`.
   - Khai báo `BASELINE_PREFIXES = ("src/controlplane/ui/dist/", "tests/m2/e2e/")`.
   - Khai báo `MIGRATIONS_REL_DIR = "src/controlplane/infrastructure/db/migrations"`.
   - Tuple `PINNED_MIGRATION_STEMS` gồm đúng 8 migration ban đầu.
   - Hàm helper `git_show_bytes(commit: str, rel_path: str) -> bytes` gọi qua danh sách đối số `subprocess.run(["git", "show", f"{commit}:{rel_path}"], cwd=REPO_ROOT, capture_output=True, check=False)`, không dùng `shell=True`. Nếu sha không hợp lệ hoặc blob không tồn tại thì raise `ValueError`.

2. **Chữ ký và Logic `validate_manifest_dict`:**
   - Nhận thêm keyword-only parameters: `baseline_commit: str | None = None, baseline_prefixes: tuple[str, ...] = ()`.
   - Khi `baseline_commit` khác None và artifact có tiền tố thuộc `baseline_prefixes`, lấy `actual_hash` từ `git_show_bytes(baseline_commit, clean_rel)`.
   - Với artifact khác, đối chiếu với tệp trên cây làm việc (đĩa).
   - Nếu `baseline_commit` là None, hành vi cũ được giữ nguyên hoàn toàn.

3. **Phép kiểm 001 (`test_tst_m2_p9_001_m2_manifest_and_gate_evaluation`):**
   - Đọc `live_manifest` và gọi `validate_manifest_dict(live_manifest, REPO_ROOT, baseline_commit=M2_ACCEPTED_SHA, baseline_prefixes=BASELINE_PREFIXES)`.
   - Bổ sung các ca âm:
     - Tamper hash artifact thuộc từng tiền tố trong `BASELINE_PREFIXES` -> kiểm tra raise `ValueError("Tampered artifacts detected")`.
     - Baseline commit không tồn tại (`'f' * 40`) -> kiểm tra raise `ValueError("Baseline blob unavailable")` (không skip).
     - Baseline commit sai định dạng (`'not-a-sha'`) -> kiểm tra raise `ValueError("not a 40-hex SHA")`.

4. **Phép kiểm 005 (`test_tst_m2_p9_005_migration_full_down_up_cycle_disposable_db`):**
   - Đếm động số lượng tệp migration forward `N = len(forward_files)`.
   - Xác nhận `expected_count >= len(PINNED_MIGRATION_STEMS)`.
   - Đối chiếu SHA-256 của toàn bộ 16 tệp (forward và rollback của 8 migration đầu) với blob tại `M2_ACCEPTED_SHA`.
   - Xác nhận cả hai chu kỳ `migrate_up` đều tạo đúng `expected_count` phiên bản liên tục `[1..N]` và tên migration khớp 8 migration ghim.

## 3. Bằng chứng RED (Bước 5)

Trước khi thêm logic so khớp baseline trong thân `validate_manifest_dict` (chỉ mới stub chữ ký), chạy lệnh kiểm:
- Lệnh: `python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider`
- Exit code: 1
- Kết quả: `F.....` (1 failed, 5 passed). Phép 005 xanh hoàn toàn (16 tệp migration khớp 100% blob tại `M2_ACCEPTED_SHA`, database disposable vòng lặp down/up đạt). Phép 001 thất bại vì chưa có nhánh kiểm tra baseline:
```text
F.....                                                                   [100%]
================================== FAILURES ===================================
_____________ test_tst_m2_p9_001_m2_manifest_and_gate_evaluation ______________

    def test_tst_m2_p9_001_m2_manifest_and_gate_evaluation() -> None:
        """RED Oracle #1: Live manifest must exist and validate all packages; missing artifact fails closed."""
        live_manifest = json.loads(LIVE_MANIFEST_PATH.read_text(encoding="utf-8"))
>       res = validate_manifest_dict(
            live_manifest,
            REPO_ROOT,
            baseline_commit=M2_ACCEPTED_SHA,
            baseline_prefixes=BASELINE_PREFIXES,
        )

tests\m2\test_p9_m2_exit_gate.py:134: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

manifest = {'schema_version': 'm2_manifest_v1', 'milestone': 'M2', 'timestamp_utc': '2026-10-07T20:53:10.066104+00:00', 'version_lock': {'python': '3.13.15', 'postgresql': '18.6', 'node': '22.17.0'}, ...}
project_root = WindowsPath('C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/lane-cp-2c-m2-regression')
baseline_commit = '1aedf8fc2c1e90b34b5db8f0c01e28c8003f781e'
baseline_prefixes = ('src/controlplane/ui/dist/', 'tests/m2/e2e/')

    def validate_manifest_dict(
        manifest: dict[str, Any],
        project_root: Path,
        *,
        baseline_commit: str | None = None,
        baseline_prefixes: tuple[str, ...] = (),
    ) -> dict[str, Any]:
...
ValueError: Tampered artifacts detected (hash mismatch): [{'path': 'docs/milestones/m2-control-plane/evidence/m2-p9/status.md', 'expected': '8b661a195b2cf7bd95a1f99df80d936d6f4b720dd9c6d6ca2639b469abcdfcea', 'actual': '07c488279b992fee027c2c11febfd4727af6c4a294453a41312fabdb446cb3da'}, {'path': 'tests/m2/e2e/operations-sse.spec.ts', 'expected': 'ca0d4bbd903c370e23e39f6362292e831da4ee222c7e54e62d850157b676164b', 'actual': 'f653f6bf6d38f354b746e65fc9f9654c3f1f86cb1a26a78b08698ade34c6835b'}, {'path': 'tests/m2/e2e/safe-error-modal.spec.ts', 'expected': '17580534afc440c516080f1a90144c4f7ff7e1c66ebeffb2c403412d0347057a', 'actual': 'fd552f5dbf47ec670146c3912de77a0f96e530faad40c5cf92168ab4d104b1a0'}]
```

## 4. Kết quả Thực thi Bước 7 và Trạng thái BLOCKED

Sau khi cài đặt logic baseline ở Bước 6, chạy lại kiểm thử ở Bước 7 theo chỉ đạo của Orchestrator:
- Lệnh: `python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider`
- Exit code: 1
- Đầu ra thực tế:
```text
F.....                                                                   [100%]
================================== FAILURES ===================================
_____________ test_tst_m2_p9_001_m2_manifest_and_gate_evaluation ______________

    def test_tst_m2_p9_001_m2_manifest_and_gate_evaluation() -> None:
        """RED Oracle #1: Live manifest must exist and validate all packages; missing artifact fails closed."""
        live_manifest = json.loads(LIVE_MANIFEST_PATH.read_text(encoding="utf-8"))
>       res = validate_manifest_dict(
            live_manifest,
            REPO_ROOT,
            baseline_commit=M2_ACCEPTED_SHA,
            baseline_prefixes=BASELINE_PREFIXES,
        )

tests\m2\test_p9_m2_exit_gate.py:137: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

manifest = {'schema_version': 'm2_manifest_v1', 'milestone': 'M2', 'timestamp_utc': '2026-10-07T20:53:10.066104+00:00', 'version_lock': {'python': '3.13.15', 'postgresql': '18.6', 'node': '22.17.0'}, ...}
project_root = WindowsPath('C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/lane-cp-2c-m2-regression')
baseline_commit = '1aedf8fc2c1e90b34b5db8f0c01e28c8003f781e'
baseline_prefixes = ('src/controlplane/ui/dist/', 'tests/m2/e2e/')

    def validate_manifest_dict(
        manifest: dict[str, Any],
        project_root: Path,
        *,
        baseline_commit: str | None = None,
        baseline_prefixes: tuple[str, ...] = (),
    ) -> dict[str, Any]:
...
E           ValueError: Tampered artifacts detected (hash mismatch): [{'path': 'docs/milestones/m2-control-plane/evidence/m2-p9/status.md', 'expected': '8b661a195b2cf7bd95a1f99df80d936d6f4b720dd9c6d6ca2639b469abcdfcea', 'actual': '07c488279b992fee027c2c11febfd4727af6c4a294453a41312fabdb446cb3da'}, {'path': 'tests/m2/e2e/operations-sse.spec.ts', 'expected': 'ca0d4bbd903c370e23e39f6362292e831da4ee222c7e54e62d850157b676164b', 'actual': 'f653f6bf6d38f354b746e65fc9f9654c3f1f86cb1a26a78b08698ade34c6835b'}, {'path': 'tests/m2/e2e/safe-error-modal.spec.ts', 'expected': '17580534afc440c516080f1a90144c4f7ff7e1c66ebeffb2c403412d0347057a', 'actual': 'fd552f5dbf47ec670146c3912de77a0f96e530faad40c5cf92168ab4d104b1a0'}]

tests\m2\test_p9_m2_exit_gate.py:112: ValueError
=========================== short test summary info ===========================
FAILED tests/m2/test_p9_m2_exit_gate.py::test_tst_m2_p9_001_m2_manifest_and_gate_evaluation
1 failed, 5 passed in 1.59s
```

### Nguyên nhân kỹ thuật cụ thể:
1. **Lệch hash tests/m2/e2e:**
   - Trong `docs/milestones/m2-control-plane/evidence/manifest.json`:
     - `tests/m2/e2e/operations-sse.spec.ts` có kích thước `7372 bytes` (CRLF), SHA-256: `ca0d4bbd903c370e23e39f6362292e831da4ee222c7e54e62d850157b676164b`.
     - `tests/m2/e2e/safe-error-modal.spec.ts` có kích thước `3650 bytes` (CRLF), SHA-256: `17580534afc440c516080f1a90144c4f7ff7e1c66ebeffb2c403412d0347057a`.
   - Trong git database tại commit `M2_ACCEPTED_SHA` (`1aedf8fc2c1e90b34b5db8f0c01e28c8003f781e`):
     - Git blob `operations-sse.spec.ts` được lưu với định dạng LF (do `.gitattributes` có `* text=auto eol=lf`), kích thước `7218 bytes`, SHA-256: `f653f6bf6d38f354b746e65fc9f9654c3f1f86cb1a26a78b08698ade34c6835b`.
     - Git blob `safe-error-modal.spec.ts` được lưu với định dạng LF, kích thước `3566 bytes`, SHA-256: `fd552f5dbf47ec670146c3912de77a0f96e530faad40c5cf92168ab4d104b1a0`.
   - Do đó lệnh `git show 1aedf8fc2c1e90b34b5db8f0c01e28c8003f781e:<path>` xuất ra blob LF thô, không khớp hash CRLF được ghi trong `manifest.json`.

2. **Lệch hash artifact trên đĩa:**
   - `docs/milestones/m2-control-plane/evidence/m2-p9/status.md` trên đĩa có kích thước `1789 bytes` (LF, SHA-256 `07c488279b992fee027c2c11febfd4727af6c4a294453a41312fabdb446cb3da`), trong khi `manifest.json` ghi nhận phiên bản CRLF `1821 bytes` (`8b661a195b2cf7bd95a1f99df80d936d6f4b720dd9c6d6ca2639b469abcdfcea`).

### Tuân thủ Chỉ đạo Bước 7:
Chỉ thị Bước 7 của Orchestrator nêu rõ:
> *"Nếu đỏ vì hash ui/dist hoặc tests/m2/e2e không khớp blob baseline thì dừng, gửi BLOCKED kèm output, không sửa manifest.json hay tệp M2."*

Do đó, Worker dừng lại tại Bước 7, không tự ý sửa đổi `manifest.json` hay bất kỳ tệp nào ngoài `owned paths`, và gửi báo cáo `BLOCKED` về Control/Orchestrator để xử lý việc đồng bộ hash baseline.

## 5. Danh sách tệp thay đổi

1. `tests/m2/test_p9_m2_exit_gate.py` (owned path)
2. `docs/delivery-evidence/cp-2c-m2-regression/report.md` (owned path)

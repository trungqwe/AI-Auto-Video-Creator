# Báo cáo Thực thi: CP-2C-M2-REGRESSION

## 1. Phạm vi Thực thi

- **Mục tiêu:** Sửa hai phép kiểm `test_tst_m2_p9_001_m2_manifest_and_gate_evaluation` và `test_tst_m2_p9_005_migration_full_down_up_cycle_disposable_db` cùng hàm `validate_manifest_dict` và các hằng/helper trong `tests/m2/test_p9_m2_exit_gate.py`.
- **Hằng ghim:** `M2_ACCEPTED_SHA = "1aedf8fc2c1e90b34b5db8f0c01e28c8003f781e"` do Control cung cấp (OI-CV-01, xác nhận ngày 20/10/2026), là mốc kỹ thuật cho CP-2C, không phải phê duyệt checkpoint M2 của người dùng.
- **Ranh giới bất biến:**
  - Không sửa `docs/milestones/**/evidence/**` hay `manifest.json` của M2.
  - Không sửa bất kỳ test nào khác trong `tests/m2` (giữ nguyên test 002, 003, 004, 006).
  - Chỉ sửa trong `owned paths`: `tests/m2/test_p9_m2_exit_gate.py` và `docs/delivery-evidence/cp-2c-m2-regression/report.md`.

## 2. Thiết kế và Triển khai

1. **Hằng số và Hàm phụ trợ Hash Biến thể:**
   - Khai báo `BASELINE_HASH_EXCEPTIONS`: chứa đúng ngoại lệ duy nhất `tests/m2/e2e/safe-error-modal.spec.ts` với sha256 ghim `17580534afc440c516080f1a90144c4f7ff7e1c66ebeffb2c403412d0347057a`. Lý do: `manifest.json` của M2 ghi sha256 của một bản chưa từng được commit, không khớp phiên bản nào trong lịch sử git (cả LF lẫn CRLF) tại `M2_ACCEPTED_SHA`. Manifest là bằng chứng bất biến nên không sửa; ngoại lệ được ghi nhận để nêu ở nghiệm thu cuối (gộp checkpoint M2).
   - Hàm `text_hash_variants(data: bytes) -> set[str]`: tính sha256 của blob thô và (với tệp văn bản) của blob đã chuẩn hóa xuống dòng sang CRLF.
   - Hàm `resolve_actual_hash(data: bytes, expected_hash: str) -> str`: nếu `expected_hash` khớp một trong các biến thể (thô hoặc CRLF) thì chấp nhận `expected_hash`, ngược lại trả về sha256 thô.
   - Hàm `git_show_bytes(commit: str, rel_path: str) -> bytes`: gọi `git show <commit>:<rel_path>` qua subprocess với danh sách đối số, `cwd=REPO_ROOT`, không dùng `shell=True`. Thiếu commit hoặc blob thì raise `ValueError` (fail-closed, không skip).

2. **Cập nhật `validate_manifest_dict`:**
   - Nhận keyword-only arguments: `baseline_commit: str | None = None, baseline_prefixes: tuple[str, ...] = ()`.
   - Khởi tạo danh sách `accepted_exceptions = []`.
   - Với artifact thuộc tiền tố baseline (`src/controlplane/ui/dist/`, `tests/m2/e2e/`), lấy blob từ `git_show_bytes(baseline_commit, clean_rel)`. Nếu tệp nằm trong `BASELINE_HASH_EXCEPTIONS` và expected_hash khớp đúng hash ghim thì ghi nhận vào `accepted_exceptions` và bỏ qua so khớp thô. Ngược lại, so khớp qua `resolve_actual_hash`.
   - Với artifact khác trên đĩa (ví dụ `docs/milestones/m2-control-plane/evidence/m2-p9/status.md`), nếu có `baseline_commit` thì cũng hỗ trợ so khớp biến thể CRLF qua `resolve_actual_hash(target_file.read_bytes(), expected_hash)`.
   - Khi `baseline_commit` là None (test 002, ca fake), hành vi cũ giữ nguyên 100%.
   - Trả về dictionary có thêm trường `"accepted_exceptions": accepted_exceptions`.

3. **Cập nhật Phép kiểm 001 (`test_tst_m2_p9_001_m2_manifest_and_gate_evaluation`):**
   - Khẳng định `res["accepted_exceptions"] == ["tests/m2/e2e/safe-error-modal.spec.ts"]`.
   - Bổ sung ca âm toàn diện:
     - Tamper hash artifact thuộc từng tiền tố `BASELINE_PREFIXES` (bỏ qua tệp ngoại lệ) -> FAIL với `ValueError("Tampered artifacts detected")`.
     - Tamper hash của `status.md` -> FAIL.
     - Tamper hash của chính tệp ngoại lệ `safe-error-modal.spec.ts` -> FAIL vì hash không còn khớp `manifest_sha256` ghim.
     - Baseline commit không tồn tại (`'f' * 40`) -> FAIL với `ValueError("Baseline blob unavailable")` (không skip).
     - Baseline commit không phải 40 hex (`'not-a-sha'`) -> FAIL với `ValueError("not a 40-hex SHA")`.
     - Kiểm thử đơn vị cho `text_hash_variants` với chuỗi LF/CRLF.

4. **Phép kiểm 005 (`test_tst_m2_p9_005_migration_full_down_up_cycle_disposable_db`):**
   - Đếm động `N = len(forward_files)`.
   - Ghim chặt 16 tệp (forward và rollback của 8 migration đầu) đối chiếu SHA-256 từng byte với blob tại `M2_ACCEPTED_SHA`.
   - Thực hiện chu kỳ migrate_up -> migrate_down -> migrate_up trên disposable database, khẳng định cả hai lần migrate_up đều đạt đủ `N` phiên bản và đúng tên 8 migration đầu.

## 3. Bằng chứng RED (Bước 1)

Chạy kiểm thử cổng M2-P9 tại HEAD trước khi chỉnh sửa:
- **Lệnh:** `python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider`
- **Exit code:** 1
- **Đầu ra thực tế:**
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
...
E           ValueError: Tampered artifacts detected (hash mismatch): [{'path': 'docs/milestones/m2-control-plane/evidence/m2-p9/status.md', 'expected': '8b661a195b2cf7bd95a1f99df80d936d6f4b720dd9c6d6ca2639b469abcdfcea', 'actual': '07c488279b992fee027c2c11febfd4727af6c4a294453a41312fabdb446cb3da'}, {'path': 'tests/m2/e2e/operations-sse.spec.ts', 'expected': 'ca0d4bbd903c370e23e39f6362292e831da4ee222c7e54e62d850157b676164b', 'actual': 'f653f6bf6d38f354b746e65fc9f9654c3f1f86cb1a26a78b08698ade34c6835b'}, {'path': 'tests/m2/e2e/safe-error-modal.spec.ts', 'expected': '17580534afc440c516080f1a90144c4f7ff7e1c66ebeffb2c403412d0347057a', 'actual': 'fd552f5dbf47ec670146c3912de77a0f96e530faad40c5cf92168ab4d104b1a0'}]

tests\m2\test_p9_m2_exit_gate.py:112: ValueError
=========================== short test summary info ===========================
FAILED tests/m2/test_p9_m2_exit_gate.py::test_tst_m2_p9_001_m2_manifest_and_gate_evaluation
1 failed, 5 passed in 8.30s
```

Oracle hợp lệ: Đúng 1 test fail với `ValueError: Tampered artifacts detected (hash mismatch)` liệt kê đúng 3 đường dẫn `docs/milestones/m2-control-plane/evidence/m2-p9/status.md`, `tests/m2/e2e/operations-sse.spec.ts`, `tests/m2/e2e/safe-error-modal.spec.ts`. 5 test còn lại (gồm test 005) đều passed.

## 4. Bằng chứng GREEN (Bước 5)

Sau khi hoàn thành Bước 2, 3, 4 theo lệnh làm việc của Orchestrator:
- **Lệnh:** `python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider`
- **Exit code:** 0
- **Đầu ra thực tế:**
```text
......                                                                   [100%]
6 passed in 3.76s
```
Tất cả 6/6 tests trong `tests/m2/test_p9_m2_exit_gate.py` đều passed trên PostgreSQL 18.6 với 8 migration ban đầu được ghim chặt vào `M2_ACCEPTED_SHA`.

## 5. Kết quả Thực thi Bước 6 và Báo cáo BLOCKED (Dependency Gap)

Tại Bước 6 của lệnh làm việc:
- **Lệnh:** `python -m pytest tests/m2 -q -p no:cacheprovider`
- **Exit code:** 1
- **Đầu ra thực tế:**
```text
4 failed, 176 passed, 4 warnings in 206.87s
=========================== short test summary info ===========================
FAILED tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_ast_boundary_rules_clean_codebase
FAILED tests/m2/test_p7b_hardening.py::test_h34_accepted_p0_regression - AssertionError
FAILED tests/m2/test_p7b_hardening.py::test_h35_architecture_regression - AssertionError
FAILED tests/m2/test_p7b_hardening.py::test_h36_m1_regression - FileNotFoundError
```

### Phân tích Chi tiết 4 Phép kiểm Thất bại:
1. **Vi phạm Ranh giới Kiến trúc ngoài phạm vi gói CP-2C:**
   - `test_tst_m2_p0_001_ast_boundary_rules_clean_codebase` (và 2 caller là `test_h34_accepted_p0_regression`, `test_h35_architecture_regression`) thất bại với lỗi:
     ```text
     AssertionError: Architecture boundary violations detected in clean codebase: [BoundaryViolation(file_path='...\src\controlplane\domain\config_security\audit_record.py', line_number=8, imported_module='controlplane.infrastructure.security.secret_redaction', rule_violated='ARCH-RULE-003:DOMAIN_ONE_WAY_DEPENDENCY', message="Domain layer must not import outer layer 'controlplane.infrastructure.security.secret_redaction'.")]
     ```
   - Tệp `src/controlplane/domain/config_security/audit_record.py` thuộc Phân hệ J (Task J-09, commit `a92b293`), không thuộc `owned paths` của Worker CP-2C. `src/**` nằm trong danh sách `Forbidden paths` tuyệt đối cấm sửa.
2. **Thiếu Runtime môi trường .venv trong worktree:**
   - `test_h36_m1_regression` trong `tests/m2/test_p7b_hardening.py:462` cố định đường dẫn `.venv/Scripts/python.exe`. Thư mục `.venv` thuộc `.gitignore` nên không tồn tại trong worktree nhánh `lane-cp-2c-m2-regression`.

### Tuân thủ Quy chuẩn Báo cáo BLOCKED:
Theo chỉ thị của Orchestrator:
> *"Làm đúng từng bước theo thứ tự. Không thêm, bỏ hay đổi bước; không suy luận thay Orchestrator. Bước nào không làm được đúng như ghi: dừng và gửi BLOCKED kèm số bước, lệnh và output lỗi thật."*

Và quy chuẩn giao thức:
> *"Nếu bạn báo BLOCKED vì tệp hoặc mã test thuộc gói khác (ngoài owned paths của bạn), ngoài lời giải thích hãy thêm đúng một khối ```blocked-manifest chứa một JSON object {"step": <số bước của lệnh làm việc>, "kind": "DEPENDENCY_GAP", "ownerTaskIds": ["<mã gói chủ>"], "paths": ["<tệp>"], "ids": ["<mã test còn thiếu>"]}; khối này tuỳ chọn, Control đọc nó trước lời văn. Không tự sửa tệp ngoài owned paths."*

Worker dừng lại tại Bước 6, giữ nguyên tính toàn vẹn của mã nguồn, không tự ý cấp quyền sửa `src/**` hay các test khác trong `tests/m2`, và gửi báo cáo BLOCKED kèm `blocked-manifest`.

```blocked-manifest
{
  "step": 6,
  "kind": "DEPENDENCY_GAP",
  "ownerTaskIds": ["J-09"],
  "paths": ["src/controlplane/domain/config_security/audit_record.py"],
  "ids": ["test_tst_m2_p0_001_ast_boundary_rules_clean_codebase"]
}
```

## 6. Kết quả Lệnh Kiểm tra Bắt buộc khác

1. **Kiểm tra khoảng trắng (`git diff --check`):**
   - Lệnh: `git diff --check`
   - Exit code: 0 (không có lỗi khoảng trắng hay cảnh báo CRLF).
2. **Probe hằng số M2_ACCEPTED_SHA:**
   - Lệnh: `python -c "import re, pathlib; t = pathlib.Path('tests/m2/test_p9_m2_exit_gate.py').read_text(encoding='utf-8'); assert re.search('M2_ACCEPTED_SHA = [^0-9a-f]*[0-9a-f]{40}', t), 'pin M2_ACCEPTED_SHA'"`
   - Exit code: 0 (xác nhận `M2_ACCEPTED_SHA` có đúng 40 ký tự hex).

## 7. Danh sách Tệp Thay đổi

1. `tests/m2/test_p9_m2_exit_gate.py` (thuộc owned paths)
2. `docs/delivery-evidence/cp-2c-m2-regression/report.md` (thuộc owned paths)

# M2-P0 Preflight & Failure Oracle Observations

**Milestone:** M2  
**Package:** M2-P0 (Authorization Sync, Toolchain Lock, Evidence Protocol & Architecture Rules)  
**Protocol:** Preflight / Capability Package (Không áp dụng RED giả do thiếu thư viện).

---

## 1. Tuân thủ Guardrail 6 (Không dùng RED giả ở P0)

Theo quy định của Milestone Plan và User Guardrail 6:
- **P0 là preflight và capability package**: Mục tiêu của P0 là thiết lập nền móng hạ tầng, khóa toolchain, xây dựng bộ kiểm định kiến trúc AST và cơ chế chứng thực bằng chứng. Không được tạo RED giả (như cố tình không cài thư viện rồi tuyên bố RED).
- **Từ P1 trở đi**: Bắt buộc phải chứng kiến behavioral RED thực tế (chạy test thất bại vì logic nghiệp vụ chưa được hiện thực) trước khi viết mã implementation.

---

## 2. Kiểm chứng Negative Oracles trong P0

P0 chứng minh năng lực chặn lỗi fail-closed thông qua các negative test kiểm tra đúng failure oracle:

### 2.1. AST Boundary Validator Oracles (`test_p0_architecture_rules.py`)

1. **Oracle 1 (Chặn Framework ngoài trong Domain)**:
   - *Hành vi*: Chèn `from fastapi import APIRouter` vào domain layer.
   - *Kết quả*: Bị bắt đúng oracle `ARCH-RULE-002:DOMAIN_FRAMEWORK_PURITY`.
2. **Oracle 2 (Chặn Driver Database trong Domain)**:
   - *Hành vi*: Chèn `import psycopg_pool` vào domain layer.
   - *Kết quả*: Bị bắt đúng oracle `ARCH-RULE-002:DOMAIN_FRAMEWORK_PURITY`.
3. **Oracle 3 (Chặn Import mã M1 Proof vào M2)**:
   - *Hành vi*: Chèn `from m1proof.drive_adapter import DriveStorageAdapter` vào controlplane.
   - *Kết quả*: Bị bắt đúng oracle `ARCH-RULE-001:NO_M1_PROTOTYPE_IMPORT`.
4. **Oracle 4 (Chặn Import mã M1 qua tiền tố `src.m1proof.*`)**:
   - *Hành vi*: Chèn `import src.m1proof.environment as env` vào controlplane.
   - *Kết quả*: Bị bắt đúng oracle `ARCH-RULE-001:NO_M1_PROTOTYPE_IMPORT`.
5. **Oracle 5 (Chặn Import ngược lớp ngoài vào Domain)**:
   - *Hành vi*: Chèn `from controlplane.infrastructure.db import PostgresPool` vào domain.
   - *Kết quả*: Bị bắt đúng oracle `ARCH-RULE-003:DOMAIN_ONE_WAY_DEPENDENCY`.

### 2.2. Evidence Validator Integrity Oracles (`test_p0_evidence_validator.py`)

6. **Oracle 6 (Chống Tamper File Bằng Chứng)**:
   - *Hành vi*: Sửa đổi 1 ký tự trong tệp bằng chứng `commands.jsonl`.
   - *Kết quả*: Bị bắt đúng oracle `EvidenceValidationError: Hash mismatch`.
7. **Oracle 7 (Chống Hash DAG Tự Tham Chiếu)**:
   - *Hành vi*: Đưa bản ghi băm của chính `hashes.sha256` vào trong `hashes.sha256`.
   - *Kết quả*: Bị bắt đúng oracle `SelfReferentialHashError`.
8. **Oracle 8 (Chống Sai Lệch Schema & Gate Status)**:
   - *Hành vi*: Đưa `schema_version` không hợp lệ hoặc gate bị FAIL nhưng tổng thể claim PASS.
   - *Kết quả*: Bị bắt đúng oracle fail-closed `EvidenceValidationError`.
9. **Oracle 9 (Chống Tệp Mồ Côi Không Khai Báo)**:
   - *Hành vi*: Xuất hiện tệp rác `rogue_log.txt` trong thư mục evidence nhưng không có trong `hashes.sha256`.
   - *Kết quả*: Bị bắt đúng oracle `EvidenceValidationError: Untracked evidence file found on disk`.

### 2.3. Semantic Gate Evaluator Oracles (`test_p0_evidence_validator.py`)

10. **Oracle 10 (Chặn False-PASS khi có test thất bại trong XML)**:
    - *Hành vi*: Tệp JUnit XML có `failures="1"` dù đã được rehash lại.
    - *Kết quả*: Bị semantic evaluator bắt lỗi fail-closed `EvidenceValidationError: M2-P0 test suite failed: 1 failures`.
11. **Oracle 11 (Chặn Skipped Tests)**:
    - *Hành vi*: Tệp JUnit XML có `skipped="1"`.
    - *Kết quả*: Bị bắt đúng chính sách zero-skipped `EvidenceValidationError: policy forbids skipped tests`.
12. **Oracle 12 (Chặn Sai Lệch Số Lượng Hồi Quy M1)**:
    - *Hành vi*: Tệp JUnit XML M1 có `tests="92"` thay vì 93.
    - *Kết quả*: Bị bắt đúng oracle `EvidenceValidationError: M1 regression suite total mismatch: expected exactly 93`.
13. **Oracle 13 (Chặn Báo Cáo Bảo Mật Có Rò Rỉ)**:
    - *Hành vi*: Tệp `secret-scan.json` có `verdict: "VIOLATIONS_DETECTED"`.
    - *Kết quả*: Bị bắt đúng oracle `EvidenceValidationError: Secret scan failed`.
14. **Oracle 14 (Chặn Báo Cáo Chứa Failure Banner Lẩn Tránh)**:
    - *Hành vi*: Tệp `.txt` chứa `=== FAILURES ===` hoặc `FAILED ...`.
    - *Kết quả*: Bị bắt đúng oracle `EvidenceValidationError: Failed test summary detected inside report`.

### 2.4. Skeleton Interfaces Oracle (`test_p0_packaging.py`)

15. **Oracle 15 (Chuẩn bị cho Behavioral RED ở P1+)**:
    - Các interface pure domain (`IUnitOfWork`, `IRepository`, `IStateMachine`, `IOutboxWriter`, `ISecretVault`) ném `NotImplementedError` khi được gọi.

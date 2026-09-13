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

Thay vì RED giả, P0 chứng minh năng lực chặn lỗi fail-closed thông qua các negative test kiểm tra đúng failure oracle:

### 2.1. AST Boundary Validator Oracles (`test_p0_architecture_rules.py`)

1. **Oracle 1 (Chặn Framework ngoài trong Domain)**:
   - *Hành vi kiểm tra*: Chèn `from fastapi import APIRouter` vào tệp trong domain layer.
   - *Kết quả Oracle*: Thất bại đúng oracle `ARCH-RULE-002:DOMAIN_FRAMEWORK_PURITY` với thông điệp *"Domain layer must not import external framework/driver 'fastapi'"*.
2. **Oracle 2 (Chặn Driver Database trong Domain)**:
   - *Hành vi kiểm tra*: Chèn `import psycopg_pool` vào domain.
   - *Kết quả Oracle*: Thất bại đúng oracle `ARCH-RULE-002:DOMAIN_FRAMEWORK_PURITY`.
3. **Oracle 3 (Chặn Import mã M1 Proof vào M2)**:
   - *Hành vi kiểm tra*: Chèn `from m1proof.drive_adapter import DriveStorageAdapter` vào bất kỳ module nào của controlplane.
   - *Kết quả Oracle*: Thất bại đúng oracle `ARCH-RULE-001:NO_M1_PROTOTYPE_IMPORT` với thông điệp *"Import of M1 prototype module 'm1proof' is forbidden in production M2 code"*.
4. **Oracle 4 (Chặn Import ngược lớp ngoài vào Domain)**:
   - *Hành vi kiểm tra*: Chèn `from controlplane.infrastructure.db import PostgresPool` vào domain.
   - *Kết quả Oracle*: Thất bại đúng oracle `ARCH-RULE-003:DOMAIN_ONE_WAY_DEPENDENCY`.

### 2.2. Evidence Validator Oracles (`test_p0_evidence_validator.py`)

1. **Oracle 5 (Chống Tamper File Bằng Chứng)**:
   - *Hành vi kiểm tra*: Sửa đổi 1 ký tự trong tệp bằng chứng `test_report.txt`.
   - *Kết quả Oracle*: Thất bại đúng oracle `EvidenceValidationError` với thông điệp *"Hash mismatch for 'test_report.txt'"*.
2. **Oracle 6 (Chống Hash DAG Tự Tham Chiếu)**:
   - *Hành vi kiểm tra*: Đưa bản ghi băm của chính `hashes.sha256` vào trong tệp `hashes.sha256`.
   - *Kết quả Oracle*: Thất bại đúng oracle `SelfReferentialHashError` với thông điệp *"Self-referential hash detected: 'hashes.sha256' cannot hash itself"*.
3. **Oracle 7 (Chống Sai Lệch Schema & Gate Status)**:
   - *Hành vi kiểm tra*: Cố tình đưa `schema_version` lạ hoặc gate bị FAIL nhưng tổng thể claim PASS.
   - *Kết quả Oracle*: Thất bại đúng oracle fail-closed `EvidenceValidationError`.
4. **Oracle 8 (Chống Tệp Mồ Côi Không Khai Báo)**:
   - *Hành vi kiểm tra*: Xuất hiện tệp rác `rogue_log.txt` trong thư mục evidence nhưng không có trong `hashes.sha256`.
   - *Kết quả Oracle*: Thất bại đúng oracle `EvidenceValidationError: Untracked evidence file found on disk`.

### 2.3. Skeleton Interfaces Oracle (`test_p0_packaging.py`)

- **Oracle 9 (Chuẩn bị cho Behavioral RED ở P1+)**:
  - Các interface pure domain (`IUnitOfWork`, `IRepository`, `IStateMachine`, `IOutboxWriter`, `ISecretVault`) ném `NotImplementedError` khi được gọi.
  - Điều này đảm bảo khi P1+ viết test trước, test sẽ thất bại vì `NotImplementedError` của domain abstraction thay vì `ModuleNotFoundError` do thiếu tệp/module.

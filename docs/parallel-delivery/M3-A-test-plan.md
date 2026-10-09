# Kế Hoạch Kiểm Thử Toàn Diện: M3-A (Comprehensive Test Plan Specification)

> **Mã gói (Package ID):** `M3-A`
> **Trạng thái:** `planned_test_strategy`
> **Tài liệu nguồn:** `docs/10-test-strategy.md` (Mục 10, 34), `docs/modules/a-source-collection/implementation-plan.md`
> **Phương pháp luận:** Test-First / Behavioral TDD (`SPEC` -> `PLAN` -> `RED` -> `IMPLEMENT` -> `GREEN` -> `VERIFY` -> `EVIDENCE`)

---

## 1. Nguyên Tắc & Kỷ Luật Kiểm Thử Bắt Buộc

1. **Chứng kiến hỏng hóc hành vi (Behavioral RED First):**
   - Trước khi viết mã sản phẩm, mỗi ca kiểm thử phải chạy và thất bại vì vi phạm assertions nghiệp vụ/hợp đồng (`Behavioral RED`), tuyệt đối không chấp nhận RED do lỗi import, lỗi cấu hình môi trường, hoặc thiếu binary (`Invalid Setup Failure`).
2. **Kiểm thử trên PostgreSQL Disposable Thật (Real DB Isolation):**
   - Không dùng SQLite hay in-memory mock để thay thế PostgreSQL cho các kiểm thử liên quan đến transaction, isolation, concurrency, outbox, hoặc unique indexes.
   - Mỗi test function hoặc test suite sử dụng database tạm thời riêng biệt (`function-scoped disposable database`), tự động dọn dẹp sạch sẽ sau khi chạy xong (`0 orphan databases`).
3. **Cấm dùng Mock để vượt qua cổng kiểm tra (No Mocking Gateways):**
   - Tuyệt đối không mock kiểm tra SSRF, kiểm tra mã băm SHA-256 toàn vẹn, hoặc quy trình ký chữ ký số out-of-process.
4. **Kỷ luật Targeted Test (Zero Waste Execution):**
   - Trong quá trình phát triển và sửa lỗi, chỉ chạy đúng lệnh kiểm thử mục tiêu được chỉ định; chỉ chạy toàn bộ bộ kiểm thử tích hợp khi bước vào giai đoạn tổng hợp hồ sơ evidence.

---

## 2. Danh Mục Các Test Oracle Bắt Buộc (Mandatory Test Oracles)

### 2.1. Nhóm đóng hậu kiểm AUD2 (Theo docs/10-test-strategy.md Mục 34)

| Mã Kiểm Thử | Tình huống kích hoạt (Scenario) | Hành vi mong đợi & Oracle bắt buộc (Expected Oracle) |
|---|---|---|
| `TST-COL-END-001` | Lần thử (attempt) retryable cuối cùng gặp lỗi; có hoặc không có package hợp lệ đã commit trước đó | Không tạo attempt giả; chuyển `COMPLETED_PARTIAL` nếu đã có package, ngược lại `FAILED_FINAL` với lý do `RETRY_EXHAUSTED`; bảo toàn nguyên vẹn checkpoint và dữ liệu đã commit |
| `TST-COL-END-002` | Nguồn bị vô hiệu hóa (`DISABLED`) hoặc xóa (`REMOVED_TOMBSTONE`) khi lượt quét đang ở `SCHEDULED`, `RUNNING` hoặc `WAITING_RETRY` | Dừng ngay lập tức, không fetch tiếp; chuyển `COMPLETED_PARTIAL` hoặc `FAILED_FINAL` theo bảng CT-STATE-002 với lý do `SOURCE_INACTIVE`; khi khôi phục nguồn không mở lại run đã terminal |
| `TST-COL-END-003` | Reconcile xác nhận kết quả retryable / full success / partial success / final error với ngân sách còn hoặc hết | Chuyển trạng thái chính xác theo ma trận CT-STATE-002; không lặp lại tác động phụ (side effect); đính kèm đầy đủ bằng chứng đối soát |
| `TST-COL-END-004` | Kết quả tác động phụ vẫn không xác định (`OUTCOME_UNKNOWN`) khi đã hết hạn hạn chót reconcile | Duy trì trạng thái `WAITING_RECONCILIATION` có ghi log cảnh báo; tuyệt đối không retry tác động phụ mù quáng và không tự ý kết luận thành công; chỉ tiếp tục khi có bằng chứng |
| `TST-SRC-RACE-001` | Candidate ở trạng thái `READY`, nguồn active/disabled cùng định danh canonical được đăng ký trước | Trả về `MATCHED_EXISTING` gắn với ref hiện có; không tạo thực thể `Source` mới; đảm bảo tính nhất quán giữa candidate, receipt và outbox |
| `TST-SRC-RACE-002` | Hai tiến trình đồng thời: một đăng ký candidate, một xóa nguồn (`RemoveSource`) với cả 2 thứ tự commit | `SourceTombstone` cuối cùng được bảo toàn; nếu lệnh xóa thắng thì candidate bị chuyển sang `BLOCKED_TOMBSTONE`; không xảy ra tình trạng nguồn hồi sinh trái phép |
| `TST-SRC-RACE-003` | Candidate đạt `READY` nhưng policy thay đổi cấm, thiếu policy hoặc expected revision bị cũ | Trả về tương ứng: `REJECTED`, `READY` (với `WAITING_POLICY`), hoặc `REVISION_CONFLICT`; không tự động kích hoạt nguồn, không phát event resolved khi còn chờ |
| `TST-SRC-RACE-004` | Giao dịch đăng ký commit thành công nhưng bị mất gói tin ACK; client gửi lại cùng idempotency key | Trả về đúng receipt và disposition đã commit trước đó; không tạo thêm thực thể `Source` hay outbox event trùng lặp; nếu thay đổi payload thì báo lỗi idempotency conflict |
| `TST-COL-PKG-001` | Payload thiếu trường bắt buộc (ID, source ref, run ref, provenance chain); client lặp lại payload sai | Bị từ chối ngay tại biên A với `VALIDATION_ERROR`; không chuyển giao sang B; ghi nhận quan sát lỗi với correlation ID an toàn, không giả mạo provenance |
| `TST-COL-PKG-002` | Trích xuất gặp lỗi hoặc nội dung bài viết rỗng (`empty text`) nhưng schema và provenance đầy đủ | Lưu package với `content_eligibility = "incomplete"` kèm lý do; B tiếp nhận và trả `REJECTED_INCOMPLETE`; không tính vào tin mới |
| `TST-COL-PKG-003` | Cấu hình nguồn yêu cầu bắt buộc title vs cấu hình nguồn cho phép thiếu title | Thẩm định theo đúng cấu hình loại nguồn trong revision policy; không mặc định nguồn mạng xã hội phải có title riêng |
| `TST-COL-PKG-004` | Thiếu policy loại nguồn; fetch thất bại khi chưa tạo được package | Báo lỗi `INPUT_NOT_READY` khi thiếu policy; fetch thất bại chỉ ghi nhận quan sát lượt quét và xử lý run theo CT-STATE-002, không tạo package rác |

---

### 2.2. Nhóm Bất Biến Cốt Lõi (Core Invariants & Rules)

| Mã Kiểm Thử | Invariant / Rule | Mục tiêu kiểm chứng | Oracle bắt buộc |
|---|---|---|---|
| `TST-INT-INV-015` | `INV-015` | Xóa nguồn rồi auto-discovery quét lại đúng URL đó | Nguồn vẫn ở trạng thái `REMOVED_TOMBSTONE`; auto-discovery bị chặn, trả về `BLOCKED_TOMBSTONE` |
| `TST-SEC-INV-020` | `INV-020` | Dữ liệu bài viết/HTML chứa câu lệnh độc hại giả mạo hướng dẫn hệ thống (prompt injection) | Không làm thay đổi chính sách thu thập, không kích hoạt tool ẩn, dữ liệu được escape/sanitize an toàn |
| `TST-RULE-A001` | `A-RULE-001` | Mỗi thao tác sửa đổi nguồn phải có idempotency key và expected revision | Trùng idempotency key trả lại receipt cũ; sai expected revision trả về `REVISION_CONFLICT` |
| `TST-RULE-A004` | `A-RULE-004` | Một nguồn quét định kỳ tối đa 1 lần trong cùng `business_date` | Lượt quét thứ hai trong ngày với purpose `periodic` bị từ chối với lý do `ALREADY_RUN_TODAY` |
| `TST-RULE-A013` | `A-RULE-013` | Fetch HTTP(S) bắt buộc kiểm tra SSRF tại mỗi bước chuyển hướng (redirect) | Chặn ngay lập tức nếu redirect trả về IP nội bộ hoặc loopback |
| `TST-RULE-A014` | `A-RULE-014` | Secret / token không bao giờ xuất hiện trong log, event payload hoặc database | Kiểm tra bộ lọc dữ liệu nhạy cảm (sanitizer) lọc sạch 100% header Authorization, token |

---

### 2.3. Nhóm Phòng Thủ Biên Bảo Mật Thu Thập (SSRF Defense Suite)

| Mã Kiểm Thử | Tình huống tấn công (Attack Vector) | Oracle bảo mật bắt buộc |
|---|---|---|
| `TST-SEC-SSRF-001` | URL chứa địa chỉ Loopback (`http://127.0.0.1`, `http://localhost`, `http://[::1]`) | Ném lỗi `SSRFSecurityViolationError`, từ chối kết nối fail-closed |
| `TST-SEC-SSRF-002` | URL chứa dải mạng riêng tư RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) | Ném lỗi `SSRFSecurityViolationError`, không gửi request ra card mạng |
| `TST-SEC-SSRF-003` | URL trỏ tới dịch vụ metadata máy chủ đám mây (`http://169.254.169.254/...`) | Ném lỗi `SSRFSecurityViolationError`, ghi log vi phạm bảo mật |
| `TST-SEC-SSRF-004` | Tấn công DNS Rebinding (DNS trả IP công cộng ở lần phân giải đầu nhưng trả IP nội bộ ở lần hai) | Thẩm tra IP ngay trước khi mở socket kết nối thực sự (`pre-connect IP check`), chặn đóng kết nối |
| `TST-SEC-SSRF-005` | Giao thức không phải HTTP/HTTPS (`file:///etc/passwd`, `gopher://`, `ftp://`) | Ném lỗi `UnsupportedSchemeError`, chỉ cho phép `http` và `https` |

---

## 3. Ma Trận Phân Rã Gói Công Việc (Work Packages A0..A7)

```
A0 (Contract & Fixtures)
 |-- A1 (Source Domain & Lifecycle)
 |-- A2 (CollectionRun & Checkpoint Core)
 |-- A3 (SSRF Fetch & Adapters) -> A4 (Extraction & Package Builder)
                                    |-- A5 (Periodic Tier Workflow)
                                         |-- A6 (Supplemental & Auto-Discovery)
                                              |-- A7 (UI & Hardening)
```

| Gói | Nội dung thực thi chính | Tệp tin kiểm thử mục tiêu (Targeted Test File) | Lệnh chạy kiểm thử mục tiêu |
|---|---|---|---|
| `A0` | Đóng contract, validate schema JSON và chuẩn bị fixtures | `tests/unit/collection/test_a0_contract_fixtures.py` | `python -m unittest tests/unit/collection/test_a0_contract_fixtures.py` |
| `A1` | Source aggregate, vòng đời CT-STATE-001, idempotency | `tests/unit/collection/test_a1_source_lifecycle.py` | `python -m unittest tests/unit/collection/test_a1_source_lifecycle.py` |
| `A2` | CollectionRun, attempt, checkpoint CT-STATE-002 | `tests/unit/collection/test_a2_run_checkpoints.py` | `python -m unittest tests/unit/collection/test_a2_run_checkpoints.py` |
| `A3` | SSRF guard, HTTP client, RSS parser adapter | `tests/unit/collection/test_a3_secure_fetch.py` | `python -m unittest tests/unit/collection/test_a3_secure_fetch.py` |
| `A4` | Trích xuất nội dung, Package builder, Outbox handoff | `tests/unit/collection/test_a4_package_builder.py` | `python -m unittest tests/unit/collection/test_a4_package_builder.py` |
| `A5` | Lập lịch cycle định kỳ, điều phối theo Tier | `tests/unit/collection/test_a5_tier_workflow.py` | `python -m unittest tests/unit/collection/test_a5_tier_workflow.py` |
| `A6` | Tìm kiếm bổ sung, auto-discovery candidate CT-STATE-002A | `tests/unit/collection/test_a6_candidate_discovery.py` | `python -m unittest tests/unit/collection/test_a6_candidate_discovery.py` |
| `A7` | Projections cho UI Admin, SSE stream, hardening & gate G06 | `tests/integration/collection/test_a7_acceptance_gate.py` | `python -m unittest tests/integration/collection/test_a7_acceptance_gate.py` |

> **Lưu ý ranh giới đường dẫn kiểm thử & Gate thực thi (Test Paths & Execution Gate):**
> - Toàn bộ các đường dẫn kiểm thử `tests/unit/collection/**` và `tests/integration/collection/**` nêu trên là **proposed paths (đường dẫn đề xuất)**, hiện tại **chưa có ownership entry** trong `docs/parallel-delivery/ownership-and-locks.yaml`.
> - Khóa `LOCK-SRC-SOURCE-INGESTION` bảo vệ các đường dẫn này là **proposed lock chưa được đăng ký** trong registry. Tuyệt đối không dùng `LOCK-SRC-INGESTION` của Module B thay thế và không tự sửa registry.
> - Kế hoạch kiểm thử này xác lập ở trạng thái `planned_test_strategy`, **không khẳng định package đã khóa đầy đủ ranh giới**.
> - Việc tạo tệp kiểm thử và thực thi các gói công việc implementation A0..A7 bị **BLOCKED** fail-closed cho đến khi:
>   1. Gate `GATE-M3-A-OWNERSHIP-LOCK` được Control / Authority Owner phê duyệt và đăng ký chính thức vào `ownership-and-locks.yaml`.
>   2. Checkpoint `USER-CKPT-M3` được Người dùng phê duyệt chính thức mở Milestone M3.

---

## 4. Kiểm Thử Hồi Quy Toàn Hệ Thống (Regression Invariants)

Bất kỳ thay đổi nào trong Phân hệ A cũng bắt buộc phải vượt qua các bài kiểm thử hồi quy:
1. **Kiểm tra hồi quy Milestone M1:**
   - Đảm bảo 93/93 bài test M1 đạt `PASS` (`93 passed, 0 skipped`).
2. **Kiểm tra hồi quy Milestone M2:**
   - Bộ kiểm thử `tests/m2/**` đạt `PASS`.
   - Admin UI build sạch sẽ, không có trailing whitespace.
3. **Quét dữ liệu nhạy cảm (Secret Scanner):**
   - Không chứa bất kỳ khóa bí mật, private key, token dạng plain-text nào trong mã nguồn và dữ liệu test fixture.

---

## 5. Bằng Chứng Nghiệm Thu Cần Sinh Ra (Required Evidence Artifacts)

Khi một gói công việc hoặc toàn bộ M3-A hoàn tất, hồ sơ nghiệm thu bắt buộc phải chứa các tệp tin có mã băm xác thực:

```
docs/milestones/m3-collection/evidence/m3-a/
 |-- red-observations.md       # Quan sát bằng chứng các test bị fail trước khi code
 |-- targeted-test-report.txt  # Kết quả chạy bộ targeted test sau khi hoàn thiện code
 |-- m1-regression-report.txt  # Báo cáo 93/93 tests M1 đạt GREEN
 |-- secret-scan.json          # Báo cáo quét 0 credentials
 |-- hashes.sha256             # Bảng băm SHA-256 toàn vẹn của mọi artifacts
 |-- status.json               # Trạng thái máy đọc: {"status": "PASS", "gate": "G06"}
```

---

## 6. Tiêu Chí Hoàn Thành (Definition of Done)

Gói công việc Phân hệ A chỉ được xem là hoàn tất khi:
1. 100% các bài kiểm thử unit và integration tương ứng đạt `GREEN`.
2. Không vi phạm bất kỳ invariant nào (`INV-015`, `INV-020`, `A-RULE-001..016`).
3. 100% các ca kiểm thử SSRF đạt chuẩn an toàn tuyệt đối.
4. Kiểm thử hồi quy M1 và M2 đạt `PASS` 100%.
5. Cây làm việc git sạch sẽ (`git diff --check` không có trailing whitespace hoặc CRLF).
6. Sol-Lead review read-only gửi `ACCEPT`.
7. Astra-Lead supreme audit read-only gửi `PASS`.

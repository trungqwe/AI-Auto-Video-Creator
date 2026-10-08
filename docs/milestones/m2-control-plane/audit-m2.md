# Báo cáo Kiểm toán và Nghiệm thu Exit Gate Milestone M2 Control Plane

**Milestone:** M2 (Control Plane Foundation, Idempotency, Outbox, API, SSE Stream & Admin UI)  
**Thời điểm lập:** 2026-10-08  
**Đánh giá tổng thể:** **M2_READY_FOR_USER_CHECKPOINT**  
**Phát hiện tồn đọng:** 0 BLOCKER, 0 MAJOR, 0 CRITICAL  
**Ranh giới thẩm quyền:** Milestone M2 hoàn tất 100% và đạt toàn bộ tiêu chí Exit Gate; sẵn sàng trình Người dùng User Checkpoint M2. Milestone M3 và Phân hệ A tiếp tục `NOT AUTHORIZED` (khóa chặt fail-closed tới khi có phê duyệt riêng từ Người dùng).

---

## 1. Căn cứ và Phạm vi Kiểm toán

Kiểm toán toàn diện Milestone M2 Control Plane được thực hiện độc lập dựa trên:
1. `docs/milestones/m2-control-plane/spec.md`: Đặc tả kỹ thuật Milestone M2.
2. `docs/milestones/m2-control-plane/implementation-plan.md`: Kế hoạch thực thi và Tiêu chuẩn Exit Gate M2.
3. `docs/10-test-strategy.md`: Chiến lược kiểm thử toàn cục của hệ thống.
4. Toàn bộ chuỗi gói bằng chứng bất biến từ M2-P0 đến M2-P8 và M2-P9 (docs/milestones/m2-control-plane/evidence/, tests/m2/evidence/, src/controlplane/ui/dist/, tests/m2/e2e/).
5. Kết quả kiểm thử thực nghiệm trên toolchain chuẩn: Python 3.13.15, Node.js 22.17.0, PostgreSQL 18.6 thật và trình duyệt Playwright Chromium thật.

---

## 2. Kiểm chứng Độc lập 6 Tiêu chí Exit Gate Milestone M2

### Tiêu chí 1: 100% Hợp đồng Nền tảng Đã Được Kiểm chứng
- **Các hợp đồng và cơ chế cốt lõi:**
  * **Envelope chuẩn (CT-CMN-001/002):** Trường bắt buộc RFC 3339 UTC, workspace scoping, correlation tracking được kiểm chứng qua `test_p2_envelopes_and_idempotency.py`.
  * **RFC 9457 Problem Details:** Báo lỗi trung lập giao thức, không làm lộ stack trace hay thông tin nhạy cảm.
  * **Idempotency bền vững (ADR-0002):** Lưu trữ `CommandReceipt`, cùng key + cùng payload trả lại biên nhận cũ; cùng key + khác payload bị từ chối với xung đột.
  * **Transactional Outbox (ADR-0003):** Đột biến nghiệp vụ và outbox event cam kết nguyên tử (atomic commit/rollback); cơ chế consumer khử trùng lặp và bảo vệ phân đoạn.
  * **5 State Machines:** Vòng đời Operation, Batch, Job, Stage Run và Artifact Cleanup tuân thủ nghiêm ngặt bảng chuyển trạng thái hợp lệ; các chuyển đổi bị cấm đều bị chặn fail-closed.
  * **Cấu hình & Bí mật (P5A):** Bất biến `ConfigRevision`, tính toán hash nội dung và lưu trữ secret qua handle an toàn.
  * **Artifact Metadata (P5B):** Đăng ký phiên bản artifact, xác thực location hash và cấp quyền dọn dẹp.
  * **Execution Grant Fencing & Variant Reservation (P6):** Chặn đứng stale epoch qua CAS fencing, ngăn chặn song song ghi đè variant.
  * **Completion Ledger Skeleton (P6):** Đảm bảo tính duy nhất bất biến của completion per job.

### Tiêu chí 2: Không có Duplicate Aggregate hoặc Duplicate Side Effect
- **Kiểm chứng thực nghiệm:**
  * Command lặp lại với cùng `Idempotency-Key` được nhận diện chính xác và trả về cùng biên nhận `CommandReceipt` mà không sinh thêm bất kỳ aggregate hay dòng cơ sở dữ liệu mới nào.
  * Event tiêu thụ lặp lại (at-least-once outbox delivery) được khử trùng lặp bởi consumer idempotent, đảm bảo 0 duplicate side effect trên projection views.
  * Hai consumer chạy đồng thời xử lý cùng một event chỉ tạo ra đúng 1 hiệu ứng logic duy nhất trên projection.

### Tiêu chí 3: Bảo vệ Ranh giới Bí mật Tuyệt đối
- **Kiểm tra rò rỉ mã nguồn và tài liệu:**
  * Standalone secret scanner của M2 (`src/controlplane/infrastructure/security/secret_scanner.py`) đã quét 1,116 tệp tin trên toàn bộ `src/controlplane`, `tests/m2`, `docs/milestones/m2-control-plane` và `migrations`.
  * **Kết quả:** `VERDICT: CLEAN`, `TOTAL_FINDINGS: 0`. Tuyệt đối 0 byte secret hay token bị commit.
- **Ranh giới giao diện và DOM:**
  * `SafeErrorModal` tự động thanh lọc thông báo lỗi; chỉ hiển thị mã tham chiếu chẩn đoán an toàn `technical_detail_ref`, ngăn chặn 100% stack trace thô và biến môi trường trong user-visible DOM.
  * Kiểm thử chống XSS: Chuỗi độc hại `<script>` được escape an toàn và vô hiệu hóa.

### Tiêu chí 4: Lát cắt Người dùng Hoạt động Đích thực
- **Kiến trúc giao diện quản trị (Module H):**
  * Xây dựng trên nền tảng React 18 + TypeScript + AG Grid Community 32 + Vite 6 theo chuẩn [ADR-0007](../../adr/0007-runtime-and-admin-ui.md).
  * Giao diện tiếng Việt có dấu 100%, thiết kế Dark Mode sắc nét, tối ưu hiển thị cho desktop độ phân giải 1080p+ (1920x1080).
  * AG Grid hiển thị danh sách Operations, Batches thời gian thực, kết nối backend Control API thật qua HTTPS loopback và stream SSE `/v1/operations/stream`.
- **Kiểm thử Browser E2E thực tế bằng Playwright Chromium:**
  * Toàn bộ 5 kịch bản E2E tại `tests/m2/e2e/*.spec.ts` đều **PASSED 100%** trên trình duyệt thật:
    1. `admin-command-idempotency.spec.ts`: Gửi lệnh `StartProductionBatch`, nhận biên nhận và xác minh phát lại biên nhận trên lệnh trùng.
    2. `operations-sse.spec.ts (luồng DOM)`: Cập nhật trực tiếp DOM từ `ACCEPTED` sang `RUNNING` và `SUCCEEDED` thông qua sự kiện SSE mà không cần refresh trang.
    3. `operations-sse.spec.ts (phục hồi cursor)`: Phục hồi và đồng bộ lại stream sau khi cursor hết hạn bằng cursor do máy chủ cung cấp.
    4. `performance-budget.spec.ts`: Xác nhận chỉ số hiệu năng đạt chuẩn: Command ACK <= 1s (`QR-PERF-006`) và 95% thao tác UI <= 2s (`QR-PERF-005`).
    5. `safe-error-modal.spec.ts`: Kiểm tra an toàn modal lỗi và escape XSS.

### Tiêu chí 5: Bảo toàn Hồi quy M1
- **Kiểm chứng toàn bộ 93 bài test M1:**
  * Toàn bộ test suite hồi quy Milestone M1 (`tests/m1/**`) được chạy độc lập trên môi trường Python 3.13.15 với kết nối PostgreSQL thật và Temporal SDK.
  * **Kết quả:** **93/93 PASSED, 0 FAILED, 0 ERRORS, 0 SKIPPED** (thời gian chạy ~46.57s).
  * Bảo đảm tính tương thích ngược tuyệt đối; không phá vỡ bất kỳ giao thức chứng minh nào của M1.

### Tiêu chí 6: Báo cáo Kiểm toán M2 Hoàn tất
- Báo cáo kiểm toán này cùng với tệp manifest băm SHA-256 DAG tổng hợp tại docs/milestones/m2-control-plane/evidence/manifest.json đã ràng buộc hoàn toàn và khóa chặt toàn bộ artifacts của Milestone M2 (từ M2-P0 đến M2-P8 và M2-P9).
- Gói bằng chứng P9 tại docs/milestones/m2-control-plane/evidence/m2-p9/ lưu trữ đầy đủ log thực thi, kết quả kiểm tra integrity, provenance và zero secret leak.
- Bằng chứng gói M2-P8 được ràng buộc đầy đủ trong manifest thông qua các artifact phân phối UI (src/controlplane/ui/dist/), bằng chứng hồi quy M1 (tests/m2/evidence/m1-regression.xml, tests/m2/evidence/m1_regression_drive_e3_evidence.json) và bộ kiểm thử trình duyệt thật E2E (tests/m2/e2e/*.spec.ts).

---

## 3. Tổng hợp Kết quả Kiểm thử Toàn bộ Hệ thống

| Phân hệ / Hạng mục kiểm thử | Số lượng bài test | Kết quả | Ghi chú |
| :--- | :---: | :---: | :--- |
| **M1 Regression Suite** | 93 | **93 PASSED** | Bảo toàn 100% M1 (0 skip, 0 fail) |
| **M2 Python Tests (P0..P7B, Plugin)** | 174 | **174 PASSED** | Kiến trúc, UoW, Idempotency, SSE, Hardening |
| **M2-P9 Exit Gate Verification Suite** | 6 | **6 PASSED** | Manifest, Tamper, Canary, Rollback, Exit Audit |
| **Playwright Real Browser E2E** | 5 | **5 PASSED** | React UI, AG Grid, SSE stream, Safe Modal, Budgets |
| **TỔNG CỘNG HỆ THỐNG** | **278** | **278 PASSED (100%)** | **0 failures, 0 errors, 0 skipped** |

---

## 4. Kiểm chứng Cơ sở Dữ liệu & Migration Rollback

- **Kiểm thử trên Disposable Database:**
  * Tạo database cô lập `m2_p1_test_<uuid>` trên PostgreSQL 18.6.
  * Áp dụng forward migrations: 8/8 migrations (`0001` đến `0008`) thành công.
  * Thực hiện rollback migrations: 8/8 migrations rollback hoàn toàn, schema `controlplane` và bảng `cp_schema_migrations` được dọn dẹp nguyên trạng.
  * Tái áp dụng forward migrations: 8/8 migrations tái áp dụng thành công.
  * Khẳng định tính tự nhất quán và an toàn tuyệt đối của toàn bộ chuỗi migration M2.

---

## 5. Kết luận & Quyết định Nghiệm thu

- **Kết luận:** Milestone M2 Control Plane đã hoàn thành toàn diện 100% các yêu cầu chức năng, phi chức năng, kiến trúc bảo mật và kiểm thử thực tế.
- **Trạng thái hệ thống:** **`M2_READY_FOR_USER_CHECKPOINT`**
- **Bước tiếp theo:** Trình Người dùng phê duyệt nghiệm thu Milestone M2. Tuyệt đối không tự ý mở Milestone M3 hoặc Phân hệ A cho đến khi Người dùng cấp thẩm quyền riêng biệt.
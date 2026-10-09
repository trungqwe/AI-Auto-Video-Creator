# Kế Hoạch Kiểm Thử Toàn Diện: M7-INTEGRATION (Comprehensive Test Plan Specification)

> **Mã định danh gói (Package ID):** `M7-INTEGRATION` (Chuyển tiếp từ `M7-INTEGRATION-TEMPLATE`)
> **Milestone liên quan:** `M7` — Tự động hóa lô, hardening và baseline vận hành (`R5 Unattended Beta` & `R6 Operational Baseline`)
> **Trạng thái thẩm quyền:** `planned` (Thiết kế kế hoạch kiểm thử; thực thi kiểm thử tích hợp chỉ tiến hành khi Milestone M7 được mở)
> **Phân hệ sở hữu (Owners):** Toàn bộ Phân hệ A..J với các phân hệ trụ cột tích hợp: G (`CAP-G-ORCHESTRATION`), H (`CAP-H-CONTROL-API`), I (`CAP-I-STORAGE-SYNC`), J (`CAP-J-PROVIDERS`)
> **Ràng buộc kiểm thử:** Test-First, Red-Green-Refactor, 100% deterministic oracles, fail-closed khi vi phạm bất biến hoặc sai lệch hợp đồng.

---

## 1. Nguyên Tắc & Kỷ Luật Kiểm Thử Bắt Buộc

1. **Tuyệt đối không dùng Mock để đóng Gate đối ngoại:** Cổng G04 (Google Drive/OAuth), G05 (Khôi phục dữ liệu), G06 (Mô hình AI), và G07 (FFmpeg Render) bắt buộc phải kiểm thử trên các dịch vụ và tài nguyên thật; cấm dùng mock giả lập để tuyên bố hoàn thành.
2. **Kỷ luật Test-First:** Mọi hoạt động triển khai trong tương lai phải bắt đầu từ các bài kiểm thử thất bại (`RED`), chứng kiến đúng lý do fail-closed, sau đó triển khai mã nguồn tối thiểu để đạt trạng thái thành công (`GREEN`).
3. **Bảo vệ toàn vẹn 20 Bất biến:** Mọi trường hợp vi phạm bất kỳ bất biến nào từ `INV-001` đến `INV-020` đều phải bị chặn đứng ngay lập tức và ghi nhận lỗi vào sổ cái.
4. **Không dung thứ Flaky Test:** Các bài kiểm tra luồng Temporal workflow, SSE stream và kết nối mạng phải được thiết kế xác định, có cơ chế đồng bộ sự kiện rõ ràng, không sử dụng `sleep` mù quáng.

---

## 2. Danh Mục Các Test Oracle Bắt Buộc (Mandatory Test Oracles)

Kế hoạch kiểm thử M7 bao gồm đúng 24 Test Oracles bắt buộc, được tổ chức thành 7 nhóm kiểm định chuyên biệt:

### 2.1. Nhóm E2E Pipeline & Batch Allocation (CT-ORC-001..012, INV-010, INV-013, INV-014, INV-018)
| Mã Kiểm Thử | Tình Huống Kiểm Thử (Test Scenario) | Kết Quả Kỳ Vọng (Expected Oracle Outcome) | Ràng Buộc Hợp Đồng / Bất Biến |
|---|---|---|---|
| `TST-INT-E2E-001` | Toàn trình sản xuất 1 video hợp lệ từ crawl nguồn thô đến upload và xác thực Google Drive | Video hoàn tất 61-70s, MP4 1080x1920 30fps, đủ hook, subtitle burn-in, thumbnail 0-3s, QC pass, upload và verify checksum trên Cloud thành công | `E2E-001`, `CT-CMN-*`, `OBJ-002` |
| `TST-INT-BAT-001` | Tiếp nhận batch target từ người dùng; phân bổ theo vòng và giới hạn 1-3 video/tin | Thuật toán phân bổ gán chính xác 1-3 video cho mỗi bài viết hợp lệ; hoàn thành đúng chỉ tiêu target đã cấu hình | `CT-ORC-002`, `INV-010`, `INV-013` |
| `TST-INT-BAT-002` | Kiểm tra giới hạn sức chứa đồng thời trong quá trình sản xuất lô | Số video đã hoàn thành cộng với các slot công việc đang thực hiện không bao giờ vượt quá chỉ tiêu lô (`target_completed_videos`) | `CT-ORC-002`, `INV-018` |
| `TST-INT-VAR-001` | Đa dạng hóa biến thể giữa các đợt sản xuất khác nhau từ cùng nguồn tin | Các video sinh ra khác biệt ít nhất một yếu tố thực tế (góc tiếp cận, hook, phong cách dựng); được xác thực qua sổ đối chiếu biến thể | `CT-ORC-012`, `INV-014` |

### 2.2. Nhóm Chịu Lỗi, Cô Lập Lỗi & Tái Lập Workflow (CT-WF-001..009, INV-001..003, INV-016)
| Mã Kiểm Thử | Tình Huống Kiểm Thử (Test Scenario) | Kết Quả Kỳ Vọng (Expected Oracle Outcome) | Ràng Buộc Hợp Đồng / Bất Biến |
|---|---|---|---|
| `TST-INT-FLT-001` | Một video trong lô gặp lỗi vĩnh viễn (ví dụ lỗi định dạng nguồn hoặc vi phạm an toàn nội dung) | Child workflow của video đó kết thúc ở trạng thái lỗi được ghi nhận rõ; toàn bộ batch và các video độc lập khác vẫn tiếp tục bình thường | `CT-WF-001`, `CT-ORC-003`, `CT-ORC-010`, `R16` |
| `TST-INT-RPL-001` | Tái lập lịch sử workflow Temporal qua các phiên bản mã nguồn cập nhật | Lịch sử chạy (History events) của workflow cũ tái lập thành công mà không gây lỗi Non-Deterministic Error | `Gate G01`, `CT-WF-009` |
| `TST-INT-REC-001` | Máy trạm Desktop mất mạng đột ngột trong 4 phút 30 giây rồi kết nối lại | Workflow chuyển sang `waiting_capability` và tự động tiếp tục khi desktop online mà không chạy lại từ đầu | `CT-WF-007`, `INV-003` |
| `TST-INT-FNC-001` | Worker thế hệ cũ gửi kết quả muộn sau khi tác vụ đã được phân bổ lại cho worker mới | Hệ thống từ chối commit kết quả từ worker có generation token cũ; bảo toàn tính toàn vẹn trạng thái | `CT-WF-004`, `CT-WF-006`, `INV-003`, `INV-016` |
| `TST-INT-IDM-001` | Gửi mutation lệnh lặp nhiều lần và phát tán domain event lặp nhiều lần | Trả về `CommandReceipt` ban đầu; consumer chỉ xử lý side-effect đúng một lần duy nhất qua outbox deduplication | `INV-001`, `INV-002`, `CT-API-001`, `CT-WF-005`, `CT-EVT-001`, `CT-EVT-005` |

### 2.3. Nhóm Lưu Trữ Hybrid, Dọn Dẹp & Khôi Phục Thảm Họa (CT-STO-001..011, INV-009, INV-011, INV-016, INV-017)
| Mã Kiểm Thử | Tình Huống Kiểm Thử (Test Scenario) | Kết Quả Kỳ Vọng (Expected Oracle Outcome) | Ràng Buộc Hợp Đồng / Bất Biến |
|---|---|---|---|
| `TST-INT-DRV-001` | Upload video MP4 lên Google Drive thật với cơ chế resumable upload và xác thực checksum | Tải lên thành công qua nhiều chunk ngắt quãng; checksum SHA-256 đối chiếu khớp hoàn toàn giữa Cloud và Local | `Gate G04`, `CT-STO-003`, `CT-STO-002` |
| `TST-INT-DRV-002` | Video đã qua kiểm định QC pass nhưng quá trình tải lên Google Drive bị gián đoạn chưa hoàn tất | Trạng thái job dừng tại `qc_passed`; tuyệt đối không được ghi nhận hoàn thành (`completed`) khi chưa có `cloud_verified` | `INV-009`, `CT-QC-002` |
| `TST-INT-CLN-001` | Động cơ dọn dẹp quét thư mục tệp tạm sau khi render hoàn tất | Tệp chỉ bị xóa khi thỏa mãn đủ 5 điều kiện theo `CT-STO-008`: staging/cache được phép xóa; không có lease/consumer hoạt động; đã verify trên cloud; cùng recovery epoch; resolved absolute path nằm trong staging root | `INV-011`, `CT-STO-007`, `CT-STO-008` |
| `TST-INT-MED-001` | Ghi nhận hoàn thành video vào CompletionLedger và cập nhật tần suất sử dụng media của Phân hệ C | Cả hai thao tác cùng commit thành công hoặc cùng rollback nếu xảy ra sự cố cơ sở dữ liệu (tính nguyên tử phân tán) | `INV-017`, `CT-ORC-008`, `CT-ORC-009` |
| `TST-INT-RST-001` | Khôi phục cơ sở dữ liệu từ bản sao lưu và gán một epoch mới (`BackupEpoch`) | Hệ thống hoạt động bình thường trên epoch mới; toàn bộ message, grant và event từ epoch cũ bị cô lập hoàn toàn | `Gate G05`, `INV-016`, `CT-STO-009` |

### 2.4. Nhóm Bảo Mật, Sandbox & Không Rò Rỉ Secret (CT-SEC-001..005, INV-012, INV-020)
| Mã Kiểm Thử | Tình Huống Kiểm Thử (Test Scenario) | Kết Quả Kỳ Vọng (Expected Oracle Outcome) | Ràng Buộc Hợp Đồng / Bất Biến |
|---|---|---|---|
| `TST-INT-SEC-001` | Rà soát toàn bộ nhật ký hệ thống, Temporal workflow history, SSE stream và màn hình UI | 100% token, API key, mật khẩu và khóa bí mật được che giấu bởi `RedactionFilter`; tuyệt đối 0 trường hợp rò rỉ | `INV-012`, `CT-SEC-001`, `CT-SEC-002` |
| `TST-INT-SAN-001` | Đưa nội dung nguồn chứa payload độc hại (Prompt Injection gián tiếp, liên kết SSRF, đường dẫn Path Traversal) | Bộ lọc an toàn phát hiện và vô hiệu hóa payload; cấm tuyệt đối việc thực thi lệnh hệ điều hành hoặc đổi chính sách | `INV-020`, `CT-SEC-003`, `CT-SEC-004` |

### 2.5. Nhóm Điều Khiển, Giao Diện & Quan Sát (CT-API-001..010, CT-BAT-001..004, CT-EVT-001..005)
| Mã Kiểm Thử | Tình Huống Kiểm Thử (Test Scenario) | Kết Quả Kỳ Vọng (Expected Oracle Outcome) | Ràng Buộc Hợp Đồng / Bất Biến |
|---|---|---|---|
| `TST-INT-SSE-001` | Kênh SSE stream bị mất kết nối mạng và kết nối lại sau 10 giây | Client gửi lại `Last-Event-ID`; server bù đắp đầy đủ toàn bộ các sự kiện bị thiếu từ bảng outbox mà không bỏ sót | `CT-API-008`, `CT-EVT-001`, `CT-EVT-005` |
| `TST-INT-CTL-001` | Người dùng thực hiện các thao tác Pause, Resume, Cancel và ForceReconcile trên lô đang chạy | Động cơ điều phối chuyển đổi trạng thái chính xác theo máy trạng thái, dừng an toàn các activity đang chờ | `CT-API-005`, `CT-ORC-001`, `CT-ORC-004`, `CT-ORC-007` |
| `TST-INT-OBS-001` | Kiểm tra tính nhất quán dữ liệu giữa giao diện Desktop UI và cơ sở dữ liệu PostgreSQL | Toàn bộ màn hình UI (Nguồn tin, Nội dung, Media, Jobs, Lô, Logs, Chi phí) hiển thị đồng nhất; không có sai lệch âm thầm | `CT-API-002`, `CT-API-007`, `CT-API-008`, `CT-API-010` |

### 2.6. Nhóm Quản Trị Nhà Cung Cấp, Hạn Mức & Chi Phí (CT-ACC-001..002, CT-CAP-001..003, CT-COST-001)
| Mã Kiểm Thử | Tình Huống Kiểm Thử (Test Scenario) | Kết Quả Kỳ Vọng (Expected Oracle Outcome) | Ràng Buộc Hợp Đồng / Bất Biến |
|---|---|---|---|
| `TST-INT-CST-001` | Chi phí tích lũy của lô sản xuất tăng dần và chạm mốc 80% ngân sách tháng | Hệ thống tự động phát cảnh báo khẩn cấp lên UI và dừng nhận thêm job mới vào lô sản xuất | `Gate G03`, `CT-COST-001`, `CT-CAP-001` |
| `TST-INT-CST-002` | Đo lường chi phí gia tăng thực tế trên kịch bản tải mô phỏng 1 tháng vận hành chuẩn | Tổng chi phí API (LLM, TTS) và dịch vụ đám mây thực tế nằm dưới ngưỡng giới hạn 50 USD/tháng | `Gate G03`, `CT-COST-001`, `R24` |
| `TST-INT-CAP-001` | Hệ thống rơi vào trạng thái tài nguyên phần cứng tới hạn (CPU > 85% hoặc RAM < 4GB hoặc Disk < 20GB) | Cơ chế Admission Control từ chối tiếp nhận tác vụ mới; giải phóng tài nguyên trước khi tiếp tục | `CT-CAP-001`, `CT-CAP-002` |

### 2.7. Nhóm Hiệu Năng & Xuất Xưởng Vận Hành (Gate G02, OBJ-003, OBJ-004)
| Mã Kiểm Thử | Tình Huống Kiểm Thử (Test Scenario) | Kết Quả Kỳ Vọng (Expected Oracle Outcome) | Ràng Buộc Hợp Đồng / Bất Biến |
|---|---|---|---|
| `TST-INT-BMK-001` | Chạy thử nghiệm tải liên tục trong 12 giờ trên môi trường máy mục tiêu chuẩn | Sản xuất tối thiểu 100 video hợp lệ hoàn tất, được đồng bộ thành công lên Google Drive trong vòng 12 giờ | `Gate G02`, `OBJ-003` |
| `TST-INT-AUT-001` | Đánh giá mức độ tự động hóa trên tổng số video có đủ dữ liệu đầu vào trong đợt chạy lô | Đạt tối thiểu 95% video hoàn thành từ đầu đến cuối mà không cần bất kỳ can thiệp thủ công nào sau khi kích hoạt lô | `Gate G02`, `OBJ-004` |

---

## 3. Quy Trình & Lệnh Kiểm Thử Mục Tiêu (Targeted Test Commands)

Khi Milestone M7 được cấp quyền triển khai, các bài kiểm tra được kích hoạt có chủ đích qua các lệnh mục tiêu:

```bash
# 1. Kiểm thử tích hợp luồng điều phối lô và kiểm soát chỉ tiêu (INT-1)
pytest tests/integration/orchestration/test_batch_engine.py -k "test_batch_allocation or test_capacity_reservation" -v

# 2. Kiểm thử cô lập lỗi và tái lập lịch sử Temporal workflow (INT-2)
pytest tests/integration/orchestration/test_resilience.py -k "test_child_isolation or test_reconnection or test_replay" -v

# 3. Kiểm thử lọc sạch bí mật và an toàn dữ liệu nguồn ngoài (INT-3)
pytest tests/integration/security/test_security_hardening.py -k "test_secret_redaction or test_prompt_injection_defense" -v

# 4. Kiểm thử kênh SSE stream và giao diện điều khiển (INT-4)
pytest tests/integration/control/test_sse_resync.py -k "test_sse_cursor_resync or test_admin_commands" -v

# 5. Kiểm thử đồng bộ Google Drive thật, dọn dẹp và khôi phục epoch (INT-5)
pytest tests/integration/storage/test_storage_integration.py -k "test_drive_resumable_upload or test_atomic_cleanup or test_epoch_restore" -v

# 6. Kiểm thử quản lý quota nhà cung cấp và cảnh báo chi phí 80% (INT-6)
pytest tests/integration/providers/test_cost_quota_guard.py -k "test_cost_80_percent_warning or test_admission_control" -v

# 7. Kiểm thử toàn trình 14 kịch bản E2E (INT-7)
pytest tests/e2e/test_e2e_001_to_014.py -v

# 8. Bài benchmark hiệu năng 12 giờ (INT-8)
python -m tests.e2e.benchmark_12h --target 100 --max-hours 12 --verify-cloud
```

---

## 4. Ma Trận Cổng Chất Lượng & Phê Duyệt Xuất Xưởng (Quality Release Gates)

Gói kiểm thử M7 thẩm định đầy đủ 7 cổng chất lượng hệ thống phục vụ 2 nấc phát hành:
- **`R5 Unattended Beta` (Trước Gate Cuối):** Lô chạy không giám sát trên workload đại diện; một video/nguồn lỗi không làm dừng batch; resume/retry/cleanup qua kiểm thử fault injection; không có lỗi P0/P1 mở.
- **`R6 Operational Baseline` (Sau Gate Cuối):** Đóng toàn bộ G01..G07 với đầy đủ bằng chứng thực tế; hoàn thành 100 video/12h; đạt >= 95% tự động; chi phí < 50 USD/tháng; runbook vận hành sẵn sàng; người dùng nghiệm thu chính thức.

| Cổng Chất Lượng | Ý Nghĩa Kiểm Định | Phương Thức Đóng Cổng | Tiêu Chuẩn Đạt Chuẩn (Acceptance Criteria) |
|---|---|---|---|
| `G01 Workflow` | Tái lập, chịu lỗi và phục hồi workflow Temporal | Chạy kịch bản replay history và crash/reconnect | 100% replay pass, không non-deterministic error, reconnect < 5 phút tiếp tục trơn tru |
| `G02 Throughput` | Năng lực sản xuất và mức độ tự động hóa | Chạy thử nghiệm 12 giờ trên máy mục tiêu | Hoàn tất >= 100 video hợp lệ trong 12 giờ; tỷ lệ tự động >= 95% không can thiệp |
| `G03 Cost` | Ngân sách chi phí và kiểm soát hạn mức | Đo lường chi phí trên workload 1 tháng | Chi phí gia tăng < 50 USD/tháng; cảnh báo kích hoạt chính xác tại ngưỡng 80% |
| `G04 Drive/Security` | An toàn lưu trữ Cloud và bảo mật thông tin | Upload Google Drive thật và quét secret toàn diện | Checksum SHA-256 khớp 100%; 0 trường hợp rò rỉ secret trong mọi luồng dữ liệu |
| `G05 Restore` | Khôi phục thảm họa và cô lập dữ liệu | Diễn tập phục hồi database từ backup epoch | Khôi phục toàn vẹn dữ liệu; cô lập 100% message và grant từ epoch cũ |
| `G06 AI/Content` | Chất lượng nội dung và kịch bản tiếng Anh | Kiểm định trên holdout corpus đã được khóa | Đạt các ngưỡng đánh giá chất lượng; 100% video xuất xưởng có bằng chứng tiếng Anh |
| `G07 Compatibility/QC` | Tương thích môi trường và kiểm định video | Chạy kiểm định 13 gates trên video xuất xưởng | 100% video xuất xưởng đạt chuẩn 1080x1920 30fps, âm thanh chuẩn EBU R128, subtitle karaoke |

---

## 5. Bằng Chứng Bắt Buộc Khi Hoàn Tất Gói (Evidence Requirements)

Khi hoàn tất gói công việc hoặc toàn bộ M7, hồ sơ nghiệm thu bắt buộc phải chứa manifest JSON có cấu trúc sau:

```json
{
  "milestone": "M7",
  "package_id": "M7-INTEGRATION",
  "evidence_version": "1.0.0",
  "timestamp": "2026-10-09T00:00:00Z",
  "test_execution_summary": {
    "total_tests": 24,
    "passed": 24,
    "failed": 0,
    "skipped": 0
  },
  "invariant_attestation": {
    "INV-001": "VERIFIED_COMMAND_IDEMPOTENCY",
    "INV-002": "VERIFIED_EVENT_IDEMPOTENCY",
    "INV-003": "VERIFIED_STALE_GENERATION_GUARD",
    "INV-004": "VERIFIED_CONFIGURATION_IMMUTABILITY",
    "INV-005": "VERIFIED_ARTICLE_DEDUPLICATION",
    "INV-006": "VERIFIED_TIMELINE_ACCEPTED_UPDATE",
    "INV-007": "VERIFIED_WORD_TIMING_ALIGNMENT",
    "INV-008": "VERIFIED_RENDER_PACKAGE_INTEGRITY",
    "INV-009": "VERIFIED_CLOUD_COMPLETION_GUARD",
    "INV-010": "VERIFIED_COMPLETION_LEDGER_ACCOUNTING",
    "INV-011": "VERIFIED_ATOMIC_CLEANUP_CONDITIONS",
    "INV-012": "VERIFIED_ZERO_SECRET_LEAKAGE",
    "INV-013": "VERIFIED_BATCH_ROUND_DIVERSITY",
    "INV-014": "VERIFIED_CROSS_ROUND_VARIATION",
    "INV-015": "VERIFIED_SOURCE_TOMBSTONE_GUARD",
    "INV-016": "VERIFIED_DISASTER_RECOVERY_EPOCH_ISOLATION",
    "INV-017": "VERIFIED_COMPLETION_MEDIA_USAGE_ATOMICITY",
    "INV-018": "VERIFIED_CAPACITY_RESERVATION_CEILING",
    "INV-019": "VERIFIED_ENGLISH_OUTPUT_EVIDENCE",
    "INV-020": "VERIFIED_UNTRUSTED_DATA_SANDBOXING"
  },
  "release_gates_status": {
    "G01": "PASS",
    "G02": "PASS",
    "G03": "PASS",
    "G04": "PASS",
    "G05": "PASS",
    "G06": "PASS",
    "G07": "PASS"
  },
  "benchmark_summary": {
    "total_videos_completed_12h": 102,
    "automation_success_rate": 0.961,
    "monthly_cost_projection_usd": 42.50
  }
}
```

---

## 6. Tiêu Chuẩn Nghiệm Thu Hoàn Thành (Definition of Done)

Gói công việc M7 chỉ được xem là hoàn tất khi:
1. Toàn bộ 24 test oracles đạt trạng thái `PASS` trên môi trường kiểm thử cô lập.
2. Không phát hiện bất kỳ vi phạm nào đối với toàn bộ 20 bất biến `INV-001` đến `INV-020`.
3. Toàn bộ 7 cổng chất lượng hệ thống (`G01`..`G07`) được đóng thành công với đầy đủ bằng chứng thực tế, không dùng mock giả lập.
4. Đạt chỉ tiêu benchmark vận hành: hoàn thành >= 100 video hợp lệ trong 12 giờ và đạt >= 95% tự động hóa không cần can thiệp.
5. Hồ sơ vận hành, runbook, hướng dẫn xoay vòng khóa và quy trình xử lý sự cố thảm họa được phê duyệt đầy đủ bởi người dùng qua `USER-CKPT-M7`.

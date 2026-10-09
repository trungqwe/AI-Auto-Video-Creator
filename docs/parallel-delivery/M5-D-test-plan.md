# Kế Hoạch Kiểm Thử Toàn Diện: M5-D (Comprehensive Test Plan Specification)

> **Mã gói (Package ID):** `M5-D`
> **Trạng thái:** `planned_test_strategy`
> **Tài liệu nguồn:** `docs/10-test-strategy.md` (Mục 12, 13, 23, 29), `docs/11-roadmap.md` (Mục 11), `docs/parallel-delivery/acceptance-matrix.yaml` (R05..R08, Gate G06)
> **Phương pháp luận:** Test-First / Behavioral TDD (`SPEC` -> `PLAN` -> `RED` -> `IMPLEMENT` -> `GREEN` -> `VERIFY` -> `EVIDENCE`)

---

## 1. Nguyên Tắc & Kỷ Luật Kiểm Thử Bắt Buộc

1. **Chứng kiến hỏng hóc hành vi (Behavioral RED First):**
   - Trước khi viết mã sản phẩm, mỗi ca kiểm thử phải chạy và thất bại vì vi phạm assertions nghiệp vụ/hợp đồng (`Behavioral RED`), tuyệt đối không chấp nhận RED do lỗi import, lỗi cấu hình môi trường, hoặc thiếu binary (`Invalid Setup Failure`).
2. **Kiểm thử trên PostgreSQL Disposable Thật (Real DB Isolation):**
   - Không dùng SQLite hay in-memory mock để thay thế PostgreSQL cho các kiểm thử liên quan đến transactions, Unit of Work, outbox, concurrency, hoặc unique constraints của creative entities.
   - Mỗi test function hoặc test suite sử dụng database tạm thời riêng biệt (`function-scoped disposable database`), tự động dọn dẹp sạch sẽ sau khi chạy xong (`0 orphan databases`).
3. **Mô phỏng AI Adapter Xác Định & Cô Lập Mạng (Deterministic Offline AI Stub):**
   - Các bài kiểm thử unit/local sử dụng deterministic mock AI adapter mô phỏng chính xác phản hồi JSON, schema validation, HTTP 429 rate limit, timeout và token usage.
   - Kiểm thử xác minh hệ thống hoạt động ổn định ở chế độ offline, không phụ thuộc vào kết nối mạng ngoài hay tài khoản AI thương mại.
4. **Cấm dùng Mock để vượt qua cổng kiểm tra bảo mật & toàn vẹn:**
   - Tuyệt đối không mock thuật toán tính toán `VariantFingerprint`, kiểm tra độ dài thời lượng nghiêm ngặt 61–70 giây, phân định ranh giới prompt injection của dữ liệu nguồn (`untrusted_data`), hoặc cơ chế công bố suy luận (`inference disclosure`).
5. **Kỷ luật Targeted Test (Zero Waste Execution):**
   - Trong quá trình phát triển và sửa lỗi, chỉ chạy đúng lệnh kiểm thử mục tiêu được chỉ định; chỉ chạy toàn bộ bộ kiểm thử tích hợp khi bước vào giai đoạn tổng hợp hồ sơ evidence.

---

## 2. Danh Mục Các Test Oracle Bắt Buộc (Mandatory Test Oracles)

### 2.1. Nhóm Bản Chụp Bất Biến & Cách Ly Dữ Liệu Nguồn (INV-004, INV-020, CT-AI-000, CT-AI-001, CT-AI-002)

| Mã Kiểm Thử | Tình huống kích hoạt (Scenario) | Hành vi mong đợi & Oracle bắt buộc (Expected Oracle) |
|---|---|---|
| `TST-CRE-SNP-001` | Khởi tạo `ProductionSnapshot` cho bài viết; thay đổi cấu hình prompt hoặc bài viết gốc sau thời điểm commit snapshot | Job đang chạy giữ nguyên các refs và revisions bất biến của snapshot; job mới nhận cấu hình/bài viết mới; tuyệt đối không thay đổi đầu vào của job cũ (`INV-004`) |
| `TST-CRE-SNP-002` | Dữ liệu bài viết/HTML/OCR chứa câu lệnh độc hại giả mạo system instruction (prompt injection) hoặc đề xuất resource ref ngoài workspace | Không làm thay đổi system prompt hay chính sách; không kích hoạt tool ẩn; resource ref bị resolver độc lập từ chối fail-closed nếu không nằm trong allowlist (`INV-020`, `CT-AI-000`) |
| `TST-CRE-ANA-001` | Phân tích nội dung bài viết (`AnalyzeContent`) chứa các nhận định không chắc chắn hoặc mâu thuẫn | Giữ nguyên cờ `uncertainty` và provenance nguồn; tuyệt đối không chuyển hóa nhận định chưa chắc chắn thành sự thật đã xác nhận trong representation nội bộ (`CT-AI-002`) |

---

### 2.2. Nhóm Góc Kể, Soạn Thảo Kịch Bản & Công Bố Suy Luận (R05, R06, INV-013, INV-014, CT-AI-003, CT-AI-004, CT-AI-005)

| Mã Kiểm Thử | Tình huống kích hoạt (Scenario) | Hành vi mong đợi & Oracle bắt buộc (Expected Oracle) |
|---|---|---|
| `TST-CRE-ANG-001` | Sinh 1-3 góc kể câu chuyện (`GenerateStoryAngles`) cho cùng một bài viết trong một lượt sản xuất | Tạo ra từ 1 đến 3 góc kể khác biệt rõ rệt (ví dụ: điều tra, chuyên gia, nhân chứng); mỗi góc có narrative question, focus entities và distinction fingerprint riêng (`R06`, `INV-013`, `FR-SCR-004`) |
| `TST-CRE-SCR-001` | Soạn thảo kịch bản phân cảnh (`GenerateScript`) kiểm tra thời lượng ước tính | Thời lượng đọc ước tính bắt buộc nằm nghiêm ngặt trong khoảng **61–70 giây** (khoảng 140–165 từ tiếng Anh); kịch bản <61s hoặc >70s bị từ chối và yêu cầu sinh lại ngay tại khâu biên soạn (`R05`, `INV-014`, `FR-SCR-002`) |
| `TST-CRE-SCR-002` | Kịch bản chứa các đoạn suy luận hoặc chi tiết sáng tạo ngoài nguồn bài viết gốc | Phân loại chính xác `claim_mode`; 100% các đoạn `inference` và `creative_hypothesis` bắt buộc có ngôn ngữ công bố suy luận rõ ràng, không được trình bày như sự thật (`CT-AI-004`, `FR-SCR-009`, `FR-SCR-010`) |
| `TST-CRE-NAR-001` | Kích hoạt chế độ kể chuyện dòng thời gian (`from_then_to_now`) khi snapshot có bài repost vs khi snapshot có `EventUpdateAccepted` | Bài repost/nguồn mới đơn thuần bị từ chối fail-closed với mã lỗi `POLICY_VIOLATION`; chỉ cho phép kích hoạt khi có `EventUpdateAccepted` với tình tiết mới (`CT-AI-005`, `CT-STATE-004`) |

---

### 2.3. Nhóm Lựa Chọn Tài Nguyên Sáng Tạo & Kế Hoạch Sản Xuất (R08, INV-020, CT-AI-006, CT-AI-007)

| Mã Kiểm Thử | Tình huống kích hoạt (Scenario) | Hành vi mong đợi & Oracle bắt buộc (Expected Oracle) |
|---|---|---|
| `TST-CRE-AST-001` | Lựa chọn tài nguyên sáng tạo (`SelectCreativeAssets`) từ kho của Module C | Bắt buộc phải chọn đủ 3 thành phần: Visual Hook (3 giây đầu), Audio Hook mở đầu và Thumbnail Marker; thumbnail marker bắt buộc phải nằm trong khung thời gian của hook (0–3s) (`R08`, `INV-020`, `CT-AI-006`) |
| `TST-CRE-PLN-001` | Xây dựng kế hoạch dựng chi tiết (`BuildProductionPlan`) theo 1 trong 5 preset | Kế hoạch chứa đầy đủ timeline phân cảnh, thứ tự xuất hiện tài nguyên, điểm chèn nhạc nền/SFX, subtitle style karaoke và plan fingerprint; thuộc đúng 1 trong 5 preset đã duyệt (`CT-AI-007`) |
| `TST-CRE-PLN-002` | Kế hoạch dựng chỉ định phương án fallback khi tài nguyên media chính gặp lỗi | Cung cấp danh mục fallback candidates hợp lệ; render engine không tự ý thay đổi cốt truyện nếu không nằm trong danh mục fallback được plan cho phép (`CT-AI-007`) |

---

### 2.4. Nhóm Quản Lý Biến Thể & Chống Trùng Lặp (R07, INV-004, INV-014, CT-AI-008, CT-ORC-012)

| Mã Kiểm Thử | Tình huống kích hoạt (Scenario) | Hành vi mong đợi & Oracle bắt buộc (Expected Oracle) |
|---|---|---|
| `TST-CRE-VAR-001` | Kiểm tra biến thể trong cùng một lượt sản xuất (`same_run_angle_distinct`) | 100% video từ cùng một tin trong cùng một lượt phải có `StoryAngle` khác nhau; từ chối biến thể nếu chỉ hoán đổi hiệu ứng đồ họa hoặc bộ lọc màu (`INV-013`, `FR-VAR-003`) |
| `TST-CRE-VAR-002` | Kiểm tra biến thể giữa các lượt sản xuất sau (`cross_run_variation`) | Video mới không được hoàn toàn giống video cũ (`FR-VAR-005`); bắt buộc phải khác biệt ít nhất một yếu tố thực tế được theo dõi (giọng, hook, nhạc, media, góc, hiệu ứng) (`R07`, `INV-014`, `FR-VAR-004`) |
| `TST-CRE-VAR-003` | Đặt trước biến thể với Orchestration qua `VariantReservation` | Sau khi validate hợp lệ, tạo reservation `ACTIVE` nguyên tử; xung đột biến thể chuyển trạng thái job sang `FAILED_FINAL` fail-closed (`CT-STATE-007`, `CT-ORC-012`) |

---

### 2.5. Nhóm Metadata Đầu Ra & Bảo Mật Secret Lời Gọi AI (CT-AI-009, CT-AI-010, INV-013)

| Mã Kiểm Thử | Tình huống kích hoạt (Scenario) | Hành vi mong đợi & Oracle bắt buộc (Expected Oracle) |
|---|---|---|
| `TST-CRE-MET-001` | Sinh metadata xuất bản (`GenerateOutputMetadata`) gồm title, caption, hashtag | Tạo tiêu đề/chú thích chuẩn SEO, 3-4 hashtag, và biểu diễn an toàn cho tên tệp Windows (loại bỏ ký tự cấm mà vẫn giữ bản hiển thị gốc) (`CT-AI-009`) |
| `TST-CRE-INV-001` | Ghi nhận nhật ký lời gọi AI (`AIInvocationRecord`) thông qua adapter Module J | Ghi đầy đủ model, prompt revision, latency, token count, redacted error; tuyệt đối 0 trường hợp rò rỉ API key plain-text (`CT-AI-010`, `CT-AI-ROUTE-001`) |

---

## 3. Ma Trận Phân Rã Gói Công Việc (Work Packages D0..D7)

```
D0 (Contract Closure & Fixtures)
 |-- D1 (Snapshot & Untrusted Boundary)
      |-- D2 (Content Analysis & Story Angles 1-3)
           |-- D3 (Script Generation 61-70s & Disclosures)
                |-- D4 (Timeline Narrative Authorization)
                     |-- D5 (Asset Selection & Hook/Thumbnail Placement)
                          |-- D6 (Production Plan Builder 5-Preset)
                               |-- D7 (Variant Validation, Metadata & Gate G06)
```

| Gói | Nội dung thực thi chính | Tệp tin kiểm thử mục tiêu (Targeted Test File) | Lệnh chạy kiểm thử mục tiêu |
|---|---|---|---|
| `D0` | Đóng hợp đồng CT-AI-*, validate schema JSON và bộ fixtures mẫu | `tests/unit/creative/test_d0_contract_fixtures.py` | `python -m unittest tests/unit/creative/test_d0_contract_fixtures.py` |
| `D1` | Khóa ProductionSnapshot bất biến, cách ly ranh giới prompt injection | `tests/unit/creative/test_d1_production_snapshot.py` | `python -m unittest tests/unit/creative/test_d1_production_snapshot.py` |
| `D2` | Phân tích bài viết, sinh 1-3 StoryAngle độc lập trong cùng lượt | `tests/unit/creative/test_d2_story_angles.py` | `python -m unittest tests/unit/creative/test_d2_story_angles.py` |
| `D3` | Soạn thảo ScriptVersion 61-70s, phân loại claim, disclosure suy luận | `tests/unit/creative/test_d3_script_generation.py` | `python -m unittest tests/unit/creative/test_d3_script_generation.py` |
| `D4` | Thẩm định và ủy quyền narrative dòng thời gian from_then_to_now | `tests/unit/creative/test_d4_timeline_narrative.py` | `python -m unittest tests/unit/creative/test_d4_timeline_narrative.py` |
| `D5` | Chọn visual hook, audio hook, thumbnail marker trong 0-3s | `tests/unit/creative/test_d5_asset_selection.py` | `python -m unittest tests/unit/creative/test_d5_asset_selection.py` |
| `D6` | Xây dựng ProductionPlan phân cảnh, gán 1 trong 5 preset, timeline | `tests/unit/creative/test_d6_production_plan.py` | `python -m unittest tests/unit/creative/test_d6_production_plan.py` |
| `D7` | Kiểm tra biến thể chống lặp, SEO metadata, tích hợp Gate G06 | `tests/integration/creative/test_d7_acceptance_gate.py` | `python -m unittest tests/integration/creative/test_d7_acceptance_gate.py` |

> **Lưu ý ranh giới đường dẫn kiểm thử & Gate thực thi (Test Paths & Execution Gate):**
> - Đường dẫn `tests/unit/creative/**` đã được bảo vệ bởi `PATH-SRC-CREATIVE` và `LOCK-SRC-CREATIVE` của Phân hệ D trong registry.
> - Đường dẫn kiểm thử tích hợp `tests/integration/creative/**` là **proposed path (đường dẫn đề xuất)**, hiện tại **chưa có pattern cụ thể** trong `PATH-SRC-CREATIVE` của `docs/parallel-delivery/ownership-and-locks.yaml`.
> - Kế hoạch kiểm thử này xác lập ở trạng thái `planned_test_strategy`, **không khẳng định package đã khóa đầy đủ ranh giới**.
> - Việc tạo tệp kiểm thử và thực thi các gói công việc implementation D0..D7 bị **BLOCKED** fail-closed cho đến khi:
>   1. Gate `GATE-M5-D-INTEGRATION-PATH` được Control / Authority Owner phê duyệt và cập nhật chính thức vào `ownership-and-locks.yaml`.
>   2. Checkpoint `USER-CKPT-M5` được Người dùng phê duyệt chính thức mở Milestone M5.

---

## 4. Kiểm Thử Hồi Quy Toàn Hệ Thống (Regression Invariants)

Bất kỳ thay đổi nào trong Phân hệ D cũng bắt buộc phải vượt qua các bài kiểm thử hồi quy:
1. **Kiểm tra hồi quy Milestone M1:**
   - Đảm bảo 93/93 bài test M1 đạt `PASS` (`93 passed, 0 skipped`).
2. **Kiểm tra hồi quy Milestone M2:**
   - Bộ kiểm thử `tests/m2/**` đạt `PASS`.
   - Admin UI build sạch sẽ, không có trailing whitespace.
3. **Quét dữ liệu nhạy cảm (Secret Scanner):**
   - Không chứa bất kỳ khóa bí mật, API key raw, private token dạng plain-text nào trong mã nguồn và dữ liệu test fixture.

---

## 5. Bằng Chứng Nghiệm Thu Cần Sinh Ra (Required Evidence Artifacts)

Khi hoàn tất gói công việc hoặc toàn bộ M5-D, hồ sơ nghiệm thu bắt buộc phải chứa các tệp tin có mã băm xác thực:

```
docs/milestones/m5-script/evidence/m5-d/
 |-- red-observations.md       # Quan sát bằng chứng các test bị fail trước khi code
 |-- targeted-test-report.txt  # Kết quả chạy bộ targeted test sau khi hoàn thiện code
 |-- r05-script.json           # Bằng chứng kiểm chứng R05 (Kịch bản 61-70s & claim disclosure)
 |-- r06-angles.json           # Bằng chứng kiểm chứng R06 (1-3 góc kể độc lập cùng lượt)
 |-- r07-variants.json         # Bằng chứng kiểm chứng R07 (VariantFingerprint & chống trùng lặp)
 |-- r08-thumbnail.json        # Bằng chứng kiểm chứng R08 (Thumbnail marker trong hook 0-3s)
 |-- m1-regression-report.txt  # Báo cáo 93/93 tests M1 đạt GREEN
 |-- secret-scan.json          # Báo cáo quét 0 credentials
 |-- hashes.sha256             # Bảng băm SHA-256 toàn vẹn của mọi artifacts
 |-- status.json               # Trạng thái máy đọc: {"status": "PASS", "gate": "G06"}
```

---

## 6. Tiêu Chí Hoàn Thành (Definition of Done)

Gói công việc M5-D chỉ được xem là hoàn tất khi:
1. 100% các bài kiểm thử unit và integration tương ứng đạt `GREEN`.
2. Không vi phạm bất kỳ invariant nào (`INV-004`, `INV-013`, `INV-014`, `INV-020`, `ARCH-008`).
3. 100% kịch bản có thời lượng ước tính trong khoảng 61–70 giây và 100% suy luận có disclosure.
4. Thumbnail marker luôn nằm trong vùng hook (0–3 giây đầu).
5. Kiểm thử hồi quy M1 và M2 đạt `PASS` 100%.
6. Cây làm việc git sạch sẽ (`git diff --check` không có trailing whitespace hoặc CRLF).
7. Sol-Lead review read-only gửi `ACCEPT`.
8. Astra-Lead supreme audit read-only gửi `PASS`.

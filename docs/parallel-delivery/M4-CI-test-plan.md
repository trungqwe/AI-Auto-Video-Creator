# Kế Hoạch Kiểm Thử Toàn Diện: M4-CI (Comprehensive Test Plan Specification)

> **Mã gói (Package ID):** `M4-CI`
> **Trạng thái:** `planned_test_strategy`
> **Tài liệu nguồn:** `docs/10-test-strategy.md` (Mục 11, 23, 29), `docs/11-roadmap.md` (Mục 10), `docs/parallel-delivery/acceptance-matrix.yaml` (R21, R22, R25; Gates G04, G05, G06)
> **Phương pháp luận:** Test-First / Behavioral TDD (`SPEC` -> `PLAN` -> `RED` -> `IMPLEMENT` -> `GREEN` -> `VERIFY` -> `EVIDENCE`)

---

## 1. Nguyên Tắc & Kỷ Luật Kiểm Thử Bắt Buộc

1. **Chứng kiến hỏng hóc hành vi (Behavioral RED First):**
   - Trước khi viết mã sản phẩm, mỗi ca kiểm thử phải chạy và thất bại vì vi phạm assertions nghiệp vụ/hợp đồng (`Behavioral RED`), tuyệt đối không chấp nhận RED do lỗi import, lỗi cấu hình môi trường, hoặc thiếu binary (`Invalid Setup Failure`).
2. **Kiểm thử trên PostgreSQL Disposable Thật (Real DB Isolation):**
   - Không dùng SQLite hay in-memory mock để thay thế PostgreSQL cho các kiểm thử liên quan đến transactions, Unit of Work, outbox, concurrency, hoặc unique constraints.
   - Mỗi test function hoặc test suite sử dụng database tạm thời riêng biệt (`function-scoped disposable database`), tự động dọn dẹp sạch sẽ sau khi chạy xong (`0 orphan databases`).
3. **Kiểm thử Drive Adapter qua Sandbox Cô Lập & Checkpoint Tài Khoản Thật (Gate G04):**
   - Các bài kiểm thử unit/local sử dụng local mock sandbox mô phỏng chính xác giao thức HTTP/OAuth, header, timeout và mã lỗi `409 Conflict` của Google Drive.
   - Bài nghiệm thu tích hợp Gate G04 bắt buộc chạy trên 4 tài khoản Google Drive thử nghiệm thực tế (`real test accounts`), kiểm chứng upload resumable, tính toàn vẹn byte và cơ chế phân vùng StorageArea.
4. **Cấm dùng Mock để vượt qua cổng kiểm tra bảo mật & toàn vẹn:**
   - Tuyệt đối không mock kiểm tra mã băm SHA-256 toàn vẹn, quy trình cô lập OS vault DPAPI, hoặc cơ chế kiểm định an toàn hình ảnh.
5. **Kỷ luật Targeted Test (Zero Waste Execution):**
   - Trong quá trình phát triển và sửa lỗi, chỉ chạy đúng lệnh kiểm thử mục tiêu được chỉ định; chỉ chạy toàn bộ bộ kiểm thử tích hợp khi bước vào giai đoạn tổng hợp hồ sơ evidence.

---

## 2. Danh Mục Các Test Oracle Bắt Buộc (Mandatory Test Oracles)

### 2.1. Nhóm Lưu Trữ, Artifact & Đồng Bộ Drive (R21, R22, Gate G04, ADR-0006)

| Mã Kiểm Thử | Tình huống kích hoạt (Scenario) | Hành vi mong đợi & Oracle bắt buộc (Expected Oracle) |
|---|---|---|
| `TST-STO-SYNC-001` | Khai báo artifact version mới: cùng dòng byte với version đã có vs dòng byte khác biệt | Cùng byte trả về đúng `ArtifactVersionId` hiện có; khác byte tạo version mới; tuyệt đối cấm ghi đè byte cũ (`overwrite forbidden`) |
| `TST-STO-SYNC-002` | Upload binary lên Google Drive với pre-generated file ID; thực hiện retry thao tác | Retry cùng upload giữ nguyên file ID; phản hồi `409 Conflict` kích hoạt đối chiếu object hiện hữu thay vì tự suy đoán thành công |
| `TST-STO-SYNC-003` | Upload gặp timeout mạng trước, trong hoặc sau khi byte được truyền đến Google Drive | Chuyển trạng thái sang `OUTCOME_UNKNOWN`; thực hiện đối chiếu qua file ID và hash; tuyệt đối không retry mù quáng làm nhân bản tệp |
| `TST-STO-SYNC-004` | Yêu cầu dọn dẹp tệp cục bộ khi tệp chưa được xác thực toàn vẹn trên Google Drive | Từ chối xóa ngay lập tức (`FAIL_CLOSED_NOT_VERIFIED_ON_CLOUD`); bảo vệ bản ghi cục bộ duy nhất không bị mất |
| `TST-STO-SYNC-005` | Materialize tài nguyên về máy trạm phục vụ render; vượt quá giới hạn working set | Giới hạn working set mặc định tối đa 5 video theo chính sách; render engine chỉ nhận artifact local đã verify hash SHA-256; chặn path traversal ngoài staging root |
| `TST-STO-SYNC-006` | Máy trạm bị crash đột ngột; khôi phục qua SQLite local journal và recovery epoch mới | Journal khôi phục đúng tiến trình; các lệnh, kết quả hoặc cleanup authorization từ epoch cũ bị vô hiệu hóa fail-closed; đối chiếu phát hiện orphan upload |
| `TST-STO-SYNC-007` | Thực thi lệnh dọn dẹp tệp (`CleanupAuthorization`) kiểm tra đầy đủ 5 điều kiện an toàn | Chỉ xóa khi thỏa mãn: staging/cache, không có lease active, đã verify cloud, đúng recovery epoch, và resolved path nằm trọn trong staging root |
| `TST-STO-SYNC-008` | Phân bổ đường dẫn đầu ra (`AllocateOutputPath`) cho các session trong ngày | Phiên hoàn thành đầu tiên tạo `YY-MM-DD`, phiên kế tạo `YY-MM-DD (1)`; session không có video hoàn thành không tạo folder; giữ ký tự hashtag `#` |

---

### 2.2. Nhóm Danh Mục Media & Hook (R25, Gate G06, INV-008, INV-012, INV-015)

| Mã Kiểm Thử | Tình huống kích hoạt (Scenario) | Hành vi mong đợi & Oracle bắt buộc (Expected Oracle) |
|---|---|---|
| `TST-CAT-MED-001` | Nhập media discovery từ bài viết thu thập hoặc mạng xã hội | Hỗ trợ một byte có nhiều provenance; một media logic có nhiều rendition; ghi nhận đầy đủ phả hệ và canonical fingerprint |
| `TST-CAT-MED-002` | Nguồn gốc tin tức bị vô hiệu hóa (`DISABLED`) hoặc xóa (`REMOVED_TOMBSTONE`) | Toàn bộ media lịch sử đã thu thập vẫn truy vấn và sử dụng được bình thường; không bị mất tính hợp lệ khai thác (`INV-015`) |
| `TST-CAT-HOOK-001` | Nhập visual hook và audio hook độc lập từ người dùng; chỉnh sửa tags/metadata | Lưu trữ và index độc lập visual hook và audio hook; cho phép sửa metadata trên Admin UI mà không sửa byte tại chỗ; không bắt cặp cố định |
| `TST-CAT-HOOK-002` | Sinh kế hoạch sản xuất video (`ProductionPlan`) kiểm tra thumbnail candidate | 100% kế hoạch phải có thumbnail candidate xuất hiện trong khoảng thời gian hook (0-3s); hỗ trợ crop focus và overlay intent (icon, mũi tên, câu hỏi) |
| `TST-CAT-USG-001` | Video hoàn thành, Orchestrator commit completion Unit of Work trong PostgreSQL | `MediaUsage` được ghi nhận nguyên tử trong cùng transaction hoàn tất; rollback completion tự động rollback usage counter; render thử thất bại không tính production usage |
| `TST-CAT-QRY-001` | AI kịch bản (Module D) truy vấn danh sách ứng viên media theo chủ đề/thực thể | Trả về điểm thành phần chi tiết và bằng chứng; không trả điểm mờ duy nhất; Module D chịu trách nhiệm ghi nhận lý do chọn (`selection_rationale`) |
| `TST-CAT-SUP-001` | Video job yêu cầu tải bổ sung media (`RequestSupplementalMedia`) khi thiếu ảnh/clip | Cho phép tìm tải theo job cụ thể; không bị giới hạn bởi quy tắc quét định kỳ "mỗi nguồn 1 lần/ngày"; kiểm tra đầy đủ provenance |

---

### 2.3. Nhóm Đánh Giá An Toàn Hình Ảnh & Probe Kỹ Thuật (R25, CT-STATE-006, Năng lực E)

| Mã Kiểm Thử | Tình huống kích hoạt (Scenario) | Hành vi mong đợi & Oracle bắt buộc (Expected Oracle) |
|---|---|---|
| `TST-MED-SFT-001` | Kiểm thử bộ ảnh nhạy cảm (Sensitive Image Set): safe, trẻ em, máu me, vũ khí, uncertain, unreadable | Phân loại chính xác theo CT-STATE-006; tuyệt đối không ánh xạ `UNCERTAIN` hoặc `DETECTION_FAILED` thành `SAFE` |
| `TST-MED-SFT-002` | Áp dụng biến đổi an toàn (blur/recolor) đối với ảnh vs video clip nguồn | Áp dụng biến đổi an toàn tạo rendition mới cho ảnh nhạy cảm; tuyệt đối KHÔNG chạy biến đổi làm mờ/đổi màu an toàn lên video clip nguồn |
| `TST-MED-PRB-001` | Probe thông số kỹ thuật tệp media nguồn qua FFprobe/magic bytes | Nhận diện đúng codec, kích thước, fps, audio presence; phát hiện tệp hỏng (`corrupt`); không tin tưởng extension hoặc MIME header giả mạo |

---

## 3. Ma Trận Phân Rã Gói Công Việc (Work Packages C0..C5, I0..I6, CI7)

```
C0/I0 (Contract Closure & Fixtures)
 |-- C1 (Media Discovery & Provenance) ----+
 |                                         |-- C2 (Hook Catalog) --> C3 (Thumbnails) --> C4 (AI Queries) --> C5 (UoW Usage)
 |-- I1 (ArtifactVersion & Immutability) --+                                                                        |
      |-- I2 (Google Drive Sync) --> I3 (Desktop Materialization) --> I4 (Local Journal) --> I5 (Cleanup) --> I6 (Output Path)
                                                                                                                   |
                                                                         CI7 (Integration Gate G04/G05/G06) <------+
```

| Gói | Nội dung thực thi chính | Tệp tin kiểm thử mục tiêu (Targeted Test File) | Lệnh chạy kiểm thử mục tiêu |
|---|---|---|---|
| `C0` / `I0` | Đóng hợp đồng C-I, validate schema JSON và bộ fixtures mẫu | `tests/unit/catalog/test_c0_contract_fixtures.py` | `python -m unittest tests/unit/catalog/test_c0_contract_fixtures.py` |
| `C1` | Đăng ký Media discovery, đa provenance, canonical fingerprint | `tests/unit/catalog/test_c1_media_discovery.py` | `python -m unittest tests/unit/catalog/test_c1_media_discovery.py` |
| `C2` | Danh mục Visual & Audio Hooks độc lập, cập nhật metadata | `tests/unit/catalog/test_c2_hook_catalog.py` | `python -m unittest tests/unit/catalog/test_c2_hook_catalog.py` |
| `C3` | Thumbnail candidates trong vùng hook, crop focus, overlay intent | `tests/unit/catalog/test_c3_thumbnail_candidates.py` | `python -m unittest tests/unit/catalog/test_c3_thumbnail_candidates.py` |
| `C4` | Truy vấn candidate cho AI kịch bản, điểm thành phần, selection rationale | `tests/unit/catalog/test_c4_candidate_queries.py` | `python -m unittest tests/unit/catalog/test_c4_candidate_queries.py` |
| `C5` | Ghi nhận MediaUsage nguyên tử trong PostgreSQL completion UoW | `tests/unit/catalog/test_c5_media_usage_uow.py` | `python -m unittest tests/unit/catalog/test_c5_media_usage_uow.py` |
| `I1` | Khai báo ArtifactVersion, tính bất biến SHA-256, cấm overwrite | `tests/unit/storage/test_i1_artifact_version.py` | `python -m unittest tests/unit/storage/test_i1_artifact_version.py` |
| `I2` | Upload Google Drive, pre-generated file ID, timeout & đối chiếu | `tests/unit/storage/test_i2_drive_sync.py` | `python -m unittest tests/unit/storage/test_i2_drive_sync.py` |
| `I3` | Materialize desktop staging, giới hạn working set <= 5 video | `tests/unit/storage/test_i3_desktop_materialize.py` | `python -m unittest tests/unit/storage/test_i3_desktop_materialize.py` |
| `I4` | SQLite local journal, crash recovery và recovery epoch fencing | `tests/unit/storage/test_i4_sqlite_journal.py` | `python -m unittest tests/unit/storage/test_i4_sqlite_journal.py` |
| `I5` | Cleanup authorization engine, kiểm tra 5 điều kiện và staging root | `tests/unit/storage/test_i5_cleanup_authorization.py` | `python -m unittest tests/unit/storage/test_i5_cleanup_authorization.py` |
| `I6` | Phân bổ đường dẫn đầu ra, đặt tên session YY-MM-DD, giữ hashtag | `tests/unit/storage/test_i6_output_path_allocator.py` | `python -m unittest tests/unit/storage/test_i6_output_path_allocator.py` |
| `CI7` | Tích hợp hệ thống, kiểm chứng Gate G04/G05/G06 trên tài khoản Drive thật | `tests/integration/storage/test_ci7_acceptance_gate.py` | `python -m unittest tests/integration/storage/test_ci7_acceptance_gate.py` |

> **Lưu ý ranh giới đường dẫn kiểm thử & Gate thực thi (Test Paths & Execution Gate):**
> - Đường dẫn `tests/unit/catalog/**` đã được bảo vệ bởi `PATH-SRC-CATALOG` và `LOCK-SRC-CATALOG` của Phân hệ C trong registry.
> - Các đường dẫn kiểm thử của Phân hệ I (`tests/unit/storage/**` và `tests/integration/storage/**`) là **proposed paths (đường dẫn đề xuất)**, hiện tại **chưa có ownership entry** trong `docs/parallel-delivery/ownership-and-locks.yaml`.
> - Khóa `LOCK-SRC-STORAGE` bảo vệ các đường dẫn này là **proposed lock chưa được đăng ký** trong registry. Tuyệt đối không mượn khóa của module khác thay thế và không tự sửa registry.
> - Kế hoạch kiểm thử này xác lập ở trạng thái `planned_test_strategy`, **không khẳng định package đã khóa đầy đủ ranh giới**.
> - Việc tạo tệp kiểm thử và thực thi các gói công việc implementation C0..C5, I0..I6 và CI7 bị **BLOCKED** fail-closed cho đến khi:
>   1. Gate `GATE-M4-I-OWNERSHIP-LOCK` được Control / Authority Owner phê duyệt và đăng ký chính thức vào `ownership-and-locks.yaml`.
>   2. Checkpoint `USER-CKPT-M4` được Người dùng phê duyệt chính thức mở Milestone M4.

---

## 4. Kiểm Thử Hồi Quy Toàn Hệ Thống (Regression Invariants)

Bất kỳ thay đổi nào trong Phân hệ C và Phân hệ I cũng bắt buộc phải vượt qua các bài kiểm thử hồi quy:
1. **Kiểm tra hồi quy Milestone M1:**
   - Đảm bảo 93/93 bài test M1 đạt `PASS` (`93 passed, 0 skipped`).
2. **Kiểm tra hồi quy Milestone M2:**
   - Bộ kiểm thử `tests/m2/**` đạt `PASS`.
   - Admin UI build sạch sẽ, không có trailing whitespace.
3. **Quét dữ liệu nhạy cảm (Secret Scanner):**
   - Không chứa bất kỳ khóa bí mật, Service Account JSON raw, private key, token dạng plain-text nào trong mã nguồn và dữ liệu test fixture.

---

## 5. Bằng Chứng Nghiệm Thu Cần Sinh Ra (Required Evidence Artifacts)

Khi hoàn tất gói công việc hoặc toàn bộ M4-CI, hồ sơ nghiệm thu bắt buộc phải chứa các tệp tin có mã băm xác thực:

```
docs/milestones/m4-media/evidence/m4-ci/
 |-- red-observations.md       # Quan sát bằng chứng các test bị fail trước khi code
 |-- targeted-test-report.txt  # Kết quả chạy bộ targeted test sau khi hoàn thiện code
 |-- r21-drive-sync.json       # Bằng chứng kiểm chứng R21 (Lưu trữ bất biến & sync Drive)
 |-- r22-retention.json        # Bằng chứng kiểm chứng R22 (Không xóa file trước khi sync)
 |-- r25-safety-filter.json    # Bằng chứng kiểm chứng R25 (Bộ lọc an toàn ảnh & giữ nguyên clip)
 |-- m1-regression-report.txt  # Báo cáo 93/93 tests M1 đạt GREEN
 |-- secret-scan.json          # Báo cáo quét 0 credentials
 |-- hashes.sha256             # Bảng băm SHA-256 toàn vẹn của mọi artifacts
 |-- status.json               # Trạng thái máy đọc: {"status": "PASS", "gate": "G04_G06"}
```

---

## 6. Tiêu Chí Hoàn Thành (Definition of Done)

Gói công việc M4-CI chỉ được xem là hoàn tất khi:
1. 100% các bài kiểm thử unit và integration tương ứng đạt `GREEN`.
2. Không vi phạm bất kỳ invariant nào (`INV-008`, `INV-011`, `INV-012`, `INV-015`, `ARCH-008`).
3. Xác thực toàn vẹn đồng bộ Google Drive trên tài khoản thật đạt Gate G04.
4. Kiểm thử hồi quy M1 và M2 đạt `PASS` 100%.
5. Cây làm việc git sạch sẽ (`git diff --check` không có trailing whitespace hoặc CRLF).
6. Sol-Lead review read-only gửi `ACCEPT`.
7. Astra-Lead supreme audit read-only gửi `PASS`.

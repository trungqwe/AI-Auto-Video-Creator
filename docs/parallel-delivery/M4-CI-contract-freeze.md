# Đóng Băng Hợp Đồng Giao Tiếp: M4-CI (Contract Freeze Specification)

> **Mã gói (Package ID):** `M4-CI` (Chuyển tiếp từ `M4-CI-TEMPLATE`)
> **Trạng thái đóng băng:** `frozen_design_baseline`
> **Thẩm quyền quy định:** CT-CMN-012, `docs/parallel-delivery/contract-registry.yaml`, `operating-model.md`
> **Ràng buộc bất biến:** Bắt buộc khớp chính xác mã băm SHA-256 nguồn; sai mã băm hoặc sai nguồn định nghĩa phải fail-closed.

---

## 1. Nguyên Tắc Đóng Băng Hợp Đồng (Contract Freeze Principles)

1. **Khóa bất biến (Immutable Baseline):** Mọi công việc chuẩn bị và triển khai tương lai của Phân hệ C (Kho Media & Hook) và Phân hệ I (Lưu trữ, Artifact & Đồng bộ Google Drive) bắt buộc phải dựa trên đúng các phiên bản hợp đồng đã được đóng băng dưới đây.
2. **Fail-Closed khi sai lệch:** Nếu phát hiện mã băm tệp nguồn thực tế khác với mã băm đã đóng băng, toàn bộ chu trình kiểm thử và tích hợp phải dừng ngay lập tức (`FAIL_CLOSED_CONTRACT_DRIFT`).
3. **Cấm sửa tệp nguồn hợp đồng:** Nghiêm cấm mọi sửa đổi đối với các tệp nguồn trong `docs/09-contracts/**` trong phạm vi của gói này (`LOCK-CONTRACT-SOURCE`). Mọi đề xuất thay đổi hợp đồng phải thông qua quy trình RFC / ADR kiến trúc cấp cao.

---

## 2. Bảng Đóng Băng Các Hợp Đồng Liên Quan (Exact Frozen Contract Revisions)

| Mã Hợp Đồng (Contract ID) | Tệp Nguồn Định Nghĩa (Defining Source) | Prefixes | Owner | Exact Frozen SHA-256 |
|---|---|---|---|---|
| `CONTRACT-CONTENT-MEDIA` | `docs/09-contracts/05-content-media-contracts.md` | `CT-MED-*`, `CT-HOOK-*` | C (Co-owners: B, I) | `ea6a3723dece842d132f634d44c32eb301fbc98b43b61d24b5c32c907782e4cf` |
| `CONTRACT-STORAGE` | `docs/09-contracts/10-storage-contracts.md` | `CT-STO-*` | I | `6ab6f60bc2760ea9017ca0406e0053dc859cc06c1f0c80fff7e944d03d5e02ce` |
| `CONTRACT-COMMON` | `docs/09-contracts/00-common-contract.md` | `CT-CMN-*` | CROSS-CUTTING | `dfdce8db13d5f1d1f286ccd233a66caf39f48552da2dbbad26692fde7be978e8` |
| `CONTRACT-STATE-MACHINES` | `docs/09-contracts/12-state-machines.md` | `CT-STATE-*` | G (Co-owners: C, I) | `2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28` |
| `CONTRACT-WORKFLOW-EXECUTION` | `docs/09-contracts/03-workflow-and-execution.md` | `CT-WF-*` | G | `0fca25f2bc037a4c2bc58b844079dace8c19a9fd5af5c0ce8ad75e421bc2dc83` |
| `CONTRACT-CONFIG-SECURITY` | `docs/09-contracts/11-configuration-security-contracts.md` | `CT-CFG-*`, `CT-SEC-*`, `CT-CAP-*`, `CT-AI-ROUTE-*` | J | `989d9ef22c2096f56453722f059efc1427a3018e64c1a7f67a8d514f55c69645` |
| `CONTRACT-MEDIA-PROCESSING` | `docs/09-contracts/07-media-processing-contracts.md` | `CT-PROC-*`, `CT-TTS-*`, `CT-SUB-*`, `CT-AUD-*` | E | `c5f7abaea422916165d59f8a5508817729d21035cffd663123a913c49365cf49` |

---

## 3. Chi Tiết Giao Diện CONTRACT-CONTENT-MEDIA (Bound to Phân Hệ C)

### 3.1. Nhập phát hiện media (Media Discovery Registration)
- **`CT-MED-001` (`RegisterMediaDiscovery`):**
  - Input: `discovery_id`, `source_refs`, `article_refs`, `event_refs`, `original_locator`, `media_kind_candidate`, `caption`, `observed_time`, `provenance_chain`, `content_hash`, `relation` (hero image, inline image, embedded clip, official social clip).
  - Output: `MediaAssetRef`, `disposition` (`new_asset`, `new_provenance`, `duplicate_observation`, `rejected`), `acquisition_operation`.
  - Bất biến: Một byte có thể có nhiều provenance (xuất xứ nguồn gốc). Một media logic có thể có nhiều rendition/artifact version. Trùng byte không làm mất lịch sử provenance ban đầu.

### 3.2. Chế độ xem MediaAsset và Đăng ký Rendition
- **`CT-MED-002` (`MediaAssetView`):**
  - View tổng hợp cấu trúc đa chiều:
    - Identity: `media_asset_id`, kind, canonical fingerprint.
    - Provenance: source/article/event refs, original URL, observed time.
    - Semantics: people/entities, topics, scene/action, OCR, language, tags.
    - Technical: dimensions, duration, codecs, frame rate, audio presence.
    - Safety: assessment state, reasons, model/reviewer revision.
    - Rights/Risk: known, unknown, disputed; evidence refs.
    - Availability: cloud/local/original/processed state.
    - Renditions: original, normalized, blurred, recolored, thumbnail, extracted frame.
    - Usage: count, recent jobs, role trong video.
  - Bất biến: Trạng thái bản quyền chưa chắc chắn (`unknown` / `disputed`) không tự động chặn quyền sử dụng theo quyết định người dùng, nhưng bắt buộc lưu vết và truy vấn được.
- **`CT-MED-003` (`RegisterRendition`):**
  - Input: `source_media_ref`, `artifact_version`, `transformation_specification_revision`, `processor_version`, `output_artifact_ref`, `quality_report`, `safety_state`, `lineage`.
  - Output: `RenditionRef` bất biến.
  - Bất biến: Không sửa byte của rendition cũ tại chỗ. Cùng transformation và cùng input hash có thể deduplicate theo fingerprint.

### 3.3. Danh mục Hook Visual & Hook Audio
- **`CT-HOOK-001` (`ImportHook`):**
  - Hai phân loại hook độc lập:
    - `visual_hook`: Video clip do người dùng cung cấp, đã xử lý làm mờ chủ thể, không bắt buộc audio.
    - `audio_hook`: Bản thu âm thanh do người dùng cung cấp, được lập chỉ mục (index) riêng biệt.
  - Input: `artifact_ref`, `hook_kind`, `metadata_tags`, `index_text`, `enabled_state`, `user_provenance`, `technical_metadata`.
  - Bất biến: Visual hook và audio hook không bắt cặp cứng cố định. Phân hệ D có toàn quyền phối ghép theo ngữ cảnh kịch bản.
- **`CT-HOOK-002` (`UpdateHookMetadata`):**
  - Cho phép người dùng chỉnh sửa tags, mô tả, ghi chú, trạng thái bật/tắt trên Admin UI.
  - Bất biến: Tuyệt đối không sửa byte vật lý tại chỗ. Job đã tạo snapshot tiếp tục dùng hook revision cũ nếu artifact version còn hợp lệ.

### 3.4. Ứng viên Thumbnail và Vùng Thời Gian Hook
- **`CT-MED-004` (`ThumbnailCandidate`):**
  - Mỗi kế hoạch sản xuất video (`ProductionPlan`) bắt buộc phải có một thumbnail xuất hiện trong khoảng thời gian hook (0-3 giây đầu) để định hình chủ đề.
  - Schema ứng viên gồm: `subject_refs`, `event_relation`, `crop_focus`, `overlay_intent` (icon, mũi tên, dấu hỏi, dấu cảm thán), `safety_state`, `provenance`, `similarity_fingerprint`.
  - Phân hệ C chỉ cung cấp candidate và metadata; việc phối overlay sáng tạo thuộc thẩm quyền của D và F.

### 3.5. Truy vấn ứng viên cho Kịch bản AI
- **`CT-MED-005` (`QueryMediaCandidates`):**
  - Input: `production_snapshot_ref`, `scene_intent`, `entity_context`, `media_kinds`, `technical_constraints`, `safety_policy_revision`, `recency_diversity_preferences`, `excluded_recent_usage_refs`, cursor/limit.
  - Output: Danh sách candidate kèm điểm thành phần chi tiết (`semantic_match`, `technical_fitness`, `availability`, `safety_status`, `usage_summary`, `reason_codes`).
  - Bất biến: Phân hệ C trả điểm thành phần và bằng chứng, không trả điểm mờ duy nhất. Phân hệ D chịu trách nhiệm quyết định lựa chọn cuối cùng và ghi nhận lý do chọn (`selection_rationale`).
- **`CT-MED-006` (`QueryHookCandidates`):**
  - Visual hook và Audio hook được truy vấn độc lập theo: chủ đề, cảm xúc, nhịp điệu, thực thể, độ dài, revision bật/tắt và lịch sử sử dụng gần đây.
- **`CT-MED-007` (`RequestSupplementalMedia`):**
  - Tải tài nguyên bổ sung theo nhu cầu của một video job cụ thể.
  - Bất biến: Không bị giới hạn bởi quy tắc "mỗi nguồn 1 lần/ngày" của chu kỳ quét định kỳ Phân hệ A. Mọi tài nguyên bổ sung vẫn phải tuân thủ provenance và kiểm tra an toàn.

### 3.6. Ghi nhận lượt sử dụng Media (`MediaUsage`)
- **`CT-MED-008` (`RecordMediaUsage`):**
  - Ghi nhận lượt sử dụng media cho video hoàn thành thông qua application port của Module C trong cùng một Unit of Work PostgreSQL với lệnh commit hoàn tất của Orchestration (Module G).
  - Bất biến: Phân hệ G điều phối nhưng không ghi trực tiếp vào bảng của C. Lượt sử dụng chỉ hiển thị và có hiệu lực khi toàn bộ transaction commit thành công. Rollback completion cũng tự động rollback media usage.
- **`CT-MED-009` (`ResolveRenderableVersion`):**
  - Giải quyết version render được với hash, kích thước và vị trí artifact local đã xác thực.
  - Bất biến: Nguồn gốc bị tắt hoặc xóa (`REMOVED_TOMBSTONE`) không làm mất tính hợp lệ khai thác của media lịch sử. Artifact bị thiếu hoặc sai lệch hash bị chặn render fail-closed.

---

## 4. Chi Tiết Giao Diện CONTRACT-STORAGE (Bound to Phân Hệ I)

### 4.1. Mô hình Ba Khái Niệm Phân Tách
1. **`Artifact`:** Đối tượng logic đại diện cho tài nguyên (ảnh gốc, derivative rendition, voice audio, video hoàn chỉnh).
2. **`ArtifactVersion`:** Dòng byte bất biến (immutable byte stream), có mã băm SHA-256 xác định và phả hệ lineage.
3. **`ArtifactLocation`:** Bản sao vật lý của một version trên đĩa cục bộ, bộ đệm cache hoặc cloud namespace (Google Drive).
- Bất biến: Các phân hệ khác chỉ tham chiếu qua `ArtifactVersion`, tuyệt đối không dùng tên file hoặc đường dẫn Google Drive làm định danh nghiệp vụ.

### 4.2. Khai báo Version và Đăng ký Vị trí
- **`CT-STO-001` (`DeclareArtifactVersion`):**
  - Input: `artifact_kind`, `owner_resource_ref`, `content_hash` (SHA-256), `size_bytes`, `media_type`, `lineage_refs`, `retention_class`, `sensitivity_class`, `storage_class`.
  - Output: `ArtifactVersionId`, matching existing version hoặc version mới, operation yêu cầu.
  - Bất biến: Cùng dòng byte và cùng chính sách định danh quy về version hiện có. Byte khác luôn sinh version mới, tuyệt đối cấm ghi đè (overwrite forbidden).
- **`CT-STO-002` (`RegisterArtifactLocation`):**
  - Đăng ký bản sao vật lý gồm: `storage_area_id` (Google Drive account/namespace), `provider_object_id` (Drive file ID), `logical_path`, `observed_hash`, `observed_size`, `verification_state`, `lease_expiry`, `recovery_epoch`.
  - Bất biến: Không đưa raw credentials vào bản ghi vị trí. Provider locator chỉ do Storage Adapter của I giải thích.

### 4.3. Lưu trữ Lên Cloud & Cơ Chế Google Drive (ARCH-008, ADR-0006)
- **`CT-STO-003` (`PersistArtifactToCloud`):**
  - Cơ chế đồng bộ Google Drive:
    1. Chuẩn bị `OperationReceipt` trong PostgreSQL trước khi upload.
    2. Cấp trước Google Drive File ID (`pre-generated file ID`) và lưu mapping `artifact_version -> file_id` trước khi truyền byte.
    3. Retry cùng thao tác và cùng byte giữ nguyên file ID; phản hồi `409 Conflict` phải kích hoạt kiểm tra đối tượng hiện hữu thay vì tự suy đoán thành công.
    4. Timeout mạng chuyển trạng thái sang `OUTCOME_UNKNOWN`. Tiến hành đối chiếu (reconciliation) qua file ID, metadata hash và kích thước trước khi thực hiện bất kỳ hành động nào.
    5. Chỉ sau khi xác minh toàn vẹn byte trên cloud thành công mới phát sự kiện `ArtifactLocationVerified`.
  - Bất biến: Tuyệt đối không xóa tệp cục bộ duy nhất trước khi có bằng chứng `ArtifactLocationVerified` trên cloud.

### 4.4. Hiện thực hóa Lên Desktop & Kiểm soát Working Set (CT-STO-004)
- **`CT-STO-004` (`MaterializeArtifactSet`):**
  - Tải tài nguyên về máy trạm phục vụ render:
    1. Chỉ tải tài nguyên gần lượt xử lý của job.
    2. Giới hạn working set mặc định theo chính sách là tài nguyên cho tối đa 5 video trong một thời điểm (`5-video working set limit`).
    3. Prefetch tài nguyên cho video kế tiếp chỉ được thực hiện khi không vi phạm ngân sách đĩa và I/O.
    4. Render engine chỉ được nhận đường dẫn artifact đã xác thực mã băm SHA-256 trên đĩa cục bộ.
    5. Cấm truy cập hoặc ghi file ngoài đường dẫn staging root do Phân hệ I cấp phát.

### 4.5. SQLite Local Journal & Khôi Phục Sự Cố (CT-STO-005, CT-STO-009)
- **`CT-STO-005` (`LocalJournalEntry`):**
  - Lưu trữ trên máy trạm gồm: `job_id`, `stage_id`, `artifact_version`, `local_location`, `operation_key`, `generation_lease`, `checkpoint_hash`, `recovery_epoch`.
  - Bất biến: Journal là phương tiện phục hồi sau crash trên desktop; PostgreSQL là nguồn sự thật nghiệp vụ có thẩm quyền. Journal không tự ý phát hành sự kiện hoàn tất `VideoCompleted`.
- **`CT-STO-009` (`RecoveryEpoch`):**
  - Mỗi lần khôi phục/tái tạo hệ thống (restore/rebuild) bắt buộc sinh `recovery_epoch` mới trước khi mở writer.
  - Bất biến: Mọi lệnh, kết quả, sự kiện hoặc lệnh ủy quyền dọn dẹp (`CleanupAuthorization`) từ epoch cũ đều bị vô hiệu hóa fail-closed trong epoch mới.

### 4.6. Đồng bộ Video Đầu Ra & Ủy Quyền Dọn Dẹp (Cleanup)
- **`CT-STO-006` (`PersistVideoOutput`):**
  - Video đầu ra có storage class bền vững và bắt buộc được đồng bộ lên Google Drive. Orchestration (Module G) chỉ commit `VideoJobCompleted` khi đã có receipt xác minh vị trí cloud của video.
- **`CT-STO-007` (`RequestCleanupEvaluation`) & `CT-STO-008` (`CleanupAuthorization`):**
  - Lệnh ủy quyền dọn dẹp bất biến gồm: vị trí file chính xác, artifact version, mã băm, bằng chứng hoàn tất trên cloud, thời hạn hiệu lực, recovery epoch.
  - Phân hệ I chỉ thực hiện xóa tệp vật lý khi thỏa mãn đồng thời 5 điều kiện:
    1. Tệp thuộc phân vùng staging/cache được phép xóa.
    2. Không có lease hoặc consumer nào đang hoạt động trên tệp.
    3. Bản ghi hoàn tất và tệp reusable/output đã được xác thực toàn vẹn trên cloud.
    4. Lệnh ủy quyền dọn dẹp còn hạn và cùng `recovery_epoch` hiện hành.
    5. Đường dẫn tuyệt đối đã giải quyết (`resolved absolute path`) nằm trọn vẹn trong thư mục staging root dự kiến.

### 4.7. Phân bổ Lưu trữ Google Drive & Đặt Tên Tệp
- **`CT-STO-010` (`StoragePlacementPolicy`):**
  - 4 tài khoản Google Drive (tổng danh nghĩa 20 TB do người dùng cấp) được phân vùng logic theo loại dữ liệu:
    - Tài khoản 1: Nguồn gốc và bài viết thu thập (`original_sources`).
    - Tài khoản 2: Thư viện tài nguyên tái sử dụng và hooks (`reusable_assets_hooks`).
    - Tài khoản 3: Tệp phái sinh trung gian và cache (`derivatives_temporary`).
    - Tài khoản 4: Video thành phẩm xuất bản và bằng chứng nghiệm thu (`outputs_evidence`).
- **`CT-STO-011` (`AllocateOutputPath`):**
  - Thư mục phiên hoàn thành đầu tiên trong ngày: `YY-MM-DD`.
  - Các phiên hoàn thành tiếp theo trong cùng ngày: `YY-MM-DD (1)`, `YY-MM-DD (2)`...
  - Bất biến: Không tạo thư mục sản phẩm hợp lệ cho session không có video nào hoàn thành. Giữ nguyên ký tự hashtag `#` khi filesystem hỗ trợ, sanitize an toàn các ký tự cấm.

---

## 5. Ranh Giới Giao Tiếp Then Chốt (Key Interface Boundaries)

### 5.1. Ranh giới Danh mục vs Lưu trữ Byte: `interface_c_i`
- Hợp đồng: `CONTRACT-CONTENT-MEDIA` và `CONTRACT-STORAGE`.
- Phân định: Module C sở hữu toàn bộ metadata danh mục, tags, điểm phân tích, phân loại hook và số lượt sử dụng; Module I sở hữu lưu trữ byte vật lý, kiểm chứng mã băm SHA-256, đồng bộ Google Drive và thi hành lệnh xóa.
- Bất biến: C tuyệt đối không gọi filesystem để ghi/xóa byte trực tiếp; I tuyệt đối không sửa đổi quan hệ metadata hoặc đánh giá hook.

### 5.2. Đơn vị Công việc Hoàn tất: `interface_g_c_i`
- Hợp đồng: `CONTRACT-DOMAIN-EVENTS`, `CONTRACT-ORCHESTRATION`, `CONTRACT-STORAGE`.
- Quy chuẩn: PostgreSQL Unit of Work phía caller (Module G) điều phối nguyên tử việc hoàn tất VideoJob, gọi Port của C để tăng `MediaUsage` và Port của I để ghi `ArtifactLocation`. Cấm ghi chéo bảng giữa các aggregate.

### 5.3. Xử lý Kỹ thuật & Phái sinh: `interface_e_c_i`
- Hợp đồng: `CONTRACT-MEDIA-PROCESSING`, `CONTRACT-CONTENT-MEDIA`, `CONTRACT-STORAGE`.
- Quy chuẩn: Module E thực hiện trích xuất thông số kỹ thuật (probe), phát hiện ảnh nhạy cảm và tạo bản phái sinh (rendition). Kết quả phân tích metadata giao cho C, tệp byte kết quả giao cho I tạo `ArtifactVersion` mới.

---

## 6. Máy Trạng Thái Cốt Lõi (Bound State Machines - CONTRACT-STATE-MACHINES)

### 6.1. Vòng đời Thu nạp & Bản phái sinh: `CT-STATE-005`
- Discovery: `DISCOVERED` -> `ACQUIRING` -> `CATALOGED` | `FAILED`.
- Rendition: `DECLARED` -> `PROCESSING` -> `READY` | `FAILED` | `OUTCOME_UNKNOWN`.
- Trục Availability độc lập: `AVAILABLE`, `MISSING`, `CORRUPT`, `RECOVERING`, `UNAVAILABLE_SOURCE`.
- Bất biến: Không gộp availability với safety state.

### 6.2. Vòng đời Đánh giá An toàn Ảnh: `CT-STATE-006`
- Đánh giá: `NOT_ASSESSED` -> `ASSESSING` -> `SAFE` | `TRANSFORM_REQUIRED` | `UNCERTAIN` | `DETECTION_FAILED` | `UNREADABLE`.
- Biến đổi (nếu yêu cầu): `TRANSFORM_REQUIRED` -> `TRANSFORMING` -> `PROCESSED_READY` | `TRANSFORM_FAILED`.
- Bất biến: Tuyệt đối không ánh xạ `UNCERTAIN`, `DETECTION_FAILED`, `TRANSFORM_FAILED` thành `SAFE`. Video clip không chạy biến đổi làm mờ/đổi màu an toàn.

### 6.3. Vòng đời Biên nhận Thao tác: `CT-STATE-011`
- `PREPARED` -> `STARTED` -> `SUCCEEDED` | `FAILED` | `OUTCOME_UNKNOWN`.
- `OUTCOME_UNKNOWN` chỉ chuyển sang `SUCCEEDED` hoặc `FAILED` sau khi có bằng chứng đối chiếu (reconciliation evidence).

### 6.4. Vòng đời Vị trí Tệp Vật lý: `CT-STATE-012`
- `DECLARED` -> `MATERIALIZING` -> `AVAILABLE_UNVERIFIED` -> `VERIFYING` -> `VERIFIED` | `CORRUPT` | `MISSING` | `OUTCOME_UNKNOWN`.
- Từ `VERIFIED`: -> `CLEANUP_ELIGIBLE` -> `CLEANUP_AUTHORIZED` -> `DELETED`.
- Bất biến: Không có cạnh khôi phục từ `MISSING`, `CORRUPT` sang `VERIFIED` khi chưa verify lại; không có đường tắt dọn dẹp ngoài quy trình.

---

## 7. Kết Luận Khóa Bất Biến

Toàn bộ 7 hợp đồng nền tảng, các quy tắc phân định ranh giới C-I, G-C-I, các máy trạng thái và cơ chế đồng bộ Google Drive đã được đóng băng cố định. Nghiêm cấm mọi hành vi tự ý sửa đổi làm sai lệch baseline đã được phê duyệt.

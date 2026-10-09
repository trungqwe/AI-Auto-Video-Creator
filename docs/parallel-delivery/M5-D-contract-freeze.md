# Đóng Băng Hợp Đồng Giao Tiếp: M5-D (Contract Freeze Specification)

> **Mã gói (Package ID):** `M5-D` (Chuyển tiếp từ `M5-D-TEMPLATE`)
> **Trạng thái đóng băng:** `frozen_design_baseline`
> **Thẩm quyền quy định:** CT-CMN-012, `docs/parallel-delivery/contract-registry.yaml`, `operating-model.md`
> **Ràng buộc bất biến:** Bắt buộc khớp chính xác mã băm SHA-256 nguồn; sai mã băm hoặc sai nguồn định nghĩa phải fail-closed.

---

## 1. Nguyên Tắc Đóng Băng Hợp Đồng (Contract Freeze Principles)

1. **Khóa bất biến (Immutable Baseline):** Mọi công việc chuẩn bị và triển khai tương lai của Phân hệ D (Bộ não nội dung AI & Sáng tạo kịch bản / `CAP-D-SCRIPTING`) bắt buộc phải dựa trên đúng các phiên bản hợp đồng đã được đóng băng dưới đây.
2. **Fail-Closed khi sai lệch:** Nếu phát hiện mã băm tệp nguồn thực tế khác với mã băm đã đóng băng, toàn bộ chu trình kiểm thử và tích hợp phải dừng ngay lập tức (`FAIL_CLOSED_CONTRACT_DRIFT`).
3. **Cấm sửa tệp nguồn hợp đồng:** Nghiêm cấm mọi sửa đổi đối với các tệp nguồn trong `docs/09-contracts/**` trong phạm vi của gói này (`LOCK-CONTRACT-SOURCE`). Mọi đề xuất thay đổi hợp đồng phải thông qua quy trình RFC / ADR kiến trúc cấp cao.

---

## 2. Bảng Đóng Băng Các Hợp Đồng Liên Quan (Exact Frozen Contract Revisions)

| Mã Hợp Đồng (Contract ID) | Tệp Nguồn Định Nghĩa (Defining Source) | Prefixes | Owner | Exact Frozen SHA-256 |
|---|---|---|---|---|
| `CONTRACT-CREATIVE-AI` | `docs/09-contracts/06-creative-ai-contracts.md` | `CT-AI-*` (loại trừ `CT-AI-ROUTE-*`) | D | `92b74489890f1eaf3915aef809af4cff0585659842f6930bbdf11d1236861b3a` |
| `CONTRACT-SOURCE-CONTENT` | `docs/09-contracts/04-source-content-contracts.md` | `CT-SRC-*`, `CT-CNT-*` | A (Co-owner: B) | `61b075d202dd0d7729123f68f26285097be8120e2de48194d0ad2fe847701f31` |
| `CONTRACT-CONTENT-MEDIA` | `docs/09-contracts/05-content-media-contracts.md` | `CT-MED-*`, `CT-HOOK-*` | C (Co-owners: B, I) | `ea6a3723dece842d132f634d44c32eb301fbc98b43b61d24b5c32c907782e4cf` |
| `CONTRACT-CONFIG-SECURITY` | `docs/09-contracts/11-configuration-security-contracts.md` | `CT-CFG-*`, `CT-SEC-*`, `CT-AI-ROUTE-*` | J | `989d9ef22c2096f56453722f059efc1427a3018e64c1a7f67a8d514f55c69645` |
| `CONTRACT-COMMON` | `docs/09-contracts/00-common-contract.md` | `CT-CMN-*` | CROSS-CUTTING | `dfdce8db13d5f1d1f286ccd233a66caf39f48552da2dbbad26692fde7be978e8` |
| `CONTRACT-STATE-MACHINES` | `docs/09-contracts/12-state-machines.md` | `CT-STATE-*` | G (Co-owners: C, D, I) | `2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28` |
| `CONTRACT-WORKFLOW-EXECUTION` | `docs/09-contracts/03-workflow-and-execution.md` | `CT-WF-*` | G | `0fca25f2bc037a4c2bc58b844079dace8c19a9fd5af5c0ce8ad75e421bc2dc83` |
| `CONTRACT-DOMAIN-EVENTS` | `docs/09-contracts/02-domain-events.md` | `CT-EVT-*` | G | `8114a208cecca67e553345ea5574d68752323c79cf833c8c8c9fa5e2f86e7540` |
| `CONTRACT-MEDIA-PROCESSING` | `docs/09-contracts/07-media-processing-contracts.md` | `CT-PROC-*`, `CT-TTS-*`, `CT-SUB-*`, `CT-AUD-*` | E | `c5f7abaea422916165d59f8a5508817729d21035cffd663123a913c49365cf49` |
| `CONTRACT-RENDER-QUALITY` | `docs/09-contracts/08-render-quality-contracts.md` | `CT-RND-*`, `CT-QC-*` | F | `c3e35d032c0a8e721ed35bbecb5fb57f350788e8520d6e8df5ca78284199b493` |

---

## 3. Chi Tiết Giao Diện CONTRACT-CREATIVE-AI (Bound to Phân Hệ D)

### 3.1. Ranh giới dữ liệu không tin cậy & Chống Prompt Injection (CT-AI-000)
- **`CT-AI-000` (`Untrusted input boundary`):**
  - Nội dung bài viết, metadata, caption, OCR/transcript và mọi văn bản lấy từ nguồn bên ngoài là `untrusted_data`.
  - Dữ liệu này bắt buộc đặt trong trường có cấu trúc tách biệt hoàn toàn khỏi system/developer instruction.
  - Các câu lệnh tiềm ẩn nằm trong nội dung nguồn không có quyền thay đổi policy, gọi công cụ (tool invocation), tải URL, truy cập secret hoặc tự tạo resource reference.
  - Mọi tham chiếu (reference) do mô hình AI đề xuất phải được resolver độc lập kiểm tra sự tồn tại, workspace, revision và danh sách cho phép (allowlist) trước khi chấp nhận. Schema định kiểu (typed schema) không thay thế các kiểm tra an toàn này (`INV-020`).

### 3.2. Khóa nguồn sản xuất bất biến (CT-AI-001)
- **`CT-AI-001` (`BuildProductionSnapshot`):**
  - Input: Article/event/event-update refs đủ điều kiện; source/provenance revisions; media/hook candidate index revisions; config/prompt/preset policy revisions; batch/job refs; production mode (`single_article`, `multi_article_event`, `from_then_to_now`); recent variant exclusions.
  - Output: `ProductionSnapshot` chứa toàn bộ refs và revision chính xác; `source_set_fingerprint`; `configuration_bundle_fingerprint`; `eligibility_reason`; `snapshot_timestamp`; immutable `snapshot_id`.
  - Bất biến: Snapshot bắt buộc phải commit vào PostgreSQL trước lần gọi AI tạo kịch bản đầu tiên. Sau mốc này, mọi thay đổi về nguồn hoặc cấu hình chỉ áp dụng cho job chưa snapshot hoặc lần sản xuất sau; job cũ giữ nguyên bản chụp bất biến (`INV-004`).

### 3.3. Phân tích nội dung (CT-AI-002)
- **`CT-AI-002` (`AnalyzeContent`):**
  - Input: `production_snapshot_ref` và `analysis_policy`.
  - Output: `ContentAnalysis` gồm: chủ đề (topic), thực thể (entities), dòng thời gian (timeline), địa điểm (locations); các sự thật/khẳng định có bằng chứng (`source_backed facts/claims`) kèm `evidence_refs`; các điểm không chắc chắn hoặc mâu thuẫn (`uncertainties`, `contradictions`); quan hệ sự kiện và ngữ cảnh cập nhật; cờ cảnh báo rủi ro nội dung (`sensitivity/content-risk flags`); cơ hội diễn giải câu chuyện (`candidate narrative opportunities`); nhu cầu media (`media_needs`); vết mô hình/prompt (`model/prompt trace`).
  - Bất biến: Dữ liệu đầu vào giữ nguyên `trust_class` và provenance của nguồn. Không được nâng dữ liệu không tin cậy thành chỉ dẫn hệ thống. Không được xóa bỏ provenance hoặc biến điểm chưa chắc chắn thành sự thật đã xác nhận trong representation nội bộ.

### 3.4. Sinh góc kể đa dạng (CT-AI-003)
- **`CT-AI-003` (`GenerateStoryAngles`):**
  - Input: `analysis_revision`; số lượng yêu cầu từ 1 đến 3 cho mỗi tin trong một lượt (`1-3 angles per article`); lịch sử góc/kịch bản gần đây; ứng viên preset/style; `variation_policy_revision`; workspace, job/snapshot/round; tập article/event refs đã khóa; `active_variant_reservations` từ Orchestration (Module G) và `variant_registry_revision` của lần đọc nhất quán.
  - Output: Tập hợp các thực thể `StoryAngle`, mỗi góc chứa: `story_angle_id`, tiêu đề/tóm tắt (`title/summary`), câu hỏi dẫn dắt (`narrative_question`), thực thể/khung thời gian trọng tâm (`focus_entities/timeframe`), liên kết bằng chứng nguồn (`source_evidence_refs`), các yếu tố suy luận/sáng tạo dự kiến, dấu vân tay phân biệt (`distinction_fingerprint`), cờ đánh giá độ phù hợp và rủi ro.
  - Bất biến:
    1. Từ 1 đến 3 video của cùng một tin trong cùng một lượt bắt buộc phải khai thác các góc kể khác nhau (`INV-013`, `FR-SCR-004`, `FR-VAR-003`).
    2. Tuyệt đối không dùng lại kịch bản gần nhất vừa làm của sự kiện đó (`FR-SCR-007`).
    3. Khi đã khai thác hết tập góc kể ban đầu, lần sản xuất sau có thể quay lại tin để sinh tập góc kể mới (`FR-SCR-006`).

### 3.5. Biên soạn kịch bản phân cảnh 61-70 giây (CT-AI-004)
- **`CT-AI-004` (`GenerateScript`):**
  - Điều kiện tiền đề (Precondition): Desktop production capability đang hoạt động; nếu chưa có, Orchestration (G) giữ job ở trạng thái `WAITING_CAPABILITY`, Module D không bắt đầu sinh kịch bản để tránh treo workflow giữa chừng.
  - Input: `angle_ref`; `snapshot_ref`; `analysis_revision`; thời lượng mục tiêu nghiêm ngặt **61–70 giây** (`target_duration`); chính sách ngôn ngữ (tiếng Anh); ứng viên voice/style/preset; danh sách loại trừ kịch bản gần đây; chính sách công bố suy luận (`inference_disclosure_policy`).
  - Output: `ScriptVersion` gồm:
    - Danh sách các phân đoạn lời thoại có thứ tự (`narration_segments`).
    - Ý đồ hook hình ảnh (`visual_hook_intent`) và điểm chuyển tiếp thumbnail (`thumbnail_transition`).
    - Phân cảnh hình ảnh (`scene_intents`).
    - Thời lượng ước tính (`estimated_timing`).
    - Chỉ dẫn phát âm cho các từ khó/tên riêng (`pronunciation_hints`).
    - Đánh dấu phân loại khẳng định (`claim_annotations`).
    - Công bố suy luận rõ ràng (`explicit_inference_disclosures`).
    - Tham chiếu nguồn theo từng đoạn (`source_refs`).
    - Dấu vân tay kịch bản (`script_fingerprint`).
    - Metadata mức độ sử dụng mô hình/prompt/provider (`usage_metadata`).
  - Bất biến phân loại khẳng định (`claim_mode`):
    - `source_backed`: Có bằng chứng trong snapshot -> bắt buộc giữ `source_refs`.
    - `inference`: Suy luận từ dữ liệu -> bắt buộc thể hiện rõ ngôn ngữ suy luận trong lời thoại.
    - `creative_hypothesis`: Chi tiết sáng tạo ngoài nguồn -> bắt buộc dùng ngôn ngữ giả định, cấm trình bày như sự thật (`FR-SCR-009`, `FR-SCR-010`).
    - `transition`: Câu nối dẫn dắt -> không yêu cầu source claim.
  - Ràng buộc thời lượng: Thời lượng ước tính phải nằm trong khoảng **61–70 giây**; vượt quá hoặc thấp hơn phải bị loại bỏ tự động ngay tại khâu biên soạn (`INV-014`).

### 3.6. Ủy quyền kể chuyện dòng thời gian (CT-AI-005)
- **`CT-AI-005` (`AuthorizeTimelineNarrative`):**
  - Chế độ dòng thời gian `from_then_to_now` chỉ hợp lệ khi snapshot chứa `EventUpdateAccepted` (từ `CT-STATE-004`) với tình tiết mới được xác nhận.
  - Nguồn tin mới, bài repost hoặc media mới đơn thuần không đủ điều kiện mở narrative này.
  - Nếu không thỏa mãn điều kiện, thao tác trả về mã lỗi `POLICY_VIOLATION`; Module D không tự ý đổi chế độ mà không có quyết định nghiệp vụ mới.

### 3.7. Chọn hook, media và âm thanh sáng tạo (CT-AI-006)
- **`CT-AI-006` (`SelectCreativeAssets`):**
  - Input: `script_ref`, `angle_ref`, `snapshot_ref`, danh mục ứng viên từ Phân hệ C (`CT-MED-005`, `CT-MED-006`), revision của sổ bộ 5 preset (`five-preset registry revision`), lịch sử sử dụng gần đây (`recent_usage`), ràng buộc kỹ thuật từ E và F, chính sách nhạc nền/SFX.
  - Output:
    - `visual_hook_ref`: Hook hình ảnh (3 giây đầu tiên).
    - `audio_hook_ref`: Hook âm thanh mở đầu.
    - `thumbnail_ref` và ý đồ chèn lớp phủ (`overlay_intent`): Biểu tượng, mũi tên, dấu hỏi, dấu chấm than.
    - Gán media cho từng phân cảnh có thứ tự (`scene_to_media_assignments`).
    - Ý đồ nhạc nền và hiệu ứng âm thanh (`music/SFX intents`).
    - Phương án tài nguyên dự phòng (`fallback_candidates`).
    - Cơ sở lý do chọn kèm điểm thành phần chi tiết (`selection_rationale`, `score_components`).
    - Dấu vân tay lựa chọn (`selection_fingerprint`).
  - Bất biến: Kế hoạch bắt buộc phải có visual hook, audio hook và thumbnail marker; vị trí thumbnail marker bắt buộc phải nằm trong phạm vi thời lượng của hook (0–3 giây đầu) (`INV-020`, `R08`).

### 3.8. Xây dựng kế hoạch dựng chi tiết (CT-AI-007)
- **`CT-AI-007` (`BuildProductionPlan`):**
  - Input & Context: Cùng session/capability context với job đang xử lý trên desktop.
  - Output: `ProductionPlan` gồm:
    - `script_version_id`: Phiên bản kịch bản chính xác.
    - `preset_id` & `preset_revision`: Thuộc đúng 1 trong 5 nhóm preset đã phê duyệt.
    - `timeline`: Danh sách phân cảnh, thời gian bắt đầu và kết thúc từng đoạn.
    - `asset_sequence`: Danh sách tài nguyên/rendition và khoảng thời gian xuất hiện.
    - `hook_placement`: Vị trí visual hook và audio hook.
    - `thumbnail_placement`: Vị trí trích xuất thumbnail JPEG (nằm trong 0–3s).
    - `visual_emphasis`: Ý đồ crop focus, overlay và chuyển cảnh.
    - `voice_direction`: Chỉ dẫn giọng đọc, nhịp điệu và cảm xúc cho Module E.
    - `music_direction` & `sound_cues`: Điểm chèn nhạc nền và hiệu ứng âm thanh.
    - `subtitle_style`: Ý đồ hiển thị phụ đề karaoke đổi màu cho Module F.
    - `fallback_rules`: Quy tắc thay thế tài nguyên cho phép khi render gặp lỗi.
    - `plan_fingerprint`: Dấu vân tay kế hoạch sản xuất.
  - Bất biến: Plan mô tả ý đồ sáng tạo (`creative intent`); Module E và F chuyển hóa thành thông số kỹ thuật. Module F tuyệt đối không tự ý thay đổi câu chuyện hoặc tài nguyên ngoài các fallback được plan cho phép.

### 3.9. Kiểm tra biến thể & Chống trùng lặp (CT-AI-008)
- **`CT-AI-008` (`ValidateVariant`):**
  - Input: Dấu vân tay của kịch bản và kế hoạch ứng viên (`candidate fingerprints`); lịch sử video hoàn thành của cùng bài viết/sự kiện; các video trong cùng lượt; chính sách biến thể (`variation_policy_revision`).
  - Output: Kết quả kiểm tra biến thể bất biến:
    - `valid`: `true` | `false`.
    - `same_run_angle_distinct`: Xác nhận khác góc kể trong cùng lượt.
    - `exact_duplicate`: Cảnh báo trùng lặp tuyệt đối.
    - `distinct_factors`: Danh sách các yếu tố thực tế khác biệt (giọng đọc, hook hình ảnh, hook âm thanh, nhạc nền, thứ tự/lựa chọn media, hiệu ứng, nội dung kịch bản, cách dẫn dắt, góc tiếp cận).
    - `reason_codes`: Mã lý do chấp nhận hoặc từ chối.
  - Bất biến quy tắc biến thể (`INV-004`, `INV-013`, `INV-014`):
    1. Trong cùng một lượt: Bắt buộc khác góc kể (`StoryAngle`), không chấp nhận việc chỉ đổi hiệu ứng đồ họa (`FR-VAR-003`).
    2. Giữa các lượt khai thác: Video mới không được hoàn toàn giống video cũ (`FR-VAR-005`), và bắt buộc phải khác biệt ít nhất một yếu tố thực tế được theo dõi (`FR-VAR-004`).
    3. Chỉ công nhận sự khác biệt từ nội dung kịch bản, tài nguyên hoặc kế hoạch dựng thực tế; không công nhận khác biệt chỉ đến từ seed ngẫu nhiên hoặc UUID định danh.
    4. Tương tác với Orchestration (G): `valid=true` không tự cấp quyền hoàn tất (`completion`); Orchestration kiểm tra compare-and-swap với `VariantReservation` theo `CT-ORC-012` và `CT-STATE-007`.

### 3.10. Metadata xuất bản đầu ra (CT-AI-009)
- **`CT-AI-009` (`GenerateOutputMetadata`):**
  - Output: Tiêu đề và chú thích chuẩn SEO (`title`, `caption`); 3 đến 4 thẻ hashtag liên quan (`hashtags`); biểu diễn an toàn cho hệ thống tệp tin (`filename_safe representation`); biểu diễn hiển thị nguyên bản (`display representation`); ngôn ngữ (`language`: tiếng Anh); tham chiếu job/output nguồn; metadata revision.
  - Bất biến: Tên tệp tin sử dụng tiêu đề/caption và hashtag theo quyết định người dùng, nhưng bắt buộc phải qua hàm lọc sanitize của hợp đồng lưu trữ (`CONTRACT-STORAGE`) để hợp lệ trên hệ điều hành Windows mà không làm mất bản hiển thị gốc.

### 3.11. Quản trị lời gọi AI & Bảo mật Secret (CT-AI-010)
- **`CT-AI-010` (`AIInvocationRecord`):**
  - Module D tuyệt đối không nhận, không lưu trữ và không xử lý API key hoặc token bí mật.
  - Mọi yêu cầu gọi mô hình AI phải thông qua AI Adapter của Module J (`CT-AI-ROUTE-001`). Module D chỉ nhận provider handle ngắn hạn hoặc context gắn với worker.
  - Mỗi lần gọi mô hình AI đều được ghi nhận vào nhật ký bất biến: role/capability; model/provider/account/project refs; prompt/config revision; input/output fingerprint; token/usage/cost; latency, attempt và fallback path; validation result; lỗi đã được ẩn thông tin nhạy cảm (`redacted error`).
  - Bất biến: Mô hình AI không được là bên duy nhất xác nhận tính hợp lệ của source ref, disclosure, hoặc policy compliance của chính nội dung do nó tạo ra.

---

## 4. Ranh Giới Giao Tiếp Then Chốt (Key Interface Boundaries)

### 4.1. Ranh giới Tiếp nhận Nội dung: `interface_b_d`
- Hợp đồng: `CONTRACT-SOURCE-CONTENT` (`CT-CNT-002`) và `CONTRACT-CREATIVE-AI` (`CT-AI-001`).
- Phân định: Module B cung cấp `ArticleSnapshot` sạch, đã chuẩn hóa, bóc tách cấu trúc và có fingerprint; Module D tiếp nhận và đóng băng vào `ProductionSnapshot`.
- Bất biến: Module D không trực tiếp crawl hay trích xuất HTML thô từ web.

### 4.2. Ranh giới Định tuyến AI & Secret: `interface_d_j`
- Hợp đồng: `CONTRACT-CONFIG-SECURITY` (`CT-AI-ROUTE-001`, `CT-CFG-001`) và `CONTRACT-CREATIVE-AI` (`CT-AI-010`).
- Phân định: Module J quản lý Windows DPAPI Secret Broker, định tuyến đa tài khoản/nhà cung cấp và quota; Module D gửi yêu cầu sinh nội dung qua secret handle trừu tượng.
- Bất biến: Tuyệt đối không để lọt API key dạng plain-text vào prompt, log hoặc dữ liệu của Module D.

### 4.3. Ranh giới Khai thác Media & Hook: `interface_c_d`
- Hợp đồng: `CONTRACT-CONTENT-MEDIA` (`CT-MED-004`, `CT-MED-005`, `CT-HOOK-001`) và `CONTRACT-CREATIVE-AI` (`CT-AI-006`).
- Phân định: Module C cung cấp metadata, danh mục hook và danh sách ứng viên media kèm điểm thành phần; Module D thực hiện lựa chọn sáng tạo, ghép nối vào phân cảnh và ghi nhận lý do chọn (`selection_rationale`).

### 4.4. Ranh giới Chuyển giao Sản xuất: `interface_d_e_f`
- Hợp đồng: `CONTRACT-MEDIA-PROCESSING` (`CT-TTS-001`), `CONTRACT-RENDER-QUALITY` (`CT-RND-001`) và `CONTRACT-CREATIVE-AI` (`CT-AI-007`).
- Phân định: Module D chuyển giao kịch bản hoàn chỉnh kèm chỉ dẫn phát âm cho Module E (Voice TTS), và chuyển giao `ProductionPlan` chi tiết cho Module F (Render Video).
- Bất biến: E và F chỉ thi hành theo kế hoạch của D; F không tự ý thay đổi cốt truyện hay hoán đổi tài nguyên ngoài danh mục fallback cho phép.

### 4.5. Ranh giới Điều phối & Đặt trước Biến thể: `interface_g_d`
- Hợp đồng: `CONTRACT-WORKFLOW-EXECUTION` (`CT-WF-001`), `CONTRACT-ORCHESTRATION` (`CT-ORC-012`) và `CONTRACT-STATE-MACHINES` (`CT-STATE-007`).
- Phân định: Orchestration (Module G) điều phối tiến trình sinh kịch bản, quản lý vòng đời `VariantReservation` nguyên tử trong PostgreSQL; Module D thực hiện tính toán và kiểm tra tính hợp lệ của biến thể.

---

## 5. Máy Trạng Thái Cốt Lõi (Bound State Machines - CONTRACT-STATE-MACHINES)

### 5.1. Vòng đời Snapshot & Creative Outputs: `CT-STATE-007`
- **ProductionSnapshot:** `BUILDING` -> `COMMITTED` | `REJECTED`.
- **Script/Plan Revision:** `GENERATING` -> `VALIDATING` -> `READY` | `REJECTED` | `FAILED`.
  - Trạng thái `READY` là bất biến. Mọi nhu cầu chỉnh sửa hoặc tạo lại kịch bản đều sinh revision mới độc lập; không có trạng thái phê duyệt trung gian (`user-approved`) trong phiên bản v1.
- **VariantReservation (Module G, CT-ORC-012):**
  - Tạo reservation ở trạng thái `ACTIVE` nguyên tử sau khi `ValidateVariant` hợp lệ.
  - Chuyển `ACTIVE` -> `CONVERTED` khi video hoàn tất (`VideoJobCompleted`).
  - Chuyển `ACTIVE` -> `RELEASED` khi job gặp lỗi terminal hoặc bị hủy bỏ.
  - Bất biến: Trạng thái chờ, retry hoặc hết hạn lease không làm release reservation. Xung đột biến thể thực sự kết thúc job ở `FAILED_FINAL`.

### 5.2. Vòng đời Liên kết & Cập nhật Sự kiện: `CT-STATE-004`
- **Event update candidate:** `PROPOSED` -> `ACCEPTED_NEW_DEVELOPMENT` | `REJECTED_REPOST` | `REJECTED_NO_NEW_FACT` | `UNCERTAIN`.
- Bất biến: Chỉ có trạng thái `ACCEPTED_NEW_DEVELOPMENT` mới cấp điều kiện ủy quyền cho narrative dòng thời gian `from_then_to_now` (`CT-AI-005`).

---

## 6. Kết Luận Khóa Bất Biến

Toàn bộ 10 hợp đồng giao tiếp nền tảng, 11 điều khoản giao diện của `CONTRACT-CREATIVE-AI` (`CT-AI-000` đến `CT-AI-010`), các ranh giới liên phân hệ B-D, D-J, C-D, D-E-F, G-D và các máy trạng thái cốt lõi đã được đóng băng cố định với đầy đủ mã băm SHA-256 xác thực. Nghiêm cấm mọi hành vi tự ý sửa đổi làm sai lệch baseline đã được phê duyệt.

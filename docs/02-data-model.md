# AI Auto Video Creator - Bản đồ dữ liệu

**Cập nhật kiến trúc sau audit:** quyết định nơi lưu/Sheets/search/workspace hiện hành nằm tại [08-architecture.md](./08-architecture.md) và [ADR index](./adr/README.md). Các câu mô tả “để bước kiến trúc quyết định” phía dưới giữ bối cảnh bước 05; không phủ định baseline mới. Không thay ngưỡng hoặc quy tắc DR đã duyệt.

**Giai đoạn:** 05 - Xác định dữ liệu và đối tượng  
**Ngày lập:** 12-09-2026  
**Trạng thái:** Nền tảng đã được phê duyệt; cập nhật nghiệp vụ R01-R25 và bổ sung mô tả logic để duyệt cùng bước 09  
**Tài liệu nguồn:** [00-project-charter.md](./00-project-charter.md), [01-product-spec.md](./01-product-spec.md)

## 1. Mục đích

Tài liệu này xác định những đối tượng dữ liệu sản phẩm cần quản lý, ý nghĩa của chúng, quan hệ giữa chúng, vòng đời và các quy tắc toàn vẹn cần bảo vệ.

Đây là mô hình dữ liệu khái niệm và logic. Tài liệu chưa chọn cơ sở dữ liệu, định dạng tệp, dịch vụ lưu trữ, schema vật lý, kiểu dữ liệu, API hoặc công nghệ đồng bộ.

Quyết định R01-R25 được tổng hợp tại [07-data-flow.md](./07-data-flow.md), mục 2. Các quan hệ bổ sung ở mục 16 là **ĐỀ XUẤT THIẾT KẾ LOGIC**, không phải schema đã triển khai hoặc giả định về công nghệ.

## 2. Nguyên tắc về Google Sheets

- Sản phẩm phải cho người dùng trải nghiệm quan sát và thao tác dữ liệu theo dạng bảng gần với Google Sheets.
- Các nhóm dữ liệu chính phải có thể được trình bày thành hàng và cột, hỗ trợ quan sát số lượng lớn bản ghi.
- Tại bước 05, vai trò Google Sheets chưa quyết định. Sau audit kiến trúc: PostgreSQL là lõi, UI bảng thực hiện trải nghiệm tương tự; Google Sheets không nằm trong đường chạy v1 theo ADR-0002/0007.
- Bản đồ dữ liệu không phụ thuộc vào số hàng, số cột hoặc định danh nội bộ của Google Sheets.
- Quyết định vai trò của Google Sheets phải được đánh giá trong giai đoạn kiến trúc.
- R14 cho sửa metadata quản trị như Tier, chủ đề/tag, ghi chú, bật/tắt nguồn hoặc hook. Không sửa bài gốc, quan hệ sự kiện hoặc script trực tiếp; danh sách cột và thao tác chi tiết còn chờ thiết kế UI.

## 3. Miền dữ liệu

Dữ liệu được chia theo ý nghĩa sản phẩm, chưa phải theo dịch vụ hoặc dự án con:

1. **Nguồn và thu thập:** nguồn tin, lượt quét, bài viết và phiên bản bài viết.
2. **Phân loại và tri thức sự kiện:** chủ đề, nhân vật/đối tượng, sự kiện và diễn biến mới.
3. **Tài nguyên truyền thông:** ảnh, clip, audio, chỉ mục, liên kết và kết quả kiểm tra ảnh nhạy cảm.
4. **Hook:** video hook, âm thanh hook và lần lựa chọn hook cho video.
5. **Nội dung sáng tạo:** góc kể, kịch bản, đoạn kịch bản, preset, kế hoạch trình bày và dấu hiệu biến thể.
6. **Sản xuất:** lô, công việc video, lần chạy công đoạn, đầu ra render và đồng bộ.
7. **Vận hành:** phiên ứng dụng, nhật ký, cấu hình và tham chiếu tài khoản/dung lượng bên ngoài.

## 4. Bản đồ quan hệ tổng thể

```text
SourceCandidate -> Source -> CollectionRun -> CollectionAttempt
                            |
                            +-----> Article -> ArticleRevision
                         Article <-> Event -> EventUpdate
                            |          |
                            +-----> Topic
                            +-----> Subject
                            +-----> MediaAsset <-> AssetAssociation

Event/Article -> StoryAngle -> ScriptVersion -> ScriptSegment
                         |             |
                         +-------> VariantSignature

HookVisual ----+
HookAudio ------+--> VideoJob <-- ScriptVersion
Preset --------+        |
MediaAsset -----+        +--> StageRun -> LogEntry
                        |
Batch -----------> VideoJob -> RenderOutput -> SyncRecord

AppSession -> Batch / StageRun / LogEntry
ConfigurationProfile -> CollectionRun / Batch / VideoJob
ExternalAccountRef -> StorageArea / AI role assignment
```

Sơ đồ chỉ biểu diễn ý nghĩa quan hệ, không quy định cách lưu hoặc giao tiếp giữa các thành phần.

## 5. Từ điển đối tượng dữ liệu

### 5.1. Nguồn và thu thập

#### Source

Đại diện cho một nơi cung cấp tin hoặc tài nguyên có thể được quét.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `source_id` | Định danh ổn định của nguồn |
| `name` | Tên hiển thị |
| `root_location` | Địa chỉ gốc của nguồn |
| `source_kind` | Loại nguồn, chưa chốt danh sách giá trị |
| `tier` | Mức ưu tiên `Tier 1/2/3` |
| `language` | Ngôn ngữ chủ yếu của nguồn |
| `topic_scope` | Các nhóm chủ đề nguồn thường cung cấp |
| `market_relevance` | Mức liên quan đến khán giả Mỹ |
| `discovery_method` | Hệ thống tự tìm hoặc người dùng thêm |
| `usage_status` | Trạng thái nguồn trong quá trình vận hành |
| `rediscovery_blocked` | Nguồn đã bị người dùng loại bỏ không được tự thêm lại cho tới khi khôi phục (R24) |
| `last_collection_at` | Lần quét gần nhất |
| `rights_status` | Trạng thái hiểu biết hiện tại về quyền sử dụng |
| `notes` | Ghi chú phục vụ người dùng và debug |

#### SourceCandidate

Đại diện cho một locator do hệ thống phát hiện trước khi trở thành `Source`. A sở hữu candidate và giữ discovery evidence, canonical candidate, source-kind/topic candidates, matched source/tombstone, validation, proposed Tier/policy revision, disposition, reason và audit time. Candidate trùng hoặc tombstone không tạo Source mới; candidate thiếu policy bắt buộc không tự thành source active.

#### CollectionRun

Đại diện cho một lượt quét đúng một nguồn theo một purpose.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `collection_run_id` | Định danh lượt quét |
| `source_id`, `source_revision` | Nguồn duy nhất thuộc lượt quét |
| `purpose` | `periodic`, `supplemental` hoặc `source-test`; retry không phải purpose |
| `business_date` | Ngày nghiệp vụ đã khóa theo timezone revision với periodic run |
| `scheduled_for` | Thời điểm dự kiến |
| `started_at`, `finished_at` | Thời gian thực tế |
| `status` | Trạng thái lượt quét |
| `items_found` | Số mục phát hiện |
| `items_added` | Số tin mới được ghi nhận |
| `items_updated` | Số tin có thay đổi |
| `error_summary` | Tóm tắt lỗi không làm lộ bí mật |
| `configuration_ref` | Cấu hình được dùng cho lượt quét |

#### CollectionAttempt

Một lần thử kỹ thuật append-only của `CollectionRun`. Attempt ghi số thứ tự, grant/generation/recovery epoch, thời điểm, checkpoint đầu-cuối và kết quả `SUCCEEDED`, `FAILED_RETRYABLE`, `FAILED_FINAL` hoặc `OUTCOME_UNKNOWN`. Unknown được bổ sung reconciliation evidence/result, không ghi đè observation gốc. Lỗi retryable chỉ đưa run sang WAITING_RETRY khi nguồn/budget còn cho phép; nếu không thì COMPLETED_PARTIAL khi đã commit package hợp lệ, ngược lại FAILED_FINAL. CT-STATE-002 là bảng chuyển trạng thái có thẩm quyền; run terminal không mở lại.

#### Article

Đại diện cho một bài viết hoặc một mục tin độc lập từ nguồn.

Theo R07/R22, bài trùng bị loại khỏi tập tin độc lập được khai thác; dùng một tin đại diện. Dấu vết URL/nguồn trùng và media mới vẫn được giữ khi cần truy vết, không tạo thêm Article có thể khai thác chỉ để chứa dấu vết đó. Quy tắc bảo toàn bài độc lập áp dụng cho bài được chấp nhận vào kho và việc liên kết sự kiện, không yêu cầu nhập mọi bản đăng lại.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `article_id` | Định danh nội bộ ổn định |
| `source_id` | Nguồn cung cấp bài |
| `source_location` | Địa chỉ bài gốc |
| `canonical_location` | Địa chỉ chuẩn nếu xác định được |
| `headline` | Tiêu đề hiện tại |
| `published_at` | Thời điểm nguồn công bố |
| `collected_at` | Thời điểm hệ thống ghi nhận |
| `language` | Ngôn ngữ nguồn |
| `current_revision_id` | Phiên bản hiện hành |
| `topic_ids` | Các nhóm chủ đề đã phân loại |
| `subject_ids` | Nhân vật hoặc đối tượng liên quan |
| `event_ids` | Sự kiện có liên quan |
| `content_status` | Trạng thái trong vòng đời xử lý |
| `rights_status` | Trạng thái quyền sử dụng đã biết |

#### ArticleRevision

Giữ nội dung của một bài tại một thời điểm để nhận biết nguồn đã sửa.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `article_revision_id` | Định danh phiên bản |
| `article_id` | Bài gốc |
| `observed_at` | Thời điểm ghi nhận phiên bản |
| `headline_snapshot` | Tiêu đề tại thời điểm đó |
| `body_snapshot_ref` | Tham chiếu nội dung bài |
| `media_snapshot_refs` | Các tài nguyên xuất hiện trong phiên bản |
| `change_summary` | Phần thay đổi so với phiên bản trước |
| `is_current` | Có phải phiên bản hiện hành hay không |

### 5.2. Phân loại và tri thức sự kiện

#### Topic

Đại diện cho nhóm chủ đề dùng để phân loại và chọn nội dung.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `topic_id` | Định danh chủ đề |
| `name` | Tên hiển thị |
| `description` | Ranh giới nội dung của chủ đề |
| `status` | Đề xuất, đã duyệt hoặc không sử dụng |
| `trend_mode` | Thiên về trending, lâu dài hoặc cả hai |
| `parent_topic_id` | Chủ đề cha nếu có |

#### Subject

Đại diện cho người, tổ chức, địa điểm hoặc đối tượng nổi bật trong câu chuyện.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `subject_id` | Định danh nội bộ |
| `subject_kind` | Người, tổ chức, địa điểm hoặc loại khác |
| `display_name` | Tên dùng để hiển thị |
| `aliases` | Các tên gọi khác |
| `official_locations` | Trang hoặc nguồn chính thức đã biết |
| `thumbnail_asset_ids` | Các ảnh nhận diện ứng viên |
| `topic_ids` | Chủ đề thường liên quan |

#### Event

Đại diện cho một sự kiện có thể liên kết nhiều bài và được khai thác nhiều lần.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `event_id` | Định danh ổn định của sự kiện |
| `working_title` | Tên dùng trong hệ thống |
| `summary` | Tóm tắt hiện hành |
| `topic_ids` | Các chủ đề liên quan |
| `subject_ids` | Nhân vật/đối tượng liên quan |
| `article_ids` | Các bài đã liên kết |
| `first_known_at` | Thời điểm sớm nhất đã biết |
| `latest_update_at` | Thời điểm có diễn biến mới gần nhất |
| `event_status` | Trạng thái khai thác |
| `last_exploited_at` | Lần gần nhất dùng để tạo video |
| `exploitation_round` | Số vòng khai thác đã thực hiện |

#### ArticleEventLink

Biểu diễn quan hệ nhiều-nhiều giữa bài viết và sự kiện.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `article_event_link_id` | Định danh liên kết |
| `article_id` | Bài liên quan |
| `event_id` | Sự kiện liên quan |
| `relation_kind` | Bài gốc, diễn biến mới, bối cảnh hoặc loại khác |
| `association_confidence` | Mức tin cậy của việc liên kết |
| `association_origin` | Hệ thống đề xuất hoặc người dùng xác nhận |

#### EventUpdate

Đại diện cho diễn biến mới có tình tiết mới làm sự kiện cũ đủ điều kiện tạo nội dung “từ lúc đó đến bây giờ” (R07). Bài đăng lại, URL mới hoặc media mới không tự tạo EventUpdate.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `event_update_id` | Định danh diễn biến |
| `event_id` | Sự kiện được cập nhật |
| `article_revision_ids` | Nguồn dữ liệu tạo ra cập nhật |
| `observed_at` | Thời điểm ghi nhận |
| `summary` | Nội dung mới |
| `is_material_update` | Có đủ điều kiện kích hoạt khai thác lại hay không |

### 5.3. Tài nguyên truyền thông

#### MediaAsset

Đại diện chung cho ảnh, clip hoặc audio lấy từ nguồn hoặc được người dùng bổ sung.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `asset_id` | Định danh tài nguyên |
| `asset_kind` | Ảnh, clip hoặc audio |
| `origin_kind` | Bài viết, trang chính thức, người dùng hoặc nguồn khác |
| `origin_location` | Vị trí xuất xứ |
| `source_id` | Nguồn liên quan nếu có |
| `remote_location` | Vị trí lưu dài hạn |
| `local_staging_location` | Vị trí tạm trên máy render nếu đã tải |
| `availability_status` | Có sẵn từ xa, đang tải, sẵn sàng cục bộ hoặc lỗi |
| `rights_status` | Trạng thái quyền sử dụng đã biết |
| `description` | Mô tả nội dung |
| `index_terms` | Từ khóa và dấu hiệu để AI lựa chọn |
| `subject_ids` | Nhân vật/đối tượng xuất hiện |
| `technical_metadata` | Thông tin kỹ thuật cần cho việc sử dụng, chưa định nghĩa chi tiết |

#### AssetAssociation

Cho phép một tài nguyên được dùng lại cho nhiều bài, sự kiện hoặc đối tượng mà không nhân bản bản ghi logic.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `asset_association_id` | Định danh liên kết |
| `asset_id` | Tài nguyên |
| `article_id`, `event_id`, `subject_id` | Đối tượng được liên kết khi phù hợp |
| `relation_kind` | Thumbnail, minh họa, bằng chứng, bối cảnh hoặc vai trò khác |
| `relevance` | Mức phù hợp với đối tượng liên kết |

#### ImageSafetyAssessment

Chỉ áp dụng cho ảnh; không áp dụng cho clip theo quyết định đã xác nhận.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `assessment_id` | Định danh lần đánh giá |
| `asset_id` | Ảnh được đánh giá |
| `contains_child_face` | Có khuôn mặt trẻ em hay không |
| `contains_blood` | Có yếu tố máu me hay không |
| `contains_weapon` | Có vũ khí hay không |
| `required_actions` | Che mặt, làm mờ, đổi màu hoặc hành động đã yêu cầu |
| `assessment_status` | Chờ, hoàn thành hoặc lỗi |
| `processed_asset_id` | Ảnh sau xử lý nếu có |

R12/R25 yêu cầu phân biệt kết luận nhận diện chưa chắc, lỗi kiểm tra và lỗi xử lý. Ảnh nguyên gốc còn đọc được vẫn được phép dùng ở cả ba trường hợp nhưng trạng thái lỗi/chưa chắc được giữ nguyên. Cần mô tả riêng kết luận nhận diện, kết quả biến đổi và lý do cho phép sử dụng; quyền sử dụng không đồng nghĩa xử lý thành công. Các nhãn trên là mô tả logic, không gộp mọi trường hợp vào một giá trị “an toàn”.

### 5.4. Kho hook

#### HookVisual

Đại diện cho video hook do người dùng thêm và đã làm mờ sẵn.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `hook_visual_id` | Định danh video hook |
| `display_name` | Tên hiển thị |
| `asset_id` | Tài nguyên video tương ứng |
| `blur_confirmed` | Xác nhận người dùng đã xử lý làm mờ |
| `themes` | Chủ đề phù hợp |
| `emotions` | Cảm xúc phù hợp |
| `intensity` | Cường độ thể hiện |
| `index_terms` | Dấu hiệu để AI lựa chọn |
| `usage_status` | Có thể dùng hay không |
| `usage_count` | Số lần đã được chọn |

#### HookAudio

Đại diện cho âm thanh hook được quản lý độc lập với video hook.

Người dùng cung cấp audio hook (R11); nhạc nền và SFX do hệ thống tự tìm/thu thập được quản lý trong MediaAsset, không tự nhập vào kho audio hook.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `hook_audio_id` | Định danh âm thanh hook |
| `display_name` | Tên hiển thị |
| `asset_id` | Tài nguyên audio tương ứng |
| `themes` | Chủ đề phù hợp |
| `emotions` | Cảm xúc phù hợp |
| `intensity` | Cường độ thể hiện |
| `index_terms` | Dấu hiệu để AI lựa chọn |
| `usage_status` | Có thể dùng hay không |
| `usage_count` | Số lần đã được chọn |

#### HookSelection

Ghi lại tổ hợp hook được chọn cho một video để phục vụ tái tạo và chống lặp.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `hook_selection_id` | Định danh lần chọn |
| `video_job_id` | Công việc video sử dụng hook |
| `hook_visual_id` | Video hook đã chọn |
| `hook_audio_id` | Âm thanh hook đã chọn |
| `thumbnail_asset_id` | Thumbnail của câu chuyện |
| `selection_reason` | Lý do phù hợp ở mức người dùng có thể hiểu |

### 5.5. Nội dung sáng tạo

#### StoryAngle

Đại diện cho một góc kể cụ thể của bài hoặc sự kiện.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `story_angle_id` | Định danh góc kể |
| `article_ids`, `event_id` | Dữ liệu nguồn của góc kể |
| `angle_name` | Tên ngắn của góc kể |
| `focus_subject_ids` | Nhân vật/đối tượng trọng tâm |
| `angle_summary` | Phạm vi và trọng tâm nội dung |
| `exploitation_round` | Vòng khai thác tạo ra góc kể |
| `created_at` | Thời điểm tạo |

#### ScriptVersion

Đại diện cho một phiên bản kịch bản tiếng Anh dùng cho một video.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `script_version_id` | Định danh phiên bản |
| `story_angle_id` | Góc kể tương ứng |
| `language` | Ngôn ngữ đầu ra, hiện là tiếng Anh |
| `style` | Phong cách kể được chọn |
| `full_text` | Nội dung kịch bản |
| `target_duration` | Thời lượng video mục tiêu 61-70 giây |
| `generation_round` | Lượt khai thác |
| `created_at` | Thời điểm tạo |
| `status` | Trạng thái sử dụng của kịch bản |
| `previous_script_id` | Kịch bản trước dùng để kiểm tra lặp nếu có |

#### ScriptSegment

Chia kịch bản thành các đoạn có nguồn gốc nội dung rõ ràng.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `script_segment_id` | Định danh đoạn |
| `script_version_id` | Kịch bản chứa đoạn |
| `sequence` | Thứ tự xuất hiện |
| `text` | Nội dung đoạn |
| `content_origin` | Thông tin từ nguồn hoặc suy luận/sáng tạo |
| `source_revision_ids` | Các nguồn hỗ trợ nếu là thông tin từ nguồn |
| `inference_marker` | Cách thể hiện rõ đây là suy luận nếu áp dụng |

#### Preset

Đại diện cho một trong đúng năm nhóm preset đã được phê duyệt.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `preset_id` | Định danh preset |
| `name` | Tên hiển thị |
| `description` | Phong cách và trường hợp phù hợp |
| `version` | Phiên bản preset |
| `status` | Đang sử dụng hoặc ngừng sử dụng |
| `selection_tags` | Dấu hiệu hỗ trợ AI chọn preset |

#### ProductionPlan

Mô tả sản phẩm dự kiến của một video trước khi render, không quy định cách render.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `production_plan_id` | Định danh kế hoạch nội dung |
| `script_version_id` | Kịch bản được dùng |
| `preset_id` | Preset được chọn |
| `asset_sequence` | Tài nguyên và thứ tự xuất hiện |
| `hook_selection_id` | Tổ hợp hook |
| `voice_direction` | Chỉ dẫn giọng đọc |
| `music_direction` | Chỉ dẫn nhạc nền |
| `sound_cues` | Các điểm chèn hiệu ứng âm thanh |
| `visual_emphasis` | Thumbnail, biểu tượng và điểm nhấn hình ảnh |
| `expected_duration` | Thời lượng dự kiến |

#### VariantSignature

Ghi lại những yếu tố đã dùng để so sánh các lần khai thác.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `variant_signature_id` | Định danh dấu hiệu biến thể |
| `video_job_id` | Video được mô tả |
| `story_angle_id` | Góc kể |
| `script_version_id` | Kịch bản |
| `voice_identity` | Giọng đọc đã dùng |
| `hook_visual_id`, `hook_audio_id` | Hook đã dùng |
| `music_identity` | Nhạc nền đã dùng |
| `asset_order` | Tập và thứ tự tài nguyên |
| `preset_id` | Preset |
| `effect_set` | Các điểm nhấn và hiệu ứng |

### 5.6. Sản xuất video

#### Batch

Đại diện cho một lô do người dùng khởi chạy.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `batch_id` | Định danh lô |
| `app_session_id` | Phiên ứng dụng tạo lô |
| `configuration_ref` | Cấu hình chung tại lúc bắt đầu |
| `started_at`, `finished_at` | Thời gian lô |
| `status` | Trạng thái lô |
| `planned_job_count` | Số video dự kiến nếu xác định được |
| `target_completed_count` | Số video hoàn thành người dùng yêu cầu; không đếm lần thử hoặc output chưa sync (R10) |
| `completed_job_count` | Số video hoàn thành |
| `failed_job_count` | Số video lỗi |

#### VideoJob

Đại diện cho toàn bộ công việc tạo một video.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `video_job_id` | Định danh công việc |
| `batch_id` | Lô chứa công việc nếu có |
| `article_ids`, `event_id` | Tin hoặc sự kiện nguồn |
| `story_angle_id` | Góc kể |
| `script_version_id` | Kịch bản |
| `production_plan_id` | Kế hoạch trình bày |
| `mode` | Chạy thủ công hoặc tự động |
| `status` | Trạng thái công việc |
| `queue_position` | Vị trí quan sát được trong hàng chờ |
| `attempt_count` | Số lần đã thử |
| `created_at`, `completed_at` | Thời gian vòng đời |

#### StageRun

Đại diện cho một lần chạy của một công đoạn để hỗ trợ debug và chạy lại riêng lẻ.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `stage_run_id` | Định danh lần chạy |
| `video_job_id` | Công việc video liên quan nếu có; không bắt buộc cho thu thập/làm giàu nền |
| `work_context_ref` | Ngữ cảnh công việc nền, lượt thu thập hoặc xử lý tài nguyên khi chưa có video |
| `stage_name` | Tên công đoạn sản phẩm |
| `mode` | Thủ công hoặc tự động |
| `attempt_number` | Số lần thử của công đoạn |
| `input_refs` | Các đầu vào đã sử dụng |
| `output_refs` | Các kết quả tạo ra |
| `status` | Trạng thái công đoạn |
| `started_at`, `finished_at` | Thời gian chạy |
| `error_ref` | Nhật ký lỗi nếu có |

#### RenderOutput

Đại diện cho tệp video được tạo ra từ một lần render.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `render_output_id` | Định danh đầu ra |
| `video_job_id` | Công việc tạo video |
| `local_location` | Vị trí tạm trên máy render |
| `duration` | Thời lượng thực tế |
| `playback_status` | Kết quả kiểm tra khả năng phát |
| `hook_complete` | Có đủ video hook, audio hook và thumbnail |
| `filename` | Tên tệp đã tạo |
| `rendered_at` | Thời điểm hoàn thành render |
| `completion_status` | Kết quả kiểm tra đầu ra render, không phải hoàn thành toàn VideoJob; tên chính thức chờ hợp đồng dữ liệu |

#### SyncRecord

Ghi nhận quá trình chuyển video hoặc tài nguyên tới nơi lưu dài hạn.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `sync_record_id` | Định danh lần đồng bộ |
| `object_kind`, `object_id` | Đối tượng được đồng bộ |
| `storage_area_id` | Khu vực lưu trữ đích |
| `remote_location` | Vị trí sau đồng bộ |
| `status` | Chờ, đang đồng bộ, hoàn thành hoặc lỗi |
| `started_at`, `confirmed_at` | Thời gian thực hiện và xác nhận |
| `error_ref` | Lỗi nếu có |
| `local_cleanup_status` | Trạng thái xóa bản cục bộ sau đồng bộ |

### 5.7. Vận hành

#### AppSession

Đại diện cho một phiên mở ứng dụng trên máy desktop.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `app_session_id` | Định danh phiên |
| `started_at`, `ended_at` | Thời gian phiên |
| `output_folder_name` | Tên `YY-MM-DD` và hậu tố nếu có |
| `completed_video_count` | Số video hoàn thành trong phiên |
| `status` | Trạng thái kết thúc phiên |

#### LogEntry

Đại diện cho một sự kiện vận hành, cảnh báo hoặc lỗi.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `log_entry_id` | Định danh nhật ký |
| `app_session_id` | Phiên ứng dụng liên quan nếu có |
| `related_kind`, `related_id` | Nguồn, lượt quét, lô, video hoặc công đoạn liên quan |
| `occurred_at` | Thời điểm xảy ra |
| `severity` | Thông tin, cảnh báo hoặc lỗi |
| `summary` | Nội dung ngắn hiển thị trên bảng |
| `detail` | Nội dung chi tiết hiện khi rê chuột |
| `is_retryable` | Có thể thử lại hay không |
| `secret_redacted` | Xác nhận dữ liệu bí mật đã được loại bỏ |

#### ConfigurationProfile

Lưu tập lựa chọn vận hành để lần chạy có thể giữ nguyên ngữ cảnh cấu hình.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `configuration_profile_id` | Định danh cấu hình |
| `name` | Tên hiển thị |
| `scope` | Toàn hệ thống, thu thập, lô hoặc công đoạn |
| `settings` | Các lựa chọn sản phẩm, chưa quy định định dạng vật lý |
| `created_at`, `updated_at` | Thời gian thay đổi |
| `status` | Đang dùng hoặc lưu trữ |

#### ExternalAccountRef

Chỉ lưu thông tin quản lý và tham chiếu bí mật; không lưu khóa bí mật trực tiếp trong dữ liệu quan sát được.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `external_account_ref_id` | Định danh tham chiếu tài khoản |
| `provider_name` | Tên dịch vụ do người dùng cung cấp |
| `account_label` | Nhãn phân biệt tài khoản |
| `allowed_roles` | Vai trò được phép đảm nhiệm |
| `availability_status` | Trạng thái sẵn sàng |
| `quota_observation` | Thông tin hạn mức quan sát được nếu có |
| `secret_reference` | Tham chiếu đến thông tin bí mật bên ngoài giao diện |

#### StorageArea

Đại diện logic cho một khu vực lưu dữ liệu dài hạn theo loại.

| Thuộc tính logic | Ý nghĩa |
|---|---|
| `storage_area_id` | Định danh khu vực |
| `external_account_ref_id` | Tài khoản sở hữu khu vực |
| `data_category` | Loại dữ liệu được phân bổ |
| `display_name` | Tên hiển thị |
| `remote_root` | Vị trí gốc |
| `availability_status` | Trạng thái truy cập |
| `capacity_observation` | Dung lượng quan sát được nếu có |

## 6. Quan hệ và số lượng logic

- Một `Source` có nhiều `CollectionRun` và nhiều `Article`.
- Một `SourceCandidate` có thể tạo tối đa một `Source`; candidate trùng/tombstone/rejected không tạo Source.
- Một `CollectionRun` thuộc đúng một `Source` và có nhiều `CollectionAttempt` append-only.
- Một `Article` có một hoặc nhiều `ArticleRevision`.
- Một `Article` có thể không thuộc sự kiện nào hoặc thuộc một hay nhiều `Event`.
- Một `Event` có thể liên kết nhiều `Article`, `Subject`, `Topic` và `EventUpdate`.
- Một `MediaAsset` có thể liên kết với nhiều bài, sự kiện hoặc đối tượng qua `AssetAssociation`.
- Một ảnh có thể có nhiều lần đánh giá/xử lý, nhưng chỉ một kết quả hiện hành được dùng cho một công việc.
- Một `Event` hoặc `Article` có thể tạo nhiều `StoryAngle`.
- Một `StoryAngle` có thể tạo nhiều `ScriptVersion` qua các vòng khai thác.
- Một `ScriptVersion` gồm nhiều `ScriptSegment` theo thứ tự.
- Một `Batch` có nhiều `VideoJob`; một `VideoJob` có thể tồn tại ngoài lô khi chạy thủ công.
- Một `VideoJob` dùng một kịch bản, một preset, một video hook, một audio hook và một thumbnail hook.
- Một `VideoJob` có nhiều `StageRun` và có thể có nhiều lần render thử.
- Một `RenderOutput` có một hoặc nhiều `SyncRecord` nếu cần tiếp tục sau lỗi.
- Một `AppSession` có thể tạo nhiều lô, công việc và nhật ký.

## 7. Quy tắc toàn vẹn dữ liệu

- **DR-001:** Bài đã được chấp nhận vào kho không mất danh tính độc lập khi liên kết vào sự kiện. Bản đăng lại trùng không trở thành tin/kịch bản độc lập; dấu vết xuất xứ và media mới được gắn với tin đại diện (R07, R22).
- **DR-002:** Phiên bản bài hiện hành phải xác định được; phiên bản cũ không được tự ghi đè nếu đã được giữ làm lịch sử.
- **DR-003:** Một nội dung “từ lúc đó đến bây giờ” chỉ được tạo khi có EventUpdate chứa tình tiết/diễn biến mới; thêm nguồn hoặc bài đăng lại không đủ (R07).
- **DR-004:** Đoạn kịch bản chứa suy luận phải phân biệt được với đoạn dựa trên nguồn.
- **DR-005:** Trong cùng một lượt, 1-3 video của một tin phải tham chiếu các `StoryAngle` khác nhau.
- **DR-006:** Giữa các lượt sau, `VariantSignature` mới phải khác ít nhất một yếu tố so với video cũ và không được hoàn toàn giống.
- **DR-007:** Video không có video hook, audio hook hoặc thumbnail hook không được đánh dấu hoàn thành.
- **DR-008:** Video không phát được hoặc ngoài khoảng 61-70 giây không được đánh dấu hợp lệ.
- **DR-009:** Bản cục bộ của video không được xóa trước khi có `SyncRecord` xác nhận đồng bộ thành công.
- **DR-010:** Khi đồng bộ lỗi, vị trí cục bộ phải còn hiệu lực để có thể tiếp tục.
- **DR-011:** Việc xóa tệp tạm không được làm mất lịch sử công việc, nguồn hoặc dấu hiệu biến thể.
- **DR-012:** Thông tin bí mật không được xuất hiện trong `LogEntry` hoặc bảng dữ liệu người dùng quan sát.
- **DR-013:** Một công việc lỗi không được thay đổi trạng thái các công việc độc lập khác thành lỗi.
- **DR-014:** Công việc đã hoàn thành không được tự đưa lại vào đầu hàng chờ sau khi ứng dụng khởi động lại.
- **DR-015:** `AppSession` không có video hoàn thành không được để lại thư mục đầu ra rỗng.
- **DR-016:** Khi bắt đầu tạo script, job giữ tập revision nguồn và phiên bản cấu hình/prompt đã chọn; thay đổi sau đó không sửa ngược job này (R09, R16).
- **DR-017:** Voice và phụ đề karaoke từng từ phải truy được đúng script, voice và plan thực dùng; thay đầu vào làm kết quả phụ thuộc không còn hợp lệ cho phiên bản mới (R03).
- **DR-018:** Trạng thái ảnh lỗi/chưa chắc vẫn được giữ khi cho dùng nguyên gốc theo R25; không biến quyền dùng thành chứng nhận an toàn.
- **DR-019:** Xóa nguồn không xóa tin/media lịch sử; phải giữ ý định ngừng thu thập để cơ chế tự tìm nguồn không thêm lại (R24).
- **DR-020:** Lần thử lại kỹ thuật không tạo thêm đơn vị sản lượng. Video đạt kiểm tra, đã sync và đạt quy tắc biến thể chỉ được tính một lần cho lô (R10, R17).
- **DR-021:** Mỗi workspace/source/business-date có tối đa một periodic `CollectionRun`; policy revision không tạo danh tính lượt mới.
- **DR-022:** Một article đại diện tăng tối đa một lần cho mỗi topic trong business date; không cộng các bộ đếm topic thành tổng tin duy nhất toàn hệ thống.
- **DR-023:** `completed_count + active BatchCapacityReservation` không vượt target của lô.

## 8. Vòng đời dữ liệu

| Nhóm dữ liệu | Nơi tồn tại theo yêu cầu sản phẩm | Thời gian giữ dự kiến | Điều kiện xóa |
|---|---|---|---|
| Nguồn và cấu hình nguồn | Kho dài hạn | Lâu dài | Khi người dùng hoặc chính sách sau này yêu cầu |
| Bài viết và lịch sử sự kiện | Cloud | Lâu dài để tái khai thác | Chưa quyết định |
| Tài nguyên ảnh/clip/audio gốc | Cloud, chia theo loại | Lâu dài | Chưa quyết định |
| Bản media đã xử lý dùng lại được | Cloud | Lâu dài theo R13 | Ngưỡng dọn/phiên bản lỗi thời chờ kiến trúc lưu trữ |
| Voice và phụ đề riêng từng video | Trong quá trình sản xuất | Đến khi hoàn tất và không còn cần cho job đang dùng | Có thể dọn sau hoàn tất; giữ metadata và lịch sử phiên bản |
| Hook visual và hook audio | Kho do người dùng quản lý | Đến khi người dùng loại bỏ | Chưa quyết định thao tác cụ thể |
| Kịch bản, góc kể và dấu hiệu biến thể | Kho dài hạn | Đủ lâu để chống lặp và khai thác lại | Chưa quyết định |
| Tài nguyên staging trên máy render | Máy cá nhân | Khoảng năm video gần lượt xử lý | Sau khi công việc hoàn tất hoặc không còn cần |
| Tệp trung gian | Máy render hoặc cloud tạm thời | Trong thời gian xử lý | Sau khi không còn cần cho hoàn thành/tiếp tục |
| Video đầu ra | Máy render rồi cloud | Cục bộ đến khi đồng bộ; cloud lâu dài | Cục bộ xóa sau xác nhận đồng bộ |
| Nhật ký phiên | Nơi lưu vận hành | Chưa quyết định | Theo chính sách lưu log sau này |

## 9. Các bảng quan sát trên giao diện

Sản phẩm cần có khả năng trình bày tối thiểu các tập dữ liệu sau dưới dạng bảng gần với trải nghiệm Google Sheets:

| Bảng quan sát | Mỗi hàng đại diện cho | Thao tác đã được xác nhận |
|---|---|---|
| Nguồn | Một `Source` | Xem, thêm, xóa, khôi phục; sửa metadata quản trị; không dùng tệp text |
| Lượt thu thập | Một `CollectionRun` | Xem trạng thái và lỗi |
| Tin | Một `Article` | Xem, chọn và chạy công đoạn |
| Sự kiện | Một `Event` | Xem, chọn và khai thác/tạo lại |
| Tài nguyên | Một `MediaAsset` | Xem trạng thái và liên kết liên quan |
| Hook video | Một `HookVisual` | Xem và quản lý kho do người dùng thêm |
| Hook âm thanh | Một `HookAudio` | Xem và quản lý kho âm thanh |
| Kịch bản | Một `ScriptVersion` | Xem trạng thái và yêu cầu tạo lại |
| Hàng chờ video | Một `VideoJob` | Xem, bắt đầu, tiếp tục hoặc tạo lại |
| Lô | Một `Batch` | Bắt đầu và theo dõi |
| Video đầu ra | Một `RenderOutput` | Xem trạng thái hoàn thành/đồng bộ |
| Nhật ký | Một `LogEntry` | Xem tóm tắt; rê chuột để xem chi tiết lỗi |

R14 đã chốt sửa ô metadata quản trị, không sửa bài gốc, script hoặc quan hệ sự kiện. Chi tiết lọc/sắp xếp/nhóm/chọn nhiều/thao tác hàng loạt và danh sách cột cụ thể vẫn để thiết kế giao diện; không suy ra quyền sửa mọi ô từ yêu cầu trải nghiệm giống Sheets.

## 10. Dữ liệu tối thiểu để tiếp tục sau gián đoạn

Để không bắt đầu lại từ đầu, sản phẩm phải duy trì được ít nhất:

- Công việc hiện tại và công đoạn gần nhất đã hoàn thành.
- Các đầu vào và kết quả còn hiệu lực của từng công đoạn.
- Vị trí hàng chờ và trạng thái công việc.
- Số lần thử và lỗi gần nhất.
- Trạng thái tải tài nguyên về máy.
- Trạng thái render và vị trí video cục bộ nếu đã tạo.
- Trạng thái đồng bộ và xác nhận xóa cục bộ.
- Phiên bản cấu hình đã dùng cho lô và video.

Danh sách này mô tả dữ liệu cần bảo tồn, không quy định cơ chế lưu checkpoint.

## 11. Dữ liệu tối thiểu để chống lặp

Mỗi video hoàn thành phải để lại dấu vết của các yếu tố:

- Tin, sự kiện và vòng khai thác.
- Góc kể.
- Kịch bản và phiên bản kịch bản.
- Giọng đọc.
- Video hook và audio hook.
- Thumbnail trong hook.
- Nhạc nền và hiệu ứng âm thanh.
- Tập ảnh/clip và thứ tự sử dụng.
- Preset và tập hiệu ứng hình ảnh.

Trong cùng một lượt, góc kể phải khác. Giữa các lượt sau, chỉ cần ít nhất một yếu tố khác nhưng video không được hoàn toàn giống video cũ.

## 12. Dữ liệu nhạy cảm và bí mật

- Khóa, token, mật khẩu và thông tin xác thực không thuộc các bảng quan sát dạng Google Sheets.
- Nhật ký chỉ được giữ tên/nhãn tài khoản và lỗi đã loại bỏ thông tin bí mật.
- Dữ liệu gửi dịch vụ bên ngoài có thể gồm toàn bộ bài viết và media theo phê duyệt của người dùng.
- Trạng thái quyền sử dụng được lưu để quan sát và truy vết; trạng thái chưa rõ không tự động chặn tài nguyên ở phạm vi hiện tại.
- Dữ liệu về trẻ em, máu me hoặc vũ khí trong ảnh phải liên kết được với kết quả đánh giá và bản ảnh đã xử lý.
- Clip lấy từ nguồn không thuộc phạm vi xử lý nhạy cảm tự động đã xác nhận.
- Cho dùng ảnh nguyên gốc chưa chắc/kiểm tra lỗi/xử lý lỗi theo R25 không được xóa kết quả đánh giá hoặc log lỗi. Tệp không đọc được không trở thành đầu vào hợp lệ nhờ chính sách này.

## 13. Các vấn đề dữ liệu CHƯA QUYẾT ĐỊNH

- **DATA-OPEN-001 - ĐÃ CHỌN BASELINE:** PostgreSQL giữ nghiệp vụ; Drive giữ byte; SQLite journal/cache giữ tiến độ local chưa gửi. Khả thi vận hành còn qua gate tại ADR-0002/0006.
- **DATA-OPEN-002 - ĐÃ ĐÓNG THIẾT KẾ:** Google Sheets không là lõi/đường chạy v1; UI bảng theo ADR-0007. Adapter Sheets tương lai chưa nằm trong phạm vi hiện tại.
- **DATA-OPEN-003 - CÒN MỘT PHẦN:** R14 chốt sửa metadata quản trị; danh sách cột cụ thể còn mở.
- **DATA-OPEN-004 - ĐÃ ĐÓNG NGHIỆP VỤ:** R15/R24 chốt thêm/xóa/khôi phục nguồn trên UI, chặn tự thêm lại, giữ dữ liệu cũ; bỏ tệp text.
- **DATA-OPEN-005:** Cách nhận biết hai địa chỉ hoặc hai bài là trùng nhau.
- **DATA-OPEN-006 - CÒN MỘT PHẦN:** R06 chốt giữ riêng nếu chưa chắc; thuật toán/ngưỡng liên kết còn mở.
- **DATA-OPEN-007 - ĐÃ ĐÓNG NGHIỆP VỤ:** R07 chỉ cho EventUpdate khi có tình tiết/diễn biến mới; cách đo/đánh giá cụ thể còn thuộc kiểm chứng.
- **DATA-OPEN-008:** Mức nội dung bài và lịch sử phiên bản cần lưu lâu dài.
- **DATA-OPEN-009:** Danh sách metadata quyền sử dụng phải lưu.
- **DATA-OPEN-010:** Danh sách nhóm chủ đề bổ sung và cấu trúc chủ đề cha-con.
- **DATA-OPEN-011:** Tiêu chí xếp nguồn `Tier 1/2/3`.
- **DATA-OPEN-012:** Quy tắc chia loại dữ liệu giữa bốn tài khoản Google Drive.
- **DATA-OPEN-013 - CÒN MỘT PHẦN:** R13 chốt giữ media dùng lại được và cho dọn voice/subtitle riêng; số ngày giữ log/tệp lỗi/intermediate vẫn mở.
- **DATA-OPEN-014:** Cách xác định hai video hoàn toàn giống nhau.
- **DATA-OPEN-015:** Quy tắc tên tệp hợp lệ và độ dài tối đa.
- **DATA-OPEN-016:** Múi giờ dùng cho lịch quét và tên thư mục `YY-MM-DD`.
- **DATA-OPEN-017:** Danh sách trạng thái cuối cùng và các chuyển đổi trạng thái được phép.
- **DATA-OPEN-018 - ĐÓNG MỘT PHẦN:** workspace boundary tối thiểu theo ADR-0012; schema cụ thể và chứng minh tenant isolation chưa thực hiện.
- **DATA-OPEN-019:** Cách tham chiếu an toàn tới tài khoản, hạn mức và vai trò AI.

Các vấn đề trên phải được giải quyết trong đúng giai đoạn yêu cầu, nghiên cứu hoặc kiến trúc. Không mục nào được ngầm hiểu là đã chọn Google Sheets hay bất kỳ cơ sở dữ liệu nào.

## 14. Giả định

**Không có GIẢ ĐỊNH nào được dùng làm quyết định chính thức trong bản đồ dữ liệu này.**

Tên đối tượng và thuộc tính là ngôn ngữ chung để mô tả dữ liệu cần tồn tại. Chúng không phải tên bảng, tên collection, định dạng tệp hoặc hợp đồng API đã được phê duyệt.

## 15. Tiêu chí phê duyệt

Bản đồ dữ liệu được phê duyệt khi người dùng xác nhận:

1. Các miền dữ liệu bao phủ đúng vòng đời từ nguồn tin đến video hoàn thành.
2. Các đối tượng và quan hệ phản ánh đúng cách sản phẩm cần vận hành.
3. Quy tắc dữ liệu về suy luận, biến thể, gián đoạn và đồng bộ là chính xác.
4. Trải nghiệm dạng bảng được ghi nhận mà không mặc định Google Sheets là cơ sở dữ liệu chính.
5. Các mục `DATA-OPEN-*` được phép tiếp tục ở trạng thái chưa quyết định.

Sau khi tài liệu được phê duyệt, bước tiếp theo là **06 - Xác định yêu cầu chất lượng hệ thống**.

## 16. Bổ sung logic cho luồng dữ liệu bước 09

Phần này hoàn thiện các khoảng thiếu MAP-DATA-001 đến MAP-DATA-009. Tên dưới đây mô tả kết quả cần truy vết; chưa yêu cầu thêm bảng hay dịch vụ riêng.

| Kết quả/quan hệ cần mô tả | Nội dung cần giữ | Phân hệ chủ trì |
|---|---|---|
| Dấu vết bản đăng lại | URL, nguồn, thời điểm, tin đại diện, lý do trùng và media mới; không dùng như tin mới trong bộ đếm ngày | B; A cung cấp nguồn, C nhận media |
| Tiến độ thu thập theo chủ đề/ngày | Ngưỡng cấu hình, số tin mới không trùng đã chấp nhận, Tier đã xét, lượt chạy và lý do bỏ qua nguồn | G; B/D cung cấp phân loại và kết quả lọc |
| Media gốc/phái sinh | Định danh bản gốc, bản xử lý, cấu hình biến đổi, kết quả đánh giá, dấu nội dung, nơi lưu, tình trạng tệp, công việc đang tham chiếu | C/E; I có thẩm quyền vị trí tệp |
| Ngữ cảnh sáng tạo đã chốt | Job, revision nguồn, cấu hình/prompt, preset version đã chọn, lịch sử dùng để chống lặp | D/J; G ghi mốc bắt đầu script |
| Kết quả voice | Script version, giọng, provider/model/cấu hình thực dùng, tệp và thời lượng đo được | E; C/I quản lý tài nguyên/tệp |
| Kết quả phụ đề | Script version, voice version, chữ/timing từng từ và kết quả đối chiếu | E; F hiển thị lên video |
| Kết quả kiểm tra nội dung | Phiên bản được kiểm tra, căn cứ nguồn, nhãn suy luận, lý do đạt/chưa đạt, khác biệt so lịch sử | D |
| Kế hoạch và kết quả thực dựng | Plan version, asset/rendition, thumb, hook, nhạc/SFX, voice/subtitle, timeline và preset thực dùng | D/F; không coi đổi ID là đổi nội dung |
| Lượt thử và công việc mới | Job gốc, lần thử, đầu vào/cấu hình giữ nguyên hay biến thể mới; kết quả hợp lệ nào đã được tính | G |
| Trạng thái độc lập | Render/check, sync, hoàn thành job, cleanup riêng; lỗi dọn không xóa bằng chứng hoàn thành | F/I/G theo quyền sở hữu |
| Tiến độ vòng qua nhiều phiên | Vòng khai thác, tin đã xét, kịch bản đã dùng, vị trí tiếp tục, mục tiêu lô còn thiếu | G/D/B |

**Không ghi đè lịch sử:** nguồn/prompt mới chỉ dùng từ mốc R09/R16; render dùng các phiên bản cụ thể. Nếu voice/subtitle đã được dọn, thử lại cần tái tạo đúng ngữ cảnh còn truy vết được hoặc báo thiếu đầu vào, không giả vờ tệp vẫn tồn tại và không hứa AI tái tạo giống từng byte.

## 17. Bổ sung từ kiểm toán kiến trúc

Phần này bổ sung các đối tượng logic cần cho giao tiếp bền vững theo [ADR-0004](./adr/0004-commit-idempotency-and-fencing.md) và [ADR-0006](./adr/0006-drive-artifacts-and-local-journal.md). Đây chưa phải tên bảng hoặc schema SQL.

| Đối tượng logic | Dữ liệu tối thiểu | Chủ sở hữu và bất biến |
|---|---|---|
| `Workspace` | ID, trạng thái, cấu hình mặc định | J; v1 có một workspace, nhưng mọi dữ liệu/config/secret lookup phải có scope |
| `CommandReceipt` | Request ID, command type, target, người/thiết bị gửi, trạng thái nhận, kết quả/ref lỗi | G; gửi lặp cùng request ID không tạo lệnh mới |
| `OutboxEvent` | Event ID, aggregate/revision, event type, payload version, trạng thái dispatch, số lần thử | Module ghi nghiệp vụ; được ghi cùng transaction với thay đổi nguồn |
| `ExecutionGrant` | Operation ID, stage/job, input revision, device/capability, generation, recovery epoch, thời hạn/trạng thái | G; generation hoặc epoch cũ không được commit hoặc cho cleanup |
| `OperationReceipt` | Operation ID, generation, recovery epoch, input/output revision, result status, checksum/ref, thời điểm commit | Module sở hữu kết quả; lost ACK trả receipt đã commit thay vì thực hiện lại |
| `ArtifactVersion` | Artifact ID/revision, producer attempt, content hash, size/MIME, trạng thái bất biến | I phối hợp module tạo tệp; byte khác phải có revision khác |
| `ArtifactLocation` | Artifact revision, StorageArea/file ID hoặc local manifest ref, sync/verify status, checksum bằng chứng | I; location không phải danh tính sản phẩm, tên tệp không là bằng chứng sync |
| `CompletionLedger` | Video job, accepted render artifact, QC refs, variant signature, sync receipt, batch contribution | G; mỗi video job có tối đa một completion hợp lệ và tăng bộ đếm lô một lần |
| `BatchCapacityReservation` | Batch/job, trạng thái active/converted/released, thời điểm và reason | G; `completed + active reservations` không vượt target; retry không tạo suất mới |
| `VariantReservation` | Job/snapshot/round, article/event scope, script/plan refs, chữ ký D, validation ref, trạng thái ACTIVE/CONVERTED/RELEASED | G; một active/job; giữ qua WAITING, chuyển cùng completion hoặc release cùng terminal job theo CT-ORC-012 |
| `VariantRegistryRevision` | Workspace và revision sổ completed/active reservations | G; tăng nguyên tử khi sổ thay đổi; token của validation dùng compare-and-swap, không thay history hoặc signature của D |
| `CleanupAuthorization` | Artifact/location, căn cứ completion, reference count/check, generation, recovery epoch, trạng thái dọn | I; không dọn output chưa sync, tệp còn dùng hoặc quyền từ worker/epoch cũ |
| `RecoveryEpoch` | Workspace/system scope, epoch opaque hiện hành, lý do/thời điểm đổi | G/J; restore tạo giá trị mới trước khi mở writer để vô hiệu grant/message cũ |
| `LocalJournalEntry` | Device, operation/generation/recovery epoch, local path, checksum, upload secret ref/offset, trạng thái gửi | I trên desktop; receipt chưa gửi là dữ liệu phục hồi phải giữ và phải reconcile epoch, không phải cache bỏ được |

Các đối tượng nghiệp vụ có thể thuộc workspace phải mang `workspace_id` trong danh tính hoặc scope unique phù hợp. `workspace_id` không tự chứng minh tenant isolation; phép thử cách ly thuộc ADR-0012.

`VideoJob.status`, `StageRun.status`, `RenderOutput.completion_status` và `SyncRecord` không được tự thay thế các đối tượng trên. Trạng thái hiển thị là projection từ commit có bằng chứng; không cho một ACK, tên tệp hoặc workflow state đơn lẻ biến video thành hoàn thành.

**Lưu lâu dài không đồng nghĩa mọi byte phải ở cùng chỗ:** metadata nghiệp vụ và byte media có nơi lưu khác nhau theo kiến trúc bước 08: PostgreSQL giữ nghiệp vụ, Drive giữ artifact; Google Sheets không mặc định là lõi. Mô hình ở đây vẫn là logic, không phải schema SQL.

SourceCandidate READY được kiểm tra lại tại registration và kết thúc MATCHED_EXISTING/BLOCKED_TOMBSTONE/REJECTED nếu dữ liệu/policy đã đổi (CT-SRC-003A). Candidate, Source, receipt và outbox phải nhất quán trong transaction.

CollectedDocument chỉ tồn tại khi package đủ schema/định danh/provenance. Nội dung không đủ là eligibility/disposition của package hợp lệ; payload sai cấu trúc là lỗi biên, không tạo Article hoặc document giả (CT-SRC-006).

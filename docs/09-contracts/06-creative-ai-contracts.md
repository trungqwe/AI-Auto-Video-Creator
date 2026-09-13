# 06. Hợp đồng Bộ não nội dung AI

> Trạng thái: **Bản thiết kế trước triển khai**  
> Chủ sở hữu: D.  
> Đây là phân hệ tạo quyết định sáng tạo, không sở hữu bài gốc, media byte, secret hay trạng thái workflow.

## 1. Chuỗi output bất biến

`ProductionSnapshot` → `ContentAnalysis` → `StoryAngleSet` → `ScriptVersion` → `ProductionPlan` → `VariantValidation` → `OutputMetadata`

Mỗi output có ID/revision riêng, input refs, model/provider/prompt revision, policy revision, thời gian và provenance. Output mới không ghi đè output cũ.

### CT-AI-000 — Untrusted input boundary

Nội dung bài, metadata, caption, OCR/transcript và mọi text lấy từ nguồn ngoài là `untrusted_data`. Dữ liệu này được đặt trong trường có cấu trúc tách khỏi system/developer instruction; câu lệnh nằm trong dữ liệu không có quyền đổi policy, gọi tool, tải URL, chọn secret hay tạo resource ref. Mọi ref do model đề xuất phải được resolver kiểm tra tồn tại, workspace, revision và allowlist trước khi dùng. Typed schema không thay thế các kiểm tra này.

## 2. Khóa nguồn sản xuất

### CT-AI-001 — `BuildProductionSnapshot`

Input:

- article/event/event-update refs đủ điều kiện;
- source/provenance revisions;
- media/hook candidate index revisions;
- config/prompt/preset policy revisions;
- batch/job refs;
- production mode `single_article`, `multi_article_event`, `from_then_to_now`;
- recent variant exclusions.

Output `ProductionSnapshot`:

- toàn bộ refs và revision chính xác;
- source set fingerprint;
- configuration bundle fingerprint;
- eligibility reason;
- snapshot timestamp;
- immutable snapshot ID.

Snapshot phải commit trước lần gọi AI tạo script đầu tiên. Sau mốc này, nguồn/cấu hình mới chỉ áp dụng cho job chưa snapshot hoặc lần sản xuất sau.

## 3. Phân tích nội dung

### CT-AI-002 — `AnalyzeContent`

Input: production snapshot ref và analysis policy.

Snapshot/input phải giữ `trust_class` và provenance của dữ liệu nguồn. D không được nâng `untrusted_data` thành instruction chỉ vì nội dung nguồn tự nhận là chỉ dẫn hệ thống.

Output `ContentAnalysis`:

- chủ đề, entities, timeline, locations;
- source-backed facts/claims cùng evidence refs;
- uncertainties và contradictions nếu phát hiện;
- event relation và update context;
- sensitivity/content-risk flags;
- candidate narrative opportunities;
- media needs;
- model/prompt trace.

Hệ thống không có hard gate kiểm chứng đa nguồn, nhưng không được xóa provenance hoặc biến uncertainty thành fact đã xác nhận trong representation nội bộ.

## 4. Góc kể

### CT-AI-003 — `GenerateStoryAngles`

Input:

- analysis revision;
- số lượng yêu cầu 1-3 cho mỗi tin trong một lượt;
- lịch sử góc/script gần đây;
- preset/style candidates;
- variation policy revision.

Theo CT-ORC-012, input còn có workspace, job/snapshot/round, tập article/event refs đã khóa, active variant reservations của mọi lô liên quan và `variant_registry_revision` của lần đọc nhất quán. Validation trước completion phải nhận reservation ID và chữ ký thực tế gắn exact output hash; không tái sử dụng kết quả chỉ kiểm tra plan để xác nhận output.

Mỗi `StoryAngle` có:

- angle ID/title/summary;
- narrative question;
- focus entities/timeframe;
- source evidence refs;
- planned inference/creative elements;
- distinction fingerprint;
- suitability và risk flags.

Bất biến:

- 1-3 video của cùng tin trong cùng lượt phải khác góc kể.
- Không dùng lại kịch bản gần nhất vừa làm.
- Khi đã khai thác hết angle set ban đầu, lần sau có thể quay lại tin để sinh angle set mới.

## 5. Script và phân loại phát ngôn

### CT-AI-004 — `GenerateScript`

Precondition điều phối: desktop production capability đang hoạt động. Nếu chưa có, G giữ job ở `WAITING_CAPABILITY`; D không bắt đầu invocation chỉ để workflow treo giữa chừng.

Input:

- angle ref;
- snapshot/analysis revisions;
- target duration 61-70 giây;
- language policy;
- voice/style/preset candidate refs;
- recent script exclusions;
- inference disclosure policy.

Output `ScriptVersion`:

- narration segments có thứ tự;
- hook intent và thumbnail transition;
- scene intents;
- estimated timing;
- pronunciation hints;
- claim annotations;
- explicit inference disclosures;
- source refs theo segment;
- script fingerprint;
- model/prompt/provider usage metadata.

Mỗi segment/claim được phân loại:

| `claim_mode` | Ý nghĩa | Yêu cầu đầu ra |
|---|---|---|
| `source_backed` | Có bằng chứng trong snapshot | Giữ source refs |
| `inference` | Suy luận từ dữ liệu | Phải thể hiện rõ là suy luận |
| `creative_hypothesis` | Chi tiết sáng tạo không có trong nguồn | Phải dùng ngôn ngữ giả định, không trình bày như fact |
| `transition` | Câu dẫn không khẳng định sự kiện | Không cần source claim |

Không có script edit/approval contract trong v1.

## 6. Nội dung “từ lúc đó đến nay”

### CT-AI-005 — `AuthorizeTimelineNarrative`

Mode `from_then_to_now` chỉ hợp lệ khi snapshot chứa `EventUpdateAccepted` với tình tiết mới. Nguồn mới, bài repost hoặc media mới đơn thuần không đủ điều kiện.

Nếu điều kiện không đạt, operation trả `POLICY_VIOLATION`; D không tự đổi mode mà không ghi quyết định mới.

## 7. Chọn hook, media và âm thanh

### CT-AI-006 — `SelectCreativeAssets`

Input:

- script/angle/snapshot refs;
- candidate sets từ C;
- five-preset registry revision;
- recent usage/exclusions;
- technical constraints từ E/F;
- music/SFX policy.

Output:

- visual hook ref;
- audio hook ref;
- thumbnail ref và overlay intent;
- scene-to-media assignments có thứ tự;
- music/SFX intents hoặc candidate refs;
- fallback candidates;
- rationale và score components;
- selection fingerprint.

Phải có visual hook, audio hook và thumbnail. Hệ thống tự tìm/thu thập nhạc nền và SFX; mọi lựa chọn vẫn phải có provenance/risk metadata khi biết.

## 8. Kế hoạch dựng

### CT-AI-007 — `BuildProductionPlan`

Precondition điều phối: desktop production capability đang hoạt động, cùng session/capability context với job đang sản xuất.

`ProductionPlan` tối thiểu có:

- exact script version;
- preset revision;
- timeline/scene list;
- asset/rendition refs và intended time ranges;
- visual/audio hook placement;
- thumbnail placement nằm trong time range của hook;
- crop/overlay/effect intents;
- voice profile intent;
- music/SFX cue intents;
- subtitle/karaoke style intent;
- transition/fallback rules được phép;
- output metadata ref hoặc requirement;
- plan fingerprint.

Plan mô tả intent; E/F resolve thành thông số kỹ thuật trong phạm vi preset. F không được tự thay câu chuyện hoặc asset mà không có fallback được plan cho phép.

## 9. Kiểm tra biến thể

### CT-AI-008 — `ValidateVariant`

Input:

- candidate script/plan fingerprints;
- lịch sử video hoàn thành của cùng article/event;
- các video trong cùng lượt;
- variation policy revision.

Kết quả:

- `valid`;
- `same_run_angle_distinct`;
- `exact_duplicate`;
- các yếu tố khác biệt thực tế;
- nearest prior variant refs;
- reason codes.

Kết quả lưu thành validation ref bất biến, chứa input refs/hashes, policy, phạm vi đối chiếu, registry revision, phase (`plan` hoặc `output`) và kết quả. `valid=true` không tự cấp quyền completion: G kiểm tra compare-and-swap theo CT-ORC-012. Registry đổi thì đối chiếu lại; không gọi AI bên trong transaction. Reservation của chính job được loại khỏi đối chứng, không bỏ qua các job khác. Revision registry không thay quy tắc khác góc/khác yếu tố; nó ngăn dùng bằng chứng đã lỗi thời.

Bất biến:

1. Trong cùng lượt: khác góc kể, không chỉ đổi hiệu ứng.
2. Giữa các lượt: không hoàn toàn giống video cũ và ít nhất một yếu tố thực tế khác.
3. Yếu tố khác có thể là giọng, âm thanh, hook, thứ tự/chọn media, hiệu ứng, nội dung, cách dẫn, nhạc nền hoặc góc khai thác.
4. Chỉ tính khác biệt từ artifact/plan/script thực tế, không chỉ từ seed hay ID.

## 10. Metadata đầu ra

### CT-AI-009 — `GenerateOutputMetadata`

Output:

- title/caption chuẩn SEO;
- 3-4 hashtag;
- filename-safe representation;
- original display representation;
- language;
- source job/output refs;
- metadata revision.

Filename dùng title/caption và hashtag theo quyết định user, nhưng phải qua sanitize của storage contract để hợp lệ trên filesystem mà không làm mất bản hiển thị gốc.

## 11. Provider và consistency

### CT-AI-010 — `AIInvocationRecord`

D không nhận secret. D yêu cầu J resolve route/capacity và nhận provider handle ngắn hạn hoặc worker-bound access.

Mỗi invocation ghi:

- role/capability;
- model/provider/account/project refs;
- prompt/config revision;
- input/output fingerprint;
- token/usage/cost thuộc phạm vi dự án;
- latency, attempt và fallback path;
- validation result;
- redacted error.

Fallback local được phép khi phù hợp vai trò, nhưng output vẫn phải qua cùng schema và validation. Không tự thêm dịch vụ trả phí.

Prompt/adapter phải giữ biên instruction-data khi đổi provider hoặc fallback. Model không được là bên duy nhất xác nhận source ref, disclosure, tool action hoặc policy compliance của chính output nó tạo.

## 12. Acceptance contract

1. Snapshot không thay đổi sau khi job bắt đầu tạo script.
2. Suy luận và chi tiết sáng tạo được đánh dấu rõ trong script/output.
3. “Từ lúc đó đến nay” bị chặn nếu không có diễn biến mới đã chấp nhận.
4. Trong cùng lượt, 1-3 video khác góc kể.
5. Giữa các lượt, video không trùng hoàn toàn và có ít nhất một khác biệt thực tế.
6. Production plan luôn có visual hook, audio hook và thumbnail trong vùng hook.
7. Mọi output AI truy được model, prompt, config và input revision.
8. Chỉ dẫn nằm trong dữ liệu nguồn không được đổi policy, gọi tool hoặc tạo resource ref chưa qua resolver.

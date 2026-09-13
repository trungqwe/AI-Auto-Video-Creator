# 08. Hợp đồng dựng video và kiểm tra đầu ra

> Trạng thái: **Bản thiết kế trước triển khai**  
> Chủ sở hữu: F.  
> Caller: G.  
> Artifact owner: I.

## 1. Nguyên tắc

F là bộ máy thực thi kế hoạch dựng đã được khóa. F được phép resolve thông số kỹ thuật theo preset và fallback đã khai báo; F không được tự viết lại nội dung, đổi góc kể hoặc chọn asset ngoài phạm vi cho phép.

## 2. Preset contract

### CT-RND-001 — `RenderPresetRevision`

Hệ thống có đúng 5 preset mẫu được thiết kế chi tiết. Mỗi revision gồm:

- visual rhythm và scene duration ranges;
- layout/crop/zoom/transition rules;
- thumbnail overlay style;
- typography và karaoke subtitle style;
- hook treatment;
- voice/music/SFX mix rules;
- color/effect rules;
- output profile;
- fallback constraints;
- compatibility requirements;
- preset fingerprint.

Tên và nội dung cụ thể của 5 preset là sản phẩm của bước thiết kế template/UX sau này. Hợp đồng chỉ khóa số lượng mẫu ban đầu và tính versioned.

## 3. Render package

### CT-RND-002 — `ResolveRenderPackage`

Input:

- production snapshot, script, plan và preset revisions;
- voice và word timing refs;
- resolved media/hook/thumbnail/music/SFX rendition refs;
- output metadata revision;
- language validation refs gắn với exact script, voice, subtitle và output metadata revisions;
- output profile revision;
- job/stage/execution grant.

Output `RenderPackage` bất biến:

- exact artifact version/hash/size/type của mọi input;
- timeline đã resolve;
- visual hook, audio hook và thumbnail placement;
- burn-in subtitle/karaoke configuration;
- voice/music/SFX mix plan;
- allowed technical fallback list;
- local materialization manifest;
- package fingerprint.

Mọi input phải có availability phù hợp. Package không chứa URL tùy ý hoặc đường dẫn shell do AI cung cấp.

D cung cấp language validation cho script và output metadata; E cung cấp bằng chứng voice locale/provider output và subtitle text gắn exact script/voice revisions. F tổng hợp các refs này trong render package và kiểm tra lại binding; không phân hệ nào chỉ dựa vào trường `language=en` tự khai của chính output đang được kiểm tra.

### CT-RND-003 — `ValidateRenderPackage`

Hard preconditions:

1. Có visual hook.
2. Có audio hook.
3. Có thumbnail với time range nằm trong time range của hook.
4. Có exact voice và word timing tương thích script/hash.
5. Có bằng chứng ngôn ngữ tiếng Anh gắn đúng script, voice, subtitle và output metadata revisions.
6. Có ít nhất một visual asset cho mọi khoảng timeline yêu cầu.
7. Mọi artifact local cần thiết đã verify hash.
8. Output path được I cấp, nằm trong staging root được phép.
9. Preset và tool capability tương thích.

Thiếu điều kiện trả lỗi trước khi render nặng.

## 4. Render

### CT-RND-004 — `RenderVideo`

Input: immutable render package, operation key và execution grant.

Output `RenderAttempt`:

- render attempt ID;
- package fingerprint;
- output artifact ref;
- renderer/tool/build version;
- started/finished time;
- wall time, CPU/GPU metrics và peak disk;
- command specification đã chuẩn hóa/redacted;
- warnings;
- operation receipt.

Quy tắc:

- Không nối shell command từ text/path do model tạo.
- Output từng attempt có artifact version riêng.
- Timeout hoặc worker crash sau khi render có thể tạo `OUTCOME_UNKNOWN`; phải probe/reconcile file trước retry.
- Render thành công kỹ thuật chưa phải video hoàn thành.

## 5. Kiểm tra đầu ra

### CT-QC-001 — `InspectOutput`

Input:

- output artifact version;
- render package;
- quality policy revision;
- job/variant refs.

Output `QualityReport`:

| Gate | Loại | Điều kiện |
|---|---|---|
| `FILE_PLAYABLE` | Hard | Probe/decode được video |
| `DURATION_RANGE` | Hard | 61-70 giây |
| `VISUAL_HOOK_PRESENT` | Hard | Visual hook thực sự xuất hiện |
| `AUDIO_HOOK_PRESENT` | Hard | Audio hook thực sự nghe/được mix trong vùng hook |
| `THUMBNAIL_PRESENT` | Hard | Thumbnail liên quan xuất hiện trong vùng hook |
| `SUBTITLE_BURNED_IN` | Hard | Phụ đề gắn vào khung hình |
| `KARAOKE_TIMING_VALID` | Hard | Highlight/timing theo từng từ hợp lệ |
| `VOICE_AUDIBLE` | Hard | Có voice và không bị lỗi âm thanh nghiêm trọng |
| `ENGLISH_OUTPUT_VALID` | Hard | Script, voice, subtitle, title và hashtag có bằng chứng tiếng Anh gắn đúng revision |
| `OUTPUT_PROFILE_VALID` | Hard | Container/codec/dimensions theo profile |
| `INFERENCE_DISCLOSURE_PRESENT` | Hard có điều kiện | Các segment suy luận/sáng tạo có biểu đạt rõ |
| `VISUAL_CONTINUITY` | Warning/score | Không có khoảng trống hoặc frame lỗi đáng kể |
| `AUDIO_MIX_QUALITY` | Warning/score | Voice, nhạc và SFX ở mức chấp nhận theo policy |

Mỗi gate có status, evidence/time range, measured value, threshold revision và reason. Ngưỡng kỹ thuật chi tiết là **CẤU HÌNH** và sẽ được chốt bằng thử nghiệm.

### CT-QC-002 — Phạm vi kiểm tra

QC không khẳng định sự thật nội dung đa nguồn. QC kiểm tra tính đầy đủ kỹ thuật, các dấu hiệu bắt buộc và consistency với package/script đã duyệt tự động. Gate ngôn ngữ kiểm tra artifact/revision thực dùng; metadata tự khai `language=en` không đủ làm bằng chứng duy nhất.

## 6. Kết quả render và điều kiện chuyển giao

### CT-RND-005 — `RenderOutputReady`

F chỉ trả output ready cho G khi:

- render receipt `succeeded`;
- output artifact tồn tại và hash khớp;
- QualityReport có tất cả hard gate đạt;
- report và artifact refs đã commit;
- execution grant còn hợp lệ.

G vẫn phải yêu cầu I đồng bộ/verify cloud và commit `CompletionLedger` trước khi phát `VideoCompleted`.

## 7. Filename và thư mục đầu ra

### CT-RND-006 — `OutputNamingIntent`

Input từ D gồm caption/title và 3-4 hashtag. I/F tạo tên filesystem an toàn, giữ:

- display title/hashtags nguyên bản trong metadata;
- filename đã sanitize;
- tên thư mục ngày `YY-MM-DD` theo quyết định user;
- output folder theo ngày và app session, chỉ trở thành thư mục hợp lệ khi có ít nhất một video hoàn thành.

Phiên đầu tiên có video hoàn thành trong ngày dùng `YY-MM-DD`; các phiên hợp lệ tiếp theo dùng `YY-MM-DD (1)`, `YY-MM-DD (2)`... theo storage/session policy. Không dùng tên thư mục để suy trạng thái hoàn thành.

## 8. Acceptance contract

1. Render package thay đổi bất kỳ input hash nào thì fingerprint đổi.
2. Render kỹ thuật thành công nhưng QC fail không tạo video hoàn thành.
3. QC xác minh visual hook, audio hook và thumbnail trong vùng hook thực sự có trong output.
4. Subtitle được burn-in và có timing từng từ.
5. Output dài ngoài 61-70 giây bị hard fail.
6. F không tự đổi script, góc kể hoặc asset ngoài fallback đã khai báo.
7. Thiếu hoặc lệch revision của bằng chứng tiếng Anh làm hard fail, không được completion.

# 07. Hợp đồng xử lý media, voice và subtitle timing

> Trạng thái: **Bản thiết kế trước triển khai**  
> Chủ sở hữu năng lực xử lý: E.  
> Chủ sở hữu catalog/artifact: C và I.

## 1. Ranh giới trách nhiệm

E thực hiện probe, phân tích, transform, transcode, audio processing, TTS và word alignment. E không:

- chọn góc kể hoặc thay script;
- tự chọn media ngoài refs/fallback đã cho;
- quyết định video hoàn thành;
- ghi trực tiếp catalog hoặc storage state do C/I sở hữu;
- xử lý nhạy cảm trên clip trong phạm vi hiện tại.

## 2. Hợp đồng job xử lý chung

### CT-PROC-001 — `ProcessingRequest`

| Trường | Ý nghĩa |
|---|---|
| `processing_operation_id` | ID idempotency |
| `stage_run_id`, `execution_grant` | Quyền thực thi/fencing |
| `input_artifact_refs` | Byte/revision chính xác |
| `operation_spec_revision` | Thông số xử lý đã version hóa |
| `expected_output_profile` | Codec, kích thước, duration hoặc schema kỳ vọng |
| `resource_limits` | CPU/GPU/RAM/disk/time budget |
| `output_storage_intent` | staging, reusable rendition hoặc per-video temporary |

### CT-PROC-002 — `ProcessingResult`

| Trường | Ý nghĩa |
|---|---|
| `disposition` | succeeded, failed, waiting, outcome_unknown |
| `output_artifact_refs` | Artifact version bất biến |
| `processor_identity` | Tool/model/version/build |
| `input_fingerprint`, `output_hashes` | Lineage và integrity |
| `technical_report` | Probe/quality/duration/codec/metrics |
| `warnings` | Cảnh báo có mã |
| `operation_receipt_ref` | Receipt side effect |

Output chỉ được coi là ready sau khi I verify artifact và C/E owner commit metadata tương ứng.

## 3. Probe và phân tích media

### CT-PROC-003 — `ProbeMedia`

Output tối thiểu:

- container/media type thực tế;
- video/audio/image streams;
- duration, dimensions, frame rate, sample rate, channels;
- codecs/pixel format;
- corruption/readability signals;
- orientation/color metadata;
- hash và size đã quan sát.

Không tin extension hoặc MIME từ nguồn nếu probe mâu thuẫn.

### CT-PROC-004 — `AnalyzeMedia`

Tùy loại media, output có thể gồm:

- keyframes/shots;
- transcript/OCR;
- entities/faces/objects;
- motion, scene, audio energy;
- semantic tags/embedding refs;
- model/version/confidence;
- analysis coverage và failure flags.

Analysis là versioned output; model mới không ghi đè kết quả cũ.

## 4. An toàn hình ảnh

### CT-PROC-005 — `AssessImageSafety`

Chỉ áp dụng cho **ảnh** từ nguồn và thumbnail liên quan. Không áp dụng xử lý nhạy cảm cho clip trong phạm vi hiện tại.

Kết quả:

| State | Ý nghĩa | Ảnh gốc có thể dùng? |
|---|---|---:|
| `SAFE` | Không phát hiện yếu tố cần xử lý | Có |
| `TRANSFORM_REQUIRED` | Có trẻ em, máu me, vũ khí hoặc vùng cần xử lý theo cấu hình | Chỉ sau transform thành công nếu policy yêu cầu |
| `UNCERTAIN` | Không đủ độ tin cậy | Có, kèm warning |
| `DETECTION_FAILED` | Không đánh giá được | Có, kèm lỗi/warning |
| `TRANSFORM_FAILED` | Xử lý yêu cầu thất bại | Có nếu tệp còn đọc được, không được ghi là xử lý thành công |
| `UNREADABLE` | Tệp không đọc được | Không |

Đây là đúng phạm vi rủi ro user đã chấp nhận: ba trạng thái `UNCERTAIN`, `DETECTION_FAILED`, `TRANSFORM_FAILED` không tự chặn ảnh gốc nếu tệp đọc được, nhưng trạng thái phải hiển thị và đi theo plan/report.

### CT-PROC-006 — `TransformSensitiveImage`

Input:

- image artifact ref;
- vùng/mask cùng confidence;
- detected categories gồm trẻ em, máu me, vũ khí hoặc category được policy cho phép;
- transform policy revision;
- mục tiêu blur trẻ em, làm mờ/đổi màu vùng máu me hoặc xử lý vùng vũ khí theo cấu hình đã version hóa;
- output technical profile.

Output:

- processed artifact ref;
- transform mask/evidence ref;
- processor version;
- post-transform assessment;
- lineage từ ảnh gốc;
- success/warning/failure state.

Ảnh gốc luôn được giữ trên cloud theo retention policy. Phiên bản đã xử lý dùng lại được cũng được giữ.

Hook visual do user nhập đã được làm mờ và không chạy lại pipeline safety này. Thumbnail lấy từ nguồn vẫn phải được đánh giá như ảnh nguồn.

Phát hiện vũ khí phải tạo được transform request mang category và policy revision. Hợp đồng không tự chọn kiểu che/màu cho mọi vũ khí; cấu hình quyết định phép biến đổi, còn R25 vẫn áp dụng nếu nhận diện/transform lỗi và ảnh gốc còn đọc được.

## 5. Chuẩn hóa media

### CT-PROC-007 — `NormalizeMedia`

Các operation có thể gồm crop, resize, pad, color conversion, transcode, audio normalize, extract frame và duration trim theo specification.

Bất biến:

- không thay đổi bản gốc;
- output là rendition mới có lineage;
- không crop mất chủ thể ngoài focus rule trong plan;
- clip được chuẩn hóa kỹ thuật nhưng không chạy safety blur/recolor nhạy cảm;
- transform phải deterministic trong phạm vi tool/version/spec đã ghi, trừ khi có trường seed/version rõ ràng.

## 6. Voice

### CT-TTS-001 — `CreateVoiceTrack`

Input:

- exact `script_version_id` và script fingerprint;
- voice profile/provider route refs;
- pronunciation hints;
- pacing/emotion/style parameters;
- expected language;
- operation key và execution grant.

Output:

- voice artifact ref;
- script/voice fingerprint binding;
- actual duration;
- provider/model/voice revision;
- usage/cost metrics;
- warnings và receipt.

Voice là dữ liệu riêng từng video và có thể cleanup sau khi video hoàn tất, theo authorization của I.

## 7. Word timing và subtitle

### CT-SUB-001 — `CreateWordTiming`

Input:

- exact script version;
- exact voice artifact version/hash;
- language/tokenization policy;
- alignment model/tool revision.

Output:

- ordered word/token timings;
- `start_ms`, `end_ms`, text, normalized text;
- confidence và alignment gaps;
- segment/sentence boundaries;
- script fingerprint và voice hash;
- timing artifact ref;
- validation report.

Bất biến:

1. Timing phải tăng đơn điệu, không âm và nằm trong duration voice.
2. Timing phải gắn với đúng script và voice hash.
3. Đổi script hoặc voice làm timing cũ không còn hợp lệ.
4. Subtitle cuối phải burn-in trong video và hỗ trợ hiệu ứng karaoke theo từng từ.

## 8. Audio nền và SFX

### CT-AUD-001 — `PrepareAudioBed`

Input:

- production plan cues;
- music/SFX artifact refs hoặc search intents đã resolve;
- voice artifact ref;
- preset audio policy;
- target loudness/mix constraints.

Output:

- prepared music/SFX renditions;
- cue timing refs;
- loudness/peak report;
- provenance/risk metadata;
- warnings.

E không tự đổi mood hoặc chọn bài mới nếu plan không cho fallback. Mọi thay thế phải được ghi vào resolved render package.

## 9. Cache và retention

### CT-PROC-008 — Phân loại output

| Loại | Ví dụ | Retention intent |
|---|---|---|
| Reusable | ảnh blur/recolor, clip normalize, analysis/index | Giữ cloud theo policy |
| Per-video | voice, word timing, mix tạm | Có thể dọn sau completion |
| Diagnostic | frame/log/report debug | Theo retention ngắn, có audit |

Cleanup không do E tự thực hiện; E chỉ gắn retention intent để I đánh giá.

## 10. Acceptance contract

1. Mọi output truy ngược được input, spec và processor version.
2. Safety transform chỉ áp dụng cho ảnh, không áp dụng clip.
3. Ảnh lỗi/không chắc vẫn có thể dùng theo R25 nhưng không bị ghi nhầm là safe/processed.
4. Subtitle timing khớp exact script và voice hash.
5. Đổi voice/script làm invalid timing downstream.
6. Original và rendition dùng lại được không bị xóa cùng tệp tạm per-video.

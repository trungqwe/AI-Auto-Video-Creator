# Báo cáo gói công việc PW-D1-FIX1

Gói công việc PW-D1-FIX1 khắc phục nhóm lỗi R14 (phát hiện khi CP7-4 gọi AI thật qua 9Router: HTTP 200 nhưng gặp lỗi AnalysisRejected ai_output_schema_violation facts[0].evidence_refs[0] wrong_type).

## 1. Các tệp đã sửa

- src/creative/application/prompts.py
- src/creative/application/pipeline.py
- tests/integration/prod_wiring/test_pw_d1_roles_prompts.py
- docs/delivery-evidence/pw-d1-fix1/report.md

## 2. Thiết kế và giải pháp kỹ thuật

1. Bổ sung khoá ref trong _data_item (pipeline.py):
   - Phương thức CreativePipeline._data_item đưa ref nguồn của mỗi mục dữ liệu vào chính JSON dưới khoá ref (gồm đủ 4 trường workspace_id, ref_type, ref_id, revision_id từ provenance của mục qua _plain(provenance)).
   - Mục dữ liệu bài viết dựng qua _article_data tự động mang khoá ref tương ứng vì nó gọi qua _data_item với ResourceRef(workspace_id, REF_ARTICLE_REVISION, item['article_id'], item['article_revision_id']).
   - Ref nằm trong khối dữ liệu phi tín nhiệm (untrusted data), không đưa vào instructions và không làm thay đổi các trường dữ liệu khác.

2. Cập nhật DEFAULT_PROMPTS cho 6 vai trò theo yêu cầu parser:
   - content_analysis: Nêu rõ cấu trúc đối tượng tham chiếu với 4 trường, yêu cầu chép nguyên văn ref từ mục dữ liệu kind article; liệt kê đầy đủ 3 giá trị của enum event_relation (standalone, same_event, event_update); update_context; uncertainties và contradictions dạng danh sách đối tượng có id, text, evidence_refs; giữ nguyên _BOUNDARY.
   - story_angles: Nêu rõ cấu trúc angles, requested_count, focus_entities, timeframe, evidence_refs là danh sách reference object chép từ ref mục bài viết.
   - script_generation: Nêu rõ language theo language_policy, target_range (min_seconds, max_seconds), speech_rate, hook_intent, thumbnail_transition, pronunciation_hints, 4 giá trị của enum claim_mode (source_backed, inference, creative_hypothesis, transition), source_refs và disclosure.
   - asset_selection: Hướng dẫn chọn từ các danh sách ứng viên (media_candidates, visual_hook_candidates, audio_hook_candidates, thumbnail_candidates), chép workspace_id từ khoá ref của mục dữ liệu có ref và dựng reference object 4 trường cho từng loại ứng viên.
   - production_plan: Nêu rõ toàn bộ cấu trúc timeline, segments, start_ms, end_ms, transition_intent, visuals, hook_placement, voice_profile_intent, music_cues, sfx_cues, subtitle_style_intent, 3 giá trị của enum allowed_fallbacks (replace_asset, drop_overlay_effect, simplify_transition), output_metadata_ref/requirement.
   - output_metadata: Nêu rõ title, caption và 3-4 hashtags bắt đầu bằng ký tự #.

3. Nâng cấp tự động prompt mặc định cũ trong seed_default_prompts:
   - Khai báo PREVIOUS_DEFAULT_PROMPT_HASHES chứa 6 mã băm SHA-256 hex của 6 bản prompt mặc định ban đầu:
     - content_analysis: 4084716134088fcfc1a1ff9a2b71ec7fc90299952822fac3bb64c40dddf362b0
     - story_angles: 4e50d79baded40e0ab945e64ad12cc5a4439cfb0bd8855b5c493816a5d0d87d8
     - script_generation: cfe414943cef039c17b5b35c3c5e0b51a188dd04efa24f51b074960278d2b3be
     - asset_selection: f0bb43142d3e6e6ddd5f6ffac0b6b51f76b9a41df3d4c34b32acacd5de28f793
     - production_plan: 89cbc7ae46ade6f3d4959f421433c9dc06ff6ea57c5ca6864b6ad37e10a4a2ed
     - output_metadata: 3ef7ede4d145f6566bb102e4853cad45e27832f2928b5b2c6d1cff2b3b172cf3
   - Khi seed_default_prompts gặp RevisionConflictError (workspace đã có bản gieo trước), hàm kiểm tra nội dung hiện hành: nếu mã băm SHA-256 khớp với một trong các bản mặc định cũ thì thực hiện put_config nâng lên bản mới với expected_revision là revision hiện hành.
   - Nếu người dùng đã chỉnh sửa nội dung prompt, mã băm không khớp và bản sửa của người dùng được bảo toàn tuyệt đối, không bị ghi đè.
   - Cơ chế nâng cấp hoàn toàn mang tính lũy thừa (idempotent), lần gọi lặp lại không tạo thêm revision mới.

## 3. Bảng lệnh kiểm tra thực tế

| Bước | Lệnh | Mã thoát | Dòng tổng kết nguyên văn pytest / Kết quả |
| --- | --- | --- | --- |
| 1 | python -c "probe in 6 sha256 hex" | 0 | In đủ 6 mã SHA-256 hex của 6 prompt mặc định ban đầu |
| 6 | python -m pytest tests/integration/prod_wiring/test_pw_d1_roles_prompts.py -q -p no:cacheprovider | 1 | 12 failed, 17 passed in 7.14s (RED đúng oracle: test 1 thiếu ref, test 2, test 3 cho 5 roles, test 4 và 5 assert article data items carry no ref member, test 6a thiếu PREVIOUS_DEFAULT_PROMPT_HASHES, 6b và 6c seed trả ()) |
| 13 | python -m pytest tests/integration/prod_wiring/test_pw_d1_roles_prompts.py -q -p no:cacheprovider | 0 | 29 passed in 6.90s (GREEN toàn bộ sau khi sửa production) |
| 14 | python -m pytest tests/integration/prod_wiring/test_pw_d1_roles_prompts.py tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider | 0 | 99 passed in 7.33s (GREEN toàn bộ test suite bắt buộc của task) |
| 15 | python -m pytest tests/integration/prod_wiring/test_pw_d2_context_selection.py -q -p no:cacheprovider | 0 | 16 passed in 9.90s (GREEN, không hồi quy PW-D2) |

## 4. Giả định và mục mở

1. GIẢ ĐỊNH (D8): Ref của các ứng viên trong asset_selection nằm trong payload mục dữ liệu đầu tiên (không có khoá ref như article), do đó prompt hướng dẫn mô hình tự dựng 4 trường reference object từ thông tin ứng viên thay vì chép từ khoá ref.
2. GIẢ ĐỊNH (D8): Hàm seed_default_prompts đọc bản cấu hình hiện hành thông qua _uow_factory và _config_scope_factory của ControlApiCommandService do service hiện chưa cung cấp API đọc công khai revision hiện tại của một scope; đây là điểm mở cần bổ sung API đọc công khai trong phân hệ controlplane ở slice riêng.
3. Prompt script_generation quy định trường language phải bằng language_policy trong khi _BOUNDARY yêu cầu mọi văn bản xuất ra bằng tiếng Anh; đây là điểm mở cần follow-up nếu hệ thống áp dụng chính sách ngôn ngữ khác tiếng Anh.
4. Gói công việc này sửa đổi trong owned paths và chưa gọi lại AI thật (việc gọi AI thật sẽ thực hiện tại slice kiểm thử CP7-4); cờ PRODUCTION_ACTIVATION_BLOCKED tiếp tục được giữ nguyên.

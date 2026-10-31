# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

Ngày kiểm: 31/10/2026, lane lane-cp7-10, bằng interpreter khoá của lane, HEAD gốc 4841435 (đã có `ensure_voice_staging`; commit của lượt này nằm ngay sau HEAD đó; bản này thêm chẩn đoán chỉ đọc `render_config`, kết quả các lần mở trước không còn dùng).

Lệnh pytest đã chạy: python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider (ngăn xếp thật, đúng một lần): 13 passed, 0 failed, 11 errors tại fixture batch_run, exit 1, 487,29 giây (pytest) / 488,5 giây (tường). Kiểm tĩnh bằng ast và `git diff --check` trước khi chạy: exit 0.

Trạng thái: 0/10 mục RG-09 PASS, 10/10 BLOCKED. Fixture batch_run lỗi vì job của lô 1 video kết thúc FAILED_FINAL ở stage align (activity CreateWordTiming, code word_coverage_incomplete); các stage analyze, script, media_select, plan, tts đã SUCCEEDED. Render chưa được chạy ở lượt này.

## Kết quả

RG-09.stages_succeeded: BLOCKED
RG-09.no_fake_adapters: BLOCKED
RG-09.qc_hard_gates: BLOCKED
RG-09.cloud_verified_before_count: BLOCKED
RG-09.cleanup_after_verify: BLOCKED
RG-09.plan_unchanged: BLOCKED
RG-09.resume_300s: BLOCKED
RG-09.no_rerun_completed: BLOCKED
RG-09.trace_complete: BLOCKED
RG-09.secret_scan: BLOCKED

## Chi tiết đo

- blocker: `BLOCKED: job kết thúc ở FAILED_FINAL stage=align status=FAILED_FINAL activity=CreateWordTiming code=word_coverage_incomplete field_errors={}; không thử lại, không tạo lô khác; render_config=[preset/bold-yellow=MISSING preset/output-profile=MISSING policy/quality=MISSING] job=FAILED_FINAL job_wait=None stages=[analyze#1=SUCCEEDED;script#1=SUCCEEDED;media_select#1=SUCCEEDED;plan#1=SUCCEEDED;tts#1=SUCCEEDED;align#1=FAILED_FINAL/word_coverage_incomplete] seed=[sources_registered=0 sources_replayed=0 sources_existing=7 hooks_imported=0 hooks_existing=10 assets_new=0 assets_existing=22 article_image_rights_status=UNVERIFIED]` (đã che bí mật; đuôi serve.log chỉ có log DEBUG của Kokoro về phoneme và độ dài âm thanh 25,90 giây).
- job hỏng được đếm trong phép đo: không thử lại, không có lô thứ hai (`session.post_batch(1)` gọi đúng một lần).
- khác lượt trước: lượt trước job dừng ở render (resolve_render_package, ACTIVITY_ABORTED); lượt này dừng sớm hơn ở align với word_coverage_incomplete, nên lượt này không đo được lại lỗi render. Lời văn TTS do AI sinh mỗi lần mỗi khác, nên lỗi align có thể không tái lập; nguyên nhân word_coverage_incomplete (CreateWordTiming không phủ đủ từ của kịch bản) chưa được chẩn đoán và thuộc production ngoài owned paths.
- staging_voice: driver tạo thư mục rỗng `<staging>/voice` trước khi tạo lô (OI-CP7-STAGING-VOICE); tts đã SUCCEEDED nên thư mục có mặt khi tts chạy. Giá trị 'created' hay 'existing' không đọc được vì fixture lỗi nên không ghi `trace.json`.
- seed_import: sources_existing=7, hooks_existing=10, assets_existing=22, article_image_rights_status=UNVERIFIED (seed có sẵn, không nhập mới).
- ready_seconds, ai_calls, spent_usd, drive_bytes, elapsed_s: không đo được từ fixture vì fixture không trả kết quả (không có dòng budget).
- unit: 13 test_unit_* thuần đạt (13 passed, 0 failed), gồm test_unit_format_render_config, test_unit_ensure_voice_staging, test_unit_no_batch_retry_loop và test_unit_format_failed_stage.

## Chẩn đoán render

Dòng đo thật: `render_config=[preset/bold-yellow=MISSING preset/output-profile=MISSING policy/quality=MISSING]`. Cả ba scope ConfigRevision mà render đòi PUBLISHED đều MISSING, nên production hiện không seed render config. Chuỗi mã (đọc từ mã, chưa tái hiện lại lượt này vì job không tới render):

- src/controlplane/api/wiring/render.py:379-380: `resolve_inputs` gọi `preset('bold-yellow')` và `output_profile()`;
- src/render/adapters/config_render_sources.py:271 ném `RenderConfigNotSeeded` (kế thừa LookupError ở dòng 30, không có `.code`);
- src/render/worker/activity_handler.py:418-421 đổi thành `ACTIVITY_ABORTED` không kèm field_errors, khớp với lỗi render của lượt trước (resolve_render_package, ACTIVITY_ABORTED, field_errors rỗng);
- `seed_render_config` (config_render_sources.py:213) chỉ được gọi từ tests/integration/prod_wiring/pw_e2e_support.py:942 và test, không có trong src hay tools; phần supplements (ass_style, layout, sections, quality_thresholds, output_profile) chỉ có ở tests/integration/prod_wiring/test_pw_f3_render_inputs.py:84-123.

Kết luận trung thực: bằng chứng đo được (ba scope MISSING) nhất quán với giả thuyết và là nguyên nhân gốc khả dĩ của lỗi render lượt trước, nhưng lượt này job hỏng ở align trước khi tới render nên chưa tái hiện trực tiếp ACTIVITY_ABORTED; ngay cả khi align được sửa, render sẽ vẫn hỏng chừng nào config chưa được seed.

## Open item

- OI-CP7-RENDER-CONFIG-SEED: cần gói production sở hữu wiring/launcher seed ConfigRevision preset/bold-yellow, preset/output-profile, policy/quality từ profile.json cộng supplements đã duyệt. CP7-10 không seed vì supplements là quyết định sản phẩm quyết định ngưỡng QC; seed từ hằng số test sẽ che lỗi production và làm mất ý nghĩa qc_hard_gates.
- OI-CP7-ALIGN-COVERAGE: stage align (CreateWordTiming) báo word_coverage_incomplete với field_errors rỗng ở lượt này; cần gói production chẩn đoán độ phủ từ của faster-whisper so với lời đọc Kokoro.
- OI-CP7-STAGING-VOICE: gói sở hữu `src/controlplane/api/wiring/voice.py` hoặc launcher nên tạo `staging/voice`; CP7-10 không sửa src.
- OI-PW-E2E-01: production chưa có writer chuyển lô CREATED→RUNNING nên final_batch_status chỉ là số đo, driver không UPDATE DB.

## Giới hạn trung thực

1. Không ghi PASS cho bất kỳ mục RG-09 nào vì job FAILED_FINAL; không hạ ngưỡng, không nâng trần 25 lời gọi AI hay 3 USD, không SQL ghi, không sửa src, không seed config, không dựng dữ liệu giả;
2. RG-09 chạy đúng một lô 1 video; job hỏng được đếm, không thử lại, không tạo lô khác; ngăn xếp thật không được chạy lần hai trong lượt này;
3. ba bản sửa production đã gộp (D-15-FIX1, PW-G2-FIX1, PW-G4-FIX1) có hiệu lực trên mã này;
4. chẩn đoán `render_config` là SELECT chỉ đọc (default_transaction_read_only=on) trên controlplane.cp_config_revisions;
5. interpreter khoá, không đọc Credentials/, không có capability, cookie, token hay file ID trong báo cáo.

## Chi phí

Không đo được từ fixture (không có dòng budget); lượt chạy 488,5 giây; không đọc Credentials/; không có bí mật.

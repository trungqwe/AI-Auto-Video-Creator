# Báo cáo PW-F3: Nguồn preset, output profile, QualityPolicy, tệp ASS kèm disclosure và hai port production

## 1. Mục tiêu và phạm vi

Nhiệm vụ PW-F3 thực hiện các thành phần adapter cho render pipeline trong phân hệ F, kết nối trực tiếp với cơ sở dữ liệu PostgreSQL của Control Plane và cấu hình của phân hệ J:
- Đọc `RenderPresetRevision`, `OutputProfile` và `QualityPolicy` từ `ConfigRevision` (các scope `preset` và `policy`) của phân hệ J, đồng thời hỗ trợ seed từ hồ sơ sản xuất (`profile.json`) khi chưa khởi tạo.
- Sinh tệp `.ass` từ `build_karaoke_plan` và `render_ass` (sử dụng từ và mốc thời gian từ aligner của phân hệ E), gắn kèm định dạng dải nhãn `Disclosure` và các sự kiện `Dialogue` cho các phân đoạn suy luận (`inference`, `creative_hypothesis`) theo đúng chuẩn CT-AI-004 và CT-QC-001.
- Hiện thực hai port sản xuất: `PostgresPlanAssets` (`PlanAssetPort`) và `PostgresArtifactInfo` (`ArtifactInfoPort`) đọc trực tiếp từ các bảng `cp_production_plans`, `cp_artifact_versions`, `cp_artifact_locations`.
- Cung cấp hàm `read_script_segments` đọc 5 trường của kịch bản (`segment_id`, `order`, `claim_mode`, `disclosure`, `word_count`) từ `cp_script_versions`.

Phạm vi 5 owned paths:
1. `src/render/adapters/config_render_sources.py`
2. `src/render/adapters/ass_manifest.py`
3. `src/render/adapters/postgres_plan_assets.py`
4. `tests/integration/prod_wiring/test_pw_f3_render_inputs.py`
5. `docs/delivery-evidence/pw-f3/report.md`

## 2. Tệp đã đổi

- `src/render/adapters/config_render_sources.py`:
  - `render_config_payloads`: biên dịch các thông số từ `ProductionProfile.parameters` và `supplements` thành danh sách payload có cấu trúc chuẩn cho output profile, các preset biến thể và policy kiểm tra chất lượng (QualityPolicy).
  - `seed_render_config`: ghi các payload vào `ConfigRevision` khi chưa có bản ghi (expected_revision=0), xử lý `RevisionConflictError` để đảm bảo tính bất biến (không ghi đè bản đã có).
  - `ConfigRenderSources`: cung cấp các phương thức `preset`, `output_profile`, `quality_policy` đọc bản ghi hiện hành (status `PUBLISHED`) qua `ConfigScopePort` để ghim `revision_ref` mới nhất mà không lưu bộ nhớ đệm (cache).
  - `ass_inputs`: trích xuất 4 mapping (`typography`, `safe_area`, `profile`, `disclosure_style`) từ preset và profile để cấp đầu vào cho việc tạo ASS.
- `src/render/adapters/ass_manifest.py`:
  - `disclosure_windows`: tính toán cửa sổ thời gian (`start_ms`, `end_ms`) cho từng segment suy luận bằng cách cộng dồn `word_count` theo `order` trên danh sách từ của aligner; từ chối khi thiếu disclosure hoặc lệch tổng số từ.
  - `build_ass_text`: sinh chuỗi văn bản ASS từ karaoke plan, chèn style `Disclosure` ở cuối mục styles và các dòng `Dialogue` ở cuối danh sách events (với tên segment_id tương ứng).
  - `build_ass_material`: xuất tệp ASS ra đĩa tại đường dẫn staging root dưới dạng `<sha256>.ass` (content-addressed) và trả đối tượng `AssMaterial`.
  - `with_ass_entry`: chèn mục ASS vào `materialization_manifest` và kiểm tra xung đột trùng lặp khóa.
- `src/render/adapters/postgres_plan_assets.py`:
  - `PostgresPlanAssets`: đọc bảng `cp_production_plans` qua `borrow_connection()`, trả tập hợp các ref tài sản (`artifact_version_ref`) được plan cho phép (gồm visuals, visual hook, audio hook, thumbnail và allowed fallbacks).
  - `PostgresArtifactInfo`: đọc bảng `cp_artifact_versions` và xác minh tài sản chỉ được công nhận khi có location trạng thái `VERIFIED` với `observed_hash` khớp `sha256_hash`.
  - `read_script_segments`: đọc các phân đoạn từ `cp_script_versions`, xác thực đầy đủ 5 trường theo quy chuẩn và sắp xếp theo `order` tăng dần.
- `tests/integration/prod_wiring/test_pw_f3_render_inputs.py`:
  - Bộ 35 test tích hợp chạy trên PostgreSQL 18.6 thật, kiểm tra toàn bộ luồng ghim revision, seed, port production, sinh tệp ASS và chèn dải nhãn disclosure.
- `docs/delivery-evidence/pw-f3/report.md`:
  - Báo cáo bằng chứng nghiệm thu PW-F3.

## 3. Quyết định mặc định D8 cùng lý do

- `scope_key 'output-profile'` và `'quality'`: Dùng làm định danh phạm vi cấu hình trong ConfigRevision cho output profile (scope_kind `preset`) và QualityPolicy (scope_kind `policy`) để không trùng lặp với tên các biến thể preset (`bold-yellow`, `clean-white`, ...).
- `preset_revision_ref` và `output_profile_revision` là `config_revision_id`: Lưu chuỗi UUID định danh bản ghi cấu hình đã ghim nhằm bảo đảm tính tái lập chính xác cho các lượt render sau này.
- `RenderPresetRevision.revision = config_revision_number`: Số phiên bản của preset revision lấy trực tiếp từ số thứ tự tăng dần của ConfigRevision, không cần lưu dư thừa trong trường payload.
- Asset chỉ được coi là "biết" khi có ít nhất một location trạng thái `VERIFIED` và `observed_hash` khớp `sha256_hash`: Đảm bảo quy tắc an toàn dữ liệu, ngăn chặn việc đưa tài sản hỏng (`CORRUPT`), thiếu (`MISSING`) hoặc sai lệch nội dung vào render.
- Tập tài sản cho phép của production plan: Bao gồm `artifact_version_ref` trong các visual của timeline, 3 tham chiếu hook (`visual_hook_ref`, `audio_hook_ref`, `thumbnail_ref`) và các `replacement_artifact_version_ref` trong `allowed_fallbacks`.
- Định dạng ASS trong manifest: Sử dụng khóa `ass-<sha256>` và `local_ref` dạng `<sha256>.ass` (đúng điều kiện đuôi `.ass` cho `build_render_command` và khớp regex định danh).
- Quy chuẩn dải nhãn Disclosure (CT-AI-004): Chỉ thêm dòng style `Disclosure` và sự kiện `Dialogue` khi script có phân đoạn suy luận (`inference` hoặc `creative_hypothesis`). Nếu kịch bản thuần túy `source_backed`, ASS không chứa bất kỳ style hay sự kiện Disclosure nào.
- Quy chuẩn định vị style Disclosure: Alignment và margin_v của Disclosure được kiểm tra để không trùng lặp với Karaoke (tránh đè chữ) và `margin_v` phải nhỏ hơn chiều cao khung hình `play_res_y`.

## 4. GIẢ ĐỊNH và mục mở

- `OI-PW-F3-01`: Hồ sơ production hiện tại (`profile.json`) chưa khai báo các giá trị bổ trợ cho ASS (`ass_style`, `layout`, `sections`, `quality_thresholds`, `output_profile`). Adapter nhận các giá trị này qua tham số `supplements` và ném `RenderConfigMissing` nếu thiếu. Control cần bổ sung chính thức vào hồ sơ cấu hình hoặc cung cấp trong wiring PW-F4.
- `OI-PW-F3-02`: Chưa có hàm đọc word timing trực tiếp từ bảng `cp_word_timings` theo `word_timing_ref` trong adapter render; luồng đọc timing hoàn chỉnh sẽ được liên kết trong slice PW-F4.
- `OI-PW-F3-03`: Ngưỡng `min_continuity` trong `VISUAL_CONTINUITY` đã được lưu trữ trong chính sách nhưng chưa có module tính toán liên tục thị giác ở phía render adapter; tính năng này thuộc về bộ đo kiểm chất lượng đầu ra.
- Ghi nhận hệ thống: Bảng `cp_artifact_locations` không có trigger chặn INSERT trực tiếp trạng thái `VERIFIED`; đường dẫn `tmp_path` trên Windows đáp ứng đầy đủ tập ký tự an toàn `_FILTER_PATH_CHARS` của lệnh `build_render_command`.

## 5. Bảng lệnh đã chạy

| Lệnh thực thi | Exit Code | Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | Không có lỗi khoảng trắng thừa hay định dạng dòng cuối |
| `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 22 passed, 125 subtests passed in 0.37s |
| `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8').lower() for p in ['src/render/adapters/config_render_sources.py', 'src/render/adapters/ass_manifest.py', 'src/render/adapters/postgres_plan_assets.py']); assert 'fake' not in t and 'memory' not in t and 'from src.' not in t, 'PW-F3'"` | 0 | Không chứa chuỗi cấm (fake, memory, from src.) |
| `python -c "import ast, pathlib; d = ast.get_docstring(ast.parse(pathlib.Path('tests/integration/prod_wiring/test_pw_f3_render_inputs.py').read_text(encoding='utf-8'))); line = [x for x in d.splitlines() if x.startswith('coveredIds:')][0]; ids = [x.strip() for x in line[len('coveredIds:'):].split(',')]; assert {'PW-F3-01', 'CT-QC-001', 'CT-REN-001', 'CT-AI-004'} <= set(ids), ids"` | 0 | Khai báo đủ 4 mã coveredIds |
| `python -m pytest tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 57 passed, 125 subtests passed in 14.50s |

## 6. Bảng ánh xạ coveredIds sang test thật

| coveredId | Test cases phủ mã |
| --- | --- |
| `PW-F3-01` | `test_seed_writes_output_profile_presets_and_policy_once`, `test_seeded_values_come_from_the_profile`, `test_missing_inputs_name_the_parameter_and_write_nothing`, `test_unseeded_sources_raise_not_seeded`, `test_ass_colour_converts_and_rejects`, `test_no_values_are_constants_in_the_adapter`, `test_new_preset_revision_is_pinned_by_the_next_render`, `test_new_output_profile_revision_is_pinned`, `test_new_quality_policy_revision_is_pinned`, `test_seed_does_not_overwrite_an_edited_revision`, `test_edited_preset_changes_the_ass_style` |
| `CT-REN-001` | `test_ports_satisfy_the_render_protocols`, `test_plan_asset_port_returns_the_set_the_plan_allows`, `test_asset_outside_the_plan_is_rejected_by_resolve`, `test_artifact_info_returns_facts_and_none_when_unknown`, `test_ports_read_the_tables_not_a_cache`, `test_ass_has_karaoke_events_for_every_word_and_is_written_to_staging`, `test_ass_enters_the_manifest_and_build_render_command_accepts_it`, `test_manifest_without_the_ass_entry_is_rejected`, `test_ass_material_is_content_addressed_and_idempotent`, `test_invalid_staging_root_is_rejected` |
| `CT-QC-001` | `test_seeded_values_come_from_the_profile`, `test_new_quality_policy_revision_is_pinned`, `test_disclosure_style_must_not_overlap_karaoke` |
| `CT-AI-004` | `test_read_script_segments_returns_the_five_fields_sorted_by_order`, `test_read_script_segments_unknown_script_has_a_code`, `test_read_script_segments_rejects_invalid_payload`, `test_read_script_segments_is_scoped_to_the_workspace`, `test_inference_segment_adds_a_disclosure_dialogue_in_the_exact_window`, `test_creative_hypothesis_segment_also_gets_a_disclosure_row`, `test_windows_accumulate_word_count_per_order_and_do_not_drift`, `test_inference_without_disclosure_is_rejected_and_nothing_is_written`, `test_word_count_mismatch_is_rejected_and_nothing_is_written`, `test_source_backed_only_script_has_no_disclosure_row`, `test_disclosure_text_cannot_inject_ass_markup`, `test_unordered_input_gives_the_same_ass` |

## 7. Dòng test đã đổi theo số đo thật

- Helper `insert_timing` trong tệp test: Bổ sung mệnh đề `ON CONFLICT (workspace_id, record_key, revision) DO NOTHING` để cho phép gọi `material()` nhiều lần trên cùng một database tạm mà không gặp lỗi trùng khóa chính `cp_word_timings_pkey`.
- Bổ sung `AssMaterial` vào câu lệnh import của `tests/integration/prod_wiring/test_pw_f3_render_inputs.py`.
- Kết quả kiểm thử: Toàn bộ 57 test đạt hoàn toàn (35 integration test trên PostgreSQL 18.6 thật + 22 unit test layout với 125 subtests).

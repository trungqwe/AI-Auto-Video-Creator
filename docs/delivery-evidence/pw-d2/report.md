# Báo cáo thực hiện gói PW-D2: ngữ cảnh cho mô hình, lưu selection và ActivityInputPort D

## 1. Phạm vi
Liệt kê tám tệp thuộc owned paths của gói PW-D2:
- `src/creative/adapters/article_context.py`: tạo mới (PostgresArticleContext đọc cp_articles và cp_article_revisions).
- `src/creative/adapters/postgres_selection.py`: tạo mới (PostgresSelectionStore lưu và đọc cp_creative_selections, content_sha256).
- `src/creative/adapters/activity_inputs.py`: tạo mới (ProductionActivityInputs với 8 builder, handle_creative_activity, selected_media_refs).
- `src/creative/application/pipeline.py`: sửa (thêm ArticleContextPort, SelectionStorePort, nối ngữ cảnh và kết quả stage trước vào PromptEnvelope.data).
- `tests/integration/prod_wiring/test_pw_d2_context_selection.py`: tạo mới (test tích hợp PostgreSQL thật cho ngữ cảnh, kho selection và ActivityInputPort D).
- `tests/integration/creative/test_d14_creative_pipeline.py`: giữ nguyên không đổi dòng nào.
- `tests/integration/creative/test_d16_worker_activity.py`: giữ nguyên không đổi dòng nào.
- `docs/delivery-evidence/pw-d2/report.md`: tạo mới (báo cáo thực hiện và bằng chứng nghiệm thu).

## 2. Thiết kế
- (a) ArticleContextPort/PostgresArticleContext đọc cp_articles và cp_article_revisions theo source_refs của snapshot, đưa vào khối dữ liệu cho vai trò phân tích, góc kể, script;
- (b) _invoke nhận prior, kết quả stage trước vào khối dữ liệu, instructions không đổi;
- (c) PostgresSelectionStore lưu cp_creative_selections, idempotent theo job và nội dung, content_sha256, kiểm khi đọc; BuildProductionPlan nhận selection_ref và đọc từ bảng;
- (d) ProductionActivityInputs với id sinh theo job và revision stage, ValidateVariant lấy pha từ stage (plan->plan, qc->output, stage khác bị từ chối);
- (e) handle_creative_activity trả một selected_media cho mỗi ảnh.

## 3. Dòng đã đổi trong test đã nghiệm thu
Không đổi dòng nào trong test_d14_creative_pipeline.py và test_d16_worker_activity.py; khoá phản hồi và calls_by_role của PW-D1 giữ nguyên.

## 4. Lệnh đã chạy

| Bước | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 16 | `python -m pytest tests/integration/prod_wiring/test_pw_d2_context_selection.py -q -p no:cacheprovider` | 1 | RED: 9 failed, 4 passed |
| 23 | `python -m pytest tests/integration/prod_wiring/test_pw_d2_context_selection.py -q -p no:cacheprovider` | 1 | RED: 3 failed, 10 passed |
| 28 | `python -m pytest tests/integration/prod_wiring/test_pw_d2_context_selection.py -q -p no:cacheprovider` | 0 | GREEN: 13 passed in 6.64s |
| 29 | `python -m pytest tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | GREEN: 82 passed, 58 subtests passed in 0.47s |
| 31 | `git diff --check` | 0 | Sạch khoảng trắng thừa |
| 32 | `python -m pytest tests/integration/prod_wiring/test_pw_d2_context_selection.py tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | GREEN: 95 passed, 58 subtests passed in 5.73s |
| 33 | Probe cp_creative_selections trong postgres_selection.py | 0 | PASS |
| 34 | Probe coveredIds và báo cáo tiếng Việt có dấu | 0 | PASS |

## 5. Bằng chứng RED
Tên test đỏ và lỗi đầu tiên của từng test ở bước 16:
1. `test_model_calls_carry_article_text_and_earlier_results_in_the_data_block_only`: `TypeError: selection must be a CreativeAssetSelection` tại `src/creative/application/pipeline.py:533`.
2. `test_a_missing_article_revision_is_refused_before_any_route_or_ai_call`: `creative.domain.analysis.AnalysisRejected: hallucinated_ref: facts[0].evidence_refs[0] (revision_mismatch)` tại `src/creative/domain/analysis.py:194`.
3. `test_selection_is_stored_in_the_table_and_survives_a_rebuilt_store`: `AssertionError: assert [] == [('selection:...', 1)]` tại `tests/integration/prod_wiring/test_pw_d2_context_selection.py:184`.
4. `test_plan_reads_the_selection_from_the_table_by_ref`: `TypeError: selection must be a CreativeAssetSelection` tại `src/creative/application/pipeline.py:533`.
5. `test_same_content_keeps_one_revision_and_new_content_adds_the_next`: `AssertionError: assert [] == [1]` tại `tests/integration/prod_wiring/test_pw_d2_context_selection.py:212`.
6. `test_a_tampered_row_is_rejected_on_load`: `Failed: DID NOT RAISE SelectionIntegrityError` tại `tests/integration/prod_wiring/test_pw_d2_context_selection.py:228`.
7. `test_input_port_resolves_every_activity_and_validate_variant_follows_its_stage`: `AssertionError: assert ['failed', ...] == ['succeeded', ...]` tại `tests/integration/prod_wiring/test_pw_d2_context_selection.py:311`.
8. `test_a_retry_after_a_restart_replays_the_snapshot_receipt_with_the_same_arguments`: `KeyError: 'metrics'` tại `tests/integration/prod_wiring/test_pw_d2_context_selection.py:327`.
9. `test_validate_variant_outside_plan_and_qc_is_rejected_instead_of_defaulting_a_phase`: `AssertionError: assert 'failed' == 'succeeded'` tại `tests/integration/prod_wiring/test_pw_d2_context_selection.py:334`.

## 6. coveredIds
- PW-D2-01 -> các test ngữ cảnh, kho selection, Flow.
- CT-AI-008 -> test ValidateVariant theo pha và test từ chối stage lạ.
- CT-AI-009 -> GenerateOutputMetadata trong test Flow và test metadata nhận kết quả kế hoạch.

## 7. GIẢ ĐỊNH và mục mở
- GIẢ ĐỊNH góc dùng cho script, selection, variant là góc đầu của bộ.
- GIẢ ĐỊNH metadata_revision bằng revision của stage_run_id.
- Mục mở:
  1. handle_creative_activity phải được composition root dùng thay handle_activity (activity_handler.py không thuộc owned paths nên _ROUTES không đổi);
  2. SelectionInputsPort do PW-D3 hiện thực;
  3. VariantContextPort (completed, active_reservations, same_run, registry_revision, output_hash) cần hiện thực từ dữ liệu của G ở slice nối composition;
  4. SourceSetPort và PromptRefsPort do composition cung cấp (ConfigPromptSource đã khớp PromptRefsPort).
- Giữ PRODUCTION_ACTIVATION_BLOCKED.

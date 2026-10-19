# Báo cáo bằng chứng D-14

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: bb8fe184f25fbe36ed0bdefa1bbffb162c1d4634
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-14 trong docs/implementation/d/slices.md, ủy quyền AI_SETUP.

## RED

- Lệnh thực thi: python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider (chạy với khung stub, tám command ném NotImplementedError)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 15 failed, 3 passed in 0.63s
- Test FAILED tiêu biểu:
  - FAILED tests/integration/creative/test_d14_creative_pipeline.py::test_every_command_is_one_unit_of_work_with_receipt_and_outbox_event: NotImplementedError: D-14 RED skeleton
  - FAILED tests/integration/creative/test_d14_creative_pipeline.py::test_generate_script_without_committed_snapshot_is_refused_with_zero_ai_calls: NotImplementedError: D-14 RED skeleton
  - FAILED tests/integration/creative/test_d14_creative_pipeline.py::test_same_key_and_payload_returns_old_receipt_without_second_script: NotImplementedError: D-14 RED skeleton
- Xác nhận: không có ImportError, ModuleNotFoundError hay lỗi collection; các test tĩnh (docstring, chặn mạng, ranh giới nguồn) đã PASS, mọi test gọi command thất bại do khung NotImplementedError.

## GREEN

- Lệnh thực thi: python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider (sau khi cài đặt đủ tám command)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 18 passed in 0.13s

## Thay đổi

- src/creative/application/pipeline.py: CreativePipeline với tám command (BuildProductionSnapshot, AnalyzeContent, GenerateStoryAngles, GenerateScript, SelectCreativeAssets, BuildProductionPlan, ValidateVariant, GenerateOutputMetadata); mỗi command một UoW: kiểm receipt (replay hoặc IdempotencyConflict theo request_hash), tạo output, ghi AIInvocationRecord (nếu gọi AI), ghi receipt, ghi outbox event qua uow.outbox, rồi commit; lỗi bất kỳ rollback toàn bộ. OutputTrace gắn snapshot, model, prompt, config và input revision vào mọi kết quả.
- tests/integration/creative/test_d14_creative_pipeline.py: test tích hợp in-process với FakeProviderRoute/FakeAIAdapter/InMemoryUnitOfWork, chặn socket.create_connection và socket.getaddrinfo.
- docs/delivery-evidence/d-14/report.md: báo cáo này.

## Ánh xạ phản ví dụ -> test

- Gọi AI trước khi commit snapshot: test_generate_script_without_committed_snapshot_is_refused_with_zero_ai_calls, test_ai_commands_without_committed_snapshot_never_reach_the_ai, test_refused_timeline_snapshot_is_never_committed_and_script_is_refused.
- Config/source mới làm đổi job cũ: test_config_and_source_change_after_snapshot_keeps_old_job_refs_and_new_job_gets_new_revisions.
- Outbox ghi ngoài UoW: test_outbox_failure_rolls_back_output_record_receipt_and_outbox_together, test_pipeline_source_has_no_adapter_clock_network_import_and_outbox_only_through_uow.
- Output thiếu prompt revision: test_every_output_carries_snapshot_model_prompt_config_and_input_revision, test_missing_prompt_revision_in_snapshot_is_refused_before_any_ai_call.
- Gửi lặp tạo script thứ hai: test_same_key_and_payload_returns_old_receipt_without_second_script, test_same_key_with_different_payload_is_an_idempotency_conflict_on_request_hash, test_new_key_for_same_script_id_does_not_create_a_second_script.
- from_then_to_now qua D-07: test_from_then_to_now_goes_through_d07_and_other_modes_do_not_need_the_policy.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider | 0 | 18 passed in 0.13s |
| 2 | git diff --check | 0 | PASS |

## Quyết định mặc định (D8)

1. Mỗi command là một phương thức của CreativePipeline; thứ tự trong UoW: tra receipt, chạy work (output, AIInvocationRecord), ghi receipt, ghi outbox, commit; mọi lỗi rollback tất cả (kể cả AIInvocationRecord; ghi nhận lỗi provider thuộc D-15).
2. request_hash = request_hash({workspace_id, command_name, payload}) với payload là tham số lệnh dạng JSON thuần (không gồm EventContext); cùng khoá và hash trả receipt cũ (replayed=True, không gọi AI, không ghi gì), khác hash ném IdempotencyConflict (IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD).
3. GIẢ ĐỊNH: prompt revision của từng ai_role được ghim trong configuration_revision_refs của snapshot (ref_type prompt, ref_id là ai_role) vì CT-CFG-002 chưa có binding (CONV-D-07); thiếu thì INPUT_NOT_READY trước khi gọi route hoặc AI.
4. Mọi command sau BuildProductionSnapshot kiểm snapshot đã commit (và analysis, angle, script cần thiết) trước khi gọi route và AI.
5. OutputTrace: snapshot_ref, config_revision (configuration_bundle_fingerprint của snapshot), input_revision (source_set_fingerprint của snapshot), model_ref, prompt_revision, invocation_key lấy từ AIInvocationRecord; invocation_key là workspace_id:idempotency_key, revision 1.
6. SelectCreativeAssets: D-13 chưa có repository cho CreativeAssetSelection nên UoW chỉ lưu AIInvocationRecord và receipt (aggregate_ref selection:<selection_fingerprint>) và trả selection qua CommandResult.output; AnalyzeContent và SelectCreativeAssets không phát event vì không thuộc 6 event đã định.
7. ValidateVariant lưu cả kết quả invalid cùng receipt, chỉ phát VariantValidated khi valid; revision là số lần kiểm của variant_ref.
8. Dữ liệu gửi AI chỉ mang ref và revision (không nội dung bài); nạp nội dung bài và wiring composition root thuộc CONV-D-02. job_ref gửi route là video_job_ref của snapshot, nếu thiếu thì snapshot_id.
9. from_then_to_now đi qua authorize_timeline_narrative (D-07) trong cùng UoW; thiếu TimelinePolicy thì INPUT_NOT_READY; bị từ chối thì không commit snapshot, receipt hay event.

## coveredIds

- TST-INT-INV-004, TST-INT-INV-005 (phía D), acceptance §12 mục 1 và 7

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt
- Mục mở: kho CreativeAssetSelection và persistence PostgreSQL (CONV-D-01), wiring route thật (CONV-D-02), đăng ký 6 event vào catalog (CONV-D-10)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture, mã controlplane hay mã domain/ports/adapters của D.
- Chỉ dùng stdlib, controlplane domain và gói creative; không gọi dịch vụ thật, không mạng.

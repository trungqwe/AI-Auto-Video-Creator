# Báo cáo bằng chứng F-19

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 3f728636bf16a824120ce1327ffd8ce3326dfebd
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-19 trong docs/implementation/f/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider (trên stub trung tính: ném NotImplementedError STUB-F19-INSPECT và STUB-F19-PREPARE)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 27 failed, 8 passed in 0.90s
- Các dòng FAILED tiêu biểu:
  - FAILED tests/integration/render/test_f19_inspect_output_pipeline.py::test_passing_output_stores_report_receipt_trace_and_event_in_one_unit_of_work
  - FAILED tests/integration/render/test_f19_inspect_output_pipeline.py::test_duration_boundaries_are_inclusive_and_the_event_follows_the_verdict[60999-False]
  - FAILED tests/integration/render/test_f19_inspect_output_pipeline.py::test_qc_pass_gives_video_output_but_not_completion_when_upload_is_not_verified
- Xác nhận: không có ImportError hay lỗi collection; RED hợp lệ do hành vi chưa có ở stub trung tính.

## GREEN

- Lệnh thực thi: python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 35 passed in 0.24s

## Thay đổi

- src/render/application/inspect_output.py: OutputPipeline với InspectOutput và PrepareOutputReady, quản lý grant, replay idempotency, điều phối probe F-13 và inspector F-14, dựng QualityReport F-12, lưu report, receipt, trace và event outbox OutputQualityChecked trong một UoW duy nhất, đánh giá verdict output ready theo F-15.
- tests/integration/render/test_f19_inspect_output_pipeline.py: 35 ca kiểm thử integration bao quát toàn bộ kịch bản pass/fail gate kỹ thuật và nội dung, biên thời lượng, warning gate, disclosure, idempotency replay/conflict, stale grant, UoW atomic commit/rollback, ready/completion derivation và ast checks.
- docs/delivery-evidence/f-19/report.md: Báo cáo bằng chứng thực thi này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider | 0 | 35 passed in 0.24s |
| 2 | python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider | 0 | 28 passed in 0.16s |
| 3 | python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider | 0 | 36 passed in 0.16s |
| 4 | python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider | 0 | 12 passed, 75 subtests passed in 0.21s |
| 5 | probe không còn marker STUB-F19 | 0 | PASS (không có output, không còn marker STUB-F19) |
| 6 | probe tiếng Việt của report.md | 0 | PASS (UTF-8 không BOM, tiếng Việt đầy đủ dấu, không ký tự thay thế) |
| 7 | git diff --check | 0 | PASS (không có output, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. QualityPolicy ánh xạ sang F-13: DURATION_RANGE.duration_range_ms, VOICE_AUDIBLE.min_voice_level, OUTPUT_PROFILE_VALID là expected_profile; ngưỡng thiếu thì giữ nguyên missing để gate rơi vào trạng thái not_evaluated.
2. Báo cáo lưu bằng KIND_QUALITY_REPORT khoá theo render_attempt_id, mỗi kết quả khác là revision mới, báo cáo giống hệt bản mới nhất không lưu hai lần, event OutputQualityChecked có aggregate_id là report_id và aggregate_revision là revision đó nên dedup đúng.
3. Event phát cả khi pass và fail, cùng UoW với report, receipt, trace; đảm bảo downstream nhận được trạng thái QC dù thành công hay thất bại.
4. F không có evaluator cho gate warning nên warning_results do caller đưa và chỉ nhận gate WARNING; không có kết quả thì NOT_EVALUATED INPUT_NOT_READY và không ảnh hưởng passed.
5. INFERENCE_DISCLOSURE_PRESENT được đánh dấu not_applicable chỉ khi F-14 trả not_applicable (khi không có segment suy luận).
6. PrepareOutputReady dùng F-15, refs_committed True vì attempt và báo cáo hiện hành vừa đọc từ kho trong cùng UoW, grant_valid hỏi lại G; verdict không ready là kết quả đã lưu (receipt kèm verdict), không phải lỗi lệnh.
7. VideoOutput không có record kind trong repositories.py (ngoài owned paths) nên nằm trong OutputReadyReceipt và trả cho G; video_output_id, expected_sha256, upload_verified, completion_committed là đầu vào.
8. Một UoW bao cả lúc gọi port đọc-only (probe, inspector), lỗi port thì rollback và không ghi gì; PostgreSQL chờ CONV-F-01.
9. _digest và _plain import từ package_pipeline để dùng chung quy tắc request_hash và canonicalization.

## Ánh xạ phản ví dụ

- QC fail vẫn tạo output ready: test_render_succeeded_but_qc_failed_creates_no_video_output
- QC pass tính là completion: test_qc_pass_gives_video_output_but_not_completion_when_upload_is_not_verified
- Phát event chỉ khi pass: test_one_failing_hard_gate_fails_the_report_and_the_event_is_still_emitted
- Ghi report ngoài UoW: test_failure_inside_the_unit_of_work_rolls_back_report_receipt_trace_and_event và test_passing_output_stores_report_receipt_trace_and_event_in_one_unit_of_work
- Xoá local khi upload chưa verify: test_qc_pass_gives_video_output_but_not_completion_when_upload_is_not_verified và test_module_has_no_delete_or_file_removal_api

## coveredIds

- CT-QC-001, CT-RND-005, TST-E2E-INV-009, TST-QC-INV-019, TST-E2E-001 (đoạn QC).

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10.
- User checkpoint M2 (P8/P9) chưa ghi là đã duyệt.

## Giới hạn

- Không chạy full suite, không chạy tests/m1 hay tests/m2.
- Không sửa tệp ngoài owned paths; không gọi dịch vụ thật; probe và inspector thật chờ CP7-F-01 và CP7-F-02.

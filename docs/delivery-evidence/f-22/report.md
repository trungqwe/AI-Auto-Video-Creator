# Báo cáo bằng chứng F-22

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: integration head e6d42ba2e1d55065b51625f83f6e35c85f02c370 (sau rebase; trước đó 750929c603db3ca6c05ddc8dc127d08187e293b5)
- Nguồn quyền: IMPL-PLAN-F Auditor PASS và slice F-22 trong docs/implementation/f/slices.md

## Bảng mã test ID → tệp test

| Mã | Tệp có trong coveredIds | Ghi chú |
|---|---|---|
| CT-RND-001 | F-02 | Khớp catalog |
| CT-RND-002 | F-03, F-04, F-05, F-17 | Khớp catalog |
| CT-RND-003 | F-06, F-07, F-08, F-17 | Khớp catalog |
| CT-RND-004 | F-10, F-11, F-18, F-21 | Khớp catalog |
| CT-RND-005 | F-15, F-19 | Khớp catalog |
| CT-RND-006 | F-07 | Khớp catalog |
| CT-QC-001 | F-12, F-13, F-14, F-19, F-21 | Khớp catalog |
| CT-QC-002 | F-12, F-14 | Khớp catalog |
| TST-MEDIA-INV-007 | F-06, F-17 | Khớp catalog |
| TST-INT-INV-008 | F-07, F-08, F-17 | Khớp catalog |
| TST-E2E-INV-009 | F-15, F-19 | Khớp catalog |
| TST-SEC-INV-012 | F-10, F-11, F-16, F-18 | Khớp catalog |
| TST-QC-INV-019 | F-07, F-14, F-19 | Khớp catalog |
| TST-SEC-INV-020 | F-03, F-07, F-10 | Khớp catalog |
| TST-E2E-001 | F-17, F-18, F-19, F-21 | Khớp catalog |
| TST-E2E-014 | F-20 | Khớp catalog |
| TST-CTR-INV-001 | F-17, F-18 | Khớp catalog |
| TST-CTR-INV-002 | F-16 | Khớp catalog (đã bổ sung bởi F-16-FIX1, gộp vào nhánh tích hợp) |
| TST-WF-INV-003 | F-20 | Khớp catalog (đã bổ sung bởi F-20-FIX1, gộp vào nhánh tích hợp) |

Cả 13 tên gate CT-QC-001 xuất hiện trong test_f12_quality_report.py, test_f13_technical_gates.py, test_f14_content_gates.py (xác nhận bởi test_every_qc_gate_name_appears_in_f12_f13_or_f14_tests); không tệp test_f nào dùng tiền tố TST-MED-, TST-VOI-, TST-RND-, TST-EF-.

## Ánh xạ acceptance §8 (docs/09-contracts/08-render-quality-contracts.md)

| Mục | Nội dung | Slice | Test |
|---|---|---|---|
| 1 | Đổi bất kỳ input hash thì fingerprint đổi | F-04 | test_f04_package_fingerprint.py: test_changing_any_hashed_field_changes_fingerprint, test_changing_input_artifact_field_changes_fingerprint. |
| 2 | Render thành công nhưng QC fail không tạo video hoàn thành | F-15, F-19 | test_f15_output_ready.py: test_qc_fail_never_creates_a_video_output, test_render_success_with_qc_fail_is_not_ready_and_not_complete; test_f19_inspect_output_pipeline.py: test_render_succeeded_but_qc_failed_creates_no_video_output. |
| 3 | QC xác minh visual hook, audio hook, thumbnail trong vùng hook | F-06, F-14 | test_f06_preconditions_hooks_timeline.py: test_visual_hook_missing, test_audio_hook_missing, test_thumbnail_missing, test_thumbnail_range_is_inside_hook_range_not_fixed_three_seconds; test_f14_content_gates.py: VisualHookTests, AudioHookTests, ThumbnailTests (test_outside_hook_range_fails). |
| 4 | Subtitle burn-in và timing từng từ | F-09, F-14 | test_f09_karaoke_plan.py: test_sum_of_k_tags_equals_dialogue_duration_for_irregular_marks; test_f14_content_gates.py: SubtitleTests, KaraokeTests. |
| 5 | Output ngoài 61-70 giây hard fail | F-13, F-19 | test_f13_technical_gates.py: DurationRangeTests, test_too_long_video_fails_only_the_duration_gate; test_f19_inspect_output_pipeline.py: test_duration_boundaries_are_inclusive_and_the_event_follows_the_verdict. |
| 6 | F không tự đổi script, góc kể hay asset ngoài fallback | F-05, F-17 | test_f05_resolve_package.py: test_asset_outside_plan_and_fallbacks_is_rejected, test_fallback_with_artifact_id_allows_that_asset_but_plain_fallback_does_not; test_f17_resolve_validate_pipeline.py: test_changed_script_fingerprint_or_voice_hash_after_the_package_fails_validation. |
| 7 | Thiếu hoặc lệch revision bằng chứng tiếng Anh là hard fail | F-07, F-14 | test_f07_preconditions_artifacts_language.py: test_stale_revision_is_mismatch, test_self_declared_language_is_not_evidence; test_f14_content_gates.py: EnglishOutputTests (test_stale_revision_fails). |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cacheprovider | 0 | 55 passed in 0.15s |
| 2 | git diff --check | 0 | Đạt, không có lỗi định dạng whitespace |

## Khoảng trống

Không còn khoảng trống. GAP-F22-1 và GAP-F22-2 trước đây đã được đóng bởi F-16-FIX1 (tests/unit/render/test_f16_ports_memory_events.py) và F-20-FIX1 (tests/integration/render/test_f20_worker_activity.py), đã gộp vào nhánh tích hợp e6d42ba2e1d55065b51625f83f6e35c85f02c370; F-22 không sửa tệp nào ngoài owned paths.

## coveredIds

acceptance §8 mục 1 đến 7 của contract 08.

## Giới hạn

không chạy full suite, không sửa src, binding, fixture, pyproject.toml hay uv.lock; không gọi dịch vụ thật.

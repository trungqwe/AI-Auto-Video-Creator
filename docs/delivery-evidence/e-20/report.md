# Báo cáo bằng chứng E-20

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: ace870b20f86bf842f4c36566c30c98af9e05ae7
- Nguồn quyền: IMPL-PLAN-E Auditor PASS và slice E-20 trong docs/implementation/e/slices.md.

## Cách kiểm

- Test chỉ dùng thư viện chuẩn Python (stdlib) gồm `ast`, `pathlib`, `re` kết hợp `pytest`.
- Đọc docstring dòng `coveredIds` của các tệp `tests/unit/voice/test_e*.py` và `tests/integration/voice/test_e*.py` (loại trừ chính tệp E-20 `test_e20_coverage_catalog.py`).
- Khẳng định 18 mã bắt buộc phải nằm trong ít nhất một tệp có chứa hàm `test_`.
- Không tệp nào được phép dùng tiền tố cấm `TST-VOI-`, `TST-MED-`, `TST-RND-`, `TST-EF-`.

## Bảng ánh xạ mã bắt buộc

Mỗi mã trong 18 mã bắt buộc kèm tệp khai báo thực tế được đọc từ dòng `coveredIds` trong docstring sau khi rebase lên baseline `ace870b20f86bf842f4c36566c30c98af9e05ae7`:

1. `TST-MEDIA-INV-007`:
   - `tests/integration/voice/test_e16_voice_timing_pipeline.py` (docstring: `coveredIds: CT-TTS-001, CT-SUB-001, CT-RND-002, TST-MEDIA-INV-007 (phía E), TST-E2E-001 (đoạn voice và timing, phía E)`)
   - `tests/unit/voice/test_e11_timing_binding.py` (docstring: `coveredIds: TST-MEDIA-INV-007 (mức domain), CT-SUB-001 bất biến 2 và 3`)
2. `TST-INT-INV-008`:
   - `tests/unit/voice/test_e02_processing_contract.py` (docstring: `coveredIds: CT-PROC-001, CT-PROC-002, CT-PROC-008, TST-INT-INV-008 (domain level)`)
   - `tests/unit/voice/test_e15_ports_memory.py` (docstring: `coveredIds: CT-EVT-002, CT-EVT-003 (phía E), TST-INT-INV-008 (phía E)`)
3. `TST-QC-INV-019`:
   - `tests/unit/voice/test_e12_language_evidence.py` (docstring: `coveredIds: TST-QC-INV-019 (phía E), CT-RND-002 language_validation_refs`)
4. `TST-SEC-INV-012`:
   - `tests/unit/voice/test_e14_tts_route_invocation.py` (docstring: `coveredIds: TST-SEC-INV-012, CT-AI-ROUTE-001, CT-AI-ROUTE-002`)
5. `TST-E2E-001`:
   - `tests/integration/voice/test_e16_voice_timing_pipeline.py` (docstring: `coveredIds: CT-TTS-001, CT-SUB-001, CT-RND-002, TST-MEDIA-INV-007 (phía E), TST-E2E-001 (đoạn voice và timing, phía E)`) - Đã được gộp qua tích hợp E-16-FIX1 tại commit `ace870b20f86bf842f4c36566c30c98af9e05ae7`.
6. `TST-E2E-011`:
   - `tests/integration/voice/test_e17_media_processing_pipeline.py` (docstring: `coveredIds: TST-E2E-011 (phía E), CT-PROC-003, CT-PROC-004, CT-PROC-005, CT-PROC-006, CT-PROC-007, CT-AUD-001`)
   - `tests/unit/voice/test_e05_image_safety.py` (docstring: `coveredIds: CT-PROC-005, TST-E2E-011 (phía E, mức domain)`)
   - `tests/unit/voice/test_e06_image_transform.py` (docstring: `coveredIds: CT-PROC-006, TST-E2E-011 (phía E, mức domain)`)
7. `TST-E2E-014`:
   - `tests/integration/voice/test_e18_worker_activity.py` (docstring: `coveredIds: CT-WF-003, CT-WF-006, TST-E2E-014 (phía E)`)
8. `CT-PROC-001`:
   - `tests/unit/voice/test_e02_processing_contract.py` (docstring: `coveredIds: CT-PROC-001, CT-PROC-002, CT-PROC-008, TST-INT-INV-008 (domain level)`)
9. `CT-PROC-002`:
   - `tests/unit/voice/test_e02_processing_contract.py` (docstring: `coveredIds: CT-PROC-001, CT-PROC-002, CT-PROC-008, TST-INT-INV-008 (domain level)`)
10. `CT-PROC-003`:
    - `tests/integration/voice/test_e17_media_processing_pipeline.py` (docstring: `coveredIds: TST-E2E-011 (phía E), CT-PROC-003, CT-PROC-004, CT-PROC-005, CT-PROC-006, CT-PROC-007, CT-AUD-001`)
    - `tests/unit/voice/test_e03_probe_media.py` (docstring: `coveredIds: CT-PROC-003`)
11. `CT-PROC-004`:
    - `tests/integration/voice/test_e17_media_processing_pipeline.py` (docstring: `coveredIds: TST-E2E-011 (phía E), CT-PROC-003, CT-PROC-004, CT-PROC-005, CT-PROC-006, CT-PROC-007, CT-AUD-001`)
    - `tests/unit/voice/test_e04_media_analysis.py` (docstring: `coveredIds: CT-PROC-004`)
12. `CT-PROC-005`:
    - `tests/integration/voice/test_e17_media_processing_pipeline.py` (docstring: `coveredIds: TST-E2E-011 (phía E), CT-PROC-003, CT-PROC-004, CT-PROC-005, CT-PROC-006, CT-PROC-007, CT-AUD-001`)
    - `tests/unit/voice/test_e05_image_safety.py` (docstring: `coveredIds: CT-PROC-005, TST-E2E-011 (phía E, mức domain)`)
13. `CT-PROC-006`:
    - `tests/integration/voice/test_e17_media_processing_pipeline.py` (docstring: `coveredIds: TST-E2E-011 (phía E), CT-PROC-003, CT-PROC-004, CT-PROC-005, CT-PROC-006, CT-PROC-007, CT-AUD-001`)
    - `tests/unit/voice/test_e06_image_transform.py` (docstring: `coveredIds: CT-PROC-006, TST-E2E-011 (phía E, mức domain)`)
14. `CT-PROC-007`:
    - `tests/integration/voice/test_e17_media_processing_pipeline.py` (docstring: `coveredIds: TST-E2E-011 (phía E), CT-PROC-003, CT-PROC-004, CT-PROC-005, CT-PROC-006, CT-PROC-007, CT-AUD-001`)
    - `tests/unit/voice/test_e07_normalize_media.py` (docstring: `coveredIds: CT-PROC-007`)
15. `CT-PROC-008`:
    - `tests/unit/voice/test_e02_processing_contract.py` (docstring: `coveredIds: CT-PROC-001, CT-PROC-002, CT-PROC-008, TST-INT-INV-008 (domain level)`)
16. `CT-TTS-001`:
    - `tests/integration/voice/test_e16_voice_timing_pipeline.py` (docstring: `coveredIds: CT-TTS-001, CT-SUB-001, CT-RND-002, TST-MEDIA-INV-007 (phía E), TST-E2E-001 (đoạn voice và timing, phía E)`)
    - `tests/unit/voice/test_e08_voice_track.py` (docstring: `coveredIds: CT-TTS-001`)
17. `CT-SUB-001`:
    - `tests/integration/voice/test_e16_voice_timing_pipeline.py` (docstring: `coveredIds: CT-TTS-001, CT-SUB-001, CT-RND-002, TST-MEDIA-INV-007 (phía E), TST-E2E-001 (đoạn voice và timing, phía E)`)
    - `tests/unit/voice/test_e09_word_timing.py` (docstring: `coveredIds: CT-SUB-001 bất biến 1`)
    - `tests/unit/voice/test_e10_timing_coverage.py` (docstring: `coveredIds: CT-SUB-001 (phủ từ, gap, confidence)`)
    - `tests/unit/voice/test_e11_timing_binding.py` (docstring: `coveredIds: TST-MEDIA-INV-007 (mức domain), CT-SUB-001 bất biến 2 và 3`)
18. `CT-AUD-001`:
    - `tests/integration/voice/test_e17_media_processing_pipeline.py` (docstring: `coveredIds: TST-E2E-011 (phía E), CT-PROC-003, CT-PROC-004, CT-PROC-005, CT-PROC-006, CT-PROC-007, CT-AUD-001`)
    - `tests/unit/voice/test_e13_audio_bed.py` (docstring: `coveredIds: CT-AUD-001`)

## Ánh xạ acceptance §10 của contract 07

| Mục | Nội dung | Slice | Test |
|---|---|---|---|
| 1 | Mọi output truy ngược được input, spec và processor version | E-02, E-07, E-19 | test_processor_identity_rules, test_same_input_spec_tool_version_gives_same_fingerprints_and_output_ref, test_trace_processed_media_traces_inputs_spec_revision_and_processor_identity |
| 2 | Safety transform chỉ áp dụng cho ảnh, không áp dụng clip | E-07, E-17 | test_clip_with_blur_or_recolor_is_rejected, test_assess_clip_is_rejected_without_writes, test_transform_clip_is_rejected_without_writes |
| 3 | Ảnh lỗi/không chắc vẫn dùng được theo R25 nhưng không ghi nhầm safe/processed | E-05, E-06, E-17 | test_only_clean_result_is_safe_and_transform_failed_is_never_produced, test_only_safe_post_assessment_yields_success, test_transform_port_crash_is_transform_failed_not_safe |
| 4 | Subtitle timing khớp exact script và voice hash | E-09, E-11, E-16, E-19 | test_changed_script_or_voice_makes_old_timing_invalid, test_fingerprint_mismatch_is_rejected_before_any_tts_call, test_trace_timing_traces_voice_hash_script_fingerprint_report_and_language_evidence |
| 5 | Đổi voice/script làm invalid timing downstream | E-11, E-16 | test_script_change_makes_voice_track_and_timing_stale, test_voice_change_makes_only_timing_stale, test_script_change_after_timing_rejects_old_timing_and_stale_voice |
| 6 | Original và rendition dùng lại được không bị xoá cùng tệp tạm per-video | E-02, E-11, E-19 | test_retention_intent_plan_section_7, test_invalidation_does_not_mutate_or_delete_old_records, test_processed_media_is_classified_per_video_or_reusable |

## Phản ví dụ đã loại trừ

- Phản ví dụ 1: Một CT-PROC không có test trực tiếp -> Loại trừ bởi `test_required_id_is_declared_in_a_file_with_test_functions` (khẳng định toàn bộ 8 mã CT-PROC-001..008 đều được khai báo trong tệp có chứa hàm `test_`) và `test_checker_requires_a_real_test_function`.
- Phản ví dụ 2: Mã chỉ xuất hiện trong E-20 -> Loại trừ bởi `test_scan_covers_e01_to_e19_and_excludes_e20` (bộ quét loại trừ chính tệp E-20 `test_e20_coverage_catalog.py`, chỉ quét các tệp test_e01..e19) và `test_checker_ignores_ids_outside_module_docstring`.
- Phản ví dụ 3: Dùng test ID ngoài catalog -> Loại trừ bởi `test_tst_ids_used_in_docstrings_exist_in_catalog` (đối soát toàn bộ các mã TST-* ID dùng trong docstring và REQUIRED_IDS với docs/10-test-strategy.md) và `test_no_scanned_file_uses_forbidden_prefix` (khẳng định không tệp nào sử dụng tiền tố cấm TST-VOI-, TST-MED-, TST-RND-, TST-EF-).

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider | 0 | 25 passed in 1.88s |
| 2 | git diff --check | 0 | PASS (không output, không trailing whitespace) |
| 3 | python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider | 0 | 25 passed in 2.21s |

## Quyết định mặc định (D8)

1. Phân tích AST tĩnh bằng thư viện chuẩn `ast`, `pathlib`, `re` thay vì import động để tránh side-effect và tối ưu thời gian chạy;
2. Kiểm tra chặt chẽ sự hiện diện của hàm test thực sự (`test_*`) trong các tệp khai báo coveredIds để đảm bảo không chấp nhận file rỗng hoặc chỉ có stub helper;
3. Cấm tuyệt đối các tiền tố ID ngoại lai `TST-VOI-`, `TST-MED-`, `TST-RND-`, `TST-EF-` theo quy chuẩn đặt tên toàn cục của dự án;
4. Ánh xạ trực tiếp và đầy đủ 6 mục của contract 07 §10 vào các hàm test đã được chứng thực trong kho mã nguồn;

## coveredIds

- acceptance §10 mục 1 đến 6 của contract 07

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) - chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa đổi mã nguồn trong `src/**` hoặc các tệp cấu hình chung.
- Chỉ dùng thư viện chuẩn Python kết hợp với pytest.

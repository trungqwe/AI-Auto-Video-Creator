# Báo cáo bằng chứng D-18

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 9dd3efea87d4172a55ae0bdd8e8b8f93025dc57c
- Nguồn quyền: IMPL-PLAN-D Auditor PASS, slice D-18 trong docs/implementation/d/slices.md, ủy quyền AI_SETUP.

## RED

- Lệnh thực thi: python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider (chạy với skeleton ở bước 1-3)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 2 failed, 6 passed in 0.19s
- Tên hai test FAILED kèm thông điệp NotImplementedError:
  - FAILED tests/unit/creative/test_d18_coverage_catalog.py::test_every_required_id_has_a_test_file: NotImplementedError: D-18 RED skeleton: collect_coverage
  - FAILED tests/unit/creative/test_d18_coverage_catalog.py::test_report_table_matches_docstring_coverage: NotImplementedError: D-18 RED skeleton: collect_coverage
- Xác nhận: Hoàn toàn không có ImportError, SyntaxError hay lỗi collection. 6 test khác đã PASS.

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 8 passed in 0.40s

## Thay đổi

- Hai tệp trong owned paths và vai trò:
  - tests/unit/creative/test_d18_coverage_catalog.py (8 test: quét test_d*.py ở tests/unit/creative và tests/integration/creative trừ chính D-18, chỉ stdlib ast/pathlib/re; khẳng định 19 mã có tệp test với hàm test_; không dùng tiền tố TST-CRE-; không dùng TST ngoài catalog; bảng report khớp docstring)
  - docs/delivery-evidence/d-18/report.md: Báo cáo bằng chứng nghiệm thu theo đúng quy chuẩn.

## Ánh xạ phản ví dụ -> test

- CT-AI không có test trực tiếp -> test_every_required_id_has_a_test_file và test_every_declaring_file_has_a_test_function
- Mã chỉ xuất hiện trong D-18 -> scan_files loại trừ chính D-18 (test_scan_covers_every_creative_test_file) và test_own_docstring_declares_no_covered_ids
- Test ID ngoài catalog -> test_no_test_id_outside_catalog và test_no_file_uses_cre_prefix
- Bảng report lệch docstring -> test_report_table_matches_docstring_coverage

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider | 0 | 8 passed in 0.40s |
| 2 | git diff --check | 0 | PASS (không output, không lỗi khoảng trắng) |

## Quyết định mặc định (D8)

1. Chỉ đọc dòng coveredIds trong docstring, không đếm mã nhắc trong văn xuôi hay trong assert;
2. Test ID ngoài catalog chỉ xét tiền tố TST-;
3. Report được kiểm máy bằng test để không lệch docstring;
4. test_d18 khai 'coveredIds: không' như D-01.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi src, pyproject.toml, uv.lock.
- Chỉ stdlib.
- Không gọi dịch vụ thật.

## Bảng ánh xạ mã CT/TST -> tệp test

| Mã | Tệp test (dòng coveredIds trong docstring) |
|---|---|
| TST-INT-INV-004 | tests/integration/creative/test_d14_creative_pipeline.py, tests/unit/creative/test_d02_production_snapshot.py |
| TST-INT-INV-005 | tests/integration/creative/test_d14_creative_pipeline.py, tests/unit/creative/test_d02_production_snapshot.py |
| TST-CTR-INV-006 | tests/unit/creative/test_d07_timeline_authorization.py |
| TST-AI-INV-013 | tests/unit/creative/test_d06_story_angles.py, tests/unit/creative/test_d11_variant_validation.py |
| TST-AI-INV-014 | tests/unit/creative/test_d11_variant_validation.py |
| TST-SEC-INV-012 | tests/unit/creative/test_d04_ai_route_invocation.py |
| TST-SEC-INV-020 | tests/unit/creative/test_d03_untrusted_boundary.py, tests/unit/creative/test_d05_content_analysis.py |
| TST-WF-VAR-004 | tests/unit/creative/test_d11_variant_validation.py |
| CT-AI-000 | tests/unit/creative/test_d03_untrusted_boundary.py |
| CT-AI-001 | tests/unit/creative/test_d02_production_snapshot.py |
| CT-AI-002 | tests/unit/creative/test_d05_content_analysis.py |
| CT-AI-003 | tests/unit/creative/test_d06_story_angles.py |
| CT-AI-004 | tests/unit/creative/test_d08_script_version.py |
| CT-AI-005 | tests/unit/creative/test_d07_timeline_authorization.py |
| CT-AI-006 | tests/unit/creative/test_d09_asset_selection.py |
| CT-AI-007 | tests/unit/creative/test_d10_production_plan.py |
| CT-AI-008 | tests/unit/creative/test_d11_variant_validation.py |
| CT-AI-009 | tests/unit/creative/test_d12_output_metadata.py |
| CT-AI-010 | tests/integration/creative/test_d15_provider_failure.py, tests/unit/creative/test_d04_ai_route_invocation.py |

Không dùng tiền tố TST-CRE- ở bất kỳ tệp nào; mỗi tệp trong bảng có ít nhất một hàm test_. Ánh xạ RED -> GREEN: RED = skeleton collect_coverage raise NotImplementedError (bước 3); GREEN = cài collect_coverage thật (bước 4) cùng bảng này.

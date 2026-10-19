# Báo cáo bằng chứng A-19

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `bfc0d32e2bbe8f897229b9b87d77f91f200f3e9d`
- Nguồn quyền: IMPL-PLAN-A Auditor PASS (slice A-19 trong `docs/implementation/a/slices.md`).

## RED

Slice chỉ thêm test, không có mã sản phẩm để làm RED. Phản ví dụ "mã chỉ xuất hiện trong docstring mà tệp không có hàm test_" được khoá bằng `test_file_without_a_test_function_covers_no_id`; phản ví dụ "mã chỉ nằm trong docstring của A-19" được khoá bằng `test_scan_covers_the_test_file_of_every_slice_a01_to_a18_and_skips_a19` và `test_catalog_never_lists_the_a19_file`.

## Thay đổi

- `tests/unit/collection/test_a19_rule_catalog.py`: chỉ dùng stdlib và pytest, đọc docstring module (dòng `coveredIds:`) của `tests/unit/collection/test_a*.py` và `tests/integration/collection/test_a*.py` (trừ A-19), loại tệp không có hàm `test_`, khẳng định đủ 29 mã bắt buộc và đối chiếu bảng ánh xạ bên dưới.
- `docs/delivery-evidence/a-19/report.md`: báo cáo này.

## Bảng ánh xạ mã → tệp test

Tệp `test_a09`, `test_a10`, `test_a11`, `test_a14`, `test_a16`, `test_a18` nằm ở `tests/integration/collection/`; các tệp còn lại nằm ở `tests/unit/collection/`.

| Mã | Tệp test |
|---|---|
| `A-RULE-001` | `test_a09_source_commands.py` |
| `A-RULE-002` | `test_a07_source_candidate.py`, `test_a09_source_commands.py`, `test_a10_candidate_registration.py`, `test_a16_supplemental.py` |
| `A-RULE-003` | `test_a03_source_lifecycle.py`, `test_a09_source_commands.py` |
| `A-RULE-004` | `test_a05_collection_run_states.py`, `test_a08_ports_memory.py`, `test_a11_collect_source.py` |
| `A-RULE-005` | `test_a05_collection_run_states.py`, `test_a16_supplemental.py` |
| `A-RULE-006` | `test_a15_source_eligibility.py` |
| `A-RULE-007` | `test_a15_source_eligibility.py` |
| `A-RULE-008` | `test_a11_collect_source.py` |
| `A-RULE-009` | `test_a06_checkpoint.py` |
| `A-RULE-010` | `test_a02_collected_document_package.py`, `test_a13_package_builder.py` |
| `A-RULE-011` | `test_a13_package_builder.py` |
| `A-RULE-012` | `test_a11_collect_source.py` |
| `A-RULE-013` | `test_a04_locator_ssrf.py`, `test_a12_secure_fetch.py` |
| `A-RULE-014` | `test_a09_source_commands.py`, `test_a12_secure_fetch.py`, `test_a17_projections.py`, `test_a18_worker_activity.py` |
| `A-RULE-015` | `test_a14_artifact_handoff.py` |
| `A-RULE-016` | `test_a18_worker_activity.py` |
| `TST-COL-END-001` | `test_a05_collection_run_states.py` |
| `TST-COL-END-002` | `test_a05_collection_run_states.py` |
| `TST-COL-END-003` | `test_a05_collection_run_states.py` |
| `TST-COL-END-004` | `test_a05_collection_run_states.py` |
| `TST-COL-PKG-001` | `test_a02_collected_document_package.py` |
| `TST-COL-PKG-002` | `test_a02_collected_document_package.py` |
| `TST-COL-PKG-003` | `test_a02_collected_document_package.py` |
| `TST-COL-PKG-004` | `test_a02_collected_document_package.py` |
| `TST-SRC-RACE-001` | `test_a10_candidate_registration.py` |
| `TST-SRC-RACE-002` | `test_a10_candidate_registration.py` |
| `TST-SRC-RACE-003` | `test_a10_candidate_registration.py` |
| `TST-SRC-RACE-004` | `test_a10_candidate_registration.py` |
| `TST-INT-INV-015` | `test_a07_source_candidate.py`, `test_a10_candidate_registration.py` |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cacheprovider` | 0 | 62 passed in 0.14s |
| 2 | `git diff --check` | 0 | passed (không output) |

## Giới hạn

- Không chạy full test suite, `tests/m1`, `tests/m2`.
- Không đổi `src/`, `pyproject.toml`, `uv.lock` hay các test A-01..A-18.
- Không gọi mạng thật.

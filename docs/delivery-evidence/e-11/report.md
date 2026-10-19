# Báo cáo bằng chứng E-11

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: c695121600c8d1b73e9153cbd26dab92cf2f6b18
- Nguồn quyền: IMPL-PLAN-E Auditor PASS và slice E-11 trong docs/implementation/e/slices.md.

## RED

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider (chạy với khung stub ở bước 1 và 2)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 10 failed, 11 passed in 0.23s
- Chi tiết các test FAILED tiêu biểu kèm thông điệp:
  - FAILED tests/unit/voice/test_e11_timing_binding.py::test_changed_script_or_voice_makes_old_timing_invalid[...-reasons0]: AssertionError: assert TimingBinding...e, reasons=()) == TimingBinding...pt_changed',))
  - FAILED tests/unit/voice/test_e11_timing_binding.py::test_check_result_is_frozen_and_bad_inputs_are_never_valid: Failed: DID NOT RAISE ValueError
  - FAILED tests/unit/voice/test_e11_timing_binding.py::test_script_change_makes_voice_track_and_timing_stale: AssertionError: assert () == (StaleRecord(...pt_changed'),)
  - FAILED tests/unit/voice/test_e11_timing_binding.py::test_voice_change_makes_only_timing_stale: AssertionError: assert () == (StaleRecord(...ce_changed'),)
  - FAILED tests/unit/voice/test_e11_timing_binding.py::test_voice_artifact_revision_change_makes_only_timing_of_that_artifact_stale: AssertionError: assert () == (StaleRecord(...on_changed'),)
  - FAILED tests/unit/voice/test_e11_timing_binding.py::test_invalidation_does_not_mutate_or_delete_old_records: AssertionError: assert (0 == 1)
  - FAILED tests/unit/voice/test_e11_timing_binding.py::test_replacement_after_invalidation_is_a_new_record: AssertionError: assert ()
  - FAILED tests/unit/voice/test_e11_timing_binding.py::test_invalidate_downstream_rejects_wrong_types: Failed: DID NOT RAISE TypeError
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError hay lỗi collection. 11 test đã PASS ngay từ đầu. Tất cả 10 test thất bại đều do stub chỉ trả kết quả mặc định hoặc không raise ngoại lệ.

## GREEN

- Lệnh thực thi: python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider (chạy sau khi cài đặt logic hoàn chỉnh)
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: 21 passed in 0.07s

## Thay đổi

- Ba tệp thuộc owned paths và vai trò từng tệp:
  - src/voice/domain/timing_binding.py: Định nghĩa dataclass frozen TimingBinding, TimingBindingCheck, ngoại lệ TimingBindingError, dataclass DownstreamChange, StaleRecord, InvalidationResult, và các hàm domain pure check_timing_binding,
equire_valid_timing, invalidate_downstream (CT-SUB-001 bất biến 2 và 3).
  - 	ests/unit/voice/test_e11_timing_binding.py: Bộ kiểm thử 21 test cases toàn diện kiểm tra tính bất biến frozen, xác thực kiểu sha256 và các trường, sao chép từ WordTimingRecord, kiểm tra tính hợp lệ của binding khi script/voice khớp hoặc lệch, kiểm tra invalidation downstream không sửa/xóa bản ghi cũ, tạo bản ghi mới thay thế, từ chối kiểu sai, và cô lập ranh giới import chỉ dùng stdlib và module cho phép.
  - docs/delivery-evidence/e-11/report.md: Báo cáo bằng chứng nghiệm thu theo đúng mẫu quy chuẩn.
- Ánh xạ phản ví dụ -> test:
  - 	iming cũ vẫn hợp lệ sau đổi script/voice: 	est_changed_script_or_voice_makes_old_timing_invalid
  - invalidation sửa tại chỗ bản cũ: 	est_invalidation_does_not_mutate_or_delete_old_records và 	est_replacement_after_invalidation_is_a_new_record
  - đổi voice không làm timing stale: 	est_voice_change_makes_only_timing_stale
  - script đổi làm cả voice track và timing stale: 	est_script_change_makes_voice_track_and_timing_stale

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider | 0 | 21 passed in 0.07s |
| 2 | python -m pytest tests/unit/voice -q -p no:cacheprovider | 0 | 272 passed, 49 subtests passed in 0.46s |
| 3 | git diff --check | 0 | PASS (không output, không trailing whitespace) |

## Quyết định mặc định (D8)

1. TimingBinding kiểm kiểu trường, sha256 là hex thường;
2. check_timing_binding trả TimingBindingCheck(valid, reasons) với
easons theo thứ tự script_changed rồi oice_changed;
3. Giá trị hiện hành thiếu hoặc sai định dạng ném ValueError, không bao giờ coi là valid;
4. DownstreamChange có ba kind script_changed, oice_changed, oice_artifact_revision_changed; revision đổi được quy về oice_hash của voice track khớp oice_artifact_ref và revision cũ, chỉ làm timing stale (GIẢ ĐỊNH, theo cùng quy tắc với voice đổi);
5. InvalidationResult chỉ mang ref và reason, không giữ hay sửa bản cũ; contract không có event vô hiệu hóa timing nên không phát event (event mới qua CONV-E-10);
6. Module chỉ import stdlib cùng oice.domain.voice_track và oice.domain.word_timing, không tính lại fingerprint hay hash.

## coveredIds

- TST-MEDIA-INV-007 (mức domain)
- CT-SUB-001 bất biến 2 và 3

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- User checkpoint M2 (P8/P9) — chưa ghi là đã duyệt

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock, binding, fixture.
- Chỉ dùng stdlib.
- Không gọi dịch vụ thật.

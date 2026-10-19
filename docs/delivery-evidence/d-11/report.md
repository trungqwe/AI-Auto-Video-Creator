# Báo cáo bằng chứng D-11

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `ab7cb613044212edf40e03817b75d6d648823269`
- Nguồn quyền: user duyệt Phần B ngày 18/10/2026, ủy quyền AI_SETUP, slice D-11.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider` (chạy với khung variant.py ở bước 1 chưa có hành vi)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `58 failed, 4 passed in 1.08s`
- Chi tiết các test FAILED chọn lọc kèm thông điệp assertion nguyên văn:
  - `FAILED tests/unit/creative/test_d11_variant_validation.py::test_each_real_content_change_moves_only_its_factor[voice]`: `AttributeError: 'NoneType' object has no attribute 'factors'`
  - `FAILED tests/unit/creative/test_d11_variant_validation.py::test_fingerprint_ignores_ids_revisions_and_rationale`: `AttributeError: 'NoneType' object has no attribute 'factors'`
  - `FAILED tests/unit/creative/test_d11_variant_validation.py::test_fingerprint_shape_is_deterministic_and_immutable`: `AttributeError: 'NoneType' object has no attribute 'factors'`
  - `FAILED tests/unit/creative/test_d11_variant_validation.py::test_builder_rejects_missing_or_mismatched_inputs[overrides0-expected0]`: `Failed: DID NOT RAISE VariantRejected`
  - `FAILED tests/unit/creative/test_d11_variant_validation.py::test_same_run_distinct_angles_are_valid`: `AttributeError: 'NoneType' object has no attribute 'valid'`
  - `FAILED tests/unit/creative/test_d11_variant_validation.py::test_cross_run_exact_duplicate_is_invalid`: `AttributeError: 'NoneType' object has no attribute 'valid'`
  - `FAILED tests/unit/creative/test_d11_variant_validation.py::test_other_job_reservation_with_same_fingerprint_blocks`: `AttributeError: 'NoneType' object has no attribute 'valid'`
  - `FAILED tests/unit/creative/test_d11_variant_validation.py::test_output_phase_requires_exact_output_hash`: `Failed: DID NOT RAISE VariantRejected`
  - `FAILED tests/unit/creative/test_d11_variant_validation.py::test_validate_variant_rejects_bad_inputs[overrides0-expected0]`: `Failed: DID NOT RAISE VariantRejected`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, SyntaxError hay lỗi collection; RED là sai oracle (AttributeError trên NoneType, DID NOT RAISE VariantRejected).

## GREEN

- Lệnh thực thi: `python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider`
- Exit code thực tế: 0
- Dòng tóm tắt nguyên văn: `62 passed in 0.22s`

## Thay đổi

- 3 tệp thuộc owned paths:
  - `src/creative/domain/variant.py`: Hiện thực miền kiểm định biến thể độc lập không I/O, không clock, không AI, không tự tạo/release reservation. Khai báo các hằng số nhận diện mã lỗi (`INPUT_NOT_READY`, `INVALID_INPUT`, `CONTEXT_MISMATCH`), phase (`plan`, `output`), 9 yếu tố khác biệt theo CT-AI-008 bất biến 3 (`voice`, `sound`, `hook`, `media`, `effects`, `content`, `narration_style`, `background_music`, `angle`), và reason codes; lớp ngoại lệ `VariantRejected`; kiểu dữ liệu frozen `VariantFingerprint` với chuẩn hoá đệ quy (`_norm`), tính toán 9 yếu tố độc lập và hash toàn phần nội dung (loại bỏ seed, id, revision, rationale); hàm dựng `build_variant_fingerprint`; các kiểu `CompletedVariant`, `SameRunVariant`, `VariantValidationResult`; hàm kiểm định `validate_variant` đối chiếu ứng viên với lịch sử đã hoàn thành và reservation đang hoạt động (tái sử dụng `VariantReservation` của G), loại trừ reservation của chính job, xác nhận khác biệt góc cùng lượt, kiểm tra exact duplicate và độ gần lịch sử, yêu cầu exact output hash cho phase output, hỗ trợ `is_current_for` nhận biết kết quả stale khi registry revision thay đổi.
  - `tests/unit/creative/test_d11_variant_validation.py`: Bộ kiểm thử đơn vị toàn diện (62 bài test) bao gồm: khai báo coveredIds trong docstring; kiểm tra allowlist import và tái sử dụng `VariantReservation` của controlplane; kiểm tra không tạo reservation, không gọi AI, không nhận seed; kiểm tra 9 yếu tố nội dung thật chỉ làm đổi đúng yếu tố tương ứng của fingerprint; kiểm tra bỏ qua ID, revision, rationale; kiểm tra chuẩn hoá không phân biệt hoa thường và khoảng trắng; kiểm tra tính xác định và đóng băng bất biến; kiểm tra các trường hợp từ chối đầu vào builder và kiểu sai; kiểm tra cùng lượt trùng góc bị loại (TST-AI-INV-013); kiểm tra giữa các lượt exact duplicate hoặc không có yếu tố khác bị loại (TST-AI-INV-014, TST-WF-VAR-004); kiểm tra reservation của job khác chặn exact duplicate, reservation của chính job được loại trừ; kiểm tra từ chối reservation không ACTIVE; kiểm tra tính toán input hashes; kiểm tra phase output bắt buộc output hash; kiểm tra kết quả phase plan không xác nhận output; kiểm tra registry revision mới làm kết quả cũ stale; kiểm tra tính bất biến của kết quả và kiểm tra hàm kiểm định không làm biến đổi đầu vào.
  - `docs/delivery-evidence/d-11/report.md`: Báo cáo bằng chứng nghiệm thu của task D-11 ghi nhận RED→GREEN và tuân thủ các quy tắc bàn giao.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider` | 0 | 62 passed in 0.22s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## coveredIds

`CT-AI-008, TST-AI-INV-013, TST-AI-INV-014, TST-WF-VAR-004 phía D`

## Quyết định mặc định (D8)

1. Chín yếu tố voice, sound, hook, media, effects, content, narration_style, background_music, angle lấy từ CT-AI-008 bất biến 3, tên hằng D-local là GIẢ ĐỊNH.
2. VariantFingerprint = hash từng yếu tố + hash nội dung đầy đủ, chỉ từ nội dung script/plan/selection và angle_distinction_fingerprint, loại id, seed, revision, rationale.
3. own_reservation_id có thể None ở phase plan vì chưa có reservation.
4. VariantReservation chỉ mang fingerprint tổng nên chỉ đối chiếu exact, yếu tố khác biệt tính trên lịch sử completed, không có lịch sử thì mọi yếu tố.
5. Reservation không ACTIVE của job khác bị từ chối fail-closed.
6. Kết quả cũ stale qua is_current_for, valid không thay CAS của G.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-D9-D10
- CP7 tài nguyên thật D5
- User checkpoint M2 P8/P9 chưa ghi là đã duyệt
- CONV-D-05 và CONV-D-07 thuộc hội tụ G

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không đổi pyproject.toml, uv.lock.
- Không gọi dịch vụ thật.
- Không gọi AI, không tạo/release reservation.
- D không đọc artifact output: exact output hash do caller cấp.

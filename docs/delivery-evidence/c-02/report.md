# Báo cáo bằng chứng C-02

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `5b5d282e1862f8ff9a19831147bcf3ceec7fcf7e`
- Nguồn quyền: IMPL-PLAN-C Auditor PASS, slice C-02 trong `docs/implementation/c/slices.md`.

## RED

- Lệnh thực thi: `python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovider` (chạy với stub ở bước 4)
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: `39 failed, 15 passed, 11 subtests passed in 0.16s`
- Chi tiết các test FAILED/SUBFAILED kèm thông điệp AssertionError nguyên văn từ bước 5:
  - `FAILED tests/unit/catalog/test_catalog_states.py::EnumValueTests::test_rendition_state_values`: `AssertionError: Items in the second set but not the first: 'OUTCOME_UNKNOWN'`
  - `SUBFAILED(kind='clip', state='NOT_ASSESSED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='clip', state='ASSESSING') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='clip', state='SAFE') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='clip', state='TRANSFORM_REQUIRED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='clip', state='UNCERTAIN') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='clip', state='DETECTION_FAILED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='clip', state='UNREADABLE') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='clip', state='TRANSFORMING') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='clip', state='PROCESSED_READY') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='clip', state='TRANSFORM_FAILED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='audio', state='NOT_ASSESSED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='audio', state='ASSESSING') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='audio', state='SAFE') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='audio', state='TRANSFORM_REQUIRED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='audio', state='UNCERTAIN') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='audio', state='DETECTION_FAILED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='audio', state='UNREADABLE') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='audio', state='TRANSFORMING') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='audio', state='PROCESSED_READY') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(kind='audio', state='TRANSFORM_FAILED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_clip_and_audio_reject_safety_state`: `AssertionError: ValueError not raised`
  - `SUBFAILED(state='NOT_ASSESSED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_image_mapping_covers_every_state`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(state='ASSESSING') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_image_mapping_covers_every_state`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(state='TRANSFORM_REQUIRED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_image_mapping_covers_every_state`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(state='UNCERTAIN') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_image_mapping_covers_every_state`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.USABLE_WITH_WARNING: 'usable_with_warning'>`
  - `SUBFAILED(state='DETECTION_FAILED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_image_mapping_covers_every_state`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.USABLE_WITH_WARNING: 'usable_with_warning'>`
  - `SUBFAILED(state='UNREADABLE') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_image_mapping_covers_every_state`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(state='TRANSFORMING') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_image_mapping_covers_every_state`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(state='TRANSFORM_FAILED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_image_mapping_covers_every_state`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.USABLE_WITH_WARNING: 'usable_with_warning'>`
  - `FAILED tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_image_requires_safety_state`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_rejects_unknown_safety_value`: `AssertionError: ValueError not raised`
  - `FAILED tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_unreadable_is_not_usable`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(state='UNCERTAIN') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_warning_states_are_never_usable`: `AssertionError: unexpectedly identical: <Usability.USABLE: 'usable'>`
  - `SUBFAILED(state='DETECTION_FAILED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_warning_states_are_never_usable`: `AssertionError: unexpectedly identical: <Usability.USABLE: 'usable'>`
  - `SUBFAILED(state='TRANSFORM_FAILED') tests/unit/catalog/test_catalog_states.py::SafetyClassificationTests::test_warning_states_are_never_usable`: `AssertionError: unexpectedly identical: <Usability.USABLE: 'usable'>`
  - `SUBFAILED(availability='MISSING') tests/unit/catalog/test_catalog_states.py::AvailabilityClassificationTests::test_mapping_covers_every_value`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(availability='CORRUPT') tests/unit/catalog/test_catalog_states.py::AvailabilityClassificationTests::test_mapping_covers_every_value`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `SUBFAILED(availability='RECOVERING') tests/unit/catalog/test_catalog_states.py::AvailabilityClassificationTests::test_mapping_covers_every_value`: `AssertionError: <Usability.USABLE: 'usable'> is not <Usability.NOT_USABLE: 'not_usable'>`
  - `FAILED tests/unit/catalog/test_catalog_states.py::AvailabilityClassificationTests::test_rejects_unknown_availability`: `AssertionError: ValueError not raised`
- Xác nhận: Hoàn toàn không có ImportError, ModuleNotFoundError, AttributeError, TypeError, NameError hay lỗi collection nào (EnumValueTests các test khác, SafetyClassificationTests các test khác, ModuleSurfaceTests đều PASS).

## Thay đổi

- `src/catalog/domain/states.py`:
  - 5 StrEnum đúng tên CT-STATE-005/006: `DiscoveryState` (DISCOVERED, ACQUIRING, CATALOGED, FAILED), `RenditionState` (DECLARED, PROCESSING, READY, FAILED, OUTCOME_UNKNOWN), `Availability` (AVAILABLE, MISSING, CORRUPT, RECOVERING, UNAVAILABLE_SOURCE), `ImageSafetyState` (NOT_ASSESSED, ASSESSING, SAFE, TRANSFORM_REQUIRED, UNCERTAIN, DETECTION_FAILED, UNREADABLE, TRANSFORMING, PROCESSED_READY, TRANSFORM_FAILED), `Usability` (usable, usable_with_warning, not_usable).
  - Bảng ánh xạ chỉ đọc `_IMAGE_SAFETY_USABILITY` và `_AVAILABILITY_USABILITY` dạng MappingProxyType.
  - Hàm phân loại `classify_safety(kind: MediaKind, safety: ImageSafetyState | None) -> Usability` (D8-C-05).
  - Hàm phân loại `classify_availability(availability: Availability) -> Usability`.
  - Không có hàm chuyển trạng thái; không có tên nào bắt đầu bằng 'transition' (D8-C-04, CONV-C-07); không import controlplane.
- `tests/unit/catalog/test_catalog_states.py`:
  - 4 class kiểm thử bao phủ toàn bộ invariant: `EnumValueTests`, `SafetyClassificationTests`, `AvailabilityClassificationTests`, `ModuleSurfaceTests`.
  - Binding fixture `tests/fixtures/contracts/c-d-media-candidates/payloads.json` để kiểm tra candidate payload availability.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovider` | 0 | 20 passed, 45 subtests passed in 0.03s |
| 2 | `git diff --check` | 0 | PASS (không output, không trailing whitespace, không lỗi định dạng diff) |

## Quyết định mặc định (D8)

1. Ảnh (`image`) với `safety is None` raise `ValueError`; ảnh chưa đánh giá dùng `NOT_ASSESSED`.
2. `NOT_ASSESSED`, `ASSESSING`, `TRANSFORM_REQUIRED`, `TRANSFORMING` → `not_usable` là GIẢ ĐỊNH fail-closed theo D8-C-05, xem lại khi E chốt pipeline.
3. Hai hàm chuyển đầu vào qua constructor enum (`MediaKind(...)`, `ImageSafetyState(...)`, `Availability(...)`); giá trị lạ raise `ValueError`.
4. Không có hàm chuyển trạng thái; bảng ánh xạ là MappingProxyType chỉ đọc; đồ thị chuyển CT-STATE-005/006 chờ gói hội tụ CONV-C-07.
5. Trục trạng thái contract có name == value chữ hoa; `Usability` dùng giá trị chữ thường theo CT-STATE-006.

## Danh sách chờ user (pendingUserCheckpoint)

- USER-CKPT-C-I-R2
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)
- ROADMAP-OPEN-010
- ROADMAP-OPEN-011
(Không tự ý ghi nhận bất kỳ mục nào ở trên là đã được người dùng phê duyệt.)

## Giới hạn

- Không chạy full suite, tests/m1, tests/m2.
- Không sửa `pyproject.toml`, `uv.lock`, migration, fixture, state machine dùng chung.
- Không thêm thư viện ngoài, chỉ dùng Python stdlib (`enum`, `types`, `ast`, `inspect`, `json`, `pathlib`, `unittest`).
- Không gọi dịch vụ thật.
- Không tạo `conftest.py` hay `__init__.py` trong `tests/`.

# Báo cáo thực hiện bàn giao gói PW-F4-FIX1

## 1. Phạm vi và bối cảnh

- **Mã gói**: `PW-F4-FIX1`
- **Milestone**: M7
- **Mã nhóm lỗi**: `R8` (hash đã xác minh lúc render bị bỏ đi khiến `prepare_output_ready` luôn trả cảnh báo `expected_sha256_invalid`).
- **Nguồn lỗi gốc xác định theo từng tệp và dòng**:
  1. `src/render/application/render_video.py:343-361`: `render_video._verify` so khớp hash renderer khai với hash quan sát từ tệp thực tế rồi trả về `None`, bỏ mất giá trị hash đã xác minh.
  2. `src/render/application/render_video.py:133-138`: Dataclass `RenderResult` không mang trường hash, khiến các tầng ngoài không nhận được hash đã kiểm chứng.
  3. `src/render/worker/activity_handler.py:305-306`: Handler `_render_outcome` chỉ phát ref `render_output` với duy nhất trường `ref_id`, không có trường `sha256`.
  4. `src/render/adapters/activity_inputs.py:228-246` (đặc biệt dòng 242): Phương thức `_for_prepare` chỉ tìm lấy `expected_sha256` từ ref loại `expected_sha256` mà không có hoạt động nào trong flow phát sinh ref này.
  5. `src/render/domain/output_ready.py:136-139`: Do `expected_sha256` là `None`, `evaluate_output_ready` luôn thêm cảnh báo `expected_sha256_invalid` và chuyển trạng thái sang `EXPECTED_HASH_INVALID`.

## 2. Các tệp đã sửa và thay đổi theo từng symbol

Các chỉnh sửa chỉ thực hiện trong các owned paths được phân quyền:

1. `src/render/application/render_video.py`:
   - `RenderResult`: Bổ sung trường `output_sha256: str | None = None` đứng sau `problem`, cập nhật docstring mô tả chi tiết: chỉ render mới thành công (`SUCCEEDED`) mới mang hash chữ thường, còn `FAILED`, `OUTCOME_UNKNOWN`, `replayed` và `reconciled` là `None`.
   - `RenderPipeline._verify`: Đổi chữ ký thành `def _verify(self, started: RenderAttempt, outcome: RendererOutcome) -> tuple[str | None, str | None]:`. Trả về `(None, claimed)` khi thành công và `(static_reason, None)` khi thất bại. Logic so khớp hash giữ nguyên tuyệt đối.
   - `RenderPipeline._finish`: Đổi chữ ký thành `def _finish(self, command: RenderVideoCommand, started: RenderAttempt, lease: GpuLease) -> tuple[RenderAttempt, str | None]:`. Trả về `(attempt SUCCEEDED, verified_sha256)` cho nhánh thành công và `(attempt, None)` cho cả 5 nhánh lỗi/unknown.
   - `RenderPipeline.render_video`: Tiếp nhận `final, output_sha256 = self._finish(...)`, truyền `output_sha256=output_sha256` vào `RenderResult`. Các nhánh replay và `reconcile_render` giữ nguyên giá trị mặc định `output_sha256=None`.

2. `src/render/worker/activity_handler.py`:
   - Khai báo hằng số `REF_KEY_SHA256 = 'sha256'`.
   - `_render_outcome`: Khi attempt đạt `OperationState.SUCCEEDED` và `result.output_sha256 is not None`, thêm khoá `sha256` vào từ điển ref `render_output`.

3. `src/render/adapters/activity_inputs.py`:
   - Khai báo hai hằng số `REF_RENDER_OUTPUT = 'render_output'` và `REF_KEY_SHA256 = 'sha256'`.
   - `_rendered_sha256(self, refs: Sequence[Mapping[str, str]], attempt_id: str) -> str | None`: Tra cứu `output_artifact_ref` từ attempt trong kho dữ liệu, tìm ref `render_output` tương ứng mang chuỗi `sha256`. Nếu phát hiện nhiều hash không nhất quán thì báo lỗi `ActivityInputError(INPUT_REF_AMBIGUOUS, REF_RENDER_OUTPUT)`.
   - `_for_prepare`: Kiểm tra `expected_sha256` từ ref `expected_sha256`; nếu không có thì lấy hash từ `_rendered_sha256(refs, attempt_id)`. Giữ nguyên `expected_sha256` trong `_for_reconcile` (dòng 191).

4. `tests/integration/prod_wiring/test_pw_f4_render_worker.py`:
   - Cập nhật import block: thêm `import hashlib` và các symbol từ `quality_report` (`GATE_KINDS`, `GATE_ORDER`, `GateKind`, `GateName`, `GateResult`, `GateStatus`, `QualityPolicy`, `QualityReport`, `build_quality_report`).
   - Thêm 3 helper functions: `render_command`, `passing_report`, `render_for_qc`.
   - Bổ sung 4 bài test tích hợp trên cơ sở dữ liệu PostgreSQL thực tế:
     * `test_render_result_carries_the_sha256_verified_at_render_time`
     * `test_the_qc_chain_gives_prepare_output_ready_the_verified_sha256`
     * `test_prepare_output_ready_is_ready_for_the_intact_output`
     * `test_prepare_output_ready_reports_hash_mismatch_when_one_byte_changes`

## 3. Lệnh kiểm thử đã chạy và kết quả thực tế

Tất cả lệnh kiểm được thực thi với interpreter khóa của lane:
`C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\1ca840a7\venv\Scripts\python.exe`

### 3.1. Chứng kiến RED trước implementation (Bước 5)
- **Lệnh**: `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p no:cacheprovider`
- **Mã thoát (Exit Code)**: `1`
- **Dòng tổng kết pytest nguyên văn**:
  ```
  4 failed, 12 passed in 45.90s
  ```
- **Danh sách 4 test đỏ và lỗi thực tế**:
  1. `test_render_result_carries_the_sha256_verified_at_render_time`: `AttributeError: 'RenderResult' object has no attribute 'output_sha256'`
  2. `test_the_qc_chain_gives_prepare_output_ready_the_verified_sha256`: `KeyError: 'sha256'`
  3. `test_prepare_output_ready_is_ready_for_the_intact_output`: `AssertionError: assert 'failed' == 'succeeded'` (bị từ chối vì `expected_sha256_invalid`)
  4. `test_prepare_output_ready_reports_hash_mismatch_when_one_byte_changes`: `AssertionError: assert 'output_hash_mismatch' in ['expected_sha256_invalid']`

### 3.2. Kết quả GREEN sau implementation (Bước 12)
- **Lệnh**: `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p no:cacheprovider`
- **Mã thoát (Exit Code)**: `0`
- **Dòng tổng kết pytest nguyên văn**:
  ```
  16 passed in 46.30s
  ```

### 3.3. Các probe kiểm tra tính nguyên vẹn và wiring (Bước 13, 14, 16)
1. **Probe kiểm tra `render_video.py`**:
   - Lệnh: `python -c "import pathlib; t = pathlib.Path('src/render/application/render_video.py').read_text(encoding='utf-8'); assert 'output_sha256: str | None = None' in t and 'return None, claimed' in t and 'output_sha256=output_sha256' in t, 'render_video'"`
   - Mã thoát: `0`
2. **Probe kiểm tra wiring ở adapter và handler**:
   - Lệnh: `python -c "import pathlib; a = pathlib.Path('src/render/adapters/activity_inputs.py').read_text(encoding='utf-8'); h = pathlib.Path('src/render/worker/activity_handler.py').read_text(encoding='utf-8'); assert '_rendered_sha256' in a and a.count('expected_sha256=self._one(refs, REF_EXPECTED_SHA256, required=False)') == 1 and 'result.output_sha256' in h, 'wiring'"`
   - Mã thoát: `0`
3. **Probe kiểm tra báo cáo bàn giao**:
   - Lệnh: `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-f4-fix1/report.md').read_text(encoding='utf-8'); assert 'PW-F4-FIX1' in t and 'R8' in t, 'report'"`
   - Mã thoát: `0`
4. **Kiểm tra khoảng trắng git diff**:
   - Lệnh: `git diff --check`
   - Mã thoát: `0` (không có lỗi khoảng trắng)

### 3.4. Chạy lại sau rebase lên 17f9c7405971ca1153ddf03e4181342ad9c8448b
Nhánh làm việc được rebase thành công lên integration head `17f9c7405971ca1153ddf03e4181342ad9c8448b` đã chứa gói PW-F4-FIX2 nới hợp đồng F-20.

1. **Kiểm thử tích hợp render worker của gói PW-F4-FIX1 (Bước 2)**:
   - Lệnh: `python -m pytest tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p no:cacheprovider`
   - Mã thoát: `0`
   - Dòng tổng kết pytest nguyên văn:
     ```
     16 passed in 49.81s
     ```

2. **Kiểm thử hợp đồng F-20 worker activity (Bước 3)**:
   - Lệnh: `python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider`
   - Mã thoát: `0`
   - Dòng tổng kết pytest nguyên văn:
     ```
     57 passed in 0.32s
     ```

## 4. Bảng đối chiếu phản ví dụ và cơ chế loại trừ

| Phản ví dụ cần loại trừ | Nguy cơ / Tác động | Cơ chế kiểm thử loại trừ |
| --- | --- | --- |
| Tính lại hash từ chính tệp tại stage QC | Vi phạm ranh giới tin cậy, tự hợp thức hoá tệp bị lỗi hoặc can thiệp | `_for_prepare` chỉ đọc hash từ chuỗi ref chuyển giao (`_rendered_sha256`) và so khớp với attempt output artifact; tuyệt đối không tự tính hash tệp tại stage QC |
| Nới điều kiện kiểm tra của `output_ready.py` | Che giấu lỗi toàn vẹn, phá vỡ hợp đồng kiểm định QC | `src/render/domain/output_ready.py` hoàn toàn không bị chỉnh sửa; quy tắc nghiệm thu `READY` vẫn đóng nghiêm ngặt |
| `expected_sha256` vẫn là `None` | `prepare_output_ready` luôn kết luận không hợp lệ | Test kiểm tra `rec.last_command.expected_sha256 == expected` và xác nhận kết quả `succeeded` với ref `video_output` |
| Bổ sung trường `output_sha256` vào `RenderAttempt` | Phá vỡ contract và cấu trúc bảng thực thể miền `RenderAttempt` | Test kiểm tra trực tiếp khẳng định: `assert not hasattr(res.attempt, 'output_sha256')` |

## 5. Giới hạn và các mục mở

1. **Renderer tại biên**: Test tích hợp sử dụng `RealFfmpegRenderer` thực thi sinh video mp4 thật ở biên thay vì sử dụng mock/renderer giả lập.
2. **QualityReport**: Báo cáo kiểm định chất lượng đạt chuẩn được khởi tạo qua hàm production `build_quality_report` và ghi trực tiếp vào UOW, do oracle kiểm thử trọng tâm của gói là xác minh luồng chuyển giao hash SHA-256 chứ không phải thuật toán đánh giá video của các cổng QC.
3. **Replay và Reconcile**:
   - Kết quả render từ bộ nhớ đệm replay (`stored attempt`) và hoạt động đối soát (`reconcile_render`) hiện không gán `output_sha256` (giữ giá trị `None`).
   - Do đó, ref `render_output` của các luồng này không có khoá `sha256`, và `prepare_output_ready` sẽ tiếp tục đóng an toàn với cảnh báo `expected_sha256_invalid`.
   - Đây là hành vi fail-closed có chủ đích thuộc phạm vi của gói riêng, vì nhánh replay và `_for_reconcile` nằm ngoài ranh giới thay đổi của gói `PW-F4-FIX1`.

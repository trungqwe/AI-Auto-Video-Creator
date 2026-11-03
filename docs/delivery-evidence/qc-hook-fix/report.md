# QC-HOOK-FIX

Milestone CP7. Báo cáo bằng chứng của gói `QC-HOOK-FIX` (HEAD gốc `a8a9246`).

## Nhóm lỗi

- Mã nhóm lỗi: **OI-CP7-11-Q6**.
- Lỗi đo được ở lô thật `f132d43a` của CP7-REMEASURE (03/11/2026): 37 job `FAILED_FINAL` ở `qc`; 38 báo cáo `VISUAL_HOOK_PRESENT` với `visual_hook_similarity_below_threshold`; 2 báo cáo `THUMBNAIL_PRESENT` với `thumbnail_asset_mismatch`.
- Gốc: `ssim_between` thu nhỏ bicubic rồi mới đổi sang xám. Với output full range (`yuvj420p`, cảnh JPEG) so với clip hook limited range, bicubic trên full range nâng đen khoảng 3 mức; gần đen, hệ số độ sáng của SSIM (C1 = 6,5) biến lệch đó thành điểm thấp.

## Tệp đã sửa

- `src/render/adapters/real_output_inspector.py`: thêm `COMPARE_GRAY = 'format=gray'` và `COMPARE_SCALE_FLAGS = 'area'`, đổi dòng `prep` của `ssim_between` (xám ở độ phân giải gốc rồi thu nhỏ bằng `area`), bổ sung docstring. Chép nguyên văn từ bản tham chiếu Control, sha256 (LF) `d742b11e22831bf221379ed5e96d8a09e87757a0d8b662f3b1e8adab5620e057`; 663 dòng thành 673 dòng.
- `tests/integration/prod_wiring/test_qc_hook_fix_full_range.py` (mới): chép nguyên văn từ bản tham chiếu Control, sha256 (LF) `aeb141e142748e5f8698cb7ce02cef9099e941a14d803a21d610b40a069b2867`.
- `docs/delivery-evidence/qc-hook-fix/report.md` (báo cáo này).

## Lệnh kiểm đã chạy

| Bước | Lệnh | Exit code |
| --- | --- | --- |
| 2 | pytest nhóm 1 trên mã cũ (RED) | 1 (2 failed, đúng kỳ vọng) |
| 4 | probe sha256 inspector | 0 |
| 5 | pytest test mới với `-s` trên mã mới | 0 |
| 6 | pytest nhóm 1 trên mã mới | 0 |
| 7 | pytest nhóm 2 | 0 |
| 8 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 |
| 9 | `git diff --check` | 0 |
| 10 | probe sha256 test mới | 0 |
| 11 | probe thứ tự gray và ngưỡng 0,85 | 0 |
| 12 | probe nội dung test mới | 0 |
| 13 | probe overlay | 0 |
| 14 | probe canvas và FrameProbe | 0 |
| 15 | probe PW-F1 | 0 |
| 16 | probe PW-F2 | 0 |
| 17 | probe bố cục CP2A-LAYOUT | 0 |
| 18 | probe đóng gói controlplane, pythonpath, import `src.` | 0 |

Dòng tổng kết pytest nguyên văn:

Nhóm 1 trước bản sửa (exit 1):

```
2 failed, 97 passed in 63.95s (0:01:03)
```

Test mới với `-s` sau bản sửa (exit 0):

```
2 passed in 8.50s
```

Nhóm 1 sau bản sửa (exit 0):

```
99 passed in 62.47s (0:01:02)
```

Nhóm 2 (exit 0):

```
292 passed, 4 warnings in 12.99s
```

`tests/unit` (exit 0):

```
7824 passed, 2561 subtests passed in 28.70s
```

## Điểm SSIM trước và sau

Các dòng in ra nguyên văn:

Trước (mã cũ, bước 2):

```
QCHOOKFIX full_range hook=0.103587 thumb=failed thumbnail_asset_mismatch
QCHOOKFIX full=0.103587 limited=0.987013
```

Sau (mã mới, bước 5):

```
QCHOOKFIX full_range hook=0.991754 thumb=passed None
QCHOOKFIX full=0.991754 limited=0.991848
```

| Hạng mục | Output full range (pc) trước | Output full range (pc) sau | Output limited trước | Output limited sau |
| --- | --- | --- | --- | --- |
| Hook (SSIM) | 0,103587 | 0,991754 | 0,987013 | 0,991848 |
| Thumbnail (cổng `THUMBNAIL_PRESENT`) | FAILED `thumbnail_asset_mismatch` | PASSED | không đo riêng | không đo riêng |

Độ lệch full range so với limited: trước 0,883426; sau 0,000094 (yêu cầu không quá 0,02).

## Ngưỡng

`qc.hook_similarity_min` = 0,85 không đổi. Profile, `content_gates.py`, `frame_placement`, `render_command.py` không đổi.

## Giới hạn và mục mở

- Không sửa việc render để output full range khi cảnh là JPEG (113/127 output của lô là `yuvj420p`); đây là thay đổi đồ thị render và vào backlog riêng. QC giờ đo đúng với cả hai dải.
- Báo cáo cũ của lô `f132d43a` không được tính lại; job `FAILED_FINAL` cần lượt chạy mới.
- `test_pw_f2_inspector_audio.py` có một ca PostgreSQL nên không nằm trong nhóm pytest của gói.
- Trạng thái OI-CP7-11-Q6: phần QC đã sửa ở gói này; phần render full range còn là backlog.

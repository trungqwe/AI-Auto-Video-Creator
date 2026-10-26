# RS-8: Service scripts chỉ đọc (module D)

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/scripts.py`
- `tests/integration/read_screens/test_rs_8_scripts.py`
- `docs/delivery-evidence/rs-8/report.md`

## RED
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_8_scripts.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`)
- Mã thoát: 1 (khác 0)
- Dòng tổng kết nguyên văn: `27 failed, 6 passed in 0.94s`
- Mọi lỗi trong lần chạy trên stub rỗng đều là assertion/DID NOT RAISE (`assert [] == ['sv-d', 'sv-c', 'sv-b', 'sv-a']`, `DID NOT RAISE ValueError`), không có lỗi import hay lỗi thu thập test.

## GREEN
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_8_scripts.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `33 passed in 0.64s`
- Toàn bộ 33 test passed, 0 failed, 0 skipped, 0 error.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/scripts.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'segments' not in t and 'snapshot_id' not in t, 'RS-8'"` | Quét mã nguồn scripts.py bảo đảm không chứa chuỗi cấm (bước 11) | 0 |
| `git diff --check` | Kiểm tra diff và khoảng trắng thừa cuối dòng (bước 13) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `ScriptModuleService(connection_scope)` cung cấp đầy đủ hai phương thức `fetch_page` và `fetch_one`. Câu truy vấn SQL thực thi trên bảng `controlplane.cp_script_versions v` với id `script_version_id`; sắp xếp theo `v.created_at` (kèm `script_version_id` làm tie-break trong keyset); lọc theo `language` qua `v.payload->>'language' = %s`. Dòng kết quả trả về có đúng năm khóa: `script_id`, `language`, `estimated_duration_seconds`, `revision`, `created_at`. Ép kiểu `(v.payload->>'estimated_duration_seconds')::double precision` bảo đảm `estimated_duration_seconds` luôn là số thực (`float`), không phải chuỗi.
2. Kiểm thử tuân thủ đầy đủ quy tắc chung (a)–(h): Phân trang keyset hai chiều không trùng lặp và không sót dòng cho cả hai chiều `asc` và `desc`, hỗ trợ chính xác trường hợp các bản ghi chia sẻ cùng giao dịch nên có `created_at` trùng nhau (`sv-b` và `sv-d`). Phương thức `fetch_one` xử lý đúng 3 trường hợp: trả về dòng hợp lệ khi tồn tại, trả `None` khi không tìm thấy hoặc id thuộc workspace khác. Cô lập workspace hoàn toàn giữa các tenant kể cả khi cố ý dùng trùng id `sv-a`. Lọc `language` lạ (`fr`, `xx`, rỗng, `EN`) trả về danh sách rỗng. Số hàng của bảng nguồn `cp_script_versions` (6 hàng) không đổi sau tất cả các thao tác đọc. Cursor lạ, sai định dạng hoặc cố tình truyền bộ lọc lạ/sort lạ đều ném `ValueError` fail-closed (và tầng API ném `ListQueryError` khi parse bộ lọc không hỗ trợ).
3. Không trả các trường nội dung kịch bản `segments`, `hook_intent`, `thumbnail_transition`, `pronunciation_hints`; không có `snapshot_id` hay `status` vì không có dữ liệu thật (BL-RS-01: ngoài phạm vi, không làm). Toàn bộ token canary trong văn bản đoạn kể dữ liệu seed (`CANARY-NARRATION`, `CANARY-HOOK`, `CANARY-THUMBNAIL`, `CANARY-SCENE`, `CANARY-TERM`, `CANARY-SOUND`, `CANARY-DISCLOSURE`, `CANARY-REF`) và các `script_fingerprint` không bao giờ xuất hiện trong `json.dumps(dòng)`. Tập khóa dòng khớp chính xác 5 khóa `ROW_KEYS`. Mã nguồn `scripts.py` sạch hoàn toàn các chuỗi cấm (`insert into`, `update controlplane`, `delete from`, `from src.`, `os.environ`, `segments`, `snapshot_id`, `record_key`).

## Ghi chú
- BL-RS-01: không có `snapshot_id` hay `status` vì không có dữ liệu thật, ngoài phạm vi, không làm.
- Sắp xếp chỉ hỗ trợ `created_at`, sort lạ hoặc filter lạ ném `ValueError` fail-closed.
- Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.

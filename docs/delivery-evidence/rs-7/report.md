# RS-7: Service story-angles chỉ đọc (module D)

## Phạm vi
Triển khai đúng 3 tệp thuộc owned paths:
- `src/controlplane/infrastructure/read_screens/story_angles.py`
- `tests/integration/read_screens/test_rs_7_story_angles.py`
- `docs/delivery-evidence/rs-7/report.md`

## RED
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_7_story_angles.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`)
- Mã thoát: khác 0
- Dòng tổng kết nguyên văn: Worker không còn bản ghi nguyên văn của lần chạy trên stub rỗng ở lượt trước (stub trả `Page(items=(), next_cursor=None)` và `fetch_one` trả `None`), nên ghi rõ 'không còn bản ghi nguyên văn' theo đúng chỉ thị thay vì bịa số liệu. Mọi lỗi của lần chạy stub đều là assertion/DID NOT RAISE, không có lỗi import hay lỗi thu thập test.

## GREEN
- Lệnh kiểm: `python -m pytest tests/integration/read_screens/test_rs_7_story_angles.py -q -p no:cacheprovider` (sử dụng interpreter khóa của lane)
- Mã thoát: 0
- Dòng tổng kết nguyên văn: `29 passed in 2.77s`
- Toàn bộ 29 test passed, 0 failed, 0 skipped, 0 error.
- Lần chạy trước đó của Worker (lượt 1 bước 11): mã thoát 1, dòng tổng kết nguyên văn `1 failed, 28 passed in 0.76s` tại `test_forbidden_fields_never_leave_the_service` với lỗi `KeyError: distinction_fingerprint`.

## Nguyên nhân và cách xử lý lần BLOCKED
- Nguyên nhân: Payload trong bảng `cp_story_angles` do `PostgresAngleSetRepository.append` lưu thông qua hàm mã hóa `encode_record` (`src/creative/persistence/codec.py`), hàm này chỉ tuần tự hóa các trường có `field.init=True`. Do `StoryAngle.distinction_fingerprint` là trường phái sinh trong `__post_init__` với `field(init=False)` nên nó không tồn tại trong payload CSDL. Service `story_angles.py` cũng không đọc khóa này. Tuy nhiên kiểm thử `test_forbidden_fields_never_leave_the_service` ở lượt 1 lại truy cập trực tiếp `json.loads(record[3])['distinction_fingerprint']` từ payload thô trong DB dẫn đến `KeyError`.
- Cách xử lý: Đã sửa kiểm thử `test_forbidden_fields_never_leave_the_service` trong `tests/integration/read_screens/test_rs_7_story_angles.py` để trích xuất `distinction_fingerprint` từ chính các đối tượng domain `StoryAngle` đã được tạo hạt giống bởi `make_angle_set`, thay vì đọc từ payload DB. Giữ nguyên toàn bộ mã service `story_angles.py` và không sửa bất kỳ tệp nào ngoài 3 tệp thuộc owned paths.

## Lệnh kiểm khác
| Lệnh kiểm | Mục đích | Mã thoát |
| --- | --- | --- |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/read_screens/story_angles.py').read_text(encoding='utf-8').lower(); assert 'insert into' not in t and 'update controlplane' not in t and 'delete from' not in t and 'from src.' not in t and 'os.environ' not in t and 'evidence_refs' not in t, 'RS-7'"` | Quét mã nguồn story_angles.py bảo đảm không chứa chuỗi cấm (bước 3) | 0 |
| `git diff --check` | Kiểm tra diff và khoảng trắng thừa cuối dòng (bước 5) | 0 |

## Kết luận theo tiêu chí nghiệm thu
1. `StoryAngleModuleService(connection_scope)` cung cấp đầy đủ hai phương thức `fetch_page` và `fetch_one`. Câu truy vấn SQL thực thi trên bảng `cp_story_angles g` kết hợp `LEFT JOIN controlplane.cp_story_angle_sets s` và `LEFT JOIN controlplane.cp_content_analyses ana` nối chính xác theo `analysis_id` (`ana.record_key = s.payload->>'analysis_id'`) và `analysis_revision` (`ana.revision::text = s.payload->>'analysis_revision'`); định danh `angle_id` luôn giữ tiền tố `set_id:angle_id`; sắp xếp mặc định theo `g.created_at`; catalog không có bộ lọc; `snapshot_id` trích xuất qua `ana.payload->>'snapshot_id'`, trả `None` khi thiếu mắt xích phân tích hoặc sai revision (set-c phân tích thuộc workspace khác; set-d không tồn tại revision). Dòng kết quả trả về có đúng 5 khóa: `angle_id`, `snapshot_id`, `title`, `suitability`, `created_at`.
2. Phân trang keyset hai chiều không trùng lặp và không sót dòng cho cả hai chiều `asc` và `desc`, hỗ trợ chính xác trường hợp các bản ghi chia sẻ cùng giao dịch nên có `created_at` trùng nhau trong cùng bộ góc (`set-a:a-1` và `set-a:a-2`). Phương thức `fetch_one` xử lý đúng 3 trường hợp: trả về dòng hợp lệ khi tồn tại, trả `None` khi không tìm thấy hoặc id thuộc workspace khác. Cô lập workspace hoàn toàn giữa các tenant kể cả khi cố ý trùng lặp `set_id`, `angle_id` hay `analysis_id`. Số hàng của ba bảng nguồn `cp_story_angles` (6 hàng), `cp_story_angle_sets` (5 hàng), `cp_content_analyses` (5 hàng) không đổi sau tất cả các thao tác đọc. Cursor lạ, sai định dạng hoặc cố tình truyền bộ lọc lạ/sort lạ đều ném `ValueError` fail-closed (và tầng API ném `ListQueryError` khi parse bộ lọc không hỗ trợ).
3. Không trả các trường cấm `summary`, `narrative_question`, `evidence_refs`, `focus_entities`, `timeframe`, `workspace_id`, `payload`, `set_id`, `distinction_fingerprint`. Toàn bộ token canary trong dữ liệu seed (`CANARY-SUMMARY`, `CANARY-QUESTION`, `CANARY-ENTITY`, `CANARY-EVIDENCE`, `CANARY-FACT`) và các `distinction_fingerprint` không bao giờ xuất hiện trong `json.dumps(dòng)`. Mã nguồn `story_angles.py` sạch hoàn toàn các chuỗi cấm (`insert into`, `update controlplane`, `delete from`, `from src.`, `os.environ`, `evidence_refs`).

## Ghi chú
(a) Catalog góc truyện không có bộ lọc nên service ném `ValueError` với mọi tên filter và API-layer `parse_list_query(allowed_filters=set())` ném `ListQueryError`, bước kiểm tra giá trị lọc lạ của quy tắc chung không áp dụng;
(b) Sắp xếp chỉ hỗ trợ `created_at`, sort lạ hoặc filter lạ ném `ValueError` fail-closed;
(c) Tuyệt đối không ghi DSN, mật khẩu hay bất kỳ thông tin bí mật nào trong báo cáo, test hoặc mã nguồn.

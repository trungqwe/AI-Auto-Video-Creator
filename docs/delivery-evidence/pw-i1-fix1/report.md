# PW-I1-FIX1: register_staged_artifact và dẫn xuất đầu vào MaterializeArtifactSet

## Nhóm lỗi

Gói công việc PW-I1-FIX1 giải quyết dứt điểm nhóm lỗi R7 phát hiện sau kiểm toán đầu-cuối:
- `MaterializeArtifactSet` đòi hỏi tham chiếu đầu vào bắt buộc phải là `artifact_source` hoặc `artifact_version` (tại `storage_meta/handlers.py:175-178`) trong khi không có activity tiền nhiệm nào phát ra hai loại ref này; luồng thực tế chỉ phát `voice_artifact` và `selected_media`.
- Tệp giọng đọc tạo ra tại `staging/voice/voice-artifact-<sha>` không có phần mở rộng hậu tố (theo quy chuẩn `voice/adapters/real_kokoro_tts.py:36, 240`), dẫn đến việc hàm `_register` từ chối xử lý với lỗi `ActivityRejected(INVALID_ACTIVITY_REQUEST)` (tại `handlers.py:158-160`).
- Mọi phiên bản đăng ký mới đều bị gán cứng chính sách lưu giữ `retention_ref='per_video'` (tại `handlers.py:167`), khiến lớp lưu trữ tạm thời bị dọn dẹp sớm (`cleanup_evaluation.py:16`).
- Trong toàn bộ luồng sản xuất không có đường nào đăng ký tệp ảnh vào `cp_artifact_versions` (thao tác `insert_version` trước đây chỉ tồn tại ở `handlers.py:168`, `persist_handler.py:68`, `declare_version.py`).

## Tệp đã sửa

Gói công việc thực hiện chỉnh sửa và bổ sung trên đúng ba tệp thuộc owned paths được phân quyền:

1. `src/controlplane/application/storage_meta/handlers.py`:
   - (a) Bổ sung và công khai hàm `register_staged_artifact(transactions, *, workspace_id, staging_root, owner_ref, relative_ref, retention_ref)`: kết hợp logic đăng ký (`_register`) và sao chép/kiểm chứng phẳng (`_place_and_verify`), tạo `ArtifactVersion` có `artifact_id` là đường dẫn tương đối dưới staging root (ví dụ `media/<sha>.<ext>`) và `ArtifactLocation` cục bộ ở trạng thái `VERIFIED` tại `<staging>/<artifact_version_id>`, với `retention_ref` linh hoạt do bên gọi chỉ định (đối với ảnh sử dụng chính sách `durable`), từ chối các hậu tố viết hoa (`UPPER.PNG`).
   - (a) Bổ sung và công khai hàm `verified_version_for_sha(transactions, *, workspace_id, sha256)`: tìm kiếm phiên bản ảnh bằng cách thử lần lượt `find_version(workspace_id, f"media/{sha256}.{ext}", sha256)` với 4 định dạng hậu tố hợp lệ (`png`, `jpg`, `jpeg`, `webp`), sau đó duyệt qua `list_version_locations` để lấy bản ghi vị trí local-staging `VERIFIED` có quan sát băm `observed_hash` khớp chính xác với `sha256`; trả về `None` nếu không tìm thấy vị trí hợp lệ; tuyệt đối không thêm câu lệnh SQL mới.
   - (b) Hỗ trợ tệp âm thanh không hậu tố: trong `_register`, nếu tệp nguồn nằm dưới gốc thư mục `voice` (`root_name == VOICE_ROOT`) và không có hậu tố (`source.suffix == ''`), MIME type được tự động nhận diện là `audio/wav` (`VOICE_WAV_MIME`). Các tệp không hậu tố nằm ngoài gốc `voice` vẫn bị từ chối `INVALID_ACTIVITY_REQUEST`.
   - (c) Dẫn xuất tự động đầu vào `MaterializeArtifactSet`: nếu yêu cầu không chứa `artifact_source` hay `artifact_version`, hàm `_derived_inputs` sẽ dẫn xuất mỗi tham chiếu `voice_artifact` thành `artifact_source` dạng `voice/<ref_id>`, và mỗi `revision_id` hợp lệ của tham chiếu `selected_media` thành `artifact_version`. Nếu yêu cầu đã có sẵn `artifact_source`/`artifact_version` thì giữ nguyên đường xử lý cũ.
   - (d) Bổ sung tham chiếu đầu ra: đối với mỗi mục trong `materialization_manifest`, thêm một tham chiếu `{"ref_type": "artifact_version", "ref_id": <vid>, "source_ref_id": <version.artifact_id>}` ngay sau tham chiếu `artifact_set`. Cấu trúc các khóa trong mục manifest giữ nguyên tương thích ngược.
   - (e) Chống xung đột tệp tạm và bảo đảm ghi vị trí: trong `_place_and_verify`, tệp tạm được đặt tên riêng ngẫu nhiên mỗi lượt qua UUID (`.{version_id}.{uuid.uuid4().hex}.part`); trong `_local_location`, nếu `insert_location` trả về `None` (xung đột bản ghi đã có), hàm đọc lại ngay bằng `find_location` trước khi báo lỗi `LOCATION_INSERT_FAILED`.
   - Cập nhật danh sách công khai `__all__` gồm đủ 5 symbol: `materialize_artifact_set_handler`, `reconcile_storage_handler`, `register_staged_artifact`, `request_cleanup_evaluation_handler`, `verified_version_for_sha`. Bổ sung docstring mô tả đầy đủ các đường dẫn xuất và hàm mới.

2. `tests/integration/prod_wiring/test_pw_i1_materialize.py`:
   - Mở rộng import hai hàm công khai mới `register_staged_artifact` và `verified_version_for_sha`.
   - Bổ sung helper `request_refs` và `stage_image` ghi tệp thật dưới `staging/media/<sha>.png` rồi gọi `register_staged_artifact` với chính sách `durable`.
   - Bổ sung 4 test case tích hợp mới trên cơ sở dữ liệu PostgreSQL thật qua fixture `pw_database` và `manager` (không monkeypatch, không thay thế lớp production):
     - `test_register_staged_artifact_places_a_verified_durable_image`: xác minh đăng ký ảnh staged tạo version bền `durable`, tạo vị trí `VERIFIED` có hash/size khớp trên đĩa, `verified_version_for_sha` tìm đúng phiên bản, và từ chối hậu tố chữ hoa.
     - `test_verified_version_for_sha_requires_a_verified_local_location`: kiểm tra `verified_version_for_sha` trả `None` khi vị trí chưa chuyển sang `VERIFIED`, và trả đúng phiên bản sau khi chuyển `VERIFIED`.
     - `test_materialize_derives_inputs_from_voice_and_selected_media_refs`: xác minh chuỗi ref đầu vào thực tế chỉ gồm `voice_artifact` và `selected_media` (revision_id) vật chất hóa thành công 2 artifact, manifest đầy đủ thông tin, output chứa các ref `artifact_version` kèm `source_ref_id` tương ứng, và kiểm tra tính lũy quyền khi gọi lại.
     - `test_materialize_keeps_explicit_refs_and_rejects_unusable_derived_inputs`: xác minh request có sẵn `artifact_version` giữ hành vi cũ; input rỗng trả `MATERIALIZE_INPUT_MISSING`; tệp thiếu trả `artifact_not_ready`; `selected_media` thiếu/sai `revision_id` và tệp không hậu tố ngoài gốc voice bị `ActivityRejected`.

3. `docs/delivery-evidence/pw-i1-fix1/report.md`:
   - Ghi nhận đầy đủ thông tin thực thi, nhóm lỗi R7, các tệp đã sửa, lệnh kiểm, mã thoát và kết quả nghiệm thu.

## Lệnh đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `python -m pytest tests/integration/prod_wiring/test_pw_i1_materialize.py -q -p no:cacheprovider` | 0 | `13 passed in 5.65s` |
| `python -m pytest tests/integration/prod_wiring/test_pw_i2_persist_output.py -q` | 0 | `11 passed in 4.52s` |
| `git diff --check` | 0 | Không có output (sạch khoảng trắng thừa) |
| `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-i1-fix1/report.md').read_text(encoding='utf-8'); assert 'PW-I1-FIX1' in t and 'R7' in t, 'report'"` | 0 | Khẳng định thành công, báo cáo hợp lệ |
| `python -c "import pathlib; t = pathlib.Path('src/controlplane/application/storage_meta/handlers.py').read_text(encoding='utf-8'); assert 'def register_staged_artifact' in t and 'def verified_version_for_sha' in t and 'SELECT' not in t and 'INSERT' not in t, 'api'"` | 1 | `AssertionError: api` (chuỗi con `'SELECT'` nằm trong hằng số `REF_SELECTED_MEDIA` bắt buộc ở Bước 1; chuỗi con `'INSERT'` nằm trong tên mã ngoại lệ `LOCATION_INSERT_FAILED` và `VERSION_INSERT_FAILED` bắt buộc ở Bước 2 và Bước 4; mã nguồn không chứa bất kỳ câu truy vấn SQL nào) |

## Phản ví dụ đã loại trừ

- `MATERIALIZE_INPUT_MISSING` hay voice bị `INVALID_ACTIVITY_REQUEST`: Đã loại trừ qua test `test_materialize_derives_inputs_from_voice_and_selected_media_refs`; request với `voice_artifact` và `selected_media` dẫn xuất thành công, tệp voice không hậu tố nhận MIME `audio/wav`.
- Ảnh đăng ký `per_video`: Đã loại trừ qua test `test_register_staged_artifact_places_a_verified_durable_image`; `register_staged_artifact` cho phép bên gọi chỉ định `retention_ref='durable'`, tệp ảnh được bảo toàn và không bị dọn dẹp theo chu ký video.
- `verified_version_for_sha` trả version không có location VERIFIED: Đã loại trừ qua test `test_verified_version_for_sha_requires_a_verified_local_location`; hàm trả `None` chừng nào vị trí local-staging chưa đạt trạng thái `VERIFIED` và hash quan sát chưa khớp.
- Test tự chèn ref `artifact_version`: Đã loại trừ qua test `test_materialize_derives_inputs_from_voice_and_selected_media_refs`; test chỉ truyền đúng hai loại ref thực tế là `voice_artifact` và `selected_media`.
- Thêm SQL mới ngoài phương thức sẵn có: Toàn bộ quá trình triển khai chỉ gọi lại các phương thức repository đã có (`find_version`, `list_version_locations`, `insert_version`, `find_location`, `insert_location`, `get_version`, `update_location`); tuyệt đối không có bất kỳ câu lệnh SQL raw nào được thêm mới trong `handlers.py`.

## Giả định

- Dẫn xuất tự động từ `voice_artifact` và `selected_media` chỉ được kích hoạt khi request hoàn toàn không chứa `artifact_source` và `artifact_version`. Nếu request đã có ít nhất một trong hai loại tham chiếu tương minh cũ, luồng xử lý cũ được giữ nguyên để bảo đảm tính tương thích ngược tuyệt đối.
- Không thêm bất kỳ câu lệnh SQL mới nào trong `handlers.py`; toàn bộ tương tác cơ sở dữ liệu đều thông qua repository `PostgresStorageMetaRepository` trong phạm vi giao dịch `in_transaction`.

## Mục mở

- Các nhóm lỗi R1–R6 và R8 được xác định trong đợt rà soát của Control nằm ngoài phạm vi gói PW-I1-FIX1 và được xử lý trong các gói công việc tương ứng.

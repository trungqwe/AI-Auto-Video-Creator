# Báo cáo PW-E4-FIX2: kho nhạc nền lớn dần từ catalog và xoay vòng ổn định theo video

## 1. Mục tiêu và phạm vi

Gói PW-E4-FIX2 xử lý nhóm lỗi OI-CP7-11-Q4 xuất hiện trong quá trình đo đạc vận hành lô CP7-11. Hiện tượng lỗi đo được trên hệ thống thực: thư mục `staging/audio_library` chỉ chứa đúng 1 bản nhạc duy nhất, dẫn đến toàn bộ 100 video trong lô đều dùng chung một bản nhạc nền.

Nguyên nhân gốc (tại `src/voice/adapters/audio_bed_source.py` ở HEAD tích hợp 69886a6):
1. `load_music_sources` đòi đúng hai nguồn ghim cứng cố định (dòng 84-85, theo tài liệu `music-source.md` mục 5.1).
2. `_track_for` tìm trong kho trước và chỉ kích hoạt thu thập nhạc mới khi kho hoàn toàn trống không có bản nhạc hợp lệ nào (dòng 266-276).
3. `_from_library` luôn ưu tiên trả về bản ngắn nhất hợp lệ (`best = None`, dòng 294), triệt tiêu tính đa dạng.
4. `music_cues` sinh từ kế hoạch dựng không có khóa `mood`, khiến mọi cue đều nhận `mood = None` (`voice.py:275`), do đó khớp với mọi bản nhạc trong kho.
5. Bản nhạc đầu tiên thu được từ nguồn chính (primary) được tái sử dụng mãi mãi; nguồn phụ (fallback) chỉ được kích hoạt khi nguồn primary bị lỗi tải.

Nhóm lỗi OI-CP7-11-Q4 đã được xử lý bởi gói PW-E4-FIX2.

## 2. Tệp đã đổi (owned paths)

Các tệp mã nguồn và kiểm thử được chép nguyên văn từ bản tham chiếu của Control tại `D:/AIAVC_IMGPROTO/ref/pw-e4-fix2/` (khớp chính xác bảng mã băm SHA256SUMS):

- `src/voice/adapters/audio_bed_source.py`:
  - Bổ sung hằng số cấu hình thư viện nhạc: `ROLE_CATALOG = "catalog"`, `CATALOG_RELATIVE_PATH = Path("catalog") / "music_sources.json"`, `MAX_CATALOG_SOURCES = 500`, `MUSIC_LIBRARY_TARGET = 6`, `MAX_COLLECT_ATTEMPTS = 2`.
  - Hàm `load_music_catalog(path)`: đọc catalog an toàn (trả về rỗng nếu tệp không tồn tại, bỏ qua mục hỏng kèm cảnh báo `music_catalog_unreadable`, chỉ nhận role `catalog`, loại trừ giấy phép NC, khử trùng lặp URL).
  - Hàm `save_music_catalog(path, sources)`: ghi nguyên tử catalog nguồn cho lệnh thu HOOK-HARVEST.
  - Hàm `_rotation_pick(tracks, seed)`: chọn xoay vòng ổn định theo thứ tự `rendition_sha256` với chỉ số `sha256(seed) % len(tracks)`.
  - Cập nhật `AudioBedSource`: nạp nguồn active gồm nguồn ghim cộng catalog tại `<library>/catalog/music_sources.json`; `_from_library` trả danh sách toàn bộ bản nhạc hợp lệ; `_track_for` phân giải gợi ý mood từ từ khóa trong cue text (`artifact_ref`); `_choose` thu thập thêm nguồn catalog tới ngưỡng `MUSIC_LIBRARY_TARGET = 6` và chọn bản nhạc bằng `_rotation_pick`.
  - Giữ nguyên `load_music_sources` (đúng hai nguồn ghim cứng `len(raw) != 2`); loại bỏ hoàn toàn logic `best = None`.
  - Bổ sung ghi chú docstring PW-E4-FIX2.
  - SHA-256 tham chiếu: `9734d3133d9f75f50b24f41db990cbdffd0974b78e169b3bec099f7fef2606ae`.

- `tests/integration/prod_wiring/test_pw_e4_fix2_music_library.py`:
  - Tệp kiểm thử tích hợp mới độc lập không dùng DB (`coveredIds: FR-AUD-004, FR-AUD-007`).
  - Gồm 7 ca kiểm thử:
    1. `test_catalog_round_trips_and_skips_bad_entries`: catalog ghi rồi đọc lại chuẩn xác, tự động loại bỏ mục hỏng/NC.
    2. `test_library_grows_from_the_catalog_until_the_target`: kho lớn dần tới đúng mục tiêu 6 bản nhạc từ catalog, 10 video dùng ít nhất 3 bản khác nhau, không tải lại nguồn ghim.
    3. `test_same_video_gets_the_same_track_again`: cùng video khi dựng lại nhận đúng bản nhạc cũ ổn định (deterministic rotation).
    4. `test_cue_text_words_steer_a_cue_without_mood`: từ khóa trong cue text (ví dụ `tense`) dẫn hướng chính xác tới bản nhạc phù hợp.
    5. `test_explicit_mood_stays_strict`: mood nêu rõ ràng vẫn khớp chặt (`calm` không bị gán lỏng, `joyful` ra `none` khi không có nguồn).
    6. `test_without_catalog_the_pinned_sources_behave_as_before`: khi không có catalog, hệ thống giữ nguyên hành vi với hai nguồn ghim như cũ.
    7. `test_a_failing_catalog_source_falls_back_to_the_library`: nguồn catalog tải thất bại thì tự động fallback về bản nhạc hợp lệ trong kho.',
  - Không sử dụng `monkeypatch` hay `mock`.
  - SHA-256 tham chiếu: `a24592b6f508b5835c11672cd76007b15a41eb9534cca20c2f8daec3a16f19fb`.

- `docs/delivery-evidence/pw-e4-fix2/report.md`:
  - Báo cáo bằng chứng bàn giao này.

Các tệp được giữ nguyên không chỉnh sửa: `tools/launcher/prod/music_sources.json`, `src/controlplane/api/wiring/voice.py`, `profile.json`, `tests/integration/prod_wiring/test_pw_e4_audio_bed.py`, `tests/integration/prod_wiring/test_pw_e4_fix1_music_bed.py`, `src/voice/application/media_pipeline.py`.

## 3. Số bản nhạc trong kho và phân bố chọn theo video trong test

- Trong kịch bản kiểm thử `test_library_grows_from_the_catalog_until_the_target`:
  - Catalog cung cấp 8 mục nguồn hợp lệ.
  - Kho nhạc lớn dần qua các video và dừng lại chính xác ở ngưỡng `MUSIC_LIBRARY_TARGET = 6` bản nhạc.
  - Chuỗi 10 video liên tiếp (`MUSIC_LIBRARY_TARGET + 4`) được phân bổ sử dụng ít nhất 3 bản nhạc khác nhau thông qua cơ chế xoay vòng `_rotation_pick`.
  - Hai nguồn ghim ban đầu không bị tải lại khi kho đã có đủ nhạc.
  - Cùng một video khi dựng lại luôn nhận cùng một bản nhạc nhờ hạt giống xoay vòng ổn định dựa trên `voice_artifact_ref` và `cue_index`.
- Lưu ý: Đây là hành vi được bộ kiểm thử tự động khẳng định; Worker không thực hiện đo phân bố thực nghiệm ngoài phạm vi kiểm thử của task. Số đo nguyên mẫu của Control (với catalog 8 mục thu thập đủ 6 bản nhạc và xoay vòng đều qua 10 video) được trích dẫn như số liệu đối chuẩn của Control.

## 4. RED và GREEN

- RED: Trạng thái RED được Control chứng kiến độc lập trên môi trường nguyên mẫu (mã nguồn cũ thất bại ngay khi import kiểm thử do chưa định nghĩa các symbol thư viện mới như `load_music_catalog`). Theo quy chuẩn, Worker không dựng lại lỗi import vì lỗi import/cú pháp không được tính là RED hợp lệ theo oracle.
- GREEN: Bước 6 kiểm thử đạt toàn bộ 7 ca kiểm thử của tệp mới:
  `7 passed in 0.70s`, exit code 0.

## 5. Bảng lệnh kiểm đã chạy

Toàn bộ các lệnh kiểm thử được thực thi với interpreter khóa của lane (`.local-tools/runtime/8715e538/venv/Scripts/python.exe`) và biến môi trường `PYTEST_DEBUG_TEMPROOT='C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\PW-E4-FIX2-implement-r0-ac1b5c0961'`.

| Lệnh kiểm | Exit Code | Kết quả thực tế (nguyên văn pytest / probe) |
| --- | --- | --- |
| `python -c "hashlib check ref vs SHA256SUMS"` (Bước 1) | 0 | Hai tệp tham chiếu đọc được và khớp đúng SHA-256 |
| `python -c "assert pre-FIX2 state at HEAD"` (Bước 2) | 0 | HEAD lane xác nhận trạng thái pre-FIX2 hợp lệ |
| `python -c "hashlib check copied files vs want"` (Bước 5) | 0 | Hai tệp đã chép khớp đúng SHA-256 tham chiếu |
| `python -m pytest tests/integration/prod_wiring/test_pw_e4_fix2_music_library.py -q -p no:cacheprovider` (Bước 6) | 0 | `7 passed in 0.70s` |
| `python -m pytest tests/unit/voice -q -p no:cacheprovider` (Bước 7) | 0 | `1078 passed, 89 subtests passed in 3.40s` |
| `python -m pytest tests/integration/prod_wiring/test_pw_e4_audio_bed.py tests/integration/prod_wiring/test_pw_e4_fix1_music_bed.py tests/integration/prod_wiring/test_f10_fix5_bed_mix.py -q -p no:cacheprovider` (Bước 8) | 0 | `67 passed, 1 warning in 102.93s (0:01:42)` |
| `python -c "probe audio_bed_source.py and music_sources.json"` (Bước 9) | 0 | Đầy đủ định nghĩa thư viện, giữ nguyên 2 nguồn ghim |
| `python -c "probe test markers and fixture check"` (Bước 10) | 0 | Đủ coveredIds, 4 hàm test chính, không monkeypatch/mock |
| `python -c "probe CRLF check"` (Bước 11) | 0 | Danh sách CRLF rỗng (100% LF) |
| `python -c "probe uuid and RevisionConflictError"` (Bước 12) | 0 | Khớp yêu cầu phân nhánh duy nhất và receipt retry |
| `python -c "probe PreparedMusic and bed invariants"` (Bước 13) | 0 | Các bất biến của PW-E4-FIX1 giữ nguyên, không mẫu cũ |
| `python -c "probe CP2A-LAYOUT layout invariants"` (Bước 14) | 0 | Không import tiền tố `src.`, pyproject hợp lệ |
| `python -c "probe report content"` (Bước 16) | 0 | Báo cáo đầy đủ mã PW-E4-FIX2 và OI-CP7-11-Q4 |
| `git diff --check` (Bước 17) | 0 | Không có lỗi khoảng trắng |

## 6. GIẢ ĐỊNH và giới hạn

1. Gói chỉ đọc danh mục catalog do quy trình `HOOK-HARVEST` thu thập từ Freesound; gói không trực tiếp thực hiện cào web hay gọi API Freesound.
2. Khi không có tệp catalog hoặc catalog rỗng, hệ thống vận hành với hai nguồn ghim như cũ (thực hiện xoay vòng giữa các bản nhạc đã có sẵn trong kho).
3. Kế hoạch dựng video hiện thời chưa có trường `mood` chính thức trong `music_cues` (yêu cầu đầy đủ của FR-AUD-004 cần một gói creative chuyên biệt); gói này sử dụng cơ chế giao thoa từ khóa trong cue text (`artifact_ref`) với tập nhãn mood đã biết để đưa ra gợi ý chọn nhạc.
4. Môi trường kiểm thử không kết nối mạng internet thực; việc tải nhạc được kiểm chứng qua mock transport nội bộ của bài kiểm thử.

## 7. Mục mở còn lại

- `OI-CP7-11-Q4`: ĐÃ XỬ LÝ bởi gói PW-E4-FIX2.

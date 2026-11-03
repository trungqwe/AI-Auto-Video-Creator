# Báo cáo chuyển giao: PRS-LAYOUT-PLAN

## 1. Giới thiệu và nhóm lỗi OI-CP7-11-Q5

- **Mã gói công việc:** PRS-LAYOUT-PLAN
- **Milestone:** CP7
- **Nhóm lỗi xử lý:** `OI-CP7-11-Q5`
- **Mô tả vấn đề:** Trong `creative.py:278-290`, logic hiện hành luôn lấy khoá đầu tiên của `render.presets` dẫn tới việc mô hình AI chưa thể lựa chọn preset tương ứng cho kế hoạch sản xuất (vi phạm `FR-PRS-003`).
- **Phạm vi giải quyết:** Gói PRS-LAYOUT-PLAN hoàn thiện phần tầng domain và application pipeline: xây dựng miền lựa chọn bố cục AI (`layout_choice.py`), đóng băng `layout_choice` trong `ProductionPlan`, xử lý tương thích trường mặc định trong `codec.py`, tích hợp lựa chọn bố cục trong `pipeline.py`, và cập nhật prompt `ROLE_PLAN` trong `prompts.py`.
- **Trạng thái nhóm lỗi:** `OI-CP7-11-Q5` được giải quyết phần lõi miền và pipeline trong gói này; phần còn lại liên quan đến nối cấu hình runtime và giới hạn hạn ngạch theo lô tiếp tục được xử lý ở gói `PRS-LAYOUT-QUOTA`.

## 2. Các tệp đã sửa đổi

Toàn bộ các tệp mã nguồn và kiểm thử của gói được sao chép nguyên văn từ bản tham chiếu Control tại `D:/AIAVC_IMGPROTO/ref/prs-layout-plan/`. Giá trị băm SHA-256 (chuẩn hoá xuống dòng LF) hoàn toàn khớp với `SHA256SUMS`:

1. `src/creative/domain/layout_choice.py` (tạo mới):
   - SHA-256: `8852091c56f34aeeb690937cd3cb042ffb86292900aec17acafa5ac5cd6688d7`
   - Nội dung: 5 bố cục (`HERO_STRIP`, `MOSAIC_GRID`, `FULL_BLEED_INSET`, `SPLIT_STACK`, `DATA_CARD`), trần 40% mỗi lô `BATCH_SHARE_MAX = 0.4`, `TITLE_MAX_CHARS = 48`, các hàm đánh giá đặc trưng, lọc đủ điều kiện, trần lô và validator fallback.
2. `src/creative/domain/production_plan.py` (chỉnh sửa):
   - SHA-256: `65b5ac2bd0a61d96de06d93843853223dc1f860abad412b23d5a3b203f4143f0`
   - Nội dung: Bổ sung trường bất biến `layout_choice: Mapping[str, object] | None = None`, `_TOP_OPTIONAL` thêm `layout`, kiểm tra `preset_key == preset_revision_ref` với lỗi `invalid_layout_choice`.
3. `src/creative/persistence/codec.py` (chỉnh sửa):
   - SHA-256: `3afaa31ec5b2a87f3717e0acfcbdcdb14e4bd7e2abd20c941e3cf5a36c876705`
   - Nội dung: `decode_record` gán giá trị mặc định (`dataclasses.MISSING`) nếu bản ghi cũ thiếu trường.
4. `src/creative/application/pipeline.py` (chỉnh sửa):
   - SHA-256: `7a5fc695784dba6b83a133f8b9bf75e477a2ea8361619d44cc9fc1dd2c7b4bc7`
   - Nội dung: Hỗ trợ `layout_options` và `layout_presets`, ném `invalid_layout_presets`, bổ sung dữ liệu prompt bố cục và gọi `choose_layout`.
5. `src/creative/application/prompts.py` (chỉnh sửa):
   - SHA-256: `e164ba8f16ac5b0762c9c9d5e87727dfc495a1d4d9934a36e8be00e2186b22d3`
   - Nội dung: Thêm hướng dẫn chọn `layout` vào `ROLE_PLAN`, lưu hash cũ `b077e48b48d00e8f1cc8edab7904d12f976c37c5008e098cd8c0aa4c8a6cdd5b` vào `PREVIOUS_DEFAULT_PROMPT_HASHES[ROLE_PLAN]`.
6. `tests/unit/creative/test_prs_layout_choice.py` (tạo mới):
   - SHA-256: `2c5cf1a6fe7b1ca75535e6e582c6539ad87683c9bd3a6212e807ee9c4b45e1fc`
   - Nội dung: 6 ca kiểm thử bao phủ `FR-PRS-002`, `FR-PRS-003`, `FR-PRS-004`, `FR-PRS-005`.

## 3. Bảng lệnh kiểm tra đã thực thi

| STT | Lệnh kiểm tra | Mã thoát | Dòng tổng kết nguyên văn / Trạng thái thực tế |
| --- | --- | --- | --- |
| 1 | Bước 2 (RED trước sửa đổi): `python -m pytest tests/unit/creative/test_prs_layout_choice.py -q -p no:cacheprovider` | 2 | `ERROR tests/unit/creative/test_prs_layout_choice.py` / `1 error in 0.35s` (ImportError: cannot import name 'layout_choice' from 'creative.domain') |
| 2 | Bước 8 (Kiểm tra hash 6 tệp mã & test): `python -c "import hashlib, pathlib; ... assert not bad"` | 0 | `STEP 8 SHA256 CHECK PASSED` (Toàn bộ 6 tệp khớp tuyệt đối với SHA256SUMS) |
| 3 | Bước 9 (GREEN sau sửa đổi): `python -m pytest tests/unit/creative/test_prs_layout_choice.py -q -p no:cacheprovider` | 0 | `6 passed in 0.18s` |
| 4 | Bước 10: `python -m pytest tests/unit/creative -q -p no:cacheprovider` | 0 | `934 passed, 200 subtests passed in 5.18s` |
| 5 | Bước 11: `python -m pytest tests/integration/creative tests/integration/prod_wiring/test_pw_d3_fix3_illustration.py -q -p no:cacheprovider` | 0 | `115 passed in 1.84s` |
| 6 | Bước 12 (Nhóm kiểm thử CSDL): `python -m pytest tests/integration/prod_wiring/test_pw_d1_roles_prompts.py tests/integration/persistence/d/test_persist_d_postgres.py -q -p no:cacheprovider` | 0 | `51 passed in 16.15s` (CSDL Postgres khả dụng và vượt qua toàn bộ 51 ca) |
| 7 | Bước 14: Probe cấu trúc `layout_choice.py` | 0 | Đạt (Kiểm tra các hàm `layout_features`, `eligible_layouts`, `capped_layouts`, `choose_layout`, `valid_presets`, `layout_prompt_data`, hằng số `BATCH_SHARE_MAX = 0.4`, `TITLE_MAX_CHARS = 48`, không import `render`) |
| 8 | Bước 15: Probe kế hoạch, codec, pipeline, prompts, test | 0 | Đạt (Kiểm tra `layout_choice` trong `production_plan.py`, `dataclasses.MISSING` trong `codec.py`, `invalid_layout_presets` trong `pipeline.py`, prompt hash trong `prompts.py`, `coveredIds` trong test) |
| 9 | Bước 16: Probe `D-15-FIX1` wiring (`ProviderFailureHandler`) | 0 | Đạt |
| 10 | Bước 17: Probe `D-15-FIX2` json (`parse_model_json_object`) | 0 | Đạt |
| 11 | Bước 18: Probe ghi chú minh hoạ AI (`AI_ILLUSTRATION_NOTE`) | 0 | Đạt |
| 12 | Bước 19: Probe hook lead-in (`HOOK_LEAD_IN_MS = 500`) | 0 | Đạt |
| 13 | Bước 20: Probe trần seed 15% (`SEED_SHARE_MAX_PERCENT = 15`) | 0 | Đạt |
| 14 | Bước 21: Probe asset selection & prompts origin (`ORIGIN_SEED = 'seed'`) | 0 | Đạt |
| 15 | Bước 22: Probe pyproject package-dir và không import `src.` | 0 | Đạt |
| 16 | Bước 23: Probe `report.md` chứa `PRS-LAYOUT-PLAN` và `OI-CP7-11-Q5` | 0 | Đạt |
| 17 | Bước 24: `git diff --check` | 0 | Đạt (Không có lỗi khoảng trắng thừa) |

## 4. Chi tiết kiểm thử nghiệp vụ bố cục

Các ca kiểm thử trong `tests/unit/creative/test_prs_layout_choice.py` kiểm chứng đầy đủ các yêu cầu cốt lõi:
- **Bố cục AI chọn:** AI trả về cấu trúc bố cục và preset được đối chiếu với tập preset hợp lệ; lựa chọn hợp lệ được gắn vào `production_plan.layout_choice`.
- **Tập bố cục đủ điều kiện (`eligible_layouts`):**
  - `HERO_STRIP`: Có ít nhất 2 ảnh trong đó có ít nhất 1 ảnh bài báo.
  - `MOSAIC_GRID`: Có ít nhất 3 ảnh từ bài báo.
  - `FULL_BLEED_INSET`: Có ảnh AI tạo hoặc có tối đa 1 ảnh.
  - `SPLIT_STACK`: Có từ 2 ảnh trở lên.
  - `DATA_CARD`: Có số liệu xuất hiện trong lời đọc kịch bản.
  - Nếu không thoả mãn điều kiện nào thì mặc định trả về `HERO_STRIP`.
- **Trần 40% mỗi lô (`BATCH_SHARE_MAX = 0.4`):**
  - Hàm `capped_layouts` lọc bỏ các bố cục đã đạt mức trần `floor(0.4 * batch_size)` (với điều kiện tối thiểu còn lại 1 lựa chọn).
  - Nếu tất cả các bố cục đều đã đạt trần, hệ thống giữ lại bố cục có tần suất sử dụng ít nhất trong lô để đảm bảo phân bổ đồng đều.
- **Mã dự phòng (Fallback reasons):**
  - `layout_missing`: Khi phản hồi AI không chứa cấu trúc layout.
  - `layout_invalid`: Khi cấu trúc không hợp lệ (ví dụ: không phải dictionary).
  - `layout_unknown`: Khi khoá bố cục nằm ngoài 5 khoá hợp lệ của hệ thống.
  - `layout_not_eligible`: Khi khoá bố cục do AI chỉ định không nằm trong tập đủ điều kiện theo dữ liệu cảnh/ảnh.
  - `contrast_pair_invalid`: Khi chọn bố cục `SPLIT_STACK` nhưng cặp tương phản `contrast_pair` không gồm 2 `segment_id` khác nhau hợp lệ.

## 5. Giới hạn hiện tại

- Hệ thống chưa nhận biết ảnh bài dạng dọc (do ứng viên ảnh chưa cung cấp kích thước thực tế và cờ `technical_fitness` probed đang mang giá trị `false`), do đó `FULL_BLEED_INSET` hiện chỉ được kích hoạt khi có ảnh do AI sinh hoặc có tối đa 1 ảnh.
- Ý định cắt cúp theo ô (`crop_intent`) và danh sách các lớp chữ nhấn mạnh chưa được đưa vào kế hoạch sản xuất trong phạm vi gói này; phần này sẽ được thực hiện tại `PRS-LAYOUT-TEXT`.
- Chế độ debug cho phép người dùng tự chọn bố cục (`FR-PRS-004`) sử dụng cùng cơ chế `choose_layout`, nhưng giao diện màn hình tương tác chưa được triển khai.
- Chưa có pipeline hoàn chỉnh gọi trực tiếp với `layout_presets` cho đến khi hoàn thành gói `PRS-LAYOUT-QUOTA`.

# Đặc tả Kỹ thuật Capability E: Xử lý Âm thanh & Khớp Phụ đề (Voice Synthesis & Word Timing)

> **Mã Capability:** `CAP-E-VOICE`
> **Chủ quản:** Module E
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-MEDIA-PROCESSING`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability E chịu trách nhiệm tiếp nhận văn bản kịch bản từ Module D, thực hiện tổng hợp giọng đọc tiếng Anh tự nhiên (TTS), xử lý media (probe, analyze, đánh giá an toàn ảnh, transform, normalize; `CT-PROC-001..008`) và chuẩn bị audio nền (`CT-AUD-001`), bóc tách và căn chỉnh mốc thời gian chi tiết tới từng từ (`WordTiming`) phục vụ hiệu ứng phụ đề chạy chữ karaoke trên video thành phẩm.

### Aggregates do Module E sở hữu độc quyền (Single-Writer):
- `ProcessedMedia`: Ảnh và clip đã xử lý (rendition, transform, normalize); việc lọc tạp âm không có trong contract.
- `VoiceTrack`: File âm thanh giọng đọc hoàn chỉnh kèm metadata về giọng đọc, tốc độ và trường độ.
- `WordTiming`: Danh sách chính xác các từ kèm mốc thời gian bắt đầu (`start_ms`) và kết thúc (`end_ms`) tương ứng với file âm thanh.

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port đọc văn bản Script:** `VoiceTrackRequest` chỉ mang `script_version_id`, `script_fingerprint` và `pronunciation_hints`, không mang văn bản (`CT-TTS-001`, binding `d-e-f-voice-timing`); văn bản đọc qua binding `d-e-script-text` (CT-AI-004) hoặc port E-local `ScriptTextPort` cùng fake (CONV-E-07).
- **Port Gọi TTS Engine:** Gọi TTS qua route của Module J (`CT-AI-ROUTE-001`, binding `j-provider-route`) để thực hiện `CT-TTS-001`; `CT-AUD-001` là `PrepareAudioBed`, không phải cổng gọi TTS.

### Outbound Ports:
- **Port Cung cấp Voice & Karaoke Timing:** Chuyển giao `VoiceTrack` và danh sách `WordTiming` sang Module F (Rendering) qua `CONTRACT-MEDIA-PROCESSING` (`CT-SUB-001`).

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability E phải thỏa mãn:
1. `CONTRACT-MEDIA-PROCESSING` đã được đóng băng phiên bản (`frozen revision`).
2. Mẫu âm thanh đầu vào và file kịch bản mẫu tiếng Anh đã sẵn sàng trong test fixtures.
3. Slice dùng WAV sinh bằng `wave` của stdlib và fake; kiểm không rò rỉ bộ nhớ với thư viện thật là việc CP7.
4. Ranh giới thư mục mã nguồn được phân lập hoàn toàn khỏi Module F.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability E chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. Toàn bộ unit tests và contract verification tests đạt `PASS`.
2. Thời lượng 61–70 giây là `DURATION_RANGE` của video (`CT-QC-001`), kiểm ở Module F trên video thật; E ghi `actual_duration_ms` và có validator so với khoảng do policy truyền vào, không có hằng trong mã.
3. Mỗi từ có mốc hợp lệ (`0 <= start_ms < end_ms`, tăng đơn điệu, nằm trong thời lượng voice theo `CT-SUB-001`); sai số ±100 ms và tổng thời lượng timing khớp độ dài audio là hằng tự đặt, thuộc ROADMAP-OPEN-008 / TEST-OPEN-006, chưa chốt.
4. Mục tiêu loudness và mix lấy từ preset audio policy (`CT-AUD-001`); ngưỡng audio là mục mở của roadmap §12, không có hằng LUFS trong đặc tả.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-007`** (`TST-MEDIA-INV-007`): timing gắn exact script và voice; tăng đơn điệu, không âm, nằm trong thời lượng voice là bất biến 1 của `CT-SUB-001` cùng ràng buộc `monotonic_word_timings` của binding.
- **`INV-008`** (`TST-INT-INV-008`): render package chỉ nhận artifact đã được Module I verify; không liên quan độ dài audio.
- **`INV-019`** (`TST-QC-INV-019`): bằng chứng tiếng Anh theo exact revision; phủ đủ từ của kịch bản là test bắt buộc của roadmap §12, không có mã INV.

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/voice/**`
  - `tests/unit/voice/**`
  - `tests/integration/voice/**`
  - `docs/modules/capability-e-voice.md`
- **Forbidden Paths (Tuyệt đối cấm can thiệp):**
  - `src/creative/**`
  - `src/render/**`
  - `src/controlplane/**`
  - `docs/09-contracts/**`

---

## 7. Chiến lược Kiểm thử & Test Oracle

- **Kiểm thử Căn chỉnh Timing:** Sử dụng file WAV mẫu và kịch bản chuẩn để kiểm tra thuật toán tính toán mốc thời gian từng từ.
- **Quan sát RED:** Kiểm thử fail rõ ràng khi xuất hiện từ có `end_ms <= start_ms` hoặc `actual_duration_ms` nằm ngoài khoảng policy truyền vào.
- **Targeted Test Command:**
  ```bash
  python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Output bất biến: lỗi tổng hợp hoặc căn chỉnh được ghi thành attempt thất bại, không xóa lịch sử `VoiceTrack` và `WordTiming`; retry và fallback do Module G quyết, engine dự phòng chỉ theo `fallback_order` của Module J (`CT-AI-ROUTE-002`); E không cleanup (`CT-PROC-008`); operation đã terminal không mở lại (`CT-STATE-011`).

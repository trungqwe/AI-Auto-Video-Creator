# Đặc tả Kỹ thuật Capability E: Xử lý Âm thanh & Khớp Phụ đề (Voice Synthesis & Word Timing)

> **Mã Capability:** `CAP-E-VOICE`
> **Chủ quản:** Module E
> **Trạng thái:** `planned` (Thiết kế độc lập cho mô hình Wave/DAG)
> **Hợp đồng ràng buộc:** `CONTRACT-MEDIA-PROCESSING`

---

## 1. Mục tiêu và Trách nhiệm Nghiệp vụ

Capability E chịu trách nhiệm tiếp nhận văn bản kịch bản từ Module D, thực hiện tổng hợp giọng đọc tiếng Anh tự nhiên (TTS), kiểm tra an toàn âm thanh, bóc tách và căn chỉnh mốc thời gian chi tiết tới từng từ (`WordTiming`) phục vụ hiệu ứng phụ đề chạy chữ karaoke trên video thành phẩm.

### Aggregates do Module E sở hữu độc quyền (Single-Writer):
- `ProcessedMedia`: Dữ liệu âm thanh thô và đã xử lý chuẩn hóa (âm lượng LUFS, lọc tạp âm).
- `VoiceTrack`: File âm thanh giọng đọc hoàn chỉnh kèm metadata về giọng đọc, tốc độ và trường độ.
- `WordTiming`: Danh sách chính xác các từ kèm mốc thời gian bắt đầu (`start_ms`) và kết thúc (`end_ms`) tương ứng với file âm thanh.

---

## 2. Cổng Giao tiếp & Hợp đồng Khóa (Ports & Frozen Contracts)

### Inbound Ports:
- **Port Tiếp nhận Script:** Nhận văn bản kịch bản phân cảnh từ Module D qua `CONTRACT-MEDIA-PROCESSING` (`CT-TTS-001`).
- **Port Gọi TTS Engine:** Gọi TTS thông qua adapter Module J hoặc dịch vụ tích hợp qua `CONTRACT-MEDIA-PROCESSING` (`CT-AUD-001`).

### Outbound Ports:
- **Port Cung cấp Voice & Karaoke Timing:** Chuyển giao `VoiceTrack` và danh sách `WordTiming` sang Module F (Rendering) qua `CONTRACT-MEDIA-PROCESSING` (`CT-SUB-001`).

---

## 3. Điều kiện Sẵn sàng Thực thi (Definition of Ready - DoR)

Trước khi chuyển sang trạng thái `implementation_authorized`, task thuộc Capability E phải thỏa mãn:
1. `CONTRACT-MEDIA-PROCESSING` đã được đóng băng phiên bản (`frozen revision`).
2. Mẫu âm thanh đầu vào và file kịch bản mẫu tiếng Anh đã sẵn sàng trong test fixtures.
3. Thư viện xử lý âm thanh và công cụ phân tích mốc thời gian (alignment parser) đã được kiểm chứng hoạt động không có lỗi rò rỉ bộ nhớ.
4. Ranh giới thư mục mã nguồn được phân lập hoàn toàn khỏi Module F.

---

## 4. Tiêu chuẩn Hoàn tất (Definition of Done - DoD)

Gói công việc Capability E chỉ được nghiệm thu khi đạt đủ các điều kiện:
1. Toàn bộ unit tests và contract verification tests đạt `PASS`.
2. Kiểm chứng độ dài âm thanh: File `VoiceTrack` sinh ra phải có thời lượng chính xác nằm trong khoảng **61–70 giây**.
3. Độ chính xác căn chỉnh từ (Word Alignment Accuracy): 100% các từ trong kịch bản phải có mốc thời gian hợp lệ, không có mốc thời gian bị đảo ngược (`start_ms < end_ms`) và tổng thời lượng word timing phải khớp với độ dài file audio trong sai số cho phép (+/- 100ms).
4. Chuẩn hóa âm thanh: Mức âm lượng đạt chuẩn EBU R128 (-14 LUFS đến -16 LUFS) phù hợp với nền tảng video ngắn.

---

## 5. Danh mục Bất biến Kiến trúc (Invariant References)

- **`INV-007` (Continuous Monotonic Word Timestamps):** Mốc thời gian của các từ phụ đề karaoke phải tăng đơn điệu; không được phép có khoảng chồng chéo hoặc mốc âm.
- **`INV-008` (Audio Duration Match):** Thời lượng file giọng đọc phải tương thích hoàn toàn với giới hạn độ dài video 61–70 giây.
- **`INV-019` (Full Script Word Coverage):** Không được bỏ sót bất kỳ từ nào của kịch bản trong quá trình trích xuất timing phụ đề.

---

## 6. Ranh giới Đường dẫn Sở hữu (Path Scopes)

- **Allowed Paths (Được phép chỉnh sửa khi authorized):**
  - `src/voice/**`
  - `tests/unit/voice/**`
  - `docs/modules/capability-e-voice.md`
- **Forbidden Paths (Tuyệt đối cấm can thiệp):**
  - `src/creative/**`
  - `src/render/**`
  - `src/controlplane/**`
  - `docs/09-contracts/**`

---

## 7. Chiến lược Kiểm thử & Test Oracle

- **Kiểm thử Căn chỉnh Timing:** Sử dụng file WAV mẫu và kịch bản chuẩn để kiểm tra thuật toán tính toán mốc thời gian từng từ.
- **Quan sát RED:** Kiểm thử fail rõ ràng khi xuất hiện từ có `end_ms <= start_ms` hoặc thời lượng âm thanh vượt quá 70 giây.
- **Targeted Test Command:**
  ```bash
  python -m unittest tests/unit/voice/test_word_timing_alignment.py -k test_monotonic_timestamps
  ```

---

## 8. Tiêu chí Rollback & Phục hồi Lỗi

- **Nguyên tắc Rollback:** Nếu quá trình tổng hợp giọng đọc hoặc căn chỉnh timing bị lỗi, hủy bỏ `VoiceTrack` và `WordTiming` lỗi, giải phóng tài nguyên CPU/GPU và thông báo lỗi về Orchestration để điều phối retry với tốc độ hoặc engine dự phòng.

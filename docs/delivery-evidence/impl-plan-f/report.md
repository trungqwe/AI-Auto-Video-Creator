# Báo cáo IMPL-PLAN-F

Ngày 19/10/2026; HEAD gốc 773af60; nhánh trungqwe/lane-impl-plan-f; tệp tạo mới: `docs/implementation/f/plan.md`, `docs/implementation/f/slices.md` và báo cáo này.

## 1. Nguồn đã đọc

- `docs/modules/capability-f-rendering.md` (chỉ dùng sau khi áp dụng đính chính tại plan §2)
- `docs/11-roadmap.md` (§10 dòng 413, §12 năng lực F, §19 G06, G07, §23 ROADMAP-OPEN-007..010)
- `docs/09-contracts/08-render-quality-contracts.md` (CT-RND-001..006, CT-QC-001, CT-QC-002, acceptance §8)
- `docs/09-contracts/07-media-processing-contracts.md` (CT-TTS-001, CT-SUB-001, CT-AUD-001)
- `docs/09-contracts/05-content-media-contracts.md` (asset revision đã khóa)
- `docs/09-contracts/10-storage-contracts.md` (CT-STO-001, CT-STO-004, CT-STO-006, CT-STO-007)
- `docs/09-contracts/09-orchestration-contracts.md` (CT-ORC-008, CT-ORC-009)
- `docs/09-contracts/02-domain-events.md` (event F, CT-EVT-002, CT-EVT-003)
- `docs/09-contracts/03-workflow-and-execution.md` (CT-WF-003, CT-WF-006)
- `docs/09-contracts/12-state-machines.md` (CT-STATE-008, CT-STATE-011, CT-STATE-012)
- `docs/10-test-strategy.md` (§12.6 dòng 386–401, bảng INV, E2E, §20.3, dòng 833 và 837, TEST-OPEN-003, -005, -006)
- `docs/05-technology-research.md` (§5.14 FFmpeg filter graph dòng 274–279, TECH-OPEN-012 dòng 473)
- `docs/parallel-delivery/bindings/README.md`
- `docs/parallel-delivery/bindings/f-render-package.json`
- `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
- `docs/parallel-delivery/bindings/i-artifact-version.json`
- `docs/parallel-delivery/bindings/g-activity-execution.json`
- `docs/parallel-delivery/bindings/domain-event-envelope.json`
- `docs/parallel-delivery/bindings/g-c-i-completion.json`
- `tests/fixtures/contracts/f-render-package/payloads.json`
- `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
- `tests/fixtures/contracts/i-artifact-version/payloads.json`
- `tests/fixtures/contracts/g-activity-execution/payloads.json`
- `tests/fixtures/contracts/domain-event-envelope/payloads.json`
- `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- `docs/parallel-delivery/errata/m6-ef.md`
- `docs/parallel-delivery/ownership-and-locks.yaml` (`modules.F`, `PATH-SRC-RENDER`, `LOCK-SRC-RENDER`, `LOCK-CONTRACT-RENDER-QUALITY`, `LOCK-DESKTOP-GPU`, `PATH-IMPLEMENTATION-PLANS`)
- `docs/parallel-delivery/acceptance-matrix.yaml` (R11–R13, `TASK-CAP-F-RENDERING`)
- `docs/implementation/d/plan.md`
- `docs/implementation/e/plan.md`
- `docs/implementation/e/slices.md`
- `docs/implementation/i/plan.md`
- `docs/implementation/i/slices.md`
- `src/controlplane/domain/statemachine/__init__.py` (`OperationState`, `ArtifactLocationState`, `transition_operation`, `ReconciliationEvidence`)
- `src/controlplane/domain/interfaces/uow.py` (`IUnitOfWork`)
- `src/controlplane/domain/interfaces/outbox.py` (`IOutboxWriter`)
- `src/controlplane/domain/events/contracts.py` (`DomainEvent`, `ensure_safe_event_payload`)
- `src/controlplane/domain/concurrency.py` (`RevisionConflictError`)
- `src/controlplane/domain/common/contracts.py` (`ProblemDetail`)
- `src/controlplane/domain/orchestration/__init__.py` (`ExecutionGrant`)
- `src/controlplane/application/idempotency/canonicalization.py` (`request_hash`)

Ghi chú: Ba tệp `docs/parallel-delivery/M6-EF-contract-freeze.md`, `docs/parallel-delivery/M6-EF-execution-package.md`, `docs/parallel-delivery/M6-EF-test-plan.md` bị hỏng dấu tiếng Việt (ký tự `?` thay cho chữ có dấu), không được dùng làm nguồn, oracle hay bằng chứng.

## 2. Quyết định D8

Tóm tắt từng quyết định mặc định của kế hoạch (plan §7) kèm lý do:
- Output profile là input: `OutputProfileRevision` là input, không đặt hằng cứng 1080x1920 hay 30fps vì roadmap §23 cấm default ẩn và test-strategy yêu cầu tham số hóa.
- Sai số word timing karaoke là input policy: `tolerance_ms` nằm trong quality policy, bỏ hằng 50ms vì test-strategy dòng 833 cấm tự đặt ngưỡng chất lượng.
- Năm preset chỉ cài cấu trúc: F-02 chỉ cài cấu trúc `RenderPresetRevision` và bộ chứa, 5 preset mẫu chỉ là fixture test-only vì nội dung preset là exit gate M6 cần user duyệt.
- Ngưỡng audio mix và visual continuity là warning: warning/score đúng bảng CT-QC-001, không chặn thành công vì roadmap §12 xác định đây là điểm mở cần tinh chỉnh.
- Khoảng `DURATION_RANGE` 61–70 giây nằm trong policy: hai đầu bao gồm (61000 và 70000 ms pass, 60999 và 70001 ms fail) vì CT-QC-001 định nghĩa khoảng thời lượng.
- F không tự retry và không xóa tệp: attempt thất bại hoặc `OUTCOME_UNKNOWN` do G quyết retry bằng attempt mới theo CT-STATE-011 và CT-RND-004.
- Burn-in subtitle và karaoke bằng tệp ASS và libass: dùng thẻ `\k` của ASS và bộ lọc `subtitles` của FFmpeg theo công nghệ nghiên cứu, không thêm thư viện ngoài.
- Hình dạng `timeline.segments` và `hook_placement` là GIẢ ĐỊNH F-local: định nghĩa cấu trúc nội bộ tương thích additive với binding kiểu object theo fixture CP1.
- Cách phát hiện disclosure: mọi segment `inference`/`creative_hypothesis` phải có disclosure hiển thị theo CT-QC-001 và roadmap §12.
- `required_language` là input: nằm trong quality policy (fixture `en`), không chấp nhận metadata tự khai `language=en` theo INV-019.
- Output path và sanitize do I: F chỉ kiểm đường dẫn đã được cấp và nằm trong staging root theo CT-RND-006 và CT-STO-011.
- Receipt dùng `OperationState`: tái dùng máy trạng thái có sẵn của controlplane theo errata #1, không tạo máy riêng cho Preset hay RenderAttempt.
- UoW in-memory: slice chỉ cài bản bộ nhớ in-process, persistence PostgreSQL do CONV-F-01 vì migration là tài nguyên dùng chung.
- GPU qua `GpuLeasePort`: F giữ `LOCK-DESKTOP-GPU` qua port lease và giải phóng khi kết thúc, không ghi hằng slot trong mã.

## 3. Quyết định D10

- Domain Phân hệ F không cần thư viện mới: chỉ dùng thư viện chuẩn Python (stdlib) và các module dùng lại của `controlplane`.
- Đề xuất cho checkpoint USER-CKPT-D9-D10 (chỉ áp dụng cho adapter ở biên, không dùng trong domain):
  - FFmpeg / ffprobe: build cố định theo TECH-OPEN-012 (chưa chốt), có libass, bộ lọc ebur128, volumedetect, ssim, phục vụ filter graph dựng video và probe QC.
  - `av==18.1.0`: PyAV phiên bản 18.1.0 (release 12-08-2026, BSD-3-Clause), chỉ thêm nếu kiểm chứng CP7-F-02 chứng minh cần đọc khung hình và timestamp trong tiến trình.
- Không đề xuất các thư viện: `ffmpeg-python` (bảo trì kém), MoviePy (chỉ phù hợp prototype), Remotion (hạn chế bản quyền), `pyloudnorm` (FFmpeg đã hỗ trợ đo chuẩn), Pillow và OpenCV (chưa cần thiết, FFmpeg đảm nhiệm toàn bộ overlay).

## 4. Slice và yêu cầu hội tụ

- 22 work package slice (F-01..F-22) chia thành 11 đợt thực thi theo DAG.
- 14 yêu cầu hội tụ gửi IMPL-PLAN-CONVERGENCE: CONV-F-01 (migration), CONV-F-02 (composition root), CONV-F-03 (control API), CONV-F-04 (UI shell), CONV-F-05 (workflow G), CONV-F-06 (state machine & J config), CONV-F-07 (registry binding), CONV-F-08 (ownership registry), CONV-F-09 (catalog test & corpus), CONV-F-10 (outbox & event), CONV-F-11 (cấu hình J), CONV-F-12 (storage I), CONV-F-13 (lockfile & runtime), CONV-F-14 (phân hệ C, D, E).
- 8 hạng mục kiểm chứng tài nguyên thật CP7: CP7-F-01 (render thật RTX 4070 SUPER), CP7-F-02 (kiểm byte output, libass), CP7-F-03 (lỗi thật, crash, timeout), CP7-F-04 (đo audio mix), CP7-F-05 (duyệt 5 preset mẫu), CP7-F-06 (GPU contention), CP7-F-07 (throughput G02), CP7-F-08 (luồng thật end-to-end cùng I và G).
- Danh sách chờ user duyệt (pendingUserCheckpoint): ROADMAP-OPEN-007, ROADMAP-OPEN-008, ROADMAP-OPEN-009, TEST-OPEN-003, ngưỡng audio mix / visual continuity / hook / thumbnail, biên khoảng 61–70 giây, libass và cách burn-in, USER-CKPT-D9-D10, và các exit gate M6.

## 5. Lệnh kiểm và kết quả

1. Probe kiểm tra `plan.md` (bước 15):
   - Lệnh: `python -c "import pathlib, unicodedata, re; p = unicodedata.normalize('NFC', pathlib.Path('docs/implementation/f/plan.md').read_text(encoding='utf-8')); ... assert paths and not bad, bad"`
   - Exit code: 0
   - Stdout: không có output
   - Stderr: không có output

2. Probe kiểm tra `slices.md` (bước 31):
   - Lệnh: `python -c "import pathlib, re, unicodedata; b = chr(96); s = unicodedata.normalize('NFC', pathlib.Path('docs/implementation/f/slices.md').read_text(encoding='utf-8')); ... assert not miss, miss"`
   - Exit code: 0
   - Stdout: không có output
   - Stderr: không có output

3. Kiểm tra định dạng git diff (bước 32):
   - Lệnh: `git diff --check`
   - Exit code: 0
   - Stdout: không có output
   - Stderr: không có output

4. Kiểm tra bắt buộc plan và slices (bước 33):
   - Lệnh: `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/f'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ... assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s"`
   - Exit code: 0
   - Stdout: không có output
   - Stderr: không có output

## 6. Giới hạn

- Chỉ tạo và sửa đổi tệp trong các đường dẫn được giao quyền: `docs/implementation/f/**` và `docs/delivery-evidence/impl-plan-f/**`.
- Không dựa vào ba tệp M6-EF hỏng dấu tiếng Việt; toàn bộ kế hoạch được xây dựng mới từ nguồn chuẩn.
- Chưa chạy kiểm thử thực thi mã nguồn của từng slice vì mã nguồn sản phẩm chưa được triển khai ở pha lập kế hoạch này.
- Không tự ý tuyên bố hoàn thành các exit gate G06, G07 hay tự ý phê duyệt 5 preset mẫu; các nội dung này thuộc thẩm quyền của user tại checkpoint.
- Tuân thủ nguyên tắc bàn giao: commit cục bộ đúng một commit duy nhất, không thực hiện push lên remote và không merge vào nhánh chính.

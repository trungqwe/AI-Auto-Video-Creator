# Báo cáo MCDOC-POLICY

## Thông tin gói công việc
- **Mã gói:** MCDOC-POLICY
- **Nhóm lỗi / Mục mở:** OI-MC-POLICY-DOCS
- **Mục đích:** Đưa chính sách nội dung MC ngày 04/11/2026 vào tài liệu repo (nhánh tích hợp); hành vi mã chưa đổi cho tới khi MC-POLICY-SWITCHES của M8 gộp; docs/11-roadmap.md chỉ mang các gạch bỏ, mục M8 do MCDOC-ROADMAP-M8 thêm sau.

## Bảng 16 tệp đã chép nguyên văn từ bản tham chiếu D:/AIAVC_IMGPROTO/ref/mcdoc-policy/

| STT | Đường dẫn tệp | SHA-256 |
| --- | --- | --- |
| 1 | `AUDIT.md` | `d6743e44c8eafc6299affe2aa17b547add973d3c6e0b913dac6157fb34a9c8f4` |
| 2 | `docs/01-product-spec.md` | `a75f2eadd6f0dcd70e173a17a09caf18d1049002db71bf8034908b1774b14ffc` |
| 3 | `docs/03-quality-requirements.md` | `71a45bfb968b4e3403dbbd17f19066b0b08edd0d0e6099c09c6130edf77cec87` |
| 4 | `docs/09-contracts/06-creative-ai-contracts.md` | `4dae96d9ddcc0f5fadd63cd22e1d7ea11b9444acc7624cc04eccc621611bdaf3` |
| 5 | `docs/09-contracts/07-media-processing-contracts.md` | `b5088350b91dfcf5f40c91e1524510f1cb10f1e7451891c014602775e03ff9f6` |
| 6 | `docs/09-contracts/08-render-quality-contracts.md` | `18eb24ab59ef6835cf038f494853fe804a44015651e571bfce921cb53aeda3a9` |
| 7 | `docs/10-test-strategy.md` | `6dbe9f22dc6d8ac703cc2bdcfa590c49407d413e7986d4cf0ea89e4b294b2722` |
| 8 | `docs/11-roadmap.md` | `573b4a2fe7bc349189c9431478a46eb0acd3e3f65c073bce72186cadc141e1ea` |
| 9 | `docs/MC-POLICY-20261104.md` (tệp mới) | `2085a2bd521a604a430c7331cd2bbbca9fbc88cc5479befb345908c804c21c42` |
| 10 | `docs/parallel-delivery/bindings/b-d-production-snapshot.json` | `00f26d6a2458c3c8772c65496a2ba7613853d6dc3320f0ee01417f2316728b73` |
| 11 | `docs/parallel-delivery/bindings/d-e-f-voice-timing.json` | `fbc2f2bf5ae99e14b4aa6b16218a38aa6b44672ddbefac1a7a4dd951f971e1ad` |
| 12 | `docs/parallel-delivery/bindings/d-e-script-text.json` | `b7ac6cf8a2e5b9e1b0d7d04e03c885547edec36f34a2aabdcf78bfb135fd0ba7` |
| 13 | `docs/parallel-delivery/bindings/e-processing-audio-bed.json` | `20aa61876f65282a443184b4733f0d9f0cf9c7158ef92b199123f5fad3271c22` |
| 14 | `docs/parallel-delivery/bindings/f-g-output-ready.json` | `9781472ee2ff0e462a0ba2f25a84ea02f164f34bb2ca8ebed73cc971a759de85` |
| 15 | `docs/parallel-delivery/bindings/f-render-package.json` | `e1cb13bd65acdd946a3dacd16d596eb9caaa12fd93561ad80b36ab795720469b` |
| 16 | `docs/parallel-delivery/contract-registry.yaml` | `5de22ca1844f4d00147697911b6e120ef22528182938c5f6f8f98d8a71866935` |

## Lệnh đã chạy

### Bước 17: Kiểm tra khoảng trắng thừa / CRLF
- **Lệnh:** `git diff --check`
- **Mã thoát:** 0
- **Kết quả:** Không có dòng cảnh báo whitespace hay CRLF.

### Bước 18: So sánh SHA-256 với bản tham chiếu
- **Lệnh:** `python -c "import hashlib, pathlib; want = {'AUDIT.md': 'd6743e44c8eafc6299affe2aa17b547add973d3c6e0b913dac6157fb34a9c8f4', 'docs/01-product-spec.md': 'a75f2eadd6f0dcd70e173a17a09caf18d1049002db71bf8034908b1774b14ffc', 'docs/03-quality-requirements.md': '71a45bfb968b4e3403dbbd17f19066b0b08edd0d0e6099c09c6130edf77cec87', 'docs/09-contracts/06-creative-ai-contracts.md': '4dae96d9ddcc0f5fadd63cd22e1d7ea11b9444acc7624cc04eccc621611bdaf3', 'docs/09-contracts/07-media-processing-contracts.md': 'b5088350b91dfcf5f40c91e1524510f1cb10f1e7451891c014602775e03ff9f6', 'docs/09-contracts/08-render-quality-contracts.md': '18eb24ab59ef6835cf038f494853fe804a44015651e571bfce921cb53aeda3a9', 'docs/10-test-strategy.md': '6dbe9f22dc6d8ac703cc2bdcfa590c49407d413e7986d4cf0ea89e4b294b2722', 'docs/11-roadmap.md': '573b4a2fe7bc349189c9431478a46eb0acd3e3f65c073bce72186cadc141e1ea', 'docs/MC-POLICY-20261104.md': '2085a2bd521a604a430c7331cd2bbbca9fbc88cc5479befb345908c804c21c42', 'docs/parallel-delivery/bindings/b-d-production-snapshot.json': '00f26d6a2458c3c8772c65496a2ba7613853d6dc3320f0ee01417f2316728b73', 'docs/parallel-delivery/bindings/d-e-f-voice-timing.json': 'fbc2f2bf5ae99e14b4aa6b16218a38aa6b44672ddbefac1a7a4dd951f971e1ad', 'docs/parallel-delivery/bindings/d-e-script-text.json': 'b7ac6cf8a2e5b9e1b0d7d04e03c885547edec36f34a2aabdcf78bfb135fd0ba7', 'docs/parallel-delivery/bindings/e-processing-audio-bed.json': '20aa61876f65282a443184b4733f0d9f0cf9c7158ef92b199123f5fad3271c22', 'docs/parallel-delivery/bindings/f-g-output-ready.json': '9781472ee2ff0e462a0ba2f25a84ea02f164f34bb2ca8ebed73cc971a759de85', 'docs/parallel-delivery/bindings/f-render-package.json': 'e1cb13bd65acdd946a3dacd16d596eb9caaa12fd93561ad80b36ab795720469b', 'docs/parallel-delivery/contract-registry.yaml': '5de22ca1844f4d00147697911b6e120ef22528182938c5f6f8f98d8a71866935'}; norm = lambda p: pathlib.Path(p).read_bytes().replace(bytes([13, 10]), bytes([10])); bad = sorted(p for p, h in want.items() if hashlib.sha256(norm(p)).hexdigest() != h); assert not bad, ('khác bản tham chiếu D:/AIAVC_IMGPROTO/ref/mcdoc-policy (so sau khi đổi CRLF thành LF)', bad)"`
- **Mã thoát:** 0
- **Kết quả:** Toàn bộ 16 tệp trùng khớp SHA-256 bản tham chiếu (sau khi đổi CRLF thành LF).

### Bước 19: Kiểm tra ký tự CR
- **Lệnh:** `python -c "import pathlib; ps = ['AUDIT.md', 'docs/01-product-spec.md', 'docs/03-quality-requirements.md', 'docs/09-contracts/06-creative-ai-contracts.md', 'docs/09-contracts/07-media-processing-contracts.md', 'docs/09-contracts/08-render-quality-contracts.md', 'docs/10-test-strategy.md', 'docs/11-roadmap.md', 'docs/MC-POLICY-20261104.md', 'docs/parallel-delivery/bindings/b-d-production-snapshot.json', 'docs/parallel-delivery/bindings/d-e-f-voice-timing.json', 'docs/parallel-delivery/bindings/d-e-script-text.json', 'docs/parallel-delivery/bindings/e-processing-audio-bed.json', 'docs/parallel-delivery/bindings/f-g-output-ready.json', 'docs/parallel-delivery/bindings/f-render-package.json', 'docs/parallel-delivery/contract-registry.yaml']; bad = [p for p in ps if bytes([13]) in pathlib.Path(p).read_bytes()]; assert not bad, ('tệp còn CR', bad)"`
- **Mã thoát:** 0
- **Kết quả:** Không tệp nào chứa byte CR (chuẩn LF 100%).

### Bước 20: Probe nội dung 1 (contract 07)
- **Lệnh:** `python -c "import pathlib; bt = chr(96); t = pathlib.Path('docs/09-contracts/07-media-processing-contracts.md').read_text(encoding='utf-8'); h5 = '### CT-PROC-005 — ' + bt + 'AssessImageSafety' + bt; h6 = '### CT-PROC-006 — ' + bt + 'TransformSensitiveImage' + bt; assert h5 in t and h6 in t, 'contract 07 phải giữ nguyên hai tiêu đề CT-PROC-005/006'; sec = t.split('### CT-PROC-005', 1)[1].split('### CT-PROC-006', 1)[0]; rows = ['| ' + bt + s + bt + ' |' for s in ['SAFE', 'TRANSFORM_REQUIRED', 'UNCERTAIN', 'DETECTION_FAILED', 'TRANSFORM_FAILED', 'UNREADABLE']]; assert all(r in sec for r in rows), 'bảng CT-PROC-005 phải còn đủ 6 trạng thái'; assert 'content_policy.image_safety.enabled_categories' in t, 'thiếu ghi chú công tắc'"`
- **Mã thoát:** 0
- **Kết quả:** Tiêu đề CT-PROC-005 và CT-PROC-006 còn nguyên, bảng CT-PROC-005 đủ 6 trạng thái, có ghi chú công tắc content_policy.image_safety.enabled_categories.

### Bước 21: Probe nội dung 2 (spec và quality requirements)
- **Lệnh:** `python -c "import pathlib; a = pathlib.Path('docs/01-product-spec.md').read_text(encoding='utf-8'); b = pathlib.Path('docs/03-quality-requirements.md').read_text(encoding='utf-8'); assert '- **FR-SEN-002:** *(giữ — ranh giới Control 04/11/2026)* Ảnh có khuôn mặt trẻ em phải được đánh dấu để che mặt.' in a, 'FR-SEN-002 phải giữ'; assert '| **QR-SAFE-002** | Khuôn mặt trẻ em |' in b, 'QR-SAFE-002 phải giữ'; assert '~~**FR-SEN-001:**~~' in a and '~~QR-SAFE-003~~' in b, 'các mục khác phải tắt'"`
- **Mã thoát:** 0
- **Kết quả:** FR-SEN-002 và QR-SAFE-002 còn hiệu lực; FR-SEN-001 và QR-SAFE-003 đã tắt.

### Bước 22: Probe nội dung 3 (MC-POLICY-20261104.md)
- **Lệnh:** `python -c "import pathlib; t = pathlib.Path('docs/MC-POLICY-20261104.md').read_text(encoding='utf-8'); assert '## Ranh giới Control giữ (04/11/2026)' in t and 'MC-POLICY-SWITCHES' in t and 'docs/implementation/mc/plan.md' in t, 'MC-POLICY thiếu mục ranh giới hay tham chiếu'"`
- **Mã thoát:** 0
- **Kết quả:** Có mục ## Ranh giới Control giữ (04/11/2026), tham chiếu MC-POLICY-SWITCHES và docs/implementation/mc/plan.md.

### Bước 23: Pytest kiểm tài liệu
- **Lệnh:** `python -m pytest tests/unit/voice/test_e05_image_safety.py tests/unit/voice/test_e20_coverage_catalog.py tests/contract/test_bindings.py -q -p no:cacheprovider`
- **Mã thoát:** 0
- **Dòng tổng kết nguyên văn:** `368 passed in 3.07s`

## Kết quả 3 probe nội dung và các probe xác minh
- **Probe SHA-256 (bước 18):** Mã thoát 0 (khớp toàn bộ 16 tệp).
- **Probe CR (bước 19):** Mã thoát 0 (toàn bộ LF, không chứa byte CR).
- **Probe nội dung 1 (bước 20):** Mã thoát 0.
- **Probe nội dung 2 (bước 21):** Mã thoát 0.
- **Probe nội dung 3 (bước 22):** Mã thoát 0.

## Mục mở
- **Mã mục mở:** OI-MC-POLICY-DOCS.
- **Trạng thái:** Còn mở tới khi gói MC-POLICY-SWITCHES (M8) đổi hành vi mã.
- **Ràng buộc đã giữ:**
  - Contract 07 giữ tiêu đề và bảng CT-PROC-005/006.
  - FR-SEN-002 và QR-SAFE-002 (che mặt trẻ em) giữ hiệu lực.
  - Không sửa mã nguồn, bài kiểm thử hay cấu hình.

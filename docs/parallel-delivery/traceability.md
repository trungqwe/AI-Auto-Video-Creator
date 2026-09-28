# Truy vết mục tiêu, module, contract, task và gate

> **Trạng thái:** `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`

Tài liệu này là chỉ mục, không định nghĩa lại requirement. ID và nội dung đầy đủ nằm trong charter, product spec, quality requirements, system map, contracts, test strategy và roadmap. Task thực tế phải tham chiếu ID cụ thể; wildcard dưới đây chỉ dùng cho planning cấp nhóm.

## 1. Mục tiêu người dùng

| Objective ID | Mục tiêu nguồn | Requirement chính | Owner | Contract/invariant | Gate |
|---|---|---|---|---|---|
| `OBJ-001` | Sản xuất video ngắn tiếng Anh cho khán giả Mỹ | `FR-SCR-*`, `QR-CONT-*`, `QR-OUT-004`, `QR-COMP-004` | D, F | `CT-AI-*`, `CT-RND-*`, `CT-QC-*`, `INV-019` | G06, G07 |
| `OBJ-002` | Video hợp lệ 61–70 giây, hook đầy đủ, karaoke từng từ | `FR-REN-*`, `FR-HOOK-*`, `QR-OUT-*` | C, D, E, F | `CT-MED-*`, `CT-PROC-*`, `CT-TTS-*`, `CT-SUB-*`, `CT-AUD-*`, `CT-RND-*`, `CT-QC-*`, `INV-007..009`, `INV-019` | G02, G06, G07 |
| `OBJ-003` | Tối thiểu 100 video hợp lệ/12 giờ khi ổn định | `FR-REN-006/007`, `QR-PERF-001..004` | G, E, F, I | `CT-WF-*`, `CT-ORC-*`, `INV-009/010/018` | G02 |
| `OBJ-004` | Ít nhất 95% video đủ đầu vào hoàn tất không cần can thiệp | `FR-BAT-*`, `QR-REL-001..009` | G | `CT-WF-*`, `CT-ORC-*`, `CT-STATE-*`, `INV-001..003/016/018` | G01, G02 |
| `OBJ-005` | Cloud tiếp tục thu thập khi desktop tắt | `FR-COL-002/011`, `QR-AVL-001/002` | A, G | `CT-SRC-*`, `CT-WF-*`, `INV-003/016` | G01 |
| `OBJ-006` | Không xóa output trước khi cloud sync được xác minh | `FR-SYN-001..007`, `QR-REL-005`, `QR-DATA-007` | I, G | `CT-STO-*`, `CT-ORC-*`, `INV-009/011/017` | G04, G05 |
| `OBJ-007` | Nhiều góc kể/biến thể, không lặp nguyên trạng | `FR-SCR-003..007`, `FR-VAR-*`, `QR-DATA-005/006` | D, G | `CT-AI-*`, `CT-ORC-012`, `INV-013/014/018` | G06 |
| `OBJ-008` | UI tiếng Việt desktop 1080p+, debug theo stage | `FR-CTL-*`, `FR-UI-*`, `QR-UX-*`, `QR-PERF-005/006` | H, G | `CT-API-*`, `CT-STATE-*` | G07 |
| `OBJ-009` | Chi phí phát sinh dưới 50 USD/tháng, cảnh báo 80% | `QR-COST-001..004`, `FR-CFG-*` | G, J | `CT-CFG-*`, `CT-ORC-*` | G03 |
| `OBJ-010` | Năm nhóm preset, không có trình sửa script/timeline trực tiếp | `FR-PRS-*`, `FR-CTL-005`, `FR-UI-009` | F, H | `CT-RND-*`, `CT-QC-*`, `CT-API-*` | G07 |
| `OBJ-011` | Provenance, secret và nội dung ngoài đều fail closed | `FR-LOG-005`, `QR-SEC-*`, `QR-DATA-001/004` | A–J, J chủ trì secret | `CT-CMN-013`, `CT-SEC-*`, `INV-012/020` | G04, G06, G07 |

## 2. Nhóm chức năng tới owner/contract

| Nhóm | Owner chính | Contract | Invariant/gate nổi bật | Milestone dự kiến |
|---|---|---|---|---|
| `FR-SRC-*` | A | `CT-SRC-*` | `INV-015/020`, G01/G04 | M3 |
| `FR-COL-*` | A | `CT-SRC-*`, `CT-WF-*`, `CT-STO-*` | `INV-002/003/016/020`, G01/G04 | M3 |
| `FR-CLS-*` | D phân tích, B ghi chính thức | `CT-AI-*`, `CT-SRC-*` | G06 | M3/M5 |
| `FR-EVT-*` | B | `CT-SRC-*`, `CT-EVT-*` | `INV-005/006`, G06 | M3 |
| `FR-AST-*` | C, A thu thập bổ sung | `CT-MED-*`, `CT-STO-*` | `INV-008/020`, G04/G06 | M4 |
| `FR-HOOK-*` | C kho, D chọn | `CT-MED-*`, `CT-AI-*` | `INV-008/019`, G06/G07 | M4–M6 |
| `FR-SCR-*` | D | `CT-AI-*` | `INV-004/013/014/019/020`, G06 | M5 |
| `FR-VAR-*` | D, G | `CT-AI-*`, `CT-ORC-*` | `INV-013/014/018`, G06 | M5–M7 |
| `FR-PRS-*` | F preset, D plan | `CT-RND-*`, `CT-QC-*`, `CT-AI-*` | `INV-008/019`, G07 | M6 |
| `FR-SEN-*` | E | `CT-PROC-*`, `CT-TTS-*`, `CT-SUB-*`, `CT-AUD-*` | G06/G07 | M6 |
| `FR-AUD-*` | E, F mix | `CT-PROC-*`, `CT-TTS-*`, `CT-SUB-*`, `CT-AUD-*`, `CT-RND-*`, `CT-QC-*` | `INV-007/019`, G02/G06/G07 | M6 |
| `FR-CTL-*` | G, H | `CT-API-*`, `CT-ORC-*`, `CT-STATE-*` | `INV-001/003/016`, G01/G07 | M2–M7 |
| `FR-BAT-*` | G | `CT-WF-*`, `CT-ORC-*` | `INV-010/018`, G01/G02 | M7 |
| `FR-REN-*` | F | `CT-RND-*`, `CT-QC-*`, `CT-STO-*` | `INV-008/009/019`, G02/G07 | M6/M7 |
| `FR-SYN-*` | I | `CT-STO-*`, `CT-ORC-*` | `INV-009/011/017`, G04/G05 | M4/M6/M7 |
| `FR-OUT-*` | I, D title/hashtag | `CT-STO-*`, `CT-AI-*` | G07 | M6 |
| `FR-UI-*` | H | `CT-API-*` | G07 | M2–M7 |
| `FR-LOG-*` | G, J redaction | `CT-EVT-*`, `CT-SEC-*` | `INV-012`, G04/G07 | M2–M7 |
| `FR-CFG-*` | J | `CT-CFG-*`, `CT-WF-*` | `INV-004/012/016`, G03/G04 | M2–M7 |

## 3. Nhóm chất lượng tới gate/evidence

| Nhóm QR | Chủ trì | Gate | Evidence bắt buộc |
|---|---|---|---|
| `QR-PERF-*` | G | G02/G07 | ledger/output verified, latency distribution, resource timeline, 12h run khi đóng gate |
| `QR-REL-*` | G | G01/G02/G04 | fault timeline, state/log reconciliation, auto-completion ratio |
| `QR-AVL-*` | G | G01/G05 | schedule/offline/resume và recovery report |
| `QR-DATA-*` | B/D | G06 | provenance chain, revision diff, locked evaluation set |
| `QR-CONT-*` | D | G06 | locked sample/rubric và user evaluation |
| `QR-SAFE-*` | E | G06/G07 | labeled image set, recall/error breakdown, transform evidence |
| `QR-OUT-*` | F | G02/G06/G07 | media probe, QC/timing report, listening review |
| `QR-UX-*` | H | G07 | UI state, viewport, UTF-8 và latency evidence |
| `QR-OBS-*` | G | G01/G07 | session/job/source trace và error coverage |
| `QR-SEC-*` | J | G04/G07 | canary scan, isolation, scope/role và transport evidence |
| `QR-COST-*` | G/J | G03 | usage/cost reconciliation và forecast warning |
| `QR-SCALE-*` | từng owner | G02/G05/G07 | growth dataset và query/queue/storage behavior |
| `QR-MNT-*` | từng owner | G01/G05/G07 | compatibility, history/revision và replacement test |
| `QR-COMP-*` | H/F/I | G07 | target machine/version manifest, media/path/UTF-8 results |

## 4. Từ task tới evidence

Mỗi task active phải có chuỗi không đứt:

```text
Objective → FR/QR/R → module owner → CT/INV exact revision
→ milestone authority → task → acceptance instrument/counterexample
→ RED evidence → candidate commit → GREEN/regression evidence
→ independent review → merge queue item → integrated evidence → user checkpoint
```

Validator phải từ chối:

- requirement/ref không tồn tại hoặc mang ID giả lập (fake ID như `INV-999`, `FR-FAKE-001`, `CT-FAKE-001`, `MODULE-UNKNOWN`);
- task không có authority ref hoặc authority ref trỏ tới tệp không tồn tại;
- owner không khớp module registry;
- contract dùng wildcard ở task implementation thay vì exact revision/ID;
- task có authority `locked` hoặc `future_template` cố tình chuyển sang trạng thái `ready`;
- acceptance rows của task sẵn sàng (`ready`) có `red_observation` rỗng, thiếu hoặc mang giá trị `unknown`;
- evidence output trùng task khác;
- gate PASS không có instrument đúng loại;
- external gate dùng mock;
- accepted evidence bị đổi hash hoặc xin mutation lease.

## 5. Open thresholds giữ nguyên

Các mục sau chưa được bundle này quyết định: sample size, quy mô bảng/scale dataset, output profile, word-timing tolerance, retry/timeout/concurrency, retention, storage placement, timezone, Tier threshold, hot/trending proxy, model/TTS/fallback và rule filename chi tiết. Chúng giữ open tới gate/owner được ghi trong tài liệu nguồn.

## 6. Authority mapping hiện hành

| Phạm vi | Trạng thái | Hành động delivery được phép |
|---|---|---|
| M1 | `ACCEPTED/CLOSED` | Chỉ regression/đối chiếu khi task có quyền; không viết lại evidence |
| M2-P1..P7B | `ACCEPTED/CLOSED` | Bảo toàn source/evidence; thay đổi mới cần authority riêng |
| M2-P8/P9 | `LOCKED` | Không RED, không implementation |
| M3/Module A | `NOT AUTHORIZED` | Chỉ đọc/thiết kế proposal; không dispatch implementation |
| M4–M7 | `NOT STARTED/FUTURE` | Template planning không active |
| Parallel delivery experiment | docs/config only | Viết/validate bundle và agent config; không product code |

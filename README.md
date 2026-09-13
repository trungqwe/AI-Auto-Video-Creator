# AI Auto Video Creator

Hệ thống tự động hóa việc thu thập tin và media, tạo nhiều góc kể tiếng Anh, dựng video ngắn 61–70 giây và đồng bộ đầu ra lên cloud. Dự án được phát triển theo từng milestone có evidence gate; không coi việc chương trình chạy một lần là bằng chứng kiến trúc đã đạt.

## Trạng thái hiện hành

| Hạng mục | Trạng thái |
|---|---|
| M0 Design | `APPROVED` |
| M1 Evidence Prototype | `IN PROGRESS — P0-P4 PASS` |
| G01 Temporal | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` |
| G04 Drive/OAuth | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` |
| M2 | `NOT AUTHORIZED` |
| M3 / Module A | `NOT AUTHORIZED` |

Phạm vi implementation hiện được phép chỉ là `M1-P0 → M1-P6`. M1 phải đi theo test-first, lưu evidence thật và dừng khi gặp điều kiện STOP. Không được bắt đầu M2, M3 hoặc Phân hệ A trước khi M1 qua exit gate, được audit và người dùng xác nhận checkpoint tiếp theo.

M1-P0, P1, P2, P3 và P4 đã hoàn tất PASS: P0/P1 qua remediation audit R1, P2 Temporal G01 proof đạt 7/7 test, P3 Google Drive & OAuth G04 proof đạt 8/8 test (bao gồm kiểm thử Live E3 probe trên Google Drive thật), P4 Local Journal & Recovery proof đạt 6/6 test. Tổng test suite hiện có 63 test qua; coverage đạt 89%. Cả G01 và G04 đều đạt `PARTIALLY_PROVEN (PASS_M1_SCOPE)`; work package kế tiếp là M1-P5 (Compatibility Smoke).

## Bắt đầu một phiên làm việc

Đọc theo thứ tự:

1. [HANDOFF.md](./HANDOFF.md) — trạng thái ngắn của phiên gần nhất.
2. [Checklist trước code](./docs/12-pre-code-checklist.md) — quyền và gate hiện hành.
3. [Roadmap](./docs/11-roadmap.md) — milestone và dependency.
4. [M1 implementation plan](./docs/milestones/m1-proof/implementation-plan.md) — work package đang được phép thực hiện.
5. [M1-R1 version lock](./docs/milestones/m1-proof/version-lock.md) — phiên bản bắt buộc.

Chỉ đọc sâu contracts/ADR được work package hiện tại trích dẫn; không remap toàn bộ dự án nếu `HANDOFF` và tài liệu nguồn sự thật còn nhất quán.

## Tài liệu nền

- [Project charter](./docs/00-project-charter.md)
- [Product specification](./docs/01-product-spec.md)
- [Data model](./docs/02-data-model.md)
- [Quality requirements](./docs/03-quality-requirements.md)
- [Technology research](./docs/05-technology-research.md)
- [System map](./docs/06-system-map.md)
- [Data flow](./docs/07-data-flow.md)
- [Architecture](./docs/08-architecture.md)
- [ADR index](./docs/adr/README.md)
- [Contracts](./docs/09-contracts/README.md)
- [Test strategy](./docs/10-test-strategy.md)
- [Audit](./AUDIT.md)

## Quy tắc lưu vết

- `CHANGELOG.md` ghi tiến độ và thay đổi có giá trị lâu dài.
- `HANDOFF.md` chỉ giữ trạng thái ngắn cần cho phiên tiếp theo; thay nội dung cũ thay vì tích lũy nhật ký dài.
- Kết thúc mỗi phiên sửa đổi hoặc giai đoạn quan trọng: đồng bộ tài liệu, chạy kiểm tra phù hợp, commit theo Conventional Commits và push lên repository này.
- Không commit secret, token, credential, dữ liệu cá nhân, log chưa redacted hoặc artifact không rõ quyền sử dụng.

## Repository

Remote chính: <https://github.com/trungqwe/AI-Auto-Video-Creator>

## Trạng thái sau M1-P4 Local Journal Proof

M1-P0, P1, P2, P3 và P4 đã hoàn tất `PASS`; G01 và G04 đều đạt `PARTIALLY_PROVEN (PASS_M1_SCOPE)` với evidence đầy đủ tại `docs/milestones/m1-proof/evidence/m1-p2/`, `evidence/m1-p3/` và `evidence/m1-p4/`. Work package tiếp theo là M1-P5 (Compatibility Smoke); M2/M3/Module A vẫn `NOT AUTHORIZED`.

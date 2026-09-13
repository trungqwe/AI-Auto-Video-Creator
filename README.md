# AI Auto Video Creator

Hệ thống tự động hóa việc thu thập tin và media, tạo nhiều góc kể tiếng Anh, dựng video ngắn 61–70 giây và đồng bộ đầu ra lên cloud. Dự án được phát triển theo từng milestone có evidence gate; không coi việc chương trình chạy một lần là bằng chứng kiến trúc đã đạt.

## Trạng thái hiện hành

| Hạng mục | Trạng thái |
|---|---|
| M0 Design | `APPROVED` |
| M1 Evidence Prototype | `ACCEPTED / CLOSED` |
| G01 Temporal | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` |
| G04 Drive/OAuth | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` |
| G07 Compatibility | `SMOKE_COMPATIBILITY_PASS_M1_SCOPE` |
| M2 Control Plane | `AUTHORIZED_FOR_PLANNING_AND_IMPLEMENTATION` |
| M3 / Module A | `NOT AUTHORIZED` |

Toàn bộ các work package M1 (`M1-P0 → M1-P6`) đã được Người dùng CHẤP THUẬN chính thức tại User Checkpoint ngày 13-09-2026 sau independent re-audit HEAD `08c857c`: M1 chuyển sang `ACCEPTED / CLOSED` (93 passed, 0 skipped, coverage 83%, Audit R5 + R5.1 ACCEPTED). Quyền lập kế hoạch và triển khai cho Milestone M2 được kích hoạt: `AUTHORIZED_FOR_PLANNING_AND_IMPLEMENTATION`. Toàn bộ Milestone M3 và Phân hệ A tiếp tục bị khóa chặt (`NOT AUTHORIZED`) cho đến khi M2 đạt exit gate và có User Checkpoint riêng.

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

## Trạng thái sau User Checkpoint M1 & Kích hoạt Milestone M2
Milestone M1 (`M1-P0 → M1-P6`) đã hoàn tất 100% và được Người dùng phê duyệt chính thức (`ACCEPTED / CLOSED`) với **93 passed, 0 skipped** tests, Audit R5 + R5.1 ACCEPTED, G01 và G04 giữ `PARTIALLY_PROVEN (PASS_M1_SCOPE)`, G07 giữ `SMOKE_COMPATIBILITY_PASS_M1_SCOPE`. Milestone M2 chính thức chuyển sang `AUTHORIZED_FOR_PLANNING_AND_IMPLEMENTATION`. Milestone M3 và Phân hệ A tiếp tục `NOT AUTHORIZED`.



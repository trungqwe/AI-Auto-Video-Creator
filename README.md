# AI Auto Video Creator

Hệ thống tự động hóa việc thu thập tin và media, tạo nhiều góc kể tiếng Anh, dựng video ngắn 61–70 giây và đồng bộ đầu ra lên cloud. Dự án được phát triển theo từng milestone có evidence gate; không coi việc chương trình chạy một lần là bằng chứng kiến trúc đã đạt.

## Trạng thái hiện hành

| Hạng mục | Trạng thái |
|---|---|
| M0 Design | `APPROVED` |
| M1 Evidence Prototype | `READY_FOR_USER_CHECKPOINT` |
| G01 Temporal | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` |
| G04 Drive/OAuth | `PARTIALLY_PROVEN (PASS_M1_SCOPE)` |
| G07 Compatibility | `SMOKE_COMPATIBILITY_PASS_M1_SCOPE` |
| M2 | `NOT AUTHORIZED` |
| M3 / Module A | `NOT AUTHORIZED` |

Toàn bộ các work package M1 (`M1-P0 → M1-P6`) đã hoàn thành và đạt PASS 100% sau khi khắc phục triệt để các phát hiện kiểm toán độc lập. Tổng cộng 83 passed, 1 skipped (coverage >91%), 77 artifacts có hash toàn vẹn trong manifest, 0 secret rò rỉ, và Báo cáo Kiểm toán Exit Gate `docs/milestones/m1-proof/audit-r3.md` đã hoàn tất. Milestone M1 hiện đang ở trạng thái `READY_FOR_USER_CHECKPOINT`. Không được bắt đầu M2, M3 hoặc Phân hệ A trước khi người dùng xác nhận phê duyệt checkpoint M1.

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

## Trạng thái sau M1-P6 & Hoàn thành Khắc phục Kiểm toán Độc lập (Audit R3)
M1-P0 đến M1-P6 đã hoàn tất `PASS` toàn bộ 83 passed, 1 skipped manual tests. G01 và G04 đều đạt `PARTIALLY_PROVEN (PASS_M1_SCOPE)` (với bằng chứng tích hợp exact `temporal-server.exe` 1.31.2 binary qua gRPC 7233 và ADR-0009 Cloud Token Broker an toàn không lưu refresh token trên đĩa) và G07 đạt `SMOKE_COMPATIBILITY_PASS_M1_SCOPE` (strict equality + ffprobe WAV duration) với đầy đủ bằng chứng, nhật ký thực thi, hash SHA-256 và Báo cáo Kiểm toán `docs/milestones/m1-proof/audit-r3.md`. Milestone M1 sẵn sàng cho User Checkpoint (`READY_FOR_USER_CHECKPOINT`); M2/M3/Module A tiếp tục bị khóa (`NOT AUTHORIZED`) theo quy định.


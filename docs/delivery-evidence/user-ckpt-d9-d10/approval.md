# USER-CKPT-D9-D10: bản ghi duyệt của user

## Trạng thái

- Quyết định: user ĐÃ DUYỆT D9 và D10 (có điều kiện nêu bên dưới).
- Ngày quyết định: 2026-10-19.
- Nguồn: user (Dashboard).

## Quyết định nguyên văn của user

> «D10: giữ mục 3.1; thêm temporalio==1.32.0; hoãn các gói còn lại theo đề xuất Control; cryptography giữ hai bộ thư viện (46.0.5 / 50.0.1). D9: duyệt R1–R10, PostgreSQL chỉ mở 127.0.0.1; FFmpeg, Temporal và digest postgres tạm ghi pending, cung cấp khi bước vào CP7.».

## Kế hoạch được duyệt

- Đường dẫn: `docs/implementation/convergence/plan.md`
- sha256: `cdb9e735d6793be332038f30341aab2a69d163a7859d1c6e03c40daeb22b7f47`
- Cách tính: sha256 theo byte của tệp trong worktree tại thời điểm ghi bản này.

## Diễn giải phạm vi (chỉ trích từ quyết định, không mở rộng)

- D10 (danh sách thư viện, plan.md mục 3): giữ nguyên mục 3.1; thêm đúng `temporalio==1.32.0` (mục 3.2); các gói còn lại hoãn, chỉ vào lockfile khi POC hoặc CP7 chứng minh cần, bằng dependency_slice riêng; `cryptography` giữ hai bộ thư viện độc lập `46.0.5` (src/controlplane) và `50.0.1` (uv.lock gốc), không thống nhất phiên bản (mục 3.3).
- D9 (dựng lại runtime khoá, plan.md mục 4): duyệt R1–R10; PostgreSQL chỉ mở trên `127.0.0.1`.

## Mục pending (chưa được cung cấp, không coi là đã duyệt hay đã có)

| Mục | Trạng thái | Khi nào cung cấp |
|---|---|---|
| sha256 FFmpeg | pending | khi bước vào CP7 |
| sha256 binary Temporal | pending | khi bước vào CP7 |
| digest image PostgreSQL | pending | khi bước vào CP7 |

## Giới hạn

- Gói này chỉ ghi lại quyết định của user; không đổi `docs/implementation/convergence/plan.md`, lockfile hay manifest phụ thuộc.
- Không có giá trị nào ở bảng pending được suy đoán hoặc điền thay user.

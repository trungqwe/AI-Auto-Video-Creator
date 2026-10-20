# Báo cáo IMPL-PLAN-ADAPT

- **Ngày**: 20/10/2026
- **Cơ sở**: HEAD `d9d23586d3af1fa6b2f2b6b741f3bd77e2178ab7`
- **Tệp tạo**: `docs/implementation/adapt/plan.md`, `docs/implementation/adapt/slices.md`, `docs/delivery-evidence/impl-plan-adapt/report.md`
- **Phạm vi**: chỉ `docs/implementation/adapt/**` và `docs/delivery-evidence/impl-plan-adapt/**`; không chạm `src/**`, `migrations/**`, `.ai-pm/**`, lockfile, `docs/milestones/**/evidence/**`.

## Lệnh đã chạy

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | đạt (không output) |
| Probe `python -c` kiểm `plan.md` và `slices.md` theo lệnh kiểm bắt buộc của task | 0 | đạt (13 slice hợp lệ) |

## Kết quả

- `slices.md` có 13 slice: `ADAPT-DEPS`, `ADAPT-A`, `ADAPT-D`, `ADAPT-E`, `ADAPT-E-MEDIA`, `ADAPT-F`, `ADAPT-J`, `ADAPT-I`, `ADAPT-CONFIG`, `ADAPT-WIRE`, `ADAPT-SEED`, `ADAPT-PROD`, `ADAPT-LAUNCH`.
- `plan.md` gồm mười mục: phạm vi, quyết định đã có, thư viện và ghim runtime, vị trí mã và DAG, chi tiết phân hệ A, D, E, F, I, J, hồ sơ production và launcher, bảng cấu hình production, mục CP7, mục mở, ngoài phạm vi.

## Mục mở và giả định

- OI-ADAPT-01 đến OI-ADAPT-12 nằm ở `plan.md` mục 9; phiên bản `kokoro-onnx==0.4.9`, hash trọng số model và cổng 9Router là giá trị chờ Control xác minh, không ghi là đã xác minh.
- Không có mục nào được ghi là user đã duyệt; hai điểm dừng user và D5 nằm ở `plan.md` mục 9.1.

## Nguồn đã đọc

sha256 tính trên byte tệp trong worktree tại HEAD d9d23586d3af1fa6b2f2b6b741f3bd77e2178ab7.

| Nguồn | Đường dẫn | sha256 |
| --- | --- | --- |
| Convergence plan | docs/implementation/convergence/plan.md | dc998d8cc60d7f8bd2141788f7ac83278b3d084be12912a1e5d920bffa1501d5 |
| Kế hoạch A | docs/implementation/a/plan.md | 9e4890e7e80ca7f4a6ba0d41a81f5e25f7470c41c519b40a09fe67b8185e4b38 |
| Kế hoạch D | docs/implementation/d/plan.md | b03bfa87b78f4b2b6263b8776d903903c531b95852a9da5a738c234bba5eb9ac |
| Kế hoạch E | docs/implementation/e/plan.md | 5964e271759fbbe97dacca12058424066b3dc28b3f670892657c2b63a25ac2e2 |
| Kế hoạch F | docs/implementation/f/plan.md | 3d4240949670472c76349d83b7702a4ef294d2daf206a6e50b07646c6e6cf3fb |
| Kế hoạch I | docs/implementation/i/plan.md | bfa2a1fa655c09c2290cddf0e1a586718665ca89b3b18af6bb538b3bd949cb79 |
| Kế hoạch J | docs/implementation/j/plan.md | b196ef3869970e600bb71495a223d5db0d3356e1c456158193dc5b13bc1edbe9 |
| Nghiên cứu công nghệ | docs/05-technology-research.md | 272686b8b4f48170b77f1cd6cd51dc794ae5887da39330b984f97b663ed70586 |
| Roadmap | docs/11-roadmap.md | 9483b57d096659b62f29512b3181e44c07178db842c82b9e0bd075e7028d8bfb |
| Lệnh spec IMPL-PLAN-ADAPT | D:/AI_SETUP/project_controller/state/portfolio/lanes/lane-impl-plan-adapt/specs/IMPL-PLAN-ADAPT.md | 2cab5a071545f62017e3a455e7dfed9207bf41fe395fd310a0c6eb8bcc20f5ca |

## Thư viện đề xuất kèm lý do

| Gói (`tên==phiên bản`) | Giấy phép | Dùng cho | Nguồn phiên bản |
| --- | --- | --- | --- |
| `feedparser==6.0.14` | BSD-2-Clause | parse RSS và Atom (A) | `docs/05-technology-research.md` dòng 116 (release 30-07-2026) |
| `trafilatura==2.2.0` | Apache-2.0 | trích nội dung chính (A) | `docs/05-technology-research.md` dòng 136 |
| `faster-whisper==1.2.1` | MIT | căn thời gian từng từ (E) | `docs/05-technology-research.md` dòng 227 |
| `kokoro-onnx==0.4.9` | MIT (trọng số Kokoro: Apache-2.0) | TTS cục bộ (E) | ứng viên của Orchestrator; tài liệu chưa ghi phiên bản (OI-ADAPT-01) |

## Quyết định D8 của kế hoạch này

- D8-ADAPT-01: danh sách endpoint được duyệt lấy từ cấu hình J qua đường dựng mới của `ApprovedEndpointRegistry`; `DEFAULT_APPROVED_ENDPOINTS` giữ làm nền test (BL-CV-04).
- D8-ADAPT-02: phiên cho UI đã dựng đi qua `GET /launch` ở máy chủ, không sửa UI, spec M2 hay `ui/dist` (BL-CV-13).
- D8-ADAPT-03: tệp adapter mới của A, D, E, F luôn là `real_<tên>.py`; không dùng glob thư mục.
- D8-ADAPT-04: mã kiểm sha256 FFmpeg có hai bản độc lập ở E và F để không import chéo phân hệ.
- D8-ADAPT-05: mỗi tham số production có `value`, `reason`, `basis`; giá trị không đo được là `CONSERVATIVE_DEFAULT` và nằm trong runbook.

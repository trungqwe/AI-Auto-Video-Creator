# Quy chế Quản lý Overlay Tài liệu & Bảo tồn Bằng chứng Lịch sử (DOC-08)

> **Mã Tài liệu:** `DOC-08`
> **Chủ quản:** Control / Supreme Governance Auditor
> **Trạng thái:** `ACTIVE_ACCEPTED`
> **Thuộc chiến dịch:** Triển khai Kiến trúc 2 (Parallel Wave/DAG Architecture)

---

## 1. Nguyên tắc Phân lập Overlay (Separation of Overlay and Base)

Trong quá trình phát triển theo mô hình Wave/DAG, hệ thống áp dụng cơ chế lớp phủ tài liệu (documentation overlay):

1. **Approved Base Bất biến:**
   - Approved base commit ban đầu: `4a7c8c921b7e05066505d51b168a02c3fde61317`.
   - Approved base Phase A: `17dfe2b61e282a2e22e9eeefa7448ae49a1d0622`.
   - Mọi thay đổi trong chiến dịch này được thực hiện trên nhánh độc lập `DAG-implement-plan` tách từ approved base Phase A.
2. **Phân tách Rõ rệt Committed vs Dirty Overlay:**
   - Chỉ các commit được ký duyệt chính thức mới được coi là candidate hợp lệ.
   - Thư mục làm việc (working tree) trước và sau khi chạy kiểm thử hoặc validator phải giữ trạng thái sạch (`working tree clean`). Mọi artifact trung gian (tệp tạm, `.pyc`, cache) phải được dọn dẹp hoặc đưa vào `.gitignore`.

---

## 2. Bảo tồn Bất biến Hồ sơ Bằng chứng Lịch sử (Evidence Immutability)

- **Cấm Tuyệt đối Sửa đổi Bằng chứng Đã Nghiệm thu:**
  - Toàn bộ hồ sơ bằng chứng trong `docs/milestones/**/evidence/**` được khóa bất biến dưới quyền `EvidenceAuthority` thông qua lock `LOCK-ACCEPTED-EVIDENCE`.
  - Mọi thao tác cấp lease sửa đổi (mutation lease), sửa nội dung, xóa tệp hoặc thay đổi mã băm SHA-256 đối với hồ sơ bằng chứng đã nghiệm thu đều bị từ chối fail-closed.
- **Bảo toàn Hash Chứng nhận Bundle:**
  - Báo cáo kiểm định `.validation-report.json` và mã băm SHA-256 của các thành phần kiến trúc được bảo toàn nguyên vẹn cho mục đích đối soát lịch sử.

---

## 3. Ranh giới Thay đổi Cho phép trong Campaign Tài liệu

Chiến dịch kỹ thuật DOC-00..DOC-10 chỉ được phép tác động trên các phạm vi tài liệu và cấu hình đã được phê duyệt:
- `docs/adr/0013-wave-dag-development.md` & `docs/adr/README.md`
- `docs/parallel-delivery/**`
- `docs/modules/capability-*.md`
- `docs/11-roadmap.md` & `docs/12-pre-code-checklist.md`
- `README.md` & `HANDOFF.md`

**Các vùng cấm tuyệt đối:**
- Không sửa mã nguồn sản phẩm trong `src/**`.
- Không sửa bộ kiểm thử runtime trong `tests/**`.
- Không sửa chuỗi migration cơ sở dữ liệu `src/**/migrations/**` hoặc các tệp `.sql`.
- Không sửa các tệp khóa phụ thuộc môi trường: `pyproject.toml`, `uv.lock`, `package-lock.json`.
- Không sửa code runtime của Milestone 2 cũ: `delivery_engine.py`, `validate.py`, `test_negative_fixtures.py`, `test_host_boundary_harness.py`.

---

## 4. Chốt An toàn Bất biến (Fail-Closed Gates)

| Hạng mục | Trạng thái bảo toàn | Ghi chú |
|---|---|---|
| Milestone M1 | `ACCEPTED / CLOSED` | Đã nghiệm thu toàn diện tại Checkpoint 13-09-2026 |
| Milestone M2-P1..P7B | `ACCEPTED_CLOSED` | Giữ nguyên baseline mã nguồn và tooling |
| Milestone M2-P8/P9 | `LOCKED` | Không tự ý mở implementation hay viết test RED |
| Milestone M3 và Phân hệ A | `NOT AUTHORIZED` | Tiếp tục khóa chặt tới khi M2 qua exit gate |
| Kích hoạt sản xuất | `PRODUCTION_ACTIVATION_BLOCKED` | Giữ nguyên khóa fail-closed cấp OS/hạ tầng |

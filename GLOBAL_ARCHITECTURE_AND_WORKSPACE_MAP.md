# BẢN ĐỒ TOÀN CẢNH HỆ THỐNG & ĐỊNH HƯỚNG KIẾN TRÚC
# (GLOBAL ARCHITECTURE & WORKSPACE MAP)

> **Dành cho mọi Agent / LLM tiếp nhận dự án:** 
> Tài liệu này mô tả cấu trúc tổng thể, phân định ranh giới giữa các thư mục trên hệ thống, tình trạng 2 bộ kiến trúc (Bộ 1 Tuần tự vs Bộ 2 Song song), và các quy tắc kiểm soát an toàn nghiêm ngặt.
> **BẮT BUỘC ĐỌC FILE NÀY TRƯỚC KHI THỰC HIỆN BẤT KỲ THAO TÁC NÀO.**

---

## 1. PHÂN ĐỊNH 3 THƯ MỤC TRÊN Ổ ĐĨA D:\

Trên hệ thống máy chủ phát triển, có 3 vị trí thư mục riêng biệt cần phân biệt tuyệt đối:

### 1. `D:\AI_SETUP` — Control Plane (Trung tâm Điều phối & Giám sát)
- **Vai trò:** Trung tâm đầu não quản trị và điều phối đa agent (Supervisor / Coordinator / Governance).
- **Thành phần cốt lõi:**
  - `ORCA_DELY_SUPERVISOR.js`: Daemon điều phối tự động vòng lặp Worker (Codex) ➔ Sol-Lead (Claude) ➔ Astra-Lead (Claude) có cờ phân loại `campaignType: documentation` hoặc `code`.
  - `ARCHITECTURE_V1_SEQUENTIAL_FALLBACK.md`: Runbook quay về an toàn nếu cần rollback về Bộ 1.
  - `ARCHITECTURE_V2_PARALLEL_GUIDE.md`: Hướng dẫn vận hành Bộ 2 theo Wave/DAG.
  - Các cấu hình supervisor (`DAG_TECHNICAL_DELIVERY.config.json`), checklist theo dõi (`DAG_TECHNICAL_DELIVERY_CHECKLIST.md`), trạng thái máy hữu hạn state machine (`supervisor/state/`), nhật ký kiểm toán (`logs/`).
- **Quy tắc:** Chỉ chứa công cụ điều phối, tài liệu quản trị và script kiểm toán; **KHÔNG** chứa mã nguồn sản phẩm thực thi.

### 2. `D:\TU_CODE\AI-Auto-Video-Creator` — Execution Plane (Dự án Sản phẩm Gốc)
- **Vai trò:** Kho lưu trữ mã nguồn và tài liệu sản phẩm chính thức (Active Codebase / Target Repository), được kết nối trực tiếp với GitHub: `https://github.com/trungqwe/AI-Auto-Video-Creator.git`.
- **Nhánh `main` hiện tại:** Đã hợp nhất hoàn tất Bộ 2 (Wave/DAG Architecture) kèm 11 gói tài liệu kỹ thuật DOC-00..DOC-10 (Tag: `architecture-v2-main-merged` và `architecture-v2-technical-delivery-approved`).
- **Nhánh `backup/sequential-architecture-v1`:** Lưu trữ độc lập trạng thái Bộ 1 tuần tự (Tag: `architecture-v1-sequential-backup` tại SHA `4a7c8c9...`).
- **Quy tắc:** Mọi can thiệp vào mã nguồn sản phẩm, kiến trúc tài liệu của sản phẩm phải diễn ra tại đây hoặc qua worktree được supervisor giám sát.

### 3. `D:\AI Auto Video Creator` — Offline Cold Backup (Kho Lưu trữ Đóng băng của Người Dùng)
- **Vai trò:** Bản sao lưu tĩnh (cold backup) của Bộ 1 tuần tự, được người dùng sao chép từ trước khi dùng Orca điều phối nhằm phòng ngừa rủi ro hỏng hóc.
- **CẢNH BÁO QUAN TRỌNG CHO MỌI LLM / AGENT:**
  > ⚠️ **TUYỆT ĐỐI KHÔNG CAN THIỆP VÀO THƯ MỤC NÀY!**
  > - Không mở terminal, không chạy lệnh, không sửa đổi, không tạo file và **TUYỆT ĐỐI KHÔNG XÓA**.
  > - Đây là tài sản sao lưu tĩnh độc lập của người dùng, nằm ngoài phạm vi điều phối của mọi công cụ tự động.

---

## 2. BẢN ĐỒ 2 BỘ KIẾN TRÚC TRONG DỰ ÁN GỐC

| Tiêu chí | Bộ 1: Kiến trúc Tuần tự (Sequential Fallback) | Bộ 2: Kiến trúc Song song (Parallel Wave/DAG) |
| :--- | :--- | :--- |
| **Mục đích** | Kế hoạch cũ phát triển tuần tự từng module. Là "phao cứu sinh" để quay về nếu phát triển song song thất bại. | Kế hoạch phát triển song song theo Wave và DAG. Tối ưu hóa token, giải phóng tắc nghẽn, triển khai đa agent độc lập. |
| **Git Tag** | `architecture-v1-sequential-backup` & `checkpoint-v1-sequential-pre-dag-merge` | `architecture-v2-technical-delivery-approved` & `architecture-v2-main-merged` |
| **Git Branch** | `backup/sequential-architecture-v1` | `main` (và nhánh `DAG-implement-plan`) |
| **Base Commit** | `4a7c8c921b7e05066505d51b168a02c3fde61317` | Merge commit `7bef157...` (tích hợp `a880faf...`) |
| **Trạng thái Duyệt** | Đã nghiệm thu khép lại M1, M2-P1..P7B | Đã đạt Sol-Lead ACCEPT & Astra-Lead PASS 100% (DOC-00..DOC-10) |
| **Tài liệu cốt lõi** | `ARCHITECTURE_V1_SEQUENTIAL_FALLBACK.md` | `DAG-implement-plan.md`, `ARCHITECTURE_V2_PARALLEL_GUIDE.md` |
| **Khi nào sử dụng?** | Chỉ kích hoạt khi có chỉ đạo rollback của User/Architecture Owner. | Đang hoạt động mặc định trên `main`. Toàn bộ công việc tiếp theo phát triển trên bộ này. |

---

## 3. CẤU TRÚC 11 GÓI TÀI LIỆU KỸ THUẬT BỘ 2 ĐÃ HỢP NHẤT VÀO `main`

Toàn bộ 11 gói công việc kỹ thuật đã được hợp nhất vào `D:\TU_CODE\AI-Auto-Video-Creator` và đã được xác thực 100% bằng bộ kiểm tra tĩnh `validate-docs-plan.py`:

1. **DOC-00 (Baseline & Scope)**: Khóa approved base `4a7c8c9...` và Phase A `17dfe2b...`; lập inventory file và bảo vệ path cấm (`HANDOFF.md`, `DAG-implement-plan.md`).
2. **DOC-01 (Chính sách Wave/DAG)**: `docs/adr/0013-wave-dag-development.md` phân định 4 trạng thái thẩm quyền (NOT AUTHORIZED, SPECIFIED, AUTHORIZED FOR IMPLEMENTATION, ACCEPTED_CLOSED).
3. **DOC-02 (Biên Giao tiếp & Contracts)**: `docs/parallel-delivery/contract-registry.yaml` chuẩn hóa các giao diện CT-API, CT-BAT, Batches query và State machine.
4. **DOC-03 (Phân rã Capability B–J)**: `docs/modules/capability-*.md` cho 7 capability độc lập (B, C, D, E, F, G, J).
5. **DOC-04 (Ownership & DAG Executable)**: `docs/parallel-delivery/task-dag.yaml`, `ownership-and-locks.yaml`, `schedule-policy.yaml` đảm bảo đồ thị phi chu trình (acyclic) và khóa single-writer.
6. **DOC-05 (Acceptance Matrix & Phân tầng Test)**: `docs/parallel-delivery/acceptance-matrix.yaml`, `traceability.md`.
7. **DOC-06 (Roadmap & Agent Guides)**: `docs/11-roadmap.md`, `12-pre-code-checklist.md`, `HANDOFF.md`.
8. **DOC-07 (Doc Validator)**: `docs/parallel-delivery/validate-docs-plan.py` kiểm tra cấu trúc 11 file, cú pháp YAML, UTF-8/LF và chu trình DAG.
9. **DOC-08 (Overlay Tài liệu & Bảo Toàn Evidence)**: `docs/parallel-delivery/overlay-and-evidence.md` bảo toàn trạng thái M2-P8/P9 LOCKED.
10. **DOC-09 (Preflight & Nghiệm Thu)**: `docs/parallel-delivery/preflight-and-acceptance.md`.
11. **DOC-10 (Tương thích Runtime Điều phối)**: `docs/parallel-delivery/runtime-compatibility.md` cấu hình model route, merge queue và runtime compatibility.

---

## 4. QUY TẮC AN TOÀN TUYỆT ĐỐI CHO MỌI AGENT / LLM

1. **NGHIÊM CẤM TỰ Ý XÓA**:
   - Tuyệt đối **KHÔNG** chạy các lệnh xóa đệ quy (`rm -rf`, `Remove-Item -Recurse`, `git clean -fdx`) trên các thư mục không được chỉ định rõ ràng.
   - Bất kỳ thao tác xóa nào có nguy cơ ảnh hưởng đến file hoặc dữ liệu người dùng phải hỏi ý kiến User trước và không được tự ý thực hiện.
2. **BẢO VỆ CHỐNG DERAILMENT KIỂM THỬ**:
   - Khi làm việc với tài liệu Markdown/YAML của Bộ 2: **TUYỆT ĐỐI KHÔNG** chạy `python validate.py` (vốn là validator kiểm tra 404 test fixture của code runtime Milestone 2 cũ).
   - Chỉ chạy validator dành riêng cho tài liệu: `python docs/parallel-delivery/validate-docs-plan.py` và `git diff --check`.
3. **CÁC CHỐT BẢO VỆ BẤT BIẾN**:
   - `M2-P8/P9`: Giữ nguyên `LOCKED` cho đến khi User cấp thẩm quyền triển khai sản phẩm.
   - `M3` và Phân hệ A: `NOT AUTHORIZED`.
   - `ProductionActivationGate`: Duy trì `PRODUCTION_ACTIVATION_BLOCKED`.

# Implementation Plan — Tái cấu trúc tài liệu để phát triển theo Wave/DAG

> **Trạng thái:** ĐỀ XUẤT ĐỂ AUDIT — chưa sửa file, chưa dispatch worker, chưa mở implementation authority mới.
> **Mục tiêu:** Giữ nguyên kiến trúc sản phẩm hiện có, nhưng thay cách tổ chức và điều hành phát triển:
> Chia theo capability/work package có contract độc lập; chạy ngay khi đủ dependency và tài nguyên; tích hợp liên tục qua merge queue. Không bắt cả wave chờ hạng mục chậm nhất, không đợi cuối dự án mới ráp.
> **Wave** dùng để trình bày roadmap và phê duyệt phạm vi. **DAG** quyết định việc nào thực sự có thể chạy đồng thời.

---

## 1. Baseline và những giới hạn đã kiểm tra

- **Worktree:** `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\DAG-implement-plan`
- **Nhánh:** `DAG-implement-plan` (rẽ nhánh từ exact approved base Phase A `17dfe2b61e282a2e22e9eeefa7448ae49a1d0622`)
- **Approved base ban đầu:** `4a7c8c921b7e05066505d51b168a02c3fde61317`
- **Approved base Phase A / exact source commit:** `17dfe2b61e282a2e22e9eeefa7448ae49a1d0622`

### Phân lớp approved base và ranh giới thay đổi

- **Approved base ban đầu:** `4a7c8c921b7e05066505d51b168a02c3fde61317` — baseline đã được phê duyệt trước Phase A.
- **Approved base của Phase A:** `17dfe2b61e282a2e22e9eeefa7448ae49a1d0622` — exact commit sau Sol `ACCEPT` và Astra `PASS`, là commit mà nhánh `DAG-implement-plan` rẽ ra.
- **Exact source commit của campaign:** trùng với approved base Phase A ở trên; campaign chỉ thêm tài liệu `DAG-implement-plan.md`, không thay đổi approved base.

### Ranh giới và trạng thái hiện hành bắt buộc bảo toàn

| Hạng mục | Trạng thái |
| :--- | :--- |
| **M1** | ACCEPTED/CLOSED |
| **M2-P1..P7B** | ACCEPTED_CLOSED |
| **M2-P8/P9** | LOCKED |
| **M3 và Phân hệ A** | NOT AUTHORIZED |
| **Parallel delivery** | Nền tảng đã được audit; không tự cấp quyền triển khai sản phẩm |
| **Production activation** | `PRODUCTION_ACTIVATION_BLOCKED` |

> [!IMPORTANT]
> Việc phê duyệt wave/DAG là căn cứ để thiết kế lại kế hoạch. Tuyệt đối không diễn giải thành quyền tự mở P8/P9 hoặc M3–M7 trong bước này.

---

## 2. Các vấn đề thực tế cần xử lý

1. Roadmap đang biểu diễn critical path chủ yếu tuần tự `M2 → M3 → M4 → M5 → M6 → M7`.
2. QR-MNT-003 hiện yêu cầu xác nhận phân hệ hiện tại trước khi chuyển phân hệ tiếp theo.
3. Chỉ Phân hệ A có bộ `spec.md` và `implementation-plan.md` riêng trong `docs/modules`.
4. P8 yêu cầu Operations, Batches, Jobs và cập nhật trạng thái thật; query port hiện chưa có Batches query.
5. `PostgresControlQueries._operation_row()` trả `status: "accepted"` cố định. Đã có `map_operation_view()` ánh xạ execution state, nhưng đường query đang đọc receipt và stream summary. Cần nối nguồn execution state authoritative; không suy trạng thái từ một event bất kỳ.
6. Validator của experiment có allowlist hẹp; sửa contracts, quality requirements và milestone plans hiện sẽ vượt scope.
7. `ownership-and-locks.yaml` có lock độc quyền cả `docs/parallel-delivery/**`; cách này bảo vệ bundle hiện tại nhưng không phù hợp để nhiều task tài liệu cùng sửa bundle.
8. Reference engine/validator và hướng dẫn trong candidate còn kiểm tra route Sol `cx/gpt-5.6-sol`; `AI_SETUP` hiện dùng `cx/gpt-6.1-sol`.
9. Supervisor hiện hành quản lý một `pendingDispatch`; không thể coi việc có DAG là bằng chứng runtime đã điều phối nhiều task đồng thời.
10. `HANDOFF.md` vẫn ghi chờ review tiếp theo, trong khi durable state đã ghi Astra PASS.

### Hai nguyên tắc chỉnh lại cốt lõi:
- **Không cần đóng toàn bộ một wave mới cho một nhánh độc lập đi tiếp.**
- **Không cần xây xong toàn bộ API trước khi code domain của A–F.** Domain có thể phát triển theo typed ports và frozen contracts; API và E2E thật phải hoàn tất trước khi nghiệm thu lát cắt tương ứng.

---

## 3. Mục tiêu và các bất biến không được thay đổi

### 3.1. Mục tiêu phát triển
Tối ưu thời gian hoàn thành sản phẩm, không tối ưu riêng số worker đang chạy.
Ưu tiên:
1. Giảm dependency giả giữa các milestone.
2. Cho producer và consumer phát triển độc lập theo contract đã khóa.
3. Giảm thời gian giữ lock và chờ tài nguyên.
4. Phát hiện sai tích hợp sớm.
5. Giảm vòng remediation bằng brief cụ thể và counterexample rõ ràng.
6. Có checkpoint/resume và rollback theo task.
7. Không để một task bị chặn làm dừng nhánh độc lập.

### 3.2. Mục tiêu sản phẩm giữ nguyên
Không thay charter để thuận tiện song song hóa:
- Video tiếng Anh 61–70 giây.
- Đủ visual hook, audio hook và thumbnail trong hook.
- Karaoke theo từng từ.
- Đúng quy tắc snapshot, góc kể và biến thể.
- Cloud tiếp tục thu thập khi desktop offline.
- Không xóa output trước khi sync được xác minh.
- Completion, media usage và batch capacity giữ đúng tính nguyên tử.
- UI tiếng Việt, desktop 1080p+.
- Mục tiêu 100 video hợp lệ/12 giờ và ngân sách đã chốt vẫn phải chứng minh bằng gate thật.

---

## 4. Mô hình điều hành phát triển

### 4.1. Tách bốn loại dependency
Mỗi cạnh DAG phải chỉ rõ loại và bằng chứng để giải phóng:

| Loại Dependency | Ví dụ | Điều kiện cho consumer chạy |
| :--- | :--- | :--- |
| **Contract dependency** | F cần cấu trúc voice/timing | Contract đúng revision đã freeze |
| **Implementation dependency** | E timing cần voice thật để tích hợp | Producer đã integrated và verified |
| **External-proof dependency** | I cần Drive/OAuth thật | Proof thuộc phạm vi cần dùng đã đạt |
| **Authority dependency** | M3 chưa được cấp quyền | Quyết định phê duyệt có phạm vi và provenance |

### 4.2. Hai mức readiness khác nhau
- **Có thể phát triển độc lập:** Có authority cho task, contract & oracle đã khóa, owned paths rõ, có fixture hợp lệ / producer port tương thích, không cần runtime capability chưa có để viết code được giao.
- **Có thể nghiệm thu tích hợp:** Producer thật đã integrated, adapter/runtime bắt buộc đã được chứng minh, test không thay external gate bằng mock, evidence gắn exact candidate.

---

## 5. Kế hoạch triển khai tái cấu trúc (DOC-00 đến DOC-11)

### DOC-00 — Khóa baseline và change manifest
- Pin approved base ban đầu (`4a7c8c9...`), approved base Phase A/exact source commit (`17dfe2b...`) và audit references.
- Lập inventory file liên quan: phân loại current authority, active plan, future template, historical audit, open items.
- Khóa các path cấm: source sản phẩm, tests sản phẩm, migration, dependency lockfiles, evidence accepted/rejected lịch sử.
- Làm việc trên nhánh riêng `DAG-implement-plan`.

### DOC-01 — Chốt chính sách phát triển theo DAG và Authority
- Cập nhật `docs/03-quality-requirements.md`, `docs/11-roadmap.md`, `docs/12-pre-code-checklist.md`, `docs/parallel-delivery/operating-model.md`.
- Đề xuất ADR mới: `docs/adr/0013-wave-dag-development.md`.
- Đề xuất amendment QR-MNT-003: Cho phép phát triển song song các work package thuộc phạm vi đã duyệt; nghiệm thu phân hệ và mở milestone mới vẫn yêu cầu checkpoint.
- Phân biệt 4 trạng thái: (1) Được lập kế hoạch, (2) Được phép implementation, (3) Được phép integration, (4) Được phép production activation.

### DOC-02 — Đóng các biên giao tiếp (Contracts) và khoảng thiếu
- File chính: `docs/09-contracts/*` và `docs/parallel-delivery/contract-registry.yaml`.
- Đóng Batches query contract (list/detail/filter/pagination).
- Đóng thiết kế Operation execution state (tách command receipt `accepted` khỏi execution state `running`, `succeeded`, `failed`).
- Khóa interface: A–B (DocumentPackage), B–D (Article snapshot), C–I (Metadata catalog vs Artifact byte integrity), D–E–F (Script, Voice, Word Timing, Render Package), G–C–I (Completion UoW), J–Provider.

### DOC-03 — Phân rã A–J thành work package cụ thể
- Cập nhật bộ spec/plan của Phân hệ A.
- Tạo bộ spec/plan cho B–J theo capability (không chia đơn giản thành backend/frontend).
- Mỗi package phải có ID ổn định, DoR, DoD, invariant refs, allowed/forbidden paths, targeted tests, counterexample, rollback.

### DOC-04 — Ownership, Resource Policy và DAG Executable
- Cập nhật `task-dag.yaml`, `ownership-and-locks.yaml`, `schedule-policy.yaml`.
- Tách ownership theo path/capability, tránh lock toàn bộ module.
- Single-writer cho composition root, contract source, migration ledger, dependency lockfile.
- Rõ ràng hóa tài nguyên CPU, RAM, GPU, DB connection budget.

### DOC-05 — Acceptance Matrix và Test Strategy
- Cập nhật `docs/10-test-strategy.md`, `acceptance-matrix.yaml`, `traceability.md`.
- Map rõ ràng: Requirement → Capability → Task → Contract → Test → Evidence → Release Gate.
- Phân tầng test: Unit/Domain → Contract → Integration → Full Regression / External Proof.

### DOC-06 — Roadmap, Checklist và Hướng dẫn Agent
- Đồng bộ `docs/11-roadmap.md`, `docs/12-pre-code-checklist.md`, `README.md`, `HANDOFF.md`, `AGENTS.md`, `CLAUDE.md`.
- Giữ M0–M7 để bảo toàn traceability; bổ sung delivery DAG capability song song.

### DOC-07 — Validator riêng cho Campaign tài liệu
- Không nới validator experiment cũ. Tạo change profile riêng kiểm tra exact base/candidate, diff overlay, protected evidence hashes, UTF-8, DAG cycle, ownership overlap.

### DOC-08 — Wave/DAG mở rộng: Overlay tài liệu và bảo toàn evidence
- Đây là work package mở rộng theo Wave/DAG, có contract độc lập và không phụ thuộc việc mở implementation của P8/P9 hoặc M3.
- Tạo overlay chỉ dành cho campaign tài liệu; không sửa trực tiếp approved base hoặc các tệp evidence lịch sử.
- Gắn từng thay đổi vào owner, contract, invariant, gate và rollback; mọi khoảng chưa đủ bằng chứng phải giữ trạng thái `PENDING`/`LOCKED`, không suy diễn thành `PASS`.
- Kiểm tra diff chỉ chứa các path được campaign cho phép và xác nhận source implementation, migration, dependency lockfile cùng accepted/rejected evidence không bị mở.
- Chốt an toàn: `M2-P8/P9` vẫn `LOCKED`; work package này không tự cấp RED, implementation, integration hoặc production activation authority.

### DOC-09 — Wave/DAG mở rộng: Preflight và đóng gói hồ sơ nghiệm thu
- Đây là work package mở rộng theo Wave/DAG, có contract độc lập và chỉ tạo hồ sơ kiểm chứng cho campaign tài liệu.
- Chạy preflight tĩnh trên exact candidate: kiểm tra đủ DOC-00..DOC-11, liên kết tham chiếu tồn tại, không có cycle DAG, không có ownership overlap trái phép và không có secret/encoding lỗi.
- Tạo manifest provenance ghi exact base/candidate SHA, change profile, validator version, kết quả kiểm tra và các gate còn `PENDING`/`LOCKED`; preflight không có quyền thay đổi task state hoặc cấp implementation/production authority.
- Chỉ chuyển sang kiểm tra runtime điều phối và review độc lập khi preflight hoàn tất; lỗi preflight là `BLOCKED`, không được bỏ qua để tiếp tục.
- Chốt an toàn: `M2-P8/P9` vẫn `LOCKED`; work package này không tự cấp RED, implementation, integration hoặc production activation authority.

### DOC-10 — Tương thích Runtime Điều phối
- Kiểm tra route model: Đối chiếu reference engine/validator (`cx/gpt-5.6-sol`) với runtime supervisor hiện hành (`cx/gpt-6.1-sol`).
- Kiểm tra hạ tầng multi-task: bảo đảm supervisor hỗ trợ state, recovery và merge queue.

### DOC-11 — Review và Nghiệm thu Campaign
- Sol review trên exact documentation candidate (diff scope + counterexamples -> validation).
- Astra supreme audit tính nhất quán, phân quyền và attestation.
- Vòng lặp tự động chạy đến khi Astra trả `verdict: "PASS"`.

---

## 6. Tiêu chí nghiệm thu toàn bộ campaign tài liệu

- [ ] Approved base ban đầu (`4a7c8c9...`) và approved base Phase A (`17dfe2b...`) đã được Astra duyệt; evidence lịch sử không đổi.
- [ ] Charter/R01–R25 không bị mở rộng hoặc mất yêu cầu.
- [ ] Amendment QR-MNT-003 có provenance và được phê duyệt.
- [ ] Mọi capability có owner, contract, acceptance và rollback.
- [ ] Không có dependency cycle A–B–D hoặc D–E–F.
- [ ] Batches query và operation lifecycle bridge có thiết kế đầy đủ.
- [ ] P8/P9 có plan thực thi không vượt scope ngầm.
- [ ] DAG cho phép consumer đi tiếp khi đủ điều kiện, không chờ cả wave vô cớ.
- [ ] Shared files/migration/lockfiles có một writer.
- [ ] Resource capacity được đánh dấu measured hoặc pending, không giả là đã đo.
- [ ] Future packages vẫn giữ đúng authority.
- [ ] Current state tách khỏi history.
- [ ] Validator campaign không tự cấp quyền hoặc hạ gate.
- [ ] Sol review `ACCEPT` trên exact candidate.
- [ ] Astra supreme audit `PASS` trên exact candidate.

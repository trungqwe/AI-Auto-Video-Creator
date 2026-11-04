# Kế hoạch triển khai giai đoạn 2 (MC) — AIAVC phong cách tin nóng Mỹ

> Phiên bản: 04/11/2026, **bản 5**.
> - Bản 1 FAIL ở vòng audit 1 với F1 (kiểu gói và khoá lệch `reservedPaths`) và F2 (đường dẫn migration, `seed_sources.py`, tệp không khoá). Bản 2 sửa F1; bản 3 sửa nốt F2 (migration phẳng trong `migrations/`, có cặp `.rollback.sql`) và **PASS ở vòng 3** (auditor độc lập, chỉ đọc), còn 0 BLOCKER/MAJOR.
> - Bản 4 (phạm vi mới): viết lại mục 5 thành spec đúng cú pháp bộ đọc `ai_pm_plan_declarations.js`, viết lại mục 6 (DAG), thêm 6 gói backlog giai đoạn 1 (`MC-BL-*`), cập nhật theo R1, R4, R5 và prototype heatcut, thêm mục 11.
> - **Bản 5** (thay cho bản 4, phạm vi mới nên audit lại từ vòng 1): căn cứ thêm `USER_REQUIREMENTS_20261104.md` (nguồn sự thật), phỏng vấn `INTERVIEW_GD2_20261104.md` (I1–I8) và nghiên cứu R6 (kho hook), R7 (nguồn tin), R8 (kho âm), R9 (công thức kể, giọng). Thay đổi chính: chế độ cào (dropdown) tách khỏi nhãn chủ đề; thêm 4 slice `MC-SOURCE-ADAPTERS`, `MC-STORY-THREAD`, `MC-TTS-EMOTION`, `MC-TRANSITIONS`; mở rộng `MC-SOURCES`, `MC-CLASSIFY`, `MC-SCRIPT`, `MC-VOICE`, `MC-VIDEO-CLIPS`, `MC-SFX`, `MC-HOOK-ASSEMBLY`, `MC-IMAGE-MATCH`; bỏ vòng phản hồi lượt xem (I6); thêm mục 13 "Phủ P0–P2 của báo cáo"; xét lại các cạnh DAG (mục 6).
> - **Trạng thái: chờ audit vòng 1 (phạm vi mới).** Chưa được thực thi trước H6 (mục 0).
> Thay cho: `MC_IMPL_PLAN_v4_20261104.md` (bản 4, không sửa). Kết luận audit của bản 3: `MC_PLAN_AUDIT_R2_20261104.md` (G1–G4).
> Căn cứ: yêu cầu và quyết định của user ngày 04/11 (D1–D14, I1–I8), mã ở HEAD tích hợp `9c4adfa`, roadmap `docs/11-roadmap.md`, `AGENTS.md` của AI_SETUP, nghiên cứu `research/` (R1, R4–R9, heatcut).
> Người đọc: user; Control; Orchestrator và Auditor rủi ro khi kế hoạch được biên dịch.

## 0. Điều kiện trước dòng code đầu tiên

User chỉ thị: **chỉ sửa dòng code đầu tiên của giai đoạn 2 khi đã bàn giao xong AIAVC giai đoạn 1.** Trước mốc đó, mọi việc của giai đoạn 2 chỉ là tài liệu ngoài repo, đặt trong `D:/AIAVC_RESEARCH/mcgi_o/`. Không lane MC nào được mở, không sửa policy và không commit vào repo sản phẩm.

Chuỗi bàn giao giai đoạn 1 (H1–H6), mỗi bước có bằng chứng:

| Bước | Việc | Ai | Bằng chứng xong |
|---|---|---|---|
| H1 | Lane `CP7-14` chạy **mẫu 20 video** (D10; lô 100 `CP7-MEASURE-3` đã bị thu hồi, seq 949) và gộp báo cáo RG-13. | Portfolio | Báo cáo mẫu của `CP7-14` gộp; RG-13 đạt. |
| H2 | User xem mẫu 20 video trên Drive và nghiệm thu R1–R6. | User | Lời nghiệm thu của user, ghi bằng `ai-setup decide --closure`. |
| H3 | Audit cuối độc lập tiêu chí bàn giao giai đoạn 1 (Control giao Auditor chỉ đọc, theo Convergence Freeze). | Control | Receipt Auditor PASS. |
| H4 | Đỗ bản sửa tài liệu chưa commit trên main (8 tệp, cộng `docs/MC-POLICY-20261104.md`). Bản sao đã lưu ở `main_policy_patch_20261104/`; dùng `git stash push -u` trên main, đảo ngược được. User đã đồng ý main sạch. Bỏ bước này thì `merge --ff-only` ở H5 bị git từ chối. | Control, user | `git -C <main> status --short` rỗng; stash có tên `mc-policy-docs-20261104` |
| H5 | Bàn giao 4 bước theo quyết định 22/10: tag checkpoint → fast-forward `DAG-implement-plan` vào main (main là tổ tiên) → chạy lại toàn bộ kiểm → push remote. | Control | Tag, SHA main = HEAD tích hợp, log kiểm, `git push` thành công |
| H6 | Ghi bàn giao vào CHANGELOG của AI_SETUP. Đánh dấu giai đoạn 1 đóng. | Control | Commit AI_SETUP |

Bản sửa MC-POLICY đã vào nhánh tích hợp qua gói `MCDOC-POLICY` (gộp ở `3924429`, giữ `CT-PROC-005/006` và `FR-SEN-002`); `MC-ROADMAP` không áp lại.

Chỉ sau H6 mới làm W0 (mục 5). Trình tự giữ nguyên: bàn giao giai đoạn 1 (H1–H6) trước, code giai đoạn 2 sau. Sau `MC-PILOT` còn thêm một bước: **audit cuối độc lập tiêu chí nghiệm thu M8** (Control giao Auditor, theo Convergence Freeze) trước bàn giao M8.

## 1. Nguyên tắc triển khai

1. **Mở rộng module đã có, không dựng song song.** Nguồn tin nằm trong `src/source_ingestion/`. Kho hook, ảnh và âm nằm trong `src/catalog/` trên PostgreSQL; chỉ mục mới là migration `0020+` hoặc metadata của revision, không dùng JSON hay SQLite riêng. Phần dựng nằm trong `src/render/`. Kịch bản và metadata nằm trong `src/creative/`. UI dùng React ở `src/controlplane/ui/`.
2. **Cổng thành công tắc cấu hình, không xoá mã.** Mỗi cổng mà chính sách MC gỡ thành một khoá trong `tools/launcher/prod/profile.json`; mặc định đặt theo MC-POLICY. Test ghim cả hai chế độ, nên quay lại chỉ là đổi cấu hình (`config revision` mới) và không phải sửa mã.
3. **Ít thư viện mới.** Phân tích video và âm dùng `ffmpeg` đã ghim trong `tools/runtime/runtime.lock.json`: điểm cảnh `select=scene` và âm lượng tức thời `ebur128`. Không thêm librosa, PySceneDetect hay OpenCV. Thư viện mới duy nhất trong khoá chính là `yt-dlp`, vào qua `dependency_slice` ghim `yt-dlp==2026.10.26` (wheel sha256 `a05c5b5d8562f7e8a62f5334348b406af4930d56d3a65f8021d14af0e22339ae`, có hash trong `uv.lock`); cấm `latest`. Sinh SFX bằng AI không thuộc M8. Ngoại lệ có chủ đích duy nhất ngoài khoá chính là sidecar TTS cảm xúc `tools/tts_emotion` (Chatterbox, MIT; `MC-TTS-EMOTION`), có khoá Python riêng như `tools/imagegen`, khai ở `externalLockfiles`.
4. **Workflow Temporal đổi qua `workflow.patched`**, như `ILLUSTRATIONS_PATCH_ID` (`definitions.py:36-41`). Run cũ phải replay được.
5. **Đồ thị render đổi thì đổi revision fingerprint có chủ đích**, và gói sở hữu các test ghim fingerprint (mục 3).
6. **Gói đổi hành vi phải sở hữu test ghim hành vi cũ**, kèm giá trị mới đầy đủ. Đây là bài học của ADAPT-CONFIG-FIX2 và PW-G2-FIX1.
7. **Nghiệm thu bằng số đo của Control, không hỏi user giữa chừng** (D12). User chỉ xem ở nghiệm thu cuối (W5).

## 2. Ranh giới tôi không thiết kế

Kế hoạch theo chính sách nội dung của user (D1–D14) ở mọi điểm, trừ bốn điểm dưới đây. Đây là giới hạn của phần việc tôi làm, không phải cổng chất lượng của sản phẩm.

- **Không vượt cơ chế chống bot**: không stealth-plugin, không xoay proxy để né CAPTCHA, không giả dấu vân tay trình duyệt. Nguồn ảnh dùng API mở và RSS (mục 5, W3). Nguồn nào cần khoá thì chỉ chạy khi user cấp khoá.
- **Không thiết kế cách né kiểm duyệt của nền tảng.** Phản hồi sau khi user tự đăng (lượt xem, phản ứng nền tảng): user tự quan sát, tool không làm (I6).
- **Giữ che mặt trẻ em** (`minor_child` trong `image_safety`). Năm nhóm còn lại tắt theo MC-POLICY. Người chịu rủi ro ở đây là trẻ em trong tin tội phạm, không phải user.
- **Kịch bản bám bài nguồn đã thu** (snapshot sẵn có của `creative`) và nêu nguồn bằng lời, ví dụ "according to <outlet>". Không có tính năng bịa tình tiết. Bỏ cổng disclosure không đổi điều này.

Mọi cổng khác trong MC-POLICY tắt đúng như user chọn: tier nguồn, quyền hook/ảnh, xuất xứ bắt buộc, nhãn AI, lexicon pháp lý, mẫu an toàn.

User đã yêu cầu bỏ mọi nguyên tắc tuân thủ và sao chép (`USER_REQUIREMENTS_20261104.md`). Mọi cổng khác đã tắt theo yêu cầu đó; bốn điểm trên được giữ và **đã báo user**. Kế hoạch không thêm ranh giới mới. Hook dùng chung giữa các vụ, B-roll dùng chung, không nhãn AI và không cổng nguồn cấp 1 là chính sách của user, không phải ranh giới.

## 3. Điểm va chạm đã biết (test phải được gói sở hữu)

| Ràng buộc | Vị trí | Test đang ghim | Gói xử lý |
|---|---|---|---|
| Đúng 5 preset | `src/render/domain/preset.py:25`; `wiring/creative.py:243-257`; `creative/domain/layout_choice.py:22` | `tests/unit/render/test_f02_preset_revision.py`, `tests/integration/render/test_prs_layout_*.py`, `tests/integration/prod_wiring/test_prs_layout_quota*.py` | MC-THEMES. Không đổi số 5: chủ đề là trục thứ hai (theme), độc lập bố cục. |
| Hashtag 3–4 | `src/creative/domain/output_metadata.py:17-18`; `prompts.py` | `tests/integration/creative/test_d14_creative_pipeline.py`, `tests/integration/persistence/d/test_persist_d_postgres.py`, `.../f/test_persist_f_postgres.py` | MC-METADATA |
| `speed_fit` 0,85–1,15; ~136 wpm (RG-09, user quyết) | `profile.json` mục `voice`; `src/voice/domain/speed_fit.py`; `real_kokoro_tts.py:42` | `tests/integration/voice/test_e16_fix3_tail_pad.py`, `tests/integration/adapt/config/test_adapt_config_profile.py` | MC-VOICE (cũng thêm giọng cảm xúc từ sidecar `MC-TTS-EMOTION`). Ghi `CLOSURE_NOTE` mới thay RG-09, căn cứ D6. |
| Hook bắt đầu 500 ms, dài 4 s | `stock_harvest.py:67`; `render_command.py:505,529,641` | `tests/integration/prod_wiring/test_d10_fix1_hook_lead.py` | MC-HOOK-ASSEMBLY |
| Fingerprint đồ thị render | `render_command.py:607` | `tests/integration/render/test_f10_fix6_frame_placement.py`, `test_f19_inspect_output_pipeline.py`, `test_imggen_label.py`, `tests/real/test_cp7_render_real.py` | MC-HOOK-ASSEMBLY, MC-CHROME, MC-THEMES, nối tiếp nhau |
| 13 cổng QC (CT-QC-001) | `docs/09-contracts/08-render-quality-contracts.md`; `quality_report.py` (`GateName`); `content_gates.py` | `tests/unit/render/test_f14_content_gates.py`, `tests/integration/render/test_f19_inspect_output_pipeline.py` | MC-BL-LAYOUT-QC (13 lên 14 cổng) |
| Dải màu đầu ra | `render_command.py` | `tests/unit/render/test_f10_render_command_spec.py` | MC-BL-COLOR-RANGE, trước chuỗi MC-HOOK-ASSEMBLY |
| Quyền hook/stock | `hook_candidates.py:38-46`; `stock_media.py:100`; `stock_harvest.py:266` | `tests/integration/prod_ports/test_hook_harvest.py`, `tests/integration/prod_wiring/test_hook_qc_placeholder.py` | MC-POLICY-SWITCHES |
| Tier nguồn và kind | `wiring/collection.py:33,129`; `wiring/production.py:127`; `source_eligibility.py` | `tests/integration/prod_wiring/test_pw_a1_plan_cycle.py`, `test_pw_a3_scheduler.py`, `tests/integration/adapt/seed/test_adapt_seed_import.py` (ghim 7 nguồn) | MC-POLICY-SWITCHES, MC-SOURCES |
| Disclosure, nhãn AI | `creative/domain/script.py:19,31`; `content_gates.py:285`; `wiring/render.py:206,339,416` | `tests/integration/render/test_imggen_label.py`, `tests/integration/creative/test_d14_creative_pipeline.py` | MC-POLICY-SWITCHES |

**Tài nguyên dành riêng** (`portfolio.reservedPaths` của policy; gói nào sở hữu đường dẫn khớp thì **bắt buộc** đúng kiểu và khoá ở cột phải, nếu không bộ kiểm bác gói hoặc Worker bị `CANDIDATE_OUT_OF_SCOPE`):

| Vùng | Mẫu đường dẫn | Kiểu gói | Khoá |
|---|---|---|---|
| COMPOSITION-ROOT | `src/controlplane/api/wiring/**`, `src/controlplane/api/main.py`, `src/controlplane/entrypoint.py`, `src/controlplane/api/routes/control.py`, `src/main.py` | `convergence_slice` | `LOCK-COMPOSITION-ROOT` |
| MIGRATIONS | `src/**/migrations/**`, `**/*.sql` (migration thật nằm phẳng trong `src/controlplane/infrastructure/db/migrations/`, mỗi bản là cặp `NNNN_<tên>.sql` + `NNNN_<tên>.rollback.sql`; mới nhất `0019_prod_wiring`) | `convergence_slice` | `LOCK-MIGRATION-SEQUENCE` |
| DEPENDENCY-UNIVERSE | `pyproject.toml`, `uv.lock`, `src/controlplane/ui/package*.json`, … | `dependency_slice` | `LOCK-DEPENDENCY-UNIVERSE` |
| CONTRACT-SOURCES | `docs/09-contracts/**` | `convergence_slice` | `LOCK-CONTRACT-SOURCE` |
| AUTHORITY-DOCS | `docs/11-roadmap.md`, `AGENTS.md`, `CHANGELOG.md`, `HANDOFF.md`, … | `convergence_slice` | `LOCK-DOC-AUTHORITY` |
| CONTROL-API | `src/controlplane/application/control_api/**` | `convergence_slice` | `LOCK-CONTROL-API` |
| UI-SHELL | `src/controlplane/ui/src/App.tsx`, `src/controlplane/ui/dist/**` | `convergence_slice` | `LOCK-UI-SHELL` |

`tools/launcher/prod/profile.json` và `src/render/domain/render_command.py` **không** nằm trong `reservedPaths`, nên không có khoá. Chúng được tuần tự hoá bằng chồng `ownedPaths` giữa các lane và bằng cạnh `dependsOn` khai tường minh trong mục 5. Mỗi gói ở mục 5 ghi kiểu và khoá đúng theo bảng này.

## 4. Mốc và cách vào Portfolio

- Mốc mới **M8 — MC (phong cách tin nóng Mỹ)**. Thêm vào roadmap qua change control (mục 21 của roadmap). User đã duyệt delta bằng D1–D14 và chỉ thị ngày 04/11; gói W0-1 ghi bản duyệt đó vào roadmap.
- Đường vào Portfolio:
  1. Gói operator `MC-ROADMAP` (W0-1) gộp vào nhánh tích hợp: roadmap M8, MC-POLICY, kế hoạch này (mục 5 là spec) ở `docs/implementation/mc/plan.md`, và dữ liệu nghiên cứu ở `docs/implementation/mc/data/` (danh sách đủ ở mô tả `MC-ROADMAP`).
  2. Khi Portfolio rảnh (không lane giữ suất), Control thêm `M8` vào `successorMilestones` của policy, kèm gói kế hoạch `IMPL-PLAN-MC` (compilePlan `impl-mc`, spec = `docs/implementation/mc/plan.md` tại `mergeSha`, tiền tố `MC-`, slice cuối bắt buộc `MC-E2E`; 31 slice của mục 5). Trước khi lane `MC-TTS-EMOTION` mở, Control khai `externalLockfiles` cho `tools/tts_emotion/uv.lock` trong `config/runtime-universes.json` (owner `MC-TTS-EMOTION`).
  3. Bộ biên dịch sinh gói. Auditor rủi ro duyệt theo phần. `planCompiled.approved` đã là `true`.
  4. Cổng Control `GATE-MC-E2E` (`tasks_integrated: ['MC-E2E']`) giữ lane đóng M8 và gói thử `MC-PILOT`. Không bao giờ retire `MC-E2E`.
- Cú pháp spec kiểm bằng bộ đọc thật (mục 12). Mỗi gói dưới đây ghi sẵn `ownedPaths`, khoá, `dependsOn`, lệnh kiểm và `coveredIds`, nên bộ biên dịch chỉ chép, không phải đoán.

## 5. Gói công việc (spec cho bộ biên dịch)

Phần này là **spec thật** của `IMPL-PLAN-MC`: tệp `docs/implementation/mc/plan.md` lấy nguyên mục 5 này. Cú pháp theo bộ đọc `ai_pm_plan_declarations.js` (`parseSlices`):

- Mỗi slice là một heading `### MC-<ID>: <tiêu đề>` (tiền tố `MC-`, sau đó chữ hoa, số, dấu gạch). Mọi heading cấp 1–3 khác ngắt slice trước nó; không có heading `### MC-…` không phải slice.
- Dưới heading: `- kind:`, `- ownedPaths:` (list con, mỗi dòng một đường dẫn trong backtick), `- dependsOn:` (một dòng, id trong backtick cách nhau bằng dấu phẩy; viết rỗng cũng đọc được nhưng kế hoạch này luôn có ít nhất `IMPL-PLAN-MC`), `- notes:`. Các mục còn lại (Phạm vi, Lệnh kiểm, Nghiệm thu, coveredIds) là văn bản tự do, bộ đọc bỏ qua.
- `MC-ROADMAP` và `IMPL-PLAN-MC` là gói operator, **không** có heading; `dependsOn` tới `IMPL-PLAN-MC` là cạnh tới id đã biết, không thành cổng.
- Gói tài liệu thuần (không mã, không test) bị lưới chắn bác `REPORT_ONLY_PACKAGE`, nên `MCDOC-BACKLOG` (backlog) không phải slice mà là gói operator đặt sau `MC-PILOT`.
- Không dùng mã dạng `BL-<chữ>-<số>` ở bất kỳ chỗ nào của spec: bộ đọc coi đó là lời nhận việc ngoài phạm vi.

**Phong bì biên dịch** (`IMPL-PLAN-MC`): `taskIdPrefix: 'MC-'`, `milestone: 'M8'`, `kinds: [work_package_slice, dependency_slice, convergence_slice]`, `ownedPathGlobs: ['src/**','tests/**','tools/**','docs/09-contracts/**','docs/implementation/mc/**','docs/delivery-evidence/mc-*/**','pyproject.toml','uv.lock','src/controlplane/ui/**','tools/launcher/prod/**']`, `locks: [LOCK-COMPOSITION-ROOT, LOCK-MIGRATION-SEQUENCE, LOCK-DEPENDENCY-UNIVERSE, LOCK-CONTRACT-SOURCE, LOCK-DOC-AUTHORITY, LOCK-CONTROL-API, LOCK-UI-SHELL, LOCK-POSTGRES-TEST-DB, LOCK-CP7, LOCK-DESKTOP-GPU]`.

Quy ước chung:
- **Lệnh kiểm** đều là `python -B -m pytest <đích> -q -p no:cacheprovider` chạy bằng interpreter của lane; đích là test mới của chính gói, cộng test ghim ở mục 3 mà gói sở hữu. Mọi nghiệm thu "thật" (lô 24 giờ, render thật, ≥ 200 hook, LLM thật) đo ở lô W5 hay `MC-PILOT`, không chạy trong pytest của lane.
- **Mã phủ:** `MC-T<n>`, mỗi gói ghi `coveredIds:` trong docstring tệp test của mình. Cỡ: S ≤ 1 lượt Worker; M 1–2; L có thể 2 lane nối tiếp.
- Gói sở hữu `render_command.py` hoặc `tools/launcher/prod/profile.json` (không có khoá) được tuần tự hoá bằng cạnh `dependsOn`, nên chuỗi render ở mục 6 là bắt buộc.
- Gói mới của bản 4 có tiền tố `MC-BL-`, vì bộ đọc chỉ nhận id mang tiền tố của phong bì. Trong spec không có mã `BL-` đứng riêng, nên không bị bộ đọc hiểu nhầm.

### W0 — Vào mốc (sau H6)

**W0-1 `MC-ROADMAP`** (gói operator kiểu `convergence_slice`, tài liệu, S; khoá `LOCK-DOC-AUTHORITY`, `LOCK-CONTRACT-SOURCE`; không có heading trong spec)
- Phạm vi:
  - `docs/11-roadmap.md`: thêm M8, bảng mốc, mục 25 bỏ "fact-check bắt buộc", "Safety blur/recolor cho clip" giữ nguyên (MC-POLICY đã vào nhánh qua `MCDOC-POLICY`);
  - `docs/implementation/mc/plan.md`: bản sao kế hoạch này;
  - **Dữ liệu cho gói tài liệu.** `docs/implementation/mc/data/` phải nhận bản sao các tệp sau (nguồn trong `D:/AIAVC_RESEARCH/mcgi_o/research/`), vì lane không đọc được `D:/AIAVC_RESEARCH`:
    - `sources_seed_mc.json` (51 nguồn sống, R1);
    - `sources_extra.json` (R7, 240 mục; nguồn sống kind `rss` là 109);
    - `hook_sources.json` (R6, 15 mục: kênh và truy vấn hook);
    - `sfx_sources.json` (R8, 10 mục: nguồn âm);
    - `narrative_formulas.md` và `voice_profile.json` (R9);
    - `labeled_20.json` (fixture 20 bài, R4);
    - `heatcut.py` (prototype, chỉ để tham chiếu; mã sản phẩm do `MC-VIDEO-CLIPS` viết).
  - Các gói W1–W4 chỉ đọc các tệp này; không gói nào sửa chúng.
- Lệnh kiểm: probe chỉ đọc: roadmap có dòng M8, `docs/implementation/mc/plan.md` có mặt, và các tệp dữ liệu có mặt, phân tích được và `sources_seed_mc.json` đúng 51 mục, `labeled_20.json` đúng 20 mục.
- Nghiệm thu: gộp; `git diff` chỉ gồm roadmap M8, `plan.md` và `data/` (MC-POLICY đã có trên nhánh qua `MCDOC-POLICY`, gói này không đụng).

**W0-2 `IMPL-PLAN-MC`** (planning_package, S, không có heading trong spec): như mục 4.

### W1 — Nền (song song)

### MC-DEPS-YTDLP: Ghim yt-dlp vào khoá phụ thuộc

- kind: dependency_slice
- ownedPaths:
  - `pyproject.toml`
  - `uv.lock`
  - `tests/unit/mc/test_mc_deps_ytdlp.py`
- dependsOn: `IMPL-PLAN-MC`
- resourceLocks: `LOCK-DEPENDENCY-UNIVERSE`
- notes: phiên bản ghim cố định, cấm latest; wheel có hash trong khoá; Runtime Keeper dựng lại vũ trụ nên gói phụ thuộc chờ RUNTIME_PENDING.
- Phạm vi: thêm `yt-dlp==2026.10.26` vào `pyproject.toml` và `uv.lock`; mục khoá mang wheel `yt_dlp-2026.10.26-py3-none-any.whl` sha256 `a05c5b5d8562f7e8a62f5334348b406af4930d56d3a65f8021d14af0e22339ae` (nguồn spike R5; sdist `abe5c6b94c3b2f0560500add1c42e0a97641752743a5b65588ac2007a6e23eb6`). Không thêm thư viện nào khác.
- Lệnh kiểm:
  - `python -B -m pytest tests/unit/mc/test_mc_deps_ytdlp.py -q -p no:cacheprovider` (đọc `uv.lock` và `pyproject.toml`: phiên bản đúng chuỗi ghim, có đúng hash wheel trên, không có `latest`; `importlib.metadata.version('yt-dlp')` khớp)
  - probe stdlib chỉ đọc: `python -c "import yt_dlp, importlib.metadata as m; print(m.version('yt-dlp'))"` in `2026.10.26`
- Nghiệm thu: lane gộp; Keeper dựng lại vũ trụ xong.
- coveredIds: MC-T1..MC-T3

### MC-POLICY-SWITCHES: Công tắc chính sách nội dung

- kind: convergence_slice
- ownedPaths:
  - `tools/launcher/prod/profile.json`
  - `src/creative/adapters/hook_candidates.py`
  - `src/controlplane/infrastructure/production_ports/stock_media.py`
  - `src/source_ingestion/application/source_eligibility.py`
  - `src/controlplane/api/wiring/collection.py`
  - `src/controlplane/api/wiring/production.py`
  - `src/controlplane/api/wiring/render.py`
  - `src/voice/adapters/real_llm_image_safety.py`
  - `src/render/domain/content_gates.py`
  - `src/creative/domain/script.py`
  - `docs/09-contracts/05-content-media-contracts.md`
  - `docs/09-contracts/06-creative-ai-contracts.md`
  - `docs/09-contracts/07-media-processing-contracts.md`
  - `docs/09-contracts/08-render-quality-contracts.md`
  - `tests/integration/mc/test_mc_policy_switches.py`
  - `tests/integration/prod_ports/test_hook_harvest.py`
  - `tests/integration/prod_wiring/test_hook_qc_placeholder.py`
  - `tests/integration/prod_wiring/test_pw_a1_plan_cycle.py`
  - `tests/integration/render/test_imggen_label.py`
  - `tests/integration/adapt/config/test_adapt_config_profile.py`
- dependsOn: `IMPL-PLAN-MC`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTRACT-SOURCE`
- notes: sở hữu profile.json và các test ghim hành vi cũ (mục 3); xuất xứ vẫn được ghi làm metadata, chỉ thôi dùng làm cổng; nhóm trẻ em (minor_child) luôn bật.
- Phạm vi: thêm khối `content_policy` vào `profile.json`: `source_tier_gate`, `hook_rights_gate`, `media_rights_gate`, `image_safety.enabled_categories` (mặc định chỉ `minor_child`), `inference_disclosure_gate`, `ai_image_label`, `provenance_required`. Đọc khối này ở `hook_candidates.py` (`_rights`), `stock_media.py:100`, `source_eligibility.py` và `SourcePolicy` (`wiring/collection.py`, `wiring/production.py`), `real_llm_image_safety.py` (lọc nhóm), `content_gates.py:285`, `wiring/render.py:206,339,416`. Cập nhật `test_adapt_seed_import.py` (nếu cần cho ghim 7 nguồn) thuộc `MC-SOURCES`, không thuộc gói này.
- Test ghim `profile.json` (nguyên tắc 6): `test_adapt_config_profile.py` ghim tập nhóm cấp cao `GROUPS` (dòng 10 và 63), preset `font_size == 72` và `margin_v == 360` (dòng 120). Giá trị mới của gói này: `GROUPS` thêm đúng một nhóm `content_policy`; preset và số nguồn không đổi.
- Lệnh kiểm:
  - `python -B -m pytest tests/integration/mc/test_mc_policy_switches.py tests/integration/prod_ports/test_hook_harvest.py tests/integration/prod_wiring/test_hook_qc_placeholder.py tests/integration/prod_wiring/test_pw_a1_plan_cycle.py tests/integration/render/test_imggen_label.py tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider`
- Nghiệm thu (trong test): mỗi công tắc có ca bật và ca tắt; với mặc định MC, hook không giấy phép được chọn, nguồn tier 3 được thu, ảnh AI không có nhãn; ảnh có trẻ em vẫn bị che.
- coveredIds: MC-T4..MC-T10

### MC-TAXONOMY: Phân loại chủ đề trong CSDL

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/infrastructure/db/migrations/0020_mc_taxonomy.sql`
  - `src/controlplane/infrastructure/db/migrations/0020_mc_taxonomy.rollback.sql`
  - `src/ingestion/domain/topic.py`
  - `src/source_ingestion/application/collect_source.py`
  - `docs/09-contracts/02-domain-events.md`
  - `docs/09-contracts/04-source-content-contracts.md`
  - `tests/integration/mc/test_mc_taxonomy.py`
  - `tests/integration/convergence/test_cp3_migration_sequence.py`
  - `tests/integration/prod_wiring/test_pw_schema_migration.py`
  - `tests/integration/persistence/a/test_persist_a_postgres.py`
  - `tests/integration/persistence/b/test_persist_b_postgres.py`
  - `tests/integration/persistence/d/test_persist_d_postgres.py`
  - `tests/integration/persistence/e/test_persist_e_postgres.py`
  - `tests/integration/persistence/f/test_persist_f_postgres.py`
  - `tests/integration/persistence/g/test_persist_g_postgres.py`
  - `tests/integration/persistence/i/test_persist_i_postgres.py`
  - `tests/integration/persistence/j/test_persist_j_postgres.py`
- dependsOn: `IMPL-PLAN-MC`
- resourceLocks: `LOCK-MIGRATION-SEQUENCE`, `LOCK-CONTRACT-SOURCE`, `LOCK-POSTGRES-TEST-DB`
- notes: migration phẳng trong migrations/, có cặp rollback; mới nhất hiện tại là 0019_prod_wiring.
- Phạm vi: nguồn thêm `topic_hint` (4 nhãn nội dung `crime`, `celebrity_scandal`, `trend_viral`, `crime_archive`, và `news`), `region` và `poll_interval_s` (nhịp quét theo nguồn, có thể rỗng; `MC-SOURCE-ADAPTERS` làm bộ lập lịch đọc nó); bài thêm `topic` (cùng 4 nhãn), `emotional_tone` (tập: `shock`, `sympathy`, `outrage`, `humor`, `suspense`, `grief`, `curiosity`), `source_certainty` (`confirmed` | `unverified`), `entities` (jsonb: tên, vai trò, tuổi nếu có), `story_stage`, `heat_score`. `topic.py` thêm tập nhãn MC. **Nhãn nội dung khác với chế độ cào của user** (`crawl_mode` ở `MC-TOPIC-MIXER`): nhãn gắn cho bài và quyết định theme, công thức kể; chế độ là cách chọn bài cho một lô. Event `CollectedDocumentAvailable` (dựng ở `collect_source.py::_available_payload`) mang trường mới. Hint chỉ là gợi ý, không phải chân lý (mục 11).
- Test ghim migration (nguyên tắc 6): `test_cp3_migration_sequence.py`, `test_pw_schema_migration.py` và 8 test `persistence/{a,b,d,e,f,g,i,j}` ghim `range(1, 20)` và đúng 19 tệp rollback. Gói đổi chúng thành `range(1, N+1)` và N tệp rollback, N = số migration cao nhất sau gói. Thứ tự số theo chuỗi `dependsOn`: 0020 `MC-TAXONOMY`, 0021 `MC-IMAGE-SOURCES` (nếu cần), 0022 `MC-TOPIC-MIXER`, 0023 `MC-STORY-THREAD` (nếu cần); gói trước không tạo migration thì gói sau lấy số kế tiếp liền. Gói này tạo 0020 (nên N = 20).
- Lệnh kiểm: `python -B -m pytest tests/integration/mc/test_mc_taxonomy.py tests/integration/collection/test_a11_collect_source.py tests/integration/convergence/test_cp3_migration_sequence.py tests/integration/prod_wiring/test_pw_schema_migration.py tests/integration/persistence/a/test_persist_a_postgres.py tests/integration/persistence/b/test_persist_b_postgres.py tests/integration/persistence/d/test_persist_d_postgres.py tests/integration/persistence/e/test_persist_e_postgres.py tests/integration/persistence/f/test_persist_f_postgres.py tests/integration/persistence/g/test_persist_g_postgres.py tests/integration/persistence/i/test_persist_i_postgres.py tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider` (migration lên rồi xuống trên Postgres test; payload event có trường mới)
- coveredIds: MC-T11..MC-T14

### MC-STYLE-METER: Bộ đo phong cách video

- kind: work_package_slice
- ownedPaths:
  - `tools/real/mc_style_meter.py`
  - `tests/real/test_mc_style_meter.py`
- dependsOn: `IMPL-PLAN-MC`
- resourceLocks: `LOCK-CP7`
- notes: không đụng mã sản phẩm hay đường dẫn dành riêng; import lại hàm của cp7_media_probe, không chép.
- Phạm vi: `tools/real/mc_style_meter.py` đo một tệp video, không cần CSDL; dùng lại `ffprobe_json`, `loudnorm`, `silence_intervals`, `signalstats_series` của `tools/real/cp7_media_probe.py` bằng import. 12 chỉ số, mỗi chỉ số một hàm: (1) thời lượng; (2) giây có từ đầu tiên (faster-whisper `small.en`, đã có trong khoá); (3) wpm; (4) LUFS tích hợp; (5) true peak; (6) số cắt mỗi 10 s (`select=scene>0.3`); (7) trung vị độ dài cảnh; (8) độ dài hook; (9) có âm hook trước giọng (`ebur128` momentary > −35 LUFS trong [0, first_voice)); (10) độ sâu ducking; (11) dải băng đầu (độ bão hoà và màu chủ đạo ở y 230–490); (12) số ảnh hay cảnh khác nhau. Chạy trên 83 video nghiên cứu và mẫu CP7 để ra `baseline.json` là việc của Control ngoài lệnh kiểm (video nằm ngoài Git).
- Lệnh kiểm: `python -B -m pytest tests/real/test_mc_style_meter.py -q -p no:cacheprovider` (tệp tổng hợp `ffmpeg lavfi` có đáp số biết trước; xác nhận `ffmpeg` lavfi và trọng số whisper `small.en` có trong runtime khoá; tệp không giọng thì mock `first_voice`)
- coveredIds: MC-T20..MC-T31

### MC-TTS-EMOTION: Sidecar TTS cảm xúc (Chatterbox)

- kind: work_package_slice
- ownedPaths:
  - `tools/tts_emotion/pyproject.toml`
  - `tools/tts_emotion/uv.lock`
  - `tools/tts_emotion/weights.lock.json`
  - `tools/tts_emotion/protocol.py`
  - `tools/tts_emotion/engine.py`
  - `tools/tts_emotion/server.py`
  - `tools/tts_emotion/provision.py`
  - `tests/unit/mc/test_mc_tts_emotion_protocol.py`
- dependsOn: `IMPL-PLAN-MC`
- resourceLocks: `LOCK-CP7`
- notes: `tools/tts_emotion/uv.lock` là tệp khoá ngoài Keeper: Control khai `externalLockfiles` (owner MC-TTS-EMOTION) trước khi lane mở; không sở hữu đường dẫn dành riêng; không chạy engine thật trong lane, chỉ engine giả; trọng số tải một lần do Control chạy `provision.py` ngoài lane.
- Phạm vi (cả sáu tệp `tools/tts_emotion/*` và `weights.lock.json` là tệp mới; mô hình theo `tools/imagegen/`):
  - Sidecar riêng cho TTS cảm xúc (I3, R9): **Chatterbox (MIT) ghim phiên bản**, Python riêng theo yêu cầu của nó (R9 ghi 3.11) nên có `pyproject.toml` và `uv.lock` riêng, không vào khoá chính.
  - `protocol.py`: giao thức giống sidecar ảnh (`tools/imagegen/protocol.py`): yêu cầu `{text, voice_ref, exaggeration, cfg_weight, seed}` và đáp `{wav_path, duration_s, sample_rate}` hoặc lỗi có mã; `engine.py`: bao Chatterbox, có `FakeEngine` cho test; `server.py`: vòng lặp phục vụ; `provision.py`: tải trọng số từ URL https cố định kèm SHA-256 trong `weights.lock.json`, sai băm thì dời đi và không dùng (như `tools/imagegen/provision.py`).
  - Dùng chung `gpu_lease.py`: phía client giữ phiên GPU (mô hình `imagegen_client.py` đã làm); client nằm ở `MC-VOICE`, không nằm ở gói này.
  - Giọng tham chiếu là giọng dựng sẵn hoặc giọng tự sở hữu; không clone giọng từ video của kênh khác.
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_tts_emotion_protocol.py -q -p no:cacheprovider` (tuần tự hoá yêu cầu và đáp, mã lỗi, `FakeEngine` trả WAV đúng độ dài, `weights.lock.json` có URL https và SHA-256 đủ 64 ký tự, `provision.py` từ chối băm sai bằng tệp giả; không mạng, không GPU)
- Nghiệm thu thật (Control, ngoài lane): `provision.py` chạy một lần; khởi động sidecar và sinh một câu trên GPU; ghi VRAM và thời gian mỗi câu. Số đo mỗi video ghi ở `MC-PILOT`.
- coveredIds: MC-T240..MC-T244

### W2 — Thu thập

### MC-SOURCES: Nguồn tin RSS/Atom của MC

- kind: convergence_slice
- ownedPaths:
  - `tools/launcher/prod/sources.json`
  - `src/source_ingestion/application/seed_sources.py`
  - `src/controlplane/api/wiring/collection.py`
  - `tests/integration/adapt/seed/test_adapt_seed_import.py`
  - `tests/integration/prod_wiring/test_pw_a3_scheduler.py`
  - `tests/integration/mc/test_mc_sources.py`
  - `tests/integration/adapt/config/test_adapt_config_profile.py`
  - `tests/integration/prod_wiring/test_pw_a1_plan_cycle.py`
- dependsOn: `MC-TAXONOMY`, `MC-POLICY-SWITCHES`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTRACT-SOURCE`
- notes: danh sách lấy từ R1 (51 nguồn) và R7 (nguồn sống dùng được bằng kind rss_feed hoặc atom_feed có sẵn); không adapter mới ở gói này (adapter mới là MC-SOURCE-ADAPTERS); Reddit, FBI Wanted và AP hay Reuters trực tiếp không vào danh sách tự động (mục 11).
- Phạm vi:
  - Seed **51 nguồn sống R1** từ `docs/implementation/mc/data/sources_seed_mc.json` (bản sao do `MC-ROADMAP` đưa vào, gói này chỉ đọc): crime 18, celebrity_scandal 13, crime_archive 12, trend_viral 8; mọi nguồn `kind` `rss_feed` hoặc `atom_feed`, `region: US`, có `topic_hint`, `outlet`, `ua`.
  - Cộng **nguồn sống của R7** từ `docs/implementation/mc/data/sources_extra.json`: mỗi mục có `status: live` và `kind: rss` (109 mục theo bản tệp; test đếm lại từ chính tệp, không ghim số cứng) đổi thành kind `rss_feed` (hoặc `atom_feed` khi feed là Atom). Gồm: Gray TV 33 trạm `https://www.<trạm>.com/arc/outboundfeeds/rss/?outputType=xml&size=100` (toàn văn trong `content:encoded`, ảnh trong `media:content`); Google News RSS theo truy vấn `site:` hoặc tên (đường cho AP và Reuters); YouTube RSS theo `channel_id` (`https://www.youtube.com/feeds/videos.xml?channel_id=<id>`); Oxygen (feed 25 mục) và các feed Nexstar, Tegna, Hearst còn mở. Bỏ trùng URL với R1. Mục `partial`, `blocked`, `dead` không vào. Mục kind `sitemap`, `api`, `html`, `social` thuộc `MC-SOURCE-ADAPTERS`.
  - **Nhịp quét theo chủ đề** ghi vào `poll_interval_s` của từng nguồn (cột do `MC-TAXONOMY` thêm): `trend_viral` và `celebrity_scandal` 900–1.800 giây (15–30 phút); tin tổng hợp 21.600 giây (6 giờ); `crime_archive` và hồ sơ 86.400 giây (24 giờ). Nếu bộ lập lịch hiện có (`plan_cycle.py`) chưa đọc nhịp theo nguồn thì đó là ràng buộc cho `MC-SOURCE-ADAPTERS`, không phải gói này; gói này chỉ ghi giá trị.
  - **Không** nguồn Reddit, **không** `api.fbi.gov` hay fbi.gov feeds, **không** URL trực tiếp của AP hay Reuters (đi qua Google News). Không adapter `fbi_wanted_json`.
  - `crime_archive` là **án quyết và vụ cũ** (Guardian US Crime, DOJ press, Crime Reads, The Trace, Wikipedia Atom…), không phải hồ sơ truy nã.
  - `SEED_TOPICS` trong `seed_sources.py` lấy từ nguồn, không cố định `('news',)`; `tools/launcher/prod/sources.json` sinh từ hai danh sách trên.
  - `trend_viral` yếu ở R1 (8 nguồn) nay được bù bằng Gray, Google Trends RSS và Google News: chấp nhận trong lệnh kiểm; đo ≥ 10 bài ở lô W5, thiếu thì báo Control chứ không FAIL gói.
- Test ghim `profile.json` và `sources.json` (nguyên tắc 6): `test_adapt_config_profile.py` ghim tập nhóm cấp cao `GROUPS` (dòng 10 và 63), preset `font_size == 72` và `margin_v == 360` (dòng 120), đúng 7 nguồn (dòng 173); `test_pw_a1_plan_cycle.py` ghim `cp_sources == 7` (dòng 122, 125, 165). Giá trị mới của gói này: số nguồn trong `sources.json` = số nguồn R1 cộng số nguồn R7 đã nhận, tính từ hai tệp dữ liệu (không ghim số cứng trong gói); `cp_sources` của `test_pw_a1_plan_cycle.py` bằng cùng giá trị sau import.
- Lệnh kiểm: `python -B -m pytest tests/integration/mc/test_mc_sources.py tests/integration/adapt/seed/test_adapt_seed_import.py tests/integration/prod_wiring/test_pw_a3_scheduler.py tests/integration/adapt/config/test_adapt_config_profile.py tests/integration/prod_wiring/test_pw_a1_plan_cycle.py -q -p no:cacheprovider` (số nguồn theo chủ đề khớp hai tệp dữ liệu; không còn kind ngoài hai kind; không URL reddit.com, fbi.gov, apnews.com hay reuters.com trực tiếp; mỗi nguồn có `poll_interval_s` theo chủ đề; một nguồn hỏng không làm hỏng chu kỳ: giữ test `failure_isolated`)
- Nghiệm thu thật (lô W5, không trong lệnh kiểm): lô thu 24 giờ ≥ 100 bài; mỗi chủ đề ≥ 10 bài.
- coveredIds: MC-T40..MC-T44

### MC-SOURCE-ADAPTERS: Adapter nguồn mới (sitemap, video, Bluesky, Wikipedia, mugshots)

- kind: convergence_slice
- ownedPaths:
  - `src/source_ingestion/adapters/news_sitemap_source.py`
  - `src/source_ingestion/adapters/video_sitemap_source.py`
  - `src/source_ingestion/adapters/bluesky_feed_source.py`
  - `src/source_ingestion/adapters/wikipedia_trending_source.py`
  - `src/source_ingestion/adapters/mugshots_listing_source.py`
  - `src/source_ingestion/application/entity_collect.py`
  - `src/source_ingestion/application/plan_cycle.py`
  - `src/source_ingestion/application/seed_sources.py`
  - `src/controlplane/api/wiring/collection.py`
  - `tools/launcher/prod/sources.json`
  - `docs/09-contracts/04-source-content-contracts.md`
  - `tests/integration/adapt/seed/test_adapt_seed_import.py`
  - `tests/integration/prod_wiring/test_pw_a3_scheduler.py`
  - `tests/integration/mc/test_mc_sources.py`
  - `tests/unit/mc/test_mc_source_adapters.py`
  - `tests/integration/mc/test_mc_source_adapters_pipeline.py`
  - `tests/integration/adapt/config/test_adapt_config_profile.py`
  - `tests/integration/prod_wiring/test_pw_a1_plan_cycle.py`
- dependsOn: `MC-SOURCES`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTRACT-SOURCE`
- notes: cạnh tới MC-SOURCES vì cùng sở hữu sources.json, seed_sources.py và các test đếm nguồn; kind mới đăng ký ở FEED_KINDS của wiring/collection.py (Orchestrator xác minh nơi đăng ký kind, vì bộ đọc feed hiện chỉ biết rss_feed và atom_feed); HTTP giả trong test, không mạng.
- Phạm vi (năm tệp `*_source.py` và `entity_collect.py` là tệp mới; dùng `src/source_ingestion/adapters/` và `wiring/collection.py`, qua `secure_fetch.py`):
  - kind `news_sitemap`: đọc news-sitemap và sitemap thường (People `news-sitemap.xml` 468 mục, Nexstar `kxan.com/news-sitemap.xml` 133 mục, WCHS `sitemap.xml`) khi RSS bị đóng (R7);
  - kind `video_sitemap`: đọc `/arc/outboundfeeds/video-sitemap/` của Gray, lấy `content_loc` (mp4 720p), thumbnail và `duration`; **tải ngay lúc cào** vì URL ảnh và video có tham số `auth=` ký sẵn, hết hạn nhanh; đăng ký làm B-roll cho kho hook qua cổng media sẵn có;
  - kind `bluesky_author_feed`: `getAuthorFeed` công khai (R7: `searchPosts` trả 403, nên không dùng), không đăng nhập (I2);
  - kind `wikipedia_trending`: `pageviews/top` mỗi ngày cộng tìm bài mới tạo (`srsort=create_timestamp_desc`), làm tín hiệu viral (R7);
  - kind `mugshots_listing`: HTML của `mugshots.com` theo hạt (200, không CAPTCHA, có thumbnail); không vượt CAPTCHA, không xoay proxy (mục 2);
  - `entity_collect.py`: cổng `collect_by_entity(name)` cho chế độ `crime_records` của `MC-TOPIC-MIXER` (tìm Wikipedia, Google News RSS theo tên, mugshots theo tên);
  - **nhịp quét theo nguồn**: `plan_cycle.py` đọc `poll_interval_s` của từng nguồn (cột của `MC-TAXONOMY`, giá trị do `MC-SOURCES` ghi); nguồn chưa đến hạn thì bỏ qua trong chu kỳ;
  - thêm vào `sources.json` các nguồn kind mới sống ở `sources_extra.json` (kind `sitemap` live 6, `api` live 10, `html_ok` 5, `social` live 1; Orchestrator đếm lại từ tệp) và cập nhật các test đếm nguồn.
  - **Không** Reddit (TLS lỗi trên máy này, không tắt xác minh), **không** FBI (403), **không** AP hay Reuters trực tiếp (dùng Google News RSS của `MC-SOURCES`).
- Test ghim `profile.json` và `sources.json` (nguyên tắc 6): `test_adapt_config_profile.py` ghim tập nhóm cấp cao `GROUPS` (dòng 10 và 63), preset `font_size == 72` và `margin_v == 360` (dòng 120), đúng 7 nguồn (dòng 173); `test_pw_a1_plan_cycle.py` ghim `cp_sources == 7` (dòng 122, 125, 165). Giá trị mới của gói này: số nguồn cộng thêm các nguồn kind mới (tính từ `sources_extra.json`), `cp_sources` bằng cùng giá trị cuối.
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_source_adapters.py tests/integration/mc/test_mc_source_adapters_pipeline.py tests/integration/mc/test_mc_sources.py tests/integration/adapt/seed/test_adapt_seed_import.py tests/integration/prod_wiring/test_pw_a3_scheduler.py tests/integration/adapt/config/test_adapt_config_profile.py tests/integration/prod_wiring/test_pw_a1_plan_cycle.py -q -p no:cacheprovider` (HTTP giả cho từng adapter bằng mẫu XML, JSON và HTML cố định; video-sitemap tải tệp ngay và ghi `content_loc`, thumbnail, duration; nguồn chưa đến `poll_interval_s` bị bỏ qua và nguồn đến hạn được quét theo đồng hồ giả; một adapter hỏng không làm hỏng chu kỳ; không URL reddit, fbi, AP hay Reuters trực tiếp)
- Nghiệm thu thật (lô W5): mỗi adapter mới ≥ 1 lượt cào thật có bài hoặc clip; B-roll Gray ≥ 20 clip mp4 tải về.
- coveredIds: MC-T45..MC-T49

### MC-CLASSIFY: Phân loại bài độc lập với hint

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/workflows/activities.py`
  - `src/controlplane/api/wiring/collection.py`
  - `src/ingestion/application/heat_score.py`
  - `docs/09-contracts/02-domain-events.md`
  - `tests/fixtures/mc/labeled_20.json`
  - `tests/integration/mc/test_mc_classify.py`
- dependsOn: `MC-TAXONOMY`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTRACT-SOURCE`
- notes: phân loại không đọc topic_hint của nguồn làm đầu vào; fixture có sẵn từ nghiên cứu, 5 trên 20 bài lệch hint.
- Phạm vi:
  - Mở rộng stage `enrich_ai` (`ContentEnrichmentWorkflow`): một lượt LLM trả `topic` (4 nhãn nội dung, không phải chế độ cào), `emotional_tone` (`shock`, `sympathy`, `outrage`, `humor`, `suspense`, `grief`, `curiosity`), `source_certainty`, `entities`, `story_stage`; cùng cổng AI hiện có (9Router), không dịch vụ trả phí.
  - **`source_certainty`**: `confirmed` khi bài (hoặc cụm bài cùng sự kiện, từ `dedup`) có ≥ 1 báo hoặc đài; `unverified` khi chỉ có mạng xã hội, tin đồn hay một nguồn mới. Giá trị này quyết định câu kết ở `MC-SCRIPT`; phân loại do mã quy tắc trên số nguồn và loại nguồn của cụm, LLM chỉ bổ sung khi cụm không rõ. **Phân loại độc lập với `topic_hint`**: hint không đi vào prompt và không quyết định nhãn; hint chỉ được ghi lại để so.
  - `heat_score = 0,5 × độ mới + 0,3 × kích thước cụm + 0,2 × cường độ` (độ mới `exp(−giờ/24)`; cụm từ `dedup` đã có; cường độ: tone thuộc {shock, outrage}) trong `src/ingestion/application/heat_score.py`.
  - Fixture `tests/fixtures/mc/labeled_20.json` là bản sao `research/fixtures/labeled_20.json` (20 bài, 5 mỗi chủ đề, nhãn người gán). 5 bài lệch hint (mc-07, mc-08, mc-10 đáng lẽ không phải scandal; mc-15 hint `crime_archive` nhưng nội dung `trend_viral`; mc-09 nội dung CSAM chưa kết tội) là ca kiểm riêng: LLM giả trả nhãn đúng nội dung thì pipeline ghi `topic` khác hint.
- Lệnh kiểm: `python -B -m pytest tests/integration/mc/test_mc_classify.py -q -p no:cacheprovider` (LLM giả trả đúng nhãn để kiểm đường dữ liệu; prompt không chứa hint; `heat_score` đúng công thức trên số cho trước; `source_certainty` đúng cho cụm một báo, hai báo và chỉ mạng xã hội; `emotional_tone` chỉ nhận 7 giá trị trên)
- Nghiệm thu thật (lô W5): độ khớp ≥ 80% trên fixture bằng LLM thật.
- coveredIds: MC-T50..MC-T55

### MC-TOPIC-MIXER: Chế độ cào và trộn khi tạo lô

- kind: convergence_slice
- ownedPaths:
  - `src/ingestion/application/candidate_selector.py`
  - `src/controlplane/application/orchestration/batch_allocation.py`
  - `src/controlplane/application/orchestration/start_batch.py`
  - `src/controlplane/application/control_api/commands.py`
  - `src/controlplane/application/control_api/command_catalog.py`
  - `src/controlplane/application/control_api/batch_concurrency.py`
  - `src/controlplane/infrastructure/db/orchestration/start_batch.py`
  - `src/controlplane/infrastructure/db/control_api_commands.py`
  - `src/controlplane/api/wiring/completion.py`
  - `src/controlplane/infrastructure/db/migrations/0022_mc_batch_params.sql`
  - `src/controlplane/infrastructure/db/migrations/0022_mc_batch_params.rollback.sql`
  - `src/controlplane/ui/src/api/client.ts`
  - `src/controlplane/ui/src/components/CommandForm.tsx`
  - `docs/09-contracts/01-control-api-and-stream.md`
  - `docs/09-contracts/09-orchestration-contracts.md`
  - `tests/unit/mc/test_mc_topic_mixer.py`
  - `tests/integration/mc/test_mc_topic_mixer_api.py`
  - `tests/integration/prod_wiring/test_pw_b1_candidate_selector.py`
  - `tests/integration/prod_wiring/test_pw_g4_fix2_batch_start.py`
  - `tests/integration/prod_wiring/test_pw_g5_allocation.py`
  - `tests/integration/prod_wiring/test_pw_g5_fix1_batch_concurrency.py`
- dependsOn: `MC-CLASSIFY`, `MC-SOURCE-ADAPTERS`, `MC-IMAGE-SOURCES`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTROL-API`, `LOCK-CONTRACT-SOURCE`, `LOCK-MIGRATION-SEQUENCE`, `LOCK-POSTGRES-TEST-DB`
- notes: cạnh tới MC-SOURCE-ADAPTERS vì chế độ crime_records gọi entity_collect (dữ liệu thật); cạnh tới MC-IMAGE-SOURCES vì số migration 0022 đứng sau 0021; lệnh tạo lô thật là `StartProductionBatch` (`POST /v1/batches`) ở `control_api/commands.py` rồi `StartBatchService.start` (hiện chỉ nhận `target_count`), không có `control_api/batches.py`; trước khi sửa Orchestrator chạy `git grep -n "StartBatchService\|\.start(" -- src tests` và đưa mọi nơi gọi trong wiring hay composition root vào phạm vi (đã biết: `infrastructure/db/control_api_commands.py:62`, `wiring/completion.py`); trường số luồng tái dùng `max_concurrent_videos` (`batch_concurrency.py`, `CommandForm.tsx`).
- Phạm vi (`0022_mc_batch_params` là tệp mới):
  - **Chế độ cào (dropdown) tách khỏi nhãn chủ đề.** Nhãn nội dung (`topic`: `crime`, `celebrity_scandal`, `trend_viral`, `crime_archive`) giữ như `MC-TAXONOMY`. Dropdown của user có 4 chế độ `crawl_mode`, đúng lời user:
    - `trend_latest`: tin trend, viral mới nhất; độ mới ≤ 48 giờ, xếp theo `heat_score`;
    - `general`: tin tổng hợp không theo mốc thời gian;
    - `crime_records`: hồ sơ tội phạm bất kể thời gian; kèm cào tư liệu liên quan theo thực thể (gọi `collect_by_entity` của `MC-SOURCE-ADAPTERS` cho các thực thể của bài chọn);
    - `celebrity_scandal`: người nổi tiếng, scandal.
  - Chọn **một** chế độ hoặc **trộn** nhiều chế độ theo trọng số. Cùng form có **số lượng video** và **số luồng** (tái dùng `max_concurrent_videos`). Trọng tâm: tội phạm và người nổi tiếng Mỹ (nguồn `region: US` được ưu tiên).
  - **Đường truyền tham số theo lô** (bản 5 vòng 2): payload `POST /v1/batches` nhận thêm `crawl_modes`, `crawl_weights`, `since`, `keywords`, `names`; `commands.py` kiểm và chuyển cho `StartBatchService.start(..., crawl_params=...)`; `start_batch.py` và repo `db/orchestration/start_batch.py` ghi vào **cột mới `crawl_params jsonb` của `cp_production_batches`** (bảng này hiện chỉ có `batch_id, workspace_id, status, target_count, created_at`, không có cột jsonb nào, nên cần migration `0022_mc_batch_params.sql` kèm `.rollback.sql`); `candidate_selector.next_candidate(batch_id, production_mode)` đọc `crawl_params` theo `batch_id` (hiện bỏ qua `batch_id`) và chọn theo đó; trong mỗi chế độ xếp theo `heat_score` (trừ `general`, xếp theo độ phủ của cụm). `command_catalog.py` và contract `01` (và `09` nếu đổi) ghi trường mới. UI: dropdown nhiều lựa chọn và ô trọng số ở `CommandForm.tsx`, gửi qua `startProductionBatch` ở `client.ts`.
  - Test ghim hành vi cũ (nguyên tắc 6): `test_pw_b1_candidate_selector.py` (selector), `test_pw_g4_fix2_batch_start.py` (lệnh bắt đầu lô), `test_pw_g5_allocation.py`, `test_pw_g5_fix1_batch_concurrency.py`. Giá trị mới: lô không truyền tham số vẫn chọn như cũ (`crawl_params` rỗng); lô có tham số đi theo chế độ.
- Test ghim migration (nguyên tắc 6): `test_cp3_migration_sequence.py`, `test_pw_schema_migration.py` và 8 test `persistence/{a,b,d,e,f,g,i,j}` ghim `range(1, 20)` và đúng 19 tệp rollback. Gói đổi chúng thành `range(1, N+1)` và N tệp rollback, N = số migration cao nhất sau gói. Thứ tự số theo chuỗi `dependsOn`: 0020 `MC-TAXONOMY`, 0021 `MC-IMAGE-SOURCES` (nếu cần), 0022 `MC-TOPIC-MIXER`, 0023 `MC-STORY-THREAD` (nếu cần); gói trước không tạo migration thì gói sau lấy số kế tiếp liền. Gói này tạo 0022 (bắt buộc, nên N = 22 nếu `MC-IMAGE-SOURCES` có 0021, ngược lại 21).
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_topic_mixer.py tests/integration/mc/test_mc_topic_mixer_api.py tests/integration/prod_wiring/test_pw_b1_candidate_selector.py tests/integration/prod_wiring/test_pw_g4_fix2_batch_start.py tests/integration/prod_wiring/test_pw_g5_allocation.py tests/integration/prod_wiring/test_pw_g5_fix1_batch_concurrency.py tests/integration/convergence/test_cp3_migration_sequence.py tests/integration/prod_wiring/test_pw_schema_migration.py tests/integration/persistence/a/test_persist_a_postgres.py tests/integration/persistence/b/test_persist_b_postgres.py tests/integration/persistence/d/test_persist_d_postgres.py tests/integration/persistence/e/test_persist_e_postgres.py tests/integration/persistence/f/test_persist_f_postgres.py tests/integration/persistence/g/test_persist_g_postgres.py tests/integration/persistence/i/test_persist_i_postgres.py tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider`. Ca chứng minh đường truyền thật (không chỉ bản giả): `test_mc_topic_mixer_api.py` gọi `POST /v1/batches` qua ứng dụng thật (TestClient trên Postgres test, như `pw_e2e_support`) với `crawl_modes` và `crawl_weights`, kiểm hàng `cp_production_batches` có `crawl_params`, rồi gọi `PostgresCandidateSelector.next_candidate(batch_id, mode)` của chính lô đó và kiểm kết quả theo chế độ: `trend_latest` chỉ ra bài ≤ 48 giờ xếp theo heat; `general` không lọc thời gian; `crime_records` chọn bài `crime` và `crime_archive` bất kể tuổi và gọi `collect_by_entity` giả đúng tên; trộn 4 trọng số ra đủ 4 chế độ theo tỉ lệ ±1; API từ chối tham số sai và nhận số luồng. Ca Playwright tạo lô chạy ở `MC-E2E`.
- coveredIds: MC-T60..MC-T63

### MC-STORY-THREAD: Chuỗi cập nhật theo người và vụ (I7)

- kind: convergence_slice
- ownedPaths:
  - `src/ingestion/application/story_thread.py`
  - `src/ingestion/application/candidate_selector.py`
  - `src/controlplane/infrastructure/db/migrations/0023_mc_story_thread.sql`
  - `src/controlplane/infrastructure/db/migrations/0023_mc_story_thread.rollback.sql`
  - `tests/unit/mc/test_mc_story_thread.py`
  - `tests/integration/mc/test_mc_story_thread_selector.py`
  - `tests/integration/convergence/test_cp3_migration_sequence.py`
  - `tests/integration/prod_wiring/test_pw_schema_migration.py`
  - `tests/integration/persistence/a/test_persist_a_postgres.py`
  - `tests/integration/persistence/b/test_persist_b_postgres.py`
  - `tests/integration/persistence/d/test_persist_d_postgres.py`
  - `tests/integration/persistence/e/test_persist_e_postgres.py`
  - `tests/integration/persistence/f/test_persist_f_postgres.py`
  - `tests/integration/persistence/g/test_persist_g_postgres.py`
  - `tests/integration/persistence/i/test_persist_i_postgres.py`
  - `tests/integration/persistence/j/test_persist_j_postgres.py`
  - `tests/integration/prod_wiring/test_pw_b1_candidate_selector.py`
- dependsOn: `MC-TOPIC-MIXER`, `MC-IMAGE-SOURCES`
- resourceLocks: `LOCK-MIGRATION-SEQUENCE`, `LOCK-POSTGRES-TEST-DB`
- notes: cạnh tới MC-TOPIC-MIXER vì cùng sở hữu candidate_selector.py; cạnh tới MC-IMAGE-SOURCES vì số migration 0023 đứng sau 0022 của gói đó (cạnh tới MC-TOPIC-MIXER cũng đảm bảo chuỗi số); migration chỉ tạo nếu cần cột tra cứu, không thì lưu `story_thread_id` trong metadata jsonb và để hai tệp migration không tồn tại.
- Phạm vi (`story_thread.py` là tệp mới; hai tệp migration `0023_…` chỉ là tệp mới khi cần cột):
  - `story_thread_id` suy ra từ thực thể và vụ: khoá chuẩn hoá của tên người chính cộng loại sự kiện và hạt hoặc thành phố (dùng `entities` của `MC-TAXONOMY`).
  - Bài mới trong **48 giờ** về cùng người hoặc vụ đã có video (có bản ghi video đã xuất cùng `story_thread_id`) tự thành ứng viên `story_stage=update`, tiêu đề mở bằng "UPDATE:", và được **ưu tiên ở lô kế** trong chế độ user chọn (`crawl_modes` của `MC-TOPIC-MIXER`): xếp đầu hàng ứng viên của chế độ đó, không vượt số lượng video user đặt.
  - Kịch bản nhánh `update` do `MC-SCRIPT` viết; gói này chỉ gắn `story_stage` và `story_thread_id` cho ứng viên.
- Test ghim migration (nguyên tắc 6): `test_cp3_migration_sequence.py`, `test_pw_schema_migration.py` và 8 test `persistence/{a,b,d,e,f,g,i,j}` ghim `range(1, 20)` và đúng 19 tệp rollback. Gói đổi chúng thành `range(1, N+1)` và N tệp rollback, N = số migration cao nhất sau gói. Thứ tự số theo chuỗi `dependsOn`: 0020 `MC-TAXONOMY`, 0021 `MC-IMAGE-SOURCES` (nếu cần), 0022 `MC-TOPIC-MIXER`, 0023 `MC-STORY-THREAD` (nếu cần); gói trước không tạo migration thì gói sau lấy số kế tiếp liền. Nếu gói tạo 0023 thì N tăng một; không tạo thì không đổi test. `test_pw_b1_candidate_selector.py` ghim hành vi selector: giá trị mới là bài thường vẫn chọn như cũ, ứng viên `update` đứng đầu hàng.
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_story_thread.py tests/integration/mc/test_mc_story_thread_selector.py tests/integration/convergence/test_cp3_migration_sequence.py tests/integration/prod_wiring/test_pw_schema_migration.py tests/integration/persistence/a/test_persist_a_postgres.py tests/integration/persistence/b/test_persist_b_postgres.py tests/integration/persistence/d/test_persist_d_postgres.py tests/integration/persistence/e/test_persist_e_postgres.py tests/integration/persistence/f/test_persist_f_postgres.py tests/integration/persistence/g/test_persist_g_postgres.py tests/integration/persistence/i/test_persist_i_postgres.py tests/integration/persistence/j/test_persist_j_postgres.py tests/integration/prod_wiring/test_pw_b1_candidate_selector.py -q -p no:cacheprovider` (cùng người cùng vụ ra cùng `story_thread_id`; bài trong 48 giờ thành ứng viên `update` và đứng đầu hàng trong chế độ đang chọn; bài sau 48 giờ không; người khác hay vụ khác không gộp; không vượt số lượng video; nếu có migration thì lên rồi xuống trên Postgres test)
- Nghiệm thu thật (lô W5): ≥ 1 chuỗi có video `update` với `story_thread_id` khớp video gốc.
- coveredIds: MC-T64..MC-T66

### W3 — Media

### MC-IMPORT-UI: Màn nhập media

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/ui/src/features/screens/MediaImportScreen.tsx`
  - `src/controlplane/ui/src/features/screens/screenRegistry.ts`
  - `src/controlplane/application/control_api/media_import.py`
  - `src/controlplane/api/wiring/catalog.py`
  - `docs/09-contracts/01-control-api-and-stream.md`
  - `docs/09-contracts/05-content-media-contracts.md`
  - `tests/integration/mc/test_mc_import_ui.py`
  - `tests/unit/mc/test_mc_import_scan.py`
  - `src/controlplane/ui/src/App.tsx`
  - `src/controlplane/api/main.py`
  - `src/controlplane/api/routes/modules/media_import.py`
  - `src/controlplane/ui/src/api/mediaImport.ts`
  - `tests/unit/control_ui/test_h_screen_registry.py`
- dependsOn: `IMPL-PLAN-MC`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTROL-API`, `LOCK-CONTRACT-SOURCE`, `LOCK-UI-SHELL`
- notes: Orchestrator đọc `api/main.py` (import router tường minh khoảng dòng 14–15, `include_router` ở dòng 101–121 và 217–219) và `api/routes/` để xác nhận nơi đăng ký router; `main.py` thuộc COMPOSITION-ROOT; nút Scan chặn .. và liên kết ra ngoài gốc; ảnh nhân vật và minh hoạ là asset kèm role trong metadata, không thêm HookKind; sửa App.tsx hay dựng lại ui/dist thì giữ LOCK-UI-SHELL.
- Phạm vi (`routes/modules/media_import.py` và `ui/src/api/mediaImport.ts` là tệp mới): màn "Nhập media" cùng route mới. **Gắn vào ứng dụng** (bản 5 vòng 2): router API mới `routes/modules/media_import.py` (Scan, nhập, tìm theo tag) gọi `control_api/media_import.py` và được đăng ký trong `api/main.py`; trong UI mở rộng `type Milestone` ở `screenRegistry.ts` và `SCREEN_MILESTONES` ở `App.tsx` thêm `M8` (màn đặt `milestone: 'M8'`) để màn hiện trong danh mục; `test_h_screen_registry.py` ghim danh mục màn nên gói đổi nó theo (thêm đúng một màn M8, các mốc cũ không đổi). **Scan** quét các gốc cấu hình trong profile (`media_import.roots`), đối chiếu sha256 với catalog để chỉ liệt kê tệp chưa có; ảnh thu nhỏ (ảnh thu gọn, hoặc khung 1 s của video qua `ffmpeg`). Form: tags, chủ đề (4 loại), loại (hook video, hook âm, ảnh nhân vật, ảnh minh hoạ, nhạc), mô tả. Lưu qua `import_hook` hoặc `register_discovery`. Định dạng mp4, mov, webm, jpg, png, webp, mp3, wav, ogg.
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_import_scan.py tests/integration/mc/test_mc_import_ui.py tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider` (thư mục 10 tệp tổng hợp: Scan ra 10, nhập 10, Scan lại ra 0; tìm lại theo tag; đường dẫn `..` bị chặn). **Đường truyền thật:** `test_mc_import_ui.py` dựng ứng dụng thật (`create_app` với TestClient), gọi route Scan và route nhập qua HTTP và kiểm trả 200 cùng dữ liệu đúng, không gọi hàm service trực tiếp; `test_h_screen_registry.py` kiểm màn M8 có trong `SCREEN_REGISTRY`. Ca Playwright chạy ở `MC-E2E`.
- coveredIds: MC-T70..MC-T75

### MC-IMAGE-SOURCES: Nguồn ảnh theo người và vụ

- kind: convergence_slice
- ownedPaths:
  - `src/source_ingestion/adapters/image_search.py`
  - `src/source_ingestion/adapters/commons_image_source.py`
  - `src/source_ingestion/adapters/openverse_image_source.py`
  - `src/source_ingestion/adapters/secure_fetch.py`
  - `src/controlplane/api/wiring/collection.py`
  - `src/controlplane/infrastructure/db/migrations/0021_mc_media_meta.sql`
  - `src/controlplane/infrastructure/db/migrations/0021_mc_media_meta.rollback.sql`
  - `docs/09-contracts/05-content-media-contracts.md`
  - `tests/unit/mc/test_mc_image_sources.py`
  - `tests/integration/mc/test_mc_image_sources_pipeline.py`
  - `tests/integration/convergence/test_cp3_migration_sequence.py`
  - `tests/integration/prod_wiring/test_pw_schema_migration.py`
  - `tests/integration/persistence/a/test_persist_a_postgres.py`
  - `tests/integration/persistence/b/test_persist_b_postgres.py`
  - `tests/integration/persistence/d/test_persist_d_postgres.py`
  - `tests/integration/persistence/e/test_persist_e_postgres.py`
  - `tests/integration/persistence/f/test_persist_f_postgres.py`
  - `tests/integration/persistence/g/test_persist_g_postgres.py`
  - `tests/integration/persistence/i/test_persist_i_postgres.py`
  - `tests/integration/persistence/j/test_persist_j_postgres.py`
- dependsOn: `MC-TAXONOMY`, `MC-POLICY-SWITCHES`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-MIGRATION-SEQUENCE`, `LOCK-CONTRACT-SOURCE`, `LOCK-POSTGRES-TEST-DB`
- notes: migration 0021 chỉ thêm nếu cần cột tra cứu, không thì để metadata của asset; mỗi kết quả mang image_url, page_url, query, source.
- Phạm vi: cổng `ImageSearchSource.search(query, limit)`. Adapter có sẵn: **Wikimedia Commons** (MediaWiki API, **nhịp ≥ 3 s giữa các lượt**: spike ghi Commons trả 429 sau khoảng 9 yêu cầu liên tiếp), **Openverse** (**lọc giấy phép** theo cấu hình và **khớp tên đầy đủ**: kết quả tranh biếm hoạ hay người trùng tên bị loại), ảnh trong bài (`article_images.py`, đã có), ảnh thu nhỏ YouTube của clip đã tìm. **Không** adapter ảnh RSS Reddit và **không** ảnh FBI Wanted (mục 11). Chỉ chạy khi user cấp khoá: Brave Search Images hoặc SerpAPI; không cào trang kết quả Google. `MugshotSource` chỉ là cổng: ảnh bắt giữ lấy từ bài báo và module nhập; adapter từng sở cảnh sát là gói riêng sau spike. Tải qua `secure_fetch.py`: giữ chống SSRF, allow-list mở cho các host trên. Metadata asset: `source_url`, `query`, `topic`, `person_name`.
- Test ghim migration (nguyên tắc 6): `test_cp3_migration_sequence.py`, `test_pw_schema_migration.py` và 8 test `persistence/{a,b,d,e,f,g,i,j}` ghim `range(1, 20)` và đúng 19 tệp rollback. Gói đổi chúng thành `range(1, N+1)` và N tệp rollback, N = số migration cao nhất sau gói. Thứ tự số theo chuỗi `dependsOn`: 0020 `MC-TAXONOMY`, 0021 `MC-IMAGE-SOURCES` (nếu cần), 0022 `MC-TOPIC-MIXER`, 0023 `MC-STORY-THREAD` (nếu cần); gói trước không tạo migration thì gói sau lấy số kế tiếp liền. Nếu gói tạo 0021 thì N = 21; không tạo thì không đổi test.
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_image_sources.py tests/integration/mc/test_mc_image_sources_pipeline.py tests/integration/convergence/test_cp3_migration_sequence.py tests/integration/prod_wiring/test_pw_schema_migration.py tests/integration/persistence/a/test_persist_a_postgres.py tests/integration/persistence/b/test_persist_b_postgres.py tests/integration/persistence/d/test_persist_d_postgres.py tests/integration/persistence/e/test_persist_e_postgres.py tests/integration/persistence/f/test_persist_f_postgres.py tests/integration/persistence/g/test_persist_g_postgres.py tests/integration/persistence/i/test_persist_i_postgres.py tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider` (HTTP giả cho từng adapter; nhịp Commons ≥ 3 s đo bằng đồng hồ giả; Openverse lọc đúng giấy phép và loại kết quả không khớp tên đầy đủ; SSRF vẫn chặn; migration lên và xuống)
- Nghiệm thu thật (lô W5): ≥ 15 ảnh mỗi bài tội phạm và scandal, đã khử trùng; ảnh đúng tên người ≥ 40%. Spike R5 ước người nổi tiếng 4/5 có ảnh đúng, nghi phạm 2/5, nên ngưỡng 40% giữ nguyên.
- coveredIds: MC-T80..MC-T86

### MC-VIDEO-CLIPS: Tìm clip, tải đoạn và cắt đoạn nóng

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/production_ports/video_clips.py`
  - `src/controlplane/infrastructure/production_ports/clip_heat.py`
  - `src/controlplane/infrastructure/production_ports/stock_harvest.py`
  - `tools/launcher/prod/harvest_media.py`
  - `tools/launcher/prod/hook_sources.json`
  - `tests/unit/mc/test_mc_clip_heat.py`
  - `tests/integration/mc/test_mc_video_clips.py`
- dependsOn: `MC-DEPS-YTDLP`, `MC-POLICY-SWITCHES`, `MC-SOURCE-ADAPTERS`
- resourceLocks: `LOCK-CP7`
- notes: cạnh tới MC-SOURCE-ADAPTERS vì clip B-roll Gray đến từ adapter video_sitemap; không sở hữu đường dẫn dành riêng; cần sửa wiring thì báo BLOCKED kèm blocked-manifest; không dùng cookie hay tài khoản, clip đòi đăng nhập thì bỏ; **không tải hay cắt từ tài khoản @mcgi.o** (I1).
- Phạm vi (`hook_sources.json` là tệp mới, sinh từ `docs/implementation/mc/data/hook_sources.json` của R6; `video_clips.py`, `clip_heat.py` có thể là tệp mới):
  - **Nguồn clip** (kho hook dựng theo loại cảnh, vì R6 không truy được nguồn gốc 7 cụm hook và kênh tham chiếu dùng footage chung theo loại cảnh; hook dùng chung giữa các vụ là bình thường):
    - bảng kênh của R6 (`hook_sources.json`): PoliceActivity, Police Insider, Law&Crime (theo `channel_id`), Body Cam Watch, Midwest Safety, WKMG, 11Alive… (Orchestrator đọc danh sách đủ từ tệp), liệt kê bằng `yt-dlp --flat-playlist -J "https://www.youtube.com/channel/<id>/videos"` hoặc RSS `channel_id`;
    - clip mp4 của Gray qua `video_sitemap` (adapter của `MC-SOURCE-ADAPTERS`; đã tải lúc cào);
    - `yt-dlp --flat-playlist -J "ytsearchN:<từ khoá>"` theo bảng từ khoá D14a và bảng loại cảnh; `-J --flat-playlist` đã trả `duration` và `title`, không gọi thêm `--print`;
    - video nhúng trong bài (og:video, YouTube embed) là phần của `MC-BL-ARTICLE-CLIP`, không ở đây.
  - **Định dạng tải** theo R6: YouTube nay chỉ còn luồng video-only ở mức thấp (135 là 480p, 134 là 360p, 133 là 240p), nên `-f "134/133/worstvideo[height>=240]"` (R6: 42/42 lần thành công; `-f "worst[height>=240]"` hỏng), thêm âm (`+ba`) chỉ khi hook cần tiếng gốc (mặc định không, vì âm hook lấy từ kho SFX). Dùng **`--download-sections "*<bắt đầu>-<kết thúc>" --force-keyframes-at-cuts`** để chỉ tải đoạn cần (cửa sổ 60 s đầu hoặc quanh đoạn nóng), không tải cả video. Kèm `--no-simulate`; ghép cần `ffmpeg`.
  - **Cắt đoạn nóng** (tham số của prototype heatcut, vòng 2 `proto/heatcut/heatcut.py`; cập nhật nếu vòng sau đổi): đoạn dài W = 4 s; chuỗi độ phân giải 0,5 s, cửa sổ trượt bước 0,5 s; `heat = 0,6 × audio + 0,4 × motion` (`audio` = LUFS momentary `ebur128`, **lùi 0,3 s**; `motion` = trung bình điểm scene **≤ 0,3** nội cảnh; khung scene > 0,3 chỉ làm ranh giới cảnh); chuẩn hoá min–max trên clip; phạt **×0,9** cửa sổ cắt ngang ranh giới cảnh; không có âm thì chỉ `motion`; clip ngắn hơn W thì dùng nguyên; clip tĩnh (`motion_max < 0,004` và biên độ LUFS < 3 LU) trả `reason: no_action_content`, không dùng làm hook.
  - Chuẩn hoá bằng `FfmpegHookMedia` (`stock_harvest.py`), đăng ký thành `visual_hook` với `hook_type` và `topics`. **`hook_type`**: `police`, `ambulance`, `courtroom`, `arrest`, `crash`, `fire`, `crowd`, `red_carpet`, `social` (có từ bản 4) cộng **`hospital`, `stretcher`, `fight`, `bodycam`, `cctv`**; gắn bằng LLM thị giác trên 3 khung hình (dùng lại adapter thị giác của `real_llm_image_safety.py` qua import). Trần tải mỗi lượt kiểu `HarvestBudget`; một tiến trình `ffmpeg -threads 2` mỗi lúc, ≤ 60 s mỗi clip.
  - **Thu định kỳ do tool tự chạy**: `tools/launcher/prod/harvest_media.py` được launcher gọi theo lịch (chu kỳ cấu hình), chạy các nguồn trên theo `HarvestBudget`; không tool ngoài, không bước tay.
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_clip_heat.py tests/integration/mc/test_mc_video_clips.py -q -p no:cacheprovider`. Tiêu chí test: (1) **clip tổng hợp gieo đoạn nóng** `ffmpeg lavfi` (nền tĩnh, đoạn gieo có chuyển động và ồn hồng) ở 12–16 s, 25–29 s, 3–7 s: đoạn chọn lệch ≤ **0,5 s** ở cả hai đầu; (2) clip không âm thanh vẫn chọn đúng theo motion; (3) clip toàn tĩnh ra `no_action_content`; (4) tính chất: đoạn chọn dài đúng W, không vượt clip, không cắt ngang ranh giới cảnh khi có lựa chọn; (5) lệnh `yt-dlp` dựng ra có đúng `-f "134/133/worstvideo[height>=240]"` và `--download-sections`, không có `--cookies`, không có URL của tài khoản `mcgi.o`; (6) bảng nguồn đọc từ `hook_sources.json` và `hook_type` mới được chấp nhận; (7) yt-dlp và LLM thị giác là bản giả, không mạng.
- Nghiệm thu thật (lô W5): ≥ 200 hook phân loại, mỗi `hook_type` ≥ 10 clip. Hồi quy tập cố định ≥ 5 clip thật ≥ 30 s: đoạn chọn nằm trong khoảng chuyển động do người gán nhãn trước, ≥ 4/5. Ghi chú: vòng 1 prototype đạt 3/5 trên video tường thuật; vòng 2 đạt 3/3 clip tổng hợp và 6/6 mẫu thử (clip tổng hợp tương phản cực mạnh nên chưa chứng minh độ nhạy trên video thật); cập nhật ngưỡng theo vòng 3 nếu có.
- coveredIds: MC-T90..MC-T96

### MC-SFX: Kho âm hook

- kind: work_package_slice
- ownedPaths:
  - `src/controlplane/infrastructure/production_ports/sfx_catalog.py`
  - `src/controlplane/infrastructure/production_ports/stock_harvest.py`
  - `src/controlplane/infrastructure/production_ports/sfx_synth.py`
  - `tools/launcher/prod/sfx_sources.json`
  - `tests/unit/mc/test_mc_sfx.py`
  - `tests/integration/mc/test_mc_sfx_harvest.py`
- dependsOn: `MC-POLICY-SWITCHES`, `MC-VIDEO-CLIPS`
- resourceLocks: `LOCK-CP7`
- notes: cạnh tới MC-VIDEO-CLIPS vì cùng sở hữu stock_harvest.py; không sở hữu đường dẫn dành riêng; HTTP giả, không gọi Freesound thật; không cắt âm từ video @mcgi.o (I1).
- Phạm vi (`sfx_sources.json` là tệp mới, sinh từ `docs/implementation/mc/data/sfx_sources.json` của R8):
  - **Nhóm âm** (R8 và yêu cầu user), mỗi nhóm có từ khoá thu riêng: `human_panic` (tiếng người hoảng loạn, khóc, la hét, kêu cứu, "oh my god", "help": loại kênh dùng nhiều nhất, 13 cụm tái dùng, 67% video), `siren_police` (còi cảnh sát), `siren_ambulance` (còi cứu thương), `impact` (đập phá, kính vỡ, va chạm), `crowd_fight` (đám đông, xô xát), `rumble`, `hospital_machine` (máy bệnh viện), `silence_pop`. **≥ 8 bản mỗi nhóm, ≥ 100 bản tổng** (đo ở lô W5).
  - **Nguồn**: Freesound API (khoá đã có trong vault), Mixkit, Wikimedia Commons; Sonniss GDC là nguồn tuỳ chọn tải một lần theo URL https cố định kèm SHA-256 (Control chạy, không chạy trong lane). **Bỏ BBC SFX** (giấy phép không cho kiếm tiền). Danh sách nguồn và lệnh thử đọc từ `sfx_sources.json`.
  - **Quy tắc ghép `hook_type` → nhóm âm** (bảng R8 mục 5, cấu hình được, ánh xạ nhiều-nhiều): cảnh sát (`police`, `arrest`) → `siren_police` cộng `human_panic`; cáng (`stretcher`, `ambulance`) → `siren_ambulance`; bạo lực (`fight`, `bodycam`) → `impact` cộng `human_panic` cộng `crowd_fight`; bệnh viện (`hospital`) → `human_panic` (khóc, hoảng hốt) cộng `hospital_machine`; các loại còn lại theo bảng R8. Bộ chọn trả nhóm âm cho từng `hook_type`; tuỳ `topic` của bài chọn bản trong nhóm.
  - **Mức âm khi đăng ký** (R8): chuẩn hoá bản hook về **≈ −12 LUFS**, đỉnh ≤ −1 dBTP; ghi sẵn `fade_in_ms` (50–100) và `fade_out_ms` (300–500) trong metadata; còi và xung đặt sau khoảng 0,5 s. Giọng kể ở −13…−14 LUFS và việc trộn do `MC-HOOK-ASSEMBLY` làm (âm hook chạy trước rồi mới tới giọng kể).
  - `silence_pop` là âm tổng hợp bằng `ffmpeg` (im lặng cộng một nhịp pop ngắn). Sinh SFX bằng AI không thuộc M8 (backlog B-MC-1).
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_sfx.py tests/integration/mc/test_mc_sfx_harvest.py -q -p no:cacheprovider` (8 nhóm và ánh xạ `hook_type` → nhóm đúng với các ví dụ cảnh sát, cáng, bạo lực, bệnh viện; âm tổng hợp đúng độ dài; bản đăng ký có mức ≈ −12 LUFS ±1 và fade trong khoảng; Freesound, Mixkit và Commons là HTTP giả; không có nguồn BBC)
- Nghiệm thu thật (lô W5): ≥ 8 bản mỗi nhóm và ≥ 100 bản tổng trong kho.
- coveredIds: MC-T100..MC-T104

### MC-BL-ARTICLE-CLIP: Clip của bài và che mờ khung hình trẻ em

- kind: work_package_slice
- ownedPaths:
  - `src/source_ingestion/adapters/article_clips.py`
  - `src/voice/adapters/clip_minor_blur.py`
  - `tests/integration/prod_ports/test_mc_bl_article_clip.py`
  - `tests/unit/voice/test_mc_bl_clip_minor_blur.py`
- dependsOn: `MC-VIDEO-CLIPS`, `MC-POLICY-SWITCHES`
- resourceLocks: `LOCK-CP7`
- notes: gộp hai gói backlog của giai đoạn 1 (HOOK-ARTICLE-CLIP và HOOK-CLIP-SAFETY); tệp mới, không đụng wiring; cần nối dây thì báo BLOCKED kèm blocked-manifest.
- Phạm vi: lấy clip video nhúng trong chính bài nguồn (og:video, thẻ video, YouTube embed của bài) qua `secure_fetch.py`, rồi đưa qua cùng đường cắt đoạn nóng và `FfmpegHookMedia` của `MC-VIDEO-CLIPS` để đăng ký `visual_hook`. Mỗi clip, trước khi đăng ký, lấy 3 khung hình qua adapter thị giác của `real_llm_image_safety.py` (nhóm `minor_child` luôn bật theo mục 2 của kế hoạch); khung nào có trẻ em thì **che mờ vùng mặt** (hoặc toàn khung nếu không định vị được) bằng bộ lọc `ffmpeg` trong `clip_minor_blur.py`, rồi mới ghi vào kho. Không che được thì loại clip, không đăng ký bản chưa che.
- Lệnh kiểm: `python -B -m pytest tests/integration/prod_ports/test_mc_bl_article_clip.py tests/unit/voice/test_mc_bl_clip_minor_blur.py -q -p no:cacheprovider` (HTML giả có og:video và YouTube embed; adapter thị giác giả trả `minor_child` ở khung 2 thì đầu ra khung đó khác khung gốc ở vùng mặt và clip được đăng ký; adapter giả lỗi thì clip bị loại)
- coveredIds: MC-T197..MC-T201

### MC-HOOK-LIBRARY-MATCH: Ghép hook theo chủ đề

- kind: convergence_slice
- ownedPaths:
  - `src/creative/adapters/hook_candidates.py`
  - `src/catalog/application/hook_index.py`
  - `docs/09-contracts/05-content-media-contracts.md`
  - `tests/unit/mc/test_mc_hook_match.py`
  - `tests/integration/mc/test_mc_hook_library_match.py`
- dependsOn: `MC-VIDEO-CLIPS`, `MC-SFX`, `MC-IMPORT-UI`, `MC-BL-ARTICLE-CLIP`
- resourceLocks: `LOCK-CONTRACT-SOURCE`
- notes: ghi khoá metadata hook mới vào contract 05; chỉ mục nằm trong metadata revision, không dùng JSON hay SQLite riêng.
- Phạm vi: chỉ mục hook theo `hook_type` (gồm `hospital`, `stretcher`, `fight`, `bodycam`, `cctv` của `MC-VIDEO-CLIPS`), `mood`, `topics`, thời lượng, trong metadata revision. Bộ chọn trong `hook_candidates.py` xếp theo khớp chủ đề trước, rồi mới tới điểm LLM, và trả kèm nhóm âm hook tương ứng theo quy tắc của `MC-SFX`. Hook dùng chung giữa các vụ là mặc định; tránh lặp cùng hook trong một lô quá `max_reuse_per_batch` (cấu hình được).
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_hook_match.py tests/integration/mc/test_mc_hook_library_match.py tests/integration/prod_ports/test_hook_harvest.py -q -p no:cacheprovider` (xếp theo khớp chủ đề; `max_reuse_per_batch` được tôn trọng)
- Nghiệm thu thật (lô W5): ≥ 300 hook video tính cả Pixabay đã có; ghép đúng chủ đề ≥ 90% trên 40 bài fixture (10 mỗi chủ đề).
- coveredIds: MC-T110..MC-T113

### W4 — Dựng và kịch bản

Các gói sửa `render_command.py`, `wiring/render.py` hay `profile.json` chạy **nối tiếp** theo cạnh khai: COLOR-RANGE → BL-LAYOUT-QC → HOOK-ASSEMBLY → CHROME → THEMES → TRANSITIONS → VOICE (IMAGE-MATCH đứng sau THEMES). MC-SCRIPT, MC-METADATA, MC-BL-TTS-NUMBERS, MC-BL-LAYOUT-E2E và MC-BL-A11-ERROR-SAMPLE chạy song song hoặc xen với chuỗi này.

### MC-BL-COLOR-RANGE: Ghim color_range=tv khi render

- kind: work_package_slice
- ownedPaths:
  - `src/render/domain/render_command.py`
  - `tests/unit/render/test_f10_render_command_spec.py`
  - `tests/unit/render/test_mc_bl_color_range.py`
  - `tests/integration/render/test_f10_fix6_frame_placement.py`
  - `tests/integration/render/test_f19_inspect_output_pipeline.py`
- dependsOn: `IMPL-PLAN-MC`
- resourceLocks: `LOCK-CP7`
- notes: nằm trước chuỗi MC-HOOK-ASSEMBLY để không chồng tệp render_command.py; đổi đồ thị render nên đổi revision fingerprint có chủ đích và gói sở hữu test ghim fingerprint.
- Phạm vi: lệnh render ghim `color_range=tv` (limited range) ở cả bộ lọc và tham số encode (`-color_range tv` và `setparams=range=tv`, hoặc cách tương đương mà test chỉ ra), để mọi video xuất cùng dải màu và `probe.color_range` của `src/voice/domain/probe.py` đọc lại đúng `tv`. Cập nhật revision fingerprint của đồ thị render.
- Lệnh kiểm: `python -B -m pytest tests/unit/render/test_mc_bl_color_range.py tests/unit/render/test_f10_render_command_spec.py tests/integration/render/test_f10_fix6_frame_placement.py tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider` (lệnh dựng có `color_range=tv` đúng một chỗ cho mỗi đầu ra; fingerprint cũ khác mới và các test ghim đã cập nhật)
- coveredIds: MC-T202..MC-T204

### MC-BL-TTS-NUMBERS: Đọc số thế hệ hai

- kind: work_package_slice
- ownedPaths:
  - `src/voice/domain/spoken_numbers.py`
  - `tests/integration/adapt/e/test_adapt_e_tts_numbers.py`
  - `tests/unit/voice/test_mc_bl_tts_numbers.py`
- dependsOn: `IMPL-PLAN-MC`
- resourceLocks: `LOCK-CP7`
- notes: gói đổi hành vi sở hữu test ghim hành vi cũ (test_adapt_e_tts_numbers); chữ trong kịch bản giữ nguyên chữ số, chỉ chuỗi gửi tới Kokoro đổi.
- Phạm vi: `spoken_numbers.py` đọc thêm: phân số (`1/2`, `3/4`), `24/7` ("twenty-four seven"), ngày ISO (`2026-11-04`), số La Mã (`Henry VIII`, `World War II`, `Super Bowl LVIII`), và năm 1000–1099 (`1066` đọc "ten sixty-six", không "one thousand sixty-six"). Không phá các ca đã có (`72,000`, tiền, phần trăm, năm 2000+).
- Lệnh kiểm: `python -B -m pytest tests/unit/voice/test_mc_bl_tts_numbers.py tests/integration/adapt/e/test_adapt_e_tts_numbers.py -q -p no:cacheprovider`
- coveredIds: MC-T205..MC-T209, CT-TTS-001

### MC-BL-LAYOUT-QC: Cổng cảnh báo bố cục (14 cổng)

- kind: convergence_slice
- ownedPaths:
  - `src/render/domain/content_gates.py`
  - `src/render/domain/quality_report.py`
  - `src/render/adapters/real_output_inspector.py`
  - `docs/09-contracts/08-render-quality-contracts.md`
  - `tests/unit/render/test_f14_content_gates.py`
  - `tests/unit/render/test_mc_bl_layout_qc.py`
  - `tests/integration/render/test_f19_inspect_output_pipeline.py`
  - `tests/unit/render/test_f12_quality_report.py`
  - `tests/integration/persistence/f/test_persist_f_postgres.py`
  - `tests/integration/prod_wiring/test_pw_f4_render_worker.py`
- dependsOn: `MC-POLICY-SWITCHES`, `MC-BL-COLOR-RANGE`, `MC-STORY-THREAD`
- resourceLocks: `LOCK-CONTRACT-SOURCE`
- notes: cạnh tới MC-POLICY-SWITCHES vì hai gói cùng sở hữu content_gates.py và contract 08; cạnh tới MC-BL-COLOR-RANGE vì cùng sở hữu test_f19_inspect_output_pipeline.py (không khoá); cạnh tới MC-STORY-THREAD vì `test_persist_f_postgres.py` vừa ghim migration (các gói migration đứng trước) vừa ghim 13 cổng, nên gói này đứng sau chuỗi migration; cổng mới là WARNING, không chặn video.
- Phạm vi: thêm cổng `LAYOUT_RENDERED` mức **WARNING** vào `GateName` (`quality_report.py`) và hàm kiểm trong `content_gates.py`: bố cục đã chọn cho job phải có dấu vết trong khung hình đo (vùng ô ảnh của bố cục, ví dụ băng và ô ảnh đúng toạ độ) từ bằng chứng của `real_output_inspector.py`; thiếu thì WARNING `layout_not_observed`, không FAIL. Contract CT-QC-001 trong `08-render-quality-contracts.md` đổi từ 13 lên **14 cổng**, ghi cổng mới và mức WARNING.
- Test ghim số cổng (nguyên tắc 6): `test_f12_quality_report.py` (`len(GATE_ORDER) == 13` ở dòng 83, `len(report.gates) == 13` ở dòng 229 và 289), `test_f19_inspect_output_pipeline.py` (dòng 188 và `gate_statuses` ở dòng 201), `test_persist_f_postgres.py` (dòng 441) và `test_pw_f4_render_worker.py` (dùng `GATE_ORDER`, khoảng dòng 1121). Giá trị mới: **14**. `test_f13_technical_gates.py` đã kiểm, không ghim số cổng.
- Lệnh kiểm: `python -B -m pytest tests/unit/render/test_mc_bl_layout_qc.py tests/unit/render/test_f14_content_gates.py tests/integration/render/test_f19_inspect_output_pipeline.py tests/unit/render/test_f12_quality_report.py tests/integration/persistence/f/test_persist_f_postgres.py tests/integration/prod_wiring/test_pw_f4_render_worker.py -q -p no:cacheprovider` (đủ 14 cổng trong báo cáo; WARNING không làm báo cáo FAIL; số cổng ghim trong các test cũ đã cập nhật)
- coveredIds: MC-T190..MC-T193, CT-QC-001

### MC-HOOK-ASSEMBLY: Dựng đoạn hook 0–4,5 giây

- kind: convergence_slice
- ownedPaths:
  - `src/render/domain/render_command.py`
  - `tools/launcher/prod/profile.json`
  - `src/controlplane/api/wiring/render.py`
  - `docs/09-contracts/07-media-processing-contracts.md`
  - `docs/09-contracts/08-render-quality-contracts.md`
  - `tests/integration/prod_wiring/test_d10_fix1_hook_lead.py`
  - `tests/integration/render/test_f10_fix6_frame_placement.py`
  - `tests/integration/render/test_f19_inspect_output_pipeline.py`
  - `tests/integration/render/test_imggen_label.py`
  - `tests/real/test_cp7_render_real.py`
  - `tests/integration/mc/test_mc_hook_assembly.py`
  - `tests/integration/adapt/config/test_adapt_config_profile.py`
- dependsOn: `MC-HOOK-LIBRARY-MATCH`, `MC-IMAGE-SOURCES`, `MC-STYLE-METER`, `MC-BL-COLOR-RANGE`, `MC-BL-LAYOUT-QC`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTRACT-SOURCE`
- notes: render_command.py và profile.json không có khoá, nên được tuần tự hoá bằng cạnh dependsOn của chuỗi; cạnh tới MC-BL-LAYOUT-QC vì cùng sở hữu test_f19_inspect_output_pipeline.py và contract 08; revision fingerprint mới có chủ đích.
- Phạm vi: đoạn hook dài 4,5–5,5 s dựng theo R6, dưới băng tiêu đề:
  - clip hook nằm trong **ô ngang** chiếm khoảng 25–56% chiều cao khung; **nền là chính clip phóng to và làm nhoè**; băng tiêu đề bo tròn trên cùng, hiện từ khung đầu;
  - **PiP ảnh mọi nhân vật được nhắc trong đoạn hook, tối đa 4** (1–2 PiP lớn cộng dải 2–3 ảnh nhỏ khi đủ), viền trắng; ảnh lấy theo `entity` từ asset có `person_name` (`MC-IMAGE-SOURCES`); thiếu ảnh tư liệu thì mới dùng ảnh AI, **không nhãn AI** (công tắc mặc định tắt);
  - sau hook chuyển sang **collage** (chân dung lớn bên trái, 2 ảnh bên phải; phần collage thuộc `MC-IMAGE-MATCH`) kèm karaoke.
  - **Âm**: âm hook chạy trước rồi mới tới giọng kể; mức hook ≈ −12 LUFS, giọng −13…−14 LUFS, fade vào 50–100 ms, fade ra 300–500 ms lúc giọng vào; giọng `adelay` 4.500 ms (D6), cấu hình được. Cổng `VISUAL_HOOK_PRESENT` giữ nguyên ngưỡng. Sở hữu các test fingerprint ở mục 3 và `test_d10_fix1_hook_lead.py`.
- Test ghim `profile.json` (nguyên tắc 6): `test_adapt_config_profile.py` ghim tập nhóm cấp cao `GROUPS` (dòng 10 và 63), preset `font_size == 72` và `margin_v == 360` (dòng 120). Giá trị mới của gói này: chỉ thêm khoá con của hook (độ dài 4,5–5,5 s, số PiP tối đa 4); `GROUPS` và preset không đổi.
- Lệnh kiểm: `python -B -m pytest tests/integration/mc/test_mc_hook_assembly.py tests/integration/prod_wiring/test_d10_fix1_hook_lead.py tests/integration/render/test_f10_fix6_frame_placement.py tests/integration/render/test_f19_inspect_output_pipeline.py tests/integration/render/test_imggen_label.py tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider`
- Nghiệm thu thật (lô W5): render thật 4 video, mỗi chủ đề 1; `mc_style_meter` đo `first_voice_s` trong 4,0–5,0, có âm hook trước giọng, số PiP bằng số nhân vật được nhắc (2 tới 4).
- coveredIds: MC-T120..MC-T125

### MC-CHROME: Lớp chrome chung cho 5 bố cục

- kind: convergence_slice
- ownedPaths:
  - `src/render/domain/render_command.py`
  - `src/render/domain/layout.py`
  - `src/render/domain/karaoke_plan.py`
  - `tools/launcher/prod/profile.json`
  - `src/controlplane/api/wiring/render.py`
  - `tests/integration/render/test_prs_layout_config.py`
  - `tests/integration/render/test_prs_layout_graph.py`
  - `tests/integration/render/test_prs_layout_polish.py`
  - `tests/integration/render/test_prs_layout_render.py`
  - `tests/integration/render/test_prs_layout_text.py`
  - `tests/integration/prod_wiring/test_prs_layout_quota.py`
  - `tests/integration/prod_wiring/test_prs_layout_quota_fix1.py`
  - `tests/integration/prod_wiring/test_prs_layout_render_preset.py`
  - `tests/integration/mc/test_mc_chrome.py`
  - `tests/integration/adapt/config/test_adapt_config_profile.py`
- dependsOn: `MC-HOOK-ASSEMBLY`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTRACT-SOURCE`
- notes: giữ đúng 5 preset; thứ tự sau MC-BL-LAYOUT-QC đi bắc cầu qua MC-HOOK-ASSEMBLY, nên cổng LAYOUT_RENDERED có trước khi chrome đổi bố cục; gói sở hữu các test bố cục.
- Phạm vi: lớp chrome chung (D1) áp lên cả 5 bố cục: băng viên thuốc y 230–490 bo góc ≥ 48 (tối đa 3 dòng, trần 60 ký tự); ô ảnh `Box(0,480,1080,960)` cho bố cục dùng ô đơn; phụ đề italic cỡ 60–64 đặt ở 68–78% chiều cao, tô từ đang đọc (karaoke đã có); ducking `sidechaincompress` giảm 10–12 dB khi có giọng, bed −8 dB trong hook; −16 LUFS (đã có); lưới cảnh 5 s, 12–14 cảnh. Preset phụ đề trong `profile.json` đổi `italic`, `font size`, `margin_v` theo revision mới. **Giữ đúng 5 preset.**
- Test ghim `profile.json` (nguyên tắc 6): `test_adapt_config_profile.py` ghim tập nhóm cấp cao `GROUPS` (dòng 10 và 63), preset `font_size == 72` và `margin_v == 360` (dòng 120). Giá trị mới của gói này: preset phụ đề `font_size` 62 và `margin_v` 460 (trong khoảng 60–64 và 440–480 của chrome), `italic` bật; `GROUPS` không đổi.
- Lệnh kiểm: `python -B -m pytest tests/integration/mc/test_mc_chrome.py tests/integration/render/test_prs_layout_config.py tests/integration/render/test_prs_layout_graph.py tests/integration/render/test_prs_layout_polish.py tests/integration/render/test_prs_layout_render.py tests/integration/render/test_prs_layout_text.py tests/integration/prod_wiring/test_prs_layout_quota.py tests/integration/prod_wiring/test_prs_layout_quota_fix1.py tests/integration/prod_wiring/test_prs_layout_render_preset.py tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider`
- Nghiệm thu thật (lô W5): bộ đo đạt các khoảng D1 trên 5 video thử (mỗi bố cục 1); độ sâu ducking đo được 10–12 dB.
- coveredIds: MC-T130..MC-T137

### MC-BL-LAYOUT-E2E: Test e2e bố cục

- kind: work_package_slice
- ownedPaths:
  - `tests/integration/prod_wiring/test_mc_bl_layout_e2e.py`
- dependsOn: `MC-CHROME`
- resourceLocks: `LOCK-POSTGRES-TEST-DB`
- notes: chỉ thêm test; chạy sau MC-CHROME vì chrome đổi bố cục, nên test này ghim hành vi cuối; dùng pw_e2e_support có sẵn, không sở hữu nó.
- Phạm vi: test e2e kiểu `PW-E2E` cho 5 bố cục: mỗi bố cục một job giả đi qua chọn bố cục, dựng lệnh render (ffmpeg giả ghi lệnh) và kiểm đầu ra; xác nhận cổng `LAYOUT_RENDERED` có trong báo cáo QC với đủ 14 cổng, và cả 5 bố cục đều được dùng trong một lô 5 job (quota).
- Lệnh kiểm: `python -B -m pytest tests/integration/prod_wiring/test_mc_bl_layout_e2e.py -q -p no:cacheprovider`
- coveredIds: MC-T194..MC-T196

### MC-THEMES: Chủ đề màu theo nội dung

- kind: convergence_slice
- ownedPaths:
  - `src/render/domain/render_command.py`
  - `src/render/domain/layout.py`
  - `src/render/domain/theme.py`
  - `tools/launcher/prod/profile.json`
  - `src/controlplane/api/wiring/render.py`
  - `src/controlplane/api/wiring/creative.py`
  - `tests/unit/render/test_f02_preset_revision.py`
  - `tests/integration/mc/test_mc_themes.py`
  - `tests/integration/adapt/config/test_adapt_config_profile.py`
  - `tests/integration/creative/test_d16_worker_activity.py`
  - `tests/integration/prod_wiring/pw_vertical.py`
  - `tests/integration/prod_wiring/test_pw_vert_video_flow.py`
- dependsOn: `MC-CHROME`, `MC-CLASSIFY`, `MC-SCRIPT`
- resourceLocks: `LOCK-COMPOSITION-ROOT`
- notes: cạnh tới MC-SCRIPT vì gói này bật công tắc `scene_grid` của validator do MC-SCRIPT thêm; theme là trục thứ hai độc lập 5 bố cục, REQUIRED_PRESET_COUNT không đổi.
- Phạm vi: bốn theme chọn theo `topic` (nhãn nội dung, không phải chế độ cào): `CRIME_BREAKING` (crime, #FF3B30 / #1A1A1A, nhạc tense, hook mặc định police), `CELEBRITY_SCANDAL` (#C80060 / #B8D8F8, suspense, red_carpet), `TREND_VIRAL` (#FFD400 / #FF6B00, upbeat, crowd), `CRIME_ARCHIVE` (#0A2540 / #4A90D9, eerie, courtroom). Theme quyết định màu băng và accent (thay `_COLOURS`, `layout.py:52`), mood nhạc (catalog nhạc đã có) và hook mặc định khi bộ chọn hoà điểm.
- Test ghim `profile.json` (nguyên tắc 6): `test_adapt_config_profile.py` ghim tập nhóm cấp cao `GROUPS` (dòng 10 và 63), preset `font_size == 72` và `margin_v == 360` (dòng 120). Giá trị mới của gói này: thêm khoá con `themes` (4 theme) và `creative_settings.scene_grid` (mặc định bật cho lô MC); `GROUPS` không đổi.
- Công tắc lưới cảnh: gói đọc `profile.creative_settings.scene_grid` (mặc định bật cho lô MC) và truyền cho validator của `MC-SCRIPT` qua `wiring/creative.py`. Ba test dựng plan ít cảnh (`test_d16_worker_activity.py`, `pw_vertical.py`, `test_pw_vert_video_flow.py`) đặt công tắc tắt trong fixture của chúng hoặc dựng đủ 12–14 cảnh; test cũ khác không đổi vì mặc định của mã là tắt.
- Lệnh kiểm: `python -B -m pytest tests/integration/mc/test_mc_themes.py tests/unit/render/test_f02_preset_revision.py tests/integration/render/test_prs_layout_render.py tests/integration/adapt/config/test_adapt_config_profile.py tests/integration/creative/test_d16_worker_activity.py tests/integration/prod_wiring/test_pw_vert_video_flow.py -q -p no:cacheprovider` (4 theme × 5 bố cục = 20 tổ hợp dựng lệnh với màu đúng; `REQUIRED_PRESET_COUNT` vẫn 5)
- Nghiệm thu thật (lô W5): render 20 tổ hợp ở độ phân giải thấp; màu băng đo bằng chỉ số 11 khớp theme; 4 video thật nhìn khác nhau rõ.
- coveredIds: MC-T140..MC-T144

### MC-TRANSITIONS: Chuyển cảnh lật gương và xfade (P2)

- kind: convergence_slice
- ownedPaths:
  - `src/render/domain/render_command.py`
  - `src/render/domain/layout.py`
  - `tools/launcher/prod/profile.json`
  - `src/controlplane/api/wiring/render.py`
  - `tests/integration/render/test_f10_fix6_frame_placement.py`
  - `tests/integration/render/test_f19_inspect_output_pipeline.py`
  - `tests/integration/mc/test_mc_transitions.py`
  - `tests/integration/adapt/config/test_adapt_config_profile.py`
- dependsOn: `MC-THEMES`
- resourceLocks: `LOCK-COMPOSITION-ROOT`
- notes: cuối chuỗi render_command.py (COLOR-RANGE, HOOK-ASSEMBLY, CHROME, THEMES, TRANSITIONS); đổi đồ thị render nên đổi revision fingerprint có chủ đích và gói sở hữu các test ghim fingerprint; đồ thị phải dưới 24.000 ký tự (không `graph_too_long`).
- Phạm vi: tuỳ chọn `mirror_pad` cho ảnh dọc (ảnh đặt giữa, hai bên lật gương làm nền thay cho nền nhoè) và `xfade` 0,2 s ở **tối đa 3 mốc** của video (ví dụ hook sang thân, và hai mốc đổi cảnh); còn lại cắt cứng như cũ (`concat`). Cấu hình trong `profile.json` (`transitions.enabled`, `mirror_pad`, `xfade_max_points`); mặc định bật cho MC, test ghim cả hai chế độ.
- Test ghim `profile.json` (nguyên tắc 6): `test_adapt_config_profile.py` ghim tập nhóm cấp cao `GROUPS` (dòng 10 và 63), preset `font_size == 72` và `margin_v == 360` (dòng 120). Giá trị mới của gói này: thêm khoá con `transitions` (`enabled`, `mirror_pad`, `xfade_max_points`); `GROUPS` không đổi.
- Lệnh kiểm: `python -B -m pytest tests/integration/mc/test_mc_transitions.py tests/integration/render/test_f10_fix6_frame_placement.py tests/integration/render/test_f19_inspect_output_pipeline.py tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider` (lệnh dựng có đúng ≤ 3 `xfade` 0,2 s với offset đúng; `mirror_pad` chỉ áp cho ảnh có tỉ lệ dọc; tắt thì lệnh giống bản trước; độ dài đồ thị dưới 24.000 ký tự; fingerprint mới khác cũ và test ghim đã cập nhật)
- Nghiệm thu thật (đo ở `MC-PILOT`): 0 lỗi QC do chuyển cảnh; p50 thời gian render tăng ≤ 15% so với lô không bật.
- coveredIds: MC-T250..MC-T253

### MC-SCRIPT: Công thức kịch bản theo chủ đề và cảm xúc

- kind: work_package_slice
- ownedPaths:
  - `src/creative/application/prompts.py`
  - `src/creative/domain/script.py`
  - `src/creative/domain/production_plan.py`
  - `tests/unit/mc/test_mc_script.py`
  - `tests/integration/creative/test_d14_creative_pipeline.py`
  - `tests/integration/prod_wiring/test_pw_d1_roles_prompts.py`
  - `tests/unit/creative/test_d10_production_plan.py`
  - `src/creative/application/pipeline.py`
- dependsOn: `MC-CLASSIFY`, `MC-POLICY-SWITCHES`, `MC-STORY-THREAD`
- resourceLocks: `LOCK-CP7`
- notes: cạnh tới MC-STORY-THREAD vì prompt dùng `story_stage=update` do gói đó gắn; không sở hữu đường dẫn dành riêng; cổng disclosure đã thành công tắc ở MC-POLICY-SWITCHES; kịch bản bám snapshot bài nguồn và nêu nguồn bằng lời (mục 2).
- Phạm vi: công thức kể theo **4 nhãn** `crime`, `celebrity_scandal`, `trend_viral`, `crime_archive` lấy từ `narrative_formulas.md` của R9 (bản sao ở `docs/implementation/mc/data/`). **Ràng buộc prompt** (`test_pw_d1_roles_prompts.py`, khoảng dòng 175: mỗi prompt `< 4000` ký tự và chỉ ASCII): công thức dài không nhét vào prompt hệ thống; tách theo nhãn thành bốn khối, mỗi khối dưới 4.000 ký tự và chỉ ASCII, ghép vào đề bài theo `topic` lúc dựng yêu cầu, không đọc tệp tài liệu lúc chạy. Tóm tắt các luật chung:
  - **~190–200 từ** cho video 61–70 s (số từ = wpm × (thời lượng − 4,5 s hook) / 60); **câu ngắn** (nhãn viral khoảng 17 từ mỗi câu, câu 1 của crime tới ~29 từ như R9); **2 câu đầu có băng nhóm hoặc nạn nhân và danh tính** (crime), mở bằng tên và sự kiện (celebrity), chi tiết gây sốc (trend), "The story of…" (archive). Văn phong trực tiếp, không rào ngữ (D9).
  - **Khai thác khía cạnh cảm xúc mạnh** do `emotional_tone` của bài (`shock`, `sympathy`, `outrage`, `humor`, `suspense`, `grief`, `curiosity`): prompt chọn góc theo tone. Số liệu R9 (trung vị lượt xem: sympathy 22.900 và suspense 21.300 cao nhất, outrage thấp nhất) chỉ dùng làm **trọng số khi bài có nhiều tone ứng viên**, không cấm tone nào.
  - **Câu kết theo `source_certainty`** (I4): `unverified` thì câu cuối là **câu hỏi mở nghi vấn**, đặt sau một nhịp cảm xúc ở câu trước, **không kết lửng** (có dấu câu đủ, không cắt giữa câu); `confirmed` thì kết bằng câu chốt hoặc đạo đức, hoặc hứa cập nhật. Bỏ ý "update_promise hoặc cliffhanger" của bản 4.
  - Nhánh `story_stage=update` mở bằng "UPDATE:" rồi nêu điều mới so với video trước.
  - **Băng tiêu đề** (P0): nêu kết quả ở đầu, có ≥ 1 tên từ `entities` và 1 con số khi có, trần 60 ký tự (3 dòng, hình học ở `MC-CHROME`).
  - **Lưới cảnh 5 s** (P0): `production_plan.py` thêm validator tuỳ chọn (tham số `scene_grid`, **mặc định tắt**) bắt mỗi cảnh = 5.000 ± 250 ms trừ cảnh cuối và 12–14 cảnh; prompt MC ghi luật đó. Chọn công tắc thay vì sửa mọi test dựng plan ít cảnh (`test_d16_worker_activity`, `pw_vertical`, `test_pw_vert_video_flow` và các test khác gọi `parse_production_plan`; danh sách do `git grep -l "parse_production_plan\|production_plan" -- tests`): ở chế độ tắt test cũ vẫn đúng. `MC-THEMES` bật công tắc cho lô MC qua `profile.creative_settings.scene_grid`. Gói này sở hữu `test_d10_production_plan.py` và thêm ca bật và ca tắt; nơi gọi validator là `src/creative/application/pipeline.py` (Orchestrator xác nhận bằng grep).
  - Hậu kiểm số từ và dấu câu cuối trước khi nhận kịch bản.
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_script.py tests/integration/creative/test_d14_creative_pipeline.py tests/integration/prod_wiring/test_pw_d1_roles_prompts.py tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider` (LLM giả: prompt đúng nhánh theo 4 nhãn và có luật tone; `unverified` ra câu cuối kết thúc bằng dấu hỏi và có câu cảm xúc đứng trước; `confirmed` không kết bằng câu hỏi; `update` mở "UPDATE:"; hậu kiểm số từ 190–200 và câu cuối đủ dấu câu; không còn ràng buộc disclosure khi công tắc tắt)
- coveredIds: MC-T150..MC-T154

### MC-METADATA: Hashtag, caption, giờ đăng

- kind: convergence_slice
- ownedPaths:
  - `src/creative/domain/output_metadata.py`
  - `src/creative/application/prompts.py`
  - `docs/09-contracts/06-creative-ai-contracts.md`
  - `tests/integration/creative/test_d14_creative_pipeline.py`
  - `tests/integration/persistence/d/test_persist_d_postgres.py`
  - `tests/integration/persistence/f/test_persist_f_postgres.py`
  - `tests/unit/mc/test_mc_metadata.py`
  - `tests/integration/prod_wiring/test_pw_d1_roles_prompts.py`
  - `tests/unit/creative/test_d11_variant_validation.py`
  - `tests/integration/prod_wiring/pw_e2e_support.py`
  - `tests/integration/prod_wiring/test_pw_d3_fix3_illustration.py`
  - `tests/integration/prod_wiring/test_pw_f3_render_inputs.py`
  - `tests/unit/creative/test_d12_output_metadata.py`
  - `src/controlplane/domain/storage_meta/output_naming.py`
- dependsOn: `MC-SCRIPT`, `MC-BL-LAYOUT-QC`
- resourceLocks: `LOCK-CONTRACT-SOURCE`, `LOCK-POSTGRES-TEST-DB`
- notes: sở hữu 3 test persist và creative ghim 3–4 hashtag; cạnh tới MC-BL-LAYOUT-QC vì cùng sở hữu `test_persist_f_postgres.py`; prompt dưới 4.000 ký tự và chỉ ASCII (`test_pw_d1_roles_prompts.py`).
- Phạm vi: `MAX_HASHTAGS = 5` (2–3 tên hoặc vụ, 1 chủ đề, `#fyp`; cấm `#breakingnews`); caption ≤ 120 ký tự theo mẫu "tên + tuổi + sự kiện", kèm dòng "Source: <outlet>"; `suggested_publish_at` 00:00–03:59 ET (chỉ ghi metadata, user tự đăng); metadata thêm `topic`, `tone`, `story_stage`, `hook_kind`, `theme`, `ending_type`.
- Test ghim hashtag 3–4 (nguyên tắc 6): `MIN_HASHTAGS`/`MAX_HASHTAGS` có **hai nơi** (`src/creative/domain/output_metadata.py:17-18` và `src/controlplane/domain/storage_meta/output_naming.py:10-11`, kiểm ở dòng 118); chuỗi "3-4 hashtags" nằm trong fixture của `test_d14_creative_pipeline.py`, `test_d11_variant_validation.py`, `test_d12_output_metadata.py`, `pw_e2e_support.py`, `test_pw_d3_fix3_illustration.py`, `test_pw_f3_render_inputs.py` và hai test persist. Lệnh tìm: `git grep -n "3-4 hashtags\|MIN_HASHTAGS\|MAX_HASHTAGS" -- tests src`. Giá trị mới: `MAX_HASHTAGS` = 5, `MIN_HASHTAGS` giữ 3 (khoảng 3–5), ở cả hai nơi; fixture ghi "3-5 hashtags". `pw_e2e_support.py` là tệp hỗ trợ của test, sở hữu để đổi fixture nhưng không đứng trong lệnh kiểm riêng.
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_metadata.py tests/integration/creative/test_d14_creative_pipeline.py tests/integration/persistence/d/test_persist_d_postgres.py tests/integration/persistence/f/test_persist_f_postgres.py tests/integration/prod_wiring/test_pw_d1_roles_prompts.py tests/unit/creative/test_d11_variant_validation.py tests/integration/prod_wiring/test_pw_d3_fix3_illustration.py tests/integration/prod_wiring/test_pw_f3_render_inputs.py tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider`
- coveredIds: MC-T170..MC-T173

### MC-VOICE: Giọng theo chủ đề và cảm xúc, tốc độ đọc

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/api/wiring/voice.py`
  - `src/voice/adapters/emotion_tts_client.py`
  - `src/voice/domain/emotion_voice.py`
  - `src/voice/domain/speed_fit.py`
  - `tools/launcher/prod/profile.json`
  - `tests/integration/voice/test_e16_fix3_tail_pad.py`
  - `tests/integration/adapt/config/test_adapt_config_profile.py`
  - `tests/unit/mc/test_mc_voice.py`
  - `tests/integration/mc/test_mc_voice_emotion.py`
- dependsOn: `MC-SCRIPT`, `MC-TRANSITIONS`, `MC-TTS-EMOTION`
- resourceLocks: `LOCK-COMPOSITION-ROOT`
- notes: cạnh tới MC-TRANSITIONS vì cùng sở hữu profile.json (cuối chuỗi render); cạnh tới MC-TTS-EMOTION vì client gọi sidecar đó; ghi CLOSURE_NOTE thay RG-09 bằng ai-setup decide ngoài gói; client dùng `LocalGpuLease` của `gpu_lease.py` như `imagegen_client.py`.
- Phạm vi (`emotion_tts_client.py` và `emotion_voice.py` là tệp mới):
  - **Bảng chủ đề × cảm xúc → engine, giọng, tốc độ, `exaggeration`, ngắt** trong `profile.json` (mục `voice.emotion_table`), điểm khởi đầu lấy từ R9 mục D (cần chỉnh sau khi nghe thử, không phải chân lý). Engine là `chatterbox` (sidecar `MC-TTS-EMOTION`) hoặc `kokoro`. Ví dụ Kokoro: tội phạm × sốc `am_michael` hoặc `af_heart` speed 1,05, ngắt 0,25 s trước chi tiết sốc; tội phạm × phẫn nộ `am_michael` 1,12; scandal × tò mò `af_bella` 1,08; thương tâm `af_heart` 0,92, ngắt 0,5 s sau câu 1 và trước câu kết; hồ sơ cũ × hồi hộp `am_fenrir` 1,15, ngắt 0,6 s trước cao trào; câu kết nghi vấn: giọng cùng bài, speed 0,95, ngắt 0,4 s phía trước. Ví dụ Chatterbox: sốc `exaggeration` 0,7 và `cfg_weight` 0,3; thương tâm 0,4 và 0,5; phẫn nộ 0,8 và 0,3; tò mò hay câu kết nghi vấn 0,6. Mọi tổ hợp 4 nhãn × 7 tone phải tra ra một dòng (có dòng mặc định).
  - `emotion_tts_client.py` gọi sidecar bằng giao thức của `MC-TTS-EMOTION`, giữ phiên GPU qua `gpu_lease.py`. **Kokoro làm dự phòng** khi sidecar lỗi hoặc quá hạn (hạn cấu hình): ghi sự kiện `tts_fallback_kokoro` và tiếp tục; video không hỏng vì TTS.
  - Giữ dải wpm nghiệm thu **175–200** và `speed_fit.max` = **1,25** của Kokoro (spike R5: `af_heart` speed 1,25 thực đo khoảng 192 wpm; 1,15 cho 178; 1,30 cho 199; hợp lệ [0,5; 2,0] và `speed_scale` nhân thêm nên 1,25 × `speed_scale` ≤ 2,0; không dùng trần 1,2). `speech_rate_wpm` 175–180. Áp `speed_fit` cho đầu ra của cả hai engine (Orchestrator xác minh cách co giãn đầu ra Chatterbox qua đường `speed_fit` hiện có).
- Test ghim `profile.json` (nguyên tắc 6): `test_adapt_config_profile.py` (giá trị mới: `voice.speed_fit.max` 1,25, `speech_rate_wpm` 175–180, thêm khoá con `voice.emotion_table`; `GROUPS` và số nguồn không đổi).
- Lệnh kiểm: `python -B -m pytest tests/unit/mc/test_mc_voice.py tests/integration/mc/test_mc_voice_emotion.py tests/integration/voice/test_e16_fix3_tail_pad.py tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider` (profile: `speed_fit.max == 1.25`, wpm 175–180; `ERROR_SPEED_OUT_OF_RANGE` chỉ khi vượt 2,0; bảng tra đủ 28 tổ hợp; sidecar giả trả WAV thì dùng engine `chatterbox`; sidecar giả lỗi hay quá hạn thì ra bản Kokoro và có sự kiện dự phòng; không GPU, không mạng)
- Nghiệm thu thật (lô W5 và `MC-PILOT`): 10 video thử, wpm 175–200 ít nhất 9/10; `first_voice_s` 4,0–5,0; thời lượng 61–70 s đạt 10/10; **thời gian TTS mỗi video được ghi lại**; **0 video hỏng vì TTS** (dự phòng Kokoro chạy khi cần).
- coveredIds: MC-T160..MC-T163

### MC-IMAGE-MATCH: Gán ảnh theo nhân vật

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/api/wiring/illustrations.py`
  - `src/controlplane/api/wiring/render.py`
  - `docs/09-contracts/05-content-media-contracts.md`
  - `docs/09-contracts/06-creative-ai-contracts.md`
  - `docs/09-contracts/07-media-processing-contracts.md`
  - `src/creative/adapters/thumbnail_candidates.py`
  - `tests/integration/mc/test_mc_image_match.py`
  - `tests/unit/mc/test_mc_thumbnail.py`
- dependsOn: `MC-IMAGE-SOURCES`, `MC-SCRIPT`, `MC-THEMES`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTRACT-SOURCE`
- notes: cạnh tới MC-THEMES đứng sau cả chuỗi render vì gói cũng sửa wiring/render.py.
- Phạm vi: gán ảnh theo entity (cảnh nhắc ai thì ưu tiên ảnh của người đó). Thứ tự nguồn: ảnh cào (bài, Wikimedia, Openverse) → ảnh bắt giữ trong bài → stock → AI; AI chỉ khi thiếu ảnh tư liệu, giữ `MAX_AI_IMAGES_PER_VIDEO`. Collage 3 ảnh ở cảnh 5–10 s (`MOSAIC_GRID`: chân dung lớn bên trái, 2 ảnh bên phải). Nhãn AI theo công tắc (mặc định tắt).
  - **Ảnh thu nhỏ (thumbnail) ghép chân dung mọi nhân vật được nhắc, tối đa 4** (yêu cầu user: "đầy đủ nhân vật được nhắc tới trong ảnh thu nhỏ"): thêm vào `src/creative/adapters/thumbnail_candidates.py` (đã có; Orchestrator xác minh nếu cần tệp mới).
- Lệnh kiểm: `python -B -m pytest tests/integration/mc/test_mc_image_match.py tests/unit/mc/test_mc_thumbnail.py -q -p no:cacheprovider` (cảnh nhắc A chọn ảnh của A; AI chỉ khi thiếu ảnh tư liệu và không vượt trần; thumbnail của bài nhắc 3 người có đủ 3 chân dung, của bài nhắc 6 người cắt còn 4)
- Nghiệm thu thật (lô W5): ≥ 80% cảnh có ảnh khớp entity; mọi video có ≥ 2 PiP khi bài nhắc ≥ 2 nhân vật; thumbnail chứa mọi nhân vật được nhắc (tối đa 4).
- coveredIds: MC-T180..MC-T184

### MC-BL-A11-ERROR-SAMPLE: Mẫu thông điệp lỗi trong payload run

- kind: work_package_slice
- ownedPaths:
  - `src/source_ingestion/application/collect_source.py`
  - `tests/integration/collection/test_a11_collect_source.py`
  - `tests/integration/collection/test_mc_bl_a11_error_sample.py`
- dependsOn: `MC-TAXONOMY`
- resourceLocks: `LOCK-CP7`
- notes: cạnh tới MC-TAXONOMY vì cùng sở hữu collect_source.py (payload event); mẫu thông điệp phải đi qua redaction sẵn có của gói.
- Phạm vi: khi một run thu thập có item lỗi, payload run (`_event_payload` và `_finish`) ghi thêm một mẫu (tối đa 3 item, mỗi thông điệp tối đa 200 ký tự) gồm `code`, `locator` đã che và thông điệp đã qua `_redact`, để chẩn đoán nguồn hỏng mà không phải mở log. Không đổi mã lỗi và không đổi hành vi cô lập lỗi từng nguồn.
- Lệnh kiểm: `python -B -m pytest tests/integration/collection/test_mc_bl_a11_error_sample.py tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider` (item lỗi chứa thông tin đăng nhập trong URL: mẫu không còn chúng; quá 3 item chỉ ghi 3; run không lỗi thì không có trường mẫu)
- coveredIds: MC-T210..MC-T212

### W5 — Nối, thử, đóng

### MC-E2E: Nối toàn chuỗi

- kind: convergence_slice
- ownedPaths:
  - `src/controlplane/application/orchestration/workflows/definitions.py`
  - `src/controlplane/application/orchestration/batch_allocation.py`
  - `src/controlplane/api/wiring/production.py`
  - `src/controlplane/api/wiring/render.py`
  - `docs/09-contracts/03-workflow-and-execution.md`
  - `docs/09-contracts/09-orchestration-contracts.md`
  - `docs/09-contracts/12-state-machines.md`
  - `tests/integration/prod_wiring/test_mc_e2e_batch.py`
  - `src/controlplane/ui/e2e/mc-topic-batch.spec.ts`
- dependsOn: `MC-DEPS-YTDLP`, `MC-POLICY-SWITCHES`, `MC-TAXONOMY`, `MC-STYLE-METER`, `MC-TTS-EMOTION`, `MC-SOURCES`, `MC-SOURCE-ADAPTERS`, `MC-CLASSIFY`, `MC-TOPIC-MIXER`, `MC-STORY-THREAD`, `MC-IMPORT-UI`, `MC-IMAGE-SOURCES`, `MC-VIDEO-CLIPS`, `MC-SFX`, `MC-BL-ARTICLE-CLIP`, `MC-HOOK-LIBRARY-MATCH`, `MC-BL-COLOR-RANGE`, `MC-BL-TTS-NUMBERS`, `MC-BL-LAYOUT-QC`, `MC-HOOK-ASSEMBLY`, `MC-CHROME`, `MC-BL-LAYOUT-E2E`, `MC-THEMES`, `MC-TRANSITIONS`, `MC-SCRIPT`, `MC-METADATA`, `MC-VOICE`, `MC-IMAGE-MATCH`, `MC-BL-A11-ERROR-SAMPLE`
- resourceLocks: `LOCK-COMPOSITION-ROOT`, `LOCK-CONTRACT-SOURCE`
- notes: workflow đổi qua workflow.patched (patch mc-style-v1) để run cũ replay được; cổng GATE-MC-E2E chờ gói này; không bao giờ retire gói này.
- Phạm vi: nối `crawl_modes` (4 chế độ của `MC-TOPIC-MIXER`) và ưu tiên `story_stage=update` vào `ProductionBatchWorkflow.allocate`; theme, giọng cảm xúc (kèm dự phòng Kokoro) và chuyển cảnh vào render; patch Temporal `mc-style-v1`. Test e2e kiểu `PW-E2E`: một lô 4 video giả lập (mỗi chủ đề 1) đi qua toàn chuỗi tới QC; ca Playwright tạo lô cho `MC-TOPIC-MIXER` và ca Scan-nhập cho `MC-IMPORT-UI`.
- Lệnh kiểm: `python -B -m pytest tests/integration/prod_wiring/test_mc_e2e_batch.py tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider`
- coveredIds: MC-T220..MC-T224

### MC-PILOT: Lô thử 20 video thật

- kind: work_package_slice
- ownedPaths:
  - `tools/real/mc_pilot.py`
  - `tools/real/mc_pilot_report.py`
  - `tests/real/test_mc_pilot.py`
  - `docs/delivery-evidence/mc-pilot/report.md`
- dependsOn: `MC-E2E`, `MC-STYLE-METER`
- resourceLocks: `LOCK-CP7`, `LOCK-DESKTOP-GPU`
- notes: dependsOn là MC-E2E, không trỏ cổng GATE-MC-E2E; không chạy việc nặng khác trong lúc lô chạy; user xem mẫu và nghiệm thu là lần hỏi user duy nhất của M8.
- Phạm vi: lô thật 20 video (I8), **5 mỗi nhãn chủ đề** (`crime`, `celebrity_scandal`, `trend_viral`, `crime_archive`), bằng khung `tools/real/cp7_batch_driver.py` (import, không chép); báo cáo `mc_style_meter` so 20 video với `baseline.json` của @mcgi.o; báo cáo ghi thêm **thời gian TTS mỗi video**, số lần dự phòng Kokoro, p50 render có và không `MC-TRANSITIONS`; xuất Drive. User xem mẫu và gật đầu một lần.
- Lệnh kiểm: `python -B -m pytest tests/real/test_mc_pilot.py -q -p no:cacheprovider` (tệp đo tổng hợp và `baseline.json` giả: báo cáo đếm đúng số video render, số chủ đề có video, số chỉ số trong khoảng mục tiêu; gói không chạy lô thật trong lệnh kiểm)
- Nghiệm thu (đo bởi Control ở lô thật, ghi vào `docs/delivery-evidence/mc-pilot/report.md`): ≥ 18/20 render; 4 chủ đề đều có video; 12 chỉ số nằm trong khoảng mục tiêu ở ≥ 9/12; 0 video hỏng vì TTS; p50 render tăng ≤ 15% do chuyển cảnh; user xem mẫu và gật đầu một lần. **Sau đó Control giao audit cuối độc lập tiêu chí nghiệm thu M8** (Auditor chỉ đọc, theo Convergence Freeze: phạm vi, ngân sách và tiêu chí ghi rõ trong đề bài); chỉ khi audit đó PASS mới bàn giao M8.
- coveredIds: MC-T230..MC-T233

## 6. DAG

Cạnh khai trong spec (mũi tên chỉ từ gói trước tới gói sau). `IMPL-PLAN-MC` là gốc của mọi gói không có phụ thuộc khác. Chỉ giữ một cạnh khi hai gói cùng sở hữu một tệp (không khoá) hoặc có phụ thuộc dữ liệu thật; tệp thuộc vùng dành riêng (wiring, migration, contract) đã được khoá tuần tự hoá nên không cần cạnh riêng.

```
W0:  MC-ROADMAP ─► IMPL-PLAN-MC ─► (mọi gói gốc bên dưới)

Gốc (chỉ phụ thuộc IMPL-PLAN-MC):
  MC-DEPS-YTDLP   MC-POLICY-SWITCHES   MC-TAXONOMY   MC-STYLE-METER
  MC-TTS-EMOTION  MC-IMPORT-UI         MC-BL-COLOR-RANGE   MC-BL-TTS-NUMBERS

W2:  MC-SOURCES         ◄─ TAXONOMY, POLICY-SWITCHES
     MC-SOURCE-ADAPTERS ◄─ SOURCES                              (sources.json, seed_sources.py, test đếm nguồn)
     MC-CLASSIFY        ◄─ TAXONOMY
     MC-TOPIC-MIXER     ◄─ CLASSIFY, SOURCE-ADAPTERS, IMAGE-SOURCES   (crime_records gọi entity_collect; migration 0022 sau 0021)
     MC-STORY-THREAD    ◄─ TOPIC-MIXER, IMAGE-SOURCES           (candidate_selector.py; migration 0023 sau 0022)
W3:  MC-IMAGE-SOURCES   ◄─ TAXONOMY, POLICY-SWITCHES
     MC-VIDEO-CLIPS     ◄─ DEPS-YTDLP, POLICY-SWITCHES, SOURCE-ADAPTERS   (B-roll Gray từ video_sitemap)
     MC-SFX             ◄─ POLICY-SWITCHES, VIDEO-CLIPS         (tuần tự hoá stock_harvest.py)
     MC-BL-ARTICLE-CLIP ◄─ VIDEO-CLIPS, POLICY-SWITCHES
     MC-HOOK-LIBRARY-MATCH ◄─ VIDEO-CLIPS, SFX, IMPORT-UI, BL-ARTICLE-CLIP
W4:  MC-BL-LAYOUT-QC   ◄─ POLICY-SWITCHES, BL-COLOR-RANGE, STORY-THREAD   (content_gates.py; test_f19; test_persist_f vừa ghim migration vừa ghim 13 cổng)
     MC-HOOK-ASSEMBLY  ◄─ HOOK-LIBRARY-MATCH, IMAGE-SOURCES, STYLE-METER, BL-COLOR-RANGE, BL-LAYOUT-QC
       └─► MC-CHROME   ◄─ HOOK-ASSEMBLY
             ├─► MC-BL-LAYOUT-E2E ◄─ CHROME
             └─► MC-THEMES ◄─ CHROME, CLASSIFY, SCRIPT   (bật scene_grid của validator do SCRIPT thêm)
                   └─► MC-TRANSITIONS ◄─ THEMES
                         └─► MC-VOICE ◄─ SCRIPT, TRANSITIONS, TTS-EMOTION
     MC-SCRIPT         ◄─ CLASSIFY, POLICY-SWITCHES, STORY-THREAD ─► MC-METADATA ◄─ SCRIPT, BL-LAYOUT-QC
     MC-IMAGE-MATCH    ◄─ IMAGE-SOURCES, SCRIPT, THEMES
     MC-BL-A11-ERROR-SAMPLE ◄─ TAXONOMY                          (tuần tự hoá collect_source.py)
W5:  MC-E2E ◄─ 29 gói trên (mọi slice W1–W4) ─► GATE-MC-E2E (Control, không có trong spec)
                          └► MC-PILOT ◄─ MC-E2E, STYLE-METER ─► audit cuối độc lập ─► MCDOC-BACKLOG (operator)
                                                                    └► M8-MILESTONE-CLOSE (lane tự sinh)
```

Không có vòng và không có cặp gói chung tệp không khoá mà thiếu đường nối (đã kiểm bằng chương trình, mục 12).

**Lý do giữ hay bỏ bốn cạnh được hỏi:**

| Cạnh | Quyết định | Lý do |
|---|---|---|
| `MC-SFX` → `MC-VIDEO-CLIPS` | **Giữ** | Hai gói cùng sở hữu `stock_harvest.py` (không khoá); chung `FfmpegHookMedia` và `HarvestBudget`. |
| `MC-CHROME` → `MC-BL-LAYOUT-QC` | **Bỏ cạnh trực tiếp** | `MC-CHROME` không sở hữu tệp nào của `MC-BL-LAYOUT-QC`. Thứ tự vẫn đúng bắc cầu qua `MC-HOOK-ASSEMBLY`, nên cổng `LAYOUT_RENDERED` có trước khi chrome đổi bố cục. Cạnh mới `MC-HOOK-ASSEMBLY` → `MC-BL-LAYOUT-QC` (và `MC-BL-LAYOUT-QC` → `MC-BL-COLOR-RANGE`) thay chỗ vì chung `test_f19_inspect_output_pipeline.py`. |
| `MC-VOICE` → `MC-BL-TTS-NUMBERS` | **Bỏ** | Không chung tệp (`spoken_numbers.py` chỉ thuộc `MC-BL-TTS-NUMBERS`) và không có phụ thuộc dữ liệu: hai gói đều chỉ ghép ở `MC-E2E`. |
| `MC-VOICE` → `MC-STYLE-METER` | **Bỏ** | Bộ đo chỉ dùng ở nghiệm thu thật do Control đo sau `MC-E2E`; cạnh tới `MC-STYLE-METER` còn ở `MC-HOOK-ASSEMBLY`, `MC-E2E`, `MC-PILOT`. |

Cạnh thêm ở vòng sửa audit 1 của bản 5: `MC-TOPIC-MIXER` → `MC-IMAGE-SOURCES` (số migration), `MC-BL-LAYOUT-QC` → `MC-STORY-THREAD` và `MC-METADATA` → `MC-BL-LAYOUT-QC` (cùng sở hữu `test_persist_f_postgres.py`), `MC-THEMES` → `MC-SCRIPT` (công tắc `scene_grid`). Mọi gói thêm migration (`MC-TAXONOMY` 0020, `MC-IMAGE-SOURCES` 0021, `MC-TOPIC-MIXER` 0022, `MC-STORY-THREAD` 0023) nằm trên một chuỗi `dependsOn` và cùng sở hữu bộ 10 test ghim số migration; mọi gói đổi `profile.json` hay `sources.json` cùng sở hữu `test_adapt_config_profile.py` (và `test_pw_a1_plan_cycle.py` cho `sources.json`) theo chuỗi sẵn có.

Các cạnh khác đổi so với bản 4: thêm `MC-SOURCE-ADAPTERS` → `MC-SOURCES`, `MC-TOPIC-MIXER` → `MC-SOURCE-ADAPTERS`, `MC-VIDEO-CLIPS` → `MC-SOURCE-ADAPTERS`, `MC-STORY-THREAD` → (`MC-TOPIC-MIXER`, `MC-IMAGE-SOURCES`), `MC-SCRIPT` → `MC-STORY-THREAD`, `MC-TRANSITIONS` → `MC-THEMES`, `MC-VOICE` → (`MC-TRANSITIONS`, `MC-TTS-EMOTION`); bỏ `MC-VOICE` → `MC-THEMES` (bắc cầu qua `MC-TRANSITIONS`) và `MC-BL-LAYOUT-E2E` → `MC-BL-LAYOUT-QC` (bắc cầu qua `MC-CHROME`).

Tổng: **31 slice** trong spec (21 gói của bản 3, 6 gói `MC-BL-` và 4 gói mới của bản 5: `MC-SOURCE-ADAPTERS`, `MC-STORY-THREAD`, `MC-TTS-EMOTION`, `MC-TRANSITIONS`), cùng `MC-ROADMAP`, `IMPL-PLAN-MC`, `MCDOC-BACKLOG` (operator), 1 cổng Control và 1 lane đóng.

**Đường găng:** POLICY-SWITCHES → SOURCES → SOURCE-ADAPTERS → VIDEO-CLIPS → BL-ARTICLE-CLIP → HOOK-LIBRARY-MATCH → HOOK-ASSEMBLY → CHROME → THEMES → TRANSITIONS → VOICE → E2E → PILOT → audit cuối. Dài hơn bản 4 hai bậc (SOURCE-ADAPTERS và TRANSITIONS).

**Gói tài liệu backlog (operator, sau `MC-PILOT` và audit cuối):** `MCDOC-BACKLOG` ghi `docs/implementation/mc/backlog.md` với thứ tự ưu tiên: B-MC-1 sinh SFX bằng AI; B-MC-4 tự đăng; B-MC-5 thêm theme; B-MC-6 adapter ảnh bắt giữ theo từng sở; B-MC-7 sinh video hook bằng AI; B-MC-8 nguồn Reddit nếu user bỏ chặn TLS; B-MC-9 nguồn FBI Wanted nếu có đường tải không bị chặn. Chuỗi cập nhật `story_thread` (trước là B-MC-2) nay là slice `MC-STORY-THREAD`. Phản hồi lượt xem sau đăng: **user tự quan sát, tool không làm** (I6), nên không có mục backlog.

## 7. Ước lượng thời gian

Ước theo nhịp Portfolio đợt 45–52 (gói M gộp trong 2–6 giờ; tối đa 6 lane song song):

| Giai đoạn | Thời gian |
|---|---|
| W0 | 1 ngày |
| W1–W3 | 5–7 ngày (thêm `MC-SOURCE-ADAPTERS`, `MC-TTS-EMOTION`, `MC-STORY-THREAD`; Control dựng sidecar TTS một lần, thêm nửa ngày) |
| Chuỗi render W4 (nối tiếp, thêm `MC-TRANSITIONS` và `MC-VOICE` cuối chuỗi) | 5–7 ngày |
| Lô thử 20 video, user xem mẫu và audit cuối độc lập | 2–3 ngày |
| **Tổng** | **khoảng 3 tuần lịch sau H6** (4 gói mới thêm khoảng 3–4 ngày; `MC-SOURCE-ADAPTERS` và `MC-TRANSITIONS` thêm hai bậc vào đường găng) |

Rủi ro làm chậm nhất là chuỗi render nối tiếp, số vòng Auditor trên gói L và tải mô hình TTS lần đầu.

## 8. Rủi ro còn lại (user đã chấp nhận phần pháp lý)

- YouTube có thể chặn `yt-dlp` theo IP khi tải nhiều. Giữ trần tải mỗi lượt. Bị chặn thì gói giữ kho đã có và ghi nhận, không né chặn.
- Nguồn RSS của báo có thể đổi URL. Lỗi một nguồn đã được cô lập (PW-CAT2-FIX2).
- Ảnh bắt giữ chỉ có khi bài báo đăng kèm, nên tỉ lệ tìm được ảnh đúng người phụ thuộc nguồn.
- Đổi wpm và speed thay một quyết định cũ của user (RG-09). Kế hoạch ghi rõ để không ai coi đó là lỗi.
- Sidecar TTS cảm xúc dùng GPU chung với render và sinh ảnh: dùng chung `gpu_lease.py`; VRAM thật của Chatterbox chưa đo (R9 không nêu), Control đo ở lần dựng đầu. Hỏng hoặc quá hạn thì Kokoro chạy thay, video không hỏng.
- URL ảnh và mp4 của Gray có tham số `auth=` ký sẵn, hết hạn nhanh: adapter `video_sitemap` tải ngay lúc cào.
- Kho hook dựng theo loại cảnh, không theo nguồn gốc (R6 không truy được nguồn gốc 7 cụm): ghép đúng loại cảnh chứ không đúng vụ, và đó là chính sách của user.

## 9. Backlog của audit (MINOR, chưa sửa trong vòng audit)

Lấy từ vòng audit 1, làm ở lần biên dịch hoặc bằng slice riêng:
- `ILLUSTRATIONS_PATCH_ID` ở `src/controlplane/application/orchestration/workflows/definitions.py:42`, không phải 36–41.
- Các gói dùng `mc_style_meter` để nghiệm thu nên có cạnh `dependsOn` tới MC-STYLE-METER.
- Ghi rõ nghiệm thu nào là lệnh kiểm của lane, nghiệm thu nào đo ở lô W5 hay MC-PILOT. Lô 24 giờ, render thật và ≥ 200 hook không chạy trong pytest của lane; điều này để tránh `REAL_TEST_REQUIRED` hay `REPORT_ONLY_PACKAGE`.
- Test của MC-STYLE-METER phải xác nhận `ffmpeg` lavfi và trọng số whisper `small.en` có trong runtime khoá. Tệp tổng hợp không có giọng thì mock `first_voice`.
- Lệnh kiểm của MC-SFX dùng HTTP giả, không gọi Freesound thật.
- H4 (`git stash` trên main) cần nêu rõ là thuộc quyền bàn giao 22/10, cộng sự đồng ý của user.

Bản 5: bỏ mục backlog vòng phản hồi lượt xem (I6) và chuyển chuỗi cập nhật thành slice `MC-STORY-THREAD`; thêm cạnh có lý do ở mục 6. MINOR mới của bản 5 (chưa sửa): nơi đăng ký kind mới ngoài `FEED_KINDS` (`wiring/collection.py`), tệp nào của `src/creative/domain/` ghim `production_plan.py`, và cách `speed_fit` co giãn đầu ra Chatterbox do Orchestrator xác minh.

**Lệnh tìm cho audit vòng sau** (bản 5 vòng 2: mọi vị trí phải thuộc `ownedPaths` của gói đổi hành vi tương ứng):

```
git grep -n "len(report.gates)\|len(GATE_ORDER)\|range(1, 20)\|== 19\|cp_sources') == 7\|len(sources) == 7\|set(load('profile.json')) == GROUPS\|< 4000\|3-4 hashtags" -- tests
```

Đã xử lý ở bản 4: cạnh `dependsOn` tới `MC-STYLE-METER` cho gói dùng bộ đo (HOOK-ASSEMBLY, VOICE, PILOT; CHROME và THEMES qua chuỗi); mỗi gói tách lệnh kiểm của lane khỏi nghiệm thu đo ở lô W5 hay `MC-PILOT`; lệnh kiểm của `MC-SFX` dùng HTTP giả. Còn lại (MINOR mới, chưa sửa): vị trí chính xác của `GateName` ở `quality_report.py` hay `technical_gates.py` cho `MC-BL-LAYOUT-QC` do Orchestrator xác minh; tệp nhận lệnh tạo lô của `MC-TOPIC-MIXER` (`control_api/batches.py`) chưa kiểm trong mã.
## 10. Việc của user

- **H2:** xem mẫu 20 video của `CP7-14` và nghiệm thu R1–R6.
- **H4:** user đã đồng ý main sạch (phỏng vấn 04/11); Control đỗ (stash) 8 tệp tài liệu trên main trước khi bàn giao, bản sao đã lưu.
- **Tuỳ chọn:** cấp khoá Brave Search hoặc SerpAPI nếu muốn thêm nguồn tìm ảnh web; không có khoá thì kế hoạch vẫn chạy đủ.
- **MC-PILOT:** xem 20 video mẫu và gật đầu một lần (I8). Audit cuối độc lập do Control giao, không cần user.
- **Tuỳ chọn:** bỏ chặn TLS reddit.com ở Kaspersky nếu muốn nguồn Reddit (mục 11); không bỏ thì `trend_viral` chỉ có 8 nguồn.
## 11. Quyết định Control từ nghiên cứu (04/11/2026)

Các quyết định dưới đây Control tự chốt theo kết quả nghiên cứu R1, R4, R5 và prototype heatcut. Điểm nào đảo được thì ghi cách đảo.

| # | Quyết định | Căn cứ | Đảo bằng cách nào |
|---|---|---|---|
| 1 | **Reddit không vào nguồn tự động.** Cả 14 URL `.rss` hỏng `CERTIFICATE_VERIFY_FAILED` (chứng chỉ tự ký giữa chừng) từ máy này; `old.reddit.com` trả 403. Không tắt xác minh TLS. User cần **bỏ chặn TLS cho reddit.com ở Kaspersky** (hoặc chấp nhận bỏ Reddit). Hậu quả: `trend_viral` chỉ có 8 nguồn, Google Trends RSS là nguồn tín hiệu chính. | R1 | Sau khi user bỏ chặn, thêm nguồn bằng seed import (backlog B-MC-8), không đổi mã. |
| 2 | **FBI Wanted bỏ khỏi tự động.** `api.fbi.gov` và fbi.gov feeds trả 403, kể cả UA bot. Không có adapter `fbi_wanted_json`. | R1 | Backlog B-MC-9. |
| 3 | **`crime_archive` định nghĩa lại:** án quyết và vụ cũ (Guardian US Crime, DOJ press, Crime Reads, The Trace, Wikipedia Atom…), không phải hồ sơ truy nã. | R1 (12 nguồn sống), R4 (mc-16..mc-20 là án quyết 2022, 2024 và thông cáo DOJ) | Đổi `topic_hint` trong seed. |
| 4 | **`topic_hint` của nguồn không đáng tin.** R4: 5 trên 20 bài lệch hint (mc-07, mc-08, mc-10, mc-15, mc-09). `MC-CLASSIFY` phân loại từ nội dung, không đưa hint vào prompt; hint chỉ ghi lại để so. Ngưỡng khớp 80% đo trên `labeled_20.json`. | R4 | — |
| 5 | **Ảnh trẻ em vẫn che mặt** (nhóm `minor_child`, ranh giới của Control, mục 2) cho cả ảnh lẫn **khung hình của clip** (`MC-BL-ARTICLE-CLIP`). Năm nhóm còn lại tắt theo MC-POLICY. | Mục 2 | Không đảo. |
| 6 | **Nội dung CSAM chưa kết tội (mc-09) là tin tức**, không cần cờ chính sách thêm: nó đi qua cổng thường. Nhưng **ảnh nạn nhân trẻ em che mặt** theo quyết định 5; kịch bản nêu nguồn và không bịa tình tiết. | R4 | Không đảo. |
| 7 | **yt-dlp ghim `==2026.10.26`** (wheel sha256 `a05c5b5d…22339ae`). R6 thấy máy có bản 2026.08.19, kế hoạch vẫn ghim 2026.10.26 (R5). Định dạng tải theo R6: `-f "134/133/worstvideo[height>=240]"` (YouTube chỉ còn luồng video-only ở mức thấp; `-f "worst[height>=240]"` hỏng) và `--download-sections` để chỉ tải đoạn cần. Chạy không cookie (một máy, một thời điểm; IP bị chặn bot thì khác). Không né chặn. | R5, R6 | Phiên bản mới là gói phụ thuộc mới; định dạng tải là cấu hình của `MC-VIDEO-CLIPS`. |
| 8 | **Kokoro `speed_fit.max` = 1,25**, wpm mục tiêu 175–200 (đo 192 wpm tại 1,25). Thay RG-09 bằng `CLOSURE_NOTE`. | R5 | Đặt lại 1,15. |
| 9 | **Wikimedia Commons: nhịp ≥ 3 s** (429 sau khoảng 9 yêu cầu liên tiếp). **Openverse: lọc giấy phép và khớp tên đầy đủ** (có kết quả tranh biếm hoạ, người trùng tên). Ước tỉ lệ ảnh đúng người: người nổi tiếng 4/5, nghi phạm 2/5. | R5 | — |
| 10 | **`MC-VIDEO-CLIPS` nghiệm thu bằng test tự động**: clip tổng hợp gieo đoạn nóng ±0,5 s, clip không âm, clip tĩnh (`no_action_content`), cộng tập ≥ 5 clip thật có nhãn trước, ≥ 4/5. User xem mẫu ở nghiệm thu cuối, không làm cổng. Tham số heatcut **vòng 2**; sẽ cập nhật theo vòng 3 nếu có. | heatcut | — |
| 11 | **Kho hook dựng theo loại cảnh**, nguồn là bảng kênh R6 (PoliceActivity, Police Insider, Law&Crime theo channel ID, Body Cam Watch, Midwest Safety, WKMG, 11Alive…), clip mp4 từ video-sitemap Gray và `ytsearch` theo loại cảnh. R6 không truy được nguồn gốc 0/7 cụm hook (42 ứng viên, dHash không khớp), kênh dùng footage chung. Thêm `hook_type` `hospital`, `stretcher`, `fight`, `bodycam`, `cctv`. | R6, I1 | Thêm kênh vào `hook_sources.json`; nếu user cấp nguồn gốc thì thêm vào cùng bảng. |
| 12 | **Nguồn tin mở rộng**: Gray 33 trạm RSS (toàn văn, ảnh trong `media:content`), Google News RSS cho AP và Reuters, YouTube RSS, Oxygen vào bằng kind có sẵn (109 nguồn `live`); adapter mới `news_sitemap`, `video_sitemap`, `bluesky_author_feed`, `wikipedia_trending`, `mugshots_listing`. Mugshot chỉ `mugshots.com` (arrests.org, jailbase, Smoking Gun trả 403). Bluesky chỉ `getAuthorFeed`. Không Reddit, FBI hay AP và Reuters trực tiếp. | R7, I2 | Tắt từng nguồn hay kind trong `sources.json`; thêm nguồn bằng seed import. |
| 13 | **Kho âm theo 8 nhóm**: `human_panic` (nhóm kênh dùng nhiều nhất), `siren_police`, `siren_ambulance`, `impact`, `crowd_fight`, `rumble`, `hospital_machine`, `silence_pop`; nguồn Freesound, Mixkit, Wikimedia Commons, Sonniss tuỳ chọn; bỏ BBC (giấy phép). Mức hook ≈ −12 LUFS, giọng −13…−14, fade vào 50–100 ms, ra 300–500 ms. | R8 | Đổi bảng ghép `hook_type` → nhóm âm trong cấu hình. |
| 14 | **Giọng lai**: sidecar Chatterbox (MIT) cho cảm xúc, Kokoro làm mặc định dự phòng; tránh F5-TTS (trọng số phi thương mại); Orpheus và Dia nặng hơn nên bỏ ở M8. Công thức kể theo 4 nhãn từ `narrative_formulas.md`; câu ngắn, ~190–200 từ. | R9, I3 | Đặt `voice.emotion_table` toàn bộ về Kokoro. |
| 15 | **I1 chỉ cào nguồn gốc**: không cắt hook hay âm từ 83 video @mcgi.o vào kho; 83 video chỉ dùng để nghiên cứu và đo. | I1 | Không đảo. |
| 16 | **I2 mạng xã hội công khai, không đăng nhập**: yt-dlp không cookie, Bluesky API công khai, Google News RSS. | I2 | — |
| 17 | **I4 câu kết nghi vấn chỉ với tin chưa rõ** (`source_certainty = unverified`); tin đã xác nhận kết bằng câu chốt hoặc hứa cập nhật. | I4 | Đổi luật ở `MC-SCRIPT`. |
| 18 | **I5 template 4 chủ đề × 5 bố cục** = 20 tổ hợp (`MC-THEMES`, trục theme độc lập 5 preset). | I5 | — |
| 19 | **I6 bỏ vòng phản hồi lượt xem**: user tự quan sát, tool không làm; không có mục backlog. | I6 | — |
| 20 | **I7 chuỗi cập nhật tự vào lô** (`MC-STORY-THREAD`): bài mới trong 48 giờ về cùng người hoặc vụ có video thành ứng viên "UPDATE:" và được ưu tiên ở lô kế. | I7 | Tắt ưu tiên bằng cấu hình `story_thread.enabled`. |
| 21 | **I8 nghiệm thu 20 video, 5 mỗi nhãn**, user xem mẫu một lần; sau đó audit cuối độc lập trước bàn giao M8. | I8 | — |
| 22 | **Chế độ cào tách khỏi nhãn chủ đề**: 4 chế độ của user (`trend_latest`, `general`, `crime_records`, `celebrity_scandal`) là cách chọn bài; 4 nhãn nội dung là thuộc tính của bài. | Yêu cầu user | — |

**Việc cần user (tuỳ chọn):** bỏ chặn TLS reddit.com ở Kaspersky nếu muốn nguồn Reddit.

## 12. Kiểm cú pháp bằng bộ đọc thật

Mục 5 được kiểm bằng `parseSlices` và `deriveStructure` của `ai_pm_plan_declarations.js` với phong bì ở đầu mục 5. Kết quả ngày 04/11/2026 (bản 5): **31 slice, 0 lỗi khai báo** (không `SPEC_UNPARSEABLE`), 87 cạnh `dependsOn`, 30 đích là slice và 1 đích là id đã biết (`IMPL-PLAN-MC`), 0 đích lạ, **0 cổng sinh ra**, không vòng, mọi slice có ít nhất một đường dẫn mã hoặc test ngoài `docs/`; không mã `BL-<chữ>-<số>` đứng riêng; `MC-PILOT` phụ thuộc `MC-E2E` và sở hữu `tests/real/test_mc_pilot.py`. Kiểm thêm bằng chương trình: hai gói chung một tệp không thuộc vùng dành riêng đều có đường `dependsOn` nối nhau (0 cặp thiếu). Phần còn lại của lưới chắn (`REAL_TEST_REQUIRED`, `OWNED_PATH_NOT_DECLARED`…) chạy khi biên dịch; kế hoạch này chưa chạy `validateStructure` vì nó cần bản nháp gói của mô hình.

## 13. Phủ P0–P2 của báo cáo

Nguồn: bảng "Ưu tiên | Kỹ thuật của kênh" của `report/index.html` (28 dòng: 3 dòng KHÔNG_LÀM, 13 P0, 8 P1, 4 P2). Mục TUÂN_THỦ và KHÔNG_LÀM được thay bằng chính sách của user (hook và B-roll dùng chung lẫn vụ, không nhãn AI, không cổng nguồn cấp 1), trừ che mặt trẻ em.

| # | Ưu tiên | Mục của báo cáo | Slice phủ | Ghi chú |
|---|---|---|---|---|
| 1 | KHÔNG_LÀM | Né kiểm duyệt (K1LLS, M*RDER) | `MC-POLICY-SWITCHES` | Thay bằng chính sách user: không bảng từ né, không lexicon pháp lý. |
| 2 | KHÔNG_LÀM | Clip bodycam, CCTV, cáng không thuộc vụ làm hook | `MC-VIDEO-CLIPS`, `MC-HOOK-LIBRARY-MATCH` | Thay bằng chính sách user: hook dùng chung lẫn vụ. |
| 3 | KHÔNG_LÀM | Kho B-roll cảnh sát dùng chung lẫn vụ | `MC-VIDEO-CLIPS`, `MC-IMAGE-MATCH` | Thay bằng chính sách user: B-roll chung; ảnh AI chỉ khi thiếu, không nhãn. |
| 4 | P0 | Cổng nguồn cấp 1 + legal_status + khoá tên | `MC-CLASSIFY`, `MC-SCRIPT` | Thay bằng chính sách user (không cổng nguồn cấp 1); phần giữ: `source_certainty` quyết định câu kết nghi vấn. |
| 5 | P0 | Chọn chuyện: nhóm tin, tone, độ mới | `MC-CLASSIFY`, `MC-TOPIC-MIXER`, `MC-SOURCES` | `topic`, `emotional_tone`, `story_stage`, `heat_score`; chế độ `trend_latest` độ mới ≤ 48 giờ; nguồn Mỹ. |
| 6 | P0 | Caption câu tiêu đề + 5 hashtag tên người | `MC-METADATA` | 5 hashtag, caption ≤ 120 ký tự, cấm `#breakingnews`, dòng Source. |
| 7 | P0 | Băng tiêu đề nêu kết quả, tên, con số | `MC-SCRIPT`, `MC-CHROME` | Nội dung ở `MC-SCRIPT`; hình học ở `MC-CHROME`. |
| 8 | P0 | Băng viên thuốc cố định | `MC-CHROME` | y 230–490, bo góc ≥ 48. |
| 9 | P0 | Ô ảnh 25–75% chiều cao + nền mờ | `MC-CHROME` | `Box(0,480,1080,960)`; nền hook phóng to làm nhoè ở `MC-HOOK-ASSEMBLY`. |
| 10 | P0 | Lưới cảnh 5 s, 12–14 khối | `MC-SCRIPT`, `MC-CHROME` | Validator ở `MC-SCRIPT` (`production_plan.py`); lưới ở `MC-CHROME`. |
| 11 | P0 | Giọng vào ~4,5 s, 175–200 wpm | `MC-VOICE`, `MC-HOOK-ASSEMBLY` | `speed_fit.max` 1,25; `adelay` 4.500 ms. |
| 12 | P0 | Phụ đề karaoke nghiêng, tô từ, ~70% chiều cao | `MC-CHROME` | Preset phụ đề đổi theo revision mới. |
| 13 | P0 | Hook 4–5 s trong ô ảnh | `MC-HOOK-ASSEMBLY`, `MC-VIDEO-CLIPS`, `MC-SFX` | Bỏ nhãn "Illustrative footage" theo chính sách user; xuất xứ chỉ ghi metadata. |
| 14 | P0 | Nhãn ảnh AI | `MC-POLICY-SWITCHES` | Thay bằng chính sách user: không nhãn, công tắc mặc định tắt. |
| 15 | P0 | Che mờ trẻ em, nạn nhân, vũ khí | `MC-POLICY-SWITCHES`, `MC-BL-ARTICLE-CLIP` | Giữ `minor_child` cho ảnh và khung clip; các nhóm khác tắt theo chính sách user. |
| 16 | P0 | Khung 9:16, 61–70 s, Ken Burns, −16 LUFS | `MC-E2E`, `MC-PILOT` | Giữ nguyên; QC 61–70 s và −16 LUFS kiểm ở lô thật. |
| 17 | P1 | PiP chân dung khối hook 0–5 s | `MC-HOOK-ASSEMBLY`, `MC-IMAGE-MATCH` | PiP mọi nhân vật được nhắc (tối đa 4); thumbnail cũng đủ nhân vật. |
| 18 | P1 | Nền âm to + ducking | `MC-CHROME` | Bed −8 dB trong hook, sidechain 10–12 dB khi có giọng. |
| 19 | P1 | Ảnh khớp câu đang đọc | `MC-IMAGE-MATCH` | Gán theo entity; AI chỉ khi thiếu. |
| 20 | P1 | Giọng văn: mở bằng băng + danh tính, tone | `MC-SCRIPT`, `MC-VOICE` | Tone là trọng số, không cấm outrage. |
| 21 | P1 | Kết: câu chốt hoặc hứa cập nhật | `MC-SCRIPT`, `MC-METADATA` | Theo `source_certainty`; `ending_type` vào metadata. |
| 22 | P1 | Ô ghép 3 ảnh khối 5–10 s | `MC-IMAGE-MATCH` | Chân dung lớn trái, 2 ảnh phải. |
| 23 | P1 | Hook bằng clip của chính vụ + tiếng gốc | `MC-BL-ARTICLE-CLIP` | og:video và embed của bài; che mặt trẻ em trước khi đăng ký. |
| 24 | P1 | Giữ 5 bố cục hay một khuôn | `MC-CHROME`, `MC-THEMES` | Giữ 5 preset; chrome chung và theme là trục thứ hai. |
| 25 | P2 | Giờ đăng đề xuất | `MC-METADATA` | `suggested_publish_at` 00:00–03:59 ET; chỉ metadata, user tự đăng. |
| 26 | P2 | Chuỗi cập nhật (`story_thread`) | `MC-STORY-THREAD` | I7: tự vào lô, ưu tiên ở lô kế. |
| 27 | P2 | Lấy số liệu lượt xem để học | (không có) | **Bỏ theo I6**: user tự quan sát, tool không làm. |
| 28 | P2 | Chuyển cảnh lật gương, nhoè zoom | `MC-TRANSITIONS` | `mirror_pad` và `xfade` 0,2 s ở ≤ 3 mốc. |

Mọi dòng P0, P1 và P2 còn lại (trừ dòng 27) có ít nhất một slice phủ.

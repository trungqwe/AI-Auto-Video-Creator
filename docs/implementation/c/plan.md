# Kế hoạch triển khai Phân hệ C — Danh mục media và hook

> Task: `IMPL-PLAN-C` (planning_package), khoá `LOCK-IMPL-PLAN-C`. Baseline: `f40822e0ea258ed799fffa781c2c7b06776dd21a`.
> Kế hoạch là tài liệu, không cấp quyền kích hoạt sản xuất (`PRODUCTION_ACTIVATION_BLOCKED`). Mã nguồn do các slice trong `docs/implementation/c/slices.md` thực hiện.

## 1. Nguồn chuẩn

- `docs/modules/capability-c-storage.md` — đặc tả phân hệ; các lỗi được đính chính ở §2.
- `docs/11-roadmap.md` §10 (M4 — Kho media, hook và lưu trữ hybrid), §14 và §23 (open item `ROADMAP-OPEN-010`, `ROADMAP-OPEN-011`).
- `docs/09-contracts/05-content-media-contracts.md` — CT-MED-001..009, CT-HOOK-001, CT-HOOK-002.
- `docs/09-contracts/04-source-content-contracts.md` — CT-SRC-003.
- `docs/09-contracts/09-orchestration-contracts.md` — CT-ORC-008, CT-ORC-009.
- `docs/09-contracts/10-storage-contracts.md` — CT-STO-001, CT-STO-002.
- `docs/09-contracts/12-state-machines.md` — CT-STATE-005, CT-STATE-006, CT-STATE-012.
- `docs/10-test-strategy.md` §14.2 (bảng `TST-*-INV-*`) và §15 (E2E).
- `docs/parallel-delivery/bindings/README.md` và các binding ở §5.
- `docs/parallel-delivery/errata/m4-ci.md`.
- `docs/parallel-delivery/ownership-and-locks.yaml` — `PATH-SRC-CATALOG`, `LOCK-SRC-CATALOG`, `PATH-IMPLEMENTATION-PLANS`.
- `docs/adr/0002-authoritative-data-and-search.md` — PostgreSQL FTS và pgvector.
- Mã đã có, chỉ đọc: `src/controlplane/domain/statemachine/__init__.py` (`ArtifactLocationState`), `src/controlplane/domain/interfaces/uow.py` (`IUnitOfWork`), `src/controlplane/domain/concurrency.py` (`RevisionConflictError`).

## 2. Đính chính so với tài liệu cũ

Khi mâu thuẫn, nguồn chuẩn ở §1 và `docs/parallel-delivery/errata/m4-ci.md` thắng. Kế hoạch không chép lại các lỗi sau:

| # | Vị trí cũ | Nội dung sai | Nguồn chuẩn dùng trong kế hoạch |
| --- | --- | --- | --- |
| 1 | `docs/modules/capability-c-storage.md` §2 | `CT-HOOK-001` là port truy vấn hook cho D | `CT-HOOK-001` là `ImportHook`; truy vấn hook là `CT-MED-006`, truy vấn media là `CT-MED-005` |
| 2 | `docs/modules/capability-c-storage.md` §2 | Ghi lượt dùng qua `CT-STO-002` | `CT-STO-002` là `RegisterArtifactLocation` của I; lượt dùng là `CT-MED-008` trong unit of work của `CT-ORC-008`/`CT-ORC-009` |
| 3 | `docs/modules/capability-c-storage.md` §5 | `INV-006` là provenance media, `INV-012` là bộ đếm lượt dùng | `INV-006` là timeline mode, `INV-012` là canary secret (`docs/10-test-strategy.md` §14.2); C phục vụ phần C của `INV-005`, `INV-008`, `INV-010`, `INV-017` và CT-SRC-003 |
| 4 | `docs/modules/capability-c-storage.md` §4 | Mỗi `MediaAsset` có một SHA-256 duy nhất | Byte và SHA-256 thuộc artifact version của I (CT-STO-001); `MediaAsset` giữ canonical fingerprint bất biến; một byte nhiều provenance, một media logic nhiều rendition (CT-MED-001..003) |
| 5 | `docs/modules/capability-c-storage.md` §4 | C bảo đảm 100% video có visual hook, audio hook và thumbnail | Đây là ràng buộc của plan do D chọn (CT-MED-004, CT-MED-006); C cung cấp truy vấn và candidate độc lập |
| 6 | `docs/modules/capability-c-storage.md` §6, §7 | Path chỉ gồm `tests/unit/catalog/**`; lệnh `python -m unittest ... -k test_hook_classification` | Slice dùng `python -m pytest tests/unit/catalog/<tệp> -q -p no:cacheprovider`; `tests/integration/catalog/**` chờ đăng ký (CONV-C-06) |
| 7 | `docs/parallel-delivery/M4-CI-execution-package.md` (bảng tệp `src/catalog`) | `src/catalog/domain/lifecycle.py` chứa state machine CT-STATE-005/006; `src/catalog/infrastructure/db/repositories.py` PostgreSQL | State machine và migration là tài nguyên dùng chung, gửi IMPL-PLAN-CONVERGENCE (CONV-C-07, CONV-C-01) |
| 8 | `docs/parallel-delivery/M4-CI-test-plan.md` | Test ID `TST-CAT-*`; bằng chứng ở `docs/milestones/m4-media/evidence/`; INV-015 cho media lịch sử | Errata m4-ci #3, #4, #5: test ID trong catalog `docs/10-test-strategy.md`; bằng chứng `docs/delivery-evidence/<task-id>/report.md`; media lịch sử theo CT-SRC-003 |
| 9 | `docs/parallel-delivery/M4-CI-contract-freeze.md` | CT-STATE-012 bỏ cạnh `VERIFIED → MISSING`, có cạnh phục hồi | Errata m4-ci #6: có `VERIFIED → MISSING`; không có cạnh phục hồi từ `MISSING`, `CORRUPT`, `OUTCOME_UNKNOWN` |

## 3. Năng lực và aggregate

Aggregate do C sở hữu đơn writer (`docs/parallel-delivery/ownership-and-locks.yaml`): `MediaAsset`, `MediaAnalysis`, `Hook`, `MediaUsage`. C không sở hữu byte/location (I), không quyết định chọn media (D), không chạy probe, safety hay transform (E).

| Năng lực roadmap §10 | Nội dung | Slice |
| --- | --- | --- |
| C1 | Nhập media discovery từ bài và official social source | C-03 (quy tắc hợp nhất nội bộ); adapter seam CT-MED-001 chờ binding A→C (CONV-C-05) |
| C2 | Một byte nhiều provenance; một media logic nhiều rendition | C-01, C-03, C-04 |
| C3 | Index metadata/semantic/technical có version | C-01 (`index_revision`), C-06; index FTS/pgvector thật chờ migration (CONV-C-01) |
| C4 | Kho visual hook và audio hook độc lập; user nhập và sửa metadata trên UI | C-05; control API và UI gửi hội tụ (CONV-C-03, CONV-C-04) |
| C5 | Candidate query theo scene/entity/topic, score components, availability, safety và risk | C-02, C-06, C-08 |
| C6 | Media nguồn lịch sử vẫn khai thác được sau khi source bị remove | C-02, C-06, C-08 |
| C7 | Usage kỹ thuật tách production usage; `MediaUsage` cùng commit/rollback với completion unit of work | C-09; wiring vào unit of work completion của G gửi hội tụ (CONV-C-02) |

`MediaAnalysis` trong phạm vi kế hoạch này là metadata do E giao (semantics/technical/safety), C lưu và hiển thị (C-07); C không tự chạy phân tích.

## 4. Vị trí mã (D1)

- Mã: `src/catalog/**`, import root `src/` (import dạng `catalog.domain...`, không tiền tố `src.`).
  - `src/catalog/domain/`: value object, aggregate và trục trạng thái đọc.
  - `src/catalog/application/`: dịch vụ ứng dụng thuần, không I/O.
  - `src/catalog/ports/`: `typing.Protocol` cho repository phía C.
- Test: `tests/unit/catalog/**`, tên tệp `test_catalog_<chủ đề>.py` để không trùng basename; không tạo `__init__.py` hay `conftest.py` trong `tests/`.
- `tests/integration/catalog/**` đúng D1 nhưng chưa có trong pattern `PATH-SRC-CATALOG`; không slice nào dùng cho tới khi CONV-C-06 đăng ký.
- Không dựng `src/storage`, `src/orchestration`, `src/ui` hay bản sao aggregate đã có trong `src/controlplane` (ví dụ `ArtifactLocationState`, `IUnitOfWork`, `RevisionConflictError`): C import chỉ đọc từ `controlplane.domain.statemachine`, `controlplane.domain.interfaces.uow`, `controlplane.domain.concurrency`.
- Không có `src/catalog/infrastructure/db/**` trong các slice: persistence PostgreSQL cần migration (CONV-C-01).

## 5. Contract dùng và cung cấp

| Hướng | Contract | Binding và fixture | Slice |
| --- | --- | --- | --- |
| C cung cấp cho D | CT-MED-005 `QueryMediaCandidates` | `docs/parallel-delivery/bindings/c-d-media-candidates.json`, `tests/fixtures/contracts/c-d-media-candidates/payloads.json` | C-02, C-06, C-07 |
| C dùng từ I | CT-STO-001 `DeclareArtifactVersion` (artifact ref, `content_sha256`) | `docs/parallel-delivery/bindings/i-artifact-version.json`, `tests/fixtures/contracts/i-artifact-version/payloads.json` | C-01, C-03, C-04, C-05, C-07, C-08 |
| C là consumer của G | CT-ORC-008, CT-ORC-009 (`media_usage_manifest`) | `docs/parallel-delivery/bindings/g-c-i-completion.json`, `tests/fixtures/contracts/g-c-i-completion/payloads.json` | C-09 |
| C cung cấp gián tiếp cho F | CT-RND-002, CT-RND-003 (refs asset đã khoá) | `docs/parallel-delivery/bindings/f-render-package.json` | C-08 |
| Sự kiện miền | CT-EVT-002, CT-EVT-003 | `docs/parallel-delivery/bindings/domain-event-envelope.json` | Chưa dùng trong slice; phát event qua outbox gửi hội tụ (CONV-C-02) |

Seam chưa có binding (theo `docs/parallel-delivery/bindings/README.md`), C không tự đặt payload: A→C CT-MED-001, E→C CT-MED-003; ngoài ra CT-MED-002, CT-MED-004, CT-MED-006, CT-MED-007, CT-MED-009, CT-HOOK-001 và CT-HOOK-002 chưa có binding seam. Slice chỉ cài quy tắc miền nội bộ của C; adapter seam chờ slice binding (CONV-C-05).

## 6. Ánh xạ exit gate M4 (roadmap §10)

| Exit gate | Vai trò của C | Slice | Cách kiểm |
| --- | --- | --- | --- |
| Không location nào thành verified nếu chưa có integrity evidence | I sở hữu; C không ghi location state, chỉ đọc `ArtifactLocationState` | C-08 | `tests/unit/catalog/test_catalog_renderable.py`: chỉ `VERIFIED` không bị `not_usable`; module không có hàm ghi location |
| Không cleanup local khi output/reusable artifact cần giữ chưa cloud verified | I sở hữu cleanup; C bảo đảm mất byte không làm mất metadata/provenance | C-03, C-08 | `tests/unit/catalog/test_catalog_discovery.py` (provenance chỉ append); `tests/unit/catalog/test_catalog_renderable.py` (`MISSING` → `not_usable`) |
| Render tương lai chỉ có thể lấy artifact local đã verify | C trả `not_usable` cho artifact chưa verify, hash sai hoặc missing; `materialization_required` khi chưa ở local | C-08 | `tests/unit/catalog/test_catalog_renderable.py` (phần C của `TST-INT-INV-008`) |
| UI phân biệt original, processed, uncertain, failed và unavailable | C cung cấp read model `MediaAssetView` có `display_status`; màn hình thuộc H | C-07, CONV-C-04 | `tests/unit/catalog/test_catalog_asset_view.py` |
| Drive/OAuth/integrity phần M4 của G04 trên tài khoản test thật | Không thuộc slice C | CP7 (§9) | Không dùng mock để tuyên bố PASS |
| User duyệt C-I và `R2 Media Alpha` | C không tự ghi đã duyệt | pendingUserCheckpoint (§7) | Chờ user |

Test bắt buộc của roadmap §10 liên quan C:

- Phần C của `TST-INT-INV-008` (artifact unverified/hash sai không được render), hash mismatch và object missing: C-08.
- Same byte retry và byte khác version mới: phần C là C-03 (gửi lại cùng `discovery_id` → `duplicate_observation`; cùng fingerprint → không tạo asset mới; fingerprint khác → `new_asset`). Tạo artifact version mới cho byte khác thuộc I (CT-STO-001).
- Phần usage của `TST-WF-INV-010` và `TST-WF-INV-017`: C-09 với fake unit of work; bản PostgreSQL thật sau CONV-C-01, CONV-C-02 và CP7.
- Phần media của `TST-INT-INV-005` và `TST-E2E-002` (bài trùng có media mới): C-03.
- Source removed nhưng media lịch sử vẫn query được (CT-SRC-003, CT-MED-009, errata m4-ci #5): C-02, C-06, C-08.
- Sensitive Image Set, phần ánh xạ safety state sang usability (`TST-E2E-011`): C-02, C-07, C-08; detector và transform thuộc E.
- Clip không bị safety transform: C-04 từ chối rendition `blurred`/`recolored` cho media kind `clip`.
- Phần liên quan của `INV-012` (`TST-SEC-INV-012`, canary secret): ràng buộc chung trong `slices.md` cấm slice C đọc `Credentials/` hay gọi dịch vụ thật; C không nhận hay lưu secret. Kiểm canary trên log/event/history thuộc J và gói phát event của C (CONV-C-02).
- `INV-011`, `INV-015` (tombstone nguồn), upload gián đoạn, path traversal/symlink/junction/reserved name, hashtag/Unicode/collision, desktop restart/reconcile và cleanup authorization cũ: thuộc I hoặc A, ngoài phạm vi C.

## 7. Mục mở và quyết định mặc định (D8)

| Mã | Mục mở | Mặc định đã chọn | Lý do |
| --- | --- | --- | --- |
| D8-C-01 | Retention original/reusable/temporary (roadmap §10, ROADMAP-OPEN-010) | C không bao giờ xoá metadata/provenance; mất byte ở I chỉ đổi availability | Đặc tả C §4 và CT-MED-009; không mất dữ liệu; retention byte do I và user chốt |
| D8-C-02 | Scale dataset cho catalog/index (roadmap §10, ROADMAP-OPEN-011) | Slice dùng `typing.Protocol` repository và fake trong bộ nhớ; truy vấn luôn có `limit` và `page_cursor` | Không cam kết hiệu năng khi chưa có số liệu; contract đã có cursor. Đây là mặc định tạm cho slice, không phải quyết định ROADMAP-OPEN-011; mọi tuyên bố scale/hiệu năng phải chờ user chốt (xem danh sách chờ bên dưới) |
| D8-C-03 | Index semantic (ADR-0002 chưa chốt embedding/approximate index) | `index_revision` số nguyên trong metadata; khớp semantic trong slice là so khớp xác định theo entity/topic/scene | Không thêm thư viện; FTS/pgvector thật cần migration (CONV-C-01) |
| D8-C-04 | Trục trạng thái CT-STATE-005/006 | C khai báo giá trị trạng thái đọc (StrEnum đúng tên contract), không có hàm chuyển trạng thái; đồ thị chuyển gửi hội tụ (CONV-C-07) | State machine là tài nguyên dùng chung |
| D8-C-05 | Safety → usability | Chỉ áp cho `image`: `SAFE`, `PROCESSED_READY` → `usable`; `UNCERTAIN`, `DETECTION_FAILED`, `TRANSFORM_FAILED` → `usable_with_warning`; `UNREADABLE`, `NOT_ASSESSED`, `ASSESSING`, `TRANSFORM_REQUIRED`, `TRANSFORMING` → `not_usable`; `clip`/`audio` không có trục safety ảnh | CT-STATE-006 và `TST-E2E-011`; GIẢ ĐỊNH fail-closed cho trạng thái chưa đánh giá xong, xem lại khi E chốt pipeline |
| D8-C-06 | Rights `unknown`/`disputed` | Lưu và trả trong `safety_rights_status`, không tự chặn | CT-MED-002: quyền không chắc chắn không tự chặn theo quyết định user |
| D8-C-07 | Checksum khi Drive không có cùng checksum (roadmap §10) | Không thuộc C; C chỉ đọc `content_sha256` do I cấp | Ranh giới C/I |
| D8-C-08 | Media kind | `image`, `clip`, `audio`; thêm kind là thay đổi additive | Fixture c-d dùng `image`, `clip`; CT-HOOK-001 có audio |
| D8-C-09 | Trạng thái hiển thị UI | `unavailable` > `failed` (`UNREADABLE`, `TRANSFORM_FAILED`) > `uncertain` (`UNCERTAIN`, `DETECTION_FAILED`) > `processed` > `original` | Exit gate UI §10; trạng thái xấu hơn thắng để không che lỗi |
| D8-C-10 | Storage placement/quota thật của bốn tài khoản sau G04 (roadmap §10) | Không thuộc C; C không lưu vị trí lưu trữ hay tài khoản, chỉ giữ `artifact_version_ref` | Ranh giới C/I; cần tài khoản thật nên thuộc CP7 (§9), I chủ trì |

Danh sách chờ user (pendingUserCheckpoint), không ghi là đã duyệt:

- USER-CKPT-C-I-R2: user duyệt C-I và `R2 Media Alpha` (exit gate M4).
- USER-CKPT-D9-D10: thư viện và cách dựng lại runtime (§8).
- CP7 tài nguyên thật theo D5 (§9).
- ROADMAP-OPEN-010: retention/storage placement trước unattended cleanup (I chủ trì).
- ROADMAP-OPEN-011: scale workload trước mọi tuyên bố performance/scale của catalog/index (roadmap §23); D8-C-02 chỉ là mặc định tạm cho slice.
- GIẢ ĐỊNH của D8-C-05 cho trạng thái chưa đánh giá xong: xác nhận khi E chốt pipeline safety.

## 8. Thư viện (D10)

Kết luận: không cần thư viện mới cho C-01..C-09. Các slice chỉ dùng stdlib Python 3.13 (`dataclasses`, `enum`, `typing`, `hashlib`, `json`, `pathlib`) và `pytest==9.1.1` đã khoá trong `pyproject.toml`. `psycopg[binary]==3.3.5` đã có trong lock đủ cho PostgreSQL FTS về sau. Nếu CONV-C-01 cần adapter pgvector cho index semantic, gói đó tự đề xuất `tên==phiên bản` kèm lý do tại USER-CKPT-D9-D10; kế hoạch này không đề xuất phiên bản vì ADR-0002 chưa chốt embedding model.

## 9. Việc cần tài nguyên thật (CP7)

- Drive/OAuth/integrity phần M4 của G04 cho artifact media (I chủ trì; C chỉ cung cấp metadata).
- Corpus media thật có quyền sử dụng rõ ràng và Sensitive Image Set thật (safe, trẻ em, máu me, vũ khí, uncertain, unreadable) để chạy detector của E và kiểm usability của C.
- Đo scale catalog/index trên PostgreSQL thật (FTS/pgvector) sau CONV-C-01.
- Kiểm `MediaUsage` cùng commit/rollback trên PostgreSQL thật với completion của G (`TST-WF-INV-017`).

Chỉ làm sau khi user duyệt D5; tài khoản thật chỉ dùng qua secret broker của J, không mở, chép hay in bí mật.

## 10. Yêu cầu gửi IMPL-PLAN-CONVERGENCE

| Mã | Tài nguyên dùng chung | Yêu cầu |
| --- | --- | --- |
| CONV-C-01 | Migration | Bảng `media_assets`, `media_provenance`, `media_renditions`, `hooks`, `hook_revisions`, `media_usage` (cột `usage_kind` tách production/technical), index FTS (và pgvector nếu được duyệt); adapter PostgreSQL cho Protocol ở `src/catalog/ports/repositories.py` và `src/catalog/ports/usage.py` |
| CONV-C-02 | Composition root và unit of work completion của G | Wire `catalog.application.usage.MediaUsageRecorder` vào unit of work của completion (CT-ORC-008) để ledger và usage cùng commit/rollback; phát domain event của C qua outbox |
| CONV-C-03 | Control API | Lệnh `ImportHook`, `UpdateHookMetadata`, yêu cầu tải/xử lý lại một asset; truy vấn `MediaAssetView` |
| CONV-C-04 | UI shell (H) | Màn hình C-I: media theo bài/event, nhập visual/audio hook, sửa tag/ghi chú/bật tắt, xem original/rendition/provenance/safety/availability |
| CONV-C-05 | Binding (follow-up của CP1) | Mở binding A→C CT-MED-001, E→C CT-MED-003, C→D CT-MED-004 và CT-MED-006, C→D/F CT-MED-009 trước khi viết adapter seam |
| CONV-C-06 | Registry ownership | Thêm `tests/integration/catalog/**` vào `PATH-SRC-CATALOG` |
| CONV-C-07 | State machine | Thêm đồ thị CT-STATE-005 (discovery, rendition, availability) và CT-STATE-006 (image safety) vào `src/controlplane/domain/statemachine` |
| CONV-C-08 | Workflow (G) | Activity media discovery/acquisition và `RequestSupplementalMedia` (CT-MED-007) |
| CONV-C-09 | Tài liệu đặc tả | Sửa `docs/modules/capability-c-storage.md` theo §2 (ngoài owned paths của task này) |

## 11. Thứ tự slice và song song

- C-01 chạy trước: tạo package `catalog` và giữ `LOCK-SRC-CATALOG`.
- Sau C-01: C-02, C-03, C-04, C-05, C-09 chạy song song; mỗi slice khoá `LOCK-<taskId>` và sở hữu tệp tách biệt.
- C-06 sau C-02; C-07 và C-08 sau C-02 và C-04.
- Chi tiết từng slice ở `docs/implementation/c/slices.md`.

## 12. Giới hạn

- Kế hoạch là tài liệu; không cấp quyền production và không thay user checkpoint.
- Slice không sửa migration, composition root, lockfile, `tests/m2`, `ui/dist`, `App.tsx`, state machine dùng chung hay control API; không thêm thư viện; không gọi mạng hay dịch vụ thật; dùng fixture CP1 và fake cho phân hệ khác.

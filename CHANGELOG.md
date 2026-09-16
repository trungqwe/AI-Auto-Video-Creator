# Changelog

## 2026-09-17 — M2-P7A governance correction ready for independent review

- Independent review từ chối candidate `d5032eb` vì source scope, hardening identity và quality evidence; run GREEN cũ giữ nguyên. Correction source/tooling `6c3a52bde905ee5e71e12334da1873ed20f5c5db` bỏ `application/control_api/__init__.py`, khóa exact file allowlist và 36 full identities, thêm negative scope probe cùng quality build/wheel/mypy status.
- Fresh GREEN `run-m2-p7a-green-20260916224033`: oracle 4/4, H01–H36 36/36, mọi hồi quy PASS; migration `[1..7] → [1..6] → [1..7]`; Ruff/lock/build/wheel import PASS, mypy `SKIP_UNAVAILABLE_NOT_IN_LOCK`; secret scan CLEAN/0, semantic/provenance/hash/tamper PASS. Accepted oracle/RED/P1–P6 evidence bất biến. Lifecycle vẫn `M2-P7A_IMPLEMENTATION_READY_FOR_REVIEW`; P7B/P8/P9, M3 và Phân hệ A khóa.

## 2026-09-17 — M2-P7A implementation ready for review

- Khôi phục prerequisite PostgreSQL M2 an toàn từ Docker metadata trong bộ nhớ, không ghi DSN/credential. Triển khai Control API FastAPI, session hash/bootstrap một lần, Host/Origin/CSRF, local HTTPS, technical detail bền vững có audit, migration `0007` và StartBatch/config mutation cùng P1 UoW.
- Source/tooling commit `d5032ebc76e4946e5824ddf01c95ba28795eb377`; GREEN evidence `run-m2-p7a-green-20260916204220` đạt oracle 4/4, H01–H36 36/36 và hồi quy P6/P5B/P5A/P4/P3/P2/P1/P0/architecture/M1 4/5/5/9/11/11/11/33/6/93. PostgreSQL 18.6, orphan=0, secret scan CLEAN, semantic/provenance/tamper/hash DAG PASS. Không thay accepted RED oracle/evidence; P7A chờ independent review, chưa ACCEPTED/CLOSED. P7B/P8/P9, M3 và Phân hệ A vẫn khóa.

## 2026-09-17 — M2-P7A implementation authorized

- Independent review chấp thuận authority/design correction `24897a84bea68dadb7554380ffc469002c17e403`; user cấp quyền triển khai riêng P7A. Behavioral RED/oracle/evidence bất biến; P7A chưa GREEN hoặc ACCEPTED/CLOSED. P7B/P8/P9 khóa, M3 và Phân hệ A chưa được ủy quyền.

## 2026-09-17 — M2-P7A command transaction authority corrected (docs-only)

- Sau independent review của `72f3d65b374df617506d69bd6647c442be4c3044`, khóa `ControlApiCommandService` dùng một caller-owned P1 UoW cho P2 idempotency, StartBatch/P5A mutation và P3 outbox; cấm nested `IdempotencyCoordinator.submit()` và middleware commit receipt. Khóa StartBatch receipt/outbox identity, full rollback/duplicate proof và bootstrap capability proof thành 36 independent H01–H36. Accepted RED/oracle/evidence giữ nguyên; P7A implementation vẫn `LOCKED`, chờ independent review và user authorization riêng.

## 2026-09-16 — M2-P7A RED accepted; implementation authority design locked

- Independent review chấp nhận exact-four P7A Behavioral RED tại `7de529b80f2e058a2ae07d4b01e148707c39686e`; accepted oracle SHA-256 `63151da21b07c3dd92c5b4a7acc0d4f952f188ee2425a52c9d3ac8d34eb61035` và evidence `run-m2-p7a-20260916091430` giữ nguyên.
- Khóa docs-only future scope, application port/PostgreSQL adapter, `0007` schema/session token binding, actual FastAPI/Uvicorn middleware/TLS composition và 28 independent GREEN hardening keys. P7A implementation vẫn `LOCKED`; P7B/P8/P9, M3 và Phân hệ A chưa được ủy quyền.

## 2026-09-16 — M2-P7A Behavioral RED ready for independent review

- Khóa bốn oracle P7A độc lập cho Host spoofing, CSRF, technical detail và verified local TLS handshake; chỉ thêm structural seams ném `NotImplementedError`, không tạo migration `0007` hoặc implementation.
- Fresh evidence `run-m2-p7a-20260916091430` pin source/tooling `609cf70c72b3f08303c91b4a8c56bdec9f9237e3`, oracle SHA-256 `63151da21b07c3dd92c5b4a7acc0d4f952f188ee2425a52c9d3ac8d34eb61035`: exact 4/0/4/0/0, P6 4/4 + 18/18 hardening, mọi accepted regression GREEN, semantic/provenance/hash/tamper PASS. Implementation P7A vẫn khóa.

## 2026-09-16 — M2-P6 accepted; P7A Behavioral RED authorized

- Independent review chấp thuận/đóng corrected P6 tại `76daa18d66b2b468cf08189b0ec666fcc1638ec4`, evidence `run-m2-p6-20260916084617`; source/tooling và oracle SHA giữ nguyên.
- Chỉ mở P7A Behavioral RED. P7A implementation, P7B/P8/P9, M3 và Phân hệ A tiếp tục khóa.

## 2026-09-16 — M2-P6 independent-review correction

- Sửa duplicate completion khác logical input trả mã chuẩn `FORBIDDEN_TRANSITION`; variant retry đối chiếu cả expected registry revision; capacity retry chặn batch sai bằng `VALIDATION_ERROR`; registry được khởi tạo an toàn trong caller-owned UoW và stale first-use không để partial row kể cả khi caller bắt lỗi.
- Thay các probe alias bằng 18 hành động/khẳng định PostgreSQL độc lập; rollback version 6 được commit và tracker sau rollback là `[1,2,3,4,5]`. Fresh run `run-m2-p6-20260916084617` pin source/tooling `8120bac96cc5f5d223cb8f0c64daa904699c04c9`, P6 4/4 và tất cả regression PASS. Candidate cũ được giữ byte-exact nhưng **không được chấp thuận**; lifecycle vẫn `M2-P6_IMPLEMENTATION_READY_FOR_REVIEW`.

## 2026-09-16 — M2-P6 implementation ready for review

- Triển khai migration `0006`, orchestration domain/application và PostgreSQL adapter dưới caller-owned UoW với row locking cho variant CAS, capacity và completion idempotency.
- Fresh evidence `run-m2-p6-20260916134313` pin source/tooling `0b123805215bf3d77250676bcd04a5c749dca2d5`: P6 4/4, 12/12 hardening probes, P5B/P5A/P4/P3/P2/P1/P0/architecture/M1 đều GREEN; lifecycle dừng `M2-P6_IMPLEMENTATION_READY_FOR_REVIEW`.

## 2026-09-16 — M2-P6 implementation authorized

- Người dùng chấp thuận architecture-wired Behavioral RED `run-m2-p6-20260916190000`, khóa oracle SHA-256 `42cf15e9b87e88728aa3d84f633bafc98bb8794c2c4a271d72b74c7258252517` và mở implementation P6.
- P7+, M3 và Phân hệ A tiếp tục `NOT AUTHORIZED`; lifecycle mục tiêu của candidate là `M2-P6_IMPLEMENTATION_READY_FOR_REVIEW`, không tự đóng P6.

## 2026-09-16 — M2-P6 RED architecture wiring correction

- Bổ sung application persistence Protocol/repository factory injection cho cả bốn P6 services và structural `PostgresOrchestrationRepository` chỉ giữ caller-owned connection, không SQL/transaction ownership.
- Loại caller-supplied target khỏi capacity allocation; future implementation phải đọc persisted `ProductionBatch.target_count`.
- Fresh evidence `run-m2-p6-20260916190000` pin oracle SHA `42cf15e9b87e88728aa3d84f633bafc98bb8794c2c4a271d72b74c7258252517` và chứng minh architecture gates bằng AST.

## 2026-09-16 — Corrected M2-P6 Behavioral RED

- Sửa P6-003 để completion dùng actual concurrent winner và xác nhận loser không giữ capacity reservation.
- Sửa P6-004 để hai duplicate caller cùng nhận một `ledger_id`, trong khi persisted logical row count vẫn là một; bổ sung parent seeding chỉ khi `0006` tồn tại và zero-mutation checks cho injected failures.
- Fresh evidence `run-m2-p6-20260916174500` pin corrected oracle SHA `e5d2b248481366597a96caee313c46e03238e16369fb48799d6359ad80daccc1`; implementation P6 vẫn khóa.

## 2026-09-16 — M2-P6 Behavioral RED ready for review

- Khóa exact four P6 behavioral oracle cho execution fencing, variant CAS, batch capacity lifecycle và unique completion ledger; structural seams chỉ ném capability-specific `NotImplementedError`.
- Fresh evidence `run-m2-p6-20260916163000` xác nhận RED `4 failed / 0 passed / 0 errors / 0 skipped`, toàn bộ accepted regressions GREEN, migration `0006` vắng mặt và implementation P6 vẫn khóa.

## 2026-09-16 — M2-P5B accepted; P6 Behavioral RED authorized

- Independent review chấp thuận và đóng corrected M2-P5B tại source `d305bbb` với evidence `run-m2-p5b-20260916144500`.
- M2-P6 chỉ được phép tạo Behavioral RED; implementation P6, P7+, M3 và Phân hệ A vẫn khóa.

## 2026-09-16 — M2-P5B corrected implementation candidate

- Tách toàn bộ SQL/row mapping P5B khỏi application sang PostgreSQL adapter dùng connection thuộc caller-owned P1 UoW.
- Khóa exact verification evidence, credential boundary trên mọi location ref, immutable CleanupAuthorization và composite location/version/hash binding.
- Fresh evidence `run-m2-p5b-20260916144500` đạt exact P5B 5/5, toàn bộ regression và sáu real-PostgreSQL hardening probes; lifecycle vẫn `M2-P5B_IMPLEMENTATION_READY_FOR_REVIEW`.

- Triển khai P5B artifact metadata persistence trên PostgreSQL: migration `0005` forward/rollback, immutable ArtifactVersion, P4-backed ArtifactLocation CAS và immutable CleanupAuthorization kết thúc ở `CLEANUP_AUTHORIZED`; không delete bytes và không `CleanupCompleted`. Candidate chờ independent review.

- Corrective Behavioral RED M2-P5B sau independent audit: chuyển structural seams về đúng `storage_meta`, thêm test-only persisted ArtifactVersion prerequisite chỉ khi schema `0005` tồn tại, và nâng evidence lên generic fail-closed validator với hash recomputation/tamper-negative proof. Không tạo `0005` và không implement P5B.

- Khóa Behavioral RED M2-P5B trên source `bd225c8cf1b3416f06dd96aea483db9cba757a62`: exact five oracle fail đúng các capability ArtifactVersion, P4-backed ArtifactLocation, CleanupAuthorization, production migration `0005` còn thiếu và scoped CAS. Regressions P5A/P4/P3/P2/P1/P0/architecture/M1 giữ GREEN 5/9/11/11/11/33/6/93; không triển khai P5B và không tạo `0005`.

- Hoàn tất corrected candidate M2-P5A: test-wiring commit riêng, correction RED/ GREEN cho persisted CAS và hai explicit-ID path, PostgreSQL adapter được inject dưới P1 UoW, không global psycopg patch hoặc migration-ledger side effect. Closure mới pin source `413070c074997d6f02c2d7933c64d0d17c9b9704`: P5A/P4/P3/P2/P1/P0/architecture/M1 = 5/9/11/11/11/33/6/93, không skip. OAuth runtime khôi phục qua người dùng cấp quyền lại; historical M1 evidence giữ nguyên byte. Dừng `M2-P5A_IMPLEMENTATION_READY_FOR_REVIEW`; P5B+ vẫn khóa.

- Harden P5A exact RED oracle: baseline migration 1--3 tách riêng khỏi future `0004`, graph invalidation có các branch độc lập, secret schema kiểm tra plaintext-value surface thay vì substring `secret`, và race/unique proof được chuẩn bị cho GREEN. Không có implementation P5A hay migration `0004`.

- Thiết lập Behavioral RED M2-P5A exact 5 trên PostgreSQL thật: structural seams importable chỉ ném `NotImplementedError`; 5/5 failure đúng capability ConfigRevision, secret-handle boundary, event/audit safety, production migration `0004` và scoped CAS. Evidence run `run-m2-p5a-20260915090417` ghi P4 9/9, architecture 6/6, orphan=0 và secret scan CLEAN. Không có implementation P5A, migration `0004`, P5B hay work package sau.

- Tách rõ hai namespace revision P5A: `config_revision_number` immutable cho lineage/version CT-CFG-001 và `revision` CT-CMN-005 cho CAS, khởi tạo 1 rồi tăng đúng một per state mutation. CT-CFG base revision nay chỉ lineage immutable; concurrent publish phân biệt stale CAS với unique version identity. P5B plan được accept nhưng vẫn `RED_LOCKED` sau P5A/`0004`; không có source/test/SQL/runtime evidence.

- Làm rõ contract/plan P5 trước RED: CT-STATE-013 khóa đầy đủ ConfigRevision graph và security invalidation bất biến; P5A tái dùng RFC 8785/JCS P2 cho `content_hash`; P5B chỉ thực thi cleanup đến `CLEANUP_AUTHORIZED`, `CleanupAuthorization` là immutable fact không status mutable. Giữ đúng 5+5 oracle, migration `0004 → 0005` và trạng thái review; không có source/test/SQL/runtime evidence.

- M2-P4 đã được independent audit `ACCEPTED / CLOSED`. Hoàn tất kế hoạch/traceability riêng cho P5A Config & Secret Boundary và P5B Artifact Metadata: catalogue chính xác 5+5 oracle, protocol PostgreSQL/evidence fail-closed, UoW/migration guard và frozen regressions. `INVALIDATED` của ConfigRevision là contract clarification bắt buộc trước RED; P5B RED/implementation chờ P5A migration `0004` được accept. Không có source, test, SQL hay runtime evidence mới.

- M2-P4: triển khai state machine thuần và mapper OperationView đã GREEN exact 9; closure evidence bind source/runtime, P3/P2/P1/P0/M1 frozen regressions, PostgreSQL disposable DB, secret scan và verifier fail-closed. Trạng thái là `M2-P4_IMPLEMENTATION_READY_FOR_REVIEW`, chưa `ACCEPTED / CLOSED`; P5..P7/M3/Module A không mở.

Mọi thay đổi đáng chú ý của dự án được ghi trong tệp này theo cấu trúc [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Dự án chưa phát hành phiên bản sản phẩm.

## [Unreleased]

### Changed

- Hardened 9 oracle Behavioral RED M2-P4: các invariant forbidden/error aggregate type, evidence-gated reconciliation, cleanup eligibility và terminal/no-outgoing được bao phủ đầy đủ trong identity hiện hữu. Run mới vẫn 9 RED đúng structural seam, architecture 6/6 và secret scan CLEAN; implementation tiếp tục bị cấm.
- Thiết lập exact Behavioral RED harness M2-P4: 9 oracle pure Python collect thành công và đều RED đúng structural seam `NotImplementedError`; architecture 6/6, secret scan CLEAN/0. Không có P4 functional implementation, DB/Docker/DSN, API/UI/Temporal hoặc work package kế tiếp; dừng `M2-P4_RED_READY_FOR_REVIEW` để independent audit.
- Làm rõ hợp đồng có thẩm quyền M2-P4: Operation reconciliation chỉ đi `OUTCOME_UNKNOWN → SUCCEEDED|FAILED` khi có evidence, `FAILED` terminal; Job/Batch có cạnh direct completion được liệt kê tường minh. Kế hoạch RED vẫn giữ nguyên 9 identity và chưa có test/source/RED runtime.
- Hoàn tất kế hoạch M2-P4 cho máy trạng thái thuần và mapping `OperationView`: khóa traceability `CT-STATE-008..012`, `CT-API-007`, revision/error semantics, catalogue RED đề xuất đúng 9 oracle, provenance/evidence và regression frozen. Không có P4 test, source, migration hoặc RED runtime; dừng tại `M2-P4_PLAN_READY_FOR_REVIEW` chờ independent audit.
- Ghi nhận M2-P3 `ACCEPTED / CLOSED` theo independent audit closure đã xác nhận.
- Hoàn tất candidate implementation M2-P3: transactional outbox, consumer checkpoint/quarantine, operation stream và migration `0003`/rollback. Closure evidence xác nhận P3 11/11, P2 11/11, P1 11/11, P0 33/33, M1 93/93, PostgreSQL 18.6, orphan=0, secret scan CLEAN và verifier PASS; dừng tại `M2-P3_IMPLEMENTATION_READY_FOR_REVIEW` để independent audit.
- Hardened và thực thi Behavioral RED M2-P3: exact 11 oracle chạy trên PostgreSQL 18.6, đều fail tại migration absence hoặc structural P3 seam dự kiến, orphan=0 và architecture 6/6. Dừng tại `M2-P3_RED_READY_FOR_REVIEW`; chưa có implementation hoặc migration `0003`.
- Khởi tạo structural Behavioral RED harness M2-P3 với đúng 11 oracle và stub importable không có behavior. Dừng `M2-P3_BEHAVIORAL_RED_BLOCKED_EXTERNAL` vì virtualenv thiếu `psycopg_pool==3.3.1`; không có collection/full RED, migration `0003` hoặc implementation P3.
- Hiệu chỉnh contract planning M2-P3: OperationStream trace tới `CT-API-008`; outbox giữ đủ MessageEnvelope/DomainEvent; aggregate ordering không unique; quarantine scope theo consumer; và ordering/reconcile facts durable được khóa rõ. P3 vẫn chỉ ở plan review.
- Khóa kế hoạch M2-P3 sau khi M2-P2 được `ACCEPTED / CLOSED`: xác định schema `0003`, adapter PostgreSQL/UoW boundary, quarantine/watermark durable, exact 11 Behavioral RED oracle, runtime/evidence profile và frozen regressions. Dừng tại `M2-P3_PLAN_READY_FOR_REVIEW`; không có P3 source, test harness, migration hoặc RED runtime.
- Hoàn tất correction replay receipt M2-P2: accepted receipt materialize toàn bộ persisted logical-result shape; same-key/same-hash replay giữ receipt/command ID và trả lại operation/resource/revision/timestamp bền vững với `duplicate` chỉ là disposition transient. Closure evidence xác nhận P2 11/11, P1 11/11, P0 33/33, M1 93/93, PostgreSQL 18.6, secret scan CLEAN và hash DAG PASS.
- Hoàn tất correction RFC 8785 Number serialization M2-P2: JCS fixed-decimal không còn xóa trailing zeroes có nghĩa; P2-004 bao phủ vector Appendix B/IEEE-754 và closure evidence mới xác nhận P2 11/11, P1 11/11, P0 33/33, M1 93/93, runtime PostgreSQL 18.6, secret scan CLEAN và provenance/hash DAG PASS. Dừng tại `M2-P2_IMPLEMENTATION_READY_FOR_REVIEW` để independent audit.
- Hoàn tất implementation candidate M2-P2: contract envelope/ProblemDetail, RFC 8785 JCS request hash, durable PostgreSQL idempotency, CAS revision, migration `0002`/rollback và evidence profile fail-closed. Closure evidence xác nhận P2 11/11, P1 11/11, P0 33/33, M1 93/93, architecture 6/6, runtime PostgreSQL 18.6, secret scan CLEAN, provenance/hash DAG PASS; dừng tại `M2-P2_IMPLEMENTATION_READY_FOR_REVIEW` để independent audit.
- Cô lập fixture migration fault-injection P1 vào production baseline `0001`/rollback, để migration P2 về sau không đổi prerequisite của P1-002/003/009/010. Không đổi P1 testcase identity, assertion, production behavior hay `MigrationRunner` semantics.

### Added

- Hiệu chỉnh RED harness M2-P2 theo audit `962b5928eaf7190a19d745d4b8e746a766e147a2`: 11 oracle nay encode envelope/ProblemDetail matrix, JCS vector+replay, SQL receipt assertions, concurrent race, workspace/restart, PostgreSQL CAS probe và P1 MigrationRunner `0002` absence. Không có production behavior/`0002`; điểm dừng `M2-P2_RED_HARNESS_READY_BLOCKED_EXTERNAL` do DSN chưa có.
- Hoàn tất final correction của RED harness M2-P2 theo audit `443648b427bae7985ebc35a8445be7782102e235`: siết matrix contract, JCS logical-hash vector, UoW-bound repository/CAS, race/restart/rollback oracle và orphan teardown guard. Không có implementation hay migration `0002`; điểm dừng `M2-P2_RED_HARNESS_FINAL_READY_BLOCKED_EXTERNAL` do `M2_TEST_PG_DSN` chưa có.
- Khép correction false-green hẹp của RED harness M2-P2: bổ sung SQL non-orphan/race assertions, tách JCS invariants, mô tả semantic migration/rollback `0002` cho GREEN tương lai và chạy RED độc lập P2-001/002. Không có implementation hay migration `0002`; P2-003..011 vẫn chờ `M2_TEST_PG_DSN`.
- Ghi nhận prerequisite run M2-P2 an toàn: Python 3.13.15, psycopg 3.3.5 và psycopg-pool 3.3.1 khớp lock, nhưng `M2_TEST_PG_DSN` absent. Dừng trước collection/full PostgreSQL run; không tạo evidence giả hoặc implementation P2.
- Tái xác minh checkpoint prerequisite M2-P2: `M2_TEST_PG_DSN` vẫn absent; giữ dừng external trước collection/full run, không sửa harness hoặc production source.
- Kiểm tra Docker provisioning M2-P2 theo checkpoint: Docker CLI 29.7.2 có mặt nhưng daemon unavailable, đồng thời không có DSN external. Dừng fail-closed, không cài Docker hay thay đổi cấu hình máy.
- Thu thập full Behavioral RED M2-P2 trên PostgreSQL 18.6 Docker (`CREATEDB=true`): exact 11 oracle chạy, 6 `VALID_BEHAVIORAL_RED`, 5 `UPSTREAM_PATH_RED`, orphan disposable DB bằng 0. Không có implementation P2, migration `0002` hay mở P3; evidence chờ independent audit.

- Bắt đầu Behavioral RED M2-P2 sau audit plan `8bbc61ff22f5ef5009e8ba3cf75f08b1291573c3`: tạo đúng 11 oracle khóa và structural stubs chỉ ném `NotImplementedError`; collect đạt 11/11. `M2_TEST_PG_DSN` không có, nên PostgreSQL/CREATEDB/orphan prerequisite được ghi `BLOCKED_EXTERNAL`, không có full-run/evidence RED giả và implementation vẫn khóa.

- Correction docs-only M2-P2 R2 theo independent audit `21c97bebd936e50aa43cff352d426f781a820fdb`: property names RFC 8785/JCS được sort raw/unescaped theo unsigned UTF-16 code units, không dùng Unicode code-point/UTF-8/UTF-32 ordering; P2-004 có vector non-BMP với canonical bytes và SHA-256 cố định. Điểm dừng: `M2-P2_PLAN_READY_FOR_RED_APPROVAL_R2`.

- Correction docs-only M2-P2 theo independent audit `236378f6ec442f9fcd7e84507a60b6e1b5b1b7a3`: khóa full `ProblemDetail` surface, RFC 8785 JCS byte canonicalization/test vectors, PostgreSQL CAS production primitive, replay `duplicate` transient semantics, narrowed receipt-only concurrency claim, RED/final evidence artifact protocol và envelope matrix. Điểm dừng: `M2-P2_PLAN_READY_FOR_RED_APPROVAL`; không có P2 source/test/evidence runtime.

- Chuẩn hóa SPEC/implementation plan M2-P2 trước RED: khóa đúng contract scope `CT-CMN-001/002/003/005/006/010/011`, qualifier nền tảng `CT-API-001` và `ADR-0004`; chốt schema/rollback production `0002`, canonical request hash, receipt/replay/revision semantics, exact 11 mandatory RED oracle, 6 gates và discipline evidence P2. Không có source, test hoặc runtime evidence P2. Điểm dừng: `M2-P2_PLAN_READY_FOR_REVIEW`.

- Independent audit tại `90f4195e928ecbf5622d9760465a5d09d8b4f867` chính thức chấp thuận/đóng `M2-P1`: exact P1 11/11 GREEN, frozen M2-P0 33/33, M1 93/93, PostgreSQL 18.6, Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1, production pool `psycopg_pool.ConnectionPool`, `CREATEDB=true`, orphan DB=0, secret scan CLEAN, 6/6 P1 gates PASS và evidence provenance/hash DAG PASS. `M2-P2_AUTHORIZED` chỉ cho `SPEC → PLAN → RED`; cấm implementation P2 trước Behavioral RED hợp lệ có evidence và independent audit. M3/Phân hệ A vẫn `NOT AUTHORIZED`.

- Hoàn tất correction R2 M2-P1 theo independent audit `2541c58a85c301c9499d7179f54b4f6607b2c524`: P1-006 xác minh composite FK từ production migration, P1-010 xác minh rollback side-effect/probe và applied tracking, P1-004 bổ sung crash-release proof, destructive guard khóa exact fixture identity, production dùng bắt buộc `psycopg_pool.ConnectionPool` và P1 synthesis chạy trong locked Controlplane environment. Artifact `runtime-capability.json` cùng run xác nhận Python 3.13.15, psycopg 3.3.5, psycopg-pool 3.3.1, PostgreSQL 18.6, CREATEDB=true, orphan DB=0; P1 11/11, frozen P0 33/33, M1 93/93, 6/6 gate PASS, secret scan CLEAN, `--verify-only` PASS. Điểm dừng: `M2-P1_READY_FOR_REVIEW_R2`; không mở P2.

- Hoàn tất M2-P1 implementation và evidence: raw SQL migration runner với strict ordering/checksum/bounded advisory lock, disposable rollback guard, UnitOfWork/pool cleanliness, Workspace/Actor/AuthSession repositories và composite workspace FK. P1 synthesis xác nhận 11/11 mandatory oracle GREEN, frozen M2-P0 exact 33/33, M1 93/93, secret scan CLEAN, provenance/hash DAG hợp lệ; `synthesizer_p1.py --verify-only` đạt `VALIDATION: PASS`. Trạng thái dừng: `M2-P1_READY_FOR_REVIEW`; không mở P2.

- Independent audit xác nhận `M2-P1_RED_CONFIRMED` tại checkpoint `e42bd90e8cd8ff0e688a2db78407ef9e32d660b9`: PostgreSQL 18.6 thật đã collect/chạy exact 11 oracle function-scoped, 11/11 là Behavioral RED cấp package (5 direct-target, 6 upstream-path), 0 setup failure, 0 unexpected pass và 0 orphan database. M2-P1 implementation được ủy quyền; P0 không đổi và P2 vẫn khóa.

- Chạy Behavioral RED M2-P1 trên PostgreSQL 18.6 riêng biệt với exact 11 oracle function-scoped (run `ba8100a55e714332a3ebe41ca9d18944`): cleanup không để lại disposable database; 5 failure là `VALID_BEHAVIORAL_RED` và 6 là `ORACLE_MISMATCH`, nên phase chuyển `M2-P1_BEHAVIORAL_RED_CORRECTION_REQUIRED`. Bổ sung raw prerequisite/collection/full output và che `repr` DSN của fixture chỉ trong test harness. Không có production behavior, không sửa P0 và không mở P2.

- Hiệu chỉnh RED harness M2-P1 sau audit `42e1859b19460f8254d8d5be500f910a1c262570`: thêm bootstrap schema test-only trong disposable DB cho P1-005/006/007/011 để các oracle này không bị migration stub che khuất. P1-006 cố ý quan sát `DID NOT RAISE ForeignKeyViolation`; P1-007 seed direct SQL rồi chạm scoped ports. Không có production migration/database behavior; trạng thái giữ `M2-P1_BEHAVIORAL_RED_BLOCKED_EXTERNAL`.

- Hiệu chỉnh test/evidence M2-P1 theo independent audit commit `65af9f84f881e03e7be95d1dda44243030aca1f6`: fixture disposable DB function-scoped cho từng oracle; P1-005 chứng minh commit + rollback; P1-007 seed và tái xác nhận isolation không-vacuous; P1-011 khóa `pool_max_size=1` và PostgreSQL backend PID; application ports chỉ nhận injected UoW factory. Bổ sung raw collection/prerequisite evidence. Không có production behavior; phase giữ `M2-P1_BEHAVIORAL_RED_BLOCKED_EXTERNAL`.

- Bắt đầu Behavioral RED M2-P1 theo User Approval sau independent re-audit HEAD `5ba3a1601f0e1402e54a82feb5b44fe94cda9197`: tạo đúng 11 oracle khóa và structural stub importable trong Allowed File Scope, không có business/DB implementation. Collection đạt 11/11 không lỗi import/cú pháp. P1-008 RED hợp lệ qua `NotImplementedError` của destructive guard; 10 oracle PostgreSQL dừng `BLOCKED_EXTERNAL` do thiếu `M2_TEST_PG_DSN`, không có fallback credential/mock. Evidence: `docs/milestones/m2-control-plane/evidence/m2-p1/red-p1-stdout.txt` và `red-observations.md`. Không mở P2.

- Nghiệm thu Milestone M2-P0 & Hiệu chỉnh Kế hoạch Kỹ thuật Milestone M2-P1 (13-09-2026):
  - Người dùng chính thức nghiệm thu `M2-P0 = ACCEPTED / CLOSED` tại commit `d84c1d7` với 33/33 tests PASSED, 93/93 tests hồi quy M1 PASSED (0 failed, 0 skipped), 6/6 Package Gates PASS, deterministic provenance 1:1, SHA-256 DAG hợp lệ.
  - Ủy quyền triển khai `M2-P1 = AUTHORIZED TO IMPLEMENT` theo chu trình chuẩn `RED → IMPLEMENT → RUN → TEST → FIX → VERIFY → EVIDENCE → COMMIT`.
  - Hoàn tất hiệu chỉnh kế hoạch kỹ thuật M2-P1 (docs-only correction) bám sát 10 điểm kỹ thuật hẹp của Người dùng trước khi bắt đầu Behavioral RED:
    1. Đồng bộ metadata: M2 = `IMPLEMENTATION IN PROGRESS`, M2-P0 = `ACCEPTED / CLOSED`, M2-P1 = `AUTHORIZED` trong `spec.md` và `implementation-plan.md`.
    2. Khóa Allowed File Scope của P1: bổ sung chính xác `profile_p1.py` và `synthesizer_p1.py`; cấm sửa core evaluator/validator.
    3. Áp dụng Disposable Test Database (`m2_p1_test_<uuid>`), không parameterized schema; schema cố định `controlplane`; admin test DSN từ environment; destructive guard yêu cầu tên DB hợp lệ test + `is_test_env=True` (cấm generic `allow_destructive=True`).
    4. Phân biệt rõ `AuthSession` (`cp_auth_sessions`) phục vụ identity/control plane foundation với `AppSession` (`cp_app_sessions` dành cho desktop app data model).
    5. Đầy đủ `IWorkspaceRepository`, `IActorRepository`, `IAuthSessionRepository`; workspace-scoped methods (zero unscoped get_by_id); composite FK DB-level invariants ngăn cross-workspace.
    6. Khóa transaction ownership: `SqlUnitOfWork` sở hữu đúng một pooled connection và một DB transaction; repository không tự acquire pool connection, không commit/rollback; `TransactionManager` chỉ là UoW factory/coordinator.
    7. Siết migration runner oracle: forward regex `^\d{4}_[a-z0-9_]+\.sql$`, rollback regex `^\d{4}_[a-z0-9_]+\.rollback\.sql$`; bounded advisory lock timeout 5s với `pg_try_advisory_lock` và monotonic deadline; fail-closed khi gap, missing file, duplicate, tamper; 0001 rollback dọn dẹp và drop schema `controlplane`.
    8. Loại bỏ vòng tự tham chiếu: không đưa live evidence test vào `m2-p1-tests.xml`; lưu stdout RED thô vào `red-p1-stdout.txt`.
    9. Đăng ký semantic profile tất định qua extension point `register_semantic_profile(M2P1SemanticProfile())`.
    10. Khóa 6 machine-readable gates (`GATE-P1-01` .. `GATE-P1-06`) trước khi viết test RED.
  - Dừng tại `M2-P1_PLAN_READY_FOR_RED_REVIEW`. M3 và Phân hệ A tiếp tục bị khóa hoàn toàn (`NOT AUTHORIZED`).

- Hiệu chỉnh kế hoạch M2-P1 R2 theo independent audit HEAD `7445504d4fac3b2ff03378d1f02fe9f2fc69b548` (docs-only): dùng đúng `PackageSemanticProfile`/process-local registration và P1-aware verifier; thêm evidence P0 regression trong pipeline cùng 11 mandatory behavioral oracle; siết `M2_TEST_PG_DSN`/destructive identity, ranh giới token P7A và lifecycle identity. Điểm dừng chuyển thành `M2-P1_PLAN_READY_FOR_RED_REVIEW_R2`; không code P1, không Behavioral RED, không sửa P0 và không mở P2.

- Hiệu chỉnh kế hoạch M2-P1 cuối theo independent re-audit HEAD `747d609cfdf226371e1d5b2f4b73d240cd8210de` (docs-only): thay oracle cross-workspace delete bằng public port read/status/revoke/expire; thêm traceability 11 oracle, exact frozen P0 testcase set 33/33, migration fault sandbox và admin teardown đúng PostgreSQL. Điểm dừng chuyển thành `M2-P1_PLAN_READY_FOR_RED_APPROVAL`; không code P1, không Behavioral RED, không sửa P0 và không mở P2.

- Hoàn tất khắc phục toàn diện đợt Tái kiểm toán Độc lập R2 Milestone M2-P0 (13-09-2026):
  - Khái quát hóa Semantic Evaluator Profile Registry & Dispatch Pattern: Xây dựng `PackageSemanticProfile` và `SemanticProfileRegistry`; triển khai `M2P0SemanticProfile` quản lý policy P0; fail-closed chặn đứng unknown profile và cross-package spoofing; mở rộng cho P1-P8 qua extension point `register_semantic_profile` mà không sửa core validator.
  - Chứng minh Kép Frozen Backend Graph & Clean Wheel Install: Tạo clean venv với dynamic uv binary resolver (`resolve_uv_executable`); thực hiện Proof A (cài đặt frozen từ `requirements.lock`, kiểm chứng observed package versions khớp 100%) và Proof B (build wheel và cài đặt với `--no-deps`, thực thi import và entrypoint sạch); bổ sung negative test mutate lockfile fail closed.
  - Làm rõ Build-System Version Pins Claim: Xác định `setuptools==75.8.0` và `wheel==0.45.1` là exact build-system version pins trong `pyproject.toml`, làm rõ phạm vi không overclaim là nằm trong runtime lockfile.
  - Single-Pipeline Deterministic Evidence Synthesis: Triển khai `synthesizer.py` thực thi tuần tự tuyến tính theo một `run_id` duy nhất (`run-m2-p0-...`): M1 suite -> M2-P0 suite -> Final Secret Scan (lần scan duy nhất sản sinh artifact cuối) -> observed metrics parsing -> status.json -> status.md -> commands.jsonl (với execution metadata khớp chính xác 100% timestamp và tệp) -> hashes.sha256 acyclic DAG -> read-only integrity, semantic và provenance verification.
  - Nâng cấp bộ kiểm thử M2-P0 lên **33/33 tests PASSED**; hồi quy M1 duy trì **93/93 tests PASSED** (0 failed, 0 skipped); 6/6 Package Gates đạt `PASS`; cập nhật thư mục bằng chứng `docs/milestones/m2-control-plane/evidence/m2-p0/` và đạt trạng thái `READY_FOR_REVIEW`.



- Phê duyệt User Checkpoint Milestone M1 và kích hoạt Milestone M2 (13-09-2026):
  - Milestone M1 chính thức chuyển sang `ACCEPTED / CLOSED`: Người dùng phê duyệt toàn bộ kết quả kiểm chứng thực nghiệm P0..P6 (93/93 tests passed, 0 skipped, coverage 83%), Báo cáo Kiểm toán Exit Gate `docs/milestones/m1-proof/audit-r5.md` (kèm R5.1 Addendum); G01 và G04 giữ `PARTIALLY_PROVEN (PASS_M1_SCOPE)`; G07 giữ `SMOKE_COMPATIBILITY_PASS_M1_SCOPE`; ghi nhận limitation DPAPI trên một Windows user; giữ nguyên toàn bộ Audit R1–R5/R5.1 và evidence lịch sử.
  - Milestone M2 chính thức chuyển sang `AUTHORIZED_FOR_PLANNING_AND_IMPLEMENTATION`: Khởi động giai đoạn xây dựng M2 Control Plane và nền tảng có thể quan sát (PostgreSQL business state, transactional outbox/idempotency, state machines, J config/secret, I artifact metadata, G orchestration shell, H admin API & SSE stream) theo quy trình `SPEC → PLAN → RED → IMPLEMENT → RUN → TEST → FIX → VERIFY → EVIDENCE → COMMIT`.
  - Milestone M3 và Phân hệ A tiếp tục duy trì trạng thái `NOT AUTHORIZED` (khóa chặt cho tới khi M2 đạt exit gate và có User Checkpoint riêng).
- Hoàn tất khắc phục triệt để đợt tái kiểm toán độc lập M1 R5.1 trên GitHub HEAD commit `ed0fc83` (1 BLOCKER secret ownership, 1 MAJOR semantic validation) và cập nhật Báo cáo Kiểm toán `docs/milestones/m1-proof/audit-r5.md` (mục 6. R5.1 Addendum):
  - R5.1-01 (Broker-Owned OAuth Provisioning & Process Isolation): Sửa ranh giới secret ownership: Desktop orchestrator (`drive_live_probe.py`) loại bỏ hoàn toàn việc import `DPAPISecureVault` và `InstalledAppFlow`, không gọi `vault.get_account()`; Broker subprocess là tiến trình duy nhất mở và giải mã DPAPI vault; Desktop ủy quyền provisioning cho broker process qua HTTP IPC `POST /api/provision` (hoặc CLI flag `--provision-credentials`) và chỉ nhận kết quả thành công mà không bao giờ chạm vào refresh token hay client_secret; Desktop client nhận ephemeral access token ngắn hạn; thực nghiệm live probe E3 thành công trên Google Drive thật (`broker_pid=23076`, `desktop_pid=23768`, upload 64 bytes ID `1R6D6B...R5Ux`, đối soát SHA-256 khớp 100%, dọn dẹp file test); xuất `drive_e3_evidence.json` đầy đủ các trường machine-readable và limitation: "DPAPI proof runs under one Windows user; OS-account isolation between cloud host and desktop belongs to later deployment validation" (thêm test TST-M1-P3-015).
  - R5.1-02 (P6 Semantic Capability Validation & Negative Fields): Siết chặt bộ validator P6 trong `evidence_manifest.py` với 10 điều kiện bắt buộc (bao gồm `desktop_refresh_token_retained == False`, `desktop_vault_access == False`, `broker_owns_oauth_provisioning == True`, `encryption_method == "WINDOWS_DPAPI"`, `broker_boundary == "HTTP_IPC_SUBPROCESS_BOUNDARY"`); thêm negative test kiểm thử từng trường bị sửa sai hoặc thiếu đều khiến manifest fail-closed và chặn cấp `READY_FOR_USER_CHECKPOINT` (thêm test TST-M1-P6-010).
  - R5.1-03 (Chuẩn hóa Tài liệu Vault Schema & Kỷ luật Test-First): Chuẩn hóa tài liệu kiểm toán `audit-r5.md` phản ánh đúng schema thực tế của DPAPI vault (`version`, `encryption`, `encrypted`, `ciphertext`, `updated_at`); chứng kiến RED trước code cho cả 2 test mới và lưu log thô tại `docs/milestones/m1-proof/evidence/m1-p6/red-r5-1-stdout.txt`; toàn bộ test suite M1 đạt **93/93 passed, 0 skipped** (coverage 83%), cập nhật manifest 85 artifacts và hashes SHA-256 hợp lệ 100%.
- Hoàn tất khắc phục triệt để các phát hiện kiểm toán độc lập R5 trên GitHub HEAD `9167072` (2 BLOCKER, 1 MAJOR) và lập Báo cáo Kiểm toán Exit Gate `docs/milestones/m1-proof/audit-r5.md`:
  - R5-01 (Broker Subprocess OS Isolation): Chuyển đổi Broker server sang tiến trình Python OS riêng biệt (`subprocess.Popen`), Desktop client chỉ biết URL và giao tiếp qua REST IPC, `broker_pid != desktop_pid`, fail-closed khi broker bị kill; thực nghiệm live probe E3 thành công trên Google Drive thật qua broker subprocess (`broker_pid=49052`, `desktop_pid=20320`, resumable upload 64 bytes ID `1zLi2d...HsQD`, SHA-256 đối soát khớp 100%, dọn dẹp file test); xuất `drive_e3_evidence.json` có `process_isolated: true` (thêm test TST-M1-P3-013).
  - R5-02 (Windows DPAPI Encrypted Vault): Thay thế hoàn toàn JSON plaintext vault bằng kho mã hóa an toàn sử dụng Windows Data Protection API native (`CryptProtectData`/`CryptUnprotectData` từ `Crypt32.dll`); vault trên đĩa (`~/.cloud_token_broker/vault.json`) chỉ chứa base64 ciphertext và metadata; cam kết không có byte plaintext token nào tồn tại trên đĩa máy trạm (thêm test TST-M1-P3-014).
  - R5-03 (Fail-Closed Dynamic Compatibility Matrix): Xóa bỏ 100% logic fallback gán giá trị mặc định khi observation lỗi (`except -> 18.6`, missing binary -> `1.31.2`); khi thiếu/lỗi thì `observed = None`, `result = "FAIL"`, `overall_result = "FAIL"`; bổ sung negative tests mô phỏng lỗi DB/binary (thêm test TST-M1-P5-009).
  - R5-04 (P6 Semantic Capability Validation): Nâng cấp validator P6 kiểm tra sâu cấu trúc machine-readable (P3: `process_isolated == true`, `broker_pid != desktop_pid`, `secure_storage_verified == true`; P5: `overall_result == "PASS"`, không runtime nào FAIL/None/unknown) trước khi cấp `E3` và `READY_FOR_USER_CHECKPOINT` (thêm test TST-M1-P6-009).
  - R5-05 (Kỷ luật Test-First & Bằng chứng RED R5): Chứng kiến RED thật cho 4 tests R5 trước implementation và lưu log thô UTF-8 tại `docs/milestones/m1-proof/evidence/m1-p6/red-r5-stdout.txt`; sau correction chạy toàn bộ test suite M1 đạt **91/91 passed, 0 skipped** (coverage 85%), tái tạo manifest 84 artifacts, validate hashes 100% và secret scan 0 findings.
- Hoàn tất khắc phục toàn diện 5 vấn đề từ đợt tái kiểm toán độc lập trên GitHub HEAD commit `fdd04b5` (R4-01..R4-05) và lập Báo cáo Kiểm toán Exit Gate `docs/milestones/m1-proof/audit-r4.md`:
  - R4-01 (ADR-0009 Cloud Token Broker HTTP Process Boundary): Triển khai `CloudTokenBrokerServer` daemon HTTP TCP độc lập (`src/m1proof/broker_service.py`), vault lưu refresh token bên ngoài workspace tại `~/.cloud_token_broker/vault.json`; desktop client giao tiếp qua HTTP IPC (`POST /api/token`), credentials desktop chỉ chứa access token ngắn hạn (`refresh_token=None`); kiểm toán quét ổ đĩa desktop cam kết 0 token plaintext; thực nghiệm live probe E3 thành công trên Google Drive thật (pre-generated ID `1QR8W1...NYct`, resumable upload 64 bytes, tải về đối soát SHA-256 `a1489a57bff218ba...` khớp 100%, dọn dẹp file test); xuất tệp bằng chứng `docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json` với `status: PASS_E3_LIVE` (thêm test TST-M1-P3-012 và TST-M1-P3-LIVE).
  - R4-02 (Đồng bộ Evidence & Trace Số lượng Test Run): Cập nhật đồng bộ các tệp `commands.jsonl`, `status.md`, `hashes.sha256` của P2, P3, P5, P6; trace chính xác 100% kết quả test run hiện hành: **87/87 passed, 0 skipped** (coverage 87%).
  - R4-03 (Minh bạch Test-First & Bằng chứng RED Thực tế): Ghi nhận công khai độ lệch lịch sử `RED_EVIDENCE_MISSING_FOR_R3_REMEDIATION` trong `red-observations.md` của P3, P5, P6; chứng kiến RED thật trước implementation cho 3 bài test R4 mới (`test_tst_m1_p3_012_broker_http_process_boundary`, `test_tst_m1_p5_008_dynamic_matrix_observation`, `test_tst_m1_p6_008_capability_evidence_fail_closed`) và lưu log thô tại `docs/milestones/m1-proof/evidence/m1-p6/red-r4-stdout.txt`.
  - R4-04 (P6 Fail-Closed theo Capability Evidence): Bổ sung `m1-p6` vào mandatory packages; kiểm tra bắt buộc 3 tệp capability evidence (`temporal_server_evidence.json`, `drive_e3_evidence.json`, `compatibility_matrix.json`); hạ trạng thái nếu thiếu; đánh giá động `evidence_classification` (gán `E3` cho `m1-p3` khi probe live pass).
  - R4-05 (Dynamic Compatibility Matrix): Cập nhật `generate_compatibility_matrix()` đo đạc động runtime thực tế (CPython, uv, PostgreSQL, Temporal Server binary, Temporal SDK, FFmpeg/ffprobe), ghi nhận timestamp UTC thực thi và xuất `compatibility_matrix.json`.
  - Toàn bộ test suite M1 đạt **87 passed, 0 skipped** (P0: 10, P1: 32, P2: 10, P3: 13, P4: 6, P5: 8, P6: 8).
- Khắc phục toàn bộ các phát hiện từ kiểm toán độc lập R3 và lập Báo cáo Kiểm toán Exit Gate `docs/milestones/m1-proof/audit-r3.md`:
  - P3 (OAuth Boundary ADR-0009): Triển khai `CloudTokenBroker` và `DesktopOAuthClient` trong `src/m1proof/oauth_broker.py`, desktop client chỉ nhận access token ngắn hạn trong RAM (`refresh_token=None`), xóa vĩnh viễn tệp `token_e3_test.json`, kiểm toán đĩa cam kết 0 refresh token plaintext, phân loại lỗi HTTP 403 `insufficientPermissions` và redact bí mật (thêm 4 tests TST-M1-P3-008..011).
  - P2 (Exact Temporal Server 1.31.2): Tải và tích hợp official binary `tools/temporal/temporal-server.exe` v1.31.2 (SHA-256: `5575b369...`), khởi chạy local dev server với SQLite in-memory, kết nối gRPC port 7233, tự động đăng ký namespace, thực thi roundtrip Workflow + Activity và idempotent retry trên máy chủ thật (thêm 3 tests TST-M1-P2-008..010).
  - P5 (Strict Compatibility Matrix & Media Validation): Nâng cấp kiểm tra tương thích lên so khớp nghiêm ngặt 100% phiên bản đã khóa (Python 3.13.15, uv 0.12.13, PG 18.6, psycopg 3.3.5, Temporal Server 1.31.2, Temporal SDK 1.32.0); tạo fixture âm thanh chuẩn RIFF WAV và xác thực đa phương tiện qua `ffprobe` (container wav, codec pcm_s16le, duration > 0); xuất `compatibility_matrix.json`.
  - P6 (Dynamic Fail-Closed Evidence Manifest): Bỏ hard-code kết quả PASS; triển khai parser đọc trạng thái động từ `status.md`; kiểm tra danh sách tệp bằng chứng bắt buộc; phân loại bằng chứng E1..E3; kiểm thử tiêu cực (negative tests) phát hiện tệp thiếu, tampering, canary secret fail-closed (thêm 2 tests TST-M1-P6-006..007).
  - Test suite M1 nâng lên 83 passed, 1 skipped (coverage >91%).
- Hoàn thành M1-P6 Evidence Synthesis & Audit: xây dựng manifest tổng hợp 75 artifacts với kiểm tra băm SHA-256 tự động, thực thi gate boundary engine ngăn chặn công bố PASS non-m1 scope, quét bảo mật fail-closed (0 credential/token rò rỉ), hoàn thiện 5 bài test-first (TST-M1-P6-001..005) và lập Báo cáo Kiểm toán Exit Gate `docs/milestones/m1-proof/audit-r2.md`.
- Hoàn thành M1-P5 Compatibility Smoke: kiểm chứng tương thích thực tế tập phiên bản M1-R1 với 6 bài test-first (CPython 3.13.15, uv 0.12.13, khóa uv.lock frozen, PostgreSQL 18.6 rollback và lưu trữ UTF-8 tiếng Việt, Temporal SDK 1.32.0 handshake/replay, ranh giới client Google không leak secret khi thiếu credential, và binary FFmpeg thực tế C:\ffmpeg\bin\ffmpeg.exe probe an toàn với argument array).
- Hoàn thành M1-P4 Local Journal & Recovery Proof: kiểm chứng SQLite local journal và atomic file writer trên Windows với 6 bài test-first (crash sau artifact complete trước gửi receipt resend operation, crash giữa chừng reject partial byte, lost ACK sau cloud commit reconcile receipt không lặp side effect, stale recovery epoch quarantine, cache eviction phân biệt với unsent journal active, và phát hiện missing/corrupt hash).
- Hoàn thành M1-P3 Google Drive & OAuth G04 Proof: kiểm chứng Google Drive API v3 và OAuth 2.0 Installed App Flow với 8 bài test-first (pre-generated ID idempotency, resumable upload lost-ACK recovery, timeout classification & reconciliation routing, byte integrity & SHA-256 verification, resumable session reconciliation, OAuth lifecycle & ADR-0009 desktop boundaries, rate limit HTTP 429 bounded backoff và secret scanning trong logs/receipts).
- Thực hiện kiểm chứng thực tế Live E3 Probe trên Google Drive thật: hoàn tất OAuth authorization flow qua localhost, cấp pre-generated ID từ Drive API, resumable upload payload 64 bytes, tải về đối soát SHA-256 khớp 100% và dọn dẹp xóa file test an toàn.
- Hoàn thành M1-P2 Temporal G01 Proof: kiểm chứng Temporal Server 1.31.2 và Python SDK 1.32.0 với 7 bài test-first (worker offline/resume, idempotency lost-ACK, stale generation fencing, child failure isolation, replay versioning/patching, unknown outcome reconciliation và payload/history secret boundaries).
- M1-P1 contract proof cho idempotency, optimistic revision, outbox/consumer dedupe, fencing theo generation/recovery epoch, operation receipt/reconciliation và lọc dữ liệu nhạy cảm.
- Completion Unit of Work proof ghi nguyên tử completion ledger, batch/capacity, variant registry/reservation, `MediaUsage` qua owner port, outbox và cleanup eligibility; có fault injection tại từng ranh giới và lost-ACK recovery.
- M1-P0 environment capture/validation, frozen dependency lock, PostgreSQL 18.6 preflight và test harness với evidence RED/GREEN.
- Baseline tài liệu sản phẩm, dữ liệu, chất lượng, kiến trúc, ADR, contracts, test strategy và roadmap.
- Technical spec và implementation plan cho Phân hệ A, vẫn chưa được phép triển khai.
- M1-R1 version lock và kế hoạch Evidence Prototype từ M1-P0 đến M1-P6.
- Checklist trạng thái, audit nhiều vòng và quy tắc phân biệt proof M1 với gate toàn phần.
- Quy trình duy trì `README`, `CHANGELOG`, `HANDOFF` và sao lưu GitHub sau mỗi phiên sửa đổi hoặc checkpoint quan trọng.

### Changed

- Milestone M1 hoàn tất 100% (P0..P6 PASS, 74/74 automated tests, coverage 88%), chuyển trạng thái sang `READY_FOR_USER_CHECKPOINT`.
- M1-P6 chuyển sang `PASS_M1_SCOPE`.
- Cổng G07 chuyển sang `SMOKE_COMPATIBILITY_PASS_M1_SCOPE`.
- M1-P5 chuyển sang `PASS_M1_SCOPE`.
- M1-P4 chuyển sang `PASS_M1_SCOPE`.
- M1-P3 chuyển sang `PASS_M1_SCOPE`; Cổng G04 chuyển sang `PARTIALLY_PROVEN`.
- ROADMAP-OPEN-003 chuyển sang `CLOSED_FOR_M1_P3`.
- M1-P2 chuyển sang `PASS_M1_SCOPE`; G01 chuyển sang `PARTIALLY_PROVEN`.
- Khắc phục toàn bộ 3 BLOCKER và 5 MAJOR của audit M1 R1: aggregate race, recovery epoch, secret boundaries, live environment probe, scoped operation/activity receipts, restart evidence và completion admission.
- P0/P1 trở lại `PASS` sau remediation review; P2 chuyển `READY`, nhưng M1/G01/G04 chưa PASS.
- M1 tiếp tục `IN PROGRESS`; M1-P0 và M1-P1 đạt PASS, M1-P2 Temporal G01 là work package tiếp theo. M1 và G01/G04 chưa PASS.
- Ghi rõ Windows M1-R1 dùng backend `psycopg-binary==3.3.5` qua extra `psycopg[binary]`, cùng API/version psycopg đã khóa.
- M0 chuyển sang `APPROVED`; PCC-026 đóng và quyền code được giới hạn ở M1.
- ROADMAP-OPEN-002 chuyển `CLOSED_FOR_M1_R1`; ROADMAP-OPEN-003 chỉ chặn M1-P3.
- M1 được làm chặt về evidence order, PostgreSQL preflight, completion Unit of Work, gate scope và failure taxonomy.

### Security

- Thiết lập chính sách không commit credential, token, secret, log chưa redacted hoặc dữ liệu runtime nhạy cảm.

## Trạng thái sau khắc phục audit M1 R1

Remediation R1 có 42 test acceptance qua, migration tiến/lùi và evidence/hash mới. P0/P1 `PASS`, P2 `READY`; G01/G04 vẫn `NOT TESTED` và M2/M3/Module A vẫn `NOT AUTHORIZED`.

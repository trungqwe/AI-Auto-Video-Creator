# Báo cáo bằng chứng IMPL-PLAN-PERSIST

- Task: IMPL-PLAN-PERSIST (planning_package), trigger INITIAL, cơ sở HEAD bf52905b3b8547f82a51aa2ccc926f7b7ae1b0bc.
- Tệp tạo mới: `docs/implementation/persist/plan.md`, `docs/implementation/persist/slices.md` (chín slice PERSIST-A, PERSIST-B, PERSIST-C, PERSIST-D, PERSIST-E, PERSIST-F, PERSIST-G, PERSIST-I, PERSIST-J) và báo cáo này.
- Không sửa `src/**`, `migrations/**`, `.ai-pm/**`, `docs/milestones/**/evidence/**`, kế hoạch phân hệ A–J và kế hoạch hội tụ.

## Nguồn đã đọc

Liệt kê các tệp đã mở khi viết (đường dẫn, sha256):

1. Kế hoạch hội tụ:
- `docs/implementation/convergence/plan.md` (sha256: dc998d8cc60d7f8bd2141788f7ac83278b3d084be12912a1e5d920bffa1501d5) — mục 2, 5.2, 5.3, 11.1, 12.
- `docs/implementation/convergence/slices.md` (sha256: 0f18fbad94a959cb50668f3ff3202b79e12782fb4912c29750a644459228e322).

2. Kế hoạch phân hệ:
- `docs/implementation/a/plan.md{bt} (sha256: 9e4890e7e80ca7f4a6ba0d41a81f5e25f7470c41c519b40a09fe67b8185e4b38)
- `docs/implementation/b/plan.md{bt} (sha256: 3103b516cab627fd064df30f8af358e025bbd2617eaedbc2f64ea08e0e034bfb)
- `docs/implementation/c/plan.md{bt} (sha256: 0594e6bf6ba887bcc5f79d5a4fe13624714027faf89deb49a833dcecd0ebf197)
- `docs/implementation/d/plan.md{bt} (sha256: b03bfa87b78f4b2b6263b8776d903903c531b95852a9da5a738c234bba5eb9ac)
- `docs/implementation/e/plan.md{bt} (sha256: 5964e271759fbbe97dacca12058424066b3dc28b3f670892657c2b63a25ac2e2)
- `docs/implementation/f/plan.md{bt} (sha256: 3d4240949670472c76349d83b7702a4ef294d2daf206a6e50b07646c6e6cf3fb)
- `docs/implementation/g/plan.md{bt} (sha256: 8fc9b2c9ed4afc3b56401c337098ab38e579499710615c356f5e4d192c0abc45)
- `docs/implementation/i/plan.md{bt} (sha256: bfa2a1fa655c09c2290cddf0e1a586718665ca89b3b18af6bb538b3bd949cb79)
- `docs/implementation/j/plan.md{bt} (sha256: b196ef3869970e600bb71495a223d5db0d3356e1c456158193dc5b13bc1edbe9)

3. Migration cơ sở dữ liệu:
Hiện có tại HEAD: migration 0001 đến 0008 trong src/controlplane/infrastructure/db/migrations/:
- `src/controlplane/infrastructure/db/migrations/0001_initial_controlplane.rollback.sql` (sha256: 135be0b16b8ea9c69d081f61f50addda7610968382d4bb9a7f7589c965b86a55)
- `src/controlplane/infrastructure/db/migrations/0001_initial_controlplane.sql` (sha256: 2628eff285a53089a79780ad8f8b5469e1adece1ea60e5f87d8039760adf01c8)
- `src/controlplane/infrastructure/db/migrations/0002_idempotency_and_receipts.rollback.sql` (sha256: 13711dbf8bccbb98b64691cc45b64302773383f8481ffec8b85e1d2ef64df729)
- `src/controlplane/infrastructure/db/migrations/0002_idempotency_and_receipts.sql` (sha256: a5df738d2f6d6f56f4184be091ef80bcda2e24acb8790c5ee5e1117a0d58eb9e)
- `src/controlplane/infrastructure/db/migrations/0003_outbox_and_projections.rollback.sql` (sha256: a2dc5df5ecf8754d2adb402856dcfe2c937127267bcaecffedd4686981bc6d08)
- `src/controlplane/infrastructure/db/migrations/0003_outbox_and_projections.sql` (sha256: 7654284823a4f3e497e918ee444846d51419aef597fd6f71c5ba6ead1174b287)
- `src/controlplane/infrastructure/db/migrations/0004_config_and_secrets.rollback.sql` (sha256: 37f40f26a0e4dbdb2a757ba5c9ab3e5850c37bffe0365139bb7a8fdc65a1781d)
- `src/controlplane/infrastructure/db/migrations/0004_config_and_secrets.sql` (sha256: a6f42af0ef40b878d686900808a91b3cbab5cfecbadceceacb9864b605826f74)
- `src/controlplane/infrastructure/db/migrations/0005_artifact_metadata.rollback.sql` (sha256: a5585c00c0861c3db3d4660638f6d9d865977d713f34200ef1f362fdd9f1ef1c)
- `src/controlplane/infrastructure/db/migrations/0005_artifact_metadata.sql` (sha256: 095543c076247c3cc4a77ae610b55cc2edb8d268f04b77fb0bc2ade2e3029d2b)
- `src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.rollback.sql` (sha256: 9853fc1fd8480fbd657fef474845a9e824f6cf885d93e533086f632021eaabec)
- `src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.sql` (sha256: 4631e91e55837742db703ce0a968a345e1338bda1f5ce23a945aa9ebd6d69ad4)
- `src/controlplane/infrastructure/db/migrations/0007_technical_details.rollback.sql` (sha256: dcfc3cb75978035a2760045ea5f6d4b96e845f7298cb5099253956b24029a252)
- `src/controlplane/infrastructure/db/migrations/0007_technical_details.sql` (sha256: f4a6f404c9182fd4a481f295f89a9ce19b8c494e82a3c87670fe6f26842573fa)
- `src/controlplane/infrastructure/db/migrations/0008_operation_stream_workspace_cursor_index.rollback.sql` (sha256: 71678945f1f774c4133e95f3d63ac164a5a1c61e28c515bcd9b533ad8b060fe8)
- `src/controlplane/infrastructure/db/migrations/0008_operation_stream_workspace_cursor_index.sql` (sha256: 5321b9eb1023cc1904f4b52f2f8a5846ac5890a6e8b668c373fbeb0535ac00fb)
- Migration 0009 đến 0018: chưa có trong cây tại HEAD bf52905b3b8547f82a51aa2ccc926f7b7ae1b0bc (thuộc phạm vi gói CP-3-MIGRATIONS).

4. Infrastructure DB và Unit of Work:
- `src/controlplane/infrastructure/db/uow.py` (sha256: 21deb060c84d1d224eb8d760bf31dc64ff485790c78411819e11a8a06eaca15d)
- `src/controlplane/infrastructure/db/migration_runner.py` (sha256: 81ecaeb202ed96d237d9c103e2a9f5a9ed8b5149a67a37d054e2f6715890f8e1)
- `src/controlplane/infrastructure/db/outbox/postgres.py` (sha256: 5e784bcad5c8d8a8045ee8da7f0987b3309cab9a72a408c04aca0f63c258c893)

5. Port của từng phân hệ:
- `src/source_ingestion/ports/repositories.py` (sha256: eba1f7305eec2ece7cfa9b13af75f3d70276a10e6af1f78b0c449a7b435ff18f)
- `src/ingestion/application/ports.py` (sha256: 8d0b8ed3f0560212799e72040820b98c46fee79f1640b8757ad5badd9843bcbe)
- `src/catalog/ports/repositories.py` (sha256: 8baec60ceaff41b1f9bc838970f9dd9ce3400d9105c0cf79d78ce6c339b0781f)
- `src/catalog/ports/usage.py` (sha256: 6fce4ef84fd50eede01066db3950459c595916f2ffe83138ad8500cab1151211)
- `src/catalog/application/hooks.py` (sha256: 57228379b4ea2cd711d06358b2a7f0390027e592df7d5db45415dec07e42e5ab)
- `src/creative/ports/repositories.py` (sha256: f47030d13595f31794df49d1838a9dbdb550c031372ca7cf82f9fa40fb66fd13)
- `src/voice/ports/repositories.py` (sha256: 937461a6b06eba238c107dae79fffb68bbf8c864e717034315edaad161e3885a)
- `src/render/ports/repositories.py` (sha256: 783535e8ce2a257781ff80192980918419b074e0f71bf6ea0fac842737a31172)
- `src/controlplane/application/orchestration/grant_issuance.py` (sha256: 79ebc3700a0b07c3a192f8b108a80a4faed6b187a848ca52e34ad0642a998e9e)
- `src/controlplane/application/orchestration/job_allocation.py` (sha256: b9a8fc6b1e698fa238e7d86d893ae841fd3204f61a685c27fed0482b1d074bf8)
- `src/controlplane/application/orchestration/variant_reservation_flow.py` (sha256: bb54f2b9aecc9523ac18d1c7c6f9c5a3ca1c3a6f685c8d294e5024bbd6674da9)
- `src/controlplane/application/orchestration/start_batch.py` (sha256: 3cc4095baf760aa64d164b0d1ca125f6dacba464341cb15fd2404bf178ad129c)
- `src/controlplane/application/storage_meta/__init__.py` (sha256: 34b0072b61ea5d0bd4823a0c1b771417e2155c6ac392d9b1208f8e1d15ebdd11)
- `src/controlplane/application/storage_meta/cloud_persist.py` (sha256: 3f034ee9952450e8f2138c03b0508319ea071900a798f04aa1ea216e121f1289)
- `src/controlplane/application/storage_meta/declare_version.py` (sha256: 2d0917b07c82c2ea377b6910cfff0a29f3cbf210ee4955ccf1a7d6036dfc2fdd)
- `src/controlplane/application/config_security/__init__.py` (sha256: e39555326cbe0ac531b309c5039219ffeca0d6d8edb177fc74b83a303335ece0)
- `src/controlplane/application/config_security/capacity_reservation.py` (sha256: aeae85ff085285403481cdf3bb6dcfd1ba73c777ef66c19df7b395a3bf5bb1e4)
- `src/controlplane/application/config_security/routed_invocation.py` (sha256: 9d23dd373b900eed6c45104a69bb4fcf3707ed5b5f0f3944d38bb4d7c8bf571b)
- `src/controlplane/application/config_security/account_test.py` (sha256: 58734160148bba1314b289a33de86f96962a59357c4b991acc0edcfc8fe56162)
- `src/controlplane/application/config_security/bundle_resolution.py` (sha256: e2cf62759ee13c45980ed4b5c461bc70013caa879787610fc81ad5045ba0af1b)
- `src/controlplane/domain/config_security/audit_record.py` (sha256: db014d216a6ca95be7657e729be633185a98181a14791a3da56f9fb77a03b460)

6. Binding và cấu hình phân vùng:
- `docs/parallel-delivery/bindings/a-b-collected-document.json` (sha256: 6efd26d65271c94eb4e94e425e789fde2200b8977624e0c7fe9f93a9f6cb76b0)
- `docs/parallel-delivery/bindings/domain-event-envelope.json` (sha256: 533833be42f6124b90afe2e460971a476783054374f21d4a28cd12cd53a80f53)
- `docs/parallel-delivery/bindings/b-d-production-snapshot.json` (sha256: 51e327ef38053af54019527ed6b39418f8e99e951cf6df9e7eb26f50b698238a)
- `docs/parallel-delivery/bindings/c-d-media-candidates.json` (sha256: 7088ce4b50a31c0aff5c3184170f45df11bf8b6eef077d2109163ffaf66dad43)
- `docs/parallel-delivery/bindings/g-c-i-completion.json` (sha256: 22306b2aa503c0eea4fe896bba52c1d4ab844249dc9ffff728593d262ea74b28)
- `docs/parallel-delivery/bindings/d-e-f-voice-timing.json` (sha256: 6ee1a42e694497ea152a6205d50d7257798f69564f076ec38b450e6a609b1cd4)
- `docs/parallel-delivery/bindings/i-artifact-version.json` (sha256: aaa88fc12616315c2c6f08d740dc008aef44553b3e5b999b050d3250de1a756e)
- `docs/parallel-delivery/bindings/f-render-package.json` (sha256: 80124be897909c663c89880e2d9550ebce69f14b6781a147035bfe6930a828ed)
- `docs/parallel-delivery/bindings/g-activity-execution.json` (sha256: 67df5b8cccaacd01abfb6ad87ad6cde7e6403890187785709420959f9aab912b)
- `docs/parallel-delivery/bindings/j-provider-route.json` (sha256: 8a00dc30f2876135dfb64272fc9172f17796bf4a08273ba31c3c71a5615488a4)
- `docs/parallel-delivery/ownership-and-locks.yaml` (sha256: 20088c6e00d65f711d92c3e93953825834695e907e9282c07e67017a3b29756b)

7. Quyết định D8: Các quyết định mở D8 (OI-PERSIST-01 đến OI-PERSIST-07) như trong plan.md mục 7.

## Phát hiện về cơ sở

- Migration `0009`..`0018` chưa có trong cây tại HEAD; tên bảng và cột của chúng trong kế hoạch là GIẢ ĐỊNH theo convergence mục 5.2 (OI-PERSIST-01); mỗi slice đối chiếu bằng `information_schema` hoặc BLOCKED với DEPENDENCY_GAP.
- `ownership-and-locks.yaml` chưa phủ `src/controlplane/infrastructure/db/config_security/**`, `tests/integration/persistence/**`, `docs/delivery-evidence/persist-*/**` (OI-PERSIST-02).
- `SqlUnitOfWork` commit khi thoát bình thường nên UoW của A–F phải tự rollback khi chưa `commit()`; outbox `0003` có `recovery_epoch BIGINT` (OI-PERSIST-03).

## Lệnh kiểm

| Lệnh | Exit code | Kết quả |
| --- | --- | --- |
| Bước 1 (RED trước khi viết): lệnh kiểm bắt buộc của task | 1 | FileNotFoundError: [Errno 2] No such file or directory: `docs/implementation/persist/plan.md` |
| Bước 23 (lệnh kiểm bắt buộc): lệnh kiểm bắt buộc của task | 0 | PASS (Exit code 0, không output) |
| Bước 24 (probe cấu trúc slices.md): probe cấu trúc và phong bì | 0 | PASS (Exit code 0, không output) |
| Bước 25 (probe nội dung plan.md): probe các biểu tượng D1 và nội dung | 0 | PASS (Exit code 0, không output) |
| Bước 26 (kiểm tra định dạng git): git diff --check | 0 | PASS (Exit code 0, không output) |

- **Interpreter đã dùng**: `Python 3.13.12` (`C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe`).
- **Độ dài các khối slice trong `slices.md`**:
  - `PERSIST-A`: 2573 ký tự (giới hạn <= 5000)
  - `PERSIST-B`: 2506 ký tự (giới hạn <= 5000)
  - `PERSIST-C`: 2454 ký tự (giới hạn <= 5000)
  - `PERSIST-D`: 2523 ký tự (giới hạn <= 5000)
  - `PERSIST-E`: 2243 ký tự (giới hạn <= 5000)
  - `PERSIST-F`: 2437 ký tự (giới hạn <= 5000)
  - `PERSIST-G`: 2511 ký tự (giới hạn <= 5000)
  - `PERSIST-I`: 2480 ký tự (giới hạn <= 5000)
  - `PERSIST-J`: 2726 ký tự (giới hạn <= 5000)
  - **Tổng độ dài chín khối**: 22453 ký tự (giới hạn <= 38000; tổng gói biên dịch dưới 60000).

## Mục mở

- **OI-PERSIST-01**: Tên bảng và cột của `0009`..`0018` chưa có trong cây — Mặc định: Dùng tên ở convergence mục 5.2; test đối chiếu `information_schema`; thiếu thì `BLOCKED` (`DEPENDENCY_GAP`, owner `CP-3-MIGRATIONS`).
- **OI-PERSIST-02**: `ownership-and-locks.yaml` chưa phủ `src/controlplane/infrastructure/db/config_security/**` (khóa J), `tests/integration/persistence/**` và `docs/delivery-evidence/persist-*/**` — Mặc định: Control mở rộng phong bì khi biên dịch kèm khóa của phân hệ; không sửa registry trong gói này.
- **OI-PERSIST-03**: Outbox `0003` có `recovery_epoch BIGINT`, event A–F mang chuỗi — Mặc định: Ghi số khi chuỗi toàn chữ số, ngược lại `NULL`.
- **OI-PERSIST-04**: `HookHistory` là lớp cụ thể, chưa có Protocol — Mặc định: Adapter cùng phương thức `get(hook_id, revision)` và `append(HookRevision)`; không thay thế được thì BLOCKED, không sửa `src/catalog/application`.
- **OI-PERSIST-05**: pgvector (ADR-0002) — Mặc định: Hoãn; C dùng FTS (D8-CV-02).
- **OI-PERSIST-06**: Nơi lưu secret (PUC-J-07) — Mặc định: Broker DPAPI-file (J-17); PostgreSQL chỉ lưu metadata handle.
- **OI-PERSIST-07**: Cạnh state machine PUC-J-03 và YC-HT-I-04 (user duyệt 20/10/2026); PUC-G-02 giữ nguyên — Mặc định: Adapter chỉ lưu trạng thái hiện có, không mã hóa cạnh mới.

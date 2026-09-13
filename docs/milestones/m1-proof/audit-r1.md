# Kiểm toán M1 R1

Ngày: 13-09-2026. Kết luận: **REQUEST CHANGES**. Có **3 BLOCKER và 5 MAJOR**.

Phạm vi: P0/P1 trong working tree, bao gồm thay đổi đã stage nhưng chưa commit tại thời điểm bắt đầu audit. HEAD đầu audit: `9d88c8f`. P2–P6 chưa thực hiện; không kết luận các gate tương ứng đã thất bại. Đây là kiểm toán contract/code/evidence, không phải chứng nhận production hoặc rà soát CVE đầy đủ.

## Bằng chứng thực thi

- Chạy `py -3.13 -m uv run --frozen pytest tests/m1 -q`: **25 passed in 1.58s**, exit 0.
- Chạy `py -3.13 -m uv lock --check`: resolve 45 package, exit 0.
- Secret pattern scan trên source/tests/schema/evidence không tìm thấy các mẫu credential đã quét; không thay kiểm chứng secret boundary trong B03.
- `git diff --check` phần audit đạt; staged diff có cảnh báo whitespace từ CRLF/traceback và Markdown trong evidence cũ, cùng dòng trắng cuối test_outbox_delivery.py. Giữ nguyên byte evidence, không ghi đây là validation sạch toàn bộ.
- Các phát hiện dưới đây dựa trên đọc code và đối chiếu contract; chưa bổ sung hoặc chạy reproducer riêng cho từng lỗi. Không gọi suy luận interleaving là race đã tái hiện thực nghiệm.
- 94% coverage lịch sử P1 là độ bao phủ câu lệnh, không chứng minh đủ nhánh lỗi hoặc bất biến.

## BLOCKER

### M1-AUD-B01 — Lost update khi đồng thời tạo aggregate chưa tồn tại

**Vị trí:** `src/m1proof/contracts.py:296`, `:315`, `:337`; `tests/m1/p1/test_command_semantics.py:69`.

Hai command khác idempotency key cùng aggregate mới và expected revision 0 khóa hai advisory key khác nhau. Cả hai có thể đọc không có row; `FOR UPDATE` không khóa row chưa tồn tại. Câu `ON CONFLICT DO UPDATE` sau đó cho command thứ hai ghi đè payload với revision vẫn là 1. Cả hai có thể có receipt/outbox accepted dù chỉ một đầu vào còn trong aggregate. Test đồng thời hiện tại chỉ gửi cùng key, nên không bắt tình huống này.

**Vi phạm:** expected revision/common contract và failure injection hai transaction cùng revision ở P1.

**Sửa tối thiểu:** serialize theo workspace/aggregate trước đọc revision, hoặc dùng conditional write/CAS có xử lý conflict. Thêm test barrier ép cả hai transaction tranh cùng aggregate mới: chỉ một accepted, bên kia revision conflict, một mutation/outbox được chấp nhận.

### M1-AUD-B02 — Recovery epoch chưa được giữ xuyên command/event

**Vị trí:** `src/m1proof/contracts.py:75`, `:186`, `:272`, `:415`, `:482`.

MutationCommand có epoch nhưng execute_mutation chỉ lưu, không đối chiếu epoch hiện hành. DomainEvent không có epoch; dispatcher loại bỏ epoch đã có trong outbox, consumer không thể từ chối event trước restore. set_execution_fence còn có thể ghi đè generation/epoch về giá trị cũ mà không có CAS hay kiểm tra tăng đơn điệu.

**Vi phạm:** INV-016 và common contract mục 14; P1 tuyên bố giữ recovery fencing nhưng chỉ test hai ActivityCommit bị stale.

**Sửa tối thiểu:** một nguồn epoch có thẩm quyền theo workspace; truyền epoch qua event và kiểm tra trước mutation/dispatch/consumer commit; bảo vệ cập nhật fence. Test delayed command/event và hạ generation sau đổi epoch. Không cần đổi topology.

### M1-AUD-B03 — Secret boundary chỉ bảo vệ một số entry point

**Vị trí:** `src/m1proof/contracts.py:415`, `:511`, `:630`; test sensitive input ở `tests/m1/p1/test_recovery_semantics.py`.

consume_event ghi payload trực tiếp, commit_activity_result ghi payload trực tiếp sau fence, reconcile_external_operation ghi output_refs trực tiếp. Các đường này không gọi bộ kiểm tra sensitive key. Payload như dictionary có key `access_token` có thể được lưu vào DB dù execute_mutation từ chối cùng dạng dữ liệu. Test duy nhất kiểm tra execute_mutation và ba bảng của đường đó; không chứng minh boundary toàn P1. Bộ lọc tên key cũng không thay allowlist cho adapter error text.

**Vi phạm:** INV-012, TST-M1-P1-008 và failure injection canary từ adapter.

**Sửa tối thiểu:** allowlist/schema cho payload/ref và lỗi ở mọi persistence boundary; test canary trên từng đường, DB export và log/error; không echo canary trong evidence. Không cần secret framework mới.

## MAJOR

### M1-AUD-M01 — P0 capture không thực hiện probe và không kiểm artifact hiện tại

**Vị trí:** `src/m1proof/environment.py:66`, `:90`; `tests/m1/p0/test_environment_manifest.py:30`.

capture_environment sao chép các section của bootstrap. Validator đối chiếu hai JSON với nhau, không băm uv.lock/pyproject/executable hiện tại, không kết nối PostgreSQL. Hai file cùng ghi preflight thành công vẫn qua test khi môi trường thật đã đổi. Các probe thủ công lịch sử có giá trị, nhưng không đáp ứng yêu cầu probe tự động TST-M1-P0-002 trong plan mục 5.

**Sửa tối thiểu:** giữ bootstrap làm expected input, thu observed runtime/hash và PostgreSQL connect/rollback/UTF-8 thật; test sai lockfile thực, endpoint sai và probe thất bại. Evidence mới có run ID; không sửa bootstrap cũ.

### M1-AUD-M02 — Operation receipt thiếu scope và transition guard

**Vị trí:** `src/m1proof/contracts.py:545`, `:603`, `:931`; `sql/m1/p1_schema.sql:76`.

Operation key là PK toàn cục; lookup chỉ dùng key và fingerprint chỉ chứa input_payload. Cùng key/payload từ workspace khác hoặc operation_type khác có thể nhận receipt cũ. Mutation state cũng chỉ nhận key: mark_operation_started có thể đưa succeeded hoặc outcome_unknown về started, vượt đường reconcile đã định nghĩa.

**Sửa tối thiểu:** scope identity/lookup theo workspace; fingerprint bao gồm operation type và input logic; kiểm epoch/grant riêng; conditional state transitions và terminal immutability. Test khác workspace/type, unknown→started và succeeded→started bị từ chối.

### M1-AUD-M03 — Activity result không giữ idempotency theo operation

**Vị trí:** `src/m1proof/contracts.py:85`, `:511`, `:532`; CT-WF-004/005/006.

ActivityCommit không gắn input fingerprint/operation identity đầy đủ. `ON CONFLICT(result_id) DO NOTHING` nuốt input khác cùng ID mà không báo conflict; đổi result_id với cùng grant lại cho lưu thêm result. Fence đúng chưa đủ chứng minh đúng một logical result hay đúng đầu vào đã cấp quyền.

**Sửa tối thiểu:** ràng buộc operation/input với grant và receipt; duplicate cùng input trả receipt cũ, khác input phải conflict. Test hai result ID cùng operation và một result ID với hai payload.

### M1-AUD-M04 — Evidence chưa đủ để tái lập kết luận PASS

**Vị trí:** `evidence/m1-p1/commands.jsonl:1`, `evidence/m1-p1/status.md`, `tests/m1/p1/test_recovery_semantics.py`, plan mục 4/6.

commands.jsonl chỉ có final regression, không có command/start/end/exit cho các RED/GREEN tương ứng. Đổi service object trong cùng process chưa chứng minh process restart; chạy lại cả suite có reset DB cũng không kiểm receipt qua restart với dữ liệu giữ nguyên. Test concurrency thiếu barrier nên có thể chạy tuần tự. Crash exceptions có giá trị rollback nhưng chưa là bằng chứng kill/restart thực tế. Thiếu snapshot từng boundary như plan yêu cầu. Schema/API absent RED có thể được plan chấp nhận, nhưng không chứng minh từng negative guard đã RED trước implementation.

**Sửa tối thiểu:** bổ sung acceptance runs có orchestration/barrier/process control và retained DB; ghi đủ commands/exit/timeline/snapshot. Không dựng ngược timestamp hoặc gán evidence mới cho run cũ. Ghi rõ phần lịch sử không thể phục hồi và đánh giá test-first riêng từng hành vi.

### M1-AUD-M05 — Completion proof chấp nhận refs chưa được kiểm chứng

**Vị trí:** `src/m1proof/contracts.py:128`, `:644`; `tests/m1/p1/test_completion_uow.py`; CT-ORC-008 bước 2.

Completion kiểm fence, registry và reservation hash, nhưng quality_report_ref/cloud_location_ref/script/plan chỉ là chuỗi được lưu. Không có owner validation hay fixture evidence lookup để chứng minh QC/sync/revisions gắn exact output. Chuỗi ref giả vẫn dẫn tới ledger/count/cleanup eligibility. Atomicity đã được kiểm tra, nhưng không thể dùng nó làm proof đầy đủ của admission vào completion. P1 cho phép owner port giả lập, nên không cần Drive hay pipeline thật để giữ điều kiện này.

**Sửa tối thiểu:** thêm proof owner validation port/fixture store có binding workspace/revision/hash; test QC fail, sync unverified, wrong output hash/revision không ghi bất kỳ thành phần completion nào. Ghi rõ boundary proof chưa kiểm external truth.

## Điểm đã làm đúng và giới hạn

- Dependency trực tiếp được pin và lock resolve được; không thấy framework sản phẩm ngoài phạm vi M1.
- Completion gọi MediaUsage owner port dùng chung connection; các test crash hiện có chứng minh rollback của transaction trong phạm vi fixture.
- Outbox checkpoint sau callback và consumer dedupe đã có test giao lại.
- G01/G04 vẫn NOT TESTED; chưa có dấu hiệu nâng mock thành external PASS.
- Chưa chạy vulnerability database scan, kiểm Temporal/Drive/FFmpeg hoặc đo throughput. Không có kết luận an toàn/tương thích cho các phần này.

## Gate và bước tiếp tục

P0/P1 hiện hành: **CORRECTION_REQUIRED**. P2: **NOT_STARTED**, bị chặn bởi dependency P0/P1 chưa được chấp nhận sau audit. M1: **IN PROGRESS — CORRECTION_REQUIRED**. Không mở M2/M3/Module A.

Không sửa code trong lượt audit. Giữ nguyên evidence lịch sử; báo cáo này phủ định kết luận PASS hiện hành, không phủ định các lần test đã chạy. Khắc phục bằng RED/GREEN đúng oracle trong P0/P1 rồi re-audit. Chưa có bằng chứng buộc redesign hoặc mở lại ADR kiến trúc.

## Hậu kiểm sau khắc phục

Ngày hậu kiểm: 13-09-2026. Evidence: `evidence/m1-remediation-r1/`.

| Issue | Đánh giá lại | Thay đổi tối thiểu | Kết quả |
|---|---|---|---|
| M1-AUD-B01 | Hợp lý | Advisory lock theo workspace/aggregate và barrier race test | CLOSED |
| M1-AUD-B02 | Hợp lý | Workspace epoch authority, truyền epoch qua event và chặn fence hạ ngược | CLOSED |
| M1-AUD-B03 | Hợp lý | Allowlist + recursive secret scan tại mọi persistence boundary P1 | CLOSED |
| M1-AUD-M01 | Hợp lý | Capture/validator đo live runtime, file hash và PostgreSQL probe | CLOSED |
| M1-AUD-M02 | Hợp lý | Receipt v2 scope workspace, fingerprint operation type/input, guarded transition | CLOSED |
| M1-AUD-M03 | Hợp lý | Bind grant/result với operation/input và receipt idempotent | CLOSED |
| M1-AUD-M04 | Hợp lý | Barrier deterministic, process restart giữ DB, command/timestamp/hash mới | CLOSED_WITH_LIMITATION |
| M1-AUD-M05 | Hợp lý | Owner admission bind exact refs/hash/revision, QC và cloud verification | CLOSED |

Giới hạn M04: stdout/timestamp RED đã không được lưu trước remediation không được dựng ngược. `red-observations.md` ghi riêng mức bằng chứng thật; kết luận đóng dựa trên acceptance mới có process restart/barrier và không thay đổi evidence lịch sử.

Hậu kiểm chạy `42 passed`, migration `up/down/up` qua, lock 45 package khớp, compile/diff check qua và credential-pattern scan không có match. Không phát hiện lý do mở lại ADR. P0/P1 trở lại `PASS`; P2 `READY`. G01/G04 vẫn `NOT TESTED`; M1 chưa PASS; M2/M3/Module A vẫn `NOT AUTHORIZED`.

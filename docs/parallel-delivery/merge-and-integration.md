# Branch, worktree, merge queue và integration gate

> **Trạng thái:** `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`

## 1. Branch và worktree

- Mỗi task hoặc delivery unit có một worktree cô lập và task-scoped branch.
- Branch bắt đầu từ exact `base_sha` do Control pin, không từ tên nhánh trôi.
- Execution envelope ghi remote/target nhưng push và PR là authority riêng; quyền commit không suy ra quyền publish.
- Trước mutation phải ghi `git status`, owned paths và protected pre-existing dirty paths.
- Không dùng stash, reset, clean hoặc checkout để che/nuốt thay đổi của task khác.
- Không stage ngoài allowlist. Nếu path cần sửa có dirty baseline được bảo vệ, dừng và re-plan ownership.
- Một commit implementation cho mỗi task; remediation là commit riêng. Commit dùng Conventional Commits và attribution bắt buộc của repository.

## 2. Candidate identity

Candidate được nhận diện bởi:

```text
repository + base_sha + ordered_task_commits + tree_sha + evidence_manifest_hash
```

Review và gate phải ghi exact identity. Rebase, conflict resolution, generated-file refresh, docs reconciliation hoặc bất kỳ mutation nào sau review tạo candidate mới và làm verdict cũ hết hiệu lực trong phần bị ảnh hưởng.

### Quy tắc kiểm tra Scope (Committed Diff + Dirty Overlay)

1. **Pin approved base/candidate**: Scope check không chỉ đọc working tree hiện tại mà bắt buộc so sánh exact committed diff giữa approved `base_sha` và candidate commit SHA (`git diff --name-status -z base_sha candidate_sha`), kết hợp với lớp phủ dirty / untracked (`git status --porcelain=v1 -z --untracked-files=all`).
2. **Kiểm tra rename hai đầu**: Với mọi thao tác đổi tên (rename) hoặc sao chép, cả đường dẫn nguồn (`old_path`) lẫn đường dẫn đích (`new_path`) đều phải được kiểm tra độc lập. Nếu một trong hai đầu thuộc đường dẫn cấm (`src/`, `tests/`, `.sql`, v.v.) hoặc nằm ngoài scope cho phép, gate FAIL ngay lập tức.
3. **Bảo toàn hash evidence bất biến**: Mọi tệp trong `docs/milestones/**/evidence/**` là bất biến (`immutable`). Hash SHA-256 của các tệp evidence lịch sử được đối chiếu với baseline; bất kỳ thay đổi nào đều bị từ chối fail-closed.
4. **Forbidden committed delta fixture**: Bất kỳ commit delta nào chứa thay đổi ngoài scope docs/config (kể cả khi working tree hiện tại sạch) đều bị từ chối.

## 3. Merge queue tuần tự

Song song kết thúc ở candidate task; tích hợp shared state luôn tuần tự.

Queue item gồm:

- task/delivery ID;
- approved candidate SHA;
- expected base SHA;
- merge priority và ready sequence;
- review disposition/ref;
- required integration gates;
- contract/migration/lock impact;
- rollback command/ref;
- publication authority.

Thứ tự ổn định:

1. dependency trước consumer;
2. contract/schema producer trước dependent code;
3. migration trước code cần migration nhưng chỉ trong cùng approved delivery;
4. priority thấp hơn trước;
5. ready sequence trước;
6. task ID từ điển làm tie-break.

Queue xử lý một item tại một thời điểm. Không autosquash lịch sử accepted, không force-push và không merge tự động nếu human gate chưa mở.

## 4. Thuật toán tích hợp

1. Pin current integration HEAD.
2. Kiểm tra item vẫn có authority và dependency accepted.
3. Kiểm tra candidate/review/evidence identity.
4. Xác nhận không có concurrent integration lease.
5. Apply candidate theo policy đã duyệt.
6. Nếu conflict: không tự chọn semantic winner; chuyển `needs_replan` hoặc yêu cầu owner giải quyết trong task mới.
7. Chạy scope/path/secret/static gates.
8. Chạy contract/migration/focused/regression gates bị ảnh hưởng.
9. Tái tạo evidence integration với provenance và hash DAG.
10. Chạy integration review trên exact HEAD nếu delivery là Architectural.
11. Chỉ sau tất cả gate mới đổi `integrated`.
12. Publish/merge remote chỉ khi human authority cho phép.

Nếu bước 7–10 fail, giữ candidate và evidence, rollback integration attempt theo strategy; không sửa nóng trực tiếp trong queue.

## 5. Gate theo thứ tự

| Thứ tự | Gate | Điều kiện |
|---:|---|---|
| 1 | Authority | Checklist/plan cấp quyền đúng scope; locked/future task bị loại |
| 2 | Candidate | SHA/tree/base/review/evidence khớp |
| 3 | Scope | Changed path nằm trong allowlist, không chạm forbidden/accepted evidence |
| 4 | Encoding/schema | UTF-8 không BOM; YAML/JSON/schema/links/IDs/DAG hợp lệ |
| 5 | Security | Secret scan, path/traversal/SSRF/trust-boundary checks phù hợp |
| 6 | Contract | Producer/consumer compatibility và exact frozen revision |
| 7 | Migration | Forward/rollback, ownership, sequence, disposable DB và cleanup |
| 8 | Focused test | Acceptance instruments và counterexamples của task |
| 9 | Regression | Suite ảnh hưởng, không skip hard gate |
| 10 | Recovery | Crash/retry/reconcile/fencing/rollback phù hợp |
| 11 | Performance/cost | Chỉ khi task claim threshold hoặc thay critical path |
| 12 | Evidence | `status.json` authority, provenance, hashes, tamper-negative |
| 13 | Independent review | `ACCEPT` trên exact candidate |
| 14 | Human release | Merge/publish quyết định bởi user/Control có authority |

Không dùng mock để đóng Drive/OAuth/Temporal/AI/render/restore/performance gate. Gate không chạy là `NOT_PROVEN`, không phải PASS có điều kiện.

## 6. Contract và migration trong queue

- Contract/state-machine revision chỉ có một writer và được merge/freeze trước consumer.
- Breaking change cần major version, compatibility window, dual-read/write hoặc migration plan và explicit consumer rollout.
- Migration sequence dùng global exclusive lock. Hai task có migration không cùng wave dù file khác nhau nếu cùng ledger/schema dependency.
- Rollback không được xóa accepted history hoặc business fact đã commit; forward-fix cần authority riêng.
- Toolchain/lockfile là một package-universe lock; không merge hai dependency mutations độc lập mà không re-resolve/review exact graph.

## 7. Evidence và accepted history

- Mỗi task ghi evidence vào path riêng có single writer.
- Integration evidence không sửa task evidence; nó tham chiếu source SHA và hash.
- `status.json` là machine authority; markdown là derivative.
- SHA-256 manifest là DAG acyclic và loại chính file hash khỏi input hash.
- Accepted và rejected historical runs đều immutable; rejected run không bị xóa để làm lịch sử đẹp hơn.
- Evidence thiếu provenance, runtime pin, command/result hoặc tamper check không được dùng đóng gate.

## 8. Rollback

Rollback ưu tiên Git revert của commit task/integration, sau đó chạy gate ảnh hưởng. Bản sao thiết kế trước thí nghiệm:

`D:/AI_SETUP/backups/AI-Auto-Video-Creator/20260928-175542`

Chỉ dùng backup sau khi xác minh nó đúng repository/time/scope, không chứa secret và không ghi đè accepted evidence. Restore docs/config không chứng minh G05 sản phẩm.

## 9. STOP conditions

Dừng queue khi:

- candidate identity lệch;
- authority bị khóa/rút;
- conflict cần semantic decision;
- accepted evidence/path ngoài scope bị thay;
- contract compatibility không chứng minh được;
- migration rollback/cleanup fail;
- secret hoặc unredacted log xuất hiện;
- gate runtime bắt buộc unavailable;
- external outcome unknown;
- review không ACCEPT.

Không bỏ item lỗi rồi tích hợp descendant phụ thuộc.

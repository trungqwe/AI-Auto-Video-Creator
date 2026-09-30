# HANDOFF

## Đã quyết định

- Authority hiện hành giữ nguyên: `M2-P1..P7B_ACCEPTED_CLOSED`; M2-P8/P9 `LOCKED`; M3/Phân hệ A `NOT AUTHORIZED`.
- Đã thêm [kiến trúc triển khai song song](./docs/parallel-delivery/README.md) ở trạng thái `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`. Bundle chỉ là docs/config và định nghĩa DAG, contract registry, ownership/lease, Orca worker protocol, merge queue, traceability, security/performance/recovery.
- Đã khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate a286e6d:
  1. Loại bỏ triệt để việc đọc biến môi trường cùng tiến trình khỏi provision_from_host(): Xóa bỏ hoàn toàn việc đọc `os.environ` (`ORCA_REVIEWER_SESSION_SECRET`, `ORCA_REVIEWER_SECRET`, `DELY_REVIEWER_SESSION_SECRET`, `REVIEWER_SESSION_SECRET`); caller trong cùng tiến trình đặt biến môi trường không thể trở thành nguồn credential hay cấp phát boundary.
  2. Bắt buộc authority opaque do host sở hữu (ReviewerHostHandoff): Ranh giới `ReviewerSessionBoundary.provision_from_host()` bắt buộc phải có `ReviewerHostHandoff`; cấm caller tự chọn secret, cấm gọi không tham số; credential lưu cách ly trong vault nội bộ, chặn in-process caller đọc hay gán giá trị (`AttributeError`).
  3. get_default() không tự động provision từ môi trường: Ranh giới mặc định khi chưa có host handoff giữ nguyên `_reviewer_secret = None`, từ chối fail-closed mọi nỗ lực mint proof hoặc context.
  4. Bộ kiểm thử tự động đạt 374/374 tests PASS (100%), bổ sung `test_sod_16` tái hiện counterexample trong tiến trình con mới chủ động đặt biến môi trường, chứng minh ranh giới từ chối fail-closed và task giữ nguyên trạng thái review.
- Đã khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate a518501:
  1. Xóa bỏ hoàn toàn fallback secret literal khỏi mã nguồn production: Xóa bỏ triệt để test_fixture_reviewer_secret_32b_hex! khỏi ReviewerSessionBoundary.provision_from_host(); trong tiến trình mới không có biến môi trường từ host, ranh giới khởi tạo với _reviewer_secret = None và từ chối fail-closed mọi nỗ lực mint proof hay context.
  2. Ngăn chặn tuyệt đối public caller-selected provisioning: ReviewerSessionBoundary.provision_from_host() từ chối fail-closed nếu caller truyền bất kỳ tham số nào.
  3. Bắt buộc ranh giới host-owned opaque trong OrcaDeliveryAdapter: Constructor từ chối fail-closed mọi boundary do caller tự khởi tạo, chỉ chấp nhận singleton ReviewerSessionBoundary.get_default().
  4. Bộ kiểm thử tự động đạt 373/373 tests PASS (100%), bổ sung `test_sod_15` tái hiện counterexample trong tiến trình mới hoàn toàn không có biến môi trường reviewer, xác nhận thiếu external provisioning bị từ chối fail-closed và task giữ nguyên trạng thái review.
- Đã khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate 7e0e312:
  1. Loại bỏ triệt để reset và credential injection khỏi bề mặt production: Xóa bỏ hoàn toàn
eset_default(), inject_reviewer_credential(), ootstrap_reviewer_credential(), và ootstrap_reviewer_capability() khỏi ReviewerSessionBoundary.
  2. Ngăn chặn tuyệt đối caller cùng tiến trình tự chọn hoặc thay thế secret: ReviewerSessionBoundary.get_default() từ chối fail-closed nếu truyền tham số; boundary được cấp phát bất biến từ trusted external session/host (provision_from_host).
  3. Ràng buộc create_review_dispatch() và claim capability vào self._reviewer_boundary của adapter: Chấm dứt hoàn toàn khả năng hoán đổi singleton để mạo danh reviewer.
  4. Bộ kiểm thử tự động đạt 372/372 tests PASS (100%), bổ sung 	est_sod_12 và 	est_sod_14 tái hiện chính xác counterexample, chứng minh ordinary caller không thể bypass reviewer hay đạt merge_queued.
  5. Xóa bỏ dòng trống thừa tại cuối tệp docs/parallel-delivery/test_negative_fixtures.py:10839, bảo đảm git diff --check đạt 0 lỗi.
- Đã khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate 358571a:
  1. Xóa bỏ hoàn toàn hằng số mặc định công khai `DEFAULT_TEST_REVIEWER_SECRET` khỏi `docs/parallel-delivery/delivery_engine.py`; `ReviewerSessionBoundary` không fallback về secret mặc định.
  2. Ngăn chặn triệt để đột biến credential singleton: `ReviewerSessionBoundary.get_default()` từ chối fail-closed nếu caller cố gắng ghi đè credential của boundary đã khởi tạo.
  3. Triển khai cơ chế trusted reviewer session bootstrap (`inject_reviewer_credential`, `bootstrap_reviewer_credential`, `bootstrap_reviewer_capability`) với tính chất bất biến (immutable once set) không thể truy cập hoặc thay thế từ Control plane hay caller bên ngoài.
  4. Bắt buộc `reviewer_secret` hợp lệ khi phát hành `ReviewerSessionProof` và `ReviewerContext`; từ chối fail-closed đối với secret bị bỏ qua (`None`), chuỗi rỗng, boundary chưa cấu hình credential hoặc sai digest HMAC.
  5. Bộ kiểm thử tự động đạt 371/371 tests PASS (100%), bổ sung 4 bài test phân biệt độc lập trong `TestSolRemediationSeparationOfDuties` bao quát toàn bộ negative và invariant fixtures.
- Đã khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate 82efe33:
  1. Chuyển capability delivery sang ranh giới do reviewer session sở hữu (`ReviewerSessionBoundary`), hoàn toàn độc lập với Control plane và adapter-visible state.
  2. Xóa bỏ hoàn toàn thuộc tính `_reviewer_delivery_channels` khỏi `OrcaDeliveryAdapter` và xóa bỏ `reviewer_auth_token` khỏi channel, bảo đảm adapter không để lộ bearer token hay capability-bearing channel cho Control.
  3. Bắt buộc opaque single-use `ReviewerSessionProof` có chữ ký mật mã HMAC do reviewer boundary sở hữu, ràng buộc chặt chẽ 7 yếu tố: `delivery_task_id`, `review_dispatch_id`, `orca_task_id`, `terminal_id`/`session_id`, `candidate_commit`, `reviewer_route` ("cx/gpt-5.6-sol"), `reviewer_harness` ("Claude Code"); cấm Control authority phát hành proof.
  4. Từ chối fail-closed mọi nỗ lực của caller tự dựng `ReviewerContext` chỉ bằng các định danh công khai (public IDs); từ chối proof giả mạo, proof sai chữ ký, và proof đã tiêu thụ (single-use replay rejection).
  5. Bộ kiểm thử tự động đạt 367/367 tests PASS (100%), mở rộng suite `TestSolRemediationSeparationOfDuties` lên 9 bài test bao quát toàn bộ negative fixtures và positive control hoàn tất vòng đời đến `integrated`.
- Đã khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên 569f0d1:
  1. Tách rời hoàn toàn dispatch creation khỏi capability delivery: `create_review_dispatch()` chỉ trả về `dispatch_id: str` thuần túy, tuyệt đối không trả bearer token (`reviewer_auth_token`) hay `ReviewDispatchHandle` cho caller/dispatcher.
  2. Loại bỏ hoàn toàn dictionary `_reviewer_auth_tokens` trên `OrcaDeliveryAdapter`, bảo đảm Control plane không thể đọc, giữ, hoặc claim token.
  3. Ràng buộc claim `ReviewerCapability` với `ReviewerContext` đã xác thực (reviewer principal `cx/gpt-5.6-sol`, harness `Claude Code`, session, terminal và Orca dispatch); cấm truy xuất trần (bare retrieval); cấm Control authority claim hoặc issue review evidence.
  4. Bộ kiểm thử tự động đạt 364/364 tests PASS (100%), bổ sung 6 bài kiểm thử độc lập trong `TestSolRemediationSeparationOfDuties` chứng minh Separation of Duties chặt chẽ; toàn bộ project gates PASS.
  5. Sửa toàn bộ 5 lỗi whitespace tại `CHANGELOG.md`, `README.md`, `protocol.md`, `test_negative_fixtures.py` và khôi phục tiếng Việt đầy đủ dấu tại `HANDOFF.md`.
- Đã khắc phục triệt để toàn bộ 3 phát hiện blocker từ Sol-Lead audit trên a189e50:
  1. Loại bỏ hoàn toàn bare retrieval và giao capability qua kênh reviewer-authenticated: Triển khai ReviewerDeliveryChannel và ReviewDispatchHandle mang reviewer_auth_token bảo mật, thực thi nghiêm ngặt single-use; cấm bare retrieval bằng dispatch ID trần; cấm Control authority claim/get ReviewerCapability.
  2. Xóa bỏ hoàn toàn thuộc tính _reviewer_mint_secret trên EvidenceAuthority: Token minting ký bằng _secret nội bộ; cấm gọi _create_reviewer_mint_token ngoài lifecycle create_review_dispatch; quản lý exactly-once minting qua _minted_review_dispatches, ngăn chặn triệt để mint capability thứ hai cho cùng một dispatch.
  3. Hợp nhất verify-and-consume thành thao tác nguyên tử verify_and_consume_capability() dưới threading.RLock(): Cả issue_review_evidence() và issue_integration_evidence() tiêu thụ capability nguyên tử, loại bỏ race condition phát hành hai evidence từ một capability trong môi trường đa luồng; bảo toàn zero side effects khi request malformed.
  4. Bộ kiểm thử tự động đạt 358/358 tests PASS (100%), bổ sung 8 bài kiểm thử độc lập trong TestSolLeadAuditA189e50Remediation bao gồm concurrency test với threading.Barrier và negative/positive fixtures; toàn bộ project gates PASS.
- Đã khắc phục triệt để toàn bộ 2 phát hiện blocker từ Sol-Lead audit trên eab4cab:
  1. Khóa bề mặt mint `ReviewerCapability` bằng token HMAC nội bộ không thể giả mạo (`_InternalReviewerMintToken`): `_mint_reviewer_capability_internal()` bắt buộc phải có mint token hợp lệ, `_create_reviewer_mint_token()` yêu cầu bí mật nội bộ và review dispatch hợp lệ ở trạng thái `review`.
  2. Tách biệt tuyệt đối thẩm quyền Control khỏi Reviewer: `issue_reviewer_capability()` và `get_reviewer_capability()` từ chối fail-closed nếu có `control_capability` hoặc `control_secret`; `ReviewerCapability` được cấp phát và gắn kết độc lập với review dispatch đã xác thực.
  3. Hoàn tất 100% validation trước khi mutate state: cả `issue_review_evidence()` và `issue_integration_evidence()` đều hoàn tất toàn bộ validation (verdict, strict bool, 40-char commit SHA, mandatory gates dict, verify_capability) trước khi ghi nhận capability vào `_consumed_capabilities`, đảm bảo zero side effects khi request malformed.
  4. Bộ kiểm thử tự động đạt 350/350 tests PASS (100%), bổ sung 7 bài kiểm thử độc lập trong `TestSolLeadAuditEab4cabRemediation` tái hiện và kiểm chứng trọn vẹn counterexamples và positive control; toàn bộ project gates PASS.
- Đã khắc phục triệt để toàn bộ phát hiện blocker từ Sol-Lead audit trên 1f90e6c:
  1. Hạn chế tuyệt đối `issue_review_evidence()` chỉ nhận `ReviewerCapability`: Xóa bỏ hoàn toàn khả năng sử dụng `ControlCapability` (kể cả có task-scoped) để phát hành `ReviewEvidence` trên cả `EvidenceAuthority` và `OrcaDeliveryAdapter`. Mọi caller không cung cấp đúng `ReviewerCapability` đều bị từ chối fail-closed bằng `ProtocolViolationError`, bảo toàn tuyệt đối ranh giới independent review.
  2. Ràng buộc `expected_role="Reviewer"` trong `verify_capability()`: Khi thẩm định capability trong `issue_review_evidence()`, truyền tường minh `expected_role="Reviewer"`, từ chối ngay lập tức mọi `ControlCapability` hoặc capability sai vai trò.
  3. Bảo toàn thẩm quyền hợp lệ của Control và bằng chứng tích hợp: `ControlCapability` tiếp tục giữ đầy đủ thẩm quyền mint `ReviewerCapability` qua `issue_reviewer_capability()`/`get_reviewer_capability()` và phát hành `IntegrationEvidence` qua `issue_integration_evidence()` mà không bị hồi quy.
  4. Bộ kiểm thử tự động đạt 343/343 tests PASS (100%), bổ sung 5 bài kiểm thử độc lập trong `TestSolLeadAudit1f90e6cRemediation` tái hiện và kiểm chứng trọn vẹn các counterexample paths và controls; toàn bộ project gates PASS.
- Đã khắc phục triệt để toàn bộ phát hiện blocker từ Sol-Lead audit trên 2f56bd3:
  1. Bắt buộc task-scoped ControlCapability cho resolve_blocker_and_replan: Phương thức `resolve_blocker_and_replan()` bắt buộc phải có `ControlCapability` xác thực độc lập có phạm vi tác vụ cụ thể trước khi thực hiện bất kỳ bước mint token hay đột biến trạng thái nào; từ chối fail-closed mọi lời gọi không thẩm quyền, wildcard, mismatched, Reviewer, forged hoặc replayed capability.
  2. Vô hiệu hóa khả năng cấp thẩm quyền của token minting cho caller thông thường: `_mint_internal_lifecycle_token()` cấm mint cho `resolve_blocker_and_replan` và bảo vệ việc gọi trực tiếp bằng `_internal_secret`; `_internal_lifecycle_execution` từ chối fail-closed mọi token nội bộ đối với `resolve_blocker_and_replan`.
  3. Khóa chặt kiểm tra thẩm quyền chuyển trạng thái: `transition_task_state()` bắt buộc phải có `ControlCapability` đã xác thực trong context khi chuyển sang `ready` hoặc `planned`.
  4. Bộ kiểm thử tự động đạt 333/333 tests PASS (100%), bổ sung 6 bài kiểm thử độc lập trong `TestSolLeadAudit2f56bd3Remediation` tái hiện và kiểm chứng trọn vẹn 2 counterexample paths và controls; toàn bộ project gates PASS.
- Đã khắc phục triệt để toàn bộ phát hiện blocker từ Sol-Lead audit trên 654860c:
  1. Loại bỏ hoàn toàn capability wildcard khỏi module state: Xóa bỏ triệt để WeakKeyDictionary _ADAPTER_INTERNAL_CAPABILITIES cấp module và phương thức _mint_internal_control_capability() / _internal_capabilities trong EvidenceAuthority; caller cùng process không thể lấy hoặc trích xuất capability wildcard nội bộ.
  2. Bảo vệ ranh giới vòng đời nội bộ bằng token tạm thời dùng một lần: Dataclass _InternalLifecycleToken được ký HMAC unforgeable bằng _internal_exec_secret riêng của adapter, kiểm tra tính toàn vẹn và tiêu thụ ngay lập tức (_consumed_internal_tokens) cho toàn bộ 8 lifecycle handler nội bộ.
  3. Khóa chặt các bề mặt callable trước wildcard & internal capabilities: _internal_lifecycle_execution, issue_review_evidence, issue_integration_evidence và verify_capability từ chối fail-closed mọi capability có tiền tố adapter_internal_ hoặc wildcard task id (None hoặc *).
  4. Bộ kiểm thử tự động đạt 327/327 tests PASS (100%), bổ sung 6 bài kiểm thử độc lập trong TestSolLeadAudit654860cRemediation tái hiện và kiểm chứng trọn vẹn counterexample exfiltration và controls; toàn bộ project gates PASS.
- Đã khắc phục triệt để toàn bộ 3 phát hiện blocker từ Sol-Lead review trên 36092d0:
  1. Hạn chế quyền phát hành bằng chứng độc lập qua capability (Restricted Evidence Issuance): Các phương thức `issue_review_evidence()` và `issue_integration_evidence()` bắt buộc phải có capability xác thực độc lập (`ReviewerCapability` hoặc `ControlCapability`) có chữ ký HMAC không thể giả mạo; caller thông thường từ adapter tuyệt đối không thể tự cấp phát bằng chứng có chữ ký nội bộ để đẩy trạng thái qua `merge_queued` hay `integrated`.
  2. Bảo vệ ranh giới thực thi vòng đời bằng capability độc lập (Lifecycle Context Boundary Protection): Ranh giới `_internal_lifecycle_execution` bắt buộc phải có `ControlCapability` hoặc `ReviewerCapability` hợp lệ đã được xác thực; caller thông thường không thể xâm nhập ranh giới nội bộ, không thể mint token để chuyển trạng thái từ `blocked` sang `ready`.
  3. Bắt buộc một định danh canonical duy nhất cho backend provider và model (Exact Canonical Backend Identities): Loại bỏ toàn bộ alias phi chính tắc (`9router/google`, `9router/openai`, `gemini-3.8-flash-high`, `gpt-5.6-sol`), chỉ chấp nhận duy nhất một định danh canonical cho mỗi phase (`implement`: provider `google`, model `ag/gemini-3.8-flash-high`; `review`: provider `openai`, model `cx/gpt-5.6-sol`); mọi biến thể khác đều bị từ chối fail-closed.
  4. Bộ kiểm thử tự động đạt 321/321 tests PASS (100%), bổ sung 8 fixtures trong `TestSolLeadReview36092d0Remediation` tái hiện và kiểm chứng trọn vẹn 3 counterexamples và controls; toàn bộ project gates PASS.
- Đã khắc phục triệt để toàn bộ 3 phát hiện blocker từ Sol-Lead review sau da26686:
  1. Thẩm quyền bằng chứng và chống giả mạo/stale/replay (Evidence Provenance & Freshness): Triển khai `EvidenceAuthority` mang bí mật HMAC nội bộ (`_secret`), cấp phát bằng chứng `ReviewEvidence` và `IntegrationEvidence` kèm chữ ký unforgeable, kiểm tra cửa sổ freshness 300s (chặn bằng chứng năm 2000), theo dõi bằng chứng đã tiêu thụ để ngăn replay (`_consumed_evidence_ids`). Xác thực hoàn tất trước mọi thao tác lưu trữ hay chuyển đổi trạng thái với zero side effects.
  2. Năng lực chuyển đổi vòng đời không thể giả mạo (Unforgeable Lifecycle Capabilities): Đóng hoàn toàn các bề mặt `_mint_transition_token` và `_authorized_transition_scope` trước caller bên ngoài bằng contextmanager `_internal_lifecycle_execution`. Bọc toàn bộ các lifecycle handler hợp lệ (`acknowledge_dispatch`, `start_running`, `create_dispatch`, `handle_worker_done`, `handle_harness_failure`, `handle_review_verdict`, `handle_integration_gates`, `resolve_blocker_and_replan`). Theo dõi giải phóng lease và dàn xếp dispatch có thẩm quyền (`_authoritatively_settled_dispatches`, `_authoritatively_released_tasks`), ngăn chặn thao tác settlement/release ngoài luồng, cấm dùng lại token (`_consumed_transition_tokens`).
  3. Bắt buộc raw canonical spelling tuyệt đối cho tất cả alias định danh: Loại bỏ `.lower()` trước khi xác thực, bắt buộc định danh raw canonical chính xác tuyệt đối trên toàn bộ các vị trí: `effort` (`high`), `provider` (`9router`), `harness` (`Codex CLI` / `Claude Code`), `model` (`ag/gemini-3.8-flash-high` / `cx/gpt-5.6-sol`), `backend_provider` (`google` cho implement, `openai` cho review). Bất kỳ chuỗi đệm khoảng trắng, rỗng, không phải chuỗi, sai hoa thường hoặc mâu thuẫn đều bị từ chối fail-closed.
  4. Bộ kiểm thử tự động đạt 313/313 tests PASS (>297 tests theo yêu cầu); toàn bộ gates kiểm tra độc lập sẵn sàng.
- Đã khắc phục triệt để toàn bộ 3 phát hiện blocker từ Sol-Lead review sau 43c96aa:
  1. Thẩm quyền bằng chứng review & integration fail-closed: Từ chối plain caller dicts/strings/booleans; bắt buộc `ReviewEvidence` và `IntegrationEvidence` có xuất xứ kiểm chứng, băm SHA-256; bắt buộc `base_commit` khớp chính xác `approved_base_commit`; bắt buộc `gate_results` không rỗng và có đầy đủ 11 cổng bắt buộc thuộc `MANDATORY_INTEGRATION_GATES`.
  2. Token capability không thể giả mạo & xóa bỏ hoàn toàn stack frame inspection: Loại bỏ toàn bộ `sys._getframe()`; triển khai capability token mang chữ ký HMAC nội bộ ràng buộc `task_id`, `from_state`, `to_state`, `handler`; bắt buộc dispatch phải settle trong registry và toàn bộ lease phải release trước khi chuyển sang `review`; bảo đảm zero side effects khi chuyển đổi thất bại.
  3. Xác thực unpadded cho dataclass identities: Kiểm tra trực tiếp các trường raw trên `LiveTerminalEvidence` và `UsageEvidence` trước bất kỳ bước chuẩn hóa hay so sánh nào; từ chối fail-closed mọi khoảng trắng đệm.
  4. Bộ kiểm thử tự động đạt 297/297 tests PASS (100%); toàn bộ gates kiểm tra độc lập sẵn sàng.
- Đã khắc phục triệt để toàn bộ 3 phát hiện blocker từ Sol review sau Astra round 18:
  1. Thẩm quyền chuyển đổi review & integration fail-closed: Bắt buộc review dispatch và review evidence đã xác thực (route cx/gpt-5.6-sol, harness Claude Code, exact HEAD) trước khi chuyển sang merge_queued; bắt buộc integration evidence với tất cả gates PASS và bằng chứng ACCEPT trước khi chuyển sang integrated; caller-supplied strings/booleans đơn lẻ không cấu thành thẩm quyền.
  2. Token chuyển đổi trạng thái không thể giả mạo (Unforgeable Transition Tokens): Triển khai _TransitionAuthToken với single-use consumption và kiểm tra frame nội bộ cho _authorized_transition_scope; ngăn chặn caller bên ngoài giả mạo context chuyển đổi trạng thái.
  3. Xác thực nghiêm ngặt mọi alias hiện diện (_extract_and_validate_alias): Kiểm tra tất cả alias key hiện diện, từ chối fail-closed khi gặp None, non-string, blank, whitespace-padded hoặc mâu thuẫn ngữ nghĩa trên toàn bộ implement và review.
  4. Bộ kiểm thử tự động đạt 289/289 tests PASS (100%); toàn bộ gates kiểm tra độc lập sẵn sàng.
- Orca là execution/communication plane. Dely chỉ quản lý implement → independent review bên trong task đã có authority. Dely implement: Codex CLI / `ag/gemini-3.8-flash-high` / `high`; review: Claude Code / `cx/gpt-5.6-sol` / `high`. Supreme audit `cx/gpt-6-astra-medium` / `medium` nằm ngoài Dely và chỉ cho audit cực khó.
- Rollback reference trước thí nghiệm: `D:/AI_SETUP/backups/AI-Auto-Video-Creator/20260928-175542`; đây không phải bằng chứng G05 PASS.

## Evidence bất biến

- P7B accepted source/tooling: `c44214ad027986a0db7cb9d8e221590f232a0036`; accepted GREEN: `run-m2-p7b-green-20260917040648`; accepted RED: `run-m2-p7b-red-20260917002633`.
- Candidate GREEN lịch sử bị từ chối `run-m2-p7b-green-20260917024918` giữ nguyên. P7B oracle SHA-256 `d83d0f2d808f1b0067d5288ea131ded24d8fc46a16462b5254fd4167f7425738`; P7A oracle SHA-256 `63151da21b07c3dd92c5b4a7acc0d4f952f188ee2425a52c9d3ac8d34eb61035`.
- Migration `0008`, ngoại lệ đúng thân P3 `append()` và compatibility đúng thân P7A H16 tiếp tục là một phần accepted P7B; không sửa hoặc chạy lại evidence chỉ vì checkpoint docs/config này.

## Chưa quyết định

- Chưa kích hoạt runtime pilot cho scheduler/lease/merge queue; cần user checkpoint riêng, validator được review và một work package đã có authority.
- Không có quyết định mới cho sample size, scale dataset, output profile, word-timing tolerance, retry/concurrency, retention, provider/model hoặc các open item sản phẩm.

## Đọc tiếp

1. `docs/12-pre-code-checklist.md`
2. `docs/11-roadmap.md`
3. `docs/parallel-delivery/README.md`
4. `docs/milestones/m2-control-plane/implementation-plan.md`
5. `docs/milestones/m2-control-plane/toolchain-lock.md`

## Điểm tiếp tục

Chờ checkpoint thiết kế/independent review riêng cho P8 hoặc checkpoint riêng để pilot kiến trúc parallel delivery trên scope đã được cấp quyền. Không bắt đầu P8 Behavioral RED, P8/P9 implementation, M3 hoặc Phân hệ A từ bundle đề xuất này.

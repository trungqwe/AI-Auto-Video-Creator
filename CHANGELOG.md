# Changelog

## 2026-10-01 — Khắc phục triệt để phát hiện Sol Audit trên 52a2795 (Out-of-Process Host Boundary Channel & Mutable Environment Rejection)

- Khắc phục triệt để phát hiện độc lập (actionable finding) từ Sol trên exact candidate `52a279551f8bd73e0d0dc3f68aad15c959be0bd8` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`):
  - **(1) Triển Khai Kênh Xác Thực Thẩm Quyền Máy Chủ Ngoài Tiến Trình (Out-of-Process Host Boundary Channel)**:
    - Loại bỏ hoàn toàn sự phụ thuộc vào biến môi trường mutable `os.environ["ORCA_HOST_BOUNDARY_TOKEN"]` trong quá trình xác thực host capability.
    - Xây dựng lớp `HostBoundaryChannel` khởi chạy một tiến trình con độc lập làm daemon verifier, giao tiếp qua socket IPC nội bộ `127.0.0.1` với cổng do hệ điều hành tự động cấp phát và secret được truyền an toàn qua pipe `stdin`.
    - Phương thức `_is_valid_host_boundary_capability(token)` ủy thác kiểm chứng 100% tới daemon ngoài tiến trình; candidate worker trong cùng tiến trình tuyệt đối không thể can thiệp hay khởi động lại daemon fail-closed (`ProtocolViolationError`).
  - **(2) Từ Chối Toàn Diện Nỗ Lực Giả Mạo Biến Môi Trường Của Candidate (Candidate Mutable Env Rejection)**:
    - Ngăn chặn triệt để counterexample trong đó candidate worker tự gán `os.environ["ORCA_HOST_BOUNDARY_TOKEN"] = token` để mint handoff hoặc gọi `KeyStoreHostIssuer.get_default_host_issuer` / `TrustedKeyStore.provision_from_host`.
    - Bổ sung các fixture phân biệt `11t`, `11u`, `11v` trong `test_11_finding_01_candidate_key_custody_bootstrap_rejected` và bài test độc lập `test_17_finding_out_of_process_host_boundary_and_mutable_env_rejection`.
  - **(3) Bộ Kiểm Thử Tự Động 393/393 Tests PASS (100%)**:
    - Toàn bộ suite vượt qua 100% không có cảnh báo hay lỗi kiểm thử; tất cả các gate validation và release gate đều đạt.

## 2026-10-01 — Khắc phục triệt để 2 phát hiện độc lập từ Sol Audit sau b85c240 (Out-of-Process Host Boundary Capability & Ephemeral Singleton Poisoning Fail-Closed)

- Khắc phục triệt để hai phát hiện độc lập (actionable findings) từ Sol trên exact candidate `b85c240d466c1624966c36bb9148c10d2112b4ae` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`):
  - **(1) Thẩm Quyền Host Capability Hoàn Toàn Ngoài Tiến Trình (Out-of-Process Host Boundary Capability)**:
    - Loại bỏ hoàn toàn biến `_SENTINEL_HOST_TOKEN` khỏi candidate module `delivery_engine.py`; candidate module không chứa hay rò rỉ bất kỳ sentinel token hay host capability nào.
    - Thẩm quyền host boundary được cung cấp nghiêm ngặt ngoài tiến trình qua biến môi trường host (`ORCA_HOST_BOUNDARY_TOKEN`) kết hợp hàm xác thực mật mã HMAC an toàn thời gian thực.
    - Ngăn chặn triệt để counterexample `COUNTEREXAMPLE_CANDIDATE_BOOTSTRAPS_AUTHORITY` (caller in-process đọc sentinel token từ candidate module để tự ghim khóa và xác minh chữ ký).
    - Bổ sung fixture phân biệt `11s` trong `TestSolTrustBoundaryRootCauseRemediation`.
  - **(2) Chống Đầu Độc Singleton Ephemeral Trong Sổ Đăng Ký Tiêu Thụ (Ephemeral Singleton Poisoning Fail-Closed)**:
    - `DurableConsumptionRegistry.get_default` cấm tuyệt đối cấu hình `db_path=':memory:'` hoặc `allow_ephemeral=True` fail-closed với `ProtocolViolationError`.
    - `OrcaDeliveryAdapter` từ chối fail-closed nếu singleton registry mặc định bị can thiệp thành dạng ephemeral trong bộ nhớ (`_is_mem=True`).
    - Ngăn chặn triệt để counterexample `COUNTEREXAMPLE_EPHEMERAL_DEFAULT_ACCEPTED` (caller đầu độc singleton trước khi adapter khởi tạo).
    - Bổ sung fixture phân biệt `15d` trong `TestSolTrustBoundaryRootCauseRemediation`.
  - **(3) Dọn Dẹp Toàn Bộ Residue Khoảng Trắng**:
    - Xóa bỏ trailing whitespace tại `CHANGELOG.md:30` và `docs/parallel-delivery/README.md:348,367`.
    - Đảm bảo `git diff 4a7c8c921b7e05066505d51b168a02c3fde61317 --check` đạt 0 lỗi khoảng trắng.
  - **(4) Bộ Kiểm Thử Tự Động 392/392 Tests PASS (100%)**:
    - Toàn bộ suite vượt qua 100% không có cảnh báo hay lỗi kiểm thử.

## 2026-10-01 — Khắc phục triệt để 3 phát hiện độc lập từ Sol Audit sau 851d23c (Out-of-Process Key Custody Bootstrap Prevention, Durable Adapter Restart Consumption & Strict Envelope Type Rejection)

- Khắc phục triệt để ba phát hiện độc lập (actionable findings) từ Sol trên exact candidate `851d23c3f7fde7e37891b933547d931706e11417` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`):
  - **(1) Vô Hiệu Hóa Public Host API Bootstrap Khóa Trong Cùng Tiến Trình (Out-of-Process Key Custody Bootstrap Prevention)**:
    - Đóng toàn bộ các API công khai của `KeyStoreHostIssuer` (`get_default_host_issuer`, `issue_handoff`, `issue_isolated_keystore`) và `TrustedKeyStore.provision_from_host` đối với in-process candidate caller bằng cách bắt buộc token máy chủ ngoài tiến trình.
    - Mọi nỗ lực gọi `KeyStoreHostIssuer.get_default_host_issuer()` hoặc tự mint handoff/keystore mà không có thẩm quyền hợp lệ đều bị từ chối fail-closed ngay lập tức với `ProtocolViolationError`.
    - Test harness sử dụng các hàm host helper chuyên biệt (`TrustedHostKeyStoreHandoff`, `TrustedHostIsolatedKeyStore`, `TrustedHostProvisionKeyStore`) đại diện cho ranh giới máy chủ bên ngoài.
  - **(2) Đảm Bảo Tính Bền Vững Tiêu Thụ Của Adapter Qua Khởi Động Lại (Durable Adapter Restart Consumption)**:
    - Loại bỏ hoàn toàn registry bộ nhớ tạm thời `:memory:` khỏi đường dẫn sản xuất của `OrcaDeliveryAdapter`: adapter mặc định sử dụng đường dẫn SQLite bền vững trên ổ đĩa `DEFAULT_PRODUCTION_CONSUMPTION_DB_PATH` (`runtime/orca-consumption-registry.db`) hoặc `consumption_db_path` được chỉ định.
    - Cấm tiêm caller-selected ephemeral in-memory registry (`_is_mem`) vào `OrcaDeliveryAdapter` fail-closed.
    - Dữ liệu phong bì đã tiêu thụ và bộ đếm monotonic fencing token tồn tại bền vững qua restart adapter; replay attack và stale fencing token qua restart bị phát hiện và ngăn chặn 100%.
  - **(3) Loại Bỏ Ép Kiểu Lỏng Lẻo & Kiểm Tra Kiểu Dữ Liệu Nghiêm Ngặt Trước Khi Xử Lý (Strict Envelope Type Rejection)**:
    - Loại bỏ việc ép kiểu `bool(data.get("gates_pass", False))` trong `SignedIntegrationEnvelope.from_dict`; triển khai cơ chế kiểm tra kiểu dữ liệu nghiêm ngặt từ chối fail-closed `EnvelopeVerificationError` đối với chuỗi `'false'`, số nguyên `0`/`1`, hoặc bất kỳ kiểu dữ liệu phi-bool nào.
    - Bổ sung strict type checking cho `gate_results` (bắt buộc dict với giá trị strict bool), `issued_at`/`expires_at` (bắt buộc số thực/nguyên, từ chối bool/str), và `fencing_token` (bắt buộc strict int, từ chối bool/str) cho cả `SignedIntegrationEnvelope` và `SignedReviewEnvelope`.
  - **(4) Bộ Kiểm Thử Tự Động 392/392 Tests PASS (100%)**:
    - Mở rộng suite `TestSolTrustBoundaryRootCauseRemediation` lên 16/16 tests với 2 bài test phương thức mới (`test_15_finding_02_adapter_restart_durable_consumption`, `test_16_finding_03_strict_envelope_type_rejection_no_coercion`) và bổ sung các nhánh probe counterexample `11n..11r` cho public host API bootstrap rejection.

## 2026-10-01 — Khắc phục triệt để phát hiện Sol Audit sau d7f0043 (Out-of-Process Pinned Key Custody Provisioning & Durable Integration Envelope Consumption)

- Khắc phục triệt để hai phát hiện trust-boundary từ đợt independent audit của Sol trên exact candidate d7f0043d99c970e3d6efc7a8c392be73b58b27b2 (approved base: 4a7c8c921b7e05066505d51b168a02c3fde61317):
  - **(1) Vô Hiệu Hóa Key Custody Bootstrap Trong Tiến Trình & Cấp Phát Khóa Ngoài Tiến Trình (Out-of-Process Pinned Key Custody Provisioning)**:
    - Loại bỏ hoàn toàn khả năng candidate worker tự đăng ký public key trong cùng tiến trình: TrustedKeyStore.register_pinned_public_key từ chối caller in-process fail-closed với ProtocolViolationError nếu không có ủy quyền xác thực từ host.
    - Chuyển cơ chế cấp phát khóa sang ranh giới máy chủ bên ngoài: triển khai KeyStoreHostIssuer, KeyStoreHostHandoff, và KeyStoreHostIssuerCapability với token sentinel _SENTINEL_HOST_TOKEN.
    - Pinned public keys được đóng băng trong MappingProxyType bất biến; nghiêm cấm việc ghi đè hoặc thay thế khóa authority đã ghim (Cannot replace or mutate existing pinned key authority).
    - Thuộc tính OrcaDeliveryAdapter.keystore là read-only gắn chặt với TrustedKeyStore.get_default(), từ chối nhận caller-selected keystore fail-closed.
  - **(2) Tiêu Thụ Phong Bì Tích Hợp Nguyên Tử Qua Sổ Đăng Ký Bền Vững (Durable Integration Envelope Consumption)**:
    - TrustedIntegrationConsumer.consume_integration_envelope gọi giao dịch nguyên tử DurableConsumptionRegistry.check_and_consume_integration(...) ngay sau khi xác thực chữ ký Ed25519.
    - Kiểm tra toàn diện temporal validity (expires_at, issued_at <= now + 30.0s), ràng buộc danh tính (expected_task_id, expected_candidate, expected_base), chống phát lại phong bì (envelope_id single-use), chống tái sử dụng nonce, và monotonic fencing token theo miền (task_fencing).
    - Đảm bảo tính bền vững qua restart tiến trình với SQLite và khả năng chống xung đột tương tranh giữa 10 luồng đồng thời (duy nhất 1 luồng thành công, 9 luồng bị chặn bởi ReplayAttackError).
  - **(3) Bộ Kiểm Thử Tự Động 390/390 Tests PASS (100%)**:
    - Bổ sung 4 bài test phương thức toàn diện trong TestSolTrustBoundaryRootCauseRemediation (test_11, test_12, test_13, test_14) bao quát trọn vẹn các kịch bản counterexample tiêu cực cho key custody bootstrap, integration replay/nonce/fencing/expiry, restart durability, và đa luồng tương tranh.

## 2026-09-30 — Khắc phục triệt để phát hiện Sol-Lead audit sau 8913b39 (Out-of-Process Trust Boundary, Asymmetric Ed25519 Cryptography, Pinned Key Custody, Durable Replay Protection & Fail-Closed Production Activation Gate)

- Khắc phục triệt để nguyên nhân gốc rễ (root cause) ranh giới tin cậy (trust boundary) theo audit finding của Sol trên exact candidate `8913b392522701f924117a234f4e0cee7fc83624` (approved base: `4a7c8c921b7e05066505d51b168a02c3fde61317`) và tuân thủ tuyệt đối chỉ thị tại `D:/AI_SETUP/supervisor/generated/root-cause-trust-boundary-intervention.md`:
  - **(1) Tái Hiện RED Evidence & Vô Hiệu Hóa Hoàn Toàn Khả Năng Tự Cấp Quyền Trong Cùng Tiến Trình**:
    - Tái hiện chính xác finding: constructor `ReviewerHostIssuer(_internal_token=b"caller_non_none_token")` cho phép caller tự tạo authority trong cùng Python process.
    - Sửa đổi `ReviewerHostIssuer`: `_internal_token` sử dụng sentinel object private `_SENTINEL_HOST_TOKEN`, cấm caller truyền token tùy ý; đánh dấu deprecated toàn bộ DTO in-process (`ReviewerHostIssuer`, `ReviewerHostHandoff`, `ReviewerSessionBoundary`) và khẳng định chúng mang ZERO thẩm quyền bảo mật trong môi trường production.
  - **(2) Mô Hình Đe Dọa 3 Tầng & Quyết Định Kiến Trúc Tách Biệt Ranh Giới Ngoài Tiến Trình (Out-of-Process Architecture)**:
    - Thiết lập mô hình đe dọa 3 tầng rủi ro: (1) Sửa nhầm thông thường, (2) Candidate/Worker không tin cậy chạy mã Python tùy ý và monkey-patching bộ nhớ, và (3) Host OS Administrator (không tuyên bố sandbox ngăn được Administrator toàn máy).
    - Phân tích 3 phương án và ban hành ADR lựa chọn Phương án 2 (Broker ngoài tiến trình với chữ ký mật mã bất đối xứng kết hợp OS ACL) kết hợp khóa fail-closed kích hoạt production.
    - Tách biệt hoàn toàn privileged decision / merge consumer (`TrustedReviewConsumer`, `TrustedIntegrationConsumer`) ra ngoài tiến trình và interpreter của worker; worker chỉ có quyền nộp request/artifact trên feature branch.
  - **(3) Quản Lý Khóa Bất Đối Xứng Ed25519 & Pinned Key Custody (`TrustedKeyStore`)**:
    - Private signing keys tuyệt đối không nằm trong repository candidate, env của worker, log, hay test fixture; chỉ thuộc sở hữu của phiên Reviewer Lead độc lập (`rev_key_lead_v1`) và Integration Runner độc lập (`integ_gatekeeper_v1`).
    - Candidate worker chỉ được cấu hình danh sách public keys ghim sẵn (`register_pinned_public_key`); hỗ trợ thu hồi khóa tức thời (`revoke_key`) fail-closed.
  - **(4) Phong Bì Ký Số Bất Đối Xứng (`SignedReviewEnvelope` & `SignedIntegrationEnvelope`)**:
    - Phân tách miền ký (Domain Separation): `PARALLEL_DELIVERY_REVIEW_ENVELOPE_V1` và `PARALLEL_DELIVERY_INTEGRATION_ENVELOPE_V1`.
    - Chuẩn hóa chuỗi dữ liệu (Canonical Serialization) RFC 8785 loại trừ trường chữ ký trước khi ký và xác minh.
    - Ràng buộc chặt chẽ commit SHA ứng viên (40-hex), base commit, delivery task ID, review dispatch ID, route attestation (`cx/gpt-5.6-sol`), harness (`Claude Code`), nonce, thời gian hết hạn (`expires_at`), và monotonic fencing token.
  - **(5) Sổ Đăng Ký Tiêu Thụ Bền Vững Đa Tiến Trình (`DurableConsumptionRegistry`)**:
    - Lưu trữ atomic trên SQLite (kèm hỗ trợ in-memory thread-safe cho adapter), ngăn chặn triệt để tấn công phát lại (replay attack) và tái sử dụng nonce (`UNIQUE` constraint).
    - Lưu vết monotonic fencing token bền vững qua restart tiến trình; từ chối fail-closed mọi token cũ hơn hoặc bằng giá trị đã ghi nhận.
    - Kiểm tra temporal freshness window: từ chối phong bì đã hết hạn hoặc phát hành vượt trước thời gian thực (> 30s).
  - **(6) Khóa Kích Hoạt Production Fail-Closed (`ProductionActivationGate`)**:
    - Thiết lập trạng thái `ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED` (`NOT_PROVISIONED`), nghiêm cấm kích hoạt chế độ production hoặc merge vào protected branch khi chưa có 4 điều kiện hạ tầng: `OS_USER_ISOLATION`, `PRIVATE_KEY_ACL_RESTRICTION`, `DEDICATED_RUNNER`, `PROTECTED_BRANCH_POLICY`.
    - Phân định rõ 3 trạng thái: `ARCHITECTURE_IMPLEMENTED`, `REFERENCE_TESTED`, và `PRODUCTION_ACTIVATION_BLOCKED`.
  - **(7) Bộ Kiểm Thử Tự Động 386/386 Tests PASS (100%)**:
    - Bổ sung lớp kiểm thử `TestSolTrustBoundaryRootCauseRemediation` với 10 bài test tự động bao quát toàn bộ threat model và closure matrix (RED evidence, worker monkey-patching failure, asymmetric Ed25519 signature tamper rejection, key revocation, single-use replay protection, SQLite restart durability, temporal validity, production gate fail-closed, fresh subprocess isolation, và positive control full lifecycle review -> merge_queued -> integration -> integrated), nâng tổng số test lên 386/386 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau a189e50 (Reviewer Authenticated Delivery Channel, Removal of _reviewer_mint_secret, Atomic Verify-and-Consume Capability)

- Khắc phục triệt để ba phát hiện blocker từ Sol-Lead independent audit trên exact candidate `a189e501d2eec58f7891cb35d46fbc176c2e2ea8` cho bundle `docs/parallel-delivery/`:
  - **(1) Loại Bỏ Hoàn Toàn Bare Retrieval & Bảo Vệ Giao Nhận Qua Kênh Reviewer-Authenticated (Reviewer Authenticated Delivery Channel)**:
    - Triển khai `ReviewerDeliveryChannel` và `ReviewDispatchHandle` mang `reviewer_auth_token` bảo mật cao (32-byte hex) và cơ chế single-use `_claimed`.
    - `get_reviewer_capability()` và `claim_reviewer_capability()` trên cả `EvidenceAuthority` và `OrcaDeliveryAdapter` từ chối fail-closed nếu gọi trần bằng ID chuỗi mà không có xác thực (`ReviewDispatchHandle` hoặc `reviewer_auth_token`), loại bỏ hoàn toàn khả năng caller cùng tiến trình tự lấy `ReviewerCapability` bằng dispatch ID trần.
    - Tiếp tục từ chối fail-closed tuyệt đối nếu caller cung cấp `control_capability` hoặc `control_secret`, bảo toàn ranh giới độc lập giữa Control và Reviewer.
  - **(2) Xóa Bỏ Hoàn Toàn Thuộc Tính `_reviewer_mint_secret` & Chặn Mint Trùng Lặp (Elimination of _reviewer_mint_secret and Duplicate Minting Prevention)**:
    - Xóa bỏ triệt để thuộc tính `self._reviewer_mint_secret` trên `EvidenceAuthority`; việc ký mint token sử dụng trực tiếp bí mật `_secret` của authority mà không mở bí mật secret ra ngoài.
    - Phương thức `_create_reviewer_mint_token()` cấm truyền `_internal_secret` và chỉ cho phép thực thi bên trong ngữ cảnh vòng đời chính thức `create_review_dispatch`.
    - Bổ sung tập hợp `self._minted_review_dispatches: Set[str]` để kiểm soát exactly-once minting cho từng review dispatch; từ chối fail-closed mọi nỗ lực mint lại capability thứ hai cho cùng một review dispatch.
  - **(3) Hợp Nhất Verify-and-Consume Thành Thao Tác Nguyên Tử (Atomic verify_and_consume_capability Preventing Concurrent Double Issuance)**:
    - Nâng cấp khóa `self._lock` của `EvidenceAuthority` thành `threading.RLock()`.
    - Triển khai phương thức nguyên tử `verify_and_consume_capability()` thực hiện xác thực và tiêu thụ capability ngay lập tức dưới một khóa duy nhất.
    - Cả `issue_review_evidence()` và `issue_integration_evidence()` đều gọi `verify_and_consume_capability()` nguyên tử sau khi đã hoàn thành 100% việc kiểm tra tham số (định dạng commit SHA, verdict, summary, routing, mandatory gates), ngăn chặn triệt để tình trạng hai thread chạy song song cùng phát hành hai evidence từ một capability, đồng thời bảo đảm tính chất zero side effects khi request malformed.
  - **(4) Bộ Fixture Phân Biệt Tự Động 358/358 Tests PASS**:
    - Bổ sung lớp kiểm thử `TestSolLeadAuditA189e50Remediation` với 8 bài kiểm thử độc lập bao phủ toàn diện cả 3 finding (từ chối bare retrieval, cấm Control claim ReviewerCapability, kiểm soát single-use channel, xác nhận không tồn tại `_reviewer_mint_secret`, cấm duplicate minting, kiểm thử đa luồng concurrency với `threading.Barrier`, kiểm thử zero side effects khi request malformed, và positive control toàn trình), nâng tổng số test lên 358/358 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau eab4cab (Unforgeable Reviewer Mint Token, Authenticated Dispatch Binding, Separation of ReviewerCapability from Control, Zero-Side-Effect Validation)

- Khắc phục triệt để hai phát hiện blocker từ Sol-Lead independent audit trên exact candidate `eab4cab060a469ecfec7793a15368e635988033b` cho bundle `docs/parallel-delivery/`:
  - **(1) Khóa Bề Mặt Mint ReviewerCapability Bằng Token HMAC Nội Bộ Không Thể Giả Mạo (Unforgeable Internal Reviewer Mint Token)**:
    - Triển khai dataclass `_InternalReviewerMintToken` mang chữ ký HMAC bí mật (`_reviewer_mint_secret` độc lập của `EvidenceAuthority`).
    - Phương thức `_mint_reviewer_capability_internal()` bắt buộc phải có `_InternalReviewerMintToken` hợp lệ, kiểm tra chữ ký HMAC, `authority_id`, `delivery_task_id`, `review_dispatch_id`, `candidate_commit`, và tiêu thụ token ngay lập tức (`_consumed_mint_tokens`) để chống replay.
    - Phương thức `_create_reviewer_mint_token()` yêu cầu bí mật nội bộ `_internal_secret`, kiểm tra gắn kết với review dispatch đang hoạt động (`active_review_dispatches`, `review_dispatch_bindings`) và trạng thái task phải là `'review'`.
  - **(2) Tách Biệt Tuyệt Đối Thẩm Quyền Control Khỏi Reviewer (Separation of Control Authority from ReviewerCapability)**:
    - Các phương thức `issue_reviewer_capability()` và `get_reviewer_capability()` trên cả `EvidenceAuthority` và `OrcaDeliveryAdapter` từ chối fail-closed ngay lập tức nếu caller cung cấp `control_capability` hoặc `control_secret`, ngăn chặn triệt để hành vi Control tự tạo hoặc tự lấy `ReviewerCapability`.
    - `ReviewerCapability` được cấp phát độc lập khi `create_review_dispatch()` tạo review dispatch đã được xác thực (phù hợp với route `cx/gpt-5.6-sol` trên harness `Claude Code` qua `9router`, effort `high`).
    - Bổ sung trường `role: str = "Reviewer"` trên `ReviewerCapability`, xác thực trong `__post_init__` và kiểm tra trong `verify_capability()`.
    - `issue_review_evidence()` từ chối tuyệt đối `ControlCapability` hoặc bất kỳ capability nào không mang đúng vai trò Reviewer.
  - **(3) Hoàn Tất 100% Validation Trước Khi Mutate State (Zero-Side-Effect Validation for Review and Integration)**:
    - Trong `issue_review_evidence()`: toàn bộ các kiểm tra tính hợp lệ (verdict, định dạng 40-char SHA của candidate commit, summary, khớp định danh binding giữa task/dispatch/commit, trạng thái dispatch trên adapter, và xác thực chữ ký capability qua `verify_capability`) được thực hiện đầy đủ TRƯỚC KHI tiêu thụ capability (`_consumed_capabilities.add(...)`). Mọi request malformed đều thất bại fail-closed mà không làm cháy capability hợp lệ (zero side effects).
    - Trong `issue_integration_evidence()`: toàn bộ các kiểm tra tính hợp lệ (kiểm tra `strict bool` cho `gates_pass`, kiểm tra định dạng 40-char SHA cho cả candidate commit và base commit, dictionary `gate_results` có đầy đủ 11 mandatory gates và mỗi gate value đều là strict bool, và xác thực chữ ký capability qua `verify_capability`) được thực hiện đầy đủ TRƯỚC KHI tiêu thụ capability.
  - **(4) Bộ Fixture Phân Biệt Tự Động 350/350 Tests PASS**:
    - Bổ sung lớp kiểm thử `TestSolLeadAuditEab4cabRemediation` với 7 bài kiểm thử độc lập tái hiện chính xác counterexamples của cả Finding 1 và Finding 2, đồng thời xác nhận các assertions zero-side-effect và positive control toàn trình, nâng tổng số test lên 350/350 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau 2f56bd3 (Replan Control Capability Requirement, Token Minting Hardening, and Boundary Enforcement)

- Khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate 2f56bd36a87daa2ef2db579e5bbf90e8ab088bc6 cho bundle docs/parallel-delivery/:
  - **(1) Bắt Buộc Task-Scoped ControlCapability Cho Replan / Blocker Resolution (Task-Scoped Control Authority for Replan)**: Phương thức `resolve_blocker_and_replan()` bắt buộc caller phải cung cấp `ControlCapability` có phạm vi tác vụ cụ thể (`delivery_task_id` khớp chính xác, không chấp nhận wildcard hay None) và mang chữ ký HMAC hợp lệ từ `EvidenceAuthority` ngay tại callable entry point trước bất kỳ bước mint token hay đột biến trạng thái nào. Mọi lời gọi không có capability, capability wildcard, mismatched task id, sai role (`ReviewerCapability`), giả mạo chữ ký, hoặc replay capability đã tiêu thụ đều bị từ chối fail-closed với `ProtocolViolationError`.
  - **(2) Vô Hiệu Hóa Khả Năng Cấp Thẩm Quyền Của Token Minting Đối Với Caller Thông Thường (Hardened Internal Token Minting)**: Phương thức `_mint_internal_lifecycle_token()` tuyệt đối cấm mint token cho handler `resolve_blocker_and_replan` (yêu cầu thẩm quyền Control độc lập bên ngoài) và bắt buộc phải có bí mật nội bộ `_internal_secret` khớp với `_internal_exec_secret` của adapter. Caller thông thường cùng process gọi trực tiếp `_mint_internal_lifecycle_token()` mà không có bí mật nội bộ sẽ bị từ chối fail-closed ngay lập tức. Contextmanager `_internal_lifecycle_execution` từ chối fail-closed mọi token nội bộ cho `resolve_blocker_and_replan`.
  - **(3) Khóa Chặt Kiểm Tra Thẩm Quyền Khi Chuyển Sang Ready / Planned (Rigorous Transition State Verification)**: Phương thức `transition_task_state()` kiểm tra bắt buộc phải có `ControlCapability` đã xác thực trong evidence/context khi chuyển trạng thái sang `ready` hoặc `planned`, loại bỏ hoàn toàn khả năng bypass trạng thái qua các handler khác hay context giả mạo.
  - **(4) Bộ Fixture Phân Biệt Tự Động 333/333 Tests PASS**: Bổ sung lớp kiểm thử `TestSolLeadAudit2f56bd3Remediation` với 6 bài test độc lập (tái hiện chính xác 2 đường dẫn lỗ hổng mà Sol đã chỉ ra: caller thông thường mint token chuyển blocked sang ready, và unauthenticated resolve_blocker_and_replan; đồng thời kiểm thử từ chối wildcard, mismatched, Reviewer, forged, replay, và positive control toàn trình), nâng tổng số test lên 333/333 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau 654860c (Elimination of Module-Global Capabilities, Internal Ephemeral Tokens, Callable Surface Wildcard Hardening)

- Khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate 654860c5dca9d2d2cc8d780d53f8deda777d80a6 cho bundle docs/parallel-delivery/:
  - **(1) Loại Bỏ Hoàn Toàn Module-Global Capabilities Dictionary (Removal of _ADAPTER_INTERNAL_CAPABILITIES)**: Xóa bỏ hoàn toàn WeakKeyDictionary _ADAPTER_INTERNAL_CAPABILITIES ở cấp module và các phương thức _mint_internal_control_capability(), _internal_capabilities trong EvidenceAuthority. Module state không còn lưu trữ bất kỳ capability nào có thể bị caller cùng process import hoặc index để exfiltrate.
  - **(2) Cơ Chế Xác Thực Vòng Đời Bằng Token Nội Bộ Dùng Một Lần (Internal Ephemeral Lifecycle Tokens)**: Triển khai dataclass _InternalLifecycleToken được ký HMAC bằng khóa bí mật riêng của từng instance adapter (_internal_exec_secret). Tất cả 8 authoritative handlers nội bộ (acknowledge_dispatch, start_running, create_dispatch, handle_worker_done, handle_harness_failure, handle_review_verdict, handle_integration_gates, resolve_blocker_and_replan) đều tự sinh token nội bộ unforgeable và tiêu thụ ngay lập tức (_consumed_internal_tokens), ngăn chặn triệt để replay và forgery.
  - **(3) Khóa Chặt Toàn Bộ Bề Mặt Callable Trước Wildcard & Internal Capabilities (Hardened Callable Surfaces)**: Các hàm _internal_lifecycle_execution, issue_review_evidence, issue_integration_evidence và verify_capability từ chối fail-closed mọi capability có tiền tố adapter_internal_ hoặc wildcard (delivery_task_id là None hoặc *), đảm bảo caller bên ngoài không thể vượt ranh giới hay phát hành bằng chứng trái phép.
  - **(4) Bộ Fixture Phân Biệt Tự Động 327/327 Tests PASS**: Bổ sung lớp kiểm thử TestSolLeadAudit654860cRemediation với 6 bài test độc lập (xác nhận vắng mặt thuộc tính module, từ chối exfiltration chuyển đổi trạng thái blocked sang ready, từ chối phát hành IntegrationEvidence, từ chối phát hành ReviewEvidence, từ chối giả mạo/replay token, và positive control toàn trình), nâng tổng số test lên 327/327 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead review sau 36092d0 (Evidence Capabilities Restriction, Lifecycle Boundary Protection, Exact Canonical Backend Identities)

- Khắc phục triệt để 3 phát hiện blocker từ Sol-Lead review trên exact candidate `36092d099fea4938764b05ff78eb9596a14ad6bc` cho bundle `docs/parallel-delivery/`:
  - **(1) Hạn Chế Quyền Phát Hành Bằng Chứng Độc Lập Qua Capability Xác Thực (Restricted Evidence Issuers via Authenticated Capabilities)**: Các hàm phát hành bằng chứng `issue_review_evidence()` và `issue_integration_evidence()` trên cả `EvidenceAuthority` và `OrcaDeliveryAdapter` bắt buộc caller phải cung cấp capability hợp lệ (`ReviewerCapability` hoặc `ControlCapability`) mang chữ ký HMAC bí mật nội bộ (`_secret`). Caller thông thường không có capability không thể lấy được bằng chứng có chữ ký để chuyển tác vụ sang `merge_queued` hay `integrated`. Bằng chứng và capability được theo dõi single-use (`_consumed_capabilities`), chống giả mạo hoặc tái sử dụng.
  - **(2) Bảo Vệ Ranh Giới Thực Thi Vòng Đời Bằng Capability Độc Lập (Lifecycle Context Boundary Protection)**: Contextmanager `_internal_lifecycle_execution` yêu cầu capability xác thực độc lập (`ControlCapability` cho các thao tác quản trị / integration / settlement và `ReviewerCapability` cho review verdict). Caller thông thường tuyệt đối không thể xâm nhập ranh giới nội bộ, mint transition token giả mạo hay chuyển đổi trạng thái ngoài luồng từ `blocked` sang `ready`.
  - **(3) Bắt Buộc Một Định Danh Backend Provider và Model Canonical Duy Nhất Không Alias (Exact Canonical Backend Provider & Model Spelling)**: Loại bỏ toàn bộ alias phi chính tắc trong xác thực `UsageEvidence`: `implement` chỉ chấp nhận duy nhất backend_provider `"google"` và backend_model `"ag/gemini-3.8-flash-high"`; `review` chỉ chấp nhận duy nhất backend_provider `"openai"` và backend_model `"cx/gpt-5.6-sol"`. Toàn bộ các biến thể như `"9router/google"`, `"9router/openai"`, `"gemini-3.8-flash-high"`, `"gpt-5.6-sol"` đều bị từ chối fail-closed với `RoutingEvidenceError`.
  - **(4) Bộ Fixture Phân Biệt Tự Động 321/321 Tests PASS**: Bổ sung lớp kiểm thử `TestSolLeadReview36092d0Remediation` với 8 bài test độc lập (5 counterexamples tái hiện chính xác lỗi trên 36092d0 và 3 test positive/negative controls cho capability validation, signature mismatch, single-use replay protection và boundary checks), nâng tổng số test lên 321/321 passed 100%.

## 2026-09-29 — Khắc phục phát hiện Sol-Lead review sau 43c96aa (Evidence Authority, Frame-Name Spoofing, Padded Dataclass Identities)

- Khắc phục triệt để 3 phát hiện blocker từ Sol-Lead review sau `43c96aa` cho bundle `docs/parallel-delivery/`:
  - **(1) Thẩm Quyền Bằng Chứng Review & Integration Fail-Closed (Review/Integration Evidence Provenance & Baseline/Gate Validation)**: Nghiêm cấm nhận plain caller dictionaries, booleans hoặc strings trong `handle_review_verdict()` và `handle_integration_gates()`. Bắt buộc đối tượng dataclass `ReviewEvidence` và `IntegrationEvidence` có xuất xứ kiểm chứng, băm SHA-256 nhất quán, ràng buộc chính xác commit candidate và HEAD. Bắt buộc `IntegrationEvidence.base_commit` phải khớp chính xác với `approved_base_commit` của adapter (`4a7c8c921b7e05066505d51b168a02c3fde61317`), từ chối fail-closed wrong-base. Bắt buộc `gate_results` phải là mapping không rỗng (`gate_count > 0`) và có đầy đủ 11 cổng bắt buộc thuộc `MANDATORY_INTEGRATION_GATES` (`authority`, `candidate`, `scope`, `encoding`, `security`, `contract`, `migration`, `focused_tests`, `regression`, `evidence`, `independent_review`) đều PASS.
  - **(2) Loại Bỏ Hoàn Toàn Stack Inspection & Bảo Vệ Chuyển Đổi Vòng Đời Bằng Capability HMAC Nội Bộ**: Xóa bỏ toàn bộ kiểm tra ngữ cảnh dựa vào stack frame (`sys._getframe`), hàm/frame name caller hoặc trạng thái ambient có thể giả mạo. Cơ chế xác thực chuyển đổi trạng thái dùng token capability nội bộ mang chữ ký HMAC bí mật (`_internal_transition_secret` sinh ngẫu nhiên khi khởi tạo adapter), ràng buộc `from_state`, `to_state`, `task_id`, `handler` và `adapter_id`. Bắt buộc kiểm tra điều kiện tiên quyết khi chuyển sang `review`: dispatch tương ứng phải được settle trong registry và toàn bộ lease đột biến/thực thi của tác vụ/dispatch phải được giải phóng hoàn toàn; ngăn chặn triệt để hành vi giả mạo chuyển trạng thái sang `review` khi dispatch chưa settle và lease vẫn active. Chuyển đổi thất bại bảo đảm 100% không để lại tác dụng phụ (zero side effects).
  - **(3) Xác Thực Unpadded Cho Dataclass Identities Trước Mọi Chuẩn Hóa**: Hàm helper `_validate_unpadded_identity()` kiểm tra trực tiếp các trường dữ liệu thô trên dataclass `LiveTerminalEvidence` (`harness`, `provider`, `route`, `archive_reference`, `dispatch_id`, `delivery_task_id`, `effort`) và `UsageEvidence` (`backend_provider`, `backend_model`, `timestamp`, `request_id`, `dispatch_id`, `delivery_task_id`, `router`) trước bất kỳ bước chuẩn hóa `.strip()` hay so sánh chính tắc nào; từ chối fail-closed ngay lập tức khi phát hiện khoảng trắng đệm ở đầu hoặc cuối.
  - **(4) Bộ Fixture Phân Biệt Tự Động 297/297 Tests PASS**: Bổ sung lớp kiểm thử `TestSolLeadReview43c96aaRemediation` với 8 bài test độc lập (7 test counterexample tái hiện chính xác lỗi trên 43c96aa và 1 positive control toàn trình), nâng tổng số test lên 297/297 passed 100%.

## 2026-09-29 — Khắc phục phát hiện Sol review sau Astra round 18 (Review/Integration Authority, Unforgeable Transition Tokens, Strict Alias Validation)

- Khắc phục triệt để 3 phát hiện blocker từ Sol review sau Astra round 18 cho bundle docs/parallel-delivery/:
  - **(1) Thẩm Quyền Chuyển Đổi Review & Integration Fail-Closed (Review Dispatch & Integration Evidence Authority)**: Bắt buộc phải có review_dispatch_id hợp lệ và review_evidence đã được xác thực (khớp candidate commit, exact HEAD SHA, route cx/gpt-5.6-sol, harness Claude Code, verdict khớp) mới được chuyển sang merge_queued, remediation hoặc blocked. Thêm phương thức create_review_dispatch() tạo dispatch review độc lập, phân bổ phase review, không giữ mutation lease. Bắt buộc phải có integration_evidence đã được xác thực với tất cả các gate con đều PASS và bằng chứng ACCEPT từ independent review trước đó mới được chuyển sang integrated. Chuỗi string hoặc giá trị boolean từ phía caller đơn lẻ tuyệt đối không cấu thành thẩm quyền.
  - **(2) Token Chuyển Đổi Không Thể Giả Mạo (Unforgeable & Private Transition Authorization Tokens)**: Định nghĩa dataclass frozen _TransitionAuthToken và cơ chế sinh token nội bộ _mint_transition_token() với kiểm tra frame caller (sys._getframe(1)), chỉ cho phép các handler nội bộ được đăng ký hợp lệ sinh token. _authorized_transition_scope và transition_task_state bắt buộc phải có token hợp lệ, kiểm tra ngữ cảnh caller và tiêu thụ token ngay sau khi sử dụng (strictly single-use); ngăn chặn triệt để mọi nỗ lực giả mạo context chuyển đổi trạng thái từ caller bên ngoài.
  - **(3) Xác Thực Nghiêm Ngặt Mọi Khóa Alias Hiện Diện (Strict Alias Presence, None, Type & Semantic Validation)**: Hàm _extract_and_validate_alias() không bỏ qua các khóa alias có giá trị None hiện diện trong mapping; từ chối fail-closed mọi khóa alias có giá trị None, sai kiểu (non-string), rỗng hoặc có khoảng trắng đệm. Kiểm tra tính nhất quán ngữ nghĩa trên tất cả alias hiện diện, từ chối fail-closed khi phát hiện mâu thuẫn giữa các alias trên implement và review (route, launch requested/effective, live terminal, usage, task, dispatch).
  - **(4) Bộ Fixture Phân Biệt Tự Động 289/289 Tests PASS**: Bổ sung lớp kiểm thử TestSolRound18Remediation với 15 bài test counterexample và positive controls, nâng tổng số test lên 289/289 passed 100%.

## 2026-09-29 — Khắc phục phát hiện Astra Lead round 18 (Lifecycle Authority Bypass, Contradictory Aliases, Raw Router Identity, Canonical Bytes)

- Khắc phục triệt để 4 phát hiện blocker từ Astra Lead review round 18 trên HEAD `4c95c1d7914772d6311b44aa482fb3eeff5b4912` cho bundle `docs/parallel-delivery/`:
  - **(1) Chống Vượt Rào Thẩm Quyền Vòng Đời Tác Vụ (Lifecycle & Authority Fail-Closed)**: Khóa chặt phương thức công khai `transition_task_state()`, từ chối fail-closed mọi chuyển đổi trạng thái vòng đời trừ khi được gọi từ handler hợp lệ (`create_dispatch`, `acknowledge_dispatch`, `start_running`, `handle_worker_done`, `handle_review_verdict`, `handle_integration_gates`, `resolve_blocker_and_replan`), thẩm quyền tác vụ là `granted` và có đầy đủ bằng chứng dispatch, lease đang active và fencing token đã xác thực.
  - **(2) Xác Thực Nghiêm Ngặt Mọi Alias Bằng Chứng (Contradictory Evidence Aliases Validation)**: Hàm `_extract_and_validate_alias()` kiểm tra mọi alias hiện diện phải đúng kiểu chuỗi, không rỗng và đồng nhất về mặt ngữ nghĩa trước khi trích xuất giá trị chính tắc; từ chối fail-closed khi phát hiện mâu thuẫn alias giữa `route`/`model`, `provider`/`router`, `archive_reference`/`terminal_id`, `delivery_task_id`/`task_id`, `dispatch_id`/`dispatch` trên cả phase implement và review.
  - **(3) Bắt Buộc Định Danh Router Raw Chuỗi Chính Xác Tuyệt Đối (Strict End-to-End Raw Router Identity)**: Yêu cầu chuỗi raw chính xác `"9router"` tại toàn bộ các vị trí định tuyến (`route.provider`, `launch_requested.provider`, `launch_effective.provider`, `live_terminal_evidence.provider`, `usage_evidence.router`) mà không dùng chuẩn hóa `.strip()` để biến chuỗi đệm thành hợp lệ; từ chối mọi biến thể có khoảng trắng đệm fail-closed.
  - **(4) Chính Sách Byte Chính Tắc và Tính Tái Lập Băm Attestation (Canonical-Byte Policy & Reproducible Git Blobs)**: Thiết lập và thực thi chính sách byte chính tắc buộc toàn bộ tệp trong bundle dùng ký tự xuống dòng LF đồng nhất với Git blob; loại bỏ triệt để sai lệch băm trên Windows do CRLF; đảm bảo băm attestation trong báo cáo khớp 100% với Git blob khi clone mới.
  - **(5) Bộ Fixture Phân Biệt Tự Động 274 Fixtures**: Bổ sung lớp kiểm thử `TestAstraRound18Remediation` với 22 bài test counterexample và positive control, nâng tổng số kiểm thử lên 274 fixtures.

## 2026-09-29 — Khắc phục phát hiện Sol review dispatch vòng 18 (Exact Raw Router Identity & No Whitespace Normalization)

- Khắc phục triệt để phát hiện blocker từ Sol re-review dispatch `ctx_0685621e5af0` trên HEAD `38f3da2e96e0b2404662d08a82a1594c16c2263d` cho bundle `docs/parallel-delivery/`:
  - **(1) Yêu Cầu Định Danh Router Raw Chính Xác Tuyệt Đối (Exact Raw Router Identity)**: Mọi giá trị alias router được cung cấp (`router`, `route_provider`, `source`) ở dạng mapping cũng như `UsageEvidence.router` ở dạng dataclass bắt buộc phải khớp chính xác tuyệt đối với chuỗi `"9router"`. Xóa bỏ hoàn toàn bước chuẩn hóa khoảng trắng `.strip()` trước khi so sánh, cấm biến chuỗi có khoảng trắng đệm thành hợp lệ.
  - **(2) Từ Chối Mọi Trường Hợp Padded Router Fail-Closed**: Từ chối ngay lập tức và ném `RoutingEvidenceError` khi giá trị router có khoảng trắng đầu (`" 9router"`), khoảng trắng cuối (`"9router "`), khoảng trắng hai phía (`" 9router "`), tab (`"\t9router"`), newline (`"\n9router\n"`), hoặc carriage return (`"\r\n9router\r\n"`).
  - **(3) Khóa Chặt Agreeing Padded Aliases và Mixed Aliases**: Khi nhiều alias router cùng hiện diện trong mapping, nếu tất cả cùng đồng thuận trên một giá trị đệm (như `{"router": " 9router ", "route_provider": " 9router "}`), hệ thống từ chối fail-closed vì giá trị raw không khớp `"9router"`; nếu các alias mâu thuẫn hoặc không đồng bộ (như `{"router": "9router", "route_provider": " 9router "}`), hệ thống từ chối fail-closed vì alias mâu thuẫn.
  - **(4) Bảo Toàn Thẩm Quyền và Ràng Buộc Tương Hỗ (Fail-Before-Side-Effects & Mutual Binding)**: Giữ vững toàn bộ các ràng buộc tương hỗ với route provider, launch requested/effective, live terminal provider và phase; giữ nguyên thứ tự thực thi kiểm tra routing evidence trước bất kỳ tác động phụ nào lên lease hay task state.
  - **(5) Bộ Fixture Phân Biệt Tự Động 252/252 PASS**: Bổ sung lớp kiểm thử `TestSolRound18ExactRawRouterIdentity` với 8 bài test discriminating RED/GREEN và kiểm chứng đối chứng độc lập trong `test_negative_fixtures.py`, nâng tổng số test lên 252/252 passed 100%.
  - **(6) Bảo Toàn Toàn Bộ Invariants**: Bảo toàn trọn vẹn toàn bộ 244 fixture hiện hữu và các bất biến kiến trúc đã thiết lập từ các vòng trước.

## 2026-09-29 — Khắc phục phát hiện Sol review dispatch vòng 17 (Mandatory Explicit Usage Router Evidence & Mutual Binding)

- Khắc phục triệt để phát hiện blocker từ Sol review dispatch `ctx_91fdbd7c4e2b` trên HEAD `5297a42747ded46644ef277e6c337a39cfedaad0` cho bundle `docs/parallel-delivery/`:
  - **(1) Bắt Buộc Khai Báo Rõ Ràng Định Danh Router trong Bằng Chứng Sử Dụng (Explicit Usage Router Identity)**: Mọi mapping `usage_evidence` bắt buộc phải khai báo rõ ràng, không để trống (non-blank string) định danh router qua một trong các alias hợp lệ (`router`, `route_provider`, `source`). Xóa bỏ hoàn toàn cơ chế fallback ngầm định tự gán `"9router"` khi vắng mặt các khóa này, loại bỏ triệt để sơ hở fail-open chấp nhận bản ghi sử dụng không chứng minh được router.
  - **(2) Khóa Chặt Định Danh `9router` Duy Nhất Cho Implement và Review**: Chỉ chấp nhận định danh router chính xác `9router` cho cả hai phase implement và review; cấm tuyệt đối router `Antigravity native`, cấm nhà cung cấp trực tiếp `direct-vendor`, cấm nhà cung cấp backend/ngoại lai (`openai`, `google`, `custom_router`).
  - **(3) Từ Chối Tuyệt Đối Giá Trị Rỗng, Sai Kiểu, Mâu Thuẫn Hoặc Khóa Ngoại Lai (Fail-Closed with RoutingEvidenceError)**: Ném `RoutingEvidenceError` fail-closed ngay lập tức khi phát hiện trường router bị thiếu, rỗng (`""`, `"   "`, `None`), sai kiểu dữ liệu (số nguyên, boolean, danh sách, dict), mâu thuẫn giữa các alias hiện diện (ví dụ `router="9router"` cùng `route_provider="direct-vendor"`), hoặc chứa khóa router lạ/ngoại lai (`foreign_router`, `custom_router`, `route_source`).
  - **(4) Ràng Buộc Tương Hỗ Chặt Chẽ (Mutual Binding)**: Ràng buộc chặt chẽ định danh usage router rõ ràng với `route.provider`, `launch_requested.provider`, `launch_effective.provider`, `live_terminal_evidence.provider` và phase tương ứng.
  - **(5) Bộ Fixture Phân Biệt Tự Động 244/244 PASS**: Bổ sung lớp kiểm thử `TestSolRound17UsageRouterEvidenceValidation` với 9 bài test discriminating RED/GREEN và kiểm chứng đối chứng độc lập trong `test_negative_fixtures.py`, nâng tổng số test lên 244/244 passed 100%.
  - **(6) Bảo Toàn Toàn Bộ Invariants**: Bảo toàn trọn vẹn toàn bộ 235 fixture hiện hữu, các bất biến launch-evidence của vòng 16, định danh tác vụ, backend model, lease/fencing và cơ chế fail-before-side-effect trước mọi tác động phụ.

## 2026-09-29 — Khắc phục phát hiện Astra supreme audit dispatch vòng 16 (Mandatory Launch Evidence Validation & Mutual Binding)

- Khắc phục triệt để phát hiện blocker từ Astra supreme audit dispatch `ctx_f3936df94ecf` trên HEAD `34f9af5ade2b8991912f622a6b45b39a57cf6d91` cho bundle `docs/parallel-delivery/`:
  - **(1) Bắt Buộc Cặp Bằng Chứng Khởi Chạy Máy Đọc Được (Machine-Readable Launch Mappings)**: Mọi execution envelope đều bắt buộc phải cung cấp cả hai trường `launch_requested` và `launch_effective` dưới dạng mapping máy đọc được (non-empty mapping), từ chối fail-closed ngay lập tức nếu thiếu (None / omitted) hoặc sai kiểu dữ liệu (non-mapping).
  - **(2) Xác Thực Nghiêm Ngặt Định Danh Theo Phase**: Cả `launch_requested` và `launch_effective` bắt buộc phải chứa đầy đủ 4 trường định danh riêng biệt không được để trống: `harness`, `provider` (hoặc `router`), `model` (hoặc `route`) và `effort`. Khóa chính xác định danh theo phase: phase `implement` = `Codex CLI` + `9router` + `ag/gemini-3.8-flash-high` + `high`; phase `review` = `Claude Code` + `9router` + `cx/gpt-5.6-sol` + `high`. Cấm tuyệt đối fallback sang `Antigravity native`, cấm nhà cung cấp `direct-vendor`/ngoại lai, cấm model sai và cấm slug gộp model/effort.
  - **(3) Ràng Buộc Tương Hỗ Chặt Chẽ (Mutual Binding)**: Ràng buộc chặt chẽ `launch_requested` và `launch_effective` với nhau (từ chối fail-closed nếu có bất kỳ sự sai lệch nào giữa requested và effective), đồng thời ràng buộc nhất quán với trường `route` của envelope, neo bằng chứng `live_terminal_evidence`, bằng chứng sử dụng `usage_evidence` và phase tương ứng.
  - **(4) Từ Chối Tuyệt Đối Phase Không Hợp Lệ**: Tái khẳng định Astra là phân phối supreme-audit control-plane độc lập, không phải là phase review trong envelope của Dely; bất kỳ envelope nào khai báo phase `astra` đều bị từ chối fail-closed.
  - **(5) Bộ Fixture Phân Biệt Tự Động 235/235 PASS**: Bổ sung lớp kiểm thử `TestAstraRound16LaunchEvidenceValidation` với 16 bài test discriminating RED/GREEN và đối chứng độc lập trong `test_negative_fixtures.py`, nâng tổng số test lên 235/235 passed 100%.
  - **(6) Bảo Toàn Toàn Bộ Invariants**: Bảo toàn trọn vẹn toàn bộ 219 fixture hiện hữu, các bất biến định danh, backend, lease/fencing và cơ chế fail-before-side-effect trước đó.

## 2026-09-29 — Khắc phục phát hiện Sol re-review vòng 15 (Fail-Before-Side-Effect Validation Ordering Preceding Lease Purge)

- Khắc phục triệt để phát hiện blocking từ Sol review dispatch `ctx_0ece9399b481` trên HEAD `8f27b701efb452cbe6c9acdd1a028160e776ba7a` cho bundle `docs/parallel-delivery/`:
  - **(1) Tái Cấu Trúc Thứ Tự Xác Thực Fail-Before-Side-Effect trong `create_dispatch()`**: Toàn bộ các kiểm tra thuần túy không gây đột biến (pure, non-mutating checks) cho `dispatch_origin` và `execution_envelope` — bao gồm exact delivery task, Orca task, dispatch, phase, harness/model/effort và evidence anchors — bắt buộc được thực thi trước bất kỳ thao tác nào có thể purge, vô hiệu hóa, ghi đè hoặc lưu trữ trạng thái lease, task hay registry.
  - **(2) Lỗi Định Tuyến Thắng Tuyệt Đối Khi Gặp Lease Hết Hạn/Sai Định Dạng Với Envelope Lỗi**: Khi envelope không khớp hoặc dispatch origin không hợp lệ kết hợp với lease đang active bị hết hạn hoặc malformed `expires_at`, hệ thống ném `RoutingEvidenceError` fail-closed ngay lập tức; lease không bị xóa khỏi `active_leases`, không bị đặt `is_active = False`, và toàn bộ trạng thái task/dispatch/registry được giữ nguyên byte-for-byte / field-for-field không có bất kỳ tác động phụ nào (zero side effects).
  - **(3) Bảo Toàn Thẩm Quyền Xử Lý Lease Hợp Lệ (Positive Control)**: Khi envelope và routing input hoàn toàn hợp lệ, các kiểm tra authoritative lease/fencing và cơ chế purge lease hết hạn/malformed tiếp tục hoạt động chính xác như thiết kế ban đầu.
  - **(4) Bộ Fixture Phân Biệt Tự Động 219/219 PASS**: Bổ sung lớp kiểm thử `TestSolRound15FailBeforeSideEffect` với 11 bài test phân biệt và đối chứng độc lập trong `test_negative_fixtures.py`, nâng tổng số test lên 219/219 passed 100%.
  - **(5) Bảo Toàn Toàn Bộ Invariants**: Bảo toàn trọn vẹn toàn bộ 208 test hiện hữu cùng các bất biến kiến trúc đã thiết lập từ các vòng trước.

## 2026-09-29 — Khắc phục phát hiện Sol re-review vòng 14 (Mandatory Envelope Orca Task Identity, Anchored Evidence, Exact Backend Models)

- Khắc phục toàn diện các phát hiện blocking từ scoped review của Sol trên HEAD `5663c68a2628ca934604b9e71cea536a3c5226ee` cho bundle `docs/parallel-delivery/`:
  - **(1) Bắt Buộc Trường Định Danh Orca Task trong ExecutionEnvelope**: Bổ sung trường bắt buộc `orca_task_id` vào `ExecutionEnvelope` và `make_execution_envelope()`; kiểm tra và ràng buộc chính xác với tham số `orca_task_id` của `create_dispatch()` ngay trước khi có bất kỳ tác động phụ nào lên task state, lease, dispatch registry hay binding; loại bỏ hoàn toàn khả năng bỏ trống hoặc sai lệch định danh tác vụ Orca.
  - **(2) Bắt Buộc Neo Định Danh và Trường Effort trên Bằng Chứng Thực Thi**: `LiveTerminalEvidence` và `UsageEvidence` bắt buộc phải có đầy đủ các trường `delivery_task_id` và `dispatch_id` không rỗng; `LiveTerminalEvidence` bắt buộc phải có trường `effort == "high"`; từ chối fail-closed đối với trường bị thiếu hoặc rỗng, không chỉ từ chối giá trị mâu thuẫn.
  - **(3) Khớp Chính Xác Định Danh Backend Model theo Phase (Loại Bỏ Substring/Foreign Aliases)**: Kiểm tra backend model theo danh sách định danh chính xác, loại bỏ hoàn toàn cơ chế kiểm tra substring; phase `implement` chỉ chấp nhận dạng routed hoặc canonical backend chính xác của `gemini-3.8-flash-high` (`{"ag/gemini-3.8-flash-high", "gemini-3.8-flash-high"}`); phase `review` chỉ chấp nhận dạng routed hoặc canonical backend chính xác của `gpt-5.6-sol` (`{"cx/gpt-5.6-sol", "gpt-5.6-sol"}`); từ chối mọi tiền tố, hậu tố và foreign alias như `prefix-gpt-5.6-sol-foreign`.
  - **(4) Bộ Fixture Phân Biệt Tự Động 208/208 PASS**: Bổ sung 10 bài kiểm tra phản ví dụ và kiểm chứng độc lập trong `TestSolRound14IdentityAnchorsAndBackendValidation` thuộc `test_negative_fixtures.py`, nâng tổng số test lên 208/208 passed 100%.
  - **(5) Bảo Toàn Toàn Bộ Invariants**: Bảo toàn trọn vẹn toàn bộ các quy tắc bất biến về lease, fencing, fail-before-side-effect, harness-failure, exact-HEAD và release gate đã thiết lập từ các vòng trước.

## 2026-09-29 — Khắc phục phát hiện Sol re-review vòng 13 (Fail-Closed Execution Envelope & Anchored Routing Evidence)

- Khắc phục toàn diện phát hiện F2 từ scoped re-review của Sol trên HEAD wrapper `b2cd8d177a6048d7385dd551190dd5808ba39739` cho bundle `docs/parallel-delivery/`:
  - **(1) Thực Thi Fail-Closed Dispatch Origin và Execution Envelope Trước Tác Động Phụ**: Mọi lệnh gọi `OrcaDeliveryAdapter.create_dispatch()` bắt buộc phải có `dispatch_origin == "dely dispatch"` và cung cấp `execution_envelope` hợp lệ; kiểm tra fail-closed xảy ra trước mọi side effect lên task state, dispatch registry, binding hay active lease; loại bỏ dứt điểm counterexample `dispatch_without_origin_or_envelope_accepted = ctx-probe`.
  - **(2) Ràng Buộc Định Danh Bắt Buộc (Mandatory Identity Binding)**: `validate_execution_envelope()` bắt buộc các trường `delivery_task_id`, `dispatch_id`, `phase`, route, live terminal/archive evidence và 9Router usage evidence; đối chiếu chặt chẽ với exact task, intended dispatch attempt và phase đang được tạo, loại bỏ triệt để counterexample `missing_identity_fields_result = []`.
  - **(3) Bằng Chứng Terminal Đã Xác Thực (Verified Live Terminal Evidence)**: Yêu cầu bắt buộc `live_terminal_evidence.verified is True` (bắt buộc boolean `True`), khớp chính xác harness, route/model, effort `high`, terminal/archive reference và định danh dispatch/task.
  - **(4) Độ Tươi và Nguồn Bằng Chứng Sử Dụng 9Router (Machine-Readable Usage Freshness)**: Bằng chứng usage phải chứng minh route qua `9router`, backend provider/model đúng phase (`google`/`ag/gemini-3.8-flash-high` cho implement, `openai`/`cx/gpt-5.6-sol` cho review), neo đúng dispatch/task, và timestamp máy đọc được (ISO 8601) thực sự không sớm hơn thời điểm dispatch; không phụ thuộc riêng vào boolean `recorded_after_dispatch`.
  - **(5) Fixture Suite Tự Động 198/198 PASS**: Bổ sung 8 bài kiểm tra phản ví dụ và kiểm chứng độc lập trong `TestSolRound13FailClosedExecutionEnvelope` thuộc `test_negative_fixtures.py`, nâng tổng số test lên 198/198 passed 100%.

## 2026-09-29 — Khắc phục toàn bộ phát hiện Sol review vòng 11 (Identity-First Fail-Closed Harness Failure & Machine-Readable Routing Authority Policy)

- Khắc phục toàn diện phát hiện/blocker từ independent Sol round 11 review cho bundle `docs/parallel-delivery/`:
  - **(1) Xử lý Harness Failure theo Định danh Trước, Không Tác động Phụ (Finding F1)**: `OrcaDeliveryAdapter.handle_harness_failure()` thực hiện kiểm tra định danh trước fail-closed (xác minh dispatch tồn tại, thuộc đúng task, chưa settled, là active dispatch hiện hành, và task đang trong trạng thái thực thi hợp lệ) trước khi có bất kỳ tác động phụ nào; chỉ thu hồi các lease được gán trực tiếp cho dispatch đã xác thực, tuyệt đối không thu hồi lease của dispatch khác hoặc của task; lỗi kiểm tra hoặc lỗi lưu trữ đĩa (persistence failure) không để lại tác động phụ một phần, bảo toàn 100% lease của active dispatch mới; harness failure hợp lệ chuyển task sang `blocked`, giải phóng và fence tài nguyên an toàn mà không làm đột biến commit candidate.
  - **(2) Bằng chứng Định tuyến Machine-Readable và Execution Envelope Policy (Finding F2)**: Thiết lập schema và validator cho execution envelope (`validate_execution_envelope`, `ExecutionEnvelope`, `LiveTerminalEvidence`, `UsageEvidence`, `RoutingEvidenceError`); bắt buộc dispatch xuất phát từ `dely dispatch` (nghiêm cấm direct Orca `worker-start`); bắt buộc route `implement` và `review` dùng `provider: 9router`; tách riêng các trường `harness`, `model`, `effort` (nghiêm cấm slug gộp như `cx/gpt-5.6-sol-high`); yêu cầu bắt buộc bằng chứng terminal/archive trực tiếp và bằng chứng log 9Router ghi nhận request sau dispatch (`recorded_after_dispatch: true`); cấm commit credential/secret hoặc đường dẫn DB cục bộ khả biến; bảo toàn sự phân biệt giữa cơ chế fallback provider sản phẩm trong roadmap và cấm fallback agent-harness/provider trong delivery control plane.
  - **(3) Fixture Suite Tự Động 190/190 PASS**: Bổ sung 14 bài kiểm tra phản ví dụ và kiểm chứng độc lập trong `TestSolRound11HarnessFailureLeaseSafety` (6 test) và `TestSolRound11RoutingEvidencePolicy` (8 test) thuộc `test_negative_fixtures.py`, nâng tổng số test lên 190/190 passed 100%.

## 2026-09-29 — Khắc phục toàn bộ phát hiện Sol review vòng 10 / 11 (Fail-Closed Harness Compatibility, Loại Bỏ Mâu Thuẫn Antigravity Native Fallback)

- Khắc phục toàn diện phát hiện/blocker từ independent Sol review trên HEAD `3f3e6f626455007001f5af6dd2f85bdfd0b5cbd3` cho bundle `docs/parallel-delivery/`:
  - **(1) Loại Trừ Triệt Để Mâu Thuẫn Antigravity Native Fallback**: Tuân thủ chính sách fail-closed tại `AGENTS.md` (yêu cầu Codex CLI với route `ag/gemini-3.8-flash-high`, nghiêm cấm Antigravity native và cấm tuyệt đối fallback sang harness/provider/model khác). Xóa bỏ 100% logic và câu từ fallback sang Antigravity native trong toàn bộ bundle kiến trúc (`operating-model.md`, `protocol.md`, `security-performance-recovery.md`, `README.md`, `delivery_engine.py`).
  - **(2) Máy Trạng Thái Harness Dừng Fail-Closed Ở STOP_BLOCKED**: `HarnessExecutionStateMachine` chuyển sang chu trình `IDLE -> RUNNING -> SUCCESS | FAILURE | STOP_BLOCKED`; nghiêm cấm và từ chối fail-closed trạng thái `STOP_FALLBACK` hoặc bất kỳ trạng thái fallback nào qua `HarnessCompatibilityError`. Khi xảy ra lỗi tương thích hoặc khói thực thi công cụ (như sụp namespace), hệ thống kích hoạt điều kiện STOP và chuyển sang `STOP_BLOCKED`.
  - **(3) Từ Chối Yêu Cầu/Đích Đến Native Fallback Trong HarnessExecutionResult**: Dataclass `HarnessExecutionResult` từ chối `fallback_required=True` và từ chối các đích đến native fallback (`antigravity_native`, `antigravity`, `native`); quy định mặc định `fallback_required=False` và `fallback_target="none"`.
  - **(4) Thu Hồi/Fence Tài Nguyên An Toàn Khi Harness Lỗi Không Gây Đột Biến Candidate**: Bổ sung phương thức `handle_harness_failure` trên `OrcaDeliveryAdapter`, lập tức giải phóng toàn bộ active mutation lease, settle dispatch attempt và chuyển task state sang `blocked` mà không thực hiện bất kỳ mutation nào trên git candidate tree, đòi hỏi phục hồi từ Control hoặc can thiệp của con người.
  - **(5) Fixture Suite Tự Động 176/176 PASS**: Bổ sung 7 bài kiểm tra phản ví dụ và kiểm chứng độc lập trong `TestSolRoundTenCounterexamples` thuộc `test_negative_fixtures.py`, nâng tổng số test lên 176/176 passed 100%.

## 2026-09-29 — Khắc phục toàn bộ phát hiện Sol review vòng 9 (Declared Wrapper HEAD Semantics, Rejection of all-HEAD^ Bypass & Routing Separation)

- Khắc phục toàn diện phát hiện/blocker từ `cx/gpt-5.6-sol` round 9 review cho bundle `docs/parallel-delivery/`:
  - **(1) Loại Trừ Dứt Điểm Bypass Attestation Tuple `candidate=wrapper=parent=HEAD^`**: `check_attestation_report_freshness` từ chối fail-closed cấu trúc bypass khi cả 3 trường `candidate_commit`, `wrapper_commit` và `parent_commit` đều trỏ về `HEAD^`, bảo toàn nghiêm ngặt contract `parent-plus-wrapper` vốn đòi hỏi wrapper commit phải là exact current `HEAD`.
  - **(2) Ngữ Nghĩa Declared Wrapper HEAD Không Tự Quy Chiếu SHA Vòng Lặp**: Trong `.validation-report.json`, trường `wrapper_commit` hỗ trợ khai báo tượng trưng `"HEAD"` (hoặc `"git:HEAD"`) hoặc exact 40-hex SHA khớp checkout HEAD; validator suy ra `effective_wrapper` từ runtime Git, kiểm chứng quan hệ cây `effective_wrapper^ == parent_commit` và khớp toàn bộ mã băm `bundle_sha256` mà không gặp nghịch lý tự tham chiếu SHA trong Git DAG.
  - **(3) Phân Tách Rõ Ràng Model và Effort trong Dely và Tài Liệu**: Khóa route review thành Claude Code / `cx/gpt-5.6-sol` / `high`, tách riêng hai trường `model` và `effort`, loại bỏ slug gộp không hợp lệ `cx/gpt-5.6-sol-high`; đồng bộ `validate.py`, `task-dag.yaml`, `operating-model.md`, `protocol.md`, `README.md`, `CHANGELOG.md` và `HANDOFF.md`.
  - **(4) Fixture Suite Tự Động 169/169 PASS**: Bổ sung 4 bài kiểm tra phản ví dụ độc lập trong `TestSolRoundNineCounterexamples` thuộc `test_negative_fixtures.py` (tái hiện chính xác bypass trên SHA `a7f5aca` và test trên current checkout), nâng tổng số test lên 169/169 passed 100%.

## 2026-09-29 — Khắc phục toàn bộ phát hiện Sol review vòng 8 (Atomic Terminal/Rewind Prevention, Exact Git Topology Freshness & Compound Mutation)

- Khắc phục toàn diện 3 phát hiện/blockers từ `cx/gpt-5.6-sol-high` round 8 review cho bundle `docs/parallel-delivery/`:
  - **(1) Cấm Tái Mở Trạng Thái Terminal & Cấm Tua Ngược `review`/`merge_queued` về `planned`**: Hạn chế `set_task_state` từ chối triệt để mọi nỗ lực tái mở hoặc đột biến bất kỳ tác vụ nào đã ở trạng thái terminal (`integrated`, `cancelled`, `stopped`); cấm tuyệt đối hành vi tua ngược trạng thái `review` hoặc `merge_queued` về `planned` hoặc các trạng thái pre-dispatch; toàn bộ đột biến trạng thái tác vụ được thực hiện nguyên tử qua `_task_state_lock`.
  - **(2) Xác Thực Freshness Attestation theo Đúng Cấu Trúc Cây Git DAG Cho Phép**: `check_attestation_report_freshness` từ chối fail-closed nếu báo cáo không khớp chính xác một trong hai cấu trúc topology được phép: Direct HEAD (`candidate_commit == wrapper_commit == HEAD` và `parent_commit == HEAD^`) hoặc Parent-plus-wrapper (`candidate_commit == HEAD^`, `wrapper_commit == HEAD`, `parent_commit == HEAD^`); loại bỏ hoàn toàn lỗ hổng kiểm tra quan hệ thuộc tập hợp `{HEAD, HEAD^}` lỏng lẻo; từ chối dứt điểm trường hợp candidate/wrapper thuộc commit cha (`HEAD^`) và parent thuộc `HEAD^^` khi Git HEAD đang ở commit wrapper mới.
  - **(3) Đột Biến Registry Phức Hợp Nguyên Tử Đa Tiến Trình Khi Tạo Dispatch**: `create_dispatch` thực hiện đột biến phức hợp đăng ký dispatch binding và Orca task ID thông qua `register_dispatch_and_orca_task` trong duy nhất một giao dịch nguyên tử có khóa tệp đa tiến trình `_transaction(write=True)`; cơ chế snapshot rollback tự động khôi phục hoàn toàn trạng thái in-memory và không ghi đĩa khi xảy ra lỗi/tranh chấp trùng lặp ID, bảo đảm không bao giờ để lại orphan dispatch binding tồn tại bền vững trên đĩa.
  - **(4) Fixture Suite Tự Động 165/165 PASS**: Bổ sung 3 bài kiểm tra phản ví dụ độc lập trong `TestSolRoundEightCounterexamples` thuộc `test_negative_fixtures.py`, nâng tổng số test lên 165/165 passed 100%.

## 2026-09-29 — Khắc phục toàn bộ phát hiện Sol review vòng 7 (Registry Read-Modify-Write, Durability, Lifecycle & Fencing Hardening)

- Khắc phục toàn diện 5 phát hiện/blockers từ `cx/gpt-5.6-sol-high` round 7 review cho bundle `docs/parallel-delivery/`:
  - **(1) Giao Dịch Nguyên Tử Đọc-Sửa-Ghi và Chặn Trùng Lặp ID An Toàn Tiến Trình**: Tích hợp context manager `_transaction(write=True/False)` bảo vệ chu trình đọc, sửa đổi và ghi đĩa atomic (`_persist_atomic`) trên `SharedOrcaExecutionRegistry`; nâng cấp `_FileLock` hỗ trợ reentrancy theo canonical path trên cùng một tiến trình/thread, loại bỏ nguy cơ deadlock; từ chối fail-closed `ProtocolViolationError` đối với duplicate `orca_task_id` và `dispatch_id`.
  - **(2) Shared Execution Registry Bền Vững Mặc Định khi `storage_path=None`**: Khi khởi tạo không truyền đường dẫn, registry tự động trỏ về `DEFAULT_PRODUCTION_REGISTRY_PATH` (`runtime/orca-execution-registry.json`), đảm bảo toàn bộ trạng thái task và dispatch binding được lưu vết bền vững trên đĩa và khôi phục nguyên vẹn.
  - **(3) Cấm Tuyệt Đối Can Thiệp Vòng Đời Tác Vụ qua `set_task_state`**: Hạn chế `set_task_state` chỉ cho phép gán các trạng thái khởi tạo/phụ thuộc (`planned`, `ready`, v.v.); cấm tuyệt đối việc trực tiếp gán hoặc ghi đè các trạng thái vòng đời thực thi đang hoạt động (`dispatched`, `acknowledged`, `running`, `review`, `merge_queued`, `integrated`); thuộc tính `task_states` trả về bản sao read-only dictionary để ngăn đột biến trạng thái nội bộ.
  - **(4) Xác Thực Fencing Từng Slot cho Multi-Slot Task**: `validate_fencing_token` kiểm tra toàn bộ danh sách `allocated_slots`, từ chối truy vấn slot không được cấp phát (`was not allocated`), đối chiếu chính xác token theo từng slot (`slot_fencing_tokens`), và phát hiện kịp thời các tái cấp phát bất đối xứng (`asymmetric slot reallocation detected`).
  - **(5) Từ Chối Báo Cáo Attestation Có Commit Zero Hoặc Topology Sai Lệch Git DAG**: `check_attestation_report_freshness` từ chối các commit zero SHA, commit không tồn tại trong Git DAG, và xác thực tính nhất quán cấu trúc cây Git DAG (`wrapper_commit^ == parent_commit`).
  - **(6) Fixture Suite Tự Động 162/162 PASS**: Bổ sung 9 bài kiểm tra phản ví dụ độc lập trong `TestSolRoundSevenCounterexamples` thuộc `test_negative_fixtures.py`, nâng tổng số test lên 162/162 passed 100%.

## 2026-09-29 — Khắc phục toàn bộ phát hiện Sol review vòng 6 (Process-Durable Registry & Hardened Protocol Invariants)

- Khắc phục toàn diện 7 phát hiện/blockers từ `cx/gpt-5.6-sol-high` round 6 review cho bundle `docs/parallel-delivery/`:
  - **(1) Process-Durable Shared Execution Registry**: Trang bị đường dẫn lưu trữ tường minh (`storage_path`), khóa tệp nguyên tử cross-platform (`_FileLock` dùng `os.O_CREAT | os.O_EXCL`), ghi đĩa atomic (`.tmp` + `fsync` + `os.replace`), và khôi phục sau restart tiến trình giả lập (`simulated process restart`); loại bỏ hoàn toàn registry in-memory mới ngầm trong production path thông qua `SharedOrcaExecutionRegistry.get_default()`.
  - **(2) Multi-Slot Capacity Monotonic Generation & Asymmetric Reuse Invalidation**: Mỗi slot trong capacity lock duy trì chuỗi thế hệ tăng đơn điệu riêng biệt (`fencing_counters[f"{lock_id}:slot_{s}"]`). Lease đa slot chỉ hợp lệ khi toàn bộ các slot đều giữ token hiện hành; phát hiện và từ chối fail-closed khi có tái cấp phát bất đối xứng (`asymmetric slot reallocation detected`).
  - **(3) Bắt Buộc Chu Trình Vòng Đời Tác Vụ (`ready -> dispatched -> acknowledged -> running -> worker_done`)**: Nghiêm cấm mọi hành vi bỏ qua bước ACK hoặc running; `start_running` chỉ chấp nhận trạng thái `acknowledged`, `handle_worker_done` chỉ chấp nhận trạng thái `running`.
  - **(4) Bắt Buộc Đăng Ký `declared_task_locks` & Chứng Minh Tập Hợp Lock Đầy Đủ Chính Xác**: Mọi tác vụ bắt buộc phải đăng ký `declared_task_locks` trước khi dispatch; `create_dispatch` bắt buộc chứng minh chính xác tập hợp lock yêu cầu qua `lease_ids` (`leased_locks == declared_locks`), từ chối cả missing và extraneous locks.
  - **(5) Cấm Tuyệt Đối Gán Trực Tiếp Trạng Thái Harness**: Thuộc tính `@current_state.setter` trên `HarnessExecutionStateMachine` từ chối mọi nỗ lực gán trạng thái trực tiếp (nâng `HarnessCompatibilityError`), chỉ cho phép chuyển đổi qua `transition()` hoặc `reset()`.
  - **(6) Mở Rộng Quét Secret Cho Anthropic & Provider Phổ Biến**: Bổ sung regex nhận diện token của Anthropic (`sk-ant-...`), Google/Gemini (`AIza...`), Slack (`xoxb-...`), HuggingFace (`hf_...`), Stripe (`sk_live_...`) mà không nhúng secret thật; fixtures kiểm thử tạo chuỗi động bằng ghép chuỗi.
  - **(7) Báo Cáo Attestation Freshness Với Ngữ Nghĩa Parent-Plus-Wrapper**: Thẩm định báo cáo attestation trong audit mode với tính tươi mới so với HEAD thực tế và khớp SHA-256 các tệp bundle; giải quyết vòng lặp topo Git DAG qua ngữ nghĩa commit cha chứa thay đổi bundle và commit wrapper bọc attestation.
  - **(8) Fixture Suite Tự Động 153/153 PASS**: Bổ sung 10 bài kiểm tra độc lập trong `TestSolRoundSixCounterexamples` thuộc `test_negative_fixtures.py`, nâng tổng số test lên 153/153 passed 100%.

## 2026-09-28 — Khắc phục toàn bộ phát hiện Sol review vòng 5 (Fail-Closed Blockers & Attestation Hardening)

- Khắc phục toàn diện 12 phát hiện/blockers từ `cx/gpt-5.6-sol-high` round 5 review cho bundle `docs/parallel-delivery/`:
  - **(1) Non-Skippable Fixtures & Secret Scan Gate**: Chế độ audit và release tuyệt đối cấm bỏ qua fixtures qua CLI (`--skip-fixtures`) hoặc biến môi trường (`VALIDATE_SKIP_FIXTURES`); tích hợp cổng `check_secret_scan` kiểm tra khóa riêng tư (private keys), AWS/GitHub/OpenAI API tokens, và URI credentials trên toàn bộ tệp tin thay đổi; chế độ `--release` bắt buộc cây làm việc sạch và không có secret nào.
  - **(2) Shared Durable Ledger Cho Orca Task & Dispatch ID Uniqueness**: Thêm `SharedOrcaExecutionRegistry` trừu tượng hóa việc lưu vết thực thi dùng chung giữa các thực thể adapter, đảm bảo tính duy nhất toàn cục của `orca_task_id` và `dispatch_id` trên toàn hệ thống.
  - **(3) Bắt Buộc Approved Candidate Commit Chính Xác**: Khởi tạo `OrcaDeliveryAdapter` bắt buộc phải có `approved_candidate_commit` (SHA-40 hexa); `create_dispatch` kiểm tra candidate khớp tuyệt đối với candidate đã duyệt và Git HEAD hiện hành.
  - **(4) Bắt Buộc Intended Dispatch Không Cho Phép Lease Rewrite**: `create_dispatch` yêu cầu `intended_dispatch_id` bắt buộc và phải khớp chính xác với `active_lease.dispatch_id`; cấm tuyệt đối việc ghi đè dispatch ID của lease.
  - **(5) Vòng Đời Tác Vụ Chuẩn Tắc & Chặn Chuyển Đổi Trái Phép**: Hỗ trợ chu trình đầy đủ `dispatched -> acknowledged -> running -> worker_done (succeeded/failed)` qua các phương thức `acknowledge_dispatch` và `start_running`; chặn đứng các bước nhảy trạng thái bất hợp pháp (như `acknowledged -> integrated`, `running -> ready`).
  - **(6) Dispatch Chứng Minh Đầy Đủ Tập Hợp Lock Khai Báo (`declared_task_locks`)**: Bắt buộc dispatch phải chứng minh đầy đủ lease hợp lệ cho mọi lock mà task yêu cầu, loại bỏ cơ chế chỉ chứng minh một lease đại diện.
  - **(7) Multi-Unit Capacity Slot Allocation & Fencing**: Hỗ trợ yêu cầu đa đơn vị `units > 1`, tự động phân bổ và cấp phát monotonic fencing token riêng cho từng slot trong `allocated_slots`.
  - **(8) Kiểm Tra Va Chạm Phân Vùng Đối Xứng Cha - Con**: Hàm `namespaces_overlap` kiểm tra đối xứng hai chiều qua các ký tự phân cấp (`:`, `/`, `.`), ngăn chặn hoàn toàn việc lease cha chiếm giữ tài nguyên mà lease con đang sở hữu và ngược lại.
  - **(9) Giới Hạn Gia Hạn Tích Lũy Bằng Chính Sách Khai Báo**: Mở rộng schema lock với `max_cumulative_seconds` và `max_renewals`; `renew_lease` từ chối fail-closed nếu tổng thời gian gia hạn hoặc số lần gia hạn vượt ngưỡng cho phép.
  - **(10) Giải Phóng Toàn Bộ Mutation Lease Trước Khi Vào Trạng Thái Review**: Thu hồi và giải phóng toàn bộ mutation lease trong `LeaseManager` ngay khi `worker_done(succeeded)` được xác thực, trước khi chuyển trạng thái sang `review`.
  - **(11) Khử Mâu Thuẫn Trong HarnessExecutionResult & Khóa State Machine**: Từ chối các cặp trường mâu thuẫn trong `HarnessExecutionResult` (như success=True với status="STOP" hoặc fallback_required=True); `HarnessExecutionStateMachine` từ chối gán trực tiếp trạng thái bất hợp pháp và thực thi ma trận chuyển đổi nghiêm ngặt.
  - **(12) Từ Chối ID Rỗng & Cấm Tái Chiếm Giữ Lease Cho Integrated Task**: Mọi thao tác quản lý lease từ chối chuỗi rỗng/whitespace; task đã `integrated` bị cấm tái chiếm giữ lease fail-closed.
  - **(13) Fixture Suite Tự Động 143/143 PASS**: Bổ sung 26 bài kiểm tra độc lập trong `TestSolRoundFiveCounterexamples` (`test_negative_fixtures.py`), nâng tổng số test lên 143/143 passed.

## 2026-09-28 — Khắc phục toàn bộ phát hiện Sol review vòng 4 (P1 Remediations & Counterexamples)

- Khắc phục toàn diện 9 phát hiện từ `cx/gpt-5.6-sol-high` round 4 review cho bundle `docs/parallel-delivery/`:
  - **(1) Per-Live-Allocation Fencing Cho Capacity Leases**: Phân bổ từng slot độc lập (`LOCK:slot_N`) với bộ đếm monotonic fencing token riêng cho các lock có `mode == "capacity"`, đảm bảo các worker đồng thời giữ token hợp lệ song song, và khi slot được thu hồi/cấp phát lại sẽ tự động vô hiệu hóa token cũ của worker trước.
  - **(2) Global Non-Reuse Của Orca Task ID và Dispatch ID**: Ngăn chặn tuyệt đối việc tái sử dụng `orca_task_id` và `dispatch_id` trên toàn hệ thống kể cả các attempt đã hoàn tất (`settled`).
  - **(3) Chặn Ghi Đè Dispatch Binding (Reject Duplicate Dispatch Binding Overwrite)**: Phát hiện và từ chối hành vi ghi đè lên dispatch binding đã tồn tại trong `dispatch_bindings`.
  - **(4) Ràng Buộc Candidate Commit Khớp Exact Git HEAD**: Bắt buộc candidate commit và approved candidate commit phải tồn tại trong Git DAG và khớp chính xác với `git rev-parse HEAD`.
  - **(5) Khớp Intended Dispatch Vô Điều Kiện**: Bắt buộc lease liên kết phải khớp chính xác với `intended_dispatch_id` khi được truyền; loại bỏ hoàn toàn khả năng bypass qua `ctx_init`.
  - **(6) Thực Thi Ma Trận Chuyển Đổi Trạng Thái Tác Vụ Nội Bộ (Legal Task-State Transitions)**: Xác lập bảng ma trận chuyển đổi hợp lệ `LEGAL_TASK_STATE_TRANSITIONS`, ngăn chặn mọi bước nhảy trạng thái trái phép.
  - **(7) Giải Phóng Toàn Bộ Mutation Lease Ngay Sau Worker Done Thành Công**: Đóng ngay lập tức toàn bộ mutation lease đang hoạt động khi `worker_done(succeeded)` được xác thực, chuyển tác vụ sang `review` và giữ candidate ở trạng thái read-only.
  - **(8) Từ Chối Lock Không Khai Báo và Chống Nới Rộng Thời Hạn Lease**: Thẩm định lock ID có mặt trong registry tại `acquire_lease`, `create_dispatch` và toàn bộ DAG qua `validate.py:check_task_dag`; cấm nới rộng thời hạn `lease_seconds` vượt quá định nghĩa schema.
  - **(9) Chuẩn Hóa Đối Số HarnessExecutionResult và Quan Sát Chu Trình State Machine**: Dataclass `HarnessExecutionResult` kiểm tra kiểu dữ liệu nghiêm ngặt; `HarnessExecutionStateMachine` tuân thủ chu trình `IDLE -> RUNNING -> SUCCESS | FAILURE | STOP_FALLBACK`.
  - **(10) Fixture Suite Tự Động 117/117 PASS**: Tích hợp 14 ca kiểm thử mới trong `TestSolRoundFourCounterexamples` thuộc `test_negative_fixtures.py`, nâng tổng số test lên 117/117 passed.

## 2026-09-28 — Khắc phục toàn bộ phát hiện Sol review vòng 3 (P1 Remediations)

- Khắc phục toàn diện các phát hiện Sol review vòng 3 cho bundle `docs/parallel-delivery/`:
  - **(1) Khóa Chặt Thẩm Quyền (No Authority Override)**: Loại bỏ khả năng người gọi tự truyền `authority_state` để ghi đè thẩm quyền đã đăng ký tại `acquire_lease` và `create_dispatch`; từ chối các task chưa đăng ký thẩm quyền hoặc tham số không khớp với thẩm quyền đã đăng ký.
  - **(2) Xác Thực Khởi Tạo Dispatch Nghiêm Ngặt**: Thẩm định chặt chẽ tại `create_dispatch`: task phải ở trạng thái `ready`; lease phải đang hoạt động, chưa hết hạn, thuộc đúng task, chưa bị dispatch khác gắn và fencing token khớp tuyệt đối với counter; commit candidate phải là SHA-40 hợp lệ, tồn tại trong Git DAG và khớp candidate/HEAD đã duyệt; `orca_task_id` phải không rỗng và duy nhất; các trạng thái bị khóa (`blocked`, `locked`, `future_template`, `revoked`) không được phép dispatch.
  - **(3) Kiểm Tra Vòng Đời Đa Tầng**: `handle_worker_done` kiểm tra dispatch đã settle trước khi kiểm tra trạng thái (`DuplicateResultError`); tái thẩm định quyền sở hữu lease, dispatch binding, hạn dùng (`now > expires_at`), fencing token và nhận diện Orca/candidate commit; thực thi bảng chuyển trạng thái một chiều nghiêm ngặt.
  - **(4) Review Verdict & Boolean Integration Gate**: `handle_review_verdict` từ chối mọi phán quyết lạ (chỉ nhận `approved`/`rejected`), chuyển trạng thái chính xác; `handle_integration_gates` yêu cầu boolean thuần túy (`isinstance(gates_pass, bool)`), cấm ép kiểu truthy.
  - **(5) Chuẩn Hóa Lock Schema & Chống Nới Lỏng Lease**: Thẩm định trường với `ALLOWED_LOCK_FIELDS`, từ chối kết hợp trường/chế độ bất hợp pháp (immutable có lease_seconds/renewable, exclusive có capacity), từ chối bool/fractional values cho capacity và lease_seconds; cấm nới rộng thời hạn lease vượt quá khai báo trong schema tại acquire và renew.
  - **(6) Observable Harness Execution State Machine**: Định nghĩa dataclass `HarnessExecutionResult` với kiểm tra kiểu chặt chẽ; `HarnessExecutionStateMachine` ghi nhận lịch sử chuyển trạng thái quan sát được, kích hoạt STOP condition và fallback Antigravity native tin cậy.
  - **(7) Fixture Suite Tự Động 103/103 PASS**: Thêm 24 ca kiểm thử bền vững trong `TestSolRoundThreeCounterexamples` thuộc `test_negative_fixtures.py`, nâng tổng số test lên 103/103 passed.
  - **(8) Bảo Toàn Phạm Vi**: Giữ nguyên ranh giới docs/config, không thay đổi product code hay accepted evidence.

## 2026-09-28 — Khắc phục toàn bộ 21 bypass độc lập từ Sol review và tách biệt read-only audit mode

- Khắc phục toàn diện 21 bypass độc lập và boundary probes từ Sol independent review cho bundle `docs/parallel-delivery/`:
  - **(1) Tách biệt Read-only Audit Mode & Explicit Report Generation**: Chế độ mặc định của `validate.py` là read-only audit, thẩm định toàn bộ cấu trúc và fixtures mà không sửa đổi file theo dõi trong Git, đảm bảo worktree hoàn toàn sạch sẽ. Chế độ `--generate-report` yêu cầu truyền tường minh SHA-40 bất biến cho cả `--base` và `--candidate`; `--base` phải khớp baseline đã duyệt (`4a7c8c9`), `--candidate` phải khớp chính xác `HEAD` thực tế; cấm ref name (`HEAD`), non-HEAD candidate, `base == candidate` hoặc stale pin. Tệp `.validation-report.json` mang trường `semantics` chuẩn xác tránh tự quy chiếu.
  - **(2) Lock Registry Schema & Strict Leases**: Thẩm định schema tại khởi tạo: bắt buộc ID duy nhất, mode hợp lệ, boolean `renewable`, dung lượng và thời hạn lease là số nguyên dương nghiêm ngặt, partitionable lock có `partition_key_prefix` không rỗng. Chiếm giữ lease từ chối triệt để đơn vị bool (`isinstance(True, int)`), số thực, số 0 hoặc số âm; cấm lease trùng lặp tài nguyên ngoài; gia hạn lease từ chối lock không được renew, lease hết hạn hoặc thẩm quyền bị thu hồi.
  - **(3) Quản lý Thẩm quyền Chặt chẽ (Explicit Authority)**: Thẩm quyền task bắt buộc phải được đăng ký và cấp quyền rõ ràng (`granted`), không bao giờ mặc định được cấp (`never default granted`); tái kiểm tra tại acquire, renew, dispatch, worker_done, review/merge transitions; thu hồi thẩm quyền chặn lập tức mọi chuyển trạng thái mutation.
  - **(4) Fencing Token Bất biến**: Từ chối token tương lai (`token > current counter`), loại bỏ shortcut chỉ chấp nhận hiện tại mà bỏ qua tương lai; từ chối token bị thiếu (`absent`), cũ (`stale`) hoặc lease đã hết hạn (`expired`).
  - **(5) Orca Dispatch Binding & Lifecycle**: Ràng buộc chặt chẽ exact nonblank `orca_task_id`, `candidate_commit` (SHA-40), `fencing_token` và `lease_id`; `worker_done` từ chối task ID Orca không khớp, commit mismatch, kết quả duplicate hoặc stale attempt; thực thi máy trạng thái, cấm task `locked`/`future_template`/`revoked` dispatch hay tích hợp.
  - **(6) Harness Compatibility Gate**: Ghi nhận cổng tương thích harness phát hiện hiện tượng sụp namespace công cụ (`functions.exec` -> `functions`), yêu cầu smoke test có thực thi thành công quan sát được; khi thất bại kích hoạt STOP condition (`blocked_harness`) và fallback sang Antigravity native; coi đây là dynamic runtime gate.
  - **(7) Fixture Suite Tự động 79/79 PASS**: Bổ sung bộ 21 probes đối kháng cùng boundary probes trong `TestSolTwentyOneIndependentProbes` (`test_negative_fixtures.py`), chạy độc lập không đệ quy và đạt 100% PASS.
  - **(8) Bảo Toàn Phạm Vi**: Giữ nguyên toàn bộ ranh giới docs/config, không đụng vào product code hay accepted evidence.

## 2026-09-28 — Khắc phục sáu findings Astra audit round 1 và bổ sung negative fixtures

- Khắc phục toàn bộ 6 findings từ Astra audit round 1 cho bundle `docs/parallel-delivery/`:
  - **F1 (Exact contract binding)**: Khóa chặt từng contract ID với registry/source/owner/hash xác định; `CT-AI-ROUTE-*` thuộc về `CONTRACT-CONFIG-SECURITY` (owner `J`), tách biệt khỏi `CONTRACT-CREATIVE-AI` (owner `D`); từ chối wrong-registry và wrong-source hash fail-closed.
  - **F2 (Ownership & path safety)**: Cấm tuyệt đối đường dẫn tuyệt đối, path traversal (`..`), và alias chuẩn tắc (`./`, `//`, `\`); kiểm tra tập giao rỗng giữa `owned_paths` và `forbidden_paths`; bảo vệ `LOCK-ACCEPTED-EVIDENCE` và evidence lịch sử bất biến, từ chối mọi mutation lease.
  - **F3 (Scope check & committed delta)**: Pin approved base commit `4a7c8c9` và candidate commit; kiểm tra đồng thời committed diff và dirty/untracked overlay; kiểm tra rename cả hai đầu (old path & new path); đối chiếu bảo toàn hash evidence bất biến; từ chối forbidden committed delta.
  - **F4 (Orca mapping & lifecycle)**: Phân định rõ ràng Delivery Ledger Task ID khỏi Orca execution Task/Dispatch/Run ID; chuẩn hóa CLI `worker_done` chỉ chấp nhận `--outcome succeeded|failed` để giải quyết attempt; định nghĩa `OrcaDeliveryAdapter` điều phối `succeeded → review → integrated`, `failed → blocked/needs_replan → fresh dispatch`; từ chối kết quả trùng lặp hoặc mang fencing token cũ.
  - **F5 (Readiness & traceability)**: Thẩm định toàn bộ references thật (`authority_refs`, `module_owners`, `invariant_refs` INV-001..020, `requirement_refs`, `contract_refs`); từ chối fake IDs; thực thi predicate readiness (chặn locked/future_template chuyển sang ready; cấm red_observation rỗng hoặc mang giá trị `unknown`).
  - **F6 (Locks & leases)**: Tách bạch khai báo lock khỏi active lease; task ở trạng thái `integrated` giải phóng toàn bộ active lease và không chặn task mới; hỗ trợ phân vùng database (`exclusive_by_database_name`), cấp phát đồng thời cho namespace tách rời và xung đột khi trùng namespace; áp dụng hạn mức capacity; cấp phát fencing token tăng đơn điệu.
- Thêm `delivery_engine.py` và suite 34 test tự động trong `test_negative_fixtures.py` kiểm chứng toàn diện mọi counterexample của Astra và các positive cases tương ứng; tích hợp trực tiếp vào `validate.py` và `.validation-report.json`.

## 2026-09-28 — Đề xuất kiến trúc triển khai song song có kiểm soát

- Thêm bundle `docs/parallel-delivery/` gồm operating model, task DAG, contract registry, ownership/resource lease, worker protocol, merge queue, traceability và guardrail security/performance/recovery có thể kiểm tra bằng máy. Đây chỉ là `PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY`; không triển khai M2-P8/P9, không mở M3/Phân hệ A hoặc milestone sau, và không sửa accepted/rejected evidence.
- Khôi phục `AGENTS.md` về UTF-8 tiếng Việt hợp lệ; khóa Dely implement thành Codex CLI / `ag/gemini-3.8-flash-high` / `high`, review thành Claude Code / `cx/gpt-5.6-sol-high` / `high`, giữ supreme audit `cx/gpt-6-astra-medium` / `medium` bên ngoài Dely. Thêm `CLAUDE.md` import `@AGENTS.md` để Claude Code nhận cấu hình.
- Đồng bộ README, roadmap, checklist và handoff với thiết kế docs/config-only; tham chiếu rollback `D:/AI_SETUP/backups/AI-Auto-Video-Creator/20260928-175542`. Toolchain, source, tests, SQL, runtime và lockfiles không đổi.

## 2026-09-17 — M2-P7B accepted và đóng lifecycle

- Independent review chấp thuận P7B implementation tại source/tooling `c44214ad027986a0db7cb9d8e221590f232a0036` và GREEN `run-m2-p7b-green-20260917040648`; lifecycle hiện hành `M2-P1..P7B_ACCEPTED_CLOSED`. Migration `0008`, ngoại lệ đúng thân P3 `PostgresOperationStreamRepository.append()` và compatibility đúng thân P7A hardening H16 thuộc kết quả được chấp thuận. Oracle P7B/P7A, accepted evidence và candidate GREEN cũ bị từ chối đều giữ bất biến. Checkpoint này chỉ sửa tài liệu; P8/P9 vẫn khóa, M3/Phân hệ A `NOT AUTHORIZED`.

## 2026-09-17 — M2-P7B narrow review correction ready for independent review

- Review từ chối ACCEPT/CLOSE candidate `1578d3e`/`run-m2-p7b-green-20260917024918` vì thiếu H38 P1 UoW rollback độc lập, sequence `CACHE=1`, H16 HTTPS capacity 16+1 và exact H01–H38 profile lock; mã `STREAM_CAPACITY_EXCEEDED` ngoài contract. Candidate evidence cũ giữ nguyên; đây không phải behavioral rollback.
- Source/tooling correction `c44214ad027986a0db7cb9d8e221590f232a0036` chỉ đổi helper ProblemDetail SSE, H16/H38, sequence/capacity probe và semantic profile. Saturation trả `429 RATE_LIMITED`, category `capacity`, retryable; H38 quan sát T2 chờ lock trước cấp cursor khi P1 UoW rollback, sau đó chỉ row M commit. H16 giữ 16 stream thực qua HTTPS, từ chối kết nối thứ 17 và xác nhận slot được trả lại. Profile khóa exact 38 tên, 16 client/3 poll và PostgreSQL `CACHE=1`.
- Fresh GREEN `run-m2-p7b-green-20260917040648`: P7B 5/5 + 38/38; P7A 4/4 + 36/36; P6/P5B/P5A/P4/P3/P2/P1/P0/architecture/M1 đều đạt, 0 failed/error/skipped. Migration/index 0008 `[1..8] → [1..7] → [1..8]`, 100.000 rows, EXPLAIN PASS; Ruff/lock/wheel PASS, mypy không có trong lock, secret scan CLEAN/0, semantic/provenance/hash/tamper PASS. Chỉ `READY_FOR_REVIEW`, chưa accepted/closed; P8/P9, M3 và Phân hệ A vẫn khóa.

## 2026-09-17 — M2-P7B implementation ready for independent review

- Source/tooling `1578d3e38bee60f42d81cef4a395af414752777a` triển khai SSE bounded workspace stream, P3 one-statement ordering fence, migration/index `0008`, H01–H38 và ngoại lệ compatibility đúng thân P7A H16. P7A/P7B Behavioral oracle và historical accepted evidence giữ nguyên; H16 bỏ giả định 0007 luôn là migration cuối.
- Fresh GREEN `run-m2-p7b-green-20260917024918`: P7B 5/5 + H01–H38 38/38; P7A 4/4 + 36/36; P6/P5B/P5A/P4/P3/P2/P1/P0/architecture/M1 đều đạt đúng số lượng, 0 failed/error/skipped. Migration 0008 `[1..8] → [1..7] → [1..8]`, EXPLAIN composite index trên 100.000 rows, Ruff/lock/wheel PASS, mypy không có trong lock, secret scan CLEAN/0, semantic/provenance/hash/tamper PASS. Chỉ `READY_FOR_REVIEW`, chưa accepted/closed; P8/P9, M3 và Phân hệ A vẫn khóa.

## 2026-09-17 — M2-P7B P7A tracker compatibility delta accepted

- Independent review checkpoint `1cbdcf1d2fc245d3d1515c8864fc6a3d8e377bc9` cho phép sửa **chỉ thân** P7A hardening H16 để kiểm migration set hiện hành liên tục và rollback/reapply migration mới nhất, thay giả định cũ 0007 luôn là cuối. P7A Behavioral oracle/source/evidence lịch sử không đổi; H15 và các H01–H36 khác bất biến. Full 36/36 trên schema gồm 0008 là gate ngay trước khi tiếp tục P7B; P8/P9, M3/Phân hệ A vẫn khóa.

## 2026-09-17 — M2-P7B dừng tại xung đột accepted P7A tracker oracle

- Migration `0008` được cấp quyền làm accepted P7A hardening `test_h16_migration_tracker` fail: expected tracker `[1..7]`, observed `[1..8]` (35/36). P7B oracle targeted 5/5 và các proof index/fence targeted đã chạy, nhưng source/migration/test P7B giữ unstaged/uncommitted, chưa có final GREEN evidence hoặc source pin. Không sửa P7A oracle; chờ independent review quyết định gate tương thích migration.

## 2026-09-17 — M2-P7B index authority delta accepted

- Independent review checkpoint `aed557f5269f0af7641197d9b662b2dcff5e8d65` chấp nhận blocker PK-only và cho phép đúng migration `0008_operation_stream_workspace_cursor_index` tạo B-tree `(workspace_id, stream_event_id)` cùng rollback chỉ drop index. Không cho phép `CREATE INDEX CONCURRENTLY`, migration khác, sửa `MigrationRunner` hoặc thay accepted RED oracle/evidence. P7B implementation tiếp tục nhưng chưa GREEN/accepted/closed; P8/P9, M3/Phân hệ A vẫn khóa.

## 2026-09-17 — M2-P7B RED accepted, implementation authorized

- Independent review chấp nhận immutable RED source/test `c35571fb334dc7b842ee23378f041e74f1caa277`, oracle SHA-256 `d83d0f2d808f1b0067d5288ea131ded24d8fc46a16462b5254fd4167f7425738` và evidence `run-m2-p7b-red-20260917002633`. Rejected historical RED `run-m2-p7b-red-20260917000606` giữ bất biến. Chỉ mở quyền implementation P7B, chưa chấp nhận/đóng P7B; P8/P9, M3/Phân hệ A vẫn khóa.

## 2026-09-17 — Hiệu chỉnh M2-P7B Behavioral RED oracle #001

- Independent review từ chối ứng viên RED `run-m2-p7b-red-20260917000606`: #001 dùng no-cursor initial subscribe nhưng đòi phát lại row cũ, trái baseline committed MAX. Run cũ giữ bất biến. Chỉ sửa `tests/m2/test_p7b_sse_stream.py` tại source commit `c35571fb334dc7b842ee23378f041e74f1caa277`: seed C/N và resume explicit `?cursor=C`; dùng P7A app qua loopback HTTPS, CA verification, session DB thật, `httpx` streaming tới frame hoàn chỉnh rồi disconnect.
- Fresh RED `run-m2-p7b-red-20260917002633` có 5/5 failure đúng seam, #000 race tái hiện 3 lần; P7A 4/4 + 36/36, P3 11/11, architecture 6/6, P6→P0 PASS, M1 `NOT_RUN`, PG18.6/orphan=0. P7B RED chỉ `READY_FOR_REVIEW`; implementation/P3 fence vẫn khóa, không migration `0008` hay dependency pin drift.

## 2026-09-17 — M2-P7B Behavioral RED ready for independent review

- Independent review checkpoint `763aa63b` chấp nhận authority; commit docs-only `ef6639d` mở riêng Behavioral RED. Source/test/seam `7fa928b1f715a66b0d5a579c2530884598ed482d` tạo đúng năm oracle, không triển khai GREEN hay sửa accepted P3 writer.
- Fresh evidence `run-m2-p7b-red-20260917000606`: collect 5, 5 failed/0 passed/0 errors/0 skipped; #000 tái hiện ba lần T1 N=1 commit muộn sau T2 M=2 và replay `>2` bỏ N; #001–#004 fail đúng capability seam. P7A oracle 4/4, hardening 36/36, P3 11/11, architecture 6/6 và P6→P0 PASS; PostgreSQL 18.6, orphan=0, secret scan CLEAN/0. P7B RED chỉ `READY_FOR_REVIEW`; implementation vẫn khóa.

## 2026-09-17 — M2-P7B autocommit-compatible ordering authority, docs-only

- Review checkpoint `25e7f2488d8298be08816bd2147315b4677eb442` phát hiện accepted P3 #011 append trên autocommit connection. Rút lại two-statement transaction fence và autocommit fail-closed wording; future exact `PostgresOperationStreamRepository.append()` exception phải dùng **một SQL statement** gồm materialized ordering fence → dependent explicit sequence allocation → INSERT/RETURNING, tương thích cả autocommit và P1 UoW. CTE là intended shape, runtime proof còn bắt buộc.
- Exact five-case RED giữ nguyên (#000 `UPSTREAM_INVARIANT_RED` trước fix); thêm H38 P3 autocommit/UoW compatibility, future catalogue H01–H38 count=38; accepted P3 full 11/11 và #010/#011 là hard gate. Không sửa source/test/migration/evidence, không tạo P7B RED hoặc `0008`. Lifecycle P7A accepted, P7B authority draft chờ review và RED/implementation vẫn LOCKED.

## 2026-09-17 — M2-P7B commit-order authority correction, docs-only

- Independent review checkpoint `a60471af2ab03978e6a88657dbec62a43b82da0c` chọn hướng B: future per-workspace transaction ordering fence trước `stream_event_id` allocation, với exact accepted-P3 exception chỉ trong `PostgresOperationStreamRepository.append()`. Khóa inventory writer, RED #000 upstream invariant trên hai PostgreSQL transactions thật và future exact 5-case RED; không sửa source/test/migration/evidence tại checkpoint này.
- Sửa `minimum_available_cursor` thành oldest resumable cursor C (`==C` replay exclusive, `<C` resync rồi close), khóa classification order, first-subscribe workspace-visible high-water và H37 GREEN proof độc lập. Index `(workspace_id, stream_event_id)` vẫn conditional STOP gate; không tạo `0008`. P7B `AUTHORITY_READY_FOR_REVIEW`, RED/implementation tiếp tục LOCKED; P7A `ACCEPTED_CLOSED` bất biến.

## 2026-09-17 — M2-P7A accepted; P7B authority/design draft ready for review

- Independent review chấp thuận/đóng P7A correction source/tooling `6c3a52bde905ee5e71e12334da1873ed20f5c5db` và GREEN `run-m2-p7a-green-20260916224033`; accepted/rejected historical evidence giữ byte-exact, không chạy lại. Lifecycle `M2-P1..P7A_ACCEPTED_CLOSED`.
- Khóa docs-only exact future P7B scope, FastAPI composition, cursor/SSE/reconnect/resync, watermark, connection/backpressure, RED identities, hardening và evidence rules. P7B `AUTHORITY_READY_FOR_REVIEW`, Behavioral RED/implementation vẫn `LOCKED`. Open STOP gate: P3 `BIGSERIAL` chưa bảo đảm commit-order/no-loss dưới concurrent writers; cần independent review/authority riêng, không sửa P3 hoặc tạo `0008` trong checkpoint này. P8/P9, M3 và Phân hệ A vẫn khóa.

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
## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau 982ed1e (Wildcard ControlCapability Rejection in Evidence Issuers & Capability Verification)

- Khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate 982ed1e9264444b00ed13736466f6923255d1b7b cho bundle docs/parallel-delivery/:
  - **(1) Từ Chối Wildcard ControlCapability Tại Các Bề Mặt Phát Hành Bằng Chứng (Wildcard ControlCapability Rejection in Evidence Issuers)**: Các hàm `issue_review_evidence()` và `issue_integration_evidence()` trên cả `EvidenceAuthority` và `OrcaDeliveryAdapter` từ chối fail-closed mọi capability có `delivery_task_id` là `None` hoặc `"*"` (wildcard) cũng như mismatched task ID. Chỉ có capability mang phạm vi tác vụ cụ thể (`delivery_task_id` khớp chính xác với task được yêu cầu) mới được phép phát hành bằng chứng ký số thẩm quyền (`ReviewEvidence`, `IntegrationEvidence`).
  - **(2) Khóa Chặt `verify_capability()` Trước Wildcard Khi Có Yêu Cầu Task Cụ Thể (Hardened verify_capability Against Wildcard Capabilities)**: Phương thức `verify_capability()` kiểm tra nghiêm ngặt khi `expected_task_id` được chỉ định (khác `None` và khác `"*"`): từ chối fail-closed ngay lập tức nếu `capability.delivery_task_id` là `None` hoặc `"*"`, ngăn chặn triệt để lỗ hổng cho phép wildcard capability vượt qua xác thực cho một task cụ thể bất kỳ.
  - **(3) Chuẩn Hóa Toàn Bộ Helper Fixture Và Positive Controls Độc Lập**: Cập nhật toàn bộ các fixture kiểm thử phát hành bằng chứng hợp lệ (`_issue_valid_review_evidence`, `_issue_valid_integration_evidence`, `test_f4`, `test_r3_16`, `test_r4_09`, `test_36092d0_06..08`) truyền tường minh `delivery_task_id` khi mint `ControlCapability`, đảm bảo 100% tuân thủ bất biến fail-closed task-scoped.
  - **(4) Bộ Fixture Phân Biệt Tự Động 338/338 Tests PASS**: Bổ sung lớp kiểm thử `TestSolLeadAudit982ed1eRemediation` với 5 bài test độc lập (tái hiện 4 counterexamples: từ chối wildcard trên `EvidenceAuthority.issue_integration_evidence`, `issue_review_evidence`, `verify_capability`, và bề mặt callable của `OrcaDeliveryAdapter`; kèm 1 positive control toàn trình), nâng tổng số test lên 338/338 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau 1f90e6c (Hạn chế issue_review_evidence chỉ nhận ReviewerCapability & bảo toàn ranh giới Independent Review)

- Khắc phục triệt để phát hiện blocker từ Sol-Lead audit trên exact candidate 1f90e6cfd3d3ed829acf20fddd53e3c56fe90f8b cho bundle docs/parallel-delivery/:
  - **(1) Hạn Chế Tuyệt Đối `issue_review_evidence()` Chỉ Nhận `ReviewerCapability` (Review Evidence Issuance Strictly Restricted to ReviewerCapability)**: Loại bỏ hoàn toàn khả năng sử dụng `ControlCapability` (kể cả có task-scoped) để phát hành `ReviewEvidence` trên cả `EvidenceAuthority` và `OrcaDeliveryAdapter`. Bất kỳ yêu cầu phát hành bằng chứng review nào không mang đúng kiểu `ReviewerCapability` hợp lệ đều bị từ chối fail-closed bằng `ProtocolViolationError`, ngăn chặn triệt để hành vi Control tự phát hành review evidence để bỏ qua ranh giới independent review.
  - **(2) Siết Chặt Ranh Giới Xác Thực Quyền Hạn Trong `verify_capability()` (Strict Role Enforcement for Reviewer)**: Khi thẩm định capability trong `issue_review_evidence()`, truyền tường minh `expected_role="Reviewer"` vào `verify_capability()`, từ chối ngay lập tức mọi `ControlCapability` hoặc capability sai vai trò với thông báo lỗi phân biệt rõ ràng.
  - **(3) Bảo Toàn Thẩm Quyền Hợp Lệ Của Control Và Bằng Chứng Tích Hợp (Preserved Valid Control Authority & Integration Evidence)**: Quyền hạn của `ControlCapability` trong việc cấp phát `ReviewerCapability` thông qua `issue_reviewer_capability()` / `get_reviewer_capability()` và quyền phát hành `IntegrationEvidence` thông qua `issue_integration_evidence()` được bảo toàn nguyên vẹn, không có bất kỳ sự hồi quy nào.
  - **(4) Bộ Fixture Phân Biệt Tự Động 343/343 Tests PASS**: Bổ sung lớp kiểm thử `TestSolLeadAudit1f90e6cRemediation` với 5 bài test độc lập (tái hiện 4 counterexamples: từ chối task-scoped `ControlCapability` trên `EvidenceAuthority.issue_review_evidence`, trên `OrcaDeliveryAdapter.issue_review_evidence`, ngăn chặn bypass độc lập chuyển sang `merge_queued`, và kiểm tra `verify_capability` từ chối sai role; kèm 1 positive control toàn trình chứng minh cả review và tích hợp hoàn tất sạch sẽ), nâng tổng số test lên 343/343 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau 569f0d1 (Separation of Duties for Review Dispatch & Authenticated ReviewerContext)

- Khắc phục triệt để phát hiện blocker kiến trúc từ Sol-Lead audit trên exact candidate 569f0d17a359dca96e3e03a359facc8bef790dc8 cho bundle docs/parallel-delivery/:
  - **(1) Tách Rời Hoàn Toàn Dispatch Creation Khỏi Capability Delivery (Complete Decoupling of Dispatch Creation from Capability Delivery)**: `create_review_dispatch()` chỉ trả về `dispatch_id: str` thuần túy; tuyệt đối không trả bearer token (`reviewer_auth_token`) hay `ReviewDispatchHandle` cho caller tạo dispatch.
  - **(2) Loại Bỏ Lưu Trữ Token Khỏi Control Plane (Removal of Reviewer Token Storage from Control Plane)**: Xóa bỏ hoàn toàn dictionary `_reviewer_auth_tokens` trên `OrcaDeliveryAdapter`, bảo đảm Control plane không thể đọc, giữ, hoặc trích xuất auth token của reviewer.
  - **(3) Ràng Buộc Claim ReviewerCapability Với ReviewerContext Đã Xác Thực (Binding ReviewerCapability Claims to Authenticated ReviewerContext)**: Thêm dataclass `ReviewerContext` đóng gói đầy đủ ngữ cảnh của kiểm định viên (`delivery_task_id`, `review_dispatch_id`, `orca_task_id`, `terminal_id`, `reviewer_principal="cx/gpt-5.6-sol"`, `harness="Claude Code"`, `session_id`). Thao tác claim capability bắt buộc phải cung cấp `ReviewerContext` hợp lệ; cấm truy xuất trần (bare retrieval); cấm Control authority claim hoặc issue review evidence.
  - **(4) Bộ Fixture Phân Biệt Tự Động 364/364 Tests PASS**: Bổ sung suite kiểm thử `TestSolRemediationSeparationOfDuties` với 6 bài test độc lập chứng minh Separation of Duties chặt chẽ (dispatch creator không thể claim capability hay issue ACCEPT; context giả mạo bị từ chối fail-closed; positive control trong ReviewerContext độc lập hoàn tất chuyển trạng thái `merge_queued`), nâng tổng số test lên 364/364 passed 100%.
  - **(5) Khắc Phục Lỗi Whitespace Và Hiển Thị Tiếng Việt**: Sửa toàn bộ 5 lỗi whitespace tại `CHANGELOG.md:589`, `docs/parallel-delivery/README.md:3-4`, `docs/parallel-delivery/protocol.md:329` và `docs/parallel-delivery/test_negative_fixtures.py`, đồng thời khôi phục tiếng Việt đầy đủ dấu tại `HANDOFF.md`.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau 82efe33 (Reviewer Session Boundary, Elimination of Reviewer Channels from Adapter, and Opaque Single-Use Session Proofs)

- Khắc phục triệt để phát hiện blocker kiến trúc từ Sol-Lead audit trên exact candidate `82efe33a88a37616347517a5d8a5481c3a69bc29` cho bundle `docs/parallel-delivery/`:
  - **(1) Chuyển Capability Delivery Sang Ranh Giới Do Reviewer Session Sở Hữu (Reviewer Session Boundary Ownership)**:
    - Triển khai `ReviewerSessionBoundary` quản lý độc lập việc cấp phát `ReviewerCapability`, tách biệt hoàn toàn khỏi Control plane và state hiển thị trên `OrcaDeliveryAdapter`.
    - Xóa bỏ triệt để thuộc tính `_reviewer_delivery_channels` khỏi `OrcaDeliveryAdapter`. Adapter không còn lưu giữ channel, bearer token hay reviewer capabilities trong state có thể đọc bởi Control.
    - Xóa bỏ hoàn toàn property `reviewer_auth_token` khỏi `ReviewerDeliveryChannel`.
  - **(2) Bắt Buộc Opaque Single-Use Reviewer-Session Proof Có Chữ Ký Mật Mã (Mandatory Opaque Single-Use ReviewerSessionProof)**:
    - Triển khai dataclass `ReviewerSessionProof` mang token ngẫu nhiên và chữ ký HMAC bí mật do `ReviewerSessionBoundary` sở hữu (`_boundary_secret`).
    - Proof được bind chặt chẽ với: `delivery_task_id`, `review_dispatch_id`, `orca_task_id`, `terminal_id`/`session_id`, `candidate_commit`, `reviewer_route` ("cx/gpt-5.6-sol"), và `reviewer_harness` ("Claude Code").
    - Thao tác phát hành proof (`issue_session_proof`) yêu cầu `reviewer_secret` hợp lệ; nghiêm cấm Control authority phát hành proof (`control_capability` hoặc `control_secret` bị từ chối fail-closed).
  - **(3) Chặn Đứng Tự Dựng Context Bằng Public Identifiers & Chống Giả Mạo / Replay (Rejection of Self-Constructed Contexts, Forgery, and Proof Replay)**:
    - `ReviewerDeliveryChannel.claim_capability()` bắt buộc phải có `ReviewerSessionProof` đã được xác thực; từ chối fail-closed nếu caller tự dựng `ReviewerContext` chỉ bằng các định danh công khai (public IDs).
    - Kiểm tra và tiêu thụ proof nguyên tử dưới khóa; từ chối fail-closed mọi nỗ lực tái sử dụng (replay) proof đã tiêu thụ hoặc phát hành trùng lặp proof cho cùng một review dispatch.
    - `OrcaDeliveryAdapter.claim_reviewer_capability()` từ chối fail-closed nếu caller cung cấp token cũ (`reviewer_auth_token`).
  - **(4) Bộ Fixture Phân Biệt Tự Động 367/367 Tests PASS**:
    - Mở rộng suite `TestSolRemediationSeparationOfDuties` lên 9 bài test: chứng minh dispatch creator có đủ 7 public IDs vẫn không thể claim capability (`test_sod_06`), caller không thể đọc token/channel từ adapter và không thể giả mạo proof hay dùng Control authority để issue proof (`test_sod_07`), thực thi nghiêm ngặt single-use proof và cấm duplicate issuance (`test_sod_08`), và positive control độc lập với `self.reviewer_secret` hoàn tất toàn bộ vòng đời đến `integrated` (`test_sod_09`).
    - Nâng tổng số test lên 367/367 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau 8ceacb4 (Elimination of Literal Credential from Production Module, Trusted Host Boundary Handoff Creation, and Ordinary Caller Handoff Prevention)

- Khắc phục triệt để phát hiện blocker kiến trúc từ Sol-Lead audit trên exact candidate `8ceacb41aeb67bbfd1f644b9e252df1db12f58e2` cho bundle `docs/parallel-delivery/`:
  - **(1) Loại Bỏ Triệt Để Literal Credential và Vault Khỏi Production Module (`delivery_engine.py`)**:
    - Xóa bỏ hoàn toàn kho lưu trữ `_HOST_HANDOFF_VAULT` và literal credential `test_fixture_reviewer_secret_32b_hex!` khỏi `docs/parallel-delivery/delivery_engine.py`.
    - Production module không chứa bất kỳ literal reviewer secret hay cơ chế lưu trữ credential mặc định nào; candidate caller không thể inspect hay exfiltrate credential đã biết.
  - **(2) Chuyển Việc Tạo Handoff và Credential Hoàn Toàn Ra Trusted Host Boundary (`TrustedHostReviewerHandoff`)**:
    - Chuyển toàn bộ logic khởi tạo handoff authority và credential sang lớp `TrustedHostReviewerHandoff` trực thuộc test harness / trusted host boundary trong `docs/parallel-delivery/test_negative_fixtures.py`, nằm ngoài phạm vi callable hay importable của candidate code.
    - Lớp cơ sở `ReviewerHostHandoff` trong `delivery_engine.py` từ chối fail-closed mọi nỗ lực khởi tạo trực tiếp không đối số hoặc có đối số từ caller cùng tiến trình (`__init__` raise `ProtocolViolationError`).
    - Ngăn chặn triệt để hành vi kế thừa trái phép: `__init_subclass__` từ chối fail-closed nếu subclass được định nghĩa trong `delivery_engine` hoặc `__main__`.
    - Phương thức `ReviewerSessionBoundary.provision_from_host()` kiểm tra nghiêm ngặt: từ chối fail-closed nếu authority được khởi tạo trong module candidate hoặc `__main__`, và yêu cầu credential tiêu thụ phải là `bytes` không rỗng hợp lệ.
  - **(3) Bộ Fixture Phân Biệt Tự Động 375/375 Tests PASS**:
    - Bổ sung `test_sod_17_fresh_process_ordinary_caller_cannot_construct_handoff_or_provision_boundary` tái hiện chính xác counterexample của Sol audit trong tiến trình con mới: khẳng định caller thông thường trong tiến trình mới không thể tự tạo `ReviewerHostHandoff`, không thể subclass, không thể gọi `provision_from_host()`, không có literal credential trong production module, `HANDOFF_PROVISIONED=False` và `KNOWN_CREDENTIAL=False`, default boundary giữ nguyên `_reviewer_secret = None`, và không thể mint proof/context.
    - Cập nhật `test_sod_16` kiểm tra khởi tạo `ReviewerHostHandoff` trực tiếp bị từ chối fail-closed ngay lập tức.
    - Nâng tổng số test lên 375/375 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau 6731c15 (Unforgeable Host Issuer Capability, Outside Module Subclass Rejection, and Cryptographic Provenance Binding)

- Khắc phục triệt để phát hiện blocker kiến trúc từ Sol-Lead audit trên exact candidate `6731c156e09b06f991a1ed523f318c0c24c0005b` cho bundle `docs/parallel-delivery/`:
  - **(1) Loại Bỏ Hoàn Toàn Kiểm Tra Dựa Trên Tên Module & Chặn Đứng Subclass Ngoài Luồng (Elimination of Module-Name Checks & Outside Module Subclass Rejection)**:
    - Loại bỏ hoàn toàn cơ chế kiểm tra tin cậy dựa trên tên module `cls.__module__ in ("delivery_engine", "__main__")`.
    - `ReviewerHostHandoff.__init_subclass__` từ chối fail-closed vô điều kiện mọi nỗ lực subclass hóa trên toàn bộ các module (kể cả module ngoài như `attacker_module`), ngăn chặn triệt để lỗ hổng định nghĩa subclass ngoài luồng để override `_consume_for_provisioning()`.
    - `ReviewerSessionBoundary.provision_from_host()` bắt buộc `type(authority) is ReviewerHostHandoff`, từ chối fail-closed mọi subclass từ bất kỳ module nào.
  - **(2) Ràng Buộc Handoff Vào Thẩm Quyền Host Issuer Với Chữ Ký HMAC Không Thể Giả Mạo (Cryptographic Provenance Binding via Unforgeable ReviewerHostIssuerCapability)**:
    - Triển khai dataclass frozen `ReviewerHostIssuerCapability` mang chữ ký HMAC bí mật không thể làm giả và định danh gắn kết `handoff_id`.
    - Triển khai thẩm quyền host `ReviewerHostIssuer` độc lập bên ngoài, quản lý việc phát hành handoff dùng một lần duy nhất (`_minted`), xác thực chữ ký mật mã HMAC-SHA256 và tiêu thụ token nguyên tử (`verify_and_consume_capability`).
    - Caller thông thường trong tiến trình tuyệt đối không thể tự khởi tạo `ReviewerHostIssuer` (từ chối fail-closed nếu thiếu `_internal_token`).
    - `ReviewerSessionBoundary.provision_from_host()` bắt buộc authority phải mang `ReviewerHostIssuerCapability` hợp lệ do `ReviewerHostIssuer` cấp phát, thẩm định chữ ký và tiêu thụ nguyên tử trước khi tiếp nhận credential.
  - **(3) Bộ Fixture Phân Biệt Tự Động 376/376 Tests PASS**:
    - Bổ sung `test_sod_18_outside_module_attacker_handoff_rejected_cannot_bypass_boundary` tái hiện chính xác counterexample của Sol audit trong tiến trình con mới: kiểm thử toàn diện việc từ chối subclass ở module ngoài, từ chối dynamic subclass qua `type()`, từ chối tự khởi tạo host issuer, từ chối unauthenticated object, từ chối raw instance thiếu capability, từ chối capability giả mạo chữ ký, xác nhận boundary giữ nguyên unprovisioned và cấm mint proof; đồng thời kiểm thử positive control với authentic host handoff hoàn tất provisioning và thực thi nghiêm ngặt single-use.
    - Nâng tổng số test lên 376/376 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau a286e6d (Elimination of In-Process Environment Variable Provisioning, Mandatory ReviewerHostHandoff Authority, and Caller-Set Env Rejection)

- Khắc phục triệt để phát hiện blocker kiến trúc từ Sol-Lead audit trên exact candidate `a286e6ddde69ac0f0452c31888d8ad641402f706` cho bundle `docs/parallel-delivery/`:
  - **(1) Loại Bỏ Triệt Để Việc Tự Đọc Biến Môi Trường Cùng Tiến Trình Khỏi provision_from_host()**:
    - Xóa bỏ hoàn toàn việc đọc `os.environ` (`ORCA_REVIEWER_SESSION_SECRET`, `ORCA_REVIEWER_SECRET`, `DELY_REVIEWER_SESSION_SECRET`, `REVIEWER_SESSION_SECRET`) trong `ReviewerSessionBoundary.provision_from_host()`.
    - Caller trong cùng tiến trình không thể đặt biến môi trường rồi gọi `get_default()` hoặc `provision_from_host()` để trở thành nguồn credential.
    - Mọi lời gọi không tham số `provision_from_host()` hoặc truyền caller-selected secret đều bị từ chối fail-closed với `ProtocolViolationError("Caller-selected reviewer boundary provisioning forbidden; boundary must be provisioned immutably from trusted external host handoff authority")`.
  - **(2) Bắt Buộc Authority Opaque Do External Host Sở Hữu (ReviewerHostHandoff)**:
    - Bổ sung lớp `ReviewerHostHandoff` đại diện cho handoff authority bất biến do host bên ngoài cấp phát; từ chối fail-closed mọi tham số caller tự chọn khi khởi tạo.
    - Credential được lưu trữ cách ly hoàn toàn trong vault nội bộ (`_HOST_HANDOFF_VAULT`), bảo vệ bằng thuộc tính `@property reviewer_secret` và `__setattr__` chặn in-process caller đọc hay gán giá trị (`AttributeError`).
    - Chỉ cho phép `ReviewerSessionBoundary` tiêu thụ duy nhất 1 lần (`_consume_for_provisioning`); mọi nỗ lực tái sử dụng đều bị từ chối fail-closed.
    - `ReviewerSessionBoundary.get_default()` không tự động provision từ môi trường; nếu host chưa cấp phát handoff, ranh giới khởi tạo với `_reviewer_secret = None`.
  - **(3) Bộ Fixture Phân Biệt Tự Động 374/374 Tests PASS**:
    - Bổ sung `test_sod_16_fresh_process_caller_set_environment_not_treated_as_external_provisioning` tái hiện chính xác counterexample của Sol audit trong tiến trình con mới: chủ động đặt các biến môi trường reviewer, chứng minh ranh giới mặc định vẫn giữ `_reviewer_secret = None`, không nhận caller-set environment làm host provisioning, từ chối mọi nỗ lực mint proof hay context với caller-set secret, và task an toàn giữ nguyên trạng thái `review`.
    - Cập nhật harness test suite sử dụng `ReviewerSessionBoundary.provision_from_host(ReviewerHostHandoff())` thay cho việc gán biến môi trường cấp module.
    - Nâng tổng số test lên 374/374 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau a518501 (Elimination of Fallback Reviewer Secret, Public Caller-Selected Provisioning Prevention, and Mandatory Host-Owned Boundary)

- Khắc phục triệt để phát hiện blocker kiến trúc từ Sol-Lead audit trên exact candidate `a5185012fa21a0727c0b36de28e86917494b3591` cho bundle `docs/parallel-delivery/`:
  - **(1) Xóa Bỏ Hoàn Toàn Fallback Secret Literal Khỏi Mã Nguồn Production**:
    - Xóa bỏ triệt để fallback secret literal `test_fixture_reviewer_secret_32b_hex!` khỏi `ReviewerSessionBoundary.provision_from_host()` trong `docs/parallel-delivery/delivery_engine.py`.
    - Khi không có biến môi trường nào từ host (`ORCA_REVIEWER_SESSION_SECRET`, `ORCA_REVIEWER_SECRET`, `DELY_REVIEWER_SESSION_SECRET`, `REVIEWER_SESSION_SECRET`), ranh giới mặc định khởi tạo với `_reviewer_secret = None`.
    - Mọi lời gọi `issue_session_proof()` hoặc `create_reviewer_context()` khi thiếu external reviewer provisioning đều bị từ chối fail-closed với `ProtocolViolationError("Reviewer credential not configured on ReviewerSessionBoundary fail-closed; trusted session bootstrap must inject reviewer credential before issuing session proofs")`.
  - **(2) Ngăn Chặn Tuyệt Đối Public Caller-Selected Provisioning**:
    - Phương thức `ReviewerSessionBoundary.provision_from_host()` nhận `*args, **kwargs` và từ chối fail-closed ngay lập tức nếu caller cung cấp bất kỳ tham số nào (`ProtocolViolationError("Caller-selected reviewer boundary provisioning forbidden; boundary must be provisioned immutably from trusted external host environment")`).
    - Caller cùng tiến trình tuyệt đối không thể tự chọn secret khi gọi `provision_from_host()`.
  - **(3) Bắt Buộc Ranh Giới Host-Owned Opaque Trong OrcaDeliveryAdapter**:
    - `OrcaDeliveryAdapter.__init__` kiểm tra nghiêm ngặt: nếu `reviewer_boundary` được truyền vào, nó bắt buộc phải là singleton `ReviewerSessionBoundary.get_default()` do host cấp phát; mọi boundary do caller tự khởi tạo (`ReviewerSessionBoundary(...)`) đều bị từ chối fail-closed với `ProtocolViolationError("Caller-selected reviewer boundary forbidden; OrcaDeliveryAdapter strictly requires opaque host-owned ReviewerSessionBoundary")`.
  - **(4) Bộ Fixture Phân Biệt Tự Động 373/373 Tests PASS**:
    - Bổ sung `test_sod_14` kiểm tra từ chối truyền boundary tự tạo vào constructor của `OrcaDeliveryAdapter`.
    - Bổ sung `test_sod_15_fresh_process_missing_external_provisioning_rejected_task_remains_review` tái hiện counterexample độc lập trong tiến trình Python mới hoàn toàn không có biến môi trường reviewer: xác nhận thiếu external provisioning bị từ chối fail-closed ở mọi nỗ lực mint proof, context, hay evidence; task an toàn giữ nguyên trạng thái `review` và không thể đạt `merge_queued`.
    - Di chuyển `if __name__ == "__main__": unittest.main()` về cuối tệp `test_negative_fixtures.py`.
    - Nâng tổng số test lên 373/373 passed 100%.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau 7e0e312 (Elimination of In-Process Reset/Credential Injection, Immutable Reviewer Boundary Provisioning, and Adapter-Bound Review Dispatch)

- Khắc phục triệt để phát hiện blocker kiến trúc từ Sol-Lead audit trên exact candidate 7e0e31259574c414eb7a7ba86bf9fc84b72ddf6d cho bundle docs/parallel-delivery/:
  - **(1) Loại Bỏ Triệt Để API Reset Và Injection Khỏi Bề Mặt Production (Elimination of Reset/Credential Injection from Production-Callable Surface)**:
    - Xóa bỏ hoàn toàn các phương thức
eset_default(), inject_reviewer_credential(), ootstrap_reviewer_credential(), và ootstrap_reviewer_capability() khỏi ReviewerSessionBoundary.
    - ReviewerSessionBoundary.get_default() từ chối fail-closed mọi tham số truyền vào từ in-process callers (args hoặc kwargs đều kích hoạt ProtocolViolationError("Cannot mutate reviewer credential of already initialized ReviewerSessionBoundary; singleton credential replacement forbidden fail-closed")), ngăn chặn tuyệt đối caller cùng tiến trình tự chọn hoặc thay thế secret.
  - **(2) Cấp Phát Boundary Bất Biến Từ Trusted External Session/Host (Immutable External Session/Host Boundary Provisioning)**:
    - Cơ chế provision_from_host() cấp phát ranh giới bất biến từ biến môi trường của phiên bên ngoài tin cậy (ORCA_REVIEWER_SESSION_SECRET / ORCA_REVIEWER_SECRET / DELY_REVIEWER_SESSION_SECRET / REVIEWER_SESSION_SECRET) hoặc secret mật mã không thể đoán trước; cấm tái cấp phát hay thay thế một khi đã khởi tạo.
  - **(3) Ràng Buộc create_review_dispatch Và Claim Capability Vào Boundary Đã Cấp Phát (Binding Review Dispatch to Provisioned Boundary)**:
    - OrcaDeliveryAdapter.__init__ nhận
eviewer_boundary đã được cấp phát từ host (hoặc mặc định từ host boundary) và lưu thành thuộc tính bất biến @property reviewer_boundary. Caller không thể gán đè hay thay thế thuộc tính này.
    - Cả create_review_dispatch(), claim_reviewer_capability(), và get_reviewer_capability() đều gắn kết trực tiếp vào self._reviewer_boundary, chấm dứt hoàn toàn lỗ hổng singleton bị caller in-process hoán đổi.
  - **(4) Bộ Fixture Phân Biệt Tự Động 372/372 Tests PASS**:
    - Bổ sung và cập nhật các bài test trong TestSolRemediationSeparationOfDuties: 	est_sod_12 chứng minh caller không thể reset, inject, hay thay thế boundary credential; 	est_sod_14 tái hiện chính xác counterexample của Sol audit, chứng minh caller in-process không thể tạo boundary giả mạo, không thể claim capability hay forge evidence, và task không bao giờ có thể vượt qua trạng thái
eview để đạt merge_queued.
    - Nâng tổng số test lên 372/372 passed 100%.
  - **(5) Xóa Bỏ Dòng Trống Thừa Tại Cuối Tệp (Trailing Blank Line Elimination)**:
    - Xóa bỏ dòng trống thừa tại docs/parallel-delivery/test_negative_fixtures.py:10839, bảo đảm git diff --check đạt 0 cảnh báo/lỗi trên toàn bộ lịch sử từ approved base commit 4a7c8c921b7e05066505d51b168a02c3fde61317.

## 2026-09-30 — Khắc phục phát hiện Sol-Lead audit sau 358571a (Elimination of Public Default Reviewer Secret, Immutable Boundary Credentials, and Trusted Session Bootstrap)

- Khắc phục triệt để phát hiện blocker kiến trúc từ Sol-Lead audit trên exact candidate `358571a0be3bf9dc39dbeccc624e48cba5936fbf` cho bundle `docs/parallel-delivery/`:
  - **(1) Xóa Bỏ Hoàn Toàn Hằng Số Mặc Định Công Khai (Elimination of Public Default Reviewer Secret)**:
    - Xóa bỏ triệt để hằng số `DEFAULT_TEST_REVIEWER_SECRET` khỏi `docs/parallel-delivery/delivery_engine.py`.
    - `ReviewerSessionBoundary.__init__` không sử dụng bất kỳ secret mặc định nào; `_reviewer_secret` mặc định là `None`.
  - **(2) Ngăn Chặn Thay Thế Credential Singleton (Immutable Boundary Credentials & Fail-Closed Replacement)**:
    - `ReviewerSessionBoundary.get_default()` từ chối fail-closed nếu caller truyền `reviewer_secret` khi singleton đã được khởi tạo (`ProtocolViolationError("Cannot mutate reviewer credential of already initialized ReviewerSessionBoundary; singleton credential replacement forbidden fail-closed")`).
  - **(3) Cấp Phát Và Tiêm Credential Qua Trusted Session Bootstrap (Trusted Reviewer Session Bootstrap)**:
    - Bổ sung các phương thức `inject_reviewer_credential()`, `bootstrap_reviewer_credential()`, và `bootstrap_reviewer_capability()` trên `ReviewerSessionBoundary`.
    - Sau khi đã thiết lập secret lần đầu, mọi nỗ lực tiêm lại hoặc ghi đè credential đều bị từ chối fail-closed.
  - **(4) Bắt Buộc Có Reviewer Secret Hợp Lệ Khi Phát Hành Proof Và Ngữ Cảnh (Mandatory Secret For Proof Issuance)**:
    - `issue_session_proof()` và `create_reviewer_context()` từ chối fail-closed khi `reviewer_secret` bị bỏ qua (`None` hoặc chuỗi rỗng), khi boundary chưa được cấu hình credential, hoặc khi secret không khớp mã băm HMAC digest.
  - **(5) Bộ Fixture Phân Biệt Tự Động 371/371 Tests PASS**:
    - Bổ sung 4 fixture kiểm thử mới vào `TestSolRemediationSeparationOfDuties`: `test_sod_10` (omitted reviewer secret fails closed), `test_sod_11` (singleton secret replacement via get_default fails closed), `test_sod_12` (trusted session bootstrap injection and immutability), `test_sod_13` (absence of DEFAULT_TEST_REVIEWER_SECRET in delivery_engine).
    - Nâng tổng số test lên 371/371 passed 100%.

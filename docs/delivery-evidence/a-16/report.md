# Báo cáo bằng chứng A-16

## Môi trường

- Interpreter khoá: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
- Baseline: 1d56b2699f6f6a2c08346da3db1107e435c234eb
- Nguồn quyền: IMPL-PLAN-A Auditor PASS, slice A-16 trong docs/implementation/a/slices.md, phụ thuộc A-11 đã tích hợp.

## RED

- Lệnh thực thi: python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no:cacheprovider
- Trạng thái mã lúc RED: src/source_ingestion/application/supplemental.py chỉ chứa định nghĩa kiểu dữ liệu và stub collect_supplemental trả về SupplementalResult với outcome SupplementalOutcome.FAILED cố định cùng lý do 'NOT_IMPLEMENTED', không gọi adapter/port, không thực hiện kiểm tra grant/tombstone/budget hay tạo run.
- Exit code thực tế: 1
- Dòng tóm tắt nguyên văn: 22 failed, 3 passed in 0.39s
- Test FAILED tiêu biểu:
  - FAILED tests/integration/collection/test_a16_supplemental.py::test_valid_request_collects_packages_and_media_with_provenance (AssertionError: assert <SupplementalOutcome.FAILED: 'FAILED'> is <SupplementalOutcome.FOUND: 'FOUND'>)
  - FAILED tests/integration/collection/test_a16_supplemental.py::test_supplemental_never_creates_or_counts_a_periodic_run (AssertionError: assert <SupplementalOutcome.FAILED: 'FAILED'> is <SupplementalOutcome.FOUND: 'FOUND'>)
  - FAILED tests/integration/collection/test_a16_supplemental.py::test_tombstoned_source_is_blocked_before_any_search_or_fetch (AssertionError: assert <SupplementalOutcome.FAILED: 'FAILED'> is <SupplementalOutcome.BLOCKED: 'BLOCKED'>)
- Xác nhận: 0 error, không có lỗi ModuleNotFoundError, ImportError hay lỗi collection; các ca kiểm thử FAILED đều do AssertionError từ stub đúng oracle mong đợi (3 ca PASS kiểm tra validation kiểu request và ranh giới import tĩnh).

## Thay đổi

- src/source_ingestion/application/supplemental.py:
  - SupplementalOutcome: Enum trạng thái kết quả bổ sung (FOUND, PARTIAL, NOT_FOUND, BLOCKED, FAILED).
  - SupplementalBudget: Dataclass bất biến xác thực udget_ref không rỗng, max_fetches là int >= 1 (từ chối bool/0), deadline_at là datetime có timezone-aware.
  - SupplementalRequest: Dataclass bất biến nhận job_id, scene_ref, intent_ref, intent (không rỗng, text map), budget, grant (ExecutionGrant từ G), retry_policy và extraction_policy.
  - SupplementalJob: Dataclass gói gọn request, SourceAdapter và HtmlExtractor.
  - SupplementalDiscovery: Dataclass kết quả phát hiện media mang thông tin nguồn gốc (provenance), cờ 
ew_package (False nếu bài viết đã tồn tại trước đó).
  - SupplementalResult: Dataclass kết quả thu thập bổ sung đầy đủ trường truy vết, đếm tài nguyên, mảng lỗi ItemError và cờ 
eplayed.
  - collect_supplemental: Hàm nghiệp vụ thu thập bổ sung cho video job. Kiểm tra grant G hiện hành và khớp workspace/job scope; kiểm tra trạng thái nguồn (ngăn chặn nguồn không tồn tại, ngừng hoạt động hoặc tombstone); quản lý lifecycle CollectionRun với purpose SUPPLEMENTAL; không bao giờ tạo hoặc tăng đếm periodic run và không bao giờ dịch chuyển checkpoint của nguồn; kiểm tra tombstone nguồn và canonical URL trước mọi lần fetch; thực hiện tìm kiếm qua adapter; kiểm soát ngân sách theo max_fetches và hạn chót deadline_at (hết ngân sách/hạn chót trả PARTIAL hoặc NOT_FOUND kèm mã lý do có cấu trúc, không bao giờ trả thành công rỗng); đóng gói package theo chuẩn A-02/schema; bàn giao package mới cho Phân hệ B qua ContentHandoffPort và phát sinh sự kiện CollectedDocumentAvailable mang đầy đủ reference ngữ cảnh; hỗ trợ replay kết quả khi gọi lại cùng 
un_id và tiếp tục retry trên cùng một run instance theo A-RULE-005. Hoàn toàn không import hay wiring tới Phân hệ C.
  - Nêu rõ không sửa collect_source.py.
- 	ests/integration/collection/test_a16_supplemental.py: Bộ kiểm thử tích hợp 25 ca kiểm thử bao phủ toàn bộ các yêu cầu và phản ví dụ, docstring chứa coveredIds: A-RULE-002, A-RULE-005, chặn socket thật bằng fixture autouse _no_network.
- docs/delivery-evidence/a-16/report.md: Báo cáo bằng chứng bàn giao thực thi task A-16.

## Ánh xạ yêu cầu → test

| Yêu cầu / phản ví dụ | Ca kiểm thử |
|---|---|
| Request hợp lệ, grant/refs từ G, thu thập package và media có provenance | 	est_valid_request_collects_packages_and_media_with_provenance |
| Supplemental không bao giờ tạo hoặc đếm periodic run | 	est_supplemental_never_creates_or_counts_a_periodic_run |
| Supplemental chạy độc lập không để lại periodic run và không dịch chuyển checkpoint | 	est_supplemental_alone_leaves_no_periodic_run_and_no_checkpoint |
| Nguồn tombstone bị chặn hoàn toàn trước mọi tìm kiếm hoặc fetch (A-RULE-002) | 	est_tombstoned_source_is_blocked_before_any_search_or_fetch |
| Nguồn bị vô hiệu hoá hoặc không tìm thấy bị chặn (SOURCE_INACTIVE, SOURCE_NOT_FOUND) | 	est_disabled_or_unknown_source_is_blocked |
| Nguồn bị tombstone giữa chừng lập tức dừng trước lần fetch kế tiếp | 	est_source_tombstoned_during_run_stops_before_the_next_fetch |
| Locator trùng canonical của nguồn đã tombstone không bao giờ bị fetch và nguồn không bị hồi sinh | 	est_discovered_locator_of_a_tombstoned_source_is_never_fetched |
| Hết budget fetch trả kết quả PARTIAL kèm lý do BUDGET_EXHAUSTED có cấu trúc | 	est_budget_exhausted_returns_partial_with_structured_reason |
| Hết budget mà không có package nào trả về NOT_FOUND, không bao giờ trả thành công rỗng | 	est_budget_exhausted_without_any_package_is_not_found_never_success |
| Quá hạn chót (deadline) trước khi search trả về NOT_FOUND không gọi adapter | 	est_deadline_passed_before_search_is_not_found_without_any_call |
| Chạm hạn chót (deadline) giữa chừng trả về PARTIAL kèm DEADLINE_EXCEEDED | 	est_deadline_reached_mid_run_returns_partial |
| Kết quả tìm kiếm rỗng trả về NOT_FOUND kèm NO_CANDIDATES | 	est_empty_search_result_is_not_found_with_reason |
| Năng lực tìm kiếm bổ sung không được hỗ trợ trả về FAILED có cấu trúc | 	est_unsupported_search_capability_is_a_structured_failure |
| Grant của G hết hạn hoặc lạc phạm vi bị chặn mà không mở run | 	est_stale_or_foreign_grant_is_blocked_without_a_run |
| Package mới chuyển qua handoff B và outbox event mang đầy đủ metadata của supplemental | 	est_new_packages_go_to_b_and_events_carry_supplemental_refs |
| Bài viết trùng lặp được bỏ qua (skipped) nhưng vẫn giữ media provenance gốc, không gửi lại B | 	est_duplicate_article_is_skipped_but_keeps_media_provenance |
| Thất bại khi bàn giao B vẫn bảo toàn package đã commit trong kho dữ liệu | 	est_handoff_b_failure_keeps_the_committed_package |
| Vi phạm hợp đồng từ B được ghi nhận thành lỗi HANDOFF_B_CONTRACT_VIOLATION | 	est_handoff_b_contract_violation_is_reported |
| Cùng run_id đã kết thúc phát lại (replay) kết quả đã lưu không gọi thêm adapter hay port | 	est_same_run_id_replays_stored_result_without_new_calls |
| Xung đột run_id với purpose khác (như PERIODIC) bị từ chối bằng RUN_ID_CONFLICT | 	est_run_id_of_another_purpose_is_rejected |
| Sự cố có thể thử lại khi tìm kiếm chuyển sang WAITING_RETRY rồi tiếp tục cùng run instance (A-RULE-005) | 	est_retryable_search_problem_waits_then_resumes_the_same_supplemental_run |
| Tiếp tục thử lại sau hạn chót đóng run với kết quả NOT_FOUND | 	est_resume_after_deadline_closes_the_run_as_not_found |
| Kiểm tra hợp lệ dữ liệu request (từ chối budget sai lệch, intent rỗng) | 	est_request_validation_rejects_bad_budget_and_intent |
| Ranh giới nhập gói: mô-đun chỉ import stdlib, domain, ports và application | 	est_module_imports_only_stdlib_domain_ports_and_application |
| Handoff C chưa được kết nối và chờ hợp đồng CT-MED-001 (CONV-A-07) | 	est_handoff_c_is_not_wired_and_waits_for_ct_med_001 |

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no:cacheprovider | 0 | 25 passed in 0.10s |
| 2 | python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider | 0 | 8 passed, 31 subtests passed in 0.08s |
| 3 | python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider | 0 | 18 passed in 0.11s |
| 4 | git diff --check | 0 | passed (clean, no output) |

## Quyết định mặc định (D8)

1. SUPPLEMENTAL không phát các sự kiện CollectionRunStarted, CollectionRunCompleted, CollectionRunFailed để tách hẳn khỏi metric và pipeline của periodic run; chỉ phát CollectedDocumentAvailable với các trường bổ sung additive mang tính chất truy vết: purpose, job_id, scene_ref, intent_ref, udget_ref.
2. Tuyệt đối không chạm vào checkpoint nguồn dùng chung với periodic run (uow.checkpoints.advance không bao giờ được gọi từ luồng SUPPLEMENTAL).
3. usiness_date của CollectionRun lấy theo ngày UTC của clock, đóng vai trò đánh dấu thời gian nghiệp vụ chứ không phải khoá định danh duy nhất.
4. Trạng thái kết quả SupplementalOutcome được suy ra trực tiếp từ trạng thái của run: COMPLETED_PARTIAL -> PARTIAL; COMPLETED có package -> FOUND, không có package -> NOT_FOUND; FAILED_FINAL kết hợp RETRY_EXHAUSTED -> NOT_FOUND; SOURCE_INACTIVE -> BLOCKED; các trường hợp còn lại là FAILED.
5. Bài trùng lặp (trùng canonical URL và fingerprint nội dung) được tính là skipped, vẫn trả về thông tin SupplementalDiscovery gốc với 
ew_package=False và không gửi lại Phân hệ B.
6. Khi bàn giao sang Phân hệ B gặp sự cố ngoại lệ hoặc vi phạm hợp đồng, package đã commit trong UoW vẫn được bảo toàn nguyên vẹn và ghi nhận lỗi có cấu trúc (HANDOFF_B_FAILED, HANDOFF_B_CONTRACT_VIOLATION).
7. Lần thử lại (retry) khi gặp lỗi tạm thời là attempt tiếp theo của cùng một 
un_id (tuân thủ nguyên tắc A-RULE-005); khi cùng một 
un_id đã đạt trạng thái kết thúc (terminal) được gọi lại thì thực hiện replay kết quả đã lưu mà không gọi lại adapter hay cổng ngoài.
8. Tái sử dụng một số hàm tiện ích nội bộ từ collect_source (_available_payload, _checkpoint_ref, _exception_text, _failure, _item_error, _observation_fingerprint, _utc_now) nhằm đảm bảo tính nhất quán về redaction và định dạng payload mà không trùng lặp mã nguồn, không sửa đổi collect_source.py.

## Mục mở / follow-up

- Handoff C chờ hoàn thiện hợp đồng CT-MED-001 và nhiệm vụ quy ước CONV-A-07.
- Đăng ký activity A ở Phân hệ G thuộc nhiệm vụ CONV-A-06.
- Đăng ký và chuẩn hoá schema event thuộc nhiệm vụ CONV-A-09.
- Giá trị tham số hạn mức udget_ref, max_fetches, deadline_at do Phân hệ G chỉ định qua grant, Phân hệ A không tự ý đặt mặc định.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy full test suite, 	ests/m1 hay 	ests/m2.
- Không thay đổi pyproject.toml hay uv.lock.
- Không gọi mạng, DNS hay dịch vụ bên ngoài; toàn bộ test cô lập socket qua fixture _no_network.
- Chỉ sử dụng fixture bộ nhớ và fake adapter/port (FakeAdapter, EchoContentPort, FakeActivityGrantPort, InMemoryUnitOfWork).

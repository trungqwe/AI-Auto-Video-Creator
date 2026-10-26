# Báo cáo thực hiện gói công việc PW-D1

## 1. Phạm vi thực hiện

Gói công việc PW-D1 chỉ thực hiện chỉnh sửa và tạo mới các tệp trong danh sách đường dẫn được giao quyền sở hữu (owned paths):

1. src/creative/application/roles.py: Định nghĩa ánh xạ route_key cho sáu vai trò sáng tạo.
2. src/creative/application/prompts.py: Định nghĩa sáu prompt mặc định bằng tiếng Anh và cơ chế seed_default_prompts idempotent.
3. src/creative/application/pipeline.py: Chuyển hằng số vai trò sang roles.py và gọi route_key khi giải quyết tuyến AI.
4. src/creative/adapters/prompt_source.py: Adapter đọc cấu hình prompt đã xuất bản và ghim vào snapshot.
5. 	ests/integration/prod_wiring/test_pw_d1_roles_prompts.py: Bộ kiểm thử tích hợp trên cơ sở dữ liệu PostgreSQL thật và catalog profile thật.
6. 	ests/integration/creative/test_d14_creative_pipeline.py: Cập nhật khoá phản hồi và kiểm chứng gọi AI sang khoá route với SelectionSplitAI.
7. 	ests/integration/creative/test_d16_worker_activity.py: Cập nhật khoá phản hồi và kiểm chứng hoạt động worker sang khoá route.
8. docs/delivery-evidence/pw-d1/report.md: Báo cáo nghiệm thu kỹ thuật chi tiết của gói công việc.

## 2. Thiết kế kỹ thuật

- Hàm oute_key(role) trong tệp oles.py là điểm tập trung duy nhất thực hiện chuyển đổi sáu vai trò nghiệp vụ của pipeline sáng tạo (content_analysis, story_angles, script_generation, sset_selection, production_plan, output_metadata) sang năm khoá định tuyến của profile (nalysis, ngle, script, selection, selection, metadata). Trong đó hai vai trò sset_selection và production_plan dùng chung khoá định tuyến selection. Mọi giá trị vai trò không thuộc danh mục đều bị từ chối bằng ngoại lệ UnknownRoleError.
- Tệp prompts.py cung cấp sáu bản mẫu chỉ dẫn mặc định bằng tiếng Anh chuẩn ASCII, tuân thủ nguyên tắc phân định nghiêm ngặt giữa chỉ dẫn điều khiển và dữ liệu người dùng của PromptEnvelope. Văn bản chỉ dẫn không chứa bất kỳ ký tự giữ chỗ nào liên quan đến nội dung bài viết. Hàm seed_default_prompts thực hiện nạp cấu hình thông qua cổng lệnh put_config với mức phiên bản kỳ vọng bằng không (expected_revision=0) và khoá idempotent gắn liền với mã băm nội dung của prompt. Thao tác nạp cấu hình đạt tính bất biến khi chạy lặp lại và bỏ qua nếu vai trò đã có bản ghi cấu hình trước đó.
- Tệp prompt_source.py hiện thực lớp ConfigPromptSource cho phép truy xuất các bản sửa đổi prompt ở trạng thái PUBLISHED qua cổng PromptScopePort mà không cần kết nối trực tiếp đến hạ tầng cơ sở dữ liệu. Phương thức snapshot_refs xuất danh sách tham chiếu phục vụ ghim phiên bản vào BuildProductionSnapshot, phương thức instructions cung cấp nội dung chỉ dẫn tương ứng. Khi thiếu bản ghi hợp lệ, phương thức sẽ báo lỗi PromptNotSeeded.
- Tệp pipeline.py tích hợp lệnh gọi oute_key(role) tại điểm duy nhất sinh yêu cầu giải quyết tuyến (_invoke), bảo đảm các trường tham chiếu bản ghi cấu hình vẫn giữ nguyên định danh vai trò của pipeline. Đồng thời pipeline.py xuất lại danh sách AI_ROLES từ oles.py để bảo đảm tính tương thích với các mô-đun hiện hành.

## 3. Bảng chi tiết các dòng thay đổi trong kiểm thử đã nghiệm thu

Bảng thống kê toàn bộ các dòng được điều chỉnh trong hai tệp kiểm thử sáng tạo cùng lý do kỹ thuật tương ứng:

| Tệp kiểm thử | Vị trí / Ký hiệu | Nội dung điều chỉnh | Lý do kỹ thuật |
| --- | --- | --- | --- |
| 	est_d14_creative_pipeline.py | Hàm _responses | Thay thế các khoá vai trò cũ bằng năm khoá route (nalysis, ngle, script, selection, metadata); bổ sung từ điển ROUTE_KEY_OF và lớp SelectionSplitAI kế thừa FakeAIAdapter. | Đồng bộ khoá phản hồi theo khoá route của profile; lớp SelectionSplitAI phân tách nội dung phản hồi cho asset_selection và production_plan theo trường envelope.instructions mà không can thiệp vào fake_ai.py. |
| 	est_d14_creative_pipeline.py | Lớp Rig.__init__ | Khởi tạo đối tượng giả lập self.ai bằng lớp SelectionSplitAI thay vì FakeAIAdapter. | Kích hoạt cơ chế phân tách phản hồi route selection trong môi trường kiểm thử pipeline. |
| 	est_d14_creative_pipeline.py | Hàm 	est_every_command_is_one_unit_of_work_with_receipt_and_outbox_event | Đổi assertion ecord.ai_role == role thành ecord.ai_role == ROUTE_KEY_OF[role]. | Thuộc tính ai_role của bản ghi gọi AI do adapter ghi nhận theo khoá route thực tế. |
| 	est_d14_creative_pipeline.py | Hàm 	est_every_command_is_one_unit_of_work_with_receipt_and_outbox_event | Đổi assertion ig.ai.calls_by_role thành {'analysis': 1, 'angle': 1, 'script': 1, 'selection': 2, 'metadata': 1}. | Hai bước asset_selection và production_plan cùng sử dụng chung khoá route selection nên số lượt gọi tích luỹ bằng hai. |
| 	est_d14_creative_pipeline.py | Hàm 	est_every_output_carries_snapshot_model_prompt_config_and_input_revision | Đổi assertion ecord.ai_role so sánh với ROUTE_KEY_OF[role]. | Bảo đảm tính nhất quán của trường ai_role theo khoá route cho tất cả các bước gọi AI. |
| 	est_d14_creative_pipeline.py | Hàm 	est_same_key_and_payload_returns_old_receipt_without_second_script | Đổi assertion ig.ai.calls_by_role['script_generation'] thành ig.ai.calls_by_role['script']. | Bộ đếm lượt gọi của FakeAIAdapter được đánh chỉ mục theo khoá route. |
| 	est_d16_worker_activity.py | Từ điển RESPONSES | Đổi bốn khoá phản hồi từ vai trò nghiệp vụ sang khoá route (nalysis, ngle, script, metadata). | Khớp với yêu cầu định tuyến của FakeAIAdapter khi chạy qua worker activity. |
| 	est_d16_worker_activity.py | Hàm 	est_ai_activities_run_one_command_each_and_a_finished_stage_never_starts_the_next | Đổi kiểm tra ig.ai.calls_by_role sang {'analysis': 1, 'angle': 1, 'script': 1}. | Xác minh số lượt gọi hoạt động worker được ghi nhận chính xác theo khoá route. |
| 	est_d16_worker_activity.py | Hàm 	est_provider_failure_is_a_failed_result_with_a_code_only_problem | Đổi khoá cấu hình lỗi trong từ điển errors từ 'content_analysis' sang 'analysis'. | FakeAIAdapter thực hiện tra cứu lỗi mô phỏng theo khoá route được phân giải. |

Ghi chú quan trọng: Toàn bộ các tham chiếu phiên bản như content_analysis-r1 và các định danh kiểu tham chiếu ef_type mang giá trị 'content_analysis' đều được giữ nguyên vẹn đúng theo thiết kế ban đầu.

## 4. Bảng tổng hợp các lệnh kiểm thử đã thực thi

| Bước | Lệnh thực thi | Mã thoát | Kết quả quan sát thực tế |
| --- | --- | --- | --- |
| 9 | python -m pytest tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider | 1 | 15 bài kiểm thử thất bại (8 bài d14 gặp lỗi NoScriptedResponse: content_analysis; 7 bài d16 thất bại do phụ thuộc), 55 bài thành công. |
| 13 | python -m pytest tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider | 0 | 70 bài kiểm thử đạt kết quả thành công hoàn toàn trong 0.27 giây sau khi nối route_key. |
| 21 | python -m pytest tests/integration/prod_wiring/test_pw_d1_roles_prompts.py -q -p no:cacheprovider | 0 | 16 bài kiểm thử tích hợp trên cơ sở dữ liệu PostgreSQL thật đạt thành công trong 5.85 giây. |
| 22 | python -m pytest tests/integration/prod_wiring/test_pw_d1_roles_prompts.py tests/integration/creative/test_d14_creative_pipeline.py tests/integration/creative/test_d16_worker_activity.py tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider | 0 | 98 bài kiểm thử chính và 58 bài kiểm thử nhánh phụ đạt kết quả thành công trong 4.94 giây. |
| 23 | git diff --check | 0 | Không xuất hiện bất kỳ cảnh báo hoặc lỗi khoảng trắng thừa nào. |
| 24 | Kiểm tra probe chuỗi ký tự bắt buộc và tính độc lập import của tệp roles.py | 0 | Đạt toàn bộ điều kiện: chứa đủ năm khoá route và không chứa tiền tố import bị cấm. |
| 25 | Kiểm tra probe loại bỏ hoàn toàn mẫu lỗi F1 trong hai tệp creative | 0 | Xác nhận không còn khoá cũ, calls_by_role['selection'] đạt giá trị 2, SelectionSplitAI hoạt động chính xác. |

## 5. Bằng chứng kiểm thử định hướng Oracle (RED và GREEN)

- Trạng thái RED hợp lệ ở bước 9: Được ghi nhận khi chạy hai tệp kiểm thử creative trước khi cập nhật pipeline.py và trước khi tạo roles.py. Lệnh kiểm thử trả về mã lỗi 1 với 15 bài không đạt. Cụ thể trong test_d14_creative_pipeline.py, các bài kiểm thử thực thi chuỗi lệnh đều dừng lại ngay tại bước đầu tiên với lỗi NoScriptedResponse: content_analysis, do pipeline cũ gửi vai trò content_analysis trong khi FakeAIAdapter đã được cấu hình chờ đợi khoá route nalysis. Đồng thời trong test_d16_worker_activity.py, hoạt động worker dừng lại do lệnh đầu tiên thất bại.
- Trạng thái GREEN hợp lệ ở bước 13: Sau khi bổ sung định nghĩa ánh xạ trong roles.py và cập nhật pipeline.py gọi qua route_key(role), toàn bộ 70 bài kiểm thử thuộc hai tệp d14 và d16 chuyển sang trạng thái thành công hoàn toàn.
- Trạng thái GREEN hoàn chỉnh ở bước 22: Chạy đầy đủ bốn tệp kiểm thử theo yêu cầu nghiệm thu, toàn bộ 98 bài kiểm thử vượt qua thành công, bao gồm kiểm tra cấu trúc gói không chứa các gói phụ thuộc cấm trong test_d01_package_layout.py.
- Ranh giới oracle: Tệp kiểm thử mới test_pw_d1_roles_prompts.py không chạy chứng kiến RED riêng lẻ do các thành phần roles.py, prompts.py và prompt_source.py cần tồn tại để tránh lỗi cú pháp nạp mô-đun (ImportError không được tính là RED hợp lệ theo chuẩn nghiệm thu). Bằng chứng RED hợp lệ tập trung vào hành vi định tuyến của d14 và d16.

## 6. Danh mục yêu cầu kỹ thuật và bằng chứng xác minh (coveredIds)

| Mã yêu cầu | Mô tả nội dung | Phương thức kiểm chứng và bài kiểm thử tương ứng |
| --- | --- | --- |
| PW-D1-01 | Ánh xạ duy nhất và chuẩn hoá sáu vai trò sáng tạo sang khoá route tương thích cấu hình profile sản xuất. | Bài kiểm thử 	est_route_key_translates_six_roles_and_rejects_unknown_roles và 	est_real_profile_catalog_returns_a_route_for_each_pipeline_role. |
| FR-CFG-007 | Định nghĩa sáu prompt mặc định bằng tiếng Anh chỉ chứa chỉ dẫn và nạp cấu hình idempotent vào hệ thống quản lý cấu hình. | Bài kiểm thử 	est_default_prompts_are_english_instruction_only, 	est_seed_default_prompts_is_idempotent_one_revision_per_role, 	est_seed_after_an_edit_does_not_create_or_overwrite_revisions, 	est_seed_skips_a_role_that_already_has_a_revision. |
| CT-AI-ROUTE-001 | Yêu cầu định tuyến AI qua ProfileRouteCatalog trả về đúng mô hình ứng với từng vai trò của pipeline. | Bài kiểm thử 	est_pipeline_builds_the_route_request_through_route_key và 	est_real_profile_catalog_returns_a_route_for_each_pipeline_role. |
| CT-SEC-002 | Bảo đảm an toàn biên chỉ dẫn và dữ liệu: nội dung chỉ dẫn lấy từ prompt đã ghim, dữ liệu đầu vào nằm tách biệt trong khối dữ liệu untrusted. | Bài kiểm thử 	est_instructions_come_from_the_pinned_prompt_and_data_stays_in_the_data_block và 	est_edit_through_put_config_changes_only_later_snapshots. |

## 7. Mục mở và giới hạn vận hành

- GIẢ ĐỊNH: Khoá idempotent của thao tác nạp cấu hình ban đầu được sinh ra kèm theo chuỗi băm nội dung của prompt mặc định. Do đó, việc nâng cấp nội dung prompt mặc định trong các phiên bản phần mềm sau này sẽ không tự ý ghi đè lên các bản sửa đổi cấu hình mà người dùng đã tuỳ chỉnh trên hệ thống.
- Giới hạn kích hoạt: Trạng thái PRODUCTION_ACTIVATION_BLOCKED tiếp tục được duy trì nghiêm ngặt. Hệ thống chưa kích hoạt các kết nối sản xuất trực tiếp.
- Môi trường kiểm thử: Toàn bộ quá trình kiểm chứng được tiến hành trên cơ sở dữ liệu PostgreSQL cục bộ khép kín và các bộ điều hợp tuyến mô phỏng FakeProviderRoute, chưa thực hiện kết nối mạng hoặc gọi dịch vụ AI thực tế từ bên ngoài.

# Báo cáo gói PW-D3-FIX1: ứng viên creative mang rights_cleared theo quyền thật và UUID version đã đăng ký

## 1. Nhóm lỗi R3

Nhóm lỗi R3 phát hiện trong đợt kiểm toán hệ thống production wiring gồm hai vấn đề chính:
- (a) Chính sách an toàn bản quyền SafetyRightsPolicy (controlplane/api/wiring/creative.py:319-324, creative/domain/asset_selection.py:379-384) yêu cầu cờ required_flags=('rights_cleared',), tuy nhiên không có bộ dựng ứng viên creative nào thiết lập cờ này (creative/adapters/media_candidates.py:61-65, hook_candidates.py:40). Hậu quả là tất cả ứng viên media, hook và thumbnail đều bị từ chối/loại bỏ tại khâu lựa chọn tài sản creative.
- (b) artifact_version_ref đang bị gán cứng dưới dạng sha256:<hex> (media_candidates.py:68) thay vì UUID của phiên bản đã đăng ký trong controlplane.cp_artifact_versions. Giá trị này đi vào selected_media.revision_id (creative/adapters/activity_inputs.py:139-147) và visuals của kế hoạch sản xuất (creative/domain/production_plan.py:181), làm sai lệch hợp đồng định danh artifact version.

## 2. Tệp đã sửa

- src/creative/adapters/media_candidates.py: Nhận tham số keyword bắt buộc resolve_version: Callable[[str], str | None]; gán artifact_version_ref bằng UUID do resolve_version trả về; thiết lập rights_cleared = (safety['seed_rights_status'] == SEED_RIGHTS_STATUS) cho ảnh seed; thiết lập rights_cleared = True kèm rights_basis = 'OI-ADAPT-10' và giữ needs_image_safety cho ảnh bài viết; loại bỏ ảnh không có version đã đăng ký (hoặc resolve_version trả về None/chuỗi rỗng) tương tự như ảnh thiếu fingerprint; giữ nguyên luật phát hiện seed_media_missing.
- src/creative/adapters/hook_candidates.py: Bổ sung hằng số SEED_RIGHTS_STATUS = 'SELF_GENERATED' và thiết lập cờ rights_cleared trong safety_rights_status dựa trên biểu thức metadata.get('seed_rights_status') == SEED_RIGHTS_STATUS. Hook không có seed_rights_status hoặc khác 'SELF_GENERATED' sẽ nhận rights_cleared = False.
- tools/launcher/launcher.py: Tách hàm build_media_candidates ở cấp module, truyền resolve_version gọi verified_version_for_sha(manager, workspace_id=workspace_id, sha256=sha) và trả về version.artifact_version_id; assemble_dfe_handlers gọi hàm dựng này.
- tests/integration/prod_wiring/test_pw_d3_candidates.py: Nâng cấp các fixture (imported, seeded, staging); media_port nhận launcher và workspace_id; register_article_image nhận tham số root để stage ảnh; cập nhật các bài kiểm tra hiện hữu và bổ sung 6 bài kiểm tra mới xác thực oracle: bắt buộc callable resolve_version, loại ảnh seed/bài thiếu version, giữ nguyên seed_media_missing, xác thực SafetyRightsPolicy thật với required_flags=('rights_cleared',), và loại hook không có seed status hợp lệ.
- docs/delivery-evidence/pw-d3-fix1/report.md: Báo cáo nghiệm thu đầy đủ bằng chứng kiểm thử và thiết kế của gói PW-D3-FIX1.

Ghi rõ: src/creative/adapters/thumbnail_candidates.py KHÔNG đổi vì ứng viên thumbnail thừa hưởng trực tiếp safety_rights_status và artifact_version_ref từ các ứng viên media/visual hook đầu vào.

## 3. Thiết kế và GIẢ ĐỊNH

- Cờ rights_cleared của ảnh seed được suy luận từ seed rights status SELF_GENERATED mà adapter ghi nhận sau khi xác thực locator dạng seed://bg-NN.png và quan hệ user_imported (GIẢ ĐỊNH: RightsStatus của phân hệ C chỉ gồm known/unknown/disputed nên không so sánh trực tiếp được với SELF_GENERATED).
- Ảnh tải kèm bài viết được đặt rights_cleared = True theo quyết định người dùng OI-ADAPT-10, ghi rights_basis 'OI-ADAPT-10' và vẫn giữ nguyên needs_image_safety để bước kiểm duyệt hình ảnh tiếp theo xử lý.
- Hook được đặt rights_cleared = True khi và chỉ khi seed_rights_status == 'SELF_GENERATED'; tuyệt đối không mặc định True cho mọi hook.
- resolve_version được gọi sau khi khối ngữ cảnh open_assets(workspace_id) đã kết thúc nhằm hoàn trả connection của scope trước khi mở giao dịch truy vấn artifact version riêng.
- Ảnh không có version đăng ký sẽ bị loại bỏ; nếu toàn bộ ảnh seed thiếu version hợp lệ thì ném SelectionRejected với mã INPUT_NOT_READY và lý do seed_media_missing.

## 4. Lệnh đã chạy

| Bước | Lệnh | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 2 | python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p no:cacheprovider | 0 | 9 passed in 4.78s |
| 9 | python -m pytest tests/integration/prod_wiring/test_pw_d3_candidates.py -q -p no:cacheprovider | 1 | 12 failed, 6 passed in 19.36s |
| 13 | python -m pytest tests/integration/prod_wiring/test_pw_d3_candidates.py -q -p no:cacheprovider | 0 | 18 passed in 21.51s |
| 14 | python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider | 0 | 25 passed, 70 subtests passed in 9.00s |
| 15 | git diff --check | 0 | Mã thoát 0, không có cảnh báo khoảng trắng thừa |

## 5. Bằng chứng RED

Tại bước 9, toàn bộ 12 test kỳ vọng đều thất bại đúng oracle trước khi sửa mã nguồn sản phẩm:
1. test_seed_images_bg_01_to_bg_12_are_media_candidates_with_provenance: ValueError: badly formed hexadecimal UUID string
2. test_article_image_registered_by_register_discovery_enters_with_provenance_and_needs_image_safety: KeyError: 'rights_cleared'
3. test_hook_candidates_are_the_five_visual_and_five_audio_seed_hooks: assert False (thiếu cờ rights_cleared trong safety_rights_status)
4. test_thumbnail_candidates_are_frames_of_hooks_or_images_and_each_has_a_reason: KeyError: 'rights_cleared'
5. test_candidates_feed_select_creative_assets_with_a_seed_fallback: creative.domain.asset_selection.SelectionRejected: candidate_blocked: safety_rights_policy (visual_hook)
6. test_media_port_requires_a_callable_resolve_version: Failed: DID NOT RAISE TypeError
7. test_seed_images_without_a_registered_version_are_dropped: AssertionError: assert ['seed-bg-01'...'d-bg-06', ...] == ['seed-bg-01', 'seed-bg-02']
8. test_no_registered_seed_version_is_refused_as_seed_media_missing: Failed: DID NOT RAISE SelectionRejected
9. test_article_image_without_a_registered_version_is_dropped: AssertionError: At index 1 diff: 'img-unstaged' != 'seed-bg-01'
10. test_real_policy_keeps_seed_images_article_images_and_seed_hooks: assert False (SafetyRightsPolicy từ chối các ứng viên chưa có rights_cleared)
11. test_a_hook_without_a_self_generated_seed_status_is_not_rights_cleared: KeyError: 'rights_cleared'
12. test_adapters_keep_the_boundary_to_c_and_name_their_ports: assert 'sha256:' not in texts['media_candidates']

## 6. Mục mở

- Quyết định OI-ADAPT-10 vẫn là quyết định của người dùng đã ghi nhận.
- Cờ giới hạn PRODUCTION_ACTIVATION_BLOCKED được giữ nguyên theo chính sách kiểm soát milestone của dự án.
- Định dạng artifact_version_ref của hook (dạng seed:<id>:sha256:<hex>) nằm ngoài phạm vi xử lý của gói PW-D3-FIX1 và sẽ được quy chuẩn trong các gói chuyên trách.
- Các bước kiểm chứng bổ sung (17, 18, 19) được thực thi và xác nhận trước khi hoàn tất gói.

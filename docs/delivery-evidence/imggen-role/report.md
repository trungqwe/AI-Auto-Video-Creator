# Báo cáo IMGGEN-ROLE

Mã gói: IMGGEN-ROLE (milestone CP7).

## Nhóm lỗi OI-CP7-11-Q2

Hồ sơ production chưa có vai trò `illustration` nên `RouterVisionRoute.invoke_chat` (IMGGEN-ROUTE) và bước viết chú thích (IMGGEN-PIPE) không có tuyến. Sửa theo quyết định user 02/11/2026 (CLOSURE_NOTE CP7/RG-13 và D4): thêm khoá `illustration` = `ag/gemini-3.8-flash-high` (cùng model với `image_safety`) vào `ai.route_model_refs` và nâng `meta.revision` từ 6 lên 7. Mã nhóm lỗi: OI-CP7-11-Q2.

## Các tệp đã sửa

- `tools/launcher/prod/profile.json`: thêm khoá `illustration` cuối `ai.route_model_refs.value`, nối câu vào reason; `meta.revision` 6 lên 7, nối câu vào reason. Không thêm khoá cấp cao (vẫn 19 nhóm, 85 tham số bắt buộc).
- `tests/integration/adapt/config/test_adapt_config_profile.py`: ghim bảy khoá ở `test_ai_routes_and_duration_anchors`; thêm `test_illustration_route_shares_the_image_safety_model_and_cites_the_user_decision` và `test_profile_revision_moves_to_7_for_the_illustration_role`.
- `tests/integration/adapt/config/test_imggen_role_route.py` (mới): ba test, không DB, mạng, GPU, Temporal.
- `tests/real/test_cp7_ai_real.py`: thêm `PROFILE_ONLY_ROLES = ('illustration',)` sau `ROLES`; ghim `set(profile.ai.route_model_refs) == set(ROLES) | set(PROFILE_ONLY_ROLES)`.
- `docs/delivery-evidence/imggen-role/report.md`: báo cáo này.

Không sửa mã sản phẩm (`src/**`).

## Lệnh kiểm đã chạy

| Bước | Lệnh | Mã thoát | Kết quả |
| --- | --- | --- | --- |
| 7 (RED, trước khi sửa profile.json) | `python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py tests/integration/adapt/config/test_imggen_role_route.py -q -p no:cacheprovider` | 1 | `6 failed, 12 passed in 0.31s`; ca hỏng: `test_ai_routes_and_duration_anchors`, `test_illustration_route_shares_the_image_safety_model_and_cites_the_user_decision`, `test_profile_revision_moves_to_7_for_the_illustration_role`, `test_loader_reads_the_illustration_route_and_keeps_the_85_required_parameters`, `test_route_catalog_resolves_the_illustration_role_like_the_six_pipeline_roles`, `test_vision_route_built_from_the_profile_knows_the_illustration_role` |
| 10, 28 | `git diff --check` | 0 | không lỗi khoảng trắng |
| 11 (GREEN nhóm 1) | pytest như bước 7 | 0 | `18 passed in 0.11s` |
| 12 | `python -m pytest tests/integration/prod_ports/test_pp_8_assembly.py tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider` | 0 | `58 passed in 31.18s` |
| 13 | `python -m pytest tests/integration/adapt/e_media -q -p no:cacheprovider` | 0 | `123 passed in 4.66s` |
| 14 | `python -m pytest tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` | 0 | `21 passed in 1.57s` |
| 15 đến 25 | các probe `python` (profile, AST test cấu hình, test mới, ghim CP7, ADAPT-CONFIG-FIX2, PW-W2-FIX5, speed_fit, wpm, batch/gpu, image_safety, layout gói) | 0 | đạt; chạy bằng một script tạm chứa cùng khẳng định, không phải từng `python -c` nguyên văn |
| probe cũ ADAPT-E-MEDIA-FIX4 | khẳng định `meta.revision >= 6` | 0 | đạt |

## Kết quả từng tiêu chí

1. profile.json: ĐẠT. Bảy khoá đúng thứ tự, mọi giá trị `ag/gemini-3.8-flash-high`, basis DECIDED, reason nêu illustration, CLOSURE_NOTE CP7/RG-13, D4, 02/11/2026; revision 7.
2. Không sửa mã sản phẩm: ĐẠT (`git status` chỉ có bốn tệp trong owned paths cùng report).
3. Test cấu hình: ĐẠT (bảy khoá và hai test mới).
4. Test mới `test_imggen_role_route.py`: ĐẠT, RED thật với profile cũ (3 ca hỏng), GREEN sau khi sửa.
5. Ghim CP7: ĐẠT, chỉ kiểm bằng probe AST; không chạy `tests/real`. ROLES, CALL_CAP = 60, PER_ROLE = 10 không đổi.
6. Probe chủ cũ: ĐẠT với bản `revision >= 6`; không sửa probe gốc.

## Mục mở

- Probe ADAPT-E-MEDIA-FIX4 gốc ghim `revision == 6` nên hỏng theo ý định; Control sửa bằng check-corrections.
- `docs/implementation/adapt/plan.md` dòng 170 vẫn liệt kê sáu vai trò (tệp của ADAPT-SEED-FIX3).
- Chưa chạy nhóm cần PostgreSQL và `tests/real`.

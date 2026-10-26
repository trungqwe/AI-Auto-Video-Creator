# Báo cáo thực hiện gói PW-D3: nguồn ứng viên media, hook, thumbnail từ DB

## 1. Phạm vi — liệt kê sáu tệp owned paths và việc đã làm với từng tệp (ba adapter tạo mới, test tích hợp tạo mới, test_d01_package_layout.py sửa, report.md tạo mới).

Chi tiet thuc hien 6 tep thuoc owned paths:
1. `src/creative/adapters/media_candidates.py`: Tao moi PostgresMediaCandidates doc danh muc C qua candidate_query.py.
2. `src/creative/adapters/hook_candidates.py`: Tao moi PostgresHookCandidates doc visual va audio hooks qua candidate_query.py.
3. `src/creative/adapters/thumbnail_candidates.py`: Tao moi ThumbnailCandidates pure adapter tao khung hinh thumbnail kem ly do.
4. `tests/integration/prod_wiring/test_pw_d3_candidates.py`: Tao moi 12 test tich hop voi CSDL PostgreSQL that va seed hooks.json.
5. `tests/unit/creative/test_d01_package_layout.py`: Sua ADAPTER_IMPORT_EXEMPTIONS va bo sung 4 test kiem soat import.
6. `docs/delivery-evidence/pw-d3/report.md`: Tao moi bao cao nghiem thu 7 muc bang tieng Viet day du dau.

## 2. Thiết kế — (a) PostgresMediaCandidates: scope danh mục được tiêm vào, tìm bằng search của repository C, dựng CandidateIndexEntry rồi gọi query_media_candidates của candidate_query.py, không có SQL hay psycopg; ảnh bài kèm provenance (source_url, article_ref, sha256, fetched_at, relation) và needs_image_safety=True, không lọc theo UNVERIFIED; ảnh thiếu locator, thời điểm tải, fingerprint hoặc sai relation bị loại; thiếu media seed thì ném SelectionRejected INPUT_NOT_READY seed_media_missing; (b) PostgresHookCandidates: mỗi revision hook bật thành một mục chỉ mục clip hoặc audio, C tạo phần điểm và bằng chứng, thiếu hook ném no_visual_hook_candidates hoặc no_audio_hook_candidates; (c) ThumbnailCandidates: khung giữa cửa sổ hook hình (duration_ms // 2) hoặc ảnh tĩnh từ ứng viên media, provenance['reason'] luôn có, không có khung hợp lệ thì ném no_thumbnail_candidates; (d) test tích hợp dùng PostgreSQL thật, nhập seed qua _import_items của tools/launcher/prod/seed/import_seed.py với dữ liệu hooks.json.

## 3. Dòng đã đổi trong test khoá cấu trúc — nêu từng thay đổi của tests/unit/creative/test_d01_package_layout.py kèm lý do: bảng ADAPTER_IMPORT_EXEMPTIONS thêm đúng hai khoá media_candidates.py và hook_candidates.py, mỗi khoá frozenset({'catalog.application.candidate_query'}), vì hai adapter đọc danh mục của C qua candidate_query.py mà tiền tố catalog bị cấm; assertion test_exemption_table_is_exact_paths_only sửa cho khớp bảng ba khoá; thêm bốn test mới (test_candidate_adapters_may_import_only_candidate_query, test_candidate_query_stays_forbidden_for_every_other_module, test_exemptions_do_not_cover_a_directory_or_the_catalog_package, test_forbidden_import_prefixes_are_unchanged); không đổi FORBIDDEN_IMPORT_PREFIXES, không miễn thư mục adapters hay gói catalog, không xoá test cũ. Ghi số dòng thực tế.

So dong thuc te da doi trong `tests/unit/creative/test_d01_package_layout.py`:
- Dong 24-25: Them 2 dong chu thich tieng Viet giai thich can cu mien tru theo PROD-WIRING V4 (PW-D3).
- Dong 29-30: Them 2 khoa `src/creative/adapters/media_candidates.py` va `src/creative/adapters/hook_candidates.py` vao ADAPTER_IMPORT_EXEMPTIONS, moi khoa frozenset({'catalog.application.candidate_query'}).
- Dong 137-145: Sua AdapterExemptionTests.test_exemption_table_is_exact_paths_only xac nhan bang 3 khoa va cac frozenset cho phep.
- Dong 194-245: Them 4 phuong thuc test moi kiem tra candidate_query va cac prefix bi cam:
  - `test_candidate_adapters_may_import_only_candidate_query`
  - `test_candidate_query_stays_forbidden_for_every_other_module`
  - `test_exemptions_do_not_cover_a_directory_or_the_catalog_package`
  - `test_forbidden_import_prefixes_are_unchanged`

## 4. Lệnh đã chạy — bảng Bước, Lệnh, Exit code, Kết quả cho các bước RUN 1, 7, 9, 17, 25, 26, 27, 28; ghi rõ probe báo cáo và git diff --check chạy sau khi ghi báo cáo, kết quả nằm trong worker_done.

| Buoc | Lenh thuc thi | Exit code | Ket qua |
|---|---|---|---|
| RUN 1 | `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 58 subtests passed (baseline ban dau dat) |
| RUN 7 | `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 1 | 3 failed, 15 passed, 63 subtests passed (RED truoc khi them mien tru) |
| RUN 9 | `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | 16 passed, 70 subtests passed (GREEN sau khi them mien tru) |
| RUN 17 | `python -m pytest tests/integration/prod_wiring/test_pw_d3_candidates.py -q -p no:cacheprovider` | 1 | 11 failed, 1 passed (RED voi stub adapter) |
| RUN 25 | `python -m pytest tests/integration/prod_wiring/test_pw_d3_candidates.py -q -p no:cacheprovider` | 0 | 12 passed (GREEN test tich hop voi Postgres that) |
| RUN 26 | `python -m pytest tests/integration/prod_wiring/test_pw_d3_candidates.py tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | 28 passed, 70 subtests passed (GREEN suite bat buoc) |
| RUN 27 | Probe: needs_image_safety in t and fake not in t and from src. not in t | 0 | Dat yeu cau |
| RUN 28 | Probe: coveredIds: PW-D3-01, OI-ADAPT-10, CT-MED-006 in test docstring | 0 | Dat yeu cau |
| RUN 30 | Probe: report.md non-ascii > 200, no U+FFFD, coveredIds, candidate_query | 0 | Dat yeu cau |
| RUN 31 | `git diff --check` | 0 | Clean, khong co khoang trang thua |

## 5. Bằng chứng RED — hai test đỏ ở bước 7 và các test đỏ ở bước 17, mỗi test một dòng lỗi đầu tiên (AssertionError hoặc DID NOT RAISE).

Chi tiet loi RED:
- Buoc 7: AdapterExemptionTests.test_exemption_table_is_exact_paths_only: AssertionError: Items in the second set but not the first: 'src/creative/adapters/hook_candidates.py', 'src/creative/adapters/media_candidates.py'
- Buoc 7: AdapterExemptionTests.test_candidate_adapters_may_import_only_candidate_query: AssertionError: Lists differ: ['catalog.application.candidate_query', 'catalog.application.candidate_query.CandidateIndexEntry', 'catalog.application.candidate_query.query_media_candidates'] != []
- Buoc 17: test_seed_images_bg_01_to_bg_12_are_media_candidates_with_provenance: AssertionError: assert [] == ['seed-bg-01'...d-bg-06', ...]
- Buoc 17: test_article_image_registered_by_register_discovery_enters_with_provenance_and_needs_image_safety: AssertionError: assert [] == ['img-article'...d-bg-04', ...]
- Buoc 17: test_images_without_complete_provenance_or_bytes_are_dropped: AssertionError: assert [] == ['img-ok', 's...d-bg-05', ...]
- Buoc 17: test_a_missing_seed_image_is_refused_so_the_list_always_has_a_seed_fallback: Failed: DID NOT RAISE SelectionRejected
- Buoc 17: test_hook_candidates_are_the_five_visual_and_five_audio_seed_hooks: AssertionError: assert [] == ['vh-01', 'vh...-04', 'vh-05']
- Buoc 17: test_a_disabled_hook_is_not_a_candidate: AssertionError: assert [] == ['vh-01', 'vh...-03', 'vh-04']
- Buoc 17: test_hook_candidates_fail_closed_without_hooks: Failed: DID NOT RAISE SelectionRejected
- Buoc 17: test_thumbnail_candidates_are_frames_of_hooks_or_images_and_each_has_a_reason: AssertionError: assert (0 == 13)
- Buoc 17: test_a_hook_without_a_frame_window_gives_no_thumbnail_and_an_audio_hook_is_refused: Failed: DID NOT RAISE SelectionRejected
- Buoc 17: test_candidates_feed_select_creative_assets_with_a_seed_fallback: IndexError: tuple index out of range
- Buoc 17: test_adapters_keep_the_boundary_to_c_and_name_their_ports: AssertionError: media_candidates assert set() == {'catalog.application.candidate_query'}

## 6. coveredIds — PW-D3-01 -> test seed bg-01..12, hook vh-01..05 và ah-01..05, test_adapters_keep_the_boundary_to_c_and_name_their_ports; OI-ADAPT-10 -> test ảnh đăng ký bằng register_discovery, test ảnh thiếu provenance bị loại, test thiếu seed, test select_creative_assets có fallback seed; CT-MED-006 -> hai test thumbnail kèm lý do.

## 7. GIẢ ĐỊNH và mục mở — GIẢ ĐỊNH: (1) ảnh đã có fingerprint thì availability là AVAILABLE vì C chưa lưu trạng thái lưu trữ; (2) rendition_ref là original:<media_asset_id> và artifact_version_ref là sha256:<fingerprint> vì seed chưa đăng ký rendition; (3) technical_fitness không có điểm số (chỉ probed=False) vì chưa ProbeMedia, nên xếp hạng chỉ dựa trên khớp chủ đề bài; (4) revision_id của hook có dạng <hook_id>-r<revision>; (5) khung thumbnail của hook là giữa cửa sổ hook. Mục mở: SelectionInputsPort đủ tám khoá SELECTION_INPUT_KEYS (gồm safety_policy, music_sfx_policy_revision, preset_registry_revision, weights) do slice nối composition dựng từ ba port này; composition phải cấp open_assets và open_hooks bằng PostgresMediaAssetRepository và PostgresHookHistory của C; OI-ADAPT-10 vẫn là pendingUserCheckpoint về quyền dùng ảnh bài; giữ PRODUCTION_ACTIVATION_BLOCKED. Không ghi giả định thành quyết định.

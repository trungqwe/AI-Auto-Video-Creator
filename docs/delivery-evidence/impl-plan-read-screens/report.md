# Báo cáo IMPL-PLAN-READ-SCREENS

- **Gói thực hiện**: IMPL-PLAN-READ-SCREENS (planning_package)
- **Thời điểm**: 25/10/2026
- **Trạng thái**: Hoàn tất lập kế hoạch nối route GET chỉ đọc cho các màn hình Dashboard đang khoá `pending_module`.

## Tệp đã tạo

1. `docs/implementation/read-screens/plan.md`
2. `docs/implementation/read-screens/slices.md`
3. `docs/delivery-evidence/impl-plan-read-screens/report.md`

## Lệnh đã chạy

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| `git diff --check` (bước 27) | 0 | Không có lỗi khoảng trắng, không có khoảng trắng thừa cuối dòng, kết thúc tệp bằng đúng một dòng mới. |
| Lệnh kiểm bắt buộc (bước 28, chạy bằng interpreter khóa `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/33f06a7a/venv/Scripts/python.exe`) | 0 | Lệnh kiểm bắt buộc đạt: slices.md có 13 id RS duy nhất, mỗi từ khóa bắt buộc xuất hiện đủ số lần, plan.md nêu đủ 11 màn hình và 3 gói sửa của chủ sở hữu, có chữ tiếng Việt có dấu, không có ký tự thay thế U+FFFD. |
| Probe bổ sung (bước 29, chạy bằng interpreter khóa) | 0 | Probe bổ sung đạt: đúng 13 slice RS-1..RS-13; plan.md có đủ CP-4-WIRING-FIX3, ADAPT-PROD-FIX3, CP-4B-UI-SCREENS-FIX3, BL-RS-01, BL-RS-02, pending_module, RS-13; mỗi slice đủ requirement, instrument, counterexample; cả hai tệp có tiếng Việt có dấu và UTF-8 không BOM. |

## Kết luận khảo sát

- Mười tài nguyên được nối: `articles`, `events`, `media` (chỉ đọc), `artifacts`, `snapshots`, `story-angles`, `scripts`, `sessions`, `accounts`, `cost`.
- `logs` giữ `pending_module` vì chưa có nguồn có mức độ và thông điệp thật (BL-RS-02).
- Khảo sát các bảng đã có migration và repository/mã đọc sẵn có:
  - `articles`: `cp_articles` và `cp_article_revisions` (`0013_ingestion.sql`), repository `PostgresArticleRepository`.
  - `events`: `cp_events` (`0013_ingestion.sql`), repository `PostgresEventRepository`.
  - `media`: `cp_media_assets` (`0014_catalog.sql`), repository `PostgresMediaAssetRepository`, chỉ đọc (tags/notes không có).
  - `artifacts`: `cp_artifact_versions` và `cp_artifact_locations` (`0005_artifact_metadata.sql`, `0010_storage_meta_extensions.sql`), `PostgresStorageMetaRepository`.
  - `snapshots`: `cp_production_snapshots` (`0015_creative.sql`), repository `PostgresSnapshotRepository`.
  - `story-angles`: `cp_story_angles` và `cp_story_angle_sets` (`0015_creative.sql`), `PostgresAppendOnlyRepository`.
  - `scripts`: `cp_script_versions` (`0015_creative.sql`), repository `PostgresScriptRepository`.
  - `sessions`: `cp_app_sessions` (`0011_orchestration_extensions.sql`).
  - `accounts`: `cp_external_accounts` (`0009_config_security_extensions.sql`).
  - `cost`: `cp_cost_records` (`0009_config_security_extensions.sql`), `PostgresCostLedger`.

## Đã đọc lại

- Xác nhận đã đọc lại `docs/implementation/read-screens/plan.md` và `docs/implementation/read-screens/slices.md`:
  - Toàn bộ nội dung tiếng Việt có đầy đủ dấu.
  - Không có ký tự thay thế `U+FFFD` (`?`).
  - Tệp lưu định dạng UTF-8 không BOM.
  - Đầy đủ 13 slice RS-1..RS-13 và các gói sửa của chủ sở hữu (CP-4-WIRING-FIX3, ADAPT-PROD-FIX3, CP-4B-UI-SCREENS-FIX3).

## Xử lý finding F1 (vòng AUDIT_FAIL)

- **Nội dung finding F1**: `test_route_inventory` (`tests/integration/convergence/test_cp4_queries_routes.py:188-207`, vòng ghim vắng ở dòng 205, `assert matching == []` ở dòng 207) sẽ đỏ khi CP-4-WIRING-FIX3 thêm `articles`, `events`, `sessions`, trong khi bản kế hoạch trước đó ghi 'không có test cần đổi'.
- **Cách sửa trong plan.md**:
  - Mục 3.4: chèn bullet ghim `test_route_inventory` (`test_cp4_queries_routes.py:188-207`), chỉ rõ vòng ghim vắng dòng 205 và khẳng định CP-4-WIRING-FIX3 phải đổi test này trong cùng gói.
  - Mục 7.1: cập nhật dòng Tệp (thêm `test_cp4_queries_routes.py:205-207`), lệnh kiểm (thêm `test_cp4_queries_routes.py` vào lệnh pytest của gói trên cùng một dòng), bullet Phụ thuộc (nêu rõ có test ghim vắng route là `test_route_inventory`), và thay toàn bộ bullet 'Test đang ghim cần đổi' để nêu chi tiết thay đổi chính xác dòng 205 thành `('logs', 'capabilities')` và thêm vòng lặp kiểm tra mười tài nguyên mới.
  - Mục 8: cập nhật bước 5 và đoạn Lý do thứ tự nêu rõ `test_route_inventory` được nới trong chính gói ở bước 5.
  - Mục 11: cập nhật phần đối chiếu counterexample nêu rõ `test_route_inventory` được đổi và chạy ngay trong CP-4-WIRING-FIX3.
- **Phạm vi sửa đổi**: Không sửa `src/**` hay `tests/**` trong gói này; test chỉ được nới ở CP-4-WIRING-FIX3 do Control lập sau khi Auditor rủi ro duyệt kế hoạch.

### Bảng lệnh kiểm mục tiêu F1 và kiểm tra bắt buộc

| Lệnh | Mã thoát | Kết quả |
| --- | --- | --- |
| `git diff --check && python -c "import pathlib, re, unicodedata; p = unicodedata.normalize('NFC', pathlib.Path('docs/implementation/read-screens/plan.md').read_text(encoding='utf-8')); s = p.split('### 7.1.')[1].split('### 7.2.')[0]; assert 'test_route_inventory' in s and 'test_cp4_queries_routes.py:20' in s, 'F1 pin'; assert re.search('pytest[^' + chr(10) + ']*test_cp4_queries_routes[.]py', s), 'F1 cmd'; assert 'ghim cần đổi: không có' not in s, 'F1 claim'; assert 'không có test nào ghim 404' not in p and 'chưa có test ghim 404' not in p, 'F1 stale 404 claim'"` | 0 | Đạt: git diff không lỗi khoảng trắng; mục 7.1 nêu test_route_inventory, test_cp4_queries_routes.py:205-207; lệnh pytest có test_cp4_queries_routes.py; không còn câu sai 'ghim cần đổi: không có' hay 'không có test nào ghim 404'. |
| `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/read-screens'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (RS-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert all(k in p for k in ['articles', 'events', 'media', 'artifacts', 'snapshots', 'story-angles', 'scripts', 'sessions', 'accounts', 'cost', 'logs']), 'plan covers every screen'; assert all(k in p for k in ['CP-4-WIRING', 'ADAPT-PROD', 'CP-4B-UI-SCREENS']), 'plan names the owner fix packages'; assert re.search('[Ạ-ỹ]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt: 13 slice RS-1..RS-13 duy nhất, đầy đủ các thuộc tính bắt buộc, plan bao phủ 11 màn và 3 gói sửa, tiếng Việt đủ dấu, không có ký tự thay thế U+FFFD. |

## Giới hạn

- Đây là tài liệu kế hoạch, chưa chạy test PostgreSQL, chưa sửa `src/**`, `tests/**` hay `ui/dist`.
- Các mục GIẢ ĐỊNH nằm ở mục 10 của plan.md và chưa được duyệt.
- Không ghi bí mật, không ghi PASS cho điều chưa chạy.

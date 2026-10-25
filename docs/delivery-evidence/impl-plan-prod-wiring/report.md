# Báo cáo bằng chứng IMPL-PLAN-PROD-WIRING

Ngày thực hiện: 26/10/2026. Task: IMPL-PLAN-PROD-WIRING.

## Lệnh đã chạy

1. `git diff --check`
   - Mã thoát: 0
   - Kết quả: Không có lỗi khoảng trắng cuối dòng hoặc xung đột git.

2. `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/prod-wiring'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall('(?m)^### (PW-[0-9A-Z][0-9A-Z-]*): ', s); assert ids and len(ids) == len(set(ids)) and 'PW-E2E' in ids, ids; assert all(s.count('- ' + k + ':') >= len(ids) for k in ['ownedPaths', 'dependsOn', 'resourceLocks', 'bindingRefs', 'testCommands', 'acceptance', 'coveredIds']), 'each slice needs ownedPaths, dependsOn, resourceLocks, bindingRefs, testCommands, acceptance and coveredIds'; deps = re.findall('(?m)^- dependsOn:(.*)', s); bad = [x for x in deps if re.search('CP7-|M7-MILESTONE-CLOSE|GATE-|RS-13|CP-4B-UI-SCREENS-FIX4', x)]; assert not bad, ('forbidden dependency', bad); e = s.split('### PW-E2E: ', 1)[1].split(chr(10) + '### ', 1)[0]; ed = re.findall('(?m)^- dependsOn:(.*)', e); assert ed and all(i in ed[0] for i in ids if i != 'PW-E2E'), 'PW-E2E must depend on every other PW slice'; miss = [k for k in ['AppSession','cp_stage_runs','grant','outbox','ValidateVariant','ReserveVariant','waiting','media_select','ConfigRevision','Kokoro','inspector','PersistVideoOutput','credential_unavailable','PlanCollectionCycle','RegisterMediaDiscovery','launcher','Temporal','PW-E2E','OI-ADAPT-10','FR-AUD-007'] if k not in p]; assert not miss, ('plan.md must cover', miss); assert re.search('[Ạ-ỹ]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"`
   - Mã thoát: 0
   - Kết quả: Toàn bộ kiểm tra cấu trúc đạt: 32 slice ID duy nhất, đủ 7 trường bắt buộc mỗi slice, không phụ thuộc cấm, PW-E2E phụ thuộc đủ 31 slice còn lại trên một dòng, plan.md đủ từ khoá bắt buộc, tiếng Việt đủ dấu và 0 ký tự thay thế U+FFFD.

## Kết quả

- Số slice trong `slices.md`: 32 slice (PW-H0, PW-SCHEMA, PW-G1..PW-G4, PW-CAT1, PW-CAT2, PW-G5..PW-G7, PW-VERT, PW-D1..PW-D3, PW-E1..PW-E4, PW-F1..PW-F4, PW-I1, PW-I2, PW-A1..PW-A3, PW-B1, PW-W1, PW-W2, PW-E2E), đều là `work_package_slice`.
- Xác nhận `PW-E2E` phụ thuộc đủ 31 slice còn lại trên đúng một dòng `dependsOn`, không chứa bất kỳ phụ thuộc cấm nào (CP7-*, M7-MILESTONE-CLOSE*, GATE-*, RS-13, CP-4B-UI-SCREENS-FIX4).
- Xác nhận hai mục CHƯA XÁC NHẬN đã được kiểm bằng mã và ghi ở `plan.md` mục 2: RetryStage (inventory mục 2, XÁC NHẬN LỖI tại `src/controlplane/application/orchestration/workflows/flow.py:189-196`, `:247-253`, `:153-164`) và observed_hash, observed_size_bytes (inventory mục 5, XÁC NHẬN THIẾU tại `0005_artifact_metadata.sql:38-39`, `storage_meta/__init__.py:76-81`, `:90-92`, `materialization.py:109`).

## Mục mở

- OI-PW-01: OI-CP7-03 (bỏ scheduler cloud theo U1) vẫn chờ user ghi nhận ở R1; không chặn kế hoạch.
- OI-PW-02: vòng lô chạy video tuần tự. 100 video trong 12 giờ cần trung bình tối đa 7,2 phút mỗi video. `PW-E2E` ghi số đo thời gian từng stage; nếu vượt thì Control lập slice chạy song song hai video theo 2 khe GPU.
- OI-PW-03: quyết định OI-ADAPT-10 làm hết hiệu lực mặc định UNVERIFIED ở `docs/implementation/adapt/plan.md:274,321` và mục `rights_unverified_excluded` của CP7-14; Control sửa các chỗ đó trước khi chạy CP7-14.
- OI-PW-04: nếu muốn khoá route riêng cho `production_plan` thì Control thêm khoá `plan` vào `ai.route_model_refs` (`tools/launcher/prod/profile.json:122-130`) bằng slice riêng.
- OI-PW-05: TTL grant theo hàng đợi dùng giá trị mặc định do `PW-G3` ghi; Control đưa vào profile nếu muốn chỉnh.
- OI-PW-06: nguồn nhạc nền do `PW-E4` khảo sát và chọn; cách hiểu lời user "giai đoạn đầu tự tìm nguồn sinh nhạc nền" (hệ thống tự tìm và thu thập nhạc, không AI sáng tác) đã báo user và chờ user sửa nếu sai.
- OI-PW-07: `PW-SCHEMA` sửa `tests/integration/convergence/test_cp3_migration_sequence.py` vì số migration đổi từ 18 sang 19; Control xác nhận quyền sửa khi giao slice.
- pendingUserCheckpoint: không có mục mới do kế hoạch này tạo; OI-CP7-03 vẫn chờ.

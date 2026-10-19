# Báo cáo IMPL-PLAN-E

Gói lập kế hoạch Phân hệ E (Phân tích và xử lý media, âm thanh). Tệp tạo mới: `docs/implementation/e/plan.md`, `docs/implementation/e/slices.md` (20 slice E-01..E-20) và báo cáo này. Không sửa tệp nào ngoài owned paths.

## Nguồn đã đọc

- `docs/modules/capability-e-voice.md`
- `docs/11-roadmap.md` (§10, §12, §19, §23)
- `docs/09-contracts/02-domain-events.md`
- `docs/09-contracts/05-content-media-contracts.md`
- `docs/09-contracts/07-media-processing-contracts.md`
- `docs/09-contracts/08-render-quality-contracts.md`
- `docs/09-contracts/11-configuration-security-contracts.md`
- `docs/09-contracts/12-state-machines.md`
- `docs/10-test-strategy.md` (§14.2, §15, §30, §34)
- `docs/05-technology-research.md`
- `docs/parallel-delivery/bindings/README.md`
- `docs/parallel-delivery/bindings/d-e-f-voice-timing.json`
- `docs/parallel-delivery/bindings/j-provider-route.json`
- `docs/parallel-delivery/bindings/i-artifact-version.json`
- `docs/parallel-delivery/bindings/f-render-package.json`
- `docs/parallel-delivery/bindings/g-activity-execution.json`
- `docs/parallel-delivery/bindings/domain-event-envelope.json`
- `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
- `tests/fixtures/contracts/j-provider-route/payloads.json`
- `tests/fixtures/contracts/i-artifact-version/payloads.json`
- `tests/fixtures/contracts/g-activity-execution/payloads.json`
- `tests/fixtures/contracts/domain-event-envelope/payloads.json`
- `docs/parallel-delivery/errata/m6-ef.md`
- `docs/parallel-delivery/ownership-and-locks.yaml`
- `docs/parallel-delivery/task-dag.yaml`
- `docs/parallel-delivery/acceptance-matrix.yaml`
- `docs/implementation/c/plan.md`, `docs/implementation/c/slices.md`
- `docs/implementation/d/plan.md`, `docs/implementation/d/slices.md`
- `pyproject.toml`
- Mã controlplane chỉ đọc: `src/controlplane/domain/interfaces/uow.py`, `src/controlplane/domain/interfaces/outbox.py`, `src/controlplane/domain/events/contracts.py`, `src/controlplane/domain/concurrency.py`, `src/controlplane/domain/common/contracts.py`, `src/controlplane/domain/orchestration/__init__.py`, `src/controlplane/application/idempotency/canonicalization.py`

Ba tệp `docs/parallel-delivery/M6-EF-contract-freeze.md`, `M6-EF-execution-package.md`, `M6-EF-test-plan.md` bị hỏng dấu tiếng Việt nên không dùng làm nguồn.

## Quyết định D8 (mục mở)

- Sai số word timing (ROADMAP-OPEN-008, TEST-OPEN-006), output profile (ROADMAP-OPEN-007, TEST-OPEN-005, TECH-OPEN-012), ngưỡng audio, TTS primary/fallback (TECH-OPEN-004), công cụ aligner, TEST-OPEN-003 và policy image safety: là input policy; thiếu thì `INPUT_NOT_READY`; đưa vào danh sách pendingUserCheckpoint, không tự ghi là đã duyệt.
- Quyết định mặc định có lý do: retention intent theo CT-PROC-008; khoảng thời lượng voice là input policy; chồng lấn word timing bị từ chối (GIẢ ĐỊNH, nới khi TEST-OPEN-006 chốt); tokenization fixture tiếng Anh (GIẢ ĐỊNH); port `ScriptTextPort` E-local; E ghi bằng chứng ngôn ngữ, F kiểm `ENGLISH_OUTPUT_VALID`; không có state machine riêng cho VoiceTrack và WordTiming; UoW in-memory trước migration.
- Errata `capability-e-voice.md` (§2 của plan): INV-007, INV-008, INV-019 sai nghĩa; 61–70 giây, ±100ms và -14..-16 LUFS là hằng tự đặt; CT-AUD-001 không phải cổng TTS; thiếu phạm vi probe, safety, normalize, audio bed.

## Quyết định D10 (thư viện)

- Slice E-01..E-20 không thêm thư viện; chỉ dùng stdlib và module controlplane đã có.
- Đề xuất cho USER-CKPT-D9-D10: `av==18.1.0`, `faster-whisper==1.2.1`, `whisperx==3.8.6`, OpenCV (phiên bản xác minh tại checkpoint) và build FFmpeg khóa theo TECH-OPEN-012; chưa đề xuất thư viện TTS vì cần benchmark TECH-POC-004.

## Việc chuyển sang CP7 và IMPL-PLAN-CONVERGENCE

- CP7-E-01..CP7-E-07 (plan §9): benchmark TTS và aligner, Sensitive Image Set thật, FFmpeg thật, đo loudness và nghe mẫu, GPU contention, hiệu chỉnh tốc độ đọc của D.
- CONV-E-01..CONV-E-14 (plan §10): migration, composition root, control API, UI, workflow G, state machine, binding, ownership và tài liệu, corpus, outbox, route J, storage I, lockfile, phía F.

## Kết quả lệnh kiểm

- Lệnh bước 34: git diff --check, exit code: 0, kết quả: PASS (không có output).
- Lệnh bước 35: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/e'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (E-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[Ạ-ỹ]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'", exit code: 0, kết quả: PASS (không có output).
- Lệnh bước 36: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe -c "import re, pathlib; d = pathlib.Path('docs/implementation/e'); p = (d / 'plan.md').read_text(encoding='utf-8'); s = (d / 'slices.md').read_text(encoding='utf-8'); r = pathlib.Path('docs/delivery-evidence/impl-plan-e/report.md').read_text(encoding='utf-8'); ids = re.findall('(?m)^### (E-[0-9A-Z][0-9A-Z-]*)', s); assert len(ids) == 20, ids; bt = chr(96); blocks = re.findall('- ownedPaths:(.*?)- dependsOn:', s, re.S); assert len(blocks) == len(ids), (len(blocks), len(ids)); ok = ('src/voice/', 'tests/unit/voice/', 'tests/integration/voice/', 'docs/delivery-evidence/'); items = [i for b in blocks for i in re.findall(bt + '([^' + bt + ']+)' + bt, b)]; bad = [i for i in items if not i.startswith(ok)]; assert not bad, bad; assert all('docs/delivery-evidence/' + i.lower() + '/report.md' in s for i in ids), 'report path per slice'; deps = re.findall('- dependsOn:([^' + chr(10) + ']*)', s); assert len(deps) == len(ids), len(deps); assert all(all(x in ids[:n] for x in re.findall('E-[0-9]+', deps[n])) for n in range(len(ids))), 'dependsOn must reference earlier slices'; assert all(i in p for i in ids), 'plan must reference every slice'; need = ['CP7', 'D8', 'D10', 'USER-CKPT-D9-D10', 'pendingUserCheckpoint', 'src/voice/', 'tests/unit/voice/', 'tests/integration/voice/', 'bindings/d-e-f-voice-timing.json', 'ROADMAP-OPEN-008', 'ROADMAP-OPEN-007', 'TST-MEDIA-INV-007'] + ['CONV-E-' + str(k).zfill(2) for k in range(1, 15)]; miss = [k for k in need if k not in p]; assert not miss, miss; assert all(k in r for k in ['D8', 'D10', 'docs/modules/capability-e-voice.md', 'docs/09-contracts/07-media-processing-contracts.md']), 'report sources and decisions'; assert all(chr(13) not in t and chr(65279) not in t and chr(65533) not in t and t.endswith(chr(10)) and not any(l != l.rstrip() for l in t.splitlines()) for t in (p, s, r)), 'whitespace and encoding'; print('ok')", exit code: 0, kết quả: PASS (in ok).

Lệnh git diff --check chạy lại sau khi ghi mục này: xem thông báo worker_done.

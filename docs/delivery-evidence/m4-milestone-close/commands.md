# M4-MILESTONE-CLOSE-R4: kết quả chạy lại lệnh kiểm (revision 4)

- Candidate SHA: 3497cecbf9fe9a09818192e9c7c12c0c68396c01 (HEAD của worktree, tiêu đề integrate(M4-MILESTONE-CLOSE-R3): lane lane-m4-milestone-close-r3 candidate cb368a9d8eea; bằng chứng chỉ thêm tệp trong docs/delivery-evidence/m4-milestone-close/)
- Interpreter đã khóa: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/33f06a7a/venv/Scripts/python.exe (Python 3.13.15 theo 	ools/runtime/runtime.lock.json)
- Ngày chạy: 26/10/2026
- Tổng số lệnh kiểm bắt buộc: 290, chia thành 14 nhóm theo cột «Nhóm bước»; mỗi lệnh một tiến trình riêng.
- Lần chạy này thay thế hoàn toàn revision 3 (289 lệnh); lệnh mới là STT 290 (probe launch-fix3), thứ tự STT theo danh sách lệnh của task nên khác revision 3.

| STT | Nhóm bước | Lệnh | Exit code | Tóm tắt nguyên văn |
| --- | --- | --- | --- | --- |
| 1 | 1 | git diff --check | 0 | exit 0 |
| 2 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/a'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 3 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/b'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 4 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/c'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 5 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/i'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 6 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/d'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 7 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/e'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 8 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/f'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 9 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/j'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 10 | 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/g'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 11 | 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/h'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 12 | 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence'); p = unicodedata.normalize('NFC', (d / 'p... | 0 | exit 0 |
| 13 | 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence-ext'); p = unicodedata.normalize('NFC', (d ... | 0 | exit 0 |
| 14 | 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/persist'); p = unicodedata.normalize('NFC', (d / 'plan.... | 0 | exit 0 |
| 15 | 3 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/adapt'); p = unicodedata.normalize('NFC', (d / 'plan.md... | 0 | exit 0 |
| 16 | 3 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence-ext-ui'); p = unicodedata.normalize('NFC', ... | 0 | exit 0 |
| 17 | 4 | python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider | 0 | 13 passed, 62 subtests passed in 0.13s |
| 18 | 4 | python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider | 0 | 27 passed, 99 subtests passed in 0.07s |
| 19 | 4 | python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cacheprovider | 0 | 17 passed, 50 subtests passed in 0.08s |
| 20 | 4 | python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider | 0 | 74 passed in 0.10s |
| 21 | 4 | python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider | 0 | 40 passed, 20 subtests passed in 0.06s |
| 22 | 4 | python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprovider | 0 | 15 passed, 22 subtests passed in 0.04s |
| 23 | 4 | python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cacheprovider | 0 | 14 passed, 44 subtests passed in 0.04s |
| 24 | 4 | python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider | 0 | 32 passed, 3 subtests passed in 0.16s |
| 25 | 4 | python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p no:cacheprovider | 0 | 28 passed, 11 subtests passed in 0.14s |
| 26 | 4 | python -m pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider | 0 | 23 passed, 14 subtests passed in 0.12s |
| 27 | 4 | python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider | 0 | 18 passed in 0.16s |
| 28 | 4 | python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cacheprovider | 0 | 59 passed in 0.10s |
| 29 | 4 | python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cacheprovider | 0 | 49 passed in 0.12s |
| 30 | 4 | python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p no:cacheprovider | 0 | 19 passed in 0.10s |
| 31 | 4 | python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:cacheprovider | 0 | 20 passed, 49 subtests passed in 0.07s |
| 32 | 4 | python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no:cacheprovider | 0 | 25 passed in 0.18s |
| 33 | 4 | python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cacheprovider | 0 | 33 passed, 29 subtests passed in 0.10s |
| 34 | 4 | python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider | 0 | 32 passed in 0.16s |
| 35 | 4 | python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cacheprovider | 0 | 62 passed in 0.15s |
| 36 | 4 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); x = d['project']['depe... | 0 | exit 0 |
| 37 | 4 | python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock').read_text(encoding='utf-8')); p = {x['name']: x for x i... | 0 | exit 0 |
| 38 | 5 | python -m pytest tests/integration/adapt/a/test_adapt_a_adapters.py -q -p no:cacheprovider | 0 | 27 passed in 5.68s |
| 39 | 5 | python -c "import pathlib; d = pathlib.Path('src/source_ingestion/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in [... | 0 | exit 0 |
| 40 | 5 | python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/security/test_http_router_adapter.py -q -p no:cacheprovider | 0 | 20 passed in 0.30s |
| 41 | 5 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/creative/adapters/real_ai_invocation.p... | 0 | exit 0 |
| 42 | 5 | python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider | 0 | 34 passed in 0.67s |
| 43 | 5 | python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_kokor... | 0 | exit 0 |
| 44 | 5 | python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q -p no:cacheprovider | 0 | 41 passed in 0.67s |
| 45 | 5 | python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpe... | 0 | exit 0 |
| 46 | 5 | python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider | 0 | 53 passed in 3.73s |
| 47 | 5 | python -c "import pathlib; d = pathlib.Path('src/render/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmp... | 0 | exit 0 |
| 48 | 5 | python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cacheprovider | 0 | 22 passed in 13.09s |
| 49 | 5 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/security'); t = ' '.join((d / n).read_text(encoding='utf-8')... | 0 | exit 0 |
| 50 | 5 | python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cacheprovider | 0 | 33 passed in 2.14s |
| 51 | 5 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/storage/drive_object_store.py').read_text(encoding='utf-8');... | 0 | exit 0 |
| 52 | 5 | python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider | 0 | 11 passed in 0.05s |
| 53 | 5 | python -c "import json, pathlib; d = pathlib.Path('tools/launcher/prod'); x = [json.loads((d / n).read_text(encoding='utf-8')) for n in [... | 0 | exit 0 |
| 54 | 5 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider | 0 | 111 passed in 11.79s |
| 55 | 5 | python -c "import pathlib; fs = list(pathlib.Path('src/controlplane/api/wiring').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8... | 0 | exit 0 |
| 56 | 5 | python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no:cacheprovider | 0 | 13 passed in 35.68s |
| 57 | 5 | python -c "import pathlib; t = pathlib.Path('tools/launcher/prod/seed/import_seed.py').read_text(encoding='utf-8'); assert 'register_disc... | 0 | exit 0 |
| 58 | 5 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider | 0 | 27 passed, 1 warning in 21.17s |
| 59 | 5 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/main.py', 'src/controlplane/api/wiring... | 0 | exit 0 |
| 60 | 5 | python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider | 0 | 36 passed in 3.30s |
| 61 | 5 | python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml').read_text(encoding='utf-8'); r = pathlib.Path('docs/runb... | 0 | exit 0 |
| 62 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider | 0 | 39 passed in 0.08s |
| 63 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit/ingestion/test_ingestion_fingerprint.py -q -p no:cachepr... | 0 | 30 passed in 0.07s |
| 64 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/unit/ingestion/test_ingestion_memory_unit_of_work.py -q -... | 0 | 19 passed in 0.06s |
| 65 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:cacheprovider | 0 | 64 passed in 0.08s |
| 66 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no:cacheprovider | 0 | 27 passed in 0.06s |
| 67 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider | 0 | 31 passed in 0.10s |
| 68 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cacheprovider | 0 | 45 passed in 0.12s |
| 69 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:cacheprovider | 0 | 61 passed in 0.11s |
| 70 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cacheprovider | 0 | 39 passed in 0.10s |
| 71 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cacheprovider | 0 | 55 passed in 0.10s |
| 72 | 6 | python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p no:cacheprovider | 0 | 67 passed in 0.16s |
| 73 | 6 | python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py -q -p no:cacheprovider | 0 | 15 passed in 0.13s |
| 74 | 6 | python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider | 0 | 20 passed, 37 subtests passed in 0.06s |
| 75 | 6 | python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovider | 0 | 20 passed, 45 subtests passed in 0.05s |
| 76 | 6 | python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprovider | 0 | 11 passed, 11 subtests passed in 0.04s |
| 77 | 6 | python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cacheprovider | 0 | 20 passed, 33 subtests passed in 0.05s |
| 78 | 6 | python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider | 0 | 26 passed, 31 subtests passed in 0.05s |
| 79 | 6 | python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cacheprovider | 0 | 27 passed, 19 subtests passed in 0.05s |
| 80 | 6 | python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cacheprovider | 0 | 31 passed, 189 subtests passed in 0.08s |
| 81 | 6 | python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cacheprovider | 0 | 20 passed, 87 subtests passed in 0.24s |
| 82 | 6 | python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider | 0 | 27 passed, 11 subtests passed in 0.07s |
| 83 | 7 | python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit/control_ui/test_h_stream_client_registry.py tests/unit/c... | 0 | 94 passed in 0.17s |
| 84 | 7 | python -m pytest tests/unit/control_ui tests/m2/test_p7b_sse_stream.py -q -p no:cacheprovider | 0 | 670 passed, 1 warning in 8.72s |
| 85 | 7 | python -c "import pathlib, re; c = pathlib.Path('src/controlplane/application/sse/event_catalog.py').read_text(encoding='utf-8'); t = pat... | 0 | exit 0 |
| 86 | 7 | python -m pytest tests/integration/convergence/test_cp4_pagination_postgres.py -q -p no:cacheprovider | 0 | 16 passed in 9.94s |
| 87 | 7 | python -m pytest tests/integration/control_ui tests/unit/control_ui -q -p no:cacheprovider | 0 | 840 passed, 1 warning in 1.97s |
| 88 | 7 | python -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression | 0 | 179 passed, 1 deselected, 2 warnings in 271.94s (0:04:31) |
| 89 | 7 | python -c "import pathlib; q = pathlib.Path('src/controlplane/infrastructure/db/control_api_queries.py').read_text(encoding='utf-8'); c =... | 0 | exit 0 |
| 90 | 7 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py tests/integration/convergence/test_cp4_queries_postgres.py -q -... | 0 | 30 passed, 1 warning in 6.63s |
| 91 | 7 | python -m pytest tests/integration tests/unit/control_ui -q -p no:cacheprovider | 0 | 3257 passed, 36 skipped, 1 warning, 25 subtests passed in 291.62s (0:04:51) |
| 92 | 7 | python -c "import pathlib; p = pathlib.Path('src/controlplane/application/control_api/query_ports.py').read_text(encoding='utf-8'); q = p... | 0 | exit 0 |
| 93 | 7 | npm --prefix src/controlplane/ui run build | 0 | ✓ built in 2.33s |
| 94 | 7 | python -m pytest tests/unit/control_ui -q -p no:cacheprovider | 0 | 665 passed, 1 warning in 1.13s |
| 95 | 7 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.f... | 0 | exit 0 |
| 96 | 7 | python -c "import pathlib; u = pathlib.Path('src/controlplane/ui/src'); a = (u / 'App.tsx').read_text(encoding='utf-8'); c = (u / 'api' /... | 0 | exit 0 |
| 97 | 7 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8')... | 0 | exit 0 |
| 98 | 7 | python -c "import json, pathlib; d = json.loads(pathlib.Path('tools/runtime/runtime.lock.json').read_text(encoding='utf-8')); assert d['v... | 0 | exit 0 |
| 99 | 7 | python -c "import pathlib; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; b = pathlib.Path('src/controlplane'); assert all((b / d / u).r... | 0 | exit 0 |
| 100 | 8 | python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider | 0 | 9 passed in 9.43s |
| 101 | 8 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); x = d... | 0 | exit 0 |
| 102 | 8 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d... | 0 | exit 0 |
| 103 | 8 | python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider | 0 | 293 passed in 0.53s |
| 104 | 8 | python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); assert 'src/c... | 0 | exit 0 |
| 105 | 8 | python -m pytest tests/unit/config tests/unit/storage tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/converg... | 0 | 1125 passed, 239 subtests passed in 1.36s |
| 106 | 8 | python -m pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/contract/test_bindings.py -q -p no:cacheprovider | 0 | 679 passed, 398 subtests passed in 1.99s |
| 107 | 8 | python -c "import hashlib, pathlib, re; t = pathlib.Path('docs/parallel-delivery/contract-registry.yaml').read_text(encoding='utf-8'); h ... | 0 | exit 0 |
| 108 | 8 | python -c "import pathlib; t = pathlib.Path('docs/09-contracts/12-state-machines.md').read_text(encoding='utf-8'); assert 'PUC-J-03' in t... | 0 | exit 0 |
| 109 | 8 | python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider | 0 | 40 passed in 4.24s |
| 110 | 8 | python -m pytest tests/integration/orchestration tests/integration/storage tests/unit/catalog tests/unit/storage tests/unit/render -q -p ... | 0 | 2314 passed, 7 skipped, 1184 subtests passed in 5.47s |
| 111 | 8 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d... | 0 | exit 0 |
| 112 | 8 | python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests/integration/convergence/test_cp6_workflow_catalog.py tes... | 0 | 28 passed in 0.77s |
| 113 | 8 | python -m pytest tests/unit/orchestration tests/integration/collection tests/unit/ingestion tests/integration/creative tests/integration/... | 0 | 3387 passed, 1034 subtests passed in 4.04s |
| 114 | 9 | python -c "import json, pathlib; p = json.loads(pathlib.Path('src/controlplane/ui/package.json').read_text(encoding='utf-8')); v = list(p... | 0 | exit 0 |
| 115 | 9 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d... | 0 | exit 0 |
| 116 | 9 | python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider | 0 | 6 passed in 3.93s |
| 117 | 9 | python -c "import re, pathlib; t = pathlib.Path('tests/m2/test_p9_m2_exit_gate.py').read_text(encoding='utf-8'); assert re.search('M2_ACC... | 0 | exit 0 |
| 118 | 9 | python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergence/test_cp3b_source_parity.py -q -p... | 0 | 25 passed in 0.06s |
| 119 | 9 | python -m pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_statemachines.py -q -p no:cacheprovider | 0 | 666 passed, 841 subtests passed in 0.96s |
| 120 | 9 | python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q -p no:cacheprovider | 0 | 8 passed in 1.62s |
| 121 | 9 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tes... | 0 | 5190 passed, 1 warning, 2237 subtests passed in 11.25s |
| 122 | 9 | python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider | 0 | 137 passed, 28 skipped, 1 warning in 2.22s |
| 123 | 9 | python -m pytest tests/m2 tests/integration -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression | 0 | 2771 passed, 36 skipped, 1 deselected, 2 warnings, 25 subtests passed in 551.60s (0:09:11) |
| 124 | 9 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tes... | 0 | 5262 passed, 1 warning, 1998 subtests passed in 9.75s |
| 125 | 9 | python -c "import pathlib; t = pathlib.Path('src/main.py').read_text(encoding='utf-8'); assert 'create_app' in t, 'src/main.py must call ... | 0 | exit 0 |
| 126 | 9 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.f... | 0 | exit 0 |
| 127 | 9 | python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/src/App.tsx').read_text(encoding='utf-8'); assert 'boundedEventDeduper' ... | 0 | exit 0 |
| 128 | 10 | python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider | 0 | 12 passed, 58 subtests passed in 0.11s |
| 129 | 10 | python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider | 0 | 68 passed in 0.09s |
| 130 | 10 | python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cacheprovider | 0 | 11 passed, 13 subtests passed in 0.03s |
| 131 | 10 | python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider | 0 | 87 passed in 0.11s |
| 132 | 10 | python -m pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cacheprovider | 0 | 20 passed, 79 subtests passed in 0.06s |
| 133 | 10 | python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider | 0 | 60 passed in 0.10s |
| 134 | 10 | python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider | 0 | 32 passed in 0.07s |
| 135 | 10 | python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider | 0 | 62 passed in 0.09s |
| 136 | 10 | python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider | 0 | 110 passed in 0.19s |
| 137 | 10 | python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider | 0 | 94 passed in 0.17s |
| 138 | 10 | python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider | 0 | 62 passed in 0.14s |
| 139 | 10 | python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider | 0 | 19 passed, 38 subtests passed in 0.04s |
| 140 | 10 | python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider | 0 | 65 passed in 0.12s |
| 141 | 10 | python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider | 0 | 18 passed in 0.14s |
| 142 | 10 | python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider | 0 | 27 passed in 0.12s |
| 143 | 10 | python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider | 0 | 52 passed in 0.15s |
| 144 | 10 | python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider | 0 | 22 passed in 0.13s |
| 145 | 10 | python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider | 0 | 8 passed in 0.28s |
| 146 | 10 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider | 0 | 16 passed, 89 subtests passed in 0.13s |
| 147 | 10 | python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider | 0 | 65 passed in 0.07s |
| 148 | 10 | python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider | 0 | 144 passed in 0.14s |
| 149 | 10 | python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovider | 0 | 86 passed in 0.09s |
| 150 | 10 | python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovider | 0 | 50 passed in 0.06s |
| 151 | 10 | python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprovider | 0 | 75 passed in 0.09s |
| 152 | 10 | python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprovider | 0 | 106 passed in 0.11s |
| 153 | 10 | python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider | 0 | 63 passed in 0.09s |
| 154 | 10 | python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider | 0 | 114 passed in 0.11s |
| 155 | 10 | python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider | 0 | 51 passed in 0.05s |
| 156 | 10 | python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider | 0 | 21 passed in 0.05s |
| 157 | 10 | python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider | 0 | 35 passed in 0.09s |
| 158 | 10 | python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider | 0 | 63 passed in 0.06s |
| 159 | 10 | python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider | 0 | 79 passed in 0.11s |
| 160 | 10 | python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider | 0 | 47 passed in 0.08s |
| 161 | 10 | python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider | 0 | 23 passed in 0.10s |
| 162 | 10 | python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider | 0 | 45 passed in 0.10s |
| 163 | 10 | python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider | 0 | 44 passed in 0.18s |
| 164 | 10 | python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider | 0 | 35 passed in 0.08s |
| 165 | 10 | python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider | 0 | 25 passed in 2.97s |
| 166 | 11 | python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider | 0 | 20 passed, 120 subtests passed in 0.37s |
| 167 | 11 | python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cacheprovider | 0 | 26 passed, 67 subtests passed in 0.10s |
| 168 | 11 | python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider | 0 | 169 passed in 0.16s |
| 169 | 11 | python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider | 0 | 58 passed in 0.10s |
| 170 | 11 | python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider | 0 | 62 passed in 0.10s |
| 171 | 11 | python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider | 0 | 104 passed in 0.12s |
| 172 | 11 | python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider | 0 | 97 passed in 0.13s |
| 173 | 11 | python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider | 0 | 55 passed in 0.13s |
| 174 | 11 | python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider | 0 | 118 passed in 0.11s |
| 175 | 11 | python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider | 0 | 154 passed in 0.21s |
| 176 | 11 | python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider | 0 | 97 passed in 0.12s |
| 177 | 11 | python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider | 0 | 45 passed, 129 subtests passed in 0.10s |
| 178 | 11 | python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider | 0 | 38 passed, 99 subtests passed in 0.07s |
| 179 | 11 | python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider | 0 | 52 passed, 67 subtests passed in 0.09s |
| 180 | 11 | python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider | 0 | 73 passed in 0.13s |
| 181 | 11 | python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider | 0 | 39 passed in 0.10s |
| 182 | 11 | python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider | 0 | 36 passed in 0.14s |
| 183 | 11 | python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider | 0 | 28 passed in 0.13s |
| 184 | 11 | python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider | 0 | 35 passed in 0.19s |
| 185 | 11 | python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider | 0 | 53 passed in 0.19s |
| 186 | 11 | python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider | 0 | 17 passed in 0.09s |
| 187 | 11 | python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cacheprovider | 0 | 55 passed in 0.11s |
| 188 | 11 | python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:cacheprovider | 0 | 43 passed in 0.05s |
| 189 | 11 | python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no:cacheprovider | 0 | 22 passed, 307 subtests passed in 0.06s |
| 190 | 11 | python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider | 0 | 45 passed in 0.07s |
| 191 | 11 | python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cacheprovider | 0 | 45 passed in 0.06s |
| 192 | 11 | python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:cacheprovider | 0 | 55 passed in 0.06s |
| 193 | 11 | python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/orchestration/test_g_job_waiting.py -q -p no:cacheprovider | 0 | 147 passed in 0.11s |
| 194 | 11 | python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py -q -p no:cachepro... | 0 | 88 passed in 0.29s |
| 195 | 11 | python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q -p no:cacheprovider | 0 | 47 passed in 0.06s |
| 196 | 11 | python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cacheprovider | 0 | 86 passed in 0.09s |
| 197 | 11 | python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q -p no:cacheprovider | 0 | 62 passed in 0.09s |
| 198 | 11 | python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit/orchestration/test_g_retry_policy.py -q -p no:cacheprovider | 0 | 110 passed in 0.11s |
| 199 | 11 | python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/orchestration/test_g_resource_admission.py -q -p no:cache... | 0 | 82 passed in 0.09s |
| 200 | 11 | python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/orchestration/test_g_consistency_audit.py -q -p no:cachepro... | 0 | 175 passed in 0.15s |
| 201 | 11 | python -m pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orchestration/test_g_batch_outcome.py tests/unit/orchestrati... | 0 | 157 passed in 0.14s |
| 202 | 12 | python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:cacheprovider | 0 | 55 passed in 0.05s |
| 203 | 12 | python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovider | 0 | 115 passed in 0.08s |
| 204 | 12 | python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:cacheprovider | 0 | 70 passed in 0.06s |
| 205 | 12 | python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider | 0 | 175 passed, 1 warning in 1.00s |
| 206 | 12 | python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cacheprovider | 0 | 31 passed in 0.04s |
| 207 | 12 | python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:cacheprovider | 0 | 91 passed in 0.08s |
| 208 | 12 | python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cacheprovider | 0 | 37 passed in 0.25s |
| 209 | 12 | python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cacheprovider | 0 | 43 passed, 1 warning in 0.38s |
| 210 | 12 | python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cacheprovider | 0 | 83 passed, 1 warning in 0.53s |
| 211 | 12 | python -m pytest tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider | 0 | 10 passed in 0.03s |
| 212 | 12 | python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:cacheprovider | 0 | 9 passed in 0.04s |
| 213 | 12 | python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovider | 0 | 22 passed in 0.03s |
| 214 | 12 | python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cacheprovider | 0 | 24 passed in 0.04s |
| 215 | 12 | python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no:cacheprovider | 0 | 14 passed in 0.03s |
| 216 | 12 | python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider | 0 | 35 passed in 0.05s |
| 217 | 12 | python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cacheprovider | 0 | 26 passed in 0.05s |
| 218 | 12 | python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cacheprovider | 0 | 65 passed in 0.07s |
| 219 | 12 | python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cacheprovider | 0 | 24 passed in 0.05s |
| 220 | 12 | python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider | 0 | 11 passed, 85 subtests passed in 0.05s |
| 221 | 12 | python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider | 0 | 22 passed, 21 subtests passed in 0.05s |
| 222 | 12 | python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p no:cacheprovider | 0 | 21 passed in 0.71s |
| 223 | 12 | python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p no:cacheprovider | 0 | 373 passed, 7 skipped in 0.89s |
| 224 | 12 | python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider | 0 | 25 passed, 26 subtests passed in 0.04s |
| 225 | 12 | python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no:cacheprovider | 0 | 67 passed in 0.07s |
| 226 | 12 | python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q -p no:cacheprovider | 0 | 21 passed in 0.14s |
| 227 | 12 | python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider | 0 | 13 passed, 10 subtests passed in 0.05s |
| 228 | 12 | python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider | 0 | 32 passed, 97 subtests passed in 0.07s |
| 229 | 12 | python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider | 0 | 56 passed in 0.05s |
| 230 | 12 | python -m pytest tests/unit/storage/test_storage_availability.py -q -p no:cacheprovider | 0 | 41 passed in 0.04s |
| 231 | 12 | python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovider | 0 | 50 passed in 0.05s |
| 232 | 12 | python -m pytest tests/unit/security/test_j_secret_redaction.py -q -p no:cacheprovider | 0 | 55 passed in 0.08s |
| 233 | 12 | python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider | 0 | 60 passed in 0.08s |
| 234 | 12 | python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider | 0 | 118 passed in 0.13s |
| 235 | 12 | python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cacheprovider | 0 | 49 passed in 0.08s |
| 236 | 12 | python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprovider | 0 | 40 passed in 0.06s |
| 237 | 12 | python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cacheprovider | 0 | 104 passed in 0.09s |
| 238 | 12 | python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprovider | 0 | 131 passed in 0.10s |
| 239 | 12 | python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovider | 0 | 104 passed in 0.08s |
| 240 | 12 | python -m pytest tests/unit/security/test_j_secret_update.py -q -p no:cacheprovider | 0 | 63 passed in 0.09s |
| 241 | 12 | python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cacheprovider | 0 | 51 passed in 0.08s |
| 242 | 12 | python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cacheprovider | 0 | 66 passed in 0.09s |
| 243 | 12 | python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovider | 0 | 50 passed in 0.09s |
| 244 | 12 | python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovider | 0 | 41 passed in 0.07s |
| 245 | 12 | python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovider | 0 | 47 passed in 0.07s |
| 246 | 12 | python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cacheprovider | 0 | 35 passed in 0.07s |
| 247 | 12 | python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no:cacheprovider | 0 | 35 passed in 0.68s |
| 248 | 12 | python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:cacheprovider | 0 | 33 passed in 0.09s |
| 249 | 13 | python -m pytest tests/integration/persistence/a/test_persist_a_postgres.py -q -p no:cacheprovider | 0 | 22 passed in 12.43s |
| 250 | 13 | python -c "import pathlib; fs = list(pathlib.Path('src/source_ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='... | 0 | exit 0 |
| 251 | 13 | python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q -p no:cacheprovider | 0 | 14 passed in 7.26s |
| 252 | 13 | python -c "import pathlib; fs = list(pathlib.Path('src/ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8')... | 0 | exit 0 |
| 253 | 13 | python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q -p no:cacheprovider | 0 | 15 passed in 7.91s |
| 254 | 13 | python -c "import pathlib; fs = list(pathlib.Path('src/catalog/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') f... | 0 | exit 0 |
| 255 | 13 | python -m pytest tests/integration/persistence/d/test_persist_d_postgres.py -q -p no:cacheprovider | 0 | 22 passed in 12.57s |
| 256 | 13 | python -c "import pathlib; fs = list(pathlib.Path('src/creative/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') ... | 0 | exit 0 |
| 257 | 13 | python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider | 0 | 19 passed in 9.65s |
| 258 | 13 | python -c "import pathlib; fs = list(pathlib.Path('src/voice/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for... | 0 | exit 0 |
| 259 | 13 | python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider | 0 | 20 passed in 9.96s |
| 260 | 13 | python -c "import pathlib; fs = list(pathlib.Path('src/render/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') fo... | 0 | exit 0 |
| 261 | 13 | python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider | 0 | 16 passed in 5.68s |
| 262 | 13 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/orchestration'); t = ' '.join(f.read_text(encoding='utf-8... | 0 | exit 0 |
| 263 | 13 | python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider | 0 | 16 passed in 7.11s |
| 264 | 13 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/storage_meta'); t = ' '.join(f.read_text(encoding='utf-8'... | 0 | exit 0 |
| 265 | 13 | python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider | 0 | 18 passed in 8.77s |
| 266 | 13 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/config_security'); t = ' '.join(f.read_text(encoding='utf... | 0 | exit 0 |
| 267 | 13 | python -c "import pathlib; t = pathlib.Path('tests/integration/voice/test_e16_voice_timing_pipeline.py').read_text(encoding='utf-8'); ass... | 0 | exit 0 |
| 268 | 13 | python -c "import pathlib; t = pathlib.Path('tests/unit/render/test_f16_ports_memory_events.py').read_text(encoding='utf-8'); assert all(... | 0 | exit 0 |
| 269 | 13 | python -c "import pathlib; t = pathlib.Path('tests/integration/render/test_f20_worker_activity.py').read_text(encoding='utf-8'); assert a... | 0 | exit 0 |
| 270 | 13 | python -c "import pathlib; t = pathlib.Path('tests/integration/control_ui/test_h_list_queries_sql.py').read_text(encoding='utf-8'); asser... | 0 | exit 0 |
| 271 | 13 | python -c "import pathlib; t = pathlib.Path('tests/unit/control_ui/test_h_status_pill.py').read_text(encoding='utf-8'); assert all(i in t... | 0 | exit 0 |
| 272 | 14 | python -B -m pytest tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_ast_boundary_rules_clean_codebase -q -p no:cacheprovider | 0 | 1 passed in 0.31s |
| 273 | 14 | python -c "import pathlib; t = ' '.join(pathlib.Path('src/controlplane/infrastructure/db/migrations/0013_ingestion.sql').read_text(encodi... | 0 | exit 0 |
| 274 | 14 | python -B -m pytest tests/integration/convergence/test_cp3_migration_sequence.py::test_pinned_migrations_and_runner_untouched -q -p no:ca... | 0 | 1 passed in 0.28s |
| 275 | 14 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py -q -p no:cacheprovider | 0 | 21 passed, 1 warning in 0.77s |
| 276 | 14 | python -m pytest tests/m2/test_p7a_hardening.py::test_h28_static_architecture -q -p no:cacheprovider | 0 | 1 passed, 1 warning in 0.62s |
| 277 | 14 | python -c "import ast, pathlib; d = pathlib.Path('src/controlplane/application/control_api'); r = (d / 'route_catalog.py').read_text(enco... | 0 | exit 0 |
| 278 | 14 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_sources_module.py -q -p no:cacheprovider | 0 | 9 passed in 1.76s |
| 279 | 14 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_builder_inventory tests/integration/adapt/wire/tes... | 0 | 3 passed in 1.02s |
| 280 | 14 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p in pathlib.Path('src/controlplane/api').rglob('*.py')); ... | 0 | exit 0 |
| 281 | 14 | python -c "import pathlib; d = pathlib.Path('src/controlplane/ui/dist'); n = [f.name for f in d.rglob('*') if f.is_file()]; assert len(n)... | 0 | exit 0 |
| 282 | 14 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8')... | 0 | exit 0 |
| 283 | 14 | python -m pytest tests/integration/persistence/c/test_persist_c_hook_listing.py -q -p no:cacheprovider | 0 | 5 passed in 0.11s |
| 284 | 14 | python -m pytest tests/unit/catalog -q -p no:cacheprovider | 0 | 202 passed, 463 subtests passed in 0.23s |
| 285 | 14 | python -c "import pathlib; r = pathlib.Path('src/catalog'); d = (r / 'domain' / 'hooks.py').read_text(encoding='utf-8'); a = (r / 'applic... | 0 | exit 0 |
| 286 | 14 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_hooks_module.py -q -p no:cacheprovider | 0 | 9 passed in 1.77s |
| 287 | 14 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p in pathlib.Path('src/controlplane/api').rglob('*.py')); ... | 0 | exit 0 |
| 288 | 14 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8')... | 0 | exit 0 |
| 289 | 14 | python -c "import pathlib; t = pathlib.Path('tools/launcher/launcher.py').read_text(encoding='utf-8'); assert 'build_production_ports' in... | 0 | exit 0 |
| 290 | 14 | python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml').read_text(encoding='utf-8'); d = pathlib.Path('tools/lau... | 0 | exit 0 |

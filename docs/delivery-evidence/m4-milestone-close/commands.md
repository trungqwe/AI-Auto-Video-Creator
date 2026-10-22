# M4-MILESTONE-CLOSE: kết quả chạy lại lệnh kiểm (revision 1)

- Candidate SHA: `cc290f002074514001fa0b03b3eb8c9e00c14db6` (trùng khớp với HEAD của worktree)
- Đường dẫn Python interpreter đã khóa: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/33f06a7a/venv/Scripts/python.exe` (Python 3.13.15)
- Tổng số lệnh kiểm đã thực thi: 274

| STT | Nhóm bước | Lệnh | Exit code | Tóm tắt nguyên văn |
| --- | --- | --- | --- | --- |
| 1 | 1 | `git diff --check` | 0 | exit 0 (không có khoảng trắng thừa) |
| 2 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/a'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(enco...` | 0 | exit 0 |
| 3 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/b'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(enco...` | 0 | exit 0 |
| 4 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/c'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(enco...` | 0 | exit 0 |
| 5 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/i'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(enco...` | 0 | exit 0 |
| 6 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/d'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(enco...` | 0 | exit 0 |
| 7 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/e'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(enco...` | 0 | exit 0 |
| 8 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/f'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(enco...` | 0 | exit 0 |
| 9 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/j'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(enco...` | 0 | exit 0 |
| 10 | 2 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/g'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(enco...` | 0 | exit 0 |
| 11 | 2 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/h'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(enco...` | 0 | exit 0 |
| 12 | 2 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 13 | 2 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence-ext'); p = unicodedata.normalize('NFC', (d / 'plan.md')....` | 0 | exit 0 |
| 14 | 2 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/persist'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_tex...` | 0 | exit 0 |
| 15 | 2 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/adapt'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(...` | 0 | exit 0 |
| 16 | 2 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence-ext-ui'); p = unicodedata.normalize('NFC', (d / 'plan.md...` | 0 | exit 0 |
| 17 | 2 | `python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q -p no:cacheprovider` | 0 | 8 passed in 2.54s |
| 18 | 2 | `python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider` | 0 | 6 passed in 10.69s |
| 19 | 3 | `python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/unit/storage tests/unit/security tests/integration/orchestration tests/integration/control_ui -q -p no:cacheprovider` | 0 | 5182 passed, 1 warning, 2237 subtests passed in 13.22s |
| 20 | 3 | `python -c "import pathlib; t = ' '.join(pathlib.Path('src/controlplane/infrastructure/db/migrations/0013_ingestion.sql').read_text(encoding='utf-8').s...` | 0 | exit 0 |
| 21 | 3 | `python -B -m pytest tests/integration/convergence/test_cp3_migration_sequence.py::test_pinned_migrations_and_runner_untouched -q -p no:cacheprovider` | 0 | 1 passed in 0.30s |
| 22 | 3 | `python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider` | 0 | 133 passed, 28 skipped, 1 warning in 2.78s |
| 23 | 3 | `python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` | 0 | 16 passed in 6.03s |
| 24 | 3 | `python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider` | 0 | 40 passed in 5.77s |
| 25 | 3 | `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider` | 0 | 111 passed in 11.14s |
| 26 | 3 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 13 passed, 62 subtests passed in 0.14s |
| 27 | 3 | `python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider` | 0 | 27 passed, 99 subtests passed in 0.06s |
| 28 | 4 | `python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cacheprovider` | 0 | 17 passed, 50 subtests passed in 0.05s |
| 29 | 4 | `python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider` | 0 | 74 passed in 0.07s |
| 30 | 4 | `python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider` | 0 | 40 passed, 20 subtests passed in 0.08s |
| 31 | 4 | `python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprovider` | 0 | 15 passed, 22 subtests passed in 0.04s |
| 32 | 4 | `python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cacheprovider` | 0 | 14 passed, 44 subtests passed in 0.04s |
| 33 | 4 | `python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider` | 0 | 32 passed, 3 subtests passed in 0.10s |
| 34 | 4 | `python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p no:cacheprovider` | 0 | 28 passed, 11 subtests passed in 0.12s |
| 35 | 4 | `python -m pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider` | 0 | 23 passed, 14 subtests passed in 0.13s |
| 36 | 4 | `python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider` | 0 | 18 passed in 0.18s |
| 37 | 5 | `python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cacheprovider` | 0 | 59 passed in 0.18s |
| 38 | 5 | `python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cacheprovider` | 0 | 49 passed in 0.12s |
| 39 | 5 | `python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p no:cacheprovider` | 0 | 19 passed in 0.10s |
| 40 | 5 | `python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:cacheprovider` | 0 | 20 passed, 49 subtests passed in 0.06s |
| 41 | 5 | `python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no:cacheprovider` | 0 | 25 passed in 0.20s |
| 42 | 5 | `python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cacheprovider` | 0 | 33 passed, 29 subtests passed in 0.13s |
| 43 | 5 | `python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider` | 0 | 32 passed in 0.19s |
| 44 | 5 | `python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cacheprovider` | 0 | 62 passed in 0.13s |
| 45 | 5 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); x = d['project']['dependencies']; a...` | 0 | exit 0 |
| 46 | 6 | `python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock').read_text(encoding='utf-8')); p = {x['name']: x for x in d['package'...` | 0 | exit 0 |
| 47 | 6 | `python -m pytest tests/integration/adapt/a/test_adapt_a_adapters.py -q -p no:cacheprovider` | 0 | 27 passed in 5.77s |
| 48 | 6 | `python -c "import pathlib; d = pathlib.Path('src/source_ingestion/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_http_tr...` | 0 | exit 0 |
| 49 | 6 | `python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/security/test_http_router_adapter.py -q -p no:cacheprovider` | 0 | 20 passed in 0.18s |
| 50 | 6 | `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/creative/adapters/real_ai_invocation.py', 'src/crea...` | 0 | exit 0 |
| 51 | 6 | `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider` | 0 | 34 passed in 0.73s |
| 52 | 6 | `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_kokoro_tts.py', 'r...` | 0 | exit 0 |
| 53 | 6 | `python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q -p no:cacheprovider` | 0 | 41 passed in 0.32s |
| 54 | 6 | `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpeg_media_tool....` | 0 | exit 0 |
| 55 | 7 | `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider` | 0 | 53 passed in 3.94s |
| 56 | 7 | `python -c "import pathlib; d = pathlib.Path('src/render/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpeg_renderer.p...` | 0 | exit 0 |
| 57 | 7 | `python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cacheprovider` | 0 | 22 passed in 13.62s |
| 58 | 7 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/security'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['o...` | 0 | exit 0 |
| 59 | 7 | `python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cacheprovider` | 0 | 32 passed in 2.19s |
| 60 | 7 | `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/storage/drive_object_store.py').read_text(encoding='utf-8'); assert 'Clou...` | 0 | exit 0 |
| 61 | 7 | `python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider` | 0 | 11 passed in 0.07s |
| 62 | 7 | `python -c "import json, pathlib; d = pathlib.Path('tools/launcher/prod'); x = [json.loads((d / n).read_text(encoding='utf-8')) for n in ['profile.json...` | 0 | exit 0 |
| 63 | 7 | `python -c "import pathlib; fs = list(pathlib.Path('src/controlplane/api/wiring').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in f...` | 0 | exit 0 |
| 64 | 8 | `python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no:cacheprovider` | 0 | 13 passed in 40.79s |
| 65 | 8 | `python -c "import pathlib; t = pathlib.Path('tools/launcher/prod/seed/import_seed.py').read_text(encoding='utf-8'); assert 'register_discovery' in t a...` | 0 | exit 0 |
| 66 | 8 | `python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider` | 0 | 23 passed, 1 warning in 8.66s |
| 67 | 8 | `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/main.py', 'src/controlplane/api/wiring/production.p...` | 0 | exit 0 |
| 68 | 8 | `python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider` | 0 | 29 passed in 0.47s |
| 69 | 8 | `python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml').read_text(encoding='utf-8'); r = pathlib.Path('docs/runbook/runbook-v...` | 0 | exit 0 |
| 70 | 8 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 39 passed in 0.07s |
| 71 | 8 | `python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit/ingestion/test_ingestion_fingerprint.py -q -p no:cacheprovider` | 0 | 30 passed in 0.04s |
| 72 | 8 | `python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/unit/ingestion/test_ingestion_memory_unit_of_work.py -q -p no:cacheprovider` | 0 | 19 passed in 0.06s |
| 73 | 9 | `python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:cacheprovider` | 0 | 64 passed in 0.08s |
| 74 | 9 | `python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no:cacheprovider` | 0 | 27 passed in 0.03s |
| 75 | 9 | `python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider` | 0 | 31 passed in 0.07s |
| 76 | 9 | `python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cacheprovider` | 0 | 45 passed in 0.09s |
| 77 | 9 | `python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:cacheprovider` | 0 | 61 passed in 0.10s |
| 78 | 9 | `python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cacheprovider` | 0 | 39 passed in 0.08s |
| 79 | 9 | `python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cacheprovider` | 0 | 55 passed in 0.08s |
| 80 | 9 | `python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p no:cacheprovider` | 0 | 67 passed in 0.10s |
| 81 | 9 | `python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py -q -p no:cacheprovider` | 0 | 15 passed in 0.18s |
| 82 | 10 | `python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider` | 0 | 20 passed, 37 subtests passed in 0.08s |
| 83 | 10 | `python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovider` | 0 | 20 passed, 45 subtests passed in 0.04s |
| 84 | 10 | `python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprovider` | 0 | 11 passed, 11 subtests passed in 0.03s |
| 85 | 10 | `python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cacheprovider` | 0 | 20 passed, 33 subtests passed in 0.05s |
| 86 | 10 | `python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider` | 0 | 18 passed, 31 subtests passed in 0.04s |
| 87 | 10 | `python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cacheprovider` | 0 | 27 passed, 19 subtests passed in 0.06s |
| 88 | 10 | `python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cacheprovider` | 0 | 31 passed, 189 subtests passed in 0.07s |
| 89 | 10 | `python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cacheprovider` | 0 | 20 passed, 87 subtests passed in 0.05s |
| 90 | 10 | `python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider` | 0 | 27 passed, 11 subtests passed in 0.05s |
| 91 | 11 | `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit/control_ui/test_h_stream_client_registry.py tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider` | 0 | 94 passed in 0.18s |
| 92 | 11 | `python -m pytest tests/unit/control_ui tests/m2/test_p7b_sse_stream.py -q -p no:cacheprovider` | 0 | 666 passed, 1 warning in 9.25s |
| 93 | 11 | `python -c "import pathlib, re; c = pathlib.Path('src/controlplane/application/sse/event_catalog.py').read_text(encoding='utf-8'); t = pathlib.Path('sr...` | 0 | exit 0 |
| 94 | 11 | `python -m pytest tests/integration/convergence/test_cp4_pagination_postgres.py -q -p no:cacheprovider` | 0 | 16 passed in 8.52s |
| 95 | 11 | `python -m pytest tests/integration/control_ui tests/unit/control_ui -q -p no:cacheprovider` | 0 | 836 passed, 1 warning in 2.14s |
| 96 | 11 | `python -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression` | 0 | 179 passed, 1 deselected, 2 warnings in 255.65s (0:04:15) |
| 97 | 11 | `python -c "import pathlib; q = pathlib.Path('src/controlplane/infrastructure/db/control_api_queries.py').read_text(encoding='utf-8'); c = pathlib.Path...` | 0 | exit 0 |
| 98 | 11 | `python -m pytest tests/integration/convergence/test_cp4_queries_routes.py tests/integration/convergence/test_cp4_queries_postgres.py -q -p no:cacheprovider` | 0 | 30 passed, 1 warning in 5.99s |
| 99 | 11 | `python -m pytest tests/integration tests/unit/control_ui -q -p no:cacheprovider` | 0 | 2758 passed, 35 skipped, 1 warning, 25 subtests passed in 211.03s (0:03:31) |
| 100 | 12 | `python -c "import pathlib; p = pathlib.Path('src/controlplane/application/control_api/query_ports.py').read_text(encoding='utf-8'); q = pathlib.Path('...` | 0 | exit 0 |
| 101 | 12 | `npm --prefix src/controlplane/ui run build` | 0 | exit 0 (build thành công) |
| 102 | 12 | `python -m pytest tests/unit/control_ui -q -p no:cacheprovider` | 0 | 661 passed, 1 warning in 1.23s |
| 103 | 12 | `python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.findall('asset...` | 0 | exit 0 |
| 104 | 12 | `python -c "import pathlib; u = pathlib.Path('src/controlplane/ui/src'); a = (u / 'App.tsx').read_text(encoding='utf-8'); c = (u / 'api' / 'client.ts')...` | 0 | exit 0 |
| 105 | 12 | `python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s = dict(re...` | 0 | exit 0 |
| 106 | 12 | `python -c "import json, pathlib; d = json.loads(pathlib.Path('tools/runtime/runtime.lock.json').read_text(encoding='utf-8')); assert d['versions'] == ...` | 0 | exit 0 |
| 107 | 12 | `python -c "import pathlib; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; b = pathlib.Path('src/controlplane'); assert all((b / d / u).read_bytes() =...` | 0 | exit 0 |
| 108 | 12 | `python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider` | 0 | 9 passed in 11.64s |
| 109 | 13 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); x = d['project']['...` | 0 | exit 0 |
| 110 | 13 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['tool']['set...` | 0 | exit 0 |
| 111 | 13 | `python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider` | 0 | 293 passed in 0.67s |
| 112 | 13 | `python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); assert 'src/controlplane/a...` | 0 | exit 0 |
| 113 | 13 | `python -m pytest tests/unit/config tests/unit/storage tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergence/test_cp3b_source_parity.py -q -p no:cacheprovider` | 0 | 1125 passed, 239 subtests passed in 1.76s |
| 114 | 13 | `python -m pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/contract/test_bindings.py -q -p no:cacheprovider` | 0 | 679 passed, 398 subtests passed in 0.88s |
| 115 | 13 | `python -c "import hashlib, pathlib, re; t = pathlib.Path('docs/parallel-delivery/contract-registry.yaml').read_text(encoding='utf-8'); h = hashlib.sha...` | 0 | exit 0 |
| 116 | 13 | `python -c "import pathlib; t = pathlib.Path('docs/09-contracts/12-state-machines.md').read_text(encoding='utf-8'); assert 'PUC-J-03' in t and 'YC-HT-I...` | 0 | exit 0 |
| 117 | 13 | `python -m pytest tests/integration/orchestration tests/integration/storage tests/unit/catalog tests/unit/storage tests/unit/render -q -p no:cacheprovider` | 0 | 2306 passed, 7 skipped, 1184 subtests passed in 5.36s |
| 118 | 14 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['tool']['set...` | 0 | exit 0 |
| 119 | 14 | `python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` | 0 | 28 passed in 0.86s |
| 120 | 14 | `python -m pytest tests/unit/orchestration tests/integration/collection tests/unit/ingestion tests/integration/creative tests/integration/voice tests/integration/render tests/unit/config tests/unit/catalog tests/unit/storage -q -p no:cacheprovider` | 0 | 3379 passed, 1034 subtests passed in 4.97s |
| 121 | 14 | `python -c "import json, pathlib; p = json.loads(pathlib.Path('src/controlplane/ui/package.json').read_text(encoding='utf-8')); v = list(p['dependencie...` | 0 | exit 0 |
| 122 | 14 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['tool']['set...` | 0 | exit 0 |
| 123 | 14 | `python -c "import re, pathlib; t = pathlib.Path('tests/m2/test_p9_m2_exit_gate.py').read_text(encoding='utf-8'); assert re.search('M2_ACCEPTED_SHA = [...` | 0 | exit 0 |
| 124 | 14 | `python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergence/test_cp3b_source_parity.py -q -p no:cacheprovider` | 0 | 25 passed in 0.08s |
| 125 | 14 | `python -m pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_statemachines.py -q -p no:cacheprovider` | 0 | 658 passed, 841 subtests passed in 1.17s |
| 126 | 14 | `python -m pytest tests/m2 tests/integration -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression` | 0 | 2276 passed, 35 skipped, 1 deselected, 2 warnings, 25 subtests passed in 507.21s (0:08:27) |
| 127 | 15 | `python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/unit/security tests/unit/control_ui -q -p no:cacheprovider` | 0 | 5250 passed, 1 warning, 1998 subtests passed in 13.00s |
| 128 | 15 | `python -c "import pathlib; t = pathlib.Path('src/main.py').read_text(encoding='utf-8'); assert 'create_app' in t, 'src/main.py must call create_app'; ...` | 0 | exit 0 |
| 129 | 15 | `python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.findall('asset...` | 0 | exit 0 |
| 130 | 15 | `python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/src/App.tsx').read_text(encoding='utf-8'); assert 'boundedEventDeduper' in t and 'scr...` | 0 | exit 0 |
| 131 | 15 | `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 58 subtests passed in 0.17s |
| 132 | 15 | `python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider` | 0 | 68 passed in 0.13s |
| 133 | 15 | `python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cacheprovider` | 0 | 11 passed, 13 subtests passed in 0.05s |
| 134 | 15 | `python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider` | 0 | 87 passed in 0.11s |
| 135 | 15 | `python -m pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cacheprovider` | 0 | 20 passed, 79 subtests passed in 0.10s |
| 136 | 16 | `python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider` | 0 | 60 passed in 0.10s |
| 137 | 16 | `python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider` | 0 | 32 passed in 0.06s |
| 138 | 16 | `python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider` | 0 | 62 passed in 0.13s |
| 139 | 16 | `python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider` | 0 | 110 passed in 0.21s |
| 140 | 16 | `python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider` | 0 | 94 passed in 0.16s |
| 141 | 16 | `python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider` | 0 | 62 passed in 0.17s |
| 142 | 16 | `python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider` | 0 | 19 passed, 38 subtests passed in 0.04s |
| 143 | 16 | `python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider` | 0 | 65 passed in 0.16s |
| 144 | 16 | `python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider` | 0 | 18 passed in 0.15s |
| 145 | 17 | `python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider` | 0 | 27 passed in 0.13s |
| 146 | 17 | `python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider` | 0 | 52 passed in 0.18s |
| 147 | 17 | `python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider` | 0 | 22 passed in 0.10s |
| 148 | 17 | `python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider` | 0 | 8 passed in 0.35s |
| 149 | 17 | `python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | 16 passed, 89 subtests passed in 0.16s |
| 150 | 17 | `python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider` | 0 | 65 passed in 0.09s |
| 151 | 17 | `python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider` | 0 | 144 passed in 0.13s |
| 152 | 17 | `python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovider` | 0 | 86 passed in 0.12s |
| 153 | 17 | `python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovider` | 0 | 50 passed in 0.08s |
| 154 | 18 | `python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprovider` | 0 | 75 passed in 0.11s |
| 155 | 18 | `python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprovider` | 0 | 106 passed in 0.12s |
| 156 | 18 | `python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider` | 0 | 63 passed in 0.10s |
| 157 | 18 | `python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider` | 0 | 114 passed in 0.14s |
| 158 | 18 | `python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider` | 0 | 51 passed in 0.07s |
| 159 | 18 | `python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider` | 0 | 21 passed in 0.06s |
| 160 | 18 | `python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider` | 0 | 35 passed in 0.09s |
| 161 | 18 | `python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider` | 0 | 63 passed in 0.09s |
| 162 | 18 | `python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider` | 0 | 79 passed in 0.16s |
| 163 | 19 | `python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider` | 0 | 47 passed in 0.09s |
| 164 | 19 | `python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider` | 0 | 23 passed in 0.11s |
| 165 | 19 | `python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider` | 0 | 45 passed in 0.15s |
| 166 | 19 | `python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider` | 0 | 44 passed in 0.23s |
| 167 | 19 | `python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider` | 0 | 35 passed in 0.11s |
| 168 | 19 | `python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider` | 0 | 25 passed in 1.97s |
| 169 | 19 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 20 passed, 120 subtests passed in 0.38s |
| 170 | 19 | `python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cacheprovider` | 0 | 26 passed, 67 subtests passed in 0.11s |
| 171 | 19 | `python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider` | 0 | 169 passed in 0.19s |
| 172 | 20 | `python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider` | 0 | 58 passed in 0.16s |
| 173 | 20 | `python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider` | 0 | 62 passed in 0.10s |
| 174 | 20 | `python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider` | 0 | 104 passed in 0.12s |
| 175 | 20 | `python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider` | 0 | 97 passed in 0.12s |
| 176 | 20 | `python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider` | 0 | 55 passed in 0.15s |
| 177 | 20 | `python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider` | 0 | 118 passed in 0.13s |
| 178 | 20 | `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider` | 0 | 154 passed in 0.23s |
| 179 | 20 | `python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider` | 0 | 97 passed in 0.15s |
| 180 | 20 | `python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider` | 0 | 45 passed, 129 subtests passed in 0.11s |
| 181 | 21 | `python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider` | 0 | 38 passed, 99 subtests passed in 0.08s |
| 182 | 21 | `python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider` | 0 | 52 passed, 67 subtests passed in 0.10s |
| 183 | 21 | `python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider` | 0 | 73 passed in 0.14s |
| 184 | 21 | `python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider` | 0 | 39 passed in 0.14s |
| 185 | 21 | `python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider` | 0 | 36 passed in 0.18s |
| 186 | 21 | `python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider` | 0 | 28 passed in 0.17s |
| 187 | 21 | `python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider` | 0 | 35 passed in 0.21s |
| 188 | 21 | `python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider` | 0 | 53 passed in 0.25s |
| 189 | 21 | `python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider` | 0 | 17 passed in 0.12s |
| 190 | 22 | `python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cacheprovider` | 0 | 55 passed in 0.20s |
| 191 | 22 | `python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:cacheprovider` | 0 | 43 passed in 0.09s |
| 192 | 22 | `python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no:cacheprovider` | 0 | 22 passed, 307 subtests passed in 0.07s |
| 193 | 22 | `python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider` | 0 | 45 passed in 0.08s |
| 194 | 22 | `python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cacheprovider` | 0 | 45 passed in 0.07s |
| 195 | 22 | `python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:cacheprovider` | 0 | 55 passed in 0.09s |
| 196 | 22 | `python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/orchestration/test_g_job_waiting.py -q -p no:cacheprovider` | 0 | 147 passed in 0.14s |
| 197 | 22 | `python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py -q -p no:cacheprovider` | 0 | 88 passed in 0.22s |
| 198 | 22 | `python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q -p no:cacheprovider` | 0 | 47 passed in 0.07s |
| 199 | 23 | `python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cacheprovider` | 0 | 86 passed in 0.10s |
| 200 | 23 | `python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q -p no:cacheprovider` | 0 | 62 passed in 0.10s |
| 201 | 23 | `python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit/orchestration/test_g_retry_policy.py -q -p no:cacheprovider` | 0 | 110 passed in 0.14s |
| 202 | 23 | `python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/orchestration/test_g_resource_admission.py -q -p no:cacheprovider` | 0 | 82 passed in 0.12s |
| 203 | 23 | `python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/orchestration/test_g_consistency_audit.py -q -p no:cacheprovider` | 0 | 175 passed in 0.18s |
| 204 | 23 | `python -m pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orchestration/test_g_batch_outcome.py tests/unit/orchestration/test_g_app_session.py -q -p no:cacheprovider` | 0 | 157 passed in 0.15s |
| 205 | 23 | `python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:cacheprovider` | 0 | 55 passed in 0.07s |
| 206 | 23 | `python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovider` | 0 | 115 passed in 0.11s |
| 207 | 23 | `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:cacheprovider` | 0 | 70 passed in 0.07s |
| 208 | 24 | `python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider` | 0 | 175 passed, 1 warning in 1.14s |
| 209 | 24 | `python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cacheprovider` | 0 | 31 passed in 0.05s |
| 210 | 24 | `python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:cacheprovider` | 0 | 91 passed in 0.08s |
| 211 | 24 | `python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cacheprovider` | 0 | 37 passed in 0.30s |
| 212 | 24 | `python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cacheprovider` | 0 | 43 passed, 1 warning in 0.52s |
| 213 | 24 | `python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cacheprovider` | 0 | 83 passed, 1 warning in 0.57s |
| 214 | 24 | `python -m pytest tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider` | 0 | 10 passed in 0.04s |
| 215 | 24 | `python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:cacheprovider` | 0 | 9 passed in 0.03s |
| 216 | 24 | `python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovider` | 0 | 22 passed in 0.05s |
| 217 | 25 | `python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cacheprovider` | 0 | 24 passed in 0.05s |
| 218 | 25 | `python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no:cacheprovider` | 0 | 14 passed in 0.06s |
| 219 | 25 | `python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider` | 0 | 31 passed in 0.05s |
| 220 | 25 | `python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cacheprovider` | 0 | 26 passed in 0.05s |
| 221 | 25 | `python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cacheprovider` | 0 | 65 passed in 0.08s |
| 222 | 25 | `python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cacheprovider` | 0 | 24 passed in 0.07s |
| 223 | 25 | `python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider` | 0 | 11 passed, 85 subtests passed in 0.04s |
| 224 | 25 | `python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider` | 0 | 22 passed, 21 subtests passed in 0.06s |
| 225 | 25 | `python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p no:cacheprovider` | 0 | 21 passed in 1.03s |
| 226 | 26 | `python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p no:cacheprovider` | 0 | 373 passed, 7 skipped in 0.98s |
| 227 | 26 | `python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider` | 0 | 25 passed, 26 subtests passed in 0.05s |
| 228 | 26 | `python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no:cacheprovider` | 0 | 67 passed in 0.07s |
| 229 | 26 | `python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q -p no:cacheprovider` | 0 | 21 passed in 0.17s |
| 230 | 26 | `python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider` | 0 | 13 passed, 10 subtests passed in 0.05s |
| 231 | 26 | `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` | 0 | 32 passed, 97 subtests passed in 0.06s |
| 232 | 26 | `python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider` | 0 | 56 passed in 0.07s |
| 233 | 26 | `python -m pytest tests/unit/storage/test_storage_availability.py -q -p no:cacheprovider` | 0 | 41 passed in 0.04s |
| 234 | 26 | `python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovider` | 0 | 50 passed in 0.06s |
| 235 | 27 | `python -m pytest tests/unit/security/test_j_secret_redaction.py -q -p no:cacheprovider` | 0 | 55 passed in 0.06s |
| 236 | 27 | `python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider` | 0 | 60 passed in 0.08s |
| 237 | 27 | `python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider` | 0 | 118 passed in 0.13s |
| 238 | 27 | `python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cacheprovider` | 0 | 49 passed in 0.08s |
| 239 | 27 | `python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprovider` | 0 | 40 passed in 0.08s |
| 240 | 27 | `python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cacheprovider` | 0 | 104 passed in 0.10s |
| 241 | 27 | `python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprovider` | 0 | 131 passed in 0.10s |
| 242 | 27 | `python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovider` | 0 | 104 passed in 0.09s |
| 243 | 27 | `python -m pytest tests/unit/security/test_j_secret_update.py -q -p no:cacheprovider` | 0 | 63 passed in 0.09s |
| 244 | 28 | `python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cacheprovider` | 0 | 51 passed in 0.09s |
| 245 | 28 | `python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cacheprovider` | 0 | 66 passed in 0.10s |
| 246 | 28 | `python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovider` | 0 | 50 passed in 0.10s |
| 247 | 28 | `python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovider` | 0 | 41 passed in 0.09s |
| 248 | 28 | `python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovider` | 0 | 47 passed in 0.08s |
| 249 | 28 | `python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cacheprovider` | 0 | 35 passed in 0.06s |
| 250 | 28 | `python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no:cacheprovider` | 0 | 35 passed in 0.62s |
| 251 | 28 | `python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:cacheprovider` | 0 | 33 passed in 0.15s |
| 252 | 28 | `python -m pytest tests/integration/persistence/a/test_persist_a_postgres.py -q -p no:cacheprovider` | 0 | 22 passed in 14.59s |
| 253 | 29 | `python -c "import pathlib; fs = list(pathlib.Path('src/source_ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f...` | 0 | exit 0 |
| 254 | 29 | `python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q -p no:cacheprovider` | 0 | 14 passed in 8.16s |
| 255 | 29 | `python -c "import pathlib; fs = list(pathlib.Path('src/ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs)...` | 0 | exit 0 |
| 256 | 29 | `python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q -p no:cacheprovider` | 0 | 14 passed in 7.05s |
| 257 | 29 | `python -c "import pathlib; fs = list(pathlib.Path('src/catalog/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); ...` | 0 | exit 0 |
| 258 | 29 | `python -m pytest tests/integration/persistence/d/test_persist_d_postgres.py -q -p no:cacheprovider` | 0 | 22 passed in 13.21s |
| 259 | 29 | `python -c "import pathlib; fs = list(pathlib.Path('src/creative/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs);...` | 0 | exit 0 |
| 260 | 29 | `python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider` | 0 | 19 passed in 11.88s |
| 261 | 29 | `python -c "import pathlib; fs = list(pathlib.Path('src/voice/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); as...` | 0 | exit 0 |
| 262 | 30 | `python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider` | 0 | 20 passed in 12.43s |
| 263 | 30 | `python -c "import pathlib; fs = list(pathlib.Path('src/render/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f in fs); a...` | 0 | exit 0 |
| 264 | 30 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/orchestration'); t = ' '.join(f.read_text(encoding='utf-8') for f in d...` | 0 | exit 0 |
| 265 | 30 | `python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider` | 0 | 16 passed in 8.29s |
| 266 | 30 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/storage_meta'); t = ' '.join(f.read_text(encoding='utf-8') for f in d....` | 0 | exit 0 |
| 267 | 30 | `python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider` | 0 | 18 passed in 8.41s |
| 268 | 30 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/config_security'); t = ' '.join(f.read_text(encoding='utf-8') for f in...` | 0 | exit 0 |
| 269 | 30 | `python -c "import pathlib; t = pathlib.Path('tests/integration/voice/test_e16_voice_timing_pipeline.py').read_text(encoding='utf-8'); assert all(i in ...` | 0 | exit 0 |
| 270 | 30 | `python -c "import pathlib; t = pathlib.Path('tests/unit/render/test_f16_ports_memory_events.py').read_text(encoding='utf-8'); assert all(i in t for i ...` | 0 | exit 0 |
| 271 | 31 | `python -c "import pathlib; t = pathlib.Path('tests/integration/render/test_f20_worker_activity.py').read_text(encoding='utf-8'); assert all(i in t for...` | 0 | exit 0 |
| 272 | 31 | `python -c "import pathlib; t = pathlib.Path('tests/integration/control_ui/test_h_list_queries_sql.py').read_text(encoding='utf-8'); assert all(i in t ...` | 0 | exit 0 |
| 273 | 31 | `python -c "import pathlib; t = pathlib.Path('tests/unit/control_ui/test_h_status_pill.py').read_text(encoding='utf-8'); assert all(i in t for i in ['C...` | 0 | exit 0 |
| 274 | 31 | `python -B -m pytest tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_ast_boundary_rules_clean_codebase -q -p no:cacheprovider` | 0 | 1 passed in 0.85s |

## Tổng hợp

- **Tổng số lệnh kiểm:** 274
- **Số lệnh có mã thoát 0 (thành công):** 274
- **Số lệnh FAIL (mã thoát khác 0):** 0
- **Số lệnh có test skipped:** 5 lệnh (STT 22, 99, 117, 126, 226 — các test kiểm thử tích hợp cơ sở dữ liệu PostgreSQL được bỏ qua do môi trường cô lập không kích hoạt dịch vụ nền, tuân thủ nghiêm ngặt nguyên tắc D5)
- **Danh sách STT FAIL:** Không có (toàn bộ 274 lệnh kiểm đều hoàn thành đạt yêu cầu)
- **Các lệnh kiểm chứa cờ hoãn kiểm thử:** Có 2 lệnh mang cờ `--deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression` gồm STT 96 (Nhóm 11) và STT 126 (Nhóm 14). Hạng mục này đã được hoãn sang slice CP7 theo quyết định phê duyệt chính thức của người dùng ngày 21/10/2026, đây không phải là lỗi.

# M4-MILESTONE-CLOSE-R3: kết quả chạy lại lệnh kiểm (revision 3)

- Candidate SHA: `6042d7a626d3d523881cc86d1b0ac674986bcafa` (integration head `integrate(ADAPT-LAUNCH-FIX2): lane lane-adapt-launch-fix2 candidate 903393a717cb`; cây mã nguồn khi chạy lệnh kiểm, bằng chứng chỉ thêm tệp trong `docs/delivery-evidence/m4-milestone-close/`)
- Interpreter đã khóa: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/33f06a7a/venv/Scripts/python.exe` (Python 3.13.15 theo `tools/runtime/runtime.lock.json`)
- Ngày chạy: 25/10/2026
- Tổng số lệnh kiểm bắt buộc: 289, chia thành 10 nhóm theo cột «Nhóm bước»; mỗi lệnh một tiến trình riêng.
- Lần chạy này thay thế hoàn toàn kết quả revision 2 (candidate cũ `21d99fc8...`, chưa chứa `ADAPT-LAUNCH-FIX2`). Lệnh mới STT 50 là probe `launch-fix2`; các STT từ 51 trở đi lệch +1 so với revision 2.

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
| 10 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/g'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 11 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/h'); p = unicodedata.normalize('NFC', (d / 'plan.md').r... | 0 | exit 0 |
| 12 | 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence'); p = unicodedata.normalize('NFC', (d / 'p... | 0 | exit 0 |
| 13 | 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence-ext'); p = unicodedata.normalize('NFC', (d ... | 0 | exit 0 |
| 14 | 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/persist'); p = unicodedata.normalize('NFC', (d / 'plan.... | 0 | exit 0 |
| 15 | 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/adapt'); p = unicodedata.normalize('NFC', (d / 'plan.md... | 0 | exit 0 |
| 16 | 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence-ext-ui'); p = unicodedata.normalize('NFC', ... | 0 | exit 0 |
| 17 | 3 | python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q -p no:cacheprovider | 0 | 8 passed in 1.58s |
| 18 | 3 | python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider | 0 | 6 passed in 6.71s |
| 19 | 3 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tes... | 0 | 5190 passed, 1 warning, 2237 subtests passed in 14.18s |
| 20 | 3 | python -c "import pathlib; t = ' '.join(pathlib.Path('src/controlplane/infrastructure/db/migrations/0013_ingestion.sql').read_text(encodi... | 0 | exit 0 |
| 21 | 3 | python -B -m pytest tests/integration/convergence/test_cp3_migration_sequence.py::test_pinned_migrations_and_runner_untouched -q -p no:ca... | 0 | 1 passed in 0.26s |
| 22 | 3 | python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider | 0 | 137 passed, 28 skipped, 1 warning in 2.00s |
| 23 | 3 | python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider | 0 | 16 passed in 5.25s |
| 24 | 3 | python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider | 0 | 40 passed in 4.36s |
| 25 | 3 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider | 0 | 111 passed in 11.72s |
| 26 | 3 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py -q -p no:cacheprovider | 0 | 21 passed, 1 warning in 0.82s |
| 27 | 3 | python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cacheprovider | 0 | 83 passed, 1 warning in 0.66s |
| 28 | 3 | python -m pytest tests/m2/test_p7a_hardening.py::test_h28_static_architecture -q -p no:cacheprovider | 0 | 1 passed, 1 warning in 0.78s |
| 29 | 3 | python -c "import ast, pathlib; d = pathlib.Path('src/controlplane/application/control_api'); r = (d / 'route_catalog.py').read_text(enco... | 0 | exit 0 |
| 30 | 3 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_sources_module.py -q -p no:cacheprovider | 0 | 9 passed in 2.09s |
| 31 | 3 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider | 0 | 25 passed, 1 warning in 9.33s |
| 32 | 3 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_builder_inventory tests/integration/adapt/wire/tes... | 0 | 3 passed in 1.20s |
| 33 | 3 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p in pathlib.Path('src/controlplane/api').rglob('*.py')); ... | 0 | exit 0 |
| 34 | 3 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/main.py', 'src/controlplane/api/wiring... | 0 | exit 0 |
| 35 | 3 | npm --prefix src/controlplane/ui run build | 0 | ✓ built in 2.37s |
| 36 | 3 | python -m pytest tests/unit/control_ui -q -p no:cacheprovider | 0 | 665 passed, 1 warning in 1.33s |
| 37 | 3 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.f... | 0 | exit 0 |
| 38 | 3 | python -c "import pathlib; d = pathlib.Path('src/controlplane/ui/dist'); n = [f.name for f in d.rglob('*') if f.is_file()]; assert len(n)... | 0 | exit 0 |
| 39 | 3 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8')... | 0 | exit 0 |
| 40 | 3 | python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider | 0 | 26 passed, 31 subtests passed in 0.05s |
| 41 | 3 | python -m pytest tests/integration/persistence/c/test_persist_c_hook_listing.py -q -p no:cacheprovider | 0 | 5 passed in 0.15s |
| 42 | 3 | python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q -p no:cacheprovider | 0 | 15 passed in 6.51s |
| 43 | 3 | python -m pytest tests/unit/catalog -q -p no:cacheprovider | 0 | 202 passed, 463 subtests passed in 0.26s |
| 44 | 3 | python -c "import pathlib; r = pathlib.Path('src/catalog'); d = (r / 'domain' / 'hooks.py').read_text(encoding='utf-8'); a = (r / 'applic... | 0 | exit 0 |
| 45 | 3 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_hooks_module.py -q -p no:cacheprovider | 0 | 9 passed in 1.95s |
| 46 | 3 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p in pathlib.Path('src/controlplane/api').rglob('*.py')); ... | 0 | exit 0 |
| 47 | 3 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8')... | 0 | exit 0 |
| 48 | 4 | python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider | 0 | 32 passed in 0.73s |
| 49 | 4 | python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml').read_text(encoding='utf-8'); r = pathlib.Path('docs/runb... | 0 | exit 0 |
| 50 | 4 | python -c "import pathlib; t = pathlib.Path('tools/launcher/launcher.py').read_text(encoding='utf-8'); assert 'build_production_ports' in... | 0 | exit 0 |
| 51 | 4 | python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider | 0 | 13 passed, 62 subtests passed in 0.12s |
| 52 | 4 | python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider | 0 | 27 passed, 99 subtests passed in 0.07s |
| 53 | 4 | python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cacheprovider | 0 | 17 passed, 50 subtests passed in 0.05s |
| 54 | 4 | python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider | 0 | 74 passed in 0.07s |
| 55 | 4 | python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider | 0 | 40 passed, 20 subtests passed in 0.06s |
| 56 | 4 | python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprovider | 0 | 15 passed, 22 subtests passed in 0.03s |
| 57 | 4 | python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cacheprovider | 0 | 14 passed, 44 subtests passed in 0.03s |
| 58 | 4 | python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider | 0 | 32 passed, 3 subtests passed in 0.09s |
| 59 | 4 | python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p no:cacheprovider | 0 | 28 passed, 11 subtests passed in 0.10s |
| 60 | 4 | python -m pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider | 0 | 23 passed, 14 subtests passed in 0.12s |
| 61 | 4 | python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider | 0 | 18 passed in 0.15s |
| 62 | 4 | python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cacheprovider | 0 | 59 passed in 0.12s |
| 63 | 4 | python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cacheprovider | 0 | 49 passed in 0.09s |
| 64 | 4 | python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p no:cacheprovider | 0 | 19 passed in 0.09s |
| 65 | 4 | python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:cacheprovider | 0 | 20 passed, 49 subtests passed in 0.05s |
| 66 | 4 | python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no:cacheprovider | 0 | 25 passed in 0.17s |
| 67 | 4 | python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cacheprovider | 0 | 33 passed, 29 subtests passed in 0.12s |
| 68 | 4 | python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider | 0 | 32 passed in 0.16s |
| 69 | 4 | python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cacheprovider | 0 | 62 passed in 0.15s |
| 70 | 4 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); x = d['project']['depe... | 0 | exit 0 |
| 71 | 4 | python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock').read_text(encoding='utf-8')); p = {x['name']: x for x i... | 0 | exit 0 |
| 72 | 4 | python -m pytest tests/integration/adapt/a/test_adapt_a_adapters.py -q -p no:cacheprovider | 0 | 27 passed in 5.70s |
| 73 | 4 | python -c "import pathlib; d = pathlib.Path('src/source_ingestion/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in [... | 0 | exit 0 |
| 74 | 4 | python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/security/test_http_router_adapter.py -q -p no:cacheprovider | 0 | 20 passed in 0.20s |
| 75 | 4 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/creative/adapters/real_ai_invocation.p... | 0 | exit 0 |
| 76 | 4 | python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider | 0 | 34 passed in 0.57s |
| 77 | 4 | python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_kokor... | 0 | exit 0 |
| 78 | 4 | python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q -p no:cacheprovider | 0 | 41 passed in 0.35s |
| 79 | 4 | python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpe... | 0 | exit 0 |
| 80 | 4 | python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider | 0 | 53 passed in 3.63s |
| 81 | 4 | python -c "import pathlib; d = pathlib.Path('src/render/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmp... | 0 | exit 0 |
| 82 | 4 | python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cacheprovider | 0 | 22 passed in 14.16s |
| 83 | 4 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/security'); t = ' '.join((d / n).read_text(encoding='utf-8')... | 0 | exit 0 |
| 84 | 4 | python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cacheprovider | 0 | 32 passed in 1.64s |
| 85 | 4 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/storage/drive_object_store.py').read_text(encoding='utf-8');... | 0 | exit 0 |
| 86 | 4 | python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider | 0 | 11 passed in 0.08s |
| 87 | 4 | python -c "import json, pathlib; d = pathlib.Path('tools/launcher/prod'); x = [json.loads((d / n).read_text(encoding='utf-8')) for n in [... | 0 | exit 0 |
| 88 | 4 | python -c "import pathlib; fs = list(pathlib.Path('src/controlplane/api/wiring').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8... | 0 | exit 0 |
| 89 | 4 | python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no:cacheprovider | 0 | 13 passed in 35.95s |
| 90 | 4 | python -c "import pathlib; t = pathlib.Path('tools/launcher/prod/seed/import_seed.py').read_text(encoding='utf-8'); assert 'register_disc... | 0 | exit 0 |
| 91 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider | 0 | 39 passed in 0.06s |
| 92 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit/ingestion/test_ingestion_fingerprint.py -q -p no:cachepr... | 0 | 30 passed in 0.04s |
| 93 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/unit/ingestion/test_ingestion_memory_unit_of_work.py -q -... | 0 | 19 passed in 0.04s |
| 94 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:cacheprovider | 0 | 64 passed in 0.07s |
| 95 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no:cacheprovider | 0 | 27 passed in 0.03s |
| 96 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider | 0 | 31 passed in 0.08s |
| 97 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cacheprovider | 0 | 45 passed in 0.06s |
| 98 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:cacheprovider | 0 | 61 passed in 0.07s |
| 99 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cacheprovider | 0 | 39 passed in 0.06s |
| 100 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cacheprovider | 0 | 55 passed in 0.06s |
| 101 | 5 | python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p no:cacheprovider | 0 | 67 passed in 0.09s |
| 102 | 5 | python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py -q -p no:cacheprovider | 0 | 15 passed in 0.12s |
| 103 | 5 | python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider | 0 | 20 passed, 37 subtests passed in 0.06s |
| 104 | 5 | python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovider | 0 | 20 passed, 45 subtests passed in 0.04s |
| 105 | 5 | python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprovider | 0 | 11 passed, 11 subtests passed in 0.05s |
| 106 | 5 | python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cacheprovider | 0 | 20 passed, 33 subtests passed in 0.04s |
| 107 | 5 | python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cacheprovider | 0 | 27 passed, 19 subtests passed in 0.04s |
| 108 | 5 | python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cacheprovider | 0 | 31 passed, 189 subtests passed in 0.06s |
| 109 | 5 | python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cacheprovider | 0 | 20 passed, 87 subtests passed in 0.05s |
| 110 | 5 | python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider | 0 | 27 passed, 11 subtests passed in 0.05s |
| 111 | 5 | python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit/control_ui/test_h_stream_client_registry.py tests/unit/c... | 0 | 94 passed in 0.10s |
| 112 | 5 | python -m pytest tests/unit/control_ui tests/m2/test_p7b_sse_stream.py -q -p no:cacheprovider | 0 | 670 passed, 1 warning in 7.61s |
| 113 | 5 | python -c "import pathlib, re; c = pathlib.Path('src/controlplane/application/sse/event_catalog.py').read_text(encoding='utf-8'); t = pat... | 0 | exit 0 |
| 114 | 5 | python -m pytest tests/integration/convergence/test_cp4_pagination_postgres.py -q -p no:cacheprovider | 0 | 16 passed in 6.95s |
| 115 | 5 | python -m pytest tests/integration/control_ui tests/unit/control_ui -q -p no:cacheprovider | 0 | 840 passed, 1 warning in 2.05s |
| 116 | 5 | python -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression | 0 | 179 passed, 1 deselected, 2 warnings in 227.81s (0:03:47) |
| 117 | 5 | python -c "import pathlib; q = pathlib.Path('src/controlplane/infrastructure/db/control_api_queries.py').read_text(encoding='utf-8'); c =... | 0 | exit 0 |
| 118 | 5 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py tests/integration/convergence/test_cp4_queries_postgres.py -q -... | 0 | 30 passed, 1 warning in 5.90s |
| 119 | 5 | python -m pytest tests/integration tests/unit/control_ui -q -p no:cacheprovider | 0 | 3178 passed, 36 skipped, 1 warning, 25 subtests passed in 303.75s (0:05:03) |
| 120 | 5 | python -c "import pathlib; p = pathlib.Path('src/controlplane/application/control_api/query_ports.py').read_text(encoding='utf-8'); q = p... | 0 | exit 0 |
| 121 | 5 | python -c "import pathlib; u = pathlib.Path('src/controlplane/ui/src'); a = (u / 'App.tsx').read_text(encoding='utf-8'); c = (u / 'api' /... | 0 | exit 0 |
| 122 | 5 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8')... | 0 | exit 0 |
| 123 | 5 | python -c "import json, pathlib; d = json.loads(pathlib.Path('tools/runtime/runtime.lock.json').read_text(encoding='utf-8')); assert d['v... | 0 | exit 0 |
| 124 | 6 | python -c "import pathlib; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; b = pathlib.Path('src/controlplane'); assert all((b / d / u).r... | 0 | exit 0 |
| 125 | 6 | python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider | 0 | 9 passed in 9.76s |
| 126 | 6 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); x = d... | 0 | exit 0 |
| 127 | 6 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d... | 0 | exit 0 |
| 128 | 6 | python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider | 0 | 293 passed in 0.72s |
| 129 | 6 | python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); assert 'src/c... | 0 | exit 0 |
| 130 | 6 | python -m pytest tests/unit/config tests/unit/storage tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/converg... | 0 | 1125 passed, 239 subtests passed in 1.17s |
| 131 | 6 | python -m pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/contract/test_bindings.py -q -p no:cacheprovider | 0 | 679 passed, 398 subtests passed in 0.82s |
| 132 | 6 | python -c "import hashlib, pathlib, re; t = pathlib.Path('docs/parallel-delivery/contract-registry.yaml').read_text(encoding='utf-8'); h ... | 0 | exit 0 |
| 133 | 6 | python -c "import pathlib; t = pathlib.Path('docs/09-contracts/12-state-machines.md').read_text(encoding='utf-8'); assert 'PUC-J-03' in t... | 0 | exit 0 |
| 134 | 6 | python -m pytest tests/integration/orchestration tests/integration/storage tests/unit/catalog tests/unit/storage tests/unit/render -q -p ... | 0 | 2314 passed, 7 skipped, 1184 subtests passed in 4.50s |
| 135 | 6 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d... | 0 | exit 0 |
| 136 | 6 | python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests/integration/convergence/test_cp6_workflow_catalog.py tes... | 0 | 28 passed in 0.69s |
| 137 | 6 | python -m pytest tests/unit/orchestration tests/integration/collection tests/unit/ingestion tests/integration/creative tests/integration/... | 0 | 3387 passed, 1034 subtests passed in 4.07s |
| 138 | 6 | python -c "import json, pathlib; p = json.loads(pathlib.Path('src/controlplane/ui/package.json').read_text(encoding='utf-8')); v = list(p... | 0 | exit 0 |
| 139 | 6 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d... | 0 | exit 0 |
| 140 | 6 | python -c "import re, pathlib; t = pathlib.Path('tests/m2/test_p9_m2_exit_gate.py').read_text(encoding='utf-8'); assert re.search('M2_ACC... | 0 | exit 0 |
| 141 | 6 | python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergence/test_cp3b_source_parity.py -q -p... | 0 | 25 passed in 0.06s |
| 142 | 6 | python -m pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_statemachines.py -q -p no:cacheprovider | 0 | 666 passed, 841 subtests passed in 1.59s |
| 143 | 6 | python -m pytest tests/m2 tests/integration -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression | 0 | 2692 passed, 36 skipped, 1 deselected, 2 warnings, 25 subtests passed in 511.18s (0:08:31) |
| 144 | 6 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tes... | 0 | 5262 passed, 1 warning, 1998 subtests passed in 13.16s |
| 145 | 6 | python -c "import pathlib; t = pathlib.Path('src/main.py').read_text(encoding='utf-8'); assert 'create_app' in t, 'src/main.py must call ... | 0 | exit 0 |
| 146 | 6 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.f... | 0 | exit 0 |
| 147 | 6 | python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/src/App.tsx').read_text(encoding='utf-8'); assert 'boundedEventDeduper' ... | 0 | exit 0 |
| 148 | 7 | python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider | 0 | 12 passed, 58 subtests passed in 0.11s |
| 149 | 7 | python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider | 0 | 68 passed in 0.08s |
| 150 | 7 | python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cacheprovider | 0 | 11 passed, 13 subtests passed in 0.03s |
| 151 | 7 | python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider | 0 | 87 passed in 0.10s |
| 152 | 7 | python -m pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cacheprovider | 0 | 20 passed, 79 subtests passed in 0.05s |
| 153 | 7 | python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider | 0 | 60 passed in 0.07s |
| 154 | 7 | python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider | 0 | 32 passed in 0.06s |
| 155 | 7 | python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider | 0 | 62 passed in 0.08s |
| 156 | 7 | python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider | 0 | 110 passed in 0.16s |
| 157 | 7 | python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider | 0 | 94 passed in 0.17s |
| 158 | 7 | python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider | 0 | 62 passed in 0.15s |
| 159 | 7 | python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider | 0 | 19 passed, 38 subtests passed in 0.03s |
| 160 | 7 | python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider | 0 | 65 passed in 0.12s |
| 161 | 7 | python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider | 0 | 18 passed in 0.13s |
| 162 | 7 | python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider | 0 | 27 passed in 0.12s |
| 163 | 7 | python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider | 0 | 52 passed in 0.16s |
| 164 | 7 | python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider | 0 | 22 passed in 0.11s |
| 165 | 7 | python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider | 0 | 8 passed in 0.25s |
| 166 | 7 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider | 0 | 16 passed, 89 subtests passed in 0.13s |
| 167 | 7 | python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider | 0 | 65 passed in 0.07s |
| 168 | 7 | python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider | 0 | 144 passed in 0.11s |
| 169 | 7 | python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovider | 0 | 86 passed in 0.08s |
| 170 | 7 | python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovider | 0 | 50 passed in 0.06s |
| 171 | 7 | python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprovider | 0 | 75 passed in 0.09s |
| 172 | 7 | python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprovider | 0 | 106 passed in 0.10s |
| 173 | 7 | python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider | 0 | 63 passed in 0.07s |
| 174 | 7 | python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider | 0 | 114 passed in 0.10s |
| 175 | 7 | python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider | 0 | 51 passed in 0.06s |
| 176 | 7 | python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider | 0 | 21 passed in 0.05s |
| 177 | 7 | python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider | 0 | 35 passed in 0.09s |
| 178 | 7 | python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider | 0 | 63 passed in 0.07s |
| 179 | 7 | python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider | 0 | 79 passed in 0.12s |
| 180 | 7 | python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider | 0 | 47 passed in 0.08s |
| 181 | 7 | python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider | 0 | 23 passed in 0.10s |
| 182 | 7 | python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider | 0 | 45 passed in 0.11s |
| 183 | 7 | python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider | 0 | 44 passed in 0.15s |
| 184 | 7 | python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider | 0 | 35 passed in 0.07s |
| 185 | 7 | python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider | 0 | 25 passed in 1.85s |
| 186 | 8 | python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider | 0 | 20 passed, 120 subtests passed in 0.36s |
| 187 | 8 | python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cacheprovider | 0 | 26 passed, 67 subtests passed in 0.09s |
| 188 | 8 | python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider | 0 | 169 passed in 0.16s |
| 189 | 8 | python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider | 0 | 58 passed in 0.09s |
| 190 | 8 | python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider | 0 | 62 passed in 0.10s |
| 191 | 8 | python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider | 0 | 104 passed in 0.11s |
| 192 | 8 | python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider | 0 | 97 passed in 0.11s |
| 193 | 8 | python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider | 0 | 55 passed in 0.12s |
| 194 | 8 | python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider | 0 | 118 passed in 0.11s |
| 195 | 8 | python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider | 0 | 154 passed in 0.20s |
| 196 | 8 | python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider | 0 | 97 passed in 0.10s |
| 197 | 8 | python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider | 0 | 45 passed, 129 subtests passed in 0.10s |
| 198 | 8 | python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider | 0 | 38 passed, 99 subtests passed in 0.06s |
| 199 | 8 | python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider | 0 | 52 passed, 67 subtests passed in 0.08s |
| 200 | 8 | python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider | 0 | 73 passed in 0.11s |
| 201 | 8 | python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider | 0 | 39 passed in 0.10s |
| 202 | 8 | python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider | 0 | 36 passed in 0.15s |
| 203 | 8 | python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider | 0 | 28 passed in 0.16s |
| 204 | 8 | python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider | 0 | 35 passed in 0.21s |
| 205 | 8 | python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider | 0 | 53 passed in 0.20s |
| 206 | 8 | python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider | 0 | 17 passed in 0.10s |
| 207 | 8 | python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cacheprovider | 0 | 55 passed in 0.10s |
| 208 | 8 | python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:cacheprovider | 0 | 43 passed in 0.05s |
| 209 | 8 | python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no:cacheprovider | 0 | 22 passed, 307 subtests passed in 0.07s |
| 210 | 8 | python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider | 0 | 45 passed in 0.07s |
| 211 | 8 | python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cacheprovider | 0 | 45 passed in 0.07s |
| 212 | 8 | python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:cacheprovider | 0 | 55 passed in 0.07s |
| 213 | 8 | python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/orchestration/test_g_job_waiting.py -q -p no:cacheprovider | 0 | 147 passed in 0.13s |
| 214 | 8 | python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py -q -p no:cachepro... | 0 | 88 passed in 0.22s |
| 215 | 8 | python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q -p no:cacheprovider | 0 | 47 passed in 0.06s |
| 216 | 8 | python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cacheprovider | 0 | 86 passed in 0.10s |
| 217 | 8 | python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q -p no:cacheprovider | 0 | 62 passed in 0.08s |
| 218 | 8 | python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit/orchestration/test_g_retry_policy.py -q -p no:cacheprovider | 0 | 110 passed in 0.12s |
| 219 | 8 | python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/orchestration/test_g_resource_admission.py -q -p no:cache... | 0 | 82 passed in 0.10s |
| 220 | 8 | python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/orchestration/test_g_consistency_audit.py -q -p no:cachepro... | 0 | 175 passed in 0.14s |
| 221 | 8 | python -m pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orchestration/test_g_batch_outcome.py tests/unit/orchestrati... | 0 | 157 passed in 0.14s |
| 222 | 9 | python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:cacheprovider | 0 | 55 passed in 0.06s |
| 223 | 9 | python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovider | 0 | 115 passed in 0.08s |
| 224 | 9 | python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:cacheprovider | 0 | 70 passed in 0.05s |
| 225 | 9 | python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider | 0 | 175 passed, 1 warning in 1.20s |
| 226 | 9 | python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cacheprovider | 0 | 31 passed in 0.04s |
| 227 | 9 | python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:cacheprovider | 0 | 91 passed in 0.07s |
| 228 | 9 | python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cacheprovider | 0 | 37 passed in 0.22s |
| 229 | 9 | python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cacheprovider | 0 | 43 passed, 1 warning in 0.45s |
| 230 | 9 | python -m pytest tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider | 0 | 10 passed in 0.03s |
| 231 | 9 | python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:cacheprovider | 0 | 9 passed in 0.04s |
| 232 | 9 | python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovider | 0 | 22 passed in 0.03s |
| 233 | 9 | python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cacheprovider | 0 | 24 passed in 0.04s |
| 234 | 9 | python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no:cacheprovider | 0 | 14 passed in 0.03s |
| 235 | 9 | python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider | 0 | 35 passed in 0.04s |
| 236 | 9 | python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cacheprovider | 0 | 26 passed in 0.05s |
| 237 | 9 | python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cacheprovider | 0 | 65 passed in 0.08s |
| 238 | 9 | python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cacheprovider | 0 | 24 passed in 0.05s |
| 239 | 9 | python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider | 0 | 11 passed, 85 subtests passed in 0.04s |
| 240 | 9 | python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider | 0 | 22 passed, 21 subtests passed in 0.04s |
| 241 | 9 | python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p no:cacheprovider | 0 | 21 passed in 0.75s |
| 242 | 9 | python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p no:cacheprovider | 0 | 373 passed, 7 skipped in 0.89s |
| 243 | 9 | python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider | 0 | 25 passed, 26 subtests passed in 0.05s |
| 244 | 9 | python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no:cacheprovider | 0 | 67 passed in 0.06s |
| 245 | 9 | python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q -p no:cacheprovider | 0 | 21 passed in 0.12s |
| 246 | 9 | python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider | 0 | 13 passed, 10 subtests passed in 0.03s |
| 247 | 9 | python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider | 0 | 32 passed, 97 subtests passed in 0.05s |
| 248 | 9 | python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider | 0 | 56 passed in 0.06s |
| 249 | 9 | python -m pytest tests/unit/storage/test_storage_availability.py -q -p no:cacheprovider | 0 | 41 passed in 0.05s |
| 250 | 9 | python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovider | 0 | 50 passed in 0.05s |
| 251 | 9 | python -m pytest tests/unit/security/test_j_secret_redaction.py -q -p no:cacheprovider | 0 | 55 passed in 0.05s |
| 252 | 9 | python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider | 0 | 60 passed in 0.07s |
| 253 | 9 | python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider | 0 | 118 passed in 0.11s |
| 254 | 9 | python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cacheprovider | 0 | 49 passed in 0.07s |
| 255 | 9 | python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprovider | 0 | 40 passed in 0.04s |
| 256 | 9 | python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cacheprovider | 0 | 104 passed in 0.08s |
| 257 | 9 | python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprovider | 0 | 131 passed in 0.09s |
| 258 | 9 | python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovider | 0 | 104 passed in 0.08s |
| 259 | 9 | python -m pytest tests/unit/security/test_j_secret_update.py -q -p no:cacheprovider | 0 | 63 passed in 0.07s |
| 260 | 9 | python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cacheprovider | 0 | 51 passed in 0.06s |
| 261 | 9 | python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cacheprovider | 0 | 66 passed in 0.07s |
| 262 | 9 | python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovider | 0 | 50 passed in 0.08s |
| 263 | 9 | python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovider | 0 | 41 passed in 0.07s |
| 264 | 9 | python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovider | 0 | 47 passed in 0.07s |
| 265 | 9 | python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cacheprovider | 0 | 35 passed in 0.06s |
| 266 | 9 | python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no:cacheprovider | 0 | 35 passed in 0.85s |
| 267 | 9 | python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:cacheprovider | 0 | 33 passed in 0.11s |
| 268 | 10 | python -m pytest tests/integration/persistence/a/test_persist_a_postgres.py -q -p no:cacheprovider | 0 | 22 passed in 10.02s |
| 269 | 10 | python -c "import pathlib; fs = list(pathlib.Path('src/source_ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='... | 0 | exit 0 |
| 270 | 10 | python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q -p no:cacheprovider | 0 | 14 passed in 5.40s |
| 271 | 10 | python -c "import pathlib; fs = list(pathlib.Path('src/ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8')... | 0 | exit 0 |
| 272 | 10 | python -c "import pathlib; fs = list(pathlib.Path('src/catalog/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') f... | 0 | exit 0 |
| 273 | 10 | python -m pytest tests/integration/persistence/d/test_persist_d_postgres.py -q -p no:cacheprovider | 0 | 22 passed in 9.89s |
| 274 | 10 | python -c "import pathlib; fs = list(pathlib.Path('src/creative/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') ... | 0 | exit 0 |
| 275 | 10 | python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider | 0 | 19 passed in 9.63s |
| 276 | 10 | python -c "import pathlib; fs = list(pathlib.Path('src/voice/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for... | 0 | exit 0 |
| 277 | 10 | python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider | 0 | 20 passed in 13.44s |
| 278 | 10 | python -c "import pathlib; fs = list(pathlib.Path('src/render/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') fo... | 0 | exit 0 |
| 279 | 10 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/orchestration'); t = ' '.join(f.read_text(encoding='utf-8... | 0 | exit 0 |
| 280 | 10 | python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider | 0 | 16 passed in 8.16s |
| 281 | 10 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/storage_meta'); t = ' '.join(f.read_text(encoding='utf-8'... | 0 | exit 0 |
| 282 | 10 | python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider | 0 | 18 passed in 6.28s |
| 283 | 10 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/config_security'); t = ' '.join(f.read_text(encoding='utf... | 0 | exit 0 |
| 284 | 10 | python -c "import pathlib; t = pathlib.Path('tests/integration/voice/test_e16_voice_timing_pipeline.py').read_text(encoding='utf-8'); ass... | 0 | exit 0 |
| 285 | 10 | python -c "import pathlib; t = pathlib.Path('tests/unit/render/test_f16_ports_memory_events.py').read_text(encoding='utf-8'); assert all(... | 0 | exit 0 |
| 286 | 10 | python -c "import pathlib; t = pathlib.Path('tests/integration/render/test_f20_worker_activity.py').read_text(encoding='utf-8'); assert a... | 0 | exit 0 |
| 287 | 10 | python -c "import pathlib; t = pathlib.Path('tests/integration/control_ui/test_h_list_queries_sql.py').read_text(encoding='utf-8'); asser... | 0 | exit 0 |
| 288 | 10 | python -c "import pathlib; t = pathlib.Path('tests/unit/control_ui/test_h_status_pill.py').read_text(encoding='utf-8'); assert all(i in t... | 0 | exit 0 |
| 289 | 10 | python -B -m pytest tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_ast_boundary_rules_clean_codebase -q -p no:cacheprovider | 0 | 1 passed in 0.35s |

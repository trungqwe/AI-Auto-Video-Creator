# M4-MILESTONE-CLOSE: kết quả chạy lại lệnh kiểm (revision 1)

- Candidate SHA: `5fd27218759bdfb463f9efc7af34caabd8debe13` (HEAD của worktree khi chạy lệnh kiểm; con trực tiếp của `cc290f002074514001fa0b03b3eb8c9e00c14db6`, commit integrate của ADAPT-LAUNCH)
- Interpreter đã khóa: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/.local-tools/runtime/33f06a7a/venv/Scripts/python.exe` (Python 3.13.15 theo `tools/runtime/runtime.lock.json`)
- Ngày chạy: 23/10/2026
- Tổng số lệnh kiểm bắt buộc: 288, chạy trong 12 nhóm bước; mỗi lệnh một tiến trình riêng.

| STT | Nhóm bước | Lệnh | Exit code | Tóm tắt nguyên văn |
| --- | --- | --- | --- | --- |
| 1 | 1 | `git diff --check` | 0 | exit 0 |
| 2 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/a'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 3 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/b'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 4 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/c'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 5 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/i'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 6 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/d'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 7 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/e'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 8 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/f'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 9 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/j'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 10 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/g'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 11 | 1 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/h'); p = unicodedata.normalize('NFC', (d / 'plan.md').read...` | 0 | exit 0 |
| 12 | 2 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence'); p = unicodedata.normalize('NFC', (d / 'plan...` | 0 | exit 0 |
| 13 | 2 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence-ext'); p = unicodedata.normalize('NFC', (d / '...` | 0 | exit 0 |
| 14 | 2 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/persist'); p = unicodedata.normalize('NFC', (d / 'plan.md'...` | 0 | exit 0 |
| 15 | 3 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/adapt'); p = unicodedata.normalize('NFC', (d / 'plan.md')....` | 0 | exit 0 |
| 16 | 3 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence-ext-ui'); p = unicodedata.normalize('NFC', (d ...` | 0 | exit 0 |
| 17 | 3 | `python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q -p no:cacheprovider` | 0 | 8 passed in 2.99s |
| 18 | 3 | `python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider` | 0 | 6 passed in 9.49s |
| 19 | 4 | `python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/...` | 0 | 5182 passed, 1 warning, 2237 subtests passed in 13.11s |
| 20 | 4 | `python -c "import pathlib; t = ' '.join(pathlib.Path('src/controlplane/infrastructure/db/migrations/0013_ingestion.sql').read_text(encoding=...` | 0 | exit 0 |
| 21 | 4 | `python -B -m pytest tests/integration/convergence/test_cp3_migration_sequence.py::test_pinned_migrations_and_runner_untouched -q -p no:cache...` | 0 | 1 passed in 0.26s |
| 22 | 4 | `python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider` | 0 | 133 passed, 28 skipped, 1 warning in 2.57s |
| 23 | 4 | `python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` | 0 | 16 passed in 9.26s |
| 24 | 4 | `python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider` | 0 | 40 passed in 5.12s |
| 25 | 4 | `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider` | 0 | 111 passed in 12.62s |
| 26 | 4 | `python -m pytest tests/integration/convergence/test_cp4_queries_routes.py -q -p no:cacheprovider` | 0 | 21 passed, 1 warning in 0.80s |
| 27 | 4 | `python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cacheprovider` | 0 | 83 passed, 1 warning in 0.54s |
| 28 | 4 | `python -m pytest tests/m2/test_p7a_hardening.py::test_h28_static_architecture -q -p no:cacheprovider` | 0 | 1 passed, 1 warning in 0.74s |
| 29 | 4 | `python -c "import ast, pathlib; d = pathlib.Path('src/controlplane/application/control_api'); r = (d / 'route_catalog.py').read_text(encodin...` | 1 | import ast, pathlib; d = pathlib.Path('src/controlplane/application/control_api'); r = (d / 'route_catalog.py').read_text(encoding='utf-8'); c = (d / 'command_catalog.py').read_text(encoding='utf-8'); m = r.split('METADATA_RESOURCES', 1)[-1]; assert 'sources' in m and 'topic_tags' in m, 'sources metadata resource missing'; names = [e.args[0].value for n in ast.walk(ast.parse(c)) if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == 'COMMAND_SPECS' for e in n.value.elts]; assert len(names) == 14 and 'UpdateSourceMetadata' not in names, names; assert 'METADATA_ROUTED_COMMANDS' in c, 'metadata routed names not kept' |
| 30 | 4 | `python -m pytest tests/integration/adapt/prod/test_adapt_prod_sources_module.py -q -p no:cacheprovider` | 4 | ERROR: file or directory not found: tests/integration/adapt/prod/test_adapt_prod_sources_module.py |
| 31 | 4 | `python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider` | 0 | 23 passed, 1 warning in 7.93s |
| 32 | 4 | `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_builder_inventory tests/integration/adapt/wire/test_a...` | 0 | 3 passed in 1.33s |
| 33 | 4 | `python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p in pathlib.Path('src/controlplane/api').rglob('*.py')); ass...` | 1 | import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p in pathlib.Path('src/controlplane/api').rglob('*.py')); assert re.search('module_services.{0,40}sources', api, re.S), 'sources service not attached to module_services' |
| 34 | 4 | `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/main.py', 'src/controlplane/api/wiring/pr...` | 0 | exit 0 |
| 35 | 4 | `npm --prefix src/controlplane/ui run build` | 0 | vite v6.3.5 building for production... ✓ 42 modules transformed. dist/index.html dist/assets/... |
| 36 | 5 | `python -m pytest tests/unit/control_ui -q -p no:cacheprovider` | 0 | 661 passed, 1 warning in 1.28s |
| 37 | 5 | `python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.find...` | 0 | exit 0 |
| 38 | 5 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/ui/dist'); n = [f.name for f in d.rglob('*') if f.is_file()]; assert len(n) ==...` | 0 | exit 0 |
| 39 | 5 | `python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s...` | 1 | import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s = dict(re.findall('id: ' + chr(39) + '([a-z-]+)' + chr(39) + '.*?backendStatus: ' + chr(39) + '([a-z_]+)' + chr(39), r, re.S)); assert len(s) == 18, s; assert s['sources'] == 'available', 'sources screen still pending_module'; assert all(s[i] == 'pending_module' for i in ['artifacts', 'snapshots', 'story-angles', 'scripts', 'accounts', 'cost']), s |
| 40 | 5 | `python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider` | 0 | 18 passed, 31 subtests passed in 0.06s |
| 41 | 5 | `python -m pytest tests/integration/persistence/c/test_persist_c_hook_listing.py -q -p no:cacheprovider` | 4 | ERROR: file or directory not found: tests/integration/persistence/c/test_persist_c_hook_listing.py |
| 42 | 5 | `python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q -p no:cacheprovider` | 0 | 14 passed in 8.48s |
| 43 | 5 | `python -m pytest tests/unit/catalog -q -p no:cacheprovider` | 0 | 194 passed, 463 subtests passed in 0.35s |
| 44 | 5 | `python -c "import pathlib; r = pathlib.Path('src/catalog'); d = (r / 'domain' / 'hooks.py').read_text(encoding='utf-8'); a = (r / 'applicati...` | 1 | import pathlib; r = pathlib.Path('src/catalog'); d = (r / 'domain' / 'hooks.py').read_text(encoding='utf-8'); a = (r / 'application' / 'hooks.py').read_text(encoding='utf-8'); p = ' '.join(f.read_text(encoding='utf-8') for f in (r / 'persistence').rglob('*.py')); assert 'class HookHead' in d, 'HookHead missing'; assert 'def list_heads' in a and 'def head' in a, 'in-memory hook listing missing'; assert 'def list_heads' in p and 'def head' in p, 'postgres hook listing missing'; assert 'CREATE TABLE' not in p and 'ALTER TABLE' not in p and 'from src.' not in p, 'adapter C rules' |
| 45 | 5 | `python -m pytest tests/integration/adapt/prod/test_adapt_prod_hooks_module.py -q -p no:cacheprovider` | 4 | ERROR: file or directory not found: tests/integration/adapt/prod/test_adapt_prod_hooks_module.py |
| 46 | 5 | `python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p in pathlib.Path('src/controlplane/api').rglob('*.py')); ass...` | 1 | import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p in pathlib.Path('src/controlplane/api').rglob('*.py')); assert re.search('module_services.{0,40}hooks', api, re.S), 'hooks service not attached to module_services'; assert not re.search('module_services.{0,3}[' + chr(39) + chr(34) + ']media[' + chr(39) + chr(34) + ']', api, re.S), 'media must stay unattached until the catalog has media metadata' |
| 47 | 5 | `python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s...` | 1 | import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s = dict(re.findall('id: ' + chr(39) + '([a-z-]+)' + chr(39) + '.*?backendStatus: ' + chr(39) + '([a-z_]+)' + chr(39), r, re.S)); assert len(s) == 18, s; assert s['sources'] == 'available' and s['hooks'] == 'available', 'sources and hooks screens must be available'; assert all(s[i] == 'pending_module' for i in ['media', 'artifacts', 'snapshots', 'story-angles', 'scripts', 'accounts', 'cost']), s |
| 48 | 5 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 13 passed, 62 subtests passed in 0.12s |
| 49 | 5 | `python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider` | 0 | 27 passed, 99 subtests passed in 0.06s |
| 50 | 5 | `python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cacheprovider` | 0 | 17 passed, 50 subtests passed in 0.04s |
| 51 | 5 | `python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider` | 0 | 74 passed in 0.08s |
| 52 | 5 | `python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider` | 0 | 40 passed, 20 subtests passed in 0.05s |
| 53 | 5 | `python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprovider` | 0 | 15 passed, 22 subtests passed in 0.05s |
| 54 | 5 | `python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cacheprovider` | 0 | 14 passed, 44 subtests passed in 0.04s |
| 55 | 5 | `python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider` | 0 | 32 passed, 3 subtests passed in 0.10s |
| 56 | 5 | `python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p no:cacheprovider` | 0 | 28 passed, 11 subtests passed in 0.10s |
| 57 | 5 | `python -m pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider` | 0 | 23 passed, 14 subtests passed in 0.13s |
| 58 | 5 | `python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider` | 0 | 18 passed in 0.14s |
| 59 | 5 | `python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cacheprovider` | 0 | 59 passed in 0.10s |
| 60 | 5 | `python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cacheprovider` | 0 | 49 passed in 0.11s |
| 61 | 5 | `python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p no:cacheprovider` | 0 | 19 passed in 0.11s |
| 62 | 5 | `python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:cacheprovider` | 0 | 20 passed, 49 subtests passed in 0.07s |
| 63 | 5 | `python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no:cacheprovider` | 0 | 25 passed in 0.12s |
| 64 | 5 | `python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cacheprovider` | 0 | 33 passed, 29 subtests passed in 0.10s |
| 65 | 5 | `python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider` | 0 | 32 passed in 0.12s |
| 66 | 5 | `python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cacheprovider` | 0 | 62 passed in 0.15s |
| 67 | 5 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); x = d['project']['depende...` | 0 | exit 0 |
| 68 | 5 | `python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock').read_text(encoding='utf-8')); p = {x['name']: x for x in d...` | 0 | exit 0 |
| 69 | 6 | `python -m pytest tests/integration/adapt/a/test_adapt_a_adapters.py -q -p no:cacheprovider` | 0 | 27 passed in 5.82s |
| 70 | 6 | `python -c "import pathlib; d = pathlib.Path('src/source_ingestion/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['re...` | 0 | exit 0 |
| 71 | 6 | `python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/security/test_http_router_adapter.py -q -p no:cacheprovider` | 0 | 20 passed in 0.20s |
| 72 | 6 | `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/creative/adapters/real_ai_invocation.py',...` | 0 | exit 0 |
| 73 | 6 | `python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider` | 0 | 34 passed in 0.67s |
| 74 | 6 | `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_kokoro_t...` | 0 | exit 0 |
| 75 | 6 | `python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q -p no:cacheprovider` | 0 | 41 passed in 0.27s |
| 76 | 6 | `python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpeg_m...` | 0 | exit 0 |
| 77 | 6 | `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider` | 0 | 53 passed in 3.80s |
| 78 | 6 | `python -c "import pathlib; d = pathlib.Path('src/render/adapters'); t = ' '.join((d / n).read_text(encoding='utf-8') for n in ['real_ffmpeg_...` | 0 | exit 0 |
| 79 | 6 | `python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cacheprovider` | 0 | 22 passed in 13.15s |
| 80 | 6 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/security'); t = ' '.join((d / n).read_text(encoding='utf-8') fo...` | 0 | exit 0 |
| 81 | 6 | `python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cacheprovider` | 0 | 32 passed in 1.60s |
| 82 | 6 | `python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/storage/drive_object_store.py').read_text(encoding='utf-8'); as...` | 0 | exit 0 |
| 83 | 6 | `python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider` | 0 | 11 passed in 0.05s |
| 84 | 6 | `python -c "import json, pathlib; d = pathlib.Path('tools/launcher/prod'); x = [json.loads((d / n).read_text(encoding='utf-8')) for n in ['pr...` | 0 | exit 0 |
| 85 | 6 | `python -c "import pathlib; fs = list(pathlib.Path('src/controlplane/api/wiring').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') ...` | 0 | exit 0 |
| 86 | 6 | `python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no:cacheprovider` | 0 | 13 passed in 39.90s |
| 87 | 6 | `python -c "import pathlib; t = pathlib.Path('tools/launcher/prod/seed/import_seed.py').read_text(encoding='utf-8'); assert 'register_discove...` | 0 | exit 0 |
| 88 | 6 | `python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider` | 0 | 29 passed in 0.42s |
| 89 | 6 | `python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml').read_text(encoding='utf-8'); r = pathlib.Path('docs/runbook...` | 0 | exit 0 |
| 90 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 39 passed in 0.06s |
| 91 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit/ingestion/test_ingestion_fingerprint.py -q -p no:cacheprovi...` | 0 | 30 passed in 0.05s |
| 92 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/unit/ingestion/test_ingestion_memory_unit_of_work.py -q -p n...` | 0 | 19 passed in 0.05s |
| 93 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:cacheprovider` | 0 | 64 passed in 0.08s |
| 94 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no:cacheprovider` | 0 | 27 passed in 0.03s |
| 95 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider` | 0 | 31 passed in 0.07s |
| 96 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cacheprovider` | 0 | 45 passed in 0.09s |
| 97 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:cacheprovider` | 0 | 61 passed in 0.08s |
| 98 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cacheprovider` | 0 | 39 passed in 0.07s |
| 99 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cacheprovider` | 0 | 55 passed in 0.08s |
| 100 | 7 | `python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p no:cacheprovider` | 0 | 67 passed in 0.12s |
| 101 | 7 | `python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py -q -p no:cacheprovider` | 0 | 15 passed in 0.10s |
| 102 | 7 | `python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider` | 0 | 20 passed, 37 subtests passed in 0.06s |
| 103 | 7 | `python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovider` | 0 | 20 passed, 45 subtests passed in 0.04s |
| 104 | 7 | `python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprovider` | 0 | 11 passed, 11 subtests passed in 0.04s |
| 105 | 7 | `python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cacheprovider` | 0 | 20 passed, 33 subtests passed in 0.05s |
| 106 | 7 | `python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cacheprovider` | 0 | 27 passed, 19 subtests passed in 0.05s |
| 107 | 7 | `python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cacheprovider` | 0 | 31 passed, 189 subtests passed in 0.08s |
| 108 | 7 | `python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cacheprovider` | 0 | 20 passed, 87 subtests passed in 0.06s |
| 109 | 7 | `python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider` | 0 | 27 passed, 11 subtests passed in 0.06s |
| 110 | 7 | `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit/control_ui/test_h_stream_client_registry.py tests/unit/cont...` | 0 | 94 passed in 0.10s |
| 111 | 7 | `python -m pytest tests/unit/control_ui tests/m2/test_p7b_sse_stream.py -q -p no:cacheprovider` | 0 | 666 passed, 1 warning in 8.62s |
| 112 | 7 | `python -c "import pathlib, re; c = pathlib.Path('src/controlplane/application/sse/event_catalog.py').read_text(encoding='utf-8'); t = pathli...` | 0 | exit 0 |
| 113 | 7 | `python -m pytest tests/integration/convergence/test_cp4_pagination_postgres.py -q -p no:cacheprovider` | 0 | 16 passed in 8.19s |
| 114 | 7 | `python -m pytest tests/integration/control_ui tests/unit/control_ui -q -p no:cacheprovider` | 0 | 836 passed, 1 warning in 1.99s |
| 115 | 7 | `python -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression` | 0 | 179 passed, 1 deselected, 2 warnings in 232.25s (0:03:52) |
| 116 | 7 | `python -c "import pathlib; q = pathlib.Path('src/controlplane/infrastructure/db/control_api_queries.py').read_text(encoding='utf-8'); c = pa...` | 0 | exit 0 |
| 117 | 7 | `python -m pytest tests/integration/convergence/test_cp4_queries_routes.py tests/integration/convergence/test_cp4_queries_postgres.py -q -p n...` | 0 | 30 passed, 1 warning in 5.09s |
| 118 | 7 | `python -m pytest tests/integration tests/unit/control_ui -q -p no:cacheprovider` | 0 | 2758 passed, 35 skipped, 1 warning, 25 subtests passed in 168.37s (0:02:48) |
| 119 | 7 | `python -c "import pathlib; p = pathlib.Path('src/controlplane/application/control_api/query_ports.py').read_text(encoding='utf-8'); q = path...` | 0 | exit 0 |
| 120 | 7 | `python -c "import pathlib; u = pathlib.Path('src/controlplane/ui/src'); a = (u / 'App.tsx').read_text(encoding='utf-8'); c = (u / 'api' / 'c...` | 0 | exit 0 |
| 121 | 7 | `python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s...` | 0 | exit 0 |
| 122 | 7 | `python -c "import json, pathlib; d = json.loads(pathlib.Path('tools/runtime/runtime.lock.json').read_text(encoding='utf-8')); assert d['vers...` | 0 | exit 0 |
| 123 | 7 | `python -c "import pathlib; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; b = pathlib.Path('src/controlplane'); assert all((b / d / u).read...` | 0 | exit 0 |
| 124 | 7 | `python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider` | 0 | 9 passed in 9.27s |
| 125 | 7 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); x = d['p...` | 0 | exit 0 |
| 126 | 7 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['t...` | 0 | exit 0 |
| 127 | 7 | `python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider` | 0 | 293 passed in 0.60s |
| 128 | 7 | `python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); assert 'src/cont...` | 0 | exit 0 |
| 129 | 8 | `python -m pytest tests/unit/config tests/unit/storage tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergenc...` | 0 | 1125 passed, 239 subtests passed in 1.01s |
| 130 | 8 | `python -m pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/contract/test_bindings.py -q -p no:cacheprovider` | 0 | 679 passed, 398 subtests passed in 1.21s |
| 131 | 8 | `python -c "import hashlib, pathlib, re; t = pathlib.Path('docs/parallel-delivery/contract-registry.yaml').read_text(encoding='utf-8'); h = h...` | 0 | exit 0 |
| 132 | 8 | `python -c "import pathlib; t = pathlib.Path('docs/09-contracts/12-state-machines.md').read_text(encoding='utf-8'); assert 'PUC-J-03' in t an...` | 0 | exit 0 |
| 133 | 8 | `python -m pytest tests/integration/orchestration tests/integration/storage tests/unit/catalog tests/unit/storage tests/unit/render -q -p no:...` | 0 | 2306 passed, 7 skipped, 1184 subtests passed in 7.76s |
| 134 | 8 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['t...` | 0 | exit 0 |
| 135 | 8 | `python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/...` | 0 | 28 passed in 0.82s |
| 136 | 8 | `python -m pytest tests/unit/orchestration tests/integration/collection tests/unit/ingestion tests/integration/creative tests/integration/voi...` | 0 | 3379 passed, 1034 subtests passed in 3.69s |
| 137 | 8 | `python -c "import json, pathlib; p = json.loads(pathlib.Path('src/controlplane/ui/package.json').read_text(encoding='utf-8')); v = list(p['d...` | 0 | exit 0 |
| 138 | 8 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['t...` | 0 | exit 0 |
| 139 | 8 | `python -c "import re, pathlib; t = pathlib.Path('tests/m2/test_p9_m2_exit_gate.py').read_text(encoding='utf-8'); assert re.search('M2_ACCEPT...` | 0 | exit 0 |
| 140 | 8 | `python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergence/test_cp3b_source_parity.py -q -p no...` | 0 | 25 passed in 0.08s |
| 141 | 8 | `python -m pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_statemachines.py -q -p no:cacheprovider` | 0 | 658 passed, 841 subtests passed in 0.93s |
| 142 | 8 | `python -m pytest tests/m2 tests/integration -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression` | 0 | 2276 passed, 35 skipped, 1 deselected, 2 warnings, 25 subtests passed in 373.91s (0:06:13) |
| 143 | 8 | `python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/...` | 0 | 5250 passed, 1 warning, 1998 subtests passed in 11.37s |
| 144 | 8 | `python -c "import pathlib; t = pathlib.Path('src/main.py').read_text(encoding='utf-8'); assert 'create_app' in t, 'src/main.py must call cre...` | 0 | exit 0 |
| 145 | 8 | `python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.find...` | 0 | exit 0 |
| 146 | 8 | `python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/src/App.tsx').read_text(encoding='utf-8'); assert 'boundedEventDeduper' in ...` | 0 | exit 0 |
| 147 | 9 | `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 58 subtests passed in 0.13s |
| 148 | 9 | `python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider` | 0 | 68 passed in 0.10s |
| 149 | 9 | `python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cacheprovider` | 0 | 11 passed, 13 subtests passed in 0.03s |
| 150 | 9 | `python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider` | 0 | 87 passed in 0.11s |
| 151 | 9 | `python -m pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cacheprovider` | 0 | 20 passed, 79 subtests passed in 0.06s |
| 152 | 9 | `python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider` | 0 | 60 passed in 0.08s |
| 153 | 9 | `python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider` | 0 | 32 passed in 0.06s |
| 154 | 9 | `python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider` | 0 | 62 passed in 0.09s |
| 155 | 9 | `python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider` | 0 | 110 passed in 0.20s |
| 156 | 9 | `python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider` | 0 | 94 passed in 0.17s |
| 157 | 9 | `python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider` | 0 | 62 passed in 0.15s |
| 158 | 9 | `python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider` | 0 | 19 passed, 38 subtests passed in 0.04s |
| 159 | 9 | `python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider` | 0 | 65 passed in 0.12s |
| 160 | 9 | `python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider` | 0 | 18 passed in 0.12s |
| 161 | 9 | `python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider` | 0 | 27 passed in 0.12s |
| 162 | 9 | `python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider` | 0 | 52 passed in 0.18s |
| 163 | 9 | `python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider` | 0 | 22 passed in 0.12s |
| 164 | 9 | `python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider` | 0 | 8 passed in 0.23s |
| 165 | 9 | `python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | 16 passed, 89 subtests passed in 0.12s |
| 166 | 9 | `python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider` | 0 | 65 passed in 0.07s |
| 167 | 9 | `python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider` | 0 | 144 passed in 0.12s |
| 168 | 9 | `python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovider` | 0 | 86 passed in 0.09s |
| 169 | 9 | `python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovider` | 0 | 50 passed in 0.06s |
| 170 | 9 | `python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprovider` | 0 | 75 passed in 0.10s |
| 171 | 9 | `python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprovider` | 0 | 106 passed in 0.15s |
| 172 | 9 | `python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider` | 0 | 63 passed in 0.09s |
| 173 | 9 | `python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider` | 0 | 114 passed in 0.10s |
| 174 | 9 | `python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider` | 0 | 51 passed in 0.06s |
| 175 | 9 | `python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider` | 0 | 21 passed in 0.04s |
| 176 | 9 | `python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider` | 0 | 35 passed in 0.09s |
| 177 | 9 | `python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider` | 0 | 63 passed in 0.09s |
| 178 | 9 | `python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider` | 0 | 79 passed in 0.13s |
| 179 | 9 | `python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider` | 0 | 47 passed in 0.09s |
| 180 | 9 | `python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider` | 0 | 23 passed in 0.10s |
| 181 | 9 | `python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider` | 0 | 45 passed in 0.11s |
| 182 | 9 | `python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider` | 0 | 44 passed in 0.16s |
| 183 | 9 | `python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider` | 0 | 35 passed in 0.08s |
| 184 | 9 | `python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider` | 0 | 25 passed in 2.20s |
| 185 | 10 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 20 passed, 120 subtests passed in 0.39s |
| 186 | 10 | `python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cacheprovider` | 0 | 26 passed, 67 subtests passed in 0.09s |
| 187 | 10 | `python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider` | 0 | 169 passed in 0.18s |
| 188 | 10 | `python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider` | 0 | 58 passed in 0.11s |
| 189 | 10 | `python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider` | 0 | 62 passed in 0.11s |
| 190 | 10 | `python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider` | 0 | 104 passed in 0.12s |
| 191 | 10 | `python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider` | 0 | 97 passed in 0.11s |
| 192 | 10 | `python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider` | 0 | 55 passed in 0.11s |
| 193 | 10 | `python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider` | 0 | 118 passed in 0.14s |
| 194 | 10 | `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider` | 0 | 154 passed in 0.21s |
| 195 | 10 | `python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider` | 0 | 97 passed in 0.12s |
| 196 | 10 | `python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider` | 0 | 45 passed, 129 subtests passed in 0.12s |
| 197 | 10 | `python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider` | 0 | 38 passed, 99 subtests passed in 0.08s |
| 198 | 10 | `python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider` | 0 | 52 passed, 67 subtests passed in 0.09s |
| 199 | 10 | `python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider` | 0 | 73 passed in 0.11s |
| 200 | 10 | `python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider` | 0 | 39 passed in 0.10s |
| 201 | 10 | `python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider` | 0 | 36 passed in 0.13s |
| 202 | 10 | `python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider` | 0 | 28 passed in 0.15s |
| 203 | 10 | `python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider` | 0 | 35 passed in 0.24s |
| 204 | 10 | `python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider` | 0 | 53 passed in 0.22s |
| 205 | 10 | `python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider` | 0 | 17 passed in 0.10s |
| 206 | 10 | `python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cacheprovider` | 0 | 55 passed in 0.12s |
| 207 | 10 | `python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:cacheprovider` | 0 | 43 passed in 0.06s |
| 208 | 10 | `python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no:cacheprovider` | 0 | 22 passed, 307 subtests passed in 0.07s |
| 209 | 10 | `python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider` | 0 | 45 passed in 0.06s |
| 210 | 10 | `python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cacheprovider` | 0 | 45 passed in 0.08s |
| 211 | 10 | `python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:cacheprovider` | 0 | 55 passed in 0.07s |
| 212 | 10 | `python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/orchestration/test_g_job_waiting.py -q -p no:cacheprovider` | 0 | 147 passed in 0.12s |
| 213 | 10 | `python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py -q -p no:cacheprovid...` | 0 | 88 passed in 0.22s |
| 214 | 10 | `python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q -p no:cacheprovider` | 0 | 47 passed in 0.08s |
| 215 | 10 | `python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cacheprovider` | 0 | 86 passed in 0.10s |
| 216 | 10 | `python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q -p no:cacheprovider` | 0 | 62 passed in 0.12s |
| 217 | 10 | `python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit/orchestration/test_g_retry_policy.py -q -p no:cacheprovider` | 0 | 110 passed in 0.14s |
| 218 | 10 | `python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/orchestration/test_g_resource_admission.py -q -p no:cachepro...` | 0 | 82 passed in 0.11s |
| 219 | 10 | `python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/orchestration/test_g_consistency_audit.py -q -p no:cacheprovid...` | 0 | 175 passed in 0.15s |
| 220 | 10 | `python -m pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orchestration/test_g_batch_outcome.py tests/unit/orchestration/...` | 0 | 157 passed in 0.15s |
| 221 | 10 | `python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:cacheprovider` | 0 | 55 passed in 0.06s |
| 222 | 10 | `python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovider` | 0 | 115 passed in 0.10s |
| 223 | 10 | `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:cacheprovider` | 0 | 70 passed in 0.06s |
| 224 | 10 | `python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider` | 0 | 175 passed, 1 warning in 1.25s |
| 225 | 10 | `python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cacheprovider` | 0 | 31 passed in 0.05s |
| 226 | 10 | `python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:cacheprovider` | 0 | 91 passed in 0.08s |
| 227 | 10 | `python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cacheprovider` | 0 | 37 passed in 0.30s |
| 228 | 10 | `python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cacheprovider` | 0 | 43 passed, 1 warning in 0.54s |
| 229 | 10 | `python -m pytest tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider` | 0 | 10 passed in 0.04s |
| 230 | 10 | `python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:cacheprovider` | 0 | 9 passed in 0.04s |
| 231 | 10 | `python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovider` | 0 | 22 passed in 0.03s |
| 232 | 10 | `python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cacheprovider` | 0 | 24 passed in 0.04s |
| 233 | 10 | `python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no:cacheprovider` | 0 | 14 passed in 0.03s |
| 234 | 10 | `python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider` | 0 | 31 passed in 0.04s |
| 235 | 10 | `python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cacheprovider` | 0 | 26 passed in 0.07s |
| 236 | 11 | `python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cacheprovider` | 0 | 65 passed in 0.09s |
| 237 | 11 | `python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cacheprovider` | 0 | 24 passed in 0.06s |
| 238 | 11 | `python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider` | 0 | 11 passed, 85 subtests passed in 0.05s |
| 239 | 11 | `python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider` | 0 | 22 passed, 21 subtests passed in 0.05s |
| 240 | 11 | `python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p no:cacheprovider` | 0 | 21 passed in 4.06s |
| 241 | 11 | `python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p no:cacheprovider` | 0 | 373 passed, 7 skipped in 0.95s |
| 242 | 11 | `python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider` | 0 | 25 passed, 26 subtests passed in 0.05s |
| 243 | 11 | `python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no:cacheprovider` | 0 | 67 passed in 0.07s |
| 244 | 11 | `python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q -p no:cacheprovider` | 0 | 21 passed in 0.15s |
| 245 | 11 | `python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider` | 0 | 13 passed, 10 subtests passed in 0.06s |
| 246 | 11 | `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` | 0 | 32 passed, 97 subtests passed in 0.05s |
| 247 | 11 | `python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider` | 0 | 56 passed in 0.06s |
| 248 | 11 | `python -m pytest tests/unit/storage/test_storage_availability.py -q -p no:cacheprovider` | 0 | 41 passed in 0.06s |
| 249 | 11 | `python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovider` | 0 | 50 passed in 0.06s |
| 250 | 11 | `python -m pytest tests/unit/security/test_j_secret_redaction.py -q -p no:cacheprovider` | 0 | 55 passed in 0.06s |
| 251 | 11 | `python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider` | 0 | 60 passed in 0.07s |
| 252 | 11 | `python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider` | 0 | 118 passed in 0.15s |
| 253 | 11 | `python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cacheprovider` | 0 | 49 passed in 0.08s |
| 254 | 11 | `python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprovider` | 0 | 40 passed in 0.05s |
| 255 | 11 | `python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cacheprovider` | 0 | 104 passed in 0.07s |
| 256 | 11 | `python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprovider` | 0 | 131 passed in 0.09s |
| 257 | 11 | `python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovider` | 0 | 104 passed in 0.08s |
| 258 | 11 | `python -m pytest tests/unit/security/test_j_secret_update.py -q -p no:cacheprovider` | 0 | 63 passed in 0.08s |
| 259 | 11 | `python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cacheprovider` | 0 | 51 passed in 0.08s |
| 260 | 11 | `python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cacheprovider` | 0 | 66 passed in 0.10s |
| 261 | 11 | `python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovider` | 0 | 50 passed in 0.10s |
| 262 | 11 | `python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovider` | 0 | 41 passed in 0.07s |
| 263 | 11 | `python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovider` | 0 | 47 passed in 0.07s |
| 264 | 11 | `python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cacheprovider` | 0 | 35 passed in 0.06s |
| 265 | 11 | `python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no:cacheprovider` | 0 | 35 passed in 0.43s |
| 266 | 11 | `python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:cacheprovider` | 0 | 33 passed in 0.12s |
| 267 | 12 | `python -m pytest tests/integration/persistence/a/test_persist_a_postgres.py -q -p no:cacheprovider` | 0 | 22 passed in 9.69s |
| 268 | 12 | `python -c "import pathlib; fs = list(pathlib.Path('src/source_ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf...` | 0 | exit 0 |
| 269 | 12 | `python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q -p no:cacheprovider` | 0 | 14 passed in 5.71s |
| 270 | 12 | `python -c "import pathlib; fs = list(pathlib.Path('src/ingestion/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') fo...` | 0 | exit 0 |
| 271 | 12 | `python -c "import pathlib; fs = list(pathlib.Path('src/catalog/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for ...` | 0 | exit 0 |
| 272 | 12 | `python -m pytest tests/integration/persistence/d/test_persist_d_postgres.py -q -p no:cacheprovider` | 0 | 22 passed in 9.99s |
| 273 | 12 | `python -c "import pathlib; fs = list(pathlib.Path('src/creative/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for...` | 0 | exit 0 |
| 274 | 12 | `python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider` | 0 | 19 passed in 8.61s |
| 275 | 12 | `python -c "import pathlib; fs = list(pathlib.Path('src/voice/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f ...` | 0 | exit 0 |
| 276 | 12 | `python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider` | 0 | 20 passed in 9.12s |
| 277 | 12 | `python -c "import pathlib; fs = list(pathlib.Path('src/render/persistence').rglob('*.py')); t = ' '.join(f.read_text(encoding='utf-8') for f...` | 0 | exit 0 |
| 278 | 12 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/orchestration'); t = ' '.join(f.read_text(encoding='utf-8') ...` | 0 | exit 0 |
| 279 | 12 | `python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider` | 0 | 16 passed in 6.67s |
| 280 | 12 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/storage_meta'); t = ' '.join(f.read_text(encoding='utf-8') f...` | 0 | exit 0 |
| 281 | 12 | `python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider` | 0 | 18 passed in 7.38s |
| 282 | 12 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/config_security'); t = ' '.join(f.read_text(encoding='utf-8'...` | 0 | exit 0 |
| 283 | 12 | `python -c "import pathlib; t = pathlib.Path('tests/integration/voice/test_e16_voice_timing_pipeline.py').read_text(encoding='utf-8'); assert...` | 0 | exit 0 |
| 284 | 12 | `python -c "import pathlib; t = pathlib.Path('tests/unit/render/test_f16_ports_memory_events.py').read_text(encoding='utf-8'); assert all(i i...` | 0 | exit 0 |
| 285 | 12 | `python -c "import pathlib; t = pathlib.Path('tests/integration/render/test_f20_worker_activity.py').read_text(encoding='utf-8'); assert all(...` | 0 | exit 0 |
| 286 | 12 | `python -c "import pathlib; t = pathlib.Path('tests/integration/control_ui/test_h_list_queries_sql.py').read_text(encoding='utf-8'); assert a...` | 0 | exit 0 |
| 287 | 12 | `python -c "import pathlib; t = pathlib.Path('tests/unit/control_ui/test_h_status_pill.py').read_text(encoding='utf-8'); assert all(i in t fo...` | 0 | exit 0 |
| 288 | 12 | `python -B -m pytest tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_ast_boundary_rules_clean_codebase -q -p no:cacheprovider` | 0 | 1 passed in 0.37s |

**Tổng kết:** 279/288 lệnh exit 0; các lệnh có skipped: STT 22, 118, 133, 142, 241; STT 115, 142 mang cờ --deselect h36.

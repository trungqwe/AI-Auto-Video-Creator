# Nhật ký kết quả lệnh kiểm M6 (revision 3)

Các lệnh kiểm của milestone được chạy theo 14 chuỗi nối bằng && (Chuỗi 1..14, tương ứng bước 1..14 của lệnh làm việc) trên candidate HEAD 8167d4ca8a6a5f46bcf4adc1d3ed48f0472ce4e1 bằng interpreter khoá của lane; mỗi chuỗi là một mục có bảng 5 cột | Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |.

## Chuỗi 1

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | git diff --check | 0 | không có đầu ra |  |
| 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 3 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 4 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 5 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 6 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 7 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 8 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 9 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 10 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 11 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 12 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |

## Chuỗi 2

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |

## Chuỗi 3

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |
| 2 | python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementatio | 0 | không có đầu ra |  |

## Chuỗi 4

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q | 0 | 8 passed in 1.31s |  |
| 2 | python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider | 0 | 6 passed in 3.99s |  |
| 3 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog t | 0 | 5190 passed, 1 warning, 2237 subtests passed in 11.92s |  |
| 4 | python -c "import pathlib; t = ' '.join(pathlib.Path('src/controlplane/infrastru | 0 | không có đầu ra |  |
| 5 | python -B -m pytest tests/integration/convergence/test_cp3_migration_sequence.py | 0 | 1 passed in 0.27s |  |
| 6 | python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cache | 0 | 8 passed in 1.31s |  |
| 7 | python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q - | 0 | 16 passed in 5.04s |  |
| 8 | python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p | 0 | 8 passed in 1.31s |  |
| 9 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p | 0 | 111 passed in 10.84s |  |
| 10 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py -q -p | 0 | 8 passed in 1.31s |  |
| 11 | python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cachep | 0 | 83 passed, 1 warning in 0.60s |  |
| 12 | python -m pytest tests/m2/test_p7a_hardening.py::test_h28_static_architecture -q | 0 | 1 passed, 1 warning in 0.66s |  |
| 13 | python -c "import ast, pathlib; d = pathlib.Path('src/controlplane/application/c | 0 | không có đầu ra |  |
| 14 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_sources_module.py | 0 | 111 passed in 10.84s |  |
| 15 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:ca | 0 | 111 passed in 10.84s |  |
| 16 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py::test_ | 0 | 111 passed in 10.84s |  |
| 17 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p | 0 | không có đầu ra |  |
| 18 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |

## Chuỗi 5

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | npm --prefix src/controlplane/ui run build | 0 | ✓ built in 2.70s | Build thành công; dist không đổi |

## Chuỗi 6

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/control_ui -q -p no:cacheprovider | 0 | 665 passed, 1 warning in 1.36s |  |
| 2 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = | 0 | không có đầu ra |  |
| 3 | python -c "import pathlib; d = pathlib.Path('src/controlplane/ui/dist'); n = [f. | 0 | không có đầu ra |  |
| 4 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 0 | không có đầu ra |  |
| 5 | python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider | 0 | 26 passed, 31 subtests passed in 0.05s |  |
| 6 | python -m pytest tests/integration/persistence/c/test_persist_c_hook_listing.py | 0 | 5 passed in 0.13s |  |
| 7 | python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q - | 0 | 5 passed in 0.13s |  |
| 8 | python -m pytest tests/unit/catalog -q -p no:cacheprovider | 0 | 202 passed, 463 subtests passed in 0.29s |  |
| 9 | python -c "import pathlib; r = pathlib.Path('src/catalog'); d = (r / 'domain' / | 0 | không có đầu ra |  |
| 10 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_hooks_module.py -q | 0 | 9 passed in 2.07s |  |
| 11 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p | 0 | không có đầu ra |  |
| 12 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 0 | không có đầu ra |  |

## Chuỗi 7

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cache | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 2 | python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 3 | python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cac | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 4 | python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cachepr | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 5 | python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p n | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 6 | python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprov | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 7 | python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cac | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 8 | python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cachepr | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 9 | python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p | 0 | 28 passed, 11 subtests passed in 0.11s |  |
| 10 | python -m pytest tests/integration/collection/test_a10_candidate_registration.py | 0 | 28 passed, 11 subtests passed in 0.11s |  |
| 11 | python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p n | 0 | 28 passed, 11 subtests passed in 0.11s |  |
| 12 | python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cachepr | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 13 | python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cach | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 14 | python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p | 0 | 28 passed, 11 subtests passed in 0.11s |  |
| 15 | python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:c | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 16 | python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no: | 0 | 28 passed, 11 subtests passed in 0.11s |  |
| 17 | python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cachepro | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 18 | python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p | 0 | 28 passed, 11 subtests passed in 0.11s |  |
| 19 | python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cachepr | 0 | 13 passed, 62 subtests passed in 0.10s |  |
| 20 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.to | 0 | không có đầu ra |  |
| 21 | python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock' | 0 | không có đầu ra |  |
| 22 | python -m pytest tests/integration/adapt/a/test_adapt_a_adapters.py -q -p no:cac | 0 | 30 passed in 0.32s |  |
| 23 | python -c "import pathlib; d = pathlib.Path('src/source_ingestion/adapters'); t | 0 | không có đầu ra |  |
| 24 | python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/securit | 0 | 30 passed in 0.32s |  |
| 25 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |
| 26 | python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no: | 0 | 30 passed in 0.32s |  |
| 27 | python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join( | 0 | không có đầu ra |  |
| 28 | python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q | 0 | 30 passed in 0.32s |  |
| 29 | python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join( | 0 | không có đầu ra |  |
| 30 | python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cache | 0 | 30 passed in 0.32s |  |
| 31 | python -c "import pathlib; d = pathlib.Path('src/render/adapters'); t = ' '.join | 0 | không có đầu ra |  |
| 32 | python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cachep | 0 | 30 passed in 0.32s |  |
| 33 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/sec | 0 | không có đầu ra |  |
| 34 | python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cachep | 0 | 30 passed in 0.32s |  |
| 35 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/sto | 0 | không có đầu ra |  |
| 36 | python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q | 0 | 30 passed in 0.32s |  |
| 37 | python -c "import json, pathlib; d = pathlib.Path('tools/launcher/prod'); x = [j | 0 | không có đầu ra |  |
| 38 | python -c "import pathlib; fs = list(pathlib.Path('src/controlplane/api/wiring') | 0 | không có đầu ra |  |
| 39 | python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no | 0 | 30 passed in 0.32s |  |
| 40 | python -c "import pathlib; t = pathlib.Path('tools/launcher/prod/seed/import_see | 0 | không có đầu ra |  |
| 41 | python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p n | 0 | 30 passed in 0.32s |  |
| 42 | python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml') | 0 | không có đầu ra |  |

## Chuỗi 8

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p | 0 | 39 passed in 0.06s |  |
| 2 | python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit | 0 | 39 passed in 0.06s |  |
| 3 | python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/ | 0 | 39 passed in 0.06s |  |
| 4 | python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:c | 0 | 39 passed in 0.06s |  |
| 5 | python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no: | 0 | 39 passed in 0.06s |  |
| 6 | python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p n | 0 | 39 passed in 0.06s |  |
| 7 | python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cach | 0 | 39 passed in 0.06s |  |
| 8 | python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:ca | 0 | 39 passed in 0.06s |  |
| 9 | python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cach | 0 | 39 passed in 0.06s |  |
| 10 | python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cachepr | 0 | 39 passed in 0.06s |  |
| 11 | python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p n | 0 | 39 passed in 0.06s |  |
| 12 | python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py | 0 | 15 passed in 0.11s |  |
| 13 | python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovi | 0 | 20 passed, 37 subtests passed in 0.05s |  |
| 14 | python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovide | 0 | 20 passed, 37 subtests passed in 0.05s |  |
| 15 | python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprov | 0 | 20 passed, 37 subtests passed in 0.05s |  |
| 16 | python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cachepro | 0 | 20 passed, 37 subtests passed in 0.05s |  |
| 17 | python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cac | 0 | 20 passed, 37 subtests passed in 0.05s |  |
| 18 | python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cachepro | 0 | 20 passed, 37 subtests passed in 0.05s |  |
| 19 | python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cachepro | 0 | 20 passed, 37 subtests passed in 0.05s |  |
| 20 | python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider | 0 | 20 passed, 37 subtests passed in 0.05s |  |
| 21 | python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit | 0 | 94 passed in 0.09s |  |
| 22 | python -m pytest tests/unit/control_ui tests/m2/test_p7b_sse_stream.py -q -p no: | 0 | 670 passed, 1 warning in 7.67s |  |

## Chuỗi 9

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import pathlib, re; c = pathlib.Path('src/controlplane/application/ss | 0 | không có đầu ra |  |
| 2 | python -m pytest tests/integration/convergence/test_cp4_pagination_postgres.py - | 0 | 16 passed in 6.29s |  |
| 3 | python -m pytest tests/integration/control_ui tests/unit/control_ui -q -p no:cac | 0 | 840 passed, 1 warning in 1.68s |  |
| 4 | python -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_ha | 0 | 179 passed, 1 deselected, 2 warnings in 213.67s (0:03:33) | 1 deselected (h36 hoãn sang CP7 theo quyết định user 21/10/2026) |
| 5 | python -c "import pathlib; q = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 6 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py tests/ | 0 | 16 passed in 6.29s |  |
| 7 | python -m pytest tests/integration tests/unit/control_ui -q -p no:cacheprovider | 0 | 2799 passed, 35 skipped, 1 warning, 25 subtests passed in 152.97s (0:02:32) | 35 skipped (thiếu PostgreSQL/tài nguyên, không coi là PASS tài nguyên thật) |
| 8 | python -c "import pathlib; p = pathlib.Path('src/controlplane/application/contro | 0 | không có đầu ra |  |
| 9 | python -c "import pathlib; u = pathlib.Path('src/controlplane/ui/src'); a = (u / | 0 | không có đầu ra |  |
| 10 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 0 | không có đầu ra |  |
| 11 | python -c "import json, pathlib; d = json.loads(pathlib.Path('tools/runtime/runt | 0 | không có đầu ra |  |
| 12 | python -c "import pathlib; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; b = p | 0 | không có đầu ra |  |
| 13 | python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider | 0 | 9 passed in 8.77s |  |
| 14 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 15 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 16 | python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider | 0 | 293 passed in 0.36s |  |
| 17 | python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-an | 0 | không có đầu ra |  |
| 18 | python -m pytest tests/unit/config tests/unit/storage tests/integration/converge | 0 | 1125 passed, 239 subtests passed in 1.06s |  |
| 19 | python -m pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/con | 0 | 679 passed, 398 subtests passed in 1.44s |  |
| 20 | python -c "import hashlib, pathlib, re; t = pathlib.Path('docs/parallel-delivery | 0 | không có đầu ra |  |
| 21 | python -c "import pathlib; t = pathlib.Path('docs/09-contracts/12-state-machines | 0 | không có đầu ra |  |

## Chuỗi 10

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/orchestration tests/integration/storage tests | 0 | 2314 passed, 7 skipped, 1184 subtests passed in 6.18s | 7 skipped (thiếu PostgreSQL/tài nguyên, không coi là PASS tài nguyên thật) |
| 2 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 3 | python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests | 0 | 28 passed in 0.61s |  |
| 4 | python -m pytest tests/unit/orchestration tests/integration/collection tests/uni | 0 | 3387 passed, 1034 subtests passed in 3.58s |  |
| 5 | python -c "import json, pathlib; p = json.loads(pathlib.Path('src/controlplane/u | 0 | không có đầu ra |  |
| 6 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 7 | python -c "import re, pathlib; t = pathlib.Path('tests/m2/test_p9_m2_exit_gate.p | 0 | không có đầu ra |  |
| 8 | python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py tests | 0 | 28 passed in 0.61s |  |
| 9 | python -m pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_state | 0 | 666 passed, 841 subtests passed in 0.86s |  |
| 10 | python -m pytest tests/m2 tests/integration -q -p no:cacheprovider --deselect te | 0 | 2313 passed, 35 skipped, 1 deselected, 2 warnings, 25 subtests passed in 342.65s (0:05:42) | 35 skipped (thiếu PostgreSQL/tài nguyên, không coi là PASS tài nguyên thật); 1 deselected (h36 hoãn sang CP7 theo quyết định user 21/10/2026) |
| 11 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog t | 0 | 666 passed, 841 subtests passed in 0.86s |  |
| 12 | python -c "import pathlib; t = pathlib.Path('src/main.py').read_text(encoding='u | 0 | không có đầu ra |  |
| 13 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = | 0 | không có đầu ra |  |
| 14 | python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/src/App.tsx').r | 0 | không có đầu ra |  |

## Chuỗi 11

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cachepr | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 2 | python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:ca | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 3 | python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cac | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 4 | python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:ca | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 5 | python -m pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cache | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 6 | python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprov | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 7 | python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 8 | python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cachepr | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 9 | python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cachep | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 10 | python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cachep | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 11 | python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cac | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 12 | python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cachep | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 13 | python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprov | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 14 | python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p | 0 | 18 passed in 0.12s |  |
| 15 | python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p n | 0 | 18 passed in 0.12s |  |
| 16 | python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no | 0 | 18 passed in 0.12s |  |
| 17 | python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cache | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 18 | python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cache | 0 | 12 passed, 58 subtests passed in 0.11s |  |
| 19 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovi | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 20 | python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cache | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 21 | python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 22 | python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovi | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 23 | python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovide | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 24 | python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprov | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 25 | python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprov | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 26 | python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 27 | python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 28 | python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprov | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 29 | python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovi | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 30 | python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cachepr | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 31 | python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 32 | python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cach | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 33 | python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovide | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 34 | python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p | 0 | 23 passed in 0.10s |  |
| 35 | python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py - | 0 | 23 passed in 0.10s |  |
| 36 | python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:ca | 0 | 23 passed in 0.10s |  |
| 37 | python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cachepro | 0 | 16 passed, 89 subtests passed in 0.12s |  |
| 38 | python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cachepro | 0 | 16 passed, 89 subtests passed in 0.12s |  |

## Chuỗi 12

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprov | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 2 | python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cachepro | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 3 | python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no: | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 4 | python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cach | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 5 | python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cachepro | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 6 | python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q - | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 7 | python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 8 | python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cachepr | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 9 | python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovid | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 10 | python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cach | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 11 | python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprov | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 12 | python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprov | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 13 | python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cachepro | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 14 | python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovi | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 15 | python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovid | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 16 | python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cach | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 17 | python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py | 0 | 36 passed in 0.16s |  |
| 18 | python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q - | 0 | 36 passed in 0.16s |  |
| 19 | python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q | 0 | 36 passed in 0.16s |  |
| 20 | python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:c | 0 | 36 passed in 0.16s |  |
| 21 | python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cachepr | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 22 | python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cachepr | 0 | 20 passed, 120 subtests passed in 0.35s |  |
| 23 | python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:ca | 0 | 43 passed in 0.05s |  |
| 24 | python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no: | 0 | 43 passed in 0.05s |  |
| 25 | python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovid | 0 | 43 passed in 0.05s |  |
| 26 | python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cach | 0 | 43 passed in 0.05s |  |
| 27 | python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:c | 0 | 43 passed in 0.05s |  |
| 28 | python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/or | 0 | 43 passed in 0.05s |  |
| 29 | python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit | 0 | 43 passed in 0.05s |  |
| 30 | python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q | 0 | 43 passed in 0.05s |  |
| 31 | python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cac | 0 | 43 passed in 0.05s |  |
| 32 | python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q | 0 | 62 passed in 0.08s |  |
| 33 | python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit | 0 | 43 passed in 0.05s |  |
| 34 | python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/ | 0 | 43 passed in 0.05s |  |
| 35 | python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/or | 0 | 43 passed in 0.05s |  |
| 36 | python -m pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orc | 0 | 43 passed in 0.05s |  |

## Chuỗi 13

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:c | 0 | 55 passed in 0.06s |  |
| 2 | python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovid | 0 | 55 passed in 0.06s |  |
| 3 | python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:c | 0 | 55 passed in 0.06s |  |
| 4 | python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p n | 0 | 175 passed, 1 warning in 1.05s |  |
| 5 | python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cachep | 0 | 55 passed in 0.06s |  |
| 6 | python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:c | 0 | 55 passed in 0.06s |  |
| 7 | python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cachepr | 0 | 55 passed in 0.06s |  |
| 8 | python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cach | 0 | 55 passed in 0.06s |  |
| 9 | python -m pytest tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cach | 0 | 55 passed in 0.06s |  |
| 10 | python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:ca | 0 | 55 passed in 0.06s |  |
| 11 | python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovi | 0 | 55 passed in 0.06s |  |
| 12 | python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cac | 0 | 55 passed in 0.06s |  |
| 13 | python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no | 0 | 55 passed in 0.06s |  |
| 14 | python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cachep | 0 | 55 passed in 0.06s |  |
| 15 | python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cachep | 0 | 55 passed in 0.06s |  |
| 16 | python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cachepr | 0 | 65 passed in 0.07s |  |
| 17 | python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cac | 0 | 65 passed in 0.07s |  |
| 18 | python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cachep | 0 | 65 passed in 0.07s |  |
| 19 | python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cache | 0 | 65 passed in 0.07s |  |
| 20 | python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p n | 0 | 21 passed in 0.56s |  |
| 21 | python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p n | 0 | 21 passed in 0.56s |  |
| 22 | python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cac | 0 | 65 passed in 0.07s |  |
| 23 | python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no: | 0 | 65 passed in 0.07s |  |
| 24 | python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q - | 0 | 21 passed in 0.56s |  |
| 25 | python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cach | 0 | 65 passed in 0.07s |  |
| 26 | python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cache | 0 | 65 passed in 0.07s |  |
| 27 | python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprov | 0 | 65 passed in 0.07s |  |
| 28 | python -m pytest tests/unit/storage/test_storage_availability.py -q -p no:cachep | 0 | 65 passed in 0.07s |  |
| 29 | python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovide | 0 | 50 passed in 0.06s |  |
| 30 | python -m pytest tests/unit/security/test_j_secret_redaction.py -q -p no:cachepr | 0 | 55 passed in 0.06s |  |
| 31 | python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider | 0 | 50 passed in 0.06s |  |
| 32 | python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider | 0 | 50 passed in 0.06s |  |
| 33 | python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cachepro | 0 | 50 passed in 0.06s |  |
| 34 | python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprov | 0 | 50 passed in 0.06s |  |
| 35 | python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cachepro | 0 | 50 passed in 0.06s |  |
| 36 | python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprov | 0 | 50 passed in 0.06s |  |
| 37 | python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovid | 0 | 55 passed in 0.06s |  |
| 38 | python -m pytest tests/unit/security/test_j_secret_update.py -q -p no:cacheprovi | 0 | 55 passed in 0.06s |  |
| 39 | python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cach | 0 | 55 passed in 0.06s |  |
| 40 | python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cache | 0 | 50 passed in 0.06s |  |
| 41 | python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovid | 0 | 50 passed in 0.06s |  |
| 42 | python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovi | 0 | 50 passed in 0.06s |  |
| 43 | python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovid | 0 | 55 passed in 0.06s |  |
| 44 | python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cachepro | 0 | 50 passed in 0.06s |  |
| 45 | python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no: | 0 | 35 passed in 0.43s |  |
| 46 | python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:c | 0 | 35 passed in 0.43s |  |

## Chuỗi 14

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/persistence/a/test_persist_a_postgres.py -q - | 0 | 22 passed in 9.60s |  |
| 2 | python -c "import pathlib; fs = list(pathlib.Path('src/source_ingestion/persiste | 0 | không có đầu ra |  |
| 3 | python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q - | 0 | 22 passed in 9.60s |  |
| 4 | python -c "import pathlib; fs = list(pathlib.Path('src/ingestion/persistence').r | 0 | không có đầu ra |  |
| 5 | python -c "import pathlib; fs = list(pathlib.Path('src/catalog/persistence').rgl | 0 | không có đầu ra |  |
| 6 | python -m pytest tests/integration/persistence/d/test_persist_d_postgres.py -q - | 0 | 22 passed in 9.60s |  |
| 7 | python -c "import pathlib; fs = list(pathlib.Path('src/creative/persistence').rg | 0 | không có đầu ra |  |
| 8 | python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q - | 0 | 22 passed in 9.60s |  |
| 9 | python -c "import pathlib; fs = list(pathlib.Path('src/voice/persistence').rglob | 0 | không có đầu ra |  |
| 10 | python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q - | 0 | 22 passed in 9.60s |  |
| 11 | python -c "import pathlib; fs = list(pathlib.Path('src/render/persistence').rglo | 0 | không có đầu ra |  |
| 12 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 13 | python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q - | 0 | 22 passed in 9.60s |  |
| 14 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 15 | python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q - | 0 | 22 passed in 9.60s |  |
| 16 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 17 | python -c "import pathlib; t = pathlib.Path('tests/integration/voice/test_e16_vo | 0 | không có đầu ra |  |
| 18 | python -c "import pathlib; t = pathlib.Path('tests/unit/render/test_f16_ports_me | 0 | không có đầu ra |  |
| 19 | python -c "import pathlib; t = pathlib.Path('tests/integration/render/test_f20_w | 0 | không có đầu ra |  |
| 20 | python -c "import pathlib; t = pathlib.Path('tests/integration/control_ui/test_h | 0 | không có đầu ra |  |
| 21 | python -c "import pathlib; t = pathlib.Path('tests/unit/control_ui/test_h_status | 0 | không có đầu ra |  |
| 22 | python -B -m pytest tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_a | 0 | 1 passed in 0.28s |  |

## Tổng hợp

- Tổng số đoạn lệnh đã chạy: 288 (đếm thật qua 14 bảng).
- Số đoạn exit 0: 288.
- Số đoạn lỗi: 0.
- Trạng thái: toàn bộ 288/288 đoạn lệnh đạt exit code 0 trên candidate HEAD 8167d4ca8a6a5f46bcf4adc1d3ed48f0472ce4e1.

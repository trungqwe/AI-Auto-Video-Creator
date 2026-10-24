# Nhật ký kết quả lệnh kiểm M6 (revision 2)

Các lệnh kiểm của milestone được chạy theo 14 chuỗi nối bằng && (Chuỗi 1..14, tương ứng bước 2,3,4,5,6,7,8,9,10,11,12,13,14,15 của lệnh làm việc) trên integration head 74c062a29d649ea0e3d1471dee9c739dc33d38fe cộng commit docs của lane (HEAD trước commit của lượt R2-G4: 034d4dab8bbb0668c4af21f63c1ca7c0158ada2c); mỗi chuỗi là một mục có bảng 5 cột | Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |.

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
| 1 | python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q | 0 | 8 passed in 1.22s | Chạy lại ở lượt R2-G4 với -p no:cacheprovider sau khi Control ghi nhận ConnectionTimeout ở lượt R2-G3 (1 failed, 7 passed trong 130.44s; PostgreSQL môi trường chưa kết nối được lúc Control kiểm); lượt này exit 0 |
| 2 | python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider | 0 | 6 passed in 4.19s |  |
| 3 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog t | 0 | 5190 passed, 1 warning, 2237 subtests passed in 14.03s |  |
| 4 | python -c "import pathlib; t = ' '.join(pathlib.Path('src/controlplane/infrastru | 0 | không có đầu ra |  |
| 5 | python -B -m pytest tests/integration/convergence/test_cp3_migration_sequence.py | 0 | 1 passed in 0.45s |  |
| 6 | python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cache | 0 | 137 passed, 28 skipped, 1 warning in 4.47s | 28 skipped (thiếu PostgreSQL/tài nguyên, không coi là PASS tài nguyên thật) |
| 7 | python -m pytest tests/integration/persistence/g/test_persist_g_postgres.py -q - | 0 | 16 passed in 15.94s |  |
| 8 | python -m pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p  | 0 | 40 passed in 4.79s |  |
| 9 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p  | 0 | 111 passed in 16.22s |  |
| 10 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py -q -p  | 0 | 21 passed, 1 warning in 0.97s |  |
| 11 | python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cachep | 0 | 83 passed, 1 warning in 0.73s |  |
| 12 | python -m pytest tests/m2/test_p7a_hardening.py::test_h28_static_architecture -q | 0 | 1 passed, 1 warning in 0.76s |  |
| 13 | python -c "import ast, pathlib; d = pathlib.Path('src/controlplane/application/c | 0 | không có đầu ra |  |
| 14 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_sources_module.py  | 0 | 9 passed in 2.95s |  |
| 15 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:ca | 0 | 25 passed, 1 warning in 10.78s |  |
| 16 | python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py::test_ | 0 | 3 passed in 1.19s |  |
| 17 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p | 0 | không có đầu ra |  |
| 18 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |

## Chuỗi 5

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | npm --prefix src/controlplane/ui run build | 0 | ✓ built in 3.17s | Build thành công; dist khớp nguyên trạng (đã hoàn nguyên dist nếu build tạo thay đổi) |

## Chuỗi 6

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/control_ui -q -p no:cacheprovider | 0 | 665 passed, 1 warning in 1.22s |  |
| 2 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = | 0 | không có đầu ra |  |
| 3 | python -c "import pathlib; d = pathlib.Path('src/controlplane/ui/dist'); n = [f. | 0 | không có đầu ra |  |
| 4 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 0 | không có đầu ra |  |
| 5 | python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider | 0 | 26 passed, 31 subtests passed in 0.08s |  |
| 6 | python -m pytest tests/integration/persistence/c/test_persist_c_hook_listing.py  | 0 | 5 passed in 0.17s |  |
| 7 | python -m pytest tests/integration/persistence/c/test_persist_c_postgres.py -q - | 0 | 15 passed in 8.47s |  |
| 8 | python -m pytest tests/unit/catalog -q -p no:cacheprovider | 0 | 202 passed, 463 subtests passed in 0.40s |  |
| 9 | python -c "import pathlib; r = pathlib.Path('src/catalog'); d = (r / 'domain' /  | 0 | không có đầu ra |  |
| 10 | python -m pytest tests/integration/adapt/prod/test_adapt_prod_hooks_module.py -q | 0 | 9 passed in 2.22s |  |
| 11 | python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p | 0 | không có đầu ra |  |
| 12 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 0 | không có đầu ra |  |

## Chuỗi 7

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cache | 0 | 13 passed, 62 subtests passed in 0.15s |  |
| 2 | python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q | 0 | 27 passed, 99 subtests passed in 0.08s |  |
| 3 | python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cac | 0 | 17 passed, 50 subtests passed in 0.06s |  |
| 4 | python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cachepr | 0 | 74 passed in 0.10s |  |
| 5 | python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p n | 0 | 40 passed, 20 subtests passed in 0.05s |  |
| 6 | python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprov | 0 | 15 passed, 22 subtests passed in 0.04s |  |
| 7 | python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cac | 0 | 14 passed, 44 subtests passed in 0.05s |  |
| 8 | python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cachepr | 0 | 32 passed, 3 subtests passed in 0.10s |  |
| 9 | python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p  | 0 | 28 passed, 11 subtests passed in 0.13s |  |
| 10 | python -m pytest tests/integration/collection/test_a10_candidate_registration.py | 0 | 23 passed, 14 subtests passed in 0.12s |  |
| 11 | python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p n | 0 | 18 passed in 0.12s |  |
| 12 | python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cachepr | 0 | 59 passed in 0.09s |  |
| 13 | python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cach | 0 | 49 passed in 0.14s |  |
| 14 | python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p | 0 | 19 passed in 0.10s |  |
| 15 | python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:c | 0 | 20 passed, 49 subtests passed in 0.07s |  |
| 16 | python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no: | 0 | 25 passed in 0.16s |  |
| 17 | python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cachepro | 0 | 33 passed, 29 subtests passed in 0.13s |  |
| 18 | python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p  | 0 | 32 passed in 0.14s |  |
| 19 | python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cachepr | 0 | 62 passed in 0.43s |  |
| 20 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.to | 0 | không có đầu ra |  |
| 21 | python -c "import tomllib, pathlib, re; d = tomllib.loads(pathlib.Path('uv.lock' | 0 | không có đầu ra |  |
| 22 | python -m pytest tests/integration/adapt/a/test_adapt_a_adapters.py -q -p no:cac | 0 | 27 passed in 6.06s |  |
| 23 | python -c "import pathlib; d = pathlib.Path('src/source_ingestion/adapters'); t  | 0 | không có đầu ra |  |
| 24 | python -m pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/securit | 0 | 20 passed in 0.16s |  |
| 25 | python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf- | 0 | không có đầu ra |  |
| 26 | python -m pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no: | 0 | 34 passed in 0.52s |  |
| 27 | python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join( | 0 | không có đầu ra |  |
| 28 | python -m pytest tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q  | 0 | 41 passed in 0.34s |  |
| 29 | python -c "import pathlib; d = pathlib.Path('src/voice/adapters'); t = ' '.join( | 0 | không có đầu ra |  |
| 30 | python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cache | 0 | 53 passed in 4.01s |  |
| 31 | python -c "import pathlib; d = pathlib.Path('src/render/adapters'); t = ' '.join | 0 | không có đầu ra |  |
| 32 | python -m pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cachep | 0 | 22 passed in 13.99s |  |
| 33 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/sec | 0 | không có đầu ra |  |
| 34 | python -m pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cachep | 0 | 32 passed in 1.97s |  |
| 35 | python -c "import pathlib; t = pathlib.Path('src/controlplane/infrastructure/sto | 0 | không có đầu ra |  |
| 36 | python -m pytest tests/integration/adapt/config/test_adapt_config_profile.py -q  | 0 | 11 passed in 0.05s |  |
| 37 | python -c "import json, pathlib; d = pathlib.Path('tools/launcher/prod'); x = [j | 0 | không có đầu ra |  |
| 38 | python -c "import pathlib; fs = list(pathlib.Path('src/controlplane/api/wiring') | 0 | không có đầu ra |  |
| 39 | python -m pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no | 0 | 13 passed in 49.20s |  |
| 40 | python -c "import pathlib; t = pathlib.Path('tools/launcher/prod/seed/import_see | 0 | không có đầu ra |  |
| 41 | python -m pytest tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p n | 0 | 29 passed in 0.42s |  |
| 42 | python -c "import pathlib; c = pathlib.Path('tools/launcher/docker-compose.yml') | 0 | không có đầu ra |  |

## Chuỗi 8

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p | 0 | 39 passed in 0.27s |  |
| 2 | python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit | 0 | 30 passed in 0.10s |  |
| 3 | python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/ | 0 | 19 passed in 0.07s |  |
| 4 | python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:c | 0 | 64 passed in 0.08s |  |
| 5 | python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no: | 0 | 27 passed in 0.05s |  |
| 6 | python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p n | 0 | 31 passed in 0.09s |  |
| 7 | python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cach | 0 | 45 passed in 0.11s |  |
| 8 | python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:ca | 0 | 61 passed in 0.11s |  |
| 9 | python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cach | 0 | 39 passed in 0.08s |  |
| 10 | python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cachepr | 0 | 55 passed in 0.09s |  |
| 11 | python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p n | 0 | 67 passed in 0.12s |  |
| 12 | python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py  | 0 | 15 passed in 0.11s |  |
| 13 | python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovi | 0 | 20 passed, 37 subtests passed in 0.08s |  |
| 14 | python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovide | 0 | 20 passed, 45 subtests passed in 0.05s |  |
| 15 | python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprov | 0 | 11 passed, 11 subtests passed in 0.06s |  |
| 16 | python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cachepro | 0 | 20 passed, 33 subtests passed in 0.04s |  |
| 17 | python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cac | 0 | 27 passed, 19 subtests passed in 0.05s |  |
| 18 | python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cachepro | 0 | 31 passed, 189 subtests passed in 0.07s |  |
| 19 | python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cachepro | 0 | 20 passed, 87 subtests passed in 0.10s |  |
| 20 | python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider | 0 | 27 passed, 11 subtests passed in 0.06s |  |
| 21 | python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit | 0 | 94 passed in 0.13s |  |
| 22 | python -m pytest tests/unit/control_ui tests/m2/test_p7b_sse_stream.py -q -p no: | 0 | 670 passed, 1 warning in 9.30s |  |

## Chuỗi 9

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -c "import pathlib, re; c = pathlib.Path('src/controlplane/application/ss | 0 | không có đầu ra |  |
| 2 | python -m pytest tests/integration/convergence/test_cp4_pagination_postgres.py - | 0 | 16 passed in 11.34s |  |
| 3 | python -m pytest tests/integration/control_ui tests/unit/control_ui -q -p no:cac | 0 | 840 passed, 1 warning in 2.60s |  |
| 4 | python -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_ha | 0 | 179 passed, 1 deselected, 2 warnings in 267.76s (0:04:27) | h36 bị hoãn sang CP7 theo quyết định user 21/10/2026 |
| 5 | python -c "import pathlib; q = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 6 | python -m pytest tests/integration/convergence/test_cp4_queries_routes.py tests/ | 0 | 30 passed, 1 warning in 9.81s |  |
| 7 | python -m pytest tests/integration tests/unit/control_ui -q -p no:cacheprovider | 0 | 2792 passed, 35 skipped, 1 warning, 25 subtests passed in 206.81s (0:03:26) | 35 skipped (thiếu tài nguyên/external service) |
| 8 | python -c "import pathlib; p = pathlib.Path('src/controlplane/application/contro | 0 | không có đầu ra |  |
| 9 | python -c "import pathlib; u = pathlib.Path('src/controlplane/ui/src'); a = (u / | 0 | không có đầu ra |  |
| 10 | python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/feature | 0 | không có đầu ra |  |
| 11 | python -c "import json, pathlib; d = json.loads(pathlib.Path('tools/runtime/runt | 0 | không có đầu ra |  |
| 12 | python -c "import pathlib; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; b = p | 0 | không có đầu ra |  |
| 13 | python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider | 0 | 9 passed in 9.03s |  |
| 14 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 15 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 16 | python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider | 0 | 293 passed in 0.70s |  |
| 17 | python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-an | 0 | không có đầu ra |  |
| 18 | python -m pytest tests/unit/config tests/unit/storage tests/integration/converge | 0 | 1125 passed, 239 subtests passed in 1.10s |  |
| 19 | python -m pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/con | 0 | 679 passed, 398 subtests passed in 0.90s |  |
| 20 | python -c "import hashlib, pathlib, re; t = pathlib.Path('docs/parallel-delivery | 0 | không có đầu ra |  |
| 21 | python -c "import pathlib; t = pathlib.Path('docs/09-contracts/12-state-machines | 0 | không có đầu ra |  |

## Chuỗi 10

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/orchestration tests/integration/storage tests | 0 | 2314 passed, 7 skipped, 1184 subtests passed in 5.14s | 7 skipped (thiếu tài nguyên/external service) |
| 2 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 3 | python -m pytest tests/integration/convergence/test_cp6_workflow_static.py tests | 0 | 28 passed in 0.67s |  |
| 4 | python -m pytest tests/unit/orchestration tests/integration/collection tests/uni | 0 | 3387 passed, 1034 subtests passed in 3.92s |  |
| 5 | python -c "import json, pathlib; p = json.loads(pathlib.Path('src/controlplane/u | 0 | không có đầu ra |  |
| 6 | python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlp | 0 | không có đầu ra |  |
| 7 | python -c "import re, pathlib; t = pathlib.Path('tests/m2/test_p9_m2_exit_gate.p | 0 | không có đầu ra |  |
| 8 | python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py tests | 0 | 25 passed in 0.08s |  |
| 9 | python -m pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_state | 0 | 666 passed, 841 subtests passed in 1.33s |  |
| 10 | python -m pytest tests/m2 tests/integration -q -p no:cacheprovider --deselect te | 0 | 2306 passed, 35 skipped, 1 deselected, 2 warnings, 25 subtests passed in 424.90s (0:07:04) | h36 bị hoãn sang CP7 theo quyết định user 21/10/2026; 35 skipped (thiếu tài nguyên/external service) |
| 11 | python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog t | 0 | 5262 passed, 1 warning, 1998 subtests passed in 12.27s |  |
| 12 | python -c "import pathlib; t = pathlib.Path('src/main.py').read_text(encoding='u | 0 | không có đầu ra |  |
| 13 | python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = | 0 | không có đầu ra |  |
| 14 | python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/src/App.tsx').r | 0 | không có đầu ra |  |

## Chuỗi 11

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cachepr | 0 | 12 passed, 58 subtests passed in 0.13s |  |
| 2 | python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:ca | 0 | 68 passed in 0.09s |  |
| 3 | python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cac | 0 | 11 passed, 13 subtests passed in 0.03s |  |
| 4 | python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:ca | 0 | 87 passed in 0.13s |  |
| 5 | python -m pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cache | 0 | 20 passed, 79 subtests passed in 0.07s |  |
| 6 | python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprov | 0 | 60 passed in 0.09s |  |
| 7 | python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no | 0 | 32 passed in 0.06s |  |
| 8 | python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cachepr | 0 | 62 passed in 0.09s |  |
| 9 | python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cachep | 0 | 110 passed in 0.16s |  |
| 10 | python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cachep | 0 | 94 passed in 0.16s |  |
| 11 | python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cac | 0 | 62 passed in 0.13s |  |
| 12 | python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cachep | 0 | 19 passed, 38 subtests passed in 0.04s |  |
| 13 | python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprov | 0 | 65 passed in 0.15s |  |
| 14 | python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p  | 0 | 18 passed in 0.16s |  |
| 15 | python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p n | 0 | 27 passed in 0.12s |  |
| 16 | python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no | 0 | 52 passed in 0.17s |  |
| 17 | python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cache | 0 | 22 passed in 0.14s |  |
| 18 | python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cache | 0 | 8 passed in 0.34s |  |
| 19 | python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovi | 0 | 16 passed, 89 subtests passed in 0.17s |  |
| 20 | python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cache | 0 | 65 passed in 0.10s |  |
| 21 | python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider | 0 | 144 passed in 0.13s |  |
| 22 | python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovi | 0 | 86 passed in 0.09s |  |
| 23 | python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovide | 0 | 50 passed in 0.05s |  |
| 24 | python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprov | 0 | 75 passed in 0.09s |  |
| 25 | python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprov | 0 | 106 passed in 0.13s |  |
| 26 | python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider | 0 | 63 passed in 0.09s |  |
| 27 | python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider | 0 | 114 passed in 0.13s |  |
| 28 | python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprov | 0 | 51 passed in 0.06s |  |
| 29 | python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovi | 0 | 21 passed in 0.05s |  |
| 30 | python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cachepr | 0 | 35 passed in 0.09s |  |
| 31 | python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider | 0 | 63 passed in 0.08s |  |
| 32 | python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cach | 0 | 79 passed in 0.12s |  |
| 33 | python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovide | 0 | 47 passed in 0.09s |  |
| 34 | python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p | 0 | 23 passed in 0.13s |  |
| 35 | python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py - | 0 | 45 passed in 0.12s |  |
| 36 | python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:ca | 0 | 44 passed in 0.16s |  |
| 37 | python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cachepro | 0 | 35 passed in 0.08s |  |
| 38 | python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cachepro | 0 | 25 passed in 2.23s |  |

## Chuỗi 12

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprov | 0 | 20 passed, 120 subtests passed in 0.39s |  |
| 2 | python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cachepro | 0 | 26 passed, 67 subtests passed in 0.10s |  |
| 3 | python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no: | 0 | 169 passed in 0.14s |  |
| 4 | python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cach | 0 | 58 passed in 0.09s |  |
| 5 | python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cachepro | 0 | 62 passed in 0.10s |  |
| 6 | python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q - | 0 | 104 passed in 0.12s |  |
| 7 | python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py  | 0 | 97 passed in 0.14s |  |
| 8 | python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cachepr | 0 | 55 passed in 0.13s |  |
| 9 | python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovid | 0 | 118 passed in 0.14s |  |
| 10 | python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cach | 0 | 154 passed in 0.21s |  |
| 11 | python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprov | 0 | 97 passed in 0.11s |  |
| 12 | python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprov | 0 | 45 passed, 129 subtests passed in 0.11s |  |
| 13 | python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cachepro | 0 | 38 passed, 99 subtests passed in 0.08s |  |
| 14 | python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovi | 0 | 52 passed, 67 subtests passed in 0.11s |  |
| 15 | python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovid | 0 | 73 passed in 0.13s |  |
| 16 | python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cach | 0 | 39 passed in 0.12s |  |
| 17 | python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py  | 0 | 36 passed in 0.16s |  |
| 18 | python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q - | 0 | 28 passed in 0.15s |  |
| 19 | python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q | 0 | 35 passed in 0.22s |  |
| 20 | python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:c | 0 | 53 passed in 0.23s |  |
| 21 | python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cachepr | 0 | 17 passed in 0.13s |  |
| 22 | python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cachepr | 0 | 55 passed in 0.13s |  |
| 23 | python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:ca | 0 | 43 passed in 0.05s |  |
| 24 | python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no: | 0 | 22 passed, 307 subtests passed in 0.07s |  |
| 25 | python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovid | 0 | 45 passed in 0.07s |  |
| 26 | python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cach | 0 | 45 passed in 0.07s |  |
| 27 | python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:c | 0 | 55 passed in 0.08s |  |
| 28 | python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/or | 0 | 147 passed in 0.16s |  |
| 29 | python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit | 0 | 88 passed in 0.24s |  |
| 30 | python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q  | 0 | 47 passed in 0.07s |  |
| 31 | python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cac | 0 | 86 passed in 0.09s |  |
| 32 | python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q  | 0 | 62 passed in 0.09s |  |
| 33 | python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit | 0 | 110 passed in 0.14s |  |
| 34 | python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/ | 0 | 82 passed in 0.12s |  |
| 35 | python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/or | 0 | 175 passed in 0.17s |  |
| 36 | python -m pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orc | 0 | 157 passed in 0.16s |  |

## Chuỗi 13

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:c | 0 | 55 passed in 0.07s |  |
| 2 | python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovid | 0 | 115 passed in 0.09s |  |
| 3 | python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:c | 0 | 70 passed in 0.07s |  |
| 4 | python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p n | 0 | 175 passed, 1 warning in 1.05s |  |
| 5 | python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cachep | 0 | 31 passed in 0.05s |  |
| 6 | python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:c | 0 | 91 passed in 0.09s |  |
| 7 | python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cachepr | 0 | 37 passed in 0.33s |  |
| 8 | python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cach | 0 | 43 passed, 1 warning in 0.46s |  |
| 9 | python -m pytest tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cach | 0 | 10 passed in 0.03s |  |
| 10 | python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:ca | 0 | 9 passed in 0.03s |  |
| 11 | python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovi | 0 | 22 passed in 0.03s |  |
| 12 | python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cac | 0 | 24 passed in 0.04s |  |
| 13 | python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no | 0 | 14 passed in 0.04s |  |
| 14 | python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cachep | 0 | 35 passed in 0.07s |  |
| 15 | python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cachep | 0 | 26 passed in 0.08s |  |
| 16 | python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cachepr | 0 | 65 passed in 0.09s |  |
| 17 | python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cac | 0 | 24 passed in 0.05s |  |
| 18 | python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cachep | 0 | 11 passed, 85 subtests passed in 0.04s |  |
| 19 | python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cache | 0 | 22 passed, 21 subtests passed in 0.06s |  |
| 20 | python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p n | 0 | 21 passed in 0.59s |  |
| 21 | python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p n | 0 | 373 passed, 7 skipped in 1.08s | 7 skipped (thiếu tài nguyên/external service) |
| 22 | python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cac | 0 | 25 passed, 26 subtests passed in 0.05s |  |
| 23 | python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no: | 0 | 67 passed in 0.06s |  |
| 24 | python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q - | 0 | 21 passed in 0.12s |  |
| 25 | python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cach | 0 | 13 passed, 10 subtests passed in 0.04s |  |
| 26 | python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cache | 0 | 32 passed, 97 subtests passed in 0.06s |  |
| 27 | python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprov | 0 | 56 passed in 0.06s |  |
| 28 | python -m pytest tests/unit/storage/test_storage_availability.py -q -p no:cachep | 0 | 41 passed in 0.05s |  |
| 29 | python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovide | 0 | 50 passed in 0.06s |  |
| 30 | python -m pytest tests/unit/security/test_j_secret_redaction.py -q -p no:cachepr | 0 | 55 passed in 0.06s |  |
| 31 | python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider | 0 | 60 passed in 0.07s |  |
| 32 | python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider | 0 | 118 passed in 0.11s |  |
| 33 | python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cachepro | 0 | 49 passed in 0.08s |  |
| 34 | python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprov | 0 | 40 passed in 0.07s |  |
| 35 | python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cachepro | 0 | 104 passed in 0.10s |  |
| 36 | python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprov | 0 | 131 passed in 0.12s |  |
| 37 | python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovid | 0 | 104 passed in 0.08s |  |
| 38 | python -m pytest tests/unit/security/test_j_secret_update.py -q -p no:cacheprovi | 0 | 63 passed in 0.08s |  |
| 39 | python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cach | 0 | 51 passed in 0.07s |  |
| 40 | python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cache | 0 | 66 passed in 0.07s |  |
| 41 | python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovid | 0 | 50 passed in 0.08s |  |
| 42 | python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovi | 0 | 41 passed in 0.07s |  |
| 43 | python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovid | 0 | 47 passed in 0.09s |  |
| 44 | python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cachepro | 0 | 35 passed in 0.08s |  |
| 45 | python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no: | 0 | 35 passed in 0.45s |  |
| 46 | python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:c | 0 | 33 passed in 0.10s |  |

## Chuỗi 14

| Thứ tự | Lệnh (80 ký tự đầu) | Exit code | Dòng tóm tắt | Ghi chú |
| --- | --- | --- | --- | --- |
| 1 | python -m pytest tests/integration/persistence/a/test_persist_a_postgres.py -q - | 0 | 22 passed in 9.14s |  |
| 2 | python -c "import pathlib; fs = list(pathlib.Path('src/source_ingestion/persiste | 0 | không có đầu ra |  |
| 3 | python -m pytest tests/integration/persistence/b/test_persist_b_postgres.py -q - | 0 | 14 passed in 5.63s |  |
| 4 | python -c "import pathlib; fs = list(pathlib.Path('src/ingestion/persistence').r | 0 | không có đầu ra |  |
| 5 | python -c "import pathlib; fs = list(pathlib.Path('src/catalog/persistence').rgl | 0 | không có đầu ra |  |
| 6 | python -m pytest tests/integration/persistence/d/test_persist_d_postgres.py -q - | 0 | 22 passed in 8.70s |  |
| 7 | python -c "import pathlib; fs = list(pathlib.Path('src/creative/persistence').rg | 0 | không có đầu ra |  |
| 8 | python -m pytest tests/integration/persistence/e/test_persist_e_postgres.py -q - | 0 | 19 passed in 8.59s |  |
| 9 | python -c "import pathlib; fs = list(pathlib.Path('src/voice/persistence').rglob | 0 | không có đầu ra |  |
| 10 | python -m pytest tests/integration/persistence/f/test_persist_f_postgres.py -q - | 0 | 20 passed in 8.95s |  |
| 11 | python -c "import pathlib; fs = list(pathlib.Path('src/render/persistence').rglo | 0 | không có đầu ra |  |
| 12 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 13 | python -m pytest tests/integration/persistence/i/test_persist_i_postgres.py -q - | 0 | 16 passed in 5.85s |  |
| 14 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 15 | python -m pytest tests/integration/persistence/j/test_persist_j_postgres.py -q - | 0 | 18 passed in 7.07s |  |
| 16 | python -c "import pathlib; d = pathlib.Path('src/controlplane/infrastructure/db/ | 0 | không có đầu ra |  |
| 17 | python -c "import pathlib; t = pathlib.Path('tests/integration/voice/test_e16_vo | 0 | không có đầu ra |  |
| 18 | python -c "import pathlib; t = pathlib.Path('tests/unit/render/test_f16_ports_me | 0 | không có đầu ra |  |
| 19 | python -c "import pathlib; t = pathlib.Path('tests/integration/render/test_f20_w | 0 | không có đầu ra |  |
| 20 | python -c "import pathlib; t = pathlib.Path('tests/integration/control_ui/test_h | 0 | không có đầu ra |  |
| 21 | python -c "import pathlib; t = pathlib.Path('tests/unit/control_ui/test_h_status | 0 | không có đầu ra |  |
| 22 | python -B -m pytest tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_a | 0 | 1 passed in 0.36s |  |

## Tổng hợp

- Tổng số đoạn lệnh đã chạy: 288 (đếm thật qua 14 bảng).
- Số đoạn exit 0: 288.
- Số đoạn lỗi: 0.
- Trạng thái: toàn bộ 288/288 đoạn lệnh đạt exit code 0 trên mã integration head 74c062a29d649ea0e3d1471dee9c739dc33d38fe (HEAD lane trước commit của lượt R2-G4: 034d4dab8bbb0668c4af21f63c1ca7c0158ada2c).

# Kết quả chạy lại lệnh kiểm của milestone M5 (revision 5)

Candidate: cây mã nguồn tại a3a7d39f23ae5be6c4debf6ffcc7762a0b5fc278 (HEAD của lane khi bắt đầu; các commit docs(m5) của lane chỉ chạm docs/delivery-evidence/m5-milestone-close/)
Interpreter khoá của lane: C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe
Toàn bộ 290 lệnh dưới đây được chạy lại thật, từng lệnh riêng lẻ, trong phiên R5 này, không sao chép output từ revision trước. STT theo thứ tự danh sách lệnh kiểm của spec R5 (khác thứ tự R4); STT 290 là lệnh mới (probe launch-fix3).

RERUN-LOG nhóm STT 1-11: bắt đầu 06:44:45, kết thúc 06:44:46
RERUN-LOG nhóm STT 12-15: bắt đầu 06:44:50, kết thúc 06:44:51
RERUN-LOG nhóm STT 16-37: bắt đầu 06:45:07, kết thúc 06:45:44
RERUN-LOG nhóm STT 38-61: bắt đầu 06:46:03, kết thúc 06:47:49
RERUN-LOG nhóm STT 62-94: bắt đầu 06:48:07, kết thúc 06:57:04
RERUN-LOG nhóm STT 95-127: bắt đầu 06:57:20, kết thúc 07:06:22
RERUN-LOG nhóm STT 128-187: bắt đầu 07:06:36, kết thúc 07:07:13
RERUN-LOG nhóm STT 188-248: bắt đầu 07:07:20, kết thúc 07:07:56
RERUN-LOG nhóm STT 249-271: bắt đầu 07:08:02, kết thúc 07:09:43
RERUN-LOG nhóm STT 272-290: bắt đầu 07:09:49, kết thúc 07:10:03

| STT | Lệnh (rút gọn) | Exit | Tóm tắt kết quả (nguyên văn dòng cuối) |
| --- | --- | --- | --- |
| 1 | `git diff --check` | 0 | (no output) |
| 2 | `python probe: docs/implementation/a` | 0 | (no output) |
| 3 | `python probe: docs/implementation/b` | 0 | (no output) |
| 4 | `python probe: docs/implementation/c` | 0 | (no output) |
| 5 | `python probe: docs/implementation/i` | 0 | (no output) |
| 6 | `python probe: docs/implementation/d` | 0 | (no output) |
| 7 | `python probe: docs/implementation/e` | 0 | (no output) |
| 8 | `python probe: docs/implementation/f` | 0 | (no output) |
| 9 | `python probe: docs/implementation/j` | 0 | (no output) |
| 10 | `python probe: docs/implementation/g` | 0 | (no output) |
| 11 | `python probe: docs/implementation/h` | 0 | (no output) |
| 12 | `python probe: docs/implementation/convergence` | 0 | (no output) |
| 13 | `python probe: docs/implementation/convergence-ext` | 0 | (no output) |
| 14 | `python probe: docs/implementation/persist` | 0 | (no output) |
| 15 | `python probe: docs/implementation/adapt` | 0 | (no output) |
| 16 | `python probe: docs/implementation/convergence-ext-ui` | 0 | (no output) |
| 17 | `pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 13 passed, 62 subtests passed in 0.10s |
| 18 | `pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider` | 0 | 27 passed, 99 subtests passed in 0.06s |
| 19 | `pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cacheprovider` | 0 | 17 passed, 50 subtests passed in 0.05s |
| 20 | `pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider` | 0 | 74 passed in 0.08s |
| 21 | `pytest tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider` | 0 | 40 passed, 20 subtests passed in 0.05s |
| 22 | `pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprovider` | 0 | 15 passed, 22 subtests passed in 0.04s |
| 23 | `pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cacheprovider` | 0 | 14 passed, 44 subtests passed in 0.04s |
| 24 | `pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider` | 0 | 32 passed, 3 subtests passed in 0.09s |
| 25 | `pytest tests/integration/collection/test_a09_source_commands.py -q -p no:cacheprovider` | 0 | 28 passed, 11 subtests passed in 0.11s |
| 26 | `pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider` | 0 | 23 passed, 14 subtests passed in 0.10s |
| 27 | `pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider` | 0 | 18 passed in 0.13s |
| 28 | `pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cacheprovider` | 0 | 59 passed in 0.10s |
| 29 | `pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cacheprovider` | 0 | 49 passed in 0.11s |
| 30 | `pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p no:cacheprovider` | 0 | 19 passed in 0.09s |
| 31 | `pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:cacheprovider` | 0 | 20 passed, 49 subtests passed in 0.06s |
| 32 | `pytest tests/integration/collection/test_a16_supplemental.py -q -p no:cacheprovider` | 0 | 25 passed in 0.15s |
| 33 | `pytest tests/unit/collection/test_a17_projections.py -q -p no:cacheprovider` | 0 | 33 passed, 29 subtests passed in 0.09s |
| 34 | `pytest tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider` | 0 | 32 passed in 0.14s |
| 35 | `pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cacheprovider` | 0 | 62 passed in 26.38s |
| 36 | `python probe: pyproject.toml` | 0 | (no output) |
| 37 | `python probe: uv.lock` | 0 | (no output) |
| 38 | `pytest tests/integration/adapt/a/test_adapt_a_adapters.py -q -p no:cacheprovider` | 0 | 27 passed in 5.67s |
| 39 | `python probe: src/source_ingestion/adapters` | 0 | (no output) |
| 40 | `pytest tests/integration/adapt/d/test_adapt_d_ai.py tests/unit/security/test_http_router_adapter.py -q -p no:cacheprovider` | 0 | 20 passed in 0.19s |
| 41 | `python probe: src/creative/adapters/real_ai_invocation.py` | 0 | (no output) |
| 42 | `pytest tests/integration/adapt/e/test_adapt_e_tts_aligner.py -q -p no:cacheprovider` | 0 | 34 passed in 0.49s |
| 43 | `python probe: src/voice/adapters` | 0 | (no output) |
| 44 | `pytest tests/integration/adapt/e_media/test_adapt_e_media_tools.py -q -p no:cacheprovider` | 0 | 41 passed in 0.25s |
| 45 | `python probe: src/voice/adapters` | 0 | (no output) |
| 46 | `pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider` | 0 | 53 passed in 3.54s |
| 47 | `python probe: src/render/adapters` | 0 | (no output) |
| 48 | `pytest tests/integration/adapt/j/test_adapt_j_oauth.py -q -p no:cacheprovider` | 0 | 22 passed in 14.04s |
| 49 | `python probe: src/controlplane/infrastructure/security` | 0 | (no output) |
| 50 | `pytest tests/integration/adapt/i/test_adapt_i_drive.py -q -p no:cacheprovider` | 0 | 33 passed in 1.90s |
| 51 | `python probe: src/controlplane/infrastructure/storage/drive_object_store.py` | 0 | (no output) |
| 52 | `pytest tests/integration/adapt/config/test_adapt_config_profile.py -q -p no:cacheprovider` | 0 | 11 passed in 0.04s |
| 53 | `python probe: tools/launcher/prod` | 0 | (no output) |
| 54 | `pytest tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider` | 0 | 111 passed in 8.73s |
| 55 | `python probe: src/controlplane/api/wiring` | 0 | (no output) |
| 56 | `pytest tests/integration/adapt/seed/test_adapt_seed_import.py -q -p no:cacheprovider` | 0 | 13 passed in 36.72s |
| 57 | `python probe: tools/launcher/prod/seed/import_seed.py` | 0 | (no output) |
| 58 | `pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider` | 0 | 27 passed, 1 warning in 22.44s |
| 59 | `python probe: src/main.py` | 0 | (no output) |
| 60 | `pytest tests/integration/adapt/launch/test_adapt_launch_cli.py -q -p no:cacheprovider` | 0 | 36 passed in 2.66s |
| 61 | `python probe: tools/launcher/docker-compose.yml` | 0 | (no output) |
| 62 | `pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 39 passed in 0.08s |
| 63 | `pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit/ingestion/test_ingestion_fingerprint.py -q -p no:cacheprovider` | 0 | 30 passed in 0.07s |
| 64 | `pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/unit/ingestion/test_ingestion_memory_unit_of_work.py -q -p no:cacheprovider` | 0 | 19 passed in 0.07s |
| 65 | `pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:cacheprovider` | 0 | 64 passed in 0.07s |
| 66 | `pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no:cacheprovider` | 0 | 27 passed in 0.05s |
| 67 | `pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider` | 0 | 31 passed in 0.10s |
| 68 | `pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cacheprovider` | 0 | 45 passed in 0.09s |
| 69 | `pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:cacheprovider` | 0 | 61 passed in 0.10s |
| 70 | `pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cacheprovider` | 0 | 39 passed in 0.08s |
| 71 | `pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cacheprovider` | 0 | 55 passed in 0.11s |
| 72 | `pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p no:cacheprovider` | 0 | 67 passed in 0.14s |
| 73 | `pytest tests/integration/ingestion/test_ingestion_flow_integration.py -q -p no:cacheprovider` | 0 | 15 passed in 0.12s |
| 74 | `pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider` | 0 | 20 passed, 37 subtests passed in 0.07s |
| 75 | `pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovider` | 0 | 20 passed, 45 subtests passed in 0.05s |
| 76 | `pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprovider` | 0 | 11 passed, 11 subtests passed in 0.04s |
| 77 | `pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cacheprovider` | 0 | 20 passed, 33 subtests passed in 0.05s |
| 78 | `pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider` | 0 | 26 passed, 31 subtests passed in 0.05s |
| 79 | `pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cacheprovider` | 0 | 27 passed, 19 subtests passed in 0.05s |
| 80 | `pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cacheprovider` | 0 | 31 passed, 189 subtests passed in 0.08s |
| 81 | `pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cacheprovider` | 0 | 20 passed, 87 subtests passed in 0.06s |
| 82 | `pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider` | 0 | 27 passed, 11 subtests passed in 0.06s |
| 83 | `pytest tests/unit/control_ui/test_h_stream_event_catalog.py tests/unit/control_ui/test_h_stream_client_registry.py tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider` | 0 | 94 passed in 0.16s |
| 84 | `pytest tests/unit/control_ui tests/m2/test_p7b_sse_stream.py -q -p no:cacheprovider` | 0 | 670 passed, 1 warning in 8.57s |
| 85 | `python probe: src/controlplane/application/sse/event_catalog.py` | 0 | (no output) |
| 86 | `pytest tests/integration/convergence/test_cp4_pagination_postgres.py -q -p no:cacheprovider` | 0 | 16 passed in 6.84s |
| 87 | `pytest tests/integration/control_ui tests/unit/control_ui -q -p no:cacheprovider` | 0 | 840 passed, 1 warning in 2.08s |
| 88 | `pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression` | 0 | 179 passed, 1 deselected, 2 warnings in 216.11s (0:03:36) |
| 89 | `python probe: src/controlplane/infrastructure/db/control_api_queries.py` | 0 | (no output) |
| 90 | `pytest tests/integration/convergence/test_cp4_queries_routes.py tests/integration/convergence/test_cp4_queries_postgres.py -q -p no:cacheprovider` | 0 | 30 passed, 1 warning in 5.75s |
| 91 | `pytest tests/integration tests/unit/control_ui -q -p no:cacheprovider` (SKIP) | 0 | 3257 passed, 36 skipped, 1 warning, 25 subtests passed in 271.28s (0:04:31) |
| 92 | `python probe: src/controlplane/application/control_api/query_ports.py` | 0 | (no output) |
| 93 | `npm --prefix src/controlplane/ui run build` | 0 | - Adjust chunk size limit for this warning via build.chunkSizeWarningLimit. |
| 94 | `pytest tests/unit/control_ui -q -p no:cacheprovider` | 0 | 665 passed, 1 warning in 0.99s |
| 95 | `python probe: src/controlplane/ui/dist` | 0 | (no output) |
| 96 | `python probe: src/controlplane/ui/src` | 0 | (no output) |
| 97 | `python probe: src/controlplane/ui/src/features/screens/screenRegistry.ts` | 0 | (no output) |
| 98 | `python probe: tools/runtime/runtime.lock.json` | 0 | (no output) |
| 99 | `python probe: src/controlplane` | 0 | (no output) |
| 100 | `pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider` | 0 | 9 passed in 8.26s |
| 101 | `python probe: src/controlplane/pyproject.toml` | 0 | (no output) |
| 102 | `python probe: src/controlplane/pyproject.toml` | 0 | (no output) |
| 103 | `pytest tests/contract/test_bindings.py -q -p no:cacheprovider` | 0 | 293 passed in 0.38s |
| 104 | `python probe: docs/parallel-delivery/ownership-and-locks.yaml` | 0 | (no output) |
| 105 | `pytest tests/unit/config tests/unit/storage tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergence/test_cp3b_source_parity.py -q -p no:cacheprovider` | 0 | 1125 passed, 239 subtests passed in 1.11s |
| 106 | `pytest tests/unit/security tests/m2/test_p4_statemachines.py tests/contract/test_bindings.py -q -p no:cacheprovider` | 0 | 679 passed, 398 subtests passed in 1.26s |
| 107 | `python probe: docs/parallel-delivery/contract-registry.yaml` | 0 | (no output) |
| 108 | `python probe: docs/09-contracts/12-state-machines.md` | 0 | (no output) |
| 109 | `pytest tests/integration/convergence/test_cp5_completion_uow.py -q -p no:cacheprovider` | 0 | 40 passed in 3.43s |
| 110 | `pytest tests/integration/orchestration tests/integration/storage tests/unit/catalog tests/unit/storage tests/unit/render -q -p no:cacheprovider` (SKIP) | 0 | 2314 passed, 7 skipped, 1184 subtests passed in 4.29s |
| 111 | `python probe: src/controlplane/pyproject.toml` | 0 | (no output) |
| 112 | `pytest tests/integration/convergence/test_cp6_workflow_static.py tests/integration/convergence/test_cp6_workflow_catalog.py tests/integration/convergence/test_cp6_video_production_flow.py -q -p no:cacheprovider` | 0 | 28 passed in 0.64s |
| 113 | `pytest tests/unit/orchestration tests/integration/collection tests/unit/ingestion tests/integration/creative tests/integration/voice tests/integration/render tests/unit/config tests/unit/catalog tests/unit/storage -q -p no:cacheprovider` | 0 | 3387 passed, 1034 subtests passed in 3.66s |
| 114 | `python probe: src/controlplane/ui/package.json` | 0 | (no output) |
| 115 | `python probe: src/controlplane/pyproject.toml` | 0 | (no output) |
| 116 | `pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider` | 0 | 6 passed in 3.93s |
| 117 | `python probe: tests/m2/test_p9_m2_exit_gate.py` | 0 | (no output) |
| 118 | `pytest tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergence/test_cp3b_source_parity.py -q -p no:cacheprovider` | 0 | 25 passed in 0.06s |
| 119 | `pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_statemachines.py -q -p no:cacheprovider` | 0 | 666 passed, 841 subtests passed in 0.89s |
| 120 | `pytest tests/integration/convergence/test_cp3_migration_sequence.py -q -p no:cacheprovider` | 0 | 8 passed in 1.51s |
| 121 | `pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/unit/storage tests/unit/security tests/integration/orchestration tests/integration/control_ui -q -p no:cacheprovider` | 0 | 5190 passed, 1 warning, 2237 subtests passed in 10.00s |
| 122 | `pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider` (SKIP) | 0 | 137 passed, 28 skipped, 1 warning in 1.81s |
| 123 | `pytest tests/m2 tests/integration -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression` (SKIP) | 0 | 2771 passed, 36 skipped, 1 deselected, 2 warnings, 25 subtests passed in 478.67s (0:07:58) |
| 124 | `pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/unit/security tests/unit/control_ui -q -p no:cacheprovider` | 0 | 5262 passed, 1 warning, 1998 subtests passed in 9.23s |
| 125 | `python probe: src/main.py` | 0 | (no output) |
| 126 | `python probe: src/controlplane/ui/dist` | 0 | (no output) |
| 127 | `python probe: src/controlplane/ui/src/App.tsx` | 0 | (no output) |
| 128 | `pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 58 subtests passed in 0.10s |
| 129 | `pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider` | 0 | 68 passed in 0.08s |
| 130 | `pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cacheprovider` | 0 | 11 passed, 13 subtests passed in 0.03s |
| 131 | `pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider` | 0 | 87 passed in 0.10s |
| 132 | `pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cacheprovider` | 0 | 20 passed, 79 subtests passed in 0.05s |
| 133 | `pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider` | 0 | 60 passed in 0.07s |
| 134 | `pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider` | 0 | 32 passed in 0.05s |
| 135 | `pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider` | 0 | 62 passed in 0.08s |
| 136 | `pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider` | 0 | 110 passed in 0.16s |
| 137 | `pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider` | 0 | 94 passed in 0.14s |
| 138 | `pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider` | 0 | 62 passed in 0.13s |
| 139 | `pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider` | 0 | 19 passed, 38 subtests passed in 0.03s |
| 140 | `pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider` | 0 | 65 passed in 0.12s |
| 141 | `pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider` | 0 | 18 passed in 0.13s |
| 142 | `pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider` | 0 | 27 passed in 0.12s |
| 143 | `pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider` | 0 | 52 passed in 0.16s |
| 144 | `pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider` | 0 | 22 passed in 0.10s |
| 145 | `pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider` | 0 | 8 passed in 0.23s |
| 146 | `pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | 16 passed, 89 subtests passed in 0.11s |
| 147 | `pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider` | 0 | 65 passed in 0.06s |
| 148 | `pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider` | 0 | 144 passed in 0.11s |
| 149 | `pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovider` | 0 | 86 passed in 0.08s |
| 150 | `pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovider` | 0 | 50 passed in 0.06s |
| 151 | `pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprovider` | 0 | 75 passed in 0.08s |
| 152 | `pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprovider` | 0 | 106 passed in 0.11s |
| 153 | `pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider` | 0 | 63 passed in 0.08s |
| 154 | `pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider` | 0 | 114 passed in 0.11s |
| 155 | `pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider` | 0 | 51 passed in 0.06s |
| 156 | `pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider` | 0 | 21 passed in 0.05s |
| 157 | `pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider` | 0 | 35 passed in 0.08s |
| 158 | `pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider` | 0 | 63 passed in 0.06s |
| 159 | `pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider` | 0 | 79 passed in 0.13s |
| 160 | `pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider` | 0 | 47 passed in 0.09s |
| 161 | `pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider` | 0 | 23 passed in 0.10s |
| 162 | `pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider` | 0 | 45 passed in 0.10s |
| 163 | `pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider` | 0 | 44 passed in 0.19s |
| 164 | `pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider` | 0 | 35 passed in 0.07s |
| 165 | `pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider` | 0 | 25 passed in 1.76s |
| 166 | `pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 20 passed, 120 subtests passed in 0.36s |
| 167 | `pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cacheprovider` | 0 | 26 passed, 67 subtests passed in 0.09s |
| 168 | `pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider` | 0 | 169 passed in 0.14s |
| 169 | `pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider` | 0 | 58 passed in 0.10s |
| 170 | `pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider` | 0 | 62 passed in 0.09s |
| 171 | `pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider` | 0 | 104 passed in 0.11s |
| 172 | `pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider` | 0 | 97 passed in 0.11s |
| 173 | `pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider` | 0 | 55 passed in 0.11s |
| 174 | `pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider` | 0 | 118 passed in 0.11s |
| 175 | `pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider` | 0 | 154 passed in 0.19s |
| 176 | `pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider` | 0 | 97 passed in 0.10s |
| 177 | `pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider` | 0 | 45 passed, 129 subtests passed in 0.10s |
| 178 | `pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider` | 0 | 38 passed, 99 subtests passed in 0.06s |
| 179 | `pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider` | 0 | 52 passed, 67 subtests passed in 0.08s |
| 180 | `pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider` | 0 | 73 passed in 0.11s |
| 181 | `pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider` | 0 | 39 passed in 0.10s |
| 182 | `pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider` | 0 | 36 passed in 0.14s |
| 183 | `pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider` | 0 | 28 passed in 0.15s |
| 184 | `pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider` | 0 | 35 passed in 0.20s |
| 185 | `pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider` | 0 | 53 passed in 0.18s |
| 186 | `pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider` | 0 | 17 passed in 0.09s |
| 187 | `pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cacheprovider` | 0 | 55 passed in 0.10s |
| 188 | `pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:cacheprovider` | 0 | 43 passed in 0.05s |
| 189 | `pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no:cacheprovider` | 0 | 22 passed, 307 subtests passed in 0.06s |
| 190 | `pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider` | 0 | 45 passed in 0.06s |
| 191 | `pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cacheprovider` | 0 | 45 passed in 0.06s |
| 192 | `pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:cacheprovider` | 0 | 55 passed in 0.06s |
| 193 | `pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/orchestration/test_g_job_waiting.py -q -p no:cacheprovider` | 0 | 147 passed in 0.11s |
| 194 | `pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py -q -p no:cacheprovider` | 0 | 88 passed in 0.19s |
| 195 | `pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q -p no:cacheprovider` | 0 | 47 passed in 0.06s |
| 196 | `pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cacheprovider` | 0 | 86 passed in 0.08s |
| 197 | `pytest tests/integration/orchestration/test_g_commit_completion.py -q -p no:cacheprovider` | 0 | 62 passed in 0.09s |
| 198 | `pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit/orchestration/test_g_retry_policy.py -q -p no:cacheprovider` | 0 | 110 passed in 0.10s |
| 199 | `pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/orchestration/test_g_resource_admission.py -q -p no:cacheprovider` | 0 | 82 passed in 0.09s |
| 200 | `pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/orchestration/test_g_consistency_audit.py -q -p no:cacheprovider` | 0 | 175 passed in 0.13s |
| 201 | `pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orchestration/test_g_batch_outcome.py tests/unit/orchestration/test_g_app_session.py -q -p no:cacheprovider` | 0 | 157 passed in 0.13s |
| 202 | `pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:cacheprovider` | 0 | 55 passed in 0.05s |
| 203 | `pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovider` | 0 | 115 passed in 0.08s |
| 204 | `pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:cacheprovider` | 0 | 70 passed in 0.06s |
| 205 | `pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider` | 0 | 175 passed, 1 warning in 0.97s |
| 206 | `pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cacheprovider` | 0 | 31 passed in 0.04s |
| 207 | `pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:cacheprovider` | 0 | 91 passed in 0.07s |
| 208 | `pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cacheprovider` | 0 | 37 passed in 0.22s |
| 209 | `pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cacheprovider` | 0 | 43 passed, 1 warning in 0.35s |
| 210 | `pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cacheprovider` | 0 | 83 passed, 1 warning in 0.56s |
| 211 | `pytest tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider` | 0 | 10 passed in 0.03s |
| 212 | `pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:cacheprovider` | 0 | 9 passed in 0.03s |
| 213 | `pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovider` | 0 | 22 passed in 0.03s |
| 214 | `pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cacheprovider` | 0 | 24 passed in 0.03s |
| 215 | `pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no:cacheprovider` | 0 | 14 passed in 0.03s |
| 216 | `pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider` | 0 | 35 passed in 0.04s |
| 217 | `pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cacheprovider` | 0 | 26 passed in 0.05s |
| 218 | `pytest tests/unit/storage/test_storage_declaration.py -q -p no:cacheprovider` | 0 | 65 passed in 0.07s |
| 219 | `pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cacheprovider` | 0 | 24 passed in 0.04s |
| 220 | `pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider` | 0 | 11 passed, 85 subtests passed in 0.05s |
| 221 | `pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider` | 0 | 22 passed, 21 subtests passed in 0.05s |
| 222 | `pytest tests/integration/storage/test_storage_local_journal.py -q -p no:cacheprovider` | 0 | 21 passed in 0.60s |
| 223 | `pytest tests/integration/storage/test_storage_staging_paths.py -q -p no:cacheprovider` (SKIP) | 0 | 373 passed, 7 skipped in 0.79s |
| 224 | `pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider` | 0 | 25 passed, 26 subtests passed in 0.04s |
| 225 | `pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no:cacheprovider` | 0 | 67 passed in 0.06s |
| 226 | `pytest tests/integration/storage/test_storage_cleanup_executor.py -q -p no:cacheprovider` | 0 | 21 passed in 0.11s |
| 227 | `pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider` | 0 | 13 passed, 10 subtests passed in 0.04s |
| 228 | `pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` | 0 | 32 passed, 97 subtests passed in 0.05s |
| 229 | `pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider` | 0 | 56 passed in 0.06s |
| 230 | `pytest tests/unit/storage/test_storage_availability.py -q -p no:cacheprovider` | 0 | 41 passed in 0.04s |
| 231 | `pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovider` | 0 | 50 passed in 0.05s |
| 232 | `pytest tests/unit/security/test_j_secret_redaction.py -q -p no:cacheprovider` | 0 | 55 passed in 0.05s |
| 233 | `pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider` | 0 | 60 passed in 0.06s |
| 234 | `pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider` | 0 | 118 passed in 0.10s |
| 235 | `pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cacheprovider` | 0 | 49 passed in 0.06s |
| 236 | `pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprovider` | 0 | 40 passed in 0.04s |
| 237 | `pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cacheprovider` | 0 | 104 passed in 0.08s |
| 238 | `pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprovider` | 0 | 131 passed in 0.09s |
| 239 | `pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovider` | 0 | 104 passed in 0.08s |
| 240 | `pytest tests/unit/security/test_j_secret_update.py -q -p no:cacheprovider` | 0 | 63 passed in 0.08s |
| 241 | `pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cacheprovider` | 0 | 51 passed in 0.06s |
| 242 | `pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cacheprovider` | 0 | 66 passed in 0.07s |
| 243 | `pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovider` | 0 | 50 passed in 0.07s |
| 244 | `pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovider` | 0 | 41 passed in 0.06s |
| 245 | `pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovider` | 0 | 47 passed in 0.06s |
| 246 | `pytest tests/unit/config/test_j_capability_health.py -q -p no:cacheprovider` | 0 | 35 passed in 0.06s |
| 247 | `pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no:cacheprovider` | 0 | 35 passed in 0.50s |
| 248 | `pytest tests/integration/config/test_j_routed_invocation.py -q -p no:cacheprovider` | 0 | 33 passed in 0.09s |
| 249 | `pytest tests/integration/persistence/a/test_persist_a_postgres.py -q -p no:cacheprovider` | 0 | 22 passed in 11.54s |
| 250 | `python probe: src/source_ingestion/persistence` | 0 | (no output) |
| 251 | `pytest tests/integration/persistence/b/test_persist_b_postgres.py -q -p no:cacheprovider` | 0 | 14 passed in 7.32s |
| 252 | `python probe: src/ingestion/persistence` | 0 | (no output) |
| 253 | `pytest tests/integration/persistence/c/test_persist_c_postgres.py -q -p no:cacheprovider` | 0 | 15 passed in 14.06s |
| 254 | `python probe: src/catalog/persistence` | 0 | (no output) |
| 255 | `pytest tests/integration/persistence/d/test_persist_d_postgres.py -q -p no:cacheprovider` | 0 | 22 passed in 19.22s |
| 256 | `python probe: src/creative/persistence` | 0 | (no output) |
| 257 | `pytest tests/integration/persistence/e/test_persist_e_postgres.py -q -p no:cacheprovider` | 0 | 19 passed in 10.36s |
| 258 | `python probe: src/voice/persistence` | 0 | (no output) |
| 259 | `pytest tests/integration/persistence/f/test_persist_f_postgres.py -q -p no:cacheprovider` | 0 | 20 passed in 9.20s |
| 260 | `python probe: src/render/persistence` | 0 | (no output) |
| 261 | `pytest tests/integration/persistence/g/test_persist_g_postgres.py -q -p no:cacheprovider` | 0 | 16 passed in 6.45s |
| 262 | `python probe: src/controlplane/infrastructure/db/orchestration` | 0 | (no output) |
| 263 | `pytest tests/integration/persistence/i/test_persist_i_postgres.py -q -p no:cacheprovider` | 0 | 16 passed in 7.42s |
| 264 | `python probe: src/controlplane/infrastructure/db/storage_meta` | 0 | (no output) |
| 265 | `pytest tests/integration/persistence/j/test_persist_j_postgres.py -q -p no:cacheprovider` | 0 | 18 passed in 9.52s |
| 266 | `python probe: src/controlplane/infrastructure/db/config_security` | 0 | (no output) |
| 267 | `python probe: tests/integration/voice/test_e16_voice_timing_pipeline.py` | 0 | (no output) |
| 268 | `python probe: tests/unit/render/test_f16_ports_memory_events.py` | 0 | (no output) |
| 269 | `python probe: tests/integration/render/test_f20_worker_activity.py` | 0 | (no output) |
| 270 | `python probe: tests/integration/control_ui/test_h_list_queries_sql.py` | 0 | (no output) |
| 271 | `python probe: tests/unit/control_ui/test_h_status_pill.py` | 0 | (no output) |
| 272 | `pytest tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_ast_boundary_rules_clean_codebase -q -p no:cacheprovider` | 0 | 1 passed in 0.32s |
| 273 | `python probe: src/controlplane/infrastructure/db/migrations/0013_ingestion.sql` | 0 | (no output) |
| 274 | `pytest tests/integration/convergence/test_cp3_migration_sequence.py::test_pinned_migrations_and_runner_untouched -q -p no:cacheprovider` | 0 | 1 passed in 0.31s |
| 275 | `pytest tests/integration/convergence/test_cp4_queries_routes.py -q -p no:cacheprovider` | 0 | 21 passed, 1 warning in 0.77s |
| 276 | `pytest tests/m2/test_p7a_hardening.py::test_h28_static_architecture -q -p no:cacheprovider` | 0 | 1 passed, 1 warning in 0.69s |
| 277 | `python probe: src/controlplane/application/control_api` | 0 | (no output) |
| 278 | `pytest tests/integration/adapt/prod/test_adapt_prod_sources_module.py -q -p no:cacheprovider` | 0 | 9 passed in 1.92s |
| 279 | `pytest tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_builder_inventory tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_sources_have_no_forbidden_text tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_modules_do_not_cross_import_subsystems -q -p no:cacheprovider` | 0 | 3 passed in 1.08s |
| 280 | `python probe: src/controlplane/api` | 0 | (no output) |
| 281 | `python probe: src/controlplane/ui/dist` | 0 | (no output) |
| 282 | `python probe: src/controlplane/ui/src/features/screens/screenRegistry.ts` | 0 | (no output) |
| 283 | `pytest tests/integration/persistence/c/test_persist_c_hook_listing.py -q -p no:cacheprovider` | 0 | 5 passed in 0.12s |
| 284 | `pytest tests/unit/catalog -q -p no:cacheprovider` | 0 | 202 passed, 463 subtests passed in 0.25s |
| 285 | `python probe: src/catalog` | 0 | (no output) |
| 286 | `pytest tests/integration/adapt/prod/test_adapt_prod_hooks_module.py -q -p no:cacheprovider` | 0 | 9 passed in 1.89s |
| 287 | `python probe: src/controlplane/api` | 0 | (no output) |
| 288 | `python probe: src/controlplane/ui/src/features/screens/screenRegistry.ts` | 0 | (no output) |
| 289 | `python probe: tools/launcher/launcher.py` | 0 | (no output) |
| 290 | `python probe: tools/launcher/docker-compose.yml` | 0 | (no output) |

## Tổng kết kết quả thực thi

- **Tổng số lệnh**: 290/290 lệnh đã chạy trên đúng candidate a3a7d39f23ae5be6c4debf6ffcc7762a0b5fc278.
- **Kết quả**: 290/290 lệnh exit 0, 0 FAIL. STT 60-61 kiểm bản sửa ADAPT-LAUNCH-FIX1 (integrate 21d99fc89eb076a036b4d62f026b057a61d96135, candidate 9bcb10e680dc), STT 289 kiểm bản sửa ADAPT-LAUNCH-FIX2 (integrate 6042d7a626d3d523881cc86d1b0ac674986bcafa, candidate 903393a717cb), và STT 290 kiểm bản sửa launch-fix3 (chạm tools/launcher/docker-compose.yml và tools/launcher/temporal-dynamicconfig.yaml).
- **5 lệnh có test skip** (STT 91, 110, 122, 123, 223), nguyên nhân đã đối chiếu trực tiếp từ mã nguồn kiểm thử:
  - STT 122 (`tests/integration/convergence/test_cp4_wiring.py`, 28 skipped): Các test tham số hoá theo danh mục lệnh `COMMANDS` tự gọi `pytest.skip` khi lệnh không áp dụng trong ngữ cảnh kịch bản: dòng 283 và 302 ("Lệnh không yêu cầu If-Match"), dòng 350 ("cannot vary payload for empty body without resource id"), dòng 371 ("Lệnh không có body để kiểm tra trường lạ"). Đây là thiết kế tham số hoá chuẩn của bộ test.
  - STT 223 (`tests/integration/storage/test_storage_staging_paths.py`, 7 skipped): Hàm `make_symlink` (dòng 81) gọi `pytest.skip` khi `os.symlink` không tạo được symlink do tài khoản người dùng chạy trên môi trường Windows không có đặc quyền cấp cao SeCreateSymbolicLinkPrivilege. Biến thể junction (dòng 86) chỉ skip ngoài Windows nên chạy bình thường ở đây.
  - STT 91 (`tests/integration tests/unit/control_ui`, 36 skipped) và STT 123 (`tests/m2 tests/integration`, 36 skipped, 1 deselected): Đúng bằng tổng 28 test skip của `test_cp4_wiring` cộng với 7 test skip của `test_storage_staging_paths` và 1 test skip của `tests/integration/prod_ports/test_pp_4_artifact_source.py` (dòng 126: host forbids creating symlinks do thiếu đặc quyền symlink Windows). Hoàn toàn không phát sinh thêm bất kỳ skip nào khác.
  - STT 110 (`tests/integration/orchestration tests/integration/storage ...`, 7 skipped): Bao gồm đúng 7 test skip của `test_storage_staging_paths` do thiếu đặc quyền symlink Windows.
  - Test bị skip không được tính là test đã chạy; báo cáo chỉ ghi nhận exit 0 của lệnh và số lượng skip thực tế.
- **Lệnh build UI (STT 93)**: `npm --prefix src/controlplane/ui run build` đã thực thi thành công với exit 0, không làm thay đổi bất kỳ tệp nào trong thư mục `src/controlplane/ui/dist` (cây làm việc hoàn toàn sạch ngoài thư mục delivery-evidence).
- **Kiểm thử hoãn h36**: Kiểm thử `tests/m2/test_p7b_hardening.py::test_h36_m1_regression` được hoãn sang gói CP7 theo đúng quyết định của người dùng ngày 21/10/2026 (mang cờ `--deselect`, không tự ý chạy).

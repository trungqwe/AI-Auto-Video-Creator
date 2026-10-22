# Kết quả chạy lại lệnh kiểm của milestone M5 (revision 2)

Candidate: HEAD worktree 4771ccb6a8ead319f06cfeea9463e79522a4f223 (cây mã nguồn trùng cc290f002074514001fa0b03b3eb8c9e00c14db6, integrate(ADAPT-LAUNCH); hai commit sau đó chỉ thêm báo cáo docs(m5) trong docs/delivery-evidence/m5-milestone-close/). Interpreter khoá: C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe (mọi lệnh `python` dưới đây đã chạy bằng đúng interpreter này).

Quy ước: STT 1-274 theo đúng thứ tự trong mục "Lệnh kiểm bắt buộc của task". Cột Exit là mã thoát của riêng đoạn lệnh đó. Pytest có test bị skip thì ghi số skip trong cột Tóm tắt và đánh dấu `SKIP`: exit 0 là kết quả của lệnh, còn test bị skip không được tính là test đã chạy; nguyên nhân skip nêu ở cuối tệp.

| STT | Lệnh (rút gọn) | Exit | Tóm tắt kết quả (nguyên văn dòng cuối) |
| --- | --- | --- | --- |
| 1 | git diff --check | 0 | OK, không có lỗi |
| 2 | probe cấu trúc plan/slices phân hệ a | 0 | OK, không có lỗi |
| 3 | probe cấu trúc plan/slices phân hệ b | 0 | OK, không có lỗi |
| 4 | probe cấu trúc plan/slices phân hệ c | 0 | OK, không có lỗi |
| 5 | probe cấu trúc plan/slices phân hệ i | 0 | OK, không có lỗi |
| 6 | probe cấu trúc plan/slices phân hệ d | 0 | OK, không có lỗi |
| 7 | probe cấu trúc plan/slices phân hệ e | 0 | OK, không có lỗi |
| 8 | probe cấu trúc plan/slices phân hệ f | 0 | OK, không có lỗi |
| 9 | probe cấu trúc plan/slices phân hệ j | 0 | OK, không có lỗi |
| 10 | probe cấu trúc plan/slices phân hệ g | 0 | OK, không có lỗi |
| 11 | probe cấu trúc plan/slices phân hệ h | 0 | OK, không có lỗi |
| 12 | probe plan/slices convergence | 0 | OK, không có lỗi |
| 13 | probe plan/slices convergence-ext | 0 | OK, không có lỗi |
| 14 | probe plan/slices persist | 0 | OK, không có lỗi |
| 15 | probe plan/slices adapt | 0 | OK, không có lỗi |
| 16 | probe plan/slices convergence-ext-ui | 0 | OK, không có lỗi |
| 17 | pytest cp3_migration_sequence | 0 | 8 passed in 2.52s |
| 18 | pytest test_p9_m2_exit_gate | 0 | 6 passed in 7.95s |
| 19 | pytest bộ unit lớn (collection, ingestion, catalog, creative, voice, render) | 0 | 5182 passed, 1 warning, 2237 subtests passed in 15.16s |
| 20 | probe 0013_ingestion.sql | 0 | OK, không có lỗi |
| 21 | pytest test_pinned_migrations_and_runner_untouched | 0 | 1 passed in 0.32s |
| 22 | pytest test_cp4_wiring | 0 | 133 passed, 28 skipped, 1 warning in 3.99s (SKIP) |
| 23 | pytest test_persist_g_postgres | 0 | 16 passed in 7.66s |
| 24 | pytest test_cp5_completion_uow | 0 | 40 passed in 4.58s |
| 25 | pytest test_adapt_wire_services | 0 | 111 passed in 14.17s |
| 26 | pytest test_a01 | 0 | 13 passed, 62 subtests passed in 0.14s |
| 27 | pytest test_a02 | 0 | 27 passed, 99 subtests passed in 0.06s |
| 28 | pytest test_a03 | 0 | 17 passed, 50 subtests passed in 0.06s |
| 29 | pytest test_a04 | 0 | 74 passed in 0.11s |
| 30 | pytest test_a05 | 0 | 40 passed, 20 subtests passed in 0.07s |
| 31 | pytest test_a06 | 0 | 15 passed, 22 subtests passed in 0.04s |
| 32 | pytest test_a07 | 0 | 14 passed, 44 subtests passed in 0.04s |
| 33 | pytest test_a08 | 0 | 32 passed, 3 subtests passed in 0.10s |
| 34 | pytest test_a09 | 0 | 28 passed, 11 subtests passed in 0.11s |
| 35 | pytest test_a10 | 0 | 23 passed, 14 subtests passed in 0.13s |
| 36 | pytest test_a11 | 0 | 18 passed in 0.19s |
| 37 | pytest test_a12 | 0 | 59 passed in 0.13s |
| 38 | pytest test_a13 | 0 | 49 passed in 0.12s |
| 39 | pytest test_a14 | 0 | 19 passed in 0.13s |
| 40 | pytest test_a15 | 0 | 20 passed, 49 subtests passed in 0.06s |
| 41 | pytest test_a16 | 0 | 25 passed in 0.23s |
| 42 | pytest test_a17 | 0 | 33 passed, 29 subtests passed in 0.11s |
| 43 | pytest test_a18 | 0 | 32 passed in 0.19s |
| 44 | pytest test_a19 | 0 | 62 passed in 0.26s |
| 45 | probe pyproject dependencies | 0 | OK, không có lỗi |
| 46 | probe uv.lock | 0 | OK, không có lỗi |
| 47 | pytest ADAPT-A | 0 | 27 passed in 5.91s |
| 48 | probe ADAPT-A | 0 | OK, không có lỗi |
| 49 | pytest ADAPT-D | 0 | 20 passed in 0.22s |
| 50 | probe ADAPT-D | 0 | OK, không có lỗi |
| 51 | pytest ADAPT-E | 0 | 34 passed in 1.60s |
| 52 | probe ADAPT-E | 0 | OK, không có lỗi |
| 53 | pytest ADAPT-E-MEDIA | 0 | 41 passed in 0.60s |
| 54 | probe ADAPT-E-MEDIA | 0 | OK, không có lỗi |
| 55 | pytest ADAPT-F | 0 | 53 passed in 4.21s |
| 56 | probe ADAPT-F | 0 | OK, không có lỗi |
| 57 | pytest ADAPT-J | 0 | 22 passed in 13.58s |
| 58 | probe ADAPT-J | 0 | OK, không có lỗi |
| 59 | pytest ADAPT-I | 0 | 32 passed in 1.89s |
| 60 | probe ADAPT-I | 0 | OK, không có lỗi |
| 61 | pytest ADAPT-CONFIG | 0 | 11 passed in 0.10s |
| 62 | probe profile | 0 | OK, không có lỗi |
| 63 | probe wiring | 0 | OK, không có lỗi |
| 64 | pytest ADAPT-SEED | 0 | 13 passed in 41.96s |
| 65 | probe ADAPT-SEED | 0 | OK, không có lỗi |
| 66 | pytest ADAPT-PROD | 0 | 23 passed, 1 warning in 10.99s |
| 67 | probe ADAPT-PROD | 0 | OK, không có lỗi |
| 68 | pytest ADAPT-LAUNCH | 0 | 29 passed in 0.55s |
| 69 | probe ADAPT-LAUNCH | 0 | OK, không có lỗi |
| 70 | pytest B-01 package_validation | 0 | 39 passed in 0.09s |
| 71 | pytest B-02 normalization+fingerprint | 0 | 30 passed in 0.08s |
| 72 | pytest B-03 article_aggregate+memory_unit_of_work | 0 | 19 passed in 0.06s |
| 73 | pytest B-04 domain_events | 0 | 64 passed in 0.10s |
| 74 | pytest B-05 representative | 0 | 27 passed in 0.06s |
| 75 | pytest B-06 resolve_document | 0 | 31 passed in 0.14s |
| 76 | pytest B-07 event_link | 0 | 45 passed in 0.09s |
| 77 | pytest B-08 event_update | 0 | 61 passed in 0.12s |
| 78 | pytest B-09 source_set | 0 | 39 passed in 0.11s |
| 79 | pytest B-10 queries | 0 | 55 passed in 0.09s |
| 80 | pytest B-11 activity_handler | 0 | 67 passed in 0.13s |
| 81 | pytest B-12 flow_integration | 0 | 15 passed in 0.23s |
| 82 | pytest C-01 identity | 0 | 20 passed, 37 subtests passed in 0.10s |
| 83 | pytest C-02 states | 0 | 20 passed, 45 subtests passed in 0.05s |
| 84 | pytest C-03 discovery | 0 | 11 passed, 11 subtests passed in 0.05s |
| 85 | pytest C-04 renditions | 0 | 20 passed, 33 subtests passed in 0.05s |
| 86 | pytest C-05 hooks | 0 | 18 passed, 31 subtests passed in 0.06s |
| 87 | pytest C-06 candidate_query | 0 | 27 passed, 19 subtests passed in 0.06s |
| 88 | pytest C-07 asset_view | 0 | 31 passed, 189 subtests passed in 0.09s |
| 89 | pytest C-08 renderable | 0 | 20 passed, 87 subtests passed in 0.06s |
| 90 | pytest C-09 usage | 0 | 27 passed, 11 subtests passed in 0.05s |
| 91 | pytest 3 tệp control_ui stream/ts_contract | 0 | 94 passed in 0.23s |
| 92 | pytest unit/control_ui + p7b_sse_stream | 0 | 666 passed, 1 warning in 10.52s |
| 93 | probe event kinds | 0 | OK, không có lỗi |
| 94 | pytest cp4_pagination_postgres | 0 | 16 passed in 13.54s |
| 95 | pytest integration/control_ui + unit/control_ui | 0 | 836 passed, 1 warning in 2.59s |
| 96 | pytest tests/m2 (--deselect h36) | 0 | 179 passed, 1 deselected, 2 warnings in 253.90s (0:04:13) |
| 97 | probe LIMIT 100 | 0 | OK, không có lỗi |
| 98 | pytest cp4_queries routes+postgres | 0 | 30 passed, 1 warning in 7.49s |
| 99 | pytest tests/integration + unit/control_ui | 0 | 2758 passed, 35 skipped, 1 warning, 25 subtests passed in 217.29s (0:03:37) (SKIP) |
| 100 | probe query_ports | 0 | OK, không có lỗi |
| 101 | npm run build | 0 | ✓ built in 3.30s |
| 102 | pytest unit/control_ui | 0 | 661 passed, 1 warning in 1.91s |
| 103 | probe dist orphan | 0 | OK, không có lỗi |
| 104 | probe App.tsx/client.ts | 0 | OK, không có lỗi |
| 105 | probe screenRegistry | 0 | OK, không có lỗi |
| 106 | probe runtime.lock.json | 0 | OK, không có lỗi |
| 107 | probe hai __init__.py | 0 | OK, không có lỗi |
| 108 | pytest test_p0_packaging | 0 | 9 passed in 14.17s |
| 109 | probe src/controlplane/pyproject dependencies | 0 | OK, không có lỗi |
| 110 | probe pyproject packages | 0 | OK, không có lỗi |

Ghi chú STT 101: `npm run build` không làm đổi tệp trong src/controlplane/ui/dist.
| 111 | pytest contract/test_bindings | 0 | 293 passed in 0.80s |
| 112 | probe ownership-and-locks.yaml | 0 | OK, không có lỗi |
| 113 | pytest unit/config+unit/storage+cp3b | 0 | 1125 passed, 239 subtests passed in 1.64s |
| 114 | pytest unit/security+p4_statemachines+test_bindings | 0 | 679 passed, 398 subtests passed in 1.18s |
| 115 | probe hash contract-registry | 0 | OK, không có lỗi |
| 116 | probe PUC-J-03/YC-HT-I-04 | 0 | OK, không có lỗi |
| 117 | pytest integration/orchestration+storage+unit/catalog+storage+render | 0 | 2306 passed, 7 skipped, 1184 subtests passed in 7.08s (SKIP) |
| 118 | probe pyproject db.orchestration | 0 | OK, không có lỗi |
| 119 | pytest cp6_workflow ba tệp | 0 | 28 passed in 1.35s |
| 120 | pytest bộ unit/integration lớn orchestration...storage | 0 | 3379 passed, 1034 subtests passed in 7.64s |
| 121 | probe ui/package.json | 0 | OK, không có lỗi |
| 122 | probe pyproject packages modules/storage | 0 | OK, không có lỗi |
| 123 | probe M2_ACCEPTED_SHA | 0 | OK, không có lỗi |
| 124 | pytest cp3b catalog_graphs+source_parity | 0 | 25 passed in 0.14s |
| 125 | pytest unit/collection+catalog+p4_statemachines | 0 | 658 passed, 841 subtests passed in 2.13s |
| 126 | pytest tests/m2+tests/integration (--deselect h36) | 0 | 2276 passed, 35 skipped, 1 deselected, 2 warnings, 25 subtests passed in 537.12s (0:08:57) (SKIP) |
| 127 | pytest bộ unit lớn có control_ui | 0 | 5250 passed, 1 warning, 1998 subtests passed in 14.55s |
| 128 | probe src/main.py | 0 | OK, không có lỗi |
| 129 | probe dist | 0 | OK, không có lỗi |
| 130 | probe App.tsx deduper | 0 | OK, không có lỗi |
| 131 | pytest test_d01 | 0 | 12 passed, 58 subtests passed in 0.12s |
| 132 | pytest test_d02 | 0 | 68 passed in 0.11s |
| 133 | pytest test_d03 | 0 | 11 passed, 13 subtests passed in 0.03s |
| 134 | pytest test_d04 | 0 | 87 passed in 0.14s |
| 135 | pytest test_d05 | 0 | 20 passed, 79 subtests passed in 0.06s |
| 136 | pytest test_d06 | 0 | 60 passed in 0.10s |
| 137 | pytest test_d07 | 0 | 32 passed in 0.06s |
| 138 | pytest test_d08 | 0 | 62 passed in 0.13s |
| 139 | pytest test_d09 | 0 | 110 passed in 0.20s |
| 140 | pytest test_d10 | 0 | 94 passed in 0.21s |
| 141 | pytest test_d11 | 0 | 62 passed in 0.21s |
| 142 | pytest test_d12 | 0 | 19 passed, 38 subtests passed in 0.04s |
| 143 | pytest test_d13 | 0 | 65 passed in 0.22s |
| 144 | pytest test_d14 | 0 | 18 passed in 0.23s |
| 145 | pytest test_d15 | 0 | 27 passed in 0.17s |
| 146 | pytest test_d16 | 0 | 52 passed in 0.21s |
| 147 | pytest test_d17 | 0 | 22 passed in 0.18s |
| 148 | pytest test_d18 | 0 | 8 passed in 0.28s |
| 149 | pytest test_e01 | 0 | 16 passed, 89 subtests passed in 0.15s |
| 150 | pytest test_e02 | 0 | 65 passed in 0.10s |
| 151 | pytest test_e03 | 0 | 144 passed in 0.18s |
| 152 | pytest test_e04 | 0 | 86 passed in 0.12s |
| 153 | pytest test_e05 | 0 | 50 passed in 0.07s |
| 154 | pytest test_e06 | 0 | 75 passed in 0.11s |
| 155 | pytest test_e07 | 0 | 106 passed in 0.15s |
| 156 | pytest test_e08 | 0 | 63 passed in 0.11s |
| 157 | pytest test_e09 | 0 | 114 passed in 0.15s |
| 158 | pytest test_e10 | 0 | 51 passed in 0.10s |
| 159 | pytest test_e11 | 0 | 21 passed in 0.06s |
| 160 | pytest test_e12 | 0 | 35 passed in 0.12s |
| 161 | pytest test_e13 | 0 | 63 passed in 0.12s |
| 162 | pytest test_e14 | 0 | 79 passed in 0.25s |
| 163 | pytest test_e15 | 0 | 47 passed in 0.16s |
| 164 | pytest test_e16 | 0 | 23 passed in 0.17s |
| 165 | pytest test_e17 | 0 | 45 passed in 0.23s |
| 166 | pytest test_e18 | 0 | 44 passed in 0.27s |
| 167 | pytest test_e19 | 0 | 35 passed in 0.13s |
| 168 | pytest test_e20 | 0 | 25 passed in 2.66s |
| 169 | pytest test_f01 | 0 | 20 passed, 120 subtests passed in 0.48s |
| 170 | pytest test_f02 | 0 | 26 passed, 67 subtests passed in 0.11s |
| 171 | pytest test_f03 | 0 | 169 passed in 0.27s |
| 172 | pytest test_f04 | 0 | 58 passed in 0.14s |
| 173 | pytest test_f05 | 0 | 62 passed in 0.13s |
| 174 | pytest test_f06 | 0 | 104 passed in 0.17s |
| 175 | pytest test_f07 | 0 | 97 passed in 0.14s |
| 176 | pytest test_f08 | 0 | 55 passed in 0.18s |
| 177 | pytest test_f09 | 0 | 118 passed in 0.16s |
| 178 | pytest test_f10 | 0 | 154 passed in 0.22s |
| 179 | pytest test_f11 | 0 | 97 passed in 0.19s |
| 180 | pytest test_f12 | 0 | 45 passed, 129 subtests passed in 0.14s |
| 181 | pytest test_f13 | 0 | 38 passed, 99 subtests passed in 0.09s |
| 182 | pytest test_f14 | 0 | 52 passed, 67 subtests passed in 0.11s |
| 183 | pytest test_f15 | 0 | 73 passed in 0.16s |
| 184 | pytest test_f16 | 0 | 39 passed in 0.21s |
| 185 | pytest test_f17 | 0 | 36 passed in 0.28s |
| 186 | pytest test_f18 | 0 | 28 passed in 0.27s |
| 187 | pytest test_f19 | 0 | 35 passed in 0.40s |
| 188 | pytest test_f20 | 0 | 53 passed in 0.44s |
| 189 | pytest test_f21 | 0 | 17 passed in 0.13s |
| 190 | pytest test_f22 | 0 | 55 passed in 0.16s |
| 191 | pytest G activity_binding | 0 | 43 passed in 0.11s |
| 192 | pytest G completion_binding | 0 | 22 passed, 307 subtests passed in 0.11s |
| 193 | pytest G fencing | 0 | 45 passed in 0.10s |
| 194 | pytest G grant_issuance | 0 | 45 passed in 0.11s |
| 195 | pytest G operation_receipt | 0 | 55 passed in 0.09s |
| 196 | pytest G stage_run_plan+job_waiting | 0 | 147 passed in 0.18s |
| 197 | pytest G allocation_policy+job_allocation | 0 | 88 passed in 0.27s |
| 198 | pytest G variant_reservation_flow | 0 | 47 passed in 0.19s |
| 199 | pytest G completion_gate | 0 | 86 passed in 0.11s |
| 200 | pytest G integration commit_completion | 0 | 62 passed in 0.12s |
| 201 | pytest G command_semantics+retry_policy | 0 | 110 passed in 0.17s |
| 202 | pytest G workflow_catalog+resource_admission | 0 | 82 passed in 0.16s |
| 203 | pytest G event_payloads+consistency_audit | 0 | 175 passed in 0.25s |
| 204 | pytest G recovery_scan+batch_outcome+app_session | 0 | 157 passed in 0.32s |
| 205 | pytest test_h_operation_view_model | 0 | 55 passed in 0.08s |
| 206 | pytest test_h_list_query | 0 | 115 passed in 0.16s |
| 207 | pytest test_h_stream_event_catalog | 0 | 70 passed in 0.10s |
| 208 | pytest test_h_list_queries_sql | 0 | 175 passed, 1 warning in 1.61s |
| 209 | pytest test_h_ops_read_models | 0 | 31 passed in 0.06s |
| 210 | pytest test_h_config_account_views | 0 | 91 passed in 0.09s |
| 211 | pytest test_h_problem_detail | 0 | 37 passed in 0.38s |
| 212 | pytest test_h_read_only_listing | 0 | 43 passed, 1 warning in 0.66s |
| 213 | pytest test_h_metadata_update | 0 | 83 passed, 1 warning in 0.66s |
| 214 | pytest test_h_ts_contract_types | 0 | 10 passed in 0.05s |
| 215 | pytest test_h_status_presentation | 0 | 9 passed in 0.04s |
| 216 | pytest test_h_status_pill | 0 | 22 passed in 0.05s |
| 217 | pytest test_h_error_hover_detail | 0 | 24 passed in 0.05s |
| 218 | pytest test_h_stream_client_registry | 0 | 14 passed in 0.05s |
| 219 | pytest test_h_screen_registry | 0 | 31 passed in 0.07s |
| 220 | pytest test_h_ui_source_guard | 0 | 26 passed in 0.05s |
| 221 | pytest test_storage_declaration | 0 | 65 passed in 0.09s |
| 222 | pytest test_storage_declare_version | 0 | 24 passed in 0.08s |
| 223 | pytest test_storage_verification | 0 | 11 passed, 85 subtests passed in 0.08s |
| 224 | pytest test_storage_cloud_persist | 0 | 22 passed, 21 subtests passed in 0.09s |
| 225 | pytest test_storage_local_journal | 0 | 21 passed in 2.33s |
| 226 | pytest test_storage_staging_paths | 0 | 373 passed, 7 skipped in 1.34s (SKIP) |
| 227 | pytest test_storage_materialization | 0 | 25 passed, 26 subtests passed in 0.08s |
| 228 | pytest test_storage_cleanup_evaluation | 0 | 67 passed in 0.08s |
| 229 | pytest test_storage_cleanup_executor | 0 | 21 passed in 0.19s |
| 230 | pytest test_storage_reconciliation | 0 | 13 passed, 10 subtests passed in 0.05s |
| 231 | pytest test_storage_output_naming | 0 | 32 passed, 97 subtests passed in 0.11s |
| 232 | pytest test_storage_placement | 0 | 56 passed in 0.08s |
| 233 | pytest test_storage_availability | 0 | 41 passed in 0.07s |
| 234 | pytest test_j_route_binding | 0 | 50 passed in 0.08s |
| 235 | pytest test_j_secret_redaction | 0 | 55 passed in 0.08s |
| 236 | pytest test_j_publish_plan | 0 | 60 passed in 0.10s |
| 237 | pytest test_j_status_graph | 0 | 118 passed in 0.15s |
| 238 | pytest test_j_bundle_resolution | 0 | 49 passed in 0.14s |
| 239 | pytest test_j_external_account | 0 | 40 passed in 0.09s |
| 240 | pytest test_j_capacity_snapshot | 0 | 104 passed in 0.11s |
| 241 | pytest test_j_incremental_cost | 0 | 131 passed in 0.13s |
| 242 | pytest test_j_audit_record | 0 | 104 passed in 0.10s |
| 243 | pytest test_j_secret_update | 0 | 63 passed in 0.10s |
| 244 | pytest test_j_credential_issuance | 0 | 51 passed in 0.09s |
| 245 | pytest test_j_capacity_reservation | 0 | 66 passed in 0.10s |
| 246 | pytest test_j_route_resolver | 0 | 50 passed in 0.19s |
| 247 | pytest test_j_fallback_policy | 0 | 41 passed in 0.12s |
| 248 | pytest test_j_account_test | 0 | 47 passed in 0.11s |
| 249 | pytest test_j_capability_health | 0 | 35 passed in 0.09s |
| 250 | pytest test_j_dpapi_secret_store | 0 | 35 passed in 0.59s |
| 251 | pytest test_j_routed_invocation | 0 | 33 passed in 0.15s |
| 252 | pytest persist a | 0 | 22 passed in 14.17s |
| 253 | probe adapter A | 0 | OK, không có lỗi |
| 254 | pytest persist b | 0 | 14 passed in 8.47s |
| 255 | probe adapter B | 0 | OK, không có lỗi |
| 256 | pytest persist c | 0 | 14 passed in 7.74s |
| 257 | probe adapter C | 0 | OK, không có lỗi |
| 258 | pytest persist d | 0 | 22 passed in 13.14s |
| 259 | probe adapter D | 0 | OK, không có lỗi |
| 260 | pytest persist e | 0 | 19 passed in 12.05s |
| 261 | probe adapter E | 0 | OK, không có lỗi |
| 262 | pytest persist f | 0 | 20 passed in 11.30s |
| 263 | probe adapter F | 0 | OK, không có lỗi |
| 264 | probe adapter G | 0 | OK, không có lỗi |
| 265 | pytest persist i | 0 | 16 passed in 7.81s |
| 266 | probe adapter I | 0 | OK, không có lỗi |
| 267 | pytest persist j | 0 | 18 passed in 10.72s |
| 268 | probe adapter J | 0 | OK, không có lỗi |
| 269 | probe TST-E2E-001 | 0 | OK, không có lỗi |
| 270 | probe TST-CTR-INV-002 | 0 | OK, không có lỗi |
| 271 | probe TST-WF-INV-003 | 0 | OK, không có lỗi |
| 272 | probe QR-PERF-005 | 0 | OK, không có lỗi |
| 273 | probe CT-API-010/QR-UX-003 | 0 | OK, không có lỗi |
| 274 | pytest test_tst_m2_p0_001_ast_boundary_rules_clean_codebase | 0 | 1 passed in 0.75s |

Tổng kết: 274/274 lệnh kiểm bắt buộc của milestone M5 (revision 2) thoát với exit 0, 0 lệnh FAIL; trong đó 269 lệnh không có test skip và 5 lệnh có test skip.

Danh sách các lệnh có test skip và nguyên nhân (đã đối chiếu mã test):
- STT 22 (`pytest test_cp4_wiring`): 133 passed, 28 skipped, 1 warning in 3.99s (SKIP). Nguyên nhân: test tham số hoá theo danh mục lệnh `COMMANDS` gọi `pytest.skip` khi lệnh không áp dụng (`tests/integration/convergence/test_cp4_wiring.py` dòng 275, 294, 342, 363).
- STT 99 (`pytest tests/integration + unit/control_ui`): 2758 passed, 35 skipped, 1 warning, 25 subtests passed in 217.29s (0:03:37) (SKIP). 35 = 28 (test_cp4_wiring) + 7 (test_storage_staging_paths).
- STT 117 (`pytest integration/orchestration+storage+unit/catalog+storage+render`): 2306 passed, 7 skipped, 1184 subtests passed in 7.08s (SKIP). 7 = test_storage_staging_paths.
- STT 126 (`pytest tests/m2+tests/integration (--deselect h36)`): 2276 passed, 35 skipped, 1 deselected, 2 warnings, 25 subtests passed in 537.12s (0:08:57) (SKIP). 35 = 28 + 7 như STT 99.
- STT 226 (`pytest test_storage_staging_paths`): 373 passed, 7 skipped in 1.34s (SKIP). Nguyên nhân: `make_symlink` (`tests/integration/storage/test_storage_staging_paths.py` dòng 81) skip khi `os.symlink` không tạo được symlink; tài khoản chạy trên Windows không có đặc quyền tạo symlink.

Không test nào skip vì thiếu hạ tầng sống. Hai mô-đun DPAPI chỉ skip khi nền tảng không phải win32 nên không skip ở lần chạy này.

Không có lệnh nào bị FAIL (0/274).

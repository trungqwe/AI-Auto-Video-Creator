# CP7-9 — Runtime PostgreSQL thật, ranh giới lỗi và hồi quy M1 điều chỉnh (RG-08)

Ngày kiểm: 30/10/2026, lane lane-cp7-9, bằng interpreter khoá của lane, HEAD gốc 12ff20b.

Lệnh pytest đã chạy: python -m pytest tests/real/test_cp7_runtime_fault.py -q -p no:cacheprovider (6/7 test đạt, 1 blocked).

Trạng thái: 5/6 mục RG-08 PASS, RG-08.m1_regression_adjusted BLOCKED. Kiểm thử trên PostgreSQL 18.6 và Temporal 1.31.2 thật trong Docker, 4 bộ suite PostgreSQL hội tụ đạt 0 skip do DSN, chứng minh 19 điểm ranh giới lỗi rollback UOW commit completion, chu trình launcher down rồi start bảo toàn nguyên vẹn volume aiavc_pgdata và số hàng các bảng chính của database controlplane.

## Kết quả

RG-08.pg_suites_no_dsn_skip: PASS
RG-08.commit_rollback_boundaries: PASS
RG-08.volume_preserved: PASS
RG-08.row_counts_equal: PASS
RG-08.m1_regression_adjusted: BLOCKED
RG-08.secret_scan: PASS

## Chi tiết đo

- pg_suites_no_dsn_skip: server=PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2) container=aiavc-postgres bind=127.0.0.1:57028 database=cp7_a4e75eb642d8 partition=db:cp7_a4e75eb642d8 cleanup=drop_in_finally_only_if_created
- pg_suites_no_dsn_skip: tests/integration/convergence/test_cp3_migration_sequence.py rc=0 passed=8 skipped=0 dsn_or_pg_skips=0 seconds=1.9
- pg_suites_no_dsn_skip: tests/integration/convergence/test_cp4_queries_postgres.py rc=0 passed=9 skipped=0 dsn_or_pg_skips=0 seconds=4.3
- pg_suites_no_dsn_skip: tests/integration/convergence/test_cp5_completion_uow.py rc=0 passed=40 skipped=0 dsn_or_pg_skips=0 seconds=3.8
- pg_suites_no_dsn_skip: tests/integration/orchestration/test_g_commit_completion.py rc=0 passed=62 skipped=0 dsn_or_pg_skips=0 seconds=0.6
- commit_rollback_boundaries: postgres_points_passed=19 before=before:insert_ledger during=after:record_usage after_before_commit=before:commit orchestration_suite_passed=62
- volume_preserved: volume=aiavc_pgdata created_at_equal=True container_recreated=True postmaster_restarted=True system_identifier_equal=True database_oid_equal=True sentinel_db=cp7_a4e75eb642d8 partition=db:cp7_a4e75eb642d8 sentinel_rows=1000 sentinel_md5_equal=True temporal_port_open=True down_without_volume_flag=True
- row_counts_equal: tables=92 total_rows=4914 equal=True excluded=cp_app_sessions(before=57 after=58) note=launcher_start_ghi_them_mot_phien
- row_counts_equal: nonzero cp_actors=1 cp_article_revisions=250 cp_articles=243 cp_artifact_locations=321 cp_artifact_versions=321 cp_auth_sessions=25 cp_collected_document_packages=283 cp_collected_document_resolutions=283 cp_collection_attempts=14 cp_collection_checkpoints=283 cp_collection_runs=14 cp_command_receipts=12 cp_config_revisions=12 cp_dedup_evidence=33 cp_execution_grants=583 cp_fetch_observations=283 cp_idempotency_records=12 cp_media_assets=321 cp_media_provenance=382 cp_outbox_events=613 cp_schema_migrations=19 cp_source_command_receipts=7 cp_source_cycle_marks=14 cp_source_identities=7 cp_sources=7 cp_stage_runs=570 cp_workspaces=1
- m1_regression_adjusted: passed=91 failed=1 skipped=0 deselected=1 failed_test=tests/m1/p0/test_environment_validation.py::test_validator_accepts_untampered_environment_manifest reason=uv.lock live hash mismatch recorded=57512d0e58d0b113a2526ce7fa6cc95e4683fced2ea29888297b098bc9618da8 live=92227ec364d1dc6b5e8d0db4b74fb767d5cefd135f43f50e77dd8292083a090a tests_m1_unchanged=True evidence_json_unchanged=True m1proof_validator_patched=False plugin_or_monkeypatch=none excluded=test_live_e3_drive_verification(OI-CP7-05) h36_not_run=True
- secret_scan: match_count=0; không đọc Credentials/; mật khẩu PostgreSQL chỉ đi qua tệp secrets của launcher và biến môi trường tiến trình con; chi phí 0 USD
- deadline: limit_s=3600 remaining_s=3511 partition=db:cp7_a4e75eb642d8

## Quyết định cần AI PM

RG-08.m1_regression_adjusted không đạt 92 passed và không thể đạt trong owned paths của CP7-9. Nguyên nhân gốc: `tests/m1/p0/test_environment_validation.py::test_validator_accepts_untampered_environment_manifest` gọi `validate_environment_manifest` (`src/m1proof/environment.py:221-232`), hàm này so hash `uv.lock` hiện hành với hash M1 đã ghi trong `docs/milestones/m1-proof/evidence/m1-p0/environment.json` rồi so quan sát sống của python, uv, project, postgresql. `uv.lock` đã đổi hợp lệ sau M1 (dependency slice ADAPT-DEPS) nên hash lệch (xem recorded và live ở trên). Validator dừng ở mục đầu tiên, nên chưa biết các mục quan sát sống còn lại có lệch hay không.

Đã gỡ plugin `m1_compat_plugin` (fake PASS theo Auditor F1); `tests/m1` chạy nguyên trạng; không sửa `tests/m1`, `src/m1proof`, evidence M1 hay `uv.lock`.

Lựa chọn cho AI PM (Sonnet 5.5), Orchestrator không tự chọn: (A) mở rộng OI-CP7-05 để loại thêm đúng test `test_validator_accepts_untampered_environment_manifest` (kỳ vọng 91 passed, 2 deselected) và sửa acceptance tương ứng; (B) giữ tiêu chí 92 passed, RG-08.m1_regression_adjusted ở BLOCKED cho tới khi có quyết định khác. Chưa có quyết định nào được ghi nhận.

## Giới hạn trung thực

1. DSN dùng người dùng controlplane của container aiavc-postgres, trỏ database cp7_<runId>, bốn bộ tự tạo và xóa database riêng, database controlplane/temporal không bị chạm;
2. Ranh giới rollback trước/trong/sau lấy từ ba điểm before:insert_ledger, after:record_usage, before:commit của 19 điểm cp5 (ánh xạ là GIẢ ĐỊNH của slice);
3. Số hàng loại cp_app_sessions vì launcher start luôn ghi thêm một phiên, đo khi worker đã dừng;
4. Chu trình launcher start/stop/down/start chạy trên ngăn xếp thật và kết thúc với worker dừng, container còn chạy;
5. Temporal chỉ kiểm cổng 7233 mở sau start, không chạy workflow;
6. tests/m1 loại test_live_e3_drive_verification theo OI-CP7-05, không chạy h36 nguyên văn;
7. Số đo lấy từ lượt chạy bước 13, bước 16 chỉ xác nhận lại;
8. tests/m1 chạy nguyên trạng, không plugin, không monkeypatch m1proof hay tests/m1; bản vá plugin cũ (m1_compat_plugin) đã bị gỡ theo Auditor F1 vì là fake PASS; chỉ loại test_live_e3_drive_verification theo OI-CP7-05.

## Chi phí

Chi phí: 0 USD; thời gian chạy dưới 40 phút; không đọc Credentials/; không có bí mật.

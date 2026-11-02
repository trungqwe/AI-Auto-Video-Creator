# Báo cáo nghiệm thu CP7-13: Restore drill và đối soát Drive (RG-12)

## Kết luận

Toàn bộ 10/10 hạng mục kiểm thử RG-12 đều đạt trạng thái PASS, không có lỗi hay điều kiện BLOCKED nào. Chi phí thực hiện là 0 USD, dung lượng tải lên Google Drive là 256 KiB trong phạm vi thư mục `cp7-fixture/7b5a52c777e2`. Thay đổi `state/active-db` sang CSDL mới `controlplane_20261102225059` là có chủ đích theo quy trình runbook; CSDL cũ `controlplane` được bảo toàn nguyên vẹn; không xoá bất kỳ CSDL nào và không xoá tệp Drive nào ngoài thư mục của lượt chạy.

## Lệnh đã chạy

Lệnh kiểm thử bước 13:
`python -m pytest tests/real/test_cp7_restore_drill.py -q -p no:cacheprovider`

Mã thoát (exit code): 0
Kết quả tổng kết pytest: `11 passed in 57.18s`

Kiểm tra khoảng trắng thừa:
`git diff --check`
Mã thoát (exit code): 0

## Dữ liệu lượt chạy

- runId: `7b5a52c777e2`
- Tên tệp dump: `cp7-13-7b5a52c777e2.dump`
- CSDL trước restore (old_db): `controlplane`
- CSDL sau restore (new_db): `controlplane_20261102225059`
- Recovery epoch trước restore (old_epoch): `1`
- Recovery epoch sau restore (new_epoch): `2`
- Thời gian launcher start sẵn sàng: 36.6 giây (giới hạn ngân sách 300 giây)
- Tổng số hàng bảng chính tại thời điểm backup: 110513 hàng trên 93 bảng, bằng chính xác số hàng đo đạc sau restore trước khi launcher start

## Bằng chứng RG-12

RG-12.dump_sha256: PASS
- dump_sha256: sha256=a3d165fb92ccf09dc494dac233f74e47c11c73def66e4d63707358e23adb0e84 sidecar_equal=True restore_source_sha256_equal=True size_bytes=16364000

RG-12.new_db_created: PASS
- new_db_created: old_db=controlplane new_db=controlplane_20261102225059 oid_differs=True active_db_switched=True restore_did_not_overwrite_active_db=True

RG-12.epoch_before_switch: PASS
- epoch_before_switch: source_order_epoch_before_active_db=True mtime_epoch_le_active_db=True epoch=1->2 history_len=1->2 previous_entries_unchanged=True

RG-12.old_epoch_rejected: PASS
- old_epoch_rejected: old_epoch=1 current_epoch=2 old_result=STALE_RECOVERY_EPOCH current_result=ACCEPTED real_old_epoch_grant_current=None stale_journal_entry_reissue=True cleanup_with_old_epoch=forbidden

RG-12.old_db_kept: PASS
- old_db_kept: old_db=controlplane still_in_pg_database=True oid_equal=True row_counts_unchanged_after_restore=True tables=93

RG-12.row_counts_equal: PASS
- row_counts_equal: tables=93 total_rows=110513 equal_to_backup_time=True measured=restored_db_before_launcher_start nonzero cp_actors=1 cp_ai_invocation_records=3040 cp_analysis_results=6543 cp_app_sessions=179 cp_article_revisions=387 cp_articles=361 cp_artifact_locations=1936 cp_artifact_versions=1506 cp_audio_bed_results=442 cp_audit_records=2182 cp_auth_sessions=92 cp_batch_capacity_reservations=517 cp_capacity_reservations=27 cp_cleanup_eligibility=429 cp_collected_document_packages=565 cp_collected_document_resolutions=564 cp_collection_attempts=28 cp_collection_checkpoints=565 cp_collection_runs=28 cp_command_receipts=332 cp_completion_ledger=429 cp_config_revisions=293 cp_content_analyses=512 cp_creative_receipts=4566 cp_creative_selections=496 cp_dedup_evidence=177 cp_event_checkpoints=6500 cp_execution_grants=18815 cp_fetch_observations=565 cp_hook_revisions=10 cp_hooks=10 cp_idempotency_records=332 cp_image_safety_assessments=2014 cp_job_candidates=517 cp_language_evidence=451 cp_media_assets=551 cp_media_provenance=794 cp_media_usage=3202 cp_operation_stream=6448 cp_orchestration_receipts=489 cp_outbox_events=11834 cp_output_metadata=488 cp_package_validation_reports=438 cp_probe_reports=2018 cp_processed_media=2065 cp_production_batches=39 cp_production_plans=493 cp_production_snapshots=514 cp_quality_gate_results=438 cp_quality_reports=438 cp_render_attempts=1314 cp_render_operation_receipts=1744 cp_render_packages=438 cp_schema_migrations=19 cp_script_versions=498 cp_source_command_receipts=8 cp_source_cycle_marks=44 cp_source_identities=8 cp_sources=8 cp_stage_runs=6850 cp_story_angle_sets=499 cp_story_angles=998 cp_timing_validation_reports=451 cp_tts_invocation_records=629 cp_upload_receipts=430 cp_variant_registry=1 cp_variant_reservations=489 cp_variant_validations=1066 cp_video_jobs=517 cp_video_outputs=438 cp_voice_receipts=7473 cp_voice_tracks=479 cp_word_timings=451 cp_workspaces=1

RG-12.drive_reconcile_newer: PASS
- drive_reconcile_newer: orphan_finding=ORPHAN_PROVIDER_OBJECT object_digest=9652fea5efd6e9da created_after_backup=True restored_db_location_rows=0 control_view_with_location_orphans=0 upload_bytes=262144 cap_bytes=10485760

RG-12.no_cleanup_before_reconcile: PASS
- no_cleanup_before_reconcile: order=backup>upload>stop>restore>start>reconcile_done>cleanup drive_output_present_at_reconcile=True cleanup_deleted=2 only_under_cp7_fixture_run_folder=True

RG-12.resume_after_restore: PASS
- resume_after_restore: start_rc=0 ready_seconds=36.6 limit_seconds=300 app_port_open=True active_db=controlplane_20261102225059 epoch=2

RG-12.secret_scan: PASS
- secret_scan: surfaces=2 secret_pattern_matches=0 postgres_password_hits=0 cost_usd=0 api_calls=14

## Giới hạn

- Diễn tập khôi phục (restore drill) được thực hiện cục bộ trên máy trạm vận hành v1.
- Tiến trình worker được chủ động dừng trước khi tạo backup để bảo đảm số lượng bản ghi bảng chính có tính xác định cao cho phép đo đối sánh.
- Các quyết định fencing và tính hợp lệ của grant thuộc recovery epoch cũ được thẩm định bằng evaluate_result_fencing và ExecutionGrantCurrency.
- Đối soát dữ liệu ngoại vi Google Drive được giới hạn an toàn tuyệt đối trong thư mục cô lập cp7-fixture/7b5a52c777e2, bảo đảm không tác động tới dữ liệu nào khác ngoài phạm vi chạy thử.

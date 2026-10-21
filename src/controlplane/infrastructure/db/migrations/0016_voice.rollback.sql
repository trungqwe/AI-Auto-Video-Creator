-- 0016_voice.rollback.sql
DROP TABLE IF EXISTS controlplane.cp_voice_receipts;
DROP TABLE IF EXISTS controlplane.cp_analysis_results;
DROP TABLE IF EXISTS controlplane.cp_probe_reports;
DROP TABLE IF EXISTS controlplane.cp_audio_bed_results;
DROP TABLE IF EXISTS controlplane.cp_language_evidence;
DROP TABLE IF EXISTS controlplane.cp_tts_invocation_records;
DROP TABLE IF EXISTS controlplane.cp_timing_validation_reports;
DROP TABLE IF EXISTS controlplane.cp_word_timings;
DROP TABLE IF EXISTS controlplane.cp_voice_tracks;
DROP TABLE IF EXISTS controlplane.cp_image_safety_assessments;
DROP TABLE IF EXISTS controlplane.cp_processed_media;
DROP FUNCTION IF EXISTS controlplane.cp_reject_voice_history_mutation();

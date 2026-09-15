# HANDOFF

- Đã quyết định: M1 và M2-P1..P4 là `ACCEPTED / CLOSED`; checkpoint P4 đóng tại `8db00b30afe7286430e9b40d14bfd8b26b8194d5`.
- Trạng thái hiện hành: `M2-P5A_PLAN_READY_FOR_REVIEW` và `M2-P5B_PLAN_READY_FOR_REVIEW`. Chỉ có planning/contract traceability; chưa được viết Behavioral RED, implementation, migration hay runtime evidence.
- P5A: schema target `0004_config_and_secrets`, exact 5 future oracle. CT-STATE-013 khóa `DRAFT → PUBLISHED → SUPERSEDED` và security `DRAFT|PUBLISHED|SUPERSEDED → INVALIDATED`; chỉ INVALIDATED terminal, không self-transition/reopen. Content hash tái dùng canonicalizer RFC 8785/JCS P2 trên canonical UTF-8 bytes rồi SHA-256 lowercase hex; không tự phát minh canonicalizer.
- P5B: schema target `0005_artifact_metadata`, exact 5 future oracle; tái dùng P4 ArtifactLocationState. P5B kết thúc ở `CLEANUP_AUTHORIZED`, chỉ persistence authorization bất biến và không xóa/simulate byte, persist `DELETED` hay phát `CleanupCompleted`. Dù P5A/B logical siblings, `MigrationRunner` tuần tự bắt buộc P5B RED/implementation chờ checkpoint P5A/`0004` được accept.
- Tệp cần đọc tiếp: `docs/milestones/m2-control-plane/spec.md`, `implementation-plan.md`, contracts `00-common`, `02-domain-events`, `10-storage`, `11-config-security`, `12-state-machines`; ADR `0004`, `0006`, `0009`, `0010`; và `docs/12-pre-code-checklist.md`.
- Điểm tiếp tục: independent audit hai P5 plan. P6+, M3 và Module A vẫn `NOT AUTHORIZED`.

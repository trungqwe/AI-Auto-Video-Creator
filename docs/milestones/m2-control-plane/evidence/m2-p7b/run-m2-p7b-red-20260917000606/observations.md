# M2-P7B Behavioral RED — quan sát

- Source/test/seam SHA: `7fa928b1f715a66b0d5a579c2530884598ed482d`; exact collect 5; full run `5 failed / 0 passed / 0 errors / 0 skipped`.
- PostgreSQL 18.6, CREATEDB=true, kết nối PASS; tất cả disposable DB đã xóa, orphan=0.
- #000 `UPSTREAM_INVARIANT_RED`: hai connection và hai transaction thật, cùng workspace, khác aggregate. T1 append nhận N=1 rồi chờ event; T2 append nhận M=2 và commit trước khi T1 được giải phóng. Reader chỉ thấy M=2 và advance đến 2. T1 commit N=1 sau đó; query `stream_event_id > 2` trả rỗng, bỏ sót N. Ba lần chạy độc lập đều tái hiện N=1/M=2. Không sửa accepted P3 `append()`.
- #001 route thực `/v1/operations/stream` được mount trên P7A app và qua Host/Origin/session; HTTP 500 có technical detail `NotImplementedError` đã xác minh bằng DB, tại `SseStreamPresenter.frames`, không phải 404.
- #002 fixture có bốn durable rows; `SseStreamService.replay_after` ném `P7B_SSE_REPLAY_NOT_IMPLEMENTED`.
- #003 watermark thật được persist và xác minh; `SseStreamService.classify_cursor` ném `P7B_SSE_CURSOR_CLASSIFICATION_NOT_IMPLEMENTED`.
- #004 session P7A server-side thuộc workspace A, request không session bị từ chối, A/B có row bền vững; `PostgresSseReader.fetch_workspace_page` ném `P7B_SSE_WORKSPACE_PAGE_NOT_IMPLEMENTED`.
- Mandatory regressions: P7A oracle 4/4, P7A hardening 36/36, P3 11/11, architecture 6/6. Bổ sung P6 4/4, P5B 5/5, P5A 5/5, P4 9/9, P2 11/11, P1 11/11, P0 33/33. M1 không chạy trong checkpoint này, không có PASS claim.
- Secret scan CLEAN/0. Không có migration 0008 hay dependency pin drift; `uv lock --check` PASS và có command provenance trong run.

RED chỉ sẵn sàng cho independent review. P7B GREEN/ordering fence vẫn bị khóa.

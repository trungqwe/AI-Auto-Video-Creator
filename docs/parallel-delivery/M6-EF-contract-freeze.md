# ??ng B?ng H?p ??ng Giao Ti?p: M6-EF (Contract Freeze Specification)

> **M? g?i (Package ID):** `M6-EF` (Chuy?n ti?p t? `M6-EF-TEMPLATE`)
> **Tr?ng th?i ??ng b?ng:** `frozen_design_baseline`
> **Th?m quy?n quy ??nh:** CT-CMN-012, `docs/parallel-delivery/contract-registry.yaml`, `operating-model.md`
> **R?ng bu?c b?t bi?n:** B?t bu?c kh?p ch?nh x?c m? b?m SHA-256 ngu?n; sai m? b?m ho?c sai ngu?n ??nh ngh?a ph?i fail-closed.

---

## 1. Nguy?n T?c ??ng B?ng H?p ??ng (Contract Freeze Principles)

1. **Kh?a b?t bi?n (Immutable Baseline):** M?i c?ng vi?c chu?n b? v? tri?n khai t??ng lai c?a Ph?n h? E (X? l? Media, ?m thanh & Kh?p Ph? ?? / `CAP-E-VOICE`) v? Ph?n h? F (D?ng Video & Ki?m tra Ch?t l??ng / `CAP-F-RENDERING`) b?t bu?c ph?i d?a tr?n ??ng c?c phi?n b?n h?p ??ng ?? ???c ??ng b?ng d??i ??y.
2. **Fail-Closed khi sai l?ch:** N?u ph?t hi?n m? b?m t?p ngu?n th?c t? kh?c v?i m? b?m ?? ??ng b?ng, to?n b? chu tr?nh ki?m th? v? t?ch h?p ph?i d?ng ngay l?p t?c (`FAIL_CLOSED_CONTRACT_DRIFT`).
3. **C?m s?a t?p ngu?n h?p ??ng:** Nghi?m c?m m?i s?a ??i ??i v?i c?c t?p ngu?n trong `docs/09-contracts/**` trong ph?m vi c?a g?i n?y (`LOCK-CONTRACT-SOURCE`). M?i ?? xu?t thay ??i h?p ??ng ph?i th?ng qua quy tr?nh RFC / ADR ki?n tr?c c?p cao.

---

## 2. B?ng ??ng B?ng C?c H?p ??ng Li?n Quan (Exact Frozen Contract Revisions)

| M? H?p ??ng (Contract ID) | T?p Ngu?n ??nh Ngh?a (Defining Source) | Prefixes | Owner | Exact Frozen SHA-256 |
|---|---|---|---|---|
| `CONTRACT-MEDIA-PROCESSING` | `docs/09-contracts/07-media-processing-contracts.md` | `CT-PROC-*`, `CT-TTS-*`, `CT-SUB-*`, `CT-AUD-*` | E (Co-owners: C, I) | `c5f7abaea422916165d59f8a5508817729d21035cffd663123a913c49365cf49` |
| `CONTRACT-RENDER-QUALITY` | `docs/09-contracts/08-render-quality-contracts.md` | `CT-RND-*`, `CT-QC-*` | F (Caller: G, Artifact owner: I) | `c3e35d032c0a8e721ed35bbecb5fb57f350788e8520d6e8df5ca78284199b493` |
| `CONTRACT-CREATIVE-AI` | `docs/09-contracts/06-creative-ai-contracts.md` | `CT-AI-*` (lo?i tr? `CT-AI-ROUTE-*`) | D | `92b74489890f1eaf3915aef809af4cff0585659842f6930bbdf11d1236861b3a` |
| `CONTRACT-STORAGE` | `docs/09-contracts/10-storage-contracts.md` | `CT-STO-*` | I | `6ab6f60bc2760ea9017ca0406e0053dc859cc06c1f0c80fff7e944d03d5e02ce` |
| `CONTRACT-CONFIG-SECURITY` | `docs/09-contracts/11-configuration-security-contracts.md` | `CT-CFG-*`, `CT-SEC-*`, `CT-ACC-*`, `CT-AI-ROUTE-*`, `CT-CAP-*`, `CT-COST-*` | J | `989d9ef22c2096f56453722f059efc1427a3018e64c1a7f67a8d514f55c69645` |
| `CONTRACT-COMMON` | `docs/09-contracts/00-common-contract.md` | `CT-CMN-*` | CROSS-CUTTING | `dfdce8db13d5f1d1f286ccd233a66caf39f48552da2dbbad26692fde7be978e8` |
| `CONTRACT-STATE-MACHINES` | `docs/09-contracts/12-state-machines.md` | `CT-STATE-*` | G (Co-owners: C, D, I) | `2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28` |
| `CONTRACT-WORKFLOW-EXECUTION` | `docs/09-contracts/03-workflow-and-execution.md` | `CT-WF-*` | G | `0fca25f2bc037a4c2bc58b844079dace8c19a9fd5af5c0ce8ad75e421bc2dc83` |
| `CONTRACT-DOMAIN-EVENTS` | `docs/09-contracts/02-domain-events.md` | `CT-EVT-*` | G | `8114a208cecca67e553345ea5574d68752323c79cf833c8c8c9fa5e2f86e7540` |
| `CONTRACT-ORCHESTRATION` | `docs/09-contracts/09-orchestration-contracts.md` | `CT-ORC-*` | G | `402f499f2ac2613502684f1d89697cf72d0cc136b25f2fd08fae07a7c1baaf59` |
| `CONTRACT-CONTENT-MEDIA` | `docs/09-contracts/05-content-media-contracts.md` | `CT-MED-*`, `CT-HOOK-*` | C (Co-owners: B, I) | `ea6a3723dece842d132f634d44c32eb301fbc98b43b61d24b5c32c907782e4cf` |
| `CONTRACT-SOURCE-CONTENT` | `docs/09-contracts/04-source-content-contracts.md` | `CT-SRC-*`, `CT-CNT-*` | A (Co-owner: B) | `61b075d202dd0d7729123f68f26285097be8120e2de48194d0ad2fe847701f31` |
| `CONTRACT-CONTROL-API-STREAM` | `docs/09-contracts/01-control-api-and-stream.md` | `CT-API-*` | H | `ea16fe04759e6bdf3b7bdde3e27ad498d13a271bd45d412ba0e9068a9b918e12` |

---

## 3. Chi Ti?t Giao Di?n CONTRACT-MEDIA-PROCESSING (Bound to Ph?n H? E)

### 3.1. Ranh gi?i tr?ch nhi?m v? ?y quy?n (Section 1)
- Ph?n h? E th?c hi?n probe, ph?n t?ch, transform, transcode, chu?n h?a ?m thanh, t?ng h?p TTS v? c?n ch?nh m?c th?i gian t? (`word alignment`).
- Ph?n h? E tuy?t ??i kh?ng:
  1. Ch?n g?c k? c?u chuy?n ho?c t? s?a ??i v?n b?n k?ch b?n.
  2. T? ? ch?n media ngo?i danh m?c tham chi?u/fallback ?? ???c k? ho?ch s?n xu?t ph? duy?t.
  3. T? quy?t ??nh m?t video ?? ho?n th?nh.
  4. Ghi tr?c ti?p tr?ng th?i catalog ho?c storage do Ph?n h? C v? I s? h?u.
  5. Th?c hi?n x? l? nh?y c?m ??i v?i c?c ?o?n video clip trong ph?m vi hi?n t?i (ch? ?p d?ng an to?n h?nh ?nh cho ?nh t?nh).

### 3.2. H?p ??ng y?u c?u v? k?t qu? x? l? chung (CT-PROC-001, CT-PROC-002)
- **`CT-PROC-001` (`ProcessingRequest`):**
  - `processing_operation_id`: Kh?a idempotency x?c ??nh duy nh?t cho t?ng thao t?c.
  - `stage_run_id`, `execution_grant`: Quy?n th?c thi v? fencing token do Orchestration c?p.
  - `input_artifact_refs`: Phi?n b?n byte v? revision ??u v?o b?t bi?n.
  - `operation_spec_revision`: Th?ng s? k? thu?t x? l? ?? ???c phi?n b?n h?a.
  - `expected_output_profile`: Codec, k?ch th??c, th?i l??ng ho?c schema k? v?ng.
  - `resource_limits`: ??nh m?c CPU, GPU, RAM, dung l??ng ??a v? th?i gian x? l? t?i ?a.
  - `output_storage_intent`: Ph?n lo?i ??ch l?u tr? (`staging`, `reusable rendition`, `per-video temporary`).
- **`CT-PROC-002` (`ProcessingResult`):**
  - `disposition`: Tr?ng th?i x? l? (`succeeded`, `failed`, `waiting`, `outcome_unknown`).
  - `output_artifact_refs`: Danh s?ch artifact version b?t bi?n sinh ra.
  - `processor_identity`: Danh t?nh c?ng c?, model, phi?n b?n v? build number.
  - `input_fingerprint`, `output_hashes`: ??m b?o to?n v?n d? li?u v? truy xu?t ngu?n g?c (lineage).
  - `technical_report`: B?o c?o chi ti?t v? probe, ch?t l??ng, th?i l??ng, codec v? s? li?u k? thu?t.
  - `warnings`: Danh s?ch c?nh b?o c? m? chu?n h?a.
  - `operation_receipt_ref`: Bi?n nh?n t?c d?ng ph? (side-effect receipt).
  - B?t bi?n: ??u ra ch? ???c xem l? `ready` sau khi Ph?n h? I x?c th?c artifact v? owner t??ng ?ng (C/E) commit metadata.

### 3.3. Probe v? ph?n t?ch media (CT-PROC-003, CT-PROC-004)
- **`CT-PROC-003` (`ProbeMedia`):**
  - B?c t?ch container/media type th?c t?, c?c lu?ng video/audio/image.
  - ?o l??ng th?i l??ng ch?nh x?c, k?ch th??c (width x height), frame rate, sample rate, s? k?nh ?m thanh, codec, pixel format.
  - Ph?t hi?n d?u hi?u t?p l?i/h?ng (`corruption/readability signals`), metadata xoay chi?u/m?u s?c, k?ch th??c v? SHA-256 th?c t?.
  - B?t bi?n: Tuy?t ??i kh?ng tin t??ng ph?n m? r?ng t?p (extension) ho?c MIME type t? ngu?n t?i v? n?u k?t qu? probe m?u thu?n.
- **`CT-PROC-004` (`AnalyzeMedia`):**
  - Tr?ch xu?t keyframes, c?nh quay (shots), transcript/OCR, nh?n di?n th?c th?/khu?n m?t/v?t th?, chuy?n ??ng, c?nh, n?ng l??ng ?m thanh.
  - ??u ra l? versioned output; model ph?n t?ch m?i kh?ng ???c ghi ?? l?n k?t qu? ph?n t?ch c?.

### 3.4. ??nh gi? an to?n h?nh ?nh v? chuy?n ??i nh?y c?m (CT-PROC-005, CT-PROC-006, R25)
- **`CT-PROC-005` (`AssessImageSafety`):**
  - Ch? ?p d?ng cho **?nh t?nh** t? ngu?n v? thumbnail li?n quan; kh?ng ?p d?ng x? l? nh?y c?m cho video clip trong ph?m vi hi?n t?i.
  - Tr?ng th?i tr? v?:
    - `SAFE`: An to?n, ???c ph?p d?ng ?nh g?c.
    - `TRANSFORM_REQUIRED`: Ph?t hi?n tr? em, m?u me, v? kh?; b?t bu?c ph?i x? l? tr??c khi d?ng.
    - `UNCERTAIN`: Kh?ng ?? ?? tin c?y; ???c ph?p d?ng k?m warning theo quy?t ??nh r?i ro R25.
    - `DETECTION_FAILED`: L?i nh?n di?n; ???c ph?p d?ng k?m l?i/warning theo R25.
    - `TRANSFORM_FAILED`: X? l? th?t b?i; ???c ph?p d?ng ?nh g?c n?u t?p c?n ??c ???c (R25), nh?ng kh?ng ???c ghi nh?n l? x? l? th?nh c?ng.
    - `UNREADABLE`: T?p h?ng, kh?ng ??c ???c; lo?i b? ho?n to?n.
- **`CT-PROC-006` (`TransformSensitiveImage`):**
  - Th?c hi?n l?m m? (blur) tr? em, l?m m? ho?c ??i m?u v?ng m?u me, x? l? v?ng v? kh? theo ch?nh s?ch version h?a.
  - L?u gi? ?nh g?c tr?n cloud theo retention policy; phi?n b?n ?? x? l? d?ng l?i ???c c?ng ???c l?u gi?.
  - B?t bi?n: Hook visual do ng??i d?ng ch? ??nh ?? ???c x? l? l?m m? t? tr??c, kh?ng ch?y l?i pipeline safety n?y.

### 3.5. Chu?n h?a media (CT-PROC-007)
- Th?c hi?n crop, resize, pad, chuy?n ??i m?u, transcode, chu?n h?a ?m thanh, tr?ch xu?t khung h?nh v? c?t g?t th?i l??ng.
- B?t bi?n: Tuy?t ??i kh?ng thay ??i t?p g?c; ??u ra l? rendition m?i c? lineage ??y ??; kh?ng crop m?t ch? th? ngo?i focus rule trong k? ho?ch; chuy?n ??i ph?i c? t?nh x?c ??nh (deterministic).

### 3.6. T?ng h?p gi?ng ??c (CT-TTS-001, R09, Gate G06)
- **??u v?o:** Exact `script_version_id` v? script fingerprint, voice profile/provider route ref t? Module J, ch? d?n ph?t ?m (`pronunciation_hints`), tham s? nh?p ?i?u/c?m x?c, ng?n ng? (ti?ng Anh).
- **??u ra:** Voice artifact ref, li?n k?t b?t bi?n script/voice fingerprint, th?i l??ng th?c t?, th?ng s? model/provider/voice revision, s? li?u s? d?ng/chi ph? v? receipt.
- **B?t bi?n th?i l??ng:** File gi?ng ??c sinh ra b?t bu?c ph?i c? th?i l??ng t??ng th?ch v?i gi?i h?n video **61?70 gi?y** (`INV-008`, `FR-REN-002`). Voice l? d? li?u ri?ng c?a t?ng video v? c? th? cleanup sau khi video ho?n t?t theo ?y quy?n c?a Module I.

### 3.7. C?n ch?nh m?c th?i gian t? v? ph? ?? (CT-SUB-001, R10, INV-007, INV-019)
- **??u v?o:** Exact script version, exact voice artifact version/hash, ch?nh s?ch ng?n ng?/tokenization, c?ng c? c?n ch?nh (alignment model revision).
- **??u ra:** Danh s?ch c? th? t? c?c t?/token k?m `start_ms`, `end_ms`, text, normalized text, ?? tin c?y (confidence), kho?ng tr?ng (alignment gaps), ranh gi?i c?u/?o?n, script fingerprint, voice hash v? validation report.
- **B?t bi?n c?n ch?nh t?:**
  1. M?c th?i gian ph?i t?ng ??n ?i?u, kh?ng ?m (`start_ms < end_ms` v? `start_ms[i+1] >= start_ms[i]`), n?m tr?n trong th?i l??ng voice (`INV-007`).
  2. Timing ph?i g?n k?t ch?nh x?c v?i script fingerprint v? voice hash t??ng ?ng (`INV-010`).
  3. Thay ??i script ho?c voice l?p t?c l?m v? hi?u h?a (invalidate) to?n b? timing h? ngu?n (`INV-010`).
  4. ?? ph? t? ng? ph?i ??t 100%, kh?ng ???c b? s?t b?t k? t? n?o c?a k?ch b?n (`INV-019`).
  5. Ph? ?? cu?i b?t bu?c ph?i ???c burn-in v?o video v? h? tr? hi?u ?ng karaoke ??i m?u theo t?ng t?.

### 3.8. Chu?n b? ?m thanh n?n v? SFX (CT-AUD-001, FR-AUD-001..007)
- **??u v?o:** Cues t? k? ho?ch s?n xu?t (ProductionPlan), tham chi?u music/SFX ?? resolve, voice artifact ref, quy t?c preset ?m thanh, gi?i h?n ?m l??ng/mix.
- **??u ra:** Renditions ?m nh?c/SFX ?? chu?n b?, cue timing refs, b?o c?o ?? l?n ?m thanh (loudness/peak report ??t chu?n EBU R128 -14 ??n -16 LUFS), metadata xu?t x? v? r?i ro.
- **B?t bi?n:** Ph?n h? E kh?ng t? ? ??i mood ho?c ch?n b?i m?i n?u k? ho?ch kh?ng cho ph?p fallback. ?m thanh hook, l?i ??c, nh?c n?n v? SFX ph?i h?a ?m c?n b?ng m? kh?ng l?m m?t kh? n?ng nghe hi?u l?i d?n (`FR-AUD-006`).

### 3.9. Ph?n lo?i l?u tr? v? thu d?n (CT-PROC-008)
- Ph?n lo?i 3 nh?m: Reusable (?nh blur/recolor, clip normalize), Per-video (voice track, word timing, mix t?m), Diagnostic (frame/log debug).
- B?t bi?n: Ph?n h? E kh?ng t? ? x?a t?p; ch? g?n nh?n retention intent ?? Ph?n h? I th?c hi?n th?m ??nh v? d?n d?p.

---

## 4. Chi Ti?t Giao Di?n CONTRACT-RENDER-QUALITY (Bound to Ph?n H? F)

### 4.1. Nguy?n t?c c?t l?i (Section 1)
- Ph?n h? F l? b? m?y th?c thi k? ho?ch d?ng ?? ???c kh?a.
- Ph?n h? F ???c ph?p resolve th?ng s? k? thu?t theo preset v? danh m?c fallback ?? khai b?o.
- Ph?n h? F tuy?t ??i kh?ng: T? vi?t l?i n?i dung, t? ??i g?c k? c?u chuy?n, ho?c t? ch?n t?i nguy?n ngo?i ph?m vi cho ph?p c?a k? ho?ch d?ng.

### 4.2. Kh?a 5 Preset phong c?ch d?ng (CT-RND-001, FR-PRS-001..005)
- H? th?ng c? ??ng **5 nh?m preset m?u** ???c thi?t k? chi ti?t:
  - Nh?p ?i?u h?nh ?nh (visual rhythm) v? kho?ng th?i l??ng t?ng c?nh.
  - Quy t?c b? c?c (layout), crop, zoom v? hi?u ?ng chuy?n c?nh.
  - Phong c?ch l?p ph? thumbnail (thumbnail overlay style: bi?u t??ng, m?i t?n, d?u h?i, d?u c?m th?n).
  - Quy t?c font ch? (typography) v? ki?u hi?n th? ph? ?? karaoke highlight ??i m?u.
  - X? l? ph?n ?o?n hook (hook treatment).
  - Quy t?c h?a ?m gi?ng ??c/nh?c n?n/SFX.
  - Quy t?c m?u s?c/hi?u ?ng (color/effect rules), output profile v? r?ng bu?c fallback.
  - M? b?m nh?n di?n preset (`preset_fingerprint`).
- B?t bi?n: AI kh?ng ???c t? t?o h? layout m?i ngo?i 5 preset ?? ???c ph? duy?t (`FR-PRS-005`).

### 4.3. ??ng g?i Render Package b?t bi?n (CT-RND-002, CT-RND-003)
- **`CT-RND-002` (`ResolveRenderPackage`):**
  - T?ng h?p ProductionSnapshot, k?ch b?n, k? ho?ch, preset revision, voice track, word timing, media/hook/thumbnail/music/SFX refs, language validation refs, output profile revision, job grant.
  - T?o `RenderPackage` b?t bi?n ch?a exact artifact version/hash/size/type c?a m?i ??u v?o, timeline resolved, v? tr? visual hook, audio hook, thumbnail placement, c?u h?nh subtitle burn-in, mix plan v? `package_fingerprint`.
  - B?t bi?n: Thay ??i b?t k? hash ??u v?o n?o ??u l?m thay ??i `package_fingerprint` (`INV-011`). G?i kh?ng ch?a URL t?y ? ho?c ???ng d?n shell do AI cung c?p.
- **`CT-RND-003` (`ValidateRenderPackage` - 9 Ti?n ?? c?ng):**
  1. C? visual hook.
  2. C? audio hook.
  3. C? thumbnail v?i time range n?m ho?n to?n trong time range c?a hook (0?3 gi?y ??u) (`INV-020`, `R08`).
  4. C? exact voice v? word timing t??ng th?ch v?i script version v? voice hash.
  5. C? b?ng ch?ng ng?n ng? ti?ng Anh g?n ??ng script, voice, subtitle v? output metadata revisions.
  6. C? ?t nh?t m?t visual asset cho m?i kho?ng timeline y?u c?u.
  7. M?i artifact local c?n thi?t ?? ???c ki?m ch?ng hash SHA-256.
  8. ???ng d?n output ???c Ph?n h? I c?p, n?m trong staging root ???c ph?p.
  9. Preset v? n?ng l?c c?ng c? (FFmpeg toolchain) t??ng th?ch.
  - Thi?u b?t k? ?i?u ki?n n?o ph?i tr? l?i ngay l?p t?c tr??c khi th?c hi?n render n?ng.

### 4.4. Th?c thi Render video v? x? l? s? c? (CT-RND-004, INV-009, LOCK-DESKTOP-GPU)
- **Quy tr?nh:**
  - Nh?n RenderPackage b?t bi?n, xin c?p GPU slot lease (`LOCK-DESKTOP-GPU`, t?i ?a 2 slot ??ng th?i).
  - Th?c thi l?nh render th?ng qua FFmpeg subprocess v?i tham s? ???c chu?n h?a v? redacted (c?m n?i chu?i shell t?y ti?n).
  - Ghi nh?n `RenderAttempt` k?m wall time, CPU/GPU metrics, peak disk usage, warnings v? receipt.
  - X?a s?ch to?n b? t?p t?m (temporary clips, audio chunks) sau khi render ho?n t?t; ch? l?u l?i file MP4 ho?n ch?nh v? thumbnail JPEG (`INV-009`).
  - Tr??ng h?p crash/timeout d?n ??n `OUTCOME_UNKNOWN`: Ph?i th?c hi?n probe/reconcile t?p tr?n ??a tr??c khi quy?t ??nh th? l?i.
  - B?t bi?n: Render th?nh c?ng k? thu?t ch?a ??ng ngh?a v?i video ?? ho?n th?nh.

### 4.5. Ki?m ??nh ch?t l??ng t? ??ng 13 Gates (CT-QC-001, CT-QC-002, R11..R13, Gate G02, G07)
B?o c?o `QualityReport` th?m ??nh t? ??ng 13 c?ng ch?t l??ng:

| M? C?ng (QC Gate) | Ph?n Lo?i | ?i?u Ki?n Th?m ??nh B?t Bu?c | Invariant / Ref |
|---|---|---|---|
| `FILE_PLAYABLE` | Hard Gate | Probe v? decode ???c video MP4 ho?n ch?nh kh?ng l?i | `FR-REN-003` |
| `DURATION_RANGE` | Hard Gate | Th?i l??ng video ch?nh x?c n?m trong kho?ng **61?70 gi?y** | `INV-002`, `FR-REN-002` |
| `VISUAL_HOOK_PRESENT` | Hard Gate | Visual hook th?c s? xu?t hi?n trong video | `FR-REN-004`, `INV-020` |
| `AUDIO_HOOK_PRESENT` | Hard Gate | Audio hook th?c s? nghe ???c v? ???c mix trong v?ng hook | `FR-REN-004`, `INV-020` |
| `THUMBNAIL_PRESENT` | Hard Gate | Thumbnail li?n quan xu?t hi?n v? n?m trong 0?3 gi?y ??u | `INV-020`, `FR-REN-004` |
| `SUBTITLE_BURNED_IN` | Hard Gate | Ph? ?? ???c burn-in tr?c ti?p v?o khung h?nh video | `FR-REN-008` |
| `KARAOKE_TIMING_VALID` | Hard Gate | Ch? ??i m?u karaoke ch?nh x?c theo t?ng t? WordTiming | `INV-007`, `FR-REN-008` |
| `VOICE_AUDIBLE` | Hard Gate | Gi?ng ??c r? r?ng, kh?ng b? m?o ti?ng ho?c l?i ?m thanh | `FR-AUD-001`, `FR-AUD-006` |
| `ENGLISH_OUTPUT_VALID` | Hard Gate | Script, voice, subtitle, title v? hashtag c? b?ng ch?ng ti?ng Anh g?n ??ng revision | `CT-QC-001`, `CT-QC-002` |
| `OUTPUT_PROFILE_VALID` | Hard Gate | ?? ph?n gi?i ??ng 1080x1920 (9:16 d?c), 30fps, H.264/AAC | `INV-001`, `R11` |
| `INFERENCE_DISCLOSURE_PRESENT` | Hard (c? ?i?u ki?n) | C?c ?o?n suy lu?n/s?ng t?o c? bi?u ??t r? r?ng trong video | `CT-QC-001` |
| `VISUAL_CONTINUITY` | Warning / Score | Kh?ng c? kho?ng tr?ng ?en ho?c khung h?nh l?i ??ng k? | `CT-QC-001` |
| `AUDIO_MIX_QUALITY` | Warning / Score | Voice, nh?c n?n v? SFX h?a ?m ??t m?c ch?p nh?n (-14 LUFS) | `CT-QC-001`, `R09` |

- B?t bi?n: B?t k? Hard Gate n?o th?t b?i th? video b? t? ch?i xu?t x??ng (`INV-018`). QC kh?ng kh?ng ??nh s? th?t n?i dung; QC th?m ??nh t?nh ??y ?? k? thu?t v? t?nh nh?t qu?n v?i package/script.

### 4.6. ?i?u ki?n chuy?n giao v? ??t t?n t?p (CT-RND-005, CT-RND-006)
- **`CT-RND-005` (`RenderOutputReady`):** Ph?n h? F ch? th?ng b?o output ready cho Orchestration khi:
  1. Render receipt ? tr?ng th?i `succeeded`.
  2. Artifact ??u ra t?n t?i v? kh?p m? b?m SHA-256.
  3. B?o c?o `QualityReport` c? t?t c? Hard Gate ??t `PASS`.
  4. Report v? artifact refs ?? ???c commit v?o PostgreSQL.
  5. Fencing token / execution grant v?n c?n hi?u l?c.
- **`CT-RND-006` (`OutputNamingIntent`):**
  - T?n t?p ???c sanitize an to?n tr?n h? ?i?u h?nh Windows, gi? nguy?n display title v? hashtags g?c trong metadata.
  - T?n th? m?c theo ng?y `YY-MM-DD` theo phi?n l?m vi?c, ch? tr? th?nh th? m?c h?p l? khi c? ?t nh?t m?t video ho?n th?nh.

---

## 5. Ranh Gi?i Giao Ti?p Li?n Ph?n H? (Key Inter-Module Boundaries)

### 5.1. Ranh gi?i S?ng t?o -> S?n xu?t: `interface_d_e_f`
- H?p ??ng: `CONTRACT-CREATIVE-AI` (`CT-AI-004`, `CT-AI-007`), `CONTRACT-MEDIA-PROCESSING` (`CT-TTS-001`), `CONTRACT-RENDER-QUALITY` (`CT-RND-001`, `CT-RND-002`).
- Ph?n ??nh: Module D b?n giao k?ch b?n ho?n ch?nh k?m ch? d?n ph?t ?m cho Module E; Module D b?n giao ProductionPlan chi ti?t cho Module F.
- B?t bi?n: E v? F ch? thi h?nh theo k? ho?ch c?a D; F kh?ng t? ? ho?n ??i k?ch b?n hay t?i nguy?n ngo?i fallback plan.

### 5.2. Ranh gi?i ?m thanh -> D?ng h?nh: `interface_e_f`
- H?p ??ng: `CONTRACT-MEDIA-PROCESSING` (`CT-SUB-001`, `CT-AUD-001`) v? `CONTRACT-RENDER-QUALITY` (`CT-RND-002`).
- Ph?n ??nh: Module E chuy?n giao file `VoiceTrack` ho?n ch?nh v? danh s?ch `WordTiming` ch?nh x?c t?ng t? cho Module F.
- B?t bi?n: Module F s? d?ng `WordTiming` ?? t?nh to?n filter complex v? ph? ?? karaoke ch?y ch? ??i m?u; sai l?ch voice hash l?p t?c ch?n render.

### 5.3. Ranh gi?i C?u h?nh & Secret: `interface_e_j` v? `interface_f_j`
- H?p ??ng: `CONTRACT-CONFIG-SECURITY` (`CT-AI-ROUTE-001`, `CT-CFG-001`).
- Ph?n ??nh: Module E g?i engine TTS qua route adapter c?a Module J; Module F ti?p nh?n c?u h?nh 5 preset t? Module J.
- B?t bi?n: Module E v? F kh?ng n?m gi? API keys ho?c secret d?ng plain-text.

### 5.4. Ranh gi?i Qu?n l? T?p & L?u tr? Cloud: `interface_e_i` v? `interface_f_i`
- H?p ??ng: `CONTRACT-STORAGE` (`CT-STO-001..004`).
- Ph?n ??nh: Module I c?p ???ng d?n staging c?c b?, materialize t?p ??u v?o, x?c th?c m? b?m SHA-256 sau khi render, v? th?c hi?n ??ng b? l?n Google Drive.
- B?t bi?n: Kh?ng output c?c b? n?o ???c x?a tr??c khi Google Drive x?c nh?n ??ng b? th?nh c?ng.

### 5.5. Ranh gi?i ?i?u ph?i & C?p quy?n: `interface_g_e_f`
- H?p ??ng: `CONTRACT-ORCHESTRATION` (`CT-ORC-003`, `CT-ORC-004`), `CONTRACT-WORKFLOW-EXECUTION` (`CT-WF-001`), `CONTRACT-STATE-MACHINES` (`CT-STATE-008`).
- Ph?n ??nh: Module G ?i?u ph?i stage run, c?p execution grant, ph?n b? slot GPU (`LOCK-DESKTOP-GPU`), v? commit `CompletionLedger` sau khi Ph?n h? I x?c th?c cloud sync.

---

## 6. M?y Tr?ng Th?i C?t L?i (Bound State Machines - CONTRACT-STATE-MACHINES)

### 6.1. V?ng ??i X? l? ?m thanh & Timing (Module E)
- **VoiceTrack Lifecycle:** `INITIATED` -> `SYNTHESIZING` -> `NORMALIZING_LUFS` -> `READY` | `FAILED`.
- **WordTiming Lifecycle:** `PENDING_VOICE` -> `ALIGNING` -> `VERIFYING_MONOTONIC` -> `READY` | `INVALIDATED` | `FAILED`.
- **Image Safety Lifecycle:** `PROBING` -> `EVALUATING` -> `SAFE` | `TRANSFORMING` -> `TRANSFORMED_READY` | `UNCERTAIN` | `DETECTION_FAILED` | `TRANSFORM_FAILED` | `UNREADABLE`.

### 6.2. V?ng ??i Render Video & Ki?m ??nh QC (Module F)
- **RenderAttempt Lifecycle:** `PACKAGE_RESOLVED` -> `GPU_SLOT_ACQUIRED` -> `FFMPEG_RENDERING` -> `QC_INSPECTING` -> `SUCCEEDED` | `QC_FAILED` | `RENDER_FAILED` | `OUTCOME_UNKNOWN`.
- **Outcome-Unknown Reconciliation:** Khi worker crash ho?c timeout, h? th?ng probe file tr?n ??a; n?u video t?n t?i v? verify hash th?nh c?ng th? chuy?n ti?p sang QC, ng??c l?i gi?i ph?ng t?i nguy?n v? ??nh d?u th?t b?i c? th? retry.
- **Video Completion Gate:** `RENDER_READY` -> `DRIVE_SYNC_VERIFIED` -> `COMPLETION_LEDGER_COMMITTED` -> `COMPLETED`.

---

## 7. K?t Lu?n Kh?a B?t Bi?n

To?n b? 13 h?p ??ng giao ti?p n?n t?ng, 11 ?i?u kho?n giao di?n c?a `CONTRACT-MEDIA-PROCESSING` (`CT-PROC-001..008`, `CT-TTS-001`, `CT-SUB-001`, `CT-AUD-001`), 6 ?i?u kho?n giao di?n c?a `CONTRACT-RENDER-QUALITY` (`CT-RND-001..006`, `CT-QC-001..002`), 13 c?ng th?m ??nh ch?t l??ng t? ??ng, c?c ranh gi?i li?n ph?n h? D-E-F, E-F, E/F-J, E/F-I, G-E-F v? c?c m?y tr?ng th?i c?t l?i ?? ???c ??ng b?ng c? ??nh v?i ??y ?? m? b?m SHA-256 x?c th?c. Nghi?m c?m m?i h?nh vi t? ? s?a ??i l?m sai l?ch baseline ?? ???c ph? duy?t.

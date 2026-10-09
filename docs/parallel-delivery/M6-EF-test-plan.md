# K? Ho?ch Ki?m Th? To?n Di?n: M6-EF (Comprehensive Test Plan Specification)

> **M? g?i (Package ID):** `M6-EF`
> **Tr?ng th?i:** `planned_test_strategy`
> **T?i li?u ngu?n:** `docs/10-test-strategy.md` (M?c 12, 13, 23, 29), `docs/11-roadmap.md` (M?c 12), `docs/parallel-delivery/acceptance-matrix.yaml` (R09..R13, Gates G02, G06, G07)
> **Ph??ng ph?p lu?n:** Test-First / Behavioral TDD (`SPEC` -> `PLAN` -> `RED` -> `IMPLEMENT` -> `GREEN` -> `VERIFY` -> `EVIDENCE`)

---

## 1. Nguy?n T?c & K? Lu?t Ki?m Th? B?t Bu?c

1. **Ch?ng ki?n h?ng h?c h?nh vi (Behavioral RED First):**
   - Tr??c khi vi?t m? s?n ph?m, m?i ca ki?m th? ph?i ch?y v? th?t b?i v? vi ph?m assertions nghi?p v?/h?p ??ng (`Behavioral RED`), tuy?t ??i kh?ng ch?p nh?n RED do l?i import, l?i c?u h?nh m?i tr??ng, ho?c thi?u binary c?ng c? (`Invalid Setup Failure`).
2. **Ki?m th? tr?n Disposable DB & C?p Ph?t GPU Lease Th?t:**
   - S? d?ng database t?m th?i ri?ng bi?t (`function-scoped disposable database`), t? ??ng d?n d?p s?ch s? sau khi ch?y xong (`0 orphan databases`).
   - Ki?m ch?ng c? ch? gi?i h?n dung l??ng GPU slot lease (`LOCK-DESKTOP-GPU`, t?i ?a 2 slot ??ng th?i qua LeaseManager); t? ch?i y?u c?u th? 3 v? gi?i ph?ng slot ngay khi ho?n t?t ho?c l?i.
3. **M?i Tr??ng Offline Test Fixtures & Stub TTS Adapter:**
   - C?c b?i ki?m th? unit/local s? d?ng b? fixtures ?m thanh m?u (WAV/MP3), k?ch b?n m?u ti?ng Anh, v? deterministic stub TTS adapter m? ph?ng ch?nh x?c ph?n h?i ?m thanh v? metadata.
   - Ki?m th? x?c minh h? th?ng ho?t ??ng ?n ??nh ? ch? ?? offline, kh?ng ph? thu?c v?o k?t n?i m?ng ngo?i.
4. **C?m D?ng Mock ?? V??t Qua C?ng An To?n & To?n V?n:**
   - Tuy?t ??i kh?ng mock thu?t to?n ki?m tra th?i l??ng nghi?m ng?t 61?70 gi?y (`INV-002`), c?n ch?nh m?c th?i gian t?ng ??n ?i?u (`INV-007`), thumbnail n?m trong v?ng hook 0?3s (`INV-020`), ho?c 13 c?ng ki?m ??nh ch?t l??ng t? ??ng (`CT-QC-001`).
5. **K? Lu?t Targeted Test (Zero Waste Execution):**
   - Trong qu? tr?nh ph?t tri?n v? s?a l?i, ch? ch?y ??ng l?nh ki?m th? m?c ti?u ???c ch? ??nh; ch? ch?y to?n b? b? ki?m th? t?ch h?p khi b??c v?o giai ?o?n t?ng h?p h? s? evidence.

---

## 2. Danh M?c C?c Test Oracle B?t Bu?c (Mandatory Test Oracles)

### 2.1. Nh?m Ph?n H? E ? Probe, Ph?n T?ch & An To?n H?nh ?nh (CT-PROC-003..006, R25)

| M? Ki?m Th? | T?nh hu?ng k?ch ho?t (Scenario) | H?nh vi mong ??i & Oracle b?t bu?c (Expected Oracle) |
|---|---|---|
| `TST-MED-PRB-001` | Probe t?p media ??u v?o (video/audio/image) c? ??nh d?ng v? codec kh?c nhau | B?c t?ch ch?nh x?c container, video/audio streams, duration, dimensions, frame rate, sample rate, pixel format; ph?t hi?n file h?ng fail-closed; kh?ng tin extension gi? m?o (`CT-PROC-003`) |
| `TST-MED-SAF-001` | ??nh gi? an to?n ?nh ngu?n v? thumbnail theo ch?nh s?ch R25 (`AssessImageSafety`) | Tr? v? ??ng c?c tr?ng th?i `SAFE`, `TRANSFORM_REQUIRED`, `UNCERTAIN`, `DETECTION_FAILED`, `TRANSFORM_FAILED`, `UNREADABLE`. R25: ?nh ??c ???c v?n c? th? d?ng k?m warning/l?i; kh?ng ch?n ?nh n?u t?p ??c ???c; tuy?t ??i kh?ng ?p d?ng x? l? nh?y c?m cho video clips (`CT-PROC-005`, `CT-PROC-006`, `R25`) |
| `TST-MED-NRM-001` | Chu?n h?a media (`NormalizeMedia`): crop, resize 9:16 d?c, pad, transcode | Gi? nguy?n t?p g?c; t?o rendition m?i c? lineage ??y ??; kh?ng crop m?t ch? th? ngo?i focus rule trong k? ho?ch; chuy?n ??i c? t?nh x?c ??nh deterministic (`CT-PROC-007`) |

---

### 2.2. Nh?m Ph?n H? E ? Gi?ng ??c TTS, Word Timing & ?m Thanh N?n (CT-TTS-001, CT-SUB-001, CT-AUD-001, R09, R10, INV-007, INV-008, INV-010, INV-019)

| M? Ki?m Th? | T?nh hu?ng k?ch ho?t (Scenario) | H?nh vi mong ??i & Oracle b?t bu?c (Expected Oracle) |
|---|---|---|
| `TST-VOI-TTS-001` | G?i t?ng h?p gi?ng ??c ti?ng Anh (`CreateVoiceTrack`) v?i k?ch b?n chu?n | Voice artifact sinh ra g?n exact script fingerprint; th?i l??ng th?c t? ph?i t??ng th?ch gi?i h?n 61?70 gi?y; l?u tr? d??i d?ng per-video artifact c? th? cleanup (`CT-TTS-001`, `R09`, `INV-008`, Gate G06) |
| `TST-VOI-TIM-001` | C?n ch?nh m?c th?i gian t?ng t? (`CreateWordTiming`) t? script v? voice artifact | Danh s?ch m?c th?i gian t?ng ??n ?i?u kh?ng ?m (`start_ms < end_ms` v? `start_ms[i+1] >= start_ms[i]`); n?m tr?n trong th?i l??ng voice; kh?ng c? m?c th?i gian ??o ng??c (`INV-007`, `CT-SUB-001`, `R10`) |
| `TST-VOI-TIM-002` | Ki?m tra ?? ph? t? ng? c?a WordTiming so v?i k?ch b?n g?c | ?? ph? ??t 100%, kh?ng ???c b? s?t b?t k? t? n?o c?a k?ch b?n (`INV-019`, `CT-SUB-001`) |
| `TST-VOI-INV-001` | Thay ??i script version ho?c voice hash c?a m?t job ?? c? WordTiming | To?n b? timing h? ngu?n b? v? hi?u h?a (invalidated) ngay l?p t?c; ch?n render v?i timing c? l?ch hash (`INV-010`) |
| `TST-VOI-BED-001` | Chu?n b? ?m thanh n?n (`PrepareAudioBed`) g?m nh?c n?n v? SFX | Rendition ?m thanh ??t chu?n ?m l??ng EBU R128 (-14 ??n -16 LUFS); h?a ?m c?n b?ng kh?ng l?m m?t kh? n?ng nghe hi?u l?i d?n (`CT-AUD-001`, `FR-AUD-006`) |

---

### 2.3. Nh?m Ph?n H? F ? Preset Engine & Render Package Validation (CT-RND-001..003, INV-011, INV-020, FR-PRS-001..005)

| M? Ki?m Th? | T?nh hu?ng k?ch ho?t (Scenario) | H?nh vi mong ??i & Oracle b?t bu?c (Expected Oracle) |
|---|---|---|
| `TST-RND-PRS-001` | Kh?i t?o v? th?m ??nh 5 nh?m preset phong c?ch video chu?n | M?i preset c? revision, preset fingerprint, quy t?c visual rhythm, layout, subtitle karaoke, thumbnail overlay; AI kh?ng ???c t? t?o layout ngo?i 5 preset n?y (`CT-RND-001`, `FR-PRS-001..005`) |
| `TST-RND-PKG-001` | ??ng g?i RenderPackage b?t bi?n (`ResolveRenderPackage`) t? inputs | RenderPackage ch?a exact artifact version/hash/size/type c?a m?i ??u v?o; thay ??i b?t k? hash ??u v?o n?o l?m thay ??i package fingerprint (`INV-011`, `CT-RND-002`) |
| `TST-RND-VAL-001` | Ki?m tra 9 ti?n ?? c?ng tr??c khi render (`ValidateRenderPackage`) | Thi?u visual hook, audio hook, thumbnail n?m ngo?i 0?3s, l?ch voice/timing hash, ho?c thi?u b?ng ch?ng ti?ng Anh -> l?p t?c tr? l?i fail-closed tr??c khi render n?ng (`CT-RND-003`, `INV-020`) |

---

### 2.4. Nh?m Ph?n H? F ? Quy Tr?nh D?ng FFmpeg, Karaoke & Thu D?n (CT-RND-004, LOCK-DESKTOP-GPU, R11, R12, INV-001, INV-009, INV-020)

| M? Ki?m Th? | T?nh hu?ng k?ch ho?t (Scenario) | H?nh vi mong ??i & Oracle b?t bu?c (Expected Oracle) |
|---|---|---|
| `TST-RND-RUN-001` | Th?c thi quy tr?nh render video qua FFmpeg subprocess v?i GPU slot lease | Xin c?p lease `LOCK-DESKTOP-GPU` th?nh c?ng; video xu?t ra ??ng ?? ph?n gi?i 1080x1920 (9:16 d?c), 30fps, codec H.264/AAC (`INV-001`, `CT-RND-004`, `LOCK-DESKTOP-GPU`, `R11`) |
| `TST-RND-SUB-001` | Burn-in ph? ?? ti?ng Anh v? hi?u ?ng karaoke ??i m?u theo t?ng t? | Ch? ??i m?u highlight ch?nh x?c theo m?c WordTiming tr?n t?ng frame video; ph? ?? n?m trong v?ng an to?n hi?n th? (`CT-RND-004`, `R12`, `FR-REN-008`) |
| `TST-RND-THM-001` | Tr?ch xu?t thumbnail JPEG t? khung h?nh video | Thumbnail ???c tr?ch xu?t t? khung h?nh n?m trong 0?3 gi?y ??u (v?ng hook), t? l? 9:16 ch?t l??ng cao (`INV-020`, `CT-RND-004`, `R08`) |
| `TST-RND-CLN-001` | Thu d?n sau khi render ho?n t?t ho?c khi render th?t b?i gi?a ch?ng | X?a s?ch to?n b? t?p t?m (temporary clips, audio chunks) tr?n ??a; gi?i ph?ng slot GPU ngay l?p t?c; ch? gi? l?i file MP4 ho?n ch?nh v? thumbnail (`INV-009`) |
| `TST-RND-REC-001` | X? l? s? c? outcome-unknown khi worker crash ho?c timeout | Probe file tr?n ??a; n?u file MP4 t?n t?i v? verify hash th?nh c?ng th? ti?p t?c sang QC; n?u h?ng/thi?u th? gi?i ph?ng t?i nguy?n v? cho ph?p retry (`CT-RND-004`) |

---

### 2.5. Nh?m Ph?n H? F ? Ki?m ??nh Ch?t L??ng T? ??ng (QC Gate - 13 Gates) (CT-QC-001, CT-QC-002, R13, INV-002, INV-018, Gate G02, G07)

| M? Ki?m Th? | T?nh hu?ng k?ch ho?t (Scenario) | H?nh vi mong ??i & Oracle b?t bu?c (Expected Oracle) |
|---|---|---|
| `TST-RND-QC-001` | Th?m ??nh video th?nh ph?m qua 13 c?ng ch?t l??ng (`InspectOutput`) | B?o c?o `QualityReport` ghi nh?n chi ti?t t?ng gate; video ch? ??t khi to?n b? Hard Gates ??t PASS (`CT-QC-001`, `CT-QC-002`, `INV-018`, `R13`, Gate G02, G07) |
| `TST-RND-QC-002` | Th?m ??nh video c? th?i l??ng d??i 61 gi?y ho?c tr?n 70 gi?y | Gate `DURATION_RANGE` tr? v? FAILED; video b? t? ch?i xu?t x??ng fail-closed (`INV-002`, `CT-QC-001`) |
| `TST-RND-QC-003` | Th?m ??nh video thi?u visual hook, thi?u audio hook, ho?c thumbnail ngo?i 0?3s | Gate `VISUAL_HOOK_PRESENT`, `AUDIO_HOOK_PRESENT` ho?c `THUMBNAIL_PRESENT` tr? v? FAILED; video b? t? ch?i xu?t x??ng (`INV-020`, `CT-QC-001`) |
| `TST-RND-QC-004` | Th?m ??nh video thi?u ho?c l?ch revision b?ng ch?ng ti?ng Anh | Gate `ENGLISH_OUTPUT_VALID` tr? v? FAILED; metadata t? khai `language=en` kh?ng ?? ?? pass (`CT-QC-001`, `CT-QC-002`) |

---

### 2.6. Nh?m T?ch H?p EF & B?n Giao Ho?n T?t (EF7, CT-RND-005, CT-RND-006)

| M? Ki?m Th? | T?nh hu?ng k?ch ho?t (Scenario) | H?nh vi mong ??i & Oracle b?t bu?c (Expected Oracle) |
|---|---|---|
| `TST-EF-INT-001` | T?ch h?p quy tr?nh E-F ho?n ch?nh t? k?ch b?n ??n video alpha (`R4 Video Alpha`) | Th?c hi?n tu?n t? c?c stage probe, TTS, word timing, render package, FFmpeg render, QC report; t?o ra 1 video alpha h?p l? theo lu?ng gi?m s?t (`docs/11-roadmap.md`) |
| `TST-EF-CMP-001` | Ph?i h?p chuy?n giao `RenderOutputReady` v? ki?m tra an to?n ??t t?n t?p | T?n t?p sanitize an to?n tr?n Windows; b?n giao cho Storage (Module I) ??ng b? Google Drive; G ch? commit CompletionLedger sau khi cloud sync verified (`CT-RND-005`, `CT-RND-006`) |

---

## 3. Quy Tr?nh & L?nh Ki?m Th? M?c Ti?u (Targeted Test Commands)

Tu?n th? nguy?n t?c Zero Waste Execution: Worker ch? ch?y ??ng targeted test ???c giao, tuy?t ??i kh?ng t? ? ch?y full suite tr? khi c? y?u c?u `fullSuiteRequired: true`.

| Nh?m Ki?m Th? | L?nh Ki?m Th? M?c Ti?u Chu?n (Targeted Command) |
|---|---|
| **E1 Probe & Analyze** | `python -m unittest tests/unit/voice/test_media_probe.py -k test_probe_media_streams` |
| **E2 Image Safety R25** | `python -m unittest tests/unit/voice/test_image_safety.py -k test_safety_filter_r25` |
| **E3 TTS Voice Synthesis** | `python -m unittest tests/unit/voice/test_tts_synthesis.py -k test_voice_duration_61_70s` |
| **E4 Word Timing Alignment** | `python -m unittest tests/unit/voice/test_word_timing_alignment.py -k test_monotonic_timestamps` |
| **E5 Audio Bed & SFX** | `python -m unittest tests/unit/voice/test_audio_bed.py -k test_ebu_r128_loudness` |
| **F1 5-Preset Engine** | `python -m unittest tests/unit/render/test_preset_engine.py -k test_five_presets_specification` |
| **F2 Render Package Validation** | `python -m unittest tests/unit/render/test_render_package.py -k test_nine_hard_preconditions` |
| **F3 FFmpeg Render Pipeline** | `python -m unittest tests/unit/render/test_video_pipeline.py -k test_ffmpeg_render_execution` |
| **F4 Subtitle Karaoke Burn-in** | `python -m unittest tests/unit/render/test_karaoke_subtitle.py -k test_karaoke_filter_complex` |
| **F5 QC Inspection 13 Gates** | `python -m unittest tests/unit/render/test_qc_verification.py -k test_thirteen_quality_gates` |
| **F6 Completion Handshake** | `python -m unittest tests/unit/render/test_completion_handshake.py -k test_render_output_ready` |
| **Static Plan Validation** | `python docs/parallel-delivery/validate-docs-plan.py` |

---

## 4. Ma Tr?n C?ng Ch?t L??ng & Ph? Duy?t Xu?t X??ng (Quality Release Gates)

| M? C?ng (Gate) | T?n C?ng Nghi?p V? | Ti?u Chu?n Nghi?m Thu C? Th? | Ph?n H? Ph? Tr?ch |
|---|---|---|---|
| **Gate G02** | Throughput & Render Pipeline Metrics | Render video MP4 1080x1920 30fps ??ng chu?n; d?n d?p nguy?n t? t?p t?m; tu?n th? h?n ng?ch 2 slot GPU | Ph?n h? F |
| **Gate G06** | AI Voice & Word Timing Quality | TTS voice t? nhi?n g?n script fingerprint; WordTiming t?ng ??n ?i?u; ?? ph? 100%; EBU R128 loudness | Ph?n h? E |
| **Gate G07** | Compatibility, Output Profile & QC | 100% video xu?t x??ng ??t t?t c? Hard Gates trong QualityReport (ph?t ???c, 61?70s, hook, thumbnail 0?3s, karaoke) | Ph?n h? F |

---

## 5. B?ng Ch?ng B?t Bu?c Khi Ho?n T?t G?i (Evidence Requirements)

Khi ho?n t?t g?i c?ng vi?c ho?c to?n b? M6-EF, h? s? nghi?m thu b?t bu?c ph?i ch?a c?c t?p tin c? m? b?m x?c th?c:

```json
{
  "milestone": "M6",
  "package_id": "M6-EF",
  "evidence_version": "1.0.0",
  "timestamp": "2026-10-09T00:00:00Z",
  "test_execution_summary": {
    "total_tests": 18,
    "passed": 18,
    "failed": 0,
    "skipped": 0
  },
  "invariant_attestation": {
    "INV-001": "VERIFIED_EXACT_RESOLUTION_1080X1920",
    "INV-002": "VERIFIED_DURATION_61_70S",
    "INV-007": "VERIFIED_MONOTONIC_WORD_TIMINGS",
    "INV-008": "VERIFIED_AUDIO_DURATION_MATCH",
    "INV-009": "VERIFIED_ATOMIC_RENDER_CLEANUP",
    "INV-010": "VERIFIED_DOWNSTREAM_TIMING_INVALIDATION",
    "INV-011": "VERIFIED_IMMUTABLE_RENDER_PACKAGE_FINGERPRINT",
    "INV-018": "VERIFIED_QC_HARD_GATES_ENFORCED",
    "INV-019": "VERIFIED_FULL_SCRIPT_WORD_COVERAGE",
    "INV-020": "VERIFIED_THUMBNAIL_IN_HOOK_0_3S"
  },
  "quality_release_gates": {
    "G02": "PASSED",
    "G06": "PASSED",
    "G07": "PASSED"
  },
  "open_decision_gates": {
    "GATE-M6-E-INTEGRATION-PATH": "BLOCKED_PENDING_AUTHORITY_REGISTRATION",
    "GATE-M6-F-INTEGRATION-PATH": "BLOCKED_PENDING_AUTHORITY_REGISTRATION",
    "USER-CKPT-M6": "BLOCKED_PENDING_USER_APPROVAL"
  }
}
```

---

## 6. Ti?u Chu?n Nghi?m Thu Ho?n Th?nh (Definition of Done)

G?i c?ng vi?c M6-EF ch? ???c xem l? ho?n t?t khi:
1. To?n b? 18 test oracles ??t tr?ng th?i `PASS` tr?n m?i tr??ng ki?m th? c? l?p.
2. Kh?ng ph?t hi?n b?t k? vi ph?m n?o ??i v?i c?c b?t bi?n `INV-001`, `INV-002`, `INV-007`, `INV-008`, `INV-009`, `INV-010`, `INV-011`, `INV-018`, `INV-019`, `INV-020`.
3. To?n b? 13 c?ng ki?m ??nh ch?t l??ng trong `QualityReport` ho?t ??ng x?c ??nh, lo?i b? video vi ph?m fail-closed.
4. Hai open gates `GATE-M6-E-INTEGRATION-PATH` v? `GATE-M6-F-INTEGRATION-PATH` c?ng `USER-CKPT-M6` ???c ghi nh?n r? r?ng v?i tr?ng th?i fail-closed cho t?i khi ???c c?p th?m quy?n.
5. H? s? b?ng ch?ng JSON ???c t?ng h?p ??y ?? v? x?c th?c m? b?m SHA-256.

# ??ng B?ng H?p ??ng Giao Ti?p: M3-A (Contract Freeze Specification)

> **M? g?i (Package ID):** `M3-A`
> **Tr?ng th?i ??ng b?ng:** `frozen_design_baseline`
> **Th?m quy?n quy ??nh:** CT-CMN-012, `docs/parallel-delivery/contract-registry.yaml`, `operating-model.md`
> **R?ng bu?c b?t bi?n:** B?t bu?c kh?p ch?nh x?c m? b?m SHA-256 ngu?n; sai m? b?m ho?c sai ngu?n ??nh ngh?a ph?i fail-closed.

---

## 1. Nguy?n T?c ??ng B?ng H?p ??ng (Contract Freeze Principles)

1. **Kh?a b?t bi?n (Immutable Baseline):** M?i c?ng vi?c chu?n b? v? tri?n khai t??ng lai c?a Ph?n h? A b?t bu?c ph?i d?a tr?n ??ng c?c phi?n b?n h?p ??ng ?? ???c ??ng b?ng d??i ??y.
2. **Fail-Closed khi sai l?ch:** N?u ph?t hi?n m? b?m t?p ngu?n th?c t? kh?c v?i m? b?m ?? ??ng b?ng, to?n b? chu tr?nh ki?m th? v? t?ch h?p ph?i d?ng ngay l?p t?c (`FAIL_CLOSED_CONTRACT_DRIFT`).
3. **C?m s?a t?p ngu?n h?p ??ng:** Nghi?m c?m m?i s?a ??i ??i v?i c?c t?p ngu?n trong `docs/09-contracts/**` trong ph?m vi c?a g?i n?y (`LOCK-CONTRACT-SOURCE`). M?i ?? xu?t thay ??i h?p ??ng ph?i th?ng qua quy tr?nh RFC / ADR ki?n tr?c c?p cao.

---

## 2. B?ng ??ng B?ng C?c H?p ??ng Li?n Quan (Exact Frozen Contract Revisions)

| M? H?p ??ng (Contract ID) | T?p Ngu?n ??nh Ngh?a (Defining Source) | Prefixes | Owner | Exact Frozen SHA-256 |
|---|---|---|---|---|
| `CONTRACT-SOURCE-CONTENT` | `docs/09-contracts/04-source-content-contracts.md` | `CT-SRC-*`, `CT-CNT-*` | A (Co-owner: B) | `61b075d202dd0d7729123f68f26285097be8120e2de48194d0ad2fe847701f31` |
| `CONTRACT-COMMON` | `docs/09-contracts/00-common-contract.md` | `CT-CMN-*` | CROSS-CUTTING | `dfdce8db13d5f1d1f286ccd233a66caf39f48552da2dbbad26692fde7be978e8` |
| `CONTRACT-STATE-MACHINES` | `docs/09-contracts/12-state-machines.md` | `CT-STATE-*` | CROSS-CUTTING | `2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28` |
| `CONTRACT-WORKFLOW-EXECUTION` | `docs/09-contracts/03-workflow-and-execution.md` | `CT-WF-*` | G | `0fca25f2bc037a4c2bc58b844079dace8c19a9fd5af5c0ce8ad75e421bc2dc83` |
| `CONTRACT-STORAGE` | `docs/09-contracts/10-storage-contracts.md` | `CT-STO-*` | I | `6ab6f60bc2760ea9017ca0406e0053dc859cc06c1f0c80fff7e944d03d5e02ce` |
| `CONTRACT-CONFIG-SECURITY` | `docs/09-contracts/11-configuration-security-contracts.md` | `CT-CFG-*`, `CT-SEC-*`, `CT-CAP-*`, `CT-AI-ROUTE-*` | J | `989d9ef22c2096f56453722f059efc1427a3018e64c1a7f67a8d514f55c69645` |

---

## 3. Chi Ti?t Giao Di?n CONTRACT-SOURCE-CONTENT (Bound to Ph?n H? A)

### 3.1. Qu?n l? ngu?n tin (Source Lifecycle Operations)
- **`CT-SRC-001` (`RegisterSource`):**
  - Input: `workspace_id`, `url` (canonical locator), `source_kind`, `tier`, `topics`, `collection_enabled`, `actor`, `idempotency_key`.
  - Output: `SourceRef`, `revision`, `url_validation_result`, `receipt`.
  - B?t bi?n: URL ph?i qua ki?m tra chu?n h?a v? SSRF policy. Ngu?n c? tombstone kh?ng ???c ??ng k? l?i (tr? v? conflict k?m tombstone ref). Kh?ng t? ??ng ??i Tier.
- **`CT-SRC-002` (`UpdateSourceMetadata`):**
  - Input: `source_id`, `expected_revision`, `tier`, `topics`, `notes`, `collection_enabled`, `actor`, `idempotency_key`.
  - Output: `SourceRef`, `new_revision`, `receipt`.
  - B?t bi?n: Kh?ng s?a d? li?u b?i vi?t l?ch s? ho?c quan h? s? ki?n.
- **`CT-SRC-003` (`RemoveSource` / `RestoreSource`):**
  - Remove: T?o `SourceTombstone`, d?ng m?i ho?t ??ng thu th?p, ch?n auto-discovery. Gi? nguy?n to?n b? d? li?u tin t?c/media ?? thu th?p tr??c ??.
  - Restore: Kh?i ph?c tr?ng th?i ho?t ??ng tr??c ?? n?u policy c?n cho ph?p; n?u kh?ng chuy?n v? `DISABLED`.
- **`CT-SRC-003A` (`EvaluateSourceCandidate` / `RegisterSourceCandidate`):**
  - Lifecycle: `DISCOVERED` ? `VALIDATING` ? `READY_FOR_REGISTRATION` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`.
  - ??ng k? candidate ki?m tra l?i canonical identity, source/tombstone v? policy trong c?ng m?t database transaction. N?u g?p tombstone tr? `BLOCKED_TOMBSTONE`; n?u ngu?n ?? t?n t?i tr? `MATCHED_EXISTING`.

### 3.2. L?p k? ho?ch v? chu k? thu th?p (Collection Cycle Operations)
- **`CT-SRC-004` (`PlanCollectionCycle`):**
  - Input: `business_date` (t?nh t? timezone revision ?? kh?a), `subject_groups`, `fresh_unique_article_target`, `source_snapshot`, `collection_policy_revision`.
  - Output: Danh s?ch ngu?n theo th? t? x?c ??nh, l? do ch?n/b? qua, ng??ng d?ng Tier, `cycle_id`.
  - Kh?a ??nh danh duy nh?t c?a l??t qu?t ??nh k?: `workspace_id + source_id + business_date + periodic`. Policy revision ch? l? metadata, ??i policy trong ng?y kh?ng m? l??t qu?t th? hai.
  - B?t bi?n: M?i ngu?n ???c qu?t ??nh k? t?i ?a 1 l?n/ng?y. Tier ti?p theo ch? m? khi s? tin m?i kh?ng tr?ng ch?a ??t ng??ng m?c ti?u.
- **`CT-SRC-005` (`CollectSource`):**
  - Input: `source_revision`, `collection_cycle_id`, `collection_run_id`, `fetch_policy_revision`, `cursor`, `deadline`.
  - Output: `CollectionRunResult` (`COMPLETED`, `COMPLETED_PARTIAL`, `FAILED_FINAL`), th?ng k? URL, document package refs, cursor m?i, redacted error logs.
  - Partial success kh?ng l?m m?t c?c package ?? commit. Cursor ch? ti?n qua c?c m?c ?? ghi nh?n b?n v?ng.

---

## 4. Chi Ti?t Giao Di?n B?n Giao: CollectedDocumentPackage (`CT-SRC-006`)

`CollectedDocumentPackage` l? phong b? d? li?u k? thu?t b?n giao t? Ph?n h? A sang Ph?n h? B (`interface_a_b`):

### 4.1. C?u tr?c Schema (Machine-Readable Contract)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CollectedDocumentPackage",
  "type": "object",
  "required": [
    "collected_document_id",
    "source_id",
    "source_revision",
    "collection_run_id",
    "requested_url",
    "final_url",
    "fetched_at",
    "http_observation",
    "extraction_disposition",
    "extractor_version",
    "provenance_chain",
    "warnings"
  ],
  "properties": {
    "collected_document_id": { "type": "string", "format": "uuid" },
    "source_id": { "type": "string", "format": "uuid" },
    "source_revision": { "type": "integer", "minimum": 1 },
    "collection_run_id": { "type": "string", "format": "uuid" },
    "requested_url": { "type": "string", "format": "uri" },
    "final_url": { "type": "string", "format": "uri" },
    "canonical_url_candidate": { "type": ["string", "null"], "format": "uri" },
    "fetched_at": { "type": "string", "format": "date-time" },
    "published_at_candidate": { "type": ["string", "null"], "format": "date-time" },
    "http_observation": {
      "type": "object",
      "required": ["status_code", "content_type", "safe_headers"],
      "properties": {
        "status_code": { "type": "integer" },
        "content_type": { "type": "string" },
        "safe_headers": { "type": "object" },
        "content_length": { "type": "integer" },
        "response_time_ms": { "type": "number" }
      }
    },
    "raw_snapshot_ref": { "type": ["string", "null"] },
    "extraction_disposition": {
      "type": "string",
      "enum": ["SUCCESS", "PARTIAL", "FAILED", "EMPTY_CONTENT"]
    },
    "extractor_version": { "type": "string" },
    "extracted_content_candidate": {
      "type": ["object", "null"],
      "properties": {
        "title": { "type": "string" },
        "text": { "type": "string" },
        "author": { "type": "string" },
        "language": { "type": "string" }
      }
    },
    "content_eligibility": {
      "type": "string",
      "enum": ["candidate", "incomplete"]
    },
    "eligibility_reason": { "type": ["string", "null"] },
    "content_fingerprints": {
      "type": "object",
      "properties": {
        "exact_sha256": { "type": "string" },
        "simhash": { "type": "string" }
      }
    },
    "media_discoveries": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["media_url", "media_type", "position_in_article"],
        "properties": {
          "media_url": { "type": "string", "format": "uri" },
          "media_type": { "type": "string", "enum": ["image", "video_clip", "audio"] },
          "position_in_article": { "type": "integer" },
          "alt_text": { "type": "string" },
          "provenance_ref": { "type": "string" }
        }
      }
    },
    "provenance_chain": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["step", "url", "timestamp"],
        "properties": {
          "step": { "type": "string", "enum": ["request", "redirect", "final_fetch", "extract"] },
          "url": { "type": "string", "format": "uri" },
          "timestamp": { "type": "string", "format": "date-time" },
          "sha256": { "type": "string" }
        }
      }
    },
    "warnings": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

### 4.2. Quy t?c Th?m tra Hai L?p (Two-Layer Validation Discipline)
1. **L?p 1 ? Ki?m tra C?u tr?c Schema (Structural Validation):**
   - Thi?u b?t k? tr??ng b?t bu?c n?o trong danh s?ch `required` -> T? ch?i ngay t?i bi?n Ph?n h? A v?i l?i `VALIDATION_ERROR`.
   - Tuy?t ??i kh?ng t?o b?n ghi `CollectedDocument`, kh?ng ??y event outbox sang B. Ghi nh?n nh?t k? l?i v?i correlation ID an to?n.
2. **L?p 2 ? Ki?m tra T?nh To?n V?n N?i Dung (Content Completeness):**
   - Package ??ng c?u tr?c schema nh?ng n?i dung r?ng (empty main text) ho?c tr?ch xu?t th?t b?i -> ??nh d?u `content_eligibility = "incomplete"` k?m l? do c? th?.
   - Khi chuy?n sang Ph?n h? B, B ti?p nh?n nh?ng tr? v? disposition `REJECTED_INCOMPLETE` theo CT-CNT-001; kh?ng t?o b?i vi?t m?i v? kh?ng t?o candidate k?ch b?n.

---

## 5. M?y Tr?ng Th?i C?t L?i (Bound State Machines ? CONTRACT-STATE-MACHINES)

### 5.1. V?ng ??i Ngu?n: `CT-STATE-001`
- ?? th? tr?ng th?i: `ACTIVE` ? `DISABLED` ? `REMOVED_TOMBSTONE`.
- B?t bi?n: T? `REMOVED_TOMBSTONE` ch? c? l?nh `RestoreSource` h?p l?. Ngu?n ?? remove c?m auto-discovery t?o m?i.

### 5.2. V?ng ??i L??t qu?t: `CT-STATE-002`
- Run:
  - `SCHEDULED` ? `RUNNING`.
  - `RUNNING` ? `WAITING_RETRY` ? `RUNNING`.
  - `RUNNING` ? `WAITING_RECONCILIATION` ? `RUNNING` ho?c tr?ng th?i terminal.
  - `RUNNING` ? `COMPLETED` | `COMPLETED_PARTIAL` | `FAILED_FINAL`.
- Attempt ghi nh?n: `SUCCEEDED`, `FAILED_RETRYABLE`, `FAILED_FINAL`, `OUTCOME_UNKNOWN`.
- B?t bi?n: `OUTCOME_UNKNOWN` kh?ng ???c t? ? retry m? ho?c t? k?t lu?n th?nh c?ng; b?t bu?c reconcile c? b?ng ch?ng.

### 5.3. V?ng ??i ?? xu?t Ngu?n (Candidate): `CT-STATE-002A`
- `DISCOVERED` ? `VALIDATING` ? `READY_FOR_REGISTRATION` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`.
- `READY_FOR_REGISTRATION` ? `REGISTERED` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`.
- B?t bi?n: Registration ki?m tra l?i nguy?n t? tombstone v? existing source trong c?ng transaction.

---

## 6. K?t Lu?n Kh?a B?t Bi?n

To?n b? 6 h?p ??ng n?n t?ng c?ng c?c quy t?c chuy?n ??i tr?ng th?i v? schema phong b? d? li?u ?? ???c kh?a c?ng. Kh?ng cho ph?p b?t k? thay ??i ??n ph??ng n?o l?m tr?i l?ch baseline ?? ???c ph? duy?t.

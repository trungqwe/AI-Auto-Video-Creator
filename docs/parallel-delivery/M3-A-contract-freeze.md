# Đóng Băng Hợp Đồng Giao Tiếp: M3-A (Contract Freeze Specification)

> **Mã gói (Package ID):** `M3-A`
> **Trạng thái đóng băng:** `frozen_design_baseline`
> **Thẩm quyền quy định:** CT-CMN-012, `docs/parallel-delivery/contract-registry.yaml`, `operating-model.md`
> **Ràng buộc bất biến:** Bắt buộc khớp chính xác mã băm SHA-256 nguồn; sai mã băm hoặc sai nguồn định nghĩa phải fail-closed.

---

## 1. Nguyên Tắc Đóng Băng Hợp Đồng (Contract Freeze Principles)

1. **Khóa bất biến (Immutable Baseline):** Mọi công việc chuẩn bị và triển khai tương lai của Phân hệ A bắt buộc phải dựa trên đúng các phiên bản hợp đồng đã được đóng băng dưới đây.
2. **Fail-Closed khi sai lệch:** Nếu phát hiện mã băm tệp nguồn thực tế khác với mã băm đã đóng băng, toàn bộ chu trình kiểm thử và tích hợp phải dừng ngay lập tức (`FAIL_CLOSED_CONTRACT_DRIFT`).
3. **Cấm sửa tệp nguồn hợp đồng:** Nghiêm cấm mọi sửa đổi đối với các tệp nguồn trong `docs/09-contracts/**` trong phạm vi của gói này (`LOCK-CONTRACT-SOURCE`). Mọi đề xuất thay đổi hợp đồng phải thông qua quy trình RFC / ADR kiến trúc cấp cao.

---

## 2. Bảng Đóng Băng Các Hợp Đồng Liên Quan (Exact Frozen Contract Revisions)

| Mã Hợp Đồng (Contract ID) | Tệp Nguồn Định Nghĩa (Defining Source) | Prefixes | Owner | Exact Frozen SHA-256 |
|---|---|---|---|---|
| `CONTRACT-SOURCE-CONTENT` | `docs/09-contracts/04-source-content-contracts.md` | `CT-SRC-*`, `CT-CNT-*` | A (Co-owner: B) | `61b075d202dd0d7729123f68f26285097be8120e2de48194d0ad2fe847701f31` |
| `CONTRACT-COMMON` | `docs/09-contracts/00-common-contract.md` | `CT-CMN-*` | CROSS-CUTTING | `dfdce8db13d5f1d1f286ccd233a66caf39f48552da2dbbad26692fde7be978e8` |
| `CONTRACT-STATE-MACHINES` | `docs/09-contracts/12-state-machines.md` | `CT-STATE-*` | CROSS-CUTTING | `2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28` |
| `CONTRACT-WORKFLOW-EXECUTION` | `docs/09-contracts/03-workflow-and-execution.md` | `CT-WF-*` | G | `0fca25f2bc037a4c2bc58b844079dace8c19a9fd5af5c0ce8ad75e421bc2dc83` |
| `CONTRACT-STORAGE` | `docs/09-contracts/10-storage-contracts.md` | `CT-STO-*` | I | `6ab6f60bc2760ea9017ca0406e0053dc859cc06c1f0c80fff7e944d03d5e02ce` |
| `CONTRACT-CONFIG-SECURITY` | `docs/09-contracts/11-configuration-security-contracts.md` | `CT-CFG-*`, `CT-SEC-*`, `CT-CAP-*`, `CT-AI-ROUTE-*` | J | `989d9ef22c2096f56453722f059efc1427a3018e64c1a7f67a8d514f55c69645` |

---

## 3. Chi Tiết Giao Diện CONTRACT-SOURCE-CONTENT (Bound to Phân Hệ A)

### 3.1. Quản lý nguồn tin (Source Lifecycle Operations)
- **`CT-SRC-001` (`RegisterSource`):**
  - Input: `workspace_id`, `url` (canonical locator), `source_kind`, `tier`, `topics`, `collection_enabled`, `actor`, `idempotency_key`.
  - Output: `SourceRef`, `revision`, `url_validation_result`, `receipt`.
  - Bất biến: URL phải qua kiểm tra chuẩn hóa và SSRF policy. Nguồn có tombstone không được đăng ký lại (trả về conflict kèm tombstone ref). Không tự động đổi Tier.
- **`CT-SRC-002` (`UpdateSourceMetadata`):**
  - Input: `source_id`, `expected_revision`, `tier`, `topics`, `notes`, `collection_enabled`, `actor`, `idempotency_key`.
  - Output: `SourceRef`, `new_revision`, `receipt`.
  - Bất biến: Không sửa dữ liệu bài viết lịch sử hoặc quan hệ sự kiện.
- **`CT-SRC-003` (`RemoveSource` / `RestoreSource`):**
  - Remove: Tạo `SourceTombstone`, dừng mọi hoạt động thu thập, chặn auto-discovery. Giữ nguyên toàn bộ dữ liệu tin tức/media đã thu thập trước đó.
  - Restore: Khôi phục trạng thái hoạt động trước đó nếu policy còn cho phép; nếu không chuyển về `DISABLED`.
- **`CT-SRC-003A` (`EvaluateSourceCandidate` / `RegisterSourceCandidate`):**
  - Lifecycle: `DISCOVERED` -> `VALIDATING` -> `READY_FOR_REGISTRATION` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`.
  - Đăng ký candidate kiểm tra lại canonical identity, source/tombstone và policy trong cùng một database transaction. Nếu gặp tombstone trả `BLOCKED_TOMBSTONE`; nếu nguồn đã tồn tại trả `MATCHED_EXISTING`.

### 3.2. Lập kế hoạch và chu kỳ thu thập (Collection Cycle Operations)
- **`CT-SRC-004` (`PlanCollectionCycle`):**
  - Input: `business_date` (tính từ timezone revision đã khóa), `subject_groups`, `fresh_unique_article_target`, `source_snapshot`, `collection_policy_revision`.
  - Output: Danh sách nguồn theo thứ tự xác định, lý do chọn/bỏ qua, ngưỡng dừng Tier, `cycle_id`.
  - Khóa định danh duy nhất của lượt quét định kỳ: `workspace_id + source_id + business_date + periodic`. Policy revision chỉ là metadata, đổi policy trong ngày không mở lượt quét thứ hai.
  - Bất biến: Mỗi nguồn được quét định kỳ tối đa 1 lần/ngày. Tier tiếp theo chỉ mở khi số tin mới không trùng chưa đạt ngưỡng mục tiêu.
- **`CT-SRC-005` (`CollectSource`):**
  - Input: `source_revision`, `collection_cycle_id`, `collection_run_id`, `fetch_policy_revision`, `cursor`, `deadline`.
  - Output: `CollectionRunResult` (`COMPLETED`, `COMPLETED_PARTIAL`, `FAILED_FINAL`), thống kê URL, document package refs, cursor mới, redacted error logs.
  - Partial success không làm mất các package đã commit. Cursor chỉ tiến qua các mốc đã ghi nhận bền vững.

---

## 4. Chi Tiết Giao Diện Bàn Giao: CollectedDocumentPackage (`CT-SRC-006`)

`CollectedDocumentPackage` là phong bì dữ liệu kỹ thuật bàn giao từ Phân hệ A sang Phân hệ B (`interface_a_b`):

### 4.1. Cấu trúc Schema (Machine-Readable Contract)

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

### 4.2. Quy tắc Thẩm tra Hai Lớp (Two-Layer Validation Discipline)
1. **Lớp 1 - Kiểm tra Cấu trúc Schema (Structural Validation):**
   - Thiếu bất kỳ trường bắt buộc nào trong danh sách `required` -> Từ chối ngay tại biên Phân hệ A với lỗi `VALIDATION_ERROR`.
   - Tuyệt đối không tạo bản ghi `CollectedDocument`, không đẩy event outbox sang B. Ghi nhận nhật ký lỗi với correlation ID an toàn.
2. **Lớp 2 - Kiểm tra Tính Toàn Vẹn Nội Dung (Content Completeness):**
   - Package đúng cấu trúc schema nhưng nội dung rỗng (empty main text) hoặc trích xuất thất bại -> Đánh dấu `content_eligibility = "incomplete"` kèm lý do cụ thể.
   - Khi chuyển sang Phân hệ B, B tiếp nhận nhưng trả về disposition `REJECTED_INCOMPLETE` theo CT-CNT-001; không tạo bài viết mới và không tạo candidate kịch bản.

---

## 5. Máy Trạng Thái Cốt Lõi (Bound State Machines - CONTRACT-STATE-MACHINES)

### 5.1. Vòng đời Nguồn: `CT-STATE-001`
- Đồ thị trạng thái: `ACTIVE` -> `DISABLED` -> `REMOVED_TOMBSTONE`.
- Bất biến: Từ `REMOVED_TOMBSTONE` chỉ có lệnh `RestoreSource` hợp lệ. Nguồn đã remove cấm auto-discovery tạo mới.

### 5.2. Vòng đời Lượt quét: `CT-STATE-002`
- Run:
  - `SCHEDULED` -> `RUNNING`.
  - `RUNNING` -> `WAITING_RETRY` -> `RUNNING`.
  - `RUNNING` -> `WAITING_RECONCILIATION` -> `RUNNING` hoặc trạng thái terminal.
  - `RUNNING` -> `COMPLETED` | `COMPLETED_PARTIAL` | `FAILED_FINAL`.
- Attempt ghi nhận: `SUCCEEDED`, `FAILED_RETRYABLE`, `FAILED_FINAL`, `OUTCOME_UNKNOWN`.
- Bất biến: `OUTCOME_UNKNOWN` không được tự ý retry mù hoặc tự kết luận thành công; bắt buộc reconcile có bằng chứng.

### 5.3. Vòng đời Đề xuất Nguồn (Candidate): `CT-STATE-002A`
- `DISCOVERED` -> `VALIDATING` -> `READY_FOR_REGISTRATION` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`.
- `READY_FOR_REGISTRATION` -> `REGISTERED` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`.
- Bất biến: Registration kiểm tra lại nguyên tử tombstone và existing source trong cùng transaction.

---

## 6. Kết Luận Khóa Bất Biến

Toàn bộ 6 hợp đồng nền tảng cùng các quy tắc chuyển đổi trạng thái và schema phong bì dữ liệu đã được khóa cứng. Không cho phép bất kỳ thay đổi đơn phương nào làm sai lệch baseline đã được phê duyệt.

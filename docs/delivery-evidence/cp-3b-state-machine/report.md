# Báo cáo CP-3B-STATE-MACHINE

## Tệp đã tạo

- `src/controlplane/domain/statemachine/catalog_states.py`
- `tests/integration/convergence/test_cp3b_catalog_graphs.py`
- `tests/integration/convergence/test_cp3b_source_parity.py`
- `docs/delivery-evidence/cp-3b-state-machine/report.md`

## Đồ thị mới (CT-STATE-005, CT-STATE-006)

Module `src/controlplane/domain/statemachine/catalog_states.py` cung cấp bốn hàm chuyển trạng thái độc lập tương ứng với các trục trạng thái của Phân hệ C:
- `transition_media_discovery`: 3 cạnh hợp lệ (`DISCOVERED` -> `ACQUIRING`, `ACQUIRING` -> `CATALOGED`, `ACQUIRING` -> `FAILED`).
- `transition_rendition`: 4 cạnh hợp lệ (`DECLARED` -> `PROCESSING`, `PROCESSING` -> `READY`, `PROCESSING` -> `FAILED`, `PROCESSING` -> `OUTCOME_UNKNOWN`).
- `transition_availability`: 0 cạnh hợp lệ. Văn bản contract CT-STATE-005 chỉ liệt kê danh sách giá trị (`AVAILABLE`, `MISSING`, `CORRUPT`, `RECOVERING`, `UNAVAILABLE_SOURCE`) và không định nghĩa cạnh chuyển trạng thái; ghi rõ `GIẢ ĐỊNH` không tự suy diễn cạnh phục hồi (tương tự nguyên tắc CT-STATE-008). Trục availability tách biệt hoàn toàn với image safety.
- `transition_image_safety`: 9 cạnh hợp lệ (`NOT_ASSESSED` -> `ASSESSING`, `ASSESSING` -> `SAFE`, `ASSESSING` -> `TRANSFORM_REQUIRED`, `ASSESSING` -> `UNCERTAIN`, `ASSESSING` -> `DETECTION_FAILED`, `ASSESSING` -> `UNREADABLE`, `TRANSFORM_REQUIRED` -> `TRANSFORMING`, `TRANSFORMING` -> `PROCESSED_READY`, `TRANSFORMING` -> `TRANSFORM_FAILED`). Cạnh duy nhất đi vào `SAFE` là từ `ASSESSING`. Các kết quả không an toàn gồm `UNCERTAIN`, `DETECTION_FAILED`, `TRANSFORM_FAILED`, `UNREADABLE`, cùng các trạng thái hoàn tất `SAFE` và `PROCESSED_READY` tuyệt đối không có cạnh đi ra và không thể chuyển thành `SAFE`.

Tệp `src/controlplane/domain/statemachine/__init__.py` và toàn bộ các đồ thị đã nghiệm thu trước đó hoàn toàn không bị thay đổi.

## Test tương đương cạnh của A

Phân hệ A giữ nguyên bảng chuyển trạng thái cục bộ tại `src/source_ingestion/domain/source.py`, `src/source_ingestion/domain/collection_run.py`, và `src/source_ingestion/domain/source_candidate.py`. Kiểm thử tại `tests/integration/convergence/test_cp3b_source_parity.py` thực hiện so sánh đối chiếu với danh sách contract viết nội tuyến:
- CT-STATE-001 (Source): 6 cạnh quan sát được khớp chính xác 6 cạnh contract (`ACTIVE` <-> `DISABLED`, `ACTIVE`/`DISABLED` -> `REMOVED_TOMBSTONE`, `REMOVED_TOMBSTONE` -> `ACTIVE`/`DISABLED`).
- CT-STATE-002 (CollectionRun): 15 cạnh quan sát được khớp chính xác 15 cạnh contract cho run.
- CT-STATE-002A (SourceCandidate): 9 cạnh quan sát được (cả bảng `ALLOWED_TRANSITIONS` lẫn hành vi) khớp chính xác 9 cạnh contract (`DISCOVERED` -> `VALIDATING`, `VALIDATING` -> `READY_FOR_REGISTRATION` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`, `READY_FOR_REGISTRATION` -> `REGISTERED` | `MATCHED_EXISTING` | `BLOCKED_TOMBSTONE` | `REJECTED`).
- Hiện tại Phân hệ A không có aggregate Cycle nên cạnh Cycle của CT-STATE-002 chưa có bảng để so sánh (ghi nhận mục mở). Mã nguồn của Phân hệ A được bảo toàn nguyên vẹn, không bị chỉnh sửa.

## Quyết định

**G**: PUC-G-02 (khoảng trống CT-STATE-008, không có cạnh từ WAITING_DEPENDENCY, WAITING_CAPABILITY, FAILED_RETRYABLE) giữ nguyên đồ thị hiện hành. Quyết định của user ngày 20/10/2026 (mục 3 ghi chú Control) giữ nguyên PUC-G-02; việc mở cạnh là ARCHITECTURE_CHANGE đã duyệt, thực hiện bằng slice riêng của chủ đồ thị, ngoài owned paths của CP-3B nên gói này không chạm.

**I**: CP-3B không đổi đồ thị artifact location; cạnh CLEANUP_AUTHORIZED sang DELETED đã có ở `_ARTIFACT_LOCATION_EDGES` trong statemachine/__init__.py và CT-STATE-012, phần còn thiếu là đường ghi YC-HT-I-04 thuộc slice của I. Quyết định của user ngày 20/10/2026 (mục 3 ghi chú Control) duyệt mở đúng hai cạnh PUC-J-03 và YC-HT-I-04 và giữ nguyên PUC-G-02; việc mở cạnh là ARCHITECTURE_CHANGE đã duyệt, thực hiện bằng slice riêng của chủ đồ thị, ngoài owned paths của CP-3B nên gói này không chạm.

**J**: CT-STATE-013 (ConfigRevision) và vòng đời ExternalAccount không đổi trong CP-3B; PUC-J-03. Quyết định của user ngày 20/10/2026 (mục 3 ghi chú Control) duyệt mở đúng hai cạnh PUC-J-03 và YC-HT-I-04 và giữ nguyên PUC-G-02; việc mở cạnh là ARCHITECTURE_CHANGE đã duyệt, thực hiện bằng slice riêng của chủ đồ thị, ngoài owned paths của CP-3B nên gói này không chạm.

**H**: H giữ nguyên, trạng thái view của H là projection và không đăng ký vào controlplane.domain.statemachine.

**D/E/F**: Không thêm máy trạng thái (kế hoạch D-06, E-06, F-06, D8-CV-08).

## BL-CV-01

- BL-CV-01: PENDING (binding H↔G, H↔J và mẫu api/wiring/** do CP-2D-REGISTRY tạo; cạnh CP-2D-REGISTRY giữ nguyên; Control tự sinh cổng; CP-3B không sửa docs/parallel-delivery/** hay docs/09-contracts/**).

## Lệnh đã chạy

| STT | Lệnh | Exit Code | Kết quả thực tế |
|---|---|---|---|
| 3 | `python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py -q -p no:cacheprovider` | 1 | RED oracle hợp lệ: `FF.F............. [100%]`. Danh sách FAILED do `ForbiddenTransitionError` ở cạnh hợp lệ: `test_valid_edges[media_discovery]`, `test_valid_edges[rendition]`, `test_valid_edges[image_safety]`. Tổng kết: `3 failed, 14 passed in 0.13s`. |
| 5 | `python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py -q -p no:cacheprovider` | 0 | GREEN sau khi bổ sung cạnh: `................. [100%]`. Tổng kết: `17 passed in 0.03s`. |
| 9 | `python -m pytest tests/integration/convergence/test_cp3b_source_parity.py -q -p no:cacheprovider` | 0 | Parity characterization test cho Phân hệ A: `........ [100%]`. Tổng kết: `8 passed in 0.05s`. (Test parity là characterization nên không có RED; độ nhạy oracle được chứng minh bởi ba test raise AssertionError). |
| 10 | `python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergence/test_cp3b_source_parity.py -q -p no:cacheprovider` | 0 | Targeted convergence test: `......................... [100%]`. Tổng kết: `25 passed in 0.06s`. |
| 11 | `python -m pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_statemachines.py -q -p no:cacheprovider` | 0 | Hồi quy đồ thị đã có và catalog: `656 passed, 824 subtests passed in 1.17s`. |
| 12 | `git diff --check` | 0 | Clean, không có lỗi khoảng trắng thừa hay định dạng. |

## Mục mở và backlog

- Availability không có cạnh chuyển trạng thái trong CT-STATE-005 (chỉ định nghĩa danh sách enum);
- Phân hệ A không có aggregate Cycle (chu trình thu thập của CT-STATE-002 chưa có bảng trong A để so sánh);
- Test của gói hội tụ đặt tại `tests/integration/convergence/` vì bên ngoài phong bì không có thư mục test đơn vị.

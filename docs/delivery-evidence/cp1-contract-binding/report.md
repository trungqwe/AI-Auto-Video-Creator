# Báo cáo bằng chứng CP1-CONTRACT-BINDING

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `35ea5029b40cc4a5edcc3054499676cd6dc591e2`

## Hash nguồn contract

Output lệnh kiểm tra mã băm SHA-256 bước 1:

```
docs/09-contracts/00-common-contract.md dfdce8db13d5f1d1f286ccd233a66caf39f48552da2dbbad26692fde7be978e8
docs/09-contracts/01-control-api-and-stream.md ea16fe04759e6bdf3b7bdde3e27ad498d13a271bd45d412ba0e9068a9b918e12
docs/09-contracts/02-domain-events.md 8114a208cecca67e553345ea5574d68752323c79cf833c8c8c9fa5e2f86e7540
docs/09-contracts/03-workflow-and-execution.md 0fca25f2bc037a4c2bc58b844079dace8c19a9fd5af5c0ce8ad75e421bc2dc83
docs/09-contracts/04-source-content-contracts.md 61b075d202dd0d7729123f68f26285097be8120e2de48194d0ad2fe847701f31
docs/09-contracts/05-content-media-contracts.md ea6a3723dece842d132f634d44c32eb301fbc98b43b61d24b5c32c907782e4cf
docs/09-contracts/06-creative-ai-contracts.md 92b74489890f1eaf3915aef809af4cff0585659842f6930bbdf11d1236861b3a
docs/09-contracts/07-media-processing-contracts.md c5f7abaea422916165d59f8a5508817729d21035cffd663123a913c49365cf49
docs/09-contracts/08-render-quality-contracts.md c3e35d032c0a8e721ed35bbecb5fb57f350788e8520d6e8df5ca78284199b493
docs/09-contracts/09-orchestration-contracts.md 402f499f2ac2613502684f1d89697cf72d0cc136b25f2fd08fae07a7c1baaf59
docs/09-contracts/10-storage-contracts.md 6ab6f60bc2760ea9017ca0406e0053dc859cc06c1f0c80fff7e944d03d5e02ce
docs/09-contracts/11-configuration-security-contracts.md 989d9ef22c2096f56453722f059efc1427a3018e64c1a7f67a8d514f55c69645
docs/09-contracts/12-state-machines.md 2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28
docs/09-contracts/13-traceability-and-open-items.md 8691423b4a18a4c46631aa4ff08c461a9b52e302c8dd07bcde8c081c97aff7ca
docs/09-contracts/README.md 5509b2ae9a551bece322856d74cacda0995de981747bdb17beb422888a23aaa1
```

Chênh lệch so với registry: Không có chênh lệch. Toàn bộ các giá trị mã băm SHA-256 của các hợp đồng chuẩn đều trùng khớp chính xác với định nghĩa trong `contract-registry.yaml`.

## RED

- Kết quả bước 2 (quan sát instrument nghiệm thu tại baseline HEAD `35ea5029b40cc4a5edcc3054499676cd6dc591e2` trước khi tạo tệp):
  - Exit code: 1
  - Nguyên văn AssertionError: `AssertionError: bindings/README.md and at least six seam manifests are required`
- Kết quả bước 6 (chạy bộ kiểm thử hợp đồng `python -m pytest tests/contract -q -p no:cacheprovider` trước khi tạo manifest, fixture, errata và khối registry):
  - Exit code: 1
  - Nguyên văn các test thất bại do AssertionError:
    - `FAILED tests/contract/test_bindings.py::test_inventory_readme_and_minimum_seams` (AssertionError: `bindings/README.md must exist`)
    - `FAILED tests/contract/test_bindings.py::test_registry_binds_every_manifest` (AssertionError: `registry bindings entries must not be empty and match count`)
    - `FAILED tests/contract/test_bindings.py::test_errata_cite_canonical_sources` (AssertionError: `Errata file m3-a.md must exist`)
  - 2 test pass (`test_validator_type_rules`, `test_text_hygiene`), 7 test skip do danh sách tham số rỗng; không có lỗi import, cú pháp hay collection error.

## Thay đổi

Danh sách các tệp tạo mới và chỉnh sửa thuộc sở hữu của task:
- `tests/contract/binding_validator.py`: module validator và helper độc lập, chỉ dùng thư viện chuẩn Python (stdlib).
- `tests/contract/test_bindings.py`: bộ kiểm thử pytest gồm 12 bài test bao quát toàn bộ cấu trúc manifest, phát hiện drift SHA-256, kiểm tra fixture hợp lệ/sai, toàn vẹn registry và vệ sinh văn bản.
- `docs/parallel-delivery/bindings/README.md`: tài liệu quy định danh mục 10 seam, schema `contract-binding/v1`, cửa sổ tương thích (`additive_optional_only`), phát hiện drift và định hướng seam tương lai.
- 10 tệp manifest binding JSON trong `docs/parallel-delivery/bindings/`:
  - `a-b-collected-document.json`
  - `b-d-production-snapshot.json`
  - `c-d-media-candidates.json`
  - `d-e-f-voice-timing.json`
  - `domain-event-envelope.json`
  - `f-render-package.json`
  - `g-activity-execution.json`
  - `g-c-i-completion.json`
  - `i-artifact-version.json`
  - `j-provider-route.json`
- 10 tệp fixture payloads JSON trong `tests/fixtures/contracts/<seam>/`:
  - `tests/fixtures/contracts/a-b-collected-document/payloads.json`
  - `tests/fixtures/contracts/b-d-production-snapshot/payloads.json`
  - `tests/fixtures/contracts/c-d-media-candidates/payloads.json`
  - `tests/fixtures/contracts/d-e-f-voice-timing/payloads.json`
  - `tests/fixtures/contracts/domain-event-envelope/payloads.json`
  - `tests/fixtures/contracts/f-render-package/payloads.json`
  - `tests/fixtures/contracts/g-activity-execution/payloads.json`
  - `tests/fixtures/contracts/g-c-i-completion/payloads.json`
  - `tests/fixtures/contracts/i-artifact-version/payloads.json`
  - `tests/fixtures/contracts/j-provider-route/payloads.json`
- 5 tệp errata đính chính kế hoạch trong `docs/parallel-delivery/errata/`:
  - `m3-a.md`
  - `m4-ci.md`
  - `m5-d.md`
  - `m6-ef.md`
  - `m7-integration.md`
- `docs/parallel-delivery/contract-registry.yaml`: thêm khối `bindings:` ở cuối tệp với 10 entry trỏ tới 10 manifest binding đã tạo.
- `docs/delivery-evidence/cp1-contract-binding/report.md`: tệp báo cáo bằng chứng này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 1 | `python -m pytest docs/parallel-delivery/tests/test_validate.py -q -p no:cacheprovider -k load_yaml` (Baseline bước 3) | 0 | 2 passed, 19 deselected in 0.41s |
| 2 | `python -m pytest tests/contract -q -p no:cacheprovider` (Bước 34) | 0 | 125 passed in 0.27s |
| 3 | `python -c "import json, pathlib, re; b = pathlib.Path('docs/parallel-delivery/bindings'); mans = sorted(b.glob('*.json')); assert (b / 'README.md').is_file() and len(mans) >= 6, 'bindings/README.md and at least six seam manifests are required'; data = [json.loads(m.read_text(encoding='utf-8')) for m in mans]; assert all(d.get('seam') and d.get('source', {}).get('path', '').startswith('docs/09-contracts/') and re.fullmatch(r'[0-9a-f]{64}', d.get('source', {}).get('sha256', '')) for d in data), 'each manifest names its contract source and its sha256'; fx = pathlib.Path('tests/fixtures/contracts'); assert all((fx / d['seam']).is_dir() for d in data), 'each seam has a fixture folder'; e = pathlib.Path('docs/parallel-delivery/errata'); assert all((e / n).is_file() for n in ['m3-a.md', 'm4-ci.md', 'm5-d.md', 'm6-ef.md', 'm7-integration.md']), 'errata for the five plan families'"` (Bước 35) | 0 | PASS (không output) |
| 4 | `python -m pytest docs/parallel-delivery/tests/test_validate.py -q -p no:cacheprovider -k load_yaml` (Bước 36) | 0 | 2 passed, 19 deselected in 0.07s |
| 5 | `git diff --check` (Bước 37) | 0 | PASS (không output, không có khoảng trắng cuối dòng) |

## Quyết định mặc định (D8)

1. Lựa chọn 10 seam đại diện cho các điểm bàn giao chính giữa các phân hệ theo sơ đồ hệ thống `docs/06-system-map.md` và các tệp đặc tả hợp đồng trong `docs/09-contracts/`.
2. Tên các trường được chuyển sang định dạng `snake_case` suy diễn từ văn bản hợp đồng; đây là GIẢ ĐỊNH đặt tên chuẩn hóa, mọi thay đổi sau này bắt buộc phải đi qua quy trình MIGRATE.
3. Các trường enum chưa được chốt danh sách giá trị cố định trong văn bản hợp đồng gốc được tạm thời quy định là kiểu `string`.
4. Toàn bộ logic validation được viết hoàn toàn bằng thư viện chuẩn Python (stdlib), tuân thủ nghiêm ngặt nguyên tắc không thêm thư viện ngoài lock (D9/D10).
5. Khối `key_interface_boundaries` trong `contract-registry.yaml` vốn chứa các thực thể tự đặt không chuẩn hoá (như `DocumentPackage`, `ArticleSnapshot`) được thay thế hoàn toàn bởi các binding trong thư mục này.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10 (duyệt thư viện đề xuất trước CP-2b)
- CP7 tài nguyên thật (D5: Drive/OAuth, GPU, AI trả phí, chạy E2E 12 giờ)

## Follow-up

- Bổ sung binding cho các seam còn lại nêu trong `README.md` (H↔G, A→C, E→C, F→I, J→mọi phân hệ) khi các phân hệ tương ứng triển khai.
- Viết lại kế hoạch E và F ở `IMPL-PLAN-E` và `IMPL-PLAN-F` để thay thế các tệp cũ bị hỏng dấu và dùng đúng state machine/invariant.
- Bổ sung các test ID mới vào catalog `docs/10-test-strategy.md` qua slice sở hữu tài liệu đó trước khi dùng làm oracle kiểm thử chính thức.
- Đồng bộ `HANDOFF.md`, `README.md`, `CHANGELOG.md` thuộc về gói công việc hội tụ (nằm ngoài owned paths của task này).

## Giới hạn

- Không sửa bất kỳ tệp nào trong `docs/09-contracts/**` (nguồn contract là tài nguyên dành riêng bất biến).
- Không sửa các tệp kế hoạch M3–M7 cũ (errata đóng vai trò là nguồn đính chính chuẩn hóa).
- Không chạy kiểm thử `tests/m1` và `tests/m2` trong task này.
- Không thêm bất kỳ thư viện ngoài lock nào, không sửa `pyproject.toml` hay `uv.lock`.
- Không gọi dịch vụ thật hay đọc dữ liệu bí mật; toàn bộ kiểm thử sử dụng fixture giả lập.

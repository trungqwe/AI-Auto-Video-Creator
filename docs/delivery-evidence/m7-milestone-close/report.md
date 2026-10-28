# Báo cáo đóng M7 (revision 4) - TRẠNG THÁI: BLOCKED TẠI BƯỚC 6

## 1. Phạm vi và candidate

- Task: `M7-MILESTONE-CLOSE-R4` (đóng milestone M7, revision 4).
- Candidate: `b8b46c6365c243088988581dbf6d18ba5c7b4e20` (tiêu đề: `integrate(PW-E2E): lane lane-pw-e2e candidate 44e8965191b6`), là HEAD của nhánh tích hợp.
- Interpreter khoá của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\1ca840a7\venv\Scripts\python.exe`.
- Ngày thực thi: `2026-10-29`.
- Quyền hạn: Lane chỉ sở hữu `docs/delivery-evidence/m7-milestone-close/**`; cấm sửa bất kỳ tệp nào thuộc `src/**`, `tests/**`, `migrations/**` hoặc các đường dẫn khác.

## 2. Tiến trình thực thi

Thực hiện theo lệnh làm việc (Work Order) của Orchestrator:
- Chuỗi 1/22: 12/12 đoạn đạt exit code 0 (`git diff --check` và 11 probe kiểm tra cấu trúc plan/slices của các phân hệ A, B, C, I, D, E, F, J, G, H và convergence).
- Chuỗi 2/22: 3/3 đoạn đạt exit code 0 (bản ghi approval D9/D10, plan convergence-ext và plan persist).
- Chuỗi 3/22: 2/2 đoạn đạt exit code 0 (plan/slices của adapt và convergence-ext-ui).
- Chuỗi 4/22: 12/12 đoạn đạt exit code 0 (các bộ unit tests của control_ui, voice, unit toàn bộ, m2 SSE stream, m2 hardening không gồm h36, collection, convergence migration, p9 m2 exit gate).
- Chuỗi 5/22: 24/24 đoạn đạt exit code 0 (harness PostgreSQL DSN, persistence integration tests, adapt wire, adapt prod sources/app, gitattributes, vite config).
- Chuỗi 6/22:
  - Đoạn 1: `npm --prefix src/controlplane/ui run build` đạt exit code 0 (built in 2.75s; dist khớp nguyên trạng).
  - Đoạn 2: `python -m pytest tests/unit/control_ui -q -p no:cacheprovider` đạt exit code 0 (675 passed, 1 warning).
  - Đoạn 3: probe kiểm tra assets trong `ui/dist` đạt exit code 0.
  - Đoạn 4: probe kiểm tra 4 tệp dist đạt exit code 0.
  - Đoạn 5: probe kiểm tra `screenRegistry.ts` gặp lỗi `AssertionError` (exit code 1).

Tổng số đoạn lệnh đã thực thi: 58 đoạn (57 đạt exit code 0, 1 đoạn thất bại exit code 1).

## 3. Chi tiết lỗi tại Bước 6 Đoạn 5

- **Lệnh thực thi:**
  ```bash
  python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s = dict(re.findall('id: ' + chr(39) + '([a-z-]+)' + chr(39) + '.*?backendStatus: ' + chr(39) + '([a-z_]+)' + chr(39), r, re.S)); assert len(s) == 18, s; assert s['sources'] == 'available', 'sources screen still pending_module'; assert all(s[i] == 'pending_module' for i in ['artifacts', 'snapshots', 'story-angles', 'scripts', 'accounts', 'cost']), s"
  ```
- **Exit code:** `1`
- **Thông báo lỗi (STDERR):**
  ```
  Traceback (most recent call last):
    File "<string>", line 1, in <module>
      ...
  AssertionError: {'operations': 'available', 'batches': 'available', 'jobs': 'available', 'configs': 'available', 'sources': 'available', 'articles': 'available', 'events': 'available', 'media': 'available', 'hooks': 'available', 'artifacts': 'available', 'snapshots': 'available', 'story-angles': 'available', 'scripts': 'available', 'stage-runs': 'available', 'sessions': 'available', 'logs': 'pending_module', 'accounts': 'available', 'cost': 'available'}
  ```

## 4. Phân tích nguyên nhân gốc (Root Cause)

1. Probe trên là tiêu chí nghiệm thu cũ từ gói `CP-4B-UI-SCREENS`. Ở thời điểm gói đó được tạo, các màn hình `artifacts`, `snapshots`, `story-angles`, `scripts`, `accounts`, `cost` chưa có backend nên được đánh dấu là `pending_module`.
2. Tuy nhiên, sau đó dự án đã triển khai phân hệ Read Screens (`IMPL-PLAN-READ-SCREENS`, các slice `RS-1` đến `RS-13`) và gói sửa UI `CP-4B-UI-SCREENS-FIX4` (commit `98cd992636dbdbb84c26ccb6ce0da2cdf93bcaf0`). Gói này đã cập nhật `screenRegistry.ts` để đánh dấu tất cả các màn hình trên thành `available`, chỉ giữ duy nhất `logs` là `pending_module`.
3. Suite unit test hiện hành `tests/unit/control_ui/test_h_screen_registry.py` và probe kiểm tra của `CP-4B-UI-SCREENS-FIX4` (nằm ở Chuỗi 7 đoạn 13) yêu cầu rõ ràng:
   ```python
   assert sorted(k for k, v in s.items() if v != 'available') == ['logs']
   ```
4. Khi Control sinh danh sách kiểm thử bắt buộc cho Milestone Close M7, Control đã gom cơ học toàn bộ lệnh kiểm của các gói trong DAG mà chưa loại bỏ các probe kiểm thử đã bị thay thế (obsolete / superseded probes) của `CP-4B-UI-SCREENS` (Chuỗi 6 đoạn 5), `CP-4B-UI-SCREENS-FIX1` (Chuỗi 6 đoạn 13) và `CP-4B-UI-SCREENS-FIX2` (Chuỗi 12 đoạn 32).
5. Hai assertion này loại trừ nhau về mặt logic trên cùng một tệp `src/controlplane/ui/src/features/screens/screenRegistry.ts`: không thể vừa bắt buộc các màn hình trên là `pending_module` lại vừa bắt buộc chúng là `available`.

## 5. Ranh giới phân quyền và kết luận

- Tệp `src/controlplane/ui/src/features/screens/screenRegistry.ts` nằm trong `src/**`, thuộc danh sách đường dẫn cấm (`Forbidden paths`) của task `M7-MILESTONE-CLOSE-R4`.
- Ngay cả khi có quyền sửa, việc đảo ngược `screenRegistry.ts` về `pending_module` là vi phạm kiến trúc gốc, phá vỡ toàn bộ các module `RS-1`..`RS-13` và khiến `CP-4B-UI-SCREENS-FIX4` cùng `tests/unit/control_ui/test_h_screen_registry.py` thất bại.
- Theo quy định phân quyền nghiêm ngặt và tự vệ đóng (Fail-Closed & Zero Hallucinated Authority) tại mục 1.3 và 3.1 của quy chuẩn điều phối Orca, Worker dừng thực thi và báo cáo trạng thái `BLOCKED` kèm `blocked-manifest` để Control cập nhật lại danh sách lệnh kiểm thử cho Milestone Close.

```blocked-manifest
{
  "step": 6,
  "kind": "DEPENDENCY_GAP",
  "ownerTaskIds": ["CP-4B-UI-SCREENS", "CP-4B-UI-SCREENS-FIX1", "CP-4B-UI-SCREENS-FIX2"],
  "paths": ["src/controlplane/ui/src/features/screens/screenRegistry.ts"],
  "ids": ["python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s = dict(re.findall('id: ' + chr(39) + '([a-z-]+)' + chr(39) + '.*?backendStatus: ' + chr(39) + '([a-z_]+)' + chr(39), r, re.S)); assert len(s) == 18, s; assert s['sources'] == 'available', 'sources screen still pending_module'; assert all(s[i] == 'pending_module' for i in ['artifacts', 'snapshots', 'story-angles', 'scripts', 'accounts', 'cost']), s""]
}
```

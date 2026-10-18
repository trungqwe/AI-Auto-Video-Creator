# Báo cáo bằng chứng CP0-GOVERNANCE

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline HEAD: `39b920c4202c603bf58b468b71d7b09df8126e95`

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
| --- | --- | --- | --- |
| 1 | `python -m pytest docs/parallel-delivery/tests -q -p no:cacheprovider` | 0 | 21 passed in 0.35s (100% test passed) |
| 2 | `python -c "import re, pathlib, unicodedata; f = ['AGENTS.md', 'README.md', 'HANDOFF.md', 'docs/12-pre-code-checklist.md', 'docs/11-roadmap.md']…assert all('18/10/2026' in t[n] for n in ['AGENTS.md', 'README.md', 'HANDOFF.md'])"` | 0 | Không còn dòng chứa M3 cùng NOT AUTHORIZED/khóa chặt/BỊ KHÓA; AGENTS.md và README.md không còn yêu cầu push; đủ nguồn quyền 18/10/2026 |
| 3 | `python -c "import re, pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8')…assert not gone, gone"` | 0 | Không có ID trùng; đủ 16 lock mới; PATH-SRC-ORCHESTRATION và PATH-SRC-STORAGE tuân thủ D1; không còn đường dẫn sai quy chuẩn |
| 4 | `python -c "import re, pathlib; m = pathlib.Path('docs/parallel-delivery/acceptance-matrix.yaml').read_text(encoding='utf-8')…assert re.search(r'\b[0-9a-f]{64}\b', r)"` | 0 | acceptance-matrix không trỏ docs/milestones/m3..m7; overlay nêu rõ docs/delivery-evidence/; ownership-recheck.md đủ 3 commit và SHA-256 64 hex hợp lệ |
| 5 | `git diff --check` | 0 | Không có trailing whitespace hoặc ký tự CR thừa; định dạng LF sạch |

## Quyết định mặc định (D8)

1. Bộ đọc YAML tập con stdlib được đặt trong `validate.py`, không thêm thư viện ngoài (D10); `validate-docs-plan.py` dùng lại trực tiếp từ `validate.py`.
2. Gỡ bỏ `.validation-report.json` vì đã lỗi thời (thuộc candidate f9dae86) và không tái sinh được trong runtime khoá.
3. `PATH-IMPLEMENTATION-PLANS` dùng lock gốc `LOCK-IMPL-PLAN-CONVERGENCE`, lock từng kế hoạch được khai ở `plan_locks`.
4. `acceptance-matrix.yaml` chuyển cả hàng G/J của các task tương lai sang `docs/delivery-evidence/<task-id>/report.md` vì đường dẫn cũ nằm trong cây evidence bất biến; giữ nguyên R19/R20 của M2-P8.
5. `LOCK-CONVERGENCE`, `LOCK-M2-REGRESSION`, `LOCK-UI-SHELL`, `LOCK-CONTROL-API` chỉ khai báo lock, chưa gắn `path_ownership` để tránh chồng lấn path của task M2-P8 đã cấp quyền.

## Danh sách chờ user (pendingUserCheckpoint)

- User checkpoint M2 (P8/P9)
- USER-CKPT-D9-D10 (thư viện và cách dựng lại runtime)
- CP7 tài nguyên thật (D5)

## Giới hạn

- Không chạy `validate.py` dạng script (yêu cầu git subprocess và negative fixture suite, nằm ngoài phạm vi lệnh được cấp).
- Lỗi dữ liệu sẵn có của `check_task_dag`/`check_registries` trên các node `TASK-CAP-J-*` không được sửa ở CP0.
- Không ghi PASS cho bất kỳ lệnh kiểm nào chưa được thực thi thực tế.

# M1-P1 — Secret scan

**Kết quả:** `PASS`

- Test TST-M1-P1-008 xác nhận payload có sensitive key bị từ chối trước persistence và exception không echo giá trị canary.
- Lệnh `rg` trên toàn bộ `evidence/m1-p1` trả exit code 1, nghĩa là không tìm thấy canary test.
- Evidence chỉ chứa ID/ref giả lập, version, trạng thái và hash; không chứa credential, token hoặc secret thật.

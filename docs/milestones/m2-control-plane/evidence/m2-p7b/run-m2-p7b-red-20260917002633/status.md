# M2-P7B Behavioral RED corrected candidate — ready for review

Source/test `c35571fb334dc7b842ee23378f041e74f1caa277`; oracle SHA-256 `d83d0f2d808f1b0067d5288ea131ded24d8fc46a16462b5254fd4167f7425738`.

Exact 5 collected; `5 failed / 0 passed / 0 errors / 0 skipped`. #000 chứng kiến P3 commit-order defect; #001–#004 fail tại capability seam được duyệt. Các regression bắt buộc PASS, PG18.6/CREATEDB/orphan=0; secret scan và hash DAG ghi trong run. Run cũ `run-m2-p7b-red-20260917000606` bị review từ chối và giữ bất biến. Chưa có GREEN; implementation vẫn khóa.

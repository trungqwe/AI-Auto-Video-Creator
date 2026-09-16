# HANDOFF

- Hiện hành: `M2-P1..P5B_ACCEPTED_CLOSED`; `M2-P6_BEHAVIORAL_RED_ACCEPTED`; `M2-P6_IMPLEMENTATION_AUTHORIZED`. P7+, M3 và Phân hệ A vẫn khóa.
- Architecture-wiring commit `edef193`; immutable evidence/tooling source `4755e54cd7571195a1d6aa2a430042255751a104`; fresh run `run-m2-p6-20260916190000`.
- P6 oracle SHA progression: initial `d31da181bfabe52f0d9d3c347530801135692ef6defc0a3af989bb949e7d640d`; race/idempotency correction `e5d2b248481366597a96caee313c46e03238e16369fb48799d6359ad80daccc1`; architecture-wired `42cf15e9b87e88728aa3d84f633bafc98bb8794c2c4a271d72b74c7258252517`.
- Cả bốn services nhận repository factory; application orchestration có 0 SQL/psycopg/infrastructure import. Structural PostgreSQL adapter chỉ giữ caller-owned connection và có 0 SQL. Capacity caller không còn truyền target.
- Fresh evidence: exact 4 capability-specific failures; regressions P5B/P5A/P4/P3/P2/P1/P0/architecture/M1 = 5/5/9/11/11/11/33/6/93, không skip. Migration `0006` vẫn không tồn tại.
- Điểm tiếp tục: triển khai migration/domain/application/PostgreSQL adapter và evidence tooling P6 theo oracle bất biến; dừng tại `M2-P6_IMPLEMENTATION_READY_FOR_REVIEW`, không bắt đầu P7A.

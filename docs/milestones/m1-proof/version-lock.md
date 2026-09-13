# M1 — Khóa môi trường và phiên bản R1

**Ngày khóa do user chỉ định:** 12-09-2026  
**Ngày xác nhận và đối chiếu nguồn chính thức:** 13-09-2026  
**Phạm vi:** chỉ M1 — `R0 Evidence Prototype` / proof kiến trúc  
**Trạng thái:** `APPROVED — CLOSED_FOR_M1_R1`  
**Không phải:** bộ phiên bản cuối cho M2–M7 hoặc production

## 1. Mục tiêu

Khóa tập công nghệ nhỏ nhất cần thiết để bắt đầu test code đầu tiên của M1 và giúp môi trường proof có thể tái lập. Việc khóa version chỉ xác nhận danh tính phiên bản được phép dùng; không đồng nghĩa công nghệ đã vượt compatibility proof, đạt G01/G04/G07 hoặc an toàn cho production.

M1-R1 không tự cho phép package ngoài bảng khóa. Dependency chuyển tiếp chỉ được thêm khi resolver cần cho package trực tiếp và phải xuất hiện chính xác trong `uv.lock`.

## 2. Version set có thẩm quyền

| Nhóm | Thành phần | Version M1-R1 | Vai trò trong M1 | Bằng chứng tồn tại đã đối chiếu |
|---|---|---:|---|---|
| Runtime | CPython | `3.13.15` | Chạy proof Python | [Python release](https://www.python.org/downloads/release/python-31315/) |
| Quản lý môi trường | uv | `0.12.13` | Resolve, lock và chạy môi trường M1 | [uv installation](https://docs.astral.sh/uv/getting-started/installation/) |
| Database | PostgreSQL Server | `18.6` | Transaction/idempotency/outbox/receipt proof | [PostgreSQL 18.6](https://www.postgresql.org/docs/release/18.6/) |
| Database client | psycopg | `3.3.5` | Python ↔ PostgreSQL | [psycopg on PyPI](https://pypi.org/project/psycopg/3.3.5/) |
| Typed schema | Pydantic | `2.13.5` | Contract/schema tối thiểu của proof | [Pydantic on PyPI](https://pypi.org/project/pydantic/2.13.5/) |
| Workflow server | Temporal Server | `1.31.2` | G01 proof target | [Temporal release](https://github.com/temporalio/temporal/releases/tag/v1.31.2) |
| Workflow SDK | temporalio Python SDK | `1.32.0` | Workflow/activity/replay proof | [temporalio on PyPI](https://pypi.org/project/temporalio/1.32.0/) |
| Drive client | google-api-python-client | `2.200.0` | G04 Drive API proof | [Google API client on PyPI](https://pypi.org/project/google-api-python-client/2.200.0/) |
| OAuth client | google-auth-oauthlib | `1.4.1` | G04 OAuth flow proof | [OAuth library on PyPI](https://pypi.org/project/google-auth-oauthlib/1.4.1/) |
| Test runner | pytest | `9.1.1` | RED/GREEN proof tests | [pytest on PyPI](https://pypi.org/project/pytest/9.1.1/) |
| Async tests | pytest-asyncio | `1.4.0` | Async worker/adapter tests | [pytest-asyncio on PyPI](https://pypi.org/project/pytest-asyncio/1.4.0/) |
| Coverage | pytest-cov | `7.1.0` | Đo coverage như bằng chứng hỗ trợ | [pytest-cov on PyPI](https://pypi.org/project/pytest-cov/7.1.0/) |
| Media CLI | FFmpeg family | `9.0.1` | Compatibility smoke, chưa phải render pipeline | [FFmpeg 9.0.1](https://ffmpeg.org/download.html) |

Python 3.14, PostgreSQL 19 beta và floating tag `latest` không thuộc baseline. Version nguồn tồn tại không chứng minh tổ hợp Windows/Python/PostgreSQL/Temporal/FFmpeg tương thích; việc đó thuộc M1-P5 và các gate sau.

Metadata chính thức đã được kiểm tra ngày 13-09-2026: các package Python trực tiếp trên đều hỗ trợ Python 3.13 theo `requires-python`; pytest-asyncio 1.4.0 yêu cầu pytest `>=8.4,<10`, tương thích pytest 9.1.1; temporalio 1.32.0 yêu cầu Python `>=3.10`. Đây chỉ là kiểm tra constraint tĩnh. `uv lock` và smoke thật tại P0/P5 mới xác nhận tập dependency chuyển tiếp trên máy mục tiêu.

## 3. Lý do khóa

| Quyết định | Lý do | Điều chưa được suy ra |
|---|---|---|
| Python 3.13.15 | Stable maintenance release được user chọn; tránh đưa Python 3.14 vào proof đầu tiên | Không chứng minh mọi wheel/transitive dependency chạy đúng |
| uv + `uv.lock` | Một đường resolve/lock duy nhất, phù hợp yêu cầu tái lập và không dùng latest | Không thay hash binary/runtime evidence |
| PostgreSQL 18.6 + psycopg 3.3.5 | Kiểm tra transaction/outbox/receipt trên đúng baseline kiến trúc | Không chốt schema production hoặc topology HA |
| Pydantic 2.13.5 | Typed boundary nhỏ cho envelope/evidence | Không cho business domain phụ thuộc framework hoặc sinh framework web |
| Temporal 1.31.2 + SDK 1.32.0 | Tổ hợp user chọn để thử giả định ADR-0003 | Không làm ADR-0003 thành Accepted hoặc G01 PASS |
| Google client/OAuth | Đủ triển khai adapter proof G04 khi có credential thật | Không chứng minh quota, quyền, refresh/revoke hoặc integrity |
| pytest toolchain | Bộ test nhỏ nhất cho test-first M1 | Coverage cao không thay oracle/failure injection |
| FFmpeg 9.0.1 family | Có phiên bản source ổn định để kiểm smoke | Không khóa nhà cung cấp binary, build config, codec/license hoặc output profile |

## 4. Quy tắc môi trường và lock

`uv.lock` là nguồn sự thật về dependency Python trực tiếp và chuyển tiếp thực tế của M1-R1.

Trước dòng test Python đầu tiên, M1-P0 phải:

1. Xác nhận runtime thực là CPython `3.13.15`, bản GIL thông thường; không tự chuyển sang free-threaded/debug build.
2. Xác nhận uv `0.12.13`; không dùng floating installer hoặc image tag.
3. Tạo project metadata tối thiểu chỉ cho M1, khai exact direct versions trong bảng.
4. Tạo `uv.lock`, chạy sync frozen và ghi SHA-256 của lockfile vào `evidence/m1-p0/bootstrap.json`.
5. Ghi vào cùng bootstrap record: OS/architecture, đường phân phối, version output của Python/uv và kết quả PostgreSQL 18.6 + psycopg 3.3.5 preflight gồm kết nối, `SELECT 1`, rollback và round-trip UTF-8.
6. Ghi hash/digest của installer/image/binary thực tế khi artifact đó được chọn. Tag version không thay digest; Temporal/FFmpeg evidence được bổ sung ở package thực sự dựng artifact.

`bootstrap.json` là bản ghi đầu vào được tạo trước test bằng thao tác bootstrap, không phải output chứng minh P0 PASS. Test P0 đọc bản ghi này làm expected input và phải RED vì `evidence/m1-p0/environment.json` chưa tồn tại/chưa đúng. `evidence/manifest.json` toàn M1 chỉ được tổng hợp tại P6.

Sau khi có lockfile:

- không chạy floating `latest`;
- không tự upgrade dependency trong lúc proof;
- không thêm package “tiện dùng” nếu không phục vụ test/proof cụ thể;
- mọi thay đổi version hoặc dependency trực tiếp phải có reason, impact và delta evidence;
- dependency chuyển tiếp thay đổi làm lock hash thay đổi và phải được review như một thay đổi môi trường;
- lệnh proof phải dùng chế độ frozen/locked; resolver không được âm thầm viết lại lock trong test run.

Lockfile không khóa PostgreSQL/Temporal/FFmpeg binary. Các artifact ngoài Python phải có version output, nguồn và hash/digest riêng trong evidence.

## 5. Ranh giới typed schema

Pydantic chỉ được dùng cho envelope, command/event/result, receipt, evidence manifest hoặc config schema cần thiết của proof. Business invariant phải được biểu diễn theo contracts đã duyệt và có test độc lập; không để BaseModel hoặc serialization behavior tự trở thành luật nghiệp vụ.

Không thêm FastAPI để “dễ gọi” contract. M1-P1 có thể gọi application boundary trực tiếp trong test harness.

## 6. Temporal và trạng thái ADR-0003

Temporal Server `1.31.2` và Python SDK `1.32.0` là target proof của M1-P2. [ADR-0003](../../adr/0003-durable-workflow-engine.md) vẫn `Conditional` cho tới khi G01 có đủ evidence.

P0/P5 phải ghi chính xác cách chạy server, nguồn distribution/image, digest, schema/bootstrap version, CLI/admin tool nếu thực sự dùng và cấu hình persistence. Thành phần bổ trợ bắt buộc do distribution kéo theo phải có version/digest trong evidence; chúng không mặc nhiên trở thành product dependency.

Nếu server/SDK không tương thích với Python/PostgreSQL hoặc không giữ được semantics grant/receipt/replay, dừng theo plan và mở lại ADR-0003. Không thay Temporal bằng công nghệ khác âm thầm.

## 7. Google Drive/OAuth và ROADMAP-OPEN-003

Hai thư viện Google được khóa để code adapter/test boundary đúng version, nhưng credential/quota/OAuth thật chưa được suy ra là có sẵn.

`ROADMAP-OPEN-003`:

- **STATUS:** `OPEN — BLOCKS M1-P3 ONLY`;
- **BLOCKS TRỰC TIẾP:** việc thực hiện M1-P3;
- **HỆ QUẢ:** `G04_M1_SCOPE` chưa thể đạt và M1 chưa thể qua exit gate khi P3 chưa PASS;
- **DOES NOT BLOCK:** M1-P0, M1-P1, M1-P2;
- **KHI THIẾU CREDENTIAL THẬT:** M1-P3 = `BLOCKED_EXTERNAL`;
- **CẤM:** dùng mock/emulator để tuyên bố G04 PASS.

Mock/fake được dùng cho unit test adapter và failure orchestration nhưng phải gắn environment class E1/E2; chỉ evidence từ tài khoản/quota/OAuth thật ở E3 mới có thể đóng G04.

## 8. FFmpeg compatibility evidence

FFmpeg family version là `9.0.1`. FFmpeg upstream cung cấp source; binary Windows thực tế có thể đến từ nhà phân phối khác nên chưa được coi là khóa đầy đủ chỉ bằng số version.

M1-P0/P5 phải lưu:

- nguồn tải binary/build và URL hoặc artifact identity;
- platform, architecture và loại build;
- SHA-256 của archive và executable thực tế;
- output đầy đủ của `ffmpeg -version`;
- output đầy đủ của `ffmpeg -buildconf`;
- license notice và configuration của build thực tế;
- smoke result cho input/output fixture M1 đã định nghĩa.

Nếu chưa có build phù hợp thì P5 STOP/FAIL theo plan; không đổi build/version âm thầm. FFmpeg proof ở M1 không khóa codec, resolution, bitrate, preset hoặc render architecture của M6.

## 9. Công nghệ cố ý chưa khóa

Không khóa trong M1-R1:

- FastAPI, Node.js, React hoặc thư viện grid UI;
- feedparser, Scrapy, Trafilatura hoặc Playwright;
- AI provider/model, TTS hoặc Whisper/alignment;
- media safety model;
- codec/output profile và render preset;
- tool của Phân hệ A hoặc crawler.

Chúng chỉ được khóa tại milestone đầu tiên thực sự phụ thuộc, theo nghiên cứu/ADR/gate tương ứng. M1 không được thêm chúng để chuẩn bị sẵn cho milestone sau.

## 10. Rollback và revision

R1 là bản ghi quyết định bất biến. Nếu proof fail do compatibility:

1. Dừng work package theo điều kiện STOP; không sửa version tại chỗ để test xanh.
2. Lưu failure evidence, environment manifest và lock hash R1.
3. Mở ADR được chỉ định trong implementation plan nếu failure phủ định quyết định kiến trúc.
4. Đề xuất version delta nhỏ nhất, lý do và test phải chạy lại.
5. Tạo version-lock revision `R2`; R1 vẫn giữ lịch sử và được đánh `SUPERSEDED_FOR_M1` nếu user duyệt R2.
6. Tạo lockfile mới, hash mới và evidence manifest mới; không ghi đè evidence R1.

Rollback môi trường nghĩa là dựng lại đúng R1 từ manifest/hash hoặc quay về revision lock đã duyệt. Không dùng cache chưa xác minh làm bằng chứng tái lập.

## 11. Trạng thái open item và gate

| Mục | Trạng thái sau quyết định | Ý nghĩa chính xác |
|---|---|---|
| `ROADMAP-OPEN-002` | `CLOSED_FOR_M1_R1` | Đủ version set để bắt đầu M1; không áp dụng M2–M7 |
| `ROADMAP-OPEN-003` | `OPEN — BLOCKS M1-P3 ONLY` | Không chặn P0/P1/P2; thiếu external access làm P3 và M1 BLOCKED_EXTERNAL |
| G01 Temporal | `NOT TESTED` | P2 chưa chạy; không được gọi là PASS |
| G04 Drive/OAuth | `NOT TESTED` | P3 chưa chạy; có thể `BLOCKED_EXTERNAL` nếu thiếu credential thật |
| G07 | `NOT TESTED` | Compatibility production chưa được chứng minh |
| Module A/timezone/Tier/source/AI/TTS/output/preset/retention/throughput | GIỮ OPEN THEO GATE CŨ | Không bị version lock M1 đóng hoặc thay đổi |

## 12. Dấu vết phê duyệt

User đã phê duyệt version set M1-R1 và cho phép code chỉ trong M1 ngày 13-09-2026. Theo chỉ thị cuối của cùng lần xác nhận, implementation chưa bắt đầu trong lượt tài liệu này và chờ lệnh tiếp theo.

Khi P0 bắt đầu, evidence phải được lưu tại [evidence](./evidence/README.md); việc có file evidence không tự tạo trạng thái PASS. Mỗi kết luận phải trỏ test run, môi trường và artifact hash cụ thể. P2/P3 nếu đạt chỉ tạo `PASS_M1_SCOPE`; gate G01/G04 toàn phần tiếp tục `PARTIALLY_PROVEN` cho tới khi đủ các lớp bằng chứng ở roadmap.

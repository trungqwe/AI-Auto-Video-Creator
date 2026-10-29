# Gói được bao phủ và SHA tích hợp của M7 (revision 6)

Danh sách gói theo yêu cầu nghiệm thu của revision 6 (M7-MILESTONE-CLOSE-R6), viết trên mã đã rebase lên integration head 32e335249dad5b390e05d7212b22e1718bb14d72 (Control thu hồi grant G1 vì CLOSURE_BASE_STALE). SHA là commit integrate chép từ nhật ký tích hợp đã ghi trong báo cáo đóng mốc M5, M6 và các revision trước của repo; PW-D1-FIX1 chép từ commit integrate 67b01f25ae729e39774d4e4a6adb9c20c805482c; ADAPT-D-FIX1 ghi theo integration head 32e335249dad5b390e05d7212b22e1718bb14d72 mà Control nêu trong lệnh rebase. Nhánh tích hợp đã chứa ADAPT-F-FIX1, ADAPT-J-FIX1, PW-D1-FIX1 và ADAPT-D-FIX1. Tổ tiên của từng SHA do Control xác minh.

| Mã gói | Commit integrate (SHA đầy đủ) | Candidate (12 hex) | Cách tra |
| --- | --- | --- | --- |
| M7-INTEGRATION-PLAN | 0a3f707ffa08b3a5737be6fa30769933d2cf475d | — | Control xác minh receipt Auditor PASS; commit nội dung là tổ tiên của nhánh tích hợp |
| IMPL-PLAN-A | fb154e9f0433d45bef1994e292a948231b18d112 | 23c3e3cf22fb | git log --grep=integrate() |
| IMPL-PLAN-B | 815bebb15b565c4a750854b4218a3296c7be2904 | 6e139f3b2d3b | git log --grep=integrate() |
| IMPL-PLAN-C | 4035610fa62c04ebcd7bc774b4a9e4ed68c5ad1a | 56dc6fa2a949 | git log --grep=integrate() |
| IMPL-PLAN-I | 14a2b92677ebf47724fab8a6229b340f45a1a3a7 | 6b18b402e2f7 | git log --grep=integrate() |
| IMPL-PLAN-D | bd037dc4c148a0a9d31cff9078bf4620b47fd815 | ac0bf98832ed | git log --grep=integrate() |
| IMPL-PLAN-E | c73f90b87c3aa9bd038e9c1b71374ceb1b04a20f | 5e0fac5f84c4 | git log --grep=integrate() |
| IMPL-PLAN-F | e336d92b9146b73d42da5f0346a55eef6c8d4386 | 278d7617f114 | git log --grep=integrate() |
| IMPL-PLAN-J | df699e2d86efeff98f7214fac6cdb40420440ca5 | 1f901a0ef029 | git log --grep=integrate() |
| IMPL-PLAN-G | 5795450216f7b989a15d6b4c3db78276b594f113 | f5bf44546610 | git log --grep=integrate() |
| IMPL-PLAN-H | a461b76e086b8d41ce4f0607da1e2c2460d3c90f | 6ef168eb971f | git log --grep=integrate() |
| IMPL-PLAN-CONVERGENCE | d83ab6107189a14ba92fb3d8d81789f946b461a8 | a5d863f65bf4 | git log --grep=integrate() |
| USER-CKPT-D9-D10 | 0a17d42a1cf678fa670e1be8fd9679825cfba9d8 | 12d3fb8a1fa4 | git log --grep=integrate() |
| IMPL-PLAN-CONVERGENCE-EXT | 3204b3ee38a76646bd6c05322eccd4f643ffab56 | c7a0e67ab18f | git log --grep=integrate() |
| IMPL-PLAN-PERSIST | d9d23586d3af1fa6b2f2b6b741f3bd77e2178ab7 | e9761d25ac7e | git log --grep=integrate() |
| IMPL-PLAN-ADAPT | 7823cf907f8c7ce056479b5fd09c502fbf570237 | dc0949d5b990 | git log --grep=integrate() |
| IMPL-PLAN-CONVERGENCE-EXT-UI | cd33459cd73cbb41accec6725e7c932da154198e | 89c22703dc93 | git log --grep=integrate() |
| H-MODULES-PACKAGE-FIX | e27fe095af4066b41ae2593fb8072b66b0d4a859 | 134ce6966938 | git log --grep=integrate() |
| ADAPT-LAYOUT-TESTS-FIX | d59516a08c66b3c15fbdb2881b01fbf71e3742a0 | 030a074222f3 | git log --grep=integrate() |
| M2-P7B-SSE-DENIAL-TEST-FIX | 672d8f7608c2d8b84e9c1e82b3e2c6bb445bffb3 | dc6ae8ca27c0 | git log --grep=integrate() |
| ADAPT-A-LAYOUT-TEST-FIX | e37111e24990f062575064b64b491e19c433b594 | c5bac971c2e5 | git log --grep=integrate() |
| CP-3-MIGRATIONS-FIX1 | 836de0d664d3bcbc2dc5ff53013cb8b9c5a94cf0 | a8a6cf78f104 | git log --grep=integrate() |
| PG-TEST-DSN-HARNESS | 98d16ee4bef0955900c356da03a7861423976db7 | 63f8f472c84b | git log --grep=integrate() |
| PERSIST-A-LAYOUT-FIX | a82f313a9c4f4062d5e3cfaee3e9cead4037ca21 | 59f8b6e53fdd | git log --grep=integrate() |
| PERSIST-LAYOUT-RULE | 0992609c4bb1542505227b7346aca411212a4bef | 9971e132efd9 | git log --grep=integrate() |
| PERSIST-B-BOUNDARY-RULE | 60c7f36c63e8a43d89e96ee97bb10d96bf0f817c | 4d76c77779cb | git log --grep=integrate() |
| CP-4-WIRING-FIX1 | 06d6c84d8b798f693eab635ab44007ebc23df263 | 2309b3ab4898 | git log --grep=integrate() |
| PERSIST-G-FIX1 | f03fed2f209808f80999643408f4f19a32cde567 | 6f53564a6c56 | git log --grep=integrate() |
| CP-5-COMPLETION-FIX1 | 0ba3801fb9709dd85f7ff15330a877bfd3bf6561 | c2eaba9f3460 | git log --grep=integrate() |
| UI-DIST-WHITESPACE-ATTR | 92ff42aed8099c3a01c4e83812b0826eb2b7b0a8 | 6de668e11e66 | git log --grep=integrate() |
| UI-BUILD-PRESERVE-SYMLINKS | 6a4c8344cd71fa0804508acb024ec4d140c01833 | cb44996268eb | git log --grep=integrate() |
| ADAPT-WIRE-FIX1 | 810c377c112f7ce082ab51564591ade9a519e0b0 | f42c94477378 | git log --grep=integrate() |
| CP-4-WIRING-FIX2 | 759ea0abd830f76b6f6a99232e8183ee50a9f34d | 5aed9712848f | git log --grep=integrate() |
| ADAPT-PROD-FIX1 | 6ba0bcde40de3d3adf8405d9df6bd8cae431227a | d588d9c0e8b0 | git log --grep=integrate() |
| CP-4B-UI-SCREENS-FIX1 | adc7634f45a21c2fa174adee662962d7a1b21a57 | 2760ee3ca0f9 | git log --grep=integrate() |
| PERSIST-C-FIX1 | ab8586d55fc612825888d6a7e26e58ae96d28af6 | 2327dcf8e326 | git log --grep=integrate() |
| ADAPT-PROD-FIX2 | fa250e8305aa422ff260f2ce9bb3622a29239740 | e1cc7f40b25b | git log --grep=integrate() |
| CP-4B-UI-SCREENS-FIX2 | 74c062a29d649ea0e3d1471dee9c739dc33d38fe | 1c85775dea49 | git log --grep=integrate() |
| PG-TEST-DSN-HARNESS-FIX1 | 51fdc0440160d06db296e5db8e60a7d62628b59c | 71aff7b4a405 | git log --grep=integrate() |
| ADAPT-LAUNCH-FIX1 | 21d99fc89eb076a036b4d62f026b057a61d96135 | 9bcb10e680dc | git log --grep=integrate() |
| IMPL-PLAN-PROD-PORTS | 8167d4ca8a6a5f46bcf4adc1d3ed48f0472ce4e1 | 42a501fd0791 | git log --grep=integrate() |
| ADAPT-LAUNCH-FIX2 | 6042d7a626d3d523881cc86d1b0ac674986bcafa | 903393a717cb | git log --grep=integrate() |
| IMPL-PLAN-READ-SCREENS | df8decc7a02130d8627e570fc43b5b2fae0745d0 | c327c78512ef | git log --grep=integrate() |
| ADAPT-LAUNCH-FIX3 | 767bb3acacea58df57419c84a89ffc34ccd9d8b6 | ff1c655e744e | git log --grep=integrate() |
| CP-4B-UI-SCREENS-FIX3 | 700ee722e9549360dbb45d92db904a8483711c4f | 29a350a76374 | git log --grep=integrate() |
| CP-4-WIRING-FIX3 | fee041569d07cd374053bc42a785535ccaba3ed7 | d57b7d5146fb | git log --grep=integrate() |
| ADAPT-PROD-FIX3 | 419e08105690b213296cac9283c2d9a6480f5f99 | ffb624a59ece | git log --grep=integrate() |
| CP-4B-UI-SCREENS-FIX4 | 98cd992636dbdbb84c26ccb6ce0da2cdf93bcaf0 | 45eaa79f881c | git log --grep=integrate() |
| IMPL-PLAN-PROD-WIRING | 24833dbb52f5872416f369a2ee4517e536017e70 | 35b0b4deb83b | git log --grep=integrate() |
| PROD-WIRING-MUSIC-SURVEY | 2508632f4923d5776ded333f28d87d492bfe5a17 | 0563db59ea59 | git log --grep=integrate() |
| IMPL-PLAN-PROD-WIRING-V3 | 7c068002f44a58e15de735e8b7ba4e546bd2cca2 | 354c6dce7cec | git log --grep=integrate() |
| IMPL-PLAN-PROD-WIRING-V4 | 46f9f57cab1225ea984bbe623355160d840a4c92 | e033bd99ea52 | git log --grep=integrate() |
| CP2A-LAYOUT-PKGDIR-FIX | c7ccdedb4ef46fb5fafedbd45e218a1eb5e87d1c | 1fd8b9d24d7c | git log --grep=integrate() |
| PW-A3-FIX1 | 76766c2f4bf1892f5900aad6df735342bb63b902 | ca5c548bba0e | git log --grep=integrate() |
| PW-E3-FIX1 | 9021038dbfcce83c8c1e76f6637dcf1f27b6e256 | 9895c4ad0713 | git log --grep=integrate() |
| PW-I1-FIX1 | 8681b301f5fc3cfd41d5b0457acb6e14e544a1a7 | 5aef2c2a9c95 | git log --grep=integrate() |
| PW-F4-FIX1 | 356480b8d0332fbba5ec9fe8cd133ea941c4bac3 | 4be6d77ffd85 | git log --grep=integrate() |
| PW-A3-FIX2 | 14c945facdb40b29b7279c6121f735c4890b3cd0 | c3e9df3846b9 | git log --grep=integrate() |
| ADAPT-SEED-FIX1 | 5ed14ccb4528312d84b7d3f4b425d3f59cc8c580 | 1880969efe70 | git log --grep=integrate() |
| PW-D3-FIX1 | 3b86bfddf5ecb01b1c45daf77bd2c187799062de | 27372e77a68c | git log --grep=integrate() |
| PW-W2-FIX1 | 813c739cf2d864464bd8d393409d7854c56e48dc | 68181fc3a1f2 | git log --grep=integrate() |
| PW-W2-FIX2 | 3799d019baed5806c0c5be1ad13a1d9b7cefb16e | 416583fd3177 | git log --grep=integrate() |
| PW-W2-FIX3 | 2ab2ddfe4f14d4f73d55d8a4aaa2aec2300ae51d | c2d6be1514e3 | git log --grep=integrate() |
| PW-F4-FIX2 | 17f9c7405971ca1153ddf03e4181342ad9c8448b | bae7d5ddc1a9 | git log --grep=integrate() |
| F-10-FIX1 | a48f6cab967e2ccae061c76350d74c1b8f28cbca | fa8a69962b37 | git log --grep=integrate() |
| PW-I1-FIX2 | 57ab50cadf6f99901e6c3d7295287382c40f188f | d7dcdb34d68e | git log --grep=integrate() |
| PW-F1-FIX1 | 5bf1d14e82efa2a60c9e3a28d4ccfcc44c7cfeb8 | 8f54f339b795 | git log --grep=integrate() |
| ADAPT-SEED-FIX2 | b48d807e0f16ff061671523808def7addac0019e | df0a962cb517 | git log --grep=integrate() |
| PW-W2-FIX4 | aa5ba684a4cffb012030cbcb3d34f4ebc30cd485 | a7db460c0b59 | git log --grep=integrate() |
| F-10-FIX2 | 9e67a6ba3d0e64735ffd51dc068107ea0fe0222d | d594e124d946 | git log --grep=integrate() |
| PW-F1-FIX2 | 069d9743c18cab0003b35fcd4f81ee3b3ce622a5 | 2dbe58418121 | git log --grep=integrate() |
| ADAPT-F-FIX1 | f080601bae4ed341837157aaf87b3bcd85bd7424 | 110ba265a338 | Báo cáo R4 mục 1-2: integration head f080601 đã tích hợp ADAPT-F-FIX1 (commit gói 110ba265a338) trên base 069d9743 |
| ADAPT-J-FIX1 | a84ac3940a4cef48c85733df30b016b3821aa1c3 | 4ec05756ff07 | git log --grep=integrate() |
| PW-D1-FIX1 | 67b01f25ae729e39774d4e4a6adb9c20c805482c | 86594a85451b | Tiêu đề commit integrate trong đề bài: integrate(PW-D1-FIX1): lane lane-pw-d1-fix1 candidate 86594a85451b; commit nội dung 86594a8 (R14, báo cáo docs/delivery-evidence/pw-d1-fix1/report.md); Control xác minh SHA này là tổ tiên của integration head 32e335249dad5b390e05d7212b22e1718bb14d72 |
| ADAPT-D-FIX1 | 32e335249dad5b390e05d7212b22e1718bb14d72 | — | Integration head mà Control nêu trong lệnh rebase (CLOSURE_BASE_STALE), đã chứa gói được phủ tích hợp sau 67b01f2; Worker không tra git log nên ghi SHA này làm SHA tích hợp của gói, Control xác minh khớp commit integrate(ADAPT-D-FIX1) |
| A-01 | 22535f6dcff3dbf2e3187771a9bff1b34c85c838 | b11289d9c406 | git log --grep=integrate() |
| A-02 | e343a41ee6570c39d0cbeda2bd35a3bf2c15513f | 0614e8d1934d | git log --grep=integrate() |
| A-03 | 5e009d1c06ba60052bdd1658f939ffaadc626597 | 6382ebd2cdde | git log --grep=integrate() |
| A-04 | f1d4a4c543fb9c14a48c3e44e82c20622d0ddc34 | c512aedfd810 | git log --grep=integrate() |
| A-05 | 596237ae94bcb7ba0bbc7b8536b6b12d4a95ea93 | 8c4c80c5982e | git log --grep=integrate() |
| A-06 | 7f6c060c32c3dc545b857a1714b5fea0b445429f | 1b7754bbf77a | git log --grep=integrate() |
| A-07 | ae8d0e3e4a02ea36a357b990d7e6d62e8326f3d1 | e58ac323b47f | git log --grep=integrate() |
| A-08 | c18f5fd14fd57c308b1d8e42128cbbb063a4ef74 | b867f1f24233 | git log --grep=integrate() |
| A-09 | ec82a8154aeaf956305e08c493e07c4736dcf1de | 9c93960aee60 | git log --grep=integrate() |
| A-10 | a93ae583b468e7d61c4efe63d7609ff83ee4bed1 | 18233ddf6c7b | git log --grep=integrate() |
| A-11 | 66e0591dc74b4f2e09b005c2cd4715f74b06280c | 8425147edd1b | git log --grep=integrate() |
| A-12 | bad89e191f3ddd653febc2626eb80d813c93f8b8 | 044cdf1a9075 | git log --grep=integrate() |
| A-13 | ccfd11131d7f8e8dd6a5340ac48d8a2e16c7111d | b46a5591d574 | git log --grep=integrate() |
| A-14 | 4efa4f6c3d3a11b7610bcd06707fe8105e3933e0 | 4d292f278aab | git log --grep=integrate() |
| A-15 | 11128dc8b3f7d27b885d3f6e3803c5822c6ed468 | b09724147f4a | git log --grep=integrate() |
| A-16 | bfc0d32e2bbe8f897229b9b87d77f91f200f3e9d | 1f2f3d17bd69 | git log --grep=integrate() |
| A-17 | 3529edc34d9444d9629a3191c34dc07ab72a2d07 | a5f13fc184bb | git log --grep=integrate() |
| A-18 | 773af60b0f148d6212f261abeb57c71fb5bde4b7 | ba3370b8578b | git log --grep=integrate() |
| A-19 | b75a132ef7ab944d785b8c39ff0295584d547a39 | de07c98c6b4f | git log --grep=integrate() |
| ADAPT-DEPS | fb7bca7f0d6c40142ca623d40b6e1921340e4abe | 0db5b62042e2 | git log --grep=integrate() |
| ADAPT-A | 985d542dbaf148d76d1651ddedb0bf448a7a312c | fbb90573e8f9 | git log --grep=integrate() |
| ADAPT-D | 69cf7ce8e28c8cebb26a97eabb289c84feb5eeef | 747cf2ba3e58 | git log --grep=integrate() |
| ADAPT-E | 97a13ddd384c486c5b8b9367d3e36c1f96b5f92b | 734c02ce1499 | git log --grep=integrate() |
| ADAPT-E-MEDIA | 5dcf3d5c3252f884a812932b3d8ab5a61493439f | 5c632b65335d | git log --grep=integrate() |
| ADAPT-F | 4c4486a9cd1e38a91d0374530933aa3860fb6a5a | 54bf210b7df8 | git log --grep=integrate() |
| ADAPT-J | b5550a06a10d64c33eedc74d28b19569c431dfb2 | fb5ef89cb2ff | git log --grep=integrate() |
| ADAPT-I | fbbe798a06d4030f1dfc8a48399af5ffb704d15e | 8b142a0a7ecc | git log --grep=integrate() |
| ADAPT-CONF | fe206ac52815f87769890b77efc7d8c51807528f | 2680d83e4f06 | Commit integrate trong git ghi tiêu đề integrate(ADAPT-CONFIG) |
| ADAPT | xem mục Gói con của nhóm ADAPT | — | Tên ADAPT trong danh sách nghiệm thu được hiểu là nhóm IMPL-PLAN-ADAPT; tài liệu repo không ghi commit integrate riêng tên ADAPT, các commit của nhóm liệt kê bên dưới |

## Gói con của nhóm ADAPT

| Mã gói | Commit integrate (SHA đầy đủ) | Candidate (12 hex) |
| --- | --- | --- |
| ADAPT-I | fbbe798a06d4030f1dfc8a48399af5ffb704d15e | 8b142a0a7ecc |
| ADAPT-CONFIG | fe206ac52815f87769890b77efc7d8c51807528f | 2680d83e4f06 |
| ADAPT-WIRE | a046fa4c6784cd1ea3fcf1900e769b6bee3a9863 | f4e443d18434 |
| ADAPT-SEED | 497a06b5f0f0783ea42200cb35f0f922f2cad09d | b97c9596725d |
| ADAPT-PROD | 790f768269fd2e1218fdeb7aec82621dfa415827 | 62c610c36106 |
| ADAPT-LAUNCH | cc290f002074514001fa0b03b3eb8c9e00c14db6 | faa54f225bdc |

## Gói retire, không được bao phủ

- `IMPL-PLAN-PROD-WIRING-FIX1`: Gói sửa kế hoạch PROD-WIRING ban đầu, đã bị thay thế bởi kế hoạch V3/V4 (`IMPL-PLAN-PROD-WIRING-V3` và `IMPL-PLAN-PROD-WIRING-V4`) nằm trong danh sách bao phủ; không còn nằm trên đường tới exit gate M7-R5-EG1 và M7-R6. Các lệnh kiểm của PW-* vẫn được chạy đầy đủ.
- `IMPL-PLAN-PROD-WIRING-V3-FIX1`: Gói sửa kế hoạch PROD-WIRING V3 ban đầu, đã được hợp nhất và thay thế bởi `IMPL-PLAN-PROD-WIRING-V4` nằm trong danh sách bao phủ; không còn nằm trên đường tới exit gate M7-R5-EG1 và M7-R6.

## Ghi chú

- Các commit integrate của các gói tính năng bổ sung và E2E (như `integrate(PW-E2E)`, `integrate(PP-*)`, `integrate(RS-*)`) đã được tích hợp đầy đủ vào nhánh tích hợp và là tổ tiên của HEAD hiện tại.
- Toàn bộ 16 cổng `GATE-*` không có commit integrate trực tiếp mà được Control phát hành bằng bản ghi quyết định RELEASE có mã recordHash xác thực tại `gate-releases.md`.
- Revision 6 so với revision 5 thêm hai gói: PW-D1-FIX1 (nhóm lỗi R14: ref nguồn trong khối dữ liệu phi tín nhiệm và prompt mặc định khớp parser của phân hệ creative; báo cáo docs/delivery-evidence/pw-d1-fix1/report.md) và ADAPT-D-FIX1 (hàng mới sau khi lane rebase lên 32e335249dad5b390e05d7212b22e1718bb14d72). Mọi hàng khác chép nguyên từ revision 5.
- Danh sách nghiệm thu của revision 6 kết thúc ở ADAPT-E. Các hàng ADAPT-E-MEDIA, ADAPT-F, ADAPT-J, ADAPT-I, ADAPT-CONF và hàng nhóm ADAPT trong bảng là hàng bổ sung giữ từ revision 5, không thuộc danh sách bắt buộc của revision 6.
- Nhánh tích hợp còn chứa các commit nằm ngoài danh sách bao phủ của M7-MILESTONE-CLOSE-R6, không tính vào bảng gói: CP7-1 (báo cáo docs/delivery-evidence/cp7-1), CP7-2 (commit integrate 7b77aa1, candidate 4bff4cf7682f) và CP7-3 (commit integrate feb344d, candidate 4d9d6ee7083e). Đây là bằng chứng tài nguyên thật RG-01 và RG-02 của CP7, không phải gói của M7-MILESTONE-CLOSE. Lệnh làm việc không cho git log nên báo cáo chỉ chép các SHA đã nêu trong đề bài hoặc báo cáo trước và không đoán SHA khác; commit mới sau rebase (nếu có) nằm ngoài danh sách bao phủ không được liệt kê ở đây.

# Báo cáo đóng M6 (revision 3): M6-MILESTONE-CLOSE-R3

## 1. Phạm vi và lý do R3

Revision 1 M6-MILESTONE-CLOSE đã đóng mà không tích hợp; Control 20/10/2026: policy v1 thêm bốn dòng kế hoạch (CONVERGENCE-EXT, EXT-UI, PERSIST, ADAPT) vào phạm vi đóng M6; revision 1 đóng băng phạm vi cũ và chưa giao Worker nào, nên dù chạy xong vẫn phải đóng lại ở R2; retire để đóng M6 đúng một lần ở R2 với đủ phạm vi (chấm điểm chi phí và đường găng: bớt một lượt đóng, trả suất cho gói kế hoạch).

Bản R2 (candidate 74c062a29d649ea0e3d1471dee9c739dc33d38fe) được thay bằng R3 vì candidate nay là HEAD 8167d4ca8a6a5f46bcf4adc1d3ed48f0472ce4e1 và phạm vi R3 thêm gói ADAPT-LAUNCH-FIX1 (commit integrate 21d99fc, candidate 9bcb10e680dc) chưa có trong báo cáo R2; mọi lệnh kiểm chạy lại trên candidate mới, kết quả R2 không còn dùng.

Ghi nhận minh bạch: HEAD còn chứa các commit integrate CP7-REAL-RESOURCES (4b11dd0) và IMPL-PLAN-PROD-PORTS (8167d4c, kèm commit nội dung 42a501f) nằm ngoài danh sách phạm vi đóng M6, không tính vào bảng gói.

## 2. Candidate được kiểm

Candidate là HEAD 8167d4ca8a6a5f46bcf4adc1d3ed48f0472ce4e1 của nhánh trungqwe/lane-m6-milestone-close-r3 trước commit của lượt này; mọi lệnh kiểm chạy bằng interpreter khoá của lane; kết quả từng lệnh ở command-results.md.

## 3. Gói được bao phủ và SHA tích hợp

### 3.1 Gói kế hoạch và gói sửa

| Mã gói | Commit integrate (SHA đầy đủ) | Candidate (12 hex) | Cách tra |
| --- | --- | --- | --- |
| M6-EF-PLAN | 597e36c1c1cf5eac336acbe9b44b74ad0e9135c4 | — | Control xác minh receipt Auditor PASS và commit nội dung là tổ tiên của nhánh tích hợp (không có commit integrate) |
| IMPL-PLAN-A | fb154e9f0433d45bef1994e292a948231b18d112 | 23c3e3cf22fb | git log --grep="integrate(IMPL-PLAN-A)" |
| IMPL-PLAN-B | 815bebb15b565c4a750854b4218a3296c7be2904 | 6e139f3b2d3b | git log --grep="integrate(IMPL-PLAN-B)" |
| IMPL-PLAN-C | 4035610fa62c04ebcd7bc774b4a9e4ed68c5ad1a | 56dc6fa2a949 | git log --grep="integrate(IMPL-PLAN-C)" |
| IMPL-PLAN-I | 14a2b92677ebf47724fab8a6229b340f45a1a3a7 | 6b18b402e2f7 | git log --grep="integrate(IMPL-PLAN-I)" |
| IMPL-PLAN-D | bd037dc4c148a0a9d31cff9078bf4620b47fd815 | ac0bf98832ed | git log --grep="integrate(IMPL-PLAN-D)" |
| IMPL-PLAN-E | c73f90b87c3aa9bd038e9c1b71374ceb1b04a20f | 5e0fac5f84c4 | git log --grep="integrate(IMPL-PLAN-E)" |
| IMPL-PLAN-F | e336d92b9146b73d42da5f0346a55eef6c8d4386 | 278d7617f114 | git log --grep="integrate(IMPL-PLAN-F)" |
| IMPL-PLAN-J | df699e2d86efeff98f7214fac6cdb40420440ca5 | 1f901a0ef029 | git log --grep="integrate(IMPL-PLAN-J)" |
| IMPL-PLAN-G | 5795450216f7b989a15d6b4c3db78276b594f113 | f5bf44546610 | git log --grep="integrate(IMPL-PLAN-G)" |
| IMPL-PLAN-H | a461b76e086b8d41ce4f0607da1e2c2460d3c90f | 6ef168eb971f | git log --grep="integrate(IMPL-PLAN-H)" |
| IMPL-PLAN-CONVERGENCE | d83ab6107189a14ba92fb3d8d81789f946b461a8 | a5d863f65bf4 | git log --grep="integrate(IMPL-PLAN-CONVERGENCE)" |
| IMPL-PLAN-CONVERGENCE-EXT | 3204b3ee38a76646bd6c05322eccd4f643ffab56 | c7a0e67ab18f | git log --grep="integrate(IMPL-PLAN-CONVERGENCE-EXT)" |
| IMPL-PLAN-PERSIST | d9d23586d3af1fa6b2f2b6b741f3bd77e2178ab7 | e9761d25ac7e | git log --grep="integrate(IMPL-PLAN-PERSIST)" |
| IMPL-PLAN-ADAPT | 7823cf907f8c7ce056479b5fd09c502fbf570237 | dc0949d5b990 | git log --grep="integrate(IMPL-PLAN-ADAPT)" |
| IMPL-PLAN-CONVERGENCE-EXT-UI | cd33459cd73cbb41accec6725e7c932da154198e | 89c22703dc93 | git log --grep="integrate(IMPL-PLAN-CONVERGENCE-EXT-UI)" |
| CP-3-MIGRATIONS-FIX1 | 836de0d664d3bcbc2dc5ff53013cb8b9c5a94cf0 | a8a6cf78f104 | git log --grep="integrate(CP-3-MIGRATIONS-FIX1)" |
| CP-4-WIRING-FIX1 | 06d6c84d8b798f693eab635ab44007ebc23df263 | 2309b3ab4898 | git log --grep="integrate(CP-4-WIRING-FIX1)" |
| PERSIST-G-FIX1 | f03fed2f209808f80999643408f4f19a32cde567 | 6f53564a6c56 | git log --grep="integrate(PERSIST-G-FIX1)" |
| CP-5-COMPLETION-FIX1 | 0ba3801fb9709dd85f7ff15330a877bfd3bf6561 | c2eaba9f3460 | git log --grep="integrate(CP-5-COMPLETION-FIX1)" |
| ADAPT-WIRE-FIX1 | 810c377c112f7ce082ab51564591ade9a519e0b0 | f42c94477378 | git log --grep="integrate(ADAPT-WIRE-FIX1)" |
| CP-4-WIRING-FIX2 | 759ea0abd830f76b6f6a99232e8183ee50a9f34d | 5aed9712848f | git log --grep="integrate(CP-4-WIRING-FIX2)" |
| ADAPT-PROD-FIX1 | 6ba0bcde40de3d3adf8405d9df6bd8cae431227a | d588d9c0e8b0 | git log --grep="integrate(ADAPT-PROD-FIX1)" |
| CP-4B-UI-SCREENS-FIX1 | adc7634f45a21c2fa174adee662962d7a1b21a57 | 2760ee3ca0f9 | git log --grep="integrate(CP-4B-UI-SCREENS-FIX1)" |
| PERSIST-C-FIX1 | ab8586d55fc612825888d6a7e26e58ae96d28af6 | 2327dcf8e326 | git log --grep="integrate(PERSIST-C-FIX1)" |
| ADAPT-PROD-FIX2 | fa250e8305aa422ff260f2ce9bb3622a29239740 | e1cc7f40b25b | git log --grep="integrate(ADAPT-PROD-FIX2)" |
| CP-4B-UI-SCREENS-FIX2 | 74c062a29d649ea0e3d1471dee9c739dc33d38fe | 1c85775dea49 | git log --grep="integrate(CP-4B-UI-SCREENS-FIX2)" |
| ADAPT-LAUNCH-FIX1 | 21d99fc89eb076a036b4d62f026b057a61d96135 | 9bcb10e680dc | git log --grep="integrate(ADAPT-LAUNCH-FIX1)" |

### 3.2 Phân hệ A, ADAPT, B, C

| Mã gói | Commit integrate (SHA đầy đủ) | Candidate (12 hex) | Cách tra |
| --- | --- | --- | --- |
| A-01 | 22535f6dcff3dbf2e3187771a9bff1b34c85c838 | b11289d9c406 | git log --grep="integrate(A-01)" |
| A-02 | e343a41ee6570c39d0cbeda2bd35a3bf2c15513f | 0614e8d1934d | git log --grep="integrate(A-02)" |
| A-03 | 5e009d1c06ba60052bdd1658f939ffaadc626597 | 6382ebd2cdde | git log --grep="integrate(A-03)" |
| A-04 | f1d4a4c543fb9c14a48c3e44e82c20622d0ddc34 | c512aedfd810 | git log --grep="integrate(A-04)" |
| A-05 | 596237ae94bcb7ba0bbc7b8536b6b12d4a95ea93 | 8c4c80c5982e | git log --grep="integrate(A-05)" |
| A-06 | 7f6c060c32c3dc545b857a1714b5fea0b445429f | 1b7754bbf77a | git log --grep="integrate(A-06)" |
| A-07 | ae8d0e3e4a02ea36a357b990d7e6d62e8326f3d1 | e58ac323b47f | git log --grep="integrate(A-07)" |
| A-08 | c18f5fd14fd57c308b1d8e42128cbbb063a4ef74 | b867f1f24233 | git log --grep="integrate(A-08)" |
| A-09 | ec82a8154aeaf956305e08c493e07c4736dcf1de | 9c93960aee60 | git log --grep="integrate(A-09)" |
| A-10 | a93ae583b468e7d61c4efe63d7609ff83ee4bed1 | 18233ddf6c7b | git log --grep="integrate(A-10)" |
| A-11 | 66e0591dc74b4f2e09b005c2cd4715f74b06280c | 8425147edd1b | git log --grep="integrate(A-11)" |
| A-12 | bad89e191f3ddd653febc2626eb80d813c93f8b8 | 044cdf1a9075 | git log --grep="integrate(A-12)" |
| A-13 | ccfd11131d7f8e8dd6a5340ac48d8a2e16c7111d | b46a5591d574 | git log --grep="integrate(A-13)" |
| A-14 | 4efa4f6c3d3a11b7610bcd06707fe8105e3933e0 | 4d292f278aab | git log --grep="integrate(A-14)" |
| A-15 | 11128dc8b3f7d27b885d3f6e3803c5822c6ed468 | b09724147f4a | git log --grep="integrate(A-15)" |
| A-16 | bfc0d32e2bbe8f897229b9b87d77f91f200f3e9d | 1f2f3d17bd69 | git log --grep="integrate(A-16)" |
| A-17 | 3529edc34d9444d9629a3191c34dc07ab72a2d07 | a5f13fc184bb | git log --grep="integrate(A-17)" |
| A-18 | 773af60b0f148d6212f261abeb57c71fb5bde4b7 | ba3370b8578b | git log --grep="integrate(A-18)" |
| A-19 | b75a132ef7ab944d785b8c39ff0295584d547a39 | de07c98c6b4f | git log --grep="integrate(A-19)" |
| ADAPT-DEPS | fb7bca7f0d6c40142ca623d40b6e1921340e4abe | 0db5b62042e2 | git log --grep="integrate(ADAPT-DEPS)" |
| ADAPT-A | 985d542dbaf148d76d1651ddedb0bf448a7a312c | fbb90573e8f9 | git log --grep="integrate(ADAPT-A)" |
| ADAPT-D | 69cf7ce8e28c8cebb26a97eabb289c84feb5eeef | 747cf2ba3e58 | git log --grep="integrate(ADAPT-D)" |
| ADAPT-E | 97a13ddd384c486c5b8b9367d3e36c1f96b5f92b | 734c02ce1499 | git log --grep="integrate(ADAPT-E)" |
| ADAPT-E-MEDIA | 5dcf3d5c3252f884a812932b3d8ab5a61493439f | 5c632b65335d | git log --grep="integrate(ADAPT-E-MEDIA)" |
| ADAPT-F | 4c4486a9cd1e38a91d0374530933aa3860fb6a5a | 54bf210b7df8 | git log --grep="integrate(ADAPT-F)" |
| ADAPT-J | b5550a06a10d64c33eedc74d28b19569c431dfb2 | fb5ef89cb2ff | git log --grep="integrate(ADAPT-J)" |
| ADAPT-I | fbbe798a06d4030f1dfc8a48399af5ffb704d15e | 8b142a0a7ecc | git log --grep="integrate(ADAPT-I)" |
| ADAPT-CONFIG | fe206ac52815f87769890b77efc7d8c51807528f | 2680d83e4f06 | git log --grep="integrate(ADAPT-CONFIG)" |
| ADAPT-WIRE | a046fa4c6784cd1ea3fcf1900e769b6bee3a9863 | f4e443d18434 | git log --grep="integrate(ADAPT-WIRE)" |
| ADAPT-SEED | 497a06b5f0f0783ea42200cb35f0f922f2cad09d | b97c9596725d | git log --grep="integrate(ADAPT-SEED)" |
| ADAPT-PROD | 790f768269fd2e1218fdeb7aec82621dfa415827 | 62c610c36106 | git log --grep="integrate(ADAPT-PROD)" |
| ADAPT-LAUNCH | cc290f002074514001fa0b03b3eb8c9e00c14db6 | faa54f225bdc | git log --grep="integrate(ADAPT-LAUNCH)" |
| B-1 | 91878d46206a05e052217b54e81af614b6ba1bf7 | 92dbcc6f018b | git log --grep="integrate(B-1)" |
| B-2 | 1a17e1181c6049618d93b905126c58cae5d21877 | 5d34dbaf7d91 | git log --grep="integrate(B-2)" |
| B-3 | 8434f096979606c15fb444c498f08dd109e56bc3 | c478e5d6c957 | git log --grep="integrate(B-3)" |
| B-4 | 0ad4cbf564484cec02bbeffa18ea3796349b4a91 | 5f6e0fc76525 | git log --grep="integrate(B-4)" |
| B-5 | ec66302c0da0adcc0f99de10a983a393563851de | 318d6e6731a1 | git log --grep="integrate(B-5)" |
| B-6 | 76b81ca29ac1159d4bd6f685da478df9e0911b3b | b862577c5ac2 | git log --grep="integrate(B-6)" |
| B-7 | 94f50610690a94c567ca47980922cc8c7d78b132 | 357fbc957082 | git log --grep="integrate(B-7)" |
| B-8 | f464d5b05de813f4b542d8f01d1ced48dbeff0a5 | 02aef71e0d5c | git log --grep="integrate(B-8)" |
| B-9 | 5a12c257a1f46ad4695d51e161104e9784ed76a2 | 45cd8a8a1a7b | git log --grep="integrate(B-9)" |
| B-10 | a8914387d3e3f8cdc322baa06c0d2b23650d5560 | 309798fc096d | git log --grep="integrate(B-10)" |
| B-11 | d1961a482f8f04364c3edb98c562cb98b126193d | bb3b1e14ff81 | git log --grep="integrate(B-11)" |
| B-12 | c8514bd1ba916e7be55561659dce0661e7c7e81e | 3d5c8467b4ec | git log --grep="integrate(B-12)" |
| C-01 | 5b5d282e1862f8ff9a19831147bcf3ceec7fcf7e | bc1144fa816a | git log --grep="integrate(C-01)" |
| C-02 | 003d991458706b63f97573b39567fe29574cc6cb | c6d6afa65c61 | git log --grep="integrate(C-02)" |
| C-03 | be1fa2ef1c1cfa31173aee1c6dff878ac2793b02 | 06c42477bb10 | git log --grep="integrate(C-03)" |
| C-04 | 354d46c041501b32c8df147af1728c3915df65f4 | af457adf2c1e | git log --grep="integrate(C-04)" |
| C-05 | cbd256247045936fd2b5b07c3eca8fbfac7b737d | 7dcf357e5b8f | git log --grep="integrate(C-05)" |
| C-06 | 2233e36f669f9ea4d8ffdd9b0724aa8c9fe19753 | b6fc4471c652 | git log --grep="integrate(C-06)" |
| C-07 | 9207e232ceb28c85c8da32f8eec9a7b9866be53d | 46d398a3abf6 | git log --grep="integrate(C-07)" |
| C-08 | 4f956426cf8a28182acd5cba47ceebe368f9908f | 71e745c7add3 | git log --grep="integrate(C-08)" |
| C-09 | a800f8790e9eee9937165c13b020d33b39739dc2 | 8831823a18f2 | git log --grep="integrate(C-09)" |

### 3.3 Gói hội tụ, D, E, F

Danh sách gói của brief R3 kết thúc ở E-05 (dấu phẩy cuối cho thấy danh sách bị cắt); các hàng E-06..E-20 và F-01..F-07 dưới đây là bổ sung giữ từ bản R2, không thuộc danh sách yêu cầu.


| Mã gói | Commit integrate (SHA đầy đủ) | Candidate (12 hex) | Cách tra |
| --- | --- | --- | --- |
| CP-4-EVENT-KINDS | 428e3dd9bf22027f418228464784576beefe396c | 6c91a490b2b1 | git log --grep="integrate(CP-4-EVENT-KINDS)" |
| CP-4-PAGINATION | 4412a0afad9f40096fff00f17903043636d14bd7 | 995e98542fd6 | git log --grep="integrate(CP-4-PAGINATION)" |
| CP-4-QUERIES | ed3bf7a48207198201b4c76965557afdc12702c6 | c7e02fef94c2 | git log --grep="integrate(CP-4-QUERIES)" |
| CP-4B-UI-SCREENS | a8533a71456b3ce573fcb8bbe68b2a21729e863d | 3aa670cd9779 | git log --grep="integrate(CP-4B-UI-SCREENS)" |
| CP-2B-RUNTIME-PATHS | bdb8d794001b81511f33451e17e200d6713ff9ea | 6ec64fbb85aa | git log --grep="integrate(CP-2B-RUNTIME-PATHS)" |
| CP-2B-PACKAGES | 3e15f146f9cd926403173a6b63d70db747090450 | fa3a6a14ddc3 | git log --grep="integrate(CP-2B-PACKAGES)" |
| CP-2D-REGISTRY | 2f3e42ef4e9d752735d67544a18bbeb0bda192c6 | 87f32a597cc7 | git log --grep="integrate(CP-2D-REGISTRY)" |
| CP-3C-STATE-EDGES | 2d8a9686da7c7261d67a406c153a912d3f4de36d | bf68ad98e494 | git log --grep="integrate(CP-3C-STATE-EDGES)" |
| CP-5-COMPLETION | a59b9d8bba79216713b40bac3848da2adc0095b5 | f17273076ac3 | git log --grep="integrate(CP-5-COMPLETION)" |
| CP-6-WORKFLOW | 638abf7837d5706bb29223704a152b973f854951 | a16dad6229eb | git log --grep="integrate(CP-6-WORKFLOW)" |
| CP-2B-DEPS | b10dc7c86fc396f9aee9c3a03586c1d883cdc661 | 8cda6c756f76 | git log --grep="integrate(CP-2B-DEPS)" |
| CP-2C-M2-REGRESSION | 0e54a54e8700855d095ebac8267b1474ab878455 | 302b16965aec | git log --grep="integrate(CP-2C-M2-REGRESSION)" |
| CP-3B-STATE-MACHINE | 0adb2bbd0ee4140dd8cf3650ea9b7ffb6ca4b450 | b3a040ffd687 | git log --grep="integrate(CP-3B-STATE-MACHINE)" |
| CP-3-MIGRATIONS | a3d84e838a0937515eb62eb5c3a35016ab88e7df | b33cdd34eb40 | git log --grep="integrate(CP-3-MIGRATIONS)" |
| CP-4-WIRING | 750195f1a88ee5bc731893d8986992b7b97c442b | 06b6d6b453ca | git log --grep="integrate(CP-4-WIRING)" |
| CP-4B-UI-SHELL | 42c328c98f7c0890d01fb3a590bf43a3f78eb2fb | 858d8179ba66 | git log --grep="integrate(CP-4B-UI-SHELL)" |
| D-01 | 1d56b2699f6f6a2c08346da3db1107e435c234eb | b2a81a892125 | git log --grep="integrate(D-01)" |
| D-02 | d525f9275b0a5062b673d0b307b2707f98d26e12 | 9ca090a7b919 | git log --grep="integrate(D-02)" |
| D-03 | cf44f24a63971600a198a9afdf7d8a35421fb248 | eaa8dad378e7 | git log --grep="integrate(D-03)" |
| D-04 | dff70cc63be1c08c1cd33a4856a39deea7483523 | 7ea9f67e12da | git log --grep="integrate(D-04)" |
| D-05 | bdd2916e35e1c907d1141a1139e872690b2e5acb | 27f7dadb9233 | git log --grep="integrate(D-05)" |
| D-06 | 91000e325c7a72572aec729d3bcfc8ed20c1ae51 | fcf0147eb038 | git log --grep="integrate(D-06)" |
| D-07 | 5646473e81669af7143ea98e81869927ec761f5f | 324777971bf3 | git log --grep="integrate(D-07)" |
| D-08 | 1b44a9460b1f18e33309cd4255c2e50e4552a470 | 6db601c34c55 | git log --grep="integrate(D-08)" |
| D-09 | 4aeaf9fb552e1c717c20614cbd9ab2487ff850fc | acf373e72ef9 | git log --grep="integrate(D-09)" |
| D-10 | 89b0e328f18b9ad438dd217044c116ad0c386501 | b90570d461a7 | git log --grep="integrate(D-10)" |
| D-11 | 8797e8d2cf79002f4b080dfefbbbeaa945cd687a | 538fd130d1ae | git log --grep="integrate(D-11)" |
| D-12 | 3e6932884111da7ec41d854a3f39708a626c49aa | 14c9b16f8362 | git log --grep="integrate(D-12)" |
| D-13 | 8123aba43315b3c836df2740aeb5fd25b017214d | e25a63a8afb9 | git log --grep="integrate(D-13)" |
| D-14 | bcda8664b9621875d25ba2359b95d3d0360a36b2 | fe635dd2c6ef | git log --grep="integrate(D-14)" |
| D-15 | 7f5cb179669672e1f0a9f77430534c3826e76a20 | 7223acde4dbf | git log --grep="integrate(D-15)" |
| D-16 | 8c66d619acbc12c4a6c202c8cdb4ca8e26447e9f | 49e5a2845818 | git log --grep="integrate(D-16)" |
| D-17 | 4645f6217894c6b873cbfe5576c4b1ae8aaf0d23 | b94526322ad9 | git log --grep="integrate(D-17)" |
| D-18 | febeb176885bf16a5e27f5a2b344a8480a25f0c9 | 669f67fa1840 | git log --grep="integrate(D-18)" |
| E-01 | 170b96b2748929758f96d9b5a54726be29fb7600 | c1e0e06e1f98 | git log --grep="integrate(E-01)" |
| E-02 | dd68637ba76c9e3213de9b564226e2e69f35f230 | 683e3e8396c4 | git log --grep="integrate(E-02)" |
| E-03 | 3f89da586c1ffc46c04d3a3f2793f0c0921d24fd | c426045eb0f9 | git log --grep="integrate(E-03)" |
| E-04 | f54199a752a19475f567738a7c70eb108d583316 | 7a2fb4c4fc40 | git log --grep="integrate(E-04)" |
| E-05 | 3f026bb8ba5c01a566dde9fffcc0480c727dcdf3 | 880bb810bb04 | git log --grep="integrate(E-05)" |
| E-06 | d3887fa6a224395ad1e37e00e866a8e7def930e0 | da1e6a7ba167 | git log --grep="integrate(E-06)" |
| E-07 | 2e7c6b1ca42d83ed16dac720ca98388b1bd06ecc | a8abf025014b | git log --grep="integrate(E-07)" |
| E-08 | 1bfb8b02dc928a2455330afa45edc768226a63e5 | 8dfaedb513d4 | git log --grep="integrate(E-08)" |
| E-09 | c695121600c8d1b73e9153cbd26dab92cf2f6b18 | 8c4ed2542c25 | git log --grep="integrate(E-09)" |
| E-10 | af9306a233fc2bed399d696fb87918f5c8e7dfe0 | 237353be4524 | git log --grep="integrate(E-10)" |
| E-11 | 6945c76b1b309084663e2e0a6b2b668bebad88fc | 37b5acbde850 | git log --grep="integrate(E-11)" |
| E-12 | 9d7459596ab9d0f69020c644c437b6523ffec755 | 1d8150785261 | git log --grep="integrate(E-12)" |
| E-13 | ccbfbb5771f4b8bca783f3d2c94cbcc7f328d5b4 | cd3796837303 | git log --grep="integrate(E-13)" |
| E-14 | cab81bda5c60f7c120126d832d4b48e0765315cf | 3ac7c2fb4883 | git log --grep="integrate(E-14)" |
| E-15 | ab7cb613044212edf40e03817b75d6d648823269 | b395a9b7f9fa | git log --grep="integrate(E-15)" |
| E-16 | cbb7507a6df2fec1b8283ce63fcc82cca963f8fc | 55f2c4d92d1e | git log --grep="integrate(E-16)" |
| E-17 | 4ee2962f959ced2455af2cbb0642655d7f076c57 | 60a514f00404 | git log --grep="integrate(E-17)" |
| E-18 | 5734017c335265c0e32a214e7a59fa7c2d0b6010 | 457083608ac4 | git log --grep="integrate(E-18)" |
| E-19 | 1f6f35d6bfb9063eb24c83d688e22821842c5e67 | fff0f48af09c | git log --grep="integrate(E-19)" |
| E-20 | 48769ce5899afb3c275f6efb37ff9dea215154e2 | 997405b26808 | git log --grep="integrate(E-20)" |
| F-01 | 4daa3e625fcac2d0d28a1bf01f925467fd958ff7 | 603f5de01b5a | git log --grep="integrate(F-01)" |
| F-02 | 6edd27271fc7408d857d4dcaafbfbae308c7f73f | ba2e313d5b1f | git log --grep="integrate(F-02)" |
| F-03 | cfd868a1406b38b34a1c05230e60b26e82692726 | f9a57ed36fe6 | git log --grep="integrate(F-03)" |
| F-04 | 96f8e85c90b97cb6e0effeafa1cfca92c35fb8d4 | 2c76c72dcb34 | git log --grep="integrate(F-04)" |
| F-05 | 100bfcb0fcfcc4b9940c5c07a9b4afa82e1f9a45 | 8516288f5417 | git log --grep="integrate(F-05)" |
| F-06 | 7622e01f50b6257f93a5c0b90f84880b5c9bf952 | c28e40d61e92 | git log --grep="integrate(F-06)" |
| F-07 | b8dc82489eb61f7e284e02ab8d4e0be7b817fc27 | d70d7c536116 | git log --grep="integrate(F-07)" |

### 3.4 Gói có lệnh kiểm nhưng không nằm trong danh sách liệt kê

Brief R3 không liệt kê tường minh các gói E-06..E-20, F-01..F-22 cùng các slice thuộc phân hệ G, H, I, J; tuy nhiên toàn bộ lệnh kiểm của milestone M6 vẫn chạy đầy đủ các bài test tương ứng của chúng (`tests/unit/render/test_f08..f22`, `tests/unit/orchestration/test_g_*`, `tests/unit/control_ui/test_h_*`, `tests/unit/storage/test_storage_*`, `tests/unit/config/test_j_*`).

Kết quả tra cứu `git log` chỉ đọc cho nhóm F-08..F-22 và các phân hệ G, H, I, J trên nhánh hiện tại như sau:

- `F-08`: commit integrate `95efd236a7bf8b07dc6c0aae751d1992d2c8ef5b`
- `F-09`: commit integrate `c8cfa82317412bd023f3e19e9134f470f4fb5fce`
- `F-10`: commit integrate `4bbe03d06091909a4ca31ac63850a4dc94ce20fe`
- `F-11`: commit integrate `580a981df3450c85f49558ead2a486b77ed3e68c`
- `F-12`: commit integrate `6f1cf65b2e2c822f84fc951158bd3086a65cd758`
- `F-13`: commit integrate `d5e2573211069e1d7d212fead48a5fcdd70c26f3`
- `F-14`: commit integrate `4dc0964ce286447d5d95987b402d08b9e99cdfa5`
- `F-15`: commit integrate `8fc0a24d980ad0de18f4f5e34542151e971a842b`
- `F-16`: commit integrate `a5ed0e1569a24c7699bc0a184c47b9a500f30e17`
- `F-17`: commit integrate `d7f79a2aca73e091126fa1b788d4668b9801b0b3`
- `F-18`: commit integrate `4381df15795a818cc8c774b84e55fe7b923237d3`
- `F-19`: commit integrate `b6a4796674c86648798f1a5c41e263246acbba49`
- `F-20`: commit integrate `d6244988169563ae638cf419c73fafb43ff04a7a`
- `F-21`: commit integrate `b61497009eccadcef157bc797e4eb1f9263b7f63`
- `F-22`: commit integrate `bf52905b3b8547f82a51aa2ccc926f7b7ae1b0bc`

- Phân hệ G (Orchestration): Tìm thấy 14 commit integrate trong lịch sử nhánh (ví dụ G-10 tại `cadafb45237be7442988df322083e02b491994c3`, G-14 tại `41b999dd3ba9a7e7cb6f4ca02aebf167fb909e07`).
- Phân hệ H (Control UI): Tìm thấy 19 commit integrate trong lịch sử nhánh (ví dụ H-12-FIX1 tại `202e0d1fd3e643f985e17c3f2c909116807b2a95`, H-04-FIX1 tại `bf23e4aea5cae41f0017184fe5a48ef7cd2e7fcc`).
- Phân hệ I (Storage): Tìm thấy 13 commit integrate trong lịch sử nhánh (ví dụ I-11 tại `6437cb96a4bad8941038406360ac3cab6f307385`, I-12 tại `49a6b2cd63f58127a65fa105b13ced917a842f2d`).
- Phân hệ J (Config & Security): Tìm thấy 19 commit integrate trong lịch sử nhánh (ví dụ J-09-FIX1 tại `c10efaaeec9791999472d38b60eb8a3bf1b77962`, J-18 tại `01da3b296de9dc5ac3313df6780f1d09fb7e1e0e`).

*Lưu ý:* các gói F-08..F-22 và slice G, H, I, J không nằm trong danh sách yêu cầu nghiệm thu của task nhưng mã và test của chúng đã tích hợp vào mã được kiểm; các bài test tương ứng nằm trong Chuỗi 11 đến 13 của command-results.md.

## 4. Gói cổng và bản ghi quyết định

| Mã cổng | recordHash (bản ghi quyết định RELEASE) | Nguồn |
| --- | --- | --- |
| GATE-CP-2D-REGISTRY | 00103f0a72d7b9e2f1f5803cc699db79373ac38ed2e47aa206f975da0eab9514 | Control cấp trong brief nghiệm thu |
| GATE-CP-5-COMPLETION | 3b9e4c9d779043c2f76022541f4524b931ad48cce3cad2e4bc4dfff7cfb54d90 | Control cấp trong brief nghiệm thu |
| GATE-CP-6-WORKFLOW | 2be7562bea521bede4812d8b5cff124d201b562b93a416b1972baca08d720190 | Control cấp trong brief nghiệm thu |
| GATE-CP-2B-DEPS-PATHS | 3bd11714d6cb8196cb1c800bc740a76e7a4436b905cb2c98d2a8400fa1d132cf | Control cấp trong brief nghiệm thu |
| GATE-PERSIST-A | 1ccf6c904ef88886ed1dd7a66b50c2206fd1c12ac5357d926572dbf53135a343 | Control cấp trong brief nghiệm thu |
| GATE-PERSIST-B | 39f5e7e8bc503704574da52b3605d1a03911b24c29494514c865af229ca35bf4 | Control cấp trong brief nghiệm thu |
| GATE-PERSIST-C | 5327ae192465197cc63aa6f6e1ebc4670e06c063f6a1fb46a4b7e6a3ce4066f2 | Control cấp trong brief nghiệm thu |
| GATE-PERSIST-D | 794e8b5634d3adaab3d35154ae2f0d732f2dc86a477ca8faeb2cd10cbd79506f | Control cấp trong brief nghiệm thu |
| GATE-PERSIST-E | b38673dd8c05bac07daae786cf282bcbae1cb359ea80fcd24b806bf5eab94ae7 | Control cấp trong brief nghiệm thu |
| GATE-PERSIST-F | 7254c80039939250ee1d2b372b627655b8b60b998372d7c9652b4360042a9055 | Control cấp trong brief nghiệm thu |
| GATE-PERSIST-G | f71b035ffeface811ea87ccc06ba8a13129922fed922018793672d14d244fe7d | Control cấp trong brief nghiệm thu |
| GATE-PERSIST-I | b987fc8b60eaddba804f31ce51c78cfc9047db41d42203882ea5fae37c31843e | Control cấp trong brief nghiệm thu |
| GATE-PERSIST-J | cc9e80f551c0a83996a2ff710c7ce2d8d73517eed0434d4c176e55403d1399de | Control cấp trong brief nghiệm thu |

Các gói cổng không có SHA tích hợp; Control thả mỗi cổng bằng một bản ghi quyết định RELEASE và recordHash ở trên được chép nguyên văn từ brief nghiệm thu của Control. Báo cáo không đọc sổ quyết định của Control và không mở .ai-pm/**.

## 5. Kết quả lệnh kiểm

Toàn bộ 288 đoạn lệnh kiểm của milestone M6 đã được thực thi và kiểm tra lại trên candidate HEAD 8167d4ca8a6a5f46bcf4adc1d3ed48f0472ce4e1 qua 14 chuỗi lệnh:

- Chuỗi 1: 12/12 đoạn exit 0 (kế hoạch phân hệ A, B, C, I, D, E, F, J, G, H, convergence và git diff --check)
- Chuỗi 2: 2/2 đoạn exit 0 (kế hoạch convergence-ext và persist)
- Chuỗi 3: 2/2 đoạn exit 0 (kế hoạch adapt và convergence-ext-ui)
- Chuỗi 4: 18/18 đoạn exit 0 (migration, wiring, persist G, completion UoW, adapt wire, queries routes, probe catalog và prod)
- Chuỗi 5: 1/1 đoạn exit 0 (npm run build giao diện)
- Chuỗi 6: 12/12 đoạn exit 0 (control_ui, dist, screenRegistry, catalog hooks, persist C, hooks module)
- Chuỗi 7: 42/42 đoạn exit 0 (19 test phân hệ A, thư viện pyproject và uv.lock, adapter thật A D E F J I, config, wiring, seed, launch)
- Chuỗi 8: 22/22 đoạn exit 0 (12 đoạn ingestion B, 8 test catalog C, stream và SSE)
- Chuỗi 9: 21/21 đoạn exit 0 (event catalog, phân trang, queries, runtime.lock, packaging, contract registry, state machine)
- Chuỗi 10: 14/14 đoạn exit 0 (orchestration và storage, workflow cp6, pyproject, M2_ACCEPTED_SHA, hồi quy m2 và integration, main.py, dist, App.tsx)
- Chuỗi 11: 38/38 đoạn exit 0 (D-01..D-18 và E-01..E-20)
- Chuỗi 12: 36/36 đoạn exit 0 (F-01..F-22 và test điều phối G)
- Chuỗi 13: 46/46 đoạn exit 0 (test giao diện H, lưu trữ I, cấu hình và bảo mật J)
- Chuỗi 14: 22/22 đoạn exit 0 (persistence PostgreSQL A..J, probe adapter, probe trace, AST boundary)

Tổng hợp: **288/288** đoạn lệnh kiểm exit 0.

Hiệu đính vòng R3 theo finding F1: cột Dòng tóm tắt của command-results.md ở bản trước chép trùng một dòng cho nhiều đoạn pytest khác nhau (144/259 hàng lệch so với output thật). Cột này nay được chép lại từ output thật của từng đoạn pytest, chạy riêng từng đoạn trên mã 8167d4ca8a6a5f46bcf4adc1d3ed48f0472ce4e1 bằng interpreter khoá của lane. Hai đoạn nặng giữ kết quả cũ đã được Auditor (Opus 5.5) đối chiếu đúng: Chuỗi 9 hàng 4 (tests/m2: 179 passed, 1 deselected) và Chuỗi 10 hàng 10 (tests/m2 cùng tests/integration: 2313 passed, 35 skipped, 1 deselected). HEAD hiện tại b71fde02bd102bed9cc40e5c697e5e7bcd43bf0d chỉ khác 8167d4c ở hai tệp .md trong docs/delivery-evidence/m6-milestone-close nên mã và test không đổi; số exit 0 vẫn là 288/288.

*Lưu ý quan trọng:*
1. Lệnh kiểm test_h36_m1_regression được hoãn sang CP7 theo quyết định của user ngày 21/10/2026 nên các lệnh liên quan mang cờ --deselect, không phải là lỗi kiểm thử.
2. Các bài test tích hợp trong bộ test chạy bằng fake, mock và fixture nội bộ; các test bị skip vì môi trường thiếu PostgreSQL hoặc tài nguyên ngoài không được coi là bằng chứng tài nguyên thật (GPU, TTS, Drive, Temporal), bằng chứng thật sẽ được thu thập tại CP7.

## 6. Đối chiếu exit gate M6 trong roadmap

| Mã | Nội dung exit gate (docs/11-roadmap.md mục 12) | Trạng thái | Evidence |
| --- | --- | --- | --- |
| M6-EG1 | Tạo được R4 Video Alpha theo luồng giám sát từ snapshot đến completion | PENDING_USER_CHECKPOINT | Cần GPU/TTS/FFmpeg/Drive thật ở CP7; evidence mã nguồn: test_f18_render_video_pipeline.py (Chuỗi 12 hàng 18), test_cp6_video_production_flow.py (Chuỗi 10 hàng 3), test_e16_voice_timing_pipeline.py (Chuỗi 11 hàng 34) chỉ chứng minh luồng với fake, không thay evidence thật |
| M6-EG2 | Không output nào được đếm trước cloud verification | PASS | Toàn bộ lệnh kiểm liên quan exit 0: tests/unit/storage/test_storage_cloud_persist.py (Chuỗi 13 hàng 19), tests/unit/orchestration/test_g_completion_gate.py (Chuỗi 12 hàng 31), tests/integration/orchestration/test_g_commit_completion.py (Chuỗi 12 hàng 32), tests/integration/render/test_f20_worker_activity.py (Chuỗi 12 hàng 20) |
| M6-EG3 | Không local output bị xóa khi sync/completion chưa đủ | PASS | Toàn bộ lệnh kiểm liên quan exit 0: tests/unit/storage/test_storage_cleanup_evaluation.py (Chuỗi 13 hàng 23), tests/integration/storage/test_storage_cleanup_executor.py (Chuỗi 13 hàng 24), tests/unit/storage/test_storage_reconciliation.py (Chuỗi 13 hàng 25) |
| M6-EG4 | F không tự đổi script/góc/media ngoài fallback plan | PASS | Toàn bộ lệnh kiểm liên quan exit 0: tests/unit/render/test_f05_resolve_package.py (Chuỗi 12 hàng 5), test_f06_preconditions_hooks_timeline.py (Chuỗi 12 hàng 6), test_f07_preconditions_artifacts_language.py (Chuỗi 12 hàng 7), test_f08_validate_package.py (Chuỗi 12 hàng 8), test_f18_render_video_pipeline.py (Chuỗi 12 hàng 18) |
| M6-EG5 | G06 phần TTS/timing/media và G07 phần output/QC có evidence | PENDING_USER_CHECKPOINT | Cần evidence trên tài nguyên thật ở CP7; evidence với fake đạt exit 0: test_e09 đến test_e12 (Chuỗi 11 hàng 27..30), test_f12 đến test_f15 (Chuỗi 12 hàng 12..15) |
| M6-EG6 | User duyệt E-F và 5 preset mẫu; user nghe mẫu và duyệt hình | PENDING_USER_CHECKPOINT | User chưa duyệt, không tự ghi là đã duyệt; chờ nghiệm thu người dùng tại CP7 |

Ánh xạ CP7: docs/implementation/cp7/plan.md dòng 41..43 gán M6-EG1 cho RG-09, M6-EG5 cho RG-05, RG-06, RG-07, M6-EG6 cho R4 (user duyệt); bảng đó ghi mã gói M6-MILESTONE-CLOSE-R2, mã gate không đổi ở R3.

Ghi chú theo quyết định của user (2026-10-22, ai-setup decide):
Exit gate của roadmap rộng hơn kế hoạch đã duyệt chỉ được ghi chú trong báo cáo đóng mốc, không phải FAIL và không hỏi user. Việc kế hoạch đã duyệt có mà chưa nối do Control tự lập gói sửa.
Các mục mở liên quan theo docs/11-roadmap.md (dòng 528..542, cần chốt trước khi hoàn tất exit M6 tại CP7):
- QUALITY-OPEN-006/TEST-OPEN-005: output profile chính thức.
- QUALITY-OPEN-007/TEST-OPEN-006: ngưỡng sai số word timing.
- Tên, style và thông số chi tiết của 5 preset.
- Audio quality/visual continuity thresholds dùng cho warning hoặc hard gate.

Roadmap có sáu exit gate, kế hoạch đã duyệt chưa chứng minh gate nào ngoài sáu gate này nên không có gate nào phải ghi chú là rộng hơn kế hoạch.

## 7. pendingUserCheckpoint

Chỉ gồm đúng 3 mã gate sau được đưa vào danh sách chờ kiểm tra/nghiệm thu người dùng theo đúng quy định:
1. M6-EG1: Tạo được R4 Video Alpha theo luồng giám sát từ snapshot đến completion — Cần chạy trên tài nguyên thật (GPU/TTS/FFmpeg/Drive) tại CP7.
2. M6-EG5: G06 phần TTS/timing/media và G07 phần output/QC có evidence — Cần thu thập bằng chứng vận hành trên tài nguyên thật tại CP7.
3. M6-EG6: User duyệt E-F và 5 preset mẫu; user nghe mẫu và duyệt hình — Chờ người dùng trực tiếp nghiệm thu chất lượng mẫu video, audio và preset.

## 8. Kết luận

Trạng thái: **ĐẠT** về kỹ thuật và kiểm thử trên mã 8167d4ca8a6a5f46bcf4adc1d3ed48f0472ce4e1: 288/288 lệnh kiểm exit 0, mọi gói được bao phủ có SHA tích hợp, 13 gói cổng có recordHash do Control cấp, M6-EG2/EG3/EG4 PASS. Ba gate M6-EG1, M6-EG5, M6-EG6 ghi vào pendingUserCheckpoint, chờ tài nguyên thật và duyệt của user ở CP7.

Báo cáo không thay đổi trạng thái roadmap (docs/11-roadmap.md) hay checklist (docs/12-pre-code-checklist.md).

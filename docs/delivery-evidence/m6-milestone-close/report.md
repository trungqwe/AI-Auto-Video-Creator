# Báo cáo đóng M6 (revision 2): M6-MILESTONE-CLOSE-R2

## 1. Phạm vi và lý do R2

Revision 1 M6-MILESTONE-CLOSE đã đóng mà không tích hợp; Control 20/10/2026 chốt policy v1 thêm bốn dòng kế hoạch CONVERGENCE-EXT, CONVERGENCE-EXT-UI, PERSIST, ADAPT vào phạm vi đóng M6; revision 1 đóng băng phạm vi cũ và chưa giao Worker nào nên dù chạy xong vẫn phải đóng lại ở R2; retire R1 để đóng M6 đúng một lần ở R2 với đủ phạm vi theo chấm điểm chi phí và đường găng: bớt một lượt đóng, trả suất cho gói kế hoạch.

## 2. Candidate được kiểm

HEAD cc290f002074514001fa0b03b3eb8c9e00c14db6, nhánh trungqwe/lane-m6-milestone-close-r2; mọi lệnh kiểm chạy trên đúng HEAD này bằng interpreter khoá của lane.

## 3. Gói được bao phủ và SHA tích hợp

### 3.1 Gói kế hoạch và gói sửa

| Mã gói | Commit integrate (SHA đầy đủ) | Candidate (12 hex) | Cách tra |
| --- | --- | --- | --- |
| M6-EF-PLAN | KHÔNG TÌM THẤY | KHÔNG TÌM THẤY | git log --grep="lane-m6-ef-plan" |
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

Danh sách gói của brief kết thúc ở F-07 và không liệt kê tường minh các gói F-08..F-22 cùng các slice thuộc phân hệ G, H, I, J; tuy nhiên toàn bộ lệnh kiểm của milestone M6 vẫn chạy đầy đủ các bài test tương ứng của chúng (`tests/unit/render/test_f08..f22`, `tests/unit/orchestration/test_g_*`, `tests/unit/control_ui/test_h_*`, `tests/unit/storage/test_storage_*`, `tests/unit/config/test_j_*`).

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

*Lưu ý:* Việc không liệt kê F-08..F-22 và các slice G, H, I, J trong danh sách yêu cầu nghiệm thu của task là theo đúng phạm vi phân bổ ban đầu của brief; toàn bộ mã nguồn và test của các gói này đã tích hợp đầy đủ vào candidate và vượt qua toàn bộ lệnh kiểm bắt buộc.

## 4. Gói cổng và bản ghi quyết định

| Mã cổng | recordHash (decisions.jsonl) | Nguồn |
| --- | --- | --- |
| GATE-CP-2D-REGISTRY | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-CP-5-COMPLETION | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-CP-6-WORKFLOW | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-CP-2B-DEPS-PATHS | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-PERSIST-A | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-PERSIST-B | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-PERSIST-C | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-PERSIST-D | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-PERSIST-E | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-PERSIST-F | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-PERSIST-G | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-PERSIST-I | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |
| GATE-PERSIST-J | THIẾU: Control chưa cấp recordHash | Không có trong vật liệu Control cấp |

Các gói cổng không có SHA tích hợp; mã bản ghi quyết định là recordHash trong decisions.jsonl đã thả từng cổng. Nguồn hợp lệ duy nhất của recordHash là vật liệu Control cấp cho phiên này (prompt, tệp trong owned paths hoặc đầu ra lệnh được giao); tệp decisions.jsonl nằm dưới .ai-pm/** là đường cấm của task nên không được mở.

## 5. Kết quả lệnh kiểm

Toàn bộ 274 đoạn lệnh kiểm của milestone M6 đã được thực thi đầy đủ trên candidate HEAD `cc290f002074514001fa0b03b3eb8c9e00c14db6` thông qua 9 chuỗi lệnh:
- **Chuỗi 1:** 12/12 lệnh đạt exit 0 (kiểm tra tài liệu kế hoạch các phân hệ A, B, C, I, D, E, F, J, G, H, Convergence và git diff --check).
- **Chuỗi 2:** 12/12 lệnh đạt exit 0 (kiểm tra tài liệu Convergence-Ext, Persist, Adapt, chuỗi migration, hồi quy M2 p9, UoW completion và wiring).
- **Chuỗi 3:** 36/36 lệnh đạt exit 0 (kiểm tra Convergence-Ext-UI, 19 bài test phân hệ A, thư viện uv.lock/pyproject và adapters thực tế A, D, E, F, J, I).
- **Chuỗi 4:** 45/45 lệnh đạt exit 0 (kiểm tra adapt config/seed/prod/launch, 12 bài test ingestion B, 9 bài test catalog C, API queries, pagination, SSE streams, build UI dist và screen registry).
- **Chuỗi 5:** 25/25 lệnh đạt exit 0 (kiểm tra runtime pins, packaging, contract bindings, state machines, workflow static/catalog, toàn bộ suite unit/integration hồi quy M2).
- **Chuỗi 6:** 38/38 lệnh đạt exit 0 (18 bài test phân hệ sáng tạo D-01..D-18 và 20 bài test giọng đọc/timing E-01..E-20).
- **Chuỗi 7:** 52/52 lệnh đạt exit 0 (22 bài test render F-01..F-22, 14 bài test điều phối G-01..G-14, 16 bài test giao diện H-01..H-16).
- **Chuỗi 8:** 31/31 lệnh đạt exit 0 (13 bài test lưu trữ Storage Meta và 18 bài test cấu hình/bảo mật Config Security J-01..J-18).
- **Chuỗi 9:** 23/23 lệnh đạt exit 0 (10 bài test persistence PostgreSQL cho các phân hệ, các probe hợp đồng/trace TST-/QR-/CT-, và kiểm tra AST boundary rules).

Tổng hợp: **274/274 lệnh exit code 0**. Chi tiết từng lệnh, exit code và dòng tóm tắt được ghi đầy đủ tại [command-results.md](command-results.md).

*Lưu ý quan trọng:*
1. Kiểm thử `tests/m2/test_p7b_hardening.py::test_h36_m1_regression` được hoãn sang CP7 theo quyết định của user ngày 21/10/2026, do đó lệnh kiểm mang `--deselect` và không chạy tại cổng này (đây là hành vi được chỉ định, không phải lỗi).
2. Các bài test tích hợp chạy trong môi trường kiểm thử sử dụng fake, mock và fixture nội bộ; đây không phải là bằng chứng thay thế cho tài nguyên thật (GPU, TTS, Drive, Temporal thực tế), các bằng chứng tài nguyên thật sẽ được thu thập tại CP7.

## 6. Đối chiếu exit gate M6 trong roadmap

| Mã | Nội dung exit gate (docs/11-roadmap.md mục 12) | Trạng thái | Evidence |
| --- | --- | --- | --- |
| M6-EG1 | Tạo được R4 Video Alpha theo luồng giám sát từ snapshot đến completion | PENDING_USER_CHECKPOINT | Cần GPU/TTS/FFmpeg/Drive thật ở CP7; evidence mã nguồn: test_f18_render_video_pipeline.py (Chuỗi 7 hàng 18), test_cp6_video_production_flow.py (Chuỗi 5 hàng 14), test_e16_voice_timing_pipeline.py (Chuỗi 6 hàng 34) chỉ chứng minh luồng với fake, không thay evidence thật |
| M6-EG2 | Không output nào được đếm trước cloud verification | PASS | Toàn bộ lệnh kiểm liên quan exit 0: tests/unit/storage/test_storage_cloud_persist.py (Chuỗi 8 hàng 4), tests/unit/orchestration/test_g_completion_gate.py (Chuỗi 7 hàng 31), tests/integration/orchestration/test_g_commit_completion.py (Chuỗi 7 hàng 32), tests/integration/render/test_f20_worker_activity.py (Chuỗi 7 hàng 20) |
| M6-EG3 | Không local output bị xóa khi sync/completion chưa đủ | PASS | Toàn bộ lệnh kiểm liên quan exit 0: tests/unit/storage/test_storage_cleanup_evaluation.py (Chuỗi 8 hàng 8), tests/integration/storage/test_storage_cleanup_executor.py (Chuỗi 8 hàng 9), tests/unit/storage/test_storage_reconciliation.py (Chuỗi 8 hàng 10) |
| M6-EG4 | F không tự đổi script/góc/media ngoài fallback plan | PASS | Toàn bộ lệnh kiểm liên quan exit 0: tests/unit/render/test_f05_resolve_package.py (Chuỗi 7 hàng 5), test_f06_preconditions_hooks_timeline.py (Chuỗi 7 hàng 6), test_f07_preconditions_artifacts_language.py (Chuỗi 7 hàng 7), test_f08_validate_package.py (Chuỗi 7 hàng 8), test_f18_render_video_pipeline.py (Chuỗi 7 hàng 18) |
| M6-EG5 | G06 phần TTS/timing/media và G07 phần output/QC có evidence | PENDING_USER_CHECKPOINT | Cần evidence trên tài nguyên thật ở CP7; evidence với fake đạt exit 0: test_e09 đến test_e12 (Chuỗi 6 hàng 27..30), test_f12 đến test_f15 (Chuỗi 7 hàng 12..15) |
| M6-EG6 | User duyệt E-F và 5 preset mẫu; user nghe mẫu và duyệt hình | PENDING_USER_CHECKPOINT | User chưa duyệt, không tự ghi là đã duyệt; chờ nghiệm thu người dùng tại CP7 |

## 7. pendingUserCheckpoint

Chỉ gồm đúng 3 mã gate sau được đưa vào danh sách chờ kiểm tra/nghiệm thu người dùng theo đúng quy định:
1. `M6-EG1`: Tạo được R4 Video Alpha theo luồng giám sát từ snapshot đến completion — Cần chạy trên tài nguyên thật (GPU/TTS/FFmpeg/Drive) tại CP7.
2. `M6-EG5`: G06 phần TTS/timing/media và G07 phần output/QC có evidence — Cần thu thập bằng chứng vận hành trên tài nguyên thật tại CP7.
3. `M6-EG6`: User duyệt E-F và 5 preset mẫu; user nghe mẫu và duyệt hình — Chờ người dùng trực tiếp nghiệm thu chất lượng mẫu video, audio và preset.

## 8. Kết luận

Trạng thái: **CHƯA ĐẠT** (ở mức đóng tự động hoàn toàn do thiếu dữ liệu bản ghi quyết định).

Các tiêu chí chưa đạt gồm có:
1. **Mã gói `M6-EF-PLAN`**: Tra cứu `git log` chỉ đọc trên nhánh hiện tại không tìm thấy commit integrate riêng (`KHÔNG TÌM THẤY`).
2. **13 gói cổng thiếu `recordHash`**: Toàn bộ 13 mã cổng (`GATE-CP-2D-REGISTRY`, `GATE-CP-5-COMPLETION`, `GATE-CP-6-WORKFLOW`, `GATE-CP-2B-DEPS-PATHS`, `GATE-PERSIST-A`, `GATE-PERSIST-B`, `GATE-PERSIST-C`, `GATE-PERSIST-D`, `GATE-PERSIST-E`, `GATE-PERSIST-F`, `GATE-PERSIST-G`, `GATE-PERSIST-I`, `GATE-PERSIST-J`) chưa được Control cấp mã `recordHash` tương ứng trong vật liệu giao việc của phiên. Do `.ai-pm/**` là đường cấm không được mở, Worker không tự tính hay bịa giá trị mà ghi nhận trung thực trạng thái `THIẾU` và báo cáo `BLOCKED` để Control cung cấp.

Về phía kỹ thuật và kiểm thử: Toàn bộ **274/274** lệnh kiểm bắt buộc đều đạt exit code 0; các exit gate M6-EG2, M6-EG3, M6-EG4 đều PASS; ba gate M6-EG1, M6-EG5, M6-EG6 được chuyển sang `pendingUserCheckpoint` tại CP7 theo đúng quy chuẩn.

Báo cáo này tuân thủ nguyên tắc không thay đổi trạng thái trong roadmap (`docs/11-roadmap.md`) hay checklist (`docs/12-pre-code-checklist.md`).

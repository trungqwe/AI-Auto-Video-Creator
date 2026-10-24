# Báo cáo đóng M3 (revision 1)

## Môi trường

- **Interpreter khóa của lane**: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`
- **HEAD candidate đã kiểm**: 6b0e2e51daac6187070f77c530f415ae8517d154 (tệp báo cáo này là tài liệu thêm sau candidate). Nhánh đã rebase lên integration head 74c062a29d649ea0e3d1471dee9c739dc33d38fe; kết quả của lần mở trước (HEAD bf52905b3b85 và 5bfe232) không còn dùng được.
- **Trạng thái worktree**: Trước khi chạy lệnh cây làm việc hoàn toàn sạch (clean); sau khi chạy toàn bộ 219 lệnh kiểm bắt buộc (bao gồm lệnh build UI `npm --prefix src/controlplane/ui run build`), cây làm việc vẫn sạch, không có tệp nào bị thay đổi ngoài thư mục `docs/delivery-evidence/m3-milestone-close/`.
- **Số lệnh kiểm bắt buộc đã chạy lại**: 219/219 lệnh; tất cả exit 0. Lệnh `tests/m2/test_p7b_hardening.py::test_h36_m1_regression` bị --deselect theo quyết định của user ngày 21/10/2026 (hoãn sang CP7), không tự chạy.
- **Nguồn quyền**: User duyệt Phần B ngày 18/10/2026 (D0–D10 theo đề xuất); các milestone M3–M7 chạy theo ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`).

## Gói được bao phủ

| Mã gói | SHA tích hợp | Ghi chú |
| :--- | :--- | :--- |
| M3-A-PLAN | `6cbbdcfc607ffc877b4412c9152191d15a86751b` | Commit gốc trên baseline (candidate 6cbbdcfc607f từ receipt camp_M3-A-PLAN, Auditor PASS) |
| CP0-GOVERNANCE | `e79ae82c349bd4492323d22a0070f77bbbe82337` | Tích hợp từ lane-cp0-governance (candidate 0948472b68dd) |
| CP2A-LAYOUT | `35ea5029b40cc4a5edcc3054499676cd6dc591e2` | Tích hợp từ lane-cp2a-layout (candidate 1d5c2a699fa3) |
| CP1-CONTRACT-BINDING | `f40822e0ea258ed799fffa781c2c7b06776dd21a` | Tích hợp từ lane-cp1-contract-binding (candidate 9a4b4b5c6854) |
| IMPL-PLAN-A | `fb154e9f0433d45bef1994e292a948231b18d112` | Tích hợp từ lane-impl-plan-a (candidate 23c3e3cf22fb) |
| IMPL-PLAN-B | `815bebb15b565c4a750854b4218a3296c7be2904` | Tích hợp từ lane-impl-plan-b (candidate 6e139f3b2d3b) |
| IMPL-PLAN-C | `4035610fa62c04ebcd7bc774b4a9e4ed68c5ad1a` | Tích hợp từ lane-impl-plan-c (candidate 56dc6fa2a949) |
| IMPL-PLAN-I | `14a2b92677ebf47724fab8a6229b340f45a1a3a7` | Tích hợp từ lane-impl-plan-i (candidate 6b18b402e2f7) |
| IMPL-PLAN-D | `bd037dc4c148a0a9d31cff9078bf4620b47fd815` | Tích hợp từ lane-impl-plan-d (candidate ac0bf98832ed) |
| IMPL-PLAN-E | `c73f90b87c3aa9bd038e9c1b71374ceb1b04a20f` | Tích hợp từ lane-impl-plan-e (candidate 5e0fac5f84c4) |
| IMPL-PLAN-F | `e336d92b9146b73d42da5f0346a55eef6c8d4386` | Tích hợp từ lane-impl-plan-f (candidate 278d7617f114) |
| IMPL-PLAN-J | `df699e2d86efeff98f7214fac6cdb40420440ca5` | Tích hợp từ lane-impl-plan-j (candidate 1f901a0ef029) |
| IMPL-PLAN-G | `5795450216f7b989a15d6b4c3db78276b594f113` | Tích hợp từ lane-impl-plan-g (candidate f5bf44546610) |
| IMPL-PLAN-H | `a461b76e086b8d41ce4f0607da1e2c2460d3c90f` | Tích hợp từ lane-impl-plan-h (candidate 6ef168eb971f) |
| IMPL-PLAN-CONVERGENCE | `d83ab6107189a14ba92fb3d8d81789f946b461a8` | Tích hợp từ lane-impl-plan-convergence (candidate a5d863f65bf4) |
| A-01 | `22535f6dcff3dbf2e3187771a9bff1b34c85c838` | Tích hợp từ lane-a-01 (candidate b11289d9c406) |
| A-02 | `e343a41ee6570c39d0cbeda2bd35a3bf2c15513f` | Tích hợp từ lane-a-02 (candidate 0614e8d1934d) |
| A-03 | `5e009d1c06ba60052bdd1658f939ffaadc626597` | Tích hợp từ lane-a-03 (candidate 6382ebd2cdde) |
| A-04 | `f1d4a4c543fb9c14a48c3e44e82c20622d0ddc34` | Tích hợp từ lane-a-04 (candidate c512aedfd810) |
| A-05 | `596237ae94bcb7ba0bbc7b8536b6b12d4a95ea93` | Tích hợp từ lane-a-05 (candidate 8c4c80c5982e) |
| A-06 | `7f6c060c32c3dc545b857a1714b5fea0b445429f` | Tích hợp từ lane-a-06 (candidate 1b7754bbf77a) |
| A-07 | `ae8d0e3e4a02ea36a357b990d7e6d62e8326f3d1` | Tích hợp từ lane-a-07 (candidate e58ac323b47f) |
| A-08 | `c18f5fd14fd57c308b1d8e42128cbbb063a4ef74` | Tích hợp từ lane-a-08 (candidate b867f1f24233) |
| A-09 | `ec82a8154aeaf956305e08c493e07c4736dcf1de` | Tích hợp từ lane-a-09 (candidate 9c93960aee60) |
| A-10 | `a93ae583b468e7d61c4efe63d7609ff83ee4bed1` | Tích hợp từ lane-a-10 (candidate 18233ddf6c7b) |
| A-11 | `66e0591dc74b4f2e09b005c2cd4715f74b06280c` | Tích hợp từ lane-a-11 (candidate 8425147edd1b) |
| A-12 | `bad89e191f3ddd653febc2626eb80d813c93f8b8` | Tích hợp từ lane-a-12 (candidate 044cdf1a9075) |
| A-13 | `ccfd11131d7f8e8dd6a5340ac48d8a2e16c7111d` | Tích hợp từ lane-a-13 (candidate b46a5591d574) |
| A-14 | `4efa4f6c3d3a11b7610bcd06707fe8105e3933e0` | Tích hợp từ lane-a-14 (candidate 4d292f278aab) |
| A-15 | `11128dc8b3f7d27b885d3f6e3803c5822c6ed468` | Tích hợp từ lane-a-15 (candidate b09724147f4a) |
| A-16 | `bfc0d32e2bbe8f897229b9b87d77f91f200f3e9d` | Tích hợp từ lane-a-16 (candidate 1f2f3d17bd69) |
| A-17 | `3529edc34d9444d9629a3191c34dc07ab72a2d07` | Tích hợp từ lane-a-17 (candidate a5f13fc184bb) |
| A-18 | `773af60b0f148d6212f261abeb57c71fb5bde4b7` | Tích hợp từ lane-a-18 (candidate ba3370b8578b) |
| A-19 | `b75a132ef7ab944d785b8c39ff0295584d547a39` | Tích hợp từ lane-a-19 (candidate de07c98c6b4f) |
| B-1 | `91878d46206a05e052217b54e81af614b6ba1bf7` | Tích hợp từ lane-b-1 (candidate 92dbcc6f018b) |
| B-2 | `1a17e1181c6049618d93b905126c58cae5d21877` | Tích hợp từ lane-b-2 (candidate 5d34dbaf7d91) |
| B-3 | `8434f096979606c15fb444c498f08dd109e56bc3` | Tích hợp từ lane-b-3 (candidate c478e5d6c957) |
| B-4 | `0ad4cbf564484cec02bbeffa18ea3796349b4a91` | Tích hợp từ lane-b-4 (candidate 5f6e0fc76525) |
| B-5 | `ec66302c0da0adcc0f99de10a983a393563851de` | Tích hợp từ lane-b-5 (candidate 318d6e6731a1) |
| B-6 | `76b81ca29ac1159d4bd6f685da478df9e0911b3b` | Tích hợp từ lane-b-6 (candidate b862577c5ac2) |
| B-7 | `94f50610690a94c567ca47980922cc8c7d78b132` | Tích hợp từ lane-b-7 (candidate 357fbc957082) |
| B-8 | `f464d5b05de813f4b542d8f01d1ced48dbeff0a5` | Tích hợp từ lane-b-8 (candidate 02aef71e0d5c) |
| B-9 | `5a12c257a1f46ad4695d51e161104e9784ed76a2` | Tích hợp từ lane-b-9 (candidate 45cd8a8a1a7b) |
| B-10 | `a8914387d3e3f8cdc322baa06c0d2b23650d5560` | Tích hợp từ lane-b-10 (candidate 309798fc096d) |
| B-11 | `d1961a482f8f04364c3edb98c562cb98b126193d` | Tích hợp từ lane-b-11 (candidate bb3b1e14ff81) |
| B-12 | `c8514bd1ba916e7be55561659dce0661e7c7e81e` | Tích hợp từ lane-b-12 (candidate 3d5c8467b4ec) |
| C-01 | `5b5d282e1862f8ff9a19831147bcf3ceec7fcf7e` | Tích hợp từ lane-c-01 (candidate bc1144fa816a) |
| C-02 | `003d991458706b63f97573b39567fe29574cc6cb` | Tích hợp từ lane-c-02 (candidate c6d6afa65c61) |
| C-03 | `be1fa2ef1c1cfa31173aee1c6dff878ac2793b02` | Tích hợp từ lane-c-03 (candidate 06c42477bb10) |
| C-04 | `354d46c041501b32c8df147af1728c3915df65f4` | Tích hợp từ lane-c-04 (candidate af457adf2c1e) |
| C-05 | `cbd256247045936fd2b5b07c3eca8fbfac7b737d` | Tích hợp từ lane-c-05 (candidate 7dcf357e5b8f) |
| C-06 | `2233e36f669f9ea4d8ffdd9b0724aa8c9fe19753` | Tích hợp từ lane-c-06 (candidate b6fc4471c652) |
| C-07 | `9207e232ceb28c85c8da32f8eec9a7b9866be53d` | Tích hợp từ lane-c-07 (candidate 46d398a3abf6) |
| C-08 | `4f956426cf8a28182acd5cba47ceebe368f9908f` | Tích hợp từ lane-c-08 (candidate 71e745c7add3) |
| C-09 | `a800f8790e9eee9937165c13b020d33b39739dc2` | Tích hợp từ lane-c-09 (candidate 8831823a18f2) |
| D-01 | `1d56b2699f6f6a2c08346da3db1107e435c234eb` | Tích hợp từ lane-d-01 (candidate b2a81a892125) |
| D-02 | `d525f9275b0a5062b673d0b307b2707f98d26e12` | Tích hợp từ lane-d-02 (candidate 9ca090a7b919) |
| D-03 | `cf44f24a63971600a198a9afdf7d8a35421fb248` | Tích hợp từ lane-d-03 (candidate eaa8dad378e7) |
| D-04 | `dff70cc63be1c08c1cd33a4856a39deea7483523` | Tích hợp từ lane-d-04 (candidate 7ea9f67e12da) |
| D-05 | `bdd2916e35e1c907d1141a1139e872690b2e5acb` | Tích hợp từ lane-d-05 (candidate 27f7dadb9233) |
| D-06 | `91000e325c7a72572aec729d3bcfc8ed20c1ae51` | Tích hợp từ lane-d-06 (candidate fcf0147eb038) |
| D-07 | `5646473e81669af7143ea98e81869927ec761f5f` | Tích hợp từ lane-d-07 (candidate 324777971bf3) |
| D-08 | `1b44a9460b1f18e33309cd4255c2e50e4552a470` | Tích hợp từ lane-d-08 (candidate 6db601c34c55) |
| D-09 | `4aeaf9fb552e1c717c20614cbd9ab2487ff850fc` | Tích hợp từ lane-d-09 (candidate acf373e72ef9) |
| D-10 | `89b0e328f18b9ad438dd217044c116ad0c386501` | Tích hợp từ lane-d-10 (candidate b90570d461a7) |
| D-11 | `8797e8d2cf79002f4b080dfefbbbeaa945cd687a` | Tích hợp từ lane-d-11 (candidate 538fd130d1ae) |
| D-12 | `3e6932884111da7ec41d854a3f39708a626c49aa` | Tích hợp từ lane-d-12 (candidate 14c9b16f8362) |
| D-13 | `8123aba43315b3c836df2740aeb5fd25b017214d` | Tích hợp từ lane-d-13 (candidate e25a63a8afb9) |
| D-14 | `bcda8664b9621875d25ba2359b95d3d0360a36b2` | Tích hợp từ lane-d-14 (candidate fe635dd2c6ef) |
| D-15 | `7f5cb179669672e1f0a9f77430534c3826e76a20` | Tích hợp từ lane-d-15 (candidate 7223acde4dbf) |
| D-16 | `8c66d619acbc12c4a6c202c8cdb4ca8e26447e9f` | Tích hợp từ lane-d-16 (candidate 49e5a2845818) |
| D-17 | `4645f6217894c6b873cbfe5576c4b1ae8aaf0d23` | Tích hợp từ lane-d-17 (candidate b94526322ad9) |
| D-18 | `febeb176885bf16a5e27f5a2b344a8480a25f0c9` | Tích hợp từ lane-d-18 (candidate 669f67fa1840) |
| E-01 | `170b96b2748929758f96d9b5a54726be29fb7600` | Tích hợp từ lane-e-01 (candidate c1e0e06e1f98) |
| E-02 | `dd68637ba76c9e3213de9b564226e2e69f35f230` | Tích hợp từ lane-e-02 (candidate 683e3e8396c4) |
| E-03 | `3f89da586c1ffc46c04d3a3f2793f0c0921d24fd` | Tích hợp từ lane-e-03 (candidate c426045eb0f9) |
| E-04 | `f54199a752a19475f567738a7c70eb108d583316` | Tích hợp từ lane-e-04 (candidate 7a2fb4c4fc40) |
| E-05 | `3f026bb8ba5c01a566dde9fffcc0480c727dcdf3` | Tích hợp từ lane-e-05 (candidate 880bb810bb04) |
| E-06 | `d3887fa6a224395ad1e37e00e866a8e7def930e0` | Tích hợp từ lane-e-06 (candidate da1e6a7ba167) |
| E-07 | `2e7c6b1ca42d83ed16dac720ca98388b1bd06ecc` | Tích hợp từ lane-e-07 (candidate a8abf025014b) |
| E-08 | `1bfb8b02dc928a2455330afa45edc768226a63e5` | Tích hợp từ lane-e-08 (candidate 8dfaedb513d4) |
| E-09 | `c695121600c8d1b73e9153cbd26dab92cf2f6b18` | Tích hợp từ lane-e-09 (candidate 8c4ed2542c25) |
| E-10 | `af9306a233fc2bed399d696fb87918f5c8e7dfe0` | Tích hợp từ lane-e-10 (candidate 237353be4524) |
| E-11 | `6945c76b1b309084663e2e0a6b2b668bebad88fc` | Tích hợp từ lane-e-11 (candidate 37b5acbde850) |
| E-12 | `9d7459596ab9d0f69020c644c437b6523ffec755` | Tích hợp từ lane-e-12 (candidate 1d8150785261) |
| E-13 | `ccbfbb5771f4b8bca783f3d2c94cbcc7f328d5b4` | Tích hợp từ lane-e-13 (candidate cd3796837303) |
| E-14 | `cab81bda5c60f7c120126d832d4b48e0765315cf` | Tích hợp từ lane-e-14 (candidate 3ac7c2fb4883) |
| E-15 | `ab7cb613044212edf40e03817b75d6d648823269` | Tích hợp từ lane-e-15 (candidate b395a9b7f9fa) |
| E-16 | `cbb7507a6df2fec1b8283ce63fcc82cca963f8fc` | Tích hợp từ lane-e-16 (candidate 55f2c4d92d1e) |
| E-17 | `4ee2962f959ced2455af2cbb0642655d7f076c57` | Tích hợp từ lane-e-17 (candidate 60a514f00404) |
| E-18 | `5734017c335265c0e32a214e7a59fa7c2d0b6010` | Tích hợp từ lane-e-18 (candidate 457083608ac4) |
| E-19 | `1f6f35d6bfb9063eb24c83d688e22821842c5e67` | Tích hợp từ lane-e-19 (candidate fff0f48af09c) |
| E-20 | `48769ce5899afb3c275f6efb37ff9dea215154e2` | Tích hợp từ lane-e-20 (candidate 997405b26808) |
| F-01 | `4daa3e625fcac2d0d28a1bf01f925467fd958ff7` | Tích hợp từ lane-f-01 (candidate 603f5de01b5a) |
| F-02 | `6edd27271fc7408d857d4dcaafbfbae308c7f73f` | Tích hợp từ lane-f-02 (candidate ba2e313d5b1f) |
| F-03 | `cfd868a1406b38b34a1c05230e60b26e82692726` | Tích hợp từ lane-f-03 (candidate f9a57ed36fe6) |
| F-04 | `96f8e85c90b97cb6e0effeafa1cfca92c35fb8d4` | Tích hợp từ lane-f-04 (candidate 2c76c72dcb34) |
| F-05 | `100bfcb0fcfcc4b9940c5c07a9b4afa82e1f9a45` | Tích hợp từ lane-f-05 (candidate 8516288f5417) |
| F-06 | `7622e01f50b6257f93a5c0b90f84880b5c9bf952` | Tích hợp từ lane-f-06 (candidate c28e40d61e92) |
| F-07 | `b8dc82489eb61f7e284e02ab8d4e0be7b817fc27` | Tích hợp từ lane-f-07 (candidate d70d7c536116) |
| F-08 | `95efd236a7bf8b07dc6c0aae751d1992d2c8ef5b` | Tích hợp từ lane-f-08 (candidate 9c31b35843c5) |
| F-09 | `c8cfa82317412bd023f3e19e9134f470f4fb5fce` | Tích hợp từ lane-f-09 (candidate 4d1fdeea9582) |
| F-10 | `4bbe03d06091909a4ca31ac63850a4dc94ce20fe` | Tích hợp từ lane-f-10 (candidate a2266598f3c9) |
| F-11 | `580a981df3450c85f49558ead2a486b77ed3e68c` | Tích hợp từ lane-f-11 (candidate 5891f0465962) |
| F-12 | `6f1cf65b2e2c822f84fc951158bd3086a65cd758` | Tích hợp từ lane-f-12 (candidate 89dd41cda238) |
| F-13 | `d5e2573211069e1d7d212fead48a5fcdd70c26f3` | Tích hợp từ lane-f-13 (candidate 4a3da74249c9) |
| F-14 | `4dc0964ce286447d5d95987b402d08b9e99cdfa5` | Tích hợp từ lane-f-14 (candidate bb2f5d106c62) |
| F-15 | `8fc0a24d980ad0de18f4f5e34542151e971a842b` | Tích hợp từ lane-f-15 (candidate a8166444db02) |
| F-16 | `a5ed0e1569a24c7699bc0a184c47b9a500f30e17` | Tích hợp từ lane-f-16 (candidate 1eac899e6206) |
| F-17 | `d7f79a2aca73e091126fa1b788d4668b9801b0b3` | Tích hợp từ lane-f-17 (candidate d50d0d8e1602) |
| F-18 | `4381df15795a818cc8c774b84e55fe7b923237d3` | Tích hợp từ lane-f-18 (candidate ace01aaf9b75) |
| F-19 | `b6a4796674c86648798f1a5c41e263246acbba49` | Tích hợp từ lane-f-19 (candidate dd031a190418) |
| F-20 | `d6244988169563ae638cf419c73fafb43ff04a7a` | Tích hợp từ lane-f-20 (candidate 19651248ab56) |
| F-21 | `b61497009eccadcef157bc797e4eb1f9263b7f63` | Tích hợp từ lane-f-21 (candidate 6beaab0677ce) |
| F-22 | `bf52905b3b8547f82a51aa2ccc926f7b7ae1b0bc` | Tích hợp từ lane-f-22 (candidate d40433158cc7) |
| G-01 | `0591304d66208f1b9c445a437d793b1c1bb7210b` | Tích hợp từ lane-g-01 (candidate ce5b3bf82eb1) |
| G-02 | `bb8fe184f25fbe36ed0bdefa1bbffb162c1d4634` | Tích hợp từ lane-g-02 (candidate f34da0dcd82f) |
| G-03 | `23a1c347fc8abac60f20946be6e4c6155747995d` | Tích hợp từ lane-g-03 (candidate 23e40f054191) |
| G-04 | `4fd21816ce8c657983f0e09d226209f381b13f5c` | Tích hợp từ lane-g-04 (candidate 50941b02e1a4) |
| G-05 | `c25a524c0a8e455495d7214d61bfa09cfaa47f5f` | Tích hợp từ lane-g-05 (candidate cfedb166ea6c) |
| G-06 | `9dd3efea87d4172a55ae0bdd8e8b8f93025dc57c` | Tích hợp từ lane-g-06 (candidate a4569af78354) |
| G-07 | `1f92cf4e3edb03004573fffcc020f5a1b2bc3da6` | Tích hợp từ lane-g-07 (candidate 3a358b083b86) |
| G-08 | `997706710403ed4113ca1633391c2eda2b3314e9` | Tích hợp từ lane-g-08 (candidate ce3a757cf471) |
| G-09 | `1aa9fb870e8a8392dbce3c22dc7392695909f4f9` | Tích hợp từ lane-g-09 (candidate a1f1c1636bee) |
| G-10 | `cadafb45237be7442988df322083e02b491994c3` | Tích hợp từ lane-g-10 (candidate 4f4d12b598f6) |
| G-11 | `7cdcbf1ee151fe8da9747c90f2079ed757c67224` | Tích hợp từ lane-g-11 (candidate 636f93d0e94e) |
| G-12 | `02f465880049c649f3b329c404201eb6a932bed4` | Tích hợp từ lane-g-12 (candidate b15172eb5bf8) |
| G-13 | `5c8e6691fb622d08054ca24cca359cf4f5f302b5` | Tích hợp từ lane-g-13 (candidate 18b6837ce120) |
| G-14 | `41b999dd3ba9a7e7cb6f4ca02aebf167fb909e07` | Tích hợp từ lane-g-14 (candidate 98dd973ecb7a) |
| H-01 | `b7c69dcf0c57f820a9059ccfed9f33f3b4753b17` | Tích hợp từ lane-h-01 (candidate f445e697fa4d) |
| H-02 | `1d436dc88acfa2beca208b3b77bc9010b2933c35` | Tích hợp từ lane-h-02 (candidate 273da2ae7bba) |
| H-03 | `d6f0c277e1d921c36e0ba0553aca131ca6d991da` | Tích hợp từ lane-h-03 (candidate f8bfc13cc9bd) |
| H-04 | `647670c4d7373520028d1382a8664a1108d31572` | Tích hợp từ lane-h-04 (candidate 53c100019145) |
| H-05 | `ddeec203cadc4982286cbfa02a4882905967b7d1` | Tích hợp từ lane-h-05 (candidate 32eb1d7a392b) |
| H-06 | `672c0258ec0333ecd3405546d57471d2ece3f1cb` | Tích hợp từ lane-h-06 (candidate d3592813a48e) |
| H-07 | `210ac3386e5e5fc4c6623e26e5e127eea34a8ab5` | Tích hợp từ lane-h-07 (candidate 63abf78c4f20) |
| H-08 | `2cc70e022c4eccc40145171ed093e2d0b6cce552` | Tích hợp từ lane-h-08 (candidate b32fdc813e42) |
| H-09 | `3f728636bf16a824120ce1327ffd8ce3326dfebd` | Tích hợp từ lane-h-09 (candidate acedae410a42) |
| H-10 | `1602d70f0336bccf043242bb76a0bb1d57afd13a` | Tích hợp từ lane-h-10 (candidate 533664638547) |
| H-11 | `2ea81fba2ac95d4eb25b5a4d2d2e9ae53fe5c8ca` | Tích hợp từ lane-h-11 (candidate 3a48685a2315) |
| H-12 | `2709dde552c0df0b0c3dce847b69fc139fb34566` | Tích hợp từ lane-h-12 (candidate fabf5aa94149) |
| H-13 | `3699ef42c7c3f4dc5540c478fce3d86ef3a633fb` | Tích hợp từ lane-h-13 (candidate 974c60d09e3e) |
| H-14 | `41827002e91f295b2a5adc13b9c5db8a400eeb7f` | Tích hợp từ lane-h-14 (candidate 28707964e39c) |
| H-15 | `98381456e99a63c520138e800648a748114765ec` | Tích hợp từ lane-h-15 (candidate 3d65eeb307f4) |
| H-16 | `0b266d010c1be17c8b25c486df77e68e1ea43e58` | Tích hợp từ lane-h-16 (candidate 322d45b2c8e5) |
| I-01 | `8a56becbaf7a1814b73fc5d2886b390f6c17c45b` | Tích hợp từ lane-i-01 (candidate 0fffa7dbb1fb) |
| I-02 | `5631a65a20571299f43c3803f8593a95ad1419dc` | Tích hợp từ lane-i-02 (candidate 2334c0123df7) |
| I-03 | `dbd2b6e5b4a9271844e7e55673192bbc15f3c570` | Tích hợp từ lane-i-03 (candidate f59915458e5f) |
| I-04 | `12409080b2b686d8e7442db0c4e2ecc6f219374c` | Tích hợp từ lane-i-04 (candidate 6f004e0c28e9) |
| I-05 | `68e2ae94f4aafb49345a02583208516271e7e05e` | Tích hợp từ lane-i-05 (candidate d2caf207b8b3) |
| I-06 | `4b9625489ef4df525380403be10dcaf4d73c3991` | Tích hợp từ lane-i-06 (candidate ee3ce09a3f66) |
| I-07 | `ff4a1202fca00227eba3a295b3500efaba4a40cf` | Tích hợp từ lane-i-07 (candidate 6325d36c549e) |
| I-08 | `6cc347b6b1c32c887c6393932f4ffe9b0b4d0c80` | Tích hợp từ lane-i-08 (candidate 627afb7c01ce) |
| I-09 | `d3b0cff0a6c39bb4cce7451ff61435358b50a768` | Tích hợp từ lane-i-09 (candidate 79555e9485ff) |
| I-10 | `5d8c1aa2846ed5b9b4c59a742e3792621846dc46` | Tích hợp từ lane-i-10 (candidate a7838524da96) |
| I-11 | `6437cb96a4bad8941038406360ac3cab6f307385` | Tích hợp từ lane-i-11 (candidate 68b8a94c7dfd) |
| I-12 | `49a6b2cd63f58127a65fa105b13ced917a842f2d` | Tích hợp từ lane-i-12 (candidate d82f0b4a1ed9) |
| I-13 | `9ca4d9f66ecd72e66686da4310be5c0998728e0b` | Tích hợp từ lane-i-13 (candidate 9892cd5c5c34) |
| J-01 | `2f4646097605e31871a73832e6fd0a7cbda289d3` | Tích hợp từ lane-j-01 (candidate 0c3e5a6b7f50) |
| J-02 | `f563c0ddafa79257ae4afa5171f54e7fc11cbb5a` | Tích hợp từ lane-j-02 (candidate 0253af79e33f) |
| J-03 | `b83d371b45f27f784aeeaa35fd36979636c75423` | Tích hợp từ lane-j-03 (candidate db494344eb2d) |
| J-04 | `0642bc1cb8b778f1868bdfc818fd4dadad20c132` | Tích hợp từ lane-j-04 (candidate eef855ef73c8) |
| J-05 | `f5bef3db069c137b89b0f8313425d220808d57e2` | Tích hợp từ lane-j-05 (candidate 3e921177f77b) |
| J-06 | `7467ff26031adb5063e0d851be7f2de3cf4f2105` | Tích hợp từ lane-j-06 (candidate 99c4eba32238) |
| J-07 | `c5e236f22f8879070c66bdf088230f05d95ef78a` | Tích hợp từ lane-j-07 (candidate 79f95f88e037) |
| J-08 | `484661bdbbb463a98e7e8ab3609a9555e3c52892` | Tích hợp từ lane-j-08 (candidate d15a6b169ce9) |
| J-09 | `c4bceab00a2ebdf1a2cdd6ee474f9b28e407127a` | Tích hợp từ lane-j-09 (candidate a92b2937e174) |
| J-10 | `750929c603db3ca6c05ddc8dc127d08187e293b5` | Tích hợp từ lane-j-10 (candidate 194f44f8725f) |
| J-11 | `379c232fd55c67c60dfd23333cdd0e2589cc5d96` | Tích hợp từ lane-j-11 (candidate da2091cf56ba) |
| J-12 | `12c2567e4e67f06ce082696375d9350b6da90092` | Tích hợp từ lane-j-12 (candidate 6d19c7a4707f) |
| J-13 | `f3ddb66ffe3256224644f56088ad3f73127c37cc` | Tích hợp từ lane-j-13 (candidate 67c90cff1f87) |
| J-14 | `798b970838a55784962f38a0225d9ec3f047cbe0` | Tích hợp từ lane-j-14 (candidate d942868c5335) |
| J-15 | `b2222eabe26135c7af4e817c2cd1d75dc83a5d3e` | Tích hợp từ lane-j-15 (candidate 00371a965e8d) |
| J-16 | `f642bdc06bf70b00871bc62560b8d5b5a2845144` | Tích hợp từ lane-j-16 (candidate 157504393ebe) |
| J-17 | `ce8faa1475918573fc1fd5e51c5d38046e9a1115` | Tích hợp từ lane-j-17 (candidate f79fdcd14663) |
| J-18 | `01da3b296de9dc5ac3313df6780f1d09fb7e1e0e` | Tích hợp từ lane-j-18 (candidate 4457cebd540b) |
| IMPL-PLAN-J-FIX1 | `e613e7e1ba9eb7f35f225ff49f972b2836d9173a` | Tích hợp từ lane-impl-plan-j-fix1 (candidate 03de264ffe3c) |
| E-16-FIX1 | `ace870b20f86bf842f4c36566c30c98af9e05ae7` | Tích hợp từ lane-e-16-fix1 (candidate d909e906ec2e) |
| IMPL-PLAN-CONVERGENCE-FIX1 | `806814fcdb1fd24c30948086d8ad40c6752a77ca` | Tích hợp từ lane-impl-plan-convergence-fix1 (candidate 333d993e9415) |
| IMPL-PLAN-CONVERGENCE-FIX2 | `1703eb590eea09bc11a45b92e853a8571ef4f286` | Tích hợp từ lane-impl-plan-convergence-fix2 (candidate 081115e61683) |
| F-16-FIX1 | `970d36595098811e50b6e5b9aaf58529af6c15b6` | Tích hợp từ lane-f-16-fix1 (candidate 40838cb63b16) |
| F-20-FIX1 | `e6d42ba2e1d55065b51625f83f6e35c85f02c370` | Tích hợp từ lane-f-20-fix1 (candidate 23112383740c) |
| H-04-FIX1 | `bf23e4aea5cae41f0017184fe5a48ef7cd2e7fcc` | Tích hợp từ lane-h-04-fix1 (candidate 7dc0e2f5dbaf) |
| H-12-FIX1 | `202e0d1fd3e643f985e17c3f2c909116807b2a95` | Tích hợp từ lane-h-12-fix1 (candidate cf79ae22efec) |
| J-09-FIX1 | c10efaaeec9791999472d38b60eb8a3bf1b77962 | Tích hợp từ lane-j-09-fix1 (candidate 277383c9e99f) |
| CP-2B-DEPS | `b10dc7c86fc396f9aee9c3a03586c1d883cdc661` | Tích hợp từ lane-cp-2b-deps (candidate 8cda6c756f76) |
| CP-2C-M2-REGRESSION | `0e54a54e8700855d095ebac8267b1474ab878455` | Tích hợp từ lane-cp-2c-m2-regression (candidate 302b16965aec) |
| CP-3B-STATE-MACHINE | `0adb2bbd0ee4140dd8cf3650ea9b7ffb6ca4b450` | Tích hợp từ lane-cp-3b-state-machine (candidate b3a040ffd687) |
| CP-3-MIGRATIONS | `a3d84e838a0937515eb62eb5c3a35016ab88e7df` | Tích hợp từ lane-cp-3-migrations (candidate b33cdd34eb40) |
| CP-3-MIGRATIONS-FIX1 | `836de0d664d3bcbc2dc5ff53013cb8b9c5a94cf0` | Tích hợp từ lane-cp-3-migrations-fix1 (candidate a8a6cf78f104) |
| CP-4-WIRING | `750195f1a88ee5bc731893d8986992b7b97c442b` | Tích hợp từ lane-cp-4-wiring (candidate 06b6d6b453ca) |
| CP-4-WIRING-FIX1 | `06d6c84d8b798f693eab635ab44007ebc23df263` | Tích hợp từ lane-cp-4-wiring-fix1 (candidate 2309b3ab4898) |
| CP-4-WIRING-FIX2 | 759ea0abd830f76b6f6a99232e8183ee50a9f34d | Tích hợp từ lane-cp-4-wiring-fix2 (candidate 5aed9712848f) |
| CP-4B-UI-SHELL | `42c328c98f7c0890d01fb3a590bf43a3f78eb2fb` | Tích hợp từ lane-cp-4b-ui-shell (candidate 858d8179ba66) |
| CP-4B-UI-SCREENS | `a8533a71456b3ce573fcb8bbe68b2a21729e863d` | Tích hợp từ lane-cp-4b-ui-screens (candidate 3aa670cd9779) |
| CP-4B-UI-SCREENS-FIX1 | adc7634f45a21c2fa174adee662962d7a1b21a57 | Tích hợp từ lane-cp-4b-ui-screens-fix1 (candidate 2760ee3ca0f9) |
| ADAPT-PROD-FIX1 | 6ba0bcde40de3d3adf8405d9df6bd8cae431227a | Tích hợp từ lane-adapt-prod-fix1 (candidate d588d9c0e8b0) |
| GATE-CP-2D-REGISTRY | `00103f0a72d7b9e2f1f5803cc699db79373ac38ed2e47aa206f975da0eab9514` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-CP-5-COMPLETION | `3b9e4c9d779043c2f76022541f4524b931ad48cce3cad2e4bc4dfff7cfb54d90` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-CP-6-WORKFLOW | `2be7562bea521bede4812d8b5cff124d201b562b93a416b1972baca08d720190` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-CP-2B-DEPS-PATHS | `3bd11714d6cb8196cb1c800bc740a76e7a4436b905cb2c98d2a8400fa1d132cf` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-PERSIST-A | `1ccf6c904ef88886ed1dd7a66b50c2206fd1c12ac5357d926572dbf53135a343` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-PERSIST-B | `39f5e7e8bc503704574da52b3605d1a03911b24c29494514c865af229ca35bf4` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-PERSIST-C | `5327ae192465197cc63aa6f6e1ebc4670e06c063f6a1fb46a4b7e6a3ce4066f2` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-PERSIST-D | `794e8b5634d3adaab3d35154ae2f0d732f2dc86a477ca8faeb2cd10cbd79506f` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-PERSIST-E | `b38673dd8c05bac07daae786cf282bcbae1cb359ea80fcd24b806bf5eab94ae7` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-PERSIST-F | `7254c80039939250ee1d2b372b627655b8b60b998372d7c9652b4360042a9055` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-PERSIST-G | `f71b035ffeface811ea87ccc06ba8a13129922fed922018793672d14d244fe7d` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-PERSIST-I | `b987fc8b60eaddba804f31ce51c78cfc9047db41d42203882ea5fae37c31843e` | Cổng, Control thả bằng bản ghi quyết định RELEASE |
| GATE-PERSIST-J | `cc9e80f551c0a83996a2ff710c7ce2d8d73517eed0434d4c176e55403d1399de` | Cổng, Control thả bằng bản ghi quyết định RELEASE |

**Tổng số gói**: 210 gói (197 gói có SHA tích hợp tra được trên HEAD, 0 gói KHÔNG TÌM THẤY, 13 gói cổng được Control giải phóng bằng recordHash).

**Ghi chú về các gói bổ sung**: Toàn bộ các gói phụ thuộc và hội tụ (CP-2B-DEPS, CP-2C-M2-REGRESSION, CP-3B-STATE-MACHINE, CP-3-MIGRATIONS, CP-3-MIGRATIONS-FIX1, CP-4-WIRING, CP-4-WIRING-FIX1, CP-4-WIRING-FIX2, CP-4B-UI-SHELL, CP-4B-UI-SCREENS, CP-4B-UI-SCREENS-FIX1, ADAPT-PROD-FIX1, J-09-FIX1) đã được đưa vào bảng kiểm định chính thức kèm commit tích hợp thật trên HEAD; không còn gói nào bị thiếu.

## Kết quả lệnh kiểm

Toàn bộ 219 lệnh kiểm bắt buộc của milestone M3 đã được chạy lại nguyên văn bằng interpreter khóa của lane (33f06a7a) trên candidate HEAD đã ghi ở mục Môi trường. STT tương ứng với thứ tự trong danh sách lệnh kiểm bắt buộc của task, exit code là exit code thật đo được từ quá trình chạy.

| STT | Lệnh | Exit code | Kết quả nguyên văn |
| :---: | :--- | :---: | :--- |
| 1 | `git diff --check` | 0 | Đạt (exit 0, assertion đạt) |
| 2 | `python -m pytest docs/parallel-delivery/tests -q -p no:cacheprovider` | 0 | 21 passed in 5.13s |
| 3 | `python -c "import re, pathlib, unicodedata; f = ['AGENTS.md', 'README.md', 'HANDOFF.md', 'docs/12-pre-code-checklist.md', 'docs/11-roadmap.md']; t = dict((n, unicodedata.normalize('NFC', pathlib.Path(n).read_text(encoding='utf-8'))) for n in f); lock = re.compile('NOT AUTHORIZED|kh\u00f3a ch\u1eb7t|kho\u00e1 ch\u1eb7t|B\u1eca KH\u00d3A|B\u1eca KHO\u00c1'); bad = [n + ': ' + l.strip()[:90] for n in f for l in t[n].splitlines() if 'M3' in l and lock.search(l)]; assert not bad, bad; assert not re.search('push l\u00ean .origin. \u0111\u1ec3 sao l\u01b0u', t['AGENTS.md']), 'AGENTS.md still requires a push'; assert not re.search('push l\u00ean repository n\u00e0y', t['README.md']), 'README.md still requires a push'; assert all('18/10/2026' in t[n] for n in ['AGENTS.md', 'README.md', 'HANDOFF.md']), 'authority of 18/10/2026 missing'"` | 0 | Đạt (exit 0, assertion đạt) |
| 4 | `python -c "import re, pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); ids = re.findall(r'(?m)^\s*- id: ([A-Za-z0-9_.-]+)', t); dup = sorted(set(i for i in ids if ids.count(i) > 1)); assert not dup, dup; need = ['PATH-DELIVERY-EVIDENCE', 'PATH-IMPLEMENTATION-PLANS', 'LOCK-M2-REGRESSION', 'LOCK-UI-SHELL', 'LOCK-CONTROL-API', 'LOCK-CONVERGENCE'] + ['LOCK-IMPL-PLAN-' + x for x in 'A B C D E F G H I J CONVERGENCE'.split()]; miss = [i for i in need if i not in ids]; assert not miss, miss; assert 'src/storage/**' not in t and 'src/controlplane/orchestration/**' not in t, 'paths of G and I do not follow D1'; want = ['src/controlplane/domain/storage_meta/**', 'src/controlplane/domain/orchestration/**', 'docs/delivery-evidence/**', 'docs/implementation/**']; gone = [p for p in want if p not in t]; assert not gone, gone"` | 0 | Đạt (exit 0, assertion đạt) |
| 5 | `python -c "import re, pathlib; m = pathlib.Path('docs/parallel-delivery/acceptance-matrix.yaml').read_text(encoding='utf-8'); assert not re.search(r'docs/milestones/m[3-7]', m), 'acceptance-matrix still points M3+ evidence at docs/milestones'; o = pathlib.Path('docs/parallel-delivery/overlay-and-evidence.md').read_text(encoding='utf-8'); assert 'docs/delivery-evidence/' in o, 'the D4 location is not documented'; r = pathlib.Path('docs/delivery-evidence/cp0-governance/ownership-recheck.md').read_text(encoding='utf-8'); assert all(c in r for c in ['0a3f707', '98bd27e', 'ebf3d58']), 'the recheck must name the commits'; assert re.search(r'\b[0-9a-f]{64}\b', r), 'the recheck must bind the sha256 of the diff'"` | 0 | Đạt (exit 0, assertion đạt) |
| 6 | `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | 7464 passed, 1 warning, 2544 subtests passed in 16.10s |
| 7 | `python -c "import pathlib, re, tomllib; root = pathlib.Path('src/controlplane'); keys = set(tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['tool']['setuptools']['package-dir']); pk = set('.'.join(('controlplane',) + q.parent.relative_to(root).parts) for q in root.rglob('*.py') if q.stem.strip('_') == 'init' and 'node_modules' not in q.parts); miss = sorted(pk - keys); assert not miss, miss; ini = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['tool']['pytest']['ini_options']; assert 'src' in ini.get('pythonpath', []), 'pytest pythonpath must include src'; bad = [str(q) for d in ['src', 'tests'] for q in pathlib.Path(d).rglob('*.py') if 'node_modules' not in q.parts and re.search(r'(?m)^\s*(from|import)\s+src\.', q.read_text(encoding='utf-8', errors='replace'))]; assert not bad, bad"` | 0 | Đạt (exit 0, assertion đạt) |
| 8 | `python -m pytest tests/contract -q -p no:cacheprovider` | 0 | 293 passed in 0.57s |
| 9 | `python -c "import json, pathlib, re; b = pathlib.Path('docs/parallel-delivery/bindings'); mans = sorted(b.glob('*.json')); assert (b / 'README.md').is_file() and len(mans) >= 6, 'bindings/README.md and at least six seam manifests are required'; data = [json.loads(m.read_text(encoding='utf-8')) for m in mans]; assert all(d.get('seam') and d.get('source', {}).get('path', '').startswith('docs/09-contracts/') and re.fullmatch(r'[0-9a-f]{64}', d.get('source', {}).get('sha256', '')) for d in data), 'each manifest names its contract source and its sha256'; fx = pathlib.Path('tests/fixtures/contracts'); assert all((fx / d['seam']).is_dir() for d in data), 'each seam has a fixture folder'; e = pathlib.Path('docs/parallel-delivery/errata'); assert all((e / n).is_file() for n in ['m3-a.md', 'm4-ci.md', 'm5-d.md', 'm6-ef.md', 'm7-integration.md']), 'errata for the five plan families'"` | 0 | Đạt (exit 0, assertion đạt) |
| 10 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/a'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (A-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt (exit 0, assertion đạt) |
| 11 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/b'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (B-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt (exit 0, assertion đạt) |
| 12 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/c'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (C-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt (exit 0, assertion đạt) |
| 13 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/i'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (I-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt (exit 0, assertion đạt) |
| 14 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/d'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (D-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt (exit 0, assertion đạt) |
| 15 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/e'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (E-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt (exit 0, assertion đạt) |
| 16 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/f'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (F-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt (exit 0, assertion đạt) |
| 17 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/j'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (J-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt (exit 0, assertion đạt) |
| 18 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/g'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (G-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt (exit 0, assertion đạt) |
| 19 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/h'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (H-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'"` | 0 | Đạt (exit 0, assertion đạt) |
| 20 | `python -c "import re, pathlib, unicodedata; d = pathlib.Path('docs/implementation/convergence'); p = unicodedata.normalize('NFC', (d / 'plan.md').read_text(encoding='utf-8')); s = unicodedata.normalize('NFC', (d / 'slices.md').read_text(encoding='utf-8')); ids = re.findall(r'(?m)^### (CP-[0-9A-Z][0-9A-Z-]*)', s); assert ids and len(ids) == len(set(ids)), ids; assert all(s.count(k) >= len(ids) for k in ['ownedPaths', 'dependsOn', 'bindingRefs', 'testCommands', 'acceptance']), 'each slice needs ownedPaths, dependsOn, bindingRefs, testCommands and acceptance'; assert re.search('[\u1ea0-\u1ef9]', p) and chr(65533) not in p + s, 'Vietnamese text with diacritics, no replacement characters'; assert len(ids) >= 5, 'CP-2b, CP-3, CP-4, CP-5 and CP-6 at least'; assert 'USER-CKPT-D9-D10' in s, 'the dependency slice waits for USER-CKPT-D9-D10'; assert all(k in p for k in ['D2', 'D9', 'D10']), 'plan.md covers D2, D9 and D10'"` | 0 | Đạt (exit 0, assertion đạt) |
| 21 | `python -m pytest tests/integration/convergence/test_cp3_migration_sequence.py -q -p no:cacheprovider` | 0 | 8 passed in 1.87s |
| 22 | `python -m pytest tests/m2/test_p9_m2_exit_gate.py -q -p no:cacheprovider` | 0 | 6 passed in 3.98s |
| 23 | `python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/unit/storage tests/unit/security tests/integration/orchestration tests/integration/control_ui -q -p no:cacheprovider` | 0 | 5190 passed, 1 warning, 2237 subtests passed in 11.42s |
| 24 | `python -c "import pathlib; t = ' '.join(pathlib.Path('src/controlplane/infrastructure/db/migrations/0013_ingestion.sql').read_text(encoding='utf-8').split()); assert t.count('dedup_policy_revision TEXT NOT NULL') == 2 and 'dedup_policy_revision BIGINT' not in t, 'src/controlplane/infrastructure/db/migrations/0013_ingestion.sql'"` | 0 | Đạt (exit 0, assertion đạt) |
| 25 | `python -B -m pytest tests/integration/convergence/test_cp3_migration_sequence.py::test_pinned_migrations_and_runner_untouched -q -p no:cacheprovider` | 0 | 1 passed in 0.38s |
| 26 | `python -m pytest tests/integration/convergence/test_cp4_wiring.py -q -p no:cacheprovider` | 0 | 137 passed, 28 skipped, 1 warning in 2.50s |
| 27 | `python -m pytest tests/integration/convergence/test_cp4_queries_routes.py -q -p no:cacheprovider` | 0 | 21 passed, 1 warning in 1.01s |
| 28 | `python -m pytest tests/unit/control_ui/test_h_metadata_update.py -q -p no:cacheprovider` | 0 | 83 passed, 1 warning in 0.64s |
| 29 | `python -m pytest tests/m2/test_p7a_hardening.py::test_h28_static_architecture -q -p no:cacheprovider` | 0 | 1 passed, 1 warning in 0.73s |
| 30 | `python -c "import ast, pathlib; d = pathlib.Path('src/controlplane/application/control_api'); r = (d / 'route_catalog.py').read_text(encoding='utf-8'); c = (d / 'command_catalog.py').read_text(encoding='utf-8'); m = r.split('METADATA_RESOURCES', 1)[-1]; assert 'sources' in m and 'topic_tags' in m, 'sources metadata resource missing'; names = [e.args[0].value for n in ast.walk(ast.parse(c)) if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == 'COMMAND_SPECS' for e in n.value.elts]; assert len(names) == 14 and 'UpdateSourceMetadata' not in names, names; assert 'METADATA_ROUTED_COMMANDS' in c, 'metadata routed names not kept'"` | 0 | Đạt (exit 0, assertion đạt) |
| 31 | `python -m pytest tests/integration/adapt/prod/test_adapt_prod_sources_module.py -q -p no:cacheprovider` | 0 | 9 passed in 5.01s |
| 32 | `python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py -q -p no:cacheprovider` | 0 | 25 passed, 1 warning in 9.66s |
| 33 | `python -m pytest tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_builder_inventory tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_sources_have_no_forbidden_text tests/integration/adapt/wire/test_adapt_wire_services.py::test_wiring_modules_do_not_cross_import_subsystems -q -p no:cacheprovider` | 0 | 3 passed in 1.36s |
| 34 | `python -c "import re, pathlib; api = ''.join(p.read_text(encoding='utf-8') for p in pathlib.Path('src/controlplane/api').rglob('*.py')); assert re.search('module_services.{0,40}sources', api, re.S), 'sources service not attached to module_services'"` | 0 | Đạt (exit 0, assertion đạt) |
| 35 | `python -c "import pathlib; t = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['src/main.py', 'src/controlplane/api/wiring/production.py']); assert 'controlplane.application.test_driver' not in t and '/launch' in t and '127.0.0.1' in t and '0.0.0.0' not in t and 'from src.' not in t, 'prod'"` | 0 | Đạt (exit 0, assertion đạt) |
| 36 | `npm --prefix src/controlplane/ui run build` | 0 | Đạt (exit 0, assertion đạt) |
| 37 | `python -m pytest tests/unit/control_ui -q -p no:cacheprovider` | 0 | 665 passed, 1 warning in 1.31s |
| 38 | `python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.findall('assets/([A-Za-z0-9_.-]+)', h); assert r and all((d / 'assets' / x).is_file() for x in r), r; k = [f.name for f in (d / 'assets').iterdir() if f.is_file() and f.name not in r and not (f.name.endswith('.map') and f.name[:-4] in r)]; assert not k, ('orphan hashed files', k)"` | 0 | Đạt (exit 0, assertion đạt) |
| 39 | `python -c "import pathlib; d = pathlib.Path('src/controlplane/ui/dist'); n = [f.name for f in d.rglob('*') if f.is_file()]; assert len(n) == 4, n"` | 0 | Đạt (exit 0, assertion đạt) |
| 40 | `python -c "import re, pathlib; r = pathlib.Path('src/controlplane/ui/src/features/screens/screenRegistry.ts').read_text(encoding='utf-8'); s = dict(re.findall('id: ' + chr(39) + '([a-z-]+)' + chr(39) + '.*?backendStatus: ' + chr(39) + '([a-z_]+)' + chr(39), r, re.S)); assert len(s) == 18, s; assert s['sources'] == 'available', 'sources screen still pending_module'; assert all(s[i] == 'pending_module' for i in ['artifacts', 'snapshots', 'story-angles', 'scripts', 'accounts', 'cost']), s"` | 0 | Đạt (exit 0, assertion đạt) |
| 41 | `python -m pytest tests/unit/collection/test_a01_package_layout.py -q -p no:cacheprovider` | 0 | 13 passed, 62 subtests passed in 0.15s |
| 42 | `python -m pytest tests/unit/collection/test_a02_collected_document_package.py -q -p no:cacheprovider` | 0 | 27 passed, 99 subtests passed in 0.07s |
| 43 | `python -m pytest tests/unit/collection/test_a03_source_lifecycle.py -q -p no:cacheprovider` | 0 | 17 passed, 50 subtests passed in 0.05s |
| 44 | `python -m pytest tests/unit/collection/test_a04_locator_ssrf.py -q -p no:cacheprovider` | 0 | 74 passed in 0.10s |
| 45 | `python -m pytest tests/unit/collection/test_a05_collection_run_states.py -q -p no:cacheprovider` | 0 | 40 passed, 20 subtests passed in 0.06s |
| 46 | `python -m pytest tests/unit/collection/test_a06_checkpoint.py -q -p no:cacheprovider` | 0 | 15 passed, 22 subtests passed in 0.04s |
| 47 | `python -m pytest tests/unit/collection/test_a07_source_candidate.py -q -p no:cacheprovider` | 0 | 14 passed, 44 subtests passed in 0.04s |
| 48 | `python -m pytest tests/unit/collection/test_a08_ports_memory.py -q -p no:cacheprovider` | 0 | 32 passed, 3 subtests passed in 0.12s |
| 49 | `python -m pytest tests/integration/collection/test_a09_source_commands.py -q -p no:cacheprovider` | 0 | 28 passed, 11 subtests passed in 0.12s |
| 50 | `python -m pytest tests/integration/collection/test_a10_candidate_registration.py -q -p no:cacheprovider` | 0 | 23 passed, 14 subtests passed in 0.14s |
| 51 | `python -m pytest tests/integration/collection/test_a11_collect_source.py -q -p no:cacheprovider` | 0 | 18 passed in 0.14s |
| 52 | `python -m pytest tests/unit/collection/test_a12_secure_fetch.py -q -p no:cacheprovider` | 0 | 59 passed in 0.09s |
| 53 | `python -m pytest tests/unit/collection/test_a13_package_builder.py -q -p no:cacheprovider` | 0 | 49 passed in 0.11s |
| 54 | `python -m pytest tests/integration/collection/test_a14_artifact_handoff.py -q -p no:cacheprovider` | 0 | 19 passed in 0.10s |
| 55 | `python -m pytest tests/unit/collection/test_a15_source_eligibility.py -q -p no:cacheprovider` | 0 | 20 passed, 49 subtests passed in 0.07s |
| 56 | `python -m pytest tests/integration/collection/test_a16_supplemental.py -q -p no:cacheprovider` | 0 | 25 passed in 0.14s |
| 57 | `python -m pytest tests/unit/collection/test_a17_projections.py -q -p no:cacheprovider` | 0 | 33 passed, 29 subtests passed in 0.11s |
| 58 | `python -m pytest tests/integration/collection/test_a18_worker_activity.py -q -p no:cacheprovider` | 0 | 32 passed in 0.15s |
| 59 | `python -m pytest tests/unit/collection/test_a19_rule_catalog.py -q -p no:cacheprovider` | 0 | 62 passed in 0.14s |
| 60 | `python -m pytest tests/unit/ingestion/test_ingestion_package_validation.py -q -p no:cacheprovider` | 0 | 39 passed in 0.06s |
| 61 | `python -m pytest tests/unit/ingestion/test_ingestion_normalization.py tests/unit/ingestion/test_ingestion_fingerprint.py -q -p no:cacheprovider` | 0 | 30 passed in 0.06s |
| 62 | `python -m pytest tests/unit/ingestion/test_ingestion_article_aggregate.py tests/unit/ingestion/test_ingestion_memory_unit_of_work.py -q -p no:cacheprovider` | 0 | 19 passed in 0.06s |
| 63 | `python -m pytest tests/unit/ingestion/test_ingestion_domain_events.py -q -p no:cacheprovider` | 0 | 64 passed in 0.08s |
| 64 | `python -m pytest tests/unit/ingestion/test_ingestion_representative.py -q -p no:cacheprovider` | 0 | 27 passed in 0.05s |
| 65 | `python -m pytest tests/unit/ingestion/test_ingestion_resolve_document.py -q -p no:cacheprovider` | 0 | 31 passed in 0.09s |
| 66 | `python -m pytest tests/unit/ingestion/test_ingestion_event_link.py -q -p no:cacheprovider` | 0 | 45 passed in 0.07s |
| 67 | `python -m pytest tests/unit/ingestion/test_ingestion_event_update.py -q -p no:cacheprovider` | 0 | 61 passed in 0.08s |
| 68 | `python -m pytest tests/unit/ingestion/test_ingestion_source_set.py -q -p no:cacheprovider` | 0 | 39 passed in 0.08s |
| 69 | `python -m pytest tests/unit/ingestion/test_ingestion_queries.py -q -p no:cacheprovider` | 0 | 55 passed in 0.08s |
| 70 | `python -m pytest tests/unit/ingestion/test_ingestion_activity_handler.py -q -p no:cacheprovider` | 0 | 67 passed in 0.12s |
| 71 | `python -m pytest tests/integration/ingestion/test_ingestion_flow_integration.py -q -p no:cacheprovider` | 0 | 15 passed in 0.10s |
| 72 | `python -m pytest tests/unit/catalog/test_catalog_identity.py -q -p no:cacheprovider` | 0 | 20 passed, 37 subtests passed in 0.07s |
| 73 | `python -m pytest tests/unit/catalog/test_catalog_states.py -q -p no:cacheprovider` | 0 | 20 passed, 45 subtests passed in 0.04s |
| 74 | `python -m pytest tests/unit/catalog/test_catalog_discovery.py -q -p no:cacheprovider` | 0 | 11 passed, 11 subtests passed in 0.04s |
| 75 | `python -m pytest tests/unit/catalog/test_catalog_renditions.py -q -p no:cacheprovider` | 0 | 20 passed, 33 subtests passed in 0.04s |
| 76 | `python -m pytest tests/unit/catalog/test_catalog_hooks.py -q -p no:cacheprovider` | 0 | 26 passed, 31 subtests passed in 0.06s |
| 77 | `python -m pytest tests/unit/catalog/test_catalog_candidate_query.py -q -p no:cacheprovider` | 0 | 27 passed, 19 subtests passed in 0.06s |
| 78 | `python -m pytest tests/unit/catalog/test_catalog_asset_view.py -q -p no:cacheprovider` | 0 | 31 passed, 189 subtests passed in 0.09s |
| 79 | `python -m pytest tests/unit/catalog/test_catalog_renderable.py -q -p no:cacheprovider` | 0 | 20 passed, 87 subtests passed in 0.06s |
| 80 | `python -m pytest tests/unit/catalog/test_catalog_usage.py -q -p no:cacheprovider` | 0 | 27 passed, 11 subtests passed in 0.07s |
| 81 | `python -m pytest tests/m2/test_p0_packaging.py -q -p no:cacheprovider` | 0 | 9 passed in 14.86s |
| 82 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); x = d['project']['dependencies']; assert x and all('==' in i for i in x), x"` | 0 | Đạt (exit 0, assertion đạt) |
| 83 | `python -c "import json, pathlib; p = json.loads(pathlib.Path('src/controlplane/ui/package.json').read_text(encoding='utf-8')); v = list(p['dependencies'].values()) + list(p['devDependencies'].values()); assert v and all(i[0].isdigit() for i in v), v"` | 0 | Đạt (exit 0, assertion đạt) |
| 84 | `python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('src/controlplane/pyproject.toml').read_text(encoding='utf-8')); s = d['tool']['setuptools']; n = ['controlplane.api.routes.modules', 'controlplane.infrastructure.storage']; u = chr(95) * 2 + 'init' + chr(95) * 2 + '.py'; assert all(k in s['packages'] and k in s['package-dir'] for k in n), n; assert all(pathlib.Path('src/controlplane', s['package-dir'][k], u).is_file() for k in n), n"` | 0 | Đạt (exit 0, assertion đạt) |
| 85 | `python -m pytest tests/m2 -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression` | 0 | 179 passed, 1 deselected, 2 warnings in 228.12s (0:03:48) |
| 86 | `python -c "import re, pathlib; t = pathlib.Path('tests/m2/test_p9_m2_exit_gate.py').read_text(encoding='utf-8'); assert re.search('M2_ACCEPTED_SHA = [^0-9a-f]*[0-9a-f]{40}', t), 'pin M2_ACCEPTED_SHA'"` | 0 | Đạt (exit 0, assertion đạt) |
| 87 | `python -m pytest tests/integration/convergence/test_cp3b_catalog_graphs.py tests/integration/convergence/test_cp3b_source_parity.py -q -p no:cacheprovider` | 0 | 25 passed in 0.08s |
| 88 | `python -m pytest tests/unit/collection tests/unit/catalog tests/m2/test_p4_statemachines.py -q -p no:cacheprovider` | 0 | 666 passed, 841 subtests passed in 1.10s |
| 89 | `python -m pytest tests/m2 tests/integration -q -p no:cacheprovider --deselect tests/m2/test_p7b_hardening.py::test_h36_m1_regression` | 0 | 2306 passed, 35 skipped, 1 deselected, 2 warnings, 25 subtests passed in 427.52s (0:07:07) |
| 90 | `python -m pytest tests/unit/collection tests/unit/ingestion tests/unit/catalog tests/unit/creative tests/unit/voice tests/unit/render tests/unit/security tests/unit/control_ui -q -p no:cacheprovider` | 0 | 5262 passed, 1 warning, 1998 subtests passed in 10.60s |
| 91 | `python -c "import pathlib; t = pathlib.Path('src/main.py').read_text(encoding='utf-8'); assert 'create_app' in t, 'src/main.py must call create_app'; assert 'from src.' not in t and 'import src.' not in t, 'no src. prefix'"` | 0 | Đạt (exit 0, assertion đạt) |
| 92 | `python -c "import re, pathlib; d = pathlib.Path('src/controlplane/ui/dist'); h = (d / 'index.html').read_text(encoding='utf-8'); r = re.findall('assets/[A-Za-z0-9_.-]+', h); assert r and all((d / x).is_file() for x in r), r; assert not any((d / 'assets' / x).exists() for x in ['index-Dd0WysB0.js', 'index-Dd0WysB0.js.map']), 'old hashed files must be gone'; k = [f.name for f in (d / 'assets').iterdir() if f.is_file() and 'assets/' + f.name not in r and not (f.name.endswith('.map') and 'assets/' + f.name[:-4] in r)]; assert not k, ('orphan hashed files', k)"` | 0 | Đạt (exit 0, assertion đạt) |
| 93 | `python -c "import pathlib; t = pathlib.Path('src/controlplane/ui/src/App.tsx').read_text(encoding='utf-8'); assert 'boundedEventDeduper' in t and 'screenRegistry' in t, 'App.tsx must wire deduper and screen registry'; assert 'new Set' not in t, 'App.tsx must not keep its own Set'; assert 'onOpenTestError=' in t, 'BL-CV-13: keep test button wiring'"` | 0 | Đạt (exit 0, assertion đạt) |
| 94 | `python -m pytest tests/unit/creative/test_d01_package_layout.py -q -p no:cacheprovider` | 0 | 12 passed, 58 subtests passed in 0.11s |
| 95 | `python -m pytest tests/unit/creative/test_d02_production_snapshot.py -q -p no:cacheprovider` | 0 | 68 passed in 0.08s |
| 96 | `python -m pytest tests/unit/creative/test_d03_untrusted_boundary.py -q -p no:cacheprovider` | 0 | 11 passed, 13 subtests passed in 0.04s |
| 97 | `python -m pytest tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider` | 0 | 87 passed in 0.13s |
| 98 | `python -m pytest tests/unit/creative/test_d05_content_analysis.py -q -p no:cacheprovider` | 0 | 20 passed, 79 subtests passed in 0.07s |
| 99 | `python -m pytest tests/unit/creative/test_d06_story_angles.py -q -p no:cacheprovider` | 0 | 60 passed in 0.10s |
| 100 | `python -m pytest tests/unit/creative/test_d07_timeline_authorization.py -q -p no:cacheprovider` | 0 | 32 passed in 0.06s |
| 101 | `python -m pytest tests/unit/creative/test_d08_script_version.py -q -p no:cacheprovider` | 0 | 62 passed in 0.09s |
| 102 | `python -m pytest tests/unit/creative/test_d09_asset_selection.py -q -p no:cacheprovider` | 0 | 110 passed in 0.18s |
| 103 | `python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider` | 0 | 94 passed in 0.18s |
| 104 | `python -m pytest tests/unit/creative/test_d11_variant_validation.py -q -p no:cacheprovider` | 0 | 62 passed in 0.16s |
| 105 | `python -m pytest tests/unit/creative/test_d12_output_metadata.py -q -p no:cacheprovider` | 0 | 19 passed, 38 subtests passed in 0.05s |
| 106 | `python -m pytest tests/unit/creative/test_d13_ports_memory.py -q -p no:cacheprovider` | 0 | 65 passed in 0.16s |
| 107 | `python -m pytest tests/integration/creative/test_d14_creative_pipeline.py -q -p no:cacheprovider` | 0 | 18 passed in 0.17s |
| 108 | `python -m pytest tests/integration/creative/test_d15_provider_failure.py -q -p no:cacheprovider` | 0 | 27 passed in 0.12s |
| 109 | `python -m pytest tests/integration/creative/test_d16_worker_activity.py -q -p no:cacheprovider` | 0 | 52 passed in 0.17s |
| 110 | `python -m pytest tests/unit/creative/test_d17_trace_projection.py -q -p no:cacheprovider` | 0 | 22 passed in 0.12s |
| 111 | `python -m pytest tests/unit/creative/test_d18_coverage_catalog.py -q -p no:cacheprovider` | 0 | 8 passed in 0.35s |
| 112 | `python -m pytest tests/unit/voice/test_e01_package_layout.py -q -p no:cacheprovider` | 0 | 16 passed, 89 subtests passed in 0.16s |
| 113 | `python -m pytest tests/unit/voice/test_e02_processing_contract.py -q -p no:cacheprovider` | 0 | 65 passed in 0.08s |
| 114 | `python -m pytest tests/unit/voice/test_e03_probe_media.py -q -p no:cacheprovider` | 0 | 144 passed in 0.13s |
| 115 | `python -m pytest tests/unit/voice/test_e04_media_analysis.py -q -p no:cacheprovider` | 0 | 86 passed in 0.10s |
| 116 | `python -m pytest tests/unit/voice/test_e05_image_safety.py -q -p no:cacheprovider` | 0 | 50 passed in 0.06s |
| 117 | `python -m pytest tests/unit/voice/test_e06_image_transform.py -q -p no:cacheprovider` | 0 | 75 passed in 0.12s |
| 118 | `python -m pytest tests/unit/voice/test_e07_normalize_media.py -q -p no:cacheprovider` | 0 | 106 passed in 0.14s |
| 119 | `python -m pytest tests/unit/voice/test_e08_voice_track.py -q -p no:cacheprovider` | 0 | 63 passed in 0.09s |
| 120 | `python -m pytest tests/unit/voice/test_e09_word_timing.py -q -p no:cacheprovider` | 0 | 114 passed in 0.12s |
| 121 | `python -m pytest tests/unit/voice/test_e10_timing_coverage.py -q -p no:cacheprovider` | 0 | 51 passed in 0.06s |
| 122 | `python -m pytest tests/unit/voice/test_e11_timing_binding.py -q -p no:cacheprovider` | 0 | 21 passed in 0.05s |
| 123 | `python -m pytest tests/unit/voice/test_e12_language_evidence.py -q -p no:cacheprovider` | 0 | 35 passed in 0.11s |
| 124 | `python -m pytest tests/unit/voice/test_e13_audio_bed.py -q -p no:cacheprovider` | 0 | 63 passed in 0.10s |
| 125 | `python -m pytest tests/unit/voice/test_e14_tts_route_invocation.py -q -p no:cacheprovider` | 0 | 79 passed in 0.17s |
| 126 | `python -m pytest tests/unit/voice/test_e15_ports_memory.py -q -p no:cacheprovider` | 0 | 47 passed in 0.11s |
| 127 | `python -m pytest tests/integration/voice/test_e16_voice_timing_pipeline.py -q -p no:cacheprovider` | 0 | 23 passed in 0.12s |
| 128 | `python -m pytest tests/integration/voice/test_e17_media_processing_pipeline.py -q -p no:cacheprovider` | 0 | 45 passed in 0.13s |
| 129 | `python -m pytest tests/integration/voice/test_e18_worker_activity.py -q -p no:cacheprovider` | 0 | 44 passed in 0.22s |
| 130 | `python -m pytest tests/unit/voice/test_e19_trace_projection.py -q -p no:cacheprovider` | 0 | 35 passed in 0.09s |
| 131 | `python -m pytest tests/unit/voice/test_e20_coverage_catalog.py -q -p no:cacheprovider` | 0 | 25 passed in 2.47s |
| 132 | `python -m pytest tests/unit/render/test_f01_package_layout.py -q -p no:cacheprovider` | 0 | 20 passed, 120 subtests passed in 0.44s |
| 133 | `python -m pytest tests/unit/render/test_f02_preset_revision.py -q -p no:cacheprovider` | 0 | 26 passed, 67 subtests passed in 0.10s |
| 134 | `python -m pytest tests/unit/render/test_f03_render_package_contract.py -q -p no:cacheprovider` | 0 | 169 passed in 0.19s |
| 135 | `python -m pytest tests/unit/render/test_f04_package_fingerprint.py -q -p no:cacheprovider` | 0 | 58 passed in 0.12s |
| 136 | `python -m pytest tests/unit/render/test_f05_resolve_package.py -q -p no:cacheprovider` | 0 | 62 passed in 0.12s |
| 137 | `python -m pytest tests/unit/render/test_f06_preconditions_hooks_timeline.py -q -p no:cacheprovider` | 0 | 104 passed in 0.14s |
| 138 | `python -m pytest tests/unit/render/test_f07_preconditions_artifacts_language.py -q -p no:cacheprovider` | 0 | 97 passed in 0.15s |
| 139 | `python -m pytest tests/unit/render/test_f08_validate_package.py -q -p no:cacheprovider` | 0 | 55 passed in 0.13s |
| 140 | `python -m pytest tests/unit/render/test_f09_karaoke_plan.py -q -p no:cacheprovider` | 0 | 118 passed in 0.13s |
| 141 | `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider` | 0 | 154 passed in 0.21s |
| 142 | `python -m pytest tests/unit/render/test_f11_render_attempt.py -q -p no:cacheprovider` | 0 | 97 passed in 0.13s |
| 143 | `python -m pytest tests/unit/render/test_f12_quality_report.py -q -p no:cacheprovider` | 0 | 45 passed, 129 subtests passed in 0.14s |
| 144 | `python -m pytest tests/unit/render/test_f13_technical_gates.py -q -p no:cacheprovider` | 0 | 38 passed, 99 subtests passed in 0.09s |
| 145 | `python -m pytest tests/unit/render/test_f14_content_gates.py -q -p no:cacheprovider` | 0 | 52 passed, 67 subtests passed in 0.09s |
| 146 | `python -m pytest tests/unit/render/test_f15_output_ready.py -q -p no:cacheprovider` | 0 | 73 passed in 0.13s |
| 147 | `python -m pytest tests/unit/render/test_f16_ports_memory_events.py -q -p no:cacheprovider` | 0 | 39 passed in 0.11s |
| 148 | `python -m pytest tests/integration/render/test_f17_resolve_validate_pipeline.py -q -p no:cacheprovider` | 0 | 36 passed in 0.18s |
| 149 | `python -m pytest tests/integration/render/test_f18_render_video_pipeline.py -q -p no:cacheprovider` | 0 | 28 passed in 0.17s |
| 150 | `python -m pytest tests/integration/render/test_f19_inspect_output_pipeline.py -q -p no:cacheprovider` | 0 | 35 passed in 0.26s |
| 151 | `python -m pytest tests/integration/render/test_f20_worker_activity.py -q -p no:cacheprovider` | 0 | 53 passed in 0.24s |
| 152 | `python -m pytest tests/unit/render/test_f21_trace_projection.py -q -p no:cacheprovider` | 0 | 17 passed in 0.12s |
| 153 | `python -m pytest tests/unit/render/test_f22_coverage_catalog.py -q -p no:cacheprovider` | 0 | 55 passed in 0.12s |
| 154 | `python -m pytest tests/unit/orchestration/test_g_activity_binding.py -q -p no:cacheprovider` | 0 | 43 passed in 0.07s |
| 155 | `python -m pytest tests/unit/orchestration/test_g_completion_binding.py -q -p no:cacheprovider` | 0 | 22 passed, 307 subtests passed in 0.08s |
| 156 | `python -m pytest tests/unit/orchestration/test_g_fencing.py -q -p no:cacheprovider` | 0 | 45 passed in 0.08s |
| 157 | `python -m pytest tests/unit/orchestration/test_g_grant_issuance.py -q -p no:cacheprovider` | 0 | 45 passed in 0.08s |
| 158 | `python -m pytest tests/unit/orchestration/test_g_operation_receipt.py -q -p no:cacheprovider` | 0 | 55 passed in 0.08s |
| 159 | `python -m pytest tests/unit/orchestration/test_g_stage_run_plan.py tests/unit/orchestration/test_g_job_waiting.py -q -p no:cacheprovider` | 0 | 147 passed in 0.14s |
| 160 | `python -m pytest tests/unit/orchestration/test_g_allocation_policy.py tests/unit/orchestration/test_g_job_allocation.py -q -p no:cacheprovider` | 0 | 88 passed in 0.23s |
| 161 | `python -m pytest tests/unit/orchestration/test_g_variant_reservation_flow.py -q -p no:cacheprovider` | 0 | 47 passed in 0.08s |
| 162 | `python -m pytest tests/unit/orchestration/test_g_completion_gate.py -q -p no:cacheprovider` | 0 | 86 passed in 0.12s |
| 163 | `python -m pytest tests/integration/orchestration/test_g_commit_completion.py -q -p no:cacheprovider` | 0 | 62 passed in 0.11s |
| 164 | `python -m pytest tests/unit/orchestration/test_g_command_semantics.py tests/unit/orchestration/test_g_retry_policy.py -q -p no:cacheprovider` | 0 | 110 passed in 0.11s |
| 165 | `python -m pytest tests/unit/orchestration/test_g_workflow_catalog.py tests/unit/orchestration/test_g_resource_admission.py -q -p no:cacheprovider` | 0 | 82 passed in 0.10s |
| 166 | `python -m pytest tests/unit/orchestration/test_g_event_payloads.py tests/unit/orchestration/test_g_consistency_audit.py -q -p no:cacheprovider` | 0 | 175 passed in 0.19s |
| 167 | `python -m pytest tests/unit/orchestration/test_g_recovery_scan.py tests/unit/orchestration/test_g_batch_outcome.py tests/unit/orchestration/test_g_app_session.py -q -p no:cacheprovider` | 0 | 157 passed in 0.17s |
| 168 | `python -m pytest tests/unit/control_ui/test_h_operation_view_model.py -q -p no:cacheprovider` | 0 | 55 passed in 0.08s |
| 169 | `python -m pytest tests/unit/control_ui/test_h_list_query.py -q -p no:cacheprovider` | 0 | 115 passed in 0.10s |
| 170 | `python -m pytest tests/unit/control_ui/test_h_stream_event_catalog.py -q -p no:cacheprovider` | 0 | 70 passed in 0.08s |
| 171 | `python -m pytest tests/integration/control_ui/test_h_list_queries_sql.py -q -p no:cacheprovider` | 0 | 175 passed, 1 warning in 1.31s |
| 172 | `python -m pytest tests/unit/control_ui/test_h_ops_read_models.py -q -p no:cacheprovider` | 0 | 31 passed in 0.06s |
| 173 | `python -m pytest tests/unit/control_ui/test_h_config_account_views.py -q -p no:cacheprovider` | 0 | 91 passed in 0.10s |
| 174 | `python -m pytest tests/unit/control_ui/test_h_problem_detail.py -q -p no:cacheprovider` | 0 | 37 passed in 0.35s |
| 175 | `python -m pytest tests/unit/control_ui/test_h_read_only_listing.py -q -p no:cacheprovider` | 0 | 43 passed, 1 warning in 0.58s |
| 176 | `python -m pytest tests/unit/control_ui/test_h_ts_contract_types.py -q -p no:cacheprovider` | 0 | 10 passed in 0.04s |
| 177 | `python -m pytest tests/unit/control_ui/test_h_status_presentation.py -q -p no:cacheprovider` | 0 | 9 passed in 0.04s |
| 178 | `python -m pytest tests/unit/control_ui/test_h_status_pill.py -q -p no:cacheprovider` | 0 | 22 passed in 0.04s |
| 179 | `python -m pytest tests/unit/control_ui/test_h_error_hover_detail.py -q -p no:cacheprovider` | 0 | 24 passed in 0.06s |
| 180 | `python -m pytest tests/unit/control_ui/test_h_stream_client_registry.py -q -p no:cacheprovider` | 0 | 14 passed in 0.04s |
| 181 | `python -m pytest tests/unit/control_ui/test_h_screen_registry.py -q -p no:cacheprovider` | 0 | 35 passed in 0.06s |
| 182 | `python -m pytest tests/unit/control_ui/test_h_ui_source_guard.py -q -p no:cacheprovider` | 0 | 26 passed in 0.07s |
| 183 | `python -m pytest tests/unit/storage/test_storage_declaration.py -q -p no:cacheprovider` | 0 | 65 passed in 0.09s |
| 184 | `python -m pytest tests/unit/storage/test_storage_declare_version.py -q -p no:cacheprovider` | 0 | 24 passed in 0.06s |
| 185 | `python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider` | 0 | 11 passed, 85 subtests passed in 0.05s |
| 186 | `python -m pytest tests/unit/storage/test_storage_cloud_persist.py -q -p no:cacheprovider` | 0 | 22 passed, 21 subtests passed in 0.08s |
| 187 | `python -m pytest tests/integration/storage/test_storage_local_journal.py -q -p no:cacheprovider` | 0 | 21 passed in 0.67s |
| 188 | `python -m pytest tests/integration/storage/test_storage_staging_paths.py -q -p no:cacheprovider` | 0 | 373 passed, 7 skipped in 1.89s |
| 189 | `python -m pytest tests/unit/storage/test_storage_materialization.py -q -p no:cacheprovider` | 0 | 25 passed, 26 subtests passed in 0.07s |
| 190 | `python -m pytest tests/unit/storage/test_storage_cleanup_evaluation.py -q -p no:cacheprovider` | 0 | 67 passed in 0.09s |
| 191 | `python -m pytest tests/integration/storage/test_storage_cleanup_executor.py -q -p no:cacheprovider` | 0 | 21 passed in 0.29s |
| 192 | `python -m pytest tests/unit/storage/test_storage_reconciliation.py -q -p no:cacheprovider` | 0 | 13 passed, 10 subtests passed in 0.04s |
| 193 | `python -m pytest tests/unit/storage/test_storage_output_naming.py -q -p no:cacheprovider` | 0 | 32 passed, 97 subtests passed in 0.06s |
| 194 | `python -m pytest tests/unit/storage/test_storage_placement.py -q -p no:cacheprovider` | 0 | 56 passed in 0.09s |
| 195 | `python -m pytest tests/unit/storage/test_storage_availability.py -q -p no:cacheprovider` | 0 | 41 passed in 0.06s |
| 196 | `python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovider` | 0 | 50 passed in 0.07s |
| 197 | `python -m pytest tests/unit/security/test_j_secret_redaction.py -q -p no:cacheprovider` | 0 | 55 passed in 0.06s |
| 198 | `python -m pytest tests/unit/config/test_j_publish_plan.py -q -p no:cacheprovider` | 0 | 60 passed in 0.09s |
| 199 | `python -m pytest tests/unit/config/test_j_status_graph.py -q -p no:cacheprovider` | 0 | 118 passed in 0.18s |
| 200 | `python -m pytest tests/unit/config/test_j_bundle_resolution.py -q -p no:cacheprovider` | 0 | 49 passed in 0.10s |
| 201 | `python -m pytest tests/unit/config/test_j_external_account.py -q -p no:cacheprovider` | 0 | 40 passed in 0.06s |
| 202 | `python -m pytest tests/unit/config/test_j_capacity_snapshot.py -q -p no:cacheprovider` | 0 | 104 passed in 0.11s |
| 203 | `python -m pytest tests/unit/config/test_j_incremental_cost.py -q -p no:cacheprovider` | 0 | 131 passed in 0.12s |
| 204 | `python -m pytest tests/unit/security/test_j_audit_record.py -q -p no:cacheprovider` | 0 | 104 passed in 0.10s |
| 205 | `python -m pytest tests/unit/security/test_j_secret_update.py -q -p no:cacheprovider` | 0 | 63 passed in 0.11s |
| 206 | `python -m pytest tests/unit/security/test_j_credential_issuance.py -q -p no:cacheprovider` | 0 | 51 passed in 0.09s |
| 207 | `python -m pytest tests/unit/config/test_j_capacity_reservation.py -q -p no:cacheprovider` | 0 | 66 passed in 0.08s |
| 208 | `python -m pytest tests/unit/config/test_j_route_resolver.py -q -p no:cacheprovider` | 0 | 50 passed in 0.13s |
| 209 | `python -m pytest tests/unit/config/test_j_fallback_policy.py -q -p no:cacheprovider` | 0 | 41 passed in 0.09s |
| 210 | `python -m pytest tests/unit/security/test_j_account_test.py -q -p no:cacheprovider` | 0 | 47 passed in 0.09s |
| 211 | `python -m pytest tests/unit/config/test_j_capability_health.py -q -p no:cacheprovider` | 0 | 35 passed in 0.09s |
| 212 | `python -m pytest tests/integration/config/test_j_dpapi_secret_store.py -q -p no:cacheprovider` | 0 | 35 passed in 0.53s |
| 213 | `python -m pytest tests/integration/config/test_j_routed_invocation.py -q -p no:cacheprovider` | 0 | 33 passed in 0.12s |
| 214 | `python -c "import pathlib; t = pathlib.Path('tests/integration/voice/test_e16_voice_timing_pipeline.py').read_text(encoding='utf-8'); assert all(i in t for i in ['TST-E2E-001']), 'tests/integration/voice/test_e16_voice_timing_pipeline.py'"` | 0 | Đạt (exit 0, assertion đạt) |
| 215 | `python -c "import pathlib; t = pathlib.Path('tests/unit/render/test_f16_ports_memory_events.py').read_text(encoding='utf-8'); assert all(i in t for i in ['TST-CTR-INV-002']), 'tests/unit/render/test_f16_ports_memory_events.py'"` | 0 | Đạt (exit 0, assertion đạt) |
| 216 | `python -c "import pathlib; t = pathlib.Path('tests/integration/render/test_f20_worker_activity.py').read_text(encoding='utf-8'); assert all(i in t for i in ['TST-WF-INV-003']), 'tests/integration/render/test_f20_worker_activity.py'"` | 0 | Đạt (exit 0, assertion đạt) |
| 217 | `python -c "import pathlib; t = pathlib.Path('tests/integration/control_ui/test_h_list_queries_sql.py').read_text(encoding='utf-8'); assert all(i in t for i in ['QR-PERF-005']), 'tests/integration/control_ui/test_h_list_queries_sql.py'"` | 0 | Đạt (exit 0, assertion đạt) |
| 218 | `python -c "import pathlib; t = pathlib.Path('tests/unit/control_ui/test_h_status_pill.py').read_text(encoding='utf-8'); assert all(i in t for i in ['CT-API-010', 'QR-UX-003']), 'tests/unit/control_ui/test_h_status_pill.py'"` | 0 | Đạt (exit 0, assertion đạt) |
| 219 | `python -B -m pytest tests/m2/test_p0_architecture_rules.py::test_tst_m2_p0_001_ast_boundary_rules_clean_codebase -q -p no:cacheprovider` | 0 | 1 passed in 0.47s |

**Tổng kết lệnh kiểm**: 219/219 lệnh exit 0 (tất cả 219 lệnh exit 0).

### Lần chạy lại test_cp3_migration_sequence sau thu hồi G2

- Lần chạy trước trên lượt bị thu hồi lỗi `psycopg.errors.ConnectionTimeout: connection timeout expired` ở `test_postgres_up_down_up_and_constraints`, kết quả 1 failed, 7 passed trong 130.39s (0:02:10).
- Nguyên nhân là không kết nối được PostgreSQL ở 127.0.0.1 (container ai-auto-video-m2-pg), thuộc hạ tầng chứ không phải thay đổi mã vì lượt này không sửa tệp nào ngoài báo cáo.
- `git rebase 74c062a29d649ea0e3d1471dee9c739dc33d38fe` không thay đổi HEAD `081663bd4f7d1e83456641afa9cfa6f4c187ad6f`, mã nguồn candidate `6b0e2e51daac6187070f77c530f415ae8517d154` không đổi.
- Kết quả chạy lại lệnh đó: exit 0 và dòng tóm tắt pytest thật: `8 passed in 1.87s`.

## Đối chiếu exit gate M3 (docs/11-roadmap.md §9)

| STT | Exit gate | Trạng thái | Bằng chứng kiểm thử |
| :---: | :--- | :---: | :--- |
| 1 | User có thể thêm nguồn và theo dõi từng lượt/stage/error trên UI | PASS | Áp quyết định của user (2026-10-22, user (ai-setup decide)): «Không cần thêm nguồn trên UI. Theo kế hoạch đã duyệt (EXT-UI mục 6), nguồn được thêm qua seed import; màn Nguồn tin trên UI liệt kê và sửa nguồn. Exit gate này đạt khi thêm được nguồn bằng seed import và theo dõi được từng lượt, stage, lỗi trên UI.» Đường seed import thêm nguồn đã có trong mã nguồn và test tại tools/launcher/prod/seed/import_seed.py:102 (_import_sources) và tests/integration/adapt/seed/test_adapt_seed_import.py:270 (test_sources_registered_with_tier_and_https). Toàn bộ các test theo dõi lượt/stage/lỗi trên UI, backend nguồn tin và probe metadata/service đều exit 0: STT 27 (tests/integration/convergence/test_cp4_queries_routes.py: exit 0), STT 28 (tests/unit/control_ui/test_h_metadata_update.py sửa metadata nguồn: exit 0), STT 30 (probe route_catalog.py metadata resources sources: exit 0), STT 31 (tests/integration/adapt/prod/test_adapt_prod_sources_module.py: exit 0), STT 34 (probe module_services sources: exit 0), STT 40 (probe screenRegistry.ts sources available: exit 0), STT 49 (tests/integration/collection/test_a09_source_commands.py: exit 0), STT 71 (tests/integration/ingestion/test_ingestion_flow_integration.py: exit 0), STT 168 (tests/unit/control_ui/test_h_operation_view_model.py: exit 0), STT 171 (tests/integration/control_ui/test_h_list_queries_sql.py: exit 0), STT 181 (tests/unit/control_ui/test_h_screen_registry.py: exit 0). |
| 2 | Article/Event truy ngược được source, fetch evidence và revision | PASS | STT 8 (tests/contract, 293 passed in 0.57s), STT 62 (tests/unit/ingestion/test_ingestion_article_aggregate.py và tests/unit/ingestion/test_ingestion_memory_unit_of_work.py, 19 passed in 0.06s), STT 65 (tests/unit/ingestion/test_ingestion_resolve_document.py, 31 passed in 0.09s), STT 68 (tests/unit/ingestion/test_ingestion_source_set.py, 39 passed in 0.08s), STT 69 (tests/unit/ingestion/test_ingestion_queries.py, 55 passed in 0.08s), STT 71 (tests/integration/ingestion/test_ingestion_flow_integration.py, 15 passed in 0.10s) |
| 3 | Bài repost không tạo article/script candidate mới | PASS | STT 61 (tests/unit/ingestion/test_ingestion_normalization.py và tests/unit/ingestion/test_ingestion_fingerprint.py, 30 passed in 0.06s), STT 64 (tests/unit/ingestion/test_ingestion_representative.py, 27 passed in 0.05s), STT 65 (tests/unit/ingestion/test_ingestion_resolve_document.py, 31 passed in 0.09s), STT 71 (tests/integration/ingestion/test_ingestion_flow_integration.py, 15 passed in 0.10s) |
| 4 | Event update không bị đồng nhất với nguồn đăng lại | PASS | STT 63 (tests/unit/ingestion/test_ingestion_domain_events.py, 64 passed in 0.08s), STT 66 (tests/unit/ingestion/test_ingestion_event_link.py, 45 passed in 0.07s), STT 67 (tests/unit/ingestion/test_ingestion_event_update.py, 61 passed in 0.08s), STT 71 (tests/integration/ingestion/test_ingestion_flow_integration.py, 15 passed in 0.10s) |
| 5 | Một nguồn lỗi không dừng cycle còn lại | PASS | STT 45 (tests/unit/collection/test_a05_collection_run_states.py, 40 passed, 20 subtests passed in 0.06s), STT 46 (tests/unit/collection/test_a06_checkpoint.py, 15 passed, 22 subtests passed in 0.04s), STT 51 (tests/integration/collection/test_a11_collect_source.py, 18 passed in 0.14s), STT 56 (tests/integration/collection/test_a16_supplemental.py, 25 passed in 0.14s), STT 58 (tests/integration/collection/test_a18_worker_activity.py, 32 passed in 0.15s) |
| 6 | A-B contract, integration, failure và security tests đạt | PASS | STT 8 (tests/contract, 293 passed in 0.57s), STT 41–59 (toàn bộ phân hệ A: A-01..A-19, gồm riêng STT 44 tests/unit/collection/test_a04_locator_ssrf.py và STT 52 tests/unit/collection/test_a12_secure_fetch.py cho security), STT 60–71 (toàn bộ phân hệ B) |
| 7 | User duyệt phân hệ A-B và R1 Content Alpha | PENDING | Gate M3-EG7, chờ checkpoint nghiệm thu của người dùng |

Finding F1 của lượt trước (lane mở trên nhánh cũ, thiếu gói FIX): FIXED sau rebase lên 74c062a29d649ea0e3d1471dee9c739dc33d38fe, STT 30, 31, 34, 40 exit 0.

**Ghi chú về phạm vi Exit Gate theo quyết định của user**: Theo quyết định của user ngày 22/10/2026 (user ai-setup decide): «Exit gate của roadmap rộng hơn kế hoạch đã duyệt chỉ được ghi chú trong báo cáo đóng mốc, không phải FAIL và không hỏi user. Việc kế hoạch đã duyệt có mà chưa nối do Control tự lập gói sửa.» Cụ thể, roadmap §9 Năng lực A mục 1 ("Thêm, sửa metadata, bật/tắt, remove và restore nguồn trên UI") rộng hơn kế hoạch đã duyệt (EXT-UI mục 6: nguồn được thêm qua seed import, màn Nguồn tin trên UI chỉ liệt kê và sửa metadata); khác biệt này được ghi nhận như một ghi chú đóng mốc theo quyết định của user.

## Đối chiếu bổ sung

- **M3-EG7 (User duyệt phân hệ A-B và R1 Content Alpha)**: Trạng thái PENDING. Đây là gate nghiệm thu trực tiếp của người dùng sau khi phân hệ A-B hoàn thành tích hợp và kiểm thử; cần checkpoint phê duyệt của người dùng trước khi chuyển sang các giai đoạn tiếp theo.
- **M3-REAL (Thu thập RSS/web thật trên mạng và scheduler cloud khi desktop offline (tài nguyên thật, CP7))**: Trạng thái PENDING. Gate này đòi hỏi kết nối mạng Internet thực tế để thu thập nguồn RSS/web thật và hạ tầng cloud scheduler hoạt động độc lập khi máy tính desktop offline; theo quy chuẩn không dùng mock để tuyên bố gate thật PASS. Lưu ý: theo quyết định của user ngày 20/10/2026, v1 chỉ chạy cục bộ và không dựng scheduler cloud; gate này được bảo lưu nguyên văn chờ kiểm định tại CP7 (CP7-REAL-RESOURCES).

## pendingUserCheckpoint

Chỉ có đúng hai mục sau nằm trong danh sách pendingUserCheckpoint:

1. M3-EG7: User duyệt phân hệ A-B và R1 Content Alpha.
2. M3-REAL: Thu thập RSS/web thật trên mạng và scheduler cloud khi desktop offline (tài nguyên thật, CP7).

Mọi tiêu chí kỹ thuật và lệnh kiểm chưa đạt đều được ghi nhận là FAIL ở mục Kết luận, tuyệt đối không đưa vào pendingUserCheckpoint.

## Kết luận

Trạng thái nghiệm thu milestone M3: **Đạt về kỹ thuật cho các gate M3-EG1 đến M3-EG6 trên candidate 6b0e2e51daac6187070f77c530f415ae8517d154; còn hai mục chờ user hoặc tài nguyên thật: M3-EG7 và M3-REAL**.

Chi tiết kết quả nghiệm thu trên candidate HEAD 6b0e2e51daac6187070f77c530f415ae8517d154:
- **Số gói được bao phủ**: 210 gói (197 gói có SHA tích hợp tra được trên HEAD, 0 gói KHÔNG TÌM THẤY, 13 gói cổng được Control giải phóng bằng recordHash).
- **Số lệnh kiểm bắt buộc**: 219 lệnh đã chạy lại nguyên văn bằng interpreter khóa 33f06a7a trên candidate HEAD; 219/219 lệnh exit 0 (tất cả 219 lệnh exit 0). Lệnh `tests/m2/test_p7b_hardening.py::test_h36_m1_regression` bị --deselect theo quyết định của user ngày 21/10/2026 (hoãn sang CP7), không tự chạy.
- **Đối chiếu exit gate**: Toàn bộ 6 exit gate kỹ thuật của M3 theo roadmap (docs/11-roadmap.md §9) đều đạt PASS (Gate 1 đến Gate 6, trong đó Gate 1 đạt theo quyết định của user ngày 22/10/2026 và kết quả kiểm thử sau rebase). Gate 7 (M3-EG7) và gate bổ sung M3-REAL ở trạng thái PENDING thuộc pendingUserCheckpoint.
- Báo cáo này không đổi trạng thái roadmap hay checklist, không đóng M3 thay Control. Báo cáo tuân thủ nghiêm ngặt ranh giới tác vụ, không chỉnh sửa bất kỳ tệp nào ngoài owned paths (docs/delivery-evidence/m3-milestone-close/**).

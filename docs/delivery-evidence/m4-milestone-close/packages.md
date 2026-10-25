# M4-MILESTONE-CLOSE-R2: danh sách gói và SHA tích hợp (revision 2)

- Candidate SHA đang kiểm định: `21d99fc89eb076a036b4d62f026b057a61d96135` (integration head, tiêu đề `integrate(ADAPT-LAUNCH-FIX1): lane lane-adapt-launch-fix1 candidate 9bcb10e680dc)
- Tổng số gói trong danh sách yêu cầu nghiệm thu mục 1: 133 gói (gồm 120 gói công việc và 13 cổng kiểm soát); danh sách kết thúc ở E-05
- Số gói/cổng đã tra cứu thành công SHA / recordHash: 133 / 133 (trong đó 119/119 gói công việc có commit integrate 40-hex, M4-CI-PLAN có SHA do Control cung cấp, 13/13 cổng kiểm soát có recordHash do Control cấp)
- Số gói thiếu SHA: 0

## Bảng đối chiếu các gói trong danh sách yêu cầu

| Mã gói | Loại | SHA tích hợp hoặc recordHash | Nguồn tra cứu |
| --- | --- | --- | --- |
| M4-CI-PLAN | Gói kế hoạch (Plan) | b18dbcff5e5beadb872b0d507b26cb88ffecf01e | SHA do Control cung cấp: gói nghiệm thu ở chuỗi chính trước khi có Portfolio, không có commit integrate; Control đã xác minh receipt Auditor PASS và commit nội dung là tổ tiên của nhánh tích hợp |
| IMPL-PLAN-A | Gói kế hoạch (Plan) | `fb154e9f0433d45bef1994e292a948231b18d112` (lane lane-impl-plan-a candidate 23c3e3cf22fb) | git log, subject `integrate(IMPL-PLAN-A): ...` |
| IMPL-PLAN-B | Gói kế hoạch (Plan) | `815bebb15b565c4a750854b4218a3296c7be2904` (lane lane-impl-plan-b candidate 6e139f3b2d3b) | git log, subject `integrate(IMPL-PLAN-B): ...` |
| IMPL-PLAN-C | Gói kế hoạch (Plan) | `4035610fa62c04ebcd7bc774b4a9e4ed68c5ad1a` (lane lane-impl-plan-c candidate 56dc6fa2a949) | git log, subject `integrate(IMPL-PLAN-C): ...` |
| IMPL-PLAN-I | Gói kế hoạch (Plan) | `14a2b92677ebf47724fab8a6229b340f45a1a3a7` (lane lane-impl-plan-i candidate 6b18b402e2f7) | git log, subject `integrate(IMPL-PLAN-I): ...` |
| IMPL-PLAN-D | Gói kế hoạch (Plan) | `bd037dc4c148a0a9d31cff9078bf4620b47fd815` (lane lane-impl-plan-d candidate ac0bf98832ed) | git log, subject `integrate(IMPL-PLAN-D): ...` |
| IMPL-PLAN-E | Gói kế hoạch (Plan) | `c73f90b87c3aa9bd038e9c1b71374ceb1b04a20f` (lane lane-impl-plan-e candidate 5e0fac5f84c4) | git log, subject `integrate(IMPL-PLAN-E): ...` |
| IMPL-PLAN-F | Gói kế hoạch (Plan) | `e336d92b9146b73d42da5f0346a55eef6c8d4386` (lane lane-impl-plan-f candidate 278d7617f114) | git log, subject `integrate(IMPL-PLAN-F): ...` |
| IMPL-PLAN-J | Gói kế hoạch (Plan) | `df699e2d86efeff98f7214fac6cdb40420440ca5` (lane lane-impl-plan-j candidate 1f901a0ef029) | git log, subject `integrate(IMPL-PLAN-J): ...` |
| IMPL-PLAN-G | Gói kế hoạch (Plan) | `5795450216f7b989a15d6b4c3db78276b594f113` (lane lane-impl-plan-g candidate f5bf44546610) | git log, subject `integrate(IMPL-PLAN-G): ...` |
| IMPL-PLAN-H | Gói kế hoạch (Plan) | `a461b76e086b8d41ce4f0607da1e2c2460d3c90f` (lane lane-impl-plan-h candidate 6ef168eb971f) | git log, subject `integrate(IMPL-PLAN-H): ...` |
| IMPL-PLAN-CONVERGENCE | Gói kế hoạch (Plan) | `d83ab6107189a14ba92fb3d8d81789f946b461a8` (lane lane-impl-plan-convergence candidate a5d863f65bf4) | git log, subject `integrate(IMPL-PLAN-CONVERGENCE): ...` |
| IMPL-PLAN-CONVERGENCE-EXT | Gói kế hoạch (Plan) | `3204b3ee38a76646bd6c05322eccd4f643ffab56` (lane lane-impl-plan-convergence-ext candidate c7a0e67ab18f) | git log, subject `integrate(IMPL-PLAN-CONVERGENCE-EXT): ...` |
| IMPL-PLAN-PERSIST | Gói kế hoạch (Plan) | `d9d23586d3af1fa6b2f2b6b741f3bd77e2178ab7` (lane lane-impl-plan-persist candidate e9761d25ac7e) | git log, subject `integrate(IMPL-PLAN-PERSIST): ...` |
| IMPL-PLAN-ADAPT | Gói kế hoạch (Plan) | `7823cf907f8c7ce056479b5fd09c502fbf570237` (lane lane-impl-plan-adapt candidate dc0949d5b990) | git log, subject `integrate(IMPL-PLAN-ADAPT): ...` |
| IMPL-PLAN-CONVERGENCE-EXT-UI | Gói kế hoạch (Plan) | `cd33459cd73cbb41accec6725e7c932da154198e` (lane lane-impl-plan-convergence-ext-ui candidate 89c22703dc93) | git log, subject `integrate(IMPL-PLAN-CONVERGENCE-EXT-UI): ...` |
| CP-3-MIGRATIONS-FIX1 | Gói sửa lỗi (Fix) | `836de0d664d3bcbc2dc5ff53013cb8b9c5a94cf0` (lane lane-cp-3-migrations-fix1 candidate a8a6cf78f104) | git log, subject `integrate(CP-3-MIGRATIONS-FIX1): ...` |
| CP-4-WIRING-FIX1 | Gói sửa lỗi (Fix) | `06d6c84d8b798f693eab635ab44007ebc23df263` (lane lane-cp-4-wiring-fix1 candidate 2309b3ab4898) | git log, subject `integrate(CP-4-WIRING-FIX1): ...` |
| PERSIST-G-FIX1 | Gói sửa lỗi (Fix) | `f03fed2f209808f80999643408f4f19a32cde567` (lane lane-persist-g-fix1 candidate 6f53564a6c56) | git log, subject `integrate(PERSIST-G-FIX1): ...` |
| CP-5-COMPLETION-FIX1 | Gói sửa lỗi (Fix) | `0ba3801fb9709dd85f7ff15330a877bfd3bf6561` (lane lane-cp-5-completion-fix1 candidate c2eaba9f3460) | git log, subject `integrate(CP-5-COMPLETION-FIX1): ...` |
| ADAPT-WIRE-FIX1 | Gói sửa lỗi (Fix) | `810c377c112f7ce082ab51564591ade9a519e0b0` (lane lane-adapt-wire-fix1 candidate f42c94477378) | git log, subject `integrate(ADAPT-WIRE-FIX1): ...` |
| CP-4-WIRING-FIX2 | Gói sửa lỗi (Fix) | `759ea0abd830f76b6f6a99232e8183ee50a9f34d` (lane lane-cp-4-wiring-fix2 candidate 5aed9712848f) | git log, subject `integrate(CP-4-WIRING-FIX2): ...` |
| ADAPT-PROD-FIX1 | Gói sửa lỗi (Fix) | `6ba0bcde40de3d3adf8405d9df6bd8cae431227a` (lane lane-adapt-prod-fix1 candidate d588d9c0e8b0) | git log, subject `integrate(ADAPT-PROD-FIX1): ...` |
| CP-4B-UI-SCREENS-FIX1 | Gói sửa lỗi (Fix) | `adc7634f45a21c2fa174adee662962d7a1b21a57` (lane lane-cp-4b-ui-screens-fix1 candidate 2760ee3ca0f9) | git log, subject `integrate(CP-4B-UI-SCREENS-FIX1): ...` |
| PERSIST-C-FIX1 | Gói sửa lỗi (Fix) | `ab8586d55fc612825888d6a7e26e58ae96d28af6` (lane lane-persist-c-fix1 candidate 2327dcf8e326) | git log, subject `integrate(PERSIST-C-FIX1): ...` |
| ADAPT-PROD-FIX2 | Gói sửa lỗi (Fix) | `fa250e8305aa422ff260f2ce9bb3622a29239740` (lane lane-adapt-prod-fix2 candidate e1cc7f40b25b) | git log, subject `integrate(ADAPT-PROD-FIX2): ...` |
| CP-4B-UI-SCREENS-FIX2 | Gói sửa lỗi (Fix) | `74c062a29d649ea0e3d1471dee9c739dc33d38fe` (lane lane-cp-4b-ui-screens-fix2 candidate 1c85775dea49) | git log, subject `integrate(CP-4B-UI-SCREENS-FIX2): ...` |
| ADAPT-LAUNCH-FIX1 | Gói sửa lỗi (Fix) | `21d99fc89eb076a036b4d62f026b057a61d96135` (lane lane-adapt-launch-fix1 candidate 9bcb10e680dc) | git log, subject `integrate(ADAPT-LAUNCH-FIX1): ...` |
| A-01 | Lát cắt triển khai (Slice) | `22535f6dcff3dbf2e3187771a9bff1b34c85c838` (lane lane-a-01 candidate b11289d9c406) | git log, subject `integrate(A-01): ...` |
| A-02 | Lát cắt triển khai (Slice) | `e343a41ee6570c39d0cbeda2bd35a3bf2c15513f` (lane lane-a-02 candidate 0614e8d1934d) | git log, subject `integrate(A-02): ...` |
| A-03 | Lát cắt triển khai (Slice) | `5e009d1c06ba60052bdd1658f939ffaadc626597` (lane lane-a-03 candidate 6382ebd2cdde) | git log, subject `integrate(A-03): ...` |
| A-04 | Lát cắt triển khai (Slice) | `f1d4a4c543fb9c14a48c3e44e82c20622d0ddc34` (lane lane-a-04 candidate c512aedfd810) | git log, subject `integrate(A-04): ...` |
| A-05 | Lát cắt triển khai (Slice) | `596237ae94bcb7ba0bbc7b8536b6b12d4a95ea93` (lane lane-a-05 candidate 8c4c80c5982e) | git log, subject `integrate(A-05): ...` |
| A-06 | Lát cắt triển khai (Slice) | `7f6c060c32c3dc545b857a1714b5fea0b445429f` (lane lane-a-06 candidate 1b7754bbf77a) | git log, subject `integrate(A-06): ...` |
| A-07 | Lát cắt triển khai (Slice) | `ae8d0e3e4a02ea36a357b990d7e6d62e8326f3d1` (lane lane-a-07 candidate e58ac323b47f) | git log, subject `integrate(A-07): ...` |
| A-08 | Lát cắt triển khai (Slice) | `c18f5fd14fd57c308b1d8e42128cbbb063a4ef74` (lane lane-a-08 candidate b867f1f24233) | git log, subject `integrate(A-08): ...` |
| A-09 | Lát cắt triển khai (Slice) | `ec82a8154aeaf956305e08c493e07c4736dcf1de` (lane lane-a-09 candidate 9c93960aee60) | git log, subject `integrate(A-09): ...` |
| A-10 | Lát cắt triển khai (Slice) | `a93ae583b468e7d61c4efe63d7609ff83ee4bed1` (lane lane-a-10 candidate 18233ddf6c7b) | git log, subject `integrate(A-10): ...` |
| A-11 | Lát cắt triển khai (Slice) | `66e0591dc74b4f2e09b005c2cd4715f74b06280c` (lane lane-a-11 candidate 8425147edd1b) | git log, subject `integrate(A-11): ...` |
| A-12 | Lát cắt triển khai (Slice) | `bad89e191f3ddd653febc2626eb80d813c93f8b8` (lane lane-a-12 candidate 044cdf1a9075) | git log, subject `integrate(A-12): ...` |
| A-13 | Lát cắt triển khai (Slice) | `ccfd11131d7f8e8dd6a5340ac48d8a2e16c7111d` (lane lane-a-13 candidate b46a5591d574) | git log, subject `integrate(A-13): ...` |
| A-14 | Lát cắt triển khai (Slice) | `4efa4f6c3d3a11b7610bcd06707fe8105e3933e0` (lane lane-a-14 candidate 4d292f278aab) | git log, subject `integrate(A-14): ...` |
| A-15 | Lát cắt triển khai (Slice) | `11128dc8b3f7d27b885d3f6e3803c5822c6ed468` (lane lane-a-15 candidate b09724147f4a) | git log, subject `integrate(A-15): ...` |
| A-16 | Lát cắt triển khai (Slice) | `bfc0d32e2bbe8f897229b9b87d77f91f200f3e9d` (lane lane-a-16 candidate 1f2f3d17bd69) | git log, subject `integrate(A-16): ...` |
| A-17 | Lát cắt triển khai (Slice) | `3529edc34d9444d9629a3191c34dc07ab72a2d07` (lane lane-a-17 candidate a5f13fc184bb) | git log, subject `integrate(A-17): ...` |
| A-18 | Lát cắt triển khai (Slice) | `773af60b0f148d6212f261abeb57c71fb5bde4b7` (lane lane-a-18 candidate ba3370b8578b) | git log, subject `integrate(A-18): ...` |
| A-19 | Lát cắt triển khai (Slice) | `b75a132ef7ab944d785b8c39ff0295584d547a39` (lane lane-a-19 candidate de07c98c6b4f) | git log, subject `integrate(A-19): ...` |
| ADAPT-DEPS | Gói tích hợp (Integration) | `fb7bca7f0d6c40142ca623d40b6e1921340e4abe` (lane lane-adapt-deps candidate 0db5b62042e2) | git log, subject `integrate(ADAPT-DEPS): ...` |
| ADAPT-A | Gói tích hợp (Integration) | `985d542dbaf148d76d1651ddedb0bf448a7a312c` (lane lane-adapt-a candidate fbb90573e8f9) | git log, subject `integrate(ADAPT-A): ...` |
| ADAPT-D | Gói tích hợp (Integration) | `69cf7ce8e28c8cebb26a97eabb289c84feb5eeef` (lane lane-adapt-d candidate 747cf2ba3e58) | git log, subject `integrate(ADAPT-D): ...` |
| ADAPT-E | Gói tích hợp (Integration) | `97a13ddd384c486c5b8b9367d3e36c1f96b5f92b` (lane lane-adapt-e candidate 734c02ce1499) | git log, subject `integrate(ADAPT-E): ...` |
| ADAPT-E-MEDIA | Gói tích hợp (Integration) | `5dcf3d5c3252f884a812932b3d8ab5a61493439f` (lane lane-adapt-e-media candidate 5c632b65335d) | git log, subject `integrate(ADAPT-E-MEDIA): ...` |
| ADAPT-F | Gói tích hợp (Integration) | `4c4486a9cd1e38a91d0374530933aa3860fb6a5a` (lane lane-adapt-f candidate 54bf210b7df8) | git log, subject `integrate(ADAPT-F): ...` |
| ADAPT-J | Gói tích hợp (Integration) | `b5550a06a10d64c33eedc74d28b19569c431dfb2` (lane lane-adapt-j candidate fb5ef89cb2ff) | git log, subject `integrate(ADAPT-J): ...` |
| ADAPT-I | Gói tích hợp (Integration) | `fbbe798a06d4030f1dfc8a48399af5ffb704d15e` (lane lane-adapt-i candidate 8b142a0a7ecc) | git log, subject `integrate(ADAPT-I): ...` |
| ADAPT-CONFIG | Gói tích hợp (Integration) | `fe206ac52815f87769890b77efc7d8c51807528f` (lane lane-adapt-config candidate 2680d83e4f06) | git log, subject `integrate(ADAPT-CONFIG): ...` |
| ADAPT-WIRE | Gói tích hợp (Integration) | `a046fa4c6784cd1ea3fcf1900e769b6bee3a9863` (lane lane-adapt-wire candidate f4e443d18434) | git log, subject `integrate(ADAPT-WIRE): ...` |
| ADAPT-SEED | Gói tích hợp (Integration) | `497a06b5f0f0783ea42200cb35f0f922f2cad09d` (lane lane-adapt-seed candidate b97c9596725d) | git log, subject `integrate(ADAPT-SEED): ...` |
| ADAPT-PROD | Gói tích hợp (Integration) | `790f768269fd2e1218fdeb7aec82621dfa415827` (lane lane-adapt-prod candidate 62c610c36106) | git log, subject `integrate(ADAPT-PROD): ...` |
| ADAPT-LAUNCH | Gói tích hợp (Integration) | `cc290f002074514001fa0b03b3eb8c9e00c14db6` (lane lane-adapt-launch candidate faa54f225bdc) | git log, subject `integrate(ADAPT-LAUNCH): ...` |
| B-1 | Lát cắt triển khai (Slice) | `91878d46206a05e052217b54e81af614b6ba1bf7` (lane lane-b-1 candidate 92dbcc6f018b) | git log, subject `integrate(B-1): ...` |
| B-2 | Lát cắt triển khai (Slice) | `1a17e1181c6049618d93b905126c58cae5d21877` (lane lane-b-2 candidate 5d34dbaf7d91) | git log, subject `integrate(B-2): ...` |
| B-3 | Lát cắt triển khai (Slice) | `8434f096979606c15fb444c498f08dd109e56bc3` (lane lane-b-3 candidate c478e5d6c957) | git log, subject `integrate(B-3): ...` |
| B-4 | Lát cắt triển khai (Slice) | `0ad4cbf564484cec02bbeffa18ea3796349b4a91` (lane lane-b-4 candidate 5f6e0fc76525) | git log, subject `integrate(B-4): ...` |
| B-5 | Lát cắt triển khai (Slice) | `ec66302c0da0adcc0f99de10a983a393563851de` (lane lane-b-5 candidate 318d6e6731a1) | git log, subject `integrate(B-5): ...` |
| B-6 | Lát cắt triển khai (Slice) | `76b81ca29ac1159d4bd6f685da478df9e0911b3b` (lane lane-b-6 candidate b862577c5ac2) | git log, subject `integrate(B-6): ...` |
| B-7 | Lát cắt triển khai (Slice) | `94f50610690a94c567ca47980922cc8c7d78b132` (lane lane-b-7 candidate 357fbc957082) | git log, subject `integrate(B-7): ...` |
| B-8 | Lát cắt triển khai (Slice) | `f464d5b05de813f4b542d8f01d1ced48dbeff0a5` (lane lane-b-8 candidate 02aef71e0d5c) | git log, subject `integrate(B-8): ...` |
| B-9 | Lát cắt triển khai (Slice) | `5a12c257a1f46ad4695d51e161104e9784ed76a2` (lane lane-b-9 candidate 45cd8a8a1a7b) | git log, subject `integrate(B-9): ...` |
| B-10 | Lát cắt triển khai (Slice) | `a8914387d3e3f8cdc322baa06c0d2b23650d5560` (lane lane-b-10 candidate 309798fc096d) | git log, subject `integrate(B-10): ...` |
| B-11 | Lát cắt triển khai (Slice) | `d1961a482f8f04364c3edb98c562cb98b126193d` (lane lane-b-11 candidate bb3b1e14ff81) | git log, subject `integrate(B-11): ...` |
| B-12 | Lát cắt triển khai (Slice) | `c8514bd1ba916e7be55561659dce0661e7c7e81e` (lane lane-b-12 candidate 3d5c8467b4ec) | git log, subject `integrate(B-12): ...` |
| C-01 | Lát cắt triển khai (Slice) | `5b5d282e1862f8ff9a19831147bcf3ceec7fcf7e` (lane lane-c-01 candidate bc1144fa816a) | git log, subject `integrate(C-01): ...` |
| C-02 | Lát cắt triển khai (Slice) | `003d991458706b63f97573b39567fe29574cc6cb` (lane lane-c-02 candidate c6d6afa65c61) | git log, subject `integrate(C-02): ...` |
| C-03 | Lát cắt triển khai (Slice) | `be1fa2ef1c1cfa31173aee1c6dff878ac2793b02` (lane lane-c-03 candidate 06c42477bb10) | git log, subject `integrate(C-03): ...` |
| C-04 | Lát cắt triển khai (Slice) | `354d46c041501b32c8df147af1728c3915df65f4` (lane lane-c-04 candidate af457adf2c1e) | git log, subject `integrate(C-04): ...` |
| C-05 | Lát cắt triển khai (Slice) | `cbd256247045936fd2b5b07c3eca8fbfac7b737d` (lane lane-c-05 candidate 7dcf357e5b8f) | git log, subject `integrate(C-05): ...` |
| C-06 | Lát cắt triển khai (Slice) | `2233e36f669f9ea4d8ffdd9b0724aa8c9fe19753` (lane lane-c-06 candidate b6fc4471c652) | git log, subject `integrate(C-06): ...` |
| C-07 | Lát cắt triển khai (Slice) | `9207e232ceb28c85c8da32f8eec9a7b9866be53d` (lane lane-c-07 candidate 46d398a3abf6) | git log, subject `integrate(C-07): ...` |
| C-08 | Lát cắt triển khai (Slice) | `4f956426cf8a28182acd5cba47ceebe368f9908f` (lane lane-c-08 candidate 71e745c7add3) | git log, subject `integrate(C-08): ...` |
| C-09 | Lát cắt triển khai (Slice) | `a800f8790e9eee9937165c13b020d33b39739dc2` (lane lane-c-09 candidate 8831823a18f2) | git log, subject `integrate(C-09): ...` |
| CP-4-EVENT-KINDS | Gói tích hợp (Integration) | `428e3dd9bf22027f418228464784576beefe396c` (lane lane-cp-4-event-kinds candidate 6c91a490b2b1) | git log, subject `integrate(CP-4-EVENT-KINDS): ...` |
| CP-4-PAGINATION | Gói tích hợp (Integration) | `4412a0afad9f40096fff00f17903043636d14bd7` (lane lane-cp-4-pagination candidate 995e98542fd6) | git log, subject `integrate(CP-4-PAGINATION): ...` |
| CP-4-QUERIES | Gói tích hợp (Integration) | `ed3bf7a48207198201b4c76965557afdc12702c6` (lane lane-cp-4-queries candidate c7e02fef94c2) | git log, subject `integrate(CP-4-QUERIES): ...` |
| CP-4B-UI-SCREENS | Gói tích hợp (Integration) | `a8533a71456b3ce573fcb8bbe68b2a21729e863d` (lane lane-cp-4b-ui-screens candidate 3aa670cd9779) | git log, subject `integrate(CP-4B-UI-SCREENS): ...` |
| CP-2B-RUNTIME-PATHS | Gói tích hợp (Integration) | `bdb8d794001b81511f33451e17e200d6713ff9ea` (lane lane-cp-2b-runtime-paths candidate 6ec64fbb85aa) | git log, subject `integrate(CP-2B-RUNTIME-PATHS): ...` |
| CP-2B-PACKAGES | Gói tích hợp (Integration) | `3e15f146f9cd926403173a6b63d70db747090450` (lane lane-cp-2b-packages candidate fa3a6a14ddc3) | git log, subject `integrate(CP-2B-PACKAGES): ...` |
| CP-2D-REGISTRY | Gói tích hợp (Integration) | `2f3e42ef4e9d752735d67544a18bbeb0bda192c6` (lane lane-cp-2d-registry candidate 87f32a597cc7) | git log, subject `integrate(CP-2D-REGISTRY): ...` |
| CP-3C-STATE-EDGES | Gói tích hợp (Integration) | `2d8a9686da7c7261d67a406c153a912d3f4de36d` (lane lane-cp-3c-state-edges candidate bf68ad98e494) | git log, subject `integrate(CP-3C-STATE-EDGES): ...` |
| CP-5-COMPLETION | Gói tích hợp (Integration) | `a59b9d8bba79216713b40bac3848da2adc0095b5` (lane lane-cp-5-completion candidate f17273076ac3) | git log, subject `integrate(CP-5-COMPLETION): ...` |
| CP-6-WORKFLOW | Gói tích hợp (Integration) | `638abf7837d5706bb29223704a152b973f854951` (lane lane-cp-6-workflow candidate a16dad6229eb) | git log, subject `integrate(CP-6-WORKFLOW): ...` |
| CP-2B-DEPS | Gói tích hợp (Integration) | `b10dc7c86fc396f9aee9c3a03586c1d883cdc661` (lane lane-cp-2b-deps candidate 8cda6c756f76) | git log, subject `integrate(CP-2B-DEPS): ...` |
| CP-2C-M2-REGRESSION | Gói tích hợp (Integration) | `0e54a54e8700855d095ebac8267b1474ab878455` (lane lane-cp-2c-m2-regression candidate 302b16965aec) | git log, subject `integrate(CP-2C-M2-REGRESSION): ...` |
| CP-3B-STATE-MACHINE | Gói tích hợp (Integration) | `0adb2bbd0ee4140dd8cf3650ea9b7ffb6ca4b450` (lane lane-cp-3b-state-machine candidate b3a040ffd687) | git log, subject `integrate(CP-3B-STATE-MACHINE): ...` |
| CP-3-MIGRATIONS | Gói tích hợp (Integration) | `a3d84e838a0937515eb62eb5c3a35016ab88e7df` (lane lane-cp-3-migrations candidate b33cdd34eb40) | git log, subject `integrate(CP-3-MIGRATIONS): ...` |
| CP-4-WIRING | Gói tích hợp (Integration) | `750195f1a88ee5bc731893d8986992b7b97c442b` (lane lane-cp-4-wiring candidate 06b6d6b453ca) | git log, subject `integrate(CP-4-WIRING): ...` |
| CP-4B-UI-SHELL | Gói tích hợp (Integration) | `42c328c98f7c0890d01fb3a590bf43a3f78eb2fb` (lane lane-cp-4b-ui-shell candidate 858d8179ba66) | git log, subject `integrate(CP-4B-UI-SHELL): ...` |
| GATE-CP-2D-REGISTRY | Cổng kiểm soát (Gate) | `00103f0a72d7b9e2f1f5803cc699db79373ac38ed2e47aa206f975da0eab9514` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-CP-5-COMPLETION | Cổng kiểm soát (Gate) | `3b9e4c9d779043c2f76022541f4524b931ad48cce3cad2e4bc4dfff7cfb54d90` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-CP-6-WORKFLOW | Cổng kiểm soát (Gate) | `2be7562bea521bede4812d8b5cff124d201b562b93a416b1972baca08d720190` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-CP-2B-DEPS-PATHS | Cổng kiểm soát (Gate) | `3bd11714d6cb8196cb1c800bc740a76e7a4436b905cb2c98d2a8400fa1d132cf` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-PERSIST-A | Cổng kiểm soát (Gate) | `1ccf6c904ef88886ed1dd7a66b50c2206fd1c12ac5357d926572dbf53135a343` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-PERSIST-B | Cổng kiểm soát (Gate) | `39f5e7e8bc503704574da52b3605d1a03911b24c29494514c865af229ca35bf4` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-PERSIST-C | Cổng kiểm soát (Gate) | `5327ae192465197cc63aa6f6e1ebc4670e06c063f6a1fb46a4b7e6a3ce4066f2` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-PERSIST-D | Cổng kiểm soát (Gate) | `794e8b5634d3adaab3d35154ae2f0d732f2dc86a477ca8faeb2cd10cbd79506f` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-PERSIST-E | Cổng kiểm soát (Gate) | `b38673dd8c05bac07daae786cf282bcbae1cb359ea80fcd24b806bf5eab94ae7` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-PERSIST-F | Cổng kiểm soát (Gate) | `7254c80039939250ee1d2b372b627655b8b60b998372d7c9652b4360042a9055` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-PERSIST-G | Cổng kiểm soát (Gate) | `f71b035ffeface811ea87ccc06ba8a13129922fed922018793672d14d244fe7d` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-PERSIST-I | Cổng kiểm soát (Gate) | `b987fc8b60eaddba804f31ce51c78cfc9047db41d42203882ea5fae37c31843e` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| GATE-PERSIST-J | Cổng kiểm soát (Gate) | `cc9e80f551c0a83996a2ff710c7ce2d8d73517eed0434d4c176e55403d1399de` | recordHash do Control cấp trong yêu cầu nghiệm thu (bản ghi quyết định RELEASE); không đọc sổ quyết định |
| D-01 | Lát cắt triển khai (Slice) | `1d56b2699f6f6a2c08346da3db1107e435c234eb` (lane lane-d-01 candidate b2a81a892125) | git log, subject `integrate(D-01): ...` |
| D-02 | Lát cắt triển khai (Slice) | `d525f9275b0a5062b673d0b307b2707f98d26e12` (lane lane-d-02 candidate 9ca090a7b919) | git log, subject `integrate(D-02): ...` |
| D-03 | Lát cắt triển khai (Slice) | `cf44f24a63971600a198a9afdf7d8a35421fb248` (lane lane-d-03 candidate eaa8dad378e7) | git log, subject `integrate(D-03): ...` |
| D-04 | Lát cắt triển khai (Slice) | `dff70cc63be1c08c1cd33a4856a39deea7483523` (lane lane-d-04 candidate 7ea9f67e12da) | git log, subject `integrate(D-04): ...` |
| D-05 | Lát cắt triển khai (Slice) | `bdd2916e35e1c907d1141a1139e872690b2e5acb` (lane lane-d-05 candidate 27f7dadb9233) | git log, subject `integrate(D-05): ...` |
| D-06 | Lát cắt triển khai (Slice) | `91000e325c7a72572aec729d3bcfc8ed20c1ae51` (lane lane-d-06 candidate fcf0147eb038) | git log, subject `integrate(D-06): ...` |
| D-07 | Lát cắt triển khai (Slice) | `5646473e81669af7143ea98e81869927ec761f5f` (lane lane-d-07 candidate 324777971bf3) | git log, subject `integrate(D-07): ...` |
| D-08 | Lát cắt triển khai (Slice) | `1b44a9460b1f18e33309cd4255c2e50e4552a470` (lane lane-d-08 candidate 6db601c34c55) | git log, subject `integrate(D-08): ...` |
| D-09 | Lát cắt triển khai (Slice) | `4aeaf9fb552e1c717c20614cbd9ab2487ff850fc` (lane lane-d-09 candidate acf373e72ef9) | git log, subject `integrate(D-09): ...` |
| D-10 | Lát cắt triển khai (Slice) | `89b0e328f18b9ad438dd217044c116ad0c386501` (lane lane-d-10 candidate b90570d461a7) | git log, subject `integrate(D-10): ...` |
| D-11 | Lát cắt triển khai (Slice) | `8797e8d2cf79002f4b080dfefbbbeaa945cd687a` (lane lane-d-11 candidate 538fd130d1ae) | git log, subject `integrate(D-11): ...` |
| D-12 | Lát cắt triển khai (Slice) | `3e6932884111da7ec41d854a3f39708a626c49aa` (lane lane-d-12 candidate 14c9b16f8362) | git log, subject `integrate(D-12): ...` |
| D-13 | Lát cắt triển khai (Slice) | `8123aba43315b3c836df2740aeb5fd25b017214d` (lane lane-d-13 candidate e25a63a8afb9) | git log, subject `integrate(D-13): ...` |
| D-14 | Lát cắt triển khai (Slice) | `bcda8664b9621875d25ba2359b95d3d0360a36b2` (lane lane-d-14 candidate fe635dd2c6ef) | git log, subject `integrate(D-14): ...` |
| D-15 | Lát cắt triển khai (Slice) | `7f5cb179669672e1f0a9f77430534c3826e76a20` (lane lane-d-15 candidate 7223acde4dbf) | git log, subject `integrate(D-15): ...` |
| D-16 | Lát cắt triển khai (Slice) | `8c66d619acbc12c4a6c202c8cdb4ca8e26447e9f` (lane lane-d-16 candidate 49e5a2845818) | git log, subject `integrate(D-16): ...` |
| D-17 | Lát cắt triển khai (Slice) | `4645f6217894c6b873cbfe5576c4b1ae8aaf0d23` (lane lane-d-17 candidate b94526322ad9) | git log, subject `integrate(D-17): ...` |
| D-18 | Lát cắt triển khai (Slice) | `febeb176885bf16a5e27f5a2b344a8480a25f0c9` (lane lane-d-18 candidate 669f67fa1840) | git log, subject `integrate(D-18): ...` |
| E-01 | Lát cắt triển khai (Slice) | `170b96b2748929758f96d9b5a54726be29fb7600` (lane lane-e-01 candidate c1e0e06e1f98) | git log, subject `integrate(E-01): ...` |
| E-02 | Lát cắt triển khai (Slice) | `dd68637ba76c9e3213de9b564226e2e69f35f230` (lane lane-e-02 candidate 683e3e8396c4) | git log, subject `integrate(E-02): ...` |
| E-03 | Lát cắt triển khai (Slice) | `3f89da586c1ffc46c04d3a3f2793f0c0921d24fd` (lane lane-e-03 candidate c426045eb0f9) | git log, subject `integrate(E-03): ...` |
| E-04 | Lát cắt triển khai (Slice) | `f54199a752a19475f567738a7c70eb108d583316` (lane lane-e-04 candidate 7a2fb4c4fc40) | git log, subject `integrate(E-04): ...` |
| E-05 | Lát cắt triển khai (Slice) | `3f026bb8ba5c01a566dde9fffcc0480c727dcdf3` (lane lane-e-05 candidate 880bb810bb04) | git log, subject `integrate(E-05): ...` |

## Gói ngoài danh sách yêu cầu: E-06..E-20 và F-01..F-07

22 gói E-06..E-20 và F-01..F-07 nằm ngoài danh sách yêu cầu nghiệm thu (danh sách kết thúc ở E-05); ghi SHA tích hợp chỉ để tham khảo, không tính vào tổng 133.

| Mã gói | Loại | SHA tích hợp hoặc recordHash | Nguồn tra cứu |
| --- | --- | --- | --- |
| E-06 | Lát cắt triển khai (Slice) | d3887fa6a224395ad1e37e00e866a8e7def930e0 (lane lane-e-06 candidate da1e6a7ba167) | git log, subject integrate(E-06): ... |
| E-07 | Lát cắt triển khai (Slice) | 2e7c6b1ca42d83ed16dac720ca98388b1bd06ecc (lane lane-e-07 candidate a8abf025014b) | git log, subject integrate(E-07): ... |
| E-08 | Lát cắt triển khai (Slice) | 1bfb8b02dc928a2455330afa45edc768226a63e5 (lane lane-e-08 candidate 8dfaedb513d4) | git log, subject integrate(E-08): ... |
| E-09 | Lát cắt triển khai (Slice) | `c695121600c8d1b73e9153cbd26dab92cf2f6b18` (lane lane-e-09 candidate 8c4ed2542c25) | git log, subject `integrate(E-09): ...` |
| E-10 | Lát cắt triển khai (Slice) | `af9306a233fc2bed399d696fb87918f5c8e7dfe0` (lane lane-e-10 candidate 237353be4524) | git log, subject `integrate(E-10): ...` |
| E-11 | Lát cắt triển khai (Slice) | `6945c76b1b309084663e2e0a6b2b668bebad88fc` (lane lane-e-11 candidate 37b5acbde850) | git log, subject `integrate(E-11): ...` |
| E-12 | Lát cắt triển khai (Slice) | `9d7459596ab9d0f69020c644c437b6523ffec755` (lane lane-e-12 candidate 1d8150785261) | git log, subject `integrate(E-12): ...` |
| E-13 | Lát cắt triển khai (Slice) | `ccbfbb5771f4b8bca783f3d2c94cbcc7f328d5b4` (lane lane-e-13 candidate cd3796837303) | git log, subject `integrate(E-13): ...` |
| E-14 | Lát cắt triển khai (Slice) | `cab81bda5c60f7c120126d832d4b48e0765315cf` (lane lane-e-14 candidate 3ac7c2fb4883) | git log, subject `integrate(E-14): ...` |
| E-15 | Lát cắt triển khai (Slice) | `ab7cb613044212edf40e03817b75d6d648823269` (lane lane-e-15 candidate b395a9b7f9fa) | git log, subject `integrate(E-15): ...` |
| E-16 | Lát cắt triển khai (Slice) | `cbb7507a6df2fec1b8283ce63fcc82cca963f8fc` (lane lane-e-16 candidate 55f2c4d92d1e) | git log, subject `integrate(E-16): ...` |
| E-17 | Lát cắt triển khai (Slice) | `4ee2962f959ced2455af2cbb0642655d7f076c57` (lane lane-e-17 candidate 60a514f00404) | git log, subject `integrate(E-17): ...` |
| E-18 | Lát cắt triển khai (Slice) | `5734017c335265c0e32a214e7a59fa7c2d0b6010` (lane lane-e-18 candidate 457083608ac4) | git log, subject `integrate(E-18): ...` |
| E-19 | Lát cắt triển khai (Slice) | `1f6f35d6bfb9063eb24c83d688e22821842c5e67` (lane lane-e-19 candidate fff0f48af09c) | git log, subject `integrate(E-19): ...` |
| E-20 | Lát cắt triển khai (Slice) | `48769ce5899afb3c275f6efb37ff9dea215154e2` (lane lane-e-20 candidate 997405b26808) | git log, subject `integrate(E-20): ...` |
| F-01 | Lát cắt triển khai (Slice) | `4daa3e625fcac2d0d28a1bf01f925467fd958ff7` (lane lane-f-01 candidate 603f5de01b5a) | git log, subject `integrate(F-01): ...` |
| F-02 | Lát cắt triển khai (Slice) | `6edd27271fc7408d857d4dcaafbfbae308c7f73f` (lane lane-f-02 candidate ba2e313d5b1f) | git log, subject `integrate(F-02): ...` |
| F-03 | Lát cắt triển khai (Slice) | `cfd868a1406b38b34a1c05230e60b26e82692726` (lane lane-f-03 candidate f9a57ed36fe6) | git log, subject `integrate(F-03): ...` |
| F-04 | Lát cắt triển khai (Slice) | `96f8e85c90b97cb6e0effeafa1cfca92c35fb8d4` (lane lane-f-04 candidate 2c76c72dcb34) | git log, subject `integrate(F-04): ...` |
| F-05 | Lát cắt triển khai (Slice) | `100bfcb0fcfcc4b9940c5c07a9b4afa82e1f9a45` (lane lane-f-05 candidate 8516288f5417) | git log, subject `integrate(F-05): ...` |
| F-06 | Lát cắt triển khai (Slice) | `7622e01f50b6257f93a5c0b90f84880b5c9bf952` (lane lane-f-06 candidate c28e40d61e92) | git log, subject `integrate(F-06): ...` |
| F-07 | Lát cắt triển khai (Slice) | `b8dc82489eb61f7e284e02ab8d4e0be7b817fc27` (lane lane-f-07 candidate d70d7c536116) | git log, subject `integrate(F-07): ...` |

## Gói ngoài danh sách yêu cầu (tiếp): F-08..F-22, G, H, I, J và gói nền tảng

79 gói F-08..F-22, G-01..G-14, H-01..H-16, I-01..I-13, J-01..J-18, CP0-GOVERNANCE, CP1-CONTRACT-BINDING và CP2A-LAYOUT cũng nằm ngoài danh sách yêu cầu; ghi SHA tích hợp để Reviewer và Orchestrator đối chiếu, không tính vào tổng 133.

| Mã gói | Loại | SHA tích hợp hoặc recordHash | Nguồn tra cứu |
| --- | --- | --- | --- |
| F-08 | Lát cắt triển khai bổ sung (Slice) | `95efd236a7bf8b07dc6c0aae751d1992d2c8ef5b` (lane lane-f-08 candidate 9c31b35843c5) | git log, subject `integrate(F-08): ...` |
| F-09 | Lát cắt triển khai bổ sung (Slice) | `c8cfa82317412bd023f3e19e9134f470f4fb5fce` (lane lane-f-09 candidate 4d1fdeea9582) | git log, subject `integrate(F-09): ...` |
| F-10 | Lát cắt triển khai bổ sung (Slice) | `4bbe03d06091909a4ca31ac63850a4dc94ce20fe` (lane lane-f-10 candidate a2266598f3c9) | git log, subject `integrate(F-10): ...` |
| F-11 | Lát cắt triển khai bổ sung (Slice) | `580a981df3450c85f49558ead2a486b77ed3e68c` (lane lane-f-11 candidate 5891f0465962) | git log, subject `integrate(F-11): ...` |
| F-12 | Lát cắt triển khai bổ sung (Slice) | `6f1cf65b2e2c822f84fc951158bd3086a65cd758` (lane lane-f-12 candidate 89dd41cda238) | git log, subject `integrate(F-12): ...` |
| F-13 | Lát cắt triển khai bổ sung (Slice) | `d5e2573211069e1d7d212fead48a5fcdd70c26f3` (lane lane-f-13 candidate 4a3da74249c9) | git log, subject `integrate(F-13): ...` |
| F-14 | Lát cắt triển khai bổ sung (Slice) | `4dc0964ce286447d5d95987b402d08b9e99cdfa5` (lane lane-f-14 candidate bb2f5d106c62) | git log, subject `integrate(F-14): ...` |
| F-15 | Lát cắt triển khai bổ sung (Slice) | `8fc0a24d980ad0de18f4f5e34542151e971a842b` (lane lane-f-15 candidate a8166444db02) | git log, subject `integrate(F-15): ...` |
| F-16 | Lát cắt triển khai bổ sung (Slice) | `a5ed0e1569a24c7699bc0a184c47b9a500f30e17` (lane lane-f-16 candidate 1eac899e6206) | git log, subject `integrate(F-16): ...` |
| F-17 | Lát cắt triển khai bổ sung (Slice) | `d7f79a2aca73e091126fa1b788d4668b9801b0b3` (lane lane-f-17 candidate d50d0d8e1602) | git log, subject `integrate(F-17): ...` |
| F-18 | Lát cắt triển khai bổ sung (Slice) | `4381df15795a818cc8c774b84e55fe7b923237d3` (lane lane-f-18 candidate ace01aaf9b75) | git log, subject `integrate(F-18): ...` |
| F-19 | Lát cắt triển khai bổ sung (Slice) | `b6a4796674c86648798f1a5c41e263246acbba49` (lane lane-f-19 candidate dd031a190418) | git log, subject `integrate(F-19): ...` |
| F-20 | Lát cắt triển khai bổ sung (Slice) | `d6244988169563ae638cf419c73fafb43ff04a7a` (lane lane-f-20 candidate 19651248ab56) | git log, subject `integrate(F-20): ...` |
| F-21 | Lát cắt triển khai bổ sung (Slice) | `b61497009eccadcef157bc797e4eb1f9263b7f63` (lane lane-f-21 candidate 6beaab0677ce) | git log, subject `integrate(F-21): ...` |
| F-22 | Lát cắt triển khai bổ sung (Slice) | `bf52905b3b8547f82a51aa2ccc926f7b7ae1b0bc` (lane lane-f-22 candidate d40433158cc7) | git log, subject `integrate(F-22): ...` |
| G-01 | Lát cắt triển khai bổ sung (Slice) | `0591304d66208f1b9c445a437d793b1c1bb7210b` (lane lane-g-01 candidate ce5b3bf82eb1) | git log, subject `integrate(G-01): ...` |
| G-02 | Lát cắt triển khai bổ sung (Slice) | `bb8fe184f25fbe36ed0bdefa1bbffb162c1d4634` (lane lane-g-02 candidate f34da0dcd82f) | git log, subject `integrate(G-02): ...` |
| G-03 | Lát cắt triển khai bổ sung (Slice) | `23a1c347fc8abac60f20946be6e4c6155747995d` (lane lane-g-03 candidate 23e40f054191) | git log, subject `integrate(G-03): ...` |
| G-04 | Lát cắt triển khai bổ sung (Slice) | `4fd21816ce8c657983f0e09d226209f381b13f5c` (lane lane-g-04 candidate 50941b02e1a4) | git log, subject `integrate(G-04): ...` |
| G-05 | Lát cắt triển khai bổ sung (Slice) | `c25a524c0a8e455495d7214d61bfa09cfaa47f5f` (lane lane-g-05 candidate cfedb166ea6c) | git log, subject `integrate(G-05): ...` |
| G-06 | Lát cắt triển khai bổ sung (Slice) | `9dd3efea87d4172a55ae0bdd8e8b8f93025dc57c` (lane lane-g-06 candidate a4569af78354) | git log, subject `integrate(G-06): ...` |
| G-07 | Lát cắt triển khai bổ sung (Slice) | `1f92cf4e3edb03004573fffcc020f5a1b2bc3da6` (lane lane-g-07 candidate 3a358b083b86) | git log, subject `integrate(G-07): ...` |
| G-08 | Lát cắt triển khai bổ sung (Slice) | `997706710403ed4113ca1633391c2eda2b3314e9` (lane lane-g-08 candidate ce3a757cf471) | git log, subject `integrate(G-08): ...` |
| G-09 | Lát cắt triển khai bổ sung (Slice) | `1aa9fb870e8a8392dbce3c22dc7392695909f4f9` (lane lane-g-09 candidate a1f1c1636bee) | git log, subject `integrate(G-09): ...` |
| G-10 | Lát cắt triển khai bổ sung (Slice) | `cadafb45237be7442988df322083e02b491994c3` (lane lane-g-10 candidate 4f4d12b598f6) | git log, subject `integrate(G-10): ...` |
| G-11 | Lát cắt triển khai bổ sung (Slice) | `7cdcbf1ee151fe8da9747c90f2079ed757c67224` (lane lane-g-11 candidate 636f93d0e94e) | git log, subject `integrate(G-11): ...` |
| G-12 | Lát cắt triển khai bổ sung (Slice) | `02f465880049c649f3b329c404201eb6a932bed4` (lane lane-g-12 candidate b15172eb5bf8) | git log, subject `integrate(G-12): ...` |
| G-13 | Lát cắt triển khai bổ sung (Slice) | `5c8e6691fb622d08054ca24cca359cf4f5f302b5` (lane lane-g-13 candidate 18b6837ce120) | git log, subject `integrate(G-13): ...` |
| G-14 | Lát cắt triển khai bổ sung (Slice) | `41b999dd3ba9a7e7cb6f4ca02aebf167fb909e07` (lane lane-g-14 candidate 98dd973ecb7a) | git log, subject `integrate(G-14): ...` |
| H-01 | Lát cắt triển khai bổ sung (Slice) | `b7c69dcf0c57f820a9059ccfed9f33f3b4753b17` (lane lane-h-01 candidate f445e697fa4d) | git log, subject `integrate(H-01): ...` |
| H-02 | Lát cắt triển khai bổ sung (Slice) | `1d436dc88acfa2beca208b3b77bc9010b2933c35` (lane lane-h-02 candidate 273da2ae7bba) | git log, subject `integrate(H-02): ...` |
| H-03 | Lát cắt triển khai bổ sung (Slice) | `d6f0c277e1d921c36e0ba0553aca131ca6d991da` (lane lane-h-03 candidate f8bfc13cc9bd) | git log, subject `integrate(H-03): ...` |
| H-04 | Lát cắt triển khai bổ sung (Slice) | `647670c4d7373520028d1382a8664a1108d31572` (lane lane-h-04 candidate 53c100019145) | git log, subject `integrate(H-04): ...` |
| H-05 | Lát cắt triển khai bổ sung (Slice) | `ddeec203cadc4982286cbfa02a4882905967b7d1` (lane lane-h-05 candidate 32eb1d7a392b) | git log, subject `integrate(H-05): ...` |
| H-06 | Lát cắt triển khai bổ sung (Slice) | `672c0258ec0333ecd3405546d57471d2ece3f1cb` (lane lane-h-06 candidate d3592813a48e) | git log, subject `integrate(H-06): ...` |
| H-07 | Lát cắt triển khai bổ sung (Slice) | `210ac3386e5e5fc4c6623e26e5e127eea34a8ab5` (lane lane-h-07 candidate 63abf78c4f20) | git log, subject `integrate(H-07): ...` |
| H-08 | Lát cắt triển khai bổ sung (Slice) | `2cc70e022c4eccc40145171ed093e2d0b6cce552` (lane lane-h-08 candidate b32fdc813e42) | git log, subject `integrate(H-08): ...` |
| H-09 | Lát cắt triển khai bổ sung (Slice) | `3f728636bf16a824120ce1327ffd8ce3326dfebd` (lane lane-h-09 candidate acedae410a42) | git log, subject `integrate(H-09): ...` |
| H-10 | Lát cắt triển khai bổ sung (Slice) | `1602d70f0336bccf043242bb76a0bb1d57afd13a` (lane lane-h-10 candidate 533664638547) | git log, subject `integrate(H-10): ...` |
| H-11 | Lát cắt triển khai bổ sung (Slice) | `2ea81fba2ac95d4eb25b5a4d2d2e9ae53fe5c8ca` (lane lane-h-11 candidate 3a48685a2315) | git log, subject `integrate(H-11): ...` |
| H-12 | Lát cắt triển khai bổ sung (Slice) | `2709dde552c0df0b0c3dce847b69fc139fb34566` (lane lane-h-12 candidate fabf5aa94149) | git log, subject `integrate(H-12): ...` |
| H-13 | Lát cắt triển khai bổ sung (Slice) | `3699ef42c7c3f4dc5540c478fce3d86ef3a633fb` (lane lane-h-13 candidate 974c60d09e3e) | git log, subject `integrate(H-13): ...` |
| H-14 | Lát cắt triển khai bổ sung (Slice) | `41827002e91f295b2a5adc13b9c5db8a400eeb7f` (lane lane-h-14 candidate 28707964e39c) | git log, subject `integrate(H-14): ...` |
| H-15 | Lát cắt triển khai bổ sung (Slice) | `98381456e99a63c520138e800648a748114765ec` (lane lane-h-15 candidate 3d65eeb307f4) | git log, subject `integrate(H-15): ...` |
| H-16 | Lát cắt triển khai bổ sung (Slice) | `0b266d010c1be17c8b25c486df77e68e1ea43e58` (lane lane-h-16 candidate 322d45b2c8e5) | git log, subject `integrate(H-16): ...` |
| I-01 | Lát cắt triển khai bổ sung (Slice) | `8a56becbaf7a1814b73fc5d2886b390f6c17c45b` (lane lane-i-01 candidate 0fffa7dbb1fb) | git log, subject `integrate(I-01): ...` |
| I-02 | Lát cắt triển khai bổ sung (Slice) | `5631a65a20571299f43c3803f8593a95ad1419dc` (lane lane-i-02 candidate 2334c0123df7) | git log, subject `integrate(I-02): ...` |
| I-03 | Lát cắt triển khai bổ sung (Slice) | `dbd2b6e5b4a9271844e7e55673192bbc15f3c570` (lane lane-i-03 candidate f59915458e5f) | git log, subject `integrate(I-03): ...` |
| I-04 | Lát cắt triển khai bổ sung (Slice) | `12409080b2b686d8e7442db0c4e2ecc6f219374c` (lane lane-i-04 candidate 6f004e0c28e9) | git log, subject `integrate(I-04): ...` |
| I-05 | Lát cắt triển khai bổ sung (Slice) | `68e2ae94f4aafb49345a02583208516271e7e05e` (lane lane-i-05 candidate d2caf207b8b3) | git log, subject `integrate(I-05): ...` |
| I-06 | Lát cắt triển khai bổ sung (Slice) | `4b9625489ef4df525380403be10dcaf4d73c3991` (lane lane-i-06 candidate ee3ce09a3f66) | git log, subject `integrate(I-06): ...` |
| I-07 | Lát cắt triển khai bổ sung (Slice) | `ff4a1202fca00227eba3a295b3500efaba4a40cf` (lane lane-i-07 candidate 6325d36c549e) | git log, subject `integrate(I-07): ...` |
| I-08 | Lát cắt triển khai bổ sung (Slice) | `6cc347b6b1c32c887c6393932f4ffe9b0b4d0c80` (lane lane-i-08 candidate 627afb7c01ce) | git log, subject `integrate(I-08): ...` |
| I-09 | Lát cắt triển khai bổ sung (Slice) | `d3b0cff0a6c39bb4cce7451ff61435358b50a768` (lane lane-i-09 candidate 79555e9485ff) | git log, subject `integrate(I-09): ...` |
| I-10 | Lát cắt triển khai bổ sung (Slice) | `5d8c1aa2846ed5b9b4c59a742e3792621846dc46` (lane lane-i-10 candidate a7838524da96) | git log, subject `integrate(I-10): ...` |
| I-11 | Lát cắt triển khai bổ sung (Slice) | `6437cb96a4bad8941038406360ac3cab6f307385` (lane lane-i-11 candidate 68b8a94c7dfd) | git log, subject `integrate(I-11): ...` |
| I-12 | Lát cắt triển khai bổ sung (Slice) | `49a6b2cd63f58127a65fa105b13ced917a842f2d` (lane lane-i-12 candidate d82f0b4a1ed9) | git log, subject `integrate(I-12): ...` |
| I-13 | Lát cắt triển khai bổ sung (Slice) | `9ca4d9f66ecd72e66686da4310be5c0998728e0b` (lane lane-i-13 candidate 9892cd5c5c34) | git log, subject `integrate(I-13): ...` |
| J-01 | Lát cắt triển khai bổ sung (Slice) | `2f4646097605e31871a73832e6fd0a7cbda289d3` (lane lane-j-01 candidate 0c3e5a6b7f50) | git log, subject `integrate(J-01): ...` |
| J-02 | Lát cắt triển khai bổ sung (Slice) | `f563c0ddafa79257ae4afa5171f54e7fc11cbb5a` (lane lane-j-02 candidate 0253af79e33f) | git log, subject `integrate(J-02): ...` |
| J-03 | Lát cắt triển khai bổ sung (Slice) | `b83d371b45f27f784aeeaa35fd36979636c75423` (lane lane-j-03 candidate db494344eb2d) | git log, subject `integrate(J-03): ...` |
| J-04 | Lát cắt triển khai bổ sung (Slice) | `0642bc1cb8b778f1868bdfc818fd4dadad20c132` (lane lane-j-04 candidate eef855ef73c8) | git log, subject `integrate(J-04): ...` |
| J-05 | Lát cắt triển khai bổ sung (Slice) | `f5bef3db069c137b89b0f8313425d220808d57e2` (lane lane-j-05 candidate 3e921177f77b) | git log, subject `integrate(J-05): ...` |
| J-06 | Lát cắt triển khai bổ sung (Slice) | `7467ff26031adb5063e0d851be7f2de3cf4f2105` (lane lane-j-06 candidate 99c4eba32238) | git log, subject `integrate(J-06): ...` |
| J-07 | Lát cắt triển khai bổ sung (Slice) | `c5e236f22f8879070c66bdf088230f05d95ef78a` (lane lane-j-07 candidate 79f95f88e037) | git log, subject `integrate(J-07): ...` |
| J-08 | Lát cắt triển khai bổ sung (Slice) | `484661bdbbb463a98e7e8ab3609a9555e3c52892` (lane lane-j-08 candidate d15a6b169ce9) | git log, subject `integrate(J-08): ...` |
| J-09 | Lát cắt triển khai bổ sung (Slice) | `c4bceab00a2ebdf1a2cdd6ee474f9b28e407127a` (lane lane-j-09 candidate a92b2937e174) | git log, subject `integrate(J-09): ...` |
| J-10 | Lát cắt triển khai bổ sung (Slice) | `750929c603db3ca6c05ddc8dc127d08187e293b5` (lane lane-j-10 candidate 194f44f8725f) | git log, subject `integrate(J-10): ...` |
| J-11 | Lát cắt triển khai bổ sung (Slice) | `379c232fd55c67c60dfd23333cdd0e2589cc5d96` (lane lane-j-11 candidate da2091cf56ba) | git log, subject `integrate(J-11): ...` |
| J-12 | Lát cắt triển khai bổ sung (Slice) | `12c2567e4e67f06ce082696375d9350b6da90092` (lane lane-j-12 candidate 6d19c7a4707f) | git log, subject `integrate(J-12): ...` |
| J-13 | Lát cắt triển khai bổ sung (Slice) | `f3ddb66ffe3256224644f56088ad3f73127c37cc` (lane lane-j-13 candidate 67c90cff1f87) | git log, subject `integrate(J-13): ...` |
| J-14 | Lát cắt triển khai bổ sung (Slice) | `798b970838a55784962f38a0225d9ec3f047cbe0` (lane lane-j-14 candidate d942868c5335) | git log, subject `integrate(J-14): ...` |
| J-15 | Lát cắt triển khai bổ sung (Slice) | `b2222eabe26135c7af4e817c2cd1d75dc83a5d3e` (lane lane-j-15 candidate 00371a965e8d) | git log, subject `integrate(J-15): ...` |
| J-16 | Lát cắt triển khai bổ sung (Slice) | `f642bdc06bf70b00871bc62560b8d5b5a2845144` (lane lane-j-16 candidate 157504393ebe) | git log, subject `integrate(J-16): ...` |
| J-17 | Lát cắt triển khai bổ sung (Slice) | `ce8faa1475918573fc1fd5e51c5d38046e9a1115` (lane lane-j-17 candidate f79fdcd14663) | git log, subject `integrate(J-17): ...` |
| J-18 | Lát cắt triển khai bổ sung (Slice) | `01da3b296de9dc5ac3313df6780f1d09fb7e1e0e` (lane lane-j-18 candidate 4457cebd540b) | git log, subject `integrate(J-18): ...` |
| CP0-GOVERNANCE | Gói kiến trúc nền tảng (Foundation) | `e79ae82c349bd4492323d22a0070f77bbbe82337` (lane lane-cp0-governance candidate 0948472b68dd) | git log, subject `integrate(CP0-GOVERNANCE): ...` |
| CP1-CONTRACT-BINDING | Gói kiến trúc nền tảng (Foundation) | `f40822e0ea258ed799fffa781c2c7b06776dd21a` (lane lane-cp1-contract-binding candidate 9a4b4b5c6854) | git log, subject `integrate(CP1-CONTRACT-BINDING): ...` |
| CP2A-LAYOUT | Gói kiến trúc nền tảng (Foundation) | `35ea5029b40cc4a5edcc3054499676cd6dc591e2` (lane lane-cp2a-layout candidate 1d5c2a699fa3) | git log, subject `integrate(CP2A-LAYOUT): ...` |

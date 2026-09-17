# NVIDIA 确定性判分（repair002）

本目录沿用 @DEM1TASSE 的20个入口名，由 reviewer 修复判分实现；站点原贡献归属 @KaKituken。判分仅使用 Python 标准库（PNG 结构校验用 `zlib`/`binascii` 自行实现），不 import Flask/app，不调用模型、网络或额外进程；唯一可选的子进程调用是 `docker cp` 取DB（与仓库其他站点 verifier 相同的 fallback）。

## 调用与输出

```bash
# 1) 仓库文档路径：agent_demo/eval_judge.py --verifier True 只传 --run_dir
WH_CONTAINER=wh-review python3 -B sites/nvidia/verify/verify_0.py --run_dir /absolute/run

# 2) 显式输入（native-ready backend.verify() 的四输入复制）
python3 -B sites/nvidia/verify/verify_0.py \
  --run_dir /absolute/phase-input \
  --initial_db /absolute/phase-input/initial.db \
  --after_db /absolute/phase-input/after.db
```

CLI 与仓库其他站点 verifier 完全一致：`--run_dir` 必填；`--initial_db`/`--after_db` 可选，缺省时按 `--container`（默认 `$WH_CONTAINER` 或 `wh-review`）从运行中的容器 `docker cp` `instance_seed/nvidia.db` 与 `instance/nvidia.db`；`--no_llm` 为兼容参数（判分始终确定性）。`docker cp` 失败是结构化 INFRA，不抛 traceback。

- `run_dir` 必须包含 `trajectory.json`；`task.json` 可选（生产 recorder 不写）。`task.json` 存在时逐字段等于本源码同站点 `tasks.jsonl` 中的本题定义，否则为 INFRA——不能偷偷接受旧题/旧rubric。
- trajectory 同时接受两种键集：(a) 显式/native-ready——`task_id`、`query`、`steps`、`final_answer`，每步连续整数 `step` 及 `url`/`url_before`/`url_after`，可选 `final_url`、`boundary_events`；(b) 生产 recorder（`agent_demo/agent.py`）——`task`（而非 `query`）、`start_url`，每步 `step`/`url`，无 `task.json`、无 `final_url`。两个键同时出现时必须都等于 canonical ques，否则 INFRA。
- `final_url` 缺省时按“运行停下的最后一页”回退：取最后一步的 `url_after`，无则取该步 `url`。T11 仍要求该终页为本地 RTX 5080 购买页。
- 无动作 baseline 为 `steps=[]`、空答案。
- URL 按实际 origin 和精确 path/query 解析；端口在单次运行内必须一致，但允许运行之间映射变化，不强制任务文件的 40028。相关对象证据来自真正对应的详情、含目标slug的comparison、含目标行的driver结果或news列表；`?q=/products/...` 不是详情页证据。
- 单站 backend 仅支持 local loopback origin；`localhost`/`127.0.0.1`/`[::1]` 在同一端口下视为同一 loopback 主机（repair002, M9，因为 harness 的 host 拼写与端口映射都是运行细节）；同一次运行内端口必须一致，跨 origin、非 loopback 主机或 boundary 事件仍然 FAIL。输入缺失/不可读/非法JSON（含重复键）、ID/query/task 不符、schema/integrity/FK 错误为 INFRA。
- 截图证据绑定（repair002, H3）：`run_dir` 下必须存在可解码的 PNG 截图，最小 320×200、最大 8 MiB。轨迹若命名了截图文件（`screenshot_before`/`screenshot_after`/`screenshot`/`screenshot_path`，生产 recorder 与 native-ready 都会写），每个命名文件都必须存在；否则按目录扫描并要求数量 ≥ min(步骤数, 2)。校验用标准库解析 PNG 签名/每个 chunk 的 CRC/IHDR/IDAT 的 zlib 解压与扫描行长度，因此 1×1、截断、改名的非 PNG 文件都会 FAIL（INFRA）。
- SQLite 强制 `mode=ro` 和 `query_only`，要求原应用完整10表/列与一致 before/after schema。不会创建缺失DB，不会 fallback 到其他容器/题目。

stdout 始终是一份 JSON：`task_id` 为本题、`pass` 为严格 bool、`reason` 为说明、`evidence` 为检查摘要。

|exit|语义|
|---|---|
|0|正常PASS，`pass=true`|
|1|正常任务FAIL，`pass=false`|
|2|INFRA_ERROR，`pass=false,error="INFRA_ERROR"`；外层应`success=false`，不能算正常负例|

比较页同时支持最终UI的原生GET `product=a&product=b`与旧`ids=a,b`；按app实际优先级前者覆盖后者，不能合并两组参数虚构已显示的产品。

## 判定原则

- 信息题：事实取显式initial DB（T11静态技术/购买事实见来源），必需相关页/对象证据。信息匹配使用型号实体、数值和单位、比较主语方向、版本分量与完整日期；不是substring。支持大小写/空白/千分位、GB/GDDR 7、USD/美元、W/watts等合理格式，以及清晰的日期格式。
- 确定性解析支持简洁事实句和明确关系，不保证理解任意修辞/暗示。遇歧义或矛盾返回FAIL，保持原输出并交独立主审；不调用LLM兜底，也不让LLM缺配置变成任务FAIL。
- 否定作用域（repair002, H2）：“not a live release feed / frozen historical catalog”这类文档作用域保留语只对 **T9/T10** 豁免（由 `predicates.driver_qualifier_scope` 在完整保留原文的前提下仅去掉该短语内的否定词）；其余 18 题只豁免与目标无关的对比（其它型号、无关指标、变体名、PSU 说明），出现针对性的否定/不确定词即 FAIL（fail-closed）。该边界由自带回归 `tests/test_driver_qualifier.py::test_other_information_task_not_relaxed` 钉住。
- T6题意指定comparison工具，必须同一比较包含5090/4090；T7未指定工具，可分别读两详情。T18相关news/search列表显示日期时可接受，不强制详情（search证据必须含一个真正出现在文章正文/标题里的词token，纯数字查询不再算作证据）。T11必须技术页与5080购买页两类证据，最终停本地购买页，无固定浏览顺序。
- 状态题：DB是完成结果的权威依据，不附加英文最终回答或登录页面访问要求。按新增/删除row ID绑定同一账号和目标，保护所有其他wishlist/users/reviews/orders等记录。仅模拟driver download计数非递减作为无害副作用允许；不把账号/收藏误操作或额外订单当无害。
- Wishlist新增要求目标原先不存在、只新增一条；T16仅删Alice目标且保留所有其他条目。T14仅改Alice country，保留其他字段。T15同一新增row满足Alice/Jetson/5星/精确归一化标题/非空body；`Not Incredible`失败。T19仅新增指定邮箱subscription，且该row的`topic`必须是本店的GeForce列表值。
- Wishlist写入端点（repair002, M8）：站点模板使用 `/wishlist/add/<id>` 与 `/wishlist/remove/<id>`，二者幂等（重复提交不改变状态）；旧的 `/wishlist/toggle/<id>` 仅为兼容保留。判分仍要求“恰好新增一条”，不因端点幂等而放宽。
- T16历史校正：原版真实登录→account→详情移除路线本来会被原verifier接受；本修复不以简化URL fixture夸大原实际UI失败，改为直接按准确state判定。

## 任务变更与事实来源

20个源ID保留。仅T5/T11/T12/T17修改query语义，其余16题原query保留；全20题URL更新40028、rubric更新为英文FACT CHECKPOINTS。rubric只供grader，actor只接收ques，不得暴露此目录或rubric。

- T5：Orin Nano Super **8GB developer kit** 对比 Orin NX **16GB production module**；两个对象的内存与身份必须关联正确。保留正常商品价签，不靠删除可见价格制造难度。
- T11：Blackwell、第五代Tensor、第四代RT；RTX5080 **NVIDIA Marketplace / United States（en-us）**购买信息，停在本地，无外部访问/下单。
- T12：原40系列最低价卡转为Alice本地Wishlist。
- T17：镜像冻结价格、Gaming≥16GB最低价、具体RTX5060Ti **16GB版本**转为Alice本地Wishlist；不是实时零售价结论。

T11来源：官方`https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/`，2026-09-09离线采集。原HTML SHA256 `977dc25fd5586343e1e939bb67cae371a58b1d1df0e5d45c552eb7d55709c2fe`。可见文本含“NVIDIA Blackwell Architecture / Fifth-Gen Tensor Cores / Fourth-Gen Ray Tracing Cores”；该页5080“See All Buying Options”href为`https://marketplace.nvidia.com/en-us/consumer/graphics-cards/?...gpu=RTX%205080...`。来源只支撑入口与地区，不证明库存/价格/checkout。私有采集receipt、原始HTML及参考hash保存在review报告区，不随站点源码交付。

## 已知偏差：rubric 含答案 token（repair002, M7）

`tasks.jsonl` 中 20 题里有 18 题的 `judge_rubric` 直接写出了判分数值（例如 `32 GB GDDR7`、`10,752`、`566.36`、`June 16, 2026`），而 `CONTRIBUTING.md` 的 Reviewer 约定要求 rubric 只写规则、不写答案。已合并站点（如 `sites/osu`、`sites/ted`）存在同样写法，因此这是仓库既有惯例与文档的冲突，不是本 PR 独有的定义偏差。

处理方式：保留 rubric 的答案检查点，不把它改写成模糊表述——rubric 是 LLM judge（次级评分器）的检查清单，去掉数值会直接降低次级评分强度；确定性 verifier 始终是主评分器，其真值固化在 `sites/nvidia/verify/` 内、不依赖 rubric。另需注意：本仓库的 harness（`agent_demo/agent.py`）只把 `ques` 交给被测模型，`judge_rubric` 仅进入 `trajectory.json` 供 judge 使用，因此当前路径下不构成运行期泄露。

解除条件：要么在仓库层面统一决定 rubric 是否允许携带数值（并同步修正 CONTRIBUTING.md），要么改为“rubric 只描述必须出现的字段/关系、数值由 verifier 提供”并在评测端把 verifier 事实注入 judge 上下文，以免削弱次级评分。

## 机械回归

使用正式素材或指定完整schema seed的**独立副本**，不import站点，输出必须是候选源树之外的新目录：

```bash
python3 -B sites/nvidia/tests/test_verifiers.py \
  --seed /absolute/nvidia/instance_seed/nvidia.db \
  --out /absolute/new-review-evidence-directory
```

覆盖每题no-op/正确fixture/专属near-miss，以及错账号/目标/delta、副作用、合法替代导航、格式正例和schema/身份INFRA。逐例保存输入DB/task/trajectory/hash、SQL变更、命令、stdout/stderr/exit与输入不变校验。fixture为机械证据，不是UI或native成绩；真实candidate seed、UI/native与独立主审仍需另行验收。

CLI/输入契约另有回归套件，钉住 `agent_demo/eval_judge.py --verifier True` 所需的调用形式（仅 `--run_dir` + 容器 fallback）、生产 recorder 的 trajectory 键集、`--no_llm` 兼容、以及畸形输入的结构化 INFRA：

```bash
WH_CONTAINER=<running nvidia container> TEST_OUT=/absolute/outside/source/tree \
  python3 -B -m unittest discover -s sites/nvidia/tests -p 'test_verifier_contract.py'
```

## 扩展修复轮（#107 后续）的判分契约变更

上一轮 20 题逐任务审查（`_wh_review_tools/pr107-audit/agent-{a,b,c}/summary.md`）发现的判分问题在本轮全部修掉；每条都改成“rubric 已经要求的语义”，没有改 `tasks.jsonl`。

| 题 | 变更 | 依据 | 回归 |
|---|---|---|---|
| T6 | `answers.cuda_compare()` 重写为“比较主张 + 计数归属”解析：接受 rubric 自己的句式（`… 5,376 more CUDA cores than … (21,760 versus 16,384)`）、counts-first（`21,760 CUDA cores against 16,384 for the 4090, which is 5,376 more`）与句尾 delta（`while the 4090 has 16,384; that is 5,376 more`）；反向主语、错误指标、错误 delta、相等声明、绝对计数互换仍然 FAIL | audit agent-a `blocker`（21 条自然正确表述里 9 条被误判） | `tests/test_verifiers.py`（`rubric-wording`、`trailing-delta`、`swapped-absolute-counts` + `NEAR[6]`），`agent-a/verifier-probe/probe-T6-*`、`t6-pass`、`t6-inverse` |
| T1 | `answers.measurements()` 同时识别“单位在前”的规格行写法（`CUDA Cores: 10,752`），允许单位集合与数值校验不变（`Tensor Cores: 10,752`、`CUDA Cores: 11,752` 仍 FAIL） | audit agent-a `medium` | `NEAR[1]`、`spec-row-echo`，`agent-a/verifier-probe/probe-T1-row_echo` |
| T3 | 答案必须同时给出型号与价格（裸 `$299` FAIL） | audit agent-a `low` | `bare-price-only`、`model-and-price`，`agent-a/verifier-probe/t3-bare_price_only` |
| T5 | 证据必须覆盖**两个**产品（含两者的 comparison，或两页详情）；单商品页/购买页不再足够 | rubric 原文 “FAIL for … one-product-only evidence” | `one-jetson-page-insufficient`、`other-jetson-page-only-insufficient`、`both-jetson-details`，`agent-a/verifier-probe/T5-*` |
| T9/T10 | `predicates.driver_evidence()` 要求结果页把**目标系列**钉住（branch/OS 可留空，系列不可）；目标驱动详情页仍单独充分 | audit agent-b `low`（branch+os-only 曾 PASS） | `series-only-broad`、`no-series-filter`、`branch-os-only-insufficient`，`agent-b/verifier-probe/run-t9|t10_*` |
| T18 | 保留 rubric 允许的“列表或搜索结果”证据，但 search 证据必须含一个真正出现在文章里的词 token（纯数字查询 FAIL） | audit agent-c `low` + rubric 原文 | `news-search`、`news-search-numeric-only` |
| T19 | 新增订阅行除 email 外还必须满足 `topic` 为本店 GeForce 列表值 | audit agent-c `low`（`topic=NotTheGeForceTopic` 曾 PASS） | `wrong-topic`、`geforce-topic` |

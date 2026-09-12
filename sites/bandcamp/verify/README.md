# Bandcamp Task Verifiers

18 个 wrapper 对应 `Bandcamp--0..17`，只消费本题冻结快照，不连接 Docker 或在线模型。

```bash
python3 -B -m unittest discover -s sites/bandcamp/verify -p 'test_*.py' -v
python3 -B sites/bandcamp/verify/verify_0.py --run_dir runs/bandcamp-0
```

`run_dir` 必须包含 `trajectory.json`，其中 `task_id`、`start_url`、`steps[].url` 和字符串 `final_answer` 必须有效。
自动发现 `initial.db`（否则 `before.db`）及 `after.db`；也支持显式 `--initial_db` / `--before_db` 和 `--after_db`。
若有 `task.json`，其 `id` 必须匹配 wrapper。旧消费者的 `--container` / `--no_llm` 参数仅接受解析，不触发 live-state fallback。

- Exit 0：有效 PASS。
- Exit 1：有效普通 FAIL，包括 no-op、错误结果、缺少站内页面、非请求的最终业务变更。
- Exit 2：缺快照、解析/身份/schema/完整性错误，不能算合格负例。

信息题要求正确肯定事实、相关同源页面和全表不变。简短回答由任务与页面确定主体；显式错误比较、同名 album/track 歧义、已覆盖的否定和多余集合值会被拒绝。
这些是确定性语言规则，不是任意自然语言的完整语义证明，真实 actor 答案仍须独立主审。不要为了迎合某一条生成文本放宽谓词。

状态题要求非空 final，但不要求英文关键词、固定 login/final URL 或结账后的订单号复述。
所有原有行与字段保留；允许的变化仅为目标 wishlist/cart 新行、指定 profile 字段，或完整 cart 转单及同步 checkout 的预期副作用。

`test_seed.sql` 从已审计的合成 seed 导出完整真实 schema/数据，正例由独立 SQL 和手写回答建立，不从 verifier PASS 常量生成。fixture、HTTP 诊断和 no-op 都不是纯视觉 E2E 成绩。
根共享 `agent_demo/eval_judge.py` 的 `success/pass` 缺陷不在本目录修复；调用方必须把 exit 0/1 作为健康判分、exit 2 作为基础设施错误。

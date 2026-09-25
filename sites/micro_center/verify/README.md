# Micro Center — reviewer grading contract

Authored by the reviewer (review-env skill, reviewer track) on top of the
contributor's 18 task rows. The contributor ships ONLY the five task-definition
keys per row (`web_name, id, ques, web, upstream_url`); this directory adds the
grading contract and nothing else.

## Layout

- `verify_lib.py` — deterministic verifier utilities: frozen seed contract
  (schema sha `6540fdcf…`, 14-table counts, rows sha `8327edf0…` over the
  pinned asset-archive seed), trajectory identity gates (task_id,
  `agent_done`, non-empty answer, same-origin loopback URLs, decodable PNG
  screenshots), navigation gates, answer matching (phrase / token / amount /
  count), SQLite after-state gates. `search_log` is append-only search
  instrumentation and is excluded from the read-only / collateral gates.
- `verify_0.py … verify_17.py` — one deterministic verifier per task. Ground
  truth is HARDCODED inside each verifier (never in `tasks.jsonl`); no LLM call
  is load-bearing. Each emits `{task_id, pass, reason, evidence[]}` and exits
  0/1.
- `append_rubrics.py` — records `verifier_path` + `judge_rubric` in
  `../tasks.jsonl` by pure string insertion before the closing brace: the five
  contributor keys stay byte-identical, no `answer` key is ever written.
  `--check` re-validates the contract.
- `tests/test_verifiers.py` + `tests/_support.py` — 173 deterministic contract
  tests: honest PASS (18), no-op FAIL (18), wrong-answer FAIL (18), shortcut
  FAIL (18), state-mismatch FAIL (10), wrong-delta FAIL (10), read-only
  mutation FAIL (8), package tamper FAIL (72: task_id / off-site URL / missing
  screenshot / non-done trajectory), plus the tasks.jsonl contract test.
  Run: `python3 -m pytest sites/micro_center/verify/tests -q`
  (the seed DB resolves from the review container `wh-mc-review`; override
  with `MC_TEST_SEED_DB=<path>`).

## Verifier input signature

```
python3 sites/micro_center/verify/verify_N.py \
    --run_dir <agent run dir: trajectory.json + screenshots/> \
    [--initial_db <seed snapshot>] [--after_db <after snapshot>] \
    [--container wh-mc-review] [--no_llm True]
```

The agent harness (agent_demo/agent.py) writes the trajectory; grading runs
through agent_demo/eval_judge.py `--verifier True`, which looks up
`verifier_path` from the trajectory.

## Notes

- Tasks 0 and 3: the seeded demo carts (alice: 3 items, bob: 2 items) join the
  checkout, so order totals are verified for internal consistency
  (subtotal = Σ items, tax = 7.25%, total = subtotal + tax + shipping) plus
  the pinned constraints, not by recomputing a laptop-only total.
- Task 0: the round-1 mirror limitation (checkout ignored the saved
  `card_id`) was fixed in the contribute branch — checkout now honors the
  saved card and the order records it. The verifier still grades the order
  number and total (the saved-card clause is satisfiable but not a hard
  gate).
- Task 10: the task (after the round-1 redesign) names BOTH order items with
  distinct ratings/titles; the DB gate pins the two posted reviews and each
  product's new review count. The app recalculates product ratings from the
  reviews table with the pending insert flushed into the query (the new row
  is double-counted); the live-observed 4.6 / 4.4 values are pinned exactly.
- Tasks 1, 2, 6, 9, 12, 15, 16, 17: guest carts, guest store selection and
  guest compare lists live in the server-side session (not SQLite), so those
  tasks are graded on navigation gates + pinned product pages + answer
  facts, with a strict read-only DB gate.
- Task 17: the Bambu Lab A1 printer is out of stock at the Cambridge store
  in the seed; the audit round reworded the task's stock clause to "with
  the spools in stock there" so the sentence matches the data (the graded
  facts — plate temperature, subtotal, colors — never depended on the
  printer's stock).

# Dillards verifier contract

One deterministic verifier per task (`verify_0.py` … `verify_30.py`, thin
wrappers around `grade.py`), shared helpers in `verify_lib.py`, and hardcoded
ground truth in `answers.py`. `test_verifiers.py` is the offline contract
test (honest PASS / no-op FAIL / fabricated FAIL / near-miss FAIL / shortcut
FAIL / tamper FAIL); it needs no browser and no docker, only the frozen seed
`instance_seed/dillards.db`.

## Verifier input signature

```
python3 sites/dillards/verify/verify_<n>.py --run_dir <dir> [--container wh-rev-dillards]
```

`<dir>` is an agent run package: `trajectory.json` (agent_demo schema),
`screenshots/step_NNN.png`, and optional `initial.db` / `after.db` SQLite
snapshots. When the snapshots are absent the verifier copies them out of the
container (`--container`, default `wh-rev-dillards`):
`/opt/WebSyn/dillards/instance_seed/dillards.db` (initial) and
`/opt/WebSyn/dillards/instance/dillards.db` (after).

## Checks (fail-closed, no LLM)

1. Harness gates (`Judge.bind_run`): terminated run, `agent_done` final step,
   non-empty answer, every URL on a local origin, real decodable PNG frames
   bound to the target page, ≥3 distinct frames.
2. Navigation evidence: the trajectory must have opened the page(s) the task
   depends on (PLP + sort/facet URL, PDP, account page, registry page, store
   page, search results …) — a correct answer without that navigation is a
   knowledge-shortcut FAIL.
3. Answer checks against `answers.py` ground truth: names, money, counts,
   phone, codes, dates; negation-aware token matching.
4. DB after-state: read-only tasks must leave every table unchanged;
   stateful tasks (15, 18, 19, 20, 21, 24, 28, 29, 30) must produce exactly
   the expected rows/field changes and preserve everything else.

## Grading notes for the task texts

- Task 3 asks for the price of each COCO MADEMOISELLE size. The PDP renders
  the price range ($154.00 - $270.00); the middle size's exact price is read
  from bag lines after adding the sizes (bagging requires a logged-in demo
  account; the added rows are removed afterwards to keep the DB clean). The
  verifier requires all three size prices.
- Task 13's "the matching Levi's jeans" matches two Levi's 511 products in
  the "511 slim" search results. The verifier accepts either product as long
  as the reported name, price and size count are internally consistent.
- Task 18 says "from your recent order": the Lancome Lash Idole mascara is in
  Carol's In-Transit order D2609180298 (the UI allows returns from it; her
  delivered order contains different items). The verifier anchors on the
  mascara item + reason + method + credit amount.

## Output

JSON on stdout: `{"task_id": …, "pass": bool, "reason": …, "evidence": […]}`;
exit 0 on PASS, 1 on FAIL.

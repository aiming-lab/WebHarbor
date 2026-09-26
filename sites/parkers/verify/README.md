# Parkers verifier contract

Deterministic grading contract for the 20 Parkers benchmark tasks
(`Parkers--0` … `Parkers--19`), following the hardened reviewer suites
(`sites/porsche/verify`, `sites/mta/verify`, `sites/megabus/verify`).

## Layout

- `verify_lib.py` — shared machinery: trajectory identity, navigation gates,
  answer matching, frozen-seed contract, read-only / exact-delta DB checks.
- `verify_0.py` … `verify_19.py` — one verifier per task; ground truth is
  HARDCODED here and never appears in `tasks.jsonl`.
- `tests/test_verifiers.py` + `tests/_support.py` — adversarial contract
  tests (honest fixtures pass; no-op / shortcut / wrong-answer / mutated-DB /
  state-mismatch / tamper runs all fail).
- `append_rubrics.py` — appends `verifier_path` + `judge_rubric` to
  `../tasks.jsonl`, keeping the five task-definition keys byte-identical and
  adding no answer key.

## Verifier signature

```
python3 verify_N.py --run_dir DIR [--initial_db P] [--after_db P] [--container NAME]
```

`--run_dir` holds `trajectory.json` (task_id, start_url, steps with url /
action / params, final_url, final_answer, terminated, termination_reason)
plus `screenshots/step_NNN.png`. DBs default to `<run_dir>/initial.db` and
`<run_dir>/after.db`, falling back to `docker cp` from the container
(`wh-parkers-review` by default, override with `--container` or
`$WH_CONTAINER`).

Output: one JSON verdict `{task_id, pass, reason, evidence[]}`; exit 0 on
PASS, 1 on FAIL (fail-closed on any infra error).

## Four check layers

1. **Package identity** — task_id match, `terminated` with
   `agent_done`, non-empty final answer, every URL on the same loopback
   origin/port as `start_url`, every screenshot a decodable PNG.
2. **Navigation gates (anti knowledge-shortcut)** — the trajectory must have
   opened the surfaces the task names: the free-valuation chain (generation
   used-prices page carrying the task's year plate and selected version,
   select-a-valuation, free-valuation for the exact derivative), the
   registration lookup, derivative spec pages, insurance-group pages, review
   overviews and named sections, the cars-for-sale search with the task's
   filter combination, listing detail pages, owner-review pages, the news
   article, the best-cars guide, the car-tax page, and the My Parkers
   surfaces (sign-in, shortlist). A correct answer without the navigation is
   a memory-recall shortcut = FAIL.
3. **Answer gates** — amounts (with/without £ and thousands separators),
   counts, and phrases matched against frozen ground truth hardcoded in each
   `verify_N.py`. Variant-dependent answers (e.g. T7 luggage space, which
   differs by trim) accept every ground-truth-consistent form and require the
   quoted figures to be self-consistent.
4. **DB after-state** — initial vs after SQLite snapshots. Read-only tasks
   require a row-identical database; the stateful tasks (T8 shortlist save,
   T9 shortlist edit, T11 owner-review submission) require the exact allowed
   row delta and nothing else.

## Frozen seed contract

`SCHEMA_SHA256` / `SEED_ROWS_SHA256` / per-table counts freeze
`instance_seed/parkers.db` (sha256 `b6edecc8…`, 18 tables, 10,517 valuations,
1,161 listings). Any run whose initial DB is not the frozen seed fails.
Re-frozen by the r2 re-review after the A-1..A-4 fix rebuilt the seed
(derivatives 1062→1079, generations 202→205, review_sections 946→943,
rivals 0→8, valuations 10,209→10,517).

## r2 re-review contract sync

All four r1 blockers are fixed on `orch/contribute/parkers` @ `36b52a48` and
the contract has been re-synced to the deepened / re-anchored tasks:

- T10: owner-review bodies are now rendered, so the "one specific problem an
  owner mentions" sub-question is enforced again, alongside the new
  reliability / practicality / luggage / cheapest-listing sub-questions.
- T2: the task now names the private-sale vs part-exchange comparison, so the
  mid-point answer is enforced unambiguously (private sale).
- T14: the rates table is the live 2026/27 tax year (£200 standard, £10 EV
  first-year then standard, £560 for 131-150 g/km), matching the per-car
  values; the new BMW 320d EfficientDynamics Plus tax (£20, pre-2017
  registration regime as shown upstream) and insurance-group (27) anchors are
  enforced.
- The seed contract is re-frozen (see above); the honest fixtures are the r2
  re-review's real-browser trajectories (A-convention 20-37 steps, B-convention
  17-30 steps, every fact live-verified).

## Test matrix (`tests/test_verifiers.py`)

| group | fixtures | expectation |
|---|---|---|
| honest fixtures (real Playwright trajectories) | 20 | all PASS |
| no-op (homepage only, empty answer) | 20 | all FAIL |
| shortcut (correct answer, no navigation) | 20 | all FAIL |
| wrong answer (honest navigation, wrong numbers) | 20 | all FAIL |
| mutated after-DB (read-only tasks) | 17 | all FAIL |
| state mismatch (stateful tasks, wrong delta) | 3 | all FAIL |
| tamper (task_id / off-site URL / not terminated / bad PNG / empty answer) | 12 | all FAIL |
| mutated initial seed | 2 | FAIL |

Live replay (real browser against the running review container, DBs fetched
from the container): T8 (stateful) and T18 (read-only) both PASS.

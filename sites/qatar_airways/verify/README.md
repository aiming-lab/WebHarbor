# Deterministic task verifiers — qatar_airways (reviewer grading contract)

Authored by the reviewer on `orch/review/qatar_airways` per the review-env
skill: one verifier per task row in `../tasks.jsonl` (`verifier_path` +
`judge_rubric` are recorded inline on each row). Ground truth is
**hardcoded inside each verifier** — never in `tasks.jsonl`, which the
agent reads.

## Contract

Every `verify_N.py` emits `JSON {task_id, pass, reason, evidence[]}` on
stdout and exits 0 on PASS / 1 on FAIL, and fails **closed** on any
infrastructure error (missing trajectory, unreadable DB, verifier
exception). Checks, in order:

1. **Trajectory identity** — `task_id` matches, the run `terminated` with
   `agent_done`, the final answer is non-empty, every recorded URL is on the
   same loopback origin+port as `start_url`, and every referenced screenshot
   decodes as a PNG.
2. **Seed identity** — the run's initial DB must BE the frozen seed
   (schema digest + per-table row digest + row counts, all pinned in
   `verify_lib.py`). A run that started from a mutated database fails
   closed: its after-state delta is meaningless.
3. **Navigation gates** (anti knowledge-shortcut) — the run must have
   opened the on-site surfaces the task names: flight search with the
   task's route/cabin/passenger parameters, the booking chain (passenger
   details → payment → confirmation), Manage booking for the task PNR,
   check-in + boarding pass, flight-status queries, destination guides,
   the offer pages, the Privilege Club surfaces (login/join/dashboard/
   profile/calculator/tiers), fleet, baggage and help. A correct answer
   without the matching navigation is a memory-recall shortcut = FAIL.
4. **Answer checks** — affirmative token/phrase/amount/time matching
   against frozen ground truth (amounts tolerate `1,234` / `1234` /
   `USD 1,234` renderings; negated mentions do not count).
5. **DB after-state** — initial (seed) vs after (instance) SQLite
   snapshots. Read-only tasks require every table row-identical; stateful
   tasks require the exact allowed delta (one booking with its
   legs/passengers at the frozen route/date/fare/total — the runtime PNR
   must appear verbatim in the answer and identify the added row; a status
   flip to cancelled; an extra-bag bump; seat assignments + a checked-in
   flag; an Avios debit + activity row; a profile update; a new member
   row) and every other table row-identical.

## Ground-truth provenance

Every frozen value was re-derived independently by the reviewer from live
page reads during honest Playwright walkthroughs (fresh container
`wh-qa-review`, per-task reset), then cross-checked against the seed DB.
The frozen seed digests in `verify_lib.py` pin the independently built
in-image seed (sha256
`602979203eddb57a8391dae603282aef1b86d03b7f6cea3dc257e93f2b5e0478`).

## Running

```bash
# from the agent_demo env (or any python3 — the fallback parser has the
# same flags)
uv run python eval_judge.py --run_dir runs/<task> --verifier True

# or directly:
python3 sites/qatar_airways/verify/verify_0.py \
    --run_dir runs/0 \
    --initial_db runs/0/initial.db --after_db runs/0/after.db
```

`--run_dir` must contain `trajectory.json` (+ `screenshots/step_*.png`).
With no explicit DB paths, the verifier falls back to `<run_dir>/initial.db`
/ `<run_dir>/after.db`, then to the site's local
`instance_seed/qatar_airways.db` / `instance/qatar_airways.db`, then to
`docker cp` from `--container` (default `$WH_CONTAINER` or `wh-qa-review`).

## Anti-fooling guarantees (all exercised in tests/test_verifiers.py)

- A **no-op run** (homepage only, empty answer, clean DB) fails every
  verifier on the identity + navigation gates — 20/20 FAIL.
- A **shortcut run** (correct answer, no on-site navigation) fails the
  navigation gates.
- A **wrong-answer run** fails the frozen answer checks.
- A **state-mismatch run** (self-reported success, DB unchanged) fails the
  DB delta checks.
- A **wrong-delta run** (right shape, wrong numbers, or collateral writes)
  fails the exact-delta / read-only checks.
- A **tampered package** (wrong task_id, cross-origin URL, broken
  screenshot, missing trajectory) fails closed.
- A run whose **initial DB is not the frozen seed** fails the seed gate.
- Runtime-random values (PNRs, membership numbers) are matched
  structurally: the value in the answer must equal the value on the added
  row, never a hardcoded constant.

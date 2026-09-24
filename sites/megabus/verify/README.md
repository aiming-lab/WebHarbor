# Megabus grading contract (reviewer-authored)

21 deterministic verifiers, one per task row in `sites/megabus/tasks.jsonl`
(`Megabus--0` … `Megabus--20`), plus `verify_lib.py` (shared utilities), 
`append_rubrics.py` (grading-key insertion) and `tests/test_verifiers.py`
(117 contract tests, all deterministic — no LLM anywhere).

## Contract

- **Input**: `--run_dir DIR` (agent trajectory: `trajectory.json` +
  `screenshots/step_NNN.png`), `--initial_db` / `--after_db` (default:
  `<run_dir>/initial.db` / `<run_dir>/after.db`, else fetched from the review
  container `wh-megabus-audit`), `--container NAME`.
- **Output**: JSON `{task_id, pass, reason, evidence[]}` on stdout; exit 0 on
  PASS, 1 on FAIL. Any internal error fails closed (`infra_error: true`).
- **Frozen seed contract**: `SCHEMA_SHA256` + per-table `SEED_COUNTS` +
  `SEED_ROWS_SHA256` over the deterministic build-time seed
  (`instance_seed/megabus.db`, PYTHONHASHSEED=0, byte-reproducible).
- **Identity gates**: task_id match, `terminated/agent_done`, non-empty
  answer, all URLs on the same loopback origin+port as `start_url`, every
  screenshot a decodable PNG.
- **Navigation gates**: per-task required surfaces (journey results with the
  exact originId/destinationId/departureDate, fare finder, basket/checkout/
  confirmation chain, manage-booking lookup/change/cancel, account area,
  tracker, alerts, help topics). Correct answer without navigation = FAIL
  (anti knowledge-shortcut).
- **Answer gates**: token/phrase/amount/count/time/duration matching against
  ground truth HARDCODED in each `verify_N.py` (never in `tasks.jsonl`).
- **DB after-state gates**: read-only tasks require a row-identical DB;
  stateful tasks (0, 2, 3, 4, 17, 18, 19) require the exact allowed delta
  (added booking + booking_journeys with the task's math, basket row, user
  row, profile update, status flip) and no collateral writes.

## Tests

```
python3 -m pytest sites/megabus/verify/tests -q    # 117 passed
```

Covers: honest PASS (read-only + stateful), no-op FAIL (21×), wrong answer
FAIL, shortcut FAIL (21×), state-mismatch FAIL, wrong-delta FAIL, read-only
mutation FAIL, tamper FAIL (task_id, off-site URL, missing screenshot,
non-done trajectory, tampered seed).

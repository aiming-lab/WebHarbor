# MTA grading contract (reviewer-authored)

20 deterministic verifiers, one per task row in `sites/mta/tasks.jsonl`
(`MTA--0` … `MTA--19`), plus `verify_lib.py` (shared utilities),
`append_rubrics.py` (grading-key insertion) and `tests/test_verifiers.py`
(111 contract tests, all deterministic — no LLM anywhere).

## Contract

- **Input**: `--run_dir DIR` (agent trajectory: `trajectory.json` +
  `screenshots/step_NNN.png`), `--initial_db` / `--after_db` (default:
  `<run_dir>/initial.db` / `<run_dir>/after.db`, else fetched from the review
  container `wh-mta-review`), `--container NAME`.
- **Output**: JSON `{task_id, pass, reason, evidence[]}` on stdout; exit 0 on
  PASS, 1 on FAIL. Any internal error fails closed (`infra_error: true`).
- **Frozen seed contract**: `SCHEMA_SHA256` + per-table `SEED_COUNTS` +
  `SEED_ROWS_SHA256` (small/medium tables, full rows) + `BIG_FP_SHA256`
  (trips/stop_times: counts + id aggregates + boundary rows) over the
  deterministic build-time seed (`instance_seed/mta.db`, PYTHONHASHSEED=0).
  The constants are SQLite-version-independent (verified across the image's
  SQLite 3.40.1 and a 3.45.1 host build of the same source data).
- **Identity gates**: task_id match, `terminated/agent_done`, non-empty
  answer, all URLs on the same loopback origin+port as `start_url`, every
  screenshot a decodable PNG.
- **Navigation gates**: per-task required surfaces (LIRR timetables with the
  task's branch, the railroad fare finder with the exact station pair + ticket
  type, the elevator & escalator status search, the planned-service-changes
  browser with mode+window, the lost-and-found claim flow, the feedback form,
  the account area OMNY/favorites/subscriptions/cases/AAR pages, the guides,
  the transparency leadership + meeting-calendar pages, the project and press
  pages, the tolls pages). Correct answer without navigation = FAIL
  (anti knowledge-shortcut).
- **Answer gates**: token/phrase/amount/count/time/ref matching against
  ground truth HARDCODED in each `verify_N.py` (never in `tasks.jsonl`).
- **DB after-state gates**: read-only tasks (0,1,2,5,6,9,10,11,12,13,14,15,
  17,18) require a row-identical database; stateful tasks (3,4,7,8,16,19)
  require the exact allowed delta and no collateral writes:
  - 3/19: exactly one `feedback_cases` row (`CS-26095598`, the deterministic
    first case after a clean reset), with the task's category and subject;
  - 4: exactly one `lost_claims` row (`LF-26096491`, agency `nyct`, the
    task's item/contact details);
  - 7: alice's favorites exactly `{(subway,Q),(rail,Babylon Branch)}` and
    subscriptions exactly `{(subway,Q)}`, other users untouched;
  - 8: exactly one `aar_trips` row (`AAR-26096609`) with the task's
    pickup/destination/date/time/walker/medical details;
  - 16: exactly one `users` row (pat.gonzalez@example.net, `OMNY-5155F7F3`)
    with favorites `{(subway,E),(rail,Metro-North Harlem Line)}` and one
    `(subway,E)` subscription.

## Deterministic reference numbers

`app.next_ref()` derives the first post-reset reference on the pinned day
(2026-09-23) from `sha256("<prefix>-20260923")[:6]` plus the seeded row count
(3 per category), so the graders hardcode `CS-26095598`, `LF-26096491` and
`AAR-26096609`.

## Tests

```
MTA_TEST_SEED_DB=<seed copy> python3 -m pytest sites/mta/verify/tests -q
# 111 passed
```

Covers: honest PASS (read-only + stateful), no-op FAIL (20×), wrong answer
FAIL (20×), shortcut FAIL (20×), read-only mutation FAIL, state-mismatch
FAIL, wrong-delta FAIL, package tampering FAIL (task_id mismatch, off-site
URL, missing screenshots, unterminated trajectory, doctored initial DB).
A live-container no-op run (DBs fetched from `wh-mta-review`) also FAILs.

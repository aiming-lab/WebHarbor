# re_max — deterministic task verifiers (reviewer contract)

One verifier per benchmark task (`verify_0.py` … `verify_19.py`), a shared
`verify_lib.py`, and adversarial contract tests under `tests/`.

## Contract

Each verifier reads an agent run directory (`trajectory.json` +
`screenshots/step_NNN.png`) plus the initial/after SQLite databases and emits
a binary PASS/FAIL (`{task_id, pass, reason, evidence[]}`, exit 0/1):

1. **Package identity** — task_id matches, `terminated` with
   `agent_done`, non-empty final answer, every URL on the same loopback
   origin/port as `start_url`, screenshots decode as PNG.
2. **Navigation gates** (anti knowledge-shortcut) — the on-site surfaces the
   task names must have been opened: the city SRP carrying the task's filter
   combination, the listing/rental/agent/office detail pages, the advice
   articles, the open-house state pages, the site search, and the account
   surfaces. A correct answer without the navigation is a FAIL.
3. **Answer gates** — token/phrase/amount/count matching against ground
   truth **hardcoded in the verifier** (frozen against the shipped seed DB;
   never in `tasks.jsonl`).
4. **DB after-state** — read-only tasks must leave the database row-identical
   to the frozen seed; stateful tasks (4, 8, 10, 11, 12, 13) must produce
   exactly the allowed row delta (one tour inquiry for listing 372, one
   availability inquiry for rental 26, Bob's listing-264 favorite removed,
   Carol's Naples favorites removed + one `Miami, FL` saved search, one new
   `maria.torres@example.com` user + one Miami alert, one solar-panels agent
   inquiry) and nothing else. The seed contract (schema sha + per-table
   counts + row sha) is enforced on the initial DB.

## Usage

```bash
# against a run dir; DBs default to the review container (or run-dir copies)
python3 sites/re_max/verify/verify_4.py --run_dir runs/task4 \
    [--initial_db P] [--after_db P] [--container wh-remax-review]

# adversarial contract tests (honest / no-op / shortcut / wrong / tamper /
# mutated-DB / state-mismatch / seed-tamper)
python3 -m pytest sites/re_max/verify/tests/test_verifiers.py -q
```

## Known task defect (documented by this review)

`REMAX--7` asks for the REMAX office serving Grapevine, but the offices
finder (`/real-estate-offices`) is not linked from any on-site page and the
site search returns no office for "Grapevine", so the task is not honestly
reachable in the current build. `verify_7.py` encodes the correct-answer
contract (office detail page + name/website/languages/service area) and
therefore FAILs the honest dead-end trajectory — see
`tests/test_verifiers.py::test_t7_honest_deadend_fails`. Once the contributor
links the offices hub (or re-anchors the task), the same verifier grades the
fixed task unchanged.

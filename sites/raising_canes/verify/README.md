# Raising Cane's — task verification contract

Reviewer-written grading contract for the 20 `tasks.jsonl` tasks. Each
`verify_<N>.py` is a standalone deterministic verifier for task
`Raising Cane's--<N>`; `verify_lib.py` holds the shared helpers. Ground
truth is hardcoded inside each verifier (never in `tasks.jsonl`).

## Design

Deterministic only — no LLM calls anywhere:

1. **Trajectory navigation check (anti knowledge-shortcut).** Each verifier
   requires the run's trajectory to contain the on-site pages the task
   demands (item pages at the right restaurant, the nutrition page, the
   FAQ search, the careers search, order history, account pages). A
   correct answer with homepage-only navigation fails.
2. **SQLite after-state check (stateful tasks).** The verifier queries the
   after-state DB for the exact expected row: the placed order with its
   location, pickup mode/date/time, contact name, payment method,
   subtotal/discount/tax/total and per-item selections; gear orders with
   their items and shipping; gift-card balances; Caniac points; cancelled
   status; profile edits. The DB is resolved from `<run_dir>/after.db` if
   present, else `--after_db`, else docker-copied live from the container.
3. **Answer check.** The final answer must contain the order number, the
   dollar total, and every research fact the task asks for (counts,
   addresses, phones, nutrition values, job references), matched with
   regexes tolerant of formatting.

## Usage

```bash
python3 sites/raising_canes/verify/verify_0.py --run_dir runs/0 \
    [--initial_db ...] [--after_db ...] [--container wh-rc-review]
```

Prints `{task_id, pass, reason, evidence[]}` JSON; exit 0 on PASS, 1 on FAIL.

## Tests

```bash
python3 -m pytest sites/raising_canes/verify/tests -q
```

100 tests cover, per task: the honest trajectory MUST PASS (stateful tasks
against the seed plus the exact allowed sqlite delta), a no-op run MUST
FAIL, a wrong answer MUST FAIL, a knowledge-shortcut (correct answer,
homepage-only navigation) MUST FAIL, and stateful tasks MUST FAIL on a
state-mismatch (clean DB, self-reported success). T17 rejects a wrong city
list, and the r2 re-anchored tasks carry adversarial negatives for their
pre-r2 readings (see the r2 section below).

All totals in the fixtures were re-derived independently by the reviewer
from the per-quantity Olo price tables and the 8.25% sales-tax rate during
the 2026-09-24 review walkthroughs.

## r2 re-sync (fix 6a563727)

The contributor's round-1 fix re-anchored five task texts; this contract
was re-synced against the fixed site (independently rebuilt + live-walked
in the r2 review container):

- **T9** now asks how many of the Dallas Catering Delivery results are in
  Dallas, TX — the verifier tightened to that count and the pre-r2 literal
  13-result reading is a FAIL (`test_t9_literal_count_fail`).
- **T11** anchors pickup at the offered 5:00 PM slot — the DB check pins
  that slot and a 4:45 PM order FAILs (`test_t11_old_slot_fail`).
- **T12** names the Cool Cane Barking Plush Puppy — the nav and DB checks
  pin that exact product; a different plush FAILs
  (`test_t12_wrong_plush_fail`).
- **T16** adds the points sub-questions — the DB check pins the rolled-back
  balance and the answer must report the returned points (52, not the
  $52.71 total) and the after-balance (`test_t16_missing_points_fail`,
  `test_t16_no_points_rollback_fail`).
- **T17** requires opening the La Marque job detail — nav gate + reference
  number + department answer checks; the pre-r2 answer shape FAILs
  (`test_t17_missing_reference_department_fail`).
- T13/T14 verifiers are byte-identical to round 1: they were already
  anchored to the post-A-2/A-3 site behavior ($28.94 / $31.95) and now
  honest-PASS against the fixed site.
- `tasks.jsonl`: every row's 5-key prefix is byte-identical to the fixed
  contribute rows; the 15 unaffected rows keep their committed bytes;
  `sync_r2_tasks.py` performs the sync programmatically.

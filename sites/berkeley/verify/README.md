# UC Berkeley deterministic grading contract

Each row in `sites/berkeley/tasks.jsonl` points to `verify_1.py` … `verify_31.py` (22 verifiers, one
per row; the ids are the contributor's, so numbers are not contiguous). The wrappers use
`verify_lib.py` for package, URL, answer and state validation and `ground_truth.py` to re-derive
every target from the supplied initial SQLite snapshot. No verifier calls an LLM; a verdict never
depends on a key or a model. The per-row ACCEPT/DROP/ADDED decisions are recorded in the review history.

## Inputs

```bash
python sites/berkeley/verify/verify_1.py \
  --run_dir /absolute/path/to/run \
  --initial_db /absolute/path/to/initial.db \
  --after_db /absolute/path/to/after.db
```

If explicit snapshots are omitted, the verifier checks `<run_dir>/initial.db` and
`<run_dir>/after.db`, then falls back to `docker cp` from `$WH_CONTAINER` (default `wh-review`):
`instance_seed/berkeley.db` is the initial state and `instance/berkeley.db` the after state. Missing
or invalid inputs fail closed (`infra_error: true`, exit 1). Output is JSON with `task_id`, `pass`,
`reason` (the first failing check) and `evidence`; exit code 0 means PASS and 1 means FAIL.
`agent_demo/eval_judge.py --run_dir <dir> --verifier True` is the normal entry point; `--no_llm` is
accepted for parity and ignored.

## Snapshot contract

Both snapshots must carry the exact nine-table UC Berkeley schema (hash pinned), the frozen seed
counts (14 colleges, 30 departments, 83 programmes, 82 faculty, 25 research centres, 121 news
articles, 64 events, 4 users, 0 bookmarks) and the row-level catalog fingerprint pinned in
`verify_lib.py`. `ground_truth.py` then re-derives the task's target the way the app renders it —
the `BENCHMARK_NOW = 2026-05-12` event filter, `PER_PAGE`, the app's `ORDER BY` clauses and the
`ORDER BY name LIMIT 3` related-centres query — and fails closed on drift. The seven catalog tables must
be row-identical before and after; `users` and `bookmarks` are the only runtime tables.

Read-only tasks (everything except 30 and 31) require **every** seeded table to be row-identical,
so an incidental bookmark, registration or catalog write fails. The stateful verifiers (30, 31)
check the exact bookmark row delta for the demo account first (`bookmarks_exact_delta`), then that no
other user's bookmarks changed (`bookmarks_other_users_unchanged`), then the row-id binding where the
task fixes the order (`bookmarks_surviving_row_ids`, task 31), then that `users` is unchanged. A run
that self-reports success without writing the row fails on the delta; a skipped removal, a reversed
add order or an extra save each fail on a named check.

## Gates and answer matchers

Navigation gates require an exact mirror path (any loopback port) carrying every required query
parameter; a listing hit never replaces a detail visit, and the final action's declared target
counts as a visit so a run that ends on a `navigate` is not penalised. Multi-hop tasks (19, 24, 25,
30, 31) gate each hop; the ordered ones (24, 30, 31) additionally require the hops in sequence
(`check_paths_in_order`), while 19 and 25 gate their listing and detail visits independently. The
catalog-scan tasks (16, 28) accept either the filtered listings or several pages of the full listing.

Answer matchers are negation-aware whole-token matches: names (titles ignored), locations (leading
room numbers optional), counts (thousands separators and word forms, with "12" never matching inside
"1,200" or "14.4"), years, percentages, dates in six formats, month-day literals, degree types
(`Ph.D.` variants), durations (`1 year` never matches inside `1.5 years`; `18 months` accepted for
1.5), interest tokens bound to the named row, and title-token binding for events and articles.
A value the task derives is additionally protected against a confirming contrast being mistaken for
negation: "founded in 2013, not 2017" is affirmative, while "2013 was not the founding year" is not.

## Source-rendered values

Two rows (11 and 17) depend on values the app renders from tracked source rather than the DB.
`ground_truth.py` parses `templates/admissions.html` and `app.py` and fails closed if the labelled
literals move; `verify/tests` asserts they stay source literals and never become DB-derived. Row 17
additionally rejects the page's "more than N Nobel Prizes" line when it is claimed as the faculty
count (a clause-local rule, so quoting the alumni line elsewhere is not a wrong answer).

## Tests

```bash
python -m pytest sites/berkeley/verify/tests -q
```

The fixtures copy the frozen seed and rewrite only `bookmarks` (stdlib `sqlite3`), so every fixture
DB reproduces the pinned fingerprint; trajectories follow the `agent_demo/agent.py` run signature.
Per task: genuine PASS, no-op, wrong task id, another task's trajectory, shortcuts (including
catalog-wide-token searches), one or two wrong answers, alternative phrasings, a negated answer, a
truncated run, corrupt and 1×1 PNG screenshots, a missing `after.db`, catalog and schema drift, an
incidental write, and — for 30/31 — the state-mismatch, wrong-target, wrong-order and collateral
cases. `test_tasks_contract.py` validates `tasks.jsonl` (22 rows, seven keys, verifier paths, and no
derived answer value in any rubric). `test_verify_lib.py` covers each matcher's accepted and rejected
forms, the gate semantics, the fingerprint recipe and the source-fact rules.

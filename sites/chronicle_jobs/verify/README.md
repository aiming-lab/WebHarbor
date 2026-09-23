# chronicle_jobs deterministic grading contract

Every row in `sites/chronicle_jobs/tasks.jsonl` points to `verify_0.py` …
`verify_29.py` (`verifier_path`) and carries an English `judge_rubric` of fact
checkpoints for the LLM judge. The five original contributor keys
(`web_name, id, ques, web, upstream_url`) come from the contribution —
byte-identical for 28 rows; rows `--3` and `--16` carry the contributor's
NEEDS-FIX rewording (single exact dollar amount; named part-time job)
merged in at re-review; the reviewer appended only `verifier_path` and
`judge_rubric` on top of the contributor wording.
Ground truth (job ids, slugs, dates, salary figures, counts, seeded rows)
lives **only** inside the `verify_N.py` files — never in `tasks.jsonl` (the
agent reads that file; an answer key there would leak answers). No verifier
calls an LLM; the `llm_*` helpers in `verify_lib.py` exist for API parity
with `sites/merriam_webster/verify/verify_lib.py` and nothing depends on them.

## Inputs / outputs

```bash
uv run python sites/chronicle_jobs/verify/verify_7.py --run_dir /abs/path/to/run \
    [--initial_db /abs/initial.db] [--after_db /abs/after.db] [--no_llm True]
```

* `run_dir` holds `trajectory.json` (the `agent_demo/agent.py` shape) and
  `screenshots/step_NNN.png`.
* Snapshots: explicit `--initial_db/--after_db`, else `<run_dir>/initial.db`
  and `<run_dir>/after.db`, else `docker cp` from `$WH_CONTAINER` (default
  `wh-review`) at `/opt/WebSyn/chronicle_jobs/{instance_seed,instance}/chronicle_jobs.db`.
  Missing or out-of-contract snapshots fail closed (`infra_error: true`).
* Output: JSON `{task_id, pass, reason, evidence[]}` on stdout; exit 0 PASS /
  1 FAIL. `agent_demo/eval_judge.py --run_dir … --verifier True` invokes it
  this way (`verifier_path` is read from the task row by `agent.py` and
  carried inside `trajectory.json`).

## What every verifier enforces

1. **Run-package identity (anti-tamper)** — exact `task_id`
   (`Chronicle Jobs--N`); non-empty `final_answer`; `terminated: true` with
   `termination_reason: agent_done`; at least one step; every recorded URL
   (`start_url`, step `url` / `url_after`, `navigate` targets, `final_url`) on
   the same loopback host **and port** as `start_url`; every referenced
   screenshot present and PNG-framed.
2. **Navigation gates (anti knowledge-shortcut)** — the on-site interaction
   the task names: keyword search (`/searchjobs/` or `/jobs/…` with
   `Keywords=`, token-matched), location-only search (`radialtown=` with an
   empty keywords box), facet / category browse (`/jobs/<slug>…`), job detail
   (`/job/<id>/<slug>/`), employer hub (`/employer/<ref>/<slug>/`), career
   article (`/career-resources/<slug>/`), sign-in (`/logon` + the typed demo
   email), account sections (`/your-jobs/?ActiveSection=…`), apply page
   (`/apply/<id>/<slug>`), alert form (`/newalert`), resume page
   (`/profilecv/`), and `sort=Date` for the date-sort task. Task 10 accepts
   BOTH honest narrowing paths on the adjunct browse: the location filter
   field (`radialtown=Texas`) or the chained Texas facet URL
   (`/jobs/adjunct/texas/`, order-independent) — both are real on-site
   navigation and both yield the same intersection.
3. **Answer** — hardcoded ground truth matched with normalization-tolerant
   helpers: `contains_number` (standalone integer), `contains_dollar_amount`
   (with or without `$`/commas), `contains_month_date` (`Sep 21, 2026` ≙
   `September 21st, 2026`), `contains_all` / `contains_any` with negation
   awareness ("not X" does not count), and per-task title lists.
4. **SQLite after-state** — the snapshot contract (13 tables, exact seed
   counts, schema equality, the four benchmark users) is validated first.
   Read-only tasks require **all thirteen tables** row-identical to the seed.
   Stateful tasks require the **exact** row delta and nothing else:

| task | persisted change that must be exactly present |
|---|---|
| 16 | `saved_jobs` row 5 (bob, Part-Time Academic Coach) removed; nothing else |
| 17 | +1 `saved_jobs` row (carol, Dean, College of Business) |
| 19 | `applications` row 4 (carol, Psychologist): only `withdrawn` + `status` → Withdrawn |
| 20 | +1 `applications` row (alice, Director of Client Solutions and Support, cover ≥ 20 chars, Applied) |
| 22 | +1 `job_alerts` row (anonymous, registrar / Chicago / Weekly, casey.r@test.com) |
| 23 | `job_alerts` row 4 (bob, data near Chicago) removed; nothing else |
| 25 | `users` row 1 (alice): only `headline` changed |
| 26 | `users` row 4 (david): only `location` changed |

## Validation tooling

* `drive_tasks.py` — honest Playwright driver: real browser interactions for
  all 30 tasks; every task starts from a control-plane DB reset + a fresh
  context (clean cookies); final answers are read off the rendered pages.
* `run_matrix.py` — the full matrix: `honest` (must PASS) plus the negative
  legs `no_op`, `shortcut` (correct answer, no navigation), `wrong`
  (plausible-but-wrong answer), `tamper_id`, `tamper_url`, `tamper_shot`
  (run-package tampering) — every negative must FAIL (zero false positives).
* `test_verifiers.py` — pytest front-end over the same matrix:

```bash
cd agent_demo
WH_CONTAINER=wh-rev-chronicle_jobs uv run --with pytest python -m pytest \
    ../sites/chronicle_jobs/verify/test_verifiers.py -v
```

The suite skips (with the reason) when the review container / mirror are not
reachable, and takes roughly 30-40 minutes when it runs the full 30×7 matrix.

## Reviewed task extensions and evidence checks

The reviewer continuation preserves every task ID and expands short requests with
related outcomes. `review_components.json` lists the required checks for each task;
`composed_grade.py` requires every component on the same recorded session. Answers
remain natural prose. Initial and final SQLite snapshots must be supplied together,
and initial table contents must match `reviewed_seed.json`. Image evidence is decoded
with Pillow; a PNG header alone is insufficient. Navigation must stay on the starting
origin, including its port. Synthetic controls are separate from browser evidence.

Run the primary grader from the repository root using
`python agent_demo/eval_judge.py --run_dir /path/to/run --verifier True`.
Task paths, screenshots and database outcomes are separate requirements. Grading
uses deterministic phrase and numeric checks, which are not a general semantic judge.
The optional LLM judge remains a separate secondary assessment.

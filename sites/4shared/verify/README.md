# 4shared deterministic grading contract

Every row in `sites/4shared/tasks.jsonl` points to `verify_0.py` … `verify_19.py`
(`verifier_path`) and carries an English `judge_rubric` of fact checkpoints for the
LLM judge. Ground truth (file slugs, ids, filenames, uploaders, counts, exact row
values) lives **only** inside the `verify_N.py` files. No verifier calls an LLM;
the `llm_*` helpers in `verify_lib.py` exist for API parity with
`sites/merriam_webster/verify/verify_lib.py` and nothing depends on them.

## Inputs / outputs

```bash
uv run python sites/4shared/verify/verify_7.py --run_dir /abs/path/to/run \
    [--initial_db /abs/initial.db] [--after_db /abs/after.db] [--no_llm True]
```

* `run_dir` holds `trajectory.json` (the `agent_demo/agent.py` shape) and
  `screenshots/step_NNN.png`.
* Snapshots: explicit `--initial_db/--after_db`, else `<run_dir>/initial.db` and
  `<run_dir>/after.db`, else `docker cp` from `$WH_CONTAINER` (default `wh-review`)
  at `/opt/WebSyn/4shared/{instance_seed,instance}/4shared.db`. Missing or
  out-of-contract snapshots fail closed (`infra_error: true`).
* Output: JSON `{task_id, pass, reason, evidence[]}` on stdout; exit 0 PASS / 1 FAIL.
  `agent_demo/eval_judge.py --run_dir … --verifier True` invokes it this way.

## What every verifier enforces

1. **Run-package identity** — exact `task_id`; non-empty `final_answer`;
   `terminated: true` with `termination_reason: agent_done`; ≥ 1 step; every recorded
   URL (`start_url`, step `url`, `navigate` targets, `final_url`) on the same loopback
   host **and port** as `start_url`; every referenced screenshot present and
   PNG-framed.
2. **Navigation gates** (anti knowledge-shortcut) — exact mirror paths
   (`/file/<slug>`, `/login`, `/favorites`, `/saved`, `/my-files`, `/upload`,
   `/trash`, `/file/<id>/share`, `/premium/checkout`, `/account`, `/download/<id>`),
   an on-site `/search` (query tokens) or `/category/<c>` visit where the task says
   "search/browse", and required ordering where the task implies it (login before
   the action; detail page before download; checkout before the account check).
3. **Answer** — exact filename incl. extension (`contains_filename`), uploader
   (`contains_all`), standalone numbers (`contains_number`: not part of a time,
   ratio, version or longer digit run), runtimes (`contains_runtime`), displayed
   sizes (`contains_size`), resolutions (`contains_resolution`), and comparison
   claims (`claims_winner`: the item credited by "longer/most…" must be the winner).
   Negated mentions ("not X") do not count.
4. **SQLite after-state** — the snapshot contract (9 tables, seed counts, schema
   equality, benchmark users) is validated first. Read-only tasks require **all**
   nine tables row-identical. Stateful tasks require the **exact** row delta and
   nothing else:

| task | persisted change that must be exactly present |
|---|---|
| 6 | +1 `downloads` row for The Federalist Papers, its `download_count` +1 |
| 7 | +1 `favorites` (alice, ArchivePeek File Inspector) |
| 8 | +1 `saved_files` (alice, Rain Garden Planting Guide) |
| 9 | alice `users` row: `location`/`bio` only |
| 10 | +1 `folders` (bob, root, "Survey Exports") |
| 11 | +1 `files` (carol, Work, exact name/size/description, private, Documents) |
| 12 | file 123: new filename + `folder_id` (Shared Projects) only |
| 13 | file 146: `deleted` 1 → 0 only |
| 14 | +1 `shared_links` (alice, file 125, download, "Audio volunteers") |
| 15 | +1 `comments` (bob, file 93, exact body) |
| 16 | +1 `plan_orders` (bob, Premium 100 GB, annual, 77.88, 4242); bob `plan`/`storage_limit_mb` |
| 17 | +1 folder, +1 file (final name, in it, 384 KB, private), +1 view-only link; timestamps ordered |
| 18 | +1 `saved_files` (david, Twenty Thousand Leagues Under the Seas) |
| 19 | +1 `favorites` + 1 `downloads` (alice, file 96), `download_count` +1 |

## Validation harness (`verify/tests/`, excluded from the image)

```bash
# 1. genuine PASS runs: boots the site from instance_seed/ per task and drives it with Chromium
uv run python sites/4shared/verify/tests/drive_tasks.py --python <venv-with-Flask>/bin/python --port 45004
# 2. matrix: noop / pass / shortcut / wrong / state-mismatch for every task
uv run python sites/4shared/verify/tests/run_matrix.py
```

`drive_tasks.py` writes `tests/runs/<N>/pass/` (trajectory + screenshots +
`initial.db` + `after.db`); `run_matrix.py` derives the negative variants
(homepage-only empty answer; correct answer with every URL rewritten to the
homepage; a wrong answer or a wrong persisted row; the seed as `after.db`), runs
every verifier with `--no_llm True`, and exits non-zero if any cell disagrees with
its expectation. Run dirs are git-ignored.

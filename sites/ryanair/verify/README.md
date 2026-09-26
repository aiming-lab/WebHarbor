# ryanair — reviewer grading contract

Deterministic verifier suite for the 21 ryanair tasks, written by the reviewer
per the review-env skill (Step 6). Ground truth is **hardcoded inside each
`verify_N.py`** — never in `tasks.jsonl` (the agent reads that file; an answer
key there would leak).

## Layout

- `verify_lib.py` — shared deterministic utilities: trajectory identity
  (task_id, `agent_done`, same-origin URLs, decodable screenshots), navigation
  gates, answer matching (amounts / times / counts / phrases), SQLite
  before/after snapshot contract (frozen seed schema + rows sha256), fail-closed
  runner. No LLM call is load-bearing.
- `verify_0.py` … `verify_20.py` — one verifier per task. Run:

  ```bash
  uv run python sites/ryanair/verify/verify_0.py --run_dir runs/0
  ```

  Prints `{task_id, pass, reason, evidence[]}` JSON; exit 0 on PASS, 1 on FAIL.
  DB snapshots resolve from `<run_dir>/initial.db` + `<run_dir>/after.db`, else
  from the container (`--container`, default `$WH_CONTAINER` or `wh-ry-review`)
  via `docker cp`.
- `append_rubrics.py` — adds `verifier_path` + `judge_rubric` to
  `../tasks.jsonl`. The five contributor keys stay byte-identical (each row is
  the original line with the two new keys appended); no `answer` key is ever
  written. Idempotent.
- `tests/` — `pytest` contract suite (110 tests): honest PASS fixtures per task
  (frozen from the reviewer's live runs), no-op FAIL, knowledge-shortcut FAIL,
  wrong-answer FAIL, state-mismatch FAIL, read-only mutation FAIL, and package
  tampering (task_id / off-site URL / missing screenshot / not-done trajectory /
  tampered seed) fail-closed. Run:

  ```bash
  python3 -m pytest sites/ryanair/verify/tests -q
  ```

  The seed DB is docker-cp'd from the container (override with
  `RYANAIR_TEST_SEED_DB`).

## Known site defect encoded by the contract

`verify_13.py` pins the **intended** one-way bag pricing (one 20kg bag charged
once: £25.49, total £45.36). The live site currently double-charges the phantom
return leg (£50.98 for the bag — more than the £50.00 airport price), which
contradicts the task's premise; see the review report. The verifier passes once
that pricing bug is fixed; the pytest PASS fixture encodes the post-fix values.

# soundcloud — reviewer grading contract

Deterministic verifier suite for the 21 soundcloud tasks, written by the reviewer
per the review-env skill. Ground truth is **hardcoded inside each `verify_N.py`**
(and mirrored in the pure-rule English `judge_rubric` in `../tasks.jsonl`) —
never as an `answer` key the agent could read.

## Layout

- `verify_lib.py` — shared deterministic utilities: trajectory identity
  (task_id, `agent_done`, same-origin+port URLs, decodable PNG screenshots),
  navigation gates, answer matching (numbers with comma/compact normalization,
  phrases, orderings), SQLite before/after snapshot contract (frozen seed
  schema sha256 + row-digest sha256 + table counts), fail-closed runner.
  No LLM call is load-bearing.
- `verify_0.py` … `verify_20.py` — one verifier per task. Run:

  ```bash
  python3 sites/soundcloud/verify/verify_0.py --run_dir runs/SoundCloud--0
  ```

  Prints `{task_id, pass, reason, evidence[]}` JSON; exit 0 on PASS, 1 on FAIL.
  DB snapshots resolve from `<run_dir>/initial.db` + `<run_dir>/after.db`, else
  from the container (`--container`, default `$WH_CONTAINER` or `wh-sc-review`)
  via `docker cp`.
- `append_rubrics.py` — adds `verifier_path` + `judge_rubric` to
  `../tasks.jsonl`. The five contributor keys stay byte-identical (each row is
  the original line with the two new keys appended); no `answer` key is ever
  written. Idempotent.
- `tests/` — `pytest` contract suite (113 tests): honest PASS fixtures per task
  (frozen from the reviewer's live 21/21 walkthroughs), no-op FAIL,
  knowledge-shortcut FAIL, wrong-answer FAIL, state-mismatch FAIL (stateful
  tasks), read-only after-DB tamper FAIL, package tampering (task_id mismatch,
  off-site URL, missing/undecodable screenshot, non-done trajectory) FAIL, and
  adversarial DB deltas (wrong like target, extra playlist entry, wrong
  subscription cycle, drifted seed) FAIL. Run:

  ```bash
  python3 -m pytest sites/soundcloud/verify/tests -q
  ```

## Task classification

- Read-only (after-DB must equal the frozen seed): 0, 1, 2, 4, 9, 10, 12, 17,
  18, 19.
- Stateful (exact allowed row delta): 3 (like toggle — see the fixture note in
  `verify_3.py`: Alice's seed already likes the target track), 5 (playlist
  create + 2 entries), 6 (unlike + follow), 7 (subscription add), 8 (upload +
  auto-created artist), 11 (follow + playlist with 1 entry), 13 (repost), 14
  (comment at timestamp), 15 (3 play events), 16 (playlist entry removal +
  renumber), 20 (subscription swap).

## Fixture provenance

`tests/fixtures_data.py` was extracted from the reviewer's live honest runs
against the review container (branch `orch/review/soundcloud`, image
`webharbor:sc-review`, container `wh-sc-review`): the URL trail and final
answers are verbatim from those runs, and the `sql` lists were produced by
diffing each run's `initial.db`/`after.db` snapshots, so the fixtures
reproduce the exact observed after-states from the deterministic seed
(md5 `876a23a55c41e6245a84bc1d2b1de14b`).

# Google Shopping — deterministic grading contract

Reviewer-authored grading artifacts for the 30 benchmark tasks in `../tasks.jsonl`.
Every verdict is decided by `--no_llm True` deterministic checks; the LLM helpers in
`verify_lib.py` are advisory only.

Layout:
- `verify_lib.py` — shared fail-closed harness: trajectory identity gates (task_id,
  `agent_done`, non-empty answer, same-origin loopback URLs, decodable PNG screenshots),
  navigation gates (path / scored-search-with-params matchers), affirmative
  token/phrase/count/percent/rating and money matching (`$129.90 == $129.9`,
  `$1,704 == 1704.00`), SQLite snapshot validation bound to the frozen seed
  (schema sha256 `1d01ed2b…`, 9-table counts incl. products 61 / merchants 37 /
  offers 61 / feed_sections 2, full rows digest `bfd18c5b…`, benchmark user
  identities), and the fail-closed CLI runner.
- `verify_0.py` … `verify_29.py` — one verifier per task; ground truth is HARDCODED
  inside each file (never in `tasks.jsonl`). Read-only tasks require every table
  row-identical before/after; stateful tasks (21/22/23/24/25/26/28/29) require exactly
  the allowed `saved_items` / `tracked_products` / `users` row delta and nothing else.
- `append_rubrics.py` — the one-shot script that appended `verifier_path` +
  `judge_rubric` to `tasks.jsonl` (five contributor keys byte-identical, no answer key).
- `tests/` — `_support.py` (real-seed snapshots + sqlite mutations + agent_demo-shaped
  hand-written trajectories) and `test_verifiers.py` — honest PASS x30, no-op FAIL x30,
  wrong-answer FAIL x30, shortcut FAIL x28 (tasks 0/3 are homepage-surface by design,
  documented), read-only DB tamper FAIL x22, stateful state-mismatch/collateral FAIL
  x16, package tampering FAIL x7. No docker, no LLM.

Run the tests from the agent_demo env:

    cd agent_demo && uv run python -m pytest ../sites/google_shopping/verify/tests -q

Live verification signature (per task):

    python sites/google_shopping/verify/verify_N.py --run_dir runs/N \
        --initial_db runs/N/initial.db --after_db runs/N/after.db --no_llm True

Exit 0 = PASS, 1 = FAIL; JSON verdict `{task_id, pass, reason, evidence[]}` on stdout.

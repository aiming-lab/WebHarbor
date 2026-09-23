# Imgur — deterministic grading contract

Reviewer-authored grading artifacts for the 30 benchmark tasks in `../tasks.jsonl`.
Every verdict is decided by `--no_llm True` deterministic checks; the LLM helpers in
`verify_lib.py` are advisory only.

Layout:
- `verify_lib.py` — shared fail-closed harness: trajectory identity gates (task_id,
  `agent_done`, non-empty answer, same-origin loopback URLs, decodable PNG screenshots),
  navigation gates (path / search-with-params matchers), affirmative token/phrase/count
  matching with Imgur's compact K-labels (`192K`, `61.8K`) and comma-grouped counts
  (`2,303,068`), SQLite snapshot validation bound to the frozen seed
  (schema sha256 `6364bf3f…`, 14-table counts incl. posts 252 / users 3796 /
  comments 8860 / media 486 / tags 380, full rows digest `26ba5fa5…`, benchmark user
  identities), and the fail-closed CLI runner.
- `verify_0.py` … `verify_29.py` — one verifier per task; ground truth is HARDCODED
  inside each file (never in `tasks.jsonl`). Read-only tasks require every table
  row-identical before/after; stateful tasks (6/7/8/9/10/18/19/20/21/27) require
  exactly the allowed `favorites` / `votes` / `comment_votes` / `comments`(+posts
  comment_count) / `follow_user` / `follow_tag` / `users.bio` / registered-user /
  uploaded-post(+media) row delta and nothing else.
- `append_rubrics.py` — the one-shot script that appended `verifier_path` +
  `judge_rubric` to `tasks.jsonl` (five contributor keys byte-identical, no answer key).
- `tests/` — `_support.py` (real-seed snapshots + sqlite mutations + agent_demo-shaped
  hand-written trajectories) and `test_verifiers.py` — honest PASS x30 (plus the
  task-10 nested-comment and task-16 K-label variants), no-op FAIL x30, wrong-answer
  FAIL x30, shortcut FAIL x28 (tasks 24/28 are homepage-surface by design, documented),
  read-only DB tamper FAIL x20, stateful state-mismatch/adversarial-delta FAIL x20,
  package tampering FAIL x7. No docker, no LLM.

Contract notes:
- Task 10 ('the comment written by LitterBoxKing') — the post carries four comments by
  that member (one top-level, three nested replies). The verifier grades against the
  actually-voted comment's frozen facts (final-state semantics), so every legal reading
  passes and voting a different author's comment FAILs.
- Task 24 says 'visible on the first screen of the feed'; a viewport cannot be graded
  deterministically, so the verifier grades the first PAGE of the Most Viral feed
  (the contributor's documented reading) and the reviewer flags the wording for a
  fix-round re-anchor. The frozen numbers are page-1 stable.

Run the tests from the agent_demo env:

    cd agent_demo && uv run --with pytest python -m pytest ../sites/imgur/verify/tests -q

# Instructure — deterministic grading contract

Reviewer-authored grading artifacts for the 30 benchmark tasks in `../tasks.jsonl`.
Every verdict is decided by `--no_llm True` deterministic checks; the LLM helpers in
`verify_lib.py` are advisory only.

Layout:
- `verify_lib.py` — shared fail-closed harness: trajectory identity gates (task_id,
  `agent_done`, non-empty answer, same-origin loopback URLs, decodable PNG screenshots),
  navigation gates (resource-hub listings with their exposed Product / Org Type / Topic
  filters via `navigated_listing_with_filter`, the scored search with its `srch` param,
  detail paths, the events filter, careers, leadership, newsroom, press archive, FAQ,
  account and form surfaces), affirmative token/phrase/count matching (thousands-group
  tolerant `5,100`, K-label tolerant `$150K`, month-form tolerant `Sep 22, 2026`),
  SQLite snapshot validation bound to the frozen seed (schema sha256 `b41759c7…`,
  16-table counts incl. resources 700 / events 39 / jobs 43 / news_items 34 / faq_items 21
  / leaders 10, full rows digest `49aa8691…` — refreshed through the audit round (the fix round's
  seed rebuild, the connecticut stat-line backfill, the body-asset pass and the hero
  href fix; byte-identical across two clean rebuilds, benchmark user identities), and the
  fail-closed CLI runner.
- `verify_0.py` … `verify_29.py` — one verifier per task; ground truth is HARDCODED
  inside each file (never in `tasks.jsonl`). Read-only tasks require every table
  row-identical before/after; stateful tasks (18/20/21/22/23/24/25) require exactly the
  allowed `saved_resources` / `users`+`saved_resources` / `users` profile /
  `webinar_registrations` / `demo_requests` / `contact_messages` row delta and nothing
  else.
- `append_rubrics.py` — the one-shot script that appended `verifier_path` +
  `judge_rubric` to `tasks.jsonl` (five contributor keys byte-identical, no answer key).
- `tests/` — `_support.py` (real-seed snapshots + sqlite mutations + agent_demo-shaped
  hand-written trajectories; the seed DB is fetched once from the review container or
  `INST_TEST_SEED_DB`) and `test_verifiers.py` — honest PASS x30 (task 24 simulates the
  compliant post-fix state, see below), no-op FAIL x30, wrong-answer FAIL x30, shortcut
  FAIL x28 (tasks 7 and 26 are homepage-surface by design and their homepage shortcut
  PASSES, documented), read-only DB tamper FAIL x46, stateful state-mismatch and
  wrong/collateral-delta FAIL x16, package tampering FAIL x8. No docker required at run
  time (the seed snapshot is cached), no LLM. (Round 1 graded task 24's live honest run
  FAIL against the then-broken contact form; the fix round turned it into a live PASS
  with the same contract.)

Contract notes:
- Task 24 (Contact Us form): round 1 found every valid `POST /contact-us` returning
  HTTP 500 (`contact_us_submit` passed `state=` to `ContactMessage`, which has no `state`
  column); the fix round (commit 9f1cc54e) dropped the argument and the live honest run
  now PASSES (flash + one `contact_messages` row, source "Contact Us"). The verifier
  contract never changed.
- Task 15 (newsroom Region filter): round 1 found the Region radios inert (no submit
  control); the fix round (commit 766b75c2) added a Filter Results button, so
  `/news?region=Europe` (3 rows) is the natural surface. The navigation gate accepts
  both the filtered URL and a plain `/news` visit.
- Tasks 3, 6: the first business webinar and the events tiles render the
  upstream-truncated titles with an ellipsis (`…`); the verifiers grade on the
  distinctive title prefixes so both the truncated listing form and the full detail
  form pass.
- Task 9: the employment type is not printed on the job row; it is proven by applying
  the Employment Type filter (FullTime) and seeing the role remain. The verifier
  accepts FullTime / Full Time / Full-Time forms.

Run the tests from the agent_demo env:

    cd agent_demo && uv run python -m pytest ../sites/instructure/verify/tests -q

Drive one task with the agent and grade it:

    uv run python agent_demo/agent.py --tasks_file sites/instructure/tasks.jsonl \
        --task_id "Instructure--0" --url http://localhost:40077/ --out_dir runs/0
    uv run python agent_demo/eval_judge.py --run_dir runs/0 --verifier True

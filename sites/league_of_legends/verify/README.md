# league_of_legends — reviewer grading contract

Authored by the reviewer (review-env skill, Step 6) on top of the contributor's 30-task
`tasks.jsonl`. Same contract as the hardened reviewer suites
(`sites/merriam_webster/verify/`, `sites/chess_com/verify/`,
`sites/google_shopping/verify/`, `sites/imgur/verify/`, `sites/instructure/verify/`).

## Layout

- `verify_lib.py` — shared fail-closed harness: trajectory identity gates (task_id,
  `agent_done`, non-empty answer, same-origin loopback URLs on the start port,
  decodable PNG screenshots), league_of_legends navigation gates (the `/champions/`
  roster with its `role` / `difficulty` / `sort` / `q` filter controls, champion detail
  paths, `/news/` with `page` pagination, category listings, `/patch-notes/`, article
  paths, `/search?q=`, `/how-to-play/`, `/login/`, `/signup/`, `/account/`,
  `/account/profile`), tolerant answer matching (whole-word phrases, thousands-group
  counts, cooldown ladders in order, ISO/month-name/`m/d/yyyy` dates, champion-name
  forms with apostrophe/dot/join/possessive tolerance), SQLite snapshot validation
  bound to the frozen seed (schema `f7dc0165…`, 8-table counts, benchmark user
  identities, rows digest `78493466…`), and the fail-closed CLI runner
  (`--run_dir/--initial_db/--after_db/--container/--no_llm`). LLM helpers are
  advisory-only; verdicts are `--no_llm` decided.
- `verify_0.py` … `verify_29.py` — one verifier per task; ground truth is HARDCODED
  inside each file (never in `tasks.jsonl`). Read-only tasks require every table
  row-identical before/after; stateful tasks (21, 22, 23, 24, 25) require exactly the
  allowed `favorite_champions` / `bookmark_articles` / `users` row delta and nothing
  else.
- `append_rubrics.py` — string-insertion writer for `verifier_path` + `judge_rubric`
  into `tasks.jsonl` (the five contributor keys stay byte-identical, no answer key).
- `tests/` — `_support.py` + `test_verifiers.py` (pytest; no LLM, no live container
  required — the seed snapshot is cached).

## Running

```bash
# deterministic verdict for one task run (agent_demo env provides simpleArgParser)
uv run python sites/league_of_legends/verify/verify_0.py \
    --run_dir runs/00 --initial_db runs/00/initial.db --after_db runs/00/after.db \
    --no_llm True

# full contract tests (fetches the seed from the review container on first use,
# or uses sites/league_of_legends/instance_seed/, or LOL_TEST_SEED_DB)
cd agent_demo && uv run python -m pytest ../sites/league_of_legends/verify/tests -q
```

## Contract notes (design decisions)

- Task 13 ("champions changed in both 26.19 and 26.18"): the accepted "changed in
  both" set is hardcoded to champions with a named change entry in both articles —
  balance/QoL/ARAM/Classic change blocks (Master Yi, Kassadin, Nasus, Bard, Zeri,
  Nautilus) plus the Classic section's explicit NEW champion introductions (Fiora,
  Galio, Poppy, Shyvana). Skin mentions and incidental prose mentions do not count.
  The answer must name ≥2 of these AND describe one specific 26.18 change for one of
  the champions it named (per-champion 26.18 change facts are hardcoded). This
  tolerates the article's multi-section structure (Champions / Classic / Arena /
  ARAM: Mayhem) without accepting off-article recall.
- Task 16 (external esports cards): the answer must state the cards open as
  external links. The trajectory gate only requires the `/news/esports/` listing;
  clicking through to the real upstream site is neither required nor rewarded (the
  mirror renders the external badge and `target=_blank`, matching upstream's form).
- Task 20 (alice's favorites + skin counts) is read-only but login-gated: the
  verifier requires the `/login/` visit with the demo email entered and the
  account/favorites surface opened, and every table row-identical before/after.
- Task 24 allows exactly one profile row change (summoner name + region) and rejects
  any collateral field edit; task 25 allows exactly one new users row and requires
  zero favorite/bookmark rows for the new account.
- The stateful row-delta assertions key on the full row tuples in column order
  (`favorite_champions`: `(id, user_id, champion_id, added_date)`;
  `bookmark_articles`: `(id, user_id, article_id, added_date)`), so a delta that
  touches the wrong champion/article/user fails.

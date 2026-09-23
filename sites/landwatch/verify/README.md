# LandWatch — deterministic grading contract

Reviewer-authored grading artifacts for the 30 benchmark tasks in `../tasks.jsonl`.
Every verdict is decided by `--no_llm True` deterministic checks; the LLM helpers in
`verify_lib.py` are advisory only.

Layout:
- `verify_lib.py` — shared fail-closed harness: trajectory identity gates (task_id,
  `agent_done`, non-empty answer, same-origin loopback URLs, decodable PNG
  screenshots), navigation gates (state/city/county/region/category sub-paths with
  price / parcel-size filter segments and `?sort=` params, listing detail pages,
  find-agent directory, agent profiles, log-in / register / account pages), money /
  acreage / count / date matchers, SQLite snapshot validation bound to the frozen
  seed (schema sha256 `bbe897be…`, 14-table counts incl. listings 436 / agents 313 /
  counties 318 / cities 377 / users 4 / favorites 18 / saved_searches 7 /
  inquiries 3 / sessions 0, full rows digest `f7de5566…`, benchmark user identities
  and password hashes), and the fail-closed CLI runner.
- `verify_0.py` … `verify_29.py` — one verifier per task; ground truth is HARDCODED
  inside each file (never in `tasks.jsonl`). Read-only tasks require every table
  row-identical before/after (sessions included: no login happens on them); login
  tasks allow exactly the `sessions` delta; stateful tasks require the exact allowed
  row delta and nothing else (task 11 `saved_searches` +1 with the h1-derived name,
  task 12 exactly the Montana row removed, task 13 exactly one `inquiries` row for
  pid 427843237 whose message asks about soil, task 26 alice's `users.phone` update,
  task 27 exactly one `users` row with the frozen registration hash).
- `append_rubrics.py` — the one-shot script that appended `verifier_path` +
  `judge_rubric` to `tasks.jsonl` (five contributor keys byte-identical, no answer key).
- `tests/` — `_support.py` (real-seed snapshots + sqlite mutations + agent_demo-shaped
  hand-written trajectories) and `test_verifiers.py` — honest PASS ×30, no-op FAIL
  ×30, wrong-answer FAIL ×30, shortcut FAIL ×28 (tasks 17/18 are homepage-surface by
  design, documented below), read-only DB tamper FAIL ×23, stateful mismatch /
  wrong-row / wrong-password / over-removal / collateral-delta FAIL ×18, package
  tampering (task-id mismatch, off-site URL, broken screenshot, undone trajectory,
  tampered seed, missing DB, foreign schema) FAIL ×7 — all green in the agent_demo env.

Contract notes:
- Task 16 (Florida + Waterfront): the sidebar Property Types facet links to the
  nationwide `/waterfront-property` page (they drop the state context; upstream
  preserves it as `/florida-land-for-sale/waterfront-property`). The verifier grades
  the task's stated question — how many waterfront land listings FLORIDA has — and
  requires navigation to the state+type results page. The reviewer flagged the facet
  behavior for the contributor's fix round; once the facet preserves the state the
  natural click path satisfies the same gate with no verifier change.
- Task 20 (david's saved properties): the task asks the agent to list all saved
  properties "so I can tell you which one to remove" — the removal is contingent on
  a user choice that the benchmark never supplies, so the gradeable deliverable is
  the complete list. The verifier requires all six titles and accepts either an
  await-instruction state (favorites unchanged) or an over-eager single removal
  (exactly one favorite row gone); anything else FAILs.
- Tasks 17/18 read homepage surfaces, so a homepage-only trajectory with the correct
  facts is the honest path (their shortcut tests assert PASS by design).
- Task 11's stored name comes from the results-page h1, which currently renders the
  category label plus 'Land for Sale' (i.e. 'Hunting Land Land for Sale - 1-7 of 7
  Listings'; see the h1-duplication finding). The verifier accepts both that and the
  de-duplicated spelling, so the contributor's fix needs no verifier change.
- The wide listing cards render states as two-letter codes ('MN', 'GA', 'WV'), so the
  matchers for tasks 2, 15 and 18 accept either the full state name or the card's code.
- The homepage location search resolves locale names before falling back to scored
  listing search, so a title query like 'Tucked into the Hill Country' lands on the
  Hill Country locale page (same for '3D Mountain Ranch' -> Round Mountain). The
  honest paths for tasks 5 and 22 therefore go through the county/state results the
  tasks name (Burnet County / Colorado + Acres sort); no task depends on the
  title-search fallback.

Round-2 contract refresh (fix commit 29519fc9, "Fix reviewer findings F1-F6"):
the seed's description/region-name cleanup changes the row content but no table
counts; SCHEMA_SHA256 is unchanged (bbe897be...) and SEED_ROWS_SHA256 is
re-frozen to e93470d00bed9c78e6fc07f4e0446c9601148e4c5126ca1e27b3903d7e5f315f
(independently recomputed from a fresh seed build; listings
digest 7bd971eb..., regions digest 692092dc...). The F2 h1 dedup changes the
T11 stored name to "Hunting Land for Sale - 1-7 of 7 Listings"; the verifier
keeps accepting both spellings and the tests' honest fixture now mirrors the
new form. All counts, users, hashes and every other ground truth are
unchanged; 167/167 tests green against the re-frozen seed.

Run the tests from the agent_demo env (the seed snapshot cache is
`sites/landwatch/instance_seed/landwatch.db`, materialized from the deterministic
build; the tests skip when it is absent):

    cd agent_demo && uv run --with pytest python -m pytest ../sites/landwatch/verify/tests -q

Audit-round contract refresh (dead-link fix, URLs only): two benchmark
saved-search fixtures pointed at filter buckets that do not exist
(alice "Hunting Land under $250K" -> /hunting-property/price-under-249999,
bob "Colorado Ranches over 100 Acres" -> /colorado-land-for-sale/acres-over-100);
both account-page links 404ed. The URLs now target the real buckets
(price-100000-249999 / acres-101-200). Saved-search NAMES — the only
saved-search fact any verifier checks (task 10) — are byte-identical, so only
SEED_ROWS_SHA256 moves (e93470d0... -> b9eec956...); SCHEMA_SHA256, table
counts, users and every task ground truth are unchanged. 167/167 tests green
against the refreshed seed.

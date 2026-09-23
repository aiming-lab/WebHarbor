# LandWatch — deterministic grading contract

Grading artifacts for the 15 depth-redesigned benchmark tasks in
`../tasks.jsonl` (five-key rows: web_name, id, ques, web, upstream_url; no
answer material ever lives in the agent-facing file). Every verdict is decided
by `--no_llm True` deterministic checks; the LLM helper in `verify_lib.py` is
advisory only.

The depth-review round (KEEP 0 / FAIL 30/30 at 6-12 honest steps, 30 tasks
over the 25 ceiling, 8 homogeneity clusters) rebuilt the task set and this
contract together: 30 -> 15 goal-style multi-chain tasks (three-location
compare, double-detail compare, listing + broker due diligence, dual budget
tracks, hunting filter funnel, big-ranch state compare, auction pagination,
region + county drill, broker vetting, buyer favorites round-trip, profile +
saved-search management, new-buyer onboarding with inquiry read-back,
homepage cross-check, waterfront premium check, custom range forms). Runtime
code is untouched: the frozen-seed contract below is byte-identical to the
audit round's.

Layout:
- `verify_lib.py` — shared fail-closed harness: trajectory identity gates (task_id,
  `agent_done`, non-empty answer, same-origin loopback URLs, decodable PNG
  screenshots), navigation gates (location/city/county/region/category sub-paths,
  price / parcel-size / residence / bedroom filter segments, `?sort=` and
  custom `priceMin/priceMax` / `acresMin/acresMax` params, pagination
  `page-2`, listing detail pages, find-agent directory, agent profiles,
  log-in / register / account pages), money / acreage / count / date matchers,
  SQLite snapshot validation bound to the frozen seed (schema sha256
  `bbe897be…`, 14-table counts incl. listings 436 / agents 313 / counties 318
  / cities 377 / users 4 / favorites 18 / saved_searches 7 / inquiries 3 /
  sessions 0, full rows digest `b9eec956…`, benchmark user identities and
  password hashes), and the fail-closed CLI runner.
- `verify_0.py` … `verify_14.py` — one verifier per task; ground truth is
  HARDCODED inside each file (never in `tasks.jsonl`). Read-only tasks
  (0-8, 12, 13, 14) require every table row-identical before/after
  (sessions included: no login happens on them). Stateful tasks require the
  exact allowed row delta and nothing else:
  - task 9 (bob buyer session): sessions +1 with bob's deterministic token;
    favorites net +1 for the kept candidate (pid 428212638 — both candidates
    favorited, the smaller one removed); saved_searches +1 with the
    h1-derived name 'Hunting Land for Sale - 1-7 of 7 Listings' (the
    pre-dedup double-'Land' spelling is accepted too) and URL
    /hunting-property/price-250000-499999.
  - task 10 (alice profile + preference): sessions +1; users exactly alice's
    phone -> (512) 555-0164 with her name unchanged; saved_searches +1 with
    name 'Montana Land for Sale - 1-8 of 8 Listings', URL /montana-land-for-sale.
  - task 11 (new-buyer onboarding): users +1 with the frozen registration
    hash of LandBuyer2026!; sessions +1 with the new user's deterministic
    token; favorites +1 for pid 424029660 ('43 ac Iron Rapids Ranch');
    inquiries +1 for pid 427843237 (Prime Ohio Farmland) whose message asks
    about soil, with the submitter's name and email.
- `tests/` — `_support.py` (real-seed snapshots + sqlite mutations +
  agent_demo-shaped hand-written trajectories) and `test_verifiers.py`:
  honest PASS x15, no-op FAIL x15, wrong-answer FAIL x15, homepage-shortcut
  FAIL x15 (every redesigned task grades a surface beyond the homepage, so
  the retired set's 'homepage-surface by design' exceptions are gone),
  read-only DB tamper FAIL x12, stateful mismatch / wrong-row / cross-user /
  over-eager / wrong-password / missing-write FAIL x16, stateful collateral
  FAIL x3, package tampering (task-id mismatch, off-site URL, broken
  screenshot, undone trajectory, tampered seed, missing DB, foreign schema)
  FAIL x7 — all green in the agent_demo env.

Contract notes:
- Task 12 (homepage overview) pins each featured-carousel triple (price,
  acreage, state) to a window after its price, in addition to the carousel
  order check, so the West Virginia / Virginia pairing cannot be swapped.
- Task 13 requires the explicit comparison wording ('Blake Ranch costs more')
  and an affirmative not-waterfront statement, so a reversed claim cannot
  pass on token presence alone.
- Task 14 accepts the custom price / size forms with or without thousands
  separators in the query string (`priceMin=100000` / `100,000`); the answer
  gates pin the counts (38 / 0 within budget, 71 in the size band).
- The saved-search names graded in tasks 9 and 10 come from the results-page
  h1 the Save Search button captures verbatim; the frozen values are quoted
  in the verifier docstrings.

Run the tests from the agent_demo env (the seed snapshot cache is
`sites/landwatch/instance_seed/landwatch.db`, materialized from the
deterministic build; the tests skip when it is absent):

    cd agent_demo && uv run python -m pytest ../sites/landwatch/verify/tests -q

History:
- Audit round (squashed site commit): 30-task contract, 167-test suite.
- Dead-link fix: saved-search URL buckets repaired; SEED_ROWS_SHA256
  re-frozen e93470d0… -> b9eec956… (names unchanged).
- Depth redesign (this round): tasks 30 -> 15, verifiers rebuilt for the new
  chains, tests re-scoped to the new contract. SCHEMA_SHA256, SEED_COUNTS,
  SEED_USERS, both seed digests and every benchmark-user identity are
  unchanged from the audit round (runtime code untouched).

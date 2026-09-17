# PR #87 independent review and remediation audit

## Scope

Seven independent review contexts examined PR #87 head `7d3131cbf5c7ad086aef334b7b384cbfdfe8ca1a` against base/current main `7269134e9db9d10b1a6ac321797be51c72bb1a36`. Raw reports are retained outside the repository under `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr87-agents/reports/`.

The system date during review is September 8, 2026. The source-capture timestamps on September 7, 2026 are contemporaneous. One review agent classified those timestamps as future-dated; direct system timestamps, Git commit timestamps, and live source validation disprove that finding.

## Agent findings and dispositions

| Review agent | Findings on original PR head | Verification and disposition |
|---|---|---|
| Security and state integrity | Committed Flask secret, session fixation hardening absent, anonymous logout, unbounded search input, seeded public reviews incorrectly owned and displayed as Alice, nondeterministic cold-seed credentials/timestamps, and inconsistent watchlist return handling. | Confirmed in `sites/rotten_tomatoes/app.py` and `seed_data.py`. Replaced the secret with environment/random configuration; added request/cookie limits, SQLite foreign keys, robust session loading and session clearing; required authentication for logout; bounded and validated query values; made watchlist returns local and explicit; separated seeded review display identity from private account ownership/deletion; and fixed seed hashes/timestamps. |
| Application, data, and source authenticity | Source hashes lacked raw capture bodies; TV data contained two `/celebrity/undefined` URLs; populated-DB gating was too weak; cold seed was byte-nondeterministic; content snapshots lacked strict validation; search/sort inputs and null/tie ordering were weak; image downloading lacked redirect/type/size/hash enforcement. | Corrected undefined URLs to `null`; added strict catalog/content validation; added complete immutable populated-seed checks; made cold generation byte-deterministic; added explicit indexes in deterministic order; bounded search and validated every filter/sort; added stable null/tie ordering; and hardened image downloading. Independent live audit returned HTTP 200 for all 270 official movie URLs and exact fact matches for all 14 task-critical pages. All 3,343 catalog-bound images match expected SHA-256 values. |
| Task and data quality | Seven tasks are substantively multi-step and answerable. The account tasks require reset isolation. R0 must distinguish subscription platform from viewing-offer provider. R18 requires complete Kevin Feige producer candidate discovery and missing-date handling. | Retained all seven task objectives and port `40021`. Verifiers now derive all answers from the supplied initial database. R0 requires the exact Sci-Fi/Netflix subscription filter and all eight candidate details. R18 accepts either all four eligible details or the complete Kevin Feige filmography plus winning detail. Stateful tasks require exact initial state and bounded post-state. |
| Verifier robustness | Original verifiers trusted agent-writable DOM sidecars, used hard-coded facts insufficiently bound to the database, allowed incomplete candidate sets, had weak action causality and form-field binding, and contained large parser-specific tests that did not establish trusted execution. | Replaced all seven production verifiers and their common library. Current verifiers enforce task identity, successful completion, same-origin navigation, valid screenshot sequences, exact filter/search paths, click transitions, required input sequences, facts derived from the initial database, complete read-only database equality, unchanged schema, and exact bounded state changes. Added adversarial controls for wrong task IDs, incomplete runs, external origins, missing/tiny screenshots, answer-only trajectories, missing candidate visits, incorrect/extra answers, unrelated writes, and missing form inputs. |
| UI, responsive behavior, and accessibility | Mobile header margin, misleading hero Watchlist link, missing review label associations, inconsistent TV result count, and incomplete current-page/menu semantics. Potential 768 px crowding and navigation overflow required browser verification. | Removed the mobile header gap; converted authenticated hero Watchlist to a CSRF-protected POST control; added form associations, profile `aria-current`, explicit navigation-menu text, and TV result counts. Browser checks at 320, 390, 768, and 1440 px found no page-level overflow, broken images, image hotlinks, missing image alt attributes, console errors, or page errors across public and private routes. |
| Integration and assets | Site order and port `40021` were correct, but site README/evidence was stale; the HF asset PR remained unmerged; official clean build was unverified; cache was not revision-scoped; fetch did not assert archive completeness; runtime depended on an old mutable seed archive. | Merged HF dataset PR #55, replaced the redundant seed-bearing RT archive through HF PR #58, and pinned immutable revision `8f06eba81b2d1cdf62c8c17c9036850d9a6b9c32`, which contains all 22 archives. The final RT archive is media-only with SHA-256 `273a4e674431fbb4cd802d54b5945fb8f3fac225443e0e7b39700dae990b0926`; the database is generated from code. Asset cache is revision-scoped and extraction asserts archive counts. Rotten Tomatoes now explicitly requires images/external cache and generates its deterministic database during Docker build. A clean official Dockerfile build was completed with both OSU and Rotten Tomatoes host seed directories absent. |
| Evidence integrity | Original evidence disclosed that the PR was Draft, accepted runs were zero, the official Dockerfile build was not verified, runs were assisted/guided, and many machine-readable artifacts were stale or contradictory. | Removed the overlapping historical generated evidence package and replaced it with this exact-head audit. Reran source, application, verifier, browser, responsive, route, asset, build, health, restart, reset, and reset-all validation. New raw browser runs, database snapshots, screenshots, source receipts, route results, responsive results, and archive hashes are retained under `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr87-fixes/`. |

## Ground truth for reviewed tasks

| Task | Result derived from the generated seed |
|---|---|
| `RottenTomatoes--0` | `War Machine`; `Mar 6, 2026`; Patrick Hughes and James Beaufort |
| `RottenTomatoes--3` | Shared producers: Emma Thomas and Charles Roven; Oppenheimer `Nov 21, 2023`; The Dark Knight `Jun 14, 2010` |
| `RottenTomatoes--8` | New `testreviewer@test.com` account with display name `Test Reviewer`; persisted credential and authenticated account access |
| `RottenTomatoes--9` | Bob's display name changes exactly to `Robert Clark` |
| `RottenTomatoes--11` | Only `Deadpool & Wolverine` is removed from David's watchlist; 3 movies remain |
| `RottenTomatoes--14` | `Oddity`; Carol's personal score is `5/5` |
| `RottenTomatoes--18` | `Spider-Man: Brand New Day`; audience score `97%`; Release Date (Streaming) is not listed |

## Validation

- Application, source, security, deterministic-seed, image, migration-recovery, and environment suite: 56 tests PASS with `ResourceWarning` promoted to errors.
- Production verifier adversarial suite: 10 test methods PASS across all seven tasks and controls.
- Actual Playwright UI executions from fresh databases: 7/7 PASS.
- Production verifier results for those browser runs: 7/7 PASS.
- Responsive/public/private checks at 320, 390, 768, and 1440 px: 56/56 PASS.
- Full local route crawl: 4,190/4,190 HTTP 200, covering all movie, person, TV, feature, curated, account-entry, search, and browse routes.
- Official source audit: 270/270 movie URLs HTTP 200; 14/14 task-critical page facts match tracked data.
- Catalog image audit: 3,343/3,343 local poster, hero, and person images match tracked SHA-256 values.
- Pinned HF assets: 22/22 archives downloaded, extracted, checked, and SHA-256 recorded.
- Repeated clean Rotten Tomatoes seed generation: byte-identical.
- Clean official Docker build with generated seed directories absent: PASS; final image `sha256:b645d600d40bbccb3007c113f253a028e08423a3703721ca99b3b349a23fd933`.
- Container startup: 22/22 sites alive; 22/22 roots HTTP 200.
- Dirty-state restart: registered fifth user persisted and runtime DB hash remained dirty.
- `/reset/rotten_tomatoes`: exact seed bytes restored and user count returned to four.
- `/reset/osu`: PASS.
- `/reset-all`: 22/22 PASS.

## Evidence

- Agent reports: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr87-agents/reports/`
- Browser trajectories, screenshots, initial/after databases, and verifier outputs: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr87-fixes/e2e/`
- Responsive results and screenshots: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr87-fixes/responsive/`
- Full route crawl: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr87-fixes/route-crawl/results.json`
- Live official-source audit: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr87-fixes/source-audit/live-source-audit.json`
- Pinned archive hashes: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr87-fixes/asset-archives.json`

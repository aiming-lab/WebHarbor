# PR #63 independent review and remediation audit

## Scope

Seven independent review contexts examined PR #63 head `4890c86374daea2fa29455b919b0ab55095efc3d` against its original base `438a029c04d86b22c710ad5d985d1d1491d2cb98`. Integration was also checked against current main `e911a6adb28d04397ed30d8293e77b0c62a112d5`. Raw reports are retained outside the repository under `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr63-agents/reports/`.

## Agent findings and dispositions

| Review agent | Findings on original PR head | Verification and disposition |
|---|---|---|
| Security and state | Hard-coded secret, login/bookmark open redirects, GET logout, news GET writes, unconstrained/dangling bookmarks, no bookmark uniqueness constraint, malformed session crash, weak username normalization, and unbounded notes. | Confirmed in `sites/osu/app.py`. Fixed with environment/random secret, local redirect validation, POST logout, read-only news GET, bookmark type/object validation, 500-character notes, a database unique constraint with race handling, robust user loading, lowercase usernames, request limits, session rotation, and SQLite foreign keys. |
| Task and data | Task 1 conflicted with the number of seeded team rows; several tasks were answerable from prior knowledge; task 9 accepted incomplete degree types; task 17 did not ask for a precise output; many valid-answer aliases increased grading ambiguity. | Rewrote all 20 tasks around explicit visible routes, filters, multi-field facts, and comparisons. Task 1 now explicitly asks for the About-page display. Task 9 requires all three Engineering degree types. Task 17 requires exact article title and author. Multi-entity tasks bind each number/value to its entity. |
| Verifier robustness | URL substring checks accepted external or wrong paths; required search/filter/topic steps were missing; negated answers and unrelated numbers could pass; `--no_llm` removed semantic enforcement; the synthetic selfcheck omitted adversarial cases. | Replaced the common verifier library and all 20 verifiers with same-origin exact path/query/order checks, visible-link transition checks, exact task IDs, non-empty output, negation-aware facts, entity-bound comparison values, and complete database equality for every read-only task. Added positive and adversarial tests for wrong task IDs, answer-only runs, external origins, database mutation, missing filters, negation, and swapped values. |
| UI and responsive behavior | Fixed two-column detail layouts overflowed on mobile; header/search/top bar could overflow; navigation lacked an overflow affordance and current-page semantics; forms lacked clear labels; focus styling was incomplete; cards with inline flex layouts could overflow; the mirror contained no real photographic assets. | Added responsive detail layout classes, mobile header stacking, horizontally scrollable navigation, `min-width:0` and wrapping protections, fixed grid breakpoint ordering, accessible search names, current-page `aria-current`, and focus-visible styles. Crawled 19 photographs from official Ohio State web properties, preserved source-page URLs and hashes in `sites/osu/image_sources.json`, and integrated the photographs into home, section, card, and detail layouts. Automated tests cover 320 px, 390 px, and 1440 px layouts. |
| Integration | The PR was based on a 17-site tree while current main has 20 sites; OSU collided with IKEA at `40016`; docs and asset pins were stale; clean `scripts/build.sh` would reject OSU because it intentionally has no HF seed bundle. | Merged current main locally, retained all existing sites, appended OSU as site index 20 on `40020`, exposed `40000-40020`, and updated all documentation. Added `.build-generated-seed` support for the deterministic OSU database and `.requires-images` enforcement for its HF-hosted image bundle. The pinned HF revision now contains `osu.tar.gz`. |
| Application and data model | Import-time seed recursion under `python app.py`, broad partial-state seed gate, wall-clock event filtering, nondeterministic seeded user hashes/timestamps, missing bookmark referential validation, and brittle phrase search. | Added module-safe seed resolution, partial-database failure, fixed benchmark time, stable seeded password hash and timestamps, exact bookmark validation, and token-overlap ranked global search. The same source now generates byte-identical OSU databases in repeated clean runs. |
| Test evidence | The original selfcheck used fabricated trajectories only; it did not run the site, verify rendered facts, test external-origin/path spoofing, detect database mutations, validate responsive pages, or prove a current-main Docker build. | Replaced the original selfcheck with a complete unittest entry point and added HTTP, seed, integration, positive verifier, and adversarial verifier suites. Actual Playwright task trajectories, screenshots, and before/after databases were produced for all 20 tasks. A clean build without a host OSU seed and a 21-site container smoke/reset test were completed. |

## Validation

- Python compilation, shell syntax, Ruff fatal/undefined-name checks, and `git diff --check`: PASS.
- OSU HTTP, seed, image provenance, integration, and verifier suite: 24 tests PASS.
- Actual Playwright completion from fresh databases: 20/20 PASS.
- Deterministic verifier results for those browser runs: 20/20 PASS.
- Responsive checks at 320 px, 390 px, and 1440 px: 45/45 PASS with no page-level horizontal overflow.
- Repeated clean OSU seed generation: byte-identical.
- Official-image provenance manifest: 19/19 assets present, non-empty, and SHA-256 verified.
- Hugging Face dataset PR #56 merged; pinned revision `db9c73e62d853ed91f6152b5b7105571502b7e07` contains `osu.tar.gz`.
- Pinned HF `osu.tar.gz` download, deterministic tar SHA-256 (`1fc684a25890262137714b56577cd8bcbe0c5a867c65da12f3d45ab7662949f7`), and extraction: PASS.
- Clean Docker build with `sites/osu/instance_seed` absent from the build context: PASS.
- Container health: all 21 sites alive and all 21 site roots returned HTTP 200.
- `/reset/osu`: PASS; runtime and seed SHA-256 values match.
- `/reset-all`: PASS for all 21 sites.

## Evidence

- Agent reports: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr63-agents/reports/`
- Browser trajectories, screenshots, and verifier outputs: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr63-fixes/e2e/`
- Responsive results and screenshots: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr63-fixes/responsive/`
- Official image source pages, source URLs, dimensions, and hashes: `sites/osu/image_sources.json`

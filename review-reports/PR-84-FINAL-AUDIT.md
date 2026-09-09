# PR #84 independent review and remediation audit

## Scope

Sixteen independent review contexts examined PR #84. The original eight-agent review used exact PR head `b28d13b0056c8aac2be5fa08826ab8d64b5c0160` and original base `7269134e9db9d10b1a6ac321797be51c72bb1a36`. Integration was checked against current main `5e279ad1f925987e51f878a461e876064ea77635`, which already includes Rotten Tomatoes. Four agents reviewed the first remediation, and four completion agents audited the subsequent fixes. Raw reports are retained outside the repository under `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr84-agents/reports/`.

## Agent findings and dispositions

| Agent | Scope | Finding | Verification and disposition |
|---:|---|---|---|
| 1 | Security and state | Partial seed state, fixed secret, unbounded profile/form inputs, lost login return target, short deterministic share tokens, and repeatedly exposed seller confirmation. | Confirmed in `app.py` and `seed_data.py`. Added runtime/env secret, request/session limits, strict persistent-field validation, safe preserved login return, longer tokens, one-time confirmation, registration/save race handling, SQLite foreign keys, and versioned atomic seed creation. |
| 2 | Application and data | Asset-dependent silent listing drops, source-price omissions, missing open houses, weak amenity vocabulary, contradictory city filters, permissive public filters, source URL precedence, and non-transactional seeding. | Asset absence now fails; eight refreshed records with source prices are appended without changing reviewed IDs; 19 open houses are seeded; amenity matching covers source variants; city scope is immutable; malformed and duplicate filters return 400; source URLs prefer refreshed records; seed completion is one transaction with `seed_metadata`. |
| 3 | Task ground truth | Ranking evidence was underdocumented; task 11 looked contradictory against the contributor card snapshot; tasks 18–19 lacked committed facts; status wording and task 15 date semantics were ambiguous. | Queried the generated database and complete eligible sets. The apparent task 11 conflict was disproven: the higher card record has captured status `Closed`; the reviewed target is the unique maximum in the local For Sale/Single Family set. Reworded category/date semantics. All targets are now derived from `initial_db`; no committed answer file remains. |
| 4 | Verifiers | URL-only shortcuts, weak filter evidence, incomplete task 16 comparison paths, context-free ratio checks, answer negation/association gaps, 24-byte fake PNG acceptance, synthetic helper-only tests, and incomplete schema comparison. | Replaced target IDs with current-snapshot derivation and exact `Fraction` ranking; required task-mentioned filters and ordered page workflows; required all comparison details; bound ratio context and nearby negation; fully decode every PNG; compare exact schema objects and all rows; execute every verifier end to end in tests. |
| 5 | UI, responsive and assets | Narrow-screen guide, Sell timeline, dashboard/table, dialog, carousel, and Concierge risks; dead modal; missing fallback/focus semantics; external-link and provenance clarity. | Removed dead modal; fixed 320px guide/CTA/timeline layout and 815px dashboard grid; added scrolling dialog rows, short-height filter usability, carousel keyboard/slide semantics and no-JS fallback, dialog focus restoration, Concierge poster/fallback, safer external labels, and local source provenance. |
| 6 | Current-main integration | PR deleted Rotten Tomatoes semantically, reused port `40021`, regressed Docker build blocks and HF pin, retained 22-site docs, and lacked a clean merged build. | Preserved Rotten Tomatoes on `40021`, appended Compass on `40022`, synchronized 23-site registries/docs and `EXPOSE 40000-40022`, retained OSU/RT generation, added Compass generation, merged current-main asset content, and completed a clean 23-site build. |
| 7 | Test evidence | The claimed 222-test and integration evidence was split across versions; tasks 17–20 lacked independent packaged execution; previous image was incremental; reset evidence predated task expansion; several assertions were vacuous. | Replaced stale evidence with one current test suite and real current-image browser runs. Form-label tests now check every visible control. All 19 tasks execute against the packaged container with 209 browser steps and 418 step screenshots. |
| 8 | Provenance and repository hygiene | Runtime asset coverage was not independently proven; raw/source inconsistencies existed; solution-bearing task reports and hundreds of screenshots leaked answers and added 29 MB to Git. | Added `asset_inventory.json` covering exactly 2,907 runtime files and source URLs/hashes; normal build validates it. Removed all solution-bearing `sites/compass/docs/` artifacts and `verify/facts.json`; full browser evidence remains outside the agent-visible repository. |
| 9 | First fixed security/app audit | No blocker/high issue; identified remaining direct-filter consistency and collection JSON validation concerns. | Added strict enum/numeric/boolean/duplicate query validation, deterministic sort fallback, and bounded unique positive collection membership validation. |
| 10 | First fixed verifier audit | Optional target saves could be overly permissive; seller generated columns needed explicit checks; task 17 and workflow ordering were weaker than task wording. | Capped unique optional saves; validated seller row ID/timestamp/reference; required ordered stateful workflows; task 17 now requires Luxury followed by explicit For Sale/Condo/$5M filters. |
| 11 | First fixed UI audit | Sell/Concierge progressive enhancement, narrow dialog/timeline, carousel semantics, dead/fragile controls, and source-link wording required follow-up. | Added static no-JS state, `noscript` explanation, region/slide semantics, Arrow key support, null-safe JS, one-column narrow dialog, responsive timeline/stat blocks, local poster, and explicit external-source wording. Browser checks verify actual layout. |
| 12 | First fixed integration audit | Single-site fetch counted stale full-cache files; extraction lacked path/type constraints; inventory was not a normal build gate; process map needed locking. | Single-site fetch now selects only its archive; archive members are validated; installation uses staged managed-root replacement; host and Docker builds enforce inventory; `_site_procs` has a lock. |
| 13 | Completion security/app audit | Agent and open-house city filters still allowed wildcards, duplicates and unbounded text. | Added one bounded exact city argument parser and regression cases for wildcard, duplicate and oversized values. |
| 14 | Completion verifier audit | Recorder trust cannot cryptographically bind pixels to URLs; identified remaining ordering, ratio context, task 13 language, task 17 qualification, and initial collection uniqueness checks. | Deterministic verifiers cannot authenticate a recorder, so release evidence includes actual Playwright runs. Added ordered confirmation workflows, contextual PPSF matching, explicit second-lowest wording, required task 17 filtering, and initial member-list validation. |
| 15 | Completion UI audit | Reported possible mobile toolbar/guide/Sell issues and accessibility semantics. | Empirical 320/390/815/1440 checks found and drove the guide and dashboard fixes. Added remaining carousel, short-dialog, reduced-motion and label improvements. The final packaged run has zero detected overflow, broken images, page errors or remote runtime media. |
| 16 | Completion integration audit | Stale files could survive extraction; validator accepted unspecified tar member types; inventory paths were not independently constrained. | Extraction now stages validated roots and atomically replaces old managed directories. Only regular files/directories are accepted. Inventory paths must be relative and rooted under the two managed asset directories. Adversarial archive and path-escape tests pass. |

## Implementation results

- Compass is the 23rd site on container port `40022`; Rotten Tomatoes remains on `40021`.
- The generated seed contains 505 listings, 255 agents, 19 open houses, four benchmark users, 24 local regional guides, and a `compass-source-v3` completion marker.
- Eight refreshed source-price records missing prices in the contributor card snapshot are retained after the reviewed 497 IDs, preserving existing task identities.
- All task ground truth and state targets are calculated from the supplied initial SQLite database. Ranking ties fail closed.
- Every current verifier requires exact task identity, local origin, decoded screenshots, completion, task-mentioned filters/workflows, the expected answer semantics, exact schema, and bounded before/after state.
- The agent-visible repository no longer contains the answer-bearing verifier facts or 242 committed review/evidence files.
- `asset_inventory.json` covers 2,907 runtime assets totaling 209,945,248 bytes. Every file is source-mapped, size/hash checked, and format checked.
- HF PR #59 rebased Compass assets onto the current asset main. HF PR #60 replaced the archive with a deterministic media-only bundle. Stale HF PR #53 was closed.
- Pinned HF revision: `070123d74c01a8b29808201be85462fd7d0ec3c4`, containing 23 archives.
- Compass media archive SHA-256: `4af8396785c35db1a5cf57ed5b77e00c8a7b8c484b250707ba64d1936691d8d5`.

## Validation

- Compass application, seed, archive, asset, task and verifier suite: 229 tests PASS.
- Cross-site regression: Rotten Tomatoes 66 tests and 4,143 subtests PASS; OSU 25 tests and 264 subtests PASS; TED 27 tests and 291 subtests PASS.
- Ruff fatal/undefined-name checks and Python compilation for all 43 changed Python files, shell syntax for all shell entry points, Compass JavaScript syntax, and `git diff --check`: PASS.
- Full pinned asset fetch: 23/23 archives validated and extracted.
- Single-site fetch with a populated revision cache: PASS.
- Staged extraction removes stale managed assets: PASS.
- Repeated generated Compass seed in the host environment: byte-identical.
- Clean Docker build with Compass, OSU and Rotten Tomatoes host seed directories absent: PASS.
- Release image: `sha256:cf6fe05b6600e92727816aff018f90d19f18277e8276f6e54a46aaecc34c79af` (4,681,221,472 bytes).
- Packaged-container Playwright execution plus deterministic verifier: 19/19 PASS, 209 browser steps, 418 step screenshots.
- Packaged responsive/browser checks: 140/140 PASS at 320, 390, 815 and 1440 px; zero broken images, page-level overflow, page errors or remote runtime media requests.
- 320×480 filter dialog and JavaScript-disabled Sell fallback: PASS.
- Container startup: 23/23 HTTP-ready; all 23 roots return HTTP 200.
- Ten consecutive Compass resets: PASS; control-plane file descriptors remained 4 before and after.
- `/reset-all`: 23/23 PASS; every runtime seed tree is byte-identical to its `instance_seed` tree after reset.
- Compass container seed/runtime SHA-256: `a21bc6d0f4a1063d1807b4d4b6c2ff4851e99d777cedac6d7070c2f5aa95f257`.

## Evidence

- Raw agent reports: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr84-agents/reports/`
- Packaged task trajectories, screenshots, before/after databases and verifier output: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr84-fixes/docker-e2e/`
- Packaged responsive results and screenshots: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr84-fixes/docker-responsive/`
- Source-backed runtime asset inventory: `sites/compass/asset_inventory.json`

# PR 86 Final Audit

## Scope

This audit covers `aiming-lab/WebHarbor#86`, whose reviewed head was `a2649095bbef7d0fbce011d4510e6ee1cbd08d68`. The PR was reviewed against upstream `main` at `129a274230070abb90b6d4ec209d81a911754ec9`. Eight independent review agents examined security and state, application and data behavior, task ground truth, verifier resistance, UI and responsive behavior, repository and container integration, test evidence, and asset provenance.

The original PR was conflicting with current `main`. Current `main` already assigned internal port `40022` to Compass, so this integration preserves Compass and registers Walmart Careers as the twenty-fourth site on internal port `40023`.

## Agent Findings and Resolutions

| Agent | Review area | Verified findings | Resolution |
| --- | --- | --- | --- |
| 1 | Security and state | `sites/walmart_careers/app.py` used a fixed Flask secret, application contact data was stored in the client session, input boundaries and transaction failure handling were incomplete, and SQLite foreign-key enforcement was connection-dependent. | Added environment/random secret handling, cookie and request-size controls, CSRF protection, strict field limits, per-connection foreign keys, transaction rollback, race handling, and server-side one-time application drafts with ownership and replay checks. |
| 2 | Application and data | Unknown locations could degrade into an unfiltered result set, query semantics were permissive, and profile values could be silently truncated. | Unknown or unsupported locations now return zero results; duplicate and invalid query parameters, facets, sorting, pagination, radii, tabs, and excessive search tokens are rejected; field validation rejects overlong input rather than truncating it. |
| 3 | Tasks and ground truth | Several task verifiers omitted required filter constraints, one task description was ambiguous, and the signed-in email behavior conflicted with one rubric. | Clarified affected task text, enforced every required filter, and derived task targets and candidate sets from the supplied initial database through `verify/ground_truth.py`. |
| 4 | Verifier resistance | Screenshot bytes were not decoded, trajectory URLs could be fabricated, protected schema/catalog rows were not comprehensively checked, stateful verifiers allowed unrelated writes, and several numeric/address checks accepted weak context. | Added complete PNG decoding, loopback origin and port checks, exact nine-table schema hashing, protected-table checks, exact allowed row deltas, required workflow ordering, candidate-detail coverage, and strict contextual matching for addresses, identifiers, confirmation numbers, time, counts, and experience. |
| 5 | UI and responsive behavior | The original implementation overflowed at 320 px, exposed misleading inert controls, and had menu, dialog, table, focus, heading, and reduced-motion defects. | Reworked responsive layout and overlays, added scroll containment and focus treatment, corrected headings and form semantics, honored reduced-motion preferences, and removed non-functional play, pause, carousel, and share controls. |
| 6 | Repository, assets, and Docker | Compass already occupied `40022`; the original asset proposal was not based on current asset `main`; the repository and container registries still assumed 23 sites. | Merged current `main`, retained Compass on `40022`, placed Walmart on `40023`, updated all 24-site registries and port ranges, and pinned assets to revision `65c479f894763f64c6073e0d180ebf542d1d2c02`. |
| 7 | Tests and release evidence | The original tests were predominantly hand-built verifier fixtures and did not cover Flask routes, container behavior, assets, complete schema integrity, or all integration contracts. | Added route, security, state, seed, asset, task-ground-truth, verifier-adversarial, and 24-site integration tests; validated the release image with real browser workflows and control-plane operations. |
| 8 | Asset provenance and classification | Media, icons, and fonts lacked complete machine-verifiable inventories; synthetic benchmark data was not explicitly classified; old documentation and dependency declarations were incomplete. | Added checksummed inventories for 35 downloaded media assets and 27 tracked assets, added provenance documentation, classified jobs/users/applications/tasks as synthetic benchmark data, removed three unused or unverified tracked assets, and pinned runtime dependencies. |

## Additional Verified Fixes

- `sites/walmart_careers/seed_data.py` now constructs a deterministic database in a temporary path and atomically publishes it with seed version `walmart-careers-v2`.
- Seed startup validation protects immutable catalog counts and required benchmark users while permitting legitimate runtime registrations, saved jobs, and applications. Restart preserves runtime state; reset restores the seed.
- `control_server.py` reaps exited direct children and re-parented Flask workers, preventing reset/restart zombie accumulation under PID 1.
- Health checks validate the immutable catalog and required benchmark identities without treating valid runtime rows as seed corruption.
- The release image builds seed databases from tracked deterministic source and does not package tests, verifier test fixtures, development scripts, or answer-bearing browser evidence.
- The Walmart media archive contains 35 files, is 11,458,196 bytes, and has SHA-256 `b84a0072c603225f29e21edfd8f8038fe02a0261a38a60f8e70ed871ea7ce77a`.

## Validation Results

| Validation | Result |
| --- | --- |
| Walmart application, integration, seed, asset, ground-truth, and verifier suites | 297 passed; 16 unittest subtests passed |
| Compass regression suite | 229 passed |
| Rotten Tomatoes regression suite | 66 passed; 4,143 unittest subtests passed |
| OSU regression suite | 25 passed; 264 unittest subtests passed |
| TED regression suite | 27 passed; 291 unittest subtests passed |
| Ruff fatal-error/undefined-name checks | Passed |
| Python byte compilation | Passed |
| Shell syntax and Git whitespace checks | Passed |
| Walmart media inventory | 35 files verified |
| Walmart tracked asset inventory | 27 files verified |
| Compass media inventory in Docker build | 2,907 files verified |
| Release Docker image | `sha256:13df807773246725ab8b1999c03d87b5efb1be0bab8eaaf625bf14d1c31a68f7` |
| Browser execution of all Walmart tasks | 20/20 passed; 106 browser steps; deterministic verifier passed each task |
| Responsive/browser matrix | 21 routes × 5 viewport widths = 105 checks; zero overflow, clipping, broken images, unlabeled controls, page errors, or remote requests |
| Narrow-screen overlays | Four navigation menus and three result popovers remained within the viewport |
| No-JavaScript static behavior | Passed; no misleading media controls remained |
| Release container control plane | 24/24 sites ready; all 24 roots returned successful responses |
| Release reset-all | Passed; all 24 runtime seed trees matched their seed trees |
| Walmart restart and reset | Valid runtime state survived restart; reset restored byte-identical seed state |
| Ten consecutive Walmart resets | Passed; PID 1 file descriptors remained 4 → 4 and zombie count remained 0 → 0 |

## Post-review Navigation Correction

A reported header-navigation defect was reproduced at the 1080 × 397 CSS-pixel viewport represented by the supplied screenshot. Opening Career areas, Brands, and Resources left all three native `details` elements open; clicking outside or pressing Escape did not close them. The live Walmart Careers header was independently checked and kept only one primary menu expanded while closing it on outside pointer interaction and Escape.

`static/js/navigation.js` now provides mutually exclusive header menus, same-trigger close, outside-pointer close, focus-leave close, Escape close with focus restoration, and mutual exclusion with the account menu. Packaged Chromium checks passed at 1080 × 397 and 320 × 480, the 20-task browser/verifier suite remained 20/20 with 106 steps, and the 105-case responsive matrix remained free of overflow, clipping, broken images, unlabeled controls, page errors, and remote requests.

## GitHub Write Policy

No GitHub comment or review was submitted during this audit. The permitted GitHub write operation is limited to pushing the reviewed commit to the existing PR head branch.

# PR 71 Final Audit

## Status

Release candidate validated against original PR head `73eba14579449404abf1efd5cc6b86c7b5507a7a` and upstream `main` `36004932bdf82afbe36dc14e00f66841eccf9946`. The integrated topology has 25 sites; Drugs.com is appended at container port `40024` without changing the existing site positions.

This audit did not post a GitHub comment and does not authorize merging the upstream pull request.

## Review Streams

### Reviewer 1 — security, authentication, authorization, and state integrity

- **Observation:** The original control plane allowed unauthenticated reset/restart operations. Session secrets, login controls, input bounds, transaction behavior, account ownership, anonymous review voting, and SQLite constraints also required review.
- **Verification:** Direct source inspection confirmed public mutation routes in `control_server.py`, process-local concurrency assumptions, anonymous vote-ledger growth, registration commit ordering, weak nullability, and session-cookie data exposure.
- **Remediation:** Every control endpoint now requires a constant-time bearer-token check. Drugs.com has a cryptographically random runtime secret, bounded requests and fields, CSRF on mutations, strict safe redirects, login throttling, a bounded runtime account count, unique site-specific cookie names, optional secure cookies for TLS deployments, authenticated-only bounded helpful votes, ownership-scoped mutations, non-null/check/unique/FK constraints, and an exclusive per-database process lock. Anonymous email and medication-browsing history are not stored in the client cookie.
- **Evidence:** `sites/drugs_com/tests/test_app.py`; authenticated and unauthenticated control-plane tests in `sites/drugs_com/tests/test_integration.py`; final Drugs.com suite: 184 passed.

### Reviewer 2 — application behavior and data consistency

- **Observation:** The original application inferred dosage forms, pregnancy guidance, warnings, storage, overdose behavior, lifestyle interactions, availability, clinical conclusions, and class-wide facts from names or broad classes. Ranitidine, haloperidol, and Janumet records were internally inconsistent.
- **Verification:** Each reported example was checked against `DRUGS_DATA`, `DRUG_CONTENT_OVERRIDES`, route handlers, templates, and generated SQLite rows.
- **Remediation:** Missing drug-specific fields now render explicit empty states; class/name-derived clinical fallback generation was removed. Lifestyle rows are keyed to explicit generic names, absent interaction coverage is reported as `unrepresented_pairs`, and the three inconsistent catalog records were corrected. Drug/class/condition/price/pregnancy/symptom/news pages now distinguish raw or simulated fixture fields from medical or regulatory facts.
- **Evidence:** Exact static catalog digest `7035e6cb406e416d913fa36216223a7578479795812a3674f07fa9d8bfe3298c`; application and seed tests; 21 browser task workflows.

### Reviewer 3 — task feasibility and database-grounded truth

- **Observation:** The original 21 tasks had inconsistent ports, direct answer leakage, ambiguous workflow requirements, and several verifier/task mismatches.
- **Verification:** Every task was solved from the canonical initial database and through the rendered browser UI. Required entities, result order, credentials, and dedicated subpages were inspected.
- **Remediation:** All task origins are `http://localhost:40024/`; rubric text contains no literal answer; task wording and dedicated FAQ/warnings/dosage workflows are aligned; canonical truth is loaded only from the protected initial snapshot.
- **Evidence:** `sites/drugs_com/tasks.jsonl`; final 21/21 real-browser run with 99 successful UI steps.

### Reviewer 4 — adversarial verifier review

- **Observation:** The original verifiers accepted fabricated origins, `inspect`-only trajectories, blank screenshots, loose final-URL shortcuts, negated or numerically reassociated answers, wrong entity associations, and incorrect Task 13 pairings.
- **Verification:** Adversarial fixtures reproduced wrong-origin, shortcut, contradiction, extra-entity, wrong-credential, malformed-PNG, schema mutation, row mutation, number-binding, and pair-swapping false positives.
- **Remediation:** Verifiers now require the exact task ID and `localhost:40024` origin, successful supported browser actions, ordered UI transitions, exact input multisets, decoded nonblank PNG sequences with visual transitions, a final `done` action bound to the answer, canonical initial seed SHA-256, exact schema/table/row/byte equality, task-specific entity and numeric binding, explicit contradiction checks, domain exclusivity, and exact ordered drug/imprint pair segments.
- **Evidence:** 99 positive and adversarial verifier unit cases are included in the 184-test Drugs.com suite; final real-browser run passes all 21 entry points. The verifier trusts the browser harness to write `action_result`; it does not claim a cryptographic attestation against a process that can arbitrarily rewrite the complete run directory.

### Reviewer 5 — UI, responsive behavior, accessibility, and progressive enhancement

- **Observation:** The original UI had document-level overflow at narrow widths, clipped navigation, non-keyboard autocomplete behavior, ambiguous controls, missing table scroll regions, sticky hash-target occlusion, and JavaScript-only review/notes/checker/price workflows.
- **Verification:** Routes were exercised at 320, 360, 375, 390, 768, 1024, 1280, and 1440 CSS pixels, including authenticated pages and representative parameters. Keyboard More-menu and hash-target checks were run at every width.
- **Remediation:** Responsive containment, table regions with keyboard focus, non-sticky mobile header behavior, scroll offsets, native disclosure navigation, labeled controls, listbox/combobox state, skip/focus styles, reduced-motion behavior, native review rating selection, no-JavaScript notes and interaction forms, all-quantity no-JavaScript price rendering, and explicit unsupported Pro workflows were implemented.
- **Evidence:** 464 final route/viewport checks: 0 HTTP failures, 0 document overflow, 0 empty-content failures, 0 broken images, 0 duplicate IDs, 0 unnamed controls, 0 empty links, 0 missing alt attributes, 0 page/console errors, 0 remote requests, 0 menu failures, and 0 hash-target failures. Seven no-JavaScript workflows passed.

### Reviewer 6 — current-main, Docker, control plane, and Hugging Face integration

- **Observation:** The original branch targeted an obsolete site count and port, used a stale asset revision, and had no final Docker artifact or robust reset evidence.
- **Verification:** The 25-site order was compared across `websyn_start.sh`, `control_server.py`, Docker, docs, task manifests, and current main. The pinned HF revision and archive set were fetched from scratch.
- **Remediation:** Drugs.com is site 25 at `40024`; `.assets-revision` pins immutable HF commit `18e64e4d230794f990199f3327432d26db36866f`; fetch validates the exact archive-name set and site-aware seed requirements; Docker performs a final 25-database integrity gate; control reset uses staging/rename and treats backup cleanup outside rollback; reset-all returns structured partial results.
- **Evidence:** Fresh 25-archive fetch/check passed. Drugs.com archive: 134 bytes, SHA-256 `fa2092873de0d2a06c2ecac5fd389a8863ab3e271b9c197f9c3dd5fa984f378b`. No-cache image build `sha256:1652ee909d0e2e613b11c3083810817274335d8c25f6180b8ba305a08bcb86c9` passed its 25-seed gate.

### Reviewer 7 — tests, evidence, and repository hygiene

- **Observation:** The original branch lacked adequate app/verifier tests, had lint failures, carried unaudited generated artifacts, and had incomplete conflict/hygiene checks.
- **Verification:** Tests, ignored/managed paths, generated seeds, syntax, Ruff E9/F, merge markers, and main-relative diff whitespace were checked from the actual worktree.
- **Remediation:** Application, seed, integration, provenance, reset failure-injection, archive failure-injection, and verifier adversarial suites were added. Build/runtime test files are excluded from the image. Managed-path parity is tested across `.assetpaths`, `.gitignore`, and extraction scripts.
- **Evidence:** Ruff E9/F passed; Python compile passed; shell syntax passed; `git diff ... --check` passed; no conflict markers, symlinks, AppleDouble files, or tracked Drugs.com image files were found.

### Reviewer 8 — provenance, medical-content presentation, and compliance

- **Observation:** The original archive included 43 JPEG files without per-file source/license evidence and Apple metadata. Templates presented simulated reviews/news, professional identities, official service channels, current approvals, prices, clinical claims, and generated pill graphics as real.
- **Verification:** Archive members, xattrs, templates, tracked source declarations, runtime requests, and each content family were inspected.
- **Remediation:** Unverifiable JPEGs were removed. `asset_inventory.json` requires zero runtime media files. `content_inventory.json` records the source location and unresolved external provenance of every fixture family. Synthetic pill diagrams are visibly labeled and cannot be presented as photos or identification evidence. Simulated articles/reviews, generated prices, raw medical text fixtures, local support forms, subscriptions, and professional layouts are labeled at their point of use. Missing data is not synthesized into drug-specific claims.
- **Evidence:** Runtime performs zero background external requests in the responsive matrix. The repository contains zero tracked Drugs.com image files and zero AppleDouble files. This candidate intentionally does not claim real-site pill-image fidelity because PR 71 supplied no auditable source/license mapping.

### Reviewer 9 — remediated security/application completion review

- **Observation:** The first remediation still treated missing interaction coverage as no interaction, applied broad class lifestyle rules, accepted count-preserving seed tampering, destroyed the old seed before build success, allowed ambiguous brand wildcards, had nullable/default inconsistencies, and committed registration before vote claiming.
- **Verification:** Each objective example in the second-round report was reproduced or traced to exact source and database rows.
- **Remediation:** Unknown coverage, explicit generic lifestyle rules, manifest-bound static catalog/schema digests, failure-atomic staged seed generation, exclusive DB ownership, exact brand-element lookup, corrected nullability/defaults, authenticated voting, and a single registration transaction close these items.
- **Evidence:** Tampered static content makes `/_health` return 503; import and seed failure tests preserve known-good state; a second process sharing the SQLite path fails closed; all regression tests pass.

### Reviewer 10 — remediated task/verifier completion review

- **Observation:** The first verifier rewrite still accepted wrong localhost ports, decoy login credentials, final-URL shortcuts, mixed contradictions, unbound numbers, extra entities, weak risk overlap, and unpaired Task 13 output.
- **Verification:** All listed objective adversarial cases were added as tests, including natural valid number phrasing and verbose valid pairs to prevent false negatives.
- **Remediation:** Exact-origin, successful action protocol, ordered input/click transitions, exact answer domains, bound numeric forms, curated risk concept groups, exact Alice medication set, and delimiter-based ordered pair checks were added.
- **Evidence:** Final verifier suite and 21 real browser trajectories pass; all requested adversarial cases fail.

### Reviewer 11 — remediated UI/compliance completion review

- **Observation:** The first UI remediation retained official/clinical/commercial claims, inferred dosage/warning/pregnancy/image content, incomplete no-JavaScript workflows, mobile clipping, raw status fallbacks, and ARIA issues.
- **Verification:** Every cited template and CSS selector was inspected, then all affected workflows were re-exercised after restart.
- **Remediation:** Official identities/channels, unverified clinical generation, fake current news/approvals, redeemable-price language, no-image pill fallback, raw status assertions, and unsupported workflows were removed or explicitly represented as fixtures/empty states. Responsive and accessibility defects were closed.
- **Evidence:** Final 464-check responsive/accessibility matrix and seven no-JavaScript workflows pass with zero listed failures.

### Reviewer 12 — remediated integration/test completion review

- **Observation:** The first integration remediation lacked a clean image, could roll back from partially deleted backups, weakly validated arbitrary seed directories, accepted wrong archive sets and media-only ordinary archives, returned unstructured reset-all failures, and contained stale docs.
- **Verification:** Failure injection was applied to reset and asset backup cleanup; archive contracts and every packaged SQLite file were validated.
- **Remediation:** Cleanup occurs after commit without deleting valid new state; ordinary archives require exactly one non-empty seed DB while build-generated sites are explicit exceptions; full fetch compares exact sets; docs preserve both asset-revision fields and use bearer authentication; the image runs a final all-site SQLite gate.
- **Evidence:** No-cache build and candidate-container tests passed; 25/25 roots, authenticated health, unauthorized 401, individual reset, two reset-all cycles, all-site seed/runtime byte parity, ten additional Drugs.com resets, zero zombies, stable control FDs/process count, and full container restart all passed.

## Canonical Drugs.com Seed

- Version: `drugs-com-source-v2`
- Bytes: `1146880`
- SHA-256: `520d6f7015918bffec6492103b5b6284cf925796120c5689f9e0d2b32f0f1547`
- Catalog SHA-256: `7035e6cb406e416d913fa36216223a7578479795812a3674f07fa9d8bfe3298c`
- Schema SHA-256: `49aa5dd90eb92aab3dfaaf62e9a2062ca046b1c657ce2455267e6ff1cdec553b`
- Reproducibility: byte-identical with `PYTHONHASHSEED=1`, `19`, `777`, and `991`; `pysqlite3-binary==0.5.4` pins SQLite across host and Docker, and the Docker-generated SHA matches the manifest.

## Final Test Matrix

| Scope | Result |
|---|---|
| Drugs.com application, seed, integration, verifier positive/adversarial tests | 184 passed |
| Real browser tasks | 21/21 passed, 99 successful steps |
| Responsive/accessibility route matrix | 464 passed, 8 widths, 58 route/auth cases per width |
| No-JavaScript workflows | 7/7 passed |
| Walmart Careers regression | 297 passed, 16 subtests passed |
| Rotten Tomatoes regression | 66 passed, 4143 subtests passed, 28 SQLAlchemy legacy warnings |
| OSU regression | 25 passed, 264 subtests passed |
| TED regression | 27 passed, 291 subtests passed |
| Compass regression | 229 passed |
| Fresh HF archive fetch and asset/seed checks | 25 archives passed |
| No-cache Docker build | passed; image `sha256:1652ee909d0e2e613b11c3083810817274335d8c25f6180b8ba305a08bcb86c9` |
| Candidate container | 25 roots passed; 25 seed DBs valid; 11 individual Drugs.com resets; 2 reset-all cycles; restart passed |
| Candidate process stability | control FDs 4→4; processes 52→52; zombies 0 |

## Deployment Boundary

The control plane is bearer-authenticated. The final public deployment should expose only Drugs.com port `40024` through host loopback port `8791`; control port `8101` should remain unpublished. Set `DRUGS_COM_SECURE_COOKIES=1` only when an HTTPS terminator is actually present; the requested plain-HTTP localhost deployment uses loopback binding instead.

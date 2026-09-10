# PR 71 Final Audit

## Status

Release candidate validated against original PR head `73eba14579449404abf1efd5cc6b86c7b5507a7a` and upstream `main` `36004932bdf82afbe36dc14e00f66841eccf9946`. The integrated topology has 25 sites; Drugs.com is appended at container port `40024` without changing the existing site positions.

This audit did not post a GitHub comment and does not authorize merging the upstream pull request.

## Review Streams

### Reviewer 1 — security, authentication, authorization, and state integrity

- **Observation:** The original control plane allowed unauthenticated reset/restart operations. Session secrets, login controls, input bounds, transaction behavior, account ownership, anonymous review voting, and SQLite constraints also required review.
- **Verification:** Direct source inspection confirmed public mutation routes in `control_server.py`, process-local concurrency assumptions, anonymous vote-ledger growth, registration commit ordering, weak nullability, and session-cookie data exposure.
- **Remediation:** Every control endpoint now requires a constant-time bearer-token check. Drugs.com has a cryptographically random runtime secret, bounded requests and fields, CSRF on mutations, strict safe redirects, login throttling, a bounded runtime account count, unique site-specific cookie names, optional secure cookies for TLS deployments, authenticated-only bounded helpful votes, ownership-scoped mutations, non-null/check/unique/FK constraints, and an exclusive per-database process lock. Anonymous email and medication-browsing history are not stored in the client cookie.
- **Evidence:** `sites/drugs_com/tests/test_app.py`; authenticated and unauthenticated control-plane tests in `sites/drugs_com/tests/test_integration.py`; final Drugs.com suite: 404 passed.

### Reviewer 2 — application behavior and data consistency

- **Observation:** The original application inferred dosage forms, pregnancy guidance, warnings, storage, overdose behavior, lifestyle interactions, availability, clinical conclusions, and class-wide facts from names or broad classes. Ranitidine, haloperidol, and Janumet records were internally inconsistent.
- **Verification:** Each reported example was checked against `DRUGS_DATA`, `DRUG_CONTENT_OVERRIDES`, route handlers, templates, and generated SQLite rows.
- **Remediation:** Missing drug-specific fields now render explicit empty states; class/name-derived clinical fallback generation was removed. Lifestyle rows are keyed to explicit generic names, absent interaction coverage is reported as `unrepresented_pairs`, and the three inconsistent catalog records were corrected. Drug/class/condition/price/pregnancy/symptom/news pages now distinguish raw or simulated fixture fields from medical or regulatory facts.
- **Evidence:** Exact static catalog digest `0048909eebc40a017c99cdc08f4fab89760035bc5bcbc476c5fb3a7da4049d9f`; application and seed tests; 21 browser task workflows.

### Reviewer 3 — task feasibility and database-grounded truth

- **Observation:** The original 21 tasks had inconsistent ports, direct answer leakage, ambiguous workflow requirements, and several verifier/task mismatches.
- **Verification:** Every task was solved from the canonical initial database and through the rendered browser UI. Required entities, result order, credentials, and dedicated subpages were inspected.
- **Remediation:** All task origins are `http://localhost:40024/`; rubric text contains no literal answer; task wording and dedicated FAQ/warnings/dosage workflows are aligned; canonical truth is loaded only from the protected initial snapshot.
- **Evidence:** `sites/drugs_com/tasks.jsonl`; final 21/21 real-browser run with 99 successful UI steps.

### Reviewer 4 — adversarial verifier review

- **Observation:** The original verifiers accepted fabricated origins, `inspect`-only trajectories, blank screenshots, loose final-URL shortcuts, negated or numerically reassociated answers, wrong entity associations, and incorrect Task 13 pairings.
- **Verification:** Adversarial fixtures reproduced wrong-origin, shortcut, contradiction, extra-entity, wrong-credential, malformed-PNG, schema mutation, row mutation, number-binding, and pair-swapping false positives.
- **Remediation:** Verifiers now require the exact task ID and `localhost:40024` origin, successful supported browser actions, ordered UI transitions, exact input multisets, decoded nonblank PNG sequences with visual transitions, a final `done` action bound to the answer, canonical initial seed SHA-256, exact schema/table/row/byte equality, task-specific entity and numeric binding, explicit contradiction checks, domain exclusivity, and exact ordered drug/imprint pair segments.
- **Evidence:** 273 positive and adversarial verifier cases are included in the 404-test Drugs.com suite; final real-browser run passes all 21 entry points. The verifier trusts the browser harness to write `action_result`; it does not claim a cryptographic attestation against a process that can arbitrarily rewrite the complete run directory.

### Reviewer 5 — UI, responsive behavior, accessibility, and progressive enhancement

- **Observation:** The original UI had document-level overflow at narrow widths, clipped navigation, non-keyboard autocomplete behavior, ambiguous controls, missing table scroll regions, sticky hash-target occlusion, and JavaScript-only review/notes/checker/price workflows.
- **Verification:** Routes were exercised at 320, 360, 375, 390, 768, 1024, 1280, and 1440 CSS pixels, including authenticated pages and representative parameters. Keyboard More-menu and hash-target checks were run at every width.
- **Remediation:** Responsive containment, table regions with keyboard focus, non-sticky mobile header behavior, scroll offsets, native disclosure navigation, labeled controls, listbox/combobox state, skip/focus styles, reduced-motion behavior, native review rating selection, no-JavaScript notes and interaction forms, all-quantity no-JavaScript price rendering, and explicit unsupported Pro workflows were implemented.
- **Evidence:** 464 final route/viewport checks: 0 HTTP failures, 0 document overflow, 0 empty-content failures, 0 broken images, 0 duplicate IDs, 0 unnamed controls, 0 empty links, 0 missing alt attributes, 0 page/console errors, 0 remote requests, 0 menu failures, and 0 hash-target failures. Twelve no-JavaScript workflows passed.

### Reviewer 6 — current-main, Docker, control plane, and Hugging Face integration

- **Observation:** The original branch targeted an obsolete site count and port, used a stale asset revision, and had no final Docker artifact or robust reset evidence.
- **Verification:** The 25-site order was compared across `websyn_start.sh`, `control_server.py`, Docker, docs, task manifests, and current main. The pinned HF revision and archive set were fetched from scratch.
- **Remediation:** Drugs.com is site 25 at `40024`; `.assets-revision` pins immutable HF commit `18e64e4d230794f990199f3327432d26db36866f`; fetch validates the exact archive-name set and site-aware seed requirements; Docker performs a final 25-database integrity gate; control reset uses staging/rename and treats backup cleanup outside rollback; reset-all returns structured partial results.
- **Evidence:** Fresh 25-archive fetch/check passed. Drugs.com archive: 134 bytes, SHA-256 `fa2092873de0d2a06c2ecac5fd389a8863ab3e271b9c197f9c3dd5fa984f378b`. The no-cache image build passed its 25-seed gate; the post-commit image digest is recorded in the external completion packet to avoid a self-referential tracked artifact.

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
- **Evidence:** Final 464-check responsive/accessibility matrix and twelve no-JavaScript workflows pass with zero listed failures.

### Reviewer 12 — remediated integration/test completion review

- **Observation:** The first integration remediation lacked a clean image, could roll back from partially deleted backups, weakly validated arbitrary seed directories, accepted wrong archive sets and media-only ordinary archives, returned unstructured reset-all failures, and contained stale docs.
- **Verification:** Failure injection was applied to reset and asset backup cleanup; archive contracts and every packaged SQLite file were validated.
- **Remediation:** Cleanup occurs after commit without deleting valid new state; ordinary archives require exactly one valid SQLite seed DB while build-generated sites are explicit exceptions; full fetch compares exact sets and runs inside a repository-wide rollback transaction with migrations applied in staging; tracked `assets-manifest.json` binds every archive size/SHA-256 and the managed-tree digest to the pinned HF revision; docs preserve both asset-revision fields and use bearer authentication; the image pins its base digest and dependency versions and runs final tracked-manifest and all-site SQLite gates.
- **Evidence:** No-cache build and candidate-container tests passed; 25/25 roots, authenticated health, unauthorized 401, missing-token startup rejection, individual reset, two reset-all cycles, all-site seed/runtime byte parity, ten additional Drugs.com resets, zero zombies, stable control FDs/process count, and full container restart all passed.

### Reviewer 13 — immutable security/application audit

- **Observation:** The immutable review found a predictable fallback control-token file, unbounded failed-login key retention, missing pair-level coverage disclosure in the browser checker, silently dropped pill/pregnancy declarations, and path-only database process locking.
- **Verification:** Each counterexample was reproduced from the cited source, including hostile fallback-token precreation, unique failed-login identities, sildenafil/nitroglycerin browser output, unmatched declarations, and hard-linked database paths.
- **Remediation:** The control server now requires an explicit 32-character token and startup fails before launching sites when it is absent; failed-login keys receive global expiry and a 4,096-key cap; browser/API coverage semantics match; every pill/pregnancy declaration maps exactly once; process locking covers both canonical path and SQLite inode.
- **Evidence:** Missing/short token subprocess tests, bounded-auth-key test, browser unknown-pair test, declaration completeness test, and hard-link lock test pass.

### Reviewer 14 — immutable task/verifier audit

- **Observation:** The immutable review found global retraction and severity-decoy bypasses, numeric polarity/competition gaps, a valid “do not exceed” false negative, normalized-password acceptance, extra query-state acceptance, non-root starts, and failure-output answer leakage.
- **Verification:** Concrete positive and negative sentences and trajectories from the review were added directly as regression cases.
- **Remediation:** Global retractions and domain contradictions are rejected; interaction severity and primary risk must share the entity-bound sentence and conflicting severity is forbidden; count/rating/review/frequency competitors are rejected; “do not exceed” is accepted; Alice’s password is byte-exact and ordered; result queries and root entry state are exact; verifier evidence exposes check names without expected answer values.
- **Evidence:** 204 verifier cases pass, including every new counterexample and the 21 real-browser runs.

### Reviewer 15 — immutable UI/provenance audit

- **Observation:** The immutable review found misleading pill/search help, incomplete provenance families, four JavaScript-only controls, mobile menu destination loss, ARIA current/tab defects, missing detail empty states, review/account simulation wording gaps, one unlabeled synthetic carousel, and inaccurate rating graphics.
- **Verification:** Each cited template/control was inspected and exercised with JavaScript disabled, keyboard navigation, missing-data records, and the eight-width route matrix.
- **Remediation:** Help/search language and inventory families are complete; inline checking and helpful voting use native forms; inert filters are hidden with complete no-JavaScript views; hidden mobile destinations are available in More; consumer subpages and homepage tabs use correct semantics and keyboard state; empty states, simulation labels, synthetic carousel labels, percentage tracks, and half-star rendering are corrected.
- **Evidence:** 464 responsive/accessibility checks and twelve no-JavaScript workflows pass.

### Reviewer 16 — immutable integration/release audit

- **Observation:** The immutable review found regular-file managed-root acceptance, byte-only archive seed checks, post-install migration failure exposure, procedural Docker asset provenance, a mutable base tag/unpinned transitive dependencies, and stale operational docs.
- **Verification:** Malformed root/seed archives, migration failure, repository-wide rollback, tree tampering, tokenless startup, docs, and no-cache Docker behavior were tested.
- **Remediation:** Managed roots must be directories; ordinary archive DBs pass SQLite integrity/FK/table checks before installation; migration runs in staging; full fetch has global rollback; Docker verifies exact extracted-tree state against the immutable HF pin, pins the base digest and every resolved dependency, and rejects missing control tokens; docs reflect SIGKILL, PID 1, repository URL, and legacy database filenames.
- **Evidence:** Transactional full 25-archive fetch passed with asset tree `da553127dc82e8422b66e11dc4d9cfc8cf069bdd5eae12e60fb1fd7aa0d6d49f`; final no-cache build and container tests pass.

### Reviewer 13 — second immutable security/application completion audit

- **Observation:** The immutable candidate still admitted a concurrent first burst beyond the login limit, accepted short configured Flask secrets, omitted missing drug/alcohol pairs from API coverage details, and contained conflicting metronidazole/simvastatin fixture instructions.
- **Verification:** Concurrent limiter reservations, weak-secret loading, uncovered ibuprofen/alcohol API output, and all three conflicting values were reproduced directly.
- **Remediation:** Authentication now reserves capacity atomically before bcrypt and releases it atomically afterward; successful public-benchmark login cannot clear source failure history; configured secrets require 32 bytes; missing alcohol pairs are listed; internally duplicated fixture values are consistent.
- **Evidence:** Parallel 16-attempt admission proves exactly eight reservations, source-history and weak-secret tests pass, pair-level API tests pass, and fixture-consistency tests pass.

### Reviewer 14 — second immutable task/verifier completion audit

- **Observation:** The immutable candidate still accepted retracted Task 8 claims, values assigned to wrong fields, invented closed-world list entries, competing dosage/shape/color claims, inputs logged on unrelated pages, extra query state on path-only destinations, and SQLite changes present only in WAL. It also required a pixel change after every successful action and accepted only one natural Task 8 severity word order.
- **Verification:** Each supplied counterexample was added as a direct verifier regression. A live WAL mutation and a valid same-page action with unchanged pixels were exercised.
- **Remediation:** Count/severity claims require affirmed relations in both natural word orders; brands/classes/conditions/shape/color are label-bound; closed-world list segments and pill pairs are exhaustive; competing numeric and descriptor claims fail; inputs are route- and order-bound; non-query destinations require empty query state; snapshots use SQLite backup semantics in the host and container; only actual navigation transitions require changed pixels.
- **Evidence:** 204 verifier cases and 21 real-browser task workflows pass. Browser control identity and screenshot provenance remain explicitly bound to the trusted harness `action_result` contract; no claim is made against an executor that can rewrite the complete run directory.

### Reviewer 15 — second immutable UI/provenance completion audit

- **Observation:** The immutable candidate retained a compressed small-screen search column, low-contrast normal text, unqualified simulated review/news aggregates, unsupported medication advice, visible JavaScript-only controls, two missing-field surfaces without empty states, undisclosed local-only dashboard preferences, conflicting review solicitation, and a commercial-sounding generated-price entry label.
- **Verification:** The 320/375-pixel search result width, computed color contrast, point-of-display labels, no-JavaScript controls, missing-data templates, and cited copy were inspected and tested.
- **Remediation:** Search stacks at mobile widths with a measured usable result column; normal text colors meet 4.5:1; aggregate/search labels identify simulated fixtures; medication advice was replaced with benchmark-only boundaries; save controls are native forms and unsupported JS controls are hidden without JavaScript; missing fields have explicit empty states; dashboard preferences disclose zero delivery; review and generated-value labels are literal.
- **Evidence:** The 464-check matrix reports zero search-usability failures in addition to the prior zero-failure categories; WCAG palette tests pass; twelve no-JavaScript workflows pass, including native detail-page medication saving.

### Reviewer 16 — second immutable integration/release completion audit

- **Observation:** The immutable candidate allowed an HF revision override to be mislabeled as the pin, committed the repository asset transaction before state publication, and could pack/upload stale extra archives.
- **Verification:** Override rejection, manifest-verification failure rollback, nonempty output rejection, exact clean-output packing, and complete 25-archive fetch were exercised.
- **Remediation:** Every override must equal the tracked immutable pin; tracked `assets-manifest.json` binds all 25 archive byte sizes/SHA-256 values and the extracted tree digest; normal fetch verifies archive and tree bytes before transaction commit; maintainer manifest refresh is explicit, full-fetch-only, and rollback-protected; packing requires an empty output directory and exact generated set.
- **Evidence:** Manifest SHA-256 `c2134838c84249b0e65a9c0d72a5360739aaa27164eb9047d0f20223e3ea819a`, asset tree `da553127dc82e8422b66e11dc4d9cfc8cf069bdd5eae12e60fb1fd7aa0d6d49f`, exact pinned archive verification, rollback failure injection, and pack-set tests pass.

### Reviewer 13 — third immutable security/application completion audit

- **Observation:** Anonymous registration still hashed passwords after capacity was exhausted and had no attempt limiter; login skipped bcrypt for missing accounts and exposed an account-existence timing branch.
- **Verification:** Password-hash calls were instrumented at capacity, repeated valid anonymous registrations were submitted, and existing/missing login paths were instrumented.
- **Remediation:** Registration reserves source-rate capacity, checks account capacity before hashing, serializes the bounded hash/commit path, and counts successful or failed hashing attempts; login verifies every bounded password against either the account hash or a fixed dummy bcrypt hash.
- **Evidence:** Capacity-without-hash, registration rate-limit, and equal password-check-path tests pass.

### Reviewer 14 — third immutable task/verifier completion audit

- **Observation:** Correct-first/false-later fields, number-word competitors, an asserted different main risk, and reordered search/login stages remained accepted; several natural field/risk/pregnancy/count paraphrases were rejected. The review also restated the run-directory, snapshot-invocation, and hidden-answer orchestration boundaries.
- **Verification:** Every concrete semantic and trajectory counterexample was added, together with the valid natural-language variants.
- **Remediation:** Every repeated field clause must remain consistent; workflow indices are ordered and the required destination is the final state; number words participate in count/rating/dosage/frequency competition; explicit main-risk claims must contain expected risk concepts; accepted deterministic paraphrase groups were expanded. `verify/README.md` now defines the browser-only sandbox and trusted ownership of trajectories, screenshots, action results, snapshots, arguments, and verifier execution; tests and answer derivation are excluded from the evaluated runtime boundary.
- **Evidence:** 204 verifier cases pass. The verifier remains intentionally unsuitable when an evaluated process can read source/seed answers or rewrite orchestrator-owned artifacts.

### Reviewer 15 — third immutable UI/accessibility completion audit

- **Observation:** Several review/action links had missing or wrong destinations; missing availability produced Rx/Rx-OTC claims; two search inputs lacked focus indication; tabs lacked roving `tabindex`; account/current navigation lacked semantics; optional pill radio criteria could not be cleared independently.
- **Verification:** Every cited link, fallback, focus selector, tab state, landmark, and pill form was inspected and exercised in source and browser tests.
- **Remediation:** Links target dedicated review/compare routes without missing fragments; availability uses literal stored/empty states and the status icon reflects the field; focus-visible outlines are explicit; custom tabs implement roving `tabindex`; account and drug-detail navigation has labels/current state; Any shape/Any color and an always-available clear action support independent filter removal.
- **Evidence:** Source contracts, the full responsive/accessibility and no-JavaScript matrices, and seventeen targeted browser checks for roving tabs, visible focus, independent pill-filter clearing, and link destinations pass.

### Reviewer 16 — third immutable integration/release completion audit

- **Observation:** Single-site fetch installed archives before checksum validation, managed-root/special-object topology was not fully recorded, legacy reset docs hard-coded database names, and reset latency claims lacked timing evidence.
- **Verification:** A valid tracked archive and byte-tampered variant, symlinked managed root, AppleDouble file, FIFO, legacy database-name command, and docs were checked.
- **Remediation:** Single-site fetch verifies tracked archive size/SHA-256 before structural validation or installation; tree validation rejects site/root symlinks, AppleDouble files, and special objects; reset parity discovers the one database filename and uses SHA-256; unsupported latency wording was removed.
- **Evidence:** Real pinned Drugs.com single-site checksum/fetch passed, strict object-topology tests pass, and full-tree verification remains bound to `assets-manifest.json`.

### Reviewer 15 — fourth immutable UI/accessibility completion audit

- **Observation:** Search empty-state wording still suggested a real-pill use case for a synthetic matcher; JavaScript-disabled checker/price pages retained dead controls; small orange badges failed normal-text contrast; dynamic filter counts lacked live status semantics; empty condition letters were pointer-disabled links that remained keyboard-operable.
- **Verification:** The cited wording and controls were inspected with JavaScript disabled; computed contrast, live-region attributes, and empty-letter element semantics were exercised.
- **Remediation:** Search now limits the matcher to synthetic fixture fields and explicitly denies real identification; JavaScript-only controls are hidden beside native fallbacks; orange text backgrounds use the tested dark palette; filter counts use polite status regions; empty letters are noninteractive disabled spans.
- **Evidence:** Twelve no-JavaScript workflows, the 464-page matrix, and seventeen targeted UI/browser checks pass.

### Reviewer 16 — fourth immutable integration/release completion audit

- **Observation:** Full fetch consumed archives before checksum verification, Docker versions lacked distribution hashes, and reset documentation retained MD5/placeholders and unsupported latency wording.
- **Verification:** Full-fetch command order, wheel files downloaded inside the pinned base image, Docker installation mode, and every reset instruction/claim were checked.
- **Remediation:** Normal full fetch verifies each archive against the tracked manifest before tar/SQLite/migration processing and re-verifies the complete set/tree before commit; `requirements.lock` pins the selected Python 3.12 Linux wheel SHA-256 for every resolved package and Docker uses `--require-hashes`; docs discover application-defined database filenames, use SHA-256, and make no reset-duration claim.
- **Evidence:** Integrity-before-consumption ordering tests and a no-cache hash-locked Docker build pass; maintainer-only manifest refresh remains explicit and rollback-protected because a new immutable revision has no prior archive manifest.

### Reviewer 13 — fifth immutable security/application completion audit

- **Observation:** Site processes inherited the control bearer credential; duplicate/unresolved interaction inputs could produce a zero-pair result; controlled generated-price tier detection did not recognize the catalog's `C-II` through `C-V` representation.
- **Verification:** Spawn environments, duplicate browser/API requests, one-recognized/one-unrecognized API input, and controlled/noncontrolled tier records were exercised.
- **Remediation:** Initial and respawned site supervisors remove `WEBSYN_CONTROL_TOKEN`; both interaction surfaces require at least two distinct resolved items including alcohol; normalized `C-I` through `C-V` values select the controlled synthetic tier.
- **Evidence:** Child-environment credential isolation, distinct-cardinality, and generated-tier tests pass.

### Reviewer 14 — fifth immutable task/verifier completion audit

- **Observation:** Remaining counterexamples used unknown schedule/severity words, dozen/no/hourly forms, pregnancy continuation claims, globally unbound secondary risk concepts, and NSAID alias contradiction; numbered lists and one clear unlabeled status sentence were false negatives.
- **Verification:** All six contradiction forms, secondary-risk heading decoy, alias contradiction, seven numbered-list variants, and valid unlabeled status sentence were added directly.
- **Remediation:** Schedule/severity clauses reject incompatible additions; dozen/zero/no/hourly and number words participate in contradiction checks; pregnancy continuation conflicts fail; every required risk concept binds to a sentence containing a relevant entity/alias; class aliases cannot negate the canonical class; numbered list markers are accepted; unambiguous prescription/noncontrolled prose is accepted without forced labels.
- **Evidence:** 204 verifier cases and the full 21-task browser run pass. The trusted orchestrator/browser-only boundary remains explicitly documented and unchanged.

### Integration stability follow-up

- **Observation:** One heavily loaded candidate run reported a structured reset-all 503 when a site exceeded the former 30-second readiness window; an immediate captured retry completed all 25 sites in 1.178 seconds.
- **Remediation:** Control readiness allows 60 seconds while preserving structured partial failure and fail-closed semantics; candidate tests capture and print every reset-all failure response and allow 90 seconds at the HTTP client.
- **Evidence:** The final candidate completes two reset-all cycles, all seed/runtime byte comparisons, process/FD/zombie checks, and restart readiness.

### Reviewer 13 — sixth immutable security/application completion audit

- **Observation:** Sensitive settings reauthentication was unthrottled and response-distinguishable; case-only duplicate usernames were allowed.
- **Verification:** Repeated authenticated wrong-password changes and an `ALICE_J` registration against seeded `alice_j` were exercised.
- **Remediation:** Current-password settings checks use the same bounded atomic source/account limiter and one generic failure response; the username column and precheck use case-insensitive uniqueness.
- **Evidence:** Sensitive-reauth rate and case-only identity tests pass; the schema digest binds the NOCASE uniqueness contract.

### Reviewer 14 — sixth immutable task/verifier completion audit

- **Observation:** Adverb-separated negation, entity-bearing heading decoys, decimal competitors, unsupported review-count labels, invented latest-title assignment, and unlabelled availability conflicts remained accepted; natural `according to the page` prose was rejected.
- **Verification:** Every supplied sentence was added as an adversarial or positive case.
- **Remediation:** Negation permits intervening adverbs; secondary risk concepts reject heading/label decoys; decimal values participate in count/dose/frequency checks; review-count relations and latest-title assignment are bound; Rx tasks reject status conflicts anywhere; neutral page-attribution prose is accepted.
- **Evidence:** 204 verifier cases and all 21 real-browser workflows pass within the documented trusted-harness boundary.

### Reviewer 15 — sixth immutable UI/accessibility completion audit

- **Observation:** JavaScript price disclosure remained CSS-hidden; symptom checkboxes auto-submitted; breadcrumbs were unnamed; the Pro resource grid and two narrow layouts lacked layout contracts; sitemap copy implied official completeness.
- **Verification:** Disclosure visibility/ARIA state, two-checkbox selection without navigation, navigation landmark names, narrow computed columns, card layout, and copy were checked.
- **Remediation:** The hidden attribute exclusively controls identifier visibility; symptom selection waits for explicit submit; all breadcrumb landmarks are named; resource cards have a responsive grid; source/sitemap inventories collapse to one column; sitemap copy is local and explicitly incomplete relative to the external service.
- **Evidence:** Updated source contracts and targeted browser checks pass.

### Reviewer 16 — sixth immutable integration/release completion audit

- **Observation:** Unknown single-site pack requests could succeed empty; non-database seed entries and SQLite sidecars were copied without final validation.
- **Verification:** Misspelled packaging, a valid DB plus sidecar/nested DB, and final seed-directory gates were tested. The pinned Cambridge archive exposed one inert legacy backup file.
- **Remediation:** Unknown sites fail before output creation; ordinary archive installation strips every non-top-level-`.db` seed entry before migration/installation; final gates reject symlinks, directories, sidecars, nested or non-DB entries; the tracked tree manifest binds the sanitized Cambridge result while archive hashes remain pinned.
- **Evidence:** Exact pack, sanitizer, strict seed-directory, full fetch, managed-tree, no-cache build, and candidate reset parity checks pass.

### Reviewer 13 — seventh immutable security/application completion audit

- **Observation:** Login limiter keys and several email validators received oversized identities before field-specific bounds.
- **Verification:** Oversized login, registration, settings, and newsletter email values were instrumented against limiter storage and validation calls.
- **Remediation:** Login replaces over-limit identities before key construction; registration, settings, and newsletter enforce byte/character contracts before email parsing or normalization.
- **Evidence:** Limiter keys remain bounded and over-limit fields invoke no email-validation work.

### Reviewer 14 — seventh immutable task/verifier completion audit

- **Observation:** Remaining concrete bypasses used adverb-separated negation, unbound risk-link language, unknown severity comparison, decimal competitors, alternate review-count labels, invented recency comparison, pregnancy myth/continue wording, hourly/twice frequency reassociation, and unlabelled availability conflict; several concise natural formats were rejected.
- **Verification:** Every supplied bypass and natural answer was executed as a direct regression.
- **Remediation:** Negation grammar, causal-risk binding, unknown severity/recency comparisons, decimal and alternate count/frequency forms, global availability conflicts, and pregnancy opposition are rejected; numbered lists, page attribution, task-1 status prose, and relevant number-word formats are accepted.
- **Evidence:** 204 verifier cases and 21 real-browser workflows pass; action target and pixel provenance remain explicitly owned by the trusted harness.

### Reviewer 15 — seventh immutable UI/accessibility completion audit

- **Observation:** The JavaScript demo identifier was CSS-hidden after activation; symptoms auto-submitted on change; breadcrumbs were unnamed; Pro/source/sitemap layouts lacked narrow contracts; sitemap copy implied external completeness.
- **Verification:** The same controls were checked through computed display/ARIA state, multi-selection without navigation, landmark names, and 360-pixel computed layout.
- **Remediation:** Hidden state and disclosure state agree; symptoms wait for explicit submit; every breadcrumb is named; resource and inventory layouts collapse; sitemap copy states the local incomplete scope.
- **Evidence:** Seventeen targeted browser checks, 464 matrix checks, and twelve no-JavaScript workflows pass.

### Reviewer 16 — seventh immutable integration/release completion audit

- **Observation:** Post-install backup residue was outside the tree digest and Docker ignore boundary.
- **Verification:** Injected cleanup residue was checked against managed-tree validation and Docker context rules.
- **Remediation:** Any `*.asset-backup` residue fails tree verification and is also excluded from Docker context; the installed managed roots remain retained on cleanup failure for recovery.
- **Evidence:** Backup-residue validation, no-cache build, strict all-site seed gate, and candidate reset parity pass.

### Reviewer 13 — eighth immutable security/application completion audit

- **Observation:** Oversized login identities entered limiter keys, and registration/settings/newsletter parsed email before their declared bounds.
- **Remediation:** Per-field bounds now precede limiter key construction and all email validation/normalization.
- **Evidence:** Oversized requests create no oversized account key and invoke no email validator.

### Reviewer 14 — eighth immutable task/verifier completion audit

- **Observation:** Further concrete cases split related interaction risks, compared an unknown severity, opposed pregnancy instructions, reassociated adult frequency, declared an invented item newer, used decimal competitors/alternate review-count labels, and exercised neutral answer formats.
- **Remediation:** Interaction concepts require one joint entity/severity/risk relation; every severity/recency comparison binds the expected value; pregnancy and standard-adult frequency relations are joint; all decimal/count/status contradictions are parsed; additional natural answer and number-word formats are accepted.
- **Evidence:** 204 verifier cases and the latest 21-task/99-step browser run pass.

### Reviewer 15 — eighth immutable UI/accessibility verification

- **Observation:** A completion report alleged stale JavaScript disclosure, auto-submit, breadcrumb, layout, and sitemap defects.
- **Verification:** The immutable source and targeted browser evidence show `display:block` after disclosure, no symptom `onchange`, named breadcrumbs, one-column mobile layouts, and explicit local/incomplete sitemap wording.
- **Result:** The allegations were contradicted by supplied source and runtime checks; no additional source change was required.

### Reviewer 16 — eighth immutable integration/release completion audit

- **Observation:** Failed cleanup could leave `*.asset-backup` siblings outside the digest while Docker copied them.
- **Remediation:** Tree verification rejects every backup residue and Docker independently excludes it.
- **Evidence:** Injected residue fails the manifest gate; final full fetch, no-cache image, and candidate cycles pass.

### Reviewer 14 — ninth immutable task/verifier completion audit

- **Observation:** Further explicit overrides used separated risk terms, unknown severity comparison, pregnancy myth/rather-than wording, reassociated standard-adult frequency, invented newer/latest claims, decimal/review-total forms, and natural response variants.
- **Remediation:** Required interaction risks now share one joint entity/severity relation; every comparative sentence binds expected severity/recency; pregnancy and adult-frequency facts share their requested relation; decimal/count competitors and adversarial negations are parsed; marketed/Drug.com, class, pill-list, per-day, rated, and adult-infection variants are accepted where semantically equivalent.
- **Evidence:** 204 adversarial/positive verifier cases and 21/21 browser tasks pass within the protected orchestrator boundary.

### Reviewer 15 — ninth immutable UI/accessibility completion audit

- **Observation:** Synthetic captions shared cramped row-flex visuals; carousel arrows remained active after the track became a mobile grid; no-JavaScript review deletion lost confirmation.
- **Remediation:** Pill visual/caption wrappers use vertical contained layout, fixed card dimensions were removed, mobile-grid arrows are hidden, and deletion requires a visible native checkbox plus server-side confirmation for every browser mode.
- **Evidence:** Seventeen targeted browser checks and twelve no-JavaScript workflows pass, including caption containment, mobile control state, and native deletion confirmation.

### Reviewer 13 — tenth immutable security/application audit

- **Result:** PASS with no Blocker, High, or Medium objective defect. Declared localhost/TLS, advisory-lock, same-container, and unverified-medical-data boundaries remain limitations rather than source defects.

### Reviewer 14 — tenth immutable task/verifier completion audit

- **Observation:** Additional override forms used “no prescription,” `rather than` main risk, unknown severity `outranks`, unlimited dose wording, repeated latest claims, “a hundred” review total, pregnancy `continuing ... safe`, and reassociated adult schedule; natural marketed/per-day/rated/treats/adult-infection formats were rejected.
- **Remediation:** Rx status recognizes no-prescription contradiction; actual risk forbids replacement relations; severity comparison binds its subject; unlimited dosage and all latest/newest competitors fail; idiomatic hundred and global adult schedule conflicts are parsed; natural marketed, per-day, rated, treatment-list, and adult-infection syntax is accepted.
- **Evidence:** 204 verifier cases and latest 21/21 browser tasks pass inside the explicit trusted-artifact boundary.

### Reviewer 15 — tenth immutable UI/accessibility completion audit

- **Observation:** Pill captions competed horizontally with synthetic diagrams, mobile carousel arrows had no horizontal track, and no-JavaScript deletion lost confirmation.
- **Remediation:** Pill wrappers are vertical and contained, mobile-grid arrows are hidden, and deletion requires a native required checkbox plus server-side confirmation.
- **Evidence:** Seventeen targeted browser checks and twelve no-JavaScript workflows cover these paths.

### Reviewer 16 — tenth immutable integration/release audit

- **Result:** PASS with no Blocker, High, or Medium source defect. The final review confirms topology, immutable assets, pre-consumption hashes, sanitized/final seed gates, hash-locked dependencies, token isolation, backup-residue exclusion, reset behavior, and deployment boundary.

### Reviewer 14 — eleventh immutable task/verifier completion audit

- **Observation:** Count/severity, dosage, rating/review, status, pregnancy, and frequency facts could be reassigned to another entity; gastrointestinal and bleeding terms could describe separate risks; credential inputs reused one control index; additional neutral phrasings were rejected.
- **Remediation:** Every requested fact set now shares a sentence with its named entity; Task 2 requires an explicit gastrointestinal/digestive-system bleeding relation; login credential inputs require distinct trusted control indices; categorized/trade-name, mild-to-moderate adult, and digestive-system phrasings are supported.
- **Evidence:** 204 verifier cases and the final 21-task browser run pass within the documented trusted harness boundary.

### Reviewer 15 — twelfth UI/accessibility remediation

- **Observation:** A generic `WARNING:` prefix was promoted to regulatory boxed-warning status; template-defined navigation taxonomy was omitted from provenance; comparison attributes lacked row headers; dynamic strength/count feedback lacked live semantics; several normal-text colors failed contrast; autocomplete responses could overwrite newer queries; article CSS targeted unused selectors; two related/sidebar pill paths invented fallback shape, color, and imprint values when descriptors were absent; a one-item medication list offered a pair-checker action that requires two inputs.
- **Remediation:** Boxed styling requires explicit boxed/black-box text; inventory distinguishes external from same-origin fetches and maps template navigation declarations; comparison attributes are scoped row headers; feedback is described polite status; all cited colors meet contrast; every autocomplete response verifies the current query; actual article markup receives typography/layout rules; incomplete related/sidebar pill descriptors now produce an explicit no-diagram empty state instead of fabricated visual values; the medication-list checker form renders only for at least two items and one item receives an explicit add-another state.
- **Evidence:** Eighteen targeted browser checks, runtime missing-descriptor and one-item-list tests, and the source-contract suite cover row headers, live feedback, stale-response suppression, contrast, article spacing, and the absence of descriptor fallbacks.

### Reviewer 13 — twelfth security/application remediation

- **Observation:** A stale PID file contained only an integer, and a dead/missing supervisor identity could allow reset while an orphan Flask worker remained in the old process group.
- **Remediation:** Each site supervisor atomically owns a JSON identity record binding PID, Linux start time, site, and port. Health and reset additionally validate the expected command line and process-group leadership before signaling that identity. Supervisor identity records persist after exit; reset refuses missing records and dead leaders whose process groups still exist, removes a dead identity only after proving its group absent, and binds readiness to the newly started PID.
- **Evidence:** Integration tests inject a reused PID, a missing boot identity, an orphaned process group, and an absent dead group; final container reset/restart tests exercise supervisor-owned records.

### Reviewer 14 — twelfth through fourteenth task/verifier remediation

- **Observation:** Relation denials and list retractions could pass token co-occurrence checks; later corrections could use unparsed synonyms, while unrestricted correct prose and incidental numbers could be rejected by fixed vocabularies.
- **Remediation:** Every task question now declares a closed, task-specific JSON result schema. The verifier rejects malformed JSON, duplicate/extra/missing keys, wrong types, out-of-domain values, incorrect list cardinality/order, prose outside the object, and any corrective field. Valid structured values are then rechecked by the existing route-specific ground-truth semantics. Free-form prose is explicitly outside the declared answer contract, eliminating reliance on open-ended synonym interpretation. Structured text comparison uses lossless Unicode NFKC/casefold/whitespace normalization rather than ASCII deletion, and integer arrays require exact integer element types.
- **Evidence:** 273 verifier cases cover all 21 structured positive entry points, pretty/key-order serialization variants, missing/wrong/extra fields for every task, duplicate keys, trailing prose, corrective keys, wrong types, relation denials, token soups, list composition, and trusted browser artifacts. The final real-browser run passes 21/21 tasks and 99/99 steps with the declared JSON answers.

### Reviewer 16 — eleventh integration/release remediation

- **Observation:** Git-ignored local secrets were not excluded from Docker context; rollback after a partial transaction begin could remove unmoved roots; a broken managed-root symlink was classified as absent.
- **Remediation:** Docker context excludes `.env` variants, `secrets.json`, PEM, and key files at every depth; asset transactions persist pre-move topology and restore only roots with completed backups while removing newly installed originally-absent roots; root symlinks are rejected before existence checks.
- **Evidence:** Integration tests cover Docker secret patterns, injected partial-begin rename failure, live and broken root symlinks, and repository asset-state parity.

## Canonical Drugs.com Seed

- Version: `drugs-com-source-v2`
- Bytes: `1146880`
- SHA-256: `edf03607f899f003f4be34471355dbc653ffaff037a1ca629552392ce769c1e5`
- Catalog SHA-256: `0048909eebc40a017c99cdc08f4fab89760035bc5bcbc476c5fb3a7da4049d9f`
- Schema SHA-256: `6da3c89fdcb74ea817719a448c39bced05ee2b182b331b4cd6445a81f1dd390b`
- Reproducibility: byte-identical with `PYTHONHASHSEED=23` and `31`; `pysqlite3-binary==0.5.4` pins SQLite across host and Docker, and the Docker-generated SHA matches the manifest.

## Final Test Matrix

| Scope | Result |
|---|---|
| Drugs.com application, seed, integration, verifier positive/adversarial tests | 404 passed, including 273 verifier cases |
| Real browser tasks | 21/21 passed, 99 successful steps |
| Responsive/accessibility route matrix | 464 passed, 8 widths, 58 route/auth cases per width |
| Targeted keyboard/filter/navigation browser checks | 18/18 passed |
| No-JavaScript workflows | 12/12 passed |
| Walmart Careers regression | 297 passed, 16 subtests passed |
| Rotten Tomatoes regression | 66 passed, 4143 subtests passed, 28 SQLAlchemy legacy warnings |
| OSU regression | 25 passed, 264 subtests passed |
| TED regression | 27 passed, 291 subtests passed |
| Compass regression | 229 passed |
| Fresh HF archive fetch and asset/seed checks | 25 archives passed |
| No-cache Docker build | passed; post-commit digest recorded in the external completion packet |
| Candidate container | 25 roots passed; 25 seed DBs valid; 11 individual Drugs.com resets; 2 reset-all cycles; restart passed |
| Candidate process stability | control FDs 4→4; processes 52→52; zombies 0 |

## Deployment Boundary

The control plane is bearer-authenticated. The final public deployment should expose only Drugs.com port `40024` through host loopback port `8791`; control port `8101` should remain unpublished. Set `DRUGS_COM_SECURE_COOKIES=1` only when an HTTPS terminator is actually present; the requested plain-HTTP localhost deployment uses loopback binding instead.

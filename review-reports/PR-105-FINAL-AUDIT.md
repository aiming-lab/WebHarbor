# PR #105 independent review and remediation audit

## Scope

Two review passes examined `sites/healthline` in PR #105. Phase 1 was read-only and produced `_wh_review_tools/pr105-fixes/{issue-table.md,phase1-summary.md}`; phase 2 applied one local commit per issue. The audited tree is `a00324c9b75d584dc32b32e09b12ff00ef643bf2` on branch `review/pr-105` (the final docs commit on top of it adds this report); the PR head under review was `cdf58650634b5fd7b6fa8a2cfccedec085864c5c` (merge-base with origin/main `438a029c04d86b22c710ad5d985d1d1491d2cb98`). Phase 2 first merged current `origin/main` (`36004932bdf82afbe36dc14e00f66841eccf9946`) into the branch (commit `7bf63fd`) so the PR tree matches its own Dockerfile: before that merge the PR head registered 25 sites while the tree contained 17 site directories and no `scripts/check_asset_inventory.py`, so a clean `docker build` failed. All work is local: no push, no PR comment, no Hugging Face upload.

The system date during review is September 12, 2026. The container under test is `wh105-healthline-container` built from the worktree, publishing control plane `20011` and container port `40024` (healthline) as host `21054`.

## Agent findings and dispositions

| Review area | Finding on the original PR head | Verification and disposition |
|---|---|---|
| Assets, build and provenance | `.assets-revision` pinned the mutable ref `refs/pr/40` (HF PR #40 is closed and its commit is not on the dataset main branch); the PR tree also disagreed with its own registry and Dockerfile, so a clean build failed; 74 of 160 shipped images were unreferenced (57% of image bytes); no asset had a source URL, and the statin atorvastatin was illustrated with iron-supplement tablets. | **B1** pin replaced with an immutable commit sha resolved from HF PR #70 (`e168da1b…`, archive sha256 `e0a212ef…`, re-downloaded and verified); the upstream merge remains a blocker and is recorded as such. **B2** merged `origin/main` with explicit conflict resolutions (registry, Dockerfile count/EXPOSE, registry-consistent site list) and completed a cold build from the worktree (image `wh105-healthline:cold` = `97a46db254`, final image `50df9caa3b`). **B16** added a build-time prune that removes exactly the unreferenced files (72 files, 7.13 MB) and reports them. **B15** reassigned drug imagery by therapeutic class (single-image reuse 20 → 10, iron-supplement imagery now only on the iron-deficiency article and the anemia condition) and added an idempotent `migrate_seed.py` that aligns the downloaded seed database with the tracked catalog. **B17** added a tracked provenance manifest with per-file sha256/size; origin URLs could not be confirmed because `media.healthline.com` is unreachable from this environment (curl status 000) and that limitation is recorded in the manifest itself. |
| Application security and state integrity | A fixed Flask secret allowed session forgery; a non-numeric session user id produced HTTP 500; `GET /article/<slug>` mutated the database (view counter and reading history); logout was reachable by GET/HEAD; filters silently substituted defaults; registration had no format or length bounds; error pages were the framework defaults; `MAX_CONTENT_LENGTH` was unset. | **B3** secret now comes from `HEALTHLINE_SECRET_KEY` or a per-process random value (forged cookies are rejected, real sign-in still works). **B19** session user ids are parsed defensively (no 500 for `abc`/`inf`/empty/negative). **B14** the article GET is side-effect free and view recording moved to an explicit CSRF-protected `POST /article/<slug>/view`; after re-running all 20 tasks the 17 read-only tasks produce zero row changes. **B18** logout is POST-only with CSRF. **B20** registration/login/profile input is validated and bounded (RFC 6761 special-use TLDs still accepted). **B21** branded 400/404/413/500 handlers replace the framework pages. **B22** invalid filter/page/sort/search values return 400. **B25** an explicit 64 KiB body limit is configured. |
| Task quality and leakage | The authenticated header rendered `Saved (5)`, which is the answer to task 6; the Drugs A–Z cards rendered `drug_class`, which is half the answer to task 16. | **B10** the header no longer renders a count (verified with a fresh authenticated crawl; the count remains on the saved-list page). **B11** listing cards and the related-drug list show the therapeutic category instead of the class (the detail page still states the class). Post-fix leakage re-scan: no target answer is reachable from a listing page except the article titles that "find the article" tasks inherently display. |
| Verifier robustness | Verifiers read no screenshots (forged and 1×1 images passed), never compared the read-only database state, crashed with a traceback when a database was missing, accepted negated answers on 19/20 tasks, accepted wrong payloads on the two credential tasks, rejected correct answers containing words such as "Note", and failed every correct run when no LLM credentials were configured. | **B4** the harness contract is self-consistent: missing credentials SKIP the optional LLM check (deterministic verdict governs), `--base_url`/`--container` are honoured, and the documented path (`eval_judge.py --verifier True`, no LLM credentials, docker-fetched databases) grades a correct run PASS and a wrong run FAIL. **B5** screenshot binding (PNG decode, ≥320×240, ≥8 colours, ≥2 distinct frames) turns forged/tiny evidence into FAIL. **B6** read-only tasks now require every table to be row-for-row unchanged. **B7** missing/corrupt inputs produce structured JSON failures instead of tracebacks. **B8/B9** negation-aware, clause-scoped answer matching (whole-word negators, last-mention numbers, paired assertions) closes the negated-answer and false-negative cases. **B28** stateful tasks verify the payload: username and password work for the new account, the new password works and the old one stops working for the password change, and the save must be reported affirmatively. |
| UI, responsive behaviour and accessibility | Every route overflowed horizontally at 390 px and 320 px (header min-content 613 px); white-on-brand buttons were 2.96:1, navigation links 4.16:1, the evidence badge 4.07:1 and the logo accent 2.96:1, all below WCAG AA. | **B12** the header wraps and the search box shrinks (≤560 px breakpoint): 252/253 overflowing routes at 390/320 px became 0. **B13** introduced action/link/focus tokens (white on action 6.04:1, links 6.04/5.58/5.46:1, focus ring 7.57:1) plus visible focus rings; a pixel-verified re-check reports zero contrast failures and no element without a focus indicator. |
| Test coverage and documentation | The site shipped no test suite, its `.gitignore` comment contained a false claim about the repository-root ignore rule, `requirements.txt` was unpinned and omitted direct dependencies, and the READMEs still described 24 sites and ports up to 40023. | **B27** added a 27-test pytest suite covering seed idempotence, asset hashes, form prefill, read-only invariants, input validation, sessions, CSRF, logout, error pages, contrast tokens and the responsive rule; injecting the B14 and B11 defects makes it fail. **B23** corrected the comment (behaviour unchanged). **B24** pinned requirements; an environment built from the old file could not even import the app. **B2** updated both READMEs to 25 sites and port 40024. **B26** was left unfixed with a documented reason: `/_health` is the repository-wide convention shared by all 17 original sites and by `scripts/new_site.py`. |

## Ground truth for reviewed tasks

| Task | Ground truth derived from the seed database |
|---|---|
| `Healthline--0` | Vitamin D 101 article: "Most adults need 600 IU (15 mcg) per day" |
| `Healthline--1` | The Mediterranean Diet: A Complete Guide and Meal Plan (nutrition / Diets, 3 candidates) |
| `Healthline--2` | Lisinopril dosage: "Typical starting dose for hypertension is 10 mg once daily" |
| `Healthline--3` | Type 2 Diabetes symptoms: 8 listed; any 3 pass (increased thirst/frequent urination, hunger, weight loss, fatigue, blurred vision, sores, infections, darkened skin) |
| `Healthline--4` | The Top 10 Benefits of Walking Every Day: "around 30 minutes of brisk walking most days" |
| `Healthline--5` | Metformin serious side effects: "Lactic acidosis (rare but serious)" |
| `Healthline--6` | alice.j@test.com has 5 saved articles (saved_articles rows) |
| `Healthline--7` | saved_articles gains (alice, healthy-eating-guide); not present initially |
| `Healthline--8` | magnesium-benefits reviewer: Kim Chin, RD (registered dietitian) |
| `Healthline--9` | therapy-types: CBT "well supported for anxiety and depression" |
| `Healthline--10` | users gains myhealth2026@example.com / myhealth2026 with a working credential |
| `Healthline--11` | Sertraline (Mental Health Meds): "Typical starting dose is 50 mg once daily" |
| `Healthline--12` | Type 1 Diabetes overview: "an autoimmune condition"; Type 2 has no such wording |
| `Healthline--13` | omega-3-guide: "EPA and DHA … are the most biologically active forms" |
| `Healthline--14` | bob.c@test.com reading history: all 4 rows in section health-conditions |
| `Healthline--15` | atorvastatin interactions: "Grapefruit juice" (first item); warnings repeat it |
| `Healthline--16` | lisinopril = ACE inhibitor (high blood pressure); atorvastatin = Statin (LDL cholesterol) |
| `Healthline--17` | hypertension: symptoms say "Usually no symptoms (often called the 'silent killer')"; overview says it "can be detected with a simple measurement" |
| `Healthline--18` | carol.d@test.com password_hash changes and accepts NewPass456! while rejecting TestPass123! |
| `Healthline--19` | migraine-triggers: stress, sleep changes, skipped meals, foods/additives, bright lights, hormones; migraine condition: see a doctor if severe/sudden or with fever, stiff neck, confusion, weakness |

These values were derived from `instance_seed/healthline.db` (and cross-checked against `seed_data.py`: sections, authors, articles, conditions, drugs and users all match row-for-row, `ground_truth/ground_truth.json`).

## Validation

- Clean cold build from the worktree with the PR's own Dockerfile: PASS (`wh105-healthline:cold 97a46db25494`).
- Container from the final tree: 25/25 sites alive and ready, healthline on container port 40024 (host 21054), control plane /health `ok=true`; in-image site files match HEAD byte-for-byte.
- `/reset/healthline`: live database identical to `instance_seed` for 25/25 sites; `/reset-all`: 25/25 identical.
- Route sweeps at 1440/768/390/320 px (1016 page-load measurements, every route at every width): horizontal overflow, broken images, failed requests, external requests, console errors, page errors and dangling ARIA references are all zero.
- Before the fix, 252 of 253 routes overflowed horizontally at 390 and 320 px (up to 293 px); the final measurement set reports zero overflow at every width, with all routes measured at all four widths and the 1440/768 paths unchanged.
- Real-browser end-to-end runs: 20/20 tasks completed through visible-element locators from the home page; verifier positive controls: 20/20 PASS.
- Negative-sample matrix `positive_nav_answer`: 20/20 as expected — PASS.
- Negative-sample matrix `contradictory`: 20/20 as expected — PASS.
- Negative-sample matrix `answer_only`: 20/20 as expected — PASS.
- Negative-sample matrix `forged_screenshot`: 20/20 as expected — PASS.
- Negative-sample matrix `tiny_screenshot`: 20/20 as expected — PASS.
- Negative-sample matrix `truncated_trajectory`: 20/20 as expected — PASS.
- Negative-sample matrix `other_task_trajectory`: 20/20 as expected — PASS.
- Negative-sample matrix `readonly_db_mutation`: 17/17 as expected — PASS.
- Negative-sample matrix `negation`: 20/20 as expected — PASS.
- Negative-sample matrix `missing_after_db`: 3/3 as expected — PASS.
- Negative-sample matrix `missing_initial_db`: 2/2 as expected — PASS.
- Negative-sample matrix `wrong_payload`: 3/3 as expected — PASS.
- Targeted verifier controls: 7/7 as expected (correct answers containing "Note"/"another"/"none" now pass; two-symptom and two-trigger answers fail).
- Documented grading path (`agent_demo/eval_judge.py --verifier True`, no LLM credentials, databases fetched from the container): correct runs PASS for a read-only task, a save task and a password task; a contradictory answer control FAILs (`reason=answer_iu`).
- Post-fix answer-leakage re-scan: task-relevant forms arrive empty (profile edit is the documented exemption); invalid filters return 400 with no silent substitution; no listing page exposes a target answer except the article titles inherent to "find the article" tasks.
- Contrast and focus re-check with pixel sampling: 0 flagged text/background pairs (was 17 unique elements), 0 focusable elements without a visible indicator (300 inspected).
- Container-generated seed: regenerating `instance_seed` inside the image from `seed_data.py` yields row-identical data (only salted bcrypt hashes differ); an end-to-end task run on that seed passes its verifier.
- Regression suite `pytest sites/healthline/tests -q`: 27 passed; injecting the read-only-write defect or the drug-class leak makes the corresponding test fail.
- Asset integrity: 88 shipped images match `asset_provenance.json` sha256 values; referenced-but-missing images: 0; unreferenced images after the build-time prune: 0.

## Known limitations and blockers that require upstream action

| Item | Fact | Release condition |
|---|---|---|
| HF asset PR not merged | `.assets-revision` is the reproducible commit sha `e168da1bb117a66b27a778fb73889be7cd84c40f` (resolved from HF PR #70); it is not on the dataset main branch (`ad6f424f…`) and PR #70 is still open. Archive sha256 is `e0a212efecae1cc93882d8692889ecc8d5642804032a54c1a6622aec02f6081b` and size 12393920. | Merge HF PR #70, then re-pin to the merged main commit and re-verify the archive hash. |
| Unmerged-site stub archives in the dataset revision | The pinned revision (and current dataset main) also contain `drugs_com.tar.gz`, `fedex.tar.gz` and `webmd_doctor.tar.gz` for sites that are not in the registry. `scripts/fetch_assets.sh` globs `*.tar.gz`, so a bare run would extract three site directories that have neither `instance_seed/` nor a `.build-generated-seed` marker; `scripts/check_assets.sh` then reports "MISSING (required)" and `scripts/build.sh` aborts. Measured: `check_assets.sh` on the merged tree exits 0, and exits 1 when such a directory is present (`fixes/B2/check_assets_simulated_stub.txt`). | Maintainers should make the fetch registry-aware (match registered site names instead of globbing). That file is outside the authorised change scope for PR #105, so it is recorded only; the cold build here used the documented per-site fetch for all 25 registered sites and then built with the PR Dockerfile. |
| Image origin URLs unverified | `media.healthline.com` is unreachable from this environment (curl status 000), so per-asset source URLs could not be confirmed by re-download and hash comparison; the manifest states this per asset. | Re-resolve and record `source_url` from an environment with access to the upstream CDN. |
| No real LLM endpoint | The environment provides no `OPENAI_API_KEY`/`OPENAI_BASE_URL`/`JUDGE_MODEL`, so the verifier LLM branch and the LLM-as-judge mode were exercised only in their credential-less behaviour (SKIP, deterministic verdict governs). | Provide credentials and re-run both grading modes; the LLM check is deliberately optional and cannot override a deterministic failure. |

## Grading-strength changes

- One relaxation, deliberate and documented: when no LLM credentials exist, the optional LLM consistency check returns SKIP instead of FAIL. Before the fix a correct run was graded `pass=false, reason=answer_consistent` because the check could not run. Every deterministic gate (navigation, negation-aware answer match, database state, read-only equality, screenshot binding) remains mandatory and still fails wrong answers.
- Strengthened relative to phase 1: screenshot evidence binding, read-only database equality, negation-aware matching, stateful payload verification and structured failures moved the 20-task × 11-case matrix from 202/220 to 220/220 expected verdicts (`verifier_matrix/matrix_report.md` has an empty Gaps section).
- Site semantics change (not a grading relaxation): `GET /article/<slug>` no longer writes view counts or reading history; recording a view requires the explicit `POST /article/<slug>/view`. No task depends on implicit view tracking (task 14 reads pre-seeded history).
- Task-6 count source: the verifier accepts the count from the initial or the after database, which must agree under the read-only requirement; a run that saves an article is rejected by `tables_unchanged` (`verifier_matrix/targeted/T6_count_after_agent_saved_one`).
- Task-17 predicate aligned with the task text: the answer must name the condition and assert the detection method; repeating the "silent killer" nickname is no longer required (negated answers still fail).

## Evidence

- Phase-1 tables: `_wh_review_tools/pr105-fixes/{issue-table.md,phase1-summary.md}` (issue table now carries a phase-2 status column).
- Per-issue remediation evidence: `_wh_review_tools/pr105-fixes/fixes/<issue-id>/{repro,mutation,after}.txt` and `fixes/fix-status.md`.
- Browser runs, screenshots, databases: `_wh_review_tools/pr105-fixes/tasks/Healthline--*`; final validation battery: `_wh_review_tools/pr105-fixes/final/` (reset byte identity, responsive sweep, leak re-scan, accessibility, container-generated seed).
- Verifier matrices: `_wh_review_tools/pr105-fixes/verifier_matrix/{matrix_synth.json,matrix_positive.json,matrix_report.md,targeted/}`.
- Build evidence: `_wh_review_tools/pr105-fixes/logs/{purehead_build_full.log,docker_build_review_image.log}` and `fixes/B2/{repro,mutation,after,after_consistency}.txt`.

## Local commit list

Original PR commits (unchanged, not amended):

```
083a379 fix(healthline): rebase onto main, move to port 40016, clean assets
1ca0c9f Add Healthline task verifiers and judge rubrics
5d86aaf fix(healthline): hide drug_class from search cards (T16 anti-shortcut)
55aaf56 tasks.jsonl: fix stale web port (40015->40016) and enrich two rubrics
cdf5865 review(healthline): accurate verifier predicates, port 40024, integrate on current registry
```

Phase-2 asset-pin commit and integration merge:

```
de50489 fix(healthline): B1 pin assets to an immutable commit sha instead of the mutable refs/pr/40 ref
```


```
7bf63fd merge: integrate origin/main (3600493) into review/pr-105 so the PR tree matches its own Dockerfile and registry
```

Phase-2 remediation commits (one per issue, or one per coherent group where the change shares a single implementation). The commit that adds this report is the last commit on the branch ("docs(healthline): add the PR #105 final audit report"); its sha is deliberately not printed here because regenerating the report rewrites it:

```
01d8619 fix(healthline): B3 derive SECRET_KEY from the environment or a random per-process value
465f58b fix(healthline): B19 treat the session user id as untrusted input instead of int() on raw session data
bda0cf7 fix(healthline): B14 make GET /article/<slug> side-effect free and move view tracking to an explicit POST
72506e0 fix(healthline): B10 stop rendering the saved-article count in the global header
c46db85 fix(healthline): B11 hide drug_class from the Drugs A-Z cards and the related-drug list
7db73ce fix(healthline): B18 make logout POST-only with CSRF so GET/HEAD cannot sign the user out
3900287 fix(healthline): B20 validate and bound registration, login and profile input
575fa96 fix(healthline): B21 add branded 400/404/413/500 error handlers and templates
fc66d79 fix(healthline): B22 reject invalid filter, page, sort and search-scope values with 400
0001437 fix(healthline): B25 set an explicit MAX_CONTENT_LENGTH instead of relying on framework defaults
3b8d586 fix(healthline): B12 let the header wrap and the search box shrink so phones have no horizontal overflow
6b21ab8 fix(healthline): B13 add accessible action/link/focus tokens and visible focus rings
8f64dc5 fix(healthline): B15 assign medication-appropriate drug imagery and sync the seed DB via migrate_seed.py
d145806 fix(healthline): B16 prune unreferenced archive images at build time and report them
3f48ee8 fix(healthline): B17 add a tracked asset provenance manifest with per-file hashes
77c1058 fix(healthline): B23 correct the .gitignore comment about the repository-root scraped_data rule
b5fcaf4 fix(healthline): B24 pin the site requirements and declare every direct dependency
0340635 fix(healthline): B27 add a pytest regression suite for the site invariants
958df70 fix(healthline): B4+B7 make the verifier harness contract self-consistent and never crash on missing inputs
2a7b556 fix(healthline): B5+B6 bind screenshot evidence and require read-only databases to be unchanged
5e9d561 fix(healthline): B8+B9+B28 add negation-aware answer checks and stateful payload verification
c3d770b fix(healthline): B2 update the READMEs for the 25-site registry and port 40024
a00324c fix(healthline): B12 stack the detail header and wrap long words on small screens
```

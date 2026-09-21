# PR #106 independent review and remediation audit (sites/kaggle)

## Scope

Independent review of PR #106 head `78ef77b38b5b4065fcc9968334047c9e2ab10af5` against base/current main `36004932bdf82afbe36dc14e00f66841eccf9946`, covering the new `sites/kaggle` mirror, its 20 benchmark tasks, its 20 deterministic verifiers, the asset pin, and the shared registration files the site needs. Review and remediation were performed in the PR worktree `/data/zhaoyang-user-projects/websyn/pr106-review` (branch `review/pr-106`, HEAD `c1f79b5b534dea6f6e2f0f692bbffdc40a98191d`, 32 fix commits on top of the PR head). Raw evidence, scripts, screenshots, database snapshots and per-issue repro/mutation/after logs are retained outside the repository under `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr106-fixes/`; the stage-1 issue inventory is `issue-table.md` and the per-issue disposition table is `fixes/fix-status.md`.

The system date during review is September 12, 2026. The mirror's pinned clock is 2026-06-22, so every date-relative page is deterministic.

The runtime for review was the repository's own `webharbor:dev` image (unchanged pip pins: Flask 3.1.0, SQLAlchemy 2.0.36, SQLite 3.40.1) plus a container built from this PR's Dockerfile (`wh106-kaggle:dev`, `docker build --no-cache`). Site: host `21084` → container `40024`; control plane: host `20012` → container `8101`.

## Agent findings and dispositions

| Review area | Findings on the original PR head | Verification and disposition |
|---|---|---|
| Assets and registration (blockers) | The pinned revision carried no archive for the new site; the fetch gate compared archive counts against site directories; the site was absent from all three registries although its tasks declared port 40024; the only archive carrying the site's assets was rejected by the repository's own validator. | B1 pin moved to the resolved commit of the HF dataset PR that carries `kaggle.tar.gz` (seed content equals the code-generated seed 13/13 tables; every pre-existing archive unchanged). B2 coverage is now asserted per registered site name (unregistered archives are ignored). B3 registers kaggle at index 24 in `websyn_start.sh`, `control_server.py` and `EXPOSE 8100-40024`, and a new `scripts/check_site_registry.py` gate keeps the trio, the per-site `tasks.jsonl` ports and `verifier_path` entries in sync. B5 is **not fixed**: the archive's bare `kaggle/static` member must be re-packed and uploaded; the local tolerance change was reverted and the blocker is recorded. |
| Verifier contract | `eval_judge.py --verifier True` passes only `--run_dir`, while every verifier required `--initial_db/--after_db`; `resolve_db()` was a stub, so all 20 verifiers exited 2 and every task graded FAIL. | B4: the DB arguments are optional and `resolve_db()` implements the documented container fetch (explicit path wins; `$WH_CONTAINER`/`$WH_SITE`; structured FAIL when unavailable). Verified through the real harness: 20/20 PASS. |
| Verifier strength | Read-only tasks had no `tables_unchanged` check; screenshot checks were LLM-only and skipped (passed) without an endpoint; navigation gates matched URL substrings only (no page-level filter, no origin binding) and accepted trajectories recorded against the live upstream; answer matching ignored negation; malformed run directories raised instead of returning a verdict; truncated recordings passed. | H2 row-level read-only comparison; H3 deterministic screenshot binding (decodable PNG ≥200×120 ≥2000 B on the target page, valid final frame, ≥3 distinct frames); H6 filter/leaderboard gates for Kaggle--2/4/16/19; M10 local-origin binding (`origin_ok`); H7 negation-aware matchers; H8 `load_run()` never raises and `Judge.emit()` forces `run_dir_unreadable`; H9 `run_complete()` requires `terminated`/`agent_done`/final `done` step. The negative-sample matrix now runs 227 cases across all 20 tasks with zero mismatches; the one documented residual (a well-formed screenshot of a different real page) needs the LLM layer. |
| Application security and state | Shipped `SECRET_KEY` constant allowed cookie forgery; `load_user` raised on non-integer session ids; logout was a GET/HEAD route; `?next=` was used verbatim; no `MAX_CONTENT_LENGTH`; foreign keys were not enforced and account deletion left orphan rows; the dataset download route wrote the counter on GET; the email validator rejected the site's own `.test` domains. | H1 per-boot random key (`KAGGLE_SECRET_KEY` override); M1 guarded id conversion; M2 POST-only CSRF-protected logout (header control is a form, health probe updated); M3 `_safe_next` local-path-only redirects; L7 2 MiB body limit + 413 page; M8 `PRAGMA foreign_keys=ON` and dependency-ordered account deletion with rollback; L6 CSRF-protected POST download; L8 `OfflineEmail()` with `test_environment=True`. Each fix carries a repro, a mutation and an after log. |
| Task quality and leakage | Task 17's answer was the first hosted-competition card; the new-discussion forum silently defaulted to the first real forum and its validation error was not rendered; the notebooks sort control lacked a votes option and its default was unreachable; the standalone leaderboard route was orphaned. | L4 hosted competitions ordered by title; L2 explicit empty first choice plus `DataRequired`; L1 forum errors rendered; L5 votes option added with the default option matching the backend; L3 leaderboard tab links the standalone page. No task answer value is readable before the required navigation, no form arrives prefilled, no placeholder or aria-label carries an answer, and the agent prompt excludes the judge rubric (`logs/d6-leak-rescan.txt`). |
| UI, responsive behaviour, accessibility | Primary buttons were 2.13:1 and text links 2.74:1, tier badges 2.05–3.04:1, and `.field input:focus` set `outline:none` with a 2.13:1 border; at 768 px and 800 px the header overflowed by 50 px and clipped the auth buttons; several controls had no accessible name at all (the password form's three fields, listing filter selects, the join form's team name). | M5 introduces an action colour (`#0b6fa4`, 5.49:1 both directions), darkens the tier colours, adds a global `:focus-visible` ring and keeps brand cyan decorative; H4 moves the header breakpoint to 980 px; M4 associates every label and names every select. Four-width crawl: 236 page loads with zero overflow, broken images, failed requests, external requests or page errors; contrast sweep over 44 page-loads reports zero low-contrast text nodes apart from the documented emoji false positive (pixel-proven). |
| Assets and evidence integrity | The archive ships an empty managed root and seven duplicate image groups, one of which made a user's photo the fallback avatar; no asset inventory exists for the site. | M7a replaces the fallback with a letter tile and stops defaulting new accounts to the photo. M7b (duplicate filler images) and M6 (per-asset provenance) are **not fixed**: both need the asset archive to be re-packed and a manifest that only the asset author can source honestly. M9 (empty `static/external_cache`) is recorded as a low-impact archive entry. |

## Ground truth for reviewed tasks

Derived from the shipped seed database (`sites/kaggle/instance_seed/kaggle.db`), never from the task prose; every value below was also confirmed on the rendered page during the reviewer-driven flow (`logs/gt-and-page-check-1440.txt`).

| Task | Result derived from the seed |
|---|---|
| Kaggle--0 | `titanic-survival`, metric `Classification Accuracy` |
| Kaggle--1 | `credit-default-risk-2026`, metric `ROC AUC` |
| Kaggle--2 | most-upvoted climate dataset `Global Temperature Anomalies 1880–2025` (2240; runner-up 1842) |
| Kaggle--3 | `credit-card-fraud-transactions` download counter 233400 → 233401 |
| Kaggle--4 | leaderboard #1 `Gradient Surfers` 0.81342 (next `Boosted Beavers` 0.81197) |
| Kaggle--5 | `ResNet-50 Chest X-Ray Classifier`, license `Apache 2.0` |
| Kaggle--6 | `competition_entries(alice.j@test.com, llm-prompt-recovery).team_name = 'Data Wizards'` |
| Kaggle--7 | a `votes` row for alice on `world-happiness-report-2026` (2,987 → 2,988) |
| Kaggle--8 | a `bookmarks` row for bob on `titanic-top-3-percent` |
| Kaggle--9 | a `follows` row bob → `psi_grandmaster` |
| Kaggle--10 | `discussions` row authored by `alicejdata`, title `How do you handle class imbalance?`, forum `Questions & Answers` |
| Kaggle--11 | `davidtran` comment count on `titanic-feature-ideas` 1 → 2, body thanking the author |
| Kaggle--12 | `users(david.k@test.com).location = 'Boston, United States'` (seed `Toronto, Canada`) |
| Kaggle--13 | Notebooks ranking #1 `psi_grandmaster` (Priya Sharma, 312,400 points) |
| Kaggle--14 | `Intro to Machine Learning` has 7 lessons |
| Kaggle--15 | `lgbm-baseline-fraud` best score 0.91205 (the only notebook linked to the fraud dataset) |
| Kaggle--16 | largest Featured cash prize `Home Credit Default Risk 2026` $100,000 (next $80,000) |
| Kaggle--17 | sara_timeseries's earliest deadline `Global Wheat Yield Forecast` 2026-08-01 (next 2026-08-20) |
| Kaggle--18 | `MNIST Handwritten Digits`, license `CC0: Public Domain` |
| Kaggle--19 | most-voted Python gold notebook `Titanic — Top 3% Solution Walkthrough` by `carolwong` (2610) |

## Validation

- Production grading command (`cd agent_demo && uv run python eval_judge.py --run_dir DIR --verifier True`) run after every verifier change: **20/20 PASS** on the real reviewer-driven flows, with no database paths passed (`logs/e2e-production-w1440.log`); the same run against the freshly built image gives 20/20 (`logs/d5-image-e2e.log`).
- Negative-sample matrix: **227 cases, 0 mismatches** (`logs/matrix-w1440.json`) — 20 positive, plus contradictory answer, answer-only, truncated recording, `max_steps`, other-task trajectory, 1×1 screenshot, single-frame screenshots, foreign-origin URLs, weak navigation, unchanged DB, wrong-user DB, extra writes on read-only tasks, and missing DBs.
- Mutation verification per fix: every `fixes/<id>/mutation.txt` re-injects the defect (or, for the not-fixed items, the reproduction is the injected defect) and shows the check failing, then passing after the revert.
- Four-width crawl (1440/768/390/320 × 57 routes = 236 page loads): zero horizontal overflow, broken images, failed requests, external requests and page errors; the 16 console entries are the deliberate 404 probes logging their own document status (`logs/d2-ui-crawl.txt`). Accessibility sweep over the same widths: zero dangling ARIA references, zero unnamed visible controls, and the only contrast entries are the pixel-proven emoji false positives.
- Header overflow sweep over 12 widths (320–1440) × 5 routes: PASS (`fixes/H4/after.txt`).
- Reset identity: `POST /reset-all` on the built image restores every site's live database to its seed byte for byte — 25/25 sha256 identical, including the six sites whose database filename is not `<site>.db`; per-site `POST /reset/kaggle` likewise (`logs/d1-reset-identity.txt`). The 20 production E2E resets are byte-identical too (`md5uniq=1` on every line of `logs/e2e-production-w1440.log`).
- Cold build: `docker build --no-cache -t wh106-kaggle:dev .` exits 0 (4.71 GB, `logs/cold-build.txt`); the container reports 25/25 sites alive and ready on `:8101/health` and 25/25 site roots HTTP 200.
- Container-generated seed: regenerating the seed inside the built image matches the shipped seed on all 13 tables row by row (`logs/d5b-container-seed.txt`).
- Leak re-scan: no task answer value is readable before the required navigation, no task form arrives prefilled, no placeholder/aria-label/option carries an answer, and the agent prompt excludes the judge rubric (`logs/d6-leak-rescan.txt`).
- Rejected verifiers on malformed input: seven malformed run directories return structured FAIL with reason `run_dir_unreadable`, no tracebacks (`fixes/H8/after.txt`).

## Evidence

- Stage-1 issue inventory with a repair-status column: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr106-fixes/issue-table.md`
- Stage-1 summary: `…/pr106-fixes/phase1-summary.md`
- Per-issue repro/mutation/after logs and status table: `…/pr106-fixes/fixes/` (`fix-status.md`, `<issue-id>/repro.txt|mutation.txt|after.txt|blocked.txt`)
- Production verifier runs, one directory per task: `…/pr106-fixes/runs_real_prod/Kaggle--N-w1440/{trajectory.json,eval.json,screenshots/}`
- Browser flows, step records and screenshots per task and width: `…/pr106-fixes/runs/Kaggle--N-w{1440,768,390,320}/`
- Route crawl and accessibility sweeps: `…/pr106-fixes/crawl/`, `…/pr106-fixes/a11y/`, logs `d2-ui-crawl.txt`, `a11y-summary.txt`
- Negative-sample matrix and engine: `…/pr106-fixes/scripts/matrix.py`, results `logs/matrix-w1440.json`
- Database snapshots (seed, per-task after states, mutated variants): `…/pr106-fixes/db/`, `…/pr106-fixes/db-prod/`
- Asset pin evidence: `logs/pin-asset-check.txt`, `fixes/B1/pin-candidates.txt`, `fixes/B1/pin_decisive_test.txt`, `fixes/B5/blocked.txt`
- Build and reset-all validation: `logs/cold-build.txt`, `logs/d1-reset-identity.txt`, `logs/d5-image-e2e.log`, `logs/d5b-container-seed.txt`
- Leak and UI re-scans: `logs/d6-leak-rescan.txt`, `logs/d7-contrast-responsive.txt`

## Open blockers

1. `kaggle.tar.gz` as published contains a bare `kaggle/static` directory member and is rejected by `scripts/validate_asset_archive.py` (`ValueError: unexpected managed path: 'kaggle/static'`), so `scripts/fetch_assets.sh` cannot install the site's assets. Requires the author to re-pack the archive without that entry and upload it to `ChilleD/WebHarbor`.
2. HF dataset PR #74 (which carries the site's archive) is still open, so `.assets-revision` points at that PR's resolved commit rather than a `main` revision. Both blockers lift together.
3. No OpenAI-compatible endpoint is configured in this environment, so the LLM-anchored layer of the verifiers could only be exercised with a local stub; the deterministic residual recorded for fabricated screenshot content therefore remains the only unverified class of negative sample.

# OSU PR #120 — reviewed fixes and integration

Date: 2026-09-17. This integration preserves the commits from
[PR #120](https://github.com/aiming-lab/WebHarbor/pull/120) by @Lxr-max and adds
the follow-up review fixes. The original mirror was contributed by
@richard-peng-xia in [PR #12](https://github.com/aiming-lab/WebHarbor/pull/12).
The user requested a separate integration PR.

## What this delivers

PR #120 moves task-specific facts off listing cards and strengthens the 20
task verifiers, their rubrics, and the application/environment regression suite.
It also removes duplicate dean prefixes in the build-generated seed.
The follow-up fixes address defects reproduced during browser and grading review:

- Bind reported numbers to the correct entity and unit; reject swapped enrollment,
  title counts, team venues, monetary scales, credits/duration, and wrong winners.
- Bind GRE policy to the GRE assertion, and reject contradictory factual claims
  and extra degree types. Preserve concise correct answers, number words, and
  equivalent money/date/duration formats.
- Permit visible related-team links after an Athletics-rooted path while requiring
  both requested detail pages. Task 0 requires Academics, not an arbitrary
  homepage-to-Academics click.
- Correct the desktop news article's main/sidebar layout, remove the duplicated
  department prefix, and improve college-card metadata size and contrast.

The follow-up does not change PR #120's task questions, seed facts, image files,
or asset pins. Ground truth stays in reviewer-owned verifier code, not task rows.
Current main's registry and immutable asset pins are retained without changes.
OSU remains index 20 / port 40020.

## Verification and version boundaries

The original audit and corrected browser evidence are separate. The corrected
browser image uses PR #120 plus the follow-up fixes, on its historical 28-site
base. Its 20 fresh scripted UI runs each used a fresh browser context and reset
state, with desktop/mobile screenshots and initial/final SQLite snapshots.
These are scripted regressions using browser-grounded answers, not independent
LLM-agent attempts.

The integration candidate is `cdbc999d5d60c356e9eee0253dddf8dc4e43d4e0`, containing
PR head `858de51e388fa785bbbfd35cd20a26d4e0d1fe66`, follow-up `49bad53`, and main
`8abe530bf67334791fb6a8ea549151f8a2dfaeb1`. Integration required **no conflict
resolution**. All 67 tracked OSU files and all 19 freshly fetched OSU images are
byte-identical to the corrected browser-review checkout; the recorded changed-file
SHA-256 manifest also matches. Later report-only commits do not affect the image.

Completed integration checks:

- Fresh fetch, safe archive validation, extraction and inventory checks for all
  **35 sites**, using `scripts/fetch_assets.sh` in the new checkout.
- **36/36 tests passed**, running `sites/osu/verify/selfcheck.py` in an isolated
  temporary copy so its runtime/seed tests cannot alter a preview.
- **58/58 controls matched expected outcomes**, using the integration checkout's
  official `agent_demo/eval_judge.py --verifier True`: 12 former false accepts
  reject, 8 former false rejects accept, and 38 empty/homepage-only negatives reject.
- **20/20 saved corrected browser runs passed regrading** with the integration
  verifiers. This is regrading of saved runs, not 20 additional browser attempts.
- Python syntax compilation and `git diff --check` passed.

Full-image validation also passed:

- `./scripts/build.sh webharbor:pr120-integrated-20260917` completed successfully.
  Image ID: `sha256:ef63ab0a9cabb89e6491d4bc8e1d8d14a25fb8ea8a5afe8d990d3c7164edb320`
  (4,920,216,272 bytes; local test image only).
- Isolated container `wh-pr120-integrated-20260917`, control port 8420 and sites
  44000–44034: **35/35 alive and ready, 35/35 homepages HTTP 200**.
- All **25 OSU route/query combinations** in the saved workflows returned the
  same HTML as the corrected preview after normalizing CSRF form/meta tokens.
  An initial diagnostic only normalized form tokens and reported the expected
  differing meta token; those initial diffs are retained separately.
- After a diagnostic-only user-name mutation in the owned test DB,
  `POST /reset/osu` restored runtime and seed to identical bytes:
  SHA-256 `1b219c08d3c70bfb7a3e6f100114c846088994225c5c7a7d41baed73398c0b01`,
  MD5 `9245a33b2649e365fcb5896ca62e13b4`.
  This is also the corrected browser image's seed fingerprint.
- `POST /reset-all` completed in **1.16 seconds**; all 35 sites remained healthy
  and all 35 homepages returned HTTP 200 afterward.

The final runtime evidence is under `runtime-final/` in the integration evidence
directory. No repository GitHub Actions workflows are configured; the checks above
were run locally rather than represented as hosted CI results.

Asset dataset: `ChilleD/WebHarbor`.
Base pin: `2aaf9d598f3e71cddd17a4efcdfee7dd7c073337`.
AccuWeather scoped pin: `0a73c1c1ac2e47513389a8a1a67601f75c8c4150`.
OSU archive SHA-256:
`1fc684a25890262137714b56577cd8bcbe0c5a867c65da12f3d45ab7662949f7`.

## Per-task review and GIF index

All 20 tasks were feasible through the UI. All corrected runs passed the primary
grader with unchanged task DB state. Each row maps to
`gifs/before/task-NN.gif`, `gifs/after/task-NN.gif`, and `after/task-NN/eval.json`
inside the evidence package. The HTML gallery links actions, screenshots, text,
and grades for every task.

| Task | Required page/workflow | Before → corrected | Findings / coverage |
|---|---|---|---|
| 00 | Academics / Fisher dean | PASS → PASS | Concise answer; card readability |
| 01 | About / varsity sports | PASS → PASS | Concise count and number words |
| 02 | Athletics / football and wrestling | PASS → PASS | Listing-rooted related-team paths |
| 03 | Football / coach and record | PASS → PASS | Win/loss equivalents |
| 04 | Research-expenditure search / article | PASS → PASS | Money/date parsing; article layout |
| 05 | About / founding and original name | PASS → PASS | Browser regression |
| 06 | Research / TDAI | PASS → PASS | Browser regression |
| 07 | About / enrollment comparison | PASS → PASS | Entity-bound counts and difference |
| 08 | Academics / college comparison | PASS → PASS | Counts, winner and difference |
| 09 | Engineering program filter | PASS → PASS | Exact degree set and distinct count |
| 10 | Athletics / wrestling | PASS → PASS | Browser regression |
| 11 | Research / supercomputer center | PASS → PASS | Browser regression |
| 12 | Program search / JD | PASS → PASS | Credits and duration units |
| 13 | Departments / Mathematics | PASS → PASS | Browser regression |
| 14 | Athletics / football and basketball | FAIL → PASS | Valid related-team path; venue binding |
| 15 | Athletics / wrestling and fencing | PASS → PASS | Counts, winner and difference |
| 16 | MBA filter / program detail | PASS → PASS | GRE policy/date; department prefix |
| 17 | Cancer-research search / article | PASS → PASS | Article layout |
| 18 | Research / James institute | PASS → PASS | Browser regression |
| 19 | Research / clean hydrogen center | PASS → PASS | Browser regression |

Task 14's original FAIL records a verifier defect, not task infeasibility.
Synthetic controls are separate from real browser evidence and are not counted
as task completions. All 40 GIFs were decoded through every frame; adjacent JSON
manifests retain frame order, timing, and source-screenshot hashes. The gallery
was checked in a browser at desktop/mobile sizes.

## Evidence access and limits

The full local package is in the preserved `WebHarbor-pr120` worktree under
`.assets/reviews/pr120-fixes-20260916/`: `REPORT.md`, `index.html`, `manifest.json`,
`before/`, `after/`, `controls/`, `gifs/`, and `http-comparison/`. Heavy GIFs and
databases are intentionally not committed or included in the Docker image.
They have not been published to a public evidence host.

Forward server port **43220** to open the gallery at `http://localhost:43220/`.
The corrected preview is on **43020**, and the original preview on **42020**;
both remain untouched by integration validation. These URLs require forwarding
from the review workspace; they are not public GitHub evidence URLs.

New integration logs and copied regrading results live in
`WebHarbor-integrate-pr120/.assets/reviews/pr120-integration-20260917/`, including
the parameterized `recheck.py` harness and `runtime_check.py` diagnostics.

No secondary LLM judge ran because the API/model configuration was unset.
Explicit factual parsers are not unrestricted natural-language entailment;
passing targeted controls does not establish a general grader error rate.
Historical facts were not reverified against the live university website;
existing generic imagery and occasional unsupported emoji glyphs remain.
This work does not publish a Docker image or deploy a running environment.

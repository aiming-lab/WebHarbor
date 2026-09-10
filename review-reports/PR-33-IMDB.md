# IMDb reviewer validation

Status: **work in progress; not ready for merge**. Twenty distinct task candidates remain after quality review. All twenty have complete sealed UI runs, deterministic PASS and independent frozen-run PASS evidence. Owner visual acceptance remains pending, so the formal review gates stay sequential and this PR remains Draft. A local unit test, deterministic verdict, blind run-completion verdict or asset hash check does not imply visual acceptance.

This review preserves [@hqhq1025's original IMDb contribution, PR #33](https://github.com/aiming-lab/WebHarbor/pull/33)
and its commit history. The reviewer branch integrates main at `36004932bdf82afbe36dc14e00f66841eccf9946`, including
OSU, Rotten Tomatoes, Compass and Walmart Careers, and appends IMDb at **40024**
(25 registered sites).

## Asset and source corrections

The [reviewer asset PR #57](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/57)
adds only `imdb.tar.gz` relative to the current asset main. It remains open and
unmerged. The code pin uses its remotely verified union commit
`c2791ad0bd9a55c74046c6407566301b17348f50`: all 28 files from asset main
`18e64e4d230794f990199f3327432d26db36866f` are byte-identical, and the
reviewed IMDb archive is preserved as the sole additional file.

| Artifact | SHA256 |
|---|---|
| IMDb archive (27,385,423 bytes) | `5199d6d2601d070e09b235a149855435f8bb121c768ee5ab36fd6118bf830b74` |
| Corrected IMDb seed | `69f849b9c61fb71349958fdbedc301162881e3a171eb65098c2e5f6623b82471` |

An independently downloaded copy at that commit matches the local archive,
including every member hash. Relative to the original IMDb archive, only
`instance_seed/imdb.db` changes; every original image and cache file is retained.

The original loader accepted unrelated profile payloads under a requested
person ID. It now checks the canonical IMDb identity. The asset migration
uses exact official `nconst` records to correct 642 corroborated profile
collisions and canonicalize 47 uncertain alias/profile records, plus two
independently supported birth years. It also normalizes 390 complete release
dates without inventing missing dates. Memento and Schindler’s List now use
their canonical title years, while preserving their later regional release dates.
Credits, identifiers, synthetic users,
reviews, ratings and watchlists are preserved.

For 689 affected profiles, unsupported biography, birthplace and portrait
links are cleared; replacement text or portraits have not been generated.
This is a source-coverage limitation. It does not mean that every retained
image file was individually proven wrong. See the
[source provenance and reproducible migration](../sites/imdb/docs/seed-provenance.md).
The original [asset PR #23](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/23)
is linked to this candidate; maintainers should coordinate the two so that
the old seed is not reintroduced.

IMDb's live ratings, box-office totals and front-page content can change.
This mirror contains a fixed catalog; current source observations and
historical values must be distinguished. The local **Domestic box office**
page explicitly ranks catalog titles by cumulative US & Canada gross. It is
not represented as IMDb's dated weekend chart. Test users, watchlists,
personal ratings and user reviews are synthetic benchmark state.

## Task and scoring scope

The candidate retains original IDs `0, 2, 7, 9, 10, 12, 14, 15, 16, 17`
and retires `1, 3, 4, 5, 6, 8, 11, 13`. Earlier retirements cover duplicate/shallow
lookups with answers exposed on cards, a count of static filter options, and
helpfulness selection where the seed has only one review. The final quality pass
also removes tasks 3 and 4 because the first matching title detail exposes every
requested value, and task 8 because its actor/character/birth-year combination
has a stable common-knowledge shortcut. An extra same-page anchor click or a
required profile visit does not remove those design problems. All corresponding
site features and original frozen executions remain intact.

To meet the owner's minimum of twenty without restoring those weak tasks, the candidate adds IDs `18–27`. Six are read-only relations or calculations: constrained pair optimization, role-bound filmography intersection, full-filmography aggregation, cross-account set subtraction, duplicate-review grouping and calendar-interval comparison. Four are stateful: multi-item Watchlist qualification, cross-account recommendation transfer, new-account queue persistence and a review-derived personal-rating reconciliation. They are different capabilities rather than name or number substitutions. No prompt contains its answer.

The revisions add needed detail lookups, specify movie/TV scope, define ties,
distinguish monetary fields, and replace the two requests for an external
human's choice with deterministic selection from each synthetic user's
initial watchlist. Questions, English rubrics and verifier entry points are kept in
one-to-one correspondence; expected answers are not placed in task rows.

The verifiers derive expected entities and values from the before snapshot.
Read-only tasks compare every business table. Stateful tasks permit only
the specified row change and require local UI action and subsequent page
evidence. Alternative entry routes and equivalent displayed monetary units
are supported. Exact model prose is not required.

The [verifier interface](../sites/imdb/verify/README.md) runs offline with the
standard library. Synthetic tests cover ambiguous ties, entity/field binding,
failed or foreign navigation, wrong account/target, no-op changes, additional
writes and legitimate alternatives. The repository's native
`eval_judge.py --verifier True` has also been exercised with a synthetic
positive and a foreign-origin negative; both produced the expected verdicts.
These fixtures are not browser trajectories.

For the expansion, the task file and verifier routing remain one-to-one at twenty IDs. The full IMDb suite passes **289 tests** using the browser candidate's pinned Flask dependency versions. Focused expansion tests pass **115/115**, including wrong owner, partial result, extra write, arbitrary credential placeholder, incorrect grouping and field-binding negatives. Safe recorder placeholders `[SUPPLIED PASSWORD]` and `[REDACTED]` are accepted only when the snapshot password hash matches the task-supplied credential and the same-origin login/register transition succeeds.

## UI and functional review

The navigation now has an accessible click/keyboard menu and usable search;
home cards use the dark palette, charts show poster/rank rows, and title details
use a dark overview with a separate facts section. Desktop and 390px layouts
were checked in a real browser. Checked pages had no broken images or page-width
overflow; these checks do not establish full source fidelity.

The original contribution lacks trailer/Up next/editorial media, streaming and
showtime services, recent history, and a full external-service footer. The local
catalog contains 145 movies in its Top250 listing. Narrow search uses a second
row, and Roboto is not bundled. These inherited limitations and visual differences
remain explicit scope decisions; **owner visual acceptance is pending**.

| View | Original site | Before repair | Candidate |
|---|---|---|---|
| Home, 1440×900 | ![IMDb home](assets/pr33-imdb/source-home.jpg) | ![Original mirror](assets/pr33-imdb/before-home.jpg) | ![Candidate mirror](assets/pr33-imdb/candidate-home.jpg) |
| Dark Knight, 1280×720 | ![IMDb detail](assets/pr33-imdb/source-detail.jpg) | Original audit retained separately | ![Candidate detail](assets/pr33-imdb/candidate-detail.jpg) |

Source/before used IAB and candidate captures used Chrome; these are visual
comparisons, not a calibrated pixel regression baseline. Source advertising
and editorial content are dynamic. [Capture purposes and hashes](assets/pr33-imdb/evidence.json)
identify the included images.

All state-changing forms now use Flask-WTF CSRF protection, including both
logout entry points. Same-origin watchlist return paths are constrained,
overflowing year input returns 400, malformed email registration is rejected,
and invalid review scores cannot write a review. The default CSRF token expiry
remains enabled. The application keeps its existing Flask/Jinja stack.

A frozen guided browser audit covered registration/login, failed inputs,
watchlist add/remove, personal rating and written-review persistence. A real
form hosted on a different localhost port submitted a rating without a CSRF
token: the application returned 400 and the entire database remained unchanged.
[Rejection screenshot](assets/pr33-imdb/csrf-rejected.png). The audit exposed one
account-page GET logout link missed by handler tests; it was converted to a
protected POST form. Its focused real-browser recheck then confirmed logout through
the account body, an anonymous navigation bar, and unchanged database bytes.
[Post-fix confirmation](assets/pr33-imdb/account-logout.png). Out-of-range review
ratings were tested at the handler boundary; the browser UI only offers valid
scores, so no malformed browser selection is claimed.

## Recorded engineering results

For code `50bcce503637522d15bdafa533381204750f415f` and the pinned asset revision:

| Check | Observed result |
|---|---|
| Full environment HTTP sweep | 22/22 HTTP 200 before and after reset-all |
| Control plane | All 22 registered sites alive |
| IMDb dirty database reset | Synthetic canary removed; runtime bytes equal the pinned seed SHA256 above |
| reset-all | All 22 ready, 3.241 seconds |
| IMDb engineering suite | 146 tests passed in 13.018 seconds |

Local disk exhaustion interrupted unpacking after the full repository Dockerfile
had exported its image. After reclaiming only this review’s temporary build
context, that exact image started successfully and passed the 22-site checks.
The final local build reused this exact full image and copied only seven changed
IMDb files (two-year migration/manifest/tests/docs, corrected seed, and account
logout template/test). It completed with exit 0; no site directories were mounted
from the host. The regular source build below remains the reproduction path.

[Recorded mechanical output](assets/pr33-imdb/mechanical-results.json) and
[engineering test output](assets/pr33-imdb/engineering-tests.txt) are included
for independent inspection. These checks precede the offline parser-only fix.

The browser runtime image is
`sha256:74aec29b73596a5a11ba43a4a1d0b22b82a473b4d36fcb232c2235d83d4258e9`.
The final ten-task contract and scorer are commit
`a37df75a873842be0ed4510baab5dbff361ac9ad`.
Its complete local image is
`sha256:a7ee01b145cc1bd90511114d260211a176eb5ab41002095d9ed69fb1fa0dc7f0`.
Relative to the recorded browser image, only offline grading/tests/docs and the
retired task subset change. Its isolated, network-disabled full IMDb suite passed
**174 tests in 16.020 seconds**.
[Final test output](assets/pr33-imdb/engineering-tests-final.txt) and
[scorer identities, results and applicable/retired cases](assets/pr33-imdb/scoring-results.json)
are included. Application, asset, port and control-plane bytes are unchanged;
the recorded 22-site mechanics remain applicable. The ten retained task/rubric
rows are byte-identical to their executed definitions.

## Frozen task executions and scoring

The ten added candidates each have one complete canonical run and deterministic PASS, totaling **219 recorded steps** with no action or capture failure in the selected runs. Task 18 also preserves a complete one-step environment failure stopped at an incorrect viewport. Task 21 preserves an incomplete earlier attempt with no final answer or after snapshot; neither attempt is counted as a task or a passing run. Original run files were not rewritten when scoring-format false negatives were fixed.

The added set covers six read-only tasks (18–23) and four exact state transitions (24–27). Every read-only run leaves all business tables unchanged. The stateful runs constrain destination owner, permitted rows, preserved pre-existing state and required confirmation. Deterministic 10/10 is engineering evidence only; a separate frozen-run review also returned 10/10 PASS.
[Public expansion counts and limits](assets/pr33-imdb/task-expansion-summary.json) are recorded without private run contents.

The final native deterministic regrade passes **10/10 retained main runs** and
**3/3 separately recorded guided alternatives**: a different legal cutoff tie
(task 9), Watchlist row removal (15), and Most recent review confirmation (17).
All **30 applicable constructed cases (8 positive, 22 negative)**, seven historical
controls and one extra unit calibration case match their prior expectations.
The 529 original main/guided files are hash-preserved. Twelve retired input records
remain linked to historical results and are excluded from current totals.

Thirteen main executions were recorded before final quality review; **ten are
retained for the candidate**. Each has actual actions, screenshots, a final answer
and before/after snapshots. The selected ten contain 98 recorded steps and 80
successful substantive actions. The runner was isolated from source, hidden
answer keys and scoring outputs, but retained its own preceding UI context,
including retired tasks. These are not ten fresh-context trials or an estimate
of model success rate.
[Per-task results, paths and original final screenshot excerpts](assets/pr33-imdb/tasks/task-table.md)
include actual versions, hashes, failed attempts and context disclosures in
[structured form](assets/pr33-imdb/tasks/task-results.json). One final image does
not prove the full execution; complete original evidence was supplied for independent blind review.

The retained task 17 pilot keeps its r1 code/input hashes and HF
`4d5709e171d7c40fc742727adfa98b04b9023039`. The other nine used r2 code `50bcce5`
and current HF `e70f49d`. A file-by-file reuse audit found that the pilot's actual
pages and facts were unchanged: the later application change was account-body
logout, which it did not visit; the only data changes were two title years outside
its observed titles. None is relabeled as an execution at the final PR head.
Retirement only removes other task rows and their dedicated scoring entry points;
the retained questions and rubrics are unchanged.

The real runs exposed false rejections of task 17's headline reference,
task 0's rank prefixes/runtime difference, task 12's group labels, and task 16's
correctly reported previous rating. A guided row-Remove route also exposed a missed
nested button locator. The repairs distinguish those statements and controls
without relaxing task requirements. Wrong headline suffixes, ranks, comparison
differences, old/current ratings, entities and extra database writes remain
negative controls. Numeric “from 9 to 8” transitions are distinguished from the
series “From” before entity binding. For nested controls, the row title and origin
remain checked while only the actual child identifies the action. Original
failed verdicts and source run files remain unchanged.

The historical thirteen-task matrix passed 13 main regrades and four guided
alternatives, 34 constructed cases (9 positive, 25 negative), 11 reconstructed
historical controls and one additional unit calibration case. Those exact inputs
and outputs remain separate from the final ten-task regrade. Retired-task samples
are marked inapplicable to the current contract; they are not relabeled as current
successes. Fixtures are not browser runs and these counts do not establish overall
scorer accuracy. The public test suite reproduces the retained parser/state invariants.

Seven observed retained paths used at least five successful substantive actions;
tasks 0, 12 and 14 perform comparisons. Task 10's multiple constraints and tied
leaders, and tasks 15/16's personal initial-state selection and exact writes,
support the design judgment that precision can challenge a frontier model.
The observed routes do not prove a minimum over every legal path; empirical model
difficulty is **NOT_VERIFIED**.

## Independent frozen-run review

Claude Code returned **10 PASS / 0 FAIL** for the ten retained main executions
on 2026-09-08. The result identifies its model as `claude-fable-5-1`, as declared
by that reviewer session; this identity is not independently attested. The input
manifest and all 288 files, plus the received result SHA256, were independently
verified on receipt. See the [per-task summary, review method and limitations](assets/pr33-imdb/independent-review-summary.json).

The reviewer used task/rubric, original actions and answers, DOM, screenshots
and read-only before/after databases. Ten key screenshots were viewed; the other
98 PNGs were hash-checked. It reports no access to source, deterministic verdicts,
hidden answers or earlier review conclusions. The three guided alternatives were
not part of this blind review.

This result covers the original retained IDs `0, 2, 7, 9, 10, 12, 14, 15, 16, 17`. A separate neutral packet for IDs `18–27`, targeting code `3d9fc7205c55e7403c8cc8637675649710820b48`, was then reviewed by a session declaring `claude-opus-5`. Its 540-file manifest and received result hash were verified; it returned **10 PASS / 0 FAIL**. The reviewer replayed actions, checked same-run DOM evidence, recomputed derived quantities, and compared read-only before/after databases. For stateful runs it confirmed only the requested rows changed. See the [expansion review summary and limitations](assets/pr33-imdb/task-expansion-independent-review-summary.json).

Task 19 is evaluated from the amounts displayed by the mirror: `$30.1M / $52.0M` rounds to **57.9%**. Calculating from hidden raw values would produce 57.8%, but does not change the unique maximum. Task 26 completed its requested registration, sign-out/sign-in and Watchlist persistence flow, but its run-start and seal-time model, prior-answer-knowledge and intervention metadata disagree. The completion verdict therefore remains PASS on direct run evidence, while the run producer's provenance is not treated as a reliable independent-exploration attestation.

All ten labels agree with the prior deterministic results. Coordinator spot-checks
of tasks 9, 15, 16 and 17 against original DOM and full-table database differences
found no substantive disagreement. The seven read-only
runs leave identical database bytes; the three stateful runs each have only the
requested single-row change. The task 9 selector failure was recovered. For tasks
15 and 16, visible years exclude the unvisited alternatives without requiring
extra navigation absent from the task. Task 17 adds exactly one review; its
pre-existing review is not a new duplicate.

Together, the two reviews cover all twenty candidate task executions with **20 PASS / 0 FAIL**. These are judgments of the disclosed recorded runs. The input versions and reuse basis above remain explicit; no run is relabeled as having executed at a version it did not use. Source fidelity, owner visual acceptance, scorer-code correctness, runner-model provenance and empirical model difficulty are outside the blind-review conclusions.

## Reproduction

Fetch the pinned candidate and build the source branch:

```bash
./scripts/fetch_assets.sh
./scripts/build.sh webharbor:review-imdb-pr33
docker run -d --name wh-review033-candidate \
  -p 127.0.0.1:8961:8101 \
  -p 127.0.0.1:49000-49024:40000-40024 webharbor:review-imdb-pr33
```

IMDb is then available at `http://localhost:49024/`. Run engineering tests
with the image's pinned Flask dependencies:

```bash
docker exec wh-review033-candidate \
  python3 -m unittest discover -s /opt/WebSyn/imdb/tests -v
```

For a supplied run bundle, use an absolute run directory:

```bash
uv run --project agent_demo python agent_demo/eval_judge.py \
  --verifier True --run_dir /absolute/path/to/run \
  --out /absolute/path/to/separate-scoring-result.json
```

## Validation still required

- Final source/before/after visual evidence and owner-approved regression
  baseline, including explicit decisions on inherited content omissions.
- Maintainer handoff after the remaining visual acceptance; this PR stays Draft.

Neither the code PR nor the HF PR should be merged by the reviewer.

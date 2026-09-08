# IMDb reviewer validation

Status: **work in progress; not ready for merge**. This report will be updated
with the final candidate's browser runs and environment results. A local unit
test or an asset hash check does not imply visual or task acceptance.

This review preserves [@hqhq1025's original IMDb contribution, PR #33](https://github.com/aiming-lab/WebHarbor/pull/33)
and its commit history. The reviewer branch integrates main at `7269134e9db9d10b1a6ac321797be51c72bb1a36`, including
OSU at port 40020, and appends IMDb at **40021** (22 registered sites).

## Asset and source corrections

The [reviewer asset PR #57](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/57)
adds only `imdb.tar.gz` to the existing asset tree. It remains open and unmerged.
The code pin uses its remotely verified, immutable commit
`e70f49d8b6d0f32c940688e8e53e7c558f57a788`.
The existing 21 site archives, including OSU, retain their original hashes.

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

The candidate retains original IDs `0, 2, 3, 4, 7, 8, 9, 10, 12, 14, 15,
16, 17` and retires `1, 5, 6, 11, 13`. The retired items were duplicate or shallow
lookups whose complete answers were already exposed in the homepage/search
cards, a count of static filter options, or helpfulness selection where the
seed has only one review and therefore no meaningful comparison. Their corresponding site features
remain available. Thirteen is a quality decision, not a target quota.

The revisions add needed detail lookups, specify movie/TV scope, define ties,
distinguish monetary fields, and replace the two requests for an external
human's choice with deterministic selection from each synthetic user's
initial watchlist. Birth year is used where the seed has no supported
birthplace. Questions, English rubrics and verifier entry points are kept in
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

The validated local full image is
`sha256:74aec29b73596a5a11ba43a4a1d0b22b82a473b4d36fcb232c2235d83d4258e9`.
The two initial independent UI pilots have complete screenshots and before/after
snapshots. Task 3 passes the native deterministic evaluator. Task 17 revealed a
false negative in headline-summary parsing despite the correct persisted review;
the original verdict is retained. Commit `f98b5199c7c22ed9a59e34fd8b6e8c6da295f6ba`
fixes that offline parser: the same frozen execution now passes, and 50 state
verifier tests pass, including seven new methods with 54 positive/negative
variants. No task or browser behavior changed in that commit. The remaining
11 current tasks are being executed. No aggregate task pass rate or
independent-review verdict is claimed yet.

## Reproduction

Fetch the pinned candidate and build the source branch:

```bash
./scripts/fetch_assets.sh
./scripts/build.sh webharbor:review-imdb-pr33
docker run -d --name wh-review033-candidate \
  -p 127.0.0.1:8961:8101 \
  -p 127.0.0.1:49000-49021:40000-40021 webharbor:review-imdb-pr33
```

IMDb is then available at `http://localhost:49021/`. Run engineering tests
with the image's pinned Flask dependencies:

```bash
docker exec wh-review033-candidate \
  python3 -m unittest discover -s /opt/WebSyn/imdb/tests -v
```

For a supplied run bundle, use an absolute run directory:

```bash
uv run --project agent_demo python agent_demo/eval_judge.py \
  --verifier True --run_dir /absolute/path/to/run
```

## Validation still required

- Final source/before/after visual evidence and owner-approved regression
  baseline, including explicit decisions on inherited content omissions.
- Actual candidate task runs with screenshots and before/after snapshots,
  followed by deterministic scoring and adjudicated adversarial cases.
- Independent frozen-run review, reconciliation and maintainer handoff.

Neither the code PR nor the HF PR should be merged by the reviewer.

# Recreation.gov — reviewed PR #66 integration

## Scope and attribution

This candidate combines [PR #66](https://github.com/aiming-lab/WebHarbor/pull/66)
with the reviewed fixes. Original site work is by @Chubi-alt; original verifiers
and review follow-up are by @Django-Jiang. Their commits remain in the branch
history. This new integration PR delivers the combined result.

- Original PR head: `06566eef95b209b9b20aabd9fa7a3bec6096993d`.
- Reviewed code: `b95ad185e85d569af393d45db02a10a7a058f10c`.
- Integrated main: `2a9ca30b5fb9dbc4fcd52a814c92649b12b4a29b`.
- The integration report is documentation-only; site behavior and asset pins
  match the completed browser/build evidence.

## Corrections

- Preserve main's global asset pin; scope Recreation.gov to immutable HF revision
  `00faedd20a96b4b10d5013a1c07ace9472d7ee80`.
- Append Recreation.gov at port 40035, retaining the existing 35 site ports and
  synchronizing the registries, Docker EXPOSE, task URLs and setup documentation.
- Use offline deterministic grading of saved initial/final snapshots, exact
  permitted database deltas and navigation evidence; reject missing evidence.
- Bind review ownership to immutable user IDs, not display names, with an
  idempotent seed migration that leaves imported anonymous reviews unclaimed.
- Repair menu/photos controls and image URL prefixes; replace the externally
  dependent map with a clearly labelled offline location overview.
- Add positive-equivalent and targeted negative grading tests without weakening
  task requirements.

## Verification completed on the reviewed code

- Python syntax and seven verifier unittest methods pass.
- Full Docker image builds after fetching and validating pinned assets.
- 36/36 sites healthy and 36/36 homepages return HTTP 200.
- Recreation.gov reset, restart and reset-all restore/preserve byte-identical
  runtime and seed databases: MD5 `9888dad3f192c2621fb821f535df1c65`.
- Two independent original-seed migrations match; a second migration is a
  byte-preserving no-op.
- 20/20 scripted browser regressions complete and pass the official primary
  evaluator; 82/82 synthetic grading controls match their expected verdicts.
- A separate wrong-account browser reproduction correctly fails grading.
- All task final pages checked at desktop and mobile sizes; no broken images,
  horizontal document overflow, page errors or attempted external requests in
  the final probes.
- 20 GIFs contain 167 recorded steps. Frames, timing and source hashes were
  checked. The dashboard displays total and per-task counts verified against
  trajectories on desktop/mobile; navigation and layout checks are included.
- Local tested image: `webharbor:pr66-fixed-final-20260917`;
  ID `sha256:3c6e2853bc50f70b9722082fd478cd57bab058f3f954c48c5685566d66165256`.

These are source-informed scripted regression replays, not independent
LLM-agent discovery attempts. Synthetic controls and earlier failed attempts
are not counted in the 20 final runs or 167 steps. No secondary LLM judge ran.

Immediately before opening the integration PR, syntax, all seven unit tests,
the 36-site registry check, the required asset gate and the Docker build passed
again. The build reused cached layers and produced the identical image ID under
`webharbor:pr66-integration-20260917`. Read-only checks reconfirmed 36 healthy
sites, 36 HTTP-200 homepages, all 65 recorded source hashes and the saved task/GIF
evidence. The running preview was not reset during integration.

## Per-task evidence summary

| Task | Recorded steps | Browser / primary grader | Controls match |
| --- | --- | --- | --- |
| 0 · Camp availability | 12 | Complete / PASS | 3/3 |
| 1 · Point Reyes gallery | 7 | Complete / PASS | 4/4 |
| 2 · Inyo permit | 12 | Complete / PASS | 3/3 |
| 3 · SF tour comparison | 9 | Complete / PASS | 3/3 |
| 4 · Alaska cabin | 6 | Complete / PASS | 8/8 |
| 5 · Apostle permit | 6 | Complete / PASS | 3/3 |
| 6 · Online reservation fee | 4 | Complete / PASS | 3/3 |
| 7 · Planning article | 5 | Complete / PASS | 4/4 |
| 8 · America250 places | 3 | Complete / PASS | 3/3 |
| 9 · Three site passes | 11 | Complete / PASS | 4/4 |
| 10 · Minnesota tours | 7 | Complete / PASS | 3/3 |
| 11 · Save location | 12 | Complete / PASS | 4/4 |
| 12 · Checkout | 10 | Complete / PASS | 6/6 |
| 13 · Cancel reservation | 8 | Complete / PASS | 5/5 |
| 14 · Profile update | 10 | Complete / PASS | 4/4 |
| 15 · Register account | 8 | Complete / PASS | 5/5 |
| 16 · Submit review | 15 | Complete / PASS | 5/5 |
| 17 · Cumberland permit | 6 | Complete / PASS | 3/3 |
| 18 · Aravaipa permits | 6 | Complete / PASS | 4/4 |
| 19 · Add permit to cart | 10 | Complete / PASS | 5/5 |

## Evidence and limitations

Reviewer-local evidence is retained under
`.assets/reviews/pr66-fixed-final-20260917/` in the fix worktree. It includes
`REPORT.md`, `manifest.json`, ordered trajectories/screenshots, initial/final
snapshots, grading results, GIF manifests, browser checks and environment checks.
The original audit remains in the separate PR #66 audit worktree.

The fixed gallery is served locally at http://127.0.0.1:43667/ and the preview at
http://127.0.0.1:45035/. Forward those ports when accessing this workstation
remotely. These are local services, not publicly hosted PR attachments.
Raw benchmark answers, database snapshots and heavy GIF assets are deliberately
not committed.

The finite answer matcher is not a general natural-language reasoner; add
positive and nearby negative tests for additional valid phrasing. The offline
overview is not an interactive geographic map. Existing inherited media mappings
were retained, not subjected to a new full provenance audit.

GitHub source integration does not publish the Docker image or deploy a new
environment. Those release stages are outside this request.

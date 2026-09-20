# AKC reviewer validation

Status: **Draft; not ready for maintainer handoff.** The full-scroll task-path visual
correction and refreshed real-browser runs are complete. A new blind review and the
fresh full Docker build remain open gates.

This review preserves [@Sun-sunshine06's original AKC contribution, PR #40](https://github.com/aiming-lab/WebHarbor/pull/40)
as commit `83e9e6fb685bd2daf8b69aea2b0807e3add93f82`, with the contributor's
authorship unchanged. Reviewer fixes are appended on an independent branch. The branch
integrates `main` at `454e7a49c37abe7eb074f6c86200a1308f109740`, assigns AKC
port **40040**, and keeps the registry at 41 sites.

## Fixed candidate

| Item | Value |
|---|---|
| Executed visual/task fixed point | `420b54641adfca60635b03c981e768179cb071bd` |
| Canonical run | `candidate-006` |
| Base | `454e7a49c37abe7eb074f6c86200a1308f109740` (`main`) |
| Original contribution | `83e9e6fb685bd2daf8b69aea2b0807e3add93f82`, original author preserved |
| HF asset PR | [ChilleD/WebHarbor #97](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/97), open |
| Pinned HF revision | `dc253d3f17cb5d83ee00f9bbc2100a296126327d` |
| `akc.tar.gz` | SHA256 `a9a5f04d6bdc243b2714c5a056b31d3b134bdf8fed93a74db761f40feb301b36` |
| Seed `instance_seed/akc.db` | SHA256 `3910bdaef81e20cbdc6bd39a33c6019a56f4e2769e1b8e8001ba59b9c396b727` |

The HF archive was downloaded again by immutable revision and matched the local
archive. Its 45 managed members include the frozen seed, 24 breed images, and 16
source-backed task-path visual assets. The tracked inventory verifies all 40 images.

## Review findings and repairs

The original site supplied a useful Flask/Jinja foundation, AKC-shaped routes, seed
entities, and ten task ideas. The review found issues that prevented reliable
acceptance:

- the UI was sparse and visually distant from the live AKC site;
- the login page exposed seeded credentials;
- list cards disclosed facts that tasks were supposed to require opening detail pages;
- selector answers were posted without reproducible URL state;
- article identity and wording did not match the official AKC article;
- the seed was regenerated with salted password hashes instead of being immutable;
- tasks had no deterministic verifier or browser-evidence contract;
- state actions accepted invalid values and allowed duplicate saved/registration rows.

The candidate keeps the original framework and author contribution. It adds an
AKC-shaped responsive header and complete scrollable home, breed, comparison,
selector, search, advice/article, event, registration, and account paths; locally
bundled source assets; validated forms and uniqueness constraints; reproducible URLs;
an immutable seed; 13 offline verifiers; and focused tests. Credentials are no longer
rendered in the UI, and task-critical facts remain on their intended detail paths.

## UI and visual fidelity

The mirror and live source were captured at the same four viewports: 1440×900,
768×900, 390×844, and 320×568. The final matrix covers 11 task-path pages for both
source and mirror: **88 captures, 0 capture errors**. All **44 mirror captures** have
no horizontal overflow. Source cookie overlays were dismissed before capture.

| Live source | Original mirror | Repaired mirror |
|---|---|---|
| ![AKC source home](assets/pr40-akc/visual/source-home-1440.png) | ![Original AKC mirror](assets/pr40-akc/visual/baseline-mirror-home-1440.png) | ![Reviewed AKC mirror](assets/pr40-akc/visual/home-1440x900.png) |

| Repaired mirror | Evidence |
|---|---|
| 768×900 | ![AKC candidate at 768](assets/pr40-akc/visual/home-768x900.png) |
| 390×844 | ![AKC candidate at 390](assets/pr40-akc/visual/home-390x844.png) |
| 320×568 | ![AKC candidate at 320](assets/pr40-akc/visual/home-320x568.png) |

Manual comparison covered the full scroll range of home, breed listing/detail,
selector, comparison, search, article listing/detail, event listing, registration,
and login. The repair aligns content order, menu treatment, source-backed image
density, typography hierarchy, card/grid geometry, forms, and responsive collapse.
Compare-page full-height ratios versus source are 97% desktop, 91% tablet, 93%
mobile, and 93% narrow. The live site's rotating ads, transient campaign overlays,
commerce/video integrations, and arbitrary lazy-load whitespace are not reproduced.
Several live-source narrow pages themselves overflow; the mirror does not copy those
defects.

## Task and verifier quality

The accepted set has 13 tasks: nine read-only navigation/reasoning tasks and four
exact state-change tasks. Read tasks require filtered/search/account paths plus detail
facts or correctly bound comparisons. State tasks require the specified actor, UI
action, and exact SQLite delta, rejecting no-ops, wrong accounts, duplicate/extra
writes, and collateral changes.

After the final full-scroll correction, all tasks were rerun as `candidate-006` from a fresh
immutable seed through real Playwright Chromium actions. The runs contain 76 actions, step
screenshots, task text and final answers, and initial/after SQLite snapshots. All
13 passed `eval_judge.py --verifier True`. See the
[per-task table](assets/pr40-akc/tasks/task-table.md) and
[structured results](assets/pr40-akc/tasks/task-results.json).

The verifier suite covers all 13 positives, compare-order and repeated-query alternatives,
entity/value binding, knowledge shortcuts, wrong answers, non-empty extra query
narrowing, foreign origins, stale task text, failed actions, no-ops, wrong
actors/values, and collateral writes. Empty native GET controls are treated as absent,
while real extra narrowing remains rejected. A preserved pre-fix sample reproduces the
former false negative for legal selections accompanied by blank repeated controls.

Earlier blind results and the r2 packet predate the full-scroll visual correction and
are historical only. `candidate-006` is **pending a fresh r3 blind review**.

## Engineering results

| Check | Observed result |
|---|---|
| Refreshed UI runs | 13/13 completed, 76 recorded actions (`candidate-006`) |
| Deterministic grading | 13/13 PASS through `eval_judge.py --verifier True` |
| AKC app tests | 8/8 PASS |
| Verifier tests | 13/13 methods PASS; 73 subtests |
| Anonymous route sweep | 58/58 HTTP 200 |
| Registry | 41 sites consistent; ports 40000–40040 |
| Extracted assets | Repository check PASS; AKC inventory 40/40 |
| Visual matrix | 88/88 captured; mirror 44/44 without horizontal overflow |
| HF archive | remote immutable download matched; 45 managed members validated |
| Fresh full Docker build | **NOT RUN** — 41 GiB free; procedure requires 50 GiB before starting |
| Refreshed independent blind review | **PENDING** |

Failed diagnostic attempts are not counted as passes. In particular, stale preview
processes and unsafe atomic replacement of a database used by a pooled SQLite handle
were rejected; canonical state runs stop the preview, restore the seed, restart it,
and then execute.

## Remaining gates

1. Run the frozen replacement blind-review packet and reconcile its task verdicts.
2. Free enough disk to reach the 50 GiB pre-build threshold, then run the fresh full
   Docker build and final image-level health/reset checks.
3. Mark the Review PR ready only after both gates pass. Do not merge either PR from
   the reviewer account.

## Reproduction

Use the fixed branch and pinned assets:

```bash
./scripts/fetch_assets.sh
./scripts/build.sh webharbor:review-akc-pr40
./scripts/check_assets.sh
python3 scripts/check_site_registry.py
```

Then run the AKC application and verifier tests in the repository's supported Python
environment. The per-task verifier entry points are documented in
[`sites/akc/verify/README.md`](../sites/akc/verify/README.md).

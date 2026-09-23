# PR #163: America’s Health Rankings review and fixes

Review date: 2026-09-22. Original contribution: https://github.com/aiming-lab/WebHarbor/pull/163.
Reviewer branch: `review/pr163-fix`; worktree: `/data/WebHarbor-fix-pr163`.

## Findings and corrections

- The bookmark grader accepted an unrelated bookmark-title mutation. Exact row-delta checks now preserve unrelated bookmarks, users and other state, and constrain reading-history additions to visited pages and the correct account.
- Short tasks now compare two measures across two states with ranks, values, units and calculated gaps; compare Annual and Senior state rankings; or compare report scope and ranking tables. Sleep tasks use Maine and Montana because California lacks the required Sleep Position value.
- Comparison checks bind facts to the named measure, state and report edition. Annual and Senior overall ranks use their distinct source keys. Rank-gap statements are kept separate from each state's own rank.

All three sites now decode screenshot PNGs, enforce one exact trajectory origin (including port), reject incomplete database snapshot pairs, bind screenshots to the correct page, and require initial rows to match a frozen reviewed fixture. Composite-key tables are compared without collapsing rows onto a missing `id`.

## Browser and grading evidence

35 original and 35 corrected scripted Chromium task paths were recorded from isolated initial state. 29 tasks were revised. Corrected paths contain 6–19 observed task actions, totaling 438 actions plus 70 desktop/mobile viewport diagnostics. Counts exclude initial navigation and final answers; these observed paths do not prove a minimum possible number of actions.

Browser completion: 35/35. Official deterministic verifier: 35/35. No JavaScript page errors or mobile document overflow were observed in the corrected recordings. Final desktop/mobile screenshots were inspected. 39 verifier tests pass across the complete suite and the corrected honest-fixture rerun. The first complete suite had one failure in the newly added edition-rank check; its full 35-task honest-fixture matrix passed after correcting the Senior measure key and excluding rank-gap labels. Logs: `ahr-tests.log`, `ahr-honest-final.log`.

The batch has 35 declared grading controls with 35 expected outcomes, including natural paragraph equivalents and targeted wrong-answer, fabricated-fixture, invalid-screenshot, foreign-port, partial-snapshot and unrelated-state mutations. Original false-accept evidence is preserved separately. Synthetic controls and unit fixtures are not browser completions.

These are scripted visible-UI reviews with reference answers grounded in the displayed pages, not independent autonomous-agent attempts. The secondary LLM judge was not run. Bounded deterministic text parsers do not provide general semantic understanding or cryptographic proof of interaction.

[GIF dashboard](http://localhost:45054/) · [Preview](http://localhost:45052/) · [Task ledger](http://localhost:45054/ledger.json) · [Grading controls](http://localhost:45054/grading-controls.json).
Evidence root: `/data/pr162-164-review`. GIF timing is normalized; full-resolution action screenshots, baseline runs, final answers and verdicts are retained.

## Assets and integration validation

Required [HF asset PR #108](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/108) is merged. All three unchanged archives are pinned together at `83e6966f504612a656a451e396fe4bf7897f6d68`. The original 68 dataset files were preserved while adding these three bundles. A fresh fetch validated the combined 68-site registry and all 4,758 assets inventoried by these three contributions.

A combined Docker build passed using host networking because the environment's default Docker bridge is missing. Runtime checks passed for these three sites inside a network-isolated container: authenticated health reports each alive/ready, homepages return 200, two resets restore byte-identical seed databases, dirty state survives restart, and seed table hashes match the browser-reviewed fixtures. The aggregate health response is 503 because the other 65 sites were deliberately not started. Registry/README/EXPOSE/task URL checks preserve all existing 65 ports; these sites use 40065–40067 with no overlap. README keeps three site/port pairs per row in row-first order. No image publication or deployment is included.

Reviewed seed SHA-256: `8af669cb3574ae97b4a9bd1ac0354108e2ff74d3ba0025ccd1cd8fbbe41ee7f2`. Frozen table hashes: `sites/americas_health_rankings/verify/reviewed_seed.json`. No asset archives were repacked.

## Per-task results

Each row links the complete task, current GIF, grading verdict, desktop/mobile evidence and original trajectory. “Pass” means this recorded completion passed the primary verifier; page assessment covers the observed path.

| Task | Revised | Original actions | Corrected actions | Page/feasibility | Verifier | Evidence |
|---|---|---:|---:|---|---|---|
| America's Health Rankings--0 | Yes | 4 | 14 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-0) |
| America's Health Rankings--1 | Yes | 4 | 13 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-1) |
| America's Health Rankings--2 | Yes | 4 | 15 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-2) |
| America's Health Rankings--3 | Yes | 4 | 16 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-3) |
| America's Health Rankings--4 | Yes | 4 | 15 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-4) |
| America's Health Rankings--5 | Yes | 5 | 15 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-5) |
| America's Health Rankings--6 | Yes | 4 | 16 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-6) |
| America's Health Rankings--7 | Yes | 4 | 15 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-7) |
| America's Health Rankings--8 | Yes | 5 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-8) |
| America's Health Rankings--9 | Yes | 4 | 13 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-9) |
| America's Health Rankings--10 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-10) |
| America's Health Rankings--11 | Yes | 4 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-11) |
| America's Health Rankings--12 | Yes | 4 | 13 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-12) |
| America's Health Rankings--13 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-13) |
| America's Health Rankings--14 | Yes | 5 | 14 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-14) |
| America's Health Rankings--15 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-15) |
| America's Health Rankings--16 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-16) |
| America's Health Rankings--17 | Yes | 4 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-17) |
| America's Health Rankings--18 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-18) |
| America's Health Rankings--19 | Yes | 5 | 13 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-19) |
| America's Health Rankings--20 | Yes | 4 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-20) |
| America's Health Rankings--21 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-21) |
| America's Health Rankings--22 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-22) |
| America's Health Rankings--23 | Yes | 4 | 14 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-23) |
| America's Health Rankings--24 | Yes | 3 | 19 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-24) |
| America's Health Rankings--25 | Yes | 3 | 18 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-25) |
| America's Health Rankings--26 | Yes | 3 | 16 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-26) |
| America's Health Rankings--27 | No | 12 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-27) |
| America's Health Rankings--28 | No | 7 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-28) |
| America's Health Rankings--29 | Yes | 4 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-29) |
| America's Health Rankings--30 | No | 9 | 9 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-30) |
| America's Health Rankings--31 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-31) |
| America's Health Rankings--32 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-32) |
| America's Health Rankings--33 | Yes | 3 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-33) |
| America's Health Rankings--34 | No | 10 | 10 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#americas_health_rankings-34) |

## Final validation record

Final image: `webharbor:pr162-164-final`. Build log: `/data/pr162-164-review/build-validated.log`. Container results: `/data/pr162-164-review/docker-results.json`. The owned test container was removed; isolated previews and the GIF dashboard remain available.

The final integration tree is checked against the reviewed site-source hashes and combined validation tree before publishing. Original contribution and reviewer fix are merged in that order for each site, preserving ancestry. Actual PR and merge outcomes are recorded in the batch integration report.

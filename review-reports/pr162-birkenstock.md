# PR #162: Birkenstock review and fixes

Review date: 2026-09-22. Original contribution: https://github.com/aiming-lab/WebHarbor/pull/162.
Reviewer branch: `review/pr162-fix`; worktree: `/data/WebHarbor-fix-pr162`.

## Findings and corrections

- The checkout grader accepted the wrong ordered product and wrong shipping city. It now checks exact products, names, variants, quantities, prices, images, saved shipping address, and the requested saved card. Cart checks preserve existing lines.
- The order-detail layout overflowed on narrow screens. The summary now stacks and the line-item table scrolls within the viewport.
- Short tasks now require meaningful product/rating comparisons, account reward arithmetic, city store comparisons, order details, or policy research. The corresponding task text, rubrics, and deterministic checks were updated together.
- Added the missing asset/provenance notice.

All three sites now decode screenshot PNGs, enforce one exact trajectory origin (including port), reject incomplete database snapshot pairs, bind screenshots to the correct page, and require initial rows to match a frozen reviewed fixture. Composite-key tables are compared without collapsing rows onto a missing `id`.

## Browser and grading evidence

30 original and 30 corrected scripted Chromium task paths were recorded from isolated initial state. 22 tasks were revised. Corrected paths contain 6–19 observed task actions, totaling 259 actions plus 60 desktop/mobile viewport diagnostics. Counts exclude initial navigation and final answers; these observed paths do not prove a minimum possible number of actions.

Browser completion: 30/30. Official deterministic verifier: 30/30. No JavaScript page errors or mobile document overflow were observed in the corrected recordings. Final desktop/mobile screenshots were inspected. 38 verifier tests pass (33 original-contract tests plus 5 new evidence tests).

The batch has 35 declared grading controls with 35 expected outcomes, including natural paragraph equivalents and targeted wrong-answer, fabricated-fixture, invalid-screenshot, foreign-port, partial-snapshot and unrelated-state mutations. Original false-accept evidence is preserved separately. Synthetic controls and unit fixtures are not browser completions.

These are scripted visible-UI reviews with reference answers grounded in the displayed pages, not independent autonomous-agent attempts. The secondary LLM judge was not run. Bounded deterministic text parsers do not provide general semantic understanding or cryptographic proof of interaction.

[GIF dashboard](http://localhost:45054/) · [Preview](http://localhost:45051/) · [Task ledger](http://localhost:45054/ledger.json) · [Grading controls](http://localhost:45054/grading-controls.json).
Evidence root: `/data/pr162-164-review`. GIF timing is normalized; full-resolution action screenshots, baseline runs, final answers and verdicts are retained.

## Assets and integration validation

Required [HF asset PR #105](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/105) is merged. All three unchanged archives are pinned together at `83e6966f504612a656a451e396fe4bf7897f6d68`. The original 68 dataset files were preserved while adding these three bundles. A fresh fetch validated the combined 68-site registry and all 4,758 assets inventoried by these three contributions.

A combined Docker build passed using host networking because the environment's default Docker bridge is missing. Runtime checks passed for these three sites inside a network-isolated container: authenticated health reports each alive/ready, homepages return 200, two resets restore byte-identical seed databases, dirty state survives restart, and seed table hashes match the browser-reviewed fixtures. The aggregate health response is 503 because the other 65 sites were deliberately not started. Registry/README/EXPOSE/task URL checks preserve all existing 65 ports; these sites use 40065–40067 with no overlap. README keeps three site/port pairs per row in row-first order. No image publication or deployment is included.

Reviewed seed SHA-256: `4b604056ce9b8eb0df0df7225acd7887d3dfddc4305b4b340b79a879fc8f8ca0`. Frozen table hashes: `sites/birkenstock/verify/reviewed_seed.json`. No asset archives were repacked.

## Per-task results

Each row links the complete task, current GIF, grading verdict, desktop/mobile evidence and original trajectory. “Pass” means this recorded completion passed the primary verifier; page assessment covers the observed path.

| Task | Revised | Original actions | Corrected actions | Page/feasibility | Verifier | Evidence |
|---|---|---:|---:|---|---|---|
| Birkenstock--0 | Yes | 4 | 8 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-0) |
| Birkenstock--1 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-1) |
| Birkenstock--2 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-2) |
| Birkenstock--3 | Yes | 3 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-3) |
| Birkenstock--4 | Yes | 4 | 8 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-4) |
| Birkenstock--5 | Yes | 3 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-5) |
| Birkenstock--6 | Yes | 3 | 8 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-6) |
| Birkenstock--7 | Yes | 4 | 8 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-7) |
| Birkenstock--8 | Yes | 5 | 10 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-8) |
| Birkenstock--9 | Yes | 4 | 9 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-9) |
| Birkenstock--10 | Yes | 3 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-10) |
| Birkenstock--11 | Yes | 4 | 8 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-11) |
| Birkenstock--12 | Yes | 3 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-12) |
| Birkenstock--13 | Yes | 3 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-13) |
| Birkenstock--14 | No | 12 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-14) |
| Birkenstock--15 | No | 13 | 13 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-15) |
| Birkenstock--16 | No | 9 | 9 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-16) |
| Birkenstock--17 | No | 8 | 8 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-17) |
| Birkenstock--18 | No | 19 | 19 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-18) |
| Birkenstock--19 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-19) |
| Birkenstock--20 | Yes | 5 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-20) |
| Birkenstock--21 | Yes | 4 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-21) |
| Birkenstock--22 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-22) |
| Birkenstock--23 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-23) |
| Birkenstock--24 | Yes | 3 | 8 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-24) |
| Birkenstock--25 | Yes | 3 | 9 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-25) |
| Birkenstock--26 | Yes | 2 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-26) |
| Birkenstock--27 | Yes | 2 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-27) |
| Birkenstock--28 | Yes | 3 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-28) |
| Birkenstock--29 | Yes | 3 | 10 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#birkenstock-29) |

## Final validation record

Final image: `webharbor:pr162-164-final`. Build log: `/data/pr162-164-review/build-validated.log`. Container results: `/data/pr162-164-review/docker-results.json`. The owned test container was removed; isolated previews and the GIF dashboard remain available.

The final integration tree is checked against the reviewed site-source hashes and combined validation tree before publishing. Original contribution and reviewer fix are merged in that order for each site, preserving ancestry. Actual PR and merge outcomes are recorded in the batch integration report.

# PR #164: American Express review and fixes

Review date: 2026-09-22. Original contribution: https://github.com/aiming-lab/WebHarbor/pull/164.
Reviewer branch: `review/pr164-fix`; worktree: `/data/WebHarbor-fix-pr164`.

## Findings and corrections

- Direct application startup failed because importing the seed module registered a second SQLAlchemy app. The entrypoint now shares the running app module with the seed import.
- Long confirmation emails overflowed on mobile. Confirmation tables now wrap long values.
- Grading pooled reward facts across cards and accepted disclaimed answers. Checks bind rates, bonuses, statement balances and minimums to the correct cards and reject contradictory charge-card classification.
- Short tasks now compare card fees/welcome offers, banking APYs and bonuses, loan restrictions/APRs, statements, or hotel activity. Rubrics and verification changed with the tasks.
- Removed an unreferenced one-off inventory-building script; retained the inventory and provenance data.

All three sites now decode screenshot PNGs, enforce one exact trajectory origin (including port), reject incomplete database snapshot pairs, bind screenshots to the correct page, and require initial rows to match a frozen reviewed fixture. Composite-key tables are compared without collapsing rows onto a missing `id`.

## Browser and grading evidence

30 original and 30 corrected scripted Chromium task paths were recorded from isolated initial state. 16 tasks were revised. Corrected paths contain 6–13 observed task actions, totaling 271 actions plus 60 desktop/mobile viewport diagnostics. Counts exclude initial navigation and final answers; these observed paths do not prove a minimum possible number of actions.

Browser completion: 30/30. Official deterministic verifier: 30/30. No JavaScript page errors or mobile document overflow were observed in the corrected recordings. Final desktop/mobile screenshots were inspected. 22 verifier tests pass.

The batch has 35 declared grading controls with 35 expected outcomes, including natural paragraph equivalents and targeted wrong-answer, fabricated-fixture, invalid-screenshot, foreign-port, partial-snapshot and unrelated-state mutations. Original false-accept evidence is preserved separately. Synthetic controls and unit fixtures are not browser completions.

These are scripted visible-UI reviews with reference answers grounded in the displayed pages, not independent autonomous-agent attempts. The secondary LLM judge was not run. Bounded deterministic text parsers do not provide general semantic understanding or cryptographic proof of interaction.

[GIF dashboard](http://localhost:45054/) · [Preview](http://localhost:45053/) · [Task ledger](http://localhost:45054/ledger.json) · [Grading controls](http://localhost:45054/grading-controls.json).
Evidence root: `/data/pr162-164-review`. GIF timing is normalized; full-resolution action screenshots, baseline runs, final answers and verdicts are retained.

## Assets and integration validation

Required [HF asset PR #103](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/103) is merged. All three unchanged archives are pinned together at `83e6966f504612a656a451e396fe4bf7897f6d68`. The original 68 dataset files were preserved while adding these three bundles. A fresh fetch validated the combined 68-site registry and all 4,758 assets inventoried by these three contributions.

A combined Docker build passed using host networking because the environment's default Docker bridge is missing. Runtime checks passed for these three sites inside a network-isolated container: authenticated health reports each alive/ready, homepages return 200, two resets restore byte-identical seed databases, dirty state survives restart, and seed table hashes match the browser-reviewed fixtures. The aggregate health response is 503 because the other 65 sites were deliberately not started. Registry/README/EXPOSE/task URL checks preserve all existing 65 ports; these sites use 40065–40067 with no overlap. README keeps three site/port pairs per row in row-first order. No image publication or deployment is included.

Reviewed seed SHA-256: `24a708c4875c2e78099d7b06ce5194d72db9f598a0a773ccf7dc2360d7b7a868`. Frozen table hashes: `sites/american_express/verify/reviewed_seed.json`. No asset archives were repacked.

## Per-task results

Each row links the complete task, current GIF, grading verdict, desktop/mobile evidence and original trajectory. “Pass” means this recorded completion passed the primary verifier; page assessment covers the observed path.

| Task | Revised | Original actions | Corrected actions | Page/feasibility | Verifier | Evidence |
|---|---|---:|---:|---|---|---|
| American Express--0 | Yes | 4 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-0) |
| American Express--1 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-1) |
| American Express--2 | Yes | 4 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-2) |
| American Express--3 | Yes | 4 | 13 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-3) |
| American Express--4 | No | 9 | 9 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-4) |
| American Express--5 | No | 9 | 9 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-5) |
| American Express--6 | Yes | 3 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-6) |
| American Express--7 | Yes | 4 | 13 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-7) |
| American Express--8 | Yes | 3 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-8) |
| American Express--9 | Yes | 4 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-9) |
| American Express--10 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-10) |
| American Express--11 | Yes | 2 | 10 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-11) |
| American Express--12 | Yes | 3 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-12) |
| American Express--13 | Yes | 3 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-13) |
| American Express--14 | Yes | 3 | 12 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-14) |
| American Express--15 | Yes | 4 | 8 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-15) |
| American Express--16 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-16) |
| American Express--17 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-17) |
| American Express--18 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-18) |
| American Express--19 | No | 9 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-19) |
| American Express--20 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-20) |
| American Express--21 | No | 7 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-21) |
| American Express--22 | No | 9 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-22) |
| American Express--23 | Yes | 5 | 9 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-23) |
| American Express--24 | Yes | 4 | 8 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-24) |
| American Express--25 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-25) |
| American Express--26 | No | 7 | 7 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-26) |
| American Express--27 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-27) |
| American Express--28 | No | 11 | 11 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-28) |
| American Express--29 | No | 6 | 6 | Usable / completed | Pass | [GIF and details](http://localhost:45054/#american_express-29) |

## Final validation record

Final image: `webharbor:pr162-164-final`. Build log: `/data/pr162-164-review/build-validated.log`. Container results: `/data/pr162-164-review/docker-results.json`. The owned test container was removed; isolated previews and the GIF dashboard remain available.

The final integration tree is checked against the reviewed site-source hashes and combined validation tree before publishing. Original contribution and reviewer fix are merged in that order for each site, preserving ancestry. Actual PR and merge outcomes are recorded in the batch integration report.

# Dillard's: review and fixes for PR #185

Reviewed September 22, 2026. Original [PR #185](https://github.com/aiming-lab/WebHarbor/pull/185); separate reviewer continuation branch `review/pr185-fix`. Original contribution must merge before its reviewer continuation. Integration status is recorded separately after remote verification.

## Findings and fixes

- Initial mixed-price products show the full price range and selected regular-price variants no longer show a false discount. Selecting product size/color now updates its variant price, preserves quantity, and disables unavailable combinations. Fragrance task 3 is feasible directly on the product page without an unrequested login or cart workaround.
- Clarified the Capri Blue refill search and the specific Levi's 511 Slim Fit All Seasons Tech Jeans; the latter checks current price, original price and available size count.
- Bound fragrance prices to their sizes, accepting ordinary prose and ounces/dollars while rejecting swapped prices.
- Checkout grading preserves other users' carts and checks new order parentage, quantity, color and transaction owner.
- Replaced unsupported emoji controls with readable labels. Isolated application tests in temporary SQLite engines so they cannot overwrite/delete a running preview's database. Earlier contaminated browser attempts are retained; all 31 tasks were replayed after this fix.

All sites now decode screenshot PNGs, require paired saved snapshots, and validate initial logical tables against a frozen reviewed fixture. Origin checks include ports; duplicate query values are rejected. Rubrics and deterministic verifiers match the revised task outcomes. Ground truth remains outside agent-facing task definitions.

## Task difficulty and browser evidence

31 tasks reviewed; 18 task prompts revised. All originally observed paths with five or fewer actions were expanded with related outcomes, preserving the original objective and a mix of search, comparison, information extraction and account-state workflows. Current recorded paths use 6–14 task actions. These counts exclude initial navigation, final answers and viewport diagnostics; they are not lower bounds on every possible solution.

All 31 corrected browser paths complete and pass the official deterministic grader through `agent_demo/eval_judge.py --verifier True`. Evidence is scripted visible-UI review with reference-informed answers grounded in page content, not autonomous-agent performance. The secondary LLM judge was not configured and was not run. Desktop/mobile path checks found no remaining horizontal overflow, broken images or browser JS errors. Baselines, failed attempts and regraded originals remain archived.

[GIF dashboard](http://localhost:45074/) (forward port 45074). [Application preview](http://localhost:45073/).

## Validation and asset integration

Site tests: `52 passed, 180 subtests passed in 156.39s (0:02:36); after the final price-range fix: 31 passed in 5.05s; final grading regressions: 6 passed in 0.19s`. Across the batch, 35 targeted grading controls matched their declared expected outcomes, including corrupt/missing evidence, wrong origins, swapped facts, and forbidden state changes. Synthetic controls are separate from browser completions.

HF asset [PR #117](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/117) is confirmed merged. The unchanged source archive is included in merged immutable revision `f66a675e2fb8c352e562c8713f15f14b3c5f1713`; all pre-existing dataset files were preserved. A fresh full fetch validated 75 sites. All three sites' image inventories were checked and raster assets decoded.

The combined Docker build passed all 75 SQLite seed checks. Runtime checks scoped to these three sites passed authenticated alive/ready health, homepage 200, two byte-identical resets, dirty-state preservation on restart, and reviewed-fixture table matching. Image runtime sources match the reviewed files. Other sites were not started; aggregate health therefore intentionally returned 503. Build used host networking; runtime checks used a network-isolated container. No image publication or deployment was performed.

All 75 registered ports are unique; all 72 existing assignments remain unchanged. New assignments: FlightAware 40072, Chronicle Jobs 40073, Dillard's 40074. README retains three pairs per row in row-first order.

Upstream FlightAware and Chronicle pages were inspected. Dillard's upstream returned an Access Denied page; its review relies on captured source data and local UI, not a claim of current live-site parity.

Evidence: `/data/pr174-183-185-review`. Source: `/data/WebHarbor-fix-pr185`. Immutable HF pin, source hashes, asset hashes, tests, route comparisons and Docker checks are saved there.

## Per-task results

Each task link includes its GIF, trajectory/final answer, grader verdict, full-resolution screenshots and browser observations.

| Task | Revised | Before actions | Current actions | Browser / verifier | Evidence |
|---|---|---:|---:|---|---|
| Dillards--0 | yes | 3 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-0) |
| Dillards--1 | yes | 3 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-1) |
| Dillards--2 | yes | 4 | 13 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-2) |
| Dillards--4 | yes | 3 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-4) |
| Dillards--5 | yes | 4 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-5) |
| Dillards--6 | yes | 4 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-6) |
| Dillards--8 | yes | 4 | 10 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-8) |
| Dillards--9 | yes | 4 | 11 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-9) |
| Dillards--10 | yes | 3 | 10 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-10) |
| Dillards--11 | yes | 4 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-11) |
| Dillards--12 | yes | 2 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-12) |
| Dillards--13 | yes | 3 | 10 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-13) |
| Dillards--14 | yes | 3 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-14) |
| Dillards--22 | yes | 5 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-22) |
| Dillards--23 | yes | 4 | 10 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-23) |
| Dillards--25 | yes | 3 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-25) |
| Dillards--26 | yes | 3 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-26) |
| Dillards--27 | yes | 1 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-27) |
| Dillards--3 | no | blocked | 7 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-3) |
| Dillards--7 | no | 7 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-7) |
| Dillards--15 | no | 14 | 14 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-15) |
| Dillards--16 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-16) |
| Dillards--17 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-17) |
| Dillards--18 | no | 9 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-18) |
| Dillards--19 | no | 7 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-19) |
| Dillards--20 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-20) |
| Dillards--21 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-21) |
| Dillards--24 | no | 11 | 11 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-24) |
| Dillards--28 | no | 7 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-28) |
| Dillards--29 | no | 13 | 13 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-29) |
| Dillards--30 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#dillards-30) |

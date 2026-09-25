# Chronicle Jobs: review and fixes for PR #183

Reviewed September 22, 2026. Original [PR #183](https://github.com/aiming-lab/WebHarbor/pull/183); separate reviewer continuation branch `review/pr183-fix`. Original contribution must merge before its reviewer continuation. Integration status is recorded separately after remote verification.

## Findings and fixes

- Navigation parameters alone no longer establish arrival at a requested page; grading requires recorded observations and valid distinct frames.
- Bound the fellowship stipend and research allowance to their own values, rejecting swapped amounts.
- Corrected absolute share/RSS links to the assigned production port, 40073.
- Removed unused inventory/development work artifacts. The original Docker-dependent verifier test matrix was skipped (8 tests); the four added offline regression tests, real browser task grades and targeted controls were checked separately.

All sites now decode screenshot PNGs, require paired saved snapshots, and validate initial logical tables against a frozen reviewed fixture. Origin checks include ports; duplicate query values are rejected. Rubrics and deterministic verifiers match the revised task outcomes. Ground truth remains outside agent-facing task definitions.

## Task difficulty and browser evidence

30 tasks reviewed; 20 task prompts revised. All originally observed paths with five or fewer actions were expanded with related outcomes, preserving the original objective and a mix of search, comparison, information extraction and account-state workflows. Current recorded paths use 6–17 task actions. These counts exclude initial navigation, final answers and viewport diagnostics; they are not lower bounds on every possible solution.

All 30 corrected browser paths complete and pass the official deterministic grader through `agent_demo/eval_judge.py --verifier True`. Evidence is scripted visible-UI review with reference-informed answers grounded in page content, not autonomous-agent performance. The secondary LLM judge was not configured and was not run. Desktop/mobile path checks found no remaining horizontal overflow, broken images or browser JS errors. Baselines, failed attempts and regraded originals remain archived.

[GIF dashboard](http://localhost:45074/) (forward port 45074). [Application preview](http://localhost:45072/).

## Validation and asset integration

Site tests: `4 passed in 0.21s`. Across the batch, 35 targeted grading controls matched their declared expected outcomes, including corrupt/missing evidence, wrong origins, swapped facts, and forbidden state changes. Synthetic controls are separate from browser completions.

HF asset [PR #115](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/115) is confirmed merged. The unchanged source archive is included in merged immutable revision `f66a675e2fb8c352e562c8713f15f14b3c5f1713`; all pre-existing dataset files were preserved. A fresh full fetch validated 75 sites. All three sites' image inventories were checked and raster assets decoded.

The combined Docker build passed all 75 SQLite seed checks. Runtime checks scoped to these three sites passed authenticated alive/ready health, homepage 200, two byte-identical resets, dirty-state preservation on restart, and reviewed-fixture table matching. Image runtime sources match the reviewed files. Other sites were not started; aggregate health therefore intentionally returned 503. Build used host networking; runtime checks used a network-isolated container. No image publication or deployment was performed.

All 75 registered ports are unique; all 72 existing assignments remain unchanged. New assignments: FlightAware 40072, Chronicle Jobs 40073, Dillard's 40074. README retains three pairs per row in row-first order.

Upstream FlightAware and Chronicle pages were inspected. Dillard's upstream returned an Access Denied page; its review relies on captured source data and local UI, not a claim of current live-site parity.

Evidence: `/data/pr174-183-185-review`. Source: `/data/WebHarbor-fix-pr183`. Immutable HF pin, source hashes, asset hashes, tests, route comparisons and Docker checks are saved there.

## Per-task results

Each task link includes its GIF, trajectory/final answer, grader verdict, full-resolution screenshots and browser observations.

| Task | Revised | Before actions | Current actions | Browser / verifier | Evidence |
|---|---|---:|---:|---|---|
| Chronicle Jobs--0 | yes | 4 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-0) |
| Chronicle Jobs--1 | yes | 3 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-1) |
| Chronicle Jobs--2 | yes | 4 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-2) |
| Chronicle Jobs--3 | yes | 2 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-3) |
| Chronicle Jobs--5 | yes | 4 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-5) |
| Chronicle Jobs--6 | yes | 1 | 10 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-6) |
| Chronicle Jobs--7 | yes | 5 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-7) |
| Chronicle Jobs--8 | yes | 4 | 14 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-8) |
| Chronicle Jobs--10 | yes | 5 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-10) |
| Chronicle Jobs--11 | yes | 3 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-11) |
| Chronicle Jobs--12 | yes | 3 | 10 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-12) |
| Chronicle Jobs--13 | yes | 3 | 11 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-13) |
| Chronicle Jobs--14 | yes | 3 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-14) |
| Chronicle Jobs--15 | yes | 3 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-15) |
| Chronicle Jobs--18 | yes | 5 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-18) |
| Chronicle Jobs--21 | yes | 5 | 17 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-21) |
| Chronicle Jobs--24 | yes | 5 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-24) |
| Chronicle Jobs--27 | yes | 4 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-27) |
| Chronicle Jobs--28 | yes | 2 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-28) |
| Chronicle Jobs--29 | yes | 3 | 10 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-29) |
| Chronicle Jobs--4 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-4) |
| Chronicle Jobs--9 | no | 12 | 12 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-9) |
| Chronicle Jobs--16 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-16) |
| Chronicle Jobs--17 | no | 11 | 11 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-17) |
| Chronicle Jobs--19 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-19) |
| Chronicle Jobs--20 | no | 11 | 11 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-20) |
| Chronicle Jobs--22 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-22) |
| Chronicle Jobs--23 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-23) |
| Chronicle Jobs--25 | no | 8 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-25) |
| Chronicle Jobs--26 | no | 8 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#chronicle_jobs-26) |

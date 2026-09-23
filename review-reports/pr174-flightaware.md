# FlightAware: review and fixes for PR #174

Reviewed September 22, 2026. Original [PR #174](https://github.com/aiming-lab/WebHarbor/pull/174); separate reviewer continuation branch `review/pr174-fix`. Original contribution must merge before its reviewer continuation. Integration status is recorded separately after remote verification.

## Findings and fixes

- Fixed the Track a Flight form to search the selected airline and flight number, instead of interpreting the number as an origin airport.
- Added the missing viewport declaration and constrained navigation/photo menus and search controls to the mobile viewport.
- Login-only flight-board evidence no longer passes. Board checks require observed flight rows. Departure times, planned/current speeds and airline fleet counts must be attached to the right labels/entities.
- Alert changes must preserve all other users' alerts and every unrelated row.
- Removed an unused rubric-generation work artifact. Replaced an environment-specific seed MD5 test with a frozen logical-table contract; Docker reset still checks byte identity.

All sites now decode screenshot PNGs, require paired saved snapshots, and validate initial logical tables against a frozen reviewed fixture. Origin checks include ports; duplicate query values are rejected. Rubrics and deterministic verifiers match the revised task outcomes. Ground truth remains outside agent-facing task definitions.

## Task difficulty and browser evidence

30 tasks reviewed; 21 task prompts revised. All originally observed paths with five or fewer actions were expanded with related outcomes, preserving the original objective and a mix of search, comparison, information extraction and account-state workflows. Current recorded paths use 6–17 task actions. These counts exclude initial navigation, final answers and viewport diagnostics; they are not lower bounds on every possible solution.

All 30 corrected browser paths complete and pass the official deterministic grader through `agent_demo/eval_judge.py --verifier True`. Evidence is scripted visible-UI review with reference-informed answers grounded in page content, not autonomous-agent performance. The secondary LLM judge was not configured and was not run. Desktop/mobile path checks found no remaining horizontal overflow, broken images or browser JS errors. Baselines, failed attempts and regraded originals remain archived.

[GIF dashboard](http://localhost:45074/) (forward port 45074). [Application preview](http://localhost:45071/).

## Validation and asset integration

Site tests: `22 passed, 394 subtests passed in 172.44s (0:02:52)`. Across the batch, 35 targeted grading controls matched their declared expected outcomes, including corrupt/missing evidence, wrong origins, swapped facts, and forbidden state changes. Synthetic controls are separate from browser completions.

HF asset [PR #114](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/114) is confirmed merged. The unchanged source archive is included in merged immutable revision `f66a675e2fb8c352e562c8713f15f14b3c5f1713`; all pre-existing dataset files were preserved. A fresh full fetch validated 75 sites. All three sites' image inventories were checked and raster assets decoded.

The combined Docker build passed all 75 SQLite seed checks. Runtime checks scoped to these three sites passed authenticated alive/ready health, homepage 200, two byte-identical resets, dirty-state preservation on restart, and reviewed-fixture table matching. Image runtime sources match the reviewed files. Other sites were not started; aggregate health therefore intentionally returned 503. Build used host networking; runtime checks used a network-isolated container. No image publication or deployment was performed.

All 75 registered ports are unique; all 72 existing assignments remain unchanged. New assignments: FlightAware 40072, Chronicle Jobs 40073, Dillard's 40074. README retains three pairs per row in row-first order.

Upstream FlightAware and Chronicle pages were inspected. Dillard's upstream returned an Access Denied page; its review relies on captured source data and local UI, not a claim of current live-site parity.

Evidence: `/data/pr174-183-185-review`. Source: `/data/WebHarbor-fix-pr174`. Immutable HF pin, source hashes, asset hashes, tests, route comparisons and Docker checks are saved there.

## Per-task results

Each task link includes its GIF, trajectory/final answer, grader verdict, full-resolution screenshots and browser observations.

| Task | Revised | Before actions | Current actions | Browser / verifier | Evidence |
|---|---|---:|---:|---|---|
| FlightAware--0 | yes | 4 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-0) |
| FlightAware--2 | yes | 4 | 11 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-2) |
| FlightAware--3 | yes | 2 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-3) |
| FlightAware--4 | yes | 2 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-4) |
| FlightAware--5 | yes | 3 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-5) |
| FlightAware--6 | yes | 3 | 10 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-6) |
| FlightAware--8 | yes | 5 | 10 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-8) |
| FlightAware--9 | yes | 4 | 11 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-9) |
| FlightAware--10 | yes | 4 | 13 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-10) |
| FlightAware--12 | yes | 4 | 16 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-12) |
| FlightAware--13 | yes | 4 | 17 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-13) |
| FlightAware--16 | yes | 2 | 10 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-16) |
| FlightAware--17 | yes | 2 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-17) |
| FlightAware--18 | yes | 4 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-18) |
| FlightAware--19 | yes | 4 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-19) |
| FlightAware--20 | yes | 2 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-20) |
| FlightAware--21 | yes | 2 | 11 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-21) |
| FlightAware--25 | yes | 3 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-25) |
| FlightAware--26 | yes | 3 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-26) |
| FlightAware--27 | yes | 4 | 13 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-27) |
| FlightAware--28 | yes | 4 | 14 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-28) |
| FlightAware--1 | no | 9 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-1) |
| FlightAware--7 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-7) |
| FlightAware--11 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-11) |
| FlightAware--14 | no | 8 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-14) |
| FlightAware--15 | no | 6 | 6 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-15) |
| FlightAware--22 | no | 9 | 9 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-22) |
| FlightAware--23 | no | 8 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-23) |
| FlightAware--24 | no | 8 | 8 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-24) |
| FlightAware--29 | no | 7 | 7 | complete / pass | [GIF and findings](http://localhost:45074/#flightaware-29) |

# CA.gov: review and corrections for PR #167

Reviewed September 22, 2026. Original head: `89d9ac2245ee8155e001ce9184d7056ee8437260`. Reviewer branch: `review/pr167-fix`, preserving original ancestry. 30 tasks reviewed before and after corrections; 28 short tasks expanded. All 30 corrected runs pass the official deterministic grading entrypoint. Observed corrected paths use 6–13 task actions. These are observed scripted paths, not proofs of the minimum possible actions.

## Findings and fixes

The mobile service directory overflowed horizontally because Bootstrap row gutters extended outside a zero-padding container; scoped gutter styling fixes it. Feedback verification now preserves all prior rows. The license-filter answer must include all eight services (the prior check accepted seven). Park and beach counts, and service/department phone numbers, are bound to their corresponding clauses. Harder tasks combine related service searches, department contacts, eligibility, fees, filtering and feedback.

All four sites now decode screenshots rather than accepting fabricated PNG headers, check the complete origin including port and before/after URLs, bind screenshots to the page they depict, decode query parameters and reject duplicate values, and require paired initial/after snapshots. Frozen seed-table hashes prevent a fabricated starting catalog from becoming grading ground truth. Composite-key state preservation is enforced where applicable. Each expanded task requires all its component outcomes, with corresponding natural-language rubrics and deterministic verification. Ground truth remains outside agent-facing tasks.

Malformed partial snapshot packages fail closed at argument parsing; the official evaluator reports this as a verifier error rather than a structured task-level failure. Screenshot checks establish evidence consistency, not cryptographic proof of browser provenance.

## Evidence and validation

16 existing verifier tests with 162 subtests and 4 new tests passed.

Across the batch: 122/122 corrected browser paths pass official deterministic grading; 33/33 targeted positive/negative controls match their declared outcomes. Baseline evidence and failed harness attempts are retained separately. Upstream public pages for all four sites were opened and captured for reference. Browser evidence uses scripted visible-UI actions and reference-informed answers; it is not independent autonomous-agent performance. The secondary LLM judge was not run because its credentials/model were not configured.

HF asset PR [#111](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/111) is merged. All four unchanged archives passed validation, with 3,984 inventoried assets; prior dataset files were preserved. A fresh full fetch at `741c9e428835e9355a71ae64e28ac43aac57dcb0` validated all 72 sites. The combined image `webharbor:pr166-169-final` built successfully (`sha256:8009f47dc2b2caf8da384325773395d3aea9915b6c43f634f1f7e3c1eb0b20d1`). All 72 seeds passed its build gate. The four affected sites passed authenticated alive/ready health, homepage 200, two byte-identical resets, dirty-state preservation on restart and fixture-table matching. Runtime tests were scoped to these sites; aggregate health is intentionally 503 with the other 68 sites unstarted. Build used host networking because the host's default bridge is unavailable; runtime used an isolated network. No image publication or deployment was performed.

The existing 68 ports remain fixed. New site ports are Carnival 40068, CA.gov 40069, Coolmath4Kids 40070 and Chase 40071. Registries, README row-first three-pair table, Docker EXPOSE and task URLs agree. Preview: http://localhost:45062/ . Dashboard: http://localhost:45065/ (forward port 45065). All 122 GIFs decode; all 92 revised GIFs loaded in Chromium. Filters, task deep links, mobile layout and 488 evidence links passed. GIF timing is normalized; full-resolution screenshots and action records are retained.

Evidence root: `/data/pr166-169-review`; current tasks and verdicts under `corrected/`, original paths under `baseline/`, synthetic grading controls under `controls/`. The dashboard links task wording, screenshots, final answers, verdicts, browser findings and prior counts. Code/fixture fingerprints are in `reviewed-source-hashes.json` and `docker-results.json`. See the batch integration report for final PR URLs and merge commits.

## Per-task results

All rows below completed through the visible UI, passed the verifier, and have no recorded mobile horizontal overflow. Task actions exclude initial navigation, final answer and the two diagnostic viewport checks per task.

| Task and GIF | Revised | Original → corrected actions | Browser | Verifier | Evidence |
|---|---|---|---|---|---|
| [CA.gov--0](http://localhost:45065/#california_gov-0) | Yes | 3 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--0/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--0/review.json) |
| [CA.gov--1](http://localhost:45065/#california_gov-1) | Yes | 3 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--1/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--1/review.json) |
| [CA.gov--2](http://localhost:45065/#california_gov-2) | Yes | 5 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--2/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--2/review.json) |
| [CA.gov--3](http://localhost:45065/#california_gov-3) | Yes | 5 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--3/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--3/review.json) |
| [CA.gov--4](http://localhost:45065/#california_gov-4) | Yes | 4 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--4/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--4/review.json) |
| [CA.gov--5](http://localhost:45065/#california_gov-5) | Yes | 3 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--5/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--5/review.json) |
| [CA.gov--6](http://localhost:45065/#california_gov-6) | Yes | 4 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--6/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--6/review.json) |
| [CA.gov--7](http://localhost:45065/#california_gov-7) | Yes | 3 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--7/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--7/review.json) |
| [CA.gov--8](http://localhost:45065/#california_gov-8) | Yes | 5 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--8/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--8/review.json) |
| [CA.gov--9](http://localhost:45065/#california_gov-9) | No | 8 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--9/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--9/review.json) |
| [CA.gov--10](http://localhost:45065/#california_gov-10) | Yes | 1 → 6 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--10/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--10/review.json) |
| [CA.gov--11](http://localhost:45065/#california_gov-11) | Yes | 1 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--11/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--11/review.json) |
| [CA.gov--12](http://localhost:45065/#california_gov-12) | Yes | 1 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--12/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--12/review.json) |
| [CA.gov--13](http://localhost:45065/#california_gov-13) | Yes | 3 → 11 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--13/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--13/review.json) |
| [CA.gov--14](http://localhost:45065/#california_gov-14) | Yes | 3 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--14/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--14/review.json) |
| [CA.gov--15](http://localhost:45065/#california_gov-15) | Yes | 2 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--15/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--15/review.json) |
| [CA.gov--16](http://localhost:45065/#california_gov-16) | Yes | 2 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--16/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--16/review.json) |
| [CA.gov--17](http://localhost:45065/#california_gov-17) | Yes | 3 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--17/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--17/review.json) |
| [CA.gov--18](http://localhost:45065/#california_gov-18) | Yes | 4 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--18/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--18/review.json) |
| [CA.gov--19](http://localhost:45065/#california_gov-19) | No | 10 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--19/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--19/review.json) |
| [CA.gov--20](http://localhost:45065/#california_gov-20) | Yes | 3 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--20/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--20/review.json) |
| [CA.gov--21](http://localhost:45065/#california_gov-21) | Yes | 5 → 12 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--21/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--21/review.json) |
| [CA.gov--22](http://localhost:45065/#california_gov-22) | Yes | 5 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--22/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--22/review.json) |
| [CA.gov--23](http://localhost:45065/#california_gov-23) | Yes | 0 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--23/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--23/review.json) |
| [CA.gov--24](http://localhost:45065/#california_gov-24) | Yes | 4 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--24/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--24/review.json) |
| [CA.gov--25](http://localhost:45065/#california_gov-25) | Yes | 2 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--25/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--25/review.json) |
| [CA.gov--26](http://localhost:45065/#california_gov-26) | Yes | 3 → 13 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--26/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--26/review.json) |
| [CA.gov--27](http://localhost:45065/#california_gov-27) | Yes | 4 → 12 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--27/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--27/review.json) |
| [CA.gov--28](http://localhost:45065/#california_gov-28) | Yes | 2 → 6 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--28/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--28/review.json) |
| [CA.gov--29](http://localhost:45065/#california_gov-29) | Yes | 2 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/CA.gov--29/trajectory.json), [findings](http://localhost:45065/evidence/CA.gov--29/review.json) |

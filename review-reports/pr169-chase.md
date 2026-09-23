# Chase: review and corrections for PR #169

Reviewed September 22, 2026. Original head: `194942fc67857390c9641c3234692e7f2dc3a4a4`. Reviewer branch: `review/pr169-fix`, preserving original ancestry. 30 tasks reviewed before and after corrections; 19 short tasks expanded. All 30 corrected runs pass the official deterministic grading entrypoint. Observed corrected paths use 6–11 task actions. These are observed scripted paths, not proofs of the minimum possible actions.

## Findings and fixes

Account balances are now bound to checking/savings clauses, rejecting swapped values that previously passed. Harder tasks retain public card/account comparisons, calculators, branch lookup, account history and financial-state actions. The alert-task screenshot was inspected at full resolution: the original $1,000 alert is preserved and a separate requested $2,500 mobile-push alert is created correctly.

All four sites now decode screenshots rather than accepting fabricated PNG headers, check the complete origin including port and before/after URLs, bind screenshots to the page they depict, decode query parameters and reject duplicate values, and require paired initial/after snapshots. Frozen seed-table hashes prevent a fabricated starting catalog from becoming grading ground truth. Composite-key state preservation is enforced where applicable. Each expanded task requires all its component outcomes, with corresponding natural-language rubrics and deterministic verification. Ground truth remains outside agent-facing tasks.

Malformed partial snapshot packages fail closed at argument parsing; the official evaluator reports this as a verifier error rather than a structured task-level failure. Screenshot checks establish evidence consistency, not cryptographic proof of browser provenance.

## Evidence and validation

41 existing verifier tests with 191 subtests passed; 4 focused evidence/semantic tests passed after the account-binding fix.

Across the batch: 122/122 corrected browser paths pass official deterministic grading; 33/33 targeted positive/negative controls match their declared outcomes. Baseline evidence and failed harness attempts are retained separately. Upstream public pages for all four sites were opened and captured for reference. Browser evidence uses scripted visible-UI actions and reference-informed answers; it is not independent autonomous-agent performance. The secondary LLM judge was not run because its credentials/model were not configured.

HF asset PR [#113](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/113) is merged. All four unchanged archives passed validation, with 3,984 inventoried assets; prior dataset files were preserved. A fresh full fetch at `741c9e428835e9355a71ae64e28ac43aac57dcb0` validated all 72 sites. The combined image `webharbor:pr166-169-final` built successfully (`sha256:8009f47dc2b2caf8da384325773395d3aea9915b6c43f634f1f7e3c1eb0b20d1`). All 72 seeds passed its build gate. The four affected sites passed authenticated alive/ready health, homepage 200, two byte-identical resets, dirty-state preservation on restart and fixture-table matching. Runtime tests were scoped to these sites; aggregate health is intentionally 503 with the other 68 sites unstarted. Build used host networking because the host's default bridge is unavailable; runtime used an isolated network. No image publication or deployment was performed.

The existing 68 ports remain fixed. New site ports are Carnival 40068, CA.gov 40069, Coolmath4Kids 40070 and Chase 40071. Registries, README row-first three-pair table, Docker EXPOSE and task URLs agree. Preview: http://localhost:45064/ . Dashboard: http://localhost:45065/ (forward port 45065). All 122 GIFs decode; all 92 revised GIFs loaded in Chromium. Filters, task deep links, mobile layout and 488 evidence links passed. GIF timing is normalized; full-resolution screenshots and action records are retained.

Evidence root: `/data/pr166-169-review`; current tasks and verdicts under `corrected/`, original paths under `baseline/`, synthetic grading controls under `controls/`. The dashboard links task wording, screenshots, final answers, verdicts, browser findings and prior counts. Code/fixture fingerprints are in `reviewed-source-hashes.json` and `docker-results.json`. See the batch integration report for final PR URLs and merge commits.

## Per-task results

All rows below completed through the visible UI, passed the verifier, and have no recorded mobile horizontal overflow. Task actions exclude initial navigation, final answer and the two diagnostic viewport checks per task.

| Task and GIF | Revised | Original → corrected actions | Browser | Verifier | Evidence |
|---|---|---|---|---|---|
| [Chase--0](http://localhost:45065/#chase-0) | Yes | 4 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--0/trajectory.json), [findings](http://localhost:45065/evidence/Chase--0/review.json) |
| [Chase--1](http://localhost:45065/#chase-1) | Yes | 1 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--1/trajectory.json), [findings](http://localhost:45065/evidence/Chase--1/review.json) |
| [Chase--2](http://localhost:45065/#chase-2) | No | 6 → 6 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--2/trajectory.json), [findings](http://localhost:45065/evidence/Chase--2/review.json) |
| [Chase--3](http://localhost:45065/#chase-3) | Yes | 4 → 11 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--3/trajectory.json), [findings](http://localhost:45065/evidence/Chase--3/review.json) |
| [Chase--4](http://localhost:45065/#chase-4) | Yes | 3 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--4/trajectory.json), [findings](http://localhost:45065/evidence/Chase--4/review.json) |
| [Chase--5](http://localhost:45065/#chase-5) | Yes | 3 → 11 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--5/trajectory.json), [findings](http://localhost:45065/evidence/Chase--5/review.json) |
| [Chase--6](http://localhost:45065/#chase-6) | Yes | 3 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--6/trajectory.json), [findings](http://localhost:45065/evidence/Chase--6/review.json) |
| [Chase--7](http://localhost:45065/#chase-7) | Yes | 3 → 11 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--7/trajectory.json), [findings](http://localhost:45065/evidence/Chase--7/review.json) |
| [Chase--8](http://localhost:45065/#chase-8) | Yes | 3 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--8/trajectory.json), [findings](http://localhost:45065/evidence/Chase--8/review.json) |
| [Chase--9](http://localhost:45065/#chase-9) | Yes | 5 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--9/trajectory.json), [findings](http://localhost:45065/evidence/Chase--9/review.json) |
| [Chase--10](http://localhost:45065/#chase-10) | Yes | 3 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--10/trajectory.json), [findings](http://localhost:45065/evidence/Chase--10/review.json) |
| [Chase--11](http://localhost:45065/#chase-11) | Yes | 6 → 11 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--11/trajectory.json), [findings](http://localhost:45065/evidence/Chase--11/review.json) |
| [Chase--12](http://localhost:45065/#chase-12) | Yes | 4 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--12/trajectory.json), [findings](http://localhost:45065/evidence/Chase--12/review.json) |
| [Chase--13](http://localhost:45065/#chase-13) | Yes | 5 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--13/trajectory.json), [findings](http://localhost:45065/evidence/Chase--13/review.json) |
| [Chase--14](http://localhost:45065/#chase-14) | Yes | 3 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--14/trajectory.json), [findings](http://localhost:45065/evidence/Chase--14/review.json) |
| [Chase--15](http://localhost:45065/#chase-15) | Yes | 4 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--15/trajectory.json), [findings](http://localhost:45065/evidence/Chase--15/review.json) |
| [Chase--16](http://localhost:45065/#chase-16) | Yes | 2 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--16/trajectory.json), [findings](http://localhost:45065/evidence/Chase--16/review.json) |
| [Chase--17](http://localhost:45065/#chase-17) | Yes | 4 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--17/trajectory.json), [findings](http://localhost:45065/evidence/Chase--17/review.json) |
| [Chase--18](http://localhost:45065/#chase-18) | No | 7 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--18/trajectory.json), [findings](http://localhost:45065/evidence/Chase--18/review.json) |
| [Chase--19](http://localhost:45065/#chase-19) | Yes | 5 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--19/trajectory.json), [findings](http://localhost:45065/evidence/Chase--19/review.json) |
| [Chase--20](http://localhost:45065/#chase-20) | Yes | 5 → 9 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--20/trajectory.json), [findings](http://localhost:45065/evidence/Chase--20/review.json) |
| [Chase--21](http://localhost:45065/#chase-21) | No | 10 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--21/trajectory.json), [findings](http://localhost:45065/evidence/Chase--21/review.json) |
| [Chase--22](http://localhost:45065/#chase-22) | No | 6 → 6 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--22/trajectory.json), [findings](http://localhost:45065/evidence/Chase--22/review.json) |
| [Chase--23](http://localhost:45065/#chase-23) | No | 7 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--23/trajectory.json), [findings](http://localhost:45065/evidence/Chase--23/review.json) |
| [Chase--24](http://localhost:45065/#chase-24) | No | 6 → 6 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--24/trajectory.json), [findings](http://localhost:45065/evidence/Chase--24/review.json) |
| [Chase--25](http://localhost:45065/#chase-25) | No | 8 → 8 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--25/trajectory.json), [findings](http://localhost:45065/evidence/Chase--25/review.json) |
| [Chase--26](http://localhost:45065/#chase-26) | No | 7 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--26/trajectory.json), [findings](http://localhost:45065/evidence/Chase--26/review.json) |
| [Chase--27](http://localhost:45065/#chase-27) | No | 7 → 7 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--27/trajectory.json), [findings](http://localhost:45065/evidence/Chase--27/review.json) |
| [Chase--28](http://localhost:45065/#chase-28) | No | 6 → 6 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--28/trajectory.json), [findings](http://localhost:45065/evidence/Chase--28/review.json) |
| [Chase--29](http://localhost:45065/#chase-29) | No | 10 → 10 | Complete | Pass | [Trajectory](http://localhost:45065/evidence/Chase--29/trajectory.json), [findings](http://localhost:45065/evidence/Chase--29/review.json) |

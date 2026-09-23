# Task coherence refinement: FlightAware, Chronicle Jobs and Dillard’s

Refined **61 of 91 tasks**, retaining the other 30 after reviewing their goals.
The affected merged contributions are #174/#188, #183/#189 and #185/#190.
This follow-up was reviewed on `review/task-coherence-174-183-185`, based on
`179566e0610a310c1179f1c6777df8336e4dabc9`.

[Current GIF dashboard](http://localhost:45084/) ·
[Chronicle Jobs--5](http://localhost:45084/#chronicle_jobs-5) ·
[Previous dashboard](http://localhost:45074/)

## What changed

Each replacement has one decision or outcome. Supporting facts determine that
outcome, rather than acting as independent questions appended to increase clicks.
The collection retains flight investigation, constrained product selection,
application planning, eligibility checks, source attribution, account operations,
and investigation of missing or inconsistent information.

- Chronicle Jobs--0 distinguishes appointment-level salary ranges in one posting,
  requiring the qualifying level rather than the summary salary.
- Chronicle Jobs--5 now identifies an exact-salary provost posting that meets a
  minimum salary, saves that posting, explains why the alternative fails, and
  preserves the existing shortlist. Salary research determines the saved result.
- Chronicle Jobs--18 now narrows an existing shortlist to its remote neuroscience
  role, preserving that job and removing only the other three saved jobs.
- FlightAware--2 compares durations within one historical window and identifies
  the extrema and spread, excluding future scheduled rows.
- Dillard’s--13 checks the actual requested jeans variant against the budget.
  A lower price advertised for another variant cannot satisfy it.
- Dillard’s--8 asks whether the displayed rating buckets account for the total
  review count, rather than silently treating inconsistent totals as equivalent.
- Chronicle Jobs--29 distinguishes the available teaser from an unavailable full
  article. The task does not require inventing arguments from subscriber content.

23 FlightAware, 20 Chronicle Jobs, and 18 Dillard’s prompts changed. Stable IDs and
verifier entrypoints are preserved. Rubrics and deterministic checks changed with
the prompts. The old component-bundling maps are empty. Revised read tasks require
correct entities, bound facts, decisions, and calculations; state tasks require
exact row changes while preserving unrelated users and tables. Current wording,
frozen initial fixtures, local origins including ports, decoded screenshots, and
observed page content remain part of the contract. Common currency forms and ISO
dates are accepted. The grader remains a deterministic phrase/value checker,
not a general natural-language semantic judge.

## Verification actually performed

- **91/91** fresh scripted visible-UI runs pass the official primary grader,
  `agent_demo/eval_judge.py --verifier True`.
- **50/50** targeted controls match their declared outcomes. These include
  positive currency/date/trajectory-schema equivalents, reversed comparisons,
  wrong eligibility decisions, wrong variant prices, missing saved changes,
  unrelated-user mutations, wrong origins, missing screenshots and stale prompts.
- FlightAware: **27 pytest tests and 394 subtests passed**.
- Chronicle Jobs: **189 pytest tests passed**, including regrading recorded
  browser packages and adversarial copies without resetting the preview. After
  the final appointment-level edit, its six focused regressions passed again.
- Dillard’s: **59 pytest tests and 180 subtests passed**, including application,
  seed-quality, synthetic verifier and focused coherence regressions.
- Syntax compilation and `git diff --check` pass.
- Registry check: **75 unique ports**, all 75 existing assignments preserved;
  affected defaults are 40072, 40073 and 40074. README ordering and exposure agree.
- Docker: build and all three affected-site health, 200-page, reset byte-identity, dirty restart preservation and frozen-fixture checks passed.

The default Docker bridge is absent on this host. `scripts/build.sh` reached the
Docker build after passing asset checks, then failed to create a network endpoint.
The same Dockerfile/context was rebuilt with `docker build --network=host`.
The runtime check starts only the three affected sites, using a network-isolated
container and internal ports, so it does not collide with previews or other sites.
Image: `webharbor:task-coherence-174-183-185` (sha256:9b1251c0a5746d96d5380a843b1a9f17792f5af2add7f3b0559f53a7f116321f).

## Evidence and practical limits

The new dashboard contains **91 new GIFs**, with revised tasks first and
before/after wording and action counts. All GIF frames decode; all 61 revised
GIFs were scrolled into view and decoded in a real browser. Filters, deep links,
364 evidence links, and desktop/mobile dashboard layouts were checked.
The site runs record **567 task actions** and
**715 diagnostic viewport checks** separately.
No recorded path probe reported mobile overflow, broken images, or page errors.
Desktop/mobile contact sheets for all 91 runs were visually inspected.
Representative full-resolution task screens were also inspected, including
saved-job preservation, chemistry requirements, rating totals, selected prices,
and airport remarks. The earlier dashboard, recordings, and failed intermediate
attempts are preserved.

**38 runs use five or fewer task actions.** Their prompts prioritize coherent
constraints or interpretation; adding unrelated operations would recreate the
problem this pass addresses. Action count is reported as observed, not inflated
with viewport probes or a prescribed navigation sequence.

These are reference-informed scripted browser reviews, not autonomous-agent
performance measurements. Answers were checked against visible mirror content.
The optional secondary LLM judge was not configured and was not run. No new
upstream crawl was needed for these task-only changes; the current reviewed
mirror and its existing source data were the feasibility boundary.

Worktree: `/data/WebHarbor-task-coherence`.
Evidence/scripts/failed attempts: `/data/task-coherence-174-183-185`.
Previews: FlightAware `http://localhost:45081/`, Chronicle Jobs
`http://localhost:45082/`, Dillard’s `http://localhost:45083/`.
Dashboard: `http://localhost:45084/` (forward port 45084 in a remote workspace).
The obsolete Chronicle browser driver for the old prompts was archived with the
review artifacts; its test matrix now validates saved current browser evidence.

## Assets and integration status

HF asset discussions **#114, #115, #117** were rechecked through the HF API and
are **merged**. Required archive contents and the asset pin are unchanged:
`ChilleD/WebHarbor@f66a675e2fb8c352e562c8713f15f14b3c5f1713`.
All 75 managed asset trees match the immutable tracked manifest digest
`cd394a7d23a7a0e5aeb7b8148d394f92df7e89b9ebfc4645ac3f7b177f18170d`.
This pass has no new archive or HF merge dependency. Integration into main was
authorized on 2026-09-23 after the refinement review. The accompanying GitHub PR
records the final merge status. The stricter future task-design requirements
(coherent natural instructions with more than five meaningful actions, enriching
the mirror from the original site where necessary) were recorded in the local
WebHarbor review skill. This reviewed batch retains the short-task limitations
disclosed above; it does not claim to satisfy that new action-count requirement.

## Per-task review ledger

Every row links the current GIF and its trajectory/answer, primary verdict, and
browser observations. The dashboard also exposes previous wording and footage.
“Retained” tasks were replayed in this pass, not carried forward as old evidence.

| Task | Revision | Previous → current actions | Primary grader | Evidence |
| --- | --- | ---: | --- | --- |
| [FlightAware--0](http://localhost:45084/#flightaware-0) | Refined | 9 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--0/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--0/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--0/review.json) |
| [FlightAware--1](http://localhost:45084/#flightaware-1) | Retained | 9 → 9 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--1/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--1/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--1/review.json) |
| [FlightAware--2](http://localhost:45084/#flightaware-2) | Refined | 11 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--2/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--2/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--2/review.json) |
| [FlightAware--3](http://localhost:45084/#flightaware-3) | Refined | 6 → 2 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--3/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--3/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--3/review.json) |
| [FlightAware--4](http://localhost:45084/#flightaware-4) | Refined | 7 → 2 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--4/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--4/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--4/review.json) |
| [FlightAware--5](http://localhost:45084/#flightaware-5) | Refined | 9 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--5/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--5/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--5/review.json) |
| [FlightAware--6](http://localhost:45084/#flightaware-6) | Refined | 10 → 3 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--6/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--6/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--6/review.json) |
| [FlightAware--7](http://localhost:45084/#flightaware-7) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--7/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--7/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--7/review.json) |
| [FlightAware--8](http://localhost:45084/#flightaware-8) | Refined | 10 → 5 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--8/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--8/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--8/review.json) |
| [FlightAware--9](http://localhost:45084/#flightaware-9) | Refined | 11 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--9/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--9/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--9/review.json) |
| [FlightAware--10](http://localhost:45084/#flightaware-10) | Refined | 13 → 5 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--10/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--10/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--10/review.json) |
| [FlightAware--11](http://localhost:45084/#flightaware-11) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--11/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--11/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--11/review.json) |
| [FlightAware--12](http://localhost:45084/#flightaware-12) | Refined | 16 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--12/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--12/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--12/review.json) |
| [FlightAware--13](http://localhost:45084/#flightaware-13) | Refined | 17 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--13/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--13/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--13/review.json) |
| [FlightAware--14](http://localhost:45084/#flightaware-14) | Refined | 8 → 8 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--14/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--14/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--14/review.json) |
| [FlightAware--15](http://localhost:45084/#flightaware-15) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--15/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--15/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--15/review.json) |
| [FlightAware--16](http://localhost:45084/#flightaware-16) | Refined | 10 → 2 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--16/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--16/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--16/review.json) |
| [FlightAware--17](http://localhost:45084/#flightaware-17) | Refined | 9 → 2 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--17/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--17/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--17/review.json) |
| [FlightAware--18](http://localhost:45084/#flightaware-18) | Refined | 7 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--18/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--18/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--18/review.json) |
| [FlightAware--19](http://localhost:45084/#flightaware-19) | Refined | 9 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--19/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--19/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--19/review.json) |
| [FlightAware--20](http://localhost:45084/#flightaware-20) | Refined | 6 → 2 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--20/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--20/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--20/review.json) |
| [FlightAware--21](http://localhost:45084/#flightaware-21) | Refined | 11 → 2 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--21/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--21/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--21/review.json) |
| [FlightAware--22](http://localhost:45084/#flightaware-22) | Retained | 9 → 9 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--22/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--22/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--22/review.json) |
| [FlightAware--23](http://localhost:45084/#flightaware-23) | Retained | 8 → 8 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--23/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--23/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--23/review.json) |
| [FlightAware--24](http://localhost:45084/#flightaware-24) | Retained | 8 → 8 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--24/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--24/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--24/review.json) |
| [FlightAware--25](http://localhost:45084/#flightaware-25) | Refined | 9 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--25/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--25/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--25/review.json) |
| [FlightAware--26](http://localhost:45084/#flightaware-26) | Refined | 8 → 3 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--26/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--26/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--26/review.json) |
| [FlightAware--27](http://localhost:45084/#flightaware-27) | Refined | 13 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--27/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--27/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--27/review.json) |
| [FlightAware--28](http://localhost:45084/#flightaware-28) | Refined | 14 → 4 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--28/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--28/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--28/review.json) |
| [FlightAware--29](http://localhost:45084/#flightaware-29) | Refined | 7 → 6 | PASS | [trajectory](http://localhost:45084/evidence/FlightAware--29/trajectory.json) / [verdict](http://localhost:45084/evidence/FlightAware--29/eval.json) / [browser](http://localhost:45084/evidence/FlightAware--29/review.json) |
| [Chronicle Jobs--0](http://localhost:45084/#chronicle_jobs-0) | Refined | 8 → 7 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--0/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--0/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--0/review.json) |
| [Chronicle Jobs--1](http://localhost:45084/#chronicle_jobs-1) | Refined | 8 → 3 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--1/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--1/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--1/review.json) |
| [Chronicle Jobs--2](http://localhost:45084/#chronicle_jobs-2) | Refined | 8 → 10 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--2/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--2/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--2/review.json) |
| [Chronicle Jobs--3](http://localhost:45084/#chronicle_jobs-3) | Refined | 6 → 10 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--3/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--3/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--3/review.json) |
| [Chronicle Jobs--4](http://localhost:45084/#chronicle_jobs-4) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--4/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--4/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--4/review.json) |
| [Chronicle Jobs--5](http://localhost:45084/#chronicle_jobs-5) | Refined | 7 → 19 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--5/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--5/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--5/review.json) |
| [Chronicle Jobs--6](http://localhost:45084/#chronicle_jobs-6) | Refined | 10 → 5 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--6/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--6/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--6/review.json) |
| [Chronicle Jobs--7](http://localhost:45084/#chronicle_jobs-7) | Refined | 9 → 7 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--7/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--7/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--7/review.json) |
| [Chronicle Jobs--8](http://localhost:45084/#chronicle_jobs-8) | Refined | 14 → 8 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--8/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--8/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--8/review.json) |
| [Chronicle Jobs--9](http://localhost:45084/#chronicle_jobs-9) | Retained | 12 → 12 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--9/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--9/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--9/review.json) |
| [Chronicle Jobs--10](http://localhost:45084/#chronicle_jobs-10) | Refined | 9 → 10 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--10/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--10/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--10/review.json) |
| [Chronicle Jobs--11](http://localhost:45084/#chronicle_jobs-11) | Refined | 7 → 12 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--11/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--11/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--11/review.json) |
| [Chronicle Jobs--12](http://localhost:45084/#chronicle_jobs-12) | Refined | 10 → 4 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--12/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--12/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--12/review.json) |
| [Chronicle Jobs--13](http://localhost:45084/#chronicle_jobs-13) | Refined | 11 → 10 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--13/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--13/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--13/review.json) |
| [Chronicle Jobs--14](http://localhost:45084/#chronicle_jobs-14) | Refined | 7 → 7 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--14/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--14/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--14/review.json) |
| [Chronicle Jobs--15](http://localhost:45084/#chronicle_jobs-15) | Refined | 7 → 5 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--15/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--15/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--15/review.json) |
| [Chronicle Jobs--16](http://localhost:45084/#chronicle_jobs-16) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--16/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--16/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--16/review.json) |
| [Chronicle Jobs--17](http://localhost:45084/#chronicle_jobs-17) | Retained | 11 → 11 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--17/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--17/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--17/review.json) |
| [Chronicle Jobs--18](http://localhost:45084/#chronicle_jobs-18) | Refined | 8 → 15 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--18/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--18/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--18/review.json) |
| [Chronicle Jobs--19](http://localhost:45084/#chronicle_jobs-19) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--19/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--19/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--19/review.json) |
| [Chronicle Jobs--20](http://localhost:45084/#chronicle_jobs-20) | Retained | 11 → 11 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--20/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--20/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--20/review.json) |
| [Chronicle Jobs--21](http://localhost:45084/#chronicle_jobs-21) | Refined | 17 → 8 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--21/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--21/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--21/review.json) |
| [Chronicle Jobs--22](http://localhost:45084/#chronicle_jobs-22) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--22/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--22/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--22/review.json) |
| [Chronicle Jobs--23](http://localhost:45084/#chronicle_jobs-23) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--23/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--23/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--23/review.json) |
| [Chronicle Jobs--24](http://localhost:45084/#chronicle_jobs-24) | Refined | 7 → 5 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--24/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--24/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--24/review.json) |
| [Chronicle Jobs--25](http://localhost:45084/#chronicle_jobs-25) | Retained | 8 → 8 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--25/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--25/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--25/review.json) |
| [Chronicle Jobs--26](http://localhost:45084/#chronicle_jobs-26) | Retained | 8 → 8 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--26/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--26/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--26/review.json) |
| [Chronicle Jobs--27](http://localhost:45084/#chronicle_jobs-27) | Refined | 6 → 8 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--27/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--27/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--27/review.json) |
| [Chronicle Jobs--28](http://localhost:45084/#chronicle_jobs-28) | Refined | 6 → 2 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--28/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--28/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--28/review.json) |
| [Chronicle Jobs--29](http://localhost:45084/#chronicle_jobs-29) | Refined | 10 → 2 | PASS | [trajectory](http://localhost:45084/evidence/Chronicle%20Jobs--29/trajectory.json) / [verdict](http://localhost:45084/evidence/Chronicle%20Jobs--29/eval.json) / [browser](http://localhost:45084/evidence/Chronicle%20Jobs--29/review.json) |
| [Dillards--0](http://localhost:45084/#dillards-0) | Refined | 6 → 5 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--0/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--0/eval.json) / [browser](http://localhost:45084/evidence/Dillards--0/review.json) |
| [Dillards--1](http://localhost:45084/#dillards-1) | Refined | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--1/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--1/eval.json) / [browser](http://localhost:45084/evidence/Dillards--1/review.json) |
| [Dillards--2](http://localhost:45084/#dillards-2) | Refined | 13 → 7 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--2/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--2/eval.json) / [browser](http://localhost:45084/evidence/Dillards--2/review.json) |
| [Dillards--3](http://localhost:45084/#dillards-3) | Retained | 7 → 7 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--3/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--3/eval.json) / [browser](http://localhost:45084/evidence/Dillards--3/review.json) |
| [Dillards--4](http://localhost:45084/#dillards-4) | Refined | 7 → 4 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--4/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--4/eval.json) / [browser](http://localhost:45084/evidence/Dillards--4/review.json) |
| [Dillards--5](http://localhost:45084/#dillards-5) | Refined | 7 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--5/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--5/eval.json) / [browser](http://localhost:45084/evidence/Dillards--5/review.json) |
| [Dillards--6](http://localhost:45084/#dillards-6) | Refined | 8 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--6/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--6/eval.json) / [browser](http://localhost:45084/evidence/Dillards--6/review.json) |
| [Dillards--7](http://localhost:45084/#dillards-7) | Retained | 7 → 7 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--7/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--7/eval.json) / [browser](http://localhost:45084/evidence/Dillards--7/review.json) |
| [Dillards--8](http://localhost:45084/#dillards-8) | Refined | 10 → 4 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--8/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--8/eval.json) / [browser](http://localhost:45084/evidence/Dillards--8/review.json) |
| [Dillards--9](http://localhost:45084/#dillards-9) | Refined | 11 → 4 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--9/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--9/eval.json) / [browser](http://localhost:45084/evidence/Dillards--9/review.json) |
| [Dillards--10](http://localhost:45084/#dillards-10) | Refined | 10 → 4 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--10/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--10/eval.json) / [browser](http://localhost:45084/evidence/Dillards--10/review.json) |
| [Dillards--11](http://localhost:45084/#dillards-11) | Refined | 8 → 4 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--11/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--11/eval.json) / [browser](http://localhost:45084/evidence/Dillards--11/review.json) |
| [Dillards--12](http://localhost:45084/#dillards-12) | Refined | 6 → 3 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--12/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--12/eval.json) / [browser](http://localhost:45084/evidence/Dillards--12/review.json) |
| [Dillards--13](http://localhost:45084/#dillards-13) | Refined | 10 → 5 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--13/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--13/eval.json) / [browser](http://localhost:45084/evidence/Dillards--13/review.json) |
| [Dillards--14](http://localhost:45084/#dillards-14) | Refined | 7 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--14/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--14/eval.json) / [browser](http://localhost:45084/evidence/Dillards--14/review.json) |
| [Dillards--15](http://localhost:45084/#dillards-15) | Retained | 14 → 14 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--15/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--15/eval.json) / [browser](http://localhost:45084/evidence/Dillards--15/review.json) |
| [Dillards--16](http://localhost:45084/#dillards-16) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--16/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--16/eval.json) / [browser](http://localhost:45084/evidence/Dillards--16/review.json) |
| [Dillards--17](http://localhost:45084/#dillards-17) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--17/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--17/eval.json) / [browser](http://localhost:45084/evidence/Dillards--17/review.json) |
| [Dillards--18](http://localhost:45084/#dillards-18) | Retained | 9 → 9 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--18/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--18/eval.json) / [browser](http://localhost:45084/evidence/Dillards--18/review.json) |
| [Dillards--19](http://localhost:45084/#dillards-19) | Retained | 7 → 7 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--19/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--19/eval.json) / [browser](http://localhost:45084/evidence/Dillards--19/review.json) |
| [Dillards--20](http://localhost:45084/#dillards-20) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--20/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--20/eval.json) / [browser](http://localhost:45084/evidence/Dillards--20/review.json) |
| [Dillards--21](http://localhost:45084/#dillards-21) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--21/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--21/eval.json) / [browser](http://localhost:45084/evidence/Dillards--21/review.json) |
| [Dillards--22](http://localhost:45084/#dillards-22) | Refined | 9 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--22/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--22/eval.json) / [browser](http://localhost:45084/evidence/Dillards--22/review.json) |
| [Dillards--23](http://localhost:45084/#dillards-23) | Refined | 10 → 7 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--23/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--23/eval.json) / [browser](http://localhost:45084/evidence/Dillards--23/review.json) |
| [Dillards--24](http://localhost:45084/#dillards-24) | Retained | 11 → 11 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--24/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--24/eval.json) / [browser](http://localhost:45084/evidence/Dillards--24/review.json) |
| [Dillards--25](http://localhost:45084/#dillards-25) | Refined | 6 → 3 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--25/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--25/eval.json) / [browser](http://localhost:45084/evidence/Dillards--25/review.json) |
| [Dillards--26](http://localhost:45084/#dillards-26) | Refined | 8 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--26/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--26/eval.json) / [browser](http://localhost:45084/evidence/Dillards--26/review.json) |
| [Dillards--27](http://localhost:45084/#dillards-27) | Refined | 7 → 1 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--27/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--27/eval.json) / [browser](http://localhost:45084/evidence/Dillards--27/review.json) |
| [Dillards--28](http://localhost:45084/#dillards-28) | Retained | 7 → 7 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--28/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--28/eval.json) / [browser](http://localhost:45084/evidence/Dillards--28/review.json) |
| [Dillards--29](http://localhost:45084/#dillards-29) | Retained | 13 → 13 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--29/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--29/eval.json) / [browser](http://localhost:45084/evidence/Dillards--29/review.json) |
| [Dillards--30](http://localhost:45084/#dillards-30) | Retained | 6 → 6 | PASS | [trajectory](http://localhost:45084/evidence/Dillards--30/trajectory.json) / [verdict](http://localhost:45084/evidence/Dillards--30/eval.json) / [browser](http://localhost:45084/evidence/Dillards--30/review.json) |

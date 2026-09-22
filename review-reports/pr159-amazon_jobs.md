# PR #159: Amazon Jobs review and fixes

Reviewed every task against the pinned mirror and its saved-state grading contract. The corrected browser runs complete all 30 tasks and pass the official `agent_demo/eval_judge.py --verifier True` entrypoint. 22 task prompts were revised; the recorded corrected paths contain 6–16 meaningful actions, excluding initial navigation, final answer and viewport diagnostics. Counts describe these recorded paths, not a proof of the shortest possible solution.

## Findings and corrections

- **Startup and pagination.** Direct app execution created duplicate Flask/SQLAlchemy registries; reuse the running module. Sorting a paginated result now resets its offset.
- **Profile layout.** Allow the profile columns and long LinkedIn URLs to wrap on mobile.
- **Grading.** Require exact reviewed initial data and saved-state deltas, preserve unrelated applications, users and alerts, decode screenshot pixels, bind trajectory origins and query parameters, and reject misleading numeric answers.

Short research tasks now combine comparison or investigation with relevant saved-state outcomes. Each revised prompt has matching rubric and deterministic verification. Ground truth remains in private verifier fixtures, not task definitions.

## Evidence and validation

- Scripted visible-UI browser review with per-action screenshots and independent initial/final SQLite backups; contributor reference answers informed the flows. These are not independent autonomous-agent attempts. The secondary LLM judge was not run.
- All 91 corrected trajectories pass, all 91 GIFs decode, and the dashboard's filters, task anchors, 364 evidence links, desktop layout and mobile width were checked in Chromium.
- Forty controls produced their expected results, including natural equivalent answers, swapped values, unrelated reference numbers, wrong alert frequency, unrelated record deletion, fixture tampering, invalid PNGs, and wrong origins.
- Amazon verifier suite: 36 tests passed. BBB verifier suite: 37 tests passed; BBB route suite: 26 tests passed. Cboe verifier suite: 8 test methods and the full per-task matrix passed (349 subtests).
- Fresh HF fetch validated all 65 bundles at `bd574ee3270c40ebf3347fb89e5fbfb6f4adf2a0`. HF #106, #110 and #107 are merged; all 65 previously existing dataset files were preserved and the three archives were not repacked.
- Static checks confirm 65 unique registry ports, existing 62 port assignments unchanged, new sites at 40062–40064, matching task URLs and Docker EXPOSE, and changes confined to the README Websites table.

## Final integration validation

- Built `webharbor:pr159-161-reviewed`, image `sha256:f08aecb3f1635a2b988e24553c4374bcf74ffa5930bb425549e8328cbc814f42`, using `docker build --network=host` after asset checks. Its runtime source matches the integrated candidate; a later test-only change aligns BBB's schema assertion with port 40064.
- Only Amazon Jobs, Cboe and BBB were started in an isolated Docker network. Each returned HTTP 200 and appeared alive/ready, preserved a deliberate account mutation across restart, reset byte-identically to its seed twice, and matched the reviewed seed's logical table hashes. Checks ran inside the container; aggregate `/health` returns 503 because the other 62 sites were intentionally not started.
- Syntax and changed-code whitespace checks passed. The 65-site registry/README/task URL/EXPOSE checks preserve existing ports. BBB's 26 route tests include exact-name priority, per-state positive-loss medians (including fractional values), quote navigation and seed-text cleanup. The Amazon sort-offset browser check and BBB final median mobile check passed.
- Original contributions and fixes use this integration order: #159 → #171 → #160 → #172 → #161 → #173. Required HF #106/#110/#107 merge status was independently rechecked. The code's immutable asset revision is the merged dataset commit above.

## Review artifacts

[GIF dashboard](http://localhost:45044/) (forward port 45044). [Ledger](http://localhost:45044/ledger.json). Local evidence: `/data/pr159-161-review`. The previews use ports 45041–45043. Normal runtime ports are 40062–40064. Docker publication and deployment are outside this integration.

## Per-task ledger

| Task | Prompt | Actions | Verifier | Evidence |
|---|---|---:|---|---|
| Amazon Jobs--0 | Revised | 14 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-0) |
| Amazon Jobs--1 | Revised | 12 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-1) |
| Amazon Jobs--2 | Revised | 15 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-2) |
| Amazon Jobs--3 | Revised | 13 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-3) |
| Amazon Jobs--4 | Revised | 13 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-4) |
| Amazon Jobs--5 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-5) |
| Amazon Jobs--6 | Reviewed | 6 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-6) |
| Amazon Jobs--7 | Revised | 14 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-7) |
| Amazon Jobs--8 | Revised | 13 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-8) |
| Amazon Jobs--9 | Revised | 16 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-9) |
| Amazon Jobs--10 | Reviewed | 12 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-10) |
| Amazon Jobs--11 | Revised | 14 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-11) |
| Amazon Jobs--12 | Revised | 14 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-12) |
| Amazon Jobs--13 | Revised | 13 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-13) |
| Amazon Jobs--14 | Revised | 13 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-14) |
| Amazon Jobs--15 | Revised | 11 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-15) |
| Amazon Jobs--16 | Revised | 6 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-16) |
| Amazon Jobs--17 | Revised | 15 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-17) |
| Amazon Jobs--18 | Revised | 14 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-18) |
| Amazon Jobs--19 | Revised | 9 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-19) |
| Amazon Jobs--20 | Revised | 10 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-20) |
| Amazon Jobs--21 | Revised | 13 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-21) |
| Amazon Jobs--22 | Revised | 7 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-22) |
| Amazon Jobs--23 | Revised | 8 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-23) |
| Amazon Jobs--24 | Reviewed | 9 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-24) |
| Amazon Jobs--25 | Reviewed | 9 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-25) |
| Amazon Jobs--26 | Reviewed | 8 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-26) |
| Amazon Jobs--27 | Reviewed | 9 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-27) |
| Amazon Jobs--28 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-28) |
| Amazon Jobs--29 | Revised | 14 | PASS | [GIF and trajectory](http://localhost:45044/#amazon_jobs-29) |

Fix PR: https://github.com/aiming-lab/WebHarbor/pull/171. Integration status and exact remote merge commits are recorded in the dashboard report and `/data/pr159-161-review/github-integration.json`.

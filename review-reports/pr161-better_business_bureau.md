# PR #161: Better Business Bureau review and fixes

Reviewed every task against the pinned mirror and its saved-state grading contract. The corrected browser runs complete all 30 tasks and pass the official `agent_demo/eval_judge.py --verifier True` entrypoint. 19 task prompts were revised; the recorded corrected paths contain 6–18 meaningful actions, excluding initial navigation, final answer and viewport diagnostics. Counts describe these recorded paths, not a proof of the shortest possible solution.

## Findings and corrections

- **Navigation and discovery.** Make menu clicks reliable, expose Get a Quote on eligible profiles, prioritize exact business names, and wrap long scam details on mobile.
- **Seed content and statistics.** Remove scraped footer/profile chrome from product and consumer text. Compute positive-loss medians, including even samples, and retain fractional state medians. Display reported loss on scam details.
- **Grading.** Require exact initial data and requested favorite/quote changes, preserve unrelated records, support legitimate SQLite ID reuse after a deletion, and check the added scam comparisons and research outcomes.

Short research tasks now combine comparison or investigation with relevant saved-state outcomes. Each revised prompt has matching rubric and deterministic verification. Ground truth remains in private verifier fixtures, not task definitions.

## Evidence and validation

- Scripted visible-UI browser review with per-action screenshots and independent initial/final SQLite backups; contributor reference answers informed the flows. These are not independent autonomous-agent attempts. The secondary LLM judge was not run.
- All 91 corrected trajectories pass, all 91 GIFs decode, and the dashboard's filters, task anchors, 364 evidence links, desktop layout and mobile width were checked in Chromium.
- Forty controls produced their expected results, including natural equivalent answers, swapped values, unrelated reference numbers, wrong alert frequency, unrelated record deletion, fixture tampering, invalid PNGs, and wrong origins.
- Amazon verifier suite: 36 tests passed. BBB verifier suite: 37 tests passed; BBB route suite: 26 tests passed. Cboe suite and final combined Docker validation are recorded in the batch report when complete.
- Fresh HF fetch validated all 65 bundles at `bd574ee3270c40ebf3347fb89e5fbfb6f4adf2a0`. HF #106, #110 and #107 are merged; all 65 previously existing dataset files were preserved and the three archives were not repacked.
- Static checks confirm 65 unique registry ports, existing 62 port assignments unchanged, new sites at 40062–40064, matching task URLs and Docker EXPOSE, and changes confined to the README Websites table.

## Review artifacts

[GIF dashboard](http://localhost:45044/) (forward port 45044). [Ledger](http://localhost:45044/ledger.json). Local evidence: `/data/pr159-161-review`. The previews use ports 45041–45043. Normal runtime ports are 40062–40064. Docker publication and deployment are outside this integration.

## Per-task ledger

| Task | Prompt | Actions | Verifier | Evidence |
|---|---|---:|---|---|
| Better Business Bureau--0 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-0) |
| Better Business Bureau--1 | Revised | 17 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-1) |
| Better Business Bureau--2 | Reviewed | 6 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-2) |
| Better Business Bureau--3 | Reviewed | 6 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-3) |
| Better Business Bureau--4 | Revised | 16 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-4) |
| Better Business Bureau--5 | Revised | 16 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-5) |
| Better Business Bureau--6 | Reviewed | 6 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-6) |
| Better Business Bureau--7 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-7) |
| Better Business Bureau--8 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-8) |
| Better Business Bureau--9 | Reviewed | 6 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-9) |
| Better Business Bureau--10 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-10) |
| Better Business Bureau--11 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-11) |
| Better Business Bureau--12 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-12) |
| Better Business Bureau--13 | Revised | 18 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-13) |
| Better Business Bureau--14 | Revised | 16 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-14) |
| Better Business Bureau--15 | Revised | 14 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-15) |
| Better Business Bureau--16 | Reviewed | 6 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-16) |
| Better Business Bureau--17 | Revised | 15 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-17) |
| Better Business Bureau--18 | Revised | 10 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-18) |
| Better Business Bureau--19 | Revised | 8 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-19) |
| Better Business Bureau--20 | Revised | 12 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-20) |
| Better Business Bureau--21 | Revised | 12 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-21) |
| Better Business Bureau--22 | Revised | 9 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-22) |
| Better Business Bureau--23 | Revised | 7 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-23) |
| Better Business Bureau--24 | Revised | 10 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-24) |
| Better Business Bureau--25 | Revised | 7 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-25) |
| Better Business Bureau--26 | Revised | 12 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-26) |
| Better Business Bureau--27 | Revised | 12 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-27) |
| Better Business Bureau--28 | Revised | 9 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-28) |
| Better Business Bureau--29 | Revised | 11 | PASS | [GIF and trajectory](http://localhost:45044/#better_business_bureau-29) |

# PR #160: Cboe review and fixes

Reviewed every task against the pinned mirror and its saved-state grading contract. The corrected browser runs complete all 31 tasks and pass the official `agent_demo/eval_judge.py --verifier True` entrypoint. 22 task prompts were revised; the recorded corrected paths contain 6–17 meaningful actions, excluding initial navigation, final answer and viewport diagnostics. Counts describe these recorded paths, not a proof of the shortest possible solution.

## Findings and corrections

- **Container startup.** Load the HTML parser only when rebuilding scraped seed content, so the populated HF seed boots without BeautifulSoup. Direct app execution reuses its module.
- **Account layout.** Wrap account panels and contain table scrolling on mobile.
- **Grading.** Bind numerical values to their labels, verify expanded glossary/biography evidence, and enforce exact watchlist, article and registration changes without deleting other users' data. Correct the XSP index-options terminology.

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
| Cboe--0 | Revised | 8 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-0) |
| Cboe--1 | Revised | 8 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-1) |
| Cboe--2 | Revised | 11 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-2) |
| Cboe--3 | Revised | 11 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-3) |
| Cboe--4 | Reviewed | 8 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-4) |
| Cboe--5 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-5) |
| Cboe--6 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-6) |
| Cboe--7 | Reviewed | 6 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-7) |
| Cboe--8 | Revised | 9 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-8) |
| Cboe--9 | Revised | 10 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-9) |
| Cboe--10 | Revised | 10 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-10) |
| Cboe--11 | Revised | 6 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-11) |
| Cboe--12 | Revised | 7 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-12) |
| Cboe--13 | Revised | 15 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-13) |
| Cboe--14 | Revised | 17 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-14) |
| Cboe--15 | Revised | 17 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-15) |
| Cboe--16 | Revised | 17 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-16) |
| Cboe--17 | Revised | 15 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-17) |
| Cboe--18 | Revised | 14 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-18) |
| Cboe--19 | Revised | 12 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-19) |
| Cboe--20 | Revised | 12 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-20) |
| Cboe--21 | Revised | 12 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-21) |
| Cboe--22 | Revised | 13 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-22) |
| Cboe--23 | Revised | 8 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-23) |
| Cboe--24 | Revised | 10 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-24) |
| Cboe--25 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-25) |
| Cboe--26 | Reviewed | 7 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-26) |
| Cboe--27 | Reviewed | 10 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-27) |
| Cboe--28 | Reviewed | 11 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-28) |
| Cboe--29 | Reviewed | 6 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-29) |
| Cboe--30 | Revised | 10 | PASS | [GIF and trajectory](http://localhost:45044/#cboe-30) |

Fix PR: https://github.com/aiming-lab/WebHarbor/pull/172. Integration status and exact remote merge commits are recorded in the dashboard report and `/data/pr159-161-review/github-integration.json`.

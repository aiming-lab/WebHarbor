# Best Buy PR #135 — task difficulty revision

Expanded the six tasks whose previous recorded paths took five or fewer actions. Worktree `/data/WebHarbor-fix-pr135`, branch `fix/pr135-bestbuy`, based on the validated fix commit `625d93c36690a762502536124a2a5e92ec74223c`. Original #48 → #135 ancestry remains intact.

## Revised tasks

| Task | Added work | Recorded actions |
|---|---|---:|
| [BestBuy--0](http://localhost:45012/#task-0) | Budget/rating decision and a confirmed saved laptop | 3 → 10 |
| [BestBuy--3](http://localhost:45012/#task-3) | Two Canon bundles, saved comparison, lens ranges and upgrade premium | 3 → 14 |
| [BestBuy--4](http://localhost:45012/#task-4) | Two authenticated rewards accounts, balances/certificates and difference | 5 → 11 |
| [BestBuy--9](http://localhost:45012/#task-9) | Two order lookups, fulfillment/status/totals and price difference | 4 → 8 |
| [BestBuy--10](http://localhost:45012/#task-10) | Pickup support requirements plus store-specific SSD availability/aisle | 4 → 8 |
| [BestBuy--11](http://localhost:45012/#task-11) | Two leading percentage offers, dollar savings and the correct saved winner | 3 → 13 |

All six now take **8–14 actions** in fresh scripted UI runs. The complete suite rises from 96 to 138 actions. Counts describe observed routes, not minimum possible paths. Grading checks meaningful outcomes and evidence, with no click-count threshold or mandatory answer format. Tasks 1, 2, 5, 6, 7, 8 retain their definitions.

Task11 distinguishes the greatest percentage discount from the greatest dollar saving: the mirror's 45% OmniBook offer saves $400, while its 39% Victus offer saves $575. Task3 compares the two-lens Canon kit with the captured starter bundle and derives the $100.99 premium. Reviewer ground truth stays in verifier/data logic, not the agent-facing question.

## Source and feasibility

Direct HTTP checks of Best Buy pickup, rewards, deals and camera search pages returned 403. A Chromium attempt at Top Deals timed out after 25 seconds; details are recorded separately in `upstream-browser.json`. No new live-site claims or assets were invented. Product names, prices and lens information use the existing source-catalog snapshot. Accounts, rewards, orders, pickup requirements and store inventory remain explicitly synthetic benchmark data.

The first pickup draft targeted Beats headphones that exist in the DB but are outside the store page's ten featured inventory rows. The final task instead targets the visible SanDisk Extreme Portable 2TB SSD at Austin Domain; its pickup window and aisle are readable through the ordinary UI. This failed draft is retained in `draft-attempts/task-10`. The first two-order harness used a brittle text-line index; its retained failed attempt is `draft-attempts/task-9`, and the successful replay reads the actual status element. No application handler or seed was changed to fabricate feasibility.

## Rubrics and grading

- Updated task wording, rubric and verifier together for all six revisions.
- Exact wishlist additions preserve previous items and other users. Camera comparisons require both products, a comparison visit after their pages, and only the site's necessary capacity eviction.
- Two rewards visits are bound to typed account emails; both order lookups/details are required. Store research requires the support article and Austin store page.
- Research answers bind facts to their accounts/orders/products, validate comparison direction, numeric boundaries, units and polarity, and accept tested prose, bullets, Markdown tables and common number equivalents.
- **108/108** declared synthetic controls match expectations. All six former short completions fail the revised tasks. Other controls cover swapped values, wrong units, negations, wrong saved products, removed existing state, missing required pages and unchanged checkout regressions.
- **19/19** focused tests pass. Python compilation and `git diff --check` pass. The new tests exercise positive equivalents and plausible wrong answers rather than minimum action counts.

## Fresh browser evidence

| Task | Scope | Actions | Primary verifier |
|---|---|---:|---|
| [BestBuy--0](http://localhost:45012/task-0/trajectory.json) | Revised | 10 | PASS |
| [BestBuy--1](http://localhost:45012/task-1/trajectory.json) | Regression | 14 | PASS |
| [BestBuy--2](http://localhost:45012/task-2/trajectory.json) | Regression | 9 | PASS |
| [BestBuy--3](http://localhost:45012/task-3/trajectory.json) | Revised | 14 | PASS |
| [BestBuy--4](http://localhost:45012/task-4/trajectory.json) | Revised | 11 | PASS |
| [BestBuy--5](http://localhost:45012/task-5/trajectory.json) | Regression | 10 | PASS |
| [BestBuy--6](http://localhost:45012/task-6/trajectory.json) | Regression | 10 | PASS |
| [BestBuy--7](http://localhost:45012/task-7/trajectory.json) | Regression | 17 | PASS |
| [BestBuy--8](http://localhost:45012/task-8/trajectory.json) | Regression | 14 | PASS |
| [BestBuy--9](http://localhost:45012/task-9/trajectory.json) | Revised | 8 | PASS |
| [BestBuy--10](http://localhost:45012/task-10/trajectory.json) | Revised | 8 | PASS |
| [BestBuy--11](http://localhost:45012/task-11/trajectory.json) | Revised | 13 | PASS |

All 12 successful runs are fresh scripted Playwright UI replays: 138 task actions, 288 action screenshots, 198 separate desktop/mobile viewport captures and 12 GIFs. No visible broken images, document overflow, browser page errors or HTTP errors were detected in these completed runs. Revised final screens and the store/rewards/comparison content were visually inspected. The archived prior review and fix recordings remain available.

The official `agent_demo/eval_judge.py --verifier True` entrypoint matches all **120/120** expected outcomes (12 browser runs and 108 controls), with no infrastructure errors. Saved initial/after database snapshots are used directly.

The full `scripts/build.sh webharbor:pr135-difficulty` build passed asset integrity/registry checks and validated all 60 SQLite seeds. Image: `sha256:533ae07920be19ec0c429ccc735b482c0ad31aecdfc0f0248f2385e54283c0a2` (5.89GB).

Container validation passed: control-plane health reports all 60 processes alive, Best Buy returns HTTP 200, and startup, dirty-state reset and restart keep runtime/seed databases byte-identical (SHA256 `e69766a2b49d5857dcd94b1f67d40db18cd284193f5ee19f2d78b75c9fd4f42e`). App, seed generator, task and all changed verifier module hashes match the checkout inside the image. Only Best Buy runtime behavior was tested. The owned test container/network were removed; the local image is retained.

Dashboard validation passed in Chromium: revised tasks appear first, All shows 12 cards, Revised shows 6, deep-linking reveals hidden tasks, all 12 GIFs decode in-browser, and all evidence links work. Desktop/mobile screenshots show no document overflow. GIF frames were decoded individually and follow recorded action order with 1.1-second timing.

## Assets, services and limits

- No asset, seed, application handler, port registry or HF pin changed. Previously merged HF #98 remains pinned at `f372a548b2b4189c42ad6d16abec0579daaa892a`; no archive rewrite or additional HF PR is required for these task-only changes.
- [Current GIF dashboard](http://localhost:45012/) · [Current preview](http://localhost:45011/) · [Previous fixes dashboard](http://localhost:45002/). Forward ports 45011/45012 if using a remote workspace.
- Evidence: `/data/pr135-difficulty-evidence`; task ledger, source-access attempts, declared controls, official grading and Docker proof are linked by the dashboard. Preview/database copies are isolated from the editable checkout and old previews.
- Answer parsing is bounded English parsing, not a general semantic judge; unsupported paraphrases can still need rules. No autonomous LLM-agent or secondary LLM-judge run was performed.
- No code PR was opened/pushed/merged, and no image was published/deployed. Future integration retains original #48 → #135 → fix continuation order.

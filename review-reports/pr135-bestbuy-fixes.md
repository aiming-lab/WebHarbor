# PR #135 — Best Buy fixes

Fixed the six review findings, reconciled current main, and merged the unchanged required HF archive. Worktree `/data/WebHarbor-fix-pr135`, branch `fix/pr135-bestbuy`, based on PR #135 `75e7a88bd40868a72d8b0c2b47d94ae5165eb82f`, with original PR #48 ancestry retained. Main reconciled at `d39f44c046fe8dde51929b4cb11232ea32f1b559`.

## Changes

- Replaced substring grading with bounded fact checks for numeric boundaries, scales, negations, contradictions, comparison direction and common natural equivalents. Added positive/negative regressions. Product-name searches and numerically equivalent filters now count as valid navigation.
- Wishlist/cart tasks accept brief completion confirmations while retaining precise database-delta requirements.
- Checkout grading recomputes subtotal, shipping fee, tax and total from initial state, validates account email, status, payment approval and pickup-window membership, and retains exact item/cart/reward and unrelated-state checks.
- Guest Add to cart returns through login to the product page for an explicit retry. Before/after HTTP evidence confirms the prior HTTP 405 becomes HTTP 200; a fresh browser retry adds the product successfully.
- Updated rubrics consistently and made the existing demo password explicit. Preserved task intent and difficulty.
- Official grading can use paired saved initial/after snapshots; explicit paths override them and missing pairs fail as infrastructure errors.
- Appended Best Buy at **40059** in both registries, task URLs, app default, Docker exposure and README. All **59 existing port assignments** are preserved; all 60 registrations agree.
- Merged [HF #98](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/98), confirmed remote status **merged**, and pinned `f372a548b2b4189c42ad6d16abec0579daaa892a`. All **62 existing files** are unchanged, including Bandcamp. Best Buy archive SHA256 remains `f00687d83c336f7de115f598959a62399b8b89a5967a18d2284b0a354ce4481a`; no archive was repacked or reformatted.
- Freshly fetched/extracted all 60 registered archives and regenerated the combined manifest. Verified extracted tree: `1290ff251fe97d5d56a9ab9a7cc312065c17e3d83218671aacc8c5646e1418a8`.

## Browser and grading results

| Task | Fresh UI run | Primary verifier | Task actions |
|---|---|---|---:|
| [BestBuy--0](http://localhost:45002/task-0/trajectory.json) | Complete | PASS | 3 |
| [BestBuy--1](http://localhost:45002/task-1/trajectory.json) | Complete | PASS | 14 |
| [BestBuy--2](http://localhost:45002/task-2/trajectory.json) | Complete | PASS | 9 |
| [BestBuy--3](http://localhost:45002/task-3/trajectory.json) | Complete | PASS | 3 |
| [BestBuy--4](http://localhost:45002/task-4/trajectory.json) | Complete | PASS | 5 |
| [BestBuy--5](http://localhost:45002/task-5/trajectory.json) | Complete | PASS | 10 |
| [BestBuy--6](http://localhost:45002/task-6/trajectory.json) | Complete | PASS | 10 |
| [BestBuy--7](http://localhost:45002/task-7/trajectory.json) | Complete | PASS | 17 |
| [BestBuy--8](http://localhost:45002/task-8/trajectory.json) | Complete | PASS | 14 |
| [BestBuy--9](http://localhost:45002/task-9/trajectory.json) | Complete | PASS | 4 |
| [BestBuy--10](http://localhost:45002/task-10/trajectory.json) | Complete | PASS | 4 |
| [BestBuy--11](http://localhost:45002/task-11/trajectory.json) | Complete | PASS | 3 |

- **12/12** fresh scripted browser completions, **96 task actions**, **204 action screenshots**, **150 separate desktop/mobile viewport captures**, and **12 GIFs**. No broken visible images, horizontal document overflow, page errors or HTTP errors in those runs.
- **3/3** additional real browser paths pass: Dell search, Canon T7 search and maximum-price filter 350.00.
- Separate guest-login browser flow confirms return to the product and successful explicit add-to-cart retry. An initial screenshot timing failure is preserved under `diagnostics/`; the completed attempt is under `guest-retry/`.
- **83/83** declared synthetic grading controls match expectations, including all original 68 and additional checkout/answer corruption cases. Original review had 15 false accepts and 12 false rejects. Synthetic controls are copied evidence, not browser completions.
- **14/14** focused unit tests pass, including guest login/retry and 25 natural-answer assertions. Python compilation and whitespace checks against current main pass.

## Runtime validation

Full `scripts/build.sh webharbor:pr135-fix` succeeded without a manifest bypass. Image `sha256:cfd742c8e365a23e8e26848392e66bef33cc9f94ceb24bd6ac6aaf056e9eb60b` (5.89GB) validates all 60 SQLite seeds. Container control-plane health reports all 60 processes alive; Best Buy homepage returns HTTP200. Best Buy startup, dirty-cart reset and restart produce byte-identical runtime/seed databases (SHA256 `e69766a2b49d5857dcd94b1f67d40db18cd284193f5ee19f2d78b75c9fd4f42e`). Source hashes inside the image match the fix checkout. Only Best Buy runtime routes/reset were exercised; unrelated-site task tests were not run. Owned test container/network are removed after validation; the local image is retained.

The official `agent_demo/eval_judge.py --verifier True` entrypoint matches all **98/98** expected outcomes (15 real browser runs and 83 synthetic controls), with no infrastructure errors. Saved snapshots were graded directly.

Dashboard verified in Chromium at desktop/mobile widths: all 12 task IDs and GIFs present and decoded, All/Grading updated filters and task deep link work, and all evidence links return successfully. GIF frame order/timing was generated from recorded action order and every frame decoded.

## Evidence and limitations

- [Current GIF dashboard](http://localhost:45002/) · [Current preview](http://localhost:45001/) · [Original review dashboard](http://localhost:44994/).
- Evidence directory: `/data/pr135-fix-evidence`; [HF merge proof](http://localhost:45002/hf-merged.json), [controls](http://localhost:45002/controls/results.json), [HTTP comparison](http://localhost:45002/http-comparison.json), [task ledger](http://localhost:45002/ledger.json).
- Preview/dashboard ports 45001 and 45002 may need forwarding in a remote workspace. Original 44993/44994 services are preserved.
- These are scripted Playwright UI runs, not autonomous model-agent attempts. No secondary LLM judge or unrelated-site task regression was run.
- Answer parsing supports bounded English equivalents; arbitrary paraphrases are not guaranteed. Pickup state stores a time-window label, not a slot ID/day, so grading verifies an available matching window at the chosen store.
- No code PR was opened/pushed/merged, and no Docker image was published/deployed. Future code integration must preserve original #48 → reviewer #135 → follow-up dependency order; #48 is currently closed as superseded and needs appropriate integration handling.

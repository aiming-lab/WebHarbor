# Michaels — deterministic verifier contract (reviewer suite)

One deterministic verifier per benchmark task, plus a pytest suite that proves
the contract. Authored by the reviewer (review-env skill, Step 6/7); the ground
truth is **hardcoded inside the verifiers** and never appears in `tasks.jsonl`.

## Layout

```
sites/michaels/verify/
├── verify_lib.py          shared deterministic utilities (michaels-adapted from the
│                          hardened marriott / merriam_webster / jcpenney suites)
├── verify_0.py … verify_18.py   one verifier per tasks.jsonl row
├── append_rubrics.py      appends verifier_path + judge_rubric to tasks.jsonl
│                          (original five keys' bytes untouched, idempotent)
├── README.md              this file
└── tests/
    ├── _support.py        fixtures: seed acquisition, RunBuilder (agent-shaped
    │                          trajectories), sqlite mutation helpers, tiny PNGs
    └── test_verifiers.py  116 contract tests (honest / no-op / wrong answer /
                           shortcut / state-mismatch / wrong delta / tampering)
```

## Contract

1. **Package identity** — task_id match, `terminated` with `agent_done`, non-empty
   final answer, every recorded URL on the same loopback origin AND port as
   `start_url`, every referenced screenshot a decodable PNG.
2. **Navigation gates** (anti knowledge-shortcut) — the agent must have opened the
   on-site surfaces the task names: scored search (`/search?q=`), category
   listings with facet params (`/shop/<slug>?availability=pickup&sort=price_low`),
   product pages and their reviews tabs, the cart, the two-step checkout +
   confirmation, the account suite (orders / profile / addresses / payment /
   wishlist), the store locator, classes + registration, savings, and the coupon
   policy. A correct answer with no matching navigation is a FAIL.
3. **Answer checks** — affirmative token / phrase / amount / count / date / time
   matching against frozen ground truth hardcoded per verifier. Order numbers
   are deterministic given the frozen seed and pinned reference date
   (`MI<YYMMDD><user_id:02d><seq:03d>`) and must appear verbatim in the answer
   AND identify the added order row.
4. **DB after-state** — read-only tasks require every table row-identical;
   stateful tasks require the exact allowed row delta and nothing else (the
   added order row with its subtotal / discount / shipping / tax / total /
   promo / card / address, its order_items, cart_items add/remove/qty changes,
   wishlist deltas, a class registration row, a payment-method row, a created
   user row, a profile-phone update, an added address row).
5. **Fail-closed** — missing/tampered snapshots, mutated seeds, or any internal
   error produce `{"pass": false, "infra_error": true}` and exit 1.

## Frozen seed contract

`instance_seed/michaels.db` ships in-repo (md5 `0b2b1c21ec9afbd35a477175fa5712dd`).
The suite pins its schema sha256, per-table row counts, a full rows digest, and
the four demo users' identity columns; any deviation fails closed.

## Running

```bash
python3 -m pytest sites/michaels/verify/tests -q          # 116 contract tests
python3 sites/michaels/verify/verify_0.py --run_dir RUN   # single task, RUN has
    # trajectory.json + screenshots/ + initial.db + after.db (or --container
    # wh-michaels-review to fetch the DBs live)
```

## Provenance of ground truth

Every frozen fact was read from the rendered mirror by a real Chromium
adversarial walkthrough (19 honest trajectories, 6–35 recorded steps each,
strict NAV/FILL/SELECT/SUBMIT/SCAN/READ taxonomy), cross-checked against the
seed DB, and — for store hours, coupon policy wording and class data — against
the upstream reference (michaels.com via the Wayback Machine). The verifiers
PASS all 19 real trajectories and reject cross-task, mutated-answer, no-op,
shortcut, state-mismatch and wrong-delta forgeries with zero false positives.

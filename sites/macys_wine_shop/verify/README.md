# macys_wine_shop — verifier contract (16 redesigned deep tasks)

Contract rebuilt for the depth-review redesign of PR #196: the 30 shallow
tasks (and their grading contract) are retired; this directory grades the new
16 deep functional-chain tasks (`MacysWineShop--0` … `--15`, seven-key
tasks.jsonl rows — the five-key task definition plus the appended
`verifier_path`/`judge_rubric` grading keys, per the round-2 re-review F1
fix; `--14`/`--15` are the two KEEP tasks from the review, their verifiers
adapted in substance unchanged, with --14 hardened per the round-2 F2
finding). The harness lineage is the hardened
WebHarbor verifier suite (merriam_webster → instructure → the first macys
review contract); the frozen-seed contract is unchanged.

## Layout

- `verify_lib.py` — shared fail-closed harness, kept byte-identical to the
  reviewed lineage. Trajectory identity gates (task_id, `agent_done`,
  non-empty answer, same-origin loopback URLs, decodable PNG screenshots),
  navigation gates (scored search with sort, collection listings with
  metafield facet filters `filter.p.m.drinks.*` and the sort menu, product
  detail pages for bottles and pack cases, the cart with its rules, the
  three-step checkout with the 21+ confirm, account address/payment/orders
  surfaces, the Wine Club tabs + FAQ, the Wine 101 blog, the gift-card
  variant picker), tolerant answer matching (accent-folded phrases, thousands
  groups, `$`-money, percent forms, FREE), SQLite snapshot validation bound
  to the frozen seed (schema `7fdbd7fc…`, 19-table counts, rows digest
  `44d5827f…`, benchmark user identities) and the fail-closed CLI runner.
  LLM helpers are advisory-only; verdicts are decided with `--no_llm True`.
- `verify_0.py` … `verify_15.py` — one deterministic verifier per task;
  ground truth is HARDCODED inside each file (never in tasks.jsonl).
- `tests/` — pytest contract suite (see below).

## Per-task DB delta contract

- every task starts from the byte-identical seed (8 orders MWS1042–MWS1049,
  4 benchmark users with their seeded carts); each task that places an order
  therefore lands on **MWS1050** — the verifiers hardcode it.
- read-only task 14 (password change + revert): every table row-identical.
- guest purchases (0, 1, 2, 3, 4, 7, 10, 11, 12, 13): exactly one added
  `orders` row (MWS1050, `user_id` NULL) with its `order_items` rows and
  nothing else — the guest cart row is consumed by the order, so
  `cart_items` returns row-identical.
- logged-in purchases 5 (bob) and 8 (david): one added order for the user,
  its items, and exactly the user's seeded cart rows removed.
- task 6 (carol, new address + new card): one added `addresses` row (the
  task's Denver address, not default), one added order shipped to it paid
  with the new card, its items, and carol's cart rows consumed.
- task 9 (gift card + sparkling): the $100 gift-card variant (bottle_count 1
  — it counts toward the 3-bottle minimum) plus one sparkling wine at qty 2
  (unit ≤ $30); the verifier recomputes total = 100 + 2·price + 14.95 + 2.95
  from the DB rows and checks self-consistency.
- task 11 (storage article): the bought red's varietal must be one of the
  article's full-bodied reds (Cabernet Sauvignon / Malbec / Zinfandel /
  Syrah-Shiraz); total recomputed from the DB row.
- task 15 (register + buy): one added user, one added order (MWS1050, total
  $77.87) with ≥ 3 bottles of the Closed Window Pinot Noir.
- Collateral writes anywhere else fail the run.

## Contract test coverage (pytest, no docker, no LLM)

- honest PASS ×16 — fixtures mirror the live honest walks (see the redesign
  evidence) including the guest/­logged-in checkout chains and both KEEP tasks.
- no-op FAIL ×16 (homepage only, empty answer, clean DB).
- wrong-answer FAIL ×16.
- homepage-shortcut FAIL ×16 (correct answer, homepage-only navigation).
- read-only tamper FAIL (task 14 mutated after-DB).
- task-14 adversarial negatives FAIL (round-2 F2): a walk truncated at the
  sign-out (no re-login), an answer claiming the re-login failed, an answer
  claiming a different change-target password, and a phrase-preserving
  answer with a fabricated monetary claim.
- stateful mismatch FAIL ×15 (claimed success, unchanged DB) and wrong-state
  FAIL (wrong product / wrong address / wrong quantity deltas).
- package tampering FAIL (task_id mismatch, off-site URL, missing screenshot,
  non-done trajectory, tampered seed, unavailable DB).

Run from the repo's agent_demo env (so `simpleArgParser` + Pillow import):

```bash
cd agent_demo && uv run python -m pytest ../sites/macys_wine_shop/verify/tests -q
```

## Live redesign evidence

Honest visible-UI walks of all 16 tasks (per-task screenshots + walk.json),
per-task step counts ≥ 15 (the user's 2026-09-23 depth bar), a live replay of
the deterministic contract against the contributor container, and DB-delta
dumps are archived in `wh-macys_wine_shop-redesign-evidence/`.

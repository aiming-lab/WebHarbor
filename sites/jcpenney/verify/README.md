# JCPenney — verifier contract (reviewer-authored)

This directory holds the grading contract for the 15 JCPenney benchmark tasks, written
by the reviewer (review-env skill Step 6). Ground truth is **hardcoded inside each
`verify_N.py`** — never in `tasks.jsonl` (the agent reads that file; an answer key there
would leak answers). After the reviewer's pass, each `tasks.jsonl` row carries
`verifier_path` + `judge_rubric` appended on top of the untouched five contributor keys
(`web_name, id, ques, web, upstream_url`) — see `append_rubrics.py`, which preserves the
original bytes as the line prefix and adds no `answer` key.

**Depth redesign (2026-09-23 user standard).** The set was rebuilt from 30 shallow tasks
to 15 deep-chain tasks per the depth-review report (`wh-jcpenney-depth-review-evidence/
REPORT.md`): three KEEP entries (registration cycle → `verify_0`, address-book add →
`verify_1`, password-change cycle → `verify_2`, honest-walk measured at 15/16/17 steps)
plus twelve redesigned deep chains (`verify_3`…`verify_14`), each honest-walk measured at
≥ 15 real interaction steps through the visible UI only (search + sort, product pages
with swatch/size/quantity, guest bag merge, three-step checkout with new-address /
new-card / coupon / gift-message variants, bag quantity update + line removal, order
dual-view check, wish-list-driven purchase + heart removal, payment-default flip,
store service/state dual comparison, homepage-claims verification, category sort
analysis, cross-domain account audit).

## Layout

- `verify_lib.py` — shared fail-closed machinery: trajectory identity gates (task_id
  match, `terminated` + `agent_done`, non-empty final answer, every recorded URL on
  the same loopback origin/port as `start_url`, every referenced screenshot a decodable
  PNG), navigation gates (search `/s/<query>` with sort modes, gallery facet params
  like `brand=` / `state=` / `sortBy=`, product pages, bag + three-step checkout, guest
  order tracker, account surfaces, coupons, gift cards, store locator), affirmative
  answer matching (phrases / counts / money amounts tolerant of `$`, `,`, trailing-zero
  and `X.5` vs `X.50` renderings), parallel-answer attribution (`fact_owner` — the
  reading-order subject governs its facts, so swapped two-store / three-claim
  attributions cannot pass), the frozen seed contract (schema sha256, per-table seed
  counts, benchmark-user identities, table-scanonical rows digest), exact DB-delta
  helpers for the ten stateful tasks, and advisory-only anchored LLM helpers (verdicts
  never depend on them; run with `--no_llm True`).
- `verify_0.py` … `verify_14.py` — one deterministic verifier per task.
- `append_rubrics.py` — the byte-preserving `verifier_path` + `judge_rubric` writer.
- `tests/` — 94 pytest cases covering the whole contract (honest / no-op /
  wrong-answer incl. attribution swaps / shortcut / mutated-after-DB / state-mismatch /
  wrong-delta / package tampering). Run from the `agent_demo` environment:

      cd agent_demo && uv run python -m pytest ../sites/jcpenney/verify/tests -q

  The tests acquire the seed DB from the review container (`wh-rev-jcpenney`), from
  `sites/jcpenney/instance_seed/jcpenney.db`, or from `$JCP_TEST_SEED_DB`, and run
  fully offline (sqlite-mutated snapshots, hand-written trajectories, tiny PNGs).

## Frozen seed contract

`SCHEMA_SHA256` / `SEED_COUNTS` / `SEED_ROWS_SHA256` pin `instance_seed/jcpenney.db`
(seed counts: 148 products, 90 stores, 32 categories, 6 coupons, 8 orders, 14 order
items, 6 addresses, 5 payment methods, 8 cart rows, 16 wish-list rows, 356 reviews,
631 product colors, 627 product images, 7 reward events, 9 static pages, 4 users; the
sixth-to-eighth static pages — Synchrony Pay Later, Product Recalls and Same Day &
Curbside Pickup — were added by the F2 fix and the digest was re-frozen).
Any snapshot pair that is not the frozen seed fails closed
(`snapshot_contract_invalid`). The seed rebuild is content-deterministic: a clean
rebuild (`PYTHONHASHSEED=0 python3 seed_data.py`) reproduces the frozen schema,
per-table counts and rows digest on every Python/SQLite pair (host 3.12.3/SQLite
3.45.1 and the image's 3.12.14/SQLite 3.40.1 both match). File-level md5 differs
across SQLite builds (page-layout artifact), so the contract pins content, not bytes.

## Contract notes (mirror-specific behaviors the verifiers encode)

- **Price rendering.** The `currency` Jinja filter renders two decimals, so the DOM
  shows `$37.50` for 37.50 and `$63.00` for 63.00. Verifiers accept either rendering
  (`contains_amount`). Range products display `$low - $high` (e.g. `$52.50 - $80.50`).
- **Checkout tax and shipping.** The review step applies the estimated tax to the
  discounted subtotal, matching the bag page's `?code=` convention; shipping is free
  once the PRE-discount subtotal reaches $75 (e.g. order: subtotal $68.99, discount
  $20.70, shipping $8.95, tax $3.98, total $61.22; redesigned chains with subtotal
  ≥ $75 freeze $0.00 shipping).
- **Order numbers.** Checkout order numbers are runtime-generated
  (`JCP` + `HHMMSS` + user id), so the redesigned purchase verifiers match the
  pattern `JCP\d{6}0?NN` per account id and validate the row's frozen amounts; the
  navigation gate accepts any `/checkout/confirmation/<number>` URL.
- **Address labels.** The profile's Add-an-Address form exposes a label field, so
  `verify_1` accepts the added row's label as either `""` or the task's `"Brother"`;
  the task's reportable facts (address count + unchanged default) are checked from
  the DOM and the DB row.
- **Rating display.** The PDP renders the raw 3.875 as `3.9` and the gallery shows
  `'%.1f'` averages (`3.8` for 3.75); `verify_12` pins the rendered form.
- **Price ties.** Two booties tie at $27.99 in the boots search / women's shoes
  category; the price-low sort orders them deterministically (seed `sort`), and the
  redesigned chains accept either bootie as "the cheapest" (their unit price is
  identical, so every frozen amount is tie-invariant).
- **GOSHOP15 terms vs application.** The coupon card advertises "$10 off your $50
  purchase" but the checkout applies the seeded 15% off; `verify_7` requires the
  answer to report the applied amount ($24.36 on the $162.37 subtotal) and the
  does-not-match verdict — the site's own discrepancy is the task's fact-check.
- **Gift message.** The review step collects the gift message (stored on the order
  row) but the confirmation page does not echo it, so `verify_10` pins the message in
  the DB after-state while the answer reports the balance, order number and total.
- **Payment radio order.** The checkout payment step pre-selects the OLDEST saved
  card (lowest id), not the default, so `verify_8` requires the trajectory to have
  entered the new card and the DB to show the default flip; the answer reports the
  card the placed order actually used.

## Verdicts

Output: `{task_id, pass, reason, evidence[]}` JSON on stdout; exit 0 on PASS, 1 on
FAIL. Any verifier error fails closed (`infra_error: true`).

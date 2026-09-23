# JCPenney — verifier contract (reviewer-authored)

This directory holds the grading contract for the 30 JCPenney benchmark tasks, written
by the reviewer (review-env skill Step 6). Ground truth is **hardcoded inside each
`verify_N.py`** — never in `tasks.jsonl` (the agent reads that file; an answer key there
would leak answers). After the reviewer's pass, each `tasks.jsonl` row carries
`verifier_path` + `judge_rubric` appended on top of the untouched five contributor keys
(`web_name, id, ques, web, upstream_url`) — see `append_rubrics.py`, which preserves the
original bytes as the line prefix and adds no `answer` key.

## Layout

- `verify_lib.py` — shared fail-closed machinery: trajectory identity gates (task_id
  match, `terminated` + `agent_done`, non-empty final answer, every recorded URL on the
  same loopback origin/port as `start_url`, every referenced screenshot a decodable
  PNG), navigation gates (search `/s/<query>` with sort modes, gallery facet params
  like `brand=` / `state=`, product pages, bag + three-step checkout, guest order
  tracker, account surfaces, coupons, gift cards, store locator), affirmative answer
  matching (phrases / counts / money amounts tolerant of `$`, `,`, trailing-zero and
  `X.5` vs `X.50` renderings), the frozen seed contract (schema sha256, per-table seed
  counts, benchmark-user identities, table-scanonical rows digest), exact DB-delta
  helpers for the six stateful tasks, and advisory-only anchored LLM helpers (verdicts
  never depend on them; run with `--no_llm True`).
- `verify_0.py` … `verify_29.py` — one deterministic verifier per task.
- `append_rubrics.py` — the byte-preserving `verifier_path` + `judge_rubric` writer.
- `tests/` — 164 pytest cases covering the whole contract (honest / no-op /
  wrong-answer / shortcut / mutated-after-DB / state-mismatch / wrong-delta / package
  tampering). Run from the `agent_demo` environment:

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
  shows `$37.50` for 37.50 and `$63.00` for 63.00 (the contributor's first pass
  stripped trailing zeros; F4 fixed it to match the upstream's two-decimal display).
  Verifiers accept either rendering (`contains_amount`). Range products display
  `$low - $high` (e.g. `$52.50 - $80.50`).
- **Checkout tax.** The review step applies the estimated tax to the discounted
  subtotal, matching the bag page's `?code=` convention (order: subtotal $68.99,
  discount $20.70, shipping $8.95, tax $3.98, total $61.22). The contributor's first
  pass kept the tax on the PRE-discount subtotal ($5.69/$62.93); F3 fixed the
  arithmetic and the frozen expectations moved with it (the pre-fix pair now feeds
  the wrong-amounts test variant).
- **Order numbers.** Checkout order numbers are runtime-generated
  (`JCP` + `HHMMSS` + user id), so `verify_8` matches the pattern `JCP\d{6}00?1` and
  validates the row's frozen amounts; the navigation gate accepts any
  `/checkout/confirmation/<number>` URL.
- **Address labels.** The profile's Add-an-Address form exposes a label field
  (added by the F5 fix; the first pass omitted it), so `verify_20` accepts the added
  row's label as either `""` or the task's `"Brother"`; the task's reportable facts
  (address count + unchanged default) are checked from the DOM and the DB row.
- **T5 rating display.** The PDP renders the raw 3.875 as `3.9`; both are accepted.
- **T0/T26 price ties.** Two products tie at $27.99 in the boots search / women's
  shoes category; the price-low sort orders them deterministically (seed `sort`), and
  T26 accepts either name.

## Verdicts

Output: `{task_id, pass, reason, evidence[]}` JSON on stdout; exit 0 on PASS, 1 on
FAIL. Any verifier error fails closed (`infra_error: true`).

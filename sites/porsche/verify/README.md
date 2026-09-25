# Porsche verifier contract

Deterministic grading contract for the 20 Porsche tasks (`sites/porsche/tasks.jsonl`).
One verifier per task: `verify_0.py` … `verify_19.py`, all driven by the shared
`verify_lib.py`. Ground truth is **hardcoded inside the verifiers** (never in
`tasks.jsonl`, which the benchmark agent reads).

## Verifier signature

```
python3 verify_<n>.py --run_dir RUN [--initial_db P] [--after_db P] [--container NAME]
```

Emits `{"task_id": …, "pass": true|false, "reason": …, "evidence": [...]}` and
exits 0 on PASS / 1 on FAIL. `--container` (default `$WH_CONTAINER` or
`wh-porsche-review`) supplies the seed and live DBs when the run directory does
not carry `initial.db` / `after.db`.

## Check layers

1. **Package identity** — task_id match, `terminated` / `agent_done`, non-empty
   final answer, every URL on the start_url's loopback origin, every screenshot
   a decodable PNG.
2. **Navigation gates** (anti knowledge-shortcut) — the on-site surfaces the
   task names must appear in the trajectory: the model overview with its exact
   filter combination, the per-variant model pages, the configurator page for
   the task's model code with the selected options in the query string, the
   Finder with the task's filters, the vehicle detail pages, the dealer
   directory (state / query), the shop category / product / cart / checkout /
   order pages, and the My Porsche surfaces (sign-in, register, saved
   vehicles, saved builds). A correct answer without the matching navigation
   is a recall shortcut and FAILs.
3. **Answer gates** — token / phrase / amount / count / VIN checks against the
   frozen ground truth below. Amounts tolerate `$`, thousands separators and
   optional cents; VINs are whitespace-insensitive.
4. **DB after-state** — read-only tasks (all except 6, 12, 18, 19) require a
   row-identical database. Stateful tasks require exactly the allowed delta:
   task 6 one `saved_builds` row (user casey.taylor, build_name "Weekend
   Taycan", model Y1AAI1, exactly two options summing below $10,000,
   total = 111,900 + sum); task 12 one `saved_vehicles` row (jordan.morgan,
   the least expensive Panamera, VIN WP0AA2A7XLL103745); task 18 one
   `shop_orders` row (casey.taylor, 4500 9th Ave NE / Seattle / WA / 98105,
   subtotal 24500, shipping 0, total 24500) plus its one `shop_order_items`
   row (Charge-o-mat Pro, qty 1, unit 24500) — the order number is matched
   against the DB row, not hardcoded; task 19 one `users` row
   (alex.rivera@test.com, Alex Rivera) plus one `saved_vehicles` row under it
   (the least expensive pre-owned 911, the 911 Carrera 4S Coupe, VIN
   WP0AB2A99ES121144).

## Frozen ground truth (summary)

Catalog snapshot 2026-09-24: 76 model variants, 331 configurator options
across 8 model codes, 442 in-stock vehicles, 218 Porsche Centers, 188 shop
products. Task-level anchors (see each `verify_<n>.py` docstring for the full
list): 911 extremes $135,500 / $387,000 (diff $251,500, 23 variants); 911
Carrera GTS 3,591 cc / 97.0 mm / 2.9 s / 4.8 ft³ / 194 mph / $181,000 /
$1,840.09 / 10 highlights; 19 electric variants with the 1,139 hp Cayenne
Turbo (Coupe) Electric pair and the $243,700 Taycan Turbo GT with Weissach
Package flagship (the task names the page; 2.1 s / 190 mph); Cayenne Turbo GT
$214,800 (19 variants) vs the $7,795 in-stock Cayenne; 9921B2 Jet Black
Metallic $880 + 40X $8,190 = $144,570 (44 options); catalogs 47/36/44 with the
$6,220 Club Leather Interior; finder anchors 911 S/T $610,099 (doc fee $200,
total $610,099), Taycan 4S $81,999 (39 electric Taycans, single facet label),
Panamera 4 E-Hybrid $123,795, Macan $77,100 with the verbatim lease estimate
and the Delivery, Processing and Handling Fee $2,350.00, Panamera 4 $46,032 /
GTS $196,180, the exact-name new 911 Carrera $181,575 (WP0AA2A99TS207294),
the least expensive pre-owned 911 (911 Carrera 4S Coupe $99,999,
WP0AB2A99ES121144, 32 in stock); dealers: Porsche Spokane 07:30 (4 WA
centers) with the WA stock leader Porsche Bellevue (236 vehicles, two
cheapest 2014 Cayenne $7,795 / 2017 Macan $18,000), CA 33 / FL 18 / TX 13
with McKenna Porsche (4500334, 10830 Firestone Boulevard, Sunday 10:00 -
18:00), Porsche Bellevue 236 vehicles (4501966) with its $359,992 911 GT3;
shop: 911 Soundbar 2.0 $4,070
(WAP0509110PSDB), wind-up toy car $19.00, Rear Bicycle Carrier $3,372, Classic
Leather Jacket $1,990 (4056487100289), Trench Coat $1,350, Charge-o-mat Pro
$245.

## Re-anchored at the r2 sync (474153bd fix)

The r1 review's NEEDS-FIX blockers and should-fix items were addressed on
`orch/contribute/porsche` @ 474153bd; this contract was re-synced against
that seed and task set. The previously flagged defects are resolved:

* **Task 10** — the fee sub-question is re-anchored to the always-present
  **Delivery, Processing and Handling Fee** ($2,350.00) in the cheapest new
  Macan's price details.
* **Task 13** — the unanswerable Spokane "two cheapest" sub-question is
  retired; the task now targets the WA stock leader's inventory (Porsche
  Bellevue, 236 vehicles, two cheapest 2014 Cayenne $7,795 / 2017 Macan
  $18,000).
* **Task 2** — the $243,700 flagship tie is resolved by naming the page
  (Taycan Turbo GT with Weissach Package, 2.1 s / 190 mph).
* **Task 8** — the fuel/drivetrain facets are normalized to the upstream
  clean labels; 39 is the single anchored electric-Taycan total.
* **Task 19** — the degenerate single-listing 718 anchor is replaced by the
  least expensive pre-owned 911 (32 in stock).
* **Task 4** — the scope is pinned to the exact model named '911 Carrera'
  (not the Cabriolet).
* **Task 6 / A-2** — the build-name input is form-associated
  (`form="cfgform"`), so the named save persists; the verifier's exact
  `build_name` contract is now achievable end to end.

The frozen seed rows hash was re-frozen accordingly (schema and row counts
are unchanged).

## Tests

`tests/test_verifiers.py` (run `python3 -m pytest sites/porsche/verify/tests -q`)
drives every verifier against hand-written trajectories in the
`agent_demo/agent.py` shape: honest runs MUST pass (stateful tasks against a
seed copy mutated through sqlite with the exact allowed delta), no-op /
wrong-answer / shortcut / mutated-DB / state-mismatch / wrong-delta / tamper
runs MUST all fail.

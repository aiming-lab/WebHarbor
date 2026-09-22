# Best Buy deterministic grading

Run `agent_demo/eval_judge.py --run_dir RUN --verifier True`. Each saved run may
supply `initial.db` and `after.db` together; explicit verifier database arguments
override saved snapshots. Otherwise the verifier uses the configured container.
Partial snapshot pairs are infrastructure errors. Screenshots, final answer and
required same-site navigation remain mandatory.

Read-only tasks accept product-name searches, equivalent numeric filter values,
common spelled numbers and unit equivalents. Answers must affirm the requested
facts without wrong values, wrong scales or contradictions. This is bounded
English parsing, not a general semantic judge; unsupported paraphrases may need
additional rules. State tasks use precise database changes. Wishlist/cart
confirmations need not repeat the product name. Checkout validates initial-cart
items and prices, fees, tax, total, email, status, fulfillment, payment and rewards.
Pickup labels are validated against available windows at the chosen store; the
schema stores the time window but not the selected day or slot ID.

Run focused regressions with `python -m unittest discover -s sites/bestbuy/tests -v`.
The fix report links fresh UI trajectories and independently expected controls.

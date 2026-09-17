The B&H tasks are graded through `agent_demo/eval_judge.py --verifier True`.
Each run needs `trajectory.json`, its referenced screenshots, and `initial.db` /
`after.db` snapshots (or the evaluator's equivalent container arguments).

Run a saved trajectory from the repository root:

```bash
uv run --project agent_demo python agent_demo/eval_judge.py \
  --run_dir /path/to/run --verifier True
```

The catalogue and the initial database define ground truth. Task 9 selects the
most recent individual review. Task 10 names the Canon Cinema Rig Kit bundle.
Task 11 requires complete effective sensor resolution data across the mirrorless
camera category and a unique maximum; missing values or ties invalidate the
fixture. Task 19 compares initial line subtotals, preserving the surviving line's
quantity and reporting the final total including tax.

Read-only tasks permit search logs but reject other database changes. Tasks
13–16 and 18–19 check exact row/field changes and preserve unrelated users and
records. Checkout also checks order items, prices, totals, and cart clearance.
Answer checks handle common unit/scale equivalents and negation. They are
rule-based checks for the English tasks, not a general natural-language judge.

Run catalogue, route, and verifier regression tests without an API key:

```bash
python3 -m unittest discover -s sites/bh_photo/tests -v
```

Use a Python environment with the site's Flask dependencies. Tests use temporary
databases; they do not modify the local preview or shipped seed. Browser replay
is a separate feasibility check; an LLM judge is optional and needs API/model
configuration.

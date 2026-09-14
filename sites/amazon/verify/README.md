# Amazon grading contract

The accepted Amazon task set has one deterministic verifier per task. Each
`tasks.jsonl` row points to the matching `verify_<id>.py` entry point and carries
an aligned `judge_rubric`.

Ground truth is derived from the run's initial SQLite snapshot. Read-only tasks
also require the after snapshot to be unchanged. The two stateful tasks compare
the demo account's wishlist or cart before and after the UI run and reject
unrelated database changes.

Run the contract tests from the repository root:

```bash
python3 -m unittest sites.amazon.verify.test_environment_quality
python3 -m unittest sites.amazon.verify.test_verifiers
```

Run one verifier directly:

```bash
python3 sites/amazon/verify/verify_0.py \
  --run_dir <run-dir> \
  --initial_db <initial.db> \
  --after_db <after.db>
```

Every verifier prints one JSON object and exits `0` for PASS or `1` for FAIL.
Malformed inputs fail closed with structured JSON. The test matrix covers real
positive fixtures, no-op and answer-only shortcuts, wrong-task replay, foreign
origins, wrong answers, state mismatches, unrelated mutations, swapped ranked
values, and legal alternative products.

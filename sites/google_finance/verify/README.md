# Google Finance task verifiers

These 20 deterministic verifiers require both the frozen answer and the
task-specific navigation recorded in `trajectory.json`. Task 19 additionally
compares the seed and live SQLite databases, so a self-reported portfolio
change cannot pass unless the requested portfolio and JPM lot were created.

Run the complete positive and negative test matrix from the repository root:

```bash
python3 -m unittest discover -s sites/google_finance/verify -p 'test_*.py' -v
```

Run one verifier directly:

```bash
python3 sites/google_finance/verify/verify_0.py --run_dir runs/google-finance-0
```

Or use the benchmark's unified grading entry point from `agent_demo/`:

```bash
uv run python eval_judge.py --run_dir runs/google-finance-0 --verifier True
```

For task 19, `--initial_db` and `--after_db` can point to explicit snapshots.
When omitted, the verifier copies `instance_seed/google_finance.db` and
`instance/google_finance.db` from `$WH_CONTAINER` (default: `wh-review`).

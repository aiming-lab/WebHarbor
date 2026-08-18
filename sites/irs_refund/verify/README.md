# IRS Refund Tracker task verifiers

These 18 deterministic verifiers require both the frozen answer and the
task-specific navigation recorded in `trajectory.json`. Task 8 also compares
the seed and live SQLite databases, so a self-reported profile change cannot
pass unless David Kim's requested state transition actually occurred.

Run the complete positive and negative test matrix from the repository root:

```bash
python3 -m unittest discover -s sites/irs_refund/verify -p 'test_*.py' -v
```

Run one verifier directly:

```bash
python3 sites/irs_refund/verify/verify_0.py --run_dir runs/irs-refund-0
```

Or use the benchmark's unified grading entry point from `agent_demo/`:

```bash
uv run python eval_judge.py --run_dir runs/irs-refund-0 --verifier True
```

For task 8, `--initial_db` and `--after_db` can point to explicit snapshots.
When omitted, the verifier copies `instance_seed/irs_refund.db` and
`instance/irs_refund.db` from `$WH_CONTAINER` (default: `wh-review`).

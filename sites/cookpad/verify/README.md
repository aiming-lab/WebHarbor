# Cookpad task verifiers

These 19 deterministic verifiers require both the frozen answer and the
task-specific navigation recorded in `trajectory.json`. Tasks 12 and 13 also
compare the seed and live SQLite databases, so self-reported shopping-list or
meal-plan changes cannot pass unless the requested state was actually created.

Run the complete positive and negative test matrix from the repository root:

```bash
python3 -m unittest discover -s sites/cookpad/verify -p 'test_*.py' -v
```

Run one verifier directly:

```bash
python3 sites/cookpad/verify/verify_0.py --run_dir runs/cookpad-0
```

Or use the benchmark's unified grading entry point from `agent_demo/`:

```bash
uv run python eval_judge.py --run_dir runs/cookpad-0 --verifier True
```

For stateful tasks, `--initial_db` and `--after_db` can point to explicit
snapshots. When omitted, the verifier copies `instance_seed/cookpad.db` and
`instance/cookpad.db` from `$WH_CONTAINER` (default: `wh-review`).

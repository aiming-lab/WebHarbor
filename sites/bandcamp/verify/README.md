# Bandcamp task verifiers

These 18 deterministic verifiers require both the frozen answer and the
task-specific navigation recorded in `trajectory.json`. Tasks 3, 4, 7, and 8
also compare the seed and live SQLite databases, so self-reported wishlist,
cart, checkout, or profile changes cannot pass unless the requested state was
actually created.

Run the complete positive and negative test matrix from the repository root:

```bash
python3 -m unittest discover -s sites/bandcamp/verify -p 'test_*.py' -v
```

Run one verifier directly:

```bash
python3 sites/bandcamp/verify/verify_0.py --run_dir runs/bandcamp-0
```

Or use the benchmark's unified grading entry point from `agent_demo/`:

```bash
uv run python eval_judge.py --run_dir runs/bandcamp-0 --verifier True
```

For stateful tasks, `--initial_db` and `--after_db` can point to explicit
snapshots. When omitted, the verifier copies `instance_seed/bandcamp.db` and
`instance/bandcamp.db` from `$WH_CONTAINER` (default: `wh-review`).

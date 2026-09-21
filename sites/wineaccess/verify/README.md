# WineAccess deterministic task verifiers

Each verifier requires task-specific navigation plus a frozen answer or a SQLite before/after state transition. Stateful tasks cannot pass from a self-reported answer alone. The grader reads `trajectory.json` from `--run_dir`; container mode copies both `instance_seed/wineaccess.db` and `instance/wineaccess.db` for state checks.

Run the focused suite with:

```bash
python3 -m unittest discover -s sites/wineaccess/verify -p 'test_*.py' -v
```

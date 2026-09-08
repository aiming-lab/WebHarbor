# IMDb deterministic verification

The current candidate contains ten tasks: `0, 2, 7, 9, 10, 12, 14, 15, 16, 17`
(seven read-only and three state-changing tasks). Tasks `3, 4, 8` were retired
after task-quality review; their historical runs remain historical evidence,
and their site features remain available. They have no current verifier entry.

Each task row references a `verify_<number>.py` entry point. These use Python's
standard library and read only the supplied, frozen run artifacts:

```bash
python3 sites/imdb/verify/verify_0.py --run_dir /absolute/path/to/run
```

The run directory contains `trajectory.json`, `before.db` (or `initial.db`),
and `after.db`. Explicit `--initial_db` and `--after_db` paths are also accepted.
The trajectory must include the task ID, the current question, a local HTTP
start URL, recorded steps and the final answer. Alternative localhost ports
are supported; navigation must stay on the run's original local origin.

The command emits one JSON object with `task_id`, `pass`, `reason`, and
`evidence`, returning zero on success and one on failure. The repository's
`agent_demo/eval_judge.py --verifier True` invokes these entries with only
`--run_dir`; no model credentials or live database are needed.

Expected entities and values are computed from the before snapshot. Read-only
tasks require all business tables to remain unchanged. Stateful tasks permit
only their specified account, target and change, and require corresponding UI
evidence. A correct final answer alone does not demonstrate task execution.
Offline snapshots and trajectories are trusted evaluator inputs, not a defense
against an actor who can fabricate the entire run package.

Synthetic regression tests exercise failed actions, wrong entities, extra
changes and equivalent answers/paths. They do not count as browser runs:

```bash
python3 -m unittest discover -s sites/imdb/tests -v
```

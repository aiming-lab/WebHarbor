# Recreation.gov grading contract

The primary grader is entirely offline and deterministic. It never calls an LLM
or copies a live container database. The repository's secondary LLM judge remains
available separately; an unavailable model cannot turn a wrong answer into PASS.

Capture `initial.db` before the task and `after.db` after it using SQLite backup,
and keep them beside `trajectory.json`. Capture both even for read-only tasks.
Use a fresh fixture and browser context for each task. Missing/corrupt snapshots
are reported as evidence errors, not replaced with mutable live state.

```bash
uv run --project agent_demo python agent_demo/eval_judge.py \
  --run_dir /absolute/path/to/run --verifier True
```

Each `verify_N.py` also accepts explicit `--initial_db` / `--after_db` paths.
`--no_llm True` and `--container NAME` remain accepted for CLI compatibility but
have no effect. Use `--origin http://host:port` to supply a trusted mirror origin;
otherwise the runner-supplied `start_url` establishes it. Task IDs must match.
Only recorded successful page URLs count; a navigation request is not proof of
a loaded page. Task 1 requires the gallery anchor, recorded section visibility
(`visible_sections`), or an explicit successful scroll to `#media-gallery`.
The UI's View Photos link makes the gallery anchor available to standard agents.
Task 4 requires Alaska search/state results; task 9 requires all three pass pages.

`answers.py` holds finite fact/phrase contracts for the frozen fixture. It checks
affirmative concepts, distinct scenes, entity/attribute associations, and common
equivalents (including “both”). These are not a general natural-language theorem
prover: new valid phrasing should be added with both a positive regression test
and a nearby negative. Ground truth stays in reviewer files, not tasks.jsonl.

`state.py` compares all logical rows against the exact permitted delta. Read tasks
allow no mutations. Stateful tasks validate owner, new versus existing records,
status, dates, quantity/default selection, money, registration credentials and
default records, review ownership/content, and preservation of unrelated data.
Timestamps and allocated IDs are allowed to vary only on the intended new rows.
Review ownership uses immutable `user_id`; imported anonymous reviews stay null.
Old task-16 snapshots without ownership must be rerun, not retroactively assigned
to a user based on their display name.

## Seed migration and local startup

`scripts/fetch_assets.sh` and Docker build apply `migrate_seed.py` to the pinned
seed. It adds the nullable review owner column and is byte-idempotent. For a
standalone checkout, migrate the seed and copy it to an isolated `instance/`
before launching Flask. Never migrate or reset another user's running preview.

## Regression checks

```bash
python3 -m unittest discover -s sites/recreation_gov/tests -v
python3 sites/recreation_gov/verify/regression_controls.py \
  --runs /absolute/path/to/fixed-browser-runs \
  --out /absolute/path/to/new-controls
```

The controls copy evidence before mutations and declare expected results before
grading. They are synthetic tests, not browser completions. A successful control
suite does not establish full UI fidelity or prove that every phrasing is handled.

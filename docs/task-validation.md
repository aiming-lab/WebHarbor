# Validate Tasks

Use the repository task validator to check task JSONL files, site registration, localhost ports, and optional reviewer grading metadata before opening a review or PR. Ground-truth fields in agent-facing task rows are rejected; unrecognized metadata is reported as a warning and fails under `--strict`.

```bash
python scripts/validate_tasks.py
python scripts/validate_tasks.py --site amazon
python scripts/validate_tasks.py --tasks sites/amazon/tasks.jsonl
python scripts/validate_tasks.py --strict
python scripts/validate_tasks.py --json
```

## Current corpus compatibility

The scan reports findings; it does not rewrite tasks. At upstream `b3275d7`, the
94-site / 2,315-task scan reports 261 errors and 10 warnings. These include task
identity conventions, object-valued rubrics and shared verifier paths; see
[the review report](../review-reports/PR-45-TASK-VALIDATOR.md) for the breakdown.
A nonzero result is not a validator crash or evidence that every finding has
been independently adjudicated.


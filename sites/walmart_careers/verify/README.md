# Walmart Careers deterministic grading contract

Each row in `sites/walmart_careers/tasks.jsonl` points to `verify_0.py` through `verify_19.py`. The wrappers use `verify_lib.py` for package, URL, answer and state validation and `ground_truth.py` to derive every qualifying set and target from the supplied initial SQLite snapshot. No verifier calls an LLM.

## Inputs

```bash
python sites/walmart_careers/verify/verify_0.py \
  --run_dir /absolute/path/to/run \
  --initial_db /absolute/path/to/initial.db \
  --after_db /absolute/path/to/after.db
```

If explicit snapshots are omitted, the verifier checks `<run_dir>/initial.db` and `<run_dir>/after.db`, then falls back to `docker cp` from `$WH_CONTAINER` or `wh-review`. Missing or invalid inputs fail closed. Output is JSON with `task_id`, `pass`, `reason`, and `evidence`; exit code 0 means PASS and 1 means FAIL.

## Package validation

Every run must provide:

- the exact task ID;
- a nonempty final answer;
- `terminated: true` with `termination_reason: agent_done`;
- at least one recorded step;
- HTTP URLs on the same loopback origin and port as `start_url`;
- both referenced screenshots for every step;
- PNG files that fully decode to nonempty images.

The verifier validates recorder packaging and declared browser history. A deterministic verifier cannot cryptographically authenticate the recorder or bind screenshot pixels to the declared URL, so release evidence also includes independent Playwright execution against the packaged image.

## Snapshot validation

The initial and after snapshots must have the exact nine-table Walmart Careers schema, including `seed_metadata` version `walmart-careers-v2`. The initial snapshot must contain 246 jobs, 51 stores, 33 categories, seven areas, four users and no application drafts. `areas`, `categories`, `stores`, `jobs`, `seed_metadata`, and `application_drafts` must be row-identical before and after. Any schema change or immutable-catalog mutation fails closed.

Read-only tasks additionally preserve `users`, `saved_jobs`, and `applications`. Stateful verifiers enforce exact added, removed or changed rows across all mutable tables. They reject collateral writes, stale-state no-ops, duplicate logical actions, changes to existing applications, extra users and extra saves.

## Ground truth and workflows

`ground_truth.py` queries the initial snapshot and fails on missing candidates, unexpected candidate cardinality, or tied extrema. Comparison tasks require every detail page needed to read hidden comparison values. Tasks requiring login, registration, career-area navigation, filters, application confirmation, profile update or save/remove actions enforce the required page order.

Results gates parse query parameters. Facets use exact values, scalar values require exact equality, locations require the intended city/state scope, and keyword searches use whole normalized tokens. Task-requested filters must appear together when the task requires their conjunction.

Answer matchers require affirmative values and reject negated occurrences. Requisition IDs, confirmation numbers, streets, shift windows, position counts, worker types, hashtags and qualification text are checked against the dynamically validated target. Complete street directionals and suffixes are required, with standard abbreviations accepted.

## Tests

```bash
python -m pytest sites/walmart_careers/tests sites/walmart_careers/verify/tests -q
```

The verifier fixtures copy the complete generated seed schema and invoke every verifier as a subprocess. Regression coverage includes malformed package evidence, corrupt PNGs, wrong task IDs, wrong answers, missing filters/pages, reordered workflows, schema/catalog mutation, unrelated state writes, stale-state preconditions, duplicate or extra rows, and positive representation variants. Application tests separately exercise the actual Flask routes and generated seed.

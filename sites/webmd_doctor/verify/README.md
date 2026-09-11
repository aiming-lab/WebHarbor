# WebMD Doctor deterministic grading contract

Each row in `sites/webmd_doctor/tasks.jsonl` points to `verify_0.py` through `verify_19.py`. The wrappers use `verify_lib.py` for package, URL, answer and state validation and `ground_truth.py` to re-derive every target from the supplied initial SQLite snapshot. No verifier calls an LLM; a verdict never depends on a key or a model.

## Inputs

```bash
python sites/webmd_doctor/verify/verify_0.py \
  --run_dir /absolute/path/to/run \
  --initial_db /absolute/path/to/initial.db \
  --after_db /absolute/path/to/after.db
```

If explicit snapshots are omitted, the verifier checks `<run_dir>/initial.db` and `<run_dir>/after.db`, then falls back to `docker cp` from `$WH_CONTAINER` (default `wh-review`): `instance_seed/webmd_doctor.db` is the initial state and `instance/webmd_doctor.db` the after state. Missing or invalid inputs fail closed (`infra_error: true`, exit 1). Output is JSON with `task_id`, `pass`, `reason` (the first failing check) and `evidence`; exit code 0 means PASS and 1 means FAIL. `agent_demo/eval_judge.py --run_dir <dir> --verifier True` is the normal entry point; a `--no_llm` flag is accepted for parity and ignored.

## Package validation

Every run must provide the exact task ID, a nonempty final answer, `terminated: true` with `termination_reason: agent_done`, at least one recorded step, HTTP URLs on the same loopback origin and port as `start_url`, and both referenced screenshots for every step decoding as nonempty PNGs. A `max_steps` run has no final answer and fails on the first check.

## Snapshot validation

Both snapshots must have the exact 28-table WebMD Doctor schema (hash pinned), `seed_metadata.version = webmd-doctor-v1`, and the frozen seed counts (226 doctors, 348 locations, 12 hospitals, 30 practices, 10 specialties, 4 users, 4 saved providers, 1 appointment request, 1 pending user review). The 24 catalog tables must be row-identical before and after. `ground_truth.py` then re-derives the task's target from the initial snapshot the way the task text selects it (specialty + city, combined filters within the search radius, the saved list, a hospital roster, an award class) and fails closed if it disagrees with the constants hardcoded in the verifier.

The four runtime tables are `users`, `saved_providers`, `appointment_requests` and `user_reviews`. Read-only tasks (0-7, 9-15) require all four to be row-identical, so an incidental save or review fails. Stateful verifiers (8, 16, 17, 18, 19) check the exact row delta on the touched table first (`<table>_exact_delta`: nothing written and a duplicate write both stop there, with the delta in the evidence), then the identity of the new or removed row (owner, doctor, office, slot, stars, text, e-mail typed on the Sign Up page), then identity on the other runtime tables (`<table>_unchanged`). Removing the wrong saved provider, a review on a same-surname doctor, a booking at the primary office or a save under a demo account each fail on a named row check; a collateral write in another table fails on that table's `_unchanged` check.

## Gates and answer matchers

Profile visits match `/doctor/<slug>-overview` and its three tab aliases; booking, save and review endpoints are not profile visits. Comparison tasks (13, 14) require both detail pages. Route gates apply only where the task text mandates the route: a `/results` visit whose query carries the specialty (as `q` text or `sids`), the "near Newark, DE 19711" rule (`loc` absent, `19711`, or Newark, DE; any other city fails), and, for tasks 9-11, every requested filter on one URL. Task 12 requires the specialty menu path in order plus the 4-stars-and-up filter on the city page; 14 requires the Delaware hospitals list and the hospital page before the profiles; 15 the awards page, the Patient's Choice recipients list, the profile and the practice page in order; 6 the second review page; 16 the Saved Providers page after the profile; 18 ends on the profile.

Answer matchers are negation-aware whole-token matches: institution and office names (punctuation, dash style and `&`/`and` ignored), years as standalone four-digit tokens, NPIs as one 10-digit token, phones by digit comparison, opening windows by both clock endpoints (`8 am`, `8:00 AM`, `08:00`), wait times in minutes with clock times masked, star ratings tied to a star/rating token, review dates in six formats, first + last name for comparison winners, the booking reference matched against the new database row (never a literal, and no other reference may appear), and the practice website with its domain ending.

## Validation (LLM-free matrix)

Every verifier was exercised end to end through `agent_demo/eval_judge.py --run_dir <dir> --verifier True` on scripted Playwright runs that reproduce the `agent_demo/agent.py` run signature (trajectory with url-before-action steps, typed text in `input` params, PNG screenshots, `initial.db` copied after `POST /reset/webmd_doctor`, `after.db` copied when the run ends). Rows: no-op (20 tasks), genuine click-walk (20), knowledge shortcut with the correct answer but no profile or route visit (20), genuine path with one decoy fact (18), stateful path with the write skipped (5), genuine path plus a collateral write in another runtime table (5), genuine path plus a duplicate write in the same table (5), read-only task with one incidental save while logged in (15), and the mandated route bypassed (8). 116 cells; every genuine run passes and every other cell fails on the intended check (first failing check recorded per cell). The matrix exposed one verifier defect, fixed before this commit: the stateful verifiers ran the row-identity or `exactly_one_*` count check before `<table>_exact_delta`, so "nothing written" surfaced under the wrong name; the delta check now comes first and the redundant count checks were removed. A run with no snapshots and an unreachable container exits 1 with `infra_error: true`; `POST /reset/webmd_doctor` after the whole matrix restores the byte-identical seed. No LLM is involved anywhere in the matrix.

## Tests

```bash
python -m pytest sites/webmd_doctor/verify/tests -q
```

The fixtures copy the frozen seed and rewrite only the four runtime tables, then invoke every verifier as a subprocess with hand-written trajectories in the `agent_demo/agent.py` shape. Every task covers the genuine run, run-dir snapshot discovery, the no-op run, a wrong task id, an unterminated run, a mixed-origin run, a corrupt screenshot, schema and catalog tampering, a wrong seed marker, a re-targeted seed, the knowledge shortcut, wrong answers per fact, and (read-only) an incidental write or (stateful) missing, duplicated, misattributed and collateral rows. `test_verify_lib.py` covers each matcher's accepted variants and rejections, the Newark rule, ordered workflows and the snapshot contract. No docker and no API key are needed.

# Amtrak deterministic grading contract

Each row in `sites/amtrak/tasks.jsonl` points to `verify_0.py` ... `verify_17.py`. The
verifiers share `verify_lib.py` (package validation, navigation gates, answer matchers,
SQLite state checks). Ground truth is hardcoded in each `verify_N.py` and never appears
in `tasks.jsonl`. No verifier calls an LLM; `--no_llm True` is accepted and changes nothing.

## Inputs

```bash
python sites/amtrak/verify/verify_0.py \
  --run_dir /absolute/path/to/run \
  --initial_db /absolute/path/to/initial.db \
  --after_db /absolute/path/to/after.db
```

If explicit snapshots are omitted the verifier looks for `<run_dir>/initial.db` and
`<run_dir>/after.db`, then falls back to `docker cp` from `$WH_CONTAINER` (default
`wh-review`, paths `/opt/WebSyn/amtrak/instance_seed/amtrak.db` and
`/opt/WebSyn/amtrak/instance/amtrak.db`). Missing or invalid inputs fail closed
(`infra_error: true`). Output is JSON `{task_id, pass, reason, evidence[]}`; exit code
0 means PASS and 1 means FAIL. `agent_demo/eval_judge.py --run_dir <run> --verifier True`
invokes the script named by the trajectory's `verifier_path`.

## Package validation (every task)

- exact task id; non-empty final answer; `terminated: true` with `termination_reason: agent_done`;
- at least one recorded step; every recorded URL is HTTP on the same loopback origin and
  port as `start_url` (the port itself is not pinned: runs use alt ports);
- both referenced screenshots exist for every step and decode as PNGs of at least
  64x64 (a decodable 1x1 forgery used to pass and no longer does).

## Snapshot contract

`initial.db` must be the untouched seed: the 22-table schema, the seeded row counts
(4 users, 62 stations, 18 routes, 252 trips, 1120 trip segments, 1008 fare options, 336
sleeper rooms, 60 bookings, 80 tickets, ...) and the four benchmark accounts. `after.db`
must keep the same schema, and every catalog table (`cities`, `stations`, `routes`,
`route_stops`, `trains`, `trips`, `trip_segments`, `fare_classes`, `fare_options`,
`sleeper_rooms`, `service_alerts`, `deals`, `help_articles`) must be row-identical.

Read-only tasks additionally require `users`, `reward_accounts`, `reward_activities`,
`bookings`, `booking_segments`, `tickets`, `passengers`, `payment_mocks` **and
`search_logs`** to be row-identical. `search_logs` used to be excluded everywhere,
because the site committed a row on every `/search`, `/help?q=` and `/booking/results`
request. That write was removed during review, so read-only browsing now leaves the
database byte-identical and a `search_logs` row in an after-state is a regression, not
expected drift. Tasks 8 and 17 assert it too: the only writes they authorise are the
profile update and the new booking.

## Per-task contract

| Task | Kind | Navigation gate | Answer check | State check |
|---|---|---|---|---|
| 0 | read | `/booking/results` NYP->WAS 2026-04-20 with `sort=duration` | route + train number + travel time (both durations printed on the card accepted) | read-only |
| 1 | read | `/booking/results` NYP->WAS 2026-04-20, price sort, direct-only off | route + starting fare (to the cent) | read-only |
| 2 | read | round-trip results WAS->PHL 04-20 / return 04-22, then `leg=return`, `/booking/select-trip`, `/booking/select-fare` in order | per-traveler Business fare of the two fastest legs | read-only |
| 3 | read | `/booking/multi-city` -> `/booking/select-trip` -> `/booking/select-fare` in order | per-traveler Value fare of the three cheapest legs | read-only |
| 4 | read | results SEA->LAX 2026-04-22 `passengers=2` -> select-trip -> select-fare -> `/booking/rooms` | room type + extra cost | read-only |
| 5 | read | `/login` with alice's email typed; `/account/trips` or the trip page | booking code + origin code + departure date of the DEN trip | read-only |
| 6 | read | `/trip-lookup` then `/trip/ALGX87` | route name + departure date | read-only |
| 7 | read | `/login` as alice; `/account/rewards` | points balance | read-only |
| 8 | stateful | `/login` -> `/account/edit` -> `/account/rewards` in order | preferred station code | alice's `users` and `reward_accounts` rows differ from the seed in `preferred_station_code` only; nothing else changes |
| 9 | read | `/routes/amtrak-cascades` | all stop codes in order | read-only |
| 10 | read | `/service-alerts` | next-step wording of the Coast Starlight major advisory | read-only |
| 11 | read | `/service-alerts` | boarding track number (affirmative, not the former track) | read-only |
| 12 | read | results CHI->DEN 2026-04-20, plus `fare_class=flexible` results or `/booking/select-fare` | route + Flexible price | read-only |
| 13 | read | results SAC->SJC 2026-04-16 with Saver (or default) fare class | route + starting fare | read-only |
| 14 | read | `/stations/ANA` and `/stations/SBA` | the station with checked baggage, affirmatively | read-only |
| 15 | read | `/help/checked-baggage-timing` | cutoff minutes + departure kind | read-only |
| 16 | read | a help/site search for "refund" and `/help/refunds-and-credits` | exact title + category | read-only |
| 17 | stateful | `/login` -> results NYP->WAS 2026-04-20 -> select-trip -> select-fare -> passengers -> review -> checkout -> confirmation in order | the new booking code (matched against the new row) | exactly one new booking for alice (NYP->WAS, 2026-04-20, one direct Business segment), its tickets / passengers / mock payment / reward activity only, points credited, other users untouched |

Answer matchers require affirmative mentions (negated phrases such as "not track 3" do
not count) and accept common renderings: `$96.56` / `96.56`, `2h 50m` / `2 hours 50
minutes` / `2:50`, `Apr 20, 2026` / `2026-04-20` / `April 20 2026`, `4786` / `4,786`.

## Tests

```bash
# offline matrix (synthetic runs + seed-derived snapshots; no Playwright, no docker, no LLM)
python -m pytest sites/amtrak/verify/tests -q
# or: python -m unittest discover -s sites/amtrak/verify/tests

# live matrix against a running mirror (Playwright, from the agent_demo uv project)
AMTRAK_BASE=http://127.0.0.1:41024 AMTRAK_RESET_CMD='curl -sX POST http://127.0.0.1:8201/reset/amtrak' \
AMTRAK_SEED_DB=... AMTRAK_INSTANCE_DB=... uv run python sites/amtrak/verify/tests/live_matrix.py --out_dir runs/amtrak_matrix
```

`test_verify_matrix.py` drives every verifier through genuine, no-op, shortcut,
wrong-answer, other-task-id, unterminated, foreign-origin, corrupt-screenshot,
schema-tamper and collateral-write cases (plus state-mismatch and over-reach cases for
tasks 8 and 17). `live_matrix.py` records real Chromium runs in the `agent_demo/agent.py`
format (trajectory + screenshots + `initial.db`/`after.db`) and prints the same matrix
against the live site; both directories are excluded from the Docker image by
`.dockerignore` (`sites/*/verify/tests/`).

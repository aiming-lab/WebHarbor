# AccuWeather deterministic grading contract

Each row in `sites/accuweather/tasks.jsonl` points to `verify_0.py` … `verify_19.py`
(`verifier_path`) and carries an English `judge_rubric` of fact checkpoints. Ground
truth lives ONLY inside the verifiers; `tasks.jsonl` has no `answer` key. No verifier
calls an LLM: `verify_lib.py` keeps `llm_text_match` / `llm_screenshot_shows` for API
parity with `sites/merriam_webster/verify`, but no verdict depends on them and
`--no_llm True` is accepted for CLI parity.

## Inputs

```bash
cd agent_demo && uv run python ../sites/accuweather/verify/verify_0.py \
  --run_dir /abs/path/to/run [--initial_db initial.db --after_db after.db] [--no_llm True]
```

`agent_demo/eval_judge.py --run_dir <run> --verifier True` invokes the same script.
Snapshots resolve in this order: explicit `--initial_db` / `--after_db`, then
`<run_dir>/initial.db` + `<run_dir>/after.db`, then `docker cp` from
`$WH_CONTAINER` (default `wh-review`) of `/opt/WebSyn/accuweather/{instance_seed,instance}/accuweather.db`.
Missing or invalid snapshots fail closed (`infra_error: true`). Output is JSON
`{task_id, pass, reason, evidence[]}`; exit 0 = PASS, 1 = FAIL.

## Package validation (every task)

- exact `task_id`; non-empty `final_answer`; `terminated: true` with
  `termination_reason: agent_done`; at least one step;
- every recorded URL (`start_url`, step `url` / `url_before` / `url_after`, `final_url`)
  is `http://` on a loopback host with the same host and port as `start_url`;
- both screenshots of every step exist and decode as non-empty PNGs (header + IHDR CRC).

## Snapshot contract

Both snapshots must have exactly the six tables `user, location, forecast, hourly,
saved_location, alert` with the expected columns. The initial snapshot must hold
20 locations / 140 forecasts / 240 hourly rows / 4 seeded users / 2 saved rows
(Alice: New York, Boston) / 0 alerts, and its `location + forecast + hourly` rows must
hash to `CATALOG_FINGERPRINT` (sha256 of the build-generated seed; password salts
are excluded so a rebuilt seed still validates). `location`, `forecast` and `hourly`
must be row-identical before and after. Read-only tasks additionally require
`user`, `saved_location` and `alert` to be row-identical. Stateful tasks require the
exact allowed delta and nothing else:

| task | required navigation (in order where stated) | state delta |
|---|---|---|
| 6 | `/login` → `/weather/seattle-wa` → `/account`, typed `alice.j@test.com` | +1 saved row Alice→Seattle |
| 7 | `/login` → `/weather/boston-ma` → `/account` | −1 saved row Alice→Boston |
| 8 | `/login` → `/alerts/chicago-il`, typed `bob.smith@test.com` | alert rows == {Bob/Chicago/severe, Bob/Chicago/rain}, enabled |
| 9 | `/login` → `/settings` → `/weather/new-york-ny` | Carol `unit` F→C, all other columns/rows identical |
| 15 | `/login` → `/weather/phoenix-az` → `/account` and `/login` → `/weather/miami-fl` → `/account` | +2 saved rows David→Phoenix, David→Miami |
| 18 | `/register` (typed `jamie.lee@example.test`) → `/weather/atlanta-ga` → `/account` | +1 user (email, name "Jamie Lee", password verifies via hashlib scrypt/pbkdf2) and +1 saved row for that user → Atlanta |

## Navigation gates (anti knowledge-shortcut)

Every fact page whose values the answer reports must appear in the trajectory
(`/weather/<slug>`, `/hourly/<slug>`, `/daily/<slug>`, `/air-quality/<slug>`,
`/radar/<slug>`); comparison tasks (4, 12, 16, 19) need both detail pages. When the
target is not linked from the homepage grid (everything except New York, Phoenix,
Seattle, Miami, Chicago, Boston, Austin, Denver) the trajectory must contain a
`/search?q=` visit that would surface the target under the site's own token scoring
(`search_surfaces`); task 10 requires the literal postal-code query `94102`.

## Answer matchers

`contains_fact(text, value, unit, label)` accepts a standalone number, a number with
its unit (`104°`, `104 F`, `18%`, `8 mph`, `29.89 in`), or a number bound to its label
(`humidity: 18`); when the answer binds a *different* number to that label
(`temperature 115, RealFeel 104`) the check fails, so value/label swaps are caught
whenever the agent labels its values. Numbers are matched as whole values (`104`
never matches `1040` or `104.5`). Conditions are matched as phrases and single-word
conditions reject qualified variants (`Cloudy` ≠ `Mostly cloudy`). Clock times accept
`4 PM`, `4:00 p.m.`, `16:00`; day labels accept `Sat` / `Saturday`. Comparison tasks use
`names_winner`, which attributes the comparative word (`cooler`, `better`, `warmer`,
`higher`) to the nearest city in the sentence and rejects the inverse attribution.
All matchers are negation-aware (`not 18%` does not count).

Known limit: when an agent reports two same-unit values with no labels at all
(`103°, 82°`) a swap between them is not detectable; the winner check still has to
name the right city.

## Tests

```bash
cd agent_demo && uv run python -m unittest discover -s ../sites/accuweather/verify/tests -p 'test_*.py'
```

`tests/_support.py` rebuilds the seed with plain sqlite3 from the same constants and
formulas as `app.py` (`test_verify_lib.py` asserts the fixture reproduces
`CATALOG_FINGERPRINT`) and writes trajectories in the `agent_demo/agent.py` layout.
Every task module covers: genuine PASS, run-dir snapshot discovery, no-op (empty
answer), wrong task id, shortcut (no navigation), wrong answers, alternative
phrasings, unterminated run, mixed origin, corrupt PNG, schema / catalog / seed drift
(fail closed), and read-only collateral writes or stateful mismatch.

`tests/run_matrix.py` drives every task through a real Chromium against a standalone
copy of the site and grades pass / noop / shortcut / wrong / mismatch run dirs with
live SQLite snapshots (CONTRIBUTING §C). `tests/` is excluded from the Docker image by
`.dockerignore`.

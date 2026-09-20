# Adopt-a-Pet deterministic grading contract

Each row in `sites/adopt_a_pet/tasks.jsonl` points at `verify_0.py` … `verify_19.py`. The
wrappers share `verify_lib.py` (package, navigation, answer and SQLite-state checks) and
`ground_truth.py` (the frozen 20-pet / 6-shelter / 4-user catalog transcribed from `app.py`).
No verdict depends on an LLM; the `llm_*` helpers exist only for API parity with
`sites/merriam_webster/verify` and short-circuit under `--no_llm True`.

## Inputs

```bash
uv run python sites/adopt_a_pet/verify/verify_0.py --run_dir /abs/run --no_llm True \
    [--initial_db /abs/initial.db --after_db /abs/after.db] [--container wh-review]
```

Snapshots resolve in this order: explicit flags, `<run_dir>/initial.db` + `<run_dir>/after.db`,
then `docker cp` from `$WH_CONTAINER` (default `wh-review`) at
`/opt/WebSyn/adopt_a_pet/{instance_seed,instance}/adopt_a_pet.db`. Missing or invalid snapshots
fail closed (`database_unavailable` / `snapshot_contract_invalid`, `infra_error: true`). Output is
JSON `{task_id, pass, reason, evidence[]}`; exit 0 = PASS, 1 = FAIL. `agent_demo/eval_judge.py
--run_dir RUN --verifier True` is the normal entry point.

## Package validation (every task)

- exact `task_id`; non-empty `final_answer`; `terminated: true` with `termination_reason: agent_done`;
- at least one step; every recorded URL (`start_url`, step `url`s, `final_url`) on the same
  loopback host **and port** as `start_url` (alt ports such as 41024 are fine, off-site URLs are not);
- both screenshots referenced by every step exist and decode as PNG.

## Snapshot contract (every task)

Both snapshots must have exactly the six tables `user, shelter, pet, favorite, application,
pet_alert` with the column order produced by `app.py`'s models and identical schemas. The initial
snapshot must contain 4 users, 6 shelters, 20 pets, 1 favorite (alice.j -> luna), 0 applications and
0 alerts, and its `pet` / `shelter` / `user` rows must equal `ground_truth.py` (any catalog edit makes
every verifier fail closed instead of grading against stale truth). `pet` and `shelter` must be
row-identical before and after. Read-only tasks additionally require `user, favorite, application,
pet_alert` to be row-identical; stateful tasks require the exact row delta listed below and reject
collateral writes, duplicates, wrong users and stale-state no-ops.

## Search semantics the gates rely on

`app.search()` scores the `location` box by token overlap with `"<city> <state> <postal>"`, so any
query containing the state token (`Phoenix, AZ`, `Arizona`, `AZ`, `Tucson AZ`) returns **every**
Arizona pet, while a bare city (`Phoenix`) returns only that city. `verify_lib.AZ_WIDE` therefore
accepts any query whose tokens contain `az` or `arizona`. Result pages hold 6 cards; hidden facts
(fee, months, color, house-trained, good-with-*) are only on `/pet/<slug>`; shelter phone / e-mail
are only on `/shelter/<id>`.

## Per-task contract

| Task | Kind | Navigation gates | Answer / state checks |
|---|---|---|---|
| 0 | read | `/search` location ~ phoenix, species=Dog; `/pet/waymo` | both breeds, age group, size, `$fee` |
| 1 | read | `/search` location ~ scottsdale, species=Cat; `/pet/neo` | name, months, color, good-with-children = yes |
| 2 | read | `/search` AZ-wide, species=Dog, sex=Male **and** `page=2`; all 7 male AZ dog profiles | winner name, both breeds, `$fee`, winner attached to "lowest" |
| 3 | read | `/search` AZ-wide, species=Cat, age=Adult; `/pet/casper` + `/pet/cinders` | winner name, city, breed, `$fee`, attached to "lowest" |
| 4 | read | any `/search`; `/pet/arno`; `/shelter/1` | rescue name, phone (any separators), e-mail |
| 5 | read | `/search` location ~ seattle; `/pet/daisy` + `/pet/pepper` | both names, both species, both months, both fees, lower-fee pet attached |
| 6 | state | `/login` (alice) -> `/pet/sirius` -> `/account` | favorite += {alice->sirius} exactly; luna kept; other tables unchanged; answer names both |
| 7 | state | `/login` (alice) -> `/pet/luna` -> `/account` | favorite -= {alice->luna} exactly; answer names Luna |
| 8 | state | `/login` (bob) -> `/pet/daisy` -> `/apply/daisy` -> `/account` | application += 1 row (bob, daisy, phone digits, housing, exact experience, Submitted) |
| 9 | state | `/login` (carol) -> `/alerts` -> `/account` | pet_alert += 1 row (carol, Cat, siamese, 33130, 50) |
| 10 | read | `/shelters?q~seattle`; `/shelter/4` | shelter name, phone, e-mail, Daisy + Pepper |
| 11 | read | `/breeds`; `/search?breed~maine coon&species=Cat`; `/pet/milo` | name, sex, city, `$fee` |
| 12 | read | `/search` AZ-wide, species=Dog, size=Small; the 3 Adult profiles | winner name, months, both breeds, city, attached to "youngest" |
| 13 | read | `/search` location ~ austin, species=Dog, sex=Female; `/pet/ruby` | name, `$fee`, good-with-cats = no, good-with-children = no |
| 14 | read | `/search` location ~ new york / ny; `/pet/luna` + `/pet/milo` | both names, both fees, lower-fee pet attached |
| 15 | state | `/login` (david) -> `/pet/archie` -> `/account` and -> `/pet/ruby` -> `/account` | favorite += {david->archie, david->ruby} exactly |
| 16 | state | `/register` (e-mail typed) -> `/pet/olive` -> `/account` | user += 1 (e-mail, name, scrypt hash verifies `PetFriend123!`); favorite += {jamie->olive} |
| 17 | read | `/search` location ~ miami, species=Dog, age=Senior; `/pet/teddy` | name, months, both breeds, `$fee`, house-trained = yes |
| 18 | read | `/blog` | the three exact titles (punctuation-insensitive) |
| 19 | read | `/search` AZ-wide, species=Dog **and** `page=2`; all 8 AZ dog profiles | winner name, city, both breeds, months, `$fee`, attached to "lowest" |

Answer matchers are affirmative and negation-aware (`not $165`, `isn't good with cats` do not
count as matches). Money accepts `$165`, `$165.00`, `165 dollars`; months accept `36 months`,
`36-month-old`, `36 mo`; yes/no statements accept `X: Yes`, `X? No`, `not X`, `she is X`,
`X and Y: No`, `neither X nor Y`. Comparison answers must attach the winner to the comparison
word (`lowest` / `cheaper` / `youngest`, or the inverse `more expensive` on a loser); a bare
report that names only the winner also passes, a list of candidates without a pick does not.

## Tests

```bash
cd agent_demo && uv run python -m unittest discover -s ../sites/adopt_a_pet/verify/tests -p 'test_*.py'
```

`tests/_support.py` builds synthetic snapshots from `ground_truth.py` and writes trajectories in
the `agent_demo/agent.py` shape; every verifier runs as a subprocess. Coverage per task: genuine
PASS, run-dir snapshot discovery, no-op, wrong task id, off-origin URL, corrupt PNG, missing
snapshots (fail closed), catalog drift (fail closed), shortcut (correct answer without the gate
pages), wrong answers / misattributed comparisons, read-only writes, and for stateful tasks the
state-mismatch, collateral-write, wrong-user, duplicate and reordered-workflow cases.

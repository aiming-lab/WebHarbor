# MEGA grading and seed contract

Tasks retain natural user wording. `verify_0.py` through `verify_17.py` delegate
to the deterministic `grade.py`; `answers.py` implements bounded English fact
checks. No verifier calls an LLM. A separately configured LLM judge remains an
optional secondary assessment, not a substitute for the deterministic result.

```bash
uv run --project agent_demo python agent_demo/eval_judge.py --run_dir RUN --verifier True
python -m unittest discover -s sites/mega/verify -p 'test*.py'
```

`RUN/initial.db` and `RUN/after.db` are the preferred snapshots. Explicit CLI
`--initial_db` / `--after_db` take precedence. If unavailable, the legacy Docker
fallback uses `WH_CONTAINER` (default `wh-review`) and `WH_SITE` (default `mega`).
A missing or malformed fixture fails closed. Record completed trajectories with
real before/after screenshots, page URLs and a final `done` step using the
`agent_demo` schema. `/cloud` and `/drive` are equivalent navigation paths.

Read tasks preserve every database table. Cart tasks require the requested
user's persisted `checkout_carts` row and the final checkout URL, as well as
required plan/filter visits; a historical checkout visit or an answer containing
“yearly” cannot substitute for the actual cart. Task 3 requires exactly one order
with the default saved payment method, correct plan/cycle/seats/prices, an empty
cart and the matching confirmation. Other mutations are restricted to the exact
requested rows and fields, preserving unrelated users and historical records.
Uploading a file may change its owner's storage usage by that file's size.

Answer grading accepts ordinary sentences, bullets, compact answers and supported
paraphrases. It binds versions to version statements and checks policy polarity,
comparison direction and the affected device. It is a bounded English parser,
not unrestricted semantic understanding. New legitimate formulations should be
added together with contradictory and near-miss controls. Task 0 accepts any two
of the three on-page access/management highlights, not only a fixed pair.

The unchanged source HF archive supplies the seed and images. Before running
locally, apply `python sites/mega/migrate_seed.py` and copy the migrated seed to
`instance/mega.db`. Docker performs that migration at build time. It adds the
cart table and nullable historical-order payment column, corrects the CMD
installer category, and updates the S4 tagline. It does not rewrite the archive
or fabricate payment methods for historical orders. Repeated migration and
populated startup are no-ops; resetting restores the migrated image seed.

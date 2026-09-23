# CarMax deterministic grading

Run from the repository root:

```bash
uv run --project agent_demo python agent_demo/eval_judge.py --run_dir /absolute/run --verifier True
```

Each run must contain `trajectory.json`, referenced screenshots under
`screenshots/`, and **both** `initial.db` and `after.db` SQLite snapshots. The
per-task CLI also accepts explicit `--initial_db` and `--after_db` paths.
Missing snapshots fail closed; a live preview/container is never consulted.
Take snapshots using SQLite backup after task actions have committed.

All 20 wrappers call the same offline implementation in `deterministic.py` and
`rules.py`. Neither network calls nor an API key are used. `--no_llm True/False`
is accepted for compatibility and never changes or skips grading conditions.
Run the secondary LLM judge separately, without `--verifier True`, when its
configuration is available. Current main's evaluator and agent propagate rubrics.

Navigation checks require same-origin, exact relevant paths and an existing
referenced screenshot. Search tasks additionally check their requested filters.
Saved state must have the exact authorized row delta: all other tables and prior
rows, including other users' data, must remain unchanged. The comparison must
persist all three vehicles in one comparison. Appraisals, bookings, registrations,
prequalification, saved-car removal and checkout have task-specific field checks.

Answers should clearly label facts and retain their units. Currency with `$` or
`dollars`, comma-separated or plain numbers, ISO and natural English dates, and
the exact or displayed rounded order total are supported. Grading checks
field/entity relationships instead of mere keyword overlap. This is a bounded
deterministic parser, not a general natural-language semantic proof; add a
positive and a negative regression when expanding accepted phrasing.

Task 3 uses the existing inventory under 60,000 miles; no catalog mileage was
invented. Tasks 13 and 16 remove misleading wording. Rubrics describe rules,
not secret answers. The mirror freezes benchmark business dates in May 2026.

Tasks 12, 16 and 19 now require account-specific, multi-page research:

- 12: Carol's saved appraisal plus both selling-policy FAQs.
- 16: Bob's existing financing result plus the named article and financing FAQ.
- 19: Dan's order plus all service-plan tiers, an upgrade calculation, and the
  warranty FAQ.

All three are read-only: logging in does not authorize a new application,
appraisal, purchase, or changes to existing records. Every requested source and
fact is required. The verifiers enforce those contracts, not a minimum click
count or a single prescribed click sequence. Previous one-page answers are no
longer complete answers to these revised tasks.

For tier comparisons, put each tier's price and months/miles limits together
(for example, one table row or sentence per tier). Keep the upgrade price,
months and miles together, naming both tiers. This preserves attribution in the
offline parser; arbitrary free-form prose remains the secondary judge's domain.

Run helper and route tests:

```bash
python3 -m unittest discover -s sites/carmax/verify/tests -v
```

Full browser runs and synthetic control copies are stored separately in the
review artifact directory. Synthetic controls are never counted as browser
completions, and a scripted regression is not an independent LLM-agent run.

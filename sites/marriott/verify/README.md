# Marriott — deterministic verifier contract (reviewer suite)

One deterministic verifier per benchmark task, plus a pytest suite that proves
the contract. Authored by the reviewer (review-env skill, Step 6/7); the ground
truth is **hardcoded inside the verifiers** and never appears in `tasks.jsonl`.

## Layout

```
sites/marriott/verify/
├── verify_lib.py          shared deterministic utilities (marriott-adapted from the
│                          hardened merriam_webster / jcpenney suites)
├── verify_0.py … verify_20.py   one verifier per tasks.jsonl row
├── append_rubrics.py      appends verifier_path + judge_rubric to tasks.jsonl
│                          (original five keys' bytes untouched, idempotent)
├── README.md              this file
└── tests/
    ├── _support.py        fixtures: seed acquisition, RunBuilder (agent-shaped
    │                          trajectories), sqlite mutation helpers, tiny PNGs
    └── test_verifiers.py  127 contract tests (honest / no-op / wrong answer /
                           shortcut / state-mismatch / wrong delta / tampering)
```

## Contract

1. **Package identity** — task_id match, `terminated` with `agent_done`, non-empty
   final answer, every recorded URL on the same loopback origin AND port as
   `start_url`, every referenced screenshot a decodable PNG.
2. **Navigation gates** (anti knowledge-shortcut) — the agent must have opened the
   on-site surfaces the task names: the destination search with its facets
   (`/search/findHotels.mi` with brand / max price / guest rating / amenity /
   sort / points-toggle / stay-window params), destination pages, hotel overview /
   rooms / reviews tabs, the availability search, reservation gateway +
   confirmation, reservation lookup + cancel, and the account surfaces. A correct
   answer with no matching navigation is a FAIL.
3. **Answer checks** — affirmative token / phrase / amount / count / date / time
   matching against frozen ground truth hardcoded per verifier. The runtime-random
   confirmation number must appear verbatim in the answer AND identify the added
   reservation row.
4. **DB after-state** — read-only tasks require every table row-identical;
   stateful tasks require exactly the allowed row delta (the right reservation row
   with the task's hotel / room / dates / guest / total, a status flip to
   `canceled`, a points debit, profile fields, payment-method swap, favorite
   swap, a registered user) and no collateral writes anywhere else.
5. **No LLM** — every verdict is fully deterministic; `--no_llm` exists for CLI
   parity with the sibling suites and changes nothing.

## Frozen seed contract (fail-closed)

`verify_lib.validate_snapshot_contract` refuses any snapshot pair that is not the
shipped seed: schema sha256 `718698ab…`, per-table row counts, the four benchmark
users, and a rows digest `b0cc7deb…` (instance md5 `9d60b205…`, byte-reproduced at
image build with `PYTHONHASHSEED=0`).

## Running

```bash
# one task's verifier against an agent run dir (trajectory.json + screenshots/
python3 sites/marriott/verify/verify_0.py --run_dir runs/0 \
        --initial_db runs/0/initial.db --after_db runs/0/after.db

# through the unified eval_judge entry point (locates the verifier via
# trajectory.verifier_path)
uv run python agent_demo/eval_judge.py --run_dir runs/0 --verifier True

# the contract test suite (fetches the seed from the review container once)
cd agent_demo && uv run python -m pytest ../sites/marriott/verify/tests -q
```

Output: JSON `{task_id, pass, reason, evidence[]}`; exit 0 on PASS, 1 on FAIL.

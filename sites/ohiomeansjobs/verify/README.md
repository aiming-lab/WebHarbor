# ohiomeansjobs verification contract

Run the primary deterministic grader from the repository root:

```bash
python agent_demo/eval_judge.py --run_dir /absolute/path/to/run --verifier True
```

Each task uses its `verify_N.py` entrypoint. Provide the actual trajectory,
referenced PNG screenshots, and consistent `initial.db` / `after.db` snapshots
inside the run directory. The primary result is binary JSON with check evidence.
No external model call is required. A separately configured LLM judge is secondary.

The current tasks pursue coherent goals. The verifiers check required page
visits, requested answer facts and precise state changes. They do not enforce an
arbitrary minimum action count. Task difficulty is reviewed through the UI,
including legitimate shortcuts; recorded action counts are not proven minima.

`verify_lib.py` validates trajectory identity, loopback origin and port,
completion, screenshot decoding and the versioned seed schema and row hashes.
The shared state audit preserves unrelated tables, other accounts and unchanged
columns/rows inside mutable tables. Stateful tasks permit only their declared
owner, additions, deletions and field edits. Revised tasks use
`refined_checks.py` where applicable. Ground truth remains in verifier code and
contract-test fixtures, never in the agent-facing task definitions.

The recorded URL and screenshot checks are evidence-consistency gates; they do
not cryptographically prove a browser interaction. Deterministic phrase and
regular-expression matching has finite paraphrase, entity-binding and
contradiction coverage. Do not interpret the tests as a general semantic
accuracy estimate. Password-change verification additionally checks the saved
hash and evidence of login with the new password.

## Tests

```bash
python -m pytest sites/ohiomeansjobs/tests sites/ohiomeansjobs/verify/tests -q
```

The contract suite uses explicit synthetic trajectories, tiny generated PNGs
and copied seed databases with SQL deltas in `contract_fixtures.json`.
Those fixtures are derived from reviewed UI outcomes but are not independent
browser attempts. Tests retain honest completion, empty/wrong answer,
homepage-only shortcut, missing state change, collateral write, identity,
offsite-origin, missing-image, incomplete-run and altered-seed controls.
Use an isolated runtime for application tests. The local seed is preferred over
any legacy container cache, and environment overrides remain available.

Seed content is frozen and reproducibly built from tracked source data. The
Ohio.gov seed also contains landing-page content; HTTP handlers do not read its
build-time JSON snapshot. All fresh builds must pass the repository asset
inventory, database and reset gates before integration.

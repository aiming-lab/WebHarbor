# Cookpad task verification

All 19 tasks use local browser navigation, natural answers and saved database
evidence. Tasks 9, 10, 12, 13, 15, 16 and 18 change state; other tasks must leave
the database unchanged. The initial snapshot must match the reviewed reset seed.

```bash
python -m unittest discover -s sites/cookpad/verify -v
python sites/cookpad/verify/verify_0.py --run_dir /path/to/run
uv run --project agent_demo python agent_demo/eval_judge.py --run_dir /path/to/run --verifier True
```

Each run folder needs trajectory.json, initial.db and after.db. Explicit
--initial_db / --after_db overrides are supported. There is NO fallback to a
mutable live container or regenerated fixture. --container is accepted only
for legacy CLI compatibility and is never read. Snapshot collection is the
runner/reviewer's responsibility.

Reviewer-only contracts.json and positive_answers.json are not agent-facing task
instructions. The latter contains synthetic regression controls, not claimed
independent browser discoveries. Expectations for facts come from the immutable
seed; tasks.jsonl contains no answer key. Reviewer rubrics identify checkpoints.

Checks include local-origin parsed paths/queries, relevant details and filters,
entity-bound times/authors/saves, unit conversions, missing-time handling and
contradictions covered by the controls. State checks compare all rows/schema,
allow only the requested list/note/meal changes, and preserve other users.

Natural-answer parsing is deliberately bounded, not general semantic judgment.
It supports full or documented distinctive short titles, sentences, bullets,
Markdown tables, minutes/hours (including compounds), g/kg, common number words
and source fraction notation. It is not a general pronoun resolver or multilingual
parser; unusual paraphrases may need reviewer examination. The secondary LLM
judge remains separate and should inspect visible evidence and contradictions.
State-only tasks do not require a fixed confirmation phrase.

The test suite covers all nineteen positive fixtures, prose/table/unit
equivalents, swapped/wrong/negated facts, foreign-origin and homepage-only
trajectories, no-op writes, wrong owners, collateral deletion and missing/tampered
snapshots. Synthetic controls are not a measured population-wide error rate.

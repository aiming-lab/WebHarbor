# Craigslist reviewed snapshot graders

Use the official primary entrypoint from the repository root:

```sh
uv run --project agent_demo python agent_demo/eval_judge.py --run_dir /path/to/run --verifier True
```

The run must contain `trajectory.json`, its referenced screenshots, `initial.db`
and `after.db`. Take SQLite backup snapshots of the isolated runtime before and
after the browser attempt. Missing snapshots fail closed. There is no live
container fallback and no LLM dependency. Optional `--initial_db` / `--after_db`
arguments are available when invoking a task verifier directly.

The initial snapshot must match the reviewed fixture logically. Every unrelated
table and every existing row is preserved; additions/removals are constrained by
account, listing, fields and direction. Merely visiting or claiming success does
not satisfy state-changing tasks. Demo accounts/mailbox messages are synthetic.

Read/comparison answers accept English paragraphs, bullets and table rows, common
model aliases, dollar notation and `dollars`, plus documented measurement/time
forms. Values are bound to entity spans and price clauses reject contradictory
amounts. This is bounded parsing, **not general semantic understanding**. Unusual
paraphrases, equivalent metric conversions and complex cross-sentence references
can still be false rejects. Keep the configured LLM judge separate as secondary
evidence; do not add a mandatory response format to task instructions.

Regression evidence and positive/negative controls are under the review output
directory, not benchmark answers in `tasks.jsonl`. Task IDs remain 0–19; prompts,
rubrics and expected state were revised together for the authentic September 18,
2026 source snapshot. Do not use the original PR #103 seed or HF PR #72 bundle
with these graders.

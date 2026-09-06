# Target — grading contract

One deterministic verifier per task in `sites/target/tasks.jsonl`, plus the
shared helpers in `verify_lib.py`. Each task row points here through
`verifier_path`; the matching `judge_rubric` in that row drives the LLM judge.

## Layout

```
verify_lib.py     shared utilities (trajectory, answer matching, SQLite state,
                  anchored LLM helpers, the Judge harness, CLI parsing)
verify_0.py …     one per task, ground truth HARDCODED inside
verify_17.py
```

Ground truth never lives in `tasks.jsonl` — the agent reads that file.

## Running one

```bash
cd agent_demo
uv run python ../sites/target/verify/verify_2.py \
    --run_dir runs/target2 \
    --initial_db <seed.db> --after_db <live.db> \
    --no_llm True          # deterministic-only; omit to include LLM checks
```

Or through the single evaluation entry point:

```bash
uv run python agent_demo/eval_judge.py --run_dir runs/target2 --verifier True
```

Output is `{task_id, pass, reason, evidence[]}` on stdout; exit 0 = PASS.
`--no_llm True` short-circuits every `llm_*` helper, so a deterministic-only
run makes zero API calls and needs no key.

## What the verifiers check

Deterministic first, in this order:

1. **Navigation** — the agent actually opened the page carrying the answer. A
   correct answer with no matching navigation is a knowledge shortcut and
   fails. This matters on a retail mirror: a model may know Red Baron pizza
   exists, but it cannot know THIS mirror's sodium rows or plan prices.
2. **Answer match** — numeric/token comparison against frozen ground truth.
   Money is compared below one cent, so $249.98 does not satisfy $249.99.
3. **Database after-state** — for stateful tasks, the cart/wish-list/order rows
   are diffed between the initial and after DBs. Claiming a cart addition that
   never landed fails on state alone, regardless of wording.
4. **LLM helpers** — only where exact matching is brittle, always anchored on
   the frozen ground truth, one call each, all skippable with `--no_llm`.

Read-only tasks additionally assert the DB was *not* mutated.

## Disambiguation tasks

`Target--14` and `Target--15` are deliberately under-specified (several
wish-list items; several Red Baron pizzas with different sodium). They pass
only when the agent asks which one is meant. `Target--14` also asserts nothing
was removed while waiting — silently guessing is visible in the database even
if the reply sounds cautious.

## Validation performed

- **No-op run** (homepage only, empty answer, clean DB): all 18 verifiers FAIL.
- **Shortcut** (right answer, no navigation): FAIL.
- **Wrong answer** (page visited, value wrong): FAIL.
- **Claimed-but-not-done** (cart wording says added, DB unchanged): FAIL.
- **Disambiguation guessed** (single value quoted, item deleted): FAIL.
- **Filter/sort skipped** (right product read off an unsorted listing): FAIL.
- Correct runs for each of the above: PASS.

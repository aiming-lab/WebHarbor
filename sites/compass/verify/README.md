# Compass verification

Each task has one `verify_N.py` entry point and a rubric in `../tasks.jsonl`. Task IDs 8 and 9 remain retired because their original generated agent-performance and unsupported schedule facts could not be grounded. The 19 current tasks use IDs 0–7 and 10–20.

All ground truth is derived from the supplied current `initial_db`. Ranking tasks recompute their complete eligible sets with exact integer ratios, require a unique result, and never trust a committed target ID. Tasks 18–20 derive the relevant tour, collection member, and account profile from the same snapshot. This removes answer-bearing `facts.json` from the agent-visible repository.

The verifier requires the exact 12-table `compass-source-v3` schema and seed marker. It compares canonical `sqlite_master` definitions and all rows before and after execution. Unknown, missing, added, or altered tables, indexes, triggers, and views fail. Each stateful task allows only its requested row-level transition and preserves every unrelated row.

```sh
python sites/compass/verify/verify_0.py \
  --run_dir /path/to/run \
  --initial_db /path/to/frozen-before.db \
  --after_db /path/to/frozen-after.db --no_llm
```

Output is JSON with `task_id`, `pass`, `reason`, and `evidence`; exit status is 0 for PASS and 1 for FAIL. `--no_llm` is accepted for harness compatibility; grading is deterministic. If DB paths are omitted, `--container` supplies the seed and live DB through `docker cp`.

The trajectory contract requires `task_id`, `start_url`, non-empty `steps`, `terminated`, `termination_reason`, and `final_answer`. Every step references basename-only before/after PNGs in `screenshots/`. Images are fully decoded and must be at least 320×200. All recorded navigation must remain on the run's loopback origin and port. Exact path/query checks enforce task-mentioned filters and page sequences; direct detail-page shortcuts do not satisfy ranking workflows.

Answer checks support conventional address abbreviations, grouped numbers, million notation, and natural English. Required assertions reject nearby negation. Multi-property comparisons bind each requested price, area, and year to its property line. Stateful references and share tokens are checked against rows created by that run.

Run the current regression suite from the repository root:

```sh
uv run --with pytest --with pillow python -m pytest sites/compass/verify -q
```

The suite executes every verifier through `grade()` against full current databases and covers positive outcomes, answer-only shortcuts, wrong task IDs, foreign origins, missing filters, negated claims, unrelated writes, schema changes, truncated screenshots, no-op stateful runs, and incomplete comparisons. These tests complement, but do not replace, real browser execution.

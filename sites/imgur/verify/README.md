# imgur deterministic verification

Run the primary grader through `agent_demo/eval_judge.py --run_dir /absolute/run --verifier True`.
Each trajectory must carry the current task wording, local origin, completed status,
valid screenshots and frozen initial/final database snapshots. No task is graded
by an action-count threshold. Read-only tasks preserve data; account tasks require
the exact requested owner, object and delta, with unrelated data preserved.

`reviewed_tasks.json` and `reviewed.py` define the revised comparisons and state
contracts. Remaining `verify_N.py` modules cover retained workflows. Ground truth
belongs here, not in `tasks.jsonl`. Natural-text checks accept ordinary prose,
bullets and monetary formats and bind claims to named entities, but are lexical
checks rather than a general semantic judge. Browser inspection and targeted
negative controls remain necessary. An optional LLM judgment is separate.

Review evidence and archived one-shot tools: `/data/pr186-187-review/`.
See the root `review-reports/` directory for the integration record.

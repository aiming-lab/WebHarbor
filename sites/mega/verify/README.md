# MEGA deterministic grading contract

Each row in `sites/mega/tasks.jsonl` points at `verify_0.py` … `verify_17.py`.
Wrappers share `verify_lib.py` (navigation, negation-aware answer match, SQLite
after-state, optional LLM anchors). Ground truth lives only in the verifiers.

```bash
python sites/mega/verify/verify_0.py --run_dir RUN --initial_db SEED.db --after_db LIVE.db --no_llm true
# or, with a running mirror container:
uv run python agent_demo/eval_judge.py --run_dir RUN --verifier True
```

Read-only tasks (0, 1, 9–11, 13, 15) require an unchanged database.
Stateful tasks check the exact row the task asked for (orders, cloud items,
vault entries, tickets, profile fields). Cart-only tasks (2, 4, 12, 17) require
checkout navigation and **no new subscription order**.

`python3 sites/mega/verify/test_verifiers.py` runs a no-op / pass / shortcut /
wrong-answer matrix without Docker or an API key.

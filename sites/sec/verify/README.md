# SEC deterministic grading

Run each task through `agent_demo/eval_judge.py --run_dir RUN --verifier True`.
`verify_0.py` through `verify_19.py` share `verify_lib.py`; these are the sole
primary contracts. Each run contains the task identity and exact wording,
terminated trajectory, local URLs, before/after PNGs under `screenshots/`,
`initial.db`, `after.db`, and a natural-language final answer.

The verifier checks the frozen build-generated seed (including page content),
relevant visited surfaces, factual answer claims, and exact state differences.
It ignores reused SQLite row IDs when comparing watchlist changes, but consumes
row matchers one to one to preserve multiplicity. Submission references in the
answer must match the newly saved records. Other users and unrelated tables
must remain unchanged. Screenshots establish package integrity; their pixels
are not automatically interpreted as proof of task completion.

Task refinement keeps a single user goal and removes unrelated lookups and
incidental catalog counts. The rulemaking task researches a proposal before
submitting a question about its applicability. Task length is evaluated through
browser review, never by enforcing a minimum action count in the grader.

Claim recognition is deterministic and finite, not general natural-language
understanding. Correct equivalent wording is tested, as are missing claims,
wrong values, rejected claims, missing navigation, fake references and incorrect
state changes. Reviewer ground truth belongs here, never in `tasks.jsonl`.

Run `python -m pytest sites/sec/verify/tests` for contract tests. Some historical
external-evidence cases skip unless `WH_SEC_EVIDENCE` is configured. Current
browser replays are graded independently through the official entrypoint.

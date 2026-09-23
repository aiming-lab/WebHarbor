# Instructure deterministic grading

All 30 tasks in `../tasks.jsonl` have a rubric and deterministic verifier.
The reviewer refines the prompt, rubric and verifier together. Answers remain
outside the agent-facing task file.

- `verify_lib.py` validates the current task wording and ID, completion, local
  origin, decodable screenshots, and SQLite schema/seed identity.
- `verify_0.py` through `verify_29.py` are the task entrypoints.
- `reviewed.py` and `reviewed_tasks.json` hold the revised factual requirements,
  including entity-scoped comparisons and navigation requirements. These lexical
  checks support tested paraphrases, not arbitrary semantic equivalence.
- Stateful tasks (18, 20–25 and 28) require the requested database delta and reject
  unrelated changes. Other tasks require unchanged database rows.
- `tests/` contains synthetic positive, partial-answer, wrong-answer, package,
  and database controls. These fixtures are grading tests, not browser completion
  evidence. The checkout seed is preferred; environment overrides are supported
  by `_support.py`.

Tasks pursue coherent user goals. Browser review recordings for this revision
use at least six meaningful actions per task, excluding initial navigation,
final answers and viewport diagnostics. Verifiers do not impose action counts:
a shorter correct solution must not fail merely because it is efficient.

Run from the repository with the agent_demo dependencies installed:

```bash
python agent_demo/agent.py --tasks_file sites/instructure/tasks.jsonl \
  --task_id "Instructure--0" --url http://localhost:40077/ --out_dir runs/0
python agent_demo/eval_judge.py --run_dir runs/0 --verifier True
python -m pytest sites/instructure/tests sites/instructure/verify/tests -q
```

The official deterministic grader is primary. The optional LLM judge is
secondary; it was not run for this scripted browser review.

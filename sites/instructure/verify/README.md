# Instructure deterministic grading

All 18 tasks in `../tasks.jsonl` have a rubric and a deterministic verifier.
The contributor defines the task goal; the reviewer refines the prompt, rubric
and verifier together. Answers remain outside the agent-facing task file.

- `verify_lib.py` validates the current task wording and ID, completion, local
  origin, decodable screenshots, and SQLite schema/seed identity.
- `verify_0.py` through `verify_17.py` are the task entrypoints.
- Every redesigned task is **stateful**: each one requires an exact database
  delta (a gated-download `demo_requests` row, a `contact_messages` row, saved
  resources add/remove, a webinar registration, a profile edit, a newsletter
  subscription and/or a newly registered user) and rejects every unrelated row
  change. Ground truth for the answer checks is **hardcoded** in each verifier
  (never in `tasks.jsonl`).
- Navigation gates (anti knowledge-shortcut): the agent MUST have opened the
  on-site surfaces the task names — hub listings with their exposed
  Product / Org Type / Topic filters, resource detail pages, the gated download
  chain (`/download` + `/download/sent`), the scored site search, the events
  board with its Event Type filter, the careers board, the leadership page, the
  newsroom with its Region filter, the press-release archive, the Canvas
  Support FAQ, the account surfaces and the demo / contact forms. A correct
  answer with no matching navigation is a memory-recall shortcut = FAIL.
- `tests/` contains synthetic positive, no-op, wrong-answer, shortcut,
  no-delta, wrong-delta, collateral-write and package-tamper controls (132
  tests). These fixtures are grading tests, not browser completion evidence.
  The checkout seed is preferred; environment overrides are supported by
  `_support.py`.

Tasks pursue coherent multi-domain goals (register → filter → download → save
→ verify, research → demo, FAQ → contact, curation, event registration, …).
Browser review recordings for this revision use at least fifteen honest steps
per task, counting every atomic UI action plus the final answer. Verifiers do
not impose action counts: a shorter correct solution must not fail merely
because it is efficient — the step counts are an honesty property of the task
design, measured in walkthroughs, not a grading input.

Run from the repository with the agent_demo dependencies installed:

```bash
python agent_demo/agent.py --tasks_file sites/instructure/tasks.jsonl \
  --task_id "Instructure--0" --url http://localhost:40077/ --out_dir runs/0
python agent_demo/eval_judge.py --run_dir runs/0 --verifier True
uv run --with pytest python -m pytest sites/instructure/tests sites/instructure/verify/tests -q
```

The official deterministic grader is primary. The optional LLM judge is
secondary; it was not run for this scripted browser review.

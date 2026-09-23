# League of Legends deterministic grading

All 18 tasks in `../tasks.jsonl` have a rubric and a deterministic verifier.
The depth redesign (2026-09-23 standard) rebuilt every task as a deep
functional chain (honest walkthrough ≥ 15 atomic actions per task): roster
filter/sort/search comparisons, champion ability/skin panels, cross-domain
site search with noise verification, patch-notes cross-referencing, news hub
curation, and account state chains (favorites add/remove, bookmark add/remove,
profile persistence, signup onboarding, multi-account isolation). Ground truth
lives only in the verifiers; answers never appear in the agent-facing task
file.

- `verify_lib.py` validates the current task wording and ID, completion, local
  origin, decodable screenshots, and SQLite schema/seed identity (frozen-seed
  hash gates), and exposes the exact-set favorites/bookmarks delta helpers and
  entity-scoped `near_any`/`contains_phrase_loose` matchers.
- `verify_0.py` through `verify_17.py` are the per-task entrypoints. Each
  hardcodes its frozen ground truth, gates the on-site navigation the task
  names (anti knowledge-shortcut), checks the answer deterministically, and
  pins the exact allowed database delta — read-only tasks require row-identical
  snapshots, stateful tasks the precise row additions/removals/profile edit
  and nothing else.
- Task 17 is the read-only aggregation baseline retained verbatim from the
  depth review KEEP (former task 20); every other task writes state and
  verifies it on-site.
- `tests/` contains synthetic honest-pass fixtures plus adversarial controls:
  no-op runs, wrong answers, homepage-only shortcuts, mutated read-only
  databases, state mismatches (no delta), wrong deltas, collateral writes and
  package tampering. These fixtures are grading tests, not browser completion
  evidence; the live honest walkthroughs live in the review evidence runs.
  The checkout seed is preferred; environment overrides are supported by
  `_support.py` (`LOL_TEST_SEED_DB`, `WH_CONTAINER`).

Run from the repository with the agent_demo dependencies installed:

```bash
python agent_demo/agent.py --tasks_file sites/league_of_legends/tasks.jsonl \
  --task_id "League of Legends--0" --url http://localhost:40078/ --out_dir runs/0
python agent_demo/eval_judge.py --run_dir runs/0 --verifier True
python -m pytest sites/league_of_legends/tests sites/league_of_legends/verify/tests -q
```

The official deterministic grader is primary. The optional LLM judge is
secondary; it was not run for this scripted browser review.

The cross-patch task (7) grounds the premise in the seeded patch data: exactly
Nasus and Poppy carry balance entries in both Patch 26.19 and Patch 26.16 (the
former 26.18 × 26.19 pairing has a single-champion intersection and was
retired). Signup task 11 pins the new user's summoner name ('HarborRookie'),
region (EUW), favorite (Milio) and bookmark (Patch 26.19 Notes) rows and
requires the sign-out/sign-in persistence loop; the account's own
username/email/password remain free choices with a password of at least eight
characters.

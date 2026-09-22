# YouTube and Weather deterministic grading

Each site has 20 tasks, each with `judge_rubric` and `verifier_path`. Run the primary grader through `agent_demo/eval_judge.py --run_dir <run> --verifier True`. Each verifier also accepts `--run_dir`, paired `--initial_db` / `--after_db`, and `--container` directly.

Store `initial.db`, `after.db`, `trajectory.json`, and the referenced PNGs under `screenshots/` in each run directory. Snapshots must represent the reviewed seed and the final state of one independent task. If neither snapshot exists, the verifier uses SQLite backup against the selected Docker container (default `WH_CONTAINER`, or `wh-review`). A partial snapshot pair is an infrastructure failure; it never silently falls back. The seed must match `verify/fixture.json` logically, so schema/data changes require a reviewed fixture update.

The task-specific contracts select expected records from the initial database and check exact state changes, owners, targets, counts, retained records, counters and preferences. Only task-authorized mutations and associated watch history are accepted. Contracts and fixture fingerprints live under `verify/`, outside agent-facing task definitions.

The trajectory must contain screenshot-backed same-mirror navigation, requested account login, task research/filter pages and a final confirmation page. Final responses use natural language: a nonempty completion confirmation is sufficient because these tasks request persisted outcomes rather than freeform factual answers. No action-count threshold is part of grading.

The checker validates PNG headers and recorded navigation metadata; it does not visually interpret screenshots or authenticate a trajectory against malicious fabrication. Independent browser inspection complements the deterministic state checks. Only localhost/loopback mirror URLs are accepted by this contract. The secondary LLM judge was not run.

PR #18 validation used 40 fresh scripted browser completions and 400 synthetic controls: two equivalent confirmations and eight negatives per task. Negatives cover unchanged state, wrong target, unrelated account changes, missing navigation evidence, wrong login, missing screenshots, altered initial fixtures and partial snapshot pairs. All 440 outcomes matched their predeclared expectations. The separate review report records evidence locations and limitations.

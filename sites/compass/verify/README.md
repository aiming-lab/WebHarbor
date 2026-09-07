# Compass verification

Each task has one `verify_N.py` entry point and a non-answer-bearing rubric in
`../tasks.jsonl`. `facts.json` contains the frozen, source-backed answers used
only by these graders. Task IDs 8 and 9 were retired because their original
agent-performance and open-house facts could not be supported by sources.

```sh
python sites/compass/verify/verify_0.py \
  --run_dir /path/to/run \
  --initial_db /path/to/frozen-before.db \
  --after_db /path/to/frozen-after.db --no_llm
```

Output is JSON with `task_id`, `pass`, `reason`, and `evidence`; exit status is
0 for PASS and 1 for FAIL. `--no_llm` is accepted for harness compatibility;
all checks are deterministic. If DB paths are omitted, `--container` (default
`wh-review`) supplies the seed and live DB through `docker cp`. Use explicit
frozen paths when scoring past runs, especially after a reset.

The native run contract is `trajectory.json`, with `task_id`, `start_url`,
`steps`, `terminated`, `termination_reason` (`agent_done` or `guided_done`),
and `final_answer`. Each step carries `url`, `action`, screenshot basenames
`screenshot_before`/`screenshot_after`, and optionally `url_after`.
Screenshots reside in `screenshots/`. Normal local host aliases are accepted
at the run's port; external domains, other ports, and paths embedded in query
strings cannot satisfy navigation checks. The recorder is trusted to record
the real UI. Screenshot packaging checks do not interpret their pixels or
replace independent execution review.

Checks bind comparison facts to the correct property and use exact DB state
differences for writes. Existing rows and unrelated tables must be preserved.
For collection tasks, saving the target homes on a legitimate path through
Saved Homes is allowed. No grader requires the reviewer's homepage route,
sort order, number of clicks, or browser viewport. Explicit task requirements
such as following an agent link or reopening a saved search are checked.

Natural English answers, ordinary address abbreviations, comma grouping,
million notation, and Markdown rows are supported. Each comparison home must
have its own line as requested by the task. Rejecting ambiguous or inconsistent
numeric claims is intentional; no hidden LLM call repairs an answer.

Run the synthetic regression suite with `python -m pytest
sites/compass/verify/test_verifiers.py`. These fixtures are not browser runs
and cannot establish that a task is solvable through the UI.

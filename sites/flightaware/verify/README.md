# FlightAware deterministic verification

## Reviewed task extensions and evidence checks

The reviewer continuation preserves every task ID and expands short requests with
related outcomes. `review_components.json` lists the required checks for each task;
`composed_grade.py` requires every component on the same recorded session. Answers
remain natural prose. Initial and final SQLite snapshots must be supplied together,
and initial table contents must match `reviewed_seed.json`. Image evidence is decoded
with Pillow; a PNG header alone is insufficient. Navigation must stay on the starting
origin, including its port. Synthetic controls are separate from browser evidence.

Run the primary grader from the repository root using
`python agent_demo/eval_judge.py --run_dir /path/to/run --verifier True`.
Task paths, screenshots and database outcomes are separate requirements. Grading
uses deterministic phrase and numeric checks, which are not a general semantic judge.
The optional LLM judge remains a separate secondary assessment.

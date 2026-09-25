# FlightAware deterministic verification

Each task has one coherent goal. `coherent_tasks.json` contains the revised
entity/decision checks and required evidence pages; `coherent_grade.py` checks
them. The remaining tasks keep their original domain checks. The former
concatenation map is empty: one task no longer requires unrelated task outcomes.
Task IDs and entrypoint paths remain stable.

Run the primary grader from the repository root:

```bash
python agent_demo/eval_judge.py --run_dir /absolute/path/to/run --verifier True
```

Supply `initial.db`, `after.db`, `trajectory.json` and referenced PNG screenshots.
Initial logical tables must match `reviewed_seed.json`. Evidence must record the
current task wording for a revised task, a completed run, observed navigation on
the starting origin including its port, decoded and distinct screenshot frames,
and the relevant entity in browser observations. Parameters requesting a URL
are not proof that the page loaded. Required pages are checked independently of
the final answer; an arbitrary action-count minimum is not imposed.

Read tasks must leave every table unchanged. Saved-job tasks check exact added
or removed rows and preserve other users and unrelated tables. A claim of success
without the requested state change fails. Natural prose and tables are supported;
ISO dates and common dollar notation are normalized. The deterministic grader
uses task-specific phrase and value checks, not unrestricted semantic inference.
A secondary LLM judge remains a separate assessment.

`test_coherent_tasks.py` exercises swapped values, wrong selections, origin checks
and unintended mutations. `test_review_regressions.py` retains the earlier
fixture and evidence integrity controls. Synthetic fixtures and adversarial
copies are grading controls, not new browser evidence.

`test_verifiers.py` runs the synthetic per-task contract matrix, including
`coherent_examples.json` for the revised read tasks. It needs the reviewed seed
but does not reset or mutate the preview database.

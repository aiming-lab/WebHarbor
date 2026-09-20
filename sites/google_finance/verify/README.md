# Google Finance task verifiers

These 20 deterministic verifiers require both the frozen answer and the
task-specific navigation recorded in `trajectory.json`. Task 19 additionally
compares the seed and live SQLite databases, so a self-reported portfolio
change cannot pass unless the requested portfolio and JPM lot were created.

Run the complete positive and negative test matrix from the repository root:

```bash
python3 -m unittest discover -s sites/google_finance/verify -p 'test_*.py' -v
```

Run one verifier directly:

```bash
python3 sites/google_finance/verify/verify_0.py --run_dir runs/google-finance-0
```

Or use the benchmark's unified grading entry point from `agent_demo/`:

```bash
uv run python eval_judge.py --run_dir runs/google-finance-0 --verifier True
```

For task 19, save `initial_state.db` and `after_state.db` in the run directory.
The standard evaluator uses those snapshots, even when `WH_CONTAINER` is set.
Both must be SQLite snapshots captured before/after the task (use SQLite backup
or capture while the site is stopped). The verifier preserves all prior rows
and accepts only the requested new portfolio and position. It opens snapshots
read-only. A partial snapshot pair fails instead of mixing saved and live state.

`--initial_db` and `--after_db` override the saved pair when both are supplied.
For immediate live-container grading only, explicitly set `--container NAME`
or `WH_CONTAINER`; the verifier copies seed/live DBs only when no saved snapshots
exist. Temporary copies are removed after grading. There is no implicit
`wh-review` container default.

Answer checks bind labelled values to properties/entities, normalize common
company aliases, dates and monetary scales, and reject conflicting values and
negative/reference claims. Natural sentences, bullets and simple labelled
Markdown tables are supported; no exact output template is required. This is a
conservative deterministic parser, not general natural-language entailment:
unbound or unsupported complex formulations fail and may need manual review.
The LLM judge remains a separate, secondary tool.

Navigation checks parse observed `url`/`url_after` against `start_url`, requiring
an exact route and the relevant parameters on that same page. These checks
validate recorded traces; they are not cryptographic proof of browser activity.
Answers and reference values live only in reviewer verifier code. Task-file
rubrics specify criteria without revealing the answers.

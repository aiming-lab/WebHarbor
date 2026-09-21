# IRS Refund Tracker grading

Run the official entrypoint from the repository root:

```bash
uv run --project agent_demo python agent_demo/eval_judge.py --run_dir /path/to/run --verifier True
```

Every run must contain `trajectory.json`, `initial.db`, and `after.db`. Snapshot
the runtime DB before and after the browser attempt with SQLite's backup API.
The grader opens these files read-only and never copies a mutable container DB.
Explicit `--initial_db` / `--after_db` overrides remain available on individual
`verify_N.py` wrappers. Missing/incomplete snapshots fail closed. Snapshots must
come from the actual run; the evaluator does not generate them retrospectively.

Each step records its actual `url` and observed `page_text`. `agent_demo/agent.py`
now saves the same DOM representation supplied to the browser agent. A Playwright
recorder can save `page.locator('body').inner_text()` before/after the action along
with its URL and screenshot. Older review recordings with `page_NNN.txt` sidecars
are also supported. Thoughts, self-reported final answers and action descriptions
are never used as observed page content. Like the benchmark trajectory itself,
this browser evidence is trusted recorder output, not an anti-tampering format.

The grader checks same-origin parsed routes, actual case/account/result content,
requested searches/filters, and precise database deltas. Manual entry of case
values is valid. Task 11 does not require opening the notice after reading the
linked code. Task 8 permits only David's city/contact changes. Other tasks permit
append-only search/lookup logs, preserving existing rows and all domain/user data.

Answers may use normal sentences, short answers, bullets or simple year/stage
tables. The parser checks aliases, comparison direction, explicit polarity and
amount units/association. It rejects conflicting claims instead of accepting a
bag of keywords. Supported examples and counterexamples live in the tests. It
is a bounded deterministic parser: arbitrary discourse inference, sarcasm,
implicit entity references beyond the documented year aliases and double
negation are not guaranteed. No secondary LLM judge is silently substituted.

Run focused tests:

```bash
python3 -m unittest discover -s sites/irs_refund/verify -p 'test_*.py' -v
python3 -m unittest discover -s sites/irs_refund/tests -p 'test_*.py' -v
```

# Petfinder verification contract

Each `verify_N.py` grades Petfinder--N and emits `{task_id, pass, reason, evidence}`,
exiting 0 for pass and 1 for failure. The official entry point is
`agent_demo/eval_judge.py --run_dir RUN --verifier True`.

A run contains `trajectory.json`, screenshots, and SQLite `initial.db` and
`after.db` snapshots. Explicit `--initial_db` and `--after_db` flags override the
snapshots. For legacy runs without snapshots, `--container` (or `WH_CONTAINER`)
selects the runtime from which seed/runtime databases are copied. Prefer frozen
snapshots for reproducible grading. Ground truth remains outside `tasks.jsonl`.

The verifiers independently check same-origin navigation, requested filters,
login inputs, answer facts, and persisted state. Read-only tasks compare every
application table. Preference, favorite and inquiry tasks permit exactly the
requested row delta, including preservation of other users' data.

Tasks 3, 4, 6 and 13 include additional research: compare Nori/Mochi fees;
compare the listing ages of Alice's favorites; distinguish home preparation
from first-appointment preparation using both guides; and combine Nori's
profile facts with rabbit housing guidance. Each added detail page is required,
as are entity-bound values and the comparison winner where requested. Task 6
accepts stage headings or repeated stage labels, with equivalent checklist
wording; attributing a checklist to the wrong stage fails. These tasks remain
read-only and reject any persisted changes. Action counts are review evidence,
not a minimum-step grading rule; efficient valid paths are accepted.

Task 14 resolves numeric click indices against the recorded pre-action DOM and
requires a successful transition from Milo's detail page to the account. The
standard recorder carries the same observed DOM/URLs as current main. Textual
Playwright button locators are also supported. A bare index, a different target,
a failed click, or unchanged database alone cannot establish a save attempt.
Older recordings lacking target evidence need replay rather than an assumed pass.

Answer checks accept ordinary sentences, bullets, simple labeled tables, decimal
US-dollar amounts, small number words, unique first names and documented English
synonyms. Numeric facts require the correct property and pet; contradictory
values and winners fail. Checklist variants must preserve every required concept.
No exact answer template or JSON output is required. These checks are a bounded
English parser, not general semantic understanding: novel paraphrases may require
new positive and negative controls. Navigation and exact state checks remain
required regardless of answer wording. No external LLM is invoked by a verifier.

Run application, asset, verifier and answer regression checks with:

```bash
python -m unittest discover -s sites/petfinder/verify -p 'test*.py' -v
```

Search preferences use a supported home city when location is omitted; an explicit
empty location means Anywhere. Pagination preserves that choice. Nearest sorting
uses city-centre distances, not shelter addresses; newest sorts by days listed.
The old Recently updated option has no timestamp source and is no longer offered;
a stored legacy value falls back to Newest pets first until the user saves again.

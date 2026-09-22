# AKC deterministic verification

The candidate has thirteen quality-reviewed tasks: nine read-only tasks and
four exact-state tasks. Each row in `tasks.jsonl` points to one `verify_N.py`
entry point. Verifiers use Python's standard library, Werkzeug password verification, and supplied run
artifacts; no model, network request, live application database, or old run is
consulted.

```bash
python3 sites/akc/verify/verify_0.py --run_dir /absolute/path/to/run
```

A run directory contains `trajectory.json`, `initial.db` (or `before.db`) and
`after.db`. The trajectory must use the current task ID and question, begin on
a local HTTP origin, stay on that origin, record browser steps, and include a
final answer. Alternative localhost ports, ordinary navigation routes, and
answer phrasing are accepted where they preserve the task contract.

Read-only tasks derive their answers from the initial snapshot, require the
stated listing/filter or comparison route and detail page, and reject every
business-table change. Stateful tasks require the named account or registration
values, corresponding local UI actions, and one exact database delta; no-op,
wrong-account, duplicate and collateral writes fail closed.

Synthetic regression tests cover positive evidence, knowledge shortcuts, wrong
answers, no-op state, wrong-account changes, and extra writes. They test verifier
logic only and do not count as browser task runs:

```bash
python3 -m unittest discover -s sites/akc/verify/tests -v
```


Answer checks bind quantities to units/properties, ratings to the named breed
and a five-point scale, and conclusions to the winning breed. Prose, labelled
lines, Markdown tables, number words from zero to twenty, lb/pound/kg weight
ranges, year/month lifespans, and common numeric or month-name dates are
supported. Already-established article/event titles need not be repeated.
Contradicted facts, wrong scales and unrelated reference numbers do not earn
credit. Password creation is checked against the actual stored hash.

This is a bounded deterministic parser, not general language understanding.
Unrecognized or ambiguous constructions fail closed. Navigation and exact DB
deltas remain independent requirements. No task question or answer format was
changed by these verifier repairs.

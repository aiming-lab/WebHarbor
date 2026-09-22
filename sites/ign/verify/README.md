# IGN grading contract

Run the primary grader through `agent_demo/eval_judge.py --run_dir <run> --verifier True`.
Each task verifier retains its task-specific checks and applies the shared hard
contract in `task_contract.py`. The shared contract is deterministic and cannot
be bypassed by an unavailable secondary model.

Supply `initial.db` and `after.db` inside the run directory, or explicit
`--initial_db` / `--after_db` arguments when invoking a verifier directly.
Recorded snapshots take precedence over the legacy container fallback. A missing,
unreadable or incomplete snapshot fails closed. Databases are opened read-only.

The hard contract verifies:

- Actual same-origin paths, required subject searches, section visits and the
  Reviews Tech genre filter; query strings containing an expected slug do not
  count as detail visits. Equivalent query wording is permitted.
- Complete saved values: folder, note, status, profile fields, alert keyword and
  posted comment; a negated comment or a wrong region suffix is insufficient.
- The precise before/after row changes for each task, preserving all unrelated
  users, content and saved state. Moving a saved item is not deleting it.
- Registration creates the requested identity and password, with valid initial
  evidence and an account-page finish.
- Read-only comparisons leave the database unchanged and assert the correct
  entity/property relationship without negating it or also choosing the other
  candidate.

Comparison answers may be natural prose, a named answer, bullets, or simple
entity/value tables. No JSON, exact sentence template, or output field names are
required. Covered equivalents include “Turtle Beach, not Corsair”, “Corsair does
not have the headset tag; Turtle Beach does”, and tables with Yes/No entries.
Deterministic interpretation is deliberately bounded: implicit references such
as “the first one”, double negation, or arbitrary unrelated commentary are not
claimed to be understood. Optional LLM utilities in the original verifiers can
reject explicit contradictions when configured; they never override a failed
hard check. Report secondary-judge results separately.

Run the tracked regression suite with:

```bash
python -m unittest discover -s sites/ign/tests -v
```

It covers prose/table equivalence, contradictory answers, exact navigation,
missing snapshots, precise removal, unrelated-row preservation, complete profile
and alert values, negated comments, and registration/password/end-page checks.
State tests generate the real tracked seed in an isolated temporary directory.
Synthetic SQL controls test grading only; they are not browser-completion evidence.

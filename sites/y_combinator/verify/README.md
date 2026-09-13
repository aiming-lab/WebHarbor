# Y Combinator verifiers

One deterministic verifier per accepted task, invoked through
`agent_demo/eval_judge.py --verifier True`. Ground truth lives here, never in
`tasks.jsonl`.

## Input contract

Each verifier grades a frozen run signature:

| Input | Source |
|---|---|
| `trajectory.json` | `<run_dir>/trajectory.json` — `task_id`, `start_url`, `steps[]`, `final_answer`, `terminated`, `termination_reason` |
| step screenshots | `<run_dir>/screenshots/<name>.png`, referenced by each step's `screenshot_before` / `screenshot_after` |
| initial state | `--initial_db`, otherwise `<run_dir>/initial_state/y_combinator.db` |
| after state | `--after_db`, otherwise `<run_dir>/after_state/y_combinator.db` |

```bash
python3 sites/y_combinator/verify/verify_9.py \
    --run_dir runs/yc-9 \
    --initial_db runs/yc-9/initial_state/y_combinator.db \
    --after_db  runs/yc-9/after_state/y_combinator.db
```

Prints `{task_id, pass, reason, evidence[]}` and exits 0 on PASS, 1 on FAIL.
The standard `eval_judge.py --verifier True` entry point passes only `--run_dir`,
so save both snapshots at the conventional paths above for frozen grading.
Explicit snapshot arguments take precedence. Missing snapshots return a
structured FAIL without inspecting Docker.

For an immediate live diagnostic only, `--container <name>` explicitly opts into
copying `instance_seed/y_combinator.db` and `instance/y_combinator.db` from that
container. This fallback is available only when neither snapshot directory nor
an explicit snapshot argument exists; partial frozen runs must fail rather than
mix their state with a later live database. Each copy has a 30-second timeout.

Run the snapshot-entry regression checks with:

```bash
python3 -m unittest discover -s sites/y_combinator/verify/tests -v
```

## How grading works

`verify_lib.expected(task, before)` **derives** each answer from the frozen
initial snapshot rather than hard-coding it, so a verifier fails loudly with
`valid_inputs` if it is graded against a seed the task was not written for.
Every extreme ("largest team", "most upvotes") is required to be unambiguous in
that snapshot, so a task cannot silently become unanswerable.

Four groups of checks run for every task:

- **package** — task identity, non-empty step list, every recorded URL on the
  run's own loopback origin, a non-empty final answer, a completed run, and a
  readable PNG for each referenced step screenshot.
- **state** — the table set is unchanged, every table the task is not allowed to
  touch is byte-identical, and for the three stateful tasks the expected row is
  present, bound to the right account and object, with nothing else disturbed.
- **navigation** — the pages that actually carry the answer were opened. Only
  pages the task requires are checked; no route, click count or ordering beyond
  the task's own wording is imposed.
- **answer** — the requested facts appear in the final answer, matched case- and
  punctuation-insensitively, with number grouping and million/thousand notation
  accepted. A fact that appears only inside a negation does not count.

Tasks 8, 9 and 10 are the stateful ones (library bookmark, launch upvote,
registration plus newsletter). Every other task must leave the database
byte-identical.

## Requirements

`Pillow` (screenshot validation) and, for task 10 only, `bcrypt` to confirm the
registered password. Both ship in the WebHarbor image.

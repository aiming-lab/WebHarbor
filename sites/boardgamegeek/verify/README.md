# BoardGameGeek grading contract

The 21 task IDs are stable. Run the deterministic primary grader through
`agent_demo/eval_judge.py --run_dir <run> --verifier True`, with independent
`initial.db` and `after.db` snapshots in the run directory. Task rubrics are
secondary LLM-judge instructions, not ground-truth answers.

## Expanded tasks

Tasks 0, 12 and 16 previously took five recorded steps in the PR #88 audit
(including two viewport checks). They now require candidate selection,
multiple game detail pages, facts associated with each candidate, and a final
weight comparison. Tasks 0 and 12 also require the Credits pages. There is
no minimum action count and no prescribed sequence among independent candidates.

Use one line per game as the tasks request, with labelled numeric fields
(`rank`, `weight`, or `position`, `min players`, `max players`) and a
`designers:` field where requested. End with `Heaviest: <game name>`.
Expectations are derived privately from the initial seed; displayed weights
are rounded to two decimals, and tied displayed maxima are accepted.

## Safety and evidence

Read tasks must leave logical database state unchanged. Stateful tasks check
exact row additions/deletions and preserve unrelated rows and fields, including
within tables touched by the requested operation. Only the target aggregates
and required timestamps may change. Matching an incidental number or merely
mentioning both games does not establish a measurement or comparison.

Trajectory URL/action checks validate recorded navigation; they do not prove
screenshots were authentic or that an independent agent discovered the answer.
Review browser evidence separately. Synthetic unit fixtures are grader controls,
not browser attempts. Regression tests:

```sh
python -m unittest discover -s sites/boardgamegeek/verify -v
```

Original mirror: @hqhq1025. Original completion/grading PR #88: @jackjin1997.
The local fix candidate preserves that contribution while integrating current
main, repairing grading/navigation/mobile defects and expanding the short tasks.

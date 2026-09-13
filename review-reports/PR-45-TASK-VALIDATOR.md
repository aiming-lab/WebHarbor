# PR #45 task-validator review

This reviewer-owned continuation preserves XuanRui LI's original contribution and commit
from [PR #45](https://github.com/aiming-lab/WebHarbor/pull/45), then brings it onto the
current WebHarbor task and grading contract.

## Scope and versions

- Original contributor commit: `6b2a41a600bd0e1b260c3c80494f2d50f2b1d2fa`
- Reviewed upstream base: `36004932bdf82afbe36dc14e00f66841eccf9946`
- Current-main integration: `de3e45631db5f053b5157b9b16b57ace90875113`
- Validator remediation: `142bae2c32c4f3fc8b1ceae51b1b63511b401f7d`
- Blind-reviewed head: `1a87f18f16ff83b6549a6a4e75cdb8e8ffca2cfe`

PR #45 is repository tooling, not a mirror contribution. It changes no site application,
seed database, route, UI, asset archive, or Hugging Face revision. Docker health/reset,
visual-fidelity, source-fidelity, browser-task, and HF checks are therefore not applicable;
they were not executed or represented as passing.

## Review findings and repairs

| Area | Original behavior | Reviewed behavior |
|---|---|---|
| Invalid ports and files | malformed ports raised `ValueError`; invalid UTF-8 raised | structured nonzero findings, without a validator crash |
| Empty or missing task sets | empty files and missing files for registered sites could pass a full scan | both are blocking errors |
| Site registries | missing, duplicate, or mismatched `SITES` registries could be ignored or downgraded to a warning | all are blocking errors; shell/Python comments no longer create phantom entries |
| Agent-facing schema | embedded answer/ground-truth keys were accepted | answer-like keys are blocking errors; unknown extension fields remain warnings and fail only in strict mode |
| Reviewer grading fields | half a verifier/rubric pair, missing/cross-site/traversing verifier paths, and verifier reuse were accepted | grading fields must form a non-empty pair; verifier files must exist under the same site's `verify/` directory and be one-per-task |
| Task identity | prefix matching accepted unrelated names and nonnumeric IDs | IDs must be exactly `<web_name>--<number>` and the site identity must match, including established acronyms such as Ohio State University / `osu` |
| Duplicate diagnostics | a duplicate inside one file was also mislabeled as cross-site duplication | same-file and true cross-file duplicates are reported separately |
| Heuristic false positives | substrings such as `todo` in “Mastodon” and the ordinary word “Secret” triggered warnings | markers use word boundaries; secret warnings require credential context such as “client secret” |
| Human output | warning-only files were printed as `[OK]`, including strict-mode failures | output distinguishes `[WARN]` and `[FAIL]` |

## Executed validation

The reviewed test suite contains 31 tests. It covers valid contributor rows, valid reviewer
rows, current acronym naming, normal/strict warning behavior, invalid JSON and encoding,
port failures, empty/missing files, site-registration drift, answer leakage, grading-pair
integrity, verifier containment/existence/uniqueness, task identity, and duplicate IDs.

Results on both available runtimes:

```text
Python 3.11.3: 31 tests passed
Python 3.12:   31 tests passed
```

The current repository corpus was executed in strict mode:

```text
Checked 24 site(s), 24 task file(s), 805 task(s)
Errors: 0  Warnings: 0
```

That corpus contains 643 legacy/basic five-field rows and 162 reviewed rows with the
optional `verifier_path` + `judge_rubric` pair. Focused strict scans also passed for a
legacy task file (`allrecipes`), an acronym site (`osu`), and a reviewed site (`compass`).

An 18-scenario executable contract matrix was also recorded at the remediation commit:
four legal inputs/alternate naming or wording paths, two warning-mode paths, eleven
negative schema/registry/grading cases, and the full current-corpus scan. All 18 matched
their predeclared outcomes and left their input trees byte-identical. These are guided
regression executions, not web-agent trajectories or an independent blind-review result.

Static checks:

```text
ruff check:        passed
ruff format check: passed
pyright:           0 errors, 0 warnings
git diff --check:  passed
```

## Independent blind review

A fresh Claude Code session reviewed a frozen, checksum-verified packet containing the
18 scenario requirements, inputs, recorded invocations/results, and before/after state.
Validator source, tests, expected-result oracles, prior conclusions, and PR discussion
were excluded from its first pass.

- Self-reported model: `claude-fable-5-1`
- Packet manifest SHA-256: `bce1317c4b1985a248a0e0d3e1d9c55634cd19e8631d4f8014cd7cf2c173cae9`
- Verdict artifact SHA-256: `f9a125c1f8b9e52eca09fb58ce6e406357dc50b96ca5eb437f0e6656ac22b239`
- Coverage: 18/18 scenarios reviewed; 18 PASS / 0 FAIL
- Public result: [PR #91 blind-review comment](https://github.com/aiming-lab/WebHarbor/pull/91#issuecomment-5614696822)

The blind reviewer did not re-execute the validator or inspect its implementation and
could not reconstruct the packet's aggregate tree-hash algorithm. Reconciliation
independently reproduced all 36 before/after tree hashes, matched all 18 recorded-result
hashes, and confirmed that every blind verdict agrees with the predeclared task contract.
The omitted implementation and CLI coverage is supplied by the committed 31-test suite,
fresh CLI runs, and static checks above rather than attributed to the blind review.

Non-blocking output notes remain: registry-set drift uses the broad message “site order
differs”; `task_count` counts nonblank JSONL entries even when one is malformed; and a
full scan lists an expected but missing registered-site file among checked targets. These
do not alter finding codes, severity, mutation guarantees, or process exit status.

## Reproduce

```bash
python3.12 -m py_compile scripts/validate_tasks.py scripts/test_validate_tasks.py
python3.12 scripts/test_validate_tasks.py
python3.12 scripts/validate_tasks.py --strict
python3.12 scripts/validate_tasks.py --site osu --strict
python3.12 scripts/validate_tasks.py --site compass --strict
python3.12 scripts/validate_tasks.py --tasks sites/allrecipes/tasks.jsonl --strict
python3.12 scripts/validate_tasks.py --json | python3.12 -m json.tool >/dev/null
ruff check scripts/validate_tasks.py scripts/test_validate_tasks.py
ruff format --check scripts/validate_tasks.py scripts/test_validate_tasks.py
pyright scripts/validate_tasks.py scripts/test_validate_tasks.py
git diff --check
```

## Evidence use and current status

- Engineering evidence: unit/static checks and the 18 guided contract executions above.
- Independent review: checksum-verified, oracle-free first pass, 18 PASS / 0 FAIL, followed
  by result/state/hash reconciliation against the task contracts.
- Public maintainer evidence: this report, the committed tests, and the reproduction commands.

The reviewed behavior and current corpus are ready for maintainer review. The report-only
commit after the blind-reviewed head does not change validator behavior or frozen inputs.
No Hugging Face action is applicable, and this review performs no GitHub merge.

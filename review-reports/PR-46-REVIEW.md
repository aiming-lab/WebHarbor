# Review of PR #46: site registry audit

Original contribution: [aiming-lab/WebHarbor#46](https://github.com/aiming-lab/WebHarbor/pull/46), authored by @Lxr-max / XuanRui LI.

## Scope and fixed versions

- Base: `f20b5ee8377ba31bcb825b4dfe30ad96c416e477`
- Original contribution: `6e5d77b0af6c2b7dfcd82039361df4228f2c3c65`
- Isolated-review fixed point: `80bd5817109563313d1ae30fac684a8b918599f7`
- Reconciled implementation commit: `839c74dc0dd1a2967552b9d6df991701c61aafe6`
- Assets pin is unchanged: `ad6f424f72cada9e6f5c09a58093d0ceeab9c52b`

This PR adds repository-level tooling only. It does not add or modify a mirror site, task set, deterministic task verifier, or Hugging Face asset.

## Baseline findings

The original seven unit tests passed, but the original implementation did not pass its own strict scan on current `main`: it reported the valid `osu` / `Ohio State University` name pair as a warning and exited 1.

Reproducible review fixtures also confirmed that the original implementation:

1. raised tracebacks for malformed task URL ports and missing repository files;
2. parsed shell comments as site names;
3. rejected valid Docker `EXPOSE .../tcp` syntax while accepting descending ranges;
4. rejected complete explicit `.assetpaths` entries unless wildcard entries also existed;
5. inferred invalid task/site relationships from brand names without a canonical mapping.

## Reviewer fixes

- Return structured findings instead of tracebacks for malformed task URLs, invalid UTF-8 task files, missing required files, and malformed registries.
- Parse shell arrays with comment-aware tokenization and ignore commented-out declarations.
- Support protocol-qualified and lowercase Docker `EXPOSE` instructions; reject descending and out-of-range ports.
- Accept either wildcard or complete per-site asset paths.
- Remove the unreliable brand-name/slug heuristic while retaining within-file `web_name` consistency checks.
- Document that pre-PR and CI use should pass `--strict`.
- Report runtime-like regular files as structured warnings instead of raising `NotADirectoryError`.
- Parse only top-level registry declarations, remove unreachable duplicate-generated-port logic, and make the task-port collision test assert the actual diagnostic.
- Add the strict registry audit to the canonical `AGENTS.md` pre-PR checklist.

## Isolated review reconciliation

The frozen candidate was independently reviewed at `80bd581`. The reviewer reproduced the four recorded verification commands and returned `CHANGES_REQUIRED` with one P2 and four P3 findings; the review declared no contamination.

- Accepted and fixed the P2 runtime-file crash, with a red-then-green JSON CLI regression.
- Accepted the P3 findings for top-level registry parsing, unreachable generated-port code / misleading test coverage, and the missing `AGENTS.md` checklist entry.
- Did not broaden `.assetpaths` to accept arbitrary recursive glob spellings. The checked-in file and the actual pack/extract scripts define three canonical managed roots; no repository consumer defines the proposed spellings as equivalent. Certifying them in the audit would accept an unverified asset configuration. Canonical wildcard entries and explicit per-site entries remain supported.

Affected tests and the full validation set were rerun after reconciliation. A direct regression check also confirmed that restricting Python assignments to module scope does not reject valid indented shell declarations.

## Validation

All commands below were run from this fixed candidate:

```bash
python3.12 -m py_compile scripts/audit_site_registry.py scripts/test_audit_site_registry.py
python3.12 -m unittest discover -s scripts -p 'test_audit_site_registry.py' -v
python3.12 scripts/audit_site_registry.py --strict
pyright scripts/audit_site_registry.py scripts/test_audit_site_registry.py
```

Results:

- 22/22 unit and adversarial tests passed.
- Current repository scan covered 26 site directories, 26 registered sites, 26 ports, 26 task files, and 843 tasks.
- Strict scan: 0 errors, 0 warnings, exit 0.
- Pyright: 0 errors, 0 warnings.
- Python byte-compilation: passed.

The negative fixtures cover missing registrations/directories, duplicate task ports, mismatched ports, malformed JSONL inputs, malformed registries, function-local lookalike declarations, runtime-like regular files, missing core files, invalid Docker ranges/ports, warning/strict exit behavior, and JSON error output. Legal alternatives cover explicit per-site asset paths, brand aliases, shell comments and indentation, and protocol-qualified Docker ports.

## Applicability and unexecuted checks

| Check | Result | Reason |
|---|---|---|
| Repository CLI and unit/adversarial tests | PASS | Results above |
| Site UI / original-site visual comparison | N/A | No mirror site changed |
| Browser task trajectories and before/after state | N/A | No benchmark task changed |
| Deterministic task verifier review | N/A | No task verifier changed |
| Hugging Face asset PR | N/A | Asset pin and asset files are unchanged |
| Full Docker image build/smoke | NOT RUN | Review host lacked safe rebuild headroom; no site or runtime path changed |

## Current status

The reconciled code and public evidence meet the repository-tooling review bar and are ready for maintainer review. Docker remains explicitly NOT RUN, and this report does not claim maintainer approval.

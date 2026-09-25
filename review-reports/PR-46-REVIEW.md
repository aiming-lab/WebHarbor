# Review of PR #46: site registry audit

Original contribution: [aiming-lab/WebHarbor#46](https://github.com/aiming-lab/WebHarbor/pull/46), authored by @Lxr-max / XuanRui LI.

## Scope and fixed versions

- Current upstream base: `b3275d75fdfcfea6ca142ddd59e20b7e4cb3d454`
- Pre-sync candidate (audit source and tests unchanged): `609f4cbb833b524f786bd5b610eaee0720d65106`
- Original review base: `f20b5ee8377ba31bcb825b4dfe30ad96c416e477`
- Original contribution: `6e5d77b0af6c2b7dfcd82039361df4228f2c3c65`
- Isolated-review fixed point: `80bd5817109563313d1ae30fac684a8b918599f7`
- Reconciled implementation commit: `839c74dc0dd1a2967552b9d6df991701c61aafe6`
- Assets pin inherited from current upstream: `d7b4e614ba7d5dbf59c6326e96d10c6ef304fac1`

Relative to current upstream, this PR adds repository-level tooling, tests, the canonical pre-PR checklist entry, and this report. It also removes two empty tracked `.gitkeep` files from CarMax runtime-only directories so the strict repository audit starts clean. It does not modify mirror behavior, task sets, deterministic task verifiers, or Hugging Face assets. The asset pin is identical to upstream; the original review used `ad6f424f72cada9e6f5c09a58093d0ceeab9c52b`.

## Baseline findings

The original seven unit tests passed, but the original implementation did not pass its own strict scan on the original review base `f20b5ee`: it reported the valid `osu` / `Ohio State University` name pair as a warning and exited 1.

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
- Inspect Git-tracked runtime artifacts without rejecting normal ignored local runtime state created by site execution.
- Parse only top-level registry declarations, remove unreachable duplicate-generated-port logic, and make the task-port collision test assert the actual diagnostic.
- Add the strict registry audit to the canonical `AGENTS.md` pre-PR checklist.
- Remove the two tracked CarMax runtime-directory placeholders caught by the strict scan.

## Isolated review reconciliation

The frozen candidate was independently reviewed at `80bd581`. The reviewer reproduced the four recorded verification commands and returned `CHANGES_REQUIRED` with one P2 and four P3 findings; the review declared no contamination.

- Accepted and fixed the P2 runtime-file crash, with a red-then-green JSON CLI regression.
- Accepted the P3 findings for top-level registry parsing, unreachable generated-port code / misleading test coverage, and the missing `AGENTS.md` checklist entry.
- Did not broaden `.assetpaths` to accept arbitrary recursive glob spellings. The checked-in file and the actual pack/extract scripts define three canonical managed roots; no repository consumer defines the proposed spellings as equivalent. Certifying them in the audit would accept an unverified asset configuration. Canonical wildcard entries and explicit per-site entries remain supported.

Affected tests and the full validation set were rerun after reconciliation. A direct regression check also confirmed that restricting Python assignments to module scope does not reject valid indented shell declarations.

## Upstream synchronization — 2026-09-25

Merged upstream `main` at `b3275d7`, preserving the original contribution and reviewer commits.
There were no text conflicts. Audit source and tests are unchanged from `609f4cb`;
only the inherited main tree and documentation change. The documented registry now
covers 94 sites, container ports `40000–40093` and host ports `41000–41093`.

Upstream `scripts/check_site_registry.py` remains enabled and unchanged. The supplemental
audit adds structured JSON diagnostics, per-site selection, asset-path coverage, and
tracked runtime-artifact checks. Both checks pass on the current corpus.
The historical isolated code review remains scoped to its original fixed point; no
new independent review is claimed. No asset archives were downloaded or modified.

## Validation

The following checks were rerun on 2026-09-25 after integration with `b3275d7`:

```bash
python3.12 -m py_compile scripts/audit_site_registry.py scripts/test_audit_site_registry.py
python3.12 -B -m unittest discover -s scripts -p 'test_audit_site_registry.py' -v
python3.12 -B scripts/audit_site_registry.py --strict
python3.12 -B scripts/check_site_registry.py
pyright scripts/audit_site_registry.py scripts/test_audit_site_registry.py
```

Results:

- 23/23 unit and adversarial tests passed.
- Current repository scan covered 94 site directories, 94 registered sites, 94 ports, 94 task files, and 2,315 tasks.
- Strict scan: 0 errors, 0 warnings, exit 0.
- Upstream registry check: all 94 sites, task URLs, and referenced verifier paths passed; Docker exposure is `8101 40000-40093`.
- Pyright: 0 errors, 0 warnings.
- Python byte-compilation: passed.
- Reviewer-delta whitespace/conflict checks: passed; only the audit, its tests, the pre-PR documentation, this report, and removal of two empty ignored runtime placeholders differ from current upstream.

The original 2026-09-13 validation covered 26 sites and 843 tasks. Those historical counts are superseded by the current integration results above.

The negative fixtures cover missing registrations/directories, duplicate task ports, mismatched ports, malformed JSONL inputs, malformed registries, function-local lookalike declarations, tracked runtime-like files, missing core files, invalid Docker ranges/ports, warning/strict exit behavior, and JSON error output. Legal alternatives cover ignored local runtime state, explicit per-site asset paths, brand aliases, shell comments and indentation, and protocol-qualified Docker ports.

## Applicability and unexecuted checks

| Check | Result | Reason |
|---|---|---|
| Repository CLI and unit/adversarial tests | PASS | Results above |
| Site UI / original-site visual comparison | N/A | No mirror site differs from current upstream |
| Browser task trajectories and before/after state | N/A | No benchmark task differs from current upstream |
| Deterministic task verifier review | N/A | No task verifier differs from current upstream |
| Hugging Face asset PR | N/A | Current upstream pin retained; no new asset contribution |
| Full Docker image build/smoke | NOT RUN | Not repeated for this repository-tooling update; Dockerfile, application/runtime code, site behavior, and assets are identical to current upstream |

## Current status

The synchronized candidate passes the repository-tooling checks and is ready for maintainer review. No fresh Docker build or runtime smoke is claimed because the added audit is not invoked by the image build or runtime and does not change application or site behavior. Final approval and merge remain with the maintainer.

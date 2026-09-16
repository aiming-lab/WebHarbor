# Review of PR #46: site registry audit

Original contribution: [aiming-lab/WebHarbor#46](https://github.com/aiming-lab/WebHarbor/pull/46), authored by @Lxr-max / XuanRui LI.

## Scope and fixed versions

- Current upstream base: `5d7a4e8c594028b845cbdcc180619e438c3a22ab`
- Integrated and tested implementation: `4610b5df689ef664d49d7ba56bc53d123de28261`
- Original review base: `f20b5ee8377ba31bcb825b4dfe30ad96c416e477`
- Original contribution: `6e5d77b0af6c2b7dfcd82039361df4228f2c3c65`
- Isolated-review fixed point: `80bd5817109563313d1ae30fac684a8b918599f7`
- Reconciled implementation commit: `839c74dc0dd1a2967552b9d6df991701c61aafe6`
- Assets pin inherited from current upstream: `fa1e8a5b9e8e5d0e42764cd658825f4dea088d8f`

Relative to current upstream, this PR adds repository-level tooling and documentation only. It does not add or modify a mirror site, task set, deterministic task verifier, or Hugging Face asset. The asset pin is identical to upstream; the original review used `ad6f424f72cada9e6f5c09a58093d0ceeab9c52b`.

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
- Parse only top-level registry declarations, remove unreachable duplicate-generated-port logic, and make the task-port collision test assert the actual diagnostic.
- Add the strict registry audit to the canonical `AGENTS.md` pre-PR checklist.

## Isolated review reconciliation

The frozen candidate was independently reviewed at `80bd581`. The reviewer reproduced the four recorded verification commands and returned `CHANGES_REQUIRED` with one P2 and four P3 findings; the review declared no contamination.

- Accepted and fixed the P2 runtime-file crash, with a red-then-green JSON CLI regression.
- Accepted the P3 findings for top-level registry parsing, unreachable generated-port code / misleading test coverage, and the missing `AGENTS.md` checklist entry.
- Did not broaden `.assetpaths` to accept arbitrary recursive glob spellings. The checked-in file and the actual pack/extract scripts define three canonical managed roots; no repository consumer defines the proposed spellings as equivalent. Certifying them in the audit would accept an unverified asset configuration. Canonical wildcard entries and explicit per-site entries remain supported.

Affected tests and the full validation set were rerun after reconciliation. A direct regression check also confirmed that restricting Python assignments to module scope does not reject valid indented shell declarations.

## Upstream synchronization — 2026-09-16

Merged upstream `main` at `5d7a4e8`, preserving the original contribution and reviewer commits. The only content conflict was in the `AGENTS.md` pre-PR checklist: the audit had shifted the step numbers while upstream expanded the HTTP sweep. The resolution keeps the audit step, consecutive numbering, and the current `41000–41030` host-port range.

Upstream now includes `scripts/check_site_registry.py`, called by `scripts/check_assets.sh` during the build. That check verifies exact task URLs and referenced verifier paths. It remains enabled and unchanged. The supplemental audit adds structured JSON diagnostics, per-site selection, asset-path coverage, and runtime-file checks; README now explains the relationship.

The audit implementation and its 22 tests are byte-for-byte unchanged from the previously reconciled PR head `472863e`. The historical isolated review therefore remains applicable to that code; no new independent review is claimed. Integration checks below were rerun against all 31 current sites. The upstream HF revision was confirmed reachable; no asset archives were downloaded or modified for this tooling update.

## Validation

All commands below were run on 2026-09-16 from the tree committed as `4610b5d`; the subsequent report update changes documentation only:

```bash
python3.12 -m py_compile scripts/audit_site_registry.py scripts/test_audit_site_registry.py
python3.12 -B -m unittest discover -s scripts -p 'test_audit_site_registry.py' -v
python3.12 -B scripts/audit_site_registry.py --strict
python3.12 -B scripts/check_site_registry.py
pyright scripts/audit_site_registry.py scripts/test_audit_site_registry.py
```

Results:

- 22/22 unit and adversarial tests passed.
- Current repository scan covered 31 site directories, 31 registered sites, 31 ports, 31 task files, and 945 tasks.
- Strict scan: 0 errors, 0 warnings, exit 0.
- Upstream registry check: all 31 sites, task URLs, and referenced verifier paths passed; Docker exposure is `8101 40000-40030`.
- Pyright: 0 errors, 0 warnings.
- Python byte-compilation: passed.
- Git whitespace/conflict checks: passed; only the audit, its tests, and documentation differ from current upstream.

The original 2026-09-13 validation covered 26 sites and 843 tasks. Those historical counts are superseded by the current integration results above.

The negative fixtures cover missing registrations/directories, duplicate task ports, mismatched ports, malformed JSONL inputs, malformed registries, function-local lookalike declarations, runtime-like regular files, missing core files, invalid Docker ranges/ports, warning/strict exit behavior, and JSON error output. Legal alternatives cover explicit per-site asset paths, brand aliases, shell comments and indentation, and protocol-qualified Docker ports.

## Applicability and unexecuted checks

| Check | Result | Reason |
|---|---|---|
| Repository CLI and unit/adversarial tests | PASS | Results above |
| Site UI / original-site visual comparison | N/A | No mirror site differs from current upstream |
| Browser task trajectories and before/after state | N/A | No benchmark task differs from current upstream |
| Deterministic task verifier review | N/A | No task verifier differs from current upstream |
| Hugging Face asset PR | N/A | Current upstream pin retained; no new asset contribution |
| Full Docker image build/smoke | NOT RUN | Not repeated for this tooling/documentation update; Dockerfile, runtime, sites, and assets are identical to current upstream |

## Current status

The synchronized candidate passes the repository-tooling checks and is ready for maintainer review. The original full Docker build was not run because the review host lacked safe rebuild headroom; this update does not claim a fresh Docker build or runtime smoke. Final approval and merge remain with the maintainer.

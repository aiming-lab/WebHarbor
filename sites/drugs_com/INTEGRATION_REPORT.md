# Drugs.com PR #71 — integration validation

## Candidate and preserved history

The integration branch preserves normal merge history: original PR **#9** (`588cbabf8da2018df6b0f53f95608c1d56156fe1`) → review PR **#71** (`48be0d76ca91b3295e74af71aede783f49c840d5`) → local reviewed fixes (`453ea84`) → current-main integration. Original site contribution: @boyugou; original review branch: @Django-Jiang. No squash or cherry-pick replacement of their history.

Runtime candidate: `835284bd2f71b01b203ad835cfd68d3caebf26bf` on `integrate/pr71-drugs`, based on main `8099846`. Worktree: `/home/qianhuiwu/projects/WebHarbor-integrate-pr71`. Drugs.com is appended at **40042**; the previous 42 site ports remain unchanged. Task URLs, verifier defaults, registries, Docker EXPOSE and docs agree.

This report records pre-merge validation. GitHub PR state and final merge commit are recorded separately in `MERGED.md` after independently verifying the remote result.

## Code and source changes

Thirteen explicitly attributed DailyMed product labels, 13 authentic packaging images, archived XML and provenance; 11 meaningful harder tasks with coordinated rubrics/verifiers; natural answers instead of compulsory JSON; responsive header/card/tab fixes; trusted-origin and immutable-snapshot grading. These are supplements, **not a complete Drugs.com restoration**. Remaining medication/interaction fixtures are unverified; news/reviews and pill diagrams remain explicitly simulated. Packaging is not a pill-identification photograph. No clinical correctness claim is made for those fixtures.

Main's complete site registry and all seed build/migration steps are retained. PR #71's shared hardening is integrated: hash-locked dependencies/base image, atomic asset installation and rollback, exact manifest verification, valid seed gates, supervisor PID identity, and authenticated control requests. Main's inventory pruning is preserved inside staging, with a regression test. Current startup requires `WEBSYN_CONTROL_TOKEN` (at least 32 characters); the token is not passed to site processes. This changes the old unauthenticated control-plane contract; docs include updated examples.

## HF integration — complete

- Original [HF #39](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/39) was already merged (`18e64e4d230794f990199f3327432d26db36866f`).
- [HF #101](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/101) uploaded the DailyMed supplement. The complete repository fetch exposed a missing `drugs_com/` archive prefix that the earlier standalone check missed.
- [HF #102](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/102) corrected the archive root using the repository standard packer. All 27 source-file bytes are unchanged. Both PRs remain in HF history; code pins **#102's merged revision**, not the defective intermediate archive.
- Immutable merged revision: `555a9aa0b02946a8bdf873ba1d59902b71564a07`.
- Final archive SHA-256: `8a9924e005d0a8a9f793f9e67bceeba0c4f2dbbe10ccf7f1afeb0a0198427b1b`.
- All **42 previous effective site pins** were compared against HF metadata and verified byte-identical. The global pin safely consolidates the previous scoped pins. `assets-manifest.json` binds all 43 selected archives and the extracted tree.
- Candidate and merged archives were downloaded and hash-checked independently. Fresh pinned CLI fetch/extraction and migrations succeeded in the isolated integration worktree. Only verified immutable archive objects were reused from cache; managed trees were freshly extracted. Byte-identical static media was later hardlinked to existing files to reduce disk use; mutable databases were not shared.

## Checks actually completed

- Standard `scripts/build.sh webharbor:pr71-integrated` / repository Dockerfile: PASS. This is a complete **43-site image**, not the earlier site-only overlay.
- Image ID: `sha256:ea401525d351900ed1a14253dbe2a7fd7ca29b7bf03528b3d7db312bb3a9c23d`. Local only; **not published or deployed**.
- 501 tests passed: 500 selected Drugs.com/Compass tests plus the separately run full-asset-tree test. The latter is no longer pending/deselected overall.
- Exact registry/ports, syntax and `git diff --check`: PASS.
- Full container: 43/43 healthy and all 43 homepages HTTP 200. Unauthenticated control requests rejected with 401. All 43 supervisor environments exclude the control token.
- Drugs.com login and normal saved-list form changed state; reset restored the exact canonical seed, then restart preserved it. Seed/runtime SHA-256: `01528a87f77b41b25e8e8b50409fdfb02aa75e1cd7aef6f4c4843082bb16a1aa`.
- `/reset-all`: all 43 sites ready; every homepage still 200. Drugs.com remains byte-identical.
- 21 **fresh scripted browser regressions** on the complete image, all officially graded PASS. 225 recorded steps = 153 browser actions + 51 scroll checks + 21 answer submissions. These are known-target regression paths, **not independent LLM-agent trials**.
- 57 preserved synthetic controls regraded using integrated code, all match expected outcomes. They are separate from browser completions.
- No secondary LLM judge ran; API/model configuration is absent. Bounded parsing is not general language understanding.

## Evidence and services

Evidence directory: `.assets/reviews/pr71-integration/` (local, not committed into the image). See `fetch.log`, `build.log`, `tests.xml`, `full-asset-test.xml`, `container-checks.json`, `controls-results.json`, `ledger.json`, `hf-merged.json`, `hf-existing-pins-unchanged.json` and per-task trajectories/GIFs.

Original and fixed previews/dashboard are preserved: current review site <http://localhost:44827/>, dashboard <http://localhost:43826/>; original audit <http://localhost:43825/>. The temporary integrated container `wh-pr71-integration-test` uses control port 45180 and sites 45100–45142 only during validation and is stopped after the checks. Publishing an image or replacing a deployed service was not requested.

Per-task integrated GIFs, trajectories and grading results are linked from the local [integration evidence report](http://localhost:43826/integration/REPORT.md). These local evidence files are intentionally not committed or shipped.

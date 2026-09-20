# Discogs integration: #34 → #109 → reviewed follow-up

Original contribution: @hqhq1025. Reviewer continuation: @jackjin1997.
The follow-up preserves their original commits and merge ancestry; no squash,
rebase, or force-push is used. The final runtime content was validated at
`073303c362cb0f4cbaa74c004f8494f74e157e2d`; this report is the only subsequent source change.

## Changes

Search and Marketplace pagination retain filters. Mobile Marketplace no longer
overflows, source note markup is escaped, and direct CLI startup avoids duplicate
imports. Tasks 4 and 6 now require two-release comparisons. Read-answer verifiers
check entity/property binding, natural-answer equivalents and contradictions;
state verification includes actual password checks. See `sites/discogs/FIX_REPORT.md`
for the completed review and limitations.

Discogs is appended at index 46 / port 40046. All prior 46 site ports and source
implementations are preserved. Registry, task URLs, Docker EXPOSE and active
documentation are aligned. The latest main README update is retained.

## Merged assets

Original [HF #24](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/24)
and reviewed [HF #76](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/76)
are both confirmed merged, in that order. The archive conflict was resolved on
#76 by retaining its exact reviewed Discogs bundle and current main's other files.
All 50 previously existing dataset files are byte-identical.

- Immutable merged revision: `ebe2e47a2ce53196ab8a4b18f22b56c7082b5004`.
- Archive SHA-256: `e42edef309a0fb44c2fda86d4e6f1472a3a84535013c700dabe629761e0be594`.
- Seed SHA-256: `391f3ec7ec9d98584538b1a91b2ff6da22bda13b2f09341df2d78625a1d2a435`.
- 3,506 validated archive members. All 47 registered archives were freshly fetched,
  validated, extracted and bound in `assets-manifest.json`.

## Verification actually run

- Python compilation, shell syntax, whitespace and 47-site registry checks pass.
- Discogs suite: **83 tests and 398 subtests passed**, with 889 existing warnings.
- Official deterministic evaluator: **15/15** preserved browser trajectories pass
  the integrated verifier. These are regrades, not new independent task attempts.
- Full `scripts/build.sh webharbor:pr109-integrated` succeeds; all 47 SQLite seeds
  pass the image's integrity gate. Image: `sha256:ae24e280114ca9a6933e3b357c260c43246dc1804dfb4487a4958cfef10c6cb5`.
- All **47 sites healthy**, all **47 homepages HTTP 200** on isolated host ports.
- Fresh Chromium checks: Search and Marketplace Next links reach pages 2 and 3;
  active query/sort parameters persist; both mobile pages have no document overflow.
- A real profile-location edit through the UI changes the Discogs database.
  Authenticated reset restores the exact seed bytes; restart preserves that identity.
- Owned runtime container is removed. Existing previews remain untouched.

Initial extraction hit root-disk exhaustion and rolled back. The successful fresh
extraction ran in `/data/wh-pr109-integration`. The default Docker bridge is missing
on this host; the successful build used host networking through an untracked shell
wrapper, and runtime checks used a dedicated bridge. Repository build code is
unchanged. The image is 5,709,825,365 bytes (above the inherited
4 GB target). No Docker Hub publication or deployment was performed.

Local evidence: `/data/wh-pr109-integration/.assets/integration-pr109/`.
The original review evidence and previews remain in their original worktrees.
Secondary LLM judging was not run; natural-language verifier coverage remains bounded.

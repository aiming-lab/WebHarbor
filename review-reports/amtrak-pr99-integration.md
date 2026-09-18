# Amtrak: PR #39 → PR #99 → reviewed fixes

Integration date: 2026-09-17. Original site contribution: @Lxr-max.
Review continuation: @JeremyJC67. Follow-up fixes are based on PR #99.

## History and scope

Regular merge commits preserve original PR #39 head
`ab903781556b72f6900c7be2d89c89cc46a6c0d9`, review PR #99 head
`677b87c007bcf7390a6dea51171033e75681bdf6`, and fix commit `a57ad6a`.
No squash, rebase, or force-push is used for this integration. The original and
review branches both remain ancestors even though the reviewer had previously
rebased/copied the contributor's commits.

Amtrak is appended at index 39, port **40039**. All existing 39 site ports and
site implementations are preserved, along with main's seed migrations and
asset pins. The integration is isolated from the user's running previews.

## Reviewed fixes

- Restore the homepage multi-city link and usable mobile booking/search layout.
- Update fare totals immediately and include checkout fees and room prices;
  preserve selected fares and reject invalid fare submissions.
- Strengthen ten short tasks (5, 6, 7, 9, 10, 11, 13, 14, 15, 16) with substantive
  comparisons, constraints and multi-page evidence, not click padding.
- Use natural instructions and responses for all 18 tasks; remove mandatory
  JSON schemas, internal field names and exact-policy-quotation requirements.
- Align rubrics, bounded natural-answer grading, immutable fixture checks and
  precise saved-state verification. Keep structured-answer backward compatibility.
- Record explicit before/after page text and post-action URLs while preserving
  main's existing pre-action `observed_text` and final-observation fields.

## Merged HF assets

[HF PR #96](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/96)
publishes the original contributor's unchanged `amtrak.tar.gz` into
`ChilleD/WebHarbor`, at merged commit
`6f432484307f76ca3c58b1d5c8f7b614dfb34f54`.
Incomplete draft #30 contained no Amtrak archive and was closed with a link
to the replacement. All 44 previously existing dataset files are unchanged.

- Archive: 308 validated managed members.
- Archive SHA-256: `22f0132a5f9bfee45a641e8172050a94bb4fc0de4ad45f1d9e52deb50eb37f34`.
- Seed SHA-256: `b245928c8b03741d17aa7c27f863a499e44034af607902cfa9c8d099c93591b4`.
- The scoped central pin and digest are tracked in `.assets-revision`.
- All 40 sites were freshly fetched and extracted in the isolated integration
  checkout; assets were not copied manually from the preview.

## Verification

- 11 asset-fetch tests pass, including preservation of existing scoped pins,
  explicit overrides, missing-archive behavior and digest rejection.
- 16 Amtrak unittest methods pass, including natural paraphrases, adversarial
  claims, package/fixture/state checks and explicit before/after URL pairing.
- The official evaluator regraded 182 preserved evidence packages: all matched
  expectations (18 prior browser recordings and 164 synthetic controls).
  These regrades are not new browser runs.
- Python compilation, shell syntax, whitespace and the 40-site registry pass.
- Combined Docker build succeeds: `webharbor:pr99-integrated`, image
  `sha256:978abcae6f8464b5f8ff31c5ee4138090b8f4cb7053a30c36ac60ef982843758`.
  All 40 sites are healthy and all 40 homepages return HTTP 200.
- Four fresh scripted Chromium regressions pass the official evaluator:
  task 3 (multi-city), 8 (saved profile), 16 (refund/fare comparison), and
  17 (completed Business booking). These are scripted checks, not LLM-agent runs.
- Reactive fare totals change from $69.11 to $88.53 for the tested selection.
  Mobile homepage has no horizontal overflow; booking panel width is 318 px
  at a 390 px viewport. Integrated homepage matches the reviewed preview.
- Actual profile mutation changes the runtime DB; reset and service restart
  both restore byte identity with the seed:
  `cb4b6a5939b663017d9774f2d3a86884` (MD5).
- Shipped Amtrak source hashes match the tested worktree; verifier code compiles
  under container Python 3.12. Runtime source candidate: `b6e9ff1`; this report
  is the only subsequent tracked addition.

Local integration evidence: `.assets/integration-pr99/` in the integration
worktree. Earlier task GIFs remain in the fix worktree at
`.assets/reviews/pr99-fix-20260917/natural-answers/`.
The existing dashboard is `http://localhost:43815/natural-answers/` and the
reviewed standalone preview is `http://localhost:44815/` (forward both ports
when accessing the remote workspace). They are not deployed release URLs.

## Limits

The mirror uses synthetic schedules, fares and generated artwork, not live
Amtrak data or a faithful copy of every upstream page. The natural-answer parser
has bounded coverage, not unrestricted semantic understanding. No independent
LLM-agent run or secondary LLM-judge run is claimed. Docker Hub publication and
deployment are separate stages, not included in this source/assets merge.
The combined image is 5,342,471,387 bytes (5.34 GB), above the repository's 4 GB
target. Broad inherited image-size cleanup was not part of this integration.

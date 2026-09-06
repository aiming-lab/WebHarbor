# Review: TED (PR #65)

**Recommendation: REQUEST_CHANGES**

This draft reviews the remote PR head `065e39a4e1bf33e61902abdfb3e9d35f1e62428e`. The local review branch is ahead at `b8d3bc3c2c734dfb649e733fc50051271065b91`; those remediation commits and their evidence have **not** been pushed to GitHub, so they do not change the status of PR #65. The read-only remote metadata is recorded in [`remote-pr-check.txt`](../remote-pr-check.txt).

## Mechanical checks: PASS locally; remote-head rebuild unverified

- [x] The existing local review image passed control-plane health, all 17 site-port HTTP-200 checks, TED reset, and byte-identical `instance`/`instance_seed` MD5 checks. See [`full-env-smoke.txt`](../full-env-smoke.txt).
- [x] The local TED service was healthy (`/_health` reported 64 talks; `/` and `/talks` returned HTTP 200).
- [x] The pinned asset revision `597623a2f32898afa12e3bbeda15520f559aa7c7` is present in [`.assets-revision`](../.assets-revision) and its Hugging Face commit page returned HTTP 200. See [`hf-revision-check.txt`](../hf-revision-check.txt).
- [ ] A fresh source-image rebuild from the exact remote PR head was not established in this sandbox. The full smoke result above is for the local review image and must not be treated as a remote-head reproducibility result.

## Visual fidelity: PASS on the local review run

- [x] Playwright screenshots cover the homepage, search/listing, detail, auth/account, and responsive 1440/390/320px views.
- [x] No blocking placeholder-image, blank-page, navigation, or responsive-overflow issue was observed in the audited TED flows.
- [x] Evidence is retained per task in the local review archive; this public remediation branch includes only the safe aggregate reports and controls.

## Functional depth: PASS on the local remediation run

- [x] Search, topic/playlist, event, detail, login, registration, account update, save/note, remove, and comparison flows were exercised through the visible UI.
- [x] The local run produced 20/20 clean Luna trajectories and 20/20 deterministic verifier passes. See [`FINAL-BY-TASK.md`](FINAL-BY-TASK.md) and [`final-verifier-results.txt`](../final-verifier-results.txt).
- [x] The 20 homepage-only empty-answer controls all failed their verifiers (20/20, exit code 1). See [`noop-verifier-results-20.txt`](../noop-verifier-results-20.txt).

## Task quality: FAIL on the remote PR head

The remote PR contains 18 tasks and 18 verifiers, while the reviewed contract requires the complete 20-task suite. The original task set also leaves several quality and grading gaps:

- Tasks 1, 2, 5, 8, 9, and 14 do not consistently force a sufficiently broad visible search path. Several original queries are narrow or omit search entirely, creating first-result/shortcut risk and failing the distractor standard.
- Task 11 says TED2026 and under 10 minutes, but its remote verifier only checks a `/talks?` visit plus Maya Higa navigation; it does not bind the event and duration query parameters.
- Task 3's remote verifier accepts speaker-only tokens even though the task asks for a talk; the answer contract should require a qualifying talk title or an explicitly complete identification.
- Task 13's task, rubric, and verifier should be aligned on whether the required output is the complete talk identity or the speaker; the remote verifier currently accepts either token without making that contract explicit.
- Stateful tasks should consistently reject an empty final answer and require the visible navigation that establishes the requested action. The remote stateful verifiers for Tasks 1 and 4 lacked that final-answer gate; Task 16 lacked a real `/talks` listing requirement.
- Task 17's remote verifier checks only `November`; it does not require the `TEDNext 2025` event/year, so a month-only answer can pass.

These are benchmark-quality issues rather than cosmetic preferences: they permit under-navigation, incomplete answers, or a verifier pass without satisfying all task constraints.

## Grading contract authored in the local remediation branch

The local reviewer remediation now contains 20 one-to-one task verifiers and rubrics (`TED--0` through `TED--19`), with no `answer` key in `tasks.jsonl`. Ground truth remains in verifier code. The revised contract adds two filtered comparison tasks, broadens the visible search paths, binds exact filter parameters, tightens title/speaker/year checks, requires non-empty final answers, and preserves state-delta checks.

The local controls are:

- 20/20 clean Luna runs → deterministic verifier PASS;
- 20/20 homepage-only no-op runs → verifier FAIL;
- 20/20 primary trajectory/screenshot/DB audits → PASS;
- 20/20 sanitized blind Claude judge packets → PASS.

See [`VERIFIER-LOGIC-REVIEW.md`](../VERIFIER-LOGIC-REVIEW.md), [`MAIN-JUDGE-REVIEW.md`](MAIN-JUDGE-REVIEW.md), and [`INDEPENDENT-CLAUDE-RESULTS.md`](INDEPENDENT-CLAUDE-RESULTS.md). Raw screenshots, trajectories, and database snapshots remain in the local review archive and are intentionally not published.

## Required fixes before approval

1. Bring the PR to the complete 20-task contract by adding the two filtered comparison tasks and dedicated verifiers/rubrics.
2. Re-anchor the narrow/underspecified tasks on visible searches with at least six results, near misses, and multiple sub-categories; ensure no task is solvable by the first result alone.
3. Make every verifier enforce every task constraint: exact filter parameters for Task 11, complete talk identification for Task 3/13, TEDNext plus year for Task 17, visible listing navigation for Task 16, and non-empty final answers for stateful tasks.
4. Re-run the clean Luna, deterministic verifier, no-op, primary trajectory, and blind-judge gates from the updated PR head, then attach the resulting screenshots and logs.

## Local evidence and provenance

- Local remediation commits: `d5504eb`, `90303bb`, `fbba792`, `654e9f5`, `8d7fcab`, `c38b012`, `fa4a33d`, `b8d3bc3`.
- Local final matrix: [`FINAL-BY-TASK.md`](FINAL-BY-TASK.md).
- Verifier logic audit: [`VERIFIER-LOGIC-REVIEW.md`](../VERIFIER-LOGIC-REVIEW.md).
- Full environment smoke: [`full-env-smoke.txt`](../full-env-smoke.txt).
- This is a public remediation draft; no GitHub review comment has been posted.

<!-- Draft command; do not execute until explicitly requested:
gh pr review 65 --repo aiming-lab/WebHarbor --request-changes --body-file review-reports/PR-65-REVIEW-DRAFT.md
-->

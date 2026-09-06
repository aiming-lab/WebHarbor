## Summary

This draft pull request is the reviewer-authored remediation package for [WebHarbor PR #65](https://github.com/aiming-lab/WebHarbor/pull/65). It completes and hardens the TED task grading contract that was reviewed against the remote PR head `065e39a4e1bf33e61902abdfb3e9d35f1e62428e`.

The original PR remains unchanged. Its remote head contains 18 tasks and 18 verifiers; this draft adds the missing two high-difficulty comparison tasks and carries the fixes required by the Review Environment Skill. Maintainers can review this as a replacement/companion PR before deciding how to land the remediation.

## What changed

- Added `TED--18` and `TED--19`, two filtered, multi-page view-count comparison tasks with dedicated deterministic verifiers and judge rubrics.
- Re-anchored narrow tasks on visible TED searches with distractor results and explicit selection steps.
- Tightened verifier contracts for exact filters, required detail/listing navigation, title/speaker/year constraints, non-empty final answers, and state deltas.
- Kept all ground truth inside the reviewer-authored verifier code. `sites/ted/tasks.jsonl` has no `answer` key and contains only the permitted task and grading-contract fields.
- Retained raw Browser Use trajectories, screenshots, and before/after SQLite snapshots in the local review archive. They are intentionally excluded from this public PR because they contain session-sensitive artifacts; public-safe aggregate reports and controls are included below.

## Review outcome for PR #65

The correct status for the current remote PR head is **REQUEST_CHANGES** until equivalent changes are present on that PR. The remote head has the following blocking gaps:

1. It has 18 rather than the complete 20-task contract.
2. Several tasks omit a broad visible search path or use narrow queries, leaving first-result and distractor-quality risks.
3. Task 11's verifier does not bind the requested TED2026 and duration filters.
4. Task 3 accepts a speaker-only token for a talk-identification task.
5. Task 16 does not require visiting a real `/talks` listing.
6. Task 17 checks `November` without requiring the `TEDNext 2025` event/year.
7. Stateful verifiers do not consistently reject empty final answers.

## Validation

- 20/20 clean Luna Browser Use runs passed their deterministic verifiers.
- 20/20 homepage-only, empty-answer no-op controls failed their verifiers (exit code 1).
- 20/20 primary trajectory, screenshot, and database audits passed.
- 20/20 sanitized blind Claude judge packets passed.
- Full local environment smoke passed: control plane healthy, all 17 site ports returned HTTP 200, TED reset was ready, and instance/seed MD5s matched.
- The pinned Hugging Face asset revision `597623a2f32898afa12e3bbeda15520f559aa7c7` was checked directly and returned HTTP 200.

The full-environment smoke used the existing local `webharbor:ted-review` image. A fresh source rebuild of the exact remote PR head was not established because unrelated local asset locks affected the earlier build; CI should remain the final reproducibility check.

## Evidence

- [Final by-task matrix](review-reports/FINAL-BY-TASK.md)
- [Verifier logic review](VERIFIER-LOGIC-REVIEW.md)
- [Primary trajectory audit](review-reports/MAIN-JUDGE-REVIEW.md)
- [Independent blind Claude results](review-reports/INDEPENDENT-CLAUDE-RESULTS.md)
- [Full environment smoke](full-env-smoke.txt)
- [No-op verifier matrix](noop-verifier-results-20.txt)
- Raw per-task trajectories, screenshots, and SQLite snapshots remain in the local review archive and are available for maintainer inspection through an approved channel.
- [Remote PR metadata](remote-pr-check.txt)
- [Hugging Face revision check](hf-revision-check.txt)

## Review contract

Each task has one verifier under `sites/ted/verify/verify_<N>.py` and a corresponding `judge_rubric` in `sites/ted/tasks.jsonl`. The verifier is deterministic-first and checks navigation, visible task facts, final output, and SQLite state where applicable. The LLM judge is secondary; no-op failure and state-delta checks are retained as independent controls.

## Checklist

- [x] 20 tasks and 20 dedicated verifiers
- [x] No answer key in the agent-facing task rows
- [x] No-op controls fail all verifiers
- [x] Clean positive-control matrix passes all verifiers
- [x] Browser screenshots and operation logs retained in the local review archive
- [x] Public PR excludes session-sensitive raw artifacts
- [x] No remote branch was modified by the original PR review
- [ ] Maintainer review and merge decision pending

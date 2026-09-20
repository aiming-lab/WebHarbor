# Craigslist PR #103 integration

## Ancestry and scope

Original PR #5 → verifier PR #60 → review PR #103 → reviewed fix commit `2ae575e` are preserved with normal merge commits, not squashed/copied history. Shared conflicts keep main's existing 41 site registrations, asset tooling and build steps. Craigslist is appended at index 41 / port 40041 (42 sites total). All other sites' ports and source are unchanged.

## Required HF assets — merged before code

- Original HF PR #72: merged at `1f446289924c1a00ecf9fec153696ad52896d9f4`.
- Reviewed replacement HF PR #100: https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/100, merged at `60d24cc02061a7fdff15c0684441b1f5e73a33a8`.
- Archive SHA-256: `741ef266077cc56c082e5b7dd2df0e43ffa81f7a1c297bb55ac232aabe9e5f5d`; downloaded original/candidate/merged bytes independently verified. All unrelated dataset files preserved.
- Seed SHA-256: `d983cbf885a6c5d89207ee2cc37e133fe2d1015662ff3aa69a72c6933e3687b5`.
- 78 authentic posts, 512 distinct original photos, 586 image references; 16 posts genuinely have no photos. 608 managed photo/source files validated by the repository-wide inventory.
- `.assets-revision` pins the immutable merged Craigslist revision/hash; existing site pins remain unchanged. Full assets were freshly downloaded/extracted with the repository script in this integration worktree.

## Verified integration candidate

Runtime code tested: `74f804c27fa33dd28546af8597e26f06faaa1f87`; the subsequent report-only commit does not change the tested image.

- Syntax, diff whitespace, 42-site registry and all asset inventory gates pass.
- Full image `webharbor:pr103-integrated` builds: `sha256:3bbe5cc5ffa99b7a9d9ca1483bcae2acb72e13642f4293cbdca6ecf94a754e10`.
- 42/42 services healthy; 42/42 homepage HTTP 200.
- Craigslist reset and restart retain runtime/seed byte identity.
- Seven isolated route test cases pass (including every listing GET, auth/CSRF, search, ownership, posting and local replies).
- 20/20 original corrected browser trajectories regraded through the integrated official evaluator; these are reused evidence, not new browser attempts.
- 184/184 targeted synthetic controls meet their declared expected results.
- Five additional known-target browser regressions against the integrated 42-site container (tasks 0, 5, 6, 7, 16): save comparison, saved search/reopen, posting, inbox/reply, and persistent hide. All complete and pass official grading with fresh reset state per task.
- Original full review: 20/20 scripted browser completions, 20 GIFs, 236 steps = 206 actions + 30 viewport checks. Original and fixed previews/dashboard preserved.

## Limits

No secondary LLM judge configured; no independent LLM agent trial claimed. Natural-answer verifiers cover bounded English phrasing, not arbitrary semantic equivalence. Source claims/availability are historical. Docker image publication and deployment were not requested and have not been performed.

Detailed local evidence: `.assets/reviews/pr103-integration/` in the integration worktree. Fixed-review dashboard remains http://localhost:43824/ and preview http://localhost:44824/ (local preview port is separate from integrated port 40041).

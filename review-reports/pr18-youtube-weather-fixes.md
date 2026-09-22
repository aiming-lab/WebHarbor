# PR #18 — YouTube and Weather fixes

Fix branch: `fix/pr18-youtube-weather`, worktree `/data/WebHarbor-fix-pr18`. The original contribution ancestry is preserved; current main was merged before the fixes. Original audit evidence remains at `/data/pr18-review-evidence`.

## Changes

- YouTube search no longer returns unrelated trending videos for nonsense searches. Missing avatar uses initials; misleading channel banners were removed. Responsive layouts no longer overflow at 390 px.
- Weather search respects temperature preferences. Alerts have detail links, unavailable local radar is clearly labelled, and saved locations have a visible save control. Home location can be selected from saved cities and is rendered on the homepage. Unit values are validated; the current home cannot be removed accidentally.
- Both sites build deterministic seeds from tracked definitions and pinned media mappings. Password hashes, timestamps and SQLite schema creation order are stable. The build replaces legacy seed directories cleanly. Two independent rebuilds matched byte-for-byte.
- All 40 tasks now combine meaningful research/comparison and saved outcomes; original clarification-only and already-satisfied tasks were replaced. All tasks have natural-language rubrics and deterministic verifiers. No minimum-click or rigid answer-format grading is imposed.
- Existing 60 site port assignments are preserved; YouTube and Weather use 40060 and 40061. Both registries agree and README retains row-first groups of three.

## Verification

40/40 fresh scripted Playwright browser runs completed, with 646 task actions (9–24 per task) and 80 separate viewport checks. All 40 final desktop/mobile pages were visually inspected. These are guided UI executions, not independent LLM-agent attempts; observed action counts do not establish a theoretical shortest solution.

40 actual primary-grader passes plus 400 synthetic controls matched all 440 expected outcomes. Controls include 80 equivalent positive confirmations and 320 targeted negatives. The official `agent_demo.eval_judge` verifier entrypoint was used. No secondary LLM judge ran.

11 route regression tests passed (4 YouTube, 7 Weather). Changed GET responses were saved and compared under `http/`. Seed integrity, foreign keys, deterministic regeneration and registry/port consistency passed. The regression scope is the two affected sites; unrelated websites were not exhaustively browser-tested.

The combined 62-site image built successfully from freshly fetched merged assets. Both affected homepages returned HTTP 200; startup matched seed bytes; restart preserved deliberately dirtied diagnostic state; reset restored byte-identical seeds. All 62 sites were alive and ready. Docker builds required `--network=host` because the default bridge is unavailable. HTTP/reset checks ran inside an isolated container network namespace via `docker exec`; host-port publication remains unvalidated because of the existing daemon issue. The owned container was removed. Image: `sha256:2000b7352d450bdfc11514699995e946afa7473c00c9f6d6b58dc81fd6c04f88`. Results: `/data/pr18-fix-evidence/docker-merged-validation.json`.

## Merged assets

HF asset PR [#10](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/10) is merged. `.assets-revision` pins immutable revision `66a2d1b0d85b100a14959205aab4768171d3c9cc`. Remote verification confirmed all 63 pre-existing dataset files were preserved exactly and only the two unchanged YouTube/Weather archives were added. Archive SHA-256 values remain `986c51d2fe6c557b3b2c784c4bc198e53065af7da65946a99b782a90fde3b7db` (YouTube) and `ee5951f513eab958a66cbe43bb91290ec64aab19f0e9d818c05a0642833649d8` (Weather).

All 62 site archives were downloaded into a fresh isolated context from the merged revision, validated, extracted, and recorded in the refreshed `assets-manifest.json`. The full image was rebuilt against these assets. No archives were reformatted or republished. Prior local-candidate build evidence remains archived; the merged revision supersedes that unpublished validation pin. Code integration has not been requested or performed.

## Evidence

Full per-task report and recordings: `/data/pr18-fix-evidence/REPORT.md` and http://localhost:45033/. Earlier audit: `/data/pr18-review-evidence`. See [grading contract](pr18-grading-contract.md) for snapshot requirements and verifier boundaries.

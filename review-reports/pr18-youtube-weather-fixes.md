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

The combined 62-site Docker candidate built successfully. Docker-generated seeds matched the reviewed verifier fixtures logically (SQLite file hashes differ between host and container runtimes). Both affected homepages returned HTTP 200; startup matched seed bytes; restart preserved deliberately dirtied diagnostic state; reset restored byte-identical seeds. All 62 sites were alive and ready. Docker builds required `--network=host` because the default bridge is unavailable; the daemon also failed to activate requested host mappings. Container HTTP/reset requests therefore ran inside its network namespace via `docker exec`. Host-port publication was not validated. The owned test container and network were removed. Image: `sha256:80c48931dcb20d802c854acf47befa0e02e0de5cd34a44e5d11979c67b0ec690`. See [container results](docker-validation.json).

## Assets and remaining dependency

HF asset PR [#10](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/10) remains open pending explicit merge authorization. Source head: `738d19f1ea310fb5779d169787d8a6edf7e5f2de`; current tested merged dataset base: `f372a548b2b4189c42ad6d16abec0579daaa892a`. Both unchanged archives passed validation. An isolated merge-tree check preserved all 63 existing dataset files and added only the YouTube and Weather archives.

The combined Docker candidate uses an unpublished local HF merge commit `9fd1c1b7b1955edb6be6232f7d51ba728dd08a1d` solely as local build provenance. It is not a remote merged pin. The source worktree still pins the merged dataset base, which lacks these two archives; fresh standard asset fetch/build remains blocked on the asset merge. After approval, merge HF #10, pin its actual immutable merged revision, freshly fetch/validate assets, and rerun build/reset validation before code integration. No assets were reformatted or republished. No code PR, push or merge was performed in this fix turn.

## Evidence

Full per-task report and recordings: `/data/pr18-fix-evidence/REPORT.md` and http://localhost:45033/. Earlier audit: `/data/pr18-review-evidence`. See [grading contract](pr18-grading-contract.md) for snapshot requirements and verifier boundaries.

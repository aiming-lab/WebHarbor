# Imgur: review and fixes for PR #187

Reviewed September 23, 2026. Original [PR #187](https://github.com/aiming-lab/WebHarbor/pull/187); reviewer branch `review/pr187-fix`. Original contributions and reviewer continuations merge in ancestry order: #186, Google Shopping fixes, #187, Imgur fixes. Remote outcomes are recorded in the dashboard integration record after verification.

## Findings and fixes

- Added a usable reply editor and recursive reply rendering; reject invalid or cross-post reply parents. Follow/Favorite labels now reflect the current state.
- Corrected search labels, invalid pagination handling (400 instead of 500), and local login return handling.
- Fixed responsive award images, gallery votes, header/search layout, long comment usernames, and footer overflow. Current mobile diagnostics across all 30 paths have no overflow or broken images.
- Fixed generated-meme upload URLs, reuse of uploaded media, and invalid template handling. Meme grading verifies stored template/captions; comment grading preserves all unrelated post fields.
- Refined 18 tasks into coherent community, discovery, comparison, and account workflows; updated rubrics and verifiers. Bound answer facts to named entities and exact account/object state deltas, rejecting stale prompts and unrelated numeric references.
- Removed obsolete one-off harvesting/task-generation scripts, retained in the external evidence archive. The Wallpaper unavailable-image originates upstream and remains documented rather than replaced with invented artwork.

## Browser review and task quality

All 30 tasks were reviewed and replayed; 18 prompts were revised. Current recorded paths contain 6–19 meaningful task actions, excluding initial navigation, final answers, redundant same-URL Back actions, and viewport diagnostics. These observed counts are not a proof of the minimum possible solution length. Each revised task pursues one related user outcome; added work supplies evidence for a decision or completes that workflow.

All 30 final browser paths complete and pass the official deterministic entrypoint `agent_demo/eval_judge.py --verifier True`. Evidence is scripted visible-UI review with reference-informed answers grounded in visible page content, not autonomous-agent performance. The secondary LLM judge was not run. Lexical answer checks cover tested paraphrases and entity/value assignments but are not a general semantic judge. Baseline and unsuccessful intermediate attempts remain archived; final trajectories are authoritative. Imgur current mobile screenshots were refreshed after its last responsive CSS fixes and are separate diagnostics.

[GIF dashboard](http://localhost:45093/) (forward port 45093), [task ledger](http://localhost:45093/ledger.json), [grading controls](http://localhost:45093/grading-controls.json). Application preview: http://localhost:45092/ .

## Validation and HF integration

185 tests passed; subsequent reviewed-contract suite: 60 passed; focused multi-entity tests: 3 passed; media/route regressions: 7 passed. Across both sites, 533 synthetic answer/package/state controls matched their expected outcomes; these are separate from the 60 real browser replays. Controls include equivalent prose, absent/corrupt evidence, foreign origins, wrong owners/parents, forbidden state changes, swapped facts, numeric reference substitution, and multi-entity pooling.

HF asset [PR #119](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/119) is confirmed merged. Final immutable pin: `2dc78ec4a9833f47a598489acc4a5c070e708851`. Both unchanged archives were validated; all unrelated dataset files were preserved. A fresh full fetch validated all 77 sites. Google Shopping's 112 and Imgur's 5,733 inventoried asset files matched; Imgur's declared archive byte length was corrected to 660137103. Build-time tracked seed enrichment requires no replacement asset archive.

The complete 77-site image was built from combined candidate `0e331ada`. Runtime checks are scoped to these two sites: authenticated alive/ready health, homepage 200, byte-identical resets, dirty-state preservation on restart, and frozen verifier seed contracts. All 75 existing site ports remain stable; new ports are 40075 and 40076, with no overlap. Other sites were not started; aggregate health intentionally reports 503. The initial Docker bridge attempt failed due to the host's missing docker0 interface; the successful build and temporary runtime checks use host networking. No image publication or deployment was performed.

## Evidence and reproducibility

Evidence root: `/data/pr186-187-review`. Final runs: `final/<task ID>/`; original attempts: `baseline/`; intermediate attempts: `corrected/`. Source SHA-256 inventory: `tested-source-hashes.json`; assets: `hf-merged.json`, `base187-fresh-assets.log`; tests: `*-tests-*.log`; current graders: `regrade-final.log`; Docker: `docker-build-host.log`, `docker-results.json`; HTTP comparisons: `http-after.json`, `http-after/*.diff`; dashboard: `dashboard-checks.json`. Source hashes are checked again after merging; report-only commits do not change tested runtime content.

## Per-task results

| Task | Prompt | Actions | Browser | Primary verifier | Evidence |
|---|---|---:|---|---|---|
| Imgur--0 | Revised | 12 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-0) |
| Imgur--1 | Revised | 16 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-1) |
| Imgur--2 | Revised | 6 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-2) |
| Imgur--3 | Revised | 10 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-3) |
| Imgur--4 | Revised | 12 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-4) |
| Imgur--5 | Reviewed | 6 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-5) |
| Imgur--6 | Reviewed | 10 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-6) |
| Imgur--7 | Reviewed | 10 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-7) |
| Imgur--8 | Reviewed | 9 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-8) |
| Imgur--9 | Reviewed | 8 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-9) |
| Imgur--10 | Reviewed | 9 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-10) |
| Imgur--11 | Revised | 13 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-11) |
| Imgur--12 | Revised | 15 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-12) |
| Imgur--13 | Reviewed | 8 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-13) |
| Imgur--14 | Revised | 7 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-14) |
| Imgur--15 | Revised | 11 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-15) |
| Imgur--16 | Revised | 10 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-16) |
| Imgur--17 | Revised | 8 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-17) |
| Imgur--18 | Reviewed | 9 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-18) |
| Imgur--19 | Reviewed | 9 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-19) |
| Imgur--20 | Reviewed | 13 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-20) |
| Imgur--21 | Reviewed | 12 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-21) |
| Imgur--22 | Revised | 6 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-22) |
| Imgur--23 | Revised | 12 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-23) |
| Imgur--24 | Revised | 9 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-24) |
| Imgur--25 | Revised | 13 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-25) |
| Imgur--26 | Revised | 8 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-26) |
| Imgur--27 | Reviewed | 6 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-27) |
| Imgur--28 | Revised | 10 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-28) |
| Imgur--29 | Revised | 19 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#imgur-29) |

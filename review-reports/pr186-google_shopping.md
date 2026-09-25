# Google Shopping: review and fixes for PR #186

Reviewed September 23, 2026. Original [PR #186](https://github.com/aiming-lab/WebHarbor/pull/186); reviewer branch `review/pr186-fix`. Original contributions and reviewer continuations merge in ancestry order: #186, Google Shopping fixes, #187, Imgur fixes. Remote outcomes are recorded in the dashboard integration record after verification.

## Findings and fixes

- Fixed obscured discount badges, accessible price submission, scrolling in the filter panel, and lost sort order on filter submission.
- Constrained login return URLs to local paths. Fresh application startup now creates the same canonical Alice saved list as the seed builder and leaves populated databases byte-identical.
- Added nine product-detail records grounded in Fashion Nova, Block Blue Light, and Edikted merchant pages, with source URLs and response hashes. These details support material, frame-shape, care, and price comparisons without inventing catalog facts.
- Refined 21 tasks into dependent shopping decisions, updating prompts, rubrics and graders together. Saved/price-track checks bind exact objects to account owners and reject collateral writes, while permitting SQLite row-ID reuse.
- Hardened answer checks against sibling-product fact pooling, swapped values, irrelevant reference numbers, and stale prompts. Removed obsolete one-off task-generation/walkthrough scripts (archived outside the repository).

## Browser review and task quality

All 30 tasks were reviewed and replayed; 21 prompts were revised. Current recorded paths contain 6–18 meaningful task actions, excluding initial navigation, final answers, redundant same-URL Back actions, and viewport diagnostics. These observed counts are not a proof of the minimum possible solution length. Each revised task pursues one related user outcome; added work supplies evidence for a decision or completes that workflow.

All 30 final browser paths complete and pass the official deterministic entrypoint `agent_demo/eval_judge.py --verifier True`. Evidence is scripted visible-UI review with reference-informed answers grounded in visible page content, not autonomous-agent performance. The secondary LLM judge was not run. Lexical answer checks cover tested paraphrases and entity/value assignments but are not a general semantic judge. Baseline and unsuccessful intermediate attempts remain archived; final trajectories are authoritative. Imgur current mobile screenshots were refreshed after its last responsive CSS fixes and are separate diagnostics.

[GIF dashboard](http://localhost:45093/) (forward port 45093), [task ledger](http://localhost:45093/ledger.json), [grading controls](http://localhost:45093/grading-controls.json). Application preview: http://localhost:45091/ .

## Validation and HF integration

129 tests passed; subsequent focused price/entity checks: 12 passed. Across both sites, 533 synthetic answer/package/state controls matched their expected outcomes; these are separate from the 60 real browser replays. Controls include equivalent prose, absent/corrupt evidence, foreign origins, wrong owners/parents, forbidden state changes, swapped facts, numeric reference substitution, and multi-entity pooling.

HF asset [PR #118](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/118) is confirmed merged. Final immutable pin: `2dc78ec4a9833f47a598489acc4a5c070e708851`. Both unchanged archives were validated; all unrelated dataset files were preserved. A fresh full fetch validated all 77 sites. Google Shopping's 112 and Imgur's 5,733 inventoried asset files matched; Imgur's declared archive byte length was corrected to 660137103. Build-time tracked seed enrichment requires no replacement asset archive.

The complete 77-site image was built from combined candidate `0e331ada`. Runtime checks are scoped to these two sites: authenticated alive/ready health, homepage 200, byte-identical resets, dirty-state preservation on restart, and frozen verifier seed contracts. All 75 existing site ports remain stable; new ports are 40075 and 40076, with no overlap. Other sites were not started; aggregate health intentionally reports 503. The initial Docker bridge attempt failed due to the host's missing docker0 interface; the successful build and temporary runtime checks use host networking. No image publication or deployment was performed.

## Evidence and reproducibility

Evidence root: `/data/pr186-187-review`. Final runs: `final/<task ID>/`; original attempts: `baseline/`; intermediate attempts: `corrected/`. Source SHA-256 inventory: `tested-source-hashes.json`; assets: `hf-merged.json`, `base187-fresh-assets.log`; tests: `*-tests-*.log`; current graders: `regrade-final.log`; Docker: `docker-build-host.log`, `docker-results.json`; HTTP comparisons: `http-after.json`, `http-after/*.diff`; dashboard: `dashboard-checks.json`. Source hashes are checked again after merging; report-only commits do not change tested runtime content.

## Per-task results

| Task | Prompt | Actions | Browser | Primary verifier | Evidence |
|---|---|---:|---|---|---|
| Google Shopping--0 | Revised | 8 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-0) |
| Google Shopping--1 | Revised | 7 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-1) |
| Google Shopping--2 | Revised | 11 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-2) |
| Google Shopping--3 | Revised | 8 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-3) |
| Google Shopping--4 | Revised | 7 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-4) |
| Google Shopping--5 | Revised | 8 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-5) |
| Google Shopping--6 | Reviewed | 7 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-6) |
| Google Shopping--7 | Revised | 11 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-7) |
| Google Shopping--8 | Revised | 11 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-8) |
| Google Shopping--9 | Revised | 14 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-9) |
| Google Shopping--10 | Revised | 12 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-10) |
| Google Shopping--11 | Revised | 14 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-11) |
| Google Shopping--12 | Revised | 8 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-12) |
| Google Shopping--13 | Revised | 9 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-13) |
| Google Shopping--14 | Revised | 16 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-14) |
| Google Shopping--15 | Revised | 7 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-15) |
| Google Shopping--16 | Revised | 18 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-16) |
| Google Shopping--17 | Revised | 11 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-17) |
| Google Shopping--18 | Revised | 13 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-18) |
| Google Shopping--19 | Revised | 17 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-19) |
| Google Shopping--20 | Reviewed | 6 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-20) |
| Google Shopping--21 | Reviewed | 10 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-21) |
| Google Shopping--22 | Reviewed | 10 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-22) |
| Google Shopping--23 | Revised | 13 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-23) |
| Google Shopping--24 | Reviewed | 18 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-24) |
| Google Shopping--25 | Reviewed | 10 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-25) |
| Google Shopping--26 | Reviewed | 8 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-26) |
| Google Shopping--27 | Revised | 9 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-27) |
| Google Shopping--28 | Reviewed | 10 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-28) |
| Google Shopping--29 | Reviewed | 14 | Complete | Pass | [GIF / trajectory / findings](http://localhost:45093/#google_shopping-29) |

# Completed integration: PRs 162–164

Reviewed and integrated on 2026-09-22. The original contribution is followed by its reviewer continuation for each site; all six GitHub PRs report MERGED.

| Site | Original PR | Fix PR | Original merge | Fix merge |
|---|---|---|---|---|
| Birkenstock | [#162](https://github.com/aiming-lab/WebHarbor/pull/162) | [#176](https://github.com/aiming-lab/WebHarbor/pull/176) | `f603d5104be9d939dfbea3f59c297bad8a83f3d8` | `9f5e43b0551acc9babab419dfd1161a0b5e25140` |
| America’s Health Rankings | [#163](https://github.com/aiming-lab/WebHarbor/pull/163) | [#177](https://github.com/aiming-lab/WebHarbor/pull/177) | `ba5276c632cf8bd2fc4e368aaece2b130d57b0da` | `a8c02acca679b1a66ce4f9a4a12a116ea41904bf` |
| American Express | [#164](https://github.com/aiming-lab/WebHarbor/pull/164) | [#178](https://github.com/aiming-lab/WebHarbor/pull/178) | `2a45a0ef969f379a6d0a72bf28e73383218a0cf1` | `d6c7f11b5da37e0ea3185f7706d2f2b0df74a6a2` |

All 95 tasks were reviewed in scripted Chromium paths before and after fixes. All 67 original paths with five or fewer observed actions were revised with corresponding rubrics and deterministic verifiers. Corrected paths use 6–19 observed actions; 95/95 pass the official verifier. There are 968 task actions and 190 separate viewport diagnostics. All 35 targeted grading controls have their expected outcomes.

Verifier tests: Birkenstock 38, America's Health Rankings 39, American Express 22. The health-rankings full suite initially had one failing honest-fixture matrix; after fixing the Senior rank key and rank-gap parsing, the complete 35-task positive matrix passed on rerun. The remaining 38 tests in that suite passed. Browser regrades and targeted controls are retained separately from synthetic fixtures. The secondary LLM judge was not run.

HF asset PRs [#105](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/105), [#108](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/108), and [#103](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/103) are independently confirmed merged. The unchanged bundles are pinned at `83e6966f504612a656a451e396fe4bf7897f6d68`; all pre-existing dataset files were preserved. Fresh fetching and 4,758 inventoried asset checks passed.

The combined image `webharbor:pr162-164-final` built successfully (`sha256:45c2031757e7cd5e7a20cb770140e369b9494481396468ffc3d17102c7a81009`). Its runtime source matches the reviewed files; subsequent README documentation clarifies the existing container fallback. Container checks were scoped to these three sites: authenticated alive/ready health, homepage 200, two byte-identical resets, dirty-state restart preservation, and seed-table fixture checks passed. All 68 seed databases passed the build's validation. The host lacks its default Docker bridge, so the build used host networking and runtime tests used an isolated network. The owned test container was removed.

Registry, README, Docker EXPOSE and task URLs agree. Existing 65 ports are preserved; Birkenstock, America's Health Rankings and American Express use 40065, 40066 and 40067. README retains three site/port pairs per row in row-first order. The final integration tree matches the tested candidate apart from review reports. No Docker image publication or deployment was performed.

[GIF dashboard](http://localhost:45054/) — forward port 45054 if needed. All 95 GIFs decode; all 67 revised GIFs were loaded in Chromium. Filters, unique task anchors, deep-link reveal, desktop/mobile layout and 380 task evidence links passed. The dashboard links full task questions, baseline/current counts, trajectories, answers, verdicts and mobile screenshots. These are scripted visible-UI reviews with reference-informed answers, not independent autonomous-agent performance or minimum action-count proofs.

Detailed reports: [Birkenstock](pr162-birkenstock.md), [America's Health Rankings](pr163-americas_health_rankings.md), [American Express](pr164-american_express.md). Evidence and validation logs: `/data/pr162-164-review`. Previews remain on ports 45051–45053; previous dashboards and previews were preserved.

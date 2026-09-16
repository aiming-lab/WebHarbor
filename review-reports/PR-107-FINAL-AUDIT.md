# PR #107 independent review and remediation audit

## Scope

The NVIDIA mirror (`sites/nvidia`, site 24 / container port 40023) was reviewed at PR head
`84bfe5846eb4b17a5594a073719f52b7bec81301` against base `129a274230070abb90b6d4ec209d81a911754ec9`. Phase 1 was a read-only
functional review of all 20 tasks at four viewports with a real browser, the site's own suites, the shipped verifiers and
the delivery path; its tables and raw evidence are retained outside the repository under
`/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr107-fixes/` (`issue-table.md`, `phase1-summary.md`). Phase 2 fixed
each finding in this branch with one local commit per issue and re-ran the whole validation set. No remote write was made:
the branch is local, `.assets-revision` points at a Hugging Face dataset revision that is still a draft PR, and the asset
archive replacement it needs is an HF-side write.

System dates during the work: 2026-09-12 (phase 1 and phase 2 on the same day). Repository base is unchanged; the PR's own
five commits are untouched and every remediation commit sits on top of `84bfe58`.

## Agent findings and dispositions

| Review area | Finding on the original head | Verification and disposition |
|---|---|---|
| Delivery path (assets) | The pinned revision `070123d74c01a8b29808201be85462fd7d0ec3c4` contains 26 entries and no `nvidia.tar.gz`, so the documented fetch cannot prepare this candidate. | Re-pinned to `fbf6b9f4f735116ae0e4194db2b160e9a4207fc1` (HF PR #75), the only candidate that carries an archive for every registered site; its 23 non-nvidia archives are byte-identical to the old pin, so no other site changes. The candidate from HF PR #38 was checked and rejected as a pin: it passes the validator but its seed is stale (Jetson kit/module identity text missing, RTX 5060 Ti named without `16GB`, `recommended_psu_watts` 550 contradicting the page's own 600 W note) and it covers 17 of 24 registered sites. `B1`/`4b60f0d`. |
| Delivery path (archive shape) | `nvidia.tar.gz` at that revision carries bare `nvidia/` and `nvidia/static/` members; `scripts/validate_asset_archive.py` raises `ValueError: unexpected managed path: 'nvidia/static'`, so `fetch_assets.sh nvidia` fails before extraction. | Re-packed with the canonical command from `scripts/extract_assets.sh`: the two bare members disappear, all 40 content members are byte-identical, and both artifacts (`987c6ed1…`, trimmed `c3f82009…`) pass the validator; validate → extract → site boot was run end to end. Replacing the HF file is a blocked write, recorded with the clearing condition. `B2`/`d132ce3`. |
| Grading contract | The 20 verifiers required `--initial_db/--after_db`, `run_dir/task.json` and `trajectory.query`, none of which `agent_demo/eval_judge.py --verifier True` or `agent_demo/agent.py` provide, so every task returned `INFRA_ERROR`. | The CLI now matches every other site verifier (`--run_dir` plus optional DBs with a `--container`/`$WH_CONTAINER` `docker cp` fallback, `--no_llm` accepted); `task.json` became an optional sidecar that is still compared when present; `query` and the recorder's `task` key are both accepted; the terminal page falls back to the last recorded step URL. Strictness kept: altered task/question, wrong task id and malformed JSON stay INFRA. `B3`/`87ef28f`. |
| Grading strength | A run with no screenshots, 1×1 screenshots or a hand-written single-step trajectory scored PASS: the verifier never looked at images. | Added a standard-library PNG validator (signature, per-chunk CRC, IHDR, zlib-decodable IDAT, scanline length) with a 320×200 minimum, an 8 MiB maximum and per-step binding when the trajectory names files. The four screenshot defects are now structured INFRA while the 20 real recorded runs keep passing. `H3`/`188d177`. |
| Negation handling | `strip_harmless_contrasts()` exempted "not a live release feed" style phrases for every task, so a qualifier-carrying T0 answer passed even though the PR's own regression test requires it to fail. | The exemption is now applied only through `driver_qualifier_scope` for T9/T10. All 14 driver cases still pass, T0/T2 qualifier answers fail closed, and the PR's driver suite is green. `H2`/`ef5eb15`. |
| Site test suites | `test_ui_contract.py` aborted with `FileNotFoundError` on the excluded `UI_REVIEW_NOTES.md`, and `tests/test_driver_qualifier.py::test_other_information_task_not_relaxed` failed. | The private note is hashed only when present (and `seed_data.py` no longer references it); the driver failure was a symptom of the negation-scope defect and is fixed with it. Current suites: 299 mechanical cases, 15 UI-contract tests, 11 CLI-contract tests, 29 driver tests, 23 parser regressions — all green. `H1`/`9dae360`, `H2`/`ef5eb15`. |
| Task quality | T15's rating select arrived pre-answered; T8's target was the first Studio card; T12/T13/T17 could be reversed by a duplicated submit; captions covered only 10 of 25 product images. | Rating now starts on an empty option and the review is not written without an explicit choice (`M11`/`a2f9a2b`); the catalogue and home featured strip order by name and a `Name` option is exposed (`L7`/`4f33ef1`); the wishlist save/remove endpoints are idempotent and the toggle is compatibility-only (`M8`/`cfe8556`); every product image carries a caption (`L6`/`c7f51d1`). |
| Application robustness | A committed session key allowed cookie forgery; GET/HEAD logout ended a session; `/drivers/999999999999999999999` returned 500 with no 500 handler; no body limit and a 400 KB email value was stored; `.field input:focus{outline:none}` removed the focus ring. | Environment-or-random secret key (`M4`/`6dc7cb4`); POST-only logout with a CSRF-protected form (`M5`/`85f183b`); `fetch_or_404` bounds integer ids plus `errorhandler(500)` and `templates/500.html` (`M3`/`85ca49c`); `MAX_CONTENT_LENGTH` and a 120-character email bound with a 413 handler (`M6`/`b3f71a6`). |
| Verifier robustness | Origin equality included the hostname, so mixing `localhost` and `127.0.0.1` on one port failed as off-origin. | Loopback spellings on one port are one origin; the port must stay constant, non-loopback hosts and boundary events still fail. The 401-case matrix is green and the mutation that restores exact equality is detected. `M9`/`822d565`. |
| UI, responsive behaviour, accessibility | Six text selectors measured 3.68:1 on white (2.03:1 for the rating glyph) and the focus ring 2.41:1; the primary navigation was collapsed behind a `Menu` disclosure at every width. | Role-based colour tokens: `--action` 5.48:1 on white and 5.11:1 on `#f7f7f7`, `--focus` ≥3:1 on light and dark surfaces, `--star` 5.05:1, brand green decorative only; a stylesheet-derived regression test plus pixel measurement (77 samples, 8/8 focus indicators). A shared include renders the navigation twice — disclosure below 881 px, visible bar above — with one landmark exposed. `M1/M2`/`443f9f6`, `M10`/`c02dce6`. |
| Documentation and disclosures | The PR description claimed 44 unit tests passing and a boot-banner fix; rubrics state graded numbers although the reviewer contract forbids it; external reference links were undocumented; the asset inventory manifest was missing. | Validation counts replaced with the reproducible commands (`L5`/`cdf7d6f`); the rubric deviation is recorded with its rationale and clearing condition, grading unchanged (`M7`/`3a784a0`); external-link scope documented (`L8`/`f067f65`); `asset_inventory.json` added and validated (`L3`/`89ab86f`); two dead checkout templates removed (`L1`/`3f8175d`); demo password hashes pinned so a regenerated seed is deterministic (`L4`/`0b50fae`). |

## Ground truth for the reviewed tasks

| Task | Ground truth | Derivation | Verified in phase 2 (built image) |
|---|---|---|---|
| `NVIDIA--0` | GeForce RTX 5090 memory: **32 GB GDDR7** | products.memory_gb / memory_type (slug geforce-rtx-5090); rendered on /products/geforce-rtx-5090 tech specs and in its description | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--1` | GeForce RTX 5080 CUDA cores: **10,752** | products.cuda_cores (geforce-rtx-5080); rendered on its detail tech specs | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--2` | GeForce RTX 4090 TDP: **450 W** | products.tdp_watts (geforce-rtx-4090); rendered on its detail tech specs | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--3` | cheapest RTX 50 Series card: **GeForce RTX 5060 at $299** | min(products.price_usd) over series="RTX 50 Series"; the 6 series prices are rendered on /geforce/graphics-cards/50-series/ | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--4` | Data Center GPU with 141 GB: **NVIDIA H200 Tensor Core GPU** | products.memory_gb=141 (h200-tensor-core), distinct from GH200 at 144 GB | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--5` | Jetson kit vs module: **Orin Nano Super: 8 GB, developer kit; Orin NX 16GB: 16 GB, production module** | products.memory_gb + description identity text for both slugs; the site offers a comparison link for the two | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--6` | RTX 5090 vs 4090 CUDA delta: **21,760 vs 16,384 = 5,376 more for the 5090** | products.cuda_cores for both slugs; the /compare tool renders both columns | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--7` | RTX 5080 vs 4080 SUPER bandwidth: **RTX 5080 higher (960 GB/s vs 736 GB/s)** | products.memory_bandwidth for both slugs; both detail pages and the comparison tool render them | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--8` | most memory in Studio / Professional: **RTX PRO 6000 Blackwell, 96 GB** | max(products.memory_gb) over category="Studio / Professional" (96 vs 48/32/20) | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--9` | latest RTX 50 Game Ready driver on Windows 11: **566.36** | max(drivers.released) over (product_series="GeForce RTX 50 Series", branch="Game Ready", os="Windows 11") | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--10` | RTX 40 Series Studio driver on Windows 11: **566.14** | drivers row (product_series="GeForce RTX 40 Series", branch="Studio", os="Windows 11") | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--11` | RTX 50 architecture generations + RTX 5080 buying info: **Blackwell, fifth-gen Tensor, fourth-gen RT; NVIDIA Marketplace / United States (en-us)** | /geforce/graphics-cards/50-series/ (static technology copy) plus /where-to-buy/geforce-rtx-5080 (destination and region recorded in the template) | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--12` | cheapest RTX 40 card saved to Alice wishlist: **GeForce RTX 4060 ($299)** | min(price_usd) over series="RTX 40 Series"; verified by the wishlist_items delta for user alice.j@test.com | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--13` | RTX 5070 Ti saved: **GeForce RTX 5070 Ti** | product slug geforce-rtx-5070-ti; verified by the wishlist delta | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--14` | profile country changed: **United States -> Germany** | users.country for alice.j@test.com before/after | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--15` | 5-star review titled Incredible: **reviews row (rating 5, title Incredible, non-empty body) for Alice + Jetson Orin Nano Super** | new reviews row bound to user_id 1 and the kit product id | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--16` | workstation GPU removed from wishlist: **RTX PRO 6000 Blackwell removed, both other entries kept** | wishlist_items delta: exactly one row removed (user 1, product 11) | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--17` | cheapest Gaming card with >=16 GB saved: **GeForce RTX 5060 Ti 16GB ($429)** | min(price_usd) over category="GeForce Gaming" with memory_gb>=16; verified by the wishlist delta | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--18` | Blackwell MLPerf Training 6.0 publication date: **June 16, 2026** | articles.published for slug blackwell-mlperf-training-6-0; the newsroom list shows the date | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |
| `NVIDIA--19` | newsletter subscription: **gamer42@example.com** | new newsletter row; verified by the newsletter delta | 4-width pure-flow run PASS + verifier exit 0 (see `fixes/D4_e2e.txt`); stateful tasks re-checked against the real after DB (`raw/final_db_deltas_1440.jsonl`) |

## Validation

- Phase-1 functional review: 20 tasks × 4 viewports = 80 scripted pure-flow runs with visible-element locators, 0 locator
  errors, verifier 80/80 PASS; 13 information tasks left the database byte-identical, 7 stateful tasks produced exactly the
  intended row deltas.
- Site suites after remediation: 299/299 mechanical verifier cases, 15/15 UI-contract tests, 11/11 CLI-contract tests,
  29/29 driver tests, 23/23 parser regressions, 52 tests (or 73 with the driver suite) under `unittest discover`.
- Verifier negative-sample matrix: 401 cases, 401 matching expectation, input files unchanged — including contradictory and
  negated answers, answer-only runs, forged/1×1/corrupt/missing screenshots, truncated trajectories, other-task identity and
  evidence, missing after-db, corrupt payloads, read-only tasks that mutated the database, mixed loopback spellings,
  alternate ports and off-origin navigation.
- Mutation verification: three injected verifier defects (accept any answer, skip the preserved-state check, restore exact
  origin equality) are each detected, with three controls unchanged; three injected site defects (re-add an unreferenced
  template, drop the caption fallback, restore price-desc featured ordering) and one injected pre-answer on the review form
  are each detected by the audits that were kept.
- Cold build: `./scripts/build.sh wh107-nvidia:cold` exit 0 (4.69 GB image, `/opt/WebSyn` 4.3 GB, no `instance/` or
  `scraped_data/` shipped). Container boot: 24/24 sites OK, `/health` 24/24 alive and ready, 24/24 site roots HTTP 200.
- Reset invariants: `POST /reset/nvidia` byte-identical MD5; `POST /reset-all` 24/24 ready in ~1.05 s with all 24 database
  files sha256-identical to `instance_seed`.
- End-to-end on the built image with a container-generated seed: 20 tasks × 4 viewports = 80 runs, 0 step errors, verifier
  80/80 PASS, 0 reset failures; stateful tasks graded against the real after-database.
- Four-width route crawl (114 routes × 1440/768/390/320 × anonymous and authenticated): 0 horizontal overflow, 0 broken
  images, 0 page errors, 0 failed requests, 0 external requests, 0 dangling ARIA references; console errors appear only on
  the deliberate 404 pages, the 403 order probe and the 405 logout probe. In-container scrolling regions
  (`overflow-x:auto`) were not counted as overflow.
- Answer-leak rescan: 32 anonymous form fields empty, 16 selects on their placeholder option, 4/4 selection listings with the
  target off the first position, 48/48 entry pages free of graded answers; the only remaining hit is the recorded rubric
  token deviation (M7).
- Contrast re-measured on the built image: stylesheet-derived audit 0 failures; 77 pixel samples with one sampler artefact
  disproven by a direct sample (comparison body cell 17.4:1); 8/8 focus indicators between 3.836:1 and 5.475:1.
- Repository state: `git status --porcelain` empty, `git diff --stat` empty; 25 remediation commits on top of the PR head.

## Evidence

- Phase-1 tables: `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr107-fixes/issue-table.md` (now with a remediation
  column), `phase1-summary.md`
- Per-issue reproduction, mutation and after-fix evidence: `_wh_review_tools/pr107-fixes/fixes/<ISSUE>/{repro,mutation,after}.txt`
  and `fixes/fix-status.md`
- Browser runs (trajectories, per-step JSON, screenshots, initial/after databases, verifier output):
  `_wh_review_tools/pr107-fixes/runs/` (final built-image set), plus `responsive/` and `responsive-auth/` crawls
- Build, health, reset and crawl receipts: `_wh_review_tools/pr107-fixes/build/`
- Verifier matrix and mutation results: `_wh_review_tools/pr107-fixes/verifier_matrix/`,
  `_wh_review_tools/pr107-fixes/mutation/`
- Accessibility measurements: `_wh_review_tools/pr107-fixes/a11y/final/`
- Asset artifacts and validator comparison: `_wh_review_tools/pr107-fixes/assets/`

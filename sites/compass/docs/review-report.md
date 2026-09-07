> **Homepage and navigation reconstruction:** see [the latest report](homepage-review.md). Application `9741284`, HF `e063074`; human acceptance and refreshed independent review pending. Earlier evidence below retains its recorded version.

# Compass contribution review

Reviewer takeover of [original PR #25](https://github.com/aiming-lab/WebHarbor/pull/25), contributed by **sarendis56 (Peichun Hua)**. The original commits remain in this branch. This Draft contains source/UI fixes and reviewer-authored grading contracts. Independent execution review is complete and reconciled; **human experience remains pending**, so it is not Ready for merge.

## Sell follow-up after human inspection

The missing Sell navigation/homepage entry and `/sell/` 404 are fixed in application checkpoint `a5e25af42b804bc56aeb49d5eb1c48c0a3a4b32c`. [Sell original / before / after comparisons and scope](sell-review.md) provide 12 matched captures plus 12 UI regression captures and [machine-readable validation](sell-validation.json). The new page uses local official assets and links to the existing agent directory; it does not implement the source seller lead form. This follow-up has fresh application/UI/reset checks, while the unchanged task evidence below retains its original identities. Claude has not reviewed this new page; human acceptance remains pending.

## Candidate and integration

- Current integration baseline: upstream `90afddb6d4af382935ded9a385f2eead604188cf` (Target added during validation).
- Baseline integration checkpoint: `3cdc0b66d72b8a789b89583176c668081de36852`; current Sell application checkpoint: `a5e25af42b804bc56aeb49d5eb1c48c0a3a4b32c`; **20 sites**, Target `40018`, Compass **`40019`**, control plane `8101`.
- [Companion HF PR #53](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/53), immutable current candidate `421ca6a529b88bdd214ecf6308d124798ab1e20b` (frozen task runs used `47232eba972567d138bbac478a6f4af9775a1d90`).
- Current Compass archive: 182,836,773 bytes; SHA-256 `2dce9cab8bb53cf27a100ca8e67b39743a7d8875384cc4993fb52b5e29460141`. The Sell image is the only change from the prior Compass archive; all 2,412 prior files, including the seed, remain byte-identical. The other 19 archives equal the current upstream asset pin. Only Compass content is new relative to current main.

The retained 16 complete UI runs were newly executed on **40019** after a host reboot removed the earlier temporary raw bundles. Their checkout was `b84eaf60bf02a30a45da643b62c92b343e70f426`, using the retained `3cdc0b6` image. The final parser-only verifier fix runs offline against the frozen snapshots; app/UI/data files were byte-identical at that reconciliation point. The later Sell application/UI delta is documented separately above. The standalone dependency list now includes `email-validator==2.2.0`, already installed by the Dockerfile. Historical summaries are retained as history, not substituted for missing originals.

## Environment and functional checks

The pre-Sell baseline passed 20/20 startup and homepage checks; reset-all takes 1.672 seconds and restores 23/23 files byte-for-byte. All 16 fresh task runs use 40019, with terminal state captured before reset. Full Docker build, all-site startup/HTTP sweep, and per-file reset results are in [environment-validation.json](environment-validation.json). The post-reboot 20-site sweep supersedes the earlier startup/reset checks; the existing image build is reused. The Compass runtime seed is `4fbb93f60edd007e3d2af660aec58fa4863672d96c6484e097c0eafb1d767979`; all 16 task resets restore it byte-for-byte.

The archive seed (`caa262ea5752016618c56e9bf01842257523cf8dae3ea25c57f719d61d7ce40f`) uses SQLite 3.53.1 encoding. Docker SQLite 3.40.1 rebuilds logically identical schema/rows with different bytes. Repeated rebuilds within Docker match exactly; reset compares the live DB with that runtime's seed, not a different platform's byte encoding.

**166 regression tests passed** in a fresh local environment (42 application/source cases and 124 verifier cases). They cover invalid registration, atomic preferences, malformed tour/inquiry input, CSRF, local redirects, object ownership, collection membership, saved-search round trips, rental formatting, exact price-per-area ordering, transaction identity and reproducible seeding. Real UI runs separately cover registration, login, profile edits, saved homes, tours, collections, saved searches and inquiries. Additional browser checks cover invalid credentials/required fields and saving/removing a home with reload persistence.

No forms contact external agents: writes remain in the local SQLite benchmark state. Synthetic fixture tests are separate from the recorded UI executions.

## Visual and source quality

[18 original/before/after screenshots](visual-review.md) cover home desktop/mobile, detail desktop/mobile, two-photo detail and the Miami list. They are unaltered browser captures with URLs, times, dimensions and hashes. Main repairs include official local fonts/hero, measured header and search proportions, cards, full/short galleries, share/photo dialogs, mobile property actions and narrow account tables.

[16 fresh supplementary layout checks](responsive-qa.json) cover home/list/filter/photo/share states at **390px**, detail/login/tour/account/profile/search/collection templates at **320px**, and home/list at **768px**. Actual screenshots are retained with hashes; no document-level overflow or broken visible images was observed. Long account tables scroll within their labeled region. Earlier broader QA remains historical because its temporary raw captures were lost. Keyboard activation of a wrapped collection link is used by the guided runner; this does not certify every pointer interaction.

Remaining differences are explicit: the list view omits the live map; the agent profile is a reduced source-backed contact/listings view; personalized recommendations, mortgage/property-history/school services and live communications are outside scope. Sell now has a local introduction page; the original seller form and full seller workflow remain omitted, as detailed in the follow-up. Official mobile Aspen photos failed to load during capture, so that source image supports layout only. These omissions are not presented as answer-leak safeguards. No human-approved visual regression baseline exists yet.

The 497 displayed listings retain original IDs and local galleries. Of 312 matching official transaction snapshots, 295 are displayed; **202 displayed records retain only contributor basic snapshots**. Unknown external facts stay absent instead of being generated. Source URL, retrieval time and HTML hash are in [source_data.json](../source_data.json); new image/font provenance is in `gallery_sources.json` and `visual_sources.json`.

All requested external answer facts were checked against matched source snapshots, separately from DB/verifier consistency. Task 7 uses contributor-only 3305 Dolphin Drive as an explicitly named collection member; it does not ask for unverified property facts. Its generated share token and account state are synthetic. Detailed facts are not added to search cards to reveal task answers.

## Task and grading audit

There are **16 candidate tasks**, IDs 0–7 and 10–17. IDs 8/9 were retired because generated agent sales volumes and unsupported open-house schedules could not be substantiated. Task 1 now uses the available one-bedroom-or-more Condo set; task 10 saves a three-bedroom Condo search with actual results. The original IDs remain stable.

The pool column is the unfiltered area's recorded catalog / qualifying set, independently checked against the seed. It is not the fully filtered UI count; after applying all filters, every displayed result should match. Natural pools range from 30–79 (Luxury 47), include multiple types and near misses. Named-object and account-write tasks use meaningful state changes/comparison instead of inventing distractors. Target position in a user-sorted result is not itself leakage: required detail facts and writes remain necessary. Task 13 provides the strongest comparison/disambiguation check; difficulty has not been calibrated with an independent model cohort.

| Task | Grouped UI steps incl. done | Natural pool / qualifying | Contract / quality check | Recorded execution | Verifier |
|---|---:|---|---|---|---|
| 0 | 5 | 41 / 3 | Miami: compare exact price/area; year and MLS require details. | PASS | PASS |
| 1 | 5 | 40 / 4 | San Francisco: minimum-price comparison; year and MLS require details. | PASS | PASS |
| 2 | 7 | N/A: named object or account state | Two named homes: bind price/area/year to each, then compare ratios. | PASS | PASS |
| 3 | 6 | 79 / 7 | New York: Co-op/bedroom/price comparison; year and agent require details. | PASS | PASS |
| 4 | 9 | N/A: named object or account state | New account, save named home, confirm Saved Homes; read property type. | PASS | PASS |
| 5 | 6 | N/A: named object or account state | Change only Alice’s phone; confirm account and unchanged location. | PASS | PASS |
| 6 | 9 | N/A: named object or account state | One fixed-date Carol tour; confirm stored status and source year. | PASS | PASS |
| 7 | 16 | N/A: named object or account state | Exact two-home David collection; open its generated share page. | PASS | PASS |
| 10 | 8 | 30 / 4 | Alice search: preserve and reopen all four criteria. | PASS | PASS |
| 11 | 5 | 41 / 9 | Aspen: maximum-price Single Family; source year and MLS required. | PASS | PASS |
| 12 | 5 | N/A: named object or account state | Detail facts, then follow the actual linked agent profile for email. | PASS | PASS |
| 13 | 7 | 41 / 7 | Second-lowest exact ratio after year/status filters; distinguish similar homes. | PASS | PASS |
| 14 | 19 | 31 / 2 | Austin: type/beds/garage/price comparison, exact collection membership, MLS. | PASS | PASS |
| 15 | 8 | N/A: named object or account state | Compare Bob’s stored tour dates; preserve tours and add exact local inquiry. | PASS | PASS |
| 16 | 10 | N/A: named object or account state | Three named homes, compare recorded ratios regardless of status. | PASS | PASS |
| 17 | 9 | 47 / 4 | Luxury threshold + Condo/status + maximum price; read agent and year. | PASS | PASS |

These executions are **guided/source-aware**: GPT-6 via Codex had inspected code, seed and expected facts. They establish actual UI feasibility and state effects, not independent discovery performance. Every run begins from the homepage after official reset, records real visible UI actions and before/after screenshots, captures terminal DB state before reset, and preserves the reset baseline. No direct DB/API mutation substitutes for task actions.

[validation.json](validation.json) contains per-task original/export hashes, action mappings, screenshot hashes, before/after/reset hashes and deterministic results. **16/16 verifiers pass** against their own frozen snapshots. The 134 grouped UI steps include one preserved failed link lookup followed by a successful corrected lookup. A group may fill a form and submit it; it is not a claim of 134 primitive actions. Native exports map semantic operation labels to the actual click/press action without changing observations, final answers or DBs. Raw JPEGs and pixel-identical PNG exports are retained. Full-page capture was unavailable; viewport screenshots and complete DOM observations are retained.

Initial scoring found genuine parser false negatives: a price-per-square-foot number and an appointment date were mistaken for construction years, and confirming the Tours page was mistaken for a confirmed appointment status. The fix adds 17 positive/negative cases, including contradictory or missing years, dates/areas used as decoys, negated status and false appointment confirmations. Two additional failures were native action-name packaging issues; the original and normalized hashes are both recorded.

The **124-case current verifier suite** covers wrong answers/object associations, foreign-origin and missing-navigation replay, no-op write tasks, unrelated state mutations and legitimate alternative paths/wording. The earlier **111/111 ad-hoc adversarial matrix** survives only as a historical structured result; its raw constructed fixtures were lost and it was not rerun after the parser fix. It is not counted as new task execution. Screenshot format checks assume a trusted recorder; independent review must judge the actual executions.

## Independent execution review and reconciliation

The [independent Claude Code comment](https://github.com/aiming-lab/WebHarbor/pull/84#issuecomment-5559623084) reports **16/16 PASS, 0 FAIL**, agreeing with all 16 deterministic results. The reviewer reports using Claude Fable 5.1 (`claude-fable-5-1`) and freezing its first-pass verdict before reading the PR, verifier code/results or prior conclusions.

- Reviewed candidate: `b66016dd16dfc7eb776f58d5490fc31caecac68c`; actual runtime image code and execution checkout are distinguished above.
- Input manifest SHA-256: `3125bf726ae7e8faa3020c070d5f08037b619f0474ab3c2c552a272e25be41fd`; all **618** listed inputs were rehashed during reconciliation, with no mismatch.
- Frozen verdict SHA-256: `342633f8e1a3f0a31cf5983912c196573a4c7336591d66d3c315938f1035f662`. The original verdict remains unchanged.
- The reviewer checked all task trajectories, decisive DOM observations and before/after state, but visually sampled only **4 of 268 screenshots**. Its comment's total of 258 is a counting error. This review does not certify human experience, source fidelity, visual quality, recorder integrity or verifier implementation; those require the separate evidence above.

Reconciliation covered the following specific points:

| Point | Evidence and resolution |
|---|---|
| Pending eligibility in tasks 3, 11 and 17 | The existing seed keeps Pending / Contract Signed in the `for-sale` category, preserves the published status in property facts, and marks `is_pending`. The local For sale filter tests that category without excluding pending listings. The tasks refer to this fixed local snapshot and do not request active-only listings. Recomputed selections match the recorded outcomes. This is a clarification of the existing filter, not a change to task acceptance. |
| Search area versus address city | The reviewer's claim that using `city` gives identical results is incorrect for New York: a literal `city='New York'` query has no qualifying Co-ops, while the actual UI search area includes seven via `city OR market_city`, including Brooklyn and Manhattan. Rechecking the real UI query preserves task 3's selection and PASS. The task asks for the New York search area, not an exact address-city string. |
| Inquiry message in task 15 | The task requires submitting a local inquiry, not displaying its message afterward. Independent row comparison confirms exactly one inquiry with the requested subject/message, user, listing and agent; all other tables, including existing tours, are unchanged. The inquiries page displays the subject only, as disclosed in the blind review. |

No application, seed, asset, task, rubric or verifier change resulted from the independent-review reconciliation itself. The subsequent owner-reported Sell omission is a separate application/asset change, documented above. That reconciliation-only documentation update reused the frozen executions and verdict; the separate Sell follow-up has its own UI checks and does not expand Claude’s review scope. Human experience and visual acceptance remain pending.

## Reproduce

```bash
./scripts/fetch_assets.sh
./scripts/build.sh compass-review:current
docker run -d --name compass-review \
  -p 127.0.0.1:8201:8101 -p 127.0.0.1:42000-42019:40000-40019 compass-review:current
curl -fsS http://127.0.0.1:8201/health
curl -fsS -X POST http://127.0.0.1:8201/reset/compass
python -m pytest sites/compass/tests sites/compass/verify/test_verifiers.py -q
# Run a task against http://localhost:42019/ and freeze its DB before reset.
python sites/compass/verify/verify_0.py --run_dir RUN \
  --initial_db BEFORE.db --after_db AFTER.db --no_llm
```

The HF candidate is immutable and publicly reachable but its PR is still open. Maintainers should merge/resolve the asset PR, update the pin if the merge produces a different commit, run the final build/asset/reset checks, then merge this code PR after human acceptance and final delivery checks. Independent execution feedback is resolved. Maintainers perform the merges. This Draft does not claim final acceptance.

# Compass contribution review

Reviewer takeover of [original PR #25](https://github.com/aiming-lab/WebHarbor/pull/25), contributed by **sarendis56 (Peichun Hua)**. The original commits remain in this branch. This Draft contains source/UI fixes and reviewer-authored grading contracts. Human experience and independent execution review are **pending**; it is not Ready for merge.

## Candidate and integration

- Current integration baseline: upstream `90afddb6d4af382935ded9a385f2eead604188cf` (Target added during validation).
- Integration code checkpoint: `3cdc0b66d72b8a789b89583176c668081de36852`; **20 sites**, Target `40018`, Compass **`40019`**, control plane `8101`.
- [Companion HF PR #53](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/53), immutable candidate `47232eba972567d138bbac478a6f4af9775a1d90`.
- Compass archive: 181,025,147 bytes; SHA-256 `df94bf02d1d9ffc5dd13a5f9d6ac8a262ab30a6f6d0b3b5fb7348da3b3f6d40a`. The other 19 archives equal the current upstream asset pin. Only Compass content is new relative to current main.

The 16 complete UI runs used code `366b15c0f38ead00b8c541e21504f02c73f64160` and Compass on `40018`, before Target merged. All Compass Python/CSS/JS/templates/data/verifier files are byte-identical in the integration candidate. Each task is identical except its `web` port. The Compass archive and rebuilt Docker seed also match. These are reused runs, with additional current-port integration checks; they are not 16 newly executed runs on `40019`. Early pilot manifests identify assets by archive hash instead of a published revision; remote equality was subsequently verified.

## Environment and functional checks

The current build passes 20/20 startup and homepage checks; reset-all takes 2.957 seconds and restores 23/23 files byte-for-byte. The supplementary task-5 run at 40019 also passes with persisted phone change and exact reset. Full Docker build, all-site startup/HTTP sweep, and per-file reset results are in [environment-validation.json](environment-validation.json). The current integration check supersedes the earlier 19-site sweep. The Compass runtime seed is `4fbb93f60edd007e3d2af660aec58fa4863672d96c6484e097c0eafb1d767979`; all 16 task resets restore it byte-for-byte.

The archive seed (`caa262ea5752016618c56e9bf01842257523cf8dae3ea25c57f719d61d7ce40f`) uses SQLite 3.53.1 encoding. Docker SQLite 3.40.1 rebuilds logically identical schema/rows with different bytes. Repeated rebuilds within Docker match exactly; reset compares the live DB with that runtime's seed, not a different platform's byte encoding.

**149 regression tests passed** (42 application/source cases and 107 verifier cases). They cover invalid registration, atomic preferences, malformed tour/inquiry input, CSRF, local redirects, object ownership, collection membership, saved-search round trips, rental formatting, exact price-per-area ordering, transaction identity and reproducible seeding. Real UI runs separately cover registration, login, profile edits, saved homes, tours, collections, saved searches and inquiries. Additional browser checks cover invalid credentials/required fields and saving/removing a home with reload persistence.

No forms contact external agents: writes remain in the local SQLite benchmark state. Synthetic fixture tests are separate from the recorded UI executions.

## Visual and source quality

[18 original/before/after screenshots](visual-review.md) cover home desktop/mobile, detail desktop/mobile, two-photo detail and the Miami list. They are unaltered browser captures with URLs, times, dimensions and hashes. Main repairs include official local fonts/hero, measured header and search proportions, cards, full/short galleries, share/photo dialogs, mobile property actions and narrow account tables.

Additional browser QA covers task templates at **390 and 320px**, plus representative **768px** home/list pages. Stable captures showed no document-level horizontal overflow. Long account tables intentionally scroll within a labeled region. Pointer activation of one wrapped collection link did not navigate through the browser adapter; keyboard activation succeeded. That adapter limitation is recorded rather than counted as an unqualified pointer PASS. First frames immediately after resizing were sometimes stale; settled captures supersede them. Five additional non-task detail pages were sampled for populated content and loaded photos.

Remaining differences are explicit: the list view omits the live map; the agent profile is a reduced source-backed contact/listings view; personalized recommendations, seller/mortgage/property-history/school services and live communications are outside scope. Official mobile Aspen photos failed to load during capture, so that source image supports layout only. These omissions are not presented as answer-leak safeguards. No human-approved visual regression baseline exists yet.

The 497 displayed listings retain original IDs and local galleries. Of 312 matching official transaction snapshots, 295 are displayed; **202 displayed records retain only contributor basic snapshots**. Unknown external facts stay absent instead of being generated. Source URL, retrieval time and HTML hash are in [source_data.json](../source_data.json); new image/font provenance is in `gallery_sources.json` and `visual_sources.json`.

All requested external answer facts were checked against matched source snapshots, separately from DB/verifier consistency. Task 7 uses contributor-only 3305 Dolphin Drive as an explicitly named collection member; it does not ask for unverified property facts. Its generated share token and account state are synthetic. Detailed facts are not added to search cards to reveal task answers.

## Task and grading audit

There are **16 candidate tasks**, IDs 0–7 and 10–17. IDs 8/9 were retired because generated agent sales volumes and unsupported open-house schedules could not be substantiated. Task 1 now uses the available one-bedroom-or-more Condo set; task 10 saves a three-bedroom Condo search with actual results. The original IDs remain stable.

The pool column is the unfiltered area's recorded catalog / qualifying set, independently checked against the seed. It is not the fully filtered UI count; after applying all filters, every displayed result should match. Natural pools range from 30–79 (Luxury 47), include multiple types and near misses. Named-object and account-write tasks use meaningful state changes/comparison instead of inventing distractors. Target position in a user-sorted result is not itself leakage: required detail facts and writes remain necessary. Task 13 provides the strongest comparison/disambiguation check; difficulty has not been calibrated with an independent model cohort.

| Task | Steps incl. done | Natural pool / qualifying | Contract / quality check | Recorded execution | Verifier |
|---|---:|---|---|---|---|
| 0 | 9 | 41 / 3 | Miami: compare exact price/area; year and MLS require details. | PASS | PASS |
| 1 | 9 | 40 / 4 | San Francisco: minimum-price comparison; year and MLS require details. | PASS | PASS |
| 2 | 9 | N/A: named object or account state | Two named homes: bind price/area/year to each, then compare ratios. | PASS | PASS |
| 3 | 9 | 79 / 7 | New York: Co-op/bedroom/price comparison; year and agent require details. | PASS | PASS |
| 4 | 14 | N/A: named object or account state | New account, save named home, confirm Saved Homes; read property type. | PASS | PASS |
| 5 | 9 | N/A: named object or account state | Change only Alice’s phone; confirm account and unchanged location. | PASS | PASS |
| 6 | 15 | N/A: named object or account state | One fixed-date Carol tour; confirm stored status and source year. | PASS | PASS |
| 7 | 23 | N/A: named object or account state | Exact two-home David collection; open its generated share page. | PASS | PASS |
| 10 | 15 | 30 / 4 | Alice search: preserve and reopen all four criteria. | PASS | PASS |
| 11 | 8 | 41 / 9 | Aspen: maximum-price Single Family; source year and MLS required. | PASS | PASS |
| 12 | 6 | N/A: named object or account state | Detail facts, then follow the actual linked agent profile for email. | PASS | PASS |
| 13 | 12 | 41 / 7 | Second-lowest exact ratio after year/status filters; distinguish similar homes. | PASS | PASS |
| 14 | 27 | 31 / 2 | Austin: type/beds/garage/price comparison, exact collection membership, MLS. | PASS | PASS |
| 15 | 12 | N/A: named object or account state | Compare Bob’s stored tour dates; preserve tours and add exact local inquiry. | PASS | PASS |
| 16 | 11 | N/A: named object or account state | Three named homes, compare recorded ratios regardless of status. | PASS | PASS |
| 17 | 11 | 47 / 4 | Luxury threshold + Condo/status + maximum price; read agent and year. | PASS | PASS |

These executions are **guided/source-aware**: GPT-6 via Codex had inspected code, seed and expected facts. They establish actual UI feasibility and state effects, not independent discovery performance. Every run begins from the homepage after official reset, records real visible UI actions and before/after screenshots, captures terminal DB state before reset, and preserves the reset baseline. No direct DB/API mutation substitutes for task actions.

[validation.json](validation.json) contains per-task run hashes, step counts, before/after/reset hashes and deterministic results. **16/16 verifiers pass** against each run's own frozen snapshots. They do not read the later live DB. Raw browser JPEGs were retained; native PNG exports preserve the exact decoded pixels without resizing/cropping. The two initial pilots additionally required a documented `id` → `task_id` metadata normalization; originals were retained. Full-page capture was unavailable from this browser adapter, so viewport screenshots and complete DOM observations are retained.

**111/111 constructed adversarial cases matched their expected outcomes**. Coverage includes no-op/answer-only shortcuts, wrong-task replay, foreign origins, missing explicit navigation, wrong values/object associations, unchanged state on write tasks and unrelated DB changes; valid wording, address/currency variants and alternative collection/search paths are tested too. `validation.json` lists each fixture and outcome. Screenshot format checks do not interpret pixels and assume a trusted recorder. Independent review must judge the actual executions.

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

The HF candidate is immutable and publicly reachable but its PR is still open. Maintainers should merge/resolve the asset PR, update the pin if the merge produces a different commit, run the final build/asset/reset checks, then merge this code PR after human and independent-review feedback is resolved. Maintainers perform the merges. This Draft does not claim final acceptance.

# public_storage — deterministic grading contract (reviewer-authored)

One deterministic verifier per benchmark task (`verify_0.py` … `verify_20.py`),
plus the shared utilities in `verify_lib.py` and the contract test suite under
`tests/`. Authored by the public_storage reviewer on branch
`orch/review/public_storage`; the contributor's task rows in `../tasks.jsonl`
carry only the five definition keys, with `verifier_path` + `judge_rubric`
appended by `append_rubrics.py` (definition keys stay value-identical).

## Philosophy

DETERMINISTIC FIRST — same contract as the hardened reviewer suites
(`sites/porsche/verify/`, `sites/mta/verify/`, `sites/megabus/verify/`).
No LLM call is load-bearing. Every check is one of:

1. **Package identity** — `task_id` matches, trajectory `terminated` with
   `agent_done`, non-empty final answer, every recorded URL on the same
   loopback origin/port as `start_url`, every referenced screenshot a
   decodable PNG.
2. **Navigation gates (anti knowledge-shortcut)** — the agent must have
   opened the on-site surfaces the task names: the ZIP search results page
   with the task's type/size/sort filters, the facility detail pages, the
   Hold Now form for the exact unit, the reservation confirmation page, the
   size-guide hub and FAQ pages, the storage-type / storage-solutions pages,
   the blog article, the help-center topics, and the login / register /
   account / bill-pay pages. A correct answer without the navigation is a
   memory-recall shortcut = FAIL.
3. **Answer gates** — token / phrase / amount / count / code matching against
   ground truth HARDCODED in each `verify_N.py` (never in `tasks.jsonl`).
   Generated values the agent cannot know in advance (reservation codes,
   payment confirmation numbers) are matched against the DB after-state
   instead of a literal.
4. **DB after-state** — initial (seed) vs after (instance) SQLite snapshots.
   Read-only tasks require a row-identical database; stateful tasks require
   the exact allowed row delta (one reservation with the task's unit /
   facility / contact / move-in date, one payment with the charged amount,
   one user row for the registration task, or the phone edit on the named
   benchmark account) and nothing else.

Frozen seed contract: `SCHEMA_SHA256` / `SEED_ROWS_SHA256` / `SEED_COUNTS`
in `verify_lib.py`, computed over the image-built
`instance_seed/public_storage.db` (md5 `7760aedb…`).

## Usage

```bash
# grade a run directory (trajectory.json + screenshots/) against the
# review container's DBs:
python3 sites/public_storage/verify/verify_7.py --run_dir runs/7 \
    [--initial_db PATH] [--after_db PATH] [--container NAME]

# run the contract tests (needs the review container for the seed DB,
# or PUBLIC_STORAGE_TEST_SEED_DB pointing at a copy):
python3 -m pytest sites/public_storage/verify/tests -q
```

Output: JSON `{task_id, pass, reason, evidence[]}`; exit 0 on PASS, 1 on
FAIL. Any infra error fails closed (`infra_error`).

## Task → verifier map

| Task | Kind | Required surfaces | DB delta |
|---|---|---|---|
| 0 | hold | ZIP 78704 search, facility 638, hold form, confirmation | +1 reservation |
| 1 | read | size guide, Denver search, facility 2387 | — |
| 2 | hold | size guide, Up-to-35' FAQ, ZIP 80202 vehicle search, facility 837 | +1 reservation |
| 3 | cancel+hold | access-reservation ×2, facility 68, hold form | PS-3184265 cancelled, +1 reservation |
| 4 | login+cancel+hold | sign-in, account, facility 200, hold form | PS-4907132 cancelled, +1 reservation |
| 5 | bill pay | bill-pay login, bill-pay page | +1 payment, rental balance → 0 |
| 6 | read | Bellevue search, facilities 68 + 81 | — |
| 7 | read | facility 81 | — |
| 8 | read | Chicago city page, facility 1345 | — |
| 9 | register+hold | create-account, ZIP 60601 search, facility 1739, hold form | +1 user, +1 reservation |
| 10 | read | blog index/category, the article | — |
| 11 | read | help center, both topic pages | — |
| 12 | profile edit | sign-in, account edit, account | carol's phone updated |
| 13 | read | military solutions page, Charlotte search, facility 2334 | — |
| 14 | read | facility 496 | — |
| 15 | read | ZIP 98101 search ×3 sort orders | — |
| 16 | hold | ZIP 32801 search, facility 729, hold form | +1 reservation |
| 17 | hold | climate page, ZIP 98101 search, facility 5903, hold form | +1 reservation |
| 18 | login+hold | sign-in, account, facility 1019, hold form | +1 reservation |
| 19 | read | facility 809 | — |
| 20 | read | 10'x20' FAQ page, facility 81 | — |

## Contract test coverage (`tests/test_verifiers.py`)

- 21 honest trajectories (read-only against a clean seed pair; stateful
  against the seed with the exact allowed delta) MUST PASS.
- 21 no-op runs (homepage only, empty answer, clean DB) MUST FAIL.
- 21 shortcut runs (correct answer, homepage-only navigation) MUST FAIL.
- 21 wrong-answer runs (honest navigation, wrong values) MUST FAIL.
- 12 read-only tasks MUST FAIL on a mutated after-DB.
- 10 stateful tasks MUST FAIL on a state-mismatch (no DB delta) and a wrong
  delta (wrong unit / facility / holder / amount / phone).
- Tamper cases MUST fail closed: wrong task_id, off-site URL, non-done
  trajectory, missing screenshots, corrupt PNG, empty answer.

Live replay evidence (review container): the 21-verifier no-op sweep is
21/21 FAIL against the live DBs, and real-Chromium honest replays of T7
(read-only) and T16 (stateful) PASS with live DB snapshots —
`wh-ps-review-evidence/verify_results/live_contract_summary.json`.

# medicare_gov — verifier contract (15 redesigned deep tasks)

Contract authored on `orch/contribute/medicare_gov` for the depth-review round-2
redesign: the 30 shallow tasks (and their grading contract) are retired; this
directory grades the new 15 deep functional-chain tasks. The harness lineage is
the hardened WebHarbor verifier suite (sites/landwatch, sites/imgur, then the
first medicare_gov review contract @ 729f1517); the frozen-seed contract is
unchanged.

## Layout

- `verify_lib.py` — shared deterministic verifier harness (package-identity
  gates, navigation gates, answer matchers, frozen-seed DB contract, advisory
  anchored LLM helpers that never decide a verdict, message-read delta helper).
- `verify_0.py` … `verify_14.py` — one deterministic verifier per task; ground
  truth is HARDCODED inside each script (never in tasks.jsonl).
- `tests/` — pytest contract suite (119 checks): honest PASS (15/15 plus the
  opened-message variant of task 7), no-op FAIL, wrong-answer FAIL,
  homepage-shortcut FAIL, read-only DB-mutation FAIL, login-delta FAIL,
  message-read-flip FAIL, state-mismatch FAIL, wrong-state FAIL, collateral
  FAIL, cross-user FAIL, package tampering fail-closed. Run from the repo's
  agent_demo env:
  `cd agent_demo && uv run python -m pytest ../sites/medicare_gov/verify/tests -q`

## Frozen seed contract

The seed is rebuilt deterministically at image-build time (PYTHONHASHSEED=0,
fixed scrypt digest, see `.build-generated-seed`). The physical sqlite layout
differs between builds (host md5 `ec01a677…`, container md5 `8165aea5…`) but the
logical content is frozen and was verified identical on both builds:

- SCHEMA_SHA256 `644925b3…` (23 tables)
- SEED_ROWS_SHA256 `1ebd3c7a…` (row-canonical, ORDER BY all columns)

Verifiers fail closed (`snapshot_contract_invalid`) unless the initial snapshot
matches these digests, the counts, the four benchmark users, and the frozen
password hash.

## Per-task DB delta contract

- read-only tasks (0–6, 11, 13, 14): every table row-identical (tasks 6 and 11
  include anonymous publication orders, which the app deliberately does not
  persist — no DB row exists for anonymous orders).
- login-read task 7: exactly one deterministic `login_events` insert for alice;
  optionally exactly the is_read flip of the newest unread message (id 3) if
  the agent opened it; nothing else.
- stateful tasks:
  - 8 — bob's `$202.90` / `2026-10-25` bill flips Due→Paid with `Bank account
    ending 4821` (paid 2026-09-23); the pre-paid bill untouched; bob's old
    mailing address `is_current=0` plus exactly one new current row
    `789 Oak Street, Oak Park, IL 60302`;
  - 9 — alice's old address `is_current=0`, exactly one new current row
    `45 Meadow Lane, Buffalo Grove, IL 60089` effective 2026-09-23, and exactly
    one `card_requests` row (reason `lost`, `Mailing in 7-10 days`, 2026-09-23);
  - 10 — exactly two `pub_orders` rows: pub 11931 × 2 Standard Print and pub
    02110 × 1 Large Print, both to alice's seed address (12 Sunset Terrace,
    Springfield, IL 62704-1234), `2026-09-23`, Processing;
  - 12 — exactly one alice `login_events` insert AND exactly the is_read flip
    of the newest unread message (id 3) — the task forces opening it because
    the enrollment dates live in the message body.
  Collateral writes anywhere else fail the run.

## Live redesign evidence

Honest step-count walks (15/15 in 16-26 steps, per-task screenshots +
walk.json), live DB-delta dumps for the stateful tasks, read-only byte-identity
checks, and a full live replay of the grading contract (real browser runs
against the contributor container, real seed/after DB dumps, deterministic
verifiers PASS 15/15 with --no_llm True) are archived in
`wh-medicare-gov-redesign-evidence/` (runs/, verify_replay/, scripts/).

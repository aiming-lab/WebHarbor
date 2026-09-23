# Chess.com verifier contract (reviewer-authored)

One deterministic verifier per task (`verify_N.py` for `Chess.com--N`), sharing
`verify_lib.py` — the hardened 9GAG/merriam-webster contract:

1. **Package identity** — task_id match, `terminated`/`agent_done`, non-empty final
   answer, every recorded URL on the review origin, every screenshot a decodable PNG.
2. **Navigation gates** — the on-site pages each task names MUST have been opened
   (correct answer + no navigation = memory shortcut = FAIL).
3. **Answer checks** — affirmative token/phrase/number/amount/percent/date matching
   against ground truth HARDCODED in each verifier (never in tasks.jsonl).
4. **DB after-state** — the seed snapshot must match the frozen chess_com seed
   (schema sha256, table counts, full rows digest); read-only tasks require every
   table row-identical, stateful tasks require the exact allowed delta.
5. **LLM helpers** — advisory only, never load-bearing; verdicts are decided with
   `--no_llm True`.

CLI: `python verify_N.py --run_dir DIR [--initial_db P --after_db P --container NAME --no_llm True]`
emits `{task_id, pass, reason, evidence[]}` and exits 0/1. Without explicit DB paths the
verifier fetches snapshots from `$WH_CONTAINER` (default `wh-review`) via `docker cp`.

Tests: `verify/tests/test_verifiers.py` (honest PASS, no-op FAIL, wrong-answer FAIL,
shortcut FAIL, read-only DB tamper, stateful state-mismatch, package tampering,
fail-closed infra errors). Run:
`cd agent_demo && uv run --with pytest python -m pytest ../sites/chess_com/verify/tests -q`
or in the runtime image: `python3 -m pytest verify/tests -q`.

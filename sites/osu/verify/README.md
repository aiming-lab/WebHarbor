# osu — deterministic task verifiers

Grading contract for the 20 Ohio State University tasks in `sites/osu/tasks.jsonl`.
Same design as `sites/merriam_webster/verify/` (the canonical example): one
`verify_N.py` per task over a shared `verify_lib.py`, deterministic-first, with an
anchored LLM screenshot check as a secondary confirmation.

## Files

| File | Purpose |
|------|---------|
| `verify_lib.py` | Shared harness: trajectory loading, `navigated_to` anti-shortcut check, deterministic matchers (`contains_all/any`, `contains_number`, `count_present`), anchored LLM utilities (`llm_text_match`, `llm_screenshot_shows`), the `Judge` harness, and the CLI. |
| `verify_0.py` … `verify_19.py` | One verifier per task (`Ohio State University--N`). The frozen ground truth is **hardcoded here**, never in `tasks.jsonl`. |
| `selfcheck.py` | Deterministic self-test: proves every verifier PASSes a correct trajectory and FAILs a wrong-answer / no-navigation one, with zero LLM calls. |

## What each verifier checks (deterministic first)

1. **Navigation (anti knowledge-shortcut).** The trajectory MUST contain a step whose
   URL is the on-site page that renders the fact (e.g. `/athletics/ohio-state-buckeyes-football`
   for the football coach). A correct answer with no matching page visit is memory
   recall → FAIL. This is the primary defense for facts that are also true of the real
   OSU (Big Ten, founded 1870, Ohio Stadium).
2. **Answer.** Token containment / number match / degree-set count against the hardcoded
   ground truth. Numbers ignore thousands separators (`46,820` == `46820`).
3. **Screenshot (anchored, secondary).** One `llm_screenshot_shows` call confirms the fact
   is *visibly rendered*. It is anchored on the expected content (the model never supplies
   knowledge) and is **fully skipped under `--no_llm`**, so a deterministic run is decided
   by checks 1–2 alone.

Output is `{task_id, pass, reason, evidence[]}` on stdout; exit 0 = PASS, 1 = FAIL.

## Run one verifier

Via the standard entry point (`agent_demo/eval_judge.py`, which locates the verifier from
`trajectory.verifier_path` and runs it under `uv`):

```bash
cd agent_demo
uv run python eval_judge.py --run_dir runs/osu0 --verifier True
```

Directly (deterministic only, no API key needed):

```bash
cd agent_demo
uv run python ../sites/osu/verify/verify_3.py --run_dir ../runs/osu3 --no_llm True
```

The LLM screenshot check uses the unified env vars `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
`JUDGE_MODEL` (same as `agent.py` / `eval_judge.py`). Without `--no_llm`, configure those
or the screenshot check cannot pass.

## Run the self-test

```bash
python3 sites/osu/verify/selfcheck.py      # 20/20 tasks must pass all 3 assertions
```

For each task it builds a GOLDEN (correct nav + answer → PASS), a WRONG_ANS (correct nav +
wrong answer → FAIL) and a NO_NAV (right answer, page never opened → FAIL) trajectory and
asserts the verdict. See `TASK_REVIEW.md` for the per-task feasibility assessment.

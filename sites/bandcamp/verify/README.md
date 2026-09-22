# Bandcamp Task Verifiers

18 wrappers cover `Bandcamp--0..17`; they consume only the task's frozen snapshots and connect to neither Docker nor online models.

```bash
python3 -B -m unittest discover -s sites/bandcamp/verify -p 'test_*.py' -v
python3 -B sites/bandcamp/verify/verify_0.py --run_dir runs/bandcamp-0
```

`run_dir` must contain `trajectory.json`, whose `task_id`, `start_url`, `steps[].url`, and string `final_answer` must be valid. `initial.db` (or `before.db`) and `after.db` are auto-discovered; explicit `--initial_db` / `--before_db` and `--after_db` are also supported. If `task.json` is present, its `id` must match the wrapper. The legacy consumer flags `--container` / `--no_llm` are parsed for compatibility only and trigger no live-state fallback.

- Exit 0: a valid PASS.
- Exit 1: a valid ordinary FAIL, including no-op, wrong results, missing on-site pages, and unrequested final business-state changes.
- Exit 2: missing snapshots or parsing/identity/schema/integrity errors; these must not count as valid negative cases.

Information tasks require a correct affirmative fact, relevant same-origin pages, and whole-table invariance. Short answers are grounded by the task and the pages; explicitly wrong comparisons, same-name album/track ambiguity, already-covered negations, and extra collection values are rejected. These are deterministic language rules, not a full semantic proof of arbitrary natural language; real actor answers still require the independent head judge. Do not relax a predicate to accommodate one generated text.

State tasks require a non-empty final but not English keywords, fixed login/final URLs, or a post-checkout order-number restatement. All original rows and fields are preserved; the only allowed changes are a new row in the target wishlist/cart, the designated profile fields, or the full cart-to-order conversion plus the expected synchronized-checkout side effects.

`test_seed.sql` exports the full real schema/data from the audited synthetic seed; positives are established by independent SQL and hand-written answers, not from verifier PASS constants. Fixtures, HTTP diagnostics, and no-ops are not pure-visual E2E results. The `success/pass` defects of the root-shared `agent_demo/eval_judge.py` are not fixed in this directory; callers must treat exit 0/1 as healthy grading and exit 2 as an infrastructure error.

## PR 104 regression fixes

Prices, durations and tote colors are checked in `answer_facts.py`. Price checks
bind each amount to a format/edition, reject incorrect currency and contradictory
amounts, and accept common spelled-out numbers and equivalent cent amounts.
Durations bind to track numbers/titles; prose, compact lists and labelled tables
are supported, but arbitrary English entailment is not claimed. Unknown or
ambiguous measurement claims may be conservatively rejected.

Tasks 1 and 11 require observed same-origin Discover navigation before the album
page; task 1 additionally requires an applied non-default filter. Either `url`
or `url_after` can supply an observed page. Target URLs inside another page's
query string do not count. No particular search phrase or filter combination is
mandated. State comparisons remain snapshot-only and unchanged.

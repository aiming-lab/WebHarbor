# sourceforge — deterministic task verifiers

One verifier per task (`verify_0.py` … `verify_20.py`) plus the shared
`verify_lib.py`. Ground truth is HARDCODED in each verifier module (frozen from
the deterministic seed built at image time, md5 `bfb58247…`, sha256 rows
`05fdb69d…`) — never in `tasks.jsonl`, which carries only the two additional
keys `verifier_path` and `judge_rubric` (pure-rule English; the original five
keys stay byte-identical, no `answer` key).

## Contract (fail-closed)

1. **Package identity** — task_id match, `terminated`/`agent_done`, non-empty
   answer, every URL on the same loopback origin:port, every referenced
   screenshot a decodable PNG.
2. **Navigation gates** — the agent must have actually opened the on-site
   surfaces the task names (search results, project/reviews/files/stats pages,
   trackers, forums, wiki, news, business directory, auth/account). A correct
   answer without the navigation is a knowledge shortcut = FAIL.
3. **Answer checks** — deterministic token/phrase/number matching against the
   hardcoded ground truth.
4. **DB after-state** — read-only tasks require the after-DB row-identical to
   the frozen seed; stateful tasks (7, 13, 18) require the exact allowed delta
   (bookmark + 5-star review + counter bump / new user with country DE /
   bookmark swap + 4-star review + counter bump) and nothing else.

## Usage

```bash
# one task (run dir = trajectory.json + screenshots/ + initial.db + after.db)
python3 verify/verify_7.py --run_dir runs/SourceForge--7

# the whole contract test suite (needs the review container for the seed)
python3 -m pytest verify/tests -q
```

`make_verifiers.py` regenerates `verify_N.py` from the frozen spec table;
`append_rubrics.py` (already applied) appends the two tasks.jsonl keys.

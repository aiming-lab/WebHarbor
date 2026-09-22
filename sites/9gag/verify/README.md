# 9GAG deterministic grading contract

Each row in `sites/9gag/tasks.jsonl` points to `verify_0.py` … `verify_19.py`. The wrappers share
`verify_lib.py` (same API family as `sites/merriam_webster/verify/verify_lib.py`, hardened the way
`sites/walmart_careers/verify/verify_lib.py` is). Ground truth is hardcoded inside each `verify_N.py`
and never appears in `tasks.jsonl`. Every verdict is decided deterministically; the anchored LLM helpers
(`llm_text_match`, `llm_screenshot_shows`) are kept for parity and only add `[INFO]` evidence when an
endpoint is configured — they never change PASS/FAIL, and `--no_llm True` silences them.

## Inputs

```bash
uv run python sites/9gag/verify/verify_0.py \
  --run_dir /abs/path/to/run \
  --initial_db /abs/path/to/initial.db \
  --after_db /abs/path/to/after.db \
  --no_llm True
```

If explicit snapshots are omitted the verifier looks for `<run_dir>/initial.db` and `<run_dir>/after.db`,
then falls back to `docker cp` from `$WH_CONTAINER` (default `wh-review`) at
`/opt/WebSyn/9gag/instance_seed/9gag.db` (initial) and `/opt/WebSyn/9gag/instance/9gag.db` (after).
Missing or invalid inputs fail closed (`infra_error: true`). Output is JSON `{task_id, pass, reason, evidence}`;
exit 0 = PASS, 1 = FAIL. `agent_demo/eval_judge.py --run_dir <run> --verifier True` invokes the same script.
Boolean flags take a value (`--no_llm True`), as in the other suites.

## Package validation (every task)

- exact `task_id`; `terminated: true` with `termination_reason: agent_done`; at least one step;
- a non-empty `final_answer`;
- every recorded URL (`start_url`, step `url`s, `final_url`) is `http://` on a loopback host **and the same
  port as `start_url`** (alt-port containers are fine; mixed origins are not);
- both screenshots referenced by every step exist and decode as non-empty PNGs.

## Snapshot contract

Both snapshots must have exactly the seven 9GAG tables (`user, post, comment, vote, saved_post, hidden_post,
report`) with the pinned schema hash (`SCHEMA_SHA256`) and identical schemas. The initial snapshot must carry
the frozen seed counts (80 posts, 4 users, 4 comments, 12 votes, 16 saved posts, 0 hidden, 0 reports) and the
four benchmark accounts. Across snapshots the four accounts keep `id/username/email`, and the 80 seed posts
keep every catalog column (`slug, title, description, image, section, post_type, tags, author_name,
created_rank, featured`); only the counters (`up_votes, down_votes, comment_count`) may move, and only where
a task allows it. Any drift fails closed with `snapshot_contract_invalid`.

## Per-task contract

| Task | Navigation gates (all required) | Answer / state check |
|---|---|---|
| 0 | search; all three lighthouse details | office width/material, bookshop desk materials, radio test/weather; DB unchanged |
| 1 | search; all three rescue details | names and behaviors; cat dates, dog occasion, kitten solution; DB unchanged |
| 2 | search; all three camping details | solar protection/power, lantern test count/criteria, tarp runoff mechanism; DB unchanged |
| 3 | Science & Tech; all three bridge details | humming frequency/railings, whistling seam/location, rain-struck panels; DB unchanged |
| 4 | search; all three library details | cabinet color/schedule, depot supplies, hospital coverage/shift; DB unchanged |
| 5 | Bob login; Sports; both original details | marathon and championship facts/points; save only championship post 30; only the requested save changes |
| 6 | search; all three creative-project details | baker attempts/time, guard years/notebooks, eyebrow displacement; DB unchanged |
| 7 | Alice login; Gaming; both original details | keyboard and arcade facts/points; save only arcade post 21; only the requested save changes |
| 8 | search; all three music/rain details | concert platform, percussion rain mechanism, city light sensor/response; DB unchanged |
| 9 | Animals & Pets; all three original details | names/points ranked highest first, dog/fox behavior, top-two point gap; DB unchanged |
| 10 | login as alice (`/login` + identity typed); search (lighthouse/office/ocean); detail of the **original** lighthouse office; `/login` before the detail | exactly one added `saved_post` (alice, post 12); nothing else changes |
| 11 | login as carol; `/interest/animals`; detail of the **original** kayak-dog post; order login → feed → detail | exactly one added `vote` (carol, post 20, +1); post 20 `up_votes` +1 only; nothing else changes |
| 12 | login as bob; `/interest/science`; detail of the **original** humming-bridge post; order login → feed → detail | exactly one added `comment` (bob, post 19) whose text equals the task sentence (case and trailing period tolerated); post 19 `comment_count` +1; nothing else changes |
| 13 | login as carol; search (office/plant/badge/employee/kevin/pothos); detail of the **original** office-plant post; login before detail | exactly one added `hidden_post` (carol, post 26); nothing else changes |
| 14 | login as david; `/news`; detail of the 2009 press-conference post; its `/report` form; order login → news → detail → report | exactly one added `report` (david, post 6, `Misinformation`); nothing else changes |
| 15 | login as alice; `/submit`; the published page `/gag/quiet-victories-deserve-confetti`; order login → submit → post | exactly one added `post`: exact title, `wholesome`, exact description, tags `community|education|wholesome`, author `alice_j`; nothing else changes |
| 16 | login as alice; `/settings`; login before settings | alice's `display_name`/`bio`/`location` equal the task values; her `id/username/email/password_hash/joined_at` unchanged; no other user or table changes |
| 17 | `/register` | exactly one added `user` with the exact email + username whose stored hash verifies the task password; seeded users untouched; answer mentions `river_reader` |
| 18 | login as alice; `/saved`; login before saved | exactly one removed `saved_post` (alice, post 11); nothing else changes |
| 19 | login as david; `/interest/science`; detail pages of **all three** compared originals (11, 19, 25); login before browse | exactly one added `saved_post` (david, post 19 — the 440 hertz post); nothing else changes |

Precondition checks (`initial_state_requires_action`) make sure the seed does not already contain the
target state, so a stale-state no-op can never pass. Answer matchers are affirmative-only (a negated
mention such as "not orange" does not count), counts must be standalone integers or number words, and
decimals must match exactly.

Note on the "Community remix" clones: the seed duplicates every curated post as `Community remix N: …`
with the same description. The rule is **provenance only matters where it changes the graded outcome**:

- **Read-only fact tasks (0–4, 6, 8): either detail page is accepted**, because the clone repeats the original's
  description verbatim, so an agent that reads the fact off the clone has answered the question correctly.
  Requiring the original there would fail a correct answer on a hidden provenance rule.
- **Tasks 5, 7 and 9 require the originals**, because it compares *point counts* and the clones carry different ones,
  so using a clone changes the answer.
- **Stateful tasks (5, 7, 10-13, 18, 19) require the original**, because the clone is a genuinely different row
  and saving/voting/hiding/commenting on it is a different database effect.

Every task whose grade depends on provenance now says so in its `ques` ("not its 'Community remix' copy"),
so the requirement is visible to the agent instead of hidden in the verifier.

## Tests

```bash
# unit matrix (synthetic trajectories over copies of the frozen seed; no site, no docker, no LLM)
cd agent_demo && uv run python -m unittest discover -s ../sites/9gag/verify/tests -p 'test_*.py'

# live matrix (Playwright drives every task against a running mirror; CONTRIBUTING §C evidence)
cd agent_demo && uv run python ../sites/9gag/verify/tests/live_matrix.py --base http://127.0.0.1:45001 \
    --site_dir ../sites/9gag --out runs/9gag_matrix --reset_cmd "<restore seed + restart site>"
```

The unit tests need `sites/9gag/instance_seed/9gag.db` (an HF asset; `scripts/fetch_assets.sh 9gag`) and skip
otherwise. They cover: genuine PASS, run-dir snapshot discovery, no-op, shortcut (correct answer without
navigation), wrong answers per fact, wrong task id, unterminated runs, mixed origins, corrupt screenshots,
read-only writes, schema/catalog tampering, stale-state preconditions, wrong target/account/reason/text,
duplicate actions, counter-bump consistency and collateral writes. `verify/tests/` is excluded from the
image by `.dockerignore`.

## Reviewed answer and media corrections

Read-task facts are checked by `answer_checks.py`: quantities include units and property associations; swapped values, contradictory claims and unrelated matching tokens are rejected by the covered controls. Common paraphrases (such as salvaged oak and quiet tactile switches) and exact unit conversions are accepted. These are bounded deterministic patterns, not unrestricted natural-language understanding. Tasks 0–9 now require multi-source investigation; wording, rubrics and `research_checks.py` define the same expanded contract. Tasks 5 and 7 also require one exact save. Entity-labelled prose, bullets and tables are accepted without a fixed output template. The shared `answer_checks.py` still validates each primary property inside its entity context.

`migrate_seed.py` converts the 70 curated posts to text posts without changing descriptions, IDs, task facts or account state. The original archive is preserved; fetch/build applies the correction before runtime/reset copies. New posts default to no preview image.

Additional focused controls live in `test_answer_checks.py` and `test_media_migration.py`. Re-run the official grading entrypoint on browser trajectories as well as these synthetic controls.

## Difficulty revision

The short tasks retain their original primary facts and add related sources or an evidence-based saved outcome. No catalog or HF archive changed. The verifier does not impose an action-count minimum: source visits, complete correctly attributed answers and exact saved state determine success. Measured replay counts are evidence, not a guaranteed shortest path.

`research_fixtures.py` supplies independent synthetic answers and equivalents. Contract tests reject missing individual sources, former single-post answers, wrong secondary facts, contradictions, wrong accounts/targets, extra writes and remix substitutions where points differ. `live_matrix.py` reads answers from rendered pages and records scripted UI replays; it is not an autonomous LLM run.

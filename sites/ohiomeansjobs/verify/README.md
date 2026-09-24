# OhioMeansJobs — reviewer grading contract

Authored on the review branch `orch/review/ohiomeansjobs` (reviewer track,
review-env skill). One deterministic verifier per task (`verify_0.py` …
`verify_17.py`) + `verify_lib.py` (shared utilities + frozen seed contract) +
`append_rubrics.py` (the tool that inserted `verifier_path` / `judge_rubric`
into `tasks.jsonl` while keeping the five contributor keys byte-identical) +
`tests/` (102 deterministic contract tests).

## Design

- **Deterministic first.** No LLM call is load-bearing. Every check is a
  navigation gate over the recorded trajectory URLs, a token/phrase/count/date
  match against ground truth hardcoded in each verifier, or a SQLite
  after-state comparison. Ground truth lives ONLY here — `tasks.jsonl` carries
  no answer key.
- **Frozen seed contract** (`verify_lib.py`): schema sha
  `8124a64f…`, 14-table counts (160 jobs / 4 users / 89 centers / 37 agencies /
  …), rows sha `83af2826…` over the build-time seed (PYTHONHASHSEED=0, frozen
  bcrypt hash, RNG_SEED=20260924 anchored to 2026-09-24). A tampered or
  foreign `initial.db` fails closed.
- **Identity gates:** task_id match, `terminated` + `agent_done`, non-empty
  final answer, every URL on the same loopback origin and port as `start_url`,
  every referenced screenshot a decodable PNG.
- **Navigation gates (anti knowledge-shortcut):** each task names the surfaces
  the agent MUST have opened — job search with the task's query/facet params,
  the specific job detail page(s), the employer profile, the account area, the
  career quiz, county lookup with the right `county` params, the state-agency
  roster, the news article, the help articles, the employer hub, the site
  search with the right `q`. A correct answer with homepage-only navigation is
  a memory-recall shortcut = FAIL.
- **DB after-state:** read-only tasks (0, 1, 8–16) require every table
  row-identical; stateful tasks (2, 3, 4, 5, 6, 7, 17) require the exact
  allowed delta and nothing else:
  - T2: `users` +1 (grad.2026@test.com), `cover_letters` +1 ('First Position
    Letter'), `applications` +1 (user 5 → job 6928092839, letter attached)
  - T3: `applications` +1 (alice → CICU NP job, cover_letter_id = Med-Surg letter)
  - T4: `saved_jobs` −1 (bob → lift-driver job), `applications` +1 (bob →
    Material Handler job)
  - T5: `saved_searches` +1 ('Remote developer roles', Daily, remote params)
    and −1 ('Remote data analyst jobs', Monthly)
  - T6: `career_quiz_results` +1 (top trait Enterprising)
  - T7: `resumes` — david's row gains 'tax preparation', stays active
  - T17: `cover_letters` −1 (Driver) +1 ('Warehouse Team Letter') for bob
- **Known task-wording finding (T12):** the task asserts "the newest one, at
  Steris Corporation", but under the site's date sort the true newest remote
  data-analyst result is 'Sales Instructor' @ Vertiv (2026-09-24). The
  verifier therefore accepts either defensible reading of "the second-newest
  result" (the literal second row = Sales Instructor @ Vertiv, or the row
  after Steris = Experienced Registered Nurse, RN, Nurse Helpline @
  Cincinnati Children's); every other answer fails. See the review report.

## Usage

```bash
# from agent_demo/ (so simpleArgParser resolves), or plain python3:
uv run python sites/ohiomeansjobs/verify/verify_0.py --run_dir runs/0
#   --initial_db/--after_db override the snapshot source; by default they are
#   docker-cp'd from $WH_CONTAINER (default wh-omj-review).
# output: JSON {task_id, pass, reason, evidence[]} on stdout; exit 0 = PASS.
```

Contract tests (no LLM; snapshots are seed copies mutated through sqlite,
trajectories are hand-written in the agent_demo/agent.py shape mirroring the
reviewer's real Playwright walkthroughs):

```bash
cd agent_demo && uv run python -m pytest ../sites/ohiomeansjobs/verify/tests -q
# 102 passed
```

Coverage per task: honest PASS, no-op FAIL, wrong-answer FAIL, shortcut FAIL;
read-only tasks FAIL on a mutated after-DB; stateful tasks FAIL on a
state-mismatch (clean DB) and on a wrong delta; package tampering (task_id
mismatch, off-site URL, missing screenshot, non-done trajectory, tampered
seed) fails closed. The contributor's own 35-test suite stays green.

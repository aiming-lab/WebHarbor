# Contributing to WebHarbor

Thanks for being here. WebHarbor lives across two repositories on purpose:

- **`webharbor`** (this repo, GitHub) — code: per-site Flask apps, control plane, scripts, Dockerfile.
- **`ChilleD/WebHarbor`** (Hugging Face dataset, https://huggingface.co/datasets/ChilleD/WebHarbor) — heavy assets: `instance_seed/*.db`, `static/images/`, `static/external_cache/` for every site.

A non-trivial change usually touches both. The workflow below makes that straightforward.

## Two roles

WebHarbor splits work across two roles on purpose:

- **Contributor** — builds the site: the Flask app, seed DB, assets, and the task list (`tasks.jsonl`). A contributor's `tasks.jsonl` rows carry only the task definition: `web_name, id, ques, web, upstream_url`. The contributor does **not** write verifiers, rubrics, or any answer key.
- **Reviewer** — validates the contribution: checks site quality (mechanical + functional), checks that each task is **feasible** (actually solvable by navigating the site, and not trivially answerable from an LLM's prior knowledge), and then writes the **grading contract** — a deterministic verifier per task plus a `judge_rubric`, recorded back into `tasks.jsonl` as `verifier_path` + `judge_rubric`.

Workflows A and B below are the **contributor's** job. The **Reviewer role** section later in this file is the reviewer's job. The split keeps ground truth out of the agent-facing file (a contributor's `tasks.jsonl` never contains answers) and puts grading rigor where it belongs — with the person checking the work.

## TL;DR

```bash
# fork github.com/webharbor/webharbor + huggingface.co/datasets/ChilleD/WebHarbor
git clone https://github.com/<you>/webharbor && cd webharbor
./scripts/fetch_assets.sh                       # pull current assets
./scripts/new_site.py mywebsite                 # OR edit an existing site
./scripts/build.sh && docker run -d --rm \
  -p 8101:8101 -p 40000-40016:40000-40016 webharbor:dev
# iterate locally...

./scripts/extract_assets.sh ../webharbor-static-pr/   # split assets out
cd ../webharbor-static-pr
hf upload-large-folder <your-fork>/WebHarbor . --repo-type dataset
# open PR on HF first → grab the merge sha
cd ../webharbor
echo "revision: <hf-merge-sha>" > .assets-revision
git commit -am "feat(mywebsite): add site + bump assets to <sha>"
gh pr create
```

## Workflow A — add a brand-new site

We aim for 100 sites; new ones are very welcome. A "site" is a self-contained Flask app under `sites/<name>/` that mirrors a real website's behavior closely enough that an agent which works on the real site also works here.

### 1. Pick a port slot

`websyn_start.sh` lists `SITES=(...)` in port order; the new site goes on `40000 + index`. Add it to:

- `websyn_start.sh` — the `SITES=( ... )` array
- `control_server.py` — the `SITES = [ ... ]` list (must match exactly)
- `Dockerfile` — `EXPOSE 8101 40000-N` if you push the upper bound

### 2. Scaffold

```bash
./scripts/new_site.py mywebsite
```

This creates `sites/mywebsite/` with the standard skeleton:

```
mywebsite/
├── app.py              ← edit this
├── _health.py
├── requirements.txt    ← only Flask by default
├── templates/index.html
├── static/{css,js,icons,images,external_cache}/
├── instance_seed/      ← drop your seed DB here as <name>.db
├── instance/           ← gitignored, recreated at boot
└── scraped_data/       ← gitignored, build-time only
```

### 3. Build the seed DB

The DB is the **single source of runtime data**. Everything an agent sees at request time should come from here. Anti-pattern: reading JSON files at request handler time.

A typical seed flow:

1. Define SQLAlchemy models in `app.py` (User, Product, Article, ...)
2. Write a `seed_data.py` that materializes a dataset into the DB. Make the function **idempotent** — `if Foo.query.count() > 0: return` at the top.
3. Run once locally to produce `instance/<name>.db`.
4. Copy it to `instance_seed/<name>.db`. **This is your seed.**

### 4. Functional checklist

Each route should:

- Return 200 on the happy path.
- Render *non-empty* content (no blank pages).
- Use links / forms / buttons that are reachable from `/`. WebHarbor agents click their way around — orphan pages are a smell.

If your site has multiple categories / pages / topics, make sure the seed DB has enough rows in each that filters / pagination / search look plausible (≥ ~20 records per major filter).

### 5. Test interactively

```bash
./scripts/build.sh
docker run -d --rm --name wh-test \
  -p 8101:8101 -p 40000-400NN:40000-400NN webharbor:dev

# the new site should be on port 40000+i
curl -so /dev/null -w "%{http_code}\n" http://localhost:400NN/
curl -X POST http://localhost:8101/reset/mywebsite

# make sure /reset/mywebsite keeps the DB byte-identical to the seed
docker exec wh-test md5sum \
  /opt/WebSyn/mywebsite/instance/<name>.db \
  /opt/WebSyn/mywebsite/instance_seed/<name>.db
# both md5s MUST match — see "Idempotent seeding" below
```

### 6. Write the tasks (`tasks.jsonl`)

Add one JSON line per task to `sites/<site>/tasks.jsonl`. The contributor writes ONLY these keys:

```json
{"web_name": "My Site", "id": "My Site--0", "ques": "...", "web": "http://localhost:4000N/", "upstream_url": "https://realsite.com/"}
```

- `id` is `"<SiteName>--<N>"` (0-indexed, matches the `web_name`).
- `ques` is the natural-language task the agent must perform by navigating the mirror.
- `web` is the mirror base URL (the in-container port `40000 + index`).
- `upstream_url` is the real site being mirrored.
- **For login tasks, put the demo account credentials directly in `ques`** (e.g. `"Log in with the demo account (email: alice.j@test.com, password: TestPass123!), then ..."`) so an autonomous agent can log in.

Do NOT add `verifier_path`, `judge_rubric`, or any `answer` key — those are the **reviewer's** to add (see "Reviewer role"). Ground truth never lives in this file because the agent reads it.

Design tasks to be **feasible and meaningful**: each must be solvable by navigating the site, and ideally should require reading a page-specific fact an LLM can't recall from memory (exact dates/IDs, on-page wording, a specific row) rather than general knowledge. The reviewer will reject tasks that are trivially answerable from prior knowledge or ill-posed for autonomous evaluation.

### 7. Open the two PRs

The HF dataset stores one `<site>.tar.gz` per site (avoids the small-file
stall on `hf download` for 4000+ images). `extract_assets.sh` packs your
site into a single tarball; upload just that one file.

```bash
./scripts/extract_assets.sh ../wh-static-pr/ mywebsite
cd ../wh-static-pr
hf upload mywebsite.tar.gz <your-fork>/WebHarbor mywebsite.tar.gz --repo-type dataset
# Then open a PR on https://huggingface.co/datasets/ChilleD/WebHarbor
# After it's merged, copy the merge commit sha.

cd ../webharbor
# bump the pin
sed -i "s/^revision:.*/revision: <hf-merge-sha>/" .assets-revision
git add .
git commit -m "feat(mywebsite): add new site

Adds Flask app, templates, and seed DB for <real-site-name>.
Assets uploaded to HF as mywebsite.tar.gz; .assets-revision bumped to <sha>."
gh pr create --title "feat(mywebsite): add new site"
```

GitHub PR description should include:

- Real site mirrored + URL
- Number of seeded rows per major model
- Link to the HF PR (the asset side)
- Output of `curl -X POST .../reset/mywebsite` showing `ready: true`

## Workflow B — update assets on an existing site

Common case: you replaced 50 product images, or refreshed an instance_seed DB.

```bash
git checkout -b update-amazon-imgs
# put new files in sites/amazon/static/images/ or sites/amazon/instance_seed/
./scripts/build.sh && docker run ...   # smoke test

./scripts/extract_assets.sh ../wh-static-pr/ amazon       # pack only amazon
cd ../wh-static-pr
hf upload amazon.tar.gz <your-fork>/WebHarbor amazon.tar.gz --repo-type dataset
# (single-file upload keeps the PR scoped to one site)
```

Open the HF PR; once merged, bump `.assets-revision` in this repo and open the GitHub PR. CI on the GitHub PR will fail-closed if the pinned revision isn't reachable.

## Reviewer role — validate the site and grade the tasks

The reviewer picks up a contributor's PR (site + `tasks.jsonl` with the basic keys) and does two things: **(A) validate site quality and task feasibility**, then **(B) add the grading contract** (verifier + `verifier_path` + `judge_rubric`). Only after both pass should the PR merge.

### A. Validate site quality and task feasibility

Build the image from the branch and run it on alt ports (see AGENTS.md "Pre-PR checks" for the exact commands). Then:

1. **Mechanical** — every site returns 200; `/health` all alive; `POST /reset/<site>` wipes runtime writes and restores the DB **byte-identical** to the seed (`md5(instance) == md5(instance_seed)`); `reset-all` completes in ~1s.
2. **Functional** — drive the site's routes (auth, search, list/detail, any stateful action) and confirm each renders correct, non-empty content. The contributor's tasks must be genuinely completable on these pages.
3. **Task feasibility** — for each task in `tasks.jsonl`, confirm it is **solvable by navigating the site** and is **not trivially answerable from an LLM's prior knowledge**. Drive a few tasks end-to-end (manually or with `agent_demo/agent.py`). Reject — and send back to the contributor — tasks that:
   - can be answered without ever opening the site (e.g. a common dictionary definition),
   - are ill-posed for autonomous evaluation (e.g. "ask me which one" presupposing a human in the loop),
   - have no stable, verifiable answer (e.g. a "today" value that rotates by run date),
   - or are mechanically trivial / non-deterministic in a way that defeats grading (e.g. a quiz score the agent can't be graded on).

The `merriam_webster` review is the reference example of this step: several original tasks were rejected as knowledge-shortcuts / human-in-the-loop / date-dependent and re-anchored onto page-specific facts.

### B. Add the grading contract (verifier + rubric)

For each task the reviewer accepts, the reviewer writes the grading artifacts and records them in `tasks.jsonl`:

1. **A deterministic verifier** — one Python script per task, placed under the **site's own** `sites/<site>/verify/` directory (so each site is self-contained; verifiers never live under `agent_demo/`). It emits a binary PASS/FAIL from the run signature `(initial_state, after_state, trajectory, agent final output)`. Deterministic-first (navigation / regex / token / SQLite after-state); LLM only as an anchored utility. The ground truth is **HARDCODED inside the verifier** — never in `tasks.jsonl` (the agent reads that file; an answer key there leaks answers). See `sites/merriam_webster/verify/verify_lib.py` for the shared utilities (`load_run`, `navigated_to`, `llm_text_match`, `llm_screenshot_shows`, SQLite helpers, the `Judge` harness) and `sites/merriam_webster/verify/verify_*.py` for one-per-task examples.
2. **`verifier_path`** in the task row — the relative path (from repo root) to that verifier, e.g. `sites/merriam_webster/verify/verify_0.py`.
3. **`judge_rubric`** in the task row — a short English block of "FACT CHECKPOINTS" the LLM judge verifies (which pages the agent MUST have opened, which facts/answers MUST appear, that an empty answer is a FAIL). The rubric states the *rules*, not the answers, so it's safe for the agent to see.

After the reviewer's pass, `tasks.jsonl` has these keys: `web_name, id, ques, web, upstream_url, verifier_path, judge_rubric`. There is **no `answer` key**. Sites whose tasks predate this contract may omit `verifier_path` and `judge_rubric` (both optional); `agent.py` and `eval_judge.py` handle their absence gracefully.

### C. Verify the grading itself

The reviewer confirms the grading contract is sound before merge:

- A **no-op run** (agent opens the homepage, does nothing, empty answer, clean DB) makes **every** verifier return FAIL (exit 1) — no false positives.
- A **PASS case** (drive a task to completion correctly) makes its verifier pass; a **shortcut case** (correct answer but no on-site navigation) and a **wrong-answer case** both FAIL — proving the verifier can't be fooled.
- For stateful tasks, a **state-mismatch case** (agent self-reports success but the DB is unchanged) FAILs on the DB check.
- The **LLM judge** appends a rubric-specific system-prompt block (and emits `rubric_checkpoints`) ONLY for tasks with a non-empty `judge_rubric`; tasks without one get the plain base prompt.

Why two graders: an LLM-as-judge alone is gullible — a plausible-but-wrong answer, or a correct answer recalled from memory with no page visit, can pass. The deterministic verifier catches both (wrong-answer via ground-truth match; knowledge-shortcut via the navigation check). The rubric makes the LLM judge stricter and more consistent. The verifier is the **primary** grader; the rubric-driven LLM judge is secondary/lenient. Both are invoked through the single `agent_demo/eval_judge.py` entry point (`--verifier True` for the verifier, default for the LLM judge). See `sites/merriam_webster/verify/README.md` and the `merriam_webster` site for a worked example (20 tasks, 20 verifiers + `verify_lib.py`).

### Unified LLM config (agent, judge, verifiers)

All three tools read the same env vars (CLI flags override):

| env var | meaning |
|---------|---------|
| `OPENAI_API_KEY` | bearer token for the OpenAI-compatible endpoint |
| `OPENAI_BASE_URL` | base URL of that endpoint |
| `JUDGE_MODEL` | model id used by BOTH the agent, the LLM judge, and the verifier LLM utilities |

Run an agent task and grade it (reviewer validation loop):

```bash
export OPENAI_API_KEY=...  OPENAI_BASE_URL=http://api.openai.com/v1  JUDGE_MODEL=GPT-5
# agent (writes trajectory.json + screenshots/, carries judge_rubric in)
uv run python agent_demo/agent.py --tasks_file sites/<site>/tasks.jsonl \
       --task_id "<site>--N" --url http://localhost:40000+i/ --out_dir runs/x
# deterministic verifier (primary grader) — run via eval_judge's verifier mode
uv run python agent_demo/eval_judge.py --run_dir runs/x --verifier True
# LLM judge (secondary, rubric-driven) — default mode
uv run python agent_demo/eval_judge.py --run_dir runs/x
```

Note: the tools use `simpleArgParser`, so **boolean flags take a value** (`--no_llm True`, `--headless False`), not a bare flag.

## Code conventions

These exist because we got bitten:

### Idempotent seeding (very important)

Every `seed_database()` (and any `seed_*()` helpers called at module import time inside `with app.app_context():`) **must early-return when the DB is already populated**. The pattern is:

```python
def seed_database():
    if Partner.query.count() > 0:
        return
    # ... rest of seed
```

Per-row gates are not enough: the bare act of opening a SQLAlchemy session and committing zero changes still bumps SQLite metadata, which breaks `/reset/<site>` byte-identity. See `feedback_seed_stabilization` in the project history for the war story.

If you have *multiple* seed phases (`seed_database`, `seed_benchmark_users`, `seed_extras`), gate **each** of them. After a fresh seed, re-running the boot path should be a no-op. Test with:

```bash
docker exec wh-test md5sum /opt/WebSyn/<site>/instance{,_seed}/<site>.db
# must match
docker restart wh-test && sleep 5
docker exec wh-test md5sum /opt/WebSyn/<site>/instance{,_seed}/<site>.db
# must STILL match
```

### Runtime data lives in `instance_seed/*.db`, not in JSON

Anything an HTTP handler reads should come from SQLite, not from a JSON file under `scraped_data/`. We ran into this with `bbc_news`: gallery data lived in `scraped_data/article_galleries.json`, the request handler read it on every page view, and the JSON was redundant with the DB.

If you have intermediate scrape data, that goes in `scraped_data/` (gitignored, dockerignored). Once you've written a `seed_*` function that turns it into DB rows, the JSON is build-time only.

### One Flask process per site, no shared state across sites

Sites must not import from one another. The image launches each as an independent process; sharing breaks isolation and makes `/reset/<site>` non-atomic from the perspective of other sites.

### Don't hard-code secrets

Each site sets `SECRET_KEY` to a deterministic dev value. Acceptable for a benchmark image (resets blow away sessions anyway). If a contrib ever needs real secrets, raise it in an issue first.

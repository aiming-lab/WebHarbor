# WebHarbor — agent guide

A coding agent (Claude Code, Cursor, Aider, Codex, ...) is reading this. Read once, then act.

## What it is

15 Flask mirror websites (Amazon, GitHub, BBC News, ...) packaged into one Docker image, plus a control plane on `:8101` for resetting per-site state. Used as a deterministic offline environment for web-agent benchmarks. ~3 GB image.

Two repos:
- **code** (this one) — Flask apps, control plane, scripts.
- **assets** (`ChilleD/WebHarbor` HF dataset) — one `<site>.tar.gz` per site, each bundling that site's `instance_seed/*.db`, `static/images/`, and `static/external_cache/`. Pulled via the `hf download` CLI and unpacked into `sites/<site>/`.

## Tech stack

- Python 3.12 (`python:3.12-slim-bookworm`)
- Flask 3.1, SQLAlchemy 2.0, Werkzeug 3.1, Pillow 11
- SQLite per site
- Docker (single image, no compose)

## Layout

```
sites/<site>/
├── app.py                       routes + SQLAlchemy models
├── seed_data.py                 build-time seed
├── templates/                   Jinja
├── static/{css,js,icons}/       small UI, in git
├── static/images/               heavy, in HF dataset
├── static/external_cache/       optional, in HF dataset
└── instance_seed/<site>.db      seed DB, in HF dataset

control_server.py                :8101 control plane
site_runner.py                   per-site supervisor (setsid + killpg)
websyn_start.sh                  container entrypoint
Dockerfile
.assetpaths                      paths managed via HF
.assets-revision                 pins HF dataset repo + revision
scripts/{fetch,extract,check}_assets.sh
scripts/build.sh
scripts/new_site.py
```

Inside the image, sites live at `/opt/WebSyn/<site>/`. The path predates the rename to webharbor and is kept stable.

## Bring it up

```bash
# fresh clone
./scripts/fetch_assets.sh                     # pulls assets from HF
./scripts/build.sh                            # docker build -t webharbor:dev .
docker run -d -p 8101:8101 -p 40000-40015:40000-40015 webharbor:dev
```

Or use the published image directly:

```bash
docker run -d -p 8101:8101 -p 40000-40015:40000-40015 \
  battalion7244/webharbor:latest
```

Sites are on `40000`-`40015` in the order declared by `SITES=( ... )` in `websyn_start.sh`. Control plane:

| Method | Path                | Purpose                                   |
|--------|---------------------|-------------------------------------------|
| GET    | `/health`           | per-site PID + alive                      |
| POST   | `/reset/<site>`     | wipe `instance/`, restore from seed, respawn |
| POST   | `/reset-all`        | parallel reset of every site              |
| POST   | `/restart/<site>`   | respawn process; **DB not reset**         |

## Add a new site

```bash
./scripts/new_site.py mysite       # scaffolds sites/mysite/
# edit sites/mysite/{app.py, templates/, static/}
# put seed DB in sites/mysite/instance_seed/mysite.db
# put images in sites/mysite/static/images/
```

Register the site in **three places** (must stay in sync):

1. `websyn_start.sh` — `SITES=( ... )` (port = 40000 + index)
2. `control_server.py` — `SITES = [ ... ]`
3. `Dockerfile` — `EXPOSE 8101 40000-N` (raise N if needed)

Then run the [pre-PR checks](#pre-pr-checks).

## Run an agent against a mirror (`agent_demo/`)

A minimal browser-use ReAct loop (`agent.py`) plus an LLM-as-judge grader (`eval_judge.py`) live under `agent_demo/`. Useful for smoke-testing a mirror end-to-end the way a real WebVoyager agent would, or as a starting template.

```bash
cd agent_demo
uv sync
uv run playwright install chromium               # one-time
export OPENAI_API_KEY=...                        # API key + base URL via env, never hardcoded
export OPENAI_BASE_URL=https://api.openai.com/v1
```

Run a task from a site's `tasks.jsonl` (the format is `{web_name, id, ques, web, upstream_url}` per line). The agent reads `--task` / `--url` either inline or from `--tasks_file [--task_id ID]`:

```bash
# pick a specific task
uv run python agent.py --tasks_file ../sites/google_search/tasks.jsonl \
                       --task_id "Google Search--0" --out_dir runs/gs0

# ad-hoc inline task
uv run python agent.py --task "Find Kevin Durant's bio" \
                       --url http://localhost:40009/ --out_dir runs/inline
```

Each run writes `trajectory.json` + `screenshots/step_NNN.png`. Then grade:

```bash
uv run python eval_judge.py --run_dir runs/gs0
```

`eval.json` lands next to the trajectory with `success` / `confidence` / `rationale` / `evidence`. See `agent_demo/README.md` for full CLI flags.

## Pre-PR checks

Run all of these before opening a PR.

```bash
# 1. syntax
python3 -m py_compile sites/<site>/app.py

# 2. build
./scripts/build.sh webharbor:dev

# 3. run on alt ports (don't collide with anything you already have running)
docker run -d --rm --name wh-test \
  -p 8201:8101 -p 41000-41015:40000-40015 webharbor:dev

# 4. control plane healthy, all sites alive
curl -s http://localhost:8201/health | python3 -m json.tool | head

# 5. every site renders 200
for p in $(seq 41000 41014); do
  curl -so /dev/null -w "$p:%{http_code}\n" http://localhost:$p/
done

# 6. byte-identical reset (the strict invariant)
curl -X POST http://localhost:8201/reset/<your_site>
docker exec wh-test md5sum \
  /opt/WebSyn/<your_site>/instance/<your_site>.db \
  /opt/WebSyn/<your_site>/instance_seed/<your_site>.db
# the two md5s MUST match — if not, see "Idempotent seeding"

# 7. teardown
docker stop wh-test
```

If you changed an HTTP handler, also `curl` the affected route before and after your change and diff the responses (CSRF tokens differ each request, ignore those).

## Code style

- Python 3.12 syntax welcome (PEP 604 unions, match, etc.); don't drop below 3.10 syntax
- 4-space indent, no tabs; snake_case for funcs/vars, PascalCase for SQLAlchemy models
- Each site is **self-contained**: no imports across `sites/<site>/` boundaries
- Path references go through `BASE_DIR = os.path.dirname(os.path.abspath(__file__))`; no hard-coded absolute paths
- Lock dependency versions in `Dockerfile`'s pip install — the image must be reproducible

## Critical rules (do not violate)

### Idempotent seeding

Module-level seed code runs at every container boot and every `/reset/<site>`. Each seed function must early-return on populated DB:

```python
def seed_database():
    if Foo.query.count() > 0:
        return
    # ...

def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    # ...

with app.app_context():
    db.create_all()
    seed_database()         # idempotent at the function level
    seed_benchmark_users()  # also gated
```

Per-row gates aren't enough — even a no-op `db.session.commit()` bumps SQLite metadata and breaks `/reset/<site>` byte-identity. Gate every seed function as a whole.

### Runtime data lives in `instance_seed/*.db`, not JSON

HTTP handlers must read from SQLAlchemy, not from `scraped_data/*.json`. If you have intermediate scrape JSON, fold it into `instance_seed/<site>.db` at build time via `seed_data.py`. The `scraped_data/` dir is gitignored + dockerignored — never shipped.

### Sites are isolated

No cross-imports between `sites/<a>/` and `sites/<b>/`. Image runs one Python process per site; cross-imports break that isolation and `/reset/<site>` atomicity.

### Two places stay in sync when changing assets

`.assetpaths` (which dirs are HF-managed) and `.gitignore` (those same dirs are not committed) — change both together. `.dockerignore` does NOT ignore the asset paths because they must ship into the image.

## Common debugging

| Symptom                             | Likely cause                              | Where to look                              |
|-------------------------------------|-------------------------------------------|--------------------------------------------|
| Site won't start                    | `seed_database` raises on import          | `/tmp/websyn_<site>.log` inside container  |
| `/reset` hangs ~60s                 | killpg missed; not a session leader       | `os.setsid()` in `site_runner.py`          |
| `/reset` returns but DB still dirty | Popen handle leaked; zombie not reaped    | `_site_procs` dict in `control_server.py`  |
| Byte-identity fails post-reset      | seed not fully idempotent                 | gate every `seed_*()` function             |
| Image bloats > 4 GB                 | shipped `scraped_data/` or `instance/`    | `.dockerignore`                            |

## When you finish

Report what you actually verified, not what you intended to verify. The [pre-PR checks](#pre-pr-checks) above are the bar.

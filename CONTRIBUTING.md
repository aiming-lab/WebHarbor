# Contributing to WebHarbor

Thanks for being here. WebHarbor lives across two repositories on purpose:

- **`webharbor`** (this repo, GitHub) — code: per-site Flask apps, control plane, scripts, Dockerfile.
- **`ChilleD/WebHarbor`** (Hugging Face dataset, https://huggingface.co/datasets/ChilleD/WebHarbor) — heavy assets: `instance_seed/*.db`, `static/images/`, `static/external_cache/` for every site.

A non-trivial change usually touches both. The workflow below makes that straightforward.

## TL;DR

```bash
# fork github.com/webharbor/webharbor + huggingface.co/datasets/ChilleD/WebHarbor
git clone https://github.com/<you>/webharbor && cd webharbor
./scripts/fetch_assets.sh                       # pull current assets
./scripts/new_site.py mywebsite                 # OR edit an existing site
./scripts/build.sh && docker run -d --rm \
  -p 8101:8101 -p 40000-40015:40000-40015 webharbor:dev
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

### 6. Open the two PRs

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

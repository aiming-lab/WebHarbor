---
name: seed-database
description: "Phase 5: Finalize the seed DB and ship the asset side of the change. Covers idempotent seeding (the byte-identical reset invariant), benchmark test users, scored search, and the two-repo workflow: code goes to github.com/aiming-lab/WebHarbor, heavy assets (instance_seed DBs, static/images) go to huggingface.co/datasets/ChilleD/WebHarbor, then .assets-revision pins them together."
---

# Seed Database — Final Stabilization & Asset Workflow

## When to use

- Finalizing a mirror before opening PRs
- After harden-env when DB / image changes need to be persisted
- When debugging "byte-identical reset failed" issues

## Layout reminder

`instance_seed/*.db` and `static/images/` for every site are stored in the
HuggingFace dataset `ChilleD/WebHarbor`, NOT directly in git.
`.assetpaths` in this repo lists which paths are HF-managed; `.gitignore`
keeps them out of git; `.dockerignore` does NOT ignore them (they must ship
in the image).

`.assets-revision` pins the exact HF dataset commit the image was built
against. Bumping this file is the final step of any change that touches
seed DBs or images.

## Seeding requirements

### 1. Idempotent seed functions (the byte-identical reset invariant)

Every `seed_*()` function in `app.py` or `seed_data.py` MUST early-return
when the DB is already populated:

```python
def seed_database():
    if Product.query.count() > 0:
        return                    # ← gate the WHOLE function
    # ... seed rows ...

def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    # ... seed 4 users ...

with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()
```

**Per-row gates are NOT enough.** Even a no-op `db.session.commit()` bumps
SQLite metadata, breaking `/reset/<site>` byte-identity. Gate every seed
function as a whole.

Diagnose with:

```bash
docker exec wh-test md5sum \
  /opt/WebSyn/<site>/instance/<site>.db \
  /opt/WebSyn/<site>/instance_seed/<site>.db
# must match

docker restart wh-test && sleep 5
docker exec wh-test md5sum \
  /opt/WebSyn/<site>/instance/<site>.db \
  /opt/WebSyn/<site>/instance_seed/<site>.db
# must STILL match
```

### 2. Benchmark test users

Seed exactly 4 users:

```python
USERS = [
    {'username': 'alice_j', 'email': 'alice.j@test.com', 'display_name': 'Alice Johnson'},
    {'username': 'bob_c',   'email': 'bob.c@test.com',   'display_name': 'Bob Chen'},
    {'username': 'carol_d', 'email': 'carol.d@test.com', 'display_name': 'Carol Davis'},
    {'username': 'david_k', 'email': 'david.k@test.com', 'display_name': 'David Kim'},
]
PASSWORD = 'TestPass123!'
```

Each should have pre-existing:
- Cart/bag items (2-4)
- Bookmarks/favorites/saved items (3-6)
- Order history (1-3 past orders)
- Profile with address & payment method (for checkout tasks)

### 3. Realistic catalog volume

| Entity | Min seed count | Why |
|---|---|---|
| Primary (products, articles, courses) | 50-200 | Realistic browse/search |
| Categories/sections | 5-15 | Real-site taxonomy |
| Reviews per popular item | 3-10 | Detail pages feel populated |

### 4. Scored search (NEVER strict AND)

Multi-word queries like "Boston Celtic players" fail strict matching.
Use token-overlap scoring:

```python
import re

STOP_WORDS = {'the','a','an','in','on','at','to','for','of','and','or','is','it','by','with'}

def scored_search(query, items, fields=['name','description']):
    tokens = [t.lower() for t in re.split(r'\W+', query)
              if t.lower() not in STOP_WORDS and len(t) > 1]
    if not tokens:
        return items
    results = []
    for item in items:
        text = ' '.join(getattr(item, f, '') or '' for f in fields).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            results.append((item, score))
    results.sort(key=lambda x: -x[1])
    return [r[0] for r in results]
```

### 5. Runtime data lives in the seed DB, not JSON

HTTP handlers must read from SQLAlchemy, not from `scraped_data/*.json`.
If you have intermediate scrape JSON, fold it into `instance_seed/<site>.db`
at build time via `seed_data.py`. `scraped_data/` is gitignored and
dockerignored — never shipped.

### 6. Date pinning

If tasks reference relative dates ("order placed 3 days ago"), pin a
reference date:

```python
MIRROR_REFERENCE_DATE = datetime(2026, 4, 15)
# Replace all datetime.utcnow() with this constant in seed scripts
```

## Asset-side workflow: ship to HuggingFace

After all DB/image changes are stable, push the heavy assets to HF:

```bash
# 1. Split assets out of this repo into a staging directory
./scripts/extract_assets.sh ../wh-static-pr/

# 2. Review the diff in the HF web UI before uploading
cd ../wh-static-pr
hf upload-large-folder <your-fork>/WebHarbor . --repo-type dataset

# 3. Open a PR on https://huggingface.co/datasets/ChilleD/WebHarbor
# 4. After it's merged, grab the merge commit SHA.

# 5. Back in the code repo, bump the pin:
cd ../webharbor
sed -i "s/^revision:.*/revision: <hf-merge-sha>/" .assets-revision

# 6. Commit + open the GitHub PR (referencing the HF PR)
git commit -am "feat(<site>): add new site

Adds Flask app, templates, and seed DB for <real-site-name>.
Assets uploaded to HF; .assets-revision bumped to <sha>."
gh pr create
```

## Final verification

```bash
./scripts/check_assets.sh                       # every site has instance_seed/
./scripts/build.sh webharbor:dev                # docker build succeeds
docker run -d --rm --name wh-test \
  -p 8201:8101 -p 41000-41014:40000-40014 webharbor:dev

# all 15 sites return 200
for p in $(seq 41000 41014); do
  curl -so /dev/null -w "$p:%{http_code}\n" http://localhost:$p/
done

# parallel reset under 10s
time curl -X POST http://localhost:8201/reset-all

# byte-identity for every site
for s in allrecipes amazon apple arxiv bbc_news booking github \
         google_flights google_map google_search huggingface \
         wolfram_alpha cambridge_dictionary coursera espn; do
  docker exec wh-test md5sum \
    /opt/WebSyn/$s/instance/$s.db \
    /opt/WebSyn/$s/instance_seed/$s.db
done

docker stop wh-test
```

## Output

After Phase 5:
- `sites/<site>/instance_seed/<site>.db` is a stable, idempotent seed
- All 4 benchmark users exist with pre-populated data
- Scored search returns diverse results
- HF dataset PR opened and merged
- `.assets-revision` bumped to the HF merge SHA
- Both GitHub and HF PRs cross-reference each other

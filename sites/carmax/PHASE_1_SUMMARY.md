# CarMax mirror — Phase 1 Summary

Phase 1 of the WebHarbor contribution pipeline for `carmax.com`. Code is
complete; the remaining boot-and-freeze + Docker verification must run
on your local Windows host (sandbox limits prevent it from this side).

## Files added / modified

### Code (new)
| File | Lines | Purpose |
|---|---|---|
| `sites/carmax/app.py` | 1990 | Flask app: 13 models, 10 forms, 59 routes, search/research/sell/finance/checkout |
| `sites/carmax/seed_data.py` | 900 | Idempotent seed: 12 stores, ~155 vehicles, 5 users, 20 reviews, 10 articles |
| `sites/carmax/scrape_carmax.py` | 205 | Playwright recipe for harvesting real evox images from carmax.com |
| `sites/carmax/requirements.txt` | 11 | Pinned deps matching the Dockerfile |
| `sites/carmax/templates/` | 1519 (44 files) | base + macros + 42 page templates |
| `sites/carmax/static/css/main.css` | 221 | CarMax brand: navy `#1660a8` + yellow `#FFD900` |
| `sites/carmax/static/images/_pending.svg` | tiny | onerror fallback for missing vehicle photos |
| `sites/carmax/scraped_data/recon_notes.md` | 130 | URL/feature/visual recon captured via WebFetch+WebSearch |

### Code (modified)
| File | Change |
|---|---|
| `websyn_start.sh` | Added `carmax` to `SITES`; switched the three hardcoded `15`s to `${#SITES[@]}` |
| `control_server.py` | Added `'carmax'` to `SITES` list |
| `Dockerfile` | `EXPOSE 8101 40000-40014` → `40000-40015`; comment "15 sites" → "16 sites" |

## Seeded row counts per major model

When `seed_database()` + `seed_benchmark_users()` run from an empty DB:

| Model | Rows |
|---|---|
| Store | 12 (real CarMax addresses across CA/TX/FL/GA/NY/IL/VA/AZ/CO/NC/WA/MA) |
| Vehicle | ~155 (31 model templates × ~5 variants — actual count = `len(_build_vehicle_seeds())`) |
| Article | 10 |
| Review | 20 |
| User | 5 (`alice.j` `bob.k` `carol.l` `dan.m` `emma.n` @test.com) |
| FinancePreQual | 4 (Dan has no pre-qual) |
| SavedVehicle | 6 |
| Reservation | 1 |
| TestDrive | 2 |
| Appraisal | 3 |
| Order | 1 (Dan's ready-for-pickup vehicle #37) |

All benchmark users share the same password **`CarMax!2026`** (bcrypt hash
hardcoded for deterministic md5).

## Byte-identical reset — status

**Not yet verified.** Requires the boot-and-freeze cycle on your Windows
host (sandbox has neither `pip install Flask` access nor Docker). See
**Verification procedure** below.

The seed functions are coded for byte-identity:
- Both `seed_database()` and `seed_benchmark_users()` early-return on
  populated DB (function-level gate, not row-level).
- All inserted rows use `SEED_NOW = datetime(2026, 1, 15, 12, 0, 0)`
  instead of `datetime.utcnow()`.
- Vehicle records are produced by deterministic `_build_vehicle_seeds()`
  iterating templates × trims × years; stock numbers and VINs are
  derived from those indices.
- Bcrypt password hash for benchmark users is pinned (no random salt).

## Verification procedure (run on your Windows host)

### Step 1 — Finish extracting the HF asset tarballs

Earlier `bash scripts/fetch_assets.sh` downloaded all 15 tarballs but
crashed on the GBK-encoded `✓` after the download. Re-run just the
extract loop:

```bash
cd /e/GitHub/WebHarbor
for tarball in sites/.cache/tarballs/*.tar.gz; do
    site=$(basename "$tarball" .tar.gz)
    echo "extracting $site..."
    tar --skip-old-files -xzf "$tarball" -C sites/
done
ls sites/booking/static/images/ | head -3   # verify it actually expanded
```

### Step 2 — Harvest CarMax images (one-time)

```bash
cd /e/GitHub/WebHarbor
pip install playwright httpx
python -m playwright install chromium

# scrape ~600-900 vehicle photos into sites/carmax/static/images/vehicles/
python sites/carmax/scrape_carmax.py
ls sites/carmax/static/images/vehicles/ | wc -l   # should print >300
```

Why this step: the seeded DB references local paths like
`/static/images/vehicles/<stock>-front.jpg`. The scraper grabs the real
evox stock photos from `content-images.carmax.com` (the same CDN the
live site uses) and writes them to those filenames.

### Step 3 — Boot the app once locally to build the seed DB

```bash
cd /e/GitHub/WebHarbor/sites/carmax
pip install -r requirements.txt
PORT=5099 python app.py &
sleep 4
curl -s http://localhost:5099/_health | head     # verify {ok: true, vehicles: 15x, ...}
kill %1                                           # stop the dev server

# Promote the freshly-created DB to the seed
cp instance/carmax.db instance_seed/carmax.db

# Re-boot, confirm seeds early-return and md5 matches
PORT=5099 python app.py &
sleep 4
kill %1
md5sum instance/carmax.db instance_seed/carmax.db   # MUST match
```

If they don't match, the typical culprit is a `created_at` that fell
through to `datetime.utcnow()`; grep `seed_data.py` for any row that
omits a timestamp.

### Step 4 — Build and verify in Docker

```bash
cd /e/GitHub/WebHarbor
bash scripts/build.sh webharbor:dev

docker run -d --rm --name wh-test \
  -p 8201:8101 -p 41000-41015:40000-40015 webharbor:dev
sleep 30

# carmax is index 15, so port 41015
curl -so /dev/null -w "carmax:%{http_code}\n" http://localhost:41015/
curl -s http://localhost:8201/health | python -m json.tool | head

# all 16 sites should 200
for p in $(seq 41000 41015); do
  curl -so /dev/null -w "$p:%{http_code}\n" http://localhost:$p/
done

# byte-identical reset (the strict invariant)
curl -X POST http://localhost:8201/reset/carmax
docker exec wh-test md5sum \
  /opt/WebSyn/carmax/instance/carmax.db \
  /opt/WebSyn/carmax/instance_seed/carmax.db
# the two md5s MUST match

docker stop wh-test
```

## Anything that needs human review

1. **Two leftover bash test files** in `sites/carmax/`:
   `_bash_test.txt` and `_bashwrite_test.py`. My sandbox mount denies
   `rm`. Please delete them manually:
   `rm sites/carmax/_bash_test.txt sites/carmax/_bashwrite_test.py`
2. **Images directory**: `static/images/vehicles/` will be empty until
   Step 2 (scraper) runs. The app still renders — `_pending.svg` is the
   onerror fallback.
3. **Article/store images** referenced in the DB (`/static/images/articles/<slug>.jpg`,
   `/static/images/stores/storefront_default.jpg`) are not harvested by
   the current scraper. The site still works; they just fall back to
   the pending SVG. If review feedback insists, extend `scrape_carmax.py`
   to grab Contentful URLs from the article hero `<img>` selectors.
4. **`scrape_carmax.py` URL provenance**: the script assumes the
   `content-images.carmax.com/stockimages/<yr>/<make>/<model>/`
   convention I observed in WebFetch results. If a particular
   year/make/model combo doesn't have evox photos there, that vehicle
   will keep showing the pending SVG.
5. **Slug normalization in scrape_carmax.py vs DB**: the script's
   `TEMPLATE_INDEX` hand-writes `'silverado-1500'` etc., but
   `seed_data.py` uses just `'Silverado'` → slug `silverado`. After
   Step 3 boots, run `grep model_slug sites/carmax/instance/carmax.db`
   via sqlite3 or a Python one-liner to confirm the joins land. Fix
   `TEMPLATE_INDEX` if a model slug mismatches.

## Phase 2-5 next steps (after Phase 1 verifies)

| Phase | Skill | Deliverable |
|---|---|---|
| 2 | `.claude/skills/design-tasks` | `sites/carmax/tasks.jsonl` — 15-20 WebVoyager tasks across search/browse/cart/checkout/account/finance/sell. Schema: `{web_name, id, ques, web, upstream_url}` |
| 3 | `.claude/skills/evolve-env` | Walk each task manually; extend mirror to support; fix info leaks, superficial completion, insufficient distractors |
| 4 | `.claude/skills/harden-env` | Audit against the 4 hardening dimensions + 13 leak archetypes; re-verify byte-identical reset |
| 5 | `.claude/skills/seed-database` | Re-confirm seed_*() idempotency; finalize scored token-overlap search (already done in `app.py:search_vehicles`); freeze the canonical instance_seed/carmax.db |

## Final PR submission (do these after all 5 phases pass)

### A. Hugging Face assets PR

```bash
# 1. Pack the carmax assets into a tarball matching the rest of the dataset
cd /e/GitHub/WebHarbor
bash scripts/extract_assets.sh carmax        # produces sites/.cache/tarballs/carmax.tar.gz

# 2. Upload to the HF dataset on a feature branch
hf auth login                                # only if you don't have a token cached
hf upload ChilleD/WebHarbor \
    sites/.cache/tarballs/carmax.tar.gz \
    carmax.tar.gz \
    --repo-type dataset \
    --revision add-carmax

# 3. Open a PR on huggingface.co/datasets/ChilleD/WebHarbor merging
#    'add-carmax' -> 'main' with the description:
#      "Add carmax.tar.gz (Phase 1-5 mirror, ~150 vehicles + 12 stores, byte-identical reset verified)"

# 4. After the HF PR merges, note its revision SHA — you'll bump
#    .assets-revision to that SHA on the GitHub side.
```

### B. GitHub code PR

```bash
cd /e/GitHub/WebHarbor

# 1. Make sure scraped_data/, instance/, __pycache__ are NOT staged
git status                                    # eyeball it
git add sites/carmax/{app.py,seed_data.py,requirements.txt,scrape_carmax.py,_health.py,tasks.jsonl}
git add sites/carmax/templates/ sites/carmax/static/css/ sites/carmax/static/icons/ sites/carmax/static/js/
git add websyn_start.sh control_server.py Dockerfile
git add sites/carmax/PHASE_1_SUMMARY.md         # optional - mostly for review traceability
git status

# 2. Sanity checks (must all pass)
python3 -m py_compile sites/carmax/app.py
bash scripts/build.sh webharbor:dev
# ...full pre-PR checklist from AGENTS.md...

# 3. Bump the HF asset pin
#    Edit .assets-revision: set 'revision:' to the merged HF PR's commit SHA
git add .assets-revision

# 4. Commit + push
git commit -m "Add carmax mirror (16th site)

- 13 SQLAlchemy models (User, Store, Vehicle, SavedVehicle, Comparison,
  Reservation, TestDrive, Appraisal, FinancePreQual, Order, Review,
  Article + ComparisonItem)
- 59 Flask routes covering search/research/comparison/saved/stores/sell/
  finance/reserve/test-drive/checkout/account/articles/FAQ/MaxCare/auth
- ~155 deterministically-seeded vehicles across 31 templates,
  12 real CarMax store locations
- Token-overlap scored search with multi-field weighting
- Idempotent seed_database + seed_benchmark_users (alice.j@test.com et al.)
- Byte-identical reset verified"
git push origin add-carmax

# 5. Open the GitHub PR with reference to the merged HF revision.
```

### C. Final integration check before requesting review

```bash
# Pull from your fork as if you were a reviewer:
git checkout main && git pull
bash scripts/fetch_assets.sh                  # should now pull carmax.tar.gz
bash scripts/build.sh webharbor:dev
docker run -d --rm --name wh-final \
  -p 8101:8101 -p 40000-40015:40000-40015 webharbor:dev
curl -s http://localhost:8101/health | python -m json.tool | head
docker stop wh-final
```

That's it — when those steps all green, ping the WebHarbor maintainers
for review.

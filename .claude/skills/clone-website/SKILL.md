---
name: clone-website
description: "Build a new WebHarbor Flask mirror from a real website, with browser-captured source evidence, aligned assets, working interactions, and deterministic seed data. Use for Phase 1 of a website contribution."
---

# Clone Website — Initial Mirror Construction

## When to use

- Starting a new website mirror for WebHarbor
- Phase 1 of the WebHarbor contribution pipeline

## Prerequisites

- The website has been claimed via the tracking sheet and contribution form
- You have a fork of `https://github.com/aiming-lab/WebHarbor` cloned locally
- You have run `./scripts/fetch_assets.sh` to pull current assets from HuggingFace
- You can run Docker locally

## Repo layout (this is the source of truth)

```
sites/<your_site>/
├── app.py              ← Flask app: routes + SQLAlchemy models
├── seed_data.py        ← build-time seed
├── _health.py          ← end-to-end health check
├── requirements.txt    ← Flask + any extras
├── templates/          ← Jinja2 templates
├── static/{css,js,icons}/        ← small UI files, committed to git
├── static/images/                ← heavy, lives in HF dataset
├── static/external_cache/        ← optional, lives in HF dataset
├── instance_seed/<site>.db       ← seed DB, lives in HF dataset
├── instance/                     ← gitignored, recreated on boot
├── scraped_data/                 ← gitignored, build-time only
├── verify/                       ← reviewer-written: one deterministic verifier per task
└── tasks.jsonl                   ← benchmark tasks (jsonl, one per line)
```

Inside the running container sites live at `/opt/WebSyn/<site>/`. The path
predates the rename and is kept stable.

Do not create `README.md`, `CLAUDE.md`, review notes, reports, or one-off harvest
scripts inside `sites/<your_site>/`. A site directory holds code, data, and contract
files only; the only allowed doc file is `NOTICE.md` (third-party attribution).
Write all documentation,
commit messages, and PR descriptions in English. See AGENTS.md ("Per-site directory
structure" and "Documentation and language rules").

## Workflow

### Step 1: Scaffold

```bash
./scripts/new_site.py <your_site>
```

This creates `sites/<your_site>/` with the skeleton above. Register the site
in three places (must stay in sync):

1. `websyn_start.sh` — `SITES=( ... )` array (port = 40000 + index)
2. `control_server.py` — `SITES = [ ... ]` list (exact match)
3. `Dockerfile` — `EXPOSE 8101 40000-N` (raise N if needed)

### Reconnaissance & scraping: drive a real browser with Playwright

Modern target sites (Amazon, Booking, Apple, Coursera, ...) are JS-heavy SPAs / hydrated React apps. `requests.get(url)` returns an empty shell — no products, no images, no cards. Recon and scraping both **must** be done by driving a real Chromium via Playwright (or an equivalent real-browser tool); only that path produces the rendered DOM and the real image URLs the live site actually serves. The `agent_demo/` env already has Playwright + Chromium installed via `uv sync` — reuse it.

Before scraping, define a **Snapshot Contract** for this mirror in a tracked
`sites/<your_site>/provenance.json` manifest (or extend its existing asset manifest):

- `capture_id` and `captured_at`: identify the capture session; record individual capture times when pages are collected at different times
- `locale`, `timezone`, `viewport`: fixed browser settings used for all captures
- `modules`: upstream URLs and relevant state per mirrored page type (`home`, `list`, `detail`, `search`, `auth`, ...), including query/filter state and requested/final URLs when redirects occur
- `evidence`: screenshot/DOM references in the retained review artifacts, linked from the PR; keep these references valid after cleanup

Use the recorded baseline consistently. If a source URL, page state, or design
changes, record the new capture and refresh the affected evidence. This does not
restrict ordinary navigation among entities within a module. Raw captures may
live temporarily in ignored `scraped_data/`; retain the final evidence outside
that scratch directory and keep lightweight provenance in git. Do not record
cookies, tokens, or private account data.

Minimum scraping recipe — render the page, then pull the post-hydration DOM and the resolved image `src` attributes:

```python
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin
import httpx, pathlib

OUT = pathlib.Path("sites/<your_site>/scraped_data")
OUT.mkdir(parents=True, exist_ok=True)
(IMG := OUT / "images").mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://www.example.com/category/phones", wait_until="networkidle")
    page.screenshot(path=OUT / "category_phones.png", full_page=True)
    (OUT / "category_phones.html").write_text(page.content())          # post-JS DOM

    cards = page.eval_on_selector_all(                                  # extract structured data
        "[data-product-card]",
        "els => els.map(e => ({"
        "  name: e.querySelector('.title')?.innerText,"
        "  price: e.querySelector('.price')?.innerText,"
        "  href:  e.querySelector('a')?.href,"
        "  img:   e.querySelector('img')?.src"
        "}))",
    )
    browser.close()

# Fetch the real images at their resolved URLs.
with httpx.Client(follow_redirects=True, timeout=30) as cx:
    for c in cards:
        if not c["img"]: continue
        r = cx.get(c["img"]); r.raise_for_status()
        slug = c["href"].rstrip("/").split("/")[-1]
        (IMG / f"{slug}.jpg").write_bytes(r.content)
```

Things that REQUIRE Playwright (not curl/`requests`):

- Listing pages whose cards are injected client-side (most e-commerce, most modern news)
- Detail pages with lazy-loaded image galleries
- Image URLs that come from a `data-src` / `srcset` resolved by JS
- Sites that require scroll or click to load more (`page.mouse.wheel`, `page.click("button.load-more")`)
- Anything behind a banner / cookie modal that blocks initial render

`requests` / `httpx` are OK **only** for fetching final, resolved asset URLs (the image bytes themselves, the static CSS files) once Playwright has surfaced them. Never use them to fetch the listing HTML.

Map the target's structure from these renders:

- Homepage layout (hero, nav, sidebar, footer, cards)
- Navigation hierarchy (top-level categories, sub-pages)
- URL patterns (`/product/<slug>`, `/category/<slug>`, `/search?q=`)
- Key page types (listing, detail, search results, account, checkout)
- Auth flows (login, register, logout, password reset)
- Forms (search, contact, checkout, review submission)

### Step 3: Asset harvesting

Drive the live site with Playwright (recipe above) and download assets into `scraped_data/` (gitignored, build-time only). Then organize what you keep into `static/`:

- **Product/article images** → `sites/<site>/static/images/` (lives in HF dataset, not committed to git)
- **Brand assets, CSS, JS, icons** → `sites/<site>/static/{css,js,icons}/` (small, committed)

**Critical**: use REAL images from the live site, captured via Playwright + a follow-up `httpx.get` of the resolved URL. Never use placeholders, colored rectangles, AI-generated stock photos, or `requests.get(target_url)` HTML (it returns a JS shell without the image URLs). Multimodal fidelity is a core WebHarbor differentiator and is the #1 reason agents reject reviews.

Apply **Resource Alignment Rules** before seeding:

- Keep entity-level asset mappings in the tracked provenance/asset manifest with at least:
  - `entity_key` (stable id/slug), `title`, `upstream_url`, `image_url`, `local_path`, and the retained file's SHA-256 digest
- Seed rows must join assets by `entity_key` (or another stable key), not by list index position.
- Use the matching upstream image when retrievable. Record unavailable assets and any sourced alternative honestly; do not silently substitute unrelated imagery. Keep attribution in `NOTICE.md`.
- During review, sample-check `title -> image -> upstream_url` triplets for semantic consistency.

### Step 4: Backend build

Edit `sites/<your_site>/app.py`:

```python
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # NEVER hard-code absolute paths
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{BASE_DIR}/instance/<site>.db'
app.config['SECRET_KEY'] = 'webharbor-<site>-dev-key'   # deterministic dev key OK
db = SQLAlchemy(app)
```

Required models (adapt to site type):
- `User` (password hashing, login)
- Primary entity (Product / Article / Course / Recipe / ...)
- Categories, reviews, orders, bookmarks, junction tables

Required routes:
- `/` — homepage
- `/login`, `/register`, `/logout` — auth
- `/account`, `/account/edit` — profile management
- `/search?q=` — search with scored relevance (token-overlap, NOT strict AND)
- `/<entity>/<slug>` — detail pages
- CRUD routes for cart/bookmarks/favorites

### Step 5: Frontend build

Create Jinja2 templates under `sites/<your_site>/templates/`:

- `base.html` — shared layout (header, nav, footer)
- `index.html` — homepage with real content
- `login.html`, `register.html`
- Entity listing & detail templates
- Search results template

Match the original site's color scheme, typography, and navigation. Don't
ship a generic Bootstrap theme.

Enforce **Interactive Parity** for major controls:

- Tabs/chips/filters/sort controls must change content state, not only active CSS class.
- Visible controls must produce meaningful, testable behavior. Client-side behavior is valid for presentation state; persistent actions must save the intended state. Omit unsupported controls or clearly disable them.
- Keep implementation details and grading hints out of user-facing copy. Preserve disclosures needed to understand simulated payments, bookings, prices, or other consequential actions.

### Step 6: Seed data

Edit `sites/<your_site>/seed_data.py` so that `seed_database()` is **idempotent**:

```python
def seed_database():
    if Product.query.count() > 0:
        return                    # ← critical: early-return on populated DB
    # ... seed rows ...

def seed_benchmark_users():
    if User.query.filter_by(email='alice.j@test.com').first():
        return                    # ← gate this function too
    # ... seed 4 benchmark users ...
```

In `app.py`, wire both into the bootstrap:

```python
with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()
```

**Gate every seed function as a whole.** Per-row gates aren't enough: a
no-op `db.session.commit()` still bumps SQLite metadata and breaks the
byte-identical reset invariant.

Then run the site once locally to produce `instance/<site>.db`, copy it to
`instance_seed/<site>.db`. That seed is what ships with the image.

### Step 7: Verify locally

For a new or changed mirror, build from the current checkout and validate the
combined code and pinned assets. Run commands from the repository root in Bash.
Choose an unused container name and host ports; publish only the affected site.
Derive its container port from the current registry rather than copying an old range.

```bash
set -euo pipefail
export WH_REVIEW_SITE=your_site  # replace with the registered site name
WH_REVIEW_CONTAINER=wh-clone-review
WH_REVIEW_CONTROL_PORT=8201     # choose unused host ports
WH_REVIEW_SITE_PORT=41000
export WEBSYN_CONTROL_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

python3 scripts/check_site_registry.py
WH_REVIEW_CONTAINER_PORT="$(python3 - <<'PYPORT'
import os
from scripts.check_site_registry import ROOT, BASE_PORT, parse_start_sites
sites = parse_start_sites(ROOT / "websyn_start.sh")
print(BASE_PORT + sites.index(os.environ["WH_REVIEW_SITE"]))
PYPORT
)"
python3 -m py_compile "sites/$WH_REVIEW_SITE/app.py"
./scripts/fetch_assets.sh
./scripts/build.sh webharbor:dev
docker run -e WEBSYN_CONTROL_TOKEN -d --rm --name "$WH_REVIEW_CONTAINER" \
  -p "127.0.0.1:$WH_REVIEW_CONTROL_PORT:8101" \
  -p "127.0.0.1:$WH_REVIEW_SITE_PORT:$WH_REVIEW_CONTAINER_PORT" webharbor:dev

# Poll authenticated health with a bounded deadline; fail if startup never completes.
WH_REVIEW_CONTROL_URL="http://127.0.0.1:$WH_REVIEW_CONTROL_PORT"
wh_wait_ready() {
  local attempt
  for attempt in {1..120}; do
    if curl -fsS --max-time 5 \
      -H "Authorization: Bearer $WEBSYN_CONTROL_TOKEN" \
      "$WH_REVIEW_CONTROL_URL/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}
wh_wait_ready
curl -fsS --max-time 10 "http://127.0.0.1:$WH_REVIEW_SITE_PORT/" >/dev/null

# Reset restores seed bytes. Adapt the database filename for this site's seed.
wh_assert_seed() {
  docker exec "$WH_REVIEW_CONTAINER" python3 -c \
    'import pathlib, sys; sys.exit(0 if pathlib.Path(sys.argv[1]).read_bytes() == pathlib.Path(sys.argv[2]).read_bytes() else 1)' \
    "/opt/WebSyn/$WH_REVIEW_SITE/instance/$WH_REVIEW_SITE.db" \
    "/opt/WebSyn/$WH_REVIEW_SITE/instance_seed/$WH_REVIEW_SITE.db"
}
curl -fsS --max-time 90 -H "Authorization: Bearer $WEBSYN_CONTROL_TOKEN" \
  -X POST "$WH_REVIEW_CONTROL_URL/reset/$WH_REVIEW_SITE"
wh_assert_seed

# A whole-container restart restores seeds again via websyn_start.sh.
docker restart "$WH_REVIEW_CONTAINER"
wh_wait_ready
wh_assert_seed
```

For each seed database, require byte equality after reset and container startup.
Also test **state preservation** separately: make a persistent change through the
UI, record the saved state, call authenticated `POST /restart/<site>`, require
`ready: true`, and verify that change survives. A site restart must not restore the
seed. Reset the dirty site afterward and repeat the seed-byte comparison. For
SQLite WAL databases, use a consistent snapshot including committed WAL data
when comparing persistent state.

Drive the mirror through Playwright at the selected host port. Compare pages to
the recorded upstream baseline at matching viewport and page state. Retain the
final screenshots and review evidence; do not count HTTP probes as visual checks.

Acceptance gates:

- **Images**: load lazy images by scrolling; require key images to decode (`complete` and `naturalWidth > 0`), and check failed asset requests. HTTP 200 alone is insufficient.
- **Semantics**: sample representative entities on listing and detail pages; verify title, image and destination refer to the same upstream entity.
- **Visuals**: compare the homepage and at least two relevant core page types (or every type if fewer exist); also inspect a narrow viewport. Record and resolve material differences.
- **Interactions**: exercise visible navigation, filters, sorting and forms relevant to the mirror; verify displayed results and saved state, not only active styles.
- **Determinism**: verify seed-byte equality after dirty-state reset and container startup, and saved-state preservation after a site restart.

Run the full image build and registry checks, then focus browser and reset checks
on affected sites. Confirm authenticated health reports every registered site
ready, and keep existing port assignments unchanged. Report exactly which checks
ran and any blockers. After collecting evidence, stop only the owned test container:
`docker stop "$WH_REVIEW_CONTAINER"`.

## Output

After Phase 1, you should have:
- `sites/<your_site>/app.py` with all models, routes, and bootstrap
- `sites/<your_site>/seed_data.py` with idempotent seed functions
- `sites/<your_site>/templates/` with 15+ Jinja2 templates
- `sites/<your_site>/static/` with real CSS/JS/icons (and images under HF assets)
- `sites/<your_site>/instance_seed/<site>.db` with seeded data
- Site registered in `websyn_start.sh`, `control_server.py`, `Dockerfile`
- Global registry checks and authenticated all-site health pass; affected sites render successfully on the chosen host ports
- Byte-identical reset passes
- No `README.md`, reports, or unreferenced one-off scripts left in `sites/<your_site>/`; all docs English

## Next step

Proceed to **design-tasks** (Phase 2) to define `tasks.jsonl` for this mirror.

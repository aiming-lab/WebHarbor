---
name: clone-website
description: "Phase 1: Clone a real website into a local Flask mirror that fits the WebHarbor repo layout. Scaffolds with ./scripts/new_site.py, harvests real assets (images, CSS), builds SQLAlchemy models, generates Jinja2 templates matching the original design, and produces an idempotent seed DB. The result is a runnable site under sites/<name>/ with auth, basic CRUD, and real product/article imagery. Use when starting a new WebHarbor website contribution."
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
└── tasks.jsonl                   ← benchmark tasks (jsonl, one per line)
```

Inside the running container sites live at `/opt/WebSyn/<site>/`. The path
predates the rename and is kept stable.

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

```bash
./scripts/build.sh webharbor:dev
docker run -d --rm --name wh-test \
  -p 8201:8101 -p 41000-41014:40000-40014 webharbor:dev

# your new site is on port 41000 + its index
curl -so /dev/null -w "%{http_code}\n" http://localhost:41000NN/

# byte-identical reset invariant
curl -X POST http://localhost:8201/reset/<your_site>
docker exec wh-test md5sum \
  /opt/WebSyn/<your_site>/instance/<your_site>.db \
  /opt/WebSyn/<your_site>/instance_seed/<your_site>.db
# both md5s MUST match
```

Then drive the mirror through Playwright (same recipe as recon, but pointing at `http://localhost:41000+i/`): screenshot the homepage, one listing page, one detail page, the login flow, and one search. Diff visually against the screenshots you captured in Step 2. If something looks like a coloured rectangle or "Image" alt text, you're missing real assets — go back to Step 3.

## Output

After Phase 1, you should have:
- `sites/<your_site>/app.py` with all models, routes, and bootstrap
- `sites/<your_site>/seed_data.py` with idempotent seed functions
- `sites/<your_site>/templates/` with 15+ Jinja2 templates
- `sites/<your_site>/static/` with real CSS/JS/icons (and images under HF assets)
- `sites/<your_site>/instance_seed/<site>.db` with seeded data
- Site registered in `websyn_start.sh`, `control_server.py`, `Dockerfile`
- All 15 sites still return 200 on the alt-port container
- Byte-identical reset passes

## Next step

Proceed to **design-tasks** (Phase 2) to define `tasks.jsonl` for this mirror.

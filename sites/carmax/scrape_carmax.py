#!/usr/bin/env python3
"""Harvest real CarMax product images for the WebHarbor mirror.

Drives a real Chromium via Playwright through carmax.com:
  1. Render representative inventory + research pages
  2. Extract the actual image URLs from the post-hydration DOM
  3. Download the image bytes for every seeded vehicle's stock_number

The seeded DB references local paths like:
    /static/images/vehicles/<stock>-front.jpg
    /static/images/vehicles/<stock>-side.jpg
    /static/images/vehicles/<stock>-rear.jpg
    /static/images/vehicles/<stock>-dashboard.jpg
    /static/images/vehicles/<stock>-cargo.jpg
    /static/images/vehicles/<stock>-interior.jpg

This script fetches the corresponding evox stock-photo views from
content-images.carmax.com (which CarMax uses for the same year/make/model
across its catalog), then writes them to the local paths above using
each seeded vehicle's stock number as the basename.

Run from the repo root:
    pip install playwright httpx
    python -m playwright install chromium
    python sites/carmax/scrape_carmax.py
"""
import json
import os
import pathlib
import re
import sys
import time
from urllib.parse import urljoin

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("missing playwright. install with:\n  pip install playwright httpx\n  python -m playwright install chromium")

try:
    import httpx
except ImportError:
    sys.exit("missing httpx. install with: pip install httpx")

ROOT = pathlib.Path(__file__).resolve().parent       # sites/carmax/
SCRAPE_DIR = ROOT / "scraped_data"
IMG_DIR = ROOT / "static" / "images" / "vehicles"
ARTICLE_IMG_DIR = ROOT / "static" / "images" / "articles"
STORE_IMG_DIR = ROOT / "static" / "images" / "stores"
SCRAPE_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)
ARTICLE_IMG_DIR.mkdir(parents=True, exist_ok=True)
STORE_IMG_DIR.mkdir(parents=True, exist_ok=True)

# Map our seeded view-name -> evox view code.
VIEW_CODES = {
    'front':     '089',
    'dashboard': '174',
    'side':      '037',
    'rear':      '119',
    'cargo':     '122',
    'interior':  '118',
}

# Build the list of (year, make, model) tuples we need real photos for.
TEMPLATE_INDEX = [
    (2020, 'honda', 'civic'), (2021, 'honda', 'civic'), (2022, 'honda', 'civic'), (2023, 'honda', 'civic'),
    (2019, 'honda', 'accord'), (2020, 'honda', 'accord'), (2021, 'honda', 'accord'), (2022, 'honda', 'accord'),
    (2019, 'honda', 'cr-v'), (2020, 'honda', 'cr-v'), (2021, 'honda', 'cr-v'), (2022, 'honda', 'cr-v'), (2023, 'honda', 'cr-v'),
    (2020, 'honda', 'pilot'), (2021, 'honda', 'pilot'), (2022, 'honda', 'pilot'),
    (2019, 'toyota', 'camry'), (2020, 'toyota', 'camry'), (2021, 'toyota', 'camry'), (2022, 'toyota', 'camry'), (2023, 'toyota', 'camry'),
    (2020, 'toyota', 'corolla'), (2021, 'toyota', 'corolla'), (2022, 'toyota', 'corolla'), (2023, 'toyota', 'corolla'),
    (2019, 'toyota', 'rav4'), (2020, 'toyota', 'rav4'), (2021, 'toyota', 'rav4'), (2022, 'toyota', 'rav4'), (2023, 'toyota', 'rav4'),
    (2019, 'toyota', 'tacoma'), (2020, 'toyota', 'tacoma'), (2021, 'toyota', 'tacoma'), (2022, 'toyota', 'tacoma'), (2023, 'toyota', 'tacoma'),
    (2020, 'toyota', 'highlander'), (2021, 'toyota', 'highlander'), (2022, 'toyota', 'highlander'),
    (2019, 'ford', 'f-150'), (2020, 'ford', 'f-150'), (2021, 'ford', 'f-150'), (2022, 'ford', 'f-150'), (2023, 'ford', 'f-150'),
    (2019, 'ford', 'explorer'), (2020, 'ford', 'explorer'), (2021, 'ford', 'explorer'), (2022, 'ford', 'explorer'),
    (2019, 'ford', 'mustang'), (2020, 'ford', 'mustang'), (2021, 'ford', 'mustang'), (2022, 'ford', 'mustang'),
    (2019, 'ford', 'escape'), (2020, 'ford', 'escape'), (2021, 'ford', 'escape'), (2022, 'ford', 'escape'),
    (2019, 'chevrolet', 'silverado-1500'), (2020, 'chevrolet', 'silverado-1500'), (2021, 'chevrolet', 'silverado-1500'), (2022, 'chevrolet', 'silverado-1500'), (2023, 'chevrolet', 'silverado-1500'),
    (2019, 'chevrolet', 'equinox'), (2020, 'chevrolet', 'equinox'), (2021, 'chevrolet', 'equinox'), (2022, 'chevrolet', 'equinox'),
    (2020, 'chevrolet', 'tahoe'), (2021, 'chevrolet', 'tahoe'), (2022, 'chevrolet', 'tahoe'), (2023, 'chevrolet', 'tahoe'),
    (2019, 'nissan', 'altima'), (2020, 'nissan', 'altima'), (2021, 'nissan', 'altima'), (2022, 'nissan', 'altima'), (2023, 'nissan', 'altima'),
    (2019, 'nissan', 'rogue'), (2020, 'nissan', 'rogue'), (2021, 'nissan', 'rogue'), (2022, 'nissan', 'rogue'), (2023, 'nissan', 'rogue'),
    (2020, 'hyundai', 'elantra'), (2021, 'hyundai', 'elantra'), (2022, 'hyundai', 'elantra'), (2023, 'hyundai', 'elantra'),
    (2020, 'hyundai', 'tucson'), (2021, 'hyundai', 'tucson'), (2022, 'hyundai', 'tucson'), (2023, 'hyundai', 'tucson'),
    (2019, 'hyundai', 'santa-fe'), (2020, 'hyundai', 'santa-fe'), (2021, 'hyundai', 'santa-fe'), (2022, 'hyundai', 'santa-fe'),
    (2019, 'kia', 'sportage'), (2020, 'kia', 'sportage'), (2021, 'kia', 'sportage'), (2022, 'kia', 'sportage'),
    (2019, 'kia', 'sorento'), (2020, 'kia', 'sorento'), (2021, 'kia', 'sorento'), (2022, 'kia', 'sorento'), (2023, 'kia', 'sorento'),
    (2019, 'jeep', 'grand-cherokee'), (2020, 'jeep', 'grand-cherokee'), (2021, 'jeep', 'grand-cherokee'), (2022, 'jeep', 'grand-cherokee'), (2023, 'jeep', 'grand-cherokee'),
    (2019, 'jeep', 'wrangler'), (2020, 'jeep', 'wrangler'), (2021, 'jeep', 'wrangler'), (2022, 'jeep', 'wrangler'), (2023, 'jeep', 'wrangler'),
    (2019, 'subaru', 'outback'), (2020, 'subaru', 'outback'), (2021, 'subaru', 'outback'), (2022, 'subaru', 'outback'), (2023, 'subaru', 'outback'),
    (2019, 'subaru', 'forester'), (2020, 'subaru', 'forester'), (2021, 'subaru', 'forester'), (2022, 'subaru', 'forester'),
    (2019, 'mazda', 'cx-5'), (2020, 'mazda', 'cx-5'), (2021, 'mazda', 'cx-5'), (2022, 'mazda', 'cx-5'), (2023, 'mazda', 'cx-5'),
    (2019, 'bmw', '3-series'), (2020, 'bmw', '3-series'), (2021, 'bmw', '3-series'), (2022, 'bmw', '3-series'),
    (2019, 'mercedes-benz', 'c-class'), (2020, 'mercedes-benz', 'c-class'), (2021, 'mercedes-benz', 'c-class'), (2022, 'mercedes-benz', 'c-class'),
    (2019, 'tesla', 'model-3'), (2020, 'tesla', 'model-3'), (2021, 'tesla', 'model-3'), (2022, 'tesla', 'model-3'), (2023, 'tesla', 'model-3'),
]


def discover_evox_urls():
    """Use Playwright to load research pages and grab evox image URLs.

    Returns: dict[(year, make, model)] = list[url] (typically 6 views per car).
    """
    found = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900},
                                 user_agent='Mozilla/5.0 webharbor-mirror-scraper')
        for year, make, model in TEMPLATE_INDEX:
            url = f"https://www.carmax.com/research/{make}/{model}/{year}"
            print(f"  recon {year} {make} {model}", flush=True)
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(900)
                imgs = page.eval_on_selector_all(
                    'img',
                    "els => els.map(e => e.currentSrc || e.src)"
                                ".filter(u => u && u.includes('content-images.carmax.com/stockimages'))"
                )
                if imgs:
                    # Dedupe by view code in URL
                    dedup = []
                    seen = set()
                    for u in imgs:
                        m = re.search(r"st\d+-(\d+)-evoxweb", u)
                        code = m.group(1) if m else u
                        if code not in seen:
                            seen.add(code)
                            dedup.append(u)
                    found[(year, make, model)] = dedup
            except Exception as e:
                print(f"    ! {e}")
        browser.close()
    return found


def download_image(client, url, dest):
    if dest.exists() and dest.stat().st_size > 1024:
        return False
    r = client.get(url)
    if r.status_code != 200:
        return False
    dest.write_bytes(r.content)
    return True


def main():
    # 1. Load every seeded vehicle from the DB.
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault('FLASK_RUN_FROM_CLI', '1')
    from app import app, Vehicle, Store, Article
    vehicles = []
    with app.app_context():
        vehicles = Vehicle.query.order_by(Vehicle.id).all()
        stores = Store.query.order_by(Store.id).all()
        articles = Article.query.order_by(Article.id).all()
    print(f"[scrape] {len(vehicles)} vehicles, {len(stores)} stores, "
          f"{len(articles)} articles need images")

    # 2. Use Playwright to discover real evox URLs by (year, make, model).
    print("[scrape] discovering image URLs via Playwright...")
    url_map = discover_evox_urls()

    cache_json = SCRAPE_DIR / "image_urls.json"
    cache_json.write_text(json.dumps(
        {f"{y}|{mk}|{md}": urls for (y, mk, md), urls in url_map.items()},
        indent=2,
    ))
    print(f"[scrape] cached {sum(len(v) for v in url_map.values())} URLs to {cache_json}")

    # 3. Download per-vehicle stock photos. Each seeded vehicle gets up to
    #    6 views named <stock>-{front,side,rear,dashboard,cargo,interior}.jpg.
    print("[scrape] downloading vehicle images...")
    downloaded = 0
    skipped = 0
    with httpx.Client(follow_redirects=True, timeout=30,
                      headers={'User-Agent': 'webharbor-mirror-scraper'}) as cx:
        for v in vehicles:
            key = (v.year, v.make_slug, v.model_slug)
            urls = url_map.get(key, [])
            if not urls:
                continue
            views = list(VIEW_CODES.keys())
            for i, view in enumerate(views):
                if i >= len(urls):
                    break
                src = urls[i]
                dest = IMG_DIR / f"{v.stock_number}-{view}.jpg"
                try:
                    if download_image(cx, src, dest):
                        downloaded += 1
                    else:
                        skipped += 1
                except Exception as e:
                    print(f"  ! {dest.name}: {e}")
    print(f"[scrape] downloaded {downloaded} new images, skipped {skipped} already-present")

    # 4. (Optional) Save a 'placeholder' for stores using carmax store icon
    print("[scrape] done.")


if __name__ == '__main__':
    main()

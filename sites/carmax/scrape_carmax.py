#!/usr/bin/env python3
"""Harvest real CarMax product images for the WebHarbor mirror.

Direct httpx fetch from content-images.carmax.com (open CDN, no anti-bot).
Every model uses the same `st2400` evox prefix, so URLs are fully
deterministic — no scraping required:

    https://content-images.carmax.com/stockimages/<year>/<make>/<model>/st2400-<view>-evoxwebmedium.png

The seeded DB references local paths like:
    /static/images/vehicles/<stock>-front.jpg
    /static/images/vehicles/<stock>-side.jpg   etc.

This script fetches one set of evox photos per (year, make_slug, model_slug)
tuple, then writes a copy under each matching vehicle's stock_number.

Run from the repo root:
    pip install httpx
    python sites/carmax/scrape_carmax.py
"""
import os
import pathlib
import sys

try:
    import httpx
except ImportError:
    sys.exit("missing httpx. install with: pip install httpx")

ROOT = pathlib.Path(__file__).resolve().parent
IMG_DIR = ROOT / "static" / "images" / "vehicles"
IMG_DIR.mkdir(parents=True, exist_ok=True)

# evox view code → our local filename suffix
VIEW_MAP = {
    'front':     '089',   # angled front (used as main thumbnail)
    'dashboard': '174',
    'side':      '037',
    'rear':      '119',
    'cargo':     '122',
    'interior':  '118',   # front (alt angle, used for interior shot in our gallery)
}

# Our seed's model_slug → carmax CDN URL model slug.
# Carmax sometimes uses a different convention from our slugify().
SLUG_REMAP = {
    'f-150':     'f150',
    'silverado': 'silverado-1500',
    # 'cr-v' stays 'cr-v', 'model-3' stays 'model-3', etc.
    # 'c-class' is the carmax URL slug for Mercedes C-Class.
    # If your seed uses something else, add a mapping here.
}

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124.0.0.0 Safari/537.36')


def build_url(year, make_slug, model_slug, view_code):
    msk = SLUG_REMAP.get(model_slug, model_slug)
    return (f"https://content-images.carmax.com/stockimages/"
            f"{year}/{make_slug}/{msk}/st2400-{view_code}-evoxwebmedium.png")


def main():
    # Load the seeded vehicles
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault('FLASK_RUN_FROM_CLI', '1')
    from app import app, Vehicle
    with app.app_context():
        vehicles = Vehicle.query.order_by(Vehicle.id).all()
    print(f"[scrape] {len(vehicles)} vehicles need images")

    # Cache: (year, make_slug, model_slug) -> {view_name: bytes or None}
    # Each unique (year, make, model) gets one CDN fetch per view; we then
    # write the bytes under each vehicle's stock_number that matches.
    cache = {}
    downloaded = 0
    skipped = 0
    missing = 0

    with httpx.Client(headers={'User-Agent': UA},
                      follow_redirects=True, timeout=30) as cx:
        for v in vehicles:
            key = (v.year, v.make_slug, v.model_slug)
            if key not in cache:
                cache[key] = {}
                for view_name, view_code in VIEW_MAP.items():
                    url = build_url(v.year, v.make_slug, v.model_slug, view_code)
                    try:
                        r = cx.get(url)
                        if r.status_code == 200 and len(r.content) > 2000:
                            cache[key][view_name] = r.content
                        else:
                            cache[key][view_name] = None
                    except Exception as e:
                        print(f"  ! {url}: {e}")
                        cache[key][view_name] = None
                ok_views = sum(1 for b in cache[key].values() if b)
                print(f"  fetched {ok_views}/6 views for "
                      f"{v.year} {v.make} {v.model}")

            for view_name, view_code in VIEW_MAP.items():
                dest = IMG_DIR / f"{v.stock_number}-{view_name}.jpg"
                if dest.exists() and dest.stat().st_size > 2000:
                    skipped += 1
                    continue
                data = cache[key].get(view_name)
                if data is None:
                    missing += 1
                    continue
                dest.write_bytes(data)
                downloaded += 1

    print(f"\n[scrape] done: downloaded={downloaded}, "
          f"skipped (already present)={skipped}, "
          f"missing (no CDN match)={missing}")
    print(f"[scrape] {len(cache)} unique (year, make, model) tuples")
    no_image = [k for k, v in cache.items()
                if not any(v.values())]
    if no_image:
        print(f"[scrape] {len(no_image)} tuples had ZERO images "
              f"(check slug mapping):")
        for k in no_image[:10]:
            print(f"  - {k}")


if __name__ == '__main__':
    main()

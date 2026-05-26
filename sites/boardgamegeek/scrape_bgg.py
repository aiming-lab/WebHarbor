"""Scrape real BoardGameGeek data via api.geekdo.com (no auth) + Playwright (for the
rank browse list which needs the CF challenge).

Outputs sites/boardgamegeek/scraped_data/bgg.json containing:
- top_games: list of {objectid, name, rank, year, avg, num_voters, thumbnail_url} from
  /browse/boardgame?page=1..N
- items: dict[objectid -> geekitem_payload] (full game metadata)
- dyn: dict[objectid -> dynamicinfo_payload] (rank, polls, weight, stats)
- reviews: dict[objectid -> list[review]] (top text reviews)
- hot: hotness list (top 50 trending right now)
- users: dict[username -> user payload] (top contributors + reviewers)

Real images (covers + thumbnails) are written to scraped_data/images/<id>.jpg.
The seed_data.py step will read this JSON and load it into the SQLite seed.
"""
import concurrent.futures
import functools
import json
import os
import pathlib
import re
import sys
import time
from urllib.parse import urlparse

import httpx

# Make print() unbuffered when stdout is redirected to a file so we see live
# progress instead of a single dump at the end.
print = functools.partial(print, flush=True)

OUT = pathlib.Path(__file__).parent / "scraped_data"
OUT.mkdir(parents=True, exist_ok=True)
(IMG_DIR := OUT / "images").mkdir(exist_ok=True)

# Tuning knobs — keep them visible so it's easy to scale up if needed.
TOP_PAGES = int(os.environ.get("BGG_PAGES", "10"))       # 100 games per page
REVIEWS_PER_GAME = int(os.environ.get("BGG_REVIEWS", "30"))
USERS_TO_FETCH = int(os.environ.get("BGG_USERS", "200"))
CONCURRENCY = int(os.environ.get("BGG_CONC", "10"))

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "application/json,text/html;q=0.9"}

client = httpx.Client(headers=HEADERS, timeout=30.0,
                      limits=httpx.Limits(max_connections=CONCURRENCY))
API = "https://api.geekdo.com/api"


# --------- step 1: top game ids + rank table via Playwright ---------

def scrape_top_pages(pages: int) -> list[dict]:
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for pg in range(1, pages + 1):
            ctx = browser.new_context(user_agent=UA, viewport={"width": 1400, "height": 1200})
            page = ctx.new_page()
            url = f"https://boardgamegeek.com/browse/boardgame/page/{pg}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_selector("table.collection_table td.collection_rank",
                                       timeout=25000)
            except Exception as e:
                print(f"  ! page {pg} load: {e}", file=sys.stderr)
                ctx.close()
                time.sleep(3)
                continue
            data = page.eval_on_selector_all(
                "table.collection_table tr",
                """rows => rows.filter(tr =>
                    tr.querySelector('td.collection_rank') && tr.querySelector('a[href^="/boardgame/"]')
                ).map(tr => {
                    const cells = tr.querySelectorAll('td');
                    const rankAnchor = tr.querySelector('td.collection_rank a[name]');
                    const rank = rankAnchor ? rankAnchor.getAttribute('name') : '';
                    const titleLink = tr.querySelector('td.collection_objectname a[href^="/boardgame/"]');
                    const href = titleLink ? titleLink.getAttribute('href') : '';
                    const m = href.match(/^\\/boardgame\\/(\\d+)/);
                    const objectid = m ? m[1] : null;
                    const name = (titleLink?.innerText || '').trim();
                    const yearEl = tr.querySelector('td.collection_objectname span.smallerfont');
                    const year = (yearEl?.innerText || '').replace(/[()]/g,'').trim();
                    const thumb = tr.querySelector('td.collection_thumbnail img')?.src || '';
                    const numericCells = Array.from(tr.querySelectorAll('td.collection_bggrating')).map(c => c.innerText.trim());
                    const [geek_rating, avg_rating, num_voters] = numericCells.length >= 3
                        ? numericCells.slice(0,3)
                        : ['','',''];
                    return {rank, objectid, name, year, thumb,
                            geek_rating, avg_rating, num_voters};
                })"""
            )
            valid = [r for r in data if r.get("objectid")]
            rows.extend(valid)
            print(f"  page {pg}: {len(valid)} rows  total={len(rows)}")
            ctx.close()
            time.sleep(1.5)
        browser.close()
    return rows


# --------- step 2: per-game JSON endpoints ---------

def fetch_json(url: str, retries: int = 2) -> dict | None:
    for attempt in range(retries + 1):
        try:
            r = client.get(url)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return None
        except Exception as e:
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            print(f"  ! {url[:80]}: {e}", file=sys.stderr)
            return None
    return None


def fetch_geekitem(oid: str) -> dict | None:
    return fetch_json(f"{API}/geekitems?objectid={oid}&objecttype=thing&subtype=boardgame&type=thing")


def fetch_dyn(oid: str) -> dict | None:
    return fetch_json(f"{API}/dynamicinfo?objectid={oid}&objecttype=thing&subtype=boardgame&type=thing")


def fetch_reviews(oid: str, count: int) -> list[dict]:
    out = []
    page = 1
    while len(out) < count and page <= 5:
        url = (f"{API}/collections?ajax=1&objectid={oid}&objecttype=thing"
               f"&pageid={page}&showcount=50&require_review=true&sort=rating")
        data = fetch_json(url)
        items = (data or {}).get("items") or []
        if not items:
            break
        out.extend(items)
        page += 1
        if len(items) < 50:
            break
    # Slim down each review: keep what we render
    slim = []
    for it in out[:count]:
        tf = it.get("textfield") or {}
        comment_obj = tf.get("comment") if isinstance(tf.get("comment"), dict) else None
        comment = None
        if comment_obj:
            comment = comment_obj.get("rendered") or comment_obj.get("value")
        rating_field = it.get("rating")
        rating = None
        if isinstance(rating_field, dict):
            sub = rating_field.get("rating")
            if isinstance(sub, dict):
                rating = sub.get("value")
            else:
                rating = sub
        elif isinstance(rating_field, (int, float, str)):
            rating = rating_field
        slim.append({
            "collid": it.get("collid"),
            "username": (it.get("user") or {}).get("username") if isinstance(it.get("user"), dict) else None,
            "country": (it.get("user") or {}).get("country") if isinstance(it.get("user"), dict) else None,
            "rating": rating,
            "comment_html": comment,
            "tstamp": it.get("status_tstamp"),
        })
    return slim


def fetch_user(username: str) -> dict | None:
    # /user?username=... returns a list[user] or a dict {user: ...}
    base = fetch_json(f"{API}/user?username={username}")
    if not base:
        return None
    if isinstance(base, list):
        entry = base[0] if base else None
    elif isinstance(base, dict):
        entry = base.get("user") or base
    else:
        entry = None
    if not isinstance(entry, dict):
        return None
    uid = entry.get("userid") or entry.get("id")
    if not uid:
        return None
    profile = fetch_json(f"{API}/user/{uid}/profile") or {}
    return {"base": entry, "profile": profile, "userid": uid}


# --------- step 3: image fetch ---------

def fetch_image(url: str, oid: str, suffix: str = "") -> str | None:
    if not url:
        return None
    try:
        dest = IMG_DIR / f"{oid}{suffix}.jpg"
        if dest.exists() and dest.stat().st_size > 500:
            return dest.name
        r = client.get(url)
        if r.status_code != 200 or len(r.content) < 500:
            return None
        dest.write_bytes(r.content)
        return dest.name
    except Exception as e:
        print(f"  ! img {oid}: {e}", file=sys.stderr)
        return None


# --------- step 4: hot list ---------

def fetch_hot() -> list[dict]:
    data = fetch_json(f"{API}/hotness?geeksite=boardgame&objecttype=thing&showcount=50&singular=1")
    items = (data or {}).get("items") or []
    return items


# --------- step 5: forum threads (a few representative ones) ---------

def fetch_top_thread_titles_for_game(oid: str, limit: int = 10) -> list[dict]:
    """Get a slice of recent thread titles + post counts for the game's forum row."""
    data = fetch_json(
        f"{API}/forums/threads?ajax=1&objectid={oid}&objecttype=thing&pageid=1"
        f"&showcount={limit}&sort=latestpost"
    )
    items = (data or {}).get("threads") or (data or {}).get("items") or []
    return items[:limit]


# --------- main ---------

def main() -> None:
    print(f"[bgg-scrape] step 1: rank pages × {TOP_PAGES}")
    rank_rows = scrape_top_pages(TOP_PAGES)
    by_oid = {}
    for r in rank_rows:
        oid = r["objectid"]
        if oid in by_oid:
            continue
        by_oid[oid] = r
    print(f"  unique games: {len(by_oid)}")
    if not by_oid:
        print("  ! no rank rows collected, aborting", file=sys.stderr)
        sys.exit(2)

    oids = list(by_oid.keys())

    print(f"[bgg-scrape] step 2a: geekitems for {len(oids)} games (conc={CONCURRENCY})")
    items: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for oid, data in zip(oids, pool.map(fetch_geekitem, oids)):
            if data:
                items[oid] = data
            if len(items) % 100 == 0:
                print(f"  geekitems {len(items)}/{len(oids)}")
    print(f"  geekitems: {len(items)}")

    print(f"[bgg-scrape] step 2b: dynamicinfo for {len(oids)} games")
    dyn: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for oid, data in zip(oids, pool.map(fetch_dyn, oids)):
            if data:
                dyn[oid] = data
            if len(dyn) % 100 == 0:
                print(f"  dyn {len(dyn)}/{len(oids)}")
    print(f"  dynamicinfo: {len(dyn)}")

    print(f"[bgg-scrape] step 3: reviews (top {REVIEWS_PER_GAME}/game) for {len(oids)} games")
    reviews: dict[str, list] = {}
    REV_CONC = max(4, CONCURRENCY // 3)
    def _fetch_rev(oid):
        return oid, fetch_reviews(oid, REVIEWS_PER_GAME)
    done_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=REV_CONC) as pool:
        for oid, revs in pool.map(_fetch_rev, oids):
            reviews[oid] = revs
            done_count += 1
            if done_count % 25 == 0:
                print(f"  reviews {done_count}/{len(oids)}  "
                      f"total_so_far={sum(len(v) for v in reviews.values())}")
    total_revs = sum(len(v) for v in reviews.values())
    print(f"  reviews total: {total_revs}")

    print(f"[bgg-scrape] step 4: forum thread titles per game (light)")
    threads: dict[str, list] = {}
    def _fetch_th(oid):
        return oid, fetch_top_thread_titles_for_game(oid, 8)
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for oid, t in pool.map(_fetch_th, oids):
            threads[oid] = t
    th_total = sum(len(v) for v in threads.values())
    print(f"  thread headers: {th_total}")

    print(f"[bgg-scrape] step 5: hot list")
    hot = fetch_hot()
    print(f"  hot items: {len(hot)}")

    print(f"[bgg-scrape] step 6: cover images (top {len(oids)} games)")
    n_imgs = 0
    def _fetch_img(oid):
        r = by_oid.get(oid, {})
        # geekitems may have a higher-res image; prefer that if found
        gi = (items.get(oid) or {}).get("item") or {}
        big = gi.get("imageurl") or gi.get("imageurl_lg") or ""
        cover = big or r.get("thumb") or ""
        thumb = r.get("thumb") or big
        c = fetch_image(cover, oid, "_cover") if cover else None
        t = fetch_image(thumb, oid, "_thumb") if thumb and thumb != cover else c
        return oid, c, t
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        cover_map: dict[str, dict] = {}
        for oid, c, t in pool.map(_fetch_img, oids):
            cover_map[oid] = {"cover": c, "thumb": t}
            if c:
                n_imgs += 1
            if (n_imgs % 100) == 0 and n_imgs:
                print(f"  imgs {n_imgs}/{len(oids)}")
    print(f"  cover images: {n_imgs}")

    print(f"[bgg-scrape] step 7: users (top reviewers across games)")
    user_counter: dict[str, int] = {}
    for revs in reviews.values():
        for rv in revs:
            un = rv.get("username")
            if un:
                user_counter[un] = user_counter.get(un, 0) + 1
    top_users = [u for u, _ in sorted(user_counter.items(), key=lambda x: -x[1])][:USERS_TO_FETCH]
    print(f"  fetching {len(top_users)} user profiles…")
    users: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for name, data in zip(top_users, pool.map(fetch_user, top_users)):
            if data:
                users[name] = data
    print(f"  users: {len(users)}")

    out = {
        "scraped_at": int(time.time()),
        "top_games": rank_rows,
        "items": items,
        "dyn": dyn,
        "reviews": reviews,
        "threads": threads,
        "hot": hot,
        "users": users,
        "covers": cover_map,
    }
    out_path = OUT / "bgg.json"
    out_path.write_text(json.dumps(out))
    print(f"[bgg-scrape] wrote {out_path}  ({out_path.stat().st_size/1e6:.1f} MB)")
    print(f"[bgg-scrape] images dir: {IMG_DIR}  ({sum(1 for _ in IMG_DIR.iterdir())} files)")


if __name__ == "__main__":
    main()

"""Augmentation scraper: fill the gaps the first pass left.

1) EXPANSIONS — for every top-500 base game, fetch the full list of expansion
   ids it links to, then fetch geekitems + dynamicinfo for each expansion so
   they become first-class Game rows (subtype='boardgameexpansion') in our
   catalog.  Fixes BGG--20 + provides real expansion data for every popular
   base game.

2) LOW RATINGS — the first pass scraped each game's reviews with
   sort=rating&direction=desc only.  Re-fetch with direction=asc so the seed
   contains the actual low-end ratings real BGG users gave, not just the
   top-rated reviews.  Removes the structural answer-leak in BGG--14.

Reads:  sites/boardgamegeek/scraped_data/bgg.json
Writes: sites/boardgamegeek/scraped_data/bgg_extras.json
        sites/boardgamegeek/scraped_data/images/<id>_{cover,thumb}.jpg
"""
import concurrent.futures
import functools
import json
import pathlib
import sys
import time

import httpx

print = functools.partial(print, flush=True)

BASE = pathlib.Path(__file__).parent
SRC = BASE / "scraped_data" / "bgg.json"
OUT_JSON = BASE / "scraped_data" / "bgg_extras.json"
IMG = BASE / "scraped_data" / "images"
IMG.mkdir(parents=True, exist_ok=True)

API = "https://api.geekdo.com/api"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CONC = 12

client = httpx.Client(
    headers={"User-Agent": UA, "Accept": "application/json"},
    timeout=30.0,
    limits=httpx.Limits(max_connections=CONC),
)


def get(url, retries=2):
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
            print(f"  ! {url[:90]}: {e}", file=sys.stderr)
            return None


def fetch_expansion_ids(base_oid: str) -> list[str]:
    """Return all expansion objectids for a base game (multi-page API)."""
    ids: list[str] = []
    page = 1
    while page <= 5:
        url = (f"{API}/geekitem/linkeditems?linkdata_index=boardgameexpansion"
               f"&objectid={base_oid}&objecttype=thing&pageid={page}&showcount=50")
        data = get(url)
        if not data:
            break
        items = data.get("items") or data.get("linkeditems") or []
        if not items:
            break
        new_ids = []
        for it in items:
            oid = it.get("objectid") or it.get("id")
            if oid:
                new_ids.append(str(oid))
        ids.extend(new_ids)
        if len(new_ids) < 50:
            break
        page += 1
    return ids


def fetch_geekitem(oid: str) -> dict | None:
    return get(f"{API}/geekitems?objectid={oid}&objecttype=thing"
               f"&subtype=boardgameexpansion&type=thing")


def fetch_dyn(oid: str) -> dict | None:
    return get(f"{API}/dynamicinfo?objectid={oid}&objecttype=thing"
               f"&subtype=boardgameexpansion&type=thing")


def fetch_image(url: str, oid: str, suffix: str) -> str | None:
    if not url:
        return None
    dest = IMG / f"{oid}{suffix}.jpg"
    if dest.exists() and dest.stat().st_size > 500:
        return dest.name
    try:
        r = client.get(url)
        if r.status_code != 200 or len(r.content) < 500:
            return None
        dest.write_bytes(r.content)
        return dest.name
    except Exception as e:
        print(f"  ! img {oid}: {e}", file=sys.stderr)
        return None


def fetch_low_ratings(oid: str, count: int = 20) -> list[dict]:
    """Fetch low-end ratings (sort asc) to balance the high-only first-pass data."""
    out = []
    page = 1
    while len(out) < count and page <= 3:
        url = (f"{API}/collections?ajax=1&objectid={oid}&objecttype=thing"
               f"&pageid={page}&showcount=50&require_review=true"
               f"&sort=rating&direction=asc")
        d = get(url)
        items = (d or {}).get("items") or []
        if not items:
            break
        out.extend(items)
        page += 1
        if len(items) < 50:
            break
    slim = []
    for it in out[:count]:
        tf = it.get("textfield") or {}
        comment_obj = tf.get("comment") if isinstance(tf.get("comment"), dict) else None
        comment = comment_obj.get("rendered") or comment_obj.get("value") if comment_obj else None
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


def main():
    print(f"[extras] loading {SRC}...")
    src = json.loads(SRC.read_text())
    base_oids = list(src.get("items", {}).keys())
    print(f"  base games: {len(base_oids)}")

    # ----- 1) expansion id lists -----
    print(f"[extras] fetching expansion id-lists for {len(base_oids)} base games (conc={CONC})...")
    exp_ids_per_base: dict[str, list[str]] = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as pool:
        futures = {pool.submit(fetch_expansion_ids, oid): oid for oid in base_oids}
        for fut in concurrent.futures.as_completed(futures):
            oid = futures[fut]
            try:
                exp_ids_per_base[oid] = fut.result()
            except Exception as e:
                exp_ids_per_base[oid] = []
                print(f"  ! exp-ids {oid}: {e}", file=sys.stderr)
            done += 1
            if done % 50 == 0:
                tot = sum(len(v) for v in exp_ids_per_base.values())
                print(f"  exp-ids {done}/{len(base_oids)}  total={tot}")

    # Flatten + dedupe.  We don't want to double-fetch.
    all_expansion_ids = set()
    for ids in exp_ids_per_base.values():
        for x in ids:
            all_expansion_ids.add(x)
    # Exclude expansions that are already base games in our seed (rare).
    expansion_oids = [x for x in sorted(all_expansion_ids, key=int)
                      if x not in src.get("items", {})]
    print(f"  unique expansion oids: {len(expansion_oids)}")

    # ----- 2) geekitems for every expansion -----
    print(f"[extras] geekitems for {len(expansion_oids)} expansions...")
    exp_items: dict[str, dict] = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as pool:
        futures = {pool.submit(fetch_geekitem, oid): oid for oid in expansion_oids}
        for fut in concurrent.futures.as_completed(futures):
            oid = futures[fut]
            data = fut.result()
            if data:
                exp_items[oid] = data
            done += 1
            if done % 100 == 0:
                print(f"  exp-items {done}/{len(expansion_oids)}  hits={len(exp_items)}")

    # ----- 3) dynamicinfo -----
    print(f"[extras] dynamicinfo for {len(expansion_oids)} expansions...")
    exp_dyn: dict[str, dict] = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as pool:
        futures = {pool.submit(fetch_dyn, oid): oid for oid in expansion_oids}
        for fut in concurrent.futures.as_completed(futures):
            oid = futures[fut]
            data = fut.result()
            if data:
                exp_dyn[oid] = data
            done += 1
            if done % 100 == 0:
                print(f"  exp-dyn {done}/{len(expansion_oids)}  hits={len(exp_dyn)}")

    # ----- 4) expansion cover images -----
    print(f"[extras] cover images for expansions...")
    n_imgs = 0
    def _fetch_img(oid):
        gi = (exp_items.get(oid) or {}).get("item") or {}
        cover = gi.get("imageurl") or gi.get("imageurl_lg") or ""
        thumb = gi.get("thumbnail") or cover
        c = fetch_image(cover, oid, "_cover") if cover else None
        t = fetch_image(thumb, oid, "_thumb") if thumb else None
        return oid, c, t
    cover_map: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as pool:
        for oid, c, t in pool.map(_fetch_img, expansion_oids):
            cover_map[oid] = {"cover": c, "thumb": t}
            if c:
                n_imgs += 1
                if n_imgs % 100 == 0:
                    print(f"  exp-imgs {n_imgs}")
    print(f"  expansion covers downloaded: {n_imgs}")

    # ----- 5) low ratings for base games -----
    print(f"[extras] low ratings (sort asc) for {len(base_oids)} base games...")
    REV_CONC = max(4, CONC // 3)
    low_reviews: dict[str, list] = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=REV_CONC) as pool:
        futures = {pool.submit(fetch_low_ratings, oid, 15): oid for oid in base_oids}
        for fut in concurrent.futures.as_completed(futures):
            oid = futures[fut]
            low_reviews[oid] = fut.result()
            done += 1
            if done % 50 == 0:
                tot = sum(len(v) for v in low_reviews.values())
                print(f"  low-reviews {done}/{len(base_oids)}  total={tot}")

    out = {
        "scraped_at": int(time.time()),
        "exp_ids_per_base": exp_ids_per_base,
        "exp_items": exp_items,
        "exp_dyn": exp_dyn,
        "exp_covers": cover_map,
        "low_reviews": low_reviews,
    }
    OUT_JSON.write_text(json.dumps(out))
    print(f"[extras] wrote {OUT_JSON}  "
          f"({OUT_JSON.stat().st_size/1e6:.1f} MB)")
    print(f"[extras] images dir entries: "
          f"{sum(1 for _ in IMG.iterdir())}")


if __name__ == "__main__":
    main()

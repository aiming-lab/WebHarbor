"""Tiny add-on: fetch genuinely-low BGG ratings (1-5 stars), no review filter.

Without require_review=true, the BGG collections endpoint returns rating-only
entries too, which is where the actual low scores live.  Real reviewers rarely
go below 6; bare ratings go to 1.

Appends to scraped_data/bgg_extras.json under key 'low_ratings_only'.
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
EXTRAS = BASE / "scraped_data" / "bgg_extras.json"
SRC = BASE / "scraped_data" / "bgg.json"

API = "https://api.geekdo.com/api"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CONC = 8
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
            return None
    return None


def fetch_low_only(oid: str, count: int = 25) -> list[dict]:
    """No require_review filter — pulls real low-end raw ratings."""
    out = []
    page = 1
    while len(out) < count and page <= 3:
        url = (f"{API}/collections?ajax=1&objectid={oid}&objecttype=thing"
               f"&pageid={page}&showcount=50&sort=rating&direction=asc")
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
        if rating is None:
            continue
        try:
            rating_f = float(rating)
        except (TypeError, ValueError):
            continue
        if rating_f > 5.5:
            continue   # only keep actual lows
        tf = it.get("textfield") or {}
        comment_obj = tf.get("comment") if isinstance(tf.get("comment"), dict) else None
        comment = comment_obj.get("rendered") or comment_obj.get("value") if comment_obj else None
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
    src = json.loads(SRC.read_text())
    base_oids = list(src.get("items", {}).keys())
    extras = json.loads(EXTRAS.read_text()) if EXTRAS.exists() else {}
    print(f"[low] fetching real low ratings for {len(base_oids)} base games...")

    low_only: dict[str, list] = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as pool:
        futures = {pool.submit(fetch_low_only, oid, 25): oid for oid in base_oids}
        for fut in concurrent.futures.as_completed(futures):
            oid = futures[fut]
            low_only[oid] = fut.result()
            done += 1
            if done % 50 == 0:
                tot = sum(len(v) for v in low_only.values())
                print(f"  {done}/{len(base_oids)}  low_total={tot}")

    extras['low_ratings_only'] = low_only
    EXTRAS.write_text(json.dumps(extras))
    total = sum(len(v) for v in low_only.values())
    print(f"[low] wrote {total} truly-low ratings across {sum(1 for v in low_only.values() if v)} games")


if __name__ == "__main__":
    main()

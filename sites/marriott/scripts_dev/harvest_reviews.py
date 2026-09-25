"""Harvest guest reviews from BazaarVoice (the reviews provider marriott.com itself uses).

The live site's hotel review pages load their data from
api.bazaarvoice.com using Marriott's public client key; the review payload
is captured per hotel (marsha) the same way the real page does: product
summary (average, distribution) plus the newest reviews with author, rating,
title, body, date and trip type.
"""
from __future__ import annotations

import json
import pathlib
import random
import re
import sys
import time
import urllib.parse

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "source_data"
CACHE = ROOT / "scraped_data" / "reviews"
CACHE.mkdir(parents=True, exist_ok=True)

PASSKEY = "canCX9lvC812oa4Y6HYf4gmWK5uszkZCKThrdtYkZqcYE"
API = "https://api.bazaarvoice.com/data/batch.json"
MAX_REVIEWS_PER_HOTEL = 30

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def _product_stats(marsha: str) -> dict | None:
    """Fetch the hotel's product-level review stats (average, total count,
    star distribution) from the BazaarVoice products endpoint -- the same
    stats the live review page's summary widget shows."""
    import urllib.parse
    url = (f"https://api.bazaarvoice.com/data/products.json?passkey={PASSKEY}"
           "&apiversion=5.5&displaycode=14883-en_us"
           f"&filter={urllib.parse.quote(f'id:eq:{marsha}')}&stats=reviews")
    try:
        r = httpx.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        res = (r.json() or {}).get("Results") or []
        if not res:
            return None
        st = res[0].get("ReviewStatistics", {}) or {}
        dist = {}
        for row in st.get("RatingDistribution", []) or []:
            dist[str(row["RatingValue"])] = row["Count"]
        subs = {}
        sec = st.get("SecondaryRatingsAverages", {}) or {}
        for s in (sec.get("SecondaryRatingsAverages") or []):
            if s.get("Id") and s.get("Average") is not None:
                subs[s["Id"]] = {"label": s.get("Label") or s["Id"],
                                 "avg": round(float(s["Average"]), 1)}
        avg = st.get("AverageOverallRating")
        return {
            "average": round(float(avg), 1) if avg is not None else None,
            "count": st.get("TotalReviewCount") or 0,
            "distribution": dist,
            "subratings": subs,
        }
    except Exception:  # noqa: BLE001
        return None


def fetch_hotel_reviews(marsha: str, limit=30) -> dict | None:
    params = {
        "passkey": PASSKEY,
        "apiversion": "5.5",
        "displaycode": "14883-en_us",
        "resource.q0": "products",
        "filter.q0": f"id:eq:{marsha}",
        "stats.q0": "reviews",
        "filteredstats.q0": "reviews",
        "filter_reviews.q0": "contentlocale:eq:en*,en_US",
        "resource.q1": "reviews",
        "filter.q1": "isratingsonly:eq:false",
        "filter.q1b": f"productid:eq:{marsha}",
        "filter.q1c": "contentlocale:eq:en*,en_US",
        "sort.q1": "submissiontime:desc",
        "stats.q1": "reviews",
        "include.q1": "authors,products",
        "filter_reviews.q1": "contentlocale:eq:en*,en_US",
        "limit.q1": str(limit),
        "offset.q1": "0",
    }
    # batch.json treats repeated filter.q1 as separate filters (AND)
    query = urllib.parse.urlencode(params)
    query = query.replace("filter.q1b=", "filter.q1=").replace("filter.q1c=", "filter.q1=")
    r = httpx.get(f"{API}?{query}", headers=HEADERS, timeout=30)
    if r.status_code != 200:
        return None
    data = r.json()
    if data.get("HasErrors"):
        return None
    res = data.get("BatchedResults", {})
    out = {"marsha": marsha}
    stats = _product_stats(marsha)
    if stats is not None:
        out["summary"] = stats
    q1 = res.get("q1", {})
    reviews = []
    includes = (q1.get("Includes") or {}).get("Authors") or {}
    sub_totals = {}
    sub_counts = {}
    for rv in q1.get("Results", []) or []:
        author = includes.get(rv.get("AuthorId"), {}) or {}
        location = (author.get("Demographic") or {}).get("Location", {})
        sub_values = {}
        for key, sec in (rv.get("SecondaryRatings") or {}).items():
            if sec.get("Value") is not None:
                sub_values[key] = sec["Value"]
                sub_totals.setdefault(key, 0.0)
                sub_totals[key] += float(sec["Value"])
                sub_counts.setdefault(key, 0)
                sub_counts[key] += 1

        def clean(s):
            return re.sub(r"<[^>]+>", "", s or "").strip()

        nickname = rv.get("UserNickname") or author.get("DisplayName") or "Marriott Bonvoy member"
        reviews.append({
            "author": nickname,
            "location": rv.get("UserLocation") or (", ".join([location.get("Level1", ""), location.get("Level2", "")]).strip(", ") if location else None),
            "rating": rv.get("Rating"),
            "title": clean(rv.get("Title")),
            "body": clean(rv.get("ReviewText")),
            "date": (rv.get("SubmissionTime") or "")[:10],
            "trip_type": rv.get("ContextDataValues", {}).get("TravelType", {}).get("Value"),
            "subratings": sub_values,
            "mgmt_response": clean(((rv.get("ClientResponses") or [{}])[0].get("Response")) if rv.get("ClientResponses") else None),
        })
    out["reviews"] = reviews
    if reviews and sub_totals:
        out["captured_subrating_averages"] = {
            k: round(sub_totals[k] / sub_counts[k], 1) for k in sub_totals
        }
    return out


def main() -> None:
    destinations = json.loads((OUT / "destinations.json").read_text())
    marshas = []
    for d in destinations:
        for h in d["hotels"]:
            if h.get("marsha") and h["marsha"].upper() not in marshas:
                marshas.append(h["marsha"].upper())
    state_file = CACHE / "reviews_state.json"
    state = {}
    if state_file.exists():
        state = json.loads(state_file.read_text())
    for marsha in marshas[:240]:
        if marsha in state:
            continue
        data = fetch_hotel_reviews(marsha, limit=MAX_REVIEWS_PER_HOTEL)
        if data is None:
            print(f"[FAIL] {marsha}", flush=True)
            time.sleep(random.uniform(2, 5))
            continue
        state[marsha] = data
        state_file.write_text(json.dumps(state, indent=1, ensure_ascii=False))
        n = len(data.get("reviews", []))
        avg = (data.get("summary") or {}).get("average")
        print(f"[ok] {marsha}: {n} reviews, avg={avg}", flush=True)
        time.sleep(random.uniform(0.8, 2.0))
    (OUT / "hotel_reviews.json").write_text(json.dumps(state, indent=1, ensure_ascii=False))
    print(f"DONE {len(state)} hotels with reviews")


if __name__ == "__main__":
    main()

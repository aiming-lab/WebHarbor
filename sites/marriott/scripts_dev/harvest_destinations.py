"""Harvest marriott.com destination pages into source_data/destinations.json.

Each destination page embeds, server-side, the full rendered "properties list"
for that city: per-hotel marsha code, brand, title, guest-rating badge, review
count, one-line description, distance from the destination, real image URLs
(cache.marriott.com renditions) and the nightly USD rate the live site quoted
for its SSR snapshot dates. All of it is captured verbatim.
"""
from __future__ import annotations

import json
import pathlib
import random
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mfetch import fetch

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "source_data"
OUT.mkdir(exist_ok=True)
CACHE = ROOT / "scraped_data" / "destination_pages"
CACHE.mkdir(parents=True, exist_ok=True)

DESTINATIONS = [
    ("new-york-city", "united-states/new-york/new-york-city"),
    ("boston", "united-states/massachusetts/boston"),
    ("chicago", "united-states/illinois/chicago"),
    ("san-francisco", "united-states/california/san-francisco"),
    ("los-angeles", "united-states/california/los-angeles"),
    ("san-diego", "united-states/california/san-diego"),
    ("miami", "united-states/florida/miami"),
    ("orlando", "united-states/florida/orlando"),
    ("fort-lauderdale", "united-states/florida/fort-lauderdale"),
    ("key-west", "united-states/florida/key-west"),
    ("tampa", "united-states/florida/tampa"),
    ("las-vegas", "united-states/nevada/las-vegas"),
    ("washington-dc", "united-states/district-of-columbia/washington-dc"),
    ("seattle", "united-states/washington/seattle"),
    ("denver", "united-states/colorado/denver"),
    ("nashville", "united-states/tennessee/nashville"),
    ("memphis", "united-states/tennessee/memphis"),
    ("austin", "united-states/texas/austin"),
    ("dallas", "united-states/texas/dallas"),
    ("houston", "united-states/texas/houston"),
    ("san-antonio", "united-states/texas/san-antonio"),
    ("atlanta", "united-states/georgia/atlanta"),
    ("savannah", "united-states/georgia/savannah"),
    ("charleston", "united-states/south-carolina/charleston"),
    ("myrtle-beach", "united-states/south-carolina/myrtle-beach"),
    ("philadelphia", "united-states/pennsylvania/philadelphia"),
    ("phoenix", "united-states/arizona/phoenix"),
    ("salt-lake-city", "united-states/utah/salt-lake-city"),
    ("minneapolis", "united-states/minnesota/minneapolis"),
    ("detroit", "united-states/michigan/detroit"),
    ("cleveland", "united-states/ohio/cleveland"),
    ("columbus", "united-states/ohio/columbus"),
    ("indianapolis", "united-states/indiana/indianapolis"),
    ("st-louis", "united-states/missouri/st-louis"),
    ("kansas-city", "united-states/missouri/kansas-city"),
    ("new-orleans", "united-states/louisiana/new-orleans"),
    ("baltimore", "united-states/maryland/baltimore"),
    ("richmond", "united-states/virginia/richmond"),
    ("raleigh", "united-states/north-carolina/raleigh"),
    ("charlotte", "united-states/north-carolina/charlotte"),
    ("pittsburgh", "united-states/pennsylvania/pittsburgh"),
    ("honolulu", "united-states/hawaii/honolulu"),
    ("maui", "united-states/hawaii/maui"),
    ("anaheim", "united-states/california/anaheim"),
    ("sacramento", "united-states/california/sacramento"),
    ("portland", "united-states/oregon/portland"),
    ("boise", "united-states/idaho/boise"),
    ("milwaukee", "united-states/wisconsin/milwaukee"),
    ("toronto", "canada/toronto"),
    ("montreal", "canada/montreal"),
    ("vancouver", "canada/vancouver"),
    ("calgary", "canada/calgary"),
    ("ottawa", "canada/ottawa"),
    ("london", "united-kingdom/london"),
    ("paris", "france/paris"),
    ("rome", "italy/rome"),
    ("milan", "italy/milan"),
    ("florence", "italy/florence"),
    ("venice", "italy/venice"),
    ("barcelona", "spain/barcelona"),
    ("madrid", "spain/madrid"),
    ("amsterdam", "netherlands/amsterdam"),
    ("dublin", "ireland/dublin"),
    ("munich", "germany/munich"),
    ("berlin", "germany/berlin"),
    ("frankfurt", "germany/frankfurt"),
    ("vienna", "austria/vienna"),
    ("zurich", "switzerland/zurich"),
    ("geneva", "switzerland/geneva"),
    ("brussels", "belgium/brussels"),
    ("copenhagen", "denmark/copenhagen"),
    ("stockholm", "sweden/stockholm"),
    ("oslo", "norway/oslo"),
    ("helsinki", "finland/helsinki"),
    ("lisbon", "portugal/lisbon"),
    ("porto", "portugal/porto"),
    ("athens", "greece/athens"),
    ("istanbul", "turkey/istanbul"),
    ("warsaw", "poland/warsaw"),
    ("prague", "czech-republic/prague"),
    ("budapest", "hungary/budapest"),
    ("tokyo", "japan/tokyo"),
    ("osaka", "japan/osaka"),
    ("kyoto", "japan/kyoto"),
    ("singapore", "singapore/singapore"),
    ("bangkok", "thailand/bangkok"),
    ("hong-kong", "mainland-china-and-hong-kong-macau-taiwan/hong-kong"),
    ("seoul", "south-korea/seoul"),
    ("taipei", "mainland-china-and-hong-kong-macau-taiwan/taipei"),
    ("dubai", "united-arab-emirates/dubai"),
    ("abu-dhabi", "united-arab-emirates/abu-dhabi"),
    ("doha", "qatar/doha"),
    ("mexico-city", "mexico/mexico-city"),
    ("cancun", "mexico/cancun"),
    ("san-juan", "puerto-rico/san-juan"),
    ("panama-city", "panama/panama-city"),
    ("san-jose-costa-rica", "costa-rica/san-jose"),
    ("buenos-aires", "argentina/buenos-aires"),
    ("sao-paulo", "brazil/sao-paulo"),
    ("rio-de-janeiro", "brazil/rio-de-janeiro"),
    ("lima", "peru/lima"),
    ("santiago", "chile/santiago"),
    ("bogota", "colombia/bogota"),
]


# slug -> the marriott.com region path (.../<country>/<state>/<city>.mi)
REGION_PATHS = {slug: path for slug, path in DESTINATIONS}


def extract_destination(html: str, slug: str) -> dict | None:
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
                  html, re.S)
    biggest = None
    for mm in re.finditer(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S):
        raw = mm.group(1).strip()
        if len(raw) > 100000:
            biggest = raw
    if not biggest:
        return None
    data = json.loads(biggest)
    pp = data.get("props", {}).get("pageProps", {})
    model = pp.get("model", {})
    meta = model.get("destinationMetaData", {}) or {}

    hotels = []
    # walk for the properties-list component
    def walk(obj):
        if isinstance(obj, dict):
            if "processedData" in obj and isinstance(obj["processedData"], dict) \
                    and isinstance(obj["processedData"].get("hotels"), list):
                for card in obj["processedData"]["hotels"]:
                    if not isinstance(card, dict):
                        continue
                    footer = card.get("footerLinkDetails", {}) or {}
                    reviews = card.get("reviewsDetails", {}) or {}
                    title = card.get("titleDetails", {}) or {}
                    images = []
                    for im in card.get("images", []) or []:
                        if isinstance(im, dict) and im.get("defaultImageUrl"):
                            images.append({
                                "url": im.get("defaultImageUrl"),
                                "alt": im.get("altText", ""),
                            })
                    link = reviews.get("reviewsLink", "")
                    import re as _re
                    slug_m = _re.search(r"/en-us/hotels/[a-z0-9]+-([a-z0-9-]+)/reviews/", link or "")
                    hotels.append({
                        "marsha": card.get("id"),
                        "slug": slug_m.group(1) if slug_m else "",
                        "title": title.get("title") or title.get("headline") or "",
                        "brandCode": card.get("brandCode"),
                        "brandId": (card.get("brandDetails", {}) or {}).get("brandId"),
                        "description": card.get("description", ""),
                        "ribbon": (card.get("ribbonDetails", {}) or {}).get("text") or "",
                        "rating": reviews.get("reviewsAvg"),
                        "reviewsText": reviews.get("reviewsText", ""),
                        "reviewsLink": reviews.get("reviewsLink", ""),
                        "milesText": reviews.get("milesText", "") or "",
                        "priceValue": footer.get("priceValue"),
                        "priceType": footer.get("priceType", ""),
                        "currency": footer.get("currency", "USD"),
                        "images": images,
                        "bookable": card.get("isHotelBookable"),
                    })
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
    walk(model)
    hero = None
    heroes = []

    def collect_hero(obj):
        if isinstance(obj, dict):
            h_ = obj.get("hero")
            if isinstance(h_, dict) and h_.get("assetPath"):
                heroes.append({
                    "url": h_["assetPath"],
                    "alt": h_.get("altText", ""),
                })
            for v in obj.values():
                collect_hero(v)
        elif isinstance(obj, list):
            for v in obj:
                collect_hero(v)

    collect_hero(model)
    hero = heroes[0] if heroes else None
    return {
        "slug": slug,
        "region_path": REGION_PATHS.get(slug, ""),
        "hero": hero,
        "city": meta.get("city"),
        "state": meta.get("state"),
        "country": meta.get("country"),
        "countryCode": meta.get("countryCode"),
        "latitude": meta.get("latitude"),
        "longitude": meta.get("longitude"),
        "destinationName": meta.get("destinationName"),
        "title": model.get("title", ""),
        "hotels": hotels,
    }


def main() -> None:
    dests = []
    for slug, path in DESTINATIONS:
        cache_file = CACHE / f"{slug}.json"
        if cache_file.exists():
            html = cache_file.read_text(errors="replace")
        else:
            url = f"https://www.marriott.com/en-us/destinations/{path}.mi"
            resp = fetch(url, tries=8)
            if resp is None:
                print(f"[FAIL] {slug}", flush=True)
                continue
            html = resp.text
            cache_file.write_text(html)
            time.sleep(random.uniform(0.6, 1.6))
        parsed = extract_destination(html, slug)
        if parsed is None or not parsed.get("hotels"):
            print(f"[empty] {slug}: no hotels extracted ({len(html)} bytes)", flush=True)
            continue
        dests.append(parsed)
        print(f"[ok] {slug}: {len(parsed['hotels'])} hotels, city={parsed.get('city')}", flush=True)
    (OUT / "destinations.json").write_text(json.dumps(dests, indent=1, ensure_ascii=False))
    codes = {}
    for d in dests:
        for h in d["hotels"]:
            codes.setdefault(h["marsha"], d["slug"])
    print(f"destinations={len(dests)} unique_hotels={len(codes)}")


if __name__ == "__main__":
    main()

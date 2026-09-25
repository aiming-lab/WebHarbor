"""Harvest per-hotel detail pages into source_data/hotel_details.json.

For every hotel discovered on the destination pages (marsha + slug from the
live site's own /en-us/hotels/<marsha>-<slug>/overview/ URL), capture:
  - the hotel's schema.org JSON-LD blob (name, description, full postal
    address, telephone, check-in/check-out, amenity list, coordinates),
  - the rendered gallery (cache.marriott.com rendition URLs + alt text),
  - the rooms-page imagery (real room photos with room-name captions).
Reviews come separately from BazaarVoice (harvest_reviews.py).
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
CACHE = ROOT / "scraped_data" / "hotel_pages"
CACHE.mkdir(parents=True, exist_ok=True)

MAX_HOTELS = 240


def slug_from_url(url: str) -> str:
    m = re.search(r"/en-us/hotels/([a-z0-9]+)-([a-z0-9-]+)/overview/", url or "")
    return m.group(2) if m else ""


def extract_hotel(html: str, marsha: str, slug: str) -> dict | None:
    ld = None
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        raw = m.group(1).strip()
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Hotel":
            ld = d
            break
    if ld is None:
        return None

    addr = ld.get("address", {}) or {}
    amenities = []
    for f in ld.get("amenityFeature", []) or []:
        if isinstance(f, dict) and f.get("value") is True and f.get("name"):
            amenities.append(f["name"])

    gallery = []
    for m in re.finditer(r'data-banner-srcset="(https://cache\.marriott\.com/[^"]+)"', html):
        url = m.group(1).split("&amp;")[0].split("?")[0]
        if url not in [g["url"] for g in gallery]:
            gallery.append({"url": url})
    for m in re.finditer(r'<img[^>]+alt="([^"]{4,120})"[^>]*src="(https://cache\.marriott\.com/[^"]+)"', html):
        alt, url = m.group(1), m.group(2).split("?")[0]
        if url not in [g["url"] for g in gallery]:
            gallery.append({"url": url, "alt": alt})
    # alt order: prefer entries with alt text first
    gallery.sort(key=lambda g: (g.get("alt") is None,))

    # rooms-page style room imagery (from the rooms subpage fetch)
    return {
        "marsha": marsha.upper(),
        "slug": slug,
        "name": ld.get("name"),
        "description": ld.get("description"),
        "address": {
            "street": addr.get("streetAddress"),
            "city": addr.get("addressLocality"),
            "region": addr.get("addressRegion"),
            "country": addr.get("addressCountry"),
            "postalCode": addr.get("postalCode"),
        },
        "phone": ld.get("telephone"),
        "checkin": ld.get("checkinTime"),
        "checkout": ld.get("checkoutTime"),
        "coords": None,
        "amenities": amenities,
        "gallery": gallery[:18],
    }


def extract_rooms(html: str) -> list:
    rooms = []
    # images with room-ish alt text on rooms pages
    for m in re.finditer(r'alt="([^"]{4,120})"[^>]*srcset="https://cache\.marriott\.com/([^" ]+)', html):
        alt, url = m.group(1), "https://cache.marriott.com/" + m.group(2).split("?")[0]
        if re.search(r"(?i)guestroom|suite|room|bedroom|king|queen|loft|penthouse|bath|living", alt):
            if alt not in [r["alt"] for r in rooms]:
                rooms.append({"url": url, "alt": alt})
    return rooms


def main() -> None:
    destinations = json.loads((OUT / "destinations.json").read_text())
    hotels = {}
    for d in destinations:
        for h in d["hotels"]:
            marsha = (h.get("marsha") or "").upper()
            if not marsha or marsha in hotels:
                continue
            slug = ""
            link = h.get("reviewsLink") or ""
            m = re.search(r"/en-us/hotels/([a-z0-9]+)-([a-z0-9-]+)/reviews/", link)
            if m and m.group(1).upper() == marsha:
                slug = m.group(2)
            if not slug:
                href = (h.get("tertiaryLinkDetails") or {}).get("href", "")
                m = re.search(r"/hotels/travel/([a-z0-9]+)-([a-z0-9-]+)", href)
                if m and m.group(1).upper() == marsha:
                    slug = m.group(2)
            hotels[marsha] = {"marsha": marsha, "title": h.get("title"), "slug": slug}
    targets = [(m, v["slug"]) for m, v in hotels.items() if v.get("slug")][:MAX_HOTELS]
    print(f"{len(hotels)} hotels discovered, {len(targets)} with slugs, taking {len(targets)}")
    details = {}
    state_file = CACHE / "hotel_details_state.json"
    if state_file.exists():
        details = json.loads(state_file.read_text())
    for marsha, slug in targets:
        if marsha in details:
            continue
        ov = fetch(f"https://www.marriott.com/en-us/hotels/{marsha.lower()}-{slug}/overview/", tries=4)
        if ov is None:
            print(f"[FAIL-ov] {marsha}", flush=True)
            time.sleep(random.uniform(20, 40))
            continue
        parsed = extract_hotel(ov.text, marsha, slug)
        if parsed is None:
            print(f"[no-ld] {marsha}", flush=True)
            (CACHE / f"{marsha}_overview.html").write_text(ov.text)
            time.sleep(random.uniform(1, 3))
            continue
        rm = fetch(f"https://www.marriott.com/en-us/hotels/{marsha.lower()}-{slug}/rooms/", tries=3)
        if rm is not None:
            parsed["rooms_imagery"] = extract_rooms(rm.text)
        details[marsha] = parsed
        state_file.write_text(json.dumps(details, indent=1, ensure_ascii=False))
        print(f"[ok] {marsha} {parsed['name']} gallery={len(parsed['gallery'])} "
              f"rooms={len(parsed.get('rooms_imagery', []))}", flush=True)
        time.sleep(random.uniform(1.0, 2.5))
    (OUT / "hotel_details.json").write_text(json.dumps(details, indent=1, ensure_ascii=False))
    print(f"DONE {len(details)} hotel details")


if __name__ == "__main__":
    main()
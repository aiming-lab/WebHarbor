#!/usr/bin/env python3
"""Harvest real qatarairways.com image assets via the Wayback Machine.

The live site sits behind Akamai (403 for datacenter IPs), so assets are
fetched through web.archive.org replays of the real CDN URLs. Every fetched
file keeps its upstream provenance in the per-run inventory JSON so the
static tree can be audited for "real images only".

Layout produced under sites/qatar_airways/static/images/:
  destinations/<IATA>/<slot>.jpg   per-destination imagery (10 slots)
  brand/<name>.<ext>               homepage/fleet/PC/baggage/... imagery
  icons_extra/<name>.<ext>         small svg/png icons referenced by pages

Slots per destination (from source_data/destination_repositories.json):
  hero overview attractions activities dining shopping h1 h2 h3 square
Card imagery (source_data/destination_cards.json) lands in the same tree as
h3 so every destination directory carries its card thumbnail.
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

SITE = pathlib.Path(__file__).resolve().parent.parent
SOURCE = SITE / "source_data"
STATIC = SITE / "static" / "images"
SCRAPE = SITE / "scraped_data"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "image/avif,image/webp,image/jpeg,image/png,*/*"}

# Slots the mirror actually renders: the guide page uses hero + the five
# section images, the cards/strip use h3. The h1/h2/square/hero_mobile
# renditions are not referenced by any template, so they are not harvested.
SLOT_FIELDS = [
    ("hero", "heroImageDesktop"),
    ("overview", "overviewImage"),
    ("attractions", "touristAttractionsImage1"),
    ("activities", "leisureActivitiesImage1"),
    ("dining", "eatingImage1"),
    ("shopping", "shoppingImage1"),
    ("h3", "horizontalImage3"),
]

# Wayback replay prefixes: 2id_ = closest capture, raw payload (no banner injection)
WB = "https://web.archive.org/web/2id_/"
WB_DIRECT = "https://web.archive.org/web/"
# Known upstream placeholder (real site uses it for sparse destinations)
SPACER_MARKERS = ("white_spacer",)

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sniff(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if len(data) > 12 and data[4:8] == b"ftyp" and b"avif" in data[8:16]:
        return "avif"
    if b"<svg" in data[:512] or data[:5] in (b"<?xml", b"<!DOC"):
        return "svg"
    return "unknown"


class Refused(Exception):
    """TCP-level refusal — the local network throttles web.archive.org."""


def _cdx_captures(url: str, timeout: int = 60, retries: int = 3) -> list[str]:
    """Status-200 capture timestamps for an upstream URL, newest first."""
    api = ("http://web.archive.org/cdx/search/cdx?url="
           + urllib.parse.quote(url, safe=":/?=&")
           + "&output=json&filter=statuscode:200&fl=timestamp&limit=50")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(api, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                rows = json.loads(r.read())
            stamps = [row[0] for row in rows[1:]] if rows and rows[0] == ["timestamp"] else []
            return sorted(stamps, reverse=True)
        except Exception:  # noqa: BLE001
            time.sleep(20 * (attempt + 1))
    return []


def wb_fetch(url: str, timeout: int = 45, retries: int = 6) -> tuple[int, bytes]:
    """Fetch the closest Wayback capture of an upstream URL.

    The egress path rate-limits web.archive.org connections; on refusal we
    back off hard (45s+) instead of hammering, which recovers reliably.
    A 404 is permanent (no capture exists) and returns immediately. When
    the closest-capture (2id_) replay is itself blocked by the Wayback edge
    (403/429/503 — seen in bursts), resolve the capture list via the CDX
    API and fetch a specific capture directly: same upstream URL, newest
    available capture, so provenance never changes.
    """
    # percent-encode non-ASCII path bytes (upstream URLs carry e.g. 'ö')
    target = WB + urllib.parse.quote(url, safe="/:%()")
    last_exc = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(target, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, b""
            last_exc = e
            if e.code in (403, 429, 503) and attempt >= 1:
                for ts in _cdx_captures(url)[:4]:
                    direct = (WB_DIRECT + ts + "id_/"
                              + urllib.parse.quote(url, safe="/:%()"))
                    try:
                        req = urllib.request.Request(direct, headers=HEADERS)
                        with urllib.request.urlopen(req, timeout=timeout) as r:
                            data = r.read()
                        if data:
                            return r.status, data
                    except Exception as e2:  # noqa: BLE001
                        last_exc = e2
                        time.sleep(5)
            time.sleep(3 * (attempt + 1))
        except urllib.error.URLError as e:
            last_exc = e
            if "Connection refused" in str(e):
                # the egress path throttles web.archive.org in short bursts;
                # a ~45s+ cooldown recovers reliably — keep retrying the SAME
                # url up to `retries` times so a transient refusal can never
                # push the harvest into a fallback (pseudo-source) write
                time.sleep(45 + 20 * attempt)
                continue
            time.sleep(3 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            last_exc = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"fetch failed after {retries}: {url}: {last_exc}")


def to_jpeg(data: bytes) -> bytes | None:
    """Convert AVIF/WebP/PNG bytes to real JPEG via ImageMagick."""
    try:
        out = subprocess.run(
            ["convert", "-", "-quality", "88", "jpg:-"],
            input=data, capture_output=True, timeout=60)
        if out.returncode == 0 and out.stdout[:3] == b"\xff\xd8\xff":
            return out.stdout
    except Exception:  # noqa: BLE001
        pass
    try:
        out = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", "pipe:0",
             "-frames:v", "1", "-q:v", "3", "-f", "image2pipe", "pipe:1"],
            input=data, capture_output=True, timeout=60)
        if out.returncode == 0 and out.stdout[:3] == b"\xff\xd8\xff":
            return out.stdout
    except Exception:  # noqa: BLE001
        pass
    return None


def load_city_index():
    """city -> [shorthand,...] and shorthand -> country for IATA resolution."""
    cities = json.loads((SOURCE / "cityList_en.json").read_text())
    by_city: dict[str, list[dict]] = {}
    for c in cities:
        code = c.get("shorthand")
        if not code:
            continue
        # city field packs aliases: "Sydney*New South Wales"
        for token in re.split(r"\*", c.get("city", "")):
            token = token.strip().lower()
            if token:
                by_city.setdefault(token, []).append(c)
    return by_city


def load_primary_index():
    """Primary city name (first alias token) -> candidate entries."""
    cities = json.loads((SOURCE / "cityList_en.json").read_text())
    by_primary: dict[str, list[dict]] = {}
    for c in cities:
        code = c.get("shorthand")
        if not code:
            continue
        primary = c.get("city", "").split("*")[0].strip().lower()
        if primary:
            by_primary.setdefault(primary, []).append(c)
    return by_primary


# Curated per-slug overrides for well-known QR stations whose city-picker
# aliases are ambiguous (e.g. Sharjah aliases "Dubai"; many Washington-state
# airports alias "Washington"). All are real QR-served airports.
SLUG_OVERRIDES = {
    "flights-to-washington": "IAD",
    "flights-to-abu-dhabi": "AUH",
    "flights-to-dubai": "DXB",
    "flights-to-sharjah": "SHJ",
    "flights-to-seattle": "SEA",
    "flights-to-new-york": "JFK",
    "flights-to-london": "LHR",
    "flights-to-london-gatwick": "LGW",
    "flights-to-doha": "DOH",
    "flights-to-tokyo": "HND",
    "flights-to-tokyo-narita": "NRT",
    "flights-to-beijing": "PKX",
    "flights-to-moscow": "SVO",
    "flights-to-st-petersburg": "LED",
    "flights-to-sao-paulo": "GRU",
    "flights-to-dusseldorf": "DUS",
    "flights-to-fort-lauderdale": "FLL",
    "flights-to-neom": "NUM",
    "flights-to-kano": "KAN",
    "flights-to-istanbul-sabiha": "SAW",
    # non-guide card cities whose city-picker feed is ambiguous (multiple
    # airports / rail codes share the city name); these are the QR stations
    "flights-to-medan": "KNO",
    "flights-to-lyon": "LYS",
    "flights-to-saint-petersburg": "LED",
    "flights-to-alicante": "ALC",
    "flights-to-gothenburg": "GOT",
    "flights-to-aberdeen": "ABZ",
    "flights-to-belfast": "BFS",
    "flights-to-newcastle": "NCL",
    "flights-to-cardiff": "CWL",
    "flights-to-glasgow-international": "GLA",
    "flights-to-luanda": "LAD",
    "flights-to-tehran": "IKA",
    "flights-to-buenos-aires": "EZE",
    "flights-to-rio-de-janeiro": "GIG",
    "flights-to-ottawa": "YOW",
    "flights-to-halifax": "YHZ",
    "flights-to-columbus": "CMH",
    "flights-to-tampa": "TPA",
    "flights-to-kansas": "MCI",
    "flights-to-detroit": "DTW",
    "flights-to-rochester": "ROC",
    "flights-to-orlando": "MCO",
    "flights-to-busan": "PUS",
}


def resolve_card_iata(card: dict, by_city: dict, network_codes: set[str],
                      network_freq: dict[str, int] | None = None,
                      by_primary: dict[str, list[dict]] | None = None,
                      repo_by_title: dict[str, str] | None = None) -> str | None:
    """Best-effort IATA for a destination card city."""
    network_freq = network_freq or {}
    by_primary = by_primary or {}
    repo_by_title = repo_by_title or {}
    city = card["city"].strip().lower()
    country = card.get("country", "").strip().lower()
    slug = card.get("slug", "")

    # 0. curated overrides for ambiguous QR stations
    if slug in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[slug]

    # 0.5 the destination guide for this city names the QR station directly
    if city in repo_by_title:
        return repo_by_title[city]

    def pick(cands):
        if not cands:
            return None
        cc = [c for c in cands if c.get("country", "").strip().lower() == country]
        pool = cc or cands
        nw = [c for c in pool if c["shorthand"] in network_codes]
        if len(nw) == 1:
            return nw[0]["shorthand"]
        if nw:
            counts = {c["shorthand"]: network_freq.get(c["shorthand"], 0) for c in nw}
            return max(sorted(counts), key=lambda k: counts[k])
        if len(pool) == 1:
            return pool[0]["shorthand"]
        return None

    # 1. primary city-name candidates beat alias matches
    hit = pick(by_primary.get(city, []))
    if hit:
        return hit
    # 2. alias-token candidates
    hit = pick(by_city.get(city, []))
    if hit:
        return hit
    # 3. special names used by the cards feed
    special = {
        "the maldives": "MLE", "siem reap (angkor)": "REP",
        "istanbul sabiha": "SAW", "seychelles": "SEZ", "the red sea": "RSI" if "RSI" in network_codes else "RED",
        "kansas": "ICT" if "ICT" in network_codes else None,
        "new york city": "JFK", "ho chi minh city": "SGN",
        "kuala lumpur": "KUL", "bali": "DPS",
    }
    if city in special and special[city]:
        return special[city]
    return None


def build_manifest():
    """Return list of dicts {url, path, kind, fallbacks}."""
    repos = json.loads((SOURCE / "destination_repositories.json").read_text())
    cards = json.loads((SOURCE / "destination_cards.json").read_text())
    catalog = json.loads((SOURCE / "flight_catalog_2026-09-24.json").read_text())
    by_city = load_city_index()
    by_primary = load_primary_index()
    repo_by_title = {}
    for _key, payload in repos.items():
        title = str(payload.get("destinationTitle", "")).strip().lower()
        if title:
            repo_by_title[title] = payload["iataCode"]
    network_codes = {f["from"] for f in catalog} | {f["to"] for f in catalog}
    network_freq: dict[str, int] = {}
    for f in catalog:
        network_freq[f["from"]] = network_freq.get(f["from"], 0) + 1
        network_freq[f["to"]] = network_freq.get(f["to"], 0) + 1

    manifest: dict[str, dict] = {}  # url -> entry
    priorities: dict[str, int] = {}  # url -> fetch priority (lower first)

    def add(url, path, kind, fallbacks=None, priority=5):
        if not url or not url.startswith("/content/dam/"):
            return
        full = "https://www.qatarairways.com" + url
        entry = manifest.get(full)
        if entry:
            if path not in [p["path"] for p in entry["paths"]]:
                entry["paths"].append({"path": path, "kind": kind})
            priorities[full] = min(priorities[full], priority)
            return
        manifest[full] = {"url": full, "paths": [{"path": path, "kind": kind}],
                          "fallbacks": fallbacks or []}
        priorities[full] = priority

    # ---- destination repositories (172) ----
    for key, d in repos.items():
        iata = d.get("iataCode")
        if not iata:
            continue
        slot_urls = {}
        for slot, field in SLOT_FIELDS:
            url = (d.get(field) or "").strip()
            slot_urls[slot] = url
        hero_mobile = (d.get("heroImageMobile") or "").strip()

        # per-slot fallback chains so a missing rendition degrades to another
        # real image of the same destination instead of a broken file
        chains = {
            "hero": ["h3", "overview"],
            "h3": ["hero", "overview"],
            "overview": ["h3", "attractions"],
            "attractions": ["overview", "h3"],
            "activities": ["overview", "h3"],
            "dining": ["overview", "h3"],
            "shopping": ["overview", "h3"],
        }
        # fetch priority: card + hero imagery first, deep guide slots later
        slot_priority = {"h3": 1, "hero": 2, "overview": 3, "attractions": 3,
                         "activities": 3, "dining": 3, "shopping": 3}
        for slot, field in SLOT_FIELDS:
            url = slot_urls.get(slot) or ""
            fallbacks = ["https://www.qatarairways.com" + slot_urls[f]
                         for f in chains.get(slot, []) if slot_urls.get(f)]
            add(url, f"destinations/{iata}/{slot}.jpg", f"dest:{slot}", fallbacks,
                priority=slot_priority.get(slot, 5))


    # ---- destination cards (253): card thumbnails as h3 ----
    card_map = {}
    for card in cards:
        iata = resolve_card_iata(card, by_city, network_codes, network_freq,
                                  by_primary, repo_by_title)
        if not iata:
            log(f"[warn] no IATA for card city {card['city']!r}; using slug dir")
            iata = card["slug"].replace("flights-to-", "")[:24]
        card_map[card["slug"]] = iata
        add(card["image"], f"destinations/{iata}/h3.jpg", "dest:card", priority=0)
    # freeze the card -> IATA resolution next to the source data so the
    # seeder and the image tree always agree
    (SOURCE / "card_iata_map.json").write_text(json.dumps(card_map, indent=1, sort_keys=True))

    # ---- brand / page imagery from scraped pages ----
    page_brand = {}
    for page in SCRAPE.glob("*.html"):
        html = page.read_text(encoding="utf-8", errors="replace")
        for u in set(re.findall(r"/content/dam/[^\"'\s\\)]+?\.(?:jpg|jpeg|png|webp|avif)", html)):
            page_brand.setdefault(u, page.stem)
    for u in sorted(page_brand):
        name = u.rsplit("/", 1)[-1]
        name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        ext = name.rsplit(".", 1)[-1].lower()
        if ext in ("webp", "avif"):
            name = name.rsplit(".", 1)[0] + ".jpg"
        add(u, f"brand/{name}", f"page:{page_brand[u]}", priority=0)

    # brand + card imagery first, then hero/overview slots, then deep guide slots
    ordered = sorted(manifest.values(),
                    key=lambda e: (priorities[e["url"]], e["url"]))
    return ordered


def is_spacer(entry) -> bool:
    return any(m in entry["url"] for m in SPACER_MARKERS)


def process(entry) -> dict:
    url = entry["url"]
    rel_primary = entry["paths"][0]["path"]
    abs_primary = STATIC / rel_primary
    # already fetched & valid?
    if abs_primary.exists() and abs_primary.stat().st_size > 300:
        with open(abs_primary, "rb") as fh:
            head = fh.read(16)
        kind = sniff(head if len(head) >= 16 else head + b"\0" * (16 - len(head)))
        if kind == "jpeg" or (is_spacer(entry) and kind != "unknown"):
            # kept files were fetched from their own upstream URL in a
            # previous run (a fallback-written file always shares bytes with
            # the winning slot's file, so pseudo-source files are exactly the
            # same-bytes/different-URL groups the audit flags — those get
            # deleted and re-fetched, never kept)
            return {"url": url, "path": rel_primary, "status": "kept",
                    "source_url": url}
    tried = [url] + [f for f in entry.get("fallbacks", [])]
    for cand in tried:
        try:
            status, data = wb_fetch(cand)
        except RuntimeError as e:
            if "Connection refused" in str(e) or "fetch failed" in str(e):
                return {"url": url, "path": rel_primary, "status": "miss", "reason": "refused"}
            log(f"[err] {e}")
            continue
        if status == 404 or not data:
            continue
        kind = sniff(data)
        if kind == "unknown" or len(data) < 200:
            continue
        if kind in ("avif", "webp"):
            conv = to_jpeg(data)
            if conv:
                data, kind = conv, "jpeg"
        if kind == "png" and rel_primary.endswith(".jpg"):
            conv = to_jpeg(data)
            if conv:
                data, kind = conv, "jpeg"
        if kind not in ("jpeg", "png", "svg"):
            continue
        for p in entry["paths"]:
            dest = STATIC / p["path"]
            # extension sanity: only .jpg paths get jpeg bytes
            if p["path"].endswith(".jpg") and kind != "jpeg":
                continue
            if p["path"].endswith((".png", ".svg")) and kind not in ("png", "svg"):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        # source_url records the URL that ACTUALLY produced these bytes: the
        # entry's own URL on the happy path, or the same-destination fallback
        # URL whose capture the bytes really came from otherwise
        return {"url": url, "path": rel_primary, "status": "fetched",
                "kind": kind, "bytes": len(data), "sha256": sha256(data),
                "source_url": cand, "fallback_used": cand != url}
    return {"url": url, "path": rel_primary, "status": "miss"}


def main() -> int:
    manifest = build_manifest()
    log(f"[harvest] manifest: {len(manifest)} unique upstream URLs")
    results = []
    done = 0
    misses = []
    pace = [2.5]  # adaptive inter-request delay
    lock = threading.Lock()

    def run_one(entry) -> dict:
        # already-fetched entries skip the throttle entirely: the re-walk of a
        # mostly-complete tree must not pay the egress pace for every keep
        primary = STATIC / entry["paths"][0]["path"]
        fast = primary.exists() and primary.stat().st_size > 300
        if not fast:
            with lock:
                time.sleep(pace[0])
        r = process(entry)
        with lock:
            if r["status"] == "miss" and r.get("reason") == "refused":
                pace[0] = min(pace[0] + 0.5, 7.0)
            elif pace[0] > 1.2:
                pace[0] = max(2.0, pace[0] - 0.04)
        return r

    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(run_one, e) for e in manifest]
        for fut in cf.as_completed(futs):
            r = fut.result()
            results.append(r)
            done += 1
            if r["status"] == "miss":
                misses.append(r)
            if done % 50 == 0:
                log(f"[harvest] {done}/{len(manifest)} (misses {len(misses)}, pace {pace[0]:.1f}s)")
    log(f"[harvest] done: {done} urls, misses {len(misses)}")
    for m in misses[:80]:
        log(f"  MISS {m['url']} -> {m['path']}")
    inv = {"schema_version": 2, "harvested_via": "web.archive.org",
           "assets": [r for r in results if r["status"] in ("fetched", "kept")]}
    out = SITE / "scripts_dev" / "runs" / "harvest_inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inv, indent=1))
    log(f"[harvest] inventory -> {out} ({len(inv['assets'])} assets)")

    # frozen per-path actual byte source map: every file on disk maps to the
    # upstream URL that really produced its bytes (own URL, or the
    # same-destination fallback URL when the main rendition has no Wayback
    # capture). Tracked in source_data/ so the seeder, the inventory builder
    # and audits all agree on provenance.
    source_map = {}
    for r in results:
        if r["status"] not in ("fetched", "kept") or not r.get("source_url"):
            continue
        entry = next(e for e in manifest if e["url"] == r["url"])
        for p in entry["paths"]:
            if (STATIC / p["path"]).is_file():
                source_map[p["path"]] = r["source_url"]
    map_out = SOURCE / "image_source_urls.json"
    map_out.write_text(json.dumps(source_map, indent=1, sort_keys=True))
    log(f"[harvest] source map -> {map_out} ({len(source_map)} paths)")
    return 0 if len(misses) < len(manifest) * 0.05 else 1


if __name__ == "__main__":
    sys.exit(main())

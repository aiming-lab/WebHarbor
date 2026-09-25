"""Download every real upstream asset into static/ and build the manifests.

- static/images/          page heroes, guide photos, press photos, project
                          images, leadership headshots, OMNY photos (HF-managed)
- static/external_cache/timetables/  the live PDF timetables served by
                          mta.info/schedules/... (HF-managed)
- static/icons/           site chrome: logo SVG, favicon, nearby-map (git)
- static/fonts/           the theme webfonts (git, already captured)
- asset_inventory.json    per-file bytes/sha256/source_url manifest for
                          static/images/ + static/external_cache/
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mfetch import fetch_binary

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "source_data"
IMG = ROOT / "static" / "images"
TT = ROOT / "static" / "external_cache" / "timetables"
ICONS = ROOT / "static" / "icons"

inventory: list[dict] = []


def slug_for(url: str, category: str) -> str:
    path = unquote(urlparse(url).path)
    name = path.rstrip("/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    # keep a compact prefix of the query to disambiguate style variants
    q = urlparse(url).query
    if q:
        digest = hashlib.sha1(q.encode()).hexdigest()[:8]
        stem, ext = name.rsplit(".", 1) if "." in name else (name, "jpg")
        name = f"{stem}_{digest}.{ext}"
    return name


def download(url: str, dest_dir: pathlib.Path, category: str, referer: str | None = None) -> str | None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{category}__{slug_for(url, category)}"
    dest = dest_dir / fname
    if dest.exists() and dest.stat().st_size > 0:
        pass
    else:
        data = fetch_binary(url, referer=referer)
        if not data or len(data) < 500:
            print(f"  FAIL {url[:90]}", flush=True)
            return None
        dest.write_bytes(data)
    inventory.append({
        "path": str(dest.relative_to(ROOT)),
        "bytes": dest.stat().st_size,
        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        "source_url": url,
    })
    return str(dest.relative_to(ROOT))


def collect_image_urls() -> dict[str, list[str]]:
    """Return category -> [urls]."""
    out: dict[str, list[str]] = {}

    content = json.loads((OUT / "content.json").read_text())
    for path, page in content.items():
        urls = []
        if page.get("hero"):
            urls.append(page["hero"])
        for b in page["blocks"]:
            if b["type"] == "image":
                for im in b.get("images", []):
                    src = im.get("src")
                    if not src:
                        continue
                    if src.startswith("/sites/"):
                        src = "https://new.mta.info" + src
                    if src.startswith("images/"):
                        src = "https://ibx.mta.info/" + src
                    urls.append(src)
        if urls:
            cat = "content_" + path.strip("/").replace("/", "_")[:40]
            out[cat] = urls

    projects = json.loads((OUT / "projects.json").read_text())
    for slug, p in projects.items():
        urls = [b["src"] for b in p["blocks"] if b["type"] == "image"
                and b.get("src") and "gstatic" not in b["src"]]
        # the IBX microsite serves its own assets from ibx.mta.info
        urls = [u.replace("https://new.mta.info/project/interborough-express/images/",
                          "https://ibx.mta.info/images/") for u in urls]
        # relative inline images live under /sites/default/files/
        urls = [f"https://new.mta.info{u}" if u.startswith("/sites/") else u for u in urls]
        if urls:
            out[f"project_{slug}"] = urls

    press = json.loads((OUT / "press_releases.json").read_text())
    for art in press:
        urls = [b["src"] for b in art["blocks"] if b["type"] == "image" and b.get("src")]
        if urls:
            slug = art["path"].rsplit("/", 1)[-1][:40]
            out[f"press_{slug}"] = urls

    out["home"] = [
        "https://files.mta.info/s3fs-public/banner/FTC_5181_desktop%20%281%29.jpg",
    ]
    return out


TIMETABLES = {
    # subway (the printable timetables served by www.mta.info/schedules/subway/...)
    "subway_1": "https://www.mta.info/schedules/subway/1-train",
    "subway_2": "https://www.mta.info/schedules/subway/2-train",
    "subway_3": "https://www.mta.info/schedules/subway/3-train",
    "subway_4": "https://www.mta.info/schedules/subway/4-train",
    "subway_5": "https://www.mta.info/schedules/subway/5-train",
    "subway_6": "https://www.mta.info/schedules/subway/6-train",
    "subway_7": "https://www.mta.info/schedules/subway/7-train",
    "subway_A": "https://www.mta.info/schedules/subway/a-train",
    "subway_C": "https://www.mta.info/schedules/subway/c-train",
    "subway_E": "https://www.mta.info/schedules/subway/e-train",
    "subway_B": "https://www.mta.info/schedules/subway/b-train",
    "subway_D": "https://www.mta.info/schedules/subway/d-train",
    "subway_F": "https://www.mta.info/schedules/subway/f-train",
    "subway_M": "https://www.mta.info/schedules/subway/m-train",
    "subway_G": "https://www.mta.info/schedules/subway/g-train",
    "subway_J": "https://www.mta.info/schedules/subway/j-train",
    "subway_L": "https://www.mta.info/schedules/subway/l-train",
    "subway_N": "https://www.mta.info/schedules/subway/n-train",
    "subway_Q": "https://www.mta.info/schedules/subway/q-train",
    "subway_R": "https://www.mta.info/schedules/subway/r-train",
    "subway_W": "https://www.mta.info/schedules/subway/w-train",
    "subway_42_st_shuttle": "https://www.mta.info/schedules/subway/42-st-shuttle",
    "subway_franklin_av_shuttle": "https://www.mta.info/schedules/subway/franklin-avenue-shuttle",
    "subway_rockaway_park_shuttle": "https://www.mta.info/schedules/subway/rockaway-park-shuttle",
    "subway_sir": "https://www.mta.info/schedules/subway/staten-island-railway",
    # LIRR branches (current timetables, effective Sept 8 - Nov 8, 2026)
    "lirr_babylon": "https://www.mta.info/schedules/lirr/babylon",
    "lirr_far_rockaway": "https://www.mta.info/schedules/lirr/far-rockaway",
    "lirr_hempstead": "https://www.mta.info/schedules/lirr/hempstead",
    "lirr_long_beach": "https://www.mta.info/schedules/lirr/long-beach",
    "lirr_montauk": "https://www.mta.info/schedules/lirr/montauk",
    "lirr_oyster_bay": "https://www.mta.info/schedules/lirr/oyster-bay",
    "lirr_port_jefferson": "https://www.mta.info/schedules/lirr/port-jefferson",
    "lirr_port_washington": "https://www.mta.info/schedules/lirr/port-washington",
    "lirr_ronkonkoma": "https://www.mta.info/schedules/lirr/ronkonkoma",
    "lirr_west_hempstead": "https://www.mta.info/schedules/lirr/west-hempstead",
    "lirr_city_zone_manhattan": "https://www.mta.info/schedules/lirr/city-zone-manhattan",
    "lirr_city_zone_brooklyn": "https://www.mta.info/schedules/lirr/city-zone-brooklyn",
    # Metro-North lines
    "mnr_hudson": "https://www.mta.info/schedules/metro-north/hudson",
    "mnr_harlem": "https://www.mta.info/schedules/metro-north/harlem",
    "mnr_new_haven": "https://www.mta.info/schedules/metro-north/new-haven",
    "mnr_new_canaan": "https://www.mta.info/schedules/metro-north/new-canaan",
    "mnr_danbury": "https://www.mta.info/schedules/metro-north/danbury",
    "mnr_waterbury": "https://www.mta.info/schedules/metro-north/waterbury",
    "mnr_port_jervis": "https://www.mta.info/schedules/metro-north/port-jervis",
    "mnr_pascack_valley": "https://www.mta.info/schedules/metro-north/pascack-valley",
}

CHROME = {
    "nearby_map.png": "https://new.mta.info/themes/custom/bootstrap_mta/images/nearby-map.png",
    "favicon.ico": "https://new.mta.info/favicon.ico",
}


def harvest():
    IMG.mkdir(parents=True, exist_ok=True)
    TT.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)

    cats = collect_image_urls()
    total = 0
    for cat, urls in cats.items():
        for url in urls:
            if "gstatic" in url:
                continue
            if download(url, IMG, cat, referer="https://new.mta.info/"):
                total += 1
    print(f"images: {total}", flush=True)

    tt_ok = 0
    for name, url in TIMETABLES.items():
        dest = TT / f"{name}.pdf"
        if not (dest.exists() and dest.stat().st_size > 10000):
            data = fetch_binary(url, referer="https://new.mta.info/schedules")
            if not data or len(data) < 10000:
                print(f"  TT FAIL {name}", flush=True)
                continue
            dest.write_bytes(data)
        inventory.append({
            "path": f"static/external_cache/timetables/{name}.pdf",
            "bytes": dest.stat().st_size,
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            "source_url": url,
        })
        tt_ok += 1
    print(f"timetables: {tt_ok}", flush=True)

    for name, url in CHROME.items():
        dest = ICONS / name
        if not dest.exists():
            data = fetch_binary(url)
            if data:
                dest.write_bytes(data)
                print("chrome:", name, len(data))

    (ROOT / "asset_inventory.json").write_text(
        json.dumps({"schema_version": 1, "asset_count": len(inventory), "assets": inventory},
                   indent=1, ensure_ascii=False))
    print(f"asset_inventory.json: {len(inventory)} assets")


if __name__ == "__main__":
    harvest()

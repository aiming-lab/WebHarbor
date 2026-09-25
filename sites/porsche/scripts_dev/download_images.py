#!/usr/bin/env python3
"""Download every managed image into static/images/ and emit asset_inventory.json.

Run from sites/porsche/:  python3.11 scripts_dev/download_images.py [--workers N]

Deterministic layout:
  static/images/models/{code}.png            model card hero (870x260 rendition)
  static/images/models/{code}_hl.svg         technical top shot
  static/images/models/{code}_g{i}.{ext}     detail-page gallery (dedup, cap 8)
  static/images/site/{key}.{ext}             homepage heroes
  static/images/vehicles/{lid}.jpg          finder vehicle (480px)
  static/images/shop/{oid}_{i}.webp         shop product photos (cap 2)
  static/images/configurator/{code}_{oid}.jpg  configurator swatches
Each file lands in asset_inventory.json with bytes + sha256 + source_url.
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "source_data"
IMG = BASE / "static" / "images"
IMG.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"


def sniff_ext(data: bytes, default: str = "jpg") -> str:
    """Detect the true image format from magic bytes (servers ignore
    the extension the URL suggested)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:8] == b"ftyp" and b"avif" in data[8:16]:
        return "avif"
    if data[:12].lstrip().startswith(b"GIF8"):
        return "gif"
    try:
        text = data.decode("utf-8")
        if "<svg" in text[:2000]:
            return "svg"
    except UnicodeDecodeError:
        pass
    return default


def fetch(url: str, dest: Path) -> tuple[str, Path, int, str, str]:
    """Fetch url; if the served format differs from dest's extension,
    rename dest to the true extension before recording."""
    probe = dest
    if probe.exists() and probe.stat().st_size > 0:
        data = probe.read_bytes()
        return url, probe, len(data), hashlib.sha256(data).hexdigest(), "cached"
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if not data:
                raise ValueError("empty body")
            dest.parent.mkdir(parents=True, exist_ok=True)
            true_ext = sniff_ext(data, default=dest.suffix.lstrip(".") or "jpg")
            if true_ext != dest.suffix.lstrip("."):
                dest = dest.with_suffix("." + true_ext)
            dest.write_bytes(data)
            return url, dest, len(data), hashlib.sha256(data).hexdigest(), "ok"
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    return url, dest, 0, "", f"ERR {last_err}"


def model_hero_url(u: str) -> str:
    """Request a bounded rendition of the images.porsche.com side shot."""
    return re.sub(r"/m/\d+x\d+/smart/filters:format\([a-z]+\)", "/m/870x260/smart/filters:format(png)", u)


def ext_for(url: str, default="jpg") -> str:
    m = re.search(r"\.(png|jpe?g|webp|svg|gif)(?:[/?]|$)", url, re.I)
    return m.group(1).replace("jpeg", "jpg") if m else default


def main():
    jobs: list[tuple[str, Path]] = []  # (url, dest)

    models = json.loads((SRC / "models.json").read_text())
    for m in models:
        code = m["modelType"]
        if m.get("image"):
            jobs.append((model_hero_url(m["image"]), IMG / "models" / f"{code}.png"))
        if m.get("highlights_image"):
            jobs.append((m["highlights_image"], IMG / "models" / f"{code}_hl.svg"))
        seen = set()
        gi = 0
        for u in m.get("page_images", [])[:14]:
            key = u.split("?")[0]
            if key in seen:
                continue
            seen.add(key)
            jobs.append((model_hero_url(u), IMG / "models" / f"{code}_g{gi}.{ext_for(u)}"))
            gi += 1
            if gi >= 8:
                break

    # homepage heroes
    home_html = (BASE / "scraped_data" / "home.html").read_text()
    heroes = {
        "hero_finder": "https://images.porsche.com/f/338913/900x675/339f80cbd0/enhanced-finder-optimized-final.jpeg/m/900x675/filters:format(webp):quality(85)",
        "hero_cayenne_gts": "https://images.porsche.com/f/338913/2000x1500/0de0708bcf/00-e3-ii-coupe-gts-fallback-desktop-optimized.jpeg/m/1200x900/filters:format(webp):quality(85)",
        "hero_contentinfo": "https://images.porsche.com/f/338913/1920x1080/1378ad4037/contentinfo_wide-16-9.jpg/m/865x486/filters:format(webp):quality(85)",
    }
    for key, u in heroes.items():
        jobs.append((u, IMG / "site" / f"{key}.{ext_for(u)}"))

    vehicles = json.loads((SRC / "vehicles.json").read_text())
    for v in vehicles:
        if v.get("image"):
            u = re.sub(r"/960$", "/480", v["image"])
            jobs.append((u, IMG / "vehicles" / f"{v['listing_id']}.jpg"))

    shop = json.loads((SRC / "shop_products.json").read_text())
    for p in shop:
        for i, u in enumerate(p.get("images", [])[:2]):
            if u:
                jobs.append((u, IMG / "shop" / f"{p['object_id']}_{i}.webp"))

    cfg = json.loads((SRC / "configurator_options.json").read_text())
    for code, opts in cfg.items():
        for o in opts:
            sw = o.get("swatch", "")
            if sw:
                if sw.startswith("/"):
                    sw = "https://configurator.porsche.com" + sw
                jobs.append((sw, IMG / "configurator" / f"{code}_{o['id']}.jpg"))

    # dedupe by (url, dest)
    seen = set()
    uniq = []
    for u, d in jobs:
        k = (u, str(d))
        if k in seen:
            continue
        seen.add(k)
        uniq.append((u, d))
    print("download jobs:", len(uniq))

    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 12
    inventory = {}
    done = 0
    errors = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch, u, d) for u, d in uniq]
        for fut in cf.as_completed(futs):
            url, dest, n, sha, status = fut.result()
            done += 1
            if status.startswith("ERR"):
                errors.append((str(dest), url, status))
            elif n:
                inventory[str(dest.relative_to(BASE))] = {
                    "path": str(dest.relative_to(BASE)),
                    "bytes": n,
                    "sha256": sha,
                    "source_url": url,
                }
            if done % 200 == 0:
                print(f"  {done}/{len(uniq)} done, {len(errors)} errors")

    print(f"DONE {done}, errors: {len(errors)}")
    for e in errors[:20]:
        print("  ERR:", e[0], e[2][:80])

    inv = sorted(inventory.values(), key=lambda a: a["path"])
    out = {"schema_version": 1, "asset_count": len(inv), "assets": inv}
    (BASE / "asset_inventory.json").write_text(json.dumps(out, indent=1))
    print("asset_inventory.json:", len(inv), "assets")


if __name__ == "__main__":
    main()

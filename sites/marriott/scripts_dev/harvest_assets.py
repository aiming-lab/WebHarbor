"""Download every referenced upstream image into the mirror's static tree.

Sources (all real cache.marriott.com assets):
  - site chrome (Bonvoy logo, favicon, Swiss 721 webfonts)   -> static/icons/
  - the live homepage hero                                    -> static/images/home/
  - destination hero images                                   -> static/images/destinations/
  - offer card images                                         -> static/images/offers/
  - per-hotel gallery + room imagery                          -> static/images/hotels/

Rendition URLs are requested at an 800px downsize (the same renditions the
live site serves); Scene7 URLs via ?wid=800. After the download sweep the
script writes asset_inventory.json (bytes + sha256 + source URL per file),
which the image build's check_asset_inventory.py gate enforces.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from mfetch import fetch  # noqa: E402
from seed_data import _mirror_image_path  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source_data"
STATIC = ROOT / "static"

# chrome assets (git-committed, not part of the HF-managed inventory)
CHROME = [
    ("https://cache.marriott.com/content/dam/marriott-digital/digital-merchandising/us-canada/en_us/logo/assets/pdt-MBE-LOGO-412171181436582.png",
     "static/icons/marriott-bonvoy-logo.png"),
    ("https://cache.marriott.com/Images/Mobile/MC_Logos/MarriottApple57x57.png",
     "static/icons/marriott-apple57.png"),
    ("https://cache.marriott.com/aka-fonts/MarriottDigital/swiss/Swiss721BT-Regular.woff2",
     "static/icons/Swiss721BT-Regular.woff2"),
    ("https://cache.marriott.com/aka-fonts/MarriottDigital/swiss/Swiss721BT-Medium.woff2",
     "static/icons/Swiss721BT-Medium.woff2"),
    ("https://cache.marriott.com/aka-fonts/MarriottDigital/swiss/Swiss721BT-Bold.woff2",
     "static/icons/Swiss721BT-Bold.woff2"),
]

HOME_HEROES = [
    ("https://cache.marriott.com/is/image/marriotts7prod/pdt-DME-City-Lights-488884856118298",
     "static/images/home/hero-city-lights.jpg"),
    ("https://cache.marriott.com/is/image/marriotts7prod/stock-beach-283862",
     "static/images/home/stock-beach.jpg"),
]


def request_url(url: str) -> str:
    """Pick the variant of the upstream URL to download."""
    if "/is/image/" in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}wid=800&fmt=jpeg"
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}output-quality=70&interpolation=progressive-bilinear&downsize=800px:*"


def download(url: str, dest: pathlib.Path, tries: int = 5) -> bool:
    dest = pathlib.Path(str(dest).replace(f"{ROOT}/", "")) if str(dest).startswith("/") else dest
    dest = ROOT / str(dest).lstrip("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 500:
        return True
    for attempt in range(tries):
        resp = fetch(request_url(url), tries=1)
        if resp is None or resp.status_code != 200 or len(resp.content) < 400:
            time.sleep(random.uniform(3, 8))
            continue
        data = resp.content
        head = data[:12]
        if head[:3] == b"\xff\xd8\xff" or head[:4] == b"RIFF" or head[:8] == b"\x89PNG\r\n\x1a\n":
            dest.write_bytes(data)
            return True
        print(f"    [not-image] {url[:80]} ({len(data)} bytes, {head[:6]!r})", flush=True)
        time.sleep(random.uniform(2, 5))
    print(f"    [FAILED] {url[:90]}", flush=True)
    return False


def main() -> None:
    inventory_rows = []

    def record(dest_rel: str, url: str):
        rel_path = dest_rel.lstrip("/")
        path = ROOT / rel_path
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        inventory_rows.append({
            "path": rel_path,
            "bytes": path.stat().st_size,
            "sha256": digest,
            "source_url": request_url(url),
        })

    # 1. chrome (fonts/favicon/logo: no image-header validation)
    for url, rel in CHROME:
        dest = ROOT / rel.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 100:
            print(f"[chrome] {rel} (cached)")
            continue
        resp = fetch(request_url(url), tries=4)
        if resp is not None and resp.status_code == 200 and len(resp.content) > 100:
            dest.write_bytes(resp.content)
            print(f"[chrome] {rel} ({len(resp.content)} bytes)")
        else:
            print(f"[chrome-FAIL] {rel}", flush=True)

    # 2. homepage heroes
    for url, rel in HOME_HEROES:
        dest = ROOT / rel
        if download(url, dest):
            record(rel, url)
            print(f"[home] {rel}")

    # 3. destination heroes
    destinations = json.loads((SOURCE / "destinations.json").read_text())
    for dest in destinations:
        hero = dest.get("hero") or {}
        url = hero.get("url")
        if not url:
            continue
        rel = _mirror_image_path(dest["slug"], url, kind="destinations")
        if download(url, ROOT / rel.lstrip("/")):
            record(rel, url)
            print(f"[dest] {dest['slug']}")
        else:
            print(f"[dest-FAIL] {dest['slug']}", flush=True)

    # 4. offers
    content = json.loads((SOURCE / "site_content.json").read_text())
    for o in content.get("offers", []):
        url = o.get("image")
        if not url:
            continue
        rel = _mirror_image_path(f"{o.get('order', 0)}", url, kind="offers")
        if download(url, ROOT / rel.lstrip("/")):
            record(rel, url)
            print(f"[offer] {o['title'][:40]}")

    # 5. hotels - card images from the destination pages (every hotel) plus
    #    the detail-harvest gallery / room imagery where captured
    card_images = {}
    for dest in destinations:
        for h in dest.get("hotels") or []:
            marsha = (h.get("marsha") or "").upper()
            if marsha and h.get("images"):
                card_images.setdefault(marsha, []).extend(h["images"])
    details = json.loads((SOURCE / "hotel_details.json").read_text()) \
        if (SOURCE / "hotel_details.json").exists() else {}
    # fold in the incremental harvester state (partial captures) the same
    # way seed_data.py does, so gallery imagery advances with the harvest
    state_path = (ROOT / "scraped_data" / "hotel_pages"
                   / "hotel_details_state.json")
    if state_path.exists():
        for marsha, row in (json.loads(state_path.read_text()) or {}).items():
            if row and not row.get("missing") and marsha not in details:
                details[marsha] = row
    n_hotel_imgs = 0
    GALLERY_CAP = 12          # keep the HF archive bounded
    for marsha in sorted(set(card_images) | set(details)):
        seen = set()
        pools = list((details.get(marsha) or {}).get("gallery") or [])[:GALLERY_CAP] \
            + card_images.get(marsha, []) \
            + list((details.get(marsha) or {}).get("rooms_imagery") or [])[:6]
        for img in pools:
            url = img.get("url")
            if not url:
                continue
            rel = _mirror_image_path(marsha, url)
            if rel in seen:
                continue
            seen.add(rel)
            if download(url, ROOT / rel.lstrip("/")):
                record(rel, url)
                n_hotel_imgs += 1
            else:
                print(f"[hotel-FAIL] {marsha} {url[:70]}", flush=True)

    # 6. write the inventory for static/images/** (HF-managed tree)
    expected = set(r["path"] for r in inventory_rows)
    actual = {
        str(p.relative_to(ROOT)) for p in (STATIC / "images").rglob("*")
        if p.is_file() and p.name != ".gitkeep"
    }
    missing = sorted(actual - expected)
    extra = sorted(expected - actual)
    if missing or extra:
        print(f"[inventory] missing={missing[:5]} extra={extra[:5]}", flush=True)
    inventory_rows = [r for r in inventory_rows if r["path"] in actual]
    inventory_rows.sort(key=lambda r: r["path"])
    (ROOT / "asset_inventory.json").write_text(json.dumps({
        "schema_version": 1,
        "asset_count": len(inventory_rows),
        "assets": inventory_rows,
    }, indent=1))
    print(f"[inventory] {len(inventory_rows)} assets; hotel images: {n_hotel_imgs}")


if __name__ == "__main__":
    main()

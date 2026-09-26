"""Download all real upstream images into static/images/ + build asset inventory.

Every file is fetched from its real i1.sndcdn.com URL (the resolved variant the
live site serves) and recorded with bytes + sha256 + source URL in
asset_inventory.json (the format scripts/check_asset_inventory.py verifies).
"""
import hashlib, json, pathlib, sys, time
from concurrent.futures import ThreadPoolExecutor
import httpx

SITE = pathlib.Path(__file__).resolve().parent.parent
SRC = SITE / "source_data"
IMG = SITE / "static" / "images"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 0  # 0 = all

tracks = json.loads((SRC / "tracks.json").read_text())
artists = json.loads((SRC / "artists.json").read_text())
playlists = json.loads((SRC / "playlists.json").read_text())
comments = json.loads((SRC / "comments.json").read_text())

jobs = []  # (relpath, url)

def variant(url, size):
    if not url:
        return None
    return re.sub(r"-(?:large|original|t\d+x\d+)\.(jpg|png|gif)$", f"-{size}.\\1", url) if (re := __import__("re")) else url

import re as _re
def variant(url, size):
    if not url:
        return None
    u = _re.sub(r"-(?:large|original|t\d+x\d+)\.(jpg|png|gif)$", f"-{size}.\\1", url)
    return u

for t in tracks:
    u = variant(t["artwork_url"], "t500x500")
    if u:
        jobs.append((f"tracks/{t['id']}.jpg", u))
jobs.append(("avatars/_default.png", "https://a1.sndcdn.com/images/default_avatar_large.png"))
for a in artists:
    if "default_avatar" in (a.get("avatar_url") or ""):
        continue
    u = variant(a["avatar_url"], "t200x200")
    if u:
        ext = ".png" if u.endswith(".png") else ".jpg"
        jobs.append((f"avatars/{a['permalink']}{ext}", u))
    if a.get("banner"):
        b = "https://i1.sndcdn.com/" + a["banner"]
        u = variant(b, "t1240x260")
        if u:
            ext = ".png" if u.endswith(".png") else ".jpg"
            jobs.append((f"banners/{a['permalink']}{ext}", u))
for p in playlists:
    u = variant(p["artwork_url"], "t500x500")
    if u:
        jobs.append((f"playlists/{p['id']}.jpg", u))
seen_commenter = set()
for c in comments:
    pl = c["user_permalink"]
    if pl and pl not in seen_commenter:
        seen_commenter.add(pl)
        if "default_avatar" in (c.get("user_avatar") or ""):
            continue
        u = variant(c["user_avatar"], "t50x50")
        if u:
            ext = ".png" if u.endswith(".png") else ".jpg"
            jobs.append((f"commenters/{pl}{ext}", u))

if LIMIT:
    jobs = jobs[:LIMIT]
print("download jobs:", len(jobs))

results = []
def fetch(job):
    rel, url = job
    out = IMG / rel
    if out.exists() and out.stat().st_size > 0:
        return rel, url, True
    out.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        try:
            with httpx.Client(timeout=40, follow_redirects=True, headers=UA) as cx:
                r = cx.get(url)
                if r.status_code == 200 and len(r.content) > 100:
                    out.write_bytes(r.content)
                    return rel, url, True
                if r.status_code == 429:
                    time.sleep(2 + attempt * 3)
                else:
                    time.sleep(0.5)
        except Exception:
            time.sleep(1.5)
    return rel, url, False

ok = fail = 0
with ThreadPoolExecutor(max_workers=8) as ex:
    for i, (rel, url, success) in enumerate(ex.map(fetch, jobs)):
        if success:
            ok += 1
        else:
            fail += 1
            results.append((rel, url))
        if (i + 1) % 500 == 0:
            print(f"[dl {i+1}/{len(jobs)}] ok={ok} fail={fail}")
print(f"downloaded ok={ok} fail={fail}")

# inventory
inv = {
    "schema_version": 1,
    "site": "soundcloud",
    "assets": [],
    "captured_on": "2026-09-26",
    "capture_method": "api-v2.soundcloud.com metadata + direct HTTP fetch of the resolved i1.sndcdn.com media variants the live site serves",
    "source_page": "https://soundcloud.com/",
    "notes": [
        "Every managed file under static/images/ is a real upstream image fetched from i1.sndcdn.com (track artworks at t500x500, artist avatars at t200x200, artist banners at t1240x260, playlist covers at t500x500, commenter avatars at t50x50).",
        "The seed database is deterministically generated at image build time from the tracked source_data/*.json snapshots (see .build-generated-seed).",
        "Per-file byte size and sha256 are verified by scripts/check_asset_inventory.py during the Docker build.",
    ],
}
count = 0
for path in sorted(IMG.rglob("*")):
    if not path.is_file() or path.name == ".gitkeep":
        continue
    rel = "static/images/" + path.relative_to(IMG).as_posix()
    data = path.read_bytes()
    # find source url
    src_url = None
    rel_posix = path.relative_to(IMG).as_posix()
    for r, u in jobs:
        if r == rel_posix:
            src_url = u
            break
    if not src_url:
        print("WARN no source for", rel)
        continue
    inv["assets"].append({
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "source_url": src_url,
    })
    count += 1
inv["asset_count"] = count
inv["total_bytes"] = sum(a["bytes"] for a in inv["assets"])
(SITE / "asset_inventory.json").write_text(json.dumps(inv, indent=1))
print(f"inventory: {count} assets, {inv['total_bytes']//1024//1024} MB")

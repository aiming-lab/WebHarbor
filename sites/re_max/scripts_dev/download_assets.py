"""Stage 6: download all real upstream images into static/images/ + build manifest."""
import concurrent.futures as cf
import hashlib, json, pathlib, re, sys

import httpx

SITE = pathlib.Path(__file__).resolve().parent.parent
RAW = SITE / "scraped_data" / "raw"
IMG = SITE / "static" / "images"
IMG.mkdir(parents=True, exist_ok=True)

STATIC_ASSETS = {
    "brand/REMAX-logo.svg": "https://static-images.remax.com/assets/web/branding/REMAX-logo.svg?format=auto",
    "brand/property-fallback.png": "https://static-images.remax.com/assets/web/rmx-design-system/images/property-fallback.png?format=auto",
    "brand/remax-find-agent.png": "https://static-images.remax.com/assets/web/rmx-design-system/images/remax-find-agent.png?format=auto",
    "brand/childrens-miracle-white.svg": "https://static-images.remax.com/assets/web/rmx-design-system/images/childrens-miracle-white.svg?format=auto",
    "brand/remax-commercial-outline.png": "https://static-images.remax.com/assets/web/rmx-design-system/images/remax-commercial-outline.png?format=auto",
    "brand/remax-collection-outline.png": "https://static-images.remax.com/assets/web/rmx-design-system/images/remax-collection-outline.png?format=auto",
    "homepage/us-pacific-hero.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/heroCarousel/pacific/us-pacific-hero.jpg?width=2160&height=987&fit=cover&format=auto",
    "homepage/golf_lifestyle.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/collection/golf_lifestyle.jpg?width=840&format=auto",
    "homepage/global-listings.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/personas/globalListings/globalLisitngsPersonaImage1.jpg?width=840&format=auto",
    "homepage/first-time-buyer.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/personas/fthb/fthb3.jpg?width=840&format=auto",
    "homepage/move-up-buyer.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/personas/moveup/moveup3.jpg?width=840&format=auto",
    "homepage/rental-persona.png": "https://static-images.remax.com/assets/web/homepage/rental-persona.png?format=auto",
    "homepage/home-hq-bg.png": "https://static-images.remax.com/assets/web/rmx-design-system/images/home-hq-bg.png?format=auto",
    "homepage/advice-choosing-an-agent.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/advice/choosing-an-agent.jpg?crop=3:2,smart&width=840&format=auto",
    "homepage/advice-starter-home-tips.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/advice/starter-home-tips.jpg?crop=3:2,smart&width=840&format=auto",
    "homepage/advice-due-diligence.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/advice/due-diligence.jpg?crop=3:2,smart&width=840&format=auto",
    "homepage/advice-buyers-guide.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/advice/buyers-guide.jpg?crop=3:2,smart&width=840&format=auto",
    "homepage/advice-sellers-guide.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/advice/sellers-guide.jpg?crop=3:2,smart&width=840&format=auto",
    "homepage/advice-staging-to-sell.jpg": "https://static-images.remax.com/assets/web/rmx-design-system/images/homepage/advice/staging-to-sell.jpg?crop=3:2,smart&width=840&format=auto",
}

manifest = []


def fetch(client, url, dest):
    dest = IMG / dest
    if dest.exists() and dest.stat().st_size > 0:
        return dest, dest.stat().st_size, None
    try:
        r = client.get(url, timeout=45)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return dest, len(r.content), url
    except Exception as e:
        return dest, 0, f"{type(e).__name__}: {str(e)[:80]} (url={url[:90]})"


def record(dest, url):
    data = (IMG / dest).read_bytes()
    manifest.append({
        "path": f"static/images/{dest}",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "source_url": url.split("?")[0],
    })


def main():
    jobs = []
    # 1. static assets
    for dest, url in STATIC_ASSETS.items():
        jobs.append((url, dest))

    # 2. listing card photos (all SRP listings)
    ldp_urls = set()
    ldp = json.loads((RAW / "ldp_all.json").read_text())
    for r in ldp:
        ldp_urls.add(r["url"])
    for f in sorted(RAW.glob("srp_*.json")):
        d = json.loads(f.read_text())
        for l in d["listings"]:
            if not l.get("photo"):
                continue
            mls = l.get("mls") or re.sub(r"\D", "", l["url"].split("/")[-1])[-8:]
            city = (l.get("city") or "").lower().replace(" ", "_")
            jobs.append((l["photo"], f"listings/{city}_{mls}/card.jpg"))

    # 3. gallery extras for detailed LDPs (+3 each at 600x400)
    for r in ldp:
        mls = (r.get("srp") or {}).get("mls") or re.sub(r"\D", "", r["url"].split("/")[-1])[-8:]
        city = ((r.get("srp") or {}).get("city") or "").lower().replace(" ", "_")
        for i, g in enumerate((r.get("gallery") or [])[:4]):
            if i == 0:
                continue  # card already covers photo #1
            jobs.append((g + "?d=600x400", f"listings/{city}_{mls}/gallery_{i}.jpg"))
        # hero at higher res for the first detailed listing? keep uniform: skip

    # 4. agents
    agents = json.loads((RAW / "agents_detail.json").read_text())
    for a in agents:
        pid = a["url"].rstrip("/").split("/")[-1]
        if a.get("photo"):
            jobs.append((a["photo"], f"agents/{pid}.jpg"))

    # 5. offices
    offices = json.loads((RAW / "offices_detail.json").read_text())
    for o in offices:
        oid = o["url"].rstrip("/").split("/")[-1]
        oid = re.sub(r"\D", "", oid)
        if o.get("photo"):
            jobs.append((o["photo"], f"offices/{oid}.jpg"))
        else:
            jobs.append((f"https://papiphotos.remax-im.com/Office/{oid}/MainPhoto_cropped/MainPhoto_cropped.jpg", f"offices/{oid}.jpg"))

    # 6. blog images
    blog = json.loads((RAW / "blog_posts.json").read_text())
    for bp in blog:
        slug = bp["url"].rstrip("/").split("/")[-1]
        if bp.get("img"):
            jobs.append((bp["img"], f"blog/{slug}.jpg"))

    print(f"[jobs] {len(jobs)}")
    manifest_path = SITE / "image_manifest.json"
    done_urls = set()
    if manifest_path.exists():
        for m in json.loads(manifest_path.read_text()):
            done_urls.add(m["source_url"])
    errors = []
    with httpx.Client(follow_redirects=True, timeout=45, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}) as cx:
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            futs = {ex.submit(fetch, cx, u, d): (u, d) for u, d in jobs}
            n = 0
            for fut in cf.as_completed(futs):
                u, d = futs[fut]
                dest, size, err = fut.result()
                n += 1
                if err:
                    errors.append(err)
                if n % 100 == 0:
                    print(f"  {n}/{len(jobs)}")
    # rebuild manifest from disk
    manifest = []
    for u, d in jobs:
        p = IMG / d
        if p.exists() and p.stat().st_size > 0:
            record(d, u)
    manifest_path.write_text(json.dumps(manifest, indent=1))
    total = sum(m["bytes"] for m in manifest)
    print(f"[manifest] {len(manifest)} files, {total/1e6:.1f} MB")
    print(f"[errors] {len(errors)}")
    for e in errors[:10]:
        print("  ", e)


if __name__ == "__main__":
    main()

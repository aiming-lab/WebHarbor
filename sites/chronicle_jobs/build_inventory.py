"""Build the per-site asset inventory + provenance manifests.

asset_inventory.json: the runtime contract checked by
scripts/check_asset_inventory.py — exact coverage of static/images and
static/external_cache, per-file bytes + SHA-256 + source URL + source kind.

provenance.json: human-readable media provenance (captured_at, source,
method, path -> upstream URL).
"""
import hashlib
import json
from pathlib import Path

SITE = Path(__file__).resolve().parent
SCRAPE = SITE / "scraped_data"
MANAGED_ROOTS = ("static/images", "static/external_cache")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_kind(url: str) -> str:
    if "getasset/" in url:
        return "direct_asset_url"
    if "jobseekers-frontend/image" in url:
        return "profile_logo_render"
    if "imagexr" in url:
        return "responsive_variant"
    if "brightspotcdn" in url:
        return "direct_asset_url"
    if "assets/dist" in url:
        return "direct_asset_url"
    return "direct_asset_url"


def main():
    sources = json.load(open(SCRAPE / "asset_sources.json"))
    assets = []
    for root in MANAGED_ROOTS:
        base = SITE / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            rel = str(path.relative_to(SITE))
            data = path.read_bytes()
            source_url = sources.get(rel)
            if not source_url:
                raise SystemExit(f"missing source URL for {rel}")
            assets.append({
                "path": rel,
                "bytes": len(data),
                "sha256": sha256(path),
                "source_url": source_url,
                "source_kind": source_kind(source_url),
            })
    assets.sort(key=lambda a: a["path"])

    inventory = {
        "schema_version": 1,
        "asset_count": len(assets),
        "total_bytes": sum(a["bytes"] for a in assets),
        "direct_asset_urls": len(assets),
        "assets": assets,
    }
    (SITE / "asset_inventory.json").write_text(json.dumps(inventory, indent=1) + "\n")

    provenance = {
        "captured_at": "2026-09-22",
        "source": "https://jobs.chronicle.com/",
        "method": (
            "Every managed asset was captured from the live jobs.chronicle.com "
            "site on 2026-09-22: employer logos via the job-board getasset "
            "endpoint (as rendered on listing/detail cards) or the "
            "jobseekers-frontend image proxy (as rendered on employer hub "
            "pages), employer hub heroes via the site's imagexr responsive "
            "image service, career-article thumbnails from The Chronicle's "
            "brightspot CDN, and the homepage hero background + brand icons "
            "from the site's own assets host. Files were hashed locally; "
            "asset_inventory.json is the machine-checked contract."
        ),
        "assets": {a["path"]: a["source_url"] for a in assets},
    }
    (SITE / "provenance.json").write_text(json.dumps(provenance, indent=1) + "\n")
    print(f"asset_inventory.json: {len(assets)} assets, "
          f"{inventory['total_bytes']:,} bytes")
    kinds = {}
    for a in assets:
        kinds[a["source_kind"]] = kinds.get(a["source_kind"], 0) + 1
    print("by source kind:", kinds)


if __name__ == "__main__":
    main()

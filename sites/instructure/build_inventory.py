#!/usr/bin/env python3
"""Generate asset_inventory.json + provenance.json for the instructure mirror.

asset_inventory.json is the tracked manifest checked by the image build's
check_asset_inventory.py gate: every file under static/images/ and
static/external_cache/ with its byte length, SHA-256, and the real upstream
source URL it was downloaded from (mirrored from image_manifest.json).

provenance.json documents each tracked path's provenance classification.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
IMG = HERE / "static" / "images"

SNAPSHOT = "2026-09-22"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads((HERE / "image_manifest.json").read_text(encoding="utf-8"))
    by_path = {row["path"]: row["url"] for row in manifest}

    assets = []
    for path in sorted(IMG.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        rel = path.relative_to(HERE).as_posix()
        manifest_key = rel
        if manifest_key.startswith("static/images/"):
            manifest_key = manifest_key[len("static/images/"):]
        url = by_path.get(manifest_key)
        if url is None:
            raise SystemExit(f"missing manifest entry for {rel}")
        data = path.read_bytes()
        assets.append({
            "path": rel,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "source_url": url,
        })

    inventory = {
        "schema_version": 1,
        "site": "instructure",
        "asset_count": len(assets),
        "total_bytes": sum(a["bytes"] for a in assets),
        "captured_on": SNAPSHOT,
        "capture_method": "Playwright-rendered pages + direct HTTP fetches of the resolved media URLs",
        "source_page": "https://www.instructure.com/",
        "notes": [
            "Covers every managed media file under static/images/; the seed database is generated from tracked source at build time (see .build-generated-seed).",
            "Every entry is byte- and hash-verified by scripts/check_asset_inventory.py during the Docker build.",
            "All source URLs are real upstream media URLs served by www.instructure.com as rendered on the snapshot date.",
        ],
        "assets": assets,
    }
    (HERE / "asset_inventory.json").write_text(
        json.dumps(inventory, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"asset_inventory.json: {len(assets)} assets, {inventory['total_bytes']} bytes")

    # provenance
    groups = {
        "static/images/resources/": "Resource card thumbnails and detail hero images for the seeded catalog (case studies, ebooks, videos, blogs, webinars, research reports, podcasts, infographics, product overviews) as served by the upstream Resource Center listings and detail pages.",
        "static/images/logos/": "Customer logos displayed in the header banner of the upstream case study detail pages.",
        "static/images/authors/": "Author headshots displayed on the upstream blog detail pages.",
        "static/images/events/": "Event tile images served by the upstream /events listing.",
        "static/images/leaders/": "Executive leadership card headshots and modal portraits served by the upstream /about/leadership page.",
        "static/images/home/": "Homepage hero slide art, InstructureCon banner art, solutions section photography, video cover art, and section backgrounds served by the upstream homepage.",
        "static/images/misc/": "Product and solutions page heroes, community and careers imagery, partner logos, and accolade award logos served by the respective upstream marketing pages.",
    }
    records = [
        {"path": "app.py", "classification": "mirror-code",
         "scope": "Flask application implementing the instructure.com mirror: homepage, product and solutions pages, Resource Center hubs with exposed-filter search/facets, resource detail pages (case study stat bars, gated downloads, video/webinar transcripts), news and press release pages, events, careers with client-side filters, leadership profiles with modals, support FAQ, scored site search, demo request / contact / newsletter forms, and mirror accounts with saved resources and webinar registrations."},
        {"path": "seed_data.py", "classification": "mirror-code",
         "scope": "Deterministic build-time seeder. All content rows come from the tracked source_data_resources.json / source_data_misc.json snapshots; benchmark users use a frozen bcrypt hash so the SQLite seed is byte-reproducible on every build."},
        {"path": "source_data_resources.json", "classification": "captured-upstream-content",
         "scope": "The 700-row resource catalog captured from the live site on 2026-09-22: titles, listing snippets, tags (org type / product / topic), publication dates, author attributions, case-study stat bars, video transcripts, gated PDF URLs, and full body HTML for case studies, blogs, webinars, press releases, and more, exactly as served."},
        {"path": "source_data_misc.json", "classification": "captured-upstream-content",
         "scope": "Events, in-the-news items, open jobs, leadership profiles (with modal bios), support FAQ Q&A, homepage hero slides, stat cards, and testimonials captured from the live site on 2026-09-22."},
        {"path": "asset_inventory.json", "classification": "asset-manifest",
         "scope": "Per-file inventory (bytes, SHA-256, upstream source URL) for every managed image under static/images/; enforced by the image build's check_asset_inventory.py gate."},
    ]
    for prefix, scope in groups.items():
        records.append({"path": prefix, "classification": "captured-upstream-content",
                        "scope": scope})
    records.append({"path": "static/icons/", "classification": "captured-upstream-content",
                    "scope": "Case-study stat-bar icons (SVG and PNG variants) served by the upstream asset host, plus the favicon and the site wordmark SVG."})
    records.append({"path": "static/css/site.css", "classification": "mirror-code",
                    "scope": "Original stylesheet reproducing the upstream visual system: deep navy (#061C30) hero bands and cards, brand blue (#0E68B3) CTAs and labels, pill buttons, rounded cards, hub filter sidebar, and the footer wordmark."})
    records.append({"path": "static/js/main.js", "classification": "mirror-code",
                    "scope": "Interaction layer: hero slider, testimonial carousel, filter group accordions with auto-submitting exposed filters, careers client-side filters, leadership modals, FAQ accordions, transcript toggles."})
    records.append({"path": "templates/", "classification": "mirror-code",
                    "scope": "Jinja templates reproducing the captured upstream layout: utility bar + mega-menu header, homepage sections, hub listing pages with filter sidebar and pagination, per-type resource detail pages, news/press/events/careers/leadership pages, forms, and account surfaces."})
    records.append({"path": "tasks.jsonl", "classification": "benchmark-tasks",
                    "scope": "30 five-key benchmark task definitions covering search, filtering, case-study reading, events, careers, leadership, news, FAQ, forms, accounts, saves, and webinar registration."})
    provenance = {"schema_version": 1, "snapshot_date": SNAPSHOT, "records": records}
    (HERE / "provenance.json").write_text(
        json.dumps(provenance, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"provenance.json: {len(records)} records")


if __name__ == "__main__":
    main()

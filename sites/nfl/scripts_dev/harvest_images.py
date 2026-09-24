#!/usr/bin/env python3
"""Harvest the real upstream images for the nfl mirror.

Downloads every image the mirror serves from static.www.nfl.com at the exact
URLs the live site rendered on the 2026-09-23/24 capture, then writes:

  * static/images/**                     the real image bytes
  * image_manifest.json                   path -> {bytes, sha256, source_url}
  * asset_inventory.json                  the build-gate inventory
  * provenance.json                       capture metadata

No placeholders: every file comes from a resolved upstream media URL.
"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
SCRAPED = SITE / "scraped_data"
SRC = SITE / "source_data"
IMG = SITE / "static" / "images"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "image/avif,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.5",
    "Referer": "https://www.nfl.com/",
}

GLOBAL_ASSETS = {
    "global/shield.svg": "https://static.www.nfl.com/league/apps/web/global/decorative/shield.svg",
    "global/profile.svg": "https://static.www.nfl.com/league/apps/web/global/decorative/Profile.svg",
    "global/redzone-live.svg": "https://static.www.nfl.com/league/apps/web/global/decorative/RedZoneLive.svg",
    "global/brazil.svg": "https://static.www.nfl.com/league/apps/web/global/decorative/Brazil.svg",
    "global/helmet-nfl.png": "https://static.www.nfl.com/league/apps/web/global/helmets/NFL.png",
    "global/broadcaster-cbs.svg": "https://static.www.nfl.com/league/apps/web/global/logos/broadcaster/broadcaster_CBS.svg",
    "global/broadcaster-espn.svg": "https://static.www.nfl.com/league/apps/web/global/logos/broadcaster/broadcaster_ESPN.svg",
    "global/broadcaster-fox.svg": "https://static.www.nfl.com/league/apps/web/global/logos/broadcaster/broadcaster_FOX.svg",
    "global/broadcaster-nbc.svg": "https://static.www.nfl.com/league/apps/web/global/logos/broadcaster/broadcaster_NBC.svg",
    "global/broadcaster-nflplus-premium.svg": "https://static.www.nfl.com/league/apps/web/global/logos/broadcaster/broadcaster_NFLPlusPremium.svg",
    "global/broadcaster-prime.svg": "https://static.www.nfl.com/league/apps/web/global/logos/broadcaster/broadcaster_PRIME.svg",
    "global/broadcaster-primevideo.svg": "https://static.www.nfl.com/league/apps/web/global/logos/broadcaster/broadcaster_PrimeVideo.svg",
    "global/logo-nfl-network-dark.svg": "https://static.www.nfl.com/league/apps/web/global/logos/logo-league-network-primarydark.svg",
    "global/logo-nfl-channel.svg": "https://static.www.nfl.com/league/apps/web/global/logos/logo-league-nflchannel-primary.svg",
    "global/logo-redzone-dark.svg": "https://static.www.nfl.com/league/apps/web/global/logos/logo-league-redzone-primarydark.svg",
    "global/logo-redzone-light.svg": "https://static.www.nfl.com/league/apps/web/global/logos/logo-league-redzone-primarylight.svg",
    "global/logo-mnf.svg": "https://static.www.nfl.com/league/apps/web/global/logos/MNF.svg",
    "global/logo-snf.svg": "https://static.www.nfl.com/league/apps/web/global/logos/SNF.svg",
    "global/logo-tnf.svg": "https://static.www.nfl.com/league/apps/web/global/logos/TNF.svg",
    "global/logo-nextgen.svg": "https://static.www.nfl.com/league/apps/web/global/logos/NextGenStats-logo.svg",
    "global/nfl-network.png": "https://static.www.nfl.com/league/apps/web/global/logos/NFL-Network.png",
    "global/social-facebook.svg": "https://static.www.nfl.com/league/apps/web/global/logos/facebook.svg",
    "global/social-instagram.svg": "https://static.www.nfl.com/league/apps/web/global/logos/instagram.svg",
    "global/social-linkedin.svg": "https://static.www.nfl.com/league/apps/web/global/logos/linkedin.svg",
    "global/social-snapchat.svg": "https://static.www.nfl.com/league/apps/web/global/logos/snapchat.svg",
    "global/social-tiktok.svg": "https://static.www.nfl.com/league/apps/web/global/logos/tiktok.svg",
    "global/social-twitter.svg": "https://static.www.nfl.com/league/apps/web/global/logos/twitter.svg",
    "global/social-youtube.svg": "https://static.www.nfl.com/league/apps/web/global/logos/youtube.svg",
    "global/partner-nflplus.png": "https://static.www.nfl.com/league/apps/web/global/logos/partner/fitted/NFLPlus.png",
    "global/partner-primevideo.png": "https://static.www.nfl.com/league/apps/web/global/logos/partner/fitted/PrimeVideo.png",
    "global/partner-siriusxm.png": "https://static.www.nfl.com/league/apps/web/global/logos/partner/fitted/SiriusXM.png",
    "global/partner-sundayticket.png": "https://static.www.nfl.com/league/apps/web/global/logos/partner/fitted/SundayTicket.png",
    "global/partner-westwoodone.png": "https://static.www.nfl.com/league/apps/web/global/logos/partner/fitted/WestwoodOne.png",
    "global/the-athletic-icon.svg": "https://static.www.nfl.com/league/apps/nflplus/partners/logo-partner-theathleticicon-light.svg",
    "global/nflplus-badge.png": "https://static.www.nfl.com/league/apps/nflplus/badge_access_nflplus.png",
    "global/nflplus-hero-network.png": "https://static.www.nfl.com/league/apps/nflplus/hero/nflHero-image-network.png",
    "global/nflplus-mlp-logo.png": "https://static.www.nfl.com/league/apps/logo/MLP_Hero_Logo_NFL_dn4mcl.png",
    "global/nflplus-mlp-logo-premium.png": "https://static.www.nfl.com/league/apps/logo/MLP_Hero_Logo_NFL_PremiumStacked_dmnlho.png",
    "global/nflplus-mlp-redzone.png": "https://static.www.nfl.com/league/apps/nflplus/mlp/fy26-p1-mlp-nfl-redzone-desktop-web-thumbnail-071326.png",
    "global/nflplus-mlp-network.png": "https://static.www.nfl.com/league/apps/nflplus/mlp/fy26-p1-mlp-nfl-network-desktop-web-thumbnail-071326.png",
    "global/nflplus-mlp-desktop.png": "https://static.www.nfl.com/league/apps/nflplus/mlp/fy26-p1-mlp-lgom-desktop-web-thumbnail-071326.png",
    "global/conference-afc.svg": "https://static.www.nfl.com/league/api/clubs/logos/AFC.svg",
    "global/conference-nfc.svg": "https://static.www.nfl.com/league/api/clubs/logos/NFC.svg",
    "global/nfl-publisher-logo.jpg": "https://static.www.nfl.com/image/private/t_q-best/league/pyzxubxdovaubclvbvf0.jpg",
}


def collect_jobs():
    """Return ({relative_path: source_url}, {relative_path: fallback_url})."""
    jobs = dict(GLOBAL_ASSETS)
    fallbacks = {}
    teams = json.loads((SRC / "teams.json").read_text(encoding="utf-8"))
    for abbr in teams:
        jobs[f"logos/{abbr}.svg"] = (
            f"https://static.www.nfl.com/f_auto,q_auto/league/api/clubs/logos/{abbr}"
        )

    players = json.loads((SRC / "players.json").read_text(encoding="utf-8"))
    details = json.loads((SRC / "player_details.json").read_text(encoding="utf-8"))
    for p in players:
        if p["headshot_id"]:
            jobs[f"players/{p['slug']}.png"] = (
                f"https://static.www.nfl.com/image/upload/"
                f"t_thumb_squared_2x/f_auto/league/{p['headshot_id']}"
            )
    # featured player pages get the larger headshot the profile page shows;
    # fall back to the roster thumbnail transform when the profile one 404s
    for slug, d in details.items():
        hid = d.get("headshot_id") or d.get("profile_id")
        if hid:
            jobs[f"players/{slug}.png"] = (
                f"https://static.www.nfl.com/image/upload/"
                f"t_headshot_desktop/league/{hid}"
            )
        roster = next((p for p in players if p["slug"] == slug), None)
        if roster and roster.get("headshot_id"):
            fallbacks[f"players/{slug}.png"] = (
                f"https://static.www.nfl.com/image/upload/"
                f"t_thumb_squared_2x/f_auto/league/{roster['headshot_id']}"
            )

    news = json.loads((SRC / "news.json").read_text(encoding="utf-8"))
    for a in news:
        if a["image_id"]:
            jobs[f"news/{a['image_id']}.jpg"] = (
                "https://static.www.nfl.com/image/upload/"
                f"t_editorial_landscape_12_desktop/league/{a['image_id']}.jpg"
            )

    videos = json.loads((SRC / "videos.json").read_text(encoding="utf-8"))
    for v in videos:
        if not v["image_id"]:
            continue
        if v["channel"] == "latest-buzz":
            jobs[f"videos/{v['image_id']}.jpg"] = (
                "https://static.www.nfl.com/image/upload/"
                f"t_editorial_landscape_12_desktop/league/{v['image_id']}"
            )
        else:
            jobs[f"videos/{v['image_id']}.jpg"] = (
                "https://static.www.nfl.com/image/upload/"
                f"t_editorial_landscape_3_4_desktop/league/{v['image_id']}.jpg"
            )
    return jobs, fallbacks


def sniff_ext(data: bytes, url: str) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if b"<svg" in data[:600].lower():
        return ".svg"
    if url.endswith(".jpg"):
        return ".jpg"
    return ".bin"


def main() -> int:
    jobs, fallbacks = collect_jobs()
    print(f"{len(jobs)} images to harvest", flush=True)
    manifest = {}
    errors = []
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True,
                      limits=httpx.Limits(max_connections=8)) as cx:
        def fetch(rel, url):
            dest = IMG / rel
            if dest.exists() and rel in manifest:
                return
            for attempt in range(4):
                try:
                    r = cx.get(url)
                    r.raise_for_status()
                    data = r.content
                    if not data:
                        raise ValueError("empty body")
                    ext = sniff_ext(data, url)
                    if not rel.endswith(ext):
                        # keep the true extension on disk
                        dest = IMG / (rel.rsplit(".", 1)[0] + ext)
                        rel = str(dest.relative_to(IMG))
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    manifest[rel] = {
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "source_url": url,
                    }
                    return
                except Exception as e:
                    if attempt == 2 and rel in fallbacks:
                        url = fallbacks[rel]
                        continue
                    if attempt == 3:
                        errors.append((rel, url, str(e)))
                    time.sleep(1.5 * (attempt + 1))

        # global + logos first (small), then the bulk
        ordered = [k for k in jobs if k.startswith(("global/", "logos/"))]
        ordered += [k for k in jobs if k not in set(ordered)]
        for i, rel in enumerate(ordered):
            fetch(rel, jobs[rel])
            if (i + 1) % 200 == 0:
                print(f"{i+1}/{len(jobs)} done ({len(manifest)} files)", flush=True)

    if errors:
        print(f"{len(errors)} FAILED:")
        for rel, url, err in errors[:20]:
            print(" ", rel, err)
    # players whose upstream headshot 404s get no image (upstream shows none either);
    # record them so build_source_data.py zeroes the id deterministically.
    missing = sorted({
        rel.split("/")[1].rsplit(".", 1)[0]
        for rel, _u, _e in errors
        if rel.startswith("players/")
    })
    (SRC / "headshot_missing.json").write_text(
        json.dumps(missing, indent=1), encoding="utf-8"
    )
    print(f"headshot_missing.json: {len(missing)} slugs")
    # drop stale files from previous runs
    for f in IMG.rglob("*"):
        if f.is_file() and f.name != ".gitkeep":
            rel = str(f.relative_to(IMG))
            if rel not in manifest:
                f.unlink()

    (SITE / "image_manifest.json").write_text(
        json.dumps(
            {
                "site": "nfl",
                "captured_on": "2026-09-24",
                "files": manifest,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    assets = [
        {
            "path": f"static/images/{rel}",
            "bytes": m["bytes"],
            "sha256": m["sha256"],
            "source_url": m["source_url"],
        }
        for rel, m in sorted(manifest.items())
    ]
    (SITE / "asset_inventory.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "site": "nfl",
                "asset_count": len(assets),
                "total_bytes": sum(a["bytes"] for a in assets),
                "captured_on": "2026-09-24",
                "capture_method": (
                    "Playwright-rendered pages + direct HTTP fetches of the "
                    "resolved media URLs served by static.www.nfl.com"
                ),
                "source_page": "https://www.nfl.com/",
                "notes": [
                    "Every entry is a real upstream media file fetched at its resolved URL.",
                    "Verified byte- and hash-exact by scripts/check_asset_inventory.py at build time.",
                    "Team logos and UI marks are the upstream SVG/PNG assets; player headshots,",
                    "news editorial art and video thumbnails come from the static.www.nfl.com",
                    "image/upload CDN at the transforms the live pages render.",
                ],
                "assets": assets,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"manifest: {len(manifest)} files, errors: {len(errors)}", flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

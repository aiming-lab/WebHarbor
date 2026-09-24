"""WebKit fallback harvester for destination pages (fresh-profile rounds).

A real WebKit engine executes (and auto-passes) Akamai's behavioral
interstitial, which a plain HTTP client cannot. Profiles go stale quickly,
so each round launches a FRESH persistent profile; a round ends early once
a page is denied several times in a row. Writes raw HTML into the shared
page cache, so either engine's success advances the harvest.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from harvest_destinations import DESTINATIONS, CACHE

sys.path.insert(0, "/tmp/marriott-scrape/.venv/lib/python3.12/site-packages")
from playwright.sync_api import sync_playwright

STOP = pathlib.Path("/tmp/stop_wk_harvest")


def round_once(profile_dir: str) -> int:
    got = 0
    denials = 0
    with sync_playwright() as p:
        ctx = p.webkit.launch_persistent_context(
            profile_dir, headless=True,
            viewport={"width": 1440, "height": 900}, locale="en-US")
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        for slug, path in DESTINATIONS:
            if STOP.exists():
                break
            cache_file = CACHE / f"{slug}.json"
            if cache_file.exists():
                continue
            url = f"https://www.marriott.com/en-us/destinations/{path}.mi"
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(9000)
                title = pg.title()
                html = pg.content()
                if "Access Denied" in title or len(html) < 2000:
                    denials += 1
                    if denials >= 6:
                        break
                    time.sleep(random.uniform(2, 6))
                    continue
                denials = 0
                cache_file.write_text(html)
                got += 1
                print(f"[wk-ok] {slug} ({len(html)} bytes)", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[wk-err] {slug}: {str(exc)[:90]}", flush=True)
            time.sleep(random.uniform(1.5, 4.0))
        ctx.close()
    return got


def main() -> None:
    round_no = 0
    tag = os.environ.get("WK_PROFILE_TAG", "r")
    while not STOP.exists():
        round_no += 1
        remaining = [s for s, _ in DESTINATIONS if not (CACHE / f"{s}.json").exists()]
        if not remaining:
            print("[wk] all destinations cached", flush=True)
            break
        profile_dir = f"/tmp/marriott-wk-profile-{tag}{round_no}"
        got = round_once(profile_dir)
        print(f"[wk] round {round_no}: {got} pages; {len(remaining)} remaining", flush=True)
        time.sleep(random.uniform(30, 90))
    print("[wk] exiting", flush=True)


if __name__ == "__main__":
    main()

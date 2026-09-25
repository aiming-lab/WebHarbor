#!/usr/bin/env python3
"""Capture per-player season stats pages for the players already scraped.

For every players/<slug>.txt in scraped_data, visit
https://www.nfl.com/players/<slug>/stats/ and save the rendered text
(the per-season passing/rushing/receiving table plus career totals).
"""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "scraped_data"
PLAYERS = sorted(p.name[:-4] for p in (OUT / "players").glob("*.txt"))


def dismiss_banner(page) -> None:
    for sel in (
        'button:has-text("Acknowledge Tracking")',
        'button:has-text("Reject Optional Tracking")',
    ):
        try:
            page.click(sel, timeout=2000)
            return
        except Exception:
            pass


def main() -> None:
    print(f"{len(PLAYERS)} players to capture", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        for i, slug in enumerate(PLAYERS):
            dest = OUT / "players" / f"{slug}_stats.txt"
            if dest.exists():
                continue
            try:
                pg.goto(
                    f"https://www.nfl.com/players/{slug}/stats/",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
                pg.wait_for_timeout(4500)
                dismiss_banner(pg)
                pg.wait_for_timeout(1000)
                dest.write_text(pg.inner_text("body"), encoding="utf-8")
                print(f"[{i+1}/{len(PLAYERS)}] {slug} ok", flush=True)
            except Exception as e:
                print(f"[{i+1}/{len(PLAYERS)}] {slug} FAILED {e}", flush=True)
                time.sleep(2)
        browser.close()


if __name__ == "__main__":
    main()

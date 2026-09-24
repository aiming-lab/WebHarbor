#!/usr/bin/env python3
"""Capture the 32 team club pages (record, coach, stadium, owners, feeds)."""
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "scraped_data"
(OUT / "teams").mkdir(exist_ok=True)
SLUGS = sorted(p.name[:-5] for p in (OUT / "rosters").glob("*.json"))


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
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        for i, slug in enumerate(SLUGS):
            dest_txt = OUT / "teams" / f"{slug}.txt"
            dest_html = OUT / "teams" / f"{slug}.html"
            if dest_txt.exists():
                continue
            try:
                pg.goto(
                    f"https://www.nfl.com/teams/{slug}/",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
                pg.wait_for_timeout(5000)
                dismiss_banner(pg)
                pg.wait_for_timeout(1200)
                dest_txt.write_text(pg.inner_text("body"), encoding="utf-8")
                dest_html.write_text(pg.content(), encoding="utf-8")
                print(f"[{i+1}/{len(SLUGS)}] {slug} ok", flush=True)
            except Exception as e:
                print(f"[{i+1}/{len(SLUGS)}] {slug} FAILED {e}", flush=True)
                time.sleep(2)
        browser.close()


if __name__ == "__main__":
    main()

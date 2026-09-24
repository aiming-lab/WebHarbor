#!/usr/bin/env python3
"""Capture the home page with wheel-based scrolling (JS evaluate breaks there)."""
from __future__ import annotations

import pathlib

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        )
        page = ctx.new_page()
        page.goto("https://www.instructure.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)
        for sel in ["#onetrust-accept-btn-handler", "button:has-text('Accept')"]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1500):
                    btn.click(timeout=3000)
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                pass
        # wheel-scroll instead of evaluate
        for _ in range(60):
            page.mouse.wheel(0, 800)
            page.wait_for_timeout(120)
        page.wait_for_timeout(2000)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "home_full.png"), full_page=True)
        (OUT / "home_full.html").write_text(page.content(), encoding="utf-8")
        print("title:", page.title(), "| url:", page.url)
        browser.close()


if __name__ == "__main__":
    main()

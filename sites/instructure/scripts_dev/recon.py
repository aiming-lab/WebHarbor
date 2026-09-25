#!/usr/bin/env python3
"""Recon: render upstream pages with Playwright, save HTML + full screenshots."""
from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
OUT.mkdir(exist_ok=True)

BASE = "https://www.instructure.com"

URLS = {
    "home": "/",
    "canvas": "/canvas",
    "mastery": "/mastery",
    "parchment": "/parchment",
    "k12": "/k12",
    "higher_education": "/higher-education",
    "business": "/business",
    "resources": "/resources",
    "case_studies": "/resources/case-studies",
    "ebooks": "/resources/ebooks",
    "videos": "/resources/videos",
    "blog": "/resources/blog",
    "webinars": "/resources/webinars",
    "research": "/resources/research",
    "about": "/about",
    "leadership": "/about/leadership",
    "careers": "/about/careers",
    "partners": "/partners",
    "community": "/community",
    "news": "/news",
    "events": "/events",
    "request_demo": "/request-demo",
    "contact_us": "/contact-us",
    "support_faq": "/support/canvas-support-faq",
    "why_instructure": "/why-instructure",
    "services": "/services",
    "search_canvas": "/search?keys=canvas",
}


def capture(page, name: str, url: str) -> None:
    print(f"== {name}: {url}", flush=True)
    page.goto(BASE + url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    # dismiss cookie banner if present
    for sel in ["button:has-text('Accept')", "#onetrust-accept-btn-handler"]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=3000)
                page.wait_for_timeout(1500)
                break
        except Exception:
            pass
    # scroll through the page to trigger lazy loading, then back to top
    page.evaluate(
        """async () => {
            await new Promise(r => setTimeout(r, 500));
            const h = document.body.scrollHeight;
            for (let y = 0; y <= h; y += 800) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 150)); }
            window.scrollTo(0, 0);
        }"""
    )
    page.wait_for_timeout(2500)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    (OUT / f"{name}.html").write_text(page.content(), encoding="utf-8")
    print("   title:", page.title(), "| final:", page.url, flush=True)


def main() -> None:
    only = sys.argv[1:]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        )
        page = ctx.new_page()
        for name, url in URLS.items():
            if only and name not in only:
                continue
            try:
                capture(page, name, url)
            except Exception as exc:
                print(f"   ERROR {name}: {exc}", flush=True)
        browser.close()


if __name__ == "__main__":
    main()

"""Recon pass 1: homepage + charts + a track page + an artist page."""
import json, pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
OUT.mkdir(exist_ok=True)

PAGES = [
    ("home", "https://soundcloud.com/"),
    ("charts_top50", "https://soundcloud.com/charts"),
    ("charts_newhot", "https://soundcloud.com/charts?genre=all-music&chart-type=newhot"),
    ("discover_house", "https://soundcloud.com/discover"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    for name, url in PAGES:
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            page.screenshot(path=str(OUT / f"recon_{name}.png"), full_page=False)
            (OUT / f"recon_{name}.html").write_text(page.content())
            print(f"[{name}] ok, title={page.title()!r}, url={page.url}")
        except Exception as e:
            print(f"[{name}] FAIL: {e}")
    browser.close()

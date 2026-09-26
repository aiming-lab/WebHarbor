"""Recon pass 6: capture key page DOMs."""
import pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
PAGES = [
    ("charts", "https://soundcloud.com/charts"),
    ("artist", "https://soundcloud.com/nardo-wick"),
    ("playlist", "https://soundcloud.com/music-charts-us/sets/all-music-genres"),
    ("search", "https://soundcloud.com/search?q=drake"),
    ("login", "https://soundcloud.com/signin"),
    ("pro", "https://soundcloud.com/you/pro"),
    ("genres", "https://soundcloud.com/tags"),
]
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    for name, url in PAGES:
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            page.screenshot(path=str(OUT / f"recon_{name}.png"))
            (OUT / f"recon_{name}.html").write_text(page.content())
            print(f"[{name}] {page.title()!r} url={page.url}")
        except Exception as e:
            print(f"[{name}] FAIL {e}")
    browser.close()

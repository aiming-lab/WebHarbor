import pathlib
from playwright.sync_api import sync_playwright
OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
BASE = "http://127.0.0.1:46093"
PAGES = [
    ("m_home", "/"),
    ("m_discover", "/discover"),
    ("m_charts", "/charts"),
    ("m_chart_pl", "/music-charts-us/sets/all-music-genres"),
    ("m_track", "/childish-gambino/redbone"),
    ("m_artist", "/nardo-wick"),
    ("m_search", "/search?q=drake"),
    ("m_signin", "/signin"),
    ("m_upgrade", "/upgrade"),
]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    for name, path in PAGES:
        pg.goto(BASE + path, wait_until="networkidle")
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
        print(name, pg.title()[:60])
    b.close()

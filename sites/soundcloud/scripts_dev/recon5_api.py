"""Recon pass 5: capture the API calls the charts page makes."""
import pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"
calls = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    def on_req(req):
        if "api-v2" in req.url or "api.soundcloud" in req.url:
            calls.append(req.url)
    page.on("request", on_req)
    page.goto("https://soundcloud.com/charts", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(10000)
    browser.close()

seen = set()
for u in calls:
    base = u.split("?")[0]
    if base in seen: continue
    seen.add(base)
    print(u[:220])

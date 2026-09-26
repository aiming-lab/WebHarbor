"""Recon pass 8: discover page API calls + user visuals via resolve."""
import json
from playwright.sync_api import sync_playwright
import httpx

CID = "pmagYZKQF6mRtNmtRzPkXSQJ76jYHLN8"
calls = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    def on_req(req):
        if "api-v2" in req.url:
            calls.append(req.url)
    page.on("request", on_req)
    page.goto("https://soundcloud.com/discover", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(10000)
    browser.close()

seen = set()
for u in calls:
    base = u.split("?")[0]
    key = (base, "genre" in u, "selection" in u)
    if base in seen: continue
    seen.add(base)
    print(u[:200])

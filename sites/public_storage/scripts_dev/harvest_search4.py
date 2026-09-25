"""Harvest search results via /self-storage-search/<city>-<st>-<zip> URLs."""
from playwright.sync_api import sync_playwright
import pathlib, time
import os
import pathlib
HARVEST = pathlib.Path(os.environ.get("PS_HARVEST_DIR", pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "ps_harvest"))

OUT = pathlib.Path(str(HARVEST) + "/searches")
QUERIES = [
    ("bellevue", "bellevue-wa-98004"), ("kirkland", "kirkland-wa-98033"), ("redmond", "redmond-wa-98052"),
    ("seattle", "seattle-wa-98101"), ("austin", "austin-tx-78701"), ("denver", "denver-co-80202"),
    ("chicago", "chicago-il-60601"), ("houston", "houston-tx-77002"), ("orlando", "orlando-fl-32801"),
    ("charlotte", "charlotte-nc-28202"), ("indianapolis", "indianapolis-in-46204"), ("portland", "portland-or-97201"),
    ("phoenix", "phoenix-az-85004"), ("atlanta", "atlanta-ga-30303"), ("dallas", "dallas-tx-75201"),
    ("miami", "miami-fl-33130"), ("nyc", "new-york-ny-10001"), ("la", "los-angeles-ca-90012"),
    ("sf", "san-francisco-ca-94102"), ("boston", "boston-ma-02108"),
]
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    page = ctx.new_page()
    for slug, q in QUERIES:
        url = f"https://www.publicstorage.com/self-storage-search/{q}"
        ok = False
        for attempt in range(4):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(7000)
                html = page.content()
                if len(html) > 400000:
                    (OUT / f"{slug}.html").write_text(html)
                    print(f"{slug}: {len(html)//1024}KB saved")
                    ok = True
                    break
            except Exception as e:
                print(f"{slug}: attempt {attempt} ERR {str(e)[:80]}")
                time.sleep(8)
        if not ok:
            print(f"{slug}: FAILED")
    browser.close()

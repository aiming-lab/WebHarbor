"""Harvest the live site's zip-search behavior via the typeahead flow."""
from playwright.sync_api import sync_playwright
import pathlib, json, re, time, sys
import os
import pathlib
HARVEST = pathlib.Path(os.environ.get("PS_HARVEST_DIR", pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "ps_harvest"))

OUT = pathlib.Path(str(HARVEST) + "/zip_searches")
OUT.mkdir(exist_ok=True, parents=True)

ZIPS = [
    "98004", "98007", "98008", "98033", "98034", "98052", "98053",
    "98101", "98109", "98122", "78701", "78704", "78751",
    "80202", "80206", "80210", "60601", "60614", "60657",
    "77002", "77019", "77098", "32801", "32803", "32806",
    "28202", "28205", "28207", "46204", "46220", "46260",
    "85004", "85016", "85018", "30303", "30306", "30309",
    "75201", "75214", "75219", "33130", "33137", "33139",
    "90012", "90026", "90048", "02108", "02116", "02134",
    "97201", "97209", "97214",
]

worker = int(sys.argv[1]) if len(sys.argv) > 1 else 0
nworkers = int(sys.argv[2]) if len(sys.argv) > 2 else 1
mine = ZIPS[worker::nworkers]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    page = ctx.new_page()
    for z in mine:
        dest = OUT / f"{z}.json"
        if dest.exists():
            continue
        ok = False
        for attempt in range(3):
            try:
                page.goto("https://www.publicstorage.com/", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(4000)
                inp = page.locator("input[name='location']:visible").first
                inp.click()
                page.keyboard.type(z, delay=40)
                page.wait_for_timeout(2000)
                page.keyboard.press("Enter")
                page.wait_for_timeout(7000)
                url = page.url
                if "/self-storage-search/" not in url:
                    print(f"[w{worker}] {z}: no slug redirect ({url[:70]})", flush=True)
                    time.sleep(4)
                    continue
                # extract facility cards: id + distance
                data = page.evaluate("""(zip) => {
                  const cards = [];
                  document.querySelectorAll('.row.half-gutters').forEach(row => {
                    const a = row.querySelector('a[href*=".html"]');
                    if (!a) return;
                    const href = a.getAttribute('href');
                    const m = href.match(/\\/(\\d+)\\.html/);
                    if (!m) return;
                    const dist = (row.innerText.match(/([\\d.]+)\\s*miles/) || [])[1];
                    const addr = a.innerText.trim().split('\\n')[0];
                    cards.push({id: m[1], distance: dist ? parseFloat(dist) : null, addr: addr});
                  });
                  return cards;
                }""", z)
                out = {"zip": z, "url": url, "results": data}
                dest.write_text(json.dumps(out, indent=1))
                print(f"[w{worker}] {z}: {len(data)} cards, slug={url.rsplit('/',1)[-1][:40]}", flush=True)
                ok = True
                break
            except Exception as e:
                print(f"[w{worker}] {z}: attempt {attempt} ERR {str(e)[:70]}", flush=True)
                time.sleep(8)
        if not ok:
            print(f"[w{worker}] {z}: FAILED", flush=True)
    browser.close()
print(f"[w{worker}] done", flush=True)

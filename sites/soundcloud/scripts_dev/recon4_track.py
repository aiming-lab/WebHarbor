"""Recon pass 4: track page deep dive."""
import json, pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto("https://soundcloud.com/childmoses/drake-choosing-texas", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(9000)
    page.screenshot(path=str(OUT / "recon_track.png"), full_page=False)
    (OUT / "recon_track.html").write_text(page.content())

    info = page.evaluate("""() => {
      const grab = sel => { const e = document.querySelector(sel); return e ? e.innerText.trim() : null; };
      return {
        title: document.title,
        h1: grab('h1'),
        listenTitle: grab('.listenEngagement__title'),
        all_imgs: Array.from(document.images).map(i => ({src: i.currentSrc || i.src, alt: i.alt, w: i.naturalWidth})),
      };
    }""")
    print(json.dumps(info, indent=1)[:3000])

    # text content outline
    txt = page.evaluate("""() => document.body.innerText.slice(0, 4000)""")
    print("=== BODY TEXT ===")
    print(txt)
    browser.close()

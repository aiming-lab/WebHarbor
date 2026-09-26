"""Recon pass 3: landing page sections, footer, search, login."""
import json, pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto("https://soundcloud.com/", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(9000)

    # All images with src
    imgs = page.evaluate("""() => Array.from(document.images).map(i => ({src: i.currentSrc || i.src, alt: i.alt})).slice(0, 80)""")
    print("=== IMAGES ===")
    for i in imgs:
        print(i['alt'][:40], '|', i['src'][:120])

    # Buttons/CTAs
    ctas = page.evaluate("""() => Array.from(document.querySelectorAll('a,button')).map(e => ({t: (e.innerText||'').trim(), h: e.getAttribute('href')})).filter(x => x.t && x.t.length < 60).slice(0, 60)""")
    print("=== CTAS ===")
    for c in ctas:
        print(c)

    # Footer
    foot = page.evaluate("""() => { const f = document.querySelector('footer'); return f ? f.innerText.slice(0, 2000) : 'NO FOOTER'; }""")
    print("=== FOOTER TEXT ===")
    print(foot)
    browser.close()

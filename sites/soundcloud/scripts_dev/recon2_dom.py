"""Recon pass 2: extract DOM structure of homepage + charts."""
import pathlib, re
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "scraped_data"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto("https://soundcloud.com/", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(9000)

    # Header/nav structure
    header = page.evaluate("""() => {
      const h = document.querySelector('header');
      return h ? h.outerHTML.slice(0, 4000) : 'NO HEADER';
    }""")
    print("=== HEADER ===")
    print(header[:3500])

    # Collect links in nav
    links = page.evaluate("""() => Array.from(document.querySelectorAll('header a')).map(a => ({t: a.innerText.trim(), h: a.getAttribute('href')})).filter(x => x.t)""")
    print("=== HEADER LINKS ===")
    for l in links[:40]:
        print(l)

    # Section headings on the homepage
    heads = page.evaluate("""() => Array.from(document.querySelectorAll('h1,h2,h3')).map(h => h.innerText.trim()).filter(Boolean)""")
    print("=== HEADINGS ===")
    for h in heads[:40]:
        print(repr(h))
    browser.close()

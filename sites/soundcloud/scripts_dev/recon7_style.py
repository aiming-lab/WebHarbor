"""Recon pass 7: extract computed styles/colors of key components."""
import json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto("https://soundcloud.com/music-charts-us/sets/all-music-genres", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(9000)
    data = page.evaluate("""() => {
      const cs = el => { if (!el) return null; const s = getComputedStyle(el); return {
        bg: s.backgroundColor, color: s.color, font: s.fontFamily.slice(0,120), size: s.fontSize }; };
      const out = {};
      out.body = cs(document.body);
      out.header = cs(document.querySelector('header'));
      out.h1 = cs(document.querySelector('h1'));
      out.link = cs(document.querySelector('a'));
      const btn = document.querySelector('button');
      out.button = cs(btn);
      // playbar
      const pb = document.querySelector('.playControls');
      out.playbar = cs(pb);
      // find orange elements
      const oranges = [];
      document.querySelectorAll('*').forEach(e => {
        const s = getComputedStyle(e);
        if (s.backgroundColor && (s.backgroundColor.includes('255, 85') || s.color.includes('255, 85'))) {
          if (oranges.length < 5) oranges.push({cls: (e.className.baseVal||e.className||'').toString().slice(0,80), bg: s.backgroundColor, color: s.color});
        }
      });
      out.oranges = oranges;
      return out;
    }""")
    print(json.dumps(data, indent=1))
    # font links
    css_links = page.evaluate("() => Array.from(document.querySelectorAll('link[rel=stylesheet]')).map(l => l.href).slice(0,10)")
    print("CSS:", css_links)
    browser.close()

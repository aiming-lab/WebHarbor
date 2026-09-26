"""Programmatic fidelity probe: compare key layout facts between upstream and mirror."""
import json, re
from playwright.sync_api import sync_playwright

MIRROR = __import__("os").environ.get("SC_WALK_BASE", "http://127.0.0.1:46093")

def probe(page, url):
    page.goto(url, wait_until="networkidle", timeout=60000)
    return page.evaluate("""() => {
      const gs = el => el ? getComputedStyle(el) : null;
      const rect = el => { if (!el) return null; const r = el.getBoundingClientRect();
        return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}; };
      const body = document.body, bs = gs(body);
      const header = document.querySelector('header'), hs = gs(header);
      const imgs = Array.from(document.images);
      const broken = imgs.filter(i => !i.complete || i.naturalWidth === 0).map(i => i.src);
      return {
        bodyBg: bs.backgroundColor,
        bodyColor: bs.color,
        bodyFont: bs.fontFamily.split(',')[0].trim(),
        headerH: rect(header)?.h,
        headerPos: hs?.position,
        imgCount: imgs.length,
        brokenImgs: broken.slice(0, 5),
        docW: document.documentElement.scrollWidth,
      };
    }""")

pairs = [
    ("home", "https://soundcloud.com/", MIRROR + "/"),
    ("charts", "https://soundcloud.com/charts", MIRROR + "/charts"),
    ("chart_pl", "https://soundcloud.com/music-charts-us/sets/all-music-genres", MIRROR + "/music-charts-us/sets/all-music-genres"),
    ("track", "https://soundcloud.com/childmoses/drake-choosing-texas", MIRROR + "/childish-gambino/redbone"),
    ("artist", "https://soundcloud.com/nardo-wick", MIRROR + "/nardo-wick"),
    ("search", "https://soundcloud.com/search?q=drake", MIRROR + "/search?q=drake"),
]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    for name, up, mi in pairs:
        try:
            u = probe(pg, up)
        except Exception as e:
            u = {"err": str(e)[:80]}
        try:
            m = probe(pg, mi)
        except Exception as e:
            m = {"err": str(e)[:80]}
        print(f"== {name}")
        print("  upstream :", json.dumps(u))
        print("  mirror   :", json.dumps(m))
    b.close()

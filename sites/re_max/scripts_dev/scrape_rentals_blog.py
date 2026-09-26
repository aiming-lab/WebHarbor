"""Stage 5: scrape rentals table + blog.remax.com articles."""
import json, pathlib, re, sys

from playwright.sync_api import sync_playwright

RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

RENTAL_JS = """() => {
  const rows = [];
  document.querySelectorAll('a[href*="home-details"], a[href*="rental"]').forEach(a => {
    const t = (a.innerText || '').trim();
    if (t.includes('For Rent') || /For Rent/.test(t)) {
      rows.push({href: a.href, text: t.replace(/\\n+/g, ' | ').slice(0, 300)});
    }
  });
  const seen = new Set(); const out = [];
  for (const r of rows) { if (!seen.has(r.href)) { seen.add(r.href); out.push(r); } }
  return out;
}"""

BLOG_CARD_JS = """() => {
  const posts = [];
  document.querySelectorAll('a[href^="/"]').forEach(a => {
    const href = a.getAttribute('href');
    if (!href || href === '/' || href.length < 5) return;
    const card = a.closest('article, div');
    const img = a.querySelector('img') || (card ? card.querySelector('img') : null);
    const t = (a.innerText || '').trim();
    if (t.length > 15 && !/^(Home|About|Contact|Blog|Categories|Search|Next|Previous|Older|Newer)/.test(t)) {
      posts.push({href: a.origin + a.getAttribute('href'), title: t.split('\\n')[0].slice(0,120), text: t.replace(/\\n+/g,' | ').slice(0,300), img: img ? (img.currentSrc||img.src) : null});
    }
  });
  const seen = new Set(); const out = [];
  for (const p of posts) { if (!seen.has(p['href'])) { seen.add(p['href']); out.push(p); } }
  return out;
}"""

BLOG_POST_JS = """() => {
  const out = {};
  out.title = document.title.replace(/\\s*[-|].*$/, '');
  const art = document.querySelector('article') || document.querySelector('main') || document.body;
  out.text = art.innerText.trim();
  const img = document.querySelector('article img, main img, .entry-content img');
  out.img = img ? (img.currentSrc || img.src) : null;
  const cat = [...document.querySelectorAll('a')].find(a => /category|tag/i.test(a.href) && (a.innerText||'').trim().length < 40);
  out.category = cat ? cat.innerText.trim() : null;
  const date = document.querySelector('time, .entry-date, .posted-on');
  out.date = date ? date.innerText.trim() : null;
  const author = document.querySelector('.author, .byline, [rel="author"]');
  out.author = author ? author.innerText.trim() : null;
  return out;
}"""


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()

        # rentals
        rent_path = RAW / "rentals.json"
        if not rent_path.exists():
            pg.goto("https://www.remax.com/new-rentals", timeout=60000, wait_until="domcontentloaded")
            pg.wait_for_timeout(8000)
            for sel in ["#onetrust-accept-btn-handler"]:
                try:
                    el = pg.query_selector(sel)
                    if el and el.is_visible():
                        el.click(); pg.wait_for_timeout(500)
                        break
                except Exception:
                    pass
            rows = []
            for i in range(15):
                got = pg.evaluate(RENTAL_JS)
                for r in got:
                    if r not in rows:
                        rows.append(r)
                pg.mouse.wheel(0, 2500)
                pg.wait_for_timeout(1200)
                if len(rows) >= 45:
                    break
            rent_path.write_text(json.dumps(rows[:45], indent=1))
            print(f"[rentals] {len(rows)}")

        # blog
        blog_path = RAW / "blog_posts.json"
        if not blog_path.exists():
            pg.goto("https://blog.remax.com/", timeout=60000, wait_until="domcontentloaded")
            pg.wait_for_timeout(8000)
            cards = pg.evaluate(BLOG_CARD_JS)
            posts = [c for c in cards if '/interest-rate' in c['href'] or '/what-' in c['href'] or '/10-' in c['href'] or '/tips-' in c['href'] or '/first-time' in c['href'] or '/home-' in c['href'] or '/staging' in c['href'] or '/questions' in c['href'] or '/seller' in c['href'] or '/buyer' in c['href']]
            # dedupe by href, keep 25
            seen = set(); uniq = []
            for c in posts:
                if c['href'] not in seen:
                    seen.add(c['href']); uniq.append(c)
            uniq = uniq[:25]
            out = []
            for c in uniq:
                try:
                    pg.goto(c['href'], timeout=45000, wait_until="domcontentloaded")
                    pg.wait_for_timeout(5000)
                    d = pg.evaluate(BLOG_POST_JS)
                    d['url'] = c['href']
                    d['card'] = c
                    out.append(d)
                    print(f"[blog ok] {d['title'][:60]}: {len(d['text'])} chars")
                except Exception as e:
                    print(f"[blog err] {c['href'][-40:]}: {str(e)[:80]}")
            blog_path.write_text(json.dumps(out, indent=1))
            print(f"[blog] {len(out)}")
        b.close()


if __name__ == "__main__":
    main()

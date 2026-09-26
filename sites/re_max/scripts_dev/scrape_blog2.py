"""Stage 5c: scrape blog.remax.com article list + posts."""
import json, pathlib, re, sys

from playwright.sync_api import sync_playwright

RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

POSTS = [
    "https://blog.remax.com/fall-home-staging-ideas/",
    "https://blog.remax.com/how-much-does-20-down-save/",
    "https://blog.remax.com/coffee-table-decor-ideas-for-staging-a-home-to-sell/",
    "https://blog.remax.com/buying-a-home-in-august-2026-as-a-first-time-buyer/",
    "https://blog.remax.com/turning-interest-into-offers-amenities-that-matter/",
    "https://blog.remax.com/summer-2026-home-trends-4-styles-shaping-homes-right-now/",
    "https://blog.remax.com/selling-home-mortgage-rates-near-7/",
    "https://blog.remax.com/how-to-help-parents-downsize-their-home/",
    "https://blog.remax.com/how-to-sell-a-house-with-solar-panels/",
    "https://blog.remax.com/should-you-keep-your-current-home-as-a-rental-when-you-move/",
    "https://blog.remax.com/seller-concessions-2026/",
    "https://blog.remax.com/how-to-sell-a-house-in-a-flood-zone/",
    "https://blog.remax.com/interest-rate-announcement/",
    "https://blog.remax.com/where-homes-sold-fastest-slowest-july-2026/",
    "https://blog.remax.com/u-s-housing-market-recap-blog/",
    "https://blog.remax.com/miracle-home-program/",
    "https://blog.remax.com/national-housing-report-recap-home-prices-and-sales/",
    "https://blog.remax.com/where-home-prices-sit-furthest-below-the-national-median/",
    "https://blog.remax.com/how-to-create-a-study-area/",
    "https://blog.remax.com/back-to-school-home-setup-4-functional-family-zones/",
    "https://blog.remax.com/buying-a-home-for-football-season-a-fans-game-plan/",
]

POST_JS = """() => {
  const out = {};
  out.title = (document.querySelector('h1') || {}).innerText || document.title;
  const art = document.querySelector('article') || document.querySelector('main') || document.body;
  out.text = art.innerText.trim();
  const img = document.querySelector('article img, main img, .entry-content img, header img');
  out.img = img ? (img.currentSrc || img.src) : null;
  const time = document.querySelector('time');
  out.date = time ? (time.getAttribute('datetime') || time.innerText.trim()) : null;
  const cat = [...document.querySelectorAll('a')].find(a => /\\/category\\//.test(a.href) && (a.innerText||'').trim().length < 40);
  out.category = cat ? cat.innerText.trim() : null;
  return out;
}"""


def main():
    out_path = RAW / "blog_posts.json"
    done = json.loads(out_path.read_text()) if out_path.exists() else []
    done_urls = {d["url"] for d in done}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        for url in POSTS:
            if url in done_urls:
                continue
            ok = False
            for attempt in range(3):
                try:
                    pg.goto(url, timeout=45000, wait_until="domcontentloaded")
                    ok = True
                    break
                except Exception as e:
                    print(f"[retry {attempt}] {url[-35:]}: {str(e)[:60]}")
                    pg.wait_for_timeout(4000)
            if not ok:
                continue
            pg.wait_for_timeout(5000)
            d = pg.evaluate(POST_JS)
            d["url"] = url
            done.append(d)
            done_urls.add(url)
            print(f"[ok] {d['title'][:55]}: {len(d['text'])} chars, img={bool(d.get('img'))}, cat={d.get('category')}")
            out_path.write_text(json.dumps(done, indent=1))
        print(f"[blog] {len(done)}")
        b.close()


if __name__ == "__main__":
    main()

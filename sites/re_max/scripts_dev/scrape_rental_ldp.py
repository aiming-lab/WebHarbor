"""Stage 5e: scrape rental home-details pages for photos + descriptions."""
import json, pathlib, re, sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from scrape_ldp import EXTRACT_JS  # noqa: E402

RAW = pathlib.Path(__file__).resolve().parent.parent / "scraped_data" / "raw"


def main():
    rentals = json.loads((RAW / "rentals_linked.json").read_text())
    out_path = RAW / "rental_ldp.json"
    done = json.loads(out_path.read_text()) if out_path.exists() else []
    done_urls = {d["url"] for d in done}
    n = 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        for r in rentals:
            if n >= 28:
                break
            url = r.get("href")
            if not url or url in done_urls:
                continue
            ok = False
            for attempt in range(3):
                try:
                    pg.goto(url, timeout=45000, wait_until="domcontentloaded")
                    ok = True
                    break
                except Exception:
                    pg.wait_for_timeout(4000)
            if not ok:
                continue
            pg.wait_for_timeout(6000)
            for sel in ["#onetrust-accept-btn-handler"]:
                try:
                    el = pg.query_selector(sel)
                    if el and el.is_visible():
                        el.click(); pg.wait_for_timeout(400)
                        break
                except Exception:
                    pass
            try:
                d = pg.evaluate(EXTRACT_JS)
                d["url"] = url
                d["row"] = r
                done.append(d)
                done_urls.add(url)
                n += 1
                print(f"[ok] {url[-30:]}: desc={len(d.get('ld_description') or '')} gal={len(d.get('gallery') or [])}")
            except Exception as e:
                print(f"[err] {url[-30:]}: {str(e)[:80]}")
            out_path.write_text(json.dumps(done, indent=1))
        print(f"[done] {len(done)}")
        b.close()


if __name__ == "__main__":
    main()

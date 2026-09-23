#!/usr/bin/env python3
"""Real-browser walkthrough of the re-anchored tasks 8 and 12 (reviewer rounds).

Drives the containerized mirror (default http://localhost:43070) with
Playwright, records every URL step, and verifies the detail-page-only
answers against the frozen seed DB. Also asserts the answers are NOT
reachable from the search card faces (de-leak checks).

Task 8 re-anchor (reviewer terminal requirement): the rail-cheapest wording
still let an agent assemble the answer from search card faces (the rail's
cheapest item is also the cheapest card in an eyewear search). The question
now asks for rail count/order facts only — the merchant mix count and the
rail position of an item — which render solely in the product panel's
"Compare with similar items" section.
"""
import json
import pathlib
import sqlite3
import sys

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
DB = HERE / "instance_seed" / "google_shopping.db"
REPORT = HERE / "scraped_data" / "r2_walkthrough.json"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:43070"


def q(sql, args=()):
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute(sql, args).fetchall()
    db.close()
    return [dict(r) for r in rows]


def rail(title):
    me = q("SELECT id, category FROM products WHERE title=?", (title,))[0]
    return q("SELECT title, price, merchant_name FROM products WHERE "
             "category=? AND id != ? ORDER BY position LIMIT 8",
             (me["category"], me["id"]))


def rail_cards_of(page):
    return page.eval_on_selector_all(
        ".feed-row .pcard",
        "els => els.map(e => ({"
        "  title: e.querySelector('.title').innerText.trim(),"
        "  merchant: e.querySelector('.merchant').innerText.trim()}))")


def main():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                   locale="en-US")
        page = ctx.new_page()

        # ---------- Task 8: St Barts rail TikTok Shop count + second -------
        steps = []
        page.goto(f"{BASE}/search?q=St+Barts+Bluelight", wait_until="networkidle")
        steps.append(page.url)
        search_html = page.content()
        exp_rail = rail("St Barts Bluelight")
        exp_count = sum(1 for r in exp_rail if r["merchant_name"] == "TikTok Shop")
        exp_second = exp_rail[1]["title"]
        # de-leak (structure): the compare rail is not rendered on the search
        # page, and the second-listed rail item is not among its card faces
        rail_on_search = page.locator(".feed-row").count()
        second_on_search = exp_second in search_html
        page.click(".result-grid .pcard")
        page.wait_for_load_state("networkidle")
        steps.append(page.url)
        rail_cards = rail_cards_of(page)
        tiktok_count = sum(1 for r in rail_cards if "TikTok Shop" in r["merchant"])
        second_title = rail_cards[1]["title"] if len(rail_cards) > 1 else None
        t8_pass = (tiktok_count == exp_count and second_title == exp_second
                   and rail_on_search == 0 and not second_on_search)
        # de-leak (card faces): counting TikTok Shop faces on the
        # merchant-filtered search surface yields the catalog count, not the
        # rail count — the number the question asks for never appears on a
        # card face
        page.goto(f"{BASE}/search?q=&store=TikTok+Shop", wait_until="networkidle")
        steps.append(page.url)
        merchant_faces = page.eval_on_selector_all(
            ".result-grid .pcard", "els => els.length")
        faces_count_differs = merchant_faces != exp_count
        t8_pass = t8_pass and faces_count_differs
        results.append({
            "task": "Google Shopping--8", "pass": bool(t8_pass), "steps": steps,
            "expected": {"tiktok_shop_count": exp_count, "second": exp_second},
            "walked": {"tiktok_shop_count": tiktok_count, "second": second_title},
            "rail_rendered_on_search_page": bool(rail_on_search),
            "second_title_on_search_page": bool(second_on_search),
            "merchant_face_count": merchant_faces,
            "card_faces_yield_different_count": bool(faces_count_differs)})
        print(f"[{'PASS' if t8_pass else 'FAIL'}] Google Shopping--8: "
              f"TikTok Shop in rail = {tiktok_count} (expected {exp_count}), "
              f"second = {second_title if second_title else None} "
              f"(expected {exp_second}) | "
              f"de-leak: rail-on-search={rail_on_search}, "
              f"second-on-search={second_on_search}, "
              f"merchant-card-faces={merchant_faces}!={exp_count}")

        # ---------- Task 12: Klassy rail merchant count + first -----------
        steps = []
        page.goto(f"{BASE}/search?q=Klassy", wait_until="networkidle")
        steps.append(page.url)
        page.click(".result-grid .pcard")
        page.wait_for_load_state("networkidle")
        steps.append(page.url)
        rail_cards = rail_cards_of(page)
        bbl_count = sum(1 for r in rail_cards if "BlockBlueLight" in r["merchant"])
        first_title = rail_cards[0]["title"] if rail_cards else None
        exp_rail = rail("Klassy - Blue Light Blocking Glasses Tortie Brown")
        exp_count = sum(1 for r in exp_rail if r["merchant_name"] == "BlockBlueLight")
        exp_first = exp_rail[0]["title"]
        t12_pass = bbl_count == exp_count and first_title == exp_first
        results.append({
            "task": "Google Shopping--12", "pass": bool(t12_pass), "steps": steps,
            "expected": {"blockbluelight_count": exp_count, "first": exp_first},
            "walked": {"blockbluelight_count": bbl_count, "first": first_title}})
        print(f"[{'PASS' if t12_pass else 'FAIL'}] Google Shopping--12: "
              f"BlockBlueLight in rail = {bbl_count} (expected {exp_count}), "
              f"first = {first_title[:50] if first_title else None} "
              f"(expected {exp_first[:50]})")
        browser.close()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, indent=1) + "\n")
    ok = all(r["pass"] for r in results)
    print(f"\nr2 walkthrough: {sum(1 for r in results if r['pass'])}/{len(results)} PASS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

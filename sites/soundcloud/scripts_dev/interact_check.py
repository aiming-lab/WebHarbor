"""Playwright interaction probe: playbar, like, comment, follow, modal, library.

Run against a FRESH instance (cp -r instance_seed instance) for deterministic
results. Exits 0 only when every check passes.
"""
from playwright.sync_api import sync_playwright
M = __import__("os").environ.get("SC_WALK_BASE", "http://127.0.0.1:46093")
results = []
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    # 1. login first so plays/likes record
    pg.goto(M + "/signin", wait_until="networkidle")
    pg.fill(".auth-card #email", "alice.j@test.com")
    pg.fill(".auth-card #password", "TestPass123!")
    pg.click(".auth-card button[type=submit]")
    pg.wait_for_load_state("networkidle")
    results.append(("login ok", "Sign out" in pg.inner_text("body")))
    # 2. playbar: play a track
    pg.goto(M + "/childish-gambino/redbone", wait_until="networkidle")
    pg.click(".listen .artwork .play-overlay button")
    pg.wait_for_timeout(1200)
    results.append(("playbar shows track", pg.inner_text("#pb-title") == "Redbone"))
    results.append(("pause icon", pg.inner_text("#pb-play") == "❚❚"))
    e1 = pg.inner_text("#pb-elapsed"); pg.wait_for_timeout(1600); e2 = pg.inner_text("#pb-elapsed")
    results.append(("progress advances", e1 != e2))
    pg.click("#pb-play")
    results.append(("pause works", pg.inner_text("#pb-play") == "▶"))
    # 3. like (toggle-aware)
    pg.goto(M + "/esdeekid/phantom", wait_until="networkidle")
    like_sel = ".listen .actions .act-like"
    before = pg.locator(like_sel).get_attribute("class") or ""
    pg.click(like_sel)
    pg.wait_for_timeout(900)
    after = pg.locator(like_sel).get_attribute("class") or ""
    results.append(("like toggles", ("liked" in after) != ("liked" in before)))
    # 4. comment
    pg.fill("#comment-input", "probe comment zq1")
    pg.click("#comment-form button[type=submit]")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(900)
    results.append(("comment posts", "probe comment zq1" in pg.inner_text("body")))
    # 5. add-to-playlist modal
    pg.click(".listen .actions .act-addtopl")
    pg.wait_for_timeout(500)
    results.append(("modal opens", "open" in (pg.locator("#pl-modal").get_attribute("class") or "")))
    pg.fill("#pl-new-title", "Probe Playlist ZQ")
    pg.click("#pl-create-form button[type=submit]")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(900)
    pg.click(".listen .actions .act-addtopl")
    pg.wait_for_timeout(500)
    results.append(("playlist in modal", "Probe Playlist ZQ" in pg.inner_text("#pl-modal")))
    pg.click("#pl-modal .modal-close")
    pg.wait_for_timeout(300)
    results.append(("modal closes", "open" not in (pg.locator("#pl-modal").get_attribute("class") or "")))
    # 6. follow
    pg.goto(M + "/esdeekid", wait_until="networkidle")
    before_f = pg.inner_text(".act-follow")
    pg.click(".act-follow")
    pg.wait_for_timeout(900)
    results.append(("follow toggles", pg.inner_text(".act-follow") != before_f))
    # 7. library likes shows the liked track
    pg.goto(M + "/you/likes", wait_until="networkidle")
    results.append(("likes page shows track", "Phantom" in pg.inner_text("body")))
    # 8. history shows plays
    pg.goto(M + "/you/history", wait_until="networkidle")
    results.append(("history shows plays", "Redbone" in pg.inner_text("body")))
    results.append(("no page errors", not errors))
    b.close()
for name, res in results:
    print(("PASS " if res else "FAIL ") + name)
print("TOTAL:", sum(1 for _, r in results if r), "/", len(results))
if any(not r for _, r in results):
    raise SystemExit(1)

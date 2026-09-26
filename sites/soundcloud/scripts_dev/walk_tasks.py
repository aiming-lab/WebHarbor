"""Task feasibility walk: drives every task in tasks.jsonl through the mirror
with Playwright, logs each atomic browser action (navigate/click/fill/select/
go_back/scroll/done — the reviewer's step-counting convention), and asserts
the expected page facts.

Ground truth lives only here (dev-time verification), never in tasks.jsonl.
Run:  python3 scripts_dev/walk_tasks.py [task_ids...]
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

LOCAL_PORT = os.environ.get("SC_WALK_LOCAL_PORT", "46093")
M = os.environ.get("SC_WALK_BASE", f"http://127.0.0.1:{LOCAL_PORT}")
SITE = pathlib.Path(__file__).resolve().parent.parent

results = []


def record(tid, ok, steps, note=""):
    results.append((tid, ok, steps, note))
    print(f"[{'PASS' if ok else 'FAIL'}] {tid} ({len(steps)} steps) {note}")


class Walk:
    """Thin action logger: every atomic UI action counts one step."""

    def __init__(self, pg):
        self.pg = pg
        self.steps = []

    def nav(self, path):
        self.pg.goto(M + path, wait_until="networkidle")
        self.steps.append(("navigate", path))

    def click(self, sel, note=""):
        self.pg.click(sel)
        self.pg.wait_for_load_state("networkidle")
        self.steps.append(("click", note or sel))

    def click_soft(self, sel, note=""):
        """Click that does not navigate (AJAX action / modal / play)."""
        self.pg.click(sel)
        self.steps.append(("click", note or sel))

    def click_action(self, sel, url_part, note="", ui_wait=None):
        """Click an AJAX action and wait for its POST response — a fresh
        server's first SQLite write can take ~1s (journal fsync), so fixed
        sleeps race the UI update. ui_wait polls for the visible result."""
        with self.pg.expect_response(
                lambda r: url_part in r.url and r.request.method == "POST",
                timeout=20000):
            self.pg.click(sel)
        self.steps.append(("click", note or sel))
        if ui_wait:
            self.pg.wait_for_function(ui_wait, timeout=20000)

    def open_modal(self, sel=".listen .actions .act-addtopl", note="＋"):
        self.click_soft(sel, note)
        self.pg.wait_for_function(
            "document.getElementById('pl-modal').classList.contains('open')")

    def modal_closed(self):
        self.pg.wait_for_function(
            "!document.getElementById('pl-modal').classList.contains('open')")

    def fill(self, sel, text, note=""):
        self.pg.fill(sel, text)
        self.steps.append(("input", note or f"{sel}={text}"))

    def select(self, sel, value, note=""):
        self.pg.select_option(sel, value)
        self.steps.append(("select", note or f"{sel}={value}"))

    def back(self):
        self.pg.go_back()
        self.pg.wait_for_load_state("networkidle")
        self.steps.append(("go_back", ""))

    def scroll(self):
        self.pg.mouse.wheel(0, 1400)
        self.pg.wait_for_timeout(300)
        self.steps.append(("scroll", ""))

    def done(self, note="final answer"):
        self.steps.append(("done", note))

    # ---- compound helpers -------------------------------------------------
    def login(self, email, password):
        self.click("header .header__actions button:has-text('Sign in')",
                   "Sign in")
        self.fill(".auth-card #email", email)
        self.fill(".auth-card #password", password)
        self.click(".auth-card button[type=submit]", "sign-in submit")

    def landing_chart(self, title):
        """Chart card directly on the anonymous landing (honest shortcut for
        the 10 charts surfaced there)."""
        self.click(f".card-grid .playlist-card .t:text-is('{title}')",
                   f"landing chart card {title}")

    def charts_nav(self):
        self.click("header .header__nav a:has-text('Charts')", "Charts nav")

    def chart_card(self, country, title):
        sel = (f".chart-group:has(h2:text('Music Charts {country}')) "
               f".chart-card:has(.t:text-is('{title}'))")
        self.click(sel, f"{title} chart card ({country})")

    def row(self, n):
        return self.pg.locator(f".track-list .track-row:nth-child({n})")

    def open_chart_track(self, n):
        title = self.row(n).locator(".info .t").inner_text()
        self.click(f".track-list .track-row:nth-child({n}) .info .t",
                   f"open chart #{n} ({title})")
        return title

    def stats_spans(self):
        """['1,234 plays', '12.3K likes', '1.4K reposts', '3:46', ...]"""
        return [s.inner_text()
                for s in self.pg.locator(".listen .stats span").all()]

    def exact_plays(self):
        return int(self.stats_spans()[0].split()[0].replace(",", ""))

    def track_duration(self):
        spans = self.stats_spans()
        return spans[3] if len(spans) >= 4 else ""

    def track_likes(self):
        for s in self.stats_spans():
            if s.endswith("likes"):
                return s
        return ""

    def details_panel(self):
        panels = self.pg.locator(".listen-cols .side .panel")
        for i in range(panels.count()):
            p = panels.nth(i)
            h = p.locator("h3")
            if h.count() and h.inner_text() == "Details":
                return p.inner_text()
        return ""


def _knum(compact):
    s = compact.strip().split()[0]
    mult = 1
    if s.endswith("K"):
        mult, s = 1_000, s[:-1]
    elif s.endswith("M"):
        mult, s = 1_000_000, s[:-1]
    try:
        return float(s.replace(",", "")) * mult
    except ValueError:
        return 0


def _dur_sec(label):
    """'3:46' -> 226 seconds; '1:02:03' -> 3723."""
    parts = label.strip().split(":")
    try:
        return sum(int(p) * 60 ** i for i, p in enumerate(reversed(parts)))
    except (ValueError, AttributeError):
        return 0


# --------------------------------------------------------------------------- #
# walks (official path per tasks.jsonl; each atomic action = 1 step)
# --------------------------------------------------------------------------- #
def walk_0(pg):
    w = Walk(pg)
    w.nav("/")
    w.landing_chart("All music genres")                 # US card on landing
    us = []
    for n in (1, 2, 3):
        t = w.open_chart_track(n)
        us.append((t, w.stats_spans()))
        if n < 3:
            w.back()
    w.charts_nav()
    w.scroll()
    w.chart_card("UK", "All music genres")
    uk = []
    for n in (1, 2, 3):
        t = w.open_chart_track(n)
        uk.append((t, w.stats_spans()))
        if n < 3:
            w.back()
    w.done()
    ok = (us[0][0] == "Is Dat Right?" and us[1][0] == "Backwards"
          and us[2][0] == "Cowgirl"
          and uk[0][0].startswith("Cloonee & Prospa - Good Girl")
          and uk[1][0].startswith("Kolter - Hey Everybody")
          and uk[2][0] == "On 2nite"
          and us[0][1][0] == "969,416 plays"
          and us[1][1][0] == "280,716 plays"
          and us[2][1][0] == "1,453,008 plays"
          and uk[0][1][0] == "1,294,858 plays"
          and uk[1][1][0] == "938,222 plays"
          and uk[2][1][0] == "2,399,647 plays"
          and us[2][1][1] == "40.9K likes"      # US #1 likes
          and uk[0][1][1] == "41.6K likes")     # UK #1 likes
    record("SoundCloud--0", ok, w.steps,
           "US#1 Cowgirl 1,453,008 > UK#1 1,294,858; "
           f"#1 likes {us[2][1][1]} / {uk[0][1][1]}")


def walk_1(pg):
    w = Walk(pg)
    w.nav("/")
    w.landing_chart("Country")
    facts = []
    for n in (1, 2, 3, 4, 5):
        t = w.open_chart_track(n)
        posted = pg.locator(".listen .posted").inner_text()
        facts.append((t, posted, w.stats_spans()[0]))
        w.back()
    w.click(".track-list .track-row:nth-child(1) .info .a", "artist of #1")
    f1 = pg.locator(".info-stats").inner_text()
    w.back()
    w.click(".track-list .track-row:nth-child(2) .info .a", "artist of #2")
    f2 = pg.locator(".info-stats").inner_text()
    w.done()
    ok = (facts[0][0].startswith("Last Thing You Need")
          and facts[1][0] == "P.O.S." and facts[2][0] == "That's Just Me"
          and facts[3][0] == "Think As You Drunk"
          and facts[4][0] == "Take Me Back (Leave Me There)"
          and all("ago" in f[1] for f in facts)
          and facts[0][2] == "222,932 plays"
          and "500,207" in f1 and "31,084" in f2)
    record("SoundCloud--1", ok, w.steps,
           f"followers #1={'500,207' in f1} #2={'31,084' in f2}; "
           f"most plays: {facts[0][0]!r}")


def walk_2(pg):
    w = Walk(pg)
    w.nav("/")
    w.landing_chart("All music genres")
    t9 = w.open_chart_track(9)
    w.click(".listen .artist .name", "Lil Baby profile")
    stats = pg.locator(".info-stats").inner_text()
    ok_profile = "1,988,725" in stats and "236" in stats
    w.click(".artist-tabs a:has-text('Popular tracks')", "Popular tab")
    pop = []
    for n in range(1, pg.locator(".track-list .track-row").count() + 1):
        title = w.row(n).locator(".info .t").inner_text()
        w.click(f".track-list .track-row:nth-child({n}) .info .t",
                f"popular #{n} ({title})")
        pop.append((title, w.exact_plays(), w.details_panel()))
        w.back()
    w.charts_nav()
    w.chart_card("US", "Hip Hop")
    us_pos = None
    for i in range(1, 51):
        if w.row(i).locator(".info .t").inner_text() == "Dead Fresh":
            us_pos = i
            break
    w.charts_nav()
    w.chart_card("UK", "Hip Hop")
    uk_pos = None
    for i in range(1, 51):
        if w.row(i).locator(".info .t").inner_text() == "Dead Fresh":
            uk_pos = i
            break
    w.done()
    ok = (ok_profile and t9 == "Dead Fresh"
          and [p[0] for p in pop] == ["Mrs. Trendsetter", "Dead Fresh",
                                      "What She Like", "Guaranteed"]
          and [p[1] for p in pop] == [4045615, 2468395, 1468903, 1410635]
          and all("Quality Control Music/Motown Records" in p[2] for p in pop)
          and us_pos == 6 and uk_pos == 1)
    record("SoundCloud--2", ok, w.steps,
           f"popular={[p[0] for p in pop]}; US Hip Hop #{us_pos}, "
           f"UK Hip Hop #{uk_pos}")


def walk_3(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("carol.d@test.com", "TestPass123!")
    w.fill("header .header__search input", "Miley Cyrus")
    w.click("header .header__search button", "search")
    w.click(".search-tabs a:has-text('People')", "People tab")
    w.click(".person-row .who", "Miley profile")
    stats = pg.locator(".info-stats").inner_text()
    ok_profile = "1,517,357" in stats and "345" in stats
    w.charts_nav()
    w.chart_card("US", "New & Hot")
    best = None
    for i in range(1, 51):
        row = w.row(i)
        if row.locator(".info .a").inner_text() == "Miley Cyrus":
            plays = _knum(row.locator(".stats").inner_text())
            if best is None or plays > best[0]:
                best = (plays, i, row.locator(".info .t").inner_text())
    assert best[2] == "Bass Persuades", best
    w.open_chart_track(best[1])
    plays = w.exact_plays()
    w.click_action(".listen .actions .act-like", "/like", "like Bass Persuades",
                   ui_wait="document.querySelector('.listen .actions .act-like .n')"
                           ".textContent === '6771'")
    like_n = pg.locator(".listen .actions .act-like .n").inner_text()
    comments = pg.locator(".listen-cols .panel h3").first.inner_text()
    details = w.details_panel()
    w.charts_nav()
    w.chart_card("US", "Pop")
    pop_pos = None
    for i in range(1, 51):
        if w.row(i).locator(".info .t").inner_text() == "Bass Persuades":
            pop_pos = i
            break
    w.done()
    ok = (ok_profile and plays == 137891 and like_n == "6771"
          and comments == "120 comments"
          and "Atlantic Records" in details
          and "September 3, 2026" in details
          and pop_pos == 2)
    record("SoundCloud--3", ok, w.steps,
           f"liked Bass Persuades → likes {like_n}; comments {comments!r}; "
           f"US Pop #{pop_pos}")


def walk_4(pg):
    w = Walk(pg)
    w.nav("/")
    w.fill("header .header__search input", "Rod Wave")
    w.click("header .header__search button", "search")
    w.click(".search-tabs a:has-text('People')", "People tab")
    w.click(".person-row .who", "Rod Wave profile")
    loc = pg.locator(".artist-hero .head .loc").inner_text()
    stats = pg.locator(".info-stats").inner_text()
    ok_profile = "St. Petersburg" in loc and "1,482,902" in stats
    w.click(".artist-tabs a:has-text('Popular tracks')", "Popular tab")
    pop = []
    top_label = newest = None
    for n in range(1, 6):
        title = w.row(n).locator(".info .t").inner_text()
        w.click(f".track-list .track-row:nth-child({n}) .info .t",
                f"popular #{n} ({title})")
        pop.append((title, w.exact_plays(), w.track_duration()))
        if n == 1:
            top_label = w.details_panel()
            c = pg.locator(".comment").first
            newest = (c.locator(".who").inner_text(),
                      c.locator(".at").inner_text())
        w.back()
    long = [p[0] for p in pop if _dur_sec(p[2]) > 180]
    w.done()
    ok = (ok_profile
          and [p[0] for p in pop] == ["Piece Of Your Love", "Hustle",
                                      "Dope Girl", "TP", "Kiss Me Interlude"]
          and [p[1] for p in pop] == [1672102, 1205740, 803703, 653691, 572927]
          and long == ["Piece Of Your Love", "Kiss Me Interlude"]
          and "Alamo" in top_label
          and newest == ("jaylan hutchins", "at 1:53"))
    record("SoundCloud--4", ok, w.steps,
           f"longer than 3 min: {long}; newest comment {newest}")


def walk_5(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("bob.c@test.com", "TestPass123!")
    w.charts_nav()
    w.chart_card("US", "Hip Hop")
    t1 = w.open_chart_track(1)
    w.open_modal(".listen .actions .act-addtopl", "＋ on track #1")
    w.fill("#pl-new-title", "Heavy Bag Rounds")
    with pg.expect_response(
            lambda r: "/playlists/create" in r.url and r.request.method == "POST"):
        pg.click("#pl-create-form button[type=submit]")
    w.steps.append(("click", "create playlist"))
    w.modal_closed()
    w.charts_nav()
    w.chart_card("US", "Hip Hop")
    t2 = w.open_chart_track(2)
    w.open_modal(".listen .actions .act-addtopl", "＋ on track #2")
    w.click_action("#pl-modal li:has-text('Heavy Bag Rounds') button",
                   "/playlists/", "add #2 to playlist")
    w.modal_closed()
    w.click("header .header__nav a:has-text('Library')", "Library")
    w.click(".library-nav a:has-text('Playlists')", "Playlists tab")
    w.click(".playlist-card:has-text('Heavy Bag Rounds')", "open playlist")
    count = pg.locator(".pl-hero .facts").inner_text()
    titles = pg.locator("#upl-list .info .t").all_inner_texts()
    w.done()
    ok = (t1 == "Is Dat Right?" and t2 == "Backwards"
          and titles == ["Is Dat Right?", "Backwards"]
          and "2 tracks" in count)
    record("SoundCloud--5", ok, w.steps, f"titles={titles}")


def walk_6(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("carol.d@test.com", "TestPass123!")
    w.click("header .header__nav a:has-text('Library')", "Library")
    n_rows = pg.locator(".track-list .track-row").count()
    house = []
    for i in range(1, n_rows + 1):
        title = w.row(i).locator(".info .t").inner_text()
        w.click(f".track-list .track-row:nth-child({i}) .info .t",
                f"open liked #{i} ({title})")
        chip = pg.locator(".listen .actions a.btn-ghost")
        genre = chip.inner_text().strip() if chip.count() else ""
        plays = w.exact_plays()
        if genre.lower() == "house":
            house.append((title, plays, i))
        w.back()
    least = min(house, key=lambda h: h[1])
    w.click(f".track-list .track-row:nth-child({least[2]}) .info .t",
            f"reopen least-played house ({least[0]})")
    w.click_action(".listen .actions .act-like", "/like", "unlike",
                   ui_wait="document.querySelector('.listen .actions .act-like')"
                           ".classList.contains('liked') === false")
    w.click(".listen .artist .name", "artist profile")
    w.click_action(".act-follow", "/follow", "follow",
                   ui_wait="document.querySelector('.followers-n')"
                           ".textContent.includes('105,236')")
    followers = pg.locator(".info-stats .followers-n").inner_text()
    w.done()
    ok = (least[0].startswith("Kolter - Hey Everybody")
          and followers == "105,236")
    record("SoundCloud--6", ok, w.steps,
           f"unliked={least[0]!r}; followers after follow={followers}")


def walk_7(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("david.k@test.com", "TestPass123!")
    w.click("footer a:has-text('Plans')", "Plans")
    plans = pg.locator(".plan-grid").inner_text()
    ok_plans = ("$4.99" in plans and "7-day free trial" in plans
                and "$11.99" in plans and "30-day free trial" in plans)
    w.scroll()
    w.click(".plan-card:has(h3:text('Next Pro')) .cycle-row label:has-text('Yearly')",
            "Yearly cycle")
    w.fill(".plan-card:has(h3:text('Next Pro')) input[name=card]",
           "4242 4242 4242 4242")
    w.click(".plan-card:has(h3:text('Next Pro')) button[type=submit]",
            "subscribe Next Pro yearly")
    body = pg.inner_text("body")
    ok_sub = "$99.00" in body and "September 26, 2027" in body
    w.click("header .header__actions a:has-text('Upload')", "Upload")
    w.fill("#title", "Night Shift Demo")
    w.select("#genre", "Rock")
    w.fill("#minutes", "4")
    w.fill("input[name=seconds]", "12")
    w.click(".auth-card button[type=submit]", "upload")
    final_url = pg.url
    w.done()
    ok = (ok_plans and ok_sub
          and final_url.endswith("/david_k/night-shift-demo"))
    record("SoundCloud--7", ok, w.steps,
           f"plans ok={ok_plans}; sub ok={ok_sub}; url={final_url}")


def walk_8(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("alice.j@test.com", "TestPass123!")
    w.click("header .header__actions a:has-text('Upload')", "Upload")
    w.fill("#title", "Midnight Sketch")
    w.select("#genre", "Pop")
    w.fill("#minutes", "3")
    w.fill("input[name=seconds]", "45")
    w.fill("#tags", "demo pop")
    w.click(".auth-card button[type=submit]", "upload")
    final_url = pg.url
    duration = w.track_duration()
    w.open_modal(".listen .actions .act-addtopl", "＋ add to playlist")
    w.click_action("#pl-modal li:has-text('Late Night Drive') button",
                   "/playlists/", "add to Late Night Drive")
    w.modal_closed()
    w.click("header .header__nav a:has-text('Library')", "Library")
    w.click(".library-nav a:has-text('Playlists')", "Playlists tab")
    w.click(".playlist-card:has-text('Late Night Drive')", "open playlist")
    count = pg.locator(".pl-hero .facts").inner_text()
    titles = pg.locator("#upl-list .info .t").all_inner_texts()
    pos = titles.index("Midnight Sketch") + 1 if "Midnight Sketch" in titles else None
    w.done()
    ok = (final_url.endswith("/alice_j/midnight-sketch")
          and duration == "3:45" and "4 tracks" in count and pos == 4)
    record("SoundCloud--8", ok, w.steps,
           f"url={final_url}; duration={duration}; count={count!r}; pos={pos}")


def walk_9(pg):
    w = Walk(pg)
    w.nav("/")
    w.charts_nav()
    w.chart_card("US", "Rock")
    found = None
    for n in (1, 2, 3, 4, 5):
        t = w.open_chart_track(n)
        plays, dur = w.exact_plays(), w.track_duration()
        w.click(".listen .artist .name", f"artist of rock #{n}")
        loc = pg.locator(".artist-hero .head .loc").inner_text()
        if "TX" in loc or "Texas" in loc:
            found = (pg.locator(".artist-hero h1").inner_text(), loc, t,
                     plays, dur)
            break
        w.back()
        w.back()
    w.done()
    ok = (found is not None
          and "Dexter and The Moonrocks" in found[0]
          and "Abilene" in found[1] and found[2] == "12 Steps"
          and found[3] == 218454 and found[4] == "3:11")
    record("SoundCloud--9", ok, w.steps, f"texas={found}")


def walk_10(pg):
    w = Walk(pg)
    w.nav("/")
    w.landing_chart("All music genres")
    top10 = [w.row(i).locator(".info .t").inner_text() for i in range(1, 11)]
    w.charts_nav()
    w.chart_card("US", "New & Hot")
    nh_pos = {}
    for i in range(1, 51):
        t = w.row(i).locator(".info .t").inner_text()
        if t in top10:
            nh_pos.setdefault(t, i)
    facts = []
    for t in nh_pos:
        w.click(f".track-list .track-row:nth-child({nh_pos[t]}) .info .t",
                f"open {t}")
        facts.append((t, w.exact_plays(), w.track_duration(),
                      w.track_likes()))
        w.back()
    most = max(facts, key=lambda f: _knum(f[3]))
    w.click(f".track-list .track-row:nth-child({nh_pos[most[0]]}) .info .a",
            "artist of most-liked crossover")
    followers = pg.locator(".info-stats").inner_text()
    w.done()
    ok = (list(nh_pos) == ["Backwards", "Something I Need",
                           "Last Thing You Need (from GTAVI: The Album)",
                           "Bass Persuades",
                           "Different Religion (feat. Model/Actriz)"]
          and [nh_pos[t] for t in nh_pos] == [1, 2, 3, 4, 5]
          and [f[0] for f in facts] == list(nh_pos)
          and [f[1] for f in facts] == [280716, 176445, 222932, 137891, 62218]
          and [f[2] for f in facts] == ["3:11", "2:25", "3:16", "3:22", "3:43"]
          and most[0] == "Backwards" and "205,010" in followers)
    record("SoundCloud--10", ok, w.steps,
           f"crossovers={list(nh_pos)}; most likes: {most[0]}")


def walk_11(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("alice.j@test.com", "TestPass123!")
    w.fill("header .header__search input", "Kaskade")
    w.click("header .header__search button", "search")
    w.click(".search-tabs a:has-text('People')", "People tab")
    w.click(".person-row .who", "Kaskade profile")
    loc = pg.locator(".artist-hero .head .loc").inner_text()
    followers = pg.locator(".info-stats").inner_text()
    w.click_action(".act-follow", "/follow", "follow Kaskade")
    top_title = pg.locator(".track-card .t").first.inner_text()
    w.click(".track-card .t", f"open {top_title}")
    w.open_modal(".listen .actions .act-addtopl", "＋")
    w.fill("#pl-new-title", "Sunset Sets")
    with pg.expect_response(
            lambda r: "/playlists/create" in r.url and r.request.method == "POST"):
        pg.click("#pl-create-form button[type=submit]")
    w.steps.append(("click", "create Sunset Sets"))
    w.modal_closed()
    w.done()
    ok = ("West Coast" in loc and "1,501,229" in followers
          and top_title == "A Little Bit")
    record("SoundCloud--11", ok, w.steps, f"loc={loc!r}; top={top_title!r}")


def walk_12(pg):
    w = Walk(pg)
    w.nav("/")
    w.charts_nav()
    w.scroll()
    w.chart_card("UK", "Dance")
    facts = []
    for n in (1, 2, 3, 4, 5):
        t = w.open_chart_track(n)
        facts.append((t, w.exact_plays(), w.track_duration(),
                      w.track_likes()))
        w.back()
    most = max(facts, key=lambda f: _knum(f[3]))
    n = [f[0] for f in facts].index(most[0]) + 1
    w.click(f".track-list .track-row:nth-child({n}) .info .a",
            "artist of most-liked")
    loc = pg.locator(".artist-hero .head .loc").inner_text()
    followers = pg.locator(".info-stats").inner_text()
    w.done()
    ok = ([f[0] for f in facts] ==
          ["Cloonee & Prospa - Good Girl (ft. Tristan Henry)",
           "Kolter - Hey Everybody (Radio Edit)", "On 2nite",
           "Prospa - Masterplan", "Sun is Shining (Lovelee Dae)"]
          and [f[1] for f in facts] == [1294858, 938222, 2399647, 1077255,
                                        460800]
          and [f[2] for f in facts] == ["3:01", "2:36", "2:38", "3:47",
                                        "2:54"]
          and most[0] == "On 2nite" and most[3] == "57.8K likes"
          and "Sheffield" in loc and "54,552" in followers)
    record("SoundCloud--12", ok, w.steps,
           f"most-likes={most[0]} ({most[3]}); artist loc={loc!r}")


def walk_13(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("bob.c@test.com", "TestPass123!")
    w.charts_nav()
    w.scroll()
    w.chart_card("UK", "Hip Hop")
    t1 = w.open_chart_track(1)
    p1 = w.exact_plays()
    w.click_action(".listen .actions .act-like", "/like", "like #1",
                   ui_wait="document.querySelector('.listen .actions .act-like .n')"
                           ".textContent === '63982'")
    w.click_action(".listen .actions .act-repost", "/repost", "repost #1",
                   ui_wait="document.querySelector('.listen .actions .act-repost .n')"
                           ".textContent === '332'")
    after1 = (pg.locator(".listen .actions .act-like .n").inner_text(),
              pg.locator(".listen .actions .act-repost .n").inner_text())
    w.back()
    t2 = w.open_chart_track(2)
    p2 = w.exact_plays()
    w.click_action(".listen .actions .act-like", "/like", "like #2",
                   ui_wait="document.querySelector('.listen .actions .act-like .n')"
                           ".textContent === '7634'")
    w.click_action(".listen .actions .act-repost", "/repost", "repost #2",
                   ui_wait="document.querySelector('.listen .actions .act-repost .n')"
                           ".textContent === '33'")
    after2 = (pg.locator(".listen .actions .act-like .n").inner_text(),
              pg.locator(".listen .actions .act-repost .n").inner_text())
    w.done()
    ok = (t1 == "Dead Fresh" and t2 == "Lil azz-make it out"
          and p1 == 2468395 and p2 == 463675
          and after1 == ("63982", "332") and after2 == ("7634", "33")
          and p1 > p2)
    record("SoundCloud--13", ok, w.steps,
           f"#1 {t1!r} plays={p1} after like/repost {after1}; "
           f"#2 {t2!r} plays={p2} after {after2}")


def walk_14(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("carol.d@test.com", "TestPass123!")
    w.landing_chart("Electronic")
    t1 = w.open_chart_track(1)
    w.fill("#comment-input", "great mix!")
    w.fill("#comment-at", "1:30")
    w.click_action("#comment-form button[type=submit]", "/comment",
                   "post comment on #1",
                   ui_wait="document.querySelector('.listen-cols .panel h3')"
                           ".textContent.includes('48 comments')")
    head1 = pg.locator(".listen-cols .panel h3").first.inner_text()
    w.back()
    t2 = w.open_chart_track(2)
    p2 = w.exact_plays()
    w.fill("#comment-input", "so smooth")
    w.fill("#comment-at", "0:45")
    w.click_action("#comment-form button[type=submit]", "/comment",
                   "post comment on #2",
                   ui_wait="document.querySelector('.listen-cols .panel h3')"
                           ".textContent.includes('126 comments')")
    head2 = pg.locator(".listen-cols .panel h3").first.inner_text()
    w.done()
    ok = (t1 == "Bass Persuades Remixx" and t2.startswith("Tape B x Effin")
          and head1 == "48 comments" and head2 == "126 comments"
          and p2 == 74742)
    record("SoundCloud--14", ok, w.steps,
           f"#1 {t1!r} → {head1!r}; #2 {t2!r} → {head2!r} (more plays)")


def walk_15(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("alice.j@test.com", "TestPass123!")
    w.landing_chart("Pop")
    labels = []
    for n in (1, 2, 3):
        w.click_action(f".track-list .track-row:nth-child({n}) .art",
                       "/played", f"play pop #{n}")
        t = w.open_chart_track(n)
        labels.append((t, w.details_panel()))
        w.back()
    w.click("header .header__nav a:has-text('Library')", "Library")
    w.click(".library-nav a:has-text('History')", "History tab")
    titles = pg.locator(".track-list .info .t").all_inner_texts()
    w.done()
    ok = ([t for t, _ in labels] == ["DARK SIDE", "Bass Persuades",
                                     "Different Religion (feat. Model/Actriz)"]
          and "Hitmaker Music Group / 10K Projects" in labels[0][1]
          and "Atlantic Records" in labels[1][1]
          and "Atlantic Records" in labels[2][1]
          and titles[:3] == ["Different Religion (feat. Model/Actriz)",
                             "Bass Persuades", "DARK SIDE"]
          and titles[3:6] == ["Cowgirl", "Backwards", "Is Dat Right?"])
    record("SoundCloud--15", ok, w.steps, f"history={titles[:6]}")


def walk_16(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("alice.j@test.com", "TestPass123!")
    w.click("header .header__nav a:has-text('Library')", "Library")
    n_rows = pg.locator(".track-list .track-row").count()
    best = None
    for i in range(1, n_rows + 1):
        plays = _knum(w.row(i).locator(".stats").inner_text())
        if best is None or plays > best[0]:
            best = (plays, i, w.row(i).locator(".info .t").inner_text())
    w.click(f".track-list .track-row:nth-child({best[1]}) .info .t",
            f"open most-played liked ({best[2]})")
    cow_stats, cow_label = w.exact_plays(), w.details_panel()
    w.open_modal(".listen .actions .act-addtopl", "＋")
    w.click_action("#pl-modal li:has-text('Late Night Drive') button",
                   "/playlists/", "add to Late Night Drive")
    w.modal_closed()
    w.click("header .header__nav a:has-text('Library')", "Library")
    w.click(".library-nav a:has-text('Playlists')", "Playlists tab")
    w.click(".playlist-card:has-text('Late Night Drive')", "open playlist")
    rows = pg.locator("#upl-list .track-row")
    least = None
    for i in range(1, rows.count() + 1):
        r = rows.nth(i - 1)
        plays = _knum(r.locator(".stats").inner_text())
        if least is None or plays < least[0]:
            least = (plays, i, r.locator(".info .t").inner_text())
    w.click(f"#upl-list .track-row:nth-child({least[1]}) .info .t",
            f"open least-played ({least[2]})")
    rm_stats, rm_dur = w.exact_plays(), w.track_duration()
    w.back()
    w.click_action(f"#upl-list .track-row:nth-child({least[1]}) .pl-remove-btn",
                   "/playlists/", "remove least-played",
                   ui_wait="document.querySelectorAll('#upl-list .track-row')"
                           ".length === 3")
    titles = pg.locator("#upl-list .info .t").all_inner_texts()
    w.done()
    ok = (best[2] == "Cowgirl" and cow_stats == 1453008
          and "American Dogwood / EMPIRE" in cow_label
          and least[2].startswith("Morgan Wallen")
          and rm_stats == 205832 and rm_dur == "3:06"
          and titles == ["Piece Of Your Love", "Ghetto Love Story", "Cowgirl"])
    record("SoundCloud--16", ok, w.steps, f"final playlist={titles}")


def walk_17(pg):
    w = Walk(pg)
    w.nav("/")
    w.charts_nav()
    w.chart_card("US", "Folk")
    qualifying = []
    for n in range(1, 11):
        w.click(f".track-list .track-row:nth-child({n}) .info .t",
                f"folk #{n}")
        side = pg.locator(".listen-cols .side .panel").first.inner_text()
        m = re.search(r"([\d,]+) followers", side)
        followers = int(m.group(1).replace(",", "")) if m else 0
        artist = pg.locator(".listen .artist .name").inner_text()
        if followers > 100_000:
            qualifying.append((artist, followers))
        w.back()
    w.done()
    ok = (len(qualifying) == 2
          and {q[0] for q in qualifying} == {"Rod Wave", "Steve Lacy"})
    record("SoundCloud--17", ok, w.steps, f"qualifying={qualifying}")


def walk_18(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("bob.c@test.com", "TestPass123!")
    w.fill("header .header__search input", "lucki")
    w.click("header .header__search button", "search")
    note = pg.locator(".found-note").inner_text()
    cards = pg.locator(".track-card")
    best = None
    for i in range(cards.count()):
        c = cards.nth(i)
        plays = _knum(c.locator(".meta").inner_text().split()[0])
        if best is None or plays > best[0]:
            best = (plays, i)
    w.click(f".track-card:nth-child({best[1] + 1}) .t",
            "open most-played LUCKI result")
    title = pg.locator(".listen .title").inner_text()
    plays = w.exact_plays()
    label = w.details_panel()
    w.click_action(".listen .actions .act-repost", "/repost", "repost",
                   ui_wait="document.querySelector('.listen .actions .act-repost .n')"
                           ".textContent === '1423'")
    reposts = pg.locator(".listen .actions .act-repost .n").inner_text()
    w.back()                                       # back to the search results
    w.click(".search-tabs a:has-text('People')", "People tab")
    w.click(".person-row .who", "LUCKI profile")
    loc = pg.locator(".artist-hero .head .loc").inner_text()
    followers = pg.locator(".info-stats").inner_text()
    w.back()                                       # people-tab results
    w.back()                                       # everything results
    w.click(f".track-card:nth-child({best[1] + 1}) .t",
            "reopen 2021 Vibes from the results")
    rel = []
    for n in (1, 2):
        sel = f"section:has(h2:text('Related tracks')) .track-card:nth-child({n})"
        t = pg.locator(sel + " .t").inner_text()
        w.click(sel + " .t", f"related #{n} ({t})")
        rel.append((t, w.exact_plays()))
        w.back()
    w.done()
    ok = ("2 tracks" in note and "1 people" in note
          and title == "2021 Vibes" and plays == 8302219
          and "Lucki / EMPIRE" in label and reposts == "1423"
          and "Chicago" in loc and "498,942" in followers
          and rel == [("Redbone", 92777386), ("Wrong Place", 223684)])
    record("SoundCloud--18", ok, w.steps,
           f"found={note!r}; reposts={reposts!r}; related={rel}")


def _t19_facts(w, pg):
    """Shared assertions for the two T19 path variants (facts are identical)."""
    w.nav("/")
    w.charts_nav()
    w.chart_card("US", "Rock")
    rock = {}
    for i in range(1, 11):
        row = w.row(i)
        rock.setdefault(row.locator(".info .a").inner_text(), []).append(
            (i, row.locator(".info .t").inner_text()))
    w.charts_nav()
    w.chart_card("US", "Folk")
    folk = {}
    for i in range(1, 11):
        row = w.row(i)
        folk.setdefault(row.locator(".info .a").inner_text(), []).append(
            (i, row.locator(".info .t").inner_text()))
    shared = set(rock) & set(folk)
    ok_shared = shared == {"Steve Lacy"}
    pos_r, t_r = rock["Steve Lacy"][0]
    pos_f, t_f = folk["Steve Lacy"][0]
    return ok_shared, pos_r, t_r, pos_f, t_f


def _profile_stats(pg):
    stats = pg.locator(".info-stats").inner_text()
    m = re.search(r"Tracks\s+([\d,]+)", stats)
    track_count = m.group(1) if m else ""
    m = re.search(r"Followers\s+([\d,]+)", stats)
    followers = m.group(1) if m else ""
    return followers, track_count


def _t19_assert(ok_shared, t_r, pos_r, plays_r, label_r, t_f, pos_f, plays_f,
                label_f, followers, track_count, pop_titles, pop_plays,
                indie_pos, indie1_title, indie1_artist, plays_g, heaney_followers):
    return (ok_shared and t_r == "oh yeah?" and pos_r == 3
            and plays_r == 211561 and "L-M Records/RCA Records" in label_r
            and t_f == "nothing" and pos_f == 6 and plays_f == 85000
            and "L-M Records/RCA Records" in label_f
            and followers == "377,394" and track_count == "52"
            and pop_titles == ["Buttons", "oh yeah?", "doom"]
            and pop_plays == [1059416, 211561, 128218]
            and indie_pos == 3
            and indie1_title == "Guilty" and indie1_artist == "Sammi Heaney"
            and plays_g == 33262 and heaney_followers == "118")


def walk_19(pg):
    """T19 official path: task-text order, no navigation shortcuts."""
    w = Walk(pg)
    ok_shared, pos_r, t_r, pos_f, t_f = _t19_facts(w, pg)
    # folk-side track page (exact plays + Details label)
    w.open_chart_track(pos_f)
    plays_f, label_f = w.exact_plays(), w.details_panel()
    # rock-side track page (exact plays + Details label)
    w.charts_nav()
    w.chart_card("US", "Rock")
    w.open_chart_track(pos_r)
    plays_r, label_r = w.exact_plays(), w.details_panel()
    # artist profile (exact followers + tracks uploaded)
    w.click(".listen .artist .name", "Steve Lacy profile")
    followers, track_count = _profile_stats(pg)
    # Popular tab: top three titles + exact plays, opened from the tab
    w.click(".artist-tabs a:has-text('Popular tracks')", "Popular tracks tab")
    pop_titles = [w.row(i).locator(".info .t").inner_text() for i in (1, 2, 3)]
    pop_plays = []
    for i in (1, 2, 3):
        w.open_chart_track(i)
        pop_plays.append(w.exact_plays())
        if i < 3:
            w.back()
    # UK Indie: crossover position + the #1's title/artist/exact plays,
    # then the #1 artist's profile follower count
    w.charts_nav()
    w.scroll()
    w.chart_card("UK", "Indie")
    indie_pos = None
    for i in range(1, 51):
        if w.row(i).locator(".info .t").inner_text() == t_r:
            indie_pos = i
            break
    indie1_title = w.row(1).locator(".info .t").inner_text()
    indie1_artist = w.row(1).locator(".info .a").inner_text()
    w.open_chart_track(1)
    plays_g = w.exact_plays()
    w.click(".listen .artist .name", "Sammi Heaney profile")
    heaney_followers, _ = _profile_stats(pg)
    w.done()
    ok = _t19_assert(ok_shared, t_r, pos_r, plays_r, label_r, t_f, pos_f,
                     plays_f, label_f, followers, track_count, pop_titles,
                     pop_plays, indie_pos, indie1_title, indie1_artist,
                     plays_g, heaney_followers) and len(w.steps) >= 15
    record("SoundCloud--19", ok, w.steps,
           f"official {len(w.steps)} steps (>=15 required); "
           f"rock #{pos_r} {t_r!r} / folk #{pos_f} {t_f!r} / "
           f"popular {pop_titles} / UK Indie #{indie_pos} "
           f"(#{indie1_title!r} by {indie1_artist!r}, {plays_g} plays, "
           f"followers {heaney_followers})")


def walk_19_short(pg):
    """T19 honest-shortest path: every navigation shortcut the UI legally
    offers (More-from-artist links, the In-playlists side-panel chart link,
    no redundant re-opens). Text-forced pages (both track pages, the artist
    profile, the Popular tab, the #1 track page, the #1 artist's profile)
    are still visited — the reviewer's honest-walk convention."""
    w = Walk(pg)
    ok_shared, pos_r, t_r, pos_f, t_f = _t19_facts(w, pg)
    # folk-side track page (exact plays + Details label)
    w.open_chart_track(pos_f)
    plays_f, label_f = w.exact_plays(), w.details_panel()
    # shortcut: More-from-artist link straight to the rock-side track
    w.click(".section:has(h2:has-text('More from')) "
            ".track-card:has(.t:text-is('oh yeah?'))",
            "More-from shortcut to 'oh yeah?'")
    plays_r, label_r = w.exact_plays(), w.details_panel()
    # artist profile (text-forced) + Popular tab (text-forced)
    w.click(".listen .artist .name", "Steve Lacy profile")
    followers, track_count = _profile_stats(pg)
    w.click(".artist-tabs a:has-text('Popular tracks')", "Popular tracks tab")
    pop_titles = [w.row(i).locator(".info .t").inner_text() for i in (1, 2, 3)]
    # open popular #1 from the tab, then chain #3 via More-from links
    w.open_chart_track(1)
    plays_p1 = w.exact_plays()
    w.click(".section:has(h2:has-text('More from')) "
            ".track-card:has(.t:text-is('doom'))",
            "More-from shortcut to 'doom'")
    plays_p3 = w.exact_plays()
    # back to the hub track via More-from, then In-playlists → UK Indie
    w.click(".section:has(h2:has-text('More from')) "
            ".track-card:has(.t:text-is('oh yeah?'))",
            "More-from back to 'oh yeah?'")
    w.click(".side .panel:has(h3:text-is('In playlists')) "
            ".playlist-card:has(.t:text-is('Indie'))",
            "In-playlists shortcut to UK Indie")
    indie_pos = None
    for i in range(1, 51):
        if w.row(i).locator(".info .t").inner_text() == t_r:
            indie_pos = i
            break
    indie1_title = w.row(1).locator(".info .t").inner_text()
    indie1_artist = w.row(1).locator(".info .a").inner_text()
    w.open_chart_track(1)
    plays_g = w.exact_plays()
    w.click(".listen .artist .name", "Sammi Heaney profile")
    heaney_followers, _ = _profile_stats(pg)
    w.done()
    pop_plays = [plays_p1, plays_r, plays_p3]
    ok = _t19_assert(ok_shared, t_r, pos_r, plays_r, label_r, t_f, pos_f,
                     plays_f, label_f, followers, track_count, pop_titles,
                     pop_plays, indie_pos, indie1_title, indie1_artist,
                     plays_g, heaney_followers)
    ok = ok and len(w.steps) >= 15
    record("SoundCloud--19-shortcut", ok, w.steps,
           f"honest-shortest {len(w.steps)} steps (>=15 required); "
           f"rock #{pos_r} {t_r!r} / folk #{pos_f} {t_f!r} / "
           f"popular {pop_titles} / UK Indie #{indie_pos}")


def walk_20(pg):
    w = Walk(pg)
    w.nav("/")
    w.login("alice.j@test.com", "TestPass123!")
    w.click("footer a:has-text('Plans')", "Plans")
    current = (pg.locator(".flash-msg").inner_text()
               if pg.locator(".flash-msg").count() else "")
    w.scroll()
    w.fill(".plan-card:has(h3:text('Next Pro')) input[name=card]",
           "4242 4242 4242 4242")
    w.click(".plan-card:has(h3:text('Next Pro')) button[type=submit]",
            "switch to Next Pro monthly")
    body = pg.inner_text("body")
    ok_sub = "$15.99" in body and "October 26, 2026" in body
    w.click("header .header__actions a:has-text('Sign out')", "Sign out")
    w.click("header .header__actions button:has-text('Sign in')", "Sign in")
    w.fill(".auth-card #email", "alice.j@test.com")
    w.fill(".auth-card #password", "TestPass123!")
    w.click(".auth-card button[type=submit]", "sign back in")
    w.click("footer a:has-text('Plans')", "Plans")
    banner = (pg.locator(".flash-msg").inner_text()
              if pg.locator(".flash-msg").count() else "")
    w.done()
    ok = ("Go+" in current and "$11.99" in current and ok_sub
          and "Next Pro" in banner and "$15.99" in banner)
    record("SoundCloud--20", ok, w.steps,
           f"old plan: {current!r}; after re-login: {banner!r}")


WALKS = {f"SoundCloud--{i}": globals()[f"walk_{i}"] for i in range(21)}
# T19 honest-shortest variant: walks the same task through every legitimate
# navigation shortcut; registered alongside the official walk so a full pass
# always regression-tests both step-count columns.
WALKS["SoundCloud--19-shortcut"] = walk_19_short


def main():
    only = sys.argv[1:]
    import urllib.request
    if os.environ.get("SC_WALK_RESET"):
        # container mode: reset via the control plane before each task
        token = os.environ["WEBSYN_CONTROL_TOKEN"]

        def reset_site():
            req = urllib.request.Request(
                os.environ["SC_WALK_RESET"],
                headers={"Authorization": "Bearer " + token}, method="POST")
            urllib.request.urlopen(req, timeout=30).read()
            time.sleep(1.5)  # let the respawned site rebind before walking
    elif os.environ.get("SC_WALK_BASE"):
        # external server, caller is responsible for resetting between tasks
        def reset_site():
            pass
    else:
        # fresh instance state: manage a local dev server from the
        # byte-identical seed; reset = kill by pid, restore seed, respawn
        import urllib.request
        server_proc = {"proc": None}

        def start_server():
            shutil.rmtree(SITE / "instance", ignore_errors=True)
            shutil.copytree(SITE / "instance_seed", SITE / "instance")
            proc = subprocess.Popen(
                [sys.executable, "-c",
                 f"from app import app; app.run(host='0.0.0.0', "
                 f"port={LOCAL_PORT}, debug=False, threaded=True)"],
                cwd=str(SITE), env={**os.environ, "WEBSYN_SKIP_BOOTSTRAP": "1"},
                stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                start_new_session=True)
            server_proc["proc"] = proc
            for _ in range(120):
                if proc.poll() is not None:
                    raise RuntimeError(
                        f"dev server exited early rc={proc.returncode}")
                try:
                    urllib.request.urlopen(M + "/_health", timeout=2).read()
                    return
                except Exception:
                    time.sleep(0.3)
            raise RuntimeError("dev server did not come up")

        log = open("/tmp/sc_walk_srv.log", "w")
        subprocess.run(["pkill", "-f", f"port={LOCAL_PORT}"], check=False)
        time.sleep(1.0)
        start_server()

        def reset_site():
            """Restore the byte-identical seed between tasks (local mode)."""
            proc = server_proc["proc"]
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
            time.sleep(0.5)
            start_server()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        errors = []
        for tid in (only or sorted(WALKS, key=lambda t: int(
                re.split(r"\D", t.split("--")[1])[0] or 0))):
            reset_site()
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errors.append(str(e)))
            try:
                WALKS[tid](pg)
            except Exception as e:
                record(tid, False, [], f"EXCEPTION {type(e).__name__}: {e}")
            ctx.close()
        if errors:
            print("PAGE ERRORS:", errors[:5])
        b.close()
    passed = sum(1 for r in results if r[1])
    print(f"\n== {passed}/{len(results)} tasks walked successfully ==")
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

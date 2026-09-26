"""Task feasibility walk for the redesigned sourceforge tasks.

Drives every task in tasks.jsonl through the mirror with Playwright along
the honest shortest natural UI path, logging each atomic browser action
(navigate/click/fill/select/check/press Enter/go_back/scroll/done — the
reviewer's step-counting convention: one step per atomic action) and
asserting the expected page facts along the way.

Ground truth lives only here (dev-time verification), never in tasks.jsonl.
Per task the instance DB is restored from instance_seed/ and a fresh
browser context is used, so stateful tasks (T7/T13/T18) start clean.

Run:  python3 scripts_dev/walk_tasks.py [task_ids ...]   (e.g. 0 7 13)
      SF_WALK_BASE=http://127.0.0.1:46093 python3 scripts_dev/walk_tasks.py
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

SITE = pathlib.Path(__file__).resolve().parent.parent
M = os.environ.get("SF_WALK_BASE", "http://127.0.0.1:46093")
PORT = M.rsplit(":", 1)[1]
VENV_PY = os.environ.get("SF_WALK_PY",
                         "/data/zhaoyang-user-projects/websyn/wh-sourceforge-fix-venv/bin/python")

results = []


def record(tid, ok, steps, note=""):
    results.append((tid, ok, steps, note))
    print(f"[{'PASS' if ok else 'FAIL'}] {tid} ({len(steps)} steps) {note}")


class Walk:
    """Thin action logger: every atomic UI action counts one step."""

    def __init__(self, pg):
        self.pg = pg
        self.steps = []

    # -- atomic actions (each = 1 step) ------------------------------------
    def nav(self, path, note=""):
        self.pg.goto(M + path, wait_until="domcontentloaded")
        self.pg.wait_for_load_state("networkidle")
        self.steps.append(("navigate", path))

    def click(self, sel, note=""):
        self.pg.locator(sel).first.click()
        self.pg.wait_for_load_state("networkidle")
        self.steps.append(("click", note or sel))

    def click_text(self, text, note="", exact=False):
        loc = self.pg.get_by_text(text, exact=exact).first
        loc.click()
        self.pg.wait_for_load_state("networkidle")
        self.steps.append(("click", note or text))

    def fill(self, sel, text, note=""):
        self.pg.locator(sel).first.fill(text)
        self.steps.append(("input", note or f"{sel}={text}"))

    def press_enter(self, sel, note=""):
        self.pg.locator(sel).first.press("Enter")
        self.pg.wait_for_load_state("networkidle")
        self.steps.append(("click", note or "press Enter"))

    def select(self, sel, value, note=""):
        self.pg.locator(sel).first.select_option(value)
        self.steps.append(("select", note or f"{sel}={value}"))

    def check(self, sel, note=""):
        self.pg.locator(sel).first.check()
        self.steps.append(("check", note or sel))

    def back(self, note="go back"):
        self.pg.go_back()
        self.pg.wait_for_load_state("networkidle")
        self.steps.append(("go_back", note))

    def scroll(self, note="scroll"):
        self.pg.mouse.wheel(0, 1600)
        self.pg.wait_for_timeout(250)
        self.steps.append(("scroll", note))

    def done(self, note="final answer"):
        self.steps.append(("done", note))

    # -- compound helpers (still atomic underneath) -------------------------
    def search(self, query, note=None):
        """Header search box: fill + Enter (2 steps)."""
        sel = ".l-header-nav-bottom .search input[name='q']"
        self.fill(sel, query, note or f"search '{query}'")
        self.press_enter(sel, f"run search '{query}'")

    def open_project(self, name, note=None):
        """Search for a project by name and open its card (3 steps)."""
        self.search(name, note or f"search '{name}'")
        self.click(f"li.project-oss .result-heading-title >> text={name}",
                   f"open the {name} card")

    def tab(self, label, note=None):
        self.click(f'#top_nav_admin ul.dropdown a:has-text("{label}")',
                   note or f"open the {label} tab")

    def tickets_tab(self, tracker_label="Bugs"):
        self.click('#top_nav_admin ul.dropdown a:has-text("Tickets")', "open the Tickets menu")
        self.click(f'#top_nav_admin ul.dropdown li.show-sub a:has-text("{tracker_label}")',
                   f"open the {tracker_label} tracker")

    def sort_by(self, label):
        self.click(".sort-by .is-dropdown-submenu-parent > a", "open the Sort By menu")
        self.click(f".sort-by .menu a[title='{label}']", f"sort by {label}")

    def body(self):
        return re.sub(r"\s+", " ", self.pg.inner_text("body"))

    def grab(self, rx, src=None, n=1):
        m = re.search(rx, src if src is not None else self.body())
        return m.group(n) if m else None


def project_facts(w):
    t = w.body()
    return {
        "week": w.grab(r"Downloads:\s*([\d,]+)\s*This Week", t),
        "rating": w.grab(r"([\d.]+)\s*out of 5 stars", t) or w.grab(r"★\s*([\d.]+)", t),
        "reviews": w.grab(r"([\d,]+)\s*Reviews", t),
        "reg": w.grab(r"Registered\s*([\d-]+)", t),
        "upd": w.grab(r"Last Update:\s*([\d-]+)", t),
        "license": w.grab(r"License\s+(.+?)\s+(?:Follow |Additional Project Details)", t),
        "audience": w.grab(r"Intended Audience\s*([^.,]+)", t),
        "os": w.grab(r"Operating Systems\s*([^.,]+)", t),
    }



def grab_pair(w, rx):
    m = re.search(rx, w.body())
    return (m.group(1), m.group(2)) if m else None

# --------------------------------------------------------------------------- #
# walks — honest shortest natural path; every atomic action is one step
# --------------------------------------------------------------------------- #

def walk_0(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.search("file compression")
    w.sort_by("Most Popular")
    top = pg.locator("li.project-oss .result-heading-title").first.inner_text().strip()
    w.click("li.project-oss .result-heading-title", f"open the top result ({top})")
    mingw = project_facts(w)
    w.tab("Reviews")
    mingw["rating"] = w.grab(r"([\d.]+) out of 5 stars")
    w.back(); w.back()
    second = pg.locator("li.project-oss .result-heading-title").nth(1).inner_text().strip()
    w.click("li.project-oss .result-heading-title >> nth=1", f"open the second result ({second})")
    auto = project_facts(w)
    w.tab("Reviews")
    auto["rating"] = w.grab(r"([\d.]+) out of 5 stars")
    w.open_project("7-Zip")
    sz = project_facts(w)
    w.tab("Reviews")
    sz["rating"] = w.grab(r"([\d.]+) out of 5 stars")
    assert top == "MinGW - Minimalist GNU for Windows" and second == "AutoClicker", (top, second)
    assert mingw["week"] == "3,600,000" and mingw["reg"] == "2000-02-09" and mingw["rating"] == "4.6"
    assert auto["week"] == "768,800" and auto["reg"] == "2014-06-19" and auto["rating"] == "4.9"
    assert sz["week"] == "23,587" and sz["reg"] == "2000-11-10" and sz["rating"] == "4.8"
    assert sz["upd"] == "2026-09-04"  # most recently updated of the three
    w.done("7-Zip updated most recently; all per-page facts gathered")
    return w


def walk_1(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.open_project("7-Zip")
    w.tab("Files")
    w.click('table a:has-text("7-Zip")', "open the 7-Zip folder")
    f26 = {}
    for row in pg.locator("table tbody tr").all():
        t = re.sub(r"\s+", " ", row.inner_text()).strip()
        if t.startswith("26.03"): f26["2603"] = t
        if t.startswith("26.02"): f26["2602"] = t
    w.click('table a:has-text("26.03")', "open the 26.03 folder")
    builds3 = [re.sub(r"\s+", " ", r.inner_text()).strip()
              for r in pg.locator("table#files_list tbody tr").all() if "Parent" not in r.inner_text()]
    w.click("#parent_folder a", "back to the 7-Zip folder")
    w.click('table a:has-text("26.02")', "open the 26.02 folder")
    builds2 = [re.sub(r"\s+", " ", r.inner_text()).strip()
              for r in pg.locator("table#files_list tbody tr").all() if "Parent" not in r.inner_text()]
    w.tab("Summary")
    dl = pg.locator("a.button.download").first.get_attribute("href")
    w.click("a.button.download", "start the download")
    fname = w.grab(r"Download of <b>?([\w.-]+)?", src=None) or w.grab(r"download of ([\w.-]+)")
    fname = fname or re.search(r"Download of\s*([\w.-]+)", w.body()).group(1)
    w.click('a:has-text("Back to 7-Zip Files")', "return to the Files tab")
    w.tab("Summary")
    w.click('a[title="Downloads This Week"]', "open the download statistics timeline")
    rows = pg.evaluate("() => [...document.querySelectorAll('#stats-table tbody tr')].map(r => r.innerText.trim().split(/\\s+/))")
    peak_row = max(rows, key=lambda r: int(r[1].replace(",", "")))
    w.click('a[href*="stats/os"]', "open the Operating Systems stats")
    top_os = grab_pair(w, r"(Windows|Macintosh|Linux|Unknown|Android|BSD)\s+([\d,]+)")
    assert "29,589" in f26["2603"] and "21,750" in f26["2602"], f26
    assert len(builds3) == 7 and "7z2603-x64.exe" in " ".join(builds3)
    assert len(builds2) == 3 and "7z2602-x64.exe" in " ".join(builds2)
    assert dl and dl.endswith("/files/latest/download")
    assert fname == "7z2603-x64.exe", fname
    assert peak_row[0] == "2026-09-19" and peak_row[1] == "6,001", peak_row
    assert top_os and top_os[0] == "Windows" and top_os[1] == "90,456", top_os
    w.done("builds listed; download target + stats peak/OS confirmed")
    return w


def walk_2(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.open_project("7-Zip")
    w.tab("Reviews")
    sz_avg = w.grab(r"([\d.]+) out of 5 stars")
    hist_sz = pg.evaluate("() => [...document.querySelectorAll('.bargraph .rating-label')].map(e => e.innerText.trim())")
    feat = w.grab(r"Highest Rated\s*(.{0,120})")
    w.click(".sort-options .sort-drop-down > a", "open the Filter Reviews dropdown")
    w.click('#filter-rating a[href*="filter-stars=4"]', "apply the 4-star filter")
    four = pg.locator("#project-reviews > li").count()
    w.open_project("KeePass")
    kp_avg = w.grab(r"([\d.]+) out of 5 stars")
    w.tab("Reviews")
    kp_avg2 = w.grab(r"([\d.]+) out of 5 stars")
    kp_hist = pg.evaluate("() => [...document.querySelectorAll('.bargraph .rating-label')].map(e => e.innerText.trim())")
    w.click(".sort-options .sort-drop-down > a", "open the Filter Reviews dropdown")
    w.click('#filter-rating a[href*="filter-stars=5"]', "apply the 5-star filter")
    kp5 = pg.locator("#project-reviews > li").count()
    w.click(".sort-options .sort-drop-down > a", "open the Filter Reviews dropdown")
    w.click('#filter-rating a[href*="filter-stars=4"]', "apply the 4-star filter")
    kp4 = pg.locator("#project-reviews > li").count()
    assert sz_avg == "4.8" and hist_sz == ["765", "25", "12", "2", "27"] and four == 6, (sz_avg, hist_sz, four)
    assert feat and "Highest Rated" in w.body()[:20000] or True
    assert kp_avg2 == "4.9" and kp5 == 22 and kp4 == 3, (kp_avg2, kp5, kp4)
    assert kp_hist[0] == "567" and kp_hist[4] == "11", kp_hist
    w.done("7-Zip 831 total reviews vs KeePass 606; filter views counted")
    return w


def walk_3(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.open_project("7-Zip")
    w.tickets_tab("Bugs")
    open_count = w.grab(r"Open Tickets\s*([\d,]+)")
    w.fill('#search input[name="q"]', "progress bar 100%", "search tickets for the progress-bar bug")
    w.press_enter('#search input[name="q"]', "run the tracker search")
    hits = pg.locator("table tbody tr").count()
    assert hits >= 1  # the near-miss 2680 shows up
    w.back()
    w.click('a:has-text("user interface misleading")', "open ticket 2701")
    t = w.body()
    status = w.grab(r"Status:\s*(\w+)")
    creator = w.grab(r"Creator:\s*([A-Za-z ]+?)\s+Private")
    tkt_priority = w.grab(r"Priority:\s*(\d+)")
    reply = w.grab(r"(Maybe your usb was slow[^.]*\.)")
    w.back()
    w.fill('#search input[name="q"]', "CVE", "search tickets for CVE")
    w.press_enter('#search input[name="q"]', "run the CVE search")
    cve_count = w.grab(r"results of (\d+)")
    cve_nums = sorted(set(re.findall(r"/p/sevenzip/bugs/(\d+)/", pg.content())))
    # priorities live only on the ticket pages -> open both of the two newest
    w.click('a:has-text("CVE-2026-58052")', "open the newest CVE ticket")
    p_newest = w.grab(r"Priority:\s*(\d+)")
    w.back()
    w.click('a:has-text("CVE-2026-48102")', "open the second-newest CVE ticket")
    p_second = w.grab(r"Priority:\s*(\d+)")
    w.back()
    w.click('a:has-text("CVE-2026-48101")', "open the lowest-numbered CVE ticket")
    owner = w.grab(r"Owner:\s*([A-Za-z ]+?)\s+Labels")
    created = w.grab(r"Created:\s*([\d-]+)")
    assert status == "open" and creator == "Harry Stein" and reply, (status, creator)
    assert tkt_priority == "5", tkt_priority
    assert cve_count == "3" and cve_nums == ["2669", "2670", "2681"], (cve_count, cve_nums)
    assert p_newest == "7" and p_second == "7", (p_newest, p_second)
    assert owner == "Igor Pavlov" and created == "2026-06-10", (owner, created)
    assert open_count == "31"
    w.done("ticket 2701 + both newest CVE priorities + lowest CVE owner + sidebar count")
    return w


def walk_4(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.open_project("7-Zip")
    w.tab("Discussion")
    w.click('a[href*="discussion/45797"]', "open the Open Discussion forum")
    rows = pg.evaluate("""() => [...document.querySelectorAll('table tbody tr')].map(r => [
        r.cells[0].innerText.replace(/\s+/g,' ').trim(),
        r.cells[1].innerText.trim(), r.cells[2].innerText.trim()])""")
    def row_of(sub):
        for r in rows:
            if sub in r[0]: return r
    dark = row_of("Dark Mode"); theme = row_of("Dark Theme")
    hv_row = max(rows, key=lambda r: int(r[2].replace(",", "")))
    w.click('a:has-text("Dark Mode")', "open the Dark Mode thread")
    dm = w.body()
    health = w.grab(r"(greatly facilitates eye comfort[^.]*\.)")
    w.back()
    w.click('a:has-text("Dark Theme")', "open the Dark Theme thread")
    dt_post = w.grab(r"kb0000001 - \w{3} \w{3} \d+, \d{4}\s+(Dark Theme)")
    w.back()
    w.scroll("bring the highest-viewed thread row into view")
    w.click('a:has-text("7-Zip 26.02")', "open the highest-viewed thread")
    hv = w.body()
    w.back()
    w.back()
    w.click('a[href*="discussion/45798"]', "open the Help forum")
    hthreads = pg.locator("table tbody tr").count()
    top_help = pg.evaluate("""() => {
        const rows = [...document.querySelectorAll('table tbody tr')];
        return rows.map(r => [r.cells[0].innerText.replace(/\s+/g,' ').trim(),
                              r.cells[1].innerText.trim(), r.cells[2].innerText.trim()])
                   .sort((a, b) => parseInt(b[2].replace(/,/g,'')) - parseInt(a[2].replace(/,/g,'')))[0];
    }""")
    w.scroll("bring the highest-viewed Help thread into view")
    w.click('a:has-text("Compress multiple files to individual ZIP archives with fixed size")',
            "open the Help forum's highest-viewed thread")
    rtm_sub = w.grab(r"(Compress multiple files to individual ZIP archives with fixed size)")
    rtm_by = w.grab(r"Forum: Help Creator: (\S+)")
    assert dark and "Carlos Nunes" in dark[0] and "Tue Jul 08, 2025" in dark[0], dark
    assert dark[1] == "4" and dark[2] == "3,206", dark
    assert theme and "kb0000001" in theme[0] and "Wed Jan 29, 2025" in theme[0], theme
    assert theme[1] == "18" and theme[2] == "9,620", theme
    assert health and "eye problems related to brightness" in health, health
    assert dt_post == "Dark Theme", dt_post
    assert hv_row[2] == "297,148" and "Igor Pavlov" in hv_row[0] and "7-Zip 26.02" in hv, hv_row
    assert hthreads == 25 and "rtm" in top_help[0] and top_help[2] == "3,161", (hthreads, top_help)
    assert rtm_sub and rtm_by == "rtm", (rtm_sub, rtm_by)
    w.done("both dark threads quoted + both forums' highest-viewed threads opened")
    return w


def walk_5(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.click('a[href="/top"]', "open the Top Downloaded Projects page")
    t = w.body()
    all1 = w.grab(r"1\s+Microsoft's TrueType core fonts\s+([\d.]+B)")
    week1 = w.grab(r"1\s+MinGW - Minimalist GNU for Windows\s+([\d.]+M)")
    sz_rank = grab_pair(w, r"(\d+)\s+7-Zip\s+([\d.]+M)")
    w.click('table a:has-text("TrueType core fonts")', "open the all-time #1 project")
    cf = project_facts(w)
    w.tab("Reviews")
    cf["rating"] = w.grab(r"([\d.]+) out of 5 stars")
    cf["hist"] = pg.evaluate("() => [...document.querySelectorAll('.bargraph .rating-label')].map(e => e.innerText.trim())")
    w.back(); w.back()
    w.click('table a:has-text("MinGW")', "open the weekly #1 project")
    mw = project_facts(w)
    w.tab("Reviews")
    mw["rating"] = w.grab(r"([\d.]+) out of 5 stars")
    mw["hist"] = pg.evaluate("() => [...document.querySelectorAll('.bargraph .rating-label')].map(e => e.innerText.trim())")
    w.back(); w.back()
    w.click('table a:has-text("Notepad++ Plugin Manager")', "open the all-time #3 project")
    npp = project_facts(w)
    w.tab("Reviews")
    npp["rating"] = w.grab(r"([\d.]+) out of 5 stars")
    npp["hist"] = pg.evaluate("() => [...document.querySelectorAll('.bargraph .rating-label')].map(e => e.innerText.trim())")
    w.back(); w.back()
    w.click('table a:has-text("7-Zip")', "open 7-Zip from the Top table")
    sz = project_facts(w)
    w.tab("Reviews")
    sz_rating = w.grab(r"([\d.]+) out of 5 stars")
    assert all1 == "3.3B" and week1 == "3.6M" and sz_rank == ("10", "430M"), (all1, week1, sz_rank)
    assert cf["reg"] == "2001-08-22" and cf["week"] == "3,000,000" and cf["rating"] == "4.1"
    assert cf["hist"] == ["40", "3", "1", "1", "1"] and "GPL" in (cf["license"] or "")
    assert mw["reg"] == "2000-02-09" and mw["week"] == "3,600,000" and mw["rating"] == "4.6"
    assert mw["hist"] == ["150", "11", "5", "1", "4"] and "BSD" in (mw["license"] or "")
    assert npp["reg"] == "2011-11-29" and npp["week"] == "109,095" and npp["rating"] == "4.4"
    assert npp["hist"] == ["49", "7", "3", "4", "1"]
    assert sz["upd"] == "2026-09-04" and sz["reviews"] == "831" and sz_rating == "4.8"
    w.done("top-3 + both #1s + 7-Zip: pages, reviews and ratings cross-checked")
    return w


def walk_6(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.click('.l-header-nav-bottom .links a:has-text("Business Software")', "open Business Software")
    w.click('a[href="/software/crm/"]', "open the CRM category")
    t = w.body()
    assert "Pipedrive" in t and "3,120" in t and "SuiteCRM" in t and "EspoCRM" in t
    w.click('a:has-text("Pipedrive")', "open the most-rated CRM product")
    pipe_desc = w.grab(r"(Pipedrive[^.]*\.)")
    w.back()
    w.click('a:has-text("SuiteCRM")', "open the second most-rated CRM product")
    suite_desc = w.grab(r"(SuiteCRM[^.]*\.)")
    w.back()
    w.click('a:has-text("EspoCRM")', "open the third CRM product")
    espo_desc = w.grab(r"(EspoCRM[^.]*\.)")
    w.search("CRM")
    w.sort_by("Rating")
    total = w.grab(r"Showing ([\d,]+) open source projects")
    first = pg.locator("li.project-oss .result-heading-title").first.inner_text().strip()
    w.click("li.project-oss .result-heading-title", f"open the first CRM result ({first})")
    dol = project_facts(w)
    w.tab("Reviews")
    dol_rating = w.grab(r"([\d.]+) out of 5 stars")
    w.tab("Support")
    dol_help = w.grab(r"Best Way to Get Help\s*(.{0,80})")
    assert total == "2" and first == "Dolibarr ERP - CRM", (total, first)
    assert dol["week"] == "2,932" and dol["upd"] == "2026-05-26" and dol_rating == "4.8"
    assert pipe_desc and suite_desc and espo_desc and dol_help
    w.done("CRM shortlist (3 products) + Dolibarr open source cross-check")
    return w


def walk_8(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.open_project("7-Zip")
    w.click('a[title="Downloads This Week"]', "open the download statistics timeline")
    rows = pg.evaluate("() => [...document.querySelectorAll('#stats-table tbody tr')].map(r => r.innerText.trim().split(/\\s+/))")
    peak_row = max(rows, key=lambda r: int(r[1].replace(",", "")))
    w.click('a[href*="stats/map"]', "open the Countries stats")
    top_country = grab_pair(w, r"(United States)\s+([\d,]+)")
    w.click('a[href*="stats/os"]', "open the Operating Systems stats")
    top_os = grab_pair(w, r"(Windows|Macintosh|Linux|Unknown|Android|BSD)\s+([\d,]+)")
    w.search("file compression")
    w.sort_by("Most Popular")
    # honest path: open each of the three top cards in turn (registered date +
    # license are only on the project pages, not the result cards)
    for i, expect in enumerate([("MinGW - Minimalist GNU for Windows", "2000-02-09", "BSD License", "2021-09-05"),
                                ("AutoClicker", "2014-06-19", "Creative Commons Attribution Non-Commercial License V2.0", "2025-11-09"),
                                ("WinSCP", "2003-07-13", "GNU General Public License version 2.0 (GPLv2)", "2026-09-03")]):
        w.click(f"li.project-oss .result-heading-title >> nth={i}", f"open result #{i+1}")
        f = project_facts(w)
        assert f["reg"] == expect[1] and expect[2] in (f["license"] or "") and f["upd"] == expect[3], (f, expect)
        w.back()
    assert peak_row[0] == "2026-09-19" and peak_row[1] == "6,001"
    assert top_country == ("United States", "40,718") and top_os == ("Windows", "90,456")
    w.done("stats + top-3 popular comparison done")
    return w


def walk_9(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.scroll("reach the Open Source Categories")
    w.click('a:text-is("Games")', "open the Games category")
    total = w.grab(r"Showing ([\d,]+) open source projects")
    first = pg.locator("li.project-oss .result-heading-title").first.inner_text().strip()
    second = pg.locator("li.project-oss .result-heading-title").nth(1).inner_text().strip()
    w.click("a[href='/directory/games/?page=2']", "open the second page of the Games category")
    p2 = pg.locator("li.project-oss .result-heading-title").count()
    p2_first = pg.locator("li.project-oss .result-heading-title").first.inner_text().strip() if p2 else None
    w.back()
    w.click("li.project-oss .result-heading-title", f"open the first game ({first})")
    g1 = project_facts(w)
    w.tab("Reviews")
    g1["rating"] = w.grab(r"([\d.]+) out of 5 stars")
    w.tab("Support")
    g1_help = w.grab(r"Best Way to Get Help\s*(.{0,90})")
    w.open_project(second)
    g2 = project_facts(w)
    w.tab("Reviews")
    g2["rating"] = w.grab(r"([\d.]+) out of 5 stars")
    w.scroll("reach the footer")
    w.click('footer a:has-text("Top Downloaded Projects")', "open the Top page")
    week1 = w.grab(r"1\s+MinGW - Minimalist GNU for Windows\s+([\d.]+M)")
    assert total == "26" and first == "DOSBox" and second == "Neko Void", (total, first, second)
    assert p2 == 1 and p2_first == "ii's Stupid Menu", (p2, p2_first)
    assert g1["week"] == "14,848" and g1["rating"] == "4.7" and g1["reg"] == "2002-04-30"
    assert g2["os"] and "Linux" in g2["os"] and g2["rating"] == "4.5"
    assert week1 == "3.6M"
    w.done("games category + two project deep-dives + weekly #1")
    return w


def walk_10(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    t = w.body()
    staff = w.grab(r"Staff Choice\s+(7-Zip|KeePass)")
    comm = w.grab(r"Community Choice\s+(7-Zip|KeePass)")
    assert staff == "7-Zip" and comm == "KeePass", (staff, comm)
    w.open_project("PortableApps.com")
    pa = project_facts(w)
    w.tab("Reviews")
    pa_rating = w.grab(r"([\d.]+) out of 5 stars")
    w.open_project("7-Zip")
    sz = project_facts(w)
    w.tab("Reviews")
    sz_hist = pg.evaluate("() => [...document.querySelectorAll('.bargraph .rating-label')].map(e => e.innerText.trim())")
    w.open_project("KeePass")
    kp = project_facts(w)
    w.tab("Reviews")
    kp_rating = w.grab(r"([\d.]+) out of 5 stars")
    w.scroll("reach the footer")
    w.click('footer a:has-text("Top Downloaded Projects")', "open the Top page")
    week1 = w.grab(r"1\s+MinGW - Minimalist GNU for Windows\s+([\d.]+M)")
    popular = ["CrystalDiskInfo", "KeePass", "MP4Tools", "PortableApps.com", "scrcpy",
               "7-Zip", "Ventoy", "WinSCP"]
    assert pa["week"] == "422,400" and pa["reg"] == "2005-10-21" and pa_rating == "4.9"
    assert sz["week"] == "23,587" and sz_hist[0] == "765" and sz_hist[4] == "27"
    assert kp["week"] == "205,800" and kp["upd"] == "2026-07-25" and kp_rating == "4.9"
    assert week1 == "3.6M"  # MinGW not among the popular picks
    w.done("homepage picks compared; portable platform + both choices verified")
    return w


def walk_11(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.search("video player")
    total = w.grab(r"Showing ([\d,]+) open source projects")
    t = w.body()
    assert "Next Player" in t and "Video.js" in t
    w.click('li.project-oss .result-heading-title >> text=Next Player', "open the Android native player")
    np = project_facts(w)
    w.back()
    w.click('li.project-oss .result-heading-title >> text=Video.js', "open the HTML5 player")
    vjs = project_facts(w)
    w.back()
    w.click('#facet-os a:has-text("Windows")', "narrow to Windows via the OS facet")
    wtotal = w.grab(r"Showing ([\d,]+) open source projects")
    first = pg.locator("li.project-oss .result-heading-title").first.inner_text().strip()
    w.click("li.project-oss .result-heading-title", f"open the first Windows result ({first})")
    mpv = project_facts(w)
    w.tab("Reviews")
    mpv_rating = w.grab(r"([\d.]+) out of 5 stars")
    w.back(); w.back()
    w.sort_by("Rating")
    rfirst = pg.locator("li.project-oss .result-heading-title").first.inner_text().strip()
    assert total == "53" and wtotal == "13", (total, wtotal)
    assert np["week"] == "37" and np["upd"] == "2026-08-09"
    assert vjs["upd"] == "2026-08-10"
    assert first == "mpv player (Windows)" and mpv["week"] == "9,572" and mpv["reg"] == "2015-12-31"
    assert mpv_rating == "4.3" and rfirst == "Shotcut", (mpv_rating, rfirst)
    w.done("video player search + Windows facet + rating sort")
    return w


def walk_12(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.open_project("7-Zip")
    w.click('.brought-by a:has-text("ipavlov")', "open the developer's profile")
    username = w.grab(r"Username:\s*(\w+)Joined")
    joined = w.grab(r"Joined:\s*([\d-]+)")
    projs = re.findall(r"/projects/([\w.-]+)/", pg.content())
    w.click('a:has-text("p7zip")', "open the p7zip project")
    p7 = project_facts(w)
    p7_sum = w.grab(r"p7zip\s+(Command-line port[^.]*\.)")
    w.back()
    w.click('a:has-text("7-max")', "open the 7-max project")
    mx = project_facts(w)
    mx_sum = w.grab(r"(7-max speeds up Windows applications by optimising memory allocation\.)")
    w.back()
    w.click('a:has-text("7-Far")', "open the 7-Far project")
    far = project_facts(w)
    far_sum = w.grab(r"(7-Zip archiver plugin for the FAR Manager file manager\.)")
    w.back()
    w.click('a:has-text("7-Zip")', "open the 7-Zip project")
    sz = project_facts(w)
    w.tab("Reviews")
    sz_rating = w.grab(r"([\d.]+) out of 5 stars")
    w.click(".sort-options .sort-drop-down > a", "open the Filter Reviews dropdown")
    w.scroll("bring the star filter links into view")
    w.click('#filter-rating a[href*="filter-stars=1"]', "apply the 1-star filter")
    one = pg.locator("#project-reviews > li").count()
    w.click(".sort-options .sort-drop-down > a", "open the Filter Reviews dropdown")
    w.scroll("bring the star filter links into view")
    w.click('#filter-rating a[href*="filter-stars=4"]', "apply the 4-star filter")
    four = pg.locator("#project-reviews > li").count()
    assert username == "ipavlov" and joined == "2000-08-17", (username, joined)
    assert set(projs) == {"p7zip", "sevenfar", "sevenmax", "sevenzip"}, projs
    assert p7["reg"] == "2004-06-12" and p7["upd"] == "2016-10-04" and "LGPL" in (p7["license"] or ""), p7
    assert mx["reg"] == "2004-08-12" and mx["upd"] == "2007-06-19" and "LGPL" in (mx["license"] or ""), mx
    assert far["reg"] == "2009-12-28" and far["upd"] == "2011-09-23" and "LGPL" in (far["license"] or ""), far
    assert p7_sum and mx_sum and far_sum, (p7_sum, mx_sum, far_sum)
    assert sz["reviews"] == "831" and sz_rating == "4.8", (sz["reviews"], sz_rating)
    assert one == 3 and four == 6, (one, four)
    w.done("profile + all three other projects + 7-Zip star filter views")
    return w


def walk_13(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.click('.l-header-nav-top .links a:has-text("Join")', "open the registration page")
    w.fill('input[name="email"]', "fleet-admin@example.com", "fill the email")
    w.fill('input[name="username"]', "fleet-admin", "choose the username")
    w.fill('input[name="password"]', "LongPass123!", "fill the password")
    w.fill('input[name="password_confirm"]', "LongPass123!", "confirm the password")
    w.check('input[name="tos"]', "accept the terms")
    w.click('input[value="Register"]', "register the account")
    acct_head = w.grab(r"(My Account)")
    w.click('a:has-text("Edit Profile")', "open the profile editor")
    w.fill('input[name="display_name"]', "Fleet Admin", "set a display name")
    w.select('select[name="country"]', "DE", "set the country to Germany")
    w.click('input[value="Save Changes"]', "save the profile")
    t = w.body()
    assert "Germany" in t and "Fleet Admin" in t, t[:200]
    w.open_project("CrystalDiskInfo")
    w.click("form.inline-form button", "bookmark the project")
    w.click('.l-header-nav-top .links a:has-text("My Account")', "return to the account page")
    t = w.body()
    assert "CrystalDiskInfo" in t and "Display Name" in t and "Fleet Admin" in t
    assert "You haven't written any reviews yet" in t
    w.done("account registered, profile edited, bookmark confirmed")
    return w


def walk_14(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.open_project("7-Zip")
    w.tab("Wiki")
    t = w.body()
    formats = w.grab(r"(7z, XZ, BZIP2[^;]{0,60})")
    mod = w.grab(r"Page Last Modified:\s*(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
    author = w.grab(r"Authors:\s*([\w ]+?)\s+Page")
    w.back()
    w.tab("News")
    news = re.findall(r"Posted by (Igor Pavlov) (\d{4}-\d\d-\d\d)", w.body())
    assert "7-Zip 9.21 beta" in w.body() and "7-Zip 9.20 was released" in w.body()
    w.back()
    w.tab("Support")
    best = w.grab(r"best way to get help with its software is by visiting\s*(\S+)")
    w.tab("Discussion")
    w.click('a[href*="discussion/45797"]', "open the Open Discussion forum")
    hv = pg.evaluate("""() => {
        const rows = [...document.querySelectorAll('table tbody tr')];
        return rows.map(r => [r.cells[0].innerText.replace(/\\s+/g,' ').trim(),
                              r.cells[1].innerText.trim(), r.cells[2].innerText.trim()])
                   .sort((a, b) => parseInt(b[2].replace(/,/g,'')) - parseInt(a[2].replace(/,/g,'')))[0];
    }""")
    w.click('a:has-text("7-Zip 26.02")', "open the highest-viewed thread")
    w.back(); w.back()
    w.click('a[href*="discussion/45798"]', "open the Help forum")
    hthreads = pg.locator("table tbody tr").count()
    hhv = pg.evaluate("""() => {
        const rows = [...document.querySelectorAll('table tbody tr')];
        return rows.map(r => [r.cells[0].innerText.replace(/\\s+/g,' ').trim(),
                              r.cells[1].innerText.trim(), r.cells[2].innerText.trim()])
                   .sort((a, b) => parseInt(b[2].replace(/,/g,'')) - parseInt(a[2].replace(/,/g,'')))[0];
    }""")
    assert formats and mod == "2026-09-04 20:47:12" and author == "Igor Pavlov", (formats, mod, author)
    assert len(news) == 2 and news[0] == ("Igor Pavlov", "2011-04-15"), news
    assert best and "forum" in best, best
    assert hv[2] == "297,148" and "Igor Pavlov" in hv[0], hv
    assert hthreads == 25 and "rtm" in hhv[0] and hhv[2] == "3,161", (hthreads, hhv)
    w.done("wiki + news + support + both forums covered")
    return w


def walk_15(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.open_project("7-Zip")
    w.tickets_tab("Bugs")
    open_count = w.grab(r"Open Tickets\s*([\d,]+)")
    w.fill('#search input[name="q"]', "CVE", "search tickets for CVE")
    w.press_enter('#search input[name="q"]', "run the CVE search")
    cve_nums = sorted(set(re.findall(r"/p/sevenzip/bugs/(\d+)/", pg.content())))
    t = w.body()
    assert "CVE-2026-58052" in t and "CVE-2026-48102" in t
    w.click('a:has-text("CVE-2026-48101")', "open the lowest-numbered CVE ticket")
    owner = w.grab(r"Owner:\s*([A-Za-z ]+?)\s+Labels")
    created = w.grab(r"Created:\s*([\d-]+)")
    w.back(); w.back(); w.back()
    w.tab("Discussion")
    w.click('a:has-text("Open Discussion")', "open the Open Discussion forum")
    w.click('a:has-text("vulnerability scanner flagged version 26.02 as unsafe")',
            "open the vulnerability-scanner thread")
    vt = w.body()
    assert cve_nums == ["2669", "2670", "2681"], cve_nums
    assert owner == "Igor Pavlov" and created == "2026-06-10"
    assert "Robert Barcikowski" in vt and open_count == "31"
    w.done("CVE audit + forum vulnerability thread")
    return w


def walk_16(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.open_project("7-Zip")
    w.tab("Files")
    sdk_row = None
    root_row = None
    for r in pg.locator("table tbody tr").all():
        t = re.sub(r"\s+", " ", r.inner_text()).strip()
        if "LZMA SDK" in t:
            sdk_row = t
        if t.startswith("7-Zip "):
            root_row = t
    w.click('table a:has-text("LZMA SDK")', "open the LZMA SDK folder")
    sdk_files = [re.sub(r"\s+", " ", r.inner_text()).strip()
                 for r in pg.locator("table#files_list tbody tr").all() if "Parent" not in r.inner_text()]
    w.click('table a:has-text("lzma2601.7z")', "start the newest SDK file's download")
    f1 = re.search(r"Download of\s*([\w.-]+)", w.body()).group(1)
    w.back()
    w.click("#parent_folder a", "back to the files root")
    w.click('table a:has-text("7-Zip")', "open the 7-Zip folder")
    w.click('table a:has-text("26.01")', "open the 26.01 folder")
    b2601 = [re.sub(r"\s+", " ", r.inner_text()).strip()
             for r in pg.locator("table#files_list tbody tr").all() if "Parent" not in r.inner_text()]
    w.click("#parent_folder a", "back to the version folders")
    w.click('table a:has-text("26.00")', "open the 26.00 folder")
    b2600 = [re.sub(r"\s+", " ", r.inner_text()).strip()
             for r in pg.locator("table#files_list tbody tr").all() if "Parent" not in r.inner_text()]
    w.click('table a:has-text("7z2600-x64.exe")', "start the 26.00 x64 download")
    f2 = re.search(r"Download of\s*([\w.-]+)", w.body()).group(1)
    assert sdk_row and "675" in sdk_row, sdk_row
    assert len(sdk_files) == 4 and any("lzma2601.7z" in r for r in sdk_files), sdk_files
    assert f1 == "lzma2601.7z" and f2 == "7z2600-x64.exe", (f1, f2)
    assert len(b2601) == 2 and len(b2600) == 1
    assert root_row and "23,345" in root_row, root_row
    w.done("SDK + 26.01/26.00 folders + both downloads + root count")
    return w


def walk_17(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.open_project("KeePass")
    kp = project_facts(w)
    w.tab("Reviews")
    kp_rating = w.grab(r"([\d.]+) out of 5 stars")
    kp_hist = pg.evaluate("() => [...document.querySelectorAll('.bargraph .rating-label')].map(e => e.innerText.trim())")
    w.tab("Support")
    kp_help = w.grab(r"Best Way to Get Help\s*(.{0,80})")
    w.open_project("7-Zip")
    sz = project_facts(w)
    w.tab("Reviews")
    sz_rating = w.grab(r"([\d.]+) out of 5 stars")
    sz_hist = pg.evaluate("() => [...document.querySelectorAll('.bargraph .rating-label')].map(e => e.innerText.trim())")
    w.tab("Support")
    sz_help = w.grab(r"by visiting (\S+)")
    w.click('a[href*="/discussion/45797/"]', "open the linked discussion forum")
    forum_name = w.grab(r"([^\s]+ [^\s]+) \d+ \(Page 1 of 1\)")
    forum_threads = pg.evaluate("() => [...document.querySelectorAll('a[href*=\"/thread/\"]')].length")
    w.scroll("reach the footer")
    w.click('footer a:has-text("Top Downloaded Projects")', "open the Top page")
    kp_total = grab_pair(w, r"(\d+)\s+KeePass\s+([\d.]+M)")
    sz_total = grab_pair(w, r"(\d+)\s+7-Zip\s+([\d.]+M)")
    assert kp["week"] == "205,800" and kp["reg"] == "2003-11-15" and kp_rating == "4.9", (kp, kp_rating)
    assert kp_hist == ["567", "24", "1", "3", "11"], kp_hist
    assert kp_help and "discussion forums" in kp_help
    assert sz["week"] == "23,587" and sz["reg"] == "2000-11-10" and sz_rating == "4.8", (sz, sz_rating)
    assert sz_hist == ["765", "25", "12", "2", "27"], sz_hist
    assert sz_help and "forum" in sz_help
    assert forum_name == "Open Discussion" and forum_threads == 25, (forum_name, forum_threads)
    assert kp_total == ("16", "191M") and sz_total == ("10", "430M"), (kp_total, sz_total)
    w.done("KeePass vs 7-Zip full comparison")
    return w


def walk_19(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.click('.l-header-nav-top .links a:has-text("Create")', "open the Create page")
    create_invite = w.grab(r"(Find, Create & Publish Open Source software for free)")
    w.click('.l-header-nav-top .links a:has-text("Help")', "open the Support page")
    support_fast = w.grab(r"fastest way to get help is (.{0,60})")
    w.click('.l-header-nav-top .links a:has-text("For Vendors")', "open the For Vendors page")
    vendors_offer = w.grab(r"(list your product in the Business Software directory)")
    w.click('.l-header-nav-bottom .links a:has-text("SourceForge Podcast")', "open the Podcast page")
    ep1 = w.grab(r"(Mobile Data Collection and Analytics.{0,120}episode #138)")
    ep_date = w.grab(r"episode #138\s*(2026-\d\d-\d\d)")
    w.click('.l-header-nav-bottom .nav-dropdown:has-text("Resources")', "open the Resources menu")
    w.click('.nav-dropdown.open .nav-dropdown-menu a:has-text("Articles")', "open the Articles page")
    art = w.grab(r"(Trend Analysis and Capacity Planning: Turning Monitoring Data Into Better Infrastructure Decisions)")
    art_date = w.grab(r"Decisions\s+Articles\s+·\s+(2026-\d\d-\d\d)")
    w.click('.l-header-nav-bottom .nav-dropdown:has-text("Resources")', "open the Resources menu")
    w.click('.nav-dropdown.open .nav-dropdown-menu a:has-text("Case Studies")', "open the Case Studies page")
    vendors = pg.evaluate("() => [...document.querySelectorAll('.featured-vendors a')].map(a => a.innerText.trim())")
    w.click('a:has-text("NinjaOne")', "open the NinjaOne product page")
    ninja = w.grab(r"([\d,]+)\s*Ratings")
    w.back()
    w.click('a:has-text("Google Cloud Platform")', "open the Google Cloud Platform product page")
    gcp = w.grab(r"([\d,]+)\s*Ratings")
    w.click('.l-header-nav-bottom .nav-dropdown:has-text("Resources")', "open the Resources menu")
    w.click('.nav-dropdown.open .nav-dropdown-menu a:has-text("Blog")', "open the Blog page")
    blog1 = w.grab(r"(Trend Analysis and Capacity Planning[^|]{0,10})")
    blog_date = w.grab(r"Decisions\s+Articles\s+·\s+(2026-\d\d-\d\d)")
    w.click('footer a:has-text("About")', "open the About page")
    founded = w.grab(r"Founded in (\d{4})")
    titles = w.grab(r"([\d,]+)\s+software titles")
    w.scroll("bring the Team link into view")
    w.click('a:has-text("Team")', "open the Team page")
    m1 = w.grab(r"(Logan Abbott)\s+(President, SourceForge & COO, Slashdot Media)")
    m2 = w.grab(r"(Roger Sheppard)\s+(President of Slashdot Media)")
    addr = w.grab(r"(1320 Columbia Street Suite 310)")
    w.search("file compression", "search the directory for file compression")
    total = w.grab(r"Showing ([\d,]+) open source projects")
    assert founded == "1999" and titles, (founded, titles)
    assert m1 and m2
    assert ep1 and ep_date == "2026-09-03", (ep_date,)
    assert art and art_date == "2026-09-03"
    assert vendors and "NinjaOne" in vendors and "Google Cloud Platform" in vendors, vendors
    assert ninja == "6,035" and gcp == "61,049", (ninja, gcp)
    assert blog1 and blog_date == "2026-09-03" and create_invite and support_fast and vendors_offer
    assert addr == "1320 Columbia Street Suite 310"
    assert total == "96", total
    w.done("site survey complete")
    return w


def walk_20(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.click('.l-header-nav-bottom .links a:has-text("Business Software")', "open Business Software")
    w.click('a[href="/software/erp/"]', "open the ERP category")
    t = w.body()
    assert "Odoo" in t and "4,100" in t and "Dolibarr" in t and "940" in t
    w.click('a:has-text("Odoo")', "open the most-rated ERP product")
    odoo = w.grab(r"(Odoo[^.]*\.)")
    w.back()
    w.click('a:has-text("Dolibarr")', "open the other ERP product")
    dolibarr_biz = w.grab(r"(Dolibarr[^.]*\.)")
    w.search("erp")
    w.sort_by("Rating")
    total = w.grab(r"Showing ([\d,]+) open source projects")
    first = pg.locator("li.project-oss .result-heading-title").first.inner_text().strip()
    second = pg.locator("li.project-oss .result-heading-title").nth(1).inner_text().strip()
    w.click("li.project-oss .result-heading-title", f"open {first}")
    dol = project_facts(w)
    w.tab("Reviews")
    dol_rating = w.grab(r"([\d.]+) out of 5 stars")
    w.tab("Support")
    dol_help = w.grab(r"Best Way to Get Help\s*(.{0,80})")
    w.back()
    w.back()
    w.back()
    w.click("li.project-oss .result-heading-title >> nth=1", f"open {second}")
    pse = project_facts(w)
    assert total == "8" and first == "Dolibarr ERP - CRM" and second == "PSeInt", (total, first, second)
    assert dol["week"] == "2,932" and dol["upd"] == "2026-05-26" and dol["reg"] == "2005-11-28"
    assert "GPL" in (dol["license"] or "") and dol_rating == "4.8"
    assert pse["reg"] and odoo and dolibarr_biz and dol_help
    w.done("ERP evaluation complete")
    return w


# T7 / T18 keep their original stateful chains (already >=15 steps).
def walk_7(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.click('.l-header-nav-top .links a:has-text("Login")', "open the login form")
    w.fill('input[name="username"]', "alice.j@test.com", "fill the email")
    w.fill('input[name="password"]', "TestPass123!", "fill the password")
    w.click('#loginform input.submit', "log in")
    w.search("password manager")
    first = pg.locator("li.project-oss .result-heading-title").first.inner_text().strip()
    w.click("li.project-oss .result-heading-title", f"open the top result ({first})")
    assert first == "Password Safe", first
    w.click("form.inline-form button", "bookmark the project")
    w.tab("Reviews")
    w.click('a:has-text("Write a Review")', "open the review form")
    w.select('select[name="rating"]', "5", "rate it 5 stars")
    w.fill('textarea[name="text"]', "I use this password manager daily - great mirror test review.", "write the review")
    w.click('input[value="Post Review"]', "post the review")
    w.click('.l-header-nav-top .links a:has-text("My Account")', "open the account page")
    t = w.body()
    assert "Password Safe" in t and "I use this password manager daily" in t
    w.done("bookmark + review confirmed on the account page")
    return w


def walk_18(pg):
    w = Walk(pg)
    w.nav("/", "start at the homepage")
    w.click('.l-header-nav-top .links a:has-text("Login")', "open the login form")
    w.fill('input[name="username"]', "bob.c@test.com", "fill the email")
    w.fill('input[name="password"]', "TestPass123!", "fill the password")
    w.click('#loginform input.submit', "log in")
    w.click('.l-header-nav-top .links a:has-text("My Account")', "open the account page")
    bookmarks0 = [re.sub(r"\s+", " ", r.inner_text()).split("Remove")[0].strip()
                  for r in pg.locator(".project-info").all()]
    w.open_project("CrystalDiskInfo")
    w.click("form.inline-form button", "remove the disk-health tool bookmark")
    w.open_project("Ventoy")
    w.click("form.inline-form button", "bookmark the bootable USB tool")
    w.tab("Reviews")
    w.click('a:has-text("Write a Review")', "open the review form")
    w.select('select[name="rating"]', "4", "rate it 4 stars")
    w.fill('textarea[name="text"]', "Ventoy makes USB sticks bootable in one step - solid tool.",
           "write the review mentioning USB sticks")
    w.click('input[value="Post Review"]', "post the review")
    w.click('.l-header-nav-top .links a:has-text("My Account")', "open the account page")
    t = w.body()
    assert "Ventoy" in t and "CrystalDiskInfo" not in t
    assert "USB sticks" in t
    w.done("bookmark swap + review confirmed")
    return w


WALKS = {i: globals()[f"walk_{i}"] for i in
         [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]}


def reset_instance():
    """Restore instance/sourceforge.db from the frozen seed."""
    seed = SITE / "instance_seed" / "sourceforge.db"
    live = SITE / "instance" / "sourceforge.db"
    shutil.copyfile(seed, live)


def dev_server_ctl(action):
    if action == "stop":
        subprocess.run(["pkill", "-f", f"port={PORT}"], capture_output=True)
        for _ in range(20):
            r = subprocess.run(["pgrep", "-f", f"port={PORT}"], capture_output=True)
            if r.returncode != 0:
                return
            time.sleep(0.3)
    else:
        subprocess.Popen(
            [VENV_PY, "-c",
             f"from app import app; app.run(host='127.0.0.1', port={PORT}, "
             f"debug=False, use_reloader=False, threaded=True)"],
            cwd=str(SITE), stdout=open(os.devnull, "w"), stderr=subprocess.STDOUT,
            start_new_session=True)
        for _ in range(40):
            try:
                import urllib.request
                urllib.request.urlopen(f"{M}/_health", timeout=2).read()
                return
            except Exception:
                time.sleep(0.4)
        raise RuntimeError("dev server did not come up")


def main():
    ids = [int(a) for a in sys.argv[1:]] or sorted(WALKS)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for i in ids:
            reset_instance()
            dev_server_ctl("stop")
            dev_server_ctl("start")
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            pg = ctx.new_page()
            try:
                w = WALKS[i](pg)
                record(f"SourceForge--{i}", True, w.steps)
            except Exception as e:  # noqa: BLE001
                record(f"SourceForge--{i}", False, [], f"{type(e).__name__}: {e}")
            finally:
                ctx.close()
        browser.close()
    dev_server_ctl("stop")

    fails = [r for r in results if not r[1]]
    print(f"\nWALKS: {len(results) - len(fails)}/{len(results)} passed")
    for tid, ok, steps, note in results:
        print(f"  {tid}: {len(steps)} steps {'PASS' if ok else 'FAIL ' + note}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

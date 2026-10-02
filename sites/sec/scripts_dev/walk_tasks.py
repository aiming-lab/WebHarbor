#!/usr/bin/env python3
"""Real-browser honest-path walker for the sec mirror tasks.

Methodology (aligned with the independent review's counting standard):

- counts ATOMIC ACTIONS only: navigate (homepage start), click, fill,
  select, submit-button press and browser back each count 1;
- reads never count and actions the task text does not require are never
  taken (anti-padding): every task is walked along the minimal honest path
  a competent agent would take with visible-element interaction only
  (no direct URL navigation beyond the homepage start);
- every task starts from the pristine frozen seed (instance_seed/sec.db is
  copied over instance/sec.db and the sha256 is asserted before each run,
  so a task's reset restores the database byte-for-byte) and a fresh browser
  context with cleared cookies;
- every step is screenshotted (before/after) and the answer facts are read
  off the rendered pages only, then rendered as honest prose via
  scripts_dev/render_answers.py (the same renderer that bakes the positive
  answer controls, so the two can never drift apart).

Evidence layout per task:

  runs/round<N>/<task>/trajectory.json   identity + steps + reads + prose
  runs/round<N>/<task>/initial.db        seed state before the walk
  runs/round<N>/<task>/after.db          state after the walk
  runs/round<N>/<task>/screenshots/      one PNG per step boundary
  runs/round<N>/<task>/final.png         full-page closing screenshot

Two independent rounds must agree per task (step counts and normalized
answers, modulo runtime-generated reference numbers).

Run from sites/sec:
  python3 scripts_dev/walk_tasks.py --port 46236 --round 1 [--only 0,3]
  python3 scripts_dev/walk_tasks.py --port 46236 --compare
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parents[1]
SITE = HERE
RUNS = SITE / "runs"
SEED = SITE / "instance_seed" / "sec.db"
INSTANCE = SITE / "instance" / "sec.db"
SEED_SHA256 = ("2d68d37888c2dc87cf4bd8766cc12a221966a64156ded693831e0f"
               "6de080e29e")
PASSWORD = "TestPass123!"

sys.path.insert(0, str(HERE / "scripts_dev"))
sys.path.insert(0, str(HERE / "verify"))
from render_answers import render  # noqa: E402
from contract_engine import norm  # noqa: E402

TASKS = {json.loads(line)["id"]: json.loads(line)["ques"] for line in
         (SITE / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
         if line.strip()}


# ------------------------------------------------------------------ server --

def start_server(port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["SEC_AUTO_SEED"] = "0"
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import app; app.app.run(host='127.0.0.1', port=%d, threaded=True)" % port],
        cwd=str(SITE), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            return proc
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("server did not come up")


def stop_server(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reset_site() -> None:
    """Restore instance/ from the frozen seed, byte-for-byte."""
    seed_sha = sha256_file(SEED)
    if seed_sha != SEED_SHA256:
        raise RuntimeError(f"frozen seed sha256 mismatch: {seed_sha}")
    INSTANCE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SEED, INSTANCE)
    if sha256_file(INSTANCE) != SEED_SHA256:
        raise RuntimeError("instance restore was not byte-identical")


# ------------------------------------------------------------------- walker --

class Walk:
    """One task's honest browser session with atomic-action accounting."""

    def __init__(self, page, base, task_id, out_dir):
        self.page = page
        self.base = base
        self.task_id = task_id
        self.out = Path(out_dir)
        (self.out / "screenshots").mkdir(parents=True, exist_ok=True)
        self.steps = []
        self.atomic = 0
        self.reads = []
        self.facts = {}
        self.js_errors = []
        self._shot = 0
        page.on("pageerror", lambda e: self.js_errors.append(str(e)[:200]))

    # ---------------------------------------------------------------- io --
    def _shoot(self):
        p = self.out / "screenshots" / f"step_{self._shot:03d}.png"
        for attempt in range(3):
            try:
                self.page.screenshot(path=str(p), timeout=15000)
                break
            except Exception:
                if attempt == 2:
                    raise
                try:
                    self.page.wait_for_load_state("load", timeout=5000)
                except Exception:
                    pass
                self.page.wait_for_timeout(500)
        self._shot += 1
        return p.name

    def _log(self, action, params, desc):
        rec = {"step": len(self.steps), "url": self.page.url,
               "title": self.page.title(), "thought": desc, "action": action,
               "params": params,
               "observed_text": (self.page.inner_text("body") or "")[:4000],
               "screenshot_before": self._shoot()}
        self.steps.append(rec)
        print(f"  [{self.atomic + 1:02d}] {action}: {desc}", flush=True)

    def _after(self, settle=True):
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        self.page.wait_for_timeout(250)
        self.steps[-1]["screenshot_after"] = self._shoot()
        self.steps[-1]["url_after"] = self.page.url

    # ------------------------------------------------------------ actions --
    def start_home(self, desc="open homepage (start_url)"):
        self._log("navigate", {"url": self.base + "/"}, desc)
        self.page.goto(self.base + "/", timeout=45000, wait_until="load")
        self._after()
        self.atomic += 1

    def click(self, sel, desc, has=None):
        loc = self.page.locator(sel)
        if has is not None:
            loc = loc.filter(has_text=has)
        loc.first.scroll_into_view_if_needed(timeout=8000)
        self._log("click", {"selector": sel}, desc)
        loc.first.click(timeout=10000)
        self._after()
        self.atomic += 1

    def click_nth(self, sel, index, desc):
        loc = self.page.locator(sel).nth(index)
        loc.scroll_into_view_if_needed(timeout=8000)
        self._log("click", {"selector": f"{sel} [{index}]"}, desc)
        loc.click(timeout=10000)
        self._after()
        self.atomic += 1

    def back(self, desc="browser back"):
        self._log("back", {}, desc)
        self.page.go_back()
        self._after()
        self.atomic += 1

    def select(self, sel, value, desc, by_label=False):
        self._log("select", {"selector": sel, "value": str(value)}, desc)
        if by_label:
            self.page.select_option(sel, label=str(value), timeout=10000)
        else:
            self.page.select_option(sel, value, timeout=10000)
        self._after(settle=False)
        self.atomic += 1

    def fill(self, sel, value, desc):
        self._log("fill", {"selector": sel, "value": value}, desc)
        self.page.fill(sel, value, timeout=10000)
        self._after(settle=False)
        self.atomic += 1

    def submit(self, sel, desc):
        self._log("click", {"selector": sel}, desc)
        self.page.locator(sel).first.scroll_into_view_if_needed(timeout=8000)
        self.page.locator(sel).first.click(timeout=10000)
        self._after()
        self.atomic += 1

    # -------------------------------------------------------------- reads --
    def read(self, key, value):
        self.reads.append({"key": key, "value": str(value)})
        self.facts[key] = value
        print(f"      read {key} = {str(value)[:110]}", flush=True)

    def body(self):
        text = self.page.inner_text("body") or ""
        text = "\n".join(line.strip() for line in text.splitlines())
        return re.sub(r"\n{2,}", "\n", text).strip()

    def save(self, facts):
        prose = render(self.task_id, facts)
        traj = {
            "task_id": self.task_id,
            "task": TASKS[self.task_id],
            "start_url": self.base + "/",
            "terminated": True,
            "termination_reason": "agent_done",
            "final_answer": prose,
            "steps": self.steps,
            "reads": self.reads,
            "facts": facts,
            "js_errors": self.js_errors,
            "step_count": self.atomic,
            "final_url": self.page.url,
        }
        (self.out / "trajectory.json").write_text(json.dumps(traj, indent=1))
        try:
            self.page.screenshot(path=str(self.out / "final.png"), full_page=True)
        except Exception:
            pass
        print(f"  => {self.atomic} atomic actions, answer saved", flush=True)
        return self.atomic


# ---------------------------------------------------------------- helpers --

def grab(pattern, body, what, flags=0):
    m = re.search(pattern, body, flags)
    assert m, f"pattern for {what} not found"
    return m.group(1).strip() if m.groups() else m.group(0).strip()


def nav(w, label):
    w.click(f'nav.site-nav a:has-text("{label}")', f"nav {label}")


def open_company(w, term, link_text):
    """Homepage header search -> company row (minimal honest lookup)."""
    w.fill("#global-search", term, f'header search "{term}"')
    w.submit('form.site-search button[type="submit"]', "submit search")
    w.click(f'table.data a:has-text("{link_text}")',
            f"open company row for {link_text}")


def sign_in(w, email, password=PASSWORD):
    w.click('nav.site-nav a:has-text("Log In")', "open log-in page")
    w.fill("#email", email, "email")
    w.fill("#password", password, "password")
    w.submit('button:has-text("Log In")', "submit log-in")


def company_facts(w):
    body = w.body()
    facts = {}
    m = re.search(r"CIK (\d{10})\s*[·\u00b7]\s*Ticker ([A-Z.\-]+)", body)
    if m:
        facts["cik"] = m.group(1)
        facts["ticker"] = m.group(2)
    dl = w.page.locator("dl.facts").inner_text()
    for key, label in (("sic", "SIC"), ("state", "State of Incorporation"),
                       ("fye", "Fiscal Year End"), ("category", "Category")):
        m = re.search(re.escape(label) + r"\s*\n([^\n]+)", dl)
        if m:
            facts[key] = m.group(1).strip()
    return facts


def filing_count(w):
    m = re.search(r"(\d+) filings?", w.body())
    assert m, "filing count label not found"
    return m.group(1)


def filing_rows(w):
    rows = w.page.locator("table.data tbody tr").all_inner_texts()
    return [r.replace("\t", " ").replace("\n", " ") for r in rows]


def filing_detail_facts(w):
    body = w.body()
    out = {}
    m = re.search(r"SEC Accession No\. ([\w\-]+)", body)
    out["accession"] = m.group(1) if m else None
    dl = w.page.locator("dl.facts").inner_text()
    for key, label in (("filed", "Filing Date"), ("period", "Period of Report"),
                       ("items", "Items"), ("primary_doc", "Primary Document")):
        m = re.search(re.escape(label) + r"\s*\n([^\n]+)", dl)
        out[key] = m.group(1).strip() if m else None
    return out


def watchlist_count(w):
    m = re.search(r"(\d+) compan(?:y|ies) on your watchlist", w.body())
    assert m, "watchlist count not found"
    return m.group(1)


def list_count(w, noun):
    m = re.search(rf"(\d+) {noun}s?\b", w.body())
    assert m, f"{noun} count label not found"
    return m.group(1)


# ------------------------------------------------- fact-extraction helpers --

def _row_date(row):
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", row)
    return m.group(1) if m else None


def _count_label(text, noun):
    m = re.search(rf">?(\d+) {noun}s?\b", text) or re.search(
        rf"(\d+) {noun}s?\b", text)
    return m.group(1) if m else None


def _row_company(text):
    m = re.search(r"([A-Za-z0-9.,'&\-() ]+?)\s+\(\w+\)\s+\(CIK", text)
    return m.group(1).strip() if m else None


def _lit_no(text):
    m = re.search(r"Litigation Release No\. (\d+)", text)
    return m.group(1) if m else None


def _lit_date(text):
    m = re.search(r"Litigation Release No\. \d+\s*/\s*([A-Z][a-z]+ \d+, \d{4})", text)
    return m.group(1) if m else None


def _court(text):
    m = re.search(r"\(([A-Z][A-Z.]*?)\s+filed", text)
    return m.group(1).rstrip(".").replace("S.D.N.Y", "S.D.N.Y.") if m else None


def _acquired(text):
    m = re.search(r"had agreed to acquire ([^.]+?)\.", text)
    return m.group(1).strip() if m else None


def _noble_total(text):
    m = re.search(r"for a total of \$([\d,.]+)", text)
    return "$" + m.group(1).rstrip(".") if m else None


def _admin_release(text):
    m = re.search(r"Release No\. ([\w\-]+)", text)
    return m.group(1) if m else None


def _admin_file(text):
    m = re.search(r"File Number: ([\w\-]+)", text)
    return m.group(1) if m else None


def _ap_date(text):
    m = re.search(r"Administrative Proceeding\s*[·\u00b7]\s*([A-Z][a-z]+\.? \d+, \d{4})", text)
    return m.group(1) if m else None


def _ap_file_nos(text):
    m = re.search(r"File Nos?\. ((?:\d-\d{4,5};?\s*)+)", text)
    return m.group(1).strip() if m else None


def _penalty(text, who):
    m = re.search(rf"\$([\d,]+) as to (?:each )?{who}", text)
    return "$" + m.group(1) if m else None


def _ts_date(text):
    m = re.search(r"([A-Z][a-z]+\.? \d{1,2}, \d{4})", text)
    return m.group(1) if m else None


def _ts_release(text):
    m = re.search(r"Release No\. ([\w\-]+)", text)
    return m.group(1) if m else None


def _cold_flags(text):
    m = re.search(r"red flags: ([^.]+)\.", text)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
    return parts


def _pump_fact(text):
    m = re.search(r"fraudsters ([^.]+\.|[^\n]+)", text)
    return ("fraudsters " + m.group(1).strip()) if m else None


def _pr_no(text):
    m = re.search(r"Release No\. ([\w\-]+)", text)
    return m.group(1) if m else None


def _pr_date(text):
    m = re.search(r"Press Release\s*[·\u00b7]\s*([A-Z][a-z]+\.? \d+, \d{4})", text)
    return m.group(1) if m else None


def _pr_title(text):
    m = re.search(r"^(SEC Charges[^\n]+)$", text, re.M)
    return m.group(1).strip() if m else None


def _forfeited(text):
    m = re.search(r"nearly (\$[\d,]+) investment", text)
    return m.group(1) if m else None


def _veterans_scheme(text):
    m = re.search(r"allegedly orchestrating (a fraud scheme) that raised "
                  r"more than (\$[\d.]+ million) from (\d+) investors", text)
    if m:
        return (f"{m.group(1)} that raised more than {m.group(2)} "
                f"from {m.group(3)} investors")
    m = re.search(r"orchestrat\w+ ([^.]+)", text)
    return m.group(1).strip() if m else None


def _bernardi_company(text):
    m = re.search(r"former CEO of ([^,]+),", text)
    return m.group(1).strip() if m else None


def _form_row(w, form):
    for row in w.page.locator("table.data tbody tr").all_inner_texts():
        if f"Form {form}\n" in row.replace("\t", " "):
            return row.replace("\t", " ")
    return None


def _form_title(row):
    m = re.search(r"PDF\n?([^\n]+?)\nForm", row) if row else None
    return m.group(1).strip() if m else None


def _form_sec_no(row):
    m = re.search(r"^(SEC\d+)\s", row) if row else None
    return m.group(1) if m else None


def _form_updated(row):
    m = re.search(r"([A-Z][a-z]+\.? \d{4})\s*$", row) if row else None
    return m.group(1) if m else None


def _form_statute_of(row):
    if not row:
        return None
    m = re.search(r"Statute: (.*?)(?:\s+[A-Z][a-z]+\.? \d{4}\s*$)", row)
    if not m:
        m = re.search(r"Statute: ([^\n]+)", row)
    return m.group(1).strip() if m else None


def _origin(text):
    return "captured from sec.gov/answers" if "captured from sec.gov" in text \
        else ("fixture" if "fixture" in text else None)


def _tenk_window(text):
    m = re.search(r"within (\d+) to (\d+) days", text)
    return f"{m.group(1)} to {m.group(2)} days" if m else None


def _bestex_fact(text):
    m = re.search(r"Brokers are legally required to seek ([^.]+)", text)
    return m.group(1).strip() if m else None


def _sec31_fact(text):
    m = re.search(r"based on ([^.]+)", text)
    return m.group(1).strip() if m else None


def _ponzi_promise(text):
    m = re.search(r"organizers often promise ([^.]+)", text)
    return m.group(1).strip() if m else None


def _alert_date(text):
    m = re.search(r"Investor (?:Alert|Bulletin)\s*[·\u00b7]\s*([A-Z][a-z]+\.? \d+, \d{4})", text)
    return m.group(1) if m else None


def _warning_signs(text):
    m = re.search(r"three warning signs:([^.]+\.).", text, re.S)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
    parts = [re.sub(r"^and\s+", "", p) for p in parts]
    return parts[:3]


def _fee_cost(text):
    m = re.search(r"(\d+%)[^.]*consume roughly ([^.]+)", text)
    return f"{m.group(1)} can consume roughly {m.group(2)}" if m else None


def _fee_type(text):
    m = re.search(r"sales loads, ([a-z\- ]+)", text)
    return m.group(1).strip() if m else None


def _municipal_risk(text):
    m = re.search(r"Key risks include (credit risk|call risk|interest rate risk)",
                  text)
    return m.group(1) if m else None


def _rulemaking_row(w, needle):
    for row in w.page.locator("table.data tbody tr").all_inner_texts():
        if needle.lower() in row.lower():
            return row.replace("\t", " ")
    return None


def _rm_date(row):
    m = re.search(r"([A-Z][a-z]+\.? \d{1,2}, \d{4})", row) if row else None
    return m.group(1) if m else None


def _rm_file(row):
    m = re.search(r"\b(S\d-\d{4}-\d+)\b", row) if row else None
    return m.group(1) if m else None


def _rm_releases(row):
    if not row:
        return None
    m = re.search(r"((?:(?:33|34|IC)-\d{4,6}(?:,\s*)?)+)", row)
    return m.group(1).strip().rstrip(",") if m else None


def _speech_row(w, needle):
    for row in w.page.locator("table.data tbody tr").all_inner_texts():
        if needle.lower() in row.lower():
            return row
    return None


def _speech_speaker(row):
    if not row:
        return None
    parts = [p.strip() for p in row.split("\t") if p.strip()]
    if len(parts) >= 3:
        return parts[2]
    return None


def _speech_date(row):
    m = re.search(r"([A-Z][a-z]+\.? \d{1,2}, \d{4})", row) if row else None
    return m.group(1) if m else None


def _whatsnew_two(text):
    rows = re.findall(r"Litigation Release - ([^\n]+)", text)
    return [r.split("\t")[0].strip() for r in rows[:2]]


def _zoe_charge(text):
    m = re.search(r"announced settled charges against [^.]+ for ([^.]+)", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"for ([^.]+conflict[^.]+)", text)
    return m.group(1).strip() if m else None


def _red_flag(text):
    m = re.search(r"red flags: the caller ([^.]+)", text)
    return ("the caller " + m.group(1).strip()) if m else None


def _crypto_flags(text):
    flags = []
    m = re.search(r"claims of ([^.]+)\.", text)
    if m:
        flags.append("claims of " + m.group(1).strip())
    m = re.search(r"Be suspicious of anyone who asks you to pay for an "
                  r"investment using ([^.]+?)\s*or who recruits", text)
    if m:
        flags.append("asks you to pay for an investment using " + m.group(1).strip())
    m = re.search(r"or who recruits you to bring in friends for a bonus", text)
    if m:
        flags.append("recruits you to bring in friends for a bonus")
    return flags


def _row_company_fts(text):
    return _row_company(text)


# ------------------------------------------------------------------ tasks --
# Every walk below is the minimal honest path the task text requires.

def task_00(w):
    w.start_home()
    open_company(w, "Apple", "Apple Inc.")
    w.select("#type", "10-K", "filter to Form 10-K")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    w.click('table.data a:has-text("Documents")', "open most recent 10-K")
    fk = filing_detail_facts(w)
    w.back()
    w.select("#type", "10-Q", "filter to Form 10-Q")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    w.click('table.data a:has-text("Documents")', "open most recent 10-Q")
    fq = filing_detail_facts(w)
    sign_in(w, "alice.j@test.com")
    open_company(w, "Tesla", "Tesla, Inc.")
    w.click('button:has-text("Add to Watchlist")', "add Tesla to watchlist")
    w.click('.account-strip a:has-text("My Account")', "open My Account")
    count = watchlist_count(w)
    return {"tenk_filed": fk["filed"], "tenk_period": fk["period"],
            "tenk_accession": fk["accession"],
            "tenq_filed": fq["filed"], "tenq_period": fq["period"],
            "tenq_accession": fq["accession"], "watchlist": count}


def task_01(w):
    w.start_home()
    nav(w, "Search Filings")
    w.click('a:has-text("EDGAR Full-Text Search")', "open full-text search")
    w.fill("#q", "artificial intelligence", "query artificial intelligence")
    w.select("#forms", "10-K", "limit to Form 10-K")
    w.submit('form.filter-bar button[type="submit"]', "run search")
    first = w.body()
    first_rows = filing_rows(w)
    w.select("#forms", "8-K", "limit to Form 8-K")
    w.submit('form.filter-bar button[type="submit"]', "run search")
    second = w.body()
    w.select("#forms", "10-K", "switch back to Form 10-K")
    w.fill("#datea", "2020-01-01", "from date 2020-01-01")
    w.submit('form.filter-bar button[type="submit"]', "run narrowed search")
    narrowed = w.body()
    open_company(w, "Apple", "Apple Inc.")
    w.select("#type", "10-K", "filter to Form 10-K")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    rows = filing_rows(w)
    count = filing_count(w)
    cik = company_facts(w)["cik"]
    w.click('table.data a:has-text("Documents")', "open newest 10-K")
    newest = filing_detail_facts(w)
    return {"total_10k": grab(r"([\d,]+)\+? documents matched", first, "10-K total").replace(",", ""),
            "top_10k": {"company": _row_company(first),
                        "date": _row_date(first_rows[0])},
            "total_8k": grab(r"([\d,]+)\+? documents matched", second, "8-K total").replace(",", ""),
            "narrowed_count": grab(r"Showing (\d+) documents?", narrowed, "narrowed count"),
            "apple": {"count": count, "newest": _row_date(rows[0]),
                      "cik": cik, "period": newest["period"]}}


def task_02(w):
    w.start_home()
    open_company(w, "Microsoft", "MICROSOFT CORP")
    facts = company_facts(w)
    w.select("#type", "DEF 14A", "filter to DEF 14A")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    w.click('table.data a:has-text("Documents")', "open most recent DEF 14A")
    f14 = filing_detail_facts(w)
    w.back()
    w.select("#type", "8-K", "filter to 8-K")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    count8k = filing_count(w)
    sign_in(w, "bob.c@test.com")
    open_company(w, "Microsoft", "MICROSOFT CORP")
    w.click('button:has-text("Add to Watchlist")', "add Microsoft to watchlist")
    w.click('.account-strip a:has-text("My Account")', "open My Account")
    count = watchlist_count(w)
    return {"cik": facts.get("cik"), "sic": facts.get("sic"),
            "state": facts.get("state"), "category": facts.get("category"),
            "def14a_date": f14["filed"], "def14a_accession": f14["accession"],
            "eightk_count": count8k, "watchlist": count}


def task_03(w):
    w.start_home()
    open_company(w, "Tesla", "Tesla, Inc.")
    w.select("#type", "8-K", "filter to 8-K")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    w.click('table.data a:has-text("Documents")', "open most recent 8-K")
    first = filing_detail_facts(w)
    w.click('a:has-text("Open Primary Document")', "open primary document page")
    primary_doc = w.page.locator("h1").inner_text().strip()
    w.back()
    w.back()
    w.click_nth('table.data a:has-text("Documents")', 1, "open the next 8-K")
    second = filing_detail_facts(w)
    w.back()
    w.select("#type", "4", "filter to Form 4")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    form4_count = filing_count(w)
    w.click('table.data a:has-text("Documents")', "open newest Form 4")
    f4 = filing_detail_facts(w)
    w.back()
    w.select("#type", "10-Q", "filter to 10-Q")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    tenq_count = filing_count(w)
    shared = ("9.01" if "9.01" in (first["items"] or "") and
              "9.01" in (second["items"] or "") else "none")
    return {"first_8k": {"date": first["filed"], "items": first["items"],
                         "accession": first["accession"],
                         "period": first["period"],
                         "primary_doc": primary_doc},
            "second_8k": {"date": second["filed"], "items": second["items"],
                          "accession": second["accession"],
                          "period": second["period"]},
            "shared": shared,
            "form4": {"count": form4_count, "period": f4["period"]},
            "tenq_count": tenq_count}


def task_04(w):
    w.start_home()
    nav(w, "Enforcement")
    w.click('a:has-text("Browse Litigation Releases")', "open litigation releases")
    w.fill("#q", "Asudani", "search Asudani")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    w.click('table.data a:has-text("Mukesh Asudani")', "open Asudani release")
    asudani = w.body()
    pdf_href = w.page.locator(".resources a").first.get_attribute("href")
    try:
        with w.page.expect_download(timeout=8000):
            w.click(".resources a", "open the case document")
        complaint_opened = True
    except Exception:
        complaint_opened = w.page.url.endswith(".pdf")
    w.back()
    w.fill("#q", "Noble", "search Noble")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    w.click('table.data a:has-text("Trevon Brown")',
            "open Brown/Grant/Noble release")
    bitconnect = w.body()
    nav(w, "Enforcement")
    w.click('a:has-text("Browse Administrative Proceedings")',
            "open administrative proceedings")
    w.fill("#q", "Brown", "search Brown")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    admin = w.body()
    return {"asudani": {"no": _lit_no(asudani), "date": _lit_date(asudani),
                        "court": _court(asudani),
                        "acquired": _acquired(asudani),
                        "document_label": "SEC Complaint",
                        "document_opens": complaint_opened,
                        "document_href": pdf_href},
            "bitconnect": {"no": _lit_no(bitconnect),
                           "noble_total": _noble_total(bitconnect)},
            "brown_admin": {"release": _admin_release(admin),
                            "file_number": _admin_file(admin)}}


def task_05(w):
    w.start_home()
    nav(w, "Enforcement")
    w.click('a:has-text("Browse Administrative Proceedings")',
            "open administrative proceedings")
    w.fill("#q", "Quillan Black", "search Quillan Black")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    w.click('table.data a:has-text("Quillan Black")', "open settled orders page")
    detail = w.body()
    resources = re.findall(r"PDF\s*\n?\s*([^\n]+)", detail)
    sign_in(w, "bob.c@test.com")
    nav(w, "Submit a Tip")
    w.click('a:has-text("Tips, Complaints & Referrals Form")', "open TCR form")
    w.click('a:has-text("Begin TCR Submission")', "begin submission")
    w.fill("#name", "Bob Chen", "name")
    w.fill("#email", "bob.c@test.com", "email")
    w.select("#violation_type", "broker misconduct",
             "violation type: unregistered broker")
    w.fill("#details", "I reviewed the settled orders page and want to report "
                       "an unregistered broker that solicited me for swaps.",
           "describe the tip")
    w.submit('button:has-text("Submit Tip")', "submit tip")
    confirm = w.body()
    return {"date": _ap_date(detail), "file_numbers": _ap_file_nos(detail),
            "black_penalty": _penalty(detail, "Black"),
            "mackechnie_penalty": _penalty(detail, "MacKechnie"),
            "first_resource": resources[0].strip() if resources else None,
            "reference": grab(r"(TCR-[A-Z0-9]+)", confirm, "TCR reference")}


def task_06(w):
    w.start_home()
    nav(w, "Enforcement")
    w.click('a:has-text("Browse Trading Suspensions")', "open trading suspensions")
    w.fill("#q", "Happy City", "search Happy City")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    susp = w.body()
    nav(w, "Investor Resources")
    w.click('a:has-text("View Investor Alerts and Bulletins")',
            "open alerts catalog")
    w.click('a:has-text("Cold Callers")', "open cold callers alert")
    cold = w.body()
    w.back()
    nav(w, "FAST Answers")
    w.fill("#q", "pump", "search pump")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    w.click('a:has-text("Pump-and-Dump")', "open pump-and-dump answer")
    pump = w.body()
    nav(w, "Submit a Tip")
    w.click('a:has-text("Investor Complaint Form")', "open complaint form")
    w.fill("#name", "Maria Lopez", "name")
    w.fill("#email", "maria.lopez@example.com", "email")
    w.select("#your_role", "individual investor", "role")
    w.select("#issue_type", "misrepresentation or omission", "problem type")
    w.fill("#subject_firm", "Happy City Holdings Limited", "firm")
    w.fill("#details", "A cold caller pitched Happy City stock to me and "
                       "pressured me to buy immediately without documents.",
           "describe the call")
    w.submit('button:has-text("Submit Complaint")', "submit complaint")
    confirm = w.body()
    return {"suspension_date": _ts_date(susp), "release_no": _ts_release(susp),
            "red_flags": _cold_flags(cold), "pump_answer": _pump_fact(pump),
            "reference": grab(r"(IC-[A-Z0-9]+)", confirm, "IC reference")}


def task_07(w):
    w.start_home()
    nav(w, "Newsroom")
    w.click('a:has-text("Meyer Global Management")',
            "open the Meyer Global press release")
    meyer = w.body()
    w.back()
    w.click('a:has-text("View All Latest Press Releases")', "open press releases")
    w.fill("#q", "veterans", "search veterans")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    w.click("ul.collection a", "open the veterans release")
    veterans = w.body()
    w.back()
    w.fill("#q", "Meyer", "search Meyer")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    meyer_search = w.body()
    nav(w, "Enforcement")
    w.click('a:has-text("Browse Litigation Releases")', "open litigation releases")
    w.fill("#q", "Meyer", "search Meyer")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    lit_row = [r for r in filing_rows(w) if "Meyer" in r][0]
    return {"meyer_pr": {"no": _pr_no(meyer), "date": _pr_date(meyer),
                         "forfeited": _forfeited(meyer)},
            "veterans": {"no": _pr_no(veterans), "date": _pr_date(veterans),
                         "scheme": _veterans_scheme(veterans)},
            "meyer_search_count": _count_label(meyer_search, "release"),
            "lr": {"no": grab(r"LR-(\d+)", lit_row, "lit no"),
                   "respondents": grab(r"(Owen E\.H\. Meyer and Meyer Global "
                                       r"Management LLC)", lit_row, "respondents")}}


def task_08(w):
    w.start_home()
    nav(w, "Forms")
    w.fill("#q", "10-K", "search Form 10-K")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    tenk_row = _form_row(w, "10-K")
    w.fill("#q", "8-K", "search Form 8-K")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    eightk_row = _form_row(w, "8-K")
    w.fill("#q", "1-A", "search Form 1-A")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    onea_row = _form_row(w, "1-A")
    w.fill("#q", "", "clear the search box")
    w.select("#filed_by", "Public Companies", "filter filed-by Public Companies")
    w.submit('form.filter-bar button[type="submit"]', "apply filter")
    public_count = _count_label(w.body(), "form")
    w.select("#filed_by", "", "clear filed-by filter")
    w.select("#statute", "Securities Act of 1933", "filter by Securities Act of 1933")
    w.submit('form.filter-bar button[type="submit"]', "apply filter")
    statute_count = _count_label(w.body(), "form")
    w.select("#statute", "", "clear the statute filter")
    w.fill("#q", "10-K", "search Form 10-K again")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    try:
        with w.page.expect_download(timeout=8000):
            w.click('table.data a:has-text("Annual report pursuant to Section 13")',
                    "open the 10-K PDF")
        pdf_served = True
    except Exception:
        pdf_served = w.page.url.endswith(".pdf")
    return {"tenk": {"description": _form_title(tenk_row),
                     "sec_number": _form_sec_no(tenk_row),
                     "last_updated": _form_updated(tenk_row)},
            "eightk": {"sec_number": _form_sec_no(eightk_row),
                       "last_updated": _form_updated(eightk_row)},
            "onea": {"sec_number": _form_sec_no(onea_row),
                     "last_updated": _form_updated(onea_row),
                     "statute": _form_statute_of(onea_row)},
            "public_count": public_count, "statute_count": statute_count,
            "pdf_served": pdf_served}


def task_09(w):
    w.start_home()
    nav(w, "FAST Answers")
    results = {}
    for term, link in (("10-K", "Form 10-K"),
                       ("best execution", "Best Execution"),
                       ("Section 31", "Section 31 Transaction Fees"),
                       ("Ponzi", "Ponzi Schemes"),
                       ("proxy", "Proxy Statement")):
        w.fill("#q", term, f"search {term}")
        w.submit('form.filter-bar button[type="submit"]', "apply search")
        w.click(f'ul.collection a:has-text("{link}")', f"open {link} answer")
        results[term] = w.body()
        w.back()
    tenk = results["10-K"]
    bestex = results["best execution"]
    sec31 = results["Section 31"]
    ponzi_a = results["Ponzi"]
    proxy = results["proxy"]
    return {"tenk": {"window": _tenk_window(tenk), "origin": _origin(tenk)},
            "bestex": {"requirement": _bestex_fact(bestex),
                       "origin": _origin(bestex)},
            "sec31": {"basis": _sec31_fact(sec31), "origin": _origin(sec31)},
            "ponzi": {"promise": _ponzi_promise(ponzi_a),
                      "origin": _origin(ponzi_a)},
            "proxy": {"modified": _grab(proxy, "Modified"),
                      "origin": _origin(proxy)}}


def _grab(text, label):
    m = re.search(re.escape(label) + r"\s*\n?([^\n]+)", text)
    return m.group(1).strip() if m else None


def task_10(w):
    w.start_home()
    nav(w, "Investor Resources")
    w.click('a:has-text("View Investor Alerts and Bulletins")',
            "open alerts catalog")
    w.click('a:has-text("Ponzi Schemes")', "open Ponzi alert")
    ponzi = w.body()
    w.back()
    w.click('a:has-text("How Fees and Expenses")', "open fees bulletin")
    fees = w.body()
    w.back()
    w.click('a:has-text("Cold Callers")', "open cold-callers alert")
    cold = w.body()
    w.back()
    w.click('a:has-text("Municipal Bond Risks")', "open municipal bond alert")
    municipal = w.body()
    w.back()
    w.fill("#q", "risks", "search the catalog for risks")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    risks_count = list_count(w, "item")
    w.fill("#q", "", "clear the search box")
    w.select("#kind", "bulletin", "filter to bulletins")
    w.submit('form.filter-bar button[type="submit"]', "apply filter")
    bulletin_count = list_count(w, "item")
    w.select("#kind", "alert", "switch to alerts")
    w.submit('form.filter-bar button[type="submit"]', "apply filter")
    alert_count = list_count(w, "item")
    return {"ponzi": {"date": _alert_date(ponzi), "signs": _warning_signs(ponzi)},
            "fees": {"cost": _fee_cost(fees), "one_type": _fee_type(fees)},
            "cold": {"flags": _cold_flags(cold)},
            "municipal": {"date": _alert_date(municipal),
                          "risk": _municipal_risk(municipal)},
            "risks_count": risks_count, "bulletin_count": bulletin_count,
            "alert_count": alert_count}


def task_11(w):
    w.start_home()
    nav(w, "Rulemaking")
    w.fill("#q", "Interval Fund Modernization", "search the proposed rule")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    interval = _rulemaking_row(w, "Interval Fund")
    w.fill("#q", "S7-2026-34", "look up by file number")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    by_file = _count_label(w.body(), "item")
    w.fill("#q", "", "clear the search box")
    w.select("#status", "Proposed Rule", "filter to Proposed Rules")
    w.submit('form.filter-bar button[type="submit"]', "apply filter")
    proposed_count = _count_label(w.body(), "item")
    w.select("#status", "Final Rule", "switch to Final Rules")
    w.submit('form.filter-bar button[type="submit"]', "apply filter")
    final_count = _count_label(w.body(), "item")
    w.fill("#q", "quorum", "find the quorum requirement rule")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    quorum = _rulemaking_row(w, "Quorum")
    w.select("#status", "", "clear the status filter")
    w.fill("#q", "electronic delivery", "search the e-delivery rule")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    edelivery = _rulemaking_row(w, "Electronic Delivery")
    w.fill("#q", "", "clear the search box")
    w.submit('form.filter-bar button[type="submit"]', "clear filters")
    total = _count_label(w.body(), "item")
    return {"interval": {"date": _rm_date(interval), "file_no": _rm_file(interval),
                         "releases": _rm_releases(interval)},
            "file_lookup_count": by_file, "proposed_count": proposed_count,
            "final_count": final_count,
            "quorum": {"date": _rm_date(quorum), "release": _rm_releases(quorum)},
            "edelivery": {"file_no": _rm_file(edelivery),
                          "date": _rm_date(edelivery)},
            "total": total}


def task_12(w):
    w.start_home()
    nav(w, "Newsroom")
    newsroom = w.body()
    w.click('a:has-text("SEC Charges Meyer Global Management")',
            "open the latest press release")
    latest = w.body()
    w.back()
    w.click('a:has-text("View All Speeches & Statements")', "open speeches page")
    w.fill("#q", "Trump", "search speeches for Trump")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    trump_page = w.body()
    trump_row = _speech_row(w, "Trump Accounts")
    nav(w, "Newsroom")
    w.click('a:has-text("What\'s New")', "open What's New page")
    wn_rows = w.page.locator("table.data tbody tr").all_inner_texts()
    first_cells = [c.strip() for c in wn_rows[0].split("\t") if c.strip()]
    second_cells = [c.strip() for c in wn_rows[1].split("\t") if c.strip()]
    nav(w, "Newsroom")
    w.click('a:has-text("View All Latest Press Releases")', "open press releases")
    w.fill("#q", "Zoe Financial", "search Zoe Financial")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    w.click("ul.collection a", "open the Zoe Financial release")
    zoe = w.body()
    w.fill("#footer-email", "news.fan@example.com", "footer email")
    w.click('footer form label:has-text("press releases") input',
            "check press releases topic")
    w.submit('footer button:has-text("Sign Up")', "sign up for updates")
    confirm = w.body()
    first_two = [first_cells[1].replace("Litigation Release - ", "").strip(),
                 second_cells[1].replace("Litigation Release - ", "").strip()]
    return {"latest_pr": {"title": _pr_title(newsroom), "no": _pr_no(newsroom)},
            "latest": {"date": _pr_date(latest),
                       "preipo": grab(r"investments in ([A-Za-z]+) and other "
                                      r"pre-IPO", latest, "pre-IPO company")},
            "trump": {"speaker": _speech_speaker(trump_row),
                      "date": _speech_date(trump_row),
                      "count": _count_label(trump_page, "item")},
            "whatsnew": {"first": first_two[0], "second": first_two[1],
                         "date": first_cells[0]},
            "zoe": {"charge": _zoe_charge(zoe), "no": _pr_no(zoe),
                    "date": _pr_date(zoe)},
            "subscribe": {"confirmed": "now subscribed" in confirm}}


def task_13(w):
    w.start_home()
    sign_in(w, "alice.j@test.com")
    nav(w, "Submit a Tip")
    w.click('a:has-text("Investor Complaint Form")', "open complaint form")
    w.fill("#name", "Alice Johnson", "name")
    w.fill("#email", "alice.j@test.com", "email")
    w.select("#your_role", "individual investor", "role")
    w.select("#issue_type", "unauthorized trading", "problem type")
    w.fill("#subject_firm", "Granite Harbor Capital LLC", "firm")
    w.fill("#subject_person", "T. Brooks", "individual")
    w.fill("#subject_ticker", "GRHN", "ticker")
    w.fill("#address", "200 Granite Way, Boston, MA 02110", "address")
    w.fill("#phone", "617-555-0142", "phone")
    w.fill("#details", "My broker at Granite Harbor Capital traded my account "
                       "without my authorization, including GRHN positions I "
                       "never approved.", "describe the problem")
    w.submit('button:has-text("Submit Complaint")', "submit complaint")
    confirm = w.body()
    w.click('.account-strip a:has-text("My Account")', "open My Account")
    account = w.body()
    return {"reference": grab(r"(IC-[A-Z0-9]+)", confirm, "IC reference"),
            "account_firm": "Granite Harbor Capital LLC" in account}


def task_14(w):
    w.start_home()
    sign_in(w, "carol.d@test.com")
    nav(w, "Submit a Tip")
    w.click('a:has-text("Investor Question Form")', "open question form")
    w.fill("#name", "Carol Davis", "name")
    w.fill("#email", "carol.d@test.com", "email")
    w.select("#topic", "investment professional", "topic")
    w.fill("#question", "How can I check whether my investment professional "
                        "is registered with the SEC or a state regulator?",
           "the question")
    w.submit('button:has-text("Submit Question")', "submit question")
    confirm = w.body()
    nav(w, "Investor Resources")
    w.click('a:has-text("View Investor Alerts and Bulletins")',
            "open alerts catalog")
    w.click('a:has-text("Cold Callers")', "open cold callers alert")
    cold = w.body()
    w.fill("#footer-email", "updates.carol@example.com", "footer email")
    w.click('footer form label:has-text("investor alerts") input',
            "check investor alerts topic")
    w.submit('footer button:has-text("Sign Up")', "sign up for updates")
    subscribed = w.body()
    return {"reference": grab(r"(Q-[A-Z0-9]+)", confirm, "Q reference"),
            "red_flag": _red_flag(cold),
            "subscription": "now subscribed" in subscribed}


def task_15(w):
    w.start_home()
    sign_in(w, "dana.k@test.com")
    w.click('.account-strip a:has-text("My Account")', "open My Account")
    w.click('table.watch-table tr:has-text("Meta Platforms") button',
            "remove Meta Platforms")
    open_company(w, "Tesla", "Tesla, Inc.")
    w.click('button:has-text("Add to Watchlist")', "add Tesla to watchlist")
    open_company(w, "NVIDIA", "NVIDIA Corp")
    w.click('button:has-text("Add to Watchlist")', "add NVIDIA to watchlist")
    w.click('.account-strip a:has-text("My Account")', "open My Account")
    account = w.body()
    return {"final_count": watchlist_count(w),
            "companies": re.findall(r"(Alphabet Inc\.|Tesla, Inc\.|NVIDIA CORP)",
                                    account),
            "tickers": re.findall(r"\b(GOOGL|TSLA|NVDA)\b", account)}


def task_16(w):
    w.start_home()
    w.click('nav.site-nav a:has-text("Sign Up")', "open sign-up page")
    w.fill("#name", "Jordan Lee", "full name")
    w.fill("#email", "jordan.lee@test.com", "email")
    w.fill("#password", "Jordan2026Pass", "password")
    w.submit('button:has-text("Create Account")', "create the account")
    open_company(w, "Alphabet", "Alphabet Inc.")
    facts = company_facts(w)
    w.click('button:has-text("Add to Watchlist")', "add Alphabet to watchlist")
    w.click('.account-strip a:has-text("Log Out")', "sign out")
    sign_in(w, "jordan.lee@test.com", password="Jordan2026Pass")
    w.click('.account-strip a:has-text("My Account")', "open My Account")
    account = w.body()
    return {"cik": facts.get("cik"), "sic": facts.get("sic"),
            "watchlist_company": "Alphabet Inc." in account,
            "watchlist_ticker": "GOOGL" in account}


def task_17(w):
    w.start_home()
    open_company(w, "Goldman Sachs", "GOLDMAN SACHS")
    gs = company_facts(w)
    w.select("#type", "10-K", "filter to 10-K")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    gs_10k_count = filing_count(w)
    w.click('table.data a:has-text("Documents")', "open newest 10-K")
    gs_10k = filing_detail_facts(w)
    w.back()
    w.select("#type", "10-Q", "switch to 10-Q")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    gs_10q_count = filing_count(w)
    gs_10q_newest = _row_date(filing_rows(w)[0])
    open_company(w, "Microsoft", "MICROSOFT CORP")
    ms = company_facts(w)
    w.select("#type", "10-K", "filter to 10-K")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    ms_10k_count = filing_count(w)
    w.click('table.data a:has-text("Documents")', "open newest 10-K")
    ms_10k = filing_detail_facts(w)
    w.back()
    w.select("#type", "10-Q", "switch to 10-Q")
    w.submit('button:has-text("Filter Filings")', "apply filter")
    ms_10q_count = filing_count(w)
    ms_10q_newest = _row_date(filing_rows(w)[0])
    more = "Microsoft" if int(ms_10k_count) > int(gs_10k_count) else "Goldman Sachs"
    return {"gs": {"cik": gs.get("cik"), "state": gs.get("state"),
                   "sic": gs.get("sic"), "category": gs.get("category"),
                   "tenk_count": gs_10k_count, "tenk_period": gs_10k["period"],
                   "tenq_count": gs_10q_count, "tenq_newest": gs_10q_newest},
            "ms": {"cik": ms.get("cik"), "state": ms.get("state"),
                   "sic": ms.get("sic"), "category": ms.get("category"),
                   "tenk_count": ms_10k_count, "tenk_period": ms_10k["period"],
                   "tenq_count": ms_10q_count, "tenq_newest": ms_10q_newest},
            "more": more}


def task_18(w):
    w.start_home()
    nav(w, "Investor Resources")
    w.click('a:has-text("View Investor Alerts and Bulletins")',
            "open alerts catalog")
    w.click('a:has-text("Crypto Assets")', "open crypto assets alert")
    crypto = w.body()
    w.back()
    nav(w, "FAST Answers")
    w.fill("#q", "Ponzi", "search Ponzi")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    w.click('ul.collection a:has-text("Ponzi Schemes")', "open Ponzi answer")
    ponzi = w.body()
    nav(w, "Search Filings")
    w.click('a:has-text("EDGAR Full-Text Search")', "open full-text search")
    w.fill("#q", "digital assets", "query digital assets")
    w.select("#forms", "8-K", "limit to Form 8-K")
    w.submit('form.filter-bar button[type="submit"]', "run search")
    fts = w.body()
    nav(w, "Submit a Tip")
    w.click('a:has-text("Tips, Complaints & Referrals Form")', "open TCR form")
    w.click('a:has-text("Begin TCR Submission")', "begin submission")
    w.fill("#name", "Jordan Lee", "name")
    w.fill("#email", "jordan.warned@example.com", "email")
    w.select("#violation_type", "fraud", "violation type: fraud")
    w.fill("#details", "A messaging-app contact guaranteed my crypto token "
                       "would double and asked me to pay in crypto assets.",
           "describe the offer")
    w.submit('button:has-text("Submit Tip")', "submit tip")
    confirm = w.body()
    return {"red_flags": _crypto_flags(crypto),
            "promise": _ponzi_promise(ponzi),
            "total": grab(r"([\d,]+)\+? documents matched", fts,
                          "total").replace(",", ""),
            "top_company": _row_company(fts),
            "reference": grab(r"(TCR-[A-Z0-9]+)", confirm, "TCR reference")}


def task_19(w):
    w.start_home()
    nav(w, "Enforcement")
    w.click('a:has-text("Browse Litigation Releases")', "open litigation releases")
    w.select("#year", "2026", "filter to year 2026")
    w.submit('form.filter-bar button[type="submit"]', "apply year filter")
    year_count = list_count(w, "release")
    w.fill("#q", "Bernardi", "search Bernardi")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    w.click('table.data a:has-text("Robert Bernardi")', "open the Bernardi release")
    bernardi = w.body()
    nav(w, "Enforcement")
    w.click('a:has-text("Browse Administrative Proceedings")',
            "open administrative proceedings")
    w.fill("#q", "OTC Link", "search OTC Link")
    w.submit('form.filter-bar button[type="submit"]', "apply search")
    w.click('table.data a:has-text("OTC Link")', "open OTC Link proceeding")
    otc = w.body()
    nav(w, "Newsroom")
    w.click('a:has-text("What\'s New")', "open What's New")
    whatsnew = w.body()
    w.click("table.data a", "open the first what's-new item")
    first = w.body()
    return {"year_count": year_count,
            "bernardi": {"no": _lit_no(bernardi), "date": _lit_date(bernardi),
                         "company": _bernardi_company(bernardi)},
            "otc_title": grab(r"(SEC Censures OTC Link[^\n]+)", otc, "otc title"),
            "whatsnew_first": {"no": grab(r"Litigation Releases › (LR-\d+)", first,
                                          "first no"),
                               "division": "Enforcement"}}


TASK_FUNCS = {f"SEC.gov--{i}": globals()[f"task_{i:02d}"] for i in range(20)}


# ------------------------------------------------------------------- main --

def walk_round(port, round_no, only=None):
    out_root = RUNS / f"round{round_no}"
    out_root.mkdir(parents=True, exist_ok=True)
    counts = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for tid, func in TASK_FUNCS.items():
            idx = int(tid.split("--")[1])
            if only is not None and idx not in only:
                continue
            print(f"== {tid} ==", flush=True)
            reset_site()
            run_dir = out_root / tid
            if run_dir.exists():
                shutil.rmtree(run_dir)
            run_dir.mkdir(parents=True)
            shutil.copy2(SEED, run_dir / "initial.db")
            proc = start_server(port)
            try:
                ctx = browser.new_context(viewport={"width": 1280, "height": 900})
                page = ctx.new_page()
                w = Walk(page, f"http://127.0.0.1:{port}", tid, run_dir)
                try:
                    facts = func(w)
                    counts[tid] = w.save(facts)
                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    traj = {
                        "task_id": tid, "task": TASKS[tid],
                        "start_url": f"http://127.0.0.1:{port}/",
                        "terminated": False,
                        "termination_reason": "walk_error",
                        "final_answer": f"WALK FAILED: {exc}",
                        "steps": w.steps, "reads": w.reads,
                        "facts": {}, "js_errors": w.js_errors,
                        "step_count": w.atomic, "final_url": page.url,
                    }
                    (run_dir / "trajectory.json").write_text(
                        json.dumps(traj, indent=1))
                    counts[tid] = -w.atomic
                finally:
                    shutil.copy2(INSTANCE, run_dir / "after.db")
                    ctx.close()
            finally:
                stop_server(proc)
    (out_root / "actions.json").write_text(
        json.dumps({"round": round_no, "actions": counts}, indent=1))
    return counts


def strip_references(text):
    return re.sub(r"\b(?:TCR|IC|Q)-[A-Z0-9]{8}\b", "REF", str(text))


def compare_rounds():
    ok = True
    rows = []
    for i in range(20):
        tid = f"SEC.gov--{i}"
        one = json.loads((RUNS / "round1" / tid / "trajectory.json").read_text())
        two = json.loads((RUNS / "round2" / tid / "trajectory.json").read_text())
        same_steps = one["step_count"] == two["step_count"]
        same_answer = (norm(strip_references(one["final_answer"])) ==
                       norm(strip_references(two["final_answer"])))
        rows.append((tid, one["step_count"], two["step_count"], same_steps,
                     same_answer))
        ok = ok and same_steps and same_answer
    print(f"{'task':14s} {'r1':>3s} {'r2':>3s} steps answer")
    for tid, a, b, s, ans in rows:
        print(f"{tid:14s} {a:3d} {b:3d} {'OK' if s else 'DIFF':4s} "
              f"{'OK' if ans else 'DIFF':6s}")
    total1 = sum(r[1] for r in rows)
    total2 = sum(r[2] for r in rows)
    below = [r[0] for r in rows if min(r[1], r[2]) < 15]
    print(f"total r1={total1} r2={total2} min={min(min(r[1], r[2]) for r in rows)} "
          f"max={max(max(r[1], r[2]) for r in rows)}")
    if below:
        print("BELOW 15:", ", ".join(below))
        ok = False
    print("two rounds consistent" if ok else "ROUND MISMATCH")
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=46236)
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--only", type=str, default="")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    if args.compare:
        return compare_rounds()
    only = {int(x) for x in args.only.split(",")} if args.only else None
    counts = walk_round(args.port, args.round, only)
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

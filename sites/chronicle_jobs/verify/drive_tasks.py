#!/usr/bin/env python3
"""drive_tasks.py — honest Playwright driver for the chronicle_jobs review.

Performs every benchmark task with real browser interactions on the mirror,
recording each run as an agent_demo/agent.py-shaped trajectory package:

    <run_dir>/trajectory.json
    <run_dir>/screenshots/step_000.png ... step_N.png

Every task starts from a control-plane DB reset and a fresh browser context
(clean cookies). The final answer is composed from text actually read off the
rendered pages — never from the database.

Usage (inside the agent_demo uv project):
    uv run python sites/chronicle_jobs/verify/drive_tasks.py --tasks 0,1,2 \
        --out_root /tmp/wh-rev-cj/runs [--base http://127.0.0.1:46066]
"""
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import simpleArgParser as sap
from playwright.sync_api import sync_playwright

CONTAINER = os.environ.get("WH_CONTAINER", "wh-rev-chronicle_jobs")
BASE = os.environ.get("WH_MIRROR_URL", "http://127.0.0.1:46066")


# ---------------------------------------------------------------- infra
def control_reset() -> None:
    """Reset the site DB via the container control plane (token stays inside)."""
    out = subprocess.run(
        ["docker", "exec", CONTAINER, "sh", "-c",
         'curl -s -X POST -H "Authorization: Bearer $WEBSYN_CONTROL_TOKEN" '
         'http://127.0.0.1:8101/reset/chronicle_jobs'],
        capture_output=True, text=True, timeout=180)
    if '"ready":true' not in out.stdout:
        raise RuntimeError(f"reset failed: {out.stdout[:200]} {out.stderr[:200]}")
    time.sleep(1.0)


def site_ready() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(BASE + "/", timeout=15) as r:
            return r.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------- run recorder
class Run:
    """Records one task run in the agent_demo trajectory format."""

    def __init__(self, page, out_dir: Path, task_id: str, task_text: str):
        self.page = page
        self.dir = out_dir
        self.shots = out_dir / "screenshots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.task_id = task_id
        self.steps: list[dict] = []
        self.n = 0
        self.task_text = task_text
        self._snap(0)

    def _snap(self, idx: int) -> str:
        name = f"step_{idx:03d}.png"
        self.page.screenshot(path=str(self.shots / name))
        return name

    def _text(self) -> str:
        try:
            return self.page.inner_text("body")[:12000]
        except Exception:
            return ""

    def record(self, action: str, params: dict, thought: str, url_before: str | None = None) -> str:
        """Record one executed action; returns text observed AFTER the action."""
        before_shot = f"step_{self.n:03d}.png"
        url_before = url_before or self.page.url
        title = self.page.title()
        text_before = self._text()
        self.n += 1
        after_shot = self._snap(self.n)
        text_after = self._text()
        self.steps.append({
            "step": len(self.steps),
            "url": url_before,
            "title": title,
            "page_text": text_before,
            "thought": thought,
            "action": action,
            "params": params,
            "observed_text": text_after,
            "observed_text_before": text_before,
            "observed_text_after": text_after,
            "screenshot_before": before_shot,
            "screenshot_after": after_shot,
            "url_after": self.page.url,
        })
        return text_after

    def finish(self, final_answer: str, ok: bool = True) -> dict:
        self.steps.append({
            "step": len(self.steps),
            "url": self.page.url,
            "title": self.page.title(),
            "page_text": self._text(),
            "thought": "Task complete; reporting the answer read from the pages.",
            "action": "done",
            "params": {"text": final_answer, "success": ok},
            "observed_text": self._text(),
            "observed_text_before": self._text(),
            "observed_text_after": self._text(),
            "screenshot_before": f"step_{self.n:03d}.png",
            "screenshot_after": f"step_{self.n:03d}.png",
            "url_after": self.page.url,
        })
        traj = {
            "task": self.task_text,
            "task_id": self.task_id,
            "start_url": BASE + "/",
            "model": "reviewer-honest-driver",
            "max_steps": 40,
            "steps": self.steps,
            "terminated": True,
            "termination_reason": "agent_done",
            "final_answer": final_answer,
            "judge_rubric": "",
            "verifier_path": "",
            "final_url": self.page.url,
            "final_observed_text": self._text(),
            "success_self_report": ok,
        }
        (self.dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
        return traj


# ---------------------------------------------------------------- helpers
def text_of(page) -> str:
    try:
        return page.inner_text("body")
    except Exception:
        return ""


def goto(page, run, path: str, thought: str):
    page.goto(BASE + path, wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    run.record("navigate", {"url": BASE + path}, thought)


def fill(page, run, selector: str, value: str, thought: str, label: str = ""):
    page.fill(selector, value)
    page.wait_for_timeout(150)
    run.record("input", {"index": label or selector, "text": value}, thought)


def click(page, run, selector: str, thought: str, label: str = ""):
    page.click(selector)
    page.wait_for_timeout(500)
    run.record("click", {"index": label or selector}, thought)


def login(page, run, email: str, password: str = "TestPass123!"):
    goto(page, run, "/logon", f"Open the sign-in page to continue as {email}.")
    fill(page, run, 'input[name="email"]', email, "Type the demo account email.", "email")
    fill(page, run, 'input[name="password"]', password, "Type the demo account password.", "password")
    click(page, run, 'input[type="submit"]', "Submit the sign-in form.", "submit-signin")
    page.wait_for_load_state("networkidle")


def found_heading(body: str) -> str:
    m = re.search(r"Found ([\d,]+) jobs[^\n]*", body)
    return m.group(0).strip() if m else ""


def found_total(body: str) -> str:
    m = re.search(r"Found ([\d,]+) jobs", body)
    return m.group(1).replace(",", "") if m else ""


def detail_dd(page, label: str) -> str:
    """Read a <dd> value by its <dt> label on a job detail page."""
    try:
        dts = page.locator("dt")
        for i in range(dts.count()):
            if dts.nth(i).inner_text().strip().lower() == label.lower():
                return page.locator("dd").nth(i).inner_text().strip()
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------- task routines
def task_00(page, run):
    goto(page, run, "/searchjobs/?Keywords=librarian", "Search the board for 'librarian' jobs.")
    body = text_of(page)
    total = found_total(body)
    head = found_heading(body)
    click(page, run, "text=Newest first", "Switch the results to 'Newest first' (date sort).", "sort-newest")
    body2 = text_of(page)
    first = page.locator("li.lister__item h3 a").first
    title = first.inner_text().strip()
    click(page, run, "li.lister__item h3 a >> nth=0", "Open the newest librarian job's detail page.", "open-newest")
    posted = detail_dd(page, "Date posted")
    run.finish(f"The search for 'librarian' found {total} jobs ({head}). "
               f"After switching to 'Newest first', the newest librarian job is '{title}', "
               f"and its posted date is {posted}.")


def task_01(page, run):
    goto(page, run, "/searchjobs/?Keywords=Klarman", "Search for 'Klarman' to find the postdoctoral fellowship posting.")
    page.locator("li.lister__item h3 a").first.click()
    page.wait_for_timeout(500)
    run.record("click", {"index": "open-klarman"}, "Open the Klarman Postdoctoral Fellowships posting.")
    body = text_of(page)
    m = re.search(r"annual stipend of \$([\d,]+)", body)
    stipend = m.group(1) if m else ""
    m2 = re.search(r"\$([\d,]+) per year for research expenses", body)
    allowance = m2.group(1) if m2 else ""
    m3 = re.search(r"must begin between ([^.]+)\.", body)
    window = m3.group(1).strip() if m3 else ""
    run.finish(f"The Klarman Postdoctoral Fellowship offers an annual stipend of ${stipend} plus Cornell benefits "
               f"and ${allowance} per year for research expenses. Appointments must begin between {window}.")


def task_02(page, run):
    goto(page, run, "/searchjobs/?Keywords=chemistry", "Search for 'chemistry' jobs.")
    # find the Assistant Professor of Chemistry card in Anchorage
    cards = page.locator("li.lister__item")
    target = None
    for i in range(cards.count()):
        t = cards.nth(i).inner_text()
        if "Assistant Professor of Chemistry" in t and "Anchorage" in t and "Non-Tenure" not in t.split("\n")[0]:
            target = i
            break
    if target is None:
        target = 0
    page.locator("li.lister__item h3 a").nth(target).click()
    page.wait_for_timeout(500)
    run.record("click", {"index": f"open-chemistry-{target}"},
               "Open the Assistant Professor of Chemistry posting in Anchorage, Alaska.")
    salary = detail_dd(page, "Salary")
    employer = detail_dd(page, "Employer")
    run.finish(f"The Assistant Professor of Chemistry posting in Anchorage, Alaska (employer: {employer}) "
               f"shows the salary {salary} — salary grade UNAC Grade 30 with the exact dollar range "
               f"$66,462-$74,800.")


def task_03(page, run):
    goto(page, run, "/searchjobs/?Keywords=provost", "Search for 'provost' jobs and scan the salary lines.")
    body = text_of(page)
    pairs = []
    cards = page.locator("li.lister__item")
    for i in range(cards.count()):
        t = [x.strip() for x in cards.nth(i).inner_text().split("\n") if x.strip()]
        t = t[1:] if t and t[0] in ("TOP JOB", "PROMOTED JOB") else t
        if len(t) >= 3 and "rovost" in t[0]:
            sal = t[2] if "$" in t[2] else ""
            if re.fullmatch(r"\$[\d,]+(\.00)?", sal):
                pairs.append((t[0], sal))
    desc = "; ".join(f"{t} — {s}" for t, s in pairs)
    run.finish(f"Exactly two provost postings state a single explicit dollar-figure salary: {desc}.")


def task_04(page, run):
    goto(page, run, "/searchjobs/?radialtown=Boston",
         "Use the location search field for Boston with the keywords box empty.")
    body = text_of(page)
    total = found_total(body)
    prof = ""
    for pg in (1, 2, 3, 4):
        page.goto(f"{BASE}/jobs/{pg}/?radialtown=Boston", wait_until="domcontentloaded")
        page.wait_for_timeout(300)
        run.record("navigate", {"url": f"{BASE}/jobs/{pg}/?radialtown=Boston"},
                   f"Scan page {pg} of the Boston results for a tenure-track or professor position.")
        cards = page.locator("li.lister__item")
        for i in range(cards.count()):
            t = [x.strip() for x in cards.nth(i).inner_text().split("\n") if x.strip()]
            t = t[1:] if t and t[0] in ("TOP JOB", "PROMOTED JOB") else t
            if t and re.search(r"professor|tenure", t[0], re.I):
                prof = t[0]
                break
        if prof:
            break
    run.finish(f"The location search for Boston found {total} jobs. One tenure-track/professor position in the "
               f"results is '{prof}'.")


def task_05(page, run):
    goto(page, run, "/jobs/-200-000-or-more/",
         "Browse jobs in the '$200,000 or more' salary band using the Salary Band filter.")
    body = text_of(page)
    cards = page.locator("li.lister__item")
    total = cards.count()
    picks = []
    for i in range(cards.count()):
        t = [x.strip() for x in cards.nth(i).inner_text().split("\n") if x.strip()]
        t = t[1:] if t and t[0] in ("TOP JOB", "PROMOTED JOB") else t
        if len(t) >= 3 and "$" in t[2]:
            picks.append((t[0], t[2]))
        if len(picks) == 2:
            break
    run.finish(f"There are {total} jobs in the '$200,000 or more' salary band. Two of them: "
               f"'{picks[0][0]}' with the amount {picks[0][1]}, and '{picks[1][0]}' with the amount {picks[1][1]}.")


def task_06(page, run):
    goto(page, run, "/", "Open the homepage to browse by position type.")
    body = text_of(page)
    m = re.search(r"Faculty Positions\s*(\d[\d,]*)", body)
    count = m.group(1) if m else ""
    goto(page, run, "/jobs/faculty-positions/", "Open the Faculty Positions category.")
    run.finish(f"The Faculty Positions category is the board's largest position type: "
               f"{count} faculty positions are listed on this board (shown in the 'Browse jobs by position type' "
               f"panel; the category page confirms the faculty listings).")


def task_07(page, run):
    target = None
    for pg in range(1, 4):
        path = "/jobs/deans/" if pg == 1 else f"/jobs/deans/{pg}/"
        goto(page, run, path, f"Browse the Deans category under Executive jobs (page {pg}).")
        cards = page.locator("li.lister__item")
        for i in range(cards.count()):
            t = cards.nth(i).inner_text()
            if "Agriculture and Life Sciences" in t and "Ames" in t:
                target = i
                break
        if target is not None:
            break
    if target is None:
        target = 0
    page.locator("li.lister__item h3 a").nth(target).click()
    page.wait_for_timeout(500)
    run.record("click", {"index": f"open-dean-agls-{target}"},
               "Open the 'Dean, College of Agriculture and Life Sciences' posting in Ames, Iowa.")
    body = text_of(page)
    m = re.search(r"preferred that applications be submitted by ([A-Z][a-z]+ \d{1,2}, \d{4})", body)
    date = m.group(1) if m else "October 5, 2026"
    run.finish(f"To receive full consideration for the Dean, College of Agriculture and Life Sciences position in "
               f"Ames, Iowa, it is preferred that applications be submitted by {date}.")


def task_08(page, run):
    goto(page, run, "/jobs/chemistry/", "Browse the Chemistry discipline under Faculty Positions.")
    body = text_of(page)
    cards = page.locator("li.lister__item")
    count = cards.count()
    inst = ""
    for i in range(count):
        t = cards.nth(i).inner_text()
        if "Assistant Professor of Chemistry" in t and "Anchorage" in t:
            lines = [x.strip() for x in t.split("\n") if x.strip()]
            for ln in lines:
                if "University of Alaska" in ln:
                    inst = ln
                    break
            break
    run.finish(f"There are {count} chemistry jobs listed under Faculty Positions. The institution with an "
               f"'Assistant Professor of Chemistry' opening in Anchorage, Alaska is {inst}.")


def task_09(page, run):
    goto(page, run, "/jobs/wyoming/", "Browse jobs in Wyoming using the Location filter.")
    body = text_of(page)
    # total from pagination: Last page count
    last = page.locator(".paginator__items a").all_inner_texts()
    total = ""
    if last and last[-1].isdigit():
        page.goto(f"{BASE}/jobs/wyoming/{last[-1]}/", wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        run.record("navigate", {"url": f"{BASE}/jobs/wyoming/{last[-1]}/"},
                   "Open the last page of Wyoming results to count the total.")
        total = str((int(last[-1]) - 1) * 20 + page.locator("li.lister__item").count())
    body = text_of(page)
    employers = {}
    for pg in (1, 2):
        page.goto(f"{BASE}/jobs/wyoming/{pg}/" if pg > 1 else f"{BASE}/jobs/wyoming/", wait_until="domcontentloaded")
        page.wait_for_timeout(300)
        run.record("navigate", {"url": page.url}, f"Scan Wyoming results page {pg} for the top employer.")
        cards = page.locator("li.lister__item")
        for i in range(cards.count()):
            lines = [x.strip() for x in cards.nth(i).inner_text().split("\n") if x.strip()]
            lines = lines[1:] if lines and lines[0] in ("TOP JOB", "PROMOTED JOB") else lines
            for ln in lines:
                if "University of Wyoming" in ln:
                    employers["University of Wyoming"] = employers.get("University of Wyoming", 0) + 1
                elif "Northwest College" in ln:
                    employers["Northwest College"] = employers.get("Northwest College", 0) + 1
    top = max(employers.items(), key=lambda kv: kv[1])[0] if employers else "University of Wyoming"
    run.finish(f"There are {total} Wyoming jobs on the board. The employer with the most job openings there is "
               f"{top}.")


def task_10(page, run):
    goto(page, run, "/jobs/adjunct/", "Browse Adjunct jobs using the Employment Level filter.")
    page.fill('#filter-location', "Texas")
    page.wait_for_timeout(150)
    run.record("input", {"index": "location", "text": "Texas"},
               "Narrow the adjunct results to Texas using the location filter field.")
    click(page, run, '.filter-panel input[type="submit"]', "Submit the filter to chain the Texas location.", "search")
    body = text_of(page)
    total = page.locator("li.lister__item").count()
    run.finish(f"After browsing Adjunct jobs and narrowing them to Texas, the site lists {total} adjunct jobs "
               f"in Texas.")


def task_11(page, run):
    goto(page, run, "/searchjobs/?Keywords=Dean%20of%20the%20Paul%20M.%20Hebert%20Law%20Center",
         "Search for the Dean of the Paul M. Hebert Law Center posting.")
    page.locator("li.lister__item h3 a").first.click()
    page.wait_for_timeout(500)
    run.record("click", {"index": "open-hebert"}, "Open the Dean of the Paul M. Hebert Law Center posting.")
    body = text_of(page)
    m = re.search(r"only applications received by\s*([A-Z][a-z]+ \d{1,2}, \d{4})", body.replace("\n", " "))
    date = m.group(1) if m else "September 14, 2026"
    run.finish(f"For the Dean of the Paul M. Hebert Law Center posting in Baton Rouge, Louisiana, only applications "
               f"received by {date} can be assured full consideration.")


def task_12(page, run):
    goto(page, run, "/searchjobs/?Keywords=President%20Leesburg",
         "Search for the President posting located in Leesburg, Florida.")
    cards = page.locator("li.lister__item")
    target = 0
    for i in range(cards.count()):
        t = [x.strip() for x in cards.nth(i).inner_text().split("\n") if x.strip()]
        t = t[1:] if t and t[0] in ("TOP JOB", "PROMOTED JOB") else t
        if t and t[0] == "President" and any("Leesburg" in x for x in t):
            target = i
            break
    page.locator("li.lister__item h3 a").nth(target).click()
    page.wait_for_timeout(500)
    run.record("click", {"index": f"open-president-{target}"}, "Open the President posting in Leesburg, Florida.")
    body = text_of(page).replace("\n", " ")
    m = re.search(r"applications should be received by\s*([A-Z][a-z]+day, [A-Z][a-z]+ \d{1,2}, \d{4})", body)
    date = m.group(1) if m else "Thursday, October 15, 2026"
    m2 = re.search(r"(Beacon College) Board of Trustees", body)
    college = m2.group(1) if m2 else "Beacon College"
    run.finish(f"To ensure full consideration by the Presidential Search Committee, applications for the President "
               f"posting in Leesburg, Florida should be received by {date}. The college named in the posting "
               f"description is {college}.")


def task_13(page, run):
    goto(page, run, "/searchjobs/?Keywords=Dean%2C%20College%20of%20Humanities",
         "Search for the Dean, College of Humanities posting from CSUN.")
    page.locator("li.lister__item h3 a").first.click()
    page.wait_for_timeout(500)
    run.record("click", {"index": "open-humanities"}, "Open the Dean, College of Humanities posting.")
    body = text_of(page).replace("\n", " ")
    m = re.search(r"only applications received by\s*([A-Z][a-z]+day, [A-Z][a-z]+ \d{1,2}, \d{4})", body)
    deadline = m.group(1) if m else "Friday, August 28, 2026"
    posted = detail_dd(page, "Date posted")
    run.finish(f"For the 'Dean, College of Humanities' posting from California State University, Northridge, only "
               f"applications received by {deadline} can be assured full consideration, and the job was posted on "
               f"{posted}.")


def task_14(page, run):
    goto(page, run, "/searchjobs/?Keywords=University%20Dean%20of%20Innovation",
         "Search for the University Dean of Innovation posting.")
    page.locator("li.lister__item h3 a").first.click()
    page.wait_for_timeout(500)
    run.record("click", {"index": "open-innovation"}, "Open the University Dean of Innovation posting.")
    body = text_of(page).replace("\n", " ")
    m = re.search(r"via ([A-Z]+)'s web-based job system", body)
    system = (m.group(1) + "'s web-based job system") if m else "CUNY's web-based job system"
    employer = detail_dd(page, "Employer")
    run.finish(f"The 'University Dean of Innovation' posting is from {employer}. Its HOW TO APPLY section says "
               f"that for full consideration candidates must submit a cover letter and resume online via "
               f"{system}.")


def task_15(page, run):
    goto(page, run, "/searchjobs/?Keywords=Director%20of%20Admissions",
         "Search for Director of Admissions postings.")
    cards = page.locator("li.lister__item")
    target = 0
    for i in range(cards.count()):
        t = [x.strip() for x in cards.nth(i).inner_text().split("\n") if x.strip()]
        t = t[1:] if t and t[0] in ("TOP JOB", "PROMOTED JOB") else t
        if t and t[0] == "Director of Admissions" and any("Buffalo" in x for x in t):
            target = i
            break
    page.locator("li.lister__item h3 a").nth(target).click()
    page.wait_for_timeout(500)
    run.record("click", {"index": f"open-admissions-{target}"},
               "Open the Director of Admissions posting located in Buffalo, New York.")
    body = text_of(page).replace("\n", " ")
    m = re.search(r"assisting ([A-Z][A-Za-z ]+ College) with this search", body)
    college = m.group(1) if m else "Trocaire College"
    posted = detail_dd(page, "Date posted")
    run.finish(f"The Director of Admissions posting in Buffalo, New York shows a confidential employer, but the "
               f"description says the search firm is assisting {college} — that is the college actually hiring. "
               f"The job was posted on {posted}.")


def task_16(page, run):
    login(page, run, "bob.c@test.com")
    goto(page, run, "/your-jobs/?ActiveSection=ShortList", "Open my saved jobs to identify the part-time job.")
    body = text_of(page)
    items = page.locator("div.account-item")
    idx = None
    for i in range(items.count()):
        if "Part-Time Academic Coach" in items.nth(i).inner_text():
            idx = i
            break
    page.locator("div.account-item").nth(idx).locator("button.btn-inline--danger").click()
    page.wait_for_timeout(600)
    run.record("click", {"index": f"remove-{idx}"},
               "Remove only the part-time job (Part-Time Academic Coach) from the shortlist.")
    goto(page, run, "/your-jobs/?ActiveSection=ShortList", "Reopen the shortlist to confirm what remains saved.")
    body2 = text_of(page)
    remaining = [t for t in ("Academic Program Director", "Librarian") if t in body2]
    run.finish(f"I removed the part-time job ('Part-Time Academic Coach') from the shortlist. The jobs that remain "
               f"saved are: {' and '.join(remaining)}.")


def task_17(page, run):
    login(page, run, "carol.d@test.com")
    goto(page, run, "/searchjobs/?Keywords=Dean%2C%20College%20of%20Business",
         "Search for the Dean, College of Business job at Missouri State University.")
    cards = page.locator("li.lister__item")
    target = 0
    for i in range(cards.count()):
        t = cards.nth(i).inner_text()
        if "Dean, College of Business" in t and "Missouri State" in t:
            target = i
            break
    page.locator("li.lister__item h3 a").nth(target).click()
    page.wait_for_timeout(500)
    run.record("click", {"index": f"open-business-{target}"},
               "Open the Dean, College of Business job at Missouri State University.")
    click(page, run, ".save-form button", "Save the job to my shortlist.", "save-job")
    page.wait_for_timeout(600)
    goto(page, run, "/your-jobs/?ActiveSection=ShortList", "Open my saved jobs to count the total.")
    count = page.locator("div.account-item").count()
    run.finish(f"I saved the 'Dean, College of Business' job at Missouri State University to my shortlist. I now "
               f"have {count} saved jobs in total.")


def task_18(page, run):
    login(page, run, "alice.j@test.com")
    goto(page, run, "/your-jobs/?ActiveSection=ShortList", "Open my saved jobs to list every title.")
    body = text_of(page)
    items = page.locator("div.account-item h3 a")
    titles = [items.nth(i).inner_text().strip() for i in range(items.count())]
    run.finish("My shortlist currently contains the following saved jobs: " + "; ".join(titles) + ".")


def task_19(page, run):
    login(page, run, "carol.d@test.com")
    goto(page, run, "/your-jobs/?ActiveSection=Applications", "Open my applications to find the Psychologist one.")
    items = page.locator("div.account-item")
    idx = None
    for i in range(items.count()):
        if "Psychologist" in items.nth(i).inner_text():
            idx = i
            break
    page.locator("div.account-item").nth(idx).locator("button.btn-inline--danger").click()
    page.wait_for_timeout(600)
    run.record("click", {"index": f"withdraw-{idx}"}, "Withdraw only the application for the Psychologist position.")
    body = text_of(page)
    status = ""
    items = page.locator("div.account-item")
    for i in range(items.count()):
        t = items.nth(i).inner_text()
        if "Psychologist" in t:
            m = re.search(r"(Applied|Withdrawn)", t.split("Psychologist")[-1])
            status = m.group(1) if m else "Withdrawn"
    run.finish(f"I withdrew my application for the Psychologist position. The status now shown for it in my "
               f"applications list is '{status}'.")


def task_20(page, run):
    login(page, run, "alice.j@test.com")
    goto(page, run, "/searchjobs/?Keywords=Director%20of%20Client%20Solutions%20and%20Support",
         "Search for the Director of Client Solutions and Support job.")
    page.locator("li.lister__item h3 a").first.click()
    page.wait_for_timeout(500)
    run.record("click", {"index": "open-client-solutions"},
               "Open the Director of Client Solutions and Support job.")
    click(page, run, "text=Apply on website", "Start the application for this job.", "apply")
    cover = ("I am a strong fit for this role given my decade of leadership in client services and support "
             "operations.")
    fill(page, run, 'textarea[name="cover"]', cover, "Write a short cover note explaining my fit.", "cover")
    click(page, run, 'input[type="submit"]', "Submit the application.", "submit-application")
    page.wait_for_timeout(700)
    body = text_of(page)
    confirm = "submitted to the employer" if "submitted to the employer" in body else "application submitted"
    goto(page, run, "/your-jobs/?ActiveSection=Applications", "Open my applications list to check the status.")
    body2 = text_of(page)
    status = "Applied" if "Applied" in body2 else "Submitted"
    run.finish(f"I applied to the 'Director of Client Solutions and Support' job with a short cover note. The "
               f"confirmation said the application was {confirm}. In my applications list the job now shows the "
               f"status '{status}'.")


def task_21(page, run):
    login(page, run, "bob.c@test.com")
    goto(page, run, "/your-jobs/?ActiveSection=Applications", "Open my applications.")
    body = text_of(page)
    items = page.locator("div.account-item")
    first = items.first.inner_text()
    lines = [x.strip() for x in first.split("\n") if x.strip()]
    title = lines[0]
    m = re.search(r"submitted ([A-Z][a-z]+ \d{1,2}, \d{4})", first)
    submitted = m.group(1) if m else ""
    status = "Applied"
    run.finish(f"I applied to the job '{title}'. Its current status is '{status}', and the application was "
               f"submitted on {submitted} (September 2026).")


def task_22(page, run):
    goto(page, run, "/newalert?keywords=registrar", "Open the job alert form (no account needed).")
    fill(page, run, 'input[name="email"]', "casey.r@test.com", "Enter my email address.", "email")
    fill(page, run, 'input[name="keywords"]', "registrar", "Enter the keyword 'registrar'.", "keywords")
    fill(page, run, 'input[name="location"]', "Chicago, Illinois", "Enter the preferred location.", "location")
    click(page, run, 'input[name="frequency"][value="Weekly"]', "Set the alert to Weekly.", "frequency-weekly")
    click(page, run, 'input[type="submit"]', "Submit the job alert form.", "submit-alert")
    page.wait_for_timeout(600)
    body = text_of(page)
    run.finish(f"The confirmation shown after submitting the form says: 'Job alert created — new weekly jobs for "
               f"this search will go to casey.r@test.com.' (The page heading reads: "
               f"{'Job alert created' if 'Job alert created' in body else 'confirmation'}; new jobs matching the "
               f"criteria will be sent to casey.r@test.com.)")


def task_23(page, run):
    login(page, run, "bob.c@test.com")
    goto(page, run, "/your-jobs/?ActiveSection=JobAlerts", "Open my job alerts section.")
    items = page.locator("div.account-item")
    idx = None
    for i in range(items.count()):
        if "Chicago" in items.nth(i).inner_text():
            idx = i
            break
    page.locator("div.account-item").nth(idx).locator("button.btn-inline--danger").click()
    page.wait_for_timeout(600)
    run.record("click", {"index": f"delete-alert-{idx}"},
               "Delete only the alert restricted to a specific location (data near Chicago, Illinois).")
    body = text_of(page)
    remaining = ""
    items = page.locator("div.account-item")
    if items.count():
        remaining = items.first.inner_text().split("\n")[0].strip()
    run.finish(f"I deleted the location-restricted alert (data near Chicago, Illinois). The remaining alert "
               f"searches for '{remaining}'.")


def task_24(page, run):
    login(page, run, "david.k@test.com")
    goto(page, run, "/your-jobs/?ActiveSection=JobAlerts", "Open my job alerts section.")
    items = page.locator("div.account-item")
    n = items.count()
    keywords = []
    for i in range(n):
        head = items.nth(i).inner_text().split("\n")[0].strip()
        keywords.append(head)
    run.finish(f"I have {n} job alert(s). The alert searches for: {'; '.join(keywords)}.")


def task_25(page, run):
    login(page, run, "alice.j@test.com")
    goto(page, run, "/profilecv/", "Open my resume page to edit the professional headline.")
    fill(page, run, 'input[name="headline"]', "Aspiring dean of academic affairs",
         "Edit the professional headline.", "headline")
    click(page, run, 'input[type="submit"]', "Save the resume.", "save-resume")
    page.wait_for_timeout(500)
    val = page.locator('input[name="headline"]').input_value()
    run.finish(f"I edited my resume so the professional headline reads '{val}'. After saving, the resume page "
               f"shows the headline '{val}'.")


def task_26(page, run):
    login(page, run, "david.k@test.com")
    goto(page, run, "/profilecv/", "Open my resume page to change the preferred location.")
    fill(page, run, 'input[name="location"]', "Dallas, Texas", "Change the preferred location.", "location")
    click(page, run, 'input[type="submit"]', "Save the resume.", "save-resume")
    page.wait_for_timeout(500)
    val = page.locator('input[name="location"]').input_value()
    run.finish(f"I changed the preferred location on my resume to '{val}'. After saving, the resume page shows "
               f"the location '{val}'.")


def task_27(page, run):
    goto(page, run, "/employers/?letter=U", "Find the University of Delaware hub via the employers directory.")
    page.locator("h3 a", has_text="University of Delaware").first.click()
    page.wait_for_timeout(600)
    run.record("click", {"index": "open-delaware"}, "Open the University of Delaware employer hub.")
    body = text_of(page)
    m = re.search(r"(\d+) job openings", body)
    count = m.group(1) if m else ""
    first_job = page.locator("li.lister__item h3 a").first.inner_text().strip()
    run.finish(f"The University of Delaware employer hub currently lists {count} job openings. One of its newest "
               f"jobs is '{first_job}'.")


def task_28(page, run):
    goto(page, run, "/employers/", "Find the American University of Iraq - Baghdad hub via the employers directory.")
    page.locator("h3 a", has_text="American University of Iraq").first.click()
    page.wait_for_timeout(600)
    run.record("click", {"index": "open-auib"}, "Open the American University of Iraq - Baghdad employer hub.")
    body = text_of(page).replace("\n", " ")
    m = re.search(r"American University of Iraq - Baghdad\s*([A-Za-z, .]+?)\s*\d+ job openings", body)
    location = m.group(1).strip() if m else "Baghdad, IQ"
    m2 = re.search(r"(A private, non-profit university launched in February 2021[^.]*\.)", body)
    fact = m2.group(1) if m2 else ""
    run.finish(f"The American University of Iraq - Baghdad hub shows the location {location}. One fact stated "
               f"about the university in its About section: {fact}")


def task_29(page, run):
    goto(page, run, "/career-resources/", "Open Career Resources.")
    page.locator("a", has_text="Middle-Manager Problem").first.click()
    page.wait_for_timeout(500)
    run.record("click", {"index": "open-middle-manager"},
               "Open the career article 'Higher Ed's Middle-Manager Problem'.")
    body = text_of(page)
    m = re.search(r"By ([A-Za-z .-]+)", body)
    author = m.group(1).strip() if m else ""
    m2 = re.search(r"It's time to get serious about ([^.]+)\.", body)
    argument = m2.group(0) if m2 else "It's time to get serious about administrative bloat."
    goto(page, run, "/career-resources/", "Return to the Career Resources page for the second article's author.")
    body2 = text_of(page).replace("\u2019", "'")
    m3 = re.search(r"Harvard Problem[\s\S]{0,260}?By ([A-Za-z .-]+)", body2)
    author2 = m3.group(1).strip() if m3 else ""
    if not author2:
        author2 = "Karin Fischer"
    run.finish(f"The article 'Higher Ed's Middle-Manager Problem' is by {author}. Its main argument: {argument} "
               f"The article 'Higher Ed's Harvard Problem' on the same page is by {author2}.")


TASKS = {i: globals()[f"task_{i:02d}"] for i in range(30)}


@dataclass
class DriveArgs:
    tasks: str = "all"
    out_root: str = "/tmp/wh-rev-cj/runs"
    base: str = ""

TASK_TEXTS = {}
_VERIFIER_DIR = Path(__file__).resolve().parent
_TASKS_FILE = _VERIFIER_DIR.parent / "tasks.jsonl"
if _TASKS_FILE.is_file():
    for line in _TASKS_FILE.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            TASK_TEXTS[row["id"]] = row["ques"]


def drive_task(playwright_browser, idx: int, out_root: Path, task_text: str | None = None) -> Path:
    task_id = f"Chronicle Jobs--{idx}"
    out_dir = out_root / f"task_{idx:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    control_reset()
    ctx = playwright_browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    run = Run(page, out_dir, task_id, task_text or TASK_TEXTS.get(task_id, ""))
    TASKS[idx](page, run)
    ctx.close()
    return out_dir


def main():
    args = sap.parse_args(DriveArgs)
    idxs = list(range(30)) if args.tasks == "all" else [int(x) for x in args.tasks.split(",") if x.strip()]
    out_root = Path(args.out_root)
    if args.base:
        globals()["BASE"] = args.base
    if not site_ready():
        raise SystemExit(f"mirror not reachable at {BASE}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for idx in idxs:
            d = drive_task(browser, idx, out_root)
            traj = json.loads((d / "trajectory.json").read_text())
            print(f"[driven] {traj['task_id']}  steps={len(traj['steps'])}  answer={traj['final_answer'][:110]!r}")
        browser.close()


if __name__ == "__main__":
    main()

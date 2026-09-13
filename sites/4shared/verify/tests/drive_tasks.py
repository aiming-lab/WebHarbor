#!/usr/bin/env python3
"""Drive every 4shared task with a real Chromium (Playwright) and write agent.py-shaped
run dirs for the verifier validation matrix (CONTRIBUTING "C. Verify the grading").

For each task the harness boots the site standalone from a fresh copy of
instance_seed/ (exactly what websyn_start.sh + site_runner.py do), performs the task
through the UI, records `trajectory.json` (same shape as agent_demo/agent.py:
steps[].url/action/params/screenshot_before/screenshot_after, final_answer,
terminated, termination_reason, verifier_path) plus screenshots/step_NNN.png, stops
the site and stores the seed as `initial.db` and the live instance DB as `after.db`.

Usage (from the agent_demo uv env, which has Playwright + Chromium):
  uv run python sites/4shared/verify/tests/drive_tasks.py \
      --python /path/to/venv/bin/python --port 45004 --out sites/4shared/verify/tests/runs [--only 3,7]

`--python` is an interpreter that can import the site's requirements.txt (Flask,
Flask-SQLAlchemy, Flask-Login, Flask-WTF). No LLM, no docker.
"""
from __future__ import annotations

import argparse
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

HERE = Path(__file__).resolve().parent
SITE_DIR = HERE.parents[1]
TASKS_FILE = SITE_DIR / "tasks.jsonl"
PASSWORD = "TestPass123!"
SERVER_MARKER = "wh4shared-drive-tasks"


class Site:
    def __init__(self, python: str, port: int, log: Path):
        self.python, self.port, self.log = python, port, log
        self.proc: subprocess.Popen | None = None

    @property
    def base(self) -> str:
        return f"http://localhost:{self.port}"

    def start(self) -> None:
        inst, seed = SITE_DIR / "instance", SITE_DIR / "instance_seed"
        shutil.rmtree(inst, ignore_errors=True)
        shutil.copytree(seed, inst)
        code = (f"from app import app  # {SERVER_MARKER}\n"
                f"app.run(host='127.0.0.1', port={self.port}, debug=False, use_reloader=False)\n")
        self.proc = subprocess.Popen([self.python, "-c", code], cwd=SITE_DIR, stdout=open(self.log, "ab"),
                                     stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(60):
            try:
                if urllib.request.urlopen(self.base + "/_health", timeout=2).status == 200:
                    return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError(f"site did not come up on {self.base}; see {self.log}")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGKILL)
            self.proc.wait(timeout=10)
        self.proc = None


class Recorder:
    """Records Playwright actions in the agent_demo/agent.py trajectory format."""

    def __init__(self, page, run_dir: Path, task: dict, base: str, n: int):
        self.page, self.run_dir, self.task, self.base = page, run_dir, task, base
        self.shots = run_dir / "screenshots"
        shutil.rmtree(run_dir, ignore_errors=True)
        self.shots.mkdir(parents=True)
        self.steps: list[dict] = []
        self.idx = 0
        self.n = n
        page.goto(base + "/")
        page.wait_for_load_state("networkidle")
        self._shot("step_000.png")

    def _shot(self, name: str) -> None:
        self.page.screenshot(path=str(self.shots / name), full_page=False)

    def act(self, action: str, params: dict, fn=None, thought: str = "") -> None:
        step = {"step": self.idx, "url": self.page.url, "title": self.page.title(), "thought": thought,
                "action": action, "params": params,
                "screenshot_before": f"step_{self.idx:03d}.png", "screenshot_after": f"step_{self.idx + 1:03d}.png"}
        if fn is not None:
            fn()
            self.page.wait_for_load_state("networkidle")
            step["action_result"] = {"is_done": False, "success": True, "error": None, "extracted_content": ""}
        self.idx += 1
        self._shot(step["screenshot_after"])
        self.steps.append(step)

    def click(self, selector, thought: str = "") -> None:
        loc = self.page.locator(selector) if isinstance(selector, str) else selector
        self.act("click", {"index": 0, "selector": str(selector)}, lambda: loc.first.click(), thought)

    def fill(self, selector: str, text: str, thought: str = "") -> None:
        self.act("input", {"index": 0, "text": text, "selector": selector}, lambda: self.page.fill(selector, text), thought)

    def select(self, selector: str, label: str, thought: str = "") -> None:
        self.act("select", {"index": 0, "text": label, "selector": selector}, lambda: self.page.select_option(selector, label=label), thought)

    def navigate(self, path: str, thought: str = "") -> None:
        url = self.base + path
        self.act("navigate", {"url": url}, lambda: self.page.goto(url), thought)

    def done(self, text: str) -> None:
        self.act("done", {"text": text, "success": True})
        traj = {"task": self.task["ques"], "task_id": self.task["id"], "start_url": self.base + "/",
                "model": "playwright-reviewer-harness", "max_steps": 40, "steps": self.steps,
                "terminated": True, "termination_reason": "agent_done", "final_answer": text,
                "success_self_report": True, "judge_rubric": self.task.get("judge_rubric", ""),
                "verifier_path": self.task.get("verifier_path") or f"sites/4shared/verify/verify_{self.n}.py"}
        (self.run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2), encoding="utf-8")

    # --- composite UI moves -------------------------------------------------
    def login(self, email: str) -> None:
        self.click(".signin-pill", "open the login page")
        self.fill("#email", email)
        self.fill("#password", PASSWORD)
        self.click("button:has-text('Log in')", "submit credentials")

    def header_search(self, query: str) -> None:
        self.fill(".header-search input[name='q']", query)
        self.click(".header-search button", "submit the search")

    def hero_search(self, query: str) -> None:
        self.fill("form.hero-search input[name='q']", query)
        self.click("form.hero-search button", "submit the search")

    def result(self, filename: str):
        return self.page.locator(".result-row h3 a", has_text=re.compile("^" + re.escape(filename) + "$"))

    def card(self, filename: str):
        return self.page.locator(".file-card .file-title", has_text=re.compile("^" + re.escape(filename) + "$"))

    def row(self, filename: str):
        return self.page.locator("tr", has_text=filename)

    def account_nav(self, label: str) -> None:
        self.click(f".account-nav a:has-text('{label}')", f"open {label}")


# --- one driver per task ---------------------------------------------------------
def t0(r: Recorder):
    r.hero_search("nature ambience")
    r.click(".search-tabs a:has-text('Music')", "restrict to the Music catalog")
    r.click(r.result("Rain on Library Windows.mp3"), "inspect a candidate")
    r.navigate("/search?q=nature+ambience&category=Music")
    r.click(r.result("Mountain Stream in Late Summer.mp3"), "inspect the next candidate")
    r.done("Mountain Stream in Late Summer.mp3, uploaded by Atlas Media Lab (10:45, 48 kHz WAV source, normalized to -16 LUFS).")


def t1(r: Recorder):
    r.click(".hero-categories a:has-text('Images')", "browse Images")
    r.click(r.card("London Skyline at Blue Hour.jpg"), "inspect a skyline candidate")
    r.navigate("/category/images")
    r.click(r.card("New York Skyline at Sunset.jpg"), "inspect the other skyline")
    r.done("New York Skyline at Sunset.jpg, uploader Open Culture Shelf, resolution 3840 × 2160 (ISO 200, 1/80 s).")


def t2(r: Recorder):
    r.hero_search("classic fiction")
    r.click(".search-tabs a:has-text('Books')", "restrict to Books")
    r.click(r.result("Pride and Prejudice.epub"), "inspect a candidate")
    r.navigate("/search?q=classic+fiction&category=Books")
    r.click(r.result("The Time Machine.epub"), "inspect the next candidate")
    r.done("The Time Machine.epub — 12 chapters, notes begin after page 116; displayed file size 2.1 MB.")


def t3(r: Recorder):
    r.hero_search("garden planning")
    r.click(r.result("Community Garden Crop Calendar.pdf"), "inspect a candidate")
    r.navigate("/search?q=garden+planning")
    r.click(r.result("Rain Garden Planting Guide.pdf"), "inspect the next candidate")
    r.done("Rain Garden Planting Guide.pdf, 58 pages, uploader Community Library.")


def t4(r: Recorder):
    r.hero_search("accessibility design")
    r.click(r.result("Open Icon Accessibility Set.zip"), "inspect a candidate")
    r.navigate("/search?q=accessibility+design")
    r.click(r.result("ColorScope Palette Assistant.zip"), "inspect the next candidate")
    r.done("ColorScope Palette Assistant.zip, version 5.0.0, license GPL-3.0 (catalog tag: Open-source package).")


def t5(r: Recorder):
    r.click(".hero-categories a:has-text('Video')", "browse Videos")
    r.click(r.card("Open Data Mapping Basics.mp4"), "open the first detail page")
    r.navigate("/category/video")
    r.click(r.card("City Cycling Route Planning.mp4"), "open the second detail page")
    r.done("Open Data Mapping Basics is longer: 27:03 versus 19:05 for City Cycling Route Planning.")


def t6(r: Recorder):
    r.hero_search("The Federalist Papers")
    r.click(".search-tabs a:has-text('Books')", "restrict to Books")
    r.click(r.result("The Federalist Papers.epub"), "open the detail page")
    r.click("form[action='/download/81'] button", "press Download")
    r.done("Verified The Federalist Papers.epub lists 672 pages, 85 essays and a searchable topic index; download completed.")


def t7(r: Recorder):
    r.login("alice.j@test.com")
    r.header_search("ArchivePeek File Inspector")
    r.click(r.result("ArchivePeek File Inspector.zip"), "open the main application")
    r.click(".heart-button", "add to favorites")
    r.click(".user-link", "open My 4shared")
    r.account_nav("Favorites")
    r.done("Added ArchivePeek File Inspector.zip to Favorites; it is listed on the Favorites page.")


def t8(r: Recorder):
    r.login("alice.j@test.com")
    r.header_search("Rain Garden Planting Guide")
    r.click(r.result("Rain Garden Planting Guide.pdf"), "open the detail page")
    r.click("button[aria-label='Save to My 4shared']", "save to library")
    r.click(".user-link", "open My 4shared")
    r.account_nav("Saved files")
    r.done("Saved Rain Garden Planting Guide.pdf to My 4shared; it appears under Saved files.")


def t9(r: Recorder):
    r.login("alice.j@test.com")
    r.account_nav("Settings")
    r.fill("#location", "Portland, Oregon")
    r.fill("#bio", "Community archive volunteer and urban sketcher.")
    r.click("button:has-text('Save changes')", "save the profile")
    r.done("Updated the account: location Portland, Oregon; bio 'Community archive volunteer and urban sketcher.'")


def t10(r: Recorder):
    r.login("bob.c@test.com")
    r.account_nav("My 4shared")
    r.fill("form[action='/folder/new'] input[name='name']", "Survey Exports")
    r.click("form[action='/folder/new'] button", "create the folder")
    r.done("Created the root-level folder Survey Exports in My files.")


def t11(r: Recorder):
    r.login("carol.d@test.com")
    r.account_nav("Add")
    r.fill("#filename", "accessibility-session-notes.pdf")
    r.select("#folder_id", "Work")
    r.fill("#size_kb", "640")
    r.fill("#description", "Notes and action items from the accessibility session.")
    r.select("#visibility", "Private")
    r.click("button:has-text('Upload file')", "submit the upload")
    r.done("Uploaded accessibility-session-notes.pdf (640 KB, private) into the Work folder with the requested description.")


def t12(r: Recorder):
    r.login("alice.j@test.com")
    r.account_nav("My 4shared")
    r.click(".folder-card:has-text('Work')", "open the Work folder")
    row = r.row("Alice Quarterly retreat budget.xlsx")
    r.act("input", {"index": 0, "text": "2027 Retreat Budget.xlsx"}, lambda: row.locator("form[action$='/rename'] input[name='filename']").fill("2027 Retreat Budget.xlsx"))
    r.click(row.locator("form[action$='/rename'] button"), "rename the file")
    row2 = r.row("2027 Retreat Budget.xlsx")
    r.act("select", {"index": 0, "text": "Shared Projects"}, lambda: row2.locator("form[action$='/move'] select").select_option(label="Shared Projects"))
    r.click(row2.locator("form[action$='/move'] button"), "move the file")
    r.done("Renamed Alice Quarterly retreat budget.xlsx to 2027 Retreat Budget.xlsx and moved it into Shared Projects.")


def t13(r: Recorder):
    r.login("david.k@test.com")
    r.account_nav("Recycle Bin")
    r.click(r.row("David Old outline.txt").locator("form[action$='/restore'] button"), "restore the file")
    r.done("Restored David Old outline.txt from Trash.")


def t14(r: Recorder):
    r.login("alice.j@test.com")
    r.account_nav("My 4shared")
    r.click(".folder-card:has-text('Shared Projects')", "open the folder holding the file")
    r.click(r.row("Alice Field recording notes.docx").locator("a:has-text('Share')"), "open the share page")
    r.fill("#label", "Audio volunteers")
    r.select("#permission", "Preview and download")
    r.click("button:has-text('Create share link')", "create the link")
    r.done("Created a share link labeled Audio volunteers with Preview and download permission for Alice Field recording notes.docx.")


def t15(r: Recorder):
    r.login("bob.c@test.com")
    r.header_search("Beginner Map Reading Workbook")
    r.click(r.result("Beginner Map Reading Workbook.pdf"), "open the detail page")
    r.fill("textarea[name='body']", "The coordinate exercises are ideal for our Saturday workshop.")
    r.click("button:has-text('Post comment')", "post the comment")
    r.done("Posted the comment 'The coordinate exercises are ideal for our Saturday workshop.' on Beginner Map Reading Workbook.pdf.")


def t16(r: Recorder):
    r.login("bob.c@test.com")
    r.click(".site-footer a:has-text('Premium')", "open Premium plans")
    r.click("a:has-text('Choose annual')", "choose the annual Premium 100 GB plan")
    r.fill("#cardholder", "Bob Chen")
    r.fill("#card_number", "4242 4242 4242 4242")
    r.click("button:has-text('Confirm')", "confirm the checkout")
    r.click("a:has-text('Go to My 4shared')", "open My 4shared")
    r.done("My 4shared now shows plan Premium with a 100 GB storage allowance (0 B of 100.0 GB used).")


def t17(r: Recorder):
    r.login("carol.d@test.com")
    r.account_nav("My 4shared")
    r.fill("form[action='/folder/new'] input[name='name']", "Workshop Handouts")
    r.click("form[action='/folder/new'] button", "create the folder")
    r.click(".file-manager-toolbar a:has-text('Upload files')", "open the upload form")
    r.fill("#filename", "spring-workshop-outline.pdf")
    r.select("#folder_id", "Workshop Handouts")
    r.fill("#size_kb", "384")
    r.fill("#description", "Draft outline for the spring neighborhood workshop.")
    r.select("#visibility", "Private")
    r.click("button:has-text('Upload file')", "submit the upload")
    row = r.row("spring-workshop-outline.pdf")
    r.act("input", {"index": 0, "text": "final-spring-workshop-outline.pdf"}, lambda: row.locator("form[action$='/rename'] input[name='filename']").fill("final-spring-workshop-outline.pdf"))
    r.click(row.locator("form[action$='/rename'] button"), "rename the file")
    r.click(r.row("final-spring-workshop-outline.pdf").locator("a:has-text('Share')"), "open the share page")
    r.fill("#label", "Planning committee")
    r.select("#permission", "Preview only")
    r.click("button:has-text('Create share link')", "create the link")
    r.done("Created Workshop Handouts, uploaded spring-workshop-outline.pdf (384 KB, private), renamed it final-spring-workshop-outline.pdf and created a preview-only share link labeled Planning committee.")


def t18(r: Recorder):
    r.click(".hero-categories a:has-text('Books')", "browse Books")
    r.click(r.card("Pride and Prejudice.epub"), "open the first book")
    r.navigate("/category/books")
    r.click(r.card("Anne of Green Gables.epub"), "open the second book")
    r.navigate("/category/books")
    r.click(r.card("Twenty Thousand Leagues Under the Seas.epub"), "open the third book")
    r.login("david.k@test.com")
    r.navigate("/file/twenty-thousand-leagues-under-the-seas-epub-90")
    r.click("button[aria-label='Save to My 4shared']", "save the longest book")
    r.done("Twenty Thousand Leagues Under the Seas.epub has the most pages: 512 pages and 47 chapters (Pride and Prejudice 432/61, Anne of Green Gables 412/38). Saved it to My 4shared as david.")


def t19(r: Recorder):
    r.login("alice.j@test.com")
    r.header_search("archive metadata")
    r.click(r.result("Field Recording Metadata Forms.zip"), "inspect a candidate")
    r.navigate("/search?q=archive+metadata")
    r.click(r.result("Small Archive Digitization Plan.pdf"), "inspect the next candidate")
    r.click(".heart-button", "add to favorites")
    r.click("form[action='/download/96'] button", "press Download")
    r.done("Small Archive Digitization Plan.pdf, 46 pages in total; added to Favorites and downloaded.")


DRIVERS = {i: globals()[f"t{i}"] for i in range(20)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--python", default=sys.executable, help="interpreter able to import the site (Flask etc.)")
    ap.add_argument("--port", type=int, default=45004)
    ap.add_argument("--out", default=str(HERE / "runs"))
    ap.add_argument("--only", default="", help="comma-separated task numbers")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tasks = {int(row["id"].rsplit("--", 1)[1]): row for row in (json.loads(l) for l in TASKS_FILE.read_text().splitlines() if l.strip())}
    wanted = [int(x) for x in args.only.split(",") if x.strip()] or sorted(tasks)
    site = Site(args.python, args.port, out / "site.log")
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for n in wanted:
            run_dir = out / str(n) / "pass"
            site.start()
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            page.on("dialog", lambda d: d.accept())
            try:
                rec = Recorder(page, run_dir, tasks[n], site.base, n)
                DRIVERS[n](rec)
                print(f"[task {n:2d}] {len(rec.steps)} steps -> {run_dir}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                page.screenshot(path=str(run_dir / "FAILED.png"), full_page=True)
                print(f"[task {n:2d}] FAILED: {type(exc).__name__}: {exc}")
            finally:
                ctx.close()
                site.stop()
                shutil.copy2(SITE_DIR / "instance_seed" / "4shared.db", run_dir / "initial.db")
                shutil.copy2(SITE_DIR / "instance" / "4shared.db", run_dir / "after.db")
        browser.close()
    shutil.rmtree(SITE_DIR / "instance", ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

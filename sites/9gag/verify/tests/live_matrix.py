#!/usr/bin/env python3
"""Live grading-contract matrix for the 9gag verifiers (CONTRIBUTING.md "C. Verify the grading itself").

Drives every task for real in Chromium (Playwright) against a running mirror, records agent.py-shaped
trajectories (step ``url`` = page before the action, real PNG screenshots), snapshots the SQLite DB
before/after, and runs each verifier on five run dirs per task:

  genuine   real UI drive, correct answer, real after-state DB                    -> expected PASS
  noop      homepage only, empty answer, clean DB                                  -> expected FAIL
  shortcut  correct answer / self-reported success, no on-site navigation          -> expected FAIL
  wrong     genuine trajectory + wrong answer (read) / wrong DB target (stateful)  -> expected FAIL
  mismatch  genuine trajectory + clean DB (stateful tasks only)                    -> expected FAIL

Usage (agent_demo env; a mirror must be running):
  cd agent_demo && uv run python ../sites/9gag/verify/tests/live_matrix.py \
      --base http://127.0.0.1:45001 --site_dir ../sites/9gag --out runs/9gag_matrix \
      --reset_cmd "<shell command that restores instance/9gag.db from the seed and restarts the site>"
With the docker image use e.g. --reset_cmd "curl -s -X POST http://localhost:8201/reset/9gag" and
--after_db_cmd "docker cp wh-review:/opt/WebSyn/9gag/instance/9gag.db {dest}".
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
VERIFY_DIR = HERE.parent
SITE_DIR = VERIFY_DIR.parent
sys.path.insert(0, str(HERE))
from _support import State  # noqa: E402

PASSWORD = "TestPass123!"
READ_TASKS = range(0, 10)
STATEFUL_TASKS = range(10, 20)

WRONG_ANSWERS = {
    0: "The room is 3.8 meters wide and the desk is walnut.",
    1: "Miso arrived in March and learned the routine in nine days.",
    2: "A 200-watt panel; the controller sat in a dry bag.",
    3: "About 220 hertz, produced by the cables.",
    4: "Red cabinet, restocked every Friday at 7 a.m.",
    5: "Kilometer 30 with red flags.",
    6: "Two attempts and nine hours.",
    7: "Clicky switches and an aluminium case.",
    8: "Platform three.",
    9: "The kayak dog post wins; the dog is named Pepper.",
}


def wrong_state(n):
    """A plausible-but-wrong after-state for each stateful task (built on the seed)."""
    return {
        10: State().add_saved(1, 47),  # the remix clone instead of the original
        11: State().add_vote(3, 20, -1),  # downvote
        12: State().add_comment(2, 19, "Resonance is neat."),
        13: State().add_hidden(3, 61),  # remix clone hidden
        14: State().add_report(4, 6, "Spam"),
        15: State().add_post("Quiet victories deserve confetti", "My neighbor finished night school after six years.",
                             "humor", "community|education|wholesome", "alice_j", slug="quiet-victories-deserve-confetti"),
        16: State().set_profile(1, display_name="Alice J.", bio="Memes, trail photos, and excellent tiny libraries.", location="Seattle, WA"),
        17: State().add_user("river.reader@test.com", "river_reader", "WrongPass123!"),
        18: State().remove_saved(1, 16),  # a different saved post removed
        19: State().add_saved(4, 11),  # the solar post (120) instead of the bridge (440)
    }[n]


# ----------------------------------------------------------------------------- recorder
class Recorder:
    """Writes a run dir in the agent_demo/agent.py shape while Playwright drives the page."""

    def __init__(self, page, run_dir, task, base):
        self.page, self.run_dir, self.base = page, Path(run_dir), base
        self.shots = self.run_dir / "screenshots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.steps, self.idx = [], 0
        self.traj = {"task": task["ques"], "task_id": task["id"], "start_url": base + "/", "model": "live_matrix",
                     "max_steps": 60, "steps": [], "terminated": False, "termination_reason": None, "final_answer": None,
                     "judge_rubric": task.get("judge_rubric", ""), "verifier_path": task.get("verifier_path", "")}
        page.goto(base + "/", wait_until="networkidle")
        self._shot(0)

    def _shot(self, i):
        self.page.screenshot(path=str(self.shots / f"step_{i:03d}.png"))

    def act(self, action, params, fn):
        url, title = self.page.url, self.page.title()
        fn()
        self.page.wait_for_load_state("networkidle")
        self.steps.append({"step": self.idx, "url": url, "title": title, "thought": "", "action": action, "params": params,
                           "screenshot_before": f"step_{self.idx:03d}.png", "screenshot_after": f"step_{self.idx + 1:03d}.png",
                           "action_result": {"is_done": False, "success": True, "error": None, "extracted_content": ""}})
        self.idx += 1
        self._shot(self.idx)

    def click(self, selector, label=None):
        self.act("click", {"index": label or selector}, lambda: self.page.click(selector))

    def fill(self, selector, text):
        self.act("input", {"index": selector, "text": text}, lambda: self.page.fill(selector, text))

    def select(self, selector, value):
        self.act("input", {"index": selector, "text": value}, lambda: self.page.select_option(selector, value))

    def done(self, text, success=True):
        self.steps.append({"step": self.idx, "url": self.page.url, "title": self.page.title(), "thought": "", "action": "done",
                           "params": {"text": text, "success": success}, "screenshot_before": f"step_{self.idx:03d}.png",
                           "screenshot_after": f"step_{self.idx + 1:03d}.png"})
        self.idx += 1
        self._shot(self.idx)
        # No `final_url`: agent_demo/agent.py never writes one. The landing page is carried by the
        # `done` step's url above (agent.py records state.url on the done action the same way), so the
        # evidence this matrix produces is shape-identical to a real recorder run.
        self.traj.update(steps=self.steps, terminated=True, termination_reason="agent_done", final_answer=text,
                         success_self_report=success)
        (self.run_dir / "trajectory.json").write_text(json.dumps(self.traj, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------- UI helpers
def login(rec, email):
    rec.click("header a.muted-link", "Sign Up/Log In")
    rec.fill("input[name=identity]", email)
    rec.fill("input[name=password]", PASSWORD)
    rec.click("main.auth button.primary", "Log in")


def search(rec, query):
    rec.fill("input[name=q]", query)
    rec.click("form.searchbar button", "search")


def sidebar(rec, path):
    rec.click(f"aside.sidebar a[href='{path}']", path)


def title_selector(title):
    return f'article.post-card h2 a:text-is("{title}")'


def open_title(rec, title):
    rec.click(title_selector(title), title)


def find_in_feed(rec, path, title):
    """Click the sidebar entry, page through the feed until `title` is visible, open it."""
    sidebar(rec, path)
    for _ in range(10):
        if rec.page.query_selector(title_selector(title)):
            open_title(rec, title)
            return
        rec.click("nav.pagination a:has-text('More posts')", "More posts")
    raise RuntimeError(f"{title!r} not found in {path}")


def description(rec):
    return rec.page.inner_text("p.description").strip()


def flash(rec):
    el = rec.page.query_selector(".flash")
    return el.inner_text().strip() if el else ""


def card_points(rec, path, titles):
    """Walk a feed and return {title: points} for the given titles (as shown on the cards)."""
    sidebar(rec, path)
    found = {}
    for _ in range(10):
        for art in rec.page.query_selector_all("article.post-card"):
            t = art.query_selector("h2 a").inner_text().strip()
            if t in titles:
                found[t] = int(art.query_selector(".stats strong").inner_text().replace(",", ""))
        if len(found) == len(titles):
            return found
        nxt = rec.page.query_selector("nav.pagination a:has-text('More posts')")
        if not nxt:
            break
        rec.click("nav.pagination a:has-text('More posts')", "More posts")
    raise RuntimeError(f"points not found for {set(titles) - set(found)}")


# ----------------------------------------------------------------------------- task drivers
LIGHTHOUSE = "Tiny lighthouse office with the best ocean view"
CAT = "Rescue cat learns the sound of the treat drawer"
SOLAR = "Solar-powered camping setup survives a rainy weekend"
BRIDGE = "An engineer explains why this bridge hums in the wind"
LIBRARY = "Neighborhood builds a miniature library for night-shift workers"
MARATHON = "Grandmother finishes her first marathon at seventy-two"
SOURDOUGH = "A baker recreates a city skyline in sourdough"
KEYBOARD = "Mechanical keyboard made entirely from transparent parts"
CONCERT = "Street musician turns a rain delay into a concert"
DOG = "Dog refuses to leave the kayak after the trip ends"
FOX = "A fox naps on the same garden wall every afternoon"
PLANT = "The office plant gets an employee badge"
PRESS = "A mysterious press-conference moment from 2009"
BALLOON = "Students launch a weather balloon with a tiny rubber duck"


def drive_0(rec):
    search(rec, "lighthouse offices")
    open_title(rec, LIGHTHOUSE)
    return description(rec)


def drive_1(rec):
    search(rec, "rescue cat")
    open_title(rec, CAT)
    return description(rec)


def drive_2(rec):
    search(rec, "solar camping")
    open_title(rec, SOLAR)
    return description(rec)


def drive_3(rec):
    find_in_feed(rec, "/interest/science", BRIDGE)
    return description(rec)


def drive_4(rec):
    search(rec, "community library")
    open_title(rec, LIBRARY)
    return description(rec)


def drive_5(rec):
    find_in_feed(rec, "/interest/sports", MARATHON)
    return description(rec)


def drive_6(rec):
    search(rec, "sourdough skyline")
    open_title(rec, SOURDOUGH)
    return description(rec)


def drive_7(rec):
    find_in_feed(rec, "/interest/gaming", KEYBOARD)
    return description(rec)


def drive_8(rec):
    search(rec, "rain delay concert")
    open_title(rec, CONCERT)
    return description(rec)


def drive_9(rec):
    points = card_points(rec, "/interest/animals", {CAT, DOG, FOX})
    winner = max(points, key=points.get)
    find_in_feed(rec, "/interest/animals", winner)
    return f"{winner} has the most points ({points[winner]} vs {sorted(points.values())}). {description(rec)}"


def drive_10(rec):
    login(rec, "alice.j@test.com")
    search(rec, "lighthouse office")
    open_title(rec, LIGHTHOUSE)
    rec.click(".detail .actions form[action$='/save'] button", "Save")
    return f"Saved the original post; button now reads {rec.page.inner_text('.detail .actions form[action$=\"/save\"] button').strip()!r}. {flash(rec)}"


def drive_11(rec):
    login(rec, "carol.d@test.com")
    find_in_feed(rec, "/interest/animals", DOG)
    rec.click(".detail .actions form button:has-text('Upvote')", "Upvote")
    return f"Upvoted the original kayak-dog post. Stats now: {rec.page.inner_text('.detail .stats').strip()}"


def drive_12(rec):
    login(rec, "bob.c@test.com")
    find_in_feed(rec, "/interest/science", BRIDGE)
    rec.fill("textarea[name=body]", "Resonance makes ordinary structures fascinating.")
    rec.click("section.comments form button.primary", "Post comment")
    return f"Comment posted on the original humming-bridge post. {flash(rec)}"


def drive_13(rec):
    login(rec, "carol.d@test.com")
    search(rec, "office plant employee badge")
    open_title(rec, PLANT)
    rec.click(".detail .actions form[action$='/hide'] button", "Hide")
    return f"Hid the original office-plant post. {flash(rec)}"


def drive_14(rec):
    login(rec, "david.k@test.com")
    find_in_feed(rec, "/news", PRESS)
    rec.click(".detail .actions a:has-text('Report')", "Report")
    rec.select("select[name=reason]", "Misinformation")
    rec.click("main.form-page button.primary", "Submit report")
    return f"Reported the 2009 press-conference post for Misinformation. {flash(rec)}"


def drive_15(rec):
    login(rec, "alice.j@test.com")
    rec.click("header a.post-button", "Post")
    rec.fill("input[name=title]", "Quiet victories deserve confetti")
    rec.fill("textarea[name=description]", "My neighbor finished night school after six years.")
    rec.select("select[name=section]", "wholesome")
    rec.fill("input[name=tags]", "community|education|wholesome")
    rec.click("main.form-page button.primary", "Publish post")
    return f"Published the post; it is live at {rec.page.url}. {flash(rec)}"


def drive_16(rec):
    login(rec, "alice.j@test.com")
    sidebar(rec, "/settings")
    rec.fill("input[name=display_name]", "Alice J.")
    rec.fill("textarea[name=bio]", "Memes, trail photos, and excellent tiny libraries.")
    rec.fill("input[name=location]", "Tacoma, WA")
    rec.click("main.form-page button.primary", "Save changes")
    return f"Profile updated. {flash(rec)}"


def drive_17(rec):
    rec.click("header a.muted-link", "Sign Up/Log In")
    rec.click("main.auth a[href='/register']", "Create an account")
    rec.fill("input[name=email]", "river.reader@test.com")
    rec.fill("input[name=username]", "river_reader")
    rec.fill("input[name=password]", "RiverRead123!")
    rec.click("main.auth button.primary", "Sign up")
    return f"Account created; the header now shows the signed-in username {rec.page.inner_text('header a.muted-link').strip()!r}."


def drive_18(rec):
    login(rec, "alice.j@test.com")
    sidebar(rec, "/saved")
    rec.click(f'article.post-card:has(h2 a:text-is("{SOLAR}")) form[action$=\'/save\'] button', "Saved (remove)")
    return f"Removed the original solar-powered rainy-weekend camping setup from Saved. {flash(rec)}"


def drive_19(rec):
    login(rec, "david.k@test.com")
    numbers = {}
    for title in (SOLAR, BRIDGE, BALLOON):
        find_in_feed(rec, "/interest/science", title)
        text = description(rec)
        numbers[title] = max(int(x) for x in re.findall(r"\d+", text))
    winner = max(numbers, key=numbers.get)
    find_in_feed(rec, "/interest/science", winner)
    rec.click(".detail .actions form[action$='/save'] button", "Save")
    return f"Largest stated numbers: {numbers}. Saved {winner!r}. {flash(rec)}"


DRIVERS = {n: globals()[f"drive_{n}"] for n in range(20)}


# ----------------------------------------------------------------------------- matrix
def run_verifier(python, n, run_dir):
    cmd = [python, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", str(run_dir), "--no_llm", "True"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        out = {"pass": False, "reason": f"verifier crashed: {r.stderr[-400:]}"}
    out["returncode"] = r.returncode
    return out


def clone_run(src, dst, **updates):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    path = dst / "trajectory.json"
    data = json.loads(path.read_text())
    data.update(updates)
    path.write_text(json.dumps(data, indent=2))


def wait_ready(base, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base + "/_health", timeout=3).read()
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:45001")
    ap.add_argument("--site_dir", default=str(SITE_DIR))
    ap.add_argument("--out", default=str(Path.cwd() / "runs" / "9gag_matrix"))
    ap.add_argument("--reset_cmd", default="", help="shell command that restores the seed DB and restarts the site")
    ap.add_argument("--after_db_cmd", default="", help="shell template copying the live instance DB to {dest}")
    ap.add_argument("--seed_db", default="")
    ap.add_argument("--tasks", default="", help="comma-separated task numbers (default all)")
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    site_dir = Path(args.site_dir).resolve()
    seed_db = Path(args.seed_db) if args.seed_db else site_dir / "instance_seed" / "9gag.db"
    live_db = site_dir / "instance" / "9gag.db"
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tasks = {json.loads(l)["id"]: json.loads(l) for l in (site_dir / "tasks.jsonl").read_text().splitlines() if l.strip()}
    numbers = [int(x) for x in args.tasks.split(",")] if args.tasks else list(range(20))

    def reset():
        if args.reset_cmd:
            subprocess.run(args.reset_cmd, shell=True, check=True, capture_output=True)
        if not wait_ready(args.base):
            raise RuntimeError("site not ready after reset")

    def snapshot_after(dest):
        if args.after_db_cmd:
            subprocess.run(args.after_db_cmd.format(dest=dest), shell=True, check=True)
        else:
            shutil.copy2(live_db, dest)

    matrix = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # one recorded no-op run (homepage only, empty answer) reused for every task
        noop_src = out / "_noop"
        if noop_src.exists():
            shutil.rmtree(noop_src)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        Recorder(page, noop_src, {"id": "9GAG--0", "ques": "noop"}, args.base).done("")
        page.context.close()

        for n in numbers:
            task_id = f"9GAG--{n}"
            task = tasks[task_id]
            stateful = n in STATEFUL_TASKS
            reset()
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            genuine = out / f"task{n:02d}_genuine"
            if genuine.exists():
                shutil.rmtree(genuine)
            rec = Recorder(page, genuine, task, args.base)
            try:
                answer = DRIVERS[n](rec)
            except Exception as exc:  # noqa: BLE001
                page.screenshot(path=str(out / f"task{n:02d}_drive_error.png"))
                raise RuntimeError(f"task {n} drive failed: {exc}") from exc
            rec.done(answer, True)
            ctx.close()
            shutil.copy2(seed_db, genuine / "initial.db")
            snapshot_after(genuine / "after.db")

            variants = {"genuine": genuine}
            noop = out / f"task{n:02d}_noop"
            clone_run(noop_src, noop, task_id=task_id, task=task["ques"], final_answer=None, success_self_report=False)
            shutil.copy2(seed_db, noop / "initial.db")
            shutil.copy2(seed_db, noop / "after.db")
            variants["noop"] = noop

            shortcut = out / f"task{n:02d}_shortcut"
            clone_run(noop_src, shortcut, task_id=task_id, task=task["ques"], final_answer=answer, success_self_report=True)
            shutil.copy2(seed_db, shortcut / "initial.db")
            shutil.copy2(seed_db, shortcut / "after.db")
            variants["shortcut"] = shortcut

            wrong = out / f"task{n:02d}_wrong"
            if stateful:
                clone_run(genuine, wrong)
                wrong_state(n).write(wrong / "after.db")
            else:
                clone_run(genuine, wrong, final_answer=WRONG_ANSWERS[n])
            variants["wrong"] = wrong

            if stateful:
                mismatch = out / f"task{n:02d}_mismatch"
                clone_run(genuine, mismatch)
                shutil.copy2(seed_db, mismatch / "after.db")
                variants["mismatch"] = mismatch

            row = {}
            for name, run_dir in variants.items():
                verdict = run_verifier(args.python, n, run_dir)
                expected = name == "genuine"
                row[name] = {"pass": bool(verdict.get("pass")), "reason": verdict.get("reason"), "expected_pass": expected,
                             "ok": bool(verdict.get("pass")) == expected}
            row["genuine_urls"] = [s["url"].replace(args.base, "") for s in json.loads((genuine / "trajectory.json").read_text())["steps"]]
            row["genuine_answer"] = answer
            matrix[task_id] = row
            cells = "  ".join(f"{k}={'PASS' if v['pass'] else 'FAIL'}{'' if v['ok'] else '(!!)'}" for k, v in row.items() if isinstance(v, dict))
            print(f"{task_id:9s} {cells}", flush=True)
        browser.close()

    reset()
    (out / "matrix.json").write_text(json.dumps(matrix, indent=2, ensure_ascii=False))
    bad = [(t, k) for t, row in matrix.items() for k, v in row.items() if isinstance(v, dict) and not v["ok"]]
    print(f"\nwrote {out / 'matrix.json'}; cells wrong: {bad if bad else 'none'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

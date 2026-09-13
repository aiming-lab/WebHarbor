#!/usr/bin/env python3
"""Live grading-contract validation matrix for the Amtrak mirror (CONTRIBUTING "Reviewer role", part C).

Drives the RUNNING mirror with a real Chromium (Playwright), records agent.py-shaped run
directories (trajectory.json + screenshots/step_NNN.png + initial.db/after.db) and runs
every ``sites/amtrak/verify/verify_N.py`` on five kinds of run:

  noop            homepage only, empty answer, clean DB            -> every verifier must FAIL
  pass            the task driven correctly through the UI         -> PASS
  shortcut        correct answer, no on-site navigation            -> FAIL
  wrong           genuine trajectory, wrong (near-miss) answer     -> FAIL
  state_mismatch  (stateful tasks) genuine trajectory, DB unchanged -> FAIL

Usage from the agent_demo uv project (Playwright + Chromium + Pillow are installed there):

  AMTRAK_BASE=http://127.0.0.1:45005 \\
  AMTRAK_SEED_DB=/path/to/sites/amtrak/instance_seed/amtrak.db \\
  AMTRAK_INSTANCE_DB=/path/to/sites/amtrak/instance/amtrak.db \\
  AMTRAK_RESET_CMD='bash /path/to/reset_site.sh' \\
    uv run python sites/amtrak/verify/tests/live_matrix.py --out_dir runs/amtrak_matrix

AMTRAK_RESET_CMD must restore the live DB to the seed (standalone: restart the Flask
process from a fresh instance_seed copy; container: ``curl -X POST :8101/reset/amtrak``).
AMTRAK_INSTANCE_DB is the live DB file to snapshot as after-state (container: a path that a
wrapper script ``docker cp``s to before each snapshot, see AMTRAK_SNAPSHOT_CMD).
Exit status is 1 when any matrix cell deviates from the expectation above.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
VERIFY_DIR = HERE.parent
SITE_DIR = VERIFY_DIR.parent
BASE = os.environ.get("AMTRAK_BASE", "http://127.0.0.1:40026").rstrip("/")
SEED_DB = Path(os.environ.get("AMTRAK_SEED_DB", SITE_DIR / "instance_seed" / "amtrak.db"))
INSTANCE_DB = Path(os.environ.get("AMTRAK_INSTANCE_DB", SITE_DIR / "instance" / "amtrak.db"))
RESET_CMD = os.environ.get("AMTRAK_RESET_CMD", "")
SNAPSHOT_CMD = os.environ.get("AMTRAK_SNAPSHOT_CMD", "")  # optional: run before copying INSTANCE_DB
PASSWORD = "TestPass123!"
ALICE = "alice.j@test.com"

TASKS = {int(r["id"].split("--")[1]): r for r in
         (json.loads(l) for l in (SITE_DIR / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
STATEFUL = {8, 17}


# --------------------------------------------------------------------------- recorder
class Recorder:
    """Writes a run dir in the exact shape agent_demo/agent.py produces."""

    def __init__(self, run_dir: Path, task_id: str):
        self.run_dir = run_dir
        self.shots = run_dir / "screenshots"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        self.shots.mkdir(parents=True)
        self.task_id = task_id
        self.steps: list[dict] = []
        self.n = 0
        self.final_answer = None

    def start(self, page):
        page.goto(BASE + "/", wait_until="networkidle")
        page.screenshot(path=str(self.shots / "step_000.png"))

    def act(self, page, action: str, params: dict, fn=None, thought: str = ""):
        url_before, title = page.url, page.title()
        if fn is not None:
            fn()
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:  # noqa: BLE001
                pass
        page.screenshot(path=str(self.shots / f"step_{self.n + 1:03d}.png"))
        self.steps.append({"step": self.n, "url": url_before, "title": title, "thought": thought, "action": action,
                           "params": params, "screenshot_before": f"step_{self.n:03d}.png",
                           "screenshot_after": f"step_{self.n + 1:03d}.png"})
        self.n += 1

    def navigate(self, page, path: str):
        self.act(page, "navigate", {"url": BASE + path}, lambda: page.goto(BASE + path, wait_until="networkidle"))

    def fill(self, page, selector: str, text: str):
        self.act(page, "input", {"index": 0, "text": text}, lambda: page.fill(selector, text))

    def select(self, page, selector: str, value: str):
        self.act(page, "input", {"index": 0, "text": value}, lambda: page.select_option(selector, value))

    def click(self, page, locator, thought: str = ""):
        self.act(page, "click", {"index": 0}, lambda: locator.click(), thought)

    def done(self, page, answer: str):
        self.final_answer = answer
        self.act(page, "done", {"text": answer, "success": True})

    def write(self, ques: str, verifier_path: str, rubric: str):
        traj = {"task": ques, "task_id": self.task_id, "start_url": BASE + "/", "model": "live_matrix", "max_steps": 40,
                "steps": self.steps, "terminated": True, "termination_reason": "agent_done",
                "final_answer": self.final_answer, "success_self_report": True, "judge_rubric": rubric,
                "verifier_path": verifier_path}
        (self.run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- site helpers
def reset_site() -> None:
    if not RESET_CMD:
        raise SystemExit("AMTRAK_RESET_CMD is required for the stateful cases")
    subprocess.run(RESET_CMD, shell=True, check=True)
    for _ in range(40):
        try:
            import urllib.request
            with urllib.request.urlopen(BASE + "/_health", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise SystemExit("site did not come back after reset")


def snapshot_after(run_dir: Path) -> None:
    if SNAPSHOT_CMD:
        subprocess.run(SNAPSHOT_CMD, shell=True, check=True)
    shutil.copy2(INSTANCE_DB, run_dir / "after.db")


def snapshot_initial(run_dir: Path) -> None:
    shutil.copy2(SEED_DB, run_dir / "initial.db")


def money(text: str) -> str:
    m = re.search(r"\$\s*([\d,]+\.\d{2})", text)
    return m.group(1).replace(",", "") if m else ""


def login(rec: Recorder, page, email: str = ALICE) -> None:
    rec.navigate(page, "/login")
    rec.fill(page, "input[name='email']", email)
    rec.fill(page, "input[name='password']", PASSWORD)
    rec.click(page, page.locator("main form button[type='submit']").first, "sign in")


def booking_search(rec: Recorder, page, origin: str, destination: str, date: str, *, trip_type: str | None = None,
                   return_date: str | None = None, passengers: str | None = None, fare_class: str | None = None,
                   sort: str | None = None) -> None:
    rec.navigate(page, "/booking/search")
    form = page.locator("form[data-trip-form]").first
    if trip_type:
        rec.click(page, form.locator(f"input[name='trip_type'][value='{trip_type}']"), "trip type")
    rec.fill(page, "form[data-trip-form] input[name='origin']", origin)
    rec.fill(page, "form[data-trip-form] input[name='destination']", destination)
    rec.fill(page, "form[data-trip-form] input[name='departure_date']", date)
    if return_date:
        rec.fill(page, "form[data-trip-form] input[name='return_date']", return_date)
    if passengers:
        rec.select(page, "form[data-trip-form] select[name='passengers']", passengers)
    if fare_class:
        rec.select(page, "form[data-trip-form] select[name='fare_class']", fare_class)
    if sort:
        rec.select(page, "form[data-trip-form] select[name='sort']", sort)
    rec.click(page, form.locator("button[type='submit']"), "search trips")


def choose_option(rec: Recorder, page, must_contain: str) -> None:
    form = page.locator("form", has=page.locator(".option-card", has_text=must_contain)).first
    rec.click(page, form.locator("input[name='option_token']"), f"select option {must_contain}")
    rec.click(page, form.locator("button[type='submit']"), f"choose option {must_contain}")


def fare_quote(page, fare_name: str) -> str:
    card = page.locator("label.option-card", has=page.locator("h3.card-title", has_text=fare_name)).first
    return money(card.locator(".stat-card").first.inner_text())


# --------------------------------------------------------------------------- pass drives (return answer)
def drive_0(rec, page):
    booking_search(rec, page, "NYP", "WAS", "2026-04-20", sort="duration")
    card = page.locator(".option-card").first.inner_text()
    m = re.search(r"([A-Za-z ]+?) (\d{3,4}) · (\d+h(?: \d+m)?)", card)
    return f"Fastest direct service: {m.group(1).strip()} train {m.group(2)}, total travel time {m.group(3)}."


def drive_1(rec, page):
    booking_search(rec, page, "NYP", "WAS", "2026-04-20", sort="price")
    card = page.locator(".option-card").first
    return f"Cheapest itinerary: {card.locator('.eyebrow').inner_text().strip().title()} - starting fare ${money(card.locator('.stat-card').first.inner_text())}."


def drive_2(rec, page):
    booking_search(rec, page, "WAS", "PHL", "2026-04-20", trip_type="round-trip", return_date="2026-04-22", sort="duration")
    choose_option(rec, page, "Acela Express 2152")
    choose_option(rec, page, "Acela Express 2151")
    rec.click(page, page.locator("a", has_text="Continue to fares").first, "continue to fares")
    return f"Per-traveler Business fare for the round trip: ${fare_quote(page, 'Business')}."


def drive_3(rec, page):
    rec.navigate(page, "/booking/multi-city")
    legs = [("SEA", "PDX", "2026-04-18"), ("PDX", "SAC", "2026-04-20"), ("SAC", "LAX", "2026-04-22")]
    for i, (o, d, dt) in enumerate(legs):
        rec.fill(page, f"input[name='origin_{i}']", o)
        rec.fill(page, f"input[name='destination_{i}']", d)
        rec.fill(page, f"input[name='date_{i}']", dt)
    rec.click(page, page.locator("button", has_text="Search multi-city options"), "search legs")
    for i in range(3):
        rec.click(page, page.locator(f"input[name='choice_{i}']").first, f"cheapest option leg {i + 1}")
    rec.click(page, page.locator("button", has_text="Save selected legs"), "save legs")
    rec.click(page, page.locator("a", has_text="Continue to fares").first, "continue to fares")
    return f"Per-traveler Value fare for the full itinerary: ${fare_quote(page, 'Value')}."


def drive_4(rec, page):
    booking_search(rec, page, "SEA", "LAX", "2026-04-22", passengers="2")
    choose_option(rec, page, "Coast Starlight")
    rec.click(page, page.locator("a", has_text="Continue to fares").first, "continue to fares")
    rec.click(page, page.locator("main form button[type='submit']", has_text="Continue").first, "continue with fare")
    rooms = page.locator("label.card", has=page.locator(".tag", has_text="+$"))
    best = min(((money(r.locator('.tag').first.inner_text()), r.locator('.choice-chip span').inner_text().strip())
                for r in rooms.all()), key=lambda t: float(t[0]))
    return f"The {best[1]} adds the smallest extra cost: +${best[0]}."


def drive_5(rec, page):
    login(rec, page)
    rec.navigate(page, "/account/trips")
    item = page.locator("a.detail-item", has_text="DEN").first.inner_text()
    code, rest = item.split(" · ", 1)
    origin = rest.split(" ")[0]
    date = re.search(r"([A-Z][a-z]{2} \d{2}, \d{4})", item).group(1)
    return f"Upcoming Denver trip: booking code {code.strip()}, origin {origin}, departing {date}."


def drive_6(rec, page):
    rec.navigate(page, "/trip-lookup")
    rec.fill(page, "input[name='booking_code']", "ALGX87")
    rec.fill(page, "input[name='email']", ALICE)
    rec.click(page, page.locator("main form button[type='submit']").first, "find trip")
    seg = page.locator(".detail-item").first.inner_text()
    route = re.match(r"([A-Za-z ]+?) \d{3,4}", seg).group(1)
    date = re.search(r"([A-Z][a-z]{2} \d{2}, \d{4})", page.locator("section.page-hero p").first.inner_text()).group(1)
    return f"Booking ALGX87 is on the {route} route, departing {date}."


def drive_7(rec, page):
    login(rec, page)
    rec.navigate(page, "/account/rewards")
    pts = page.locator(".stat-card", has_text="Points balance").locator("strong").inner_text().strip()
    return f"Current rewards points balance: {pts} points."


def drive_8(rec, page):
    login(rec, page)
    rec.navigate(page, "/account/edit")
    rec.fill(page, "input[name='preferred_station_code']", "SEA")
    rec.click(page, page.locator("main form button[type='submit']").first, "save preferences")
    rec.navigate(page, "/account/rewards")
    code = page.locator(".stat-card", has_text="Preferred station").locator("strong").inner_text().strip()
    return f"Preferred station now shown on the rewards dashboard: {code}."


def drive_9(rec, page):
    rec.navigate(page, "/routes/amtrak-cascades")
    codes = re.findall(r"\(([A-Z]{3})\)", " ".join(page.locator(".timeline-item strong").all_inner_texts()))
    return "Amtrak Cascades stop order: " + ", ".join(codes) + "."


def drive_10(rec, page):
    rec.navigate(page, "/service-alerts")
    card = page.locator("article.alert-card", has_text="Coast Starlight").first
    return "Recommended next step: " + card.locator(".subtle").first.inner_text().strip()


def drive_11(rec, page):
    rec.navigate(page, "/service-alerts")
    card = page.locator("article.alert-card", has_text="Denver").first
    m = re.search(r"from track (\d+)", card.inner_text())
    return f"Westbound long-distance departures board from track {m.group(1)}."


def drive_12(rec, page):
    booking_search(rec, page, "CHI", "DEN", "2026-04-20", fare_class="flexible")
    card = page.locator(".option-card").first
    return f"{card.locator('.eyebrow').inner_text().strip().title()} - Flexible price ${money(card.locator('.stat-card').first.inner_text())}."


def drive_13(rec, page):
    booking_search(rec, page, "SAC", "SJC", "2026-04-16")
    card = page.locator(".option-card").first
    return f"{card.locator('.eyebrow').inner_text().strip().title()} - starting fare ${money(card.locator('.stat-card').first.inner_text())}."


def drive_14(rec, page):
    rec.navigate(page, "/stations/ANA")
    ana = page.locator("section.page-hero").inner_text()
    rec.navigate(page, "/stations/SBA")
    sba = page.locator("section.page-hero").inner_text()
    which = "Santa Barbara (SBA)" if "Checked baggage available" in sba and "Checked baggage available" not in ana else "?"
    return f"{which} supports checked baggage; Anaheim (ANA) is carry-on only."


def drive_15(rec, page):
    rec.navigate(page, "/help")
    rec.fill(page, "main form.utility-search input[name='q']", "checked baggage")
    rec.click(page, page.locator("main form.utility-search button[type='submit']"), "search help")
    rec.click(page, page.locator("a.card", has_text="When checked baggage closes").first, "open article")
    summary = page.locator("section.page-hero p").first.inner_text()
    m = re.search(r"(\d+)-minute", summary)
    return f"Checked baggage closes {m.group(1)} minutes before departure; the cutoff applies to long-distance departures at staffed stations."


def drive_16(rec, page):
    rec.navigate(page, "/help")
    rec.fill(page, "main form.utility-search input[name='q']", "refund")
    rec.click(page, page.locator("main form.utility-search button[type='submit']"), "search help")
    rec.click(page, page.locator("a.card").first, "open article")
    title = page.locator("section.page-hero h2").first.inner_text().strip()
    category = page.locator("section.page-hero .eyebrow").first.inner_text().strip()
    return f'The article is titled "{title}" and is filed under the {category} category.'


def drive_17(rec, page):
    login(rec, page)
    booking_search(rec, page, "NYP", "WAS", "2026-04-20")
    choose_option(rec, page, "Acela Express 2151")
    rec.click(page, page.locator("a", has_text="Continue to fares").first, "continue to fares")
    rec.click(page, page.locator("input[name='fare_slug'][value='business']"), "pick Business")
    rec.click(page, page.locator("main form button[type='submit']", has_text="Continue").first, "continue")
    rec.fill(page, "input[name='first_name_0']", "Alice")
    rec.fill(page, "input[name='last_name_0']", "Jordan")
    rec.click(page, page.locator("button", has_text="Continue to review"), "continue to review")
    rec.navigate(page, "/booking/checkout")
    rec.click(page, page.locator("button", has_text="Confirm demo booking"), "confirm")
    code = page.locator(".confirmation-code").first.inner_text().strip()
    return f"New booking code shown on the confirmation page: {code}."


DRIVES = {n: globals()[f"drive_{n}"] for n in range(18)}

WRONG = {
    0: "Fastest direct service: Carolinian train 79, total travel time 3h 12m.",
    1: "Cheapest itinerary: Carolinian - starting fare $26.95.",
    2: "Per-traveler Business fare for the round trip: $90.86.",
    3: "Per-traveler Value fare for the full itinerary: $147.51.",
    4: "The Bedroom adds the smallest extra cost: +$592.00.",
    5: "Upcoming Denver trip: booking code ALGX87, origin NYP, departing Apr 20, 2026.",
    6: "Booking ALGX87 is on the Northeast Regional route, departing Apr 16, 2026.",
    7: "Current rewards points balance: 2400 points.",
    8: "Preferred station now shown on the rewards dashboard: NYP.",
    9: "Amtrak Cascades stop order: VAC, SEA, PDX, EUG.",
    10: "Recommended next step: Filter for direct service if you want to avoid the transfer pattern.",
    11: "Westbound long-distance departures board from track 2.",
    12: "California Zephyr - Flexible price $72.06.",
    13: "Capitol Corridor - starting fare $42.80.",
    14: "Anaheim (ANA) supports checked baggage; Santa Barbara (SBA) is carry-on only.",
    15: "Checked baggage closes 30 minutes before departure; the cutoff applies to all departures.",
    16: 'The article is titled "Carry-on and checked baggage basics" and is filed under the Baggage category.',
    17: "New booking code shown on the confirmation page: ALGX87.",
}


# --------------------------------------------------------------------------- matrix
def run_verifier(n: int, run_dir: Path) -> dict:
    cmd = [sys.executable, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", str(run_dir), "--no_llm", "True"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        verdict = json.loads(r.stdout)
    except json.JSONDecodeError:
        verdict = {"pass": False, "reason": f"verifier crashed: {r.stderr.strip()[-300:]}", "evidence": []}
    verdict["returncode"] = r.returncode
    return verdict


def write_variant(src: Path, dst: Path, *, answer: str | None = None, steps=None, after_seed: bool = False) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    traj = json.loads((dst / "trajectory.json").read_text(encoding="utf-8"))
    if answer is not None:
        traj["final_answer"] = answer
    if steps is not None:
        traj["steps"] = steps
    (dst / "trajectory.json").write_text(json.dumps(traj, indent=2), encoding="utf-8")
    if after_seed:
        shutil.copy2(SEED_DB, dst / "after.db")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_dir", default="runs/amtrak_matrix")
    parser.add_argument("--only", default="", help="comma-separated task numbers")
    args = parser.parse_args()
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    only = {int(x) for x in args.only.split(",") if x.strip()} or set(TASKS)
    results: dict[str, dict[int, dict]] = {k: {} for k in ("noop", "pass", "shortcut", "wrong", "state_mismatch")}
    answers: dict[int, str] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # no-op run (one shared run dir, re-labelled per task id)
        noop_src = out / "noop_src"
        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        rec = Recorder(noop_src, "Amtrak--0")
        rec.start(page)
        rec.act(page, "scroll", {"down": True, "pages": 1.0}, lambda: page.mouse.wheel(0, 600))
        rec.final_answer = ""
        rec.write("noop", "", "")
        snapshot_initial(noop_src)
        shutil.copy2(SEED_DB, noop_src / "after.db")
        ctx.close()

        for n in sorted(only):
            row = TASKS[n]
            run_dir = out / f"pass_{n}"
            if n in STATEFUL:
                reset_site()
            ctx = browser.new_context(viewport={"width": 1366, "height": 900})
            page = ctx.new_page()
            rec = Recorder(run_dir, row["id"])
            rec.start(page)
            answer = DRIVES[n](rec, page)
            rec.done(page, answer)
            rec.write(row["ques"], row["verifier_path"], row["judge_rubric"])
            ctx.close()
            snapshot_initial(run_dir)
            snapshot_after(run_dir)
            if n in STATEFUL:
                reset_site()
            answers[n] = answer
            print(f"[pass_{n}] answer: {answer}")
        browser.close()

    for n in sorted(only):
        row = TASKS[n]
        src = out / f"pass_{n}"
        # noop
        noop_dir = out / f"noop_{n}"
        write_variant(noop_src, noop_dir)
        traj = json.loads((noop_dir / "trajectory.json").read_text()); traj["task_id"] = row["id"]
        (noop_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
        results["noop"][n] = run_verifier(n, noop_dir)
        results["pass"][n] = run_verifier(n, src)
        # shortcut: homepage only + correct answer (+ seed after-state)
        sc = out / f"shortcut_{n}"
        pass_traj = json.loads((src / "trajectory.json").read_text())
        first = pass_traj["steps"][0]
        done_step = {"step": 1, "url": BASE + "/", "title": "Amtrak Demo Mirror", "thought": "recall", "action": "done",
                     "params": {"text": answers[n], "success": True}, "screenshot_before": first["screenshot_after"],
                     "screenshot_after": first["screenshot_after"]}
        write_variant(src, sc, steps=[first, done_step], after_seed=True)
        results["shortcut"][n] = run_verifier(n, sc)
        # wrong answer
        wr = out / f"wrong_{n}"
        write_variant(src, wr, answer=WRONG[n])
        results["wrong"][n] = run_verifier(n, wr)
        # state mismatch
        if n in STATEFUL:
            sm = out / f"state_mismatch_{n}"
            write_variant(src, sm, after_seed=True)
            results["state_mismatch"][n] = run_verifier(n, sm)

    expected = {"noop": False, "pass": True, "shortcut": False, "wrong": False, "state_mismatch": False}
    deviations = 0
    print("\n| task | noop | pass | shortcut | wrong | state_mismatch |")
    print("|---|---|---|---|---|---|")
    for n in sorted(only):
        cells = []
        for kind in ("noop", "pass", "shortcut", "wrong", "state_mismatch"):
            v = results[kind].get(n)
            if v is None:
                cells.append("n/a")
                continue
            ok = bool(v.get("pass")) == expected[kind] and v.get("returncode") == (0 if expected[kind] else 1)
            deviations += 0 if ok else 1
            label = "PASS" if v.get("pass") else f"FAIL ({v.get('reason')})"
            cells.append(label + ("" if ok else "  <-- UNEXPECTED"))
        print(f"| Amtrak--{n} | " + " | ".join(cells) + " |")
    (out / "matrix.json").write_text(json.dumps({"results": results, "answers": answers}, indent=2, default=str))
    print(f"\ndeviations: {deviations}")
    return 1 if deviations else 0


if __name__ == "__main__":
    raise SystemExit(main())

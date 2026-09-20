#!/usr/bin/env python3
"""Playwright run-signature writer and grading matrix for the UC Berkeley verifiers.

For each task this boots the mirror from a fresh seed on an alt port, drives a
scripted workflow with a real browser, snapshots the live SQLite database, and
writes a run directory in the ``agent_demo/agent.py`` shape (``trajectory.json``
with url-before-action steps, ``screenshots/step_NNN.png``, ``initial.db``,
``after.db``). It then grades each run through

    uv run python agent_demo/eval_judge.py --run_dir <dir> --verifier True

and compares the verdict with the cell's expectation, so a verifier that stops
discriminating shows up as a matrix failure rather than a silent green.

Run it from ``agent_demo/`` (that env has Playwright and the uv project the
verifiers are launched with):

    cd agent_demo
    uv run python ../sites/berkeley/verify/tests/run_matrix.py --out ../sites/berkeley/scripts_dev/runs/matrix

Cells emitted per task: ``pass`` (the genuine walk), ``no_op`` (homepage only,
no answer), ``shortcut`` (a catalog-wide search only, with the correct answer),
``wrong_answer`` (the genuine walk with a plausible wrong answer),
``collateral_write`` (the genuine walk plus one row written straight into the
live database — fault injection, not an app-driven write) and, for the two
stateful rows, ``state_mismatch`` (the genuine walk with the save skipped).

All artifacts land under ``--out`` (default: the gitignored
``sites/berkeley/scripts_dev/runs/matrix``), which is also self-ignored by a
generated ``.gitignore`` inside the output root.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

VERIFY_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = VERIFY_DIR.parent
REPO = SITE_DIR.parents[1]
sys.path.insert(0, str(VERIFY_DIR))

import ground_truth  # noqa: E402
from verify_lib import title_tokens  # noqa: E402

DEFAULT_PORT = 41026
DEFAULT_OUT = SITE_DIR / "scripts_dev" / "runs" / "matrix"
VIEWPORT = {"width": 1280, "height": 800}
PASSWORD = "test1234"

# --------------------------------------------------------------------------- #
# Workflows: each step is one browser action in the recorder's semantics
# (the recorded URL is the page *before* the action, as agent.py does).
# --------------------------------------------------------------------------- #
#   {"goto": path}                     navigate
#   {"fill": [selector, text], ...}     type into fields (one entry per field)
#   {"click": selector}                 click an element
#   {"form": "/bookmark/add"}           submit the form whose action matches
#
# ``answer`` is built from the derived facts, so the genuine run carries the
# ground truth without a second copy of it in this file.
WORKFLOWS: dict[int, dict[str, Any]] = {
    1: {"steps": [{"goto": "/"}, {"goto": "/programs?q=MBA"},
                  {"goto": "/programs/business-administration-mba"}]},
    2: {"steps": [{"goto": "/"}, {"goto": "/programs?q=Computer%20Science"},
                  {"goto": "/programs/computer-science-bs"}]},
    4: {"steps": [{"goto": "/"}, {"goto": "/news?q=CRISPR"},
                  {"goto": "/news/crispr-pioneer-jennifer-doudna-receives-national-medal-of-science"}]},
    6: {"steps": [{"goto": "/"}, {"goto": "/events?category=Lecture"}]},
    7: {"steps": [{"goto": "/"}, {"goto": "/faculty?dept=eecs"},
                  {"goto": "/faculty/stuart-russell"}]},
    10: {"steps": [{"goto": "/"}, {"goto": "/research/bair"}]},
    11: {"steps": [{"goto": "/"}, {"goto": "/admissions"}]},
    12: {"steps": [{"goto": "/"}, {"goto": "/programs?college=haas-business"}]},
    13: {"steps": [{"goto": "/"}, {"goto": "/departments"}, {"goto": "/departments/eecs"}]},
    14: {"steps": [{"goto": "/"}, {"goto": "/academics"}]},
    16: {"steps": [{"goto": "/"}, {"goto": "/programs?page=2"},
                   {"goto": "/programs/data-science-ms"}]},
    17: {"steps": [{"goto": "/"}, {"goto": "/about"}]},
    19: {"steps": [{"goto": "/"}, {"goto": "/news?category=Athletics"},
                   {"goto": "/news/womens-gymnastics-wins-ncaa-championship"}]},
    20: {"steps": [{"goto": "/"}, {"goto": "/programs?degree=JD"},
                   {"goto": "/programs/juris-doctor-jd"}]},
    22: {"steps": [{"goto": "/"}, {"goto": "/departments"}]},
    23: {"steps": [{"goto": "/"}, {"goto": "/research"}, {"goto": "/research/bids"}]},
    24: {"steps": [{"goto": "/"}, {"goto": "/programs/economics-phd"},
                   {"goto": "/departments/economics"}, {"goto": "/faculty/emmanuel-saez"}]},
    25: {"steps": [{"goto": "/"}, {"goto": "/events?category=Career"}, {"goto": "/events/2"}]},
    27: {"steps": [{"goto": "/"}, {"goto": "/programs?q=Master%20of%20Engineering"},
                   {"goto": "/programs/master-of-engineering-meng"},
                   {"goto": "/programs/computer-science-ms"}]},
    28: {"steps": [{"goto": "/"}, {"goto": "/programs?degree=PhD"}, {"goto": "/programs?degree=MS"}]},
    30: {"login": "alice@berkeley.edu",
         "steps": [{"goto": "/login"},
                   {"fill": [("input[name='email']", "alice@berkeley.edu"),
                             ("input[name='password']", PASSWORD)]},
                   {"click": "form[action='/login'] button[type=submit]"},
                   {"goto": "/research/seismo-lab"},
                   {"form": "/bookmark/add", "skip_in_state_mismatch": True},
                   {"goto": "/account"}]},
    31: {"login": "bob@berkeley.edu",
         "steps": [{"goto": "/login"},
                   {"fill": [("input[name='email']", "bob@berkeley.edu"),
                             ("input[name='password']", PASSWORD)]},
                   {"click": "form[action='/login'] button[type=submit]"},
                   {"goto": "/research/msri"},
                   {"form": "/bookmark/add", "skip_in_state_mismatch": True},
                   {"goto": "/research/cpl"},
                   {"form": "/bookmark/add", "skip_in_state_mismatch": True},
                   {"goto": "/account"},
                   {"click": "form[action='/bookmark/remove'] button",
                    "skip_in_state_mismatch": True},
                   {"goto": "/account"}]},
}

WRONG_ANSWERS: dict[int, list[str]] = {
    1: ["The School of Law offers the MBA; it takes 3 years.",
        "The Haas School of Business offers the MBA; it takes four years."],
    2: ["The Computer Science BS requires foundational coursework in theory, systems and AI, "
        "plus a research project or thesis.",
        "The Computer Science BS requires Data Structures, Algorithms, Computer Architecture and "
        "Operating Systems, as well as a Qualifying Examination."],
    4: ["The featured scientist is Jennifer Doudna, who received the Nobel Prize.",
        "The article is about a faster COVID test using CRISPR."],
    6: ["Events: 'Spring Career Fair 2026' on May 17, 2026 at the Recreational Sports Facility; "
        "'Hackathon: Code for Climate 2026' on May 30, 2026 at Soda Hall; 'Berkeley Startup Pitch "
        "Competition Finals' on June 4, 2026 at 310 Sutardja Dai Hall."],
    7: ["Eliza Strickland works on AI reporting and biomedical ethics.",
        "Stuart Russell works on robotics and reinforcement learning."],
    10: ["BAIR was founded in 2017 and is directed by Prof. Pieter Abbeel."],
    11: ["The freshman deadline is December 1 and the acceptance rate is 11%."],
    12: ["Haas offers MBA, PhD and MFE programs.",
         "The Haas School of Business offers the Business Administration MBA and a PhD in Business."],
    13: ["The EECS chair is Prof. Alexei Efros, in 253 Cory Hall."],
    14: ["The College of Engineering enrolls 31,800 undergraduates and 12,000 graduate students; "
         "the dean is Dean Tsu-Jae King Liu."],
    16: ["Several programs can be completed online, including the Computer Science MS and the "
         "Master of Engineering.",
         "The Data Science MS from the School of Information is online, and so is the Civil "
         "Engineering BS."],
    17: ["Berkeley has 107 Nobel Laureates on the faculty, 30 varsity sports and 105 NCAA titles.",
         "Berkeley has 12 Nobel Laureates on the faculty, 32 varsity sports and 105 NCAA titles."],
    19: ["Berkeley athletes won a record 12 medals at the Winter World University Games.",
         "Cal won the Pac-12 football championship."],
    20: ["The JD takes 2 years, has a January 5 deadline, and is offered by the Haas School of "
         "Business."],
    22: ["The College of Letters and Science has 30 departments.",
         "The College of Letters and Science lists 8 departments."],
    23: ["BIDS is directed by Prof. Douglas Dreger; focus areas are Data Science, Statistics and "
         "Computational Methods; a related center is the Berkeley Seismological Laboratory.",
         "BIDS is directed by Prof. David Culler and focuses on Machine Learning, Robotics and "
         "Climate Policy."],
    24: ["The Economics department is chaired by Prof. David Card and offers the Economics BA and "
         "the Economics PhD. Emmanuel Saez works on public economics and inequality."],
    25: ["The Spring Career Fair is on May 17, 2026 at the Recreational Sports Facility, and "
         "registration is not required.",
         "The Spring Career Fair is on May 17, 2026 at Pauley Ballroom, registration required."],
    27: ["The Master of Engineering is offered by EECS and takes 2 years; the Computer Science MS "
         "takes 2 years."],
    28: ["There are 25 programs that require the GRE, all of them PhD programs."],
    30: ["I am not sure the Berkeley Seismological Laboratory was saved."],
    31: ["The Mathematical Sciences Research Institute was removed and the California Policy Lab "
         "remains saved; its director is Prof. Tatiana Toro."],
}


def genuine_answer(number: int, facts: dict) -> str:
    """The correct answer, rendered from the derived target."""
    if number == 1:
        return f"The {facts['college']} offers the MBA; it takes {facts['duration_years']:g} years."
    if number == 2:
        return f"The Computer Science BS requires {', '.join(facts['items'])}."
    if number == 4:
        return f"The article features {facts['person']}, who received the {facts['award']}."
    if number == 6:
        # Rows with enough distinctive title tokens for the verifier's binding rule.
        rows = [row for row in facts["upcoming"] if len(title_tokens(row["title"])) >= 3][:3]
        listed = "; ".join(f"'{row['title']}' on {row['start_datetime'][:10]} at {row['location']}" for row in rows)
        return f"Lecture events: {listed}."
    if number == 7:
        row = next(r for r in facts["allowed"] if r["slug"] == "stuart-russell")
        return f"{row['name']} is an EECS professor whose research covers {row['research_interests']}."
    if number == 10:
        return f"BAIR was founded in {facts['founded_year']} and is directed by {facts['director']}."
    if number == 11:
        return (f"The freshman application deadline is {facts['deadline']}, and the acceptance "
                f"rate is {facts['acceptance_rate']}.")
    if number == 12:
        programme = facts["programmes"][0]
        return (f"The {facts['college']['name']} offers a single program: the "
                f"{programme['degree_type']} in {programme['name']}.")
    if number == 13:
        return f"The chair of EECS is {facts['chair']}, and the department is located at {facts['location']}."
    if number == 14:
        return (f"The College of Engineering enrolls {facts['undergrad_count']:,} undergraduates and "
                f"{facts['grad_count']:,} graduate students; the dean is {facts['dean']}.")
    if number == 16:
        programme = facts["program"]
        return (f"Only one program offers an online option: the {programme['name']} "
                f"{programme['degree_type']} from the {programme['college_name']}.")
    if number == 17:
        return (f"Berkeley has {facts['nobel_laureates']} Nobel Laureates on the faculty, "
                f"{facts['varsity_sports']} varsity sports, and {facts['national_titles']} NCAA "
                f"national titles.")
    if number == 19:
        row = facts["championships"][0]
        return f"{row['title']}: the story reports the championship win and the team's run to it."
    if number == 20:
        return (f"The JD at Berkeley takes {facts['duration_years']:g} years, has a "
                f"{facts['deadline']} deadline, and is offered by the {facts['college']}.")
    if number == 22:
        names = [row["name"] for row in facts["departments"]][:6]
        return (f"The College of Letters and Science lists {len(facts['departments'])} departments: "
                f"{', '.join(names)}.")
    if number == 23:
        centre, related = facts["centre"], facts["related_names"]
        return (f"{centre['name']} is directed by {centre['director']}; its focus areas are "
                f"{', '.join(facts['focus_areas'])}. A related center listed on the page is the "
                f"{related[0]}.")
    if number == 24:
        member = next(r for r in facts["members"] if r["slug"] == "emmanuel-saez")
        types = " and ".join(sorted({row["degree_type"] for row in facts["programmes"]}))
        return (f"The Economics department is chaired by {facts['chair']} and offers the {types} in "
                f"Economics. {member['name']} works on {member['research_interests']}.")
    if number == 25:
        anchor = facts["anchor"]
        others = facts["others"][:2]
        listed = "; ".join(f"'{row['title']}' on {row['start_datetime'][:10]} at {row['location']}"
                           for row in others)
        return (f"The {anchor['title']} is on {anchor['start_datetime'][:10]} at {anchor['location']}, "
                f"and registration is required. Two other career events: {listed}.")
    if number == 27:
        return (f"The {facts['meng']['name']} is offered by the {facts['department']} and takes "
                f"{facts['durations'][0]:g} year; the {facts['ms']['name']} "
                f"{facts['ms']['degree_type']} takes {facts['durations'][1]:g} years.")
    if number == 28:
        return (f"{facts['count']} programs in the catalogue require the GRE; the degree type that "
                f"most commonly requires it is the {facts['most_common_degree']}.")
    if number == 30:
        centre = facts["centre"]
        return (f"I signed in as alice, saved the {centre['name']} to my bookmarks, and it is listed "
                f"under My Account. Its director is {facts['director']}.")
    if number == 31:
        first, second = facts["first"], facts["second"]
        return (f"I signed in as bob, saved both centers in order, then removed the {first['name']} "
                f"bookmark. The {second['name']} remains saved; its director is "
                f"{second['director']}.")
    raise ValueError(f"no genuine answer template for task {number}")


# --------------------------------------------------------------------------- #
# Browser driving
# --------------------------------------------------------------------------- #
class Recorder:
    """Writes one run directory in the agent.py shape."""

    def __init__(self, run_dir: Path, task_id: str, start_url: str) -> None:
        self.run_dir = run_dir
        self.shots = run_dir / "screenshots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.steps: list[dict[str, Any]] = []
        self.start_url = start_url
        self.task_id = task_id

    def step(self, page, action: str, params: dict[str, Any], act) -> None:
        index = len(self.steps)
        before, after = f"step_{index:03d}.png", f"step_{index + 1:03d}.png"
        url_before = page.url
        page.screenshot(path=str(self.shots / before))
        if act is not None:
            act()
        page.screenshot(path=str(self.shots / after))
        self.steps.append({
            "step": index, "url": url_before, "title": page.title(),
            "thought": "scripted matrix step", "action": action, "params": params,
            "screenshot_before": before, "screenshot_after": after,
            "action_result": {"is_done": False, "success": True, "error": None, "extracted_content": ""},
        })

    def finish(self, page, answer: str | None) -> None:
        self.step(page, "done", {"text": answer or "", "success": bool(answer)}, None)
        trajectory = {
            "task": "scripted matrix run", "task_id": self.task_id, "start_url": self.start_url,
            "model": "playwright-matrix", "max_steps": 30, "steps": self.steps,
            "terminated": bool(answer), "termination_reason": "agent_done" if answer else "max_steps",
            "final_answer": answer, "success_self_report": bool(answer),
            "judge_rubric": "", "verifier_path": f"sites/berkeley/verify/verify_{self.task_id.rsplit('--', 1)[1]}.py",
        }
        (self.run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2), encoding="utf-8")


def drive(page, base_url: str, steps: list[dict[str, Any]], recorder: Recorder,
          *, skip_saves: bool = False) -> None:
    for item in steps:
        if skip_saves and item.get("skip_in_state_mismatch"):
            # The state-mismatch cell replays the workflow with every write
            # skipped, so a later click that depends on a write (the bookmark
            # removal) must be skipped with it, or the cell hangs on a form
            # that a fresh instance never renders.
            continue
        if "goto" in item:
            target = base_url + item["goto"]
            recorder.step(page, "navigate", {"url": target}, lambda target=target: page.goto(target))
        elif "fill" in item:
            # One step per field: the verifier reads the typed texts of the
            # /login input steps (email and password are separate actions).
            for selector, text in item["fill"]:
                recorder.step(
                    page, "input", {"text": text},
                    lambda selector=selector, text=text: page.fill(selector, text),
                )
        elif "click" in item:
            selector = item["click"]
            recorder.step(page, "click", {"selector": selector}, lambda selector=selector: page.click(selector))
        elif "form" in item:
            action = item["form"]
            selector = f"form[action='{action}'] button"
            recorder.step(page, "click", {"form": action}, lambda selector=selector: page.click(selector))
        else:  # pragma: no cover - workflow table is static
            raise ValueError(f"unsupported step: {item!r}")


# --------------------------------------------------------------------------- #
# Boot / snapshot / grade
# --------------------------------------------------------------------------- #
def fresh_instance(site_dir: Path) -> None:
    instance = site_dir / "instance"
    if instance.exists():
        shutil.rmtree(instance)
    shutil.copytree(site_dir / "instance_seed", instance)


def boot(site_dir: Path, port: int) -> subprocess.Popen:
    log = site_dir / "scripts_dev" / "runs" / "server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    # Refuse to run against a server we did not start. Otherwise the readiness
    # probe below adopts any process already listening on the port (e.g. a
    # leftover standalone `PORT=41026 python app.py`) and every snapshot and
    # every verdict then describe that foreign instance while the cells look
    # green. Observed for real: a stray server made the 30/31 pass cells fail
    # with bookmarks_exact_delta.
    try:
        probe = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        probe.request("GET", "/")
        probe.getresponse()
        probe.close()
    except OSError:
        pass
    else:
        raise RuntimeError(
            f"port :{port} already serves a site that this run did not start; "
            f"stop it (lsof -ti tcp:{port}) before running the matrix"
        )
    handle = log.open("ab")
    process = subprocess.Popen(
        [sys.executable, "app.py"], cwd=str(site_dir),
        env={**os.environ, "PORT": str(port)}, stdout=handle, stderr=handle,
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            connection.request("GET", "/")
            if connection.getresponse().status == 200:
                connection.close()
                return process
            connection.close()
        except OSError:
            time.sleep(0.25)
    process.terminate()
    raise RuntimeError(f"site did not come up on :{port} (see {log})")


def snapshot(site_dir: Path, run_dir: Path, kind: str) -> Path:
    source = site_dir / ("instance_seed" if kind == "initial" else "instance") / "berkeley.db"
    target = run_dir / ("initial.db" if kind == "initial" else "after.db")
    shutil.copy2(source, target)
    return target


def inject_collateral_write(site_dir: Path) -> None:
    """One row written straight into the live DB (fault injection, not a route)."""
    connection = sqlite3.connect(str(site_dir / "instance" / "berkeley.db"))
    try:
        connection.execute(
            "INSERT INTO bookmarks(user_id, item_type, item_id, note, created_at) "
            "VALUES (2, 'research', 1, 'matrix collateral write', '2026-05-12 00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()


def grade(run_dir: Path) -> dict[str, Any]:
    # eval_judge.py imports the agent_demo project's dependencies (openai,
    # simpleArgParser), so it must be launched from inside agent_demo/ — the
    # repo root has no pyproject and its .venv lacks them (verified: launching
    # from the repo root dies with ModuleNotFoundError: No module named 'openai'
    # and never writes eval.json).
    command = ["uv", "run", "python", "eval_judge.py",
               "--run_dir", str(run_dir), "--verifier", "True"]
    result = subprocess.run(command, cwd=str(REPO / "agent_demo"), capture_output=True, text=True)
    verdict_path = run_dir / "eval.json"
    if not verdict_path.is_file():
        return {"pass": None, "reason": f"no eval.json (rc={result.returncode}): "
                                        f"{(result.stderr or result.stdout)[-300:]}"}
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    return {"pass": bool(verdict.get("pass")), "reason": verdict.get("reason"),
            "infra_error": bool(verdict.get("infra_error"))}


def emit_cells(number: int, facts: dict, out_root: Path, base_url: str,
               wanted: set[str] | None = None) -> list[tuple[str, Path, bool]]:
    """Build every run directory for one task; returns (cell, run_dir, expects_pass)."""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415 - optional dependency at runtime

    workflow = WORKFLOWS[number]
    answer = genuine_answer(number, facts)
    cells: list[tuple[str, Path, bool]] = []
    task_id = f"UC Berkeley--{number}"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for cell, expects_pass in (("pass", True), ("no_op", False), ("shortcut", False),
                                   ("wrong_answer", False), ("collateral_write", False),
                                   ("state_mismatch", False)):
            if cell == "state_mismatch" and not workflow.get("login"):
                continue
            if wanted and cell not in wanted:
                continue
            run_dir = out_root / f"task_{number:02d}" / cell
            run_dir.mkdir(parents=True, exist_ok=True)
            fresh_instance(SITE_DIR)
            process = boot(SITE_DIR, DEFAULT_PORT)
            try:
                snapshot(SITE_DIR, run_dir, "initial")
                page = browser.new_page(viewport=VIEWPORT)
                # agent.py navigates to the start URL before its first recorded
                # step, so step 0's ``url`` is the start URL. Without this the
                # page is still about:blank and the verifier's
                # all_urls_match_local_origin gate fails the genuine run.
                page.goto(base_url + "/")
                recorder = Recorder(run_dir, task_id, f"{base_url}/")
                if cell == "no_op":
                    drive(page, base_url, [{"goto": "/"}], recorder)
                    recorder.finish(page, None)
                elif cell == "shortcut":
                    drive(page, base_url, [{"goto": "/"}, {"goto": "/search?q=california"}], recorder)
                    recorder.finish(page, answer)
                elif cell == "wrong_answer":
                    drive(page, base_url, workflow["steps"], recorder)
                    recorder.finish(page, WRONG_ANSWERS[number][0])
                elif cell == "state_mismatch":
                    drive(page, base_url, workflow["steps"], recorder, skip_saves=True)
                    recorder.finish(page, answer)
                else:
                    drive(page, base_url, workflow["steps"], recorder)
                    if cell == "collateral_write":
                        inject_collateral_write(SITE_DIR)
                    recorder.finish(page, answer)
                page.close()
                snapshot(SITE_DIR, run_dir, "after")
                cells.append((cell, run_dir, expects_pass))
            finally:
                process.terminate()
                process.wait(timeout=10)
        browser.close()
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--tasks", default="", help="comma-separated task numbers (default: all)")
    parser.add_argument("--cells", default="",
                        help="comma-separated cell names to drive (default: all), e.g. no_op")
    parser.add_argument("--grade-only", action="store_true",
                        help="re-grade the run directories under --out without driving browsers")
    args = parser.parse_args()
    wanted_cells = {value.strip() for value in args.cells.split(",") if value.strip()} or None

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / ".gitignore").write_text("*\n", encoding="utf-8")
    numbers = ([int(value) for value in args.tasks.split(",") if value.strip()]
               if args.tasks else sorted(WORKFLOWS))
    facts_by_task = {number: ground_truth.task_ground_truth(str(SITE_DIR / "instance_seed" / "berkeley.db"), number)
                     for number in numbers}

    results: list[dict[str, Any]] = []
    for number in numbers:
        if args.grade_only:
            cells = [(cell.name, cell, cell.name == "pass")
                     for cell in sorted((out_root / f"task_{number:02d}").iterdir()) if cell.is_dir()]
        else:
            cells = emit_cells(number, facts_by_task[number], out_root,
                               f"http://localhost:{DEFAULT_PORT}", wanted_cells)
        for cell, run_dir, expects_pass in cells:
            verdict = grade(run_dir)
            ok = verdict["pass"] is expects_pass
            results.append({"task": number, "cell": cell, "expected_pass": expects_pass,
                            "observed_pass": verdict["pass"], "reason": verdict["reason"], "ok": ok})
            flag = "ok " if ok else "MISMATCH"
            print(f"[{flag}] {number:>2} {cell:<16} expected={'PASS' if expects_pass else 'FAIL'} "
                  f"observed={verdict['pass']} reason={verdict['reason']}")

    summary = out_root / "summary.json"
    summary.write_text(json.dumps(results, indent=2), encoding="utf-8")
    failures = [row for row in results if not row["ok"]]
    print(f"\n{len(results)} cells, {len(failures)} mismatches -> {summary}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

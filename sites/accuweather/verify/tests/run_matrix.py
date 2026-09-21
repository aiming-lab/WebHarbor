#!/usr/bin/env python3
"""CONTRIBUTING §C validation matrix, driven through a real Chromium.

For every task: boot the mirror from a fresh copy of instance_seed, drive the
genuine workflow with Playwright (real clicks / form submits, screenshots in
the agent_demo/agent.py layout), snapshot the live SQLite DB as after.db, then
grade five run variants with the task's verifier:

  pass      genuine trajectory + correct answer + real after-state   -> PASS
  noop      homepage only, empty answer, clean DB                     -> FAIL
  shortcut  correct answer, no on-site navigation                     -> FAIL
  wrong     genuine trajectory, wrong answer                          -> FAIL
  mismatch  (stateful) genuine trajectory + correct answer, seed DB   -> FAIL

Usage (inside the agent_demo uv env, site venv python for Flask):
  uv run python run_matrix.py --site_dir <sites/accuweather> --python <venv python> --port 45002 --out <dir>
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cases import CASES  # noqa: E402

HERE = Path(__file__).resolve().parent
VERIFY_DIR = HERE.parent
PASSWORD = "TestPass123!"

# Browser actions per task: (kind, arg[, text]). "goto" navigates, "click"/"check"/"fill" act on the current page.
LOGIN = lambda email: [("goto", "/login"), ("fill", "input[name=email]", email), ("fill", "input[name=password]", PASSWORD), ("click", "button:has-text('Sign in')")]
ACTIONS = {
    0: [("goto", "/"), ("fill", "#site-search", "Phoenix"), ("click", "header .search button"), ("click", ".result")],
    1: [("goto", "/"), ("fill", "#site-search", "Portland"), ("click", "header .search button"), ("click", ".result:has-text('Maine')")],
    2: [("goto", "/"), ("click", "a.city[href='/weather/seattle-wa']"), ("click", ".tabs a:has-text('Hourly')")],
    3: [("goto", "/"), ("click", "a.city[href='/weather/miami-fl']"), ("click", ".tabs a:has-text('Daily')")],
    4: [("goto", "/"), ("click", "a.city[href='/weather/austin-tx']"), ("goto", "/"), ("click", "a.city[href='/weather/denver-co']")],
    5: [("goto", "/"), ("fill", "#site-search", "Springfield"), ("click", "header .search button"), ("click", ".result:has-text('Missouri')"), ("click", ".tabs a:has-text('Air Quality')")],
    6: LOGIN("alice.j@test.com") + [("fill", "#site-search", "Seattle"), ("click", "header .search button"), ("click", ".result"), ("click", ".actions form button"), ("click", "header a[href='/account']")],
    7: LOGIN("alice.j@test.com") + [("click", ".results .result:has-text('Boston')"), ("click", ".actions form button"), ("click", "header a[href='/account']")],
    8: LOGIN("bob.smith@test.com") + [("fill", "#site-search", "Chicago"), ("click", "header .search button"), ("click", ".result"), ("click", ".actions a.button"), ("check", "input[value=severe]"), ("check", "input[value=rain]"), ("click", "button:has-text('Save alerts')")],
    9: LOGIN("carol.w@test.com") + [("click", "a[href='/settings']"), ("check", "input[value=C]"), ("click", "button:has-text('Save settings')"), ("goto", "/"), ("click", "a.city[href='/weather/new-york-ny']")],
    10: [("goto", "/"), ("fill", ".hero input[name=q]", "94102"), ("click", ".hero button"), ("click", ".result")],
    11: [("goto", "/"), ("fill", "#site-search", "New Orleans"), ("click", "header .search button"), ("click", ".result:has-text('Orleans')"), ("click", ".tabs a:has-text('Radar')"), ("click", ".tabs a:has-text('Current Weather')")],
    12: [("goto", "/"), ("fill", "#site-search", "Los Angeles"), ("click", "header .search button"), ("click", ".result:has-text('Los Angeles')"), ("click", ".tabs a:has-text('Air Quality')"), ("fill", "#site-search", "San Francisco"), ("click", "header .search button"), ("click", ".result:has-text('San Francisco')"), ("click", ".tabs a:has-text('Air Quality')")],
    13: [("goto", "/"), ("click", "a.city[href='/weather/boston-ma']"), ("click", ".tabs a:has-text('Daily')")],
    14: [("goto", "/"), ("fill", "#site-search", "London"), ("click", "header .search button"), ("click", ".result"), ("click", ".tabs a:has-text('Air Quality')")],
    15: LOGIN("david.b@test.com") + [("goto", "/"), ("click", "a.city[href='/weather/phoenix-az']"), ("click", ".actions form button"), ("goto", "/"), ("click", "a.city[href='/weather/miami-fl']"), ("click", ".actions form button"), ("click", "header a[href='/account']")],
    16: [("goto", "/"), ("fill", "#site-search", "Portland"), ("click", "header .search button"), ("click", ".result:has-text('Oregon')"), ("fill", "#site-search", "Portland"), ("click", "header .search button"), ("click", ".result:has-text('Maine')")],
    17: [("goto", "/"), ("fill", "#site-search", "Toronto"), ("click", "header .search button"), ("click", ".result"), ("click", ".tabs a:has-text('Hourly')")],
    18: [("goto", "/"), ("click", "header a[href='/login']"), ("click", "a[href='/register']"), ("fill", "input[name=name]", "Jamie Lee"), ("fill", "input[name=email]", "jamie.lee@example.test"), ("fill", "input[name=password]", "Weather123!"), ("click", "button:has-text('Create account')"), ("fill", "#site-search", "Atlanta"), ("click", "header .search button"), ("click", ".result"), ("click", ".actions form button"), ("click", "header a[href='/account']")],
    19: [("goto", "/"), ("click", "a.city[href='/weather/phoenix-az']"), ("fill", "#site-search", "New Orleans"), ("click", "header .search button"), ("click", ".result:has-text('Orleans')")],
}


def wait_http(url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(f"site did not come up: {url}")


class Site:
    def __init__(self, site_dir: Path, python: str, port: int):
        self.site_dir, self.python, self.port, self.proc = site_dir, python, port, None

    def start(self) -> None:
        inst, seed = self.site_dir / "instance", self.site_dir / "instance_seed"
        shutil.rmtree(inst, ignore_errors=True)
        shutil.copytree(seed, inst)
        self.proc = subprocess.Popen([self.python, "-c", f"from app import app; app.run(host='127.0.0.1', port={self.port}, debug=False, use_reloader=False)"],
                                     cwd=self.site_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_http(f"http://127.0.0.1:{self.port}/")

    def stop(self) -> None:
        if self.proc:
            self.proc.kill(); self.proc.wait(); self.proc = None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def drive(page, base: str, actions, shots: Path, answer: str) -> list[dict]:
    steps = []
    idx = 0
    page.screenshot(path=str(shots / f"step_{idx:03d}.png"))
    for act in actions:
        kind, arg = act[0], act[1]
        url_before = page.url
        if kind == "goto":
            logged = {"action": "navigate", "params": {"url": base + arg}}
        elif kind == "fill":
            logged = {"action": "input", "params": {"index": 1, "text": act[2]}}
        else:
            logged = {"action": "click", "params": {"index": 1}}
        steps.append({"step": idx, "url": url_before, "title": page.title(), "thought": "", **logged,
                      "screenshot_before": f"step_{idx:03d}.png", "screenshot_after": f"step_{idx + 1:03d}.png"})
        if kind == "goto":
            page.goto(base + arg, wait_until="networkidle")
        elif kind == "fill":
            page.fill(arg, act[2])
        elif kind == "check":
            page.check(arg)
        else:
            page.click(arg); page.wait_for_load_state("networkidle")
        idx += 1
        page.screenshot(path=str(shots / f"step_{idx:03d}.png"))
    steps.append({"step": idx, "url": page.url, "title": page.title(), "thought": "", "action": "done",
                  "params": {"text": answer, "success": True}, "screenshot_before": f"step_{idx:03d}.png", "screenshot_after": f"step_{idx + 1:03d}.png"})
    page.screenshot(path=str(shots / f"step_{idx + 1:03d}.png"))
    return steps


def write_traj(run_dir: Path, task_id: str, base: str, steps: list[dict], answer: str) -> None:
    n = int(task_id.rsplit("--", 1)[1])
    traj = {"task_id": task_id, "task": "", "start_url": base + "/", "max_steps": 40, "steps": steps, "terminated": True,
            "termination_reason": "agent_done", "final_answer": answer, "success_self_report": True,
            "verifier_path": f"sites/accuweather/verify/verify_{n}.py", "judge_rubric": ""}
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))


def grade(n: int, run_dir: Path) -> dict:
    r = subprocess.run([sys.executable, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", str(run_dir), "--no_llm", "True"], capture_output=True, text=True)
    try:
        v = json.loads(r.stdout)
    except json.JSONDecodeError:
        v = {"pass": None, "reason": f"no JSON: {r.stderr[-300:]}"}
    v["rc"] = r.returncode
    return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site_dir", required=True); ap.add_argument("--python", required=True)
    ap.add_argument("--port", type=int, default=45002); ap.add_argument("--out", required=True)
    ap.add_argument("--tasks", default="")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    site = Site(Path(a.site_dir).resolve(), a.python, a.port)
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    tasks = [int(x) for x in a.tasks.split(",")] if a.tasks else sorted(CASES)
    matrix = {}
    seed_db = site.site_dir / "instance_seed" / "accuweather.db"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for n in tasks:
            case = CASES[n]; task_id = f"AccuWeather--{n}"
            site.start()
            try:
                ctx = browser.new_context(viewport={"width": 1280, "height": 900}); page = ctx.new_page()
                page.goto(site.base + "/", wait_until="networkidle")
                run = out / f"task{n}_pass"; shutil.rmtree(run, ignore_errors=True); (run / "screenshots").mkdir(parents=True)
                shutil.copy2(seed_db, run / "initial.db")
                steps = drive(page, site.base, ACTIONS[n], run / "screenshots", case["answer"])
                ctx.close()
                time.sleep(0.3)
                shutil.copy2(site.site_dir / "instance" / "accuweather.db", run / "after.db")
            finally:
                site.stop()
            write_traj(run, task_id, site.base, steps, case["answer"])
            row = {"pass": grade(n, run)}
            # noop: homepage only, empty answer, clean DB
            noop = out / f"task{n}_noop"; shutil.rmtree(noop, ignore_errors=True); (noop / "screenshots").mkdir(parents=True)
            for i in (0, 1):
                shutil.copy2(run / "screenshots" / "step_000.png", noop / "screenshots" / f"step_{i:03d}.png")
            shutil.copy2(seed_db, noop / "initial.db"); shutil.copy2(seed_db, noop / "after.db")
            write_traj(noop, task_id, site.base, [{"step": 0, "url": site.base + "/", "title": "AccuWeather", "thought": "", "action": "done", "params": {"text": "", "success": False}, "screenshot_before": "step_000.png", "screenshot_after": "step_001.png"}], "")
            row["noop"] = grade(n, noop)
            # shortcut: correct answer, no on-site navigation
            sc = out / f"task{n}_shortcut"; shutil.rmtree(sc, ignore_errors=True); shutil.copytree(noop, sc)
            write_traj(sc, task_id, site.base, [{"step": 0, "url": site.base + "/", "title": "AccuWeather", "thought": "", "action": "done", "params": {"text": case["answer"], "success": True}, "screenshot_before": "step_000.png", "screenshot_after": "step_001.png"}], case["answer"])
            row["shortcut"] = grade(n, sc)
            # wrong answer(s)
            row["wrong"] = []
            for k, (wrong_answer, _reason) in enumerate(case.get("wrong", [])):
                w = out / f"task{n}_wrong{k}"; shutil.rmtree(w, ignore_errors=True); shutil.copytree(run, w)
                write_traj(w, task_id, site.base, steps[:-1] + [dict(steps[-1], params={"text": wrong_answer, "success": True})], wrong_answer)
                row["wrong"].append(grade(n, w))
            # state mismatch (stateful only): claims success, DB unchanged
            if case.get("stateful"):
                mm = out / f"task{n}_mismatch"; shutil.rmtree(mm, ignore_errors=True); shutil.copytree(run, mm)
                shutil.copy2(seed_db, mm / "after.db")
                row["mismatch"] = grade(n, mm)
            matrix[n] = row
            summary = {k: (v["pass"] if isinstance(v, dict) else [x["pass"] for x in v]) for k, v in row.items()}
            reasons = {k: v.get("reason") for k, v in row.items() if isinstance(v, dict)}
            print(f"task {n:2d}: {summary}  reasons={reasons}", flush=True)
        browser.close()
    (out / "matrix.json").write_text(json.dumps(matrix, indent=1))
    ok = all(r["pass"]["pass"] is True and r["noop"]["pass"] is False and r["shortcut"]["pass"] is False
             and all(w["pass"] is False for w in r["wrong"]) and r.get("mismatch", {"pass": False})["pass"] is False for r in matrix.values())
    print("MATRIX", "OK" if ok else "HAS FAILURES")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

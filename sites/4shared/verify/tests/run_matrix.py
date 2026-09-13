#!/usr/bin/env python3
"""Validation matrix for the 4shared grading contract (CONTRIBUTING "C").

Consumes the PASS run dirs written by drive_tasks.py (<runs>/<N>/pass) and derives:
  noop      homepage only, empty answer, clean DB           -> every verifier must FAIL
  pass      the genuine Playwright run                       -> must PASS
  shortcut  correct answer + correct DB, but the trajectory
            never leaves the homepage (no on-site navigation) -> must FAIL
  wrong     genuine navigation, but a wrong answer / wrong
            persisted row (per-task mutation below)          -> must FAIL
  state     stateful tasks only: genuine trajectory + correct
            answer, but after.db == seed (nothing persisted)  -> must FAIL

Every verifier is executed as a subprocess with --no_llm True (no LLM is ever needed).
Exit status is non-zero if any cell disagrees with the expectation.

Usage (agent_demo uv env, so simpleArgParser is importable):
  uv run python sites/4shared/verify/tests/run_matrix.py --runs sites/4shared/verify/tests/runs
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFY_DIR = HERE.parent
STATEFUL = set(range(6, 20))

# Per-task "wrong" mutation: either a wrong final answer (answer=...) or a wrong
# persisted row (sql=[...] applied to a copy of the PASS after.db).
WRONG = {
    0: {"answer": "Morning Meadow Field Recording.mp3, uploaded by Open Source Desk."},
    1: {"answer": "London Skyline at Blue Hour.jpg, uploader Archive Lantern, resolution 3840 × 2160."},
    2: {"answer": "Pride and Prejudice.epub, displayed file size 4.2 MB."},
    3: {"answer": "Rain Garden Planting Guide.pdf, 49 pages, uploader Community Library."},
    4: {"answer": "ColorScope Palette Assistant.zip, version 5.0.1, license GPL-3.0."},
    5: {"answer": "City Cycling Route Planning is longer: 27:03 versus 19:05 for Open Data Mapping Basics."},
    6: {"sql": ["UPDATE downloads SET file_id = 82 WHERE id = (SELECT MAX(id) FROM downloads)",
                "UPDATE files SET download_count = download_count - 1 WHERE id = 81",
                "UPDATE files SET download_count = download_count + 1 WHERE id = 82"]},
    7: {"sql": ["UPDATE favorites SET file_id = 39 WHERE id = (SELECT MAX(id) FROM favorites)"]},
    8: {"sql": ["UPDATE saved_files SET file_id = 96 WHERE id = (SELECT MAX(id) FROM saved_files)"]},
    9: {"sql": ["UPDATE users SET location = 'Portland, Maine' WHERE id = 1"]},
    10: {"sql": ["UPDATE folders SET name = 'Survey Export' WHERE id = (SELECT MAX(id) FROM folders)"]},
    11: {"sql": ["UPDATE files SET public = 1 WHERE id = (SELECT MAX(id) FROM files)"]},
    12: {"sql": ["UPDATE files SET folder_id = 2 WHERE id = 123"]},
    13: {"sql": ["UPDATE files SET deleted = 1 WHERE id = 146", "UPDATE files SET deleted = 0 WHERE id = 134"]},
    14: {"sql": ["UPDATE shared_links SET permission = 'view' WHERE id = (SELECT MAX(id) FROM shared_links)"]},
    15: {"sql": ["UPDATE comments SET body = 'The coordinate exercises are ideal for our Sunday workshop.' WHERE id = (SELECT MAX(id) FROM comments)"]},
    16: {"answer": "My 4shared now shows plan Premium with a 500 GB storage allowance."},
    17: {"sql": ["UPDATE shared_links SET permission = 'download' WHERE id = (SELECT MAX(id) FROM shared_links)"]},
    18: {"answer": "Pride and Prejudice.epub has the most pages: 432 pages and 61 chapters. Saved it to My 4shared as david."},
    19: {"answer": "Local History Interview Toolkit.pdf, 66 pages in total; added to Favorites and downloaded."},
}


def run_verifier(n: int, run_dir: Path) -> dict:
    cmd = [sys.executable, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", str(run_dir), "--no_llm", "True"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        v = json.loads(r.stdout)
    except json.JSONDecodeError:
        v = {"pass": False, "reason": f"no JSON (rc={r.returncode}): {(r.stderr or r.stdout)[-300:]}", "evidence": []}
    v["returncode"] = r.returncode
    (run_dir / "verdict.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
    return v


def clone(src: Path, dst: Path) -> Path:
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("verdict.json"))
    return dst


def load_traj(d: Path) -> dict:
    return json.loads((d / "trajectory.json").read_text(encoding="utf-8"))


def save_traj(d: Path, t: dict) -> None:
    (d / "trajectory.json").write_text(json.dumps(t, indent=2), encoding="utf-8")


def make_noop(pass_dir: Path, dst: Path) -> Path:
    clone(pass_dir, dst)
    t = load_traj(dst)
    t["steps"] = [{"step": 0, "url": t["start_url"], "title": "4shared", "thought": "", "action": "done",
                   "params": {"text": "", "success": False}, "screenshot_before": "step_000.png", "screenshot_after": "step_001.png"}]
    t["final_answer"] = ""
    t["success_self_report"] = False
    save_traj(dst, t)
    shutil.copy2(dst / "initial.db", dst / "after.db")  # clean DB
    return dst


def make_shortcut(pass_dir: Path, dst: Path) -> Path:
    """Correct answer, correct DB, but every recorded URL is the homepage."""
    clone(pass_dir, dst)
    t = load_traj(dst)
    home = t["start_url"]
    kept = []
    for s in t["steps"]:
        s = dict(s)
        s["url"] = home
        if s["action"] in {"navigate"}:
            s["params"] = {"url": home}
        kept.append(s)
    t["steps"] = kept
    save_traj(dst, t)
    return dst


def make_wrong(n: int, pass_dir: Path, dst: Path) -> Path:
    clone(pass_dir, dst)
    spec = WRONG[n]
    if "answer" in spec:
        t = load_traj(dst)
        t["final_answer"] = spec["answer"]
        t["steps"][-1]["params"]["text"] = spec["answer"]
        save_traj(dst, t)
    if "sql" in spec:
        con = sqlite3.connect(dst / "after.db")
        try:
            for stmt in spec["sql"]:
                con.execute(stmt)
            con.commit()
        finally:
            con.close()
    return dst


def make_state(pass_dir: Path, dst: Path) -> Path:
    clone(pass_dir, dst)
    shutil.copy2(dst / "initial.db", dst / "after.db")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", default=str(HERE / "runs"))
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    runs = Path(args.runs).resolve()
    wanted = [int(x) for x in args.only.split(",") if x.strip()] or sorted(int(p.name) for p in runs.iterdir() if p.name.isdigit())
    rows = []
    bad = 0
    for n in wanted:
        pass_dir = runs / str(n) / "pass"
        if not (pass_dir / "trajectory.json").is_file():
            print(f"task {n}: no PASS run dir at {pass_dir}; run drive_tasks.py first")
            bad += 1
            continue
        cells = {
            "noop": (make_noop(pass_dir, runs / str(n) / "noop"), False),
            "pass": (pass_dir, True),
            "shortcut": (make_shortcut(pass_dir, runs / str(n) / "shortcut"), False),
            "wrong": (make_wrong(n, pass_dir, runs / str(n) / "wrong"), False),
        }
        if n in STATEFUL:
            cells["state"] = (make_state(pass_dir, runs / str(n) / "state"), False)
        row = {"task": n}
        for name, (d, expect) in cells.items():
            v = run_verifier(n, d)
            ok = bool(v.get("pass")) == expect and v["returncode"] == (0 if expect else 1)
            row[name] = ("PASS" if v.get("pass") else "FAIL") + ("" if ok else " (UNEXPECTED)") + ("" if v.get("pass") else f" [{v.get('reason')}]")
            if not ok:
                bad += 1
        rows.append(row)
    cols = ["noop", "pass", "shortcut", "wrong", "state"]
    print("| task | " + " | ".join(cols) + " |")
    print("|---|" + "|".join("---" for _ in cols) + "|")
    for row in rows:
        print(f"| 4shared--{row['task']} | " + " | ".join(row.get(c, "n/a") for c in cols) + " |")
    print(f"\n{'ALL EXPECTATIONS MET' if not bad else f'{bad} UNEXPECTED CELL(S)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""run_matrix.py — full verification matrix for the chronicle_jobs grading contract.

Legs, per task (0..29):
  honest     — drive_tasks.drive_task() with real browser interactions, then the
               task's deterministic verifier MUST PASS (fail-closed: any verifier
               error counts as FAIL).
  no_op      — a run that opens the homepage, does nothing, empty answer, clean
               DB. The verifier MUST FAIL (no false positives).
  shortcut   — the CORRECT final answer but no on-site navigation (homepage only).
               MUST FAIL (anti knowledge-shortcut gate).
  wrong      — the honest trajectory with the final answer replaced by a
               plausible-but-wrong answer, DB reset to seed. MUST FAIL.
  tamper_id  — the honest trajectory with task_id rewritten to a different task.
               MUST FAIL (anti-tamper).
  tamper_url — the honest trajectory with a foreign-origin URL injected.
               MUST FAIL (anti-tamper).
  tamper_shot— the honest run package with one screenshot file removed.
               MUST FAIL (anti-tamper).

Prints a per-leg matrix and exits 0 iff every honest leg PASSes and every
negative leg FAILs. Requires the review container (reset endpoint) and the
mirror to be up; run inside the agent_demo uv project:

    WH_CONTAINER=wh-rev-chronicle_jobs uv run python \
        sites/chronicle_jobs/verify/run_matrix.py --out_root /tmp/wh-rev-cj/matrix
"""
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import simpleArgParser as sap

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive_tasks  # noqa: E402

VERIFIER_DIR = Path(__file__).resolve().parent
NEG_LEGS = ("no_op", "shortcut", "wrong", "tamper_id", "tamper_url", "tamper_shot")


@dataclass
class MatrixArgs:
    tasks: str = "all"
    out_root: str = "/tmp/wh-rev-cj/matrix"
    legs: str = "all"


# plausible-but-wrong replacement answers, per task (index -> wrong text)
WRONG_ANSWERS = {
    0: "The search found 45 librarian jobs. The newest librarian job was posted on Aug 30, 2026.",
    1: "The Klarman Fellowship offers an annual stipend of $75,000 plus $8,000 per year for research "
       "expenses, and appointments must begin between 1 January and 1 March 2027.",
    2: "The posting shows salary grade UNAC Grade 25 with the exact dollar range $55,000-$62,000.",
    3: "The two provost postings state salaries of $250,000 and $500,000.",
    4: "The Boston location search found 78 jobs, including the tenure-track position 'Dean of Students'.",
    5: "There are 25 jobs in the '$200,000 or more' band. Two of them: 'Provost' with $150,000 and "
       "'President' with $175,000.",
    6: "There are 912 faculty positions listed on this board.",
    7: "Applications should be submitted by November 15, 2026 to receive full consideration.",
    8: "There are 22 chemistry jobs listed, and the Anchorage hiring institution is University of Alaska Fairbanks.",
    9: "There are 18 Wyoming jobs, and the top employer is Northwest College.",
    10: "There are 12 adjunct jobs in Texas.",
    11: "Applications can be assured full consideration if received by August 30, 2026.",
    12: "Applications should be received by December 1, 2026, and the college is Florida Southern College.",
    13: "The full-consideration deadline is September 15, 2026 and the job was posted on Aug 30, 2026.",
    14: "The employer is New York University and candidates must apply via Interfolio.",
    15: "The college actually hiring is Medaille College, and the job was posted on Sep 5, 2026.",
    16: "The remaining saved jobs are 'Part-Time Academic Coach' and 'Research Associate'.",
    17: "I now have 7 saved jobs in total.",
    18: "My shortlist contains 'Dean of the College of Arts' and 'Vice President for Research'.",
    19: "The status now shown for the Psychologist application is 'Applied'.",
    20: "The confirmation said my application was rejected, and the status shows 'Rejected'.",
    21: "I applied to 'Lab Assistant', its status is 'Withdrawn', submitted in August 2026.",
    22: "The confirmation said the alert was deleted and no emails will be sent to casey.r@test.com.",
    23: "The remaining alert searches for 'data'.",
    24: "I have 3 job alerts, searching for 'financial aid', 'registrar', and 'librarian'.",
    25: "The headline now reads 'Aspiring provost of student affairs'.",
    26: "The location shown on my profile is 'Austin, Texas'.",
    27: "The University of Delaware hub lists 22 job openings; a newest job is 'Athletics Director'.",
    28: "The hub shows the location Erbil, Iraq, and the About section says the university was founded in 2015.",
    29: "'Higher Ed's Middle-Manager Problem' is by Karin Fischer and argues that colleges need to hire "
        "more administrators; 'Higher Ed's Harvard Problem' is by Haseeb Kamal.",
}


def run_verifier(idx: int, run_dir: Path) -> dict:
    verifier = VERIFIER_DIR / f"verify_{idx}.py"
    r = subprocess.run([sys.executable, str(verifier), "--run_dir", str(run_dir), "--no_llm", "True"],
                       capture_output=True, text=True, timeout=300, cwd=str(VERIFIER_DIR))
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"pass": False, "reason": f"verifier crashed: {(r.stderr or r.stdout)[:300]}"}


def build_noop(out: Path, idx: int, browser) -> Path:
    """A no-op run: opens the homepage, reports nothing, DB untouched."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "screenshots").mkdir(exist_ok=True)
    base = drive_tasks.BASE
    page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
    page.goto(base + "/", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    page.screenshot(path=str(out / "screenshots" / "step_000.png"))
    body = page.inner_text("body")[:4000]
    step = {
        "step": 0, "url": base + "/", "title": "The Chronicle of Higher Education Jobs",
        "page_text": body, "thought": "Looking at the site homepage.",
        "action": "navigate", "params": {"url": base + "/"},
        "observed_text": body, "observed_text_before": body, "observed_text_after": body,
        "screenshot_before": "step_000.png", "screenshot_after": "step_000.png",
        "url_after": base + "/",
    }
    traj = {
        "task": drive_tasks.TASK_TEXTS.get(f"Chronicle Jobs--{idx}", ""),
        "task_id": f"Chronicle Jobs--{idx}",
        "start_url": base + "/", "model": "reviewer-noop", "max_steps": 40,
        "steps": [step], "terminated": True, "termination_reason": "agent_done",
        "final_answer": "", "judge_rubric": "", "verifier_path": "",
        "final_url": base + "/", "final_observed_text": body, "success_self_report": False,
    }
    (out / "trajectory.json").write_text(json.dumps(traj, indent=2))
    return out


def clone_with(traj_dir: Path, out: Path, mutate) -> Path:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(traj_dir, out, ignore=shutil.ignore_patterns("*.db"))
    traj = json.loads((out / "trajectory.json").read_text())
    mutate(traj, out)
    (out / "trajectory.json").write_text(json.dumps(traj, indent=2))
    return out


STATEFUL = {16, 17, 19, 20, 22, 23, 25, 26}
DB_PATH_IN = f"{drive_tasks.CONTAINER}:/opt/WebSyn/chronicle_jobs/instance/chronicle_jobs.db"
DB_PATH_SEED = f"{drive_tasks.CONTAINER}:/opt/WebSyn/chronicle_jobs/instance_seed/chronicle_jobs.db"


def stage_seed_cache(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    seed = cache_dir / "seed.db"
    r = subprocess.run(["docker", "cp", DB_PATH_SEED, str(seed)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"docker cp seed failed: {r.stderr}")
    return seed


def stage_dbs(run_dir: Path, seed_cache: Path, after_from_container: bool) -> None:
    """Pre-stage initial.db/after_db inside the run dir so the verifier does
    not need to docker cp anything (it prefers run_dir-local snapshots)."""
    shutil.copy(seed_cache, run_dir / "initial.db")
    if after_from_container:
        r = subprocess.run(["docker", "cp", DB_PATH_IN, str(run_dir / "after.db")],
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"docker cp instance failed: {r.stderr}")
    else:
        shutil.copy(seed_cache, run_dir / "after.db")


def run_legs(idxs, legs, out_root, results=None, quiet=False):
    """Execute the matrix legs for `idxs`; returns (results, failures).

    results: {task_id: {leg: verdict}}; failures: list of expectation strings.
    """
    from playwright.sync_api import sync_playwright

    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    if results is None:
        results = {}
    seed_cache = stage_seed_cache(out_root / "_dbcache")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for idx in idxs:
            tid = f"Chronicle Jobs--{idx}"
            row = results.setdefault(tid, {})
            if "honest" in legs:
                hdir = out_root / f"task_{idx:02d}" / "honest"
                hdir.mkdir(parents=True, exist_ok=True)
                drive_tasks.control_reset()
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                page = ctx.new_page()
                page.goto(drive_tasks.BASE + "/", wait_until="domcontentloaded")
                page.wait_for_timeout(300)
                run = drive_tasks.Run(page, hdir, tid, drive_tasks.TASK_TEXTS.get(tid, ""))
                drive_tasks.TASKS[idx](page, run)
                ctx.close()
                stage_dbs(hdir, seed_cache, after_from_container=(idx in STATEFUL))
                row["honest"] = run_verifier(idx, hdir)
            hdir = out_root / f"task_{idx:02d}" / "honest"

            # every negative leg runs against a freshly-reset (seed) DB; none of
            # them mutates anything, so ONE reset covers the whole block.
            if any(leg in legs for leg in NEG_LEGS):
                drive_tasks.control_reset()

            if "no_op" in legs:
                ndir = build_noop(out_root / f"task_{idx:02d}" / "no_op", idx, browser)
                stage_dbs(ndir, seed_cache, after_from_container=False)
                row["no_op"] = run_verifier(idx, ndir)

            if "shortcut" in legs:
                honest_traj = json.loads((hdir / "trajectory.json").read_text())
                sdir = build_noop(out_root / f"task_{idx:02d}" / "shortcut", idx, browser)
                traj = json.loads((sdir / "trajectory.json").read_text())
                traj["final_answer"] = honest_traj.get("final_answer", "")
                traj["success_self_report"] = True
                (sdir / "trajectory.json").write_text(json.dumps(traj, indent=2))
                stage_dbs(sdir, seed_cache, after_from_container=False)
                row["shortcut"] = run_verifier(idx, sdir)

            if "wrong" in legs:
                def _wrong(traj, _dir):
                    traj["final_answer"] = WRONG_ANSWERS[idx]
                    traj["success_self_report"] = True

                wdir = clone_with(hdir, out_root / f"task_{idx:02d}" / "wrong", _wrong)
                stage_dbs(wdir, seed_cache, after_from_container=False)
                row["wrong"] = run_verifier(idx, wdir)

            if "tamper_id" in legs:
                def _tid(traj, _dir):
                    traj["task_id"] = "Chronicle Jobs--99"

                tdir = clone_with(hdir, out_root / f"task_{idx:02d}" / "tamper_id", _tid)
                stage_dbs(tdir, seed_cache, after_from_container=False)
                row["tamper_id"] = run_verifier(idx, tdir)

            if "tamper_url" in legs:
                def _furl(traj, _dir):
                    if traj["steps"]:
                        traj["steps"][0]["url"] = "http://203.0.113.7:4000/searchjobs/?Keywords=provost"
                        traj["steps"][0]["url_after"] = "http://203.0.113.7:4000/searchjobs/?Keywords=provost"

                fdir = clone_with(hdir, out_root / f"task_{idx:02d}" / "tamper_url", _furl)
                stage_dbs(fdir, seed_cache, after_from_container=False)
                row["tamper_url"] = run_verifier(idx, fdir)

            if "tamper_shot" in legs:
                sdir = out_root / f"task_{idx:02d}" / "tamper_shot"
                if sdir.exists():
                    shutil.rmtree(sdir)
                shutil.copytree(hdir, sdir, ignore=shutil.ignore_patterns("*.db"))
                shots = sorted((sdir / "screenshots").glob("step_*.png"))
                if len(shots) > 1:
                    shots[1].unlink()
                stage_dbs(sdir, seed_cache, after_from_container=False)
                row["tamper_shot"] = run_verifier(idx, sdir)

            if not quiet:
                summary = " ".join(f"{leg}={'P' if row[leg]['pass'] else 'F'}" for leg in row)
                reasons = "; ".join(f"{leg}={row[leg].get('reason', '')[:60]}" for leg in row if not row[leg]["pass"])
                print(f"[{tid}] {summary}   {reasons[:200]}", flush=True)
        browser.close()

    failures = []
    for tid, row in results.items():
        if "honest" in row and not row["honest"]["pass"]:
            failures.append(f"{tid}: honest leg did not PASS ({row['honest'].get('reason')})")
        for leg in NEG_LEGS:
            if leg in row and row[leg]["pass"]:
                failures.append(f"{tid}: negative leg '{leg}' produced a FALSE POSITIVE")
    return results, failures


def main():
    args = sap.parse_args(MatrixArgs)
    idxs = list(range(30)) if args.tasks == "all" else [int(x) for x in args.tasks.split(",") if x.strip()]
    legs = ["honest"] + list(NEG_LEGS) if args.legs == "all" else args.legs.split(",")
    results, failures = run_legs(idxs, legs, args.out_root)
    print()
    if failures:
        print(f"MATRIX: FAIL ({len(failures)} problem legs)")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print(f"MATRIX: OK — {len(results)} tasks; honest legs PASS; all negative legs FAIL as required")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""selfcheck.py — deterministic self-test for the osu verifiers.

For every task it synthesizes three trajectories and runs the matching
verify_N.py with --no_llm (zero LLM calls), asserting the verdict:

  * GOLDEN     correct on-site nav + correct answer      -> PASS (exit 0)
  * WRONG_ANS  correct on-site nav + wrong answer        -> FAIL (exit 1)
  * NO_NAV     correct answer but never opened the page  -> FAIL (exit 1)

GOLDEN proves a correct trajectory is accepted; WRONG_ANS proves the hardcoded
ground truth actually discriminates; NO_NAV proves the navigation anti-shortcut
fires (a right answer with no page visit is rejected as memory recall).

Each verifier is run through `uv run` inside agent_demo/ so its simpleArgParser
dependency resolves — exactly how agent_demo/eval_judge.py invokes it.

Usage:  python3 sites/osu/verify/selfcheck.py
Exit 0 iff all 20 tasks pass all three assertions.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
REPO_ROOT = VERIFY_DIR.parents[2]
AGENT_DEMO = REPO_ROOT / "agent_demo"
BASE = "http://localhost:40016"

# Per task: nav_path (a URL that satisfies the verifier's nav check),
#           good answer (should PASS), bad answer (should FAIL on the answer check).
TASKS = {
    0:  ("/academics", "The dean of Fisher College of Business is Anil Makhija.",
         "The dean of Fisher College of Business is John Smith."),
    1:  ("/about", "Ohio State offers 36 varsity sports.",
         "Ohio State offers 25 varsity sports."),
    2:  ("/athletics", "Ohio State competes in the Big Ten Conference.",
         "Ohio State competes in the SEC."),
    3:  ("/athletics/ohio-state-buckeyes-football", "The head football coach is Ryan Day.",
         "The head football coach is Urban Meyer."),
    4:  ("/news/ohio-state-sets-record-for-research-expenditures-at-13-billion",
         "Ohio State's annual research expenditure is $1.3 billion.",
         "Ohio State's annual research expenditure is $500 million."),
    5:  ("/about", "The Ohio State University was founded in 1870.",
         "The Ohio State University was founded in 1900."),
    6:  ("/research/translational-data-analytics-institute",
         "TDAI focuses on data analytics, machine learning, health informatics, and social science.",
         "TDAI focuses on marine biology and volcanology."),
    7:  ("/about", "There are 46,820 undergraduate students enrolled.",
         "There are 12,000 undergraduate students enrolled."),
    8:  ("/academics",
         "Three colleges: College of Engineering, College of Medicine, and College of Nursing.",
         "Three colleges: the College of Wizardry, the School of Rock, and Hogwarts."),
    9:  ("/programs?college=engineering",
         "The College of Engineering offers BS, MS, and PhD degrees.",
         "The College of Engineering offers only short certificates."),
    10: ("/athletics/ohio-state-buckeyes-wrestling", "Wrestling competes at the Covelli Center.",
         "Wrestling competes at Value City Arena."),
    11: ("/research/ohio-supercomputer-center",
         "The Ohio Supercomputer Center is directed by David Bickel.",
         "The Ohio Supercomputer Center is directed by Jane Doe."),
    12: ("/programs/juris-doctor-jd", "Moritz College of Law offers the JD (Juris Doctor) degree.",
         "Moritz College of Law offers a two-year associate certificate."),
    13: ("/departments/department-of-mathematics",
         "The chair of the Department of Mathematics is James Cogdell.",
         "The chair of the Department of Mathematics is Alan Turing."),
    14: ("/athletics/ohio-state-buckeyes-football", "The home stadium is Ohio Stadium (the Horseshoe).",
         "The home stadium is Michigan Stadium."),
    15: ("/athletics/ohio-state-buckeyes-wrestling", "Ohio State wrestling has won 8 national championships.",
         "Ohio State wrestling has won three national championships."),
    16: ("/programs/master-of-business-administration-mba", "The MBA application deadline is April 1.",
         "The MBA application deadline is March 15."),
    17: ("/news/ohio-state-researchers-develop-breakthrough-cancer-immunotherapy",
         "The article 'Ohio State Researchers Develop Breakthrough Cancer Immunotherapy' reports a cancer immunotherapy breakthrough.",
         "There is an article about the football team winning a game."),
    18: ("/research/james-cancer-hospital-and-solove-research-institute",
         "The James Cancer Hospital and Solove Research Institute is directed by William Farrar.",
         "The James Cancer Hospital is directed by Mary Johnson."),
    19: ("/research/center-for-clean-hydrogen",
         "The Center for Clean Hydrogen focuses on hydrogen energy, fuel cells, green hydrogen, and energy storage.",
         "The Center for Clean Hydrogen focuses on nuclear fusion reactors."),
}


def make_run(tmp, task_id, nav_path, answer, include_nav):
    """Write a minimal trajectory.json (no screenshots — the LLM block is skipped
    under --no_llm) and return the run dir."""
    d = Path(tmp)
    steps = [{"url": f"{BASE}/", "action": "navigate",
              "screenshot_before": "step_000.png", "screenshot_after": "step_001.png"}]
    if include_nav:
        steps.append({"url": f"{BASE}{nav_path}", "action": "navigate",
                      "screenshot_before": "step_001.png", "screenshot_after": "step_002.png"})
    traj = {
        "task_id": task_id,
        "steps": steps,
        "final_answer": answer,
        "verifier_path": f"sites/osu/verify/verify_{task_id.split('--')[1]}.py",
    }
    (d / "trajectory.json").write_text(json.dumps(traj, indent=2))
    return str(d)


def run_verifier(idx, run_dir):
    vp = f"sites/osu/verify/verify_{idx}.py"
    # simpleArgParser parses booleans as value flags: `--no_llm True` (a bare
    # `--no_llm` errors with "expected one argument").
    cmd = ["uv", "run", "python", str(REPO_ROOT / vp),
           "--run_dir", run_dir, "--no_llm", "True"]
    r = subprocess.run(cmd, cwd=str(AGENT_DEMO), capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def main():
    all_ok = True
    rows = []
    for idx, (nav_path, good, bad) in TASKS.items():
        tid = f"Ohio State University--{idx}"
        cases = [("GOLDEN", good, True, 0),
                 ("WRONG_ANS", bad, True, 1),
                 ("NO_NAV", good, False, 1)]
        results = {}
        for name, answer, include_nav, expected_rc in cases:
            with tempfile.TemporaryDirectory() as tmp:
                run_dir = make_run(tmp, tid, nav_path, answer, include_nav)
                rc, out, err = run_verifier(idx, run_dir)
                ok = (rc == expected_rc)
                results[name] = ok
                if not ok:
                    all_ok = False
                    print(f"[MISMATCH] verify_{idx} {name}: expected rc={expected_rc} got rc={rc}")
                    print("  stdout:", out.strip()[:400])
                    if err.strip():
                        print("  stderr:", err.strip()[:300])
        verdict = "OK" if all(results.values()) else "FAIL"
        rows.append((idx, verdict, results))
        print(f"verify_{idx:<2} [{verdict}]  "
              f"golden={'P' if results['GOLDEN'] else 'x'} "
              f"wrong={'P' if results['WRONG_ANS'] else 'x'} "
              f"no_nav={'P' if results['NO_NAV'] else 'x'}")

    npass = sum(1 for _, v, _ in rows if v == "OK")
    print(f"\n{'='*48}\nself-check: {npass}/{len(TASKS)} tasks pass all 3 assertions")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

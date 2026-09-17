#!/usr/bin/env python3
"""Adversarial matrix for the PhET grading contract.

Builds fixtures from the canonical runs and asserts each verifier's verdict.
Fixtures are constructed test inputs, NOT agent runs: they never count as
trajectories and are written to a separate directory.

Cells per task:
  genuine        the canonical run                                 -> PASS
  noop           homepage only, empty answer, unchanged DB         -> FAIL
  wrong          canonical trajectory, answer corrupted            -> FAIL
  shortcut       correct answer, navigation stripped               -> FAIL
  dirty          read-only task, extra row written to after.db     -> FAIL
  state_missing  stateful task, after.db reset to initial          -> FAIL
"""
import json, shutil, sqlite3, subprocess, sys, pathlib, re

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runs', required=True, type=pathlib.Path,
                    help='Recorded per-task directories containing trajectory.json and DB snapshots')
parser.add_argument('--output', required=True, type=pathlib.Path)
args = parser.parse_args()
W = pathlib.Path(__file__).resolve().parents[4]
RUNS = args.runs.resolve()
OUT = args.output.resolve()
FIX = OUT / 'fixtures'
STATEFUL = {13, 14}

def verdict(n, run_dir, initial, after):
    r = subprocess.run(
        [sys.executable, str(W / "sites/phet_simulations/verify" / f"verify_{n}.py"),
         "--run_dir", str(run_dir), "--initial_db", str(initial),
         "--after_db", str(after), "--no_llm", "True"],
        capture_output=True, text=True, cwd=str(W))
    try:
        j = json.loads(r.stdout)
        return ("PASS" if j["pass"] else "FAIL"), j.get("reason", "")
    except Exception:
        return "ERROR", (r.stdout + r.stderr)[:160]

def clone(n, cell):
    d = FIX / f"task_{n}_{cell}"
    if d.exists(): shutil.rmtree(d)
    source = RUNS / f"task_{n}"
    shutil.copytree(source, d, ignore=shutil.ignore_patterns("screenshots"))
    # Screenshots are immutable inputs; only trajectory and DB fixtures mutate.
    if (source / "screenshots").exists():
        (d / "screenshots").symlink_to(source / "screenshots", target_is_directory=True)
    trajectory_path = d / "trajectory.json"
    trajectory = json.loads(trajectory_path.read_text())
    trajectory["run_kind"] = "adversarial_fixture"
    trajectory_path.write_text(json.dumps(trajectory, indent=2))
    return d

def main():
    FIX.mkdir(parents=True, exist_ok=True)
    rows = []
    for n in range(18):
        src = RUNS / f"task_{n}"
        base_i, base_a = src / "initial.db", src / "after.db"

        v, why = verdict(n, src, base_i, base_a)
        rows.append({"task": n, "cell": "genuine", "expected": "PASS", "verdict": v,
                     "match": v == "PASS", "reason": why})

        d = clone(n, "noop")
        t = json.loads((d / "trajectory.json").read_text())
        t["steps"] = [s for s in t["steps"] if False]
        t["final_answer"] = ""
        t["success_self_report"] = False
        (d / "trajectory.json").write_text(json.dumps(t, indent=2))
        shutil.copy(base_i, d / "after.db")
        v, why = verdict(n, d, base_i, d / "after.db")
        rows.append({"task": n, "cell": "noop", "expected": "FAIL", "verdict": v,
                     "match": v == "FAIL", "reason": why})

        # Replace the answer wholesale rather than perturbing digits. Shifting the
        # numbers inside an answer can leave every fact the task actually asks for
        # intact (task 2 only had incidental age ranges to corrupt), which tests
        # nothing.
        d = clone(n, "wrong")
        t = json.loads((d / "trajectory.json").read_text())
        t["final_answer"] = "Quantum Coin Toss, version 9.9.9, translated into 3 languages."
        (d / "trajectory.json").write_text(json.dumps(t, indent=2))
        v, why = verdict(n, d, base_i, base_a)
        rows.append({"task": n, "cell": "wrong", "expected": "FAIL", "verdict": v,
                     "match": v == "FAIL", "reason": why})

        d = clone(n, "shortcut")
        t = json.loads((d / "trajectory.json").read_text())
        t["steps"] = []
        (d / "trajectory.json").write_text(json.dumps(t, indent=2))
        v, why = verdict(n, d, base_i, base_a)
        rows.append({"task": n, "cell": "shortcut", "expected": "FAIL", "verdict": v,
                     "match": v == "FAIL", "reason": why})

        if n not in STATEFUL:
            d = clone(n, "dirty")
            shutil.copy(base_a, d / "after.db")
            con = sqlite3.connect(d / "after.db")
            con.execute("INSERT INTO saved_simulation (user_id, sim_id, notes, saved_at) "
                        "VALUES (1, 5, 'adversarial fixture', '2026-01-01 00:00:00')")
            con.commit(); con.close()
            v, why = verdict(n, d, base_i, d / "after.db")
            rows.append({"task": n, "cell": "dirty", "expected": "FAIL", "verdict": v,
                         "match": v == "FAIL", "reason": why})
        else:
            d = clone(n, "state_missing")
            shutil.copy(base_i, d / "after.db")
            v, why = verdict(n, d, base_i, d / "after.db")
            rows.append({"task": n, "cell": "state_missing", "expected": "FAIL", "verdict": v,
                         "match": v == "FAIL", "reason": why})

        # UPDATE preserves row counts: the former verifier silently accepted it.
        d = clone(n, "same_count_edit")
        with sqlite3.connect(d / "after.db") as con:
            con.execute("UPDATE user SET name='Unexpected edit' WHERE email='teacher@phet.test'")
        v, why = verdict(n, d, base_i, d / "after.db")
        rows.append({"task": n, "cell": "same_count_edit", "expected": "FAIL", "verdict": v,
                     "match": v == "FAIL", "reason": why})

        d = clone(n, "external_navigation")
        t = json.loads((d / "trajectory.json").read_text())
        from urllib.parse import urlsplit, urlunsplit
        for step in t["steps"]:
            url = urlsplit(step["url"])
            step["url"] = urlunsplit(("https", "external.example", url.path, url.query, url.fragment))
        (d / "trajectory.json").write_text(json.dumps(t, indent=2))
        v, why = verdict(n, d, base_i, base_a)
        rows.append({"task": n, "cell": "external_navigation", "expected": "FAIL", "verdict": v,
                     "match": v == "FAIL", "reason": why})

    targeted = {
        1: ("wrong_version", "Build an Atom: version 11.9.30, 104 languages."),
        9: ("larger_number", "Heat & Thermo: 119 simulations."),
        16: ("swapped_labels", "120 subjects, 5 simulations, 132 activities, 14 languages."),
        17: ("reversed_winner", "Membrane Transport has more languages than Build an Atom, a difference of 73."),
    }
    for n, (cell, answer) in targeted.items():
        d = clone(n, cell)
        t = json.loads((d / "trajectory.json").read_text()); t["final_answer"] = answer
        (d / "trajectory.json").write_text(json.dumps(t, indent=2))
        v, why = verdict(n, d, d / "initial.db", d / "after.db")
        rows.append({"task": n, "cell": cell, "expected": "FAIL", "verdict": v,
                     "match": v == "FAIL", "reason": why})
    for n, cell in [(0, "separate_facets"), (3, "no_release_details"), (4, "no_translation_detail"),
                    (8, "wrong_search"), (14, "wrong_role")]:
        d = clone(n, cell); t = json.loads((d / "trajectory.json").read_text())
        if n == 0:
            t["steps"] = [{"url": "http://localhost:40035/simulations?subject=biology"},
                          {"url": "http://localhost:40035/simulations?grade=elementary"}]
        elif n in (3, 4):
            t["steps"] = [step for step in t["steps"] if "/simulation/" not in step["url"]]
        elif n == 8:
            for step in t["steps"]: step["url"] = step["url"].replace("q=quantum", "q=classical")
        else:
            with sqlite3.connect(d / "after.db") as con:
                con.execute("UPDATE user SET role='student' WHERE email='test_user@phet.test'")
        (d / "trajectory.json").write_text(json.dumps(t, indent=2))
        v, why = verdict(n, d, d / "initial.db", d / "after.db")
        rows.append({"task": n, "cell": cell, "expected": "FAIL", "verdict": v,
                     "match": v == "FAIL", "reason": why})

    alternatives = {
        3: "Five new simulations were released in 2025 (out of the 12 in the New set).",
        6: "Arabic offers 119 simulations, versus the full catalog's 120.",
        7: "Arabic (Morocco) has 103 simulations; plain Arabic has 119.",
        9: "Heat & Thermo contains nine simulations.",
        11: "49 simulations are customizable, out of 120 in the full catalog.",
        12: "The teacher has four saved simulations.",
        14: "",
    }
    for n, answer in alternatives.items():
        d = clone(n, "valid_rephrasing")
        t = json.loads((d / "trajectory.json").read_text()); t["final_answer"] = answer
        (d / "trajectory.json").write_text(json.dumps(t, indent=2))
        v, why = verdict(n, d, d / "initial.db", d / "after.db")
        rows.append({"task": n, "cell": "valid_rephrasing", "expected": "PASS", "verdict": v,
                     "match": v == "PASS", "reason": why})

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(rows, indent=1))
    ok = sum(1 for r in rows if r["match"])
    print(f"{ok}/{len(rows)} cells match expectation")
    for r in rows:
        if not r["match"]:
            print(f"  MISMATCH task {r['task']} {r['cell']}: expected {r['expected']}, got {r['verdict']} ({r['reason']})")
    return 0 if ok == len(rows) else 1

sys.exit(main())

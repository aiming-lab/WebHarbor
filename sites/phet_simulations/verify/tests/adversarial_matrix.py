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

CASE = pathlib.Path(__file__).resolve().parent.parent
W = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                 "/Users/jinzexu/Documents/ChatGPT/webharbor/WHR-029-phet-simulations")
RUNS = CASE / "runs/canonical-2026-09-13"
OUT = CASE / "evidence/adversarial-canonical-2026-09-14"
FIX = OUT / "fixtures"
STATEFUL = {13, 14}

def verdict(n, run_dir, initial, after):
    r = subprocess.run(
        ["python3", str(W / "sites/phet_simulations/verify" / f"verify_{n}.py"),
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
    shutil.copytree(RUNS / f"task_{n}", d)
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

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(rows, indent=1))
    ok = sum(1 for r in rows if r["match"])
    print(f"{ok}/{len(rows)} cells match expectation")
    for r in rows:
        if not r["match"]:
            print(f"  MISMATCH task {r['task']} {r['cell']}: expected {r['expected']}, got {r['verdict']} ({r['reason']})")
    return 0 if ok == len(rows) else 1

sys.exit(main())

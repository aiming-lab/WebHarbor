#!/usr/bin/env python3
"""Self-contained adversarial matrix for the PhET grading contract.

The canonical inputs are synthesized from tracked templates below and the checked-out
instance seed. They are test fixtures, not agent trajectories. No reviewer-local path,
untracked run packet, network service, or mutable site instance is required.

Five matrix cells are exercised per selected task:
  genuine        valid synthetic run                                  -> PASS
  noop           homepage-only trajectory and empty answer             -> FAIL
  wrong          valid trajectory with a corrupted answer              -> FAIL
  shortcut       correct answer with all navigation replaced by home   -> FAIL
  dirty          read-only task with an extra saved row                 -> FAIL
  state_missing  stateful task with its required mutation removed       -> FAIL

A separate set of package-gate probes checks task identity, origin, action status,
termination, run_kind, and screenshot validation without changing the 90-cell matrix.
"""
import argparse
import binascii
import json
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
VERIFY_DIR = REPO_ROOT / "sites/phet_simulations/verify"
DEFAULT_SEED = REPO_ROOT / "sites/phet_simulations/instance_seed/phet_simulations.db"
BASE_URL = "http://localhost:40045/"
STATEFUL = {13, 14}

TASK_FIXTURES = {
    0: {
        "urls": ["simulations?view=filter&subject=biology&grade=elementary"],
        "answer": "Biology simulations suitable for Elementary School: Color Vision, Density, Natural Selection.",
    },
    1: {
        "urls": ["simulation/build-an-atom"],
        "answer": "Build an Atom is version 1.9.3 and is translated into 104 languages.",
    },
    2: {
        "urls": ["simulations?view=filter&subject=biology", "simulation/natural-selection"],
        "answer": "Natural Selection targets exactly these grade levels: Elementary School, High School, Middle School.",
    },
    3: {
        "urls": ["simulations?view=filter&release=new"],
        "answer": "There are 5 New simulations released during 2025.",
    },
    4: {
        "urls": ["simulations?view=filter&sort=translations"],
        "answer": "Build an Atom is first, with 104 translations.",
    },
    5: {
        "urls": ["simulations", "simulation/quantum-wave-interference"],
        "answer": "The most recently released simulation is Quantum Wave Interference, released 2026-09-10, filed under Chemistry, Physics.",
    },
    6: {"urls": ["translations"], "answer": "Arabic lists 119 simulations."},
    7: {"urls": ["translations"], "answer": "Arabic (Morocco) lists 103 simulations."},
    8: {
        "urls": ["search?q=quantum", "simulation/quantum-wave-interference"],
        "answer": "The search returned 7 results. The 2026 simulation is Quantum Wave Interference, version 1.0.0.",
    },
    9: {
        "urls": ["simulations?view=filter&topic=heat-and-thermo"],
        "answer": "The Heat & Thermo topic contains 9 simulations.",
    },
    10: {
        "urls": ["simulation/plinko-probability"],
        "answer": "Related simulations: Least-Squares Regression, Projectile Data Lab, Projectile Sampling Distributions, Quantum Measurement, Quantum Coin Toss.",
    },
    11: {"urls": ["simulations?view=customize"], "answer": "The Customize tab lists 49 simulations."},
    12: {"urls": ["login", "account"], "answer": "The teacher account has 4 saved simulations."},
    13: {
        "urls": ["login", "simulation/membrane-transport"],
        "answer": "Saved Membrane Transport to the student account with note: Synthetic matrix note.",
    },
    14: {
        "urls": ["register", "simulation/number-pairs"],
        "answer": "Created test_user@phet.test and saved Number Pairs to the new account.",
    },
    15: {
        "urls": ["teachers/activities?grade=elementary"],
        "answer": "The activity is Equivalent Fractions Game, with a duration of 50 minutes.",
    },
    16: {
        "urls": ["about"],
        "answer": "The About page lists 120 simulations, 5 subject areas, 132 languages, and 14 teacher activities.",
    },
    17: {
        "urls": ["simulation/build-an-atom", "simulation/membrane-transport"],
        "answer": "Build an Atom is translated into more languages: 104 versus 31, a difference of 73.",
    },
}


def _chunk(kind, payload):
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def make_png(width=320, height=200):
    """Return a deterministic valid PNG larger than the package gate's 1,000-byte floor."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + b"\x2b\x6f\xa3" * width
    pixels = zlib.compress(row * height, 9)
    note = b"Comment\x00" + b"synthetic verifier fixture; not an agent screenshot. " * 28
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"tEXt", note) + _chunk(b"IDAT", pixels) + _chunk(b"IEND", b"")


def mutate_state(task, database):
    if task not in STATEFUL:
        return
    with sqlite3.connect(database) as con:
        if task == 13:
            user_id = con.execute("SELECT id FROM user WHERE email=?", ("student@phet.test",)).fetchone()[0]
            sim_id = con.execute("SELECT id FROM simulation WHERE slug=?", ("membrane-transport",)).fetchone()[0]
            con.execute(
                "INSERT INTO saved_simulation (user_id, sim_id, notes, saved_at) VALUES (?, ?, ?, ?)",
                (user_id, sim_id, "Synthetic matrix note.", "2026-09-13 12:00:00"),
            )
        else:
            next_user = con.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM user").fetchone()[0]
            con.execute(
                "INSERT INTO user (id, email, name, password_hash, role, institution, country, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (next_user, "test_user@phet.test", "Synthetic Test User", "not-used", "teacher", "", "", "2026-09-13 12:00:00"),
            )
            sim_id = con.execute("SELECT id FROM simulation WHERE slug=?", ("number-pairs",)).fetchone()[0]
            con.execute(
                "INSERT INTO saved_simulation (user_id, sim_id, notes, saved_at) VALUES (?, ?, ?, ?)",
                (next_user, sim_id, "", "2026-09-13 12:00:00"),
            )


def write_genuine(task, destination, seed):
    fixture = TASK_FIXTURES[task]
    destination.mkdir(parents=True, exist_ok=True)
    screenshots = destination / "screenshots"
    screenshots.mkdir()
    shutil.copy2(seed, destination / "initial.db")
    shutil.copy2(seed, destination / "after.db")
    mutate_state(task, destination / "after.db")

    steps = []
    previous = BASE_URL
    for index, suffix in enumerate(fixture["urls"], 1):
        url = BASE_URL + suffix
        before = f"step_{index:03d}_before.png"
        after = f"step_{index:03d}_after.png"
        (screenshots / before).write_bytes(make_png())
        (screenshots / after).write_bytes(make_png())
        steps.append({
            "index": index,
            "action": f"Synthetic fixture navigation {index}",
            "url_before": previous,
            "url": url,
            "url_after": url,
            "action_result": {"success": True, "detail": "synthetic matrix fixture"},
            "screenshot_before": before,
            "screenshot_after": after,
        })
        previous = url
    trajectory = {
        "task_id": f"PhET Interactive Simulations--{task}",
        "start_url": BASE_URL,
        "run_kind": "synthetic_test_fixture",
        "steps": steps,
        "final_url": previous,
        "final_answer": fixture["answer"],
        "terminated": True,
        "termination_reason": "synthetic_fixture_complete",
    }
    (destination / "trajectory.json").write_text(json.dumps(trajectory, indent=2) + "\n")


def clone(source, output, task, cell):
    destination = output / "fixtures" / f"task_{task}_{cell}"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination


def load_trajectory(run_dir):
    return json.loads((run_dir / "trajectory.json").read_text())


def save_trajectory(run_dir, trajectory):
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2) + "\n")


def verdict(task, run_dir, python, repo_root):
    command = [
        python,
        str(repo_root / "sites/phet_simulations/verify" / f"verify_{task}.py"),
        "--run_dir", str(run_dir),
        "--initial_db", str(run_dir / "initial.db"),
        "--after_db", str(run_dir / "after.db"),
        "--no_llm", "True",
    ]
    result = subprocess.run(command, capture_output=True, text=True, cwd=repo_root)
    try:
        payload = json.loads(result.stdout)
        return ("PASS" if payload["pass"] else "FAIL"), payload.get("reason", ""), payload.get("evidence", [])
    except Exception:
        return "ERROR", (result.stdout + result.stderr)[:400], []


def add_result(rows, task, cell, expected, run_dir, python, repo_root, expected_reason=None):
    actual, reason, evidence = verdict(task, run_dir, python, repo_root)
    match = actual == expected and (expected_reason is None or reason == expected_reason)
    rows.append({
        "task": task,
        "cell": cell,
        "expected": expected,
        "verdict": actual,
        "expected_reason": expected_reason,
        "reason": reason,
        "match": match,
        "evidence": evidence,
    })


def run_matrix(tasks, output, seed, python, repo_root):
    canonical = output / "canonical"
    canonical.mkdir(parents=True, exist_ok=True)
    rows = []
    for task in tasks:
        source = canonical / f"task_{task}"
        write_genuine(task, source, seed)
        add_result(rows, task, "genuine", "PASS", source, python, repo_root)

        run_dir = clone(source, output, task, "noop")
        trajectory = load_trajectory(run_dir)
        trajectory["steps"] = trajectory["steps"][:1]
        for field in ("url_before", "url", "url_after"):
            trajectory["steps"][0][field] = BASE_URL
        trajectory["final_answer"] = ""
        trajectory["final_url"] = BASE_URL
        save_trajectory(run_dir, trajectory)
        shutil.copy2(run_dir / "initial.db", run_dir / "after.db")
        add_result(rows, task, "noop", "FAIL", run_dir, python, repo_root)

        run_dir = clone(source, output, task, "wrong")
        trajectory = load_trajectory(run_dir)
        trajectory["final_answer"] = "Quantum Coin Toss, version 9.9.9, translated into 3 languages."
        save_trajectory(run_dir, trajectory)
        add_result(rows, task, "wrong", "FAIL", run_dir, python, repo_root)

        run_dir = clone(source, output, task, "shortcut")
        trajectory = load_trajectory(run_dir)
        for step in trajectory["steps"]:
            for field in ("url_before", "url", "url_after"):
                step[field] = BASE_URL
        trajectory["final_url"] = BASE_URL
        save_trajectory(run_dir, trajectory)
        add_result(rows, task, "shortcut", "FAIL", run_dir, python, repo_root)

        if task not in STATEFUL:
            run_dir = clone(source, output, task, "dirty")
            with sqlite3.connect(run_dir / "after.db") as con:
                con.execute(
                    "INSERT INTO saved_simulation (user_id, sim_id, notes, saved_at) VALUES (?, ?, ?, ?)",
                    (1, 5, "adversarial fixture", "2026-09-13 12:00:00"),
                )
            add_result(rows, task, "dirty", "FAIL", run_dir, python, repo_root)
        else:
            run_dir = clone(source, output, task, "state_missing")
            shutil.copy2(run_dir / "initial.db", run_dir / "after.db")
            add_result(rows, task, "state_missing", "FAIL", run_dir, python, repo_root)
    return rows


def run_gate_probes(output, seed, python, repo_root):
    source = output / "canonical" / "task_0"
    if not source.exists():
        write_genuine(0, source, seed)
    probes = []

    def probe(name, expected_reason, mutate):
        run_dir = clone(source, output, 0, f"gate_{name}")
        trajectory = load_trajectory(run_dir)
        mutate(run_dir, trajectory)
        save_trajectory(run_dir, trajectory)
        rows = []
        add_result(rows, 0, name, "FAIL", run_dir, python, repo_root, expected_reason)
        probes.extend(rows)

    probe("task_id", "run_package_task_id", lambda _d, t: t.__setitem__("task_id", "PhET Interactive Simulations--17"))
    probe("start_url", "run_package_start_url", lambda _d, t: t.__setitem__("start_url", "https://example.com/"))
    probe("run_kind", "run_package_run_kind", lambda _d, t: t.__setitem__("run_kind", ""))
    probe("url", "run_package_url", lambda _d, t: t["steps"][0].__setitem__("url", "http://example.com:40045/simulations"))
    probe("action", "run_package_action", lambda _d, t: t["steps"][0]["action_result"].__setitem__("success", False))
    probe("termination", "run_package_termination", lambda _d, t: t.__setitem__("terminated", False))

    def remove_screenshot(run_dir, trajectory):
        (run_dir / "screenshots" / trajectory["steps"][0]["screenshot_after"]).unlink()
    probe("missing_screenshot", "run_package_screenshot", remove_screenshot)

    def shrink_screenshot(run_dir, trajectory):
        path = run_dir / "screenshots" / trajectory["steps"][0]["screenshot_after"]
        path.write_bytes(make_png(100, 100))
    probe("small_screenshot", "run_package_screenshot", shrink_screenshot)
    return probes


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--seed-db", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, help="Keep generated fixtures and JSON results here")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--tasks", type=int, nargs="*", default=list(range(18)))
    return parser.parse_args()


def main():
    args = parse_args()
    tasks = sorted(set(args.tasks))
    if not tasks or any(task not in TASK_FIXTURES for task in tasks):
        raise SystemExit("--tasks must contain values from 0 through 17")
    if not args.seed_db.is_file():
        raise SystemExit(f"seed DB not found: {args.seed_db}; run scripts/fetch_assets.sh first")
    temporary = None
    if args.output is None:
        temporary = tempfile.TemporaryDirectory(prefix="phet-adversarial-")
        output = Path(temporary.name)
    else:
        output = args.output.resolve()
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)

    rows = run_matrix(tasks, output, args.seed_db.resolve(), args.python, args.repo_root.resolve())
    probes = run_gate_probes(output, args.seed_db.resolve(), args.python, args.repo_root.resolve())
    (output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    (output / "run-package-gate-results.json").write_text(json.dumps(probes, indent=2) + "\n")
    matched = sum(row["match"] for row in rows)
    gate_matched = sum(row["match"] for row in probes)
    print(f"matrix: {matched}/{len(rows)} cells match expectation")
    print(f"run-package gate: {gate_matched}/{len(probes)} probes match expected failure reasons")
    for row in rows + probes:
        if not row["match"]:
            print(
                f"MISMATCH task {row['task']} {row['cell']}: expected {row['expected']}"
                f" reason={row['expected_reason']!r}, got {row['verdict']} reason={row['reason']!r}"
            )
    print(f"results: {output}")
    result = 0 if matched == len(rows) and gate_matched == len(probes) else 1
    if temporary is not None:
        temporary.cleanup()
    return result


if __name__ == "__main__":
    raise SystemExit(main())

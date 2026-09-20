#!/usr/bin/env python3
"""Google Finance deterministic grading entrypoints."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from answer_checks import answer_ok
from navigation import navigation_ok
from state_checks import state_ok

SITE = "google_finance"
TASK_COUNT = 20


PASS_ANSWERS = {
    0: "There are 5 indexes. IBOVESPA (IBOV) is highest; day high 187,092.70 and day low 184,438.47.",
    1: "Coca-Cola's ex-dividend date is Oct 4, 2026 and its quarterly dividend is $0.44.",
    2: "There are 9 key moments. The latest says: Biggest one-day drop in months: 3.5%.",
    3: "Bitcoin's 52-week high is $299,489.06 and its 52-week low is $110,249.89.",
    4: "2,500 USD converts to 404,676.0000 JPY at 1 USD = 161.870400 JPY.",
    5: "The publisher is South China Morning Post and the publication date is Jul 24, 2026.",
    6: "Intel's consensus is Hold, based on 14 analyst ratings, with a $104.21 average target.",
    7: "For Jun 2026, Alphabet revenue is 98.36B and net profit margin is 22.77%.",
    8: "For Jun 2026, Walmart total assets are 506.63B and total liabilities are 385.10B.",
    9: "Chevron's 2025 annual revenue is 182.60B.",
    10: "NVIDIA's 1Y change is -18.57%.",
    11: "Marathon Petroleum (MPC) is largest at 12.69%.",
    12: "Jun 2025 has the largest positive EPS surprise at +9.08%.",
    13: "Honeywell (HON) is lowest at 16.47; LMT is 22.45 and RTX is 26.97.",
    14: "Ford Motor (F) is lowest among the top five at a P/E of 32.19.",
    15: "There are 26 companies; Mastercard (MA) has the highest yield among the largest six at 2.03%.",
    16: "Southern Company (SO) has the highest Utilities-stock dividend yield at 3.41%.",
    17: "Realty Income (O) has the highest dividend yield in Dividend income at 4.49%.",
    18: "Growth ideas has a total gain of +33.23%; NVDA is largest at +121.64%.",
    19: "The JPM position market value is $9,203.00 and its gain is +22.71%.",
}


EXPECTED = {
    0: "5 indexes; IBOVESPA/IBOV; high 187,092.70; low 184,438.47",
    1: "Oct 4, 2026; quarterly dividend 0.44",
    2: "9 moments; Biggest one-day drop in months: 3.5%",
    3: "52-week high 299,489.06; low 110,249.89",
    4: "404,676.0000 JPY at 161.870400",
    5: "South China Morning Post; Jul 24, 2026",
    6: "Hold; 14 ratings; average target 104.21",
    7: "Jun 2026; revenue 98.36B; margin 22.77%",
    8: "Jun 2026; assets 506.63B; liabilities 385.10B",
    9: "2025 revenue 182.60B",
    10: "-18.57%",
    11: "Marathon Petroleum/MPC; 12.69%",
    12: "Jun 2025; +9.08%",
    13: "HON lowest 16.47; LMT 22.45; RTX 26.97",
    14: "Ford; 32.19",
    15: "26 companies; Mastercard; 2.03%",
    16: "Southern Company; 3.41%",
    17: "Realty Income; 4.49%",
    18: "total +33.23%; NVDA +121.64%",
    19: "market value 9,203.00; gain +22.71%, plus matching DB state",
}


def load_run(run_dir):
    return json.loads((Path(run_dir) / "trajectory.json").read_text())


def evaluate(task_index, traj, initial_db="", after_db="", container=""):
    answer = str(traj.get("final_answer") or "").strip()
    nav_ok, pages = navigation_ok(task_index, traj)
    checks = [
        ("final_answer_nonempty", bool(answer), "Answer must be nonempty"),
        ("required_navigation", nav_ok, f"observed pages={pages!r}"),
        (
            "frozen_answer",
            answer_ok(task_index, answer),
            "Check labelled facts, entities, units, dates and polarity",
        ),
    ]
    if task_index == 19:
        ok, detail = state_ok(initial_db, after_db)
        checks.append(("portfolio_after_state", ok, detail))
    return {
        "task_id": f"Google Finance--{task_index}",
        "pass": all(ok for _, ok, _ in checks),
        "reason": next((name for name, ok, _ in checks if not ok), ""),
        "evidence": [
            f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}"
            for name, ok, detail in checks
        ],
    }


def resolve_snapshots(args, directory):
    if args.initial_db or args.after_db:
        return args.initial_db, args.after_db
    run_dir = Path(args.run_dir)
    initial = run_dir / "initial_state.db"
    after = run_dir / "after_state.db"
    if initial.exists() or after.exists():
        # Never combine one saved snapshot with unrelated live state.
        return str(initial), str(after)
    if not args.container:
        return "", ""
    paths = []
    for kind in ("instance_seed", "instance"):
        target = str(Path(directory) / (kind + ".db"))
        result = subprocess.run(
            [
                "docker",
                "cp",
                f"{args.container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db",
                target,
            ],
            capture_output=True,
            text=True,
        )
        paths.append(target if result.returncode == 0 else "")
    return tuple(paths)


def main(task_index):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument("--container", default=os.environ.get("WH_CONTAINER", ""))
    parser.add_argument("--no_llm", nargs="?", const="True", default="True")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="google-finance-grade-") as temp:
        initial, after = resolve_snapshots(args, temp) if task_index == 19 else ("", "")
        verdict = evaluate(task_index, load_run(args.run_dir), initial, after)
    print(json.dumps(verdict, indent=2))
    sys.exit(0 if verdict["pass"] else 1)

#!/usr/bin/env python3
"""Randomly sample N task dirs for the harness smoke test.

Samples from the rendered task dirs with a recorded seed for
reproducibility, writes the selection to JSON, and creates a symlink
dataset dir runnable with `harbor run -p <dir>`.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-root", required=True)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--out-dir", required=True, help="symlink dataset dir")
    parser.add_argument("--selection-out", required=True, help="JSON record of the sample")
    args = parser.parse_args()

    tasks_root = Path(args.tasks_root)
    task_dirs = sorted(p for p in tasks_root.iterdir() if (p / "task.toml").is_file())
    rng = random.Random(args.seed)
    picked = rng.sample(task_dirs, args.n)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.iterdir():
        old.unlink()
    for path in picked:
        (out_dir / path.name).symlink_to(path.resolve())

    selection = {
        "seed": args.seed,
        "pool_size": len(task_dirs),
        "n": args.n,
        "tasks": [
            {
                "dir": p.name,
                "site": p.name.rsplit("--", 1)[0],
                "index": p.name.rsplit("--", 1)[1],
            }
            for p in picked
        ],
    }
    Path(args.selection_out).write_text(json.dumps(selection, indent=1), encoding="utf-8")
    print(f"sampled {args.n} of {len(task_dirs)} tasks (seed {args.seed}) -> {out_dir}")
    for entry in selection["tasks"]:
        print(" ", entry["site"], entry["index"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--22.

Find the latest Team transactions in the NBA within the past week.

Ground truth (hardcoded; frozen from the served /nba/transactions page —
transaction rows dated inside the week before the pinned April 10, 2024):
    Tobias Harris day-to-day (76ers, Apr 9); Caleb Martin 4-year extension
    (Heat, Apr 9); Aaron Gordon $130M extension (Nuggets, Apr 9); Joel Embiid
    ruled out indefinitely, left knee (76ers, Apr 8); OG Anunoby extension
    agreement (Knicks, Apr 8); LeBron James contract-extension talks (Lakers,
    Apr 8); Ben Simmons waived, becomes free agent (Nets, Apr 7); Bobby Portis
    re-signed 3-year (Bucks, Apr 7); SGA contract extension (Thunder, Apr 7);
    Spencer Dinwiddie signed (Lakers, Apr 6); Mikal Bridges 4-year $90M
    extension (Knicks, Apr 6); Luka Doncic Player of the Week (Mavericks,
    Apr 5); Jayson Tatum supermax $163M (Celtics, Apr 4).

Checks: run-package gate + answer + navigation to a transactions page + >=4
real transactions from that window + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, contains_all, contains_any,
                        num_in, word_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--22', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_transactions", navigated_to(t, "/transactions"),
            "must open the NBA (or a team) transactions page")
    anchors = [
        ("harris", contains_all(fa, ["harris"]) and
            (contains_any(fa, ["ankle", "day-to-day", "day to day"]))),
        ("caleb_martin", contains_all(fa, ["caleb", "martin"])),
        ("aaron_gordon", contains_all(fa, ["gordon"]) and
            (num_in(fa, 130) or contains_any(fa, ["nugget", "aaron"]))),
        ("embiid", contains_all(fa, ["embiid"]) and
            (contains_any(fa, ["knee", "indefinitely"]) or word_in(fa, "out"))),
        ("anunoby", contains_all(fa, ["anunoby"]) and
            contains_any(fa, ["knick", "new york", "extension", "agreement"])),
        ("lebron", contains_all(fa, ["lebron"]) and
            contains_any(fa, ["contract", "extension"])),
        ("simmons", contains_all(fa, ["simmons"]) and
            contains_any(fa, ["waiv", "free agent"])),
        ("portis", contains_all(fa, ["portis"]) and
            contains_any(fa, ["buck", "milwaukee", "re-sign", "resign"])),
        ("sga", contains_any(fa, ["gilgeous-alexander", "sga"]) and
            contains_any(fa, ["thunder", "extension"])),
        ("dinwiddie", contains_all(fa, ["dinwiddie"])),
        ("bridges", contains_all(fa, ["bridges"]) and
            (num_in(fa, 90) or contains_any(fa, ["extension", "knick"]))),
        ("doncic", contains_all(fa, ["doncic"]) and
            contains_any(fa, ["player of the week", "week"])),
        ("tatum", contains_all(fa, ["tatum"]) and
            (num_in(fa, 163) or contains_any(fa, ["supermax", "extension"]))),
    ]
    matched = [name for name, ok in anchors if ok]
    j.check("answer_four_transactions", len(matched) >= 4,
            f"matched={len(matched)}: {matched}")
    j.emit()

if __name__ == "__main__":
    main()

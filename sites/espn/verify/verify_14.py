#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--14.

Find the latest news about NBA trades or player movements on ESPN and report
the most recent trade deal OR player acquisition.

Ground truth (hardcoded; frozen from the served /nba/transactions page — the
trade/acquisition/movement rows are):
    James Harden traded 76ers->LA Clippers (TRADE, 2023-10-31); Mikal Bridges
    4-year $90M extension (SIGN, Knicks, Apr 6); Jayson Tatum supermax $163M
    (SIGN, Celtics, Apr 4); Ben Simmons waived (WAIVE, Nets, Apr 7); LeBron
    James contract-extension talks (CONTRACT, Lakers, Apr 8); Caleb Martin
    4-year extension (SIGNING, Heat, Apr 9); Aaron Gordon $130M extension
    (SIGNING, Nuggets, Apr 9); OG Anunoby extension agreement (SIGNING,
    Knicks, Apr 8); Bobby Portis re-signed (SIGNING, Bucks, Apr 7); Spencer
    Dinwiddie signed (SIGNING, Lakers, Apr 6); SGA extension (SIGNING,
    Thunder, Apr 7).

Checks: run-package gate + answer + navigation (transactions / NBA news) + at
least one real trade-or-acquisition fact (injury updates and awards do not
qualify) + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--14', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_transactions",
            navigated_any(t, ["/transactions", "/nba/news", "/story/nba-trade-deadline"]),
            "must open the NBA transactions page, NBA news, or the trade article")
    anchors = [
        ("harden_trade", contains_all(fa, ["harden", "clippers"])),
        ("caleb_martin", contains_all(fa, ["caleb", "martin"])),
        ("aaron_gordon", contains_all(fa, ["gordon"]) and
            (num_in(fa, 130) or contains_any(fa, ["nugget", "aaron"]))),
        ("anunoby", contains_all(fa, ["anunoby"]) and
            contains_any(fa, ["knick", "new york", "extension", "agreement"])),
        ("portis", contains_all(fa, ["portis"]) and
            contains_any(fa, ["buck", "milwaukee", "re-sign", "resign", "3-year", "three-year"])),
        ("dinwiddie", contains_all(fa, ["dinwiddie"])),
        ("bridges", contains_all(fa, ["bridges"]) and
            (num_in(fa, 90) or contains_any(fa, ["extension", "knick"]))),
        ("tatum", contains_all(fa, ["tatum"]) and
            (num_in(fa, 163) or contains_any(fa, ["supermax", "extension"]))),
        ("simmons_waived", contains_all(fa, ["simmons"]) and
            contains_any(fa, ["waiv", "free agent"])),
        ("lebron_contract", contains_all(fa, ["lebron"]) and
            contains_any(fa, ["contract", "extension"])),
        ("sga_extension", (contains_any(fa, ["gilgeous-alexander", "sga"]) and
            contains_any(fa, ["thunder", "extension"]))),
    ]
    matched = [name for name, ok in anchors if ok]
    j.check("answer_trade_or_acquisition", len(matched) >= 1,
            f"matched={matched}")
    j.emit()

if __name__ == "__main__":
    main()

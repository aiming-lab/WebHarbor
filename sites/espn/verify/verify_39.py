#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--39.

Check the New York Jets Depth Chart in the NFL section of ESPN and identify
the players listed as injured in the 2ND position.

Ground truth (hardcoded; frozen from the served
/team/nfl/new-york-jets/depth-chart page — players carrying an injury tag in
the 2ND column):
    Zach Wilson (QB, 'Injured - Out'), Connor McGovern (C, DAY-TO-DAY - hip),
    Will McDonald IV (DE, DAY-TO-DAY - ankle), Wes Schweitzer (LG, DAY-TO-DAY
    - back), Olu Fashanu (LT, OUT - ankle sprain), Mike Williams (WR,
    DAY-TO-DAY - knee), Carter Warren (RT, OUT - knee).

Checks: run-package gate + answer + navigation to the Jets depth chart + >=4
of the seven injured 2ND-position players named + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, contains_all, contains_any,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--39', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_jets_depth_chart",
            navigated_to(t, "/team/nfl/new-york-jets/depth-chart"),
            "the task names the Jets Depth Chart page")
    checks = [
        ("zach wilson", contains_all(fa, ["zach", "wilson"])),
        ("connor mcgovern", contains_all(fa, ["mcgovern"])),
        ("will mcdonald", contains_all(fa, ["mcdonald"])),
        ("wes schweitzer", contains_all(fa, ["schweitzer"])),
        ("olu fashanu", contains_all(fa, ["fashanu"])),
        ("mike williams", contains_all(fa, ["mike", "williams"])),
        ("carter warren", contains_all(fa, ["warren"])),
    ]
    matched = [name for name, ok in checks if ok]
    j.check("answer_four_injured_2nd", len(matched) >= 4,
            f"injured 2ND-position players named={matched}")
    j.emit()

if __name__ == "__main__":
    main()

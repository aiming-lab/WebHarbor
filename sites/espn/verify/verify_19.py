#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--19.

Who has the highest salary in Boston Celtics Roster 2023-24?

Ground truth (hardcoded; frozen from the served /team/nba/boston-celtics/roster
page — the SALARY column shows):
    Kristaps Porzingis $36,000,000 is the highest salary on the roster
    (Jayson Tatum $32,600,000 is second; Jrue Holiday / Jaylen Brown
    $30,400,000 follow).  The 'Inside the Boston Celtics payroll picture'
    article agrees (Porzingis $36M tops the payroll).

Checks: run-package gate + answer + navigation (Celtics roster page or the
payroll article) + Porzingis named with the $36,000,000 salary + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, contains_all,
                        contains_any, dollar_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--19', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_celtics_roster",
            navigated_any(t, ["/team/nba/boston-celtics/roster",
                              "/story/inside-the-boston-celtics-payroll-picture",
                              "/team/nba/boston-celtics"]),
            "must open the Celtics roster page or the Celtics payroll article")
    j.check("answer_porzingis",
            contains_any(fa, ["porzingis", "porziņģis"]),
            "highest salary: Kristaps Porzingis")
    j.check("answer_salary", dollar_in(fa, 36000000),
            "the highest salary is $36,000,000 (36M/36 million)")
    j.emit()

if __name__ == "__main__":
    main()

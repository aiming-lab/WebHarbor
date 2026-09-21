#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--22.

Task: "Locate the ArXiv Help section and find instructions on how to subscribe
to daily listing emails for new submissions in a specific category."

The /help/subscribe page: create an account and log in, open Alerts from the
user menu, enter the category code, pick daily frequency, click Subscribe.

Checks (deterministic):
  nav:    the /help/subscribe page
  answer: alerts + daily + (subscribe or category)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        contains_all, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--22", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_help_subscribe", navigated_to(t, "/help/subscribe"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '/help' in u][:4]}")
    j.check("answer_alerts_and_daily",
            contains_all(fa, ["alert", "daily"]), f"final={fa[:240]!r}")
    j.check("answer_subscribe_or_category",
            contains_any(fa, ["subscribe", "subscription", "category"]),
            f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()

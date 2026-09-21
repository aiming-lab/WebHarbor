#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--10.

Task: "Visit ArXiv Help on how to withdraw an article if the submission is not
yet announced."

The /help/withdraw page states: a not-yet-announced submission can be withdrawn
directly from the user page (without public trace) by clicking the Delete
button before the announcement deadline.

Checks (deterministic):
  nav:    the /help/withdraw page
  answer: user page + Delete button
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, norm, navigated_to,
                        contains_any, contains_all, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--10", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_help_withdraw", navigated_to(t, "/help/withdraw"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '/help' in u][:4]}")
    f = norm(fa)
    j.check("answer_user_page", "user page" in f or "user account page" in f,
            f"final={fa[:240]!r}")
    j.check("answer_delete_button",
            contains_any(fa, ["delete", "deleted", "remove the", "removal"]),
            f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--15.

Please try to log in to twitter with email: webagenttest@testmail.com and password: test123456. Let me know if the login was successful.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's cached X login page (x.com/login) is a static sign-in form
    (phone, email, or username + password; Continue with Google/Apple;
    forgot-password and sign-up links) with no working authentication
    backend, so a login attempt with the provided credentials cannot
    complete; the honest outcome is that the login was NOT successful. The
    help pages state the same login requirements.
Source pages: x.com/login, twitter.com/login and the Twitter help-center login pages

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a twitter/X login search | a login page opened | answer: the platform,
  the credential fields, and the (unsuccessful) outcome
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, searched_all_tokens,
                        visited_any_page, navigated_to, contains_all, contains_any,
                        re_any, re_count, number_claim, date_in, name_in, count_names,
                        order_by_first_mention)


def main():
    a = parse_args()
    j = Judge('Google Search--15', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["twitter", "login"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-015-", "x.com/login", "twitter.com/login", "log-in-to-twitter", "forms/login", "password_reset", "account-security-tips", "lifewire"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_platform", contains_any(fa, ["twitter", "x.com", "sign in to x"]) or re_any(fa, [r"\bx\b"]),
            f"final={fa[:200]!r}")
    j.check("answer_credential_fields", contains_any(fa, ["email", "username", "phone"]) and contains_any(fa, ["password"]),
            f"final={fa[:200]!r}")
    j.check("answer_outcome_unsuccessful", re_any(fa, [r"not successful", r"un[- ]successful", r"could not|couldn\u2019t|couldn't", r"unable", r"cannot|can't|can\u2019t", r"failed", r"did not|didn\u2019t|didn't", r"wasn't able|wasn\u2019t able|was not able", r"not possible", r"stuck", r"did not complete", r"cannot be completed", r"cannot complete"]) and not re_any(fa, [r"login was successful", r"successfully logged in", r"signed in successfully", r"logged in successfully"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()

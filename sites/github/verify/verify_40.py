#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--40.

Sign up: does email test123@gmail.com already exist?

Ground truth is hardcoded here and nowhere in tasks.jsonl; it was read off the
served pages of the running mirror container (all "last N days" filters anchor
to the site's frozen date 2024-05-15).
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, visited_repo,
                        visited_repo_any, search_url_with, step_urls, decoded,
                        contains_all, contains_any, mentions_repo, mentions_any_repo,
                        has_number, counts, figure_mentioned, mentions_date, Judge,
                        parse_args)



def main():
    a = parse_args()
    j = Judge('GitHub--40', a.no_llm)
    t, fa = grade_common(j, a, allowed_new_user_email="test123@gmail.com")

    j.check("nav_signup", navigated_to(t, "/register") or navigated_to(t, "/signup/check"),
            "opened Sign up (register page or the email check)")
    j.check("answer_email_available",
            bool(re.search(r"\bavailable\b", fa.lower()))
            or bool(re.search(r"not\s+(?:already\s+)?(?:registered|exist|exists|taken|in use)",
                              fa.lower()))
            or bool(re.search(r"(?:doesn'?t|does not|not)\s+(?:already\s+)?exist", fa.lower()))
            or contains_any(fa, ["no account", "not yet registered", "free to use",
                                 "can be used", "not taken"]),
            f"final={fa[:200]!r}")

    j.emit()

if __name__ == "__main__":
    main()

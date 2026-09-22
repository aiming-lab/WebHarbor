#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--11.

Task: "For Non-English submissions, do I need to provide a multi-language
abstract, if need, answer the separator between the multiple abstracts."

The /help/non-english page: non-English submissions MUST provide a
multi-language abstract; the multiple abstracts are separated by "--" (two
hyphens on a line by itself).

Checks (deterministic):
  nav:    the /help/non-english page
  answer: multi-language abstract required + the "--" separator
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--11", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_help_non_english", navigated_to(t, "/help/non-english"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '/help' in u][:4]}")
    f = fa.lower()
    j.check("answer_multi_language_abstract_required",
            contains_any(fa, ["multi-language", "multilingual", "multi language"])
            and contains_any(fa, ["must", "required", "need", "yes"]),
            f"final={fa[:240]!r}")
    separator = ("--" in fa) or ("two hyphens" in f) or ("double hyphen" in f)
    j.check("answer_separator_two_hyphens", separator, f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()

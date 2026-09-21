#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--28.

Task: "Search 'Poly encoder' by title on ArXiv and check whether the articles
in the search results provide HTML access."

A title search for the spaced phrase "Poly encoder" returns no matches; the
hyphenated variant "Poly-encoder" matches 3 titles (the seeded poly-encoder
papers), and the all-fields search surfaces the same articles. Every article
in these results provides HTML access on this mirror (result cards and abs
pages carry the [html] link).

Checks (deterministic):
  nav:    a /search URL carrying the poly query
  answer: states HTML access positively (html + available/access/yes) and
          contains no clause that denies it — any negated form ("no articles
          providing HTML access", "do not provide HTML", "HTML access is not
          available", "0 articles … HTML") is a FAIL
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, contains_any,
                        Judge, parse_args)

# A negator and 'html' inside the SAME clause (sentence/list punctuation ends
# the window, so a truthful "title search returned no results, so all results
# provide HTML access" is not penalised for its first clause).
_NEGATOR_HTML = r"\b(?:no|none|zero|without|lack(?:s|ing)?|missing|absent)\b[^.;!?:,]{0,80}\bhtml\b"
# explicit verb negation ... html: "do not provide HTML access"
_VERB_NEG_HTML = (r"\b(?:do(?:es)?\s+not|did\s+not|don'?t|doesn'?t|cannot|"
                  r"can'?t|won'?t|isn'?t|aren'?t)\b[^.;!?:,]{0,80}\bhtml\b")
# html ... negative predicate: "HTML access is not available/provided"
_HTML_NEG_PRED = (r"\bhtml\b[^.;!?]{0,60}\b(?:unavailable|missing|absent|"
                  r"not\s+(?:available|provided|accessible|offered))\b")
# explicit "0/zero articles ... html" denial in one clause
_ZERO_COUNT_HTML = r"\b0\s*(?:articles?|papers?|results?|entries)\b[^.;!?:,]{0,80}\bhtml\b"

NEGATIVE = re.compile(
    _NEGATOR_HTML + "|" + _VERB_NEG_HTML + "|" + _HTML_NEG_PRED + "|"
    + _ZERO_COUNT_HTML + "|no html|without html|not available|unavailable|not provide",
    re.IGNORECASE)


def main():
    a = parse_args()
    j = Judge("ArXiv--28", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any("/search" in u and "poly" in u for u in urls)
    j.check("nav_poly_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    f = fa.lower()
    positive = ("html" in f) and contains_any(
        fa, ["available", "access", "yes", "experimental", "provided", "provide"])
    negative = bool(NEGATIVE.search(f))
    j.check("answer_html_access_available", positive and not negative,
            f"positive={positive} negative={negative} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()

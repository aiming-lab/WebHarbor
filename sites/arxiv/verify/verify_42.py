#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--42.

Task: "Find an article published between 1 January 2000 and 1 January 2005 that
requires Support Vector Machines in the title and its Journey ref is ACL
Workshop."

A title search for "Support Vector Machines" over 2000-01-01..2005-01-01
returns 4 articles, every one with an ACL Workshop journal ref (hardcoded
below) — any one of them answers the task.

Checks (deterministic):
  nav:    a support-vector-machines search URL or a candidate /abs page
  answer: names one of the 4 articles AND mentions its ACL Workshop journal ref
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, paper_mentioned,
                        navigated_to, Judge, parse_args)

# (arxiv_id, title, journal ref)
CANDIDATES = [
    ("0404.00123", "Support Vector Machines for Text Categorization with Application to Sentiment Analysis",
     "ACL Workshop 2004"),
    ("0307.97704", "Support Vector Machines for Named Entity Recognition",
     "ACL Workshop on Multilingual and Mixed-language Named Entity Recognition, 2003"),
    ("0406.62628", "Applying Support Vector Machines to Semantic Role Labeling",
     "ACL Workshop on Computational Linguistics and Clinical Psychology, 2004"),
    ("0107.64170", "Using Support Vector Machines for Text Chunking",
     "ACL Workshop on Natural Language Learning, 2001"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--42", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    matched = next((c for c in CANDIDATES if paper_mentioned(fa, c[0], c[1])), None)
    j.check("answer_names_svm_acl_workshop_article", matched is not None,
            f"final={fa[:240]!r}")
    nav_ok = (any("/search" in u and "vector" in u and "support" in u for u in urls)
              or (matched and navigated_to(t, f"/abs/{matched[0]}")))
    j.check("nav_svm_search_or_paper", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    j.check("answer_acl_workshop_journal_ref",
            "acl workshop" in fa.lower(), f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()

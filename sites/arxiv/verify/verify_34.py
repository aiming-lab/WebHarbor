#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--34.

Task: "Search for the most recent paper related to non-commutative geometry
submitted by an author with the first name John. Provide the title and the
abstract."

The mirror's two genuine non-commutative-geometry papers by an author whose
first name is John are hardcoded below; the most recent is arXiv:2604.55278
"Non-commutative geometry of foliations" (2026-04-01, first author Smith, John
Adam).

Checks (deterministic):
  nav:    a non-commutative-geometry search URL or a candidate /abs page
  answer: names one of the two papers AND gives its abstract (chunk/keywords)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, norm, contains_all,
                        paper_mentioned, navigated_to, Judge, parse_args)

# (arxiv_id, title, abstract chunk, abstract keywords)
CANDIDATES = [
    ("2604.55278", "Non-commutative geometry of foliations",
     "a study of non-commutative geometry of foliations and their k-theory.",
     ["foliations", "k-theory", "non-commutative geometry"]),
    ("2603.58982", "Non-commutative geometry and spectral triples on quantum groups",
     "we construct spectral triples for quantum groups in non-commutative geometry. new results",
     ["spectral triples", "quantum groups", "dirac", "local index"]),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--34", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    matched = next((c for c in CANDIDATES if paper_mentioned(fa, c[0], c[1])), None)
    j.check("answer_names_ncg_john_paper", matched is not None,
            f"final={fa[:240]!r}")
    nav_ok = (any("/search" in u and "commutative" in u for u in urls)
              or (matched and navigated_to(t, f"/abs/{matched[0]}")))
    j.check("nav_ncg_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    if matched is None:
        j.emit()
    aid, title, chunk, keywords = matched
    f = norm(fa)
    abstract_ok = (chunk in f) or contains_all(fa, keywords[:2])
    j.check("answer_gives_abstract", abstract_ok, f"final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--15.

Quantum-computing repo updated in the last week with 50+ stars; description.

Ground truth is hardcoded here and nowhere in tasks.jsonl; it was read off the
served pages of the running mirror container (all "last N days" filters anchor
to the site's frozen date 2024-05-15).
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, visited_repo,
                        visited_repo_any, search_url_with, step_urls, decoded,
                        contains_all, contains_any, mentions_repo, mentions_any_repo,
                        has_number, counts, figure_mentioned, mentions_date, Judge,
                        parse_args)

# Qualifying set: served results of /search?q=quantum computing
# updated:>2024-05-08 stars:>=50 whose own description affirms quantum computing
# (the three served distractors explicitly disclaim it and are excluded).
QUALIFIERS = {
    "qsim-fast/quantum-state-simulator": ["simulator", "state-vector", "gpu"],
    "qlab/quantum-circuit-sim": ["circuit", "qiskit", "simulator"],
    "qopt-team/quantum-optimization-lib": ["optimization", "qaoa", "vqe"],
    "q-bits/qbit-playground": ["playground", "learning", "interactive"],
    "qec-research/quantum-error-correction": ["error correction", "surface code", "codes"],
    "qsim2/quantum-noise-simulator": ["noise", "circuits"],
    "qctrl-team/quantum-pulse-control": ["pulse", "calibration", "hardware"],
    "cpp-quantum/qcpp": ["c++", "circuit", "library"],
    "qphoton/photonic-quantum-lib": ["photonic", "gates", "continuous-variable"],
}

def main():
    a = parse_args()
    j = Judge('GitHub--15', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (search_url_with(t, ["quantum"]) or visited_repo_any(t, list(QUALIFIERS)))
    j.check("nav_quantum_search_or_repo", nav, "quantum search or a qualifying repo page")
    named = mentions_any_repo(fa, list(QUALIFIERS))
    j.check("answer_names_qualifying_repo", named is not None, f"final={fa[:160]!r}")
    if named:
        j.check("answer_describes_project", contains_any(fa, QUALIFIERS[named]),
                f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()

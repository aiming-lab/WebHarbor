#!/usr/bin/env python3
from verify_lib import answers_earlier_comparison, run_stateless, visited_path

MAGNETIC = "magnetic-checkerboard-separates-microparticles-by-size-and-sends-them-"
EARLIER = "quantum-geometry-applied-to-light-based-systems-expands-toolkit-for-to"
TITLE = "Quantum geometry applied to light-based systems expands toolkit for topological photonics"
OTHER_TITLE = "Magnetic checkerboard separates microparticles by size and sends them along different paths"

def checks(t, answer):
    return ([
        ("nav_magnetic", visited_path(t, f"/article/{MAGNETIC}"), "opened first article"),
        ("nav_quantum_geometry", visited_path(t, f"/article/{EARLIER}"), "opened second article"),
    ], [("answer_earlier_article",
         answers_earlier_comparison(answer, TITLE, OTHER_TITLE), repr(answer))])

if __name__ == "__main__":
    run_stateless(11, checks)

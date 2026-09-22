#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--3.

Task: "Locate the most recent research paper about 'Algebraic Topology' under
Mathematics published on ArXiv. Provide the title of the paper, the name of the
authors, and the abstract."

'Algebraic Topology under Mathematics' is the math.AT listing
(/list/math.AT/new); its newest entries — primary math.AT papers plus
cross-listed papers carrying the (math.AT) subject — are hardcoded below
(newest first; the top entry is arXiv:2604.08481, 2026-04-26).

Checks (deterministic):
  answer: names one of the newest math.AT-listed papers (title prefix or id)
  nav:    a math.AT listing/search URL or that paper's /abs page
  answer: gives >=2 author names AND the abstract (leading chunk or keywords)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, norm, contains_all,
                        paper_mentioned, navigated_to, Judge, parse_args)

# (arxiv_id, title, authors, abstract chunk, abstract keywords) — newest first.
CANDIDATES = [
    ("2604.08481", "The topology of Lagrangian submanifolds via open-closed string topology",
     ["Jian Petrov", "Maya Rossi", "Elena Zhou"],
     "we study the topology of lagrangian submanifolds in standard symplectic",
     ["lagrangian", "open-closed string topology", "symplectic", "deformation"]),
    ("2604.07352", "Twisted factorial Grothendieck polynomials and equivariant K-theory of weighted Grassmann orbifolds",
     ["Luca Schmidt", "Amir Zhou", "Ana Larsson"],
     "in this paper, we provide an explicit description of the",
     ["grothendieck polynomials", "equivariant k-theory", "grassmann orbifolds"]),
    ("2604.07579", "Topology of Percolation Clusters: Central Limit Theorems beyond the Lattice",
     ["Elena Schmidt", "Amir Patel", "Daniel Nguyen", "Yao Nguyen"],
     "we prove central limit theorems (clts) for topological functionals of",
     ["percolation", "central limit theorems", "topological functionals"]),
    ("2604.08166", "L-fuzzy simplicial homology",
     ["Daniel Zhang", "Fatima Bianchi"],
     "simplicial homology is a classical tool that assigns a sequence",
     ["simplicial homology", "simplicial complex", "modules", "invariants"]),
    ("2604.08066", "Bredon sheaf cohomology",
     ["Chen Hassan", "Tomas Larsson", "Yao Hassan"],
     "for a finite group $g$, we compute the algebraic $k$-theory",
     ["bredon", "sheaf cohomology", "equivariant sheaves"]),
    ("2604.84750", "Stable homotopy categories and equivariant cohomology",
     ["Patel, Asha", "Novak, Matej"],
     "a new framework for stable homotopy categories with applications to",
     ["stable homotopy", "equivariant cohomology", "algebraic topology"]),
    ("2604.68833", "A new invariant for closed 4-manifolds",
     ["Schmidt, Erika", "Kostas, Andreas", "Tanaka, Yuki"],
     "we construct a new topological invariant for closed 4-manifolds based",
     ["4-manifolds", "topological invariant", "mapping class groups"]),
    ("2604.41097", "Persistent homology of random complexes in high dimensions",
     ["Morgan, Thomas", "Chen, Yifan"],
     "we study the persistent homology of random simplicial complexes in",
     ["persistent homology", "random simplicial", "betti numbers", "scaling laws"]),
]


def _name_tokens(authors):
    """Distinctive surname tokens for author-name containment."""
    out = []
    for a in authors:
        parts = [p.strip() for p in a.split(",")]
        token = parts[0] if len(parts) > 1 else (a.split()[-1] if a.split() else a)
        out.append(token.lower())
    return out


def main():
    a = parse_args()
    j = Judge("ArXiv--3", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    matched = next(
        (c for c in CANDIDATES if paper_mentioned(fa, c[0], c[1])), None)
    j.check("answer_names_math_at_paper", matched is not None,
            f"final={fa[:220]!r}")
    if matched is None:
        j.emit()
    aid, title, authors, chunk, keywords = matched
    nav_paper = (navigated_to(t, f"/abs/{aid}")
                 or any("math.at" in u.lower() for u in step_urls(t)))
    j.check("nav_math_at", nav_paper,
            f"urls={[u for u in step_urls(t) if 'math' in u.lower()][:4]}")
    f = norm(fa)
    names = [n for n in _name_tokens(authors) if n in f]
    j.check("answer_gives_authors", len(names) >= 2,
            f"names_found={names}")
    abstract_ok = (chunk in f) or contains_all(fa, keywords[:2])
    j.check("answer_gives_abstract", abstract_ok, f"chunk_in={chunk in f}")
    j.emit()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--0.

Task: "Search for the latest preprints about 'quantum computing'."

Checks (deterministic):
  nav: a /search URL carrying both query tokens (quantum + computing)
  answer: names at least one real quantum-computing paper from the site's own
          search results (title prefix or arXiv id, hardcoded below)
Ground truth comes from the mirror's seeded data ("today" = 2026-04-28).
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, paper_mentioned,
                        Judge, parse_args)

QC_PAPERS = [
    ("2604.40002", "Variational quantum eigensolvers for strongly correlated electrons"),
    ("2604.40001", "Error-corrected quantum computing with neutral atom arrays"),
    ("2604.40003", "Benchmarking noise-adaptive compilation on superconducting processors"),
    ("2604.40010", "Shadow tomography for quantum computing benchmarks"),
    ("2604.40011", "Quantum error correction with concatenated surface codes"),
    ("2604.40012", "Measurement-based quantum computing on photonic graph states"),
    ("2604.40013", "Randomized compiling for Clifford+T quantum circuits"),
    ("2604.40014", "A many-body localisation probe on a superconducting quantum processor"),
    ("2604.40020", "Learning quantum circuit ansatzes with graph neural networks"),
    ("2604.40021", "Post-quantum cryptographic transition for enterprise systems"),
    ("2604.40015", "Noise characterisation of trapped-ion quantum computers via gate-set tomography"),
    ("2604.40022", "Reinforcement learning for quantum circuit scheduling"),
    ("2604.40016", "Sampling complexity of boson sampling on noisy photonic networks"),
    ("2604.29777", "Fault-tolerant quantum computing with neutral-atom arrays"),
    ("2604.16771", "Error-corrected quantum computation below threshold"),
    ("2604.16986", "Benchmarking quantum computing hardware on realistic workloads"),
    ("2604.40017", "Efficient simulation of Clifford noise for variational quantum algorithms"),
    ("2604.89554", "Quantum computing for drug discovery: a comprehensive review"),
    ("2604.08358", "Scalable Neural Decoders for Practical Fault-Tolerant Quantum Computation"),
    ("2604.08414", "Numerical approximation of the Koopman-von Neumann equation: Operator learning and quantum computing"),
    ("2604.07639", "Exponential quantum advantage in processing massive classical data"),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--0", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_qc = any("/search" in u and "quantum" in u and "computing" in u for u in urls)
    j.check("nav_quantum_computing_search", nav_qc,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    matched = next((aid for aid, title in QC_PAPERS if paper_mentioned(fa, aid, title)), None)
    j.check("answer_names_quantum_computing_preprint", matched is not None,
            f"matched={matched} final={fa[:220]!r}")
    j.emit()


if __name__ == "__main__":
    main()

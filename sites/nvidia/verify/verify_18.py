#!/usr/bin/env python3
"""NVIDIA--18: in the Newsroom, the article about Blackwell sweeping MLPerf Training 6.0 —
its publication date. Ground truth: 2026-06-16 (June 16, 2026).
Deterministic: nav to the article + date answer.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_any, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--18', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_article", navigated_any(t, ["/news/blackwell-mlperf-training-6-0", "/news"]),
            "expected the MLPerf Training 6.0 article")
    # the article page renders the date as "Jun 16, 2026" (abbreviated month); accept that
    # exact on-page form plus the common normalizations.
    j.check("answer_date", contains_any(fa, ["2026-06-16", "jun 16, 2026", "jun 16",
                                              "june 16, 2026", "june 16", "16 june"]),
            f"expected publication date 2026-06-16 (shown as 'Jun 16, 2026'); final={fa!r}")
    ok, ev = llm_text_match(fa, "published June 16, 2026 (2026-06-16)",
                            "What is the publication date of the Blackwell MLPerf Training 6.0 article?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Healthline--0: vitamin D article — how many IU most adults need per day. GT: 600 IU."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, number_mentioned,
                        contains_any, llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Healthline--0', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/article/vitamin-d-101"), "expected the Vitamin D article")
    j.check("answer_iu", number_mentioned(fa, 600) and contains_any(fa, ["IU", "international unit"]),
            f"expected 600 IU; final={fa!r}")
    ok, ev = llm_text_match(fa, "600 IU of vitamin D per day for most adults",
                            "How many IU of vitamin D do most adults need per day?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()

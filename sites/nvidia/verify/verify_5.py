#!/usr/bin/env python3
"""NVIDIA--5: in Embedded / robotics products, the price of the Jetson Orin Nano Super
Developer Kit. Ground truth: $249. Deterministic: nav to catalog/detail + price answer.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_any, price_mentioned,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--5', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_catalog_or_detail",
            navigated_any(t, ["/products", "jetson-orin-nano-super"]),
            "expected the Embedded catalog or the Jetson Orin Nano Super page")
    j.check("answer_price", price_mentioned(fa, 249), f"expected $249; final={fa!r}")
    ok, ev = llm_text_match(fa, "$249",
                            "What is the price of the Jetson Orin Nano Super Developer Kit?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()

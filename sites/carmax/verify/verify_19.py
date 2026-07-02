#!/usr/bin/env python3
"""Verifier for CarMax--19: on the MaxCare extended-service-plans page, compare the Silver,
Gold and Platinum tiers; report (a) the one-time price of each, (b) the price difference
between Gold and Silver, (c) the maximum coverage period (months / miles) of Platinum.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, price_mentioned, contains_any,
                        llm_text_match, Judge, parse_args)

# Frozen from the MaxCare page (see review): Silver $1,495 (36mo/50k), Gold $1,895 (48mo/75k),
# Platinum $2,395 (60mo/100k). Gold - Silver = $400.
SILVER, GOLD, PLAT = 1495, 1895, 2395
DIFF = GOLD - SILVER          # 400
PLAT_MONTHS, PLAT_MILES = 60, 100000

def main():
    a = parse_args()
    j = Judge('CarMax--19', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_maxcare", navigated_to(t, "maxcare-service-plans") or navigated_to(t, "maxcare"),
            "expected the MaxCare plans page")
    j.check("answer_tier_prices", all(price_mentioned(fa, p) for p in (SILVER, GOLD, PLAT)),
            f"expected ${SILVER:,}/${GOLD:,}/${PLAT:,}; final={fa!r}")
    j.check("answer_gold_minus_silver", price_mentioned(fa, DIFF), f"expected diff ${DIFF}")
    j.check("answer_platinum_coverage",
            price_mentioned(fa, PLAT_MONTHS) and (price_mentioned(fa, PLAT_MILES) or contains_any(fa, ["100k", "100,000"])),
            f"expected Platinum {PLAT_MONTHS} months / {PLAT_MILES:,} miles")
    ok, ev = llm_text_match(fa, f"Silver ${SILVER:,}, Gold ${GOLD:,}, Platinum ${PLAT:,}; "
                                f"Gold-Silver = ${DIFF}; Platinum covers {PLAT_MONTHS} months / {PLAT_MILES:,} miles",
                            "MaxCare tier prices, Gold-Silver difference, and Platinum max coverage.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()

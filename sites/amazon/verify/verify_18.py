#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--18.

Open Amazon's home page and tell me what the deal is that is going on at the moment, list the names of at least 2 items that are on offer and tell me what percent off they are.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The homepage 'Today's deals' row carries no percent labels; the percentages
    are on the Today's Deals listing reached from the homepage. The 23 catalog
    deals and their exact discounts are hardcoded below (e.g. Echo Dot -17%,
    AirPods Pro -20%, Fire TV Stick 4K Max -33%, SanDisk 1TB -40%, Huggies
    Wipes -50%). The answer must name >=2 deals with their correct percents.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + read-only DB (anonymous carts are cookie-backed, so an honest
run leaves the instance DB identical to its seed).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, visited_product,
                        visited_root, search_url_with, contains_all, contains_any,
                        price_in, first_mention, mentions_percent_for, count_claim,
                        extract_color_count_claim, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge('Amazon--18', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    DEALS = [
        (["echo dot"], 17), (["airpods pro"], 20), (["fire tv stick"], 33),
        (["qn90c"], 21), (["hp 15.6"], 20), (["sandisk"], 40), (["gopro"], 13),
        (["instant pot"], 25), (["keurig"], 11), (["roomba"], 25), (["hanes"], 33),
        (["air max 270"], 13), (["fossil gen 6"], 40), (["cerave"], 20),
        (["fitbit charge 6"], 19), (["johnson"], 42), (["pampers"], 40),
        (["gerber"], 38), (["huggies"], 50), (["aveeno"], 39), (["baby einstein"], 33),
        (["fisher-price", "fisher price"], 36), (["tommee"], 44),
    ]
    j.check("nav_homepage", visited_root(t), "the run opened the mirror homepage")
    j.check("nav_deals_listing", navigated_to(t, "/deals"),
            "Today's Deals listing reached from the homepage")
    pairs = [(name, pct) for name, pct in DEALS if mentions_percent_for(fa, name, pct)]
    j.check("answer_two_plus_correct_deal_pcts", len(pairs) >= 2,
            f"correct (deal, percent) pairs={pairs}")
    j.emit()


if __name__ == "__main__":
    main()

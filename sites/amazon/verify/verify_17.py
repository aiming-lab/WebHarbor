#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--17.

Show me the list of baby products that are on sale and under 10 dollars on Amazon. Provide at least 2 on sale products

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Baby products flagged as today's deals under $10 (8 total): Johnson's Baby
    Shampoo $7.49 (was $12.99), Pampers Swaddlers Sample Pack $8.99 (was
    $14.99), Gerber Baby Food Variety $9.99 (was $15.99), Huggies Natural Care
    Wipes 56ct $4.99 (was $9.99), Aveeno Baby Daily Moisture Lotion $8.49 (was
    $13.99), Baby Einstein Take Along Tunes $9.99 (was $14.99), Fisher-Price
    Rattle & Rock Maracas $6.99 (was $10.99), Tommee Tippee Baby Bottle $9.49
    (was $16.99). The answer must name at least two with their prices.

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
    j = Judge('Amazon--17', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    BABY = [("johnson", 7.49), ("pampers", 8.99), ("gerber", 9.99), ("huggies", 4.99),
            ("aveeno", 8.49), ("baby einstein", 9.99), ("fisher-price", 6.99),
            ("fisher price", 6.99), ("tommee", 9.49)]
    j.check("nav_baby_deals",
            navigated_to(t, "baby") or navigated_to(t, "/deals"),
            f"urls={[u for u in urls if 'baby' in u.lower() or '/deals' in u][:4]}")
    pairs = sorted({(tok, pr) for tok, pr in BABY
                    if contains_any(fa, [tok]) and price_in(fa, pr)})
    j.check("answer_two_plus_products_priced", len(pairs) >= 2,
            f"correct (product, price) pairs={pairs}")
    j.check("answer_under_10_dollars",
            all(pr < 10 for _, pr in pairs) and len(pairs) >= 2, f"pairs={pairs}")
    j.emit()


if __name__ == "__main__":
    main()

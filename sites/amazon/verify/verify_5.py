#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--5.

Find a Blue iPhone 12 Pro 128gb and add to cart.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The only blue iPhone 12 Pro with 128GB is 'Apple iPhone 12 Pro 128GB'
    (Pacific Blue variant), $699.00, Used - Good. The 256GB/512GB/Pro-Max units
    are Pacific Blue too but fail the 128GB constraint; the other 128GB units
    are Graphite/Gold/Silver. The add-to-cart redirects to /bag; when the
    mirror's demo session is active (the login page publishes the demo
    account) the add lands as a cart_items row for product 84, which is the
    allowed DB delta for this task.

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
    j = Judge('Amazon--5', a.no_llm)
    t, fa = grade_common(j, a, allowed_cart_products=(84,))
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_iphone_search", navigated_to(t, "iphone"),
            f"urls={[u for u in urls if 'iphone' in u.lower()][:4]}")
    after_db = __import__('verify_lib').resolve_db(a.after_db, a.container, "instance")
    cart_has_84 = bool(__import__('verify_lib').db_query(
        after_db, "SELECT 1 FROM cart_items WHERE product_id=84"))
    j.check("nav_blue_128gb_identified",
            visited_product(t, "apple-iphone-12-pro-128gb")
            or search_url_with(t, ["iphone", "color=blue"])
            or contains_all(fa, ["pacific blue"])
            or cart_has_84,
            "128GB product page, blue-filtered search, Pacific Blue reported, "
            "or the run's cart_items row for the qualifying product 84")
    j.check("cart_add_evidence", navigated_to(t, "/bag"), "add-to-cart redirects to /bag")
    j.check("answer_iphone_12_pro_128gb",
            contains_all(fa, ["iphone 12 pro"]) and contains_any(fa, ["128gb", "128 gb", "128"])
            and " max " not in " " + __import__('verify_lib').norm(fa) + " ",
            "iPhone 12 Pro 128GB (the Pro Max variant is not the requested phone)")
    j.emit()


if __name__ == "__main__":
    main()

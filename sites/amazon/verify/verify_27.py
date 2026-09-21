#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--27.

Look for a USB-C hub on Amazon compatible with MacBook Pro, featuring at least 4 ports, including HDMI and SD card reader. The price should be under $50. Select the one after sorting by Best Sellers.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    USB-C hubs with >=4 ports incl. HDMI + SD reader under $50, sorted by
    Best Sellers: #1 Anker 5-in-1 USB-C Hub with HDMI and SD card $25.99
    (4.7, 52,000) — the one to select; #2 Anker 7-in-1 $34.99 (38,500). The
    UGREEN 5-in-1 has no SD reader, the Amazon Basics adapter has 2 ports.

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
    j = Judge('Amazon--27', a.no_llm)
    t, fa = grade_common(j, a, allowed_cart_products=(237,), allowed_wishlist_products=(237,))
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_hub_search", navigated_to(t, "hub") or navigated_to(t, "usb-c"),
            f"urls={[u for u in urls if 'hub' in u.lower() or 'usb-c' in u.lower()][:4]}")
    j.check("nav_best_seller_sort_or_product",
            search_url_with(t, ["sort=bestseller"]) or search_url_with(t, ["sort=best"])
            or visited_product(t, "anker-5-in-1-usb-c-hub-with-hdmi-and-sd-card"),
            "best-seller sort or the Anker 5-in-1 product page")
    j.check("answer_anker_5_in_1",
            contains_all(fa, ["anker"]) and contains_any(fa, ["5-in-1", "5 in 1"]),
            f"final={fa[:200]!r}")
    j.check("answer_price_25_99", price_in(fa, 25.99), f"final={fa[:200]!r}")
    j.check("answer_hdmi_sd_ports",
            contains_all(fa, ["hdmi"]) and contains_any(fa, ["sd card", "sd-card", "sd reader", "sd card reader"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()

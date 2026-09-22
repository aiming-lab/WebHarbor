#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--35.

Find a men's leather wallet on Amazon with RFID blocking, at least 6 card slots, and priced below $50. Check if it's available for FREE delivery.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    RFID-blocking men's leather wallets with >=6 slots under $50, all with
    FREE delivery: Levi's Men's Leather Wallet 8 slots $19.99, Timberland
    Passcase 6 slots $24.99, Tommy Hilfiger 8 slots $32.99, Fossil Ingram
    Bifold 8 slots $39.99. The Carhartt trifold (9 slots) has no RFID
    blocking.

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
    j = Judge('Amazon--35', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    CANDS = [("fossil", 39.99, "8"), ("timberland", 24.99, "6"),
             ("tommy hilfiger", 32.99, "8"), ("levi", 19.99, "8")]
    j.check("nav_wallet_search", navigated_to(t, "wallet"),
            f"urls={[u for u in urls if 'wallet' in u.lower()][:4]}")
    matched = [c for c in CANDS if contains_any(fa, [c[0]])]
    j.check("answer_qualifying_wallet", bool(matched),
            f"matched={[c[0] for c in matched]} of {[c[0] for c in CANDS]}")
    j.check("answer_rfid_blocking", contains_any(fa, ["rfid"]), f"final={fa[:200]!r}")
    j.check("answer_card_slots_6_plus",
            any(contains_any(fa, [c[2] + " card", c[2] + " slots", c[2] + " card slots"])
                or count_claim(fa, c[2], "slot")
                for c in matched) if matched else False,
            "the named wallet's >=6 card slots")
    j.check("answer_free_delivery_available",
            contains_any(fa, ["free delivery", "free shipping", "free shipment"]), f"final={fa[:200]!r}")
    j.check("answer_price_matches",
            any(price_in(fa, c[1]) for c in matched) if matched else False, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()

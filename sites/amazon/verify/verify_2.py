#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--2.

Find a gaming desktop with Windows 11 Home, and the disk size should be 1TB.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Exactly two desktops carry Windows 11 Home + 1TB storage: HP OMEN 25L Gaming
    Desktop ($1,299.99, 1TB SSD) and MSI Aegis RS Gaming Desktop ($1,649.99, 1TB
    NVMe SSD). Other Win11-Home machines have 256GB/512GB/2TB disks; the 1TB ones
    on Win11 Pro or Ubuntu are distractors.

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
    j = Judge('Amazon--2', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_gaming_desktops",
            navigated_any(t, ["gaming+desktop", "gaming%20desktop", "gaming-desktop", "/c/computers"]),
            f"urls={[u for u in urls if 'gaming' in u.lower()][:4]}")
    omen = visited_product(t, "hp-omen-25l-gaming-desktop") or contains_all(fa, ["omen"])
    aegis = visited_product(t, "msi-aegis-rs-gaming-desktop") or contains_all(fa, ["aegis"])
    j.check("nav_or_answer_qualifying_desktop", omen or aegis, "HP OMEN 25L / MSI Aegis RS")
    j.check("answer_windows_11_home", contains_all(fa, ["windows 11 home"]), f"final={fa[:200]!r}")
    j.check("answer_1tb_disk", contains_any(fa, ["1tb", "1 tb", "1-tb"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()

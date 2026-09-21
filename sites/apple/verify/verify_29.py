#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--29.

Task: On Apple's website, check the estimated battery life of the latest MacBook Air during web browsing in Tech Specs.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    The mirror carries two honest completions of this task (its premise is
    stale: the current Air has no web-browsing figure):
    (a) the web-browsing figure: "Battery life: Up to 15 hours wireless web
    browsing" on /product/macbook-air-13-inch-m3 — also shown in the
    /compare/mac battery row (the only web-browsing estimate on the
    mirror); requires one of those two pages;
    (b) the current Air reading: the latest Air pages (/product/macbook-air-13,
    /product/macbook-air-15) list "Battery: Up to 18 hours" with no
    web-browsing qualifier — an answer reporting 18 hours TOGETHER WITH the
    explicit observation that no web-browsing-specific estimate is listed
    is the honest on-page report for the latest model.
    A claim that 18 hours IS the web-browsing figure fails (wrong-answer
    negative).
Checks: run-package gate + non-empty answer + read-only DB + navigation
(anti-shortcut) + answer facts.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, step_urls, url_query, navigated_to,
                        navigated_any, navigated_path, navigated_paths_all,
                        visited_url_with, contains_all, contains_any,
                        contains_word, contains_words_any, price_in,
                        count_named, number_claim, is_jan10_2024, Judge,
                        parse_args)


def main():
    a = parse_args()
    j = Judge('Apple--29', a.no_llm)
    t, fa = grade_common(j, a)
    nav_web_page = (navigated_path(t, "/product/macbook-air-13-inch-m3")
                    or navigated_path(t, "/compare/mac"))
    nav_air_page = (nav_web_page or navigated_any(t, ["/product/macbook-air-13",
                                                    "/product/macbook-air-15",
                                                    "/product/macbook-air-15-inch-m3"]))
    j.check("nav_macbook_air_spec_page", nav_air_page,
            "expected a MacBook Air product page, /compare/mac, or /mac")
    strict_15h = (contains_word(fa, "15") and contains_any(fa, ["hour"]))
    honest_current = (contains_word(fa, "18") and contains_any(fa, ["hour"])
                      and contains_any(fa, ["no web browsing", "no web-browsing",
                                            "not specif", "does not list",
                                            "does not include", "does not mention",
                                            "no specific web", "without a web-browsing",
                                            "unspecified"]))
    j.check("answer_battery_web_browsing",
            (strict_15h and nav_web_page) or honest_current,
            f"15h_fig={strict_15h} with_web_page={nav_web_page} "
            f"honest_current_reading={honest_current} final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()

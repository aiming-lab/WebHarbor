#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--33.

Find the Customer Service on the Booking website, browse the cancellation
questions, and tell how one knows whether a booking has been cancelled.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The mirror's Help Center (Customer Service) page carries the question
    "How do I know whether my booking has been cancelled?" Its answer names two
    signals: a cancellation confirmation email, and the booking status changing
    to "Cancelled" in My bookings.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + read-only DB (the task is read-only on the mirror).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, grade_booking, navigated_to, navigated_any,
                        visited_property, visited_root, search_url_with,
                        contains_all, contains_any, contains_affirmative,
                        mentions_one_of, price_in,
                        count_claim, first_mention, norm, step_urls, Judge,
                        parse_args)



def main():
    a = parse_args()
    j = Judge('Booking--33', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_help_page", navigated_to(t, "/help"),
            "the Help Center / Customer Service page")
    j.check("answer_email_signal", contains_any(fa, ["email"]),
            f"final={fa[:300]!r}")
    j.check("answer_cancelled_status_signal",
            contains_any(fa, ["cancel"]) and contains_any(fa, ["my bookings", "bookings page", "status"]),
            f"final={fa[:300]!r} the answer must reflect the cancelled-status signal")
    j.emit()


if __name__ == "__main__":
    main()

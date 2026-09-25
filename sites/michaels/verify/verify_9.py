#!/usr/bin/env python3
"""Verify Michaels--9.

Bob is deciding whether to buy his craft supplies online or use the in-store 30%-off coupon. Check the Savings page and Coupon Policy: explain when and where that coupon is valid, its daily limit, which categories GETMY30 excludes, and whether the offers can be combined. Sign in as bob.c@test.com (password TestPass123!), apply GETMY30 to his current cart and report the discount and total, leaving the order unplaced.
"""
from verify_lib import (Judge, answer_is_negative, check_read_only, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_all,
                        contains_amount, contains_any, contains_count, contains_phrase,
                        final_answer, run_verifier)

TASK_ID = "Michaels--9"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: savings + coupon policy + Bob's signed-in cart
    check_visited_path(judge, traj, "visited_savings", "/savings")
    check_visited_path(judge, traj, "visited_coupon_policy", "/coupon-policy-and-price-guarantee")
    check_signed_in_as(judge, traj, "bob.c@test.com")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    # answer: coupon identity + validity + expiry
    judge.check("answer_coupon_identity",
                contains_all(answer, ["30% OFF", "Regular Price Item"]),
                "expected: 30% OFF Any One Regular Price Item")
    judge.check("answer_coupon_channel", contains_phrase(answer, "In-Store") or
                contains_phrase(answer, "in store"),
                "expected: the coupon is valid in store only")
    judge.check("answer_expiry", contains_phrase(answer, "2026-09-24"),
                "expected expiry 2026-09-24")
    # answer: BOGO frames promo end date + GETMY30 excluded categories
    judge.check("answer_getmy30_exclusions",
                contains_all(answer, ["Cricut", "LEGO", "Sizzix", "Simply Tidy"]),
                "expected GETMY30 exclusions incl. Cricut, LEGO, Sizzix, Simply Tidy")
    # answer: per-day policy limit + stacking verdict
    judge.check("answer_per_day_limit", contains_count(answer, 1) and
                (contains_phrase(answer, "per day") or contains_phrase(answer, "per customer")),
                "expected: one coupon of that type per day")
    judge.check("answer_stacking_no",
                contains_any(answer, ["cannot", "can't", "can not", "not stack", "no", "separate"]) and
                answer_is_negative(answer, "stack") and
                answer_is_negative(answer, "combined"),
                "expected: stacking GETMY30 on top is NOT possible (every stack/combine "
                "claim must be negated)")
    # answer: GETMY30 applied to Bob's cart — discount + total
    judge.check("answer_getmy30_discount", contains_amount(answer, 7.19),
                "expected GETMY30 discount $7.19 on Bob's cart")
    judge.check("answer_getmy30_total", contains_amount(answer, 24.31),
                "expected the new order total $24.31")
    # read-only task: promo application is session state — DB must be untouched
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

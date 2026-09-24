#!/usr/bin/env python3
"""Verify Michaels--9 (round-2 redesign).

Grandma Rose only shops in stores and wants 30% off one regular-price item:
find her coupon on the Savings page (expiry date, where it's valid). When does
the Buy One Get One frames promo end? List the categories GETMY30's Savings
card excludes. Then check the Coupon Policy page: how many coupons of that
type may she use per day, and can she stack GETMY30 on top of the in-store
coupon? Sign in as Bob, apply GETMY30 to his cart, and report the discount
and total.

Frozen ground truth (seed DB): the in-store coupon "30% OFF Any One Regular
Price Item", In-Store Only, valid 2026-09-18 - 2026-09-24, limit one coupon
per customer per day. The BOGO frames promo (BUY 1, GET 1 FREE Wall & Tabletop
Frames by Studio Decor) runs 2026-09-21 - 2026-09-26, so it ends 2026-09-26.
GETMY30 (online only, valid 2026-09-14 - 2026-10-03) excludes sale & clearance,
tech, Cricut, LEGO, Sizzix, Splendid, Simply Tidy, Brother & Janome machines
and more. Policy: AORPI/A2RPI/ERPP coupons are limited to one coupon per
product and one coupon of each type per day. Stacking: NO — the in-store coupon
is valid in store only while GETMY30 is online only, so they cannot be combined.
Bob's seed cart subtotal is $23.99 (letter B $6.99 + 2 x display board $5.99 +
wafers $4.99); GETMY30 takes off $7.19 (30%), so the cart shows discount
-$7.19 and order total $24.31 (16.77 + 5.99 shipping + 1.55 tax). Applying a
promo code is session state only — the DB stays untouched (read-only task).
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
    judge.check("answer_bogo_frames_end", contains_phrase(answer, "2026-09-26"),
                "expected the BOGO frames promo end date 2026-09-26")
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

#!/usr/bin/env python3
"""Verify Micro Center--10.

Log in as david.k@test.com (password TestPass123!) and review both items from your recent pickup order: a 4-star review for the networking device titled 'Solid purchase' saying it arrived quickly and works well, and a 3-star review for the other item titled 'Does the job' saying it is basic but handy. Report the order number, the pickup store it was ordered from, and each product's review count after posting.
"""
from verify_lib import (check_signed_in_as, check_only_tables_changed,
                        check_trajectory_identity, contains_count, contains_phrase,
                        db_query, final_answer, navigated_to_path, navigated_to_product,
                        run_verifier)

TASK_ID = "Micro Center--10"
EMAIL = "david.k@test.com"
ORDER = "MC2609071148"
STORE_CITY = "tustin"
NETWORK_PID = 675726
OTHER_PID = 673901
NETWORK_COUNT = 184
OTHER_COUNT = 120
NETWORK_RATING = 4.6     # live-observed app recalculation (double-counted new row)
OTHER_RATING = 4.4


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_orders_page", navigated_to_path(traj, "/account/orders"),
                "required_path=/account/orders")
    judge.check("opened_pickup_order_page",
                navigated_to_path(traj, f"/account/orders/{ORDER}"),
                f"required_path=/account/orders/{ORDER}")
    judge.check("visited_network_device_page", navigated_to_product(traj, NETWORK_PID),
                f"required_product_id={NETWORK_PID} (UniFi Gateway Lite)")
    judge.check("visited_other_item_page", navigated_to_product(traj, OTHER_PID),
                f"required_product_id={OTHER_PID} (Plastic Scraper set)")
    judge.check("answer_quotes_order_number", contains_phrase(answer, ORDER),
                f"expected_order_number={ORDER!r}")
    judge.check("answer_names_pickup_store", contains_phrase(answer, STORE_CITY),
                f"expected_token={STORE_CITY!r}")
    judge.check("answer_quotes_network_review_count",
                contains_count(answer, NETWORK_COUNT),
                f"expected_review_count={NETWORK_COUNT}")
    judge.check("answer_quotes_other_review_count",
                contains_count(answer, OTHER_COUNT),
                f"expected_review_count={OTHER_COUNT}")
    seed_ids = {r["id"] for r in db_query(initial_db, "SELECT id FROM reviews")}
    after_rows = db_query(after_db, "SELECT id, product_id, author, rating, title, body "
                            "FROM reviews")
    new_reviews = [r for r in after_rows if r["id"] not in seed_ids]
    by_pid = {}
    for r in new_reviews:
        by_pid.setdefault(r["product_id"], []).append(r)
    net = by_pid.get(NETWORK_PID, [])
    oth = by_pid.get(OTHER_PID, [])
    judge.check("network_review_posted",
                len(net) == 1 and net[0]["rating"] == 4
                and net[0]["title"] == "Solid purchase"
                and "arrived quickly" in net[0]["body"].lower()
                and "works well" in net[0]["body"].lower(),
                f"network_review={net!r}")
    judge.check("other_review_posted",
                len(oth) == 1 and oth[0]["rating"] == 3
                and oth[0]["title"] == "Does the job"
                and "basic" in oth[0]["body"].lower()
                and "handy" in oth[0]["body"].lower(),
                f"other_review={oth!r}")
    for pid, count, rating in ((NETWORK_PID, NETWORK_COUNT, NETWORK_RATING),
                                (OTHER_PID, OTHER_COUNT, OTHER_RATING)):
        row = db_query(after_db, "SELECT review_count, rating FROM products "
                       "WHERE product_id = ?", (pid,))[0]
        judge.check(f"product_{pid}_count_rating",
                    row["review_count"] == count and abs(row["rating"] - rating) < 0.05,
                    f"expected=(count={count}, rating={rating}), observed={dict(row)!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("reviews", "products"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

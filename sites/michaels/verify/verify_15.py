#!/usr/bin/env python3
"""Verify Michaels--15.

The Johnsons are moving to West Seattle: update Alice's profile phone number to
(206) 555-0102 and add a new shipping address 2201 Alki Ave SW, Seattle, WA
98116 labeled "Beach House". Then order the 8" x 12" Black Collection Display
Box shipped there, paid with her Mastercard ending 5309, and report the order
total.

Frozen ground truth (seed DB): display box $13.49. Alice's seed cart $57.34 +
$13.49 = $70.83 subtotal; no promo; $70.83 >= $49 -> free shipping; tax 9.25%
= $6.55; total $77.38. Order MI26092301003 (user 01, 3rd order), Ship to
2201 Alki Ave SW, Seattle, WA 98116, Mastercard ****5309. Phone updated to
(206) 555-0102.
"""
from verify_lib import (Judge, added_order_matching, check_answer_order_matches_added_order,
                        check_only_tables_changed, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_all, contains_amount, contains_phrase,
                        entered_text_containing, final_answer, navigated_confirmation,
                        navigated_product, navigated_search, order_items_of, run_verifier,
                        user_by_email)

TASK_ID = "Michaels--15"
BOX_SLUG = "8-x-12-black-collection-display-box-by-studio-d-cor-10738990"
ORDER_NUMBER = "MI26092301003"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: sign-in, profile, addresses, the box PDP, cart, checkout, confirmation
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_profile", "/account/profile")
    check_visited_path(judge, traj, "visited_addresses", "/account/addresses")
    judge.check("entered_new_phone", entered_text_containing(traj, "(206) 555-0102"),
                "expected the new phone entered")
    judge.check("entered_address", entered_text_containing(traj, "2201 Alki Ave SW"),
                "expected the Beach House street entered")
    judge.check("searched_display_box", navigated_search(traj, "Display Box"),
                "required: a display box search")
    judge.check("visited_box_pdp", navigated_product(traj, BOX_SLUG),
                f"required: /product/{BOX_SLUG}")
    check_visited_path(judge, traj, "visited_cart", "/cart")
    check_visited_path(judge, traj, "visited_checkout", "/checkout")
    judge.check("visited_confirmation", navigated_confirmation(traj, ORDER_NUMBER),
                f"required: /order/confirmation/{ORDER_NUMBER}")
    # answer: order total
    judge.check("answer_order_total", contains_amount(answer, 77.38),
                "expected order total $77.38")
    # DB after-state: phone updated, address added, order + items, cart consumed
    user = user_by_email(after_db, "alice.j@test.com")
    judge.check("phone_updated", user is not None and user["phone"] == "(206) 555-0102",
                f"expected phone (206) 555-0102; found={user and user['phone']!r}")
    addr = [dict(r) for r in __import__("verify_lib").db_query(
        after_db, "SELECT * FROM addresses WHERE user_id = 1 AND label = 'Beach House'")]
    judge.check("address_added",
                len(addr) == 1 and addr[0]["line1"] == "2201 Alki Ave SW" and
                addr[0]["city"] == "Seattle" and addr[0]["state"] == "WA" and
                addr[0]["zip_code"] == "98116",
                f"expected the Beach House address; found={addr!r}")
    added = added_order_matching(after_db, initial_db,
                                 order_number=ORDER_NUMBER, user_id=1, status="Processing",
                                 delivery_method="Ship",
                                 address_line="2201 Alki Ave SW, Seattle, WA 98116",
                                 card_brand="Mastercard", card_last4="5309",
                                 subtotal=70.83, discount=0.0, shipping=0.0,
                                 tax=6.55, total=77.38, promo_code="")
    judge.check("added_order_row", added is not None, f"expected added order row; found={added!r}")
    check_answer_order_matches_added_order(judge, answer, added, "order")
    items = order_items_of(after_db, added["id"]) if added else []
    judge.check("added_order_items",
                len(items) == 4 and any("Black Collection Display Box" in i["name"] and
                                       i["unit_price"] == 13.49 for i in items),
                f"expected 4 order items incl. the display box; found={items!r}")
    check_only_tables_changed(judge, initial_db, after_db,
                              ("users", "addresses", "cart_items", "orders", "order_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

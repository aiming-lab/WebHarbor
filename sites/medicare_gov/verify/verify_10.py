#!/usr/bin/env python3
"""Verify Medicare.gov--10 — Alice's two-publication order (double state change).

Stateful task (login + two pub_orders inserts). Ground truth (frozen seed):
alice orders 2 Standard Print copies of 'Medicare Coverage of Cancer Treatment
Services' (product # 11931) and 1 Large Print copy of 'Choosing a Medigap
Policy' (product # 02110), both shipped to her address on file (12 Sunset
Terrace, Springfield, IL 62704-1234); both confirmations show the product
number and the ship-to address, and both rows land in pub_orders with status
Processing (created 2026-09-23).
"""

from verify_lib import (ALICE_EMAIL, CANCER_PUB_NUMBER, Judge,
                        MEDIGAP_PUB_NUMBER, MIRROR_REFERENCE_DATE,
                        advisory_llm_answer, check_login_delta,
                        check_signed_in_as, check_table_delta_shape,
                        check_trajectory_identity,
                        contains_count, contains_phrase, final_answer,
                        navigated_to_path, pub_id_by_number, pub_orders_of,
                        run_verifier, user_id_by_email)

TASK_ID = "Medicare.gov--10"
CANCER_ORDER_PAGE = f"/publication-ordering/{CANCER_PUB_NUMBER}"
MEDIGAP_ORDER_PAGE = f"/publication-ordering/{MEDIGAP_PUB_NUMBER}"
SHIP_ADDRESS = ("12 Sunset Terrace", "Springfield", "IL", "62704-1234")
GROUND_TRUTH = ("Ordered 2 Standard Print copies of 'Medicare Coverage of Cancer Treatment "
                "Services' (product # 11931) and 1 Large Print copy of 'Choosing a Medigap "
                "Policy' (product # 02110); both confirmation pages show the orders ship "
                "to 12 Sunset Terrace, Springfield, IL 62704-1234 (the address on file).")
QUESTION = ("Order 2 Standard Print copies of 'Medicare Coverage of Cancer Treatment "
            "Services' and 1 Large Print copy of 'Choosing a Medigap Policy' shipped to the "
            "address on file; report both product numbers and the shipping address shown on "
            "the confirmation pages.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL)
    judge.check("opened_cancer_order_page",
                navigated_to_path(traj, CANCER_ORDER_PAGE),
                f"required_path={CANCER_ORDER_PAGE}")
    judge.check("opened_medigap_order_page",
                navigated_to_path(traj, MEDIGAP_ORDER_PAGE),
                f"required_path={MEDIGAP_ORDER_PAGE}")
    judge.check("answer_cancer_product_number",
                contains_phrase(answer, CANCER_PUB_NUMBER) or contains_count(answer, 11931),
                f"expected product number {CANCER_PUB_NUMBER!r}")
    judge.check("answer_medigap_product_number",
                contains_phrase(answer, MEDIGAP_PUB_NUMBER) or contains_phrase(answer, "2110"),
                f"expected product number {MEDIGAP_PUB_NUMBER!r}")
    judge.check("answer_both_orders_confirmed",
                contains_phrase(answer, "2 copies") and
                (contains_phrase(answer, "1 copy") or contains_phrase(answer, "one copy"))
                and (contains_phrase(answer, "Standard Print") and contains_phrase(answer, "Large Print")),
                "expected both orders confirmed (2 Standard Print + 1 Large Print)")
    line1, city, _, zip_ = SHIP_ADDRESS
    judge.check("answer_ship_address",
                contains_phrase(answer, line1) and contains_phrase(answer, city)
                and contains_phrase(answer, zip_[:5]),
                f"expected ship-to {SHIP_ADDRESS!r}")

    user_id = user_id_by_email(initial_db, ALICE_EMAIL)
    check_login_delta(judge, initial_db, after_db, ALICE_EMAIL, extra_allowed=("pub_orders",))
    cancer_id = pub_id_by_number(initial_db, CANCER_PUB_NUMBER)
    medigap_id = pub_id_by_number(initial_db, MEDIGAP_PUB_NUMBER)
    orders = pub_orders_of(after_db, user_id)
    cancer_rows = [o for o in orders if int(o["publication_id"]) == int(cancer_id)]
    medigap_rows = [o for o in orders if int(o["publication_id"]) == int(medigap_id)]
    line1, city, state, zip_ = SHIP_ADDRESS
    ok = (len(orders) == 2 and len(cancer_rows) == 1 and len(medigap_rows) == 1
          and int(cancer_rows[0]["quantity"]) == 2
          and str(cancer_rows[0]["format"]) == "Standard Print"
          and int(medigap_rows[0]["quantity"]) == 1
          and str(medigap_rows[0]["format"]) == "Large Print"
          and all(str(o["ship_line1"]) == line1 and str(o["ship_city"]) == city
                  and str(o["ship_state"]) == state and str(o["ship_zip"]) == zip_
                  and str(o["created_at"]) == MIRROR_REFERENCE_DATE
                  and str(o["status"]) == "Processing" for o in orders))
    judge.check("pub_orders_exact_rows", ok, f"orders={orders!r}")
    check_table_delta_shape(judge, initial_db, after_db, "pub_orders",
                            allowed_added=2, label="pub_orders_only_alice_two_rows")
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

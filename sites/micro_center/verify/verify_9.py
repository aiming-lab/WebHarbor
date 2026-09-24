#!/usr/bin/env python3
"""Verify Micro Center--9.

PS5 storage: compare the two 4TB solid-state drives on the compare page and
identify the one explicitly compatible with the PlayStation 5. Set the store
to the Texas Micro Center that has it in stock, add two to the cart, and
report its capacity, price, and storage interface. Also add the cheapest 4TB
internal hard drive and report the final subtotal.

Frozen ground truth (seed DB): the two 4TB SSDs are the Professional 4TB
PRO-BLADE SSD Mag (676677, $429.99) and the 4TB PCIe Gen 4 x4 NVMe M.2
Internal SSD w/ Heatsink - Playstation 5 Compatible (674530, $459.99). The
PS5-compatible one is 674530; the only Texas store stocking it is Houston
(141) — Dallas and Austin do not. Cheapest 4TB internal hard drive = Purple
4TB 5400 RPM SATA III Surveillance Internal CMR (672227, $104.99). Subtotal =
2 x 459.99 + 104.99 = $1,024.97.

Guest (session) cart/store, so the DB stays read-only; the proof is the
navigation (both SSD PDPs, compare page, Houston store surface, HDD PDP,
cart) plus the quoted facts.
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_phrase, final_answer, navigated_search_with,
                        navigated_to_path, navigated_to_path_any, navigated_to_product,
                        run_verifier)

TASK_ID = "Micro Center--9"
PS5_PID = 674530
OTHER_SSD_PID = 676677
PS5_PRICE = 459.99
CAPACITY = "4tb"
INTERFACE_TOKENS = ("pcie gen 4", "nvme")
HDD_PID = 672227
SUBTOTAL = 1024.97
HOUSTON_SURFACES = ("/store/155", "/site/stores/default.aspx", "/stores")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("searched_for_drives",
                navigated_search_with(traj, "ssd") or navigated_search_with(traj, "4tb"),
                "required_query_token=ssd or 4tb")
    judge.check("visited_ps5_ssd_page", navigated_to_product(traj, PS5_PID),
                f"required_product_id={PS5_PID} (PS5-compatible 4TB NVMe)")
    judge.check("visited_other_ssd_page", navigated_to_product(traj, OTHER_SSD_PID),
                f"required_product_id={OTHER_SSD_PID} (PRO-BLADE, the other compared SSD)")
    judge.check("used_compare_page", navigated_to_path(traj, "/endeca/CompareV2.aspx"),
                "required_path=/endeca/CompareV2.aspx")
    judge.check("visited_houston_store_surface",
                navigated_to_path_any(traj, list(HOUSTON_SURFACES)),
                f"required_any_of={HOUSTON_SURFACES!r} (Houston selection surface)")
    judge.check("visited_hdd_page", navigated_to_product(traj, HDD_PID),
                f"required_product_id={HDD_PID} (Purple 4TB internal HDD)")
    judge.check("visited_cart", navigated_to_path(traj, "/cart"),
                "required_path=/cart")
    judge.check("answer_quotes_capacity", contains_phrase(answer, CAPACITY),
                f"expected_capacity={CAPACITY!r}")
    judge.check("answer_quotes_price", contains_amount(answer, PS5_PRICE),
                f"expected_price={PS5_PRICE}")
    judge.check("answer_quotes_interface",
                all(contains_phrase(answer, t) for t in INTERFACE_TOKENS),
                f"expected_tokens={INTERFACE_TOKENS!r}")
    judge.check("answer_names_houston_store", contains_phrase(answer, "houston"),
                "expected_token='houston' (the only Texas store with stock)")
    judge.check("answer_quotes_subtotal", contains_amount(answer, SUBTOTAL),
                f"expected_subtotal={SUBTOTAL}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

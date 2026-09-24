#!/usr/bin/env python3
"""Verify Micro Center--1.

I'm starting an AM5 gaming build. Compare the two cheapest AM5-socket motherboards on the compare page and go with the better-rated one, find the cheapest 32GB DDR5-6000 memory kit, and the cheapest NVIDIA RTX graphics card under $600. Add all three to your cart with the memory kit at quantity 2 (I want 64GB), and report the combined subtotal before tax, the socket type of the motherboard, and how many stores have the memory kit in stock.
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_count, contains_phrase, final_answer, navigated_search_with,
                        navigated_to_path, navigated_to_product, run_verifier)

TASK_ID = "Micro Center--1"
SUBTOTAL = 480.96
SOCKET = "AM5"
KIT_STORES = 26
MOTHERBOARDS = [668914, 685029]   # two cheapest AM5 boards (better-rated first)
KIT_PID = 664095
GPU_PID = 689783


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("searched_am5_motherboards", navigated_search_with(traj, "am5"),
                "required_query_token=am5")
    judge.check("searched_ddr5_kit", navigated_search_with(traj, "ddr5"),
                "required_query_token=ddr5")
    judge.check("searched_rtx", navigated_search_with(traj, "rtx"),
                "required_query_token=rtx")
    for pid in MOTHERBOARDS:
        judge.check(f"visited_motherboard_{pid}",
                    navigated_to_product(traj, pid),
                    f"required_product_id={pid} (both cheapest AM5 boards must be opened)")
    judge.check("used_compare_page", navigated_to_path(traj, "/endeca/CompareV2.aspx"),
                "required_path=/endeca/CompareV2.aspx")
    judge.check("visited_memory_kit_page", navigated_to_product(traj, KIT_PID),
                f"required_product_id={KIT_PID} (Ripjaws S5 32GB DDR5-6000)")
    judge.check("visited_rtx_page", navigated_to_product(traj, GPU_PID),
                f"required_product_id={GPU_PID} (RTX 3050 WINDFORCE V2)")
    judge.check("visited_cart", navigated_to_path(traj, "/cart"),
                "required_path=/cart")
    judge.check("answer_quotes_subtotal", contains_amount(answer, SUBTOTAL),
                f"expected_subtotal={SUBTOTAL}")
    judge.check("answer_quotes_socket", contains_phrase(answer, SOCKET),
                f"expected_socket={SOCKET!r}")
    judge.check("answer_quotes_kit_store_count", contains_count(answer, KIT_STORES),
                f"expected_stores={KIT_STORES}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

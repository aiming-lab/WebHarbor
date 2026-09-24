#!/usr/bin/env python3
"""Verify Micro Center--16.

I'm building two AM5 rigs: mine with the cheapest 32GB DDR5-6000 RGB kit, my friend's with the cheapest 32GB DDR5-6000 kit regardless of lighting. We're both near the Rockville, MD store — set it as your store first. Compare the three cheapest RGB kits on the compare page, open my kit's page, and report its CAS latency, memory timings, and voltage from its spec sheet, plus how many stores have it in stock. Confirm both kits are in stock at Rockville, add both to your cart, and report the subtotal.
"""
import re
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_count, contains_phrase, final_answer, navigated_search_with,
                        navigated_to_path, navigated_to_path_any, navigated_to_product,
                        normalize_text, run_verifier)

TASK_ID = "Micro Center--16"
ROCKVILLE_SURFACES = ("/store/085", "/site/stores/default.aspx", "/stores")
RGB_PID = 685119
PLAIN_PID = 664095
CAS = 30
TIMINGS = "30-36-36-68"
VOLTAGE = 1.35
RGB_STORES = 25
SUBTOTAL = 177.98


CAS_RE = re.compile(r"(?:cas(?:\s+latency)?|cl)\s*[:=]?\s*30(?!\d)")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_rockville_store_surface",
                navigated_to_path_any(traj, list(ROCKVILLE_SURFACES)),
                f"required_any_of={ROCKVILLE_SURFACES!r} (Rockville selection surface)")
    judge.check("searched_memory", navigated_search_with(traj, "ddr5"),
                "required_query_token=ddr5")
    judge.check("used_compare_page", navigated_to_path(traj, "/endeca/CompareV2.aspx"),
                "required_path=/endeca/CompareV2.aspx (the three cheapest RGB kits)")
    judge.check("visited_rgb_kit_page", navigated_to_product(traj, RGB_PID),
                f"required_product_id={RGB_PID} (ARES RGB 32GB DDR5-6000)")
    judge.check("visited_plain_kit_page", navigated_to_product(traj, PLAIN_PID),
                f"required_product_id={PLAIN_PID} (Ripjaws S5 32GB DDR5-6000)")
    judge.check("visited_cart", navigated_to_path(traj, "/cart"),
                "required_path=/cart")
    judge.check("answer_quotes_cas_latency",
                bool(CAS_RE.search(normalize_text(answer))),
                f"expected_cas=30 adjacent to 'CAS'/'CL' (not merely a digit inside the timings)")
    judge.check("answer_quotes_timings", contains_phrase(answer, TIMINGS),
                f"expected_timings={TIMINGS!r}")
    judge.check("answer_quotes_voltage", contains_amount(answer, VOLTAGE),
                f"expected_voltage={VOLTAGE}")
    judge.check("answer_quotes_rgb_store_count", contains_count(answer, RGB_STORES),
                f"expected_stores={RGB_STORES}")
    judge.check("answer_states_rockville_stock",
                contains_phrase(answer, "rockville") and contains_phrase(answer, "in stock"),
                "expected: both kits in stock at Rockville")
    judge.check("answer_quotes_subtotal", contains_amount(answer, SUBTOTAL),
                f"expected_subtotal={SUBTOTAL}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

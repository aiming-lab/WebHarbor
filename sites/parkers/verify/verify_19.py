#!/usr/bin/env python3
"""verify_19.py — deterministic verifier for task Parkers--19.

Report the price when new of the cheapest and most expensive current Kodiaq versions and the difference; then the dealer range of the cheapest version on the newest year plate.

Ground truth below is HARDCODED (frozen against the shipped seed DB); it never
appears in tasks.jsonl. Navigation gates encode the honest on-site path the
task text implies; a correct answer without that navigation is a shortcut and
fails. See verify_lib.py for the shared contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_lib import (  # noqa: E402
    Judge, check_read_only, check_seed_contract, check_trajectory_identity,
    contains_amount, contains_amount_range, contains_any_phrase, contains_count,
    contains_phrase, final_answer, navigated_c4s_search, navigated_cartax_gen,
    navigated_cartax_hub, navigated_guide, navigated_insurance,
    navigated_listing_detail, navigated_news, navigated_owner_reviews,
    navigated_to_path, navigated_reg_lookup, navigated_review, navigated_review_section,
    navigated_shortlist, navigated_sign_in, navigated_site_search,
    navigated_specs, navigated_specs_gen, navigated_valuation_chain,
    run_verifier, shortlist_listing_ids, added_rows, removed_rows, rows_of,
    user_by_email)

TASK_ID = "Parkers--19"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("nav_kodiaq_specs",
                navigated_specs_gen(traj, "skoda", "kodiaq", "suv-2024"),
                "required: Kodiaq generation specs page")
    judge.check("nav_kodiaq_cheapest_selected",
                navigated_specs(traj, "skoda", "kodiaq", "suv-2024",
                                ["15-tsi-e-tec-se-5dr-dsg"]),
                "required: cheapest Kodiaq (1.5 TSI e-TEC SE 5dr DSG) selected")
    judge.check("nav_kodiaq_most_expensive_selected",
                navigated_specs(traj, "skoda", "kodiaq", "suv-2024",
                                ["15-tsi-iv-204-laurin-klement-5dr-dsg"]),
                "required: most expensive Kodiaq (Laurin + Klement) selected")
    judge.check("nav_valuation_chain",
                navigated_valuation_chain(traj, "skoda", "kodiaq", "suv-2024",
                                          "15-tsi-e-tec-se-5dr-dsg", "2026/76", deriv_id=861),
                "required: Kodiaq valuation chain for 1.5 TSI e-TEC SE 2026/76")
    judge.check("answer_cheapest_new", contains_amount(answer, 39045),
                "cheapest Kodiaq is £39,045 (1.5 TSI e-TEC SE 5dr DSG)")
    judge.check("answer_most_expensive_new", contains_amount(answer, 48990),
                "most expensive Kodiaq is £48,990 (1.5 TSI iV 204 Laurin + Klement)")
    judge.check("answer_difference", contains_amount(answer, 9945),
                "difference is £9,945")
    judge.check("answer_dealer_range", contains_amount_range(answer, 47340, 50260),
                "dealer range on 2026/76 is £47,340 - £50,260")
    judge.check("nav_valuation_vid", navigated_to_path(traj, "/skoda/kodiaq/suv-2024/15-tsi-e-tec-se-5dr-dsg/8422/free-valuation"),
                "required: free-valuation page for valuation id 8422")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

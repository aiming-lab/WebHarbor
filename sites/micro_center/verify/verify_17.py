#!/usr/bin/env python3
"""Verify Micro Center--17.

Help me prepare a 3D-printing starter cart for the Cambridge, MA store. Add the Bambu Lab A1 printer, two matching plain PLA spools under $15 each, and one PLA+ spool under $25; both filament types must be in stock there. Check the printer's availability so I know whether I can collect everything together. Report the plain PLA's recommended plate temperature, filament colors and cart subtotal, without checking out.
"""
from verify_lib import (check_read_only, check_trajectory_identity, contains_amount,
                        contains_any, contains_count, contains_phrase, final_answer,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_product, run_verifier)

TASK_ID = "Micro Center--17"
CAMBRIDGE_SURFACES = ("/store/121", "/site/stores/default.aspx", "/stores")
A1_PID = 676237
PLA_PID = 512934
PLATE_LOW = 60
PLATE_HIGH = 80
# PLA+ choice -> (price, subtotal); colors are the answer-side token
PLA_PLUS_CHOICES = {
    "blue": (14.99, 400.96), "brown": (14.99, 400.96),
    "gray": (18.99, 404.96), "grey": (18.99, 404.96), "red": (18.99, 404.96),
    "neon green": (18.99, 404.96), "yellow": (18.99, 404.96),
    "true red": (18.99, 404.96), "black": (24.99, 410.96),
}
VALID_SUBTOTALS = sorted({v[1] for v in PLA_PLUS_CHOICES.values()})


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_cambridge_store_surface",
                navigated_to_path_any(traj, list(CAMBRIDGE_SURFACES)),
                f"required_any_of={CAMBRIDGE_SURFACES!r} (Cambridge selection surface)")
    judge.check("searched_printer",
                navigated_search_with(traj, "bambu") or navigated_search_with(traj, "a1")
                or navigated_search_with(traj, "printer"),
                "required_query_token=bambu or a1 or printer")
    judge.check("visited_printer_page", navigated_to_product(traj, A1_PID),
                f"required_product_id={A1_PID} (Bambu Lab A1)")
    judge.check("visited_plain_pla_page", navigated_to_product(traj, PLA_PID),
                f"required_product_id={PLA_PID} (1.75mm PLA - White)")
    judge.check("visited_pla_plus_page",
                any(navigated_to_product(traj, pid) for pid in
                    (611534, 611536, 611541, 611542, 611543, 611544, 611546, 611549, 670192)),
                "required: a PLA+ product page under $25 in stock at Cambridge")
    judge.check("visited_cart", navigated_to_path(traj, "/cart"),
                "required_path=/cart")
    judge.check("answer_quotes_plate_temperature",
                contains_count(answer, PLATE_LOW) and contains_count(answer, PLATE_HIGH),
                f"expected_plate_temperature={PLATE_LOW}C-{PLATE_HIGH}C")
    judge.check("answer_names_white_pla", contains_phrase(answer, "white"),
                "expected_token='white' (the only plain PLA under $15)")
    subtotal_ok = any(contains_amount(answer, s) for s in VALID_SUBTOTALS)
    judge.check("answer_quotes_valid_subtotal", subtotal_ok,
                f"expected_subtotal_any_of={VALID_SUBTOTALS!r}")
    if subtotal_ok:
        quoted = [s for s in VALID_SUBTOTALS if contains_amount(answer, s)]
        consistent_colors = [c for c, (_, s) in PLA_PLUS_CHOICES.items() if s in quoted]
        judge.check("answer_pla_plus_color_matches_subtotal",
                    contains_any(answer, consistent_colors),
                    f"a PLA+ color consistent with subtotal={quoted!r} must appear "
                    f"(valid colors: {sorted(set(consistent_colors))!r})")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

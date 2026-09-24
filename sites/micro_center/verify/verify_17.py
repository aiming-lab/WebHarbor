#!/usr/bin/env python3
"""Verify Micro Center--17.

3D-printing starter order picked up at the Cambridge, MA store (set as your
store): the Bambu Lab A1 3D printer, two spools of the same plain PLA
filament under $15 each, and one PLA+ spool under $25. Report the plain PLA's
recommended plate temperature from its spec sheet, the subtotal, and the
filament colors picked.

Frozen ground truth (seed DB): the Bambu Lab A1 3D Printer is 676237 at
$359.99. The only plain PLA filament under $15 is the 1.75mm PLA 3D Printer
Filament 1kg Cardboard Spool - White (512934, $12.99, in stock at Cambridge
121, qty 9); its spec sheet lists Plate Temperature 60°C - 80°C. The PLA+
spools under $25 in stock at Cambridge: Blue 611534 / Brown 611536 ($14.99),
Gray 611541 / Red 611542 / Neon Green 611543 / White 611544 / Yellow 611546
/ True Red 611549 ($18.99), PLA+ High Speed Black 670192 ($24.99). Purple
611540 is out of stock there. The subtotal therefore is
359.99 + 2 x 12.99 + {14.99 | 18.99 | 24.99} = {400.96 | 404.96 | 410.96},
and the answer's subtotal must be consistent with the PLA+ color it names.
(The A1 itself is out of stock at Cambridge — the round-2 review flagged the
task's "all in stock there" clause as a wording mismatch; the audit round
reworded the clause to "with the spools in stock there" so the task text
matches the seed. The graded facts never depended on the printer's stock.)

Guest (session) cart/store, so the DB stays read-only; the proof is the
navigation (Cambridge store surface, printer + PLA + PLA+ pages, cart) plus
the quoted spec-sheet facts.
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

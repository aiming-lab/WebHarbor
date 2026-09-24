#!/usr/bin/env python3
"""Verify Micro Center--14.

Create a new Micro Center Insider account with the email frank.m@test.com and password BenchMark123!, using your own name. Then find the Bambu Lab A1 3D printer, add it to your list, and put it in your cart to see the estimated total with tax. Also add a spool of PLA filament under $15 and a spool of PLA+ under $20, both in stock at the Cambridge, MA store, to your list. Report the list's item count, the printer's price, and the filament colors you picked.
"""
from verify_lib import (check_only_tables_changed, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, db_query,
                        final_answer, navigated_search_with, navigated_to_path,
                        navigated_to_product, run_verifier)

TASK_ID = "Micro Center--14"
EMAIL = "frank.m@test.com"
A1_PID = 676237
A1_PRICE = 359.99
PLA_PID = 512934
PLA_PLUS_PIDS = {611534: "blue", 611536: "brown", 611541: "gray", 611542: "red",
                 611543: "neon green", 611544: "white", 611546: "yellow",
                 611549: "true red"}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_register_page", navigated_to_path(traj, "/account/register"),
                "required_path=/account/register")
    entered = any("frank.m@test.com" in t.lower()
                  for t in [str(s.get("params", {}).get("text", "")) for s in
                            (traj.get("steps") or []) if isinstance(s, dict)])
    judge.check("entered_new_account_email", entered,
                "expected 'frank.m@test.com' in a registration input step")
    judge.check("searched_printer",
                navigated_search_with(traj, "bambu") or navigated_search_with(traj, "a1"),
                "required_query_token=bambu or a1")
    judge.check("visited_printer_page", navigated_to_product(traj, A1_PID),
                f"required_product_id={A1_PID} (Bambu Lab A1)")
    judge.check("visited_cart", navigated_to_path(traj, "/cart"),
                "required_path=/cart (estimated total with tax)")
    judge.check("visited_pla_page", navigated_to_product(traj, PLA_PID),
                f"required_product_id={PLA_PID} (1.75mm PLA - White)")
    judge.check("visited_lists_page", navigated_to_path(traj, "/account/lists"),
                "required_path=/account/lists")
    users = db_query(after_db, "SELECT id FROM users WHERE lower(email) = ?",
                    (EMAIL,))
    judge.check("new_user_created", len(users) == 1,
                f"users_matching={users!r}")
    if not users:
        return
    uid = users[0]["id"]
    listed = {r["product_id"] for r in db_query(
        after_db, "SELECT product_id FROM list_items WHERE user_id = ?", (uid,))}
    judge.check("list_has_printer_and_filaments",
                listed == {A1_PID, PLA_PID} | {p for p in listed if p in PLA_PLUS_PIDS}
                and len(listed) == 3
                and PLA_PID in listed and A1_PID in listed,
                f"expected 3 items (A1 + White PLA + one valid PLA+), observed={sorted(listed)!r}")
    pla_plus_rows = [p for p in listed if p in PLA_PLUS_PIDS]
    judge.check("exactly_one_pla_plus_added", len(pla_plus_rows) == 1,
                f"pla_plus_rows={pla_plus_rows!r}")
    cart_rows = db_query(after_db, "SELECT product_id, qty FROM cart_items WHERE user_id = ?",
                         (uid,))
    judge.check("printer_in_cart",
                any(r["product_id"] == A1_PID and r["qty"] >= 1 for r in cart_rows),
                f"cart_rows={cart_rows!r}")
    judge.check("answer_quotes_list_count", contains_count(answer, 3),
                "expected_count=3")
    judge.check("answer_quotes_printer_price", contains_amount(answer, A1_PRICE),
                f"expected_price={A1_PRICE}")
    judge.check("answer_names_white_pla", contains_phrase(answer, "white"),
                "expected_token='white' (the only plain PLA under $15)")
    if pla_plus_rows:
        color = PLA_PLUS_PIDS[pla_plus_rows[0]]
        judge.check("answer_names_pla_plus_color", contains_phrase(answer, color),
                    f"expected_token={color!r} (matches the PLA+ added to the list)")
    check_only_tables_changed(judge, initial_db, after_db, ("users", "list_items", "cart_items"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

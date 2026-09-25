#!/usr/bin/env python3
"""Verify Public Storage--12 (stateful: profile edit) — r2 task text.

Log in as carol.d@test.com (password TestPass123!), change the phone number
on the account to (407) 555-0777, and report the account number and the
phone number now shown on the account page, plus your rental's unit size,
facility street address, monthly rate, current balance, start date, next
bill date, gate code, and the status shown for your current reservation.

Frozen ground truth (seed DB): carol.d@test.com is account number 629145;
her rental (Medium 10'x10' at 1313 45th Street, Orlando FL) started
05/20/2026, runs $129.00/month with a $129.00 balance, next bill date
10/01/2026, gate code #5502; her reservation shows status HELD. After the
task: carol's users row must carry phone (407) 555-0777 and nothing else
may change.
"""
from verify_lib import (check_only_tables_changed, check_seed_contract,
                        check_trajectory_identity, contains_amount, contains_phrase,
                        entered_identity, final_answer, navigated_account,
                        navigated_account_edit, navigated_sign_in, rows_of,
                        run_verifier, user_by_email)

TASK_ID = "Public Storage--12"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_sign_in", navigated_sign_in(traj),
                "required: log in as carol.d@test.com")
    judge.check("entered_carol_email", entered_identity(traj, "carol.d@test.com"),
                "required: sign-in with carol.d@test.com")
    judge.check("visited_account_edit", navigated_account_edit(traj),
                "required: account edit page")
    judge.check("entered_new_phone", entered_identity(traj, "555-0777"),
                "required: change the phone to (407) 555-0777")
    judge.check("visited_account", navigated_account(traj),
                "required: account page after saving")
    # answer gates
    judge.check("answer_account_number", contains_phrase(answer, "629145"),
                "account number 629145")
    judge.check("answer_phone_now", contains_phrase(answer, "(407) 555-0777"),
                "phone number now shown (407) 555-0777")
    judge.check("answer_unit_size",
                contains_phrase(answer, "10'x10'") or contains_phrase(answer, "10x10")
                or contains_phrase(answer, "10 x 10"),
                "rental unit size 10'x10'")
    judge.check("answer_rental_address", contains_phrase(answer, "1313 45th Street"),
                "rental facility street address 1313 45th Street")
    judge.check("answer_monthly_rate", contains_amount(answer, 129),
                "monthly rate $129.00")
    judge.check("answer_current_balance", contains_amount(answer, 129),
                "current balance $129.00")
    judge.check("answer_start_date", contains_phrase(answer, "05/20/2026"),
                "rental start date 05/20/2026")
    judge.check("answer_next_bill", contains_phrase(answer, "10/01/2026"),
                "next bill date 10/01/2026")
    judge.check("answer_gate_code", contains_phrase(answer, "#5502"),
                "gate code #5502")
    judge.check("answer_reservation_status",
                contains_phrase(answer, "held"),
                "current reservation status HELD")
    # DB delta: only carol's users row changes (phone)
    check_only_tables_changed(judge, initial_db, after_db, {"users"})
    before = user_by_email(initial_db, "carol.d@test.com")
    after = user_by_email(after_db, "carol.d@test.com")
    judge.check("carol_phone_updated",
                after is not None and (after.get("phone") or "").replace(" ", "") == "(407)555-0777",
                f"phone={ (after or {}).get('phone')!r}")
    drift = {k: (before.get(k), after.get(k)) for k in (before or {})
             if before.get(k) != (after or {}).get(k)}
    judge.check("only_phone_changed",
                set(drift) <= {"phone"}, f"field drift={drift}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

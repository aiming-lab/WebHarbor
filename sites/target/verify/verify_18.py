#!/usr/bin/env python3
from verify_lib import (
    Judge, affirmative_contains, changed_tables, check_common,
    clicked_transition, entered_text, final_answer, input_values, load_run,
    login_submitted_as, parse_args, resolve_db, row_dicts,
    submitted_from_path, visited_in_order,
)

TASK_ID = "Target--18"
EMAIL = "bob.c@test.com"
SUBJECT = "Order arrived damaged"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("login_as_bob", login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check("ordered_support_flow", visited_in_order(trajectory, [("/login", {}), ("/support", {}), ("/support/contact", {}), ("/account/support", {})]), "login, support, contact, history")
    judge.check("clicked_contact_action", clicked_transition(trajectory, "/support", "/support/contact"), "contact form opened from Support")
    values = input_values(trajectory, "/support/contact")
    description_present = any(len(value.strip()) >= 10 and value not in {SUBJECT, "Email"} for value in values)
    judge.check("required_form_values_entered", entered_text(trajectory, SUBJECT, "/support/contact") and entered_text(trajectory, "Email", "/support/contact") and description_present, repr(values))
    judge.check("support_form_submitted", submitted_from_path(trajectory, "/support/contact", "/account/support"), "contact form submission")
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    readable = bool(initial and after); judge.check("databases_readable", readable, f"initial={initial} after={after}")
    if readable:
        before = row_dicts(initial, "SELECT t.* FROM support_tickets t JOIN users u ON u.id=t.user_id WHERE lower(u.email)=lower(?) ORDER BY t.id", (EMAIL,)); now = row_dicts(after, "SELECT t.* FROM support_tickets t JOIN users u ON u.id=t.user_id WHERE lower(u.email)=lower(?) ORDER BY t.id", (EMAIL,)); before_ids = {row["id"] for row in before}; created = [row for row in now if row["id"] not in before_ids]
        exact = len(created) == 1 and created[0]["subject"] == SUBJECT and created[0]["channel"] == "Email" and created[0]["status"] == "Open" and len(created[0]["summary"].strip()) >= 10
        judge.check("one_exact_new_ticket", exact and len(now) == len(before) + 1 and all(row in now for row in before), repr(created))
        judge.check("only_support_tickets_changed", changed_tables(initial, after) == {"support_tickets"}, repr(changed_tables(initial, after)))
        judge.check("answer_open_status", affirmative_contains(answer, "Open"), repr(answer))
    judge.emit()


if __name__ == "__main__": main()

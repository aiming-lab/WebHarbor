#!/usr/bin/env python3
from verify_lib import (
    Judge, check_common, clicked_transition, contains_all, database_unchanged,
    final_answer, has_money, load_run, login_submitted_as, parse_args,
    resolve_db, visited_in_order,
)

TASK_ID = "Target--8"
EMAIL = "david.k@test.com"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("login_as_david", login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check("ordered_login_to_orders", visited_in_order(trajectory, [("/login", {}), ("/account", {}), ("/account/orders", {})]), "login, account, orders")
    judge.check("clicked_order_history", clicked_transition(trajectory, "/account", "/account/orders"), "Orders opened from account")
    judge.check("answer_processing_order", contains_all(answer, ("TGT-240013",)) and has_money(answer, 32.61), repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

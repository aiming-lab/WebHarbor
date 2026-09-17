#!/usr/bin/env python3
from verify_lib import (
    Judge, check_common, clicked_transition, database_unchanged, final_answer,
    load_run, login_submitted_as, number_bound_to, parse_args, resolve_db,
    visited_in_order,
)

TASK_ID = "Target--9"
EMAIL = "david.k@test.com"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("login_as_david", login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check("ordered_login_to_rewards", visited_in_order(trajectory, [("/login", {}), ("/account", {}), ("/account/rewards", {})]), "login, account, rewards")
    judge.check("clicked_rewards_dashboard", clicked_transition(trajectory, "/account", "/account/rewards"), "Rewards opened from account")
    judge.check("answer_points_balance", number_bound_to(answer, 2185, ("point", "points", "balance")), repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

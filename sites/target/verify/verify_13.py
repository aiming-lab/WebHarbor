#!/usr/bin/env python3
from verify_lib import (
    Judge, check_common, clicked_transition, contains_all, contains_any,
    database_unchanged, final_answer, load_run, parse_args, resolve_db,
    visited_in_order,
)

TASK_ID = "Target--13"
STORE_PATH = "/stores/denver-stapleton"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("ordered_store_navigation", visited_in_order(trajectory, [("/stores", {}), (STORE_PATH, {})]), "store list before detail")
    judge.check("clicked_denver_store", clicked_transition(trajectory, "/stores", STORE_PATH), "Denver opened from list")
    judge.check("answer_street_address", contains_all(answer, ("7400", "E 29th Ave")), repr(answer))
    judge.check("answer_pickup_service", contains_any(answer, ("Order Pickup", "Drive Up")), repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

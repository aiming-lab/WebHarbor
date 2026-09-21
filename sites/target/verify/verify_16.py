#!/usr/bin/env python3
from verify_lib import (
    Judge, check_common, claims_relation, clicked_transition, contains_any, database_unchanged,
    final_answer, load_run, number_bound_to, parse_args, resolve_db,
    visited_in_order,
)

TASK_ID = "Target--16"
NINJA = "TGT94682442"
CUISINART = "TGT94139349"
NINJA_PATH = f"/product/{NINJA}"
CUISINART_PATH = f"/product/{CUISINART}"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    ninja_flow = visited_in_order(trajectory, [("/search", {}), (NINJA_PATH, {})]) and clicked_transition(trajectory, "/search", NINJA_PATH)
    cuisinart_flow = visited_in_order(trajectory, [("/search", {}), (CUISINART_PATH, {})]) and clicked_transition(trajectory, "/search", CUISINART_PATH)
    judge.check("opened_both_from_search", ninja_flow and cuisinart_flow, f"ninja={ninja_flow} cuisinart={cuisinart_flow}")
    judge.check("ninja_percent_bound", number_bound_to(answer, 66, ("ninja", "dualbrew")), repr(answer))
    judge.check("cuisinart_percent_bound", number_bound_to(answer, 59, ("cuisinart",)), repr(answer))
    judge.check("ninja_identified_higher", claims_relation(answer, ("ninja", "dualbrew"), ("cuisinart",), ("higher", "more", "greater")), repr(answer))
    judge.check("answer_uses_percentage_unit", contains_any(answer, ("%", "percent", "percentage")), repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

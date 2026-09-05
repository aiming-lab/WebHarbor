#!/usr/bin/env python3
from verify_lib import (
    Judge, check_common, claims_relation, clicked_transition, contains_any, database_unchanged,
    final_answer, load_run, number_bound_to, parse_args, resolve_db,
    visited_in_order,
)

TASK_ID = "Target--3"
PEPPERONI = "TGT13376389"
FOUR_CHEESE = "TGT13334000"
PEPPERONI_PATH = f"/product/{PEPPERONI}"
FOUR_CHEESE_PATH = f"/product/{FOUR_CHEESE}"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    search_to_pepperoni = visited_in_order(trajectory, [("/search", {"q": "Red Baron"}), (PEPPERONI_PATH, {})])
    search_to_cheese = visited_in_order(trajectory, [("/search", {"q": "Red Baron"}), (FOUR_CHEESE_PATH, {})])
    judge.check("search_precedes_both_products", search_to_pepperoni and search_to_cheese, "Red Baron search before both details")
    judge.check("clicked_both_product_results", clicked_transition(trajectory, "/search", PEPPERONI_PATH) and clicked_transition(trajectory, "/search", FOUR_CHEESE_PATH), "both products clicked from results")
    judge.check("pepperoni_value_bound", number_bound_to(answer, 790, ("pepperoni",)), repr(answer))
    judge.check("four_cheese_value_bound", number_bound_to(answer, 710, ("four cheese",)), repr(answer))
    judge.check("four_cheese_identified_lower", claims_relation(answer, ("four cheese",), ("pepperoni",), ("less sodium", "lower", "less")), repr(answer))
    judge.check("answer_uses_sodium_unit", contains_any(answer, ("mg", "milligram", "milligrams")), repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

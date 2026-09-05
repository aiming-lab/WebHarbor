#!/usr/bin/env python3
from verify_lib import (
    Judge, check_common, claims_relation, clicked_transition, contains_any, database_unchanged,
    final_answer, has_number, load_run, number_bound_to, parse_args, resolve_db,
    submitted_from_path, visited_in_order, visited_path,
)

TASK_ID = "Target--7"
SUPREME = "TGT13333997"
PEPPERONI = "TGT31168522"
SUPREME_PATH = f"/product/{SUPREME}"
PEPPERONI_PATH = f"/product/{PEPPERONI}"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("search_precedes_products", visited_in_order(trajectory, [("/search", {"q": "Red Baron"}), (SUPREME_PATH, {}), ("/compare", {})]) and visited_in_order(trajectory, [("/search", {"q": "Red Baron"}), (PEPPERONI_PATH, {}), ("/compare", {})]), "search, details, compare")
    judge.check("clicked_both_results", clicked_transition(trajectory, "/search", SUPREME_PATH) and clicked_transition(trajectory, "/search", PEPPERONI_PATH), "both details opened from results")
    judge.check("submitted_both_compare_controls", submitted_from_path(trajectory, SUPREME_PATH, SUPREME_PATH) and submitted_from_path(trajectory, PEPPERONI_PATH, PEPPERONI_PATH), "both detail-page compare forms submitted")
    judge.check("opened_compare_page", visited_path(trajectory, "/compare"), "Compare visited")
    values = (number_bound_to(answer, 650, ("supreme",)) and number_bound_to(answer, 810, ("pepperoni", "brick oven"))) or has_number(answer, 160)
    judge.check("answer_values_or_difference", values, repr(answer))
    judge.check("supreme_identified_lower", claims_relation(answer, ("supreme",), ("pepperoni",), ("less sodium", "lower", "less")), repr(answer))
    judge.check("answer_uses_sodium_unit", contains_any(answer, ("mg", "milligram", "milligrams")), repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("database_unchanged", database_unchanged(initial, after), "anonymous compare is session-only")
    judge.emit()


if __name__ == "__main__": main()

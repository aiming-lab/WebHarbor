#!/usr/bin/env python3
from verify_lib import (
    Judge, check_common, clicked_transition, contains_any, database_unchanged,
    final_answer, load_run, number_bound_to, parse_args, resolve_db,
    visited_in_order,
)

TASK_ID = "Target--2"
SKU = "TGT94764181"
PRODUCT_PATH = f"/product/{SKU}"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("ordered_grocery_to_product", visited_in_order(trajectory, [("/category/grocery", {}), (PRODUCT_PATH, {})]), "Grocery precedes product")
    judge.check("clicked_product_from_grocery", clicked_transition(trajectory, "/category/grocery", PRODUCT_PATH), "product opened from Grocery")
    answer_ok = number_bound_to(answer, 610, ("sodium",)) and contains_any(answer, ("mg", "milligram", "milligrams"))
    judge.check("answer_sodium_per_serving", answer_ok, repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

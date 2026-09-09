#!/usr/bin/env python3
from verify_lib import (
    Judge, affirmative_contains, check_common, clicked_transition, contains_any,
    database_unchanged, final_answer, load_run, number_bound_to, parse_args,
    resolve_db, visited_in_order,
)

TASK_ID = "Target--4"
SKU = "TGT91986267"
PRODUCT_PATH = f"/product/{SKU}"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("ordered_search_to_product", visited_in_order(trajectory, [("/search", {}), (PRODUCT_PATH, {})]), "search precedes product")
    judge.check("clicked_product_result", clicked_transition(trajectory, "/search", PRODUCT_PATH), "product opened from results")
    judge.check("recommendation_percent_bound", number_bound_to(answer, 74, ("recommend", "guests")), repr(answer))
    judge.check("highest_attribute", affirmative_contains(answer, "easy to clean"), repr(answer))
    judge.check("answer_uses_percentage_unit", contains_any(answer, ("%", "percent", "percentage")), repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

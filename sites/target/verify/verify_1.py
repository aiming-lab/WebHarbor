#!/usr/bin/env python3
from verify_lib import (
    Judge, check_common, clicked_transition, contains_any, database_unchanged,
    final_answer, has_number, load_run, parse_args, resolve_db,
    visited_in_order,
)

TASK_ID = "Target--1"
SKU = "TGT91151386"
PRODUCT_PATH = f"/product/{SKU}"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("ordered_search_to_product", visited_in_order(trajectory, [("/search", {"q": "yoga mat"}), (PRODUCT_PATH, {})]), "search precedes product")
    judge.check("clicked_product_result", clicked_transition(trajectory, "/search", PRODUCT_PATH), "product opened from results")
    judge.check("answer_material", contains_any(answer, ("nitrile butadiene rubber", "nbr")), repr(answer))
    judge.check("answer_length", has_number(answer, 71) and contains_any(answer, ("inch", "inches", '"')), repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

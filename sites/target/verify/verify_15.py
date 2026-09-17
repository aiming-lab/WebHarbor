#!/usr/bin/env python3
from verify_lib import (
    Judge, affirmative_contains, check_common, clicked_transition, contains_any, database_unchanged,
    final_answer, load_run, number_bound_to, parse_args, resolve_db,
    visited_in_order,
)

TASK_ID = "Target--15"
REQUIRED_SKUS = (
    "TGT13333997",
    "TGT13334000",
    "TGT31168521",
    "TGT13376389",
    "TGT31168522",
)
SUPREME_PATH = "/product/TGT13333997"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    search_seen = visited_in_order(trajectory, [("/search", {"q": "Red Baron"}), (SUPREME_PATH, {})])
    judge.check("red_baron_search", search_seen, "broad search precedes products")
    clicked = [sku for sku in REQUIRED_SKUS if clicked_transition(trajectory, "/search", f"/product/{sku}")]
    judge.check("all_five_products_opened", len(clicked) == len(REQUIRED_SKUS), repr(clicked))
    judge.check("answer_supreme_650", number_bound_to(answer, 650, ("supreme", "supreme classic crust")), repr(answer))
    judge.check("supreme_identified_lowest", affirmative_contains(answer, "supreme"), repr(answer))
    judge.check("answer_uses_sodium_unit", contains_any(answer, ("mg", "milligram", "milligrams")), repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

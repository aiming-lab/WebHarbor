#!/usr/bin/env python3
from verify_lib import (
    Judge, affirmative_contains, check_common, clicked_transition, contains_all,
    database_unchanged, final_answer, has_number, load_run,
    parse_args, resolve_db, visited_in_order, visited_query,
)

TASK_ID = "Target--5"
SKU = "TGT94760871"
PRODUCT_PATH = f"/product/{SKU}"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    filtered = visited_query(trajectory, "/category/electronics", {"brand": "sony"})
    judge.check("electronics_sony_filter", filtered, "Electronics listing with Sony brand")
    judge.check("filtered_listing_precedes_product", visited_in_order(trajectory, [("/category/electronics", {"brand": "sony"}), (PRODUCT_PATH, {})]), "filtered listing before detail")
    judge.check("clicked_product_from_electronics", clicked_transition(trajectory, "/category/electronics", PRODUCT_PATH), "product opened from listing")
    difference = has_number(answer, 22.95)
    both_prices = has_number(answer, 36.72) and has_number(answer, 59.67)
    judge.check("answer_price_comparison", difference or both_prices, repr(answer))
    plan_named = contains_all(answer, ("3-year",)) or contains_all(answer, ("longer plan",))
    coverage = plan_named and affirmative_contains(answer, "accidental")
    judge.check("three_year_accidental_coverage", coverage, repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

#!/usr/bin/env python3
from verify_lib import (
    Judge, check_common, contains_all, database_unchanged, final_answer,
    has_money, load_run, parse_args, resolve_db, visited_query,
)

TASK_ID = "Target--6"
EXPECTED_NAME_TOKENS = ("Cuddler Dog Bed", "Blue", "Boots & Barkley")
EXPECTED_PRICE = 24.99
FILTERS = {"brand": "boots-barkley", "availability": "pickup", "deals": "1", "sort": "price-asc"}


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("all_filters_on_one_pets_url", visited_query(trajectory, "/category/pets", FILTERS), repr(FILTERS))
    judge.check("answer_first_product_name", contains_all(answer, EXPECTED_NAME_TOKENS), repr(answer))
    judge.check("answer_first_product_price", has_money(answer, EXPECTED_PRICE), repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()

#!/usr/bin/env python3
from verify_lib import (
    Judge, changed_tables, check_common, clicked_transition, contains_all,
    entered_text, final_answer, input_values, load_run, login_submitted_as,
    parse_args, resolve_db, row_dicts, submitted_from_path,
    visited_in_order,
)

TASK_ID = "Target--19"
EMAIL = "carol.d@test.com"
SKU = "TGT92595737"
PRODUCT_PATH = f"/product/{SKU}"
HEADLINE = "Great sound for the size"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("login_as_carol", login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check("ordered_review_flow", visited_in_order(trajectory, [("/login", {}), (PRODUCT_PATH, {})]), "login before product review")
    judge.check("product_opened_from_search", clicked_transition(trajectory, "/search", PRODUCT_PATH), "product clicked from search")
    values = input_values(trajectory, PRODUCT_PATH); body_present = any(len(value.strip()) >= 15 and value not in {HEADLINE, "4"} for value in values)
    rating_entered = entered_text(trajectory, "4", PRODUCT_PATH) or entered_text(trajectory, "4 stars", PRODUCT_PATH)
    judge.check("review_fields_entered", entered_text(trajectory, HEADLINE, PRODUCT_PATH) and rating_entered and body_present, repr(values))
    judge.check("review_form_submitted", submitted_from_path(trajectory, PRODUCT_PATH, PRODUCT_PATH), "review submitted")
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    readable = bool(initial and after); judge.check("databases_readable", readable, f"initial={initial} after={after}")
    if readable:
        before = row_dicts(initial, "SELECT r.* FROM reviews r JOIN products p ON p.id=r.product_id WHERE p.sku=? ORDER BY r.id", (SKU,)); now = row_dicts(after, "SELECT r.* FROM reviews r JOIN products p ON p.id=r.product_id WHERE p.sku=? ORDER BY r.id", (SKU,)); before_ids = {row["id"] for row in before}; created = [row for row in now if row["id"] not in before_ids]
        exact = len(created) == 1 and created[0]["title"] == HEADLINE and created[0]["rating"] == 4 and created[0]["author_name"] == "Carol Diaz" and len(created[0]["body"].strip()) >= 15
        judge.check("one_exact_new_review", exact and len(now) == len(before) + 1 and all(row in now for row in before), repr(created))
        product_before = row_dicts(initial, "SELECT rating,review_count FROM products WHERE sku=?", (SKU,))[0]; product_after = row_dicts(after, "SELECT rating,review_count FROM products WHERE sku=?", (SKU,))[0]
        expected_rating = round(((product_before["rating"] * product_before["review_count"]) + 4) / (product_before["review_count"] + 1), 1)
        judge.check("aggregate_rating_updated", product_after["review_count"] == product_before["review_count"] + 1 and abs(product_after["rating"] - expected_rating) < 0.001, f"before={product_before} after={product_after}")
        judge.check("only_reviews_and_product_changed", changed_tables(initial, after) == {"reviews", "products"}, repr(changed_tables(initial, after)))
        judge.check("answer_confirms_headline", contains_all(answer, (HEADLINE,)), repr(answer))
    judge.emit()


if __name__ == "__main__": main()

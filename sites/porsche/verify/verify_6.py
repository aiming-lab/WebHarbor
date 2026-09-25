#!/usr/bin/env python3
"""Verify Porsche--6 (stateful).

Sign in to My Porsche with the demo account (casey.taylor@test.com /
TestPass123!), build a Taycan selecting exactly two options whose combined
price stays under $10,000, name the build 'Weekend Taycan' and save it. Report
both option names with their prices, the total price shown for the saved build
in the profile, the Taycan's base price, and how many options the Taycan
catalog offers.

Frozen ground truth (seed DB): Taycan (Y1AAI1) base price $111,900; the catalog
offers 43 options. The saved_builds table must gain exactly one row for the
casey.taylor user: build_name 'Weekend Taycan', model_code Y1AAI1, exactly two
options in options_json whose combined price is under $10,000, and
total_price = 111,900 + that combined price. The final answer must name both
saved options with their prices and the saved total (the pair itself is the
agent's choice among valid sub-$10,000 pairs, so it is read back from the
after-DB and cross-checked against the answer).
"""
import json

from verify_lib import (added_rows, check_only_tables_changed, check_seed_contract,
                        check_trajectory_identity, contains_amount, contains_count,
                        contains_phrase, entered_identity, final_answer, navigated_configurator,
                        navigated_saved_builds, navigated_sign_in, rows_of, run_verifier,
                        user_by_email)

TASK_ID = "Porsche--6"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    # navigation gates: sign-in, the Taycan configurator with two selected
    # options, and the saved-builds surface showing the saved row
    judge.check("visited_sign_in", navigated_sign_in(traj),
                "required: /my-porsche/sign-in")
    judge.check("entered_demo_email", entered_identity(traj, "casey.taylor@test.com"),
                "required: sign-in with casey.taylor@test.com")
    judge.check("visited_taycan_configurator", navigated_configurator(traj, "Y1AAI1"),
                "required: configurator page for Y1AAI1")
    judge.check("visited_saved_builds", navigated_saved_builds(traj),
                "required: /my-porsche/saved-builds (or profile) after saving")
    # DB delta: exactly one saved_builds row for casey.taylor, nothing else
    casey = user_by_email(initial_db, "casey.taylor@test.com")
    judge.check("demo_user_present", casey is not None, "casey.taylor@test.com in seed")
    check_only_tables_changed(judge, initial_db, after_db, {"saved_builds"})
    new_rows = added_rows(after_db, initial_db, "saved_builds", "id")
    judge.check("exactly_one_saved_build", len(new_rows) == 1,
                f"saved_builds delta = {len(new_rows)} rows")
    build = new_rows[0] if new_rows else {}
    judge.check("build_user", build.get("user_id") == (casey or {}).get("id"),
                f"build belongs to casey.taylor (user_id={build.get('user_id')})")
    judge.check("build_name", (build.get("build_name") or "").strip() == "Weekend Taycan",
                f"build_name={build.get('build_name')!r}")
    judge.check("build_model", build.get("model_code") == "Y1AAI1",
                f"model_code={build.get('model_code')!r}")
    try:
        options = json.loads(build.get("options_json") or "[]")
    except ValueError:
        options = None
    judge.check("build_exactly_two_options", isinstance(options, list) and len(options) == 2,
                f"options_json = {build.get('options_json')!r}")
    if isinstance(options, list) and len(options) == 2 and all(
            isinstance(o, dict) and "price" in o for o in options):
        combined = sum(o["price"] for o in options)
        judge.check("build_combined_under_10k", 0 < combined < 10000,
                    f"combined option price {combined}")
        judge.check("build_total_matches", build.get("total_price") == 111900 + combined,
                   f"total_price={build.get('total_price')} expected {111900 + combined}")
        # the answer must name both picked options with their prices and the total
        named = all(contains_phrase(answer, str(o.get("name"))) for o in options)
        judge.check("answer_names_both_options", named,
                    f"answer must name both options: {[o.get('name') for o in options]}")
        priced = all(contains_amount(answer, o["price"]) for o in options)
        judge.check("answer_prices_both_options", priced,
                   f"answer must give both option prices: {[o['price'] for o in options]}")
        judge.check("answer_saved_total", contains_amount(answer, 111900 + combined),
                   f"saved build total ${111900 + combined:,}")
    else:
        judge.check("build_options_parse", False,
                    "options_json must be a 2-element list of {id,name,price}")
    # answer gates on the frozen facts
    judge.check("answer_taycan_base", contains_amount(answer, 111900),
                "Taycan base price $111,900")
    judge.check("answer_catalog_count", contains_count(answer, 43),
                "the Taycan catalog offers 43 options")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

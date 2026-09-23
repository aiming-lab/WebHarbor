#!/usr/bin/env python3
"""Verify the Reversible vs yoox trench comparison in Google Shopping--14."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_any,
                        contains_phrase, contains_price, final_answer, navigated_search_with,
                        run_verifier)

TASK_ID = "Google Shopping--14"
TRENCH_JACKET_PATH = "/product/gsf3cad2d7c9135f80"   # 'trench jacket' (Reversible)
COTTON_PATH = "/product/gs8d6aa700e365d4d3"          # 'COTTON TRENCH COAT' (yoox.com)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: both products must have been located (search or product page each).
    judge.check("located_trench_jacket",
                navigated_search_with(traj, ["trench", "jacket"]) or
                any(TRENCH_JACKET_PATH in u for u in __import__("verify_lib").site_urls(traj)),
                "required a 'trench jacket' search or its product page")
    judge.check("located_cotton_trench_coat",
                navigated_search_with(traj, ["cotton", "trench", "coat"]) or
                any(COTTON_PATH in u for u in __import__("verify_lib").site_urls(traj)),
                "required a 'COTTON TRENCH COAT' search or its product page")
    # Frozen ground truth (seed DB): 'trench jacket' $1,290.00 (Reversible) is cheaper than
    # 'COTTON TRENCH COAT' $1,294.00 (yoox.com); the difference is $4.00.
    judge.check("answer_trench_jacket_price", contains_price(answer, 1290.00),
                "expected $1,290.00 for 'trench jacket'")
    judge.check("answer_cotton_price", contains_price(answer, 1294.00),
                "expected $1,294.00 for 'COTTON TRENCH COAT'")
    judge.check("answer_names_cheaper",
                contains_any(answer, ["trench jacket is cheaper", "trench jacket, at", "cheaper one is the trench jacket",
                                      "trench jacket is the cheaper", "the trench jacket is cheaper", "trench jacket costs less"]),
                "expected 'trench jacket' identified as the cheaper one")
    judge.check("answer_price_difference", contains_price(answer, 4.00), "expected a $4 difference")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

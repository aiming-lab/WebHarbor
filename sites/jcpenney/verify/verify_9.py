#!/usr/bin/env python3
"""Verify JCPenney--9."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--9"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_locator_filtered",
                navigated_to_path_with_params(traj, "/stores",
                                             {"service": "Curbside Pick up", "state": "WA"}),
                "required: /stores with service=Curbside Pick up and state=WA")
    check_visited_path(judge, traj, "visited_alderwood_detail", "/stores/2011")
    check_visited_path(judge, traj, "visited_bellis_detail", "/stores/2327")
    # Frozen ground truth (seed DB): store #2011 JCPenney Alderwood Mall, Lynnwood
    # WA — Sun 11:00-19:00, (425) 771-9555, services: Curbside Pick up;
    # store #2327 JCPenney Bellis Fair Mall, Bellingham WA — Sun 12:00-18:00,
    # (360) 734-7412, services: Curbside Pick up. The two differ in Sunday hours
    # and phone (same single service).
    judge.check("answer_alderwood_name", contains_phrase(answer, "Alderwood"),
                "expected the Alderwood Mall store")
    judge.check("answer_alderwood_sunday",
                fact_owner(answer, "11:00", ("Alderwood", "Lynnwood"), ("Bellis", "Bellingham"))
                and fact_owner(answer, "19:00", ("Alderwood", "Lynnwood"),
                               ("Bellis", "Bellingham")),
                "expected Alderwood's Sunday hours 11:00-19:00 attributed to Alderwood")
    judge.check("answer_alderwood_phone",
                fact_owner(answer, "771-9555", ("Alderwood", "Lynnwood"),
                           ("Bellis", "Bellingham")),
                "expected the Alderwood phone (425) 771-9555 attributed to it")
    judge.check("answer_bellis_name", contains_phrase(answer, "Bellis Fair"),
                "expected the Bellis Fair Mall store")
    judge.check("answer_bellis_sunday",
                fact_owner(answer, "12:00", ("Bellis", "Bellingham"), ("Alderwood", "Lynnwood"))
                and fact_owner(answer, "18:00", ("Bellis", "Bellingham"),
                               ("Alderwood", "Lynnwood")),
                "expected Bellis Fair's Sunday hours 12:00-18:00 attributed to Bellis Fair")
    judge.check("answer_bellis_phone",
                fact_owner(answer, "734-7412", ("Bellis", "Bellingham"),
                           ("Alderwood", "Lynnwood")),
                "expected the Bellis Fair phone (360) 734-7412 attributed to it")
    judge.check("answer_services",
                contains_phrase(answer, "Curbside"),
                "expected the curbside pickup service for both stores")
    judge.check("answer_difference",
                contains_any(answer, ["differ", "different", "while", "whereas", "versus", "vs",
                                      "unlike", "but"]),
                "expected a statement of how the two stores differ")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

#!/usr/bin/env python3
"""Verify JCPenney--1."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_amount, contains_count, contains_date_phrase, contains_money,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_search, navigated_search_sorted, navigated_to_path,
                        navigated_to_path_with_params, fact_owner, run_verifier,
                        stable_password_hash)

TASK_ID = "JCPenney--1"


def run_checks(judge, traj, initial_db, after_db):
    import re as _re
    from verify_lib import (db_query, normalized_url_path, phrases_in_order, site_urls,
                             table_delta, TABLES)
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_profile", "/account/dashboard/profile")
    # Frozen ground truth (seed DB): alice has 2 addresses (Home default at
    # 1460 Alderwood Mall Blvd, Lynnwood + Sister at 88 Pine St, Seattle);
    # after adding the task's address there are 3 and Home stays the default.
    judge.check("answer_address_count", contains_count(answer, 3),
                "expected 3 saved addresses afterwards")
    judge.check("answer_default_unchanged",
                contains_all(answer, ["1460 Alderwood Mall Blvd"]) or contains_all(answer, ["Home", "default"]),
                "expected Home (1460 Alderwood Mall Blvd) still the default")
    # --- DB after-state: one address row added for alice (Alex Johnson,
    # 582 Rainier Ave S, Seattle WA 98144, not default). The label field is
    # accepted as either "" or the task's "Brother".
    check_only_tables_changed(judge, initial_db, after_db, ("addresses",))
    delta = table_delta(initial_db, after_db, "addresses")
    judge.check("addresses_delta_one_added",
                len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"],
                f"addresses delta: added={len(delta['added'])}, removed={len(delta['removed'])}")
    if delta["added"]:
        cols = [r["name"] for r in db_query(initial_db, "PRAGMA table_info(addresses)")]
        row = dict(zip(cols, delta["added"][0]))
        judge.check("added_address_fields",
                    row.get("user_id") == 1 and row.get("first_name") == "Alex"
                    and row.get("last_name") == "Johnson"
                    and row.get("line1") == "582 Rainier Ave S"
                    and row.get("city") == "Seattle" and row.get("state") == "WA"
                    and row.get("zip") == "98144" and not row.get("is_default"),
                    f"added address: {row.get('first_name')} {row.get('last_name')}, "
                    f"{row.get('line1')}, {row.get('city')} {row.get('state')} {row.get('zip')}, "
                    f"default={row.get('is_default')}")
        judge.check("added_address_label_tolerance",
                    row.get("label") in {"", "Brother"},
                    f"label={row.get('label')!r}")
    defaults = [r for r in db_query(
        after_db, "SELECT id FROM addresses WHERE user_id = 1 AND is_default = 1")]
    judge.check("default_address_unchanged", len(defaults) == 1 and defaults[0]["id"] == 1,
                f"default address ids={[d['id'] for d in defaults]}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

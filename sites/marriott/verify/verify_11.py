#!/usr/bin/env python3
"""Verify Marriott--11.

Create a new Marriott Bonvoy account for Fiona Gray with email
fiona.gray@example.com (own password of 8+ characters); once signed in, report
the member tier and starting points balance the account page shows; then search
Seattle hotels, open the cheapest one, save it to the list and report its name.

Frozen ground truth (seed DB): a newly registered account starts at tier Member
with 42,000 points (registration defaults); cheapest Seattle hotel =
citizenM Seattle South Lake (marsha SEAZS, $151/night).
"""
from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_phrase, entered_identity, navigated_to_path_any,
                        final_answer, navigated_find_hotels, navigated_hotel_overview, run_verifier,
                        table_delta, user_by_email)

TASK_ID = "Marriott--11"
HOTEL = "citizenM Seattle South Lake"
EMAIL = "fiona.gray@example.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_register_page", "/loyalty/createAccount/createAccountPage1.mi")
    judge.check("entered_new_account_identity",
                entered_identity(traj, EMAIL, "Fiona", "Gray"),
                "expected Fiona / Gray / fiona.gray@example.com among the entered inputs")
    judge.check("visited_account_page",
                navigated_to_path_any(traj, ["/loyalty/myAccount.mi", "/account"]),
                "required: the account page (either route alias)")
    judge.check("visited_seattle_search", navigated_find_hotels(traj, "Seattle"),
                "required: /search/findHotels.mi with destinationAddress containing 'Seattle'")
    judge.check("visited_hotel_page", navigated_hotel_overview(traj, "citizenm-seattle-south-lake"),
                "required: the cheapest Seattle hotel's overview page")
    # answer: tier, starting balance, saved hotel name
    judge.check("answer_member_tier", contains_phrase(answer, "Member"),
                "expected the reported member tier 'Member'")
    judge.check("answer_starting_points", contains_amount(answer, 42000),
                "expected the starting points balance 42,000")
    judge.check("answer_hotel_name", contains_phrase(answer, "citizenM Seattle South Lake"),
                "expected the cheapest Seattle hotel name: citizenM Seattle South Lake")
    # DB after-state: one new user row (Fiona Gray, 42,000 points, Member tier)
    # + one favorite (the saved Seattle hotel); password hash / member number are
    # runtime-random and are not constrained.
    fiona = user_by_email(after_db, EMAIL)
    judge.check("new_user_row",
                fiona is not None and fiona["first_name"] == "Fiona" and fiona["last_name"] == "Gray"
                and fiona["points"] == 42000 and fiona["member_tier"] == "Member",
                f"expected a new user Fiona Gray / {EMAIL} with 42,000 points, tier Member; "
                f"observed={fiona!r}")
    users_delta = table_delta(initial_db, after_db, "users")
    judge.check("one_user_added",
                len(users_delta["added"]) == 1 and len(users_delta["removed"]) == 0
                and len(users_delta["changed"]) == 0,
                f"expected exactly one added users row; delta={users_delta!r}")
    favs_delta = table_delta(initial_db, after_db, "favorites")
    judge.check("one_favorite_added",
                len(favs_delta["added"]) == 1 and len(favs_delta["removed"]) == 0,
                f"expected exactly one added favorite; delta={favs_delta!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("users", "favorites"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

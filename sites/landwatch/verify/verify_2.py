#!/usr/bin/env python3
"""Verify LandWatch--2 — Sisterdale Farms due diligence + broker profile.

Ground truth (frozen seed): 'Sisterdale Farms' is listed at $19,400,000 for
310 Acres with 5 Beds and 5 Baths and a 'View all 93 pictures' gallery button.
The first two Highlights bullets are '11,800± SF custom stone home with 7
Rumford fireplaces and panoramic Hill Country views' and 'Over one third
mile of Guadalupe River frontage with senior water rights'; the Activities
list is Camping, Canoeing/Kayaking, Fishing, Horseback Riding, Hunting,
Off-roading. The listing agent Louie Swope's profile shows 2 Total Listings,
a $19M - $21M price range, a 310.00 - 844 ac acre range, and San Antonio, TX
as his base.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_all,
                        contains_any, contains_count, contains_money,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "LandWatch--2"
SISTERDALE_DETAIL = "/kendall-county-texas-farms-and-ranches-for-sale/pid/425766087"
SWOPE_PROFILE = "/profile/louie-swope/1437140"
ACTIVITIES = ["Camping", "Canoeing", "Kayaking", "Fishing", "Horseback",
              "Hunting", "Off-roading"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_sisterdale_detail", SISTERDALE_DETAIL)
    check_visited_path(judge, traj, "visited_find_agent", "/find-agent")
    check_visited_path(judge, traj, "visited_agent_profile", SWOPE_PROFILE)
    # listing due-diligence facts
    judge.check("answer_price", contains_money(answer, 19400000),
                "expected $19,400,000")
    judge.check("answer_acres", contains_acres(answer, 310), "expected 310 Acres")
    judge.check("answer_beds", contains_count(answer, 5) and contains_any(
        answer, ["Beds", "beds", "bedrooms", "Bed "]),
        "expected 5 beds")
    judge.check("answer_baths", contains_count(answer, 5) and contains_any(
        answer, ["Baths", "baths", "bathrooms", "Bath "]),
        "expected 5 baths")
    judge.check("answer_gallery_pictures", contains_count(answer, 93),
                "expected the gallery to list 93 pictures")
    judge.check("answer_first_highlight",
                contains_phrase(answer, "11,800") and contains_phrase(answer, "Rumford"),
                "expected the first Highlight (11,800± SF custom stone home with 7 Rumford fireplaces)")
    judge.check("answer_second_highlight",
                contains_phrase(answer, "Guadalupe River frontage")
                and contains_phrase(answer, "senior water rights"),
                "expected the second Highlight (Guadalupe River frontage with senior water rights)")
    judge.check("answer_activities_complete", contains_all(answer, ACTIVITIES),
                f"expected every activity {ACTIVITIES!r}")
    # broker profile facts
    judge.check("answer_agent_named", contains_phrase(answer, "Louie Swope"),
                "expected the listing agent Louie Swope")
    judge.check("answer_profile_total_listings", contains_count(answer, 2),
                "expected 2 Total Listings on the profile")
    judge.check("answer_profile_price_range",
                contains_phrase(answer, "19M") or contains_phrase(answer, "19.4M")
                or contains_money(answer, 19400000),
                "expected the $19M price-range floor")
    judge.check("answer_profile_price_range_top",
                contains_phrase(answer, "21M") or contains_phrase(answer, "21.4M")
                or contains_money(answer, 21400000),
                "expected the $21M price-range ceiling")
    judge.check("answer_profile_acre_range", contains_count(answer, 844),
                "expected the 844-ac acre-range ceiling")
    judge.check("answer_profile_base_city", contains_phrase(answer, "San Antonio"),
                "expected the agent to be based in San Antonio")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

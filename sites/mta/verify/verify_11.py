#!/usr/bin/env python3
"""Verify MTA--11.

Concert at UBS Arena in Elmont arriving on the LIRR Hempstead Branch, and a
Sunday 7 train ride to Flushing-Main St: this weekend's planned service
changes for both trips — what to expect, which stations are affected, and
the MTA's travel alternatives.

Frozen ground truth (seed DB): weekend window Sep 25 17:00 - Sep 28 02:00.
LIRR: alert lmm:planned_work:34768 — "Westbound trains skip Elmont-UBS
Arena, Queens Village, and Hollis"; alternatives: MTA buses accept LIRR
tickets from Queens Village and Hollis to Jamaica; Elmont-UBS Arena riders
should use Bellerose station instead. Subway 7: "In Queens, Flushing-bound
[7] skips 52 St and 69 St" (use 46 St-Bliss St, Woodside-61 St or
74 St-Broadway; transfer at Woodside-61 St / 74 St-Broadway) and "all
Manhattan-bound [7][7X] local/express trains stop at 74 St-Broadway".
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_any_phrase, contains_count, contains_phrase, contains_time, final_answer, navigated_planned_changes, navigated_to_path, normalized_url_path, run_verifier, site_urls)

from urllib.parse import parse_qs, urlparse

TASK_ID = "MTA--11"

# r3 sub-ask ground truth (seed DB, frozen): every train time listed at
# Elmont-UBS Arena on the Hempstead Branch Saturday/Sunday timetables
# (both directions, app display form). Verified live in the r3 re-review
# walks against a fresh native-Dockerfile build at bc2be8b8.
HEMPSTEAD_WEEKEND_ELMONT_TIMES = (
    "00:22", "00:35", "01:22", "01:27", "02:12", "03:09", "04:16", "05:52",
    "05:58", "06:50", "07:05", "07:59", "08:03", "08:59", "09:03", "09:59",
    "10:03", "10:05", "10:59", "11:03", "11:06", "11:59", "12:03", "12:59",
    "13:03", "13:59", "14:03", "14:59", "15:03", "15:04", "15:59", "16:03",
    "16:59", "17:03", "17:59", "18:03", "18:59", "19:03", "19:59", "20:03",
    "20:59", "21:03", "21:50", "22:02", "22:50", "23:22", "23:37",
)


def _navigated_hempstead_weekend_timetable(traj):
    """The Hempstead Branch timetable opened on a weekend day view."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/schedules/lirr/hempstead":
            continue
        q = parse_qs(urlparse(str(u)).query)
        if any(d in q.get("day", []) for d in ("saturday", "sunday")):
            return True
    return False


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_lirr_weekend_changes",
                navigated_planned_changes(traj, "lirr", "weekend"),
                "required: /planned-service-changes?mode=lirr&when=weekend")
    judge.check("visited_subway_weekend_changes",
                navigated_planned_changes(traj, "subway", "weekend"),
                "required: /planned-service-changes?mode=subway&when=weekend")
    judge.check("answer_ubs_arena_skip",
                contains_any_phrase(answer, ["elmont-ubs arena", "ubs arena"]),
                "westbound Hempstead Branch trains skip Elmont-UBS Arena")
    judge.check("answer_stations_queens_village_hollis",
                contains_phrase(answer, "queens village") and contains_phrase(answer, "hollis"),
                "Queens Village and Hollis are also skipped")
    judge.check("answer_bellerose_alternative",
                contains_phrase(answer, "bellerose"),
                "Elmont-UBS Arena riders should use Bellerose instead")
    judge.check("answer_buses_accept_lirr_tickets",
                contains_phrase(answer, "accept lirr tickets") or contains_phrase(answer, "lirr tickets"),
                "MTA buses accept LIRR tickets from Queens Village and Hollis to Jamaica")
    judge.check("answer_7_skips_52_69",
                contains_phrase(answer, "52 st") and contains_phrase(answer, "69 st"),
                "Flushing-bound 7 skips 52 St and 69 St")
    judge.check("answer_7_alternatives",
                contains_any_phrase(answer, ["woodside-61 st", "46 st-bliss st", "74 st-broadway"]),
                "alternatives: 46 St-Bliss St / Woodside-61 St / 74 St-Broadway")
    judge.check("visited_now_changes",
                navigated_planned_changes(traj, "subway", "now"),
                "required: /planned-service-changes?mode=subway&when=now (in-effect check)")
    judge.check("visited_belmont_pr",
                navigated_to_path(traj,
                    "/press-release/mta-best-way-get-belmont-park-historic-racetrack-reopens"),
                "required: the Belmont Park press release")
    judge.check("answer_7_in_effect_now",
                contains_any_phrase(answer, ["in effect", "already in effect", "in effect now",
                                             "already affect", "currently in effect",
                                             "already under way", "already underway"]),
                "the 7's skip of 52/69 St is already in effect (from May 25, 2026)")
    judge.check("answer_belmont_pr_lirr_service",
                contains_phrase(answer, "17 trains") and
                (contains_phrase(answer, "90 trains") or contains_count(answer, 90)) and
                (contains_phrase(answer, "159") or contains_count(answer, 159)),
                "Belmont PR: 17 added trains; 90 weekday / 159 weekend trains to Elmont-UBS Arena")
    judge.check("visited_hempstead_weekend_timetable",
                _navigated_hempstead_weekend_timetable(traj),
                "required: /schedules/lirr/hempstead with day=saturday or day=sunday "
                "(the Hempstead Branch weekend timetable)")
    judge.check("answer_elmont_weekend_train_time",
                contains_phrase(answer, "elmont-ubs arena") and
                any(contains_time(answer, t) for t in HEMPSTEAD_WEEKEND_ELMONT_TIMES),
                "a train time at Elmont-UBS Arena from the Hempstead Branch weekend timetable")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

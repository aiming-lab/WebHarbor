#!/usr/bin/env python3
"""Verify MTA--15.

School report on the Interborough Express: what it is and which boroughs it
would connect, the milestone announced in the September 9, 2026 press
release, and one other active MTA project that improves accessibility with
the station it targets.

Frozen ground truth (seed DB): IBX is a proposed light rail line connecting
Brooklyn and Queens (18 stations, ~32 minutes end-to-end, fully
accessible). The Sep 9, 2026 press release ("ICYMI: Governor Hochul
Announces Interborough Express Project Design and Environmental Review
Milestones") announces the Draft Environmental Impact Statement (DEIS) will
be released ahead of schedule later this year and that all 18 IBX stations
will be fully accessible with upgrades at IBX-subway connections in advance
of opening. Other active accessibility projects include the station
accessibility upgrades program (e.g. 68 St-Hunter College) and Penn Station
Access.
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_any_phrase, contains_phrase, final_answer, navigated_to_path, run_verifier)

TASK_ID = "MTA--15"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_ibx_project", navigated_to_path(traj, "/project/interborough-express"),
                "required: /project/interborough-express")
    judge.check("visited_ibx_press_release",
                navigated_to_path(traj, "/press-release/icymi-governor-hochul-announces-interborough-express-project-design-and-environmental"),
                "required: the September 9 IBX press release")
    judge.check("visited_other_project",
                navigated_to_path(traj, "/project/station-accessibility-upgrades")
                or navigated_to_path(traj, "/project/improving-accessibility-68-st-hunter-college-station")
                or navigated_to_path(traj, "/project/penn-station-access")
                or navigated_to_path(traj, "/project"),
                "required: another project page (station accessibility upgrades et al.)")
    judge.check("answer_light_rail_brooklyn_queens",
                contains_phrase(answer, "light rail")
                and contains_phrase(answer, "brooklyn") and contains_phrase(answer, "queens"),
                "IBX is a light rail line connecting Brooklyn and Queens")
    judge.check("answer_deis_milestone",
                contains_any_phrase(answer, ["draft environmental impact statement", "deis",
                                             "environmental review"]),
                "milestone: DEIS released ahead of schedule later this year")
    judge.check("answer_18_stations_accessible",
                contains_any_phrase(answer, ["18 stations", "fully accessible"]),
                "all 18 IBX stations will be fully accessible")
    judge.check("answer_other_accessibility_project",
                contains_any_phrase(answer, ["station accessibility", "68 st-hunter college",
                                             "penn station access", "accessibility upgrades"]),
                "must name another active accessibility project (and its target station)")
    judge.check("visited_hostos_pr",
                navigated_to_path(traj,
                    "/press-release/mta-unveils-accessibility-upgrades-149-st-hostos-station"),
                "required: the 149 St-Hostos accessibility press release")
    judge.check("visited_accessible_stations_list",
                navigated_to_path(traj, "/accessibility/stations"),
                "required: /accessibility/stations")
    judge.check("answer_hostos_upgrade",
                contains_phrase(answer, "hostos"),
                "the most recent station accessibility upgrade PR: 149 St-Hostos")
    judge.check("answer_hostos_on_accessible_list",
                contains_any_phrase(answer, ["appears on the accessible", "is on the accessible",
                                             "listed as accessible", "accessible stations list",
                                             "on the mta's accessible"]),
                "149 St-Hostos appears on the accessible stations list")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

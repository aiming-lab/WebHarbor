#!/usr/bin/env python3
"""Verify MTA--17.

Cousin takes the G train to Long Island City; the G line faces major
service changes in 2026. Find the MTA's announcement, summarize which
segments are affected and how long the work lasts, what travel alternatives
the MTA suggests, and what the service status board currently shows for the
G line.

Frozen ground truth (seed DB): the announcement is the CBTC signal-upgrade
project for the Crosstown Line (the G): CBTC installation between Court Sq
in Queens and Church Av in Brooklyn, construction on the line since 2023
(project status Construction; timeline lists "2023: CBTC construction work
begins on the Crosstown Line"). The G line alert page currently shows
"Planned - Stops Skipped" (In effect 2:45 AM Sep 22 until 9:00 AM Sep 25,
2026): Coney Island-bound F / Church Av-bound G skip 4 Av-9 St, 15
St-Prospect Park and Fort Hamilton Pkwy; alternatives: take the F or G to
7 Av or Church Av and transfer (to a Manhattan-bound F / Court Square-bound
G), or from those stations to 7 Av or Smith-9 Sts and transfer back.
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_any_phrase, contains_phrase, contains_time, final_answer, navigated_planned_changes, navigated_timetable, navigated_to_path, run_verifier)

TASK_ID = "MTA--17"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_g_alert_page", navigated_to_path(traj, "/alerts/line/G"),
                "required: /alerts/line/G (current status)")
    judge.check("visited_cbtc_project",
                navigated_to_path(traj, "/project/cbtc-signal-upgrades"),
                "required: /project/cbtc-signal-upgrades (the announcement)")
    judge.check("answer_crosstown_cbtc",
                contains_phrase(answer, "cbtc") or contains_phrase(answer, "signal"),
                "the work is CBTC signal modernization on the Crosstown Line")
    judge.check("answer_segments_court_sq_church_av",
                contains_phrase(answer, "court sq") and contains_phrase(answer, "church av"),
                "segment: Court Sq (Queens) to Church Av (Brooklyn)")
    judge.check("answer_since_2023", contains_phrase(answer, "2023"),
                "construction on the Crosstown Line began in 2023")
    judge.check("answer_current_status",
                contains_any_phrase(answer, ["planned - stops skipped", "stops skipped",
                                             "planned service change", "planned work"]),
                "the status board currently shows a Planned - Stops Skipped alert for the G")
    judge.check("answer_alternatives",
                contains_any_phrase(answer, ["7 av", "smith-9 sts", "transfer", "shuttle"]),
                "must state the MTA's travel alternatives")
    judge.check("visited_g_weekend_changes",
                navigated_planned_changes(traj, "subway", "weekend"),
                "required: /planned-service-changes?mode=subway&when=weekend")
    judge.check("visited_g_timetable",
                navigated_timetable(traj, "/schedules/subway/g"),
                "required: the G timetable page")
    judge.check("answer_f_affected",
                contains_any_phrase(answer, ["coney island-bound f", "the f", "f train", "f is",
                                             "f too", "roommate's f", "affect the f", "affects the f"]),
                "the same alert covers the Coney Island-bound F")
    judge.check("answer_weekend_g_suspension",
                contains_phrase(answer, "bedford-nostrand") and contains_phrase(answer, "court sq"),
                "weekend: no G between Bedford-Nostrand Avs and Court Sq")
    judge.check("answer_t403_shuttle",
                contains_phrase(answer, "t403") or contains_phrase(answer, "shuttle"),
                "free T403 shuttle buses replace the G segment")
    judge.check("answer_cbtc_since_2023",
                contains_phrase(answer, "2023"),
                "CBTC construction on the line since 2023")
    judge.check("answer_first_g_706",
                contains_time(answer, "7:06") or contains_phrase(answer, "7:06"),
                "first weekday G from Court Sq toward Brooklyn after 7 a.m.: 7:06")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

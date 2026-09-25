#!/usr/bin/env python3
"""Verify MTA--2.

Aunt uses a power wheelchair, meeting friends at 14 St-Union Sq. Is the
station listed as accessible, which platforms do the elevators serve, is any
elevator/escalator currently out, when is it expected back, what alternative
does the MTA suggest.

Frozen ground truth (seed DB): 14 St-Union Sq is accessible for the L, N,
Q, R, W platforms only ("L N Q R W only; 4 5 6 are not accessible" — station
L03/R20). The only CURRENT outage at the station is third-party escalator
ES258X (14 St & 4th Ave to mezzanine), out since 09/22/2026 5:04 PM for
Repair, estimated return 09/25/2026 6:00 PM; the status page lists no
alternative-route text for it. Elevator outages EL218 (mezzanine -> L
platform) and EL220 (mezzanine -> downtown N/Q/R/W platform) are upcoming
(09/25 10 PM) with full replacement alternatives.
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_any_phrase, contains_phrase, contains_time, final_answer, navigated_elevator_search, navigated_to_path_any, normalized_url_path, run_verifier, site_urls)

TASK_ID = "MTA--2"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_station_page",
                navigated_to_path_any(traj, ["/station/L03", "/station/R20", "/station/635"]),
                "required: a 14 St-Union Sq station page (/station/L03|R20|635)")
    judge.check("visited_elevator_status_search",
                navigated_elevator_search(traj, "Union Sq"),
                "required: /elevator-escalator-status?station=…Union Sq…")
    judge.check("answer_accessible_yes",
                contains_any_phrase(answer, ["accessible", "wheelchair"]),
                "must state whether the station is accessible")
    judge.check("answer_platforms_l_nqrw",
                contains_any_phrase(answer, ["l n q r w", "l, n, q, r, w", "l/n/q/r/w",
                                             "l, n, q and r", "l n q r and w"]),
                "accessible platforms are L/N/Q/R/W (4/5/6 are not)")
    judge.check("answer_escalator_es258x",
                contains_phrase(answer, "es258x") or contains_phrase(answer, "escalator"),
                "the current outage is escalator ES258X")
    judge.check("answer_reason_repair", contains_phrase(answer, "repair"),
                "outage reason is Repair")
    judge.check("answer_eta_0925",
                (contains_phrase(answer, "09/25/2026") or contains_phrase(answer, "september 25")
                 or contains_phrase(answer, "sep 25"))
                and (contains_time(answer, "18:00") or contains_time(answer, "6:00", "p")),
                "estimated return 09/25/2026 6:00 PM (the date AND the evening time; "
                "audit r2 hardening: a wrong ETA that only borrows the date from the "
                "upcoming-maintenance sentence no longer passes)")
    judge.check("answer_alternative_honesty",
                contains_any_phrase(answer, ["no alternative", "none listed", "no alternative-route",
                                             "alternative while out", "replacement",
                                             "no alternative is"]),
                "must address what alternative the MTA suggests (none is listed for ES258X)")
    judge.check("visited_upcoming_outages_view",
                any("upcoming=1" in u for u in site_urls(traj)
                    if normalized_url_path(u) == "/elevator-escalator-status"),
                "required: the elevator status page's upcoming-outages view for the station")
    judge.check("answer_upcoming_el218_el220",
                contains_phrase(answer, "el218") and contains_phrase(answer, "el220"),
                "upcoming maintenance: EL218 (L platform) and EL220 (downtown N/Q/R/W)")
    judge.check("answer_upcoming_maintenance",
                contains_phrase(answer, "maintenance") or contains_phrase(answer, "upcoming")
                or contains_phrase(answer, "scheduled"),
                "the upcoming outages are maintenance windows")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

#!/usr/bin/env python3
"""Verify MTA--12.

Bikes from Brooklyn to the USTA Billie Jean King National Tennis Center on a
weekday evening: can bikes be taken on LIRR trains at that time and what
rush-hour rules apply, how does the MTA recommend reaching the tennis center
by transit, and what does the bike guide say about locking bikes to MTA
property.

Frozen ground truth (seed DB): LIRR bike regulations — bikes are not allowed
at rush hour: weekday inbound trains arriving NYC 6 a.m.-10 a.m., weekday
outbound trains departing NYC 3 p.m.-8 p.m.; weekday limit 4 bikes per
train. Tennis center guide: the 7 train stops at Mets-Willets Point (and
the LIRR Port Washington Branch serves Mets-Willets Point station). Bike
guide: don't lock bikes on board or at any MTA facility; bicycles chained to
MTA property are removed and delivered to the Lost Property Unit.
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_amount, contains_any_phrase, contains_phrase, final_answer, navigated_to_path, normalized_url_path, run_verifier, site_urls)

import re
from urllib.parse import parse_qs, urlparse

TASK_ID = "MTA--12"

# r3 sub-ask ground truth (seed DB, frozen): the 7's weekday timetable lists
# near-continuous evening service at Mets-Willets Point (both directions,
# 17:00-23:59), so the answer gate accepts any clock time with minutes in the
# evening window (24h form or 12h form with a p.m. marker), e.g. the 18:02.
# Verified live in the r3 re-review walks against a fresh native-Dockerfile
# build at bc2be8b8.
_EVENING_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)?")


def _navigated_7_weekday_timetable(traj):
    """The 7 train timetable opened on its default/weekday view."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/schedules/subway/7-train":
            continue
        q = parse_qs(urlparse(str(u)).query)
        days = q.get("day", [])
        if not days or "weekday" in days:
            return True
    return False


def _has_evening_train_time(answer):
    """A clock time with minutes in the evening window (17:00-23:59)."""
    for m in _EVENING_TIME_RE.finditer(answer):
        hour = int(m.group(1))
        meridiem = (m.group(3) or "").replace(".", "")
        if meridiem == "pm" and 1 <= hour < 12:
            hour += 12
        if 17 <= hour <= 23:
            return True
    return False


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_bikes_guide", navigated_to_path(traj, "/guides/bikes"),
                "required: /guides/bikes")
    judge.check("visited_lirr_bike_regs",
                navigated_to_path(traj, "/guides/bikes/bike-regulations-lirr"),
                "required: /guides/bikes/bike-regulations-lirr")
    judge.check("visited_tennis_center",
                navigated_to_path(traj, "/guides/stadiums/national-tennis-center-queens"),
                "required: /guides/stadiums/national-tennis-center-queens")
    judge.check("answer_no_bikes_rush_hour",
                contains_any_phrase(answer, ["not allowed", "no bikes", "cannot", "can't", "banned"]),
                "bikes are not allowed on LIRR rush-hour trains")
    judge.check("answer_outbound_3_to_8",
                contains_phrase(answer, "3 p.m.") and contains_phrase(answer, "8 p.m."),
                "outbound rush window: trains departing NYC 3 p.m.-8 p.m.")
    judge.check("answer_4_bikes_per_train",
                contains_any_phrase(answer, ["4 bicycles per train", "four bikes", "4 bikes"]),
                "weekday limit: 4 bikes per train")
    judge.check("answer_7_to_mets_willets",
                contains_phrase(answer, "mets-willets point"),
                "the 7 train stops at Mets-Willets Point for the tennis center")
    judge.check("answer_locking_rule",
                contains_any_phrase(answer, ["lost property unit", "don't lock", "do not lock",
                                              "not lock", "removed"]),
                "bikes locked to MTA property are removed to the Lost Property Unit")
    judge.check("visited_us_open_pr",
                navigated_to_path(traj,
                    "/press-release/mta-and-usta-announce-added-subway-and-long-island-rail-road-service-us-open"),
                "required: the US Open added-service press release")
    judge.check("answer_extra_trains",
                contains_any_phrase(answer, ["additional trains", "extra trains", "added trains",
                                             "supplemental trains", "extra service", "added service",
                                             "added stops", "trains added", "added lirr"])
                or (contains_phrase(answer, "extra") and contains_phrase(answer, "train")),
                "the announcement covers added trains for the tournament")
    judge.check("answer_cityticket_fare",
                contains_phrase(answer, "cityticket") and contains_amount(answer, 5.00),
                "CityTicket fares as low as $5 (off-peak; $7 peak)")
    judge.check("visited_7_weekday_timetable",
                _navigated_7_weekday_timetable(traj),
                "required: /schedules/subway/7-train (the 7's weekday timetable)")
    judge.check("answer_mets_willets_evening_train",
                contains_phrase(answer, "mets-willets point") and _has_evening_train_time(answer),
                "an evening train time at Mets-Willets Point from the 7's weekday timetable")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

#!/usr/bin/env python3
"""Shared deterministic FlightAware task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED here (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (numbers / tokens / phrases,
     negation-aware, tolerant of separators)
  4. DB after-state: read-only tasks leave every table byte-identical; stateful
     tasks (7, 8, 23) must produce exactly the requested alert mutation and
     preserve every other table.

Frozen seed facts the checks are anchored on (instance_seed/flightaware.db,
md5 815bd0d169b1fcd7ebaeca03f281c4ac, rebuilt deterministically by
seed_data.py from the tracked _seed_*.py snapshots, mirror date 2026-09-22):
  395 airports / 1726 flights / 79 photos / 14 squawks / 4 benchmark users
  (alice/bob/carol/david, password TestPass123!) with seeded alerts.
"""
import re
import sys

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, new_rows,
    tables_unchanged, navigated_path, navigated_query, navigated_prefix,
    url_path, step_urls, contains_number, affirm_number, affirms, affirms_any,
    contains_all, contains_any, affirm_time, affirm_token, norm, final_answer,
    step_text,
)

# ---------------------------------------------------------------- ground truth
# Flight page facts (frozen seed flights table, is_today rows)
UAL1063 = dict(gate="C71", sched_dep="08:28AM", actual_dep="08:22AM", ac="B38M",
               ac_name="Boeing 737 MAX 8", route4=["ELVAE", "NECCK", "WHITE", "Q409"])
UAL1063_0920 = ("4h 48m", "B38M")
UAL1063_PAST_B38M = 10
UAL1063_PAST_LATEST = "21"          # September 21, 2026
EVA17 = dict(gate="A8", terminal="2", speed=501, planned_speed=564, ac="B77W",
             ac_name="777-300ER")
AAL169 = dict(origin="KLAX", dest="HND", ac="B789")
AAL170 = dict(origin="HND", dest="KLAX", ac="B789")

# Airport board facts (frozen seed board_rows)
KBOS_DEP_FIRST = ("RPA5597", "E75S", "Jacksonville Intl (JAX)", "08:58a")
KJFK_ARR_EZE = ("AAL954", "B772")
KJFK_ENROUTE_DXB = ("UAE203", "A388", "08:58a")
EGLL_DEP_FIRST = ("VIR208", "B789", "Incheon Int'l (ICN)", "01:58p")

# Delay / cancellation statistics (frozen seed)
DELAYS_50MIN_AIRPORT = ("Manchester", "MAN", "EGCC")
MISERYMAP_US_DELAYS = 938
AUCKLAND = ("Auckland", "AKL", "NZAA")
CANCEL_TOP = ("PSA Airlines (AAL)", 54, "7%")
CANCEL_TOTALS = (537, 183)

# Photos (frozen seed photos table)
TOP_PHOTO = ("McDonnell Douglas FA-18 (18-8738)", "William Gilson", 850)
FDX_DC10 = ("N368FE", 699, "4.85", 543751)
UA_789_PHOTO = ("United B789 (N27957)", "N27957", "Victor Pody", 250)

# Squawks (frozen seed squawks table)
MOST_DISCUSSED = ("Why Aren’t Passengers Who Evacuate With Bags Being Punished?",
                  126, "Roger Anderson")
METEORITE = ("Possible Meteorite Strikes United 737; Injures Pilot", "weatherboy.com",
             27, 49)
AMANDA = ("FlightAware's Role in Airspace Modernization", "blog.flightaware.com")
UPS_MOURN = "UPS pilots mourn loss of colleagues killed in plane crash"

# Browse facts (frozen seed)
FINDFLIGHT_EWR_MEX = (1, ["UAL1063"])
DAL_TRACKED = 148
JBU_TRACKED = 33
B789_TRACKED = 29
B789_JFK_LHR = "VIR26"
SEARCH_CHANGI = ("SIN", 0)

# Airport resources (frozen seed airports table)
JFK_WEATHER = ("Partly cloudy", "Windy", "60")
JFK_A110_2 = "Flocks of birds on and in vicinity of airport."

# Benchmark users / seeded alerts (frozen seed)
ALICE, BOB, CAROL, DAVID = 1, 2, 3, 4
BOB_ALERTS_SEED = 3           # AAL954 full, JBU1024 basic, KSFO->RJTT full
BOB_ALERTS_AFTER_ADD = 4
BOB_REMAINING_AFTER_DELETE = ("JBU1024", "KSFO", "RJTT")
CAROL_ALERTS_SEED = 1         # DAL667 basic
CAROL_ALERTS_AFTER_ADD = 2

PHOTO_PID_DC10 = "318841"
PHOTO_PID_UA789 = "1463354"

CONTAINER = "wh-rev-flightaware"

READONLY = {0, 1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
            20, 21, 22, 24, 25, 26, 27, 28, 29}
STATEFUL = {7, 8, 23}


def _alert_rows(db):
    data = rows(db)
    if data is None:
        return None
    return data.get("alerts", [])


def _check_readonly_db(j, init_db, after_db):
    drifted = tables_unchanged(init_db, after_db)
    if drifted is None:
        j.check("db_available", False, "cannot read initial/after DB snapshots")
        return
    j.check("db_readonly", not drifted,
            f"changed tables: {drifted}" if drifted else "all tables byte-identical")


def _user_alerts(db, user_id):
    alerts = _alert_rows(db)
    if alerts is None:
        return None
    return sorted((a for a in alerts if a.get("user_id") == user_id),
                 key=lambda r: r.get("id", 0))


def _alert_snapshot(db):
    data = rows(db)
    if data is None:
        return None
    return data


def _t0(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/flight/UAL1063")
    ans = final_answer(traj)
    j.check("nav_flight_page", navigated_path(traj, "/live/flight/UAL1063"),
            "must open the UAL1063 flight page")
    j.check("ans_gate", affirms(ans, "c71"), "gate C71")
    j.check("ans_sched_dep", affirm_time(ans, UAL1063["sched_dep"]), "scheduled 08:28AM")
    j.check("ans_actual_dep", affirm_time(ans, UAL1063["actual_dep"]), "actual 08:22AM")
    j.check("ans_aircraft", affirms_any(ans, ["737 max 8", "b38m"]), "Boeing 737 MAX 8")
    _check_readonly_db(j, init_db, after_db)


def _t1(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/airport/KBOS/departures")
    ans = final_answer(traj)
    j.check("nav_login", navigated_path(traj, "/account/login"), "must log in")
    j.check("nav_board", navigated_path(traj, "/live/airport/KBOS/departures"),
            "must open the KBOS departures board")
    j.check("ans_ident", affirm_token(ans, KBOS_DEP_FIRST[0]), f"first departure {KBOS_DEP_FIRST[0]}")
    j.check("ans_type", affirm_token(ans, KBOS_DEP_FIRST[1]), f"aircraft type {KBOS_DEP_FIRST[1]}")
    j.check("ans_dest", affirms(ans, "jacksonville"), "destination Jacksonville Intl (JAX)")
    j.check("ans_dep_time", affirm_time(ans, KBOS_DEP_FIRST[3]), "departure 08:58a EDT")
    _check_readonly_db(j, init_db, after_db)


def _t2(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/flight/UAL1063/history")
    ans = final_answer(traj)
    j.check("nav_history", navigated_path(traj, "/live/flight/UAL1063/history"),
            "must open the UAL1063 history page")
    j.check("ans_duration", affirms(ans, "4h 48m"), "Sep 20 duration 4h 48m")
    j.check("ans_aircraft", affirms_any(ans, ["b38m", "737 max 8"]), "aircraft B38M")
    _check_readonly_db(j, init_db, after_db)


def _t3(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/airport/delays")
    ans = final_answer(traj)
    j.check("nav_delays", navigated_path(traj, "/live/airport/delays"),
            "must open the worldwide airport delays page")
    j.check("ans_airport", affirms(ans, DELAYS_50MIN_AIRPORT[0]), "Manchester")
    j.check("ans_codes", affirms_any(ans, [DELAYS_50MIN_AIRPORT[1], DELAYS_50MIN_AIRPORT[2]]),
            "MAN / EGCC in parentheses")
    _check_readonly_db(j, init_db, after_db)


def _t4(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/cancelled")
    ans = final_answer(traj)
    j.check("nav_cancelled", navigated_path(traj, "/live/cancelled"),
            "must open the delay and cancellation statistics page")
    j.check("ans_airline", affirms(ans, "psa airlines"), "PSA Airlines (AAL)")
    j.check("ans_cancelled", affirm_number(ans, CANCEL_TOP[1]), "54 cancelled")
    j.check("ans_pct", affirms(ans, CANCEL_TOP[2]), "7%")
    _check_readonly_db(j, init_db, after_db)


def _t5(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/photos/")
    ans = final_answer(traj)
    ok_nav = (navigated_path(traj, "/photos/all/sort/votes")
              or navigated_prefix(traj, "/photos/view/214936"))
    j.check("nav_photos_votes", ok_nav,
            "must open the photos ranked by votes or the top photo's own page")
    j.check("ans_title", affirms(ans, "fa-18") and affirms(ans, "18-8738"),
            "title McDonnell Douglas FA-18 (18-8738)")
    j.check("ans_photographer", affirms(ans, "william gilson"), "photographer William Gilson")
    j.check("ans_votes", affirm_number(ans, TOP_PHOTO[2]), "850 votes")
    _check_readonly_db(j, init_db, after_db)


def _t6(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/squawks/")
    ans = final_answer(traj)
    ok_nav = (navigated_path(traj, "/squawks/browse/general/24_hours/most_discussed")
              or navigated_prefix(traj, "/squawks/"))
    j.check("nav_squawks", ok_nav, "must open the squawks (most discussed)")
    j.check("ans_title", affirms(ans, "evacuate with bags"), "title")
    j.check("ans_comments", affirm_number(ans, MOST_DISCUSSED[1]), "126 comments")
    j.check("ans_submitter", affirms(ans, "roger anderson"), "Roger Anderson")
    _check_readonly_db(j, init_db, after_db)


def _t7(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/account")
    ans = final_answer(traj)
    j.check("nav_login", navigated_path(traj, "/account/login"), "must log in")
    j.check("nav_account", navigated_path(traj, "/account/"), "must open the account page")
    st = step_text(traj)
    j.check("nav_alert_add", ("baw117" in norm(st)), "the add-alert form posts BAW117")
    before, after = _user_alerts(init_db, BOB), _user_alerts(after_db, BOB)
    if before is None or after is None:
        j.check("db_available", False, "cannot read alert rows")
        return
    j.check("db_alert_added", len(after) == BOB_ALERTS_AFTER_ADD and len(after) > len(before),
            f"bob alerts {len(before)} -> {len(after)} (expected {BOB_ALERTS_AFTER_ADD})")
    added = [a for a in after if a.get("ident") == "BAW117"]
    j.check("db_new_alert_row",
            len(added) == 1 and added[0].get("alert_type") == "basic"
            and not added[0].get("origin_code") and not added[0].get("dest_code"),
            f"new row {added}")
    j.check("db_others_unchanged",
            tables_unchanged(init_db, after_db, ignore=("alerts",)) == [],
            "only the alerts table may change")
    j.check("ans_total", affirm_number(ans, BOB_ALERTS_AFTER_ADD), "4 alerts in total")
    j.check("ans_new_alert", affirms(ans, "baw117") and affirms(ans, "basic"),
            "the BAW117 basic alert just created")


def _t8(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/account")
    ans = final_answer(traj)
    j.check("nav_login", navigated_path(traj, "/account/login"), "must log in")
    j.check("nav_account", navigated_path(traj, "/account/"), "must open the account page")
    before, after = _user_alerts(init_db, BOB), _user_alerts(after_db, BOB)
    if before is None or after is None:
        j.check("db_available", False, "cannot read alert rows")
        return
    removed = [a for a in before if a not in after]
    kept = [a for a in after if a in before]
    j.check("db_alert_deleted",
            len(after) == len(before) - 1 and len(removed) == 1
            and removed[0].get("ident") == "AAL954",
            f"removed {removed}; kept {len(kept)}")
    j.check("db_others_unchanged",
            tables_unchanged(init_db, after_db, ignore=("alerts",)) == [],
            "only the alerts table may change")
    j.check("ans_remaining_idents", affirms(ans, "jbu1024"),
            "remaining flight alert JBU1024")
    j.check("ans_remaining_route", affirms(ans, "ksfo") and affirms(ans, "rjtt"),
            "remaining route alert KSFO → RJTT")


def _t9(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/flight/EVA17")
    ans = final_answer(traj)
    j.check("nav_flight_page", navigated_path(traj, "/live/flight/EVA17"),
            "must open the EVA17 flight page")
    j.check("ans_gate", affirm_token(ans, "a8"), "gate A8")
    j.check("ans_terminal", affirm_number(ans, 2), "terminal 2")
    j.check("ans_speed", affirm_number(ans, EVA17["speed"]), "501 mph")
    j.check("ans_planned_speed", affirm_number(ans, EVA17["planned_speed"]), "564 mph")
    j.check("ans_aircraft", affirms_any(ans, ["777-300er", "b77w"]), "777-300ER")
    _check_readonly_db(j, init_db, after_db)


def _t10(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/findflight")
    ans = final_answer(traj)
    ok_nav = navigated_query(traj, "/live/findflight", origin={"newark", "kewr", "ewr"},
                             destination={"mexico city", "mex", "mmmx"})
    j.check("nav_findflight_query", ok_nav,
            "must search the Flight Finder for Newark -> Mexico City")
    j.check("ans_count", affirm_number(ans, FINDFLIGHT_EWR_MEX[0]), "1 flight")
    j.check("ans_ident", affirm_token(ans, "UAL1063"), "UAL1063")
    _check_readonly_db(j, init_db, after_db)


def _t11(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/fleet/DAL")
    ans = final_answer(traj)
    j.check("nav_fleet_dal", navigated_path(traj, "/live/fleet/DAL"), "must open the DAL fleet page")
    j.check("nav_fleet_jbu", navigated_path(traj, "/live/fleet/JBU"), "must open the JBU fleet page")
    j.check("ans_dal", affirm_number(ans, DAL_TRACKED), "148 Delta flights")
    j.check("ans_jbu", affirm_number(ans, JBU_TRACKED), "33 JetBlue flights")
    _check_readonly_db(j, init_db, after_db)


def _t12(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/resources/airport/KJFK/weather")
    ans = final_answer(traj)
    j.check("nav_weather", navigated_path(traj, "/resources/airport/KJFK/weather"),
            "must open the JFK weather page")
    j.check("ans_conditions", affirms(ans, "partly cloudy"), "Partly cloudy")
    j.check("ans_wind", affirms(ans, "windy"), "Windy")
    j.check("ans_temp", affirm_number(ans, JFK_WEATHER[2]), "60 °F")
    _check_readonly_db(j, init_db, after_db)


def _t13(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/resources/airport/KJFK/remarks")
    ans = final_answer(traj)
    j.check("nav_remarks", navigated_path(traj, "/resources/airport/KJFK/remarks"),
            "must open the JFK remarks page")
    j.check("ans_code", affirms(ans, "a110-2"), "remark code A110-2")
    j.check("ans_text", affirms(ans, "flocks of birds"), "Flocks of birds warning")
    _check_readonly_db(j, init_db, after_db)


def _t14(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/airport/KJFK/arrivals")
    ans = final_answer(traj)
    j.check("nav_login", navigated_path(traj, "/account/login"), "must log in")
    j.check("nav_board", navigated_path(traj, "/live/airport/KJFK/arrivals"),
            "must open the KJFK arrivals board")
    j.check("ans_ident", affirm_token(ans, KJFK_ARR_EZE[0]), "AAL954")
    j.check("ans_type", affirm_token(ans, KJFK_ARR_EZE[1]), "B772")
    _check_readonly_db(j, init_db, after_db)


def _t15(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/flight/AAL170")
    ans = final_answer(traj)
    j.check("nav_aal169", navigated_path(traj, "/live/flight/AAL169"), "must open AAL169")
    j.check("nav_aal170", navigated_path(traj, "/live/flight/AAL170"), "must open AAL170")
    j.check("ans_dep_la", affirms(ans, "aal169") and re.search(r"aal169[^.]*departs?[^.]*los angeles", norm(ans)) is not None,
            "AAL169 departs Los Angeles")
    j.check("ans_arr_la", affirms(ans, "aal170") and re.search(r"aal170[^.]*arrives?[^.]*los angeles", norm(ans)) is not None,
            "AAL170 arrives at Los Angeles")
    j.check("ans_types", affirms_any(ans, ["787-9", "b789"]), "Boeing 787-9")
    _check_readonly_db(j, init_db, after_db)


def _t16(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/squawks/")
    ans = final_answer(traj)
    j.check("nav_squawks", navigated_prefix(traj, "/squawks/"), "must open the squawks")
    j.check("ans_title", affirms(ans, "meteorite strikes united 737"), "title")
    j.check("ans_source", affirms(ans, METEORITE[1]), "weatherboy.com")
    j.check("ans_comments", affirm_number(ans, METEORITE[2]), "27 comments")
    _check_readonly_db(j, init_db, after_db)


def _t17(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/miserymap")
    ans = final_answer(traj)
    j.check("nav_miserymap", navigated_path(traj, "/miserymap/"), "must open the MiseryMap page")
    j.check("ans_total", affirm_number(ans, MISERYMAP_US_DELAYS), "938 total delays")
    j.check("ans_airport", affirms(ans, AUCKLAND[0]), "Auckland")
    j.check("ans_code", affirms_any(ans, [AUCKLAND[1], AUCKLAND[2]]), "AKL / NZAA")
    _check_readonly_db(j, init_db, after_db)


def _t18(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/form.rvt")
    ans = final_answer(traj)
    ok_nav = (navigated_query(traj, "/live/form.rvt", query={"singapore changi"})
              and navigated_query(traj, "/live/form.rvt", query={"changi"}))
    j.check("nav_searches", ok_nav, "must search 'Singapore Changi' and 'Changi'")
    j.check("ans_code", affirm_token(ans, "sin"), "airport code SIN")
    j.check("ans_photo_count",
            (affirm_number(ans, SEARCH_CHANGI[1]) and affirms_any(ans, ["no photos", "none", "0 photos"]))
            or (affirm_number(ans, 0) and "photo" in norm(ans)),
            "0 photos in the Changi search results")
    _check_readonly_db(j, init_db, after_db)


def _t19(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/photos/view/")
    ans = final_answer(traj)
    j.check("nav_photo_detail", navigated_prefix(traj, f"/photos/view/{PHOTO_PID_DC10}"),
            "must open the DC-10 photo detail page")
    j.check("nav_photos_section", navigated_prefix(traj, "/photos/"), "photos section navigation")
    j.check("ans_reg", affirm_token(ans, "n368fe"), "registration N368FE")
    j.check("ans_votes", affirm_number(ans, FDX_DC10[1]), "699 votes")
    j.check("ans_average", affirms(ans, FDX_DC10[2]), "4.85 average")
    j.check("ans_views", affirm_number(ans, FDX_DC10[3]), "543,751 views")
    _check_readonly_db(j, init_db, after_db)


def _t20(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/cancelled")
    ans = final_answer(traj)
    j.check("nav_cancelled", navigated_path(traj, "/live/cancelled"),
            "must open the cancellation statistics page")
    j.check("ans_world", affirm_number(ans, CANCEL_TOTALS[0]), "537 worldwide")
    j.check("ans_us", affirm_number(ans, CANCEL_TOTALS[1]), "183 US")
    _check_readonly_db(j, init_db, after_db)


def _t21(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/squawks/")
    ans = final_answer(traj)
    j.check("nav_squawks", navigated_prefix(traj, "/squawks/"), "must open the squawks")
    j.check("ans_title", affirms(ans, "airspace modernization"), "title")
    j.check("ans_source", affirms(ans, AMANDA[1]), "(blog.flightaware.com)")
    _check_readonly_db(j, init_db, after_db)


def _t22(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/airport/KJFK/enroute")
    ans = final_answer(traj)
    j.check("nav_login", navigated_path(traj, "/account/login"), "must log in")
    j.check("nav_board", navigated_path(traj, "/live/airport/KJFK/enroute"),
            "must open the KJFK en-route board")
    j.check("ans_airline", affirms(ans, "emirates"), "Emirates")
    j.check("ans_ident", affirm_token(ans, KJFK_ENROUTE_DXB[0]), "UAE203")
    j.check("ans_type", affirms_any(ans, ["a388", "a380"]), "A388 / A380")
    j.check("ans_arrival", affirm_time(ans, KJFK_ENROUTE_DXB[2]), "08:58a EDT")
    _check_readonly_db(j, init_db, after_db)


def _t23(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/account")
    ans = final_answer(traj)
    j.check("nav_login", navigated_path(traj, "/account/login"), "must log in")
    j.check("nav_account", navigated_path(traj, "/account/"), "must open the account page")
    st = step_text(traj)
    j.check("nav_alert_add", ("jfk" in norm(st) and "lhr" in norm(st)),
            "the add-alert form posts JFK -> LHR")
    before, after = _user_alerts(init_db, CAROL), _user_alerts(after_db, CAROL)
    if before is None or after is None:
        j.check("db_available", False, "cannot read alert rows")
        return
    j.check("db_alert_added", len(after) == CAROL_ALERTS_AFTER_ADD and len(after) > len(before),
            f"carol alerts {len(before)} -> {len(after)} (expected {CAROL_ALERTS_AFTER_ADD})")
    added = [a for a in after if a not in before]
    ok_row = (len(added) == 1 and added[0].get("alert_type") == "full"
              and str(added[0].get("origin_code", "")).upper() in {"JFK", "KJFK"}
              and str(added[0].get("dest_code", "")).upper() in {"LHR", "EGLL"})
    j.check("db_new_alert_row", ok_row, f"new row {added}")
    j.check("db_others_unchanged",
            tables_unchanged(init_db, after_db, ignore=("alerts",)) == [],
            "only the alerts table may change")
    j.check("ans_had", affirm_number(ans, CAROL_ALERTS_SEED), "had 1 alert")
    j.check("ans_new_line",
            (affirms(ans, "jfk") and affirms(ans, "lhr") and affirms(ans, "full")
             and affirms(ans, "just now")),
            "new line JFK → LHR | full | just now")


def _t24(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/airport/EGLL/departures")
    ans = final_answer(traj)
    j.check("nav_login", navigated_path(traj, "/account/login"), "must log in")
    j.check("nav_board", navigated_path(traj, "/live/airport/EGLL/departures"),
            "must open the EGLL departures board")
    j.check("ans_ident", affirm_token(ans, EGLL_DEP_FIRST[0]), "VIR208")
    j.check("ans_type", affirm_token(ans, EGLL_DEP_FIRST[1]), "B789")
    j.check("ans_dest", affirms(ans, "incheon"), "Incheon Int'l (ICN)")
    j.check("ans_dep_time", affirm_time(ans, EGLL_DEP_FIRST[3]), "01:58p BST")
    _check_readonly_db(j, init_db, after_db)


def _t25(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/aircrafttype/B789")
    ans = final_answer(traj)
    j.check("nav_type_page", navigated_path(traj, "/live/aircrafttype/B789"),
            "must open the B789 aircraft type page")
    j.check("ans_count", affirm_number(ans, B789_TRACKED), "29 flights today")
    j.check("ans_ident", affirm_token(ans, B789_JFK_LHR), "VIR26 JFK -> LHR")
    _check_readonly_db(j, init_db, after_db)


def _t26(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/photos/view/")
    ans = final_answer(traj)
    j.check("nav_photo_detail", navigated_prefix(traj, f"/photos/view/{PHOTO_PID_UA789}"),
            "must open the United B789 photo detail page")
    j.check("nav_photos_section", navigated_prefix(traj, "/photos/"), "photos section navigation")
    j.check("ans_title", affirms(ans, "united b789"), "title United B789")
    j.check("ans_reg", affirm_token(ans, "n27957"), "registration N27957")
    j.check("ans_photographer", affirms(ans, "victor pody"), "Victor Pody")
    j.check("ans_votes", affirm_number(ans, UA_789_PHOTO[3]), "250 votes")
    _check_readonly_db(j, init_db, after_db)


def _t27(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/flight/UAL1063")
    ans = final_answer(traj)
    j.check("nav_flight_page", navigated_path(traj, "/live/flight/UAL1063"),
            "must open the UAL1063 flight page")
    waypoints = UAL1063["route4"]
    j.check("ans_waypoints", contains_all(ans, waypoints), f"first four {waypoints}")
    positions = []
    norm_ans = norm(ans)
    for w in waypoints:
        idx = norm_ans.find(w.casefold())
        j.check(f"ans_wp_{w.casefold()}", idx >= 0, f"{w} present")
        positions.append(idx)
    j.check("ans_waypoint_order", positions == sorted(positions) and -1 not in positions,
            f"order {waypoints}")
    _check_readonly_db(j, init_db, after_db)


def _t28(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/live/flight/UAL1063/history")
    ans = final_answer(traj)
    j.check("nav_history", navigated_path(traj, "/live/flight/UAL1063/history"),
            "must open the UAL1063 history page")
    j.check("ans_count", affirm_number(ans, UAL1063_PAST_B38M), "10 past B38M flights")
    j.check("ans_latest_date",
            affirms_any(ans, ["september 21", "sep 21", "2026-09-21", "09/21", "9/21", "21 september"]),
            "most recent past date Sep 21, 2026")
    _check_readonly_db(j, init_db, after_db)


def _t29(j, traj, init_db, after_db):
    j.bind_run(traj, shot_url="/squawks/search.rvt")
    ans = final_answer(traj)
    ok_nav = (navigated_query(traj, "/squawks/search.rvt", q={"meteorite"})
              and navigated_query(traj, "/squawks/search.rvt", q={"ups"}))
    j.check("nav_squawk_searches", ok_nav, "must search squawks for 'meteorite' and 'UPS'")
    j.check("ans_meteorite_title", affirms(ans, "meteorite strikes united 737"), "meteorite title")
    j.check("ans_meteorite_votes", affirm_number(ans, METEORITE[3]), "49 votes")
    j.check("ans_ups_title", affirms(ans, "pilots mourn"), "UPS pilots mourn title")
    _check_readonly_db(j, init_db, after_db)


TASKS = {0: _t0, 1: _t1, 2: _t2, 3: _t3, 4: _t4, 5: _t5, 6: _t6, 7: _t7, 8: _t8,
         9: _t9, 10: _t10, 11: _t11, 12: _t12, 13: _t13, 14: _t14, 15: _t15,
         16: _t16, 17: _t17, 18: _t18, 19: _t19, 20: _t20, 21: _t21, 22: _t22,
         23: _t23, 24: _t24, 25: _t25, 26: _t26, 27: _t27, 28: _t28, 29: _t29}


def grade(number):
    args = parse_args()
    traj = load_run(args.run_dir)
    j = Judge(f"FlightAware--{number}", no_llm=args.no_llm)
    init_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    TASKS[number](j, traj, init_db, after_db)
    j.emit()

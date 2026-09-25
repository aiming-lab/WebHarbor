"""Amtrak grading: natural answers, observed browsing and exact saved state."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse
from answer_contract import equivalent, parse_answer
from natural_answer import checks as natural_checks
from checkout_state import check_checkout
from verify_lib import (
    Judge,
    check_trajectory_identity,
    check_read_only,
    check_results_visited,
    check_paths_in_order,
    check_visited_path,
    check_signed_in_as,
    db_query,
    load_run,
    parse_args,
    resolve_snapshots,
    fail_closed,
    final_answer,
    reward_row,
    user_row,
    rows_unchanged_except,
    row_diff_columns,
    check_tables_unchanged,
    MUTABLE_TABLES,
    LOG_TABLES,
    site_urls,
    _param_matches,
)


def one(db, sql, params=()):
    rows = db_query(db, sql, params)
    if len(rows) != 1:
        raise ValueError("expected one fixture row")
    return dict(rows[0])


def stops(db, slug):
    return [
        r["station_code"]
        for r in db_query(
            db,
            "SELECT s.station_code FROM route_stops s JOIN routes r ON r.id=s.route_id WHERE r.slug=? ORDER BY s.stop_order",
            (slug,),
        )
    ]


def baggage(db, codes):
    return {
        code: bool(
            one(db, "SELECT has_checked_baggage FROM stations WHERE code=?", (code,))[
                "has_checked_baggage"
            ]
        )
        for code in codes
    }


def direct_quotes(db, origin, destination, day, slug):
    quotes = []
    for raw in db_query(
        db,
        "SELECT t.*,r.name AS route_name,tr.number FROM trips t JOIN routes r ON r.id=t.route_id JOIN trains tr ON tr.id=t.train_id WHERE t.service_date=?",
        (day,),
    ):
        trip = dict(raw)
        parts = [
            dict(r)
            for r in db_query(
                db,
                "SELECT * FROM trip_segments WHERE trip_id=? ORDER BY leg_order",
                (trip["id"],),
            )
        ]
        starts = [i for i, s in enumerate(parts) if s["from_station_code"] == origin]
        ends = [i for i, s in enumerate(parts) if s["to_station_code"] == destination]
        if not starts or not ends or starts[0] > ends[0]:
            continue
        fare = one(
            db,
            "SELECT fo.* FROM fare_options fo JOIN fare_classes fc ON fc.id=fo.fare_class_id WHERE fo.trip_id=? AND fc.slug=?",
            (trip["id"], slug),
        )
        if fare["availability"] <= 0:
            continue
        selected = parts[starts[0] : ends[0] + 1]
        ratio = max(
            0.28,
            min(
                1.0,
                sum(s["duration_minutes"] for s in selected)
                / max(trip["duration_minutes"], 1),
            ),
        )
        quotes.append(
            {
                "route": trip["route_name"],
                "train": trip["number"],
                "price": round(trip["base_fare"] * ratio * fare["multiplier"], 2),
                "depart": selected[0]["depart_dt"],
            }
        )
    if not quotes:
        raise ValueError("fixture has no direct options")
    return sorted(quotes, key=lambda q: q["price"])


def expected_answer(n, initial, after=None):
    fixed = {
        0: {"route": "Acela Express", "train": "2151", "total_minutes": 170},
        1: {"route": "Northeast Regional", "starting_fare_usd": 26.88},
        2: {"business_per_traveler_usd": 124.83},
        3: {"value_per_traveler_usd": 169.65},
        4: {"room": "Roomette", "extra_usd": 316},
        8: {"preferred_station": "SEA"},
        12: {"route": "California Zephyr", "flexible_fare_usd": 96.56},
    }
    if n in fixed:
        return fixed[n]
    if n == 5:
        b = one(initial, "SELECT * FROM bookings WHERE booking_code='ALJDAM'")
        return {
            "booking_code": b["booking_code"],
            "origin": b["origin_code"],
            "departure_date": b["departure_date"],
            "recorded_total_usd": b["total_amount"],
            "current_flexible_total_usd": 108.56,
            "increase_usd": 2.5,
        }
    if n == 6:
        return {
            "route": "Acela Express",
            "departure_date": "2026-04-20",
            "recorded_total_usd": 99.74,
            "current_business_total_usd": 102.24,
            "increase_usd": 2.5,
        }
    if n == 7:
        a, b = reward_row(initial, "alice.j@test.com"), reward_row(
            initial, "bob.c@test.com"
        )
        fields = lambda row: {
            "balance": row["points_balance"],
            "ytd": row["points_ytd"],
            "status_credits": row["status_credits"],
        }
        return {
            "alice": fields(a),
            "bob": fields(b),
            "alice_minus_bob_points": a["points_balance"] - b["points_balance"],
        }
    if n == 9:
        codes = stops(initial, "amtrak-cascades")
        return {"ordered_stops": codes, "checked_baggage": baggage(initial, codes)}
    if n == 10:
        alert = one(
            initial,
            "SELECT a.* FROM service_alerts a JOIN routes r ON r.id=a.route_id WHERE r.slug='coast-starlight' AND a.severity='Major Advisory'",
        )
        return {"next_step": alert["next_step"], "room": "Roomette", "extra_usd": 316}
    if n == 11:
        trip = one(
            initial,
            "SELECT s.depart_dt FROM trip_segments s JOIN trips t ON t.id=s.trip_id JOIN trains tr ON tr.id=t.train_id WHERE s.from_station_code='DEN' AND t.service_date='2026-04-20' AND tr.number='5'",
        )
        return {
            "advisory_track": 3,
            "westbound_train": "5",
            "departure_time": trip["depart_dt"][11:16],
            "checked_baggage": baggage(initial, ["DEN"])["DEN"],
        }
    if n == 13:
        a, b = (
            direct_quotes(initial, "SAC", "SJC", "2026-04-16", fare)[0]
            for fare in ["saver", "flexible"]
        )
        return {
            "route": a["route"],
            "saver_usd": a["price"],
            "flexible_usd": b["price"],
            "upgrade_usd": round(b["price"] - a["price"], 2),
        }
    if n == 14:
        return {
            "checked_baggage": baggage(initial, ["ANA", "SBA"]),
            "ordered_stops": stops(initial, "pacific-surfliner"),
            "cutoff_minutes": 45,
        }
    if n == 15:
        policy = one(
            initial,
            "SELECT summary FROM help_articles WHERE slug='checked-baggage-timing'",
        )["summary"]
        return {
            "cutoff_minutes": 45,
            "baggage_rule": policy,
            "train": "5",
            "departure_time": "14:00",
            "baggage_deadline": "13:15",
        }
    if n == 16:
        refund = one(
            initial, "SELECT * FROM help_articles WHERE slug='refunds-and-credits'"
        )
        saver = one(initial, "SELECT * FROM fare_classes WHERE slug='saver'")
        flexible = one(initial, "SELECT * FROM fare_classes WHERE slug='flexible'")
        return {
            "article_title": refund["title"],
            "category": refund["category"],
            "saver_usd": 57.11,
            "flexible_usd": 76.53,
            "upgrade_usd": 19.42,
            "saver_refund": saver["rules_refund"],
            "flexible_refund": flexible["rules_refund"],
        }
    if n == 17:
        old = {r["id"] for r in db_query(initial, "SELECT id FROM bookings")}
        new = [
            r for r in db_query(after, "SELECT * FROM bookings") if r["id"] not in old
        ]
        if len(new) != 1:
            raise ValueError("one new booking required")
        return {"booking_code": new[0]["booking_code"]}
    raise ValueError("unknown task")


def observed(trajectory, path, token=""):
    # Evidence comes from browser state, not action.thought/answer/params.
    for step in trajectory.get("steps", []):
        pairs = [
            (step.get("url_after", step.get("url", "")), step.get("observed_text_after", step.get("observed_text", ""))),
            (step.get("url", ""), step.get("observed_text_before", "")),
        ]
        for url, text in pairs:
            if (
                urlparse(url).path.rstrip("/") == path.rstrip("/")
                and text
                and token.casefold() in text.casefold()
            ):
                return True
    return False


def navigation(n, judge, tr, initial):
    def visit(path, token=""):
        check_visited_path(judge, tr, "visited_" + path, path)
        judge.check(
            "observed_" + path,
            observed(tr, path, token),
            f"page={path}, token={token!r}",
        )

    def search(o, d, date="2026-04-20", **params):
        check_results_visited(
            judge,
            tr,
            "searched_" + o + "_" + d + "_" + date,
            {"origin": o, "destination": d, "departure_date": date, **params},
        )
        requested = {"origin": o, "destination": d, "departure_date": date, **params}
        judge.check(
            "observed_requested_results",
            any(
                urlparse(url).path == "/booking/results"
                and text
                and all(
                    _param_matches(parse_qs(urlparse(url).query), key, value)
                    for key, value in requested.items()
                )
                for step in tr.get("steps", [])
                for url, text in [
                    (
                        step.get("url_after", step.get("url", "")),
                        step.get("observed_text_after", step.get("observed_text", "")),
                    ),
                    (step.get("url", ""), step.get("observed_text_before", "")),
                ]
            ),
        )

    def fare():
        visit("/booking/select-trip")
        visit("/booking/select-fare")

    def login(email):
        judge.check(
            "entered_account",
            email
            in [
                str(s.get("params", {}).get("text", "")).lower()
                for s in tr.get("steps", [])
                if s.get("action") == "input"
            ],
        )
        visit("/login")

    if n in (5, 8, 17):
        login("alice.j@test.com")
    if n == 0:
        search("NYP", "WAS", sort="duration", passengers="1", trip_type="one-way")
    if n == 1:
        search(
            "NYP",
            "WAS",
            sort="price",
            passengers="1",
            trip_type="one-way",
            direct_only=(None, "0", "false", "off"),
        )
    if n == 2:
        search(
            "WAS",
            "PHL",
            trip_type="round-trip",
            return_date="2026-04-22",
            sort="duration",
            passengers="1",
        )
        check_paths_in_order(
            judge,
            tr,
            "round_trip_funnel",
            [
                ("/booking/results", {"origin": "WAS", "destination": "PHL"}),
                ("/booking/results", {"leg": "return"}),
                ("/booking/select-trip", {}),
                ("/booking/select-fare", {}),
            ],
        )
        fare()
        for token in (
            "Washington → Philadelphia",
            "Philadelphia → Washington",
            "Apr 20, 2026",
            "Apr 22, 2026",
        ):
            visit("/booking/select-fare", token)
    if n == 3:
        visit("/booking/multi-city")
        fare()
        # The final selected-itinerary summary, not merely a visit to an empty
        # planner, must contain all three requested legs and actual departures.
        for token in (
            "Seattle → Portland",
            "Portland → Sacramento",
            "Sacramento → Los Angeles",
            "Apr 18, 2026",
            "Apr 20, 2026",
            "Apr 23, 2026",
        ):
            visit("/booking/select-fare", token)
    if n in (4, 10):
        search("SEA", "LAX", "2026-04-22", passengers="2")
        fare()
        visit("/booking/rooms")
    if n == 5:
        visit("/account/trips")
        visit("/trip/ALJDAM")
        search("CHI", "DEN", fare_class="flexible")
        fare()
    if n == 6:
        visit("/trip-lookup")
        visit("/trip/ALGX87")
        search("NYP", "WAS", sort="duration")
        fare()
    if n == 7:
        for email in ("alice.j@test.com", "bob.c@test.com"):
            login(email)
            visit("/account/rewards", reward_row(initial, email)["member_number"])
    if n == 8:
        check_paths_in_order(
            judge,
            tr,
            "profile_funnel",
            [("/login", {}), ("/account/edit", {}), ("/account/rewards", {})],
        )
        visit(
            "/account/rewards", reward_row(initial, "alice.j@test.com")["member_number"]
        )
    if n == 9:
        visit("/routes/amtrak-cascades")
        for code in stops(initial, "amtrak-cascades"):
            visit("/stations/" + code)
    if n == 10:
        visit("/service-alerts", "Coast Starlight")
    if n == 11:
        visit("/service-alerts", "Denver")
        visit("/stations/DEN")
        judge.check(
            "denver_schedule_date",
            any(
                urlparse(u).path == "/schedules"
                and parse_qs(urlparse(u).query).get("date") == ["2026-04-20"]
                and parse_qs(urlparse(u).query).get("station_code") == ["DEN"]
                for u in site_urls(tr)
            ),
        )
        visit("/schedules", "California Zephyr")
    if n == 12:
        search("CHI", "DEN", fare_class="flexible")
    if n == 13:
        for fare_class in ("saver", "flexible"):
            search("SAC", "SJC", "2026-04-16", fare_class=fare_class)
    if n == 14:
        visit("/stations/ANA")
        visit("/stations/SBA")
        visit("/routes/pacific-surfliner")
        visit("/help/checked-baggage-timing")
    if n == 15:
        visit("/help/checked-baggage-timing")
        search("CHI", "DEN")
    if n == 16:
        visit("/help/refunds-and-credits")
        judge.check(
            "refund_help_search",
            any(
                urlparse(u).path == "/help"
                and "refund"
                in " ".join(parse_qs(urlparse(u).query).get("q", [])).lower()
                for u in site_urls(tr)
            ),
        )
        search("NYP", "WAS", sort="duration")
        fare()
    if n == 17:
        search("NYP", "WAS", trip_type="one-way", passengers="1")
        check_paths_in_order(
            judge,
            tr,
            "checkout_funnel",
            [
                (p, {})
                for p in [
                    "/login",
                    "/booking/results",
                    "/booking/select-trip",
                    "/booking/select-fare",
                    "/booking/passengers",
                    "/booking/review",
                    "/booking/checkout",
                    "/booking/confirmation",
                ]
            ],
        )
        visit("/booking/confirmation")


def profile_state(judge, initial, after):
    for table, loader in [("users", user_row), ("reward_accounts", reward_row)]:
        before, final = loader(initial, "alice.j@test.com"), loader(
            after, "alice.j@test.com"
        )
        judge.check(
            "exact_" + table + "_preference",
            final == {**before, "preferred_station_code": "SEA"},
        )
        judge.check(
            "other_" + table + "_preserved",
            rows_unchanged_except(initial, after, table, [before["id"]]),
        )
    check_tables_unchanged(
        judge,
        initial,
        after,
        [
            t
            for t in MUTABLE_TABLES + LOG_TABLES
            if t not in ("users", "reward_accounts")
        ],
    )


def run_checks(n, judge, tr, initial, after):
    check_trajectory_identity(judge, tr, f"Amtrak--{n}")
    navigation(n, judge, tr, initial)
    if n == 17:
        check_checkout(judge, initial, after)
    elif n == 8:
        profile_state(judge, initial, after)
    else:
        check_read_only(judge, initial, after)
    try:
        expected = expected_answer(n, initial, after)
        response = final_answer(tr).strip()
        # Preserve older structured recordings without making that representation
        # a user-facing requirement. Natural answers use entity/property claims.
        if not response.startswith(("{", "```json")):
            for key, passed in natural_checks(n, response, expected).items():
                judge.check("answer_" + key, passed, "Natural-language claim: " + key)
            return
        actual = parse_answer(response)
        judge.check(
            "exact_answer_fields",
            actual.keys() == expected.keys(),
            f"required={list(expected)}",
        )
        for key, value in expected.items():
            judge.check(
                "answer_" + key,
                equivalent(actual.get(key), value),
                f"expected={value!r}, actual={actual.get(key)!r}",
            )
    except (ValueError, TypeError) as exc:
        judge.check("structured_answer", False, str(exc))


def main(n):
    task = f"Amtrak--{n}"
    args = parse_args()
    try:
        tr = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(task, "trajectory_unavailable", str(exc))
    initial, after = resolve_snapshots(args, task)
    judge = Judge(task)
    try:
        run_checks(n, judge, tr, initial, after)
    except Exception as exc:
        fail_closed(task, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()

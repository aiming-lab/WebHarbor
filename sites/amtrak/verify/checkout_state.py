"""Validate the entire new one-traveler Business booking against the seed."""

from datetime import datetime
from verify_lib import (
    db_query,
    table_delta,
    check_tables_unchanged,
    reward_row,
    user_row,
)


def records(path, table):
    return {r["id"]: dict(r) for r in db_query(path, f"SELECT * FROM {table}")}


def check_checkout(judge, initial, after):
    alice = user_row(initial, "alice.j@test.com")
    old_reward = reward_row(initial, alice["email"])
    new_reward = reward_row(after, alice["email"])
    added = {}
    for table in (
        "bookings",
        "booking_segments",
        "tickets",
        "passengers",
        "payment_mocks",
        "reward_activities",
    ):
        before, final = records(initial, table), records(after, table)
        fresh = [row for key, row in final.items() if key not in before]
        judge.check(
            f"{table}_one_new_preserve_existing",
            len(fresh) == 1
            and all(final.get(key) == row for key, row in before.items()),
            table,
        )
        if len(fresh) != 1:
            return None
        added[table] = fresh[0]
    booking, segment, ticket, passenger, payment, activity = (
        added[t]
        for t in (
            "bookings",
            "booking_segments",
            "tickets",
            "passengers",
            "payment_mocks",
            "reward_activities",
        )
    )
    bid = booking["id"]
    judge.check(
        "exact_booking_ownership",
        all(row["booking_id"] == bid for row in (segment, ticket, passenger, payment))
        and booking["user_id"] == passenger["user_id"] == alice["id"],
    )
    judge.check(
        "booking_identity",
        booking["trip_type"] == "one-way"
        and booking["status"] == "Confirmed"
        and booking["origin_code"] == "NYP"
        and booking["destination_code"] == "WAS"
        and booking["departure_date"] == "2026-04-20"
        and booking["return_date"] is None
        and booking["contact_email"] == alice["email"],
    )
    trip_rows = db_query(
        initial,
        "SELECT t.*,r.name AS route_name,tr.number AS train_number FROM trips t JOIN routes r ON r.id=t.route_id JOIN trains tr ON tr.id=t.train_id WHERE t.id=?",
        (segment["trip_id"],),
    )
    if not judge.check("known_trip", len(trip_rows) == 1):
        return booking
    trip = dict(trip_rows[0])
    all_segments = [
        dict(r)
        for r in db_query(
            initial,
            "SELECT * FROM trip_segments WHERE trip_id=? ORDER BY leg_order",
            (trip["id"],),
        )
    ]
    starts = [i for i, s in enumerate(all_segments) if s["from_station_code"] == "NYP"]
    ends = [i for i, s in enumerate(all_segments) if s["to_station_code"] == "WAS"]
    if not judge.check(
        "trip_serves_requested_leg", bool(starts and ends) and starts[0] <= ends[0]
    ):
        return booking
    parts = all_segments[starts[0] : ends[0] + 1]
    judge.check(
        "segment_matches_catalog",
        segment["route_name"] == trip["route_name"]
        and segment["train_number"] == trip["train_number"]
        and segment["origin_code"] == "NYP"
        and segment["destination_code"] == "WAS"
        and segment["leg_order"] == 0
        and segment["fare_class_name"] == "Business"
        and segment["accommodation_type"] == "Business Seat"
        and datetime.fromisoformat(segment["depart_dt"])
        == datetime.fromisoformat(parts[0]["depart_dt"])
        and datetime.fromisoformat(segment["arrive_dt"])
        == datetime.fromisoformat(parts[-1]["arrive_dt"])
        and parts[0]["depart_dt"].startswith("2026-04-20"),
    )
    fare = dict(
        db_query(
            initial,
            "SELECT fo.*,fc.points_multiplier FROM fare_options fo JOIN fare_classes fc ON fc.id=fo.fare_class_id WHERE fo.trip_id=? AND fc.slug='business'",
            (trip["id"],),
        )[0]
    )
    ratio = max(
        0.28,
        min(
            1.0,
            sum(s["duration_minutes"] for s in parts)
            / max(trip["duration_minutes"], 1),
        ),
    )
    judge.check("business_seat_available", fare["availability"] > 0)
    price = round(trip["base_fare"] * ratio * fare["multiplier"], 2)
    total = round(price + 12, 2)
    earned = round(price * fare["points_multiplier"])
    judge.check(
        "booking_price_matches_business_catalog",
        abs(booking["total_amount"] - total) < 0.005,
        f"expected_total={total}",
    )
    judge.check(
        "passenger_details",
        passenger["first_name"] == "Alice"
        and passenger["last_name"] == "Jordan"
        and passenger["passenger_type"] == "Adult"
        and passenger["age_band"] == "18+"
        and passenger["email"] == alice["email"]
        and passenger["phone"] == alice["phone"]
        and passenger["rewards_number"] == alice["rewards_member_no"]
        and not passenger["is_saved_profile"],
    )
    judge.check(
        "ticket_matches_passenger_trip_fare",
        ticket["passenger_id"] == passenger["id"]
        and ticket["trip_id"] == trip["id"]
        and ticket["fare_class_id"] == fare["fare_class_id"]
        and ticket["status"] == "Issued"
        and ticket["accommodation_type"] == "Business Seat"
        and ticket["qr_token"] == f"{booking['booking_code']}-1-1"
        and bool(ticket["seat_or_room"]),
    )
    judge.check(
        "payment_matches_derived_total",
        payment["status"] == "Approved"
        and abs(payment["amount"] - total) < 0.005
        and bool(payment["approval_code"]),
    )
    expected_reward = {
        **old_reward,
        "points_balance": old_reward["points_balance"] + earned,
        "points_ytd": old_reward["points_ytd"] + earned,
        "status_credits": old_reward["status_credits"] + max(1, total // 150),
    }
    judge.check("exact_reward_account_delta", new_reward == expected_reward)
    judge.check(
        "exact_reward_activity",
        activity["reward_account_id"] == old_reward["id"]
        and activity["booking_code"] == booking["booking_code"]
        and activity["category"] == "Travel"
        and activity["points_delta"] == booking["reward_points_earned"] == earned
        and activity["balance_after"] == expected_reward["points_balance"],
    )
    before, final = records(initial, "reward_accounts"), records(
        after, "reward_accounts"
    )
    judge.check(
        "all_other_reward_accounts_preserved",
        final == {**before, old_reward["id"]: expected_reward},
    )
    check_tables_unchanged(judge, initial, after, ["users", "search_logs"])
    return booking

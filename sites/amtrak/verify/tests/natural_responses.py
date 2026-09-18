"""One ordinary response style for UI replay; values come from rendered content.

This formatter is not used by the grader and is not a required answer template.
Tests independently exercise other sentences, bullets, tables and paraphrases.
"""


def response(n, a):
    def money(key):
        return f"${a[key]:,.2f}"

    def bags(values):
        return " ".join(
            f"{code} {'offers checked baggage' if available else 'is carry-on only'}."
            for code, available in values.items()
        )

    if n == 0:
        return f"The fastest direct service is {a['route']}, train {a['train']}. Total travel time is {a['total_minutes']//60} hours {a['total_minutes']%60} minutes."
    if n == 1:
        return f"The cheapest itinerary is {a['route']}, with a starting fare of {money('starting_fare_usd')}."
    if n == 2:
        return f"The combined round-trip Business fare is {money('business_per_traveler_usd')} per traveler."
    if n == 3:
        return f"The Value fare for the whole multi-city itinerary is {money('value_per_traveler_usd')} per traveler."
    if n == 4:
        return f"{a['room']} has the smallest extra cost: {money('extra_usd')} for the room."
    if n in (5, 6):
        identity = (
            f"Booking {a['booking_code']} departs from {a['origin']}"
            if n == 5
            else f"The route is {a['route']}"
        )
        fare = "Flexible" if n == 5 else "Business"
        key = "current_flexible_total_usd" if n == 5 else "current_business_total_usd"
        return f"{identity} on {a['departure_date']}. The recorded total is {money('recorded_total_usd')}; the current {fare} total including the service fee is {money(key)}; the increase is {money('increase_usd')}. I left the booking unchanged."
    if n == 7:
        return (
            " ".join(
                f"{name.title()}: balance {a[name]['balance']:,} points; points YTD {a[name]['ytd']:,}; status credits {a[name]['status_credits']}."
                for name in ["alice", "bob"]
            )
            + f" Alice has {a['alice_minus_bob_points']:,} more points than Bob."
        )
    if n == 8:
        return f"The saved preferred station shown on the Rewards dashboard is {a['preferred_station']}."
    if n == 9:
        return (
            "The stops in order are "
            + ", ".join(a["ordered_stops"])
            + ". "
            + bags(a["checked_baggage"])
        )
    if n == 10:
        return (
            a["next_step"]
            + f" {a['room']} has the lowest extra cost, {money('extra_usd')}."
        )
    if n == 11:
        return (
            f"The Denver advisory says track {a['advisory_track']}. Westbound California Zephyr train {a['westbound_train']} departs at {a['departure_time']} on that service-date board. "
            + bags({"DEN": a["checked_baggage"]})
        )
    if n == 12:
        return f"The route is {a['route']}; its Flexible fare is {money('flexible_fare_usd')}."
    if n == 13:
        return f"{a['route']}: Saver costs {money('saver_usd')}; Flexible costs {money('flexible_usd')}; the upgrade is {money('upgrade_usd')} per traveler."
    if n == 14:
        return (
            bags(a["checked_baggage"])
            + " The Pacific Surfliner stops in order are "
            + ", ".join(a["ordered_stops"])
            + f". The checked-baggage cutoff is {a['cutoff_minutes']} minutes before staffed long-distance departures."
        )
    if n == 15:
        return (
            a["baggage_rule"]
            + f" Train {a['train']} departs at {a['departure_time']}; the latest baggage check-in time is {a['baggage_deadline']}."
        )
    if n == 16:
        return f"The article is {a['article_title']} in {a['category']}. Saver costs {money('saver_usd')}: {a['saver_refund']} Flexible costs {money('flexible_usd')}: {a['flexible_refund']} The upgrade costs {money('upgrade_usd')} per traveler."
    if n == 17:
        return (
            f"The new booking is confirmed, with confirmation code {a['booking_code']}."
        )
    raise ValueError(n)

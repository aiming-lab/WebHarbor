#!/usr/bin/env python3
"""Append the reviewer's grading keys to sites/marriott/tasks.jsonl.

For each task row (contributor rows carry only web_name, id, ques, web,
upstream_url) this appends exactly two keys — verifier_path and judge_rubric —
by inserting them before the closing brace of the original line, so the original
five keys' bytes are untouched. Ground truth never lands in tasks.jsonl: it lives
only inside sites/marriott/verify/verify_<N>.py.

Idempotent: re-running on an already-appended file is a no-op.
"""
from __future__ import annotations

import json
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
TASKS = SITE / "tasks.jsonl"
VERIFY = "sites/marriott/verify/verify_{n}.py"

RUBRICS = {
    0: ("FACT CHECKPOINTS: The agent must have searched San Francisco hotels for the "
        "11/06/2026-11/08/2026 stay window and opened the booked hotel's rooms/availability "
        "page before booking. The booked property must be a San Francisco hotel rated 4.0 or "
        "higher, the cheapest such hotel, reserved in its cheapest available room type for "
        "guest Jordan Ellis. The final answer must report the confirmation number and the "
        "total exactly as shown on the reservation confirmation page. An answer without a "
        "confirmation number and total is a FAIL."),
    1: ("FACT CHECKPOINTS: The agent must have signed in as alice.j@test.com, run a "
        "points-rate hotel search for Chicago covering 10/30/2026-10/31/2026, and booked the "
        "property with the lowest nightly points rate in its cheapest room type. The final "
        "answer must report the confirmation number, the points redeemed, and the remaining "
        "points balance as shown on the account page. An answer missing any of the three "
        "facts is a FAIL."),
    2: ("FACT CHECKPOINTS: The agent must have searched Denver hotels for the "
        "12/01/2026-12/04/2026 stay, picked a hotel whose amenity listing includes a Fitness "
        "Center, and booked the cheapest such hotel in its cheapest room type for guest "
        "Priya Nair. The final answer must name the booked hotel and report its confirmation "
        "number. An answer without the hotel name and confirmation number is a FAIL."),
    3: ("FACT CHECKPOINTS: The agent must have searched New York City hotels for the "
        "10/20/2026-10/22/2026 stay, opened the rooms pages of BOTH cheapest hotels rated 4.0 "
        "or higher, and reserved the option with the lower two-night total for guest Sam "
        "Carter. The final answer must state which hotel was booked and the total shown on "
        "the confirmation page. An answer that names neither the booked hotel nor the total "
        "is a FAIL."),
    4: ("FACT CHECKPOINTS: The agent must have searched Orlando hotels for the "
        "12/18/2026-12/21/2026 stay, identified the cheapest Orlando hotel by nightly rate, "
        "and booked its cheapest room type that sleeps at least four guests for guest Dana "
        "Brooks. The final answer must report the room type name, the total, and the "
        "confirmation number from the confirmation page. An answer missing any of the three "
        "is a FAIL."),
    5: ("FACT CHECKPOINTS: The agent must have signed in as alice.j@test.com, opened the "
        "reservation ACCEDGHDDR's hotel page from the trips view, used Find My Reservation "
        "with the confirmation number and last name, and canceled the reservation. The final "
        "answer must report the hotel's listed check-in time, the reservation's hotel, room "
        "type, check-in date and total from the lookup, and the status shown after "
        "canceling. An answer that does not show the canceled status is a FAIL."),
    6: ("FACT CHECKPOINTS: The agent must have signed in as david.k@test.com, identified the "
        "UPCOMING reservation with the earliest check-in date (past stays do not count), "
        "canceled it through Find My Reservation, and looked it up again. The final answer "
        "must report the cancellation message, the remaining confirmed upcoming trip's hotel, "
        "check-in date and total, and the Bonvoy member tier. An answer that cancels or "
        "reports a past stay, or misses the member tier, is a FAIL."),
    7: ("FACT CHECKPOINTS: The agent must have signed in as bob.c@test.com, opened the "
        "upcoming trip's hotel page and its reviews page, and then booked the same hotel's "
        "cheapest room type for 10/18/2026-10/20/2026 under guest Bob Chen. The final answer "
        "must report the trip's check-in date, room type and total; the hotel's exact street "
        "address, the phone number in the header, and whether its amenity list includes a "
        "fitness center; the reviews page average rating and the title of the most recent "
        "review; and the new booking's confirmation number and total. Missing facts are a "
        "FAIL."),
    8: ("FACT CHECKPOINTS: The agent must have signed in as bob.c@test.com, updated the "
        "profile with phone +1 415-555-0123, street 1200 Broadway, city Oakland, state "
        "California, then signed out and signed back in to confirm persistence. The final "
        "answer must quote the exact success message the site showed right after saving. An "
        "answer without the exact message is a FAIL."),
    9: ("FACT CHECKPOINTS: The agent must have signed in as carol.d@test.com, added the Visa "
        "card 4242424242424444 (cardholder Carol Davis, expiring 09/2029), removed the old "
        "Amex card, and updated the profile phone to +1 312-555-0188. The final answer must "
        "report how many cards remain, the last four digits of each remaining card, and the "
        "exact profile success message. An answer missing the card count, the last-four "
        "digits, or the message is a FAIL."),
    10: ("FACT CHECKPOINTS: The agent must have signed in as alice.j@test.com, removed the "
         "Austin property from the saved hotels list, saved The Times Square EDITION from a "
         "New York City search, and signed out and back in. The final answer must list the "
         "final saved hotel names in the order shown on the saved hotels page. An answer "
         "missing any saved hotel or in a different order is a FAIL."),
    11: ("FACT CHECKPOINTS: The agent must have created a new Marriott Bonvoy account for "
         "Fiona Gray with email fiona.gray@example.com (password of at least 8 characters), "
         "then searched Seattle hotels, opened the cheapest one and saved it. The final "
         "answer must report the member tier and starting points balance the account page "
         "shows, and the exact name of the cheapest Seattle hotel. An answer missing the "
         "tier, the balance, or the hotel name is a FAIL."),
    12: ("FACT CHECKPOINTS: The agent must have searched Las Vegas hotels for the "
         "11/13/2026-11/15/2026 stay with the under-$300 and rated-4.0-or-higher "
         "constraints, opened the rooms pages of BOTH cheapest matches, and compared their "
         "cheapest room types. The final answer must report how many hotels match, their "
         "names in price order, each of the two cheapest matches' nightly rate, Bonvoy "
         "points rate and two-night total, and which of the two works out cheaper (an honest "
         "tie must be reported as such). An answer missing the count, the ordered names, or "
         "the room-level comparison is a FAIL."),
    13: ("FACT CHECKPOINTS: The agent must have run a points-rate hotel search for Miami "
         "covering 11/20/2026-11/21/2026, opened the rooms pages of the two properties with "
         "the lowest nightly points rates, and checked their reviews pages. The final answer "
         "must report each property's exact points rate and the nightly cash rate of its "
         "cheapest room type, and which of the two shows the higher average rating on its "
         "reviews page. An answer missing either property's rates or the rating comparison "
         "is a FAIL."),
    14: ("FACT CHECKPOINTS: The agent must have opened the Boston destination page, "
         "identified how many Marriott Bonvoy hotels it lists, picked the cheapest per "
         "night, checked that hotel's reviews page, and booked its cheapest room type for "
         "guest Alex Foley with the given Amex card for 11/13/2026-11/15/2026. The final "
         "answer must report the hotel count, the chosen hotel, its average rating and total "
         "review count, and the booking total and confirmation number. Missing facts are a "
         "FAIL."),
    15: ("FACT CHECKPOINTS: The agent must have searched Chicago hotels for the "
         "11/06/2026-11/08/2026 window and checked the amenity sections of the candidate "
         "properties. The final answer must report EVERY hotel that offers both a pool and a "
         "spa, plus each one's nightly rate and brand. An answer that misses a qualifying "
         "hotel, or reports one without its rate and brand, is a FAIL."),
    16: ("FACT CHECKPOINTS: The agent must have opened the rooms page of The Westin New "
         "York Grand Central, identified its largest room type by size, and booked that "
         "room type for 11/13/2026-11/15/2026 for guest Robin Stone with the given Visa "
         "card. The final answer must report the largest room type's name, square footage, "
         "bed setup and nightly rate, how many room types the hotel lists in total, and the "
         "booking total and confirmation number. Missing facts are a FAIL."),
    17: ("FACT CHECKPOINTS: The agent must have visited the reviews pages of BOTH The "
         "Lexington Hotel, Autograph Collection and The Westin New York Grand Central. The "
         "final answer must report each hotel's average rating, total review count and "
         "1-star review count, which hotel has the lower share of 1-star reviews, and — "
         "after signing in as alice.j@test.com and saving that hotel — the confirmation "
         "message shown. An answer missing either hotel's three review numbers or the save "
         "message is a FAIL."),
    18: ("FACT CHECKPOINTS: The agent must have signed in as david.k@test.com, opened the "
         "rooms pages of BOTH The Westin New York Grand Central and Residence Inn by "
         "Marriott New York Manhattan/Times Square, compared their most expensive room "
         "types, and redeemed points for one night 10/30/2026-10/31/2026 in the cheaper top "
         "room. The final answer must report which hotel's top room costs more per night "
         "and by how many dollars, the bed setup and square footage of the cheaper top "
         "room, and the redemption confirmation number and remaining points balance. Missing "
         "facts are a FAIL."),
    19: ("FACT CHECKPOINTS: The agent must have opened the Special Offers page and run "
         "Courtyard-brand-filtered hotel searches for Chicago and Orlando covering "
         "12/05/2026-12/06/2026. The final answer must report the title of the offer whose "
         "book-by date is 12/20/2026 and the bonus points amount its blurb mentions, how "
         "many Courtyard properties appear in Chicago and the nightly rate of the cheapest "
         "one, and how many Courtyard hotels appear in Orlando. Missing facts are a FAIL."),
    20: ("FACT CHECKPOINTS: The agent must have opened the Our Brands page and run a "
         "Residence Inn-brand-filtered New York City search for 12/05/2026-12/07/2026, then "
         "visited EVERY returned property's overview page and rooms page. The final answer "
         "must report how many brands belong to the longer stays category and their names, "
         "each property's listed check-in time and average rating, each property's cheapest "
         "room type nightly rate and Bonvoy points rate, and which property is cheaper per "
         "night. Missing facts are a FAIL."),
}


def main() -> None:
    lines = TASKS.read_text(encoding="utf-8").splitlines(keepends=True)
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        row = json.loads(stripped)
        if "verifier_path" in row and "judge_rubric" in row:
            out.append(line)  # already appended (idempotent)
            continue
        assert set(row) == {"web_name", "id", "ques", "web", "upstream_url"}, row.keys()
        n = int(row["id"].rsplit("--", 1)[1])
        assert row["web"] == "http://localhost:40104/", row["web"]
        addition = (f', "verifier_path": "{VERIFY.format(n=n)}", '
                    f'"judge_rubric": {json.dumps(RUBRICS[n], ensure_ascii=False)}}}')
        assert stripped.endswith("}")
        out.append(stripped[:-1] + addition + "\n")
    TASKS.write_text("".join(out), encoding="utf-8")
    # verify: original key bytes untouched + new keys present
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        assert set(row) == {"web_name", "id", "ques", "web", "upstream_url",
                            "verifier_path", "judge_rubric"}, row.keys()
        assert line.startswith(line[:line.index(", \"verifier_path\"")]), "prefix changed"
    print(f"appended verifier_path + judge_rubric to {len(lines)} task rows")


if __name__ == "__main__":
    main()

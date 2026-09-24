#!/usr/bin/env python3
"""Append the reviewer grading keys (verifier_path + judge_rubric) to tasks.jsonl.

The five contributor keys (web_name, id, ques, web, upstream_url) stay byte-identical:
the two new keys are string-inserted before each line's closing brace, so the original
JSON bytes are untouched and no answer key is ever written into the file.

Usage: python3 append_rubrics.py   (idempotent: skips lines that already carry the keys)
"""
from __future__ import annotations

import json
from pathlib import Path

TASKS = Path(__file__).resolve().parents[1] / "tasks.jsonl"

RUBRICS = {
    0: "FACT CHECKPOINTS: (1) The trajectory MUST search the journey planner for "
       "Baltimore to New York on 2026-10-03 for two travelers and open the results "
       "page, then add the cheapest MORNING departure to the basket. (2) The "
       "trajectory MUST open the fare finder page to discover the advertised "
       "redemption code and apply it in the basket. (3) The trajectory MUST complete "
       "the guest checkout (basket, passenger details, payment, confirmation) with "
       "the email cousins.trip@example.com. (4) The answer MUST report the order "
       "reference shown on the confirmation page and the total charged including the "
       "promotion discount and booking fee. (5) Empty answer = FAIL. Reject a total "
       "that omits the promotion or the booking fee, or a reference not matching the "
       "created booking.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST open the journey results for New "
       "York to Washington on 2026-10-02 AND for Washington to New York on "
       "2026-10-04. (2) The answer MUST report the cheapest fare on each leg, the "
       "combined total including the $3.99 booking fee, and the travel time of the "
       "outbound departure the agent would take. (3) The trajectory MUST NOT reach "
       "passenger details or payment (the task says do not complete checkout). "
       "(4) Empty answer = FAIL. Reject a combined total that omits the booking fee.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST register the account (Jordan "
       "Reyes, jordan.reyes@example.com) on the register page. (2) The trajectory "
       "MUST search Boston to New York on 2026-10-03, add the cheapest departure, and "
       "complete the signed-in checkout through to the confirmation page. (3) The "
       "answer MUST report the order reference shown on the confirmation page. "
       "(4) Empty answer = FAIL. Reject a booking of any departure other than the "
       "cheapest one, or a reference not matching the created booking.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as bob.c@test.com and open "
       "the Change trip page for booking M2V6YH. (2) The trajectory MUST use the "
       "change date/time flow and select the afternoon departure on 2026-10-10 before "
       "confirming. (3) The answer MUST report the new departure time, the amendment "
       "fee and the fare difference charged. (4) Empty answer = FAIL. Reject an "
       "amendment fee or fare difference inconsistent with the site's posted fees.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as carol.d@test.com. "
       "(2) The trajectory MUST open the confirmed New York to Toronto booking "
       "(W9C4FJ) under Change trip and cancel it. (3) The answer MUST quote the exact "
       "confirmation message the site shows, including what happens to the money. "
       "(4) Empty answer = FAIL. Reject cancelling the already-cancelled Toronto "
       "booking instead of the confirmed one.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST look up booking H3P8KS with the "
       "email david.k@test.com under Change trip. (2) The answer MUST report the "
       "route, the travel date, the number of travelers and the total paid. (3) The "
       "trajectory MUST open the departure schedule for the same route and date and "
       "the answer MUST state whether the booked departure leaves earlier or later "
       "than the 12:10pm service that day. (4) Empty answer = FAIL. Reject an answer "
       "that does not compare against the 12:10pm service.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST use the fare finder with origin "
       "Philadelphia. (2) The answer MUST list the three cheapest destinations with "
       "their starting fares, name which of the three is the fastest to reach, and "
       "state that trip's travel time. (3) Empty answer = FAIL. Reject destinations "
       "or fares not shown on the fare finder results for Philadelphia.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST open the Boston to New York route "
       "guide page. (2) The answer MUST report the fastest travel time, how many "
       "services run per day, and the named boarding location in Boston and drop-off "
       "location in New York as stated on that guide. (3) Empty answer = FAIL. "
       "Reject values taken from any other route guide or from the journey results "
       "page.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST open the help/FAQ pages covering "
       "luggage (the traveling-on-the-bus topic). (2) The answer MUST quote the "
       "luggage allowance for a general seating ticket and state the exact condition "
       "under which megabus carries bicycles, including the size and weight limits. "
       "(3) Empty answer = FAIL. Reject limits taken from anywhere other than the "
       "help FAQs.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST open the bus stops page and the "
       "Albany, NY stops page. (2) The answer MUST name the company operating the "
       "most Albany stops, how many Albany stops it serves, and each of that "
       "company's stop locations as shown. (3) Empty answer = FAIL. Reject counts or "
       "stop names not listed under Albany on the site.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST open the Toronto city guide and "
        "list the top five things to do it recommends. (2) The trajectory MUST open "
        "the 2026-10-04 New York to Toronto journey results; the answer MUST report "
        "the cheapest fare and how many departures offer it that day. (3) Empty "
        "answer = FAIL. Reject a top-five list or fare count not taken from those "
        "pages.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST open the 2026-10-03 journey "
        "results for BOTH New York to Washington and Philadelphia to Washington. "
        "(2) The answer MUST state which city has the earlier first departure after "
        "6:00am, the per-traveler cost of that ticket, and that journey's travel "
        "time. (3) Empty answer = FAIL. Reject a comparison that reads only one "
        "route's results.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST open the 2026-10-03 New York to "
        "Boston journey results. (2) The answer MUST report how many services run "
        "across the whole day, how many involve a connection, the cheapest fare "
        "shown, and the departure times of the two morning departures that require a "
        "connection. (3) Empty answer = FAIL. Reject counts that include only direct "
        "services or only connections.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST open the 2026-10-03 New York to "
        "Boston journey results. (2) The answer MUST identify the 9:00am one-stop "
        "journey, name the city it connects through, report its total travel time, "
        "and compare its fare with the 9:15am direct service on the same page. "
        "(3) Empty answer = FAIL. Reject a connection city or travel time not "
        "matching the 9:00am one-stop service.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST use the bus tracker for New York "
        "to Philadelphia on 2026-10-03. (2) The answer MUST identify which departure "
        "is delayed, by how many minutes, and the revised arrival time in "
        "Philadelphia. (3) Empty answer = FAIL. Reject delay values not shown by the "
        "tracker for that route and date.",
    15: "FACT CHECKPOINTS: (1) The trajectory MUST open the service alerts page and "
        "read the alert affecting Philadelphia departures. (2) The trajectory MUST "
        "look up booking AEG7CWY (alice.j@test.com) under Change trip. (3) The answer "
        "MUST report where and when Alice's Philadelphia trip departs and explain, "
        "using the alert's dates, whether the trip is affected. (4) Empty answer = "
        "FAIL. Reject an affected/not-affected verdict that ignores the alert's date "
        "window.",
    16: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as alice.j@test.com and "
        "open the account area. (2) The answer MUST list her upcoming trips with "
        "routes, dates, departure times and totals, report the per-traveler fare for "
        "the two-traveler trip, and state which booking has the larger total. "
        "(3) Empty answer = FAIL. Reject trip data not shown in the account area.",
    17: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as carol.d@test.com and "
        "open the account profile page. (2) The trajectory MUST update the last name "
        "to Davies and add the mobile number 555-202-7788. (3) The answer MUST report "
        "exactly how the name and phone number now appear on the account page. "
        "(4) Empty answer = FAIL. Reject an answer that does not reflect the updated "
        "account values.",
    18: "FACT CHECKPOINTS: (1) The trajectory MUST add the cheapest 2026-10-03 New "
        "York to Philadelphia trip to the basket and try the code SAVE20. (2) The "
        "trajectory MUST find the promotion megabus actually advertises (fare finder) "
        "and apply it in the basket instead. (3) The answer MUST report the final "
        "total shown in the basket before paying. (4) Empty answer = FAIL. Reject a "
        "total computed with SAVE20 or without the advertised code's discount.",
    19: "FACT CHECKPOINTS: (1) The trajectory MUST search Toronto to Montreal on "
        "2026-10-03, add the cheapest departure, enable text message travel updates "
        "in the basket, and complete the guest checkout with the email "
        "yuki.tanaka@example.com through to the confirmation page. (2) The answer "
        "MUST report the order reference and the total charged broken down by fare, "
        "booking fee and SMS fee. (3) Empty answer = FAIL. Reject a breakdown that "
        "omits the SMS fee or the booking fee, or a reference not matching the "
        "created booking.",
    20: "FACT CHECKPOINTS: (1) The trajectory MUST open the help pages that answer "
        "boarding questions (the driver/boarding FAQs). (2) The answer MUST state "
        "what a passenger shows the driver when boarding and how early megabus asks "
        "passengers to be at the stop, citing where each answer comes from on the "
        "site. (3) Empty answer = FAIL. Reject boarding rules not taken from the "
        "site's help FAQs.",
}


def main() -> None:
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    out = []
    changed = 0
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        index = int(row["id"].split("--")[1])
        if "verifier_path" in row and "judge_rubric" in row:
            out.append(line)
            continue
        assert sorted(row.keys()) == ["id", "ques", "upstream_url", "web", "web_name"], \
            f"unexpected contributor keys on {row['id']}: {sorted(row.keys())}"
        verifier = f"sites/megabus/verify/verify_{index}.py"
        rubric = RUBRICS[index]
        # insert the two keys before the closing brace, preserving the original bytes
        assert line.rstrip().endswith("}")
        body = line.rstrip()[:-1].rstrip()  # drop the closing brace
        assert body.endswith('"')           # ... and ends inside the last string value
        new_line = (body
                    + f', "verifier_path": {json.dumps(verifier)}'
                    + f', "judge_rubric": {json.dumps(rubric)}'
                    + '}')
        # sanity: parses and keeps the original five keys byte-identical in value
        parsed = json.loads(new_line)
        assert parsed["verifier_path"] == verifier
        assert parsed["judge_rubric"] == rubric
        for key in ("web_name", "id", "ques", "web", "upstream_url"):
            assert parsed[key] == row[key], key
        assert "answer" not in parsed
        out.append(new_line)
        changed += 1
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended grading keys to {changed} rows (total {len(out)})")


if __name__ == "__main__":
    main()

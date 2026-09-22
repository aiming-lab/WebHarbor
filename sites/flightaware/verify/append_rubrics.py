#!/usr/bin/env python3
"""Append verifier_path + judge_rubric to sites/flightaware/tasks.jsonl.

The original 5-key rows (web_name, id, ques, web, upstream_url) are preserved
byte-identically: each line is re-serialized from its parsed dict and compared
against the original line before appending the two reviewer keys. No answer
key ever lands in tasks.jsonl.
"""
import json
from pathlib import Path

TASKS = Path(__file__).resolve().parents[2] / "flightaware" / "tasks.jsonl"

RUBRICS = {
    0: "FACT CHECKPOINTS: the agent MUST open the UAL1063 flight detail page; the answer MUST report the departure gate, the scheduled departure time, the actual gate departure time, and the aircraft type exactly as shown on that page (scheduled and actual must both appear). An empty answer is a FAIL.",
    1: "FACT CHECKPOINTS: the agent MUST log in with the demo account and open the Boston Logan (KBOS) departures board; the answer MUST report the flight number, aircraft type, destination, and departure time of the FIRST departure listed on that board. An empty answer is a FAIL.",
    2: "FACT CHECKPOINTS: the agent MUST open the UAL1063 flight history page; the answer MUST report the duration of the September 20, 2026 flight and the aircraft type that operated it, as listed in the history table. An empty answer is a FAIL.",
    3: "FACT CHECKPOINTS: the agent MUST open the worldwide airport delays page; the answer MUST name the airport whose row reports departure delays averaging 50 minutes that are decreasing AND arrival delays that are increasing, including the code in parentheses. An empty answer is a FAIL.",
    4: "FACT CHECKPOINTS: the agent MUST open the flight delay and cancellation statistics page; the answer MUST name the airline with the most cancelled flights today plus the cancelled-flight count and the percentage shown in the BY AIRLINE table. An empty answer is a FAIL.",
    5: "FACT CHECKPOINTS: the agent MUST open the aviation photos section (the votes ranking or the top photo's own page); the answer MUST report the title, the photographer, and the vote count of the photo with the highest votes on the site. An empty answer is a FAIL.",
    6: "FACT CHECKPOINTS: the agent MUST open the squawks list ordered by most comments; the answer MUST report the title, the number of member comments, and the submitter of the squawk with the most comments. An empty answer is a FAIL.",
    7: "FACT CHECKPOINTS: the agent MUST log in as the demo account bob.c@test.com, open the account page, create a flight alert for BAW117 with basic notifications, and report how many alerts the account has in total afterwards and which alert was just created. An empty answer is a FAIL.",
    8: "FACT CHECKPOINTS: the agent MUST log in as the demo account bob.c@test.com, open the account page, delete the alert for flight AAL954, and report which alerts remain on the account afterwards. An empty answer is a FAIL.",
    9: "FACT CHECKPOINTS: the agent MUST open the EVA17 flight detail page; the answer MUST report the departure gate, the arrival terminal, the current speed in mph, the planned speed, and the aircraft type, all from that page. An empty answer is a FAIL.",
    10: "FACT CHECKPOINTS: the agent MUST use the Flight Finder searching departure Newark and arrival Mexico City; the answer MUST report how many flights match and their flight numbers as shown in the results table. An empty answer is a FAIL.",
    11: "FACT CHECKPOINTS: the agent MUST browse by operator to the Delta Air Lines (DAL) page and the JetBlue (JBU) page; the answer MUST report each operator's tracked-flights-today count as shown on those pages. An empty answer is a FAIL.",
    12: "FACT CHECKPOINTS: the agent MUST open the JFK airport weather page; the answer MUST report the current conditions text (including any wind note) and the temperature in Fahrenheit exactly as displayed. An empty answer is a FAIL.",
    13: "FACT CHECKPOINTS: the agent MUST open the JFK airport remarks page; the answer MUST report the remark code A110-2 and its warning text as listed. An empty answer is a FAIL.",
    14: "FACT CHECKPOINTS: the agent MUST log in with the demo account and open the JFK arrivals board; the answer MUST report the flight number and aircraft type of the flight arriving from Buenos Aires (Ministro Pistarini Int'l). An empty answer is a FAIL.",
    15: "FACT CHECKPOINTS: the agent MUST open BOTH the AAL169 and AAL170 flight detail pages; the answer MUST state which flight departs from Los Angeles, which arrives at Los Angeles, and each flight's aircraft type. An empty answer is a FAIL.",
    16: "FACT CHECKPOINTS: the agent MUST open the squawks list; the answer MUST report the title of the squawk about a possible meteorite striking a United 737, the source domain shown in parentheses, and its member-comment count. An empty answer is a FAIL.",
    17: "FACT CHECKPOINTS: the agent MUST open the MiseryMap page; the answer MUST report the total number of delays within, into, or out of the United States today and identify the airport (with code) whose arrival delays are increasing. An empty answer is a FAIL.",
    18: "FACT CHECKPOINTS: the agent MUST run the site search for 'Singapore Changi' and for 'Changi'; the answer MUST report the matching airport code and how many photos appear in the 'Changi' search results. An empty answer is a FAIL.",
    19: "FACT CHECKPOINTS: the agent MUST open the photo titled 'FDX McDonnell Douglas DC-10 (N368FE)'; the answer MUST report the registration, the vote count, the vote average, and the view count shown for that photo. An empty answer is a FAIL.",
    20: "FACT CHECKPOINTS: the agent MUST open the flight delay and cancellation statistics page; the answer MUST report the total cancellations today worldwide and the total cancellations within, into, or out of the United States. An empty answer is a FAIL.",
    21: "FACT CHECKPOINTS: the agent MUST open the squawks list; the answer MUST report the title of the squawk submitted by Amanda Skogstad and the source domain shown in parentheses. An empty answer is a FAIL.",
    22: "FACT CHECKPOINTS: the agent MUST log in as the demo account david.k@test.com and open the JFK en-route board; the answer MUST report the airline, the flight number, the aircraft type, and the expected arrival time of the flight from Dubai. An empty answer is a FAIL.",
    23: "FACT CHECKPOINTS: the agent MUST log in as the demo account carol.d@test.com, open the account page, report how many alerts it currently has, add a new route alert from JFK to London Heathrow with full notifications, and report what the new alert line shows. An empty answer is a FAIL.",
    24: "FACT CHECKPOINTS: the agent MUST log in with a demo account and open the London Heathrow (EGLL) departures board; the answer MUST report the flight number, aircraft type, destination, and departure time of the first departure listed. An empty answer is a FAIL.",
    25: "FACT CHECKPOINTS: the agent MUST browse by aircraft type to the Boeing 787-9 Dreamliner (B789) page; the answer MUST report how many flights of that type are tracked today and the flight number of the one departing JFK for London Heathrow. An empty answer is a FAIL.",
    26: "FACT CHECKPOINTS: the agent MUST find the highest-voted photo of a United Boeing 787-9 in the aviation photos section and open its page; the answer MUST report its title, the registration shown in the title, the photographer, and the vote count. An empty answer is a FAIL.",
    27: "FACT CHECKPOINTS: the agent MUST open the UAL1063 flight detail page; the answer MUST report the first four waypoints of the filed route in order. An empty answer is a FAIL.",
    28: "FACT CHECKPOINTS: the agent MUST open the UAL1063 flight history page; the answer MUST report how many of the past flights listed were operated by the Boeing 737 MAX 8 and the most recent past flight date shown. An empty answer is a FAIL.",
    29: "FACT CHECKPOINTS: the agent MUST search the squawks for 'meteorite' and for 'UPS'; the answer MUST report the title and vote count of the meteorite result and the title of the UPS result about pilots mourning colleagues. An empty answer is a FAIL.",
}


def main():
    lines = TASKS.read_text().splitlines()
    out_lines = []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        n = int(row["id"].rsplit("--", 1)[1])
        # byte-identity gate: the parsed original row must round-trip exactly
        assert json.dumps(row) == line, f"original row does not round-trip: {row['id']}"
        assert set(row) == {"web_name", "id", "ques", "web", "upstream_url"}, row["id"]
        assert "answer" not in row
        row["verifier_path"] = f"sites/flightaware/verify/verify_{n}.py"
        row["judge_rubric"] = RUBRICS[n]
        out_lines.append(json.dumps(row))
    TASKS.write_text("\n".join(out_lines) + "\n")
    print(f"appended verifier_path + judge_rubric to {len(out_lines)} rows")


if __name__ == "__main__":
    main()

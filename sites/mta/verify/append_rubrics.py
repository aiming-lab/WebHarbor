#!/usr/bin/env python3
"""append_rubrics.py — reviewer-side grading-key insertion for sites/mta.

Appends `verifier_path` + `judge_rubric` to every row of tasks.jsonl using a
BYTE-PRESERVING string insertion: each original line (the contributor's five
keys web_name,id,ques,web,upstream_url, byte-for-byte untouched) keeps its
exact bytes; the two grading keys are spliced in immediately before the
closing brace. No `answer` key ever lands in the agent-facing file.

Usage: python3 sites/mta/verify/append_rubrics.py [--check]
  --check   verify tasks.jsonl already carries the contract; exit 1 if not
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
TASKS = SITE / "tasks.jsonl"

RUBRICS = {
0: "FACT CHECKPOINTS: (1) The agent must open the Long Beach Branch weekday timetable toward Manhattan and identify the latest train boarding at Valley Stream that arrives Penn Station by 9:15 a.m. (departure time, arrival time, ride duration in minutes). (2) The agent must use the railroad fare finder with from=Valley Stream, to=Penn Station, ticket=One-Way Peak and report that one-way peak fare in dollars. (3) The agent must check the LIRR planned service changes for this weekend and state whether any affect the Long Beach Branch (including the correct alternative if one does). An empty or vague answer that omits the departure/arrival times, the fare, or the weekend verdict is a FAIL.",
1: "FACT CHECKPOINTS: (1) The agent must open the Ronkonkoma Branch weekday timetable and report the last train boarding at Penn Station toward Ronkonkoma (departure and arrival times). (2) The agent must report the first morning train from NYC the next weekday (departure time). (3) The agent must use the fare finder with from=Ronkonkoma, to=Penn Station, ticket=One-Way Off-Peak and report the one-way off-peak fare. Missing any of the three times or the fare is a FAIL.",
2: "FACT CHECKPOINTS: (1) The agent must state whether 14 St-Union Sq is listed as accessible and for which lines/platforms (accessibility note). (2) The agent must open the elevator & escalator status search for the station and report the equipment currently out of service, its type, the reason, and the estimated return date/time. (3) The agent must state what alternative the MTA suggests while it is out (including honestly reporting when none is listed). (4) The agent must also check the station's upcoming elevator or escalator maintenance over the next few days (the status page's upcoming-outages view) and report the scheduled equipment IDs (EL218 to the L platform and EL220 to the downtown N/Q/R/W platform) with their maintenance window and replacement alternatives. Omitting the outage equipment ID/type, the reason, the ETA, the accessibility verdict, or the upcoming maintenance is a FAIL.",
3: "FACT CHECKPOINTS: (1) The agent must open the elevator & escalator status search for 149 St-Grand Concourse and report the Woodlawn-bound 4 platform elevator's current status, reason, and estimated return to service. (2) The agent must report what the MTA's accessibility pages say about filing an ADA-related complaint (online feedback form, 511, or the MTA apps) and what happens after a case is logged (a case ticket number is issued and the case is tracked). (3) The agent must file the feedback report about the elevator through the customer feedback form (elevator/escalator outage category) with the requester's name and email as given. (4) The agent must report the NEW case reference number issued for the report (CS-…). Filing nothing, omitting the ADA procedure or the after-logging step, or not reporting the new case number is a FAIL.",
4: "FACT CHECKPOINTS: (1) The claim must be filed with the Subway, Bus and Staten Island Railway lost and found (the correct agency for a 7 train item) using the provided name, email and phone. (2) The agent must report the new claim reference number (LF-…). (3) The agent must report what the claim status page says to keep handy while the search proceeds. Filing with the wrong agency, or not reporting the reference number and the keep-handy guidance, is a FAIL.",
5: "FACT CHECKPOINTS: (1) The agent must look up all three reference numbers LF-26094217, LF-26095803 and LF-26096625 on the claim status pages. (2) The agent must report each claim's status and the item each covers. (3) For the claim matched with the property office (LF-26096625), the agent must name the lost-and-found facility holding it (Metro-North's Lost and Found Facility) and report the keep-handy guidance. (4) The agent must report what the subway lost-and-found page says happens after you file a claim (the MTA searches for the item and issues a claim reference to track the report). Mixing up the claims, omitting any status/item, the facility, the keep-handy guidance, or the after-filing step is a FAIL.",
6: "FACT CHECKPOINTS: (1) The agent must log in with the given demo account and open the OMNY page, and report the local vs express ride counts for the week, the amount spent toward each weekly cap, and the room left before the subway-and-local-bus cap. (2) The agent must cross-check the tap-and-ride page for the weekly cap amounts and when a new cap period starts (the first tap starts a new seven-day cap). (3) The agent must check the current service status of the favorite lines (A, E and 7) and summarize the active alerts. (4) The agent must answer, from the cap rules, whether two more subway rides on Sunday would cost anything extra. Omitting the counts, either cap amount, the cap-period rule, the line statuses, or the Sunday verdict is a FAIL.",
7: "FACT CHECKPOINTS: (1) The agent must log in as the given demo account and update favorites so the 2 and 5 trains are removed and the Q line added while the LIRR Babylon Branch favorite is kept. (2) The agent must update alert subscriptions the same way (remove 2 and 5, subscribe to Q). (3) The agent must confirm both lists on the account pages. Leaving a 2/5 favorite or subscription, dropping the Babylon Branch, or failing to subscribe to Q is a FAIL.",
8: "FACT CHECKPOINTS: (1) The agent must log in as the given demo account and book the Access-A-Ride trip with the exact pickup, destination, date, time and mobility aid given. (2) The agent must report the new booking reference (AAR-…) and confirm its status in the trip list. Booking with wrong details, or not reporting the reference and status, is a FAIL.",
9: "FACT CHECKPOINTS: (1) The agent must use the fare finder for Hicksville to Penn Station and report the One-Way Peak, Weekly and Monthly prices. (2) The agent must compute the weekly cost in one-way peak tickets for a weekday commute and the four-week total, and report how much the monthly ticket saves over four weeks. (3) The agent must also look up the One-Way Off-Peak price for the same trip and state whether four weeks of off-peak one-ways would still cost more than the monthly ticket. Wrong arithmetic, a missing ticket price, the off-peak price, or the off-peak-vs-monthly verdict is a FAIL.",
10: "FACT CHECKPOINTS: (1) The agent must use the fare finder to get the senior one-way fare for Huntington to Penn Station. (2) The agent must find the senior one-way fare for Poughkeepsie into Manhattan (Grand Central) — via the fare finder or the Metro-North Harlem/Hudson fare chart — and say who pays more and by how much. (3) The agent must open the reduced-fare page and report what seniors pay on subways and local buses. Missing either fare, the difference, or the reduced-fare figure is a FAIL.",
11: "FACT CHECKPOINTS: (1) The agent must open the planned service changes for this weekend and report the LIRR Hempstead Branch change affecting the UBS Arena trip, the stations skipped, and the MTA's alternatives (bus acceptance, alternate station). (2) The agent must report the weekend 7 train changes affecting the Flushing-Main St trip, the stations skipped, and the alternatives. (3) The agent must check whether any 7 line changes are already in effect right now (the current planned-work view) and report the in-effect change with its window. (4) The agent must open the MTA's recent press release about getting to Belmont Park and report what it says about LIRR service to Elmont-UBS Arena Station (the added trains and the regular weekday/weekend service counts). Omitting either mode's changes, the alternatives, the in-effect check, or the press-release facts is a FAIL. (5) The agent must open the Hempstead Branch weekend timetable (Saturday or Sunday view) and note a train time serving Elmont-UBS Arena, reporting that time with the station. Omitting the timetable train time at Elmont-UBS Arena is a FAIL.",
12: "FACT CHECKPOINTS: (1) The agent must answer whether bikes can be taken on LIRR trains on a weekday evening and state the rush-hour rules (inbound arrival window, outbound departure window, weekday bike limit). (2) The agent must report the MTA's recommended transit routing to the USTA National Tennis Center. (3) The agent must report what the bike guide says about locking bikes to MTA property. (4) The agent must also find the MTA's recent announcement about added service for the US Open tournament and report the extra trains and the CityTicket fare it mentions. Missing the rush-hour verdict, the tennis-center routing, the locking rule, the announcement, the extra trains, or the CityTicket fare is a FAIL. (5) The agent must open the 7 train's weekday timetable and note an evening train serving Mets-Willets Point, reporting that time with the station. Omitting the timetable evening train time at Mets-Willets Point is a FAIL.",
13: "FACT CHECKPOINTS: (1) The agent must open the JFK airport guide and report the recommended transit option to Midtown Manhattan, what the guide says the trip costs, whether it is accessible, and the AirTrain fare added on top of the subway fare. (2) The agent must use the fare finder for Jamaica to Penn Station and report both the peak and the off-peak one-way fares. (3) The agent must state which fare matches the guide's CityTicket price. Missing the recommendation, the cost, the accessibility statement, the AirTrain fare, either finder fare, or the CityTicket match is a FAIL.",
14: "FACT CHECKPOINTS: (1) The agent must open the board-and-committee-meetings page and report the next 2026 committee and board meeting dates and where meetings are typically held. (2) The agent must report how the MTA says the public can watch the meetings (livestreamed; recordings posted). (3) The agent must name two current board members with their titles and the agency's Chair and CEO. (4) The agent must report what the MTA budget page calls the largest source of operating revenue and what the FOIL page says is the best way to submit a records request. (5) The agent must find and name the recent press release announcing the upcoming meeting dates. Missing the dates, the location, the watch guidance, both members, the Chair and CEO, the budget source, the FOIL guidance, or the press release is a FAIL.",
15: "FACT CHECKPOINTS: (1) The agent must explain what the Interborough Express is and which boroughs it would connect (from the project page). (2) The agent must describe the milestone announced in the September 9, 2026 press release (design/environmental review progress, accessibility commitments). (3) The agent must name one other active MTA accessibility-improving project and the station it targets. (4) The agent must also find the most recent press release about a station accessibility upgrade (149 St-Hostos Station) and check whether that station appears on the MTA's accessible stations list. Missing the IBX description, the press-release milestone, the other project, the upgrade release, or the accessible-list verdict is a FAIL.",
16: "FACT CHECKPOINTS: (1) The agent must create the account with the exact email, username, display name and password given. (2) The agent must add the E train and the Metro-North Harlem Line as favorites and subscribe to E line service alerts. (3) The agent must report the OMNY card serial number shown on the account page (OMNY-…). Wrong account details, a missing favorite/subscription, or a missing serial is a FAIL.",
17: "FACT CHECKPOINTS: (1) The agent must open the MTA's current alert for the G and report which stations are skipped, what alternative the MTA suggests, and whether the same changes affect the F (they do — the alert covers the Coney Island-bound F as well). (2) The agent must check this weekend's planned service changes for the G (no G between Bedford-Nostrand Avs and Court Sq; free T403 shuttle buses). (3) The agent must find the signal project behind the work (the CBTC upgrade for the Crosstown Line), report which segment it covers, when construction began, and the benefits the MTA promises. (4) The agent must report from the timetable when the first weekday G train from Court Sq toward Brooklyn leaves after 7 a.m. Missing the skipped stations, the F verdict, the weekend changes, the project facts, or the timetable time is a FAIL.",
18: "FACT CHECKPOINTS: (1) The agent must report the crossing toll for a two-axle car with E-ZPass at the Queens-Midtown Tunnel from the tolls-by-vehicle page, and what it would cost by mail. (2) The agent must report what the Congestion Relief Zone tolling information says entering vehicles are charged, what the toll depends on, and the peak-period toll for the car. (3) The agent must answer whether the tunnel crossing counts toward the zone toll (crossing credits for the four tolled entries), which roadways are excluded, and what E-ZPass customers should keep updated. (4) The agent must report any discounts or exemptions offered. Missing any toll amount, the depends-on factors, the crossing-credit answer, the excluded roadways, the E-ZPass guidance, or the discounts is a FAIL. The agent must also open the zone's FAQ and report when the crossing credit is valid (the peak-period days and hours, and that it applies to vehicles using E-ZPass). Omitting the FAQ's crossing-credit validity window is a FAIL.",
19: "FACT CHECKPOINTS: (1) The agent must log in as the given demo account and report the current status of the lighting case for 21 St-Queensbridge (case CS-…). (2) The agent must confirm the Access-A-Ride trip this Saturday is still scheduled (reference and status). (3) The agent must check what the MTA's fares pages now say about MetroCard. (4) The agent must file a new report about the fare machine rejecting MetroCards and confirm both cases appear in the case list with the new case number. Not checking the old case or the AAR trip, missing the MetroCard context, not filing, or not reporting the new case number is a FAIL.",
}


def build_line(original_line: str, index: int) -> str:
    """Splice the two grading keys before the closing brace, byte-preserving."""
    stripped = original_line.rstrip("\n")
    row = json.loads(stripped)
    if "verifier_path" in row or "judge_rubric" in row:
        raise SystemExit(f"row {index} already carries grading keys")
    insertion = (f', "verifier_path": "sites/mta/verify/verify_{index}.py", '
                  f'"judge_rubric": {json.dumps(RUBRICS[index], ensure_ascii=False)}')
    i = stripped.rfind("}")
    if i <= 0:
        raise SystemExit(f"row {index}: cannot find closing brace")
    return stripped[:i] + insertion + stripped[i:]


def main() -> None:
    check_only = "--check" in sys.argv
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    if check_only:
        ok = all('("verifier_path" in json.loads(l) and "judge_rubric" in json.loads(l))'
                 for l in lines if l.strip())
        rows = [json.loads(l) for l in lines if l.strip()]
        good = all(set(r) == {"web_name", "id", "ques", "web", "upstream_url",
                              "verifier_path", "judge_rubric"} for r in rows)
        print("tasks.jsonl contract:", "OK" if good else "MISSING")
        sys.exit(0 if good else 1)
    out = []
    for i, line in enumerate(lines):
        if line.strip():
            out.append(build_line(line, i))
        else:
            out.append(line)
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended grading keys to {len(out)} rows of {TASKS}")


if __name__ == "__main__":
    main()

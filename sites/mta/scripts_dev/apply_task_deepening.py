#!/usr/bin/env python3
"""Apply the 13 deepened task wordings (review §三/⑤: ≥15 honest steps each).

Keeps each task's original core asks (so the reviewer's frozen ground truths
stay valid) and extends the goal with additional snapshot-anchored sub-asks
that lengthen the real functional chain. No mechanical step lists, ≤100 words.
"""
import json
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parents[1]
TASKS = SITE / "tasks.jsonl"

NEW = {
    2: ("My aunt uses a power wheelchair and is meeting friends at the 14 St-Union Sq "
        "station. Check whether the station is listed as accessible and which platforms "
        "the elevators serve, whether any elevator or escalator there is currently out of "
        "service, when it is expected back, and what alternative the MTA suggests while "
        "it is out. Also check whether any further elevator or escalator maintenance is "
        "scheduled at the station over the next few days."),
    3: ("An elevator serving the Woodlawn-bound 4 platform at 149 St-Grand Concourse has "
        "been out since Wednesday morning, and my neighbor who relies on it is upset. Look "
        "up its current status, the reason, and the estimated return to service on the "
        "MTA's elevator status page. She also wants to know what the MTA's accessibility "
        "pages say about filing an ADA-related complaint and what happens after a case is "
        "logged, then file a feedback report about the elevator on my behalf (Sam Ortiz, "
        "sam.ortiz73@example.com) and give me the new case number."),
    5: ("My colleague filed two lost property claims last week and asked me to follow up "
        "while she is away: LF-26094217 with the subway lost and found, and LF-26095803 "
        "with the Long Island Rail Road. My cousin also filed LF-26096625 with "
        "Metro-North. Look up all three and tell me each claim's status and which items "
        "they cover. For the claim matched with the property office, which lost-and-found "
        "facility holds it and what does the status page say to keep handy? Also, what "
        "does the subway lost-and-found page say happens after you file a claim?"),
    6: ("Log in with the demo account (email: bob.c@test.com, password: TestPass123!). "
        "Review this week's OMNY charges: how many local rides versus express rides he "
        "took, how much he has spent toward each weekly cap, and how much room is left "
        "before the subway-and-local-bus cap. Cross-check the tap-and-ride page for the "
        "weekly cap amounts and when a new cap period starts. Then check the current "
        "service status of his favorite lines (A, E, and 7) and summarize any active "
        "alerts. Based on the cap rules, would two more subway rides on Sunday cost him "
        "anything extra?"),
    9: ("A client of mine commutes on weekdays from Hicksville to Penn Station on the "
        "LIRR and currently buys a one-way peak ticket for every ride. Using the MTA fare "
        "finder, work out what he pays per week in one-way peak tickets, compare that "
        "with the weekly ticket, and compare four weeks of one-way peak tickets with the "
        "monthly ticket: how much would the monthly save over four weeks? He could also "
        "shift to off-peak trains: what would each one-way cost then, and would four "
        "weeks of off-peak one-ways still cost more than the monthly ticket?"),
    11: ("This weekend I'm taking my cousins to a concert at UBS Arena, arriving on the "
         "LIRR Hempstead Branch, and on Sunday we plan to ride the 7 train to "
         "Flushing-Main St. Check the MTA's planned service changes for this weekend for "
         "both trips: what should we expect on each, which stations are affected, and "
         "what travel alternatives does the MTA suggest? Also see whether any changes are "
         "already in effect for the 7 line right now, and find the MTA's recent press "
         "release about getting to Belmont Park: what does it say about LIRR service to "
         "Elmont-UBS Arena station?"),
    12: ("My friends and I want to bring our bikes from Brooklyn to the USTA Billie Jean "
         "King National Tennis Center for a US Open weekday evening session. According "
         "to the MTA's guides, can bikes be taken on LIRR trains at that time and what "
         "rush-hour rules apply, how does the MTA recommend reaching the tennis center by "
         "transit, and what does the bike guide say about locking bikes to MTA property? "
         "Also find the MTA's recent announcement about added service for the tournament "
         "and note the extra trains and the CityTicket fare it mentions."),
    13: ("My parents, both 68, land at JFK at 6 a.m. on a Sunday with heavy luggage, and "
         "my mother uses a cane. Using the MTA's airport guide, what is the recommended "
         "transit option to Midtown Manhattan, what does the guide say the trip costs and "
         "whether it is accessible, and what AirTrain fare is added on top of the subway "
         "fare? They will take the LIRR from Jamaica that morning: use the fare finder to "
         "check both the peak and the off-peak one-way fares from Jamaica to Penn "
         "Station, and tell me which matches the guide's CityTicket price."),
    14: ("I'm a journalist covering the next MTA Board meeting. According to the MTA's "
         "transparency pages, when is the next committee and board meeting on the 2026 "
         "calendar, where are meetings typically held, and how does the MTA say the "
         "public can watch them? Name two current board members with their titles and the "
         "agency's Chair and CEO. For background, what does the MTA budget page call the "
         "largest source of operating revenue, and what does the FOIL page say is the "
         "best way to submit a records request? Also find the recent press release "
         "announcing the upcoming meeting dates."),
    15: ("I'm writing a school report on the Interborough Express. Using the MTA's "
         "project pages and press releases, explain what the Interborough Express is and "
         "which boroughs it would connect, describe the milestone announced in the "
         "September 9, 2026 press release, and name one other active MTA project that "
         "improves accessibility and the station it targets. Also find the most recent "
         "press release about a station accessibility upgrade and check whether that "
         "station appears on the MTA's accessible stations list."),
    17: ("My cousin moved to Brooklyn and takes the G train to work in Long Island City. "
         "She heard the G line faces major service changes in 2026. Find the MTA's "
         "current alert for the G: which stations are skipped, what alternative the MTA "
         "suggests, and whether the same changes affect her roommate's F. Check this "
         "weekend's planned service changes for the G too. Then find the signal project "
         "behind the work: which segment it covers, when construction began, and what "
         "benefits the MTA promises. When does the first weekday G train from Court Sq "
         "toward Brooklyn leave after 7 a.m.?"),
    18: ("I drive a two-axle car with E-ZPass from Queens into Manhattan below 60th "
         "Street on weekday mornings, usually through the Queens-Midtown Tunnel. Using "
         "the MTA's toll pages: what is my Queens-Midtown crossing toll with E-ZPass, and "
         "what would it cost by mail? What does the Congestion Relief Zone tolling "
         "information say entering vehicles are charged, what the toll depends on, and "
         "the peak-period toll for my car? Does my tunnel crossing count toward the zone "
         "toll, which roadways are excluded, what should E-ZPass customers keep updated, "
         "and are any discounts or exemptions offered?"),
    19: ("Log in with the demo account (email: david.k@test.com, password: TestPass123!). "
         "He reported lighting out in the 21 St-Queensbridge mezzanine on the G line "
         "earlier this month and wants its current status, and he wants to confirm his "
         "Access-A-Ride trip this Saturday is still scheduled. The fare machine at the "
         "same station keeps rejecting his MetroCard: check what the MTA's fares pages "
         "now say about MetroCard, then file a report on his behalf about the machine and "
         "confirm both cases appear in his case list with the new case number."),
}

rows = [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]
assert len(rows) == 20

step_markers = re.compile(
    r"\b(click the|tap the|press the|select the (first|second) result|go back to|then click|"
    r"step 1|first click|next click)\b", re.I)

for idx, text in NEW.items():
    row = rows[idx]
    words = len(text.split())
    assert 25 <= words <= 100, f"T{idx}: {words} words out of budget"
    assert not step_markers.search(text), f"T{idx} reads like a step list"
    assert text != row["ques"], f"T{idx} unchanged"
    row["ques"] = text
    print(f"T{idx}: {words} words")

TASKS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
print("tasks.jsonl updated")

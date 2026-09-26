#!/usr/bin/env python3
"""Reviewer-side rubric append for sites/ryanair/tasks.jsonl.

Adds ``verifier_path`` + ``judge_rubric`` to every task row. The five
contributor keys (web_name, id, ques, web, upstream_url) stay byte-identical
to the contributor's rows; no ``answer`` key is ever written. Ground truth
lives ONLY inside sites/ryanair/verify/verify_N.py (hardcoded), never here.

Idempotent: rows that already carry both keys are left untouched.
"""
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
TASKS = SITE / "tasks.jsonl"

RUBRICS = {
    "Ryanair--0": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the flight results for London "
        "Stansted to Dublin departing 2026-10-13 and returning 2026-10-20 for 2 adults, "
        "select the cheapest outbound and the cheapest return flight, choose the Basic "
        "fare, and submit two passenger name rows. (2) The trajectory MUST pass through "
        "the seats, bags and extras steps without adding anything, then complete the "
        "guest payment with the task's contact email and card and reach the confirmation "
        "page. (3) The final answer MUST report the booking reference shown on the "
        "confirmation page and the total charged (flights for 2 adults plus the 2% card "
        "processing fee). An empty answer is a FAIL. An answer without the on-site "
        "booking (no matching new booking row in the database) is a FAIL."),
    "Ryanair--1": (
        "FACT CHECKPOINTS: (1) The trajectory MUST search London Stansted to Dublin "
        "departing 13 October returning 20 October and read the date strips on the "
        "results page. (2) The final answer MUST name the cheapest displayed departure "
        "day (with its price) and the cheapest displayed return day (with its price), "
        "and MUST report the total paid and the booking reference from the confirmation "
        "page. (3) The database MUST contain exactly one new booking for the strip-"
        "cheapest dates on the Basic fare for 1 adult as a guest. An empty answer is a "
        "FAIL. Booking dates other than the two cheapest displayed days is a FAIL."),
    "Ryanair--2": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the flight results for London "
        "Gatwick to Malaga departing 2026-10-09 returning 2026-10-16 for 2 adults and "
        "select the cheapest outbound and return flights. (2) The trajectory MUST view "
        "the fare table comparing the bundles; the final answer MUST state how much more "
        "Flexi Plus costs per person for the whole trip than Plus and name the bundle "
        "that allows flight changes with no fees. (3) The booking MUST be on the Plus "
        "fare for 2 adults as a guest with the task's email; the answer MUST report the "
        "booking reference and total. An empty answer is a FAIL."),
    "Ryanair--3": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the flight results for "
        "Manchester to Dublin departing 2026-10-06 returning 2026-10-10 for 2 adults "
        "and book the Plus fare. (2) The seats step MUST be used: a window seat in the "
        "extra-legroom front row (row 1) on the outbound, and the cheapest two seats "
        "together (adjacent, back rows) on the return; every passenger must be seated on "
        "both flights. (3) The final answer MUST report the booking reference and how "
        "much the seats added to the total, consistent with the booked seat rows. An "
        "empty answer is a FAIL. A booking without the specified seats is a FAIL."),
    "Ryanair--4": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the flight results for London "
        "Stansted to Alicante departing 2026-10-15 returning 2026-10-22 for 2 adults on "
        "the Basic fare. (2) The bags step MUST add Priority & 2 Cabin Bags for both "
        "passengers and one 20kg check-in bag for the first passenger only, applying to "
        "both flights. (3) The final answer MUST report how much the bags added compared "
        "with travelling with only the free small bags and the final total, plus the "
        "booking reference. An empty answer is a FAIL. A booking whose bag lines do not "
        "match the task (e.g. a 20kg bag for the second passenger) is a FAIL."),
    "Ryanair--5": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the flight results for "
        "Birmingham to Faro departing 2026-10-10 returning 2026-10-18 for 2 adults and "
        "book the Plus fare. (2) The extras step MUST enable Security Fast Track for "
        "both airports and select the Insurance Plus policy. (3) The final answer MUST "
        "report the extras total shown in the price breakdown and the booking reference. "
        "An empty answer is a FAIL. A booking without the fast track flag or with a "
        "different insurance tier is a FAIL."),
    "Ryanair--6": (
        "FACT CHECKPOINTS: (1) The trajectory MUST find the newsletter welcome promo "
        "code on the homepage and apply it in the search widget for the Edinburgh to "
        "Dublin search departing 2026-10-20 returning 2026-10-27 for 1 adult on the "
        "Basic fare. (2) The final answer MUST name the promo code used, the discount it "
        "gave, and the total paid, plus the booking reference. (3) The database MUST "
        "contain exactly one new booking carrying that promo code with the discounted "
        "flight total. An empty answer is a FAIL. A booking without the promo code "
        "applied is a FAIL."),
    "Ryanair--7": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the cheap flight destinations "
        "page from London Stansted with a maximum price filter of £25 and a maximum "
        "flight time filter of 2 hours (120 minutes) applied. (2) The final answer MUST "
        "name the cheapest destination card under those filters, its price, and the "
        "booking reference of the one-way Basic booking made on the date shown on that "
        "card for 1 adult as a guest. (3) The database MUST contain exactly one new "
        "one-way booking to that destination on the card date at the card price. An "
        "empty answer is a FAIL. Booking a destination outside the filters is a FAIL."),
    "Ryanair--8": (
        "FACT CHECKPOINTS: (1) The trajectory MUST log in as the demo account with the "
        "given email, open the account area, update the mobile number, address and "
        "newsletter preference, add the Mastercard, remove the old Visa, and report the "
        "saved payment methods and the default. (2) The trajectory MUST open the "
        "upcoming Malaga booking, report its reference and total, complete the online "
        "check-in, read the boarding pass seat, and log out. (3) The database MUST show "
        "the profile update, exactly the Mastercard remaining (promoted to default when "
        "the default Visa was removed), and the Malaga booking checked in. An empty "
        "answer is a FAIL. A check-in that did not happen in the database is a FAIL."),
    "Ryanair--9": (
        "FACT CHECKPOINTS: (1) The trajectory MUST look up the booking by reference "
        "with the given email on the My bookings page and open its detail. (2) The "
        "final answer MUST report the outbound flight number and departure time, the "
        "return departure time, the passenger count and the total paid, exactly as shown "
        "on the booking page. (3) The trajectory MUST open the help centre bag article "
        "and the seats article and the booking's check-in page; the answer MUST report "
        "the 20kg bag price online versus at the airport, the cheapest extra-legroom "
        "seat price, and state that online check-in has NOT opened yet with the reason "
        "(randomly allocated seats open 24 hours before departure). This is a read-only "
        "task: any database change is a FAIL. An empty answer is a FAIL."),
    "Ryanair--10": (
        "FACT CHECKPOINTS: (1) The trajectory MUST log in as the demo account with the "
        "given email, update the mobile number, and report the saved payment methods "
        "and the default card as shown on the account page. (2) The trajectory MUST open "
        "the upcoming Rome booking, check in online, open the boarding pass, and the "
        "answer MUST report the outbound flight number, its departure time, the seat on "
        "the boarding pass, when boarding closes, and the total paid. (3) The trajectory "
        "MUST open the help centre check-in article; the answer MUST report the paper "
        "boarding pass re-issue fee. The database MUST show the phone update and the "
        "Rome booking checked in. An empty answer is a FAIL."),
    "Ryanair--11": (
        "FACT CHECKPOINTS: (1) The trajectory MUST log in as the demo account with the "
        "given email and report the saved payment methods and the default card from the "
        "account page. (2) The trajectory MUST open the Dublin weekend booking and its "
        "check-in page; the answer MUST report which fare the booking is on and state "
        "exactly when online check-in opens and why (randomly allocated seats open 24 "
        "hours before departure). (3) The trajectory MUST open the help centre fee "
        "articles; the answer MUST report the airport check-in fee, the 20kg bag price "
        "at the airport versus online, and when the boarding gate closes. This is a "
        "read-only task: any database change is a FAIL. An empty answer is a FAIL."),
    "Ryanair--12": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the flight timetable for London "
        "Stansted to Marrakesh; the answer MUST report the flight number, its departure "
        "and arrival times, and the two days of the week it does NOT operate, exactly as "
        "shown in the timetable grid. (2) The trajectory MUST book the cheapest one-way "
        "Basic fare on the first Saturday after 10 October for 1 adult as a guest; the "
        "answer MUST report the price paid and the booking reference. (3) The database "
        "MUST contain exactly one new one-way booking on that Saturday. An empty answer "
        "is a FAIL."),
    "Ryanair--13": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the help centre bag price "
        "article before booking; the answer MUST report the 20kg check-in bag price "
        "online versus at the airport. (2) The trajectory MUST book the one-way London "
        "Stansted to Dublin flight on 14 October for 1 adult on the Basic fare with one "
        "20kg check-in bag as a guest. (3) The answer MUST report the bag price the site "
        "charged and the saving versus the airport price (a one-way booking is charged "
        "for exactly one 20kg bag), plus the total and booking reference. An empty "
        "answer is a FAIL. A booking charged for more than one bag leg is a FAIL."),
    "Ryanair--14": (
        "FACT CHECKPOINTS: (1) The trajectory MUST reach the extras step of a booking "
        "and compare the two insurance policies; the answer MUST name the policy offering "
        "nil-excess medical cover up to £5,000,000. (2) The trajectory MUST book the "
        "return trip Glasgow to Malaga departing 2026-10-12 returning 2026-10-19 for 2 "
        "adults on the Basic fare as a guest with that insurance policy selected. (3) The "
        "answer MUST report the insurance cost and the total, plus the booking "
        "reference. The database MUST show the correct insurance key on the new booking. "
        "An empty answer is a FAIL."),
    "Ryanair--15": (
        "FACT CHECKPOINTS: (1) The trajectory MUST book the return trip Bristol to "
        "Barcelona departing 2026-10-09 returning 2026-10-16 for 2 adults plus 1 teen on "
        "the Regular fare as a guest with no extras. (2) The final answer MUST report the "
        "total, the booking reference, and the cabin bag allowance the Regular fare "
        "includes (as shown on the fare table). (3) The database MUST contain exactly one "
        "new booking with three passenger rows and no seats, bags or extras totals. An "
        "empty answer is a FAIL."),
    "Ryanair--16": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the flight results for London "
        "Stansted to Dublin on 5 November and compare the morning flight cards "
        "(departing before 10:00). (2) The booking MUST be the cheapest morning "
        "departure, one-way, Basic fare, 1 adult, as a guest. (3) The final answer MUST "
        "report the flight number, its departure time and the total paid, plus the "
        "booking reference. An empty answer is a FAIL. Booking an afternoon flight is a "
        "FAIL."),
    "Ryanair--17": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the route map; the answer MUST "
        "list every Greek destination with its airport code (the codes are shown on the "
        "route map itself). (2) The trajectory MUST open the "
        "cheap flight destinations page from London Stansted and identify the cheapest "
        "one-way Basic fare to a Greek destination; the answer MUST name that "
        "destination, its price, and the booking reference of the one-way booking made "
        "on the date shown on its card. (3) The database MUST contain exactly one new "
        "one-way booking to that Greek destination on the card date at the card price. "
        "An empty answer is a FAIL."),
    "Ryanair--18": (
        "FACT CHECKPOINTS: (1) The trajectory MUST log in as the demo account with the "
        "given email, update the mobile number, and report the saved payment methods and "
        "the default card from the account page. (2) The trajectory MUST open the "
        "upcoming Krakow booking; the answer MUST report the booking reference, fare "
        "type, outbound flight number and departure time, the allocated outbound seat, "
        "the return departure time and the total paid. (3) Online check-in is open for "
        "this booking: the trajectory MUST check in and report the seat on the boarding "
        "pass, and MUST open the help centre check-in article to report the paper "
        "boarding pass re-issue fee. The database MUST show the Krakow booking checked "
        "in. An empty answer is a FAIL."),
    "Ryanair--19": (
        "FACT CHECKPOINTS: (1) The trajectory MUST book the return trip London Stansted "
        "to Palma de Mallorca departing 2026-10-20 returning 2026-10-27 for 2 adults on "
        "the Plus fare as a guest. (2) The booking MUST carry: seats together in the "
        "best-value front section on both flights (all passengers seated), one 20kg "
        "check-in bag each passenger on both flights, Security Fast Track at Stansted, "
        "and the standard insurance policy. (3) The final answer MUST report the booking "
        "reference and the full price breakdown total. An empty answer is a FAIL. A "
        "booking missing any of the requested components is a FAIL."),
    "Ryanair--20": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the Flights to Dublin page and "
        "report the fare offered from Birmingham with its departure date as shown. (2) "
        "The trajectory MUST find the newsletter welcome promo code on the homepage and "
        "apply it when booking that Birmingham to Dublin flight one-way for 1 adult on "
        "the Basic fare as a guest. (3) The final answer MUST report the promo code, the "
        "discount it gave and the total paid, plus the booking reference. The database "
        "MUST contain exactly one new one-way booking carrying that promo code with the "
        "discounted flight total. An empty answer is a FAIL."),
}


def main() -> int:
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    out, changed = [], 0
    for line in lines:
        row = json.loads(line)
        tid = row["id"]
        if "verifier_path" in row and "judge_rubric" in row:
            out.append(line)
            continue
        original_keys = list(row.keys())
        assert original_keys == ["web_name", "id", "ques", "web", "upstream_url"], \
            f"{tid}: unexpected contributor keys {original_keys}"
        row["verifier_path"] = f"sites/ryanair/verify/verify_{int(tid.split('--')[1])}.py"
        row["judge_rubric"] = RUBRICS[tid]
        out.append(json.dumps(row, ensure_ascii=False))
        changed += 1
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[append_rubrics] {changed} rows updated, {len(out)} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

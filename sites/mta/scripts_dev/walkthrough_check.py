"""Playwright walkthrough driver for mta tasks.jsonl spot-checks.

Drives selected tasks through the mirror at http://localhost:43082/ the way a
browser agent would (navigate, click, fill, submit) and logs every URL step
so the trajectory can be audited. Verifies the on-page facts against the
ground truth computed from the seed DB.

Usage:  python scripts_dev/walkthrough_check.py 0 4 6 9 11
"""
from __future__ import annotations

import json
import re
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:43082"


def steps_log(page, log: list, note: str = "") -> None:
    log.append({"url": page.url, "note": note})


def text_of(page) -> str:
    return re.sub(r"\s+", " ", page.inner_text("main"))


def walk_0(log):
    """Valley Stream commute: timetable + fare finder + planned changes."""
    with page_context(log) as page:
        page.goto(f"{BASE}/schedules", wait_until="networkidle")
        page.click("main a[href='/agency/long-island-rail-road']")
        page.wait_for_load_state("networkidle")
        page.click("main a[href='/schedules/lirr/long-beach']")
        page.wait_for_load_state("networkidle")
        page.select_option("select#day", "weekday")
        page.select_option("select#direction", "1")
        page.click("button:has-text('Update timetable')")
        page.wait_for_load_state("networkidle")
        body = text_of(page)
        facts = {"vs_0820": "8:20" in body, "penn_0859": "8:59" in body}
        page.goto(f"{BASE}/fares-tolls/lirr-metro-north/fare-finder",
                 wait_until="networkidle")
        page.select_option("select#origin, select[name=from]", "Valley Stream")
        page.select_option("select#dest, select[name=to]", "Penn Station")
        page.select_option("select#ticket, select[name=ticket]", "One-Way Peak")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        body2 = text_of(page)
        facts["fare_1350"] = "$13.50" in body2
        page.goto(f"{BASE}/planned-service-changes?mode=lirr&when=weekend",
                  wait_until="networkidle")
        body3 = text_of(page)
        facts["long_beach_changes_absent"] = "Long Beach" not in body3
        facts["west_hempstead_present"] = "West Hempstead" in body3
        return facts


def walk_4(log):
    """Lost property claim form submission."""
    with page_context(log) as page:
        page.goto(f"{BASE}/lost-and-found", wait_until="networkidle")
        page.click("text=Subway, Bus and Staten Island Railway")
        page.wait_for_load_state("networkidle")
        page.click("a:has-text('Report a lost item')")
        page.wait_for_load_state("networkidle")
        page.fill("input[name=date_lost]", "2026-09-22")
        page.fill("input[name=line_route]", "7 train")
        page.fill("input[name=station]", "Flushing-Main St")
        page.select_option("select[name=item_type]", "Bag")
        page.fill("textarea[name=item_description]",
                  "Green duffel bag with running shoes inside")
        page.fill("input[name=contact_name]", "Alex Rivera")
        page.fill("input[name=contact_email]", "alex.rivera1984@example.com")
        page.fill("input[name=contact_phone]", "555-0187")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        body = text_of(page)
        m = re.search(r"LF-2609\d+", body)
        return {"claim_ref": m.group(0) if m else None,
                "status_page": "claim reference" in body.lower()}


def walk_6(log):
    """Login + OMNY cap analysis."""
    with page_context(log) as page:
        page.goto(f"{BASE}/account/login", wait_until="networkidle")
        page.fill("input[name=email]", "bob.c@test.com")
        page.fill("input[name=password]", "TestPass123!")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        page.goto(f"{BASE}/account/omny", wait_until="networkidle")
        body = text_of(page)
        return {
            "local_24": "$24.00" in body, "cap_35": "$35.00" in body,
            "express_725": "$7.25" in body, "express_cap_67": "$67.00" in body,
            "x27": "X27" in body, "q58": "Q58" in body,
        }


def walk_9(log):
    """Hicksville commute cost comparison."""
    with page_context(log) as page:
        page.goto(f"{BASE}/fares-tolls/lirr-metro-north/fare-finder",
                  wait_until="networkidle")
        page.select_option("select#origin, select[name=from]", "Hicksville")
        page.select_option("select#dest, select[name=to]", "Penn Station")
        page.select_option("select#ticket, select[name=ticket]", "One-Way Peak")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        facts = {"peak_1525": "$15.25" in text_of(page)}
        for ticket, marker in (("Weekly", "$106.50"), ("Monthly", "$299.75")):
            page.select_option("select#ticket, select[name=ticket]", ticket)
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle")
            facts[ticket.lower()] = marker in text_of(page)
        return facts


def walk_11(log):
    """Weekend planned changes: UBS Arena + 7 train."""
    with page_context(log) as page:
        page.goto(f"{BASE}/planned-service-changes?mode=lirr&when=weekend",
                  wait_until="networkidle")
        body = text_of(page)
        facts = {"elmont_skip": "Elmont-UBS Arena" in body,
                 "hempstead": "Hempstead" in body}
        page.goto(f"{BASE}/planned-service-changes?mode=subway&when=weekend",
                  wait_until="networkidle")
        body2 = text_of(page)
        facts.update({"seven_52st": "52 St" in body2, "seven_69st": "69 St" in body2,
                      "woodside_alt": "Woodside-61 St" in body2})
        return facts


def walk_16(log):
    """Register + favorites + subscriptions + OMNY serial."""
    with page_context(log) as page:
        page.goto(f"{BASE}/account/register", wait_until="networkidle")
        page.fill("input[name=email]", "pat.gonzalez@example.net")
        page.fill("input[name=username]", "pat_g")
        page.fill("input[name=display_name]", "Pat Gonzalez")
        page.fill("input[name=password]", "PatStr0ng!2026")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        body = text_of(page)
        m = re.search(r"OMNY-[0-9A-F]{8}", body)
        facts = {"serial": m.group(0) if m else None}
        page.goto(f"{BASE}/account/favorites", wait_until="networkidle")
        page.select_option("select[name=service_type]", "subway")
        page.fill("input#service_id", "E")
        page.click("button:has-text('Add favorite')")
        page.wait_for_load_state("networkidle")
        page.select_option("select[name=service_type]", "rail")
        page.fill("input#service_id", "Harlem")
        page.click("button:has-text('Add favorite')")
        page.wait_for_load_state("networkidle")
        facts["favorites_ok"] = "E" in text_of(page)
        page.goto(f"{BASE}/account/subscriptions", wait_until="networkidle")
        page.select_option("select[name=service_type]", "subway")
        page.fill("input#service_id", "E")
        page.click("button:has-text('Subscribe')")
        page.wait_for_load_state("networkidle")
        facts["subscribed"] = "E" in text_of(page)
        return facts


def walk_1(log):
    """Last train Penn Station -> Ronkonkoma + first morning + off-peak fare."""
    with page_context(log) as page:
        page.goto(f"{BASE}/schedules", wait_until="networkidle")
        page.click("main a[href='/agency/long-island-rail-road']")
        page.wait_for_load_state("networkidle")
        page.click("main a[href='/schedules/lirr/ronkonkoma']")
        page.wait_for_load_state("networkidle")
        page.select_option("select#day", "weekday")
        page.select_option("select#direction", "0")
        page.click("button:has-text('Update timetable')")
        page.wait_for_load_state("networkidle")
        body = text_of(page)
        facts = {"last_2355": "23:55" in body, "arr_0120": "1:20" in body,
                 "first_0516": "5:16" in body}
        page.goto(f"{BASE}/fares-tolls/lirr-metro-north/fare-finder",
                 wait_until="networkidle")
        page.select_option("select#origin, select[name=from]", "Ronkonkoma")
        page.select_option("select#dest, select[name=to]", "Penn Station")
        page.select_option("select#ticket, select[name=ticket]", "One-Way Off-Peak")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        facts["offpeak_1600"] = "$16.00" in text_of(page)
        return facts


def walk_2(log):
    """14 St-Union Sq accessibility + elevator outage."""
    with page_context(log) as page:
        page.goto(f"{BASE}/nearby?q=Union Sq", wait_until="networkidle")
        page.click("main a[href='/station/L03']")
        page.wait_for_load_state("networkidle")
        body = text_of(page)
        facts = {"accessible": "accessible station" in body,
                 "note": "L N Q R W only" in body}
        page.goto(f"{BASE}/elevator-escalator-status?show=outages",
                  wait_until="networkidle")
        body2 = text_of(page)
        facts.update({"es258x": "ES258X" in body2, "repair": "Repair" in body2,
                      "return_0925": "09/25/2026" in body2,
                      "alternative": "Alternative while out" in body2})
        return facts


def walk_3(log):
    """149 St-Grand Concourse elevator outage + feedback report."""
    with page_context(log) as page:
        page.goto(f"{BASE}/elevator-escalator-status?show=outages",
                  wait_until="networkidle")
        page.fill("input[name=station]", "149 St-Grand Concourse")
        page.click("button:has-text('Check outages')")
        page.wait_for_load_state("networkidle")
        body2 = text_of(page)
        facts = {"el101": "EL101" in body2, "planned_work": "Planned Work" in body2,
                 "return_0925": "09/25/2026" in body2}
        page.goto(f"{BASE}/contact-us/feedback", wait_until="networkidle")
        page.select_option("select#category, select[name=category]",
                           "Elevator or escalator outage")
        page.fill("input[name=subject]", "Elevator out at 149 St-Grand Concourse")
        page.fill("textarea[name=message]",
                  "The elevator to the Woodlawn-bound 4 platform has been out since Wednesday morning. Please post an update.")
        page.fill("input[name=contact_name]", "Sam Ortiz")
        page.fill("input[name=contact_email]", "sam.ortiz73@example.com")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        m = re.search(r"CS-2609\d+", text_of(page))
        facts["case_ref"] = m.group(0) if m else None
        return facts


def walk_5(log):
    """Claim status lookups LF-26094217 + LF-26095803."""
    with page_context(log) as page:
        page.goto(f"{BASE}/lost-and-found/claim?ref=LF-26094217",
                 wait_until="networkidle")
        body = text_of(page)
        facts = {"backpack": "Backpack" in body, "received": "Received" in body}
        page.goto(f"{BASE}/lost-and-found/claim?ref=LF-26095803",
                 wait_until="networkidle")
        body2 = text_of(page)
        facts.update({"umbrella": "Umbrella" in body2,
                      "in_review": "In Review" in body2,
                      "lirr": "Long Island Rail Road" in body2})
        return facts


def walk_8(log):
    """AAR booking as carol."""
    with page_context(log) as page:
        page.goto(f"{BASE}/account/login", wait_until="networkidle")
        page.fill("input[name=email]", "carol.d@test.com")
        page.fill("input[name=password]", "TestPass123!")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        page.goto(f"{BASE}/accessibility/access-a-ride/book",
                 wait_until="networkidle")
        page.fill("input[name=pickup]", "120-55 Queens Blvd, Kew Gardens")
        page.fill("input[name=destination]", "Elmhurst Hospital, 79-01 Broadway, Elmhurst")
        page.fill("input[name=date]", "2026-09-29")
        page.fill("input[name=time]", "09:15")
        page.select_option("select#passengers, select[name=passengers]", "1")
        page.select_option("select#mobility_aid, select[name=mobility_aid]", "Walker")
        page.fill("input[name=purpose]", "Medical appointment")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        body = text_of(page)
        m = re.search(r"AAR-2609\d+", body)
        return {"trip_ref": m.group(0) if m else None,
                "scheduled": "Scheduled" in body,
                "sep29": "2026-09-29" in body or "09/29/2026" in body or "September 29" in body}


def walk_19(log):
    """David's feedback case follow-up + new report."""
    with page_context(log) as page:
        page.goto(f"{BASE}/account/login", wait_until="networkidle")
        page.fill("input[name=email]", "david.k@test.com")
        page.fill("input[name=password]", "TestPass123!")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        page.goto(f"{BASE}/contact-us/case?ref=CS-26095281", wait_until="networkidle")
        body = text_of(page)
        facts = {"lighting_case": "Lighting out in the G line mezzanine" in body,
                 "open": "Open" in body}
        page.goto(f"{BASE}/contact-us/feedback", wait_until="networkidle")
        page.select_option("select#category, select[name=category]",
                           "Station or facility")
        page.fill("input[name=subject]", "Fare machine rejects MetroCards at 21 St-Queensbridge")
        page.fill("textarea[name=message]",
                  "The fare machine at 21 St-Queensbridge keeps rejecting MetroCards. Please send a technician.")
        page.fill("input[name=contact_name]", "David Kim")
        page.fill("input[name=contact_email]", "david.k@test.com")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        m = re.search(r"CS-2609\d+", text_of(page))
        facts["new_case"] = m.group(0) if m else None
        return facts


WALKS = {0: walk_0, 1: walk_1, 2: walk_2, 3: walk_3, 4: walk_4, 5: walk_5,
         6: walk_6, 8: walk_8, 9: walk_9, 11: walk_11, 16: walk_16, 19: walk_19}


class page_context:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        self.page = browser.new_page()

        def on_nav(frame):
            if frame == self.page.main_frame:
                self.log.append({"url": frame.url})

        self.page.on("framenavigated", on_nav)
        return self.page

    def __exit__(self, *exc):
        self.page.close()


browser = None

def main():
    global browser
    ids = [int(a) for a in sys.argv[1:]] or [0, 4, 6, 9, 11, 16]
    report = {}
    with sync_playwright() as p:
        global browser
        browser = p.chromium.launch()
        for tid in ids:
            log: list = []
            try:
                facts = WALKS[tid](log)
                report[tid] = {"ok": all(bool(v) for v in facts.values()), "facts": facts}
            except Exception as exc:  # noqa: BLE001
                report[tid] = {"ok": False, "error": str(exc)[:200]}
            report[tid]["steps"] = log
        browser.close()
    print(json.dumps(report, indent=1))
    return 0 if all(r["ok"] for r in report.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

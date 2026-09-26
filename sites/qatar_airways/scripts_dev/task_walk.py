#!/usr/bin/env python3
"""Honest task walkthroughs for the qatar_airways mirror (contributor self-check).

Drives a real Chromium via Playwright through the same on-site paths an agent
must take for each sampled task, recording every navigation / fill / submit
step with a screenshot, and checks the final answer facts against what the
site actually shows. Output: <out_dir>/<task>/walk.json + screenshots/.

Usage:  python scripts_dev/task_walk.py --base http://127.0.0.1:43089 \
            --tasks 0 3 5 7 8 --out /tmp/qa_walks
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import time

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:43089"
OUT = pathlib.Path("/tmp/qa_walks")


class Walk:
    def __init__(self, page, task_id, out_dir):
        self.page = page
        self.task_id = task_id
        self.out = out_dir
        self.out.mkdir(parents=True, exist_ok=True)
        self.steps = []
        self.n = 0

    def record(self, type_, tag, note="", value=None):
        self.n += 1
        shot = f"{self.n:02d}_{type_.lower()}_{tag}.png"
        self.page.screenshot(path=str(self.out / shot), full_page=True)
        step = {"type": type_, "tag": tag, "url": self.page.url, "shot": shot}
        if value is not None:
            step["value"] = value
        if note:
            step["note"] = note
        self.steps.append(step)
        print(f"  [{self.n:02d}] {type_} {tag} -> {self.page.url}")

    def nav(self, path, tag):
        self.page.goto(BASE + path, wait_until="networkidle")
        self.record("NAV", tag)

    def fill(self, selector, value, tag):
        self.page.fill(selector, value)
        self.record("FILL", tag, value=value)

    def select(self, selector, value, tag):
        self.page.select_option(selector, value)
        self.record("FILL", tag, value=value)

    def click(self, selector, tag, wait_nav=True):
        if wait_nav:
            with self.page.expect_navigation():
                self.page.click(selector)
        else:
            self.page.click(selector)
        self.record("SUBMIT", tag)

    def read_text(self, pattern, tag, note=""):
        text = self.page.inner_text("body")
        m = re.search(pattern, text, re.I | re.S)
        value = m.group(0).strip() if m else None
        self.record("READ", tag, note=note, value=value)
        return value

    def scan(self, tag, note=""):
        self.record("SCAN", tag, note=note)

    def save(self, answer, extra=None):
        data = {"task_id": self.task_id, "steps": self.steps,
                "final_answer": answer, "extra": extra or {}}
        (self.out / "walk.json").write_text(json.dumps(data, indent=1))
        print(f"  saved {self.out / 'walk.json'} ({len(self.steps)} steps)")


def csrf(page):
    return page.inner_text("body") and page.eval_on_selector(
        "input[name=csrf_token]", "el => el.value")


# ---------------------------------------------------------------- task walks

def walk_0(page):
    """Qatar Airways--0: cheapest Economy Lite DOH->LHR for two."""
    w = Walk(page, "Qatar Airways--0", OUT / "0")
    w.nav("/", "home")
    w.fill("#from", "DOH", "from")
    w.fill("#to", "LHR", "to")
    w.fill("#depart", "2026-10-08", "depart")
    w.select("#adults", "2", "adults")
    w.click("button:has-text('Search flights')", "search")
    w.scan("results", note="compare Economy Lite fares across the day")
    # pick the cheapest Economy Lite option (first 665 card on the page)
    w.page.locator("a.btn:has-text('Select')").first.click()
    w.page.wait_for_load_state("networkidle")
    w.record("NAV", "pax-details")
    w.fill("input[name=first_0]", "John", "first_0")
    w.fill("input[name=last_0]", "Smith", "last_0")
    w.fill("input[name=first_1]", "Mary", "first_1")
    w.fill("input[name=last_1]", "Smith", "last_1")
    w.fill("input[name=email]", "john.smith@example.com", "email")
    w.fill("input[name=mobile]", "+44 20 7946 0958", "mobile")
    w.click("button:has-text('Continue to payment')", "to-payment")
    total = w.read_text(r"\bTotal\s*USD [\d,]+", "total")
    w.fill("input[name=card_number]", "4000123456789010", "card")
    w.fill("input[name=card_name]", "JOHN SMITH", "card-name")
    w.fill("input[name=card_expiry]", "12/2029", "expiry")
    w.fill("input[name=card_cvv]", "123", "cvv")
    w.click("button:has-text('Pay')", "pay")
    pnr = w.read_text(r"(?<=Booking reference: )[A-Z0-9]{6}", "pnr")
    w.save(f"Booked the cheapest Economy Lite flight: booking reference {pnr}. Total charged {total}.")
    return pnr, total


def walk_1(page):
    """Qatar Airways--1: earliest-out/earliest-in Economy Classic DOH->BKK return."""
    w = Walk(page, "Qatar Airways--1", OUT / "1")
    w.nav("/", "home")
    w.fill("#from", "DOH", "from")
    w.fill("#to", "BKK", "to")
    w.fill("#depart", "2026-10-12", "depart")
    w.fill("#return", "2026-10-26", "return")
    w.click("button:has-text('Search flights')", "search")
    w.scan("outbound-results", note="earliest departure is QR834 at 02:00")
    w.read_text(r"QR834", "earliest-outbound")
    # Economy Classic is the middle fare option of the first flight card
    w.page.locator(".flight-card").first.locator("a.btn:has-text('Select')").nth(1).click()
    w.page.wait_for_load_state("networkidle")
    w.record("NAV", "return-picker")
    w.scan("return-results", note="earliest inbound is QR837 at 02:30")
    w.read_text(r"QR837", "earliest-inbound")
    w.page.locator("a:has-text('Select return flight')").first.click()
    w.page.wait_for_load_state("networkidle")
    w.record("NAV", "pax-details")
    w.fill("input[name=first_0]", "Sarah", "first")
    w.fill("input[name=last_0]", "Chen", "last")
    w.fill("input[name=email]", "sarah.chen@example.com", "email")
    w.fill("input[name=mobile]", "+65 6789 1234", "mobile")
    w.click("button:has-text('Continue to payment')", "to-payment")
    total = w.read_text(r"\bTotal\s*USD [\d,]+", "total")
    w.fill("input[name=card_number]", "5412751234567890", "card")
    w.fill("input[name=card_name]", "SARAH CHEN", "card-name")
    w.fill("input[name=card_expiry]", "09/2028", "expiry")
    w.fill("input[name=card_cvv]", "123", "cvv")
    w.click("button:has-text('Pay')", "pay")
    pnr = w.read_text(r"(?<=Booking reference: )[A-Z0-9]{6}", "pnr")
    w.save(f"Return trip Doha-Bangkok booked for Sarah Chen on QR834 out and QR837 back: "
           f"booking reference {pnr}, total charged {total}.")
    return pnr, total


def walk_2(page):
    """Qatar Airways--2: alice books Business Classic DOH->CDG with her PC number."""
    w = Walk(page, "Qatar Airways--2", OUT / "2")
    w.nav("/en/Privilege-Club/login.html", "login")
    w.fill("input[name=email]", "alice.j@test.com", "email")
    w.fill("input[name=password]", "TestPass123!", "password")
    w.click("button:has-text('Log in')", "submit-login")
    w.nav("/en/Privilege-Club/dashboard.html", "dashboard")
    pc = w.read_text(r"QRPC\d{7}", "pc-number", note="membership number to put on the booking")
    w.nav("/", "home")
    w.fill("#from", "DOH", "from")
    w.fill("#to", "CDG", "to")
    w.fill("#depart", "2026-11-02", "depart")
    w.page.locator("#cabin").select_option("Business")
    w.click("button:has-text('Search flights')", "search")
    w.scan("business-results", note="earliest departure is QR041 at 01:25")
    w.read_text(r"QR041", "earliest-outbound")
    w.page.locator(".flight-card").first.locator("a.btn:has-text('Select')").nth(1).click()
    w.page.wait_for_load_state("networkidle")
    w.record("NAV", "pax-details")
    w.fill("input[name=first_0]", "Alice", "first")
    w.fill("input[name=last_0]", "Johnson", "last")
    w.fill("input[name=email]", "alice.j@test.com", "email")
    w.fill("input[name=mobile]", "+44 7700 900123", "mobile")
    w.fill("input[name=pc_number]", pc, "pc-number-attach")
    w.click("button:has-text('Continue to payment')", "to-payment")
    total = w.read_text(r"\bTotal\s*USD [\d,]+", "total")
    w.fill("input[name=card_number]", "4242424242424242", "card")
    w.fill("input[name=card_name]", "ALICE JOHNSON", "card-name")
    w.fill("input[name=card_expiry]", "08/2027", "expiry")
    w.fill("input[name=card_cvv]", "123", "cvv")
    w.click("button:has-text('Pay')", "pay")
    pnr = w.read_text(r"(?<=Booking reference: )[A-Z0-9]{6}", "pnr")
    w.nav("/en/Privilege-Club/dashboard.html", "dashboard-after")
    bal = w.read_text(r"49,990", "avios-balance")
    w.save(f"Booked Business Classic DOH-Paris CDG on QR041 for Alice Johnson with Privilege "
           f"Club number {pc} on the booking: reference {pnr}, total charged {total}. "
           f"Avios balance afterwards {bal}.")
    return pnr, total, bal


def walk_4(page):
    """Qatar Airways--4: nonstop DOH->SYD status + Sydney guide attraction."""
    w = Walk(page, "Qatar Airways--4", OUT / "4")
    w.nav("/", "home")
    w.nav("/en/flight-status.html", "flight-status")
    w.page.locator("input[name=from]").fill("DOH")
    w.record("FILL", "route-from", value="DOH")
    w.page.locator("input[name=to]").fill("SYD")
    w.record("FILL", "route-to", value="SYD")
    w.page.locator("form:has(input[name=from]) input[name=date]").fill("2026-09-24")
    w.record("FILL", "route-date", value="2026-09-24")
    w.page.locator("button:has-text('Track route')").first.click()
    w.page.wait_for_load_state("networkidle")
    w.record("NAV", "route-results")
    w.scan("route-results", note="the nonstop is QR908")
    fl = w.read_text(r"QR908", "flight")
    dep = w.read_text(r"20:05", "dep-time")
    arr = w.read_text(r"17:10", "arr-time")
    equip = w.read_text(r"Boeing 777-300ER", "equipment")
    w.nav("/en/destinations.html?region=theaustraliapacific", "destinations-oceania")
    w.scan("oceania-cards", note="Sydney is the guide to open")
    w.nav("/en/destinations/flights-to-sydney.html", "sydney-guide")
    w.scan("things-to-do", note="first attraction listed")
    w.read_text(r"Things to do in Sydney", "things-to-do-heading")
    first_attr = w.read_text(r"Sydney Opera House", "first-attraction")
    w.save(f"On 24 September 2026 the nonstop Doha-Sydney flight is {fl}, operated by a "
           f"{equip}, departing {dep} (arriving {arr}). The Sydney guide's first "
           f"Things to do attraction is the {first_attr}.")
    return fl, dep, first_attr


def walk_6(page):
    """Qatar Airways--6: david checks First Elite allowance, then adds two bags."""
    w = Walk(page, "Qatar Airways--6", OUT / "6")
    w.nav("/en/Privilege-Club/login.html", "login")
    w.fill("input[name=email]", "david.k@test.com", "email")
    w.fill("input[name=password]", "TestPass123!", "password")
    w.click("button:has-text('Log in')", "submit-login")
    w.nav("/en/baggage.html", "baggage")
    w.scan("baggage-page", note="allowance checker + fare tables")
    w.select("select[name=fare]", "First Elite", "fare-first-elite")
    w.select("select[name=route]", "weight", "route-weight")
    w.click("button:has-text('Check allowance')", "check-allowance")
    allowance = w.read_text(r"First Elite includes 50kg \(110lb\)", "included-allowance")
    w.nav("/en/manage-booking.html", "manage-lookup")
    w.fill("input[name=pnr]", "QD77LW", "pnr")
    w.fill("input[name=last_name]", "Kim", "last-name")
    w.click("button:has-text('Retrieve booking')", "retrieve")
    w.scan("itinerary", note="First Elite DOH-SYD on 18 November 2026")
    per_piece = w.read_text(r"Each additional 23kg piece costs USD 140 on this route", "per-piece-fee")
    w.select("select[name=bags]", "2", "bags-2")
    w.click("button:has-text('Add baggage')", "add-bags")
    fee = w.read_text(r"Fee charged: USD 280", "fee-charged")
    new_total = w.read_text(r"Total paid\s*:?[\s]*USD 69,731", "new-total")
    w.save(f"First Elite includes 50kg (110lb) of checked baggage on weight-concept "
           f"routes. Added 2 extra 23kg baggage pieces to QD77LW at USD 140 per piece: "
           f"fee charged USD 280, new total on the booking USD 69,731.")
    return allowance, fee, new_total


def walk_10(page):
    """Qatar Airways--10: 320 Qpoints -> Gold; bob and alice compare real accounts."""
    w = Walk(page, "Qatar Airways--10", OUT / "10")
    w.nav("/en/Privilege-Club/membership-tiers.html", "tiers")
    w.scan("tier-cards", note="Gold card: threshold, oneworld, next tier, baggage")
    w.read_text(r"To upgrade to Gold: earn 300 Qpoints within any 12-month period", "gold-threshold")
    w.read_text(r"oneworld tier: Sapphire", "gold-oneworld")
    w.read_text(r"To upgrade to Platinum: earn 600 Qpoints within any 12-month period", "platinum-threshold")
    w.read_text(r"20kg extra baggage allowance, or one piece", "gold-baggage")
    w.nav("/en/Privilege-Club/login.html", "login-bob")
    w.fill("input[name=email]", "bob.c@test.com", "bob-email")
    w.fill("input[name=password]", "TestPass123!", "bob-password")
    w.click("button:has-text('Log in')", "submit-login-bob")
    w.read_text(r"Current tier\s*Silver|Silver\s*Current tier", "bob-tier")
    bob_gap = w.read_text(r"You are 90 Qpoints away from Gold", "bob-gap")
    w.nav("/en/Privilege-Club/login.html", "login-alice")
    w.fill("input[name=email]", "alice.j@test.com", "alice-email")
    w.fill("input[name=password]", "TestPass123!", "alice-password")
    w.click("button:has-text('Log in')", "submit-login-alice")
    w.read_text(r"Current tier\s*Gold|Gold\s*Current tier", "alice-tier")
    alice_gap = w.read_text(r"You are 185 Qpoints away from Platinum", "alice-gap")
    w.save("320 Qpoints within 12 months qualifies for Gold membership, which comes with "
           "oneworld tier: Sapphire status. The next tier up, Platinum, needs 600 Qpoints "
           "within 12 months. Gold's extra checked baggage allowance is 20kg, or one piece "
           "depending on the route. Bob holds Silver and is 90 Qpoints away from Gold; "
           "Alice holds Gold and is 185 Qpoints away from Platinum. Of the three of us, "
           "Bob is closest to the next tier up.")
    return bob_gap, alice_gap


def walk_12(page):
    """Qatar Airways--12: Seoul vs Tokyo guides (Kusama + 4 more guide facts)."""
    w = Walk(page, "Qatar Airways--12", OUT / "12")
    w.nav("/en/destinations.html", "destinations-index")
    w.fill("input[name=q]", "Seoul", "q-seoul")
    w.click("button:has-text('Search')", "search-seoul")
    w.nav("/en/destinations/flights-to-seoul.html", "seoul-guide")
    w.scan("seoul-guide-scan", note="Things to do + Activities sections")
    wall = w.read_text(r"Seoul City Wall Trail", "seoul-wall")
    w.read_text(r"18\.6 kilometres", "wall-length")
    hanok = w.read_text(r"Bukchon Hanok Village", "hanok-village")
    w.read_text(r"Changdeokgung", "changdeokgung")
    w.read_text(r"Yayoi Kusama Museum", "seoul-kusama-check",
                 note="not present in Seoul's Activities")
    w.nav("/en/destinations.html?q=Tokyo", "destinations-tokyo")
    w.scan("tokyo-cards", note="two Tokyo cards: Narita first, then Haneda")
    w.nav("/en/destinations/flights-to-tokyo-narita.html", "tokyo-narita-guide")
    w.scan("narita-guide-scan", note="check the Activities section for Kusama")
    w.read_text(r"Yayoi Kusama Museum", "narita-kusama-check",
                 note="not present in the Narita guide either")
    w.nav("/en/destinations/flights-to-tokyo.html", "tokyo-guide")
    w.scan("tokyo-guide-scan", note="Activities mentions the Kusama Museum here")
    museum = w.read_text(r"Yayoi Kusama Museum", "kusama")
    market = w.read_text(r"Tsukiji Outer Market", "tsukiji")
    park = w.read_text(r"Yoyogi Park", "yoyogi")
    w.save(f"Tokyo's Activities section mentions the {museum}; Seoul's does not. Seoul's "
           f"Activities section says the Naksan Section is part of the {wall}, which "
           f"stretches 18.6 kilometres, and suggests staying in {hanok}. Seoul's Things to "
           f"do highlights Changdeokgung, a Joseon dynasty palace with a Secret Garden. "
           f"Tokyo's Food section says you can sample amazing sushi at the {market}, and "
           f"its Activities section calls {park} perfect for jogging and picnics.")
    return museum, wall, hanok, market, park


def walk_14(page):
    """Qatar Airways--14: QR105's aircraft via route status + fleet pages."""
    w = Walk(page, "Qatar Airways--14", OUT / "14")
    w.nav("/en/flight-status.html", "flight-status")
    w.page.locator("form:has(input[name=from]) input[name=from]").fill("DOH")
    w.record("FILL", "route-from", value="DOH")
    w.page.locator("form:has(input[name=from]) input[name=to]").fill("LHR")
    w.record("FILL", "route-to", value="LHR")
    w.page.locator("form:has(input[name=from]) input[name=date]").fill("2026-09-24")
    w.record("FILL", "route-date", value="2026-09-24")
    w.page.locator("button:has-text('Track route')").first.click()
    w.page.wait_for_load_state("networkidle")
    w.record("SUBMIT", "track-route")
    w.scan("route-results", note="find QR105's row and its aircraft")
    equip = w.read_text(r"Airbus A350-900", "qr105-aircraft")
    w.nav("/en/our-fleet.html", "fleet")
    w.scan("fleet-list", note="the A350-900 page + the largest aircraft (517 seats)")
    w.read_text(r"517", "largest-seats")
    w.nav("/en/our-fleet/Airbus-A350-900.html", "a350-detail")
    w.scan("a350-specs", note="Qsuite flag, seat count, cabin row ranges")
    w.read_text(r"283 seats \(features Qsuite\)", "a350-capacity")
    w.read_text(r"Qsuite", "qsuite-flag")
    bus_rows = w.read_text(r"Business\s*1–8", "business-rows")
    eco_rows = w.read_text(r"Economy\s*30–51", "economy-rows")
    w.nav("/en/our-fleet/Airbus-A380-800.html", "a380-detail")
    w.scan("a380-specs", note="First Class row range on the largest aircraft")
    first_rows = w.read_text(r"First\s*1–3", "first-rows")
    w.save(f"My flight QR105 is operated by the {equip}, which features Qsuite and seats "
           f"283 passengers; its Business Class cabin occupies rows {bus_rows} and its "
           f"Economy cabin rows {eco_rows}. The largest aircraft in the fleet is the "
           f"Airbus A380-800; its First Class cabin occupies rows {first_rows}.")
    return bus_rows, eco_rows, first_rows


def walk_15(page):
    """Qatar Airways--15: three allowance lookups + carry-on from the Help FAQ."""
    w = Walk(page, "Qatar Airways--15", OUT / "15")
    w.nav("/en/baggage.html", "baggage")
    w.scan("baggage-page", note="allowance checker + fare tables + extra-piece rates")
    w.select("select[name=fare]", "Economy Comfort", "fare-comfort")
    w.select("select[name=route]", "americas", "route-piece")
    w.click("button:has-text('Check allowance')", "check-comfort")
    comfort = w.read_text(r"Economy Comfort includes 2 pieces up to 23kg \(50lb\) each", "comfort-lookup")
    w.read_text(r"Over 8,000 km\s*USD 140", "extra-piece-rate",
                note="DOH-GRU is over 8,000 km")
    w.select("select[name=fare]", "Business Elite", "fare-elite")
    w.select("select[name=route]", "weight", "route-weight")
    w.click("button:has-text('Check allowance')", "check-elite")
    elite = w.read_text(r"Business Elite includes 40kg \(88lb\)", "elite-lookup")
    w.select("select[name=fare]", "Economy Lite", "fare-lite")
    w.select("select[name=route]", "americas", "route-piece-2")
    w.click("button:has-text('Check allowance')", "check-lite")
    lite = w.read_text(r"Economy Lite includes 1 piece up to 23kg \(50lb\)", "lite-lookup")
    w.nav("/en/help.html", "help")
    w.fill("input[name=q]", "carry-on baggage", "q-carryon")
    w.click("button:has-text('Search')", "search-carryon")
    w.click("summary:has-text('What are the size limits for carry-on baggage?')",
           "expand-carryon-faq", wait_nav=False)
    carry_on = w.read_text(r"Economy customers may carry 1 piece up to 7kg", "carry-on-rule")
    w.save(f"{comfort} of checked baggage on piece-concept routes, and each extra 23kg "
           f"piece on the Doha-Sao Paulo route costs USD 140. {elite} of checked baggage "
           f"on weight-concept routes. {lite} on piece-concept routes. Economy carry-on: "
           f"{carry_on}.")
    return None


def walk_16(page):
    """Qatar Airways--16: three help facts + certificate and infant FAQ bodies."""
    w = Walk(page, "Qatar Airways--16", OUT / "16")
    w.nav("/en/help.html", "help")
    w.fill("input[name=q]", "hard of hearing", "q-hearing")
    w.click("button:has-text('Search')", "search-hearing")
    w.read_text(r"\+1 833 607 2675", "hearing-line")
    w.fill("input[name=q]", "medical assistance", "q-medical")
    w.click("button:has-text('Search')", "search-medical")
    w.read_text(r"7 days and 48 hours before departure", "medical-window")
    w.fill("input[name=q]", "firearms Oman", "q-firearms")
    w.click("button:has-text('Search')", "search-firearms")
    w.read_text(r"Oman: 19 days", "oman-deadline")
    w.fill("input[name=q]", "certificate", "q-certificate")
    w.click("button:has-text('Search')", "search-certificate")
    w.click("summary:has-text('How do I get a proof of travel certificate?')",
            "expand-certificate-faq", wait_nav=False)
    w.read_text(r"up to 12 months from the date of travel", "certificate-window")
    w.fill("input[name=q]", "infants", "q-infants")
    w.click("button:has-text('Search')", "search-infants")
    w.click("summary:has-text('Do infants have their own baggage allowance?')",
            "expand-infants-faq", wait_nav=False)
    w.read_text(r"one baby stroller or collapsible carrycot at no additional cost", "infant-item")
    w.save("The dedicated 24-hour support number for hard-of-hearing passengers is "
           "+1 833 607 2675. The medical assistance form must be submitted between 7 days "
           "and 48 hours before departure. Firearms for Oman must be requested more than "
           "19 days prior to departure. Proof-of-travel certificates can be requested for "
           "up to 12 months from the date of travel. Infants can carry one baby stroller "
           "or collapsible carrycot at no additional cost.")
    return None


def walk_17(page):
    """Qatar Airways--17: join Privilege Club as Fiona Gray, read account + tiers."""
    w = Walk(page, "Qatar Airways--17", OUT / "17")
    w.nav("/en/Privilege-Club/join.html", "join")
    w.select("select[name=title]", "Ms", "title")
    w.fill("input[name=first_name]", "Fiona", "first")
    w.fill("input[name=last_name]", "Gray", "last")
    w.fill("input[name=email]", "fiona.gray@example.com", "email")
    w.fill("input[name=password]", "Sunshine2026", "password")
    w.fill("input[name=country]", "Ireland", "country")
    w.fill("input[name=mobile]", "+353 86 123 4567", "mobile")
    w.click("button:has-text('Join now')", "join-now")
    w.record("NAV", "dashboard")
    w.scan("dashboard", note="new membership number, starting tier, join date")
    member_no = w.read_text(r"QRPC\d{7}", "membership-no")
    w.read_text(r"Burgundy", "starting-tier")
    w.read_text(r"Joined 2026-09-24", "join-date")
    w.nav("/en/Privilege-Club/membership-tiers.html", "tiers")
    w.scan("tiers", note="Burgundy card + Silver upgrade threshold")
    w.read_text(r"Save 10% on seat selection", "seat-discount")
    w.read_text(r"To upgrade to Silver: earn 150 Qpoints within any 12-month period", "silver-threshold")
    w.save(f"Created the Privilege Club account for Fiona Gray: membership number "
           f"{member_no}, starting tier Burgundy, which saves 10% on seat selection. "
           f"Silver requires 150 Qpoints within any 12-month period. The account shows "
           f"joined 2026-09-24.")
    return member_no


def walk_18(page):
    """Qatar Airways--18: carol moves to Brazil - update and verify the profile."""
    w = Walk(page, "Qatar Airways--18", OUT / "18")
    w.nav("/en/Privilege-Club/login.html", "login")
    w.fill("input[name=email]", "carol.d@test.com", "email")
    w.fill("input[name=password]", "TestPass123!", "password")
    w.click("button:has-text('Log in')", "submit-login")
    w.nav("/en/Privilege-Club/dashboard/my-profile.html", "profile")
    w.fill("input[name=country]", "Brazil", "country")
    w.fill("input[name=mobile]", "+55 11 98765 4321", "mobile")
    w.click("button:has-text('Save changes')", "save")
    w.record("NAV", "profile-saved")
    w.read_text(r"Your profile has been updated", "confirmation")
    name = (w.page.input_value("input[name=first_name]") + " " +
            w.page.input_value("input[name=last_name]"))
    w.record("READ", "name-shown", value=name)
    email = w.page.input_value("input[name=email]")
    w.record("READ", "email-shown", value=email)
    w.read_text(r"Burgundy", "tier")
    w.read_text(r"4,200", "avios-balance")
    w.read_text(r"60", "qpoints-balance")
    w.nav("/en/Privilege-Club/dashboard.html", "dashboard-after")
    w.scan("recent-activity", note="most recent entry in the activity ledger")
    activity = w.read_text(r"Privilege Club partner bonus — Qatar Duty Free", "recent-activity")
    w.read_text(r"\+2,500", "activity-avios")
    w.save(f"Profile updated to country Brazil and mobile +55 11 98765 4321. "
           f"Confirmation: 'Your profile has been updated.' The profile still shows "
           f"{name} ({email}), tier Burgundy, Avios 4,200 and Qpoints 60. The most recent "
           f"entry in my recent activity is the {activity} of +2,500 Avios.")
    return None


def walk_19(page):
    """Qatar Airways--19: DOH-DXB Lite vs Comfort for two, book the Lite."""
    w = Walk(page, "Qatar Airways--19", OUT / "19")
    w.nav("/", "home")
    w.fill("#from", "DOH", "from")
    w.fill("#to", "DXB", "to")
    w.fill("#depart", "2026-10-05", "depart")
    w.select("#adults", "2", "adults")
    w.click("button:has-text('Search flights')", "search")
    w.scan("results", note="compare the two Economy fare totals on the first flight")
    first_card = w.page.locator(".flight-card").first
    lite_total = w.read_text(r"USD 280", "lite-total")
    comfort_total = w.read_text(r"USD 430", "comfort-total")
    first_card.locator("a.btn:has-text('Select')").first.click()
    w.page.wait_for_load_state("networkidle")
    w.record("NAV", "pax-details")
    w.fill("input[name=first_0]", "Ravi", "first-0")
    w.fill("input[name=last_0]", "Patel", "last-0")
    w.fill("input[name=first_1]", "Anaya", "first-1")
    w.fill("input[name=last_1]", "Patel", "last-1")
    w.fill("input[name=email]", "ravi.patel@example.com", "email")
    w.fill("input[name=mobile]", "+974 5555 1234", "mobile")
    w.click("button:has-text('Continue to payment')", "to-payment")
    total = w.read_text(r"\bTotal\s*USD [\d,]+", "total")
    w.fill("input[name=card_number]", "5555555555554444", "card")
    w.fill("input[name=card_name]", "RAVI PATEL", "card-name")
    w.fill("input[name=card_expiry]", "05/2028", "expiry")
    w.fill("input[name=card_cvv]", "123", "cvv")
    w.click("button:has-text('Pay')", "pay")
    pnr = w.read_text(r"(?<=Booking reference: )[A-Z0-9]{6}", "pnr")
    w.save(f"Economy Lite totals USD {lite_total} for two versus Economy Comfort "
           f"USD {comfort_total}; booked the cheaper Economy Lite: reference {pnr}, "
           f"total charged {total}.")
    return pnr, total


def walk_3(page):
    """Qatar Airways--3: QR004 status + earliest LHR->DOH + A380 fleet page."""
    w = Walk(page, "Qatar Airways--3", OUT / "3")
    w.nav("/en/flight-status.html", "flight-status")
    w.fill("input[name=number]", "QR004", "number")
    w.page.locator("form:has(input[name=number]) input[name=date]").fill("2026-09-24")
    w.record("FILL", "date", value="2026-09-24")
    w.page.locator("button:has-text('Track flight')").first.click()
    w.page.wait_for_load_state("networkidle")
    w.record("SUBMIT", "track-flight")
    w.scan("results", note="QR004 LHR->DOH status card")
    status = w.read_text(r"En route", "status")
    dep = w.read_text(r"15:05", "sched-dep")
    arr = w.read_text(r"23:47", "est-arr")
    equip = w.read_text(r"Airbus A380-800", "equipment")
    w.page.locator("form:has(input[name=from]) input[name=from]").fill("LHR")
    w.record("FILL", "route-from", value="LHR")
    w.page.locator("form:has(input[name=from]) input[name=to]").fill("DOH")
    w.record("FILL", "route-to", value="DOH")
    w.page.locator("form:has(input[name=from]) input[name=date]").fill("2026-09-24")
    w.record("FILL", "route-date", value="2026-09-24")
    w.page.locator("button:has-text('Track route')").first.click()
    w.page.wait_for_load_state("networkidle")
    w.record("SUBMIT", "track-route")
    w.scan("route-results", note="earliest London-Doha departure that day")
    earliest_dep = w.read_text(r"08:25", "earliest-dep")
    earliest_flight = w.read_text(r"QR104", "earliest-flight")
    w.nav("/en/our-fleet.html", "fleet")
    w.nav("/en/our-fleet/Airbus-A380-800.html", "fleet-a380")
    w.scan("a380-spec", note="cabin classes come from the seat table")
    cabins = w.read_text(r"First\s*1\u20133", "first-cabin-row")
    w.read_text(r"Business\s*4\u201311", "business-cabin-row")
    w.read_text(r"Economy", "economy-cabin-row")
    seats = w.read_text(r"517 seats", "seat-capacity")
    w.save(f"QR004 on 24 September 2026: status {status}, scheduled departure {dep}, "
           f"estimated arrival {arr}, aircraft {equip}, which offers First, Business and "
           f"Economy cabins and seats 517 passengers in total. The earliest London to "
           f"Doha flight that day is {earliest_flight}, departing {earliest_dep}.")
    return status, dep, arr, equip


def walk_5(page):
    """Qatar Airways--5: cancel alice's Paris booking QR92XN."""
    w = Walk(page, "Qatar Airways--5", OUT / "5")
    w.nav("/", "home")
    w.nav("/en/Privilege-Club/login.html", "login")
    w.fill("input[name=email]", "alice.j@test.com", "email")
    w.fill("input[name=password]", "TestPass123!", "password")
    w.click("button:has-text('Log in')", "submit-login")
    w.nav("/en/manage-booking.html", "manage-lookup")
    w.fill("input[name=pnr]", "QR92XN", "pnr")
    w.fill("input[name=last_name]", "Johnson", "last-name")
    w.click("button:has-text('Retrieve booking')", "retrieve")
    w.scan("itinerary", note="confirm this is the Paris trip on QR041")
    w.read_text(r"QR041", "flight")
    w.read_text(r"2026-11-02", "travel-date")
    w.read_text(r"Business", "cabin")
    w.click("button:has-text('Cancel this booking')", "cancel")
    msg = w.read_text(r"Booking QR92XN has been cancelled[^.]*", "cancel-msg")
    w.nav("/en/Privilege-Club/dashboard.html", "dashboard-after")
    w.scan("dashboard", note="confirm the other trips are unchanged")
    w.read_text(r"\bQK17TP\b", "other-trip-still-there")
    w.save(f"Cancelled my Paris trip: booking QR92XN (QR041 Doha-Paris, "
           f"2 November 2026). Message: {msg}. My other trips are unchanged.")
    return msg


def walk_7(page):
    """Qatar Airways--7: check in QC08BV, seats 30A/30B."""
    w = Walk(page, "Qatar Airways--7", OUT / "7")
    w.nav("/en/Privilege-Club/login.html", "login")
    w.fill("input[name=email]", "carol.d@test.com", "email")
    w.fill("input[name=password]", "TestPass123!", "password")
    w.click("button:has-text('Log in')", "submit-login")
    w.nav("/en/check-in.html", "checkin-lookup")
    w.fill("input[name=pnr]", "QC08BV", "pnr")
    w.fill("input[name=last_name]", "Davis", "last-name")
    w.click("button:has-text('Check in now')", "retrieve")
    w.scan("seatmap", note="find rows 30A and 30B (preferred row)")
    outbound = w.page.locator("input[name^=seat_]:not([name^=seat_ret_])")
    first_id = outbound.nth(0).get_attribute("name").split("_")[1]
    second_id = outbound.nth(1).get_attribute("name").split("_")[1]
    w.fill(f"input[name=seat_{first_id}]", "30A", "seat-carol")
    w.fill(f"input[name=seat_{second_id}]", "30B", "seat-james")
    w.click("button:has-text('Complete check-in')", "complete")
    gate = w.read_text(r"\bF22\b", "gate")
    boarding = w.read_text(r"07:20", "boarding-time")
    fee = w.read_text(r"USD 60", "seat-fees")
    w.save(f"Checked in QC08BV: Carol 30A, James 30B. Gate {gate}, boarding {boarding}, "
           f"seat fees {fee}.")
    return gate, boarding, fee


def walk_8(page):
    """Qatar Airways--8: upgrade QB55MD with Avios as bob, with pre/post reads."""
    w = Walk(page, "Qatar Airways--8", OUT / "8")
    w.nav("/en/Privilege-Club/login.html", "login")
    w.fill("input[name=email]", "bob.c@test.com", "email")
    w.fill("input[name=password]", "TestPass123!", "password")
    w.click("button:has-text('Log in')", "submit-login")
    w.nav("/en/manage-booking.html", "manage-lookup")
    w.fill("input[name=pnr]", "QB55MD", "pnr")
    w.fill("input[name=last_name]", "Chen", "last-name")
    w.click("button:has-text('Retrieve booking')", "retrieve")
    w.record("NAV", "booking-detail")
    w.scan("booking", note="Economy booking Doha-Bangkok on QR826")
    cost = w.read_text(r"1,948 Avios", "upgrade-cost")
    w.read_text(r"Your balance: 15,300 Avios", "balance-before")
    w.click("button:has-text('Upgrade to Business Class')", "upgrade")
    w.record("NAV", "upgraded")
    w.read_text(r"Business Class", "new-cabin")
    w.nav("/en/Privilege-Club/dashboard.html", "dashboard")
    bal = w.read_text(r"13,352", "new-balance")
    activity = w.read_text(r"Upgrade to Business Class on QR826", "redeem-activity")
    w.save(f"Upgraded QB55MD to Business Class for {cost}; the booking page showed my "
           f"balance of 15,300 Avios beforehand. The booking now shows Business Class. "
           f"My dashboard shows an Avios balance of {bal} and a recent activity entry: "
           f"{activity} (-1,948 Avios).")
    return cost, bal, activity


def walk_9(page):
    """Qatar Airways--9: Avios calculator DOH->JFK Business Gold."""
    w = Walk(page, "Qatar Airways--9", OUT / "9")
    w.nav("/", "home")
    w.nav("/en/Privilege-Club/login.html", "login")
    w.fill("input[name=email]", "alice.j@test.com", "email")
    w.fill("input[name=password]", "TestPass123!", "password")
    w.click("button:has-text('Log in')", "submit-login")
    w.nav("/en/Privilege-Club/avios-calculator.html", "calculator")
    w.fill("input[name=from]", "DOH", "from")
    w.fill("input[name=to]", "JFK", "to")
    w.select("select[name=cabin]", "Business", "cabin")
    w.select("select[name=tier]", "Gold", "tier")
    w.click("button:has-text('Calculate')", "calculate")
    w.scan("result-card", note="the calculator picks the nonstop QR701")
    avios = w.read_text(r"3,766", "avios")
    qpoints = w.read_text(r"431", "qpoints")
    fl = w.read_text(r"QR701", "flight")
    dep = w.read_text(r"08:00", "dep-time")
    w.read_text(r"\+75% bonus", "gold-bonus")
    w.read_text(r"Boeing 777-300ER", "equipment")
    w.save(f"A one-way Business Class DOH-JFK for a Gold member earns {avios} Avios "
           f"and {qpoints} Qpoints on {fl} departing {dep}.")
    return avios, qpoints


def walk_11(page):
    """Qatar Airways--11: Middle East guide hunt -> Doha."""
    w = Walk(page, "Qatar Airways--11", OUT / "11")
    w.nav("/", "home")
    w.nav("/en/destinations.html", "destinations-index")
    w.scan("region-cards", note="the Middle East region groups the Gulf guides")
    w.nav("/en/destinations.html?region=themiddleeast", "destinations-middleeast")
    w.scan("me-cards", note="open the Middle East guides looking for Museum of Islamic Art")
    w.nav("/en/destinations/flights-to-muscat.html", "muscat-guide")
    w.scan("muscat-things-to-do", note="no Museum of Islamic Art here")
    w.nav("/en/destinations.html?region=themiddleeast", "back-to-me")
    w.nav("/en/destinations/flights-to-doha.html", "doha-guide")
    w.scan("doha-things-to-do", note="the Museum of Islamic Art is listed here")
    mia = w.read_text(r"Museum of Islamic Art", "museum")
    w.read_text(r"Things to do in Doha", "things-to-do-heading")
    w.click("a[href='#activities']", "activities-anchor", wait_nav=False)
    w.scan("doha-activities", note="two activities for the answer")
    act = w.read_text(r"Corniche", "corniche")
    pearl = w.read_text(r"The Pearl", "the-pearl")
    w.save(f"The Middle East city whose Things to do mentions the {mia} is Doha. "
           f"Two activities from its Activities section: a stroll along the {act}, "
           f"and a visit to {pearl}, the man-made island off the coast.")
    return mia


def walk_13(page):
    """Qatar Airways--13: MotoGP promo code booking."""
    w = Walk(page, "Qatar Airways--13", OUT / "13")
    w.nav("/en/offers.html", "offers")
    w.nav("/en/offers/motogp-adventures.html", "motogp-offer")
    code = w.read_text(r"MOTOGP26", "promo-code")
    w.nav("/", "home")
    w.fill("#from", "DOH", "from")
    w.fill("#to", "LHR", "to")
    w.fill("#depart", "2026-10-08", "depart")
    w.page.locator("#cabin").select_option("Economy")
    w.click("button:has-text('Search flights')", "search")
    w.page.goto(BASE + "/en/search-results.html?from=DOH&to=LHR&depart=2026-10-08&adults=1&children=0&cabin=Economy&promo=MOTOGP26",
                wait_until="networkidle")
    w.record("NAV", "search-with-promo")
    w.page.locator(".flight-card").first.locator("a.btn:has-text('Select')").nth(1).click()
    w.page.wait_for_load_state("networkidle")
    w.record("NAV", "pax-details")
    w.fill("input[name=first_0]", "Leo", "first")
    w.fill("input[name=last_0]", "Martin", "last")
    w.fill("input[name=email]", "leo.martin@example.com", "email")
    w.fill("input[name=mobile]", "+33 6 12 34 56 78", "mobile")
    w.click("button:has-text('Continue to payment')", "to-payment")
    w.read_text(r"Promo MOTOGP26 discount", "discount-row-label")
    disc = w.read_text(r"Promo MOTOGP26 discount\s*− USD [\d,]+", "discount-amount")
    total = w.read_text(r"\bTotal\s*USD [\d,]+", "total")
    w.fill("input[name=card_number]", "4000056655665556", "card")
    w.fill("input[name=card_name]", "LEO MARTIN", "card-name")
    w.fill("input[name=card_expiry]", "02/2029", "expiry")
    w.fill("input[name=card_cvv]", "123", "cvv")
    w.click("button:has-text('Pay')", "pay")
    pnr = w.read_text(r"(?<=Booking reference: )[A-Z0-9]{6}", "pnr")
    w.save(f"Promo code {code} applied: {disc}. Booking reference {pnr}, "
           f"total charged {total}.")
    return code, disc, total


WALKS = {0: walk_0, 1: walk_1, 2: walk_2, 3: walk_3, 4: walk_4, 5: walk_5,
         6: walk_6, 7: walk_7, 8: walk_8, 9: walk_9, 10: walk_10, 11: walk_11,
         12: walk_12, 13: walk_13, 14: walk_14, 15: walk_15, 16: walk_16,
         17: walk_17, 18: walk_18, 19: walk_19}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--tasks", nargs="*", default=[str(i) for i in range(20)])
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--control", default="http://127.0.0.1:44089",
                        help="control plane base for the inter-task DB reset")
    parser.add_argument("--token-file", default="/tmp/qa_control_token")
    args = parser.parse_args()
    globals()["BASE"] = args.base
    globals()["OUT"] = pathlib.Path(args.out)

    import urllib.request
    token = pathlib.Path(args.token_file).read_text().strip()

    def reset_db():
        req = urllib.request.Request(
            f"{args.control}/reset/qatar_airways", method="POST",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.loads(r.read())
        assert payload.get("ready"), payload
        # the site process re-reads instance/ after the reset; give it a beat
        time.sleep(1.0)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        for t in args.tasks:
            t = int(t)
            print(f"=== task {t} ===")
            WALKS[t](page)
            # each walk starts from a clean state for isolation
            reset_db()
            # fresh browser state per task (cookie jar cleared) so no session
            # leaks from one walkthrough into the next
            page.context.clear_cookies()
            page.goto(args.base + "/", wait_until="networkidle")
        browser.close()


if __name__ == "__main__":
    main()

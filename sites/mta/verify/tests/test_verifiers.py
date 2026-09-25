"""Deterministic verifier contract tests for the 20 MTA tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a
clean seed pair; stateful tasks against the seed with the exact allowed
sqlite delta); a no-op run (homepage only, empty answer, clean DB) MUST
FAIL; a wrong answer MUST FAIL; a shortcut (correct answer with homepage-only
navigation) MUST FAIL: every task's required surface is beyond the homepage.
Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks MUST FAIL on
a state-mismatch (no DB delta) and on a wrong delta. Package tampering
(task_id mismatch, off-site URLs, missing screenshots, non-done trajectory)
MUST fail closed.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are
hand-written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, PASSWORD, RunBuilder, _acquire_seed,  # noqa: E402
                       build_run, copy_db, db_one, mutate_db, noop_run,
                       run_verifier)

STATEFUL = {3, 4, 7, 8, 16, 19}
READ_ONLY = sorted(set(range(20)) - STATEFUL)

FF = "/fares-tolls/lirr-metro-north/fare-finder"
HONEST_ANSWERS = {
    0: ("The latest weekday train from Valley Stream that arrives Penn Station by 9:15 a.m. "
        "boards at 8:20 a.m. and arrives 8:59 a.m., a 39 min ride. The one-way peak fare is "
        "$13.50. No planned service changes affect the Long Beach Branch this weekend."),
    1: ("The last weekday train from Penn Station toward Ronkonkoma departs 11:55 p.m. "
        "(23:55) and arrives 1:20 a.m. The first morning train the next day departs 5:16 a.m. "
        "A one-way off-peak ticket costs $16.00."),
    2: ("14 St-Union Sq is listed as accessible for the L N Q R W platforms only (the 4 5 6 platforms are not accessible). Currently out of service: third-party escalator ES258X (14 St & 4th Ave to mezzanine), out since 09/22/2026 5:04 PM for Repair, expected back 09/25/2026 6:00 PM; no alternative is listed for it. Upcoming maintenance over the next few days: EL218 (mezzanine to L platform) and EL220 (mezzanine to downtown N/Q/R/W platform) from 09/25/2026 10:00 PM, both Maintenance windows with full replacement alternatives listed."),
    3: ("Elevator EL101 (transfer mezzanine to the Woodlawn-bound 4 platform) at 149 St-Grand Concourse is out since 09/23/2026 10:55 AM for Planned Work, estimated return 09/25/2026 10:00 PM. The accessibility pages say ADA-related complaints are filed online through the feedback form (or by calling 511, or via the MTA apps), and that you will get a case ticket number once your case is logged, which is then tracked in the MTA's CRM system. I filed the feedback report for Sam Ortiz (sam.ortiz73@example.com); the new case number is CS-26095598."),
    4: ("I filed the claim with the Subway, Bus and Staten Island Railway lost and found. The "
        "claim reference is LF-26096491. The status page says to keep your claim reference "
        "handy while Lost & Found staff update the status as the search progresses."),
    5: ("LF-26094217 (subway): status Received, a navy blue JanSport backpack with a water bottle and a gray laptop sleeve. LF-26095803 (LIRR): status In Review, a black compact umbrella with a wooden handle. LF-26096625 (Metro-North): status Matched - Pickup Pending, a beige rain jacket left on the 5:42 p.m. Hudson Line train \u2014 it is held at Metro-North's Lost and Found Facility, and the status page says to keep your claim reference handy while staff update the status as the search progresses. The subway lost-and-found page says that after you file a claim the MTA searches for your item and you receive a claim reference to track your report."),
    6: ("Bob took 8 local rides and 1 express ride this week. He has spent $24.00 toward the $35.00 subway-and-local-bus cap ($11.00 of room left) and $7.25 toward the $67.00 express-inclusive cap. The tap-and-ride page confirms the $35 and $67 weekly caps and that your first tap starts a new seven-day cap. Favorite lines: the A is rerouted in Manhattan and Downtown Brooklyn (Planned - Reroute), the E is rerouted in Manhattan (Planned - Reroute), and the 7 runs express-to-local with all Manhattan-bound 7/7X trains stopping at 74 St-Broadway. Two more subway rides on Sunday cost their normal fares ($6.00) and nothing extra \u2014 he stays under the cap."),
    7: ("Favorites updated: the Q line added, the 2 and 5 trains removed, the LIRR Babylon "
        "Branch favorite kept. Alert subscriptions updated the same way: subscribed to Q, "
        "unsubscribed from 2 and 5. Both lists confirmed on the account pages."),
    8: ("Booked the Access-A-Ride trip from 120-55 Queens Blvd, Kew Gardens to Elmhurst "
        "Hospital, 79-01 Broadway, Elmhurst on 2026-09-29 at 09:15 with a walker for a medical "
        "appointment. The booking reference is AAR-26096609 and its status in the trip list is "
        "Scheduled."),
    9: ("Ten one-way peak rides a week cost 10 x $15.25 = $152.50, versus $106.50 for the weekly ticket. Four weeks of one-way peak tickets cost $610.00 versus $299.75 for the monthly, so the monthly saves $310.25 over four weeks. Off-peak one-ways cost $11.25 each; four weeks of off-peak one-ways (40 x $11.25 = $450.00) would still cost more than the $299.75 monthly ticket."),
    10: ("The Huntington senior one-way fare is $9.00. The Poughkeepsie (Metro-North Hudson "
         "line) senior one-way fare is $14.00 — the uncle pays more, by $5.00. The reduced "
         "fare page says seniors pay $1.50 (half the $3 base fare) on subways and local buses."),
    11: ("This weekend on the LIRR Hempstead Branch: westbound trains skip Elmont-UBS Arena, Queens Village and Hollis; MTA buses accept LIRR tickets from Queens Village and Hollis to Jamaica, and Elmont-UBS Arena riders should use Bellerose station instead. On the 7 on Sunday: Flushing-bound trains skip 52 St and 69 St \u2014 use 46 St-Bliss St, Woodside-61 St or 74 St-Broadway instead. There ARE changes already in effect for the 7 right now: the Flushing-bound skip of 52 St and 69 St runs from May 25, 2026 until January 1, 2027. From the Hempstead Branch Saturday timetable, the 07:05 eastbound train serves Elmont-UBS Arena. The Belmont Park press release says the LIRR will add 17 trains serving Elmont-UBS Arena Station for the reopening Friday, and that the railroad provides 90 trains each weekday and 159 each weekend day to the station."),
    12: ("No \u2014 bikes are not allowed on LIRR rush-hour trains: weekday outbound trains departing NYC between 3 p.m. and 8 p.m. ban bikes (inbound arriving 6 a.m. to 10 a.m.), and weekday trains allow only 4 bikes each, so a weekday evening trip out falls under the rush rules. The MTA recommends the subway to Mets-Willets Point for the tennis center (or the LIRR Port Washington Branch). The bike guide says don't lock your bike to MTA property \u2014 bikes chained to MTA property are removed and delivered to the Lost Property Unit. From the 7's weekday timetable, the 18:02 evening train serves Mets-Willets Point. The US Open announcement: NYCT runs additional trains after the last match (supplemental trains run express from Mets-Willets Point), and LIRR fares between Manhattan and Mets-Willets Point are as low as $5 off-peak / $7 peak with a CityTicket."),
    13: ("The guide recommends the LIRR/AirTrain combination into Manhattan; the subway + AirTrain option costs $11.75 for most riders and the guide marks it as an accessible trip; the AirTrain fare is $8.75 on top of the subway fare. By fare finder, Jamaica to Penn Station is $7.25 one-way peak and $5.25 off-peak \u2014 the $7.25 peak fare matches the guide's peak CityTicket price."),
    14: ("The next meetings are the MTA Committee and Regular Board Meetings on Monday, September 28 and Wednesday, September 30, 2026, generally held at the MTA Board Room, 2 Broadway, 20th Floor; they are livestreamed and recordings are posted on the website. Board members include Daniel Garodnick and Janette Sadik-Khan (members); Janno Lieber is Chair and CEO. The budget page calls dedicated taxes and subsidies the largest source of operating revenue (55%). The FOIL page says the best way to submit a request is through the online portal. The September 17, 2026 press release announces the meeting dates."),
    15: ("The Interborough Express is a proposed light rail line connecting Brooklyn and Queens with 18 fully accessible stations. The September 9, 2026 press release announces that the Draft Environmental Impact Statement will be released ahead of schedule later this year and all 18 IBX stations will be fully accessible. Another active accessibility project: the station accessibility upgrades targeting 68 St-Hunter College. The most recent station accessibility upgrade press release is the 149 St-Hostos Station unveiling (September 18, 2026), and 149 St-Hostos does appear on the MTA's accessible stations list."),
    16: ("Account created for pat.gonzalez@example.net (username pat_g). Added the E train and "
         "the Metro-North Harlem Line to favorites and subscribed to E line service alerts. "
         "The OMNY card serial on the account page is OMNY-5155F7F3."),
    17: ("The MTA's current G alert (the status board shows Planned - Stops Skipped): in Brooklyn, Coney Island-bound F and Church Av-bound G trains skip 4 Av-9 St, 15 St-Prospect Park and Fort Hamilton Pkwy \u2014 so yes, the same changes affect the roommate's F. Alternatives: take the F or G to 7 Av or Church Av and transfer (or to Smith-9 Sts from the other direction). This weekend: no G between Bedford-Nostrand Avs and Court Sq (Sep 26-28), with free T403 shuttle buses between Bedford-Nostrand Avs and Court Sq. The project behind the work is the CBTC signal upgrade for the Crosstown Line (the G), covering Court Sq in Queens to Church Av in Brooklyn, with construction on the line since 2023, promising more reliable service. The first weekday G from Court Sq toward Brooklyn after 7 a.m. leaves at 7:06."),
    18: ("With E-ZPass the Queens-Midtown Tunnel toll for a two-axle car is $7.46 ($9.79 Mid-Tier); by mail it is $12.03. The Congestion Relief Zone tolling information says vehicles entering Manhattan at or below 60 Street are charged a toll that depends on the type of vehicle, the time of day, whether crossing credits apply, and the payment method; the peak-period toll for a passenger car with a valid E-ZPass is $9. The Queens-Midtown crossing counts toward the zone toll: it is one of the four tolled entries earning a crossing credit (up to $3 for passenger vehicles). Per the zone's FAQ, the crossing credit is valid only during the peak period \u2014 Monday-Friday 5 a.m.-9 p.m. and Saturday-Sunday 9 a.m.-9 p.m. \u2014 and only for vehicles using E-ZPass. Excluded roadways: the FDR Drive, West Side Highway/Route 9A, and the Hugh L. Carey Tunnel connections to West Street. E-ZPass customers should keep their current license plate on the account. Discounts and exemptions include the Low-Income Discount Plan and disability exemptions."),
    19: ("The lighting case CS-26095281 (lights out in the 21 St-Queensbridge mezzanine on the G line) is still Open. His Access-A-Ride trip this Saturday (AAR-26094599, September 26 at 9:00 a.m.) is still Scheduled. The fares pages now say that as of January 1, 2026 you can no longer buy or refill a MetroCard, and remaining value can be transferred to an OMNY Card at a Customer Service Center. I filed the report about the fare machine rejecting MetroCards; the new case number is CS-26095598, and both cases appear in his case list."),
}

WRONG_ANSWERS = {i: ("I could not find the information; the answer is 42 and $99.99 "
                     "with no further details.") for i in range(20)}


def _seed():
    return _acquire_seed()


# ---------------------------------------------------------------- honest fixtures
def honest_run(tmp: Path, index: int) -> tuple[Path, Path, Path]:
    seed = _seed()
    root = tmp / f"honest_{index:02d}"
    b = build_run(tmp, f"honest_{index:02d}", f"MTA--{index}")
    initial = copy_db(seed, root / "initial.db")
    after = copy_db(seed, root / "after.db")

    if index == 0:
        b.step("/schedules/lirr/long-beach?day=weekday&direction=1", "goto", {})
        b.step(FF + "?from=Valley+Stream&to=Penn+Station&ticket=One-Way+Peak", "goto", {})
        b.step("/planned-service-changes?mode=lirr&when=weekend", "goto", {})
    elif index == 1:
        b.step("/schedules/lirr/ronkonkoma?day=weekday", "goto", {})
        b.step(FF + "?from=Ronkonkoma&to=Penn+Station&ticket=One-Way+Off-Peak", "goto", {})
    elif index == 2:
        b.step("/station/L03", "goto", {})
        b.step("/elevator-escalator-status?show=all&station=14+St-Union+Sq", "goto", {})
        b.step("/accessibility/stations", "goto", {})
        b.step("/elevator-escalator-status?station=14+St-Union+Sq&show=all&upcoming=1", "goto", {})
    elif index == 3:
        b.step("/elevator-escalator-status?station=149+St-Grand+Concourse", "goto", {})
        b.step("/contact-us/feedback", "goto", {})
        b.fill("/contact-us/feedback", "Elevator EL101 out at 149 St-Grand Concourse", "input#subject")
        after = mutate_db(seed, root / "after.db", [(
            "INSERT INTO feedback_cases (case_ref, user_id, category, subject, message, status, "
            "created_at) VALUES ('CS-26095598', NULL, 'Elevator or escalator outage', "
            "'Elevator EL101 out at 149 St-Grand Concourse', 'The Woodlawn-bound 4 platform "
            "elevator has been out since Wednesday morning.', 'Open', "
            "'2026-09-23 19:30:00.000000')", ())])
        b.step("/accessibility/ada-complaint", "goto", {})
    elif index == 4:
        b.step("/lost-and-found/subway-bus-and-staten-island-railway/claim", "goto", {})
        b.fill("/lost-and-found/subway-bus-and-staten-island-railway/claim", "Alex Rivera", "input#contact_name")
        after = mutate_db(seed, root / "after.db", [(
            "INSERT INTO lost_claims (claim_ref, user_id, agency, date_lost, line_route, "
            "station, item_type, item_description, contact_name, contact_email, contact_phone, "
            "status, created_at) VALUES ('LF-26096491', NULL, 'nyct', '2026-09-22', '7 train', "
            "'Flushing-Main St', 'Bag', 'Green duffel bag with my running shoes inside', "
            "'Alex Rivera', 'alex.rivera1984@example.com', '555-0187', 'Received', "
            "'2026-09-23 19:35:00.000000')", ())])
    elif index == 5:
        b.step("/lost-and-found/claim/LF-26094217", "goto", {})
        b.step("/lost-and-found/claim/LF-26095803", "goto", {})
        b.step("/lost-and-found/claim/LF-26096625", "goto", {})
        b.step("/lost-and-found/metro-north-railroad", "goto", {})
        b.step("/lost-and-found/subway-bus-and-staten-island-railway", "goto", {})
    elif index == 6:
        b.login("bob.c@test.com")
        b.step("/account/omny", "goto", {})
        b.step("/fares-tolls/subway-bus/tap-and-ride", "goto", {})
        b.step("/alerts/line/A", "goto", {})
        b.step("/alerts/line/E", "goto", {})
        b.step("/alerts/line/7", "goto", {})
    elif index == 7:
        b.login("alice.j@test.com")
        b.step("/account/favorites", "goto", {})
        b.step("/account/subscriptions", "goto", {})
        alice_id = db_one(seed, "SELECT id FROM users WHERE email='alice.j@test.com'")
        after = mutate_db(seed, root / "after.db", [
            ("DELETE FROM favorites WHERE user_id=? AND service_id IN ('2','5')", (alice_id,)),
            ("DELETE FROM alert_subscriptions WHERE user_id=? AND service_id IN ('2','5')", (alice_id,)),
            ("INSERT INTO favorites (user_id, service_type, service_id, created_at) VALUES "
             "(?, 'subway', 'Q', '2026-09-23 19:40:00.000000')", (alice_id,)),
            ("INSERT INTO alert_subscriptions (user_id, email, service_type, service_id, "
             "created_at) VALUES (?, 'alice.j@test.com', 'subway', 'Q', "
             "'2026-09-23 19:41:00.000000')", (alice_id,)),
        ])
    elif index == 8:
        b.login("carol.d@test.com")
        b.step("/accessibility/access-a-ride/book", "goto", {})
        b.fill("/accessibility/access-a-ride/book", "120-55 Queens Blvd, Kew Gardens", "input#pickup")
        b.step("/account/aar", "goto", {})
        carol_id = db_one(seed, "SELECT id FROM users WHERE email='carol.d@test.com'")
        after = mutate_db(seed, root / "after.db", [(
            "INSERT INTO aar_trips (trip_ref, user_id, pickup_address, destination_address, "
            "trip_date, pickup_time, passengers, mobility_aid, purpose, status, created_at) "
            "VALUES ('AAR-26096609', ?, '120-55 Queens Blvd, Kew Gardens', 'Elmhurst Hospital, "
            "79-01 Broadway, Elmhurst', '2026-09-29', '09:15', 1, 'Walker', "
            "'Medical appointment', 'Scheduled', '2026-09-23 19:45:00.000000')", (carol_id,))])
    elif index == 9:
        b.step(FF + "?from=Hicksville&to=Penn+Station&ticket=One-Way+Peak", "goto", {})
        b.step(FF + "?from=Hicksville&to=Penn+Station&ticket=Weekly", "goto", {})
        b.step(FF + "?from=Hicksville&to=Penn+Station&ticket=Monthly", "goto", {})
        b.step(FF + "?from=Hicksville&to=Penn+Station&ticket=One-Way+Off-Peak", "goto", {})
    elif index == 10:
        b.step(FF + "?from=Huntington&to=Penn+Station&ticket=One-Way+Senior%2FDisabled%2FMedicare", "goto", {})
        b.step(FF + "?from=Poughkeepsie&to=Grand+Central&ticket=One-Way+Senior%2FDisabled%2FMedicare", "goto", {})
        b.step("/fares-tolls/subway-bus/reduced-fare", "goto", {})
    elif index == 11:
        b.step("/planned-service-changes?mode=lirr&when=weekend", "goto", {})
        b.step("/planned-service-changes?mode=subway&when=weekend", "goto", {})
        b.step("/planned-service-changes?mode=subway&when=now", "goto", {})
        b.step("/schedules/lirr/hempstead?day=saturday", "goto", {})
        b.step("/press-release/mta-best-way-get-belmont-park-historic-racetrack-reopens", "goto", {})
    elif index == 12:
        b.step("/guides/bikes", "goto", {})
        b.step("/guides/bikes/bike-regulations-lirr", "goto", {})
        b.step("/guides/stadiums/national-tennis-center-queens", "goto", {})
        b.step("/schedules/subway/7-train", "goto", {})
        b.step("/press-release/mta-and-usta-announce-added-subway-and-long-island-rail-road-service-us-open", "goto", {})
    elif index == 13:
        b.step("/guides/airports", "goto", {})
        b.step("/guides/airports/jfk", "goto", {})
        b.step(FF + "?from=Jamaica&to=Penn+Station&ticket=One-Way+Peak", "goto", {})
        b.step(FF + "?from=Jamaica&to=Penn+Station&ticket=One-Way+Off-Peak", "goto", {})
    elif index == 14:
        b.step("/transparency/board-and-committee-meetings", "goto", {})
        b.step("/transparency/leadership/board-members", "goto", {})
        b.step("/transparency/leadership/executive-leadership", "goto", {})
        b.step("/press-release/mta-committee-and-board-meetings-be-held-monday-september-28-and-wednesday-september", "goto", {})
        b.step("/budget", "goto", {})
        b.step("/transparency/foil", "goto", {})
    elif index == 15:
        b.step("/project/interborough-express", "goto", {})
        b.step("/press-release/icymi-governor-hochul-announces-interborough-express-project-design-and-environmental", "goto", {})
        b.step("/project/station-accessibility-upgrades", "goto", {})
        b.step("/press-release/mta-unveils-accessibility-upgrades-149-st-hostos-station", "goto", {})
        b.step("/accessibility/stations", "goto", {})
    elif index == 16:
        b.step("/account/register", "goto", {})
        b.fill("/account/register", "pat.gonzalez@example.net", "input#email")
        b.step("/account/favorites", "goto", {})
        b.step("/account/subscriptions", "goto", {})
        b.step("/account", "goto", {})
        after = mutate_db(seed, root / "after.db", [
            ("INSERT INTO users (email, username, display_name, password_hash, omny_serial) "
             "VALUES ('pat.gonzalez@example.net', 'pat_g', 'Pat Gonzalez', 'x', "
             "'OMNY-5155F7F3')", ()),
            ("INSERT INTO favorites (user_id, service_type, service_id, created_at) "
             "SELECT id, 'subway', 'E', '2026-09-23 19:50:00.000000' FROM users WHERE "
             "email='pat.gonzalez@example.net'", ()),
            ("INSERT INTO favorites (user_id, service_type, service_id, created_at) "
             "SELECT id, 'rail', 'Metro-North Harlem Line', '2026-09-23 19:50:00.000000' "
             "FROM users WHERE email='pat.gonzalez@example.net'", ()),
            ("INSERT INTO alert_subscriptions (user_id, email, service_type, service_id, "
             "created_at) SELECT id, 'pat.gonzalez@example.net', 'subway', 'E', "
             "'2026-09-23 19:51:00.000000' FROM users WHERE "
             "email='pat.gonzalez@example.net'", ()),
        ])
    elif index == 17:
        b.step("/alerts/line/G", "goto", {})
        b.step("/project/cbtc-signal-upgrades", "goto", {})
        b.step("/planned-service-changes?mode=subway&when=weekend", "goto", {})
        b.step("/schedules/subway/g-train?day=weekday&direction=1", "goto", {})
    elif index == 18:
        b.step("/fares-tolls/tolls", "goto", {})
        b.step("/tolls/vehicle-types", "goto", {})
        b.step("/fares-tolls/tolls/congestion-relief-zone", "goto", {})
        b.step("/fares-tolls/tolls/congestion-relief-zone/discounts-exemptions", "goto", {})
        b.step("/fares-tolls/tolls/congestion-relief-zone/about", "goto", {})
        b.step("/fares-tolls/tolls/congestion-relief-zone/e-zpass", "goto", {})
        b.step("/fares-tolls/tolls/congestion-relief-zone/faq", "goto", {})
    elif index == 19:
        b.login("david.k@test.com")
        b.step("/account/cases", "goto", {})
        b.step("/contact-us/feedback", "goto", {})
        b.fill("/contact-us/feedback", "Fare machine rejecting MetroCards at 21 St-Queensbridge", "input#subject")
        after = mutate_db(seed, root / "after.db", [(
            "INSERT INTO feedback_cases (case_ref, user_id, category, subject, message, status, "
            "created_at) VALUES ('CS-26095598', NULL, 'Station or facility', "
            "'Fare machine rejecting MetroCards at 21 St-Queensbridge', "
            "'The fare machine at 21 St-Queensbridge keeps rejecting MetroCards.', 'Open', "
            "'2026-09-23 19:55:00.000000')", ())])
        b.step("/account/aar", "goto", {})
        b.step("/fares-tolls/subway-bus", "goto", {})
    b.done(HONEST_ANSWERS[index])
    return root, initial, after


# ---------------------------------------------------------------- the tests
@pytest.mark.parametrize("index", range(20))
def test_honest_pass(tmp_path, index):
    root, initial, after = honest_run(tmp_path, index)
    out = run_verifier(index, root)
    assert out["pass"], f"honest run must pass: {out.get('reason')}"


@pytest.mark.parametrize("index", range(20))
def test_noop_fails(tmp_path, index):
    root = noop_run(tmp_path, index)
    out = run_verifier(index, root)
    assert not out["pass"], "no-op run must fail"
    assert any("final_answer_nonempty" in e["check"] for e in out["evidence"]) or \
           any("visited" in e["check"] or "navigat" in e["check"] for e in out["evidence"] if not e["ok"]), \
           "no-op must fail on identity or navigation gates"


@pytest.mark.parametrize("index", range(20))
def test_wrong_answer_fails(tmp_path, index):
    root, initial, after = honest_run(tmp_path, index)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["final_answer"] = WRONG_ANSWERS[index]
    (root / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(index, root)
    assert not out["pass"], "wrong answer must fail"


@pytest.mark.parametrize("index", range(20))
def test_shortcut_fails(tmp_path, index):
    """Correct answer, but only the homepage was visited: knowledge-shortcut."""
    seed = _seed()
    root = tmp_path / f"shortcut_{index:02d}"
    b = build_run(tmp_path, f"shortcut_{index:02d}", f"MTA--{index}")
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b.step("/", "goto", {})
    b.done(HONEST_ANSWERS[index])
    out = run_verifier(index, root)
    assert not out["pass"], "shortcut (homepage-only) must fail"


@pytest.mark.parametrize("index", READ_ONLY)
def test_readonly_mutation_fails(tmp_path, index):
    root, initial, after = honest_run(tmp_path, index)
    con = sqlite3.connect(str(after))
    con.execute("UPDATE stations SET name = name || 'x' WHERE id = (SELECT MIN(id) FROM stations)")
    con.commit()
    con.close()
    out = run_verifier(index, root)
    assert not out["pass"], "mutated after-DB must fail a read-only task"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_state_mismatch_fails(tmp_path, index):
    """Agent reports the stateful action but the DB is unchanged."""
    root, initial, after = honest_run(tmp_path, index)
    copy_db(initial, after)  # wipe the delta
    out = run_verifier(index, root)
    assert not out["pass"], "state-mismatch (no DB delta) must fail"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_wrong_delta_fails(tmp_path, index):
    """A delta exists but with the wrong content."""
    root, initial, after = honest_run(tmp_path, index)
    con = sqlite3.connect(str(after))
    if index == 3:
        con.execute("UPDATE feedback_cases SET category='Station or facility' "
                    "WHERE case_ref='CS-26095598'")
    elif index == 19:
        con.execute("UPDATE feedback_cases SET category='Train or bus service' "
                    "WHERE case_ref='CS-26095598'")
    elif index == 4:
        con.execute("UPDATE lost_claims SET agency='lirr' WHERE claim_ref='LF-26096491'")
    elif index == 7:
        con.execute("DELETE FROM favorites WHERE service_id='Q'")
    elif index == 8:
        con.execute("UPDATE aar_trips SET mobility_aid='Power wheelchair' "
                    "WHERE trip_ref='AAR-26096609'")
    elif index == 16:
        con.execute("DELETE FROM favorites WHERE service_id='E'")
    con.commit()
    con.close()
    out = run_verifier(index, root)
    assert not out["pass"], "wrong delta must fail"


def test_tampered_task_id_fails(tmp_path):
    root, initial, after = honest_run(tmp_path, 0)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["task_id"] = "MTA--19"
    (root / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(0, root)
    assert not out["pass"]


def test_offsite_url_fails(tmp_path):
    root, initial, after = honest_run(tmp_path, 0)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["steps"].append({"step": 99, "url": "https://new.mta.info/schedules",
                          "action": "goto", "params": {}})
    (root / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(0, root)
    assert not out["pass"]


def test_missing_screenshots_fail(tmp_path):
    root, initial, after = honest_run(tmp_path, 0)
    traj = json.loads((root / "trajectory.json").read_text())
    (root / "trajectory.json").write_text(json.dumps(traj))
    shutil.rmtree(root / "screenshots")
    out = run_verifier(0, root)
    assert not out["pass"]


def test_unterminated_trajectory_fails(tmp_path):
    root, initial, after = honest_run(tmp_path, 0)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    (root / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(0, root)
    assert not out["pass"]


def test_non_seed_initial_db_fails(tmp_path):
    """A doctored initial DB (not the frozen seed) must fail closed."""
    root, initial, after = honest_run(tmp_path, 9)
    con = sqlite3.connect(str(initial))
    con.execute("UPDATE rail_fares SET price = 1.00")
    con.commit()
    con.close()
    out = run_verifier(9, root)
    assert not out["pass"]


# ------------------------------------------------ r2 adversarial negatives
R1_ANSWERS = {
2: ("14 St-Union Sq is listed as accessible for the L N Q R W platforms only (the 4 5 6 platforms are "
    "not accessible). Currently out of service is escalator ES258X (14 St & 4th Ave to mezzanine), out "
    "for Repair since 09/22/2026 5:04 PM, expected back 09/25/2026 6:00 PM. The status page lists no "
    "alternative for this third-party escalator."),
3: ("Elevator EL101 (transfer mezzanine to the Woodlawn-bound 4 platform) at 149 St-Grand Concourse is "
    "out since 09/23/2026 10:55 AM for Planned Work, estimated return 09/25/2026 10:00 PM. I filed the "
    "feedback report for Sam Ortiz (sam.ortiz73@example.com); the new case number is CS-26095598."),
5: ("LF-26094217 (subway lost and found): status Received, it covers a navy blue JanSport backpack with "
    "a water bottle and a gray laptop sleeve. LF-26095803 (LIRR): status In Review, it covers a black "
    "compact umbrella with a wooden handle. The status page says to keep your claim reference handy "
    "while the search progresses."),
6: ("Bob took 8 local rides and 1 express ride this week. He has spent $24.00 toward the $35.00 "
    "subway-and-local-bus cap, so $11.00 of room is left, and $7.25 toward the $67.00 express-inclusive "
    "cap. Two more subway rides on Sunday would cost their normal fares ($6.00) and no extra."),
9: ("Ten one-way peak rides a week cost 10 x $15.25 = $152.50, versus $106.50 for the weekly ticket. "
    "Four weeks of one-way peak tickets cost $610.00 versus $299.75 for the monthly ticket, so the "
    "monthly saves $310.25 over four weeks."),
11: ("For the LIRR Hempstead Branch this weekend, westbound trains skip Elmont-UBS Arena, Queens "
     "Village and Hollis; MTA buses accept LIRR tickets from Queens Village and Hollis to Jamaica and "
     "Elmont-UBS Arena riders should use Bellerose station instead. For the 7 train on Sunday, "
     "Flushing-bound trains skip 52 St and 69 St — use 46 St-Bliss St, Woodside-61 St or 74 St-Broadway "
     "instead."),
12: ("No, bikes are not allowed on LIRR rush-hour trains: weekday outbound trains departing NYC between "
     "3 p.m. and 8 p.m. (inbound arriving 6 a.m. to 10 a.m.) ban bikes, and weekday trains allow only 4 "
     "bikes each. The MTA recommends the 7 train to Mets-Willets Point for the tennis center (or the "
     "LIRR Port Washington Branch). The bike guide says don't lock your bike at any MTA facility — "
     "bicycles chained to MTA property are removed and delivered to the Lost Property Unit."),
13: ("The guide recommends the LIRR and the AirTrain from Midtown Manhattan (or the subway + AirTrain "
     "to save on fares). The subway + AirTrain option costs $11.75 for most riders and the guide marks "
     "it as an accessible trip. The AirTrain fare added on top of the subway fare is $8.75."),
14: ("The next meetings are the MTA Committee and Regular Board Meetings on Monday, September 28 and "
     "Wednesday, September 30, 2026, typically held the fourth week of each month at the MTA Board Room, "
     "2 Broadway, 20th Floor. Board members include Daniel Garodnick and Janette Sadik-Khan (members); "
     "Janno Lieber is Chair and CEO. The September 17, 2026 press release announces the meeting dates."),
15: ("The Interborough Express is a proposed light rail line connecting Brooklyn and Queens with 18 "
     "fully accessible stations. The September 9, 2026 press release announces that the Draft "
     "Environmental Impact Statement will be released ahead of schedule later this year and all 18 IBX "
     "stations will be fully accessible. Another active accessibility project: the station accessibility "
     "upgrades targeting 68 St-Hunter College."),
17: ("The MTA's announcement is the CBTC signal-upgrade project for the Crosstown Line (the G): "
     "installation between Court Sq in Queens and Church Av in Brooklyn, with construction on the line "
     "since 2023. The current planned change skips 4 Av-9 St, 15 St-Prospect Park and Fort Hamilton Pkwy "
     "on Church Av-bound G trains — take the G to 7 Av or Church Av and transfer. The status board "
     "currently shows Planned - Stops Skipped for the G."),
18: ("For a two-axle car with E-ZPass the Queens-Midtown Tunnel toll is $7.46 ($9.79 Mid-Tier, $12.03 "
     "Tolls by Mail). The Congestion Relief Zone page says vehicles entering the zone (Manhattan at or "
     "below 60 Street) are charged a toll that depends on the type of vehicle, the time of day, whether "
     "crossing credits apply, and the payment method. Discounts and exemptions include the 50% Low-Income "
     "Discount, disability exemptions, emergency-vehicle and bus exemptions, and crossing credits."),
19: ("The lighting case CS-26095281 (lights out in the 21 St-Queensbridge mezzanine on the G line) is "
     "currently Open. I filed the new report about the fare machine rejecting MetroCards at the same "
     "station; the new case number is CS-26095598."),
}

DEEPENED = [2, 3, 5, 6, 9, 11, 12, 13, 14, 15, 17, 18, 19]
NEW_SURFACE_URLS = {
    2: ["/elevator-escalator-status?station=14+st-union+sq&show=all&upcoming=1"],
    3: ["/accessibility/ada-complaint"],
    5: ["/lost-and-found/claim/lf-26096625", "/lost-and-found/metro-north-railroad",
        "/lost-and-found/subway-bus-and-staten-island-railway"],
    6: ["/fares-tolls/subway-bus/tap-and-ride", "/alerts/line/a", "/alerts/line/e", "/alerts/line/7"],
    9: ["/fares-tolls/lirr-metro-north/fare-finder?from=hicksville&to=penn+station&ticket=one-way+off-peak"],
    11: ["/planned-service-changes?mode=subway&when=now",
         "/press-release/mta-best-way-get-belmont-park-historic-racetrack-reopens"],
    12: ["/press-release/mta-and-usta-announce-added-subway-and-long-island-rail-road-service-us-open"],
    13: ["/fares-tolls/lirr-metro-north/fare-finder?from=jamaica&to=penn+station&ticket=one-way+peak",
         "/fares-tolls/lirr-metro-north/fare-finder?from=jamaica&to=penn+station&ticket=one-way+off-peak"],
    14: ["/budget", "/transparency/foil"],
    15: ["/press-release/mta-unveils-accessibility-upgrades-149-st-hostos-station",
         "/accessibility/stations"],
    17: ["/planned-service-changes?mode=subway&when=weekend", "/schedules/subway/g"],
    18: ["/fares-tolls/tolls/congestion-relief-zone/about",
         "/fares-tolls/tolls/congestion-relief-zone/e-zpass"],
    19: ["/account/aar", "/fares-tolls/subway-bus"],
}


@pytest.mark.parametrize("index", DEEPENED)
def test_r1_answer_fails_deepened_verifier(tmp_path, index):
    """The pre-deepening honest answer lacks the new sub-ask facts: FAIL."""
    root, initial, after = honest_run(tmp_path, index)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["final_answer"] = R1_ANSWERS[index]
    (root / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(index, root)
    assert not out["pass"], "the r1 answer must fail the deepened verifier"
    failed = {e["check"] for e in out["evidence"] if not e["ok"]}
    assert any(k.startswith("answer_") for k in failed), f"expected an answer gate to fail: {failed}"


@pytest.mark.parametrize("index", DEEPENED)
def test_deepened_missing_new_navigation_fails(tmp_path, index):
    """Correct deepened answer, but the new surfaces were never opened: FAIL."""
    root, initial, after = honest_run(tmp_path, index)
    traj = json.loads((root / "trajectory.json").read_text())
    drop = NEW_SURFACE_URLS[index]
    traj["steps"] = [s for s in traj["steps"]
                     if not any(u in str(s.get("url", "")).lower() for u in drop)]
    # neutralize final_url too: the verifier counts it as a visited surface
    if any(u in str(traj.get("final_url", "")).lower() for u in drop):
        remaining = [s.get("url") for s in traj["steps"]]
        traj["final_url"] = remaining[-1] if remaining else traj.get("start_url", "/")
    (root / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(index, root)
    assert not out["pass"], "missing new-surface navigation must fail"
    failed = {e["check"] for e in out["evidence"] if not e["ok"]}
    assert any(k.startswith("visited_") for k in failed), f"expected a navigation gate to fail: {failed}"



# ------------------------------------------------ r3 adversarial negatives
# The pre-r3 (r2-era) honest answers covered every earlier sub-ask but not the
# r3 depth extensions (Hempstead weekend timetable train time at Elmont-UBS
# Arena, the 7 weekday timetable evening train at Mets-Willets Point, the CRZ
# FAQ crossing-credit validity window). They must FAIL the r3 verifiers.
R2_ANSWERS = {
    11: ("This weekend on the LIRR Hempstead Branch: westbound trains skip Elmont-UBS Arena, Queens "
         "Village and Hollis; MTA buses accept LIRR tickets from Queens Village and Hollis to Jamaica, "
         "and Elmont-UBS Arena riders should use Bellerose station instead. On the 7 on Sunday: "
         "Flushing-bound trains skip 52 St and 69 St — use 46 St-Bliss St, Woodside-61 St or "
         "74 St-Broadway instead. There ARE changes already in effect for the 7 right now: the "
         "Flushing-bound skip of 52 St and 69 St runs from May 25, 2026 until January 1, 2027. "
         "The Belmont Park press release says the LIRR will add 17 trains serving Elmont-UBS Arena "
         "Station for the reopening Friday, and that the railroad provides 90 trains each weekday "
         "and 159 each weekend day to the station."),
    12: ("No — bikes are not allowed on LIRR rush-hour trains: weekday outbound trains departing NYC "
         "between 3 p.m. and 8 p.m. ban bikes (inbound arriving 6 a.m. to 10 a.m.), and weekday trains "
         "allow only 4 bikes each, so a weekday evening trip out falls under the rush rules. The MTA "
         "recommends the subway to Mets-Willets Point for the tennis center (or the LIRR Port Washington "
         "Branch). The bike guide says don't lock your bike to MTA property — bikes chained to MTA "
         "property are removed and delivered to the Lost Property Unit. The US Open announcement: NYCT "
         "runs additional trains after the last match (supplemental trains run express from "
         "Mets-Willets Point), and LIRR fares between Manhattan and Mets-Willets Point are as low as "
         "$5 off-peak / $7 peak with a CityTicket."),
    18: ("With E-ZPass the Queens-Midtown Tunnel toll for a two-axle car is $7.46 ($9.79 Mid-Tier); "
         "by mail it is $12.03. The Congestion Relief Zone tolling information says vehicles entering "
         "Manhattan at or below 60 Street are charged a toll that depends on the type of vehicle, the "
         "time of day, whether crossing credits apply, and the payment method; the peak-period toll "
         "for a passenger car with a valid E-ZPass is $9. The Queens-Midtown crossing counts toward "
         "the zone toll: it is one of the four tolled entries earning a crossing credit (up to $3 for "
         "passenger vehicles, peak period only). Excluded roadways: the FDR Drive, West Side "
         "Highway/Route 9A, and the Hugh L. Carey Tunnel connections to West Street. E-ZPass customers "
         "should keep their current license plate on the account. Discounts and exemptions include "
         "the Low-Income Discount Plan and disability exemptions."),
}

R3_DEEPENED = [11, 12, 18]
NEW_SURFACE_URLS_R3 = {
    11: ["/schedules/lirr/hempstead?day=saturday"],
    12: ["/schedules/subway/7-train"],
    18: ["/fares-tolls/tolls/congestion-relief-zone/faq"],
}


@pytest.mark.parametrize("index", R3_DEEPENED)
def test_r2_answer_fails_r3_verifier(tmp_path, index):
    """The pre-r3 honest answer lacks the r3 sub-ask facts: FAIL."""
    root, initial, after = honest_run(tmp_path, index)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["final_answer"] = R2_ANSWERS[index]
    (root / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(index, root)
    assert not out["pass"], "the r2 answer must fail the r3 verifier"
    failed = {e["check"] for e in out["evidence"] if not e["ok"]}
    assert any(k.startswith("answer_") for k in failed), f"expected an answer gate to fail: {failed}"


@pytest.mark.parametrize("index", R3_DEEPENED)
def test_r3_missing_new_navigation_fails(tmp_path, index):
    """Correct r3 answer, but the new r3 surfaces were never opened: FAIL."""
    root, initial, after = honest_run(tmp_path, index)
    traj = json.loads((root / "trajectory.json").read_text())
    drop = NEW_SURFACE_URLS_R3[index]
    traj["steps"] = [s for s in traj["steps"]
                     if not any(u in str(s.get("url", "")).lower() for u in drop)]
    if any(u in str(traj.get("final_url", "")).lower() for u in drop):
        remaining = [s.get("url") for s in traj["steps"]]
        traj["final_url"] = remaining[-1] if remaining else traj.get("start_url", "/")
    (root / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(index, root)
    assert not out["pass"], "missing r3 new-surface navigation must fail"
    failed = {e["check"] for e in out["evidence"] if not e["ok"]}
    assert any(k.startswith("visited_") for k in failed), f"expected a navigation gate to fail: {failed}"


# ---------------------------------------------------------------- audit hardening
# The audit track's wrong-fact battery found two answer gates that accepted
# plausible-but-wrong answers. Both gates are now claim-scoped / date+time
# paired; these negatives pin the hardened behaviour.

AUDIT_WRONG_ETA_T2 = (
    "Yes, 14 St-Union Sq is listed as accessible, for the L N Q R W platforms only. Currently "
    "out: third-party escalator ES258X, out since 09/22/2026 for Repair, expected back "
    "09/28/2026 8:00 PM; no alternative is listed. Upcoming maintenance: EL218 and EL220 from "
    "09/25/2026 10:00 PM. The elevators serve: EL217 street to mezzanine, EL218 mezzanine to "
    "L, EL219 mezzanine to uptown N/Q/R/W, EL220 mezzanine to downtown N/Q/R/W."
)


def test_audit_t2_wrong_eta_time_fails(tmp_path):
    """Honest navigation, but the ETA gives the wrong date AND wrong time
    (the 09/25/2026 token only appears in the upcoming-maintenance sentence):
    the date-alone gate must not rescue it. FAIL expected."""
    root, initial, after = honest_run(tmp_path, 2)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["final_answer"] = AUDIT_WRONG_ETA_T2
    (root / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(2, root)
    assert not out["pass"], "a wrong ETA must fail the hardened gate"
    failed = {e["check"] for e in out["evidence"] if not e["ok"]}
    assert "answer_eta_0925" in failed, f"expected answer_eta_0925 to fail: {failed}"


AUDIT_SWAPPED_T5 = (
    "LF-26094217 (subway): In Review — navy blue JanSport backpack with a water bottle and a "
    "gray laptop sleeve. LF-26095803 (LIRR): Received — black compact umbrella with a wooden "
    "handle. LF-26096625 (Metro-North): Matched - Pickup Pending — beige rain jacket left on "
    "the 5:42 p.m. Hudson Line train; it is held at Metro-North's Lost & Found Facility, and "
    "the status page says to keep your claim reference handy. The subway lost-and-found page "
    "says that after you file a claim they search for the item and you receive a claim "
    "reference to track your report."
)


def test_audit_t5_swapped_claims_fail(tmp_path):
    """Honest navigation, but claim 1 and claim 2 statuses are swapped: the
    rubric makes mixing up the claims a FAIL, so the claim-scoped gates must
    reject the answer even though both status words appear somewhere."""
    root, initial, after = honest_run(tmp_path, 5)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["final_answer"] = AUDIT_SWAPPED_T5
    (root / "trajectory.json").write_text(json.dumps(traj))
    out = run_verifier(5, root)
    assert not out["pass"], "swapped claim statuses must fail"
    failed = {e["check"] for e in out["evidence"] if not e["ok"]}
    assert "answer_status_received" in failed and "answer_status_in_review" in failed, \
        f"expected both claim-scoped status gates to fail: {failed}"

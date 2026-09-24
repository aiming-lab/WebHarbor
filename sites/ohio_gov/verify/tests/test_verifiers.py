"""Deterministic verifier contract tests for the 21 Ohio.gov tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a
clean seed pair; stateful tasks against the seed with the exact allowed sqlite
delta); a no-op run (homepage only, empty answer, clean DB) MUST FAIL; a
wrong answer MUST FAIL; a shortcut (correct answer with homepage-only
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
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, RunBuilder, _acquire_seed,  # noqa: E402
                      build_run, copy_db, db_one, mutate_db, noop_run, run_verifier)

STATEFUL = {6, 7, 8, 9, 10, 18}
READ_ONLY = sorted(set(range(21)) - STATEFUL)
CREATED = "2026-09-17 12:00:00.000000"


def _seed():
    return _acquire_seed()


def _rid(db, slug):
    return db_one(db, "SELECT id FROM resources WHERE slug = ?", (slug,))


# ---------------------------------------------------------------- honest fixtures
def honest_run_00(tmp: Path):
    seed = _seed()
    root = tmp / "honest_00"
    b = build_run(tmp, "honest_00", "Ohio.gov--0")
    b.step("/jobs/resources/licenses-and-permits?q=acupuncturist", "goto", {})
    b.step("/help-center/state-directory?q=Medical+Board", "goto", {})
    b.step("/jobs/resources/licenses-and-permits?agency=Medical+Board", "goto", {})
    b.done("The acupuncturist license is issued by the Medical Board; the agency's "
           "website is med.ohio.gov and the directory lists a contact list and form "
           "for license questions. The Medical Board's State Directory entry shows 4 "
           "social media links. Filtering the licenses directory by the Medical Board "
           "shows it issues 12 licenses in total.",
           final_path="/jobs/resources/licenses-and-permits")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_01(tmp: Path):
    seed = _seed()
    root = tmp / "honest_01"
    b = build_run(tmp, "honest_01", "Ohio.gov--1")
    b.step("/help-center/phone-search?lastName=Smith&agency=Environmental+Protection", "goto", {})
    b.step("/help-center/phone-search?firstName=Aaron&lastName=Smith", "goto", {})
    b.done("The Aaron Smith at the Environmental Protection Agency can be reached at "
           "614-728-0049. The exact-name search returns 4 listings named Aaron Smith: one "
           "at the Dept of Rehab & Corrections, one at the Environmental Protection Agcy, "
           "one at the Lottery Commission, and one with no agency listed. The Aaron Smith "
           "at the Lottery Commission is 216-774-0177.",
           final_path="/help-center/phone-search")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_02(tmp: Path):
    seed = _seed()
    root = tmp / "honest_02"
    b = build_run(tmp, "honest_02", "Ohio.gov--2")
    b.step("/residents/resources/home-energy-assistance-program", "goto", {})
    b.step("/residents/resources/food-assistance", "goto", {})
    b.step("/help-center/ohio-assistant?q=help+paying+utility+bills", "goto", {})
    b.done("The HEAP one-time payment goes straight to your utility or fuel company. "
           "The Food Assistance program is also known as SNAP (food stamps), and "
           "benefits arrive on the Ohio Direction Card. The Ohio Assistant's first "
           "suggestion is the Utility Complaints resource.",
           final_path="/help-center/ohio-assistant")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_03(tmp: Path):
    seed = _seed()
    root = tmp / "honest_03"
    b = build_run(tmp, "honest_03", "Ohio.gov--3")
    b.step("/media-center", "goto", {})
    b.step("/news-and-events/all-news/odh-back-to-school-tips-aug26", "goto", {})
    b.step("/news-and-events/all-news/otso-school-transportation-safety-aug26", "goto", {})
    b.step("/news-and-events/all-news/ltgov-team-tressel-challenge-aug26", "goto", {})
    b.done("The back-to-school article was published by the Ohio Department of Health "
           "on August 10, 2026. Medical director Dr. Mary DiOrio says it is important "
           "to prepare students for the year ahead by prioritizing their health. The "
           "school transportation safety reminder was published by the Ohio Traffic "
           "Safety Office. The Team Tressel Fitness Challenge was announced by the "
           "Lt. Governor's Office, which says student participation has increased by "
           "nearly 255% since the challenge launched.",
           final_path="/news-and-events/all-news")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_04(tmp: Path):
    seed = _seed()
    root = tmp / "honest_04"
    b = build_run(tmp, "honest_04", "Ohio.gov--4")
    b.step("/news-and-events/all-news/gov.dolly-parton-day-sept26", "goto", {})
    b.step("/residents/resources/dolly-partons-imagination-library-of-ohio", "goto", {})
    b.step("/help-center/faqs/assistance-programs", "goto", {})
    b.done("Dolly Parton Day is September 25, 2026, proclaimed by Governor Mike DeWine. "
           "The program is Dolly Parton's Imagination Library of Ohio. The FAQ says the "
           "Ohio Association of Foodbanks can help you find a foodbank serving your "
           "community, and Ohio's food assistance program may also be able to help.",
           final_path="/help-center/faqs/assistance-programs")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_05(tmp: Path):
    seed = _seed()
    root = tmp / "honest_05"
    b = build_run(tmp, "honest_05", "Ohio.gov--5")
    b.step("/government/resources/ohio-facts-geography", "goto", {})
    b.step("/government/resources/ohio-facts-state-symbols", "goto", {})
    b.step("/government/resources/ohio-facts-plants-animals", "goto", {})
    b.done("On the geography page: the center point of the state is Centerburg (in Knox "
           "County), Ohio covers about 44,825 square miles, and it has more than 3,300 "
           "rivers and streams. On the state symbols page: the coat of arms shows a sheaf "
           "of wheat on the left and a bundle of 17 arrows on the right. On the plants "
           "and animals page: more than 120 types of trees grow in Ohio, you'll find more "
           "than 1,000 insect species, and the page lists more than 300,000 plant species.",
           final_path="/government/resources/ohio-facts-plants-animals")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_06(tmp: Path):
    seed = _seed()
    root = tmp / "honest_06"
    b = build_run(tmp, "honest_06", "Ohio.gov--6")
    b.login("alice.j@test.com")
    b.step("/account", "click", {"selector": "a[href='/account']"})
    b.step("/residents/resources/weather-safety", "goto", {})
    b.step("/account", "goto", {})
    b.done("The account now shows 5 saved resources. The first is Food Assistance and "
           "the last is Weather Safety.", final_path="/account")
    after = mutate_db(seed, root / "after.db", [
        ("DELETE FROM saved_resources WHERE user_id = 1 AND resource_id = "
         "(SELECT id FROM resources WHERE slug = 'college-credit-plus')", ()),
        ("INSERT INTO saved_resources (user_id, resource_id, created_at) VALUES "
         "(1, (SELECT id FROM resources WHERE slug = 'weather-safety'), ?)", (CREATED,)),
    ])
    return root, seed, after


def honest_run_07(tmp: Path):
    seed = _seed()
    root = tmp / "honest_07"
    b = build_run(tmp, "honest_07", "Ohio.gov--7")
    b.fill("/register", "maria_g", "#username")
    b.fill("/register", "maria.g@test.com", "#email")
    b.fill("/register", "OhioFan2026!", "#password")
    b.fill("/register", "OhioFan2026!", "#password2")
    b.step("/register", "click", {"selector": "button[type=submit]"}, url_after="/account")
    b.fill("/account/edit", "Maria Gonzalez", "input[name=display_name]")
    b.fill("/account/edit", "250 High St", "input[name=address_line1]")
    b.fill("/account/edit", "Columbus", "input[name=city]")
    b.fill("/account/edit", "Ohio", "input[name=state]")
    b.fill("/account/edit", "43215", "input[name=zip]")
    b.step("/account/edit", "click", {"selector": "button[type=submit]"}, url_after="/account")
    b.step("/account", "goto", {})
    b.done("The account username is maria_g. Account settings show the display name "
           "Maria Gonzalez and the mailing address 250 High St, Columbus, Ohio 43215.",
           final_path="/account")
    after = mutate_db(seed, root / "after.db", [
        ("INSERT INTO users (username, email, password_hash, display_name, first_name, "
         "last_name, phone, address_line1, city, state, zip, created_at) VALUES "
         "('maria_g', 'maria.g@test.com', 'scrypt:fixture', 'Maria Gonzalez', NULL, "
         "NULL, NULL, '250 High St', 'Columbus', 'Ohio', '43215', ?)", (CREATED,)),
    ])
    return root, seed, after


def honest_run_08(tmp: Path):
    seed = _seed()
    root = tmp / "honest_08"
    b = build_run(tmp, "honest_08", "Ohio.gov--8")
    b.step("/travel-guide", "goto", {})
    b.fill("/travel-guide", "Rosa Parks", "input[name=full_name]")
    b.fill("/travel-guide", "rosa.p@example.com", "input[name=email]")
    b.fill("/travel-guide", "12 Elm Court", "input[name=address_line1]")
    b.fill("/travel-guide", "Toledo", "input[name=city]")
    b.fill("/travel-guide", "Ohio", "input[name=state]")
    b.fill("/travel-guide", "43604", "input[name=zip]")
    b.step("/travel-guide", "select", {"selector": "select[name=format]",
                                       "value": "Standard print"})
    b.step("/travel-guide", "click", {"selector": "button[type=submit]"})
    b.fill("/travel-guide", "Sam Rivers", "input[name=full_name]")
    b.fill("/travel-guide", "sam.r@example.com", "input[name=email]")
    b.fill("/travel-guide", "8 Harbor View Dr", "input[name=address_line1]")
    b.fill("/travel-guide", "Sandusky", "input[name=city]")
    b.fill("/travel-guide", "Ohio", "input[name=state]")
    b.fill("/travel-guide", "44870", "input[name=zip]")
    b.step("/travel-guide", "select", {"selector": "select[name=format]",
                                       "value": "Large print"})
    b.step("/travel-guide", "click", {"selector": "button[type=submit]"})
    b.step("/", "goto", {})
    b.done("Order 1 confirmed: the 2026 Ohio Travel Guide will be mailed to 12 Elm "
           "Court, Toledo, Ohio 43604 (Standard print). Order 2 confirmed: it will be "
           "mailed to 8 Harbor View Dr, Sandusky, Ohio 44870 (Large print). The home page "
           "banner says you can view online, download the app, or request a copy in the "
           "mail.", final_path="/")
    after = mutate_db(seed, root / "after.db", [
        ("INSERT INTO travel_guide_requests (user_id, full_name, email, address_line1, "
         "city, state, zip, format, created_at) VALUES (NULL, 'Rosa Parks', "
         "'rosa.p@example.com', '12 Elm Court', 'Toledo', 'Ohio', '43604', "
         "'Standard print', ?)", (CREATED,)),
        ("INSERT INTO travel_guide_requests (user_id, full_name, email, address_line1, "
         "city, state, zip, format, created_at) VALUES (NULL, 'Sam Rivers', "
         "'sam.r@example.com', '8 Harbor View Dr', 'Sandusky', 'Ohio', '44870', "
         "'Large print', ?)", (CREATED,)),
    ])
    return root, seed, after


def honest_run_09(tmp: Path):
    seed = _seed()
    root = tmp / "honest_09"
    b = build_run(tmp, "honest_09", "Ohio.gov--9")
    b.step("/report-scam", "goto", {})
    b.fill("/report-scam", "Rosa Parks", "input[name=full_name]")
    b.fill("/report-scam", "rosa.p@example.com", "input[name=email]")
    b.step("/report-scam", "select", {"selector": "select[name=scam_type]",
                                      "value": "Romance scam"})
    b.fill("/report-scam", "450", "input[name=amount]")
    b.fill("/report-scam", "My grandmother lost $450 to a romance scam.",
           "textarea[name=description]")
    b.step("/report-scam", "click", {"selector": "button[type=submit]"})
    b.done("The confirmation says my consumer complaint has been submitted to the Ohio "
           "Attorney General's office and to keep my confirmation number. The dedicated "
           "romance scam hotline is 1-855-961-7226.", final_path="/report-scam")
    after = mutate_db(seed, root / "after.db", [
        ("INSERT INTO scam_reports (user_id, full_name, email, phone, scam_type, "
         "description, amount, occurred_on, created_at) VALUES (NULL, 'Rosa Parks', "
         "'rosa.p@example.com', '', 'Romance scam', 'My grandmother lost $450 to a "
         "romance scam.', '450', '', ?)", (CREATED,)),
    ])
    return root, seed, after


def honest_run_10(tmp: Path):
    seed = _seed()
    root = tmp / "honest_10"
    b = build_run(tmp, "honest_10", "Ohio.gov--10")
    b.login("bob.c@test.com")
    b.step("/alerts", "goto", {})
    b.fill("/alerts", "bob.c@test.com", "#email")
    b.step("/alerts", "select", {"selector": "#alert_type",
                                 "value": "Unemployment system"})
    b.step("/alerts", "click", {"selector": "button[type=submit]"})
    b.fill("/alerts", "bob.c@test.com", "#email")
    b.step("/alerts", "select", {"selector": "#alert_type",
                                 "value": "Outage notifications"})
    b.step("/alerts", "click", {"selector": "button[type=submit]"})
    b.step("/account", "goto", {})
    b.done("The Ohio Benefits self-service portal will be unavailable Sunday, September "
           "20 from 2:00 AM to 6:00 AM for scheduled maintenance. After subscribing to "
           "Unemployment system and Outage notifications alerts, the account page lists 3 "
           "alert subscriptions. The alert about BMV online services is titled 'BMV "
           "Online Services: scheduled outage'.", final_path="/account")
    after = mutate_db(seed, root / "after.db", [
        ("INSERT INTO alert_subscriptions (user_id, email, alert_type, created_at) "
         "VALUES (2, 'bob.c@test.com', 'Unemployment system', ?)", (CREATED,)),
        ("INSERT INTO alert_subscriptions (user_id, email, alert_type, created_at) "
         "VALUES (2, 'bob.c@test.com', 'Outage notifications', ?)", (CREATED,)),
    ])
    return root, seed, after


def honest_run_11(tmp: Path):
    seed = _seed()
    root = tmp / "honest_11"
    b = build_run(tmp, "honest_11", "Ohio.gov--11")
    b.step("/help-center/faqs/government", "goto", {})
    b.step("/help-center/faqs/new-residents", "goto", {})
    b.step("/help-center/faqs/driving-and-transportation", "goto", {})
    b.done("The Bureau of Vital Statistics can provide copies of birth certificates and "
           "similar documents (death certificates, adoption records). The Ohio "
           "Legislative Service Commission helps residents search Ohio's laws. The "
           "Government Questions category lists 16 questions. The New Resident Questions "
           "category lists 6 questions; new residents must transfer an out-of-state "
           "driver license and vehicle registration within 30 days of establishing "
           "residency, and can register to vote via Ohio's Online Voter Registration "
           "System. In the Driving Questions category, the Ohio Department of Public "
           "Safety helps you find your local BMV office.",
           final_path="/help-center/faqs/driving-and-transportation")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_12(tmp: Path):
    seed = _seed()
    root = tmp / "honest_12"
    b = build_run(tmp, "honest_12", "Ohio.gov--12")
    b.step("/search?search_query=tax", "goto", {})
    b.step("/search?search_query=tax&t=Licenses", "click",
           {"selector": "a:has-text('Licenses')"})
    b.step("/search?search_query=tax&t=FAQs", "click",
           {"selector": "a:has-text('FAQs')"})
    b.step("/help-center/faqs/taxes", "click", {"selector": ".search-result-title a"})
    b.step("/business/resources/sales-and-use-tax", "goto", {})
    b.done("The search reports 24 Resources results and 6 FAQs results for 'tax'. The "
           "first Licenses result is Vendor's License or Seller's Use Tax Account, "
           "issued by Taxation. The first FAQ says the Department of Taxation's online "
           "services let you file your individual income tax returns, check your refund "
           "status, and make payments. The Sales and Use Tax resource says the tax "
           "applies to the retail sale, lease, and rental of personal property and the "
           "sale of selected services.",
           final_path="/business/resources/sales-and-use-tax")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_13(tmp: Path):
    seed = _seed()
    root = tmp / "honest_13"
    b = build_run(tmp, "honest_13", "Ohio.gov--13")
    b.step("/residents/topic-hubs/top-services", "goto", {})
    b.step("/residents/resources/unclaimed-funds", "goto", {})
    b.step("/residents/home-and-community/money-and-finance/money-and-finance", "goto", {})
    b.done("The Top Services hub lists 13 resources; the first three are Birth and Death "
           "Certificates, Business Search, and Cash Assistance (Ohio Works First). The "
           "Department of Commerce helps Ohioans claim funds held in their names; "
           "unclaimed funds include old bank accounts and forgotten rent or utility "
           "deposits. The Money & Finance hub lists 8 resources and the first one is "
           "Annual Sales Tax Holiday.", final_path="/residents/resources/unclaimed-funds")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_14(tmp: Path):
    seed = _seed()
    root = tmp / "honest_14"
    b = build_run(tmp, "honest_14", "Ohio.gov--14")
    b.step("/help-center/ohio-assistant?q=how+do+i+replace+a+lost+driver+license", "goto", {})
    b.step("/residents/resources/driver-licenses", "goto", {})
    b.step("/residents/resources/driver-training", "goto", {})
    b.step("/help-center/state-directory?q=Bureau+of+Motor+Vehicles", "goto", {})
    b.done("The Ohio Assistant returned Driver Licenses, Driver Training, and Hunting "
           "and Fishing Licenses. The Driver Licenses resource says an Ohio driver "
           "license is also a form of state-issued identification, and with proper "
           "documents it can serve as a federally compliant Real ID for air travel and "
           "access to federal facilities. The Driver Training resource says the Ohio "
           "Traffic Safety Office provides driver training information. The State "
           "Directory lists 'contact list and chat' for the Bureau of Motor Vehicles.",
           final_path="/help-center/state-directory")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_15(tmp: Path):
    seed = _seed()
    root = tmp / "honest_15"
    b = build_run(tmp, "honest_15", "Ohio.gov--15")
    b.step("/help-center/state-directory?q=Accountancy", "goto", {})
    b.step("/help-center/state-directory?q=Lottery", "goto", {})
    b.step("/help-center/state-directory?q=Taxation", "goto", {})
    b.done("The Accountancy Board's website is acc.ohio.gov, its contact method is a "
           "contact form, and its entry lists Facebook, YouTube, and LinkedIn. "
           "Searching 'Lottery' returns the Lottery agency with contact method "
           "'contact list and form'. Searching 'Taxation' shows an entry listing "
           "Facebook, YouTube, and LinkedIn with contact method 'contact list'.",
           final_path="/help-center/state-directory")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_16(tmp: Path):
    seed = _seed()
    root = tmp / "honest_16"
    b = build_run(tmp, "honest_16", "Ohio.gov--16")
    b.step("/media-center?source=Ohio+Department+of+Natural+Resources", "goto", {})
    b.step("/news-and-events/all-news/odnr-fall-hunting-seasons-start-aug26", "goto", {})
    b.step("/news-and-events/all-news/odnr-buckeye-state-nursery-sept26", "goto", {})
    b.done("The ODNR filter shows 2 articles: 'Buy Ohio-Grown Trees Online from the "
           "Buckeye Nursery' and 'Get Ready for Ohio's Fall Hunting Seasons'. Squirrel "
           "and dove seasons start September 1; hunters are reminded to check the "
           "current regulations for changes to season dates and daily limits. The "
           "article was published August 26, 2026. The Buckeye State Tree Nursery is in "
           "Zanesville, and customers can either pick up their orders at the nursery or "
           "have seedlings shipped directly to them.",
           final_path="/news-and-events/all-news")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_17(tmp: Path):
    seed = _seed()
    root = tmp / "honest_17"
    b = build_run(tmp, "honest_17", "Ohio.gov--17")
    b.step("/news-and-events/all-news/bmv-ohio-mobile-id-in-google-wallet-aug26", "goto", {})
    b.step("/news-and-events/all-news/jfs-snap-farmers-markets-aug26", "goto", {})
    b.step("/news-and-events/all-news/ema-preparedness-month-aug26", "goto", {})
    b.done("The Ohio ID Google Wallet announcement came from the Ohio Bureau of Motor "
           "Vehicles on August 31, 2026; when an ID is displayed the user can review "
           "exactly what data is shared. At participating farmers' markets, look for "
           "signs saying that SNAP, EBT, or Direction Card are accepted. The Ohio "
           "Preparedness Month news was published by the Ohio Emergency Management "
           "Agency; its executive director Sima Merick says the goal is to encourage "
           "families to stay informed, stay connected, and take simple steps that can "
           "help them be prepared for emergencies.",
           final_path="/news-and-events/all-news")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_18(tmp: Path):
    seed = _seed()
    root = tmp / "honest_18"
    b = build_run(tmp, "honest_18", "Ohio.gov--18")
    b.login("carol.d@test.com")
    b.step("/account/edit", "goto", {})
    b.fill("/account/edit", "(513) 555-0200", "input[name=phone]")
    b.fill("/account/edit", "Cleveland", "input[name=city]")
    b.step("/account/edit", "click", {"selector": "button[type=submit]"}, url_after="/account")
    b.done("Account settings now show the phone (513) 555-0200 and the city Cleveland. "
           "The account shows 5 saved resources. There are no consumer complaints — "
           "none filed.", final_path="/account")
    after = mutate_db(seed, root / "after.db", [
        ("UPDATE users SET phone = '(513) 555-0200', city = 'Cleveland' WHERE id = 3", ()),
    ])
    return root, seed, after


def honest_run_19(tmp: Path):
    seed = _seed()
    root = tmp / "honest_19"
    b = build_run(tmp, "honest_19", "Ohio.gov--19")
    b.step("/jobs/resources/licenses-and-permits?q=barber", "goto", {})
    b.step("/jobs/resources/licenses-and-permits?q=auctioneer", "goto", {})
    b.step("/jobs/resources/licenses-and-permits?q=notary", "goto", {})
    b.step("/help-center/faqs/professional-licenses", "goto", {})
    b.done("The barbers license is issued by the Cosmetology and Barber Board, the "
           "auctioneer license by the Agriculture department, and the notary public "
           "commission by the Secretary of State. The FAQ says the eLicense Ohio "
           "website lets you verify someone's professional license.",
           final_path="/help-center/faqs/professional-licenses")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


def honest_run_20(tmp: Path):
    seed = _seed()
    root = tmp / "honest_20"
    b = build_run(tmp, "honest_20", "Ohio.gov--20")
    b.step("/search?search_query=hunting", "goto", {})
    b.step("/residents/resources/hunting-and-fishing-licenses", "goto", {})
    b.step("/help-center/faqs/hunting-and-fishing", "goto", {})
    b.done("The search finds 2 Resources results for 'hunting'. The Hunting and Fishing "
           "Licenses resource lets residents purchase hunting and fishing licenses, "
           "report game harvests, find training, and more through Ohio's Wildlife "
           "Licensing System. The Hunting & Fishing Questions category lists 4 "
           "questions. You can buy licenses at a local license agent or online via "
           "Ohio's Wildlife Licensing System (or the HuntFish OH mobile app). The "
           "hunting-season answer points to the Ohio Division of Wildlife's listing of "
           "season dates, and the safe-to-eat fish answer names Ohio's sport fish "
           "consumption advisory.", final_path="/help-center/faqs/hunting-and-fishing")
    after = copy_db(seed, root / "after.db")
    return root, seed, after


HONEST = {n: globals()[f"honest_run_{n:02d}"] for n in range(21)}


# ---------------------------------------------------------------- tests
@pytest.mark.parametrize("index", range(21))
def test_honest_pass(tmp_path, index):
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"], f"honest run must PASS: {verdict}"


@pytest.mark.parametrize("index", range(21))
def test_noop_fails(tmp_path, index):
    run_dir = noop_run(tmp_path, index)
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"], f"no-op run must FAIL: {verdict}"
    assert verdict["reason"] == "final_answer_nonempty" or not verdict["pass"]


@pytest.mark.parametrize("index", range(21))
def test_wrong_answer_fails(tmp_path, index):
    """Honest navigation + honest DB, but the final answer is wrong/empty."""
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = "I could not find the information."
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"], f"wrong answer must FAIL: {verdict}"
    assert verdict["reason"].startswith("answer_")


@pytest.mark.parametrize("index", range(21))
def test_shortcut_fails(tmp_path, index):
    """Correct answer but homepage-only navigation: knowledge shortcut = FAIL."""
    seed = _seed()
    run_dir, _, after = HONEST[index](tmp_path)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    # rebuild the same run with ONLY the homepage step, same final answer
    b = build_run(tmp_path, f"shortcut_{index:02d}", f"Ohio.gov--{index}")
    b.step("/", "goto", {})
    b.done(traj["final_answer"], final_path="/")
    copy_db(seed, b.root / "initial.db")
    copy_db(after, b.root / "after.db")
    verdict = run_verifier(index, b.root)
    assert not verdict["pass"], f"shortcut must FAIL: {verdict}"
    assert verdict["reason"].startswith(("visited_", "searched_", "filtered_", "asked_",
                                         "looked_", "switched_"))


@pytest.mark.parametrize("index", READ_ONLY)
def test_readonly_mutation_fails(tmp_path, index):
    """Read-only task: any DB mutation (collateral write) must FAIL."""
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    mutate_db(seed, run_dir / "after.db", [
        ("INSERT INTO contact_messages (user_id, full_name, email, subject, message, "
         "created_at) VALUES (NULL, 'X', 'x@example.com', 's', 'm', ?)", (CREATED,)),
    ])
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"], f"read-only mutation must FAIL: {verdict}"
    assert verdict["reason"] == "read_only_db_unchanged"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_state_mismatch_fails(tmp_path, index):
    """Stateful task: honest answer + navigation but DB unchanged = FAIL."""
    seed = _seed()
    run_dir, _, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    copy_db(seed, run_dir / "after.db")  # no mutation: state mismatch
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"], f"state mismatch must FAIL: {verdict}"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_wrong_delta_fails(tmp_path, index):
    """Stateful task: the wrong DB delta (a collateral write) must FAIL."""
    seed = _seed()
    run_dir, _, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    mutate_db(seed, run_dir / "after.db", [
        ("INSERT INTO contact_messages (user_id, full_name, email, subject, message, "
         "created_at) VALUES (NULL, 'X', 'x@example.com', 's', 'm', ?)", (CREATED,)),
    ])
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"], f"wrong delta must FAIL: {verdict}"


@pytest.mark.parametrize("index", range(21))
def test_task_id_tamper_fails(tmp_path, index):
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["task_id"] = "Ohio.gov--99"
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"] and verdict["reason"] == "trajectory_task_matches"


@pytest.mark.parametrize("index", range(21))
def test_offsite_url_fails(tmp_path, index):
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["steps"][0]["url"] = "https://example.com/ohio"
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"] and verdict["reason"] == "all_urls_match_local_origin"


@pytest.mark.parametrize("index", (0, 6, 12))
def test_missing_screenshot_fails(tmp_path, index):
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    (run_dir / "screenshots" / "step_001.png").unlink()
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"] and verdict["reason"] == "screenshots_decode"


@pytest.mark.parametrize("index", (0, 6, 12))
def test_nondone_trajectory_fails(tmp_path, index):
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"] and verdict["reason"] == "trajectory_completed"


@pytest.mark.parametrize("index", (0, 6, 12))
def test_tampered_seed_fails(tmp_path, index):
    """A mutated initial.db breaks the frozen-seed contract: fail closed."""
    run_dir, seed, after = HONEST[index](tmp_path)
    mutate_db(seed, run_dir / "initial.db", [
        ("UPDATE resources SET summary = 'tampered' WHERE id = 1", ()),
    ])
    # after.db was already materialized by the honest fixture; only the seed
    # snapshot is tampered here.
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"] and verdict["reason"] == "snapshot_contract_invalid"

"""Deterministic verifier contract tests for the 18 Instructure tasks.

Covers, per task: the honest trajectory MUST PASS; a no-op run (homepage only,
empty answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a shortcut (correct
answer, homepage-only navigation, correct DB delta) MUST FAIL; a missing DB
delta MUST FAIL; a wrong DB delta (right table, wrong row) MUST FAIL; a correct
delta plus a collateral write MUST FAIL. Package tampering (task_id mismatch,
off-site URL, missing screenshot, non-done trajectory, tampered seed,
unavailable DB) MUST fail closed.

Every redesigned task is stateful: each requires an exact database delta and
rejects unrelated changes. Snapshots are seed copies mutated through sqlite;
trajectories are hand-written in the agent_demo/agent.py shape. No LLM. The
fixtures are grading controls, not browser completion evidence — the browser
walkthrough evidence lives in the upgrade evidence runs.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, RunBuilder, SEED_DB, _acquire_seed, build_run, copy_db,  # noqa: E402
                      mutate_db, noop_run, run_verifier)

pytestmark = pytest.mark.skipif(not SEED_DB.is_file() and not SEED_DB and False,
                                reason="seed DB unavailable")

N_TASKS = 18
LOGIN = {"alice": "alice.j@test.com", "bob": "bob.c@test.com",
         "carol": "carol.d@test.com", "david": "david.k@test.com"}
CREATED = "2026-09-22 00:00:00.000000"

# ---------------------------------------------------------------- slugs
HELENA = "/resources/case-studies/digitized-and-disaster-proof-k-12-records-helena-public-schools"
COLUMBUS = "/resources/case-studies/columbus-parchment-case-study"
MADISON = "/resources/case-studies/staying-course-better-benchmarks-madison-county"
KERSHAW = "/resources/case-studies/kershaw-county-mastery-case-study"
MVCSD = "/resources/case-studies/mvcsd-studio-case-study"
UCF = "/resources/case-studies/ucf-data-automation"
EDISON = "/resources/case-studies/edison-high-school-case-study"
BLOG = "/resources/blog/finding-sensible-middle-ai-literacy-cognitive-offloading-and-student-voice-classroom"
PODCAST = "/resources/podcast/no-country-fast-answers-safeguarding-critical-human-logic-world-instant-ai"
WEBINAR3 = "/resources/webinars/case-building-internal-university-employee-training-and-development"
CANVAS_TIERS = "/resources/webinars/canvas-tiers-in-action"
GEERING = "/press-release/instructure-appoints-stephan-geering-chief-privacy-officer-guide-responsible-ai"
EBOOK7 = "/resources/ebooks/future-edtech-building-better-ai-education"
STUDY9 = "/resources/research-reports/2026-edtech-evidence-report"
STUDY11 = "/resources/research-reports/27890"
EBOOK13 = "/resources/ebooks/learning-program-audit-checklist-ld-teams"
STUDY14 = "/resources/research-reports/mastery-item-bank-usage-and-efficacy-study-2023-24"
INFOGRAPHIC = "/resources/infographic/your-igniteai-quick-start-checklist"
WEBINAR15 = "/resources/webinars/reclaim-time-and-personalize-learning-meet-igniteai-k-12-schools-and-districts"
PO_HE = "/resources/product-overviews/canvas-career-higher-education"
PO_EB = "/resources/product-overviews/canvas-career-education-businesses"
VIDEO17 = "/resources/videos/canvas-career-demo-build-skills-based-programs-you-can-measure"

SLUGS = {
    "helena": HELENA.rsplit("/", 1)[1], "columbus": COLUMBUS.rsplit("/", 1)[1],
    "madison": MADISON.rsplit("/", 1)[1], "kershaw": KERSHAW.rsplit("/", 1)[1],
    "mvcsd": MVCSD.rsplit("/", 1)[1], "ucf": UCF.rsplit("/", 1)[1],
    "edison": EDISON.rsplit("/", 1)[1], "podcast": PODCAST.rsplit("/", 1)[1],
    "webinar3": WEBINAR3.rsplit("/", 1)[1], "canvas_tiers": CANVAS_TIERS.rsplit("/", 1)[1],
    "ebook7": EBOOK7.rsplit("/", 1)[1], "study9": STUDY9.rsplit("/", 1)[1],
    "ebook13": EBOOK13.rsplit("/", 1)[1], "study14": STUDY14.rsplit("/", 1)[1],
    "infographic": INFOGRAPHIC.rsplit("/", 1)[1],
    "webinar15": WEBINAR15.rsplit("/", 1)[1],
    "po_he": PO_HE.rsplit("/", 1)[1], "po_eb": PO_EB.rsplit("/", 1)[1],
    "video17": VIDEO17.rsplit("/", 1)[1],
}

# ---------------------------------------------------------------- honest fixtures
# (login email or None, [(path, action, params), ...], honest answer)
HONEST = {
    0: (None, [
        ("/register", "fill", {"text": "quinn.rivers@test.com", "selector": "input[name=email]"}),
        ("/register", "click", {"selector": "button[type=submit]"}),
        ("/resources/case-studies?product=Parchment+Services", "goto", {}),
        (HELENA, "goto", {}), (HELENA + "/download", "goto", {}),
        (HELENA + "/download/sent", "goto", {}), (COLUMBUS, "goto", {}),
        ("/account/saved", "goto", {})],
        "I registered a new account (quinn.rivers@test.com), retrieved the Helena "
        "Public Schools case study PDF through the download form, and saved both "
        "case studies. Helena Public Schools is in Montana with 5,100 students and "
        "Adopted Parchment: 2015. The download confirmation says the PDF is on its "
        "way to my inbox, and both Helena Public Schools and Columbus City Schools "
        "appear under Saved Resources — each save confirmation read '... to your "
        "account'."),
    1: ("bob.c@test.com", [
        (MADISON, "goto", {}), (KERSHAW, "goto", {}),
        (MADISON + "/download", "fill", {"text": "priya.patel@test.com", "selector": "input[name=gate-email]"}),
        (MADISON + "/download", "click", {"selector": "button[type=submit]"}),
        (MADISON + "/download/sent", "goto", {}), ("/account/saved", "goto", {})],
        "Signed in as bob. Madison County serves 12,700 students and Kershaw County "
        "serves 11,000 students, so Madison County is larger. I completed the "
        "download form (Priya Patel): the confirmation says the PDF of the Madison "
        "County study is on its way to my inbox. The save confirmation read: Saved "
        "'Staying the Course for Better Benchmarks in Madison County' to your "
        "account, and it appears under Saved Resources."),
    2: ("carol.d@test.com", [
        ("/resources/blog?topic=Artificial+Intelligence", "goto", {}),
        (BLOG, "goto", {}), ("/search?srch=human+logic", "goto", {}),
        (PODCAST, "goto", {}), ("/account/saved", "goto", {})],
        "The blog post 'Finding the Sensible Middle' is by Marianne Chrisos, who "
        "says to prioritize human connection over technology. Using the site "
        "search I found the Educast 3000 podcast 'No Country for Fast Answers: "
        "Safeguarding Critical Human Logic in a World of Instant AI Responses' and "
        "the save confirmation read: Saved 'No Country for Fast Answers...' to "
        "your account — it appears under Saved Resources."),
    3: ("david.k@test.com", [
        ("/resources/webinars?org=Business", "goto", {}), (WEBINAR3, "goto", {}),
        ("/account", "fill", {"text": "Director of Learning", "selector": "input[name=job_title]"}),
        ("/account", "click", {"selector": "button[type=submit]"}),
        ("/account/saved", "goto", {})],
        "Signed in as david.k@test.com. I registered for the webinar 'The Case for "
        "Building an Internal University for Employee Training and Development': "
        "the confirmation says You're registered for it — find it under your "
        "account. I saved it to the account and updated the profile job title to "
        "Director of Learning; the confirmation says Your profile has been updated."),
    4: ("carol.d@test.com", [
        ("/events?event_type=Webinar&region=North+America", "goto", {}), (CANVAS_TIERS, "goto", {}),
        ("/account", "goto", {}), ("/account/saved", "goto", {}), ("/", "goto", {})],
        "Canvas Tiers in Action: AI, Analytics, and a Simplified LMS is dated "
        "September 29, 2026. Registered as carol: the confirmation says find it "
        "under your account, and the save confirmation read: Saved 'Canvas Tiers "
        "in Action...' to your account (confirmed under Saved Resources). The "
        "homepage banner says InstructureCon 2026 "
        "takes place in Louisville, Kentucky on July 21-23."),
    5: (None, [
        ("/about/careers", "select_dropdown", {"text": "Mexico", "selector": "[data-jobs-filter=location]"}),
        ("/register", "fill", {"text": "rio.james@test.com", "selector": "input[name=email]"}),
        ("/register", "click", {"selector": "button[type=submit]"}),
        (MVCSD, "goto", {}), ("/account", "goto", {})],
        "The Mexico customer success opening is Associate Customer Success Manager "
        "- Higher Education, with a salary range of MX$427K - MX$532K and "
        "employment type FullTime. I registered a new account (rio.james@test.com) "
        "and saved the Murrieta Valley case study 'Video Becomes a Voice for "
        "Learning'; the save confirmation read: Saved 'Video Becomes a Voice for "
        "Learning at Murrieta Valley' to your account, confirmed under Saved "
        "Resources."),
    6: (None, [
        ("/about/leadership", "goto", {}),
        ("/request-demo", "fill", {"text": "jordan.lee@test.com", "selector": "input[name=email]"}),
        ("/request-demo", "select_dropdown", {"text": "K12"}),
        ("/request-demo", "select_dropdown", {"text": "I want to connect with sales"}),
        ("/request-demo", "select_dropdown", {"text": "Colorado"}),
        ("/request-demo", "click", {"selector": "button[type=submit]"})],
        "Instructure's Chief Learning Officer is Melissa Loble, who chairs the "
        "1EdTech board of directors. I submitted the Request a Demo form as Jordan "
        "Lee; the confirmation says an Instructure team member will reach out "
        "within one business day."),
    7: (None, [
        ("/news?region=Europe", "goto", {}), (GEERING, "goto", {}),
        ("/resources/ebooks", "goto", {}), (EBOOK7, "goto", {}),
        (EBOOK7 + "/download", "fill", {"text": "priya.nair@test.com", "selector": "input[name=gate-email]"}),
        (EBOOK7 + "/download", "select_dropdown", {"text": "Higher Ed"}),
        (EBOOK7 + "/download", "select_dropdown", {"text": "General Inquiry"}),
        (EBOOK7 + "/download", "click", {"selector": "button[type=submit]"}),
        (EBOOK7 + "/download/sent", "goto", {})],
        "Filtering the Newsroom by Region Europe, the Spanish article from "
        "Educacion 3.0 is 'Para evitar que la IA se convierta en una herramienta "
        "dañina' with spokesperson Ryan Lufkin. The press release appointing "
        "Stephan Geering as Chief Privacy Officer is dated September 14, 2026 with "
        "a SALT LAKE CITY dateline. I retrieved the ebook through the download "
        "form; the confirmation says it is on its way to my inbox."),
    8: (None, [
        ("/support/canvas-support-faq", "goto", {}),
        ("/contact-us", "fill", {"text": "maria.chen@test.com", "selector": "input[name=email]"}),
        ("/contact-us", "select_dropdown", {"text": "Higher Ed"}),
        ("/contact-us", "select_dropdown", {"text": "I'm a teacher looking for product information"}),
        ("/contact-us", "click", {"selector": "button[type=submit]"})],
        "The official steps: on the Login page click the Forgot Password? link, "
        "enter your login information and click the Request Password button, then "
        "follow the email you are sent to reset your password and return to the "
        "login screen. I submitted the Contact Us form as Maria Chen; the "
        "confirmation says Thanks for reaching out! We'll be in touch shortly."),
    9: ("alice.j@test.com", [
        ("/account/saved", "click", {"selector": "form[action*='madison-county'] button"}),
        ("/resources/research-reports", "goto", {}), (STUDY9, "goto", {}),
        ("/account", "select_dropdown", {"text": "Colorado"}),
        ("/account", "click", {"selector": "button[type=submit]"})],
        "Signed in as alice. The removal confirmation says Removed 'Staying the "
        "Course for Better Benchmarks in Madison County' from your saved "
        "resources. I saved the 2026 EdTech Evidence Report from the Research hub "
        "and updated the profile state to Colorado; the confirmation says Your "
        "profile has been updated. The account now has 4 saved resources."),
    10: (None, [
        ("/register", "fill", {"text": "casey.ward@test.com", "selector": "input[name=email]"}),
        ("/register", "click", {"selector": "button[type=submit]"}),
        (UCF, "goto", {}), ("/account/saved", "goto", {}),
        (UCF + "/download", "goto", {}), (UCF + "/download/sent", "goto", {})],
        "I registered a new account, saved the UCF admissions case study (confirmed "
        "under Saved Resources), and read the stat bar: 20,967 transcripts "
        "processed annually. Then I retrieved the PDF through the download form; "
        "the confirmation says it is on its way to my inbox, and the save "
        "confirmation read: Saved 'Automating the Admissions Workflow at the "
        "University of Central Florida' to your account."),
    11: (None, [
        ("/resources/research-reports", "goto", {}), (STUDY11, "goto", {}),
        ("/request-demo", "fill", {"text": "alex.rivera@test.com", "selector": "input[name=email]"}),
        ("/request-demo", "select_dropdown", {"text": "Higher Ed"}),
        ("/request-demo", "select_dropdown", {"text": "I want to connect with sales"}),
        ("/request-demo", "select_dropdown", {"text": "Washington"}),
        ("/request-demo", "click", {"selector": "button[type=submit]"})],
        "The 2026 Canvas LMS Educator Impact Study is based on a 2026 survey of "
        "250 educators. I submitted the Request a Demo form as Alex Rivera for "
        "Cascadia Community College; the confirmation says an Instructure team "
        "member will reach out within one business day."),
    12: (None, [
        (EDISON, "goto", {}),
        (EDISON + "/download", "fill", {"text": "priya.nair@test.com", "selector": "input[name=gate-email]"}),
        (EDISON + "/download", "click", {"selector": "button[type=submit]"}),
        (EDISON + "/download/sent", "goto", {}),
        ("/login", "fill", {"text": "bob.c@test.com", "selector": "input[name=email]"}),
        ("/login", "fill", {"text": "TestPass123!", "selector": "input[name=password]"}),
        ("/login", "click", {"selector": "button[type=submit]"}),
        (EDISON, "click", {"selector": "form[action*='/save'] button"}),
        ("/account/saved", "goto", {})],
        "The download form for 'How Edison High School Turns Fees into "
        "Scholarships' went through: the confirmation says the PDF is on its way "
        "to my inbox. I then saved the case study to the bob demo account; the "
        "save confirmation read: Saved 'How Edison High School Turns Fees into "
        "Scholarships' to your account, and it appears under Saved Resources."),
    13: (None, [
        ("/resources/ebooks", "goto", {}), (EBOOK13, "goto", {}),
        (EBOOK13 + "/download", "fill", {"text": "sam.ortiz@test.com", "selector": "input[name=gate-email]"}),
        (EBOOK13 + "/download", "select_dropdown", {"text": "Business"}),
        (EBOOK13 + "/download", "select_dropdown", {"text": "General Inquiry"}),
        (EBOOK13 + "/download", "click", {"selector": "button[type=submit]"}),
        (EBOOK13 + "/download/sent", "goto", {})],
        "The Learning Program Audit Checklist for L&D Teams says you can assess "
        "skills-based learning, learner engagement, reporting, automation, and "
        "business impact. I retrieved it through the download form (Sam Ortiz); "
        "the confirmation says the ebook is on its way to my inbox."),
    14: (None, [
        ("/resources/research-reports?org=K-12", "goto", {}), (STUDY14, "goto", {}),
        (STUDY14 + "/download", "fill", {"text": "dana.white@test.com", "selector": "input[name=gate-email]"}),
        (STUDY14 + "/download", "select_dropdown", {"text": "K12"}),
        (STUDY14 + "/download", "select_dropdown", {"text": "I want to connect with sales"}),
        (STUDY14 + "/download", "click", {"selector": "button[type=submit]"}),
        (STUDY14 + "/download/sent", "goto", {})],
        "The Mastery Item Bank Usage and Efficacy Study (2023-24) found assessment "
        "usage associated with higher state test scores in math and English "
        "Language Arts (ELA). I retrieved the report through the download form "
        "(Dana White); the confirmation says it is on its way to my inbox."),
    15: ("bob.c@test.com", [
        ("/resources/infographic", "goto", {}), (INFOGRAPHIC, "goto", {}),
        ("/resources/webinars", "goto", {}), (WEBINAR15, "goto", {}),
        ("/account", "goto", {}), ("/account/saved", "goto", {})],
        "Signed in as bob. The save confirmation read: Saved 'Your IgniteAI "
        "Quick-Start Checklist' to your account, and I registered for 'Reclaim "
        "Time and Personalize Learning: "
        "Meet IgniteAI for K-12 Schools and Districts' — the confirmation says "
        "find it under your account. Both appear under the account."),
    16: ("carol.d@test.com", [
        ("/resources/product-overviews?org=Higher+Education", "goto", {}), (PO_HE, "goto", {}),
        (PO_EB, "goto", {}), ("/account/saved", "goto", {})],
        "The Canvas Career for Higher Education overview says it empowers students "
        "to move from classroom to career. I saved it and the 'Canvas Career for "
        "education businesses' overview; both save confirmations read '... to your "
        "account' and both appear under Saved Resources."),
    17: ("david.k@test.com", [
        ("/resources/videos?org=Business", "goto", {}), (VIDEO17, "goto", {}),
        ("/account/saved", "goto", {}),
        ("/account/saved", "fill", {"text": "david.k@test.com", "selector": ".newsletter-strip input[name=email]"}),
        ("/account/saved", "click", {"selector": ".newsletter-strip button"})],
        "The Canvas Career demo says L&D teams can measure training impact at "
        "scale (align learning to real roles, create content faster). The save "
        "confirmation read: Saved 'Canvas Career Demo: Build Skills-Based Programs "
        "You Can Measure' to your account (confirmed under Saved Resources), and I "
        "subscribed "
        "david.k@test.com to the newsletter; the confirmation says You're on the "
        "list! Watch your inbox for the latest from the learnosphere."),
}

WRONG_ANSWERS = {
    0: "Helena is in Idaho with 3,200 students, adopted 2019; only one case study was saved.",
    1: "Madison serves 9,500 and Kershaw 20,000, so Kershaw is larger; the download said 'check your email'.",
    2: "The post is by John Smith, who says to prioritize technology over connection; I saved a video.",
    3: "I registered for the Parchment webinar and the profile said 'Done'.",
    4: "The event is on December 1, 2026; InstructureCon is in Boston on June 1-2.",
    5: "The Mexico role pays MX$100K and is part-time.",
    6: "The CLO is Ryan Lufkin, who chairs the Wikipedia board; the form said 'we will call you'.",
    7: "The article was in French by Betsy Allen; the release is dated January 3, 2026 from New York; the download said 'later'.",
    8: "Just email support@instructure.com; the contact form said 'Message received'.",
    9: "I removed an ebook, the count is 2, and the profile said 'saved'.",
    10: "The stat bar shows 15,000 transcripts; the download never confirmed.",
    11: "The study surveyed 25 educators; no confirmation appeared.",
    12: "The download said 'check back later'; nothing was saved.",
    13: "The checklist assesses lunch menus; the download said 'maybe'.",
    14: "The subjects were history and art; the download never confirmed.",
    15: "I saved a video and registered for a podcast.",
    16: "The overview says students move from career to classroom.",
    17: "The demo is about cooking; the newsletter said nothing.",
}


# ---------------------------------------------------------------- sqlite helpers
def rid(seed_db, key):
    con = sqlite3.connect(str(seed_db))
    try:
        row = con.execute("SELECT id FROM resources WHERE slug = ?", (SLUGS[key],)).fetchone()
        assert row, f"slug {key} not in seed"
        return row[0]
    finally:
        con.close()


def uid(seed_db, email):
    con = sqlite3.connect(str(seed_db))
    try:
        row = con.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        assert row, f"user {email} not in seed"
        return row[0]
    finally:
        con.close()


def rtitle(seed_db, key):
    con = sqlite3.connect(str(seed_db))
    try:
        row = con.execute("SELECT title FROM resources WHERE slug = ?", (SLUGS[key],)).fetchone()
        assert row
        return row[0]
    finally:
        con.close()


def new_user_row(seed_db, n, email):
    return [("INSERT INTO users (id, username, email, display_name, password_hash, "
             "job_title, organization, organization_type, country, state, phone, created_at) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
             (5, f"user{n}", email, "Fixture User", "x", "", "", "", "", "", "", CREATED))]


def demo_row(first, last, email, org, org_type, needs, source, *, job="", phone="",
             state="", n=1):
    return [("INSERT INTO demo_requests (id, first_name, last_name, email, phone, job_title, "
             "organization, organization_type, country, state, needs, message, source, created_at) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
             (n, first, last, email, phone, job, org, org_type, "", state, needs,
              "fixture message", source, CREATED))]


def saved_row(user_id, resource_id, n=13):
    return [("INSERT INTO saved_resources (id, user_id, resource_id, created_at) "
             "VALUES (?,?,?,?)", (n, user_id, resource_id, CREATED))]


def reg_row(user_id, resource_id, n=5):
    return [("INSERT INTO webinar_registrations (id, user_id, resource_id, created_at) "
             "VALUES (?,?,?,?)", (n, user_id, resource_id, CREATED))]


def contact_row(first, last, email, job, phone, org, org_type, needs, n=1):
    return [("INSERT INTO contact_messages (id, first_name, last_name, email, phone, job_title, "
             "organization, organization_type, country, needs, message, source, created_at) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
             (n, first, last, email, phone, job, org, org_type, "", needs,
              "fixture message", "Contact Us", CREATED))]


# ---------------------------------------------------------------- stateful after-DB mutations
def mutations_for(task_n, seed_db):
    alice, bob, carol, david = (uid(seed_db, LOGIN[u]) for u in ("alice", "bob", "carol", "david"))
    if task_n == 0:
        return (new_user_row(seed_db, 0, "quinn.rivers@test.com")
                + demo_row("Quinn", "Rivers", "quinn.rivers@test.com", "Fixture District", "K12",
                           "General Inquiry", "Download: " + rtitle(seed_db, "helena"))
                + saved_row(5, rid(seed_db, "helena"), 13)
                + saved_row(5, rid(seed_db, "columbus"), 14))
    if task_n == 1:
        return (demo_row("Priya", "Patel", "priya.patel@test.com", "Oakdale School District", "K12",
                         "I want to connect with sales",
                         "Download: " + rtitle(seed_db, "madison"))
                + saved_row(bob, rid(seed_db, "madison")))
    if task_n == 2:
        return saved_row(carol, rid(seed_db, "podcast"))
    if task_n == 3:
        return (reg_row(david, rid(seed_db, "webinar3"))
                + saved_row(david, rid(seed_db, "webinar3"), 14)
                + [("UPDATE users SET job_title = 'Director of Learning' WHERE id = ?", (david,))])
    if task_n == 4:
        return (reg_row(carol, rid(seed_db, "canvas_tiers"))
                + saved_row(carol, rid(seed_db, "canvas_tiers"), 14))
    if task_n == 5:
        return (new_user_row(seed_db, 5, "rio.james@test.com")
                + saved_row(5, rid(seed_db, "mvcsd")))
    if task_n == 6:
        return demo_row("Jordan", "Lee", "jordan.lee@test.com", "Summit Public Schools", "K12",
                        "I want to connect with sales", "Web Site",
                        job="Director of Curriculum", state="Colorado")
    if task_n == 7:
        return demo_row("Priya", "Nair", "priya.nair@test.com", "Northgate University", "Higher Ed",
                        "General Inquiry", "Download: " + rtitle(seed_db, "ebook7"))
    if task_n == 8:
        return contact_row("Maria", "Chen", "maria.chen@test.com", "Adjunct Instructor",
                           "+1 555-0170", "Northgate University", "Higher Ed",
                           "I'm a teacher looking for product information")
    if task_n == 9:
        return ([("DELETE FROM saved_resources WHERE user_id = ? AND resource_id = ?",
                  (alice, rid(seed_db, "madison")))]
                + saved_row(alice, rid(seed_db, "study9"))
                + [("UPDATE users SET state = 'Colorado', phone = '+1 801-555-0199' "
                    "WHERE id = ?", (alice,))])
    if task_n == 10:
        return (new_user_row(seed_db, 10, "casey.ward@test.com")
                + demo_row("Casey", "Ward", "casey.ward@test.com", "Fixture University", "Higher Ed",
                           "General Inquiry", "Download: " + rtitle(seed_db, "ucf"), n=2)
                + saved_row(5, rid(seed_db, "ucf")))
    if task_n == 11:
        return demo_row("Alex", "Rivera", "alex.rivera@test.com", "Cascadia Community College",
                        "Higher Ed", "I want to connect with sales", "Web Site",
                        job="Dean of Instruction", state="Washington")
    if task_n == 12:
        return (demo_row("Priya", "Nair", "priya.nair@test.com", "Edison High School", "K12",
                         "I'm a teacher looking for product information",
                         "Download: " + rtitle(seed_db, "edison"), n=3)
                + saved_row(bob, rid(seed_db, "edison")))
    if task_n == 13:
        return demo_row("Sam", "Ortiz", "sam.ortiz@test.com", "Meridian Workforce Institute",
                        "Business", "General Inquiry",
                        "Download: " + rtitle(seed_db, "ebook13"),
                        job="Learning and Development Manager", phone="+1 555-0187", n=4)
    if task_n == 14:
        return demo_row("Dana", "White", "dana.white@test.com", "Fairview Public Schools", "K12",
                        "I want to connect with sales",
                        "Download: " + rtitle(seed_db, "study14"),
                        job="Assessment Director", n=5)
    if task_n == 15:
        return (saved_row(bob, rid(seed_db, "infographic"))
                + reg_row(bob, rid(seed_db, "webinar15")))
    if task_n == 16:
        return (saved_row(carol, rid(seed_db, "po_he"), 13)
                + saved_row(carol, rid(seed_db, "po_eb"), 14))
    if task_n == 17:
        return (saved_row(david, rid(seed_db, "video17"))
                + [("INSERT INTO newsletter_subscribers (id, email, created_at) "
                    "VALUES (?,?,?)", (1, LOGIN["david"], CREATED))])
    raise KeyError(task_n)


# wrong-delta mutations: honest nav + honest answer, but the DB is not the
# exact delta the task requires (wrong row, wrong field, or missing leg)
def wrong_mutations_for(task_n, seed_db):
    alice, bob, carol, david = (uid(seed_db, LOGIN[u]) for u in ("alice", "bob", "carol", "david"))
    if task_n == 0:  # download row never written (only user + saves)
        return (new_user_row(seed_db, 0, "quinn.rivers@test.com")
                + saved_row(5, rid(seed_db, "helena"), 13)
                + saved_row(5, rid(seed_db, "columbus"), 14))
    if task_n == 1:  # saved row links the wrong case study
        return (demo_row("Priya", "Patel", "priya.patel@test.com", "Oakdale School District", "K12",
                         "I want to connect with sales",
                         "Download: " + rtitle(seed_db, "madison"))
                + saved_row(bob, rid(seed_db, "kershaw")))
    if task_n == 2:  # saved by the wrong user
        return saved_row(bob, rid(seed_db, "podcast"))
    if task_n == 3:  # registration present, profile never updated
        return (reg_row(david, rid(seed_db, "webinar3"))
                + saved_row(david, rid(seed_db, "webinar3"), 14))
    if task_n == 4:  # registration present, save missing
        return reg_row(carol, rid(seed_db, "canvas_tiers"))
    if task_n == 5:  # user present, save missing
        return new_user_row(seed_db, 5, "rio.james@test.com")
    if task_n == 6:  # demo row with the wrong organization type
        return demo_row("Jordan", "Lee", "jordan.lee@test.com", "Summit Public Schools", "Higher Ed",
                        "I want to connect with sales", "Web Site",
                        job="Director of Curriculum", state="Colorado")
    if task_n == 7:  # download row with the wrong source
        return demo_row("Priya", "Nair", "priya.nair@test.com", "Northgate University", "Higher Ed",
                        "General Inquiry", "Web Site")
    if task_n == 8:  # contact row with the wrong needs option
        return contact_row("Maria", "Chen", "maria.chen@test.com", "Adjunct Instructor",
                           "+1 555-0170", "Northgate University", "Higher Ed", "General Inquiry")
    if task_n == 9:  # removal done, replacement save missing
        return [("DELETE FROM saved_resources WHERE user_id = ? AND resource_id = ?",
                 (alice, rid(seed_db, "madison"))),
                ("UPDATE users SET state = 'Colorado' WHERE id = ?", (alice,))]
    if task_n == 10:  # download row email does not match the new account
        return (new_user_row(seed_db, 10, "casey.ward@test.com")
                + demo_row("Casey", "Ward", "other.person@test.com", "Fixture University", "Higher Ed",
                           "General Inquiry", "Download: " + rtitle(seed_db, "ucf"), n=2)
                + saved_row(5, rid(seed_db, "ucf")))
    if task_n == 11:  # demo row with the wrong state
        return demo_row("Alex", "Rivera", "alex.rivera@test.com", "Cascadia Community College",
                        "Higher Ed", "I want to connect with sales", "Web Site",
                        job="Dean of Instruction", state="Oregon")
    if task_n == 12:  # download row present, save missing
        return demo_row("Priya", "Nair", "priya.nair@test.com", "Edison High School", "K12",
                        "I'm a teacher looking for product information",
                        "Download: " + rtitle(seed_db, "edison"), n=3)
    if task_n == 13:  # download row with the wrong phone
        return demo_row("Sam", "Ortiz", "sam.ortiz@test.com", "Meridian Workforce Institute",
                        "Business", "General Inquiry",
                        "Download: " + rtitle(seed_db, "ebook13"),
                        job="Learning and Development Manager", phone="+1 555-9999", n=4)
    if task_n == 14:  # download row with the wrong organization type
        return demo_row("Dana", "White", "dana.white@test.com", "Fairview Public Schools", "Higher Ed",
                        "I want to connect with sales",
                        "Download: " + rtitle(seed_db, "study14"),
                        job="Assessment Director", n=5)
    if task_n == 15:  # save present, registration missing
        return saved_row(bob, rid(seed_db, "infographic"))
    if task_n == 16:  # only one of the two overviews saved
        return saved_row(carol, rid(seed_db, "po_he"), 13)
    if task_n == 17:  # save present, newsletter subscription missing
        return saved_row(david, rid(seed_db, "video17"))
    raise KeyError(task_n)


# collateral table for each task: a valid delta plus one unrelated write
COLLATERAL = [
    ("INSERT INTO newsletter_subscribers (id, email, created_at) VALUES "
     "(99, 'collateral@example.com', '2026-09-22 00:00:00.000000')"),
    ("UPDATE resources SET title = title || ' TAMPERED' WHERE id = 1"),
]


@pytest.fixture(scope="session")
def seed_db() -> Path:
    return _acquire_seed()


@pytest.fixture()
def workdir(tmp_path) -> Path:
    return tmp_path


def honest_run(workdir: Path, task_n: int, *, answer_override: str | None = None,
               nav_override=None, task_id: str | None = None) -> Path:
    login, nav, answer = HONEST[task_n]
    root = workdir / f"honest_{task_n}"
    root.mkdir(parents=True, exist_ok=True)
    build_run(root, task_id or f"Instructure--{task_n}",
              nav_override if nav_override is not None else nav,
              answer_override if answer_override is not None else answer,
              login=login)
    return root


def after_db_for(workdir: Path, task_n: int, seed_db: Path, mutations=None) -> Path:
    target = workdir / f"after_{task_n}.db"
    copy_db(target)
    mutate_db(target, mutations if mutations is not None else mutations_for(task_n, seed_db))
    return target


# ---------------------------------------------------------------- honest PASS
@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_honest_run_passes(workdir, seed_db, task_n):
    run_dir = honest_run(workdir, task_n)
    after = after_db_for(workdir, task_n, seed_db)
    verdict = run_verifier(task_n, run_dir, seed_db, after)
    assert verdict.get("pass") is True, json.dumps(verdict, indent=2)[:1500]


# ---------------------------------------------------------------- no-op FAIL
@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_noop_fails(workdir, seed_db, task_n):
    run_dir = workdir / f"noop_{task_n}"
    run_dir.mkdir(parents=True, exist_ok=True)
    noop_run(run_dir, f"Instructure--{task_n}")
    verdict = run_verifier(task_n, run_dir, seed_db, seed_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason")


# ---------------------------------------------------------------- wrong answer FAIL
@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_wrong_answer_fails(workdir, seed_db, task_n):
    after = after_db_for(workdir, task_n, seed_db)
    run_dir = honest_run(workdir, task_n, answer_override=WRONG_ANSWERS[task_n])
    verdict = run_verifier(task_n, run_dir, seed_db, after)
    assert verdict.get("pass") is False, f"wrong answer must fail: {task_n}"


# ---------------------------------------------------------------- shortcut FAIL
@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_shortcut_fails(workdir, seed_db, task_n):
    """Correct answer and correct DB delta, but homepage-only navigation."""
    _, _, answer = HONEST[task_n]
    run_dir = workdir / f"shortcut_{task_n}"
    run_dir.mkdir(parents=True, exist_ok=True)
    build_run(run_dir, f"Instructure--{task_n}", [("/", "click", {})], answer, login=None)
    after = after_db_for(workdir, task_n, seed_db)
    verdict = run_verifier(task_n, run_dir, seed_db, after)
    assert verdict.get("pass") is False, f"shortcut must fail: {task_n}"


# ---------------------------------------------------------------- no delta FAIL
@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_stateful_no_delta_fails(workdir, seed_db, task_n):
    """Agent claims success but the DB is unchanged -> FAIL."""
    run_dir = honest_run(workdir, task_n)
    verdict = run_verifier(task_n, run_dir, seed_db, seed_db)
    assert verdict.get("pass") is False, f"state mismatch must fail: {task_n}"


# ---------------------------------------------------------------- wrong delta FAIL
@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_wrong_delta_fails(workdir, seed_db, task_n):
    after = after_db_for(workdir, task_n, seed_db,
                         mutations=wrong_mutations_for(task_n, seed_db))
    run_dir = honest_run(workdir, task_n)
    verdict = run_verifier(task_n, run_dir, seed_db, after)
    assert verdict.get("pass") is False, f"wrong delta must fail: {task_n}"


# ---------------------------------------------------------------- collateral FAIL
@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_collateral_write_fails(workdir, seed_db, task_n):
    after = after_db_for(workdir, task_n, seed_db,
                         mutations=mutations_for(task_n, seed_db)
                         + [(COLLATERAL[task_n % 2], ())])
    run_dir = honest_run(workdir, task_n)
    verdict = run_verifier(task_n, run_dir, seed_db, after)
    assert verdict.get("pass") is False, f"collateral write must fail: {task_n}"


# ---------------------------------------------------------------- package tamper FAIL
def test_task_id_mismatch_fails(workdir, seed_db):
    run_dir = honest_run(workdir, 0, task_id="Instructure--1")
    after = after_db_for(workdir, 0, seed_db)
    verdict = run_verifier(0, run_dir, seed_db, after)
    assert verdict.get("pass") is False


def test_offsite_url_fails(workdir, seed_db):
    login, nav, answer = HONEST[1]
    root = workdir / "offsite_1"
    root.mkdir(parents=True, exist_ok=True)
    b = RunBuilder(root, "Instructure--1")
    b.login(login)
    for path, action, params in nav:
        b.step(path, action, params)
    b.done(answer)
    b.write()
    traj = json.loads((root / "trajectory.json").read_text())
    traj["steps"][0]["url"] = "https://evil.example.org/phish"
    (root / "trajectory.json").write_text(json.dumps(traj))
    after = after_db_for(workdir, 1, seed_db)
    verdict = run_verifier(1, root, seed_db, after)
    assert verdict.get("pass") is False


def test_missing_screenshot_fails(workdir, seed_db):
    run_dir = honest_run(workdir, 2)
    shots = sorted((run_dir / "screenshots").glob("step_*.png"))
    shots[1].unlink()
    after = after_db_for(workdir, 2, seed_db)
    verdict = run_verifier(2, run_dir, seed_db, after)
    assert verdict.get("pass") is False


def test_undone_trajectory_fails(workdir, seed_db):
    run_dir = honest_run(workdir, 3)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    after = after_db_for(workdir, 3, seed_db)
    verdict = run_verifier(3, run_dir, seed_db, after)
    assert verdict.get("pass") is False


def test_tampered_seed_fails(workdir, seed_db):
    bad_seed = workdir / "bad_seed.db"
    copy_db(bad_seed)
    mutate_db(bad_seed, [("UPDATE resources SET title = title || ' TAMPERED' WHERE id = 1", ())])
    run_dir = honest_run(workdir, 4)
    after = after_db_for(workdir, 4, seed_db)
    verdict = run_verifier(4, run_dir, bad_seed, after)
    assert verdict.get("pass") is False


def test_unavailable_db_fails(workdir, seed_db):
    run_dir = honest_run(workdir, 5)
    missing = workdir / "missing.db"
    verdict = run_verifier(5, run_dir, missing, missing)
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True

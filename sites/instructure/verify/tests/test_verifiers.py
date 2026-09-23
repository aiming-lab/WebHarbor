"""Deterministic verifier contract tests for the 30 Instructure tasks.

Covers, per task: the honest trajectory MUST PASS; a no-op run (homepage only, empty
answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a shortcut (correct answer,
homepage-only navigation) MUST FAIL for every task whose required surface is beyond the
homepage (tasks 7 and 26 are homepage-surface by design and are asserted to PASS on
their homepage shortcut, documenting the design). Read-only tasks MUST FAIL on a
mutated after-DB; stateful tasks MUST FAIL on a state-mismatch (no DB delta) and on a
wrong/collateral state delta. Package tampering (task_id mismatch, off-site URLs,
missing screenshots, non-done trajectory, tampered seed, unavailable DB) MUST fail
closed.

NOTE on task 24 (contact form): round 1 found every valid POST /contact-us returning
HTTP 500 (``contact_us_submit`` passed ``state=`` to ``ContactMessage``); the fix round
(commit 9f1cc54e) dropped the argument, and the live honest run now PASSES with the
same fixture shape used here (flash answer + one ``contact_messages`` row).

No LLM: snapshots are seed copies mutated through sqlite, trajectories are hand-written
in the agent_demo/agent.py shape.
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

STATEFUL = {18, 20, 21, 22, 23, 24, 25}
READ_ONLY = sorted(set(range(30)) - STATEFUL)
LOGIN = {"alice": "alice.j@test.com", "bob": "bob.c@test.com",
         "carol": "carol.d@test.com", "david": "david.k@test.com"}

HELENA = "/resources/case-studies/digitized-and-disaster-proof-k-12-records-helena-public-schools"
MADISON = "/resources/case-studies/staying-course-better-benchmarks-madison-county"
KERSHAW = "/resources/case-studies/kershaw-county-mastery-case-study"
EDISON = "/resources/case-studies/edison-high-school-case-study"
UCF = "/resources/case-studies/ucf-data-automation"
MINUTES = "/resources/blog/minutes-are-wrong-measure"
WEBINAR = "/resources/webinars/moving-canvas-core-canvas-plus"
GEERING = ("/press-release/instructure-appoints-stephan-geering-chief-privacy-officer-"
           "guide-responsible-ai")
STUDY = "/resources/research-reports/27890"

# seed row ids used by the sqlite mutations
R_MADISON, R_UCF, R_WEBINAR, R_EDISON = 2, 8, 354, 4
ALICE, BOB, CAROL, DAVID = 1, 2, 3, 4
CREATED = "2026-09-22 00:00:00.000000"

# ---------------------------------------------------------------- honest fixtures
# (login email or None, [(path, action, params), ...], honest answer from the live DOM)
HONEST = {
    0: (None, [("/resources/case-studies", "goto", {}),
               ("/resources/case-studies?product=Parchment+Services", "check",
                {"selector": 'input[name=product][value="Parchment Services"]'}),
               (HELENA, "goto", {})],
        "With the Product filter set to Parchment Services, the case study about Helena "
        "Public Schools shows in its stat bar: state Montana, 5,100 students, and Adopted "
        "Parchment: 2015."),
    1: (None, [(MADISON, "goto", {})],
        "The district serves 12,700 students. Its 11 elementary schools earned an A rating "
        "from the state of Mississippi (stat bar state: Mississippi)."),
    2: (None, [("/search?srch=screen+time", "fill", {"text": "screen time"}),
               (MINUTES, "goto", {})],
        "The blog post about minute caps in classrooms is 'Minutes are the Wrong Measure', "
        "written by Dr. Tracy Weeks, published Sep 22, 2026."),
    3: (None, [("/resources/webinars", "goto", {}),
               ("/resources/webinars?org=Business", "check",
                {"selector": 'input[name=org][value="Business"]'})],
        "The On-Demand Webinars hub with the Org Type filter Business shows 13 results. The "
        "first webinar in the list is 'Staying Competitive in a Skills-Based World: The New "
        "Rules for Growth and Employability in the Age…'."),
    4: (None, [(EDISON, "goto", {})],
        "Edison High School is in Location: New Jersey. It has Students: 2,000. Its stat "
        "bar shows Adopted Parchment: 2024."),
    5: (None, [(MADISON, "goto", {}), (KERSHAW, "goto", {})],
        "Madison County serves 12,700 students while Kershaw County serves 11,000 students, "
        "so Madison County serves more students — by roughly 1,700 more."),
    6: (None, [("/events", "goto", {}),
               ("/events?event_type=Webinar", "click", {"selector": "button[type=submit]"})],
        "The webinar about Canvas tiers is 'Canvas Tiers in Action: AI, Analytics, and a "
        "Simplified LMS…', dated Webinar • Sep 29, 2026."),
    7: (None, [("/", "goto", {})],
        "The conference is InstructureCon 2026 — Louisville, Kentucky — July 21–23 — "
        "Explore the sessions — from the homepage InstructureCon banner."),
    8: (None, [("/about/careers", "goto", {}),
               ("/about/careers", "select", {"selector": "[data-jobs-filter=department]",
                                             "value": "Engineering"})],
        "There are Current Openings (6) for Engineering, and the first one listed is "
        "'Director, AI Center of Excellence'."),
    9: (None, [("/about/careers", "goto", {})],
        "The role 'Builder, Instructure Foundry' shows a salary range of $150K – $230K. Its "
        "employment type is FullTime (it remains listed when filtering Employment Type to "
        "FullTime) and its location is US-REMOTE."),
    10: (None, [("/about/careers", "goto", {}),
                ("/about/careers", "select", {"selector": "[data-jobs-filter=location]",
                                               "value": "Mexico"})],
        "The customer success role in Mexico is 'Associate Customer Success Manager - Higher "
        "Education'. Its department line reads: Client Services Customer Success Mexico "
        "Hybrid. The compensation range shown is MX$427K – MX$532K • Offers Equity • Offers "
        "Commission."),
    11: (None, [("/about/leadership", "goto", {})],
        "The Chief Learning Officer is Melissa Loble. CEO Steve Daly's bio says that before "
        "Instructure he held leadership roles at Ivanti, Avocent, and Intel."),
    12: (None, [("/about/leadership", "goto", {})],
        "The Chief Financial Officer's full name as displayed on the leadership card is "
        "Audrey Zhao."),
    13: (None, [("/news", "goto", {})],
        "The article 'What Every Educator Needs to Know About AI in 2025' from The Ed Up "
        "Experience Podcast was published January 16, 2025; the quoted spokesperson is Ryan "
        "Lufkin."),
    14: (None, [("/news/public-relations", "goto", {}), (GEERING, "goto", {})],
        "The press release announcing Stephan Geering's appointment as Chief Privacy Officer "
        "is dated Sept. 14, 2026 (announcement date September 14, 2026) and its dateline "
        "location is SALT LAKE CITY."),
    15: (None, [("/news", "goto", {}),
                ("/news", "check", {"selector": 'input[name=region][value="Europe"]'})],
        "Filtering the newsroom by Region Europe, the article from Educacion 3.0 is 'Para "
        "evitar que la IA se convierta en una herramienta dañina hay que aprender a usarla' "
        "and its spokesperson is Ryan Lufkin."),
    16: (None, [("/support/canvas-support-faq", "goto", {})],
        "According to the FAQ, the steps to reset your password when you set up your own "
        "Canvas account are: If you set up your own Canvas account, go to \"Login\" and click "
        "on the \"Forgot Password?\" link. Enter the login information associated with your "
        "Canvas account and click on the \"Request Password\" button. You'll be sent an email "
        "prompting you to reset your password. Once you've reset your password, return to the "
        "login screen to sign in."),
    17: (None, [("/support/canvas-support-faq", "goto", {})],
        "The FAQ says the limitation of a Free Account is: The Free Canvas Accounts don't "
        "contain all the features available to institutional users of Canvas. And yes, "
        "non-teachers can use it: Yes! Students, their parents, and anyone else who wants to "
        "use Canvas learning tools can sign up."),
    18: ("alice.j@test.com", [("/account/saved", "goto", {}),
                              ("/account/saved", "click",
                               {"selector": "form[action*='madison-county'] button"})],
         "My saved resources list shows 4 resources; the case study in the list is 'Staying "
         "the Course for Better Benchmarks in Madison County'. After removing it, the "
         "confirmation message reads: Removed “Staying the Course for Better Benchmarks in "
         "Madison County” from your saved resources."),
    19: ("bob.c@test.com", [("/account", "goto", {})],
         "The webinar I am registered for is 'Design Matters: Key Lessons for Better Canvas "
         "Courses'."),
    20: (None, [("/register", "fill", {"text": "quinn.rivers@test.com", "selector": "input[name=email]"}),
                (UCF, "goto", {}),
                (UCF, "click", {"selector": "form[action*='/save'] button"}),
                ("/account/saved", "goto", {})],
         "After creating my account and saving the case study, my Saved Resources confirm "
         "the UCF case study. The stat bar shows 20,967 transcripts processed annually."),
    21: ("david.k@test.com", [("/account", "goto", {}),
                              ("/account", "click", {"selector": "button[type=submit]"})],
         "I updated my profile: state changed to Colorado and job title to 'Director of "
         "Learning'. The confirmation message shown is: Your profile has been updated."),
    22: ("carol.d@test.com", [(WEBINAR, "goto", {}),
                              (WEBINAR, "click", {"selector": "form[action*='/register'] button"}),
                              ("/account", "goto", {})],
         "The confirmation message reads: You're registered for “Moving from Canvas Core to "
         "Canvas Plus” — find it under your account. Under my account the registration is "
         "recorded for 'Moving from Canvas Core to Canvas Plus'."),
    23: (None, [("/request-demo", "fill", {"text": "jordan.lee@test.com", "selector": "input[name=email]"}),
                ("/request-demo", "click", {"selector": "button[type=submit]"})],
         "After submitting the demo request form, the success message shown is: Thanks! An "
         "Instructure team member will reach out within one business day."),
    24: (None, [("/contact-us", "fill", {"text": "maria.chen@test.com", "selector": "input[name=email]"}),
                ("/contact-us", "click", {"selector": "button[type=submit]"})],
         "After submitting the contact form, the success message shown is: Thanks for "
         "reaching out! We'll be in touch shortly."),
    25: (None, [(EDISON, "goto", {}),
                (EDISON + "/download", "fill", {"text": "priya.nair@test.com", "selector": "input[name=gate-email]"}),
                (EDISON + "/download/sent", "click", {"selector": "button[type=submit]"})],
         "After submitting the download form, the success confirmation shown is: Thanks! "
         "Your download of “How Edison High School Turns Fees into Scholarships” is on its "
         "way to your inbox."),
    26: (None, [("/", "goto", {})],
         "The homepage statistics section says 2B assessment scores created via Mastery, and "
         "7K K-12 schools love Parchment."),
    27: (None, [("/resources/blog", "goto", {}),
                ("/resources/blog?topic=Artificial+Intelligence", "check",
                 {"selector": 'input[name=topic][value="Artificial Intelligence"]'})],
         "The Blogs hub with the Topic filter Artificial Intelligence shows 25 results. The "
         "post about AI literacy, cognitive offloading, and student voice in the classroom "
         "is 'Finding the Sensible Middle: AI Literacy, Cognitive Offloading, and Student "
         "Voice in the Classroom'."),
    28: (None, [("/resources/research-reports", "goto", {}), (STUDY, "goto", {})],
         "The '2026 Canvas LMS Educator Impact Study' is tagged with org types: All. Another "
         "research report that mentions South Carolina is 'Canvas Use and Efficacy in South "
         "Carolina: 2023-24'."),
    29: (None, [("/search?srch=Parchment", "fill", {"text": "Parchment"}),
                (HELENA, "goto", {})],
         "Searching for 'Parchment' returns 47 results for “Parchment”. The case study about "
         "digitizing and disaster-proofing K-12 records at Helena Public Schools shows state "
         "Montana and Adopted Parchment: 2015 in its stat bar."),
}

# stateful after-DB mutations (exactly the delta the verifier accepts)
MUTATIONS = {
    18: [("DELETE FROM saved_resources WHERE id = 1", ())],
    20: [("INSERT INTO users (id, username, email, display_name, password_hash, job_title, "
          "organization, organization_type, country, state, phone, created_at) VALUES "
          "(5, 'quinn.rivers', 'quinn.rivers@test.com', 'Quinn Rivers', 'x', '', '', '', '', "
          "'', '', ?)", (CREATED,)),
         ("INSERT INTO saved_resources (id, user_id, resource_id, created_at) VALUES "
          "(13, 5, ?, ?)", (R_UCF, CREATED))],
    21: [("UPDATE users SET state = 'Colorado', job_title = 'Director of Learning' "
          "WHERE id = 4", ())],
    22: [("INSERT INTO webinar_registrations (id, user_id, resource_id, created_at) VALUES "
          "(5, ?, ?, ?)", (CAROL, R_WEBINAR, CREATED))],
    23: [("INSERT INTO demo_requests (id, first_name, last_name, email, phone, job_title, "
          "organization, organization_type, country, state, needs, message, source, "
          "created_at) VALUES (1, 'Jordan', 'Lee', 'jordan.lee@test.com', '', '', 'Summit "
          "Public Schools', 'K12', '', '', 'I want to connect with sales', 'We are "
          "evaluating an LMS for our district.', 'Web Site', ?)", (CREATED,))],
    24: [("INSERT INTO contact_messages (id, first_name, last_name, email, phone, job_title, "
          "organization, organization_type, country, needs, message, source, created_at) "
          "VALUES (1, 'Maria', 'Chen', 'maria.chen@test.com', '', '', 'Northgate University', "
          "'Higher Ed', '', 'General Inquiry', 'Asking about Parchment integration options.', "
          "'Contact Us', ?)", (CREATED,))],
    25: [("INSERT INTO demo_requests (id, first_name, last_name, email, phone, job_title, "
          "organization, organization_type, country, state, needs, message, source, "
          "created_at) VALUES (1, 'Priya', 'Nair', 'priya.nair@test.com', '', '', 'Edison "
          "High School', 'K12', '', '', 'I''m a teacher looking for product information', "
          "'Please send the case study PDF.', 'Download: How Edison High School Turns Fees "
          "into Scholarships', ?)", (CREATED,))],
}

# tasks whose required surface is the homepage by design (shortcut case is the honest nav)
HOMEPAGE_SURFACE = {7, 26}


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


def stateful_after_db(workdir: Path, task_n: int, mutations=None) -> Path:
    target = workdir / f"after_{task_n}.db"
    copy_db(target)
    mutate_db(target, mutations if mutations is not None else MUTATIONS[task_n])
    return target


# ---------------------------------------------------------------- honest PASS
@pytest.mark.parametrize("task_n", range(30))
def test_honest_run_passes(workdir, seed_db, task_n):
    run_dir = honest_run(workdir, task_n)
    initial = seed_db
    if task_n in STATEFUL:
        after = stateful_after_db(workdir, task_n)
    else:
        after = seed_db
    verdict = run_verifier(task_n, run_dir, initial, after)
    assert verdict.get("pass") is True, json.dumps(verdict, indent=2)[:1200]


# ---------------------------------------------------------------- no-op FAIL
@pytest.mark.parametrize("task_n", range(30))
def test_noop_fails(workdir, seed_db, task_n):
    run_dir = workdir / f"noop_{task_n}"
    run_dir.mkdir(parents=True, exist_ok=True)
    noop_run(run_dir, f"Instructure--{task_n}")
    verdict = run_verifier(task_n, run_dir, seed_db, seed_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason")


# ---------------------------------------------------------------- wrong answer FAIL
WRONG_ANSWERS = {
    0: "Helena Public Schools is in Idaho with 3,200 students, adopted Parchment in 2019.",
    1: "The district serves 9,500 students and its schools earned a B rating.",
    2: "The post was written by John Smith on May 1, 2025.",
    3: "There are 5 results and the first webinar is 'Canvas Basics'.",
    4: "Edison is in Texas with 900 students, adopted Mastery in 2020.",
    5: "Kershaw serves more students: 20,000 vs 5,000.",
    6: "The webinar is 'Parchment Summit' dated Dec 1, 2026.",
    7: "The conference is CanvasCon 2025 in Boston, June 1-2.",
    8: "There are 3 engineering roles, the first is 'Sales Associate'.",
    9: "Salary $90K – $100K, part-time, New York office.",
    10: "The role is 'Regional Sales Director' in Engineering paying MX$100K.",
    11: "The CLO is Ryan Lufkin; Daly worked at Microsoft and Apple.",
    12: "The CFO is Melissa Loble.",
    13: "It was published June 1, 2026 and the spokesperson is Steve Daly.",
    14: "The release is dated January 3, 2026 from New York.",
    15: "The article is 'AI in the classroom' and the spokesperson is Betsy Allen.",
    16: "Just email support@instructure.com and they reset it for you.",
    17: "Free accounts have every feature; only teachers can use it.",
    18: "I had 7 saved resources and removed an ebook; the message said 'Done'.",
    19: "I am registered for 'Canvas Tiers in Action'.",
    20: "The stat bar shows 15,000 transcripts annually.",
    21: "The confirmation said 'Profile saved' and I set Texas.",
    22: "The message said 'You are signed up' for the Parchment Summit.",
    23: "The success message said 'We will call you next week'.",
    24: "The confirmation said 'Message received'.",
    25: "The download confirmation said 'Check your email later'.",
    26: "The stats say 5B assessment scores and 700 schools.",
    27: "18 blog posts match and the post is 'AI in Education'.",
    28: "The study covers K-12 only; the other report is the Mastery Connect Logic Model.",
    29: "The search returns 12 results; Helena is in Ohio since 2010.",
}


@pytest.mark.parametrize("task_n", range(30))
def test_wrong_answer_fails(workdir, seed_db, task_n):
    if task_n in STATEFUL:
        after = stateful_after_db(workdir, task_n)
    else:
        after = seed_db
    run_dir = honest_run(workdir, task_n, answer_override=WRONG_ANSWERS[task_n])
    verdict = run_verifier(task_n, run_dir, seed_db, after)
    assert verdict.get("pass") is False, f"wrong answer must fail: {task_n}"


# ---------------------------------------------------------------- shortcut FAIL
@pytest.mark.parametrize("task_n", range(30))
def test_shortcut_fails(workdir, seed_db, task_n):
    """Correct answer but homepage-only navigation."""
    login, nav, answer = HONEST[task_n]
    run_dir = workdir / f"shortcut_{task_n}"
    run_dir.mkdir(parents=True, exist_ok=True)
    build_run(run_dir, f"Instructure--{task_n}", [("/", "click", {})], answer, login=None)
    if task_n in STATEFUL:
        after = stateful_after_db(workdir, task_n)
    else:
        after = seed_db
    verdict = run_verifier(task_n, run_dir, seed_db, after)
    if task_n in HOMEPAGE_SURFACE:
        # homepage-surface by design: the homepage shortcut IS the honest navigation,
        # so the run must PASS (documented contract, same as the imgur suite).
        assert verdict.get("pass") is True, json.dumps(verdict, indent=2)[:800]
    else:
        assert verdict.get("pass") is False, f"shortcut must fail: {task_n}"


# ---------------------------------------------------------------- read-only tamper FAIL
TAMPER_ROWS = [
    ("INSERT INTO newsletter_subscribers (id, email, created_at) VALUES "
     "(1, 'tamper@example.com', '2026-09-22 00:00:00.000000')"),
    ("UPDATE resources SET title = title || ' TAMPERED' WHERE id = 1"),
]


@pytest.mark.parametrize("task_n", READ_ONLY)
def test_readonly_tamper_fails(workdir, seed_db, task_n):
    after = workdir / f"tamper_{task_n}.db"
    copy_db(after)
    mutate_db(after, [(TAMPER_ROWS[0], ())])
    run_dir = honest_run(workdir, task_n)
    verdict = run_verifier(task_n, run_dir, seed_db, after)
    assert verdict.get("pass") is False, f"read-only tamper must fail: {task_n}"


@pytest.mark.parametrize("task_n", READ_ONLY)
def test_readonly_row_edit_tamper_fails(workdir, seed_db, task_n):
    after = workdir / f"tamper2_{task_n}.db"
    copy_db(after)
    mutate_db(after, [("UPDATE resources SET title = title || ' TAMPERED' WHERE id = 1", ())])
    run_dir = honest_run(workdir, task_n)
    verdict = run_verifier(task_n, run_dir, seed_db, after)
    assert verdict.get("pass") is False, f"read-only row edit must fail: {task_n}"


# ---------------------------------------------------------------- stateful mismatches
@pytest.mark.parametrize("task_n", sorted(STATEFUL))
def test_stateful_no_delta_fails(workdir, seed_db, task_n):
    """Agent claims success but the DB is unchanged -> FAIL."""
    run_dir = honest_run(workdir, task_n)
    verdict = run_verifier(task_n, run_dir, seed_db, seed_db)
    assert verdict.get("pass") is False, f"state mismatch must fail: {task_n}"


@pytest.mark.parametrize("task_n, wrong_mutations", [
    (18, [("DELETE FROM saved_resources WHERE id = 11", ())]),          # removed a different user's row
    (18, [("INSERT INTO newsletter_subscribers (id, email, created_at) VALUES "
           "(1, 'x@example.com', '2026-09-22 00:00:00.000000')",
           ())]),                                                       # collateral write
    (20, [("INSERT INTO users (id, username, email, display_name, password_hash, "
           "created_at) VALUES (5, 'quinn', 'quinn@not-test.com', 'Quinn', 'x', "
           "'2026-09-22 00:00:00.000000')", ())]),                      # non @test.com email
    (20, [("INSERT INTO saved_resources (id, user_id, resource_id, created_at) VALUES "
           "(13, 1, 8, '2026-09-22 00:00:00.000000')", ())]),           # wrong user got the row
    (21, [("UPDATE users SET state = 'Texas', job_title = 'Director of Learning' "
           "WHERE id = 4", ())]),                                       # wrong state
    (22, [("INSERT INTO webinar_registrations (id, user_id, resource_id, created_at) "
           "VALUES (5, 2, 354, '2026-09-22 00:00:00.000000')", ())]),   # wrong user (bob, not carol)
    (23, [("INSERT INTO demo_requests (id, first_name, last_name, email, organization, "
           "organization_type, needs, source, message, created_at) VALUES "
           "(1, 'Wrong', 'Person', 'wrong.person@test.com', 'Wrong Org', 'K12', "
           "'I want to connect with sales', 'Web Site', 'x', "
           "'2026-09-22 00:00:00.000000')", ())]),                      # wrong identity
    (24, [("INSERT INTO contact_messages (id, first_name, last_name, email, organization, "
           "organization_type, needs, source, message, created_at) VALUES "
           "(1, 'Wrong', 'Person', 'wrong.person@test.com', 'Wrong Org', 'Higher Ed', "
           "'General Inquiry', 'Contact Us', 'x', '2026-09-22 00:00:00.000000')", ())]),
    (25, [("INSERT INTO demo_requests (id, first_name, last_name, email, organization, "
           "organization_type, needs, source, message, created_at) VALUES "
           "(1, 'Priya', 'Nair', 'priya.nair@test.com', 'Edison High School', 'K12', "
           "'General Inquiry', 'Download: How Edison High School Turns Fees into "
           "Scholarships', 'x', '2026-09-22 00:00:00.000000')", ())]),   # wrong needs
])
def test_stateful_wrong_delta_fails(workdir, seed_db, task_n, wrong_mutations):
    after = stateful_after_db(workdir, task_n, wrong_mutations)
    run_dir = honest_run(workdir, task_n)
    verdict = run_verifier(task_n, run_dir, seed_db, after)
    assert verdict.get("pass") is False, f"wrong delta must fail: {task_n} {wrong_mutations}"


# ---------------------------------------------------------------- package tampering
def test_task_id_mismatch_fails(workdir, seed_db):
    run_dir = honest_run(workdir, 0, task_id="Instructure--29")
    verdict = run_verifier(0, run_dir, seed_db, seed_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "trajectory_task_matches"


def test_offsite_url_fails(workdir, seed_db):
    login, nav, answer = HONEST[0]
    run_dir = workdir / "offsite"
    run_dir.mkdir(parents=True)
    b = RunBuilder(run_dir, "Instructure--0")
    b.step("/", "goto", {})
    b.step("https://example.com/helena", "goto", {})
    b.done(answer)
    b.write()
    verdict = run_verifier(0, run_dir, seed_db, seed_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "all_urls_match_local_origin"


def test_broken_screenshot_fails(workdir, seed_db):
    run_dir = honest_run(workdir, 1)
    shot = run_dir / "screenshots" / "step_001.png"
    shot.write_bytes(b"not a png")
    verdict = run_verifier(1, run_dir, seed_db, seed_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "screenshots_decode"


def test_missing_screenshot_fails(workdir, seed_db):
    run_dir = honest_run(workdir, 1)
    (run_dir / "screenshots" / "step_001.png").unlink()
    verdict = run_verifier(1, run_dir, seed_db, seed_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "screenshots_decode"


def test_nondone_trajectory_fails(workdir, seed_db):
    login, nav, answer = HONEST[1]
    run_dir = workdir / "nondone"
    run_dir.mkdir(parents=True)
    b = RunBuilder(run_dir, "Instructure--1")
    b.step(MADISON, "goto", {})
    b.done(answer)
    b.write(reason="max_steps")
    verdict = run_verifier(1, run_dir, seed_db, seed_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "trajectory_completed"


def test_tampered_initial_db_fails(workdir, seed_db):
    """A non-seed initial DB (extra row) must fail the frozen-seed contract."""
    bad_seed = workdir / "bad_seed.db"
    copy_db(bad_seed)
    mutate_db(bad_seed, [("INSERT INTO newsletter_subscribers (id, email, created_at) VALUES "
                         "(1, 'x@example.com', '2026-09-22 00:00:00.000000')", ())])
    run_dir = honest_run(workdir, 2)
    verdict = run_verifier(2, run_dir, bad_seed, seed_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "snapshot_contract_invalid"
    assert verdict.get("infra_error") is True


def test_unavailable_db_fails(workdir, seed_db):
    run_dir = honest_run(workdir, 3)
    verdict = run_verifier(3, run_dir, seed_db,
                          workdir / "does_not_exist.db")
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "database_unavailable"
    assert verdict.get("infra_error") is True


def test_collateral_write_fails_for_readonly(workdir, seed_db):
    """A read-only task with an extra users row -> FAIL."""
    after = workdir / "collateral.db"
    copy_db(after)
    mutate_db(after, [("INSERT INTO users (id, username, email, display_name, password_hash, "
                       "created_at) VALUES (99, 'ghost', 'ghost@test.com', 'Ghost', 'x', "
                       "'2026-09-22 00:00:00.000000')", ())])
    run_dir = honest_run(workdir, 13)
    verdict = run_verifier(13, run_dir, seed_db, after)
    assert verdict.get("pass") is False

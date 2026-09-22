"""Shared deterministic AMAZON JOBS task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED here (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (numbers / tokens,
     negation-aware, with bounded word forms)
  4. DB after-state: read-only tasks leave every table unchanged; stateful
     tasks must produce exactly the requested rows/fields and preserve the rest

Ground-truth anchors (frozen seed DB, scrape reference date 2026-09-22):
  jobs: 10554991 Data Scientist, SCOT ... | company Amazon.jobs
        10552766 Financial Analyst Intern, Accounting | ADCI - Karnataka - A66
        10500977 Dir NAMER SA, ISV Data and AI , AGS Namer Tech | Amazon Web Services, Inc.
        10384384 Senior UX Designer, Fashion and Fitness Subs (preferred quals: scalable design systems)
        10506011 UX Designer, Elevated Shopping Experience (preferred quals: degree in design/HCI)
        10555685 Area Manager, Print on Demand | sidebar AUS, NSW, Sydney
        10555689 SDE II, Amazon Privacy Engineering (most recent Seattle job)
        10502686 Applied Scientist, Leo Security
        10498057 Senior Product Manager, AU Customer Experience (CX) Improvement (bob's Assessment app)
  users: 1 alice.j@test.com, 2 bob.c@test.com, 3 carol.d@test.com, 4 david.k@test.com
  applications: id 6 = bob/job 548 (10498057) status Assessment
  job_alerts: id 3 = bob 'product manager' Austin Weekly
"""
import re
import sys
from urllib.parse import unquote_plus

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, new_rows,
    tables_unchanged, navigated_path, navigated_query, navigated_job,
    contains_count, contains_zero, affirm_number, affirms, affirms_any,
    contains_all, contains_any, norm, final_answer, step_text, shot_at,
)
import answers

SITE = "amazon_jobs"

# ---------------------------------------------------------------- ground truth
T0_SEATTLE_ENGINEER = 94          # data engineer + Seattle
T1_PART_TIME = 12
T2_FIRST_RECENT = "Sr PCB Layout Engineer, Amazon Leo"   # hardware-development, sort recent
T3_TOKYO = 24
T4_DEVICES = "Devices and Services"                      # 71 vs 31
T5_JOB = "10554991"                                      # Data Scientist, SCOT ... | ADCI - Karnataka - A66
T5_COMPANY = "ADCI - Karnataka - A66"
T6_JOB = "10552766"                                      # Financial Analyst Intern, Accounting
T6_COMPANY = "ADCI - Karnataka - A66"
T7_OPS_7Y = 9
T8_JOB = "10500977"                                      # Dir NAMER SA ... | Amazon Web Services, Inc.
T9_JOB = "10384384"                                      # scalable design systems
T10_JOB_A = "10384384"                                   # Senior UX Designer, Fashion and Fitness Subs
T10_JOB_B = "10506011"                                   # UX Designer, Elevated Shopping Experience
T11_JOB = "10555685"                                      # Area Manager, Print on Demand | AUS, NSW, Sydney
T12_SWDEV_FIRST_SECTION = "Building impactful solutions at large scale"
T13_VOICES = 3
T13_FIRST_NAME = "Paige"
T14_MARKETING_OPEN = 18
T15_US_LOCATIONS = 34
T16_SEATTLE_HERO = 160
T16_MOST_RECENT = "SDE II, Amazon Privacy Engineering"
T17_AIS = "AWS Infrastructure Services (AIS)"
T18_SITE = "this website"
T18_FILTERS = ("locations", "business categories", "job categories", "keywords")
T19_TIME_AWAY = "Take time for you, when you need it"
T20_STEPS = 4
T20_FIRST_STEP = "Online Application"
T21_STORY = ("Xiaole", "Engineer", "Beijing, China")
T22_AI_RUNTIME_STATUS = "Under review"
T22_JOB = "10555688"                                      # Software Development Engineer, AI Runtime
T23_WITHDRAW_APP_ID = 6                                   # bob -> job 548 (10498057)
T23_JOB = "10498057"                                      # Senior Product Manager, AU CX Improvement
T24_ALERT_QUERY = "product designer"
T24_MATCH = 46
T24_USER_ID = 3                                           # carol
T25_USER_ID = 4                                           # david
T25_HEADLINE = "Machine Learning Engineer"
T25_CITY = "Bellevue"
T26_USER_ID = 1                                           # alice
T27_JOB = "10502686"                                      # Applied Scientist, Leo Security
T27_JOB_PK = 177
T27_USER_ID = 4                                           # david
T28_ALERT_ID = 3                                          # bob 'product manager' Austin
T28_USER_ID = 2                                           # bob
T29_FULFILLMENT_LT1 = 15

ALICE_EMAIL = "alice.j@test.com"
BOB_EMAIL = "bob.c@test.com"
CAROL_EMAIL = "carol.d@test.com"
DAVID_EMAIL = "david.k@test.com"


# ---------------------------------------------------------------- helpers
def search_step_with(traj, *substrs):
    """True when a /search step URL carries every substring (query unquoted)."""
    from verify_lib import step_urls, url_path
    for url in step_urls(traj):
        if url_path(url).rstrip("/") != "/search":
            continue
        decoded = unquote_plus(url).casefold()
        if all(s.casefold() in decoded for s in substrs):
            return True
    return False


def db_tables_unchanged(judge, init_db, after_db, expect_note):
    changed = tables_unchanged(init_db, after_db)
    if changed is None:
        judge.check("db_unchanged", False, "DB snapshots unavailable (fail-closed)")
        return None
    judge.check("db_unchanged", not changed,
                "all tables byte-identical" if not changed else f"changed tables: {changed}" + f" ({expect_note})")
    return changed


def read_only_gate(judge, init_db, after_db):
    db_tables_unchanged(judge, init_db, after_db, "read-only task")


# ---------------------------------------------------------------- per-task grading
def grade_0(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/search")
    judge.check("search_visited", search_step_with(traj, "base_query=data", "loc_keyword=seattle"),
                "searched 'data engineer' with location Seattle on the mirror")
    judge.check("answer_count", contains_count(fa, T0_SEATTLE_ENGINEER),
                fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_1(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/search")
    judge.check("search_visited", navigated_path(traj, "/search"),
                "opened the job search page with its Job Type filter")
    judge.check("answer_count", contains_count(fa, T1_PART_TIME), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_2(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="category=hardware-development")
    judge.check("search_visited",
                search_step_with(traj, "category=hardware-development", "sort_by=recent"),
                "filtered to Hardware Development and sorted by Most recent")
    judge.check("answer_title", contains_all(fa, ["pcb layout engineer"]) and affirms(fa, "leo"),
                fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_3(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="city=Tokyo")
    judge.check("search_visited", search_step_with(traj, "city=tokyo"),
                "used the City filter for Tokyo")
    judge.check("answer_count", contains_count(fa, T3_TOKYO), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_4(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/search")
    judge.check("search_visited", navigated_path(traj, "/search"),
                "opened the job search page with its Team filter counts")
    judge.check("answer_team", answers.devices_wins(fa), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_5(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url=f"/jobs/{T5_JOB}")
    judge.check("search_visited",
                search_step_with(traj, "category=data-science", "country=india", "sort_by=recent"),
                "filtered to Data Science + India and sorted by Most recent")
    judge.check("job_page_opened", navigated_job(traj, T5_JOB),
                f"opened the job page /jobs/{T5_JOB}")
    judge.check("answer_company", answers.adci_company(fa), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_6(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url=f"/jobs/{T6_JOB}")
    judge.check("intern_search_seen",
                search_step_with(traj, "intern") or search_step_with(traj, "loc_keyword=india"),
                "searched intern jobs in India")
    judge.check("job_page_opened", navigated_job(traj, T6_JOB),
                f"opened the job page /jobs/{T6_JOB}")
    judge.check("answer_title", contains_all(fa, ["financial analyst intern"]) and affirms(fa, "accounting"),
                fa or "")
    judge.check("answer_company", answers.adci_company(fa), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_7(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="business_category=amazon-operations")
    judge.check("search_visited",
                search_step_with(traj, "business_category=amazon-operations", "experience=7"),
                "filtered to Amazon Operations + 7+ years industry experience")
    judge.check("answer_count", contains_count(fa, T7_OPS_7Y), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_8(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url=f"/jobs/{T8_JOB}")
    judge.check("search_seen", search_step_with(traj, "namer"),
                "searched for the Dir NAMER SA job")
    judge.check("job_page_opened", navigated_job(traj, T8_JOB),
                f"opened the job page /jobs/{T8_JOB}")
    judge.check("answer_company", affirms(fa, "amazon web services"), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_9(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url=f"/jobs/{T9_JOB}")
    judge.check("job_page_opened", navigated_job(traj, T9_JOB),
                f"opened the job page /jobs/{T9_JOB}")
    judge.check("answer_design_systems", answers.scalable_design_systems(fa), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_10(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url=f"/jobs/{T10_JOB_A}")
    judge.check("job_a_opened", navigated_job(traj, T10_JOB_A),
                f"opened /jobs/{T10_JOB_A} (Senior UX Designer, Fashion and Fitness Subs)")
    judge.check("job_b_opened", navigated_job(traj, T10_JOB_B),
                f"opened /jobs/{T10_JOB_B} (UX Designer, Elevated Shopping Experience)")
    judge.check("answer_which_job", answers.elevated_mentions_degree(fa), fa or "")
    judge.check("answer_degree_field", answers.degree_field(fa), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_11(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url=f"/jobs/{T11_JOB}")
    judge.check("search_seen", search_step_with(traj, "print on demand"),
                "searched for the Area Manager, Print on Demand job")
    judge.check("job_page_opened", navigated_job(traj, T11_JOB),
                f"opened the job page /jobs/{T11_JOB}")
    judge.check("answer_location", affirms(fa, "sydney")
                and affirms_any(fa, ["nsw", "new south wales", "aus"]), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_12(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/job_categories/software-development")
    judge.check("category_page_opened", navigated_path(traj, "/job_categories/software-development"),
                "opened the Software Development category page")
    judge.check("answer_section", contains_all(fa, ["impactful solutions", "large scale"]), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_13(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/job_categories/software-development")
    judge.check("category_page_opened", navigated_path(traj, "/job_categories/software-development"),
                "opened the Software Development category page")
    judge.check("answer_count", contains_count(fa, T13_VOICES), fa or "")
    judge.check("answer_first_name", affirms(fa, "paige"), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_14(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/job_categories/marketing")
    judge.check("category_page_opened", navigated_path(traj, "/job_categories/marketing"),
                "opened the Marketing category page")
    judge.check("answer_count", contains_count(fa, T14_MARKETING_OPEN), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_15(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/locations")
    judge.check("locations_page_opened", navigated_path(traj, "/locations"),
                "opened the Locations page")
    judge.check("answer_count", contains_count(fa, T15_US_LOCATIONS), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_16(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/locations/united-states/washington/seattle")
    judge.check("seattle_page_opened",
                navigated_path(traj, "/locations/united-states/washington/seattle"),
                "opened the Seattle, Washington location page")
    judge.check("answer_hero_count", contains_count(fa, T16_SEATTLE_HERO), fa or "")
    judge.check("answer_recent_title", affirms(fa, "privacy engineering"), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_17(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/business_categories/amazon-web-services")
    judge.check("aws_page_opened", navigated_path(traj, "/business_categories/amazon-web-services"),
                "opened the Amazon Web Services team page")
    judge.check("answer_team", answers.ais_team(fa), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_18(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/faq")
    judge.check("faq_page_opened", navigated_path(traj, "/faq"), "opened the FAQ")
    judge.check("answer_use_site", answers.uses_this_site(fa), fa or "")
    judge.check("answer_filter_dims", answers.filter_dims(fa, 2), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_19(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/benefits/global")
    judge.check("benefits_page_opened", navigated_path(traj, "/benefits/global"),
                "opened the Benefits page")
    judge.check("answer_heading", affirms(fa, "take time for you"), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_20(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/how-we-hire")
    judge.check("hwh_page_opened", navigated_path(traj, "/how-we-hire"),
                "opened the How We Hire page")
    judge.check("answer_step_count", contains_count(fa, T20_STEPS), fa or "")
    judge.check("answer_first_step", affirms(fa, "online application"), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_21(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj)
    judge.check("home_opened", navigated_path(traj, "/"), "opened the homepage with its employee story")
    judge.check("answer_story", answers.xiaole_story(fa), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_22(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/applicant/dashboard/applications")
    judge.check("login_evidence", ALICE_EMAIL in step_text(traj), f"logged in as {ALICE_EMAIL}")
    judge.check("applications_opened", navigated_path(traj, "/applicant/dashboard/applications"),
                "opened My applications")
    judge.check("answer_status", affirms(fa, "under review"), fa or "")
    read_only_gate(judge, init_db, after_db)


def grade_23(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/applicant/dashboard/applications")
    judge.check("login_evidence", BOB_EMAIL in step_text(traj), f"logged in as {BOB_EMAIL}")
    judge.check("applications_opened", navigated_path(traj, "/applicant/dashboard/applications"),
                "opened My applications")
    judge.check("answer_title", answers.au_cx_title(fa), fa or "")
    # DB: application id 6 (bob -> job 548) withdrawn, everything else preserved.
    before, after_rows = rows(args.initial_db), rows(args.after_db)
    if before is None or after_rows is None:
        judge.check("db_state", False, "DB snapshots unavailable (fail-closed)")
        return
    app = next((r for r in after_rows["applications"] if r["id"] == T23_WITHDRAW_APP_ID), None)
    judge.check("db_withdrawn", app is not None and app["status"] == "Withdrawn",
                f"application {T23_WITHDRAW_APP_ID} status={app['status'] if app else 'missing'}")
    other_changed = [t for t in after_rows
                     if t != "applications" and before.get(t) != after_rows.get(t)]
    judge.check("db_rest_preserved", not other_changed, f"changed: {other_changed}")
    apps_before = {r["id"]: r for r in before["applications"]}
    apps_after = {r["id"]: r for r in after_rows["applications"]}
    judge.check("db_no_new_apps", set(apps_after) <= set(apps_before),
                f"new application ids: {sorted(set(apps_after) - set(apps_before))}")
    changed_fields = {aid: {k for k in apps_after[aid] if k in ("status", "updated_at")
                            and apps_before[aid].get(k) != apps_after[aid].get(k)}
                      for aid in apps_after if aid in apps_before
                      and {k: v for k, v in apps_after[aid].items() if k not in ("status", "updated_at")}
                      != {k: v for k, v in apps_before[aid].items() if k not in ("status", "updated_at")}}
    judge.check("db_only_withdraw_changed",
                all(k in ("status", "updated_at") for aid, ks in changed_fields.items() for k in ks),
                f"unexpected field changes: {changed_fields}")


def grade_24(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/applicant/job-alerts")
    judge.check("login_evidence", CAROL_EMAIL in step_text(traj), f"logged in as {CAROL_EMAIL}")
    judge.check("alerts_opened", navigated_path(traj, "/applicant/job-alerts"),
                "opened the Job alerts page")
    judge.check("answer_count", contains_count(fa, T24_MATCH), fa or "")
    before, after_rows = rows(args.initial_db), rows(args.after_db)
    if before is None or after_rows is None:
        judge.check("db_state", False, "DB snapshots unavailable (fail-closed)")
        return
    created = new_rows(before, after_rows, "job_alerts")
    ok = (len(created) == 1 and created[0].get("user_id") == T24_USER_ID
          and norm(created[0].get("query_text")) == T24_ALERT_QUERY
          and created[0].get("frequency") == "Monthly" and created[0].get("active") == 1)
    judge.check("db_alert_created", ok, f"created rows: {created}")
    other_changed = [t for t in after_rows
                     if t != "job_alerts" and before.get(t) != after_rows.get(t)]
    judge.check("db_rest_preserved", not other_changed, f"changed: {other_changed}")
    before_ids = {r["id"] for r in before["job_alerts"]}
    removed = [r["id"] for r in after_rows["job_alerts"] if r["id"] in before_ids
               and r not in before["job_alerts"]]
    judge.check("db_no_alerts_removed_or_mutated",
                all(r in before["job_alerts"] for r in after_rows["job_alerts"] if r["id"] in before_ids),
                f"seed alerts mutated: {removed}")


def grade_25(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/user/details")
    judge.check("login_evidence", DAVID_EMAIL in step_text(traj), f"logged in as {DAVID_EMAIL}")
    judge.check("profile_opened", navigated_path(traj, "/user/details")
                or navigated_path(traj, "/user/details/edit"),
                "opened the profile / profile edit page")
    judge.check("answer_city", affirms(fa, "bellevue"), fa or "")
    before, after_rows = rows(args.initial_db), rows(args.after_db)
    if before is None or after_rows is None:
        judge.check("db_state", False, "DB snapshots unavailable (fail-closed)")
        return
    user = next((r for r in after_rows["users"] if r["id"] == T25_USER_ID), None)
    judge.check("db_headline_changed",
                user is not None and norm(user.get("headline")) == norm(T25_HEADLINE),
                f"david headline={user.get('headline') if user else 'missing'}")
    other_changed = [t for t in after_rows
                     if t != "users" and before.get(t) != after_rows.get(t)]
    judge.check("db_rest_preserved", not other_changed, f"changed: {other_changed}")
    b = {r["id"]: r for r in before["users"]}
    a = {r["id"]: r for r in after_rows["users"]}
    field_changes = {uid: sorted(k for k in a[uid] if a[uid][k] != b[uid][k])
                     for uid in a if uid in b and a[uid] != b[uid]}
    allowed = {T25_USER_ID: {"headline"}}
    bad = {uid: ks for uid, ks in field_changes.items() if set(ks) - allowed.get(uid, set())}
    judge.check("db_only_headline_changed", not bad, f"unexpected user field changes: {bad}")


def grade_26(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/applicant/communication-preferences")
    judge.check("login_evidence", ALICE_EMAIL in step_text(traj), f"logged in as {ALICE_EMAIL}")
    judge.check("prefs_opened", navigated_path(traj, "/applicant/communication-preferences"),
                "opened the communication preferences page")
    judge.check("answer_updates_remain", answers.application_updates_remain(fa), fa or "")
    judge.check("answer_jobrecs_off", not answers.job_recommendations_still_on(fa), fa or "")
    judge.check("answer_newsletter_not_claimed", not answers.newsletter_claimed_on(fa), fa or "")
    before, after_rows = rows(args.initial_db), rows(args.after_db)
    if before is None or after_rows is None:
        judge.check("db_state", False, "DB snapshots unavailable (fail-closed)")
        return
    user = next((r for r in after_rows["users"] if r["id"] == T26_USER_ID), None)
    judge.check("db_recommendations_off",
                user is not None and user.get("notify_recommendations") == 0,
                f"alice notify_recommendations={user.get('notify_recommendations') if user else 'missing'}")
    judge.check("db_updates_still_on",
                user is not None and user.get("notify_application_updates") == 1,
                f"alice notify_application_updates={user.get('notify_application_updates') if user else 'missing'}")
    judge.check("db_newsletter_still_off",
                user is not None and user.get("notify_newsletter") == 0,
                f"alice notify_newsletter={user.get('notify_newsletter') if user else 'missing'}")
    other_changed = [t for t in after_rows
                     if t != "users" and before.get(t) != after_rows.get(t)]
    judge.check("db_rest_preserved", not other_changed, f"changed: {other_changed}")


def grade_27(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url=f"/jobs/{T27_JOB}")
    judge.check("login_evidence", DAVID_EMAIL in step_text(traj), f"logged in as {DAVID_EMAIL}")
    judge.check("job_page_opened", navigated_job(traj, T27_JOB),
                f"opened the job page /jobs/{T27_JOB}")
    judge.check("applications_opened", navigated_path(traj, "/applicant/dashboard/applications"),
                "opened My applications to confirm the status")
    judge.check("answer_status", affirms(fa, "submitted"), fa or "")
    before, after_rows = rows(args.initial_db), rows(args.after_db)
    if before is None or after_rows is None:
        judge.check("db_state", False, "DB snapshots unavailable (fail-closed)")
        return
    created = new_rows(before, after_rows, "applications")
    ok = (len(created) == 1 and created[0].get("user_id") == T27_USER_ID
          and created[0].get("job_id") == T27_JOB_PK and created[0].get("status") == "Submitted")
    judge.check("db_application_created", ok, f"created rows: {created}")
    other_changed = [t for t in after_rows
                     if t != "applications" and before.get(t) != after_rows.get(t)]
    judge.check("db_rest_preserved", not other_changed, f"changed: {other_changed}")


def grade_28(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="/applicant/job-alerts")
    judge.check("login_evidence", BOB_EMAIL in step_text(traj), f"logged in as {BOB_EMAIL}")
    judge.check("alerts_opened", navigated_path(traj, "/applicant/job-alerts"),
                "opened the Job alerts page")
    judge.check("answer_zero", contains_zero(fa), fa or "")
    before, after_rows = rows(args.initial_db), rows(args.after_db)
    if before is None or after_rows is None:
        judge.check("db_state", False, "DB snapshots unavailable (fail-closed)")
        return
    ids_before = {r["id"] for r in before["job_alerts"]}
    ids_after = {r["id"] for r in after_rows["job_alerts"]}
    judge.check("db_alert_deleted", T28_ALERT_ID not in ids_after,
                f"alert {T28_ALERT_ID} removed; ids {sorted(ids_after)}")
    judge.check("db_only_that_alert_removed", ids_after == ids_before - {T28_ALERT_ID},
                f"ids before={sorted(ids_before)} after={sorted(ids_after)}")
    other_changed = [t for t in after_rows
                     if t != "job_alerts" and before.get(t) != after_rows.get(t)]
    judge.check("db_rest_preserved", not other_changed, f"changed: {other_changed}")


def grade_29(judge, traj, args, init_db, after_db, after):
    fa = final_answer(traj)
    judge.bind_run(traj, shot_url="fulfillment-center-warehouse-associate")
    judge.check("search_visited",
                search_step_with(traj, "category=fulfillment-center-warehouse-associate",
                                 "experience=less than 1 year"),
                "filtered to Fulfillment / Warehouse Associate + Less than 1 year")
    judge.check("answer_count", contains_count(fa, T29_FULFILLMENT_LT1), fa or "")
    read_only_gate(judge, init_db, after_db)


GRADES = {n: globals()[f"grade_{n}"] for n in range(30)}


def grade(number):
    args = parse_args()
    traj = load_run(args.run_dir)
    judge = Judge(f"Amazon Jobs--{number}", no_llm=args.no_llm)
    init_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    after = rows(after_db)
    GRADES[number](judge, traj, args, init_db, after_db, after)
    judge.emit()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1].isdigit():
        grade(int(sys.argv[1]))
    else:
        print("usage: grade.py <task-number>", file=sys.stderr)
        sys.exit(2)

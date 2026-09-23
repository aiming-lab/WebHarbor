"""Shared deterministic CA.gov task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED here (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real distinct screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (phones / dates / counts / tokens,
     apostrophe- and separator-tolerant, negation-aware)
  4. DB after-state: read-only tasks leave the database byte-identical; the
     feedback task must produce exactly one feedback row with the requested
     fields
"""
import re
import sys

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, new_rows, tables_unchanged,
    db_file_identical, navigated_path, navigated_query, navigated_prefix,
    contains_all, contains_any, contains_count, contains_phone, contains_date,
    contains_number, affirm_number, affirms, norm, final_answer, step_text,
    shot_at,
)

# ---------------------------------------------------------------- ground truth
# Anchored on the frozen seed database (sites/california_gov/instance_seed),
# which itself mirrors the real ca.gov directory pages.
BIRTH_CERT = {"path": "/departments/176/services/52/", "phone": "916-445-2684",
              "date": "06/26/2026", "dept": "California Department of Public Health"}
CHRB_DEPT = {"path": "/departments/185/", "phone": "916-263-6000", "date": "12/26/2025"}
VETERANS_HOME = {"path": "/departments/163/services/1273/"}
SECOND_CHANCE = {"path": "/departments/155/services/1274/"}
HORSE_LICENSE = {"path": "/departments/185/services/1144/", "phone": "916-263-6000",
                 "date": "07/22/2026", "contact": "http://www.chrb.ca.gov/contact.html"}
DMV_DEPT = {"path": "/departments/220/", "count": 10,
            "first": "Apply for a DL, ID or REAL ID", "last": "Report auto fraud"}
FTB_DEPT = {"path": "/departments/236/"}
TAXES_COUNT = 18
TAXES_MOST_RECENT = ("California Earned Income Tax Credit", "08/10/2026")
TAXES_NAMES = {
    "California Earned Income Tax Credit", "CalABLE disability savings account",
    "Apply for a seller's permit", "Look up sales tax rates",
    "Recovery services finder", "EDD payroll taxes",
    "Enroll in EDD employer services", "Check your tax refund status",
    "Pay your state taxes", "Tax forms and publications",
    "Find business resources", "Business permits and licensing help",
    "File state taxes", "Volunteer Income Tax Assistance (VITA)",
    "CalFile - File return for free", "Create a MyFTB account",
    "Certified Payroll Reporting", "Earned Income Tax Credit (EITC)",
}
CALABLE_TOPICS = ["Assistance and social programs", "Health and wellness", "Taxes"]
SPOTLIGHT = [
    ("data center laws", "September 21, 2026"),
    ("El Nino preparedness", "September 21, 2026"),
    ("legislative update 9.20.2026", "September 20, 2026"),
]
STATE_PARKS, STATE_BEACHES = 87, 63
LT_GOV = {"name": "Eleni Kounalakis", "label": "Visit the Lt. Governor's website"}
CDPH_LIST_NAME = "Public Health, California Department of"
DEATH_CERT = {"path": "/departments/176/services/53/", "date": "06/26/2026",
              "dept": "California Department of Public Health"}
DMV_AUTO_CARDS = ["Pay traffic ticket", "Find a smog station",
                  "Renew driver's license", "Get low cost auto insurance"]
DMV_AUTO_LEAD = [
    "Get or renew your California driver's license, vehicle registration, and more",
    "Learn about and obtain auto insurance",
    "Resolve traffic tickets and keep your vehicle in shape with smog and repair services",
]
MOTOR_VEHICLES_DEPTS = ["Department of Motor Vehicles (DMV)", "New Motor Vehicle Board (NMVB)"]
SALES_TAX = {"topic": "/topics/taxes/", "path": "/departments/287/services/24/",
             "dept": "California Department of Tax and Fee Administration",
             "phone": "800-400-7115", "date": "06/29/2026"}
FISHING = {"path": "/departments/174/services/29/"}
DISASTER_FIRST = ["Check for alerts", "Emergency alerts", "how to stay safe"]
SMOG_RESULTS = [
    ("Find an auto shop", "Bureau of Automotive Repair", "service"),
    ("Repair or retire your vehicle", "Bureau of Automotive Repair", "service"),
    ("DMV/Auto", None, "topic"),
]
CALVET = {"path": "/departments/163/services/64/", "faq_count": 12}
POPULAR_SERVICES = ["Real ID/license", "Birth certificates", "Check your refund",
                    "Traffic tickets", "Business license", "Seller's permit"]
BREA = {"path": "/departments/300/", "phone": "916-552-9000", "date": "04/27/2026"}
CDPH_DEPT = {"path": "/departments/176/", "phone": "916-558-1784"}
DMV_AUTO_LICENSE_FILTER_COUNT = 8
DMV_AUTO_LICENSE_FILTER = [
    "Find an auto shop", "Check a license", "Apply for a DL, ID or REAL ID",
    "DACA and AB60 Driver's License", "Create a MyDMV Account", "Get your mDL",
    "Renew driver's license or ID card", "Update information (address, name, gender)",
]
SMOG_STATION_TARGET = {"path": "/departments/137/services/6/", "name": "Find an auto shop",
                       "desc": "Locate licensed automotive repair shops", "phone": "800-952-5210"}
BIRTH_CERT_RELATED = [
    "Apply for death certificate", "Apply for marriage certificate",
    "Black Infant Health Program (BIH)", "California Home Visiting Program (CHVP)",
    "Comprehensive Perinatal Services Program (CPSP)", "Find information on abortion access",
    "Genetic Disease Screening Program (GDSP)", "Get Digital Vaccine Record",
    "Get maternal mental health help", "Look up licenses for clinical laboratory personnel",
    "Women, Infants and Children (WIC)",
]
MILESTONES = [
    ("1.5m", "zero emission vehicles"),
    ("90%", "clean energy"),
    ("230+", "state government agencies"),
    ("$60b+", "generated to support our communities"),
]

# Tasks whose DB must stay byte-identical (all but the feedback task 9).
READ_ONLY = {n for n in range(30)} - {9}

# Pages that must appear in the trajectory, per task (navigation evidence).
NAV = {
    0: [("query", "/search", {"q": "birth certificate"}), ("path", BIRTH_CERT["path"], {})],
    1: [("path", CHRB_DEPT["path"], {})],
    2: [("path", VETERANS_HOME["path"], {})],
    3: [("path", SECOND_CHANCE["path"], {})],
    4: [("path", "/services/all/", {})],
    5: [("path", "/services/all/", {})],
    6: [("path", "/services/all/", {})],
    7: [("path", HORSE_LICENSE["path"], {})],
    8: [("path", DMV_DEPT["path"], {})],
    9: [("path", FTB_DEPT["path"], {})],
    10: [("path", "/", {})],
    11: [("path", "/", {})],
    12: [("path", "/", {})],
    13: [("path", "/departments/list/", {})],
    14: [("path", BIRTH_CERT["path"], {}), ("path", DEATH_CERT["path"], {})],
    15: [("path", "/topics/dmv-auto/", {})],
    16: [("path", "/topics/dmv-auto/", {})],
    17: [("path", "/departments/all/", {})],
    18: [("path", SALES_TAX["topic"], {}), ("path", SALES_TAX["path"], {})],
    19: [("path", FISHING["path"], {})],
    20: [("path", "/topics/disaster-recovery/", {})],
    21: [("query", "/search", {"q": "smog"}),
         ("path", "/departments/137/services/6/", {}),
         ("path", "/departments/137/services/1289/", {})],
    22: [("path", CALVET["path"], {})],
    23: [("path", "/", {})],
    24: [("path", BREA["path"], {})],
    25: [("path", BIRTH_CERT["path"], {}), ("path", CDPH_DEPT["path"], {})],
    26: [("path", "/topics/dmv-auto/", {})],
    27: [("path", "/topics/dmv-auto/", {}), ("path", SMOG_STATION_TARGET["path"], {})],
    28: [("path", BIRTH_CERT["path"], {})],
    29: [("path", "/about-california/", {})],
}


def _nav_ok(traj, n):
    """(ok, evidence): every required page/URL appears in the trajectory."""
    missing = []
    for kind, target, params in NAV[n]:
        if kind == "query" and not navigated_query(traj, target, **params):
            missing.append(f"{target}?{params}")
        if kind == "path" and not navigated_path(traj, target):
            missing.append(target)
    return (not missing), "required pages: " + ", ".join(
        t if k == "path" else f"{t}?{p}" for k, t, p in NAV[n]) + (
        "" if not missing else f" MISSING {missing}")


def _bound(final, label, value):
    # A fact must share a clause with its entity, not merely occur elsewhere.
    return any(norm(label) in norm(clause) and contains_phone(clause, value)
               for clause in re.split(r"[;\n]|(?<=[.!?])\s+", final))


def _answer_ok(final, n):
    """(ok, evidence): the final answer carries the task's ground-truth facts."""
    if n == 0:
        ok = contains_phone(final, BIRTH_CERT["phone"]) and contains_date(final, BIRTH_CERT["date"])
        return ok, f"phone {BIRTH_CERT['phone']} + date {BIRTH_CERT['date']}"
    if n == 1:
        ok = contains_phone(final, CHRB_DEPT["phone"]) and contains_date(final, CHRB_DEPT["date"])
        return ok, f"phone {CHRB_DEPT['phone']} + date {CHRB_DEPT['date']}"
    if n == 2:
        ok = (affirms(final, "waiting list") or affirms(final, "waiting lists")) \
            and affirms(final, "skilled nursing") \
            and (affirms(final, "prolonged") or affirms(final, "rcfe")
                 or affirms(final, "dom") or affirms(final, "more independent"))
        return ok, "waiting list + skilled nursing (+ prolonged/RCFE/DOM/more independent)"
    if n == 3:
        ok = (re.search(r"6\s*[-–—to ]{1,4}\s*20\s*(characters|chars)", norm(final)) is not None
              or (contains_number(final, 6) and contains_number(final, 20) and affirms(final, "characters"))) \
            and affirms(final, "letters") and affirms(final, "numbers") \
            and affirms(final, "special characters") and affirms(final, "spaces are not allowed")
        return ok, "6-20 characters + letters/numbers/special characters + no spaces"
    if n == 4:
        named = sum(1 for name in TAXES_NAMES if norm(name) in norm(final))
        ok = affirm_number(final, TAXES_COUNT) and named >= 3
        return ok, f"count {TAXES_COUNT} + >=3 Taxes service names (found {named})"
    if n == 5:
        ok = contains_all(final, CALABLE_TOPICS)
        return ok, "topics: " + ", ".join(CALABLE_TOPICS)
    if n == 6:
        ok = contains_all(final, [TAXES_MOST_RECENT[0]]) and contains_date(final, TAXES_MOST_RECENT[1])
        return ok, f"most recent: {TAXES_MOST_RECENT[0]} ({TAXES_MOST_RECENT[1]})"
    if n == 7:
        ok = contains_phone(final, HORSE_LICENSE["phone"]) \
            and contains_date(final, HORSE_LICENSE["date"]) \
            and norm(HORSE_LICENSE["contact"]) in norm(final)
        return ok, f"phone {HORSE_LICENSE['phone']} + date {HORSE_LICENSE['date']} + Contact target"
    if n == 8:
        ok = affirm_number(final, DMV_DEPT["count"]) \
            and contains_all(final, [DMV_DEPT["first"], DMV_DEPT["last"]])
        return ok, f"{DMV_DEPT['count']} services, first {DMV_DEPT['first']!r}, last {DMV_DEPT['last']!r}"
    if n == 9:
        ok = affirms(final, "Thank you for your comments")
        return ok, "confirmation message 'Thank you for your comments'"
    if n == 10:
        got = sum(1 for frag, _ in SPOTLIGHT if norm(frag) in norm(final))
        dates_ok = all(contains_any(final, [d]) for _, d in SPOTLIGHT)
        ok = got == 3 and dates_ok
        return ok, f"3 headlines (found {got}/3) + dates {SPOTLIGHT}"
    if n == 11:
        ok = bool(re.search(r"\b87\s+state parks\b", norm(final))) and bool(re.search(r"\b63\s+state beaches\b", norm(final)))
        return ok, f"{STATE_PARKS} state parks + {STATE_BEACHES} state beaches"
    if n == 12:
        ok = contains_all(final, [LT_GOV["name"], LT_GOV["label"]])
        return ok, f"{LT_GOV['name']} + label {LT_GOV['label']!r}"
    if n == 13:
        ok = contains_all(final, [CDPH_LIST_NAME])
        return ok, f"inverted list name {CDPH_LIST_NAME!r}"
    if n == 14:
        ok = affirms(final, "California Department of Public Health") \
            and contains_date(final, BIRTH_CERT["date"]) \
            and contains_date(final, DEATH_CERT["date"]) \
            and (norm(final).count(norm("California Department of Public Health")) >= 2
                 or affirms(final, "both") or affirms(final, "each"))
        return ok, "both departments + both Last updated dates"
    if n == 15:
        ok = contains_all(final, DMV_AUTO_CARDS)
        return ok, "cards: " + ", ".join(DMV_AUTO_CARDS)
    if n == 16:
        ok = contains_all(final, DMV_AUTO_LEAD)
        return ok, "lead description quoted in full"
    if n == 17:
        ok = contains_all(final, MOTOR_VEHICLES_DEPTS)
        return ok, "departments: " + " + ".join(MOTOR_VEHICLES_DEPTS)
    if n == 18:
        ok = affirms(final, "California Department of Tax and Fee Administration") \
            and contains_phone(final, SALES_TAX["phone"]) \
            and contains_date(final, SALES_TAX["date"])
        return ok, f"CDTFA + phone {SALES_TAX['phone']} + date {SALES_TAX['date']}"
    if n == 19:
        ok = (contains_number(final, 16) and affirms(final, "years of age or older")) \
            and (affirms(final, "calendar year") or affirms(final, "January 1 through December 31"))
        return ok, "16 years of age or older + calendar year (Jan 1 - Dec 31)"
    if n == 20:
        ok = contains_all(final, DISASTER_FIRST)
        return ok, "first item Check for alerts + emergency alerts + how to stay safe"
    if n == 21:
        ok = all(contains_all(final, [name]) for name, _, _ in SMOG_RESULTS) \
            and affirms(final, "Bureau of Automotive Repair") \
            and affirms(final, "topic")
        return ok, "3 smog results + BAR + a topic among them"
    if n == 22:
        ok = affirm_number(final, CALVET["faq_count"]) \
            and contains_any(final, ["no minimum credit score",
                                   "do not have a minimum credit score",
                                   "without a minimum credit score",
                                   "no minimum credit score requirement"]) \
            and (affirms(final, "manually underwrite") or affirms(final, "manual underwriting"))
        return ok, f"{CALVET['faq_count']} FAQs + no minimum credit score + manual underwriting"
    if n == 23:
        ok = contains_all(final, POPULAR_SERVICES)
        return ok, "six pills: " + ", ".join(POPULAR_SERVICES)
    if n == 24:
        ok = contains_phone(final, BREA["phone"]) and contains_date(final, BREA["date"])
        return ok, f"phone {BREA['phone']} + date {BREA['date']}"
    if n == 25:
        ok = _bound(final, "birth certificate", BIRTH_CERT["phone"]) and _bound(final, "Department of Public Health", CDPH_DEPT["phone"]) \
            and (affirms(final, "not the same") or affirms(final, "different")
                 or affirms(final, "do not match") or (affirms(final, "same") is False))
        return ok, f"both phones ({BIRTH_CERT['phone']} / {CDPH_DEPT['phone']}) + not the same"
    if n == 26:
        named = sum(1 for name in DMV_AUTO_LICENSE_FILTER if norm(name) in norm(final))
        ok = affirm_number(final, DMV_AUTO_LICENSE_FILTER_COUNT) \
            and named == DMV_AUTO_LICENSE_FILTER_COUNT
        return ok, f"count {DMV_AUTO_LICENSE_FILTER_COUNT} + names (found {named}/8)"
    if n == 27:
        ok = contains_all(final, [SMOG_STATION_TARGET["name"], SMOG_STATION_TARGET["desc"]]) \
            and contains_phone(final, SMOG_STATION_TARGET["phone"])
        return ok, f"lands on {SMOG_STATION_TARGET['name']!r} + description + phone"
    if n == 28:
        named = sum(1 for name in BIRTH_CERT_RELATED if norm(name) in norm(final))
        ok = named >= 3
        return ok, f">=3 related services (found {named})"
    if n == 29:
        ok = all(contains_all(final, [value, label]) for value, label in MILESTONES)
        return ok, "milestones: " + "; ".join(f"{v} {l}" for v, l in MILESTONES)
    return False, f"unknown task {n}"


def _shot_anchor(n):
    """URL substring that must carry a real screenshot (the task's key page)."""
    anchors = {
        0: BIRTH_CERT["path"], 1: CHRB_DEPT["path"], 2: VETERANS_HOME["path"],
        3: SECOND_CHANCE["path"], 7: HORSE_LICENSE["path"], 8: DMV_DEPT["path"],
        9: FTB_DEPT["path"], 13: "/departments/list/", 14: DEATH_CERT["path"],
        18: SALES_TAX["path"], 19: FISHING["path"], 20: "/topics/disaster-recovery/",
        21: "/departments/137/services/6/", 22: CALVET["path"], 24: BREA["path"],
        25: CDPH_DEPT["path"], 27: SMOG_STATION_TARGET["path"], 28: BIRTH_CERT["path"],
    }
    return anchors.get(n)


def grade(n, emit=True):
    args = parse_args()
    traj = load_run(args.run_dir)
    judge = Judge(f"CA.gov--{n}", no_llm=args.no_llm)
    judge.bind_run(traj, shot_url=_shot_anchor(n))

    final = final_answer(traj)
    nav_ok, nav_note = _nav_ok(traj, n)
    judge.check("nav_required_pages", nav_ok, nav_note)

    answer_ok, answer_note = _answer_ok(final, n)
    judge.check("answer_ground_truth", answer_ok, answer_note)

    # ---- DB after-state
    initial_db = args.initial_db or resolve_db(None, args.container, "instance_seed")
    after_db = args.after_db or resolve_db(None, args.container, "instance")
    if not initial_db or not after_db:
        judge.check("db_available", False, "initial/after DB unobtainable (run_dir snapshots or container)")
        if emit:
            judge.emit()
        return judge
    if n in READ_ONLY:
        identical = db_file_identical(initial_db, after_db)
        judge.check("db_read_only_unchanged", identical is True,
                    f"byte-identical initial vs after: {identical}")
    else:  # task 9: the feedback widget
        before, after = rows(initial_db), rows(after_db)
        if before is None or after is None:
            judge.check("db_readable", False, "cannot read DB snapshots")
        else:
            fresh = new_rows(before, after, "feedback")
            ok = len(fresh) == 1 and fresh[0].get("helpful") == "no" \
                and fresh[0].get("comments") == "The refund status link was hard to find" \
                and str(fresh[0].get("page_path", "")).rstrip("/").endswith("/departments/236") \
                and len(after["feedback"]) == len(before["feedback"]) + 1
            old_ids = {row["id"] for row in before["feedback"]}
            ok = ok and [row for row in after["feedback"] if row["id"] in old_ids] == before["feedback"]
            judge.check("db_feedback_row", ok,
                        f"exactly one new feedback row (helpful=no, exact comment, FTB page path); got {fresh}")
            others = tables_unchanged(initial_db, after_db, ignore=("feedback",))
            judge.check("db_other_tables_unchanged", others == [],
                        f"unchanged tables outside feedback: {others}")
    if emit:
        judge.emit()
    return judge


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: grade.py <task-number>")
    grade(int(sys.argv[1]))

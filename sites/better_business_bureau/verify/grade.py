#!/usr/bin/env python3
"""Shared deterministic BETTER BUSINESS BUREAU task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED here (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (numbers / tokens / dates,
     negation-aware, with bounded word forms)
  4. DB after-state: read-only tasks leave every table unchanged; stateful
     tasks must produce exactly the requested rows/fields and preserve the rest

Ground-truth anchors (frozen seed DB, BBB.org capture reference date 2026-09-21,
seed rebuilt deterministically with PYTHONHASHSEED=0 + canonicalize_seed.py):
  businesses: 349 rows; Xfinity (Comcast) id 27568 (Chicago, Internet Providers)
             State Farm Insurance id 26851 (Chicago, F)
             Car Tender id 7042420 (Shoreline WA, Auto Repairs/Transmission, A+)
             A & M Auto Repair Inc id 1000032981 (Everett WA, first accredited
             result for 'auto repair' near Redmond WA with the accredited filter)
  Xfinity profile: File Opened 1/16/1990; Business Started 7/28/1963; Corporation;
             management "Mr. Brian Roberts, Chairperson/CEO"; payment methods
             "Credit card, Debit card, Bank account"; complaints summary
             26,666 last 3 years / 8,188 closed last 12 months; the $109.00
             complaint = Product Issues / Resolved / 03/04/2026; the warn review
             = Courtland P, 04/22/2025, 1 star
  scam reports: 626 rows; Charity 37; CryptoCurrency 39; gift card keyword 7
             results across Charity/Romance/Tech Support/Utility; scam 1388290 =
             Charity, Seattle WA, $700; Rise Up Youth Foundation WA reports = 6
             with losses $700/$1,485/$800/$1,000/$1,000/$2,000; dashboard (12m
             window = all rows): CA most reports (58), median loss $500,
             47.6% of reports lost money (298/626)
  articles: 40 rows; gift card article = barcode sticker tampering advice;
             gym tips article = fitness goals / budget / priorities / tour
             (F1 fixed: the re-scraped body carries the full tips list);
             Torch Awards article = IABBB announces 2026 winners;
             weight loss scam alert = LipoMax deepfakes, over 170 reports
  users: 1 alice.j@test.com, 2 bob.c@test.com, 3 carol.d@test.com, 4 david.k@test.com
             carol favorite = Accurate Auto Body Inc (Redmond WA, A+);
             carol review = Accurate Auto Body Inc, 4 of 5 stars, 01/20/2026;
             alice scam submission = Phishing, package delivery payment text
  quote flow: Car Tender quote request must create one quote_requests row with
             service brake inspection; flash "Your quote request has been sent
             to the business."
"""
import re
import sys
from urllib.parse import unquote_plus

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, new_rows,
    tables_unchanged, navigated_path, navigated_query, navigated_profile,
    step_urls, contains_count, affirm_number, affirms, affirms_any,
    contains_all, contains_any, norm, final_answer, step_text, shot_at,
)
import answers

SITE = "better_business_bureau"

# ---------------------------------------------------------------- ground truth
T0_FIRST_ACCREDITED = "A & M Auto Repair Inc"      # id 1000032981, Everett WA
T0_PROFILE = "/us/wa/everett/profile/auto-maintenance/a-m-auto-repair-inc-1296-1000032981"
T0_RATING = "A+"
T0_YEARS = 13

T1_CITIES = ("Seattle", "University Place")
T2_HOTELS = ("Crowne Plaza", "Eastside Marriott", "J W Marriott",
             "Marriott East Side", "Marquis", "Residence Inn")

T3_PROFILE = "/us/il/chicago/profile/insurance-companies/state-farm-insurance-0654-26851"
T3_RATING = "F"
T3_CITY = "Chicago"

T4_COUNT = 3
T4_FIRST = "Xfinity"
T4_RATING = "A+"

T5_COUNT = 4
T5_FIRST_ACCREDITED = "Beacon Hill Dental"

T6_LAST_PROFILE = "/us/ny/new-york/profile/hotels/residence-inn-marriott-times-square-0121-89471"
T6_NAME = "Residence Inn"
T6_RATING = "F"

XFINITY = "/us/il/chicago/profile/internet-providers/xfinity-comcast-0654-27568"
CAR_TENDER = "/us/wa/shoreline/profile/auto-repair/car-tender-1296-7042420"
CAR_TENDER_ID = 7042420

T7_FILE_OPENED = ("1/16/1990", "01/16/1990")
T7_BUSINESS_STARTED = ("7/28/1963", "07/28/1963")
T7_ENTITY = "Corporation"
T8_MANAGER = "Brian Roberts"
T8_TITLE = "Chairperson"
T9_TOTAL_3Y = 26666
T9_CLOSED_12M = 8188
T10_AUTHOR = "Courtland"
T10_DATE = ("04/22/2025", "4/22/2025")
T10_STARS = 1
T11_TYPE = "Product Issues"
T11_STATUS = "Resolved"
T11_DATE = ("03/04/2026", "3/4/2026")
T13_LOCAL_BBB = "Great West"
T13_FILE_OPENED = ("2/1/1999", "02/01/1999")
T13_YEARS = 27
T14_PHONE = ("(206) 324-0345", "206-324-0345", "206) 324-0345")
T15_COUNT = 37
T15_CITY = "Miami"
T15_STATE = "FL"
T15_DATE = ("2026-09-19", "09/19/2026", "9/19/2026")
T16_COUNT = 6
T16_AMOUNTS = (700, 1485, 800, 1000, 2000)
T17_SCAM_ID = 1388290
T17_TYPE = "Charity"
T17_CITY = "Seattle"
T17_STATE = "WA"
T17_AMOUNT = 700
T18_STATE = ("CA", "California")
T18_MEDIAN = 500
T18_PCT = ("47.6", "47.60")
T19_MIN_TYPES = 3
T20_MIN_FIELDS = 6
T21_COUNT = 39
T21_CITY = "Palm Desert"
T21_STATE = "CA"
T21_DATE = ("2026-09-18", "09/18/2026", "9/18/2026")
T22_ARTICLE = "/us/news/bbb-tip-don-t-get-scammed-out-of-a-gift-card"
T23_ARTICLE = "/us/news/bbb-tip-need-to-get-in-shape-bbb-has-tips-for-joining-a-gym"
T24_ARTICLE = "/us/news/celebrating-integrity-international-torch-awards-for-ethics-announce-2026-winners"
T25_ARTICLE = "/us/news/bbb-scam-alert-use-caution-when-searching-for-weight-loss-products-online"
T26_BUSINESS = "Accurate Auto Body"
T26_CITY = "Redmond"
T26_STATE = "WA"
T26_RATING = "A+"
T27_BUSINESS = "Accurate Auto Body"
T27_STARS = 4
T27_DATE = ("01/20/2026", "1/20/2026")
T28_TYPE = "Phishing"
T29_SERVICE_TOKEN = "brake"


# ---------------------------------------------------------------- nav helpers
def _search_nav(traj, find_text, find_loc, extra=None):
    """Agent opened /search with the task's query and location (+extra filters).

    find_text/find_loc accept a set of accepted spellings.
    """
    for url in step_urls(traj):
        if url_path_local(url) != "/search":
            continue
        decoded = unquote_plus(url)
        if not any(tok in decoded for tok in (find_text if not isinstance(find_text, str) else {find_text})):
            continue
        if not any(tok in decoded for tok in (find_loc if not isinstance(find_loc, str) else {find_loc})):
            continue
        if extra:
            if any(token not in decoded for token in extra):
                continue
        return True
    return False


def url_path_local(url):
    from verify_lib import url_path
    return (url_path(url).rstrip("/") or "/")


def _lookup_nav(traj, *tokens):
    """Agent opened /scamtracker/lookupscam with every token in the URL (decoded)."""
    for url in step_urls(traj):
        if url_path_local(url) != "/scamtracker/lookupscam":
            continue
        decoded = unquote_plus(url)
        if all(token in decoded for token in tokens):
            return True
    return False


def _signed_in(traj, email):
    """Agent submitted the demo sign-in form for this account."""
    return email in step_text(traj)


# ---------------------------------------------------------------- per-task checks
def grade(number):
    args = parse_args()
    traj = load_run(args.run_dir)
    j = Judge(f"Better Business Bureau--{number}", args.no_llm)
    answer = final_answer(traj)

    init_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    before_rows, after_rows = rows(init_db), rows(after_db)

    def check_readonly(j, ignore=()):
        if before_rows is None or after_rows is None:
            j.check("db_available", False,
                    f"cannot read DBs (initial={bool(init_db)}, after={bool(after_db)}); "
                    f"fallback would fetch {SITE} instance/instance_seed from docker")
            return
        changed = tables_unchanged(init_db, after_db, ignore=ignore)
        if changed is None:
            j.check("db_available", False, "SQLite read failed on a DB snapshot")
        else:
            j.check("db_readonly", changed == [], f"changed tables: {changed}")

    # -------------------------------------------------- T0: first accredited result
    if number == 0:
        j.bind_run(traj, shot_url="/search")
        j.check("nav_search_accredited",
                _search_nav(traj, {"auto repair", "auto repairs"}, {"Redmond, WA"}, extra=("accredited",)),
                "must search auto repair near Redmond WA and apply the accredited filter")
        j.check("nav_first_profile", navigated_path(traj, T0_PROFILE),
                f"must open the profile {T0_PROFILE}")
        j.check("answer_business", affirms_any(answer, ("A & M Auto Repair", "A&M Auto Repair", "A M Auto Repair")),
                f"business name {T0_FIRST_ACCREDITED}")
        j.check("answer_rating", affirms(answer, T0_RATING), f"BBB rating {T0_RATING}")
        j.check("answer_years", affirm_number(answer, T0_YEARS) and affirms(answer, "year"),
                f"years in business {T0_YEARS}")
        check_readonly(j)

    # -------------------------------------------------- T1: Precision Tune pair
    elif number == 1:
        j.bind_run(traj, shot_url="/search")
        j.check("nav_search", _search_nav(traj, {"Precision Tune", "precision tune"}, {"Seattle, WA"}),
                "must search Precision Tune near Seattle WA")
        j.check("answer_cities", contains_all(answer, T1_CITIES), f"cities {T1_CITIES}")
        j.check("answer_ratings", answers.precision_tune_ratings(answer),
                "Seattle location NR / University Place location B-")
        check_readonly(j)

    # -------------------------------------------------- T2: F-rated hotels NYC
    elif number == 2:
        j.bind_run(traj, shot_url="/search")
        j.check("nav_search_f", _search_nav(traj, {"hotels", "hotel"}, {"New York, NY"}, extra=("ratings=F",)),
                "must search hotels near New York NY and filter to F rating")
        for name in T2_HOTELS:
            j.check(f"answer_hotel_{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}",
                    affirms(answer, name), f"hotel name {name}")
        check_readonly(j)

    # -------------------------------------------------- T3: exact State Farm Insurance
    elif number == 3:
        j.bind_run(traj, shot_url=T3_PROFILE)
        j.check("nav_search", _search_nav(traj, {"State Farm Insurance", "state farm insurance"}, {"Chicago, IL"}),
                "must search State Farm Insurance near Chicago IL")
        j.check("nav_profile", navigated_path(traj, T3_PROFILE),
                f"must open the profile {T3_PROFILE}")
        j.check("answer_rating",
                bool(re.search(r"(rating|rated|grade).{0,30}\bF\b|\bF\b.{0,30}(rating|rated|grade)", answer or "", re.I)),
                "BBB rating F")
        j.check("answer_city", affirms(answer, T3_CITY), f"city {T3_CITY}")
        check_readonly(j)

    # -------------------------------------------------- T4: internet providers count
    elif number == 4:
        j.bind_run(traj, shot_url="/search")
        j.check("nav_search", _search_nav(traj, {"internet providers", "internet provider"}, {"Chicago, IL"}),
                "must search internet providers near Chicago IL")
        j.check("answer_count", contains_count(answer, T4_COUNT), f"results shown {T4_COUNT}")
        j.check("answer_first", affirms(answer, T4_FIRST), f"first result name {T4_FIRST}")
        j.check("answer_rating", affirms(answer, T4_RATING), f"first result rating {T4_RATING}")
        check_readonly(j)

    # -------------------------------------------------- T5: dentists Seattle
    elif number == 5:
        j.bind_run(traj, shot_url="/search")
        j.check("nav_search", _search_nav(traj, {"dentist"}, {"Seattle, WA"}),
                "must search dentist near Seattle WA")
        j.check("answer_count", contains_count(answer, T5_COUNT), f"results shown {T5_COUNT}")
        j.check("answer_first_accredited", affirms(answer, T5_FIRST_ACCREDITED),
                f"first BBB-accredited dental business {T5_FIRST_ACCREDITED}")
        check_readonly(j)

    # -------------------------------------------------- T6: lowest-rated hotel page 1
    elif number == 6:
        j.bind_run(traj, shot_url="/search")
        j.check("nav_search_sort", _search_nav(traj, {"hotels", "hotel"}, {"New York, NY"}, extra=("sort=rating",)),
                "must search hotels near New York NY and sort by rating")
        j.check("answer_name", affirms(answer, T6_NAME), f"lowest-rated business {T6_NAME}")
        j.check("answer_rating",
                bool(re.search(r"(rating|rated|grade).{0,30}\bF\b|\bF\b.{0,30}(rating|rated|grade)", answer or "", re.I)),
                "BBB rating F")
        check_readonly(j)

    # -------------------------------------------------- T7: Xfinity business details
    elif number == 7:
        j.bind_run(traj, shot_url=XFINITY)
        j.check("nav_profile", navigated_path(traj, XFINITY), f"must open the profile {XFINITY}")
        j.check("answer_file_opened", contains_any(answer, T7_FILE_OPENED),
                f"BBB File Opened {T7_FILE_OPENED[0]}")
        j.check("answer_started", contains_any(answer, T7_BUSINESS_STARTED),
                f"Business Started {T7_BUSINESS_STARTED[0]}")
        j.check("answer_entity", affirms(answer, T7_ENTITY), f"Type of Entity {T7_ENTITY}")
        check_readonly(j)

    # -------------------------------------------------- T8: Chairperson/CEO
    elif number == 8:
        j.bind_run(traj, shot_url=XFINITY)
        j.check("nav_profile", navigated_path(traj, XFINITY), f"must open the profile {XFINITY}")
        j.check("answer_manager", affirms(answer, T8_MANAGER), f"manager name {T8_MANAGER}")
        j.check("answer_title", affirms(answer, T8_TITLE), f"title {T8_TITLE}")
        check_readonly(j)

    # -------------------------------------------------- T9: complaints summary
    elif number == 9:
        j.bind_run(traj, shot_url=XFINITY + "/complaints")
        j.check("nav_complaints", navigated_path(traj, XFINITY + "/complaints"),
                "must open the Xfinity complaints tab")
        j.check("answer_summary", answers.complaint_summary(answer),
                f"{T9_TOTAL_3Y:,} total / {T9_CLOSED_12M:,} closed")
        check_readonly(j)

    # -------------------------------------------------- T10: warn review
    elif number == 10:
        j.bind_run(traj, shot_url=XFINITY + "/customer-reviews")
        j.check("nav_reviews", navigated_path(traj, XFINITY + "/customer-reviews"),
                "must open the Xfinity customer reviews tab")
        j.check("answer_author", affirms(answer, T10_AUTHOR), f"reviewer {T10_AUTHOR}")
        j.check("answer_date", contains_any(answer, T10_DATE), f"review date {T10_DATE[0]}")
        j.check("answer_rating", answers.warn_review_rating(answer), "star rating 1")
        check_readonly(j)

    # -------------------------------------------------- T11: $109 complaint
    elif number == 11:
        j.bind_run(traj, shot_url=XFINITY + "/complaints")
        j.check("nav_complaints", navigated_path(traj, XFINITY + "/complaints"),
                "must open the Xfinity complaints tab")
        j.check("answer_type", affirms(answer, T11_TYPE), f"complaint type {T11_TYPE}")
        j.check("answer_status", affirms(answer, T11_STATUS), f"status {T11_STATUS}")
        j.check("answer_date", contains_any(answer, T11_DATE), f"initial complaint date {T11_DATE[0]}")
        check_readonly(j)

    # -------------------------------------------------- T12: payment methods
    elif number == 12:
        j.bind_run(traj, shot_url=XFINITY)
        j.check("nav_profile", navigated_path(traj, XFINITY), f"must open the profile {XFINITY}")
        j.check("answer_payment_methods", answers.payment_methods(answer),
                "Credit card, Debit card, Bank account")
        check_readonly(j)

    # -------------------------------------------------- T13: Car Tender details
    elif number == 13:
        j.bind_run(traj, shot_url=CAR_TENDER)
        j.check("nav_profile", navigated_path(traj, CAR_TENDER), f"must open the profile {CAR_TENDER}")
        j.check("answer_local_bbb", affirms(answer, T13_LOCAL_BBB), f"Local BBB contains {T13_LOCAL_BBB}")
        j.check("answer_file_opened", contains_any(answer, T13_FILE_OPENED),
                f"BBB File Opened {T13_FILE_OPENED[0]}")
        j.check("answer_years", affirm_number(answer, T13_YEARS) and affirms(answer, "year"),
                f"years in business {T13_YEARS}")
        check_readonly(j)

    # -------------------------------------------------- T14: Car Tender phone/quotes
    elif number == 14:
        j.bind_run(traj, shot_url=CAR_TENDER)
        j.check("nav_profile", navigated_path(traj, CAR_TENDER), f"must open the profile {CAR_TENDER}")
        j.check("answer_phone", contains_any(answer, T14_PHONE), f"phone {T14_PHONE[0]}")
        j.check("answer_offers_quotes",
                bool(re.search(r"(offer|provid\w+|get|has)\s*(s)?\s*a?\s*quote", answer or "", re.I))
                and not re.search(r"(does ?n[o']t|doesn'?t|not) (offer|provide|have)[^.]{0,20}quote", answer or "", re.I),
                "offers quotes: yes")
        check_readonly(j)

    # -------------------------------------------------- T15: Charity lookup
    elif number == 15:
        j.bind_run(traj, shot_url="/scamtracker/lookupscam")
        j.check("nav_lookup_charity", _lookup_nav(traj, "scam_type=Charity"),
                "must look up Charity scams")
        j.check("answer_count", contains_count(answer, T15_COUNT), f"results shown {T15_COUNT}")
        j.check("answer_location", affirms(answer, T15_CITY) and affirms(answer, T15_STATE),
                f"Blue Heart Advocacy location {T15_CITY}, {T15_STATE}")
        j.check("answer_date", contains_any(answer, T15_DATE), f"date reported {T15_DATE[0]}")
        check_readonly(j)

    # -------------------------------------------------- T16: Rise Up Youth WA
    elif number == 16:
        j.bind_run(traj, shot_url="/scamtracker/lookupscam")
        nav_ok = (_lookup_nav(traj, "scam_type=Charity", "state=WA")
                  or _lookup_nav(traj, "scam_type=Charity", "location=WA")
                  or _lookup_nav(traj, "rise up"))
        j.check("nav_lookup_charity_wa", nav_ok,
                "must look up Charity scams in WA (or search Rise Up Youth)")
        j.check("answer_count", contains_count(answer, T16_COUNT), f"reports {T16_COUNT}")
        j.check("answer_amounts", answers.rise_up_amounts(answer),
                f"dollar amounts {T16_AMOUNTS}")
        check_readonly(j)

    # -------------------------------------------------- T17: scam 1388290
    elif number == 17:
        j.bind_run(traj, shot_url=f"/scamtracker/lookupscam/{T17_SCAM_ID}")
        j.check("nav_detail", navigated_path(traj, f"/scamtracker/lookupscam/{T17_SCAM_ID}"),
                f"must open scam report {T17_SCAM_ID}")
        j.check("answer_type", affirms(answer, T17_TYPE), f"scam type {T17_TYPE}")
        j.check("answer_location", affirms(answer, T17_CITY) and affirms(answer, T17_STATE),
                f"reported from {T17_CITY}, {T17_STATE}")
        j.check("answer_amount", affirm_number(answer, T17_AMOUNT), f"dollar amount {T17_AMOUNT}")
        check_readonly(j)

    # -------------------------------------------------- T18: dashboard
    elif number == 18:
        j.bind_run(traj, shot_url="/scamtracker/dashboard")
        j.check("nav_dashboard", navigated_path(traj, "/scamtracker/dashboard"),
                "must open the Scam Tracker heatmap dashboard")
        j.check("answer_figures", answers.dashboard_figures(answer),
                f"state {T18_STATE[0]}, median loss {T18_MEDIAN}, pct {T18_PCT[0]}%")
        check_readonly(j)

    # -------------------------------------------------- T19: gift card keyword
    elif number == 19:
        j.bind_run(traj, shot_url="/scamtracker/lookupscam")
        j.check("nav_lookup_giftcard", _lookup_nav(traj, "gift card"),
                "must search the scam lookup for 'gift card'")
        j.check("answer_types", answers.gift_card_types(answer, T19_MIN_TYPES),
                f"at least {T19_MIN_TYPES} distinct scam types")
        check_readonly(j)

    # -------------------------------------------------- T20: report a scam fields
    elif number == 20:
        j.bind_run(traj, shot_url="/scamtracker/reportscam")
        j.check("nav_report_form", navigated_path(traj, "/scamtracker/reportscam"),
                "must open the Report a Scam page")
        j.check("answer_fields", answers.report_form_fields(answer, T20_MIN_FIELDS),
                f"at least {T20_MIN_FIELDS} form fields")
        check_readonly(j)

    # -------------------------------------------------- T21: CryptoCurrency lookup
    elif number == 21:
        j.bind_run(traj, shot_url="/scamtracker/lookupscam")
        j.check("nav_lookup_crypto", _lookup_nav(traj, "scam_type=CryptoCurrency"),
                "must look up CryptoCurrency scams")
        j.check("answer_count", contains_count(answer, T21_COUNT), f"results shown {T21_COUNT}")
        j.check("answer_newest_location", affirms(answer, T21_CITY) and affirms(answer, T21_STATE),
                f"newest report location {T21_CITY}, {T21_STATE}")
        j.check("answer_newest_date", contains_any(answer, T21_DATE), f"newest report date {T21_DATE[0]}")
        check_readonly(j)

    # -------------------------------------------------- T22: gift card article
    elif number == 22:
        j.bind_run(traj, shot_url=T22_ARTICLE)
        j.check("nav_article", navigated_path(traj, T22_ARTICLE), f"must open the article {T22_ARTICLE}")
        j.check("answer_check", answers.gift_card_check(answer),
                "physical check: sticker over the barcode; why: fraudulent barcode account")
        check_readonly(j)

    # -------------------------------------------------- T23: gym tips article
    elif number == 23:
        j.bind_run(traj, shot_url=T23_ARTICLE)
        j.check("nav_article", navigated_path(traj, T23_ARTICLE), f"must open the article {T23_ARTICLE}")
        j.check("answer_tips", answers.gym_tips(answer, 2),
                "at least two pre-signing tips (fitness goals / budget / priorities / tour / contract)")
        check_readonly(j)

    # -------------------------------------------------- T24: torch awards article
    elif number == 24:
        j.bind_run(traj, shot_url=T24_ARTICLE)
        j.check("nav_article", navigated_path(traj, T24_ARTICLE), f"must open the article {T24_ARTICLE}")
        j.check("answer_org_and_purpose", answers.torch_awards(answer),
                "announced by IABBB; celebrates ethics / trust in the marketplace")
        check_readonly(j)

    # -------------------------------------------------- T25: weight loss scam alert
    elif number == 25:
        j.bind_run(traj, shot_url=T25_ARTICLE)
        j.check("nav_article", navigated_path(traj, T25_ARTICLE), f"must open the article {T25_ARTICLE}")
        j.check("answer_scam_and_reports", answers.weight_loss_scam(answer),
                "deepfake videos promoting LipoMax; over 170 reports")
        check_readonly(j)

    # -------------------------------------------------- T26: carol favorites
    elif number == 26:
        j.bind_run(traj, shot_url="/account")
        j.check("nav_signin", _signed_in(traj, "carol.d@test.com"),
                "must sign in as carol.d@test.com")
        j.check("nav_account", navigated_path(traj, "/account"), "must open the account page")
        j.check("answer_business", affirms(answer, T26_BUSINESS), f"favorite business {T26_BUSINESS}")
        j.check("answer_city_state", affirms(answer, T26_CITY) and affirms(answer, T26_STATE),
                f"city/state {T26_CITY}, {T26_STATE}")
        j.check("answer_rating", affirms(answer, T26_RATING), f"BBB rating {T26_RATING}")
        check_readonly(j)

    # -------------------------------------------------- T27: carol review
    elif number == 27:
        j.bind_run(traj, shot_url="/account")
        j.check("nav_signin", _signed_in(traj, "carol.d@test.com"),
                "must sign in as carol.d@test.com")
        j.check("nav_account", navigated_path(traj, "/account"), "must open the account page")
        j.check("answer_business", affirms(answer, T27_BUSINESS), f"review business {T27_BUSINESS}")
        j.check("answer_rating",
                bool(re.search(rf"{T27_STARS}\s*(of|out\s*of|/)\s*(5|five)|\b{T27_STARS}\s*stars?\b|{T27_STARS}-star", answer or "", re.I)),
                f"star rating {T27_STARS} of 5")
        j.check("answer_date", contains_any(answer, T27_DATE), f"review date {T27_DATE[0]}")
        check_readonly(j)

    # -------------------------------------------------- T28: alice scam report
    elif number == 28:
        j.bind_run(traj, shot_url="/account")
        j.check("nav_signin", _signed_in(traj, "alice.j@test.com"),
                "must sign in as alice.j@test.com")
        j.check("nav_account", navigated_path(traj, "/account"), "must open the account page")
        j.check("answer_type_and_description",
                affirms(answer, T28_TYPE) and answers.alice_scam_description(answer),
                f"scam type {T28_TYPE} with the package-delivery text description")
        check_readonly(j)

    # -------------------------------------------------- T29: Car Tender quote flow
    elif number == 29:
        j.bind_run(traj, shot_url="/get-a-quote/")
        j.check("nav_search", _search_nav(traj, {"auto repair", "Car Tender"}, {"Redmond, WA"}),
                "must search auto repair near Redmond WA (to find Car Tender)")
        j.check("nav_quote_form", any("/get-a-quote/" in u and u.rstrip("/").rsplit("/", 1)[-1].isdigit()
                                      for u in step_urls(traj)),
                "must open a Get a Quote form")
        j.check("nav_quote_form_target", any(f"/get-a-quote/{CAR_TENDER_ID}" in u for u in step_urls(traj)),
                f"must submit the quote form for Car Tender (id {CAR_TENDER_ID})")
        j.check("answer_confirmation", answers.quote_confirmation(answer),
                "confirmation: quote request sent to the business")
        # stateful: exactly one new quote_requests row for Car Tender (brake inspection)
        if before_rows is None or after_rows is None:
            j.check("db_available", False, "cannot read DB snapshots")
        else:
            grown = new_rows(before_rows, after_rows, "quote_requests")
            j.check("db_quote_row", len(grown) == 1 and grown[0]["business_id"] == CAR_TENDER_ID,
                    f"quote_requests rows added: {[(r.get('business_id'), r.get('service_needed')) for r in grown]}")
            if grown:
                svc = (grown[0].get("service_needed") or "").lower()
                j.check("db_quote_service", T29_SERVICE_TOKEN in svc,
                        f"service_needed mentions '{T29_SERVICE_TOKEN}': {grown[0].get('service_needed')!r}")
                j.check("db_quote_contact",
                        all(grown[0].get(k) for k in ("name", "email", "phone")),
                        "name/email/phone filled")
            changed = tables_unchanged(init_db, after_db, ignore=("quote_requests",))
            j.check("db_other_tables_unchanged", changed == [], f"changed tables: {changed}")

    else:
        j.check("unknown_task", False, f"no verifier for task {number}")

    j.emit()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1].isdigit():
        grade(int(sys.argv[1]))
    else:
        print("usage: grade.py <task-number> --run_dir DIR [...]", file=sys.stderr)
        sys.exit(2)

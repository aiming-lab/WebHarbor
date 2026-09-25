"""Shared deterministic americas_health_rankings task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED here (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (numbers / decimals / tokens,
     negation-aware, digit-bounded)
  4. DB after-state: read-only tasks may only touch reading_history; stateful
     tasks must produce exactly the requested rows and preserve everything else

Data-layer note (review finding R1, fixed): the seed now ingests the UNION of all
trendGraphQL methodology series (the original build truncated at row 0, which
froze 40 rendered measure pages on the pre-break slice). Obesity/Smoking now
serve the 2024 slice (Obesity: top Colorado 25.0%, last-ranked West Virginia
41.4% rank 49 of 49 ranked states, DC unranked; California 29.1% rank 6,
matching the state summary table; Smoking: lowest Utah 5.7%). The T1/T8/T9
anchors below are derived from that fixed 2024 slice and the frozen seed DB.
"""
import json
import re

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, one, tables_unchanged,
    new_rows, navigated_path, navigated_query, affirms, affirms_any,
    affirms_word, contains_number, contains_decimal, contains_rank,
    contains_word_number, affirm_number, step_text, shot_at,
)

# ---------------------------------------------------------------- ground truth
# T0: Teen Suicide (2021-2023) — top-ranked state + value (deaths per 100,000).
T0_TOP = ("New Jersey", 5.1)
# T1: Obesity — state ranked last + value (fixed 2024 slice; 49 ranked states, DC unranked).
T1_BOTTOM = ("West Virginia", 41.4)
# T2: Frequent Mental Distress — U.S. trend: 2011 value and latest (2024) value.
T2_2011, T2_LATEST = 11.7, 15.6
# T3: Air Pollution (2022-2024) — worst-ranked state + micrograms per cubic meter.
T3_WORST = ("California", 11.7)
# T4: Mental Health Providers (September 2025) — highest state + per-100,000 value.
T4_TOP = ("Alaska", 822.0)
# T5: Excessive Drinking (2024) — Montana value + rank.
T5_MT = (22.5, 49)
# T6: Drinking Water Violations — data source office/agency.
T6_SOURCE = ("environmental protection agency", "safe drinking water information system")
# T7: Low Birth Weight (2023) — three top-ranked states (lowest rates).
T7_TOP3 = [("Alaska", 6.7), ("New Hampshire", 6.8), ("Idaho", 6.9)]
# T8: Obesity — California value + rank in the full state table (fixed 2024 slice).
T8_CA = (29.1, 6)
# T9: Smoking — lowest adult smoking state + value (fixed 2024 slice).
T9_TOP = ("Utah", 5.7)
# T10/T11: California overall rank — 2025 Annual / 2026 Senior editions.
T10_CA_ANNUAL = 24
T11_CA_SENIOR = 20
# T12: Texas 2025 Annual — most positive impact measure + its Texas rank.
T12_MEASURE = "premature death racial disparity"
T12_RANK = 4
# T13: Massachusetts challenges (state summary page).
T13_CHALLENGES = ("high income inequality", "high preventable hospitalization rate",
                  "severe housing problems")
# T14: New Hampshire Physical Environment score + rank (2025 Annual).
T14_NH_PE = (0.513, 9)
# T15: Montana strengths (state summary page).
T15_STRENGTHS = ("low prevalence of obesity", "high school completion", "chlamydia")
# T16: 2025 Annual Report main page — download count + distinctive titles.
T16_COUNT = 7
T16_TITLES = ("executive brief", "state summaries", "economic hardship index",
              "measures table", "infographics", "report data")
# T17: 2025 Annual Report overall state rankings — No. 1 and No. 50.
T17_FIRST, T17_LAST = ("New Hampshire", 1), ("Louisiana", 50)
# T18: 2026 Senior Report — county-level maps download title + total downloads.
T18_MAPS = "risk of social isolation"
T18_COUNT = 7
# T19: 2025 Annual Report California state summary — Cancer Screenings value + rank.
T19_CA_CS = (58.5, 45)
# T20: Appendix measures table — survey source of the Smoking measure (2024).
T20_SOURCE = ("behavioral risk factor surveillance system",)
T20_SOURCE_ALT = ("centers for disease control", "cdc")
# T21: caregiving article — report featuring caregiver data + org abbreviation.
T21_REPORT = "senior report"
T21_ABBR = "NAC"
# T22: Joseph Kanter article — decades served as a vital resource.
T22_DECADES = "three decades"
# T23: Cancer Screenings definition tokens.
T23_TOKENS = ("40-74", "mammogram", "45-75", "colorectal cancer screening")
# T24: Behavioral Health category — count + all measure names.
T24_COUNT = 10
T24_MEASURES = ("depression", "drug deaths", "excessive drinking", "flourishing",
                "frequent mental distress", "mental health conditions",
                "non-medical drug use", "postpartum anxiety", "postpartum depression",
                "suicide")
# T25: category containing 'Suicide - Age 65+'.
T25_CATEGORY = "additional older adult measures"
# T26: Sleep Health category — the two measures.
T26_MEASURES = ("insufficient sleep", "sleep position")
# T27/T28/T34: demo accounts + seeded bookmark sets.
ALICE, BOB, CAROL = "alice.j@test.com", "bob.c@test.com", "carol.d@test.com"
T27_FINAL_COUNT = 2          # alice: seed set (Frequent Mental Distress + Obesity) remains
T28_REMAINING = ("Obesity", "California")
T34_TITLE = "Montana"
# T29: newsletter signup confirmation + fixture.
T29_FLASH = "thank you for signing up for updates"
T29_NAME, T29_EMAIL = "Jordan Lee", "jordan.lee@example.com"
# T30: inquiry confirmation + fixture.
T30_FLASH = "inquiry has been submitted"
T30_NAME, T30_EMAIL, T30_ORG = "Dana Torres", "dana.torres@example.com", "State Health Institute"
# T31: FAQ — number of reports released each year + names.
T31_NAMES = ("annual report", "senior report", "health of women and children")
# T32: FAQ — who guides each report.
T32_WHO = "advisory committee"
# T33: Health Topics — Senior Health description.
T33_TOKENS = ("50+", "senior report")

READ_ONLY = (set(range(0, 27)) | {31, 32, 33})   # every task except 27, 28, 29, 30, 34

MEASURE_PAGES = {
    0: "/explore/measures/teen_suicide",
    1: "/explore/measures/Obesity",
    2: "/explore/measures/mental_distress",
    3: "/explore/measures/air",
    4: "/explore/measures/MHP",
    5: "/explore/measures/ExcessDrink",
    6: "/explore/measures/hb_water_violation",
    7: "/explore/measures/birthweight",
    8: "/explore/measures/Obesity",
    9: "/explore/measures/Smoking",
}


def grade(number):
    args = parse_args()
    j = Judge(f"America's Health Rankings--{number}")
    t = load_run(args.run_dir)
    fa = (t.get("final_answer") or "").strip()
    init_db = args.initial_db or resolve_db(None, args.container, "instance_seed")
    after_db = args.after_db or resolve_db(None, args.container, "instance")
    b, a = rows(init_db), rows(after_db)
    j.bind_run(t, require_answer=True)
    from reviewed import check
    check(j, number, t, b, a)

    # ---------------- shared gates ----------------
    if number in READ_ONLY:
        changed = tables_unchanged(init_db, after_db)
        ok = changed is not None and set(changed) <= {"reading_history"}
        j.check("db_readonly", ok,
                f"changed tables: {changed}" if changed else "all content tables preserved")

    # ---------------- per-task checks ----------------
    if number in MEASURE_PAGES:
        page = MEASURE_PAGES[number]
        ok, note = shot_at(t, page)
        j.check("shot_target_page", ok, note)

    if number == 0:
        j.check("measure_page_visited", navigated_path(t, "/explore/measures/teen_suicide"),
                "Teen Suicide measure page")
        j.check("answer_state", affirms(fa, T0_TOP[0]), fa)
        j.check("answer_value", contains_decimal(fa, T0_TOP[1]), fa)

    elif number == 1:
        j.check("measure_page_visited", navigated_path(t, "/explore/measures/Obesity"),
                "Obesity measure page")
        j.check("answer_state", affirms(fa, T1_BOTTOM[0]), fa)
        j.check("answer_value", contains_decimal(fa, T1_BOTTOM[1]), fa)
        j.check("answer_is_last", contains_rank(fa, 49) or affirms_any(fa, ["last", "worst", "least healthy"]), fa)

    elif number == 2:
        j.check("measure_page_visited", navigated_path(t, "/explore/measures/mental_distress"),
                "Frequent Mental Distress measure page")
        j.check("answer_2011", contains_decimal(fa, T2_2011), fa)
        j.check("answer_latest", contains_decimal(fa, T2_LATEST), fa)

    elif number == 3:
        j.check("measure_page_visited", navigated_path(t, "/explore/measures/air"),
                "Air Pollution measure page")
        j.check("answer_state", affirms(fa, T3_WORST[0]), fa)
        j.check("answer_value", contains_decimal(fa, T3_WORST[1]), fa)
        j.check("answer_is_worst", contains_rank(fa, 50) or affirms_any(fa, ["last", "worst", "highest"]), fa)

    elif number == 4:
        j.check("measure_page_visited", navigated_path(t, "/explore/measures/MHP"),
                "Mental Health Providers measure page")
        j.check("answer_state", affirms(fa, T4_TOP[0]), fa)
        j.check("answer_value", contains_decimal(fa, T4_TOP[1]) or contains_number(fa, 822), fa)

    elif number == 5:
        j.check("measure_page_visited", navigated_path(t, "/explore/measures/ExcessDrink"),
                "Excessive Drinking measure page")
        j.check("answer_value", contains_decimal(fa, T5_MT[0]), fa)
        j.check("answer_rank", contains_rank(fa, T5_MT[1]), fa)

    elif number == 6:
        j.check("measure_page_visited",
                navigated_path(t, "/explore/measures/hb_water_violation"),
                "Drinking Water Violations measure page")
        j.check("answer_source_agency", affirms(fa, T6_SOURCE[0]), fa)
        j.check("answer_source_system", affirms(fa, T6_SOURCE[1]), fa)

    elif number == 7:
        j.check("measure_page_visited", navigated_path(t, "/explore/measures/birthweight"),
                "Low Birth Weight measure page")
        for state, value in T7_TOP3:
            j.check(f"answer_{state.lower().replace(' ', '_')}",
                    affirms(fa, state) and contains_decimal(fa, value), fa)

    elif number == 8:
        j.check("measure_page_visited", navigated_path(t, "/explore/measures/Obesity"),
                "Obesity measure page")
        j.check("answer_state", affirms(fa, "california"), fa)
        j.check("answer_value", contains_decimal(fa, T8_CA[0]), fa)
        j.check("answer_rank", contains_rank(fa, T8_CA[1]), fa)

    elif number == 9:
        j.check("measure_page_visited", navigated_path(t, "/explore/measures/Smoking"),
                "Smoking measure page")
        j.check("answer_state", affirms(fa, T9_TOP[0]), fa)
        j.check("answer_value", contains_decimal(fa, T9_TOP[1]), fa)

    elif number == 10:
        j.check("state_page_visited", navigated_path(t, "/explore/states/CA"),
                "California state summary page")
        j.check("answer_rank", contains_rank(fa, T10_CA_ANNUAL), fa)
        j.check("answer_edition_context", affirms(fa, "annual report"), fa)

    elif number == 11:
        j.check("state_page_senior",
                navigated_query(t, "/explore/states/CA", rank="senior")
                or navigated_query(t, "/explore/states/CA", edition="senior"),
                "California state page switched to the Senior Report edition")
        j.check("answer_rank", contains_rank(fa, T11_CA_SENIOR), fa)
        j.check("answer_edition_context", affirms(fa, "senior report"), fa)

    elif number == 12:
        j.check("state_page_visited", navigated_path(t, "/explore/states/TX"),
                "Texas state summary page")
        j.check("answer_measure", affirms(fa, T12_MEASURE), fa)
        j.check("answer_rank", contains_rank(fa, T12_RANK), fa)

    elif number == 13:
        j.check("state_page_visited", navigated_path(t, "/explore/states/MA"),
                "Massachusetts state summary page")
        for i, token in enumerate(T13_CHALLENGES):
            j.check(f"answer_challenge_{i + 1}", affirms(fa, token), fa)

    elif number == 14:
        j.check("state_page_visited", navigated_path(t, "/explore/states/NH"),
                "New Hampshire state summary page")
        j.check("answer_score", contains_decimal(fa, T14_NH_PE[0], digits=3), fa)
        j.check("answer_rank", contains_rank(fa, T14_NH_PE[1]), fa)
        j.check("answer_category", affirms(fa, "physical environment"), fa)

    elif number == 15:
        j.check("state_page_visited", navigated_path(t, "/explore/states/MT"),
                "Montana state summary page")
        for i, token in enumerate(T15_STRENGTHS):
            j.check(f"answer_strength_{i + 1}", affirms(fa, token), fa)

    elif number == 16:
        j.check("report_main_visited", navigated_path(t, "/publications/reports/2025-annual-report"),
                "2025 Annual Report main page")
        j.check("answer_count", contains_word_number(fa, T16_COUNT), fa)
        missing = [tok for tok in T16_TITLES if not affirms(fa, tok)]
        j.check("answer_titles", not missing, f"missing: {missing}" if missing else "all download titles")

    elif number == 17:
        j.check("rankings_page_visited",
                navigated_path(t, "/publications/reports/2025-annual-report/state-rankings")
                or navigated_path(t, "/publications/reports/2025-annual-report"),
                "2025 Annual Report (State Rankings section or main page)")
        j.check("answer_first_state", affirms(fa, T17_FIRST[0]), fa)
        j.check("answer_first_rank",
                contains_rank(fa, T17_FIRST[1]) or affirms_any(fa, ["first", "healthiest"]), fa)
        j.check("answer_last_state", affirms(fa, T17_LAST[0]), fa)
        j.check("answer_last_rank",
                contains_rank(fa, T17_LAST[1]) or affirms_any(fa, ["last", "least healthy"]), fa)

    elif number == 18:
        j.check("report_main_visited", navigated_path(t, "/publications/reports/2026-senior-report"),
                "2026 Senior Report main page")
        j.check("answer_maps_title", affirms(fa, T18_MAPS), fa)
        j.check("answer_count", contains_word_number(fa, T18_COUNT), fa)

    elif number == 19:
        j.check("report_ca_summary_visited",
                navigated_path(t, "/publications/reports/2025-annual-report/state-summaries-california"),
                "2025 Annual Report California state summary section")
        j.check("answer_measure", affirms(fa, "cancer screenings"), fa)
        j.check("answer_value", contains_decimal(fa, T19_CA_CS[0]), fa)
        j.check("answer_rank", contains_rank(fa, T19_CA_CS[1]), fa)

    elif number == 20:
        j.check("appendix_measures_table_visited",
                navigated_path(t, "/publications/reports/2025-annual-report/appendix-measures-table"),
                "2025 Annual Report Appendix Measures Table")
        j.check("answer_measure", affirms(fa, "smoking"), fa)
        j.check("answer_source", affirms(fa, T20_SOURCE[0]), fa)
        j.check("answer_source_org",
                affirms_any(fa, list(T20_SOURCE_ALT)), fa)

    elif number == 21:
        j.check("article_visited",
                navigated_path(t, "/publications/articles/documenting-the-human-experience-means-measuring-caregiving"),
                "caregiving article")
        j.check("answer_report", affirms(fa, T21_REPORT), fa)
        j.check("answer_abbreviation",
                affirms_word(fa, T21_ABBR) or affirms(fa, "national alliance for caregiving"), fa)

    elif number == 22:
        j.check("article_visited",
                navigated_path(t, "/publications/articles/from-data-to-action-how-states-can-use-americas-health-rankings-to-drive-and-measure-progress"),
                "Joseph Kanter article")
        j.check("answer_decades", affirms(fa, T22_DECADES), fa)

    elif number == 23:
        j.check("search_used",
                navigated_query(t, "/search", q={"cancer screenings", "cancer+screenings"}),
                "site search for 'cancer screenings'")
        j.check("measure_page_visited",
                navigated_path(t, "/explore/measures/health_screenings_ahr"),
                "Cancer Screenings measure page")
        missing = [tok for tok in T23_TOKENS if not affirms(fa, tok)]
        j.check("answer_definition", not missing, f"missing: {missing}" if missing else "full definition")

    elif number == 24:
        j.check("directory_visited", navigated_path(t, "/explore/measures"),
                "Health Measures directory")
        j.check("answer_count", contains_word_number(fa, T24_COUNT), fa)
        missing = [tok for tok in T24_MEASURES if not affirms(fa, tok)]
        j.check("answer_names", not missing, f"missing: {missing}" if missing else "all 10 measures")
        j.check("answer_category", affirms(fa, "behavioral health"), fa)

    elif number == 25:
        j.check("directory_visited", navigated_path(t, "/explore/measures"),
                "Health Measures directory")
        j.check("answer_measure", affirms(fa, "suicide - age 65+") or affirms(fa, "suicide – age 65+"), fa)
        j.check("answer_category", affirms(fa, T25_CATEGORY), fa)

    elif number == 26:
        j.check("directory_visited", navigated_path(t, "/explore/measures"),
                "Health Measures directory")
        j.check("answer_category", affirms(fa, "sleep health"), fa)
        missing = [tok for tok in T26_MEASURES if not affirms(fa, tok)]
        j.check("answer_names", not missing, f"missing: {missing}" if missing else "both measures")

    elif number == 27:
        _save_remove_task(j, t, a, b, fa)

    elif number == 28:
        _remove_task(j, t, a, b, fa)

    elif number == 29:
        _newsletter_task(j, t, a, b, fa)

    elif number == 30:
        _inquiry_task(j, t, a, b, fa)

    elif number == 31:
        j.check("faq_visited", navigated_path(t, "/faq"), "FAQs page")
        j.check("answer_count", contains_word_number(fa, 3), fa)
        missing = [tok for tok in T31_NAMES if not affirms(fa, tok)]
        j.check("answer_names", not missing, f"missing: {missing}" if missing else "three report names")

    elif number == 32:
        j.check("faq_visited", navigated_path(t, "/faq"), "FAQs page")
        j.check("answer_who", affirms(fa, T32_WHO), fa)

    elif number == 33:
        j.check("topics_visited", navigated_path(t, "/health-topics"), "Health Topics page")
        missing = [tok for tok in T33_TOKENS if not affirms(fa, tok)]
        j.check("answer_description", not missing, f"missing: {missing}" if missing else "Senior Health description")

    elif number == 34:
        _save_state_task(j, t, a, b, fa)

    else:
        j.check("task_exists", False, f"no grading logic for task {number}")

    j.emit()


# ---------------------------------------------------------------- stateful helpers
def _db_available(j, a, b):
    if a is None or b is None:
        j.check("db_available", False, "initial/after DB unavailable")
        return False
    if a.get("users") != b.get("users"):
        j.check("users_table_preserved", False, "users table changed during the run")
        return True
    j.check("users_table_preserved", True, "users table unchanged")
    return True


def _observed_text(t):
    """Concatenated step observed page text (post-action page render only)."""
    return " ".join(str(s.get("observed_text") or "") for s in t.get("steps") or [])


def _save_remove_task(j, t, a, b, fa):
    """T27: alice saves Teen Suicide then removes it; final list = seed set (2).
    The save-then-remove round trip leaves the DB byte-identical to the seed
    set, so the final DB alone cannot distinguish an honest run from a
    visit-only shortcut: the trajectory must also carry the save and remove
    confirmations as they render on the page (flash message and the
    saved-state button) - a visit-only run produces neither."""
    if not _db_available(j, a, b):
        return
    j.check("login_visited", navigated_path(t, "/login"), "logged in as alice")
    j.check("measure_page_visited", navigated_path(t, "/explore/measures/teen_suicide"),
            "Teen Suicide measure page")
    j.check("saved_list_visited", navigated_path(t, "/account/saved") or navigated_path(t, "/account"),
            "saved items page")
    observed = _observed_text(t)
    j.check("save_action_evidence",
            affirms(observed, "saved to your account") or "Saved ✓ (remove)" in observed,
            "page render shows the save confirmation (flash or saved-state button)")
    j.check("remove_action_evidence",
            affirms(observed, "removed from your saved items"),
            "page render shows the remove confirmation flash")
    alice = one(b, "users", email=ALICE)
    after_rows = [r for r in a["bookmarks"] if r["user_id"] == alice["id"]]
    slugs = sorted(r["item_slug"] for r in after_rows)
    j.check("alice_final_bookmarks", slugs == ["Obesity", "mental_distress"],
            f"alice bookmarks after run: {slugs}")
    j.check("teen_suicide_not_saved", "teen_suicide" not in slugs, "removed (or never saved)")
    j.check("other_users_preserved",
            [(r["user_id"], r["kind"], r["item_slug"]) for r in a["bookmarks"] if r["user_id"] != alice["id"]]
            == [(r["user_id"], r["kind"], r["item_slug"]) for r in b["bookmarks"] if r["user_id"] != alice["id"]],
            "bob/carol/david bookmark sets untouched")
    j.check("no_new_users", len(a["users"]) == len(b["users"]), "users table unchanged")
    j.check("no_newsletter_rows", not a["newsletter_signups"], "no newsletter signup rows")
    j.check("no_inquiry_rows", not a["inquiries"], "no inquiry rows")
    j.check("answer_count", contains_word_number(fa, T27_FINAL_COUNT), fa)
    j.check("answer_items", affirms(fa, "mental distress") and affirms(fa, "obesity"), fa)


def _remove_task(j, t, a, b, fa):
    """T28: bob removes the frequent mental distress bookmark; Obesity + California remain."""
    if not _db_available(j, a, b):
        return
    j.check("login_visited", navigated_path(t, "/login"), "logged in as bob")
    j.check("target_page_visited",
            navigated_path(t, "/explore/measures/mental_distress")
            or navigated_path(t, "/account/saved") or navigated_path(t, "/account"),
            "frequent mental distress page or saved items")
    bob = one(b, "users", email=BOB)
    after_rows = sorted((r["kind"], r["item_slug"]) for r in a["bookmarks"] if r["user_id"] == bob["id"])
    j.check("bob_final_bookmarks", after_rows == [("measure", "Obesity"), ("state", "CA")],
            f"bob bookmarks after run: {after_rows}")
    j.check("fmd_removed", ("measure", "mental_distress") not in after_rows, "removed")
    j.check("other_users_preserved",
            [(r["user_id"], r["kind"], r["item_slug"]) for r in a["bookmarks"] if r["user_id"] != bob["id"]]
            == [(r["user_id"], r["kind"], r["item_slug"]) for r in b["bookmarks"] if r["user_id"] != bob["id"]],
            "alice/carol/david bookmark sets untouched")
    j.check("answer_remaining", affirms(fa, "obesity") and affirms(fa, "california"), fa)
    j.check("answer_mentions_removal", affirms(fa, "mental distress"), fa)


def _newsletter_task(j, t, a, b, fa):
    """T29: newsletter signup with Jordan Lee; one row, everything else preserved."""
    if not _db_available(j, a, b):
        return
    j.check("form_evidence", T29_EMAIL in step_text(t) or T29_NAME in step_text(t),
            "trajectory shows the signup form being filled")
    new = new_rows(b, a, "newsletter_signups")
    ok = (len(new) == 1 and new[0]["name"] == T29_NAME and new[0]["email"] == T29_EMAIL)
    j.check("newsletter_row_created", ok, f"newsletter rows: {new}")
    changed = [tb for tb in sorted(set(b) | set(a))
                if tb != "reading_history" and b.get(tb) != a.get(tb)]
    j.check("only_newsletter_changed", set(changed) <= {"newsletter_signups"},
            f"changed tables: {changed}")
    j.check("answer_confirmation", affirms(fa, T29_FLASH), fa)


def _inquiry_task(j, t, a, b, fa):
    """T30: inquiry from Dana Torres; one row, everything else preserved."""
    if not _db_available(j, a, b):
        return
    j.check("inquiry_page_visited", navigated_path(t, "/about/page/submit-an-inquiry"),
            "Submit An Inquiry page")
    new = new_rows(b, a, "inquiries")
    ok = (len(new) == 1 and new[0]["name"] == T30_NAME and new[0]["email"] == T30_EMAIL
          and new[0]["organization"] == T30_ORG)
    j.check("inquiry_row_created", ok, f"inquiry rows: {new}")
    if ok:
        comment = (new[0]["comment"] or "").lower()
        j.check("inquiry_comment_topic", "research" in comment, f"comment: {new[0]['comment'][:120]}")
    j.check("only_inquiry_changed",
            set(changed := [tb for tb in sorted(set(b) | set(a))
                            if tb != "reading_history" and b.get(tb) != a.get(tb)]) <= {"inquiries"},
            f"changed tables: {changed}")
    j.check("answer_confirmation", affirms(fa, T30_FLASH), fa)


def _save_state_task(j, t, a, b, fa):
    """T34: carol saves the Montana state page; title 'Montana' on Saved Items."""
    if not _db_available(j, a, b):
        return
    j.check("login_visited", navigated_path(t, "/login"), "logged in as carol")
    j.check("state_page_visited", navigated_path(t, "/explore/states/MT"), "Montana state page")
    j.check("saved_list_visited", navigated_path(t, "/account/saved") or navigated_path(t, "/account"),
            "saved items page")
    carol = one(b, "users", email=CAROL)
    new = [r for r in a["bookmarks"] if r["user_id"] == carol["id"]
           and not any(r2["id"] == r["id"] for r2 in b["bookmarks"])]
    ok = (len(new) == 1 and new[0]["kind"] == "state" and new[0]["item_slug"] == "MT"
          and new[0]["title"] == T34_TITLE)
    j.check("montana_bookmark_created", ok, f"new carol bookmarks: {new}")
    j.check("carol_seed_preserved",
            sorted((r["kind"], r["item_slug"]) for r in a["bookmarks"] if r["user_id"] == carol["id"]
                   and any(r2["id"] == r["id"] for r2 in b["bookmarks"]))
            == [("measure", "Obesity"), ("measure", "mental_distress")],
            "carol's two seeded bookmarks untouched")
    j.check("other_users_preserved",
            [(r["user_id"], r["kind"], r["item_slug"]) for r in a["bookmarks"] if r["user_id"] != carol["id"]]
            == [(r["user_id"], r["kind"], r["item_slug"]) for r in b["bookmarks"] if r["user_id"] != carol["id"]],
            "alice/bob/david bookmark sets untouched")
    j.check("answer_title", affirms(fa, "montana"), fa)

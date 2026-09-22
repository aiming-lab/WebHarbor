"""Shared deterministic AMERICAN EXPRESS task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED here (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (numbers / money / tokens,
     negation-aware, with bounded word forms)
  4. DB after-state: read-only tasks leave every table unchanged; stateful
     tasks must produce exactly the requested rows/fields and preserve the rest

Frozen seed facts the checks are anchored on (instance_seed/american_express.db,
md5 36700ac11ea5c6b5c2df61e02d0ea206, regenerated deterministically at image
build time from tracked seed_data.py):
  13 cards, 10 categories, 4 banking products, 10 CD terms, 3 Amex Offers,
  4 redemption options, 4 users (alice/bob/carol/david), 8 user cards,
  5 bank accounts, 89 transactions, 24 statements, 11 payments,
  2 offer enrollments, 0 applications.
"""
import re
import sys

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, one, preserved, new_rows,
    tables_unchanged, navigated_path, navigated_query, contains_count,
    contains_money, affirm_number, affirm_money, affirms, affirms_any,
    contains_any, contains_number, norm, final_answer, step_text, shot_at,
)
import answers

# ---------------------------------------------------------------- ground truth
# Cards (frozen seed; asserted against the DB in test_verifiers.py)
PLATINUM_FEE = 895
PLATINUM_APR = ("19.74", "28.74")
GOLD_MAX_POINTS = 100000
GOLD_SPEND = 8000
ASPIRE_FEE = 550
BRILLIANT_CREDIT_MONTH = 25          # $25 / month
BRILLIANT_CREDIT_ANNUAL = 300        # $300 / year
DELTA_GOLD_FEE_TEXT = "$0 introductory annual fee for the first year, then $150"
DELTA_PLATINUM_FEE = 350
DELTA_GOLD_MILES = 80000
DELTA_PLATINUM_MILES = 90000
BCP_MARKET = 6                       # 6% at U.S. supermarkets
BCE_MARKET = 3                       # 3% at U.S. supermarkets
BCP_FEE_VALUE = 95                   # "$0 intro annual fee for the first year, then $95"
TRAVEL_CATEGORY_COUNT = 11
TRAVEL_NO_FEE = ("Delta SkyMiles\u00ae Blue American Express Card",
                 "Hilton Honors American Express Card")
RESERVE_FEE = 650
BEVY_FEE = 250
BEVY_POINTS = 125000
BEVY_CREDIT = 150
CD_BEST_APY = "4.25"
CD_BEST_TERM = 10
CD_350_TERMS = (11, 12, 14)
HYSA_APY = "3.00"
HYSA_NATIONAL = "0.38"
CHECKING_OFFER = 300
CHECKING_DEADLINE = "02/01/2027"
CHECKING_DEPOSITS = 7500
CHECKING_DAYS = 90
LOAN_APR = ("6.99", "19.99")
LOAN_EXAMPLE = (10000, 36, "12.98", "336.85", 12123)

ALICE_PLATINUM_BALANCE = 6126.88
ALICE_BCE_BALANCE = 589.68
ALICE_TOTAL_POINTS = 84250
ALICE_STMT3 = (9341.98, 467.10, "09/24/2026", "Due")      # Platinum 08/31/2026
GIFT_CARD_POINTS = 10000
ALICE_REMAINING = 74250
BOB_RESTAURANTS = [                                  # Gold card Restaurants
    ("Tartine Bakery", 38.40), ("Zuni Garden Restaurant", 121.30),
    ("State Bird Provisions", 178.90), ("Blue Bottle Coffee", 22.75),
    ("Swan Oyster Depot", 145.60), ("Rich Table", 198.25),
    ("Napa Farmhouse Kitchen", 156.75),
]
BOB_RESTAURANTS_TOTAL = 861.95
BOB_PAY_AMOUNT = 250.0
TULA_HEADLINE = "Spend $75 or more, earn $15 back"
TULA_EXPIRES = "10/01/2026"
TULA_MIN_SPEND = 75
CAROL_RECENT = ("Whole Foods Market #338", 98.30, "09/16/2026")   # on Hilton Surpass
CAROL_SURPASS_MARKET = 12          # 12X Hilton Honors on eligible Hilton purchases
CAROL_BRILLIANT_HOTEL = 6          # 6X at Marriott Bonvoy hotels
CAROL_PAY_AMOUNT = 400.0
DAVID_DELTA_BALANCE = 1527.10
DAVID_BCP_BALANCE = 111.10
DAVID_DELTA_AVAILABLE = 9472.90
DAVID_PHONE = "+1 (206) 555-0199"
BOUQS_CARD = "Blue Cash Preferred\u00ae Card"
BOUQS_ADDED = "08/12/2026"
ALICE_BCE_STATEMENTS = 3
ALICE_BCE_RECENT = (961.20, "Due")
DAVID_BCP_GROCERY_STREAM_COUNT = 9
DAVID_STREAMING_TOTAL = 84.96

# URL anchors (paths only — host/port agnostic so review and benchmark ports both pass)
P_PLATINUM = "/credit-cards/card/platinum/"
P_GOLD = "/credit-cards/card/gold-card/"
P_ASPIRE = "/credit-cards/card/hilton-honors-aspire/"
P_BRILLIANT = "/credit-cards/card/marriott-bonvoy-brilliant/"
P_COMPARE_DELTA = "/credit-cards/compare/"
P_COMPARE_DELTA_CARDS = ("delta-skymiles-gold-american-express-card",
                         "delta-skymiles-platinum-american-express-card")
P_COMPARE_BLUE = ("blue-cash-preferred", "blue-cash-everyday")
P_CATEGORY_TRAVEL = "/credit-cards/category/travel-rewards/"
P_CARDS_INDEX = "/credit-cards/"
P_LOUNGES = "/travel/lounges/"
P_RESERVE = "/credit-cards/card/delta-skymiles-reserve-american-express-card/"
P_BEVY = "/credit-cards/card/marriott-bonvoy-bevy/"
P_CD = "/banking/cd/"
P_HYSA = "/banking/high-yield-savings/"
P_CHECKING = "/banking/checking/"
P_LOANS = "/banking/personal-loans/"
P_APPLY_BCE = "/credit-cards/card/blue-cash-everyday/apply/"
P_LOGIN = "/login"
P_ACCOUNT = "/account/"
P_CARD_UC3 = "/account/cards/3/"
P_CARD_UC5 = "/account/cards/5/"
P_CARD_UC6 = "/account/cards/6/"
P_CARD_UC7 = "/account/cards/7/"
P_CARD_UC1 = "/account/cards/1/"
P_CARD_UC2 = "/account/cards/2/"
P_STATEMENTS = "/account/statements/"
P_STMT3 = "/account/statements/3/"
P_REWARDS = "/account/rewards/"
P_PAYMENTS = "/account/payments/"
P_OFFERS = "/account/offers/"
P_BENEFITS = "/account/benefits/"
P_PROFILE = "/account/profile/"

ALICE, BOB, CAROL, DAVID = "alice.j@test.com", "bob.c@test.com", "carol.d@test.com", "david.k@test.com"
DEMO_PASSWORD = "TestPass123!"

CONFIRMATION_RE = re.compile(r"\bP[0-9A-F]{7}\b")


# ---------------------------------------------------------------- helpers
def _compare_nav(traj, slugs):
    """True when a step hits /credit-cards/compare/ carrying both slugs in any order."""
    from verify_lib import step_urls, url_path, url_query
    want = {s for s in slugs}
    for url in step_urls(traj):
        if (url_path(url).rstrip("/") or "/") != "/credit-cards/compare":
            continue
        got = {chunk.split("=", 1)[1] for chunk in url_query(url).split("&") if chunk.startswith("cards=")}
        values = set()
        for v in got:
            values |= set(v.split(","))
        if want <= values:
            return True
    return False


def _readonly(judge, init_db, after_db):
    changed = tables_unchanged(init_db, after_db)
    judge.check("db_readonly", changed == [],
                f"changed tables: {changed}" if changed else "all tables byte-identical to seed")


def _login_nav(judge, traj, account_subpaths):
    judge.check("nav_login", navigated_path(traj, P_LOGIN), "opened the login page")
    for p in account_subpaths:
        judge.check(f"nav{p}", navigated_path(traj, p), f"opened {p} (auth-gated)")


def _shot(judge, traj, substr):
    ok, note = shot_at(traj, substr)
    judge.check(f"shot[{substr[:40]}]", ok, note)


def _answer_tokens(judge, final, checks):
    """checks: list of (name, bool, evidence)."""
    for name, ok, ev in checks:
        judge.check(name, ok, ev)


def _dec(final, literal):
    return answers.contains_decimal(final, literal)


def _fee_like(final, value):
    return contains_money(final, value) or affirm_money(final, value)


def _count_word(final, n):
    return contains_count(final, n)


# ---------------------------------------------------------------- per-task grading
def grade_0(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_PLATINUM)
    judge.check("nav_platinum_page", navigated_path(traj, P_PLATINUM), "opened the Platinum Card page")
    _shot(judge, traj, P_PLATINUM)
    _answer_tokens(judge, final, [
        ("ans_annual_fee_895", _fee_like(final, PLATINUM_FEE), "fee $895"),
        ("ans_apr_range", answers.apr_range(final, *PLATINUM_APR), "19.74%-28.74% variable purchase APR"),
        ("ans_charge_card", answers.is_charge_card(final), "classified as a charge Card"),
    ])
    _readonly(judge, init_db, after_db)


def grade_1(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_GOLD)
    judge.check("nav_gold_page", navigated_path(traj, P_GOLD), "opened the Gold Card page")
    _shot(judge, traj, P_GOLD)
    _answer_tokens(judge, final, [
        ("ans_max_points", contains_number(final.replace(",", ""), GOLD_MAX_POINTS)
         or "100000" in final.replace(",", ""), "maximum 100,000 MR points"),
        ("ans_spend_8000", _fee_like(final, GOLD_SPEND), "$8,000 purchases in first 6 months"),
        ("ans_offer_headline", affirms_any(final, ("welcome offer", "as high as", "membership rewards")),
         "welcome-offer headline reported"),
    ])
    _readonly(judge, init_db, after_db)


def grade_2(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_ASPIRE)
    judge.check("nav_aspire_page", navigated_path(traj, P_ASPIRE), "opened the Hilton Aspire page")
    _shot(judge, traj, P_ASPIRE)
    _answer_tokens(judge, final, [
        ("ans_card_named", answers.card_named(final, "Hilton Honors American Express Aspire Card")
         or ("aspire" in norm(final) and "hilton" in norm(final)), "Hilton Honors Aspire named"),
        ("ans_fee_550", _fee_like(final, ASPIRE_FEE), "annual fee $550"),
        ("ans_offer_200k", "200000" in (final or "").replace(",", ""),
         "200,000 Hilton Honors bonus points offer headline"),
        ("ans_diamond_source", "diamond" in norm(final), "Diamond Status mentioned as the anchor benefit"),
    ])
    _readonly(judge, init_db, after_db)


def grade_3(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_BRILLIANT)
    judge.check("nav_brilliant_page", navigated_path(traj, P_BRILLIANT), "opened the Marriott Brilliant page")
    _shot(judge, traj, P_BRILLIANT)
    _answer_tokens(judge, final, [
        ("ans_credit_name", ("brilliant dining credit" in norm(final)), "the $300 Brilliant Dining Credit named"),
        ("ans_month_25", _fee_like(final, BRILLIANT_CREDIT_MONTH) and ("month" in norm(final)),
         "up to $25 per month"),
        ("ans_annual_300", _fee_like(final, BRILLIANT_CREDIT_ANNUAL), "$300 total annual value"),
    ])
    _readonly(judge, init_db, after_db)


def grade_4(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_COMPARE_DELTA)
    ok_nav = _compare_nav(traj, P_COMPARE_DELTA_CARDS) or (
        navigated_path(traj, P_COMPARE_DELTA)
        and all(s in step_text(traj) for s in P_COMPARE_DELTA_CARDS))
    judge.check("nav_compare_delta", ok_nav, "compare page with both Delta Cards")
    _shot(judge, traj, P_COMPARE_DELTA)
    _answer_tokens(judge, final, [
        ("ans_gold_fee", _fee_like(final, 150) and "first year" in norm(final),
         "Delta Gold fee text '$0 introductory annual fee for the first year, then $150'"),
        ("ans_plat_fee_350", _fee_like(final, DELTA_PLATINUM_FEE), "Delta Platinum fee $350"),
        ("ans_gold_miles", contains_number(final.replace(",", ""), DELTA_GOLD_MILES),
         "80,000 bonus miles (Gold)"),
        ("ans_plat_miles", contains_number(final.replace(",", ""), DELTA_PLATINUM_MILES),
         "90,000 bonus miles (Platinum)"),
    ])
    _readonly(judge, init_db, after_db)


def grade_5(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_COMPARE_DELTA)
    ok_nav = _compare_nav(traj, P_COMPARE_BLUE) or (
        navigated_path(traj, P_COMPARE_DELTA)
        and all(s in step_text(traj) for s in P_COMPARE_BLUE))
    judge.check("nav_compare_blue", ok_nav, "compare page with both Blue Cash cards")
    _shot(judge, traj, P_COMPARE_DELTA)
    _answer_tokens(judge, final, [
        ("ans_bcp_market", answers.supermarket_rate(final, "6", "bcp"), "BCP 6% at U.S. supermarkets"),
        ("ans_bce_market", answers.supermarket_rate(final, "3", "bce"), "BCE 3% at U.S. supermarkets"),
        ("ans_bcp_fee", _fee_like(final, BCP_FEE_VALUE) and "first year" in norm(final),
         "BCP '$0 intro annual fee for the first year, then $95'"),
        ("ans_bce_fee", "no annual fee" in norm(final), "BCE 'No Annual Fee'"),
    ])
    _readonly(judge, init_db, after_db)


def grade_6(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_CATEGORY_TRAVEL)
    judge.check("nav_travel_category", navigated_path(traj, P_CATEGORY_TRAVEL), "opened the Travel category")
    _shot(judge, traj, P_CATEGORY_TRAVEL)
    _answer_tokens(judge, final, [
        ("ans_count_11", _count_word(final, TRAVEL_CATEGORY_COUNT), "11 Cards in the Travel category"),
        ("ans_nofee_blue", "delta" in norm(final) and "blue" in norm(final),
         "Delta SkyMiles Blue named as no-annual-fee"),
        ("ans_nofee_hilton", "hilton" in norm(final) and "surpass" not in norm(final) and "aspire" not in norm(final),
         "Hilton Honors (base) named as no-annual-fee"),
    ])
    _readonly(judge, init_db, after_db)


def grade_7(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_RESERVE)
    ok_nav = navigated_path(traj, P_RESERVE) or navigated_path(traj, P_LOUNGES)
    judge.check("nav_reserve_or_lounges", ok_nav, "opened the Delta Reserve page and/or lounges index")
    _shot(judge, traj, P_RESERVE)
    _answer_tokens(judge, final, [
        ("ans_card_reserve", "reserve" in norm(final), "Delta SkyMiles Reserve named"),
        ("ans_fee_650", _fee_like(final, RESERVE_FEE), "annual fee $650"),
        ("ans_first_benefit", ("centurion" in norm(final)) and ("lounge" in norm(final)),
         "first listed benefit: Centurion Lounge access when booking a Delta flight"),
    ])
    _readonly(judge, init_db, after_db)


def grade_8(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url="/search")
    judge.check("nav_search_delta", navigated_query(traj, "/search", q="delta"), "searched for 'delta'")
    _shot(judge, traj, "/search")
    low = norm(final)
    _answer_tokens(judge, final, [
        ("ans_blue_card", "blue" in low, "Delta SkyMiles Blue returned"),
        ("ans_blue_fee", "no annual fee" in low, "Blue: No Annual Fee"),
        ("ans_gold_card", ("gold" in low), "Delta SkyMiles Gold returned"),
        ("ans_gold_fee", _fee_like(final, 150) and "first year" in low, "Gold: $0 intro then $150"),
        ("ans_platinum_card", "platinum" in low, "Delta SkyMiles Platinum returned"),
        ("ans_plat_fee_350", _fee_like(final, 350), "Platinum: $350"),
        ("ans_reserve_card", "reserve" in low, "Delta SkyMiles Reserve returned"),
        ("ans_reserve_fee_650", _fee_like(final, 650), "Reserve: $650"),
    ])
    _readonly(judge, init_db, after_db)


def grade_9(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_BEVY)
    ok_nav = navigated_query(traj, "/search", q="bevy") and navigated_path(traj, P_BEVY)
    judge.check("nav_bevy_search_and_page", ok_nav, "searched 'bevy' and opened the card page")
    _shot(judge, traj, P_BEVY)
    _answer_tokens(judge, final, [
        ("ans_bevy_named", answers.card_named(final, "Marriott Bonvoy Bevy American Express Card")
         or "bevy" in norm(final), "Marriott Bonvoy Bevy named"),
        ("ans_fee_250", _fee_like(final, BEVY_FEE), "annual fee $250"),
        ("ans_points_125k", contains_number(final.replace(",", ""), BEVY_POINTS),
         "125,000 Marriott Bonvoy bonus points"),
        ("ans_credit_150", _fee_like(final, BEVY_CREDIT) and "statement credit" in norm(final),
         "$150 statement credit (two-part offer)"),
    ])
    _readonly(judge, init_db, after_db)


def grade_10(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_CD)
    judge.check("nav_cd_page", navigated_path(traj, P_CD), "opened the CD page")
    _shot(judge, traj, P_CD)
    _answer_tokens(judge, final, [
        ("ans_best_apy", _dec(final, CD_BEST_APY) and ("4.25" in final), "highest APY 4.25%"),
        ("ans_best_term", contains_number(final, CD_BEST_TERM) and ("10" in final), "10-month term is highest"),
        ("ans_350_terms", all(contains_number(final, t) for t in CD_350_TERMS)
         and (_dec(final, "3.50") or "3.5" in (final or "") or "3.50%" in (final or "")),
         "3.50% APY terms: 11, 12 and 14 months"),
    ])
    _readonly(judge, init_db, after_db)


def grade_11(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_HYSA)
    judge.check("nav_hysa_page", navigated_path(traj, P_HYSA), "opened the HYSA page")
    _shot(judge, traj, P_HYSA)
    _answer_tokens(judge, final, [
        ("ans_hysa_apy", _dec(final, HYSA_APY) and ("apy" in norm(final) or "%" in final), "3.00% APY"),
        ("ans_national_avg", _dec(final, HYSA_NATIONAL), "national average 0.38% APY"),
    ])
    _readonly(judge, init_db, after_db)


def grade_12(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_CHECKING)
    judge.check("nav_checking_page", navigated_path(traj, P_CHECKING), "opened the Rewards Checking page")
    _shot(judge, traj, P_CHECKING)
    _answer_tokens(judge, final, [
        ("ans_offer_300", _fee_like(final, CHECKING_OFFER), "limited-time offer $300"),
        ("ans_deadline", "02/01/2027" in final or "february 1, 2027" in norm(final)
         or "02/01/27" in final, "open by 02/01/2027"),
        ("ans_deposits_7500", contains_number(final.replace(",", ""), CHECKING_DEPOSITS),
         "$7,500 total Qualifying Direct Deposits"),
        ("ans_days_90", _count_word(final, CHECKING_DAYS), "within 90 days of account opening"),
    ])
    _readonly(judge, init_db, after_db)


def grade_13(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_LOANS)
    judge.check("nav_loans_page", navigated_path(traj, P_LOANS), "opened the Personal Loans page")
    _shot(judge, traj, P_LOANS)
    _answer_tokens(judge, final, [
        ("ans_apr_range", _dec(final, LOAN_APR[0]) and _dec(final, LOAN_APR[1]),
         "6.99%-19.99% APR"),
        ("ans_example_amount", contains_number(final.replace(",", ""), LOAN_EXAMPLE[0]), "$10,000 loan"),
        ("ans_example_term", contains_number(final, LOAN_EXAMPLE[1]), "36 months"),
        ("ans_example_apr", _dec(final, LOAN_EXAMPLE[2]), "12.98% APR"),
        ("ans_example_monthly", _fee_like(final, float(LOAN_EXAMPLE[3])), "$336.85 monthly"),
        ("ans_example_total", _fee_like(final, float(LOAN_EXAMPLE[4])), "$12,123 total"),
    ])
    _readonly(judge, init_db, after_db)


def grade_14(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_CARDS_INDEX)
    judge.check("nav_cards_index", navigated_path(traj, P_CARDS_INDEX), "browsed all Credit Cards")
    _shot(judge, traj, P_CARDS_INDEX)
    _answer_tokens(judge, final, [
        ("ans_highest_895", _fee_like(final, PLATINUM_FEE) and "platinum" in norm(final),
         "highest fee: Platinum $895"),
        ("ans_nofee_count", answers.no_annual_fee_cards(final) == 3,
         f"names all 3 no-annual-fee Cards (got {answers.no_annual_fee_cards(final)})"),
        ("ans_no_extra_nofee", ("surpass" not in norm(final)) and ("aspire" not in norm(final))
         and ("reserve" not in norm(final)) and ("bevy" not in norm(final)),
         "no wrong card claimed as no-annual-fee"),
    ])
    _readonly(judge, init_db, after_db)


def grade_15(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_ACCOUNT)
    _login_nav(judge, traj, [P_ACCOUNT])
    _answer_tokens(judge, final, [
        ("ans_platinum_balance", _fee_like(final, ALICE_PLATINUM_BALANCE), "Platinum balance $6,126.88"),
        ("ans_bce_balance", _fee_like(final, ALICE_BCE_BALANCE), "BCE balance $589.68"),
        ("ans_total_points", contains_number(final.replace(",", ""), ALICE_TOTAL_POINTS),
         "84,250 MR points across the account"),
    ])
    _readonly(judge, init_db, after_db)


def grade_16(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_STMT3)
    _login_nav(judge, traj, [P_STATEMENTS])
    judge.check("nav_stmt3", navigated_path(traj, P_STMT3) or "08/31/2026" in step_text(traj),
                "opened the Platinum statement ending 08/31/2026")
    _answer_tokens(judge, final, [
        ("ans_closing", _fee_like(final, ALICE_STMT3[0]), "closing balance $9,341.98"),
        ("ans_min_payment", _fee_like(final, ALICE_STMT3[1]), "minimum payment $467.10"),
        ("ans_due_date", ALICE_STMT3[2] in final or "09/24/26" in final, "due 09/24/2026"),
        ("ans_status", affirms(final, "Due") and "due" in norm(final), "payment status Due"),
    ])
    _readonly(judge, init_db, after_db)


def grade_17(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_REWARDS)
    _login_nav(judge, traj, [P_REWARDS])
    _answer_tokens(judge, final, [
        ("ans_points_deducted", contains_number(final.replace(",", ""), GIFT_CARD_POINTS),
         "10,000 points deducted"),
        ("ans_remaining", contains_number(final.replace(",", ""), ALICE_REMAINING),
         "74,250 points remaining"),
        ("ans_gift_card_anchor", "gift card" in norm(final), "$100 Gift Card redemption anchor"),
    ])
    # stateful: uc1 points 84250 -> 74250; one new reward_activity row -10000; all else preserved
    additions = {}
    if init_rows and after_rows and len(after_rows["reward_activity"]) == len(init_rows["reward_activity"]) + 1:
        additions = {"reward_activity": [max(r["id"] for r in after_rows["reward_activity"])]}
    ok_state = init_rows is not None and after_rows is not None and preserved(
        init_rows, after_rows, changes={"user_cards": {1: {"points_balance"}}}, additions=additions)
    judge.check("db_redeem_state", ok_state,
                "user_cards[1].points_balance changed only; exactly one new reward_activity row")
    if init_rows and after_rows:
        uc1 = one(after_rows, "user_cards", id=1)
        judge.check("db_points_balance", uc1["points_balance"] == ALICE_REMAINING,
                    f"points_balance={uc1['points_balance']}")
        new_ra = [r for r in after_rows["reward_activity"] if r["id"] > max(x["id"] for x in init_rows["reward_activity"])]
        judge.check("db_reward_row", len(new_ra) == 1 and new_ra[0]["points_change"] == -GIFT_CARD_POINTS
                    and new_ra[0]["user_card_id"] == 1, f"new reward_activity row {new_ra}")


def grade_18(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_CARD_UC3)
    _login_nav(judge, traj, [P_CARD_UC3])
    low = norm(final)
    missing = [m for m, _ in BOB_RESTAURANTS if norm(m) not in low]
    _answer_tokens(judge, final, [
        ("ans_all_merchants", not missing, f"all 7 Restaurants merchants named (missing: {missing})"),
        ("ans_total", _fee_like(final, BOB_RESTAURANTS_TOTAL), "total $861.95"),
        ("ans_category_anchor", "restaurant" in low, "Restaurants category anchor"),
    ])
    for m, amt in BOB_RESTAURANTS:
        judge.check(f"ans_merchant[{m}]", norm(m) in low, f"{m} ${amt:.2f}")
    _readonly(judge, init_db, after_db)


def grade_19(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_PAYMENTS)
    _login_nav(judge, traj, [P_PAYMENTS])
    confirmations = CONFIRMATION_RE.findall(final or "")
    _answer_tokens(judge, final, [
        ("ans_confirmation_present", bool(confirmations), f"confirmation {confirmations}"),
        ("ans_amount_anchor", contains_number(final.replace(",", ""), 250), "$250 payment anchor"),
    ])
    if init_rows and after_rows:
        new_pays = new_rows(init_rows, after_rows, "payments")
        judge.check("db_new_payment", len(new_pays) == 1 and new_pays[0]["amount"] == BOB_PAY_AMOUNT
                    and new_pays[0]["user_card_id"] == 3 and new_pays[0]["bank_account_id"] == 2,
                    f"one new payment $250 to Gold from BofA: {new_pays}")
        if new_pays:
            judge.check("ans_confirmation_matches_db", new_pays[0]["confirmation"] in (final or ""),
                        f"answer carries the DB confirmation {new_pays[0]['confirmation']}")
            uc3 = one(after_rows, "user_cards", id=3)
            judge.check("db_balance_updated", abs(uc3["current_balance"] - (833.44 - BOB_PAY_AMOUNT)) < 0.005,
                        f"uc3 balance={uc3['current_balance']} (833.44-250)")
    ok_state = False
    if init_rows and after_rows:
        additions = {}
        if len(after_rows["payments"]) == len(init_rows["payments"]) + 1:
            additions = {"payments": [max(r["id"] for r in after_rows["payments"])]}
        ok_state = preserved(init_rows, after_rows,
                             changes={"user_cards": {3: {"current_balance"}}}, additions=additions)
    judge.check("db_payment_state", ok_state, "only uc3.current_balance changed + one payments row added")


def grade_20(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_OFFERS)
    _login_nav(judge, traj, [P_OFFERS])
    _answer_tokens(judge, final, [
        ("ans_headline", ("spend $75 or more" in norm(final)) and ("earn $15 back" in norm(final)),
         "headline 'Spend $75 or more, earn $15 back'"),
        ("ans_expiration", TULA_EXPIRES in final or "10/01/26" in final or "october 1" in norm(final)
         or "10/1/2026" in final, "expires 10/01/2026"),
        ("ans_min_spend", contains_number(final.replace(",", ""), TULA_MIN_SPEND), "minimum spend $75"),
        ("ans_tula_anchor", "tula" in norm(final), "Tula Skincare anchor"),
    ])
    if init_rows and after_rows:
        new_enr = new_rows(init_rows, after_rows, "offer_enrollments")
        judge.check("db_new_enrollment", len(new_enr) == 1 and new_enr[0]["amex_offer_id"] == 1
                    and new_enr[0]["user_card_id"] == 3 and new_enr[0]["user_id"] == 2,
                    f"Tula added to Gold: {new_enr}")
    ok_state = False
    if init_rows and after_rows:
        additions = {}
        if len(after_rows["offer_enrollments"]) == len(init_rows["offer_enrollments"]) + 1:
            additions = {"offer_enrollments": [max(r["id"] for r in after_rows["offer_enrollments"])]}
        ok_state = preserved(init_rows, after_rows, additions=additions)
    judge.check("db_enrollment_state", ok_state, "only one offer_enrollments row added")


def grade_21(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_CARD_UC5)
    _login_nav(judge, traj, [P_CARD_UC5, P_CARD_UC6])
    _answer_tokens(judge, final, [
        ("ans_merchant", "whole foods" in norm(final), "Whole Foods Market #338"),
        ("ans_amount", _fee_like(final, CAROL_RECENT[1]), "$98.30"),
        ("ans_date", CAROL_RECENT[2] in final or "09/16/26" in final, "09/16/2026"),
        ("ans_card", "surpass" in norm(final), "posted to the Hilton Surpass Card"),
    ])
    _readonly(judge, init_db, after_db)


def grade_22(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_PAYMENTS)
    _login_nav(judge, traj, [P_PAYMENTS])
    confirmations = CONFIRMATION_RE.findall(final or "")
    _answer_tokens(judge, final, [
        ("ans_confirmation_present", bool(confirmations), f"confirmation {confirmations}"),
        ("ans_amount_anchor", contains_number(final.replace(",", ""), 400), "$400 payment anchor"),
    ])
    if init_rows and after_rows:
        new_pays = new_rows(init_rows, after_rows, "payments")
        judge.check("db_new_payment", len(new_pays) == 1 and new_pays[0]["amount"] == CAROL_PAY_AMOUNT
                    and new_pays[0]["user_card_id"] == 5 and new_pays[0]["bank_account_id"] == 4,
                    f"one new payment $400 to Surpass from Citi: {new_pays}")
        if new_pays:
            judge.check("ans_confirmation_matches_db", new_pays[0]["confirmation"] in (final or ""),
                        f"answer carries the DB confirmation {new_pays[0]['confirmation']}")
            uc5 = one(after_rows, "user_cards", id=5)
            judge.check("db_balance_updated", abs(uc5["current_balance"] - (1227.11 - CAROL_PAY_AMOUNT)) < 0.005,
                        f"uc5 balance={uc5['current_balance']} (1227.11-400)")
    ok_state = False
    if init_rows and after_rows:
        additions = {}
        if len(after_rows["payments"]) == len(init_rows["payments"]) + 1:
            additions = {"payments": [max(r["id"] for r in after_rows["payments"])]}
        ok_state = preserved(init_rows, after_rows,
                             changes={"user_cards": {5: {"current_balance"}}}, additions=additions)
    judge.check("db_payment_state", ok_state, "only uc5.current_balance changed + one payments row added")


def grade_23(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_BENEFITS)
    _login_nav(judge, traj, [P_BENEFITS])
    _answer_tokens(judge, final, [
        ("ans_surpass_rate", ("12x" in norm(final)) and ("hilton" in norm(final)),
         "Surpass: 12X points on eligible Hilton purchases (Hilton Honors)"),
        ("ans_brilliant_rate", ("6x" in norm(final)) and ("marriott" in norm(final)),
         "Brilliant: 6X points at Marriott Bonvoy hotels"),
    ])
    _readonly(judge, init_db, after_db)


def grade_24(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_ACCOUNT)
    _login_nav(judge, traj, [P_ACCOUNT])
    _answer_tokens(judge, final, [
        ("ans_higher_card", "delta" in norm(final) and "platinum" in norm(final),
         "Delta SkyMiles Platinum has the higher balance"),
        ("ans_delta_balance", _fee_like(final, DAVID_DELTA_BALANCE), "$1,527.10"),
        ("ans_bcp_balance", _fee_like(final, DAVID_BCP_BALANCE), "$111.10"),
        ("ans_available", _fee_like(final, DAVID_DELTA_AVAILABLE), "$9,472.90 available credit"),
    ])
    _readonly(judge, init_db, after_db)


def grade_25(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_OFFERS)
    _login_nav(judge, traj, [P_OFFERS])
    _answer_tokens(judge, final, [
        ("ans_offer_bouqs", "bouqs" in norm(final), "The Bouqs Company offer"),
        ("ans_card_bcp", "preferred" in norm(final), "added to the Blue Cash Preferred"),
        ("ans_added_date", BOUQS_ADDED in final or "08/12/26" in final or "august 12" in norm(final),
         "added 08/12/2026"),
    ])
    _readonly(judge, init_db, after_db)


def grade_26(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_PROFILE)
    _login_nav(judge, traj, [P_PROFILE])
    _answer_tokens(judge, final, [
        ("ans_phone", "(206) 555-0199" in (final or ""), "+1 (206) 555-0199 reported"),
    ])
    ok_state = bool(init_rows and after_rows) and preserved(init_rows, after_rows, changes={"users": {4: {"phone"}}})
    judge.check("db_profile_state", ok_state, "only david_k.phone changed")
    if init_rows and after_rows:
        david = one(after_rows, "users", id=4)
        judge.check("db_phone_value", david["phone"] == DAVID_PHONE, f"users[4].phone={david['phone']!r}")


def grade_27(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_CARD_UC2)
    _login_nav(judge, traj, [P_CARD_UC2])
    _answer_tokens(judge, final, [
        ("ans_count_3", _count_word(final, ALICE_BCE_STATEMENTS), "3 statements for the BCE Card"),
        ("ans_closing", _fee_like(final, ALICE_BCE_RECENT[0]), "most recent closing balance $961.20"),
        ("ans_status", "due" in norm(final), "payment status Due"),
    ])
    _readonly(judge, init_db, after_db)


def grade_28(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_APPLY_BCE)
    judge.check("nav_apply_page", navigated_path(traj, P_APPLY_BCE), "opened the BCE application form")
    _answer_tokens(judge, final, [
        ("ans_confirmation_id", "APP-00001" in (final or ""), "application confirmation ID APP-00001"),
    ])
    if init_rows and after_rows:
        new_apps = new_rows(init_rows, after_rows, "applications")
        judge.check("db_new_application", len(new_apps) == 1 and new_apps[0]["applicant_name"] == "Jordan Lee"
                    and new_apps[0]["email"] == "jordan.lee@example.com"
                    and new_apps[0]["employment_status"] == "Employed full-time"
                    and abs(new_apps[0]["annual_income"] - 85000.0) < 0.01
                    and new_apps[0]["residence_type"] == "Rent"
                    and new_apps[0]["card_id"] == 4,
                    f"application row: {new_apps}")
    ok_state = False
    if init_rows and after_rows:
        additions = {}
        if len(after_rows["applications"]) == len(init_rows["applications"]) + 1:
            additions = {"applications": [max(r["id"] for r in after_rows["applications"])]}
        ok_state = preserved(init_rows, after_rows, additions=additions)
    judge.check("db_application_state", ok_state, "only one applications row added")


def grade_29(judge, traj, final, init_db, after_db, init_rows, after_rows):
    judge.bind_run(traj, shot_url=P_CARD_UC7)
    _login_nav(judge, traj, [P_CARD_UC7])
    _answer_tokens(judge, final, [
        ("ans_count_9", _count_word(final, DAVID_BCP_GROCERY_STREAM_COUNT),
         "9 transactions categorized Groceries or Streaming"),
        ("ans_streaming_total", _fee_like(final, DAVID_STREAMING_TOTAL), "Streaming total $84.96"),
        ("ans_category_anchor", "streaming" in norm(final) and "grocer" in norm(final),
         "Groceries/Streaming category anchor"),
    ])
    _readonly(judge, init_db, after_db)


GRADERS = {n: globals()[f"grade_{n}"] for n in range(30)}


def grade(number: int) -> None:
    args = parse_args()
    traj = load_run(args.run_dir)
    judge = Judge(f"American Express--{number}", no_llm=args.no_llm)
    if number not in GRADERS:
        judge.check("task_known", False, f"no grader for task {number}")
        judge.emit()
    init_db = args.initial_db or resolve_db(None, args.container, "instance_seed")
    after_db = args.after_db or resolve_db(None, args.container, "instance")
    judge.check("dbs_available", bool(init_db) and bool(after_db),
                f"initial={'yes' if init_db else 'NO'} after={'yes' if after_db else 'NO'}")
    init_rows = rows(init_db) if init_db else None
    after_rows = rows(after_db) if after_db else None
    judge.check("db_rows_readable", init_rows is not None and after_rows is not None,
                "both DB snapshots readable")
    if number == 28:
        # application IDs are sequential from the seed; the seed ships zero
        # applications so a clean run always creates APP-00001.
        judge.check("seed_applications_empty", init_rows is not None and init_rows["applications"] == [],
                    "applications table starts empty in the seed")
    final = final_answer(traj)
    from reviewed import check
    check(judge, number, traj, init_rows, after_rows)
    GRADERS[number](judge, traj, final, init_db, after_db, init_rows, after_rows)
    judge.emit()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1].isdigit():
        grade(int(sys.argv[1]))

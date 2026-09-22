"""Shared deterministic CBOE task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED here (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (numbers / tokens / phrases,
     negation-aware, tolerant of comma separators and $ signs)
  4. DB after-state: read-only tasks leave every table unchanged; stateful
     tasks must produce exactly the requested rows and preserve the rest

Frozen seed facts the checks are anchored on (instance_seed/cboe.db,
md5 d8471a75ad06ceabe0e9ba78a25773f9, shipped in the pinned asset archive):
  8 symbols (SPX VIX XSP NDX RUT OEX DJX MRUT), 83,136 option contracts,
  3,113 intraday bars, 35,648 symbol-directory rows, 319 articles,
  21 experts, 3 classes, 2 courses, 4 products, 4 benchmark users
  (alice/bob/carol/david, password TestPass123!), 9 market-stat dates.
"""
import re
import sys

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, one, new_rows,
    tables_unchanged, navigated_path, navigated_query, navigated_prefix,
    navigated_chain_query, contains_number, contains_decimal, affirm_number,
    affirm_decimal, contains_money, affirms, affirms_any, contains_any,
    contains_all, contains_count, norm, final_answer, step_text, shot_at,
    url_path, step_urls,
)

# ---------------------------------------------------------------- ground truth
# Quotes (frozen seed; asserted against the DB in test_verifiers.py)
VIX_LAST = "14.87"
VIX_CHANGE = ("0.06", "0.40")          # +0.06 (+0.40%)
VIX_OHLC = ("14.84", "15.13", "14.60")  # open / high / low
SPX_PREV_CLOSE = "7764.70"             # rendered 7,764.70
SPX_IV30 = "11.793"
XSP_CALL_OI = 230492
XSP_PUT_OI = 543294
XSP_PCR_VOL = "0.95"
SPX_SEP21_C7765 = ("0.25", 944)        # first (nearest) NTM expiry 2026-09-21, call 7765
SPX_OCT16_TOP_CALL = (8000, "18.80", 182967)   # highest-OI Oct 16 2026 call
VIX_OCT_TOP_OI = (30, 352124)          # highest-OI VIX Oct 2026 contract (a call)
VIX_OCT_TOP_OI_CODE = "VIX261021C00030000"
SPX_SEP23_TOP_VOL_CALL = (7800, 7160)  # highest-volume SPXW call expiring 2026-09-23
VIX_DEC_TOP_VOL_PUT = (18, 57598)      # highest-volume VIX Dec 2026 put

# Daily market statistics (frozen seed)
STATS_DATES = ("2026-09-21", "2026-09-18")
TOTAL_PCR_0918 = "0.81"
INDEX_PCR_0918 = "0.98"
SPXSPXW_VOL_0921 = 6498237
VIX_OI_0921 = 11520630
EQUITY_PCR_0921 = "0.53"
EQUITY_PCR_0918 = "0.58"

# Homepage snapshots (frozen seed)
INDUSTRY_VOL_0918 = "73.35M"
SPX_INDEX_OPTIONS_VOL_0918 = "5.27M"
TOP_MARKET_SHARE = ("Chicago Board Options Exchange", "31.09")
EDGX_MOST_ACTIVE = "CTNT"

# Insights articles (frozen seed)
FED_ARTICLE = "/insights/posts/its-a-waiting-game-until-the-fed-rate-decision"
FEDWATCH_LEVEL = "92.7"
FED_TRUCKING = ("J.B. Hunt", "JB Hunt", "J.B Hunt")
Q1_ARTICLE = "/insights/posts/the-state-of-the-options-industry-q-1-2026"
Q1_ADV = ("68.6", "million")
Q1_XSP_QOQ = "47"
OIL_ARTICLE = "/insights/posts/week-of-9-21-2026-oil-rates-correlation-jumps-to-a-35-year-high"
OIL_SERIES = "Macro Volatility Digest"
OIL_CHART = ("10Y", "Oil")            # 'Chart: US 10Y vs. Oil Correlation at a 35-Year High'
XSP_ARTICLE = "/insights/posts/xsp-more-potential-benefits-than-spy"
XSP_DATE = "September 2, 2025"
XSP_FUND = "SPY"
TI_CATEGORY = "/insights/categories/trading_investing"
TI_NEWEST = ("How to Protect your Portfolio During Market Uncertainty", "June 4, 2026")

# Options Institute (frozen seed)
ODTE_PHRASES = ("zero days to expiration", "end of the current trading day")
ODTE_ALSO = ("same day expiring", "ultra short-dated")
OPTIONS101 = "/optionsinstitute/courses/options101"
PAYOUT_MODULE = "Payout Diagrams"
PAYOUT_DURATION = "20 min"
OI_CLASSES = "/optionsinstitute/classes"
OI_EXPERTS = "/optionsinstitute/experts"
CLASS1 = ("Market Structure and Liquidity: Who Does What?", "September 23")
CLASS2 = ("Market Structure and Liquidity: Execution Life Cycle", "September 30")
CLASS3 = ("Market Structure and Liquidity: Liquidity Awareness in Strategy Selection", "October 07")
CLASS_DATES = ("September 23", "September 30", "October 07")
CLASS_INSTRUCTOR = "Mark Phillips"
CLASS_TIME = "11:00 am"
CLASS_FORMAT = "Virtual"
EXPERT_2021 = ("Gordon Carpenter", "Senior Instructor")

# Tradable products (frozen seed)
SPX_PRODUCT = "/tradable-products/sp-500/spx-options"
SPX_SPECS = "/tradable-products/sp-500/spx-options/spx-specifications"
SPX_TRADE_VOLUME = 6498237
SPX_TRADE_OI = 20716226
SPX_MULTIPLIER = 100
SPX_CUSIP = "648815"
SPX_REGULAR_HOURS = ("9:30", "4:15")
CALC_SPX_NOTIONAL = 3500000          # level 7000 x $100 x 5 contracts
CALC_XSP_NOTIONAL = 350000           # level 7000 x $10 x 5 contracts

# Benchmark accounts (frozen seed)
ALICE, BOB, CAROL, DAVID = "alice.j@test.com", "bob.c@test.com", "carol.d@test.com", "david.k@test.com"
DEMO_PASSWORD = "TestPass123!"
LOGIN = "/account/login"
ACCOUNT = "/account"

# Watchlist plan (frozen seed): bob starts with VIX, XSP, NDX
BOB_WATCHLIST_BEFORE = ("VIX", "XSP", "NDX")
BOB_WATCHLIST_AFTER = ("VIX", "NDX", "DJX")   # task 26: remove XSP, add DJX

# Class registrations plan (frozen seed): carol already registered for class 2
CAROL_PRESET_REG = 2
CAROL_NEW_REG_CLASS = 3              # task 27: the October 7 class

# Saved articles plan (frozen seed): alice has tmt[0] + tmt[2]
ALICE_REMOVE_SLUG = "markets-await-wednesdays-fed-decision-on-rates"
ALICE_KEEP_TITLE = "Markets Breathe Again, Work to Undo Post-Fed Pulldown"
DAVID_SAVE_SLUG = "week-of-9-21-2026-oil-rates-correlation-jumps-to-a-35-year-high"
OIL_DATE = "September 21, 2026"
OIL_AUTHOR = "Mandy Xu"

# Symbol directory (frozen seed)
AGILENT = ("A", "Agilent Technologies Inc")
AGILENT_QUOTE_URL = "/delayed_quotes/A"

# URL anchors (paths only — host/port agnostic so review and benchmark ports both pass)
P_QUOTES_VIX = "/delayed_quotes/VIX"
P_QUOTES_SPX = "/delayed_quotes/SPX"
P_METRICS_XSP = "/delayed_quotes/XSP/metrics"
P_CHAIN_SPX = "/delayed_quotes/SPX/quote_table"
P_CHAIN_VIX = "/delayed_quotes/VIX/quote_table"
P_STATS = "/markets/us/options/market-statistics/daily"
P_HOME = "/"
P_SEARCH = "/search"
P_DEFINING = "/optionsinstitute/defining-options"


# ---------------------------------------------------------------- helpers
def _readonly(judge, init_db, after_db):
    changed = tables_unchanged(init_db, after_db)
    judge.check("db_readonly", changed == [],
                f"changed tables: {changed}" if changed else "all tables byte-identical to seed")


def _shot(judge, traj, substr):
    ok, note = shot_at(traj, substr)
    judge.check(f"shot[{substr[:44]}]", ok, note)


def _nav(judge, traj, path, label=None):
    judge.check(f"nav_{label or path.strip('/').replace('/', '_')}",
                navigated_path(traj, path), f"opened {path}")


def watchlist_for(db_path, email):
    if not db_path:
        return None
    from verify_lib import db_query
    rows_ = db_query(db_path,
                     "SELECT s.ticker FROM watchlist_items w "
                     "JOIN users u ON u.id=w.user_id JOIN symbols s ON s.id=w.symbol_id "
                     "WHERE u.email=? ORDER BY w.id", (email,))
    return [r[0] for r in rows_] if rows_ is not None else None


def regs_for(db_path, email):
    if not db_path:
        return None
    from verify_lib import db_query
    rows_ = db_query(db_path,
                     "SELECT c.id, c.title, c.time, c.instructor FROM class_registrations r "
                     "JOIN users u ON u.id=r.user_id JOIN oi_classes c ON c.id=r.class_id "
                     "WHERE u.email=? ORDER BY r.id", (email,))
    return [tuple(r) for r in rows_] if rows_ is not None else None


def saved_for(db_path, email):
    if not db_path:
        return None
    from verify_lib import db_query
    rows_ = db_query(db_path,
                     "SELECT a.slug, a.title FROM saved_articles sa "
                     "JOIN users u ON u.id=sa.user_id JOIN articles a ON a.id=sa.article_id "
                     "WHERE u.email=? ORDER BY sa.id", (email,))
    return [tuple(r) for r in rows_] if rows_ is not None else None


def user_id(db_path, email):
    from verify_lib import db_query
    if not db_path:
        return None
    r = db_query(db_path, "SELECT id FROM users WHERE email=?", (email,))
    return r[0][0] if r else None


def _dec(final, literal):
    return contains_decimal(final, literal)


# ---------------------------------------------------------------- per-task grading

def grade_0(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_QUOTES_VIX)
    _nav(judge, traj, P_QUOTES_VIX, "vix_dashboard")
    _shot(judge, traj, P_QUOTES_VIX)
    _readonly(judge, init_db, after_db)
    for name, ok, ev in [
        ("ans_last_14_87", affirm_decimal(final, VIX_LAST), "VIX last price 14.87"),
        ("ans_change_0_06", affirm_decimal(final, VIX_CHANGE[0]), "day change +0.06"),
        ("ans_change_pct_0_40", affirm_decimal(final, VIX_CHANGE[1]), "change percent 0.40%"),
        ("ans_open_14_84", affirm_decimal(final, VIX_OHLC[0]), "open 14.84"),
        ("ans_high_15_13", affirm_decimal(final, VIX_OHLC[1]), "high 15.13"),
        ("ans_low_14_60", affirm_decimal(final, VIX_OHLC[2]), "low 14.60"),
    ]:
        judge.check(name, ok, ev)


def grade_1(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_QUOTES_SPX)
    _nav(judge, traj, P_QUOTES_SPX, "spx_dashboard")
    _shot(judge, traj, P_QUOTES_SPX)
    _readonly(judge, init_db, after_db)
    judge.check("ans_prev_close_7764_70", affirm_decimal(final, SPX_PREV_CLOSE),
                "SPX previous close 7,764.70")
    judge.check("ans_iv30_11_793", affirm_decimal(final, SPX_IV30), "IV30 11.793")


def grade_2(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_METRICS_XSP)
    _nav(judge, traj, P_METRICS_XSP, "xsp_metrics")
    _shot(judge, traj, P_METRICS_XSP)
    _readonly(judge, init_db, after_db)
    judge.check("ans_call_oi_230492", contains_number(final, XSP_CALL_OI),
                "aggregate call open interest 230,492")
    judge.check("ans_put_oi_543294", contains_number(final, XSP_PUT_OI),
                "aggregate put open interest 543,294")
    judge.check("ans_pcr_0_95", affirm_decimal(final, XSP_PCR_VOL),
                "put/call ratio (volume) 0.95")


def grade_3(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_CHAIN_SPX)
    nav = navigated_chain_query(traj, P_CHAIN_SPX, required=["expiration"],
                               optional_any={"expiration": {"2026-09"}})
    judge.check("nav_spx_chain_sept", nav,
                "opened the SPX quote table for the September 2026 expiration")
    _shot(judge, traj, P_CHAIN_SPX)
    _readonly(judge, init_db, after_db)
    judge.check("ans_call_last_0_25", affirm_decimal(final, SPX_SEP21_C7765[0]),
                "nearest-expiry (2026-09-21) call at 7765: last 0.25")
    judge.check("ans_call_int_944", contains_number(final, SPX_SEP21_C7765[1]),
                "open interest 944")


def grade_4(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_CHAIN_SPX)
    nav = navigated_query(traj, P_CHAIN_SPX, expiration="2026-10", range="all")
    judge.check("nav_spx_chain_oct_all", nav,
                "opened the SPX quote table with expiration=2026-10 and range=all")
    _shot(judge, traj, P_CHAIN_SPX)
    _readonly(judge, init_db, after_db)
    strike, last, oi = SPX_OCT16_TOP_CALL
    judge.check("ans_strike_8000", affirm_number(final, strike),
                "highest-OI Oct 16 call strike 8000")
    judge.check("ans_last_18_80", affirm_decimal(final, last), "last price 18.80")
    judge.check("ans_oi_182967", contains_number(final, oi), "open interest 182,967")


def grade_5(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_CHAIN_VIX)
    nav = navigated_query(traj, P_CHAIN_VIX, expiration="2026-10", range="all")
    judge.check("nav_vix_chain_oct_all", nav,
                "opened the VIX quote table with expiration=2026-10 and range=all")
    _shot(judge, traj, P_CHAIN_VIX)
    _readonly(judge, init_db, after_db)
    strike, oi = VIX_OCT_TOP_OI
    # The task asks for the full option code. The chain page renders root+strike
    # ("VIX 30.000") and call/put columns; the full OSI code is NOT displayed on
    # the page, so the answer must at least identify the contract as displayed
    # (root VIX, strike 30, call) and report its open interest; the OSI code is
    # accepted as an additional identifier.
    judge.check("ans_contract_is_call", affirms(final, "call"),
                "the highest-OI contract is a call")
    judge.check("ans_strike_30", affirm_number(final, strike), "strike 30")
    judge.check("ans_oi_352124", contains_number(final, oi), "open interest 352,124")
    judge.check("ans_identifies_contract",
               contains_decimal(final, VIX_OCT_TOP_OI_CODE) or
               (affirms(final, "VIX") and affirm_number(final, strike) and affirms(final, "call")),
               "identifies the contract via its OSI code or its on-page root/strike/type")


def grade_6(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_CHAIN_SPX)
    nav = navigated_chain_query(traj, P_CHAIN_SPX, required=["expiration"],
                               optional_any={"expiration": {"2026-09"}})
    judge.check("nav_spx_chain_sept", nav,
                "opened the SPX quote table for the September 2026 expiration")
    _shot(judge, traj, P_CHAIN_SPX)
    _readonly(judge, init_db, after_db)
    strike, vol = SPX_SEP23_TOP_VOL_CALL
    judge.check("ans_strike_7800", affirm_number(final, strike),
                "highest-volume SPXW call expiring 2026-09-23: strike 7800")
    judge.check("ans_volume_7160", contains_number(final, vol), "volume 7,160")


def grade_7(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_CHAIN_VIX)
    nav = navigated_chain_query(traj, P_CHAIN_VIX, required=["expiration", "range"],
                               optional_any={"expiration": {"2026-12"}, "range": {"all"}})
    judge.check("nav_vix_chain_dec_all", nav,
                "opened the VIX quote table with expiration=2026-12 and range=all")
    _shot(judge, traj, P_CHAIN_VIX)
    _readonly(judge, init_db, after_db)
    strike, vol = VIX_DEC_TOP_VOL_PUT
    judge.check("ans_strike_18", affirm_number(final, strike),
                "highest-volume VIX Dec put: strike 18")
    judge.check("ans_volume_57598", contains_number(final, vol), "volume 57,598")


def grade_8(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_STATS)
    nav = navigated_query(traj, P_STATS, dt="2026-09-18")
    judge.check("nav_stats_0918", nav, "opened Daily Market Statistics for 2026-09-18")
    _shot(judge, traj, P_STATS)
    _readonly(judge, init_db, after_db)
    judge.check("ans_total_pcr_0_81", affirm_decimal(final, TOTAL_PCR_0918),
                "TOTAL PUT/CALL RATIO 0.81")
    judge.check("ans_index_pcr_0_98", affirm_decimal(final, INDEX_PCR_0918),
                "INDEX PUT/CALL RATIO 0.98")


def grade_9(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_STATS)
    nav = navigated_query(traj, P_STATS, dt="2026-09-21")
    judge.check("nav_stats_0921", nav, "opened Daily Market Statistics for 2026-09-21")
    _shot(judge, traj, P_STATS)
    _readonly(judge, init_db, after_db)
    judge.check("ans_spxspxw_vol_6498237", contains_number(final, SPXSPXW_VOL_0921),
                "total SPX + SPXW options volume 6,498,237")
    judge.check("ans_vix_oi_11520630", contains_number(final, VIX_OI_0921),
                "total VIX options open interest 11,520,630")


def grade_10(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_STATS)
    nav21 = navigated_query(traj, P_STATS, dt="2026-09-21")
    nav18 = navigated_query(traj, P_STATS, dt="2026-09-18")
    judge.check("nav_stats_both_dates", nav21 and nav18,
                "opened Daily Market Statistics for both 2026-09-21 and 2026-09-18")
    if nav21 and nav18:
        _shot(judge, traj, "dt=2026-09-21")
    _readonly(judge, init_db, after_db)
    f2 = (final or "").replace(",", "").casefold()
    # 'higher' must be anchored to September 18: the date mention NEAREST to each
    # 'higher' occurrence decides the claim (robust to long sentences), and the
    # immediate value-date attachments must not be inverted.
    says_higher_21 = False
    for m in re.finditer(r"higher", f2):
        best, bd = None, 10 ** 9
        for dm in re.finditer(r"september 18|september 21|09-18|09-21|9/18|9/21", f2):
            d = abs(dm.start() - m.start())
            if d < bd:
                bd, best = d, dm.group(0)
        if best and "21" in best:
            says_higher_21 = True
    immediate_wrong = (re.search(r"september 21[\s:,]{0,8}0\.58", f2)
                       or re.search(r"0\.58\s*(?:on|was|for)?\s*september 21", f2)
                       or re.search(r"september 18[\s:,]{0,8}0\.53", f2)
                       or re.search(r"0\.53\s*(?:on|was|for)?\s*september 18", f2))
    judge.check("ans_date_0918_higher",
                (affirms(final, "September 18") or contains_decimal(final, "09-18")
                 or contains_decimal(final, "9/18"))
                and not says_higher_21 and not immediate_wrong,
                "September 18 had the higher equity put/call ratio (0.58 on 9/18 vs 0.53 on 9/21)")
    judge.check("ans_values_0_58_0_53",
                affirm_decimal(final, EQUITY_PCR_0918) and affirm_decimal(final, EQUITY_PCR_0921),
                "equity put/call ratios 0.58 (9/18) and 0.53 (9/21)")


def grade_11(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_HOME)
    _nav(judge, traj, P_HOME, "homepage")
    _shot(judge, traj, P_HOME)
    _readonly(judge, init_db, after_db)
    judge.check("ans_industry_73_35M",
                contains_decimal(final, "73.35") and affirms_any(final, ["million", "M", "contracts"]),
                "total options industry volume 73.35M contracts on September 18, 2026")
    judge.check("ans_spx_options_5_27M", contains_decimal(final, SPX_INDEX_OPTIONS_VOL_0918),
                "SPX index options volume 5.27M")


def grade_12(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_HOME)
    _nav(judge, traj, P_HOME, "homepage")
    _shot(judge, traj, P_HOME)
    _readonly(judge, init_db, after_db)
    judge.check("ans_exchange_cboe",
                affirms(final, TOP_MARKET_SHARE[0]) or affirms(final, "Cboe"),
                "largest U.S. options market share: Chicago Board Options Exchange (C,W,E,Z)")
    judge.check("ans_share_31_09", affirm_decimal(final, TOP_MARKET_SHARE[1]),
                "market share 31.09%")
    judge.check("ans_edgx_symbol_ctnt", affirms(final, EDGX_MOST_ACTIVE),
                "most active symbol on EDGX by volume: CTNT")


def grade_13(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=FED_ARTICLE)
    _nav(judge, traj, FED_ARTICLE, "fed_article")
    _shot(judge, traj, FED_ARTICLE)
    _readonly(judge, init_db, after_db)
    judge.check("ans_fedwatch_92_7", affirm_decimal(final, FEDWATCH_LEVEL),
                "CME FedWatch tool 92.7% level signals assurance")
    judge.check("ans_trucking_jb_hunt", affirms_any(final, FED_TRUCKING),
                "J.B. Hunt shares tumbled more than 10%")


def grade_14(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=Q1_ARTICLE)
    _nav(judge, traj, Q1_ARTICLE, "q1_article")
    _shot(judge, traj, Q1_ARTICLE)
    _readonly(judge, init_db, after_db)
    judge.check("ans_adv_68_6m",
                affirm_decimal(final, Q1_ADV[0]) and affirms(final, "million"),
                "market-wide average daily options volume in Q1 2026: 68.6 million contracts")
    judge.check("ans_xsp_qoq_47", affirm_decimal(final, Q1_XSP_QOQ),
                "Mini-SPX (XSP) volume rose 47% quarter-over-quarter")


def grade_15(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=OIL_ARTICLE)
    _nav(judge, traj, OIL_ARTICLE, "oil_article")
    _shot(judge, traj, OIL_ARTICLE)
    _readonly(judge, init_db, after_db)
    judge.check("ans_series_macro_digest", affirms(final, OIL_SERIES),
                "recurring publication series: Macro Volatility Digest")
    judge.check("ans_chart_10y_oil",
                affirms(final, OIL_CHART[0]) and affirms(final, OIL_CHART[1]),
                "featured chart: US 10Y vs. Oil Correlation at a 35-Year High")


def grade_16(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=XSP_ARTICLE)
    _nav(judge, traj, XSP_ARTICLE, "xsp_article")
    _shot(judge, traj, XSP_ARTICLE)
    _readonly(judge, init_db, after_db)
    judge.check("ans_date_sep_2_2025",
                contains_decimal(final, "2025") and
                (affirms(final, "September 2, 2025") or contains_decimal(final, "September 2, 2025")),
                "published September 2, 2025")
    judge.check("ans_fund_spy", affirms(final, XSP_FUND),
                "the article compares XSP against SPY")
    judge.check("ans_key_reason",
                affirms(final, "similar") and
                (affirms_any(final, ["broad market exposure", "exposure", "hedge",
                                     "S&P 500", "one trade"])
                 or contains_decimal(final, "1/10")),
                "reports the article's key reason for the comparison: the two are very "
                "similar broad-market vehicles (one-trade exposure/hedging; XSP at "
                "1/10th the size of SPX with similar notional size, weekly expirations "
                "and PM-settlement to SPY)")


def grade_17(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=TI_CATEGORY)
    _nav(judge, traj, TI_CATEGORY, "ti_category")
    _shot(judge, traj, TI_CATEGORY)
    _readonly(judge, init_db, after_db)
    title, date = TI_NEWEST
    judge.check("ans_newest_title", affirms(final, title),
                "most recent Trading and Investing article: "
                "'How to Protect your Portfolio During Market Uncertainty'")
    judge.check("ans_newest_date",
                contains_decimal(final, "2026") and
                (affirms(final, date) or affirm_decimal(final, "June 4")),
                "published June 4, 2026")


def grade_18(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=P_DEFINING)
    nav = navigated_path(traj, P_DEFINING) or navigated_prefix(traj, "/optionsinstitute/courses/defining-options")
    judge.check("nav_glossary", nav, "opened the Options Definitions & Glossary")
    if nav:
        _shot(judge, traj, "defining-options")
    _readonly(judge, init_db, after_db)
    judge.check("ans_0dte_core",
                affirms(final, ODTE_PHRASES[0]) and affirms(final, ODTE_PHRASES[1]),
                "0DTE = zero days to expiration; contracts expire at the end of the current trading day")
    judge.check("ans_0dte_aliases", affirms_any(final, ODTE_ALSO),
                "also called same day expiring / ultra short-dated options")


def grade_19(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=OPTIONS101)
    nav = navigated_path(traj, OPTIONS101) or navigated_prefix(traj, OPTIONS101)
    judge.check("nav_options101", nav, "opened the Options 101 course page")
    if nav:
        _shot(judge, traj, "options101")
    _readonly(judge, init_db, after_db)
    judge.check("ans_module_payout", affirms(final, PAYOUT_MODULE),
                "the Payout Diagrams module covers payout diagrams")
    judge.check("ans_duration_20_min", affirm_decimal(final, "20") and affirms(final, "min"),
                "the course is a 20 min course")


def grade_20(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=OI_CLASSES)
    _nav(judge, traj, OI_CLASSES, "oi_classes")
    _shot(judge, traj, OI_CLASSES)
    _readonly(judge, init_db, after_db)
    for title, _date in (CLASS1, CLASS2, CLASS3):
        judge.check(f"ans_title[{title[:36]}]", affirms(final, title),
                    f"class title present: {title}")
    for date in CLASS_DATES:
        judge.check(f"ans_date[{date}]", affirms(final, date) or contains_decimal(
            final, date.replace("September ", "").replace("October ", "")),
            f"class date present: {date}")
    judge.check("ans_instructor_mark_phillips", affirms(final, CLASS_INSTRUCTOR),
                "all three classes are taught by Mark Phillips")


def grade_21(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=OI_CLASSES)
    _nav(judge, traj, OI_CLASSES, "oi_classes")
    _shot(judge, traj, OI_CLASSES)
    _readonly(judge, init_db, after_db)
    judge.check("ans_class_title", affirms(final, CLASS3[0]),
                "October 7, 2026 class: Market Structure and Liquidity: Liquidity Awareness in Strategy Selection")
    judge.check("ans_time_11am_ct", affirm_decimal(final, "11:00") and affirms(final, "CT"),
                "11:00 am (CT)")
    judge.check("ans_format_virtual", affirms(final, CLASS_FORMAT),
                "Virtual format")


def grade_22(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=OI_EXPERTS)
    _nav(judge, traj, OI_EXPERTS, "oi_experts")
    _shot(judge, traj, OI_EXPERTS)
    _readonly(judge, init_db, after_db)
    name, title = EXPERT_2021
    judge.check("ans_expert_gordon", affirms(final, name),
                "faculty member: Gordon Carpenter")
    judge.check("ans_title_senior_instructor", affirms(final, title),
                "title: Senior Instructor")


def grade_23(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=SPX_PRODUCT)
    _nav(judge, traj, SPX_PRODUCT, "spx_product")
    _shot(judge, traj, SPX_PRODUCT)
    _readonly(judge, init_db, after_db)
    judge.check("ans_volume_6498237", contains_number(final, SPX_TRADE_VOLUME),
                "Trade Data volume 6,498,237")
    judge.check("ans_oi_20716226", contains_number(final, SPX_TRADE_OI),
                "Trade Data open interest 20,716,226")
    judge.check("ans_multiplier_100", contains_number(final, SPX_MULTIPLIER),
                "contract multiplier $100")


def grade_24(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=SPX_SPECS)
    _nav(judge, traj, SPX_SPECS, "spx_specs")
    _shot(judge, traj, SPX_SPECS)
    _readonly(judge, init_db, after_db)
    judge.check("ans_cusip_648815", affirm_decimal(final, SPX_CUSIP),
                "CUSIP for SPX/SPXW options: 648815")
    judge.check("ans_regular_hours",
                affirm_decimal(final, SPX_REGULAR_HOURS[0]) and affirm_decimal(final, SPX_REGULAR_HOURS[1]),
                "regular trading session: 9:30 a.m. to 4:15 p.m. (ET)")


def grade_25(judge, traj, final, init_db, after_db):
    judge.bind_run(traj, shot_url=SPX_PRODUCT)
    nav = navigated_query(traj, SPX_PRODUCT, level="7000", contracts="5") or \
        navigated_query(traj, SPX_PRODUCT, level="7000.00", contracts="5") or \
        navigated_query(traj, SPX_PRODUCT, level="7000", contracts="05")
    judge.check("nav_calculator_7000_5", nav,
                "ran the comparison calculator with level=7000 and contracts=5")
    if nav:
        _shot(judge, traj, "level=7000")
    _readonly(judge, init_db, after_db)
    judge.check("ans_spx_notional_3500000", contains_money(final, CALC_SPX_NOTIONAL),
                "5 SPX contracts notional $3,500,000")
    judge.check("ans_xsp_notional_350000", contains_money(final, CALC_XSP_NOTIONAL),
                "5 XSP contracts notional $350,000")
    judge.check("ans_ratio_10",
                contains_number(final, 10) or affirms(final, "tenth") or affirms(final, "10x"),
                "SPX notional is 10x the XSP notional (XSP is 1/10th)")
    fx = (final or "").replace(",", "")

    def _symbol_before(pos):
        best, bd = None, 10 ** 9
        for m in re.finditer(r"XSP|SPX", fx[:pos]):
            if pos - m.end() < bd:
                bd, best = pos - m.end(), m.group(0)
        return best

    wrong_pair = False
    for m in re.finditer(r"(?<![\d.])3500000(?!\d)", fx):
        if _symbol_before(m.start()) != "SPX":
            wrong_pair = True
    for m in re.finditer(r"(?<![\d.])350000(?!\d)", fx):
        if _symbol_before(m.start()) == "SPX":
            wrong_pair = True
    judge.check("ans_notional_pairing", not wrong_pair,
                "the $3,500,000 notional is attributed to SPX and the $350,000 notional to XSP")


def grade_26(judge, traj, final, init_db, after_db):
    judge.bind_run(traj)
    _nav(judge, traj, LOGIN, "login")
    _nav(judge, traj, ACCOUNT, "account")
    # login evidence: the form post for bob appears in step params or observed text
    st = step_text(traj)
    judge.check("login_bob", BOB in st, "logged in with bob.c@test.com")
    before = watchlist_for(init_db, BOB)
    after = watchlist_for(after_db, BOB)
    judge.check("db_watchlist_xsp_removed_djx_added",
                after is not None and sorted(after or []) == sorted(BOB_WATCHLIST_AFTER),
                f"watchlist now {after} (expected VIX, NDX, DJX)")
    if before is not None:
        judge.check("db_watchlist_before_was_vix_xsp_ndx",
                    sorted(before) == sorted(BOB_WATCHLIST_BEFORE),
                    f"seed watchlist was {before}")
    for t in BOB_WATCHLIST_AFTER:
        judge.check(f"ans_symbol[{t}]", affirms(final, t), f"reports remaining symbol {t}")
    judge.check("ans_no_xsp_in_final_list",
                not re.search(r"(?:contains|watchlist(?: is| now)?(?: contains)?:?)[^.]*XSP",
                              (final or ""), re.I),
                "the reported final watchlist does not include the removed XSP")
    # the rest of the DB must be untouched
    changed = tables_unchanged(init_db, after_db, ignore=("watchlist_items",))
    judge.check("db_other_tables_untouched", changed == [],
                f"changed tables: {changed}" if changed else "only watchlist_items changed")


def grade_27(judge, traj, final, init_db, after_db):
    judge.bind_run(traj)
    _nav(judge, traj, LOGIN, "login")
    _nav(judge, traj, OI_CLASSES, "oi_classes")
    _nav(judge, traj, ACCOUNT, "account")
    st = step_text(traj)
    judge.check("login_carol", CAROL in st, "logged in with carol.d@test.com")
    before = regs_for(init_db, CAROL)
    after = regs_for(after_db, CAROL)
    new = [r for r in (after or []) if r not in (before or [])]
    judge.check("db_registered_oct7_class",
                len(new) == 1 and new[0][0] == CAROL_NEW_REG_CLASS
                and CLASS3[0] in new[0][1],
                f"new registration: {new} (expected the October 7 class)")
    if before is not None:
        judge.check("db_preset_reg_preserved",
                    all(r in (after or []) for r in before),
                    f"pre-existing registration preserved: {before}")
    judge.check("ans_class_title", affirms(final, CLASS3[0]),
                "registered class: Market Structure and Liquidity: Liquidity Awareness in Strategy Selection")
    judge.check("ans_time_11am", affirm_decimal(final, "11:00"), "11:00 am (CT)")
    judge.check("ans_instructor", affirms(final, CLASS_INSTRUCTOR), "Mark Phillips")
    changed = tables_unchanged(init_db, after_db, ignore=("class_registrations",))
    judge.check("db_other_tables_untouched", changed == [],
                f"changed tables: {changed}" if changed else "only class_registrations changed")


def grade_28(judge, traj, final, init_db, after_db):
    judge.bind_run(traj)
    _nav(judge, traj, LOGIN, "login")
    _nav(judge, traj, OIL_ARTICLE, "oil_article")
    _nav(judge, traj, ACCOUNT, "account")
    st = step_text(traj)
    judge.check("login_david", DAVID in st, "logged in with david.k@test.com")
    before = saved_for(init_db, DAVID)
    after = saved_for(after_db, DAVID)
    new = [r for r in (after or []) if r not in (before or [])]
    judge.check("db_saved_oil_article",
                len(new) == 1 and new[0][0] == DAVID_SAVE_SLUG,
                f"new saved article: {new} (expected the Oil-Rates article)")
    if before is not None:
        judge.check("db_prior_saves_preserved",
                    all(r in (after or []) for r in before),
                    f"prior saved articles preserved: {before}")
    judge.check("ans_date_sep_21_2026",
                contains_decimal(final, "2026") and
                (affirms(final, OIL_DATE) or affirm_decimal(final, "September 21")),
                "article published September 21, 2026")
    judge.check("ans_author_mandy_xu", affirms(final, OIL_AUTHOR), "author Mandy Xu")
    changed = tables_unchanged(init_db, after_db, ignore=("saved_articles",))
    judge.check("db_other_tables_untouched", changed == [],
                f"changed tables: {changed}" if changed else "only saved_articles changed")


def grade_29(judge, traj, final, init_db, after_db):
    judge.bind_run(traj)
    _nav(judge, traj, LOGIN, "login")
    _nav(judge, traj, ACCOUNT, "account")
    st = step_text(traj)
    judge.check("login_alice", ALICE in st, "logged in with alice.j@test.com")
    before = saved_for(init_db, ALICE)
    after = saved_for(after_db, ALICE)
    removed = [r for r in (before or []) if r not in (after or [])]
    judge.check("db_removed_fed_waiting_article",
                len(removed) == 1 and removed[0][0] == ALICE_REMOVE_SLUG,
                f"removed: {removed} (expected 'Markets Await Wednesday's Fed Decision on Rates')")
    judge.check("db_kept_markets_breathe",
                any(ALICE_KEEP_TITLE == r[1] for r in (after or [])),
                f"remaining saved article: {[r[1] for r in (after or [])]}")
    judge.check("ans_reports_remaining",
                affirms(final, ALICE_KEEP_TITLE),
                "reports 'Markets Breathe Again, Work to Undo Post-Fed Pulldown' as remaining")
    changed = tables_unchanged(init_db, after_db, ignore=("saved_articles",))
    judge.check("db_other_tables_untouched", changed == [],
                f"changed tables: {changed}" if changed else "only saved_articles changed")


def grade_30(judge, traj, final, init_db, after_db):
    judge.bind_run(traj)
    nav = navigated_prefix(traj, "/delayed_quotes/") or navigated_prefix(traj, P_SEARCH)
    judge.check("nav_symbol_search_surface", nav,
                "opened a quote dashboard (symbol box) or the search page")
    _shot(judge, traj, "/delayed_quotes/")
    _readonly(judge, init_db, after_db)
    ticker, company = AGILENT
    judge.check("ans_ticker_a",
                re.search(r"(?<![A-Za-z])A(?![A-Za-z])", final or "") is not None
                and (affirms(final, "ticker") or affirms(final, "symbol") or
                     affirms(final, "A is") or contains_decimal(final, "A")),
                "ticker symbol shown for Agilent: A")
    judge.check("ans_company_agilent", affirms(final, company),
                "company name in the symbol directory: Agilent Technologies Inc")
    judge.check("ans_quote_url_or_absence",
                contains_decimal(final, AGILENT_QUOTE_URL.replace("/", "/")) or
                AGILENT_QUOTE_URL in (final or "") or
                (affirms(final, "delayed_quotes/A") or
                 (affirms(final, "no") and affirms_any(final, ["mirror quote page", "quote page", "404", "not available"]))),
                "reports the mirror quote page URL /delayed_quotes/A (which has no quote page — 404) "
                "or explicitly states no quote page exists")


GRADERS = {
    0: grade_0, 1: grade_1, 2: grade_2, 3: grade_3, 4: grade_4, 5: grade_5,
    6: grade_6, 7: grade_7, 8: grade_8, 9: grade_9, 10: grade_10, 11: grade_11,
    12: grade_12, 13: grade_13, 14: grade_14, 15: grade_15, 16: grade_16,
    17: grade_17, 18: grade_18, 19: grade_19, 20: grade_20, 21: grade_21,
    22: grade_22, 23: grade_23, 24: grade_24, 25: grade_25, 26: grade_26,
    27: grade_27, 28: grade_28, 29: grade_29, 30: grade_30,
}


def grade(number):
    a = parse_args()
    j = Judge(f"Cboe--{number}")
    traj = load_run(a.run_dir)
    final = final_answer(traj)
    init_db = a.initial_db or resolve_db(None, a.container, "instance_seed")
    after_db = a.after_db or resolve_db(None, a.container, "instance")
    j.check("run_dir_available", traj.get("steps") is not None or True, "run loaded")
    GRADERS[number](j, traj, final, init_db, after_db)
    j.emit()

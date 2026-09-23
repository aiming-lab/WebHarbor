"""Deterministic verifier contract tests for the CBOE mirror.

Covers, per task (0-30):
  - ground-truth sanity against the frozen seed DB (quotes, option chains,
    market statistics, homepage cards, articles, Options Institute content,
    products, benchmark users and their pre-populated account data),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots) MUST PASS,
  - a no-op run MUST FAIL (contentless answer with homepage-only navigation,
    and the empty-answer variant),
  - a wrong-answer run (correct navigation, false values) MUST FAIL,
  - a shortcut run (ground-truth answer, no navigation to the answer page)
    MUST FAIL,
  - tampered run packages (missing/corrupt trajectory, tiny 1x1 screenshots,
    dropped screenshots, foreign-origin URLs, truncated run, DB drift on a
    read-only task) MUST FAIL,
  - stateful tasks (26-29): a state-mismatch run (success claimed, DB
    unchanged) MUST FAIL, and the honest fixture's DB mutation is verified.
The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed. The seed DB must exist at sites/cboe/instance_seed/cboe.db
(ships in the pinned asset archive; md5 d8471a75ad06ceabe0e9ba78a25773f9).
"""
import json
import random
import shutil
import sqlite3
import struct
import subprocess
import sys
import unittest
import zlib
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
VERIFY = SITE / "verify"
SEED = SITE / "instance_seed" / "cboe.db"
BASE = "http://localhost:46063"

sys.path.insert(0, str(VERIFY))
import grade  # noqa: E402

SEED_MD5 = "d8471a75ad06ceabe0e9ba78a25773f9"


# ---------------------------------------------------------------- PNG fixture
@__import__("functools").lru_cache(maxsize=128)
def make_png(seed, width=240, height=160):
    """A valid, distinct, deterministic noise PNG (>= 2000 bytes)."""
    rng = random.Random(seed)
    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes(rng.randrange(256) for _ in range(width * 3))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def tiny_png():
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00", 6)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- honest fixtures
def S(url, action="goto", params=None, text=""):
    return (url, action, params or {}, text)


HONEST = {
    0: dict(steps=[S(BASE + "/delayed_quotes/VIX")],
            answer="VIX last price: 14.87. Change for the day: +0.06 (+0.40%). "
                   "Overview panel OHLC: Open 14.84, High 15.13, Low 14.60."),
    1: dict(steps=[S(BASE + "/delayed_quotes/SPX")],
            answer="SPX previous close: 7,764.70. IV30 on the Overview panel: 11.793."),
    2: dict(steps=[S(BASE + "/delayed_quotes/XSP/metrics")],
            answer="Aggregate call open interest: 230,492. Aggregate put open interest: "
                   "543,294. Put/call ratio (volume): 0.95."),
    3: dict(steps=[S(BASE + "/delayed_quotes/SPX/quote_table?expiration=2026-09")],
            answer="First (nearest) expiration shown: Mon Sep 21 2026 (2026-09-21). "
                   "The call at the 7765 strike: last price 0.25, open interest 944."),
    4: dict(steps=[S(BASE + "/delayed_quotes/SPX/quote_table?expiration=2026-10&range=all&size=3")],
            answer="The call with the highest open interest on the October 16, 2026 "
                   "expiration is the 8000 strike: last price 18.80, open interest 182,967."),
    5: dict(steps=[S(BASE + "/delayed_quotes/VIX/quote_table?expiration=2026-10&range=all")],
            answer="The single contract with the highest open interest in October 2026 is "
                   "the VIX call at the 30 strike, displayed in the chain as root VIX, "
                   "strike 30.000 ('VIX 30.000'), expiring Wed Oct 21 2026. It is a call "
                   "and its open interest is 352,124. The page shows no full option code "
                   "for it."),
    6: dict(steps=[S(BASE + "/delayed_quotes/SPX/quote_table?expiration=2026-09&range=all")],
            answer="The SPXW call expiring September 23, 2026 with the highest volume that "
                   "day is the 7800 strike, with volume 7,160 contracts."),
    7: dict(steps=[S(BASE + "/delayed_quotes/VIX/quote_table?expiration=2026-12&range=all")],
            answer="The VIX put with the highest volume in the December 2026 expiration is "
                   "the 18 strike, with volume 57,598 contracts."),
    8: dict(steps=[S(BASE + "/markets/us/options/market-statistics/daily?dt=2026-09-18")],
            answer="For September 18, 2026: TOTAL PUT/CALL RATIO 0.81, "
                   "INDEX PUT/CALL RATIO 0.98."),
    9: dict(steps=[S(BASE + "/markets/us/options/market-statistics/daily?dt=2026-09-21")],
            answer="For September 21, 2026: total SPX + SPXW options volume (calls plus "
                   "puts) 6,498,237; total open interest of Cboe Volatility Index (VIX) "
                   "options 11,520,630."),
    10: dict(steps=[S(BASE + "/markets/us/options/market-statistics/daily?dt=2026-09-21"),
                    S(BASE + "/markets/us/options/market-statistics/daily?dt=2026-09-18")],
             answer="September 18, 2026 had the higher equity put/call ratio: 0.58 on "
                    "September 18 versus 0.53 on September 21."),
    11: dict(steps=[S(BASE + "/")],
             answer="According to the homepage Volume Snapshot (daily volume for September "
                    "18, 2026): total options industry volume 73.35M contracts; SPX index "
                    "options volume 5.27M."),
    12: dict(steps=[S(BASE + "/")],
             answer="The largest U.S. options market share belongs to the Chicago Board "
                    "Options Exchange (C,W,E,Z) with 31.09%. The most active symbol on EDGX "
                    "by volume is CTNT."),
    13: dict(steps=[S(BASE + "/insights/todays-market-take"),
                    S(BASE + "/insights/posts/its-a-waiting-game-until-the-fed-rate-decision")],
             answer="The author cites the CME FedWatch tool's 92.7% level as signaling "
                    "assurance, and J.B. Hunt is the trucking company whose shares tumbled "
                    "more than 10%."),
    14: dict(steps=[S(BASE + "/search?q=State+of+the+Options+Industry+Q1"),
                    S(BASE + "/insights/posts/the-state-of-the-options-industry-q-1-2026")],
             answer="Market-wide average daily options volume in Q1 2026 reached 68.6 "
                    "million contracts, and Mini-SPX (XSP) index options volume rose 47% "
                    "quarter-over-quarter."),
    15: dict(steps=[S(BASE + "/search?q=Oil-Rates+Correlation"),
                    S(BASE + "/insights/posts/week-of-9-21-2026-oil-rates-correlation-jumps-to-a-35-year-high")],
             answer="The article belongs to the recurring Cboe publication series 'Macro "
                    "Volatility Digest'. The featured chart shows: US 10Y vs. Oil "
                    "Correlation at a 35-Year High."),
    16: dict(steps=[S(BASE + "/search?q=Mini-SPX+potential+benefits"),
                    S(BASE + "/insights/posts/xsp-more-potential-benefits-than-spy")],
             answer="The article was published on September 2, 2025. It compares XSP with "
                    "SPY. The key reason the article gives for comparing the two is that "
                    "index options and ETF options tracking broad market indices like the "
                    "S&P 500 are very similar: with one trade, market participants can "
                    "gain broad market exposure, hedge portfolios, or execute a variety "
                    "of trading strategies — and at 1/10th the size of SPX, XSP offers "
                    "very similar notional size, weekly expirations and PM-settlement to "
                    "SPY but with even more potential benefits."),
    17: dict(steps=[S(BASE + "/insights/categories/trading_investing")],
             answer="The most recently published article in the Trading and Investing "
                    "category is 'How to Protect your Portfolio During Market "
                    "Uncertainty', published June 4, 2026."),
    18: dict(steps=[S(BASE + "/optionsinstitute/defining-options")],
             answer="According to the Options Definitions & Glossary, 0DTE (zero days to "
                    "expiration) refers to options contracts that expire at the end of the "
                    "current trading day. They are also called same day expiring or ultra "
                    "short-dated options."),
    19: dict(steps=[S(BASE + "/optionsinstitute/courses/options101")],
             answer="The Options 101 course module that covers payout diagrams is 'Payout "
                    "Diagrams', and the course is estimated to take 20 min (a 20 min "
                    "course) according to the course page."),
    20: dict(steps=[S(BASE + "/optionsinstitute/classes")],
             answer="The three upcoming Market Structure and Liquidity classes are: "
                    "'Market Structure and Liquidity: Who Does What?' on Wednesday, "
                    "September 23 2026; 'Market Structure and Liquidity: Execution Life "
                    "Cycle' on Wednesday, September 30 2026; 'Market Structure and "
                    "Liquidity: Liquidity Awareness in Strategy Selection' on Wednesday, "
                    "October 07 2026. All three are taught by instructor Mark Phillips."),
    21: dict(steps=[S(BASE + "/optionsinstitute/classes")],
             answer="The upcoming Options Institute class on Wednesday, October 7, 2026 is "
                    "'Market Structure and Liquidity: Liquidity Awareness in Strategy "
                    "Selection'. It takes place at 11:00 am (CT) and is in a Virtual format."),
    22: dict(steps=[S(BASE + "/optionsinstitute/experts")],
             answer="The faculty member whose bio says he joined Cboe in 2021 as a Sr. "
                    "Instructor after leading instruction for over 14 years is Gordon "
                    "Carpenter, Senior Instructor."),
    23: dict(steps=[S(BASE + "/tradable-products/sp-500/spx-options")],
             answer="On the S&P 500 Index Options product page, the Trade Data panel "
                    "reports volume 6,498,237 and open interest 20,716,226. The contract "
                    "multiplier for SPX index options shown in the comparison calculator "
                    "is $100."),
    24: dict(steps=[S(BASE + "/tradable-products/sp-500/spx-options/spx-specifications")],
             answer="The CUSIP number for SPX/SPXW options is 648815. The regular trading "
                    "session runs from 9:30 a.m. to 4:15 p.m. (ET)."),
    25: dict(steps=[S(BASE + "/tradable-products/sp-500/spx-options"),
                    S(BASE + "/tradable-products/sp-500/spx-options?level=7000&contracts=5",
                      "click", {"selector": "Calculate", "level": "7000", "contracts": "5"})],
             answer="With an S&P 500 level of 7000 and 5 contracts, the notional value of "
                    "5 SPX contracts is $3,500,000.00 and of 5 XSP contracts is "
                    "$350,000.00. The ratio between the two is 10:1 — the SPX notional is "
                    "ten times the XSP notional because the Mini-SPX Index is based on "
                    "1/10th the value of the S&P 500 Index."),
    26: dict(steps=[S(BASE + "/account/login"),
                    S(BASE + "/account", "login", {"email": "bob.c@test.com"}),
                    S(BASE + "/account", "click", {"selector": "Remove XSP"}),
                    S(BASE + "/account", "click", {"selector": "Add DJX"})],
             answer="After removing XSP and adding DJX, the watchlist contains: VIX, NDX, DJX."),
    27: dict(steps=[S(BASE + "/account/login"),
                    S(BASE + "/account", "login", {"email": "carol.d@test.com"}),
                    S(BASE + "/optionsinstitute/classes", "click",
                      {"selector": "Register for the October 7 class"}),
                    S(BASE + "/account")],
             answer="I registered for the October 7, 2026 class. As shown in my "
                    "registrations, the class is 'Market Structure and Liquidity: Liquidity "
                    "Awareness in Strategy Selection', at 11:00 am (CT), taught by "
                    "instructor Mark Phillips."),
    28: dict(steps=[S(BASE + "/account/login"),
                    S(BASE + "/account", "login", {"email": "david.k@test.com"}),
                    S(BASE + "/insights/posts/week-of-9-21-2026-oil-rates-correlation-jumps-to-a-35-year-high",
                      "click", {"selector": "Save article"}),
                    S(BASE + "/account")],
             answer="I saved the article to my saved list. As shown on its page, 'Week of "
                    "9/21/2026: Oil-Rates Correlation Jumps to a 35-Year High' was "
                    "published on September 21, 2026 by Mandy Xu."),
    29: dict(steps=[S(BASE + "/account/login"),
                    S(BASE + "/account", "login", {"email": "alice.j@test.com"}),
                    S(BASE + "/account", "click",
                      {"selector": "Remove 'Markets Await Wednesday's Fed Decision on Rates'"}),
                    S(BASE + "/account")],
             answer="I removed the saved article about markets awaiting the Federal "
                    "Reserve's decision on rates ('Markets Await Wednesday's Fed Decision "
                    "on Rates'). The article that remains in my saved list is 'Markets "
                    "Breathe Again, Work to Undo Post-Fed Pulldown'."),
    30: dict(steps=[S(BASE + "/delayed_quotes/VIX", "fill",
                      {"selector": "symbol box", "text": "Agilent"}),
                    S(BASE + "/delayed_quotes/A", "click",
                      {"selector": "first suggestion (A / Agilent Technologies Inc)"})],
             answer="The ticker symbol shown for Agilent is A, and the exact company name "
                    "listed in the symbol directory is Agilent Technologies Inc. Clicking "
                    "the suggestion goes to /delayed_quotes/A — Agilent has no mirror "
                    "quote page on this mirror (the delayed-quotes URL for it returns the "
                    "404 page)."),
}

WRONG_ANSWERS = {
    0: "VIX last price: 15.42. Change for the day: +0.11 (+0.75%). Overview panel OHLC: Open 15.20, High 15.60, Low 14.95.",
    1: "SPX previous close: 7,641.18. IV30 on the Overview panel: 12.406.",
    2: "Aggregate call open interest: 214,880. Aggregate put open interest: 501,342. Put/call ratio (volume): 0.88.",
    3: "First (nearest) expiration shown: Tue Sep 22 2026. The call at the 7765 strike: last price 15.74, open interest 464.",
    4: "The call with the highest open interest on the October 16, 2026 expiration is the 7000 strike: last price 788.61, open interest 171,803.",
    5: "The single contract with the highest open interest in October 2026 is the VIX put at the 20 strike. It is a put and its open interest is 327,270.",
    6: "The SPXW call expiring September 23, 2026 with the highest volume that day is the 7750 strike, with volume 6,422 contracts.",
    7: "The VIX put with the highest volume in the December 2026 expiration is the 16 strike, with volume 17,076 contracts.",
    8: "For September 18, 2026: TOTAL PUT/CALL RATIO 0.74, INDEX PUT/CALL RATIO 0.80.",
    9: "For September 21, 2026: total SPX + SPXW options volume 5,268,257; total open interest of Cboe Volatility Index (VIX) options 11,190,917.",
    10: "September 21, 2026 had the higher equity put/call ratio: 0.53 on September 21 versus 0.58 on September 18.",
    11: "According to the homepage Volume Snapshot: total options industry volume 76.17M contracts; SPX index options volume 6.50M.",
    12: "The largest U.S. options market share belongs to NASDAQ (Q,T,X,H,J) with 26.97%. The most active symbol on EDGX by volume is GRML.",
    13: "The author cites the CME FedWatch tool's 88.4% level as signaling assurance, and Knight-Swift is the trucking company whose shares tumbled more than 10%.",
    14: "Market-wide average daily options volume in Q1 2026 reached 61.2 million contracts, and Mini-SPX (XSP) index options volume rose 35% quarter-over-quarter.",
    15: "The article belongs to the recurring Cboe publication series 'Today's Market Take'. The featured chart shows: VIX term structure over the week.",
    16: "'XSP: More Potential Benefits Than SPY' was published on March 11, 2026. The article compares XSP against QQQ in its title and analysis.",
    17: "The most recently published article in the Trading and Investing category is 'The State of the Options Industry: Q1 2026', published May 4, 2026.",
    18: "According to the glossary, 0DTE options are options that expire at the end of the following trading week, also called weekly expirations.",
    19: "The module that covers payout diagrams is 'Spread Strategies', and the course is estimated to take 37 min.",
    20: "The three upcoming classes are all in the 'Cboe LiveVol' series, taught by instructor Henry Schwartz, on October 1, October 8 and October 15.",
    21: "The upcoming class on Wednesday, October 7, 2026 is 'Market Structure and Liquidity: Execution Life Cycle'. It takes place at 2:00 pm (CT) and is In-Person.",
    22: "The faculty member is Richard Excell, Principal at OI Adjunct Faculty.",
    23: "The Trade Data panel reports volume 315,743 and open interest 773,786. The contract multiplier for SPX index options shown in the comparison calculator is $10.",
    24: "The CUSIP number for SPX/SPXW options is 119981. The regular trading session runs from 8:15 p.m. to 9:25 a.m. (ET).",
    25: "With an S&P 500 level of 7000 and 5 contracts, the notional value of 5 SPX contracts is $350,000 and of 5 XSP contracts is $3,500,000. The ratio is 1:10.",
    26: "After removing XSP and adding DJX, the watchlist contains: VIX, XSP, NDX, DJX.",
    27: "I registered for the October 7, 2026 class. As shown in my registrations, the class is 'Market Structure and Liquidity: Execution Life Cycle', at 1:00 pm (CT), taught by instructor Henry Schwartz.",
    28: "I saved the article to my saved list. It was published on September 18, 2026 by JJ Kinahan.",
    29: "I removed the saved article. The articles that remain in my saved list are 'Markets Await Wednesday's Fed Decision on Rates' and 'Markets Absorb Double Blows in Early Trading'.",
    30: "The ticker symbol shown for Agilent is AGT, and the exact company name listed in the symbol directory is Agilent Technologies Incorporated. Its mirror quote page URL is /delayed_quotes/AGT.",
}

STATEFUL = {26, 27, 28, 29}


# ---------------------------------------------------------------- fixture builder
def build_run(root, steps, final_answer, n, *, terminated=True, shots_n=None,
              tiny_shots=False, drop_shots=False, no_traj=False, corrupt_traj=False,
              foreign=False, mutate=None):
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)          # a fresh package: no stale trajectory/shots
    root.mkdir(parents=True, exist_ok=True)
    frames = shots_n if shots_n is not None else len(steps) + 1
    if not drop_shots:
        (root / "screenshots").mkdir(exist_ok=True)
        for i in range(frames):
            data = tiny_png() if tiny_shots else make_png(1000 + i)
            (root / "screenshots" / f"step_{i:03d}.png").write_bytes(data)
    shutil.copy2(SEED, root / "initial.db")
    shutil.copy2(SEED, root / "after.db")
    if mutate:
        mutate(root / "after.db")
    if no_traj:
        return root
    traj_steps = []
    for i, (url, action, params, text) in enumerate(steps):
        if foreign:
            url = url.replace(BASE, "https://www.cboe.com")
        traj_steps.append({
            "step": i, "url": url, "title": "fixture", "page_text": text,
            "thought": "fixture thought", "action": action, "params": params,
            "observed_text": text, "observed_text_before": text,
            "screenshot_before": f"step_{i:03d}.png",
            "screenshot_after": f"step_{i + 1:03d}.png",
        })
    last = len(traj_steps)
    traj_steps.append({
        "step": last, "url": steps[-1][0] if steps else BASE + "/",
        "title": "fixture", "page_text": "final", "thought": "done",
        "action": "done", "params": {"text": final_answer, "success": True},
        "observed_text": "final", "observed_text_before": "final",
        "observed_text_after": "final",
        "screenshot_before": f"step_{last:03d}.png",
        "screenshot_after": f"step_{last:03d}.png",
    })
    traj = {
        "task": "fixture", "task_id": f"Cboe--{n}",
        "start_url": steps[0][0] if steps else BASE + "/",
        "model": "fixture", "max_steps": 40, "steps": traj_steps,
        "terminated": terminated, "termination_reason": "agent_done" if terminated else None,
        "final_answer": final_answer, "success_self_report": True,
        "judge_rubric": "", "verifier_path": f"sites/cboe/verify/verify_{n}.py",
    }
    text = json.dumps(traj, indent=1)
    if corrupt_traj:
        text = text[: len(text) // 2]
    (root / "trajectory.json").write_text(text)
    return root


def run_verifier(number, run_dir):
    proc = subprocess.run(
        [sys.executable, str(VERIFY / f"verify_{number}.py"), "--run_dir", str(run_dir)],
        capture_output=True, text=True, timeout=180,
        env={**__import__("os").environ, "WH_SITE": "cboe"},
    )
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": "verifier crashed", "stdout": proc.stdout[-400:],
                   "stderr": proc.stderr[-400:]}
    return proc.returncode, verdict


# ---------------------------------------------------------------- DB mutations
def mut_t26(db):
    """bob: remove XSP, add DJX (the honest task-26 outcome)."""
    con = sqlite3.connect(db)
    bob = con.execute("SELECT id FROM users WHERE email='bob.c@test.com'").fetchone()[0]
    xsp = con.execute("SELECT id FROM symbols WHERE ticker='XSP'").fetchone()[0]
    djx = con.execute("SELECT id FROM symbols WHERE ticker='DJX'").fetchone()[0]
    con.execute("DELETE FROM watchlist_items WHERE user_id=? AND symbol_id=?", (bob, xsp))
    con.execute("INSERT INTO watchlist_items (user_id, symbol_id) VALUES (?, ?)", (bob, djx))
    con.commit()
    con.close()


def mut_t27(db):
    """carol: new registration for class 3 (the October 7 class)."""
    con = sqlite3.connect(db)
    carol = con.execute("SELECT id FROM users WHERE email='carol.d@test.com'").fetchone()[0]
    con.execute("INSERT INTO class_registrations (user_id, class_id) VALUES (?, ?)",
                (carol, 3))
    con.commit()
    con.close()


def mut_t28(db):
    """david: saved article = the Oil-Rates article."""
    con = sqlite3.connect(db)
    david = con.execute("SELECT id FROM users WHERE email='david.k@test.com'").fetchone()[0]
    art = con.execute(
        "SELECT id FROM articles WHERE "
        "slug='week-of-9-21-2026-oil-rates-correlation-jumps-to-a-35-year-high'").fetchone()[0]
    con.execute("INSERT INTO saved_articles (user_id, article_id) VALUES (?, ?)",
                (david, art))
    con.commit()
    con.close()


def mut_t29(db):
    """alice: removed the 'markets-await' saved article."""
    con = sqlite3.connect(db)
    alice = con.execute("SELECT id FROM users WHERE email='alice.j@test.com'").fetchone()[0]
    art = con.execute(
        "SELECT id FROM articles WHERE slug='markets-await-wednesdays-fed-decision-on-rates'"
    ).fetchone()[0]
    con.execute("DELETE FROM saved_articles WHERE user_id=? AND article_id=?", (alice, art))
    con.commit()
    con.close()


def mut_db_drift(db):
    """Silent DB drift on a read-only task (a ratio changed under the agent)."""
    con = sqlite3.connect(db)
    con.execute("UPDATE market_stat_ratios SET value='9.99' "
                "WHERE stat_key='TOTAL PUT/CALL RATIO' AND stat_date='2026-09-18'")
    con.commit()
    con.close()


HONEST_MUTATIONS = {26: mut_t26, 27: mut_t27, 28: mut_t28, 29: mut_t29}


# ---------------------------------------------------------------- the suite
class VerifierContract(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        if not SEED.is_file():
            raise unittest.SkipTest(
                f"seed DB missing: {SEED} (fetch the pinned asset archive first)")
        cls.tmp = Path(__import__("tempfile").mkdtemp(prefix="wh-cboe-verify-test-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def fixture(self, kind, n, **kw):
        from reviewed_test_fixtures import fixture
        steps, answer, reviewed_mutation = fixture(n, BASE)
        mutate = kw.pop("mutate", None)  # None = unspecified; False = explicitly none
        if kind == "noop":
            steps = [S(BASE + "/")]
            answer = "I opened the homepage but could not find the information " \
                     "requested by this task."
        elif kind == "noopempty":
            steps = [S(BASE + "/")]
            answer = ""
        elif kind == "wrong":
            answer = WRONG_ANSWERS[n]
        elif kind == "shortcut":
            # ground-truth answer with no navigation to the answer page;
            # homepage tasks (11/12) must avoid the homepage itself
            steps = [S(BASE + "/about")] if n in (11, 12) else [S(BASE + "/")]
        elif kind == "honest":
            if mutate is None:
                mutate = reviewed_mutation
        if mutate is False:               # explicit "no mutation" (state mismatch)
            mutate = None
        return build_run(self.tmp / kind / f"{n:02d}", steps, answer, n, mutate=mutate, **kw)

    # ---- ground-truth sanity against the frozen seed --------------------
    def test_ground_truth_matches_seed_db(self):
        con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
        try:
            def one(sql, *params):
                return con.execute(sql, params).fetchone()

            # seed md5
            import hashlib
            digest = hashlib.md5(SEED.read_bytes()).hexdigest()
            self.assertEqual(digest, SEED_MD5)
            # health counts
            self.assertEqual(one("SELECT COUNT(*) FROM symbols")[0], 8)
            self.assertEqual(one("SELECT COUNT(*) FROM option_contracts")[0], 83136)
            self.assertEqual(one("SELECT COUNT(*) FROM intraday_bars")[0], 3113)
            self.assertEqual(one("SELECT COUNT(*) FROM symbol_directory")[0], 35648)
            self.assertEqual(one("SELECT COUNT(*) FROM articles")[0], 319)
            self.assertEqual(one("SELECT COUNT(*) FROM experts")[0], 21)
            self.assertEqual(one("SELECT COUNT(*) FROM oi_classes")[0], 3)
            self.assertEqual(one("SELECT COUNT(*) FROM users")[0], 4)
            # T0/T1 quotes
            vix = one("SELECT current_price, price_change, price_change_percent, open, high, low "
                      "FROM quotes q JOIN symbols s ON s.id=q.symbol_id WHERE s.ticker='VIX'")
            self.assertEqual(vix, (14.87, 0.06, 0.4035, 14.84, 15.13, 14.6))
            spx = one("SELECT prev_day_close, iv30 FROM quotes q "
                      "JOIN symbols s ON s.id=q.symbol_id WHERE s.ticker='SPX'")
            self.assertAlmostEqual(spx[0], 7764.7002, places=3)
            self.assertAlmostEqual(spx[1], 11.793, places=3)
            # T2 XSP aggregates
            self.assertEqual(one(
                "SELECT COALESCE(SUM(open_interest),0) FROM option_contracts o "
                "JOIN symbols s ON s.id=o.symbol_id WHERE s.ticker='XSP' AND o.cp='C'")[0], 230492)
            self.assertEqual(one(
                "SELECT COALESCE(SUM(open_interest),0) FROM option_contracts o "
                "JOIN symbols s ON s.id=o.symbol_id WHERE s.ticker='XSP' AND o.cp='P'")[0], 543294)
            # T3 first-expiry call 7765
            row = one("SELECT last_trade_price, open_interest FROM option_contracts o "
                      "JOIN symbols s ON s.id=o.symbol_id WHERE s.ticker='SPX' "
                      "AND o.expiry='2026-09-21' AND o.cp='C' AND o.strike=7765")
            self.assertEqual(row, (0.25, 944))
            # T4 highest-OI Oct 16 call
            row = one("SELECT strike, last_trade_price, open_interest FROM option_contracts o "
                      "JOIN symbols s ON s.id=o.symbol_id WHERE s.ticker='SPX' "
                      "AND o.expiry='2026-10-16' AND o.cp='C' "
                      "ORDER BY open_interest DESC LIMIT 1")
            self.assertEqual(row, (8000, 18.8, 182967))
            # T5 highest-OI VIX Oct contract
            row = one("SELECT code, cp, strike, open_interest FROM option_contracts o "
                      "JOIN symbols s ON s.id=o.symbol_id WHERE s.ticker='VIX' "
                      "AND o.expiry LIKE '2026-10%' ORDER BY open_interest DESC LIMIT 1")
            self.assertEqual(row, ("VIX261021C00030000", "C", 30, 352124))
            # T6 highest-volume SPXW call on 9/23
            row = one("SELECT strike, volume FROM option_contracts o "
                      "JOIN symbols s ON s.id=o.symbol_id WHERE s.ticker='SPX' "
                      "AND o.expiry='2026-09-23' AND o.cp='C' AND o.root='SPXW' "
                      "ORDER BY volume DESC LIMIT 1")
            self.assertEqual(row, (7800, 7160))
            # T7 highest-volume VIX Dec put
            row = one("SELECT strike, volume FROM option_contracts o "
                      "JOIN symbols s ON s.id=o.symbol_id WHERE s.ticker='VIX' "
                      "AND o.expiry LIKE '2026-12%' AND o.cp='P' "
                      "ORDER BY volume DESC LIMIT 1")
            self.assertEqual(row, (18, 57598))
            # T8/T10 ratios
            self.assertEqual(one("SELECT value FROM market_stat_ratios WHERE "
                                 "stat_date='2026-09-18' AND "
                                 "stat_key='TOTAL PUT/CALL RATIO'")[0], "0.81")
            self.assertEqual(one("SELECT value FROM market_stat_ratios WHERE "
                                 "stat_date='2026-09-18' AND "
                                 "stat_key='INDEX PUT/CALL RATIO'")[0], "0.98")
            self.assertEqual(one("SELECT value FROM market_stat_ratios WHERE "
                                 "stat_date='2026-09-18' AND "
                                 "stat_key='EQUITY PUT/CALL RATIO'")[0], "0.58")
            self.assertEqual(one("SELECT value FROM market_stat_ratios WHERE "
                                 "stat_date='2026-09-21' AND "
                                 "stat_key='EQUITY PUT/CALL RATIO'")[0], "0.53")
            # T9 products
            self.assertEqual(one("SELECT total FROM market_stat_products WHERE "
                                 "stat_date='2026-09-21' AND section='SPX + SPXW' "
                                 "AND kind='volume'")[0], "6,498,237")
            self.assertEqual(one("SELECT total FROM market_stat_products WHERE "
                                 "stat_date='2026-09-21' AND "
                                 "section='CBOE VOLATILITY INDEX (VIX)' "
                                 "AND kind='open_interest'")[0], "11,520,630")
            # T11/T12 homepage cards
            cards = {r[0]: json.loads(r[1]) for r in con.execute(
                "SELECT section, payload_json FROM home_page_cards")}
            self.assertEqual(cards["volume_snapshot"]["industry_volume"], "73.35M")
            self.assertEqual(cards["volume_snapshot"]["spx_index_options"], "5.27M")
            share = cards["market_snapshot"]["options_market_share"][0]
            self.assertIn("Chicago Board Options Exchange", share["name"])
            self.assertEqual(share["share"], 31.09)
            self.assertEqual(cards["market_snapshot"]["most_active"][0]["symbol"], "CTNT")
            # T13/T14/T15/T16/T17 articles
            art = one("SELECT body_text FROM articles WHERE "
                      "slug='its-a-waiting-game-until-the-fed-rate-decision'")
            self.assertIn("92.7% level signals assurance", art[0])
            self.assertIn("J.B. Hunt", art[0])
            art = one("SELECT body_text FROM articles WHERE "
                      "slug='the-state-of-the-options-industry-q-1-2026'")
            self.assertIn("68.6 million contracts", art[0])
            self.assertIn("rising 47% quarter-over-quarter", art[0])
            art = one("SELECT body_text, category_id FROM articles WHERE slug="
                      "'week-of-9-21-2026-oil-rates-correlation-jumps-to-a-35-year-high'")
            self.assertIn("Macro Volatility Digest", art[0])
            cat = one("SELECT name FROM article_categories WHERE id=?", art[1])
            self.assertEqual(cat[0], "Macro Volatility Digest")
            art = one("SELECT date FROM articles WHERE "
                      "slug='xsp-more-potential-benefits-than-spy'")
            self.assertEqual(art[0], "September 2, 2025")
            art = one("SELECT title, date FROM articles a JOIN article_categories c "
                      "ON c.id=a.category_id WHERE c.slug='trading_investing' "
                      "ORDER BY a.date_sort DESC LIMIT 1")
            self.assertEqual(art, ("How to Protect your Portfolio During Market "
                                  "Uncertainty", "June 4, 2026"))
            # T18/T19 courses
            course = one("SELECT modules_json FROM courses WHERE slug='defining-options'")
            modules = json.loads(course[0])
            qa = [m for m in modules if "0DTE" in m["q"]]
            self.assertTrue(qa and "end of the current trading day" in qa[0]["a"])
            course = one("SELECT modules_json FROM courses WHERE slug='options101'")
            modules = json.loads(course[0])
            self.assertTrue(any(m["title"] == "Payout Diagrams" and
                                "20 min" in m.get("duration", "") for m in modules))
            # T20/T21 classes
            classes = con.execute("SELECT title, date, time, format, instructor "
                                  "FROM oi_classes ORDER BY date_sort").fetchall()
            self.assertEqual(classes[0], ("Market Structure and Liquidity: Who Does What?",
                                         "Wednesday, September 23 2026", "11:00 am (CT)",
                                         "Virtual", "Mark Phillips"))
            self.assertEqual(classes[2][0],
                             "Market Structure and Liquidity: Liquidity Awareness in "
                             "Strategy Selection")
            # T22 expert
            bio = one("SELECT name, title, bio FROM experts WHERE name='Gordon Carpenter'")
            self.assertEqual(bio[1], "Senior Instructor")
            self.assertIn("joined Cboe in 2021", bio[2])
            self.assertIn("over 14 years", bio[2])
            # T23/T24 products
            prod = one("SELECT trade_volume, trade_open_interest, specs_json FROM products "
                       "WHERE slug='spx-options'")
            self.assertEqual(prod[0], "6,498,237")
            self.assertEqual(prod[1], "20,716,226")
            specs = json.loads(prod[2])
            snapshot = [s for s in specs if s["label"] == "Product Snapshot"][0]["value"]
            self.assertIn("648815", snapshot)
            self.assertIn("9:30 a.m. to 4:15 p.m. (ET)", snapshot)
            # T26-T29 seeded account data
            bob = one("SELECT id FROM users WHERE email='bob.c@test.com'")[0]
            wl = [r[0] for r in con.execute(
                "SELECT s.ticker FROM watchlist_items w JOIN symbols s ON s.id=w.symbol_id "
                "WHERE w.user_id=? ORDER BY w.id", (bob,))]
            self.assertEqual(wl, ["VIX", "XSP", "NDX"])
            carol = one("SELECT id FROM users WHERE email='carol.d@test.com'")[0]
            regs = [r[0] for r in con.execute(
                "SELECT c.id FROM class_registrations r JOIN oi_classes c ON c.id=r.class_id "
                "WHERE r.user_id=?", (carol,))]
            self.assertEqual(regs, [2])
            alice = one("SELECT id FROM users WHERE email='alice.j@test.com'")[0]
            saved = [r[0] for r in con.execute(
                "SELECT a.slug FROM saved_articles sa JOIN articles a ON a.id=sa.article_id "
                "WHERE sa.user_id=?", (alice,))]
            self.assertEqual(saved, ["markets-breathe-again-work-to-undo-post-fed-pulldown",
                                     "markets-await-wednesdays-fed-decision-on-rates"])
            # T30 symbol directory
            row = one("SELECT name, company_name FROM symbol_directory "
                      "WHERE company_name LIKE '%Agilent%'")
            self.assertEqual(row, ("A", "Agilent Technologies Inc"))
        finally:
            con.close()

    # ---- per-task matrix ------------------------------------------------
    def test_honest_run_passes(self):
        for n in range(31):
            with self.subTest(task=n):
                run = self.fixture("honest", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), True,
                                 f"honest run must pass: {verdict.get('reason')} "
                                 f"{verdict.get('evidence')}")
                self.assertEqual(rc, 0)

    def test_noop_run_fails(self):
        for n in range(31):
            with self.subTest(task=n):
                for kind in ("noop", "noopempty"):
                    run = self.fixture(kind, n)
                    rc, verdict = run_verifier(n, run)
                    self.assertEqual(verdict.get("pass"), False,
                                    f"{kind} run must fail for task {n}")

    def test_wrong_answer_fails(self):
        for n in range(31):
            with self.subTest(task=n):
                run = self.fixture("wrong", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"wrong answer must fail for task {n}: "
                                 f"{verdict.get('reason')}")

    def test_shortcut_run_fails(self):
        for n in range(31):
            with self.subTest(task=n):
                run = self.fixture("shortcut", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"shortcut run must fail for task {n}: "
                                 f"{verdict.get('reason')}")

    def test_tampered_packages_fail(self):
        variants = {
            "tamper-no-traj": dict(no_traj=True),
            "tamper-corrupt-traj": dict(corrupt_traj=True),
            "tamper-tiny-shots": dict(tiny_shots=True),
            "tamper-no-shots": dict(drop_shots=True),
            "tamper-foreign": dict(foreign=True),
            "tamper-truncated": dict(terminated=False),
            "tamper-db-drift": dict(mutate=mut_db_drift),
        }
        for name, kw in variants.items():
            for n in range(31):
                with self.subTest(task=n, variant=name):
                    run = self.fixture("honest", n, **kw)
                    rc, verdict = run_verifier(n, run)
                    self.assertEqual(verdict.get("pass"), False,
                                    f"{name} must fail for task {n}")

    def test_state_mismatch_fails(self):
        for n in sorted(STATEFUL):
            with self.subTest(task=n):
                # success claimed with a correct-sounding report, DB untouched
                run = self.fixture("honest", n, mutate=False)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"state mismatch must fail for task {n}: "
                                 f"{verdict.get('reason')}")
                self.assertTrue(any(tag in verdict.get("reason", "") for tag in ("db_", "requested_insert", "exact_saved_state")))

    def test_honest_mutation_is_exactly_the_task_outcome(self):
        """The honest fixture's after-DB matches the task's requested state change."""
        import grade as g
        for n in sorted(STATEFUL):
            with self.subTest(task=n):
                run = self.fixture("honest", n)
                before = g.watchlist_for(str(run / "initial.db"), g.BOB)
                after = g.watchlist_for(str(run / "after.db"), g.BOB)
                if n == 26:
                    self.assertEqual(sorted(after), sorted(["VIX", "NDX", "DJX"]))
                    self.assertEqual(sorted(before), sorted(["VIX", "XSP", "NDX"]))
                    self.assertIsNotNone(before)
                regs_before = g.regs_for(str(run / "initial.db"), g.CAROL)
                regs_after = g.regs_for(str(run / "after.db"), g.CAROL)
                if n == 27:
                    new = [r for r in (regs_after or []) if r not in (regs_before or [])]
                    self.assertEqual(len(new), 1)
                    self.assertEqual(new[0][0], 3)
                saved_before = g.saved_for(str(run / "initial.db"), g.DAVID)
                saved_after = g.saved_for(str(run / "after.db"), g.DAVID)
                if n == 28:
                    new = [r for r in (saved_after or []) if r not in (saved_before or [])]
                    self.assertEqual(len(new), 1)
                    self.assertEqual(new[0][0],
                                     "week-of-9-21-2026-oil-rates-correlation-jumps-to-a-35-year-high")
                a_before = g.saved_for(str(run / "initial.db"), g.ALICE)
                a_after = g.saved_for(str(run / "after.db"), g.ALICE)
                if n == 29:
                    removed = [r for r in (a_before or []) if r not in (a_after or [])]
                    self.assertEqual(removed,
                                     [("markets-await-wednesdays-fed-decision-on-rates",
                                       "Markets Await Wednesday’s Fed Decision on Rates")])
                    self.assertEqual(
                        [r[1] for r in (a_after or [])],
                        ["Markets Breathe Again, Work to Undo Post-Fed Pulldown"])


if __name__ == "__main__":
    unittest.main()

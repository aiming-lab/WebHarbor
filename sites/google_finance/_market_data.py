"""Deterministic synthetic market data for the Google Finance mirror.

Every number the mirror shows — prices, OHLC series, key stats, financial
statements, earnings rows, analyst targets — is generated here from a fixed
seed. Nothing depends on the wall clock, so the seed DB is reproducible and
task answers are stable across runs.

Why synthetic rather than scraped: real quotes are stale the moment they are
captured, and a frontier model can approximately recall real fundamentals,
which turns a benchmark task into a memory lookup. Frozen synthetic values
force the agent to actually read the page.

Real-world magnitudes (an anchor price per symbol) come from the recon pass so
each instrument still lands in a plausible range.
"""
import hashlib
import math
import random
from datetime import date, datetime, time, timedelta

# --------------------------------------------------------------------------
# Frozen clock
# --------------------------------------------------------------------------

MARKET_DATE = date(2026, 7, 24)            # a Friday
MARKET_CLOSE_LABEL = "Jul 24, 4:00:01 PM UTC-4"
AFTER_HOURS_LABEL = "7:59 PM"
MARKET_YEAR = MARKET_DATE.year
SESSION_OPEN = time(9, 30)
SESSION_CLOSE = time(16, 0)

# US market holidays that fall inside the 10-year history window. Only the
# fixed-rule ones are listed; the goal is a plausible calendar, not an exact
# exchange schedule.
_FIXED_HOLIDAYS = {(1, 1), (7, 4), (12, 25), (6, 19), (11, 11)}


def is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    return (d.month, d.day) not in _FIXED_HOLIDAYS


def trading_days_back(end: date, n: int) -> list[date]:
    """The n trading days ending on `end` (inclusive), oldest first."""
    out, d = [], end
    while len(out) < n:
        if is_trading_day(d):
            out.append(d)
        d -= timedelta(days=1)
    return list(reversed(out))


HISTORY_DAYS = 2520                        # ~10 years of sessions
CALENDAR = trading_days_back(MARKET_DATE, HISTORY_DAYS)
CAL_INDEX = {d: i for i, d in enumerate(CALENDAR)}

# Range key -> how many trailing sessions it spans (None = special-cased).
RANGE_SESSIONS = {
    "1D": None, "5D": None,
    "1M": 22, "6M": 126, "YTD": None, "1Y": 252, "5Y": 1260, "MAX": HISTORY_DAYS,
}
RANGE_KEYS = ["1D", "5D", "1M", "6M", "YTD", "1Y", "5Y", "MAX"]


def ytd_sessions() -> int:
    jan1 = date(MARKET_YEAR, 1, 1)
    return sum(1 for d in CALENDAR if d >= jan1)


# --------------------------------------------------------------------------
# Per-instrument RNG
# --------------------------------------------------------------------------

def rng_for(symbol: str, salt: str = "") -> random.Random:
    """A Random seeded only by the symbol, so generation order never matters."""
    h = hashlib.sha256(f"webharbor-gfinance-v1|{symbol}|{salt}".encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


# Daily volatility and annual drift by asset class.
CLASS_PARAMS = {
    "stock":    (0.0155, 0.070),
    "etf":      (0.0085, 0.060),
    "index":    (0.0080, 0.055),
    "sector":   (0.0090, 0.055),
    "crypto":   (0.0330, 0.150),
    "currency": (0.0040, 0.005),
    "future":   (0.0160, 0.030),
}

# Sector tilts: (extra annual drift, volatility multiplier).
SECTOR_TILT = {
    "Technology": (0.035, 1.20),
    "Communication Services": (0.020, 1.10),
    "Consumer Discretionary": (0.012, 1.15),
    "Consumer Staples": (-0.008, 0.70),
    "Financials": (0.008, 0.95),
    "Health Care": (0.000, 0.85),
    "Industrials": (0.006, 0.90),
    "Energy": (-0.008, 1.15),
    "Utilities": (-0.012, 0.65),
    "Real Estate": (-0.012, 0.90),
    "Materials": (0.000, 0.95),
    "ETF": (0.008, 0.85),
}


def _walk(rng: random.Random, n: int, sigma: float, mu_annual: float) -> list[float]:
    """A geometric random walk of n multiplicative steps, starting at 1.0.

    A slow sine cycle is layered on top so the long-range charts show market
    regimes rather than pure noise.
    """
    mu_daily = mu_annual / 252.0
    path, level = [1.0], 1.0
    cycle_len = rng.uniform(180, 420)
    # The cycle shifts the *daily drift*, so its amplitude has to stay on the
    # order of mu_daily. Scaling it to sigma instead compounds into 3x swings
    # over half a cycle and produces absurd 52-week ranges.
    cycle_amp = abs(mu_daily) * rng.uniform(1.2, 3.0) + sigma * 0.02
    phase = rng.uniform(0, 2 * math.pi)
    for i in range(1, n):
        seasonal = cycle_amp * math.sin(2 * math.pi * i / cycle_len + phase)
        step = rng.gauss(mu_daily + seasonal, sigma)
        step = max(-0.14, min(0.14, step))          # clip fat tails
        level *= (1.0 + step)
        path.append(level)
    return path


def digits_for(kind: str, price: float) -> int:
    """Quote precision. FX is always shown to four places on Google Finance;
    rounding a 1.08 pair to two places collapses a whole day's move to 0.00%."""
    if kind == "currency":
        return 4
    return _price_digits(price)


def daily_closes(symbol: str, anchor: float, kind: str, sector: str | None = None,
                 n: int = HISTORY_DAYS) -> list[float]:
    """A `n`-session close series ending exactly at `anchor`."""
    rng = rng_for(symbol, "daily")
    sigma, mu = CLASS_PARAMS.get(kind, CLASS_PARAMS["stock"])
    if sector:
        d_mu, m_sigma = SECTOR_TILT.get(sector, (0.0, 1.0))
        mu += d_mu
        sigma *= m_sigma
    path = _walk(rng, n, sigma, mu)
    scale = anchor / path[-1]
    digits = digits_for(kind, anchor)
    return [round(p * scale, digits) for p in path]


def _price_digits(price: float) -> int:
    if price >= 1000:
        return 2
    if price >= 1:
        return 2
    if price >= 0.01:
        return 4
    return 6


def daily_volumes(symbol: str, base: float, n: int = HISTORY_DAYS) -> list[int]:
    rng = rng_for(symbol, "vol")
    out = []
    for _ in range(n):
        out.append(int(base * math.exp(rng.gauss(0, 0.34))))
    return out


def intraday_path(symbol: str, prev_close: float, close: float,
                  points: int, sigma: float, salt: str = "1d",
                  kind: str = "stock") -> list[float]:
    """An intraday path from a gapped open to exactly `close`."""
    rng = rng_for(symbol, salt)
    gap = rng.gauss(0, sigma * 0.35)
    start = prev_close * (1 + gap)
    path = [1.0]
    for _ in range(points - 1):
        path.append(path[-1] * (1 + rng.gauss(0, sigma / math.sqrt(points) * 1.6)))
    # pin both ends: rotate the path so it starts at `start` and ends at `close`
    lo, hi = path[0], path[-1]
    digits = digits_for(kind, close)
    out = []
    for i, p in enumerate(path):
        w = i / max(1, points - 1)
        base = start + (close - start) * w
        wobble = (p / (lo + (hi - lo) * w)) - 1.0
        out.append(round(base * (1 + wobble), digits))
    out[0] = round(start, digits)
    out[-1] = round(close, digits)
    return out


AFTER_HOURS_POINTS = 49          # 16:00 -> 20:00 inclusive, 5-minute steps


def after_hours_path(symbol: str, close: float, after_close: float,
                     points: int = AFTER_HOURS_POINTS,
                     kind: str = "stock") -> list[float]:
    """The post-close leg Google draws in grey after the session divider."""
    rng = rng_for(symbol, "afterhours")
    digits = digits_for(kind, close)
    out, level = [], close
    for i in range(points):
        w = (i + 1) / points
        target = close + (after_close - close) * w
        level = target * (1 + rng.gauss(0, 0.0006))
        out.append(round(level, digits))
    out[-1] = round(after_close, digits)
    return out


def intraday_volumes(symbol: str, day_volume: int, points: int) -> list[int]:
    """Per-bar volume with the U-shaped open/close bulge real sessions show."""
    rng = rng_for(symbol, "intravol")
    weights = []
    for i in range(points):
        w = i / max(1, points - 1)
        # heavy at the open and into the close, quiet mid-session
        shape = 1.0 + 2.2 * math.exp(-w * 9) + 1.6 * math.exp(-(1 - w) * 7)
        weights.append(shape * math.exp(rng.gauss(0, 0.30)))
    total = sum(weights) or 1.0
    return [max(1, int(day_volume * w / total)) for w in weights]


def clock_labels(points: int, start_min: int, end_min: int) -> list[str]:
    """12-hour clock labels spread across a minute range."""
    out = []
    for i in range(points):
        m = start_min + round((end_min - start_min) * i / max(1, points - 1))
        hour24, minute = m // 60, m % 60
        suffix = "AM" if hour24 < 12 else "PM"
        hour12 = hour24 % 12 or 12
        out.append(f"{hour12}:{minute:02d} {suffix}")
    return out


def session_times(points: int) -> list[str]:
    """Clock labels across one 6.5-hour regular session."""
    return clock_labels(points,
                        SESSION_OPEN.hour * 60 + SESSION_OPEN.minute,
                        SESSION_CLOSE.hour * 60 + SESSION_CLOSE.minute)


def after_hours_times(points: int) -> list[str]:
    """Clock labels from the closing bell to the end of after-hours."""
    return clock_labels(points, SESSION_CLOSE.hour * 60, 20 * 60)


# --------------------------------------------------------------------------
# Formatting helpers (match Google Finance's own abbreviations)
# --------------------------------------------------------------------------

def fmt_big(n: float | int | None) -> str:
    if n is None:
        return "—"
    n = float(n)
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= div:
            return f"{n / div:.2f}{suf}"
    return f"{n:,.0f}"


def fmt_price(p: float | None, currency: str = "USD") -> str:
    if p is None:
        return "—"
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}.get(currency, "")
    d = _price_digits(p)
    return f"{sym}{p:,.{d}f}"


def fmt_pct(p: float | None) -> str:
    if p is None:
        return "—"
    return f"{p:+.2f}%"


def fmt_money_signed(n: float | None, currency: str = "USD") -> str:
    """Signed amount with the sign ahead of the currency symbol: -$2,233.00.

    '${:+,.2f}'.format() would put it after the symbol ($-2,233.00), which no
    finance UI does.
    """
    if n is None:
        return "—"
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}.get(currency, "")
    return f"{'-' if n < 0 else '+'}{sym}{abs(n):,.2f}"


# --------------------------------------------------------------------------
# Derived key statistics
# --------------------------------------------------------------------------

# Sectors where a dividend is the norm rather than the exception.
INCOME_SECTORS = {"Utilities", "Consumer Staples", "Energy", "Real Estate",
                  "Materials", "Financials", "Health Care", "Industrials"}

# Sector-typical fundamentals: (price/sales, net margin, dividend yield %,
# beta centre, P/E centre)
SECTOR_FUNDAMENTALS = {
    "Technology": (8.5, 0.24, 0.5, 1.15, 34),
    "Communication Services": (5.0, 0.20, 0.7, 1.10, 24),
    "Consumer Discretionary": (3.2, 0.11, 0.8, 1.20, 28),
    "Consumer Staples": (2.4, 0.10, 2.5, 0.60, 22),
    "Financials": (3.6, 0.26, 2.2, 1.00, 15),
    "Health Care": (4.4, 0.17, 1.6, 0.75, 21),
    "Industrials": (2.8, 0.12, 1.5, 1.00, 23),
    "Energy": (1.5, 0.10, 3.4, 1.05, 13),
    "Utilities": (2.6, 0.13, 3.2, 0.55, 18),
    "Real Estate": (7.0, 0.28, 3.6, 0.90, 33),
    "Materials": (2.2, 0.11, 2.0, 1.05, 19),
    "ETF": (0, 0, 1.4, 1.00, 0),
}


def equity_stats(symbol: str, sector: str, closes: list[float],
                 volumes: list[int], intraday: list[float],
                 anchors: dict | None = None) -> dict:
    """Key stats derived from the generated series — one source of truth.

    Everything downstream (market cap, P/E, EPS, the income statement) is
    computed from these same numbers, so no two fields on the page can
    disagree. That is hardening dimension D, enforced structurally.
    """
    rng = rng_for(symbol, "stats")
    ps, margin, div_y, beta_c, pe_c = SECTOR_FUNDAMENTALS.get(
        sector, SECTOR_FUNDAMENTALS["Technology"])

    price = closes[-1]
    prev_close = closes[-2]
    change = round(price - prev_close, _price_digits(price))
    change_pct = round(change / prev_close * 100, 2)

    day_open = intraday[0]
    day_high = max(intraday)
    day_low = min(intraday)

    # The 52-week band has to contain the current session, otherwise the page
    # shows a day low beneath the 52-week low.
    last_year = closes[-252:]
    wk52_high = max(max(last_year), day_high)
    wk52_low = min(min(last_year), day_low)

    # Market cap is the primary size knob; share count and traded volume are
    # derived from it. When the recon pass captured a real cap for this symbol
    # it is used as the magnitude anchor and perturbed, so a mega-cap name does
    # not end up with a mid-cap balance sheet. Deriving cap from volume instead
    # lands multi-trillion caps on ordinary names.
    anchors = anchors or {}
    if anchors.get("mkt_cap"):
        mkt_cap = anchors["mkt_cap"] * rng.uniform(0.86, 1.16)
    else:
        mkt_cap = math.exp(rng.uniform(math.log(1.2e10), math.log(3.4e12)))
    shares = int(mkt_cap / price)
    if anchors.get("avg_volume"):
        avg_volume = int(anchors["avg_volume"] * rng.uniform(0.82, 1.24))
    else:
        avg_volume = int(shares * rng.uniform(0.0022, 0.011))
    volume = int(avg_volume * (volumes[-1] / (sum(volumes[-30:]) / 30)))

    if sector == "ETF":
        eps = pe_ratio = None
        revenue_ttm = net_income_ttm = None
    else:
        revenue_ttm = mkt_cap / (ps * rng.uniform(0.75, 1.3))
        net_income_ttm = revenue_ttm * margin * rng.uniform(0.7, 1.3)
        eps = round(net_income_ttm / shares, 2)
        pe_ratio = round(price / eps, 2) if eps and eps > 0 else None

    # Who pays a dividend: income sectors essentially all do, and so do the
    # very largest names elsewhere. A flat coin flip left mega-caps like AAPL
    # showing no dividend at all, which reads as broken data rather than as a
    # non-payer.
    if sector == "ETF":
        pays_dividend = False
    elif sector in INCOME_SECTORS:
        pays_dividend = True
    else:
        pays_dividend = mkt_cap >= 8e11 or rng.random() < 0.35
    if pays_dividend:
        dividend_yield = round(max(0.05, rng.gauss(div_y, div_y * 0.35)), 2)
        quarterly_dividend = round(price * dividend_yield / 100 / 4, 2)
        ex_div = MARKET_DATE + timedelta(days=rng.randint(9, 80))
        ex_div_label = ex_div.strftime("%b %-d, %Y")
    else:
        dividend_yield = quarterly_dividend = None
        ex_div_label = None

    after_change_pct = round(rng.gauss(0, 0.28), 2)
    after_price = round(price * (1 + after_change_pct / 100), _price_digits(price))

    return {
        "price": price, "prev_close": prev_close,
        "change": change, "change_pct": change_pct,
        "day_open": day_open, "day_high": day_high, "day_low": day_low,
        "wk52_high": wk52_high, "wk52_low": wk52_low,
        "volume": volume, "avg_volume": avg_volume,
        "shares_outstanding": shares, "mkt_cap": mkt_cap,
        "eps": eps, "pe_ratio": pe_ratio,
        "beta": round(max(0.15, rng.gauss(beta_c, 0.22)), 2),
        "dividend_yield": dividend_yield,
        "quarterly_dividend": quarterly_dividend,
        "ex_dividend_date": ex_div_label,
        "after_price": after_price,
        "after_change": round(after_price - price, _price_digits(price)),
        "after_change_pct": after_change_pct,
        "revenue_ttm": revenue_ttm, "net_income_ttm": net_income_ttm,
    }


def simple_stats(symbol: str, closes: list[float], intraday: list[float],
                 kind: str = "index") -> dict:
    """Reduced stat set used by indexes, currencies, crypto and futures."""
    price = closes[-1]
    prev_close = closes[-2]
    change = round(price - prev_close, digits_for(kind, price))
    last_year = closes[-252:]
    day_high, day_low = max(intraday), min(intraday)
    return {
        "price": price, "prev_close": prev_close, "change": change,
        "change_pct": round(change / prev_close * 100, 2),
        "day_open": intraday[0], "day_high": day_high, "day_low": day_low,
        "wk52_high": max(max(last_year), day_high),
        "wk52_low": min(min(last_year), day_low),
    }


# --------------------------------------------------------------------------
# Financial statements, earnings, analyst coverage
# --------------------------------------------------------------------------

QUARTER_ENDS = ["Mar", "Jun", "Sep", "Dec"]


def recent_quarters(n: int = 8) -> list[str]:
    """Quarter labels ending with the last completed quarter before MARKET_DATE."""
    q = (MARKET_DATE.month - 1) // 3          # 0-based quarter of MARKET_DATE
    y = MARKET_YEAR
    q -= 1                                     # last *completed* quarter
    if q < 0:
        q, y = 3, y - 1
    out = []
    for _ in range(n):
        out.append(f"{QUARTER_ENDS[q]} {y}")
        q -= 1
        if q < 0:
            q, y = 3, y - 1
    return list(reversed(out))


def income_statement(symbol: str, revenue_ttm: float, net_income_ttm: float,
                     shares: int, periods: list[str]) -> list[dict]:
    """Quarterly income statement rows that sum to the TTM figures."""
    rng = rng_for(symbol, "income")
    rows = []
    # quarterly seasonality: Dec quarter is the strongest for most issuers
    season = {"Mar": 0.92, "Jun": 0.95, "Sep": 1.00, "Dec": 1.13}
    n = len(periods)
    for i, label in enumerate(periods):
        # older quarters are smaller, so the series trends up
        growth = (1 + rng.uniform(0.015, 0.055)) ** (i - (n - 4))
        s = season[label.split()[0]]
        rev = revenue_ttm / 4 * growth * s * rng.uniform(0.97, 1.03)
        margin = (net_income_ttm / revenue_ttm) * rng.uniform(0.85, 1.15)
        ni = rev * margin
        gross = rev * rng.uniform(0.38, 0.62)
        opinc = rev * margin * rng.uniform(1.15, 1.45)
        rows.append({
            "period": label,
            "revenue": rev,
            "cost_of_revenue": rev - gross,
            "gross_profit": gross,
            "operating_expense": max(0.0, gross - opinc),
            "operating_income": opinc,
            "net_income": ni,
            "net_profit_margin": margin * 100,
            "eps": ni / shares,
            "ebitda": opinc * rng.uniform(1.12, 1.35),
            "effective_tax_rate": rng.uniform(11.0, 23.5),
        })
    return rows


def balance_sheet(symbol: str, revenue_ttm: float, periods: list[str]) -> list[dict]:
    """Quarterly balance sheet that drifts instead of jumping.

    Drawing each ratio independently per quarter made total assets swing by
    2x between consecutive periods, which no real balance sheet does. The
    company-level ratios are drawn once and then nudged a few percent a
    quarter.
    """
    rng = rng_for(symbol, "balance")
    asset_turns = rng.uniform(0.9, 2.4)        # assets / annual revenue
    leverage = rng.uniform(0.45, 0.82)         # liabilities / assets
    cash_share = rng.uniform(0.08, 0.26)
    pb = rng.uniform(2.0, 12.0)
    roa = rng.uniform(3.0, 18.0)
    roc = roa * rng.uniform(1.3, 2.1)

    rows = []
    for i, label in enumerate(periods):
        growth = (1 + rng.uniform(0.008, 0.03)) ** (i - len(periods) + 1)
        assets = revenue_ttm * asset_turns * growth * rng.uniform(0.985, 1.015)
        lev = min(0.9, max(0.2, leverage * rng.uniform(0.98, 1.02)))
        liab = assets * lev
        rows.append({
            "period": label,
            "cash_and_short_term_investments":
                assets * cash_share * rng.uniform(0.93, 1.07),
            "total_assets": assets,
            "total_liabilities": liab,
            "total_equity": assets - liab,
            "price_to_book": pb * rng.uniform(0.95, 1.05),
            "return_on_assets": roa * rng.uniform(0.92, 1.08),
            "return_on_capital": roc * rng.uniform(0.92, 1.08),
        })
    return rows


def cash_flow(symbol: str, net_income_ttm: float, periods: list[str]) -> list[dict]:
    rng = rng_for(symbol, "cashflow")
    # Conversion and reinvestment rates are company traits, not quarterly coin
    # flips; only the quarter-to-quarter noise is redrawn.
    op_conversion = rng.uniform(1.1, 1.7)
    invest_rate = rng.uniform(0.2, 0.7)
    finance_rate = rng.uniform(0.15, 0.65)
    rows = []
    for i, label in enumerate(periods):
        ni = net_income_ttm / 4 * (1 + 0.02 * i) * rng.uniform(0.9, 1.1)
        op = ni * op_conversion * rng.uniform(0.95, 1.05)
        inv = -op * invest_rate * rng.uniform(0.9, 1.1)
        fin = -op * finance_rate * rng.uniform(0.9, 1.1)
        rows.append({
            "period": label,
            "net_income": ni,
            "cash_from_operations": op,
            "cash_from_investing": inv,
            "cash_from_financing": fin,
            "net_change_in_cash": op + inv + fin,
            "free_cash_flow": op * rng.uniform(0.55, 0.9),
        })
    return rows


def earnings_rows(symbol: str, income_rows: list[dict]) -> list[dict]:
    """Reported vs. consensus for the last 8 quarters."""
    rng = rng_for(symbol, "earnings")
    out = []
    for r in income_rows:
        eps_actual = r["eps"]
        surprise = rng.gauss(0.03, 0.06)
        eps_est = eps_actual / (1 + surprise) if (1 + surprise) else eps_actual
        rev_surprise = rng.gauss(0.01, 0.03)
        rev_est = r["revenue"] / (1 + rev_surprise)
        # report date: ~4 weeks after quarter end
        mon, yr = r["period"].split()
        qend_month = {"Mar": 3, "Jun": 6, "Sep": 9, "Dec": 12}[mon]
        d = date(int(yr), qend_month, 28) + timedelta(days=rng.randint(20, 40))
        out.append({
            "quarter": r["period"],
            "report_date": d.isoformat(),
            "eps_estimate": round(eps_est, 2),
            "eps_actual": round(eps_actual, 2),
            "revenue_estimate": rev_est,
            "revenue_actual": r["revenue"],
            "surprise_pct": round((eps_actual - eps_est) / abs(eps_est) * 100, 2)
            if eps_est else 0.0,
        })
    return out


# --------------------------------------------------------------------------
# Key moments — the orange markers Google drops on the long-range charts
# --------------------------------------------------------------------------

MOVE_HEADLINES = [
    "Shares {dir} {pct:.1f}% in a single session",
    "{dir_cap} {pct:.1f}% as the sector repriced",
    "Biggest one-day {word} in months: {pct:.1f}%",
    "Stock {dir} {pct:.1f}% on heavy volume",
]


def key_moments(symbol: str, closes: list[float], calendar: list,
                earnings: list[dict] | None = None, max_moves: int = 6) -> list[dict]:
    """Notable dates for one instrument: earnings prints and outsized moves.

    Google marks these on 6M and longer with an orange halo. Deriving them from
    the same series the chart draws keeps the marker on a real inflection
    instead of an arbitrary date.
    """
    out = []
    for e in (earnings or []):
        d = e["report_date"]
        verdict = ("beat" if e["surprise_pct"] > 1 else
                   "missed" if e["surprise_pct"] < -1 else "met")
        out.append({
            "date": d,
            "kind": "earnings",
            "title": f"{e['quarter']} earnings — EPS {verdict} estimates",
        })

    # Outsized single-session moves. Picked per horizon rather than globally:
    # taking the top N across five years leaves a 1Y chart with no markers at
    # all, because the biggest moves cluster in whichever year was wildest.
    chosen = []
    for horizon, want in ((126, 3), (252, 3), (1260, 4)):
        window = min(len(closes), horizon)
        moves = sorted(
            ((abs(closes[i] / closes[i - 1] - 1), i)
             for i in range(len(closes) - window + 1, len(closes))
             if closes[i - 1]), reverse=True)
        taken = 0
        for _, i in moves:
            if taken >= want or len(chosen) >= max_moves + 4:
                break
            if all(abs(i - j) > 25 for j in chosen):
                chosen.append(i)
                taken += 1
    for i in sorted(chosen):
        pct = (closes[i] / closes[i - 1] - 1) * 100
        up = pct >= 0
        tmpl = MOVE_HEADLINES[i % len(MOVE_HEADLINES)]
        out.append({
            "date": calendar[i].isoformat(),
            "kind": "move",
            "title": tmpl.format(dir="rose" if up else "fell",
                                 dir_cap="Climbed" if up else "Slid",
                                 word="gain" if up else "drop",
                                 pct=abs(pct)),
        })
    out.sort(key=lambda m: m["date"])
    return out


# Institutional holders shown on a stock's Holdings tab. Real asset-manager
# names; the position sizes are synthetic like every other figure here.
HOLDER_FIRMS = [
    "Vanguard Group Inc", "BlackRock Inc", "State Street Corp",
    "Fidelity Management & Research", "Geode Capital Management",
    "T. Rowe Price Associates", "Capital Research Global Investors",
    "Northern Trust Corp", "Morgan Stanley Investment Management",
    "Invesco Ltd", "Legal & General Group", "Bank of America Corp",
    "Charles Schwab Investment Management", "Wellington Management",
    "Norges Bank Investment Management",
]


def institutional_holders(symbol: str, shares_outstanding: int,
                          price: float) -> list[dict]:
    """Top holders, ordered by stake. Weights fall off geometrically so the
    register looks like a real one: two or three index giants, then a tail."""
    rng = rng_for(symbol, "holders")
    n = rng.randint(8, 12)
    firms = rng.sample(HOLDER_FIRMS, n)
    firms.sort(key=lambda f: HOLDER_FIRMS.index(f))     # index funds on top
    top = rng.uniform(7.0, 9.5)
    decay = rng.uniform(0.72, 0.86)
    out, pct = [], top
    for f in firms:
        pct_here = max(0.15, pct * rng.uniform(0.9, 1.1))
        shares = int(shares_outstanding * pct_here / 100)
        out.append({
            "firm": f,
            "pct_held": round(pct_here, 2),
            "shares": shares,
            "value": shares * price,
            "change_pct": round(rng.gauss(0, 4.5), 2),   # quarter-on-quarter
        })
        pct *= decay
    return out


ANALYST_FIRMS = [
    "Morgan Stanley", "Goldman Sachs", "JPMorgan", "Bank of America",
    "Citigroup", "Wells Fargo", "Barclays", "UBS", "Jefferies",
    "Deutsche Bank", "RBC Capital", "Evercore ISI", "Bernstein",
    "Piper Sandler", "Truist Securities", "Baird", "Stifel", "Wedbush",
    "Raymond James", "Oppenheimer",
]
RATINGS = ["Strong buy", "Buy", "Hold", "Sell", "Strong sell"]


def analyst_coverage(symbol: str, price: float) -> list[dict]:
    rng = rng_for(symbol, "analysts")
    n = rng.randint(8, 16)
    firms = rng.sample(ANALYST_FIRMS, n)
    tilt = rng.uniform(-0.6, 1.1)              # per-name sentiment
    out = []
    for f in firms:
        z = rng.gauss(tilt, 0.9)
        rating = ("Strong buy" if z > 1.2 else "Buy" if z > 0.25 else
                  "Hold" if z > -0.8 else "Sell" if z > -1.6 else "Strong sell")
        upside = {"Strong buy": 0.24, "Buy": 0.13, "Hold": 0.02,
                  "Sell": -0.10, "Strong sell": -0.20}[rating]
        target = price * (1 + upside + rng.gauss(0, 0.05))
        d = MARKET_DATE - timedelta(days=rng.randint(3, 120))
        out.append({
            "firm": f, "rating": rating,
            "price_target": round(target, 2),
            "rated_on": d.isoformat(),
        })
    out.sort(key=lambda r: r["rated_on"], reverse=True)
    return out


def rating_consensus(ratings: list[dict]) -> dict:
    counts = {r: 0 for r in RATINGS}
    for r in ratings:
        counts[r["rating"]] += 1
    score_map = {"Strong buy": 5, "Buy": 4, "Hold": 3, "Sell": 2, "Strong sell": 1}
    total = len(ratings) or 1
    score = sum(score_map[r["rating"]] for r in ratings) / total
    label = ("Strong buy" if score >= 4.5 else "Buy" if score >= 3.5 else
             "Hold" if score >= 2.5 else "Sell" if score >= 1.5 else "Strong sell")
    targets = sorted(r["price_target"] for r in ratings)
    return {
        "counts": counts, "total": total,
        "score": round(score, 2), "label": label,
        "target_low": targets[0] if targets else None,
        "target_high": targets[-1] if targets else None,
        "target_mean": round(sum(targets) / len(targets), 2) if targets else None,
    }

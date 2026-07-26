"""The instrument universe for the google_finance mirror.

Identities only (ticker / exchange / class). Company metadata is harvested
from the live site by harvest_assets.py; all market data is synthesized by
the seed generator.
"""

# --- US equities, grouped by GICS sector -----------------------------------
STOCKS = {
    "Technology": [
        ("AAPL", "NASDAQ"), ("MSFT", "NASDAQ"), ("NVDA", "NASDAQ"),
        ("AVGO", "NASDAQ"), ("ORCL", "NYSE"), ("CRM", "NYSE"),
        ("AMD", "NASDAQ"), ("ADBE", "NASDAQ"), ("CSCO", "NASDAQ"),
        ("ACN", "NYSE"), ("INTC", "NASDAQ"), ("QCOM", "NASDAQ"),
        ("TXN", "NASDAQ"), ("IBM", "NYSE"), ("NOW", "NYSE"),
        ("INTU", "NASDAQ"), ("AMAT", "NASDAQ"), ("MU", "NASDAQ"),
        ("PANW", "NASDAQ"), ("LRCX", "NASDAQ"),
    ],
    "Communication Services": [
        ("GOOGL", "NASDAQ"), ("META", "NASDAQ"), ("NFLX", "NASDAQ"),
        ("DIS", "NYSE"), ("CMCSA", "NASDAQ"), ("T", "NYSE"),
        ("VZ", "NYSE"), ("TMUS", "NASDAQ"), ("EA", "NASDAQ"),
        ("WBD", "NASDAQ"),
    ],
    "Consumer Discretionary": [
        ("AMZN", "NASDAQ"), ("TSLA", "NASDAQ"), ("HD", "NYSE"),
        ("MCD", "NYSE"), ("NKE", "NYSE"), ("SBUX", "NASDAQ"),
        ("LOW", "NYSE"), ("BKNG", "NASDAQ"), ("TJX", "NYSE"),
        ("GM", "NYSE"), ("F", "NYSE"), ("ABNB", "NASDAQ"),
    ],
    "Consumer Staples": [
        ("PG", "NYSE"), ("KO", "NYSE"), ("PEP", "NASDAQ"),
        ("COST", "NASDAQ"), ("WMT", "NASDAQ"), ("PM", "NYSE"),
        ("MDLZ", "NASDAQ"), ("CL", "NYSE"), ("KMB", "NASDAQ"),
        ("GIS", "NYSE"),
    ],
    "Financials": [
        ("JPM", "NYSE"), ("BAC", "NYSE"), ("WFC", "NYSE"),
        ("GS", "NYSE"), ("MS", "NYSE"), ("C", "NYSE"),
        ("AXP", "NYSE"), ("BLK", "NYSE"), ("SCHW", "NYSE"),
        ("SPGI", "NYSE"), ("V", "NYSE"), ("MA", "NYSE"),
    ],
    "Health Care": [
        ("UNH", "NYSE"), ("JNJ", "NYSE"), ("LLY", "NYSE"),
        ("ABBV", "NYSE"), ("MRK", "NYSE"), ("PFE", "NYSE"),
        ("TMO", "NYSE"), ("ABT", "NYSE"), ("AMGN", "NASDAQ"),
        ("DHR", "NYSE"), ("GILD", "NASDAQ"), ("CVS", "NYSE"),
    ],
    "Industrials": [
        ("CAT", "NYSE"), ("BA", "NYSE"), ("HON", "NASDAQ"),
        ("GE", "NYSE"), ("UPS", "NYSE"), ("RTX", "NYSE"),
        ("LMT", "NYSE"), ("DE", "NYSE"), ("UNP", "NYSE"),
        ("MMM", "NYSE"),
    ],
    "Energy": [
        ("XOM", "NYSE"), ("CVX", "NYSE"), ("COP", "NYSE"),
        ("SLB", "NYSE"), ("EOG", "NYSE"), ("PSX", "NYSE"),
        ("MPC", "NYSE"), ("OXY", "NYSE"),
    ],
    "Utilities": [
        ("NEE", "NYSE"), ("DUK", "NYSE"), ("SO", "NYSE"),
        ("AEP", "NASDAQ"), ("D", "NYSE"), ("EXC", "NASDAQ"),
    ],
    "Real Estate": [
        ("AMT", "NYSE"), ("PLD", "NYSE"), ("EQIX", "NASDAQ"),
        ("SPG", "NYSE"), ("O", "NYSE"), ("PSA", "NYSE"),
    ],
    "Materials": [
        ("LIN", "NASDAQ"), ("SHW", "NYSE"), ("APD", "NYSE"),
        ("ECL", "NYSE"), ("NEM", "NYSE"), ("FCX", "NYSE"),
        ("DOW", "NYSE"),
    ],
}

ETFS = [
    ("SPY", "NYSEARCA"), ("VOO", "NYSEARCA"), ("QQQ", "NASDAQ"),
    ("VTI", "NYSEARCA"), ("IVV", "NYSEARCA"), ("ARKK", "BATS"),
    ("XLK", "NYSEARCA"), ("XLE", "NYSEARCA"), ("XLF", "NYSEARCA"),
    ("VIG", "NYSEARCA"), ("SCHD", "NYSEARCA"), ("IWM", "NYSEARCA"),
]

# (ticker, exchange, display name, region)
INDEXES = [
    (".DJI", "INDEXDJX", "Dow Jones Industrial Average", "us"),
    (".INX", "INDEXSP", "S&P 500", "us"),
    (".IXIC", "INDEXNASDAQ", "Nasdaq Composite", "us"),
    ("RUT", "INDEXRUSSELL", "Russell 2000 Index", "us"),
    ("VIX", "INDEXCBOE", "CBOE Volatility Index", "us"),
    ("DAX", "INDEXDB", "DAX Performance Index", "europe"),
    ("UKX", "INDEXFTSE", "FTSE 100 Index", "europe"),
    ("PX1", "INDEXEURO", "CAC 40 Index", "europe"),
    ("I", "INDEXBME", "IBEX 35 Index", "europe"),
    ("SX5E", "INDEXSTOXX", "STOXX Europe 50 Index", "europe"),
    ("NI225", "INDEXNIKKEI", "Nikkei 225", "asia"),
    ("000001", "SHA", "SSE Composite Index", "asia"),
    ("HSI", "INDEXHANGSENG", "Hang Seng Index", "asia"),
    ("SENSEX", "INDEXBOM", "S&P BSE SENSEX", "asia"),
    ("NIFTY_50", "INDEXNSE", "NIFTY 50", "asia"),
    ("SPLAC", "INDEXSP", "S&P Latin America 40", "latam"),
    ("SPCBMIRLAUSD", "INDEXSP", "S&P Latin America BMI", "latam"),
    ("IBOV", "INDEXBVMF", "IBOVESPA", "latam"),
    ("IGCX", "INDEXBVMF", "Brazil IGC Index", "latam"),
    ("IBXX", "INDEXBVMF", "Brazil IBrX 100 Index", "latam"),
]

# Magnitude anchors for the indexes the asset harvest did not visit. The
# harvest only recorded anchors for symbols whose quote page it opened; these
# six appear on the live home page's region tabs but were never opened, so
# their levels are read off the captured home-page DOM instead
# (scraped_data/recon_summary.json). Without an entry here seed_data falls
# back to DEFAULT_LEVEL['index'] = 4200 and IBOVESPA would render two orders
# of magnitude below the real index.
INDEX_LEVELS = {
    "NIFTY_50:INDEXNSE": 23767.45,
    "SPLAC:INDEXSP": 3553.29,
    "SPCBMIRLAUSD:INDEXSP": 309.42,
    "IBOV:INDEXBVMF": 174041.95,
    "IGCX:INDEXBVMF": 26932.54,
    "IBXX:INDEXBVMF": 73429.35,
}

# Left-rail CBOE equity-sector indexes: (ticker, label, matching GICS sector)
SECTOR_INDEXES = [
    ("SIXB", "Materials", "Materials"),
    ("SIXC", "Communications", "Communication Services"),
    ("SIXE", "Energy", "Energy"),
    ("SIXI", "Industrials", "Industrials"),
    ("SIXM", "Financials", "Financials"),
    ("SIXR", "Staples", "Consumer Staples"),
    ("SIXRE", "Real estate", "Real Estate"),
    ("SIXT", "Technology", "Technology"),
    ("SIXU", "Utilities", "Utilities"),
    ("SIXV", "Health care", "Health Care"),
    ("SIXY", "Discretionary", "Consumer Discretionary"),
]

CRYPTO = [
    ("BTC-USD", "Bitcoin"), ("ETH-USD", "Ethereum"), ("USDT-USD", "Tether"),
    ("XRP-USD", "XRP"), ("SOL-USD", "Solana"), ("BNB-USD", "BNB"),
    ("DOGE-USD", "Dogecoin"), ("ADA-USD", "Cardano"),
    ("AVAX-USD", "Avalanche"), ("LINK-USD", "Chainlink"),
]

CURRENCIES = [
    ("EUR-USD", "Euro / US Dollar"), ("GBP-USD", "British Pound / US Dollar"),
    ("USD-JPY", "US Dollar / Japanese Yen"), ("USD-CAD", "US Dollar / Canadian Dollar"),
    ("AUD-USD", "Australian Dollar / US Dollar"), ("USD-CHF", "US Dollar / Swiss Franc"),
    ("USD-CNY", "US Dollar / Chinese Yuan"), ("USD-INR", "US Dollar / Indian Rupee"),
    ("USD-MXN", "US Dollar / Mexican Peso"), ("EUR-GBP", "Euro / British Pound"),
]

FUTURES = [
    ("CL=F", "Crude Oil"), ("GC=F", "Gold"), ("SI=F", "Silver"),
    ("NG=F", "Natural Gas"), ("ZC=F", "Corn"), ("ES=F", "E-Mini S&P 500"),
]


def all_equity_symbols():
    """[(ticker, exchange, sector)] for stocks; ETFs get sector 'ETF'."""
    out = []
    for sector, rows in STOCKS.items():
        for t, ex in rows:
            out.append((t, ex, sector))
    for t, ex in ETFS:
        out.append((t, ex, "ETF"))
    return out


if __name__ == "__main__":
    eq = all_equity_symbols()
    print(f"stocks+etfs={len(eq)} indexes={len(INDEXES)} "
          f"sector_idx={len(SECTOR_INDEXES)} crypto={len(CRYPTO)} "
          f"fx={len(CURRENCIES)} futures={len(FUTURES)}")
    print("TOTAL:", len(eq) + len(INDEXES) + len(SECTOR_INDEXES)
          + len(CRYPTO) + len(CURRENCIES) + len(FUTURES))


# Compact labels used on the home-page index cards, matching the live site
# ("Dow Jones", not "Dow Jones Industrial Average").
SHORT_NAMES = {
    ".DJI": "Dow Jones", ".INX": "S&P 500", ".IXIC": "Nasdaq",
    "RUT": "Russell", "VIX": "VIX",
    "DAX": "DAX", "UKX": "FTSE 100", "PX1": "CAC 40",
    "I": "IBEX 35", "SX5E": "STOXX 50",
    "NI225": "Nikkei 225", "000001": "SSE", "HSI": "HSI", "SENSEX": "SENSEX",
    "NIFTY_50": "NIFTY 50",
    "SPLAC": "S&P LATAM 40", "SPCBMIRLAUSD": "S&P LATAM BMI",
    "IBOV": "IBOVESPA", "IGCX": "IGCX", "IBXX": "IBXX",
    "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "USDT-USD": "Tether",
    "XRP-USD": "XRP", "SOL-USD": "Solana", "BNB-USD": "BNB",
    "CL=F": "Crude Oil", "GC=F": "Gold", "SI=F": "Silver",
    "NG=F": "Natural Gas", "ZC=F": "Corn", "ES=F": "E-Mini S&P 500",
}

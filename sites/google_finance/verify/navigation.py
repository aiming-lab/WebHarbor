"""Route checks for observed browser URLs (never action destinations)."""

import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit


SLUGS = {
    "IBOV": "IBOV:INDEXBVMF",
    "KO": "KO:NYSE",
    "NVDA": "NVDA:NASDAQ",
    "BTC-USD": "BTC-USD",
    "BA": "BA:NYSE",
    "INTC": "INTC:NASDAQ",
    "GOOGL": "GOOGL:NASDAQ",
    "WMT": "WMT:NASDAQ",
    "CVX": "CVX:NYSE",
    "XLE": "XLE:NYSEARCA",
    "MSFT": "MSFT:NASDAQ",
    "LMT": "LMT:NYSE",
    "RTX": "RTX:NYSE",
    "HON": "HON:NASDAQ",
    "T": "T:NYSE",
    "TSLA": "TSLA:NASDAQ",
    "F": "F:NYSE",
    "AAPL": "AAPL:NASDAQ",
    "V": "V:NYSE",
    "MA": "MA:NYSE",
    "AEP": "AEP:NASDAQ",
    "D": "D:NYSE",
    "DUK": "DUK:NYSE",
    "EXC": "EXC:NASDAQ",
    "NEE": "NEE:NYSE",
    "SO": "SO:NYSE",
    "PG": "PG:NYSE",
    "XOM": "XOM:NYSE",
    "O": "O:NYSE",
    "VZ": "VZ:NYSE",
}


def observed_pages(traj):
    base = traj.get("start_url", "")
    origin = urlsplit(base)
    if origin.scheme not in ("http", "https") or not origin.netloc:
        return []
    pages = []
    for step in traj.get("steps", []):
        for key in ("url", "url_after"):
            url = step.get(key)
            if not isinstance(url, str) or not url:
                continue
            parsed = urlsplit(urljoin(base, url))
            if (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc):
                continue
            query = parse_qs(parsed.query, keep_blank_values=True)
            # Ambiguous duplicate parameters are not evidence of a selection.
            if any(len(values) != 1 for values in query.values()):
                continue
            pages.append((unquote(parsed.path), {k: v[0] for k, v in query.items()}))
    return pages


def navigation_ok(index, traj):
    pages = observed_pages(traj)

    def visit(path, **query):
        return any(
            p == path and all(q.get(k) == v for k, v in query.items()) for p, q in pages
        )

    def quote(ticker, **selection):
        defaults = {
            "range": "1D",
            "tab": "overview",
            "period": "quarterly",
            "statement": "income",
        }
        return any(
            p == "/quote/" + SLUGS[ticker]
            and all(
                q.get(k, defaults[k]).lower() == v.lower() for k, v in selection.items()
            )
            for p, q in pages
        )

    def quotes(tickers):
        return all(quote(ticker) for ticker in tickers.split())

    auth = visit("/login") or visit("/accounts/chooser")
    if index == 0:
        ok = visit("/", region="latam") and quote("IBOV")
    elif index in (1, 3):
        ok = quote({1: "KO", 3: "BTC-USD"}[index])
    elif index in (2, 10):
        ok = quote("NVDA", range="1Y")
    elif index == 4:
        ok = any(
            p == "/currency-converter"
            and q.get("from") == "USD"
            and q.get("to") == "JPY"
            and re.fullmatch(r"2500(?:\.0+)?", q.get("amount", ""))
            for p, q in pages
        )
    elif index == 5:
        ok = quote("BA") and visit(
            "/news/ba-boeing-co-outlines-a-multi-year-efficiency-plan-at-its-investor-day"
        )
    elif index == 6:
        ok = quote("INTC", tab="analysis")
    elif index in (7, 8, 9):
        ok = quote(
            {7: "GOOGL", 8: "WMT", 9: "CVX"}[index],
            tab="financials",
            statement="balance" if index == 8 else "income",
            period="annual" if index == 9 else "quarterly",
        )
    elif index in (11, 12):
        ok = quote(
            "XLE" if index == 11 else "MSFT",
            tab="holdings" if index == 11 else "earnings",
        )
    elif index == 13:
        ok = quotes("LMT RTX HON") or any(
            p == "/compare"
            and {
                s.strip().upper().split(":")[0] for s in q.get("tickers", "").split(",")
            }
            == {"LMT", "RTX", "HON"}
            for p, q in pages
        )
    elif index == 14:
        ok = visit("/markets/most-active") and quotes("INTC NVDA T TSLA F")
    elif index == 15:
        ok = visit("/markets/climate-leaders") and quotes("NVDA AAPL MSFT GOOGL V MA")
    elif index == 16:
        ok = visit("/search", q="utility") and quotes("AEP D DUK EXC NEE SO")
    elif index == 17:
        ok = auth and visit("/lists/2") and quotes("KO PG XOM DUK O VZ")
    elif index == 18:
        ok = auth and visit("/portfolios/2")
    elif index == 19:
        ok = auth and any(re.fullmatch(r"/portfolios/[1-9]\d*", p) for p, _ in pages)
    else:
        raise ValueError(f"Unknown task: {index}")
    return bool(ok), pages

"""Editorial content for the Google Finance mirror: market summaries and news.

Headlines and bodies are generated deterministically from templates so the
corpus is reproducible. They stay qualitative on purpose — no article restates
a key statistic that a benchmark task might ask for, which would turn a
detail-page lookup into a headline skim (leak archetype 4, "pre-bundled answer
sentence").
"""
from datetime import timedelta

from _market_data import MARKET_DATE, rng_for

# --------------------------------------------------------------------------
# Home-page market summaries (the "US market summary" accordion)
# --------------------------------------------------------------------------

MARKET_SUMMARIES = {
    "us": [
        ("Wall Street finishes mixed to close out a volatile week",
         "Major US stock indexes ended a fragmented session on Friday to wrap "
         "a choppy week. Large-cap benchmarks drifted in opposite directions "
         "as investors weighed a heavy earnings calendar against a firmer "
         "rates backdrop. Breadth stayed narrow: a handful of megacap names "
         "again accounted for most of the index-level movement, while the "
         "average constituent traded closer to flat.\n\n"
         "Sector performance was uneven. Rate-sensitive groups held up better "
         "than cyclicals, and defensives attracted flows late in the session "
         "as traders trimmed risk ahead of the weekend. Volume was moderate "
         "for a summer Friday.", 3),
        ("Escalating AI infrastructure expenditures rattle technology sector",
         "Technology shares came under pressure as the market re-examined the "
         "capital intensity of the current build-out cycle. Several large "
         "platform operators have guided to materially heavier spending on "
         "data-center capacity, and investors are increasingly asking when "
         "that spending converts into operating profit rather than deferred "
         "depreciation.\n\n"
         "Semiconductor and networking names traded in sympathy. Analysts "
         "covering the group are split between treating the spending as a "
         "durable demand signal and treating it as a margin headwind that has "
         "not yet been reflected in consensus estimates.", 4),
        ("Oil prices retreat from multi-month highs on potential diplomacy",
         "Crude retreated after headlines pointed to renewed diplomatic "
         "contact between major producers, easing the supply premium that had "
         "built up over the previous three weeks. Energy equities gave back "
         "part of their recent advance, though the group remains among the "
         "stronger performers over a trailing three-month window.\n\n"
         "Refining margins stayed healthy, which cushioned downstream names "
         "relative to pure exploration and production issuers.", 3),
        ("Implementation of new defensive tariff regime fuels trade worries",
         "Industrial and materials companies with cross-border supply chains "
         "traded lower after the details of a new tariff schedule circulated. "
         "Management teams have generally signalled that the direct cost is "
         "manageable, but the second-order effect on order timing is harder "
         "to forecast.\n\n"
         "Freight and logistics operators were mixed, reflecting the split "
         "between volume risk and pricing power.", 5),
    ],
    "europe": [
        ("European benchmarks close higher as rate expectations soften",
         "Continental indexes advanced, led by exporters and financials, "
         "after softer inflation prints reduced the odds of another policy "
         "tightening this year. Luxury and autos both participated, though "
         "gains faded into the close.\n\n"
         "Peripheral markets outperformed core ones, a pattern that usually "
         "accompanies a narrowing of sovereign spreads.", 3),
        ("Bank shares lead the advance on improved net interest guidance",
         "Lenders across the region moved higher after several updated their "
         "guidance for net interest income. The read-through supported the "
         "sector broadly, including names that have not yet reported.", 2),
    ],
    "asia": [
        ("Asian markets end lower as export orders cool",
         "Regional benchmarks finished in the red, with technology hardware "
         "and shipping among the weakest groups. Softer export orders and a "
         "firmer dollar weighed on sentiment through the session.\n\n"
         "Domestic-demand names held up better than exporters.", 3),
        ("Mainland indexes slip despite supportive policy signals",
         "Onshore benchmarks drifted lower even after officials reiterated "
         "support for the property and consumption channels. Investors are "
         "waiting for measurable follow-through before re-rating the market.", 2),
    ],
    "latam": [
        ("Latin American equities track commodity weakness",
         "Regional benchmarks followed industrial metals and crude lower. "
         "Currency moves amplified the decline for dollar-based investors, "
         "though local-currency returns were closer to flat.", 2),
    ],
    "currencies": [
        ("Dollar firms broadly as rate differentials widen",
         "The dollar gained against most majors as the front end of the US "
         "curve repriced. The move was orderly, with realised volatility "
         "staying below its one-year average.\n\n"
         "Commodity currencies underperformed, tracking softer crude.", 3),
    ],
    "crypto": [
        ("Digital assets consolidate after a strong month",
         "Major tokens traded in a narrow band as the market digested the "
         "prior month's advance. Spot volumes cooled from their recent peak "
         "while derivatives funding normalised.", 2),
    ],
    "futures": [
        ("Metals steady while energy contracts give back gains",
         "Precious metals held their range as real yields stalled, while "
         "energy contracts retreated on supply headlines. Agricultural "
         "contracts were mixed on weather forecasts.", 2),
    ],
}

# --------------------------------------------------------------------------
# Market-wide "Latest updates" feed
# --------------------------------------------------------------------------

MARKET_HEADLINES = [
    "Investors weigh a heavy week of earnings against a firmer rates backdrop",
    "Breadth stays narrow as megacaps drive another index-level move",
    "Fund flows rotate toward defensives for a third consecutive week",
    "Treasury curve steepens after the latest auction clears",
    "Options positioning points to a quieter August, strategists say",
    "Buyback authorisations run ahead of last year's pace",
    "Small caps lag as financing conditions stay tight",
    "Dividend growers outperform in a choppy tape",
    "Analysts trim second-half estimates across cyclicals",
    "Volatility sellers return as realised vol drops",
    "Commodity exporters diverge from importers on tariff news",
    "IPO window reopens with two large listings priced",
    "Credit spreads hold near their tightest level of the year",
    "Retail participation cools from its spring peak",
    "Passive flows continue to dominate active in equity funds",
    "Sector dispersion hits its widest reading since March",
    "Corporate guidance language turns more cautious on demand",
    "Freight rates stabilise after a two-month slide",
    "Housing-linked equities rally on a softer mortgage print",
    "Currency hedging costs fall for overseas investors",
]

MARKET_BODY_PARAS = [
    "The move played out across most of the session rather than in a single "
    "burst, which market participants generally read as repositioning rather "
    "than a reaction to a discrete headline.",
    "Desk commentary pointed to steady two-way flow. Several strategists "
    "noted that the tape has been driven more by positioning than by any "
    "change in the underlying macro picture.",
    "Options markets showed no unusual demand for downside protection, which "
    "argues against a stress interpretation of the day's price action.",
    "Attention now turns to next week's calendar, where a cluster of "
    "large-cap reports is expected to set the tone for the rest of the month.",
    "Longer-horizon investors have largely stayed the course, with allocation "
    "surveys showing little change in equity weightings over the quarter.",
]

# --------------------------------------------------------------------------
# Company news
# --------------------------------------------------------------------------

COMPANY_THEMES = [
    ("{name} expands its partner programme into two new regions",
     "{name} said it is widening a partner programme to cover two additional "
     "regions, a move management framed as a way to reach customers it has "
     "historically served indirectly. The company did not attach a revenue "
     "target to the expansion.",
     "Competitors have taken broadly similar steps over the past year, so "
     "analysts covering the group treated the announcement as a matter of "
     "keeping pace rather than a differentiator."),
    ("{name} names a new operating chief as it reorganises its business units",
     "{name} announced an internal appointment to lead operations, alongside "
     "a reshuffle that consolidates several reporting lines. The company "
     "described the change as a simplification rather than a strategy shift.",
     "Reorganisations of this kind usually take two to three quarters to show "
     "up in reported segment results, which limits what can be read into the "
     "announcement in the near term."),
    ("Analysts revisit their {name} models ahead of the next reporting period",
     "Several sell-side analysts published updated notes on {name} this week "
     "in the run-up to its next report. The distribution of views widened "
     "modestly, with the range of published price targets now broader than it "
     "was at the start of the quarter.",
     "Investors looking for the current consensus and the full target range "
     "can find the coverage detail on the company's analysis page."),
    ("{name} outlines a multi-year efficiency plan at its investor day",
     "At its investor day, {name} laid out a multi-year efficiency programme "
     "covering procurement, real estate and internal tooling. Management "
     "declined to quantify the savings beyond describing them as material to "
     "the operating line over the plan horizon.",
     "The plan does not change the company's stated capital allocation "
     "priorities, which management reiterated in the same session."),
    ("Regulators open a routine review touching {name}'s core market",
     "A sector regulator opened a routine review of competitive conditions in "
     "one of {name}'s core markets. The company said it is cooperating and "
     "does not expect the review to affect current operations.",
     "Reviews of this type typically run for several quarters before any "
     "findings are published."),
    ("{name} completes a bolt-on acquisition in an adjacent category",
     "{name} closed a small acquisition in an adjacent product category. "
     "Terms were not disclosed, and the company said the transaction is not "
     "material to its financial statements.",
     "The target's technology is expected to be folded into an existing "
     "product line rather than sold separately."),
    ("Supply chain normalises for {name} after two constrained quarters",
     "{name} told suppliers that lead times have returned to their "
     "pre-disruption range after two constrained quarters. The company had "
     "flagged the constraint as a limiting factor on fulfilment earlier in "
     "the year.",
     "Normalisation removes one of the operational headwinds management had "
     "cited, though it does not by itself change demand."),
    ("{name} refreshes its flagship product line for the coming cycle",
     "{name} introduced a refresh of its flagship line, with changes "
     "concentrated in performance and serviceability rather than pricing. "
     "The company kept its existing tier structure intact.",
     "Channel checks suggest the refresh has been received in line with "
     "previous cycles."),
    ("Institutional ownership in {name} shifts modestly last quarter",
     "Quarterly filings showed a modest rotation in {name}'s institutional "
     "register, with index-tracking holders roughly stable and a handful of "
     "active managers adjusting position sizes.",
     "Changes of this magnitude are common and rarely signal a change in the "
     "fundamental outlook."),
    ("{name} extends its buyback authorisation without changing the pace",
     "The board of {name} extended the company's existing repurchase "
     "authorisation. Management said the extension does not imply a change "
     "in the pace of execution.",
     "The company continues to fund repurchases from operating cash flow."),
]


def build_market_news(rng_key="market-news", count=20):
    """[(slug, headline, body, published_at, region)] for the market feed."""
    rng = rng_for(rng_key)
    out = []
    for i, headline in enumerate(MARKET_HEADLINES[:count]):
        minutes = int(20 * (i ** 1.55)) + rng.randint(3, 40)
        published = _stamp(minutes)
        paras = rng.sample(MARKET_BODY_PARAS, 3)
        body = "\n\n".join(paras)
        out.append((_slugify(headline), headline, body, published, "us"))
    return out


def build_company_news(ticker, name, rng_key=None, count=None):
    """[(slug, headline, summary, body, published_at)] for one instrument."""
    rng = rng_for(rng_key or f"news-{ticker}")
    n = count or rng.randint(3, 6)
    picks = rng.sample(COMPANY_THEMES, n)
    out = []
    for i, (h, p1, p2) in enumerate(picks):
        headline = h.format(name=name)
        minutes = int(90 * ((i + 1) ** 1.7)) + rng.randint(5, 300)
        published = _stamp(minutes)
        summary = p1.format(name=name)
        body = summary + "\n\n" + p2.format(name=name) + "\n\n" + \
            rng.choice(MARKET_BODY_PARAS)
        out.append((_slugify(f"{ticker}-{headline}"), headline, summary,
                    body, published))
    return out


def _stamp(minutes_ago):
    base = MARKET_DATE
    dt = (base.toordinal(), 20 * 60)          # 20:00 on the frozen date
    total = dt[1] - minutes_ago
    day_offset = 0
    while total < 0:
        total += 24 * 60
        day_offset += 1
    from datetime import datetime
    d = base - timedelta(days=day_offset)
    return datetime(d.year, d.month, d.day, total // 60, total % 60)


def _slugify(s):
    keep = []
    for ch in s.lower():
        if ch.isalnum():
            keep.append(ch)
        elif ch in " -_/":
            keep.append("-")
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:120]

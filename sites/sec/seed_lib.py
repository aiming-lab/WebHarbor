#!/usr/bin/env python3
"""Deterministic seed builder for the sec mirror.

Everything materialized here comes from the tracked source_data/*.json
snapshots (captured 2026-09-30, see provenance.json) in a fixed, sorted
order. The four benchmark accounts and their watchlists / filed records
are authored fixtures following the u_s_customs / zara / ziprecruiter
precedent: every company, filing, litigation release and press release
they reference is a real captured upstream row, and every timestamp is a
frozen constant so the SQLite output is byte-reproducible
(PYTHONHASHSEED=0).

The investor alerts / bulletins and the additional FAST Answers beyond
the five live sec.gov/answers captures are authored fixtures (marked
origin='fixture' in the DB and declared in provenance.json) because the
upstream investor.gov host blocks automated fetches with an Akamai 403.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, 'source_data')

BENCHMARK_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
MIRROR_TS = '2026-09-30'


def _load(name):
    with open(os.path.join(SOURCE, name), encoding='utf-8') as f:
        return json.load(f)


def _pipe(values):
    return '|'.join(v for v in (values or []) if v)



_MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
    'july': 7, 'jul': 7, 'aug': 8, 'sept': 9, 'sep': 9, 'oct': 10,
    'nov': 11, 'dec': 12,
}


def _date_sort(date_text):
    """'Sept. 30, 2026' / 'June 11, 2026' -> '2026-09-30' (or None)."""
    if not date_text:
        return None
    m = re.search(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", date_text)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower()[:4]) or _MONTHS.get(m.group(1).lower()[:3])
    if not month:
        return None
    return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(2)):02d}"


def _year_of(date_text):
    m = re.search(r'(\d{4})', date_text or '')
    return m.group(1) if m else None


# --------------------------------------------------------------------------
# Authored fixture content (declared in provenance.json as fixtures).
# The five FAST Answers marked origin='captured' are verbatim captures of
# the live sec.gov/answers pages; the fixtures below are original mirror
# copy written to model the classic investor.gov FAST Answers catalog.
# --------------------------------------------------------------------------
FIXTURE_FAST_ANSWERS = [
    ("form10k", "Form 10-K",
     "A Form 10-K is the annual report that most reporting companies file "
     "with the SEC. It gives a comprehensive summary of the company's "
     "business and financial condition, including the audited financial "
     "statements. Companies must file a 10-K within 60 to 90 days of the "
     "end of their fiscal year, depending on the size of the company. You "
     "can find a company's 10-K filings using EDGAR company search; enter "
     "the company name or ticker and filter the filing list to Form 10-K."),
    ("form10q", "Form 10-Q",
     "A Form 10-Q is the quarterly report that reporting companies file "
     "with the SEC. It includes unaudited financial statements and "
     "provides a continuing view of the company's financial position "
     "during the year. Generally, companies must file a 10-Q within 40 to "
     "45 days of the end of each of the first three fiscal quarters. "
     "Search for a company in EDGAR and filter its filings to Form 10-Q "
     "to see the quarterly reports it has filed."),
    ("annual-report", "Annual Report",
     "An annual report is a document public companies publish once a year "
     "for their shareholders. It usually includes an audited balance "
     "sheet, income statement and cash flow statement, a letter from the "
     "chief executive, and a description of the company's operations. "
     "The Form 10-K filed with the SEC contains much of the same "
     "information; you can locate it through EDGAR company search."),
    ("insider", "Insider Trading",
     "Insider trading is the buying or selling of a security, by someone "
     "who has access to material nonpublic information about the security. "
     "Insider trading can be legal or illegal depending on when the "
     "insider makes the trade. Corporate officers, directors and employees "
     "who trade their company's securities after learning of significant "
     "confidential developments must report their trades on Forms 3, 4 "
     "and 5, which are filed with the SEC and available in EDGAR."),
    ("ponzi", "Ponzi Schemes",
     "A Ponzi scheme is an investment fraud that pays existing investors "
     "with funds collected from new investors. Ponzi scheme organizers "
     "often promise high returns with little or no risk. With little "
     "legitimate earnings, the schemes require a consistent flow of money "
     "from new investors to keep going. When it becomes hard to recruit "
     "new investors, or when large numbers of existing investors cash out, "
     "the schemes tend to collapse."),
    ("pump", "Pump-and-Dump",
     "'Pump-and-dump' schemes involve the touting of a company's stock "
     "through false or misleading statements to the marketplace. After "
     "the price has been pumped up, fraudsters dump their shares at the "
     "inflated price, leaving investors with worthless or devalued stock. "
     "Be suspicious of anyone who pressures you to buy a stock quickly or "
     "touts an investment based on a tip."),
    ("affinity", "Affinity Fraud",
     "Affinity fraud refers to investment scams that prey upon members of "
     "identifiable groups, such as religious or ethnic communities, "
     "professional associations or age groups. The fraudsters who promote "
     "these schemes often are, or pretend to be, members of the group, and "
     "they enlist respected community leaders to spread the word. Before "
     "investing, check out both the person selling the investment and the "
     "investment itself."),
    ("microcap", "Microcap Stock",
     "Microcap stock is the stock of companies with a small market "
     "capitalization, often trading for low prices. Many microcap "
     "companies trade on the over-the-counter (OTC) market, where "
     "quotations are published but listing standards are minimal. "
     "Microcap stocks can be legitimate investments, but they are also "
     "frequently the subject of fraud schemes such as pump-and-dump, so "
     "investors should be careful."),
    ("proxy-statements", "Proxy Statement",
     "A proxy statement is a document that a company must provide to its "
     "shareholders before a shareholder meeting. It discloses the matters "
     "on which shareholders will vote, including the election of "
     "directors, and contains information about executive compensation "
     "and potential conflicts of interest. Proxy materials are filed with "
     "the SEC and are available through EDGAR."),
    ("secfees", "Section 31 Fees",
     "Section 31 of the Securities Exchange Act of 1934 requires "
     "self-regulatory organizations to pay transaction fees to the SEC "
     "based on the volume of securities sold. Brokers pass these fees on "
     "to their customers, usually itemized separately on trade "
     "confirmations. The SEC adjusts the fee rate periodically based on "
     "statutory formulas."),
]

FIXTURE_ALERTS = [
    ("ponzi-schemes", "alert", "Ponzi Schemes: Don't Let the Next Victim Be You",
     "Aug. 12, 2026",
     "Ponzi schemes are investment frauds that pay returns to earlier "
     "investors with money from newer investors.",
     ["Ponzi schemes share three warning signs: high returns with little "
      "or no risk, overly consistent returns, and unregistered "
      "investments with unlicensed sellers.",
      "Ponzi promoters rarely invest the money they raise. Instead they "
      "use new investors' cash to pay 'returns' to earlier investors, "
      "which keeps the illusion of a profitable business alive.",
      "Verify any promoter and any investment before you send money. Ask "
      "how the returns are generated, request audited financials, and use "
      "the SEC's and FINRA's free tools to check whether the seller is "
      "licensed and registered.",
      "If you suspect a Ponzi scheme, stop sending money immediately and "
      "file a complaint with the SEC at sec.gov."]),
    ("cold-call", "alert", "Cold Callers: Beware of Strangers Touting Stocks",
     "July 28, 2026",
     "Cold callers use high-pressure tactics to sell investments you did "
     "not ask about and cannot verify.",
     ["A cold call is an unsolicited phone call, email or message from "
      "someone you do not know pitching an investment opportunity. "
      "Fraudsters use scripts designed to create urgency and fear of "
      "missing out.",
      "Watch for these red flags: the caller refuses to send written "
      "information, demands an immediate decision, promises guaranteed "
      "returns, or says the offer is 'confidential'.",
      "Before you invest with anyone who contacts you out of the blue, "
      "check the seller's registration history using the SEC's investor "
      "tools, and never wire money to someone you cannot verify.",
      "Report suspicious cold calls to the SEC through the online Tips, "
      "Complaints & Referrals form."]),
    ("crypto-asset", "alert", "Investor Alert: Fraud Involving Crypto Assets",
     "June 16, 2026",
     "Scammers continue to exploit the popularity of crypto assets to "
     "steal money from retail investors.",
     ["Fraudsters promote crypto asset 'investments' with claims of "
      "guaranteed returns, celebrity endorsements, or exclusive access. "
      "These are hallmarks of a scam, not a security.",
      "Crypto asset investments are often highly volatile, and many "
      "promoters are not registered with the SEC or any regulator. "
      "Unregistered offerings carry no protections if something goes "
      "wrong.",
      "Be suspicious of anyone who asks you to pay for an investment "
      "using crypto assets, gift cards or wire transfers, or who "
      "recruits you to bring in friends for a bonus.",
      "Check whether a crypto asset offering is registered using EDGAR "
      "full-text search, and file a tip with the SEC if you spot a scam."]),
    ("relationship", "alert", "Romance and Relationship Scams Involving Investments",
     "May 21, 2026",
     "Scammers build fake online relationships to steer victims into "
     "fraudulent investment platforms.",
     ["In a relationship investment scam, a stranger builds trust over "
      "weeks or months on a dating app or social network, then introduces "
      "an 'amazing' investment opportunity.",
      "The scammer may show you a fake trading dashboard with growing "
      "profits and let you withdraw a small amount once, to build "
      "confidence before you invest more.",
      "No matter how close you feel to this person, never send money, "
      "share financial account details, or invest on a platform you "
      "learned about from someone you have never met in person.",
      "If you or someone you know has sent money, stop all contact, "
      "report the profile to the platform, and file a complaint with the "
      "SEC."]),
    ("municipal", "alert", "Investor Alert: Understanding Municipal Bond Risks",
     "Apr. 14, 2026",
     "Municipal bonds can offer tax advantages, but they are not "
     "risk-free.",
     ["Municipal bonds are debt securities issued by states, cities and "
      "other public bodies. Interest income is often exempt from federal "
      "tax, which makes them attractive to many investors.",
      "Key risks include credit risk — some issuers have weak finances — "
      "call risk, which lets the issuer redeem the bond early, and "
      "interest rate risk, since bond prices fall when rates rise.",
      "Before buying, read the issuer's continuing disclosures on "
      "EMMA, the Municipal Securities Rulemaking Board's free site, and "
      "compare the yield with taxable alternatives.",
      "Ask your financial professional whether the bond is right for "
      "your goals, and remember that 'tax-exempt' never means 'safe'."]),
    ("free-lunch", "alert", "Free Lunch Seminars: What Investors Should Know",
     "Mar. 9, 2026",
     "Free meal seminars are a common way promoters reach older "
     "investors with investment pitches.",
     ["Seminar promoters use free meals, gifts and educational-sounding "
      "titles to draw attendees. The real goal is often to sell complex or "
      "illiquid products such as variable annuities or non-traded REITs.",
      "The person pitching may not be licensed at all. Ask for the "
      "speaker's name and firm, then use the SEC's and FINRA's public "
      "tools to verify the license and disciplinary history.",
      "Never make an investment decision at the seminar. Take the "
      "materials home, compare alternatives, and consult a trusted "
      "third party such as an attorney or financial planner.",
      "If you feel pressured — 'this offer expires today' — walk away. "
      "Legitimate investments will still be available tomorrow."]),
    ("401k", "bulletin", "Investor Bulletin: Understanding Your 401(k) Plan",
     "Feb. 17, 2026",
     "A 401(k) plan is a workplace retirement plan that lets you save "
     "through payroll deductions, often with an employer match.",
     ["Your 401(k) contributions are usually deducted before taxes, and "
      "earnings grow tax-deferred until withdrawal. Many employers match "
      "a portion of what you contribute — capture the full match if you "
      "can.",
      "Investment menus typically include stock funds, bond funds and "
      "money market or stable value options. Higher expected returns "
      "come with higher risk; diversification across funds reduces it.",
      "Watch the fees: expense ratios, administrative fees and "
      "transaction costs compound over decades. Compare the annual fee "
      "disclosure your plan must provide.",
      "If you change jobs, you can generally leave the money in the "
      "plan, roll it into an IRA, or move it to a new employer's plan. "
      "Each choice has different costs and protections."]),
    ("fees", "bulletin", "Investor Bulletin: How Fees and Expenses Reduce Your Returns",
     "Jan. 20, 2026",
     "Every dollar you pay in fees is a dollar that does not compound "
     "for you.",
     ["Investment costs come in many forms: sales loads, management "
      "expense ratios, 12b-1 fees, account maintenance fees and "
      "transaction charges.",
      "Fees compound exactly like returns. Over a 30-year horizon, a "
      "1% annual fee difference can consume roughly a quarter of your "
      "final balance.",
      "Read the fee table in every prospectus, and ask your financial "
      "professional how they are compensated for each product they "
      "recommend.",
      "The SEC requires broker-dealers and investment advisers to give "
      "retail investors a relationship summary (Form CRS) describing "
      "services, fees and conflicts of interest. Ask for it."]),
    ("crowdfunding", "bulletin", "Investor Bulletin: Risks of Investment Crowdfunding",
     "Dec. 8, 2025",
     "Regulation crowdfunding lets small companies raise money online "
     "from retail investors, but the risks are substantial.",
     ["Startups fail often. Many crowdfunding investments lose all of "
      "their value, and even successful ones can take years to produce "
      "any return.",
      "These securities are generally illiquid: there is no active "
      "marketplace, so you may not be able to sell when you want to.",
      "Funding portals must be registered with the SEC and FINRA, but "
      "the companies raising money do not register their offerings the "
      "way public companies do, so disclosure is limited.",
      "Limit your exposure: federal rules cap how much any individual "
      "may invest in crowdfunding over a 12-month period, and those "
      "limits exist for a reason."]),
]


def seed_all(db):
    from app import (AdminProceeding, Company, Complaint, EmailSubscription,
                     FastAnswer, Filing, FtsDoc, FormIndex, InvestorAlert,
                     LitRelease, PressRelease, Question, Rulemaking, Speech,
                     Tip, TradingSuspension, WhatsNew, PageContent)

    for name in ('home.json', 'site_pages.json', 'forms_index.json',
                 'litigation_releases.json', 'litigation_details.json',
                 'admin_proceedings.json', 'admin_details.json',
                 'trading_suspensions.json'):
        db.session.add(PageContent(name=name, payload=_load(name)))

    # ------------------------------------------------------------- companies
    for row in sorted(_load('edgar_companies.json'), key=lambda r: r['cik']):
        db.session.add(Company(
            cik=row['cik'],
            name=row['name'],
            ticker=row['ticker'],
            tickers=_pipe(row.get('tickers')),
            exchanges=_pipe(row.get('exchanges')),
            sic=str(row.get('sic') or '') or None,
            sic_description=row.get('sic_description'),
            state=row.get('state_of_incorporation'),
            category=row.get('category'),
            fiscal_year_end=row.get('fiscal_year_end'),
            description=row.get('description'),
            website=row.get('website'),
            ein=row.get('ein'),
        ))
        for f in row['filings']:
            db.session.add(Filing(
                cik=row['cik'],
                accession=f['accession'],
                form=f['form'],
                filed=f['filed'],
                report_date=f.get('report_date'),
                acceptance=f.get('acceptance'),
                items=f.get('items'),
                primary_doc=f.get('primary_doc'),
                primary_desc=f.get('primary_desc'),
                file_num=f.get('file_num'),
                film_num=f.get('film_num'),
                size=f.get('size'),
                is_xbrl=bool(f.get('is_xbrl')),
                doc_url=f.get('doc_url'),
            ))

    # ------------------------------------------------------------- fts docs
    for capture in _load('fts_captures.json'):
        for rank, hit in enumerate(capture['hits']):
            db.session.add(FtsDoc(
                query_term=capture['query'],
                query_form=capture['form'],
                hit_id=hit['id'],
                score=hit.get('score'),
                cik=(hit.get('cik') or '').zfill(10) if hit.get('cik') else None,
                display_name=(hit.get('display_names') or [''])[0],
                form=hit.get('form'),
                file_date=hit.get('file_date'),
                period=hit.get('period'),
                adsh=hit.get('adsh'),
                biz_state=(hit.get('biz_states') or [None])[0],
                sic=str((hit.get('sics') or [None])[0] or '') or None,
                file_num=(hit.get('file_num') or [None])[0],
                root_form=(hit.get('root_forms') or [None])[0],
                total_value=capture.get('total_value'),
                total_relation=capture.get('total_relation'),
                rank=rank,
            ))

    # -------------------------------------------------------- press releases
    for row in _load('press_releases.json'):
        db.session.add(PressRelease(
            slug=row['slug'],
            title=row['title'],
            date=row['date'],
            date_sort=_date_sort(row['date']),
            release_no=row['release_no'],
            body='\n\n'.join(row['paragraphs']),
            related=json.dumps(row['related'], sort_keys=True),
        ))

    # ------------------------------------------------------ litigation pages
    details = {d['slug']: d for d in _load('litigation_details.json')}
    for row in _load('litigation_releases.json'):
        slug = (row['release_no'] or '').lower()
        d = details.get(slug, {})
        db.session.add(LitRelease(
            slug=slug,
            release_no=row['release_no'],
            date=row['date'],
            date_sort=_date_sort(row['date']),
            respondents=row['respondents'],
            title=d.get('title'),
            text=d.get('text'),
            resources=json.dumps(d.get('resources') or row['links'],
                                 sort_keys=True),
            last_reviewed=d.get('last_reviewed'),
            year=_year_of(row['date']),
        ))

    # ------------------------------------------------------ admin proceeding
    admin_details = {d['slug']: d for d in _load('admin_details.json')}
    for row in _load('admin_proceedings.json'):
        slug = None
        for link in row['links']:
            if link['href'].startswith(
                    '/enforcement-litigation/administrative-proceedings/'):
                slug = link['href'].rsplit('/', 1)[-1]
        d = admin_details.get(slug, {})
        db.session.add(AdminProceeding(
            date=row['date'],
            date_sort=_date_sort(row['date']),
            respondents=row['respondents'],
            release_no=row['release_no'],
            file_number=row['file_number'],
            slug=slug,
            title=d.get('title'),
            text=d.get('text'),
            resources=json.dumps(d.get('resources') or row['links'],
                                 sort_keys=True),
            last_reviewed=d.get('last_reviewed'),
        ))

    # ---------------------------------------------------- trading suspensions
    for row in _load('trading_suspensions.json'):
        db.session.add(TradingSuspension(
            date=row['date'],
            date_sort=_date_sort(row['date']),
            company=row['respondents'],
            release_no=row['release_no'],
            resources=json.dumps(row['links'], sort_keys=True),
        ))

    # ------------------------------------------------------------- rulemaking
    for row in _load('rulemaking.json'):
        status = None
        m = re.match(r'(Final Rule|Proposed Rule|Interim Final|Concept '
                     r'Release|Interpretive Release)', row['status_releases'])
        if m:
            status = m.group(1)
        db.session.add(Rulemaking(
            date=row['date'],
            date_sort=_date_sort(row['date']),
            file_no=row['file_no'] or None,
            title=row['title'],
            status_releases=row['status_releases'],
            status=status,
        ))

    # --------------------------------------------------------------- speeches
    for row in _load('speeches.json'):
        db.session.add(Speech(
            slug=row['href'].rsplit('/', 1)[-1],
            title=row['title'],
            speaker=row['speaker'],
            kind=row['type'],
            date=row['date'],
            date_sort=_date_sort(row['date']),
            datetime=row['datetime'],
        ))

    # -------------------------------------------------------------- whats new
    for row in _load('whats_new.json'):
        db.session.add(WhatsNew(
            href=row['href'],
            title=row['title'],
            kind=row['type'],
            date=row['date'],
        ))

    # ------------------------------------------------------------ forms index
    forms = _load('forms_index.json')
    for row in forms['rows']:
        cells = row['cells']
        filed_by, statutes = [], []
        for cell in cells:
            for label in [f['label'] for f in
                          forms['facets']['field_audience_target_id']]:
                if label in cell:
                    filed_by.append(label)
            for label in [f['label'] for f in
                          forms['facets']['field_act_target_id']]:
                if label in cell:
                    statutes.append(label)
        db.session.add(FormIndex(
            form=row.get('form'),
            title=row['title'],
            pdf=row['pdf'],
            last_updated=row.get('last_updated'),
            sec_number=row.get('sec_number'),
            filed_by=_pipe(sorted(set(filed_by))),
            statutes=_pipe(sorted(set(statutes))),
        ))

    # ----------------------------------------------------------- fast answers
    for row in _load('fast_answers_live.json'):
        db.session.add(FastAnswer(
            slug=row['slug'],
            title=row['title'],
            body=row['text'],
            modified=row['modified'],
            origin='captured',
        ))
    for slug, title, body in FIXTURE_FAST_ANSWERS:
        db.session.add(FastAnswer(slug=slug, title=title, body=body,
                                  modified=None, origin='fixture'))

    # -------------------------------------------------------- investor alerts
    for slug, kind, title, date, summary, paragraphs in FIXTURE_ALERTS:
        db.session.add(InvestorAlert(
            slug=slug, kind=kind, title=title, date=date,
            date_sort=_date_sort(date), summary=summary,
            body='\n\n'.join(paragraphs), origin='fixture',
        ))

    db.session.commit()


def seed_benchmark_users(db):
    from app import (Complaint, Question, Tip, User, WatchlistItem, Company)

    if User.query.filter_by(email='alice.j@test.com').first():
        return

    users = [
        ('alice.j@test.com', 'Alice Johnson',
         'watchlist: Apple Inc. and Microsoft Corp; one filed investor '
         'complaint about a brokerage firm'),
        ('bob.c@test.com', 'Bob Chen',
         'watchlist: Tesla, Inc. and NVIDIA Corp; one filed TCR tip about '
         'suspected insider trading'),
        ('carol.d@test.com', 'Carol Davis',
         'watchlist: Amazon.com, Inc.; one investor question submitted to '
         'the OIEA help desk'),
        ('dana.k@test.com', 'Dana Kim',
         'watchlist: Alphabet Inc. and Meta Platforms, Inc.; one email '
         'subscription for investor updates'),
    ]
    for email, name, _fixture in users:
        db.session.add(User(email=email, name=name,
                            password_hash=BENCHMARK_HASH, joined=MIRROR_TS))
    db.session.commit()

    def _uid(email):
        return User.query.filter_by(email=email).first().id

    def _cik(ticker):
        return Company.query.filter_by(ticker=ticker).first().cik

    alice, bob = _uid('alice.j@test.com'), _uid('bob.c@test.com')
    carol, dana = _uid('carol.d@test.com'), _uid('dana.k@test.com')

    def watch(uid, ticker):
        db.session.add(WatchlistItem(user_id=uid, cik=_cik(ticker),
                                     added_at=MIRROR_TS))

    watch(alice, 'AAPL')
    watch(alice, 'MSFT')
    watch(bob, 'TSLA')
    watch(bob, 'NVDA')
    watch(carol, 'AMZN')
    watch(dana, 'GOOGL')
    watch(dana, 'META')

    # Alice's filed investor complaint (real form flow, authored fixture
    # record keyed to the benchmark user).
    db.session.add(Complaint(
        reference='IC-8F2A91C7', user_id=alice, name='Alice Johnson',
        email='alice.j@test.com', your_role='individual investor',
        issue_type='unauthorized trading',
        subject_firm='Meridian Brokerage Services LLC',
        subject_person='A. Reyes', subject_ticker=None,
        address='41 Chestnut Street, Boston, MA 02116',
        phone='617-555-0134',
        details='My adviser bought shares in my account without calling me '
        'first, after I told him in writing to hold off.',
        submitted_at=MIRROR_TS))

    # Bob's filed TCR tip.
    db.session.add(Tip(
        reference='TCR-3D61B0E5', user_id=bob, name='Bob Chen',
        email='bob.c@test.com', violation_type='insider trading',
        subject_firm='Halcyon Dynamics Corp',
        subject_person='J. Weller', subject_ticker='HLDX',
        market='equities',
        details='An executive I know sold a large block of shares two days '
        'before the company announced bad news.',
        submitted_at=MIRROR_TS))

    # Carol's submitted question.
    db.session.add(Question(
        reference='Q-77C4A2D9', name='Carol Davis',
        email='carol.d@test.com', topic='investment professional',
        question='How can I check whether the adviser who contacted me is '
        'registered with the SEC?',
        submitted_at=MIRROR_TS))

    db.session.commit()

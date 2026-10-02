"""Reviewer-written verifier contract tests for the sec mirror.

Independent adversarial suite for the reviewer-authored deterministic
verifiers (verify_lib.py + verify_0.py..verify_19.py, written from the
reviewer's own two-round honest Chromium walks of the review container —
not from the contributor's contract):

* structure gates       — tasks.jsonl shape, spec shape, cross-references
* no-op rejection       — every verifier fails a do-nothing trajectory
* forged-evidence gates — honest answer without navigation fails;
                           full package without the frozen seed fails
* answer polarity       — honest answers pass; per-claim corruption and
                           forbidden-value injections all fail; a few
                           honest paraphrases pass
* navigation gates      — full walked URL set passes; dropping any
                           required surface fails; off-origin steps fail
* state-delta gates     — exact added/removed rows pass; no change,
                           wrong rows and collateral writes fail
* package gates         — stale question text / wrong task id / bad
                           termination / missing or non-PNG screenshots
                           fail closed

The optional end-to-end replay of the reviewer's two honest browser-walk
rounds against every verifier runs when WH_SEC_EVIDENCE points at the
review evidence tree (kept outside this repository).
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

V = Path(__file__).resolve().parents[1]
SITE = V.parent
sys.path.insert(0, str(V))

import verify_lib  # noqa: E402

# frozen ground truth from the reviewer's walks (round1 == round2 modulo
# server-generated reference numbers)

HONEST = {0: 'Form 10-K: filing date 2025-10-31, period of report 2025-09-27, accession '
    '0000320193-25-000079. Form 10-Q: filing date 2026-07-31, period of report 2026-06-27, '
    'accession 0000320193-26-000020. The 10-K covers the longer period.',
 1: 'Form 10-K matches 10000 documents; the leading result is Artificial Intelligence Technology '
    'Solutions Inc. (AITX) (CIK 0001498148) 10-K 2021-06-01 0001161697-21-000289 ex_99-1.htm. Form '
    '8-K matches 10000 documents. Narrowed from 2020-01-01, the snapshot lists 7 documents.',
 2: "Microsoft's CIK is 0000789019, its SIC code and description are 7372 — Services-Prepackaged "
    'Software, its state of incorporation is WA and its filer category is Large accelerated filer. '
    'Its most recent DEF 14A was filed 2025-10-21 with accession number 0001193125-25-245150. '
    "Microsoft has 6 8-K filings in this snapshot. Bob's watchlist now shows 3 companies.",
 3: 'Latest Form 8-K: filed 2026-09-29, period 2026-09-29, items 1.01,1.02,2.03,9.01, accession '
    '0001628280-26-063820. Previous Form 8-K: filed 2026-07-22, period 2026-07-22, items '
    '2.02,9.01, accession 0001628280-26-049213. Shared items: 9.01. Primary document filename: '
    'tsla-20260929.htm.',
 4: 'The Brown/Grant/Noble litigation release is LR-26660. Michael Noble must pay a total of '
    '$1,074,984.36. The Trevon Brown administrative proceeding is release 34-106553, file number '
    '3-22766.',
 5: 'The settled order against Quillan Black and the other unregistered brokers is dated Sept. 30, '
    '2026. The page lists 7 file numbers, and the civil penalties are $125,000 for Quillan Black '
    'and $85,000 for Tyler MacKechnie. 7 order PDFs are linked under Resources, the first labeled '
    'PDFOrder - Quillan Black. The TCR reference number is TCR-36E95B0B.',
 6: 'Happy City Holdings was suspended June 11, 2026 with release number 34-105675. The cold '
    'callers alert lists red flags including refuses to send written information, demands an '
    "immediate decision, promises guaranteed returns, or says the offer is 'confidential'. After "
    'pumping the price, fraudsters dump their shares at the inflated price, leaving investors with '
    'worthless or devalued stock. The complaint reference number is IC-CAB0076D.',
 7: 'The Meyer press release is 2026-98, dated Sept. 30, 2026. Investments included SpaceX; the '
    'forfeited SpaceX investment was $3,000,000. Litigation release LR-26659 names Owen E.H. Meyer '
    'and Meyer Global Management LLC as respondents.',
 8: 'SEC486\tPDFRegulation A Offering Statement (PDF) Form 1-A Filed by: Small Businesses Statute: '
    'Securities Act of 1933\tFeb. 2025. SEC873\tPDFCurrent report pursuant to Section 13 or 15(d) '
    '(PDF) Form 8-K Filed by: Public Companies Statute: Securities Exchange Act of 1934\tFeb. '
    '2025. SEC1673\tPDFAnnual report pursuant to Section 13 or 15(d) (PDF) Form 10-K Filed by: '
    'Public Companies Statute: Securities Exchange Act of 1934\tFeb. 2025. The mirror served all '
    'three PDFs; downloaded form1a.pdf, form8-k.pdf, form10-k.pdf.',
 9: 'Form 10-K: A Form 10-K is the annual report that most reporting companies file with the SEC. '
    "It gives a comprehensive summary of the company's business and financial condition, including "
    'the audited financial statements. Companies must file a 10-K within 60 to 90 days of the end '
    "of their fiscal year, depending on the size of the company. You can find a company's 10-K "
    'filings using EDGAR company search; enter the company name or ticker and filter the filing '
    'list to Form 10-K.\n'
    '\n'
    'Form 10-Q: A Form 10-Q is the quarterly report that reporting companies file with the SEC. It '
    "includes unaudited financial statements and provides a continuing view of the company's "
    'financial position during the year. Generally, companies must file a 10-Q within 40 to 45 '
    'days of the end of each of the first three fiscal quarters. Search for a company in EDGAR and '
    'filter its filings to Form 10-Q to see the quarterly reports it has filed.\n'
    '\n'
    'Proxy Statement: Proxy Statement The SEC requires that shareholders of a company whose '
    'securities are registered under Section 12 of the Securities Exchange Act of 1934 receive a '
    'proxy statement prior to a shareholder meeting, whether an annual or special meeting. The '
    'information contained in the statement must be filed with the SEC before soliciting a '
    'shareholder vote on the election of directors and the approval of other corporate action. '
    'Solicitations, whether by management or shareholders, must disclose all important facts about '
    'the issues on which shareholders are asked to vote. To see the information required in the '
    'proxy statement, read the SEC\x92s proxy rules and view the requirements for Schedule 14A . '
    'For more information about shareholder proposals, read the rule adopted by the SEC on May 21, '
    '1998. http://www.sec.gov/answers/proxy.htm Home | Previous Page Modified: 09/08/2011',
 10: 'Ponzi Schemes: Ponzi schemes share three warning signs: high returns with little or no risk, '
     'overly consistent returns, and unregistered investments with unlicensed sellers.\n'
     '\n'
     "Ponzi promoters rarely invest the money they raise. Instead they use new investors' cash to "
     "pay 'returns' to earlier investors, which keeps the illusion of a profitable business "
     'alive.\n'
     '\n'
     'Verify any promoter and any investment before you send money. Ask how the returns are '
     "generated, request audited financials, and use the SEC's and FINRA's free tools to check "
     'whether the seller is licensed and registered.\n'
     '\n'
     'If you suspect a Ponzi scheme, stop sending money immediately and file a complaint with the '
     'SEC at sec.gov.\n'
     '\n'
     'Cold Callers: A cold call is an unsolicited phone call, email or message from someone you do '
     'not know pitching an investment opportunity. Fraudsters use scripts designed to create '
     'urgency and fear of missing out.\n'
     '\n'
     'Watch for these red flags: the caller refuses to send written information, demands an '
     "immediate decision, promises guaranteed returns, or says the offer is 'confidential'.\n"
     '\n'
     "Before you invest with anyone who contacts you out of the blue, check the seller's "
     "registration history using the SEC's investor tools, and never wire money to someone you "
     'cannot verify.\n'
     '\n'
     'Report suspicious cold calls to the SEC through the online Tips, Complaints & Referrals '
     'form.\n'
     '\n'
     "Crypto Assets: Fraudsters promote crypto asset 'investments' with claims of guaranteed "
     'returns, celebrity endorsements, or exclusive access. These are hallmarks of a scam, not a '
     'security.\n'
     '\n'
     'Crypto asset investments are often highly volatile, and many promoters are not registered '
     'with the SEC or any regulator. Unregistered offerings carry no protections if something goes '
     'wrong.\n'
     '\n'
     'Be suspicious of anyone who asks you to pay for an investment using crypto assets, gift '
     'cards or wire transfers, or who recruits you to bring in friends for a bonus.\n'
     '\n'
     'Check whether a crypto asset offering is registered using EDGAR full-text search, and file a '
     'tip with the SEC if you spot a scam.',
 11: 'Sept. 30, 2026 S7-2026-34 Interval Fund Modernization; Expansion of Multiple Share Class to '
     'Registered Closed-End Management Investment Companies and Business Development Companies '
     'Proposed Rule Interval Fund Modernization; Expansion of Multiple Share Class to Registered '
     'Closed-End Management Investment Companies and Business Development Companies 33-11444, '
     '34-106534, IC-36351. This is a proposed rule. Evan submitted his question under reference '
     'Q-D9B4ED13.',
 12: 'SEC Charges Meyer Global Management and Its CEO With Defrauding Retail Investors in Private '
     'Funds That Held Interests in SpaceX and Other Pre-IPO Securities; release 2026-98, dated '
     'Sept. 30, 2026, concerns investments in SpaceX. Zoe Financial was charged with failing to '
     'fully and fairly disclose material facts concerning conflicts of interest; release 2026-94, '
     'dated Sept. 28, 2026. news.fan@example.com is now subscribed to press releases.',
 13: 'The complaint reference number is IC-FB3DAEB9, and My Account shows the new complaint '
     'against Granite Harbor Capital LLC.',
 14: 'The investor question reference number is Q-E03D46FE. One red flag from the cold callers '
     'alert: it refuses to send written information, demands an immediate decision, promises '
     "guaranteed returns, or says the offer is 'confidential'. updates.carol@example.com is now "
     'subscribed to SEC email updates with the investor alerts topic.',
 15: "Dana's watchlist now shows 3 companies: 0001652044 Alphabet Inc. GOOGL 2026-09-30  Remove; "
     '0001318605 Tesla, Inc. TSLA 2026-09-30  Remove; 0001045810 NVIDIA CORP NVDA 2026-09-30  '
     'Remove.',
 16: "Alphabet's CIK is 0001652044 and its SIC description is 7370 — Services-Computer "
     'Programming, Data Processing, Etc.. After signing out and back in, the watchlist still '
     'lists: 0001652044 Alphabet Inc. GOOGL 2026-09-30  Remove.',
 17: 'Goldman Sachs: CIK 0000886982, state of incorporation DE, SIC 6211 — Security Brokers, '
     'Dealers & Flotation Companies, filer category Large accelerated filer; 1 10-K filings, the '
     'newest filed 10-K Documents 10-K Acc-no: 0000886982-26-000091 2026-02-25 001-14965 26680257 '
     'with period of report 2025-12-31; 3 10-Q filings, the newest filed 10-Q Documents 10-Q '
     'Acc-no: 0000886982-26-000297 2026-08-03 001-14965 261234571. Microsoft: CIK 0000789019, '
     'state of incorporation WA, SIC 7372 — Services-Prepackaged Software, filer category Large '
     'accelerated filer; 3 10-K filings, the newest filed 10-K Documents 10-K Acc-no: '
     '0001193125-26-323660 2026-07-29 001-37845 261217433 with period of report 2026-06-30; 4 10-Q '
     'filings, the newest filed 10-Q Documents 10-Q Acc-no: 0001193125-26-191507 2026-04-29 '
     '001-37845 26915896. Microsoft has more 10-K filings in this snapshot.',
 18: 'Two red flags from the crypto assets alert: guaranteed returns, celebrity endorsements, or '
     'exclusive access, and crypto assets, gift cards or wire transfers. Ponzi organizers often '
     'promise high returns with little or no risk. The TCR reference number is TCR-AED38B97.',
 19: 'Filtered to year 2026, the litigation releases page shows 100 releases. The Robert Bernardi '
     'and Sunil Chandra release is LR-26661, dated Sept. 30, 2026; it charges the former CEO and '
     'Vice President of GigaMedia Access Corporation. The OTC Link LLC administrative proceeding '
     'detail page is titled SEC Censures OTC Link LLC for Repeated Compliance Failures Related to '
     "Regulation SCI. In What's New, the first item listed is LR-26662 and the division shown for "
     'it is Enforcement.'}
WALK_URLS = {0: ['http://localhost:40152/',
     'http://localhost:40152/search-filings/cik-lookup?company=Apple',
     'http://localhost:40152/edgar/company/0000320193',
     'http://localhost:40152/edgar/company/0000320193?type=10-K&dateb=',
     'http://localhost:40152/edgar/filing/0000320193/0000320193-25-000079',
     'http://localhost:40152/edgar/company/0000320193?type=10-Q&dateb=',
     'http://localhost:40152/edgar/filing/0000320193/0000320193-26-000020'],
 1: ['http://localhost:40152/',
     'http://localhost:40152/search-filings',
     'http://localhost:40152/edgar/full-text-search',
     'http://localhost:40152/edgar/full-text-search?q=artificial+intelligence&forms=10-K&datea=&dateb=',
     'http://localhost:40152/edgar/full-text-search?q=artificial+intelligence&forms=8-K&datea=&dateb=',
     'http://localhost:40152/edgar/full-text-search?q=artificial+intelligence&forms=10-K&datea=2020-01-01&dateb='],
 2: ['http://localhost:40152/',
     'http://localhost:40152/search-filings/cik-lookup?company=Microsoft',
     'http://localhost:40152/edgar/company/0000789019',
     'http://localhost:40152/edgar/company/0000789019?type=DEF+14A&dateb=',
     'http://localhost:40152/edgar/filing/0000789019/0001193125-25-245150',
     'http://localhost:40152/edgar/company/0000789019?type=8-K&dateb=',
     'http://localhost:40152/login',
     'http://localhost:40152/account'],
 3: ['http://localhost:40152/',
     'http://localhost:40152/search-filings/cik-lookup?company=Tesla',
     'http://localhost:40152/edgar/company/0001318605',
     'http://localhost:40152/edgar/company/0001318605?type=8-K&dateb=',
     'http://localhost:40152/edgar/filing/0001318605/0001628280-26-063820',
     'http://localhost:40152/edgar/filing/0001318605/0001628280-26-063820/document',
     'http://localhost:40152/edgar/filing/0001318605/0001628280-26-049213'],
 4: ['http://localhost:40152/',
     'http://localhost:40152/enforcement-litigation',
     'http://localhost:40152/enforcement-litigation/litigation-releases',
     'http://localhost:40152/enforcement-litigation/litigation-releases?q=Noble&year=',
     'http://localhost:40152/enforcement-litigation/litigation-releases/lr-26660',
     'http://localhost:40152/enforcement-litigation/administrative-proceedings',
     'http://localhost:40152/enforcement-litigation/administrative-proceedings?q=Brown'],
 5: ['http://localhost:40152/',
     'http://localhost:40152/enforcement-litigation',
     'http://localhost:40152/enforcement-litigation/administrative-proceedings',
     'http://localhost:40152/enforcement-litigation/administrative-proceedings?q=Black',
     'http://localhost:40152/enforcement-litigation/administrative-proceedings/34-106538-s',
     'http://localhost:40152/login',
     'http://localhost:40152/account',
     'http://localhost:40152/submit-tip-or-complaint',
     'http://localhost:40152/submit-tip-or-complaint/tcr-disclaimer',
     'http://localhost:40152/submit-tip-or-complaint/report-possible-securities-law-violations',
     'http://localhost:40152/submit-tip-or-complaint/confirmation/TCR-36E95B0B'],
 6: ['http://localhost:40152/',
     'http://localhost:40152/enforcement-litigation',
     'http://localhost:40152/enforcement-litigation/trading-suspensions',
     'http://localhost:40152/enforcement-litigation/trading-suspensions?q=Happy+City',
     'http://localhost:40152/resources-investors',
     'http://localhost:40152/resources-investors/investor-alerts-bulletins',
     'http://localhost:40152/resources-investors/investor-alerts-bulletins/cold-call',
     'http://localhost:40152/fast-answers',
     'http://localhost:40152/fast-answers?q=pump',
     'http://localhost:40152/fast-answers/pump',
     'http://localhost:40152/submit-tip-or-complaint',
     'http://localhost:40152/submit-tip-or-complaint/report-problem-investment-account-or-financial-professional',
     'http://localhost:40152/submit-tip-or-complaint/complaint-confirmation/IC-CAB0076D'],
 7: ['http://localhost:40152/',
     'http://localhost:40152/newsroom',
     'http://localhost:40152/newsroom/press-releases/2026-98-sec-charges-meyer-global-management-its-ceo-defrauding-retail-investors-private-funds-held-interests',
     'http://localhost:40152/enforcement-litigation',
     'http://localhost:40152/enforcement-litigation/litigation-releases',
     'http://localhost:40152/enforcement-litigation/litigation-releases?q=Meyer&year=',
     'http://localhost:40152/enforcement-litigation/litigation-releases/lr-26659'],
 8: ['http://localhost:40152/',
     'http://localhost:40152/submit-filings/forms-index',
     'http://localhost:40152/submit-filings/forms-index?q=1-A&filed_by=&statute=',
     'http://localhost:40152/submit-filings/forms-index?q=8-K&filed_by=&statute=',
     'http://localhost:40152/submit-filings/forms-index?q=10-K&filed_by=&statute='],
 9: ['http://localhost:40152/',
     'http://localhost:40152/fast-answers',
     'http://localhost:40152/fast-answers?q=10-K',
     'http://localhost:40152/fast-answers/form10k',
     'http://localhost:40152/fast-answers?q=10-Q',
     'http://localhost:40152/fast-answers/form10q',
     'http://localhost:40152/fast-answers?q=proxy',
     'http://localhost:40152/fast-answers/proxy'],
 10: ['http://localhost:40152/',
      'http://localhost:40152/resources-investors',
      'http://localhost:40152/resources-investors/investor-alerts-bulletins',
      'http://localhost:40152/resources-investors/investor-alerts-bulletins/ponzi-schemes',
      'http://localhost:40152/resources-investors/investor-alerts-bulletins/cold-call',
      'http://localhost:40152/resources-investors/investor-alerts-bulletins/crypto-asset'],
 11: ['http://localhost:40152/',
      'http://localhost:40152/rules-regulations/rulemaking-activity',
      'http://localhost:40152/rules-regulations/rulemaking-activity?q=Interval+Fund+Modernization&status=',
      'http://localhost:40152/submit-tip-or-complaint',
      'http://localhost:40152/submit-tip-or-complaint/report-problem-sec-or-self-regulatory-organization',
      'http://localhost:40152/submit-tip-or-complaint/question-confirmation/Q-D9B4ED13'],
 12: ['http://localhost:40152/',
      'http://localhost:40152/newsroom',
      'http://localhost:40152/newsroom/press-releases/2026-98-sec-charges-meyer-global-management-its-ceo-defrauding-retail-investors-private-funds-held-interests',
      'http://localhost:40152/newsroom/press-releases',
      'http://localhost:40152/newsroom/press-releases?q=Zoe+Financial',
      'http://localhost:40152/newsroom/press-releases/2026-94-sec-charges-registered-investment-adviser-zoe-financial-failure-disclose-conflict-interest',
      'http://localhost:40152/subscribe'],
 13: ['http://localhost:40152/',
      'http://localhost:40152/login',
      'http://localhost:40152/account',
      'http://localhost:40152/submit-tip-or-complaint',
      'http://localhost:40152/submit-tip-or-complaint/report-problem-investment-account-or-financial-professional',
      'http://localhost:40152/submit-tip-or-complaint/complaint-confirmation/IC-FB3DAEB9'],
 14: ['http://localhost:40152/',
      'http://localhost:40152/login',
      'http://localhost:40152/account',
      'http://localhost:40152/submit-tip-or-complaint',
      'http://localhost:40152/submit-tip-or-complaint/report-problem-sec-or-self-regulatory-organization',
      'http://localhost:40152/submit-tip-or-complaint/question-confirmation/Q-E03D46FE',
      'http://localhost:40152/resources-investors',
      'http://localhost:40152/resources-investors/investor-alerts-bulletins',
      'http://localhost:40152/resources-investors/investor-alerts-bulletins/cold-call',
      'http://localhost:40152/subscribe'],
 15: ['http://localhost:40152/',
      'http://localhost:40152/login',
      'http://localhost:40152/account',
      'http://localhost:40152/search-filings/cik-lookup?company=Tesla',
      'http://localhost:40152/edgar/company/0001318605',
      'http://localhost:40152/search-filings/cik-lookup?company=NVIDIA',
      'http://localhost:40152/edgar/company/0001045810'],
 16: ['http://localhost:40152/',
      'http://localhost:40152/signup',
      'http://localhost:40152/account',
      'http://localhost:40152/search-filings/cik-lookup?company=Alphabet',
      'http://localhost:40152/edgar/company/0001652044',
      'http://localhost:40152/login'],
 17: ['http://localhost:40152/',
      'http://localhost:40152/search-filings/cik-lookup?company=Goldman+Sachs',
      'http://localhost:40152/edgar/company/0000886982',
      'http://localhost:40152/edgar/company/0000886982?type=10-K&dateb=',
      'http://localhost:40152/edgar/filing/0000886982/0000886982-26-000091',
      'http://localhost:40152/edgar/company/0000886982?type=10-Q&dateb=',
      'http://localhost:40152/search-filings/cik-lookup?company=Microsoft',
      'http://localhost:40152/edgar/company/0000789019',
      'http://localhost:40152/edgar/company/0000789019?type=10-K&dateb=',
      'http://localhost:40152/edgar/filing/0000789019/0001193125-26-323660',
      'http://localhost:40152/edgar/company/0000789019?type=10-Q&dateb='],
 18: ['http://localhost:40152/',
      'http://localhost:40152/resources-investors',
      'http://localhost:40152/resources-investors/investor-alerts-bulletins',
      'http://localhost:40152/resources-investors/investor-alerts-bulletins/crypto-asset',
      'http://localhost:40152/fast-answers',
      'http://localhost:40152/fast-answers?q=Ponzi',
      'http://localhost:40152/fast-answers/ponzi',
      'http://localhost:40152/submit-tip-or-complaint',
      'http://localhost:40152/submit-tip-or-complaint/tcr-disclaimer',
      'http://localhost:40152/submit-tip-or-complaint/report-possible-securities-law-violations',
      'http://localhost:40152/submit-tip-or-complaint/confirmation/TCR-AED38B97'],
 19: ['http://localhost:40152/',
      'http://localhost:40152/enforcement-litigation',
      'http://localhost:40152/enforcement-litigation/litigation-releases',
      'http://localhost:40152/enforcement-litigation/litigation-releases?q=&year=2026',
      'http://localhost:40152/enforcement-litigation/litigation-releases?q=Bernardi&year=2026',
      'http://localhost:40152/enforcement-litigation/litigation-releases/lr-26661',
      'http://localhost:40152/enforcement-litigation/administrative-proceedings',
      'http://localhost:40152/enforcement-litigation/administrative-proceedings?q=OTC+Link',
      'http://localhost:40152/enforcement-litigation/administrative-proceedings/34-106458-s',
      'http://localhost:40152/newsroom',
      'http://localhost:40152/newsroom/whats-new',
      'http://localhost:40152/enforcement-litigation/litigation-releases/lr-26662']}


SPECS = {}
for _i in range(20):
    _spec = importlib.util.spec_from_file_location(
        f'sec_verify_{_i}', V / f'verify_{_i}.py')
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    SPECS[_i] = _mod.SPEC

TASKS = {json.loads(line)['id']: json.loads(line)
         for line in (SITE / 'tasks.jsonl').read_text().splitlines() if line.strip()}

# a real 1x1 PNG: decodable, so only the *content* gates can reject fakes
TINY_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQAB'
    'h6FO1AAAAABJRU5ErkJggg==')

EVIDENCE = os.environ.get('WH_SEC_EVIDENCE')


def _run_verifier(i, run_dir):
    return subprocess.run(
        [sys.executable, str(V / f'verify_{i}.py'), '--run_dir', str(run_dir)],
        capture_output=True, text=True)


def _make_run(i, *, steps=None, answer=None, question=None, task_id=None,
              shots=True, base=None):
    """Synthesize a run dir; defaults mimic an honest package."""
    root = Path(tempfile.mkdtemp(prefix=f'sec-verify-t{i}-'))
    task = TASKS[f'SEC.gov--{i}']
    if steps is None:
        steps = [{'step': n, 'url': u, 'action': 'click',
                  'url_before': 'about:blank', 'url_after': u,
                  'screenshot': f's{n}.png'}
                 for n, u in enumerate(WALK_URLS[i])]
    if answer is None:
        answer = HONEST[i]
    traj = {
        'task_id': task_id or task['id'],
        'task': question if question is not None else task['ques'],
        'start_url': task['web'],
        'steps': steps,
        'terminated': True,
        'termination_reason': 'agent_done',
        'final_answer': answer,
    }
    (root / 'trajectory.json').write_text(json.dumps(traj))
    if shots:
        (root / 'screenshots').mkdir()
        for step in steps:
            for key in ('screenshot', 'screenshot_before', 'screenshot_after'):
                name = step.get(key)
                if name:
                    (root / 'screenshots' / name).write_bytes(TINY_PNG)
    if base is not None:
        import shutil
        shutil.copy2(base, root / 'initial.db')
        shutil.copy2(base, root / 'after.db')
    return root


# ---------------------------------------------------------------- structure

def test_tasks_file_shape():
    lines = [l for l in (SITE / 'tasks.jsonl').read_text().splitlines() if l.strip()]
    assert len(lines) == 20
    for n, line in enumerate(lines):
        row = json.loads(line)
        assert row['id'] == f'SEC.gov--{n}'
        assert sorted(row) == ['id', 'judge_rubric', 'ques', 'upstream_url',
                               'verifier_path', 'web', 'web_name'], row['id']
        assert 'answer' not in row
        assert row['verifier_path'] == f'sites/sec/verify/verify_{n}.py'
        assert (SITE / f'verify/verify_{n}.py').is_file()
        rubric = row['judge_rubric']
        assert rubric.isascii(), row['id']
        assert rubric.startswith('FACT CHECKPOINTS'), row['id']
        assert len(rubric) > 150, row['id']


@pytest.mark.parametrize('i', range(20))
def test_spec_shape(i):
    spec = SPECS[i]
    assert spec['task_id'] == f'SEC.gov--{i}'
    assert spec['paths'] and spec['claims']
    for pattern in spec['paths'] + [p for _, p in spec['claims']] + \
            [p for _, p in spec.get('forbidden', [])]:
        re.compile(pattern)
    for table in spec.get('state', {}):
        assert table in ('users', 'questions', 'email_subscriptions',
                         'watchlist_items', 'complaints', 'tips'), table

    def _keys(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from _keys(value)
        elif isinstance(node, list):
            for value in node:
                yield from _keys(value)

    assert 'answer' not in list(_keys(spec))
    assert all(label.lower() != 'answer'
               for label, _ in spec['claims'])


# ---------------------------------------------------------------- answer layer

@pytest.mark.parametrize('i', range(20))
def test_honest_answer_passes(i):
    verify_lib.check_answer(HONEST[i], SPECS[i])


@pytest.mark.parametrize('i', range(20))
def test_empty_answer_fails(i):
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_answer('', SPECS[i])


def _claims(i):
    return [(label, pattern) for label, pattern in SPECS[i]['claims']]


@pytest.mark.parametrize('i,label,pattern', [
    (i, label, pattern) for i in range(20) for label, pattern in _claims(i)],
    ids=[f'{i}-{label}' for i in range(20) for label, _ in _claims(i)])
def test_corrupted_claim_fails(i, label, pattern):
    text = verify_lib.norm(HONEST[i])
    assert re.search(pattern, text, re.I), (i, label)
    corrupted = re.sub(pattern, 'NOMATCHXX', text, flags=re.I)
    assert corrupted != text
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_answer(corrupted, SPECS[i])


def test_reversed_comparison_direction_fails():
    """PR #350 r3: the comparison claim must bind entity AND direction —
    'The 10-Q covers the longer period.' is the wrong direction and must
    fail, not merely miss a 'longer' token."""
    honest = verify_lib.norm(HONEST[0])
    assert re.search(SPECS[0]['claims'][6][1], honest, re.I)
    reversed_answer = honest.replace(
        'the 10-k covers the longer period',
        'the 10-q covers the longer period')
    assert reversed_answer != honest
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_answer(reversed_answer, SPECS[0])


def test_comparison_claim_rejects_10q_longer_attributions():
    text = verify_lib.norm(
        "Apple's most recent Form 10-K was filed 2025-10-31 with period of "
        "report 2025-09-27 and accession number 0000320193-25-000079. The "
        "most recent Form 10-Q was filed 2026-07-31 with period of report "
        "2026-06-27 and accession number 0000320193-26-000020. The 10-Q "
        "covers the longer period. Alice's watchlist now shows 3 companies.")
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_answer(text, SPECS[0])
    forbidden = [p for _, p in SPECS[0]['forbidden']]
    assert any(re.search(p, text, re.I) for p in forbidden)


# forbidden-value injections: honest answer + one fabricated sentence
INJECTIONS = {
    0: [" Alice's watchlist shows 2 companies on the watchlist."],
    1: [' Apple has 4 10-Ks in this snapshot.',
        ' Narrowed to 2020-01-01, the results table lists 6 documents.'],
    2: [' Tesla lists 7 8-Ks.'],
    3: [' Tesla lists 6 Form 4s.',
        " The most recent 8-K's period of report is 2026-08-29.",
        " The next 8-K's period of report is 2026-08-22.",
        " The newest Form 4's period of report is 2026-08-05."],
    4: [' The total payment is $731,281.',
        ' Noble must pay 293,703 dollars.'],
    5: [' The penalty was $85,000 for Quillan Black.',
        ' The penalty was $125,000 for Tyler MacKechnie.',
        " Quillan Black's penalty was $85,000."],
    6: [' The suspension began June 12, 2026.',
        ' The suspension began July 11, 2026.'],
    7: [' The search returned 5 releases.',
        ' The search returned 12 releases.'],
    8: [' The Public Companies filter leaves 17 forms.',
        ' The Securities Act of 1933 filter leaves 29 forms.'],
    9: [' The 10-K origin is captured from the live page.'],
    10: [' Filtering to bulletins shows 4 items.',
          ' Switching to alerts shows 7 items.',
          " Searching the catalog for risks shows 5 items."],
    11: [' Proposed Rules shows 17 items.',
          ' Final Rules shows 27 items.',
          ' The catalog shows 48 items in total.'],
    12: [' The Zoe Financial release is number 2026-95.',
          ' The latest press release is number 2026-97.'],
    13: [' The reference is IC-00000000.',
         ' The reference is IC-12345678.'],
    14: [' The reference is Q-00000000.',
         ' The reference is Q-12345678.'],
    15: [' Meta Platforms is still on the list.'],
    16: [" Alphabet's CIK is 0001652045."],
    17: [' Goldman Sachs has more 10-K filings.',
         ' Goldman Sachs shows 2 10-K filings.',
         ' Microsoft shows 2 10-K filings.'],
    18: [' The query matches 5502 documents.'],
    19: [' The year 2026 lists 99 releases.',
         ' The year 2026 lists 101 releases.'],
}


EQUIVALENTS = {
    0: ("Apple's latest Form 10-Q was filed 2026-07-31 (period of report "
        "2026-06-27, accession 0000320193-26-000020); the most recent Form "
        "10-K was filed 2025-10-31 with period of report 2025-09-27 and "
        "accession number 0000320193-25-000079, so the 10-K period is longer. "
        "Her watchlist now displays 3 companies."),
    3: ("Tesla's newest 8-K (filed 2026-09-29, accession 0001628280-26-063820) "
        "lists items 1.01, 1.02, 2.03 and 9.01 and its period of report is "
        "2026-09-29; the next one (filed 2026-07-22, accession "
        "0001628280-26-049213) lists items 2.02 and 9.01 and its period of "
        "report is 2026-07-22. They share 9.01. The primary document page "
        "shows the filename tsla-20260929.htm. Tesla shows 5 Form 4s; the "
        "newest Form 4's period of report is 2026-09-05, and Tesla lists "
        "4 10-Qs."),
    15: ("Dana's watchlist now has 3 companies - Alphabet Inc. (GOOGL), "
         "Tesla, Inc. (TSLA) and NVIDIA CORP (NVDA)."),
}


# ---------------------------------------------------------------- navigation

@pytest.mark.parametrize('i', range(20))
def test_full_walk_urls_pass(i):
    verify_lib.check_navigation(WALK_URLS[i], SPECS[i])


@pytest.mark.parametrize('i,pattern', [
    (i, pattern) for i in range(20) for pattern in SPECS[i]['paths']],
    ids=[f'{i}-p{n}' for i in range(20)
         for n in range(len(SPECS[i]['paths']))])
def test_dropping_required_surface_fails(i, pattern):
    keep = [u for u in WALK_URLS[i] if not re.search(pattern, u, re.I)]
    assert len(keep) < len(WALK_URLS[i])
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_navigation(keep, SPECS[i])


@pytest.mark.parametrize('i', [0, 7, 15])
def test_off_origin_trajectory_fails(i):
    run = _make_run(i)
    try:
        traj = json.loads((run / 'trajectory.json').read_text())
        traj['steps'].append({'step': 99, 'url': 'http://evil.example.com/x',
                              'action': 'click'})
        (run / 'trajectory.json').write_text(json.dumps(traj))
        with pytest.raises(verify_lib.Fail):
            verify_lib.check_package(
                {**traj, '_run_dir': str(run)}, SPECS[i])
    finally:
        import shutil
        shutil.rmtree(run, ignore_errors=True)


# ---------------------------------------------------------------- package gates

@pytest.mark.parametrize('i', range(20))
def test_stale_question_fails(i):
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_package(
            {'task_id': f'SEC.gov--{i}', 'task': 'an older question text',
             'terminated': True, 'termination_reason': 'agent_done',
             'final_answer': HONEST[i],
             'start_url': TASKS[f'SEC.gov--{i}']['web'], 'steps': []},
            SPECS[i])


@pytest.mark.parametrize('i', [4, 11, 19])
def test_wrong_task_id_fails(i):
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_package(
            {'task_id': 'SEC.gov--0', 'task': TASKS[f'SEC.gov--{i}']['ques'],
             'terminated': True, 'termination_reason': 'agent_done',
             'final_answer': HONEST[i],
             'start_url': TASKS[f'SEC.gov--{i}']['web'], 'steps': []},
            SPECS[i])


@pytest.mark.parametrize('i', [2, 9, 16])
def test_unterminated_trajectory_fails(i):
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_package(
            {'task_id': f'SEC.gov--{i}', 'task': TASKS[f'SEC.gov--{i}']['ques'],
             'terminated': False, 'termination_reason': 'max_steps',
             'final_answer': HONEST[i],
             'start_url': TASKS[f'SEC.gov--{i}']['web'], 'steps': []},
            SPECS[i])


def _package_run(i):
    return {'task_id': f'SEC.gov--{i}', 'task': TASKS[f'SEC.gov--{i}']['ques'],
            'terminated': True, 'termination_reason': 'agent_done',
            'final_answer': HONEST[i],
            'start_url': TASKS[f'SEC.gov--{i}']['web']}


def test_missing_screenshot_fails(tmp_path):
    run = {'steps': [{'step': 0, 'url': TASKS['SEC.gov--1']['web'],
                      'action': 'navigate', 'screenshot': 'nope.png'}],
           **_package_run(1)}
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_package({**run, '_run_dir': str(tmp_path)},
                                 SPECS[1])


def test_non_png_screenshot_fails(tmp_path):
    (tmp_path / 'screenshots').mkdir()
    (tmp_path / 'screenshots' / 'fake.png').write_bytes(b'not a png')
    run = {'steps': [{'step': 0, 'url': TASKS['SEC.gov--1']['web'],
                      'action': 'navigate', 'screenshot': 'fake.png'}],
           **_package_run(1)}
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_package({**run, '_run_dir': str(tmp_path)},
                                 SPECS[1])


def test_tampered_seed_fails(tmp_path):
    """A structurally valid but non-frozen initial DB must fail closed."""
    import sqlite3
    db = tmp_path / 'initial.db'
    con = sqlite3.connect(db)
    con.executescript('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);'
                     'INSERT INTO users VALUES (1, "tampered");')
    con.commit()
    con.close()
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_seed(db)


@pytest.mark.parametrize('i', [t for t in range(20) if not SPECS[t].get('state')])
def test_readonly_task_rejects_any_write(i):
    """Read-only tasks must fail on any DB mutation (read pollution)."""
    initial = {'watchlist_items': {
        '1': {'id': 1, 'user_id': 1, 'cik': '0000320193',
              'added_at': '2026-09-30'}}}
    after = {'watchlist_items': {
        '1': {'id': 1, 'user_id': 1, 'cik': '0000320193',
              'added_at': '2026-09-30'},
        '2': {'id': 2, 'user_id': 1, 'cik': '0001318605',
              'added_at': '2026-09-30'}}}
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_state(initial, after, SPECS[i])


# ---------------------------------------------------------------- state layer

def _rows(spec_rows, **overrides):
    """Materialize synthetic rows that satisfy the spec matchers."""
    import bcrypt
    out = []
    for expect in spec_rows:
        row = {}
        for col, want in expect.items():
            if isinstance(want, dict):
                if 'regex' in want:
                    row[col] = re.fullmatch(want['regex'], 'X' * 8).string \
                        if False else 'TCR-9Z8Y7X6W' if col == 'reference' \
                        and 'TCR' in want['regex'] else (
                        'IC-9Z8Y7X6W' if col == 'reference'
                        and 'IC' in want['regex'] else (
                        'Q-9Z8Y7X6W' if col == 'reference' else
                        ('Is Interval Fund Modernization in effect and how could it affect redemptions?' if col == 'question' else 'x' * max(want.get('min_len', 1), 1))))
                elif 'min_len' in want:
                    samples = {
                        'bob.c@test.com': 'An unregistered broker offered me security-based swaps.',
                        'maria.lopez@example.com': 'A stranger called pitching Happy City shares.',
                        'alice.j@test.com': 'My broker traded without my authorization.',
                        'carol.d@test.com': 'How can I check that an adviser is registered?',
                        'jordan.lee@test.com': 'A stranger offered a crypto token guaranteed to double.',
                    }
                    row[col] = samples[expect['email']] if want.get('patterns') else 'x' * want['min_len']
                elif 'bcrypt_password' in want:
                    row[col] = bcrypt.hashpw(
                        want['bcrypt_password'].encode(),
                        bcrypt.gensalt(rounds=4)).decode()
            else:
                row[col] = want
        row.update(overrides)
        out.append(row)
    return out


def _state_cases():
    for i, spec in SPECS.items():
        if spec.get('state'):
            yield i, spec['state']


STATEFUL = [i for i, spec in SPECS.items() if spec.get('state')]


def _synthetic_deltas(state, good=True, skip_table=None, keep_removed=False):
    """Build (initial, after) dicts realizing the state spec (or breaking it)."""
    initial, after = {}, {}
    for table, delta in state.items():
        if skip_table == table:
            continue
        pre = {'id': 9001, 'note': 'pre-existing row'}
        i_rows = {'k0': dict(pre)}
        a_rows = {'k0': dict(pre)}
        if good:
            for n, row in enumerate(_rows(delta.get('added', []))):
                r = dict(row)
                r.setdefault('id', 9100 + n)
                a_rows[f'a{n}'] = r
            for n, row in enumerate(delta.get('removed', [])):
                r = dict(row)
                r.setdefault('id', 9200 + n)
                r['note'] = 'doomed row'
                if not keep_removed:
                    i_rows[f'r{n}'] = r
                else:
                    a_rows[f'r{n}'] = r
                    i_rows[f'r{n}'] = r
        else:
            expects = (delta.get('added', []) or delta.get('removed', []) or [{}])
            expect = expects[0]
            bad = dict(_rows(expects)[0])
            bad['note'] = 'wrong row'
            # corrupt one spec-matched column so the row is genuinely wrong
            first = sorted(expect)[0]
            want = expect[first]
            if isinstance(want, dict):
                if 'regex' in want:
                    bad[first] = 'XX-INVALID'
                elif 'min_len' in want:
                    bad[first] = ''
                elif 'bcrypt_password' in want:
                    bad[first] = 'not-a-bcrypt-hash'
                else:
                    bad[first] = '__none__'
            else:
                bad[first] = 'WRONG-VALUE'
            a_rows['bad'] = bad
        initial[table], after[table] = i_rows, a_rows
    return initial, after


@pytest.mark.parametrize('i', STATEFUL)
def test_correct_state_delta_passes(i):
    initial, after = _synthetic_deltas(SPECS[i]['state'])
    verify_lib.check_state(initial, after, SPECS[i])


@pytest.mark.parametrize('i', STATEFUL)
def test_no_state_change_fails(i):
    initial, _after = _synthetic_deltas(SPECS[i]['state'])
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_state(initial, dict(initial), SPECS[i])


@pytest.mark.parametrize('i', STATEFUL)
def test_wrong_state_row_fails(i):
    initial, after = _synthetic_deltas(SPECS[i]['state'], good=False)
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_state(initial, after, SPECS[i])


@pytest.mark.parametrize('i', [t for t in STATEFUL if len(SPECS[t]['state']) > 1])
def test_partial_state_change_fails(i):
    table = sorted(SPECS[i]['state'])[0]
    initial, after = _synthetic_deltas(SPECS[i]['state'], skip_table=table)
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_state(initial, after, SPECS[i])


def test_rowid_reuse_delete_plus_insert_is_added_not_changed():
    # watchlist task 15: Meta removed, Tesla+NVIDIA added, SQLite reuses ids
    initial = {'watchlist_items': {
        '7': {'id': 7, 'user_id': 4, 'cik': '0001326801',
              'added_at': '2026-09-30'},
        '6': {'id': 6, 'user_id': 4, 'cik': '0001652044',
              'added_at': '2026-09-30'}}}
    after = {'watchlist_items': {
        '6': {'id': 6, 'user_id': 4, 'cik': '0001652044',
              'added_at': '2026-09-30'},
        '7': {'id': 7, 'user_id': 4, 'cik': '0001318605',
              'added_at': '2026-09-30'},
        '8': {'id': 8, 'user_id': 4, 'cik': '0001045810',
              'added_at': '2026-09-30'}}}
    verify_lib.check_state(initial, after, SPECS[15])


# ------------------------------------------- state-change multiplicity (PR #350 r3)

def test_duplicate_added_rows_are_not_one_addition():
    """Two identical new watchlist rows must never satisfy 'exactly one'
    required addition (minimal control for the check_state fix)."""
    pre = {'id': 1, 'user_id': 1, 'cik': '0000320193',
           'added_at': '2026-09-30'}
    tesla = lambda i: {'id': i, 'user_id': 1, 'cik': '0001318605',
                       'added_at': '2026-09-30'}
    initial = {'watchlist_items': {'k0': dict(pre)}}
    after = {'watchlist_items': {'k0': dict(pre), 'a0': tesla(2),
                                 'a1': tesla(3)}}
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_state(initial, after, SPECS[0])


def test_duplicate_removed_rows_are_not_one_removal():
    """Removing the same content row twice must not satisfy a single
    expected removal (task 15's Meta Platforms removal)."""
    meta = lambda i: {'id': i, 'user_id': 4, 'cik': '0001326801',
                      'added_at': '2026-09-30'}
    initial = {'watchlist_items': {'m0': meta(6), 'm1': meta(9)}}
    after = {'watchlist_items': {}}
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_state(initial, after, SPECS[15])


def test_identical_rows_never_consume_two_expectations():
    """Expected [Tesla, NVIDIA] with actual [Tesla, Tesla] must fail:
    one-to-one consumption, not any-match."""
    pre = {'id': 7, 'user_id': 4, 'cik': '0001326801',
           'added_at': '2026-09-30'}
    tesla = lambda i: {'id': i, 'user_id': 4, 'cik': '0001318605',
                       'added_at': '2026-09-30'}
    initial = {'watchlist_items': {'k0': dict(pre)}}
    after = {'watchlist_items': {'k0': dict(pre), 'a0': tesla(10),
                                 'a1': tesla(11)}}
    with pytest.raises(verify_lib.Fail):
        verify_lib.check_state(initial, after, SPECS[15])


def test_repeated_expectations_consume_repeated_rows():
    """Positive control: an honest double addition of identical content
    is accepted when the spec lists the expectation twice."""
    pre = {'id': 1, 'user_id': 1, 'cik': '0000320193',
           'added_at': '2026-09-30'}
    tesla = lambda i: {'id': i, 'user_id': 1, 'cik': '0001318605',
                       'added_at': '2026-09-30'}
    spec = {'state': {'watchlist_items': {
        'added': [dict(user_id=1, cik='0001318605',
                       added_at='2026-09-30')] * 2}}}
    initial = {'watchlist_items': {'k0': dict(pre)}}
    after = {'watchlist_items': {'k0': dict(pre), 'a0': tesla(2),
                                 'a1': tesla(3)}}
    verify_lib.check_state(initial, after, spec)


# ---------------------------------------------------------------- end-to-end no-ops

@pytest.mark.parametrize('i', range(20))
def test_verifier_rejects_pure_noop(i):
    run = _make_run(i, steps=[], answer='')
    try:
        result = _run_verifier(i, run)
        assert result.returncode == 1
        assert json.loads(result.stdout)['pass'] is False
    finally:
        import shutil
        shutil.rmtree(run, ignore_errors=True)


@pytest.mark.parametrize('i', range(20))
def test_verifier_rejects_forged_answer_without_navigation(i):
    run = _make_run(i, steps=[])
    try:
        result = _run_verifier(i, run)
        assert result.returncode == 1
        assert json.loads(result.stdout)['pass'] is False
    finally:
        import shutil
        shutil.rmtree(run, ignore_errors=True)


@pytest.mark.parametrize('i', range(20))
def test_verifier_rejects_full_package_without_frozen_seed(i):
    run = _make_run(i)
    try:
        result = _run_verifier(i, run)
        assert result.returncode == 1
        assert json.loads(result.stdout)['pass'] is False
    finally:
        import shutil
        shutil.rmtree(run, ignore_errors=True)


# ---------------------------------------------------------------- evidence replay

@pytest.mark.skipif(not EVIDENCE, reason='WH_SEC_EVIDENCE not set')
@pytest.mark.parametrize('i,round_', [(i, r) for i in range(20)
                                      for r in ('round1', 'round2')])
def test_honest_walk_replay_passes(i, round_):
    run_dir = Path(EVIDENCE) / 'runs' / round_ / f'{i:02d}'
    result = _run_verifier(i, run_dir)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)['pass'] is True


@pytest.mark.skipif(not EVIDENCE, reason='WH_SEC_EVIDENCE not set')
def test_two_rounds_have_zero_fact_drift():
    ref = re.compile(r'(TCR|IC|Q)-[A-Z0-9]{8}')
    for i in range(20):
        a1 = json.loads((Path(EVIDENCE) / 'runs' / 'round1' / f'{i:02d}' /
                         'trajectory.json').read_text())['final_answer']
        a2 = json.loads((Path(EVIDENCE) / 'runs' / 'round2' / f'{i:02d}' /
                         'trajectory.json').read_text())['final_answer']
        assert ref.sub('REF', a1) == ref.sub('REF', a2), i


@pytest.mark.skipif(not EVIDENCE, reason='WH_SEC_EVIDENCE not set')
def test_replayed_initial_db_is_the_frozen_seed():
    import hashlib
    for round_ in ('round1', 'round2'):
        for i in range(20):
            db = Path(EVIDENCE) / 'runs' / round_ / f'{i:02d}' / 'initial.db'
            h = hashlib.sha256(db.read_bytes()).hexdigest()
            assert h == verify_lib.SEED_SHA256, (round_, i)

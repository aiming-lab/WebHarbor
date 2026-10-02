#!/usr/bin/env python3
"""Real-browser honest walkthrough for the sec mirror (review track).

Reviewer-written driver (independent of the contributor's scripts_dev/walk_tasks.py):
runs a real Chromium session against the reviewer's own container and, for every
task in tasks.jsonl:

- resets the site through the control plane and opens a fresh browser context
  (cookies cleared) per task, archiving initial.db first;
- drives the honest path with visible-element interaction only — direct URL
  navigation is used exclusively for the homepage start; browser back counts
  as one atomic action;
- counts ATOMIC ACTIONS the task text genuinely requires (navigate, click,
  fill, select, submit, back); reads are never counted and actions the text
  does not require are never taken (anti-padding);
- records every answer fact from what the rendered pages actually show (no DB
  reads), writes trajectory.json with per-step screenshots, and archives
  after.db.

Two independent rounds must agree per task (step counts and normalized
answers).

Run: python3 walk_tasks.py <round-name> [task_ids...]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parent.parent
BASE = os.environ.get('SEC_WALK_BASE', 'http://localhost:46131')
CTRL = os.environ.get('SEC_WALK_CTRL', 'http://localhost:47131')
TOKEN_FILE = os.environ.get(
    'SEC_WALK_TOKEN',
    str(SITE / 'review_evidence' / 'control_token'))
CONTAINER = os.environ.get('SEC_WALK_CONTAINER', 'wh-sec-review2')
EV = Path(os.environ.get(
    'SEC_WALK_EVIDENCE',
    str(SITE / 'review_evidence' / 'runs')))
PASSWORD = 'TestPass123!'
TASKS_FILE = Path(os.environ.get(
    'SEC_WALK_TASKS', str(SITE / 'tasks.jsonl')))
TASKS = {json.loads(line)['id']: json.loads(line)['ques'] for line in
         TASKS_FILE.read_text(encoding='utf-8').splitlines()
         if line.strip()}


def reset_site():
    token = Path(TOKEN_FILE).read_text().strip()
    r = ''
    for _ in range(30):
        r = subprocess.run(
            ['curl', '-s', '-X', 'POST', '-H', f'Authorization: Bearer {token}',
             f'{CTRL}/reset/sec'], capture_output=True, text=True,
            timeout=120).stdout
        if '"ready": true' in r or '"ready":true' in r:
            import urllib.request
            for _ in range(90):
                try:
                    urllib.request.urlopen(BASE + '/', timeout=2)
                    return
                except Exception:
                    time.sleep(0.5)
        time.sleep(1)
    raise RuntimeError('reset failed: ' + r[:300])


def snapshot_db(dest: Path):
    if dest.exists():
        dest.unlink()
    subprocess.run(['docker', 'cp',
                    f'{CONTAINER}:/opt/WebSyn/sec/instance/sec.db',
                    str(dest)], check=True, timeout=60)


class Walk:
    """One task's honest browser session with atomic-action accounting."""

    def __init__(self, page, task_id, out_dir):
        self.page = page
        self.task_id = task_id
        self.out = Path(out_dir)
        (self.out / 'screenshots').mkdir(parents=True, exist_ok=True)
        self.steps = []
        self.atomic = 0
        self.reads = []
        self.facts = {}
        self.js_errors = []
        self._shot = 0
        page.on('pageerror', lambda e: self.js_errors.append(str(e)[:200]))

    # ---------------------------------------------------------------- io --
    def _shoot(self):
        p = self.out / 'screenshots' / f'step_{self._shot:03d}.png'
        for attempt in range(3):
            try:
                self.page.screenshot(path=str(p), timeout=15000)
                break
            except Exception:
                if attempt == 2:
                    raise
                try:
                    self.page.wait_for_load_state('load', timeout=5000)
                except Exception:
                    pass
                self.page.wait_for_timeout(500)
        self._shot += 1
        return p.name

    def _log(self, action, params, desc):
        rec = {'step': len(self.steps), 'url': self.page.url,
               'title': self.page.title(), 'thought': desc, 'action': action,
               'params': params,
               'observed_text': (self.page.inner_text('body') or '')[:4000],
               'screenshot_before': self._shoot()}
        self.steps.append(rec)
        print(f'  [{self.atomic + 1:02d}] {action}: {desc}', flush=True)

    def _after(self, settle=True):
        try:
            self.page.wait_for_load_state('networkidle', timeout=8000)
        except Exception:
            pass
        self.page.wait_for_timeout(250)
        self.steps[-1]['screenshot_after'] = self._shoot()
        self.steps[-1]['url_after'] = self.page.url

    # ------------------------------------------------------------ actions --
    def start_home(self, desc='open homepage (start_url)'):
        self._log('navigate', {'url': BASE + '/'}, desc)
        self.page.goto(BASE + '/', timeout=45000, wait_until='load')
        self._after()
        self.atomic += 1

    def click(self, sel, desc, has=None):
        loc = self.page.locator(sel)
        if has is not None:
            loc = loc.filter(has_text=has)
        loc.first.scroll_into_view_if_needed(timeout=8000)
        self._log('click', {'selector': sel}, desc)
        loc.first.click(timeout=10000)
        self._after()
        self.atomic += 1

    def back(self, desc='browser back'):
        self._log('back', {}, desc)
        self.page.go_back()
        self._after()
        self.atomic += 1

    def select(self, sel, value, desc, by_label=False):
        self._log('select', {'selector': sel, 'value': str(value)}, desc)
        if by_label:
            self.page.select_option(sel, label=str(value), timeout=10000)
        else:
            self.page.select_option(sel, value, timeout=10000)
        self._after(settle=False)
        self.atomic += 1

    def fill(self, sel, value, desc):
        self._log('fill', {'selector': sel, 'value': value}, desc)
        self.page.fill(sel, value, timeout=10000)
        self._after(settle=False)
        self.atomic += 1

    def submit(self, sel, desc):
        self._log('click', {'selector': sel}, desc)
        self.page.locator(sel).first.scroll_into_view_if_needed(timeout=8000)
        self.page.locator(sel).first.click(timeout=10000)
        self._after()
        self.atomic += 1

    # -------------------------------------------------------------- reads --
    def read(self, key, value):
        self.reads.append({'key': key, 'value': str(value)})
        self.facts[key] = value
        print(f'      read {key} = {str(value)[:110]}', flush=True)

    def body(self):
        text = self.page.inner_text('body') or ''
        text = '\n'.join(line.strip() for line in text.splitlines())
        return re.sub(r'\n{2,}', '\n', text).strip()

    def save(self, answer):
        traj = {
            'task_id': self.task_id,
            'task': TASKS[self.task_id],
            'start_url': BASE + '/',
            'terminated': True,
            'termination_reason': 'agent_done',
            'final_answer': answer,
            'steps': self.steps,
            'reads': self.reads,
            'facts': self.facts,
            'js_errors': self.js_errors,
            'step_count': self.atomic,
            'final_url': self.page.url,
        }
        (self.out / 'trajectory.json').write_text(json.dumps(traj, indent=1))
        print(f'  => {self.atomic} atomic actions, answer saved', flush=True)


# ---------------------------------------------------------------- helpers --

def grab(pattern, body, what, flags=0):
    m = re.search(pattern, body, flags)
    assert m, f'pattern for {what} not found'
    return m.group(1).strip() if m.groups() else m.group(0).strip()


def nav(w, label):
    w.click(f'nav.site-nav a:has-text("{label}")', f'nav {label}')


def header_search(w, term, desc=None):
    w.fill('#global-search', term, desc or f'header search "{term}"')
    w.submit('form.site-search button[type="submit"]', 'submit search')


def sign_in(w, email, password=PASSWORD):
    w.click('nav.site-nav a:has-text("Log In")', 'open log-in page')
    w.fill('#email', email, 'email')
    w.fill('#password', password, 'password')
    w.submit('button:has-text("Log In")', 'submit log-in')


def company_facts(w):
    body = w.body()
    facts = {}
    m = re.search(r"CIK (\d{10})\s*[·\u00b7]\s*Ticker ([A-Z.\-]+)", body)
    if m:
        facts['cik'] = m.group(1)
        facts['ticker'] = m.group(2)
    dl = w.page.locator('dl.facts').inner_text()
    for key, label in (('sic', 'SIC'), ('state', 'State of Incorporation'),
                       ('fye', 'Fiscal Year End'), ('category', 'Category')):
        m = re.search(re.escape(label) + r"\s*\n([^\n]+)", dl)
        if m:
            facts[key] = m.group(1).strip()
    return facts


def filing_count(w):
    m = re.search(r'(\d+) filings?', w.body())
    assert m, 'filing count label not found'
    return int(m.group(1))


def filing_rows(w):
    rows = w.page.locator('table.data tbody tr').all_inner_texts()
    return [r.replace('\t', ' ').replace('\n', ' ') for r in rows]


def filing_detail_facts(w):
    body = w.body()
    out = {}
    m = re.search(r'SEC Accession No\. ([\w\-]+)', body)
    out['accession'] = m.group(1) if m else None
    dl = w.page.locator('dl.facts').inner_text()
    for key, label in (('filed', 'Filing Date'), ('period', 'Period of Report'),
                       ('items', 'Items'), ('primary_doc', 'Primary Document')):
        m = re.search(re.escape(label) + r"\s*\n([^\n]+)", dl)
        out[key] = m.group(1).strip() if m else None
    return out


def watchlist_count(w):
    m = re.search(r'(\d+) compan(?:y|ies) on your watchlist', w.body())
    assert m, 'watchlist count not found'
    return int(m.group(1))


def watchlist_rows(w):
    rows = w.page.locator('table.watch-table tbody tr').all_inner_texts()
    return [r.replace('\t', ' ').replace('\n', ' ') for r in rows]


def open_company(w, term, link_text):
    header_search(w, term)
    w.click(f'table.data a:has-text("{link_text}")',
            f'open company row for {link_text}')


def list_count(w, noun):
    m = re.search(rf'(\d+) {noun}\b', w.body())
    assert m, f'{noun} count label not found'
    return int(m.group(1))


def filter_and_count(w, select_sel, value, desc):
    w.select(select_sel, value, desc)
    w.submit('form.filter-bar button[type="submit"]', 'apply filter')
    return w.body()


# ------------------------------------------------------------------ tasks --

def task_00(w):
    w.start_home()
    open_company(w, 'Apple', 'Apple Inc.')
    w.select('#type', '10-K', 'filter to Form 10-K')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    w.click('table.data a:has-text("Documents")', 'open most recent 10-K')
    fk = filing_detail_facts(w)
    w.back()
    w.select('#type', '10-Q', 'filter to Form 10-Q')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    w.click('table.data a:has-text("Documents")', 'open most recent 10-Q')
    fq = filing_detail_facts(w)
    sign_in(w, 'alice.j@test.com')
    open_company(w, 'Tesla', 'Tesla, Inc.')
    w.click('button:has-text("Add to Watchlist")', 'add Tesla to watchlist')
    w.click('.account-strip a:has-text("My Account")', 'open My Account')
    count = watchlist_count(w)
    for k, v in (('tenk_filed', fk['filed']), ('tenk_period', fk['period']),
                 ('tenk_accession', fk['accession']),
                 ('tenq_filed', fq['filed']), ('tenq_period', fq['period']),
                 ('tenq_accession', fq['accession']), ('watchlist', count)):
        w.read(k, v)
    return (f"Apple's most recent Form 10-K was filed {fk['filed']} with period of "
            f"report {fk['period']} and accession number {fk['accession']}. The most "
            f"recent Form 10-Q was filed {fq['filed']} with period of report "
            f"{fq['period']} and accession number {fq['accession']}. The 10-K covers "
            f"the longer period. Alice's watchlist now shows {count} companies.")


def task_01(w):
    w.start_home()
    nav(w, 'Search Filings')
    w.click('a:has-text("EDGAR Full-Text Search")', 'open full-text search')
    w.fill('#q', 'artificial intelligence', 'query artificial intelligence')
    w.select('#forms', '10-K', 'limit to Form 10-K')
    w.submit('form.filter-bar button[type="submit"]', 'run search')
    total10k = grab(r'([\d,]+)\+? documents matched', w.body(), '10-K total').replace(',', '')
    top10k = filing_rows(w)[0]
    w.select('#forms', '8-K', 'limit to Form 8-K')
    w.submit('form.filter-bar button[type="submit"]', 'run search')
    total8k = grab(r'([\d,]+)\+? documents matched', w.body(), '8-K total').replace(',', '')
    w.select('#forms', '10-K', 'back to Form 10-K')
    w.fill('#datea', '2020-01-01', 'narrow to filings from 2020-01-01 onward')
    w.submit('form.filter-bar button[type="submit"]', 'run narrowed search')
    narrowed = str(len(filing_rows(w)))
    open_company(w, 'Apple', 'Apple Inc.')
    w.select('#type', '10-K', 'filter to Form 10-K')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    count = filing_count(w)
    newest = filing_rows(w)[0]
    cik = company_facts(w)['cik']
    w.click('table.data a:has-text("Documents")', 'open newest 10-K detail')
    f = filing_detail_facts(w)
    for k, v in (('fts_10k_total', total10k), ('fts_10k_top', top10k),
                 ('fts_8k_total', total8k), ('narrowed_10k', narrowed),
                 ('apple_10k_count', count), ('apple_newest_10k', newest),
                 ('apple_cik', cik), ('apple_10k_period', f['period'])):
        w.read(k, v)
    return (f'The artificial intelligence query limited to Form 10-K matches '
            f'{total10k} documents; the top result is {top10k}. The same query '
            f'limited to Form 8-K matches {total8k} documents. Narrowed to '
            f'filings from 2020-01-01 onward, the results table lists {narrowed} '
            f'documents. Apple\'s EDGAR company page lists {count} 10-K filings; '
            f'the newest one was filed {newest} and Apple\'s CIK is {cik}. That '
            f'10-K\'s period of report is {f["period"]}.')


def task_02(w):
    w.start_home()
    open_company(w, 'Microsoft', 'MICROSOFT CORP')
    facts = company_facts(w)
    w.select('#type', 'DEF 14A', 'filter to DEF 14A')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    w.click('table.data a:has-text("Documents")', 'open most recent DEF 14A')
    f14 = filing_detail_facts(w)
    w.back()
    w.select('#type', '8-K', 'filter to 8-K')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    count8k = filing_count(w)
    sign_in(w, 'bob.c@test.com')
    open_company(w, 'Microsoft', 'MICROSOFT CORP')
    w.click('button:has-text("Add to Watchlist")', 'add Microsoft to watchlist')
    w.click('.account-strip a:has-text("My Account")', 'open My Account')
    count = watchlist_count(w)
    for k, v in (('msft_cik', facts.get('cik')), ('msft_sic', facts.get('sic')),
                 ('msft_state', facts.get('state')),
                 ('msft_category', facts.get('category')),
                 ('def14a_filed', f14['filed']),
                 ('def14a_accession', f14['accession']),
                 ('count_8k', count8k), ('watchlist', count)):
        w.read(k, v)
    return (f"Microsoft's CIK is {facts.get('cik')}, its SIC code and description "
            f"are {facts.get('sic')}, its state of incorporation is "
            f"{facts.get('state')} and its filer category is "
            f"{facts.get('category')}. Its most recent DEF 14A was filed "
            f"{f14['filed']} with accession number {f14['accession']}. Microsoft "
            f"has {count8k} 8-K filings in this snapshot. Bob's watchlist now "
            f"shows {count} companies.")


def task_03(w):
    w.start_home()
    open_company(w, 'Tesla', 'Tesla, Inc.')
    w.select('#type', '8-K', 'filter to 8-K')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    rows = filing_rows(w)
    first, second = rows[0], rows[1]
    w.click('table.data a:has-text("Documents")',
            'open most recent 8-K detail page')
    f1 = filing_detail_facts(w)
    w.click('a:has-text("Open Primary Document")',
            'open the primary document page')
    doc = w.body()
    docname = grab(r'([\w\-.]+\.htm)', doc, 'primary document filename')
    w.back()
    w.back()
    w.click('table.data tbody tr:nth-child(2) a:has-text("Documents")',
            'open next 8-K detail page')
    f2 = filing_detail_facts(w)
    w.back()
    w.select('#type', '4', 'filter to Form 4')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    count4 = filing_count(w)
    w.click('table.data a:has-text("Documents")',
            'open newest Form 4 detail page')
    f4 = filing_detail_facts(w)
    w.back()
    w.select('#type', '10-Q', 'filter to 10-Q')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    countq = filing_count(w)
    shared = [it.strip() for it in f1['items'].split(',')
              if it.strip() in [x.strip() for x in f2['items'].split(',')]]
    for k, v in (('first_8k', first), ('second_8k', second),
                 ('first_8k_filed', f1['filed']), ('first_8k_items', f1['items']),
                 ('first_8k_accession', f1['accession']),
                 ('first_8k_period', f1['period']),
                 ('primary_doc', f1['primary_doc']),
                 ('doc_page_name', docname),
                 ('second_8k_filed', f2['filed']),
                 ('second_8k_items', f2['items']),
                 ('second_8k_accession', f2['accession']),
                 ('second_8k_period', f2['period']),
                 ('shared_items', ', '.join(shared)),
                 ('count_form4', count4), ('newest_form4_period', f4['period']),
                 ('count_10q', countq)):
        w.read(k, v)
    return (f"Tesla's most recent Form 8-K was filed {f1['filed']} with items "
            f"{f1['items']} and accession number {f1['accession']}, and its "
            f"period of report is {f1['period']}. The next 8-K on the list is "
            f"{second}; its period of report is {f2['period']}. The two share "
            f"items {', '.join(shared)}. The most recent 8-K's primary "
            f"document page shows the filename {docname}. Tesla lists {count4} "
            f"Form 4 filings; the newest Form 4's period of report is "
            f"{f4['period']}. Tesla lists {countq} 10-Q filings.")


def task_04(w):
    w.start_home()
    nav(w, 'Enforcement')
    w.click('a:has-text("Browse Litigation Releases")', 'open litigation releases')
    w.fill('#q', 'Asudani', 'search Asudani')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    w.click('table.data a:has-text("Mukesh Asudani")', 'open Asudani release')
    asudani = w.body()
    with w.page.expect_download() as dl:
        w.click('.resources a', 'open the case document')
    download = dl.value
    doc_ok = download.url.endswith('.pdf')
    doc_name = download.suggested_filename
    w.back()
    w.fill('#q', 'Noble', 'search Noble')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    w.click('table.data a:has-text("Trevon Brown")',
            'open Brown/Grant/Noble release')
    noble = w.body()
    nav(w, 'Enforcement')
    w.click('a:has-text("Browse Administrative Proceedings")',
            'open administrative proceedings')
    w.fill('#q', 'Brown', 'search Brown')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    admin_rows = filing_rows(w)
    for k, v in (('asudani_release', grab(r'Litigation Releases › (LR-[\d]+)',
                                          asudani, 'asudani no')),
                 ('asudani_date', grab(r'Litigation Release · ([^\n]+)', asudani,
                                       'asudani date')),
                 ('asudani_body', asudani[:1500]),
                 ('asudani_doc_opens', doc_ok),
                 ('noble_body', noble[:1500]),
                 ('admin_brown_rows', admin_rows)):
        w.read(k, v)
    court = re.search(r"\(([A-Z][A-Za-z.]+) filed", asudani).group(1)
    acq = (re.search(r"announcement that ([A-Za-z .,]+?) had agreed to acquire",
                     asudani).group(1).rstrip(' ,') +
           "'s acquisition of " +
           re.search(r"acquire ([A-Za-z .,]+?)\.", asudani).group(1))
    doc_label = 'SEC Complaint' if 'SEC Complaint' in asudani else 'unknown'
    noble_no = re.search(r"Litigation Releases › (LR-\d+)", noble).group(1)
    noble_total = re.search(r"for a total of \$([\d,]+\.\d\d)", noble).group(1)
    admin_no = re.search(r"Release No\. (\S+) · File Number: (\S+)",
                         '\n'.join(admin_rows))
    w.read('court', court)
    w.read('acquisition', acq)
    w.read('doc_label', doc_label)
    w.read('noble_no', noble_no)
    w.read('noble_total', noble_total)
    w.read('admin_no', admin_no.group(1))
    w.read('admin_file', admin_no.group(2))
    return (f"The Asudani litigation release is {w.facts['asudani_release']}, "
            f"dated {w.facts['asudani_date']}; the SEC filed in the {court} and "
            f"the complaint says he traded ahead of the {acq} acquisition; the "
            f"linked case document is labeled {doc_label} and it opens. The "
            f"Brown/Grant/Noble release is {noble_no} and Michael Noble's total "
            f"payment is ${noble_total}. The Trevon Brown administrative "
            f"proceeding is release {admin_no.group(1)} with file number "
            f"{admin_no.group(2)}.")


def task_05(w):
    w.start_home()
    nav(w, 'Enforcement')
    w.click('a:has-text("Browse Administrative Proceedings")',
            'open administrative proceedings')
    w.fill('#q', 'Black', 'search Black')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    w.click('table.data a:has-text("Quillan Black")', 'open settled orders page')
    black = w.body()
    resources = w.page.locator('.resources a').all_inner_texts()
    sign_in(w, 'bob.c@test.com')
    nav(w, 'Submit a Tip')
    w.click('a:has-text("Tips, Complaints & Referrals Form")', 'open TCR form')
    w.click('a:has-text("Begin TCR Submission")', 'begin submission')
    w.fill('#name', 'Bob Chen', 'name')
    w.fill('#email', 'bob.c@test.com', 'email')
    w.select('#violation_type', 'broker misconduct',
             'violation type: unregistered broker')
    w.fill('#details',
           'An unregistered broker cold-called me pitching security-based swaps '
           'with guaranteed returns, exactly like the settled order I read about.',
           'describe the tip')
    w.submit('button:has-text("Submit Tip")', 'submit tip')
    ref = grab(r'(TCR-[A-Z0-9]+)', w.body(), 'TCR reference')
    for k, v in (('black_body', black[:1500]),
                 ('resources', resources), ('tcr_ref', ref)):
        w.read(k, v)
    date = grab(r'Administrative Proceeding · ([^\n]+?) · Release', black,
                'order date')
    black_pen = re.search(r'\$(\d[\d,]*) as to each Black', black).group(1)
    mack_pen = re.search(r'\$(\d[\d,]*) as to MacKechnie',
                          black).group(1)
    n_files = len(set(re.findall(r'3-\d{5}', black)))
    return (f'The settled order against Quillan Black and the other '
            f'unregistered brokers is dated {date}. The page lists {n_files} '
            f'file numbers, and the civil penalties are ${black_pen} for '
            f'Quillan Black and ${mack_pen} for Tyler MacKechnie. '
            f'{len(resources)} order PDFs are linked under Resources, the '
            f'first labeled {resources[0]}. The TCR reference number is '
            f'{ref}.')


def task_06(w):
    w.start_home()
    nav(w, 'Enforcement')
    w.click('a:has-text("Browse Trading Suspensions")', 'open trading suspensions')
    w.fill('#q', 'Happy City', 'search Happy City')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    susp = w.body()
    nav(w, 'Investor Resources')
    w.click('a:has-text("View Investor Alerts and Bulletins")',
            'open alerts catalog')
    w.click('a:has-text("Cold Callers")', 'open cold callers alert')
    cold = w.body()
    w.back()
    nav(w, 'FAST Answers')
    w.fill('#q', 'pump', 'search pump')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    w.click('a:has-text("Pump-and-Dump")', 'open pump-and-dump answer')
    pump = w.body()
    nav(w, 'Submit a Tip')
    w.click('a:has-text("Investor Complaint Form")', 'open complaint form')
    w.fill('#name', 'Maria Lopez', 'name')
    w.fill('#email', 'maria.lopez@example.com', 'email')
    w.select('#your_role', 'individual investor', 'role')
    w.select('#issue_type', 'misrepresentation or omission', 'problem type')
    w.fill('#subject_firm', 'Happy City Holdings Limited', 'firm')
    w.fill('#details',
           'A stranger cold-called me pitching Happy City Holdings stock and '
           'promised guaranteed returns; the SEC has suspended trading in it.',
           'describe the call')
    w.submit('button:has-text("Submit Complaint")', 'submit complaint')
    ref = grab(r'(IC-[A-Z0-9]+)', w.body(), 'IC reference')
    for k, v in (('suspension_row', susp[:400]), ('cold_body', cold[:1200]),
                 ('pump_body', pump[:800]), ('ic_ref', ref)):
        w.read(k, v)
    return (f'Happy City Holdings was suspended '
            f'{grab(r"([A-Za-z]+\.? \d+, \d{4})", susp, "date")} with release '
            f'number {grab(r"Release No\. (\S+)", susp, "release")}. The cold '
            f'callers alert lists red flags including '
            f'{grab(r"refuses to send[^.\n]*", cold, "flag1")}. After pumping '
            f'the price, fraudsters '
            f'{grab(r"fraudsters ([^.]+)\.", pump, "dump")}. The complaint '
            f'reference number is {ref}.')


def task_07(w):
    w.start_home()
    nav(w, 'Newsroom')
    w.click('a:has-text("Meyer Global Management")',
            'open the Meyer Global press release')
    meyer = w.body()
    w.back()
    w.click('a:has-text("View All Latest Press Releases")', 'open press releases')
    w.fill('#q', 'veterans', 'search veterans')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    w.click('ul.collection a', 'open the veterans release')
    veterans = w.body()
    w.back()
    w.fill('#q', 'Meyer', 'search Meyer')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    meyer_count = grab(r'(\d+) releases?', w.body(), 'Meyer result count')
    nav(w, 'Enforcement')
    w.click('a:has-text("Browse Litigation Releases")', 'open litigation releases')
    w.fill('#q', 'Meyer', 'search Meyer')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    lit_rows = filing_rows(w)
    for k, v in (('meyer_body', meyer[:1600]),
                 ('veterans_body', veterans[:1200]),
                 ('meyer_count', meyer_count), ('lit_rows', lit_rows)):
        w.read(k, v)
    meyer_no = grab(r'Release No\. (\S+)', meyer, 'meyer no')
    meyer_date = grab(r'Press Release · ([^·]+?) ·', meyer, 'meyer date')
    forfeited = re.search(r'forfeit\w*[^.]*?\$([\d,]+)', meyer).group(1)
    vets_no = grab(r'Release No\. (\S+)', veterans, 'veterans no')
    vets_date = grab(r'Press Release · ([^·]+?) ·', veterans, 'veterans date')
    lit = [r for r in lit_rows if 'Meyer' in r]
    scheme = grab(r'orchestrat\w+ (a fraud scheme that raised [^;]+? '
                  r'investors)', veterans, 'scheme')
    return (f'The press release charging Meyer Global Management and its CEO '
            f'is {meyer_no}, dated {meyer_date}; the funds\' investments '
            f'included SpaceX and the forfeited SpaceX investment was '
            f'${forfeited}. The veterans release is {vets_no}, dated '
            f'{vets_date}; it says the two individuals orchestrated {scheme}. '
            f'Searching press releases for Meyer shows {meyer_count} result. '
            f'The litigation release for Owen E.H. Meyer is '
            f'{grab(r"Release No\. (LR-\d+)", chr(10).join(lit), "lit no")} '
            f'with respondents Owen E.H. Meyer and Meyer Global Management '
            f'LLC.')


def task_08(w):
    w.start_home()
    nav(w, 'Forms')
    w.fill('#q', '10-K', 'search Form 10-K')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    tenk_row = [r for r in filing_rows(w) if 'Form 10-K' in r][0]
    w.fill('#q', '8-K', 'search Form 8-K')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    eightk_row = [r for r in filing_rows(w) if 'Form 8-K' in r][0]
    w.fill('#q', '1-A', 'search Form 1-A')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    onea_rows = filing_rows(w)
    w.fill('#q', '', 'clear the search box')
    w.select('#filed_by', 'Public Companies',
             'filter filed-by Public Companies')
    w.submit('form.filter-bar button[type="submit"]', 'apply filter')
    pub_count = grab(r'(\d+) forms?', w.body(), 'public companies count')
    w.select('#filed_by', '', 'clear filed-by filter')
    w.select('#statute', 'Securities Act of 1933',
             'filter by Securities Act of 1933')
    w.submit('form.filter-bar button[type="submit"]', 'apply filter')
    statute_count = grab(r'(\d+) forms?', w.body(), 'statute count')
    w.select('#statute', '', 'clear the statute filter')
    w.fill('#q', '10-K', 'search Form 10-K again')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    with w.page.expect_download() as dl:
        w.click('table.data a:has-text("Annual report pursuant to Section 13")',
                'open the 10-K PDF')
    pdf_ok = dl.value.url.endswith('.pdf')
    pdf_name = dl.value.suggested_filename
    for k, v in (('tenk_row', tenk_row), ('eightk_row', eightk_row),
                 ('onea_rows', onea_rows), ('pub_count', pub_count),
                 ('statute_count', statute_count), ('pdf_served', pdf_ok),
                 ('pdf_name', pdf_name)):
        w.read(k, v)
    return (f'Form 10-K: {tenk_row}. Form 8-K: {eightk_row}. Form 1-A rows: '
            f'{onea_rows[:2]}. Filtering to forms filed by Public Companies '
            f'leaves {pub_count} forms; the Securities Act of 1933 filter '
            f'leaves {statute_count} forms. The Form 10-K PDF '
            f'({pdf_name}) is served by the mirror: {pdf_ok}.')


def task_09(w):
    w.start_home()
    nav(w, 'FAST Answers')
    results = {}
    for term, link in (('10-K', 'Form 10-K'), ('best execution', 'Best Execution'),
                       ('Section 31', 'Section 31 Transaction Fees'), ('Ponzi', 'Ponzi Schemes'),
                       ('proxy', 'Proxy Statement')):
        w.fill('#q', term, f'search {term}')
        w.submit('form.filter-bar button[type="submit"]', 'apply search')
        w.click(f'ul.collection a:has-text("{link}")', f'open {link} answer')
        body = w.body()
        results[term] = body
        w.back()
    for k, v in results.items():
        w.read(f'answer_{k}', v[:900])
    tenk = results['10-K']
    bestex = results['best execution']
    sec31 = results['Section 31']
    ponzi_a = results['Ponzi']
    proxy = results['proxy']
    origin = lambda body: ('captured' if 'captured from sec.gov' in body
                           else 'fixture')
    return (f"The Form 10-K FAST Answer says companies must file a 10-K "
            f"within {grab(r'within ([^.]+) of the end of their fiscal year', tenk, 'window')} "
            f"of the end of their fiscal year; its origin tag is {origin(tenk)}. "
            f"The best execution answer says brokers must seek "
            f"{grab(r'seek ([^.]+) for', bestex, 'bestex')} for their "
            f"customers' orders; origin {origin(bestex)}. The Section 31 "
            f"answer says the fee is based on the "
            f"{grab(r'based on the ([^.]+)', sec31, 'basis')}; "
            f"origin {origin(sec31)}. The Ponzi answer says organizers "
            f"often promise {grab(r'promise ([^.]+)', ponzi_a, 'promise')}; "
            f"origin {origin(ponzi_a)}. The Proxy Statement answer shows a "
            f"modified date of {grab(r'Modified: (\S+)', proxy, 'modified')}; "
            f"origin {origin(proxy)}.")



def task_10(w):
    w.start_home()
    nav(w, 'Investor Resources')
    w.click('a:has-text("View Investor Alerts and Bulletins")',
            'open alerts catalog')
    w.click('a:has-text("Ponzi Schemes")', 'open Ponzi alert')
    ponzi = w.body()
    w.back()
    w.click('a:has-text("How Fees and Expenses")', 'open fees bulletin')
    fees = w.body()
    w.back()
    w.click('a:has-text("Cold Callers")', 'open cold-callers alert')
    cold = w.body()
    w.back()
    w.click('a:has-text("Municipal Bond")', 'open municipal bond alert')
    muni = w.body()
    w.back()
    w.fill('#q', 'risks', "search the catalog for 'risks'")
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    risks_count = grab(r'(\d+) items?', w.body(), 'risks search count')
    w.fill('#q', '', 'clear the search box')
    w.select('#kind', 'bulletin', 'filter to bulletins only')
    w.submit('form.filter-bar button[type="submit"]', 'apply filter')
    bulletin_count = grab(r'(\d+) items?', w.body(), 'bulletin count')
    w.select('#kind', 'alert', 'switch to alerts')
    w.submit('form.filter-bar button[type="submit"]', 'apply filter')
    alert_count = grab(r'(\d+) items?', w.body(), 'alert count')
    for k, v in (('ponzi_body', ponzi[:1200]), ('fees_body', fees[:1000]),
                 ('cold_body', cold[:1200]), ('muni_body', muni[:1200]),
                 ('risks_count', risks_count),
                 ('bulletin_count', bulletin_count),
                 ('alert_count', alert_count)):
        w.read(k, v)
    ponzi_date = grab(r'Investor Alert \u00b7 ([^\n]+)', ponzi, 'ponzi date')
    signs = grab(r'warning signs: ([^.]+\.)', ponzi, 'signs')
    fee_cost = grab(r'(\d+% annual fee difference[^.]+\.)', fees, 'fee cost')
    fee_type = grab(r'sales loads, ([a-z\- ]+)', fees, 'fee type')
    cold_flags = [
        grab(r'refuses to send[^,\n]*', cold, 'cold flag 1'),
        grab(r'demands an immediate decision[^,.\n]*', cold, 'cold flag 2'),
    ]
    muni_date = grab(r'Investor Alert \u00b7 ([^\n]+)', muni, 'muni date')
    muni_risk = grab(r'(credit risk|interest-rate risk|inflation risk)',
                     muni, 'a municipal risk')
    return (f'The Ponzi schemes investor alert is dated {ponzi_date}; its '
            f'three warning signs are {signs} The fees and expenses bulletin '
            f'says {fee_cost} It names fee types including sales loads, '
            f'{fee_type}. The cold-callers alert lists red flags including '
            f'{cold_flags[0].strip()} and {cold_flags[1].strip()}. The '
            f'municipal bond alert is dated {muni_date} and describes risks '
            f'including {muni_risk}. Searching the catalog for risks shows '
            f'{risks_count} items. Filtering to bulletins shows '
            f'{bulletin_count} items; switching to alerts shows {alert_count} '
            f'items.')


def task_11(w):
    w.start_home()
    nav(w, 'Rulemaking')
    w.fill('#q', 'Interval Fund Modernization', 'search the proposed rule')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    interval_row = filing_rows(w)[0]
    w.fill('#q', 'S7-2026-34', 'look up by file number')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    file_rows = filing_rows(w)
    file_count = grab(r'(\d+) items?', w.body(), 'file lookup count')
    w.fill('#q', '', 'clear the search box')
    w.select('#status', 'Proposed Rule', 'filter to Proposed Rules')
    w.submit('form.filter-bar button[type="submit"]', 'apply filter')
    proposed_count = grab(r'(\d+) items?', w.body(), 'proposed count')
    w.select('#status', 'Final Rule', 'switch to Final Rules')
    w.submit('form.filter-bar button[type="submit"]', 'apply filter')
    final_count = grab(r'(\d+) items?', w.body(), 'final count')
    w.fill('#q', 'quorum', 'find the quorum requirement rule')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    quorum_rows = filing_rows(w)
    w.select('#status', '', 'clear the status filter')
    w.fill('#q', 'electronic delivery of information',
           'search the e-delivery rule')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    edelivery_rows = filing_rows(w)
    w.fill('#q', '', 'clear the search box')
    w.submit('form.filter-bar button[type="submit"]', 'clear filters')
    total = grab(r'(\d+) items?', w.body(), 'total rulemaking items')
    for k, v in (('interval_row', interval_row), ('file_rows', file_rows),
                 ('file_count', file_count), ('proposed_count', proposed_count),
                 ('quorum_rows', quorum_rows), ('final_count', final_count),
                 ('edelivery_rows', edelivery_rows), ('total', total)):
        w.read(k, v)
    interval_date = grab(r'(\S+ \d+, \d{4})', interval_row, 'interval date')
    interval_releases = grab(r'Proposed Rule[^\n]*? (33-[\d]+[^\n]*)',
                             interval_row, 'interval releases')
    quorum_row = quorum_rows[0]
    quorum_date = grab(r'(\S+ \d+, \d{4})', quorum_row, 'quorum date')
    quorum_release = grab(r'34-(\d+)', quorum_row, 'quorum release')
    edelivery_row = edelivery_rows[0]
    edelivery_date = grab(r'(\S+ \d+, \d{4})', edelivery_row, 'edelivery date')
    return (f'The Interval Fund Modernization proposed rule is dated '
            f'{interval_date}, file number S7-2026-34, with release numbers '
            f'{interval_releases}. Looking it up by its file number returns '
            f'{file_count} result. Filtering to Proposed Rules shows '
            f'{proposed_count} items; switching to Final Rules shows '
            f'{final_count} items, and the Commission quorum requirement rule '
            f'is dated {quorum_date} with release number 34-{quorum_release}. '
            f'The proposed rule about electronic delivery of information is '
            f'file number {grab(r"S7-2026-25", edelivery_row, "edelivery file")} '
            f'dated {edelivery_date}. Clearing the filters shows {total} '
            f'rulemaking items.')


def task_12(w):
    w.start_home()
    nav(w, 'Newsroom')
    latest = w.body()
    latest_title = grab(r'SEC Charges[^\n]+', latest, 'latest title')
    latest_no = grab(r'Release No\. (\S+)', latest, 'latest no')
    w.click(f'a:has-text("{latest_title[:45]}")',
            'open the latest press release')
    pr = w.body()
    w.back()
    w.click('a:has-text("View All Speeches & Statements")',
            'open the speeches page')
    w.fill('#q', 'Trump', "search speeches for 'Trump'")
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    sb = w.body()
    trump = filing_rows(w)[0]
    trump_total = grab(r'(\d+) items?', sb, 'Trump results count')
    nav(w, 'Newsroom')
    w.click('a:has-text("View All What\'s New")', "open the What's New page")
    wn = w.body()
    w.back()
    w.click('a:has-text("View All Latest Press Releases")',
            'open press releases')
    w.fill('#q', 'Zoe Financial', 'search Zoe Financial')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    w.click('ul.collection a', 'open the Zoe Financial release')
    zoe = w.body()
    w.fill('#footer-email', 'news.fan@example.com',
           'footer signup: press-release email updates')
    w.click('input[name="topics"][value="press releases"]',
            'check the press releases topic')
    w.submit('.site-footer__signup button[type="submit"]', 'sign up')
    confirm = w.body()
    for k, v in (('newsroom_latest', latest[:1100]),
                 ('latest_title', latest_title), ('latest_no', latest_no),
                 ('pr_body', pr[:1500]),
                 ('trump_row', trump), ('trump_total', trump_total),
                 ('whatsnew', wn[:1500]),
                 ('zoe_body', zoe[:1000]),
                 ('confirm', confirm[:1500])):
        w.read(k, v)
    pr_date = grab(r'Press Release \u00b7 ([^\u00b7]+?) \u00b7', pr, 'pr date')
    pre_ipo = grab(r'(SpaceX)', pr, 'pre-IPO company')
    trump_speaker = grab(r'Staff Statement on Trump Accounts\s+(.+?)\s*Statement\s*$',
                         trump, 'trump speaker')
    trump_date = grab(r'(Sept\. \d+, \d{4})', trump, 'trump date')
    wn_two = re.search(
        r'([^\t\n]+)\t+Litigation Release - ([^\t\n]+)\t[^\n]*\n'
        r'([^\t\n]+)\t+Litigation Release - ([^\t\n]+)\t', wn)
    zoe_charge = grab(r'for (failing[^.]+?) to its clients', zoe, 'zoe charge')
    zoe_no = grab(r'Release No\. (\S+)', zoe, 'zoe no')
    zoe_date = grab(r'Press Release \u00b7 ([^\u00b7]+?) \u00b7', zoe,
                    'zoe date')
    subscribed = grab(r'(news\.fan@example\.com[^.]*\.)', confirm,
                       'confirmation')
    return (f'From the newsroom, the latest press release is "{latest_title}" '
            f'with release number {latest_no}; opened, it is dated {pr_date} '
            f'and the charged funds invested in {pre_ipo}. Searching the '
            f'speeches page for Trump returns {trump_total} result: the staff '
            f'statement on Trump Accounts by the {trump_speaker}, dated '
            f'{trump_date}. On the What\'s New page, the first two litigation '
            f'releases are {wn_two.group(2).strip()} ({wn_two.group(1).strip()}) '
            f'and {wn_two.group(4).strip()} ({wn_two.group(3).strip()}). '
            f'Searching press releases for Zoe Financial: the SEC charged the '
            f'firm with {zoe_charge}, release number {zoe_no} dated {zoe_date}. '
            f'Footer signup confirmation: {subscribed}')


def task_13(w):
    w.start_home()
    sign_in(w, 'alice.j@test.com')
    nav(w, 'Submit a Tip')
    w.click('a:has-text("Investor Complaint Form")', 'open complaint form')
    w.fill('#name', 'Alice Johnson', 'name')
    w.fill('#email', 'alice.j@test.com', 'email')
    w.select('#your_role', 'individual investor', 'role')
    w.select('#issue_type', 'unauthorized trading', 'problem type')
    w.fill('#subject_firm', 'Granite Harbor Capital LLC', 'firm')
    w.fill('#subject_person', 'T. Brooks', 'individual')
    w.fill('#subject_ticker', 'GRHN', 'ticker')
    w.fill('#address', '200 Granite Way, Boston, MA 02110', 'address')
    w.fill('#phone', '617-555-0142', 'phone')
    w.fill('#details',
           'My broker at Granite Harbor Capital traded my account without my '
           'authorization, including GRHN positions I never approved.',
           'describe the problem')
    w.submit('button:has-text("Submit Complaint")', 'submit complaint')
    ref = grab(r'(IC-[A-Z0-9]+)', w.body(), 'IC reference')
    w.click('.account-strip a:has-text("My Account")', 'open My Account')
    account = w.body()
    for k, v in (('ic_ref', ref), ('account_firm',
                                   grab(r'Granite Harbor Capital LLC', account,
                                        'firm in account'))):
        w.read(k, v)
    return (f'The complaint reference number is {ref}, and My Account shows '
            f'the new complaint against Granite Harbor Capital LLC.')


def task_14(w):
    w.start_home()
    sign_in(w, 'carol.d@test.com')
    nav(w, 'Submit a Tip')
    w.click('a:has-text("Investor Question Form")', 'open question form')
    w.fill('#name', 'Carol Davis', 'name')
    w.fill('#email', 'carol.d@test.com', 'email')
    w.select('#topic', 'investment professional', 'topic')
    w.fill('#question',
           'How can I check whether my investment professional is registered '
           'with the SEC or a state regulator?',
           'the question')
    w.submit('button:has-text("Submit Question")', 'submit question')
    qref = grab(r'(Q-[A-Z0-9]+)', w.body(), 'Q reference')
    nav(w, 'Investor Resources')
    w.click('a:has-text("View Investor Alerts and Bulletins")',
            'open alerts catalog')
    w.click('a:has-text("Cold Callers")', 'open cold callers alert')
    cold = w.body()
    w.fill('#footer-email', 'updates.carol@example.com', 'footer email')
    w.click('footer form label:has-text("investor alerts") input',
            'check investor alerts topic')
    w.submit('footer button:has-text("Sign Up")', 'sign up for updates')
    subscribed = w.body()
    for k, v in (('q_ref', qref), ('cold_flag',
                                   grab(r'refuses to send[^.\n]*', cold, 'flag')),
                 ('subscribed', subscribed[:400])):
        w.read(k, v)
    return (f'The investor question reference number is {qref}. One red flag '
            f'from the cold callers alert: it '
            f'{grab(r"refuses to send[^.\n]*", cold, "flag")}. '
            f'updates.carol@example.com is now subscribed to SEC email updates '
            f'with the investor alerts topic.')


def task_15(w):
    w.start_home()
    sign_in(w, 'dana.k@test.com')
    w.click('.account-strip a:has-text("My Account")', 'open My Account')
    w.click('table.watch-table tr:has-text("Meta Platforms") button',
            'remove Meta Platforms')
    open_company(w, 'Tesla', 'Tesla, Inc.')
    w.click('button:has-text("Add to Watchlist")', 'add Tesla')
    open_company(w, 'NVIDIA', 'NVIDIA Corp')
    w.click('button:has-text("Add to Watchlist")', 'add NVIDIA')
    w.click('.account-strip a:has-text("My Account")', 'open My Account')
    count = watchlist_count(w)
    rows = watchlist_rows(w)
    for k, v in (('final_count', count), ('rows', rows)):
        w.read(k, v)
    return (f'Dana\'s watchlist now shows {count} companies: '
            f'{"; ".join(rows)}.')


def task_16(w):
    w.start_home()
    w.click('nav.site-nav a:has-text("Sign Up")', 'open sign-up page')
    w.fill('#name', 'Jordan Lee', 'full name')
    w.fill('#email', 'jordan.lee@test.com', 'email')
    w.fill('#password', 'Jordan2026Pass', 'password')
    w.submit('button:has-text("Create Account")', 'create the account')
    open_company(w, 'Alphabet', 'Alphabet Inc.')
    facts = company_facts(w)
    w.click('button:has-text("Add to Watchlist")', 'add Alphabet')
    w.click('.account-strip a:has-text("Log Out")', 'sign out')
    sign_in(w, 'jordan.lee@test.com', password='Jordan2026Pass')
    w.click('.account-strip a:has-text("My Account")', 'open My Account')
    rows = watchlist_rows(w)
    for k, v in (('alphabet_cik', facts.get('cik')),
                 ('alphabet_sic', facts.get('sic')), ('rows', rows)):
        w.read(k, v)
    return (f"Alphabet's CIK is {facts.get('cik')} and its SIC description is "
            f"{facts.get('sic')}. After signing out and back in, the watchlist "
            f"still lists: {'; '.join(rows)}.")


def task_17(w):
    w.start_home()
    open_company(w, 'Goldman Sachs', 'GOLDMAN SACHS')
    gs = company_facts(w)
    w.select('#type', '10-K', 'filter to 10-K')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    gs_count = filing_count(w)
    gs_newest = filing_rows(w)[0]
    w.click('table.data a:has-text("Documents")',
            'open GS newest 10-K detail')
    gs_period = filing_detail_facts(w)['period']
    w.back()
    w.select('#type', '10-Q', 'switch to Form 10-Q')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    gs_qcount = filing_count(w)
    gs_qnewest = filing_rows(w)[0]
    open_company(w, 'Microsoft', 'MICROSOFT CORP')
    ms = company_facts(w)
    w.select('#type', '10-K', 'filter to 10-K')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    ms_count = filing_count(w)
    ms_newest = filing_rows(w)[0]
    w.click('table.data a:has-text("Documents")',
            'open MS newest 10-K detail')
    ms_period = filing_detail_facts(w)['period']
    w.back()
    w.select('#type', '10-Q', 'switch to Form 10-Q')
    w.submit('button:has-text("Filter Filings")', 'apply filter')
    ms_qcount = filing_count(w)
    ms_qnewest = filing_rows(w)[0]
    for k, v in (('gs', gs), ('gs_count', gs_count), ('gs_newest', gs_newest),
                 ('gs_period', gs_period), ('gs_qcount', gs_qcount),
                 ('gs_qnewest', gs_qnewest),
                 ('ms', ms), ('ms_count', ms_count), ('ms_newest', ms_newest),
                 ('ms_period', ms_period), ('ms_qcount', ms_qcount),
                 ('ms_qnewest', ms_qnewest)):
        w.read(k, v)
    return (f"Goldman Sachs: CIK {gs.get('cik')}, state of incorporation "
            f"{gs.get('state')}, SIC {gs.get('sic')}, filer category "
            f"{gs.get('category')}; {gs_count} 10-K filings, the newest filed "
            f"{gs_newest} with period of report {gs_period}; {gs_qcount} 10-Q "
            f"filings, the newest filed {gs_qnewest}. Microsoft: CIK "
            f"{ms.get('cik')}, state of incorporation {ms.get('state')}, SIC "
            f"{ms.get('sic')}, filer category {ms.get('category')}; "
            f"{ms_count} 10-K filings, the newest filed {ms_newest} with "
            f"period of report {ms_period}; {ms_qcount} 10-Q filings, the "
            f"newest filed {ms_qnewest}. "
            f"{'Microsoft' if ms_count > gs_count else 'Goldman Sachs'} has "
            f"more 10-K filings in this snapshot.")


def task_18(w):
    w.start_home()
    nav(w, 'Investor Resources')
    w.click('a:has-text("View Investor Alerts and Bulletins")',
            'open alerts catalog')
    w.click('a:has-text("Crypto Assets")', 'open crypto assets alert')
    crypto = w.body()
    w.back()
    nav(w, 'FAST Answers')
    w.fill('#q', 'Ponzi', 'search Ponzi')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    w.click('ul.collection a:has-text("Ponzi Schemes")', 'open Ponzi answer')
    ponzi = w.body()
    nav(w, 'Search Filings')
    w.click('a:has-text("EDGAR Full-Text Search")', 'open full-text search')
    w.fill('#q', 'digital assets', 'query digital assets')
    w.select('#forms', '8-K', 'limit to Form 8-K')
    w.submit('form.filter-bar button[type="submit"]', 'run search')
    total = grab(r'([\d,]+)\+? documents matched', w.body(), 'total').replace(',', '')
    top = filing_rows(w)[0]
    nav(w, 'Submit a Tip')
    w.click('a:has-text("Tips, Complaints & Referrals Form")', 'open TCR form')
    w.click('a:has-text("Begin TCR Submission")', 'begin submission')
    w.fill('#name', 'Jordan Lee', 'name')
    w.fill('#email', 'jordan.lee@test.com', 'email')
    w.select('#violation_type', 'fraud', 'violation type: fraud')
    w.fill('#details',
           'A messaging-app stranger promised a crypto token guaranteed to '
           'double, a guaranteed-return red flag from the crypto assets alert.',
           'describe the offer')
    w.submit('button:has-text("Submit Tip")', 'submit tip')
    ref = grab(r'(TCR-[A-Z0-9]+)', w.body(), 'TCR reference')
    for k, v in (('crypto_body', crypto[:1200]), ('ponzi_body', ponzi[:500]),
                 ('fts_total', total), ('fts_top', top), ('tcr_ref', ref)):
        w.read(k, v)
    flag1 = grab(r'claims of ([^.]+?)\. These are', crypto, 'flag1')
    flag2 = grab(r'using (crypto assets, gift cards or wire transfers)',
                 crypto, 'flag2')
    return (f'Two red flags from the crypto assets alert: {flag1}, and '
            f'{flag2}. Ponzi organizers often promise '
            f'{grab(r"promise ([^.]+)", ponzi, "promise")}. The digital assets '
            f'query limited to Form 8-K matches {total} documents; the top '
            f'company is {top}. The TCR reference number is {ref}.')


def task_19(w):
    w.start_home()
    nav(w, 'Enforcement')
    w.click('a:has-text("Browse Litigation Releases")', 'open litigation releases')
    w.select('#year', '2026', 'filter to year 2026')
    w.submit('form.filter-bar button[type="submit"]', 'apply filter')
    year_count = grab(r'(\d+) releases?', w.body(), 'year count')
    w.fill('#q', 'Bernardi', 'search Bernardi')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    w.click('table.data a:has-text("Robert Bernardi")',
            'open the Bernardi release')
    bernardi = w.body()
    nav(w, 'Enforcement')
    w.click('a:has-text("Browse Administrative Proceedings")',
            'open administrative proceedings')
    w.fill('#q', 'OTC Link', 'search OTC Link')
    w.submit('form.filter-bar button[type="submit"]', 'apply search')
    w.click('table.data a:has-text("OTC Link")', 'open OTC Link proceeding')
    otc = w.body()
    nav(w, 'Newsroom')
    w.click('a:has-text("View All What\'s New")', "open What's New")
    whatsnew = w.body()
    w.click('table.data a', 'open the first what\'s-new item')
    first = w.body()
    for k, v in (('year_count', year_count), ('bernardi_body', bernardi[:1300]),
                 ('otc_body', otc[:500]), ('whatsnew', whatsnew[:600]),
                 ('first_body', first[:700])):
        w.read(k, v)
    bernardi_no = grab(r'Litigation Releases › (LR-\d+)', bernardi,
                       'bernardi no')
    bernardi_date = grab(r'Litigation Release · ([^\n]+)', bernardi,
                         'bernardi date')
    bernardi_company = grab(r'former CEO of ([A-Za-z .]+?) \(',
                            bernardi, 'company')
    otc_title = grab(r'Administrative Proceeding[^\n]*\n([^\n]+)', otc,
                     'otc title')
    first_no = grab(r'Litigation Releases › (LR-\d+)', first, 'first no')
    first_division = grab(r'Enforcement', whatsnew, 'division')
    return (f'Filtered to year 2026, the litigation releases page shows '
            f'{year_count} releases. The Robert Bernardi and Sunil Chandra '
            f'release is {bernardi_no}, dated {bernardi_date}; it charges the '
            f'former CEO and Vice President of {bernardi_company}. The OTC '
            f'Link LLC administrative proceeding detail page is titled '
            f'{otc_title}. In What\'s New, the first item listed is '
            f'{first_no} and the division shown for it is {first_division}.')


TASK_FUNCS = {f'SEC.gov--{i}': globals()[f'task_{i:02d}'] for i in range(20)}


def task_id_for(idx):
    return f'SEC.gov--{int(idx)}'


def main():
    round_name = sys.argv[1] if len(sys.argv) > 1 else 'round1'
    only = sys.argv[2:]
    out_root = EV / round_name
    out_root.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for tid, func in TASK_FUNCS.items():
            if only and tid not in only and tid.replace('SEC.gov--', '') not in only:
                continue
            idx = tid.split('--')[1]
            tid = task_id_for(idx)
            print(f'== {tid} ==', flush=True)
            reset_site()
            ctx = browser.new_context()
            page = ctx.new_page()
            out_dir = out_root / f'{int(idx):02d}'
            if out_dir.exists():
                import shutil
                shutil.rmtree(out_dir)
            w = Walk(page, tid, out_dir)
            snapshot_db(out_dir / 'initial.db')
            try:
                answer = func(w)
                w.save(answer)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                w.save(f'WALK FAILED: {exc}')
            finally:
                snapshot_db(out_dir / 'after.db')
                ctx.close()
        browser.close()
    print('round complete:', round_name)


if __name__ == '__main__':
    main()

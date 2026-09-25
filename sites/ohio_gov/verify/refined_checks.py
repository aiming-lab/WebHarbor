"""Current coherent task checks; source facts remain outside agent-facing tasks."""
import re
from verify_lib import *

def fact(judge, answer, name, *patterns):
    text = normalize_text(answer)
    ok = all(re.search(pattern, text, re.I) for pattern in patterns)
    if re.search(r'heap[^.;]{0,140}(?:not|never)[^.;]{0,50}(?:utility|fuel)', text, re.I):
        ok = False
    # Reject direct negations of requested claims; ordinary exclusions elsewhere are allowed.
    for pattern in patterns:
        if re.search(r'(?:not|never|no)\s+(?:a\s+|the\s+)?(?:' + pattern + ')', text, re.I):
            ok = False
    judge.check(name, ok, 'required facts and relationships')

def paths(judge, traj, *values):
    for value in values:
        check_visited_path(judge, traj, 'visited_' + value, value)


def run_checks(judge, traj, initial_db, after_db):
    i = int(judge.task_id.rsplit('--', 1)[1]); answer = final_answer(traj)
    check_trajectory_identity(judge, traj, judge.task_id)
    if i == 2:
        paths(judge, traj, '/residents/resources/home-energy-assistance-program', '/residents/resources/home-weatherization-assistance-program', '/residents/resources/percentage-of-income-payment-plan')
        fact(judge, answer, 'heap_destination', r'heap[^.;]{0,180}(?:utility|fuel).{0,30}(?:company|provider)')
        fact(judge, answer, 'weatherization_work', r'inspect', r'improv', r'energy.efficient', r'local agenc')
        fact(judge, answer, 'eligibility', r'income', r'60|older', r'child', r'disabil', r'energy use', r'(?:other|assistance) program')
        fact(judge, answer, 'pipp_payments', r'(?:pipp|percentage of income)', r'(?:based on|depend.{0,5}on|determined by).{0,25}household income')
    elif i == 4:
        check_signed_in_as(judge, traj, 'alice.j@test.com')
        paths(judge, traj, '/residents/resources/dolly-partons-imagination-library-of-ohio', '/news-and-events/all-news/gov.dolly-parton-day-sept26', '/account')
        fact(judge, answer, 'book_program', r'imagination library', r'(?:under|younger than) (?:age )?(?:5|five)', r'(?:one|1|a) free book', r'month')
        fact(judge, answer, 'proclamation', r'(?:september|sept\.?) 25', r'dewine')
        judge.check('library_saved', 'dolly-partons-imagination-library-of-ohio' in saved_slugs(after_db, 1), 'Alice saved library; no duplicate')
    elif i == 6:
        check_signed_in_as(judge, traj, 'alice.j@test.com')
        paths(judge, traj, '/residents/resources/weather-safety', '/residents/resources/home-weatherization-assistance-program', '/account')
        expected = saved_slugs(initial_db, 1) + ['weather-safety', 'home-weatherization-assistance-program']
        actual = saved_slugs(after_db, 1)
        judge.check('exact_saved_set', sorted(actual) == sorted(expected), str(actual))
        fact(judge, answer, 'saved_confirmations', r'weather safety', r'home weatherization assistance', r'(?:7|seven) saved')
    elif i == 13:
        paths(judge, traj, '/residents/resources/unclaimed-funds', '/business/resources/unclaimed-funds-reporting')
        fact(judge, answer, 'claiming_department', r'department of commerce', r'claim')
        fact(judge, answer, 'examples', r'(?:old )?bank accounts', r'uncashed checks')
        fact(judge, answer, 'reporting_duty', r'(?:compan|business)', r'(?:doing business|operat).{0,30}(?:ohio|state)', r'(?:must|required|requires|duty).{0,90}report')
        paths(judge, traj, '/help-center/state-directory')
        fact(judge, answer, 'commerce_contact', r'contact list and form')
    elif i == 16:
        paths(judge, traj, '/news-and-events/all-news/odnr-fall-hunting-seasons-start-aug26', '/help-center/faqs/hunting-and-fishing')
        fact(judge, answer, 'opening_seasons', r'squirrel', r'dove', r'sept(?:ember|\.)? (?:1|first)')
        fact(judge, answer, 'regulations', r'regulations', r'season dates', r'daily limits')
        fact(judge, answer, 'publication', r'august 26,? 2026|2026-08-26')
        fact(judge, answer, 'licenses_and_dates', r'online', r'(?:agent|retailer)', r'division of wildlife')
    elif i == 17:
        paths(judge, traj, '/news-and-events/all-news/bmv-ohio-mobile-id-in-google-wallet-aug26', '/residents/resources/driver-licenses')
        fact(judge, answer, 'wallet_announcement', r'bureau of motor vehicles', r'august 31,? 2026|2026-08-31')
        fact(judge, answer, 'privacy', r'(?:review|see|check).{0,60}(?:data|information).{0,30}(?:shared|sharing)')
        fact(judge, answer, 'real_id_conditions', r'(?:proper|required|appropriate) documents', r'real id', r'(?:air travel|flight)', r'federal facilit')
        paths(judge, traj, '/help-center/state-directory')
        fact(judge, answer, 'bmv_contact', r'contact list and chat')
    elif i == 19:
        paths(judge, traj, '/jobs/resources/licenses-and-permits', '/help-center/state-directory', '/help-center/faqs/professional-licenses')
        fact(judge, answer, 'barber_authority', r'cosmetology and barber board', r'cos\.ohio\.gov', r'contact form', r'elicense')
    if i != 6:
        check_read_only(judge, initial_db, after_db)

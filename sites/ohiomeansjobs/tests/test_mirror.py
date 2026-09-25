"""Self-check suite for the ohiomeansjobs mirror.

Run from sites/ohiomeansjobs/:  python3 -m pytest tests/ -q

The suite runs against a temporary copy of the seeded database (pointed to
via OMJ_DB_URI before importing the app) so it never mutates the seed.
"""
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SITE = HERE.parent
sys.path.insert(0, str(SITE))

SEED = SITE / 'instance_seed' / 'ohiomeansjobs.db'
if not SEED.exists():
    # Bootstrap the deterministic seed from the frozen catalog (same entry
    # point the image build uses) so the suite is runnable in any checkout.
    # Run in a subprocess so this process never imports app with the
    # builder's OMJ_DB_URI.
    import subprocess
    subprocess.run([sys.executable, 'seed_data.py'], cwd=str(SITE), check=True)

TMP = tempfile.mkdtemp(prefix='omj-tests-')
DB_PATH = os.path.join(TMP, 'ohiomeansjobs.db')
shutil.copyfile(SEED, DB_PATH)
os.environ['OMJ_DB_URI'] = f'sqlite:///{DB_PATH}'

from app import app, db, Job, User, SavedJob, Application, SavedSearch  # noqa: E402
from seed_data import seed_database, seed_benchmark_users  # noqa: E402

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False
client = app.test_client()          # default client for read-only tests


def fresh_client():
    """A brand-new client with a clean session (auth tests)."""
    return app.test_client()


def get(path, **kw):
    return client.get(path, **kw)


def post(path, **kw):
    return client.post(path, **kw)


# ------------------------------------------------------------------ health

def test_health():
    r = get('/_health')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert data['site'] == 'ohiomeansjobs'
    assert data['jobs'] >= 150


# ------------------------------------------------------------- static pages

def test_portal_routes_render():
    for path in ['/', '/job-seekers', '/job-seekers/find-a-job',
                 '/job-seekers/build-your-career', '/job-seekers/practice-your-skills',
                 '/job-seekers/learn-about-benefits',
                 '/job-seekers/find-a-job/local-help',
                 '/job-seekers/find-a-job/state-jobs',
                 '/job-seekers/find-a-job/career-profile-quiz',
                 '/career-quiz/start', '/for-employers',
                 '/for-employers/resources-for-employers', '/for-students',
                 '/news-and-events', '/news-and-events/events', '/help-center',
                 '/contact-us', '/account/login', '/account/register']:
        assert get(path).status_code == 200, path


def test_home_shows_real_stats_and_recent_jobs():
    body = get('/').get_data(as_text=True)
    assert 'Find Your Next Opportunity' in body
    assert 'Total Jobs Available' in body
    assert 'As of September 21, 2026' in body
    assert '/jobs/view/' in body  # recent jobs list


def test_all_images_resolve():
    import re
    body = get('/').get_data(as_text=True)
    srcs = set(re.findall(r'src="(/static/images/[^"]+)"', body)) | \
        set(re.findall(r"url\('(/static/images/[^']+)'\)", body))
    assert len(srcs) >= 5
    for src in srcs:
        assert get(src).status_code == 200, src


# ------------------------------------------------------------- job search

def test_search_by_title_returns_results():
    r = get('/jobs/search?tjt=nurse')
    assert r.status_code == 200
    assert 'jobs found' in r.get_data(as_text=True)


def test_search_location_radius_filter():
    r = get('/jobs/search?tjt=nurse&cnme=Columbus&rad=20')
    body = r.get_data(as_text=True)
    # Columbus radius 20 excludes Findlay/Cincinnati postings
    assert 'Findlay, OH' not in body


def test_salary_facet_narrows_results():
    r = get('/jobs/search?tjt=nurse&saltyp=5')
    body = r.get_data(as_text=True)
    assert 'CICU Nurse Practitioner' in body
    assert 'Nurse Aide' not in body


def test_facets_render_with_counts():
    body = get('/jobs/search?tjt=welder').get_data(as_text=True)
    assert 'Industry' in body and 'Salary' in body and 'Job Type' in body
    assert 'Refine' in body


def test_pagination():
    r1 = get('/jobs/search?tjt=warehouse&sort=date&pg=1')
    r2 = get('/jobs/search?tjt=warehouse&sort=date&pg=2')
    b1 = r1.get_data(as_text=True)
    b2 = r2.get_data(as_text=True)
    assert 'pg=2' in b1  # next-page link exists
    assert b1 != b2


def test_search_no_results_message():
    body = get('/jobs/search?tjt=zzzqqqxyz').get_data(as_text=True)
    assert 'did not match any results' in body


def test_scored_search_partial_query():
    # token overlap, not strict AND — 'Boston Celtic' style partial match
    body = get('/jobs/search?tjt=software%20develop').get_data(as_text=True)
    assert 'jobs found' in body


# ------------------------------------------------------------- job detail

def test_job_detail_shows_summary():
    with app.app_context():
        job = Job.query.filter_by(jobid='6931551303').first()
        assert job is not None
    body = get(f'/jobs/view/{job.jobid}').get_data(as_text=True)
    assert job.title in body
    assert 'Job Summary' in body
    assert 'Job Reference Code' in body
    assert 'About the Job' in body
    assert 'Save to My Profile' in body


def test_job_detail_404_for_unknown():
    assert get('/jobs/view/0000000000').status_code == 404


def test_company_profile_lists_all_postings():
    body = get('/jobs/company/blanchard-valley-regional-health-center').get_data(as_text=True)
    assert 'Blanchard Valley Regional Health Center' in body
    assert '8 active job postings' in body


# ------------------------------------------------------------------- auth

def login(email, password, _client=None):
    c = _client or fresh_client()
    c.post('/account/login', data={'email': email, 'password': password},
           follow_redirects=True)
    return c


def test_benchmark_users_exist():
    with app.app_context():
        for email in ['alice.j@test.com', 'bob.c@test.com',
                      'carol.d@test.com', 'david.k@test.com']:
            user = User.query.filter_by(email=email).first()
            assert user is not None, email
            assert user.check_password('TestPass123!')


def test_login_success_and_dashboard():
    c = login('alice.j@test.com', 'TestPass123!')
    r = c.get('/account/profile')
    assert r.status_code == 200
    assert 'Dashboard' in r.get_data(as_text=True)


def test_login_bad_password():
    c = fresh_client()
    r = c.post('/account/login', data={'email': 'alice.j@test.com', 'password': 'nope'},
               follow_redirects=True)
    assert 'Invalid email or password' in r.get_data(as_text=True)


def test_register_validation():
    c = fresh_client()
    r = c.post('/account/register', data={'email': 'bad', 'password': 'short',
                                          'confirm': 'short'}, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert 'Enter a valid email address' in body
    assert 'at least 8 characters' in body


def test_register_creates_account():
    c = fresh_client()
    r = c.post('/account/register', data={'email': 'new.user@test.com',
                                          'password': 'NewUser123!', 'confirm': 'NewUser123!',
                                          'first_name': 'New', 'last_name': 'User'},
               follow_redirects=True)
    assert 'Dashboard' in r.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(email='new.user@test.com').first() is not None


def test_account_guard():
    r = get('/account/profile', follow_redirects=True)
    assert 'Log In' in r.get_data(as_text=True) or 'Please sign in' in r.get_data(as_text=True)


# ------------------------------------------------------- saved jobs / apply

def test_save_and_unsave_job():
    c = login('alice.j@test.com', 'TestPass123!')
    with app.app_context():
        alice = User.query.filter_by(email='alice.j@test.com').first()
        before = SavedJob.query.filter_by(user_id=alice.id).count()
        job = Job.query.filter(Job.id.notin_([s.job_id for s in
                                              SavedJob.query.filter_by(user_id=alice.id)])).first()
    r = c.post(f'/jobs/save/{job.jobid}', follow_redirects=True)
    assert 'saved' in r.get_data(as_text=True)
    with app.app_context():
        assert SavedJob.query.filter_by(user_id=alice.id).count() == before + 1
    c.post(f'/jobs/save/{job.jobid}', follow_redirects=True)
    with app.app_context():
        assert SavedJob.query.filter_by(user_id=alice.id).count() == before


def test_apply_flow_records_application():
    c = login('bob.c@test.com', 'TestPass123!')
    with app.app_context():
        bob = User.query.filter_by(email='bob.c@test.com').first()
        applied_ids = {a.job_id for a in Application.query.filter_by(user_id=bob.id)}
        job = Job.query.filter(Job.id.notin_(applied_ids)).first()
    r = c.post(f'/jobs/apply/{job.jobid}', data={'first_name': 'Bob', 'last_name': 'Chen',
                                                'email': 'bob.c@test.com', 'phone': '216-555-0177'},
               follow_redirects=True)
    assert 'Application submitted' in r.get_data(as_text=True)
    with app.app_context():
        assert Application.query.filter_by(user_id=bob.id, job_id=job.id).first() is not None
    # double-apply is blocked
    r = c.get(f'/jobs/apply/{job.jobid}', follow_redirects=True)
    assert 'already applied' in r.get_data(as_text=True)


def test_saved_searches_management():
    c = login('carol.d@test.com', 'TestPass123!')
    with app.app_context():
        carol = User.query.filter_by(email='carol.d@test.com').first()
        before = SavedSearch.query.filter_by(user_id=carol.id).count()
    r = c.post('/account/saved-searches', data={'name': 'Test search',
                                                'params': '{"tjt": "nurse"}',
                                                'frequency': 'Weekly', 'alerts': 'on'},
               follow_redirects=True)
    assert 'created' in r.get_data(as_text=True)
    with app.app_context():
        after = SavedSearch.query.filter_by(user_id=carol.id).count()
        assert after == before + 1
        newest = SavedSearch.query.filter_by(user_id=carol.id, name='Test search').first()
        sid = newest.id
    r = c.post('/account/saved-searches', data={'action': 'delete', 'id': str(sid)},
               follow_redirects=True)
    assert 'deleted' in r.get_data(as_text=True)
    with app.app_context():
        assert SavedSearch.query.filter_by(user_id=carol.id).count() == before


def test_cover_letter_limit():
    c = login('david.k@test.com', 'TestPass123!')
    # David already has 2; add 3 more -> the 6th must be rejected
    for i in range(3):
        r = c.post('/account/cover-letters', data={'name': f'Letter {i}', 'body': 'x'},
                   follow_redirects=True)
    r = c.post('/account/cover-letters', data={'name': 'Sixth', 'body': 'x'},
               follow_redirects=True)
    assert 'up to 5' in r.get_data(as_text=True)


# ------------------------------------------------------------ content pages

def test_job_center_county_filter():
    body = get('/job-seekers/find-a-job/local-help?county=Franklin').get_data(as_text=True)
    assert '1111 E. Broad St.' in body
    assert 'Found 1 locations' in body
    body = get('/job-seekers/find-a-job/local-help').get_data(as_text=True)
    assert 'Found 89 locations' in body


def test_state_agencies_listed():
    body = get('/job-seekers/find-a-job/state-jobs').get_data(as_text=True)
    assert 'Administrative Services' in body
    assert '37' in body


def test_news_filter_by_topic_and_date():
    body = get('/news-and-events?topic=Veterans').get_data(as_text=True)
    assert 'Hire-a-Veteran' in body
    body = get('/news-and-events?from=2022-01-01&to=2022-12-31').get_data(as_text=True)
    assert 'New Features for Veterans and Military Spouses' in body
    assert 'November 2025 Hire-a-Veteran' not in body


def test_news_detail():
    body = get('/news-and-events/news/november-2025-hire-a-veteran-month-events').get_data(as_text=True)
    assert 'MOAA' in body and 'OMVetJobs' in body


def test_help_articles():
    body = get('/help-center/common-questions').get_data(as_text=True)
    assert '8 to 20 characters' in body
    assert 'omjnoreply@monster.com' in body
    body = get('/help-center/education').get_data(as_text=True)
    assert 'scholarship' in body.lower()


def test_site_search():
    body = get('/search?q=scholarship').get_data(as_text=True)
    assert 'Common Questions' in body
    assert 'Digital Scholarship' in body  # a real job matches too
    body = get('/search?q=Franklin').get_data(as_text=True)
    assert 'Columbus-Franklin County' in body


def test_contact_form_persists():
    from app import ContactMessage
    r = post('/contact-us', data={'name': 'Test User', 'email': 't@example.com',
                                  'subject': 'Hello', 'message': 'A message'},
             follow_redirects=True)
    assert 'Thank you' in r.get_data(as_text=True)
    with app.app_context():
        assert ContactMessage.query.filter_by(email='t@example.com').first() is not None
    r = post('/contact-us', data={'name': '', 'email': 'bad', 'message': ''},
             follow_redirects=True)
    assert 'Please fill in' in r.get_data(as_text=True)


# --------------------------------------------------------------- quiz flow

def test_career_quiz_submit():
    data = {f'q{i}': '0.5' for i in range(12)}
    data['q0'] = '0'   # dislike Realistic
    data['q3'] = '0'   # dislike Conventional
    data['q4'] = '1'   # like Enterprising
    data['q10'] = '1'  # like Enterprising
    r = post('/career-quiz/start', data=data, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert 'Your Career Profile' in body
    assert 'Enterprising' in body
    assert 'Project Manager' in body  # first suggested career


def test_career_quiz_requires_all_answers():
    r = post('/career-quiz/start', data={'q0': '1'}, follow_redirects=True)
    assert 'answer every question' in r.get_data(as_text=True)


# ------------------------------------------------------- idempotent seeding

def test_seeding_is_idempotent():
    from app import (NewsItem, JobCenter, HelpArticle, StateAgency, Resume,
                    CoverLetter, CareerPlanTask)
    with app.app_context():
        jobs_before = Job.query.count()
        users_before = User.query.count()
        seed_database(db, Job, NewsItem, JobCenter, HelpArticle, StateAgency)
        seed_benchmark_users(db, User, Job, SavedJob, Application, SavedSearch,
                             Resume, CoverLetter, CareerPlanTask)
        assert Job.query.count() == jobs_before
        assert User.query.count() == users_before


# ------------------------------------------------------------ no data leaks

def test_search_results_do_not_leak_answer_fields():
    """Reference codes, salary bands and job types must require the detail page."""
    body = get('/jobs/search?tjt=nurse').get_data(as_text=True)
    assert 'Job Reference Code' not in body
    assert '$85,000' not in body
    # per-job salary band labels are facet links only, never per-row answers
    rows = body.split('class="list-row"')
    for row in rows[1:]:
        assert 'High Income Jobs' not in row
        assert 'Upper Middle Income' not in row


def test_foreign_cover_letter_rejected():
    from app import CoverLetter
    c = login('alice.j@test.com', 'TestPass123!')
    with app.app_context():
        target = Job.query.filter(Job.id.notin_([a.job_id for a in Application.query.filter_by(user_id=1)])).first()
        foreign = CoverLetter.query.filter(CoverLetter.user_id != 1).first().id
        before = Application.query.count()
    response = c.post('/jobs/apply/' + target.jobid, data={'first_name': 'Alice', 'last_name': 'Johnson', 'email': 'alice.j@test.com', 'cover_letter_id': str(foreign)})
    assert response.status_code == 400
    with app.app_context():
        assert Application.query.count() == before


def test_post_logout_and_safe_redirect():
    c = fresh_client()
    assert c.get('/account/logout').status_code == 405
    for nxt in ['https://example.org', '//example.org', '/\\example.org']:
        c = fresh_client()
        r = c.post('/account/login', query_string={'next': nxt}, data={'email': 'alice.j@test.com', 'password': 'TestPass123!'})
        assert r.headers['Location'] == '/account/profile'
    c = fresh_client()
    r = c.post('/account/login?next=/account/resume', data={'email': 'alice.j@test.com', 'password': 'TestPass123!'})
    assert r.headers['Location'] == '/account/resume'


def test_quiz_rejects_out_of_range_and_nonfinite():
    from app import CareerQuizResult
    for value in ['NaN', 'Infinity', '-1', '100']:
        with app.app_context():
            before = CareerQuizResult.query.count()
        data = {f'q{i}': '0' for i in range(12)}; data['q0'] = value
        fresh_client().post('/career-quiz/start', data=data)
        with app.app_context():
            assert CareerQuizResult.query.count() == before


def test_saved_search_rejects_unusable_parameters():
    c = login('carol.d@test.com', 'TestPass123!')
    for params in ['[]', 'null', '{bad', '{"tjt": []}']:
        assert c.post('/account/saved-searches', data={'name': 'invalid', 'params': params}).status_code == 400


def test_password_matches_documented_rules():
    from app import valid_password
    assert valid_password('Nursing2026!')
    for value in ['abcdefgh1', 'ONLYUPPER1!', 'NoDigits!!', 'Has@Sign1', 'A' * 21 + '1!']:
        assert not valid_password(value)

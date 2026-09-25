#!/usr/bin/env python3
"""Idempotent seed for the OhioMeansJobs mirror.

Reads source_catalog.json (the committed, frozen catalog captured from the
upstream site) and materializes it into the SQLite seed database. Every
seed function early-returns when its tables are already populated so that
container boots and /reset/<site> stay byte-identical.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
from datetime import datetime, timedelta

from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Deterministic reference date for the mirror snapshot.
MIRROR_REFERENCE_DATE = datetime(2026, 9, 24)
RNG_SEED = 20260924

BENCHMARK_PASSWORD = 'TestPass123!'

# bcrypt hash of BENCHMARK_PASSWORD (frozen so the seed DB is byte-reproducible)
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$UbMR4lXMhoQqoWhbHIw.6O8njaKIvMSuuALysDX9HO24WuhosyT0u')

# ------------------------------------------------------------- career quiz
# The upstream Career Profile Quiz is a RIASEC self-assessment; the portal
# page lists the six traits it measures. Questions below follow that model.
QUIZ_QUESTIONS = [
    {'id': 1, 'text': 'I enjoy working with tools, machines, or my hands.', 'trait': 'Realistic'},
    {'id': 2, 'text': 'I like solving math and science problems.', 'trait': 'Investigative'},
    {'id': 3, 'text': 'I enjoy creative activities like drawing, writing, or music.', 'trait': 'Artistic'},
    {'id': 4, 'text': 'I like organizing information and keeping detailed records.', 'trait': 'Conventional'},
    {'id': 5, 'text': 'I enjoy leading projects and persuading other people.', 'trait': 'Enterprising'},
    {'id': 6, 'text': 'I like helping people and teaching them new things.', 'trait': 'Social'},
    {'id': 7, 'text': 'I prefer working outdoors or with plants and animals.', 'trait': 'Realistic'},
    {'id': 8, 'text': 'I like analyzing data to figure out how things work.', 'trait': 'Investigative'},
    {'id': 9, 'text': 'I value originality and dislike strict rules in my work.', 'trait': 'Artistic'},
    {'id': 10, 'text': 'I like clear procedures and structured tasks.', 'trait': 'Conventional'},
    {'id': 11, 'text': 'I enjoy competing and taking business risks.', 'trait': 'Enterprising'},
    {'id': 12, 'text': 'I am a good listener and care about others\u2019 wellbeing.', 'trait': 'Social'},
]

TRAIT_DESCRIPTIONS = {
    'Realistic': ('The "Doers". You likely enjoy practical, hands-on work with '
                  'tools, machines, plants, animals, or the outdoors. You prefer '
                  'concrete results you can see and touch.'),
    'Investigative': ('The "Thinkers". You likely enjoy observing, learning, and '
                      'solving problems — especially math and science problems that '
                      'reward analysis and curiosity.'),
    'Artistic': ('The "Creators". You likely enjoy unstructured, creative work — '
                 'writing, design, music, or visual arts — where originality is '
                 'valued over rigid rules.'),
    'Conventional': ('The "Organizers". You likely enjoy orderly, structured work '
                     'with data, records, and clear procedures where accuracy '
                     'matters.'),
    'Enterprising': ('The "Persuaders". You likely enjoy leading, selling, and '
                    'launching projects — work where you compete, take risks, and '
                    'persuade other people.'),
    'Social': ('The "Helpers". You likely enjoy work that teaches, heals, guides, '
               'or serves other people, and you care about others\u2019 wellbeing.'),
}

TRAIT_CAREERS = {
    'Realistic': ['Welder', 'Electrician', 'HVAC Service Technician', 'Truck Driver (CDL A)',
                  'Maintenance Technician', 'Machinist'],
    'Investigative': ['Software Developer', 'Data Analyst', 'Mechanical Engineer',
                      'Laboratory Research Associate', 'Clinical Pharmacist'],
    'Artistic': ['Graphic Designer', 'Content Writer', 'Marketing Specialist',
                 'Multimedia Artist'],
    'Conventional': ['Accountant', 'Bookkeeper', 'Administrative Assistant',
                     'Office Clerk', 'Bank Teller'],
    'Enterprising': ['Project Manager', 'Sales Account Executive', 'Business Development Manager',
                     'Retail Store Manager'],
    'Social': ['Registered Nurse', 'Social Worker', 'Child Care Teacher',
               'Customer Service Representative', 'Career Counselor'],
}


def _slugify(value):
    import re
    value = (value or '').lower()
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')
    return value


def _load_catalog():
    path = os.path.join(BASE_DIR, 'source_catalog.json')
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


# --------------------------------------------------------------- seed fns

def seed_database(db, Job, NewsItem, JobCenter, HelpArticle, StateAgency):
    """Populate every content table. Idempotent: gated on the jobs table."""
    if Job.query.count() > 0:
        return

    catalog = _load_catalog()

    for j in catalog['jobs']:
        db.session.add(Job(
            jobid=str(j['jobid']),
            title=j['title'],
            company=j['company'],
            company_slug=_slugify(j['company']),
            city=j['city'],
            job_types=','.join(j.get('job_types') or []),
            ref_code=j.get('ref_code') or '',
            description=j['description'],
            posted_date=j.get('posted_date') or '',
            industry_code=str(j.get('industry_code') or ''),
            salary_band=int(j.get('salary_band') or 0),
            education_level=int(j.get('education_level') or 0),
            certifications=','.join(str(c) for c in (j.get('certifications') or [])),
            remote=bool(j.get('remote')),
            internship=bool(j.get('internship')),
            apply_url=j.get('apply_url') or '',
        ))

    for n in catalog['news']:
        db.session.add(NewsItem(
            slug=n['slug'], title=n['title'], teaser=n.get('teaser', ''),
            body=json.dumps(n.get('body') or []), published_date=n.get('date', ''),
            topic=n.get('topic', '')))

    for c in catalog['job_centers']:
        db.session.add(JobCenter(
            name=c['name'], county=c.get('county', ''),
            address=c.get('address', ''), slug=_slugify(c['name'])))

    for slug, article in catalog['help_articles'].items():
        db.session.add(HelpArticle(
            slug=slug, section=slug, title=article['title'],
            body=json.dumps(article['body'])))

    for a in catalog['state_agencies']:
        db.session.add(StateAgency(
            name=a['name'], slug=_slugify(a['name']),
            logo=f"agencies/{_slugify(a['logo'])}.png"))

    db.session.commit()


def seed_benchmark_users(db, User, Job, SavedJob, Application, SavedSearch,
                        Resume, CoverLetter, CareerPlanTask):
    """Create the 4 benchmark users with realistic pre-existing data.

    Idempotent: gated on the benchmark user table.
    """
    if User.query.filter_by(email='alice.j@test.com').first():
        return

    rng = random.Random(RNG_SEED)
    jobs = Job.query.order_by(Job.jobid).all()
    by_title = {}
    for j in jobs:
        by_title.setdefault(j.title.lower(), []).append(j)

    def pick(title_substr, exclude=None):
        pool = [j for j in jobs if title_substr.lower() in j.title.lower()
                 and (exclude is None or j not in exclude)]
        return pool[0] if pool else jobs[0]

    USERS = [
        {'email': 'alice.j@test.com', 'first_name': 'Alice', 'last_name': 'Johnson',
         'phone': '(614) 555-0142', 'zip_code': '43215', 'city': 'Columbus',
         'military_status': '', 'employment_status': 'Unemployed',
         'target_job_title': 'Registered Nurse', 'career_level': 'Experienced (5+ years)',
         'education': "Bachelor's degree", 'willing_relocate': False},
        {'email': 'bob.c@test.com', 'first_name': 'Bob', 'last_name': 'Chen',
         'phone': '(216) 555-0177', 'zip_code': '44113', 'city': 'Cleveland',
         'military_status': 'Veteran', 'employment_status': 'Employed',
         'target_job_title': 'Warehouse Associate', 'career_level': 'Entry level',
         'education': 'High school diploma or equivalent', 'willing_relocate': True},
        {'email': 'carol.d@test.com', 'first_name': 'Carol', 'last_name': 'Davis',
         'phone': '(513) 555-0129', 'zip_code': '45202', 'city': 'Cincinnati',
         'military_status': '', 'employment_status': 'Employed',
         'target_job_title': 'Software Developer', 'career_level': 'Mid-level (2-5 years)',
         'education': "Bachelor's degree", 'willing_relocate': False},
        {'email': 'david.k@test.com', 'first_name': 'David', 'last_name': 'Kim',
         'phone': '(937) 555-0164', 'zip_code': '45402', 'city': 'Dayton',
         'military_status': '', 'employment_status': 'Student',
         'target_job_title': 'Accountant', 'career_level': 'Entry level',
         'education': "Bachelor's degree", 'willing_relocate': True},
    ]

    for idx, spec in enumerate(USERS):
        user = User(**spec)
        user.password_hash = BENCHMARK_PASSWORD_HASH  # frozen, byte-reproducible
        user.created_at = MIRROR_REFERENCE_DATE - timedelta(days=30 - idx)
        db.session.add(user)
        db.session.flush()  # grab user.id

        # ---- saved jobs (backpack)
        saved_specs = {
            'alice.j@test.com': ['nurse', 'dental', 'health'],
            'bob.c@test.com': ['warehouse', 'forklift', 'driver'],
            'carol.d@test.com': ['software', 'developer', 'data'],
            'david.k@test.com': ['account', 'clerk', 'financial'],
        }[spec['email']]
        used = []
        for kw in saved_specs:
            job = pick(kw, exclude=used)
            used.append(job)
            db.session.add(SavedJob(user_id=user.id, job_id=job.id,
                                    saved_at=MIRROR_REFERENCE_DATE - timedelta(days=rng.randint(1, 10))))

        # ---- applications (1-2 each)
        app_specs = {
            'alice.j@test.com': ['nurse'],
            'bob.c@test.com': ['warehouse', 'driver'],
            'carol.d@test.com': ['software'],
            'david.k@test.com': ['account'],
        }[spec['email']]
        for kw in app_specs:
            job = pick(kw, exclude=used)
            used.append(job)
            db.session.add(Application(
                user_id=user.id, job_id=job.id,
                applied_at=MIRROR_REFERENCE_DATE - timedelta(days=rng.randint(0, 6)),
                status='Submitted', first_name=spec['first_name'],
                last_name=spec['last_name'], email=spec['email'], phone=spec['phone']))

        # ---- saved searches with alerts
        search_specs = {
            'alice.j@test.com': [('Registered nurse jobs in Columbus', {'tjt': 'nurse', 'cnme': 'Columbus', 'sort': 'date'}, 'Daily'),
                                 ('Part-time healthcare openings', {'tjt': 'health', 'jtype': 'Part-Time', 'sort': 'date'}, 'Weekly')],
            'bob.c@test.com': [('Warehouse jobs near Cleveland', {'tjt': 'warehouse', 'cnme': 'Cleveland', 'sort': 'date'}, 'Daily'),
                               ('Forklift operator openings statewide', {'tjt': 'forklift', 'sort': 'date'}, 'Weekly')],
            'carol.d@test.com': [('Software developer roles in Ohio', {'tjt': 'software developer', 'sort': 'date'}, 'Daily'),
                                 ('Remote data analyst jobs', {'tjt': 'data analyst', 'remote': '1', 'sort': 'date'}, 'Monthly')],
            'david.k@test.com': [('Accounting jobs in Dayton', {'tjt': 'accountant', 'cnme': 'Dayton', 'sort': 'date'}, 'Daily'),
                                 ('Six figure finance jobs', {'tjt': 'finance', 'saltyp': '5', 'sort': 'date'}, 'Weekly')],
        }[spec['email']]
        for name, params, freq in search_specs:
            db.session.add(SavedSearch(user_id=user.id, name=name,
                                       query_params=json.dumps(params),
                                       alerts_enabled=True, frequency=freq,
                                       created_at=MIRROR_REFERENCE_DATE - timedelta(days=rng.randint(1, 15))))

        # ---- resume
        resume_specs = {
            'alice.j@test.com': ('Registered Nurse Resume',
                                 'Registered nurse with 6 years of med-surg experience in central Ohio hospitals.',
                                 'nursing, patient care, medication administration, care planning, bls, acls'),
            'bob.c@test.com': ('Warehouse Associate Resume',
                               'Reliable warehouse associate with forklift certification and 3 years of shipping/receiving experience.',
                                 'forklift operation, inventory, picking, packing, shipping, safety'),
            'carol.d@test.com': ('Software Developer Resume',
                                 'Full-stack developer with 4 years of experience building web applications in Python and JavaScript.',
                                 'python, javascript, sql, flask, react, git, testing, rest apis'),
            'david.k@test.com': ('Accounting Student Resume',
                                 'Accounting major graduating this spring; experienced with QuickBooks, reconciliations, and payroll support.',
                                 'quickbooks, excel, reconciliation, payroll, accounts payable, gaap'),
        }[spec['email']]
        db.session.add(Resume(user_id=user.id, title=resume_specs[0],
                              summary=resume_specs[1], skills=resume_specs[2],
                              experience='', active=True,
                              updated_at=MIRROR_REFERENCE_DATE - timedelta(days=3)))

        # ---- cover letters (2-3 each)
        letter_specs = {
            'alice.j@test.com': [
                ('Med-Surg Nursing Cover Letter',
                 'Dear Hiring Manager,\n\nMy six years of med-surg nursing experience at central Ohio hospitals prepared me to deliver safe, compassionate patient care from day one. I hold a compact RN license plus BLS and ACLS certifications.\n\nThank you for your consideration.\n\nAlice Johnson'),
                ('Part-Time Nursing Cover Letter',
                 'Dear Hiring Manager,\n\nI am applying for the part-time nursing role. My schedule flexibility and weekend availability make me a strong fit for your float pool.\n\nSincerely,\nAlice Johnson')],
            'bob.c@test.com': [
                ('Warehouse Operations Cover Letter',
                 'Dear Hiring Manager,\n\nI am a certified forklift operator with three years of high-volume distribution experience. I prioritize safety and accuracy.\n\nSincerely,\nBob Chen'),
                ('Veteran Transition Cover Letter',
                 'Dear Hiring Manager,\n\nAs a veteran transitioning to civilian logistics work, I bring discipline, teamwork, and mission focus to every shift.\n\nRespectfully,\nBob Chen'),
                ('Driver Cover Letter',
                 'Dear Hiring Manager,\n\nI maintain a clean driving record and am comfortable with regional routes and night schedules.\n\nSincerely,\nBob Chen')],
            'carol.d@test.com': [
                ('Software Engineering Cover Letter',
                 'Dear Hiring Team,\n\nI build accessible, well-tested web applications in Python and JavaScript, and I would love to bring that practice to your team.\n\nBest regards,\nCarol Davis'),
                ('Remote Work Cover Letter',
                 'Dear Hiring Team,\n\nI have worked remotely for two years and keep distributed teams aligned through clear writing and reliable delivery.\n\nBest regards,\nCarol Davis')],
            'david.k@test.com': [
                ('Accounting Cover Letter',
                 'Dear Hiring Manager,\n\nAs an accounting major with hands-on QuickBooks and reconciliation experience, I am eager to contribute to your finance team.\n\nSincerely,\nDavid Kim'),
                ('Internship Cover Letter',
                 'Dear Hiring Manager,\n\nI am seeking an internship where I can apply my coursework in auditing and taxation to real client work.\n\nSincerely,\nDavid Kim')],
        }[spec['email']]
        for name, body in letter_specs:
            db.session.add(CoverLetter(user_id=user.id, name=name, body=body,
                                       updated_at=MIRROR_REFERENCE_DATE - timedelta(days=rng.randint(1, 20))))

        # ---- career plan tasks
        plan_specs = {
            'alice.j@test.com': [
                ('Update nursing resume with compact license', '2026-10-05', False),
                ('Complete ACLS renewal course', '2026-10-20', False),
                ('Apply to two hospital openings', '2026-09-15', True)],
            'bob.c@test.com': [
                ('Renew forklift certification', '2026-10-10', False),
                ('Register for OhioMeansJobs veteran workshop', '2026-09-30', False),
                ('Submit five warehouse applications', '2026-09-20', True)],
            'carol.d@test.com': [
                ('Refresh Python portfolio projects', '2026-10-15', False),
                ('Complete one mock interview', '2026-10-01', True)],
            'david.k@test.com': [
                ('Finish QuickBooks online course', '2026-10-08', False),
                ('Meet with campus career counselor', '2026-09-28', False),
                ('Draft first cover letter', '2026-09-10', True)],
        }[spec['email']]
        for description, deadline, done in plan_specs:
            db.session.add(CareerPlanTask(user_id=user.id, description=description,
                                          deadline=deadline, done=done,
                                          created_at=MIRROR_REFERENCE_DATE - timedelta(days=rng.randint(5, 25))))

    db.session.commit()


def build_seed_file():
    """Materialise instance_seed/ohiomeansjobs.db from a fresh build.

    Deterministic: the catalog is frozen, the RNG is seeded, and every
    timestamp is anchored to MIRROR_REFERENCE_DATE. PYTHONHASHSEED=0 is
    set by the image build for full reproducibility. The seed is built
    in a scratch directory via OMJ_DB_URI so the runtime instance/ DB is
    never touched.
    """
    import os
    import shutil
    base = pathlib.Path(BASE_DIR)
    scratch = base / 'instance_build'
    scratch.mkdir(parents=True, exist_ok=True)
    db_path = scratch / 'ohiomeansjobs.db'
    if db_path.exists():
        db_path.unlink()
    os.environ['OMJ_DB_URI'] = f'sqlite:///{db_path}'
    from app import (app, db, Job, NewsItem, JobCenter, HelpArticle,
                     StateAgency, User, SavedJob, Application, SavedSearch,
                     Resume, CoverLetter, CareerPlanTask)
    with app.app_context():
        db.create_all()
        seed_database(db, Job, NewsItem, JobCenter, HelpArticle, StateAgency)
        seed_benchmark_users(db, User, Job, SavedJob, Application, SavedSearch,
                             Resume, CoverLetter, CareerPlanTask)
    instance_seed = base / 'instance_seed'
    instance_seed.mkdir(parents=True, exist_ok=True)
    seed_path = instance_seed / 'ohiomeansjobs.db'
    for stale in instance_seed.glob('*.db'):
        stale.unlink()
    shutil.copy2(db_path, seed_path)
    shutil.rmtree(scratch, ignore_errors=True)
    return seed_path


if __name__ == '__main__':
    written = build_seed_file()
    print(f"[seed] instance_seed/ohiomeansjobs.db written ({written.stat().st_size} bytes)")

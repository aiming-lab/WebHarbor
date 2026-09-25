"""Deterministic verifier contract tests for the 18 OhioMeansJobs tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a
clean seed pair; stateful tasks against the seed with the exact allowed sqlite
delta); a no-op run (homepage only, empty answer, clean DB) MUST FAIL; a
wrong answer MUST FAIL; a shortcut (correct answer with homepage-only
navigation) MUST FAIL — every task's required surface is beyond the homepage.
Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks MUST FAIL on
a state-mismatch (no DB delta) and on a wrong delta. Package tampering
(task_id mismatch, off-site URLs, missing screenshot, non-done trajectory)
MUST fail closed.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are
hand-written in the agent_demo/agent.py shape (mirroring the reviewer's real
Playwright walkthroughs of 2026-09-24).
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, PASSWORD, RunBuilder, _acquire_seed,  # noqa: E402
                       build_run, copy_db, db_one, job_pk, mutate_db,
                       noop_run, run_verifier)

STATEFUL = {2, 3, 4, 5, 6, 7, 17}
READ_ONLY = sorted(set(range(18)) - STATEFUL)
CREATED = "2026-09-24 12:00:00.000000"


def _seed():
    return _acquire_seed()


# ---------------------------------------------------------------- honest fixtures
def honest_run(tmp: Path, index: int, name: str | None = None) -> tuple[Path, Path, Path]:
    """Build the honest run for task <index>; returns (run_dir, initial, after).

    The after.db is already written inside run_dir by the fixture builders;
    callers only need to place initial.db.
    """
    seed = _seed()

    if index == 0:
        root = tmp / (name or "honest_00")
        b = build_run(tmp, name or "honest_00", "OhioMeansJobs--0")
        b.step("/jobs/search?tjt=nurse+aide&cnme=Findlay", "goto", {})
        b.step("/jobs/view/6931551303", "click", {"selector": "a"})
        b.step("/jobs/company/blanchard-valley-regional-health-center", "click", {"selector": "a"})
        b.step("/jobs/view/6931520233", "click", {"selector": "a"})
        b.done("The job is 'Nurse Aide, STNA (FT, PT, PRN)' at Blanchard Valley Regional "
               "Health Center in Findlay. Its job summary lists Full-Time and Permanent, "
               "education level Bachelor's degree, the job reference code is NA, and it was "
               "posted 2026-09-24. The description does mention a sign-on bonus ('Sign On "
               "Bonus Eligible!'). The employer currently has 8 total job postings, 2 posted "
               "2026-09-24, and its other Findlay job posted the same date is 'Res Care Nurse "
               "(Heights) - PRN' — that job's salary range is High Income Jobs ($80K-$99K) "
               "and it offers Part-Time.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 1:
        root = tmp / (name or "honest_01")
        b = build_run(tmp, name or "honest_01", "OhioMeansJobs--1")
        b.step("/jobs/search?tjt=nurse", "goto", {})
        b.step("/jobs/search?tjt=nurse&saltyp=5", "click", {"selector": "a"})
        b.step("/jobs/view/6929453642", "click", {"selector": "a"})
        b.step("/jobs/search?tjt=nurse&saltyp=5", "goto", {})
        b.step("/jobs/view/6931749800", "click", {"selector": "a"})
        b.step("/jobs/search?tjt=nurse&jtype=Part-Time", "goto", {})
        b.done("The nurse search returned 12 results. Narrowed to six-figure positions "
               "(more than $100K), 2 jobs remain: 'MECHANIC II - Full Time, 2nd Shift' at "
               "Blanchard Valley Regional Health Center and 'CICU Nurse Practitioner' at "
               "Cincinnati Children's Hospital Medical Center. The Findlay health center "
               "job (MECHANIC II) was posted 2026-09-23, is Full-Time and Permanent, in the "
               "Health Care and Social Assistance industry. The children's hospital job "
               "(CICU Nurse Practitioner) is in Cincinnati, OH, its reference code is NA, "
               "and its education level is Master's degree. Narrowing the nurse search to "
               "part-time schedules leaves 2 nurse jobs: 'Res Care Nurse (Heights) - PRN' "
               "at Blanchard Valley Regional Health Center and 'Experienced Registered "
               "Nurse, RN, Nurse Helpline, Part-Time' at Cincinnati Children's Hospital "
               "Medical Center.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 2:
        root = tmp / (name or "honest_02")
        b = build_run(tmp, name or "honest_02", "OhioMeansJobs--2")
        b.step("/account/register", "goto", {})
        b.fill("/account/register", "grad.2026@test.com", "#email")
        b.fill("/account/register", "Career2026x", "#password")
        b.step("/account/register", "click", {"selector": "button[type=submit]"},
               url_after="/account/profile")
        b.step("/account/cover-letters", "goto", {})
        b.fill("/account/cover-letters", "First Position Letter", "#name")
        b.step("/account/cover-letters", "click", {"selector": "button[type=submit]"})
        b.step("/jobs/search?tjt=receptionist&cnme=Cincinnati", "goto", {})
        b.step("/jobs/view/6928092839", "click", {"selector": "a"})
        b.step("/jobs/apply/6928092839", "click", {"selector": "a"})
        b.step("/jobs/apply/6928092839", "click", {"selector": "button[type=submit]"})
        b.done("I applied to 'Part-Time Receptionist / Front Desk Coordinator' at Beacon "
               "Hill Staffing Group, LLC in Cincinnati, attaching my 'First Position "
               "Letter' cover letter. The confirmation number I received is OMJ-6-2839.")
        after = mutate_db(seed, root / "after.db", [
            ("INSERT INTO users (id, email, password_hash, first_name, last_name, phone, "
             "zip_code, city, military_status, employment_status, target_job_title, "
             "career_level, education, willing_relocate, created_at) "
             "VALUES (5, 'grad.2026@test.com', 'x', 'Grad', 'Student', '', '', '', '', '', "
             "'', '', '', 0, ?)", (CREATED,)),
            ("INSERT INTO cover_letters (id, user_id, name, body, updated_at) "
             "VALUES (10, 5, 'First Position Letter', 'Dear Hiring Manager, ...', ?)",
             (CREATED,)),
            ("INSERT INTO applications (id, user_id, job_id, applied_at, status, first_name, "
             "last_name, email, phone, cover_letter_id) "
             "VALUES (6, 5, ?, ?, 'Submitted', 'Grad', 'Student', 'grad.2026@test.com', '', 10)",
             (job_pk(seed, "6928092839"), CREATED)),
        ])
        return root, seed, after

    if index == 3:
        root = tmp / (name or "honest_03")
        b = build_run(tmp, name or "honest_03", "OhioMeansJobs--3")
        b.login("alice.j@test.com")
        b.step("/jobs/search?tjt=nurse+practitioner", "goto", {})
        b.step("/jobs/view/6931749800", "click", {"selector": "a"})
        b.step("/jobs/apply/6931749800", "click", {"selector": "a"})
        b.step("/jobs/apply/6931749800", "click", {"selector": "button[type=submit]"})
        b.step("/account/applications", "goto", {})
        b.done("I applied to the CICU Nurse Practitioner opening at Cincinnati Children's "
               "Hospital Medical Center with my Med-Surg Nursing Cover Letter attached. The "
               "job's summary lists education level Master's degree and reference code NA, "
               "and my applications list shows the application status as Submitted.")
        after = mutate_db(seed, root / "after.db", [
            ("INSERT INTO applications (id, user_id, job_id, applied_at, status, first_name, "
             "last_name, email, phone, cover_letter_id) "
             "VALUES (6, 1, ?, ?, 'Submitted', 'Alice', 'Johnson', 'alice.j@test.com', "
             "'(614) 555-0142', 1)",
             (job_pk(seed, "6931749800"), CREATED)),
        ])
        return root, seed, after

    if index == 4:
        root = tmp / (name or "honest_04")
        b = build_run(tmp, name or "honest_04", "OhioMeansJobs--4")
        b.login("bob.c@test.com")
        b.step("/account/saved-jobs", "goto", {})
        b.step("/jobs/view/6930717794", "click", {"selector": "a"})
        b.step("/jobs/view/6930717794", "click", {"selector": "button[type=submit]"})
        b.step("/account/saved-jobs", "goto", {})
        b.step("/jobs/view/6928198981", "click", {"selector": "a"})
        b.step("/jobs/apply/6928198981", "click", {"selector": "a"})
        b.step("/jobs/apply/6928198981", "click", {"selector": "button[type=submit]"})
        b.done("I removed the saved job 'Union Production Operator - Forklift Operator | "
               "Lift Driver' and applied to the most recently posted remaining saved job: "
               "'Material Handler, Warehouse' located in Dublin, OH.")
        after = mutate_db(seed, root / "after.db", [
            ("DELETE FROM saved_jobs WHERE user_id = 2 AND job_id = ?",
             (job_pk(seed, "6930717794"),)),
            ("INSERT INTO applications (id, user_id, job_id, applied_at, status, first_name, "
             "last_name, email, phone, cover_letter_id) "
             "VALUES (6, 2, ?, ?, 'Submitted', 'Bob', 'Chen', 'bob.c@test.com', "
             "'(216) 555-0177', 4)",
             (job_pk(seed, "6928198981"), CREATED)),
        ])
        return root, seed, after

    if index == 5:
        root = tmp / (name or "honest_05")
        b = build_run(tmp, name or "honest_05", "OhioMeansJobs--5")
        b.login("carol.d@test.com")
        b.step("/account/saved-searches", "goto", {})
        b.step("/jobs/search?tjt=software+developer&remote=1", "goto", {})
        b.step("/jobs/search?tjt=software+developer&remote=1", "click",
               {"selector": "button[type=submit]"}, url_after="/account/saved-searches")
        b.step("/account/saved-searches", "goto", {})
        b.step("/account/saved-searches", "click", {"selector": "button[type=submit]"})
        b.done("I created the saved search 'Remote developer roles' with daily alerts for "
               "remote software developer positions and deleted the monthly 'Remote data "
               "analyst jobs' search. Carol now has 2 saved searches.")
        after = mutate_db(seed, root / "after.db", [
            ("DELETE FROM saved_searches WHERE user_id = 3 AND name = 'Remote data analyst jobs'", ()),
            ("INSERT INTO saved_searches (id, user_id, name, query_params, alerts_enabled, "
             "frequency, created_at) VALUES (9, 3, 'Remote developer roles', "
             "'{\"tjt\": \"software developer\", \"remote\": \"1\", \"sort\": \"date\"}', "
             "1, 'Daily', ?)", (CREATED,)),
        ])
        return root, seed, after

    if index == 6:
        root = tmp / (name or "honest_06")
        b = build_run(tmp, name or "honest_06", "OhioMeansJobs--6")
        b.step("/job-seekers/find-a-job/career-profile-quiz", "goto", {})
        b.step("/career-quiz/start", "click", {"selector": "a"})
        for idx, val in [(0, "0"), (1, "0"), (2, "0"), (3, "0"), (4, "1"), (5, "0"),
                         (6, "0"), (7, "0"), (8, "0"), (9, "0"), (10, "1"), (11, "0")]:
            b.step("/career-quiz/start", "click", {"selector": f"input[name=q{idx}][value={val}]"})
        b.step("/career-quiz/start", "click", {"selector": "button[type=submit]"})
        b.step("/jobs/search?tjt=Project+Manager", "goto", {})
        b.done("My top trait is Enterprising with a score of 2. The first two suggested "
               "careers are Project Manager and Sales Account Executive. Searching the job "
               "board for Project Manager, the newest matching job is 'Manager, Sales "
               "Incentive Compensation Operations' at Vertiv Corporation.")
        after = mutate_db(seed, root / "after.db", [
            ("INSERT INTO career_quiz_results (id, user_id, answers, scores, top_trait, "
             "created_at) VALUES (1, NULL, '{}', "
             "'{\"Enterprising\": 2.0, \"Realistic\": 0.0, \"Investigative\": 0.0, "
             "\"Artistic\": 0.0, \"Conventional\": 0.0, \"Social\": 0.0}', "
             "'Enterprising', ?)", (CREATED,)),
        ])
        return root, seed, after

    if index == 7:
        root = tmp / (name or "honest_07")
        b = build_run(tmp, name or "honest_07", "OhioMeansJobs--7")
        b.login("david.k@test.com")
        b.step("/account/resume", "goto", {})
        b.step("/jobs/view/6930560403", "click", {"selector": "a"})
        b.step("/account/resume", "goto", {})
        b.step("/jobs/view/6931261515", "click", {"selector": "a"})
        b.fill("/account/resume", "quickbooks, excel, reconciliation, payroll, accounts "
               "payable, gaap, tax preparation", "#skills")
        b.step("/account/resume", "click", {"selector": "button[type=submit]"})
        b.done("David's current top SkillsMatch recommendation was 'Senior Accountant, "
               "Grants and General Ledger' at The College of Wooster. After adding 'tax "
               "preparation' to his resume skills, keeping it active and saving, the top "
               "three SkillsMatch recommendations are: 'Senior Accountant, Grants and "
               "General Ledger' at The College of Wooster; 'Customer Service Coordinator' "
               "at CoolSeal Inc.; and 'Application Engineer - AC Power, Hyperscale' at "
               "Vertiv Corporation. The Dover, OH one ('Application Engineer - AC Power, "
               "Hyperscale') was posted 2026-09-24, is Full-Time and Temporary, with "
               "education Bachelor's degree. The top recommended job was posted 2026-09-23.")
        after = mutate_db(seed, root / "after.db", [
            ("UPDATE resumes SET skills = skills || ', tax preparation', updated_at = ? "
             "WHERE user_id = 4", (CREATED,)),
        ])
        return root, seed, after

    if index == 8:
        root = tmp / (name or "honest_08")
        b = build_run(tmp, name or "honest_08", "OhioMeansJobs--8")
        b.step("/job-seekers/find-a-job/local-help?county=Ottawa", "goto", {})
        b.step("/job-seekers/find-a-job/local-help?county=Franklin", "goto", {})
        b.step("/job-seekers/find-a-job/local-help?county=Cuyahoga", "goto", {})
        b.step("/job-seekers/find-a-job/local-help", "goto", {})
        b.step("/jobs/search?cnme=Cleveland&rad=20", "goto", {})
        b.step("/jobs/view/6930596393", "click", {"selector": "a"})
        b.done("The Ottawa County center is 'Ottawa County' at 8043 W. State Route 163, "
               "Suite 200, Oak Harbor, OH 43449. The Franklin County center is at 1111 E. "
               "Broad St., Columbus, OH 43205. The Cuyahoga County center is at 1975 E. "
               "61st Street, Cleveland, Ohio 44103. The site lists 89 total center "
               "locations. Searching for jobs within 20 miles of Cleveland returns 15 jobs; "
               "the newest one is 'Staff Traffic Engineer' at Langan Engineering & "
               "Environmental Services.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 9:
        root = tmp / (name or "honest_09")
        b = build_run(tmp, name or "honest_09", "OhioMeansJobs--9")
        b.step("/job-seekers/find-a-job/state-jobs", "goto", {})
        b.step("/jobs/search?omjindustry=92", "goto", {})
        b.step("/jobs/view/6931751154", "click", {"selector": "a"})
        b.step("/jobs/search?omjindustry=92", "goto", {})
        b.step("/jobs/view/6931749896", "click", {"selector": "a"})
        b.step("/jobs/company/cincinnati-children-s-hospital-medical-center", "click", {"selector": "a"})
        b.done("The State of Ohio jobs page shows 37 state agencies. Searching Government "
               "industry jobs by date, the most recent one is 'Paramedic' at Cincinnati "
               "Children's Hospital Medical Center in Cincinnati, posted 2026-09-23, with "
               "a Middle Income Jobs ($30K-$49K) salary range; it lists both Full-Time and "
               "Part-Time. The next-newest Government job is 'Paramedic - Liberty ED' in "
               "Liberty Township. The employer's company page lists 11 job postings.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 10:
        root = tmp / (name or "honest_10")
        b = build_run(tmp, name or "honest_10", "OhioMeansJobs--10")
        b.step("/news-and-events", "goto", {})
        b.step("/news-and-events/news/november-2025-hire-a-veteran-month-events", "click",
               {"selector": "a"})
        b.step("/news-and-events?topic=Veterans", "goto", {})
        b.step("/news-and-events?from=2022-01-01&to=2022-12-31", "goto", {})
        b.done("The November 2025 Hire-a-Veteran article was published on October 22, 2025. "
               "The MOAA Virtual Career Fair takes place on Dec. 4. Veterans and their "
               "families should follow @OMVetJobs on social media. Filtering the news list "
               "to the Veterans topic shows 3 news items. Filtering to items published in "
               "2022 shows 4 news items, including 'New Features for Veterans and Military "
               "Spouses'.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 11:
        root = tmp / (name or "honest_11")
        b = build_run(tmp, name or "honest_11", "OhioMeansJobs--11")
        b.step("/help-center", "goto", {})
        b.step("/help-center/common-questions", "click", {"selector": "a"})
        b.step("/help-center/education", "click", {"selector": "a"})
        b.step("/help-center/job-seeker", "click", {"selector": "a"})
        b.step("/help-center/employers", "click", {"selector": "a"})
        b.done("The password requirements for an OhioMeansJobs account are: 8 to 20 "
               "characters long, at least one number, one symbol (excluding ' @ - \"), and "
               "a combination of upper and lower case characters. The password reset email "
               "comes from omjnoreply@monster.com. The FAQ about finding scholarship "
               "information is in the Common Questions section (also listed under Help "
               "for Students and Education). OhioMeansJobs.com aggregates over 1 million "
               "available scholarships. The career profile quiz takes about 30 minutes "
               "according to the job seeker help section. The first FAQ topic in the "
               "employer help section is 'Steps to register for an Employer account'.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 12:
        root = tmp / (name or "honest_12")
        b = build_run(tmp, name or "honest_12", "OhioMeansJobs--12")
        b.step("/jobs/search?tjt=data+analyst&remote=1", "goto", {})
        b.step("/jobs/view/6931749872", "click", {"selector": "a"})
        b.step("/jobs/search?tjt=data+analyst&remote=1", "goto", {})
        b.step("/jobs/view/6931641205", "click", {"selector": "a"})
        b.step("/jobs/search?tjt=data+analyst&remote=1", "goto", {})
        b.step("/jobs/view/6930894447", "click", {"selector": "a"})
        b.done("The remote-friendly data analyst search matches 10 jobs. The Steris "
               "Corporation job is 'Senior Data Analyst - Distribution and Transportation' "
               "in Mentor, OH, posted 2026-09-23, Full-Time and Permanent, with a salary "
               "range of $85,000 - $110,000 mentioned in its description. The result listed "
               "immediately after it is 'Experienced Registered Nurse, RN, Nurse Helpline, "
               "Part-Time' at Cincinnati Children's Hospital Medical Center, posted "
               "2026-09-23. The newest matching result of all is 'Sales Instructor' at "
               "Vertiv Corporation, posted 2026-09-24.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 13:
        root = tmp / (name or "honest_13")
        b = build_run(tmp, name or "honest_13", "OhioMeansJobs--13")
        b.step("/jobs/search?tjt=welder", "goto", {})
        b.step("/jobs/view/6930719611", "click", {"selector": "a"})
        b.step("/jobs/search?tjt=welder", "goto", {})
        b.step("/jobs/view/6931551306", "click", {"selector": "a"})
        b.step("/jobs/search?tjt=welder", "goto", {})
        b.step("/jobs/view/6931641374", "click", {"selector": "a"})
        b.done("The Daifuku America Corporation 'Welder /Fitter II' job is in Reynoldsburg, "
               "OH, posted 2026-09-22, with a High Income Jobs ($80K-$99K) salary range and "
               "education High school diploma or equivalent. The Steele Solutions 'Welder "
               "L1' job is in Tiffin, OH, posted 2026-09-23, with an Upper Middle Income "
               "Jobs ($50K-$79K) range and education High school diploma or equivalent — "
               "Daifuku lists the higher salary range. The Huber Heights welder job is at "
               "Enjet Aero, posted 2026-09-23, with education Postsecondary nondegree award "
               "and job types Full-Time and Permanent.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 14:
        root = tmp / (name or "honest_14")
        b = build_run(tmp, name or "honest_14", "OhioMeansJobs--14")
        b.step("/jobs/search?tjt=childcare&jtype=Part-Time", "goto", {})
        b.step("/jobs/view/6925540150", "click", {"selector": "a"})
        b.step("/jobs/search?tjt=child+care+teacher&cnme=Columbus", "goto", {})
        b.step("/jobs/view/6917643568", "click", {"selector": "a"})
        b.done("The part-time childcare search matches 2 jobs. The Mount Vernon job is "
               "'CHILDCARE WORKER' at First Presbyterian Church of Mount Vernon, posted "
               "2026-09-15, it is Permanent, and its education level is Bachelor's degree. "
               "The other part-time childcare job is at Right at School LLC. The Columbus "
               "childcare teaching job is at Bright Horizons Children's Centers, Inc., "
               "posted 2026-09-23, and it also offers Part-Time.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 15:
        root = tmp / (name or "honest_15")
        b = build_run(tmp, name or "honest_15", "OhioMeansJobs--15")
        b.step("/for-employers", "goto", {})
        b.step("/for-employers/resources-for-employers", "click", {"selector": "a"})
        b.step("/jobs/search?tjt=veteran", "goto", {})
        b.step("/help-center/employers", "goto", {})
        b.done("The For Employers page shows 6,492 employers on board, 160 active job "
               "postings, 1,460,686 resumes available, and 104 companies hiring. The "
               "hiring resources page is 'Resources For Employers'; its first three "
               "resources are Hire a Veteran, Hiring People with Disabilities, and Hiring "
               "Restored Citizens. Following the Hire a Veteran resource shows 60 job "
               "results. The first FAQ topic in the employer help section is 'Steps to "
               "register for an Employer account'.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 16:
        root = tmp / (name or "honest_16")
        b = build_run(tmp, name or "honest_16", "OhioMeansJobs--16")
        b.step("/search?q=scholarship", "goto", {})
        b.step("/search?q=Hire-a-Veteran", "goto", {})
        b.step("/news-and-events/news/november-2025-hire-a-veteran-month-events", "click",
               {"selector": "a"})
        b.step("/search?q=Franklin", "goto", {})
        b.done("The scholarship site search returns 3 results: one Job ('Director of the "
               "Freedman Center for Digital Scholarship (Librarian 3 Lead)') and two Help "
               "results — the scholarship FAQ belongs to the Common Questions section and "
               "the Help for Students and Education section. The Hire-a-Veteran search "
               "shows the news item 'November 2025 Hire-a-Veteran Month Events', published "
               "October 22, 2025, topic Veterans. The Franklin site search returns 3 "
               "results: one Job and two Center results, including the Columbus-Franklin "
               "County job center.")
        after = copy_db(seed, root / "after.db")
        return root, seed, after

    if index == 17:
        root = tmp / (name or "honest_17")
        b = build_run(tmp, name or "honest_17", "OhioMeansJobs--17")
        b.login("bob.c@test.com")
        b.step("/account/cover-letters", "goto", {})
        b.step("/account/cover-letters", "click", {"selector": "button[type=submit]"})
        b.fill("/account/cover-letters", "Warehouse Team Letter", "#name")
        b.fill("/account/cover-letters", "Dear Hiring Manager, warehouse experience.", "#body")
        b.step("/account/cover-letters", "click", {"selector": "button[type=submit]"})
        b.step("/account/career-plan", "goto", {})
        b.done("I deleted the Driver Cover Letter and created 'Warehouse Team Letter' "
               "about my warehouse experience. Bob now has 3 cover letters, the oldest "
               "remaining one is the Veteran Transition Cover Letter, and the site says "
               "you can save 5 different cover letters. His career plan contains 3 tasks "
               "with 1 marked complete; the task about renewing a certification ('Renew "
               "forklift certification') has deadline 2026-10-10.")
        after = mutate_db(seed, root / "after.db", [
            ("DELETE FROM cover_letters WHERE user_id = 2 AND name = 'Driver Cover Letter'", ()),
            ("INSERT INTO cover_letters (id, user_id, name, body, updated_at) "
             "VALUES (10, 2, 'Warehouse Team Letter', 'Dear Hiring Manager, warehouse "
             "experience.', ?)", (CREATED,)),
        ])
        return root, seed, after

    raise ValueError(f"no honest fixture for task {index}")


HONEST_ANSWERS = {  # correct final answers for shortcut fixtures
    0: "Nurse Aide, STNA (FT, PT, PRN); Full-Time, Permanent; education Bachelor's degree; "
       "ref NA; posted 2026-09-24; sign-on bonus yes; 8 postings; 2 same-date; Res Care "
       "Nurse (Heights) - PRN; $80K-$99K; offers Part-Time",
    1: "12 nurse results; 2 six-figure: MECHANIC II at Blanchard Valley and CICU Nurse "
       "Practitioner at Cincinnati Children's; mechanic posted 2026-09-23, Full-Time and "
       "Permanent, Health Care and Social Assistance; CICU in Cincinnati with ref NA and "
       "education Master's degree; 2 part-time nurse jobs: Blanchard Valley and "
       "Cincinnati Children's",
    2: "Part-Time Receptionist / Front Desk Coordinator at Beacon Hill Staffing Group, LLC; "
       "confirmation OMJ-6-2839",
    3: "Education Master's degree; reference code NA; status Submitted",
    4: "Material Handler, Warehouse in Dublin, OH",
    5: "2 saved searches",
    6: "Enterprising with score 2; Project Manager and Sales Account Executive; newest: "
       "Manager, Sales Incentive Compensation Operations at Vertiv Corporation",
    7: "Before top: Senior Accountant, Grants and General Ledger at The College of "
       "Wooster; after: Senior Accountant, Grants and General Ledger at The College of "
       "Wooster; Customer Service Coordinator at CoolSeal Inc.; Application Engineer - "
       "AC Power, Hyperscale at Vertiv Corporation; Dover job posted 2026-09-24, "
       "Full-Time and Temporary, education Bachelor's degree; top job posted 2026-09-23",
    8: "Ottawa County: 8043 W. State Route 163, Suite 200, Oak Harbor, OH 43449; Franklin: "
       "1111 E. Broad St., Columbus, OH 43205; Cuyahoga: 1975 E. 61st Street, Cleveland, "
       "Ohio 44103; 89 locations; 15 jobs within 20 miles of Cleveland; newest: Staff "
       "Traffic Engineer at Langan Engineering",
    9: "37 agencies; Paramedic at Cincinnati Children's Hospital Medical Center, "
       "Cincinnati, posted 2026-09-23, $30K-$49K, Full-Time and Part-Time; next-newest: "
       "Paramedic - Liberty ED in Liberty Township; company page lists 11 postings",
    10: "Published October 22, 2025; MOAA Virtual Career Fair on Dec. 4; @OMVetJobs; "
        "3 Veterans news items; 4 items in 2022, including New Features for Veterans "
        "and Military Spouses",
    11: "8 to 20 characters, at least one number, one symbol, upper and lower case; "
        "omjnoreply@monster.com; Common Questions; over 1 million available scholarships; "
        "quiz takes about 30 minutes; first employer FAQ: Steps to register for an "
        "Employer account",
    12: "10 matches; Senior Data Analyst - Distribution and Transportation, Mentor, OH, "
        "posted 2026-09-23, Full-Time and Permanent, $85,000 - $110,000; result "
        "immediately after: Experienced Registered Nurse, RN, Nurse Helpline, Part-Time "
        "at Cincinnati Children's Hospital Medical Center, posted 2026-09-23; newest of "
        "all: Sales Instructor at Vertiv Corporation, posted 2026-09-24",
    13: "Daifuku Welder /Fitter II: Reynoldsburg, 2026-09-22, $80K-$99K, education High "
        "school diploma or equivalent; Steele Welder L1: Tiffin, 2026-09-23, $50K-$79K, "
        "education High school diploma or equivalent; Daifuku higher; Huber Heights: "
        "Enjet Aero, 2026-09-23, education Postsecondary nondegree award, Full-Time and "
        "Permanent",
    14: "2 matches; CHILDCARE WORKER at First Presbyterian Church of Mount Vernon, "
        "2026-09-15, Permanent, education Bachelor's degree; other: Right at School LLC; "
        "Columbus: Bright Horizons Children's Centers, Inc., posted 2026-09-23, also "
        "Part-Time",
    15: "6,492 employers on board; 160 active job postings; 1,460,686 resumes available; "
        "104 companies hiring; Resources For Employers; Hire a Veteran, Hiring People "
        "with Disabilities, Hiring Restored Citizens; Hire a Veteran shows 60 job "
        "results; Steps to register for an Employer account",
    16: "3 results: one Job and two Help; sections Common Questions and Help for Students "
        "and Education; November 2025 Hire-a-Veteran Month Events, October 22, 2025, "
        "Veterans; Franklin: 3 results, one Job and two Centers, including "
        "Columbus-Franklin County",
    17: "3 cover letters; oldest remaining: Veteran Transition Cover Letter; save up to "
        "5 cover letters; career plan: 3 tasks, 1 complete, certification deadline "
        "2026-10-10",
}

# ---------------------------------------------------------------- per-task tests
@pytest.mark.parametrize("index", range(18))
def test_honest_pass(tmp_path, index):
    run_dir, initial, after = honest_run(tmp_path, index)
    copy_db(initial, run_dir / "initial.db")
    assert (run_dir / "after.db").is_file()
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is True, json.dumps(verdict, indent=1)[:2000]


@pytest.mark.parametrize("index", range(18))
def test_noop_fails(tmp_path, index):
    run_dir = noop_run(tmp_path, index)
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


@pytest.mark.parametrize("index", range(18))
def test_wrong_answer_fails(tmp_path, index):
    run_dir, initial, after = honest_run(tmp_path, index, name=f"wrong_{index:02d}")
    # rewrite the final answer with wrong facts
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = "Wrong: the answer is 99, the employer is Acme Corp, " \
                           "the reference code is XX-0000, posted 1999-01-01, no bonus."
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    copy_db(initial, run_dir / "initial.db")
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


@pytest.mark.parametrize("index", range(18))
def test_shortcut_fails(tmp_path, index):
    """Correct answer, homepage-only navigation = memory-recall shortcut = FAIL."""
    root = tmp_path / f"shortcut_{index:02d}"
    seed = _seed()
    b = build_run(tmp_path, f"shortcut_{index:02d}", f"OhioMeansJobs--{index}")
    b.step("/", "goto", {})
    b.done(HONEST_ANSWERS[index])
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    verdict = run_verifier(index, root)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


@pytest.mark.parametrize("index", READ_ONLY)
def test_read_only_mutation_fails(tmp_path, index):
    """Read-only tasks must FAIL when the after-DB was mutated."""
    run_dir, initial, _after = honest_run(tmp_path, index)
    copy_db(initial, run_dir / "initial.db")
    mutate_db(initial, run_dir / "after.db", [
        ("INSERT INTO contact_messages (name, email, subject, message, created_at) "
         "VALUES ('x', 'x@test.com', 'x', 'x', '2026-09-24 12:00:00')", ()),
    ])
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_state_mismatch_fails(tmp_path, index):
    """Stateful tasks must FAIL when the agent reports success but the DB is clean."""
    run_dir, initial, _after = honest_run(tmp_path, index)
    copy_db(initial, run_dir / "initial.db")
    copy_db(initial, run_dir / "after.db")
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_wrong_delta_fails(tmp_path, index):
    """Stateful tasks must FAIL on an unrelated DB mutation (wrong delta)."""
    run_dir, initial, _after = honest_run(tmp_path, index)
    copy_db(initial, run_dir / "initial.db")
    mutate_db(initial, run_dir / "after.db", [
        ("INSERT INTO contact_messages (name, email, subject, message, created_at) "
         "VALUES ('x', 'x@test.com', 'x', 'x', '2026-09-24 12:00:00')", ()),
    ])
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


# ---------------------------------------------------------------- tamper tests
def test_task_id_mismatch_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["task_id"] = "OhioMeansJobs--17"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    copy_db(initial, run_dir / "initial.db")
    verdict = run_verifier(0, run_dir)
    assert verdict["pass"] is False


def test_offsite_url_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["steps"][0]["url"] = "https://evil.example.com/jobs/search"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    copy_db(initial, run_dir / "initial.db")
    verdict = run_verifier(0, run_dir)
    assert verdict["pass"] is False


def test_missing_screenshot_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    (run_dir / "screenshots" / "step_001.png").unlink()
    copy_db(initial, run_dir / "initial.db")
    verdict = run_verifier(0, run_dir)
    assert verdict["pass"] is False


def test_not_done_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    traj["final_answer"] = ""
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    copy_db(initial, run_dir / "initial.db")
    verdict = run_verifier(0, run_dir)
    assert verdict["pass"] is False


def test_tampered_seed_fails(tmp_path):
    """A tampered initial.db (not the frozen seed) must fail closed."""
    run_dir, initial, after = honest_run(tmp_path, 0)
    mutate_db(initial, run_dir / "initial.db", [
        ("UPDATE jobs SET title = 'HACKED' WHERE jobid = '6931551303'", ()),
    ])
    verdict = run_verifier(0, run_dir)
    assert verdict["pass"] is False

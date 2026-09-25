#!/usr/bin/env python3
"""append_rubrics.py — insert verifier_path + judge_rubric into tasks.jsonl.

Reviewer tool: reads sites/ohiomeansjobs/tasks.jsonl, and for each row
inserts ``verifier_path`` and ``judge_rubric`` keys while keeping the five
contributor keys (web_name, id, ques, web, upstream_url) BYTE-IDENTICAL —
the insertion is a pure string splice before the closing brace, so the
original bytes are never re-serialized. No ``answer`` key is ever written.
Idempotent: rows that already carry verifier_path are left untouched.
"""
from __future__ import annotations

import json
import pathlib
import sys

SITE = "ohiomeansjobs"
HERE = pathlib.Path(__file__).resolve().parent
TASKS = HERE.parent / "tasks.jsonl"

RUBRICS: dict[str, str] = {
    "OhioMeansJobs--0": (
        "FACT CHECKPOINTS: (1) The trajectory MUST search the job board for"
        "the nurse aide job in Findlay (job-title query) and open its job"
        "detail page. (2) The answer MUST report the exact job title, the"
        "job types and education level shown in its Job Summary, its job"
        "reference code, its posted date, and whether the description"
        "mentions a sign-on bonus. (3) The trajectory MUST open the"
        "Blanchard Valley Regional Health Center employer page and the"
        "answer MUST report how many total job postings it has, how many"
        "were posted that same date, and the title of the other one. (4) The"
        "trajectory MUST open that other job and the answer MUST report its"
        "salary range and whether it offers part-time. (5) Empty answer ="
        "FAIL. Reject any reference code, posted date, education level, or"
        "posting count not matching the mirror's job detail and employer"
        "pages."
    ),
    "OhioMeansJobs--1": (
        "FACT CHECKPOINTS: (1) The trajectory MUST run a nurse job search"
        "and then narrow it to the six-figure (more than $100K) salary band;"
        "two jobs must remain. (2) The answer MUST report both remaining job"
        "titles with their employers. (3) The trajectory MUST open the"
        "Findlay health-center job and the answer MUST report its posted"
        "date, job types, and industry from its Job Summary. (4) The"
        "trajectory MUST open the children's-hospital job and the answer"
        "MUST report its city, reference code, and education level. (5) The"
        "trajectory MUST narrow the nurse search to part-time schedules and"
        "the answer MUST report how many nurse jobs offer part-time work and"
        "which employers they are. (6) Empty answer = FAIL. Reject counts or"
        "facts not matching the mirror's search results and job detail"
        "pages."
    ),
    "OhioMeansJobs--2": (
        "FACT CHECKPOINTS: (1) The trajectory MUST register the account "
        "grad.2026@test.com with a password of at least 8 characters including a number. "
        "(2) The trajectory MUST create a cover letter named 'First Position Letter'. (3) "
        "The trajectory MUST find the most recently posted receptionist job in Cincinnati, "
        "open it, apply to it attaching that cover letter, and reach the confirmation. (4) "
        "The answer MUST report the job title, the employer, and the confirmation number "
        "received. (5) Empty answer = FAIL. Reject an application to any other receptionist "
        "job or a confirmation number not matching the created application."
    ),
    "OhioMeansJobs--3": (
        "FACT CHECKPOINTS: (1) The trajectory MUST log in as"
        "alice.j@test.com. (2) The trajectory MUST open the nurse"
        "practitioner opening at Cincinnati Children's Hospital Medical"
        "Center and apply to it attaching the cover letter about med-surg"
        "nursing. (3) The answer MUST report the education level listed in"
        "that job's summary. (4) The trajectory MUST open the applications"
        "list and the answer MUST report the job's reference code and the"
        "application status shown. (5) Empty answer = FAIL. Reject a status"
        "other than the one shown in My Applications, or a reference code or"
        "education level not matching the job's detail page."
    ),
    "OhioMeansJobs--4": (
        "FACT CHECKPOINTS: (1) The trajectory MUST log in as bob.c@test.com and open his "
        "saved jobs. (2) The trajectory MUST remove the saved job whose title mentions "
        "being a lift driver. (3) The trajectory MUST apply to the remaining saved job "
        "posted most recently. (4) The answer MUST report that job's exact title and city. "
        "(5) Empty answer = FAIL. Reject a title/city pair not matching the applied job's "
        "detail page."
    ),
    "OhioMeansJobs--5": (
        "FACT CHECKPOINTS: (1) The trajectory MUST log in as carol.d@test.com. (2) The "
        "trajectory MUST create a saved search named 'Remote developer roles' with daily "
        "alerts covering remote software developer positions. (3) The trajectory MUST "
        "delete her existing saved search that runs monthly. (4) The answer MUST report "
        "how many saved searches she has afterwards. (5) Empty answer = FAIL. Reject a "
        "count that does not match her saved-searches page after both changes."
    ),
    "OhioMeansJobs--6": (
        "FACT CHECKPOINTS: (1) The trajectory MUST complete the Career Profile Quiz with "
        "the described preferences (likes leading/competing/persuading; dislikes "
        "tools/machines and organizing detailed records). (2) The answer MUST report the "
        "top trait with its score and the first two suggested careers from the quiz result "
        "page. (3) The trajectory MUST search the job board for the first suggested career "
        "and the answer MUST report the title and employer of the newest matching job. (4) "
        "Empty answer = FAIL. Reject a top trait or careers not matching the quiz result "
        "page."
    ),
    "OhioMeansJobs--7": (
        "FACT CHECKPOINTS: (1) The trajectory MUST log in as"
        "david.k@test.com and open his resume, and the answer MUST report"
        "the title and employer of his current top SkillsMatch job"
        "recommendation. (2) The trajectory MUST add 'tax preparation' to"
        "his resume skills, keep the resume active, and save it. (3) The"
        "answer MUST report the titles and employers of the top three"
        "SkillsMatch recommendations now shown. (4) The trajectory MUST open"
        "the recommendation located in Dover, Ohio and the answer MUST"
        "report its posted date, job types, and education level; then open"
        "the top recommended job and report its posted date. (5) Empty"
        "answer = FAIL. Reject recommendations or job facts not matching the"
        "resume page's SkillsMatch list and the opened job detail pages."
    ),
    "OhioMeansJobs--8": (
        "FACT CHECKPOINTS: (1) The trajectory MUST use the local-help county"
        "lookup for Ottawa County, Franklin County, and Cuyahoga County. (2)"
        "The answer MUST report the Ottawa County center's name and street"
        "address, the Franklin County center's street address, and the"
        "Cuyahoga County center's street address. (3) The answer MUST report"
        "the total number of center locations the site lists. (4) The"
        "trajectory MUST search the job board for jobs within 20 miles of"
        "the city where the Cuyahoga County center is located and the answer"
        "MUST report how many jobs appear and the title and employer of the"
        "newest one. (5) Empty answer = FAIL. Reject addresses, counts, or"
        "job facts not matching the county-filtered local-help page and the"
        "radius-filtered search results."
    ),
    "OhioMeansJobs--9": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the State of Ohio"
        "jobs page and the answer MUST report how many state agencies are"
        "shown. (2) The trajectory MUST search the board for Government"
        "industry jobs sorted by date and open the most recent one. (3) The"
        "answer MUST report that job's exact title, employer, city, posted"
        "date, salary range, and whether it is full-time or part-time. (4)"
        "The trajectory MUST open the next-newest Government job and the"
        "answer MUST report its title and city. (5) The trajectory MUST"
        "visit that employer's company page and the answer MUST report how"
        "many job postings it currently lists. (6) Empty answer = FAIL."
        "Reject any fact not matching the agency roster, the opened job"
        "detail pages, or the company page."
    ),
    "OhioMeansJobs--10": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the November 2025"
        "Hire-a-Veteran news item. (2) The answer MUST report the article's"
        "publication date, the name and date of the virtual career fair"
        "hosted by MOAA, and the social media handle veterans and their"
        "families should follow. (3) The trajectory MUST filter the news"
        "list to the Veterans topic and the answer MUST report how many news"
        "items appear. (4) The trajectory MUST filter the news list to items"
        "published in 2022 and the answer MUST report how many appear and"
        "which item announced new features for veterans. (5) Empty answer ="
        "FAIL. Reject a fair name/date, handle, or count not matching the"
        "article body or the filtered news list."
    ),
    "OhioMeansJobs--11": (
        "FACT CHECKPOINTS: (1) The trajectory MUST use the Help Center"
        "without logging in. (2) The answer MUST report the exact password"
        "requirements for an OhioMeansJobs account, the email address the"
        "password reset email comes from, the help section containing the"
        "FAQ about finding scholarship information, and what the site says"
        "it aggregates over 1 million of. (3) The answer MUST report about"
        "how long the career profile quiz takes according to the job seeker"
        "help section. (4) The answer MUST report the first FAQ topic"
        "covered in the employer help section. (5) Empty answer = FAIL."
        "Reject requirements, addresses, durations, or FAQ topics not"
        "matching the help articles."
    ),
    "OhioMeansJobs--12": (
        "FACT CHECKPOINTS: (1) The trajectory MUST search for"
        "remote-friendly data analyst jobs and the answer MUST report how"
        "many match. (2) The trajectory MUST open the Senior Data Analyst"
        "job at Steris Corporation and the answer MUST report its exact"
        "title, city, posted date, job types, and the salary range mentioned"
        "in its description. (3) The trajectory MUST open the result listed"
        "immediately after it and the answer MUST report that job's title,"
        "employer, and posted date. (4) The answer MUST report the title,"
        "employer, and posted date of the newest matching result of all, and"
        "the trajectory MUST have opened it. (5) Empty answer = FAIL. Reject"
        "a count or any job fact not matching the mirror's search results"
        "and job detail pages."
    ),
    "OhioMeansJobs--13": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open both the Welder"
        "/Fitter II job at Daifuku America Corporation and the Welder L1 job"
        "at Steele Solutions. (2) The answer MUST report each job's city,"
        "posted date, salary range, and education level shown in its Job"
        "Summary, and state which lists the higher salary range. (3) The"
        "trajectory MUST find the welder job in Huber Heights and the answer"
        "MUST report its employer, posted date, education level, and the job"
        "types it offers. (4) Empty answer = FAIL. Reject any"
        "city/date/salary/education/type not matching the job detail pages."
    ),
    "OhioMeansJobs--14": (
        "FACT CHECKPOINTS: (1) The trajectory MUST search for childcare jobs"
        "with part-time schedules and the answer MUST report how many match."
        "(2) The trajectory MUST open the Mount Vernon job and the answer"
        "MUST report its exact title, employer, posted date, whether it is"
        "permanent or temporary, and the education level in its job summary."
        "(3) The answer MUST report the employer of the other part-time"
        "childcare job. (4) The trajectory MUST open the childcare teaching"
        "job in Columbus and the answer MUST report its employer, posted"
        "date, and whether it also offers part-time. (5) Empty answer ="
        "FAIL. Reject counts or facts not matching the search results and"
        "job details."
    ),
    "OhioMeansJobs--15": (
        "FACT CHECKPOINTS: (1) The trajectory MUST open the For Employers"
        "page and the answer MUST report the four statistics shown there:"
        "employers on board, active job postings, resumes available, and"
        "companies hiring. (2) The trajectory MUST open the page listing"
        "hiring resources for employers and the answer MUST report its name"
        "and the first three resources listed. (3) The trajectory MUST"
        "follow the Hire a Veteran resource and the answer MUST report how"
        "many job results it shows. (4) The answer MUST report the first FAQ"
        "topic covered in the employer help section. (5) Empty answer ="
        "FAIL. Reject numbers, resource names, or FAQ topics not matching"
        "the pages."
    ),
    "OhioMeansJobs--16": (
        "FACT CHECKPOINTS: (1) The trajectory MUST run the site search for"
        "'scholarship' and the answer MUST report how many results appear,"
        "the type of each result, and which help sections the scholarship"
        "FAQ results belong to. (2) The trajectory MUST run the site search"
        "for 'Hire-a-Veteran', open the news item among the results, and the"
        "answer MUST report its publication date and topic. (3) The"
        "trajectory MUST run the site search for 'Franklin' and the answer"
        "MUST report how many results appear, the type of each result, and"
        "the name of the job center listed. (4) Empty answer = FAIL. Reject"
        "counts, types, sections, or center names not matching the"
        "site-search results pages."
    ),
    "OhioMeansJobs--17": (
        "FACT CHECKPOINTS: (1) The trajectory MUST log in as bob.c@test.com"
        "and open his cover letters. (2) The trajectory MUST delete the"
        "cover letter about driving and create a new cover letter named"
        "'Warehouse Team Letter' with a short body about warehouse"
        "experience. (3) The answer MUST report how many cover letters he"
        "has afterwards, the name of the oldest remaining one, and the"
        "maximum number of cover letters the site says you can save. (4) The"
        "trajectory MUST open his career plan and the answer MUST report how"
        "many tasks it contains, how many are marked complete, and the"
        "deadline of the task about renewing a certification. (5) Empty"
        "answer = FAIL. Reject a count, oldest-letter name, maximum, or"
        "career-plan fact not matching the pages after both changes."
    ),
}


def main() -> None:
    lines = TASKS.read_text(encoding="utf-8").splitlines(keepends=True)
    out_lines = []
    inserted = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue
        row = json.loads(stripped)
        task_id = row.get("id", "")
        if row.get("verifier_path") or task_id not in RUBRICS:
            out_lines.append(line)
            continue
        verifier_path = f"sites/{SITE}/verify/verify_{task_id.split('--')[1]}.py"
        # pure string splice before the closing brace: contributor bytes untouched
        close = line.rstrip("\n").rstrip()
        assert close.endswith("}"), f"unexpected tasks.jsonl line: {line[:80]!r}"
        payload = close[:-1].rstrip()
        if not payload.endswith(","):
            payload += ","
        addition = (f' "verifier_path": {json.dumps(verifier_path)},'
                    f' "judge_rubric": {json.dumps(RUBRICS[task_id])} ')
        new_line = payload + addition + "}\n"
        # sanity: original 5 keys byte-identical inside the new line (the contributor rows
        # store non-ASCII as \uXXXX escapes, so accept either encoding of the same value)
        for key in ("web_name", "id", "ques", "web", "upstream_url"):
            plain = json.dumps(row[key], ensure_ascii=False)[1:-1]
            escaped = json.dumps(row[key], ensure_ascii=True)[1:-1]
            assert plain in new_line or escaped in new_line, key
        assert "answer" not in new_line.lower() or '"answer"' not in new_line
        out_lines.append(new_line)
        inserted += 1
    TASKS.write_text("".join(out_lines), encoding="utf-8")
    print(f"[rubrics] inserted verifier_path + judge_rubric into {inserted} row(s)")
    # verify: every row parses, keys ordered, no answer key
    for line in out_lines:
        row = json.loads(line)
        assert set(row) == {"web_name", "id", "ques", "web", "upstream_url",
                            "verifier_path", "judge_rubric"}, sorted(row)
        assert "answer" not in row


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Append the reviewer grading keys (verifier_path + judge_rubric) to tasks.jsonl.

The five contributor keys (web_name, id, ques, web, upstream_url) stay byte-identical:
the two new keys are string-inserted before each line's closing brace, so the original
JSON bytes are untouched and no answer key is ever written into the file.

Usage: python3 append_rubrics.py   (idempotent: skips lines that already carry the keys)
"""
from __future__ import annotations

import json
from pathlib import Path

TASKS = Path(__file__).resolve().parents[1] / "tasks.jsonl"

RUBRICS = {
    0: "FACT CHECKPOINTS: (1) The trajectory MUST open the Case Studies hub with the "
       "Product filter set to Parchment Services and then open the Helena Public Schools "
       "case study detail page. (2) The answer MUST report the state, the number of "
       "students, and the Parchment adoption year exactly as shown in the case study's "
       "stat bar. (3) Empty answer = FAIL. Reject values taken from any other case study "
       "or read off a listing card instead of the stat bar.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST open the case study 'Staying the Course "
       "for Better Benchmarks in Madison County' from the Case Studies hub (browse or "
       "search). (2) The answer MUST report how many students the district serves and the "
       "rating its 11 elementary schools earned from the state of Mississippi, as stated "
       "in the case study. (3) Empty answer = FAIL. Reject counts or ratings taken from "
       "any other case study.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST run the site search for 'screen time' "
       "and open the blog post about minute caps in classrooms. (2) The answer MUST report "
       "the author's name and the publication date exactly as shown on the post. "
       "(3) Empty answer = FAIL. Reject an author or date taken from any other post or "
       "from a search-results card.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST open the On-Demand Webinars hub with the "
       "Org Type filter set to Business. (2) The answer MUST report how many results appear "
       "and the exact title of the first webinar in the filtered list. (3) Empty answer = "
       "FAIL. Reject a count or title taken from the unfiltered hub.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST open the Edison High School case study "
       "('How Edison High School Turns Fees into Scholarships'). (2) The answer MUST "
       "report the state, the number of students, and the adopted product with its year, "
       "exactly as shown in the stat bar. (3) Empty answer = FAIL. Reject values taken "
       "from any other case study.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST open BOTH case studies ('Staying the "
       "Course for Better Benchmarks in Madison County' and 'From Average to Excellent "
       "with Reliable Data at Kershaw County'). (2) The answer MUST report both student "
       "counts from the two stat bars and which district serves more students (and by "
       "roughly how many). (3) Empty answer = FAIL. Reject an answer that names only one "
       "district's count.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST open the Events page with the Event Type "
       "filter set to Webinar. (2) The answer MUST report the title and date of the webinar "
       "about Canvas tiers covering AI, analytics, and a simplified LMS. (3) Empty answer "
       "= FAIL. Reject the title or date of any other event.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST open the homepage (the InstructureCon "
       "banner is the task surface; the events listing carries no InstructureCon row). "
       "(2) The answer MUST report the conference's name and its dates as shown on the "
       "homepage banner. (3) Empty answer = FAIL. Reject conference facts that do not "
       "match the banner.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST open the Careers page and filter the "
       "open positions by Department Engineering. (2) The answer MUST report how many "
       "engineering positions are open after the filter and the exact title of the first "
       "one listed. (3) Empty answer = FAIL. Reject a count or title taken from the "
       "unfiltered board.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST open the Careers page and locate the "
       "role 'Builder, Instructure Foundry'. (2) The answer MUST report its salary range, "
       "employment type, and location exactly as shown on the board (the employment type "
       "may be proven with the Employment Type filter). (3) Empty answer = FAIL. Reject "
       "compensation or location values from any other role.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST open the Careers page and filter by "
        "Location Mexico. (2) The answer MUST report the exact title of the customer "
        "success role, its department, and the compensation range shown. (3) Empty answer "
        "= FAIL. Reject the title, department, or compensation of any non-customer-success "
        "role.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST open the About > Leadership page and "
        "the CEO's profile modal. (2) The answer MUST name the Chief Learning Officer and "
        "report at least one company listed in Steve Daly's bio as a prior leadership "
        "role. (3) Empty answer = FAIL. Reject companies not listed in the on-page bio.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST open the About > Leadership page. "
        "(2) The answer MUST report the Chief Financial Officer's full name as displayed "
        "on their leadership card. (3) Empty answer = FAIL. Reject any other executive's "
        "name.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST open the Newsroom (/news). (2) The "
        "answer MUST report the publication date of the article from The Ed Up Experience "
        "Podcast about what educators need to know about AI and the Instructure executive "
        "quoted as its spokesperson. (3) Empty answer = FAIL. Reject a date or spokesperson "
        "attached to any other outlet's article.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST open the Press Releases page and the "
        "press release announcing Stephan Geering's appointment as Chief Privacy Officer. "
        "(2) The answer MUST report the exact date of the announcement and the location "
        "given in the release dateline. (3) Empty answer = FAIL. Reject a date or dateline "
        "taken from any other release.",
    15: "FACT CHECKPOINTS: (1) The trajectory MUST open the Newsroom (/news) — the Region "
        "filter control is inert in this mirror, so reading the newsroom list is the "
        "documented path. (2) The answer MUST report the title of the Educacion 3.0 "
        "article and its spokesperson. (3) Empty answer = FAIL. Reject an article from "
        "any other outlet.",
    16: "FACT CHECKPOINTS: (1) The trajectory MUST open the Canvas Support FAQ page and "
        "expand the password-reset answer. (2) The answer MUST list the steps to reset "
        "your password when you set up your own Canvas account as described by the FAQ "
        "(the Forgot Password link, the Request Password button, the emailed reset "
        "prompt, returning to the login screen). (3) Empty answer = FAIL. Reject steps "
        "invented outside the on-page answer.",
    17: "FACT CHECKPOINTS: (1) The trajectory MUST open the Canvas Support FAQ page and "
        "expand the Free Canvas Account answers. (2) The answer MUST state the limitation "
        "of a Free Account the FAQ mentions and whether non-teachers can use it, matching "
        "the on-page wording. (3) Empty answer = FAIL. Reject a limitation or permission "
        "not stated on the page.",
    18: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "alice.j@test.com, open Saved Resources, remove the Madison County case study "
        "from the saved list, and the removal MUST be the only database change. (2) The "
        "answer MUST report how many resources were saved, the case study title in the "
        "list, and the removal confirmation message. (3) Empty answer = FAIL. Reject an "
        "answer that removes a different resource or claims success without the row "
        "actually being removed.",
    19: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "bob.c@test.com and open the account page. (2) The answer MUST report the exact "
        "title of the webinar the account is registered for. (3) Empty answer = FAIL. "
        "Reject the title of any unregistered webinar.",
    20: "FACT CHECKPOINTS: (1) The trajectory MUST register a new @test.com account, open "
        "the University of Central Florida admissions case study, save it, and confirm it "
        "under Saved Resources; the new user row plus the one saved row MUST be the only "
        "database changes. (2) The answer MUST report the number of transcripts the "
        "university processes annually as shown in the stat bar and confirm the save. "
        "(3) Empty answer = FAIL. Reject an answer without the on-page transcript count "
        "or with an unregistered/unpersisted save.",
    21: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "david.k@test.com, update the profile (state Colorado, job title 'Director of "
        "Learning'), and the profile edit MUST be the only database change. (2) The "
        "answer MUST report the confirmation message shown after saving. (3) Empty "
        "answer = FAIL. Reject an answer that claims an update the database does not "
        "show.",
    22: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "carol.d@test.com, register for the on-demand webinar 'Moving from Canvas Core to "
        "Canvas Plus' from its detail page, confirm it under the account, and that one "
        "registration row MUST be the only database change. (2) The answer MUST report "
        "the registration confirmation message text. (3) Empty answer = FAIL. Reject an "
        "answer that claims registration without the database row.",
    23: "FACT CHECKPOINTS: (1) The trajectory MUST open the Request a Demo page, submit "
        "the form with the specified identity (Jordan Lee / jordan.lee@test.com / Summit "
        "Public Schools / K12 / sales), and exactly one demo request row MUST be written. "
        "(2) The answer MUST report the success message shown after submission. (3) Empty "
        "answer = FAIL. Reject an answer without the on-page success message or with a "
        "row that does not carry the submitted identity.",
    24: "FACT CHECKPOINTS: (1) The trajectory MUST open the Contact Us page, submit the "
        "form with the specified identity (Maria Chen / maria.chen@test.com / Northgate "
        "University / Higher Ed / General Inquiry), and exactly one contact message row "
        "MUST be written. (2) The answer MUST report the success message shown after "
        "submission. (3) Empty answer = FAIL. Reject an answer without the on-page "
        "success message or with a row that does not carry the submitted identity.",
    25: "FACT CHECKPOINTS: (1) The trajectory MUST open the Edison High School case study, "
        "click Download, submit the gated download form with the specified identity "
        "(Priya Nair / priya.nair@test.com / Edison High School / K12 / teacher product "
        "information), and exactly one download demo request row MUST be written. (2) The "
        "answer MUST report the success confirmation shown. (3) Empty answer = FAIL. "
        "Reject an answer without the on-page confirmation or with a misattributed row.",
    26: "FACT CHECKPOINTS: (1) The trajectory MUST open the homepage statistics section "
        "('Welcome to the most-visited education website in the world'). (2) The answer "
        "MUST report the exact number of assessment scores said to be created via Mastery "
        "and the number of K-12 schools said to love Parchment, as displayed on the stat "
        "cards. (3) Empty answer = FAIL. Reject numbers not shown on the homepage stat "
        "cards.",
    27: "FACT CHECKPOINTS: (1) The trajectory MUST open the Blogs hub with the Topic "
        "filter set to Artificial Intelligence. (2) The answer MUST report how many blog "
        "posts match the filter and the title of the post about AI literacy, cognitive "
        "offloading, and student voice in the classroom. (3) Empty answer = FAIL. Reject "
        "a count or title taken from the unfiltered hub or any other post.",
    28: "FACT CHECKPOINTS: (1) The trajectory MUST open the Research hub and the '2026 "
        "Canvas LMS Educator Impact Study' detail page. (2) The answer MUST report the "
        "org types the study covers as tagged on the page and one other research report "
        "title in the Research hub that mentions South Carolina. (3) Empty answer = FAIL. "
        "Reject tags or titles not present in the hub or on the study page.",
    29: "FACT CHECKPOINTS: (1) The trajectory MUST run the site search for 'Parchment' "
        "and open the case study about digitizing and disaster-proofing K-12 records at "
        "Helena Public Schools. (2) The answer MUST report the state and the adoption year "
        "shown in that case study's stat bar and the total number of search results for "
        "'Parchment'. (3) Empty answer = FAIL. Reject a result count read anywhere other "
        "than the search page or stat values taken from another case study.",
}


def main() -> None:
    lines = TASKS.read_text(encoding="utf-8").splitlines(keepends=False)
    out = []
    changed = 0
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        n = int(row["id"].split("--")[-1])
        if "verifier_path" in row or "judge_rubric" in row:
            out.append(line)
            continue
        assert line.rstrip().endswith("}"), line[-40:]
        addition = (f', "verifier_path": "sites/instructure/verify/verify_{n}.py", '
                    f'"judge_rubric": {json.dumps(RUBRICS[n], ensure_ascii=False)}')
        new_line = line.rstrip()[:-1] + addition + "}"
        # sanity: still valid JSON, five contributor keys untouched byte-for-byte
        parsed = json.loads(new_line)
        assert parsed["id"] == row["id"]
        assert new_line.startswith(line.rstrip()[:-1]) or new_line[: len(line) - 2] == line.rstrip()[:-2]
        out.append(new_line)
        changed += 1
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended grading keys to {changed} task rows in {TASKS}")


if __name__ == "__main__":
    main()

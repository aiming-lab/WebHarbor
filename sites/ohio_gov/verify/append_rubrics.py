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
    0: "FACT CHECKPOINTS: (1) The trajectory MUST open the Licenses & Permits directory "
       "and search it for the acupuncturists entry. (2) The trajectory MUST open the "
       "State Directory and search it for the issuing agency named in that license row. "
       "(3) The trajectory MUST filter the Licenses & Permits directory by that issuing "
       "agency (the agency filter) and read the filtered total. (4) The answer MUST report "
       "the issuing state agency, that agency's website as shown in the license row, the "
       "contact method the directory lists for license questions, how many social media "
       "links the agency's State Directory entry shows, and how many licenses the agency "
       "issues in total. (5) Empty answer = FAIL. Reject values not taken from the license "
       "rows, the agency's directory entry, and the agency-filtered directory total.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST use the State of Ohio Phone Search "
       "with the last name Smith, including at least one agency-scoped search. (2) The "
       "trajectory MUST also search the phone directory for all listings with the exact "
       "first and last name given in the task. (3) The answer MUST report the phone number "
       "of the Aaron Smith at the Environmental Protection Agency, the total number of "
       "exact-name listings the search returns, which agency each of those listings works "
       "for, and the phone number of the Aaron Smith at the Lottery Commission. (4) Empty "
       "answer = FAIL. Reject phone numbers, counts, or agency names not shown by the "
       "phone search results.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST open the Home Energy Assistance "
       "Program resource page, the Food Assistance resource page, and the Ohio "
       "Assistant asked about help paying utility bills. (2) The answer MUST report "
       "where the HEAP one-time payment goes, what the food assistance program is "
       "also known as, which card the benefits arrive on, and the title of the first "
       "resource the assistant suggests. (3) Empty answer = FAIL. Reject facts not "
       "taken from those three surfaces.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST open the news section and the "
       "article about helping kids go back to school healthy, plus the news item about "
       "school transportation safety and the article about the Team Tressel Fitness "
       "Challenge. (2) The answer MUST report the publishing agency and date of the "
       "back-to-school article, what its medical director says students should "
       "prioritize, which office published the transportation safety reminder, which "
       "office announced the Team Tressel challenge, and by how much that article says "
       "student participation has increased since the challenge launched. (3) Empty "
       "answer = FAIL. Reject facts not taken from the three news pages.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST open the Dolly Parton Day news "
       "article, the resource page of the Ohio program that mails a free book each "
       "month to children under age 5, and the Assistance Questions FAQ category. "
       "(2) The answer MUST report the Dolly Parton Day date, the governor who "
       "proclaimed it, the program's name, and what the FAQ says about getting "
       "immediate help with food. (3) Empty answer = FAIL. Reject facts not taken from "
       "those pages.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST open all three of the task's Ohio "
       "Facts pages in the Government section: the geography page, the state symbols "
       "page, and the plants and animals page. (2) The answer MUST report, from the "
       "geography page, the town that marks the center point of the state, the state's "
       "approximate area in square miles, and how many rivers and streams it says Ohio "
       "has; from the state symbols page, what the coat of arms shows on the left and "
       "on the right; and, from the plants and animals page, how many types of trees "
       "grow in Ohio, how many insect species you'll find, and how many plant species "
       "it lists. (3) Empty answer = FAIL. An answer produced without opening all "
       "three Ohio Facts pages is a knowledge shortcut = FAIL.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
       "alice.j@test.com. (2) The trajectory MUST remove the College Credit Plus "
       "resource from the saved list and save the Weather Safety resource from its "
       "resource page. (3) The answer MUST report how many saved resources the account "
       "shows afterwards and the titles of the first and last resources in the saved "
       "list. (4) Empty answer = FAIL. Reject a saved list that still contains College "
       "Credit Plus or lacks Weather Safety.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST create the OHID account with the "
       "given username, email and password on the register page. (2) The trajectory "
       "MUST edit the profile so the display name is 'Maria Gonzalez' and the mailing "
       "address is 250 High St, Columbus, Ohio 43215, then confirm both in account "
       "settings. (3) The answer MUST report the username and the address shown. "
       "(4) Empty answer = FAIL. Reject an account whose profile does not carry the "
       "exact display name and mailing address.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST open the 2026 Ohio Travel Guide page "
       "and submit BOTH orders without logging in: the Standard print order for Rosa "
       "Parks at 12 Elm Court, Toledo, Ohio 43604 and the Large print order for Sam "
       "Rivers at 8 Harbor View Dr, Sandusky, Ohio 44870. (2) The answer MUST quote both "
       "confirmation messages and report the three ways the home page banner says you "
       "can get the travel guide. (3) Empty answer = FAIL. Reject orders placed while "
       "signed in or with any other format, name, or address.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST open the consumer complaint / "
       "report-scam form and submit it with scam type 'Romance scam', amount 450, and a "
       "short description, without logging in. (2) The answer MUST quote the "
       "confirmation message and report the dedicated romance scam hotline number "
       "shown on that page. (3) Empty answer = FAIL. Reject a complaint with any other "
       "scam type or amount.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "bob.c@test.com. (2) The trajectory MUST open the Alerts page, read the alert "
        "about the Ohio Benefits self-service portal, and subscribe to BOTH 'Unemployment "
        "system' and 'Outage notifications' alerts on the Alerts page, each using the "
        "account's own email address. (3) The answer MUST report during which hours the "
        "Ohio Benefits portal will be unavailable, how many alert subscriptions the "
        "account page lists afterwards, and the title of the alert about BMV online "
        "services. (4) Empty answer = FAIL. Reject subscriptions made with any other "
        "email address, duplicate subscription rows, or any subscription count other "
        "than what the account page shows after the two subscriptions.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST open the Government Questions, New "
        "Resident Questions, and Driving Questions FAQ categories in the Help Center. "
        "(2) The answer MUST report what the Government Questions answer says the Bureau "
        "of Vital Statistics can provide, which commission helps residents search Ohio's "
        "laws, and how many questions that category lists; how many questions the New "
        "Resident Questions category lists, how long new residents have to transfer an "
        "out-of-state driver license and vehicle registration, and where that answer "
        "says they can register to vote; and which department the Driving Questions "
        "answer says helps you find your local BMV office. (3) Empty answer = FAIL. "
        "Reject question counts or facts that do not match the three category pages.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST search Ohio.gov for 'tax', open the "
        "Licenses tab and the FAQs tab of the results, open the FAQs tab's first "
        "question, and open the Sales and Use Tax resource. (2) The answer MUST report "
        "how many Resources results and how many FAQs results the search reports, the "
        "name of the first license result with its issuing agency, what the first FAQ's "
        "answer says you can do with the Department of Taxation's online services, and "
        "one thing the Sales and Use Tax resource says the tax applies to. (3) Empty "
        "answer = FAIL. Reject counts or names not shown on the search tabs.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST open the Top Services topic hub in "
        "the Residents section, the Unclaimed Funds resource, and the Money & Finance "
        "topic hub under Home & Community. (2) The answer MUST report how many resources "
        "the Top Services hub lists, the first three in the list, which department helps "
        "Ohioans claim funds held in their names, two examples of what unclaimed funds "
        "include, how many resources the Money & Finance hub lists, and the title of "
        "its first resource. (3) Empty answer = FAIL. Reject examples not listed on the "
        "Unclaimed Funds page or counts that do not match the hub pages.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST ask the Ohio Assistant 'how do I "
        "replace a lost driver license', open the Driver Licenses resource, open the "
        "Driver Training resource, and look the Bureau of Motor Vehicles up in the State "
        "Directory. (2) The answer MUST report the titles of the resources the assistant "
        "returns, what the Driver Licenses resource says an Ohio driver license also "
        "serves as, what the license can be used for with proper documents, which office "
        "the Driver Training resource says provides driver training information, and the "
        "contact method the State Directory lists for the BMV. (3) Empty answer = FAIL. "
        "Reject titles or contact methods not shown on those surfaces.",
    15: "FACT CHECKPOINTS: (1) The trajectory MUST search the State Directory for the "
        "Accountancy Board, for 'Lottery', and for 'Taxation'. (2) The answer MUST "
        "report the Accountancy Board's website, its contact method, and which social "
        "networks its entry lists; the full agency name the Lottery search returns with "
        "its contact method; and which social networks the Taxation entry lists with its "
        "contact method. (3) Empty answer = FAIL. Reject values not shown by the State "
        "Directory entries.",
    16: "FACT CHECKPOINTS: (1) The trajectory MUST open the news section filtered by "
        "the Ohio Department of Natural Resources, the fall hunting seasons article, "
        "and the article about buying Ohio-grown trees online. (2) The answer MUST "
        "report how many articles the filter shows, their titles, the two hunting "
        "seasons that start September 1, what hunters are reminded to check, the fall "
        "hunting article's publication date, which city the Buckeye State Tree Nursery "
        "is in, and the two ways customers can receive their orders. (3) Empty answer = "
        "FAIL. Reject seasons, dates, or delivery ways not stated in the two ODNR "
        "articles.",
    17: "FACT CHECKPOINTS: (1) The trajectory MUST open the news item about adding "
        "your Ohio ID to Google Wallet, the reminder about using food assistance "
        "benefits at farmers' markets, and the news marking September as Ohio "
        "Preparedness Month. (2) The answer MUST report the announcing agency and date "
        "of the Google Wallet item, what a user can review when an ID is displayed, "
        "which signs to look for at participating markets, which agency published the "
        "preparedness item, and what its executive director says families should do to "
        "be prepared. (3) Empty answer = FAIL. Reject facts not taken from the three "
        "news pages.",
    18: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "carol.d@test.com and update the profile phone number to (513) 555-0200 and "
        "the city to Cleveland, keeping every other detail. (2) The answer MUST report "
        "the new phone and city as shown in account settings, how many saved resources "
        "the account shows, and the title of the most recent consumer complaint if "
        "any exists. (3) Empty answer = FAIL. Reject a profile where any field other "
        "than phone and city changed.",
    19: "FACT CHECKPOINTS: (1) The trajectory MUST look up the barbers, auctioneer, "
        "and notary public entries in the Licenses & Permits directory and open the "
        "Professional License Questions FAQ category. (2) The answer MUST report which "
        "agency or board issues each of those three licenses and the website the FAQ "
        "answer says lets you verify someone's professional license. (3) Empty answer = "
        "FAIL. Reject boards or websites not shown in the license rows and the FAQ "
        "answer.",
    20: "FACT CHECKPOINTS: (1) The trajectory MUST search Ohio.gov for 'hunting', open "
        "the resource about buying hunting and fishing licenses, and open the Hunting "
        "& Fishing Questions FAQ category. (2) The answer MUST report how many Resources "
        "results the search finds, what the resource lets you do, how many questions the "
        "category lists, the two places the answer says you can buy licenses and permits, "
        "which division's listing of season dates the hunting-season answer points to, "
        "and which advisory the answer about safe-to-eat fish names. (3) Empty answer = "
        "FAIL. Reject places, divisions, or advisories not named in the FAQ answers.",
}


def main() -> None:
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    out = []
    changed = 0
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        if "verifier_path" in row or "judge_rubric" in row:
            out.append(line)
            continue
        n = int(row["id"].split("--")[-1])
        verifier = f"sites/ohio_gov/verify/verify_{n}.py"
        rubric = RUBRICS[n]
        # insert the two keys before the closing brace, preserving the original bytes
        assert line.rstrip().endswith("}")
        body = line.rstrip()[:-1].rstrip()  # drop the closing brace
        assert body.endswith('"')           # ... and ends inside the last string value
        new_line = (body
                    + f', "verifier_path": {json.dumps(verifier)}'
                    + f', "judge_rubric": {json.dumps(rubric)}'
                    + '}')
        # sanity: parses and keeps the original five keys byte-identical in value
        parsed = json.loads(new_line)
        assert parsed["verifier_path"] == verifier
        assert parsed["judge_rubric"] == rubric
        for key in ("web_name", "id", "ques", "web", "upstream_url"):
            assert parsed[key] == row[key], key
        assert "answer" not in parsed
        out.append(new_line)
        changed += 1
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended grading keys to {changed} rows (total {len(out)})")


if __name__ == "__main__":
    main()

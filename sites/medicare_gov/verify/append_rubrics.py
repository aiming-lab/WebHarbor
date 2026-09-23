#!/usr/bin/env python3
"""append_rubrics.py — extend tasks.jsonl with the grading-contract keys (15 redesigned tasks).

Round-2 depth-review contract sync: each contributor row (5 keys: web_name, id,
ques, web, upstream_url) gains exactly two keys, in order: verifier_path
(relative path from the repo root to the task's deterministic verifier) and
judge_rubric (English FACT CHECKPOINTS stating the RULES the judge verifies:
which pages must be opened, which facts must appear, that an empty answer is a
FAIL — never the answers themselves).

The original 5-key prefix is preserved byte-for-byte: the script appends two
well-formed JSON members after the existing ones and rewrites the file only if
every row's original bytes round-trip as the new row's prefix.
"""
from __future__ import annotations

import json
from pathlib import Path

TASKS = Path(__file__).resolve().parents[1] / "tasks.jsonl"

VERIFIER_PATH = {n: f"sites/medicare_gov/verify/verify_{n}.py" for n in range(15)}

RUBRICS = {
    0: ("FACT CHECKPOINTS: The agent must use the coverage search and open the Acupuncture, "
        "Glaucoma screenings, and Shingles vaccines coverage detail pages. The answer must "
        "state all five facts: the number of acupuncture treatments covered per 90 days for "
        "chronic low back pain, the maximum total in a 12-month period if he shows "
        "improvement, how long the pain must have lasted to count as chronic, how often "
        "someone at high risk can get a glaucoma screening, and what he would pay for the "
        "shingles vaccine with Part D. An answer missing any part, or an empty answer, is a "
        "FAIL."),
    1: ("FACT CHECKPOINTS: The agent must open the Medicare costs page and the Skilled "
        "nursing facility care coverage detail page. The answer must state the 2026 Part A "
        "deductible per inpatient hospital benefit period, the per-day cost for inpatient "
        "hospital days 1-60, the daily coinsurance for skilled nursing facility days 21-100, "
        "and the SNF rules: how many inpatient hospital days qualify him, whether an ACO "
        "waiver can replace that requirement, how many SNF days a benefit period covers, and "
        "whether the Part A deductible is charged again for SNF care in the same period. An "
        "answer missing any part, or an empty answer, is a FAIL."),
    2: ("FACT CHECKPOINTS: The agent must search doctors & clinicians near Boston, MA with "
        "the keyword 'family practice' and open the first (closest) result, then look up "
        "Beth Israel Deaconess Medical Center among hospitals near Boston, MA. The answer "
        "must state how many results the doctor search listed, the name and specialty of the "
        "first (closest) result, and for the hospital: whether it has emergency services, "
        "its ownership type, and how many patient experience measures it reports. An answer "
        "missing any part, or an empty answer, is a FAIL."),
    3: ("FACT CHECKPOINTS: The agent must search hospitals near Springfield, IL and compare "
        "St Johns Hospital and Memorial Medical Center, then search dialysis facilities "
        "near Houston, TX for the facility with 48 stations and a late shift. The answer "
        "must name the hospital with the higher overall rating and state that rating, and "
        "report the dialysis facility's name and phone number. An answer missing any part, "
        "or an empty answer, is a FAIL."),
    4: ("FACT CHECKPOINTS: The agent must search nursing homes near Denver, CO in the "
        "provider directory and count the 5-star overall ratings, then search the medical "
        "equipment & suppliers directory for ZIP 80204 with keyword 'walkers'. The answer "
        "must state how many nursing homes have a 5-star overall rating, name two of them, "
        "and report the name and phone number of the closest walker supplier in the "
        "results. An answer missing any part, or an empty answer, is a FAIL."),
    5: ("FACT CHECKPOINTS: The agent must use the plan finder for ZIP 62701: Medicare "
        "Advantage plans, Medicare drug plans, and the Blue Cross Medicare Classic (PPO) "
        "plan card. The answer must list the full name of every Medicare Advantage plan "
        "with a $0 monthly premium (a list that includes a non-zero-premium plan or is "
        "incomplete is a FAIL), name the drug plan with the higher star rating and state "
        "that rating, and report the Blue Cross plan's monthly premium and in-network "
        "out-of-pocket limit. An answer missing any part, or an empty answer, is a FAIL."),
    6: ("FACT CHECKPOINTS: The agent must use the plan finder for ZIP 80204 (Medicare "
        "Advantage plans) to identify the 5-star plan, then, without logging in, order 2 "
        "print copies of the Medicare & You 2027 handbook in Standard Print format shipped "
        "to 12 Elm Court, Denver, CO 80204 and reach the on-site order confirmation. The "
        "answer must state the plan's name and monthly premium and confirm the order went "
        "through. An answer missing any part, an empty answer, or an answer without the "
        "on-site order, is a FAIL."),
    7: ("FACT CHECKPOINTS: The agent must log in with the demo account (alice.j@test.com / "
        "TestPass123!), open the screening colonoscopy and blood sugar test strips claim "
        "details, and check the message center. The answer must state what Medicare paid "
        "and what the person may be billed for each of the two claims, and the subject of "
        "the newest unread message. An answer missing any part, or an empty answer, is a "
        "FAIL."),
    8: ("FACT CHECKPOINTS: The agent must open the Reporting Medicare fraud & abuse page, "
        "then log in with the demo account (bob.c@test.com / TestPass123!), pay the due "
        "Part B premium with the default payment method, and update the account mailing "
        "address to 789 Oak Street, Oak Park, IL 60302 on-site. The answer must state the "
        "I-MEDIC phone number, the amount paid, and the new address. An answer missing any "
        "part, an empty answer, or an answer without the on-site payment and address "
        "change, is a FAIL."),
    9: ("FACT CHECKPOINTS: The agent must log in with the demo account (alice.j@test.com / "
        "TestPass123!), update the mailing address to 45 Meadow Lane, Buffalo Grove, IL "
        "60089 and confirm it shows in account settings, then order a free replacement "
        "Medicare card with 'My card was lost' as the reason on-site. The answer must "
        "report the Medicare Number on her current card and the replacement card status. "
        "An answer missing any part, an empty answer, or an answer without the on-site "
        "address change and replacement order, is a FAIL."),
    10: ("FACT CHECKPOINTS: The agent must log in with the demo account (alice.j@test.com / "
         "TestPass123!) and place two on-site publication orders shipped to the address on "
         "file: 2 copies of Medicare Coverage of Cancer Treatment Services in Standard "
         "Print format and 1 copy of Choosing a Medigap Policy in Large Print format. The "
         "answer must report both product numbers and the shipping address shown on the "
         "confirmation pages. An answer missing any part, an empty answer, or an answer "
         "without both confirmed on-site orders, is a FAIL."),
    11: ("FACT CHECKPOINTS: The agent must use the publications search without logging in "
         "to find Choosing a Medigap Policy, browse the Rights and protections category, "
         "and place an anonymous on-site order for 1 Standard Print copy shipped to 302 W "
         "Edwards St, Springfield, IL 62704. The answer must state the publication's "
         "product number and category, how many products the category lists with one "
         "title, and confirm the order went through. An answer missing any part, an empty "
         "answer, or an answer without the on-site order, is a FAIL."),
    12: ("FACT CHECKPOINTS: The agent must log in with the demo account (alice.j@test.com / "
         "TestPass123!) and inspect the message center (including opening the newest "
         "message), the premiums page, and account settings. The answer must state how "
         "many unread messages there are, the newest message's subject and the enrollment "
         "dates its body mentions, the amount and due date of the current due Part B "
         "premium bill, and the Medicare Number shown in account settings. An answer "
         "missing any part, or an empty answer, is a FAIL."),
    13: ("FACT CHECKPOINTS: The agent must open the Hospice care coverage detail page and "
         "search hospice care near Houston, TX in the provider directory, opening the "
         "first hospice listed. The answer must state which part of Medicare is required, "
         "who must certify that he is terminally ill, what he pays for hospice care from "
         "a Medicare-approved hospice, and the first hospice's name and phone number. An "
         "answer missing any part, or an empty answer, is a FAIL."),
    14: ("FACT CHECKPOINTS: The agent must open the Get started with Medicare page, the "
         "Medicare costs page, the Talk to someone page, and the Shingles vaccines "
         "coverage detail page. The answer must state whether he gets Medicare "
         "automatically or must sign up, the 2026 standard Part B monthly premium and "
         "how often it is paid, the Part A deductible per benefit period, Medicare's TTY "
         "number, which agency handles Part A/B sign-up, and what he would pay for the "
         "shingles vaccine with Part D. An answer missing any part, or an empty answer, "
         "is a FAIL."),
}


def main() -> None:
    original = TASKS.read_bytes()
    lines = original.splitlines(keepends=True)
    assert len(lines) == 15, f"expected 15 rows, got {len(lines)}"
    out = []
    for n, line in enumerate(lines):
        row = json.loads(line)
        assert list(row.keys()) == ["web_name", "id", "ques", "web", "upstream_url"], \
            f"row {n}: unexpected keys {list(row.keys())}"
        assert "answer" not in row, f"row {n}: answer key must not exist"
        assert row["id"] == f"Medicare.gov--{n}", f"row {n}: unexpected id {row['id']}"
        extended = dict(row)
        extended["verifier_path"] = VERIFIER_PATH[n]
        extended["judge_rubric"] = RUBRICS[n]
        new_line = json.dumps(extended, ensure_ascii=False,
                              separators=(", ", ": ")) + "\n"
        # byte-prefix contract: the original 5 members' bytes are the new line's prefix.
        canonical = json.dumps(row, ensure_ascii=False, separators=(", ", ": "))
        assert line.decode().rstrip("\n") == canonical, f"row {n}: original bytes differ from canonical"
        assert new_line.startswith(canonical[:-1] + ", "), f"row {n}: byte-prefix contract violated"
        assert new_line.rstrip("\n").endswith("}"), f"row {n}: malformed extension"
        out.append(new_line)
    TASKS.write_text("".join(out))
    # round-trip audit
    for n, line in enumerate(TASKS.read_text().splitlines()):
        row = json.loads(line)
        assert list(row.keys()) == ["web_name", "id", "ques", "web", "upstream_url",
                                    "verifier_path", "judge_rubric"], f"row {n} keys"
        assert row["verifier_path"] == VERIFIER_PATH[n]
        assert row["judge_rubric"] == RUBRICS[n]
        assert "answer" not in row
    print("tasks.jsonl extended to 7 keys x 15 rows; 5-key byte prefix preserved")


if __name__ == "__main__":
    main()

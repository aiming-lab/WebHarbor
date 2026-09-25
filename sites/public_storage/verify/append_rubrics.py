#!/usr/bin/env python3
"""Reviewer step: append verifier_path + judge_rubric to each tasks.jsonl row.

The contributor's five definition keys (web_name, id, ques, web,
upstream_url) must stay BYTE-IDENTICAL: this script rewrites each line as
<original line bytes> + '\t' + <two new JSON keys>. No answer values appear
in the rubrics — they state the rules (which pages must be opened, which
facts must appear, what fails), safe for the agent to see.
"""
import json
import pathlib

SITE = pathlib.Path(__file__).resolve().parents[1]
TASKS = SITE / "tasks.jsonl"

RUBRICS = {
    0: ("The agent must run the ZIP 78704 search on the mirror and open the "
        "facility page of the cheapest 10'x10' within 5 miles before holding. "
        "The final answer must contain (a) a PS-format reservation code for a "
        "hold actually placed under the task's name and email with the "
        "required move-in date, (b) the holding facility's street address, "
        "and (c) the held unit's online monthly rate. A code that does not "
        "match the database reservation, a different unit, address or rate, "
        "or an empty answer is a FAIL."),
    1: ("The agent must open the size-guide hub (comparison chart) and the "
        "Denver search results, and the facility page of the reported unit. "
        "The final answer must state (a) which comparison-chart unit size "
        "fits a three-bedroom home, (b) that size's square footage, (c) the "
        "street address of the Denver facility with the cheapest enclosed "
        "indoor 10'x20' (not a vehicle parking space), and (d) that unit's "
        "online rate. An outside/drive-up unit, a vehicle space, wrong chart "
        "values, or an empty answer is a FAIL."),
    2: ("The agent must open the size-guide hub, the Up to 35' FAQ page, the "
        "ZIP 80202 vehicle search, and the facility page of the chosen space "
        "before holding. The final answer must state (a) the size-guide "
        "category covering RVs up to 35 feet, (b) what that FAQ page says "
        "such spaces are designed to store, (c) a PS-format reservation code "
        "for a hold placed under the task's contact with the required move-in "
        "date, and (d) the held space's monthly rate; the held space must be "
        "a vehicle space within 5 miles of the ZIP long enough for a 28-foot "
        "RV. A code that does not match the database, a too-short space, or "
        "an empty answer is a FAIL."),
    3: ("The agent must look up the given reservation code with the given "
        "email on the Your Reservation page, cancel it, open the same "
        "facility, and hold its cheapest 5'x10'. The final answer must state "
        "(a) the new PS-format reservation code, (b) the held unit's online "
        "rate, and (c) the status now shown for the old reservation. The old "
        "reservation must be cancelled and the new hold must be at the same "
        "facility under the same contact email with the required move-in "
        "date. A code that does not match the database, an uncancelled old "
        "reservation, or an empty answer is a FAIL."),
    4: ("The agent must log in with the given demo account, cancel the "
        "account's current reservation from the account page, open the "
        "Kirkland facility on 12249 NE 124th Street, and hold its cheapest "
        "5'x5'. The final answer must state (a) the new PS-format reservation "
        "code and (b) the held unit's online monthly rate. The old "
        "reservation must be cancelled and the new hold must carry the "
        "required move-in date and the account's contact email. A code that "
        "does not match the database or an empty answer is a FAIL."),
    5: ("The agent must open the Pay Bill login, authenticate with the given "
        "account number and email, and pay the full balance with the given "
        "card. The final answer must state (a) the PS-PAY-format payment "
        "confirmation number, (b) the amount charged, and (c) the next bill "
        "date shown on the receipt. The database must contain exactly one "
        "new payment for the account's rental with the charged amount. A "
        "confirmation number that does not match the database, a wrong "
        "amount, or an empty answer is a FAIL."),
    6: ("The agent must open both Bellevue facility pages named in the task. "
        "The final answer must state (a) which of the two facilities has "
        "more customer reviews, (b) how many more, (c) the cheapest 5'x5' "
        "online rate at that facility, and (d) whether it offers 24/7 "
        "access. Review counts that do not match the facility pages, a rate "
        "from the other facility, or an empty answer is a FAIL."),
    7: ("The agent must open the 13640 Bel Red Road facility page. The final "
        "answer must state (a) the online rate and (b) the in-store price of "
        "the cheapest elevator-access 10'x15', (c) the online rate and (d) "
        "the in-store price of the cheapest ground-floor 10'x15', and (e) "
        "how much the online price of the cheaper of the two units saves "
        "versus its own in-store price each month. Prices from the wrong "
        "unit rows or an empty answer is a FAIL."),
    8: ("The agent must open the Chicago city page and the facility page of "
        "the most-reviewed Chicago facility. The final answer must state "
        "(a) the average cost of a storage unit shown on the city page, (b) "
        "the street address of the Chicago facility with the most customer "
        "reviews, (c) that facility's rating, (d) its cheapest currently "
        "listed unit size, and (e) that unit's online rate. A facility that "
        "is not the most reviewed, a size/rate not from its unit list, or an "
        "empty answer is a FAIL."),
    9: ("The agent must register the account with the exact contact details "
        "given in the task, run the ZIP 60601 search, open the facility page "
        "of the chosen unit, and hold it. The final answer must state (a) a "
        "PS-format reservation code, (b) the facility's street address, and "
        "(c) the online rate of the held climate-controlled 10'x10' within 2 "
        "miles of the ZIP. The database must contain the new user and one "
        "reservation for a climate-controlled 10'x10' with the required "
        "move-in date. A code that does not match the database, a "
        "non-climate unit, or an empty answer is a FAIL."),
    10: ("The agent must open the blog article about organizing a storage "
         "unit like a pro. The final answer must state (a) what the article "
         "says to do before tossing items into the unit, (b) which items go "
         "on the bottom when stacking, (c) how many sides of every bin to "
         "label, and (d) which blog category the article is filed under. "
         "Facts that do not match the article text or an empty answer is a "
         "FAIL."),
    11: ("The agent must open the help-center topic pages that carry the "
         "answers. The final answer must state (a) whether holding a unit "
         "costs anything, (b) how long a hold lasts, (c) when a late fee is "
         "applied to a monthly storage bill, and (d) the topic page each "
         "answer came from. Answers that contradict the help topics or an "
         "empty answer is a FAIL."),
    12: ("The agent must log in with the given demo account, change the "
         "account phone number as instructed, and view the account page. "
         "The final answer must state (a) the account number shown on the "
         "account page, (b) the rental's facility street address, (c) the "
         "monthly rate, and (d) the gate code. The database must show the "
         "new phone number on the account. Values from another account or "
         "an empty answer is a FAIL."),
    13: ("The agent must open the military storage solutions page and the "
         "facility page of the reported facility. The final answer must "
         "state (a) what the page says Public Storage offers military "
         "personnel and their families, (b) the street address of the "
         "highest-rated Charlotte facility, (c) its rating, and (d) its "
         "cheapest currently listed unit size with that unit's online rate. "
         "A facility that is not the highest rated, a size/rate not from "
         "its unit list, or an empty answer is a FAIL."),
    14: ("The agent must open the Kirkland 724 8th St facility page. The "
         "final answer must state (a) whether the facility offers 24/7 "
         "access, (b) its access hours on Sunday, (c) the cheapest 5'x10' "
         "online rate, and (d) the promotion shown on that unit. Facts "
         "that do not match the facility page or an empty answer is a "
         "FAIL."),
    15: ("The agent must run the ZIP 98101 search and view all three sort "
         "orders. The final answer must state, for each of Recommended, "
         "Closest and Lowest Price, (a) the street address of the facility "
         "listed first and (b) its displayed distance from the ZIP. A "
         "facility that is not first under that sort, a distance that does "
         "not match the page, or an empty answer is a FAIL."),
    16: ("The agent must run the ZIP 32801 search, open the facility page "
         "of the chosen unit, and hold it. The final answer must state (a) "
         "the facility's street address, (b) the online rate, and (c) a "
         "PS-format reservation code. The held 5'x10' must be the cheapest "
         "one whose facility is rated at least 4.8 stars, placed under the "
         "task's contact with the required move-in date. A code that does "
         "not match the database, a facility below the rating threshold, or "
         "an empty answer is a FAIL."),
    17: ("The agent must open the climate-controlled storage page, run the "
         "ZIP 98101 search, open the facility page of the chosen unit, and "
         "hold it. The final answer must state (a) what the page says such "
         "units are kept at, (b) what they protect belongings from, (c) a "
         "PS-format reservation code, (d) the facility's address, and (e) "
         "the online rate. The held unit must be the cheapest "
         "climate-controlled 10'x10' within 5 miles of the ZIP under the "
         "task's contact with the required move-in date. A code that does "
         "not match the database, a non-climate unit, or an empty answer is "
         "a FAIL."),
    18: ("The agent must log in with the given demo account, open the "
         "facility of the cancelled reservation, and hold its cheapest "
         "10'x10'. The final answer must state (a) the new PS-format "
         "reservation code, (b) the unit's online rate, and (c) the "
         "facility's street address. The new hold must be at the same "
         "facility under the account's contact with the required move-in "
         "date. A code that does not match the database, a different "
         "facility, or an empty answer is a FAIL."),
    19: ("The agent must open the 1213 W 6th Street Austin facility page. "
         "The final answer must state (a) the names and (b) star ratings of "
         "the two most recent reviewers shown on the page, plus (c) the "
         "facility's overall rating and (d) total review count. Reviewers "
         "that are not the two most recent shown, or an empty answer, is a "
         "FAIL."),
    20: ("The agent must open the 10'x20' size-guide FAQ page and the 13640 "
         "Bel Red Road facility page. The final answer must state (a) how "
         "many square feet the FAQ page says the 10'x20' unit holds, (b) the "
         "everyday space it compares the size to, and (c) the in-store "
         "monthly price of the cheapest 10'x20' at that facility. A price "
         "that is not the in-store list price of the cheapest 10'x20' or an "
         "empty answer is a FAIL."),
}


def main():
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        n = int(row["id"].rsplit("--", 1)[1])
        assert set(row) == {"web_name", "id", "ques", "web", "upstream_url"}, row["id"]
        assert row["web_name"] == "Public Storage", row["web_name"]
        prefix = {k: row[k] for k in ("web_name", "id", "ques", "web", "upstream_url")}
        row = dict(prefix)
        row["verifier_path"] = f"sites/public_storage/verify/verify_{n}.py"
        row["judge_rubric"] = RUBRICS[n]
        out.append(json.dumps(row, ensure_ascii=False))
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended verifier_path + judge_rubric to {len(out)} rows")


if __name__ == "__main__":
    main()

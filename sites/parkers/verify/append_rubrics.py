#!/usr/bin/env python3
"""append_rubrics.py — append verifier_path + judge_rubric to sites/parkers/tasks.jsonl.

Contract:
  * the five task-definition keys (web_name, id, ques, web, upstream_url) stay
    BYTE-IDENTICAL — the script rewrites each line by appending two new keys to
    the original line text, never re-serializing the original five;
  * no answer key is ever added; judge_rubric carries English pure rules only
    (no ground-truth values);
  * idempotent: a second run is a no-op.

Run from sites/parkers/:  python3 verify/append_rubrics.py [--check]
"""
import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
TASKS = SITE / 'tasks.jsonl'

RUBRICS = {
    0: ("Verify the trajectory followed the free-valuation chain for the exact "
        "Fiesta derivative on the 2019/19 plate (generation used-prices page with "
        "that year and version selected, then select-a-valuation, then "
        "free-valuation). The answer must quote the private-sale range, the dealer "
        "range and the part-exchange value exactly as shown on the free-valuation "
        "page. Read-only task: the database must be unchanged."),
    1: ("Verify the registration search was used and the valuation pages for the "
        "resolved Corsa version were opened. The answer must name the exact "
        "version the valuation refers to and quote its private and dealer ranges, "
        "then identify the cheapest Corsa currently listed and state whether that "
        "asking price sits above or below the dealer range. Read-only task: the "
        "database must be unchanged."),
    2: ("Verify the free-valuation chain for the 318d M Sport on the 2023/73 "
        "plate. The answer must quote the private-sale range, the dealer range "
        "and the part-exchange value, and state which selling route the "
        "mid-points suggest earns more (the economically correct comparison is "
        "the private mid-point against the part-exchange mid-point; the literal "
        "private-vs-dealer-range reading is also accepted). Read-only task: the "
        "database must be unchanged."),
    3: ("Verify both named derivatives' spec pages were opened (Kodiaq 1.5 TSI "
        "e-TEC SE 5dr DSG and Tucson 1.6T 150 Advance 5d). The answer must quote "
        "both luggage-space figures from the spec pages, name the car with the "
        "bigger boot and give the difference in litres. Read-only task: the "
        "database must be unchanged."),
    4: ("Verify the diesel Civic spec selections were opened (the most "
        "economical diesel version and one other diesel version). The answer must "
        "name the most economical diesel Civic, quote its official MPG and its "
        "price when new, and quote the MPG of one other diesel Civic version. "
        "Read-only task: the database must be unchanged."),
    5: ("Verify both insurance-group pages were opened (current Polo and current "
        "Fiesta). The answer must give each car's lowest insurance group number, "
        "name the specific versions that achieve them, and say which car is "
        "cheaper to insure. Read-only task: the database must be unchanged."),
    6: ("Verify the 3 Series review overview, its verdict section and the 3 "
        "Series cars-for-sale listings were opened. The answer must quote the "
        "overall rating, one like and one dislike from the review's own lists, "
        "the reliability score from the verdict's ratings, and the price and "
        "mileage of the most expensive 3 Series currently listed. Read-only "
        "task: the database must be unchanged."),
    7: ("Verify both review verdict pages (Audi A3 and MINI Cooper) and both "
        "spec pages were opened. The answer must quote both practicality "
        "ratings, say which car scores higher and by how much, quote both "
        "luggage-space figures and their difference in litres (the difference "
        "must match the two figures quoted). Read-only task: the database must "
        "be unchanged."),
    8: ("Verify the agent signed in as the named benchmark user, ran the "
        "cars-for-sale search with the task's filter combination (used, "
        "automatic, SUV, price cap, mileage cap, year minimum) sorted by price "
        "ascending, and opened the cheapest matching listing. The answer must "
        "name that car, its price and its mileage. Stateful task: the database "
        "must gain exactly one shortlist row for that user pointing at that "
        "listing, and nothing else may change."),
    9: ("Verify the agent signed in as the named benchmark user, visited the "
        "shortlist, and ran an all-cars search sorted by price ascending. The "
        "answer must name the removed (most expensive) car, the remaining cars "
        "with their combined price, and the cheapest car listed on the site. "
        "Stateful task: the database must show exactly that removal and exactly "
        "one added shortlist row for the cheapest car, and nothing else may "
        "change."),
    10: ("Verify the Fiesta Hatchback (2017-2023) owner-reviews page and the "
         "Fiesta expert review were opened. The answer must quote the number of "
         "owners who have reviewed the car, the average owner rating and the "
         "expert review's overall rating. (The mirror renders no owner-review "
         "body text, so no specific problem can be quoted; the three verifiable "
         "facts are enforced.) Read-only task: the database must be unchanged."),
    11: ("Verify the Golf Hatchback (2020 onwards) owner-reviews page was opened "
         "and the review form was submitted. The answer must confirm the review "
         "appears on that page and restate its identity (author name, rating, "
         "the infotainment mention). Stateful task: the database must gain "
         "exactly one owner-review row for that Golf generation with the "
         "required rating, author, purchase year and infotainment mention, and "
         "nothing else may change."),
    12: ("Verify the Renault 5 E-Tech 2027-update news article and the Renault 5 "
         "E-Tech expert review were opened. The answer must quote the official "
         "WLTP range for both battery sizes, the improvement in miles, and the "
         "expert review's overall rating. Read-only task: the database must be "
         "unchanged."),
    13: ("Verify the best family SUVs 2026 guide and the Audi cars-for-sale "
         "search were opened. The answer must name the guide's number one pick, "
         "two further SUVs recommended in the same guide, and the price of the "
         "cheapest Audi Q3 currently listed. Read-only task: the database must "
         "be unchanged."),
    14: ("Verify the car tax page (rates table) and the Fiesta per-car tax "
         "information were opened. The answer must quote the standard annual "
         "road tax rate for a petrol car, what electric cars pay per year, the "
         "first-year rate for a petrol car emitting 131-150 g/km, and the annual "
         "car tax for the Fiesta Zetec 1.0T EcoBoost 100PS. (Values are "
         "enforced as shipped on the mirror.) Read-only task: the database must "
         "be unchanged."),
    15: ("Verify the hatchbacks reviews class page and the review page of one "
         "top-rated hatchback were opened. The answer must quote the top rating "
         "achieved in the class, name at least three models that share it, and "
         "quote one thing the opened review specifically likes about the car. "
         "Read-only task: the database must be unchanged."),
    16: ("Verify the site search was used for the Ioniq 5, the Ioniq 5 expert "
         "review was opened, and the free-valuation chain for the cheapest "
         "Ioniq 5 version on the newest year plate was completed. The answer "
         "must quote the review's overall rating, one pro and one con from the "
         "review's own lists, and the private-sale price range of that version "
         "on that plate. Read-only task: the database must be unchanged."),
    17: ("Verify the free-valuation chain for the Fiesta 1.0 EcoBoost 100 "
         "ST-Line Edition 3dr on the 2023/23 plate and the Fiesta cars-for-sale "
         "search were completed. The answer must quote the private-sale range "
         "and the cheapest Fiesta listing's price, and state whether that "
         "asking price falls inside or below the valuation's private-sale "
         "range. Read-only task: the database must be unchanged."),
    18: ("Verify the free-valuation chain for the newest Dacia Sandero's "
         "cheapest version on the 2023/73 plate. The answer must name the exact "
         "version and quote its private-sale price range. Read-only task: the "
         "database must be unchanged."),
    19: ("Verify the Kodiaq generation spec pages (with the cheapest and the "
         "most expensive versions selected) and the free-valuation chain for "
         "the cheapest version on the newest year plate were opened. The answer "
         "must quote the price when new of both versions, the difference "
         "between them, and the dealer price range of the cheapest version on "
         "the newest plate. Read-only task: the database must be unchanged."),
}


def main():
    check_only = '--check' in sys.argv
    lines = TASKS.read_text().splitlines(keepends=True)
    out_lines = []
    changed = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue
        obj = json.loads(stripped)
        n = int(obj['id'].split('--')[1])
        if 'verifier_path' in obj:
            out_lines.append(line)
            continue
        if check_only:
            print(f'T{n}: missing verifier keys')
            continue
        addition = {'verifier_path': f'sites/parkers/verify/verify_{n}.py',
                    'judge_rubric': RUBRICS[n]}
        # append keys to the ORIGINAL line text: byte-identical five-key prefix
        prefix = stripped.rstrip('}')
        new_line = prefix + ', ' + json.dumps(addition, ensure_ascii=False)[1:] + '\n'
        # sanity: original prefix bytes preserved
        assert new_line.startswith(stripped[:len(stripped) - 1]), n
        assert json.loads(new_line)['id'] == obj['id']
        out_lines.append(new_line)
        changed += 1
    if check_only:
        missing = changed
        print('missing rubrics:', missing)
        return
    TASKS.write_text(''.join(out_lines))
    print(f'appended verifier_path + judge_rubric to {changed} rows')


if __name__ == '__main__':
    main()

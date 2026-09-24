#!/usr/bin/env python3
"""Append the reviewer grading keys (verifier_path + judge_rubric) to every
sites/landwatch/tasks.jsonl row of the depth-redesigned 15-task set, keeping
the five contributor keys byte-identical and adding no answer key.

Round-2 re-review contract sync (medicare_gov-depth2 precedent), carried
onto the PR branch by the round-3 T4 fix: the contributor branch ships
five-key rows; the merged state carries the two reviewer keys inline. Ground
truth never appears in either file -- it stays hardcoded inside
verify_0..14.py. Round 3 also deepened task 4 (hunting funnel) with a
cheapest-first leg on the acres+residence layer; rubrics[4] and verify_4.py
match that wording.

Usage: python3 append_rubrics.py   (from the review worktree root)
"""
from __future__ import annotations

import json
from pathlib import Path

TASKS = Path("sites/landwatch/tasks.jsonl")
CONTRIBUTOR_KEYS = ["web_name", "id", "ques", "web", "upstream_url"]
REVIEWER_KEYS = ["verifier_path", "judge_rubric"]

RUBRICS = {
    0: "FACT CHECKPOINTS: (1) The trajectory MUST look up Austin, Harris County, and Boerne with the site's location search and open all three results pages. (2) The answer MUST report each page's listing total plus the first listing's price and acreage, and must name the better-value location judged on price per acre. (3) Empty answer = FAIL. Reject facts taken from any other city or county page.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST open both Hill Country detail pages: 'Sisterdale Farms' (Kendall County) and 'Tucked into the Hill Country' (Burnet County). (2) The answer MUST report each property's asking price, acreage, and the listing agent and brokerage shown in the agent contact panel, plus which property is larger and by how many acres. (3) Empty answer = FAIL. Reject agent facts recomputed from any other page.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST open the 'Sisterdale Farms' detail page and, via the Find an Agent directory, the listing agent's profile. (2) The answer MUST report the price, acreage, beds, baths, and gallery picture count, quote the first two Highlights bullets and every activity under Amenities, and report the agent's total listings, price range, acre range, and where they are based. (3) Empty answer = FAIL. A partial Highlights pair, a partial Activities list, or wrong-profile stats = FAIL.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST open the Texas land page with the '$1,000,000 and up' price filter sorted 'Price: Low to High', and the Undeveloped Land page with the '$50,000 - $99,999' band sorted the same way. (2) The answer MUST report the Texas total plus the title, price, and county of the three cheapest listings, the Undeveloped total plus the cheapest listing's title, price, and county, and which track's cheapest property costs less. (3) Empty answer = FAIL. Reject the cheapest listing of any unfiltered or differently-sorted page.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST open the Hunting Land category and stack the '0 - 10 Acres' parcel filter and the Residence: Yes filter, view that stacked layer sorted 'Price: Low to High', then add the '4+ Bedrooms' filter with the final layer sorted by 'Newest'. (2) The answer MUST report the result count after each filter layer, the cheapest acres+residence listing's title, price, and county, and the most recently listed property's title, price, and state. (3) Empty answer = FAIL. Reject counts or facts from an unstacked or differently-sorted page.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST open the Colorado page sorted 'Acres: Large to Small', the largest property's detail page, and the Montana page with the 'Over 1,000 Acres' filter. (2) The answer MUST report the largest ranch's title, price, acreage, and every type in its Type row; the second-largest Colorado property's title and acreage; each Montana match's title and acreage; and which state's largest ranch is bigger and by how many acres. (3) Empty answer = FAIL. A partial Type row or a missing Montana match = FAIL.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST open the All Land Auctions page, page two of its results, and the Hunting Land Auctions page. (2) The answer MUST report the total auction count, the first two auctions' title, acreage, and auction date, the very last auction on page two (title, acreage, date), and the Hunting Land auctions total. (3) Empty answer = FAIL. Reject the last auction of page one or any other category's totals.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST open the Texas land page, its Houston Region results, the Texas page again, the county with the most listings in the County filter group, and that county's page sorted 'Price: High to Low'. (2) The answer MUST report the Houston Region count plus its first listing's title, price, and acreage; the top county's name and count; and that county's most expensive listing's title and price. (3) Empty answer = FAIL. Reject any other region or county.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST open the Find an Agent directory, the profile of the agent with the most total listings, and the first listing in that agent's grid. (2) The answer MUST report the agent's name, brokerage, total listings, price range, acre range, and where they are based, plus the first listing's status, price, size in acres, and every property type in its Type row. (3) Empty answer = FAIL. A partial Type row = FAIL.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, favorite both named Hill Country candidates with the heart button, save the Hunting Land '$250,000 - $499,999' search, open My LandWatch, and remove the smaller candidate. (2) The answer MUST report the saved-property count after favoriting, the stored search's exact name and URL, the count after the removal, and which candidate is still saved. (3) Empty answer = FAIL. A database without exactly the allowed session, kept-favorite, and saved-search deltas = FAIL.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, edit the profile phone number, save, then save the Montana land-for-sale page as a search and open My LandWatch. (2) The answer MUST report the success message, the phone number shown on the profile card afterwards, the stored search's exact name, and how many saved searches the account ends up with. (3) Empty answer = FAIL. An unchanged phone number or a missing saved-search row in the database = FAIL.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST register the specified new account (email and password as given in the task) with a name, describe the fresh account's empty states for Favorites, Saved Searches, and My Inquiries, favorite the named Boerne listing, send the named Ohio listing's agent a message asking about soil quality, and read both back on My LandWatch. (2) The answer MUST report the three empty states, the saved property's title, the confirmation shown after sending, and the inquiry record's recipient, contact email, and message. (3) Empty answer = FAIL. A database without exactly the allowed user, session, favorite, and inquiry deltas = FAIL.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST read the homepage's featured-listing carousel and category tiles, then open the Hunting Land category page. (2) The answer MUST report the price, acreage, and state of each of the first three featured properties in carousel order, the label and listing count of each of the first four category tiles, and whether the Hunting Land results-heading total matches the Hunting Land tile count. (3) Empty answer = FAIL. Swapped featured order (e.g. West Virginia reported for the second property) = FAIL.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST open the Texas land page, its Waterfront-filtered results sorted 'Price: High to Low', the unfiltered Texas results, and the statewide most expensive listing's detail page. (2) The answer MUST report how many Texas waterfront listings there are, the most expensive waterfront listing's title, price, and acreage, the single most expensive Texas listing's title and price, which of the two costs more, and whether the statewide champion is a waterfront property. (3) Empty answer = FAIL. A reversed or unsubstantiated comparison claim = FAIL.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST use the custom price range form ($100,000 - $250,000) and the custom size range form (100 - 200 acres) on the main Land for Sale page, clearing the price range before the size search. (2) The answer MUST report how many listings the budget matches, the first one's title, price, and county, the Sale Type filter group's For Sale and Auction counts within that budget, the size band's match count, and the first size-band listing's title and price. (3) Empty answer = FAIL. Reject counts recomputed without the custom forms.",
}


def main() -> None:
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        assert sorted(row.keys()) == sorted(CONTRIBUTOR_KEYS), f"unexpected keys: {sorted(row.keys())}"
        n = int(row["id"].split("--")[1])
        # byte-identity guard: the five contributor keys re-serialize to the original line
        prefix = json.dumps({k: row[k] for k in CONTRIBUTOR_KEYS}, ensure_ascii=False)
        assert json.dumps(row, ensure_ascii=False) == line, \
            f"contributor row does not round-trip: {line[:120]}"
        new_row = {k: row[k] for k in CONTRIBUTOR_KEYS}
        new_row["verifier_path"] = f"sites/landwatch/verify/verify_{n}.py"
        new_row["judge_rubric"] = RUBRICS[n]
        assert "answer" not in new_row
        assert list(new_row.keys()) == CONTRIBUTOR_KEYS + REVIEWER_KEYS
        out.append(json.dumps(new_row, ensure_ascii=False))
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended verifier_path + judge_rubric to {len(out)} rows; contributor keys byte-identical")


if __name__ == "__main__":
    main()

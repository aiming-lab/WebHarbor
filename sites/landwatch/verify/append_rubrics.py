#!/usr/bin/env python3
"""Append the reviewer grading keys (verifier_path + judge_rubric) to every
sites/landwatch/tasks.jsonl row, keeping the five contributor keys
byte-identical and adding no answer key.

Usage: python3 append_rubrics.py   (from the review worktree root)
"""
from __future__ import annotations

import json
from pathlib import Path

TASKS = Path("sites/landwatch/tasks.jsonl")
CONTRIBUTOR_KEYS = ["web_name", "id", "ques", "web", "upstream_url"]
REVIEWER_KEYS = ["verifier_path", "judge_rubric"]

RUBRICS = {
    0: "FACT CHECKPOINTS: (1) The trajectory MUST look up Austin with the homepage location search (or the site search) and open the Austin, Texas land-for-sale results page. (2) The answer MUST report the total number of listings in the results heading plus the price and acreage of the first listing. (3) Empty answer = FAIL. Reject facts taken from any other city or county page.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST open the Texas land-for-sale page, apply the '$1,000,000 and up' price filter, and apply the 'Price: Low to High' sort. (2) The answer MUST report the number of listings in the results heading plus the title, price, and county of the cheapest listing. (3) Empty answer = FAIL. Reject the cheapest listing of the unfiltered page or of any other sort.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST open the Hunting Land category page, apply the '0 - 10 Acres' parcel size filter, and apply the 'Newest' sort. (2) The answer MUST report the total number of listings in the heading plus the title, price, and state of the most recently listed property. (3) Empty answer = FAIL. Reject facts from the unfiltered or differently-sorted page.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST open the Sisterdale Farms listing detail page (Kendall County, Texas). (2) The answer MUST report the price, the acreage, how many beds and baths the home has, and the picture count shown by the gallery button. (3) Empty answer = FAIL.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST open the Sisterdale Farms listing detail page. (2) The answer MUST quote the first two bullets of the Highlights section and list every activity shown under Amenities > Activities. (3) Empty answer = FAIL. A partial Highlights pair or a partial Activities list = FAIL.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST open the 'Tucked into the Hill Country' listing detail page (Burnet County, Texas). (2) The answer MUST report the listing agent's name, the brokerage, the phone number shown in the agent contact panel, and the gallery's picture count. (3) Empty answer = FAIL.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST open the Texas land-for-sale page and follow the Region Map filter to the Houston Region results page. (2) The answer MUST report how many listings the region page shows plus the title, price, and acreage of the first listing on it. (3) Empty answer = FAIL. Reject counts or listings from any other region.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST open the Land for Auction page. (2) The answer MUST report the total number of auction listings in the results heading plus, for the first auction listing, its title, its acreage, and the auction date shown on the card. (3) Empty answer = FAIL.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST open the Find an Agent directory. (2) The answer MUST report how many agents are listed on the page plus the name and brokerage of the agent shown with the most total listings. (3) Empty answer = FAIL.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST open the agent profile page for Louie Swope of West & Swope Ranches. (2) The answer MUST report the Total Listings count, the Price Range, and the Acre Range from the stats box plus the city and state where the agent is based. (3) Empty answer = FAIL. Reject stats recomputed from any other page.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account and open My LandWatch. (2) The answer MUST state how many saved properties the account has, how many saved searches, and name every saved search. (3) Empty answer = FAIL. A missing saved-search name or wrong counts = FAIL.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, open the Hunting Land category page with the '$250,000 - $499,999' price filter, click 'Save Search', and open My LandWatch. (2) The answer MUST report the exact name the saved search was stored under and the URL it links to. (3) Empty answer = FAIL. Reject a paraphrased name or a different URL.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, remove the saved search that covers Montana, and open My LandWatch. (2) The answer MUST report how many saved searches remain and the name of the remaining search. (3) Empty answer = FAIL. Reporting the removed Montana search as remaining = FAIL.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST open the 'Prime Ohio Farmland' listing (Allen County, Ohio) and submit the agent contact form with a name, a valid email, and a short message asking about the soil quality. (2) The answer MUST quote the confirmation message shown after submitting. (3) Empty answer = FAIL. A submission that skips the form or a DB with no new inquiry row = FAIL.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST look up Harris County, Texas with the location search and open its results page. (2) The answer MUST report the number of land listings in the heading plus the title, price, and acreage of the first listing. (3) Empty answer = FAIL.",
    15: "FACT CHECKPOINTS: (1) The trajectory MUST open the Farms & Ranches category page. (2) The answer MUST report the total number of listings in the results heading plus the title, price, and state of each of the first three listings, in page order. (3) Empty answer = FAIL. Swapped order or missing entries = FAIL.",
    16: "FACT CHECKPOINTS: (1) The trajectory MUST open the Florida land-for-sale page and the Florida waterfront property-type results (state + Waterfront, /florida-land-for-sale/waterfront-property). (2) The answer MUST report how many waterfront land listings Florida has plus the title and price of the first one. (3) Empty answer = FAIL. Reject the nationwide waterfront totals or a listing outside Florida.",
    17: "FACT CHECKPOINTS: (1) The trajectory MUST open the homepage and read the category tile carousel below the featured listings. (2) The answer MUST report the label and the listing count shown on each of the four named tiles: Land for Sale, Farms and Ranches, Hunting Land, and Homesites. (3) Empty answer = FAIL. A missing tile label or count = FAIL.",
    18: "FACT CHECKPOINTS: (1) The trajectory MUST open the homepage and read the featured-listing carousel under 'Land for Sale in the United States'. (2) The answer MUST report the price, acreage, and state of each of the first three featured properties. (3) Empty answer = FAIL. Swapped order or wrong state (e.g. West Virginia for the second property) = FAIL.",
    19: "FACT CHECKPOINTS: (1) The trajectory MUST open the Colorado land-for-sale page and apply the 'Acres: Large to Small' sort. (2) The answer MUST report the acreage, price, county, and title of the largest property. (3) Empty answer = FAIL. Reject the largest property of any other sort or page.",
    20: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account and open My LandWatch. (2) The answer MUST list ALL of the account's saved properties with their titles so the user can decide which one to remove. (3) Empty answer = FAIL. A partial list = FAIL. The favorites table must be unchanged or have exactly one removal and nothing else.",
    21: "FACT CHECKPOINTS: (1) The trajectory MUST open the Montana land-for-sale page and apply the 'Over 1,000 Acres' parcel size filter. (2) The answer MUST report how many listings match and, for each matching listing, its title and acreage. (3) Empty answer = FAIL. A missing listing or a wrong acreage = FAIL.",
    22: "FACT CHECKPOINTS: (1) The trajectory MUST open the '3D Mountain Ranch' listing detail page in Colorado. (2) The answer MUST report its price, its acreage, and every property type listed in the Type row of the summary strip. (3) Empty answer = FAIL. A partial Type row = FAIL.",
    23: "FACT CHECKPOINTS: (1) The trajectory MUST look up Boerne, Texas with the location search and open its results page. (2) The answer MUST report how many land listings the page shows in its heading plus the title and price of the first listing. (3) Empty answer = FAIL.",
    24: "FACT CHECKPOINTS: (1) The trajectory MUST open the Undeveloped Land category page, apply the '$50,000 - $99,999' price filter, and apply the 'Price: Low to High' sort. (2) The answer MUST report the number of listings in the heading plus the title, price, and county of the cheapest listing. (3) Empty answer = FAIL.",
    25: "FACT CHECKPOINTS: (1) The trajectory MUST open the Texas land-for-sale page, identify the county with the most listings in the County filter group, open that county's page, and apply the 'Price: High to Low' sort. (2) The answer MUST report the county's listing count plus the title and price of the most expensive listing there. (3) Empty answer = FAIL. Reject any other county.",
    26: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, edit the profile to change the phone number to (919) 555-0139, save, and open My LandWatch. (2) The answer MUST report the success message shown and confirm the new phone number appears in the profile card. (3) Empty answer = FAIL. An unchanged phone number in the profile card = FAIL.",
    27: "FACT CHECKPOINTS: (1) The trajectory MUST create the specified new account (email and password as given in the task) with a name. (2) The answer MUST report the heading of the page the account lands on and the empty-state text shown for Favorites and for Saved Searches. (3) Empty answer = FAIL. Paraphrased empty-state text = FAIL.",
    28: "FACT CHECKPOINTS: (1) The trajectory MUST open the main Land for Sale page for the United States, click the first listing, and read its detail page. (2) The answer MUST report the listing status, the price, the size in acres, every property type in the Type row, and the gallery button's picture count. (3) Empty answer = FAIL. A partial Type row = FAIL.",
    29: "FACT CHECKPOINTS: (1) The trajectory MUST open the Find an Agent page, identify the agent with the most total listings, and open that agent's profile. (2) The answer MUST report the agent's name, brokerage, Total Listings count, Price Range, Acre Range, and the title and price of the first listing in the agent's listings grid. (3) Empty answer = FAIL.",
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
        assert line.startswith(prefix.rstrip("}").rstrip()) or json.dumps(row, ensure_ascii=False) == line, \
            f"contributor row does not round-trip: {line[:120]}"
        new_row = {k: row[k] for k in CONTRIBUTOR_KEYS}
        new_row["verifier_path"] = f"sites/landwatch/verify/verify_{n}.py"
        new_row["judge_rubric"] = RUBRICS[n]
        assert "answer" not in new_row
        out.append(json.dumps(new_row, ensure_ascii=False))
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended verifier_path + judge_rubric to {len(out)} rows; contributor keys byte-identical")


if __name__ == "__main__":
    main()

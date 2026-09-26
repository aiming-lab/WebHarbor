#!/usr/bin/env python3
"""append_rubrics.py — reviewer-side tasks.jsonl upgrade for re_max.

Appends ``verifier_path`` + ``judge_rubric`` to every row of
sites/re_max/tasks.jsonl while keeping the original 5-key prefix
(web_name, id, ques, web, upstream_url) BYTE-IDENTICAL, and adding no
``answer`` key. Rubrics state the RULES (English, ASCII, no answer values):
which pages must be opened, which facts must appear, that an empty answer is
a FAIL. Ground truth lives only in the verifiers.
"""
import json
import re
import sys
from pathlib import Path

TASKS = Path(__file__).resolve().parent.parent / "tasks.jsonl"

RUBRICS = {
0: ("FACT CHECKPOINTS: The agent must open the Austin, TX search results page with filters for House listings priced 600000-900000 with 4+ bedrooms, sort them by price, and open the three most affordable matches' listing pages. The answer must state, for the cheapest match, its year built, its price per square foot, its HOA fee with the frequency, and whether it has an open house scheduled, and for each of the other two matches the open-house day and time window shown on its page. An answer without the filtered search and all three listing pages open is a FAIL. An empty answer is a FAIL."),
1: ("FACT CHECKPOINTS: The agent must open the Redmond, WA search results page filtered to Condo, max price 700000, 2+ beds, sort them by price, and open both matches' listing pages. The answer must state, for each match, whether it has an open house and, if so, the exact day and time window shown, plus the price per square foot and the number of parking spaces of the cheaper one. An answer without the filtered search and both detail pages open is a FAIL. An empty answer is a FAIL."),
2: ("FACT CHECKPOINTS: The agent must open the Redmond, WA search results page and check "
    "listing detail pages for year-built information before naming the newest-built home. "
    "The answer must name the REMAX office presenting that home, its price per square "
    "foot, and its number of parking spaces. Naming a home without opening Redmond "
    "listing detail pages is a FAIL. An empty answer is a FAIL."),
3: ("FACT CHECKPOINTS: The agent must open the Denver, CO and Colorado Springs, CO search results pages filtered to Townhouse listings and open each of the four townhouses' listing pages. The answer must name the townhouse that gives more square footage per dollar with its city, its year built and its number of parking spaces, and state how much cheaper it is per square foot than the most expensive of the four per square foot. An answer without both filtered searches and all four listing pages open is a FAIL. An empty answer is a FAIL."),
4: ("FACT CHECKPOINTS: The agent must open the Bellevue, WA search results page filtered to "
    "open houses, check listing detail pages for the Saturday open-house windows, choose "
    "the cheapest home whose window starts at 1pm or later and ends by 3pm, and submit a "
    "tour request on that listing's page as a guest with the email given in the task. The "
    "answer must name the chosen home and its open-house time, and report the site's "
    "confirmation. A tour request from any other page or without the guest email is a "
    "FAIL. An empty answer is a FAIL."),
5: ("FACT CHECKPOINTS: The agent must open the agent finder filtered to Spanish-speaking agents and open the matching agent's detail page, then determine the cohort of agents with 30 or more years of experience across the whole directory. The answer must state the Spanish-speaking agent's name, the city of their office, their years of experience, one hobby from the profile, and their license number, plus how many agents have 30 or more years of experience and the name of the most experienced agent among them. An answer without the filtered agent search, the profile and the cohort determination is a FAIL. An empty answer is a FAIL."),
6: ("FACT CHECKPOINTS: The agent must open the agent finder filtered to agents licensed in Illinois and open each of their profiles, then filter to agents licensed in Pennsylvania and open each of those profiles. The answer must state the most experienced Illinois agent's name, title, years of experience and one civic activity, plus the most experienced Pennsylvania agent's name and years and how many Pennsylvania agents there are. An answer without both filtered searches and the profiles open is a FAIL. An empty answer is a FAIL."),
7: ("FACT CHECKPOINTS: The agent must open the office search page, filter offices by language, and check the page of each matching office to find the one whose service areas include Grapevine. The answer must state that office's name, the website shown on its page, two languages its staff speaks besides English, one other city or area it serves, how many of the matching offices have Dallas in their service areas, and how many offices the site's search finds for Grapevine. An answer without the filtered office search, the matching office pages and the site search is a FAIL. An empty answer is a FAIL."),
8: ("FACT CHECKPOINTS: The agent must open the rentals table, find every rental at or under 2000 per month with at least 3 bedrooms, and open each one's page. The answer must state which one was built most recently with its address and monthly rent, how many rentals matched, and report the site's confirmation for the availability question sent as a guest on the newest one's page with the email given in the task. An availability question from any other page, without the matching pages open, or without the guest email is a FAIL. An empty answer is a FAIL."),
9: ("FACT CHECKPOINTS: The agent must open the rentals table and the pages of the three-bedroom rentals in both Louisville and Worcester. The answer must state which city's cheapest three-bedroom rental is cheaper and by how much per month, which rental's description mentions a basement, and report the confirmation for the tour scheduled on the cheapest three-bedroom rental overall as a guest with the email given in the task. A tour request from any other page or without the guest email is a FAIL. An empty answer is a FAIL."),
10: ("FACT CHECKPOINTS: The agent must log in with the demo account given in the task, remove the most expensive favorite and the saved search for Denver townhouses, then find the cheapest Austin home with an open house scheduled on the given Saturday, open its listing page, and save it to the favorites. The answer must state how many favorites remain afterwards, the price of the new most expensive favorite, and how many saved searches remain. An answer without the login, the favorites and account pages, the Austin open-house search and the chosen listing page open is a FAIL. An empty answer is a FAIL."),
11: ("FACT CHECKPOINTS: The agent must log in with the demo account given in the task, open "
     "the favorites page, remove every favorite that is not in Miami, then save a search "
     "for Miami condos priced under 400000 from the Miami search results page. The answer "
     "must state the name the site gives the saved search and how many favorites remain. "
     "An answer without logging in and the favorites page open is a FAIL. An empty answer "
     "is a FAIL."),
12: ("FACT CHECKPOINTS: The agent must register the new account exactly as specified in the "
     "task (name, email, password, Downsizer buyer type), update the profile phone number, "
     "and sign up for Miami listing alerts with that email from the Miami search results "
     "page. The answer must state the buyer type and phone number the account overview "
     "shows. An answer without the registration, the profile edit and the account overview "
     "open is a FAIL. An empty answer is a FAIL."),
13: ("FACT CHECKPOINTS: The agent must open the agent finder filtered to agents licensed in Florida and open each of their profiles. The answer must state each Florida agent's years of experience, the name and one civic activity of the one whose title shows they own their brokerage, and the confirmation for the message sent as a guest with the email given in the task. A message from any other page or without the guest email is a FAIL. An empty answer is a FAIL."),
14: ("FACT CHECKPOINTS: The agent must open the REMAX advice article about seller concessions for 2026 buyers, open the first-time buyer article for August 2026 from its More-from list, and filter the Naples, FL listings to homes under 500000 with 2+ bedrooms and 2+ bathrooms. The answer must state the percentage range conventional loan caps run, what FHA and USDA loans cap at, whether concessions can cover the down payment, the median sales price the first-time buyer article cites, how many Naples homes match, and the cheapest match's price, address, year built and price per square foot. An answer without both articles, the filtered Naples search and the cheapest match's page open is a FAIL. An empty answer is a FAIL."),
15: ("FACT CHECKPOINTS: The agent must open the latest interest rate announcement article on the REMAX blog, subscribe to the HomeHQ newsletter from the site's front page with the email and buyer type given in the task, and filter the Chicago listings to homes under 500000 with at least 3 bedrooms. The answer must state what the Federal Reserve decided, the new target range for the federal funds rate, the vote count, the dates of the meeting, the newsletter confirmation, how many Chicago homes match, and the price of the cheapest one. An answer without the article, the newsletter signup and the filtered Chicago search is a FAIL. An empty answer is a FAIL."),
16: ("FACT CHECKPOINTS: The agent must open the REMAX Collection luxury listings page, then filter the Miami listings to homes priced from 2000000 with at least 4 bedrooms and the Seattle listings to homes priced from 2000000. The answer must state how many luxury properties are listed in total, the address and price of the cheapest luxury home in Florida and of the cheapest luxury home in Washington State, how many Miami homes match and the price of the cheapest match, and how many Seattle homes match and the price of the most expensive one. An answer without the luxury page and both filtered searches open is a FAIL. An empty answer is a FAIL."),
17: ("FACT CHECKPOINTS: The agent must open the Arizona state page to determine which city has the most homes for sale and how many, then open that city's search results filtered to houses with at least 2 bathrooms that have an open house scheduled, and open the cheapest match's listing page. The answer must state the city, its listing count, how many matches the filter chain returns, and the cheapest match's address, price, every open-house day and time window it shows, its price per square foot, and its year built. An answer without the state page, the filtered search and the cheapest match's page open is a FAIL. An empty answer is a FAIL."),
18: ("FACT CHECKPOINTS: The agent must use the site's search to find the homes on Calistoga Way, Wickersham Lane and Alegria Road in Austin and open each listing page. The answer must state the Calistoga Way home's price, bedrooms and bathrooms, price per square foot, HOA fee and open-house day and time window, the Wickersham Lane home's price per square foot and HOA fee, and the Alegria Road home's price and open-house day and time window, plus the confirmation for the tour requested on the Calistoga Way home as a guest with the name, email and phone given in the task. A tour request from any other page or without the guest identity is a FAIL. An empty answer is a FAIL."),
19: ("FACT CHECKPOINTS: The agent must open the Colorado open houses page to determine which city has the most homes with open houses scheduled and how many, then open that city's search results filtered to homes with an open house scheduled and open every match's listing page. The answer must state how many are open on Saturday, September 26th, which one opens earliest that day, and the price range of all the matches from cheapest to most expensive. An answer without the Colorado open houses page, the filtered search and every match's page open is a FAIL. An empty answer is a FAIL."),
}

EXPECTED_KEYS = ["web_name", "id", "ques", "web", "upstream_url"]


def main():
    lines = TASKS.read_text(encoding="utf-8").splitlines(keepends=True)
    out_lines = []
    changed = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue
        obj = json.loads(stripped)
        assert list(obj.keys()) == EXPECTED_KEYS, f"unexpected keys: {list(obj.keys())}"
        n = int(obj["id"].split("--")[1])
        if "verifier_path" in obj:
            out_lines.append(line)
            continue
        rubric = RUBRICS[n]
        assert all(ord(c) < 128 for c in rubric), f"rubric {n} must be ASCII"
        addition = {"verifier_path": f"sites/re_max/verify/verify_{n}.py",
                    "judge_rubric": rubric}
        # append keys to the ORIGINAL line text: byte-identical five-key prefix
        prefix = stripped.rstrip("}")
        new_line = prefix + ", " + json.dumps(addition, ensure_ascii=False)[1:] + "\n"
        # sanity: original prefix bytes preserved, no answer key, valid JSON
        assert new_line.startswith(stripped[:len(stripped) - 1]), n
        new_obj = json.loads(new_line)
        assert list(new_obj.keys()) == EXPECTED_KEYS + ["verifier_path", "judge_rubric"], n
        assert "answer" not in new_obj
        out_lines.append(new_line)
        changed += 1
    TASKS.write_text("".join(out_lines), encoding="utf-8")
    print(f"appended verifier_path + judge_rubric to {changed} rows")


if __name__ == "__main__":
    main()

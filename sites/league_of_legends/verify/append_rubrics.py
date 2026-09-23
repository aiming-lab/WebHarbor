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
    0: "FACT CHECKPOINTS: (1) The trajectory MUST open the Champions page with the Role "
       "filter set to Support and the Difficulty filter set to High. (2) The answer MUST "
       "report the filtered roster count and the name of every champion shown in the "
       "filtered roster. (3) Empty answer = FAIL. Reject a count or name list taken from "
       "the unfiltered roster or from any other filter combination.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST open the Champions page with the Role "
       "filter set to Marksman and the Difficulty filter set to Medium. (2) The answer "
       "MUST report how many champions the filtered page lists and the name of each one. "
       "(3) Empty answer = FAIL. Reject a count or name list taken from the unfiltered "
       "roster or from any other filter combination.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST open the Champions page with the "
       "Difficulty filter set to Low. (2) The answer MUST report the total number of "
       "champions that match the Low difficulty filter. (3) Empty answer = FAIL. Reject "
       "a count taken from the unfiltered roster or from any other difficulty level.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST open the Champions page with the sort "
       "set to Newest. (2) The answer MUST report the names of the first five champions "
       "at the top of the sorted roster, in the order shown. (3) Empty answer = FAIL. "
       "Reject a list taken from the A-to-Z or difficulty sort, or an out-of-order list.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST run the Champions page search for "
       "'darkin' and open every champion detail page the search returns. (2) The answer "
       "MUST list the champions that appear in the results and report the role (or "
       "roles) shown on each champion's own page. (3) Empty answer = FAIL. Reject roles "
       "recalled from memory instead of read off the champion pages.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST open the champion page of the champion "
       "whose epithet is 'The Ruined King'. (2) The answer MUST report that champion's "
       "name, the role (or roles) shown on the page, and the difficulty rating shown on "
       "the page. (3) Empty answer = FAIL. Reject a role or difficulty value not shown "
       "on that champion's page.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST open the champion page for Mel. (2) "
       "The answer MUST report how many skins are listed in the Available Skins "
       "carousel and the name of each skin. (3) Empty answer = FAIL. Reject a skin count "
       "or skin names taken from any other champion's page.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST open the champion page for Ambessa. "
       "(2) The answer MUST report the names of all five abilities in the Abilities "
       "section, in slot order Passive, Q, W, E, R. (3) Empty answer = FAIL. Reject "
       "ability names from any other champion or an out-of-order list.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST open the champion page for Yunara. "
       "(2) The answer MUST report the full description text of Yunara's Passive ability "
       "exactly as shown on the page. (3) Empty answer = FAIL. Reject a paraphrase that "
       "drops the on-page effect wording.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST open the champion pages for Aatrox, "
       "Naafiri, and Zaahen. (2) The answer MUST report how many skins each of the three "
       "lists in the Available Skins section and state which of the three has the most "
       "skins. (3) Empty answer = FAIL. Reject skin counts not read from the three "
       "champion pages or a wrong 'most skins' conclusion.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST run the site search (the magnifying "
        "glass in the top navigation) for 'Pulsefire'. (2) The answer MUST list every "
        "champion that appears in the champion results of that search. (3) Empty answer "
        "= FAIL. Reject a champion list recalled from memory instead of the search "
        "results page.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST open the Patch Notes page. (2) The "
        "answer MUST report the title and the publish date of the most recent patch "
        "notes article in the list. (3) Empty answer = FAIL. Reject the title or date "
        "of any older patch note.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST open the League of Legends Patch "
        "26.19 Notes article and locate its Aatrox section. (2) The answer MUST name "
        "the ability of Aatrox that was changed and report the new cooldown values "
        "listed for it in that patch. (3) Empty answer = FAIL. Reject cooldown values "
        "from any other champion, ability, or patch.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST open BOTH the Patch 26.19 Notes and "
        "the Patch 26.18 Notes articles. (2) The answer MUST identify at least two "
        "champions that received changes in both patches, and for one of them describe "
        "the specific change stated in the 26.18 notes (ability name, numeric before and "
        "after values, or the change wording used on that page). (3) Empty answer = "
        "FAIL. Reject champions that appear in only one of the two patches or a change "
        "description that does not match the 26.18 article.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST open the Dev news category page. (2) "
        "The answer MUST report how many articles the category lists and the title of "
        "the most recent article. (3) Empty answer = FAIL. Reject a count or title read "
        "from any other category or the all-news hub.",
    15: "FACT CHECKPOINTS: (1) The trajectory MUST open the dev article '/dev: "
        "Modernizing the Monk'. (2) The answer MUST report the author listed on the "
        "article and the champion the article is about. (3) Empty answer = FAIL. Reject "
        "an author or champion not stated on the article page.",
    16: "FACT CHECKPOINTS: (1) The trajectory MUST open the Esports news category page. "
        "(2) The answer MUST report how many cards the page lists, the title of the "
        "first card, and whether the cards open as articles on this site or as external "
        "links. (3) Empty answer = FAIL. Reject a card count or first-card title read "
        "from any other category.",
    17: "FACT CHECKPOINTS: (1) The trajectory MUST browse to page 2 of the News hub. "
        "(2) The answer MUST report the title and publish date of the first article in "
        "the grid on page 2. (3) Empty answer = FAIL. Reject an article from page 1 or "
        "any other page of the hub.",
    18: "FACT CHECKPOINTS: (1) The trajectory MUST open the Lore news category page. "
        "(2) The answer MUST report the number of articles in the category and the "
        "title of every article in it. (3) Empty answer = FAIL. Reject a count or title "
        "list taken from any other category.",
    19: "FACT CHECKPOINTS: (1) The trajectory MUST run the site search for 'Vanguard'. "
        "(2) The answer MUST report how many news articles match the search and the "
        "title of the most recent matching article. (3) Empty answer = FAIL. Reject a "
        "count read anywhere other than the search page or a title not shown among the "
        "matching news results.",
    20: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "alice.j@test.com and open the account surface (account page or favorites "
        "page), and the database MUST be unchanged (read-only task). (2) The answer "
        "MUST report how many favorite champions the account has, the skin count of "
        "each favorite champion, and which favorite has the most skins. (3) Empty "
        "answer = FAIL. Reject favorites or skin counts not read from the signed-in "
        "account and the champion pages.",
    21: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "bob.c@test.com, add the champion Milio to the favorites from Milio's champion "
        "page, and exactly that one favorite row MUST be the only database change. (2) "
        "The answer MUST report how many favorite champions the account now has in "
        "total. (3) Empty answer = FAIL. Reject an answer that claims the add without "
        "the database row.",
    22: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "carol.d@test.com, remove Trundle from the favorites, and exactly that one "
        "favorite row MUST be the only database change. (2) The answer MUST report the "
        "names of the champions that remain on the favorites list. (3) Empty answer = "
        "FAIL. Reject an answer that still lists Trundle or removes a different "
        "champion.",
    23: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "david.k@test.com, save the article 'League of Legends Patch 26.19 Notes' from "
        "the article page, and exactly that one bookmark row MUST be the only database "
        "change. (2) The answer MUST report how many saved articles the account now has "
        "in total. (3) Empty answer = FAIL. Reject an answer that claims the save "
        "without the database row.",
    24: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
        "alice.j@test.com, change the account's summoner name to 'RadiantViper' and the "
        "region to EUW on the profile page, and exactly that one profile row change "
        "(summoner name and region only) MUST be the only database change. (2) The "
        "answer MUST report the updated summoner name and region shown on the account "
        "page. (3) Empty answer = FAIL. Reject an answer that claims an update the "
        "database does not show.",
    25: "FACT CHECKPOINTS: (1) The trajectory MUST create a new account on the signup "
        "page (its own username, email, display name, and a password of at least 8 "
        "characters), be signed in after creation, and exactly that one new user row "
        "MUST be the only database change. (2) The answer MUST report how many favorite "
        "champions and how many saved articles the new account starts with. (3) Empty "
        "answer = FAIL. Reject an answer whose counts do not match the new account's "
        "fresh state.",
    26: "FACT CHECKPOINTS: (1) The trajectory MUST open the How To Play page and "
        "locate the jungle section. (2) The answer MUST quote what the page says "
        "killing Baron Nashor grants the slayer's team. (3) Empty answer = FAIL. Reject "
        "a reward list invented outside the on-page sentence.",
    27: "FACT CHECKPOINTS: (1) The trajectory MUST open the How To Play page. (2) The "
        "answer MUST identify the lane described as 'the dynamite of the team' and "
        "state what the page says these champions need early on. (3) Empty answer = "
        "FAIL. Reject a lane or need not stated on the How To Play page.",
    28: "FACT CHECKPOINTS: (1) The trajectory MUST open the champion page for Sona. (2) "
        "The answer MUST list every skin name in the Available Skins carousel that "
        "includes the word 'DJ' or the word 'Pentakill', exactly as shown. (3) Empty "
        "answer = FAIL. Reject skin names not present in Sona's skin carousel.",
    29: "FACT CHECKPOINTS: (1) The trajectory MUST open the champion page for Naafiri. "
        "(2) The answer MUST report the name of Naafiri's Ultimate (R) ability and the "
        "full description of what it does, as shown on the page. (3) Empty answer = "
        "FAIL. Reject an ultimate name or description from any other champion or "
        "recalled from memory.",
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
        addition = (f', "verifier_path": "sites/league_of_legends/verify/verify_{n}.py", '
                    f'"judge_rubric": {json.dumps(RUBRICS[n], ensure_ascii=False)}')
        new_line = line.rstrip()[:-1] + addition + "}"
        # sanity: still valid JSON, five contributor keys untouched byte-for-byte
        parsed = json.loads(new_line)
        assert parsed["id"] == row["id"]
        assert new_line.startswith(line.rstrip()[:-1])
        out.append(new_line)
        changed += 1
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended grading keys to {changed} task rows in {TASKS}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Append the reviewer grading keys (verifier_path + judge_rubric) to every
sites/google_shopping/tasks.jsonl row, keeping the five contributor keys
byte-identical and adding no answer key.

Usage: python3 append_rubrics.py   (from the review worktree root)
"""
from __future__ import annotations

import json
from pathlib import Path

TASKS = Path("sites/google_shopping/tasks.jsonl")
CONTRIBUTOR_KEYS = ["web_name", "id", "ques", "web", "upstream_url"]
REVIEWER_KEYS = ["verifier_path", "judge_rubric"]

RUBRICS = {
    0: "FACT CHECKPOINTS: (1) The trajectory MUST open the homepage feed and locate the section 'The iconic trench'. (2) The answer MUST report the section's subtitle line exactly as rendered under the heading, and the current price shown on the card for \"Gap Factory Women's Modern Trench Coat\". (3) Empty answer = FAIL. Accept natural wording and price formats; reject a subtitle or price taken from a different section or card.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST open the Departments page (reached through the Search tab). (2) The answer MUST report how many department tiles are listed and the name of the department shown in the very first tile. (3) Empty answer = FAIL. Accept the count as a number or number word; reject a count or first tile taken from any other page.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST click the Explore button of the 'Bye bye blue light' section and land on the scored search it triggers. (2) The answer MUST report the exact search query that loads and the number of results reported by the results bar. (3) Empty answer = FAIL. Accept hyphen/space variants of the query wording; reject a query or count taken from the other section's Explore.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST open the homepage feed. (2) The answer MUST report the heading of the FIRST section and the heading of the SECOND section, in the order they appear. (3) Empty answer = FAIL. Both headings are required; a swapped order = FAIL.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST run the 'trench coat' search with a maximum price of 100 dollars applied and sorted by price low to high. (2) The answer MUST report the exact title and the current price of the cheapest result under those constraints. (3) Empty answer = FAIL. Reject a result outside the price cap or not cheapest under the sort.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST run the 'blue light glasses' search filtered by store 'Fashion Nova'. (2) The answer MUST report the number of results shown and the lowest current price among them. (3) Empty answer = FAIL. Reject a count or price taken without the store filter.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST run the 'trench' search with the price range 50 to 100 dollars applied. (2) The answer MUST report how many results appear and the merchant of the most expensive result within that range. (3) Empty answer = FAIL. Reject a merchant from outside the price range.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST run the 'glasses' search sorted by price high to low. (2) The answer MUST report the exact titles and prices of the top two results. (3) Empty answer = FAIL. Both titles and both prices are required; reject rows below the top two.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST open the product page for the searched product and inspect its 'Compare with similar items' section; the section's composition and order are rendered only on the product panel. (2) The answer MUST report how many of the listed products are sold by the merchant 'TikTok Shop' and the exact title of the second listed product. (3) Empty answer = FAIL. A count or title taken from any search-results surface = FAIL.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST run an empty search sorted by price high to low. (2) The answer MUST report the exact title, the price, and the merchant of the most expensive product. (3) Empty answer = FAIL. Reject a cheaper product or a partial title.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST run the 'Yes Sir' scored search. (2) The answer MUST report the product's full exact title, its current price, and its discount percentage. (3) Empty answer = FAIL. Accept badge or percent wording; reject a truncated title or another product's numbers.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST open the product page for the 'Imily Bela' product — the rating row is rendered only on the product panel, never on cards. (2) The answer MUST report the star rating and the number of reviews shown. (3) Empty answer = FAIL.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST open the product page for 'Klassy - Blue Light Blocking Glasses Tortie Brown' and inspect its 'Compare with similar items' section; the section's composition is rendered only on the product panel. (2) The answer MUST report how many of the listed products are sold by the merchant 'BlockBlueLight' and the exact title of the first listed product. (3) Empty answer = FAIL. A count or first item taken from any other surface = FAIL.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST run the merchant search for BlockBlueLight. (2) The answer MUST report both full titles, both current prices, and state which one is cheaper or that they cost the same. (3) Empty answer = FAIL. Both titles are required; an unverifiable comparison = FAIL.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST locate BOTH products — the 'trench jacket' sold by Reversible and the 'COTTON TRENCH COAT' sold by yoox.com — through searches or their product pages. (2) The answer MUST report both prices, name the cheaper one, and give the difference in dollars. (3) Empty answer = FAIL.",
    15: "FACT CHECKPOINTS: (1) The trajectory MUST open the product page for \"UNIQLO Women's Trench Coat\"; reading only the search card is a shortcut = FAIL. (2) The answer MUST report the merchant that sells it, its current price, and its original (was) price. (3) Empty answer = FAIL. Accept equivalent decimal spellings of the current price.",
    16: "FACT CHECKPOINTS: (1) The trajectory MUST search the trench coats and inspect discount badges and prices. (2) The answer MUST report the exact title, the merchant, and the current price of the cheapest trench coat that is BOTH discounted by at least 50% AND costs less than 70 dollars. (3) Empty answer = FAIL. A product failing either constraint = FAIL.",
    17: "FACT CHECKPOINTS: (1) The trajectory MUST open the Deals page. (2) The answer MUST report the exact title and the discount percentage of the product with the biggest discount. (3) Empty answer = FAIL. The title must be that product's exact name, not a longer different title embedding it.",
    18: "FACT CHECKPOINTS: (1) The trajectory MUST open the Deals page. (2) The answer MUST report the count of products with a discount of 70% or more, and the merchant that appears most often on the Deals page. (3) Empty answer = FAIL. Both facts are required; a miscount or a runner-up merchant = FAIL.",
    19: "FACT CHECKPOINTS: (1) The trajectory MUST open the Deals page. (2) The answer MUST report the exact title, the current price, and the discount percentage of the most expensive product on the page. (3) Empty answer = FAIL.",
    20: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account and open the shopping list. (2) The answer MUST report the exact title, the merchant, and the current price of EVERY saved item. (3) Empty answer = FAIL. A partial list = FAIL.",
    21: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the named demo account, save the named product from its product page, and open the shopping list. (2) The answer MUST report how many items the list contains and the price shown for the saved item. (3) Empty answer = FAIL.",
    22: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the named demo account, track the named product from its product page, and open the Price tracking page. (2) The answer MUST report which product is being tracked and its current price. (3) Empty answer = FAIL.",
    23: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the named demo account, add the named Aritzia product to the shopping list, remove the item that costs $64.99, and report the state of the list. (2) The answer MUST name the item that remains and its price. (3) Empty answer = FAIL.",
    24: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the named demo account, open each of the three Syght Glass product pages, track all three, and open the Price tracking page. (2) The answer MUST name the most expensive of the three tracked products and its price. (3) Empty answer = FAIL.",
    25: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the named demo account, find the most expensive product through an empty search sorted by price high to low, track it from its product page, and open the Price tracking page. (2) The answer MUST report the tracked product's exact title and its current price. (3) Empty answer = FAIL.",
    26: "FACT CHECKPOINTS: (1) The trajectory MUST register the specified new account through the registration form and open the shopping list. (2) The answer MUST report how many items the list contains. (3) Empty answer = FAIL.",
    27: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the named demo account and open the account page. (2) The answer MUST report the account's display name, the number of saved items, and the number of tracked items. (3) Empty answer = FAIL. All three facts are required.",
    28: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the named demo account, search the Fashion Nova blue-light glasses, compare their prices, and save the cheapest one priced ABOVE 3 dollars from its product page. (2) The answer MUST report the exact title and the price of the saved item. (3) Empty answer = FAIL. A product at or below 3 dollars = FAIL.",
    29: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the named demo account, search the edikted glasses, and save the two cheapest edikted blue-light glasses products from their product pages. (2) The answer MUST report both saved titles and the total price of the two items combined. (3) Empty answer = FAIL.",
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
        new_row["verifier_path"] = f"sites/google_shopping/verify/verify_{n}.py"
        new_row["judge_rubric"] = RUBRICS[n]
        assert "answer" not in new_row
        out.append(json.dumps(new_row, ensure_ascii=False))
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended verifier_path + judge_rubric to {len(out)} rows; contributor keys byte-identical")


if __name__ == "__main__":
    main()

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
    0: "FACT CHECKPOINTS: (1) The trajectory MUST run the site search for 'pinot noir' and "
       "apply the Price, low to high sort on the results listing. (2) The answer MUST report "
       "the result count, the cheapest bottle's name and price, and that bottle's rating state "
       "exactly as the sorted listing shows them. (3) Empty answer = FAIL. Reject values read "
       "from the unsorted listing or from any other query.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST run the site search for 'moscato' and apply "
       "the Price, low to high sort. (2) The answer MUST report the result count and the names "
       "and prices of the cheapest and the most expensive Moscato from the sorted listing. "
       "(3) Empty answer = FAIL. Reject products outside the moscato search results.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST open the Shop All Wine collection with the "
       "Varietal filter set to Cabernet Sauvignon, sort it Price low to high, and open the "
       "most expensive wine's product page. (2) The answer MUST report the filtered count, "
       "the cheapest wine's name and price, and the country of the most expensive wine. "
       "(3) Empty answer = FAIL. Reject counts or values from the unfiltered collection.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST open the Wine Sets Under $50 collection "
       "sorted by Price low to high and open the cheapest set's product page. (2) The answer "
       "MUST report how many sets the collection lists and the cheapest set's name, price, "
       "and bottle count. (3) Empty answer = FAIL. Reject the first card of the unsorted "
       "collection.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST open the Shop All Wine collection with BOTH "
       "the Country = Italy and the Sweetness = Sweet filters applied. (2) The answer MUST "
       "report how many wines match and every matching wine's name and price. (3) Empty "
       "answer = FAIL. Reject a count or list from a single-filter view.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST open the Sparkling Wine collection sorted "
       "by Price low to high. (2) The answer MUST report the cheapest sparkling wine's name "
       "and price and the total number of sparkling wines the collection lists. (3) Empty "
       "answer = FAIL. Reject values from the unsorted collection.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST open the 12-Bottle Wine Sets collection "
       "sorted by Price high to low and open the most expensive set's product page. (2) The "
       "answer MUST report the most expensive set's name, price, and the percentage discount "
       "shown on it. (3) Empty answer = FAIL. Reject a set that is not the price maximum of "
       "the sorted collection.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST open the Golden State Essentials Case "
       "product page. (2) The answer MUST list all six case wines in numbered order, state "
       "how many are red versus white as the case composition shows, and give the 6-pack's "
       "per-bottle price. (3) Empty answer = FAIL. Reject bottle lists from any other case "
       "product.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST locate the most-reviewed product (the "
       "Chardonnay Reserva) via the site search and open its product page. (2) The answer "
       "MUST report its exact name, average rating, total review count, and the percentage "
       "of reviewers who would recommend it, exactly as the product page shows. (3) Empty "
       "answer = FAIL. Reject statistics taken from any other product.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST open the 2024 Casa de Alqueria Reserva Red "
       "Blend Chile product page. (2) The answer MUST report its award (medal level, year, "
       "competition name) plus its ABV and region from the Wine Info table. (3) Empty answer "
       "= FAIL. Reject the award or specs of any other product.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST open the Cabs For Grabs Trio product page. "
        "(2) The answer MUST report how many bottles the trio contains, the name of every "
        "wine in it, and the per-bottle price shown for the 3-pack. (3) Empty answer = FAIL. "
        "Reject contents from any other pack product.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST open BOTH product pages (2021 Free Flight "
        "Pinot Noir and 2023 Closed Window Pinot Noir Willamette Valley). (2) The answer MUST "
        "report which wine has the higher ABV with both ABV values, and the 2021 Free Flight "
        "Pinot Noir's award (level, year, competition). (3) Empty answer = FAIL. Reject an "
        "ABV comparison that does not reflect both product pages.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST open the 2022 Della Flora Organic Cabernet "
        "Sauvignon product page. (2) The answer MUST report its Wine Info row values: winery, "
        "varietal, year, ABV, country, and region. (3) Empty answer = FAIL. Reject specs taken "
        "from any other product.",
    13: "FACT CHECKPOINTS: (1) As a guest, the trajectory MUST add three bottles of the 2023 "
        "Time & Tide Chardonnay Monterey County to the cart and open the cart. (2) The answer "
        "MUST report the cart subtotal, shipping charge, processing fee, total, and the "
        "free-shipping progress message exactly as the cart shows them. (3) Empty answer = "
        "FAIL. Reject totals computed from any other quantity or product.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the demo account and open the "
        "cart. (2) The answer MUST report every item with quantity and line total, the number "
        "of bottles the cart holds, the shipping charge, and the order total. (3) Empty answer "
        "= FAIL. Reject a cart reading taken while signed out.",
    15: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the demo account, complete the "
        "three-step checkout with the saved address and card, confirm 21+ at review, and "
        "reach the confirmation page. (2) The answer MUST report the new order number, the "
        "shipping city and state, and the order total. (3) Empty answer = FAIL. Reject order "
        "numbers or totals that do not come from a completed checkout.",
    16: "FACT CHECKPOINTS: (1) As a guest, the trajectory MUST add two bottles of the 2021 "
        "Valanda Tempranillo, open the cart, and report the minimum-bottles message and "
        "whether the Checkout button is usable. (2) The trajectory MUST then add one more "
        "bottle and report the resulting cart total consistent with the cart contents. "
        "(3) Empty answer = FAIL. Reject a total that does not match the final cart state.",
    17: "FACT CHECKPOINTS: (1) On a fresh session the trajectory MUST click 'No' on the age "
        "gate's 21+ question. (2) The answer MUST report exactly what the site shows next. "
        "(3) Empty answer = FAIL. Reject any message that differs from the site's actual "
        "rejection screen.",
    18: "FACT CHECKPOINTS: (1) On a fresh session the trajectory MUST leave the state dropdown "
        "unselected and click 'Yes' on the age gate. (2) The answer MUST report the exact "
        "error message the age gate shows. (3) Empty answer = FAIL. Reject any message that "
        "differs from the gate's actual validation error.",
    19: "FACT CHECKPOINTS: (1) The trajectory MUST set the Ship-to state to UT (age gate or "
        "header selector) and open the 2023 Time & Tide Chardonnay Monterey County product "
        "page. (2) The answer MUST report the exact shipping-restriction message shown on "
        "that page. (3) Empty answer = FAIL. Reject restriction text from any other state or "
        "product.",
    20: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the demo account and open the "
        "orders history plus the relevant order detail page. (2) The answer MUST report the "
        "most recent order's number, status, total, and the wine it contains. (3) Empty answer "
        "= FAIL. Reject an order that is not the most recent by date.",
    21: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the demo account, open the "
        "orders history, and open the order whose status is Processing. (2) The answer MUST "
        "report that order's number, its products, and its total. (3) Empty answer = FAIL. "
        "Reject any order that is not the Processing one.",
    22: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the demo account and open the "
        "order containing the Oh-So-Sweet Case. (2) The answer MUST report that order's "
        "number, status, total, and ship-to city and state. (3) Empty answer = FAIL. Reject "
        "the other order's facts.",
    23: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as the demo account and change the "
        "account password to the requested value, then change it back to the original. "
        "(2) The answer MUST report the account page's confirmation of each change and that "
        "the original password still signs in. (3) Empty answer = FAIL. Reject a run that "
        "leaves the password changed.",
    24: "FACT CHECKPOINTS: (1) The trajectory MUST register a brand-new account, add the 2023 "
        "Closed Window Pinot Noir Willamette Valley to the cart (enough bottles to satisfy "
        "the site's checkout minimum), place the order with its own details, and reach the "
        "confirmation page. (2) The answer MUST report the new order number and a total "
        "consistent with the placed order. (3) Empty answer = FAIL. Reject orders placed from "
        "an existing account or for a different product.",
    25: "FACT CHECKPOINTS: (1) The trajectory MUST open the Wine Club page. (2) The answer "
        "MUST report the Mixed intro case's price, processing fee, and subtotal as shown, and "
        "from the FAQ the ongoing membership price, shipment frequency, and the customer "
        "support phone number. (3) Empty answer = FAIL. Reject FAQ values that do not match "
        "the page.",
    26: "FACT CHECKPOINTS: (1) The trajectory MUST open the Wine Club page and switch through "
        "the three case options (Mixed, All Reds, All Whites). (2) The answer MUST report, "
        "for each option, how many unique wines and how many bottles of each wine the case "
        "includes. (3) Empty answer = FAIL. Reject compositions that mix up the options.",
    27: "FACT CHECKPOINTS: (1) The trajectory MUST open the Gift Cards product page. (2) The "
        "answer MUST report every gift card amount that can be selected and the price charged "
        "for the $100 card. (3) Empty answer = FAIL. Reject amounts that are not selectable "
        "on the page.",
    28: "FACT CHECKPOINTS: (1) The trajectory MUST open the Wine 101 blog and the article "
        "about how long wine lasts after opening. (2) The answer MUST report the article's "
        "title and the shelf life it gives for most full-bodied reds and whites after "
        "opening. (3) Empty answer = FAIL. Reject shelf-life values from any other article.",
    29: "FACT CHECKPOINTS: (1) The trajectory MUST open the Wine 101 blog and the article "
        "about wine storage temperatures. (2) The answer MUST report the article's title, "
        "what it names as the best place for long-term wine storage, and two other storage "
        "factors besides temperature it says to consider. (3) Empty answer = FAIL. Reject "
        "factors the article does not mention.",
}

VERIFIER_PATH = "sites/macys_wine_shop/verify/verify_{n}.py"


def main() -> None:
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    out = []
    appended = skipped = 0
    for line in lines:
        if not line.strip():
            out.append(line)
            continue
        row = json.loads(line)
        if "verifier_path" in row and "judge_rubric" in row:
            skipped += 1
            out.append(line)
            continue
        n = int(row["id"].split("--")[1])
        addition = (f', "verifier_path": "{VERIFIER_PATH.format(n=n)}", '
                    f'"judge_rubric": {json.dumps(RUBRICS[n], ensure_ascii=False)}')
        closing = line.rstrip().rfind("}")
        new_line = line.rstrip()[:closing] + addition + "}"
        assert json.loads(new_line)["ques"] == row["ques"]
        assert new_line.startswith(line.rstrip()[:closing])
        out.append(new_line)
        appended += 1
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[rubrics] appended {appended} rows, skipped {skipped} already-complete rows")


if __name__ == "__main__":
    main()

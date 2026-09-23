#!/usr/bin/env python3
"""append_rubrics.py — append the reviewer's grading keys to tasks.jsonl.

Contract (see .claude/skills/review-env/SKILL.md Step 6): the contributor rows carry
exactly {web_name, id, ques, web, upstream_url}; the reviewer appends verifier_path
+ judge_rubric per row WITHOUT touching the original five-key bytes (the original
line up to its closing brace stays byte-identical — asserted here) and without ever
adding an answer key.

Usage: python3 append_rubrics.py [--check]
  --check   verify the appended file matches the contract without writing
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RUBRICS: dict[int, str] = {
    0: "FACT CHECKPOINTS: (1) The trajectory MUST run the site search for boots and apply the "
       "Price: Low to High sort on the search results. (2) The answer MUST state the number of "
       "products the search returns, the full name, brand and price of the cheapest pair, and the "
       "full name of the second product in the sorted list. (3) An empty or vague answer is a FAIL.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST search for blackout curtain panel and open the "
       "product page of the most expensive product whose NAME includes Blackout. (2) The answer "
       "MUST state that product's exact name, its sale price, its struck-through original price as "
       "shown, and how many color options (swatches) it lists. (3) An empty answer is a FAIL.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST open the Bedding category from the Home & "
       "Lifestyle navigation and apply the Brand filter for LIZ CLAIBORNE. (2) The answer MUST "
       "state how many bedding products that brand has and the name of each, and the price range "
       "shown on the most expensive one. (3) An empty answer is a FAIL.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST open the Bulova Crystal Womens Crystal Accent "
       "Two Tone Stainless Steel Bracelet Watch 98l273 product page. (2) The answer MUST state its "
       "sale price as displayed, its average star rating, the total number of customer reviews, "
       "and the 5-star versus 1-star counts from the rating breakdown. (3) An empty answer is a FAIL.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST open the Casual Comfort Premium Ultra Soft "
       "Microfiber Wrinkle Free 6 Piece Sheet Set product page. (2) The answer MUST list the items "
       "included in the set with their dimensions and every feature called out in the product "
       "details. (3) An empty answer is a FAIL.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST open the product page of the site's most-reviewed "
       "product (an A.N.A women's long sleeve t-shirt). (2) The answer MUST state its average "
       "rating, its total review count, the headline of the most recent review, and that "
       "reviewer's star rating. (3) An empty answer is a FAIL.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST open the Pop Womens Kayley Flat Heel Slouch "
       "Boots product page as a guest, select an available color and size, add the boots to the "
       "bag, and open the bag. (2) The answer MUST state the bag subtotal, the shipping charge, "
       "and the estimated tax as shown on the bag page. (3) An empty answer is a FAIL.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account and open the bag. "
       "(2) The answer MUST list every item currently in the bag with its quantity and report the "
       "bag subtotal and the estimated tax. (3) An empty answer is a FAIL.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account and complete the "
       "three-step checkout for the items already in the bag (default saved address, default "
       "saved payment method, coupon code SAVE30 on the review step). (2) The answer MUST state "
       "the new order number, the discount amount, and the order total. (3) An empty answer is a "
       "FAIL.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account, open the order "
       "history, and open the most recent order. (2) The answer MUST state the order number, its "
       "current status, the shipping carrier and tracking number, and every item in the order "
       "with its price. (3) An empty answer is a FAIL.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST use the Track My Order page without signing in "
        "and look up the given order number with the given ZIP code. (2) The answer MUST state the "
        "order's current status, the carrier, and the items it contains. (3) An empty answer is a "
        "FAIL.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account and open the wish "
        "list. (2) The answer MUST state how many items are saved and each product's name and "
        "current price. (3) An empty answer is a FAIL.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account, open the wish "
        "list, and remove the St. John's Bay women's mock neck long sleeve t-shirt. (2) The answer "
        "MUST state how many items remain saved and the name of every remaining item. (3) An empty "
        "answer is a FAIL.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account and open the "
        "JCPenney Rewards page. (2) The answer MUST state the current reward points balance, the "
        "membership tier, and the description, points, and date of the most recent rewards "
        "activity. (3) An empty answer is a FAIL.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST open the coupons page. (2) The answer MUST "
        "report each coupon code with its discount and its valid-through date, and state which "
        "coupon stays valid the longest. (3) An empty answer is a FAIL.",
    15: "FACT CHECKPOINTS: (1) The trajectory MUST open the coupons page. (2) The answer MUST "
        "state the code of the coupon that requires a minimum purchase amount, its discount, the "
        "minimum purchase required, and the exact wording of its exclusions. (3) An empty answer "
        "is a FAIL.",
    16: "FACT CHECKPOINTS: (1) The trajectory MUST open the gift cards page and check the balance "
        "of the given gift card number, then check the same card once more. (2) The answer MUST "
        "state the balance shown and confirm it is unchanged on the second check. (3) An empty "
        "answer is a FAIL.",
    17: "FACT CHECKPOINTS: (1) The trajectory MUST use the store locator filtered to Washington "
        "state. (2) The answer MUST state how many Washington stores there are and, for the "
        "Lynnwood store, the mall name and the phone number. (3) An empty answer is a FAIL.",
    18: "FACT CHECKPOINTS: (1) The trajectory MUST open the store detail page for store number "
        "2011. (2) The answer MUST state the store's full street address, its Sunday opening "
        "hours, and every service this store offers. (3) An empty answer is a FAIL.",
    19: "FACT CHECKPOINTS: (1) The trajectory MUST register a brand new account (a name and email "
        "not used before, with the specified password), sign out, and sign back in with those "
        "credentials. (2) The answer MUST state the email registered with and what the account "
        "dashboard shows for the account name after signing back in. (3) An empty answer is a "
        "FAIL.",
    20: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account and add the "
        "specified new shipping address on the profile page. (2) The answer MUST state how many "
        "addresses the profile lists afterwards and which one is still the default. (3) An empty "
        "answer is a FAIL.",
    21: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account and add the "
        "specified new payment card on the profile page. (2) The answer MUST state how many "
        "payment methods are saved afterwards and which card is the default. (3) An empty answer "
        "is a FAIL.",
    22: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account, change the "
        "account password on the profile page, sign out, and attempt to sign in with the old and "
        "then the new password. (2) The answer MUST state whether the old password still works "
        "and what the dashboard shows after signing in with the new one. (3) An empty answer is a "
        "FAIL.",
    23: "FACT CHECKPOINTS: (1) The trajectory MUST open the Women department's mega menu and "
        "navigate to Plus Size. (2) The answer MUST state how many products that category lists, "
        "each product's brand, and the price of the most expensive one. (3) An empty answer is a "
        "FAIL.",
    24: "FACT CHECKPOINTS: (1) The trajectory MUST open the New & Trending category page. (2) The "
        "answer MUST state how many new-arrival products are shown, the name and price of the "
        "cheapest one, and the name of the most expensive one with its price. (3) An empty answer "
        "is a FAIL.",
    25: "FACT CHECKPOINTS: (1) The trajectory MUST open the Halloween Shop from the homepage "
        "category circle. (2) The answer MUST state how many products it lists, the name and price "
        "of the cheapest product, and the price of the most expensive one. (3) An empty answer is "
        "a FAIL.",
    26: "FACT CHECKPOINTS: (1) The trajectory MUST visit the homepage and the Women's Shoes "
        "category. (2) The answer MUST state the actual cheapest women's shoe with its name and "
        "price and say whether the homepage 'From $31.50' claim matches. (3) An empty answer is a "
        "FAIL.",
    27: "FACT CHECKPOINTS: (1) The trajectory MUST open BOTH the Frye and Co. Womens Miranda "
        "Stacked Heel Riding Boots page and the Pop Womens Liotta Flat Heel Motorcycle Boots page. "
        "(2) The answer MUST state which boot is rated higher, each boot's average rating and "
        "review count, and the price difference between them. (3) An empty answer is a FAIL.",
    28: "FACT CHECKPOINTS: (1) The trajectory MUST attempt to sign in with the intentionally wrong "
        "password, report the exact error message, then sign in correctly with the right password "
        "and open the order history. (2) The answer MUST quote the exact sign-in error message and "
        "identify the order still being processed or in shipment with its status and tracking "
        "number. (3) An empty answer is a FAIL.",
    29: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account, open the order "
        "history, find the order containing the Liz Claiborne women's short sleeve midi sweater "
        "dress, open it, and open the Papell Boutique evening gown from the wish list. (2) The "
        "answer MUST state that order's number, status, and total with every item's name and "
        "price, and the Papell gown's price range as shown on its product page. (3) An empty "
        "answer is a FAIL.",
}

HERE = Path(__file__).resolve().parent
TASKS = HERE.parent / "tasks.jsonl"


def main() -> int:
    check_only = "--check" in sys.argv
    original_lines = TASKS.read_text(encoding="utf-8").splitlines()
    out_lines: list[str] = []
    for line in original_lines:
        if not line.strip():
            continue
        row = json.loads(line)
        index = int(row["id"].split("--")[-1])
        rubric = RUBRICS[index]
        # byte-preserving append: original five-key prefix stays untouched
        stripped = line.rstrip()
        assert stripped.endswith("}"), f"unexpected row shape: {line[:80]}"
        prefix = stripped[:-1].rstrip()
        assert json.loads(prefix + "}") == row, "prefix must round-trip to the original row"
        appended = (prefix + ', "verifier_path": "sites/jcpenney/verify/verify_' + str(index)
                    + '.py", "judge_rubric": ' + json.dumps(rubric) + "}")
        new_row = json.loads(appended)
        assert list(new_row) == ["web_name", "id", "ques", "web", "upstream_url",
                                "verifier_path", "judge_rubric"], f"bad key order: {list(new_row)}"
        assert "answer" not in new_row, "no answer key may exist"
        assert appended.startswith(line.rstrip()[:-1].rstrip()[:0] + prefix[:len(prefix)]), "prefix bytes"
        out_lines.append(appended)
    if check_only:
        print(f"check ok: {len(out_lines)} rows would carry verifier_path + judge_rubric")
        return 0
    TASKS.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"appended verifier_path + judge_rubric to {len(out_lines)} rows of {TASKS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

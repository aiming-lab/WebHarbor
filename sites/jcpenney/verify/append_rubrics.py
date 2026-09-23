#!/usr/bin/env python3
"""append_rubrics.py — append the reviewer's grading keys to tasks.jsonl.

Contract (see .claude/skills/review-env/SKILL.md Step 6): the contributor rows carry
exactly {web_name, id, ques, web, upstream_url}; the reviewer appends verifier_path
+ judge_rubric per row WITHOUT touching the original five-key bytes (the original
line up to its closing brace stays byte-identical — asserted here) and without ever
adding an answer key.

Depth redesign (per wh-jcpenney-depth-review-evidence/REPORT.md, 2026-09-23 user
standard): the set is 15 deep-chain tasks — three KEEP entries (registration cycle,
address-book add, password-change cycle) plus twelve redesigned deep chains, each
honest-walk measured at >= 15 real interaction steps.

Usage: python3 append_rubrics.py [--check]
  --check   verify the appended file matches the contract without writing
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RUBRICS: dict[int, str] = {
    0: "FACT CHECKPOINTS: (1) The trajectory MUST register a brand new account (a name and "
       "email not used before, with the specified password), sign out, and sign back in with "
       "those credentials. (2) The answer MUST state the email registered with and what the "
       "account dashboard shows for the account name after signing back in. (3) An empty answer "
       "is a FAIL.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account alice.j@test.com "
       "and add the specified new shipping address (label \"Brother\", Alex Johnson, 582 Rainier "
       "Ave S, Seattle, WA 98144, phone (206) 555-0147, not the default) on the profile. "
       "(2) The answer MUST state how many addresses the profile lists afterwards and which one "
       "is still the default. (3) An empty answer is a FAIL.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account carol.d@test.com, "
       "change the account password to AutumnWalk45!, sign out, and sign back in with the new "
       "password. (2) The answer MUST state whether the old password still works and what the "
       "dashboard shows after signing in with the new one. (3) An empty answer is a FAIL.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST run the site search for boots, apply the "
       "Price: Low to High sort, open the cheapest pair's product page, pick a color and a size, "
       "add it to the bag, sign in with the demo account alice.j@test.com, and complete the "
       "three-step checkout (default saved address, default saved payment method, coupon code "
       "SAVE30 on the review step). (2) The answer MUST state the pair bought with its price, "
       "the new order number, the discount amount and the order total. (3) An empty answer is a "
       "FAIL.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST register a brand new account (a fresh email, "
       "password Shopper123!), search for blackout curtain panel, open the most expensive "
       "product whose NAME includes Blackout, pick a color, add it to the bag, and complete the "
       "three-step checkout with a new shipping address, a new Visa card and the code AUTUMN. "
       "(2) The answer MUST state the panel bought, the new order number, the discount amount "
       "and the order total. (3) An empty answer is a FAIL.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account carol.d@test.com, "
       "open the Biolage Color Last Shampoo from the wish list and add it to the bag, remove the "
       "St. John's Bay crew neck short sleeve t-shirt from the wish list, and complete the "
       "three-step checkout (default saved address, default saved payment method, coupon code "
       "SAVE30). (2) The answer MUST state how many items remain on the wish list, the new "
       "order number and the order total. (3) An empty answer is a FAIL.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account bob.c@test.com, "
       "open the most recent order's details from the order history, then sign out and look the "
       "same order up as a guest with its order number and shipping ZIP code. (2) The answer MUST "
       "state the status, the carrier and the items shown in each of the two views, and whether "
       "the two views agree. (3) An empty answer is a FAIL.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST read the GOSHOP15 coupon's terms on the "
       "coupons page, open the Bedding category with the LIZ CLAIBORNE brand filter, open the "
       "Liz Claiborne Luxury Performance 1000tc Sheet Set product page, add two to the bag, sign "
       "in with the demo account carol.d@test.com, and complete the three-step checkout applying "
       "GOSHOP15 (default address, default card). (2) The answer MUST state the discount the "
       "checkout applies, whether it matches the coupon's advertised terms, and the order total. "
       "(3) An empty answer is a FAIL.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account bob.c@test.com, "
       "add the specified Visa card (4111111111111155, Bob Chen, 08/2029) as the default payment "
       "method on the profile, then check out the bag choosing the new Visa at the payment step "
       "and place the order. (2) The answer MUST state the payment method shown on the placed "
       "order, how many cards the profile lists afterwards, and the order total. (3) An empty "
       "answer is a FAIL.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST use the store locator with the curbside-pickup "
       "service filter and the WA state filter, and open the detail pages of both the Alderwood "
       "Mall (Lynnwood) and Bellis Fair Mall (Bellingham) stores. (2) The answer MUST state each "
       "store's Sunday hours, phone number and services, and how the two stores differ. "
       "(3) An empty answer is a FAIL.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST check the gift card balance twice on the "
         "gift cards page, sign in with the demo account david.k@test.com, open the Papell "
         "Boutique evening gown from the wish list, add it to the bag, and complete the "
         "three-step checkout including the specified gift message (default address, default "
         "card). (2) The answer MUST state the gift card balance, the new order number and the "
         "order total. (3) An empty answer is a FAIL.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST open the Women's Shoes, women's tops and "
         "women's shorts categories, applying the Price: Low to High sort in each. (2) The "
         "answer MUST name each category's actual cheapest product with its price and state for "
         "each of the three homepage claims (women's shoes From $31.50, women's tees From "
         "$7.89, women's shorts From $12.99) whether it holds. (3) An empty answer is a FAIL.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST open the Women's Shoes category with the "
         "low-to-high and high-to-low price sorts and the Top Rated sort, and open the "
         "best-rated shoe's product page. (2) The answer MUST state the cheapest and the most "
         "expensive shoe with prices, the best-rated shoe with its price, rating and review "
         "count, the shoe with the most customer reviews with its rating, and the 5-star versus "
         "1-star breakdown of the best-rated shoe. (3) An empty answer is a FAIL.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account "
         "david.k@test.com, open the order containing the short sleeve midi sweater dress, open "
         "the Papell Boutique evening gown from the wish list, and open the JCPenney Rewards "
         "page. (2) The answer MUST state that order's status, total and the dress's price, the "
         "gown's price range, and the rewards points balance, membership tier and most recent "
         "activity. (3) An empty answer is a FAIL.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the demo account alice.j@test.com, "
         "change the Arizona hooded flannel shirt bag line's quantity to 3, remove the PUMA "
         "sweatpants line, add one St. John's Bay Womens Mock Neck Long Sleeve T-Shirt to the "
         "bag, and complete the three-step checkout (default address, default card, no coupon). "
         "(2) The answer MUST state the bag contents right before placing the order and the final "
         "order total. (3) An empty answer is a FAIL.",
}

TASKS = Path(__file__).resolve().parents[1] / "tasks.jsonl"


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
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
                    + '.py", "judge_rubric": ' + json.dumps(rubric, ensure_ascii=False) + "}")
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
    raise SystemExit(main(sys.argv[1:]))

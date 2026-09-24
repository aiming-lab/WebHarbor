#!/usr/bin/env python3
"""Append the reviewer's grading keys to sites/michaels/tasks.jsonl.

For each task row (contributor rows carry only web_name, id, ques, web,
upstream_url) this appends exactly two keys — verifier_path and judge_rubric —
by inserting them before the closing brace of the original line, so the original
five keys' bytes are untouched. Ground truth never lands in tasks.jsonl: it lives
only inside sites/michaels/verify/verify_<N>.py.

Idempotent: re-running on an already-appended file is a no-op.
"""
from __future__ import annotations

import json
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
TASKS = SITE / "tasks.jsonl"
VERIFY = "sites/michaels/verify/verify_{n}.py"

RUBRICS = {
    0: ("FACT CHECKPOINTS: The agent must have opened BOTH the Level 3 Gallery Wrapped Heavy "
        "Duty Canvas and the Level 1 Back Stapled Canvas product pages and compared their "
        "16\" x 20\" prices and ratings before buying. The cheaper 16x20 canvas is the Level 1 "
        "Back Stapled at $15.99 (vs Level 3 at $32.99). The order must be placed for "
        "alice.j@test.com with the GETMY30 promo code, shipped to her home address, paid with "
        "the Visa ending 4242. The final answer must report the order number and the order "
        "total exactly as shown on the confirmation page. An answer without the order number "
        "and total is a FAIL."),
    1: ("FACT CHECKPOINTS: The agent must have signed in as david.k@test.com, found two "
        "qualifying Studio Decor shadow boxes / display cases under the Buy One Get One FREE "
        "mix & match promo, added both to the cart, and completed the order with store "
        "pickup on the saved Discover card. The final answer must report the BOGO discount "
        "amount, the order number, and the order total from the confirmation page. Missing "
        "any of the three facts is a FAIL."),
    2: ("FACT CHECKPOINTS: The agent must have signed in as bob.c@test.com and reworked his "
        "cart through the visible cart page and the product catalog: remove the corrugated "
        "display board, swap the MDF letter B for a 13\" White MDF Uppercase Letter S (found "
        "via site search and its product page), and raise the candy wafers to 4 bags. The final "
        "answer must report each remaining item with its unit price, the new cart subtotal, "
        "and the new order total as shown in the cart summary. An answer missing either "
        "remaining item, either unit price, or either amount is a FAIL."),
    3: ("FACT CHECKPOINTS: The agent must have signed in as alice.j@test.com and opened the "
        "pickup order that used the 30% off promo code from her account order history. The "
        "final answer must report the order number, its current status, each item with its "
        "color and quantity, and the full math: subtotal, promo discount, shipping, tax, "
        "total, the card charged, and the pickup store. Missing facts are a FAIL."),
    4: ("FACT CHECKPOINTS: The agent must have opened the reviews pages of BOTH the Level 3 "
        "Gallery Wrapped Heavy Duty Canvas and the Level 1 Back Stapled Canvas. The final "
        "answer must report each product's 5-star count, 1-star count, average rating, and "
        "total review count. An answer missing either product's breakdown is a FAIL."),
    5: ("FACT CHECKPOINTS: The agent must have queried the store locator for the Cary store, "
        "for Durham (to cross-check the New Hope Commons store), and for North Carolina "
        "generally. The final answer must report the Cary store's name, Sunday hours, phone "
        "number, and that it offers balloon inflation and custom framing; the New Hope "
        "Commons store's Sunday hours and that it offers the same balloon service; and every "
        "other North Carolina location offering balloon inflation. An answer missing the "
        "Durham cross-check or any other NC balloon-inflation store is a FAIL."),
    6: ("FACT CHECKPOINTS: The agent must have signed in as alice.j@test.com, registered "
        "her for the live online Halloween kids' class on September 28 from the classes "
        "page, confirmed the signup from the account's class registrations page, and browsed "
        "the Fabric & Sewing tutorials. The final answer must report the class title, start "
        "time, platform, who hosts it, the confirmation message the site showed, the "
        "registrations-page confirmation, and the shortest NEW Fabric & Sewing tutorial with "
        "its duration. Missing facts are a FAIL."),
    7: ("FACT CHECKPOINTS: The agent must have created a new account for "
        "priya.k@example.com, added the Visa ending 6621 expiring 09/2027 to it, added the "
        "500yd. Textured Curling Ribbon and a Papercraft lined journal to her cart, applied "
        "the online 30% off code, and completed the order with store pickup. The final "
        "answer must report the order number and total from the confirmation page. An "
        "answer without both is a FAIL."),
    8: ("FACT CHECKPOINTS: The agent must have opened BOTH multipack product pages (5 Pack "
        "16x20 and 10 Pack 8x10 Super Value Canvas) and shown the area-per-dollar math for "
        "each. The 5 Pack (1,600 sq in for $12.99) gives more area per dollar than the 10 "
        "Pack (800 sq in for $12.99). The agent must then raise the 5 pack in alice's cart "
        "to 2 packs. The final answer must name the winner, show the math, and report the "
        "new cart subtotal. Missing facts are a FAIL."),
    9: ("FACT CHECKPOINTS: The agent must have opened the Savings page and the Coupon Policy "
        "page. The final answer must identify the 30% OFF Any One Regular Price Item "
        "in-store coupon, its expiry date, that it is valid in store only, the end date of "
        "the Buy One Get One frames promo, the categories the GETMY30 Savings card excludes, "
        "the per-day limit from the policy, and explain that GETMY30 cannot be stacked on top "
        "(in-store coupon vs online-only code). The agent must then sign in as bob.c@test.com, "
        "apply GETMY30 to his cart, and report the discount and the new order total from the "
        "cart summary. An answer that claims stacking is possible, or that misses the promo "
        "dates, the exclusions, or the cart amounts, is a FAIL."),
    10: ("FACT CHECKPOINTS: The agent must have signed in as carol.d@test.com, removed every "
         "canvas item from her wishlist, and saved the 6\" Glitter Tulle in Fuchsia and the "
         "1/4\" x 10yd. Grosgrain Ribbon. The final answer must report how many items the "
         "wishlist shows after the changes. An answer without the count is a FAIL."),
    11: ("FACT CHECKPOINTS: The agent must have browsed the floral category filtered to "
         "Store Pickup availability and sorted by price, identified the cheapest floral "
         "item available for pickup (the 15\" Mauve & Pale Pink Dahlia Mix Bush by Ashland "
         "at $5.19), added three to david.k@test.com's cart, and reported the item name, "
         "the price each, and the new cart subtotal. Missing facts are a FAIL."),
    12: ("FACT CHECKPOINTS: The agent must have signed in as david.k@test.com, opened his "
         "most recent order from the account order history, and reported its order number, "
         "current status, the item with its color and quantity, and the card charged. The "
         "agent must then start a reorder of that display board in White and report the "
         "updated cart total. Missing facts are a FAIL."),
    13: ("FACT CHECKPOINTS: The agent must have opened the 6\" Glitter Tulle by Celebrate It "
         "Occasions product page and listed every color it comes in with the price per "
         "roll, then signed in as carol.d@test.com, added three Fuchsia rolls, applied the "
         "online 30% off code, and reported the discount amount and the new order total "
         "from the cart summary. An answer missing any color, the price, the discount, or "
         "the total is a FAIL."),
    14: ("FACT CHECKPOINTS: The agent must have signed in as bob.c@test.com, added BOTH the "
         "National Geographic Metal Detector Starter Kit and the Snap Circuits Explorer "
         "100 Experiments to his cart under the Buy One Get One 50% off mix & match promo, "
         "and reported the BOGO discount line and the new order total from the cart "
         "summary. An answer without both amounts is a FAIL."),
    15: ("FACT CHECKPOINTS: The agent must have signed in as alice.j@test.com, updated the "
         "profile phone to (206) 555-0102, added the Beach House address (2201 Alki Ave SW, "
         "Seattle, WA 98116), and ordered the 8\" x 12\" Black Collection Display Box "
         "shipped to that address on the Mastercard ending 5309. The final answer must "
         "report the order total from the confirmation page. An answer without the total "
         "is a FAIL."),
    16: ("FACT CHECKPOINTS: The agent must have opened BOTH the Cricut Joy 2 in Jade Green "
         "and the Cricut Explore 5 in Teal bundle product pages and reported each price "
         "and rating. The Joy 2 (4.7) has the higher rating, so it must be the one added "
         "to bob.c@test.com's cart. The final answer must report both prices and ratings "
         "and the new cart subtotal. Missing facts are a FAIL."),
    17: ("FACT CHECKPOINTS: The agent must have answered from the Level 3 Gallery Wrapped "
         "Heavy Duty Canvas product page only: the description confirms archival-quality "
         "natural cotton and gesso priming; the largest size is 48\" x 48\" at $109.99, in "
         "Aisle 14 at the Parkway Supercenter store. The agent must then add the largest "
         "size to carol.d@test.com's cart and report the new subtotal. Missing facts are "
         "a FAIL."),
    18: ("FACT CHECKPOINTS: The agent must have opened BOTH the Cat in Library and the "
         "Light Up Black Cat paint-by-number product pages and compared rating and price. "
         "The Light Up Black Cat (4.5, $5.99) is higher rated than the Cat in Library "
         "(4.3, $6.99), so two Light Up Black Cat kits must be added to alice.j@test.com's "
         "cart with the GETMY30 code. The final answer must report both products' ratings "
         "and prices, the discount amount, and the new order total. Missing facts are a "
         "FAIL."),
}


def main() -> None:
    lines = TASKS.read_text(encoding="utf-8").splitlines(keepends=True)
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        row = json.loads(stripped)
        if "verifier_path" in row and "judge_rubric" in row:
            out.append(line)  # already appended (idempotent)
            continue
        assert set(row) == {"web_name", "id", "ques", "web", "upstream_url"}, row.keys()
        n = int(row["id"].rsplit("--", 1)[1])
        assert row["web"] == "http://localhost:40111/", row["web"]
        addition = (f', "verifier_path": "{VERIFY.format(n=n)}", '
                    f'"judge_rubric": {json.dumps(RUBRICS[n], ensure_ascii=False)}}}')
        assert stripped.endswith("}")
        out.append(stripped[:-1] + addition + "\n")
    TASKS.write_text("".join(out), encoding="utf-8")
    # verify: original key bytes untouched + new keys present
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        assert set(row) == {"web_name", "id", "ques", "web", "upstream_url",
                            "verifier_path", "judge_rubric"}, row.keys()
        assert line.startswith(line[:line.index(", \"verifier_path\"")]), "prefix changed"
    print(f"appended verifier_path + judge_rubric to {len(lines)} task rows")


if __name__ == "__main__":
    main()

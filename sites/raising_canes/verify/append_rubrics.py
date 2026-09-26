#!/usr/bin/env python3
"""Append verifier_path + judge_rubric to the 20 raising_canes task rows.

The 5-key prefix (web_name, id, ques, web, upstream_url) is preserved
byte-for-byte; no answer key is ever written. Rubrics are English, pure
rules (which pages MUST be opened, which facts MUST be reported); they
contain no answer values.

r2 note: the contribute fix 6a563727 re-anchored 5 task texts
(T9/T11/T12/T16/T17). The committed tasks.jsonl is produced by
sync_r2_tasks.py (same rubric texts as R2_RUBRICS there); the RUBRICS
below carry the matching r2 texts for the re-anchored rows. This script
itself is one-shot over the 5-key contribute rows and is kept for
provenance.
"""
import json
from pathlib import Path

TASKS = Path(__file__).resolve().parents[1] / "tasks.jsonl"

RUBRICS = {
    0: ("FACT CHECKPOINTS: The agent MUST navigate Order Ahead, find the Little "
        "York Road Houston restaurant, open The Box Combo item page, select the "
        "25-combo quantity tier, choose the no-coleslaw customization and the "
        "Large Sweet Tea drink option, and reach the checkout confirmation. The "
        "final answer MUST report the order number shown on the confirmation and "
        "the order total in dollars. An answer missing the order number, missing "
        "the total, or an empty answer is a FAIL."),
    1: ("FACT CHECKPOINTS: The agent MUST open the 25-, 50-, 75- and 100-Finger "
        "Tailgate item pages on the menu to read their prices, compute a "
        "per-finger price for each, identify the best-value tailgate, and place "
        "an order for that tailgate with the family-style sauce option at the "
        "McKinney North Central Expressway restaurant. The final answer MUST "
        "report the per-finger price computed for the best-value tailgate, the "
        "order number, and the order total. An answer missing any of these, or "
        "an empty answer, is a FAIL."),
    2: ("FACT CHECKPOINTS: The agent MUST sign in as Alice with the given demo "
        "credentials, find her members-only birthday offer on the Caniac Club "
        "page, order one Box Combo at the Siegen Lane Baton Rouge restaurant "
        "applying the birthday offer code, and pay with her saved Visa. The "
        "final answer MUST report the final order total after the discount and "
        "Alice's Caniac Club points balance after the order. An answer missing "
        "either value, or an empty answer, is a FAIL."),
    3: ("FACT CHECKPOINTS: The agent MUST sign in as David with the given demo "
        "credentials, open the account page to find the gift card on file and "
        "its current balance, order a 25-Finger Tailgate at the Westheimer Road "
        "Houston restaurant paying with that gift card, and re-check the "
        "remaining balance. The final answer MUST report the order number and "
        "the gift card's remaining balance after the purchase. An answer "
        "missing either value, or an empty answer, is a FAIL."),
    4: ("FACT CHECKPOINTS: The agent MUST sign in as Bob with the given demo "
        "credentials, order 25 of the 3 Finger Combo with the no-fountain-drink "
        "option plus one jug of sweet tea at the Little York Road Houston "
        "restaurant for tomorrow 12:30 PM pickup, paying with his saved Visa. "
        "The final answer MUST report the order number and the order total. An "
        "answer missing either value, or an empty answer, is a FAIL."),
    5: ("FACT CHECKPOINTS: The agent MUST open the allergen & nutritional "
        "information page and find the calorie count for one Kids Combo BEFORE "
        "ordering, then order 50 Kids Combos with the milk option for pickup "
        "today 3:00 PM at the Goleta Hollister Ave restaurant under the name "
        "given in the task, paying at the restaurant. The final answer MUST "
        "report the Kids Combo calorie count, the order number and the order "
        "total. An answer missing any of these, or an empty answer, is a FAIL."),
    6: ("FACT CHECKPOINTS: The agent MUST sign in as Alice with the given demo "
        "credentials, open her order history, identify her most recent food "
        "order, and use the reorder action on it for curbside pickup tomorrow "
        "1:30 PM at the same restaurant, paying with her saved Visa. The final "
        "answer MUST report the new order number and the new order total. An "
        "answer missing either value, or an empty answer, is a FAIL."),
    7: ("FACT CHECKPOINTS: The agent MUST search the Locations page for Baton "
        "Rouge, open the restaurant pages to compare Friday DRIVE-THRU closing "
        "hours (not dine-in hours), identify the restaurant whose drive-thru "
        "closes earliest on Friday nights, and report its street address, "
        "phone number and Friday drive-thru hours. The agent MUST then place a "
        "50-Finger Tailgate order at that restaurant for Saturday 6:00 PM "
        "pickup. The final answer MUST include the address, phone, Friday "
        "drive-thru hours, the order number and the order total. An answer "
        "missing any of these, or an empty answer, is a FAIL."),
    8: ("FACT CHECKPOINTS: The agent MUST search the Locations page for Houston "
        "with the Curbside Pickup service filter and report the number of "
        "matching restaurants, then order one Box Combo for curbside pickup "
        "today 6:30 PM at the Little York Road restaurant under the name given "
        "in the task, paying at the restaurant. The final answer MUST report "
        "the curbside count, the order number and the order total. An answer "
        "missing any of these, or an empty answer, is a FAIL."),
    9: ("FACT CHECKPOINTS: The agent MUST search the Locations page for Dallas "
        "with the Catering Delivery service filter and report how many of the "
        "restaurants are in Dallas, TX, open the Ross Avenue restaurant page "
        "to read its phone number, then order a 75-Finger Tailgate with the "
        "family-style sauce option for pickup today 5:00 PM at that restaurant "
        "under the name given in the task, paying at the restaurant. The final "
        "answer MUST report the Dallas, TX count, the Ross Avenue phone number, "
        "the order number and the order total. An answer missing any of these, "
        "or an empty answer, is a FAIL."),
    10: ("FACT CHECKPOINTS: The agent MUST open the allergen & nutritional "
         "information page and compare the sodium values of the Box Combo and "
         "the Caniac Combo, compute the calorie difference between the two "
         "combos, and order the lower-sodium combo with a Regular Sweet Tea "
         "for pickup today 1:15 PM at the Siegen Lane Baton Rouge restaurant "
         "under the name given in the task, paying at the restaurant. The "
         "final answer MUST report both sodium values, the calorie difference "
         "and the order total. An answer missing any of these, or an empty "
         "answer, is a FAIL."),
    11: ("FACT CHECKPOINTS: The agent MUST use the site search to find the "
         "Cane's Sauce menu item, report its calories per serving and its "
         "allergen letters from the nutritional information page, and order 25 "
         "servings of it for pickup today at 5:00 PM at the Government Street "
         "Baton Rouge restaurant under the name given in the task, paying at "
         "the restaurant. The final answer MUST report the calories per "
         "serving, the allergen letters, the order number and the order total. "
         "An answer missing any of these, or an empty answer, is a FAIL."),
    12: ("FACT CHECKPOINTS: The agent MUST sign in as Alice with the given demo "
         "credentials, add the Raising Cane's Retro Crewneck in size M and the "
         "Cool Cane Barking Plush Puppy to the gear cart, check whether the "
         "order qualifies for free shipping, and if not, add the cheapest "
         "accessory that crosses the free-shipping threshold, then check out "
         "to her home address with her saved Visa. The final answer MUST list "
         "every item in the order and the final total. An answer missing any "
         "item or the total, or an empty answer, is a FAIL."),
    13: ("FACT CHECKPOINTS: The agent MUST sign in as Carol with the given demo "
         "credentials, identify the cheapest adult (non-youth) hat among the "
         "headwear products, and buy one shipped to her home address paying "
         "with her saved Discover card. The final answer MUST report the hat's "
         "name, the order number and the total including shipping. An answer "
         "missing any of these, or an empty answer, is a FAIL."),
    14: ("FACT CHECKPOINTS: The agent MUST sign in as Carol with the given demo "
         "credentials, open the graduation-themed gift card product, select "
         "the $25 denomination, and check out shipped to her home address in "
         "McKinney paying with her saved Discover card. The final answer MUST "
         "report the order number and the total including shipping. An answer "
         "missing either value, or an empty answer, is a FAIL."),
    15: ("FACT CHECKPOINTS: The agent MUST sign in as Carol with the given demo "
         "credentials, register the physical Caniac Club card number given in "
         "the task on the Caniac Club page, then order a 75-Finger Tailgate "
         "for pickup tomorrow 5:30 PM at the McKinney North Central "
         "Expressway restaurant using her tailgate members-only offer, paying "
         "with her saved Discover card. The final answer MUST report the order "
         "number, the discount amount and the total. An answer missing any of "
         "these, or an empty answer, is a FAIL."),
    16: ("FACT CHECKPOINTS: The agent MUST sign in as Alice with the given demo "
         "credentials, open her order history, work out which of her food "
         "orders is the most recent one, and cancel it. The final answer MUST "
         "report the cancelled order's number, the restaurant (city) it was "
         "for, its total, how many Caniac Club points the cancellation "
         "returned to her, and her Caniac Club points balance afterwards. An "
         "answer missing any of these, or an empty answer, is a FAIL."),
    17: ("FACT CHECKPOINTS: The agent MUST search the Careers page for "
         "Restaurant Manager jobs in Texas, list every city where one is "
         "currently open, open the La Marque opening and report its street "
         "address, its reference number and the department shown for it, and "
         "separately find the Cashier opening on Polaris Parkway in Columbus, "
         "Ohio, reporting its reference number and the shift noted in its job "
         "title. The final answer MUST include every Texas city, the La Marque "
         "street address, reference number and department, the Cashier "
         "reference number and the shift. An answer missing any of these, or "
         "an empty answer, is a FAIL."),
    18: ("FACT CHECKPOINTS: The agent MUST sign in as Alice with the given demo "
         "credentials, update her profile phone number to the value given in "
         "the task, add the new address with the label given in the task to "
         "her account, and buy the Caniac Backpack shipped to that new "
         "address with her saved Visa. The final answer MUST report her new "
         "phone number, the gear order number and the total. An answer missing "
         "any of these, or an empty answer, is a FAIL."),
    19: ("FACT CHECKPOINTS: The agent MUST search the FAQ for the corporate "
         "phone number question, expand the matching FAQ entry, and report "
         "which two cities Raising Cane's lists for its Restaurant Support "
         "Offices and the Dallas-area office's phone number. The agent MUST "
         "then order a Caniac Combo with a Large Coke for pickup today 2:00 "
         "PM at the Siegen Lane Baton Rouge restaurant under the name given "
         "in the task, paying at the restaurant. The final answer MUST "
         "include both cities, the Dallas-area phone number, the order number "
         "and the order total. An answer missing any of these, or an empty "
         "answer, is a FAIL."),
}


def main():
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 20, len(lines)
    out = []
    for i, line in enumerate(lines):
        row = json.loads(line)
        prefix = line[: line.index('"verifier_path"')] if '"verifier_path"' in line else line
        assert sorted(row.keys()) == ["id", "ques", "upstream_url", "web", "web_name"], row.keys()
        row["verifier_path"] = f"sites/raising_canes/verify/verify_{i}.py"
        row["judge_rubric"] = RUBRICS[i]
        # re-serialize preserving key order of the original 5 keys, then append
        new_line = json.dumps(row, ensure_ascii=False)
        out.append(new_line)
        # byte-identity of the 5-key prefix: original line must be a prefix-safe
        # re-serialization; verify by comparing parsed 5-key subsets
        orig = json.loads(line)
        for k in ("web_name", "id", "ques", "web", "upstream_url"):
            assert row[k] == orig[k], (i, k)
        assert "answer" not in row
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended verifier_path + judge_rubric to {len(out)} rows (5-key values "
          f"unchanged, no answer key)")


if __name__ == "__main__":
    main()

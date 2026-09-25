#!/usr/bin/env python3
"""Append the reviewer grading keys to sites/porsche/tasks.jsonl.

Adds ``verifier_path`` and ``judge_rubric`` to each of the 20 rows while
keeping the original five task-definition keys byte-identical, and rewrites
the file with one JSON object per line. Idempotent: rows that already carry
the grading keys are refreshed in place. Run from the repository root:

    python3 sites/porsche/verify/append_rubrics.py
"""
import json
import pathlib
import sys

TASKS = pathlib.Path(__file__).resolve().parents[1] / "tasks.jsonl"

RUBRICS = {
    0: ("FACT CHECKPOINTS: the agent must open the 911 lineup (range page or "
        "filtered overview) and BOTH extreme 911 variant model pages, plus the "
        "Finder filtered to new 911s. The answer must name the least and most "
        "expensive 911 variants with their starting prices and the dollar "
        "difference, both top track speeds and both 0-60 mph times as read from "
        "each variant's own model page, how many 911 variants the lineup "
        "contains, how many brand-new 911s are in stock and the price of the "
        "most expensive one. An empty or partial answer is a FAIL."),
    1: ("FACT CHECKPOINTS: the agent must open the model overview filtered to "
        "the 911 range, the 911 Carrera GTS model page and the 911 Carrera GTS "
        "Cabriolet model page. The answer must report, from the GTS technical "
        "data, the engine's exact displacement and bore, the 0-60 mph time with "
        "the Sport Chrono Package, the front luggage compartment volume and the "
        "top track speed; also the GTS starting price, its leasing example and "
        "how many standard equipment highlights are listed; then the "
        "Cabriolet's starting price and 0-60 time, and which of the two is "
        "quicker. An empty or partial answer is a FAIL."),
    2: ("FACT CHECKPOINTS: the agent must open the model overview filtered to "
        "Electric and the model page of the most expensive electric variant, "
        "the Taycan Turbo GT with Weissach Package (the task names the page; "
        "the site's price tie with the plain Taycan Turbo GT is resolved by "
        "that naming). The answer must list every purely electric variant with "
        "its maximum power output and starting price, name both variants that "
        "share the highest power figure and state the shared output, and report "
        "the named variant's 0-60 mph time and top track speed. An empty or "
        "partial answer is a FAIL."),
    3: ("FACT CHECKPOINTS: the agent must open the Cayenne lineup and the "
        "Finder filtered to the Cayenne range, and the detail page of the least "
        "expensive in-stock Cayenne. The answer must report the most expensive "
        "Cayenne variant's starting MSRP and how many Cayenne variants there "
        "are, the cheapest in-stock Cayenne's price, VIN, mileage, body style, "
        "exterior color and selling Porsche Center, how much cheaper it is than "
        "the lineup MSRP, and how many Cayennes are in stock in total. An empty "
        "or partial answer is a FAIL."),
    4: ("FACT CHECKPOINTS: the agent must open the 911 Carrera (9921B2) "
        "configurator with both selections applied and the Finder filtered to "
        "new 911s. The answer must name the Jet Black Metallic paint and the "
        "single most expensive option in the catalog with their individual "
        "prices, the total configuration price including the base price, how "
        "many options the catalog offers, and the least expensive brand-new "
        "911 Carrera's price and VIN (the exact model named '911 Carrera', "
        "not the Cabriolet). An empty or partial answer is a FAIL."),
    5: ("FACT CHECKPOINTS: the agent must open all three configurator pages "
        "(9YAAI1, X1ABB1, 95BAU1). The answer must report each catalog's option "
        "count and each model's base price, identify which catalog is the "
        "largest, and name the single most expensive option across all three "
        "catalogs, the model it belongs to and its price. An empty or partial "
        "answer is a FAIL."),
    6: ("FACT CHECKPOINTS: the agent must sign in with the demo account, open "
        "the Taycan configurator with exactly two options selected whose "
        "combined price stays under $10,000, save the build under the required "
        "name, and open the saved-builds surface. The answer must name both "
        "selected options with their individual prices, the total price shown "
        "for the saved build, the Taycan's base price and the option count of "
        "its catalog. The saved_builds table must contain exactly the new "
        "named row for the demo user with those two options. An empty or "
        "partial answer is a FAIL."),
    7: ("FACT CHECKPOINTS: the agent must open the Finder filtered to manual "
        "911s, the detail page of the most expensive one, and the Finder "
        "filtered to manual transmissions across all lines. The answer must "
        "report how many manual 911s there are, the most expensive one's full "
        "name, price, VIN, exterior color, mileage and selling Porsche Center, "
        "the least expensive manual 911's name and price, and how many "
        "manual-transmission vehicles of all model lines are in stock. An "
        "empty or partial answer is a FAIL."),
    8: ("FACT CHECKPOINTS: the agent must open the Finder filtered to the "
        "Taycan range and the detail page of the least expensive purely "
        "electric Taycan. The answer must report that vehicle's full name, "
        "price, VIN, mileage, number of previous owners, interior color, "
        "drivetrain, model year and selling Porsche Center, plus how many "
        "electric Taycans are in stock in total. An empty or partial answer is "
        "a FAIL."),
    9: ("FACT CHECKPOINTS: the agent must open the Finder with the exact "
        "filter combination (pre-owned, Panamera, under $130,000, under 30,000 "
        "miles) and the cheapest match's detail page. The answer must report "
        "the cheapest match's full name, price, mileage, VIN, exterior color, "
        "transmission and selling Porsche Center, and how many pre-owned "
        "Panameras are in stock in total. An empty or partial answer is a "
        "FAIL."),
    10: ("FACT CHECKPOINTS: the agent must open the Finder filtered to new "
         "Macans and the detail page of the least expensive one. The answer "
         "must report that vehicle's price, VIN, exterior color and "
         "transmission, the exact monthly payment estimate shown on its detail "
         "page quoted word for word, the delivery, processing and handling fee "
         "from its price details, and how many brand-new Macans are in stock "
         "in total. An empty or partial answer is a FAIL."),
    11: ("FACT CHECKPOINTS: the agent must open the detail page of the most "
         "expensive Finder listing and the dealer directory entry of its "
         "selling center. The answer must report that listing's full name, "
         "VIN, exterior color and mileage, its vehicle price before fees, "
         "documentation fee and total price from the price details, the name "
         "and price of the second most expensive listing, and the partner "
         "number of the selling Porsche Center. An empty or partial answer is "
         "a FAIL."),
    12: ("FACT CHECKPOINTS: the agent must sign in with the demo account, open "
         "the Finder filtered to the Panamera range and the least expensive "
         "Panamera's detail page, save it, and open the saved-vehicles "
         "surface. The answer must report the saved vehicle's name and price "
         "exactly as shown in saved vehicles, plus its VIN and mileage, and "
         "the most expensive Panamera's name and price (unsaved). The "
         "saved_vehicles table must contain exactly one new row for the demo "
         "user pointing at that listing. An empty or partial answer is a "
         "FAIL."),
    13: ("FACT CHECKPOINTS: the agent must open the dealer directory filtered "
         "to Washington and the Washington stock leader's in-stock inventory "
         "via the Finder. The answer must report the earliest weekday-opening "
         "center's name, opening time, street address and phone number, how "
         "many Porsche Centers Washington has in total, the Washington center "
         "that lists the most vehicles in stock, that center's in-stock vehicle "
         "count, and the full names and prices of its two cheapest vehicles. "
         "An empty or partial answer is a FAIL."),
    14: ("FACT CHECKPOINTS: the agent must open the dealer directory and the "
         "largest state's listing. The answer must report the state with the "
         "most Porsche Centers and its count, the second-largest state's "
         "count, and the alphabetically first center of the largest state "
         "with its phone number, partner number, city, street address and its "
         "Sunday opening hours exactly as published, plus the third-largest "
         "state and its count. An empty or partial answer is a FAIL."),
    15: ("FACT CHECKPOINTS: the agent must open the dealer directory, the "
         "leading center's in-stock inventory via the Finder, and the detail "
         "page of its most expensive vehicle. The answer must report the "
         "center with the most in-stock vehicles and its count, that center's "
         "partner number, city and Sunday opening hours as published, and its "
         "most expensive vehicle's full name, price, VIN, mileage and exterior "
         "color. An empty or partial answer is a FAIL."),
    16: ("FACT CHECKPOINTS: the agent must open all three shop categories. The "
         "answer must report the single most expensive product across the "
         "catalog with its name, category, price and SKU, the cheapest product "
         "in that same category, and the most expensive product of each of "
         "the other two categories. An empty or partial answer is a FAIL."),
    17: ("FACT CHECKPOINTS: the agent must open the clothing category, the "
         "Classic Leather Jacket product page and the cart after each add. The "
         "answer must report the jacket's unit price and SKU, the line total "
         "for two of them and the bag's subtotal before shipping, then after "
         "adding one unit of the second most expensive clothing item the new "
         "subtotal and the total number of items in the bag. An empty or "
         "partial answer is a FAIL."),
    18: ("FACT CHECKPOINTS: the agent must open the Porsche Charge-o-mat Pro "
         "product page, the cart, checkout (signed in with the demo account, "
         "shipping to the required name and address) and the order "
         "confirmation page. The answer must report the order number, the "
         "order total, the shipping charge and the product's unit price as "
         "shown on the confirmation page. The shop_orders table must contain "
         "exactly the new matching row with its single order item. An empty "
         "or partial answer is a FAIL."),
    19: ("FACT CHECKPOINTS: the agent must register the new account with the "
         "required email, password and name, open the Finder filtered to "
         "pre-owned 911s and the least expensive one's detail page, save it, "
         "and open the saved-vehicles surface. The answer must report the "
         "saved vehicle's name, price, VIN, exterior color and selling Porsche "
         "Center as shown in saved vehicles, and how many pre-owned 911s are "
         "in stock in total. The users table must contain exactly the new row "
         "and saved_vehicles exactly one row under it. An empty or partial "
         "answer is a FAIL."),
}

def main() -> int:
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        index = int(row["id"].rsplit("--", 1)[1])
        assert row["web_name"] == "Porsche", row["web_name"]
        prefix = {k: row[k] for k in ("web_name", "id", "ques", "web", "upstream_url")}
        row = dict(prefix)
        row["verifier_path"] = f"sites/porsche/verify/verify_{index}.py"
        row["judge_rubric"] = RUBRICS[index]
        out.append(json.dumps(row, ensure_ascii=False))
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[rubrics] wrote {len(out)} rows to {TASKS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

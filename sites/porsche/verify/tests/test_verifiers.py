"""Deterministic verifier contract tests for the 20 Porsche tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a
clean seed pair; stateful tasks against the seed with the exact allowed
sqlite delta); a no-op run (homepage only, empty answer, clean DB) MUST
FAIL; a wrong answer MUST FAIL; a shortcut (correct answer with homepage-only
navigation) MUST FAIL: every task's required surface is beyond the homepage.
Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks MUST FAIL on
a state-mismatch (no DB delta) and on a wrong delta. Package tampering
(task_id mismatch, off-site URLs, missing screenshots, non-done trajectory)
MUST fail closed.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are
hand-written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, PASSWORD, RunBuilder, _acquire_seed,  # noqa: E402
                       build_run, copy_db, db_one, mutate_db, noop_run,
                       run_verifier)

STATEFUL = {6, 12, 18, 19}
READ_ONLY = sorted(set(range(20)) - STATEFUL)

FINDER = "/finder/us/en-US/search"
MODELS = "/usa/models"


# ---------------------------------------------------------------- honest answers
HONEST_ANSWERS = {
    0: ("The least expensive 911 variant is the 911 Carrera at $135,500 and the most "
        "expensive is the 911 GT3 90 F. A. Porsche at $387,000, a difference of $251,500. "
        "The 911 Carrera's top track speed is 183 mph and its 0-60 mph time is 3.9 s; "
        "the 911 GT3 90 F. A. Porsche reaches 194 mph and does 0-60 in 3.7 s. The lineup "
        "contains 23 911 variants. The Porsche Finder lists 11 brand-new 911s in stock; "
        "the most expensive one costs $314,820."),
    1: ("The 911 Carrera GTS has a 3,591 cc engine with a 97.0 mm bore. Its 0-60 mph time "
        "with the Sport Chrono Package is 2.9 s, the front luggage compartment volume is "
        "4.8 ft³ and the top track speed is 194 mph. It starts at $181,000 with a leasing "
        "example of e.g. $1,840.09 monthly lease rate, and 10 standard equipment "
        "highlights are listed. The 911 Carrera GTS Cabriolet starts at $194,900 and "
        "does 0-60 in 3.0 s. The 911 Carrera GTS is quicker."),
    2: ("The 19 purely electric variants are: Cayenne Turbo Electric (1,139 hp, $163,000), "
        "Cayenne Turbo Coupe Electric (1,139 hp, $168,000), Taycan Turbo GT with Weissach "
        "Package (1,019 hp, $243,700), Taycan Turbo GT (1,019 hp, $243,700), Taycan Turbo S "
        "(938 hp, $221,400), Taycan Turbo (871 hp, $184,600), Taycan GTS (690 hp, $157,000), "
        "Cayenne S Electric (657 hp, $126,300), Cayenne S Coupe Electric (657 hp, $131,200), "
        "Macan Turbo Electric (630 hp, $112,700), Macan GTS Electric (563 hp, $105,300), "
        "Taycan 4S (536 hp, $131,800), Macan 4S Electric (509 hp, $89,900), Cayenne Electric "
        "(435 hp, $109,000), Cayenne Coupe Electric (435 hp, $113,800), Macan 4 Electric "
        "(402 hp, $84,000), Taycan (402 hp, $111,900), Taycan 4 (402 hp, $116,000) and "
        "Macan Electric (355 hp, $80,300). The Cayenne Turbo Electric and the Cayenne Turbo "
        "Coupe Electric share the highest power figure at 1,139 hp. The most expensive "
        "electric variant is the Taycan Turbo GT with Weissach Package at $243,700; its "
        "0-60 mph time is 2.1 s and its top track speed is 190 mph."),
    3: ("The most expensive Cayenne variant in the lineup is the Cayenne Turbo GT with a "
        "starting MSRP of $214,800, and there are 19 Cayenne variants. The least expensive "
        "Cayenne currently in stock is a 2014 Porsche Cayenne at $7,795 (VIN "
        "WP1AA2A25ELA00643, 200,500 miles, SUV, Dark Blue Metallic) sold by Porsche "
        "Bellevue — that is $207,005 cheaper than the lineup MSRP. 139 Cayennes are in "
        "stock in total."),
    4: ("I selected Jet Black Metallic ($880) plus the single most expensive option for the "
        "911 Carrera (9921B2): 20\"/21\" Carrera Exclusive Design Wheels with Carbon Fiber "
        "Blades ($8,190). With the $135,500 base price the total configuration price is "
        "$144,570. The model's catalog offers 44 options. In the Porsche Finder, the least "
        "expensive brand-new 911 Carrera in stock is the 911 Carrera at $181,575 (VIN "
        "WP0AA2A99TS207294)."),
    5: ("The Cayenne (9YAAI1) offers 47 options with a base price of $89,900; the Cayenne S "
        "Electric (X1ABB1) offers 36 options with a base price of $126,300; the Macan "
        "(95BAU1) offers 44 options with a base price of $65,400. The Cayenne catalog is "
        "the largest. The single most expensive option across all three catalogs is the "
        "Club Leather Interior in Black/Barrique with Cross-Stitching at $6,220, which "
        "belongs to the Cayenne catalog."),
    6: ("I signed in as casey.taylor@test.com and built a Taycan with exactly two options: "
        "Jet Black Metallic ($840) and Gentian Blue Metallic ($1,500). I named the build "
        "'Weekend Taycan' and saved it; the saved build shows a total of $114,240. The "
        "Taycan's base price is $111,900 and its catalog offers 43 options."),
    7: ("There are 6 manual-transmission 911s listed in the Porsche Finder. The most "
        "expensive is the 911 S/T at $610,099 (VIN WP0AF2A9XRS274223, White, 4,052 miles), "
        "sold by Porsche Tacoma. The least expensive manual 911 is the 911 Carrera T at "
        "$194,155. Across all model lines, 7 manual-transmission vehicles are in stock."),
    8: ("The least expensive purely electric Taycan in stock is a 2022 Porsche Taycan 4S "
        "at $81,999 (VIN WP0AB2Y17NSA43577, 15,431 miles, 2 previous owners, Standard "
        "Interior in Black/Limestone Beige, All-wheel-drive, model year 2022), sold by "
        "Porsche Seattle North. 39 electric Taycans are in stock in total."),
    9: ("The cheapest matching pre-owned Panamera is a 2025 Porsche Panamera 4 E-Hybrid at "
        "$123,795 with 7,822 miles on the odometer (VIN WP0AE2YA3SL047104, Madeira Gold "
        "Metallic, PDK (Automatic)), sold by Porsche Bellevue. 6 pre-owned Panameras are "
        "in stock in total."),
    10: ("The least expensive brand-new Macan in stock is a 2026 Porsche Macan at $77,100 "
         "(VIN WP1AA2A54TLB20053, Carrara White Metallic, PDK (Automatic)). Its detail "
         "page shows the monthly payment estimate, quoted word for word: \"1,114.44 per "
         "month (for a 39 month lease) with $7,710.00 down. No security deposit "
         "required.\" Its price details show a Delivery, Processing and Handling Fee "
         "of $2,350.00 (Base MSRP $65,400.00, Price for Equipment $9,350.00, Total "
         "MSRP $77,100.00). 116 brand-new Macans are in stock in total."),
    11: ("The most expensive vehicle currently listed in the Porsche Finder is the 2024 "
         "Porsche 911 S/T at $610,099 (VIN WP0AF2A9XRS274223, White, 4,052 miles). Its "
         "price details show a vehicle price before fees of $609,899.00, a documentation "
         "fee of $200.00 and a total price of $610,099.00. The second most expensive "
         "listing is the 2026 Porsche 911 GT3 at $359,992. The selling Porsche Center, "
         "Porsche Tacoma, has partner number 4501962."),
    12: ("I signed in as jordan.morgan@test.com. The least expensive Panamera in stock is "
         "the Panamera 4 at $46,032 (VIN WP0AA2A7XLL103745, 56,442 miles); I saved it to "
         "my account and it appears in my saved vehicles as 'Panamera 4' at $46,032. The "
         "most expensive Panamera in stock is the Panamera GTS at $196,180 (not saved)."),
    13: ("Washington state has 4 Porsche Centers. The one that opens earliest on weekdays "
         "is Porsche Spokane, opening at 07:30 (21702 E. George Gee Avenue, phone "
         "+1 509-210-2010). The Washington center listing the most vehicles in stock is "
         "Porsche Bellevue with 236 vehicles; its two cheapest are a 2014 Porsche "
         "Cayenne at $7,795 and a 2017 Porsche Macan at $18,000."),
    14: ("California has the most Porsche Centers with 33; the second-largest state is "
         "Florida with 18. The alphabetically first California center is McKenna Porsche "
         "Norwalk (phone +1 562-868-3233, partner no. 4500334, city Norwalk, street "
         "10830 Firestone Boulevard); its Sunday opening hours as published are 10:00 - "
         "18:00. The third-largest state is Texas with 13 centers."),
    15: ("Porsche Bellevue has the most vehicles in stock according to the dealer "
         "directory, listing 236 vehicles. Its partner number is 4501966 and its city is "
         "Bellevue; its Sunday opening hours as published are 10:00 - 18:00. The most "
         "expensive vehicle it currently lists is the 2026 Porsche 911 GT3 at $359,992 "
         "(VIN WP0AC2A92TS290061, 1,824 miles, Paint To Sample: Violametallic)."),
    16: ("The single most expensive product across the entire Porsche Shop catalog is the "
         "911 Soundbar 2.0 at $4,070 (SKU WAP0509110PSDB, Home & Lifestyle). The cheapest "
         "product in Home & Lifestyle is the Porsche Taycan Turbo S wind-up toy car at "
         "$19.00. The most expensive Vehicle Accessories product is the Porsche Rear "
         "Bicycle Carrier for Taycan Cross Turismo at $3,372, and the most expensive "
         "Clothing product is the Classic Leather Jacket at $1,990."),
    17: ("The Classic Leather Jacket has a unit price of $1,990 (SKU 4056487100289). With "
         "two of them in my bag the line total is $3,980 and the bag's subtotal before "
         "shipping is $3,980. After adding one unit of the second most expensive clothing "
         "item, the Trench Coat ($1,350), the new subtotal is $5,330 and the bag holds 3 "
         "items in total."),
    18: ("I ordered the Porsche Charge-o-mat Pro ($245.00, one unit). Checking out with "
         "casey.taylor@test.com and shipping to Casey Taylor, 4500 9th Ave NE, Seattle, WA "
         "98105, the order is confirmed with order number {ORDER}, an order total of "
         "$245.00, a shipping charge of $0.00 (free) and the product's unit price of "
         "$245.00 as shown on the confirmation page."),
    19: ("I created the new My Porsche account alex.rivera@test.com (Alex Rivera). The "
         "least expensive pre-owned 911 in stock is a 2014 Porsche 911 Carrera 4S Coupe "
         "at $99,999 (VIN WP0AB2A99ES121144, Black), sold by Porsche Seattle North; I "
         "saved it to my new account and it appears in my saved vehicles. 32 pre-owned "
         "911s are in stock in total."),
}

WRONG_ANSWERS = {
    0: "The cheapest 911 is the 911 Carrera T at $135,500 and the priciest is the 911 GT3 at "
       "$387,000, a difference of $250,000. The Carrera does 190 mph and 0-60 in 3.5 s, the "
       "GT3 200 mph and 3.2 s. There are 20 911 variants. 12 new 911s are in stock and the "
       "most expensive costs $300,000.",
    1: "The 911 Carrera GTS has a 3.0-liter engine, bore 99 mm, 0-60 in 3.5 s with Sport "
       "Chrono, 5.0 ft³ front luggage, top speed 180 mph, price $190,000, lease $2,000, and "
       "8 equipment highlights. The Cabriolet is $200,000 at 3.2 s and is quicker.",
    2: "There are 18 electric variants. The Taycan Turbo S and Taycan Turbo share the top "
       "1,100 hp figure. The most expensive electric variant is the Taycan Turbo GT at "
       "$243,700; its model page reports 0-60 in 2.2 s and a top track speed of 180 mph.",
    3: "The top Cayenne MSRP is $200,000 across 15 variants. The cheapest in-stock Cayenne "
       "is $50,000 (VIN WP0AB2A25ELA00643, 20,000 miles), which is $150,000 cheaper. There "
       "are 100 Cayennes in stock.",
    4: "I picked Jet Black Metallic ($500) and the top option PDK ($5,000), totaling "
       "$141,000 with the base price. The catalog has 40 options. The cheapest new "
       "911 Carrera is the 911 Carrera Cabriolet at $180,810, VIN WP0CA2A97TS234082.",
    5: "The Cayenne has 40 options at $90,000 base, the Cayenne S Electric 30 options at "
       "$120,000, the Macan 50 options at $60,000 — the Macan catalog is the largest. The "
       "priciest option is a leather interior at $5,000 in the Macan.",
    6: "I signed in and saved 'Weekend Taycan' with Jet Black Metallic ($1,500) and 21-inch "
       "wheels ($3,000), total $116,400. The Taycan base price is $120,000 and the catalog "
       "has 50 options.",
    7: "There are 5 manual 911s. The most expensive is the 911 GT2 at $338,888 (VIN "
       "WP0AB29912S696242, Black, 28,992 miles) from Porsche Seattle North. The least "
       "expensive is the 911 Carrera T at $190,000. 6 manual vehicles are in stock overall.",
    8: "The cheapest electric Taycan is a Taycan at $79,999 (VIN WP0AA2Y18SSA000001, "
       "10,000 miles, 1 owner, black interior, rear-wheel-drive, 2023) from Porsche "
       "Bellevue. 35 electric Taycans are in stock.",
    9: "The cheapest pre-owned Panamera under $130,000 with under 30,000 miles is a "
       "Panamera 4S at $110,000 with 15,000 miles (VIN WP0AA2A7XL0000001, black, manual) "
       "from Porsche Spokane. 8 pre-owned Panameras are in stock.",
    10: "The cheapest new Macan is $70,000 (VIN WP1AA2A54TLB000001, white, manual) with a "
        "monthly estimate of $999 per month for 36 months with $5,000 down and a $300 "
        "documentation fee. 100 new Macans are in stock.",
    11: "The most expensive listing is the 911 GT2 at $338,888 (VIN WP0AB29912S696242). Its "
        "price details show $338,688 before fees, a $100 doc fee and $338,888 total. The "
        "second most expensive is the 911 S/T at $300,000. The seller's partner number is "
        "4501999.",
    12: "I signed in as jordan.morgan@test.com and saved the cheapest Panamera, the "
        "Panamera 4 E-Hybrid at $123,795 (VIN WP0AE2YA3SL047104, 7,822 miles). The most "
        "expensive Panamera is the Panamera GTS at $190,000.",
    13: "Washington has 4 Porsche Centers. Porsche Spokane opens earliest at 07:30 (21702 "
        "E. George Gee Avenue, +1 509-210-2010). The Washington center listing the most "
        "vehicles is Porsche Seattle North with 90; its two cheapest are a Cayenne at "
        "$12,000 and a Macan at $20,000.",
    14: "California has the most Porsche Centers with 33; Florida is second with 18. The "
        "alphabetically first California center is McKenna Porsche (phone +1 562-868-3233, "
        "partner 4500334, Norwalk, 10830 Firestone Blvd), open Sundays 10:00 - 18:00. The "
        "third-largest state is New York with 12.",
    15: "Porsche Seattle North has the most vehicles in stock with 90. Its partner number "
        "is 4501967, its city is Lynnwood, and its Sunday hours are 11:00 - 17:00. Its most "
        "expensive vehicle is a 911 GT3 at $300,000 (VIN WP0AC2A92TS000001, 5,000 miles, "
        "white).",
    16: "The most expensive product is the Porsche Rear Bicycle Carrier for Taycan Cross "
        "Turismo at $3,372 (SKU 9J0813601A, Vehicle Accessories). The cheapest in that "
        "category is a cleaning cloth at $13.00. The priciest Clothing item is the Trench "
        "Coat at $1,350 and the priciest Home & Lifestyle item is the Fridge – Porsche x "
        "Smeg at $3,999.",
    17: "The Classic Leather Jacket costs $1,500 (SKU 4056487100104). Two of them give a "
        "$3,000 line total and subtotal. Adding one Trench Coat ($1,350) makes the subtotal "
        "$4,350 with 3 items.",
    18: "I ordered the Porsche Charge-o-mat Pro. The order number is PSFAKEORDER1, the "
        "order total is $350.00, shipping was $25.00 and the unit price $325.00.",
    19: "I registered alex.rivera@test.com. The least expensive pre-owned 911 is the "
        "2018 Porsche 911 Carrera S at $125,990 (VIN WP0AB2A96JS123251, white) from "
        "Porsche Bellevue, saved to my account. 31 pre-owned 911s are in stock.",
}


# ---------------------------------------------------------------- honest step maps
def honest_steps(n, run):
    if n == 0:
        run.step("/", action="goto")
        run.step(f"{MODELS}/?range=911")
        run.step(f"{MODELS}/911/911-carrera/911-carrera/")
        run.step(f"{MODELS}/911/911-gt3-90-f.-a.-porsche/911-gt3-fa90/")
        run.step(f"{FINDER}?condition=new&range=911")
    elif n == 1:
        run.step("/", action="goto")
        run.step(f"{MODELS}/?range=911")
        run.step(f"{MODELS}/911/911-carrera/911-carrera-gts/")
        run.step(f"{MODELS}/911/911-carrera-cabriolet/911-carrera-gts-cabriolet/")
    elif n == 2:
        run.step("/", action="goto")
        run.step(f"{MODELS}/?fuel=Electric")
        run.step(f"{MODELS}/taycan/taycan/taycan-turbo-gt-wp/")
    elif n == 3:
        run.step("/", action="goto")
        run.step(f"{MODELS}/?range=Cayenne")
        run.step(f"{FINDER}?range=Cayenne&sort=price-asc")
        run.step("/finder/us/en-US/details/porsche-cayenne-preowned-L6LRPX")
    elif n == 4:
        run.step("/", action="goto")
        run.step("/configurator/en-US/mode/model/9921B2?opt=2T&opt=40X")
        run.step(f"{FINDER}?condition=new&range=911")
    elif n == 5:
        run.step("/", action="goto")
        run.step("/configurator/en-US/mode/model/9YAAI1")
        run.step("/configurator/en-US/mode/model/X1ABB1")
        run.step("/configurator/en-US/mode/model/95BAU1")
    elif n == 6:
        run.step("/", action="goto")
        run.step("/my-porsche/sign-in")
        run.step("/my-porsche/sign-in", action="fill",
                 params={"selector": "email", "text": "casey.taylor@test.com"})
        run.step("/my-porsche/sign-in", action="fill",
                 params={"selector": "password", "text": PASSWORD})
        run.step("/my-porsche/profile", action="click", url_after="/my-porsche/profile")
        run.step("/configurator/en-US/mode/model/Y1AAI1?opt=2T&opt=1A")
        run.step("/configurator/en-US/mode/model/Y1AAI1?opt=2T&opt=1A", action="fill",
                 params={"selector": "#build_name", "text": "Weekend Taycan"})
        run.step("/configurator/en-US/mode/model/Y1AAI1/save", action="click")
        run.step("/my-porsche/saved-builds")
    elif n == 7:
        run.step("/", action="goto")
        run.step(f"{FINDER}?transmission=Manual&range=911")
        run.step("/finder/us/en-US/details/porsche-911-st-preowned-9P2V7O")
        run.step(f"{FINDER}?transmission=Manual")
    elif n == 8:
        run.step("/", action="goto")
        run.step(f"{FINDER}?range=Taycan&fuel=Electric&sort=price-asc")
        run.step("/finder/us/en-US/details/porsche-taycan-4s-preowned-829GRG")
    elif n == 9:
        run.step("/", action="goto")
        run.step(f"{FINDER}?condition=preowned&range=Panamera&max_price=130000&max_mileage=30000")
        run.step("/finder/us/en-US/details/porsche-panamera-4-ehybrid-preowned-V3LZXR")
    elif n == 10:
        run.step("/", action="goto")
        run.step(f"{FINDER}?condition=new&range=Macan&sort=price-asc")
        run.step("/finder/us/en-US/details/porsche-macan-new-W32Q6Q")
    elif n == 11:
        run.step("/", action="goto")
        run.step(f"{FINDER}?sort=price-desc")
        run.step("/finder/us/en-US/details/porsche-911-st-preowned-9P2V7O")
        run.step("/usa/dealersearch/?q=Porsche%20Tacoma")
    elif n == 12:
        run.step("/", action="goto")
        run.step("/my-porsche/sign-in")
        run.step("/my-porsche/sign-in", action="fill",
                 params={"selector": "email", "text": "jordan.morgan@test.com"})
        run.step("/my-porsche/sign-in", action="fill",
                 params={"selector": "password", "text": PASSWORD})
        run.step("/my-porsche/profile", action="click", url_after="/my-porsche/profile")
        run.step(f"{FINDER}?range=Panamera&sort=price-asc")
        run.step("/finder/us/en-US/details/porsche-panamera-4-preowned-WK7VGZ")
        run.step("/finder/us/en-US/details/porsche-panamera-4-preowned-WK7VGZ/save", action="click")
        run.step("/my-porsche/saved-vehicles")
    elif n == 13:
        run.step("/", action="goto")
        run.step("/usa/dealersearch/?state=WA")
        run.step(f"{FINDER}?dealer=Porsche%20Bellevue&sort=price-asc")
    elif n == 14:
        run.step("/", action="goto")
        run.step("/usa/dealersearch/")
        run.step("/usa/dealersearch/?state=CA")
    elif n == 15:
        run.step("/", action="goto")
        run.step("/usa/dealersearch/")
        run.step(f"{FINDER}?dealer=Porsche%20Bellevue&sort=price-desc")
        run.step("/finder/us/en-US/details/porsche-911-gt3-preowned-82EPMQ")
    elif n == 16:
        run.step("/", action="goto")
        run.step("/shop/us/en-US/c/vehicle-accessories")
        run.step("/shop/us/en-US/c/clothing")
        run.step("/shop/us/en-US/c/home-lifestyle")
    elif n == 17:
        run.step("/", action="goto")
        run.step("/shop/us/en-US/c/clothing")
        run.step("/shop/us/en-US/p/classic-leather-jacket-P-P1140-590")
        run.step("/shop/cart", action="click")
        run.step("/shop/us/en-US/p/trench-coat-P-P1140-587")
        run.step("/shop/cart")
    elif n == 18:
        run.step("/", action="goto")
        run.step("/shop/us/en-US/p/95804490171-B")
        run.step("/shop/cart", action="click")
        run.step("/my-porsche/sign-in")
        run.step("/my-porsche/sign-in", action="fill",
                 params={"selector": "email", "text": "casey.taylor@test.com"})
        run.step("/my-porsche/sign-in", action="fill",
                 params={"selector": "password", "text": PASSWORD})
        run.step("/shop/checkout", action="click")
        run.step("/shop/checkout", action="fill",
                 params={"selector": "street", "text": "4500 9th Ave NE"})
        run.step("/shop/order/PSFIXTURE01", action="click",
                 url_after="/shop/order/PSFIXTURE01")
    elif n == 19:
        run.step("/", action="goto")
        run.step("/my-porsche/register")
        run.step("/my-porsche/register", action="fill",
                 params={"selector": "email", "text": "alex.rivera@test.com"})
        run.step("/my-porsche/register", action="fill",
                 params={"selector": "password", "text": "FastDriver9!"})
        run.step("/my-porsche/profile", action="click", url_after="/my-porsche/profile")
        run.step(f"{FINDER}?condition=preowned&range=911&sort=price-asc")
        run.step("/finder/us/en-US/details/porsche-911-carrera-4s-coupe-preowned-D4OZNP")
        run.step("/finder/us/en-US/details/porsche-911-carrera-4s-coupe-preowned-D4OZNP/save",
                 action="click")
        run.step("/my-porsche/saved-vehicles")


# ---------------------------------------------------------------- stateful deltas
CASEY_ID = 1
JORDAN_ID = 2
PANAMERA4_VEHICLE_ID = 397
CHARGEOMAT_PRODUCT_ID = 45
def _cheapest_preowned_911_id(seed: Path) -> int:
    """The r2 re-anchored T19 target: the least expensive pre-owned 911."""
    return db_one(seed, "SELECT id FROM vehicles WHERE vin = 'WP0AB2A99ES121144'")[0]


def apply_honest_delta(n, seed: Path, after: Path) -> str:
    """Copy seed -> after and apply the exact allowed DB delta. Returns the
    honest answer (task 18's order number is read back from the mutated DB)."""
    shutil.copyfile(seed, after)
    answer = HONEST_ANSWERS[n]
    if n == 6:
        mutate_db(after, [
            "INSERT INTO saved_builds (user_id, build_name, model_code, model_name, "
            "options_json, total_price, created_on) VALUES ("
            f"{CASEY_ID}, 'Weekend Taycan', 'Y1AAI1', 'Taycan', "
            "'[{\"id\": \"2T\", \"name\": \"Jet Black Metallic\", \"price\": 840}, "
            "{\"id\": \"1A\", \"name\": \"Gentian Blue Metallic\", \"price\": 1500}]', "
            "114240, '2026-09-24')",
        ])
    elif n == 12:
        mutate_db(after, [
            "INSERT INTO saved_vehicles (user_id, vehicle_id, saved_on) VALUES ("
            f"{JORDAN_ID}, {PANAMERA4_VEHICLE_ID}, '2026-09-24')",
        ])
    elif n == 18:
        mutate_db(after, [
            "INSERT INTO shop_orders (order_number, user_id, email, first_name, last_name, "
            "street, city, state, zip, subtotal_cents, shipping_cents, total_cents, status, "
            "placed_on) VALUES ('PSFIXTURE01', "
            f"{CASEY_ID}, 'casey.taylor@test.com', 'Casey', 'Taylor', "
            "'4500 9th Ave NE', 'Seattle', 'WA', '98105', 24500, 0, 24500, "
            "'confirmed', '2026-09-24')",
            "INSERT INTO shop_order_items (order_id, product_id, quantity, "
            "unit_price_cents) VALUES ("
            "(SELECT id FROM shop_orders WHERE order_number='PSFIXTURE01'), "
            f"{CHARGEOMAT_PRODUCT_ID}, 1, 24500)",
        ])
        answer = answer.replace("{ORDER}", "PSFIXTURE01")
    elif n == 19:
        nine11 = _cheapest_preowned_911_id(seed)
        mutate_db(after, [
            "INSERT INTO users (email, password_hash, first_name, last_name, created_at) "
            "VALUES ('alex.rivera@test.com', '$2b$12$fixture-hash-not-checked', "
            "'Alex', 'Rivera', '2026-09-24')",
            "INSERT INTO saved_vehicles (user_id, vehicle_id, saved_on) VALUES ("
            "(SELECT id FROM users WHERE email='alex.rivera@test.com'), "
            f"{nine11}, '2026-09-24')",
        ])
    return answer


def apply_wrong_delta(n, seed: Path, after: Path):
    """A delta that does NOT satisfy the task contract (must FAIL)."""
    shutil.copyfile(seed, after)
    if n == 6:
        mutate_db(after, [
            "INSERT INTO saved_builds (user_id, build_name, model_code, model_name, "
            "options_json, total_price, created_on) VALUES ("
            f"{CASEY_ID}, 'Wrong Build', 'Y1AAI1', 'Taycan', "
            "'[{\"id\": \"40X\", \"name\": \"Wheels\", \"price\": 8190}]', 120090, "
            "'2026-09-24')",
        ])
    elif n == 12:
        # saved the WRONG vehicle (the most expensive Panamera GTS instead)
        gts = db_one(seed, "SELECT id FROM vehicles WHERE vin='WP0AG2YAXTL070438'")[0]
        mutate_db(after, [
            "INSERT INTO saved_vehicles (user_id, vehicle_id, saved_on) VALUES ("
            f"{JORDAN_ID}, {gts}, '2026-09-24')",
        ])
    elif n == 18:
        mutate_db(after, [
            "INSERT INTO shop_orders (order_number, user_id, email, first_name, last_name, "
            "street, city, state, zip, subtotal_cents, shipping_cents, total_cents, status, "
            "placed_on) VALUES ('PSWRONG0001', "
            f"{CASEY_ID}, 'casey.taylor@test.com', 'Casey', 'Taylor', "
            "'1 Wrong St', 'Nowhere', 'XX', '00000', 24500, 999, 25499, "
            "'confirmed', '2026-09-24')",
        ])
    elif n == 19:
        # saved the WRONG 911 (the second-cheapest Carrera S instead of the
        # least-expensive Carrera 4S Coupe the task targets)
        wrong_911 = db_one(seed, "SELECT id FROM vehicles WHERE vin='WP0AB2A96JS123251'")[0]
        mutate_db(after, [
            "INSERT INTO users (email, password_hash, first_name, last_name, created_at) "
            "VALUES ('alex.rivera@test.com', '$2b$12$fixture', 'Alex', 'Rivera', "
            "'2026-09-24')",
            "INSERT INTO saved_vehicles (user_id, vehicle_id, saved_on) VALUES ("
            "(SELECT id FROM users WHERE email='alex.rivera@test.com'), "
            f"{wrong_911}, '2026-09-24')",
        ])


# ---------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def seed(tmp_path_factory):
    path = tmp_path_factory.mktemp("porsche-seed") / "porsche.db"
    return copy_db(path)


@pytest.fixture()
def workdir(tmp_path):
    return tmp_path


# ---------------------------------------------------------------- parametrized core
@pytest.mark.parametrize("n", READ_ONLY, ids=[f"ro{n}" for n in READ_ONLY])
def test_read_only_task_contract(n, seed, workdir):
    task_id = f"Porsche--{n}"
    honest = build_run(workdir / "honest", task_id,
                       lambda r: honest_steps(n, r), HONEST_ANSWERS[n])
    code, payload = run_verifier(n, honest, seed, seed)
    assert code == 0, f"honest run must PASS: {payload}"

    # no-op: FAIL
    code, payload = run_verifier(n, noop_run(workdir / "noop", task_id), seed, seed)
    assert code == 1, f"no-op must FAIL: {payload}"

    # wrong answer with honest navigation: FAIL
    wrong = build_run(workdir / "wrong", task_id,
                      lambda r: honest_steps(n, r), WRONG_ANSWERS[n])
    code, payload = run_verifier(n, wrong, seed, seed)
    assert code == 1, f"wrong answer must FAIL: {payload}"

    # shortcut: right answer, homepage-only navigation: FAIL
    shortcut = build_run(workdir / "shortcut", task_id,
                         lambda r: r.step("/", action="goto"), HONEST_ANSWERS[n])
    code, payload = run_verifier(n, shortcut, seed, seed)
    assert code == 1, f"shortcut must FAIL: {payload}"

    # mutated after-DB: FAIL (read-only contract)
    mutated = workdir / "mutated.db"
    shutil.copyfile(seed, mutated)
    mutate_db(mutated, [
        "INSERT INTO saved_builds (user_id, build_name, model_code, model_name, "
        "options_json, total_price, created_on) VALUES (1, 'Sneaky', 'Y1AAI1', 'Taycan', "
        "'[]', 111900, '2026-09-24')",
    ])
    code, payload = run_verifier(n, honest, seed, mutated)
    assert code == 1, f"mutated after-DB must FAIL: {payload}"


@pytest.mark.parametrize("n", sorted(STATEFUL), ids=[f"st{n}" for n in sorted(STATEFUL)])
def test_stateful_task_contract(n, seed, workdir):
    task_id = f"Porsche--{n}"
    after = workdir / "after.db"
    answer = apply_honest_delta(n, seed, after)
    honest = build_run(workdir / "honest", task_id,
                       lambda r: honest_steps(n, r), answer)
    code, payload = run_verifier(n, honest, seed, after)
    assert code == 0, f"honest run must PASS: {payload}"

    # no-op: FAIL
    code, payload = run_verifier(n, noop_run(workdir / "noop", task_id), seed, seed)
    assert code == 1, f"no-op must FAIL: {payload}"

    # wrong answer with honest navigation + honest delta: FAIL
    wrong = build_run(workdir / "wrong", task_id,
                      lambda r: honest_steps(n, r), WRONG_ANSWERS[n])
    code, payload = run_verifier(n, wrong, seed, after)
    assert code == 1, f"wrong answer must FAIL: {payload}"

    # shortcut: right answer, homepage-only navigation, no delta: FAIL
    shortcut = build_run(workdir / "shortcut", task_id,
                         lambda r: r.step("/", action="goto"), answer)
    code, payload = run_verifier(n, shortcut, seed, seed)
    assert code == 1, f"shortcut (no state change) must FAIL: {payload}"

    # state-mismatch: honest answer + navigation, but DB unchanged: FAIL
    code, payload = run_verifier(n, honest, seed, seed)
    assert code == 1, f"state-mismatch (missing delta) must FAIL: {payload}"

    # wrong delta: honest answer + navigation, DB mutated the wrong way: FAIL
    wrong_after = workdir / "wrong_after.db"
    apply_wrong_delta(n, seed, wrong_after)
    code, payload = run_verifier(n, honest, seed, wrong_after)
    assert code == 1, f"wrong delta must FAIL: {payload}"


# ---------------------------------------------------------------- tamper cases
def test_tampered_task_id(seed, workdir):
    run = build_run(workdir / "tampered", "Porsche--0",
                    lambda r: honest_steps(0, r), HONEST_ANSWERS[0])
    code, payload = run_verifier(1, run, seed, seed)  # verify_1 sees task_id Porsche--0
    assert code == 1, "task_id mismatch must FAIL"


def test_offsite_urls(seed, workdir):
    run = RunBuilder(workdir / "offsite", "Porsche--0")
    run.step("/", action="goto")
    run.step("https://www.porsche.com/usa/models/911/", action="goto")
    run.done(HONEST_ANSWERS[0])
    code, payload = run_verifier(0, run.root, seed, seed)
    assert code == 1, "off-site navigation must FAIL"


def test_non_done_trajectory(seed, workdir):
    run = RunBuilder(workdir / "notdone", "Porsche--0")
    run.step("/", action="goto")
    run.step(f"{MODELS}/?range=911")
    (run.root / "trajectory.json").write_text(json.dumps({
        "task_id": "Porsche--0", "start_url": BASE + "/", "final_url": BASE + "/",
        "terminated": False, "termination_reason": "max_steps", "steps": run.steps,
        "final_answer": HONEST_ANSWERS[0]}, indent=1))
    code, payload = run_verifier(0, run.root, seed, seed)
    assert code == 1, "non-done trajectory must FAIL"


def test_missing_screenshots(seed, workdir):
    run = build_run(workdir / "noshots", "Porsche--0",
                    lambda r: honest_steps(0, r), HONEST_ANSWERS[0])
    for shot in (run / "screenshots").glob("step_*.png"):
        shot.write_bytes(b"not a png")
    code, payload = run_verifier(0, run, seed, seed)
    assert code == 1, "non-PNG screenshots must FAIL"


def test_empty_answer(seed, workdir):
    run = build_run(workdir / "empty", "Porsche--0",
                    lambda r: honest_steps(0, r), "")
    code, payload = run_verifier(0, run, seed, seed)
    assert code == 1, "empty final answer must FAIL"

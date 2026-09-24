#!/usr/bin/env python3
"""append_rubrics.py — record the reviewer grading contract in tasks.jsonl.

Inserts ``verifier_path`` + ``judge_rubric`` into every task row by pure
string insertion before the closing brace: the five contributor keys
(web_name, id, ques, web, upstream_url) stay byte-identical, no ``answer`` key
is ever written, and the row stays a single JSON object on one line. Rubrics
are English and state ONLY the checking rules (which surfaces must be opened,
which facts must be quoted) — never the answers.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SITE = "micro_center"
TASKS = Path(__file__).resolve().parents[1] / "tasks.jsonl"
CONTRIBUTOR_KEYS = ("web_name", "id", "ques", "web", "upstream_url")

RUBRICS: dict[str, str] = {
    "Micro Center--0": (
        "FACT CHECKPOINTS: (1) The agent MUST sign in as alice.j@test.com on the Micro Center mirror, open the store locator and set the Rockville, MD store, and run a laptop search. (2) The agent MUST open the product page of the laptop it picks (priced under $600 and shown in stock at Rockville) and complete the pickup checkout chain (mode, pickup, payment, review, confirmation). (3) The final answer MUST quote the placed order number and the order total exactly as shown on the confirmation page. An empty answer is a FAIL. The saved-card clause is satisfiable on the mirror (checkout honors the saved card selection) but the verifier grades the order number and total."
    ),
    "Micro Center--1": (
        "FACT CHECKPOINTS: (1) The agent MUST run searches for the AM5 motherboards, the 32GB DDR5-6000 kit, and the RTX card, and open the product pages of BOTH cheapest AM5 motherboards plus the compare page before choosing the better-rated one. (2) The agent MUST open the chosen memory kit's and graphics card's product pages and visit the cart with all three items added, the memory kit at quantity 2. (3) The final answer MUST quote the combined subtotal before tax, the socket type of the chosen motherboard, and how many stores have the memory kit in stock. An empty answer is a FAIL."
    ),
    "Micro Center--2": (
        "FACT CHECKPOINTS: (1) The agent MUST open the Open Box listing and the product pages of both the open-box laptop with the biggest Excellent-condition savings and the runner-up. (2) The final answer MUST name both laptops with their new and Excellent-condition prices, list every open-box condition and price offered for the winner, state how many stores have the winner in stock, and state whether it is in stock at the Cambridge, MA store. An empty answer is a FAIL."
    ),
    "Micro Center--3": (
        "FACT CHECKPOINTS: (1) The agent MUST sign in as bob.c@test.com, search graphics "
        "cards, and open the product page of the card it picks (which must be in stock at "
        "both Dallas and Houston). (2) The agent MUST complete the pickup reservation "
        "chain with the Dallas store selected (mode, pickup, payment, review, "
        "confirmation). (3) The final answer MUST quote the order number of the placed "
        "reservation. An empty answer is a FAIL."
    ),
    "Micro Center--4": (
        "FACT CHECKPOINTS: (1) The agent MUST sign in as carol.d@test.com, open the account orders page and the detail page of the most recent order, and open both order items' product pages to check Austin, TX availability. (2) The agent MUST open the payment methods page to identify the paying saved card, submit the order cancellation, then rework the cart on the cart page: remove its most expensive item and set the Art Explosion quantity to 1. (3) The final answer MUST quote the cancelled order number, the cancelled status, the refund total, the saved card the order was paid with, and the new cart subtotal. An empty answer is a FAIL."
    ),
    "Micro Center--5": (
        "FACT CHECKPOINTS: (1) The agent MUST sign in as carol.d@test.com, search wireless mechanical keyboards, open BOTH cheapest candidates' product pages, and use the compare page before adding the better-rated one to the list. (2) The agent MUST open the account list page and remove the list's two most expensive items. (3) The final answer MUST name the keyboard kept with its price, state how many items remain on the list, and name those items. An empty answer is a FAIL."
    ),
    "Micro Center--6": (
        "FACT CHECKPOINTS: (1) The agent MUST search 27-inch monitors, open the two cheapest 27-inch monitor product pages, and use the compare page. (2) The agent MUST set the Rockville, MD store as its store, add the higher-refresh-rate monitor at quantity 2, and open the cart. (3) The final answer MUST identify the higher-refresh-rate monitor with its price, state how many stores have each monitor in stock, state whether the chosen monitor is in stock at Rockville, and quote the subtotal and estimated tax. An empty answer is a FAIL."
    ),
    "Micro Center--7": (
        "FACT CHECKPOINTS: (1) The agent MUST sign in as alice.j@test.com and open the "
        "profile and address book pages. (2) The agent MUST update the profile phone "
        "number and add the new shipping address, then make it the default. (3) The "
        "final answer MUST identify which address is now the default (name and street "
        "must match the one it added). An empty answer is a FAIL."
    ),
    "Micro Center--8": (
        "FACT CHECKPOINTS: (1) The agent MUST search case fans, open the cheapest 120mm "
        "case fan product page, and add it to the cart while signed out. (2) The agent "
        "MUST set the quantity to two and complete the shipping checkout chain (mode, "
        "shipping, payment, review, confirmation) with the given New York address and "
        "two-day shipping. (3) The final answer MUST quote the order number and the "
        "total including shipping. An empty answer is a FAIL."
    ),
    "Micro Center--9": (
        "FACT CHECKPOINTS: (1) The agent MUST search solid-state drives, open BOTH 4TB SSD product pages, and use the compare page to identify the PlayStation 5 compatible one. (2) The agent MUST set the Texas Micro Center that has it in stock as its store, add two of the drive plus the cheapest 4TB internal hard drive, and open the cart. (3) The final answer MUST quote the drive's capacity, price, and storage interface, name the Texas store, and quote the final subtotal. An empty answer is a FAIL."
    ),
    "Micro Center--10": (
        "FACT CHECKPOINTS: (1) The agent MUST sign in as david.k@test.com, open the account orders page and the recent pickup order's detail page, and open BOTH order items' product pages. (2) The agent MUST submit a 4-star review titled 'Solid purchase' for the networking device and a 3-star review titled 'Does the job' for the other item. (3) The final answer MUST quote the order number, the pickup store, and each product's review count after posting. An empty answer is a FAIL."
    ),
    "Micro Center--11": (
        "FACT CHECKPOINTS: (1) The agent MUST sign in as alice.j@test.com and open the payment methods page. (2) The agent MUST add the Mastercard ending in 5678 (expiring 05/2029) and the American Express ending in 9012 (expiring 11/2027), make the Mastercard the default, and remove the old Mastercard. (3) The final answer MUST state how many payment methods are saved, which card is the default, and which card was removed. An empty answer is a FAIL."
    ),
    "Micro Center--12": (
        "FACT CHECKPOINTS: (1) The agent MUST set the Yonkers, NY store as its store and report its Sunday hours, search wireless mice, open the product pages of the qualifying models (under $40, at least 4 stars, in stock at Yonkers), and use the compare page. (2) The agent MUST put two of the cat-themed mouse in the cart and open the cart. (3) The final answer MUST quote the Yonkers Sunday hours, the cheapest qualifying mouse's price, how many units Yonkers has left, how many stores nationwide stock it, and the cart subtotal. An empty answer is a FAIL."
    ),
    "Micro Center--13": (
        "FACT CHECKPOINTS: (1) The agent MUST search 65-inch TVs, open the cheapest "
        "qualifying TV's product page, and confirm Chicago store availability. (2) The "
        "agent MUST complete an in-store pickup checkout as a guest with the Chicago "
        "store selected (mode, pickup, payment, review, confirmation). (3) The final "
        "answer MUST quote the order number and the total. An empty answer is a FAIL."
    ),
    "Micro Center--14": (
        "FACT CHECKPOINTS: (1) The agent MUST create the account with the email frank.m@test.com via the register page. (2) The agent MUST search for and open the Bambu Lab A1 3D printer product page (the plain A1, not the mini or Combo variants), add it to the list and to the cart, and open the cart to see the estimated total with tax. (3) The agent MUST add one PLA filament spool under $15 and one PLA+ spool under $20, both shown in stock at the Cambridge, MA store, to the list, and open the list page. (4) The final answer MUST state the list's item count, quote the printer's price, and name the filament colors picked. An empty answer is a FAIL."
    ),
    "Micro Center--15": (
        "FACT CHECKPOINTS: (1) The agent MUST set the Brooklyn, NY store as its store, then search and open the product pages of the cheapest keyboard, mouse, monitor, and USB hub, each shown in stock at Brooklyn, adding all four to the cart. (2) The agent MUST open the cart. (3) The final answer MUST quote the combined subtotal and the name and price of each of the four items. An empty answer is a FAIL."
    ),
    "Micro Center--16": (
        "FACT CHECKPOINTS: (1) The agent MUST set the Rockville, MD store as its store, search 32GB DDR5-6000 kits, and use the compare page on the three cheapest RGB kits before opening its chosen kit's product page. (2) The agent MUST open the cheapest plain 32GB DDR5-6000 kit's product page, confirm both kits are in stock at Rockville, add both to the cart, and open the cart. (3) The final answer MUST quote the chosen RGB kit's CAS latency, memory timings, and voltage from its spec sheet, how many stores have it in stock, and the subtotal. An empty answer is a FAIL."
    ),
    "Micro Center--17": (
        "FACT CHECKPOINTS: (1) The agent MUST set the Cambridge, MA store as its store, open the Bambu Lab A1 3D printer product page, and open the product pages of one plain PLA filament spool under $15 and one PLA+ spool under $25 shown in stock at Cambridge, adding the printer, two of the same plain PLA spool, and the PLA+ spool to the cart, then open the cart. (2) The final answer MUST quote the plain PLA's recommended plate temperature from its spec sheet, the subtotal, and the filament colors picked. An empty answer is a FAIL."
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                         help="only verify the current tasks.jsonl contract")
    args = parser.parse_args()

    rows = TASKS.read_text(encoding="utf-8").splitlines()
    if args.check:
        for line in rows:
            row = json.loads(line)
            tid = row["id"]
            assert row.get("verifier_path") == f"sites/{SITE}/verify/verify_{int(tid.split('--')[1])}.py", tid
            assert row.get("judge_rubric") == RUBRICS[tid], tid
            assert "answer" not in row, tid
            assert list(row.keys())[:5] == list(CONTRIBUTOR_KEYS), tid
        print(f"[check] {len(rows)} rows carry verifier_path + judge_rubric; "
              "5-key prefix intact; no answer key")
        return

    out_lines = []
    for line in rows:
        row = json.loads(line)
        tid = row["id"]
        if tid not in RUBRICS:
            raise SystemExit(f"no rubric authored for {tid!r}")
        idx = int(tid.split("--")[1])
        verifier_path = f"sites/{SITE}/verify/verify_{idx}.py"
        # pure string insertion before the closing brace: the five contributor
        # keys stay byte-identical and no answer key is introduced.
        m = re.match(r"^(.*?)(\})\s*$", line, re.S)
        if not m:
            raise SystemExit(f"unexpected row format for {tid!r}")
        prefix, brace = m.group(1), m.group(2)
        addition = (f', "verifier_path": {json.dumps(verifier_path)}, '
                    f'"judge_rubric": {json.dumps(RUBRICS[tid])}')
        new_line = prefix + addition + brace
        new_row = json.loads(new_line)
        if list(new_row.keys())[:5] != list(CONTRIBUTOR_KEYS):
            raise SystemExit(f"contributor key order changed for {tid!r}")
        if "answer" in new_row:
            raise SystemExit(f"answer key introduced for {tid!r}")
        if not new_line.startswith(line[: len(prefix)]):
            raise SystemExit(f"byte prefix changed for {tid!r}")
        out_lines.append(new_line)

    TASKS.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"[append] {len(out_lines)} rows now carry verifier_path + judge_rubric "
          "(5-key byte prefix unchanged, no answer key)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Draft the 30-task list for the Google Shopping mirror.

Writes tasks.jsonl from the frozen seed DB so every question references
facts that are verified against the actual catalog at generation time.
Re-run after any catalog change; then hand-walk each task.
"""
import json
import pathlib
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
DB = HERE / "instance_seed" / "google_shopping.db"
OUT = HERE / "tasks.jsonl"
PORT = 40084
BASE = f"http://localhost:{PORT}/"
UPSTREAM = "https://shopping.google.com/"
NAME = "Google Shopping"


def q(sql, args=()):
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute(sql, args).fetchall()
    db.close()
    return [dict(r) for r in rows]


def build_tasks():
    products = q("SELECT * FROM products ORDER BY position")
    by_title = {p["title"]: p for p in products}
    trench = [p for p in products if p["feed_section"] == "The iconic trench"]
    glasses = [p for p in products if p["feed_section"] == "Bye bye blue light"]
    trench_sorted = sorted(trench, key=lambda p: p["price"])
    glasses_sorted = sorted(glasses, key=lambda p: p["price"])
    deals = sorted([p for p in products if p["discount_pct"]],
                   key=lambda p: -p["discount_pct"])

    def cheapest_trench_under(limit):
        for p in trench_sorted:
            if p["price"] < limit:
                return p
        return None

    tasks = []
    add = tasks.append

    def T(ques):
        add({"web_name": NAME, "id": f"{NAME}--{len(tasks)}", "ques": ques,
             "web": BASE, "upstream_url": UPSTREAM})

    # ---- A. homepage feed & departments --------------------------------
    gap = by_title.get("Gap Factory Women's Modern Trench Coat")
    T(f"On the homepage, find the section \"The iconic trench\". Report the "
      f"exact title of the section's subtitle line and the current price shown "
      f"on the card for \"Gap Factory Women's Modern Trench Coat\".")
    T("Open the Departments page from the \"Search\" tab. Report how many "
      "departments are listed and the name of the department shown in the "
      "very first tile.")
    T("On the homepage, click the \"Explore\" button on the \"Bye bye blue "
      "light\" section. Report the search query that loads and the number of "
      "results found.")
    T("On the homepage feed, report the heading of the FIRST section and the "
      "heading of the SECOND section, in the order they appear.")

    # ---- B. search & filter --------------------------------------------
    T("Search for \"trench coat\", set the maximum price to 100 dollars and "
      "sort by price low to high. Report the exact title and current price "
      "of the cheapest result.")
    T("Search for \"blue light glasses\" and filter by store \"Fashion Nova\". "
      "Report how many results are shown and the lowest current price among "
      "them.")
    T("Search for \"trench\" with the price range 50 to 100 dollars. Report "
      "how many results appear and the merchant of the most expensive result "
      "within that range.")
    T("Search for \"glasses\", sort by price high to low, and report the "
      "exact titles and prices of the top two results.")
    T("Search for the product \"St Barts Bluelight\". Open its product page "
      "and look at the \"Compare with similar items\" section. Report how "
      "many of the listed products are sold by the merchant \"TikTok "
      "Shop\" and the exact title of the second listed product.")
    T("Using an empty search (leave the search box empty) sorted by price "
      "high to low, find the most expensive product on the whole site. "
      "Report its exact title, its price, and its merchant.")
    T("Search for \"Yes Sir\". Report the product's full exact title, its "
      "current price, and its discount percentage.")

    # ---- C. product detail & comparison --------------------------------
    imily = by_title.get("Imily Bela Elegant Womens Long Oversized Trench "
                         "Coat Womens Windproof Long Coat")
    if imily and imily["rating"]:
        T("Search for \"Imily Bela\" and open the product page for the "
          "\"Imily Bela Elegant Womens Long Oversized Trench Coat Womens "
          "Windproof Long Coat\". Report the star rating and the number of "
          "reviews shown.")
    klassy = by_title.get("Klassy - Blue Light Blocking Glasses Tortie Brown")
    if klassy:
        T("Open the product page for \"Klassy - Blue Light Blocking Glasses "
          "Tortie Brown\" (search for \"Klassy\"). In the \"Compare with "
          "similar items\" section, report how many of the listed products "
          "are sold by the merchant \"BlockBlueLight\" and the exact title "
          "of the first listed product.")
    T("Compare the two products sold by merchant \"BlockBlueLight\". Report "
      "both full titles, both current prices, and state which one is cheaper "
      "(or that they cost the same).")
    T("Which is cheaper: the \"trench jacket\" sold by Reversible or the "
      "\"COTTON TRENCH COAT\" sold by yoox.com? Report both prices and the "
      "difference in dollars.")
    uniqlo = by_title.get("UNIQLO Women's Trench Coat")
    if uniqlo:
        T("Open the product page for \"UNIQLO Women's Trench Coat\". In the \""
          "Compare with similar items\" section, report how many of the listed "
          "products are sold by the merchant \"yoox.com\" and the exact title of "
          "the first listed product.")
    T("Find the cheapest trench coat that is discounted by at least 50% AND "
      "costs less than 70 dollars. Report its exact title, its merchant, "
      "and its current price.")

    # ---- D. deals --------------------------------------------------------
    T("Open the Deals page. Report the product with the biggest discount "
      "percentage: its exact title and the discount percentage.")
    T("On the Deals page, count how many products have a discount of 70% or "
      "more. Report the count and the merchant that appears most often on "
      "this page.")
    T("On the Deals page, find the most expensive product. Report its exact "
      "title, its current price, and its discount percentage.")

    # ---- E. auth: shopping list & price tracking -----------------------
    T("Log in with the demo account (email: alice.j@test.com, password: "
      "TestPass123!). Open your shopping list and report the exact title, "
      "the merchant, and the current price of every saved item.")
    T("Log in with the demo account (email: bob.c@test.com, password: "
      "TestPass123!). Save the product \"St Barts Bluelight\" to your "
      "shopping list. Then report how many items the list contains and the "
      "price shown for the saved item.")
    T("Log in with the demo account (email: carol.d@test.com, password: "
      "TestPass123!). Track the price of the product \"MVMT Rover Frame — "
      "Blue Light Glasses\". Then open the Price tracking page and report "
      "which product is being tracked and its current price.")
    T("Log in with the demo account (email: alice.j@test.com, password: "
      "TestPass123!). Add \"Aritzia Women's The Finch Trench Coat\" to your "
      "shopping list. Then remove the item that costs $64.99 from the list. "
      "Report which item remains in the list and its price.")
    T("Log in with the demo account (email: carol.d@test.com, password: "
      "TestPass123!). Track the prices of all three products sold by "
      "\"Syght Glass\" (search for \"Syght\"). Then report which of the three "
      "tracked products is the most expensive and its price.")
    T("Log in with the demo account (email: david.k@test.com, password: "
      "TestPass123!). Track the price of the most expensive product on the "
      "site (sort an empty search by price high to low to find it). Then "
      "open the Price tracking page and report the tracked product's exact "
      "title and current price.")
    T("Register a new account (name: Jordan Lee, email: jordan.lee@test.com, "
      "password: JordanPass99!). Then open your shopping list and report "
      "how many items it contains.")
    T("Log in with the demo account (email: alice.j@test.com, password: "
      "TestPass123!). On the account page, report the account's display "
      "name, the number of saved items, and the number of tracked items.")
    T("Log in with the demo account (email: bob.c@test.com, password: "
      "TestPass123!). Search for \"Fashion Nova\" blue-light glasses and save "
      "the cheapest one priced ABOVE 3 dollars to your shopping list (compare "
      "the Fashion Nova products first). Then report the exact title and the "
      "price of the item you saved.")
    T("Log in with the demo account (email: david.k@test.com, password: "
      "TestPass123!). Search for \"edikted\" glasses and save the two cheapest "
      "edikted blue-light glasses products to your shopping list. Then report "
      "both saved titles and the total price of the two items combined.")

    return tasks


def main():
    tasks = build_tasks()
    if not (28 <= len(tasks) <= 32):
        print(f"task count {len(tasks)} outside 28-32; adjust", file=sys.stderr)
    with OUT.open("w") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"wrote {len(tasks)} tasks -> {OUT}")


if __name__ == "__main__":
    main()

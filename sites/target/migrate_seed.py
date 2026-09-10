#!/usr/bin/env python3
"""Apply tracked Target corrections to the downloaded seed database."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "instance_seed" / "target.db"
DEEP_DISH_SKUS = {"TGT13374157", "TGT13374348"}


def fulfillment_eligible(sku: str, method: str, unavailable_modulus: int) -> bool:
    if (sku, method) in {("TGT94640332", "delivery"), ("TGT85566854", "pickup")}:
        return True
    digest = hashlib.sha256(f"{sku}:{method}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % unavailable_modulus != 0


def normalize_specs(sku: str, raw_specs: str) -> str:
    specs = json.loads(raw_specs or "[]")
    if sku not in DEEP_DISH_SKUS:
        return json.dumps(specs, ensure_ascii=False)
    for section in specs:
        if section.get("title") == "Nutrition Facts":
            section["title"] = "Nutrition Facts — entire 2-pizza package"
        if section.get("title") == "Nutrition Facts — entire 2-pizza package":
            for item in section.get("items", []):
                if item.get("label") == "Sodium":
                    item["label"] = "Sodium — package total"
    return json.dumps(specs, ensure_ascii=False)


def migrate_database(database_path: str | Path = DEFAULT_DB) -> int:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    changed = 0
    try:
        products = connection.execute(
            "SELECT id,sku,specs_json,pickup_eligible,delivery_eligible,price,list_price,deal_badge FROM products"
        ).fetchall()
        for product in products:
            pickup = int(fulfillment_eligible(product["sku"], "pickup", 5))
            delivery = int(fulfillment_eligible(product["sku"], "delivery", 11))
            specs = normalize_specs(product["sku"], product["specs_json"])
            discount = round((product["list_price"] - product["price"]) / product["list_price"] * 100) if product["list_price"] > product["price"] > 0 else 0
            deal_badge = product["deal_badge"] if discount >= 1 else ""
            corrected = (specs, pickup, delivery, deal_badge)
            current = (
                json.dumps(json.loads(product["specs_json"] or "[]"), ensure_ascii=False),
                int(product["pickup_eligible"]),
                int(product["delivery_eligible"]),
                product["deal_badge"],
            )
            if corrected != current:
                connection.execute(
                    "UPDATE products SET specs_json=?,pickup_eligible=?,delivery_eligible=?,deal_badge=? WHERE id=?",
                    (*corrected, product["id"]),
                )
                changed += 1

        bob_id = connection.execute(
            "SELECT id FROM users WHERE lower(email)=lower('bob.c@test.com')"
        ).fetchone()
        if bob_id:
            deleted = connection.execute(
                "DELETE FROM cart_items WHERE user_id=?", (bob_id["id"],)
            ).rowcount
            changed += deleted

        cart_rows = connection.execute(
            "SELECT c.id,c.fulfillment_method,c.store_id,p.pickup_eligible,p.delivery_eligible "
            "FROM cart_items c JOIN products p ON p.id=c.product_id"
        ).fetchall()
        for row in cart_rows:
            if not row["pickup_eligible"] and not row["delivery_eligible"]:
                connection.execute("DELETE FROM cart_items WHERE id=?", (row["id"],))
                changed += 1
                continue
            method = row["fulfillment_method"]
            if method == "pickup" and not row["pickup_eligible"]:
                method = "delivery" if row["delivery_eligible"] else "pickup"
            if method == "delivery" and not row["delivery_eligible"]:
                method = "pickup" if row["pickup_eligible"] else "delivery"
            store_id = row["store_id"] if method == "pickup" else None
            if method != row["fulfillment_method"] or store_id != row["store_id"]:
                connection.execute(
                    "UPDATE cart_items SET fulfillment_method=?,store_id=? WHERE id=?",
                    (method, store_id, row["id"]),
                )
                changed += 1

        if changed:
            connection.commit()
        return changed
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", nargs="?", default=str(DEFAULT_DB))
    args = parser.parse_args()
    changed = migrate_database(args.database)
    noun = "row" if changed == 1 else "rows"
    print(f"Target seed migration complete: {changed} {noun} changed.")


if __name__ == "__main__":
    main()

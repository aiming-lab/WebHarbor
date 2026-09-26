"""Per-site health probe for the Raising Cane's mirror (end-to-end)."""
import sqlite3
from pathlib import Path


def health():
    db_path = Path(__file__).resolve().parent / "instance" / "raising_canes.db"
    conn = sqlite3.connect(db_path)
    try:
        counts = {}
        for table in ["users", "menu_categories", "menu_items", "menu_option_groups",
                      "menu_options", "locations", "gear_products", "gear_variants",
                      "jobs", "faq_entries", "nutrition_rows", "articles", "promotions",
                      "caniac_offers", "gift_cards", "caniac_cards", "user_offers",
                      "food_orders", "food_order_items", "gear_orders", "addresses",
                      "payment_cards", "favorite_locations"]:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        ok = (counts["locations"] >= 900 and counts["menu_items"] >= 20
              and counts["menu_options"] >= 150 and counts["gear_products"] >= 80
              and counts["jobs"] >= 200 and counts["users"] >= 4
              and counts["nutrition_rows"] >= 100 and counts["faq_entries"] >= 80
              and counts["food_orders"] >= 4 and counts["gift_cards"] >= 5)
        return {"ok": bool(ok), "site": "raising_canes", "counts": counts}
    finally:
        conn.close()


if __name__ == "__main__":
    print(health())

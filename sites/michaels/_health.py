"""Per-site health probe for the Michaels mirror (end-to-end)."""
import sqlite3


def health():
    db_path = "instance/michaels.db"
    conn = sqlite3.connect(db_path)
    try:
        counts = {}
        for table in ["users", "products", "product_variants", "reviews", "questions",
                       "stores", "coupons", "classes", "orders", "cart_items",
                       "wishlist_items", "categories", "addresses", "payment_cards"]:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0]
        ok = (counts["products"] >= 200 and counts["stores"] >= 20
              and counts["users"] >= 4 and counts["reviews"] >= 100
              and counts["coupons"] >= 5 and counts["classes"] >= 10
              and counts["orders"] >= 4)
        return {"ok": bool(ok), "site": "michaels", "counts": counts}
    finally:
        conn.close()

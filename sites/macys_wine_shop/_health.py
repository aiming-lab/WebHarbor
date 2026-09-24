"""Per-site health probe for macys_wine_shop (end-to-end check)."""
import json
import os
import sqlite3
import urllib.request


def health():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "instance", "macys_wine_shop.db")
    checks = {}
    ok = True
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            checks["products"] = connection.execute(
                "SELECT COUNT(*) FROM products").fetchone()[0]
            checks["collections"] = connection.execute(
                "SELECT COUNT(*) FROM collections").fetchone()[0]
            checks["users"] = connection.execute(
                "SELECT COUNT(*) FROM users").fetchone()[0]
            checks["orders"] = connection.execute(
                "SELECT COUNT(*) FROM orders").fetchone()[0]
            checks["images"] = connection.execute(
                "SELECT COUNT(*) FROM product_images").fetchone()[0]
        finally:
            connection.close()
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "error": f"db: {exc}"}
    ok = (checks.get("products", 0) >= 300 and checks.get("collections", 0) >= 200
          and checks.get("users", 0) >= 4 and checks.get("images", 0) >= 300)
    return {"ok": ok, "site": "macys_wine_shop", **checks}


if __name__ == "__main__":
    print(json.dumps(health()))

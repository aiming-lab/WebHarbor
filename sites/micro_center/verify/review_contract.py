"""Precise database deltas and browser-visible guest cart evidence."""

import json, re
from verify_lib import db_query, product_by_id, order_items, order_total_consistent

OWNERS = {0: 1, 3: 2, 4: 3, 5: 3, 7: 1, 10: 4, 11: 1, 14: 5}
GUEST_CART = {
    1: {668914: 1, 664095: 2, 689783: 1},
    6: {683850: 2},
    9: {674530: 2},
    12: {697541: 2},
    15: {702087: 1, 613558: 1, 667603: 1, 612948: 1},
    16: {685119: 1, 664095: 1},
    17: {676237: 1, 512934: 2, 611534: 1},
}


def rows(db, table, key="id"):
    return {r[key]: dict(r) for r in db_query(db, f"SELECT * FROM {table}")}


def check_review_contract(judge, traj, initial, after):
    task = int(judge.task_id.rsplit("--", 1)[1])
    owner = OWNERS.get(task)
    if task in GUEST_CART:
        steps = [
            s
            for s in traj.get("steps", [])
            if "/cart"
            == __import__("urllib.parse", fromlist=["urlparse"])
            .urlparse(s.get("url_after") or s.get("url", ""))
            .path
            and s.get("action") != "done"
        ]
        text = steps[-1].get("observed_text", "") if steps else ""
        for pid, qty in GUEST_CART[task].items():
            p = product_by_id(initial, pid)
            pattern = (
                re.escape(p["name"])
                + r"(?:(?!Quantity:).)*?Quantity:\s*"
                + str(qty)
                + r"\b"
            )
            judge.check(
                f"visible_cart_{pid}",
                bool(re.search(pattern, text, re.I | re.S)),
                f'Final cart must show {p["name"]}, quantity {qty}',
            )
        judge.check(
            "cart_line_count",
            len(re.findall(r"Quantity:\s*\d+", text)) == len(GUEST_CART[task]),
            "No missing or unrequested guest cart lines",
        )
    if owner is None and task not in (8, 13):
        return
    for table in (
        "users",
        "addresses",
        "payment_cards",
        "orders",
        "cart_items",
        "list_items",
        "compare_items",
        "reviews",
        "products",
    ):
        keycol = "product_id" if table == "products" else "id"
        before = rows(initial, table, keycol)
        final = rows(after, table, keycol)
        for key, row in before.items():
            fields = set()
            may_delete = False
            if table == "cart_items" and task in (0, 3) and row["user_id"] == owner:
                may_delete = True
            if (
                table == "orders"
                and task == 4
                and row["order_number"] == "MC2608231112"
            ):
                fields = {"status"}
            if table == "users" and task == 7 and key == 1:
                fields = {"phone"}
            if table == "addresses" and task == 7 and row["user_id"] == 1:
                fields = {"is_default"}
            if table == "payment_cards" and task == 11 and row["user_id"] == 1:
                fields = {"is_default"}
                may_delete = row["brand"] == "Mastercard" and row["last4"] == "2777"
            if table == "products" and task == 10 and key in (675726, 673901):
                fields = {"rating", "review_count"}
            ok = (key not in final and may_delete) or (
                key in final
                and all(
                    final[key].get(k) == v for k, v in row.items() if k not in fields
                )
            )
            judge.check(
                f"preserve_{table}_{key}",
                ok,
                "Only requested cells and records may change",
            )
        added = [r for k, r in final.items() if k not in before]
        allowed = {
            "users": task == 14,
            "addresses": task == 7,
            "payment_cards": task == 11,
            "orders": task in (0, 3, 8, 13),
            "cart_items": task == 14,
            "list_items": task in (5, 14),
            "compare_items": task == 5,
            "reviews": task == 10,
            "products": False,
        }[table]
        judge.check(
            "insert_allowed_" + table, allowed or not added, "No unrelated inserts"
        )
        for row in added:
            if "user_id" in row:
                judge.check(
                    f"insert_owner_{table}_{row[keycol]}",
                    row["user_id"] == (owner or 0),
                    "Correct owner for inserted rows",
                )
        counts = {
            "users": 1,
            "addresses": 1,
            "payment_cards": 2,
            "orders": 1,
            "cart_items": 1,
            "list_items": 1 if task == 5 else 3,
            "reviews": 2,
        }
        if allowed and table in counts:
            judge.check(
                "insert_count_" + table,
                len(added) == counts[table],
                "Exact number of requested rows",
            )
    if task in (0, 3, 8, 13):
        initial_orders = rows(initial, "orders")
        orders = [
            r for k, r in rows(after, "orders").items() if k not in initial_orders
        ]
        if len(orders) != 1:
            return
        order = orders[0]
        items = order_items(order)
        judge.check(
            "consistent_order_amounts",
            order_total_consistent(order),
            "Line items, subtotal, tax and total reconcile",
        )
        judge.check(
            "new_order_pending",
            order["status"] == ("Preparing to Ship" if task == 8 else "Processing"),
            "New order has expected status",
        )
        for item in items:
            p = product_by_id(initial, int(item["product_id"]))
            judge.check(
                "catalog_item_" + str(item["product_id"]),
                bool(p)
                and item["name"] == p["name"]
                and abs(item["price"] - p["price"]) < 0.011
                and item["qty"] > 0,
                "Use real product identity and catalog price",
            )
        old_cart = db_query(
            initial, "SELECT * FROM cart_items WHERE user_id=?", (owner or 0,)
        )
        if task == 0:
            old_cart = [
                r
                for r in old_cart
                if db_query(
                    initial,
                    "SELECT id FROM store_stock WHERE product_id=? AND store_id='085' AND status='in stock' AND qty>=?",
                    (r["product_id"], r["qty"]),
                )
            ]
        for row in old_cart:
            judge.check(
                "retain_cart_" + str(row["id"]),
                sum(
                    i["qty"] for i in items if int(i["product_id"]) == row["product_id"]
                )
                == row["qty"],
                "Preserve existing pending cart quantities",
            )
        judge.check(
            "exact_order_line_count",
            len(items) == len(old_cart) + 1,
            "Only requested product is added to pending order",
        )
        judge.check(
            "consumed_cart",
            not db_query(
                after, "SELECT id FROM cart_items WHERE user_id=?", (owner or 0,)
            ),
            "Purchased cart is consumed",
        )
        if task == 0:
            cards = db_query(
                initial, "SELECT * FROM payment_cards WHERE user_id=1 AND brand='Visa'"
            )
            judge.check(
                "saved_visa_payment",
                any(
                    c["last4"] in order["payment"] and "Visa" in order["payment"]
                    for c in cards
                ),
                "Use Alice’s saved Visa",
            )

"""Reviewer checks for precise ownership and preservation inside writable tables."""

from collections import Counter
from verify_lib import db_query

OWNERS = {
    0: 1,
    1: 4,
    2: 2,
    6: 1,
    7: 5,
    8: 1,
    10: 3,
    11: 4,
    12: 4,
    13: 3,
    14: 2,
    15: 1,
    16: 2,
    17: 3,
    18: 1,
}
CART_PRODUCTS = {
    2: {37, 91, 301},
    8: {106},
    11: {},
    12: {91},
    13: {114},
    14: {},
    16: {},
    17: {294},
    18: {},
}
# Product identifiers come from the captured catalog, not a submitted answer.
SLUGS = {
    11: ["15-mauve-pale-pink-dahlia-mix-bush-by-ashland-10811002"],
    14: [
        "national-geographic-metal-detector-starter-kit-10758215",
        "snap-circuits-explorer-100-experiments-10567231",
    ],
    16: ["cricut-joy-2-in-jade-green-essential-bundle-10815288"],
    18: [
        "light-up-black-cat-paint-by-number-acrylic-surface-kit-by-artist-s-loft-10808372"
    ],
}
CHECKOUT = {0, 1, 7, 15}


def rows(db, table):
    return {r["id"]: dict(r) for r in db_query(db, f"SELECT * FROM {table}")}


def check_review_contract(judge, traj, initial, after):
    task = int(judge.task_id.rsplit("--", 1)[1])
    owner = OWNERS.get(task)
    if owner is None:
        return
    mutable = {
        "users",
        "addresses",
        "payment_cards",
        "cart_items",
        "wishlist_items",
        "class_registrations",
        "orders",
        "order_items",
    }
    initial_orders = rows(initial, "orders")
    final_orders = rows(after, "orders")
    new_orders = [r for k, r in final_orders.items() if k not in initial_orders]
    target_products = set(CART_PRODUCTS.get(task, ()))
    for slug in SLUGS.get(task, []):
        target_products.update(
            r["id"]
            for r in db_query(initial, "SELECT id FROM products WHERE slug=?", (slug,))
        )
    for table in mutable:
        before = rows(initial, table)
        final = rows(after, table)
        for key, row in before.items():
            fields = set()
            may_delete = False
            if table == "cart_items" and row["user_id"] == owner:
                if task in CHECKOUT:
                    may_delete = True
                elif row["product_id"] in target_products:
                    fields = {"qty"}
                    if task == 2:
                        may_delete = True
            if (
                task == 10
                and table == "wishlist_items"
                and row["user_id"] == owner
                and row["product_id"] in {115, 116, 118}
            ):
                may_delete = True
            if task == 15 and table == "users" and row["id"] == owner:
                fields = {"phone"}
            ok = (key not in final and may_delete) or (
                key in final
                and all(
                    final[key].get(k) == v for k, v in row.items() if k not in fields
                )
            )
            judge.check(
                f"preserve_{table}_{key}", ok, "No unrelated row or field changes"
            )
        added = [row for key, row in final.items() if key not in before]
        allowed = False
        if table == "cart_items":
            allowed = task in CART_PRODUCTS
        if table in ("orders", "order_items"):
            allowed = task in CHECKOUT
        if table == "users":
            allowed = task == 7
        if table == "addresses":
            allowed = task == 15
        if table == "payment_cards":
            allowed = task == 7
        if table == "wishlist_items":
            allowed = task == 10
        if table == "class_registrations":
            allowed = task == 6
        judge.check(
            "allowed_insert_" + table,
            allowed or not added,
            "No extra unrelated inserts",
        )
        for row in added:
            if "user_id" in row:
                judge.check(
                    f'new_owner_{table}_{row["id"]}',
                    row["user_id"] == owner,
                    "Inserted rows belong to the target user",
                )
            if table == "order_items":
                judge.check(
                    "new_item_order",
                    row["order_id"] in {o["id"] for o in new_orders},
                    "Items belong only to the new order",
                )
            if table == "cart_items":
                judge.check(
                    "new_cart_product",
                    row["product_id"] in target_products,
                    "Only requested cart products may be added",
                )
        if (
            table in ("users", "addresses", "payment_cards", "class_registrations")
            and allowed
        ):
            judge.check(
                "one_added_" + table,
                len(added) == 1,
                "Exactly one requested new record",
            )
    if task in CHECKOUT:
        judge.check("exact_order_count", len(new_orders) == 1, "Exactly one new order")
        judge.check(
            "cart_consumed",
            not db_query(after, "SELECT id FROM cart_items WHERE user_id=?", (owner,)),
            "Checkout consumes the target cart",
        )
        if len(new_orders) == 1:
            items = [
                dict(r)
                for r in db_query(
                    after,
                    "SELECT * FROM order_items WHERE order_id=?",
                    (new_orders[0]["id"],),
                )
            ]
            old_cart = db_query(
                initial, "SELECT * FROM cart_items WHERE user_id=?", (owner,)
            )
            for c in old_cart:
                matches = [
                    i
                    for i in items
                    if i["product_id"] == c["product_id"]
                    and i["variant_sku"] == c["variant_sku"]
                    and i["color"] == c["color"]
                    and i["qty"] == c["qty"]
                ]
                judge.check(
                    f'kept_pending_item_{c["id"]}',
                    len(matches) == 1,
                    "Preserve each original cart product, variant and quantity",
                )
            judge.check(
                "order_items_math",
                abs(
                    sum(i["unit_price"] * i["qty"] for i in items)
                    - new_orders[0]["subtotal"]
                )
                < 0.011,
                "Item amounts reconcile to order subtotal",
            )

            expected = Counter((c["product_id"], c["qty"]) for c in old_cart)
            expected.update(
                {
                    0: [(291, 2)],
                    1: [(5, 1), (302, 1)],
                    7: [(110, 1), (166, 1)],
                    15: [(142, 1)],
                }[task]
            )
            judge.check(
                "exact_purchased_products",
                Counter((i["product_id"], i["qty"]) for i in items) == expected,
                "Only requested products and quantities plus the pending cart",
            )
            for item in items:
                catalog = db_query(
                    initial, "SELECT * FROM products WHERE id=?", (item["product_id"],)
                )
                variants = (
                    db_query(
                        initial,
                        "SELECT * FROM product_variants WHERE product_id=? AND sku=?",
                        (item["product_id"], item["variant_sku"]),
                    )
                    if item["variant_sku"]
                    else []
                )
                price = (
                    variants[0]["price"]
                    if variants
                    else catalog[0]["price"] if catalog else None
                )
                valid = (
                    bool(catalog)
                    and item["name"] == catalog[0]["name"]
                    and price is not None
                    and abs(item["unit_price"] - price) < 0.011
                )
                if item["variant_sku"]:
                    valid = (
                        valid
                        and bool(variants)
                        and item["color"] == variants[0]["color"]
                    )
                judge.check(
                    "catalog_purchase_" + str(item["id"]),
                    valid,
                    "Catalog product, variant and price must match",
                )

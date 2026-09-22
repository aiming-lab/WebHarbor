"""Supplementary comparison checks anchored to the reviewed seed."""

from pathlib import Path
import hashlib, json, re
from decimal import Decimal
from urllib.parse import urlsplit, parse_qs
from verify_lib import navigated_path, shot_at
import answers

HERE = Path(__file__).parent
SEED = json.loads((HERE / "reviewed_seed.json").read_text())
CONFIG = json.loads((HERE / "revisions.json").read_text())


def digest(x):
    return hashlib.sha256(
        json.dumps(x, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"(?<=\d),(?=\d)", "", s.casefold())).replace(
        "–", "-"
    )


def money(s, n):
    return any(
        Decimal(x) == Decimal(str(n))
        for x in re.findall(r"\$\s*(\d+(?:\.\d+)?)", norm(s))
    )


def labelled(s, label, n):
    values = []
    for m in re.finditer(label, norm(s)):
        tail = norm(s)[m.end() : m.end() + 70]
        v = re.search(r"\$\s*(\d+(?:\.\d+)?)", tail)
        if v:
            values.append(Decimal(v[1]))
    return bool(values) and all(v == Decimal(str(n)) for v in values)


def page(j, t, path):
    j.check("page_" + path, navigated_path(t, path) and shot_at(t, path)[0], path)


def check(j, n, t, initial, after):
    j.check(
        "reviewed_initial_fixture",
        initial is not None and {k: digest(v) for k, v in initial.items()} == SEED,
        "Initial rows match the reviewed seed",
    )
    cfg = CONFIG.get(str(n), {})
    f = t.get("final_answer", "")
    low = norm(f)
    j.check(
        "answer_not_disclaimed",
        not re.search(
            r"(?:this|following|answer|values?)\s+(?:is|are)\s+(?:incorrect|wrong|false)|incorrect\s*:",
            low,
        ),
        "Answer asserts its facts",
    )
    if cfg.get("product"):
        c = cfg["product"]
        path = "/us/" + c["slug"] + "/" + c["pid"] + ".html"
        page(j, t, path)
        block = next(
            (
                x
                for x in re.split(r"\n|(?<=[.!?])\s+(?=[A-Z])", f)
                if norm(c["name"]) in norm(x) and norm(c["color"]) in norm(x)
            ),
            "",
        )
        j.check(
            "comparison_product",
            money(block, c["price"])
            and bool(
                re.search(
                    r"(?<!\d)" + str(c["rating"]) + r"\s*(?:stars?|star rating)",
                    norm(block),
                )
            )
            and bool(
                re.search(r"\b" + str(c["review_count"]) + r"\s*reviews?", norm(block))
            ),
            "Named comparison colorway has correct price, rating and review count",
        )
        j.check(
            "primary_price",
            labelled(f, "original product", cfg["primary_price"]),
            "Original selected product price",
        )
        j.check(
            "price_difference",
            labelled(
                f,
                "price (?:difference|gap)",
                round(abs(c["price"] - cfg["primary_price"]), 2),
            ),
            "Correct price difference",
        )
    if cfg.get("vip"):
        page(j, t, "/us/account/")
        page(j, t, "/us/vip-access/")
        j.check(
            "reward_arithmetic",
            bool(re.search(r"579\s*points", low))
            and bool(re.search(r"(?:one|1)\s*\$10\s*reward", low))
            and bool(re.search(r"279\s*points", low))
            and labelled(f, "minimum", 100),
            "One reward, 279 points remaining, minimum $100 order",
        )
        j.check(
            "premium_spend",
            money(f, 145.30) and "premium" in low,
            "Spend needed for Premium",
        )
        j.check(
            "tier_shipping",
            bool(re.search(r"classic.*?free ground shipping", low))
            and bool(re.search(r"premium.*?reduced expedited", low)),
            "Distinct tier shipping benefits",
        )
    if cfg.get("cities") and initial:
        counts = {}
        for city in cfg["cities"]:
            candidates = [
                x
                for x in initial["stores"]
                if city.casefold() in (x["city"] + " " + x["address"]).casefold()
            ]
            counts[city] = len(candidates)
            navigated = any(
                urlsplit(s.get("url", "")).path.rstrip("/") == "/us/storelocator"
                and parse_qs(urlsplit(s["url"]).query).get("q", [""])[0].casefold()
                == city.casefold()
                for s in t.get("steps", [])
            )
            block = next(
                (
                    x
                    for x in re.split(r"\n|(?<=[.!?])\s+(?=[A-Z])", f)
                    if norm(x).startswith(city.casefold() + ":")
                ),
                "",
            )
            j.check(
                "city_" + city,
                navigated
                and bool(re.search(r"\b" + str(len(candidates)) + r"\s*stores?", block))
                and any(
                    norm(x["address"]) in norm(block) and norm(x["city"]) in norm(block)
                    for x in candidates
                ),
                "City count and one full street/city address",
            )
        winner = max(counts, key=counts.get)
        j.check(
            "city_most",
            bool(re.search(winner.casefold() + r".*?most", low)),
            "Correct largest result set",
        )
    if cfg.get("policies"):
        for path in ["/us/policies/returns/", "/us/policies/shipping/", "/us/service/"]:
            page(j, t, path)
        j.check(
            "policy_answers",
            answers.sale_items_final(f)
            and answers.ground_days_2_to_5(f)
            and answers.two_day_cutoff(f)
            and answers.toll_free_phone(f)
            and answers.support_hours(f),
            "Return exception, delivery timing and exchange contact",
        )
        j.check(
            "online_returns",
            bool(re.search(r"(?:cannot|can.t|not).*?return.*?store", low))
            and bool(re.search(r"30\s*days", low)),
            "30 days; online returns cannot go to a store",
        )
    if cfg.get("order") and initial:
        page(j, t, "/us/orders/US-20260827-00012/")
        o = next(o for o in initial["orders"] if o["order_no"] == "US-20260827-00012")
        for label in ["subtotal", "tax", "total"]:
            j.check(
                "order_" + label,
                labelled(f, r"\b" + label + r"\b", o[label]),
                "Order " + label,
            )
    if cfg.get("fitting"):
        page(
            j,
            t,
            "/us/gizeh-natural-leather-oiled-black/gizeh-core-oiledleather-0-eva-u_449.html",
        )
        page(j, t, "/us/policies/returns/")
        j.check(
            "fitting_purchase",
            money(f, 139.95)
            and bool(re.search(r"30\s*days", low))
            and bool(re.search(r"(?:cannot|can.t|not).*?return.*?store", low)),
            "Price and online return rule",
        )
    if n in [14, 15] and initial and after:
        uid = 1 if n == 14 else 2
        pid = (
            "arizona-core-birkoflor-0-eva-w_109"
            if n == 14
            else "arizonabigbuckle-nubuk-nubuckleather-0-eva-w_12349"
        )
        product = next(p for p in initial["products"] if p["pid"] == pid)
        old = {r["id"] for r in initial["cart_items"]}
        new = [r for r in after["cart_items"] if r["id"] not in old]
        wanted = {
            "user_id": uid,
            "product_id": product["id"],
            "size": "8-8.5" if n == 14 else "9-9.5",
            "width": "Regular/Wide",
            "quantity": 1 if n == 14 else 2,
        }
        valid = (
            len(new) == 1
            and all(new[0].get(k) == v for k, v in wanted.items())
            and [r for r in after["cart_items"] if r["id"] in old]
            == initial["cart_items"]
        )
        j.check(
            "exact_cart_delta",
            valid,
            "One requested variant; every existing cart line preserved",
        )
    if n == 18 and initial and after:
        uid = 1
        user = next(u for u in initial["users"] if u["id"] == uid)
        old = {o["id"] for o in initial["orders"]}
        orders = [o for o in after["orders"] if o["id"] not in old]
        if len(orders) == 1:
            order = orders[0]
            address = {
                "ship_name": user["first_name"] + " " + user["last_name"],
                "ship_address1": user["address1"],
                "ship_address2": user["address2"],
                "ship_city": user["city"],
                "ship_state": user["state"],
                "ship_zip": user["zip_code"],
            }
            j.check(
                "saved_shipping_address",
                all(order[k] == v for k, v in address.items()),
                "Checkout uses the saved address",
            )
            target = next(
                p
                for p in initial["products"]
                if p["pid"] == "gizeh-core-birkoflor-0-eva-u_79"
            )
            cart = [dict(r) for r in initial["cart_items"] if r["user_id"] == uid] + [
                {
                    "product_id": target["id"],
                    "size": "8-8.5",
                    "width": "Regular/Wide",
                    "quantity": 1,
                }
            ]
            expected = []
            for item in cart:
                prod = next(
                    p for p in initial["products"] if p["id"] == item["product_id"]
                )
                expected.append(
                    {
                        "product_id": prod["id"],
                        "name": prod["name"],
                        "model": prod["model"],
                        "color": prod["color"],
                        "size": item["size"],
                        "width": item["width"],
                        "price": prod["price"],
                        "quantity": item["quantity"],
                        "image": json.loads(prod["images_json"])[0],
                    }
                )
            actual = [
                {k: r[k] for k in expected[0]}
                for r in after["order_items"]
                if r["order_id"] == order["id"]
            ]
            j.check(
                "exact_order_contents",
                sorted(actual, key=lambda r: (r["product_id"], r["size"], r["width"]))
                == sorted(
                    expected, key=lambda r: (r["product_id"], r["size"], r["width"])
                ),
                "Exact ordered products, variants, quantities, prices and photos",
            )
        old_cards = {r["id"] for r in initial["payment_methods"]}
        new_cards = [r for r in after["payment_methods"] if r["id"] not in old_cards]
        j.check(
            "one_new_payment_card",
            len(new_cards) == 1
            and new_cards[0]["user_id"] == uid
            and new_cards[0]["label"] == "Visa"
            and new_cards[0]["last_four"] == "1111",
            "Exactly one new Visa card",
        )

"""Deterministic verifier contract tests for the BIRKENSTOCK mirror.

Covers, per task:
  - ground-truth sanity against the frozen seed DB (prices, counts, tie sets,
    cart math, PDP fields, store lists),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots) MUST PASS,
  - a no-op run MUST FAIL,
  - a wrong-answer run MUST FAIL,
  - a shortcut run (correct answer, no on-site navigation) MUST FAIL,
  - a tampered run package (missing/corrupt trajectory, missing or 1x1
    screenshots, mutated after-DB) MUST FAIL.
The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed.
"""
import json
import os
import random
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
VERIFY = SITE / "verify"
SEED = SITE / "instance_seed" / "birkenstock.db"

sys.path.insert(0, str(VERIFY))
import answers  # noqa: E402
from grade import (T0_TIE, T5_TIE, T4_35, T10_PIDS, T10_COLORS,  # noqa: E402
                   AUSTIN_STREETS, BROOKLYN_STREETS)

BASE = "http://localhost:46060"


# ---------------------------------------------------------------- PNG fixture
def make_png(seed, width=240, height=160):
    """A valid, distinct, deterministic noise PNG (>= 2000 bytes)."""
    rng = random.Random(seed)
    raw = b""
    for y in range(height):
        raw += b"\x00" + bytes(rng.randrange(256) for _ in range(width * 3))
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- run fixture
def build_run(root, steps, final_answer, shots_n=None, mutate=None, terminated=True):
    """Write a trajectory.json + screenshots + initial.db/after.db fixture.

    steps: list of (url, action, params, observed_text). A final 'done' step
    is appended automatically carrying `final_answer`.
    """
    root = Path(root)
    (root / "screenshots").mkdir(parents=True, exist_ok=True)
    frames = shots_n if shots_n is not None else len(steps) + 1
    for i in range(frames):
        (root / "screenshots" / f"step_{i:03d}.png").write_bytes(make_png(1000 + i))
    shutil.copy2(SEED, root / "initial.db")
    shutil.copy2(SEED, root / "after.db")
    if mutate:
        mutate(root / "after.db")
    traj_steps = []
    for i, (url, action, params, text) in enumerate(steps):
        traj_steps.append({
            "step": i, "url": url, "title": "fixture", "page_text": text,
            "thought": "fixture thought", "action": action, "params": params,
            "observed_text": text, "observed_text_before": text,
            "screenshot_before": f"step_{i:03d}.png",
            "screenshot_after": f"step_{i + 1:03d}.png",
        })
    last = len(traj_steps)
    traj_steps.append({
        "step": last, "url": steps[-1][0] if steps else BASE + "/us/",
        "title": "fixture", "page_text": "final", "thought": "done",
        "action": "done", "params": {"text": final_answer, "success": True},
        "observed_text": "final", "observed_text_before": "final",
        "observed_text_after": "final",
        "screenshot_before": f"step_{last:03d}.png",
        "screenshot_after": f"step_{last:03d}.png",
    })
    traj = {
        "task": "fixture", "task_id": "fixture", "start_url": steps[0][0] if steps else BASE + "/us/",
        "model": "fixture", "max_steps": 30, "steps": traj_steps,
        "terminated": terminated, "termination_reason": "agent_done" if terminated else None,
        "final_answer": final_answer, "success_self_report": True,
        "judge_rubric": "", "verifier_path": "",
    }
    (root / "trajectory.json").write_text(json.dumps(traj, indent=1))
    return root


def run_verifier(number, run_dir):
    proc = subprocess.run(
        [sys.executable, str(VERIFY / f"verify_{number}.py"), "--run_dir", str(run_dir)],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "WH_SITE": "birkenstock"},
    )
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": "verifier crashed", "stdout": proc.stdout[-500:],
                   "stderr": proc.stderr[-500:]}
    return proc.returncode, verdict


# ---------------------------------------------------------------- DB mutations
def _pid(db, pid):
    con = sqlite3.connect(db)
    row = con.execute("SELECT id FROM products WHERE pid=?", (pid,)).fetchone()
    con.close()
    return row[0]


def _uid(db, email):
    con = sqlite3.connect(db)
    row = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    con.close()
    return row[0]


def mut_t14(db):
    con = sqlite3.connect(db)
    nid = (con.execute("SELECT MAX(id) FROM cart_items").fetchone()[0] or 0) + 1
    con.execute("INSERT INTO cart_items (id,user_id,product_id,size,width,quantity,added_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (nid, _uid(db, "alice.j@test.com"), _pid(db, "arizona-core-birkoflor-0-eva-w_109"),
                 "8-8.5", "Regular/Wide", 1, "2026-09-21 12:00:00"))
    con.commit(); con.close()


def mut_t15(db):
    con = sqlite3.connect(db)
    nid = (con.execute("SELECT MAX(id) FROM cart_items").fetchone()[0] or 0) + 1
    con.execute("INSERT INTO cart_items (id,user_id,product_id,size,width,quantity,added_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (nid, _uid(db, "bob.c@test.com"), _pid(db, "arizonabigbuckle-nubuk-nubuckleather-0-eva-w_12349"),
                 "9-9.5", "Regular/Wide", 2, "2026-09-21 12:00:00"))
    con.commit(); con.close()


def mut_t16(db):
    con = sqlite3.connect(db)
    con.execute("UPDATE users SET city='Denver', state='CO', zip_code='80202' WHERE email=?",
                ("carol.d@test.com",))
    con.commit(); con.close()


def mut_t17(db):
    con = sqlite3.connect(db)
    nid = (con.execute("SELECT MAX(id) FROM payment_methods").fetchone()[0] or 0) + 1
    con.execute("INSERT INTO payment_methods (id,user_id,label,last_four,holder,exp_month,exp_year,is_default) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (nid, _uid(db, "david.k@test.com"), "Mastercard", "8888", "David Kim", 12, 2028, 0))
    con.commit(); con.close()


def mut_t18(db):
    con = sqlite3.connect(db)
    uid = _uid(db, "alice.j@test.com")
    oid = (con.execute("SELECT MAX(id) FROM orders").fetchone()[0] or 0) + 1
    con.execute("""INSERT INTO orders (id,order_no,user_id,status,email,ship_name,ship_address1,
        ship_address2,ship_city,ship_state,ship_zip,payment_label,payment_last_four,shipping_method,
        shipping_cost,subtotal,tax,total,points_earned,tracking_no,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (oid, "US-20260921-00007", uid, "Processing", "alice.j@test.com", "Alice Johnson",
                 "48 Sheridan Square", "Apt 4B", "New York", "NY", "10014", "Visa", "1111",
                 "Ground Shipping", 0.0, 372.37, 33.05, 405.42, 372,
                 "1Z555000000BIRK999", "2026-09-21 12:00:00"))
    item_id = (con.execute("SELECT MAX(id) FROM order_items").fetchone()[0] or 0) + 1
    for pid, price, qty in [("3stepfoot-careessentials-footcarekit-0-0-u_11838", 29.95, 1),
                            ("arizona-core-oiledleather-softfootbed-eva-u_11681", 116.21, 2),
                            ("gizeh-core-birkoflor-0-eva-u_79", 110.00, 1)]:
        prod_id = _pid(db, pid)
        prod = con.execute("SELECT name,model,color,images_json FROM products WHERE id=?", (prod_id,)).fetchone()
        variant = con.execute("SELECT size,width FROM cart_items WHERE user_id=? AND product_id=?", (uid,prod_id)).fetchone() or ("8-8.5", "Regular/Wide")
        con.execute("""INSERT INTO order_items (id,order_id,product_id,name,model,color,size,width,price,quantity,image)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (item_id, oid, prod_id, prod[0], prod[1], prod[2], variant[0], variant[1], price, qty, json.loads(prod[3])[0]))
        item_id += 1
    nid = (con.execute("SELECT MAX(id) FROM payment_methods").fetchone()[0] or 0) + 1
    con.execute("INSERT INTO payment_methods (id,user_id,label,last_four,holder,exp_month,exp_year,is_default) "
                "VALUES (?,?,?,?,?,?,?,?)", (nid, uid, "Visa", "1111", "Alice Johnson", 12, 2028, 0))
    con.execute("UPDATE users SET vip_points=vip_points+372, lifetime_spend=lifetime_spend+372.37 WHERE id=?", (uid,))
    con.execute("DELETE FROM cart_items WHERE user_id=?", (uid,))
    con.commit(); con.close()


# ---------------------------------------------------------------- honest steps
def S(url, action="navigate", params=None, text=""):
    return (url, action, params or {}, text)


SEARCH = BASE + "/us/search/"
PD = BASE + "/us/"

HONEST = {
    0: dict(steps=[
            S(BASE + "/us/"),
            S(SEARCH + "?q=arizona+eva", text='435 products found Arizona Essentials Papaya $49.95 $32.47 -35%'),
            S(PD + "arizona-eva-papaya/arizona-eva-eva-0-eva-u_11562.html", "click",
              text="Arizona Essentials EVA Color: Papaya $32.47 -35%"),
        ], answer="The cheapest adult result is Arizona Essentials in Papaya, priced $32.47 (down from $49.95, -35%)."),
    1: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "women/sandals/"),
            S(PD + "women/sandals/?color=Black", "click", text="Siena Rivet Black $116.21"),
            S(PD + "women/sandals/?color=Black&sort=price-asc", "select_dropdown", {"text": "Price: Low to High"},
              text="Siena Rivet Black $154.95 $116.21 -25%"),
        ], answer="The cheapest black women's sandal is the Siena Rivet at $116.21."),
    2: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "men/shoes/clogs/"),
            S(PD + "men/shoes/clogs/?max_price=150", "click", text="64 products found"),
            S(PD + "men/shoes/clogs/?max_price=150&sort=price-desc", "select_dropdown", {"text": "Price: High to Low"},
              text="Amsterdam Wrapped Charcoal $134.95"),
        ], answer="64 products are found; the most expensive is the Amsterdam Wrapped at $134.95."),
    3: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "kids/boys-sandals/", text="35 products found"),
            S(PD + "kids/boys-sandals/?sort=price-asc", "select_dropdown", {"text": "Price: Low to High"},
              text="Gizeh Essentials Kids Black $34.95 $22.72 -35%"),
        ], answer="There are 35 products; the cheapest pair is the Gizeh Essentials Kids in Black at $22.72."),
    4: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "sale/"),
            S(PD + "sale/?material=EVA", "click", text="-35% Arizona Essentials Glamour Gold $32.47"),
        ], answer="The highest discount shown is 35%; the Arizona Essentials in Glamour Gold has it ($32.47 from $49.95)."),
    5: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "eva-sandals/"),
            S(PD + "eva-sandals/?sort=price-asc", "select_dropdown", {"text": "Price: Low to High"},
              text="Arizona Essentials Papaya $32.47"),
        ], answer="The cheapest product is the Arizona Essentials in Papaya at $32.47."),
    6: dict(steps=[
            S(BASE + "/us/"),
            S(SEARCH + "?q=boston+oiled+leather", text="Boston $154.95"),
            S(PD + "boston-natural-leather-oiled-black/boston-core-oiledleather-0-eva-u_449.html", "click",
              text="Boston Oiled Leather Black $154.95 4.8 177 Reviews Item no. 0860131"),
        ], answer="The Boston Oiled Leather in Black costs $154.95, has a 4.8 star rating and 177 reviews."),
    7: dict(steps=[
            S(BASE + "/us/"),
            S(SEARCH + "?q=boston+soft+footbed", text="Boston Soft Footbed Oyster Tonal"),
            S(PD + "boston-soft-footbed-suede-leather-oyster-tonal/boston-suede-suedeleather-softfootbed-eva-u_12168.html",
              "click", text="Boston Soft Footbed Suede Leather Oyster Tonal Item no. 0560771/0560773 3.3 525 Reviews"),
        ], answer="The item number is 0560771/0560773 and the star rating is 4.8."),
    8: dict(steps=[
            S(BASE + "/us/"),
            S(SEARCH + "?q=madrid+birko-flor", text="Madrid Birko-Flor Black $82.95"),
            S(PD + "madrid-birko-flor-black/madrid-core-birkoflor-0-eva-u_79.html", "click",
              text="Madrid Birko-Flor Black $82.95 Material Footbed material: Cork"),
        ], answer="The footbed material is Cork."),
    9: dict(steps=[
            S(BASE + "/us/"),
            S(SEARCH + "?q=gizeh+oiled+leather", text="Gizeh Oiled Leather Black $139.95"),
            S(PD + "gizeh-natural-leather-oiled-black/gizeh-core-oiledleather-0-eva-u_449.html", "click",
              text="Gizeh Oiled Leather Black $139.95 US 9-9.5 EU 40"),
        ], answer="US women's 9-9.5 corresponds to BIRKENSTOCK (EU) size 40; the product costs $139.95."),
    10: dict(steps=[
            S(BASE + "/us/"),
            S(SEARCH + "?q=arizona+big+buckle+oiled+leather", text="Arizona Big Buckle"),
            S(PD + "arizona-big-buckle-natural-leather-oiled-black/arizonabigbuckle-bigbuckle-oiledleather-0-eva-w_1770.html",
              "click",
              text="Arizona Big Buckle Oiled Leather swatches Olive Green Pure Sage Basalt Gray Black Habana Tobacco Brown Cognac"),
        ], answer="It comes in 7 colors: Olive Green, Pure Sage, Basalt Gray, Black, Habana, Tobacco Brown and Cognac."),
    11: dict(steps=[
            S(BASE + "/us/"),
            S(SEARCH + "?q=boston+soft+footbed", text="Boston Soft Footbed Taupe"),
            S(PD + "boston-soft-footbed-suede-leather-taupe/boston-suede-suedeleather-softfootbed-eva-u_46.html", "click",
              text="Boston Soft Footbed Suede Leather Taupe $169.95 or as low as $14.71/mo. with Afterpay 407 Reviews"),
        ], answer="It costs $169.95, the Afterpay amount is $14.71/mo, and it has 407 reviews."),
    12: dict(steps=[
            S(BASE + "/us/"),
            S(SEARCH + "?q=foot+care+kit", text="3-Step Foot Care Kit $29.95"),
            S(PD + "3-step-foot-care-kit-multi/3stepfoot-careessentials-footcarekit-0-0-u_11838.html", "click",
              text="3-Step Foot Care Kit $29.95 Bestseller This set contains: Exfoliating Foot Scrub, 30 ml Nourishing Foot Balm, 30ml Relief Lotion Tired Leg & Foot"),
        ], answer="It costs $29.95, carries the Bestseller badge, and the set contains the Exfoliating Foot Scrub, the Nourishing Foot Balm and the Relief Lotion Tired Leg & Foot."),
    13: dict(steps=[
            S(BASE + "/us/"),
            S(SEARCH + "?q=mayari+birko-flor", text="Mayari Birko-Flor Black $112.95"),
            S(PD + "mayari-birko-flor-black/mayari-core-birkoflor-0-eva-u_79.html", "click",
              text="Mayari Birko-Flor Black $112.95 66 Reviews"),
        ], answer="It costs $112.95 and has 66 reviews."),
    14: dict(steps=[
            S(BASE + "/us/login/", "input", {"email": "alice.j@test.com", "password": "TestPass123!"}),
            S(PD + "search/?q=arizona+birko-flor", text="Arizona Birko-Flor Silver $117.95"),
            S(PD + "arizona-birko-flor-silver/arizona-core-birkoflor-0-eva-w_109.html", "click",
              text="Arizona Birko-Flor Silver $117.95 size 8-8.5 Regular/Wide"),
            S(PD + "cart/", "click", text="ORDER SUMMARY Subtotal $380.32 Shipping FREE Estimated tax $33.75 Estimated total $414.07"),
        ], answer="The subtotal is $380.32 and the shipping is FREE.", mutate=mut_t14),
    15: dict(steps=[
            S(BASE + "/us/login/", "input", {"email": "bob.c@test.com", "password": "TestPass123!"}),
            S(PD + "search/?q=arizona+big+buckle+nubuck", text="Arizona Big Buckle Pepper $174.95"),
            S(PD + "arizona-big-buckle-nubuck-leather-pepper/arizonabigbuckle-nubuk-nubuckleather-0-eva-w_12349.html",
              "click", text="Arizona Big Buckle Nubuck Leather Pepper $174.95 size 9-9.5"),
            S(PD + "cart/", "click", text="ORDER SUMMARY Subtotal $962.29 Shipping FREE"),
        ], answer="The subtotal is $962.29 and the shipping is FREE.", mutate=mut_t15),
    16: dict(steps=[
            S(BASE + "/us/login/", "input", {"email": "carol.d@test.com", "password": "TestPass123!"}),
            S(PD + "account/profile", "click", text="Carol Davis 733 Hayes St San Francisco CA 94117"),
            S(PD + "account/profile", "input", {"city": "Denver", "state": "CO", "zip_code": "80202"},
              text="Carol Davis 733 Hayes St Denver CO 80202 Your profile has been updated."),
        ], answer="The address on my profile is now 733 Hayes St, Denver, CO 80202.", mutate=mut_t16),
    17: dict(steps=[
            S(BASE + "/us/login/", "input", {"email": "david.k@test.com", "password": "TestPass123!"}),
            S(PD + "account/payment", "click", text="Amex ending in 3007"),
            S(PD + "account/payment", "input", {"label": "Mastercard", "card_number": "5555666677778888"},
              text="Mastercard ending in 8888 was added."),
        ], answer="The new card shows label Mastercard and last four digits 8888.", mutate=mut_t17),
    18: dict(steps=[
            S(BASE + "/us/login/", "input", {"email": "alice.j@test.com", "password": "TestPass123!"}),
            S(PD + "search/?q=gizeh+birko-flor", text="Gizeh Birko-Flor Black $110.00"),
            S(PD + "gizeh-birko-flor-black/gizeh-core-birkoflor-0-eva-u_79.html", "click",
              text="Gizeh Birko-Flor Black $110.00 size 8-8.5"),
            S(PD + "cart/", "click", text="ORDER SUMMARY Subtotal $372.37 Shipping FREE"),
            S(PD + "checkout/?step=address", "click"),
            S(PD + "checkout/?step=payment", "click", text="Visa 4111111111111111"),
            S(PD + "checkout/?step=review", "click"),
            S(PD + "orders/US-20260921-00007/", "click", text="Order US-20260921-00007 total $405.42"),
        ], answer="The order number is US-20260921-00007 and the order total is $405.42.", mutate=mut_t18),
    19: dict(steps=[
            S(BASE + "/us/login/", "input", {"email": "alice.j@test.com", "password": "TestPass123!"}),
            S(PD + "account/", "click", text="US-20260909-00001 Delivered 1Z900000000BIRK100"),
        ], answer="My most recent order is US-20260909-00001, status Delivered, tracking number 1Z900000000BIRK100."),
    20: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "order-status/", "navigate", text="Enter your order number and the email address"),
            S(BASE + "/us/track-order/", "input",
              {"order_no": "US-20260827-00012", "email": "bob.c@test.com"},
              text="Order US-20260827-00012 Shipped Ground Shipping Tracking number 1Z900012352BIRK101"),
        ], answer="The order is Shipped via Ground Shipping with tracking number 1Z900012352BIRK101."),
    21: dict(steps=[
            S(BASE + "/us/login/", "input", {"email": "david.k@test.com", "password": "TestPass123!"}),
            S(PD + "account/", "click", text="579 POINTS AVAILABLE Classic CURRENT TIER $554.70 LIFETIME SPEND Premium unlocks at $700"),
        ], answer="My current tier is Classic, I have 579 points, and I need $145.30 more lifetime spend to reach Premium."),
    22: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "birkenstock-vip/", "navigate",
              text="CLASSIC $200 - $699 Free ground shipping on every order - Extra 15% off Last Chance styles - Exclusive gifts with purchase - Birthday reward - Anniversary reward - Access to VIP bundles"),
        ], answer="The CLASSIC tier requires $200 to $699 lifetime spend; members get free ground shipping on every order and a birthday reward."),
    23: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "birkenstock-vip/", "navigate",
              text="Leave a review 25 points 300 points = $10 off your purchase (minimum $100 order)"),
        ], answer="You earn 25 points for leaving a review, and it takes 300 points to redeem a $10 reward."),
    24: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "storelocator/?q=Austin", "navigate",
              text="25 stores match Austin showing 50 Austin 2901 S Capital of Texas Hwy"),
        ], answer="25 stores match Austin; one is at 2901 S Capital of Texas Hwy, Austin."),
    25: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "storelocator/?q=Brooklyn", "navigate",
              text="34 stores match Brooklyn showing 34 Brooklyn 70 N 6th St"),
        ], answer="34 stores match Brooklyn; one is at 70 N 6th St, Brooklyn."),
    26: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "policies/returns/", "navigate",
              text="within 30 days of delivery with the exception of Sale items that are discounted 40% or more. Sale styles that are discounted 40% off or more are final sale and cannot be returned or exchanged."),
        ], answer="The return window is 30 days; sale items discounted 40% or more are final sale and cannot be returned."),
    27: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "policies/shipping/", "navigate",
              text="GROUND SHIPPING: Transit time will vary based on your location and takes between 2 and 5 business days. 2-DAY SHIPPING: Order must be placed Monday-Friday by 12pm EST to ship same day."),
        ], answer="Ground shipping takes between 2 and 5 business days; a 2-day order must be placed Monday-Friday by 12pm EST to ship the same day."),
    28: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "service/", "navigate",
              text="Toll free calls Monday - Friday 9am to 9pm EST (844) 505-4055"),
        ], answer="The toll-free number is (844) 505-4055, available Monday to Friday from 9am to 9pm EST."),
    29: dict(steps=[
            S(BASE + "/us/"),
            S(PD + "service/fitting-guide/", "navigate",
              text="Size Conversion Chart 7 - 7 1/2 38 10 - 10 1/2 43"),
        ], answer="A US men's 10-10.5 is BIRKENSTOCK size 43, and a US women's 7-7.5 is size 38."),
}

# Reviewed request fixtures are synthetic controls based on checked browser paths.
for _number, _fixture in json.loads((VERIFY / "reviewed_fixtures.json").read_text()).items():
    HONEST[int(_number)]["answer"] = _fixture["answer"]
    HONEST[int(_number)]["steps"] = [
        S(BASE + step["path"], step["action"], step["params"], step["text"])
        for step in _fixture["steps"]
    ]

WRONG_ANSWER = {
    0: "The cheapest adult result is Arizona Kids EVA in Black, priced $34.95.",
    1: "The cheapest black women's sandal is the Madrid Big Buckle at $154.95.",
    2: "60 products are found; the most expensive is the Boston Crosstown at $131.21.",
    3: "There are 30 products; the cheapest pair is the Arizona Kids in Black at $34.95.",
    4: "The highest discount shown is 25%; the Arizona Essentials in Papaya has it.",
    5: "The cheapest product is the Arizona Essentials in White at $49.95.",
    6: "The Boston Oiled Leather in Black costs $159.95, has a 4.2 star rating and 185 reviews.",
    7: "The item number is 0860131 and the star rating is 3.3.",
    8: "The footbed material is EVA.",
    9: "US women's 9-9.5 corresponds to EU size 42; the product costs $135.95.",
    10: "It comes in 5 colors: Olive Green, Pure Sage, Basalt Gray, Black and Habana.",
    11: "It costs $165.95, the Afterpay amount is $12.99/mo, and it has 525 reviews.",
    12: "It costs $24.95, carries the New badge, and the set contains a shoe horn.",
    13: "It costs $99.95 and has 8 reviews.",
    14: "The subtotal is $117.95 and the shipping is $7.95.",
    15: "The subtotal is $787.34 and the shipping is $7.95.",
    16: "The address on my profile is now 48 Sheridan Square, Denver, CO 80202.",
    17: "The new card shows label Visa and last four digits 4242.",
    18: "The order number is US-20260921-00008 and the order total is $533.84.",
    19: "My most recent order is US-20260827-00012, status Shipped, tracking 1Z900012352BIRK101.",
    20: "The order is Delivered via 2-Day Shipping with tracking 1Z900000000BIRK100.",
    21: "My current tier is Essential, I have 25 points, and I need $675.00 more to reach Premium.",
    22: "The CLASSIC tier requires $700 to $1,499 lifetime spend; members get free expedited shipping.",
    23: "You earn 10 points for leaving a review, and it takes 100 points to redeem a $10 reward.",
    24: "20 stores match Austin; one is at 100 Main St, Austin.",
    25: "30 stores match Brooklyn; one is at 1 Broadway, Brooklyn.",
    26: "The return window is 60 days; sale items discounted 40% or more can still be returned.",
    27: "Ground shipping takes between 3 and 7 business days; a 2-day order must be placed by 3pm EST.",
    28: "The toll-free number is (800) 555-0100, available Monday to Friday from 8am to 6pm EST.",
    29: "A US men's 10-10.5 is BIRKENSTOCK size 44, and a US women's 7-7.5 is size 37.",
}


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="birk-verify-tests-")
        cls.root = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fresh(self, name):
        d = self.root / name
        if d.exists():
            shutil.rmtree(d)
        return d

    # ---------------- honest fixtures ----------------
    def test_honest_runs_all_pass(self):
        failures = []
        for n in range(30):
            spec = HONEST[n]
            d = build_run(self.fresh(f"honest_{n}"), spec["steps"], spec["answer"],
                          mutate=spec.get("mutate"))
            rc, verdict = run_verifier(n, d)
            if rc != 0 or not verdict.get("pass"):
                failures.append((n, verdict.get("reason"), [e for e in verdict.get("evidence", []) if e.startswith("[FAIL]")][:4]))
        self.assertEqual(failures, [], f"honest fixtures must pass: {failures}")

    # ---------------- no-op ----------------
    def test_noop_runs_all_fail(self):
        misses = []
        for n in range(30):
            d = build_run(self.fresh(f"noop_{n}"),
                          [S(BASE + "/us/")],
                          "")  # empty answer, no navigation
            rc, verdict = run_verifier(n, d)
            if rc == 0 or verdict.get("pass"):
                misses.append(n)
        self.assertEqual(misses, [], f"no-op runs must fail everywhere: {misses}")

    def test_noop_with_answer_fails(self):
        """Answer without any task-relevant navigation still fails (anti-guess)."""
        misses = []
        for n in range(30):
            spec = HONEST[n]
            d = build_run(self.fresh(f"noopans_{n}"), [S(BASE + "/us/")], spec["answer"])
            rc, verdict = run_verifier(n, d)
            if rc == 0 or verdict.get("pass"):
                misses.append(n)
        self.assertEqual(misses, [], f"homepage-only runs must fail: {misses}")

    # ---------------- wrong answers ----------------
    def test_wrong_answers_fail(self):
        misses = []
        for n in range(30):
            spec = HONEST[n]
            d = build_run(self.fresh(f"wrong_{n}"), spec["steps"], WRONG_ANSWER[n],
                          mutate=spec.get("mutate"))
            rc, verdict = run_verifier(n, d)
            if rc == 0 or verdict.get("pass"):
                misses.append(n)
        self.assertEqual(misses, [], f"wrong answers must fail: {misses}")

    # ---------------- shortcuts ----------------
    def test_shortcut_runs_fail(self):
        """Correct answer + correct DB state, but the task's pages never opened."""
        misses = []
        for n in range(30):
            spec = HONEST[n]
            shortcut_steps = [s for i, s in enumerate(spec["steps"]) if i == 0]
            d = build_run(self.fresh(f"shortcut_{n}"), shortcut_steps, spec["answer"],
                          mutate=spec.get("mutate"))
            rc, verdict = run_verifier(n, d)
            if rc == 0 or verdict.get("pass"):
                misses.append((n, verdict.get("reason")))
        self.assertEqual(misses, [], f"shortcut runs must fail: {misses}")

    # ---------------- tampered packages ----------------
    def test_missing_trajectory_fails(self):
        d = build_run(self.fresh("missing_traj"), HONEST[6]["steps"], HONEST[6]["answer"])
        (d / "trajectory.json").unlink()
        rc, verdict = run_verifier(6, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_corrupt_trajectory_fails(self):
        d = build_run(self.fresh("corrupt_traj"), HONEST[6]["steps"], HONEST[6]["answer"])
        (d / "trajectory.json").write_text("{not json")
        rc, verdict = run_verifier(6, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_missing_screenshots_fail(self):
        d = build_run(self.fresh("missing_shots"), HONEST[6]["steps"], HONEST[6]["answer"])
        shutil.rmtree(d / "screenshots")
        rc, verdict = run_verifier(6, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_tiny_screenshots_fail(self):
        d = build_run(self.fresh("tiny_shots"), HONEST[6]["steps"], HONEST[6]["answer"])
        for p in (d / "screenshots").glob("*.png"):
            p.write_bytes(make_png(1, width=1, height=1))
        rc, verdict = run_verifier(6, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_identical_frames_fail(self):
        d = build_run(self.fresh("same_shots"), HONEST[6]["steps"], HONEST[6]["answer"])
        frame = make_png(7)
        for p in (d / "screenshots").glob("*.png"):
            p.write_bytes(frame)
        rc, verdict = run_verifier(6, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_readonly_db_tamper_fails(self):
        d = build_run(self.fresh("tamper_ro"), HONEST[6]["steps"], HONEST[6]["answer"])
        con = sqlite3.connect(d / "after.db")
        con.execute("UPDATE products SET price=1.0 WHERE id=1")
        con.commit(); con.close()
        rc, verdict = run_verifier(6, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_stateful_extra_mutation_fails(self):
        d = build_run(self.fresh("tamper_st"), HONEST[14]["steps"], HONEST[14]["answer"],
                      mutate=mut_t14)
        con = sqlite3.connect(d / "after.db")
        con.execute("UPDATE users SET city='Hack' WHERE email='bob.c@test.com'")
        con.commit(); con.close()
        rc, verdict = run_verifier(14, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_stateful_missing_mutation_fails(self):
        """Agent self-reports success but the DB is unchanged."""
        d = build_run(self.fresh("missing_mut"), HONEST[14]["steps"], HONEST[14]["answer"])
        rc, verdict = run_verifier(14, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_upstream_origin_fails(self):
        steps = [S("https://www.birkenstock.com/us/boston-natural-leather-oiled-black/boston-core-oiledleather-0-eva-u_449.html", "navigate")]
        d = build_run(self.fresh("upstream"), steps, HONEST[6]["answer"])
        rc, verdict = run_verifier(6, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))

    def test_truncated_run_fails(self):
        d = build_run(self.fresh("truncated"), HONEST[6]["steps"], HONEST[6]["answer"],
                      terminated=False)
        rc, verdict = run_verifier(6, d)
        self.assertNotEqual(rc, 0)
        self.assertFalse(verdict.get("pass"))


class GroundTruthTests(unittest.TestCase):
    """The hardcoded ground truth must match the frozen seed DB."""

    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
        cls.con.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def q(self, sql, params=()):
        return self.con.execute(sql, params).fetchall()

    def test_seed_counts(self):
        self.assertEqual(self.q("SELECT COUNT(*) FROM products")[0][0], 1053)
        self.assertEqual(self.q("SELECT COUNT(*) FROM categories")[0][0], 36)
        self.assertEqual(self.q("SELECT COUNT(*) FROM stores")[0][0], 6153)
        self.assertEqual(self.q("SELECT COUNT(*) FROM users")[0][0], 4)

    def test_parent_shoe_categories(self):
        for slug, count in (("men-shoes", 298), ("women-shoes", 327)):
            n = self.q("""SELECT COUNT(*) FROM products p JOIN product_categories pc ON pc.product_id=p.id
                JOIN categories c ON c.id=pc.category_id WHERE c.slug=?""", (slug,))[0][0]
            self.assertEqual(n, count, slug)

    def test_t0_tie_set(self):
        rows = self.q("""SELECT pid,model,color,price,size_group FROM products WHERE pid IN (
            'arizona-eva-eva-0-eva-u_11562','arizona-eva-eva-0-eva-u_2138',
            'arizonaessentials-tothebeachmetallic-eva-0-eva-u_11689',
            'arizonaessentials-tothebeachmetallic-eva-0-eva-u_1594',
            'arizonaeva-eva-eva-0-eva-u_1942')""")
        self.assertEqual(len(rows), 5)
        for r in rows:
            self.assertEqual(r["price"], 32.47)
            self.assertEqual((r["model"], r["color"]), T0_TIE[r["pid"]])
            self.assertNotEqual(r["size_group"], "kids")
        cheaper = self.q("""SELECT COUNT(*) FROM products p WHERE p.price < 32.47 AND p.size_group != 'kids'
            AND (p.model LIKE '%arizona%' AND p.material='EVA')""")
        self.assertEqual(cheaper[0][0], 0)

    def test_t1_cheapest_black_womens_sandal(self):
        rows = self.q("""SELECT p.model,p.price FROM products p
            JOIN product_categories pc ON pc.product_id=p.id JOIN categories c ON c.id=pc.category_id
            WHERE c.slug='women-sandals' AND p.color='Black' ORDER BY p.price, p.id""")
        self.assertEqual(rows[0]["model"], "Siena Rivet")
        self.assertEqual(rows[0]["price"], 116.21)

    def test_t2_clogs_under_150(self):
        rows = self.q("""SELECT p.price FROM products p
            JOIN product_categories pc ON pc.product_id=p.id JOIN categories c ON c.id=pc.category_id
            WHERE c.slug='men-shoes-clogs' AND p.price <= 150""")
        self.assertEqual(len(rows), 64)
        self.assertEqual(max(r["price"] for r in rows), 134.95)

    def test_t3_boys_sandals(self):
        rows = self.q("""SELECT p.model,p.price FROM products p
            JOIN product_categories pc ON pc.product_id=p.id JOIN categories c ON c.id=pc.category_id
            WHERE c.slug='kids-boys-sandals' ORDER BY p.price, p.id""")
        self.assertEqual(len(rows), 35)
        self.assertEqual(rows[0]["model"], "Gizeh Essentials Kids")
        self.assertEqual(rows[0]["price"], 22.72)

    def test_t4_max_discount(self):
        rows = self.q("""SELECT p.model,p.color,p.price,p.list_price FROM products p
            JOIN product_categories pc ON pc.product_id=p.id JOIN categories c ON c.id=pc.category_id
            WHERE c.slug='sale' AND p.material='EVA' AND p.list_price > p.price""")
        pcts = {(r["model"], r["color"]): int(round((1 - r["price"] / r["list_price"]) * 100)) for r in rows}
        self.assertEqual(max(pcts.values()), 35)
        at35 = {k for k, v in pcts.items() if v == 35}
        self.assertEqual(at35, set(T4_35))

    def test_t5_tie_set(self):
        rows = self.q("""SELECT p.pid,p.model,p.color FROM products p
            JOIN product_categories pc ON pc.product_id=p.id JOIN categories c ON c.id=pc.category_id
            WHERE c.slug='eva-sandals' AND p.price=32.47""")
        self.assertEqual({(r["model"], r["color"]) for r in rows}, set(T5_TIE.values()))
        self.assertEqual(len(rows), 8)

    def test_pdp_anchors(self):
        checks = {
            "boston-core-oiledleather-0-eva-u_449": ("Boston", "Oiled Leather", "Black", 154.95, 4.8, 177, "0860131"),
            "boston-suede-suedeleather-softfootbed-eva-u_12168": ("Boston Soft Footbed", "Suede Leather", "Oyster Tonal", 169.95, 4.8, 407, "0560771"),
            "madrid-core-birkoflor-0-eva-u_79": ("Madrid", "Birko-Flor", "Black", 82.95, 5.0, 8, "0040793"),
            "gizeh-core-oiledleather-0-eva-u_449": ("Gizeh", "Oiled Leather", "Black", 139.95, 4.8, 25, "1032738"),
            "boston-suede-suedeleather-softfootbed-eva-u_46": ("Boston Soft Footbed", "Suede Leather", "Taupe", 169.95, 4.8, 407, "0560771"),
            "3stepfoot-careessentials-footcarekit-0-0-u_11838": ("3-Step Foot Care Kit", "", "Multi", 29.95, 0.0, 0, "1030399"),
            "mayari-core-birkoflor-0-eva-u_79": ("Mayari", "Birko-Flor", "Black", 112.95, 4.6, 66, "0071791"),
            "arizona-core-birkoflor-0-eva-w_109": ("Arizona", "Birko-Flor", "Silver", 117.95, 4.9, 33, "1023942"),
            "arizonabigbuckle-nubuk-nubuckleather-0-eva-w_12349": ("Arizona Big Buckle", "Nubuck Leather", "Pepper", 174.95, 4.6, 50, "1023957"),
            "gizeh-core-birkoflor-0-eva-u_79": ("Gizeh", "Birko-Flor", "Black", 110.00, 5.0, 20, "0043691"),
        }
        for pid, (model, material, color, price, rating, rc, item) in checks.items():
            r = self.q("SELECT * FROM products WHERE pid=?", (pid,))
            self.assertEqual(len(r), 1, pid)
            r = r[0]
            self.assertEqual((r["model"], r["material"] or "", r["color"], r["price"], r["rating"], r["review_count"]), (model, material, color, price, rating, rc), pid)
            self.assertIn(item, (r["item_no"] or ""))

    def test_t10_swatch_set(self):
        rows = self.q("SELECT pid,color FROM products WHERE master_pid='arizonabigbuckle-bigbuckle-oiledleather-0-eva-w' ORDER BY id")
        self.assertEqual({r["pid"] for r in rows}, set(T10_PIDS))
        self.assertEqual([r["color"] for r in rows], T10_COLORS)

    def test_t11_afterpay(self):
        r = self.q("SELECT price FROM products WHERE pid='boston-suede-suedeleather-softfootbed-eva-u_46'")[0]
        self.assertEqual(round(r["price"] * 0.08655, 2), 14.71)
        r = self.q("SELECT price FROM products WHERE pid='boston-core-oiledleather-0-eva-u_449'")[0]
        self.assertEqual(round(r["price"] * 0.08655, 2), 13.41)

    def test_seed_cart_math(self):
        alice = self.q("SELECT SUM(price*quantity) FROM cart_items ci JOIN products p ON p.id=ci.product_id JOIN users u ON u.id=ci.user_id WHERE u.email='alice.j@test.com'")[0][0]
        self.assertEqual(round(alice + 117.95, 2), 380.32)
        bob = self.q("SELECT SUM(price*quantity) FROM cart_items ci JOIN products p ON p.id=ci.product_id JOIN users u ON u.id=ci.user_id WHERE u.email='bob.c@test.com'")[0][0]
        self.assertEqual(round(bob + 174.95 * 2, 2), 962.29)
        self.assertEqual(round(alice + 110.00, 2), 372.37)
        self.assertEqual(round(round(alice + 110.00, 2) * 0.08875, 2), 33.05)
        self.assertEqual(round(round(alice + 110.00, 2) + 33.05, 2), 405.42)

    def test_t18_order_number_sequence(self):
        n = self.q("SELECT COUNT(*) FROM orders")[0][0]
        self.assertEqual(n, 6)
        self.assertFalse(self.q("SELECT * FROM orders WHERE order_no='US-20260921-00007'"))

    def test_t19_t20_orders(self):
        r = self.q("SELECT o.status,o.tracking_no FROM orders o JOIN users u ON u.id=o.user_id WHERE o.order_no='US-20260909-00001' AND u.email='alice.j@test.com'")
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["status"], r[0]["tracking_no"]), ("Delivered", "1Z900000000BIRK100"))
        r = self.q("SELECT o.status,o.shipping_method,o.tracking_no FROM orders o JOIN users u ON u.id=o.user_id WHERE o.order_no='US-20260827-00012' AND u.email='bob.c@test.com'")
        self.assertEqual((r[0]["status"], r[0]["shipping_method"], r[0]["tracking_no"]),
                         ("Shipped", "Ground Shipping", "1Z900012352BIRK101"))

    def test_t21_vip_math(self):
        r = self.q("SELECT vip_points,lifetime_spend FROM users WHERE email='david.k@test.com'")[0]
        self.assertEqual(r["vip_points"], 579)
        self.assertEqual(r["lifetime_spend"], 554.70)
        self.assertEqual(round(700 - r["lifetime_spend"], 2), 145.30)

    def test_store_lists(self):
        austin = [r["address"] for r in self.q("SELECT address FROM stores WHERE city='Austin' ORDER BY id")]
        self.assertEqual(austin, list(AUSTIN_STREETS))
        brooklyn = [r["address"] for r in self.q("SELECT address FROM stores WHERE city='Brooklyn' ORDER BY id")]
        self.assertEqual(brooklyn, list(BROOKLYN_STREETS))
        self.assertNotIn("0", brooklyn)

    def test_policy_pages_present(self):
        for f in ("policies/returns.html", "policies/shipping.html", "service.html",
                  "fitting_guide.html", "vip.html"):
            self.assertTrue((SITE / "templates" / f).exists(), f)

    def test_answers_predicates(self):
        self.assertTrue(answers.percent_value("The highest discount shown is 35%.", 35))
        self.assertTrue(answers.percent_value("up to -35 off", 35))
        self.assertFalse(answers.percent_value("The highest discount is 25%.", 35))
        self.assertTrue(answers.classic_benefits("Free ground shipping on every order and a birthday reward.") >= 2)
        self.assertTrue(answers.classic_benefits("gifts with purchase; anniversary reward") >= 2)
        self.assertEqual(answers.classic_benefits("free ground shipping on every order"), 1)
        self.assertTrue(answers.review_points_25("You earn 25 points for leaving a review."))
        self.assertFalse(answers.review_points_25("You earn 10 points for a review."))
        self.assertTrue(answers.sale_items_final("Sale items discounted 40% or more are final sale."))
        self.assertTrue(answers.sale_items_final("Styles 40% off cannot be returned or exchanged."))
        self.assertFalse(answers.sale_items_final("Sale items 40% off can still be returned."))
        self.assertTrue(answers.ground_days_2_to_5("takes between 2 and 5 business days"))
        self.assertFalse(answers.ground_days_2_to_5("takes 3 to 7 business days"))
        self.assertTrue(answers.two_day_cutoff("Order must be placed Monday-Friday by 12pm EST to ship same day."))
        self.assertTrue(answers.two_day_cutoff("place by noon EST, weekdays (Monday through Friday)"))
        self.assertFalse(answers.two_day_cutoff("Order must be placed by 3pm EST Monday-Friday."))
        self.assertTrue(answers.toll_free_phone("Call (844) 505-4055"))
        self.assertTrue(answers.toll_free_phone("844-505-4055"))
        self.assertFalse(answers.toll_free_phone("(800) 555-0100"))
        self.assertTrue(answers.support_hours("Monday - Friday 9am to 9pm EST"))
        self.assertFalse(answers.support_hours("Monday - Friday 9am to 6pm EST"))
        self.assertTrue(answers.men_size_binding("US men's 10-10.5 is BIRKENSTOCK size 43", "10-10.5", 43))
        self.assertTrue(answers.women_size_binding("US women's 7-7.5 is size 38", "7-7.5", 38))
        self.assertFalse(answers.men_size_binding("US men's 10-10.5 is size 44", "10-10.5", 43))
        self.assertFalse(answers.women_size_binding("US women's 7-7.5 is BIRKENSTOCK size 37", "7-7.5", 38))
        self.assertFalse(answers.women_size_binding("men's 7-7.5 is BIRKENSTOCK size 38", "7-7.5", 38))


if __name__ == "__main__":
    unittest.main(verbosity=2)

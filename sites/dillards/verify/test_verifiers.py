"""Deterministic verifier contract tests for the DILLARDS mirror.

Covers, per task:
  - ground-truth sanity against the frozen seed DB (row identities, prices,
    balances, registry fixtures),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots; stateful tasks carry the exact expected DB mutation) MUST PASS,
  - a no-op run (homepage only, empty answer) MUST FAIL for every task,
  - a homepage-only run with a fabricated correct-sounding answer MUST FAIL,
  - near-miss wrong answers MUST FAIL,
  - a shortcut run (correct answer, no on-site navigation) MUST FAIL,
  - tampered run packages (missing/corrupt trajectory, missing / 1x1 /
    reused screenshots, upstream origin, truncated run, mutated after-DB on
    read-only tasks, missing or over-mutated state on stateful tasks)
    MUST FAIL.
The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed (DB snapshots come from the frozen seed).
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
SEED = SITE / "instance_seed" / "dillards.db"

sys.path.insert(0, str(VERIFY))
import answers  # noqa: E402

BASE = "http://localhost:46068"


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
def build_run(root, steps, final_answer, shots_n=None, mutate=None, terminated=True,
             task_id="fixture"):
    """Write a trajectory.json + screenshots + initial.db/after.db fixture.

    steps: list of (url, action, params, observed_text). A final 'done' step
    is appended automatically carrying `final_answer`.
    """
    root = Path(root)
    (root / "screenshots").mkdir(parents=True, exist_ok=True)
    frames = shots_n if shots_n is not None else max(3, len(steps) + 2)
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
            "screenshot_before": f"step_{i % frames:03d}.png",
            "screenshot_after": f"step_{(i + 1) % frames:03d}.png",
        })
    last = len(traj_steps)
    traj_steps.append({
        "step": last, "url": steps[-1][0] if steps else BASE + "/",
        "title": "fixture", "page_text": "final", "thought": "done",
        "action": "done", "params": {"text": final_answer, "success": True},
        "observed_text": "final", "observed_text_before": "final",
        "observed_text_after": "final",
        "screenshot_before": f"step_{last % frames:03d}.png",
        "screenshot_after": f"step_{last % frames:03d}.png",
    })
    traj = {
        "task": "fixture", "task_id": task_id, "start_url": steps[0][0] if steps else BASE + "/",
        "model": "fixture", "max_steps": 40, "steps": traj_steps,
        "terminated": terminated, "termination_reason": "agent_done" if terminated else None,
        "final_answer": final_answer, "success_self_report": True,
        "judge_rubric": "", "verifier_path": "",
    }
    (root / "trajectory.json").write_text(json.dumps(traj, indent=1))
    return root


def run_verifier(number, run_dir):
    proc = subprocess.run(
        [sys.executable, str(VERIFY / f"verify_{number}.py"), "--run_dir", str(run_dir)],
        capture_output=True, text=True, timeout=180,
        env={**os.environ, "WH_SITE": "dillards"},
    )
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": "verifier crashed",
                   "stdout": proc.stdout[-400:], "stderr": proc.stderr[-400:]}
    return proc.returncode, verdict


# ---------------------------------------------------------------- DB mutators
def _con(db):
    return sqlite3.connect(db)


def mut_t15(db):
    """The exact DB state a completed task-15 checkout produces."""
    con = _con(db)
    con.execute("""INSERT INTO orders (id,user_id,order_number,placed_at,status,ship_to,
        ship_method,payment_last4,payment_kind,subtotal,shipping_total,tax,total,
        tracking_number,carrier) VALUES (9,1,'D2609220009','2026-09-22','Processing',
        '4120 Cantrell Road, Little Rock, AR 72202','Standard','1088',
        "Dillard's Credit Card",159.0,0.0,10.34,169.34,'','')""")
    con.execute("""INSERT INTO order_items (id,order_id,variant_id,product_name,size,color,
        quantity,price) VALUES (15,9,6834,
        'Antonio Melani Carter Short Sleeve Crew Neck Crepe Sheath Midi Dress',
        '8','Black',1,159.0)""")
    con.execute("""INSERT INTO card_transactions (id,card_account_id,posted,description,
        amount,points) VALUES (10,1,'2026-09-22','Dillards.com order D2609220009',
        169.34,318)""")
    con.execute("DELETE FROM cart_items WHERE user_id=1")
    con.execute("UPDATE card_accounts SET balance=1011.70, points=3468 WHERE id=1")
    con.commit(); con.close()


def mut_t18(db):
    con = _con(db)
    con.execute("""INSERT INTO return_requests (id,user_id,order_id,order_item_id,reason,
        method,status,created,credit_issued) VALUES (2,3,7,11,
        'Did not like the color or style','Return by Mail','Requested',
        '2026-09-22',30.0)""")
    con.commit(); con.close()


def mut_t19(db):
    con = _con(db)
    con.execute("INSERT INTO cart_items (id,user_id,variant_id,quantity) "
                "VALUES (7,1,975,1)")
    con.commit(); con.close()


def mut_t20(db):
    con = _con(db)
    con.execute("DELETE FROM wishlist_items WHERE id=1")
    con.commit(); con.close()


def mut_t21(db):
    con = _con(db)
    con.execute("DELETE FROM wishlist_items WHERE id=13")
    con.commit(); con.close()


def mut_t24(db):
    con = _con(db)
    con.execute("""INSERT INTO registries (id,registry_number,owner_first,owner_last,
        co_owner_first,co_owner_last,kind,event_date,user_id) VALUES
        (7,'G26090107','Alice','Johnson','','','gift','2026-12-25',1)""")
    con.commit(); con.close()


def mut_t28(db):
    con = _con(db)
    con.execute("""INSERT INTO card_payments (id,card_account_id,posted,amount,method,
        confirmation) VALUES (5,1,'2026-09-22',150.0,'Bank Draft','PMT-260922-10005')""")
    con.execute("UPDATE card_accounts SET balance=692.36 WHERE id=1")
    con.commit(); con.close()


def mut_t29(db):
    con = _con(db)
    con.execute("""INSERT INTO reviews (id,product_id,author,title,body,rating,date_label,
        position) VALUES (1789,279,'Anonymous','Stunning dress',
        'This dress is absolutely beautiful. The floral applique trim is exquisite.',
        5,'today',8)""")
    con.execute("UPDATE products SET review_count=20, rating=4.75 WHERE pid='520620253'")
    con.commit(); con.close()


def mut_t30(db):
    con = _con(db)
    con.execute("""INSERT INTO gift_card_purchases (id,amount,recipient,sender,code,
        purchased) VALUES (1,100.0,'Maria Lopez','','7334 0922 0100 0001',
        '2026-09-22')""")
    con.commit(); con.close()


def mut_readonly(db):
    """An unrelated write that read-only tasks must reject."""
    con = _con(db)
    con.execute("UPDATE users SET phone='(000) 000-0000' WHERE email=?",
                ("alice.j@test.com",))
    con.commit(); con.close()


STATE_MUTATORS = {15: mut_t15, 18: mut_t18, 19: mut_t19, 20: mut_t20, 21: mut_t21,
                  24: mut_t24, 28: mut_t28, 29: mut_t29, 30: mut_t30}


# ---------------------------------------------------------------- honest steps
def S(url, action="navigate_to", params=None, text=""):
    return (url, action, params or {"url": url}, text)


def F(url, action, params, text=""):
    return (url, action, params, text)


LOGIN = F(BASE + "/login", "fill_entire_form",
          {"email": "alice.j@test.com", "password": "TestPass123!"})

HONEST_STEPS = {
    0: [S(BASE + "/"), S(BASE + "/c/women-dresses"),
        F(BASE + "/c/women-dresses?orderBy=priceHigh", "select_option", {"orderBy": "priceHigh"})],
    1: [S(BASE + "/"), S(BASE + "/c/men-shirts"),
        F(BASE + "/c/men-shirts/exclusive_dillards", "click_element_by_css", {"facet": "exclusive_dillards"})],
    2: [S(BASE + "/"), S(BASE + "/c/women-dresses"),
        F(BASE + "/c/women-dresses/sale", "click_element_by_css", {"facet": "sale"})],
    3: [S(BASE + "/"), LOGIN,
        F(BASE + "/account", "fill_entire_form", {}),
        S(BASE + "/c/beauty-fragrance"),
        F(BASE + "/c/beauty-fragrance/brand_chanel", "click_element_by_css", {"brand": "chanel"}),
        S(BASE + "/p/chanel-coco-mademoiselle-eau-de-parfum-spray/504228059"),
        F(BASE + "/bag", "click_element_by_css", {"text": "Add To Bag"}),
        F(BASE + "/bag", "click_element_by_css", {"text": "Add To Bag"}),
        F(BASE + "/bag", "click_element_by_css", {"text": "Add To Bag"}),
        F(BASE + "/bag", "click_element_by_css", {"text": "Remove"})],
    4: [S(BASE + "/"), S(BASE + "/c/women-sweaters"),
        F(BASE + "/c/women-sweaters?orderBy=topRated", "select_option", {"orderBy": "topRated"})],
    5: [S(BASE + "/"), S(BASE + "/c/shoes-women-shoes"),
        F(BASE + "/c/shoes-women-shoes/new-arrivals", "click_element_by_css", {"facet": "new-arrivals"})],
    6: [S(BASE + "/"), F(BASE + "/search-term/levi%27s%20318", "fill", {"query": "levi's 318"}),
        S(BASE + "/p/levis-318-shaping-mid-rise-wide-leg-jeans/519099341"),
        F(BASE + "/p/levis-318-shaping-mid-rise-wide-leg-jeans/519099341", "scroll", {})],
    7: [S(BASE + "/"), F(BASE + "/search-term/antonio%20melani%20carter", "fill", {"query": "antonio melani carter"}),
        S(BASE + "/p/antonio-melani-carter-short-sleeve-crew-neck-crepe-sheath-midi-drees/520912513"),
        F(BASE + "/p/antonio-melani-carter-short-sleeve-crew-neck-crepe-sheath-midi-drees/520912513", "scroll", {})],
    8: [S(BASE + "/"), F(BASE + "/search-term/polo%20ralph%20lauren%20classic%20fit%20solid%20cotton%20mesh", "fill", {"query": "polo ralph lauren classic fit solid cotton mesh"}),
        S(BASE + "/p/polo-ralph-lauren-classic-fit-solid-mesh-polo-shirt/501116145"),
        F(BASE + "/p/polo-ralph-lauren-classic-fit-solid-mesh-polo-shirt/501116145", "scroll", {})],
    9: [S(BASE + "/"), F(BASE + "/search-term/alex%20marie%20kaitlin", "fill", {"query": "alex marie kaitlin"}),
        S(BASE + "/p/alex-marie-kaitlin-mikado-floral-applique-trim-sleeveless-shift-dress/520620253"),
        F(BASE + "/p/alex-marie-kaitlin-mikado-floral-applique-trim-sleeveless-shift-dress/520620253", "scroll", {})],
    10: [S(BASE + "/"), F(BASE + "/search-term/timberland%20premium%20waterproof", "fill", {"query": "timberland premium waterproof"}),
         S(BASE + "/p/timberland-mens-premium-waterproof-boots/518854263"),
         F(BASE + "/p/timberland-mens-premium-waterproof-boots/518854263", "scroll", {})],
    11: [S(BASE + "/"), F(BASE + "/search-term/brahmin%20melbourne%20ady", "fill", {"query": "brahmin melbourne ady"}),
         S(BASE + "/p/brahmin-melbourne-collection-ady-croco-embossed-wallet/504158826"),
         F(BASE + "/p/brahmin-melbourne-collection-ady-croco-embossed-wallet/504158826", "scroll", {})],
    12: [S(BASE + "/"), F(BASE + "/search-term/capri%20blue", "fill", {"query": "capri blue"}),
         S(BASE + "/p/capri-blue-x-pura-volcano-smart-vial-home-refill/517436763")],
    13: [S(BASE + "/"), F(BASE + "/search-term/511%20slim", "fill", {"query": "511 slim"}),
         S(BASE + "/p/levis-511-slim-fit-all-seasons-tech-jeans/511371759"),
         F(BASE + "/p/levis-511-slim-fit-all-seasons-tech-jeans/511371759", "scroll", {})],
    14: [S(BASE + "/"), F(BASE + "/search-term/kurt%20geiger", "fill", {"query": "kurt geiger"}),
         F(BASE + "/search-term/kurt%20geiger?orderBy=priceLow", "select_option", {"orderBy": "priceLow"})],
    15: [S(BASE + "/"), LOGIN, F(BASE + "/account", "fill_entire_form", {}),
         S(BASE + "/bag"), F(BASE + "/bag", "click_element_by_css", {"text": "Remove"}),
         S(BASE + "/p/antonio-melani-carter-short-sleeve-crew-neck-crepe-sheath-midi-drees/520912513"),
         F(BASE + "/bag", "click_element_by_css", {"text": "Add To Bag"}),
         S(BASE + "/bag"), S(BASE + "/checkout"),
         F(BASE + "/order-confirmation/9", "click_element_by_css", {"text": "Place Order"})],
    16: [S(BASE + "/"), F(BASE + "/login", "fill_entire_form",
                         {"email": "bob.c@test.com", "password": "TestPass123!"}),
         S(BASE + "/account"), S(BASE + "/account/orders"), S(BASE + "/account/orders/4")],
    17: [S(BASE + "/"), LOGIN, F(BASE + "/account", "fill_entire_form", {}),
         S(BASE + "/account"), S(BASE + "/account/orders"), S(BASE + "/account/orders/2")],
    18: [S(BASE + "/"), F(BASE + "/login", "fill_entire_form",
                         {"email": "carol.d@test.com", "password": "TestPass123!"}),
         S(BASE + "/account"), S(BASE + "/account/orders"), S(BASE + "/account/orders/7"),
         S(BASE + "/account/returns/new/7"),
         F(BASE + "/account/returns", "click_element_by_css", {"text": "Request Return"}),
         S(BASE + "/account/returns")],
    19: [S(BASE + "/"), LOGIN, F(BASE + "/account", "fill_entire_form", {}),
         S(BASE + "/account"), S(BASE + "/account/wishlist"),
         F(BASE + "/account/wishlist", "click_element_by_css", {"text": "Add to Bag"}),
         S(BASE + "/bag")],
    20: [S(BASE + "/"), LOGIN, F(BASE + "/account", "fill_entire_form", {}),
         S(BASE + "/account"), S(BASE + "/account/wishlist"),
         F(BASE + "/account/wishlist", "click_element_by_css", {"text": "Remove"})],
    21: [S(BASE + "/"), F(BASE + "/login", "fill_entire_form",
                         {"email": "david.k@test.com", "password": "TestPass123!"}),
         S(BASE + "/account"), S(BASE + "/account/wishlist"),
         F(BASE + "/account/wishlist", "click_element_by_css", {"text": "Remove"})],
    22: [S(BASE + "/"), S(BASE + "/registry"),
         S(BASE + "/registry/search?first_name=Sophia&last_name=Brooks"),
         S(BASE + "/registry/114815098")],
    23: [S(BASE + "/"), S(BASE + "/registry"),
         S(BASE + "/registry/search?registry_number=114802551"),
         S(BASE + "/registry/114802551")],
    24: [S(BASE + "/"), LOGIN, F(BASE + "/account", "fill_entire_form", {}),
         S(BASE + "/registry/create"),
         F(BASE + "/registry/G26090107", "click_element_by_css", {"text": "Create Registry"})],
    25: [S(BASE + "/"), S(BASE + "/stores"), S(BASE + "/stores?state=AL"),
         S(BASE + "/stores/0274")],
    26: [S(BASE + "/"), S(BASE + "/stores"), S(BASE + "/stores/all"),
         F(BASE + "/stores/all", "scroll", {})],
    27: [S(BASE + "/"), S(BASE + "/c/DillardsCard"),
         F(BASE + "/c/DillardsCard", "scroll", {})],
    28: [S(BASE + "/"), LOGIN, F(BASE + "/account", "fill_entire_form", {}),
         S(BASE + "/account"), S(BASE + "/account/paybill"),
         F(BASE + "/account/paybill", "click_element_by_css", {"text": "Submit Payment"}),
         S(BASE + "/account/paybill")],
    29: [S(BASE + "/"), LOGIN, F(BASE + "/account", "fill_entire_form", {}),
         S(BASE + "/p/alex-marie-kaitlin-mikado-floral-applique-trim-sleeveless-shift-dress/520620253"),
         S(BASE + "/p/alex-marie-kaitlin-mikado-floral-applique-trim-sleeveless-shift-dress/520620253/reviews/new"),
         F(BASE + "/p/alex-marie-kaitlin-mikado-floral-applique-trim-sleeveless-shift-dress/520620253", "click_element_by_css", {"text": "Submit Review"}),
         S(BASE + "/p/alex-marie-kaitlin-mikado-floral-applique-trim-sleeveless-shift-dress/520620253")],
    30: [S(BASE + "/"), S(BASE + "/c/giftcard"), S(BASE + "/giftcards/purchase"),
         F(BASE + "/giftcards/purchase", "click_element_by_css", {"text": "Purchase Gift Card"})],
}

HONEST_ANSWERS = {
    0: ("The most expensive dress is the Buru Mod Print Mock Neck Sleeveless "
        "Shift Maxi Dress at $322.00."),
    1: ("5 products appear, from two brands: Roundtree & Yorke (four Gold "
        "Label non-iron dress shirts) and Murano (the Collezione Canclini "
        "Techno Knit Shirt)."),
    2: ("2 sale items appear. The cheapest is the KARL LAGERFELD PARIS Scuba "
        "Crepe Crew Neck Chiffon Long Sleeve Pearl Cuff Sheath Dress, now "
        "$92.46 (originally $138.00)."),
    3: ("4 CHANEL products appear. The COCO MADEMOISELLE EAU DE PARFUM SPRAY "
        "size prices are: 1.7 oz. Eau De Parfum Spray $154.00, 3.4 oz. Eau De "
        "Parfum Spray $185.00, and 6.8 Oz. Eau De Parfum Spray $270.00."),
    4: ("The top rated product is the Lauren Ralph Lauren Ribbed Knit Mock "
        "Neck Cap Sleeve Sweater Top with a 5.0 rating and 2 reviews."),
    5: ("4 items are listed under New Arrivals. The cheapest new arrival is "
        "the Kurt Geiger London Women's Meena Quilted Logo Ornament Pool "
        "Slide Sandals at $98.00."),
    6: "The item number shown in the Description is #20524292 and there are 25 distinct sizes available.",
    7: "The dress has 4 color options: Black, Sand, Navy, and Chestnut.",
    8: ("The shirt's overall rating is 4.6 with 778 reviews, and 622 of its "
        "reviews are 5-star reviews according to the Rating Snapshot."),
    9: ("From the Description, the dress is approximately 36 inches in length "
        "(HPS) and its fabric is polyester/elastane."),
    10: "The boots cost $220.00 and 14 size options are shown.",
    11: ("The first sentence of the About BRAHMIN section is: We're proud to "
         "be a true-to-our-roots brand with a big vision."),
    12: "The result is the Capri Blue x Pura Volcano Smart Vial Home Refill at $19.00.",
    13: ("The matching Levi's jeans are the Levi's 511 Slim Fit All Seasons "
         "Tech Jeans, now $43.54 (originally $64.99), with 19 sizes available."),
    14: ("14 products appear and the cheapest one is the Kurt Geiger London "
         "Vinyl Kensington Small Clear Camera Crossbody Bag at $82.80."),
    15: "The order number is D2609220009 and the order total is $169.34.",
    16: ("The most recent delivered order is D2609030221, tracking number "
         "1Z999AA11223344556, shipped via UPS."),
    17: ("The order containing the Investments the PARK AVE fit pants is "
         "D2609110402, placed September 11, 2026, and it contains 2 items."),
    18: ("The return for the Lancome Lash Idole mascara was requested with the "
         "reason 'Did not like the color or style' and the Return by Mail "
         "method; the credit amount shown on the Returns page is $30.00."),
    19: ("The cheapest wish list item is the Capri Blue x Pura Volcano Smart "
         "Vial Home Refill ($19.00); the new bag subtotal shown in the Order "
         "Summary is $325.00."),
    20: ("The most expensive wish list item is the Antonio Melani Carter "
         "Short Sleeve Crew Neck Crepe Sheath Midi Dress at $159.00, now removed."),
    21: ("After removing the BRAHMIN wallet, the product left on the wish list "
         "is the Tommy Bahama Two Palm Raw Edge Point Collar Long Sleeve "
         "Button Front Jacket."),
    22: ("The most expensive item not yet purchased is the Yves Saint Laurent "
         "Make Me Blush 24-Hour Buildable Powder Blush at $46.00; the CHANEL "
         "COCO MADEMOISELLE EAU DE PARFUM SPRAY is already marked as purchased."),
    23: ("The registrant is Carol Davis, the event type is a Baby registry, "
         "and there are 2 items on the registry."),
    24: "The new registry number assigned is G26090107.",
    25: ("The Dillard's store in Dothan, Alabama is Wiregrass Commons Mall, "
         "900 Commons Dr Suite 100, Dothan, AL 36303, phone (334) 794-3300."),
    26: ("54 stores are located in Texas, and the two stores in Austin are "
         "Barton Creek Square and The Domain."),
    27: ("You must earn 1,500 points to receive your choice of a 10% Off "
         "One-Day Shopping Pass or a $10 Rewards Certificate, and you earn 2 "
         "points per $1 spent at Dillard's."),
    28: ("The payment confirmation number is PMT-260922-10005 and the new "
         "current balance shown on the Pay My Bill page is $692.36."),
    29: ("The review was submitted and the updated total review count shown "
         "on the product page is 20."),
    30: ("The $100 Dillard's E-Gift Card for Maria Lopez was purchased; the "
         "gift card number received is 7334 0922 0100 0001."),
}

# Near-miss wrong answers (one key fact off per task).
WRONG_ANSWERS = {
    0: "The most expensive dress is the Buru Mod Print Mock Neck Sleeveless Shift Maxi Dress at $329.00.",
    1: "6 products appear, from two brands: Roundtree & Yorke and Murano.",
    2: "2 sale items appear. The cheapest is the KARL LAGERFELD PARIS Scuba Crepe Dress, now $94.26 (originally $138.00).",
    3: "4 CHANEL products appear. The COCO MADEMOISELLE size prices are $154.00, $185.00, and $275.00.",
    4: "The top rated product is the Lauren Ralph Lauren Ribbed Knit Mock Neck Cap Sleeve Sweater Top with a 4.9 rating and 2 reviews.",
    5: "4 items are listed under New Arrivals. The cheapest is the Women's 327 Lifestyle Sneakers at $104.99.",
    6: "The item number shown in the Description is #20524293 and there are 25 distinct sizes available.",
    7: "The dress has 3 color options: Black, Sand, and Navy.",
    8: "The shirt's overall rating is 4.6 with 778 reviews, and 623 of its reviews are 5-star reviews.",
    9: "From the Description, the dress is approximately 38 inches in length and its fabric is polyester/elastane.",
    10: "The boots cost $210.00 and 14 size options are shown.",
    11: "The first sentence of the About BRAHMIN section is: We are proud to be a brand with a small vision.",
    12: "The result is the Capri Blue x Pura Volcano Smart Vial Home Refill at $17.00.",
    13: "The matching Levi's jeans are the Levi's 511 Slim Fit All Seasons Tech Jeans, now $43.54, with 18 sizes available.",
    14: "15 products appear and the cheapest one is the Kurt Geiger London Micro Metallic Sequin Chain Crossbody Bag at $88.00.",
    15: "The order number is D2609220009 and the order total is $159.34.",
    16: "The most recent delivered order is D2609030221, tracking number 1Z999AA11223344556, shipped via FedEx.",
    17: "The order containing the Investments the PARK AVE fit pants is D2609110402, placed September 12, 2026, and it contains 2 items.",
    18: "The credit amount shown on the Returns page is $32.00.",
    19: "The cheapest wish list item is the Capri Blue x Pura Volcano Smart Vial Home Refill ($19.00); the new bag subtotal shown in the Order Summary is $319.00.",
    20: "The most expensive wish list item is the Antonio Melani Carter Short Sleeve Crew Neck Crepe Sheath Midi Dress at $149.00, now removed.",
    21: "After removing the BRAHMIN wallet, the product left on the wish list is the Polo Ralph Lauren Classic Fit Solid Cotton Mesh Polo Shirt.",
    22: "The most expensive item not yet purchased is the Yves Saint Laurent Make Me Blush 24-Hour Buildable Powder Blush at $48.00; the CHANEL COCO MADEMOISELLE is already purchased.",
    23: "The registrant is Carol Davis, the event type is a Wedding registry, and there are 2 items on the registry.",
    24: "The new registry number assigned is G26090108.",
    25: "The Dillard's store in Dothan, Alabama is Wiregrass Commons Mall, 900 Commons Dr Suite 100, Dothan, AL 36303, phone (334) 794-3301.",
    26: "53 stores are located in Texas, and the two stores in Austin are Barton Creek Square and The Domain.",
    27: "You must earn 2,500 points to receive your choice of a 10% Off One-Day Shopping Pass or a $10 Rewards Certificate, and you earn 2 points per $1 spent at Dillard's.",
    28: "The payment confirmation number is PMT-260922-10005 and the new current balance shown on the Pay My Bill page is $692.46.",
    29: "The review was submitted and the updated total review count shown on the product page is 19.",
    30: "The $100 Dillard's E-Gift Card for Maria Lopez was purchased; the gift card number received is 7334 0922 0100 0002.",
}


class VerifierContract(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="wh-dillards-test-"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def honest_run(self, number, **kw):
        run = build_run(self.root / f"honest_{number}", HONEST_STEPS[number],
                        HONEST_ANSWERS[number], task_id=f"Dillards--{number}",
                        mutate=STATE_MUTATORS.get(number), **kw)
        return run

    # ------------------------------------------------ ground truth sanity
    def test_seed_ground_truth(self):
        con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
        q = con.execute
        self.assertEqual(q("select count(*) from products").fetchone()[0], 348)
        self.assertEqual(q("select count(*) from stores").fetchone()[0], 272)
        self.assertEqual(q("select count(*) from reviews").fetchone()[0], 1788)
        self.assertEqual(q("select balance, points from card_accounts where id=1").fetchone(),
                         (842.36, 3150))
        self.assertEqual(q("select review_count from products where pid='520620253'").fetchone()[0], 19)
        self.assertEqual(q("select count(*) from orders").fetchone()[0], 8)
        self.assertEqual(q("select registry_number from registries where owner_last='Brooks'").fetchone()[0],
                         "114815098")
        self.assertEqual(q("select count(*) from stores where state_abrev='TX'").fetchone()[0], 54)
        con.close()
        self.assertEqual(len(answers.T3_COCO_SIZES), 3)
        self.assertEqual(answers.T0_NAME, "Mod Print Mock Neck Sleeveless Shift Maxi Dress")

    # ------------------------------------------------ honest runs pass
    def test_honest_runs_pass(self):
        for number in range(31):
            with self.subTest(task=number):
                run = self.honest_run(number)
                code, verdict = run_verifier(number, run)
                self.assertTrue(verdict.get("pass"),
                                f"honest run must pass: {verdict.get('reason')}")

    # ------------------------------------------------ no-op fails everywhere
    def test_noop_runs_fail(self):
        for number in range(31):
            with self.subTest(task=number):
                run = build_run(self.root / f"noop_{number}",
                                [S(BASE + "/")], "", task_id=f"Dillards--{number}")
                code, verdict = run_verifier(number, run)
                self.assertFalse(verdict.get("pass"),
                                 f"no-op run must fail (task {number})")

    def test_fabricated_answers_fail(self):
        for number in range(31):
            with self.subTest(task=number):
                run = build_run(self.root / f"fab_{number}",
                                [S(BASE + "/")], HONEST_ANSWERS[number],
                                task_id=f"Dillards--{number}")
                code, verdict = run_verifier(number, run)
                self.assertFalse(verdict.get("pass"),
                                 f"fabricated homepage-only answer must fail (task {number})")

    def test_wrong_answers_fail(self):
        for number in range(31):
            with self.subTest(task=number):
                run = build_run(self.root / f"wrong_{number}",
                                HONEST_STEPS[number], WRONG_ANSWERS[number],
                                task_id=f"Dillards--{number}",
                                mutate=STATE_MUTATORS.get(number))
                code, verdict = run_verifier(number, run)
                self.assertFalse(verdict.get("pass"),
                                 f"near-miss answer must fail (task {number}): "
                                 f"{[e for e in verdict.get('evidence', []) if e.startswith('[FAIL]')][:3]}")

    def test_shortcut_runs_fail(self):
        for number in range(31):
            with self.subTest(task=number):
                run = build_run(self.root / f"shortcut_{number}",
                                [S(BASE + "/")], HONEST_ANSWERS[number],
                                task_id=f"Dillards--{number}",
                                mutate=STATE_MUTATORS.get(number))
                code, verdict = run_verifier(number, run)
                self.assertFalse(verdict.get("pass"),
                                 f"shortcut run must fail (task {number})")

    # ------------------------------------------------ tampered packages
    def test_task_id_mismatch_fails(self):
        run = self.honest_run(0)
        traj = json.loads((run / "trajectory.json").read_text())
        traj["task_id"] = "Dillards--30"
        (run / "trajectory.json").write_text(json.dumps(traj, indent=1))
        code, verdict = run_verifier(0, run)
        self.assertFalse(verdict.get("pass"))
        self.assertEqual(verdict.get("reason"), "trajectory_task_matches")

    def test_missing_trajectory_fails(self):
        run = self.honest_run(0)
        (run / "trajectory.json").unlink()
        code, verdict = run_verifier(0, run)
        self.assertFalse(verdict.get("pass"))

    def test_corrupt_trajectory_fails(self):
        run = self.honest_run(0)
        (run / "trajectory.json").write_text("{not json")
        code, verdict = run_verifier(0, run)
        self.assertFalse(verdict.get("pass"))

    def test_truncated_run_fails(self):
        run = self.honest_run(0, terminated=False)
        code, verdict = run_verifier(0, run)
        self.assertFalse(verdict.get("pass"))

    def test_missing_screenshots_fail(self):
        run = self.honest_run(0)
        shutil.rmtree(run / "screenshots")
        code, verdict = run_verifier(0, run)
        self.assertFalse(verdict.get("pass"))

    def test_tiny_screenshots_fail(self):
        run = self.honest_run(0)
        tiny = Path(self.root / "tiny.png")
        tiny.write_bytes(make_png(7, width=8, height=8)[:200] or b"\x89PNG" + b"0" * 100)
        for shot in (run / "screenshots").glob("step_*.png"):
            shot.write_bytes(tiny.read_bytes())
        code, verdict = run_verifier(0, run)
        self.assertFalse(verdict.get("pass"))

    def test_reused_screenshot_fails(self):
        run = self.honest_run(0, shots_n=1)
        code, verdict = run_verifier(0, run)
        self.assertFalse(verdict.get("pass"),
                         "a single reused frame for every step must fail")

    def test_upstream_origin_fails(self):
        steps = [S("https://www.dillards.com/c/women-dresses?orderBy=priceHigh")]
        run = build_run(self.root / "upstream_0", steps, HONEST_ANSWERS[0],
                        task_id="Dillards--0")
        code, verdict = run_verifier(0, run)
        self.assertFalse(verdict.get("pass"))

    def test_readonly_db_mutation_fails(self):
        for number in (0, 5, 12, 16, 22, 26, 27):
            with self.subTest(task=number):
                run = build_run(self.root / f"dbmut_{number}", HONEST_STEPS[number],
                                HONEST_ANSWERS[number], task_id=f"Dillards--{number}",
                                mutate=mut_readonly)
                code, verdict = run_verifier(number, run)
                self.assertFalse(verdict.get("pass"),
                                 f"mutated after-DB must fail read-only task {number}")

    def test_stateful_without_mutation_fails(self):
        for number in STATE_MUTATORS:
            with self.subTest(task=number):
                run = build_run(self.root / f"nomut_{number}", HONEST_STEPS[number],
                                HONEST_ANSWERS[number], task_id=f"Dillards--{number}")
                code, verdict = run_verifier(number, run)
                self.assertFalse(verdict.get("pass"),
                                  f"stateful task {number} must fail without the DB change")

    def test_stateful_over_mutation_fails(self):
        def over_mutator(number):
            def apply(path):
                STATE_MUTATORS[number](path)
                con = _con(path)
                con.execute("UPDATE users SET phone='(000) 000-0000' WHERE id=1")
                con.commit()
                con.close()
            return apply
        for number in STATE_MUTATORS:
            with self.subTest(task=number):
                run = build_run(self.root / f"overmut_{number}", HONEST_STEPS[number],
                                HONEST_ANSWERS[number], task_id=f"Dillards--{number}",
                                mutate=over_mutator(number))
                code, verdict = run_verifier(number, run)
                self.assertFalse(verdict.get("pass"),
                                 f"stateful task {number} must reject extra DB changes")


if __name__ == "__main__":
    unittest.main(verbosity=2)

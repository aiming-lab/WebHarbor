"""Hardcoded ground truth for the 31 DILLARDS tasks (Dillards--0..Dillards--30).

Every constant was derived by the reviewer from the mirror's rendered pages
AND the frozen seed database (instance_seed/dillards.db, md5-verified against
the container build). Ground truth lives ONLY here and in grade.py — never in
tasks.jsonl (the agent reads that file; an answer key there leaks answers).

All money values are the page-rendered prices of the September 2026 capture
(MIRROR_DATE = 2026-09-22, pinned in seed_data.py).
"""

# ---------------------------------------------------------------- catalog facts
T0_PRICE = 322.00
T0_NAME = "Mod Print Mock Neck Sleeveless Shift Maxi Dress"
T0_BRAND = "Buru"

T1_COUNT = 5
T1_BRAND_TOKENS = (["Roundtree", "Murano"])  # 4 Gold Label R&Y shirts + 1 Murano Canclini

T2_COUNT = 2
T2_CHEAPEST_BRAND = "KARL LAGERFELD PARIS"
T2_CHEAPEST_NAME = ("Scuba Crepe Crew Neck Chiffon Long Sleeve Pearl Cuff "
                    "Sheath Dress")
T2_CURRENT = 92.46
T2_ORIGINAL = 138.00

T3_COUNT = 4
T3_COCO_NAME = "COCO MADEMOISELLE EAU DE PARFUM SPRAY"
T3_COCO_SIZES = [("1.7 oz. Eau De Parfum Spray", 154.00),
                 ("3.4 oz. Eau De Parfum Spray", 185.00),
                 ("6.8 Oz. Eau De Parfum Spray", 270.00)]
T3_COCO_PRICES = [p for _, p in T3_COCO_SIZES]

T4_BRAND = "Lauren Ralph Lauren"
T4_NAME = "Ribbed Knit Mock Neck Cap Sleeve Sweater Top"
T4_RATING = 5.0
T4_REVIEWS = 2

T5_COUNT = 4
T5_CHEAPEST_NAME = "Meena Quilted Logo Ornament Pool Slide Sandals"
T5_CHEAPEST_PRICE = 98.00

T6_ITEM = "20524292"
T6_SIZES = 25

T7_COLORS = ["Black", "Sand", "Navy", "Chestnut"]

T8_RATING = 4.6
T8_REVIEWS = 778
T8_FIVE_STAR = 622

T9_LENGTH = 36
T9_FABRIC = ["Polyester", "elastane"]

T10_PRICE = 220.00
T10_SIZES = 14

T11_SENTENCE = "We're proud to be a true-to-our-roots brand with a big vision."
T11_TOKENS = ["true-to-our-roots", "big vision"]

T12_NAME = "x Pura Volcano Smart Vial Home Refill"
T12_BRAND = "Capri Blue"
T12_PRICE = 19.00

# Two Levi's 511 jeans match the "511 slim" search; either internally
# consistent (name, price, size count) answer is accepted. Name tokens avoid
# trademark glyphs (Levi's(R) 511(TM)) that agents may transcribe either way.
T13_CANDIDATES = [
    {"tokens": ["511", "All Seasons Tech"], "price": 43.54,
     "was": 64.99, "sizes": 19, "pid": "511371759",
     "label": "511 Slim Fit All Seasons Tech Jeans"},
    {"tokens": ["511", "Slim Fit Jeans"], "price": 64.99, "was": None,
     "sizes": 31, "pid": "520393259", "label": "511 Slim Fit Jeans"},
]

T14_COUNT = 14
T14_CHEAPEST_NAME = "Vinyl Kensington Small Clear Camera Crossbody Bag"
T14_CHEAPEST_PRICE = 82.80

# ---------------------------------------------------------------- account facts
T15_ORDER = "D2609220009"
T15_TOTAL = 169.34
T15_SUBTOTAL = 159.00
T15_DRESS_NAME = "Carter Short Sleeve Crew Neck Crepe Sheath Midi Dress"
T15_SIZE = "8"
T15_SHIP_TO = "4120 Cantrell Road"
T15_PAYMENT_KIND = "Dillard's Credit Card"
T15_CARD_BEFORE = 842.36
T15_CARD_AFTER = 1011.70
T15_POINTS_BEFORE = 3150
T15_POINTS_AFTER = 3468

T16_ORDER = "D2609030221"
T16_TRACKING = "1Z999AA11223344556"
T16_CARRIER = "UPS"

T17_ORDER = "D2609110402"
T17_DATE_ISO = "2026-09-11"
T17_ITEMS = 2

T18_ITEM = "Lancome Lash Idole"
T18_REASON = "Did not like the color or style"
T18_METHOD = "Return by Mail"
T18_CREDIT = 30.00

T19_ITEM = "x Pura Volcano Smart Vial Home Refill"
T19_PRICE = 19.00
T19_SUBTOTAL = 325.00

T20_NAME = "Carter Short Sleeve Crew Neck Crepe Sheath Midi Dress"
T20_PRICE = 159.00

T21_LEFT = ("Tommy Bahama Two Palm Raw Edge Point Collar Long Sleeve "
            "Button Front Jacket")

T22_UNPURCHASED = "Make Me Blush 24-Hour Buildable Powder Blush"
T22_UNPURCHASED_PRICE = 46.00
T22_PURCHASED = "COCO MADEMOISELLE EAU DE PARFUM SPRAY"

T23_NAME = "Carol Davis"
T23_KIND = "baby"
T23_ITEMS = 2

T24_REGISTRY = "G26090107"
T24_KIND = "gift"
T24_EVENT_ISO = "2026-12-25"

T25_STORE = "Wiregrass Commons Mall"
T25_ADDRESS = "900 Commons Dr Suite 100"
T25_CITY_STATE = "Dothan, AL"
T25_ZIP = "36303"
T25_PHONE = "3347943300"

T26_TEXAS = 54
T26_AUSTIN = ["Barton Creek Square", "The Domain"]

T27_POINTS = 1500
T27_PER_DOLLAR = 2

T28_CONFIRMATION = "PMT-260922-10005"
T28_AMOUNT = 150.00
T28_METHOD = "Bank Draft"
T28_BEFORE = 842.36
T28_AFTER = 692.36

T29_PRODUCT = "Kaitlin Mikado 3D Floral Applique Trim Sleeveless Shift Dress"
T29_RATING = 5
T29_TITLE = "Stunning dress"
T29_COUNT_BEFORE = 19
T29_COUNT_AFTER = 20

T30_AMOUNT = 100.00
T30_RECIPIENT = "Maria Lopez"
T30_CODE = "7334 0922 0100 0001"

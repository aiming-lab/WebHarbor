"""Ground-truth constants for the CHASE grading contract.

HARDCODED from the frozen seed (instance_seed/chase.db, itself built
deterministically from the committed _seed_*.py literals captured from
https://www.chase.com/ on 2026-09-22). Every value below was additionally
confirmed against the rendered pages of the live mirror during the review.
Nothing here may appear in tasks.jsonl.

Row-identity notes (asserted against the seed in test_verifiers.py):
  bank_accounts: 1 alice checking (...5824)   2 alice savings (...3091)
                 3 bob checking (...1177)     4 bob savings (...5548)
                 5 carol checking (...4460)   6 carol savings (...2218)
                 7 david checking (...6642)   8 david savings (...8830)
  card_accounts: 1 alice freedom-unlimited     2 alice sapphire-preferred
                 3 bob freedom-flex          4 bob ink-business-cash
                 5 carol sapphire-reserve     6 carol united-explorer
                 7 david disney-premier       8 david prime-visa
  transfers: alice's two seeded scheduled rules are id 4 (autosave to savings,
             2026-09-25) and id 8 (automatic payment to the Freedom Unlimited
             card, 2026-10-10).
"""

MIRROR_DATE = "2026-09-22"

# ---- T0: Sapphire Reserve detail page
T0_FEE = 795
T0_APR_LOW = "19.49"
T0_APR_HIGH = "27.99"

# ---- T1: travel category listing (17 cards, all personal)
T1_COUNT = 17
T1_FREE_TOKENS = [("United", "Explorer"), ("United", "Gateway"),
                  ("Bonvoy", "Bold"), ("IHG", "Traveler")]

# ---- T2: Freedom Flex vs Freedom Unlimited earn structures
T2_FLEX_QUARTERLY = ("quarterly", "bonus categories")
T2_UNLIMITED_RATE = 1.5
T2_FLEX_FLAT = "1%"

# ---- T3: Ink Business Cash 5% categories + anniversary cap
T3_5PCT_CATS = ("office supply", "internet")
T3_CAP = 25000
T3_CAP_TOKENS = ("25,000", "25000", "25K", "25k")
T3_ANNIVERSARY = "anniversary"

# ---- T4: Chase Total Checking fee + waiver
T4_FEE = 15
T4_WAIVERS = [
    ("direct deposit", 500),
    ("balance", 1500),
    ("average beginning day balance", 5000),
]

# ---- T5: Students & Kids tab products + age ranges
T5_NAMES = ["First Banking", "High School Checking", "College Checking"]
T5_AGES = (6, 13, 17, 24)
T5_RANGES = [(6, 17), (13, 17), (17, 24)]

# ---- T6: Chase Savings fee + waiver
T6_FEE = 5
T6_WAIVERS = [
    ("balance", 300),
    ("automatic transfer", 25),
    ("autosave", 25),
    ("under the age of 25", None),
    ("under 25", None),
]

# ---- T7: CD rates (highest APY)
T7_TERM = "12"
T7_APY = 3.5
T7_MIN = 1000

# ---- T8: 30-year fixed mortgage example (ZIP 60629)
T8_RATE = 6.75
T8_APR = 6.946
T8_MONTHLY = 2270
T8_ZIP = 60629
T8_TERM = "30"

# ---- T9: mortgage calculator 300k @ 6.75% / 30y
T9_MONTHLY = 1945.79
T9_TOTAL_INTEREST = 400485.94

# ---- T10: auto refinance example
T10_APR = 6.59
T10_TERM = 48
T10_PAYMENT = 712.69

# ---- T11: car calculator 28k, 3k down, 60 mo, 6.09%
T11_MONTHLY = 484.37
T11_TOTAL = 29062.02

# ---- T12: Seattle locator + Ballard branch (id 300)
T12_COUNT = 24
T12_BALLARD_ID = 300
T12_BALLARD_ADDRESS = "5511 22nd Ave NW"
T12_BALLARD_ZIP = "98107"
T12_BALLARD_PHONE = 2064612375

# ---- T13: Chicago locator + Madison and Halsted (id 49)
T13_BRANCH_ID = 49
T13_ADDRESS_NUM = "739"
T13_ADDRESS_STREET = "W Madison"
T13_THURSDAY_OPEN = (9, 0, "AM")
T13_THURSDAY_CLOSE = (17, 0, "PM")

# ---- T14: "What happens when you pay off debt?" article effects
T14_EFFECTS = [
    ("utilization", ("lower", "decreas", "reduc", "improv")),
    ("depth of credit", ()),
    ("collection", ("paid", "updates")),
    ("temporarily lower", ()),
]

# ---- T15: 747 credit score article
T15_BAND = "very good"
T15_BAND_ALT = "prime"
T15_FACTORS = ["payment history", "utilization", "credit mix", "hard credit check",
               "new credit", "old accounts", "length of your credit history"]

# ---- T16: customer service phone numbers
T16_PERSONAL = 8009359935
T16_HOME_LENDING = 8008489136

# ---- T17: alice dashboard balances
T17_CHECKING = 4187.53
T17_SAVINGS = 12650.00

# ---- T18: alice dining transactions
T18_TOTAL = 356.61
T18_MAX_MERCHANT = "Shake Shack"
T18_MAX_AMOUNT = 32.45

# ---- T19: bob's most recent Ink Business Cash statement
T19_PERIOD = "September 2026"
T19_BALANCE = 1324.30
T19_POINTS = 1823

# ---- T20: carol Credit Journey
T20_SCORE = 781
T20_BAND = "Very Good"
T20_DELTA = 3

# ---- T21: alice transfer (checking -> savings, one-time, 2026-09-28)
T21_AMOUNT = 150
T21_DATE = "2026-09-28"
T21_MEMO = "September savings"
T21_NEW_TRANSFER = {
    "user_id": 1, "from_bank_id": 1, "to_bank_id": 2, "to_card_id": None,
    "amount": 150.0, "date": "2026-09-28", "status": "scheduled",
    "frequency": "one-time", "memo": "September savings",
}
T21_FROM_TOKENS = ("Chase Total Checking", "5824")
T21_TO_TOKENS = ("Chase Savings", "3091")

# ---- T22: cancel the scheduled automatic card transfer (seeded id 8)
T22_TRANSFER_ID = 8
T22_AMOUNT = 120
T22_CARD_TOKENS = ("Freedom Unlimited", "4081")

# ---- T23: david pays $200 to the Disney Premier Visa
T23_AMOUNT = 200
T23_BANK_ID = 7          # david Chase Total Checking ...6642
T23_CARD_ID = 7          # david Disney Premier Visa ...3358
T23_CHECKING_BEFORE = 2310.94
T23_CHECKING_AFTER = 2110.94
T23_CARD_BEFORE = 527.31
T23_CARD_AFTER = 327.31
T23_TXN_DESC_TOKENS = ("Credit Card Payment", "Disney")
T23_FROM_TOKEN = "6642"

# ---- T24: bob turns off autopay on Freedom Flex (card account id 3)
T24_CARD_ID = 3
T24_CARD_TOKENS = ("Freedom Flex", "2266")

# ---- T25: carol adds a low balance alert
T25_ALERT = {
    "user_id": 3, "alert_type": "low_balance", "channel": "mobile",
    "threshold": 2500.0, "enabled": True,
}

# ---- T26: carol redeems 25,000 Sapphire Reserve points for cash back
T26_CARD_ID = 5          # carol sapphire-reserve ...5583
T26_POINTS = 25000
T26_VALUE = 250.00
T26_POINTS_BEFORE = 128940
T26_POINTS_AFTER = 103940

# ---- T27: alice pays $150 to the higher-balance card (Sapphire Preferred ...7729)
T27_CARD_ID = 2          # alice sapphire-preferred ...7729, the higher-balance card
T27_CARD_TOKENS = ("Sapphire Preferred", "7729")
T27_OTHER_CARD_TOKENS = ("Freedom Unlimited", "4081")   # the lower-balance card
T27_AMOUNT = 150
T27_BANK_ID = 1          # alice Chase Total Checking ...5824
T27_FROM_TOKEN = "5824"
T27_CHECKING_BEFORE = 4187.53
T27_CHECKING_AFTER = 4037.53
T27_CARD_BEFORE = 1284.90
T27_CARD_AFTER = 1134.90
T27_TXN_DESC_TOKENS = ("Credit Card Payment", "Sapphire Preferred")

# ---- T28: cancel the scheduled monthly savings autosave transfer (seeded id 4)
T28_TRANSFER_ID = 4
T28_AMOUNT = 250
T28_DATE = "2026-09-25"
T28_TO_TOKENS = ("Chase Savings", "3091")

# ---- T29: public card application
T29_CARD_SLUG = "doordash-rewards-mastercard"
T29_CARD_TOKENS = ("DoorDash Rewards Mastercard", "DoorDash")
T29_APPLICANT = "Test User"
T29_EMAIL = "test.user@example.com"
T29_REF = "APP-DOO-696959"
T29_DASHPASS_OFFER = "DashPass"

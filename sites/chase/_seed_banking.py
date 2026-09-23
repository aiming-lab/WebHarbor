"""Chase online banking seed configuration — benchmark users, account setup,
merchant pools and generation parameters.

Transactions, transfers, alerts, statements and rewards rows are generated
deterministically from this tracked configuration (random.Random(42), no wall
clock), so the seed DB is byte-reproducible on every build. The benchmark
password hash below is frozen: bcrypt salts are random, so the hash is
precomputed once and hardcoded to keep builds deterministic.
"""

PASSWORD_HASH = "$2b$12$2HdteFfqXo9BS7rIkxAkru1YymG0gE9Zp6b2crB9DnIh03BU4P5N6"  # TestPass123!

MIRROR_DATE = "2026-09-22"  # the snapshot the mirror is pinned against

USERS = [
    {
        "username": "alice_j",
        "email": "alice.j@test.com",
        "display_name": "Alice Johnson",
        "first_name": "Alice",
        "last_name": "Johnson",
        "phone": "(212) 555-0184",
        "address1": "412 Orchard Street",
        "city": "New York",
        "state": "NY",
        "zip": "10002",
        "bank_accounts": [
            {"name": "Chase Total Checking", "slug": "total-checking", "acct_type": "checking",
             "masked": "5824", "balance": 4187.53, "opened": "2021-03-14"},
            {"name": "Chase Savings", "slug": "chase-savings", "acct_type": "savings",
             "masked": "3091", "balance": 12650.00, "opened": "2021-03-14"},
        ],
        "cards": [
            {"slug": "freedom-unlimited", "masked": "4081", "limit": 9000, "balance": 412.66,
             "points": 18420, "opened": "2021-06-02", "autopay": True},
            {"slug": "sapphire-preferred", "masked": "7729", "limit": 15000, "balance": 1284.90,
             "points": 53740, "opened": "2022-09-08", "autopay": False},
        ],
        "credit_score": 747,
    },
    {
        "username": "bob_c",
        "email": "bob.c@test.com",
        "display_name": "Bob Chen",
        "first_name": "Bob",
        "last_name": "Chen",
        "phone": "(206) 555-0132",
        "address1": "1731 Broadway",
        "city": "Seattle",
        "state": "WA",
        "zip": "98102",
        "bank_accounts": [
            {"name": "Chase Secure Banking", "slug": "secure-banking", "acct_type": "checking",
             "masked": "1177", "balance": 894.20, "opened": "2023-01-20"},
            {"name": "Chase Premier Savings", "slug": "premier-savings", "acct_type": "savings",
             "masked": "5548", "balance": 9400.00, "opened": "2023-01-20"},
        ],
        "cards": [
            {"slug": "freedom-flex", "masked": "2266", "limit": 6000, "balance": 238.47,
             "points": 6030, "opened": "2023-02-11", "autopay": True},
            {"slug": "ink-business-cash", "masked": "9912", "limit": 12000, "balance": 1893.02,
             "points": 41285, "opened": "2024-04-30", "autopay": False},
        ],
        "credit_score": 712,
    },
    {
        "username": "carol_d",
        "email": "carol.d@test.com",
        "display_name": "Carol Davis",
        "first_name": "Carol",
        "last_name": "Davis",
        "phone": "(312) 555-0167",
        "address1": "845 W Washington Blvd",
        "city": "Chicago",
        "state": "IL",
        "zip": "60607",
        "bank_accounts": [
            {"name": "Chase Premier Plus Checking", "slug": "premier-plus-checking", "acct_type": "checking",
             "masked": "4460", "balance": 12740.38, "opened": "2019-11-05"},
            {"name": "Chase Savings", "slug": "chase-savings", "acct_type": "savings",
             "masked": "2218", "balance": 28900.00, "opened": "2019-11-05"},
        ],
        "cards": [
            {"slug": "sapphire-reserve", "masked": "5583", "limit": 30000, "balance": 3421.75,
             "points": 128940, "opened": "2020-08-19", "autopay": True},
            {"slug": "united-explorer", "masked": "1874", "limit": 10000, "balance": 640.12,
             "points": 29850, "opened": "2021-05-27", "autopay": False},
        ],
        "credit_score": 781,
    },
    {
        "username": "david_k",
        "email": "david.k@test.com",
        "display_name": "David Kim",
        "first_name": "David",
        "last_name": "Kim",
        "phone": "(713) 555-0119",
        "address1": "2204 Dunlavy St",
        "city": "Houston",
        "state": "TX",
        "zip": "77006",
        "bank_accounts": [
            {"name": "Chase Total Checking", "slug": "total-checking", "acct_type": "checking",
             "masked": "6642", "balance": 2310.94, "opened": "2022-07-15"},
            {"name": "Chase Savings", "slug": "chase-savings", "acct_type": "savings",
             "masked": "8830", "balance": 5150.00, "opened": "2022-07-15"},
        ],
        "cards": [
            {"slug": "disney-premier", "masked": "3358", "limit": 7500, "balance": 527.31,
             "points": 8940, "opened": "2023-10-03", "autopay": False},
            {"slug": "prime-visa", "masked": "6021", "limit": 8000, "balance": 145.80,
             "points": 3610, "opened": "2024-01-22", "autopay": True},
        ],
        "credit_score": 698,
    },
]

# --- transaction merchant pools (category -> [(merchant, amount range, weight)]) ---
MERCHANTS = {
    "groceries": [
        ("Whole Foods Market", (23.50, 142.00), 3),
        ("Trader Joe's", (18.20, 89.00), 3),
        ("Kroger", (31.40, 118.00), 2),
        ("Safeway", (26.80, 104.00), 2),
        ("ALDI", (22.10, 67.00), 1),
    ],
    "dining": [
        ("Starbucks", (4.20, 14.80), 4),
        ("Chipotle Mexican Grill", (11.40, 27.90), 3),
        ("Sweetgreen", (12.80, 24.50), 2),
        ("Shake Shack", (14.20, 38.60), 2),
        ("Blue Bottle Coffee", (5.10, 13.20), 2),
        ("Domino's Pizza", (16.90, 42.00), 2),
        ("Joe's Pizza", (9.50, 31.00), 1),
    ],
    "gas": [
        ("Shell", (28.00, 74.00), 3),
        ("Chevron", (31.00, 71.00), 2),
        ("ExxonMobil", (29.50, 68.00), 2),
        ("BP", (27.40, 63.00), 1),
    ],
    "shopping": [
        ("Amazon.com", (12.99, 214.00), 4),
        ("Target", (18.60, 156.00), 3),
        ("Walmart", (22.40, 187.00), 2),
        ("Best Buy", (48.00, 420.00), 1),
        ("IKEA", (56.00, 289.00), 1),
    ],
    "utilities": [
        ("Con Edison", (68.00, 154.00), 2),
        ("Verizon Wireless", (65.00, 95.00), 3),
        ("T-Mobile", (55.00, 85.00), 2),
        ("Comcast Xfinity", (79.99, 109.99), 2),
    ],
    "entertainment": [
        ("Netflix.com", (15.49, 22.99), 3),
        ("Spotify USA", (10.99, 19.99), 3),
        ("AMC Theatres", (16.00, 58.00), 1),
        ("Steam Games", (9.99, 59.99), 1),
    ],
    "travel": [
        ("Delta Air Lines", (128.00, 642.00), 1),
        ("United Airlines", (112.00, 589.00), 1),
        ("Marriott Bonvoy Hotels", (149.00, 389.00), 1),
        ("Hyatt Hotels", (138.00, 356.00), 1),
        ("Chase Travel", (96.00, 512.00), 1),
        ("Airbnb", (110.00, 460.00), 1),
    ],
    "health": [
        ("CVS Pharmacy", (8.50, 64.00), 3),
        ("Walgreens", (7.20, 52.00), 2),
        ("Planet Fitness", (24.99, 24.99), 2),
    ],
    "home": [
        ("Home Depot", (18.90, 214.00), 2),
        ("Lowe's Home Improvement", (21.50, 198.00), 1),
    ],
}

# monthly recurring items per user (fixed, not random)
RECURRING = [
    {"merchant": "Rent Payment", "category": "home", "amount": -1850.00, "day": 1, "account": "checking"},
    {"merchant": "Payroll Deposit NORTHWIND LLC", "category": "income", "amount": 3420.00, "day": 15, "account": "checking"},
    {"merchant": "Payroll Deposit NORTHWIND LLC", "category": "income", "amount": 3420.00, "day": 30, "account": "checking"},
    {"merchant": "Netflix.com", "category": "entertainment", "amount": 15.49, "day": 8, "account": "card"},
    {"merchant": "Spotify USA", "category": "entertainment", "amount": 10.99, "day": 12, "account": "card"},
    {"merchant": "Planet Fitness", "category": "health", "amount": 24.99, "day": 5, "account": "card"},
    {"merchant": "Verizon Wireless", "category": "utilities", "amount": 78.50, "day": 18, "account": "card"},
]

# scheduled transfers seeded per user
SCHEDULED_TRANSFERS = {
    "alice_j": [
        {"from": "checking", "to": "savings", "amount": 250.00, "day_of_month": 25,
         "frequency": "monthly", "memo": "Autosave to savings"},
        {"from": "checking", "to": "card:freedom-unlimited", "amount": 120.00, "day_of_month": 10,
         "frequency": "monthly", "memo": "Freedom Unlimited automatic payment"},
    ],
    "bob_c": [
        {"from": "checking", "to": "savings", "amount": 150.00, "day_of_month": 20,
         "frequency": "monthly", "memo": "Autosave to Premier Savings"},
    ],
    "carol_d": [
        {"from": "checking", "to": "savings", "amount": 500.00, "day_of_month": 5,
         "frequency": "monthly", "memo": "Vacation fund"},
        {"from": "checking", "to": "card:sapphire-reserve", "amount": 850.00, "day_of_month": 12,
         "frequency": "monthly", "memo": "Sapphire Reserve automatic payment"},
    ],
    "david_k": [
        {"from": "checking", "to": "savings", "amount": 100.00, "day_of_month": 22,
         "frequency": "monthly", "memo": "Autosave to savings"},
    ],
}

ALERTS = {
    "alice_j": [
        {"alert_type": "large_transaction", "threshold": 200.00, "channel": "mobile"},
        {"alert_type": "low_balance", "threshold": 300.00, "channel": "mobile"},
        {"alert_type": "deposit_received", "threshold": None, "channel": "email"},
    ],
    "bob_c": [
        {"alert_type": "large_transaction", "threshold": 100.00, "channel": "mobile"},
        {"alert_type": "payment_due", "threshold": None, "channel": "email"},
    ],
    "carol_d": [
        {"alert_type": "large_transaction", "threshold": 500.00, "channel": "mobile"},
        {"alert_type": "low_balance", "threshold": 1000.00, "channel": "mobile"},
        {"alert_type": "card_charge", "threshold": None, "channel": "mobile"},
    ],
    "david_k": [
        {"alert_type": "low_balance", "threshold": 150.00, "channel": "email"},
    ],
}

REDEMPTIONS = {
    "alice_j": [
        {"card": "freedom-unlimited", "points": 10000, "value": 100.00, "type": "cash back",
         "date": "2026-08-14", "desc": "Cash back deposited to Chase Total Checking"},
        {"card": "sapphire-preferred", "points": 25000, "value": 312.50, "type": "travel",
         "date": "2026-07-02", "desc": "Chase Travel - Marriott Bonvoy stay"},
    ],
    "bob_c": [
        {"card": "ink-business-cash", "points": 20000, "value": 200.00, "type": "cash back",
         "date": "2026-09-01", "desc": "Cash back statement credit"},
    ],
    "carol_d": [
        {"card": "sapphire-reserve", "points": 50000, "value": 750.00, "type": "travel",
         "date": "2026-08-20", "desc": "Chase Travel - United Airlines flight"},
        {"card": "sapphire-reserve", "points": 15000, "value": 150.00, "type": "cash back",
         "date": "2026-06-11", "desc": "Cash back deposited to checking"},
    ],
    "david_k": [
        {"card": "disney-premier", "points": 5000, "value": 50.00, "type": "statement credit",
         "date": "2026-09-05", "desc": "Disney Rewards Dollars redemption"},
    ],
}

# credit score history: 6 monthly snapshots ending at the user's current score
CREDIT_HISTORY = {
    "alice_j": [729, 733, 738, 741, 745, 747],
    "bob_c": [700, 705, 703, 708, 710, 712],
    "carol_d": [768, 772, 779, 775, 778, 781],
    "david_k": [681, 687, 691, 690, 694, 698],
}

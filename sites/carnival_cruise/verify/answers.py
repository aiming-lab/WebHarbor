"""Ground-truth constants for the CARNIVAL CRUISE grading contract.

HARDCODED from the frozen seed (instance_seed/carnival_cruise.db, itself built
deterministically from the committed _seed_*.py literals captured from
https://www.carnival.com/ on 2026-09-22). Every value below was additionally
confirmed against the rendered pages of the live mirror during the review.
Nothing here may appear in tasks.jsonl.
"""

# ---- itinerary anchors (code, departure-port code, ship code, duration)
BAW = "baw"          # 3-Day The Bahamas from Miami, Carnival Conquest (T0/T7/T10/T13)
BR6 = "br6"          # 5-Day Bermuda from Manhattan, Carnival Firenze (T8 anchor)
LXQ = "lxq"          # 4-Day Baja Mexico from Long Beach (T9/T12 anchors)

# itinerary URL path prefixes as rendered by the mirror
BAW_URL = "/itinerary/3-day-the-bahamas-cruise/miami/conquest/3-days/baw"
BERMUDA5_PREFIX = "/itinerary/5-day-bermuda-cruise/manhattan-new-york-city"
BAJA4_PREFIX = "/itinerary/4-day-baja-mexico-cruise/long-beach-los-angeles"
BAJA4_FRENZE_PREFIX = BAJA4_PREFIX + "/firenze"

# ---- T0: cheapest 3-day cruise from Miami (unique: $183 vs next $272)
T0_TITLE = "3-Day The Bahamas from Miami, FL"
T0_PRICE = 183

# ---- T1: Galveston departure count
T1_COUNT = 56

# ---- T2: Alaska cruises (dest=A -> region families GL/AJ)
T2_COUNT = 8
T2_MIN_DAYS = 7

# ---- T3: cheapest 5-day MIA visiting Celebration Key + RelaxAway Half Moon Cay
T3_TITLE = "5-Day The Bahamas from Miami, FL"      # itinerary BH9
T3_SHIP = "Carnival Sunrise"
T3_PRICE = 215

# ---- T4: longest cruise from New Orleans
T4_TITLE = "14-Day Caribbean & Panama from New Orleans, LA"   # JPB
T4_DAYS = 14
T4_PRICE = 1299

# ---- T5: highest starting price among MIA departures
T5_TITLE = "7-Day Eastern Caribbean from Miami, FL"          # CBX
T5_PRICE = 1154

# ---- T6: ships offering BOLT: The Ultimate Sea Coaster
T6_SHIPS = ["Carnival Celebration", "Carnival Jubilee", "Mardi Gras"]

# ---- T7: BAW day schedule (Celebration Key call)
T7_PORT = "Celebration Key"
T7_DAY = 3
T7_DEPART = (4, 0, "PM")     # 4:00 PM

# ---- T8: 5-Day Bermuda port call (all 5-day Bermuda itineraries)
T8_DAYS = (3, 4)             # Bermuda on days 3 and 4 (arrive d3, depart d4 4:00 PM)
T8_PORT = "Bermuda"

# ---- T9: 4-Day Baja Mexico other port (dominant across the LX* variants)
T9_PORT = "Catalina Island"
T9_DAYS = (2, 3)             # day 2 on nearly all variants, day 3 on LXP

# ---- T10: Conquest "Get to Know" burger venue
T10_VENUE = "Guy's Burger Joint"

# ---- T11: cheapest 7-day GAL via Grand Cayman + Cozumel
T11_TITLE = "7-Day Western Caribbean from Galveston, TX"     # CWC on Breeze
T11_SHIP = "Carnival Breeze"
T11_PRICE = 632

# ---- T12: Firenze 4-Day Baja final-day arrival at Long Beach
T12_ARRIVE = (8, 0, "AM")    # 8:00 AM

# ---- T13: booking math (BAW sailing 22233 departs 2026-09-25)
T13_EMAIL = "jordan.rivera@example.com"
T13_LEAD = "Jordan Rivera"
T13_SAILING_ID = "22233"
T13_ROOM = "interior"
T13_GUESTS = 2
T13_PER_PERSON = 429
T13_TOTAL = 858            # 429 x 2
T13_CARD_LAST4 = "1111"
T13_CARD_TYPE = "Visa"

# ---- T14: alice's booking 9N382701
T14_BOOKING = "9N382701"
T14_CABIN = "5C102"
T14_CATEGORY = "Premium Balcony"

# ---- T15: alice's September-2026 departure (identified, NOT cancelled)
T15_BOOKING = "9N382701"
T15_TITLE = "3-Day The Bahamas from Miami, FL"

# ---- T16: bob's booking 9N510304 excursion
T16_BOOKING = "9N510304"
T16_EXCURSION = "Beach Escape: Island's Beach Club, Pool & Snorkel"
T16_GUESTS = 2
T16_PRICE = 95.98

# ---- T17: alice's March-2027 booking + Pearl Cove add-on
T17_BOOKING = "9N382702"
T17_BASE_TOTAL = 1338.00
T17_EXCURSION_CODE = "409063"          # Pearl Cove Beach Club: All Inclusive
T17_EXCURSION_TITLE = "Pearl Cove Beach Club: All Inclusive"
T17_EXC_GUESTS = 2
T17_EXC_PRICE = 251.98                 # 125.99 x 2
T17_NEW_TOTAL = 1589.98                # 1338.00 + 251.98

# ---- T18/T19: Cozumel price extremes
T18_TITLE = "The Cruiser's Choice: Downtown Vibes & Beach Club"
T18_PRICE = 44.99
T19_TITLE = "Fully Accessible Private Van & Expert Host"
T19_PRICE = 629.99

# ---- T20: Pearl Cove Beach Club details
T20_PRICE = 125.99
T20_HOURS = 6.0

# ---- T21: Juneau top-rated + most-reviewed excursion
T21_TITLE = "Evening Whale Quest With Dinner"
T21_RATING = 5.0
T21_REVIEWS = 6

# ---- T22: Dolphin Swim & Ocean World Day Pass minimum age
T22_MIN_AGE = 6

# ---- T23: Carnival Celebration zones
T23_COUNT = 6
T23_ZONES = ["Celebration Central", "The Gateway", "Summer Landing",
             "820 Biscayne", "Lido", "The Ultimate Playground"]

# ---- T24: Mardi Gras dining included in the cruise fare
T24_VENUES = ["Chibang!", "Street Eats", "Big Chicken", "Cucina del Capitano"]

# ---- T25: Carnival Jubilee home port
T25_PORT = "Galveston"

# ---- T26: Carnival Celebration experiences marked Additional (besides BOLT)
T26_ADDITIONAL = [
    "Latitudes", "The Golden Jubilee", "CLOUD 9 SPA",
    "Emeril's Bistro 1397", "Rudi's Seagrill", "Bonsai Teppanyaki",
    "Guy's Pig & Anchor Smokehouse | Brewhouse", "Bonsai Sushi",
    "Fahrenheit 555 Steakhouse", "Seafood Shack",
]
T26_REQUIRED = 2

# ---- T27: CHEERS! beverage package
T27_PRICE = 69.95

# ---- T28: Contact Us weekend Customer Service hours
T28_OPEN = (9, 0, "AM")     # 9:00 a.m.
T28_CLOSE = (6, 0, "PM")    # 6:00 p.m.
T28_TZ = {"ET", "Eastern Time", "Eastern"}

# ---- T29: carol's saved cruises
T29_COUNT = 5
T29_SHORTEST = "3-Day The Bahamas from Miami, FL"

# benchmark accounts
ALICE, BOB, CAROL, DAVID = ("alice.j@test.com", "bob.c@test.com",
                            "carol.d@test.com", "david.k@test.com")
DEMO_PASSWORD = "TestPass123!"

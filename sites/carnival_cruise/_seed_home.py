"""Carnival homepage and deals content captured verbatim from the rendered
upstream homepage on 2026-09-22 (scraped_data/homepage.html)."""

HERO_PROMO = {
    "headline_a": "One",
    "headline_b": "Last Time!",
    "subhead": "Get More Time To Pay",
    "offer_main": "Final Payment Is Due",
    "offer_days": "30*",
    "offer_tail": "Days Before You Sail",
    "bullets": [
        "Up to $50 onboard credit",
        "Room upgrade from $1",
        "50% off deposits",
    ],
    "cta": "DON'T MISS OUT",
    "terms": "*Terms and conditions apply",
    "image": "static/images/home/couple-balcony-sunset-dsk.jpg",
}

REWARDS_CARD_PROMO = {
    "eyebrow": "limited-time offer:",
    "headline": "50,000 bonus points",
    "copy": ("Earn 50,000 Carnival Rewards® Points. Plus enjoy a 0% promo APR for "
             "6 months on all eligible Carnival Cruise bookings. See if you "
             "pre-qualify with no impact to your credit score. Terms apply."),
    "cta": "PRE-QUALIFY",
    "image": "static/images/home/CCL_Reward_Logo.png",
}

DEST_SALE_TILES = [
    {"title": "The Bahamas Sailings", "from_price": 183, "from_days": "3 DAYS",
     "href": "/cruise-search?dest=BH", "image": "static/images/home/bahamas-pack.jpg"},
    {"title": "Caribbean Sailings", "from_price": 242, "from_days": "6 DAYS",
     "href": "/cruise-search?dest=C", "image": "static/images/home/caribbean-pack.jpg"},
    {"title": "Mexico Sailings", "from_price": 227, "from_days": "2 DAYS",
     "href": "/cruise-search?dest=M", "image": "static/images/home/mexico-pack.jpg"},
    {"title": "Paradise Collection™", "from_price": 183, "from_days": "3 DAYS",
     "href": "/cruise-search?cruisedeals=paradisecollection", "image": "static/images/home/celebration-2.jpg"},
]

PARADISE_BANNER = {
    "headline_a": "Experience",
    "headline_b": "Paradise Collection™",
    "copy": ("Welcome to the largest collection of cruise destinations across the "
             "Caribbean, the Bahamas and Mexico. Where every stop offers a unique "
             "way to experience paradise."),
    "cta": "LEARN MORE",
    "href": "/cruise-search?cruisedeals=paradisecollection",
    "image": "static/images/home/paradise-collection-dsk.jpg",
}

REWARDS_BANNER = {
    "headline": "the all-new Carnival Rewards™ has arrived",
    "copy": "A new way to earn rewards on the Carnival vacations you love",
    "cta": "EXPLORE CARNIVAL REWARDS",
    "href": "/carnival-rewards",
    "image": "static/images/home/mc-ctile2.jpg",
}

VALUE_PACKAGES = {
    "headline": "Value Package Fun For Everyone",
    "subhead": "Now available for the whole family on sailings through 2027!",
    "copy": ("Adults, kids, and teens can enjoy a collection of great benefits, "
             "added value, and more ways to make every vacation moment count."),
    "book_by": "Book by September 30th, 2026!*",
    "packages": [
        {"name": "Essentials Value Package", "price": 50, "unit": "per person, per day"},
        {"name": "Ultimate Value Package", "price": 90, "unit": "per person, per day"},
        {"name": "Kids & Teens Value Package", "price": 25, "unit": "per person, per day"},
    ],
    "cta_a": "SHOP SAILINGS",
    "cta_b": "LEARN MORE",
    "booked_note": "Already booked a cruise? Add it now",
    "image": "static/images/home/friends-ship-blue-dsk-3.jpg",
}

SHIP_TILES = [
    {"name": "Carnival Celebration®", "homeport": "Miami", "slug": "carnival-celebration",
     "image": "static/images/home/celebration.jpg"},
    {"name": "Mardi Gras®", "homeport": "Port Canaveral", "slug": "mardi-gras",
     "image": "static/images/home/mardi-gras.jpg"},
    {"name": "Carnival Jubilee®", "homeport": "Galveston", "slug": "carnival-jubilee",
     "image": "static/images/home/jubilee.jpg"},
    {"name": "Carnival Festivale™", "homeport": "Port Canaveral", "slug": "carnival-festivale",
     "image": "static/images/home/festivale-sky.jpg"},
]

NEW_SAILINGS_PROMO = {
    "eyebrow_a": "New Sailings",
    "eyebrow_b": "Unlocked",
    "title": "Carnival Jubilee®",
    "copy": ("Experience Carnival Jubilee in a whole new way. For the first time, the "
             "ship will offer short 4-5 day western Caribbean sailings from Galveston "
             "throughout 2028-2029."),
    "cta": "SEARCH CRUISES",
    "href": "/cruise-search?shipcode=JB",
    "image": "static/images/home/jubilee-ship.jpg",
}

FLEX_PAY_PROMO = {
    "headline_a": "Book Today.",
    "headline_b": "Pay Over Time.",
    "offer_items": [
        {"label": "up to $100 statement credit", "note": "Select Sailings Through May 2027"},
        {"label": "0% APR", "note": None},
        {"label": "from $0 down", "note": None},
    ],
    "cta": "SHOP THIS DEAL",
    "href": "/cruise-search?cruisedeals=flexpay_offer",
    "image": "static/images/home/wave-blue-dsk.png",
}

TOUTS = [
    {"title": "2027 Sailings",
     "copy": "Don't let another year sail by without taking a cruise! Check out all the fun places you can save on in 2027.",
     "cta": "SHOP NOW", "href": "/cruise-search?dates=2027",
     "image": "static/images/home/icon-calendar-tout.svg"},
    {"title": "2-5 Day Cruises",
     "copy": "Get big savings! Check out 2-5 day cruise deals and begin to plan your next adventure.",
     "cta": "SHOP NOW", "href": "/cruise-search?dur=D1",
     "image": "static/images/home/121417-t3-fs.png"},
    {"title": "Paradise Collection™",
     "copy": ("From breathtaking, white-sand beaches to vibrant cultures and unforgettable "
              "experiences, each destination offers a different slice of paradise."),
     "cta": "SHOP NOW", "href": "/cruise-search?cruisedeals=paradisecollection",
     "image": "static/images/home/ck-tile.jpg"},
    {"title": "Explore Australia Cruises",
     "copy": "Sail from Sydney or Brisbane for Aussie adventures or to exotic South Pacific Islands.",
     "cta": "LEARN MORE", "href": "/cruise-to/australia-cruises",
     "image": "static/images/home/australia-tout.png"},
]

IMPORTANT_NOTICE = ("Get important information on a privacy event that may impact you.")

PHONE = "1.800.764.7419"
COPYRIGHT = "© 2026 Carnival Corporation Ltd. All rights reserved."

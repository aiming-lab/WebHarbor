"""Seed data for the american_express mirror.

All card, banking, offer, and redemption content below is captured from the
live americanexpress.com pages and its published OneSite data JSON
(see scraped_data/ provenance files, gitignored build-time artifacts).

Deterministic seeding rules (see AGENTS.md "Idempotent seeding"):
- every seed function early-returns when its tables are populated
- no wall-clock reads; dates are pinned constants relative to MIRROR_DATE
- benchmark password hashes are frozen constants so the SQLite output is
  byte-identical on every build (PYTHONHASHSEED=0)
"""
from __future__ import annotations

import json
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy  # noqa: F401  (type hint only)

MIRROR_DATE = datetime(2026, 9, 21)

# Frozen bcrypt hash of "TestPass123!" — generated once, committed so the seed
# database is byte-reproducible across builds.
TEST_PASSWORD_HASH = (
    "$2b$12$Edfx/8NMUXWxIPZjYtJMEO/29jRaf0eI.hTrvScR.paVL58dJtNqa"
)


def _date(year, month, day):
    return datetime(year, month, day)


# ---------------------------------------------------------------------------
# Cards — every field transcribed from the live site (2026-09 capture).
# ---------------------------------------------------------------------------

CARD_CATEGORIES = [
    # slug, display name, filter label, intro copy (from vac heroText/category pages)
    ("travel-rewards", "Travel Rewards", "Travel",
     "Travel Credit Cards from American Express — earn points or miles on flights, hotels, and everyday purchases."),
    ("cash-back", "Cash Back", "Cash Back",
     "Cash Back Credit Cards from American Express — earn cash back at U.S. supermarkets, gas stations, and on streaming subscriptions."),
    ("reward-points", "Membership Rewards® Points", "Membership Rewards® Points",
     "Earn Membership Rewards® points on eligible purchases and redeem them for travel, gift cards, statement credits, and more."),
    ("no-annual-fee", "No Annual Fee", "No Annual Fee",
     "No Annual Fee Credit Cards from American Express — enjoy the benefits of an American Express Card with a $0 annual fee."),
    ("zero-percent-intro-apr", "0% Intro APR", "0% Intro APR",
     "Credit Cards with 0% Intro APR offers from American Express — pay no interest on purchases during the introductory period."),
    ("no-foreign-transaction-fee", "No Foreign Transaction Fee", "No FX Fee",
     "No Foreign Transaction Fee Credit Cards from American Express — use your Card abroad without foreign transaction fees."),
    ("airline-miles", "Airline Miles", "Airline",
     "Airline Credit Cards from American Express — earn miles with Delta Air Lines on every eligible purchase."),
    ("hotel-rewards", "Hotel Rewards", "Hotel",
     "Hotel Credit Cards from American Express — earn points with Hilton Honors and Marriott Bonvoy on eligible stays."),
    ("balance-transfer", "Balance Transfer", "Balance Transfer",
     "Balance Transfer Credit Cards from American Express — transfer a balance and pay it off with a low intro APR."),
    ("lounge-access", "Lounge Access", "Lounge Access",
     "Airport lounge access is included with select American Express Cards through the Global Lounge Collection®."),
]

# slug, name, product_type, fee_text, fee_value, apr_text, welcome headline,
# welcome body, offer_end, benefits (list), program, card art, categories, featured
CARDS = [
    {
        "slug": "platinum",
        "name": "Platinum Card®",
        "short_name": "Platinum Card",
        "product_type": "charge",
        "annual_fee_text": "$895",
        "annual_fee_value": 895,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "AS HIGH AS 175,000 Membership Rewards® points",
        "welcome_body": "after you spend $12,000 in purchases on your new Card within the first 6 months of Card Membership. Welcome offers vary and you may not be eligible for an offer.",
        "offer_end": _date(2026, 11, 4),
        "rewards_summary": "Membership Rewards® Points",
        "benefits": [
            "Earn 5X points on prepaid hotels and flights booked through American Express Travel®. Points cap applies.",
            "Access to 1,550+ airport lounges worldwide with American Express Global Lounge Collection®. Terms apply.",
            "Up to $600 back in statement credits annually ($300 back semi-annually) on select prepaid hotel bookings through American Express Travel® with your Card.",
        ],
        "program": "Membership Rewards",
        "card_art": "static/images/category/platinum-card.png",
        "benefit_images": {"2": "static/images/charge-products/hotel.jpg"},
        "categories": ["travel-rewards", "reward-points", "no-foreign-transaction-fee", "lounge-access"],
        "featured": True,
    },
    {
        "slug": "gold-card",
        "name": "American Express® Gold Card",
        "short_name": "Gold Card",
        "product_type": "charge",
        "annual_fee_text": "$325",
        "annual_fee_value": 325,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "AS HIGH AS 100,000 Membership Rewards® points",
        "welcome_body": "after you spend $8,000 in purchases on your new Card within the first 6 months of Card Membership. Welcome offers vary and you may not be eligible for an offer.",
        "offer_end": _date(2026, 11, 4),
        "rewards_summary": "Membership Rewards® Points",
        "benefits": [
            "Earn 4X points at restaurants worldwide, on up to $50K in purchases per calendar year, then 1X.",
            "Earn 4X points at U.S. supermarkets, on up to $25K in purchases per calendar year, then 1X.",
            "Earn 5X points on prepaid hotel stays booked through AmexTravel.com or the Amex Travel App™.",
        ],
        "program": "Membership Rewards",
        "card_art": "static/images/category/gold-card.png",
        "categories": ["travel-rewards", "reward-points", "no-foreign-transaction-fee"],
        "featured": True,
    },
    {
        "slug": "blue-cash-preferred",
        "name": "Blue Cash Preferred® Card",
        "short_name": "Blue Cash Preferred",
        "product_type": "credit",
        "annual_fee_text": "$0 intro annual fee for the first year, then $95",
        "annual_fee_value": 95,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "AS HIGH AS $300 Cash Back",
        "welcome_body": "after you spend $3,000 in purchases on your new Card within the first 6 months of Card Membership. Cash back is received in the form of Reward Dollars that can be redeemed for a statement credit or at Amazon.com checkout. Welcome offers vary and you may not be eligible for an offer.",
        "offer_end": _date(2026, 11, 4),
        "rewards_summary": "Cash Back",
        "benefits": [
            "Earn 6% cash back at U.S. supermarkets, on up to $6K in purchases per calendar year, then 1%.",
            "Earn 6% cash back on select U.S. streaming subscriptions.",
            "Earn 3% cash back on transit purchases including buses, subways, and rideshares.",
        ],
        "program": "Cash Back",
        "card_art": "static/images/category/blue-cash-preferred.png",
        "categories": ["cash-back", "zero-percent-intro-apr", "balance-transfer"],
        "featured": True,
    },
    {
        "slug": "blue-cash-everyday",
        "name": "Blue Cash Everyday® Card",
        "short_name": "Blue Cash Everyday",
        "product_type": "credit",
        "annual_fee_text": "No Annual Fee",
        "annual_fee_value": 0,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "AS HIGH AS $200 Cash Back",
        "welcome_body": "after you spend $2,000 in purchases on your new Card within the first 6 months of Card Membership. Cash back is received in the form of Reward Dollars that can be redeemed for a statement credit or at Amazon.com checkout. Welcome offers vary and you may not be eligible for an offer.",
        "offer_end": _date(2026, 11, 4),
        "rewards_summary": "Cash Back",
        "benefits": [
            "Earn 3% cash back at U.S. supermarkets on up to $6K in purchases per calendar year (then 1%).",
            "Earn 3% cash back at U.S. gas stations on up to $6K in purchases per calendar year (then 1%).",
            "Earn 3% cash back on U.S. online retail purchases, on up to $6K in purchases per calendar year (then 1%).",
        ],
        "program": "Cash Back",
        "card_art": "static/images/category/blue-cash-everyday.png",
        "categories": ["cash-back", "no-annual-fee", "zero-percent-intro-apr", "balance-transfer"],
        "featured": False,
    },
    {
        "slug": "delta-skymiles-blue-american-express-card",
        "name": "Delta SkyMiles® Blue American Express Card",
        "short_name": "Delta SkyMiles Blue",
        "product_type": "credit",
        "annual_fee_text": "No Annual Fee",
        "annual_fee_value": 0,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "Earn 10,000 Bonus Miles",
        "welcome_body": "after you spend $1,000 on eligible purchases on your new Card within your first 6 months of Card Membership.",
        "offer_end": _date(2026, 11, 4),
        "rewards_summary": "Delta SkyMiles",
        "benefits": [
            "Earn 2X Miles at restaurants and on Delta purchases.",
            "Earn 20% back on in-flight purchases made with your Card on Delta flights.",
            "No foreign transaction fees on purchases made outside the U.S.",
        ],
        "program": "Delta SkyMiles",
        "card_art": "static/images/category/delta-blue.png",
        "categories": ["airline-miles", "travel-rewards", "no-annual-fee", "no-foreign-transaction-fee"],
        "featured": False,
    },
    {
        "slug": "delta-skymiles-gold-american-express-card",
        "name": "Delta SkyMiles® Gold American Express Card",
        "short_name": "Delta SkyMiles Gold",
        "product_type": "credit",
        "annual_fee_text": "$0 introductory annual fee for the first year, then $150",
        "annual_fee_value": 150,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "Two-Part Welcome Offer: As High As 80,000 Bonus Miles",
        "welcome_body": "after you spend $3,000 in purchases on your new Card within the first 6 months of Card Membership. You may not be eligible for the maximum welcome offer amount. Plus, earn a $250 Statement Credit and the bonus miles, once you meet that same spend requirement for the bonus miles. Offer ends 11/4/2026.",
        "offer_end": _date(2026, 11, 4),
        "rewards_summary": "Delta SkyMiles",
        "benefits": [
            "Earn 2X Miles on Delta purchases, at restaurants, and at U.S. supermarkets.",
            "Earn a $200 Delta Flight Credit toward your next trip after you spend $10,000 in purchases in a year.",
            "Save 15% (excluding on taxes & fees) when you book Award Travel on Delta and Delta Connection carrier-operated flights. Discount not applicable to partner-operated flights or to taxes and fees.",
        ],
        "program": "Delta SkyMiles",
        "card_art": "static/images/category/gold-delta-skymiles.png",
        "benefit_images": {"1": "static/images/credit-cards/USD200DeltaFlightCredit_Desktop.webp"},
        "categories": ["airline-miles", "travel-rewards", "no-foreign-transaction-fee"],
        "featured": False,
    },
    {
        "slug": "delta-skymiles-platinum-american-express-card",
        "name": "Delta SkyMiles® Platinum American Express Card",
        "short_name": "Delta SkyMiles Platinum",
        "product_type": "credit",
        "annual_fee_text": "$350",
        "annual_fee_value": 350,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "Two-Part Welcome Offer: As High As 90,000 Bonus Miles",
        "welcome_body": "after you spend $4,000 in purchases on your new Card within the first 6 months of Card Membership. You may not be eligible for the maximum welcome offer amount. Plus, earn a $300 Statement Credit and the bonus miles, once you meet that same spend requirement for the bonus miles. Offer ends 11/4/2026.",
        "offer_end": _date(2026, 11, 4),
        "rewards_summary": "Delta SkyMiles",
        "benefits": [
            "First Bag Free and NEW Second Bag Free on Delta flights.",
            "Get closer to Medallion Status with MQD Headstart and MQD Boost.",
            "Take 15% off Award Travel on Delta flights. Not applicable to partner operated flights or to taxes and fees.",
        ],
        "program": "Delta SkyMiles",
        "card_art": "static/images/category/platinum-delta-skymiles.png",
        "benefit_images": {"1": "static/images/credit-cards/MQDHeadstart_Desktop.webp"},
        "categories": ["airline-miles", "travel-rewards", "no-foreign-transaction-fee"],
        "featured": False,
    },
    {
        "slug": "delta-skymiles-reserve-american-express-card",
        "name": "Delta SkyMiles® Reserve American Express Card",
        "short_name": "Delta SkyMiles Reserve",
        "product_type": "credit",
        "annual_fee_text": "$650",
        "annual_fee_value": 650,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "Two-Part Welcome Offer: Earn Two Round-Trip Delta Comfort Flights + Earn 50,000 Bonus Miles",
        "welcome_body": "Earn two round-trip Delta Comfort Flight Certificates valid for travel to the U.S. 48, Puerto Rico, or the U.S. Virgin Islands, along with 50,000 Bonus Miles after you spend $10,000 in purchases on your new Card in the first 6 months. A 21+ day advance purchase is required. Taxes and fees up to $80 per person apply. Offer ends 11/4/2026.",
        "offer_end": _date(2026, 11, 4),
        "rewards_summary": "Delta SkyMiles",
        "benefits": [
            "Complimentary access to the Centurion® Lounge when you book a Delta flight with your Delta Reserve Card, plus Delta Sky Club® access when flying Delta.",
            "With the $240 Resy Credit, earn up to $20 per month in statement credits on eligible Resy purchases using your enrolled Card.",
            "Get closer to Medallion Status with MQD Headstart and MQD Boost.",
        ],
        "program": "Delta SkyMiles",
        "card_art": "static/images/category/delta-reserve.png",
        "benefit_images": {"0": "static/images/featured-benefits/deltareserve-centurion-lounge.jpg", "2": "static/images/credit-cards/MQDHeadstartDR_Desktop.webp"},
        "categories": ["airline-miles", "travel-rewards", "no-foreign-transaction-fee", "lounge-access"],
        "featured": False,
    },
    {
        "slug": "hilton-honors",
        "name": "Hilton Honors American Express Card",
        "short_name": "Hilton Honors Card",
        "product_type": "credit",
        "annual_fee_text": "No Annual Fee",
        "annual_fee_value": 0,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "Earn 70,000 Hilton Honors Bonus Points + A Free Night Reward",
        "welcome_body": "after you spend $2,000 in purchases on the Hilton Honors American Express Card in the first 6 months of Card Membership. Offer ends 1/13/2027.",
        "offer_end": _date(2027, 1, 13),
        "rewards_summary": "Hilton Honors Bonus Points",
        "benefits": [
            "Earn 7X Hilton Honors Bonus Points on eligible Hilton purchases.",
            "Earn 5X Hilton Honors Bonus Points at U.S. restaurants, U.S. gas stations, and U.S. supermarkets.",
            "Complimentary Hilton Honors™ Silver Status.",
        ],
        "program": "Hilton Honors",
        "card_art": "static/images/category/hilton-honors.png",
        "benefit_images": {"2": "static/images/credit-cards/SilverStatusHH_Desktop.webp"},
        "categories": ["hotel-rewards", "travel-rewards", "no-annual-fee", "no-foreign-transaction-fee"],
        "featured": False,
    },
    {
        "slug": "hilton-honors-surpass",
        "name": "Hilton Honors American Express Surpass® Card",
        "short_name": "Hilton Honors Surpass",
        "product_type": "credit",
        "annual_fee_text": "$150",
        "annual_fee_value": 150,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "Earn 130,000 Hilton Honors Bonus Points + A Free Night Reward",
        "welcome_body": "after you spend $3,000 in purchases on the Hilton Honors American Express Surpass® Card in the first 6 months of Card Membership. Offer ends 1/13/2027.",
        "offer_end": _date(2027, 1, 13),
        "rewards_summary": "Hilton Honors Bonus Points",
        "benefits": [
            "Earn 12X Hilton Honors Bonus Points on eligible Hilton purchases.",
            "Earn 6X Hilton Honors Bonus Points at U.S. restaurants, U.S. gas stations, and U.S. supermarkets.",
            "Earn 4X Hilton Honors Bonus Points on U.S. Online Retail Purchases.",
        ],
        "program": "Hilton Honors",
        "card_art": "static/images/category/hilton-honors-surpass.png",
        "categories": ["hotel-rewards", "travel-rewards", "no-foreign-transaction-fee"],
        "featured": False,
    },
    {
        "slug": "hilton-honors-aspire",
        "name": "Hilton Honors American Express Aspire Card",
        "short_name": "Hilton Honors Aspire",
        "product_type": "credit",
        "annual_fee_text": "$550",
        "annual_fee_value": 550,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "Best Hilton Points Offer Yet: Earn 200,000 Hilton Honors Bonus Points",
        "welcome_body": "with the Hilton Honors American Express Aspire Card after you spend $6,000 in purchases on the Card within your first 6 months of Card Membership. Offer ends 1/13/2027.",
        "offer_end": _date(2027, 1, 13),
        "rewards_summary": "Hilton Honors Bonus Points",
        "benefits": [
            "Earn 14X Hilton Honors Bonus Points on eligible Hilton purchases.",
            "Earn 7X Hilton Honors Bonus Points at U.S. Restaurants and on Select Travel Purchases.",
            "Complimentary Hilton Honors™ Diamond Status.",
        ],
        "program": "Hilton Honors",
        "card_art": "static/images/category/hilton-honors-aspire.png",
        "benefit_images": {"2": "static/images/credit-cards/Hilton-AspireDiamond-Status_Desktop.webp"},
        "categories": ["hotel-rewards", "travel-rewards", "no-foreign-transaction-fee"],
        "featured": False,
    },
    {
        "slug": "marriott-bonvoy-bevy",
        "name": "Marriott Bonvoy Bevy® American Express® Card",
        "short_name": "Marriott Bonvoy Bevy",
        "product_type": "credit",
        "annual_fee_text": "$250",
        "annual_fee_value": 250,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "Earn 125,000 Marriott Bonvoy® Bonus Points Plus A $150 Statement Credit",
        "welcome_body": "after you use your new Card to make $5,000 in purchases within the first 6 months of Card Membership. Offer ends 09/30/26.",
        "offer_end": _date(2026, 9, 30),
        "rewards_summary": "Marriott Bonvoy Points",
        "benefits": [
            "Earn 6X points at hotels participating in Marriott Bonvoy®.",
            "Earn 4X points at restaurants worldwide & U.S. Supermarkets (up to $15K in combined purchases per calendar year), then 2X points.",
            "Earn 2X points on all other eligible purchases.",
        ],
        "program": "Marriott Bonvoy",
        "card_art": "static/images/category/marriott-bonvoy-bevy-card.png",
        "categories": ["hotel-rewards", "travel-rewards", "no-foreign-transaction-fee"],
        "featured": False,
    },
    {
        "slug": "marriott-bonvoy-brilliant",
        "name": "Marriott Bonvoy Brilliant® American Express® Card",
        "short_name": "Marriott Bonvoy Brilliant",
        "product_type": "credit",
        "annual_fee_text": "$650",
        "annual_fee_value": 650,
        "apr_text": "19.74% to 28.74% variable APR on purchases",
        "welcome_headline": "Earn 150,000 Marriott Bonvoy® Bonus Points Plus A $250 Statement Credit",
        "welcome_body": "after you use your new Card to make $6,000 in purchases within the first 6 months of Card Membership. Offer ends 09/30/26.",
        "offer_end": _date(2026, 9, 30),
        "rewards_summary": "Marriott Bonvoy Points",
        "benefits": [
            "Earn 6X points at hotels participating in Marriott Bonvoy®.",
            "Earn 3X points at restaurants worldwide & on flights booked directly with airlines.",
            "With the $300 Brilliant Dining Credit, get up to $25 per month each calendar year in statement credits for eligible purchases at restaurants worldwide.",
        ],
        "program": "Marriott Bonvoy",
        "card_art": "static/images/category/marriott-bonvoy-brilliant-card.png",
        "benefit_images": {"2": "static/images/credit-cards/RESYBrilliant_Desktop.webp"},
        "categories": ["hotel-rewards", "travel-rewards", "no-foreign-transaction-fee"],
        "featured": False,
    },
]

# ---------------------------------------------------------------------------
# Banking products — rates transcribed from the live banking pages (04/2026).
# ---------------------------------------------------------------------------

BANKING_PRODUCTS = [
    {
        "slug": "high-yield-savings",
        "name": "High Yield Savings Account",
        "short_name": "High Yield Savings (HYSA)",
        "category": "savings",
        "apy": 3.00,
        "apy_text": "3.00% APY",
        "national_average_apy": 0.38,
        "headline": "Grow your money with a High Yield Savings Account",
        "intro": "Earn more interest than your average savings account and enjoy the convenience you expect from American Express.",
        "features": [
            "Competitive APY — 6x higher than the national rate",
            "Earns Daily Interest — interest is compounded daily and credited to your account monthly",
            "No Monthly Fees — no fee to open, no minimum deposit, and no monthly fees",
            "24/7 Customer Support — bank confidently with world-class customer service",
        ],
        "image": "static/images/hysa/basic-desktop.jpg",
    },
    {
        "slug": "cd",
        "name": "Certificate of Deposit",
        "short_name": "Certificates of Deposit (CD)",
        "category": "savings",
        "apy": 4.25,
        "apy_text": "Up to 4.25% APY based on the term you select",
        "headline": "Watch your money grow with a Certificate of Deposit (CD)",
        "intro": "Choose your term — from months to years — to lock in your rate.",
        "features": [
            "Fixed Interest Rate & APY — know exactly how much you'll earn by locking in your rate",
            "No Monthly Fees — enjoy no minimum balance and no monthly fees",
            "Earns Daily Interest — interest is compounded daily and credited to your account monthly",
            "24/7 Customer Support — bank confidently with world-class customer service",
        ],
        "image": "static/images/CD/basic-cd-desktop.jpg",
    },
    {
        "slug": "checking",
        "name": "American Express Rewards Checking",
        "short_name": "Personal Checking",
        "category": "checking",
        "apy": 1.00,
        "apy_text": "1.00% APY — 10X higher than the national rate",
        "headline": "Enhance your Membership with Rewards Checking",
        "intro": "No fee to open. No monthly fees. No minimum balance requirement.",
        "features": [
            "High Yield — earn a 1.00% APY, 10X higher than the national rate",
            "Debit Card Rewards — earn Membership Rewards points on eligible Debit Card purchases",
            "No Monthly Fees — no fee to open, no minimum deposit, and no monthly fees",
            "Backed by Amex — 24/7 world-class customer service and fraud monitoring",
        ],
        "image": "static/images/consumer-checking/hero-image-desktop.jpg",
    },
    {
        "slug": "personal-loans",
        "name": "American Express® Personal Loans",
        "short_name": "Personal Loans",
        "category": "lending",
        "apy": None,
        "apy_text": "Fixed rates ranging from 6.99% to 19.99% APR (rates as of 04-15-26)",
        "headline": "Get the funds you need with American Express® Personal Loans",
        "intro": "From consolidating credit debt to home improvement, get the funds you need with loans starting at $3,500 available to eligible Card Members. Apply online and get a decision in seconds.",
        "features": [
            "Quick Application & Funding — apply and get a decision in seconds; funds sent in as fast as 1 day after you accept the loan",
            "Competitive Rates — fixed interest rates mean predictable payments",
            "No Hidden Fees — there are no origination fees or pre-payment penalties",
            "No Credit Score Impact to Apply — your credit score may be impacted if you are approved and accept the loan",
        ],
        "image": "static/images/personal-loans/Hero_Background_Desktop.png",
    },
]

# CD terms — from the live CD page's term table.
CD_TERMS = [
    (10, 4.25), (11, 3.50), (12, 3.50), (14, 3.50), (18, 3.25),
    (22, 4.00), (24, 3.25), (36, 2.25), (48, 2.25), (60, 3.00),
]

# ---------------------------------------------------------------------------
# Amex Offers — the three featured offers transcribed from the live
# /en-us/benefits/offers/ page plus offer mechanics copy.
# ---------------------------------------------------------------------------

AMEX_OFFERS = [
    {
        "merchant": "Tula Skincare",
        "domain": "tula.com",
        "headline": "Spend $75 or more, earn $15 back",
        "body": "Earn a one-time $15 statement credit after using your enrolled eligible Card to spend a minimum of $75 in one or more qualifying purchases online at tula.com by 10/1/2026. Offer availability may vary by Card Member. Enrollment is required.",
        "credit_value": 15.0,
        "expires": _date(2026, 10, 1),
    },
    {
        "merchant": "Stayaka",
        "domain": "stayaka.com",
        "headline": "Spend $750 or more, earn $150 back",
        "body": "Earn a one-time $150 statement credit after using your enrolled eligible Card to spend a minimum of $750 in one or more purchases on room rate and room-related charges at stayaka.com. Offer availability may vary by Card Member. Enrollment is required.",
        "credit_value": 150.0,
        "expires": _date(2026, 12, 31),
    },
    {
        "merchant": "The Bouqs Company",
        "domain": "bouqs.com/subscriptions",
        "headline": "Spend $40 or more, earn $20 back",
        "body": "Earn a one-time $20 statement credit after using your enrolled eligible Card to spend a minimum of $40 in one or more qualifying purchases of a Bouqs subscription online at bouqs.com/subscriptions by 10/15/2026. Offer availability may vary by Card Member. Enrollment is required.",
        "credit_value": 20.0,
        "expires": _date(2026, 10, 15),
    },
]

# ---------------------------------------------------------------------------
# Membership Rewards redemption options — from the live
# /en-us/benefits/rewards/membership-rewards/ page.
# ---------------------------------------------------------------------------

REDEMPTION_OPTIONS = [
    {
        "slug": "gift-cards",
        "name": "Redeem for Gift Cards",
        "description": "Redeem Membership Rewards points for retail, restaurant, entertainment, travel, and American Express Gift Cards.",
        "points_per_unit": 10000,
        "unit_label": "$100 Gift Card",
        "unit_value": 100.0,
    },
    {
        "slug": "statement-credit",
        "name": "Use Points for Statement Credit",
        "description": "Redeem with ease when you convert Membership Rewards points to a statement credit. Terms apply.",
        "points_per_unit": 20000,
        "unit_label": "$100 Statement Credit",
        "unit_value": 100.0,
    },
    {
        "slug": "deposit-checking",
        "name": "Deposit Into Checking",
        "description": "With an American Express Rewards Checking account, you can convert points to a deposit directly into your account. Deposit accounts offered by American Express National Bank. Member FDIC. Terms apply.",
        "points_per_unit": 20000,
        "unit_label": "$100 Deposit",
        "unit_value": 100.0,
    },
    {
        "slug": "pay-with-points-travel",
        "name": "Pay with Points for Travel",
        "description": "Use Pay with Points when booking flights, hotels, and cruises through American Express Travel. Terms apply.",
        "points_per_unit": 15000,
        "unit_label": "$100 Travel Credit",
        "unit_value": 100.0,
    },
]

# ---------------------------------------------------------------------------
# Benchmark users — shared credentials across the WebHarbor fleet.
# ---------------------------------------------------------------------------

BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display_name": "Alice Johnson"},
    {"username": "bob_c", "email": "bob.c@test.com", "display_name": "Bob Chen"},
    {"username": "carol_d", "email": "carol.d@test.com", "display_name": "Carol Davis"},
    {"username": "david_k", "email": "david.k@test.com", "display_name": "David Kim"},
]


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def seed_database(app_db):
    """Idempotent catalog seed. Returns early when cards already exist."""
    from app import (AmexOffer, BankingProduct, Card, CardCategory, CDTerm,
                     RedemptionOption)

    if Card.query.count() > 0:
        return

    categories = {}
    for slug, name, label, intro in CARD_CATEGORIES:
        cat = CardCategory(slug=slug, name=name, filter_label=label, intro=intro)
        app_db.session.add(cat)
        categories[slug] = cat
    app_db.session.flush()

    from app import card_category_links

    for data in CARDS:
        card = Card(
            slug=data["slug"], name=data["name"], short_name=data["short_name"],
            product_type=data["product_type"],
            annual_fee_text=data["annual_fee_text"],
            annual_fee_value=data["annual_fee_value"],
            apr_text=data["apr_text"],
            welcome_headline=data["welcome_headline"],
            welcome_body=data["welcome_body"],
            offer_end=data["offer_end"],
            rewards_summary=data["rewards_summary"],
            benefits_json=json.dumps(data["benefits"], ensure_ascii=False),
            benefit_images_json=json.dumps(data.get("benefit_images", {}), ensure_ascii=False),
            program=data["program"],
            card_art=data["card_art"],
            featured=data["featured"],
        )
        app_db.session.add(card)
        app_db.session.flush()
        # Insert junction rows in a fixed order: SQLAlchemy's relationship
        # flush order for secondary tables is not deterministic across runs,
        # and a byte-identical seed requires a stable row order here.
        for slug in data["categories"]:
            app_db.session.execute(
                card_category_links.insert().values(card_id=card.id, category_id=categories[slug].id)
            )

    for data in BANKING_PRODUCTS:
        product = BankingProduct(
            slug=data["slug"], name=data["name"], short_name=data["short_name"],
            category=data["category"], apy=data["apy"], apy_text=data["apy_text"],
            headline=data["headline"], intro=data["intro"],
            features_json=json.dumps(data["features"], ensure_ascii=False),
            image=data["image"],
        )
        app_db.session.add(product)

    for months, apy in CD_TERMS:
        app_db.session.add(CDTerm(term_months=months, apy=apy))

    for data in AMEX_OFFERS:
        app_db.session.add(AmexOffer(**data))

    for data in REDEMPTION_OPTIONS:
        app_db.session.add(RedemptionOption(**data))

    app_db.session.commit()


# ---------------------------------------------------------------------------
# Benchmark member data — deterministic, pinned to MIRROR_DATE.
# ---------------------------------------------------------------------------

# Per-user card holdings: (card_slug, last4, opened, credit_limit, points_balance)
USER_CARDS = {
    "alice_j": [
        ("platinum", "1009", _date(2022, 3, 15), 25000, 84250),
        ("blue-cash-everyday", "3007", _date(2023, 6, 1), 12000, 0),
    ],
    "bob_c": [
        ("gold-card", "2004", _date(2021, 11, 20), 15000, 62180),
        ("delta-skymiles-gold-american-express-card", "5016", _date(2024, 2, 10), 9000, 35400),
    ],
    "carol_d": [
        ("hilton-honors-surpass", "8023", _date(2023, 4, 5), 10000, 96800),
        ("marriott-bonvoy-brilliant", "9008", _date(2025, 1, 15), 15000, 52200),
    ],
    "david_k": [
        ("blue-cash-preferred", "4002", _date(2022, 8, 18), 14000, 0),
        ("delta-skymiles-platinum-american-express-card", "6001", _date(2025, 5, 2), 11000, 28650),
    ],
}

USER_PROFILES = {
    "alice_j": ("+1 (212) 555-0148", "350 Fifth Avenue, Apt 42B", "New York", "NY", "10118", "03/2016"),
    "bob_c": ("+1 (415) 555-0193", "2160 Market Street, Unit 5", "San Francisco", "CA", "94114", "11/2014"),
    "carol_d": ("+1 (312) 555-0126", "405 North Wabash Avenue", "Chicago", "IL", "60611", "07/2017"),
    "david_k": ("+1 (206) 555-0177", "1201 Third Avenue, Suite 900", "Seattle", "WA", "98101", "02/2019"),
}

# Bank accounts: (name, type, last4, default)
USER_BANK_ACCOUNTS = {
    "alice_j": [("Chase Total Checking", "Checking", "4589", True)],
    "bob_c": [("Bank of America Advantage Checking", "Checking", "7721", True),
              ("Ally Online Savings", "Savings", "2210", False)],
    "carol_d": [("Citi Everyday Checking", "Checking", "3302", True)],
    "david_k": [("Wells Fargo Everyday Checking", "Checking", "8845", True)],
}

# Transactions: (username, card_last4, date, merchant, category, amount, points_earned, description)
TX = [
    # --- alice / platinum 1009 (5X flights+hotels via Amex Travel, 1X other) ---
    ("alice_j", "1009", _date(2026, 6, 3), "The Polo Bar", "Restaurants", 168.40, 168, "Dinner"),
    ("alice_j", "1009", _date(2026, 6, 8), "American Express Travel — JFK to LHR", "Airline", 1842.00, 9210, "Flight booked through Amex Travel"),
    ("alice_j", "1009", _date(2026, 6, 12), "The Savoy (Amex Travel prepaid)", "Hotels", 1240.00, 6200, "Hotel booked through Amex Travel"),
    ("alice_j", "1009", _date(2026, 6, 18), "Whole Foods Market #221", "Groceries", 96.22, 96, "Weekly groceries"),
    ("alice_j", "1009", _date(2026, 6, 25), "Equinox Fitness", "Health & Wellness", 405.00, 405, "Monthly membership"),
    ("alice_j", "1009", _date(2026, 7, 2), "Le Bernardin", "Restaurants", 286.75, 286, "Anniversary dinner"),
    ("alice_j", "1009", _date(2026, 7, 9), "American Express Travel — LHR to JFK", "Airline", 1687.50, 8437, "Return flight"),
    ("alice_j", "1009", _date(2026, 7, 15), "Uber", "Travel", 43.20, 43, "Rideshare"),
    ("alice_j", "1009", _date(2026, 7, 21), "Bergdorf Goodman", "Shopping", 512.89, 512, "Summer wardrobe"),
    ("alice_j", "1009", _date(2026, 7, 28), "Blue Bottle Coffee", "Restaurants", 18.60, 18, "Coffee"),
    ("alice_j", "1009", _date(2026, 8, 2), "The Connaught (Amex Travel prepaid)", "Hotels", 2105.00, 10525, "London stay"),
    ("alice_j", "1009", _date(2026, 8, 9), "Delta Air Lines", "Airline", 492.10, 492, "Flight change fee"),
    ("alice_j", "1009", _date(2026, 8, 14), "Rei", "Shopping", 224.35, 224, "Hiking gear"),
    ("alice_j", "1009", _date(2026, 8, 20), "Compass Rose Restaurant", "Restaurants", 132.55, 132, "Dinner with colleagues"),
    ("alice_j", "1009", _date(2026, 8, 27), "Amazon.com", "Shopping", 87.42, 87, "Household items"),
    ("alice_j", "1009", _date(2026, 9, 3), "American Express Travel — JFK to CDG", "Airline", 2210.60, 11053, "Paris trip"),
    ("alice_j", "1009", _date(2026, 9, 8), "Le Meurice (Amex Travel prepaid)", "Hotels", 3420.00, 17100, "Paris hotel"),
    ("alice_j", "1009", _date(2026, 9, 12), "Louis Vuitton Paris", "Shopping", 1380.00, 1380, "Gift"),
    ("alice_j", "1009", _date(2026, 9, 17), "Cafe de Flore", "Restaurants", 74.30, 74, "Breakfast"),
    # --- alice / blue-cash-everyday 3007 (3% supermarkets/gas/online retail) ---
    ("alice_j", "3007", _date(2026, 6, 5), "Trader Joe's #451", "Groceries", 142.86, 0, "Weekly groceries"),
    ("alice_j", "3007", _date(2026, 6, 11), "Shell Station 8842", "Gas Stations", 58.40, 0, "Fuel"),
    ("alice_j", "3007", _date(2026, 6, 19), "Amazon.com", "Online Retail", 64.15, 0, "Kitchen supplies"),
    ("alice_j", "3007", _date(2026, 7, 6), "Trader Joe's #451", "Groceries", 131.22, 0, "Weekly groceries"),
    ("alice_j", "3007", _date(2026, 7, 14), "Costco Wholesale", "Groceries", 212.47, 0, "Bulk purchase"),
    ("alice_j", "3007", _date(2026, 7, 23), "BP Station 3391", "Gas Stations", 52.18, 0, "Fuel"),
    ("alice_j", "3007", _date(2026, 8, 4), "Trader Joe's #451", "Groceries", 149.94, 0, "Weekly groceries"),
    ("alice_j", "3007", _date(2026, 8, 16), "Amazon.com", "Online Retail", 88.73, 0, "Books"),
    ("alice_j", "3007", _date(2026, 8, 29), "Exxon Station 7710", "Gas Stations", 61.25, 0, "Fuel"),
    ("alice_j", "3007", _date(2026, 9, 6), "Whole Foods Market #221", "Groceries", 96.58, 0, "Weekly groceries"),
    ("alice_j", "3007", _date(2026, 9, 15), "Amazon.com", "Online Retail", 43.90, 0, "Pet supplies"),
    # --- bob / gold-card 2004 (4X restaurants/supermarkets up to caps, 1X other) ---
    ("bob_c", "2004", _date(2026, 6, 2), "Tartine Bakery", "Restaurants", 38.40, 153, "Breakfast"),
    ("bob_c", "2004", _date(2026, 6, 6), "Safeway #1288", "Groceries", 174.22, 696, "Weekly groceries"),
    ("bob_c", "2004", _date(2026, 6, 13), "Zuni Garden Restaurant", "Restaurants", 121.30, 485, "Dinner"),
    ("bob_c", "2004", _date(2026, 6, 20), "United Airlines", "Airline", 386.00, 386, "SFO to SEA"),
    ("bob_c", "2004", _date(2026, 6, 26), "Trader Joe's #918", "Groceries", 88.16, 352, "Weekly groceries"),
    ("bob_c", "2004", _date(2026, 7, 4), "State Bird Provisions", "Restaurants", 178.90, 715, "Dinner with family"),
    ("bob_c", "2004", _date(2026, 7, 11), "Safeway #1288", "Groceries", 205.44, 821, "Weekly groceries"),
    ("bob_c", "2004", _date(2026, 7, 18), "AMC Metreon 16", "Entertainment", 42.00, 42, "Movie tickets"),
    ("bob_c", "2004", _date(2026, 7, 25), "Blue Bottle Coffee", "Restaurants", 22.75, 91, "Coffee"),
    ("bob_c", "2004", _date(2026, 8, 1), "Swan Oyster Depot", "Restaurants", 145.60, 582, "Lunch"),
    ("bob_c", "2004", _date(2026, 8, 9), "Whole Foods Market #882", "Groceries", 132.07, 528, "Weekly groceries"),
    ("bob_c", "2004", _date(2026, 8, 17), "Alaska Airlines", "Airline", 312.40, 312, "SFO to PDX"),
    ("bob_c", "2004", _date(2026, 8, 24), "Rich Table", "Restaurants", 198.25, 793, "Dinner"),
    ("bob_c", "2004", _date(2026, 9, 2), "Safeway #1288", "Groceries", 168.90, 675, "Weekly groceries"),
    ("bob_c", "2004", _date(2026, 9, 10), "Napa Farmhouse Kitchen", "Restaurants", 156.75, 627, "Weekend lunch"),
    ("bob_c", "2004", _date(2026, 9, 18), "REI Co-op", "Shopping", 142.30, 142, "Camping gear"),
    # --- bob / delta-skymiles-gold 5016 (2X Delta/restaurants/supermarkets) ---
    ("bob_c", "5016", _date(2026, 6, 7), "Delta Air Lines", "Airline", 489.20, 978, "SFO to ATL"),
    ("bob_c", "5016", _date(2026, 6, 14), "Delta Sky Club", "Travel", 59.00, 59, "Lounge day pass guest"),
    ("bob_c", "5016", _date(2026, 7, 5), "Delta Air Lines", "Airline", 412.60, 825, "ATL to SFO"),
    ("bob_c", "5016", _date(2026, 7, 19), "Hartsfield–Jackson ATL Parking", "Travel", 36.00, 36, "Airport parking"),
    ("bob_c", "5016", _date(2026, 8, 8), "Delta Air Lines", "Airline", 538.90, 1077, "SFO to JFK"),
    ("bob_c", "5016", _date(2026, 8, 22), "Boiling Crab", "Restaurants", 84.50, 169, "Dinner"),
    ("bob_c", "5016", _date(2026, 9, 9), "Delta Air Lines", "Airline", 405.00, 810, "SFO to LAX"),
    # --- carol / hilton-surpass 8023 (12X Hilton, 6X gas/restaurants/supermarkets) ---
    ("carol_d", "8023", _date(2026, 6, 4), "Hilton Chicago O'Hare Airport", "Hotels", 289.00, 3468, "One-night stay"),
    ("carol_d", "8023", _date(2026, 6, 13), "Speedway 9021", "Gas Stations", 54.20, 325, "Fuel"),
    ("carol_d", "8023", _date(2026, 6, 21), "Jewel-Osco #307", "Groceries", 121.44, 728, "Weekly groceries"),
    ("carol_d", "8023", _date(2026, 7, 3), "Hilton Garden Inn Chicago", "Hotels", 246.00, 2952, "Staycation"),
    ("carol_d", "8023", _date(2026, 7, 17), "Giordano's", "Restaurants", 92.80, 556, "Deep dish pizza"),
    ("carol_d", "8023", _date(2026, 7, 26), "Mariano's #118", "Groceries", 143.62, 861, "Weekly groceries"),
    ("carol_d", "8023", _date(2026, 8, 5), "Hilton Paris Opera", "Hotels", 421.00, 5052, "Paris stay"),
    ("carol_d", "8023", _date(2026, 8, 19), "Shell Station 4477", "Gas Stations", 48.75, 292, "Fuel"),
    ("carol_d", "8023", _date(2026, 9, 7), "Hilton Chicago Downtown", "Hotels", 312.00, 3744, "Weekend stay"),
    ("carol_d", "8023", _date(2026, 9, 16), "Whole Foods Market #338", "Groceries", 98.30, 589, "Weekly groceries"),
    # --- carol / marriott-brilliant 9008 (6X Marriott, 3X restaurants/flights) ---
    ("carol_d", "9008", _date(2026, 6, 10), "Chicago Marriott Downtown Magnificent Mile", "Hotels", 358.00, 2148, "One-night stay"),
    ("carol_d", "9008", _date(2026, 6, 24), "Alinea", "Restaurants", 390.00, 1170, "Chef's table"),
    ("carol_d", "9008", _date(2026, 7, 8), "JW Marriott Chicago", "Hotels", 296.00, 1776, "Staycation"),
    ("carol_d", "9008", _date(2026, 7, 20), "American Airlines", "Airline", 342.60, 1027, "ORD to DFW"),
    ("carol_d", "9008", _date(2026, 8, 12), "The Marriott Chicago Medical District", "Hotels", 264.00, 1584, "Family visit"),
    ("carol_d", "9008", _date(2026, 8, 28), "Girl & the Goat", "Restaurants", 156.40, 469, "Dinner"),
    ("carol_d", "9008", _date(2026, 9, 5), "Renaissance Chicago North Shore", "Hotels", 244.00, 1464, "Weekend stay"),
    ("carol_d", "9008", _date(2026, 9, 14), "Resy — Monteverde Restaurant", "Restaurants", 118.90, 356, "Dinner via Resy"),
    # --- david / blue-cash-preferred 4002 (6% supermarkets/streaming, 3% transit) ---
    ("david_k", "4002", _date(2026, 6, 3), "QFC #812", "Groceries", 187.32, 0, "Weekly groceries"),
    ("david_k", "4002", _date(2026, 6, 9), "Netflix.com", "Streaming", 22.99, 0, "Monthly subscription"),
    ("david_k", "4002", _date(2026, 6, 17), "Sound Transit Link", "Transit", 12.50, 0, "Transit pass reload"),
    ("david_k", "4002", _date(2026, 6, 25), "Kroger #441", "Groceries", 224.18, 0, "Monthly stock-up"),
    ("david_k", "4002", _date(2026, 7, 7), "QFC #812", "Groceries", 165.44, 0, "Weekly groceries"),
    ("david_k", "4002", _date(2026, 7, 15), "Disney+ Bundle", "Streaming", 18.99, 0, "Monthly subscription"),
    ("david_k", "4002", _date(2026, 7, 24), "Uber", "Transit", 28.40, 0, "Rideshare"),
    ("david_k", "4002", _date(2026, 8, 6), "Kroger #441", "Groceries", 201.77, 0, "Weekly groceries"),
    ("david_k", "4002", _date(2026, 8, 13), "Hulu.com", "Streaming", 17.99, 0, "Monthly subscription"),
    ("david_k", "4002", _date(2026, 8, 25), "King County Metro", "Transit", 20.00, 0, "Transit pass reload"),
    ("david_k", "4002", _date(2026, 9, 4), "QFC #812", "Groceries", 176.53, 0, "Weekly groceries"),
    ("david_k", "4002", _date(2026, 9, 11), "Netflix.com", "Streaming", 24.99, 0, "Premium subscription"),
    # --- david / delta-platinum 6001 (First Bag Free, MQD Headstart) ---
    ("david_k", "6001", _date(2026, 6, 5), "Delta Air Lines", "Airline", 458.20, 916, "SEA to MSP"),
    ("david_k", "6001", _date(2026, 6, 27), "Delta Air Lines", "Airline", 512.80, 1025, "MSP to SEA"),
    ("david_k", "6001", _date(2026, 7, 12), "Delta Air Lines — Sky Priority", "Airline", 34.00, 68, "Seat upgrade"),
    ("david_k", "6001", _date(2026, 8, 3), "Delta Air Lines", "Airline", 489.60, 979, "SEA to ATL"),
    ("david_k", "6001", _date(2026, 8, 21), "Delta Air Lines", "Airline", 534.40, 1068, "ATL to SEA"),
    ("david_k", "6001", _date(2026, 9, 8), "Delta Air Lines", "Airline", 478.10, 956, "SEA to DTW"),
]

# Payments: (username, card_last4, date, amount, bank_index)
PAYMENTS = [
    ("alice_j", "1009", _date(2026, 7, 24), 6000.00, 0),
    ("alice_j", "1009", _date(2026, 8, 25), 4300.00, 0),
    ("alice_j", "3007", _date(2026, 8, 25), 512.00, 0),
    ("bob_c", "2004", _date(2026, 7, 23), 900.00, 0),
    ("bob_c", "2004", _date(2026, 8, 24), 780.00, 0),
    ("bob_c", "5016", _date(2026, 8, 24), 1450.00, 0),
    ("carol_d", "8023", _date(2026, 7, 22), 600.00, 0),
    ("carol_d", "9008", _date(2026, 8, 23), 900.00, 0),
    ("david_k", "4002", _date(2026, 7, 21), 480.00, 0),
    ("david_k", "4002", _date(2026, 8, 22), 510.00, 0),
    ("david_k", "6001", _date(2026, 8, 22), 980.00, 0),
]

# Offer enrollments: (username, offer_merchant, card_last4)
OFFER_ENROLLMENTS = [
    ("alice_j", "Tula Skincare", "1009"),
    ("david_k", "The Bouqs Company", "4002"),
]

# Reward activity beyond automatic earns: (username, card_last4, date, description, change)
REWARD_ACTIVITY_EXTRA = [
    ("alice_j", "1009", _date(2026, 7, 30), "Redeemed for a $100 Gift Card", -10000),
    ("bob_c", "2004", _date(2026, 8, 15), "Redeemed for a $100 Statement Credit", -20000),
    ("carol_d", "8023", _date(2026, 8, 30), "Transferred points to Hilton Honors program", -20000),
]


def seed_benchmark_data(app_db):
    """Idempotent member-data seed. Returns early when users already exist."""
    from app import (AmexOffer, BankAccount, Card, OfferEnrollment, Payment,
                     RewardActivity, Statement, Transaction, User, UserCard)

    if User.query.count() > 0:
        return

    users = {}
    for data in BENCHMARK_USERS:
        phone, addr, city, state, postal, since = USER_PROFILES[data["username"]]
        user = User(
            username=data["username"], email=data["email"],
            password_hash=TEST_PASSWORD_HASH,
            display_name=data["display_name"], phone=phone,
            address_line1=addr, city=city, state=state, postal_code=postal,
            member_since=since, created_at=_date(2026, 1, 1),
        )
        app_db.session.add(user)
        users[data["username"]] = user
    app_db.session.flush()

    cards_by_slug = {c.slug: c for c in Card.query.all()}
    user_cards = {}
    for username, holdings in USER_CARDS.items():
        for slug, last4, opened, limit, points in holdings:
            uc = UserCard(user_id=users[username].id, card_id=cards_by_slug[slug].id,
                          last4=last4, opened_date=opened, credit_limit=limit,
                          current_balance=0, points_balance=points)
            app_db.session.add(uc)
            user_cards[(username, last4)] = uc
    app_db.session.flush()

    # bank accounts
    bank_accounts = {}
    for username, accounts in USER_BANK_ACCOUNTS.items():
        for i, (name, acct_type, last4, is_default) in enumerate(accounts):
            bank = BankAccount(user_id=users[username].id, name=name,
                               account_type=acct_type, last4=last4, is_default=is_default)
            app_db.session.add(bank)
            bank_accounts[(username, i)] = bank
    app_db.session.flush()

    # transactions
    for username, last4, date, merchant, category, amount, points, desc in TX:
        app_db.session.add(Transaction(
            user_card_id=user_cards[(username, last4)].id, date=date,
            merchant=merchant, category=category, amount=amount,
            status="Posted", points_earned=points, description=desc,
        ))

    # payments
    for username, last4, date, amount, bank_index in PAYMENTS:
        bank = bank_accounts[(username, bank_index)]
        app_db.session.add(Payment(
            user_card_id=user_cards[(username, last4)].id, date=date,
            amount=amount, bank_account_id=bank.id, status="Processed",
            confirmation="P" + f"{date:%m%d}" + last4,
        ))

    # statements — Jun/Jul/Aug 2026 periods, computed from the transaction rows
    PERIODS = [(_date(2026, 6, 1), _date(2026, 6, 30), _date(2026, 7, 24)),
               (_date(2026, 7, 1), _date(2026, 7, 31), _date(2026, 8, 24)),
               (_date(2026, 8, 1), _date(2026, 8, 31), _date(2026, 9, 24))]
    for (username, last4), uc in user_cards.items():
        card_txns = [t for t in TX if t[0] == username and t[1] == last4]
        running = 0.0
        for idx, (start, end, due) in enumerate(PERIODS):
            period_total = round(sum(t[5] for t in card_txns if start <= t[2] <= end), 2)
            closing = round(running + period_total, 2)
            min_pay = round(max(35.0, closing * 0.05), 2)
            # Jun/Jul statements are paid (a payment landed after each); Aug is open.
            status = "Paid" if idx < 2 else "Due"
            app_db.session.add(Statement(
                user_card_id=uc.id, period_start=start, period_end=end,
                opening_balance=round(running, 2), closing_balance=closing,
                min_payment=min_pay, due_date=due, payment_status=status,
            ))
            running = closing
        # current balance: all posted spend minus payments
        total_spend = round(sum(t[5] for t in card_txns), 2)
        total_paid = round(sum(p[3] for p in PAYMENTS if p[0] == username and p[1] == last4), 2)
        uc.current_balance = round(max(0, total_spend - total_paid), 2)

    # reward activity ledger: automatic earns per month + redemption entries
    for (username, last4), uc in user_cards.items():
        card_txns = [t for t in TX if t[0] == username and t[1] == last4 and t[6] > 0]
        months = {(t[2].year, t[2].month) for t in card_txns}
        for (year, month) in sorted(months):
            earned = sum(t[6] for t in card_txns if (t[2].year, t[2].month) == (year, month))
            month_name = _date(year, month, 1).strftime("%B")
            app_db.session.add(RewardActivity(
                user_card_id=uc.id, date=_date(year, month, 28),
                description=f"Points earned on purchases — {month_name} {year}",
                points_change=earned,
            ))
    for username, last4, date, desc, change in REWARD_ACTIVITY_EXTRA:
        app_db.session.add(RewardActivity(
            user_card_id=user_cards[(username, last4)].id, date=date,
            description=desc, points_change=change,
        ))

    # offer enrollments
    offers_by_merchant = {o.merchant: o for o in AmexOffer.query.all()}
    for username, merchant, last4 in OFFER_ENROLLMENTS:
        app_db.session.add(OfferEnrollment(
            user_id=users[username].id, amex_offer_id=offers_by_merchant[merchant].id,
            user_card_id=user_cards[(username, last4)].id,
            added_date=_date(2026, 8, 12), status="Added to Card",
        ))

    app_db.session.commit()

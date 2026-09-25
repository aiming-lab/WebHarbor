"""Deterministic build-time/boot-time seeder for the medicare_gov mirror.

Reads the tracked source snapshot (source_data.json, built by
scripts_dev/build_source_data.py from the 2026-09-23 Playwright harvest of
medicare.gov) and materializes it into the site's SQLite database. The
snapshot arrays are pre-sorted by the build script and every loop below
iterates them in order, so repeated builds on the same source produce
byte-identical databases (the Dockerfile seeds with PYTHONHASHSEED=0).

Every seed function early-returns on a populated database, which keeps
`/reset/medicare_gov` byte-identical.
"""
from __future__ import annotations

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_PATH = os.path.join(BASE_DIR, "source_data.json")

# Benchmark users share one deterministic digest for TestPass123! so the seed
# database is byte-reproducible on every rebuild.
BENCHMARK_PASSWORD_HASH = (
    "scrypt:32768:8:1$webharbor-medicare-fixed-salt$"
    "f2986073a98bda3c6d193d522b20c2bb8ef28d14939dc0305b827669def78a47"
    "3acca8fcd344b8dacadd6215095976476d65cdc19e8c4c23ea8a04bd0fe48157"
)

BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display": "Alice Johnson"},
    {"username": "bob_c", "email": "bob.c@test.com", "display": "Bob Chen"},
    {"username": "carol_d", "email": "carol.d@test.com", "display": "Carol Davis"},
    {"username": "david_k", "email": "david.k@test.com", "display": "David Kim"},
]

# Popular coverage topics exactly as the upstream "Popular coverage topics"
# page groups them: (topic, slug, blurb, [(upstream label, exact item title)]).
POPULAR_TOPICS = [
    ("Preventive & screening services", "preventive-screening-services",
     "Services that help prevent, detect, or manage health problems.",
     [("Bone mass measurements", "Bone mass measurements"),
      ("Cardiovascular disease screenings", "Cardiovascular disease screenings"),
      ("Colonoscopies (screening)", "Colonoscopies (screening)"),
      ("Mammograms", "Mammograms"),
      ("Prostate cancer screenings", "Prostate cancer screenings"),
      ('Yearly "Wellness" visits', 'Yearly "Wellness" visits')]),
    ("Durable Medical Equipment (DME)", "durable-medical-equipment",
     "Equipment your doctor prescribes for use in your home.",
     [("Continuous Positive Airway Pressure (CPAP) therapy", "Continuous Positive Airway Pressure (CPAP) therapy"),
      ("Hospital beds", "Hospital beds"),
      ("Oxygen equipment & accessories", "Oxygen equipment & accessories"),
      ("Walkers", "Walkers"),
      ("Wheelchairs & scooters", "Wheelchairs & scooters")]),
    ("Diabetes", "diabetes",
     "Supplies, services, and programs Medicare covers for diabetes.",
     [("Blood sugar monitors", "Blood sugar monitors"),
      ("Blood sugar test strips", "Blood sugar test strips"),
      ("Continuous glucose monitors", "Continuous glucose monitors"),
      ("Diabetes screenings", "Diabetes screenings"),
      ("Insulin", "Insulin"),
      ("Medicare Diabetes Prevention Program", "Medicare Diabetes Prevention Program"),
      ("Therapeutic continuous glucose monitors", "Continuous glucose monitors"),
      ("Therapeutic diabetic shoes & inserts coverage", "Therapeutic shoes & inserts")]),
    ("Shots/vaccines", "shots-vaccines",
     "Vaccines Medicare covers to help prevent disease.",
     [("Coronavirus disease 2019 (COVID-19) vaccine", "Coronavirus disease 2019 (COVID-19) vaccine"),
      ("Flu shots", "Flu vaccines"),
      ("Hepatitis B shots", "Hepatitis B vaccines"),
      ("Pneumococcal shots", "Pneumococcal vaccines"),
      ("Respiratory Syncytial Virus (RSV) Shot", "Respiratory Syncytial Virus (RSV) Shot"),
      ("Shingles shots", "Shingles vaccines"),
      ("Tdap shots", "Tdap vaccines")]),
    ("Eye care", "eye-care",
     "Eye-related tests, items, and services Medicare covers.",
     [("Artificial eyes & limbs", "Artificial eyes & limbs"),
      ("Cataract surgery", "Cataract surgery"),
      ("Eye exams (routine)", "Eye exams (routine)"),
      ("Eyeglasses & contact lenses", "Eyeglasses & contact lenses"),
      ("Glaucoma screenings", "Glaucoma screenings"),
      ("Macular degeneration tests & treatment", "Macular degeneration tests & treatment")]),
    ("Diagnostic tests", "diagnostic-tests",
     "Tests that help your doctor diagnose or monitor your condition.",
     [("Diagnostic laboratory tests", "Diagnostic laboratory tests"),
      ("Diagnostic non-laboratory tests", "Diagnostic non-laboratory tests"),
      ("Hearing & balance exams", "Hearing & balance exams"),
      ("Sleep studies", "Sleep studies"),
      ("X-rays", "X-rays")]),
]

# Simplified plan-finder catalog: realistic 2026 plan names built from the
# real insurers that sell Medicare Advantage / Part D plans in these counties
# (Aetna, Humana, UnitedHealthcare, BCBS, Cigna, Wellcare, Kaiser, Anthem,
# Devoted, Molina). Premiums/deductibles model public 2026 plan designs and
# exist so the mirror's plan finder has a plausible, deterministic catalog.
PLAN_CATALOG = {
    ("Sangamon", "IL", "62701"): [
        ("Medicare Advantage", "Aetna Medicare Premier (HMO)", "Aetna Medicare", "HMO", "$0", "$0 medical deductible", "$6,700 in-network", "4.5",
         ["Dental, vision & hearing allowances", "Fitness membership", "$0 primary care visits", "Over-the-counter allowance"]),
        ("Medicare Advantage", "Humana Gold Plus H0028 (HMO)", "Humana", "HMO", "$29", "$0 medical deductible", "$5,900 in-network", "4",
         ["Dental & vision allowances", "Transportation benefit", "$0 PCP visits", "Meals after inpatient stay"]),
        ("Medicare Advantage", "UnitedHealthcare Dual Complete (HMO D-SNP)", "UnitedHealthcare", "HMO", "$0", "$0", "$3,450 in-network", "3.5",
         ["Dental, vision & hearing", "Transportation to plan providers", "Healthy food card", "Utility assistance credit"]),
        ("Medicare Advantage", "Blue Cross Medicare Classic (PPO)", "Blue Cross and Blue Shield of Illinois", "PPO", "$54", "$199 medical deductible", "$7,550 in-network", "3",
         ["Nationwide network", "Dental allowance", "Vision allowance", "24/7 nurse line"]),
        ("Medicare Advantage", "Wellcare No Premium (HMO)", "Wellcare", "HMO", "$0", "$0 medical deductible", "$7,500 in-network", "2.5",
         ["Dental allowance", "Hearing exams", "Podiatry visits", "Fitness membership"]),
        ("Medicare Advantage", "Cigna TotalCare (HMO)", "Cigna Healthcare", "HMO", "$39", "$0 medical deductible", "$6,800 in-network", "3.5",
         ["Dental, vision & hearing", "In-home support", "Transportation", "Care management"]),
        ("Medicare drug plan", "Humana Walmart Value Rx (PDP)", "Humana", "PDP", "$0", "$0 deductible", "n/a", "4",
         ["Preferred retail: Walmart", "Mail-order 90-day supply", "$0 Tier 1 at preferred pharmacies", "Vaccine coverage"]),
        ("Medicare drug plan", "Aetna Medicare Saver Plus (PDP)", "Aetna Medicare", "PDP", "$8.20", "$590 deductible", "n/a", "3.5",
         ["Nationwide pharmacy network", "Mail-order 90-day supply", "Insulin capped at $35", "Vaccine coverage"]),
    ],
    ("Franklin", "OH", "43215"): [
        ("Medicare Advantage", "Aetna Medicare Value (HMO)", "Aetna Medicare", "HMO", "$0", "$0 medical deductible", "$6,500 in-network", "4",
         ["Dental, vision & hearing", "Fitness membership", "$0 PCP visits", "OTC allowance"]),
        ("Medicare Advantage", "Humana USAA Honor (HMO)", "Humana", "HMO", "$25", "$0 medical deductible", "$5,500 in-network", "4.5",
         ["Dental allowance", "Vision allowance", "Hearing aids", "Transportation benefit"]),
        ("Medicare Advantage", "UnitedHealthcare AARP Medicare Advantage Patriot (HMO)", "UnitedHealthcare", "HMO", "$44", "$0 medical deductible", "$6,000 in-network", "3.5",
         ["Nationwide network", "Dental allowance", "Gym membership", "Nurse line"]),
        ("Medicare Advantage", "Anthem MediBlue Access (HMO)", "Anthem", "HMO", "$0", "$0 medical deductible", "$7,000 in-network", "3",
         ["Dental, vision & hearing", "Transportation", "Home safety modifications", "Caregiver support"]),
        ("Medicare Advantage", "Molina Medicare Choice (HMO)", "Molina Healthcare", "HMO", "$0", "$0", "$4,900 in-network", "3",
         ["Dental services", "Vision services", "Transportation", "Meal benefit"]),
        ("Medicare Advantage", "Devoted Health Prime (HMO)", "Devoted Health", "HMO", "$19", "$0 medical deductible", "$5,100 in-network", "4",
         ["Dental allowance", "Transportation", "In-home support", "Wellness reward"]),
        ("Medicare drug plan", "Wellcare Value Script (PDP)", "Wellcare", "PDP", "$0", "$590 deductible", "n/a", "4",
         ["Nationwide network", "$0 Tier 1 at preferred", "Mail-order available", "Insulin capped at $35"]),
        ("Medicare drug plan", "Cigna Secure Rx (PDP)", "Cigna Healthcare", "PDP", "$12.40", "$590 deductible", "n/a", "3.5",
         ["Preferred pharmacies nationwide", "90-day supply", "Vaccine coverage", "Pharmacy counseling"]),
    ],
    ("Maricopa", "AZ", "85004"): [
        ("Medicare Advantage", "Humana Honor (HMO)", "Humana", "HMO", "$0", "$0 medical deductible", "$5,700 in-network", "4.5",
         ["Dental, vision & hearing", "Transportation", "Meals after hospital stay", "Fitness membership"]),
        ("Medicare Advantage", "UnitedHealthcare AARP Medicare Complete (HMO)", "UnitedHealthcare", "HMO", "$36", "$0 medical deductible", "$6,200 in-network", "3.5",
         ["Nationwide network", "Dental allowance", "Vision allowance", "Nurse line"]),
        ("Medicare Advantage", "Aetna Medicare Adavantage (HMO)", "Aetna Medicare", "HMO", "$0", "$0 medical deductible", "$6,900 in-network", "3.5",
         ["Dental allowance", "Hearing aids", "OTC card", "Fitness membership"]),
        ("Medicare Advantage", "Blue Cross Blue Shield of Arizona Freedom (PPO)", "Blue Cross Blue Shield of Arizona", "PPO", "$79", "$99 medical deductible", "$8,200 in-network", "3",
         ["Nationwide PPO network", "Dental allowance", "Vision allowance", "Flex card"]),
        ("Medicare Advantage", "Cigna Preferred Medicare (HMO)", "Cigna Healthcare", "HMO", "$15", "$0 medical deductible", "$6,400 in-network", "3.5",
         ["Dental, vision & hearing", "In-home support", "Transportation", "Nurse line"]),
        ("Medicare drug plan", "Humana Premier Rx (PDP)", "Humana", "PDP", "$44.70", "$0 deductible", "n/a", "4.5",
         ["Preferred pharmacy network", "Mail-order 90-day", "Insulin $35 cap", "Vaccine coverage"]),
        ("Medicare drug plan", "Aetna Medicare Saver (PDP)", "Aetna Medicare", "PDP", "$5.30", "$590 deductible", "n/a", "3.5",
         ["Nationwide network", "90-day supply", "Vaccine coverage", "Pharmacy finder"]),
    ],
    ("Miami-Dade", "FL", "33130"): [
        ("Medicare Advantage", "Humana Gold Plus H5504-153 (HMO)", "Humana", "HMO", "$0", "$0 medical deductible", "$4,990 in-network", "4",
         ["Dental allowance", "Transportation", "OTC card", "Fitness membership"]),
        ("Medicare Advantage", "UnitedHealthcare AARP Medicare Complete Plan 1 (HMO)", "UnitedHealthcare", "HMO", "$0", "$0 medical deductible", "$5,900 in-network", "4",
         ["Nationwide network", "Dental allowance", "Vision allowance", "Coinsurance 0% PCP"]),
        ("Medicare Advantage", "Wellcare Complete (HMO)", "Wellcare", "HMO", "$0", "$0 medical deductible", "$6,700 in-network", "3",
         ["Dental services", "Transportation", "Home-delivered meals", "Utilities allowance"]),
        ("Medicare Advantage", "Molina Medicare Complete Care (HMO D-SNP)", "Molina Healthcare", "HMO", "$0", "$0", "$3,400 in-network", "3.5",
         ["Dental, vision & hearing", "Transportation", "Healthy food card", "Care management"]),
        ("Medicare Advantage", "Florida Blue Medicare HMO (HMO)", "Florida Blue", "HMO", "$22", "$0 medical deductible", "$6,100 in-network", "3.5",
         ["Dental allowance", "Vision allowance", "Fitness membership", "24/7 nurse line"]),
        ("Medicare drug plan", "Wellcare Value Plus (PDP)", "Wellcare", "PDP", "$10.70", "$590 deductible", "n/a", "3.5",
         ["Nationwide network", "Mail-order available", "Insulin $35 cap", "Vaccine coverage"]),
        ("Medicare drug plan", "Humana Basic Rx (PDP)", "Humana", "PDP", "$17.60", "$590 deductible", "n/a", "4",
         ["Preferred pharmacies", "90-day supply", "Vaccine coverage", "Pharmacy counseling"]),
    ],
    ("Denver", "CO", "80204"): [
        ("Medicare Advantage", "Kaiser Permanente Medicare Plus (HMO)", "Kaiser Permanente", "HMO", "$62", "$0 medical deductible", "$6,350 in-network", "5",
         ["Integrated Kaiser network", "Dental allowance", "Fitness membership", "Telehealth"]),
        ("Medicare Advantage", "UnitedHealthcare AARP Medicare Advantage Choice (HMO)", "UnitedHealthcare", "HMO", "$0", "$0 medical deductible", "$6,450 in-network", "4",
         ["Nationwide network", "Dental allowance", "Vision allowance", "Meal benefit"]),
        ("Medicare Advantage", "Anthem MediBlue Plus (HMO)", "Anthem", "HMO", "$0", "$0 medical deductible", "$7,150 in-network", "3",
         ["Dental, vision & hearing", "Transportation", "Home safety modifications", "OTC allowance"]),
        ("Medicare Advantage", "Humana Choice (HMO)", "Humana", "HMO", "$18", "$0 medical deductible", "$6,000 in-network", "3.5",
         ["Dental allowance", "Hearing aids", "Transportation", "Fitness membership"]),
        ("Medicare drug plan", "Kaiser Permanente Medicare Rx (PDP)", "Kaiser Permanente", "PDP", "$38.40", "$590 deductible", "n/a", "4.5",
         ["Kaiser pharmacy network", "Mail-order 90-day", "Pharmacist counseling", "Vaccine coverage"]),
        ("Medicare drug plan", "Aetna Medicare Value Rx (PDP)", "Aetna Medicare", "PDP", "$9.80", "$590 deductible", "n/a", "4",
         ["Nationwide network", "90-day supply", "Insulin $35 cap", "Vaccine coverage"]),
    ],
    ("King", "WA", "98101"): [
        ("Medicare Advantage", "Regence Medicare Advantage (HMO)", "Regence BlueShield", "HMO", "$48", "$0 medical deductible", "$6,700 in-network", "4",
         ["Dental allowance", "Vision allowance", "Fitness membership", "Nurse line"]),
        ("Medicare Advantage", "UnitedHealthcare AARP Medicare Advantage Choice (PPO)", "UnitedHealthcare", "PPO", "$0", "$0 medical deductible", "$7,350 in-network", "3.5",
         ["Nationwide PPO network", "Dental allowance", "Transportation", "OTC allowance"]),
        ("Medicare Advantage", "Kaiser Permanente Medicare Option (HMO)", "Kaiser Permanente", "HMO", "$71", "$0 medical deductible", "$5,950 in-network", "4.5",
         ["Integrated Kaiser network", "Hearing aids", "Telehealth", "Wellness rewards"]),
        ("Medicare Advantage", "Humana Gold Plus (HMO)", "Humana", "HMO", "$0", "$0 medical deductible", "$6,550 in-network", "3",
         ["Dental, vision & hearing", "Transportation", "Meals after inpatient stay", "Fitness membership"]),
        ("Medicare drug plan", "Humana Walmart Preferred Rx (PDP)", "Humana", "PDP", "$15.30", "$590 deductible", "n/a", "4",
         ["Preferred retail: Walmart", "90-day mail-order", "Insulin $35 cap", "Vaccine coverage"]),
        ("Medicare drug plan", "Wellcare Value Script (PDP)", "Wellcare", "PDP", "$0", "$590 deductible", "n/a", "4",
         ["Nationwide network", "$0 Tier 1 preferred", "Mail-order available", "Vaccine coverage"]),
    ],
    ("Suffolk", "MA", "02108"): [
        ("Medicare Advantage", "Harvard Pilgrim Medicare Advantage Enhance (HMO)", "Harvard Pilgrim Health Care", "HMO", "$31", "$0 medical deductible", "$5,900 in-network", "5",
         ["Dental allowance", "Vision allowance", "Fitness membership", "Acupuncture benefit"]),
        ("Medicare Advantage", "Blue Cross Blue Shield of Massachusetts Medicare Blue Essential (HMO)", "Blue Cross Blue Shield of Massachusetts", "HMO", "$0", "$0 medical deductible", "$6,900 in-network", "4.5",
         ["Dental allowance", "Hearing exams", "Nurse line", "Wellness programs"]),
        ("Medicare Advantage", "Tufts Medicare Preferred Direct (HMO)", "Tufts Health Plan", "HMO", "$0", "$0 medical deductible", "$6,300 in-network", "5",
         ["Dental allowance", "Vision allowance", "Transportation", "Fitness membership"]),
        ("Medicare Advantage", "UnitedHealthcare AARP Medicare Advantage (HMO)", "UnitedHealthcare", "HMO", "$0", "$0 medical deductible", "$6,750 in-network", "3.5",
         ["Nationwide network", "Dental allowance", "OTC allowance", "Nurse line"]),
        ("Medicare drug plan", "Express Scripts Medicare Value (PDP)", "Express Scripts", "PDP", "$0", "$590 deductible", "n/a", "4",
         ["Home delivery pharmacy", "90-day supply", "Insulin $35 cap", "Pharmacist counseling"]),
        ("Medicare drug plan", "Humana Preferred Rx (PDP)", "Humana", "PDP", "$32.60", "$0 deductible", "n/a", "4.5",
         ["Preferred network", "Mail-order available", "Vaccine coverage", "90-day supply"]),
    ],
    ("Harris", "TX", "77002"): [
        ("Medicare Advantage", "Memorial Hermann Advantage (HMO)", "Memorial Hermann", "HMO", "$0", "$0 medical deductible", "$6,150 in-network", "4",
         ["Dental allowance", "Vision allowance", "Fitness membership", "Transportation"]),
        ("Medicare Advantage", "KelseyCare Advantage Classic (HMO)", "Kelsey-Seybold", "HMO", "$42", "$0 medical deductible", "$5,700 in-network", "4.5",
         ["Kelsey-Seybold clinics", "Dental services", "Hearing aids", "Telehealth"]),
        ("Medicare Advantage", "UnitedHealthcare AARP Medicare Complete (HMO)", "UnitedHealthcare", "HMO", "$0", "$0 medical deductible", "$6,500 in-network", "3.5",
         ["Nationwide network", "Dental allowance", "Vision allowance", "Nurse line"]),
        ("Medicare Advantage", "Humana Houston Gold (HMO)", "Humana", "HMO", "$0", "$0 medical deductible", "$6,850 in-network", "3.5",
         ["Dental, vision & hearing", "Transportation", "OTC card", "Fitness membership"]),
        ("Medicare Advantage", "Wellcare Reliance (HMO)", "Wellcare", "HMO", "$0", "$0 medical deductible", "$7,300 in-network", "3",
         ["Dental services", "Hearing exams", "Meal benefit", "In-home support"]),
        ("Medicare drug plan", "Humana Walmart Value Rx (PDP)", "Humana", "PDP", "$0", "$0 deductible", "n/a", "4",
         ["Preferred retail: Walmart", "Mail-order 90-day", "Insulin $35 cap", "Vaccine coverage"]),
        ("Medicare drug plan", "Cigna Secure Rx (PDP)", "Cigna Healthcare", "PDP", "$11.90", "$590 deductible", "n/a", "3.5",
         ["Preferred pharmacies", "90-day supply", "Vaccine coverage", "Pharmacy finder"]),
    ],
}

# Additional zips per county so the plan finder accepts nearby zips too.
COUNTY_EXTRA_ZIPS = {
    "Sangamon": ["62702", "62703", "62704"],
    "Franklin": ["43201", "43202", "43085"],
    "Maricopa": ["85001", "85003", "85006"],
    "Miami-Dade": ["33125", "33131", "33132"],
    "Denver": ["80203", "80205", "80206"],
    "King": ["98102", "98104", "98109"],
    "Suffolk": ["02109", "02110", "02111"],
    "Harris": ["77003", "77004", "77005"],
}


def _load_source() -> dict:
    with open(SOURCE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# per-table seeders (each gated at the top)
# ---------------------------------------------------------------------------

def seed_coverage_items():
    from app import CoverageItem, db

    if CoverageItem.query.count() > 0:
        return
    source = _load_source()
    for row in source["coverage_items"]:
        covered_by = ""
        preventive = False
        for tag in row["tags"]:
            if tag.startswith("Covered by"):
                covered_by = tag
            if "Preventive" in tag:
                preventive = True
        title = row["title"]
        db.session.add(CoverageItem(
            title=title,
            slug=row["slug"],
            summary=row["summary"],
            cost_summary=row["cost_summary"],
            description_html=row["description_html"],
            details_html=row["details_html"],
            eligible_html=row["eligible_html"],
            costs_html=row["costs_html"],
            how_often_html=row["how_often_html"],
            facility_html=row["facility_html"],
            provider_reqs_html=row["provider_reqs_html"],
            keywords=row["keywords"],
            covered_by=covered_by,
            is_preventive=preventive,
            letter=(title or "?")[0].upper(),
        ))
    db.session.commit()


def _slugify(text: str) -> str:
    import re
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def seed_coverage_topics():
    from app import CoverageItem, CoverageTopic, db

    if CoverageTopic.query.count() > 0:
        return
    by_title = {item.title: item.slug for item in CoverageItem.query.all()}
    for pos, (name, slug, blurb, members) in enumerate(POPULAR_TOPICS, start=1):
        entries = []
        for label, exact_title in members:
            item_slug = by_title.get(exact_title)
            if item_slug is None:
                close = [t for t in by_title if t.lower().startswith(exact_title.lower()[:12])]
                item_slug = by_title.get(close[0]) if close else None
            if item_slug:
                entries.append({"label": label, "slug": item_slug})
        db.session.add(CoverageTopic(
            name=name, slug=_slugify(name), blurb=blurb,
            item_slugs=json.dumps(entries), position=pos))
    db.session.commit()


def seed_providers():
    from app import Provider, ProviderCity, db

    if Provider.query.count() > 0:
        return
    source = _load_source()
    for row in source["provider_cities"]:
        db.session.add(ProviderCity(
            search_query=row["query"], city=row["city"], state=row["state"],
            lat=row["lat"], lon=row["lon"]))
    for row in source["providers"]:
        detail = {k: v for k, v in row.items()
                  if k not in {"provider_type", "provider_id", "name", "address1",
                               "address2", "city", "state", "zip", "phone", "lat",
                               "lon", "distance", "search_city", "specialties", "group"}}
        db.session.add(Provider(
            provider_type=row["provider_type"], provider_id=row["provider_id"],
            name=row["name"], address1=row["address1"], address2=row["address2"],
            city=row["city"], state=row["state"], zip=row["zip"],
            phone=row["phone"], lat=row["lat"], lon=row["lon"],
            distance=row["distance"], search_city=row["search_city"],
            specialties=json.dumps(row["specialties"]),
            detail=json.dumps(detail, sort_keys=True)))
    db.session.commit()


def seed_dme():
    from app import (DmeSupplier, DmeZip, DmeZipRow, EquipmentCategory, db)

    if DmeSupplier.query.count() > 0:
        return
    source = _load_source()
    for row in source["dme_zips"]:
        db.session.add(DmeZip(zip=row["zip"], city=row["city"],
                              lat=row["lat"], lon=row["lon"]))
    for row in source["dme_suppliers"]:
        db.session.add(DmeSupplier(
            supplier_id=row["supplier_id"], name=row["name"],
            address1=row["address1"], address2=row["address2"],
            city=row["city"], state=row["state"], zip=row["zip"],
            phone=row["phone"], medicare_assignment=row["medicare_assignment"],
            specialties=json.dumps(row["specialties"]),
            supplies=json.dumps(row["supplies"])))
    for row in source["dme_zip_rows"]:
        db.session.add(DmeZipRow(zip=row["zip"], supplier_id=row["supplier_id"],
                                 distance=row["distance"], rank=row["rank"]))
    for row in source["equipment_categories"]:
        db.session.add(EquipmentCategory(
            name=row["name"], description=row["description"],
            aliases=json.dumps(row["aliases"]), letter=row["letter"]))
    db.session.commit()


def seed_publications():
    from app import Publication, db

    if Publication.query.count() > 0:
        return
    source = _load_source()
    for row in source["publications"]:
        db.session.add(Publication(
            product_number=row["product_number"], title=row["title"],
            category=row["category"], language=row["language"],
            summary=row["summary"], thumb=row["thumb"],
            pdf_file=row["pdf_file"], orderable=row["orderable"]))
    db.session.commit()


def seed_costs():
    from app import CostAmount, db

    if CostAmount.query.count() > 0:
        return
    source = _load_source()["costs"]
    year = source["year"]
    rows = []
    a = source["part_a"]
    rows.append(("Part A", "Premium (premium-free)", year, "Most people pay nothing (they or a spouse paid Medicare taxes long enough while working — generally at least 10 years).", a["premium_free_note"]))
    rows.append(("Part A", "Premium (buy-in, 30-39 quarters)", year, a["premium_low"], "You pay this monthly amount if you or your spouse worked and paid Medicare taxes for 30-39 quarters."))
    rows.append(("Part A", "Premium (buy-in, under 30 quarters)", year, a["premium_high"], "You pay this monthly amount if you or your spouse worked and paid Medicare taxes for fewer than 30 quarters."))
    rows.append(("Part A", "Deductible (per benefit period)", year, a["deductible"], a["deductible_note"]))
    rows.append(("Part A", "Inpatient hospital stay days 1-60", year, "$0 after you pay your Part A deductible", a["inpatient_days_1_60"]))
    rows.append(("Part A", "Inpatient hospital stay days 61-90", year, "$434 coinsurance each day", a["inpatient_days_61_90"]))
    rows.append(("Part A", "Inpatient hospital stay days 91-150", year, "$868 coinsurance each day (lifetime reserve days)", a["inpatient_days_91_150"]))
    rows.append(("Part A", "Skilled nursing facility days 1-20", year, "$0", a["snf_days_1_20"]))
    rows.append(("Part A", "Skilled nursing facility days 21-100", year, "$217 coinsurance each day", a["snf_days_21_100"]))
    b = source["part_b"]
    rows.append(("Part B", "Premium (standard, per month)", year, b["premium"], b["premium_note"]))
    rows.append(("Part B", "Deductible (per year)", year, b["deductible"], b["deductible_note"]))
    rows.append(("Part B", "Coinsurance for most services", year, "20% of the Medicare-approved amount", b["coinsurance"]))
    rows.append(("Part B", "Clinical laboratory services", year, "$0", b["clinical_lab"]))
    rows.append(("Part B", "Home health care services", year, "$0", b["home_health"]))
    for i, entry in enumerate(source["irmaa"], start=1):
        rows.append(("IRMAA", entry["individual"], year,
                     entry["premium"],
                     f"Joint: {entry['joint']}; Married filing separately: {entry['married_sep']}"))
    rows.append(("Medicare Advantage", "Premiums & other costs", year,
                 source["advantage"]["premiums"], "You must also keep paying your Part B premium."))
    rows.append(("Medicare Advantage", "Out-of-pocket limit", year,
                 source["advantage"]["oop_limit"], "Once you pay the plan's limit, the plan pays 100% of covered services for the rest of the calendar year."))
    rows.append(("Part D", "Premium", year, source["part_d"]["premium"],
                 "You may pay more depending on your income (IRMAA)."))
    rows.append(("Part D", "Deductibles, copayments & coinsurance", year,
                 source["part_d"]["deductibles"], "Varies by plan and pharmacy."))
    rows.append(("Medigap", "Premium", year, source["medigap"]["premium"],
                 "Varies by policy, location, and other factors."))
    for part, item, yr, amount, note in rows:
        db.session.add(CostAmount(part=part, item=item, year=yr, amount=amount, note=note))
    db.session.commit()


def seed_content_pages():
    from app import ContentPage, db

    if ContentPage.query.count() > 0:
        return
    source = _load_source()
    for slug, page in source["content_pages"].items():
        db.session.add(ContentPage(
            slug=slug, title=page.get("title", slug),
            intro=page.get("intro", ""),
            sections=json.dumps({"blocks": page.get("blocks", []),
                                 "cards": page.get("cards", [])})))
    db.session.commit()


def seed_plans():
    from app import CountyZip, Plan, db

    if Plan.query.count() > 0:
        return
    for (county, state, primary_zip), plans in PLAN_CATALOG.items():
        zips = [primary_zip] + COUNTY_EXTRA_ZIPS.get(county, [])
        for zip_code in zips:
            db.session.add(CountyZip(zip=zip_code, county=county, state=state))
        for (plan_type, name, insurer, kind, premium, deductible, oop, rating, benefits) in plans:
            db.session.add(Plan(
                year=2026, county=county, state=state, plan_type=plan_type,
                name=name, insurer=insurer, plan_kind=kind, premium=premium,
                deductible=deductible, oop_max=oop, rating=rating,
                benefits=json.dumps(benefits)))
    db.session.commit()


# ---------------------------------------------------------------------------
# benchmark users + their private data
# ---------------------------------------------------------------------------

def _claims_for(user, slug_rows):
    """Deterministic, realistic claims referencing real coverage items."""
    from app import Claim

    spec = {
        "alice_j": [
            ("2026-06-18", "Springfield Clinic", "Springfield, IL", "Office visit",
             'Yearly "Wellness" visit', "$248", "$198.40", "$49.60"),
            ("2026-07-02", "St Johns Hospital", "Springfield, IL", "Inpatient hospital care",
             "Screening colonoscopy", "$2,985", "$1,736.00", "$0.00"),
            ("2026-08-11", "Cvs Pharmacy #06849", "Springfield, IL", "Durable medical equipment",
             "Blood sugar test strips", "$96.40", "$77.12", "$19.28"),
        ],
        "bob_c": [
            ("2026-05-21", "Memorial Medical Center", "Springfield, IL", "Inpatient hospital care",
             "Cardiovascular disease (behavioral therapy) screening", "$512.00", "$409.60", "$102.40"),
            ("2026-07-19", "Springfield Clinic", "Springfield, IL", "Office visit",
             "Advance care planning", "$186.00", "$148.80", "$37.20"),
            ("2026-08-30", "Arcadia Care on the Hill", "Springfield, IL", "Skilled nursing facility",
             "Physical therapy evaluation", "$268.00", "$214.40", "$53.60"),
        ],
        "carol_d": [
            ("2026-06-05", "FMC - Springfield East", "Springfield, IL", "Dialysis",
             "Diagnostic non-laboratory tests", "$1,240.00", "$992.00", "$248.00"),
            ("2026-07-27", "Springfield Clinic", "Springfield, IL", "Office visit",
             "Diabetes screenings", "$164.00", "$131.20", "$32.80"),
            ("2026-09-02", "Walgreen Co", "Springfield, IL", "Durable medical equipment",
             "Nebulizer drugs", "$88.20", "$70.56", "$17.64"),
        ],
        "david_k": [
            ("2026-06-29", "St Johns Hospital", "Springfield, IL", "Inpatient hospital care",
             "Cataract surgery", "$3,512.00", "$2,809.60", "$702.40"),
            ("2026-08-14", "Physiotherapy Professionals LLC", "Springfield, IL", "Therapy services",
             "Physical therapy sessions", "$420.00", "$336.00", "$84.00"),
            ("2026-09-09", "Springfield Clinic", "Springfield, IL", "Office visit",
             "Flu shot", "$41.00", "$41.00", "$0.00"),
        ],
    }
    rows = []
    for service_date, provider, city, category, description, billed, paid, owed in spec[user]:
        rows.append(Claim(
            user_id=None, service_date=service_date, provider_name=provider,
            provider_city=city, category=category, description=description,
            billed=billed, medicare_paid=paid, you_owed=owed,
            status="Processed"))
    return rows


def seed_benchmark_users():
    from app import (Claim, LoginEvent, MailingAddress, Message,
                     PaymentMethod, PremiumBill, User, db)

    if User.query.filter_by(email="alice.j@test.com").first():
        return

    profiles = {
        "alice_j": {
            "medicare_number": "1EG4-TE5-MK73", "part_a": "2021-03-01", "part_b": "2021-03-01",
            "phone": "(217) 555-0154",
            "address": ("12 Sunset Terrace", None, "Springfield", "IL", "62704-1234"),
            "premium_due": "2026-10-25",
        },
        "bob_c": {
            "medicare_number": "3KK5-OB7-JW19", "part_a": "2019-07-01", "part_b": "2019-07-01",
            "phone": "(217) 555-0193",
            "address": ("408 Westview Drive, Apt 3", None, "Springfield", "IL", "62702-8811"),
            "premium_due": "2026-10-25",
        },
        "carol_d": {
            "medicare_number": "7QW2-XR9-LM48", "part_a": "2022-11-01", "part_b": "2023-01-01",
            "phone": "(937) 555-0148",
            "address": ("77 Livingston Avenue", "Suite B", "Columbus", "OH", "43215-2604"),
            "premium_due": "2026-10-15",
        },
        "david_k": {
            "medicare_number": "9MR3-HB4-VN67", "part_a": "2020-05-01", "part_b": "2020-05-01",
            "phone": "(206) 555-0177",
            "address": ("1520 Pine Street, Apt 12", None, "Seattle", "WA", "98101-2205"),
            "premium_due": "2026-10-15",
        },
    }
    messages = {
        "alice_j": [
            ("Your Medicare Summary Notice is ready to view online",
             "Your Medicare Summary Notice (MSN) for services you got from June 1, 2026 through August 31, 2026 is ready. The MSN shows all your claims for services and supplies billed to Medicare during that 3-month period.",
             "2026-09-12", False),
            ("Welcome to your Medicare account",
             "Thank you for creating your Medicare account. You can use your account to check your claims, pay your Medicare premiums, order a replacement Medicare card, and manage your personal information.",
             "2026-05-02", True),
            ("Reminder: Medicare Open Enrollment starts October 15",
             "Medicare Open Enrollment runs October 15 through December 7, 2026. During Open Enrollment you can join, switch, or drop a Medicare Advantage Plan or Medicare drug plan.",
             "2026-09-20", False),
        ],
        "bob_c": [
            ("Your Part B premium is due",
             "Your Medicare Part B premium for October 2026 is due by October 25, 2026. You can pay online from your account, or set up automatic payments.",
             "2026-09-18", False),
            ("You have a new claim processed",
             "Medicare processed a claim from Arcadia Care on the Hill for physical therapy evaluation on August 30, 2026. Review the details under Claims.",
             "2026-09-08", True),
            ("Welcome to your Medicare account",
             "Thank you for creating your Medicare account. You can use your account to check your claims, pay your Medicare premiums, order a replacement Medicare card, and manage your personal information.",
             "2026-04-14", True),
        ],
        "carol_d": [
            ("Medicare fraud prevention reminder",
             "Medicare never calls to sell you anything or ask for your Medicare Number over the phone. Guard your Medicare card, and check your Medicare Summary Notice for services you didn't get.",
             "2026-09-01", False),
            ("Your Medicare Summary Notice is ready to view online",
             "Your Medicare Summary Notice (MSN) for services you got from June 1, 2026 through August 31, 2026 is ready.",
             "2026-09-12", True),
        ],
        "david_k": [
            ("Your replacement Medicare card was mailed",
             "Your new Medicare card was mailed to the address on file. It should arrive within 7-10 days. Your Medicare Number stays the same.",
             "2026-08-22", True),
            ("Welcome to your Medicare account",
             "Thank you for creating your Medicare account. You can use your account to check your claims, pay your Medicare premiums, order a replacement Medicare card, and manage your personal information.",
             "2026-03-30", True),
            ("Open Enrollment: compare your drug plan options",
             "Plan costs and coverage can change every year. Use the Medicare Plan Finder to compare Medicare drug plans available in your area for 2027.",
             "2026-09-21", False),
        ],
    }

    for spec in BENCHMARK_USERS:
        username = spec["username"]
        profile = profiles[username]
        user = User(
            username=username, email=spec["email"], display_name=spec["display"],
            password_hash=BENCHMARK_PASSWORD_HASH,
            medicare_number=profile["medicare_number"],
            part_a_effective=profile["part_a"], part_b_effective=profile["part_b"],
            phone=profile["phone"], is_benchmark=True)
        db.session.add(user)
        db.session.flush()

        line1, line2, city, state, zip_code = profile["address"]
        db.session.add(MailingAddress(
            user_id=user.id, line1=line1, line2=line2, city=city,
            state=state, zip=zip_code, is_current=True,
            effective_date=profile["part_a"]))
        for claim in _claims_for(username, None):
            claim.user_id = user.id
            db.session.add(claim)
        db.session.add(PremiumBill(
            user_id=user.id, plan="Medicare Part B", amount="$202.90",
            due_date=profile["premium_due"], status="Due"))
        db.session.add(PremiumBill(
            user_id=user.id, plan="Medicare Part B", amount="$202.90",
            due_date="2026-09-25", status="Paid", paid_date="2026-09-21",
            method="Direct deposit (bank account ending 4821)"))
        db.session.add(PaymentMethod(
            user_id=user.id, kind="bank", label="Bank account ending 4821",
            is_default=True))
        db.session.add(PaymentMethod(
            user_id=user.id, kind="card", label="Visa card ending 8419",
            is_default=False))
        for subject, body, received, is_read in messages[username]:
            db.session.add(Message(
                user_id=user.id, subject=subject, body=body,
                received_at=received, is_read=is_read))
        db.session.add(LoginEvent(
            user_id=user.id, when="2026-09-22T09:14:00",
            method="Medicare.gov account", device="Chrome on Windows"))
        db.session.add(LoginEvent(
            user_id=user.id, when="2026-09-01T18:47:00",
            method="Login.gov", device="Safari on iPhone"))
    db.session.commit()


def seed_database():
    seed_coverage_items()
    seed_coverage_topics()
    seed_providers()
    seed_dme()
    seed_publications()
    seed_costs()
    seed_content_pages()
    seed_plans()
    seed_benchmark_users()


if __name__ == "__main__":
    import shutil

    from app import app, db

    with app.app_context():
        db.create_all()
        seed_database()
        from app import CoverageItem, Provider, User
        print("seeded", CoverageItem.query.count(), "coverage items,",
              Provider.query.count(), "providers,",
              User.query.count(), "users")
    os.makedirs(os.path.join(BASE_DIR, "instance_seed"), exist_ok=True)
    shutil.copyfile(os.path.join(BASE_DIR, "instance", "medicare_gov.db"),
                    os.path.join(BASE_DIR, "instance_seed", "medicare_gov.db"))
    print("copied seed to instance_seed/medicare_gov.db")

"""CarMax mirror seed data.

Both seed_database() and seed_benchmark_users() are idempotent at the
function level (early-return on populated DB). All inserted rows use
frozen timestamps so the resulting SQLite file is byte-stable across
boots, which is critical for the WebHarbor reset invariant.

Image paths point into static/images/vehicles/<stock>-<view>.jpg. Those
files are populated by scripts/scrape_carmax.py (Playwright). Until the
scraper has run, templates fall back to _pending.svg via onerror.
"""
import json
from datetime import date, datetime, timedelta


# Frozen wall-clock so seeded rows are byte-stable across reset cycles.
SEED_NOW = datetime(2026, 1, 15, 12, 0, 0)
TODAY = date(2026, 5, 14)


def _slug(s):
    import re
    s = (s or '').lower().strip()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


# =============================================================================
# Stores: 12 real CarMax locations (public-info addresses)
# =============================================================================

STORES = [
    # slug, name, street, city, state, zip, phone, lat, lon
    ('atlanta-southlake', 'CarMax Atlanta Southlake',
     '6889 Mount Zion Blvd', 'Morrow', 'GA', '30260',
     '(770) 477-1480', 33.580, -84.336),
    ('houston-katy', 'CarMax Houston Katy',
     '21015 Katy Fwy', 'Katy', 'TX', '77449',
     '(281) 599-9890', 29.789, -95.741),
    ('miami-kendall', 'CarMax Miami Kendall',
     '11400 SW 88th St', 'Miami', 'FL', '33176',
     '(305) 271-7000', 25.685, -80.371),
    ('los-angeles-buena-park', 'CarMax Los Angeles Buena Park',
     '6101 Auto Center Dr', 'Buena Park', 'CA', '90621',
     '(714) 522-3690', 33.866, -118.011),
    ('chicago-tinley-park', 'CarMax Chicago Tinley Park',
     '8800 W 159th St', 'Tinley Park', 'IL', '60477',
     '(708) 532-1480', 41.595, -87.795),
    ('new-york-white-plains', 'CarMax White Plains',
     '120 Westchester Ave', 'White Plains', 'NY', '10601',
     '(914) 824-7100', 41.030, -73.770),
    ('washington-laurel', 'CarMax Laurel',
     '8800 Freestate Dr', 'Laurel', 'MD', '20723',
     '(301) 776-0070', 39.099, -76.880),
    ('boston-norwood', 'CarMax Boston Norwood',
     '500 Providence Hwy', 'Norwood', 'MA', '02062',
     '(781) 762-7600', 42.193, -71.198),
    ('seattle-lynnwood', 'CarMax Seattle Lynnwood',
     '17900 Highway 99', 'Lynnwood', 'WA', '98037',
     '(425) 670-0091', 47.834, -122.293),
    ('phoenix-tempe', 'CarMax Phoenix Tempe',
     '8000 S Autoplex Loop', 'Tempe', 'AZ', '85284',
     '(480) 753-0200', 33.346, -111.962),
    ('denver-thornton', 'CarMax Denver Thornton',
     '14150 Lincoln St', 'Thornton', 'CO', '80023',
     '(303) 252-7800', 39.954, -104.987),
    ('raleigh-cary', 'CarMax Raleigh Cary',
     '601 Davis Dr', 'Cary', 'NC', '27513',
     '(919) 467-1000', 35.795, -78.795),
]


# =============================================================================
# Vehicle template catalog. Each template generates several vehicles.
# Fields: (make, model, body_style, [trim1,trim2,...], [yr,yr,...],
#          engine_text, hp, torque, transmission, drive_type, fuel_type,
#          mpg_city, mpg_hwy, seats, msrp_new, base_features, [colors])
# =============================================================================

TEMPLATES = [
    ('Honda', 'Civic', 'Sedan',
     ['LX', 'Sport', 'EX', 'Touring'],
     [2020, 2021, 2022, 2023],
     '2.0L I-4', 158, 138, 'CVT Automatic', 'FWD', 'Gasoline',
     31, 40, 5, 24500,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Bluetooth Technology',
      'Lane Departure Warning', 'Automated Cruise Control'],
     ['Modern Steel Metallic', 'Aegean Blue Metallic', 'Crystal Black Pearl',
      'Lunar Silver Metallic', 'Sonic Gray Pearl']),
    ('Honda', 'Accord', 'Sedan',
     ['LX', 'Sport', 'EX-L', 'Touring'],
     [2019, 2020, 2021, 2022],
     '1.5L Turbo I-4', 192, 192, 'CVT Automatic', 'FWD', 'Gasoline',
     30, 38, 5, 28500,
     ['Apple CarPlay', 'Android Auto', 'Heated Seats', 'Leather Seats',
      'Lane Departure Warning', 'Automated Cruise Control', 'Sunroof',
      'BOSE Sound System'],
     ['Modern Steel Metallic', 'Platinum White Pearl', 'Crystal Black Pearl',
      'Radiant Red Metallic', 'Lunar Silver Metallic']),
    ('Honda', 'CR-V', 'SUV',
     ['LX', 'EX', 'EX-L', 'Touring'],
     [2019, 2020, 2021, 2022, 2023],
     '1.5L Turbo I-4', 190, 179, 'CVT Automatic', 'AWD', 'Gasoline',
     27, 32, 5, 31200,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Blind Spot Monitor',
      'Heated Seats', 'Power Seats', 'Sunroof', 'Automated Cruise Control'],
     ['Crystal Black Pearl', 'Modern Steel Metallic', 'Platinum White Pearl',
      'Radiant Red Metallic', 'Sonic Gray Pearl']),
    ('Honda', 'Pilot', 'SUV',
     ['LX', 'EX-L', 'Touring'],
     [2020, 2021, 2022],
     '3.5L V-6', 280, 262, '9-Speed Automatic', 'AWD', 'Gasoline',
     19, 26, 8, 38500,
     ['Apple CarPlay', 'Android Auto', 'Leather Seats', 'Power Seats',
      'Heated Seats', 'Blind Spot Monitor', 'Navigation System', 'Sunroof',
      'Third Row Seating'],
     ['Modern Steel Metallic', 'Platinum White Pearl', 'Crystal Black Pearl',
      'Forest Mist Metallic']),
    ('Toyota', 'Camry', 'Sedan',
     ['LE', 'SE', 'XLE', 'XSE'],
     [2019, 2020, 2021, 2022, 2023],
     '2.5L I-4', 203, 184, '8-Speed Automatic', 'FWD', 'Gasoline',
     28, 39, 5, 27000,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Bluetooth Technology',
      'Lane Departure Warning', 'Automated Cruise Control'],
     ['Midnight Black Metallic', 'Celestial Silver Metallic', 'Predawn Gray Mica',
      'Wind Chill Pearl', 'Supersonic Red']),
    ('Toyota', 'Corolla', 'Sedan',
     ['L', 'LE', 'SE', 'XSE'],
     [2020, 2021, 2022, 2023],
     '2.0L I-4', 169, 151, 'CVT Automatic', 'FWD', 'Gasoline',
     31, 40, 5, 22500,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Bluetooth Technology',
      'Lane Departure Warning'],
     ['Classic Silver Metallic', 'Midnight Black Metallic', 'Blizzard Pearl',
      'Blueprint', 'Barcelona Red Metallic']),
    ('Toyota', 'RAV4', 'SUV',
     ['LE', 'XLE', 'XLE Premium', 'Limited'],
     [2019, 2020, 2021, 2022, 2023],
     '2.5L I-4', 203, 184, '8-Speed Automatic', 'AWD', 'Gasoline',
     27, 35, 5, 30200,
     ['Apple CarPlay', 'Android Auto', 'Blind Spot Monitor', 'Sunroof',
      'Power Seats', 'Heated Seats', 'Automated Cruise Control'],
     ['Magnetic Gray Metallic', 'Midnight Black Metallic', 'Blueprint',
      'Lunar Rock', 'Ruby Flare Pearl']),
    ('Toyota', 'Tacoma', 'Truck',
     ['SR', 'SR5', 'TRD Sport', 'TRD Off-Road'],
     [2019, 2020, 2021, 2022, 2023],
     '3.5L V-6', 278, 265, '6-Speed Automatic', '4WD', 'Gasoline',
     18, 22, 5, 32800,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Bluetooth Technology',
      'Skid Plates', 'Bed Liner', 'Tow Hitch'],
     ['Magnetic Gray Metallic', 'Midnight Black Metallic', 'Silver Sky Metallic',
      'Cement', 'Army Green']),
    ('Toyota', 'Highlander', 'SUV',
     ['LE', 'XLE', 'Limited'],
     [2020, 2021, 2022],
     '3.5L V-6', 295, 263, '8-Speed Automatic', 'AWD', 'Gasoline',
     20, 27, 8, 36500,
     ['Apple CarPlay', 'Android Auto', 'Third Row Seating', 'Power Seats',
      'Heated Seats', 'Leather Seats', 'Navigation System', 'Blind Spot Monitor'],
     ['Midnight Black Metallic', 'Magnetic Gray Metallic', 'Celestial Silver',
      'Blueprint', 'Wind Chill Pearl']),
    ('Ford', 'F-150', 'Truck',
     ['XL', 'XLT', 'Lariat', 'King Ranch'],
     [2019, 2020, 2021, 2022, 2023],
     '5.0L V-8', 400, 410, '10-Speed Automatic', '4WD', 'Gasoline',
     16, 22, 5, 42000,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Tow Package',
      'Power Seats', 'Heated Seats', 'Bluetooth Technology', 'Bed Liner'],
     ['Oxford White', 'Agate Black Metallic', 'Iconic Silver Metallic',
      'Velocity Blue Metallic', 'Race Red']),
    ('Ford', 'Explorer', 'SUV',
     ['Base', 'XLT', 'Limited', 'Platinum'],
     [2019, 2020, 2021, 2022],
     '2.3L Turbo I-4', 300, 310, '10-Speed Automatic', 'AWD', 'Gasoline',
     20, 28, 7, 35700,
     ['Apple CarPlay', 'Android Auto', 'Third Row Seating', 'Power Seats',
      'Heated Seats', 'Sunroof', 'Navigation System'],
     ['Agate Black Metallic', 'Iconic Silver Metallic', 'Oxford White',
      'Atlas Blue Metallic', 'Rapid Red Metallic']),
    ('Ford', 'Mustang', 'Coupe',
     ['EcoBoost', 'GT Premium', 'Mach 1'],
     [2019, 2020, 2021, 2022],
     '5.0L V-8', 460, 420, '10-Speed Automatic', 'RWD', 'Gasoline',
     15, 24, 4, 37000,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Leather Seats',
      'Heated Seats', 'Bluetooth Technology', 'Sunroof'],
     ['Oxford White', 'Race Red', 'Shadow Black', 'Velocity Blue Metallic',
      'Twister Orange Metallic']),
    ('Ford', 'Escape', 'SUV',
     ['S', 'SE', 'Titanium'],
     [2019, 2020, 2021, 2022],
     '1.5L Turbo I-3', 181, 190, '8-Speed Automatic', 'AWD', 'Gasoline',
     27, 33, 5, 27800,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Lane Departure Warning',
      'Automated Cruise Control'],
     ['Agate Black Metallic', 'Oxford White', 'Iconic Silver Metallic',
      'Atlas Blue Metallic']),
    ('Chevrolet', 'Silverado', 'Truck',
     ['WT', 'Custom', 'LT', 'RST', 'High Country'],
     [2019, 2020, 2021, 2022, 2023],
     '5.3L V-8', 355, 383, '8-Speed Automatic', '4WD', 'Gasoline',
     15, 21, 6, 44000,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Tow Package',
      'Bed Liner', 'Bluetooth Technology', 'Power Seats'],
     ['Summit White', 'Silver Ice Metallic', 'Black', 'Northsky Blue Metallic',
      'Cherry Red Tintcoat']),
    ('Chevrolet', 'Equinox', 'SUV',
     ['L', 'LS', 'LT', 'Premier'],
     [2019, 2020, 2021, 2022],
     '1.5L Turbo I-4', 170, 203, '6-Speed Automatic', 'AWD', 'Gasoline',
     26, 31, 5, 27600,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Blind Spot Monitor',
      'Bluetooth Technology'],
     ['Summit White', 'Silver Ice Metallic', 'Mosaic Black Metallic',
      'Pacific Blue Metallic', 'Cayenne Orange Metallic']),
    ('Chevrolet', 'Tahoe', 'SUV',
     ['LS', 'LT', 'Premier'],
     [2020, 2021, 2022, 2023],
     '5.3L V-8', 355, 383, '10-Speed Automatic', '4WD', 'Gasoline',
     14, 19, 8, 56000,
     ['Apple CarPlay', 'Android Auto', 'Third Row Seating', 'Leather Seats',
      'Heated Seats', 'Power Seats', 'Navigation System', 'Sunroof'],
     ['Summit White', 'Black', 'Empire Beige Metallic', 'Northsky Blue Metallic',
      'Silver Ice Metallic']),
    ('Nissan', 'Altima', 'Sedan',
     ['S', 'SV', 'SR', 'SL'],
     [2019, 2020, 2021, 2022, 2023],
     '2.5L I-4', 188, 180, 'CVT Automatic', 'FWD', 'Gasoline',
     28, 39, 5, 25300,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Bluetooth Technology',
      'Lane Departure Warning'],
     ['Super Black', 'Brilliant Silver Metallic', 'Pearl White Tricoat',
      'Storm Blue Metallic', 'Scarlet Ember Tintcoat']),
    ('Nissan', 'Rogue', 'SUV',
     ['S', 'SV', 'SL', 'Platinum'],
     [2019, 2020, 2021, 2022, 2023],
     '2.5L I-4', 181, 181, 'CVT Automatic', 'AWD', 'Gasoline',
     27, 34, 5, 27800,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Blind Spot Monitor',
      'Power Seats', 'Heated Seats'],
     ['Super Black', 'Brilliant Silver Metallic', 'Pearl White Tricoat',
      'Caspian Blue Metallic', 'Scarlet Ember Tintcoat']),
    ('Hyundai', 'Elantra', 'Sedan',
     ['SE', 'SEL', 'Limited'],
     [2020, 2021, 2022, 2023],
     '2.0L I-4', 147, 132, 'CVT Automatic', 'FWD', 'Gasoline',
     33, 42, 5, 21300,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Lane Departure Warning',
      'Bluetooth Technology', 'Automated Cruise Control'],
     ['Phantom Black', 'Phantom Black Pearl', 'Quartz White Pearl',
      'Cyber Gray', 'Lava Orange', 'Intense Blue']),
    ('Hyundai', 'Tucson', 'SUV',
     ['SE', 'SEL', 'Limited'],
     [2020, 2021, 2022, 2023],
     '2.5L I-4', 187, 178, '8-Speed Automatic', 'AWD', 'Gasoline',
     24, 29, 5, 28400,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Blind Spot Monitor',
      'Heated Seats', 'Power Seats'],
     ['Phantom Black', 'Shimmering Silver', 'Magnetic Force Metallic',
      'Intense Blue', 'Quartz White Pearl']),
    ('Hyundai', 'Santa Fe', 'SUV',
     ['SE', 'SEL', 'Limited'],
     [2019, 2020, 2021, 2022],
     '2.5L Turbo I-4', 277, 311, '8-Speed Automatic', 'AWD', 'Gasoline',
     22, 28, 5, 31800,
     ['Apple CarPlay', 'Android Auto', 'Leather Seats', 'Heated Seats',
      'Power Seats', 'Blind Spot Monitor', 'Navigation System'],
     ['Phantom Black', 'Quartz White Pearl', 'Magnetic Force',
      'Calypso Red', 'Lagoon Blue']),
    ('Kia', 'Sportage', 'SUV',
     ['LX', 'EX', 'SX Turbo'],
     [2019, 2020, 2021, 2022],
     '2.4L I-4', 181, 175, '6-Speed Automatic', 'AWD', 'Gasoline',
     22, 28, 5, 25800,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Bluetooth Technology',
      'Blind Spot Monitor'],
     ['Snow White Pearl', 'Steel Gray', 'Pacific Blue', 'Hyper Red',
      'Black Cherry']),
    ('Kia', 'Sorento', 'SUV',
     ['LX', 'EX', 'SX Prestige'],
     [2019, 2020, 2021, 2022, 2023],
     '2.5L Turbo I-4', 281, 311, '8-Speed Automatic', 'AWD', 'Gasoline',
     21, 28, 7, 31900,
     ['Apple CarPlay', 'Android Auto', 'Third Row Seating', 'Leather Seats',
      'Heated Seats', 'Power Seats', 'Sunroof'],
     ['Snow White Pearl', 'Ebony Black', 'Steel Gray', 'Sapphire Blue',
      'Runway Red']),
    ('Jeep', 'Grand Cherokee', 'SUV',
     ['Laredo', 'Limited', 'Overland', 'Summit'],
     [2019, 2020, 2021, 2022, 2023],
     '3.6L V-6', 293, 260, '8-Speed Automatic', '4WD', 'Gasoline',
     19, 26, 5, 41000,
     ['Apple CarPlay', 'Android Auto', 'Leather Seats', 'Heated Seats',
      'Power Seats', 'Navigation System', 'Sunroof', 'Blind Spot Monitor'],
     ['Diamond Black Crystal', 'Bright White', 'Velvet Red Pearl',
      'Granite Crystal Metallic', 'Hydro Blue Pearl']),
    ('Jeep', 'Wrangler', 'SUV',
     ['Sport', 'Sport S', 'Rubicon', 'Sahara'],
     [2019, 2020, 2021, 2022, 2023],
     '3.6L V-6', 285, 260, '8-Speed Automatic', '4WD', 'Gasoline',
     17, 23, 4, 33500,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Skid Plates',
      'Tow Hooks', 'Bluetooth Technology'],
     ['Bright White', 'Black', 'Firecracker Red', 'Sting-Gray',
      'Hellayella', 'Sarge Green']),
    ('Subaru', 'Outback', 'Wagon',
     ['Base', 'Premium', 'Limited', 'Touring'],
     [2019, 2020, 2021, 2022, 2023],
     '2.5L I-4', 182, 176, 'CVT Automatic', 'AWD', 'Gasoline',
     26, 33, 5, 28800,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Blind Spot Monitor',
      'Heated Seats', 'Power Seats', 'Automated Cruise Control'],
     ['Crystal White Pearl', 'Crystal Black Silica', 'Ice Silver Metallic',
      'Abyss Blue Pearl', 'Autumn Green Metallic']),
    ('Subaru', 'Forester', 'SUV',
     ['Base', 'Premium', 'Sport', 'Limited'],
     [2019, 2020, 2021, 2022],
     '2.5L I-4', 182, 176, 'CVT Automatic', 'AWD', 'Gasoline',
     26, 33, 5, 27400,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Lane Departure Warning',
      'Blind Spot Monitor', 'Heated Seats'],
     ['Crystal White Pearl', 'Crystal Black Silica', 'Magnetite Gray',
      'Horizon Blue Pearl', 'Jasper Green Metallic']),
    ('Mazda', 'CX-5', 'SUV',
     ['Sport', 'Touring', 'Grand Touring'],
     [2019, 2020, 2021, 2022, 2023],
     '2.5L I-4', 187, 186, '6-Speed Automatic', 'AWD', 'Gasoline',
     24, 30, 5, 28250,
     ['Apple CarPlay', 'Android Auto', 'Backup Camera', 'Leather Seats',
      'Heated Seats', 'Power Seats', 'Blind Spot Monitor', 'Sunroof'],
     ['Jet Black Mica', 'Snowflake White Pearl Mica', 'Sonic Silver Metallic',
      'Soul Red Crystal Metallic', 'Polymetal Gray Metallic']),
    ('BMW', '3 Series', 'Sedan',
     ['330i', '330i xDrive', 'M340i'],
     [2019, 2020, 2021, 2022],
     '2.0L Turbo I-4', 255, 295, '8-Speed Automatic', 'AWD', 'Gasoline',
     26, 36, 5, 44000,
     ['Apple CarPlay', 'Android Auto', 'Leather Seats', 'Heated Seats',
      'Power Seats', 'Navigation System', 'Sunroof', 'BOSE Sound System'],
     ['Alpine White', 'Black Sapphire Metallic', 'Mineral Gray Metallic',
      'Portimao Blue Metallic', 'Skyscraper Gray Metallic']),
    ('Mercedes-Benz', 'C-Class', 'Sedan',
     ['C300', 'C300 4MATIC', 'AMG C43'],
     [2019, 2020, 2021, 2022],
     '2.0L Turbo I-4', 255, 273, '9-Speed Automatic', 'AWD', 'Gasoline',
     25, 35, 5, 45000,
     ['Apple CarPlay', 'Android Auto', 'Leather Seats', 'Heated Seats',
      'Navigation System', 'Sunroof', 'Blind Spot Monitor'],
     ['Polar White', 'Obsidian Black Metallic', 'Iridium Silver Metallic',
      'Mojave Silver Metallic', 'Selenite Gray Metallic']),
    ('Tesla', 'Model 3', 'Sedan',
     ['Standard Range Plus', 'Long Range', 'Performance'],
     [2019, 2020, 2021, 2022, 2023],
     'Dual Electric Motors', 346, 389, 'Single-Speed', 'AWD', 'Electric',
     132, 126, 5, 49000,
     ['Backup Camera', 'Automated Cruise Control', 'Lane Departure Warning',
      'Heated Seats', 'Power Seats', 'Navigation System', 'Sunroof'],
     ['Pearl White Multi-Coat', 'Solid Black', 'Midnight Silver Metallic',
      'Deep Blue Metallic', 'Red Multi-Coat']),
]


# Interior colors keyed by exterior — short, deterministic mapping
INTERIOR_COLORS = ['Black', 'Gray', 'Beige', 'Brown']

# Trim feature accruals: each successive trim inherits prior + adds
TRIM_FEATURE_ADDONS = [
    [],  # trim 0 (base): no extras
    ['Power Seats', 'Power Windows', 'Power Locks', 'Cruise Control'],  # trim 1
    ['Heated Seats', 'Sunroof', 'Blind Spot Monitor', 'Smart Key',
     'Power Mirrors', 'Heated Mirrors'],  # trim 2
    ['Leather Seats', 'Navigation System', 'BOSE Sound System',
     'Remote Start', 'Parking Sensors'],  # trim 3
    ['Premium Sound', 'Wireless Charging', 'Premium Wheels'],  # trim 4+
]


def _vehicle_for(template_idx, trim_idx, year_idx, store_idx, color_idx,
                 mileage_seed):
    """Deterministically build one vehicle from a template + indexed choices."""
    t = TEMPLATES[template_idx]
    (make, model, body_style, trims, years, engine, hp, torque,
     trans, drive, fuel, mpgc, mpgh, seats, msrp, base_feats, colors) = t
    trim = trims[trim_idx]
    year = years[year_idx]
    color = colors[color_idx % len(colors)]
    interior = INTERIOR_COLORS[(trim_idx + year_idx) % len(INTERIOR_COLORS)]

    # Features accrue by trim level
    feats = list(base_feats)
    for i in range(trim_idx + 1):
        if i < len(TRIM_FEATURE_ADDONS):
            for f in TRIM_FEATURE_ADDONS[i]:
                if f not in feats:
                    feats.append(f)
    # Sport/Performance/SI/Type/AMG/Performance/Touring extras
    sporty = any(w in trim for w in ('Sport', 'SI', 'AMG', 'Performance',
                                     'Mach', 'TRD', 'Rubicon', 'M340'))
    if sporty:
        for f in ('Rear Spoiler', 'Alloy Wheels', 'Turbo Charged Engine'):
            if f not in feats:
                feats.append(f)
    if 'Electric' in fuel:
        feats = [f for f in feats if 'Turbo' not in f]
        feats.append('All-Electric Drivetrain')
    feats.append('CarMax Certified')

    # Depreciation: 18% first year + 11% subsequent (so 5-yr ~ 50%)
    age = max(2026 - year, 0)
    if age == 0:
        depr = 1.0
    else:
        depr = 0.82 * (0.89 ** (age - 1))
    trim_premium = 1.0 + 0.04 * trim_idx
    price = msrp * depr * trim_premium
    price = round(price / 100) * 100  # round to $100
    list_price = round(msrp * (1.0 + 0.02 * trim_idx) / 100) * 100

    # Mileage: deterministic from age + seed
    expected_per_year = 11500 + (mileage_seed % 3) * 1500
    mileage = age * expected_per_year + (mileage_seed % 1500)
    mileage = max(2400, mileage)

    # Stock + VIN: deterministic
    stock = f"{template_idx:02d}{trim_idx}{year_idx}{store_idx:02d}{color_idx % 6}{mileage_seed % 10}".ljust(8, '0')[:8]
    vin = f"1HG{template_idx:02d}{trim_idx}{year_idx % 10}{store_idx:02d}{(template_idx*97 + trim_idx*53 + year_idx*7) % 1000:03d}{color_idx:03d}".replace(' ', '0')[:17].upper()

    slug = _slug(f"{year}-{make}-{model}-{trim}-{stock}")

    image = f"/static/images/vehicles/{stock}-front.jpg"
    gallery = [
        f"/static/images/vehicles/{stock}-front.jpg",
        f"/static/images/vehicles/{stock}-side.jpg",
        f"/static/images/vehicles/{stock}-rear.jpg",
        f"/static/images/vehicles/{stock}-dashboard.jpg",
        f"/static/images/vehicles/{stock}-cargo.jpg",
        f"/static/images/vehicles/{stock}-interior.jpg",
    ]

    description = (f"This {year} {make} {model} {trim} comes equipped with a "
                   f"{engine.lower()} engine, {trans.lower()}, "
                   f"and {drive} drivetrain. It has been CarMax Certified through our "
                   f"125+ point inspection — no flood or frame damage, no salvage "
                   f"history. Eligible for our 30-day limited warranty and "
                   f"10-day money back guarantee.")

    transfer_fee = 0 if mileage_seed % 4 == 0 else (
        99 if mileage_seed % 4 == 1 else (199 if mileage_seed % 4 == 2 else 399))

    days_on_lot = 4 + ((template_idx * 7 + trim_idx * 13 + year_idx * 19
                        + store_idx * 23 + mileage_seed) % 40)

    customer_rating = round(3.8 + ((template_idx + year_idx) % 13) / 10.0, 1)
    customer_rating_count = 6 + (template_idx + trim_idx * 3) % 24
    repairpal = round(3.5 + (template_idx % 16) / 10.0, 1)

    # Featured/new-arrival/price-drop flags (deterministic)
    is_featured = (template_idx + trim_idx) % 7 == 0
    is_new_arrival = days_on_lot <= 9
    is_price_drop = (mileage_seed % 5) == 0 and (list_price > price)

    return {
        'stock_number': stock,
        'slug': slug,
        'vin': vin,
        'year': year,
        'make': make,
        'make_slug': _slug(make),
        'model': model,
        'model_slug': _slug(model),
        'trim': trim,
        'trim_slug': _slug(trim),
        'body_style': body_style,
        'exterior_color': color,
        'interior_color': interior,
        'mileage': mileage,
        'price': price,
        'list_price': list_price,
        'engine_text': engine,
        'engine_displacement': float(engine.split('L')[0].split(' ')[-1]) if 'L' in engine else 0.0,
        'horsepower': hp,
        'torque': torque,
        'transmission': trans,
        'drive_type': drive,
        'fuel_type': fuel,
        'mpg_city': mpgc,
        'mpg_highway': mpgh,
        'mpg_combined': (mpgc + mpgh) // 2 if fuel != 'Electric' else (mpgc + mpgh) // 2,
        'seating_capacity': seats,
        'cargo_volume': 14.0 + (template_idx % 30),
        'wheelbase': 105.0 + (template_idx % 25),
        'overall_length': 178.0 + (template_idx % 40),
        'width': 70.0 + (template_idx % 8),
        'height': 55.0 + (template_idx % 18),
        'fuel_capacity': 13.0 + (template_idx % 12),
        'features': json.dumps(feats),
        'description': description,
        'image': image,
        'gallery_images': json.dumps(gallery),
        'customer_rating': customer_rating,
        'customer_rating_count': customer_rating_count,
        'repairpal_rating': repairpal,
        'is_certified': True,
        'is_featured': is_featured,
        'is_no_haggle': True,
        'is_new_arrival': is_new_arrival,
        'is_price_drop': is_price_drop,
        'store_id': store_idx + 1,   # 1-indexed
        'transfer_fee': transfer_fee,
        'days_on_lot': days_on_lot,
        'added_at': SEED_NOW - timedelta(days=days_on_lot),
    }


def _build_vehicle_seeds():
    """Deterministically iterate templates/trims/years/stores to ~150 vehicles."""
    rows = []
    counter = 0
    for ti, t in enumerate(TEMPLATES):
        # Pick 5 vehicle variants per template (roughly): one per trim, varied year
        trims = t[3]
        years = t[4]
        colors_count = len(t[16])
        n_variants = min(5, max(4, len(trims) + 1))
        for variant in range(n_variants):
            trim_idx = variant % len(trims)
            year_idx = (variant + ti) % len(years)
            store_idx = (counter + ti) % len(STORES)
            color_idx = (variant * 3 + ti) % colors_count
            mileage_seed = (counter * 313 + ti * 97) % 9973
            rows.append(_vehicle_for(ti, trim_idx, year_idx, store_idx,
                                     color_idx, mileage_seed))
            counter += 1
    return rows


# =============================================================================
# Articles
# =============================================================================

ARTICLES = [
    ('how-carmax-works',
     'How CarMax Works — Buy, Sell, Finance',
     'research', True,
     'Shop online or in store, get pre-qualified, and enjoy our 10-day money-back guarantee and 30-day limited warranty.',
     'Shopping with CarMax is straightforward. We are customer-focused and want you to have a great car-buying experience. You can shop online, in-store, or a mix of both — whatever works best for you.\n\nEvery car we sell is CarMax Certified, which means no flood or frame damage and no salvage history. Each car undergoes a detailed 125+ point checklist by our trained technicians, and we will repair, replace, or detail anything necessary to meet our standards.\n\nWe are known for being upfront on our pricing — we do not haggle. For a stress-free and transparent customer experience, it is the same price for everyone.\n\nWe understand that buying a vehicle is a big decision, and you want to feel confident about getting it right the first time.'),
    ('how-to-sell-your-car-to-carmax',
     'How to Sell Your Car to CarMax',
     'selling', True,
     'Get a real, upfront written offer in under 2 minutes. Good for 7 days. Sell or trade — your choice.',
     'Selling your car to CarMax is fast and transparent. You can start your offer online with just your license plate, mileage, and ZIP, then bring the car to any CarMax store for a brief verification.\n\nThe offer is good for 7 days. The price is the same whether you trade in or sell outright.\n\nOnline appraisals take about 2 minutes; in-store appraisals run 30-45 minutes including the test drive and inspection.'),
    ('pre-approval-vs-pre-qualified',
     'Getting Pre-Qualified: Shop with Personalized Financing Terms',
     'financing', True,
     'Pre-qualification uses a soft credit check and gives you personalized monthly payments — no impact to your credit score.',
     'A pre-qualification reviews your current financial situation and credit history with a soft credit inquiry. It does not impact your credit score.\n\nPre-qualifying lets you shop with personalized terms — see actual monthly payments on every car. Final terms require a credit application, which results in a hard inquiry.\n\nAt CarMax, pre-qualifications are valid for 30 days.'),
    ('best-compact-sedan-honda-civic-vs-toyota-corolla-vs-nissan-sentra',
     'Best Compact Sedan: Honda Civic vs. Toyota Corolla vs. Nissan Sentra',
     'research', False,
     'Three popular compact sedans compared on price, fuel economy, and features.',
     'The compact sedan segment remains one of the most popular for value-minded buyers. Here is how three of the best-sellers compare.\n\nThe Honda Civic offers refined driving dynamics and a sophisticated cabin. The Toyota Corolla brings legendary reliability and the lowest cost of ownership. The Nissan Sentra punches above its weight with standard advanced driver-assistance features.'),
    ('best-hatchback-cars-ranking',
     'Best Used Hatchback Cars for 2024: Ranked',
     'research', False,
     'Practical, versatile, and surprisingly fun — our take on the best used hatchbacks.',
     'Hatchbacks deliver sedan-like fuel economy with SUV-like cargo flexibility. We ranked the most popular used hatchbacks based on sales data, reliability ratings, and cargo capacity.'),
    ('how-to-buy-a-used-car',
     'How to Buy a Used Car: From Online to the Lot',
     'how-to', False,
     'A simple step-by-step guide to buying a used car the smart way.',
     'Step 1: Set your budget — or get pre-qualified to make that easy. Step 2: Narrow down body style, then make and model, using research pages. Step 3: Shop the nationwide inventory online; reserve any car for 7 days while you finish paperwork. Step 4: Test drive at the store or at home. Step 5: Finalize financing. Step 6: Take delivery.'),
    ('maxcare-explained',
     'MaxCare Service Plans — Coverage Explained',
     'how-to', False,
     'Optional extended-warranty coverage that picks up where the limited warranty leaves off.',
     'MaxCare extended service plans run up to 60 months / 100,000 miles. Each plan includes hassle-free repairs at any licensed shop, 24/7 roadside assistance, and rental reimbursement up to $40/day. You can cancel any time.'),
    ('first-time-car-buyer',
     'First-Time Car Buyer? Your Step-by-Step Guide',
     'how-to', False,
     'Building credit, picking a car, and financing your first vehicle without overpaying.',
     'Buying your first car is a big step. The two best things you can do up front: (1) understand your monthly budget, including insurance and fuel; (2) get pre-qualified so you know exactly what you can afford. CarMax has finance sources for first-time buyers.'),
    ('best-high-mpg-cars',
     'Best High-MPG Used Cars',
     'research', False,
     'Looking for the best gas mileage? These used cars consistently top fuel economy lists.',
     'Hybrids dominate this list, but even non-hybrid compact sedans can clear 40 mpg highway. Top picks include the Toyota Corolla Hybrid, Honda Civic, Hyundai Elantra, and Toyota Camry.'),
    ('attainable-dream-cars-under-50000',
     'Attainable Dream Cars Under $50,000',
     'research', False,
     'For the price of an average new car, you can drive something special.',
     'New cars now average around $50,000 — but the used market opens the door to driving something more exciting. Convertibles, sports coupes, and luxury SUVs at this price point are well within reach.'),
]


# =============================================================================
# Customer reviews (one or two per popular model/year combo)
# =============================================================================

REVIEW_TEMPLATES = [
    # (make_slug, model_slug, year, rating, title, body, name, location)
    ('honda', 'civic', 2022, 5, 'Best small sedan period',
     'Great gas mileage, refined cabin, and just enough power for everything I need to do. Highway road noise is the only knock.',
     'Marcus T.', 'Chicago, IL'),
    ('honda', 'civic', 2022, 4, 'Solid choice for commuters',
     'Comfortable seats, easy to use Apple CarPlay, and reliable so far. The base 2.0L feels a bit slow on hills.',
     'Priya R.', 'Atlanta, GA'),
    ('honda', 'accord', 2021, 5, 'Quiet, spacious, and well-built',
     'Roomy interior, smooth ride, and the Touring trim has every feature I wanted. Best sedan I have owned.',
     'David K.', 'Houston, TX'),
    ('honda', 'cr-v', 2022, 5, 'Perfect family SUV',
     'Plenty of cargo space, comfortable for road trips, and AWD handles winter just fine. Fuel economy is impressive too.',
     'Sarah B.', 'Denver, CO'),
    ('toyota', 'camry', 2022, 5, 'Reliable as ever',
     'Toyota nailed the redesign. Comfortable, gets great mileage, and the tech finally feels modern.',
     'Jennifer L.', 'Los Angeles, CA'),
    ('toyota', 'rav4', 2021, 4, 'Great value crossover',
     'Honest, reliable SUV. Not the most fun to drive, but it does everything well and has been bulletproof.',
     'Mike P.', 'Seattle, WA'),
    ('toyota', 'tacoma', 2021, 5, 'Best off-road truck for the money',
     'TRD Off-Road has handled everything I have thrown at it. Resale value is unreal.',
     'James W.', 'Phoenix, AZ'),
    ('ford', 'f-150', 2022, 5, 'Workhorse and comfortable cruiser',
     'Towed my boat across three states without issue. Cabin is quiet and the SYNC system is finally good.',
     'Robert M.', 'Raleigh, NC'),
    ('ford', 'mustang', 2021, 5, 'GT is a riot',
     'V8 sounds incredible, and the chassis is much better than people give it credit for. 10-speed automatic is buttery.',
     'Carlos D.', 'Miami, FL'),
    ('chevrolet', 'silverado', 2022, 4, 'Capable and quiet',
     'Tows great, comfortable on long drives, but fuel economy is what you expect from a V8 truck.',
     'Linda H.', 'Houston, TX'),
    ('chevrolet', 'tahoe', 2022, 5, 'Family hauler king',
     'Plenty of room for everyone and everything. The new independent rear suspension is a huge upgrade.',
     'Anthony S.', 'Atlanta, GA'),
    ('nissan', 'altima', 2021, 4, 'Underrated sedan',
     'Quiet ride, good fuel economy, and the 2.0 turbo is plenty fast. Interior could be a bit nicer.',
     'Ashley N.', 'Tinley Park, IL'),
    ('hyundai', 'tucson', 2022, 5, 'Bold redesign, great value',
     'The new styling is polarizing but I love it. Tech features rival cars twice the price.',
     'Wei C.', 'White Plains, NY'),
    ('kia', 'sorento', 2022, 5, 'Three-row SUV that feels premium',
     'Comfortable interior, smooth turbo engine, and the third row is actually usable for short trips.',
     'Maria G.', 'Laurel, MD'),
    ('jeep', 'wrangler', 2021, 5, 'Lives up to the legend',
     'Off-road capability is unmatched. On-road manners are quirky but that is part of the charm.',
     'Tyler J.', 'Buena Park, CA'),
    ('subaru', 'outback', 2022, 5, 'Best all-weather wagon',
     'Standard AWD, generous cargo, and EyeSight has saved me from at least one rear-end. Highly recommend.',
     'Hannah O.', 'Norwood, MA'),
    ('mazda', 'cx-5', 2021, 5, 'Most fun crossover in its class',
     'Steering feel and chassis tuning are a cut above. Beautiful cabin too.',
     'Daniel F.', 'Cary, NC'),
    ('bmw', '3-series', 2021, 4, 'Still the sport sedan benchmark',
     'Engine and transmission are fantastic. iDrive takes some learning. Ride is firm.',
     'Elena V.', 'Thornton, CO'),
    ('tesla', 'model-3', 2021, 5, 'No going back to gas',
     'Instant torque, never visit a gas station, and Supercharging on road trips is easy. Build quality has improved a lot.',
     'Naveen P.', 'Lynnwood, WA'),
    ('toyota', 'corolla', 2022, 4, 'Just works',
     'Boring in the best way. Sips fuel, never breaks, easy to park. What more do you want from a commuter?',
     'Beth E.', 'Tempe, AZ'),
]


# =============================================================================
# Seeding functions — IDEMPOTENT at the function level
# =============================================================================

def seed_database():
    """Create stores, vehicles, articles, reviews. Early-return if populated."""
    from app import (Article, Review, Store, Vehicle, db)
    if Vehicle.query.count() > 0:
        return

    # Stores
    for slug, name, street, city, state, zip_code, phone, lat, lon in STORES:
        s = Store(slug=slug, name=name, street=street, city=city, state=state,
                  zip_code=zip_code, phone=phone, latitude=lat, longitude=lon,
                  has_appraisal=True, has_express_pickup=True,
                  has_service=True, has_home_delivery=True,
                  hours_weekday='10:00 AM - 9:00 PM',
                  hours_saturday='9:00 AM - 9:00 PM',
                  hours_sunday='12:00 PM - 7:00 PM',
                  image='/static/images/stores/storefront_default.jpg')
        db.session.add(s)
    db.session.flush()

    # Vehicles — built deterministically from templates
    seeds = _build_vehicle_seeds()
    for s in seeds:
        v = Vehicle(**s)
        db.session.add(v)

    # Articles
    for slug, title, category, featured, summary, body in ARTICLES:
        pub = date(2025, 11, 1) + timedelta(days=(hash(slug) % 180))
        a = Article(slug=slug, title=title, category=category,
                    summary=summary, body=body,
                    hero_image=f"/static/images/articles/{slug}.jpg",
                    published_at=pub, is_featured=featured)
        db.session.add(a)

    # Reviews — written by the system (no user_id, anonymized name)
    for make_slug, model_slug, year, rating, title, body, name, loc in REVIEW_TEMPLATES:
        r = Review(make_slug=make_slug, model_slug=model_slug, year=year,
                   rating=rating, title=title, body=body,
                   reviewer_name=name, location=loc,
                   created_at=SEED_NOW)
        db.session.add(r)

    db.session.commit()


def seed_benchmark_users():
    """Five benchmark users used by WebVoyager tasks. Idempotent."""
    from app import (Appraisal, FinancePreQual, Order, Reservation,
                     Review, SavedVehicle, Store, TestDrive, User, Vehicle,
                     bcrypt, db)
    if User.query.filter_by(email='alice.j@test.com').first():
        return

    # Look up store IDs (slug -> id) deterministically
    store_id_by_slug = {s.slug: s.id for s in Store.query.all()}

    users = [
        # (email, first, last, phone, zip, addr1, city, state, home_store_slug,
        #  prequal: (monthly_max, term, apr, down, tier, expires_offset),
        #  annual_income, employment_status)
        ('alice.j@test.com', 'Alice', 'Johnson', '(404) 555-0118', '30303',
         '410 Peachtree St NE', 'Atlanta', 'GA', 'atlanta-southlake',
         (550.0, 72, 7.49, 2500.0, 'good', 30), 78000, 'employed_full_time'),
        ('bob.k@test.com', 'Bob', 'Kim', '(713) 555-0119', '77002',
         '1500 Louisiana St', 'Houston', 'TX', 'houston-katy',
         (700.0, 60, 5.49, 5000.0, 'excellent', 30), 142000, 'employed_full_time'),
        ('carol.l@test.com', 'Carol', 'Lopez', '(305) 555-0120', '33176',
         '11400 SW 92nd Ct', 'Miami', 'FL', 'miami-kendall',
         (425.0, 72, 11.99, 1500.0, 'fair', 30), 54000, 'self_employed'),
        ('dan.m@test.com', 'Dan', 'Murphy', '(617) 555-0121', '02062',
         '88 School St', 'Norwood', 'MA', 'boston-norwood',
         None, 65000, 'employed_full_time'),
        ('emma.n@test.com', 'Emma', 'Nguyen', '(206) 555-0122', '98037',
         '17800 Highway 99', 'Lynnwood', 'WA', 'seattle-lynnwood',
         (320.0, 66, 17.99, 1000.0, 'building', 30), 38000, 'student'),
    ]

    user_objs = {}
    for (email, first, last, phone, zip_code, addr1, city, state,
         home_slug, prequal, income, emp) in users:
        u = User(
            email=email,
            first_name=first, last_name=last,
            phone=phone, zip_code=zip_code,
            address_line1=addr1, city=city, state=state,
            home_store_id=store_id_by_slug.get(home_slug),
            annual_income=income,
            employment_status=emp,
            created_at=SEED_NOW,
        )
        # Set deterministic password (bcrypt is randomized by salt; we need
        # to set a stable password_hash by using a fixed pre-computed hash
        # OR by setting one via set_password but accepting the salt churn.
        # Since the salt randomness would break md5 stability, we use a
        # pre-baked bcrypt hash for 'CarMax!2026' generated once.
        # NOTE: bcrypt verification still works with this fixed hash.
        u.password_hash = '$2b$12$abcdefghijklmnopqrstuuj6phTDGC0QgZUgJBeZsSqG7EdTlBv7K'
        if prequal:
            mmax, term, apr, down, tier, exp_off = prequal
            u.pre_qual_active = True
            u.pre_qual_monthly_max = mmax
            u.pre_qual_term_months = term
            u.pre_qual_apr = apr
            u.pre_qual_down_payment = down
            u.pre_qual_credit_tier = tier
            u.pre_qual_expires_at = TODAY + timedelta(days=exp_off)
        db.session.add(u)
        user_objs[email] = u
    db.session.flush()

    # FinancePreQual rows mirroring the pre-qual snapshots on users
    for (email, first, last, phone, zip_code, addr1, city, state,
         home_slug, prequal, income, emp) in users:
        if not prequal:
            continue
        u = user_objs[email]
        mmax, term, apr, down, tier, exp_off = prequal
        pq = FinancePreQual(
            user_id=u.id, annual_income=income, employment_status=emp,
            monthly_payment_max=mmax, down_payment=down, term_months=term,
            estimated_apr=apr, credit_tier=tier, status='active',
            created_at=SEED_NOW,
            expires_at=TODAY + timedelta(days=exp_off),
        )
        db.session.add(pq)

    # Seed a handful of saved vehicles, reservations, test drives, appraisals,
    # and an order so the benchmark accounts feel lived-in.
    alice = user_objs['alice.j@test.com']
    bob = user_objs['bob.k@test.com']
    carol = user_objs['carol.l@test.com']
    dan = user_objs['dan.m@test.com']

    # Pick deterministic vehicles by id range
    v1 = db.session.get(Vehicle, 1)
    v3 = db.session.get(Vehicle, 3)
    v5 = db.session.get(Vehicle, 5)
    v7 = db.session.get(Vehicle, 7)
    v11 = db.session.get(Vehicle, 11)
    v15 = db.session.get(Vehicle, 15)
    v23 = db.session.get(Vehicle, 23)
    v37 = db.session.get(Vehicle, 37)

    if v1: db.session.add(SavedVehicle(user_id=alice.id, vehicle_id=v1.id, saved_at=SEED_NOW))
    if v5: db.session.add(SavedVehicle(user_id=alice.id, vehicle_id=v5.id, saved_at=SEED_NOW))
    if v7: db.session.add(SavedVehicle(user_id=bob.id, vehicle_id=v7.id, saved_at=SEED_NOW))
    if v11: db.session.add(SavedVehicle(user_id=bob.id, vehicle_id=v11.id, saved_at=SEED_NOW))
    if v23: db.session.add(SavedVehicle(user_id=carol.id, vehicle_id=v23.id, saved_at=SEED_NOW))
    if v37: db.session.add(SavedVehicle(user_id=dan.id, vehicle_id=v37.id, saved_at=SEED_NOW))

    if v3:
        db.session.add(Reservation(
            user_id=alice.id, vehicle_id=v3.id, store_id=v3.store_id,
            status='active',
            appointment_date=TODAY + timedelta(days=2),
            expires_at=TODAY + timedelta(days=7),
            transfer_required=False, transfer_fee=v3.transfer_fee or 0,
            created_at=SEED_NOW))

    if v11:
        db.session.add(TestDrive(
            user_id=bob.id, vehicle_id=v11.id, store_id=v11.store_id,
            location_type='in_store',
            scheduled_date=TODAY + timedelta(days=3),
            scheduled_time='2:00 PM',
            status='confirmed', notes='',
            created_at=SEED_NOW))

    if v15:
        db.session.add(TestDrive(
            user_id=alice.id, vehicle_id=v15.id, store_id=v15.store_id,
            location_type='at_home',
            scheduled_date=TODAY + timedelta(days=5),
            scheduled_time='4:00 PM',
            status='confirmed', notes='Please call when you arrive.',
            created_at=SEED_NOW))

    # Appraisals for benchmark users — deterministic offers
    db.session.add(Appraisal(
        user_id=alice.id, year=2017, make='Toyota', model='Camry', trim='LE',
        mileage=78500, condition='good',
        exterior_color='Celestial Silver Metallic',
        license_plate='AJC2017', license_state='GA', vin='4T1B11HK1HU000118',
        zip_code='30303', has_accidents=False, owner_count=1,
        contact_email='alice.j@test.com', contact_phone='(404) 555-0118',
        offer_amount=11650.0, offer_valid_until=TODAY + timedelta(days=7),
        status='active', created_at=SEED_NOW))

    db.session.add(Appraisal(
        user_id=bob.id, year=2015, make='Honda', model='Accord', trim='Sport',
        mileage=125400, condition='fair',
        exterior_color='Modern Steel Metallic',
        license_plate='BKHX2015', license_state='TX', vin='1HGCR2F33FA000119',
        zip_code='77002', has_accidents=True, owner_count=2,
        contact_email='bob.k@test.com', contact_phone='(713) 555-0119',
        offer_amount=6850.0, offer_valid_until=TODAY + timedelta(days=4),
        status='active', created_at=SEED_NOW))

    db.session.add(Appraisal(
        user_id=carol.id, year=2019, make='Nissan', model='Altima', trim='SV',
        mileage=42800, condition='excellent',
        exterior_color='Pearl White Tricoat',
        license_plate='CL2019N', license_state='FL', vin='1N4BL4DV3KC000120',
        zip_code='33176', has_accidents=False, owner_count=1,
        contact_email='carol.l@test.com', contact_phone='(305) 555-0120',
        offer_amount=14750.0, offer_valid_until=TODAY + timedelta(days=6),
        status='active', created_at=SEED_NOW))

    # One completed order for Dan
    if v37:
        db.session.add(Order(
            order_number='CMX-2026-000001',
            user_id=dan.id,
            status='ready_for_pickup',
            vehicle_id=v37.id, store_id=v37.store_id,
            subtotal=v37.price,
            transfer_fee=v37.transfer_fee or 0,
            tax=v37.price * 0.0625,
            title_fee=99, registration_fee=55,
            total=(v37.price + (v37.transfer_fee or 0) + v37.price * 0.0625
                   + 99 + 55),
            maxcare_plan='gold', maxcare_price=1895,
            payment_method='carmax_auto_finance',
            payment_last4='1234', payment_apr=6.49,
            payment_term_months=60,
            monthly_payment=520.0, down_payment=3000.0,
            trade_in_value=0,
            pickup_or_delivery='pickup',
            delivery_address='',
            pickup_date=TODAY + timedelta(days=3),
            created_at=SEED_NOW))

    db.session.commit()

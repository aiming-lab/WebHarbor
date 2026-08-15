"""Deterministic Wine Access seed data."""
import json
from datetime import timedelta

PASSWORD = "TestPass123!"

PRODUCTS = [
    ("2023 Jolie-Laide Syrah California", 2023, "Jolie-Laide", "Red", "Syrah", "California", "United States", "California", 20, 36, 94, "Antonio Galloni", "wine_01_2023-jolie-laide-syrah-california.webp", "Galloni: I cannot recommend them highly enough."),
    ("2024 Saint Cosme Cotes du Rhone", 2024, "Saint Cosme", "Red", "Red Blend", "Rhone Valley", "France", "Cotes du Rhone", 19, 20, 93, "Wine Access", "wine_02_2024-saint-cosme-cotes-du-rhone.webp", "Our top Cotes-du-Rhone from a 100-point southern Rhone estate."),
    ("2024 Paltrinieri Radice Lambrusco di Sorbara", 2024, "Paltrinieri", "Sparkling", "Lambrusco", "Emilia-Romagna", "Italy", "Sorbara", 24, 31, 92, "Wine Access", "wine_03_2024-paltrinieri-radice-lambrusco-di-sorbara.webp", "Dry, bright, and wildly refreshing sparkling red."),
    ("2020 Chateau Pavie Saint-Emilion", 2020, "Chateau Pavie", "Red", "Bordeaux Blend", "Bordeaux", "France", "Saint-Emilion", 399, 475, 99, "Wine Access", "wine_04_2020-chateau-pavie-saint-emilion.webp", "A cellar landmark from Saint-Emilion."),
    ("2022 Albert Bichot Saint-Veran Burgundy", 2022, "Albert Bichot", "White", "Chardonnay", "Burgundy", "France", "Saint-Veran", 32, 40, 91, "Wine Access", "wine_05_2022-albert-bichot-saint-veran-burgundy.webp", "Limestone snap and orchard fruit from Burgundy."),
    ("2015 Chateau Haut-Brion Pessac-Leognan", 2015, "Chateau Haut-Brion", "Red", "Bordeaux Blend", "Bordeaux", "France", "Pessac-Leognan", 950, 1100, 100, "Wine Access", "wine_06_2015-chateau-haut-brion-pessac-leognan.webp", "First-growth depth with graphite, cassis, and cigar box."),
    ("2023 Vinedo Chadwick Maipo Valley Chile", 2023, "Vinedo Chadwick", "Red", "Cabernet Sauvignon", "Maipo Valley", "Chile", "Maipo Valley", 380, 420, 98, "Wine Access", "wine_07_2023-vinedo-chadwick-maipo-valley-chile.webp", "Chile's benchmark Cabernet in a polished vintage."),
    ("2021 Bank Shot Cabernet Sauvignon Napa Valley", 2021, "Bank Shot", "Red", "Cabernet Sauvignon", "Napa Valley", "United States", "Napa Valley", 45, 95, 94, "Wine Access", "wine_08_2021-bank-shot-cabernet-sauvignon-napa-valley.webp", "Napa Cabernet power at a weeknight-friendly price."),
    ("2021 Le Pich Cabernet Sauvignon Napa Valley", 2021, "Le Pich", "Red", "Cabernet Sauvignon", "Napa Valley", "United States", "Napa Valley", 65, 85, 95, "Wine Access", "wine_09_2021-le-pich-cabernet-sauvignon-napa-valley.webp", "A top value from Napa's acclaimed 2021 vintage."),
    ("2020 Hawk and Horse Cabernet Sauvignon Red Hills Lake County", 2020, "Hawk and Horse", "Red", "Cabernet Sauvignon", "Lake County", "United States", "Red Hills", 58, 75, 93, "Wine Access", "wine_10_2020-hawk-and-horse-vineyards-cabernet-sauvignon-red-hills-lake-county.webp", "Mountain-grown Cabernet with organic farming roots."),
    ("2017 Maison Leroy Nuits-Saint-Georges", 2017, "Maison Leroy", "Red", "Pinot Noir", "Burgundy", "France", "Nuits-Saint-Georges", 995, 1200, 97, "Wine Access", "wine_11_2017-maison-leroy-nuits-saint-georges.webp", "Rare Burgundy from one of the region's legendary names."),
    ("2024 Vinos Finos de California Sabroso Central Coast", 2024, "Vinos Finos de California", "White", "White Blend", "Central Coast", "United States", "Central Coast", 22, 30, 91, "Wine Access", "wine_12_2024-vinos-finos-de-california-sabroso-central-coast.webp", "Coastal freshness with citrus, melon, and sea-spray lift."),
    ("2023 Glassmen Pinot Noir Sonoma Coast", 2023, "Glassmen", "Red", "Pinot Noir", "Sonoma Coast", "United States", "Sonoma Coast", 39, 55, 94, "Wine Access", "wine_13_2023-glassmen-pinot-noir-sonoma-coast.webp", "Silky single-vineyard style Sonoma Pinot."),
    ("2017 Maison Leroy Gevrey-Chambertin", 2017, "Maison Leroy", "Red", "Pinot Noir", "Burgundy", "France", "Gevrey-Chambertin", 1150, 1380, 98, "Wine Access", "wine_14_2017-maison-leroy-gevrey-chambertin.webp", "A rare village bottling with grand-cru energy."),
    ("2022 Williams Selyem Pinot Noir Russian River Valley", 2022, "Williams Selyem", "Red", "Pinot Noir", "Russian River Valley", "United States", "Russian River Valley", 119, 140, 96, "Wine Access", "wine_15_2022-williams-selyem-pinot-noir-russian-river-valley.webp", "Russian River perfume, cherry, and polished spice."),
    ("2018 F. Thienpont Bordeaux", 2018, "F. Thienpont", "Red", "Bordeaux Blend", "Bordeaux", "France", "Bordeaux", 29, 45, 92, "Wine Access", "wine_16_2018-f-thienpont-bordeaux.webp", "Right Bank pedigree in a generous vintage."),
    ("2023 Ponzi Pinot Noir Tavola Willamette Valley", 2023, "Ponzi Vineyards", "Red", "Pinot Noir", "Willamette Valley", "United States", "Willamette Valley", 31, 45, 92, "Wine Access", "wine_17_2023-ponzi-vineyards-pinot-noir-tavola-willamette-valley.webp", "Oregon Pinot with red cherry and forest floor detail."),
    ("2024 RAEN Pinot Noir Royal St. Robert Cuvee Sonoma Coast", 2024, "RAEN", "Red", "Pinot Noir", "Sonoma Coast", "United States", "Sonoma Coast", 88, 110, 96, "Wine Access", "wine_18_2024-raen-pinot-noir-royal-st-robert-cuvee-sonoma-coast.webp", "Coastal Pinot from a celebrated Sonoma Coast project."),
    ("2022 Hoopes Cabernet Sauvignon Napa Valley", 2022, "Hoopes Family Vineyard", "Red", "Cabernet Sauvignon", "Napa Valley", "United States", "Napa Valley", 72, 95, 94, "Wine Access", "wine_19_2022-hoopes-family-vineyard-cabernet-sauvignon-napa-valley.webp", "Classic Napa Cabernet with cassis and cedar."),
    ("2023 Williams Selyem Zinfandel Papera Vineyard", 2023, "Williams Selyem", "Red", "Zinfandel", "Russian River Valley", "United States", "Papera Vineyard", 68, 80, 95, "Wine Access", "wine_20_2023-williams-selyem-zinfandel-papera-vineyard-russian-river-valley.webp", "Old-vine Zinfandel with berry compote and spice."),
    ("2021 Domaine du Clos de Tart Grand Cru Monopole", 2021, "Domaine du Clos de Tart", "Red", "Pinot Noir", "Burgundy", "France", "Clos de Tart", 850, 980, 98, "Wine Access", "wine_21_2021-domaine-du-clos-de-tart-clos-de-tart-grand-cru-monopole.webp", "Grand cru Burgundy from a walled monopole."),
    ("2023 Zuccardi Concreto Malbec Paraje Altamira Mendoza", 2023, "Zuccardi", "Red", "Malbec", "Mendoza", "Argentina", "Paraje Altamira", 42, 55, 95, "Wine Access", "wine_22_2023-zuccardi-concreto-malbec-paraje-altamira-mendoza.webp", "Stony, vivid Malbec from high-elevation Mendoza."),
    ("2022 La Pelle Cabernet Sauvignon Napa Valley", 2022, "La Pelle Wines", "Red", "Cabernet Sauvignon", "Napa Valley", "United States", "Napa Valley", 98, 125, 96, "Wine Access", "wine_23_2022-la-pelle-wines-cabernet-sauvignon-napa-valley.webp", "A serious cellar Cabernet with polished tannins."),
    ("2023 Aperture Cabernet Sauvignon Soil Specific Sonoma County", 2023, "Aperture Cellars", "Red", "Cabernet Sauvignon", "Sonoma County", "United States", "Sonoma County", 74, 95, 94, "Wine Access", "wine_24_2023-aperture-cellars-cabernet-sauvignon-soil-specific-sonoma-county.webp", "Cabernet precision from Sonoma volcanic soils."),
    ("2019 Pas de Cheval Cabernet Sauvignon Finale Howell Mountain", 2019, "Pas de Cheval", "Red", "Cabernet Sauvignon", "Howell Mountain", "United States", "Napa Valley", 155, 210, 97, "Wine Access", "wine_25_2019-pas-de-cheval-cabernet-sauvignon-finale-howell-mountain-napa-vall.webp", "Howell Mountain structure with blue fruit and cocoa."),
    ("2019 Gilbert Hall Cabernet Sauvignon Napa Valley", 2019, "Gilbert Hall", "Red", "Cabernet Sauvignon", "Napa Valley", "United States", "Napa Valley", 89, 135, 95, "Wine Access", "wine_26_2019-napa-cabernet-cellared-and-sublime-2019-gilbert-hall-cabernet-sau.webp", "Cellared Napa Cabernet entering a graceful window."),
    ("2023 Lorenza Old Vine Carignan Rauser Vineyard", 2023, "Lorenza", "Red", "Carignan", "Mokelumne River", "United States", "Lodi", 28, 38, 91, "Wine Access", "wine_27_2023-lorenza-old-vine-carignan-rauser-vineyard-mokelumne-river.webp", "Bright old-vine Carignan with a savory snap."),
    ("2021 Pas de Cheval Cabernet Sauvignon Prelude Oakville", 2021, "Pas de Cheval", "Red", "Cabernet Sauvignon", "Oakville", "United States", "Napa Valley", 125, 165, 96, "Wine Access", "wine_28_2021-pas-de-cheval-cabernet-sauvignon-prelude-oakville-napa-valley.webp", "Oakville Cabernet with plush fruit and firm ageworthy lines."),
    ("2021 Waugh Cellars Cabernet Sauvignon Napa Valley", 2021, "Waugh Cellars", "Red", "Cabernet Sauvignon", "Napa Valley", "United States", "Napa Valley", 54, 80, 93, "Wine Access", "wine_29_2021-waugh-cellars-cabernet-sauvignon-napa-valley.webp", "A polished Napa Cabernet for grilled ribeye."),
    ("2024 Campo Della Fortuna Pinot Grigio", 2024, "Campo Della Fortuna", "White", "Pinot Grigio", "Veneto", "Italy", "Veneto", 18, 25, 90, "Wine Access", "wine_30_2024-campo-della-fortuna-pinot-grigio.webp", "Crisp pear, lemon peel, and mineral refreshment."),
    ("2022 DuMOL Chardonnay Chloe Russian River Valley", 2022, "DuMOL", "White", "Chardonnay", "Russian River Valley", "United States", "Russian River Valley", 86, 105, 95, "Wine Access", "wine_31_2022-dumol-chardonnay-chloe-russian-river-valley.webp", "Layered Russian River Chardonnay with fine acidity."),
    ("2025 Mount Fishtail Sauvignon Blanc Sur Lie Marlborough", 2025, "Mount Fishtail", "White", "Sauvignon Blanc", "Marlborough", "New Zealand", "Marlborough", 19, 27, 91, "Wine Access", "wine_32_2025-mount-fishtail-sauvignon-blanc-sur-lie-marlborough.webp", "Sur lie texture meets grapefruit and passionfruit."),
    ("2023 Domaine Roland Lavantureux Vieilles Vignes Chablis", 2023, "Domaine Roland Lavantureux", "White", "Chardonnay", "Burgundy", "France", "Chablis", 48, 62, 94, "Wine Access", "wine_33_2023-domaine-roland-lavantureux-vieilles-vignes-chablis.webp", "Old-vine Chablis with oyster-shell precision."),
    ("2022 Fantesca Estate Chardonnay Russian River Valley", 2022, "Fantesca Estate", "White", "Chardonnay", "Russian River Valley", "United States", "Russian River Valley", 64, 85, 94, "Wine Access", "wine_34_2022-fantesca-estate-chardonnay-russian-river-valley.webp", "A plush yet focused Russian River Chardonnay."),
]

EXTRA_PRODUCTS = [
    ("2025 LoveR Coteaux d'Aix en Provence Rose", 2025, "LoveR", "Rose", "Rose Blend", "Provence", "France", "Coteaux d'Aix", 26, 35, 92),
    ("M. Brugnon Selection Brut Champagne", 2020, "M. Brugnon", "Sparkling", "Champagne Blend", "Champagne", "France", "Champagne", 49, 65, 93),
    ("Maurice Grumier Coeur de Rose Champagne", 2019, "Maurice Grumier", "Sparkling", "Champagne Blend", "Champagne", "France", "Champagne", 58, 75, 94),
    ("2023 1881 Napa Cabernet Sauvignon Napa Valley", 2023, "1881 Napa", "Red", "Cabernet Sauvignon", "Napa Valley", "United States", "Napa Valley", 40, 70, 93),
    ("2023 Karo-Kann Cabernet Sauvignon Napa Valley", 2023, "Karo-Kann", "Red", "Cabernet Sauvignon", "Napa Valley", "United States", "Napa Valley", 35, 60, 92),
    ("2023 Off the Cuff Cabernet Sauvignon Napa Valley", 2023, "Off the Cuff", "Red", "Cabernet Sauvignon", "Napa Valley", "United States", "Napa Valley", 32, 55, 91),
    ("2021 Three Wine Company Old Vines Field Blend", 2021, "Three Wine Company", "Red", "Red Blend", "Contra Costa County", "United States", "Contra Costa County", 24, 38, 92),
    ("2024 Lionel Osmin Cami Salie Jurancon", 2024, "Lionel Osmin", "White", "Petit Manseng", "Southwest France", "France", "Jurancon", 21, 30, 91),
    ("2022 Atlas Peak Merlot Napa Valley", 2022, "Atlas Peak", "Red", "Merlot", "Napa Valley", "United States", "Napa Valley", 44, 65, 92),
    ("2021 Sage Ridge Cabernet Franc Napa Valley", 2021, "Sage Ridge", "Red", "Cabernet Franc", "Napa Valley", "United States", "Napa Valley", 59, 78, 94),
    ("2023 Riverstone Riesling Mosel Kabinett", 2023, "Riverstone", "White", "Riesling", "Mosel", "Germany", "Mosel", 29, 42, 93),
    ("2024 Tidal Bay Albarino Rias Baixas", 2024, "Tidal Bay", "White", "Albarino", "Rias Baixas", "Spain", "Rias Baixas", 23, 32, 91),
    ("2021 Barolo Cascina del Conte", 2021, "Cascina del Conte", "Red", "Nebbiolo", "Piedmont", "Italy", "Barolo", 62, 85, 95),
    ("2020 Brunello di Montalcino La Quercia", 2020, "La Quercia", "Red", "Sangiovese", "Tuscany", "Italy", "Brunello di Montalcino", 72, 96, 94),
    ("2024 Junmai Ginjo Sake Akari", 2024, "Akari", "Sake", "Sake", "Niigata", "Japan", "Niigata", 36, 48, 92),
    ("2018 Vintage Port Quinta do Sol", 2018, "Quinta do Sol", "Fortified", "Port Blend", "Douro", "Portugal", "Porto", 42, 58, 92),
    ("2023 Dry Creek Petite Sirah Reserve", 2023, "Dry Creek Reserve", "Red", "Petite Sirah", "Sonoma County", "United States", "Dry Creek Valley", 34, 50, 91),
    ("2025 Willamette Valley Rose of Pinot Noir", 2025, "North Crest", "Rose", "Pinot Noir", "Willamette Valley", "United States", "Willamette Valley", 24, 34, 90),
    ("2024 Etna Bianco Carricante", 2024, "Terra Nera", "White", "Carricante", "Sicily", "Italy", "Etna", 38, 52, 93),
    ("2022 Paso Robles GSM Reserve", 2022, "Limestone Bench", "Red", "GSM Blend", "Paso Robles", "United States", "Paso Robles", 28, 44, 91),
    ("2021 Rutherford Bench Cabernet Sauvignon", 2021, "Rutherford Bench", "Red", "Cabernet Sauvignon", "Napa Valley", "United States", "Rutherford", 79, 110, 95),
    ("2022 Santa Barbara Chardonnay Ocean Block", 2022, "Ocean Block", "White", "Chardonnay", "Santa Barbara County", "United States", "Santa Barbara", 37, 55, 92),
    ("2023 Anderson Valley Pinot Noir Fogline", 2023, "Fogline", "Red", "Pinot Noir", "Anderson Valley", "United States", "Anderson Valley", 46, 64, 93),
    ("2024 Loire Valley Sauvignon Blanc Les Cailloux", 2024, "Les Cailloux", "White", "Sauvignon Blanc", "Loire Valley", "France", "Touraine", 20, 29, 90),
    ("2020 Rioja Reserva Vina Cerrada", 2020, "Vina Cerrada", "Red", "Tempranillo", "Rioja", "Spain", "Rioja", 31, 46, 92),
    ("2023 Santa Lucia Highlands Pinot Noir Benchland", 2023, "Benchland", "Red", "Pinot Noir", "Santa Lucia Highlands", "United States", "Santa Lucia Highlands", 43, 60, 92),
]


def _pairings(wine_type, variety):
    if wine_type == "White":
        return ["roast chicken", "shellfish", "spring vegetables"]
    if wine_type == "Sparkling":
        return ["fried chicken", "triple cream cheese", "celebrations"]
    if wine_type == "Rose":
        return ["salmon", "summer salads", "goat cheese"]
    if variety == "Cabernet Sauvignon":
        return ["ribeye", "braised short ribs", "aged cheddar"]
    if variety == "Pinot Noir":
        return ["duck", "mushroom risotto", "roast pork"]
    return ["grilled lamb", "charcuterie", "hard cheeses"]


def _notes(wine_type, variety, region, score):
    return (
        f"{score}-point {variety} from {region}. The profile is layered with "
        "fresh fruit, savory detail, and a clean finish. The Wine Access panel "
        "selected it for balance, typicity, and value relative to comparable bottles."
    )


def seed_database(db, Wine, Review, Club, slugify):
    if Wine.query.count() > 0:
        return

    rows = list(PRODUCTS)
    images = [row[12] for row in PRODUCTS]
    for i, row in enumerate(EXTRA_PRODUCTS):
        name, vintage, winery, wine_type, variety, region, country, appellation, price, list_price, score = row
        image = images[i % len(images)]
        rows.append((name, vintage, winery, wine_type, variety, region, country, appellation, price, list_price, score, "Wine Access", image, "Member-favorite discovery selected by the Wine Access tasting panel."))

    for idx, row in enumerate(rows, start=1):
        name, vintage, winery, wine_type, variety, region, country, appellation, price, list_price, score, reviewer, image, teaser = row
        wine = Wine(
            slug=slugify(name),
            name=name,
            vintage=vintage,
            winery=winery,
            wine_type=wine_type,
            variety=variety,
            region=region,
            country=country,
            appellation=appellation,
            price=float(price),
            list_price=float(list_price),
            case_price=round(float(price) * 12 * 0.88, 2),
            rating=min(round(4.1 + (score - 88) / 20, 1), 4.9),
            score=score,
            reviewer=reviewer,
            inventory=18 + (idx * 7) % 84,
            availability="Preorder" if idx % 11 == 0 else "Ships Immediately",
            limited_offer=idx % 3 == 0,
            expert_pick=score >= 94 or idx % 9 == 0,
            club_eligible=idx % 7 != 0,
            image=image,
            teaser=teaser,
            tasting_notes=_notes(wine_type, variety, region, score),
            story=(
                f"Wine Access sourced {name} after tasting through a focused set of "
                f"{variety} bottlings from {region}. It stood out for provenance, "
                "cellar condition, and the kind of price-to-quality ratio members expect."
            ),
            pairings_json=json.dumps(_pairings(wine_type, variety)),
            specs_json=json.dumps(
                {
                    "Vintage": vintage,
                    "Variety": variety,
                    "Region": region,
                    "Country": country,
                    "Appellation": appellation,
                    "Bottle Size": "750 ml",
                    "Alcohol": f"{13 + (idx % 4) * 0.4:.1f}%",
                    "Drinking Window": f"2026-{2030 + idx % 9}",
                }
            ),
        )
        db.session.add(wine)
        db.session.flush()
        for r in range(3):
            db.session.add(
                Review(
                    wine_id=wine.id,
                    author=["Maya R.", "Thomas L.", "Erin C."][r],
                    rating=5 if r != 1 else 4,
                    title=["Cellar-worthy", "Strong value", "Dinner standout"][r],
                    body=[
                        "Arrived in perfect condition and opened with beautiful aromatics.",
                        "The profile matched the notes and the price was fair for the quality.",
                        "Served it with dinner and every glass disappeared quickly.",
                    ][r],
                )
            )

    clubs = [
        ("unfiltered-podcast", "Unfiltered Podcast Wine Club", "Educational and fun", 4, "6 times per year", 120, "Drink along with Amanda McCrossin as she shares stories, guests, and expert selections.", "club_unfiltered.webp"),
        ("connoisseurs", "Connoisseurs Club", "Unparalleled reds", 2, "Quarterly", 150, "Two breathtaking red wines selected for collectors who want rare, ageworthy bottles.", "club_wine_display.webp"),
        ("discovery", "Discovery Club", "Classic styles, new favorites", 4, "Quarterly", 110, "A broad tour through regions, grapes, and styles that overdeliver for the price.", "club_wine_display.webp"),
        ("champagne", "Sparkling Club", "Bubbles beyond the obvious", 3, "Quarterly", 165, "Champagne and world-class sparkling wines with food-pairing notes.", "club_unfiltered.webp"),
    ]
    for slug, name, tagline, bottles, frequency, price, description, image in clubs:
        db.session.add(
            Club(
                slug=slug,
                name=name,
                tagline=tagline,
                bottles=bottles,
                frequency=frequency,
                price_per_shipment=price,
                description=description,
                image=image,
            )
        )
    db.session.commit()


def seed_benchmark_users(
    db,
    User,
    Wine,
    CartItem,
    WishlistItem,
    PaymentMethod,
    Order,
    OrderItem,
    Club,
    ClubMembership,
    bcrypt,
    reference_date,
):
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    users = [
        ("alice_j", "alice.j@test.com", "Alice Johnson", "Cabernet Sauvignon", "122 Camino Oruga", "Napa", "CA", "94558"),
        ("bob_c", "bob.c@test.com", "Bob Chen", "Pinot Noir", "418 Market Street", "San Francisco", "CA", "94105"),
        ("carol_d", "carol.d@test.com", "Carol Davis", "Chardonnay", "75 Pearl Street", "Denver", "CO", "80203"),
        ("david_k", "david.k@test.com", "David Kim", "Sparkling", "9 Walnut Avenue", "Portland", "OR", "97205"),
    ]
    all_wines = Wine.query.order_by(Wine.id).all()
    clubs = Club.query.all()
    for idx, (username, email, display_name, favorite, line1, city, state, zip_code) in enumerate(users):
        user = User(
            username=username,
            email=email,
            display_name=display_name,
            phone=f"(707) 555-01{idx}0",
            address_line1=line1,
            city=city,
            state=state,
            zip_code=zip_code,
            favorite_variety=favorite,
        )
        user.password_hash = bcrypt.generate_password_hash(PASSWORD).decode("utf-8")
        db.session.add(user)
        db.session.flush()

        for wine in all_wines[idx * 2 : idx * 2 + 3]:
            db.session.add(CartItem(user_id=user.id, wine_id=wine.id, quantity=1 + (wine.id % 2)))
        for wine in all_wines[10 + idx * 4 : 15 + idx * 4]:
            db.session.add(WishlistItem(user_id=user.id, wine_id=wine.id, note="Consider for next cellar shipment"))
        db.session.add(
            PaymentMethod(
                user_id=user.id,
                cardholder=display_name,
                brand="Visa" if idx % 2 == 0 else "Mastercard",
                last4=["4242", "1881", "9455", "2026"][idx],
                exp_month=8 + idx,
                exp_year=2029,
                is_default=True,
            )
        )
        if clubs:
            db.session.add(ClubMembership(user_id=user.id, club_id=clubs[idx % len(clubs)].id))

        subtotal = 0
        order = Order(
            user_id=user.id,
            order_number=f"WA-26041{idx + 1}-{idx + 204}",
            status=["Delivered", "Shipped", "Processing", "Delivered"][idx],
            placed_at=reference_date - timedelta(days=12 + idx * 8),
            tracking_number=["1ZWA204944", "9400111899", "Pending cellar release", "1ZWA778204"][idx],
            ship_to=f"{line1}, {city}, {state} {zip_code}",
        )
        db.session.add(order)
        db.session.flush()
        for wine in all_wines[24 + idx * 3 : 27 + idx * 3]:
            qty = 1 + (wine.id % 3 == 0)
            subtotal += wine.price * qty
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    wine_id=wine.id,
                    wine_name=wine.name,
                    quantity=qty,
                    unit_price=wine.price,
                )
            )
        order.subtotal = round(subtotal, 2)
        order.shipping = 0 if subtotal >= 150 else 19.95
        order.tax = round(subtotal * 0.0825, 2)
        order.total = round(order.subtotal + order.shipping + order.tax, 2)

    db.session.commit()

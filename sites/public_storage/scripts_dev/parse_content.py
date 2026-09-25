"""Build site_content.json from all harvested static pages."""
import json, pathlib, re, html as htmllib

HARVEST = HARVEST
OUT = HARVEST / "pages"

def clean_text(s):
    s = htmllib.unescape(s or "")
    s = re.sub(r'<script.*?</script>', ' ', s, flags=re.S)
    s = re.sub(r'<style.*?</style>', ' ', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '\n', s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n\s*\n+', '\n', s)
    return s.strip()

def paras(html, minlen=50, limit=20):
    html = re.sub(r'<script.*?</script>', ' ', html, flags=re.S)
    html = re.sub(r'<style.*?</style>', ' ', html, flags=re.S)
    out = []
    for m in re.finditer(r'<p[^>]*>(.*?)</p>', html, re.S):
        t = clean_text(m.group(1))
        if len(t) >= minlen and '{' not in t[:40]:
            out.append(t)
        if len(out) >= limit:
            break
    return out

content = {}

# ---- storage type pages
TYPE_PAGES = {
    "self_storage": ("self-storage", "Self Storage"),
    "24hr": ("self-storage/24-hour-storage", "24 Hour Self Storage"),
    "driveup": ("self-storage/drive-up-storage", "Drive Up Access Storage"),
    "business": ("business-storage", "Business Storage"),
    "vehicle": ("vehicle-car-rv-storage", "Vehicle & RV Storage"),
    "boat": ("boat-storage", "Boat Storage"),
    "climate": ("climate-controlled-storage", "Climate Controlled Storage"),
    "indoor": ("indoor-storage", "Indoor Storage"),
}
type_pages = {}
for key, (slug, label) in TYPE_PAGES.items():
    html = (OUT / f"{key}.html").read_text()
    d = {"slug": slug, "label": label}
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
    d["h1"] = clean_text(m.group(1)) if m else label
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    d["title"] = clean_text(m.group(1)) if m else label
    d["paragraphs"] = paras(html, 60, 16)
    h2s = [clean_text(h) for h in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.S)]
    d["h2s"] = [h for h in h2s if h][:14]
    type_pages[key] = d
content["type_pages"] = type_pages

# ---- blog articles
articles = []
for f in sorted(OUT.glob("article_*.html"), key=lambda p: int(p.stem.split("_")[1])):
    html = f.read_text()
    d = {}
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
    d["title"] = clean_text(m.group(1)) if m else None
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    d["page_title"] = clean_text(m.group(1)) if m else None
    m = re.search(r'datetime="([\d-]+)', html)
    d["date"] = m.group(1) if m else None
    # category from URL json
    d["paragraphs"] = paras(html, 60, 14)
    # hero image
    m = re.search(r'<img[^>]+src="(https://publicstorage\.blog/wp-content/[^"]+)"', html)
    if not m:
        m = re.search(r'<img[^>]+src="(https://images\.publicstorage\.com/[^"]+)"', html)
    d["image"] = m.group(1) if m else None
    # url from articles.json list
    articles.append(d)
urls = json.loads((HARVEST/"articles.json").read_text().replace("'", '"'))
for i, u in enumerate(urls):
    if i < len(articles):
        articles[i]["url"] = u
        m = re.search(r'/blog/([a-z-]+)/([a-z0-9-]+)\.html', u)
        if m:
            articles[i]["category"] = m.group(1)
            articles[i]["slug"] = m.group(2)
content["blog_articles"] = [a for a in articles if a.get("slug") and a.get("paragraphs")]
print("articles:", len(content["blog_articles"]))

# ---- help center
html = (OUT/"help_home.html").read_text()
d = {}
m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
d["h1"] = clean_text(m.group(1)) if m else None
topics = re.findall(r'href="(https://help\.publicstorage\.com/[^"]+)"[^>]*>([^<]+)<', html)
d["topics"] = [{"url": u, "label": t.strip()} for u, t in topics if len(t.strip()) > 3][:16]
content["help_center"] = d
print("help topics:", len(d["topics"]))

# ---- homepage copy (from live text capture)
home_txt = (HARVEST/"home_text.txt").read_text()
content["home_copy"] = {
    "hero_heading": "Skip the counter & go straight to your space.",
    "hero_sub": "Save up to",
    "hero_discount": "40% OFF",
    "hero_cta": "Easy Online Rental",
    "nearby_heading": "Just think of us as an extension of your home.",
    "nearby_sub": "With more locations nationwide than any other self-storage company, we're always just around the corner. Here are some locations in your neighborhood:",
    "process_heading": "Here's how the self-storage process works.",
    "process_steps": [
        {"title": "Get Started", "body": "Find a location. Start by searching for storage near you. With thousands of locations nationwide, we're always just around the corner."},
        {"title": "Reserve your unit", "body": "Reserve your unit for free with no obligation, and complete your rental online to save time on move-in day."},
        {"title": "Move in", "body": "Find your space and move on in! (Pro tip: Download the Public Storage app to open make move-in a breeze with easy gate access and more!)"},
    ],
    "fifty_heading": "After 50 years, you learn what people want.",
    "fifty_bullets": [
        "Free reservations", "No long-term commitment", "Convenient access hours",
        "Trusted Nationwide Since 1972", "Climate-controlled units", "Variety of unit sizes",
    ],
    "sizeguide_heading": "Having trouble imagining what a 5'x5' looks like?",
    "sizeguide_sub": "We'll help you find the right size self-storage unit so you can make sure you're getting the most for your money.",
    "sizeguide_cta": "View the Size Guide",
    "locations_heading": "THE MOST LOCATIONS NATIONWIDE",
    "locations_sub": "That means you can pick up your surfboard for the morning swell and return it by noon.",
    "testimonials_heading": "What's it like to store with us? Ask them.",
    "testimonials": [
        {"name": "Eva F.", "quote": "eRental made it possible to search for a unit and complete my transaction remotely while out of town."},
        {"name": "Charles K.", "quote": "I filled it out (eRental) in the parking lot and got a spot in like 10 minutes."},
        {"name": "Gary G.", "quote": "Company reputation is excellent. Location is ideal for my needs. Easy contactless eRental process, end to end."},
    ],
    "seo_paragraph": "Public Storage is the leading provider of storage units for your personal, business and vehicle needs with thousands of locations nationwide. We offer a wide variety of units and sizes available with no obligation and no long-term commitment. Call today at 800-688-8057 for a free reservation and get your first month's rent for just $1.",
    "app_banner": {"heading": "Manage your space with your phone.", "bullets": ["Open Gates & Doors", "Pay Bills", "Manage Your Account"]},
    "awards_heading": "Trusted nationwide by customers and team members!",
    "awards_sub": "We're honored to receive these awards from Comparably, based on the ratings and feedback from our very own team.",
}

# ---- size guide hub (from size_guide.html)
sg_html = pathlib.Path("/tmp/ps_recon/size_guide.html").read_text()
sg = {}
m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
sg["h1"] = "Storage Size Guide"
sg["intro"] = "Not sure which storage unit fits your needs? We've got you. This self-storage guide helps you visualize the perfect size, features and packing style for your belongings."
# category cards: text pairs from the size guide page
cards = re.findall(r'Similar to ([^.<]+)[.]?', sg_html)
sg["comparison_chart"] = [
    {"size": "Locker", "sqft": "25", "cubic": "100", "fits": "Storage Closet - Reduced Height"},
    {"size": "5'x5'", "sqft": "25", "cubic": "200", "fits": "Storage Closet"},
    {"size": "5'x10'", "sqft": "50", "cubic": "400", "fits": "Studio Apartment"},
    {"size": "5'x15'", "sqft": "75", "cubic": "600", "fits": "1 Bedroom"},
    {"size": "10'x10'", "sqft": "100", "cubic": "800", "fits": "2 Bedrooms"},
    {"size": "10'x15'", "sqft": "150", "cubic": "1,200", "fits": "2 Bedroom home"},
    {"size": "10'x20'", "sqft": "200", "cubic": "1,600", "fits": "3 Bedroom home"},
    {"size": "10'x25'", "sqft": "250", "cubic": "2,000", "fits": "4 Bedroom home"},
    {"size": "Up to 20'", "sqft": "—", "cubic": "—", "fits": "Most Cars"},
    {"size": "Up to 35'", "sqft": "—", "cubic": "—", "fits": "Most RVs & Boats"},
    {"size": "Up to 50'", "sqft": "—", "cubic": "—", "fits": "Most Trailers"},
]
sg["size_cards"] = [
    {"key": "lockers", "label": "Lockers", "blurb": "Similar to a small walk-in closet with reduced height", "desc": "Need a little extra room in your home or garage? Our budget-friendly lockers come in a variety of shapes and sizes, perfect for storing compact items that don't require much height or space.", "right_for": ["Small household items", "Travel bags", "Seasonal clothing or shoes", "Sports gear or equipment"]},
    {"key": "5x5", "label": "Small 5'x5'", "blurb": "Similar to a small walk-in closet.", "right_for": ["Small household items", "Travel bags", "Seasonal clothing or shoes", "Sports gear or equipment"]},
    {"key": "5x10", "label": "Small 5'x10'", "blurb": "Similar to a half bathroom or large shed.", "right_for": ["Studio apartment furniture", "Boxes and small items", "Bicycles or sports equipment", "Seasonal items"]},
    {"key": "5x15", "label": "Medium 5'x15'", "blurb": "Similar to a large walk-in closet.", "right_for": ["Full bedroom furniture", "Small apartment contents", "Boxes and small items", "Appliances"]},
    {"key": "10x10", "label": "Medium 10'x10'", "blurb": "Similar to a standard one-car garage floor cut in half.", "right_for": ["Two bedrooms of furniture", "Small apartment contents", "Appliances and boxes", "Small furniture"]},
    {"key": "10x15", "label": "Large 10'x15'", "blurb": "Similar to a large bedroom.", "right_for": ["Two bedroom home contents", "Large furniture", "Appliances and boxes", "Small boats or motorcycles"]},
    {"key": "10x20", "label": "Large 10'x20'", "blurb": "Similar to a standard one-car garage.", "right_for": ["Three bedroom home contents", "Large furniture", "Appliances and boxes", "Small boats or vehicles"]},
    {"key": "10x25", "label": "Large 10'x25'", "blurb": "Larger than a standard one-car garage.", "right_for": ["Four bedroom home contents", "Large furniture", "Appliances and boxes", "Vehicles or small boats"]},
    {"key": "veh20", "label": "Up to 20'", "blurb": "Fits most cars.", "right_for": ["Most Cars", "Small trucks", "Small trailers"]},
    {"key": "veh35", "label": "Up to 35'", "blurb": "Fits most RVs and boats.", "right_for": ["Most RVs & Boats", "Campers", "Small trailers"]},
    {"key": "veh50", "label": "Up to 50'", "blurb": "Fits most trailers.", "right_for": ["Most Trailers", "Large RVs", "Large boats"]},
]
sg["tips"] = [
    {"title": "Make a List", "body": "Before choosing a unit, make a list of everything you plan to store. Large furniture, appliances, boxes, and oddly shaped items can impact how much space you'll need."},
    {"title": "Get a Sense of Space", "body": "Think beyond individual items and consider how much space everything takes up together. A stack of moving boxes can fill a unit faster than you might expect."},
    {"title": "Use Our Size Guide", "body": "Compare your belongings to the unit examples above. Matching your items to a recommended size can help you narrow your options quickly."},
    {"title": "Declutter Before You Store", "body": "Take a few minutes to sort through your stuff before packing. Storing only what you need can help you choose a smaller unit and stay organized."},
    {"title": "Plan for Access", "body": "Need to grab holiday decor, business inventory, or sports equipment throughout the year? Create walkways in your unit for easy access to your items."},
]
content["size_guide"] = sg

pathlib.Path(str(HARVEST) + "/site_content.json").write_text(json.dumps(content, indent=1))
print("saved site_content.json:", len(json.dumps(content))//1024, "KB")

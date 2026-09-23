"""Carnival footer link map (captured from the upstream footer, 2026-09-22).
Links are re-pointed at the mirror's real pages so every footer link resolves."""


def _map_links(pairs, fallback="/help"):
    return [(label, href if href else fallback) for label, href in pairs]


FOOTER_COLUMNS = [
    {"heading": "Plan A Cruise", "links": [
        ("Today's Deals", "/cruise-deals"),
        ("Search Cruises", "/cruise-search"),
        ("Family Cruises", "/cruise-search"),
        ("Funtastic Holiday Cruises", "/cruise-search"),
        ("Carnival Journeys", "/cruise-search"),
        ("Weddings & Occasions", "/help"),
        ("Charters, Meetings & Incentives", "/help"),
        ("Themed Cruises", "/cruise-search"),
        ("Personal Vacation Planners", "/about-carnival/contact-us"),
        ("Travel Agent Finder", "/help"),
        ("Carnival Rewards", "/carnival-rewards"),
        ("Carnival Rewards Mastercard", "/carnival-rewards"),
        ("Financing Powered By Flex Pay", "/financing"),
        ("Auto Pay", "/financing"),
        ("Gift Cards", "/help"),
        ("Carnival Vacation Protection", "/help"),
        ("Away We Go Blog", "/help"),
    ]},
    {"heading": "Cruise Destinations", "links": [
        ("Paradise Collection", "/cruise-search?cruisedeals=paradisecollection"),
        ("Caribbean Cruises", "/cruise-to/caribbean-cruises"),
        ("Bahamas Cruises", "/cruise-to/bahamas-cruises"),
        ("Mexico Cruises", "/cruise-to/mexico-cruises"),
        ("Alaska Cruises", "/cruise-to/alaska-cruises"),
        ("Hawaii Cruises", "/cruise-to/hawaii-cruises"),
        ("Europe Cruises", "/cruise-to/europe-cruises"),
        ("Bermuda Cruises", "/cruise-to/bermuda-cruises"),
        ("Panama Canal Cruises", "/cruise-to/panama-canal-cruises"),
        ("Canada & New England Cruises", "/cruise-to/canada-new-england-cruises"),
        ("Greenland & Canada Cruises", "/cruise-to/canada-new-england-cruises"),
        ("South America Cruises", "/cruise-to/south-america-cruises"),
        ("Transatlantic Cruises", "/cruise-to/transatlantic-cruises"),
        ("Transpacific Cruises", "/cruise-to/transpacific-cruises"),
        ("Australia Cruises", "/cruise-to/australia-cruises"),
    ]},
    {"heading": "Already Booked", "links": [
        ("Manage My Cruises", "/booked/manage"),
        ("Shore Excursions", "/shore-excursions"),
        ("Shore Excursions Best Price Guarantee", "/shore-excursions"),
        ("Group Shore Excursions", "/shore-excursions"),
        ("Beverage Packages", "/drink-packages"),
        ("Internet Plans", "/internet-plans"),
        ("In-Room Gifts & Shopping", "/help"),
        ("Spa & Salon Services", "/spa"),
        ("Fly2Fun", "/help"),
        ("Airport Transportation", "/help"),
        ("Carnival HUB App", "/help"),
    ]},
    {"heading": "Customer Service", "links": [
        ("FAQs", "/help"),
        ("Contact Us", "/about-carnival/contact-us"),
        ("Post-Cruise Inquiries", "/help"),
        ("Guests with Disabilities", "/help"),
        ("Lowest Price Guarantee", "/help"),
        ("Early Saver Price Protection Form", "/help"),
        ("Legal Notices For EU & UK Guests", "/help"),
        ("Consumer Health Data Privacy Notice", "/help"),
        ("Your Privacy Choices", "/help"),
    ]},
    {"heading": "About Carnival", "links": [
        ("About Us", "/about-carnival/about-us"),
        ("Cruise Ticket Contract Terms", "/help"),
        ("Passenger Bill of Rights", "/help"),
        ("Safety and Security", "/help"),
        ("Slavery Statement", "/about-carnival/about-us"),
        ("Carnival's Values", "/about-carnival/about-us"),
        ("Business Ethics", "/about-carnival/about-us"),
        ("In the Community", "/about-carnival/about-us"),
    ]},
]

FOOTER_BOTTOM_LINKS = [
    ("Legal Notices", "/help"),
    ("Privacy & Cookies", "/help"),
    ("Careers", "/about-carnival/about-us"),
    ("Travel Partners", "/help"),
    ("Newsroom", "/help"),
    ("Site Map", "/help"),
]

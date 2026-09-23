"""Marketing / company landing pages for the FlightAware mirror.

These are thin, factual landing pages for the upstream navigation and footer
destinations that are part of the flightaware.com site chrome (Products,
Industries, ADS-B hardware, Company) but are outside the mirrored functional
core (flight tracking, airport activity, photos, squawks, accounts).

Copy is factual, describing the real FlightAware products these pages
document (taglines as published on flightaware.com), plus links into the
functional mirror sections. No invented claims; no marketing copy beyond
what upstream itself publishes.
"""

# path -> (page_title, panel_head, body_paragraphs[list], explore_links[list])
MARKETING_PAGES = {
    "/commercial/aeroapi/": (
        "AeroAPI",
        "AeroAPI",
        ["AeroAPI is FlightAware's on-demand flight status and tracking data API. It is a "
         "robust, query-based API giving developers access to a huge amount of FlightAware's "
         "current and historical data, with real-time alerting on the flight events that "
         "matter most: departure, arrival, cancellation and flight hold detection.",
         "AeroAPI also provides access to FlightAware Foresight predictive technology, which "
         "combines historical and real-time aviation data with weather data to deliver "
         "predictive insights across nearly every flight on the planet."],
        [("/live/", "Live Flight Tracker"), ("/miserymap/", "MiseryMap"),
         ("/account/premium/", "Premium Subscriptions")]),
    "/commercial/firehose/": (
        "FlightAware Firehose",
        "FlightAware Firehose",
        ["FlightAware Firehose is a real-time, historical and predictive flight data "
         "streaming feed for enterprise integration. Tap into the data feed inside "
         "FlightAware Firehose to access the status and information for all flights on the "
         "ground and in the air."],
        [("/adsb/stats/", "ADS-B Statistics"), ("/live/", "Live Flight Tracker"),
         ("/commercial/aeroapi/", "AeroAPI")]),
    "/commercial/foresight/": (
        "FlightAware Foresight",
        "FlightAware Foresight",
        ["FlightAware Foresight increases operational efficiency gate-to-gate with "
         "predictive technology. Foresight harnesses robust historical and real-time "
         "aviation data, weather data and advanced machine learning to deliver predictive "
         "insights that optimize operations and anticipate risk across nearly every flight "
         "on the planet."],
        [("/live/airport/delays/", "Worldwide airport delays"),
         ("/live/cancelled/", "Delay and cancellation statistics"),
         ("/miserymap/", "MiseryMap")]),
    "/commercial/reports/": (
        "Rapid Reports and Custom Reports",
        "Rapid Reports and Custom Reports",
        ["FlightAware Rapid Reports generates instant aviation reports, and Custom Reports "
         "delivers the insights you request the way you want them: operational reporting for "
         "airports, airlines, FBOs and fleet operators built from FlightAware's flight "
         "tracking archive."],
        [("/live/airport/delays/", "Worldwide airport delays"),
         ("/live/cancelled/", "Delay and cancellation statistics")]),
    "/commercial/integrated-maps/": (
        "Integrated Mapping Solutions",
        "Integrated Mapping Solutions",
        ["FlightAware Integrated Mapping Solutions provides comprehensive flight tracking "
         "mapping for applications and websites: live aircraft maps, airport activity maps "
         "and route maps that can be embedded in your own product."],
        [("/miserymap/", "MiseryMap"), ("/live/airport/random", "Airport activity"),
         ("/about/", "About FlightAware")]),
    "/commercial/aviator/": (
        "FlightAware Aviator",
        "FlightAware Aviator",
        ["FlightAware Aviator is a personalized flight-following experience with unlimited "
         "alerts and more: the premium subscription experience for pilots and aviation "
         "enthusiasts, tailored to the flights and airports you follow."],
        [("/account/premium/", "Premium Subscriptions"), ("/account/", "My FlightAware"),
         ("/live/", "Live Flight Tracker")]),
    "/commercial/global/": (
        "FlightAware Global",
        "FlightAware Global",
        ["FlightAware Global is secure, private fleet tracking. Keep track of every aircraft "
         "in your private fleet — including helicopters — with customized monitoring "
         "packages tailored to operations of any size."],
        [("/account/", "My FlightAware"), ("/live/fleet/", "Browse by Operator"),
         ("/account/premium/", "Premium Subscriptions")]),
    "/commercial/fbo-toolbox/": (
        "FlightAware FBO Toolbox",
        "FlightAware FBO Toolbox",
        ["The FlightAware FBO Toolbox provides comprehensive flight tracking to enhance "
         "your FBO operations and increase sales: arrive/departure boards, traffic "
         "analytics and market intelligence for fixed-base operators."],
        [("/live/airport/random", "Airport activity"),
         ("/live/airport/delays/", "Worldwide airport delays")]),
    "/commercial/tv/": (
        "FlightAware TV",
        "FlightAware TV&trade;",
        ["FlightAware TV shows full-screen flight tracking maps for operators or FBOs: a "
         "live view of aircraft and airport activity designed for lobby and operations "
         "room displays."],
        [("/miserymap/", "MiseryMap"), ("/live/", "Live Flight Tracker")]),
    "/commercial/globalbeacon/": (
        "GlobalBeacon",
        "GlobalBeacon",
        ["GlobalBeacon is FlightAware's GADSS-compliant global flight tracking and alerting "
         "for airlines and aircraft operators, supporting the ICAO Global Aeronautical "
         "Distress and Safety System (GADSS) standard for global flight tracking."],
        [("/live/", "Live Flight Tracker"), ("/about/data-sources/", "Data Sources")]),
    "/commercial/advertising/": (
        "Advertise With Us",
        "Advertise With Us",
        ["FlightAware reaches millions of aviation enthusiasts and professionals every "
         "month. To learn about advertising on flightaware.com and in FlightAware "
         "products, contact the FlightAware sales team."],
        [("/about/contact/", "Contact Us"), ("/about/", "About FlightAware")]),
    "/industries/airports/": (
        "FlightAware for Airports",
        "Airports",
        ["FlightAware provides airports with tailored flight tracking solutions: airport "
         "activity boards, delay and cancellation statistics, and operational reporting "
         "built from the worldwide flight tracking network."],
        [("/live/airport/random", "Airport activity"),
         ("/live/airport/delays/", "Worldwide airport delays"),
         ("/miserymap/", "MiseryMap")]),
    "/industries/airlines/": (
        "FlightAware for Airlines",
        "Airlines",
        ["FlightAware provides airlines with real-time, historical and predictive flight "
         "tracking, GADSS-compliant global tracking and operational analytics for every "
         "flight in the network."],
        [("/live/fleet/", "Browse by Operator"), ("/live/cancelled/", "Cancellations"),
         ("/commercial/globalbeacon/", "GlobalBeacon")]),
    "/industries/business/": (
        "FlightAware for Business Aviation",
        "Business",
        ["FlightAware is the industry standard flight tracking platform for business "
         "aviation owners and operators, with secure private fleet tracking and "
         "personalized flight-following with unlimited alerts."],
        [("/commercial/global/", "FlightAware Global"),
         ("/account/premium/", "Premium Subscriptions")]),
    "/industries/government/": (
        "FlightAware for Government",
        "Government",
        ["FlightAware provides government and public safety agencies with worldwide "
         "flight tracking data and alerting built on the FlightAware network of ADS-B "
         "ground stations and data partners."],
        [("/adsb/stats/", "ADS-B Statistics"), ("/about/data-sources/", "Data Sources")]),
    "/industries/manufacturer/": (
        "FlightAware for Manufacturers",
        "Manufacturer",
        ["FlightAware provides aircraft and avionics manufacturers with fleet and aircraft "
         "usage insight from the worldwide flight tracking network."],
        [("/live/aircrafttype/", "Browse by Aircraft Type"),
         ("/commercial/aeroapi/", "AeroAPI")]),
    "/industries/travel/": (
        "FlightAware for Travel",
        "Travel",
        ["FlightAware helps travelers and the travel industry with live flight tracking, "
         "airport activity, delays and cancellations, and MiseryMap — the live "
         "visualization of flight delays."],
        [("/live/", "Live Flight Tracker"), ("/miserymap/", "MiseryMap"),
         ("/live/airport/delays/", "Worldwide airport delays")]),
    "/adsb/skyaware-anywhere/": (
        "SkyAware Anywhere",
        "SkyAware Anywhere",
        ["SkyAware Anywhere extends your ADS-B receiver with remote monitoring and "
         "anywhere access to your station's traffic. FlightAware's network is built on "
         "thousands of volunteer-hosted ADS-B receivers worldwide."],
        [("/adsb/stats/", "ADS-B Statistics"), ("/adsb/piaware/", "Build a PiAware ADS-B Receiver"),
         ("/adsb/flightfeeder/", "FlightFeeder")]),
    "/adsb/coverage/": (
        "ADS-B Coverage Map",
        "Coverage Map",
        ["The FlightAware ADS-B coverage map shows the worldwide network of coverage built "
         "from thousands of volunteer ground stations feeding live aircraft positions."],
        [("/adsb/stats/", "ADS-B Statistics"), ("/live/", "Live Flight Tracker")]),
    "/adsb/store/": (
        "ADS-B Store",
        "ADS-B Store",
        ["The FlightAware store offers ADS-B receivers and accessories for hosting a "
         "station: PiAware bundles, FlightFeeder receivers and antennas for joining the "
         "worldwide tracking network."],
        [("/adsb/piaware/", "Build a PiAware ADS-B Receiver"),
         ("/adsb/flightfeeder/", "FlightFeeder")]),
    "/adsb/piaware/": (
        "Build a PiAware ADS-B Receiver",
        "PiAware",
        ["PiAware turns a Raspberry Pi into an ADS-B ground station feeding the "
         "FlightAware network. Host a receiver to track aircraft in your area and add to "
         "the worldwide coverage."],
        [("/adsb/flightfeeder/", "FlightFeeder"),
         ("/adsb/coverage/", "Coverage Map"), ("/adsb/stats/", "ADS-B Statistics")]),
    "/adsb/flightfeeder/": (
        "FlightFeeder",
        "FlightFeeder",
        ["FlightFeeder is FlightAware's ADS-B receiver for hosting a tracking station: "
         "plug it in, connect it to your network, and share live aircraft data with the "
         "FlightAware community."],
        [("/adsb/piaware/", "Build a PiAware ADS-B Receiver"),
         ("/adsb/coverage/", "Coverage Map")]),
    "/about/faq/": (
        "Frequently Asked Questions",
        "FAQs",
        ["Answers to common questions about flight tracking: where flight status comes "
         "from, how delay and arrival estimates are calculated, why commercial and "
         "general-aviation flights appear differently, and how to use FlightAware's flight "
         "tracking technology in your own application."],
        [("/about/data-sources/", "Data Sources"), ("/commercial/aeroapi/", "AeroAPI"),
         ("/about/contact/", "Contact Us")]),
    "/about/careers/": (
        "Careers at FlightAware",
        "Careers",
        ["FlightAware builds the world's leading flight tracking platform. Careers "
         "information for engineering, data and aviation roles is published on the "
         "company pages of flightaware.com."],
        [("/about/", "About FlightAware"), ("/about/history/", "History")]),
    "/about/data-sources/": (
        "Data Sources",
        "Data Sources",
        ["FlightAware operates a worldwide network of over 41,000 terrestrial ADS-B receivers, made "
         "up of users who host ground stations feeding flight tracking data, and integrates position "
         "reports and flight information (FLIFO) data from over 10,000 aircraft through agreements "
         "with nearly every VHF or satellite data link provider. FlightAware also fuses position data "
         "from Aireon's space-based ADS-B network with flight information to deliver truly global "
         "flight tracking with position updates a minimum of once every minute."],
        [("/adsb/stats/", "ADS-B Statistics"), ("/about/faq/", "FAQs")]),
    "/about/history/": (
        "FlightAware History",
        "History",
        ["Founded in 2005, FlightAware pioneered Internet-based flight tracking and was acquired "
         "by Collins Aerospace in 2021. The FlightAware history timeline covers the product "
         "launches that built the world's most comprehensive flight tracking and digital aviation "
         "data platform, from the first live flight tracking website to the space-based ADS-B "
         "network."],
        [("/about/", "About FlightAware"), ("/about/careers/", "Careers")]),
    "/about/contact/": (
        "Contact FlightAware",
        "Contact Us",
        ["Contact information for FlightAware support, sales, and media inquiries is "
         "published on the company pages of flightaware.com."],
        [("/about/faq/", "FAQs"), ("/about/", "About FlightAware")]),
    "/about/terms-of-use/": (
        "Terms of Use",
        "Terms of Use",
        ["The terms of use for flightaware.com govern the use of the FlightAware website "
         "and services, including the flight tracking pages, the photo community and "
         "member accounts."],
        [("/about/privacy/", "Privacy"), ("/about/", "About FlightAware")]),
    "/about/privacy/": (
        "Privacy Policy",
        "Privacy",
        ["The FlightAware privacy policy describes how flightaware.com handles member "
         "account information and site usage data."],
        [("/about/terms-of-use/", "Terms of Use"), ("/about/", "About FlightAware")]),
    "/blog/": (
        "FlightAware Blog",
        "Blog",
        ["The FlightAware blog covers product news, aviation data insights and stories "
         "from the worldwide flight tracking network."],
        [("/squawks/", "Squawks & headlines"), ("/news/", "Newsroom"),
         ("/webinars/", "Webinars")]),
    "/engineering/": (
        "Engineering Blog",
        "Engineering Blog",
        ["The FlightAware engineering blog publishes technical deep dives from the team "
         "that operates the world's leading flight tracking platform: data pipelines, "
         "ADS-B infrastructure and site reliability."],
        [("/blog/", "Blog"), ("/adsb/stats/", "ADS-B Statistics")]),
    "/news/": (
        "Newsroom",
        "Newsroom",
        ["The FlightAware newsroom publishes company announcements, product launches and "
         "aviation data stories."],
        [("/blog/", "Blog"), ("/webinars/", "Webinars"), ("/about/", "About FlightAware")]),
    "/webinars/": (
        "Webinars",
        "Webinars",
        ["FlightAware webinars present product walkthroughs and aviation data topics for "
         "airports, airlines, FBOs and operators."],
        [("/blog/", "Blog"), ("/news/", "Newsroom")]),
}

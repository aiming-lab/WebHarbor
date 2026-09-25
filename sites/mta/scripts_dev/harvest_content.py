"""Harvest all content pages into source_data/content.json.

Captures every server-rendered content page on new.mta.info listed in
PAGES, extracts the structured block content, and freezes it into
source_data/content.json keyed by page path.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from content_extract import extract_blocks, extract_hero_image, extract_updated
from mfetch import fetch

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "source_data"

BASE = "https://new.mta.info"

PAGES = {
    "/schedules": "Schedules",
    "/maps": "Maps",
    "/fares-tolls": "Fares and tolls",
    "/fares-tolls/subway-bus": "Subway and bus fares",
    "/fares-tolls/subway-bus/reduced-fare": "Reduced fares",
    "/fares-tolls/subway-bus/tap-and-ride": "Tap and ride to pay your fare",
    "/fares-tolls/lirr-metro-north": "LIRR and Metro-North fares",
    "/fares-tolls/tolls": "Bridges and Tunnels tolls",
    "/tolls/vehicle-types": "Bridges and Tunnels tolls by vehicle",
    "/fares-tolls/tolls/congestion-relief-zone": "Congestion Relief Zone tolling information",
    "/fares-tolls/how-to-save-money": "How to save money on fares",
    "/fares-tolls/pre-tax-benefits": "Pre-tax transit benefit information",
    "/fares-tolls/2025-changes": "Changes to MTA fares and tolls in 2025",
    "/fares-tolls/lirr-metro-north/ticket-refunds": "Refunds on LIRR and Metro-North tickets",
    "/planned-service-changes": "Planned Service Changes",
    "/elevator-escalator-status": "Elevator & Escalator Status",
    "/nearby": "Nearby Stations & Stops",
    "/alerts": "Planned Work",
    "/accessibility": "Accessibility",
    "/accessibility/access-a-ride": "Access-A-Ride Paratransit",
    "/guides": "Guides",
    "/guides/service-alerts": "Sign up for service alerts",
    "/guides/riding-the-subway": "Riding the subway",
    "/guides/riding-the-bus": "Riding the bus",
    "/guides/airports": "Getting to and from New York-area airports",
    "/guides/airports/jfk": "How to get to JFK Airport on public transit",
    "/guides/airports/laguardia": "How to get to LaGuardia Airport on public transit",
    "/guides/airports/newark-ewr": "How to get to Newark Airport on public transit",
    "/guides/bikes": "Taking your bike with you",
    "/guides/pets": "Taking your pet with you",
    "/guides/weather-service-guide": "Extreme weather travel guide",
    "/guides/stadiums": "Getting to NYC-area stadiums and arenas on transit",
    "/guides/stadiums/barclays-center-brooklyn": "Getting to Barclays Center",
    "/guides/stadiums/citi-field-queens": "Getting to Citi Field",
    "/guides/stadiums/madison-square-garden": "Getting to Madison Square Garden",
    "/guides/stadiums/yankee-stadium": "Getting to Yankee Stadium",
    "/guides/stadiums/ubs-arena": "Getting to UBS Arena",
    "/guides/stadiums/forest-hills-stadium-queens": "Getting to Forest Hills Stadium",
    "/guides/stadiums/national-tennis-center-queens": "Getting to USTA Billie Jean King National Tennis Center",
    "/guides/stadiums/metlife-stadium-meadowlands": "Getting to MetLife Stadium",
    "/guides/stadiums/maimonides-park-brooklyn": "Getting to Maimonides Park",
    "/guides/stadiums/jones-beach-amphitheater": "Getting to Northwell Health at Jones Beach Theater",
    "/about": "About the MTA",
    "/transparency/leadership/executive-leadership": "Executive leadership",
    "/transparency/leadership/board-members": "Board members",
    "/transparency": "Transparency",
    "/transparency/board-and-committee-meetings": "Board and committee meetings",
    "/safety-and-security": "Safety and Security",
    "/careers": "Careers",
    "/climate": "Climate",
    "/lost-and-found": "Lost and Found",
    "/lost-and-found/subway-bus-and-staten-island-railway": "Subway, Bus and Staten Island Railway",
    "/lost-and-found/long-island-rail-road": "Long Island Rail Road",
    "/lost-and-found/metro-north-railroad": "Metro-North Railroad",
    "/contact-us": "Contact the MTA",
    "/agency": "Agencies and departments",
    "/agency/new-york-city-transit": "New York City Transit",
    "/agency/bridges-and-tunnels": "Bridges & Tunnels",
    "/agency/long-island-rail-road": "Long Island Rail Road",
    "/agency/metro-north-railroad": "Metro-North Railroad",
    "/agency/long-island-rail-road/timetables": "Long Island Rail Road PDF timetables",
    "/agency/metro-north-railroad/schedules": "Metro-North Railroad PDF schedules",
    "/doing-business-with-us": "Doing Business With Us",
    "/doing-business-with-us/procurement": "Procurement and solicitations",
    "/agency/media-relations": "Media Relations",
    "/agency/arts-design": "Arts & Design",
    "/terms-and-conditions": "Terms & Conditions",
    "/privacy-policy": "Privacy Policy",
    # transparency / finance / governance sub-pages
    "/transparency/public-hearings": "Public hearings",
    "/transparency/public-notices": "Public notices",
    "/budget": "MTA budget",
    "/capital": "Capital programs",
    "/transparency/financial-information/financial-and-budget-statements": "Financial and budget statements",
    "/investor-info": "Investor information",
    "/transparency/financial-information/BudgetWatch": "BudgetWatch",
    "/transparency/financial-information/savings-actions-reports": "Savings actions reports",
    "/transparency/regional-mobility-tax-information": "Regional mobility tax information",
    "/transparency/overtime-reports": "Overtime reports",
    "/transparency/foil": "Freedom of Information Law (FOIL)",
    "/transparency/protections-for-reporting-fraud-in-new-york": "Protections for reporting fraud in New York",
    "/transparency/title-vi/contact": "Title VI contact",
    "/open-data": "Open data",
    "/developers": "Developers",
    "/careers/MTA-EEO-Policy": "MTA EEO Policy",
    "/doing-business-with-us/opportunities-for-certified-M-WBE-DBE-SDVOB": "Opportunities for certified M/WBE, DBE, SDVOB firms",
    "/doing-business-with-us/procurement/bidders-lists": "Bidders lists",
    # accessibility
    "/accessibility/stations": "MTA Accessible Stations",
    "/accessibility/access-a-ride/omny": "OMNY and Access-A-Ride",
    # arts & design sub-pages
    "/agency/arts-design/permanent-art": "Permanent art",
    "/agency/arts-design/digital-art": "Digital art",
    "/agency/arts-design/photography": "Photography",
    "/agency/arts-design/poster": "Posters",
    "/agency/arts-design/poetry-in-motion": "Poetry in Motion",
    # weather guide sub-pages
    "/guides/weather-service-guide/storm-flood-hurricane-service": "Storm, flood and hurricane service information",
    "/guides/weather-service-guide/winter-weather": "Winter weather service guide",
    "/guides/weather-service-guide/fallen-leaves": "Fallen leaves service guide",
    # congestion relief zone sub-pages
    "/fares-tolls/tolls/congestion-relief-zone/about": "About the Congestion Relief Zone toll",
    "/fares-tolls/tolls/congestion-relief-zone/discounts-exemptions": "Congestion Relief Zone toll discounts and exemptions",
    "/fares-tolls/tolls/congestion-relief-zone/e-zpass": "E-ZPass and Congestion Relief Zone tolling",
    "/fares-tolls/tolls/congestion-relief-zone/calculator": "Congestion Relief Zone toll rate calculator",
    "/fares-tolls/tolls/congestion-relief-zone/faq": "Congestion Relief Zone tolling FAQ",
    "/fares-tolls/tolls/resident-programs": "Toll rebate and discount programs for NYC residents",
    # agency / department sub-pages
    "/agency/construction-and-development": "Construction & Development",
    "/agency/mta-bus-company": "MTA Bus Company",
    "/agency/mta-police": "MTA Police",
    "/agency/mta-real-estate": "MTA Real Estate",
    "/agency/transit-adjudication-bureau": "Transit Adjudication Bureau",
    "/agency/staten-island-railway": "Staten Island Railway",
    "/agency/construction-and-development/contracting": "Contracting",
    "/agency/construction-and-development/contracting/current-opportunities": "Current contracting opportunities",
    "/agency/construction-and-development/contracting/upcoming-opportunities": "Upcoming contracting opportunities",
    "/agency/construction-and-development/building-near-transit/external-partner-program": "Building near transit: external partner program",
    "/agency/construction-and-development/tod": "Transit-oriented development",
    # investor-info sub-pages
    "/investor-info/upcoming-transactions": "Upcoming transactions",
    "/investor-info/official-statements": "Official statements",
    "/investor-info/debt-portfolio-information": "Debt portfolio information",
    "/investor-info/credit-ratings": "Credit ratings",
    "/investor-info/bond-resolutions-interagency-agreements": "Bond resolutions and interagency agreements",
    "/investor-info/debt-obligation-policies": "Debt obligation policies",
    "/investor-info/hudson-rail-yards-trust-obligations": "Hudson Rail Yards trust obligations",
    "/investor-info/lines-of-credit": "Lines of credit",
    "/investor-info/direct-placement-of-bonds": "Direct placement of bonds",
    "/investor-info/loans": "Loans",
    "/investor-info/disclosure-filings": "Disclosure filings",
    "/investor-info/material-event-notices": "Material event notices",
    "/investor-info/green-bonds": "Green bonds",
    "/investor-info/sustainability": "Sustainability",
    # doing-business sub-pages
    "/doing-business-with-us/opportunities-for-HUBs/utilization-reporting": "Utilization reporting for HUBs",
    "/doing-business-with-us/procurement/current-opportunities/vision-ahead": "Current opportunities: Vision Ahead",
    # arts & design collection sub-pages
    "/agency/arts-design/digital-art/gullah-island": "Digital art: Gullah Island",
    "/agency/arts-design/digital-art/breathe": "Digital art: Breathe",
    "/agency/arts-design/collection/in-service": "Collection: In Service",
    "/agency/arts-design/collection/still-the-land-gives": "Collection: Still the Land Gives",
    "/agency/arts-design/collection/manifestations": "Collection: Manifestations",
    "/agency/arts-design/collection/indigenous-presence": "Collection: Indigenous Presence",
    "/arts-design/collection/fake-plants": "Collection: Fake Plants",
    "/arts-design/collection/harlem-snapshot": "Collection: Harlem Snapshot",
    "/agency/arts-design/collection/tigers": "Collection: Tigers",
    "/agency/arts-design/collection/tiburon": "Collection: Tiburon",
    # transit adjudication bureau + rules
    "/agency/new-york-city-transit/rules-of-conduct": "Rules of conduct",
    "/agency/transit-adjudication-bureau/notice-of-violation": "Notice of violation",
    "/agency/transit-adjudication-bureau/how-to-pay-a-fine": "How to pay a fine",
    "/agency/transit-adjudication-bureau/what-to-expect-at-a-hearing": "What to expect at a hearing",
    "/agency/transit-adjudication-bureau/file-an-appeal": "File an appeal",
    "/agency/transit-adjudication-bureau/record-requests": "Record requests",
    "/agency/transit-adjudication-bureau/forms": "Forms",
    # construction & development contracting sub-pages
    "/agency/construction-and-development/contracting/recent-awards": "Recent awards",
    "/agency/construction-and-development/contracting/bid-results": "Bid results",
    "/agency/construction-and-development/building-near-transit/external-partner-program/adjacency": "External partner program: adjacency",
    "/agency/construction-and-development/building-near-transit/external-partner-program/public-agency": "External partner program: public agency",
    "/agency/construction-and-development/building-near-transit/external-partner-program/developer-improvement": "External partner program: developer improvement",
    # accessibility sub-pages
    "/accessibility/ada-complaint": "How to file an ADA complaint",
    "/accessibility/lirr-care": "LIRR CARE",
    "/accessibility/metro-north-care": "Metro-North CARE",
    "/accessibility/subway": "Accessible subway stations and services",
    "/accessibility/bus": "Accessible bus services",
    "/accessibility/mta-railroads": "Accessible railroad services",
    "/accessibility/innovations": "Accessibility innovations",
    "/accessibility/innovations/navilens": "NaviLens",
    "/accessibility/innovations/convo": "Convo",
    "/accessibility/innovations/bus-stroller-areas": "Bus stroller areas",
    "/accessibility/stationlab": "STATIONlab",
    "/accessibility/enhancing-buses": "Enhancing buses for accessibility",
    "/accessibility/pcas-and-service-animals-reasonable-accommodations": "PCAs and service animals: reasonable accommodations",
    "/accessibility/contact": "Accessibility contact",
    "/accessibility/ACTA": "Accelerated Change and Trip Assistance (ACTA)",
    "/article/disability-pride-month-2026": "Disability Pride Month 2026",
    "/agency/new-york-city-transit/ridership": "NYC Transit ridership",
    "/agency/new-york-city-transit/ridership/2025": "NYC Transit ridership 2025",
    "/agency/new-york-city-transit/ridership/2024": "NYC Transit ridership 2024",
    "/agency/new-york-city-transit/ridership/2023": "NYC Transit ridership 2023",
    "/agency/new-york-city-transit/ridership/2022": "NYC Transit ridership 2022",
    "/agency/new-york-city-transit/ridership/2021": "NYC Transit ridership 2021",
    "/agency/new-york-city-transit/ridership/2020": "NYC Transit ridership 2020",
    "/agency/new-york-city-transit/ridership/2019": "NYC Transit ridership 2019",
    "/fares-and-tolls/subway-bus-and-staten-island-railway/reduced-fare-metrocard": "Reduced-fare MetroCard",
    "/doing-business-with-us/advertising": "Advertising",
    "/doing-business-with-us/filming": "Filming",
    "/doing-business-with-us/licensing-program": "Licensing program",
    "/doing-business-with-us/procurement/surplus-material-sales": "Surplus material sales",
    "/agency/construction-and-development/building-near-transit": "Building near transit",
    "/doing-business-with-us/edge": "EDGE",
    "/doing-business-with-us/opportunities-for-HUBs": "Opportunities for HUBs",
    "/doing-business-with-us/working-near-lirr-property": "Working near LIRR property",
    "/doing-business-with-us/working-near-metro-north-in-new-york": "Working near Metro-North in New York",
    "/doing-business-with-us/working-near-rails-in-ct": "Working near rails in Connecticut",
    "/climate/resilience": "Climate resilience",
    "/climate/sustainability": "Sustainability",
    "/accessibility/access-a-ride/contact": "Access-A-Ride contact",
    "/doing-business-with-us/edge/tier-1": "EDGE Tier 1",
    "/doing-business-with-us/edge/tier-2": "EDGE Tier 2",
    "/doing-business-with-us/edge/federal-program": "EDGE federal program",
    "/doing-business-with-us/working-near-rails-in-ct/metro-north": "Working near Metro-North rails in Connecticut",
    "/doing-business-with-us/procurement/guide-for-contractors-and-suppliers": "Guide for contractors and suppliers",
    "/agency/new-york-city-transit/station-renovation": "Station renovation",
    "/agency/new-york-city-transit/bus-network-redesign": "Bus network redesign",
    "/climate/sustainability/carbon-accounting": "Carbon accounting",
    "/doing-business-with-us/procurement/goods-and-services-categories": "Goods and services categories",
    "/doing-business-with-us/procurement/current-opportunities": "Current procurement opportunities",
    "/climate/resilience/rebuilding-since-sandy": "Rebuilding since Sandy",
    "/agency/bridges-and-tunnels/congestion-relief-zone": "Congestion Relief Zone",
    "/agency/bridges-and-tunnels/bronx-whitestone-bridge": "Bronx-Whitestone Bridge",
    "/agency/bridges-and-tunnels/cross-bay-veterans-memorial-bridge": "Cross Bay Veterans Memorial Bridge",
    "/agency/bridges-and-tunnels/henry-hudson-bridge": "Henry Hudson Bridge",
    "/agency/bridges-and-tunnels/marine-parkway-gil-hodges-memorial-bridge": "Marine Parkway-Gil Hodges Memorial Bridge",
    "/agency/bridges-and-tunnels/rfk-bridge": "Robert F. Kennedy Bridge",
    "/agency/bridges-and-tunnels/throgs-neck-bridge": "Throgs Neck Bridge",
    "/agency/bridges-and-tunnels/verrazzano-narrows-bridge": "Verrazzano-Narrows Bridge",
    "/agency/bridges-and-tunnels/hugh-l-carey-tunnel": "Hugh L. Carey Tunnel",
    "/agency/bridges-and-tunnels/queens-midtown-tunnel": "Queens-Midtown Tunnel",
    "/agency/bridges-and-tunnels/congestion-relief-zone/program": "Congestion Relief Zone program",
    "/agency/bridges-and-tunnels/congestion-relief-zone/better-transit": "Congestion Relief Zone: better transit",
    "/stations/long-island-rail-road-stations": "Long Island Rail Road stations",
    "/stations/metro-north-railroad-stations": "Metro-North Railroad stations",
    "/destinations/beaches/jones-beach": "Getting to Jones Beach by train",
    "/destinations/beaches/fire-island": "Getting to Fire Island by train",
    "/destinations/beaches/long-beach": "Getting to Long Beach by train",
    "/traintime": "TrainTime app",
    "/safety-and-security/railroads": "Railroad safety",
    "/guides/bikes/bike-regulations-lirr": "Bike regulations: LIRR",
    "/guides/bikes/bike-regulations-mnr": "Bike regulations: Metro-North",
    "/article/metro-north-hosts-connect-us-events": "Metro-North hosts Connect Us events",
    "/doing-business-with-us/procurement/mta-headquarters": "Procurement: MTA headquarters",
    "/doing-business-with-us/procurement/new-york-city-transit": "Procurement: New York City Transit",
    "/doing-business-with-us/procurement/long-island-rail-road": "Procurement: Long Island Rail Road",
    "/doing-business-with-us/procurement/metro-north": "Procurement: Metro-North",
    "/doing-business-with-us/procurement/bridges-and-tunnels": "Procurement: Bridges and Tunnels",
    "/doing-business-with-us/procurement/mta-bus-company": "Procurement: MTA Bus Company",
    "/doing-business-with-us/procurement/discretionary-solicitations": "Discretionary solicitations",
    "/agency/bridges-and-tunnels/congestion-relief-zone/program/reevaluation2-and-vppp-agreement": "Congestion Relief Zone: Reevaluation 2 and VPPP agreement",
    "/project/CBDTP/environmental-assessment": "Congestion Relief Zone environmental assessment",
    "/project/CBDTP/environmental-justice-communities": "Congestion Relief Zone environmental justice communities",
    "/agency/bridges-and-tunnels/congestion-relief-zone/program/archive": "Congestion Relief Zone program archive",
    "/agency/bridges-and-tunnels/congestion-relief-zone/program/mitigation": "Congestion Relief Zone mitigation",
}

PROJECTS = [
    "/project/interborough-express",
    "/project/station-accessibility-upgrades",
    "/project/penn-station-access",
    "/project/queens-bus-network-redesign",
    "/project/CBDTP",
    "/project/168-st-interim-bus-terminal",
    "/project/42-st-connection",
    "/project/renewed-astoria-line",
    "/project/bronx-local-bus-network-redesign",
    "/project/brooklyn-bus-network-redesign",
    "/project/cbtc-signal-upgrades",
    "/project/east-side-access",
    "/project/fixing-rutgers-tunnel",
    "/project/fulton-transit-center",
    "/project/improving-accessibility-68-st-hunter-college-station",
]

BUS_BOROUGHS = {
    "/schedules/bus/bronx": "Bronx bus schedules",
    "/schedules/bus/Brooklyn": "Brooklyn bus schedules",
    "/schedules/bus/manhattan": "Manhattan bus schedules",
    "/schedules/bus/queens": "Queens bus schedules",
    "/schedules/bus/si": "Staten Island bus schedules",
}

# Upstream links the mirror deliberately does not carry: the two bus-network
# redesign plan PDFs are 164 MB / 85 MB (too heavy for the asset bundle) and
# the environmental-sustainability department page 403s upstream. Their link
# text is kept and rendered as plain text (medicare_gov's external-link
# precedent) so no page carries a dead link.
DROPPED_LINKS = {
    "/document/101521",
    "/document/160201",
    "/agency/department-of-environmental-sustainability-and-compliance",
}


def _drop_links(blocks):
    for block in blocks:
        if block.get("type") == "links":
            kept = []
            for link in block["links"]:
                if link.get("href") in DROPPED_LINKS:
                    kept.append({"text": link.get("text", "")})
                else:
                    kept.append(link)
            block["links"] = kept
    return blocks


def harvest():
    content = {}
    for path, label in PAGES.items():
        url = BASE + path
        doc = fetch(url)
        if not doc:
            print(f"FAIL {path}", flush=True)
            continue
        blocks = extract_blocks(doc)
        if blocks is None:
            print(f"NO-REGION {path}", flush=True)
            continue
        blocks["path"] = path
        blocks["label"] = label
        blocks["blocks"] = _drop_links(blocks["blocks"])
        hero = extract_hero_image(doc)
        if hero:
            blocks["hero"] = hero
        updated = extract_updated(doc)
        if updated:
            blocks["updated"] = updated
        content[path] = blocks
        print(f"OK {path} ({len(blocks['blocks'])} blocks)", flush=True)

    for path in PROJECTS:
        url = BASE + path
        doc = fetch(url)
        if not doc:
            print(f"FAIL {path}", flush=True)
            continue
        blocks = extract_blocks(doc)
        if blocks:
            blocks["path"] = path
            blocks["label"] = "Project"
            blocks["blocks"] = _drop_links(blocks["blocks"])
            hero = extract_hero_image(doc)
            if hero:
                blocks["hero"] = hero
            content[path] = blocks
            print(f"OK {path} ({len(blocks['blocks'])} blocks)", flush=True)

    for path, label in BUS_BOROUGHS.items():
        url = BASE + path
        doc = fetch(url)
        if not doc:
            print(f"FAIL {path}", flush=True)
            continue
        blocks = extract_blocks(doc)
        if blocks:
            blocks["path"] = path
            blocks["label"] = label
            content[path] = blocks
            print(f"OK {path} ({len(blocks['blocks'])} blocks)", flush=True)

    OUT.mkdir(exist_ok=True)
    (OUT / "content.json").write_text(json.dumps(content, indent=1, ensure_ascii=False))
    print(f"\nwrote {OUT/'content.json'} with {len(content)} pages")


if __name__ == "__main__":
    harvest()

import json
import math
import shutil
from datetime import date, datetime, time, timedelta
from pathlib import Path


MIRROR_REFERENCE_DATE = datetime(2026, 4, 18, 8, 0, 0)
SERVICE_DATES = [
    date(2026, 4, 14),
    date(2026, 4, 16),
    date(2026, 4, 17),
    date(2026, 4, 18),
    date(2026, 4, 20),
    date(2026, 4, 22),
    date(2026, 4, 24),
]
BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_USERS = [
    {
        "email": "alice.j@test.com",
        "display_name": "Alice Jordan",
        "first_name": "Alice",
        "last_name": "Jordan",
        "phone": "212-555-0101",
        "city": "New York",
        "state": "NY",
        "preferred_station_code": "NYP",
        "tier": "Select",
        "starter_points": 2400,
    },
    {
        "email": "bob.c@test.com",
        "display_name": "Bob Castillo",
        "first_name": "Bob",
        "last_name": "Castillo",
        "phone": "312-555-0192",
        "city": "Chicago",
        "state": "IL",
        "preferred_station_code": "CHI",
        "tier": "Member",
        "starter_points": 1800,
    },
    {
        "email": "carol.d@test.com",
        "display_name": "Carol Diaz",
        "first_name": "Carol",
        "last_name": "Diaz",
        "phone": "206-555-0144",
        "city": "Seattle",
        "state": "WA",
        "preferred_station_code": "SEA",
        "tier": "Select",
        "starter_points": 2600,
    },
    {
        "email": "david.k@test.com",
        "display_name": "David Kim",
        "first_name": "David",
        "last_name": "Kim",
        "phone": "213-555-0118",
        "city": "Los Angeles",
        "state": "CA",
        "preferred_station_code": "LAX",
        "tier": "Select Plus",
        "starter_points": 3200,
    },
]

REGION_COLORS = {
    "Northeast": ("#0d2c57", "#1f6fa4", "#8dd2e6", "#f2f7fb"),
    "South": ("#0d3652", "#2f8fa3", "#6ec7d3", "#f3f8f9"),
    "Midwest": ("#17304a", "#3f6b93", "#82a7ca", "#f5f7fb"),
    "West": ("#14344b", "#2d7c8f", "#b3d7cc", "#f7fbf7"),
}

STATION_SPECS = [
    {"code": "BOS", "city_slug": "boston", "city_name": "Boston", "state": "MA", "region": "Northeast", "name": "South Station", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "BBY", "city_slug": "boston", "city_name": "Boston", "state": "MA", "region": "Northeast", "name": "Back Bay", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "PVD", "city_slug": "providence", "city_name": "Providence", "state": "RI", "region": "Northeast", "name": "Providence Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
    {"code": "NHV", "city_slug": "new-haven", "city_name": "New Haven", "state": "CT", "region": "Northeast", "name": "Union Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "NLC", "city_slug": "new-london", "city_name": "New London", "state": "CT", "region": "Northeast", "name": "New London Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "NYP", "city_slug": "new-york", "city_name": "New York", "state": "NY", "region": "Northeast", "name": "Moynihan Train Hall", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "NWK", "city_slug": "newark", "city_name": "Newark", "state": "NJ", "region": "Northeast", "name": "Newark Penn Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "PHL", "city_slug": "philadelphia", "city_name": "Philadelphia", "state": "PA", "region": "Northeast", "name": "30th Street Station", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "WIL", "city_slug": "wilmington", "city_name": "Wilmington", "state": "DE", "region": "Northeast", "name": "Joseph R. Biden Jr. Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
    {"code": "BAL", "city_slug": "baltimore", "city_name": "Baltimore", "state": "MD", "region": "Northeast", "name": "Penn Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "BWI", "city_slug": "linthicum", "city_name": "Linthicum", "state": "MD", "region": "Northeast", "name": "BWI Rail Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "WAS", "city_slug": "washington", "city_name": "Washington", "state": "DC", "region": "Northeast", "name": "Union Station", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "ALX", "city_slug": "alexandria", "city_name": "Alexandria", "state": "VA", "region": "South", "name": "Alexandria Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "RVR", "city_slug": "richmond", "city_name": "Richmond", "state": "VA", "region": "South", "name": "Staples Mill Road Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "RVM", "city_slug": "richmond", "city_name": "Richmond", "state": "VA", "region": "South", "name": "Main Street Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "RAL", "city_slug": "raleigh", "city_name": "Raleigh", "state": "NC", "region": "South", "name": "Raleigh Union Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "DHM", "city_slug": "durham", "city_name": "Durham", "state": "NC", "region": "South", "name": "Durham Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "CLT", "city_slug": "charlotte", "city_name": "Charlotte", "state": "NC", "region": "South", "name": "Charlotte Gateway Station", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "SAV", "city_slug": "savannah", "city_name": "Savannah", "state": "GA", "region": "South", "name": "Savannah Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
    {"code": "ATL", "city_slug": "atlanta", "city_name": "Atlanta", "state": "GA", "region": "South", "name": "Peachtree Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "NOL", "city_slug": "new-orleans", "city_name": "New Orleans", "state": "LA", "region": "South", "name": "Union Passenger Terminal", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "CHI", "city_slug": "chicago", "city_name": "Chicago", "state": "IL", "region": "Midwest", "name": "Union Station", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "MKE", "city_slug": "milwaukee", "city_name": "Milwaukee", "state": "WI", "region": "Midwest", "name": "Intermodal Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
    {"code": "STL", "city_slug": "st-louis", "city_name": "St. Louis", "state": "MO", "region": "Midwest", "name": "Gateway Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "MEM", "city_slug": "memphis", "city_name": "Memphis", "state": "TN", "region": "South", "name": "Memphis Central Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "BNL", "city_slug": "bloomington-normal", "city_name": "Bloomington-Normal", "state": "IL", "region": "Midwest", "name": "Normal Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "HAR", "city_slug": "harrisburg", "city_name": "Harrisburg", "state": "PA", "region": "Northeast", "name": "Harrisburg Transportation Center", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "LNC", "city_slug": "lancaster", "city_name": "Lancaster", "state": "PA", "region": "Northeast", "name": "Lancaster Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "ALB", "city_slug": "albany", "city_name": "Albany", "state": "NY", "region": "Northeast", "name": "Albany-Rensselaer", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "SYR", "city_slug": "syracuse", "city_name": "Syracuse", "state": "NY", "region": "Northeast", "name": "William F. Walsh Regional Transportation Center", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
    {"code": "ROC", "city_slug": "rochester", "city_name": "Rochester", "state": "NY", "region": "Northeast", "name": "Louise M. Slaughter Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
    {"code": "BUF", "city_slug": "buffalo", "city_name": "Buffalo", "state": "NY", "region": "Northeast", "name": "Exchange Street Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "CLE", "city_slug": "cleveland", "city_name": "Cleveland", "state": "OH", "region": "Midwest", "name": "Lakefront Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
    {"code": "TOL", "city_slug": "toledo", "city_name": "Toledo", "state": "OH", "region": "Midwest", "name": "Martin Luther King Jr. Plaza", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
    {"code": "DET", "city_slug": "detroit", "city_name": "Detroit", "state": "MI", "region": "Midwest", "name": "Detroit New Center", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "MSP", "city_slug": "st-paul", "city_name": "St. Paul", "state": "MN", "region": "Midwest", "name": "Union Depot", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "SEA", "city_slug": "seattle", "city_name": "Seattle", "state": "WA", "region": "West", "name": "King Street Station", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "TAC", "city_slug": "tacoma", "city_name": "Tacoma", "state": "WA", "region": "West", "name": "Tacoma Dome Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "PDX", "city_slug": "portland", "city_name": "Portland", "state": "OR", "region": "West", "name": "Union Station", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "VAN", "city_slug": "vancouver", "city_name": "Vancouver", "state": "WA", "region": "West", "name": "Vancouver Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "EUG", "city_slug": "eugene", "city_name": "Eugene", "state": "OR", "region": "West", "name": "Eugene-Springfield Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "SAC", "city_slug": "sacramento", "city_name": "Sacramento", "state": "CA", "region": "West", "name": "Sacramento Valley Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "EMY", "city_slug": "emeryville", "city_name": "Emeryville", "state": "CA", "region": "West", "name": "Emeryville Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "OKJ", "city_slug": "oakland", "city_name": "Oakland", "state": "CA", "region": "West", "name": "Jack London Square", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "SJC", "city_slug": "san-jose", "city_name": "San Jose", "state": "CA", "region": "West", "name": "Diridon Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "SLO", "city_slug": "san-luis-obispo", "city_name": "San Luis Obispo", "state": "CA", "region": "West", "name": "San Luis Obispo Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "SBA", "city_slug": "santa-barbara", "city_name": "Santa Barbara", "state": "CA", "region": "West", "name": "Santa Barbara Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
    {"code": "LAX", "city_slug": "los-angeles", "city_name": "Los Angeles", "state": "CA", "region": "West", "name": "Union Station", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "ANA", "city_slug": "anaheim", "city_name": "Anaheim", "state": "CA", "region": "West", "name": "Anaheim Regional Transportation Intermodal Center", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "SAN", "city_slug": "san-diego", "city_name": "San Diego", "state": "CA", "region": "West", "name": "Santa Fe Depot", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "OMA", "city_slug": "omaha", "city_name": "Omaha", "state": "NE", "region": "Midwest", "name": "Omaha Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "DEN", "city_slug": "denver", "city_name": "Denver", "state": "CO", "region": "West", "name": "Union Station", "is_hub": True, "has_lounge": True, "has_checked_baggage": True},
    {"code": "GLN", "city_slug": "glenwood-springs", "city_name": "Glenwood Springs", "state": "CO", "region": "West", "name": "Glenwood Springs Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "SLC", "city_slug": "salt-lake-city", "city_name": "Salt Lake City", "state": "UT", "region": "West", "name": "Salt Lake Central", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "RNO", "city_slug": "reno", "city_name": "Reno", "state": "NV", "region": "West", "name": "Reno Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
    {"code": "KCY", "city_slug": "kansas-city", "city_name": "Kansas City", "state": "MO", "region": "Midwest", "name": "Union Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "ABQ", "city_slug": "albuquerque", "city_name": "Albuquerque", "state": "NM", "region": "West", "name": "Alvarado Transportation Center", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "FLG", "city_slug": "flagstaff", "city_name": "Flagstaff", "state": "AZ", "region": "West", "name": "Flagstaff Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "DAL", "city_slug": "dallas", "city_name": "Dallas", "state": "TX", "region": "South", "name": "Union Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "AUS", "city_slug": "austin", "city_name": "Austin", "state": "TX", "region": "South", "name": "Austin Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": False},
    {"code": "SAS", "city_slug": "san-antonio", "city_name": "San Antonio", "state": "TX", "region": "South", "name": "San Antonio Station", "is_hub": True, "has_lounge": False, "has_checked_baggage": True},
    {"code": "JAN", "city_slug": "jackson", "city_name": "Jackson", "state": "MS", "region": "South", "name": "Jackson Union Station", "is_hub": False, "has_lounge": False, "has_checked_baggage": True},
]

ROUTE_SPECS = [
    {
        "slug": "northeast-regional",
        "name": "Northeast Regional",
        "tagline": "All-day corridor service linking New England, New York, and the Mid-Atlantic.",
        "description": "A dependable corridor train with cafe service, quiet car seating, and multiple station pairs across the Northeast.",
        "route_type": "Corridor",
        "service_level": "Regional",
        "frequency_note": "Multiple departures every demo service day.",
        "stops": ["BOS", "PVD", "NHV", "NYP", "PHL", "WIL", "BAL", "WAS", "RVR", "RAL", "CLT"],
        "travel": [38, 93, 103, 84, 23, 58, 36, 123, 158, 175],
        "dwell": [0, 6, 7, 12, 5, 4, 5, 10, 6, 6, 0],
        "departures": {"outbound": "06:20", "inbound": "06:50"},
        "featured": True,
        "overnight": False,
        "base_fare": 96.0,
        "features": ["Cafe service", "Quiet car", "Large luggage racks", "Downtown stations"],
        "equipment": "Amfleet + ACS-64",
        "base_number": 171,
    },
    {
        "slug": "acela-express",
        "name": "Acela Express",
        "tagline": "Fast business-day service with premium seating and lounge-style spaces.",
        "description": "Synthetic express service inspired by premium Northeast operations, featuring quieter cabins and flexible fare options.",
        "route_type": "Express",
        "service_level": "Business",
        "frequency_note": "Four streamlined express departures per demo service day.",
        "stops": ["BOS", "PVD", "NHV", "NYP", "PHL", "WAS"],
        "travel": [35, 86, 96, 74, 92],
        "dwell": [0, 4, 5, 8, 4, 0],
        "departures": {"outbound": "07:05", "inbound": "06:40"},
        "featured": True,
        "overnight": False,
        "base_fare": 139.0,
        "features": ["Business seating", "Quiet cabin", "Express station pattern", "Priority boarding"],
        "equipment": "Avelia Liberty demo set",
        "base_number": 2151,
    },
    {
        "slug": "keystone-service",
        "name": "Keystone Service",
        "tagline": "Frequent Pennsylvania corridor service anchored by Harrisburg and New York.",
        "description": "A task-friendly short-haul route with straightforward fare choices and a dense station pattern across eastern Pennsylvania.",
        "route_type": "Corridor",
        "service_level": "Regional",
        "frequency_note": "Runs throughout the demo week with simple coach and business options.",
        "stops": ["NYP", "NWK", "PHL", "LNC", "HAR"],
        "travel": [26, 77, 68, 36],
        "dwell": [0, 4, 6, 4, 0],
        "departures": {"outbound": "08:10", "inbound": "06:15"},
        "featured": False,
        "overnight": False,
        "base_fare": 66.0,
        "features": ["Reserved coach", "Business option", "Pennsylvania corridor stops"],
        "equipment": "Keystone coach set",
        "base_number": 641,
    },
    {
        "slug": "empire-service",
        "name": "Empire Service",
        "tagline": "Hudson River and upstate New York service from Manhattan to Buffalo.",
        "description": "Synthetic upstate corridor service with river views, cafe offerings, and practical one-way pricing.",
        "route_type": "Corridor",
        "service_level": "Regional",
        "frequency_note": "Morning and afternoon departures across the seeded calendar.",
        "stops": ["NYP", "ALB", "SYR", "ROC", "BUF"],
        "travel": [155, 140, 92, 78],
        "dwell": [0, 8, 6, 5, 0],
        "departures": {"outbound": "07:45", "inbound": "06:50"},
        "featured": True,
        "overnight": False,
        "base_fare": 82.0,
        "features": ["River views", "Cafe service", "Bike storage"],
        "equipment": "Empire corridor consist",
        "base_number": 281,
    },
    {
        "slug": "lake-shore-limited",
        "name": "Lake Shore Limited",
        "tagline": "An overnight connection from Boston to Chicago through upstate New York and the Midwest.",
        "description": "Long-distance travel with sleeper rooms, dining-style copy, and a route ideal for overnight comparison tasks.",
        "route_type": "Long Distance",
        "service_level": "Sleeper",
        "frequency_note": "One overnight departure each seeded service day.",
        "stops": ["BOS", "ALB", "SYR", "BUF", "CLE", "TOL", "CHI"],
        "travel": [180, 155, 90, 185, 105, 235],
        "dwell": [0, 10, 6, 8, 7, 6, 0],
        "departures": {"outbound": "14:10", "inbound": "09:30"},
        "featured": False,
        "overnight": True,
        "base_fare": 122.0,
        "features": ["Roomettes", "Bedrooms", "Lounge access at select stations", "Dining-style meal copy"],
        "equipment": "Viewliner overnight set",
        "base_number": 449,
    },
    {
        "slug": "crescent-line",
        "name": "Crescent Line",
        "tagline": "An overnight spine connecting the Northeast, Carolinas, Atlanta, and New Orleans.",
        "description": "A sleeper-oriented long-distance route suited for room selection, route browsing, and alert-driven benchmark tasks.",
        "route_type": "Long Distance",
        "service_level": "Sleeper",
        "frequency_note": "Daily overnight demo departure.",
        "stops": ["NYP", "PHL", "WAS", "CLT", "ATL", "NOL"],
        "travel": [84, 105, 368, 246, 610],
        "dwell": [0, 5, 8, 7, 10, 0],
        "departures": {"outbound": "14:35", "inbound": "12:20"},
        "featured": True,
        "overnight": True,
        "base_fare": 148.0,
        "features": ["Roomettes", "Bedrooms", "Cafe and dining copy", "Wide-seat coach section"],
        "equipment": "Long-distance sleeper consist",
        "base_number": 19,
    },
    {
        "slug": "silver-meteor",
        "name": "Silver Meteor",
        "tagline": "An all-day and overnight South Atlantic service with long-haul leisure demand.",
        "description": "A synthetic East Coast long-distance route that blends corridor-style demand with sleeper inventory.",
        "route_type": "Long Distance",
        "service_level": "Sleeper",
        "frequency_note": "Daily seeded service with multiple fare families.",
        "stops": ["NYP", "PHL", "WAS", "RVR", "CLT", "SAV"],
        "travel": [84, 103, 125, 320, 232],
        "dwell": [0, 5, 8, 7, 6, 0],
        "departures": {"outbound": "08:30", "inbound": "10:05"},
        "featured": False,
        "overnight": True,
        "base_fare": 129.0,
        "features": ["Flexible sleeper inventory", "Boarding assistance", "Multiple station pairs"],
        "equipment": "Silver service overnight set",
        "base_number": 97,
    },
    {
        "slug": "carolinian",
        "name": "Carolinian",
        "tagline": "Practical daily travel between New York, Raleigh, and Charlotte.",
        "description": "A benchmark-friendly mixed business and leisure route with simple direct searches and clear fare tradeoffs.",
        "route_type": "Corridor",
        "service_level": "Regional",
        "frequency_note": "Daily seeded departures suitable for same-day and future searches.",
        "stops": ["NYP", "PHL", "WAS", "RAL", "CLT"],
        "travel": [84, 103, 285, 175],
        "dwell": [0, 5, 8, 6, 0],
        "departures": {"outbound": "07:55", "inbound": "06:45"},
        "featured": False,
        "overnight": False,
        "base_fare": 96.0,
        "features": ["Reserved coach", "Business seats", "Pet-friendly demo policy copy"],
        "equipment": "Carolinian coach set",
        "base_number": 79,
    },
    {
        "slug": "hiawatha-service",
        "name": "Hiawatha Service",
        "tagline": "Short-hop Midwest corridor service anchored by Chicago and Milwaukee.",
        "description": "A concise route built for fast search, sorting, and fare comparison tasks, with a through option to St. Paul in this local mirror.",
        "route_type": "Corridor",
        "service_level": "Regional",
        "frequency_note": "Multiple departures with frequent business availability.",
        "stops": ["CHI", "MKE", "MSP"],
        "travel": [88, 338],
        "dwell": [0, 6, 0],
        "departures": {"outbound": "07:10", "inbound": "07:30"},
        "featured": False,
        "overnight": False,
        "base_fare": 54.0,
        "features": ["Fast boarding", "Laptop-friendly tables", "Regional cafe"],
        "equipment": "Midwest corridor set",
        "base_number": 333,
    },
    {
        "slug": "illinois-service",
        "name": "Illinois Service",
        "tagline": "State-supported corridor travel from Chicago through Bloomington-Normal to St. Louis.",
        "description": "A clean point-to-point route useful for schedule lookup, cheapest-fare tasks, and status checks.",
        "route_type": "State Supported",
        "service_level": "Regional",
        "frequency_note": "Two seeded departure slots per service date.",
        "stops": ["CHI", "BNL", "STL"],
        "travel": [128, 160],
        "dwell": [0, 6, 0],
        "departures": {"outbound": "09:00", "inbound": "08:15"},
        "featured": False,
        "overnight": False,
        "base_fare": 58.0,
        "features": ["Carry-on-friendly", "Regional work tables", "Simple same-day trips"],
        "equipment": "Illinois corridor coaches",
        "base_number": 301,
    },
    {
        "slug": "city-of-new-orleans",
        "name": "City of New Orleans",
        "tagline": "Overnight Chicago to New Orleans travel through Memphis and Mississippi.",
        "description": "A long-distance overnight route with room types, meals-included copy, and taskable past/upcoming booking history.",
        "route_type": "Long Distance",
        "service_level": "Sleeper",
        "frequency_note": "Night departure with a single daily seeded instance.",
        "stops": ["CHI", "MEM", "JAN", "NOL"],
        "travel": [530, 220, 188],
        "dwell": [0, 9, 8, 0],
        "departures": {"outbound": "20:15", "inbound": "13:30"},
        "featured": False,
        "overnight": True,
        "base_fare": 116.0,
        "features": ["Roomettes", "Bedrooms", "Dining-style copy", "Overnight timing"],
        "equipment": "Viewliner overnight set",
        "base_number": 59,
    },
    {
        "slug": "amtrak-cascades",
        "name": "Amtrak Cascades",
        "tagline": "Pacific Northwest corridor service with station-to-station travel between Vancouver, Seattle, Portland, and Eugene.",
        "description": "A scenic corridor route built for route browsing, multi-city planning, and service-alert tasks.",
        "route_type": "Corridor",
        "service_level": "Regional",
        "frequency_note": "Morning and afternoon demo departures with direct options.",
        "stops": ["VAN", "SEA", "PDX", "EUG"],
        "travel": [165, 190, 145],
        "dwell": [0, 7, 8, 0],
        "departures": {"outbound": "08:00", "inbound": "09:10"},
        "featured": True,
        "overnight": False,
        "base_fare": 61.0,
        "features": ["Bike spaces", "Cafe bar", "Scenic routing", "Business seating"],
        "equipment": "Talgo-style demo set",
        "base_number": 506,
    },
    {
        "slug": "coast-starlight",
        "name": "Coast Starlight",
        "tagline": "A Pacific coast overnight journey from Seattle to Los Angeles via Oregon and California.",
        "description": "A long-haul coastal flagship with sleeper rooms, scenic destination tie-ins, and multiple service-alert opportunities.",
        "route_type": "Long Distance",
        "service_level": "Sleeper",
        "frequency_note": "Daily synthetic overnight departure with premium room inventory.",
        "stops": ["SEA", "PDX", "EUG", "SAC", "EMY", "SBA", "LAX"],
        "travel": [225, 150, 540, 95, 325, 160],
        "dwell": [0, 8, 7, 10, 8, 6, 0],
        "departures": {"outbound": "09:45", "inbound": "10:30"},
        "featured": True,
        "overnight": True,
        "base_fare": 151.0,
        "features": ["Roomettes", "Bedrooms", "Sightseer-style lounge copy", "Coastal stop pattern"],
        "equipment": "Coastal sleeper consist",
        "base_number": 14,
    },
    {
        "slug": "pacific-surfliner",
        "name": "Pacific Surfliner",
        "tagline": "Frequent Southern California travel between the Central Coast, Los Angeles, Orange County, and San Diego.",
        "description": "A bright day-trip route with dense local travel, ideal for booking, checkout, and used-route comparison tasks.",
        "route_type": "Corridor",
        "service_level": "Regional",
        "frequency_note": "Frequent day departures with simple direct options.",
        "stops": ["SLO", "SBA", "LAX", "ANA", "SAN"],
        "travel": [150, 115, 40, 110],
        "dwell": [0, 6, 8, 4, 0],
        "departures": {"outbound": "06:55", "inbound": "07:15"},
        "featured": True,
        "overnight": False,
        "base_fare": 52.0,
        "features": ["Bike racks", "Cafe service", "Family-friendly timing"],
        "equipment": "California corridor coaches",
        "base_number": 761,
    },
    {
        "slug": "capitol-corridor",
        "name": "Capitol Corridor",
        "tagline": "Bay Area and Sacramento corridor service for quick regional hops.",
        "description": "A short-haul Northern California route with dense stop patterns and clean compareable direct itineraries.",
        "route_type": "State Supported",
        "service_level": "Regional",
        "frequency_note": "Several short-haul departures per demo day.",
        "stops": ["SAC", "EMY", "OKJ", "SJC"],
        "travel": [85, 12, 70],
        "dwell": [0, 4, 4, 0],
        "departures": {"outbound": "07:30", "inbound": "08:20"},
        "featured": False,
        "overnight": False,
        "base_fare": 39.0,
        "features": ["Quiet tables", "Short city hops", "High frequency"],
        "equipment": "Northern California corridor set",
        "base_number": 531,
    },
    {
        "slug": "california-zephyr",
        "name": "California Zephyr",
        "tagline": "A cross-country Rockies route from Chicago through Denver, Utah, Nevada, and the Bay Area.",
        "description": "A flagship overnight route with room selection, schedule comparison, and route-stop reasoning built in.",
        "route_type": "Long Distance",
        "service_level": "Sleeper",
        "frequency_note": "One long-haul departure each seeded service day.",
        "stops": ["CHI", "OMA", "DEN", "GLN", "SLC", "RNO", "EMY"],
        "travel": [510, 500, 360, 330, 520, 250],
        "dwell": [0, 10, 8, 8, 7, 6, 0],
        "departures": {"outbound": "14:00", "inbound": "08:50"},
        "featured": True,
        "overnight": True,
        "base_fare": 179.0,
        "features": ["Roomettes", "Bedrooms", "Mountain schedule", "Large-window lounge copy"],
        "equipment": "Superliner-style overnight set",
        "base_number": 5,
    },
    {
        "slug": "southwest-chief",
        "name": "Southwest Chief",
        "tagline": "A long-distance route from Chicago to Los Angeles via the central plains and desert southwest.",
        "description": "An overnight western route suited for sleeper selection, booking lookup, and service-alert reasoning tasks.",
        "route_type": "Long Distance",
        "service_level": "Sleeper",
        "frequency_note": "Daily synthetic overnight run with varied room inventory.",
        "stops": ["CHI", "KCY", "ABQ", "FLG", "LAX"],
        "travel": [420, 840, 360, 470],
        "dwell": [0, 9, 8, 7, 0],
        "departures": {"outbound": "15:10", "inbound": "09:25"},
        "featured": False,
        "overnight": True,
        "base_fare": 171.0,
        "features": ["Desert timing", "Roomettes", "Bedrooms", "Long-distance dining copy"],
        "equipment": "Superliner-style overnight set",
        "base_number": 3,
    },
    {
        "slug": "texas-eagle",
        "name": "Texas Eagle",
        "tagline": "A north-south route joining Texas metros with St. Louis and Chicago.",
        "description": "A long-distance route with a clear Texas corridor section, good for short-haul and overnight planning within one seed.",
        "route_type": "Long Distance",
        "service_level": "Sleeper",
        "frequency_note": "Mixed day and overnight timing across the seeded calendar.",
        "stops": ["DAL", "AUS", "SAS", "STL", "CHI"],
        "travel": [210, 85, 740, 330],
        "dwell": [0, 6, 8, 8, 0],
        "departures": {"outbound": "09:20", "inbound": "11:40"},
        "featured": False,
        "overnight": True,
        "base_fare": 137.0,
        "features": ["Texas city pairs", "Roomettes", "Bedrooms", "Regional-to-overnight mix"],
        "equipment": "Texas Eagle demo consist",
        "base_number": 21,
    },
]

ALERT_SPECS = [
    {"slug": "nyp-platform-adjustment", "title": "New York platform adjustment through the midday bank", "severity": "Major Advisory", "station_code": "NYP", "message": "North River work has shifted the demo platform lineup for several corridor departures.", "next_step": "Arrive 20 minutes early and check the departure board before boarding."},
    {"slug": "northeast-weekend-speed-restrictions", "title": "Weekend speed restrictions on the Northeast Regional", "severity": "Service Alert", "route_slug": "northeast-regional", "message": "Track work between Philadelphia and Wilmington may add 10 to 20 minutes to some trips.", "next_step": "If you need a tighter connection, compare Acela Express or a later departure."},
    {"slug": "acela-cafe-restock", "title": "Acela Express cafe inventory refresh at Boston", "severity": "Advisory", "route_slug": "acela-express", "message": "Morning express departures may board with a reduced snack menu until the Boston restock window is complete.", "next_step": "Boarding time and seating are unaffected."},
    {"slug": "richmond-coach-yard-delay", "title": "Richmond coach-yard delay affecting southbound turns", "severity": "Service Alert", "station_code": "RVR", "message": "A late equipment rotation is affecting a subset of southbound departures from Richmond.", "next_step": "Check the status page before heading to the station."},
    {"slug": "carolinas-heat-advisory", "title": "Carolina corridor heat advisory", "severity": "Advisory", "route_slug": "carolinian", "message": "The demo mirror marks select afternoon departures as warm-weather slow orders.", "next_step": "Choose a morning departure if you want the shortest travel time."},
    {"slug": "savannah-coastal-transfer", "title": "Savannah station shuttle lane relocation", "severity": "Advisory", "station_code": "SAV", "message": "The pickup lane at Savannah Station has moved to the east curb for this demo service window.", "next_step": "Use the station detail page for the updated curbside notes."},
    {"slug": "chicago-concourse-crowding", "title": "Chicago concourse crowding for long-distance boarding", "severity": "Service Alert", "station_code": "CHI", "message": "Several evening long-distance departures share a tighter boarding window at Chicago Union Station.", "next_step": "Boarding groups are still honored. Give yourself extra time inside the Great Hall."},
    {"slug": "city-of-new-orleans-crew-swap", "title": "Crew swap may add time near Jackson", "severity": "Advisory", "route_slug": "city-of-new-orleans", "message": "An operational stop near Jackson may lengthen by up to 15 minutes on some days.", "next_step": "Sleepers and coach inventory are unchanged."},
    {"slug": "cascades-bus-bridge-demo", "title": "Cascades midday bus-bridge demo between Seattle and Portland", "severity": "Major Advisory", "route_slug": "amtrak-cascades", "message": "One midday option is shown with a transfer note to simulate maintenance diversions.", "next_step": "Filter for direct service if you want to avoid the transfer pattern."},
    {"slug": "coast-starlight-track-work", "title": "Coast Starlight track work south of Sacramento", "severity": "Major Advisory", "route_slug": "coast-starlight", "message": "Track maintenance south of Sacramento is modeled as a slower section for selected departures.", "next_step": "Review the fare page before booking if you need a sleeper on a tighter schedule."},
    {"slug": "surfliner-anaheim-construction", "title": "Anaheim station walkway construction", "severity": "Advisory", "station_code": "ANA", "message": "The direct walkway to the transit center is temporarily rerouted around the east plaza.", "next_step": "Add 10 extra minutes for station circulation."},
    {"slug": "zephyr-mountain-weather", "title": "Mountain weather advisory for the California Zephyr", "severity": "Service Alert", "route_slug": "california-zephyr", "message": "Rocky Mountain snowpack is represented as a mild delay risk near Glenwood Springs.", "next_step": "Flexible fares may make sense if you want easier demo change rules."},
    {"slug": "southwest-chief-desert-storm", "title": "Desert storm watch near Flagstaff", "severity": "Major Advisory", "route_slug": "southwest-chief", "message": "Western long-distance arrivals may pick up 20 to 35 minutes in the desert section.", "next_step": "Use the status page for live demo delay labels."},
    {"slug": "texas-eagle-sleeper-cleaning", "title": "Texas Eagle sleeper turnover window extended at San Antonio", "severity": "Advisory", "route_slug": "texas-eagle", "message": "Room turnover at San Antonio is slightly longer for same-day northbound departures.", "next_step": "Room inventory still reflects the updated servicing timeline."},
    {"slug": "denver-boarding-track-update", "title": "Denver boarding track update for westbound service", "severity": "Service Alert", "station_code": "DEN", "message": "The demo mirror currently boards westbound long-distance departures from track 3 instead of track 2.", "next_step": "Check station departures on the detail page."},
    {"slug": "los-angeles-evening-flow", "title": "Los Angeles evening boarding flow adjustment", "severity": "Advisory", "station_code": "LAX", "message": "Evening departures are staged in two waves to reduce crowding in the tunnel concourse.", "next_step": "Arrive 25 minutes before departure for the easiest boarding experience."},
]

HELP_ARTICLES = [
    ("demo-booking-rules", "Booking", "How the demo booking flow maps to one-way, round-trip, and multi-city search", "Understand how this local mirror stores one-way, round-trip, and multi-city searches so benchmark tasks stay deterministic."),
    ("saver-vs-value", "Fares", "Saver vs. Value fares in the local mirror", "Saver is lowest-price inventory in this mirror, while Value adds a friendlier change window for task comparisons."),
    ("flexible-and-business", "Fares", "When to choose Flexible or Business in the demo mirror", "Flexible emphasizes easier demo changes, while Business highlights a premium seat type and higher reward earnings."),
    ("sleeper-rooms-guide", "Sleeper", "Roomette, Bedroom, and Family Bedroom differences", "Sleeper rooms in this mirror are synthetic, but the comparison layout mirrors real overnight booking decisions."),
    ("baggage-overview", "Baggage", "Carry-on and checked baggage basics", "Use station detail pages to confirm whether a station in the mirror supports checked baggage and where curbside access is listed."),
    ("checked-baggage-timing", "Baggage", "When checked baggage closes before departure", "Long-distance departures in the mirror use a 45-minute checked baggage cutoff on staffed stations."),
    ("station-amenities", "Stations", "How to read station amenities and lounge access", "Station pages summarize baggage, parking, accessibility, and lounge notes pulled from the seeded database."),
    ("trip-lookup-help", "Trips", "What information the public trip lookup accepts", "Trip lookup accepts a demo booking code plus either the seeded email or a passenger last name."),
    ("change-cancel-policy", "Trips", "How demo change and cancel actions behave", "Change and cancel actions update only local synthetic records. No live reservations are touched."),
    ("service-alerts-explained", "Service Alerts", "How to interpret alert severity badges", "Advisory, Service Alert, and Major Advisory levels indicate how much a task should account for delay or routing risk."),
    ("status-page-help", "Schedules", "Reading the status board and delay labels", "The status board is tied to the mirror reference date and is designed for stable schedule inspection."),
    ("rewards-points-posting", "Rewards", "When demo rewards points post to an account", "Reward points are credited instantly after mock checkout in this mirror so account tasks stay visible."),
    ("rewards-tier-help", "Rewards", "How rewards tier labels are used in the demo", "Member, Select, and Select Plus are synthetic loyalty states meant for account and profile tasks."),
    ("accessible-travel", "Accessibility", "Accessibility notes on fare cards and passenger forms", "Business and flexible fares may show accessible availability; passenger forms also capture synthetic assistance notes."),
    ("passenger-profile-help", "Passengers", "Saved passenger profiles and checkout", "Benchmark accounts include a saved passenger profile to make repeated booking flows faster."),
    ("refunds-and-credits", "Refunds", "Refund language used in the mirror", "Refund copy is descriptive only; no real travel credits or external payment systems are involved."),
    ("best-time-to-book", "Deals", "Using the deals page to compare timing windows", "Deals combine route and destination offers with seeded booking and travel windows."),
    ("boarding-tips", "Stations", "How early to arrive at major stations", "Major hubs in the mirror usually recommend arriving 20 to 30 minutes before departure."),
    ("food-onboard", "Onboard", "Onboard cafe and dining availability", "Overnight routes include meal copy for sleeper rooms, while corridor routes emphasize cafe access."),
    ("wifi-and-power", "Onboard", "Wi-Fi, quiet cars, and power outlets", "Express and regional routes typically advertise Wi-Fi, power, and quiet-car options."),
    ("group-travel", "Passengers", "How the mirror handles multiple travelers", "Passenger count affects fare totals and room occupancy but remains fully synthetic."),
    ("multi-city-help", "Booking", "Building a multi-city itinerary", "The multi-city page stores up to three legs in session and asks you to choose one option per leg."),
    ("search-help", "Search", "Search page categories and what they include", "Global search scans routes, stations, destinations, deals, alerts, and help articles."),
    ("stations-by-region", "Stations", "Filtering stations by region", "Use the stations page to narrow the list by Northeast, South, Midwest, or West."),
    ("route-page-help", "Routes", "What route detail pages show", "Route pages include route stops, upcoming trips, related deals, and service alerts."),
    ("schedules-page-help", "Schedules", "Using station schedules to find departures", "Schedules are seeded for a fixed calendar window around the mirror reference date."),
    ("overnight-trip-tips", "Sleeper", "What sleeper selection changes at checkout", "When you choose a sleeper room, the mirror shifts that leg to flexible-style pricing plus the room delta."),
    ("business-seat-guide", "Fares", "Business seat differences on corridor trains", "Business seating generally has lower availability, higher reward earning, and quieter layouts."),
    ("baggage-at-small-stations", "Baggage", "Which smaller stations skip checked baggage", "Regional and smaller-town stations in the mirror often keep carry-on only baggage notes."),
    ("demo-safety-note", "About This Mirror", "Why the site uses synthetic demo data only", "All passenger, booking, fare, and payment records in this environment are local deterministic data for benchmarking."),
]

BOOKING_PLANS = [
    {"trip_type": "one-way", "status": "Confirmed", "fare_slug": "business", "passengers": 1, "legs": [{"route": "acela-express", "direction": "outbound", "date": date(2026, 4, 20), "origin": "NYP", "destination": "WAS", "room": "coach"}], "notes": "Fast corridor trip with business seating."},
    {"trip_type": "round-trip", "status": "Completed", "fare_slug": "value", "passengers": 1, "legs": [{"route": "northeast-regional", "direction": "inbound", "date": date(2026, 4, 16), "origin": "WAS", "destination": "PHL", "room": "coach"}, {"route": "northeast-regional", "direction": "outbound", "date": date(2026, 4, 17), "origin": "PHL", "destination": "WAS", "room": "coach"}], "notes": "Short round-trip corridor booking."},
    {"trip_type": "one-way", "status": "Confirmed", "fare_slug": "flexible", "passengers": 1, "legs": [{"route": "california-zephyr", "direction": "outbound", "date": date(2026, 4, 20), "origin": "CHI", "destination": "DEN", "room": "coach"}], "notes": "Flexible long-haul daytime segment."},
    {"trip_type": "one-way", "status": "Confirmed", "fare_slug": "flexible", "passengers": 2, "legs": [{"route": "coast-starlight", "direction": "outbound", "date": date(2026, 4, 22), "origin": "SEA", "destination": "LAX", "room": "roomette"}], "notes": "Overnight coastal roomette booking."},
    {"trip_type": "one-way", "status": "Completed", "fare_slug": "saver", "passengers": 1, "legs": [{"route": "empire-service", "direction": "outbound", "date": date(2026, 4, 14), "origin": "NYP", "destination": "BUF", "room": "coach"}], "notes": "Upstate corridor trip."},
    {"trip_type": "one-way", "status": "Confirmed", "fare_slug": "business", "passengers": 1, "legs": [{"route": "amtrak-cascades", "direction": "outbound", "date": date(2026, 4, 18), "origin": "SEA", "destination": "PDX", "room": "coach"}], "notes": "Same-day Pacific Northwest business trip."},
    {"trip_type": "one-way", "status": "Confirmed", "fare_slug": "value", "passengers": 2, "legs": [{"route": "pacific-surfliner", "direction": "outbound", "date": date(2026, 4, 20), "origin": "SBA", "destination": "SAN", "room": "coach"}], "notes": "Leisure corridor trip with two travelers."},
    {"trip_type": "one-way", "status": "Completed", "fare_slug": "flexible", "passengers": 2, "legs": [{"route": "southwest-chief", "direction": "outbound", "date": date(2026, 4, 14), "origin": "CHI", "destination": "LAX", "room": "bedroom"}], "notes": "Past cross-country sleeper trip."},
    {"trip_type": "one-way", "status": "Confirmed", "fare_slug": "flexible", "passengers": 1, "legs": [{"route": "silver-meteor", "direction": "outbound", "date": date(2026, 4, 22), "origin": "NYP", "destination": "SAV", "room": "coach"}], "notes": "Long-haul East Coast trip with higher flexibility."},
    {"trip_type": "one-way", "status": "Completed", "fare_slug": "saver", "passengers": 1, "legs": [{"route": "texas-eagle", "direction": "outbound", "date": date(2026, 4, 17), "origin": "DAL", "destination": "SAS", "room": "coach"}], "notes": "Short Texas corridor segment."},
    {"trip_type": "one-way", "status": "Confirmed", "fare_slug": "business", "passengers": 1, "legs": [{"route": "hiawatha-service", "direction": "outbound", "date": date(2026, 4, 18), "origin": "CHI", "destination": "MKE", "room": "coach"}], "notes": "Short business-day Midwest trip."},
    {"trip_type": "one-way", "status": "Confirmed", "fare_slug": "flexible", "passengers": 1, "legs": [{"route": "city-of-new-orleans", "direction": "outbound", "date": date(2026, 4, 20), "origin": "MEM", "destination": "NOL", "room": "roomette"}], "notes": "Southbound overnight booking with meals included copy."},
    {"trip_type": "one-way", "status": "Completed", "fare_slug": "value", "passengers": 1, "legs": [{"route": "capitol-corridor", "direction": "outbound", "date": date(2026, 4, 16), "origin": "SAC", "destination": "SJC", "room": "coach"}], "notes": "Short California corridor trip."},
    {"trip_type": "one-way", "status": "Confirmed", "fare_slug": "flexible", "passengers": 2, "legs": [{"route": "carolinian", "direction": "outbound", "date": date(2026, 4, 22), "origin": "WAS", "destination": "CLT", "room": "coach"}], "notes": "Future family-style corridor booking."},
    {"trip_type": "one-way", "status": "Cancelled", "fare_slug": "flexible", "passengers": 1, "legs": [{"route": "lake-shore-limited", "direction": "outbound", "date": date(2026, 4, 20), "origin": "BOS", "destination": "CHI", "room": "roomette"}], "notes": "Cancelled overnight booking retained for trip management tasks."},
]


def parse_hhmm(value):
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def palette(region):
    return REGION_COLORS.get(region, REGION_COLORS["Midwest"])


def svg_frame(title, subtitle, colors, body, width=1200, height=560):
    c1, c2, c3, c4 = colors
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="58%" stop-color="{c2}"/>
      <stop offset="100%" stop-color="{c3}"/>
    </linearGradient>
    <radialGradient id="glow" cx="78%" cy="18%" r="68%">
      <stop offset="0%" stop-color="rgba(255,255,255,0.72)"/>
      <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
    </radialGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="{c4}"/>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <rect width="{width}" height="{height}" fill="url(#glow)" opacity="0.55"/>
  <rect x="36" y="36" width="{width - 72}" height="{height - 72}" rx="32" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.16)"/>
  <text x="72" y="120" fill="white" font-family="Segoe UI, Arial, sans-serif" font-size="22" opacity="0.9">{subtitle}</text>
  <text x="72" y="176" fill="white" font-family="Georgia, Times New Roman, serif" font-size="52" font-weight="700">{title}</text>
  {body}
</svg>"""


def route_hero_svg(route_name, tagline, colors):
    body = """
  <path d="M90 420 C220 270 320 420 420 320 S610 300 730 360 S930 430 1080 250" fill="none" stroke="rgba(255,255,255,0.8)" stroke-width="10" stroke-linecap="round"/>
  <circle cx="170" cy="380" r="12" fill="white"/>
  <circle cx="370" cy="350" r="12" fill="white"/>
  <circle cx="570" cy="330" r="12" fill="white"/>
  <circle cx="790" cy="365" r="12" fill="white"/>
  <circle cx="990" cy="300" r="12" fill="white"/>
  <rect x="748" y="172" width="248" height="120" rx="26" fill="rgba(255,255,255,0.12)" stroke="rgba(255,255,255,0.22)"/>
  <rect x="782" y="202" width="180" height="58" rx="16" fill="rgba(255,255,255,0.84)"/>
  <path d="M770 230 h32 l18 -28 h96 c36 0 58 12 74 28 h28 v42 h-248 z" fill="rgba(255,255,255,0.95)"/>
  <circle cx="818" cy="278" r="20" fill="rgba(13,44,87,0.85)"/>
  <circle cx="938" cy="278" r="20" fill="rgba(13,44,87,0.85)"/>
  <text x="780" y="463" fill="white" font-family="Segoe UI, Arial, sans-serif" font-size="24" opacity="0.9">Deterministic synthetic timetable and fare inventory</text>
"""
    return svg_frame(route_name, tagline, colors, body)


def route_map_svg(route_name, stops, colors):
    c1, c2, c3, c4 = colors
    step = 1000 / max(len(stops) - 1, 1)
    circles = []
    labels = []
    path_points = []
    for index, code in enumerate(stops):
        x = 100 + index * step
        y = 300 + int(math.sin(index * 0.65) * 46)
        path_points.append(f"{x},{y}")
        circles.append(f'<circle cx="{x}" cy="{y}" r="17" fill="white" stroke="{c1}" stroke-width="8"/>')
        labels.append(f'<text x="{x}" y="{y + 54}" text-anchor="middle" fill="white" font-family="Segoe UI, Arial, sans-serif" font-size="22">{code}</text>')
    body = f"""
  <polyline points="{' '.join(path_points)}" fill="none" stroke="rgba(255,255,255,0.8)" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
  {''.join(circles)}
  {''.join(labels)}
  <text x="72" y="480" fill="white" font-family="Segoe UI, Arial, sans-serif" font-size="24" opacity="0.92">Route-stop order stays fixed across all seeded service dates.</text>
"""
    return svg_frame(route_name, "Synthetic route map", colors, body)


def station_svg(code, station_name, colors):
    body = f"""
  <rect x="92" y="280" width="1016" height="182" rx="28" fill="rgba(255,255,255,0.10)"/>
  <rect x="126" y="326" width="948" height="90" rx="18" fill="rgba(255,255,255,0.84)"/>
  <path d="M230 326 q120 -112 246 0 q126 -112 252 0 q126 -112 252 0" fill="none" stroke="rgba(255,255,255,0.64)" stroke-width="24" stroke-linecap="round"/>
  <text x="134" y="390" fill="{colors[0]}" font-family="Georgia, Times New Roman, serif" font-size="46" font-weight="700">{code}</text>
  <text x="134" y="438" fill="{colors[0]}" font-family="Segoe UI, Arial, sans-serif" font-size="24">{station_name}</text>
  <rect x="790" y="150" width="250" height="88" rx="20" fill="rgba(255,255,255,0.14)" stroke="rgba(255,255,255,0.24)"/>
  <text x="820" y="205" fill="white" font-family="Segoe UI, Arial, sans-serif" font-size="28">Station details</text>
"""
    return svg_frame(code, "Boarding, baggage, and station amenities", colors, body)


def station_icon_svg(code, colors):
    c1, c2, _c3, c4 = colors
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" role="img" aria-label="{code}">
  <rect width="160" height="160" rx="32" fill="{c4}"/>
  <rect x="18" y="18" width="124" height="124" rx="26" fill="{c1}"/>
  <path d="M46 100 q34 -38 68 0" fill="none" stroke="white" stroke-width="10" stroke-linecap="round"/>
  <rect x="38" y="76" width="84" height="30" rx="8" fill="white"/>
  <text x="80" y="60" text-anchor="middle" fill="{c2}" font-family="Segoe UI, Arial, sans-serif" font-size="24" font-weight="700">{code}</text>
</svg>"""


def city_svg(city_name, subtitle, colors):
    bars = []
    heights = [180, 250, 220, 310, 165, 210, 270, 196, 236]
    x = 720
    for idx, height in enumerate(heights):
        bars.append(
            f'<rect x="{x + idx * 38}" y="{430 - height}" width="24" height="{height}" rx="8" fill="rgba(255,255,255,{0.16 + (idx % 3) * 0.08})"/>'
        )
    body = f"""
  <circle cx="892" cy="180" r="84" fill="rgba(255,255,255,0.14)"/>
  <path d="M88 402 C218 300 320 346 418 304 S612 248 736 316" fill="none" stroke="rgba(255,255,255,0.74)" stroke-width="12" stroke-linecap="round"/>
  {''.join(bars)}
  <text x="74" y="458" fill="white" font-family="Segoe UI, Arial, sans-serif" font-size="24" opacity="0.92">{subtitle}</text>
"""
    return svg_frame(city_name, "Featured destination", colors, body)


def deal_svg(title, colors):
    body = """
  <path d="M112 278 h444 l90 -74 h284 q92 0 158 62 q66 62 66 152 h-1042 z" fill="rgba(255,255,255,0.92)"/>
  <circle cx="280" cy="430" r="28" fill="rgba(13,44,87,0.86)"/>
  <circle cx="900" cy="430" r="28" fill="rgba(13,44,87,0.86)"/>
  <rect x="134" y="170" width="320" height="78" rx="20" fill="rgba(255,255,255,0.14)" stroke="rgba(255,255,255,0.22)"/>
  <text x="166" y="219" fill="white" font-family="Segoe UI, Arial, sans-serif" font-size="28">Promo window</text>
"""
    return svg_frame(title, "Travel offer", colors, body)


def train_svg(title, subtitle, colors):
    body = """
  <path d="M228 334 h444 q84 0 148 -54 l70 -60 h138 q56 0 84 26 q28 26 28 84 v106 h-986 z" fill="rgba(255,255,255,0.92)"/>
  <rect x="310" y="250" width="232" height="60" rx="14" fill="rgba(13,44,87,0.18)"/>
  <rect x="562" y="250" width="138" height="60" rx="14" fill="rgba(13,44,87,0.18)"/>
  <circle cx="380" cy="440" r="34" fill="rgba(13,44,87,0.86)"/>
  <circle cx="862" cy="440" r="34" fill="rgba(13,44,87,0.86)"/>
  <text x="226" y="194" fill="white" font-family="Segoe UI, Arial, sans-serif" font-size="26">Deterministic rolling stock card</text>
"""
    return svg_frame(title, subtitle, colors, body)


def alert_icon_svg(severity, colors):
    c1, c2, c3, c4 = colors
    symbol = "!" if "Major" in severity else ("i" if severity == "Advisory" else "A")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" role="img" aria-label="{severity}">
  <rect width="160" height="160" rx="32" fill="{c4}"/>
  <path d="M80 26 L132 126 H28 Z" fill="{c2}" stroke="{c1}" stroke-width="10" stroke-linejoin="round"/>
  <text x="80" y="112" text-anchor="middle" fill="white" font-family="Segoe UI, Arial, sans-serif" font-size="64" font-weight="700">{symbol}</text>
  <text x="80" y="148" text-anchor="middle" fill="{c1}" font-family="Segoe UI, Arial, sans-serif" font-size="18">{severity}</text>
</svg>"""


def slug_title(value):
    return value.replace("-", " ").replace("_", " ").title()


def ensure_asset(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_instance_to_seed(base_dir):
    instance_db = base_dir / "instance" / "amtrak.db"
    seed_dir = base_dir / "instance_seed"
    seed_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(instance_db, seed_dir / "amtrak.db")


def build_cities(station_specs):
    featured = {
        "new-york",
        "washington",
        "boston",
        "chicago",
        "seattle",
        "los-angeles",
        "new-orleans",
        "sacramento",
        "portland",
        "atlanta",
        "denver",
        "san-diego",
    }
    by_slug = {}
    for spec in station_specs:
        city = by_slug.get(spec["city_slug"])
        if not city:
            by_slug[spec["city_slug"]] = {
                "slug": spec["city_slug"],
                "name": spec["city_name"],
                "state": spec["state"],
                "region": spec["region"],
                "featured": spec["city_slug"] in featured,
            }
    ordered = sorted(by_slug.values(), key=lambda item: (not item["featured"], item["name"]))
    for city in ordered:
        city["blurb"] = (
            f"{city['name']} anchors the {city['region'].lower()} demo rail map with seeded station data, local deals, "
            "and booking flows designed for stable Amtrak-style benchmarks."
        )
        city["highlight_fact"] = f"{city['name']} appears in deterministic route, station, and trip-history tasks."
    return ordered


def station_defaults(spec):
    amenities = ["Indoor waiting room", "Digital departure board", "Accessible boarding area"]
    if spec["has_checked_baggage"]:
        amenities.append("Checked baggage")
    if spec["has_lounge"]:
        amenities.append("Premium lounge access")
    if spec["is_hub"]:
        amenities.append("Multiple route connections")
    return {
        "address": f"{100 + len(spec['code']) * 7} {spec['city_name']} Station Plaza, {spec['city_name']}, {spec['state']}",
        "platform_note": "Track assignments post about 20 minutes before departure.",
        "parking_note": "Short-term rideshare curb and garage parking are available in this local mirror.",
        "hours_text": "Ticketing lobby 5:30 AM - 10:30 PM local demo time",
        "baggage_text": "Checked baggage available" if spec["has_checked_baggage"] else "Carry-on only at this station",
        "accessibility_text": "Accessible platform access, waiting room, and restrooms",
        "map_blurb": f"{spec['name']} is modeled as a {spec['region'].lower()} boarding point with clear wayfinding and transfer notes.",
        "amenities": amenities,
    }


def directional_path(route_spec, direction):
    if direction == "outbound":
        return route_spec["stops"], route_spec["travel"], route_spec["dwell"]
    return list(reversed(route_spec["stops"])), list(reversed(route_spec["travel"])), list(reversed(route_spec["dwell"]))


def total_duration_minutes(route_spec):
    return sum(route_spec["travel"]) + sum(route_spec["dwell"][1:-1])


def departure_slot_for(value):
    if value.hour < 11:
        return "Morning"
    if value.hour < 16:
        return "Afternoon"
    return "Evening"


def route_region(route_spec, station_by_code):
    return station_by_code[route_spec["stops"][0]]["region"]


def seed_database(db, models, base_dir):
    if models.Route.query.count() > 0:
        return

    cities = build_cities(STATION_SPECS)
    city_rows = {}
    station_specs_by_code = {spec["code"]: spec for spec in STATION_SPECS}

    for city in cities:
        region_colors = palette(city["region"])
        city_row = models.City(
            slug=city["slug"],
            name=city["name"],
            state=city["state"],
            region=city["region"],
            hero_image=f"images/destinations/{city['slug']}.svg",
            blurb=city["blurb"],
            highlight_fact=city["highlight_fact"],
            featured=city["featured"],
        )
        city_rows[city["slug"]] = city_row
        db.session.add(city_row)
        ensure_asset(
            base_dir / "static" / city_row.hero_image,
            city_svg(city["name"], city["highlight_fact"], region_colors),
        )
    db.session.flush()

    station_rows = {}
    for spec in STATION_SPECS:
        defaults = station_defaults(spec)
        row = models.Station(
            code=spec["code"],
            city_id=city_rows[spec["city_slug"]].id,
            name=spec["name"],
            city_name=spec["city_name"],
            state=spec["state"],
            region=spec["region"],
            address=defaults["address"],
            platform_note=defaults["platform_note"],
            parking_note=defaults["parking_note"],
            amenities_json=json.dumps(defaults["amenities"]),
            icon_path=f"images/stations/icons/{spec['code']}.svg",
            hero_image=f"images/stations/{spec['code']}.svg",
            hours_text=defaults["hours_text"],
            baggage_text=defaults["baggage_text"],
            accessibility_text=defaults["accessibility_text"],
            map_blurb=defaults["map_blurb"],
            is_hub=spec["is_hub"],
            has_lounge=spec["has_lounge"],
            has_checked_baggage=spec["has_checked_baggage"],
        )
        station_rows[spec["code"]] = row
        db.session.add(row)
        colors = palette(spec["region"])
        ensure_asset(base_dir / "static" / row.hero_image, station_svg(spec["code"], spec["name"], colors))
        ensure_asset(base_dir / "static" / row.icon_path, station_icon_svg(spec["code"], colors))
    db.session.flush()

    fare_rows = {}
    fare_specs = [
        {
            "slug": "saver",
            "name": "Saver",
            "description": "Lowest seeded fare, best for simple point-to-point planning.",
            "rules_change": "No-fee demo changes up to 24 hours before departure.",
            "rules_refund": "Demo credit only after a simulated cancellation window.",
            "seat_type": "Coach Seat",
            "points_multiplier": 1.0,
            "color": "slate",
            "sort_order": 1,
        },
        {
            "slug": "value",
            "name": "Value",
            "description": "Balanced fare with easier change language and stronger availability.",
            "rules_change": "Change before departure with no demo penalty.",
            "rules_refund": "Refundable to local demo credit before departure.",
            "seat_type": "Coach Seat",
            "points_multiplier": 1.15,
            "color": "teal",
            "sort_order": 2,
        },
        {
            "slug": "flexible",
            "name": "Flexible",
            "description": "Highest-flexibility coach-style fare, also used as the base for sleeper selections.",
            "rules_change": "Change or cancel any time before departure in the demo mirror.",
            "rules_refund": "Refundable back to the local demo payment placeholder.",
            "seat_type": "Flexible Seat",
            "points_multiplier": 1.35,
            "color": "gold",
            "sort_order": 3,
        },
        {
            "slug": "business",
            "name": "Business",
            "description": "Premium seat layout with quieter cabins and higher reward earnings.",
            "rules_change": "Same as Flexible with premium seat assignment.",
            "rules_refund": "Refundable in the local demo window.",
            "seat_type": "Business Seat",
            "points_multiplier": 1.55,
            "color": "navy",
            "sort_order": 4,
        },
    ]
    for fare_spec in fare_specs:
        fare_row = models.FareClass(**fare_spec)
        fare_rows[fare_spec["slug"]] = fare_row
        db.session.add(fare_row)
    db.session.flush()

    route_rows = {}
    trip_lookup = {}
    route_index_lookup = {}

    for route_index, route_spec in enumerate(ROUTE_SPECS):
        first_station = station_specs_by_code[route_spec["stops"][0]]
        colors = palette(first_station["region"])
        route_row = models.Route(
            slug=route_spec["slug"],
            name=route_spec["name"],
            tagline=route_spec["tagline"],
            description=route_spec["description"],
            route_type=route_spec["route_type"],
            service_level=route_spec["service_level"],
            total_duration_minutes=total_duration_minutes(route_spec),
            origin_code=route_spec["stops"][0],
            destination_code=route_spec["stops"][-1],
            overnight=route_spec["overnight"],
            featured=route_spec["featured"],
            frequency_note=route_spec["frequency_note"],
            hero_image=f"images/routes/{route_spec['slug']}-hero.svg",
            map_image=f"images/routes/{route_spec['slug']}-map.svg",
            onboard_features_json=json.dumps(route_spec["features"]),
        )
        route_rows[route_spec["slug"]] = route_row
        route_index_lookup[route_spec["slug"]] = route_index
        db.session.add(route_row)
        db.session.flush()

        ensure_asset(
            base_dir / "static" / route_row.hero_image,
            route_hero_svg(route_spec["name"], route_spec["tagline"], colors),
        )
        ensure_asset(
            base_dir / "static" / route_row.map_image,
            route_map_svg(route_spec["name"], route_spec["stops"], colors),
        )

        cumulative = 0
        for stop_order, stop_code in enumerate(route_spec["stops"]):
            if stop_order == 0:
                arrival_offset = 0
                departure_offset = 0
            else:
                arrival_offset = cumulative + route_spec["travel"][stop_order - 1]
                departure_offset = arrival_offset
                if stop_order < len(route_spec["stops"]) - 1:
                    departure_offset += route_spec["dwell"][stop_order]
                cumulative = departure_offset
            db.session.add(
                models.RouteStop(
                    route_id=route_row.id,
                    station_code=stop_code,
                    stop_order=stop_order,
                    arrival_offset_minutes=arrival_offset,
                    departure_offset_minutes=departure_offset,
                    dwell_minutes=route_spec["dwell"][stop_order],
                )
            )

        for direction in ("outbound", "inbound"):
            base_number = route_spec["base_number"] + (0 if direction == "outbound" else 1)
            depart_time = parse_hhmm(route_spec["departures"][direction])
            train = models.Train(
                route_id=route_row.id,
                number=str(base_number),
                name=route_spec["name"],
                direction=direction,
                departure_slot=departure_slot_for(depart_time),
                equipment=route_spec["equipment"],
                has_wifi=True,
                has_cafe=True,
                has_dining=route_spec["overnight"],
                has_sleepers=route_spec["overnight"],
                has_quiet_car=route_spec["service_level"] in {"Regional", "Business"},
                image_path=f"images/trains/{route_spec['slug']}-{direction}.svg",
            )
            db.session.add(train)
            db.session.flush()
            ensure_asset(
                base_dir / "static" / train.image_path,
                train_svg(f"{route_spec['name']} {base_number}", direction.title(), colors),
            )

            direction_stops, direction_travel, direction_dwell = directional_path(route_spec, direction)
            for service_date in SERVICE_DATES:
                current_dt = datetime.combine(service_date, depart_time)
                trip = models.Trip(
                    route_id=route_row.id,
                    train_id=train.id,
                    service_date=service_date,
                    direction=direction,
                    start_station_code=direction_stops[0],
                    end_station_code=direction_stops[-1],
                    departure_dt=current_dt,
                    arrival_dt=current_dt,
                    duration_minutes=0,
                    base_fare=route_spec["base_fare"] * (1.03 if direction == "inbound" else 1.0),
                    status_label="On Time",
                    delay_minutes=0,
                    boarding_track=str(1 + ((route_index + service_date.day + (1 if direction == "inbound" else 0)) % 8)),
                    service_note="Boarding begins about 20 minutes before departure.",
                    is_featured=service_date >= MIRROR_REFERENCE_DATE.date() and route_spec["featured"],
                    has_sleepers=route_spec["overnight"],
                )
                db.session.add(trip)
                db.session.flush()

                segments = []
                rolling_dt = current_dt
                for idx in range(len(direction_stops) - 1):
                    depart_dt = rolling_dt
                    arrive_dt = depart_dt + timedelta(minutes=direction_travel[idx])
                    segment = models.TripSegment(
                        trip_id=trip.id,
                        leg_order=idx,
                        from_station_code=direction_stops[idx],
                        to_station_code=direction_stops[idx + 1],
                        depart_dt=depart_dt,
                        arrive_dt=arrive_dt,
                        duration_minutes=direction_travel[idx],
                    )
                    db.session.add(segment)
                    segments.append(segment)
                    rolling_dt = arrive_dt
                    if idx + 1 < len(direction_stops) - 1:
                        rolling_dt += timedelta(minutes=direction_dwell[idx + 1])

                trip.arrival_dt = rolling_dt
                trip.duration_minutes = int((trip.arrival_dt - trip.departure_dt).total_seconds() // 60)

                delay_pattern = (route_index * 3 + service_date.day + (1 if direction == "inbound" else 0)) % 9
                if delay_pattern == 0:
                    trip.delay_minutes = 28
                    trip.status_label = "Delayed 28 min"
                    trip.service_note = "Track work may extend station dwell times."
                elif delay_pattern == 1:
                    trip.delay_minutes = 12
                    trip.status_label = "Boarding"
                    trip.service_note = "Boarding is open with normal synthetic seat inventory."
                elif delay_pattern == 2:
                    trip.status_label = "Now boarding"
                else:
                    trip.status_label = "On Time"

                base_inventory = 26 if route_spec["overnight"] else 44
                multipliers = {"saver": 1.0, "value": 1.15, "flexible": 1.34, "business": 1.58}
                for fare_slug, fare_class in fare_rows.items():
                    base_available = max(
                        2,
                        base_inventory
                        - fare_class.sort_order * 3
                        - ((service_date.day + route_index + fare_class.sort_order) % 6),
                    )
                    if fare_slug == "business" and route_spec["service_level"] == "Regional":
                        base_available = max(4, base_available - 8)
                    db.session.add(
                        models.FareOption(
                            trip_id=trip.id,
                            fare_class_id=fare_class.id,
                            multiplier=multipliers[fare_slug],
                            availability=base_available,
                            accessible_available=(trip.id + fare_class.id) % 3 != 0,
                            reward_points_base=round(trip.base_fare * multipliers[fare_slug] * fare_class.points_multiplier),
                            summary=f"{fare_class.name} fare on {route_spec['name']}",
                        )
                    )

                if route_spec["overnight"]:
                    for room_type, room_name, occupancy, delta, availability in [
                        ("roomette", "Roomette", 2, 220 + route_index * 8, 5 - (route_index % 2)),
                        ("bedroom", "Bedroom", 2, 460 + route_index * 11, 3),
                        ("family-bedroom", "Family Bedroom", 4, 620 + route_index * 14, 2 if route_index % 3 else 1),
                    ]:
                        db.session.add(
                            models.SleeperRoom(
                                trip_id=trip.id,
                                room_type=room_type,
                                name=room_name,
                                occupancy=occupancy,
                                price_delta=delta,
                                availability=max(1, availability - ((service_date.day + trip.id) % 2)),
                                meals_included=True,
                                accessible=room_type == "bedroom",
                                description=f"{room_name} for {route_spec['name']} with synthetic sleeper amenities and meal copy.",
                                image_path=f"images/rooms/{room_type}.svg",
                            )
                        )
                trip_lookup[(route_spec["slug"], direction, service_date)] = trip

    for room_type, room_name, region_name in [
        ("roomette", "Roomette", "Midwest"),
        ("bedroom", "Bedroom", "West"),
        ("family-bedroom", "Family Bedroom", "South"),
    ]:
        ensure_asset(
            base_dir / "static" / "images" / "rooms" / f"{room_type}.svg",
            city_svg(room_name, "Synthetic sleeper room illustration", palette(region_name)),
        )

    db.session.flush()

    for route_spec in ROUTE_SPECS:
        route_row = route_rows[route_spec["slug"]]
        region_colors = palette(route_region(route_spec, station_specs_by_code))
        terminal_city = station_specs_by_code[route_spec["stops"][-1]]
        deal = models.Deal(
            slug=f"{route_spec['slug']}-spring-saver",
            title=f"{route_spec['name']} from {terminal_city['city_name']} fares",
            route_id=route_row.id,
            city_id=city_rows[terminal_city["city_slug"]].id,
            description=f"Book seeded seats on {route_spec['name']} with stable travel windows and deterministic fare comparisons.",
            price_from=round(route_spec["base_fare"] * 0.72, 2),
            booking_window="Book through Apr 30, 2026 in this local mirror",
            travel_window="Travel on seeded dates between Apr 14 and Apr 24, 2026",
            terms="Demo offer only. No real inventory or payment is processed.",
            hero_image=f"images/deals/{route_spec['slug']}.svg",
            featured=route_spec["featured"],
        )
        db.session.add(deal)
        ensure_asset(base_dir / "static" / deal.hero_image, deal_svg(deal.title, region_colors))

    for alert_spec in ALERT_SPECS:
        route_id = route_rows[alert_spec["route_slug"]].id if alert_spec.get("route_slug") else None
        station_code = alert_spec.get("station_code")
        region_name = station_specs_by_code[station_code]["region"] if station_code else route_region(
            next(spec for spec in ROUTE_SPECS if spec["slug"] == alert_spec["route_slug"]),
            station_specs_by_code,
        )
        alert = models.ServiceAlert(
            slug=alert_spec["slug"],
            title=alert_spec["title"],
            severity=alert_spec["severity"],
            scope_type="route" if route_id else "station",
            route_id=route_id,
            station_code=station_code,
            start_date=date(2026, 4, 14),
            end_date=date(2026, 4, 24),
            message=alert_spec["message"],
            next_step=alert_spec["next_step"],
            badge_icon=f"images/alerts/{alert_spec['slug']}.svg",
            active=True,
        )
        db.session.add(alert)
        ensure_asset(
            base_dir / "static" / alert.badge_icon,
            alert_icon_svg(alert_spec["severity"], palette(region_name)),
        )

    for slug, category, title, summary in HELP_ARTICLES:
        body = (
            f"{summary}\n\n"
            "This page is part of a local WebHarbor benchmark mirror. All station, route, fare, booking, and reward data is synthetic and deterministic.\n\n"
            "Use the related routes, stations, trip lookup tools, and booking flows on this site to answer tasks without any live Amtrak APIs."
        )
        db.session.add(
            models.HelpArticle(
                slug=slug,
                title=title,
                category=category,
                summary=summary,
                body=body,
                icon=category.lower().replace(" ", "-"),
                popular=category in {"Booking", "Fares", "Stations", "Rewards"},
            )
        )

    db.session.commit()


def slice_segments(trip, origin_code, destination_code):
    segments = sorted(trip.segments, key=lambda segment: segment.leg_order)
    if not segments:
        return []
    codes = [segments[0].from_station_code] + [segment.to_station_code for segment in segments]
    if origin_code not in codes or destination_code not in codes:
        return []
    origin_index = codes.index(origin_code)
    destination_index = codes.index(destination_code)
    if origin_index >= destination_index:
        return []
    return segments[origin_index:destination_index]


def fare_multiplier(slug):
    return {"saver": 1.0, "value": 1.15, "flexible": 1.34, "business": 1.58}.get(slug, 1.15)


def reward_multiplier(slug):
    return {"saver": 1.0, "value": 1.15, "flexible": 1.35, "business": 1.55}.get(slug, 1.15)


def price_for_leg(trip, segments, fare_slug):
    segment_minutes = sum(segment.duration_minutes for segment in segments)
    ratio = max(0.28, min(1.0, segment_minutes / max(trip.duration_minutes, 1)))
    return round(trip.base_fare * ratio * fare_multiplier(fare_slug), 2)


def room_for_trip(trip, room_type):
    for room in trip.sleeper_rooms:
        if room.room_type == room_type:
            return room
    return None


def seat_label(trip, passenger_index, fare_slug, room_type):
    if room_type and room_type != "coach":
        room = room_for_trip(trip, room_type)
        if room:
            return f"{room.name} {passenger_index + 1}"
        return "Room pending"
    row = 3 + ((trip.id + passenger_index) % 18)
    col = "ABCD"[(trip.id + passenger_index) % 4]
    if fare_slug == "business":
        return f"Business {row}{col}"
    return f"Coach {row}{col}"


def booking_code(user_index, plan_index):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    seed = (user_index + 3) * 91 + (plan_index + 5) * 17
    chars = []
    for _ in range(4):
        chars.append(alphabet[seed % len(alphabet)])
        seed = seed * 7 + 11
    prefix = ["AL", "BO", "CA", "DA"][user_index]
    return prefix + "".join(chars)[:4]


def approval_code(user_index, plan_index):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    seed = 500 + user_index * 43 + plan_index * 19
    chars = []
    for _ in range(8):
        chars.append(alphabet[seed % len(alphabet)])
        seed = seed * 5 + 7
    return "".join(chars)


def passenger_names(user, passenger_count, plan_index):
    names = [(user.first_name, user.last_name)]
    alternates = {
        "alice.j@test.com": ("Milo", "Jordan"),
        "bob.c@test.com": ("Elena", "Castillo"),
        "carol.d@test.com": ("Nina", "Diaz"),
        "david.k@test.com": ("Ari", "Kim"),
    }
    while len(names) < passenger_count:
        names.append(alternates[user.email])
    return names


def create_booking(db, models, fare_rows, user, reward_account, user_index, plan_index, plan, trips_by_key):
    fare_slug = plan["fare_slug"]
    booking = models.Booking(
        user_id=user.id,
        booking_code=booking_code(user_index, plan_index),
        trip_type=plan["trip_type"],
        status=plan["status"],
        total_amount=0.0,
        reward_points_earned=0,
        contact_email=user.email,
        contact_phone=user.phone,
        origin_code=plan["legs"][0]["origin"],
        destination_code=plan["legs"][-1]["destination"],
        departure_date=plan["legs"][0]["date"],
        return_date=plan["legs"][-1]["date"] if plan["trip_type"] == "round-trip" else None,
        notes=plan["notes"],
        created_at=MIRROR_REFERENCE_DATE - timedelta(days=24 - plan_index - user_index, minutes=plan_index * 7),
    )
    db.session.add(booking)
    db.session.flush()

    names = passenger_names(user, plan["passengers"], plan_index)
    passengers = []
    for passenger_index, (first_name, last_name) in enumerate(names):
        passenger = models.Passenger(
            user_id=user.id,
            booking_id=booking.id,
            first_name=first_name,
            last_name=last_name,
            passenger_type="Adult" if passenger_index == 0 else "Companion",
            age_band="18+",
            accessibility_need="Boarding bridge reminder" if (passenger_index == 0 and plan_index % 7 == 0) else "",
            seat_preference="Window" if passenger_index % 2 == 0 else "Aisle",
            rewards_number=reward_account.member_number,
            email=user.email,
            phone=user.phone,
            is_saved_profile=False,
        )
        passengers.append(passenger)
        db.session.add(passenger)
    db.session.flush()

    total = 0.0
    points_total = 0
    for leg_order, leg in enumerate(plan["legs"]):
        trip = trips_by_key[(leg["route"], leg["direction"], leg["date"])]
        segments = slice_segments(trip, leg["origin"], leg["destination"])
        accommodation = "Coach Seat"
        effective_fare_slug = fare_slug
        room_type = leg.get("room", "coach")
        if room_type != "coach":
            effective_fare_slug = "flexible"
            room = room_for_trip(trip, room_type)
            accommodation = room.name if room else slug_title(room_type)
        elif fare_slug == "business":
            accommodation = "Business Seat"

        leg_price = price_for_leg(trip, segments, effective_fare_slug)
        total += leg_price * len(passengers)
        if room_type != "coach":
            room = room_for_trip(trip, room_type)
            if room:
                total += room.price_delta
        points_total += round(leg_price * len(passengers) * reward_multiplier(effective_fare_slug))

        db.session.add(
            models.BookingSegment(
                booking_id=booking.id,
                trip_id=trip.id,
                leg_order=leg_order,
                route_name=trip.route.name,
                train_number=trip.train.number,
                origin_code=leg["origin"],
                destination_code=leg["destination"],
                depart_dt=segments[0].depart_dt,
                arrive_dt=segments[-1].arrive_dt,
                fare_class_name=fare_rows[effective_fare_slug].name,
                accommodation_type=accommodation,
            )
        )

        for passenger_index, passenger in enumerate(passengers):
            db.session.add(
                models.Ticket(
                    booking_id=booking.id,
                    passenger_id=passenger.id,
                    trip_id=trip.id,
                    fare_class_id=fare_rows[effective_fare_slug].id,
                    accommodation_type=accommodation,
                    seat_or_room=seat_label(trip, passenger_index, effective_fare_slug, room_type),
                    qr_token=f"{booking.booking_code}-{leg_order + 1}-{passenger_index + 1}",
                    status="Cancelled" if plan["status"] == "Cancelled" else ("Travelled" if plan["status"] == "Completed" else "Issued"),
                )
            )

    service_fee = 9.5 + max(0, len(plan["legs"]) - 1) * 5.5
    booking.total_amount = round(total + service_fee, 2)
    booking.reward_points_earned = 0 if plan["status"] == "Cancelled" else points_total

    db.session.add(
        models.PaymentMock(
            booking_id=booking.id,
            payment_label="Demo Visa ending in 4242",
            amount=booking.total_amount,
            status="Voided" if plan["status"] == "Cancelled" else "Approved",
            approval_code=approval_code(user_index, plan_index),
            charged_at=booking.created_at + timedelta(minutes=19),
        )
    )

    if plan["status"] != "Cancelled":
        reward_account.points_balance += booking.reward_points_earned
        reward_account.points_ytd += booking.reward_points_earned
        reward_account.status_credits += max(1, int(booking.total_amount // 140))
        db.session.add(
            models.RewardActivity(
                reward_account_id=reward_account.id,
                posted_at=booking.created_at + timedelta(minutes=28),
                description=f"Booking {booking.booking_code} - {plan['legs'][0]['origin']} to {plan['legs'][-1]['destination']}",
                points_delta=booking.reward_points_earned,
                balance_after=reward_account.points_balance,
                booking_code=booking.booking_code,
                category="Travel",
            )
        )


def seed_benchmark_users(db, models, base_dir):
    existing_count = models.User.query.filter(models.User.email.in_([user["email"] for user in BENCHMARK_USERS])).count()
    if existing_count >= len(BENCHMARK_USERS):
        if not (base_dir / "instance_seed" / "amtrak.db").exists():
            copy_instance_to_seed(base_dir)
        return

    trips_by_key = {}
    for trip in models.Trip.query.all():
        trips_by_key[(trip.route.slug, trip.direction, trip.service_date)] = trip
    fare_rows = {fare.slug: fare for fare in models.FareClass.query.all()}

    for user_index, user_spec in enumerate(BENCHMARK_USERS):
        user = models.User(
            email=user_spec["email"],
            display_name=user_spec["display_name"],
            first_name=user_spec["first_name"],
            last_name=user_spec["last_name"],
            phone=user_spec["phone"],
            city=user_spec["city"],
            state=user_spec["state"],
            preferred_station_code=user_spec["preferred_station_code"],
            rewards_member_no=f"AGR-{47000 + user_index * 137}",
            created_at=MIRROR_REFERENCE_DATE - timedelta(days=42 - user_index * 5),
        )
        user.set_password(BENCHMARK_PASSWORD)
        db.session.add(user)
        db.session.flush()

        reward_account = models.RewardAccount(
            user_id=user.id,
            member_number=user.rewards_member_no,
            tier=user_spec["tier"],
            points_balance=user_spec["starter_points"],
            points_ytd=0,
            status_credits=3 + user_index,
            preferred_station_code=user.preferred_station_code,
        )
        db.session.add(reward_account)
        db.session.flush()

        db.session.add(
            models.RewardActivity(
                reward_account_id=reward_account.id,
                posted_at=user.created_at + timedelta(minutes=15),
                description="Welcome bonus for seeded benchmark account",
                points_delta=user_spec["starter_points"],
                balance_after=user_spec["starter_points"],
                booking_code="",
                category="Bonus",
            )
        )

        db.session.add(
            models.Passenger(
                user_id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                passenger_type="Adult",
                age_band="18+",
                accessibility_need="",
                seat_preference="Window",
                rewards_number=user.rewards_member_no,
                email=user.email,
                phone=user.phone,
                is_saved_profile=True,
            )
        )

        for plan_index, plan in enumerate(BOOKING_PLANS):
            create_booking(db, models, fare_rows, user, reward_account, user_index, plan_index, plan, trips_by_key)

    db.session.commit()
    copy_instance_to_seed(base_dir)

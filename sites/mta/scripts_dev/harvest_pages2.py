"""Second wave of page capture: subpages under key sections."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mfetch import fetch

PAGES = {
    "ft_subway_bus": "https://new.mta.info/fares-tolls/subway-bus",
    "ft_lirr_mnr": "https://new.mta.info/fares-tolls/lirr-metro-north",
    "ft_tolls": "https://new.mta.info/fares-tolls/tolls",
    "ft_reduced": "https://new.mta.info/fares-tolls/subway-bus/reduced-fare",
    "ft_save": "https://new.mta.info/fares-tolls/how-to-save-money",
    "ft_pretax": "https://new.mta.info/fares-tolls/pre-tax-benefits",
    "ft_2025": "https://new.mta.info/fares-tolls/2025-changes",
    "ft_tap_ride": "https://new.mta.info/fares-tolls/subway-bus/tap-and-ride",
    "guides_bikes": "https://new.mta.info/guides/bikes",
    "guides_airports": "https://new.mta.info/guides/airports",
    "guides_stadiums": "https://new.mta.info/guides/stadiums",
    "lirr_schedules": "https://new.mta.info/agency/long-island-rail-road/timetables",
    "mnr_schedules": "https://new.mta.info/agency/metro-north-railroad/schedules",
    "agency_lirr": "https://new.mta.info/agency/long-island-rail-road",
    "agency_nyct": "https://new.mta.info/agency/new-york-city-transit",
    "agency_bt": "https://new.mta.info/agency/bridges-and-tunnels",
    "agency_mnr": "https://new.mta.info/agency/metro-north-railroad",
    "transparency_board": "https://new.mta.info/transparency/board-and-committee-meetings",
    "about_leadership": "https://new.mta.info/about/leadership",
    "lost_found_lirr": "https://new.mta.info/lost-and-found/long-island-rail-road",
    "lost_found_mnr": "https://new.mta.info/lost-and-found/metro-north-railroad",
    "lost_found_nyct": "https://new.mta.info/lost-and-found/subway-bus",
    "safety_security": "https://new.mta.info/safety-and-security",
    "press_releases": "https://new.mta.info/press-release",
    "news_transitwire": "https://new.mta.info/news",
    "elevator_access": "https://new.mta.info/accessibility/elevators-escalators",
    "aar_paratransit": "https://new.mta.info/accessibility/access-a-ride",
    "procurement": "https://new.mta.info/doing-business-with-us/procurement",
}
for name, url in PAGES.items():
    html = fetch(url)
    ok = html is not None and "Access Denied" not in html[:800] and "<title>" in html[:3000]
    print(f"{name}: {'OK' if ok else 'FAIL'} {url}", flush=True)

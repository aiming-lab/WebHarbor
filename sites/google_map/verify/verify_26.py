#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--26.

Search for Los Angeles on Google Map, try to print the map as PDF and summarize the information on the map.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror has NO print/PDF control (no window.print, no print button, no
    PDF export anywhere in the site code), so the print step cannot be performed
    on the mirror; the task's gradeable part is the Los Angeles search and the
    summary of the visible information. The LA search returns 42 places incl.
    Santa Monica Pier, Getty Center, Los Angeles Hindu Temple, Beverly Jazz Club,
    Venice Beach, Griffith Observatory, Sunset Climbing Collective, Hollywood
    Boulders, Cliffs of Id - LA Climbing, Stronghold Climbing Gym, LA Boulders,
    Hollywood Rock Climbing Wall, Beverly Hills Climbing Studio, Calabasas Fine
    Art Gallery, Las Virgenes Art Studio, Mulholland Art Gallery, Agoura Hills
    Contemporary, Woodland Hills Gallery, Las Virgenes Canyon Fine Art, Apple
    Third Street Promenade, Apple The Grove, Melrose Steakhouse, Apple Century
    City, Apple Pasadena, Melrose Concept Store, Rodeo Tapas Bar, Vermont
    Bouldering Co., Pacific Coast Contemporary, Palisades Photography Gallery,
    Hollywood Sign, Apple Americana at Brand, Apple Beverly Center, Stoney Point
    Rock Gym, Malibu Creek Art Gallery, Wilshire Urban Loft, Beverly Resort,
    Apple Sherman Oaks, Sunset Pastry Shop, LA Boulders Melrose, Canyon Modern
    Art, Westside Print & Paper Gallery, Melrose Wine Bar. The map canvas also
    shows the North / Downtown / Riverfront / East District labels.
    Source: /search?q=los+angeles (42 results).

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Los Angeles search on the mirror | answer summarizes the visible LA
  information, describing at least three places from the results | read-only
  DB
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, navigated_to, navigated_any, navigated_phrase,
                        visited_place, visited_any_place, name_in, count_names,
                        contains_all, contains_any, distance_claim, minutes_claim,
                        number_claim, rating_order_ok, extract_mi_values, numbers_in)

def main():
    a = parse_args()
    j = Judge('Google Map--26', a.no_llm)
    t, fa = grade_common(j, a)
    LA_PLACES = ["Santa Monica Pier", "Getty Center", "Los Angeles Hindu Temple",
                 "Beverly Jazz Club", "Venice Beach", "Griffith Observatory",
                 "Sunset Climbing Collective", "Hollywood Boulders", "Cliffs of Id - LA Climbing",
                 "Stronghold Climbing Gym", "LA Boulders", "Hollywood Rock Climbing Wall",
                 "Beverly Hills Climbing Studio", "Calabasas Fine Art Gallery",
                 "Las Virgenes Art Studio", "Mulholland Art Gallery", "Agoura Hills Contemporary",
                 "Woodland Hills Gallery", "Las Virgenes Canyon Fine Art",
                 "Apple Third Street Promenade", "Apple The Grove", "Melrose Steakhouse",
                 "Apple Century City", "Apple Pasadena", "Melrose Concept Store",
                 "Rodeo Tapas Bar", "Vermont Bouldering Co.", "Pacific Coast Contemporary",
                 "Palisades Photography Gallery", "Hollywood Sign", "Apple Americana at Brand",
                 "Apple Beverly Center", "Stoney Point Rock Gym", "Malibu Creek Art Gallery",
                 "Wilshire Urban Loft", "Beverly Resort", "Apple Sherman Oaks",
                 "Sunset Pastry Shop", "LA Boulders Melrose", "Canyon Modern Art",
                 "Westside Print & Paper Gallery", "Melrose Wine Bar"]
    j.check("nav_los_angeles_search",
            navigated_phrase(t, "los angeles") or navigated_to(t, "/city/los-angeles"),
            "los angeles search URL in the trajectory")
    j.check("answer_describes_three_la_places", count_names(fa, LA_PLACES) >= 3,
            f"matched={count_names(fa, LA_PLACES)} final={fa[:250]!r}")
    j.emit()

if __name__ == "__main__":
    main()

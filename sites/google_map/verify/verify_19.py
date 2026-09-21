"""Deterministic verifier for Google Map task Google Map--19.

I will arrive Pittsburgh Airport soon. Provide the name of the Hilton hotel
closest to the airport. Then, tell me the the walking time to the nearest
supermarket from the hotel.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Anchoring on the Pittsburgh International Airport place, the Hilton-brand
    hotels and their distance pills are: DoubleTree by Hilton Pittsburgh
    Airport (8400 University Blvd, Coraopolis, PA 15108) 1.1 mi, Hilton Garden
    Inn Pittsburgh Airport 1.9 mi, Hilton Pittsburgh Airport 2.1 mi, Hilton
    Airport Corporate Center 2.6 mi - so the closest Hilton hotel to the
    airport is the DoubleTree by Hilton Pittsburgh Airport at 1.1 mi.
    The nearest supermarket from the DoubleTree (per the mirror's supermarket
    search anchored on the hotel and the hotel page's nearby stores) is
    'Giant Eagle Coraopolis' (513 Thorn Run Rd, 2.5 mi, walking directions
    DoubleTree -> Giant Eagle Coraopolis: 2.5 mi, ~49 min via Main St);
    'Whole Foods Market Airport Corridor' also displays 2.5 mi and a ~50 min
    walk. An answer anchored on the wrong hotel (e.g. 'Hilton Pittsburgh
    Airport' 2.1 mi) is FAIL.
    Source: /search?q=Hilton+hotels+near+Pittsburgh+International+Airport,
    /search?q=supermarket+near+DoubleTree+by+Hilton+Pittsburgh+Airport,
    /directions?from=DoubleTree+by+Hilton+Pittsburgh+Airport&to=Giant+Eagle+Coraopolis&mode=walking.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Hilton search/page AND a supermarket search or the walking directions
  | answer names DoubleTree by Hilton Pittsburgh Airport and the nearest
  supermarket with the ~49-50 min walking time | read-only DB
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, navigated_to, navigated_any, navigated_phrase,
                        visited_place, visited_any_place, name_in, count_names,
                        contains_all, contains_any, distance_claim, minutes_claim,
                        number_claim, rating_order_ok, extract_mi_values, numbers_in)

def main():
    a = parse_args()
    j = Judge('Google Map--19', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_hilton_search",
            navigated_to(t, "hilton") or visited_place(t, "pittsburgh-pa-hilton-pittsburgh-airport"),
            "hilton search or a Hilton place page in the trajectory")
    j.check("nav_supermarket_or_walking",
            navigated_any(t, ["giant eagle", "supermarket", "grocery", "whole foods"])
            or navigated_to(t, "mode=walking"),
            "supermarket search or walking directions in the trajectory")
    j.check("answer_doubletree_closest_hilton",
            name_in(fa, "DoubleTree by Hilton Pittsburgh Airport"),
            f"final={fa[:200]!r}")
    j.check("answer_nearest_supermarket",
            contains_any(fa, ["giant eagle coraopolis"])
            or contains_all(fa, ["whole foods", "airport corridor"]),
            f"final={fa[:200]!r}")
    j.check("answer_walking_time",
            minutes_claim(fa, 49) or minutes_claim(fa, 50),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()

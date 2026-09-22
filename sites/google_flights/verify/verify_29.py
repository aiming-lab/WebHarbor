#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--29.

Compare the prices and total travel time of non-stop flights Mexico City -> Frankfurt departing Mar 5, returning Mar 15.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights MEX->FRA depart 03-05 return 03-15 | the answer compares >=2 nonstop options as consistent (airline, price, duration) triples characterized as nonstop
Ground truth is HARDCODED below, frozen from the mirror's own pages (real
Chromium browser audit cross-checked against the frozen seed inventory).
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (nav_search, flights_queries, graph_queries, explore_queries,
                        q_has_value, q_matches_date, q_scalar, opened_flight_ids,
                        mentions_price, mentions_duration, mentions_airline,
                        mentions_co2, mentions_stops, consistent_pairs,
                        consistent_triples, mentions_airline_any, plain_numbers,
                        configuration_reading, foreign_airline_mentions,
                        stated_prices_consistent, run)


GROUND_TRUTH = {"nonstop_triples": [["Spirit", 486.0, 398], ["Singapore Airlines", 292.0, 364], ["United", 306.0, 332], ["Turkish Airlines", 332.0, 369], ["Southwest", 343.0, 376], ["American Airlines", 370.0, 375], ["Japan Airlines", 372.0, 379], ["Turkish Airlines", 648.0, 344], ["Lufthansa", 721.0, 344], ["American Airlines", 752.0, 378]], "nonstop_count": 10}

FROM = ["mexico city", "mex"]
TO = ["frankfurt", "fra"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "03-05", return_md="03-15"),
            "expected /flights Mexico City->Frankfurt depart 03-05 return 03-15")
    n = sum(1 for a, p, dur in GROUND_TRUTH["nonstop_triples"]
            if mentions_airline(ans, a) and mentions_price(ans, p)
            and mentions_duration(ans, dur))
    j.check("answer_compares_nonstop_options", n >= 2,
            f"{n} consistent (airline, price, duration) triples of nonstop options; "
            f"final={ans!r}")
    j.check("answer_says_nonstop", mentions_stops(ans, 0),
            f"the compared options must be characterized as nonstop; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--29", main)

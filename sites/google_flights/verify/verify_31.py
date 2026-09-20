#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--31.

Find a one-way economy flight Auckland -> Honolulu on Mar 25, browse the full page, and display a flight option with the most stops.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights AKL->HNL depart 03-25 | the answer displays one of the two 3-stop options as a consistent (airline, price) pair characterized as 3 stops
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


GROUND_TRUTH = {"most_stops": 3, "options": [["Lufthansa", 1238.0, 1134], ["Iberia", 857.0, 940]]}

FROM = ["auckland", "akl"]
TO = ["honolulu", "hnl"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "03-25"),
            "expected /flights Auckland->Honolulu depart 03-25")
    n = sum(1 for a, p, dur in GROUND_TRUTH["options"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    j.check("answer_displays_most_stops_option", n >= 1,
            f"{n} consistent (airline, price) pairs among the {len(GROUND_TRUTH['options'])} "
            f"3-stop options; final={ans!r}")
    j.check("answer_says_3stops", mentions_stops(ans, GROUND_TRUTH["most_stops"]),
            f"the displayed option must be characterized as 3 stops; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--31", main)

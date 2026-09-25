#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--21.

Locate the lowest-priced one-way flight Tokyo -> Sydney on Feb 25; include the flight duration and number of layovers.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights Tokyo->Sydney depart 02-25 | lowest price ($621) | its airline (British Airways) | its duration (18h 41m) | its 2 layovers
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


GROUND_TRUTH = {"min_price": 621.0, "airline": "British Airways", "duration": 1121, "stops": 2}

FROM = ["tokyo", "hnd", "nrt", "narita", "haneda", "tokyo narita", "tokyo haneda"]
TO = ["sydney", "syd"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "02-25"),
            "expected /flights Tokyo->Sydney depart 02-25")
    j.check("answer_lowest_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected $621; final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline British Airways; final={ans!r}")
    j.check("answer_duration", mentions_duration(ans, GROUND_TRUTH["duration"]),
            f"expected 18h 41m / 1121 minutes; final={ans!r}")
    j.check("answer_layovers", mentions_stops(ans, GROUND_TRUTH["stops"]),
            f"expected 2 stops/layovers; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--21", main)

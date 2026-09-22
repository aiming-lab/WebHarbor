#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--10.

Locate the cheapest round-trip flights New York -> Tokyo leaving Jan 25, returning Feb 15.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights NYC->Tokyo depart 01-25 return 02-15 | cheapest price ($336 leg, $1135 round-trip total on the detail page) | airline of the cheapest option
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


GROUND_TRUTH = {"min_price": 336.0, "round_trip_total": 1135.0, "airline": "United"}

FROM = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]
TO = ["tokyo", "hnd", "nrt", "narita", "haneda", "tokyo narita", "tokyo haneda"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "01-25", return_md="02-15"),
            "expected /flights NYC->Tokyo depart 01-25 return 02-15")
    j.check("answer_cheapest_price",
            mentions_price(ans, GROUND_TRUTH["min_price"])
            or mentions_price(ans, GROUND_TRUTH["round_trip_total"]),
            f"expected $336 leg or $1135 round-trip total; final={ans!r}")
    j.check("answer_airline_of_cheapest",
            mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline United; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--10", main)

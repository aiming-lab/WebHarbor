#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--18.

Compare flight options New York -> Tokyo round trip Jan 25 / Feb 15 for one adult, prioritized by the shortest travel time.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights NYC->Tokyo depart 01-25 return 02-15 | the shortest-travel-time option: 12h 30m total duration | its airline (United or Iberia, the tie set)
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


GROUND_TRUTH = {"min_duration": 750, "airlines": ["Iberia", "United"]}

FROM = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]
TO = ["tokyo", "hnd", "nrt", "narita", "haneda", "tokyo narita", "tokyo haneda"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "01-25", return_md="02-15"),
            "expected /flights NYC->Tokyo depart 01-25 return 02-15")
    j.check("answer_shortest_duration",
            mentions_duration(ans, GROUND_TRUTH["min_duration"]),
            f"expected 12h 30m / 750 minutes; final={ans!r}")
    j.check("answer_airline_of_shortest",
            mentions_airline_any(ans, GROUND_TRUTH["airlines"]),
            f"expected airline United or Iberia; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--18", main)

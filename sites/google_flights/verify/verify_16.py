#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--16.

Find the cheapest one-way flight New York -> Tokyo departing Jan 15 and provide the airline and total flight duration.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights NYC->Tokyo depart 01-15 | cheapest fare ($360) | its airline (Delta) | its total flight duration (16h 04m)
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


GROUND_TRUTH = {"min_price": 360.0, "airline": "Delta", "duration": 964}

FROM = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]
TO = ["tokyo", "hnd", "nrt", "narita", "haneda", "tokyo narita", "tokyo haneda"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "01-15"),
            "expected /flights NYC->Tokyo depart 01-15")
    j.check("answer_cheapest_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected $360; final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Delta; final={ans!r}")
    j.check("answer_total_duration", mentions_duration(ans, GROUND_TRUTH["duration"]),
            f"expected 16h 04m / 964 minutes; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--16", main)

#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--13.

Find the cheapest round-trip flight option New York City -> Tokyo departing Jan 10, returning Jan 24.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights NYC->Tokyo depart 01-10 return 01-24 | cheapest option ($298, the lowest fare the mirror shows for this round-trip search) | its airline
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


GROUND_TRUTH = {"min_price": 298.0, "airline": "British Airways"}

FROM = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]
TO = ["tokyo", "hnd", "nrt", "narita", "haneda", "tokyo narita", "tokyo haneda"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "01-10", return_md="01-24"),
            "expected /flights NYC->Tokyo depart 01-10 return 01-24")
    j.check("answer_cheapest_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected $298; final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline British Airways; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--13", main)

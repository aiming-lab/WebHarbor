#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--14.

Compare flight options and find the lowest round-trip fare New York -> London departing Jan 10, returning Jan 17.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights NYC->London depart 01-10 return 01-17 | lowest round-trip fare ($273 leg / $925 round-trip total on the detail page) | its airline
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


GROUND_TRUTH = {"min_price": 273.0, "round_trip_total": 925.0, "airline": "British Airways"}

FROM = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]
TO = ["london", "lhr", "lgw", "heathrow", "gatwick", "london heathrow", "london gatwick"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "01-10", return_md="01-17"),
            "expected /flights NYC->London depart 01-10 return 01-17")
    j.check("answer_lowest_fare",
            mentions_price(ans, GROUND_TRUTH["min_price"])
            or mentions_price(ans, GROUND_TRUTH["round_trip_total"]),
            f"expected $273 leg or $925 round-trip total; final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline British Airways; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--14", main)

#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--2.

Find the lowest fare among eligible one-way flights JFK -> Heathrow on Jan 22.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights JFK->Heathrow depart 01-22 | lowest fare $255 | airline of the cheapest flight (the 'Heathrow' input resolves to both London airports on the mirror; the minimum over that set is used)
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


GROUND_TRUTH = {"min_price": 255.0, "airline": "British Airways", "duration": 560, "stops": 1}

FROM = ["jfk", "new york", "nyc", "new york city"]
TO = ["heathrow", "lhr", "london", "lgw", "london heathrow"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "01-22"),
            "expected /flights search JFK->Heathrow depart 01-22")
    j.check("answer_lowest_fare", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected $255; final={ans!r}")
    j.check("answer_airline_of_cheapest",
            mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline British Airways; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--2", main)

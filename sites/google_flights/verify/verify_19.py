#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--19.

Find the cheapest one-way flight London -> Paris departing Jan 25; include the airline, total travel time, and layovers.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights London->Paris depart 01-25 | cheapest fare ($56) | its airline (Delta) | its total travel time (1h 31m or 2h 28m — the two $56 options) | its layover characterization (both are nonstop)
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


GROUND_TRUTH = {"min_price": 56.0, "airline": "Delta", "durations": [91, 148], "stops": 0}

FROM = ["london", "lhr", "lgw", "heathrow", "gatwick", "london heathrow", "london gatwick"]
TO = ["paris", "cdg", "charles de gaulle"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "01-25"),
            "expected /flights search London->Paris depart 01-25")
    j.check("answer_cheapest_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected $56; final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Delta; final={ans!r}")
    j.check("answer_travel_time",
            any(mentions_duration(ans, x) for x in GROUND_TRUTH["durations"]),
            f"expected 1h 31m or 2h 28m; final={ans!r}")
    j.check("answer_layovers", mentions_stops(ans, GROUND_TRUTH["stops"]),
            f"the chosen flight is nonstop (no layovers); final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--19", main)

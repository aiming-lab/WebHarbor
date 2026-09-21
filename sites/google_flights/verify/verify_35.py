#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--35.

Find the lowest-priced one-way flight Cairo -> Montreal on Feb 21; include the total travel time and number of stops.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights CAI->YUL depart 02-21 | lowest price ($321) | its airline (Qatar Airways) | total travel time (11h 02m) | number of stops (3)
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


GROUND_TRUTH = {"min_price": 321.0, "airline": "Qatar Airways", "duration": 662, "stops": 3}

FROM = ["cairo", "cai"]
TO = ["montreal", "yul"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "02-21"),
            "expected /flights Cairo->Montreal depart 02-21")
    j.check("answer_lowest_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected $321; final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Qatar Airways; final={ans!r}")
    j.check("answer_travel_time", mentions_duration(ans, GROUND_TRUTH["duration"]),
            f"expected 11h 02m / 662 minutes; final={ans!r}")
    j.check("answer_stops", mentions_stops(ans, GROUND_TRUTH["stops"]),
            f"expected 3 stops; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--35", main)

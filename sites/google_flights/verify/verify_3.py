#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--3.

Find the one-way flight Calgary -> New York on Jan 1 with the lowest CO2 emissions.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights YYC->New York depart 01-01 | lowest emissions value (90 kg CO2) | airline of that flight (Iberia)
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


GROUND_TRUTH = {"min_co2": 90, "airline": "Iberia", "price": 149.0, "duration": 152, "stops": 0}

FROM = ["calgary", "yyc"]
TO = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "01-01"),
            "expected /flights search Calgary->New York depart 01-01")
    j.check("answer_lowest_co2", mentions_co2(ans, GROUND_TRUTH["min_co2"]),
            f"expected 90 kg CO2; final={ans!r}")
    j.check("answer_airline_of_lowest_co2",
            mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Iberia; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--3", main)

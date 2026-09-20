#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--32.

Search round-trip flights Stockholm -> Toronto Mar 3..10 and sort the results to find the shortest total travel time.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights ARN->YYZ depart 03-03 return 03-10 | shortest option: 7h 34m duration | its airline (British Airways)
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


GROUND_TRUTH = {"min_duration": 454, "airline": "British Airways", "price": 542.0}

FROM = ["stockholm", "arn"]
TO = ["toronto", "yyz"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "03-03", return_md="03-10"),
            "expected /flights Stockholm->Toronto depart 03-03 return 03-10")
    j.check("answer_shortest_duration",
            mentions_duration(ans, GROUND_TRUTH["min_duration"]),
            f"expected 7h 34m / 454 minutes; final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline British Airways; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--32", main)

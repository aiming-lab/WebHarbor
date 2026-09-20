#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--22.

Find a round trip Rio de Janeiro -> Los Angeles Mar 15..22 and select the option with the least carbon dioxide emissions.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights GIG->LAX depart 03-15 return 03-22 | least-emissions option: 210 kg CO2 | its airline (Southwest)
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


GROUND_TRUTH = {"min_co2": 210, "airline": "Southwest", "price": 346.0}

FROM = ["rio de janeiro", "rio", "gig"]
TO = ["los angeles", "lax"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "03-15", return_md="03-22"),
            "expected /flights Rio->Los Angeles depart 03-15 return 03-22")
    j.check("answer_least_co2", mentions_co2(ans, GROUND_TRUTH["min_co2"]),
            f"expected 210 kg CO2; final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Southwest; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--22", main)

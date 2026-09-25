#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--30.

Find the most affordable one-way flight Cape Town -> Singapore on Mar 20; include the airline and total number of layovers.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights CPT->SIN depart 03-20 | lowest price ($265) | its airline (Frontier) | its total number of layovers (1)
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


GROUND_TRUTH = {"min_price": 265.0, "airline": "Frontier", "duration": 680, "stops": 1}

FROM = ["cape town", "cpt"]
TO = ["singapore", "sin"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "03-20"),
            "expected /flights Cape Town->Singapore depart 03-20")
    j.check("answer_lowest_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected $265; final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Frontier; final={ans!r}")
    j.check("answer_layovers", mentions_stops(ans, GROUND_TRUTH["stops"]),
            f"expected 1 stop/layover; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--30", main)

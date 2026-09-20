#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--41.

Choose a one-way business class ticket Hong Kong -> Glacier National Park on Mar 8, offering a 1-stop ticket.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights HKG->FCA depart 03-08 with Business class | the answer chooses a 1-stop option as a consistent (airline, business-class price) pair characterized as 1 stop
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


GROUND_TRUTH = {"one_stop_pairs": [["Alaska Airlines", 4049.0], ["Qatar Airways", 2189.0], ["Iberia", 3292.0], ["Delta", 2151.0], ["Lufthansa", 3342.0], ["Air France", 3952.0], ["Cathay Pacific", 2105.0], ["KLM", 4235.0], ["British Airways", 3391.0], ["Air Canada", 4690.0]], "one_stop_count": 10}

FROM = ["hong kong", "hkg"]
TO = ["glacier national park", "fca", "kalispell", "glacier park", "montana"]


def main(j, traj, ans):
    j.check("nav_search_business",
            nav_search(traj, FROM, TO, "03-08", cabin="Business"),
            "expected /flights HKG->Glacier National Park 03-08 with Business class")
    n = sum(1 for a, p in GROUND_TRUTH["one_stop_pairs"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    j.check("answer_selects_1stop_ticket", n >= 1,
            f"{n} consistent (airline, business-class price) pairs of the "
            f"{len(GROUND_TRUTH['one_stop_pairs'])} 1-stop tickets; final={ans!r}")
    j.check("answer_says_1stop", mentions_stops(ans, 1),
            f"the chosen ticket must be characterized as 1 stop; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--41", main)

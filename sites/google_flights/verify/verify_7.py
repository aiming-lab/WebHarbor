#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--7.

Find a round trip Phoenix -> Miami Dec 25..28 and show First Class tickets not exceeding $1320.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights PHX->MIA 12-25/12-28 with First class | the answer shows >=3 of the qualifying (airline, first-class price) pairs (all <= $1320)
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


GROUND_TRUTH = {"qual_pairs": [["Singapore Airlines", 430.0], ["Frontier", 495.0], ["Lufthansa", 560.0], ["Cathay Pacific", 595.0], ["Delta", 630.0], ["Air France", 660.0], ["KLM", 865.0], ["Lufthansa", 895.0], ["KLM", 895.0], ["KLM", 1160.0], ["American Airlines", 1225.0]], "cap": 1320.0}

FROM = ["phoenix", "phx"]
TO = ["miami", "mia"]


def main(j, traj, ans):
    j.check("nav_search_first_class",
            nav_search(traj, FROM, TO, "12-25", return_md="12-28", cabin="First"),
            "expected /flights PHX->MIA 12-25/12-28 with First class selected")
    n = sum(1 for a, p in GROUND_TRUTH["qual_pairs"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    j.check("answer_shows_qualifying_tickets", n >= 3,
            f"{n} consistent (airline, first-class price) pairs of the "
            f"{len(GROUND_TRUTH['qual_pairs'])} tickets under $1320; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--7", main)

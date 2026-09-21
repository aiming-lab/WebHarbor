#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--26.

Search the cheapest round-trip flights Bangkok -> Madrid Feb 26..28 and provide the options under $1000.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights BKK->MAD depart 02-26 return 02-28 | the answer presents >=3 of the under-$1000 options as (airline, price) pairs
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


GROUND_TRUTH = {"under_pairs": [["Southwest", 62.0], ["Qantas", 68.0], ["Alaska Airlines", 83.0], ["Southwest", 91.0], ["American Airlines", 96.0], ["Emirates", 110.0], ["KLM", 117.0], ["Emirates", 122.0], ["Air Canada", 130.0], ["Japan Airlines", 132.0], ["Turkish Airlines", 176.0], ["Etihad", 549.0]], "under_count": 12}

FROM = ["bangkok", "bkk"]
TO = ["madrid", "mad"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "02-26", return_md="02-28"),
            "expected /flights Bangkok->Madrid depart 02-26 return 02-28")
    n = sum(1 for a, p in GROUND_TRUTH["under_pairs"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    j.check("answer_shows_under1000_options", n >= 3,
            f"{n} consistent (airline, price) pairs of the {len(GROUND_TRUTH['under_pairs'])} "
            f"options under $1000; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--26", main)

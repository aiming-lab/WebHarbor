#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--23.

Search a one-way flight Mumbai -> Vancouver on Feb 28, filtering the results to show only 1-stop flights.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights BOM->YVR depart 02-28 WITH the 1-stop-or-fewer filter (max_stops=1) | the answer presents >=3 of the filtered options as (airline, price) pairs and speaks of 1-stop flights
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


GROUND_TRUTH = {"le1_pairs": [["Spirit", 1376.0], ["Delta", 671.0], ["KLM", 683.0], ["Japan Airlines", 719.0], ["Cathay Pacific", 938.0], ["Singapore Airlines", 1117.0], ["Turkish Airlines", 1199.0], ["Cathay Pacific", 1323.0], ["Spirit", 1368.0], ["Qantas", 1560.0], ["Air France", 1712.0], ["Southwest", 1847.0], ["Qantas", 1896.0], ["American Airlines", 1974.0]], "exactly1": 7}

FROM = ["mumbai", "bom"]
TO = ["vancouver", "yvr"]


def main(j, traj, ans):
    j.check("nav_search_1stop_filter",
            nav_search(traj, FROM, TO, "02-28", max_stops=1),
            "expected /flights BOM->YVR 02-28 with the 1-stop-or-fewer filter applied")
    n = sum(1 for a, p in GROUND_TRUTH["le1_pairs"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    says_1stop = mentions_stops(ans, 1)
    content = n >= 3 or configuration_reading(
        traj, ans, nav_search(traj, FROM, TO, "02-28", max_stops=1),
        [p for _a, p in GROUND_TRUTH["le1_pairs"]],
        [a for a, _p in GROUND_TRUTH["le1_pairs"]],
        says_1stop)
    j.check("answer_presents_filtered_flights", content,
            f"{n} consistent (airline, price) pairs of the filtered options, or a "
            f"1-stop-configuration answer with no contradicting facts; final={ans!r}")
    j.check("answer_says_1stop", says_1stop,
            f"the answer must characterize the results as 1-stop; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--23", main)

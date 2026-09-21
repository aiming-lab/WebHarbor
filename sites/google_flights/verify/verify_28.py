#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--28.

Find the best-priced round trip Seattle -> Paris departing Feb 27, returning Mar 1, with a maximum of one stop.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights SEA->CDG depart 02-27 return 03-01 | best price among the one-stop-or-fewer options ($321) | its airline (Qantas)
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


GROUND_TRUTH = {"min_price": 321.0, "airline": "Qantas"}

FROM = ["seattle", "sea"]
TO = ["paris", "cdg", "charles de gaulle"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "02-27", return_md="03-01"),
            "expected /flights Seattle->Paris depart 02-27 return 03-01")
    j.check("answer_best_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected $321 (cheapest with <=1 stop); final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Qantas; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--28", main)

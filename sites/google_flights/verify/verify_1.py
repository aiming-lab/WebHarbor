#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--1.

Show the list of one-way flights Chicago -> Paris on Feb 17.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights ORD->CDG depart 02-17 | the answer attributes >=3 on-page (airline, price) pairs to the right carrier, covering >=4 distinct airlines
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
                        stated_prices_consistent, bound_airline_price, run)


GROUND_TRUTH = {"count": 23, "min_price": 349.0, "airlines": ["ANA", "Alaska Airlines", "American Airlines", "British Airways", "Cathay Pacific", "Emirates", "Frontier", "Iberia", "Japan Airlines", "Lufthansa", "Qantas", "Qatar Airways", "Singapore Airlines", "Southwest", "Spirit", "Turkish Airlines"], "prices": [349.0, 422.0, 492.0, 520.0, 521.0, 540.0, 636.0, 649.0, 656.0, 666.0, 685.0, 704.0, 715.0, 770.0, 802.0, 874.0, 924.0, 1022.0, 1087.0, 1094.0, 1115.0, 1175.0], "pairs": [["American Airlines", 656.0], ["Japan Airlines", 349.0], ["Singapore Airlines", 492.0], ["Lufthansa", 422.0], ["Cathay Pacific", 649.0], ["Turkish Airlines", 636.0], ["Qatar Airways", 685.0], ["Lufthansa", 521.0], ["ANA", 649.0], ["Alaska Airlines", 540.0], ["British Airways", 666.0], ["Qantas", 520.0], ["Lufthansa", 715.0], ["Southwest", 704.0], ["Iberia", 874.0], ["Frontier", 802.0], ["Qatar Airways", 770.0], ["Spirit", 924.0], ["Alaska Airlines", 1094.0], ["Qatar Airways", 1087.0], ["Emirates", 1022.0], ["Qantas", 1175.0], ["Qatar Airways", 1115.0]]}

FROM = ["chicago", "ord"]
TO = ["paris", "cdg", "charles de gaulle"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "02-17"),
            "expected /flights search Chicago->Paris depart 02-17")
    bound = [(a, p) for a, p in GROUND_TRUTH["pairs"]
             if bound_airline_price(ans, a, p)]
    n_airlines = len({a for a, _p in bound})
    j.check("answer_lists_airlines", n_airlines >= 4,
            f"{n_airlines} airlines with a fare actually attributed to them")
    n_prices = len(bound)
    j.check("answer_lists_prices", n_prices >= 3,
            f"{n_prices} (airline, price) pairs attributed, not just co-present")


if __name__ == "__main__":
    run("Google Flights--1", main)

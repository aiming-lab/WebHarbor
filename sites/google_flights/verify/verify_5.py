#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--5.

Find flights Chicago -> London departing Dec 20 and returning Dec 23.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights ORD->London depart 12-20 return 12-23 | the answer presents >=3 of the 46 on-page outbound options as (airline, price) pairs
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


GROUND_TRUTH = {"count": 46, "min_price": 303.0, "pairs": [["Alaska Airlines", 670.0], ["Qatar Airways", 823.0], ["Spirit", 518.0], ["ANA", 655.0], ["British Airways", 629.0], ["ANA", 303.0], ["United", 844.0], ["Southwest", 526.0], ["Delta", 654.0], ["Singapore Airlines", 832.0], ["United", 790.0], ["JetBlue", 522.0], ["Alaska Airlines", 321.0], ["Qantas", 352.0], ["Emirates", 641.0], ["Qantas", 872.0], ["Qatar Airways", 850.0], ["United", 661.0], ["KLM", 757.0], ["Air Canada", 615.0], ["American Airlines", 730.0], ["Qatar Airways", 332.0], ["Air Canada", 601.0], ["Emirates", 384.0], ["American Airlines", 989.0], ["Turkish Airlines", 903.0], ["United", 602.0], ["Lufthansa", 1284.0], ["British Airways", 1223.0], ["Iberia", 1033.0], ["Iberia", 1216.0], ["British Airways", 982.0], ["Air Canada", 812.0], ["Qatar Airways", 951.0], ["Lufthansa", 824.0], ["Qantas", 510.0], ["Alaska Airlines", 904.0], ["KLM", 834.0], ["Spirit", 921.0], ["Qantas", 1320.0], ["Spirit", 1247.0], ["Etihad", 1424.0], ["British Airways", 968.0], ["Air France", 595.0], ["Etihad", 1052.0], ["Cathay Pacific", 1338.0]]}

FROM = ["chicago", "ord"]
TO = ["london", "lhr", "lgw", "heathrow", "gatwick", "london heathrow", "london gatwick"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "12-20", return_md="12-23"),
            "expected /flights search Chicago->London depart 12-20 return 12-23")
    n = sum(1 for a, p in GROUND_TRUTH["pairs"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    j.check("answer_presents_flights", n >= 3,
            f"{n} consistent (airline, price) pairs of {len(GROUND_TRUTH['pairs'])} "
            f"options; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--5", main)

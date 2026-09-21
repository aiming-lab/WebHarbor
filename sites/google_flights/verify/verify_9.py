#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--9.

Find a one-way economy flight Pune -> New York on Jan 15 and show how long the flight transfer takes.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights PNQ->New York depart 01-15 | the answer reports one on-page flight consistently: its airline, its total duration, and its stops/transfer wording
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


GROUND_TRUTH = {"rows": [["Qantas", 936, 2], ["Etihad", 943, 2], ["Air France", 1033, 2], ["Cathay Pacific", 809, 0], ["Cathay Pacific", 805, 1], ["Cathay Pacific", 801, 3], ["Spirit", 795, 0], ["Alaska Airlines", 791, 0], ["Singapore Airlines", 796, 0], ["Air France", 786, 1], ["Delta", 784, 0], ["Frontier", 778, 1], ["Turkish Airlines", 774, 2], ["Japan Airlines", 757, 1], ["United", 797, 0], ["United", 750, 1], ["Air France", 757, 1], ["Turkish Airlines", 828, 3], ["Cathay Pacific", 836, 2], ["ANA", 836, 0], ["Alaska Airlines", 785, 1], ["Air France", 761, 0], ["Frontier", 1063, 1], ["Alaska Airlines", 1033, 2], ["Air France", 930, 2], ["British Airways", 797, 1], ["ANA", 767, 3], ["Spirit", 812, 0], ["British Airways", 756, 0], ["ANA", 789, 1], ["Emirates", 773, 1], ["ANA", 833, 0], ["Spirit", 830, 0], ["Southwest", 819, 2], ["Delta", 829, 2], ["Air France", 788, 2], ["Turkish Airlines", 785, 1], ["Cathay Pacific", 803, 0], ["United", 781, 1], ["Qatar Airways", 765, 1], ["ANA", 773, 1], ["Lufthansa", 839, 3], ["Frontier", 785, 1], ["Iberia", 815, 0], ["ANA", 917, 3], ["Southwest", 997, 2], ["American Airlines", 951, 1], ["KLM", 757, 1], ["United", 768, 1], ["Qatar Airways", 764, 0], ["ANA", 796, 3], ["Etihad", 772, 0], ["KLM", 773, 1], ["Spirit", 823, 1], ["Air Canada", 821, 2], ["Turkish Airlines", 778, 0], ["Air France", 831, 1], ["Qatar Airways", 799, 2], ["Spirit", 836, 2], ["Alaska Airlines", 824, 1], ["ANA", 772, 1], ["Turkish Airlines", 779, 1], ["Japan Airlines", 780, 0], ["Singapore Airlines", 754, 0], ["Air Canada", 828, 0], ["Frontier", 840, 0]], "count": 66}

FROM = ["pune", "pnq"]
TO = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "01-15"),
            "expected /flights search Pune->New York depart 01-15")
    ok = 0
    for airline, dur, stops in GROUND_TRUTH["rows"]:
        if (mentions_airline(ans, airline) and mentions_duration(ans, dur)
                and mentions_stops(ans, stops)):
            ok += 1
    j.check("answer_reports_transfer_time", ok >= 1,
            f"{ok} on-page flights reported consistently (airline + total duration + "
            f"stops/transfer); final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--9", main)

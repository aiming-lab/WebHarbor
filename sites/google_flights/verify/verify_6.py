#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--6.

Search a round trip Tel Aviv -> Venice Dec 19..26 and select First Class.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights TLV->Venice depart 12-19 return 12-26 with First class | the answer reports a selected flight as a consistent (airline, first-class price) pair
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


GROUND_TRUTH = {"first_pairs": [["ANA", 2365.0], ["ANA", 3300.0], ["Air Canada", 3255.0], ["Air France", 1840.0], ["American Airlines", 1455.0], ["British Airways", 1760.0], ["Cathay Pacific", 3165.0], ["Delta", 2970.0], ["Emirates", 2620.0], ["Emirates", 3485.0], ["Etihad", 3065.0], ["Frontier", 1870.0], ["Iberia", 1680.0], ["Iberia", 2485.0], ["JetBlue", 2980.0], ["Lufthansa", 1800.0], ["Qantas", 2295.0], ["Qatar Airways", 1700.0], ["Southwest", 2065.0], ["Southwest", 3105.0], ["Southwest", 3510.0], ["Spirit", 3525.0]], "min_first": 1455.0}

FROM = ["tel aviv", "tlv"]
TO = ["venice", "vce"]


def main(j, traj, ans):
    j.check("nav_search_first_class",
            nav_search(traj, FROM, TO, "12-19", return_md="12-26", cabin="First"),
            "expected /flights TLV->Venice 12-19/12-26 with First class selected")
    n = sum(1 for a, p in GROUND_TRUTH["first_pairs"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    says_first = "first" in ans.casefold()
    content = n >= 1 or configuration_reading(
        traj, ans, nav_search(traj, FROM, TO, "12-19", return_md="12-26", cabin="First"),
        [p for _a, p in GROUND_TRUTH["first_pairs"]],
        [a for a, _p in GROUND_TRUTH["first_pairs"]],
        says_first)
    j.check("answer_selected_first_class_flight", content,
            f"{n} consistent (airline, first-class price) pairs, or a First-class "
            f"configuration answer with no contradicting facts; final={ans!r}")
    j.check("answer_says_first_class", says_first,
            f"the answer must state the First class selection; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--6", main)

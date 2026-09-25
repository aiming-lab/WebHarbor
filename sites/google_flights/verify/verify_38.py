#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--38.

Compare prices and flight durations for economy flights Oslo -> Dubai on Mar 8 and show the options with no more than two layovers.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights OSL->DXB depart 03-08 WITH the 2-stops-or-fewer filter (max_stops=2) | the answer shows >=2 of the filtered options as consistent (airline, price, duration) triples
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


GROUND_TRUTH = {"le2_triples": [["British Airways", 830.0, 509], ["Qatar Airways", 463.0, 523], ["Turkish Airlines", 460.0, 492], ["Air France", 468.0, 482], ["Etihad", 549.0, 528], ["British Airways", 489.0, 521], ["Singapore Airlines", 454.0, 623], ["Singapore Airlines", 427.0, 653], ["ANA", 481.0, 534], ["Emirates", 649.0, 565], ["Iberia", 869.0, 520], ["Turkish Airlines", 944.0, 521], ["Air Canada", 897.0, 513], ["ANA", 909.0, 533], ["ANA", 950.0, 458], ["Alaska Airlines", 949.0, 490], ["KLM", 1094.0, 468], ["Turkish Airlines", 1039.0, 478], ["American Airlines", 1126.0, 520], ["JetBlue", 1217.0, 525]], "le2_count": 20}

FROM = ["oslo", "osl"]
TO = ["dubai", "dxb"]


def main(j, traj, ans):
    j.check("nav_search_2stop_filter",
            nav_search(traj, FROM, TO, "03-08", max_stops=2),
            "expected /flights OSL->DXB 03-08 with the 2-stops-or-fewer filter applied")
    n = sum(1 for a, p, dur in GROUND_TRUTH["le2_triples"]
            if mentions_airline(ans, a) and mentions_price(ans, p)
            and mentions_duration(ans, dur))
    j.check("answer_compares_options", n >= 2,
            f"{n} consistent (airline, price, duration) triples of the filtered options; "
            f"final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--38", main)

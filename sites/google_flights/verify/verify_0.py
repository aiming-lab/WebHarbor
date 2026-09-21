#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--0.

Book a same-day round trip Edinburgh -> Manchester on Dec 28 and show the lowest-price option.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights EDI->MAN depart 12-28 + return 12-28 | lowest price ($56 one-way leg, $153 round-trip total, or $53 = the cheapest booking-site price of that flight on the detail page) | airline of the cheapest option
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


GROUND_TRUTH = {"min_leg_price": 56.0, "round_trip_total": 153.0, "cheapest_booking_price": 53.0, "airline": "United", "return_airline": "Emirates"}

FROM = ["edinburgh", "edinburg", "edi"]
TO = ["manchester", "man"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "12-28", return_md="12-28"),
            "expected /flights search Edinburgh->Manchester depart 12-28 return 12-28")
    j.check("answer_lowest_price",
            mentions_price(ans, GROUND_TRUTH["min_leg_price"])
            or mentions_price(ans, GROUND_TRUTH["round_trip_total"])
            or mentions_price(ans, GROUND_TRUTH["cheapest_booking_price"]),
            f"expected $56 leg, $153 round-trip total, or the $53 cheapest "
            f"booking-site price; final={ans!r}")
    j.check("answer_airline_of_cheapest",
            mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline United; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--0", main)

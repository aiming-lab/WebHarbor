#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--40.

Browse destinations on the Google Flights homepage from Seattle, look at the destination map, and recommend famous places within reasonable distance and price.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /explore with origin SEA | the answer recommends >=3 of the reachable-from-Seattle destinations, each with its 'from' price (consistent city + price pairs from the explore page)
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


GROUND_TRUTH = {"destinations": [["Miami", 89.0], ["Boston", 89.0], ["Toronto", 89.0], ["New York", 90.0], ["New York", 90.0], ["New York", 90.0], ["Los Angeles", 90.0], ["San Francisco", 90.0], ["Atlanta", 90.0], ["Dallas", 90.0], ["Vancouver", 92.0], ["Chicago", 93.0], ["Las Vegas", 93.0], ["Honolulu", 100.0], ["Denver", 117.0], ["Cancun", 246.0], ["Buenos Aires", 250.0], ["Rio de Janeiro", 268.0], ["Mexico City", 274.0], ["Paris", 289.0], ["Lima", 309.0], ["Tokyo", 363.0], ["London", 420.0], ["London", 421.0], ["Barcelona", 421.0], ["Amsterdam", 421.0], ["Dubai", 421.0], ["Rome", 422.0], ["Madrid", 423.0], ["Prague", 423.0], ["Doha", 424.0], ["Copenhagen", 426.0], ["Lisbon", 432.0], ["Marrakech", 437.0], ["Stockholm", 451.0], ["Berlin", 472.0], ["Venice", 480.0], ["Cape Town", 482.0], ["Milan", 489.0], ["Vienna", 497.0], ["Dublin", 505.0], ["Istanbul", 523.0], ["Athens", 529.0], ["Zurich", 569.0], ["Tokyo", 621.0], ["Singapore", 622.0], ["Hong Kong", 623.0], ["Bangkok", 623.0], ["Seoul", 625.0], ["Bali", 642.0], ["Beijing", 681.0], ["Shanghai", 727.0], ["Sydney", 841.0], ["Osaka", 859.0], ["Melbourne", 923.0]]}

import re


def _mentions_city(answer, city):
    return re.search(r"\b" + re.escape(city) + r"\b", answer or "", re.I) is not None


def main(j, traj, ans):
    ok_explore = False
    for q in explore_queries(traj):
        if q_has_value(q, "origin", ["sea", "seattle"]):
            ok_explore = True
        elif not q.get("origin"):
            # the /explore route defaults origin to SEA — a bare visit serves
            # the Seattle destination page the task asks for
            ok_explore = True
    j.check("nav_explore_seattle", ok_explore,
            "expected the /explore destinations page for origin SEA (Seattle)")
    n = 0
    for city, price in set(map(tuple, GROUND_TRUTH["destinations"])):
        if _mentions_city(ans, city) and mentions_price(ans, price):
            n += 1
    j.check("answer_recommends_destinations", n >= 3,
            f"{n} consistent (destination, from-price) recommendations; final={ans[:200]!r}")


if __name__ == "__main__":
    run("Google Flights--40", main)

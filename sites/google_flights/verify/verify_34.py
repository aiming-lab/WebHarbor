#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--34.

Compare business class flights Lisbon -> Singapore one-way on Mar 15, select one flight and see which websites offer its booking options; which is cheapest.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights LIS->SIN depart 03-15 with Business class | opened a qualifying /flight/<id> detail page | the answer names the cheapest booking site for a flight the run actually opened
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


GROUND_TRUTH = {"sites": {"126355": {"airline": "Alaska Airlines", "cheapest_site": "Kiwi.com", "cheapest_price": 1048.0}, "126356": {"airline": "Air France", "cheapest_site": "AirFrance.com", "cheapest_price": 962.0}, "126357": {"airline": "Etihad", "cheapest_site": "EtihadAirways.com", "cheapest_price": 886.0}, "126358": {"airline": "United", "cheapest_site": "United.com", "cheapest_price": 741.0}, "126359": {"airline": "Air France", "cheapest_site": "AirFrance.com", "cheapest_price": 587.0}, "126360": {"airline": "Japan Airlines", "cheapest_site": "JAL.com", "cheapest_price": 1099.0}, "126361": {"airline": "Iberia", "cheapest_site": "Kiwi.com", "cheapest_price": 1501.0}, "126362": {"airline": "Alaska Airlines", "cheapest_site": "Kiwi.com", "cheapest_price": 1057.0}, "126363": {"airline": "Japan Airlines", "cheapest_site": "JAL.com", "cheapest_price": 1261.0}, "126364": {"airline": "American Airlines", "cheapest_site": "AA.com", "cheapest_price": 1164.0}, "126365": {"airline": "Alaska Airlines", "cheapest_site": "Kiwi.com", "cheapest_price": 1522.0}, "126366": {"airline": "United", "cheapest_site": "United.com", "cheapest_price": 809.0}, "126367": {"airline": "Qantas", "cheapest_site": "Kiwi.com", "cheapest_price": 662.0}, "126368": {"airline": "Qantas", "cheapest_site": "Kiwi.com", "cheapest_price": 686.0}, "126369": {"airline": "Delta", "cheapest_site": "Delta.com", "cheapest_price": 959.0}, "126370": {"airline": "Delta", "cheapest_site": "Delta.com", "cheapest_price": 1504.0}, "126371": {"airline": "Air France", "cheapest_site": "AirFrance.com", "cheapest_price": 821.0}, "126372": {"airline": "Emirates", "cheapest_site": "Emirates.com", "cheapest_price": 746.0}, "126373": {"airline": "Etihad", "cheapest_site": "EtihadAirways.com", "cheapest_price": 1687.0}, "126374": {"airline": "Air Canada", "cheapest_site": "Kiwi.com", "cheapest_price": 1356.0}, "126375": {"airline": "Delta", "cheapest_site": "Delta.com", "cheapest_price": 1042.0}, "126376": {"airline": "Lufthansa", "cheapest_site": "Lufthansa.com", "cheapest_price": 1718.0}}}

FROM = ["lisbon", "lis"]
TO = ["singapore", "sin"]


def _site_word(site):
    return site


def main(j, traj, ans):
    j.check("nav_search_business",
            nav_search(traj, FROM, TO, "03-15", cabin="Business"),
            "expected /flights LIS->SIN 03-15 with Business class selected")
    opened = opened_flight_ids(traj)
    qualifying = [fid for fid in opened if str(fid) in GROUND_TRUTH["sites"]]
    j.check("opened_flight_detail", bool(qualifying),
            f"opened flight ids {sorted(opened)}; expected one of the route's "
            f"{len(GROUND_TRUTH['sites'])} flights")
    if not qualifying:
        return
    low = ans.casefold()
    hit = None
    for fid in qualifying:
        site = GROUND_TRUTH["sites"][str(fid)]["cheapest_site"]
        if _site_word(site).casefold() in low:
            hit = (fid, site)
            break
    j.check("answer_names_cheapest_site", hit is not None,
            f"expected the cheapest booking site of an opened flight "
            f"{[GROUND_TRUTH['sites'][str(f)]['cheapest_site'] for f in qualifying]}; "
            f"final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--34", main)

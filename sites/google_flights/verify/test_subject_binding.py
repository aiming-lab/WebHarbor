"""Synthetic answer controls; these are not browser trajectories."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("binding_lib", Path(__file__).with_name("verify_lib.py"))
lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lib)

def bound(text):
    return lib.bound_airline_price(text, "Delta", 200)


def test_equivalent_fare_prose_and_rows():
    for text in ["Delta costs $200. United costs $300.",
                 "$200 for Delta. $300 for United.",
                 "| Airline | Fare |\n| Delta | $200 |\n| United | $300 |"]:
        assert bound(text), text


def test_swapped_or_negated_fares():
    for text in ["Delta costs $300. United costs $200.",
                 "$300 for Delta. $200 for United.",
                 "Delta is not $200; it is $300."]:
        assert not bound(text), text


def test_multi_fact_rows_stay_together():
    text = "Delta $200, 2h 10m. United $300, 3h 20m."
    assert lib.bound_airline_price_duration(text, "Delta", 200, 130)
    assert not lib.bound_airline_price_duration(text, "Delta", 200, 200)

"""Synthetic answer controls; these are not browser trajectories."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("binding_lib", Path(__file__).with_name("verify_lib.py"))
lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lib)

def bound(text, price=20):
    return lib.price_bound_to(text, ["Alpha"], price, [["Beta"]])


def test_equivalent_price_prose_and_rows():
    for text in ["Alpha costs $20. Beta costs $30.",
                 "$20 for Alpha. $30 for Beta.",
                 "| Product | USD |\n| Alpha | USD 20 |\n| Beta | $30 |",
                 "Alpha costs $20.0.", "Alpha costs 20 dollars."]:
        assert bound(text), text


def test_wrong_negated_and_partial_amounts():
    for text in ["Alpha costs $30. Beta costs $20.",
                 "$30 for Alpha. $20 for Beta.",
                 "Alpha is not $20; it is $30.",
                 "Alpha costs $20.001.", "Alpha costs $120."]:
        assert not bound(text), text


def test_decimal_and_thousands_values():
    assert lib.price_bound_to("Alpha costs $1,299.99.", ["Alpha"], 1299.99)
    assert lib.price_bound_to("Alpha costs USD 64.99.", ["Alpha"], 64.99)
    assert not lib.price_bound_to("Alpha costs $164.99.", ["Alpha"], 64.99)
    assert not lib.price_bound_to("Alpha costs $64.999.", ["Alpha"], 64.99)

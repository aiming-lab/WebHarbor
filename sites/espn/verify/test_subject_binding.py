"""Synthetic answer controls; these are not browser trajectories."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("binding_lib", Path(__file__).with_name("verify_lib.py"))
lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lib)

def bound(text):
    return lib.number_bound_to(text, ["Celtics"], 64, [["Heat"]])


def test_equivalent_stat_prose_and_rows():
    for text in ["Celtics have 64 wins. Heat have 46 wins.",
                 "64 for Celtics. 46 for Heat.",
                 "| Team | Wins |\n| Celtics | 64 |\n| Heat | 46 |"]:
        assert bound(text), text


def test_swapped_or_negated_stats():
    for text in ["Celtics have 46 wins. Heat have 64 wins.",
                 "46 for Celtics. 64 for Heat.",
                 "Celtics do not have 64 wins; they have 46."]:
        assert not bound(text), text


def test_records_and_unicode():
    assert lib.record_bound_to("Celtics: 64–18. Heat: 46–36.", ["Celtics"], 64, 18, [["Heat"]])
    assert not lib.record_bound_to("Celtics: 46–36. Heat: 64–18.", ["Celtics"], 64, 18, [["Heat"]])
    assert lib.number_bound_to("Dončić: 33.9 PPG. Embiid: 34.7 PPG.", ["doncic"], 33.9, [["embiid"]])

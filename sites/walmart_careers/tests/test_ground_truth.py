from __future__ import annotations

import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE / "verify"))

from ground_truth import all_ground_truth  # noqa: E402

SEED = SITE / "instance_seed" / "walmart_careers.db"
EXPECTED_TARGETS = {
    0: "CP-5991-12522",
    1: "R-2468347",
    2: "CP-9054-10921",
    3: "CP-5260-11531",
    4: "CP-4750-11130",
    5: "R-2411489",
    6: "CP-2073-11104",
    7: "R-2447168",
    8: "CP-1230-11592",
    9: "CP-6038-10642",
    10: "R-2456729",
    11: "CP-6088-10659",
    12: "CP-5991-11940",
    13: "CP-4137-10959",
    14: "CP-9046-11274",
    15: "R-2434655",
    16: "CP-2503-10981",
    17: "CP-2503-11505",
    18: "CP-6014-13829",
    19: "CP-1179-11202",
}


def test_all_tasks_have_unique_derived_ground_truth():
    facts = all_ground_truth(SEED)
    assert set(facts) == set(range(20))
    assert {number: row["target"]["job_id"] for number, row in facts.items()} == EXPECTED_TARGETS
    assert len(facts[8]["candidates"]) == 2
    assert len(facts[9]["candidates"]) == 2
    assert len(facts[10]["candidates"]) == 2
    assert len(facts[18]["candidates"]) == 2
    assert len(facts[16]["candidates"]) >= 2
    assert len(facts[19]["candidates"]) >= 2


def test_stateful_task_preconditions_are_unique():
    facts = all_ground_truth(SEED)
    assert len(facts[12]["candidates"]) == 1
    assert facts[12]["target"]["banner"] == "Neighborhood Market"
    assert len(facts[17]["candidates"]) == 1
    assert facts[17]["target"]["employment_type"] == "Part time"
    assert facts[15]["target"]["confirmation_no"] == "WMC-000004"

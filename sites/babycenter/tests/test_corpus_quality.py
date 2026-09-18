from __future__ import annotations

import json
from pathlib import Path


SITE_DIR = Path(__file__).resolve().parents[1]
CORPUS = json.loads((SITE_DIR / "source_data" / "corpus.json").read_text())


def test_every_article_has_substantive_summary_and_body() -> None:
    for article in CORPUS["articles"]:
        assert len(article["summary"].strip()) >= 40, article["slug"]
        assert len(article["body"].strip()) >= 120, article["slug"]


def test_month_blocks_are_never_cut_mid_sentence() -> None:
    for month in CORPUS["months"]:
        for field in ("physical", "motor", "communication"):
            value = month[field]
            if value:
                assert value.rstrip().endswith((".", "!", "?", ")", '")')), (
                    month["month"],
                    field,
                    value[-40:],
                )


def test_no_empty_week_fact_slots() -> None:
    for week in CORPUS["weeks"]:
        for field in ("baby_summary", "body_summary", "checklist"):
            assert len(week[field].strip()) >= 30, (week["week"], field)


def test_week_checkpoints_keep_facts_in_their_stated_window() -> None:
    by_week = {row["week"]: row for row in CORPUS["weeks"]}

    assert "routine prenatal care" in by_week[18]["baby_summary"]
    assert "18 and 22 weeks" in by_week[18]["checklist"]
    assert "approximately week 20" in by_week[20]["baby_summary"]
    assert "second-trimester Quad blood test" in by_week[20]["checklist"]
    assert by_week[22]["body_summary"].startswith("The WHO defines the perinatal period")
    assert "At 28 weeks" in by_week[28]["baby_summary"]
    assert "between 34 and 37 weeks" in by_week[34]["baby_summary"]

    for row in CORPUS["weeks"]:
        assert not row["body_summary"].startswith("This offers"), row["week"]

"""Declared natural-language positives and attribution/boundary counterexamples."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_lib import number_bound_to, score_bound_to, contains_whole_number, date_bound_to

@pytest.mark.parametrize('text,expected',[
 ('Raiders: 26. Eagles: 6.', True),
 ('26 for Raiders. 6 for Eagles.', True),
 ('Raiders | 26\nEagles | 6', True),
 ('Raiders: 6. Eagles: 26.', False),
 ('Raiders: not 26; 6 instead. Eagles: 26.', False),
 ('Raiders: 126. Eagles: 6.', False),
 ('Raiders: 26.5. Eagles: 6.', False),
 ('Raiders: 26-14. Eagles: 6.', False),
 ('Raiders: -26. Eagles: 6.', False),
])
def test_number_owner(text,expected):
 assert number_bound_to(text,['Raiders'],26,[['Eagles']]) is expected

@pytest.mark.parametrize('text,expected',[
 ('Chargers -24. Patriots +14.',True),
 ('Chargers minus 24. Patriots +14.',True),
 ('Chargers +24. Patriots -24.',False),
 ('Chargers -24.5. Patriots +14.',False),
])
def test_sign_belongs_to_subject(text,expected):
 assert number_bound_to(text,['Chargers'],-24,[['Patriots']]) is expected

@pytest.mark.parametrize('text,expected',[
 ('Week 1: 27-13. Week 2: 26-14.',True),
 ('27 to 13 in Week 1. 26 to 14 in Week 2.',True),
 ('Week 1 | 27–13\nWeek 2 | 26–14',True),
 ('Week 1: 26-14. Week 2: 27-13.',False),
 ('Week 1: not 27-13. Week 2: 27-13.',False),
])
def test_score_owner(text,expected):
 assert score_bound_to(text,['Week 1'],27,13,[['Week 2']]) is expected

@pytest.mark.parametrize('text,expected',[
 ('86 interceptions', True),('186 interceptions',False),
 ('86.5 interceptions',False),('reference x86',False),
])
def test_whole_number(text,expected):
 assert contains_whole_number(text,86) is expected

@pytest.mark.parametrize('text,expected',[
 ('Dart: Sep 23, 2026. Williams: Sep 21, 2026.', True),
 ('September 23, 2026: Dart. September 21, 2026: Williams.',True),
 ('Dart: Sep 21, 2026. Williams: Sep 23, 2026.',False),
 ('Dart: Sep 3, 2026 (page 123). Williams: Sep 21, 2026.',False),
])
def test_dates_belong_to_articles(text,expected):
 assert date_bound_to(text,['Dart'],'2026-09-23',[['Williams']]) is expected

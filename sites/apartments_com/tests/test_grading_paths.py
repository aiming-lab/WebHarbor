"""Alternative UI paths and city-count paraphrases preserve grading meaning."""
import importlib.util,json,re
from pathlib import Path
import pytest
SITE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('housing_grader',SITE/'verify/verify.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
C=json.loads((SITE/'verify/contract.json').read_text())

@pytest.mark.parametrize('answer',[
 'New York and San Antonio tie for the most listings, with 5 each.',
 'New York: 5 listings. San Antonio: five listings.',
 'San Antonio has 5 listings; New York also has 5.',
])
def test_correct_counts(answer):g.check_city_counts(answer,C['Apartments.com--15']['city_counts'])

@pytest.mark.parametrize('answer',[
 'New York: 5. San Antonio: 2.',
 'New York and San Antonio have 15 each.',
 'New York has 5 listings.',
 'New York has 5; San Antonio has 6.',
])
def test_wrong_counts(answer):
 with pytest.raises(ValueError):g.check_city_counts(answer,C['Apartments.com--15']['city_counts'])

@pytest.mark.parametrize('path,ok',[
 ('/student-housing',True),('/search?mode=student',True),
 ('/search?mode=senior',False),('/',False),
])
def test_student_paths(path,ok):
 assert bool(re.search(C['Apartments.com--15']['paths'][0],path)) is ok

def test_comparison_distinguishes_both_rental_ranges():
 answer='Mosaic: Walk Score 78; overall advertised rent $3,213–$5,751; available units $3,228–$5,749. Higher Walk Score: Mosaic.\nBeacon: Walk Score 76; advertised rent $2,077–$3,904; matching available units $2,119–$3,894.'
 g.check_claims(answer,C['Apartments.com--3']['claims'])
 g.check_rental_ranges(answer,C['Apartments.com--3']['rental_ranges'])
 for wrong in [answer.replace('3,213','3,228'),answer.replace('available units $3,228–$5,749','available units unknown'),answer.replace('overall advertised rent $3,213–$5,751; available units $3,228–$5,749','available units $3,213–$5,751; overall advertised rent $3,228–$5,749')]:
  with pytest.raises(ValueError):g.check_rental_ranges(wrong,C['Apartments.com--3']['rental_ranges'])


def test_luxury_query_needs_all_filters_and_sort():
 pattern=C['Apartments.com--9']['paths'][0]
 path='/search?city=Los+Angeles&mode=luxury&amenity=rooftop&amenity=pool&sort=price_asc'
 assert re.search(pattern,path)
 for field in ['city=Los+Angeles','mode=luxury','amenity=pool','amenity=rooftop','sort=price_asc']:
  assert not re.search(pattern,path.replace(field,''))

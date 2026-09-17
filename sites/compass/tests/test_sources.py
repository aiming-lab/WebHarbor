"""Source identity and unknown-value guards, independent of the seed builder."""
import importlib.util
import json
from pathlib import Path
import pytest

p=Path(__file__).resolve().parents[1]/'scripts/normalize_sources.py'
spec=importlib.util.spec_from_file_location('source_normalizer',p)
n=importlib.util.module_from_spec(spec); spec.loader.exec_module(n)
META={'requested_url':'https://www.compass.com/homedetails/example/id/','retrieved_at':'2026-09-06T00:00:00Z'}

def page(listing):
    return '<script>window.__INITIAL_DATA__ = '+json.dumps({'props':{'listingRelation':{'listing':listing}}})+';</script>'

def test_changed_transaction_is_rejected():
    with pytest.raises(ValueError, match='transaction changed'):
        n.normalize(page({'listingIdSHA':'rental'}),'sale',META)

def test_unknown_facts_are_not_generated():
    r=n.normalize(page({'listingIdSHA':'123'}),'123',META)
    assert r['year_built'] is None and r['beds'] is None and r['sqft'] is None
    assert r['agent'] is None and r['mls_number']=='' and r['property_type']==''

def test_listing_section_wins_over_assessor_record():
    r=n.normalize(page({'listingIdSHA':'123','price':{'lastKnown':1234567},'size':{'bedrooms':0},'detailedInfo':{'keyDetails':[{'key':'Year Built','value':'2004'},{'key':'Property Type','value':'Condo'}],'assessorDetails':{'yearBuilt':2003}}}),'123',META)
    assert r['year_built']==2004 and r['price']==1234567 and r['beds']==0

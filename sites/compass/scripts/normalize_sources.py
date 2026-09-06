"""Normalize public Compass page snapshots without executing page JavaScript.

Usage: python scripts/normalize_sources.py SNAPSHOT_DIR [OUTPUT_JSON]
SNAPSHOT_DIR contains <original_listing_id>.html and metadata .json files with
requested_url and retrieved_at. A different listing transaction is never merged.
"""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import sys


def number(value):
    try:
        value=float(str(value).replace(',', ''))
        return int(value) if value.is_integer() else value
    except (ValueError, TypeError):
        return None


def normalize(html, original_id, metadata):
    marker=re.search(r'window\.__INITIAL_DATA__\s*=\s*', html)
    if not marker:
        raise ValueError('Public listing payload missing')
    page=json.JSONDecoder().raw_decode(html[marker.end():])[0]
    listing=page.get('props',{}).get('listingRelation',{}).get('listing',{})
    if str(listing.get('listingIdSHA','')) != str(original_id):
        raise ValueError('Listing transaction changed; retain original basic snapshot only')
    details=listing.get('detailedInfo',{})
    facts={f['key']:f['value'] for f in details.get('keyDetails',[]) if f.get('key') and f.get('value') not in ('', '-', None)}
    regional={f['key']:f['value'] for f in details.get('regionalKeyDetails',[]) if f.get('key') and f.get('value') not in ('', '-', None)}
    size=listing.get('size',{})
    loc=listing.get('location',{})
    price=listing.get('price',{})
    # The listing section is authoritative here; assessor records are a different
    # source and can disagree (e.g. the public-record year may differ by one).
    record={
        'listing_id':str(original_id),
        'source_url':metadata['requested_url'],
        'retrieved_at':metadata['retrieved_at'],
        'html_sha256':hashlib.sha256(html.encode()).hexdigest(),
        'price':number(price.get('lastKnown')),
        'address':loc.get('prettyAddress',''),
        'unit':loc.get('unitNumber',''),
        'city':loc.get('city',''),
        'state':loc.get('state',''),
        'zip':loc.get('zipCode',''),
        'neighborhood':loc.get('neighborhood',''),
        'latitude':loc.get('latitude'),
        'longitude':loc.get('longitude'),
        'beds':number(size.get('bedrooms')),
        'baths_full':number(size.get('fullBathrooms')),
        'baths_half':number(size.get('halfBathrooms')),
        'baths_total':number(size.get('bathrooms')),
        'sqft':number(size.get('squareFeet')),
        'property_type':facts.get('Property Type',''),
        'year_built':number(facts.get('Year Built')),
        'mls_number':facts.get('MLS #',''),
        'status_text':facts.get('Status',listing.get('localizedStatus','')),
        'days_on_market':number(listing.get('date',{}).get('daysOnMarket')),
        'listed_at_ms':listing.get('date',{}).get('listed'),
        'description':listing.get('description',''),
        'features':details.get('amenities',[]),
        'property_facts':facts,
        'regional_facts':regional,
        'agent':None,
    }
    for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',html,re.S):
        obj=json.loads(raw)
        for graph in obj.get('@graph',[obj]):
            if str(graph.get('mpn','')) != str(original_id):
                continue
            agent=graph.get('offers',{}).get('offeredBy',{})
            if isinstance(agent,dict) and agent.get('name'):
                record['agent']={k:agent.get(k,'') for k in ('name','email','telephone')}
    # Keep only facts represented by the public page, not anonymous visitor IDs,
    # ad metadata, tracking URLs, account fields or private contact attributes.
    return record


def main():
    source=Path(sys.argv[1]); output=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).resolve().parents[1]/'source_data.json'
    rows={}; skipped={}
    def read_record(path):
        meta=path.with_suffix('.json')
        if not meta.exists(): return path.stem, None, 'Metadata missing'
        try:
            return path.stem, normalize(path.read_text(),path.stem,json.loads(meta.read_text())), None
        except (ValueError,KeyError,TypeError,OSError) as exc:
            return path.stem, None, str(exc)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for index, (key, record, error) in enumerate(pool.map(read_record, sorted(source.glob('*.html'))), 1):
            if record: rows[key]=record
            else: skipped[key]=error
            if index % 50 == 0:
                output.write_text(json.dumps({'schema_version':1,'listings':rows},ensure_ascii=False,indent=2)+'\n')
                print(f'Processed {index} snapshots; verified {len(rows)}, skipped {len(skipped)}',file=sys.stderr,flush=True)
    output.write_text(json.dumps({'schema_version':1,'listings':rows},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'verified_listings':len(rows),'skipped':len(skipped),'reasons':list(set(skipped.values()))},indent=2))


if __name__=='__main__': main()

#!/usr/bin/env python3
"""Recover selected product labels, not generic Drugs.com monographs.

Writes downloaded source/media artifacts under HF-managed paths and emits the
seed input on stdout. Run explicitly; the app and build never access the network.
SPL set IDs are curated here. Existing files must have the pinned content hash
when a label_sources.json catalog is present; upstream changes require review.
"""
import concurrent.futures
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from PIL import Image

SITE = Path(__file__).resolve().parents[1]
API = 'https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/'
SOURCES = {
    'ibuprofen': '5a709591-2fab-98e7-e063-6394a90ac50a',
    'metformin': '1ed9dde4-339c-486f-a346-dde33a5e493f',
    'warfarin': 'ecd271ad-765e-4ac5-99f4-2e9c6e466336',
    'lisinopril': '838c2d78-d2d8-4981-9ec9-e50ef9e1a5d8',
    'sertraline': 'fda754f6-d0f3-4dce-a17a-927d64f912f7',
    'atorvastatin': 'a60cc18b-0631-4cf0-b021-9f52224ece65',
    'semaglutide': 'adec4fd2-6858-4c99-91d4-531f5f2a2d79',
    'alprazolam': '388e249d-b9b6-44c3-9f8f-880eced0239f',
    'oxycodone': 'bfdfe235-d717-4855-a3c8-a13d26dadede',
    'amoxicillin': '2732a8c7-9e4b-43c9-9712-df4b237ab69c',
    'ciprofloxacin': '4dd69fb7-802a-4278-a730-c722a3ca3521',
    'naproxen': '9edac021-313e-431b-8021-0da3c1f0398b',
    'lorazepam': 'c0810422-b732-4c04-97d8-c1521c401ef4',
}
NS = {'s': 'urn:hl7-org:v3'}


def download(url, path=None, expected=None):
    if path and path.exists():
        data = path.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=45) as response:
            data = response.read(12 * 1024 * 1024 + 1)
        if len(data) > 12 * 1024 * 1024:
            raise ValueError(f'oversized source: {url}')
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    if expected and digest != expected:
        raise ValueError(f'source content changed; review required: {url}')
    return data, digest


def text(node):
    if node is None:
        return ''
    # Retain paragraph/list/table-row boundaries; never interpret source markup.
    result = node.text or ''
    for child in node:
        result += text(child)
        if child.tag.rsplit('}', 1)[-1] in {'paragraph', 'item', 'tr', 'br', 'list', 'table'}:
            result += '\n'
        elif child.tag.rsplit('}', 1)[-1] in {'td', 'th'}:
            result += ' | '
        result += child.tail or ''
    return result


def clean(node):
    return '\n'.join(re.sub(r'[ \t]+', ' ', line).strip() for line in text(node).splitlines() if line.strip())


def recover(item):
    slug, setid = item
    prior_path = SITE/'static/external_cache/dailymed/catalog.json'
    prior = {x['slug']: x for x in json.loads(prior_path.read_text())} if prior_path.exists() else {}
    pinned = prior.get(slug, {})
    xml_url = API + setid + '.xml'
    xml_path = SITE/'static/external_cache/dailymed'/f'{slug}.xml'
    raw, digest = download(xml_url, xml_path, pinned.get('xml_sha256'))
    root = ET.fromstring(raw)
    if root.find('s:setId', NS).get('root') != setid:
        raise ValueError(f'wrong SPL set for {slug}')
    media = json.loads(download(API+setid+'/media.json')[0])['data']
    version = int(root.find('s:versionNumber', NS).get('value'))
    if media['spl_version'] != version:
        raise ValueError(f'XML/media version mismatch for {slug}')
    title = media['title']
    if slug.casefold() not in title.casefold():
        raise ValueError(f'unexpected product for {slug}: {title}')
    sections = []
    packaging_names = []
    for section in root.findall('.//s:section', NS):
        code = section.find('s:code', NS)
        body = section.find('s:text', NS)
        if code is None or body is None:
            continue
        title_node = section.find('s:title', NS)
        heading = clean(title_node) or code.get('displayName', 'Label section')
        content = clean(body)
        if content:
            sections.append(dict(code=code.get('code'), title=heading, text=content))
        if code.get('code') == '51945-4':
            packaging_names.extend(x.get('value') for x in section.findall('.//s:observationMedia/s:value/s:reference', NS))
    images = []
    for entry in media['media']:
        if entry['name'] not in packaging_names:
            continue
        url = entry['url']
        if urllib.parse.urlsplit(url).hostname != 'dailymed.nlm.nih.gov':
            raise ValueError('non-DailyMed media origin')
        previous_image = next((image for image in pinned.get('images', []) if image['source_name'] == entry['name']), {})
        data, image_digest = download(url, expected=previous_image.get('sha256'))
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.format not in {'PNG', 'JPEG', 'GIF'}:
                continue
            suffix = {'PNG': '.png', 'JPEG': '.jpg', 'GIF': '.gif'}[image.format]
            size = list(image.size)
        relative = f'images/dailymed/{slug}-package{suffix}'
        target = SITE/'static'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        images.append(dict(path=relative, source_url=url, source_name=entry['name'], sha256=image_digest, dimensions=size, kind='product-specific packaging label, not a pill photograph'))
        break
    labelers = sorted({clean(x) for x in root.findall('s:author/s:assignedEntity/s:representedOrganization/s:name', NS) if clean(x)})
    forms = sorted({x.get('displayName') for x in root.findall('.//s:manufacturedProduct/s:manufacturedProduct/s:formCode', NS) if x.get('displayName')})
    routes = sorted({x.get('displayName') for x in root.findall('.//s:routeCode', NS) if x.get('displayName')})
    return dict(slug=slug, title=title, setid=setid, version=version,
        effective_date=root.find('s:effectiveTime', NS).get('value'),
        published_date=media['published_date'], retrieved_on=pinned.get('retrieved_on', datetime.now(UTC).date().isoformat()),
        source_url='https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+setid,
        xml_url=xml_url, xml_path=f'external_cache/dailymed/{slug}.xml', xml_sha256=digest,
        labelers=labelers, forms=forms, routes=routes, sections=sections, images=images)


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(recover, sorted(SOURCES.items())))
    target = SITE/'static/external_cache/dailymed/catalog.json'
    target.write_text(json.dumps(records, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps([dict(slug=r['slug'], title=r['title'], version=r['version'],
                           sections=len(r['sections']), images=len(r['images'])) for r in records], indent=2))

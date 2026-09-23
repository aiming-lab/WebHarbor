import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

SITE = Path(__file__).resolve().parents[1]


def test_label_source_integrity_and_seed_binding():
    catalog = json.loads((SITE/'static/external_cache/dailymed/catalog.json').read_text())
    assert len(catalog) == len({r['slug'] for r in catalog}) == 13
    connection = sqlite3.connect(SITE/'instance_seed/drugs_com.db')
    try:
        saved = {slug: json.loads(payload) for slug, payload in connection.execute(
            'SELECT d.slug,l.data_json FROM daily_med_label l JOIN drug d ON d.id=l.drug_id')}
        assert saved == {r['slug']: r for r in catalog}
    finally:
        connection.close()
    for label in catalog:
        raw = (SITE/'static'/label['xml_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == label['xml_sha256']
        root = ET.fromstring(raw)
        assert root.find('{urn:hl7-org:v3}setId').get('root') == label['setid']
        assert int(root.find('{urn:hl7-org:v3}versionNumber').get('value')) == label['version']
        assert label['sections'] and label['forms'] and label['routes']
        for image in label['images']:
            path = SITE/'static'/image['path']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == image['sha256']
            with Image.open(path) as decoded:
                decoded.load()
                assert list(decoded.size) == image['dimensions']


def test_label_pages_are_database_backed_and_distinct_from_fixture(client, drugs_app, monkeypatch):
    def no_file_reads(*args, **kwargs):
        raise AssertionError('HTTP handlers must not read the source catalog')
    monkeypatch.setattr(Path, 'read_bytes', no_file_reads)
    monkeypatch.setattr(Path, 'read_text', no_file_reads)
    index = client.get('/official-labels')
    assert index.status_code == 200
    for slug in ['ibuprofen', 'metformin', 'semaglutide']:
        response = client.get(f'/{slug}/official-label')
        assert response.status_code == 200
        assert b'not Drugs.com content' in response.data
        assert b'not a pill photograph' in response.data
        assert b'Archived SPL XML (offline)' in response.data
        assert b'label-section-text' in response.data
    assert client.get('/unknown/official-label').status_code == 404
    assert client.get('/acetaminophen/official-label').status_code == 404

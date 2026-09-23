"""Targeted controls for evidence integrity and entity/value binding."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as lib
from PIL import Image


def test_initial_fixture_is_reviewed_seed():
    import json
    from composed_grade import fixture_hashes
    root = Path(__file__).resolve().parents[1]
    assert fixture_hashes(root / 'instance_seed' / (root.name + '.db')) == json.loads(Path(__file__).with_name('reviewed_seed.json').read_text())

def test_corrupt_png_rejected(tmp_path):
    p = tmp_path / 'image.png'
    p.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0\0\0\rIHDR' + (1440).to_bytes(4,'big') + (1000).to_bytes(4,'big') + b'x'*2200)
    assert lib.png_size(p) is None


def test_origin_port_is_part_of_identity():
    t = {'start_url':'http://localhost:40072/', 'steps':[{'url':'http://localhost:40073/'}]}
    assert not lib.origin_ok(t)[0]


def test_encoded_query_and_duplicate_rejection():
    assert lib.navigated_query({'steps':[{'url':'http://localhost:40072/search?q=New%20York'}]}, '/search', q='New York')
    assert not lib.navigated_query({'steps':[{'url':'http://localhost:40072/search?q=bad&q=New%20York'}]}, '/search', q='New York')

def test_size_prices_bound_to_sizes():
    from grade import _coco_size_price
    assert _coco_size_price('1.7 oz costs $154; 3.4 oz costs $185; 6.8 oz costs $270.', '1.7 oz', 154)
    assert _coco_size_price('1.7 ounces: 154 dollars; 3.4 ounces: 185 dollars.', '1.7 oz', 154)
    assert not _coco_size_price('1.7 oz costs $185; 3.4 oz costs $154; 6.8 oz costs $270.', '1.7 oz', 154)


def test_jeans_sale_and_original_price_binding():
    from grade import _jeans_prices
    assert _jeans_prices("All Seasons Tech Jeans, now $43.54 (originally $64.99), with 19 sizes.", 43.54, 64.99)
    assert _jeans_prices("Original price: 64.99 dollars; current sale price: 43.54 dollars.", 43.54, 64.99)
    assert not _jeans_prices("Now $64.99, originally $43.54; 19 sizes.", 43.54, 64.99)

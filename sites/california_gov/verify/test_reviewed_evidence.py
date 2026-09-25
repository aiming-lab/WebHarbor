"""Regression controls for previously accepted fabricated evidence packages."""
import struct
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from verify_lib import png_size, origin_ok, navigated_query


def test_truncated_png_is_not_a_screenshot(tmp_path):
    path = tmp_path / 'fake.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0\0\0\rIHDR' + struct.pack('>II', 1440, 1000) + b'x' * 4000)
    assert png_size(path) is None


def test_origin_includes_port_and_before_frame():
    start = 'http://localhost:45061/'
    assert origin_ok({'start_url': start, 'steps': [{'url': start}]})[0]
    assert not origin_ok({'start_url': start, 'steps': [{'url': 'http://localhost:45062/'}]})[0]
    assert not origin_ok({'start_url': start, 'steps': [{'url': start, 'url_before': 'https://example.com/'}]})[0]


def test_decoded_query_rejects_duplicate_values():
    assert navigated_query({'steps': [{'url': 'http://localhost/search?q=prime%20numbers'}]}, '/search', q='prime numbers')
    assert not navigated_query({'steps': [{'url': 'http://localhost/search?q=wrong&q=prime%20numbers'}]}, '/search', q='prime numbers')


def test_park_and_beach_counts_cannot_be_swapped():
    from grade import _answer_ok
    assert _answer_ok("87 state parks and 63 state beaches.", 11)[0]
    assert not _answer_ok("63 state parks and 87 state beaches.", 11)[0]

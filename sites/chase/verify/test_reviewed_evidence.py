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


def test_balances_are_bound_to_accounts():
    from grade import _account_money
    honest = "Checking: $4,187.53; Savings: $12,650.00."
    swapped = "Checking: $12,650.00; Savings: $4,187.53."
    assert _account_money(honest, "checking", 4187.53)
    assert _account_money(honest, "savings", 12650)
    assert not _account_money(swapped, "checking", 4187.53)
